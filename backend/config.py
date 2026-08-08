"""
NASSAQ Production Configuration
Centralized config from environment variables with validation.

DEPLOYMENT SAFETY POLICY (PERMANENT & NON-NEGOTIABLE):
- Production data must NEVER be lost, overwritten, or replaced
- Seed/demo data must NEVER be injected into production
- Destructive migrations are BLOCKED in production
- Environment separation is strictly enforced
"""
import os
from typing import Optional
from urllib.parse import urlparse


SEED_BLOCKED_ENVIRONMENTS = {"production", "staging"}

SAFE_MIGRATION_OPS = {"add_field", "add_collection", "add_index", "create_index"}
DESTRUCTIVE_MIGRATION_OPS = {"drop", "delete", "rename", "remove", "truncate", "replace"}

# ---------------------------------------------------------------------------
# Public app/base URL for recipient-facing links (email deep-links etc).
#
# Canonical variable: APP_URL. FRONTEND_URL is accepted as an equivalent
# alias (it is the name used in the ops handover). The Replit-managed
# domain variables are safe automatic fallbacks because they are always
# publicly reachable. A hardcoded localhost fallback is allowed ONLY in
# development, where no real recipients exist.
# ---------------------------------------------------------------------------

_PUBLIC_URL_ENV_ORDER = (
    "APP_URL",
    "FRONTEND_URL",
    "REPLIT_DEPLOYMENT_URL",
    "REPLIT_DOMAINS",
    "REPLIT_DEV_DOMAIN",
)

_DEV_ENVIRONMENTS = ("development", "dev", "")


class PublicUrlConfigError(RuntimeError):
    """Raised when the public app URL is missing or clearly non-public
    in an environment where real recipients receive email links."""


def is_dev_environment(environment: Optional[str] = None) -> bool:
    env = environment if environment is not None else os.environ.get("ENVIRONMENT", "development")
    return env in _DEV_ENVIRONMENTS


def _normalize_base_url(raw: str) -> str:
    value = (raw or "").strip()
    if value and "://" not in value:
        value = f"https://{value}"
    return value.rstrip("/")


def _non_public_reason(url: str) -> Optional[str]:
    """Return a human-readable reason when ``url`` cannot be used for
    recipient-facing links, or None when it looks publicly reachable."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return "the value cannot be parsed as a URL"
    if parsed.scheme not in ("http", "https"):
        return f"scheme '{parsed.scheme}' is not http/https"
    host = (parsed.hostname or "").lower()
    if not host:
        return "the value has no hostname"
    if host == "localhost" or host.endswith(".localhost"):
        return "it points at localhost"
    if host.startswith("127.") or host in ("::1", "0.0.0.0"):
        return "it points at a loopback/unspecified address"
    if host.endswith(".local"):
        return "it points at a .local (non-public) hostname"
    if "." not in host and ":" not in host:
        return "it points at a bare internal hostname (no domain)"
    if host.startswith("10.") or host.startswith("192.168."):
        return "it points at a private (RFC1918) address"
    if host.startswith("172."):
        parts = host.split(".")
        if len(parts) > 1 and parts[1].isdigit() and 16 <= int(parts[1]) <= 31:
            return "it points at a private (RFC1918) address"
    return None


def is_public_base_url(url: str) -> bool:
    return _non_public_reason(url) is None


def get_public_app_url(environment: Optional[str] = None) -> str:
    """Resolve the public base URL used to build every recipient-facing
    link (password reset, parent invitations, workspace lifecycle emails).

    Reads the environment at CALL time so configuration changes and test
    monkeypatching are honoured. In non-development environments a
    missing or non-public value raises :class:`PublicUrlConfigError`
    with a precise operator-facing message — silently emailing a broken
    localhost link is never acceptable.
    """
    source_var: Optional[str] = None
    candidate = ""
    for var in _PUBLIC_URL_ENV_ORDER:
        raw = os.environ.get(var, "")
        if var == "REPLIT_DOMAINS" and raw:
            raw = raw.split(",")[0]
        if raw and raw.strip():
            source_var = var
            candidate = _normalize_base_url(raw)
            break

    dev = is_dev_environment(environment)

    if not candidate:
        if dev:
            return "http://localhost:5000"
        raise PublicUrlConfigError(
            "Public app URL is not configured: set the APP_URL environment "
            "variable (or its alias FRONTEND_URL) to the publicly reachable "
            "site URL, e.g. https://nassaqapp.com. Refusing to build "
            "recipient-facing email links without it."
        )

    reason = _non_public_reason(candidate)
    if reason and not dev:
        raise PublicUrlConfigError(
            f"Public app URL from {source_var} is not usable for "
            f"recipient-facing email links: {reason} ({candidate}). Set "
            "APP_URL (or FRONTEND_URL) to the publicly reachable site URL, "
            "e.g. https://nassaqapp.com."
        )
    return candidate


class NassaqConfig:
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
    JWT_SECRET: str = os.environ.get("JWT_SECRET_KEY", "")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))

    ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "development")
    DEBUG: bool = os.environ.get("DEBUG", "false").lower() == "true"

    CORS_ORIGINS: list = os.environ.get("CORS_ORIGINS", "*").split(",")
    ALLOWED_HOSTS: list = os.environ.get("ALLOWED_HOSTS", "*").split(",")

    RATE_LIMIT_LOGIN: int = int(os.environ.get("RATE_LIMIT_LOGIN", "10"))
    RATE_LIMIT_WINDOW: int = int(os.environ.get("RATE_LIMIT_WINDOW", "60"))

    # Where rate-limit counters live. "shared" (default) keeps them in the
    # Postgres `rate_limit_counters` table so every worker/instance enforces
    # ONE budget; "memory" is the legacy per-process window and multiplies
    # every limit by the instance count — only for isolated local runs.
    RATE_LIMIT_STORE: str = os.environ.get("RATE_LIMIT_STORE", "shared").strip().lower()
    # Hard ceiling on the limiter's DB round-trip. Past this the request is
    # served by the in-process fallback rather than waiting: brute-force
    # protection must never become an availability risk on the auth path.
    # Measured cost against the real pool: p50 5 ms, p95 9 ms. Tests run on
    # a NullPool (db.py), so every check pays a fresh connect — hence the
    # wider budget there, otherwise the suite silently exercises the
    # degraded path instead of the shared one.
    RATE_LIMIT_DB_TIMEOUT_MS: int = int(os.environ.get(
        "RATE_LIMIT_DB_TIMEOUT_MS",
        "3000" if os.environ.get("TESTING") == "1" else "250",
    ))
    # Most pooled connections the limiter may hold at once, per process.
    # The request-scoped session (pg_session_middleware) is already checked
    # out when a handler-level limit runs, so limiter checks are nested
    # checkouts; this cap keeps a flood of *unique* keys (which the local
    # deny-cache cannot absorb) from draining the app pool. Waiters bail out
    # after RATE_LIMIT_DB_TIMEOUT_MS into the in-process fallback.
    RATE_LIMIT_MAX_INFLIGHT: int = max(1, int(os.environ.get("RATE_LIMIT_MAX_INFLIGHT", "8")))
    # Key prefix for the shared counters. Lets two deployments share one
    # database without sharing budgets (and gives tests an isolated space).
    RATE_LIMIT_NAMESPACE: str = os.environ.get("RATE_LIMIT_NAMESPACE", "rl1")

    # ---- CPU-bound offload (PDF / XLSX / archive rendering) --------------
    # This server is one asyncio process per instance, so any render that runs
    # inline on the event loop freezes EVERY other request for its whole
    # duration (measured: 1.5 s for a 200-row Arabic PDF, 3.4 s for 500 rows —
    # see scripts/evidence_event_loop_pdf.py). Renders therefore run on a
    # dedicated thread pool via services/cpu_offload.py.
    #
    # Workers are deliberately few: ReportLab is pure Python, so extra threads
    # do not render faster (the GIL serializes them) — they only add jitter to
    # the loop and to every concurrent report. Two workers keep the loop
    # responsive while a third heavy report waits its turn.
    CPU_OFFLOAD_MAX_WORKERS: int = max(1, int(os.environ.get("CPU_OFFLOAD_MAX_WORKERS", "2")))
    # Total jobs admitted (running + waiting). Beyond this a caller is told to
    # retry rather than joining an unbounded queue that would make everyone
    # wait minutes for a file they will have given up on.
    CPU_OFFLOAD_MAX_INFLIGHT: int = max(
        1, int(os.environ.get("CPU_OFFLOAD_MAX_INFLIGHT", "8"))
    )
    # How long a caller waits for a slot before getting the 503.
    CPU_OFFLOAD_ADMISSION_TIMEOUT_S: float = float(
        os.environ.get("CPU_OFFLOAD_ADMISSION_TIMEOUT_S", "20")
    )
    # Wall-clock budget for a single render. A thread cannot be killed, so this
    # frees the waiting request, not the worker — the admission cap is the real
    # protection against runaway jobs.
    CPU_OFFLOAD_TIMEOUT_S: float = float(os.environ.get("CPU_OFFLOAD_TIMEOUT_S", "90"))
    # Renders slower than this are logged at WARNING so growth is visible
    # before users start reporting it.
    CPU_OFFLOAD_SLOW_MS: int = int(os.environ.get("CPU_OFFLOAD_SLOW_MS", "5000"))

    # --- Timetable generation pool -------------------------------------
    # Smart timetable generation is a combinatorial search that runs for tens
    # of seconds (measured: 1.3 s for 12 classes, 6.2 s for 24, 27 s for 40 —
    # see scripts/evidence_event_loop_timetable.py). It gets its own pool so a
    # principal's 30-second schedule run can never occupy the render workers
    # and stall everyone's report downloads behind it.
    #
    # Two workers: the search is pure Python, so more threads do not solve
    # faster (the GIL serializes them); two lets a second principal start
    # without waiting for the first to finish.
    TIMETABLE_OFFLOAD_MAX_WORKERS: int = max(
        1, int(os.environ.get("TIMETABLE_OFFLOAD_MAX_WORKERS", "2"))
    )
    # Running + waiting generation jobs. Past this the caller is told to retry
    # instead of joining a queue whose tail would wait several minutes.
    TIMETABLE_OFFLOAD_MAX_INFLIGHT: int = max(
        1, int(os.environ.get("TIMETABLE_OFFLOAD_MAX_INFLIGHT", "4"))
    )
    # A generation job may legitimately queue behind another long one, so the
    # admission wait is longer than the render pool's.
    TIMETABLE_OFFLOAD_ADMISSION_TIMEOUT_S: float = float(
        os.environ.get("TIMETABLE_OFFLOAD_ADMISSION_TIMEOUT_S", "60")
    )
    # Hard cap for one generation phase. Generous on purpose: the run is now
    # off the loop, so a slow-but-succeeding search for a very large school
    # costs that principal time and nobody else's responsiveness — killing it
    # at 60 s would simply make the feature unusable for big schools.
    TIMETABLE_OFFLOAD_TIMEOUT_S: float = float(
        os.environ.get("TIMETABLE_OFFLOAD_TIMEOUT_S", "180")
    )
    # A queued job whose worker vanished (deploy, autoscale scale-down, crash)
    # would otherwise sit "generating" forever, lying to the principal and
    # blocking the one-run-per-school guard. Any non-terminal run older than
    # this is reaped as failed on the next poll. Comfortably above the phase
    # timeout plus admission wait so it never fires on a healthy long run.
    TIMETABLE_JOB_STALE_AFTER_S: float = float(
        os.environ.get("TIMETABLE_JOB_STALE_AFTER_S", "600")
    )

    LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO")

    VERSION: str = "3.0.0"
    APP_NAME: str = "NASSAQ - نَسَّق"

    @classmethod
    def is_production(cls) -> bool:
        return cls.ENVIRONMENT == "production"

    @classmethod
    def is_staging(cls) -> bool:
        return cls.ENVIRONMENT == "staging"

    @classmethod
    def is_development(cls) -> bool:
        return cls.ENVIRONMENT in ("development", "dev", "")

    @classmethod
    def seed_allowed(cls) -> bool:
        if cls.ENVIRONMENT in SEED_BLOCKED_ENVIRONMENTS:
            return False
        db_url = os.environ.get("DATABASE_URL", "")
        if db_url and ("helium" in db_url or "replit" in db_url.lower()):
            if cls.ENVIRONMENT not in ("development", "dev"):
                return False
        return True

    @classmethod
    def destructive_ops_allowed(cls) -> bool:
        return cls.is_development()

    @classmethod
    def validate(cls) -> list:
        issues = []
        if not cls.JWT_SECRET:
            if cls.is_production():
                raise ValueError("JWT_SECRET_KEY must be set in production environment")
            issues.append("JWT_SECRET not set")
        if cls.is_production() and cls.JWT_SECRET and len(cls.JWT_SECRET) < 32:
            raise ValueError("JWT_SECRET_KEY too short for production (min 32 chars)")
        if cls.is_production() and cls.CORS_ORIGINS == ["*"]:
            raise ValueError("CORS_ORIGINS must be explicitly set in production (wildcard '*' is not allowed)")
        if cls.is_production() and cls.DEBUG:
            issues.append("DEBUG should be false in production")
        if cls.is_production() and not cls.DATABASE_URL:
            raise ValueError("DATABASE_URL must be set in production environment")
        if not cls.is_development():
            # Recipient-facing email links must never point at localhost.
            # Fail the boot with an operator-facing message instead of
            # silently sending broken invitation / password-reset emails.
            try:
                get_public_app_url(environment=cls.ENVIRONMENT)
            except PublicUrlConfigError as e:
                raise ValueError(str(e))
        return issues

    @classmethod
    def deployment_checklist(cls) -> dict:
        checks = {
            "environment_set": cls.ENVIRONMENT != "",
            "environment_value": cls.ENVIRONMENT,
            "database_url_set": bool(cls.DATABASE_URL),
            "seed_blocked": not cls.seed_allowed() if cls.is_production() else "n/a",
            "destructive_ops_blocked": not cls.destructive_ops_allowed() if cls.is_production() else "n/a",
            "jwt_secret_set": bool(cls.JWT_SECRET),
            "cors_configured": cls.CORS_ORIGINS != ["*"] if cls.is_production() else True,
            "debug_off": not cls.DEBUG if cls.is_production() else True,
            "pg_configured": bool(cls.DATABASE_URL),
        }
        all_passed = all(
            v is True or v == "n/a" or (isinstance(v, str) and v)
            for k, v in checks.items()
        )
        checks["all_passed"] = all_passed
        return checks


config = NassaqConfig()
