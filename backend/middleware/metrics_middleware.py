"""
NASSAQ — Prometheus API Metrics Middleware & Endpoint Handler
Tracks API Request counts, HTTP Status Codes, Error rates, and Latency histograms.
"""
import time
from fastapi import Request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

API_REQUESTS_TOTAL = Counter(
    "nassaq_api_requests_total",
    "Total NASSAQ API Requests counter",
    ["method", "path_group", "status_code", "status_class"]
)

API_REQUEST_DURATION = Histogram(
    "nassaq_api_request_duration_seconds",
    "NASSAQ API Request duration in seconds",
    ["method", "path_group"]
)

def get_path_group(path: str) -> str:
    """Group API paths to prevent high cardinality metric labels."""
    parts = [p for p in path.split("/") if p]
    if not parts:
        return "/"
    if parts[0] == "api":
        if len(parts) > 1 and parts[1] == "v1":
            return "/api/v1/" + (parts[2] if len(parts) > 2 else "")
        return "/api/" + parts[1]
    return "/" + parts[0]

async def prometheus_metrics_middleware(request: Request, call_next):
    path = request.url.path
    if path in ("/metrics", "/health", "/readiness", "/liveness") or path.startswith("/static/"):
        return await call_next(request)

    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    status_code = str(response.status_code)
    status_class = f"{response.status_code // 100}xx"
    path_group = get_path_group(path)

    API_REQUESTS_TOTAL.labels(
        method=request.method,
        path_group=path_group,
        status_code=status_code,
        status_class=status_class
    ).inc()

    API_REQUEST_DURATION.labels(
        method=request.method,
        path_group=path_group
    ).observe(duration)

    return response

async def metrics_endpoint(request: Request):
    """Serve Prometheus metrics endpoint at /metrics."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
