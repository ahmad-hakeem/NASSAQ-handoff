# Health checks for infrastructure tooling

Load balancers, container orchestrators and uptime monitors are not users. They
hold no account, no token and no session, and they expect a bare URL that
answers `200` when the instance may take traffic and `5xx` when it may not.

Two public endpoints serve them. Everything detailed stays behind admin auth.

## Endpoints

| Path | Auth | Checks | Healthy | Unhealthy | Use it for |
|---|---|---|---|---|---|
| `GET`/`HEAD` `/healthz` | none | process only | `200 {"status":"ok"}` | — (no body if the process is dead) | liveness probes, "is it up" monitors |
| `GET`/`HEAD` `/readyz` | none | database ping, time-bounded | `200 {"status":"ok"}` | `503 {"status":"unavailable","failed":["database"]}` | readiness probes, load-balancer target health |
| `GET /system/health` | none | database ping | `200 {"status":"healthy"\|"degraded", ...}` | always `200` | legacy status display in the admin UI |
| `GET /system/status` | platform admin | DB + counts + uptime + versions | `200` + diagnostics | `401`/`403` | human diagnostics |
| `GET /system/metrics` | platform admin | full metrics payload | `200` + metrics | `401`/`403` | the `/admin/monitoring` dashboard |

`/system/health` reports `degraded` **inside a 200 body**, so it cannot be used
as a probe: an LB reading only status codes would keep routing traffic to a
broken instance. It is kept for backwards compatibility with the admin UI.
Point every probe at `/healthz` or `/readyz`.

Both new endpoints are mounted at the root only — never under `/api` — and are
`include_in_schema=False`, so they stay out of the public OpenAPI surface.

## Semantics

**Liveness (`/healthz`)** answers one question: *is this process alive and
serving HTTP?* It deliberately touches no dependency. If it consulted the
database, a database blip would make every orchestrator kill every otherwise
healthy pod at once, turning a recoverable outage into a full restart storm.

**Readiness (`/readyz`)** answers a different one: *should this instance receive
traffic right now?* It pings Postgres on a connection of its own — not the
request-scoped session, which would report "ready" from a pool that can no
longer hand out connections — and fails closed: any error, or a ping slower
than the timeout, yields `503`.

The dependency check is bounded by `READINESS_TIMEOUT_S` (default `2.0`,
clamped to `0.25`–`10.0`). The probe must never become the bottleneck it exists
to detect. Keep it comfortably below the probe timeout configured in the
infrastructure below.

## Configuration

### Replit Autoscale (this deployment)

Replit's own promote-time healthcheck probes `GET /` and is not configurable.
Nothing to change. Add `/readyz` to any *external* uptime monitor you run
against the published domain.

### Kubernetes

```yaml
livenessProbe:
  httpGet: { path: /healthz, port: 8000 }
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 3          # ~30s of silence before a restart
readinessProbe:
  httpGet: { path: /readyz, port: 8000 }
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 3            # > READINESS_TIMEOUT_S so the app answers first
  failureThreshold: 2          # drain quickly, restart slowly
startupProbe:
  httpGet: { path: /healthz, port: 8000 }
  periodSeconds: 5
  failureThreshold: 30         # migrations/boot gate may take a while
```

Liveness on `/healthz` and readiness on `/readyz` is the important split: pods
get drained when the database is down, but not killed and rescheduled.

### NGINX

```nginx
location = /readyz { proxy_pass http://app_upstream; access_log off; }

upstream app_upstream {
    server app-1:8000 max_fails=2 fail_timeout=10s;
    server app-2:8000 max_fails=2 fail_timeout=10s;
    # NGINX Plus only:
    # health_check uri=/readyz interval=5s fails=2 passes=2;
}
```

### AWS ALB / ECS target group

```
Health check path:      /readyz
Healthy threshold:      2
Unhealthy threshold:    2
Timeout:                5 seconds
Interval:               10 seconds
Success codes:          200
```

ECS container health check: `CMD-SHELL curl -f http://localhost:8000/healthz || exit 1`.

### Uptime monitors

Probe `https://<domain>/readyz`, expect `200` and the body substring `"ok"`,
interval 60 s, alert after 2 consecutive failures. Use `HEAD` if the monitor
supports it — both verbs are accepted.

## Security

The public bodies are fixed literals: `{"status":"ok"}` and
`{"status":"unavailable","failed":["database"]}`. No version, environment,
hostname, config, record counts, timings, connection strings or exception text
— a failing probe names the dependency *class* only, which is what an operator
reading probe logs needs and is useless to anyone else. Both endpoints are
read-only; only `GET`/`HEAD` are routed, so no write verb exists on them. They
are also `no-store`, so a CDN or proxy can never serve a stale "ok" for a
dead instance.

Tests: `backend/tests/test_health_probes.py` covers the public contract, the
timeout, the no-leak guarantee, and a regression guard that the admin
diagnostics routes stay gated.
