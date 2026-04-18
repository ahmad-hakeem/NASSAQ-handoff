"""
NASSAQ Monitoring & Health Endpoints
Provides /system/health, /system/status, /system/metrics, /system/metrics/history
"""
from fastapi import APIRouter, Depends
from datetime import datetime, timezone
import collections
import time
import os
import platform

from dependencies import db, get_current_user, require_roles, UserRole
from sqlalchemy import text as sa_text
from sqlalchemy.exc import SQLAlchemyError
import logging
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert, _gd_aggregate

logger = logging.getLogger("nassaq.monitoring_routes")

router = APIRouter(prefix="/system", tags=["Monitoring"])

_start_time = time.time()
_metrics_history: collections.deque = collections.deque(maxlen=30)
_last_net_snapshot: dict = {"bytes_sent": 0, "bytes_recv": 0, "ts": 0}
_last_cpu_snapshot: dict = {"usage_usec": 0, "ts": 0.0}

CGROUP_BASE = "/sys/fs/cgroup"


def _read_cgroup_file(path: str):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except (OSError, IOError):
        return None


def _container_memory():
    """Return container memory stats from cgroup v2, or None if unavailable."""
    current = _read_cgroup_file(f"{CGROUP_BASE}/memory.current")
    limit = _read_cgroup_file(f"{CGROUP_BASE}/memory.max")
    if current is None or limit is None:
        return None
    try:
        used_bytes = int(current)
        if limit == "max":
            return None
        limit_bytes = int(limit)
        if limit_bytes <= 0:
            return None
        return {
            "used_mb": round(used_bytes / 1024 / 1024, 1),
            "total_mb": round(limit_bytes / 1024 / 1024, 1),
            "available_mb": round(max(limit_bytes - used_bytes, 0) / 1024 / 1024, 1),
            "percent": round(used_bytes / limit_bytes * 100, 1),
        }
    except (ValueError, TypeError):
        return None


def _container_cpu():
    """Return container CPU usage as percent of allocated quota (cgroup v2)."""
    cpu_max = _read_cgroup_file(f"{CGROUP_BASE}/cpu.max")
    cpu_stat = _read_cgroup_file(f"{CGROUP_BASE}/cpu.stat")
    if cpu_stat is None:
        return None
    try:
        usage_usec = 0
        for line in cpu_stat.splitlines():
            if line.startswith("usage_usec "):
                usage_usec = int(line.split()[1])
                break
        now = time.time()
        last_usage = _last_cpu_snapshot.get("usage_usec", 0)
        last_ts = _last_cpu_snapshot.get("ts", 0.0)
        _last_cpu_snapshot["usage_usec"] = usage_usec
        _last_cpu_snapshot["ts"] = now

        # Determine cpu quota in cores
        cores = 1.0
        if cpu_max:
            parts = cpu_max.split()
            if len(parts) == 2 and parts[0] != "max":
                quota = int(parts[0])
                period = int(parts[1])
                if period > 0:
                    cores = quota / period
        if last_ts <= 0 or usage_usec < last_usage:
            return {"percent": 0, "cores": cores}
        elapsed = now - last_ts
        if elapsed <= 0:
            return {"percent": 0, "cores": cores}
        delta_sec = (usage_usec - last_usage) / 1_000_000.0
        pct = (delta_sec / (elapsed * cores)) * 100.0
        return {"percent": round(max(0.0, min(pct, 100.0)), 1), "cores": cores}
    except (ValueError, TypeError):
        return None


async def _pg_ping(db_ref):
    session = db_ref._get_session()
    if not session:
        return False, 0
    start = time.time()
    result = await session.execute(sa_text("SELECT 1"))
    result.scalar()
    latency = round((time.time() - start) * 1000, 2)
    return True, latency


async def _pg_table_count(db_ref):
    session = db_ref._get_session()
    if not session:
        return 0
    result = await session.execute(sa_text(
        "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
    ))
    return result.scalar() or 0


@router.get("/health")
async def health_check():
    db_ok = False
    db_latency_ms = 0
    try:
        db_ok, db_latency_ms = await _pg_ping(db)
    except (SQLAlchemyError, ConnectionError, OSError) as e:
        logger.error(f"Health check DB ping failed: {e}")
    except Exception as e:
        logger.error(f"Health check unexpected error: {e}")

    pool_stats = {}
    try:
        from db import get_sync_engine
        from middleware.query_monitor import get_pool_stats
        pool_stats = get_pool_stats(get_sync_engine())
    except Exception as e:
        logger.debug(f"Pool stats unavailable: {e}")

    process_stats = {}
    try:
        import psutil
        proc = psutil.Process()
        mem = proc.memory_info()
        process_stats = {
            "cpu_percent": proc.cpu_percent(interval=None),
            "memory_rss_mb": round(mem.rss / 1024 / 1024, 1),
            "threads": proc.num_threads(),
            "open_fds": proc.num_fds() if hasattr(proc, "num_fds") else None,
        }
    except Exception as e:
        logger.debug(f"Process stats unavailable: {e}")

    response_metrics = {}
    try:
        from middleware.request_tracing import get_response_metrics
        response_metrics = get_response_metrics()
    except Exception as e:
        logger.debug(f"Response metrics unavailable: {e}")

    cache_metrics = {}
    try:
        from middleware.cache_metrics import get_cache_metrics
        cache_metrics = get_cache_metrics()
    except Exception as e:
        logger.debug(f"Cache metrics unavailable: {e}")

    active_connections = pool_stats.get("checked_out", 0)

    uptime_seconds = round(time.time() - _start_time)
    status = "healthy" if db_ok else "degraded"

    return {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": uptime_seconds,
        "database": {
            "connected": db_ok,
            "latency_ms": db_latency_ms,
            "active_connections": active_connections,
            "pool": pool_stats,
        },
        "process": process_stats,
        "response_time": response_metrics,
        "cache": cache_metrics,
        "version": "3.0.0",
    }


@router.get("/status")
async def system_status(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    db_ok = False
    table_count = 0
    total_users = 0
    total_schools = 0
    active_users_24h = 0

    try:
        db_ok, _ = await _pg_ping(db)
        if db_ok:
            table_count = await _pg_table_count(db)
            total_users = await gd_count(db.session, "users", {})
            total_schools = await gd_count(db.session, "schools", {})
            from datetime import timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            active_users_24h = await gd_count(db.session, "users", {"last_login": {"$gte": cutoff.isoformat()}})
    except Exception as e:
        logger.warning(f"System status query error: {e}")

    uptime_seconds = round(time.time() - _start_time)
    hours = uptime_seconds // 3600
    minutes = (uptime_seconds % 3600) // 60

    return {
        "status": "operational" if db_ok else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime": f"{hours}h {minutes}m",
        "uptime_seconds": uptime_seconds,
        "environment": os.environ.get("ENVIRONMENT", "development"),
        "python_version": platform.python_version(),
        "database": {
            "connected": db_ok,
            "name": "nassaq_postgres",
            "collections_count": table_count,
        },
        "stats": {
            "total_users": total_users,
            "total_schools": total_schools,
            "active_users_24h": active_users_24h,
        },
    }


@router.get("/deployment-safety")
async def deployment_safety_check(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    from config import config
    checklist = config.deployment_checklist()

    db_ok = False
    collection_counts = {}
    try:
        db_ok, _ = await _pg_ping(db)
        if db_ok:
            # B-05: replaced legacy MongoDB syntax (`db[coll].count_documents({})`)
            # which always raised silently because Repos has no __getitem__.
            from engines.sql_utils import gd_count
            for coll_name in ["users", "schools", "teachers", "students", "product_issues"]:
                try:
                    collection_counts[coll_name] = await gd_count(db.session, coll_name, {})
                except Exception as _ce:
                    logger.warning(f"deployment-safety count for {coll_name} failed: {_ce}")
                    collection_counts[coll_name] = None
    except (SQLAlchemyError, ConnectionError, OSError) as e:
        logger.error(f"Deployment safety check DB query failed: {e}")
    except Exception as e:
        logger.error(f"Deployment safety check unexpected error: {e}")

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": config.ENVIRONMENT,
        "database_name": "nassaq_postgres",
        "database_connected": db_ok,
        "seed_scripts_blocked": not config.seed_allowed(),
        "destructive_ops_blocked": not config.destructive_ops_allowed(),
        "pre_flight_checklist": checklist,
        "data_snapshot": collection_counts,
        "policy": {
            "rule": "Production data must NEVER be lost, overwritten, or replaced",
            "seed_blocked_in": ["production", "staging"],
            "safe_to_deploy": checklist.get("all_passed", False) and db_ok,
        }
    }


@router.get("/errors")
async def system_errors(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    try:
        session = db._get_session()
        if session:
            result = await session.execute(sa_text(
                "SELECT id, data->>'level' as level, data->>'message' as message, "
                "data->>'source' as source, data->>'timestamp' as timestamp "
                "FROM generic_documents WHERE collection='system_errors' "
                "ORDER BY created_at DESC LIMIT 50"
            ))
            rows = result.mappings().all()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"Error fetching system errors: {e}")
    return []


@router.get("/jobs")
async def system_jobs(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    return []


@router.get("/alerts")
async def system_alerts(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    alerts = []
    try:
        db_ok, latency = await _pg_ping(db)
        if not db_ok:
            alerts.append({
                "id": "db-health",
                "type": "critical",
                "message": "Database connection failed",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        elif latency > 500:
            alerts.append({
                "id": "db-slow",
                "type": "warning",
                "message": f"Database latency high: {latency}ms",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    except (SQLAlchemyError, ConnectionError, OSError) as e:
        logger.error(f"System alerts DB check failed: {e}")
        alerts.append({
            "id": "db-check-error",
            "type": "critical",
            "message": f"Failed to check database status: {e}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        logger.error(f"System alerts unexpected error: {e}")
        alerts.append({
            "id": "db-check-error",
            "type": "critical",
            "message": "Unexpected error checking database status",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    return alerts


@router.get("/metrics")
async def system_metrics(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    process_info = {}
    system_memory = {}
    disk_info = {}
    network_info = {}
    try:
        import psutil
        try:
            process = psutil.Process()
            mem = process.memory_info()
            process_info = {
                "memory_rss_mb": round(mem.rss / 1024 / 1024, 2),
                "memory_vms_mb": round(mem.vms / 1024 / 1024, 2),
                "cpu_percent": 0,
                "threads": process.num_threads(),
            }
        except Exception:
            process_info = {"cpu_percent": 0, "memory_rss_mb": 0, "memory_vms_mb": 0, "threads": 0}

        # Container-aware CPU (cgroup v2): falls back to host psutil only if cgroup unavailable
        cgroup_cpu = _container_cpu()
        if cgroup_cpu is not None:
            process_info["cpu_percent"] = cgroup_cpu["percent"]
            process_info["cpu_cores"] = cgroup_cpu["cores"]
        else:
            try:
                process_info["cpu_percent"] = psutil.cpu_percent(interval=None)
            except Exception:
                process_info["cpu_percent"] = 0

        # Container-aware memory (cgroup v2): falls back to host psutil only if cgroup unavailable
        cgroup_mem = _container_memory()
        if cgroup_mem is not None:
            system_memory = cgroup_mem
        else:
            try:
                vm = psutil.virtual_memory()
                system_memory = {
                    "total_mb": round(vm.total / 1024 / 1024, 1),
                    "available_mb": round(vm.available / 1024 / 1024, 1),
                    "used_mb": round(vm.used / 1024 / 1024, 1),
                    "percent": vm.percent,
                }
            except Exception:
                system_memory = {"percent": 0, "total_mb": 0, "available_mb": 0, "used_mb": 0}
        try:
            du = psutil.disk_usage("/")
            disk_info = {
                "total_gb": round(du.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(du.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(du.free / 1024 / 1024 / 1024, 2),
                "percent": du.percent,
            }
        except Exception:
            disk_info = {"percent": 0}
        try:
            net = psutil.net_io_counters()
            now_ts = time.time()
            elapsed = max(now_ts - _last_net_snapshot["ts"], 1) if _last_net_snapshot["ts"] > 0 else 0
            sent_rate = round((net.bytes_sent - _last_net_snapshot["bytes_sent"]) / 1024 / max(elapsed, 1), 1) if elapsed > 0 else 0
            recv_rate = round((net.bytes_recv - _last_net_snapshot["bytes_recv"]) / 1024 / max(elapsed, 1), 1) if elapsed > 0 else 0
            _last_net_snapshot["bytes_sent"] = net.bytes_sent
            _last_net_snapshot["bytes_recv"] = net.bytes_recv
            _last_net_snapshot["ts"] = now_ts
            network_info = {
                "bytes_sent_mb": round(net.bytes_sent / 1024 / 1024, 2),
                "bytes_recv_mb": round(net.bytes_recv / 1024 / 1024, 2),
                "sent_kbps": sent_rate,
                "recv_kbps": recv_rate,
                "packets_sent": net.packets_sent,
                "packets_recv": net.packets_recv,
            }
        except Exception:
            network_info = {"bytes_sent_mb": 0, "bytes_recv_mb": 0, "sent_kbps": 0, "recv_kbps": 0}
    except ImportError:
        process_info = {"error": "psutil not installed"}

    response_metrics = {}
    try:
        from middleware.request_tracing import get_response_metrics
        response_metrics = get_response_metrics()
    except Exception as e:
        logger.debug(f"Response metrics unavailable: {e}")

    cache_metrics = {}
    try:
        from middleware.cache_metrics import get_cache_metrics
        cache_metrics = get_cache_metrics()
    except Exception as e:
        logger.debug(f"Cache metrics unavailable: {e}")

    pool_stats = {}
    db_latency_ms = 0
    try:
        from db import get_sync_engine
        from middleware.query_monitor import get_pool_stats
        pool_stats = get_pool_stats(get_sync_engine())
    except Exception as e:
        logger.debug(f"Pool stats unavailable: {e}")
    try:
        _, db_latency_ms = await _pg_ping(db)
    except Exception:
        pass

    db_counts = {}
    active_users_24h = 0
    try:
        db_counts = {
            "users": await gd_count(db.session, "users", {}),
            "schools": await gd_count(db.session, "schools", {}),
            "teachers": await gd_count(db.session, "teachers", {}),
            "students": await gd_count(db.session, "students", {}),
            "classes": await gd_count(db.session, "classes", {}),
            "sessions": await gd_count(db.session, "teacher_sessions", {}),
            "audit_logs": await gd_count(db.session, "audit_logs", {}),
        }
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        active_users_24h = await gd_count(db.session, "users", {"last_login": {"$gte": cutoff.isoformat()}})
    except (SQLAlchemyError, ConnectionError, OSError) as e:
        logger.error(f"System metrics DB query failed: {e}")
        db_counts = {"error": "database unavailable"}
    except Exception as e:
        logger.error(f"System metrics unexpected error: {e}")
        db_counts = {"error": "database unavailable"}

    uptime_seconds = round(time.time() - _start_time)
    total_reqs = response_metrics.get("total_requests", 0)
    reqs_per_min = round(total_reqs / max(uptime_seconds / 60, 1), 1) if total_reqs else 0

    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cpu": process_info.get("cpu_percent", 0),
        "memory": system_memory.get("percent", 0),
        "disk": disk_info.get("percent", 0),
        "avg_response_ms": response_metrics.get("avg_response_ms", 0),
        "requests_per_min": reqs_per_min,
        "db_latency_ms": db_latency_ms,
    }
    _metrics_history.append(snapshot)

    return {
        "timestamp": snapshot["timestamp"],
        "uptime_seconds": uptime_seconds,
        "process": process_info,
        "system_memory": system_memory,
        "disk": disk_info,
        "network": network_info,
        "database_counts": db_counts,
        "active_users_24h": active_users_24h,
        "response_metrics": response_metrics,
        "cache_metrics": cache_metrics,
        "pool_stats": pool_stats,
        "db_latency_ms": db_latency_ms,
        "requests_per_min": reqs_per_min,
    }


@router.get("/metrics/history")
async def system_metrics_history(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    return list(_metrics_history)


@router.post("/restart-service")
async def restart_service(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    checks = {}
    try:
        db_ok, latency = await _pg_ping(db)
        checks["database"] = {"status": "healthy" if db_ok else "degraded", "latency_ms": latency}
    except Exception as e:
        checks["database"] = {"status": "error", "detail": str(e)}

    try:
        import psutil
        proc = psutil.Process()
        checks["process"] = {
            "status": "running",
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_rss_mb": round(proc.memory_info().rss / 1024 / 1024, 1),
            "threads": proc.num_threads(),
        }
    except Exception:
        checks["process"] = {"status": "running"}

    try:
        from middleware.request_tracing import get_response_metrics
        rm = get_response_metrics()
        checks["api"] = {"status": "healthy", "avg_response_ms": rm.get("avg_response_ms", 0)}
    except Exception:
        checks["api"] = {"status": "unknown"}

    all_healthy = all(c.get("status") in ("healthy", "running") for c in checks.values())
    try:
        await gd_insert(db.session, "audit_logs", {
            "action": "system_restart_service",
            "user_id": current_user.get("id"),
            "details": {"checks": checks, "result": "healthy" if all_healthy else "degraded"},
        })
    except Exception as e:
        logger.warning(f"Audit log for restart-service failed: {e}")

    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }


@router.post("/resync")
async def resync_integrations(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    results = {}
    try:
        db_ok, latency = await _pg_ping(db)
        results["database"] = {"connected": db_ok, "latency_ms": latency}
    except Exception:
        results["database"] = {"connected": False, "latency_ms": 0}

    try:
        pool_stats_data = {}
        from db import get_sync_engine
        from middleware.query_monitor import get_pool_stats
        pool_stats_data = get_pool_stats(get_sync_engine())
        results["connection_pool"] = {"status": "healthy", "checked_out": pool_stats_data.get("checked_out", 0)}
    except Exception:
        results["connection_pool"] = {"status": "unknown"}

    try:
        from middleware.cache_metrics import get_cache_metrics
        cm = get_cache_metrics()
        results["cache"] = {"status": "active", "hit_rate": cm.get("hit_rate_percent", 0)}
    except Exception:
        results["cache"] = {"status": "unknown"}

    try:
        await gd_insert(db.session, "audit_logs", {
            "action": "system_resync",
            "user_id": current_user.get("id"),
            "details": {"results": results},
        })
    except Exception as e:
        logger.warning(f"Audit log for resync failed: {e}")

    return {
        "status": "completed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }


@router.post("/escalate-alert")
async def escalate_alert(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    try:
        await gd_insert(db.session, "audit_logs", {
            "action": "alert_escalated",
            "user_id": current_user.get("id"),
            "details": {
                "escalated_by": current_user.get("email", "unknown"),
                "escalated_at": datetime.now(timezone.utc).isoformat(),
                "target": "tech_team",
            },
        })
    except Exception as e:
        logger.warning(f"Audit log for escalate-alert failed: {e}")

    return {
        "status": "escalated",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": "Alert escalated to tech team",
    }


@router.post("/ai-diagnosis")
async def ai_diagnosis(current_user: dict = Depends(require_roles([UserRole.PLATFORM_ADMIN]))):
    findings = []
    overall = "healthy"

    cpu_pct = 0
    mem_pct = 0
    disk_pct = 0
    try:
        import psutil
        cpu_pct = psutil.cpu_percent(interval=0.3)
        mem_pct = psutil.virtual_memory().percent
        try:
            disk_pct = psutil.disk_usage("/").percent
        except Exception:
            pass
    except ImportError:
        pass

    if cpu_pct > 80:
        findings.append({"category": "cpu", "status": "critical" if cpu_pct > 90 else "warning",
                         "message": f"CPU usage high: {cpu_pct}%", "value": cpu_pct})
        overall = "critical" if cpu_pct > 90 else "warning"
    else:
        findings.append({"category": "cpu", "status": "healthy", "message": f"CPU usage normal: {cpu_pct}%", "value": cpu_pct})

    if mem_pct > 85:
        findings.append({"category": "memory", "status": "critical" if mem_pct > 95 else "warning",
                         "message": f"Memory usage high: {mem_pct}%", "value": mem_pct})
        if overall != "critical":
            overall = "critical" if mem_pct > 95 else "warning"
    else:
        findings.append({"category": "memory", "status": "healthy", "message": f"Memory usage normal: {mem_pct}%", "value": mem_pct})

    if disk_pct > 90:
        findings.append({"category": "disk", "status": "critical" if disk_pct > 95 else "warning",
                         "message": f"Disk usage high: {disk_pct}%", "value": disk_pct})
        if overall != "critical":
            overall = "critical" if disk_pct > 95 else "warning"
    else:
        findings.append({"category": "disk", "status": "healthy", "message": f"Disk usage normal: {disk_pct}%", "value": disk_pct})

    db_latency = 0
    try:
        db_ok, db_latency = await _pg_ping(db)
        if not db_ok:
            findings.append({"category": "database", "status": "critical", "message": "Database connection failed", "value": 0})
            overall = "critical"
        elif db_latency > 100:
            findings.append({"category": "database", "status": "warning", "message": f"Database latency high: {db_latency}ms", "value": db_latency})
            if overall == "healthy":
                overall = "warning"
        else:
            findings.append({"category": "database", "status": "healthy", "message": f"Database latency normal: {db_latency}ms", "value": db_latency})
    except Exception:
        findings.append({"category": "database", "status": "critical", "message": "Database check failed", "value": 0})
        overall = "critical"

    try:
        from middleware.request_tracing import get_response_metrics
        rm = get_response_metrics()
        total_reqs = rm.get("total_requests", 0)
        total_errs = rm.get("total_errors", 0)
        error_rate = (total_errs / total_reqs * 100) if total_reqs > 0 else 0
        if error_rate > 5:
            findings.append({"category": "errors", "status": "warning", "message": f"Error rate elevated: {error_rate:.1f}%", "value": round(error_rate, 1)})
            if overall == "healthy":
                overall = "warning"
        else:
            findings.append({"category": "errors", "status": "healthy", "message": f"Error rate normal: {error_rate:.1f}%", "value": round(error_rate, 1)})

        avg_ms = rm.get("avg_response_ms", 0)
        if avg_ms > 1000:
            findings.append({"category": "response_time", "status": "warning", "message": f"Average response time slow: {avg_ms}ms", "value": avg_ms})
            if overall == "healthy":
                overall = "warning"
        else:
            findings.append({"category": "response_time", "status": "healthy", "message": f"Response time normal: {avg_ms}ms", "value": avg_ms})
    except Exception:
        findings.append({"category": "errors", "status": "unknown", "message": "Could not retrieve error metrics", "value": 0})

    try:
        from db import get_sync_engine
        from middleware.query_monitor import get_pool_stats
        ps = get_pool_stats(get_sync_engine())
        utilization = ps.get("checked_out", 0) / max(ps.get("pool_size", 1), 1) * 100
        if utilization > 80:
            findings.append({"category": "pool", "status": "warning", "message": f"Connection pool utilization high: {utilization:.0f}%", "value": round(utilization)})
            if overall == "healthy":
                overall = "warning"
        else:
            findings.append({"category": "pool", "status": "healthy", "message": f"Pool utilization normal: {utilization:.0f}%", "value": round(utilization)})
    except Exception:
        findings.append({"category": "pool", "status": "unknown", "message": "Pool stats unavailable", "value": 0})

    recommendations = []
    for f in findings:
        if f["status"] == "critical":
            recommendations.append(f"⚠️ {f['message']} — immediate attention required")
        elif f["status"] == "warning":
            recommendations.append(f"⚡ {f['message']} — monitor closely")

    if not recommendations:
        recommendations.append("All systems operating within normal parameters")

    return {
        "status": overall,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "findings": findings,
        "recommendations": recommendations,
    }
