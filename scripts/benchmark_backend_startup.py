#!/usr/bin/env python3
"""Fresh-process import gate; never starts the app lifespan or maintenance."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import platform
import re
import statistics
import subprocess
import sys
import time
from urllib.parse import urlsplit

BACKEND = Path(__file__).resolve().parents[1] / "backend"
MARKER = "STARTUP_BENCHMARK="
ERROR_MARKER = "STARTUP_BENCHMARK_ERROR="
FORBIDDEN = ("pandas", "reportlab", "arabic_reshaper", "bidi")
DUMMY_DATABASE_URL = "postgresql://benchmark:benchmark@127.0.0.1:1/benchmark"

def safe_probe_error(exc):
    """Identify failed imports without logging exception messages or locals."""
    detail = {"exception": type(exc).__name__}
    tb = exc.__traceback__
    while tb and tb.tb_next:
        tb = tb.tb_next
    if tb:
        detail["location"] = f"{Path(tb.tb_frame.f_code.co_filename).name}:{tb.tb_lineno}"
    if isinstance(exc, ModuleNotFoundError) and isinstance(exc.name, str):
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", exc.name):
            detail["missing_module"] = exc.name
    return detail


async def measure_schema_gate(db):
    from sqlalchemy.ext.asyncio import create_async_engine

    original_engine = db.engine
    gate_engine = create_async_engine(
        db._get_async_url(),
        connect_args={"server_settings": {
            "default_transaction_read_only": "on",
            "statement_timeout": "15000",
        }},
    )
    db.engine = gate_engine
    try:
        start = time.perf_counter()
        status = await db.init_pg_tables()
        return {
            "schema_gate_seconds": time.perf_counter() - start,
            "schema_ready": status.get("schema_ready") is True,
        }
    finally:
        db.engine = original_engine
        await gate_engine.dispose()


def child_environment():
    # Allowlist rather than copying deployment credentials/flags into the probe.
    env = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL", "TZ")
           if key in os.environ}
    env.update(
        ENVIRONMENT="development",
        PYTHON_DOTENV_DISABLED="1",
        BACKEND_STARTUP_CHILD="1",
        JWT_SECRET_KEY="startup-benchmark-not-a-real-secret",
        DATABASE_URL=DUMMY_DATABASE_URL,
    )
    return env


def probe(module, schema_gate=False):
    import importlib
    import socket

    sys.path.insert(0, str(BACKEND))
    # An eager connection is a regression, not permission to contact a service.
    def reject_network(*args, **kwargs):
        raise RuntimeError("Network access attempted during app import")

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    socket.socket.connect = reject_network
    socket.socket.connect_ex = reject_network
    started = time.perf_counter()
    imported = importlib.import_module(module)
    elapsed = time.perf_counter() - started
    forbidden = [name for name in FORBIDDEN if name in sys.modules]
    result = {
        "module": module,
        "import_seconds": elapsed,
        "forbidden_modules": forbidden,
        "route_count": len(imported.app.routes) if module == "server" else None,
        "schema_gate_seconds": None,
        "schema_ready": None,
    }
    if schema_gate:
        # Only this explicit, separate phase can connect. No lifespan, DDL,
        # sequence repair, seeds, or background jobs run here.
        socket.socket.connect = original_connect
        socket.socket.connect_ex = original_connect_ex
        import asyncio
        from src.core.database import db

        result.update(asyncio.run(measure_schema_gate(db)))
    print(MARKER + json.dumps(result))


def run_probe(module, timeout, schema_url=None):
    env = child_environment()
    command = [sys.executable, str(Path(__file__).resolve()), "--probe", module]
    if schema_url:
        env["DATABASE_URL"] = schema_url
        env["REPLIT_DEPLOYMENT"] = "1"  # Actual managed physical-schema gate.
        command.append("--schema-gate")
    started = time.perf_counter()
    try:
        completed = subprocess.run(command, cwd=BACKEND, env=env,
                                   capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"{module} probe exceeded {timeout}s") from None
    if completed.returncode:
        # Do not echo arbitrary app logs (especially schema connection errors).
        detail = ""
        for line in completed.stdout.splitlines():
            if line.startswith(ERROR_MARKER):
                try:
                    error = json.loads(line[len(ERROR_MARKER):])
                    fields = [error.get(key, "") for key in
                              ("exception", "location", "missing_module")]
                    # Accept only identifier/location tokens, never arbitrary logs.
                    fields = [value for value in fields if isinstance(value, str)
                              and re.fullmatch(r"[A-Za-z0-9_.:-]{1,200}", value)]
                    detail = ": " + " / ".join(fields) if fields else ""
                except (ValueError, AttributeError):
                    pass
        raise RuntimeError(f"{module} probe exited with status {completed.returncode}{detail}")
    lines = [line[len(MARKER):] for line in completed.stdout.splitlines()
             if line.startswith(MARKER)]
    if len(lines) != 1:
        raise RuntimeError(f"{module} probe did not return one benchmark result")
    result = json.loads(lines[0])
    result["process_seconds"] = time.perf_counter() - started
    return result


def failures_for(result, budget):
    failures = []
    if result["import_seconds"] > budget:
        failures.append(f"import {result['import_seconds']:.3f}s exceeds {budget:.3f}s")
    if result["forbidden_modules"]:
        failures.append("eager export imports: " + ", ".join(result["forbidden_modules"]))
    if result.get("schema_ready") is False:
        failures.append("read-only schema gate reports not ready")
    return failures


def positive_seconds(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a finite positive number")
    return number


def validate_schema_target(env):
    if (env.get("REPLIT_DEPLOYMENT") or "").strip().lower() not in ("", "0", "false", "no", "off"):
        raise ValueError("Schema benchmarks cannot run inside a managed deployment")
    url = env.get("BENCHMARK_DATABASE_URL")
    if not url:
        raise ValueError("--schema-gate requires explicit non-production BENCHMARK_DATABASE_URL")

    def identity(value):
        parsed = urlsplit(value)
        return (parsed.hostname, parsed.port or 5432, parsed.path)

    try:
        target = identity(url)
        if not target[0] or not target[2]:
            raise ValueError()
        if env.get("DATABASE_URL") and target == identity(env["DATABASE_URL"]):
            raise ValueError()
    except ValueError:
        raise ValueError("Benchmark target must be valid and separate from the app database") from None
    return url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--max-dependencies-seconds", type=positive_seconds, default=5)
    parser.add_argument("--max-server-seconds", type=positive_seconds, default=15)
    parser.add_argument("--timeout", type=positive_seconds, default=60)
    parser.add_argument("--schema-gate", action="store_true",
                        help="Use BENCHMARK_DATABASE_URL, a non-production DB, read-only")
    parser.add_argument("--probe", choices=("server", "dependencies"),
                        help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.probe:
        if (os.environ.get("BACKEND_STARTUP_CHILD") != "1"
                or os.environ.get("PYTHON_DOTENV_DISABLED") != "1"):
            parser.error("--probe is internal; run the benchmark without --probe")
        if not args.schema_gate and os.environ.get("DATABASE_URL") != DUMMY_DATABASE_URL:
            parser.error("Import probes require the isolated dummy database")
        try:
            probe(args.probe, args.schema_gate)
        except (Exception, SystemExit) as exc:
            print(ERROR_MARKER + json.dumps(safe_probe_error(exc)), flush=True)
            return 1
        return 0
    if args.samples < 1:
        parser.error("--samples must be positive")
    schema_url = None
    if args.schema_gate:
        try:
            schema_url = validate_schema_target(os.environ)
        except ValueError as exc:
            parser.error(str(exc))
    report = {
        "environment": {
            "python": sys.version.split()[0], "executable": sys.executable,
            "platform": platform.platform(), "machine": platform.machine(),
            "cpu_count": os.cpu_count(), "load_average": os.getloadavg(),
            "filesystem_cache": "uncontrolled; may be warm",
            "bytecode": "existing caches allowed; no purge or prewarming",
            "scope": "fresh interpreter imports, NOT deployed cold start or time-to-ready",
            "schema": "separate read-only non-production physical gate" if schema_url else "not run; no database access",
        },
        "budgets_seconds": {"dependencies": args.max_dependencies_seconds,
                            "server": args.max_server_seconds},
        "samples": [], "summary": {}, "failures": [],
    }
    for module, budget in report["budgets_seconds"].items():
        results = []
        for _ in range(args.samples):
            try:
                result = run_probe(module, args.timeout,
                                   schema_url if module == "server" else None)
            except RuntimeError as exc:
                report["failures"].append(str(exc))
                break
            results.append(result)
            report["samples"].append(result)
            report["failures"].extend(f"{module}: {failure}"
                                      for failure in failures_for(result, budget))
        if results:
            report["summary"][module] = {
                "median_import_seconds": statistics.median(r["import_seconds"] for r in results),
                "max_import_seconds": max(r["import_seconds"] for r in results),
            }
    print(json.dumps(report, indent=2))
    return int(bool(report["failures"]))


if __name__ == "__main__":
    sys.exit(main())