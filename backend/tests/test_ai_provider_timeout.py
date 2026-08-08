"""AI provider calls must be bounded, non-blocking and observable.

Root cause these tests lock down (audited 2026-07-30):

1. Every OpenAI client was built with ``OpenAI(api_key=..., base_url=...)`` and
   no ``timeout``/``max_retries``. The SDK default is
   ``Timeout(connect=5, read=600, write=600, pool=600)`` with ``max_retries=2``
   — i.e. a hung provider could hold a single call for ~30 minutes.

2. The *synchronous* SDK was called directly inside ``async def`` handlers, so
   a slow provider blocked the whole event loop of that worker: even endpoints
   that never touch AI stalled behind it. That is the cascading failure.

The tests below fail against that old behaviour and pass once AI calls go
through ``services.ai_client``.
"""
import ast
import asyncio
import os
import time

import pytest

os.environ.setdefault("ENVIRONMENT", "development")

from services.ai_client import (  # noqa: E402
    AIProviderError,
    AIProviderTimeout,
    PURPOSE_BACKGROUND,
    PURPOSE_INTERACTIVE,
    ai_chat_completion,
    build_openai_client,
    get_ai_metrics,
    resolve_timeout,
)

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --------------------------------------------------------------------------
# Test doubles
# --------------------------------------------------------------------------
class _HungCompletions:
    """Stands in for a provider that accepts the request and never answers."""

    def __init__(self, delay: float):
        self.delay = delay
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        time.sleep(self.delay)  # blocking, exactly like the real sync SDK
        return "never-reached"


class _FakeClient:
    def __init__(self, delay: float = 30.0):
        self.chat = type("chat", (), {"completions": _HungCompletions(delay)})()

    @property
    def completions(self):
        return self.chat.completions


class _FailingCompletions:
    def __init__(self, exc):
        self.exc = exc

    def create(self, **kwargs):
        raise self.exc


class _FailingClient:
    def __init__(self, exc):
        self.chat = type("chat", (), {"completions": _FailingCompletions(exc)})()


# --------------------------------------------------------------------------
# 1. Clients are constructed with an explicit, bounded timeout
# --------------------------------------------------------------------------
def test_client_is_built_with_explicit_bounded_timeout(monkeypatch):
    monkeypatch.setenv("AI_INTEGRATIONS_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AI_INTEGRATIONS_OPENAI_BASE_URL", "https://example.invalid/v1")

    client = build_openai_client(purpose=PURPOSE_INTERACTIVE)
    assert client is not None

    # httpx.Timeout — every phase must be bounded (no None anywhere).
    timeout = client.timeout
    assert timeout is not None, "client must not fall back to the SDK default"
    for phase in ("connect", "read", "write", "pool"):
        value = getattr(timeout, phase, None)
        assert value is not None, f"{phase} timeout must be bounded"
        assert 0 < value <= 600, f"{phase} timeout out of range: {value}"

    # Retries multiply the worst case; keep them bounded and small.
    assert client.max_retries <= 2


def test_missing_api_key_yields_no_client(monkeypatch):
    monkeypatch.delenv("AI_INTEGRATIONS_OPENAI_API_KEY", raising=False)
    assert build_openai_client(purpose=PURPOSE_INTERACTIVE) is None


def test_timeouts_are_configurable_per_purpose(monkeypatch):
    monkeypatch.setenv("AI_REQUEST_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("AI_BACKGROUND_TIMEOUT_SECONDS", "48")
    assert resolve_timeout(PURPOSE_INTERACTIVE) == pytest.approx(12.0)
    assert resolve_timeout(PURPOSE_BACKGROUND) == pytest.approx(48.0)
    # An explicit per-call override always wins.
    assert resolve_timeout(PURPOSE_INTERACTIVE, override=3.5) == pytest.approx(3.5)


# --------------------------------------------------------------------------
# 2. A hung provider fails fast AND leaves the event loop free
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_hung_provider_times_out_and_never_blocks_the_event_loop():
    client = _FakeClient(delay=30.0)
    ticks = 0
    stop = False

    async def heartbeat():
        """Stands in for every other request served by this worker."""
        nonlocal ticks
        while not stop:
            await asyncio.sleep(0.02)
            ticks += 1

    hb = asyncio.create_task(heartbeat())
    started = time.perf_counter()
    with pytest.raises(AIProviderTimeout) as excinfo:
        await ai_chat_completion(
            client,
            purpose=PURPOSE_INTERACTIVE,
            timeout=0.5,
            model="gpt-5-mini",
            messages=[{"role": "user", "content": "hi"}],
        )
    elapsed = time.perf_counter() - started
    stop = True
    hb.cancel()

    # Fails fast: bounded by the timeout, not by the provider.
    assert elapsed < 5.0, f"call was not bounded (took {elapsed:.1f}s)"
    # The rest of the platform kept running while the AI call was pending.
    assert ticks >= 5, f"event loop was blocked during the AI call (ticks={ticks})"
    # Structured, mappable error.
    err = excinfo.value
    assert err.code == "ai_provider_timeout"
    assert err.provider == "openai"
    assert err.endpoint == "chat.completions"
    assert err.elapsed_ms >= 0


@pytest.mark.asyncio
async def test_provider_error_is_wrapped_not_leaked():
    client = _FailingClient(RuntimeError("connection reset by peer"))
    with pytest.raises(AIProviderError) as excinfo:
        await ai_chat_completion(
            client,
            purpose=PURPOSE_INTERACTIVE,
            timeout=5,
            model="gpt-5-mini",
            messages=[{"role": "user", "content": "hi"}],
        )
    assert excinfo.value.code == "ai_provider_error"
    assert not isinstance(excinfo.value, AIProviderTimeout)


# --------------------------------------------------------------------------
# 3. Timeouts are observable
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_timeout_is_counted_in_metrics():
    before = get_ai_metrics()
    before_timeouts = before["totals"]["timeouts"]

    client = _FakeClient(delay=5.0)
    with pytest.raises(AIProviderTimeout):
        await ai_chat_completion(
            client,
            purpose=PURPOSE_INTERACTIVE,
            timeout=0.2,
            model="gpt-5-mini",
            messages=[{"role": "user", "content": "hi"}],
        )

    after = get_ai_metrics()
    assert after["totals"]["timeouts"] == before_timeouts + 1
    assert after["totals"]["calls"] >= before["totals"]["calls"] + 1
    bucket = after["by_endpoint"].get("openai:chat.completions")
    assert bucket is not None
    assert bucket["timeouts"] >= 1
    assert bucket["latency_ms_p95"] >= 0


# --------------------------------------------------------------------------
# 4. The central Hakim wrapper degrades gracefully instead of hanging
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_hakim_generate_degrades_gracefully_when_provider_hangs(monkeypatch):
    import services.hakim_llm_service as hakim

    monkeypatch.setenv("AI_REQUEST_TIMEOUT_SECONDS", "1")
    monkeypatch.setattr(hakim, "_get_client", lambda: _FakeClient(delay=30.0))

    started = time.perf_counter()
    result = await hakim.hakim_generate(
        "improve", "evidence_description",
        text="نص تجريبي للاختبار يصف شاهد ملف الإنجاز بشكل مختصر", language="ar",
    )
    elapsed = time.perf_counter() - started

    assert elapsed < 8.0, f"Hakim did not fail fast (took {elapsed:.1f}s)"
    assert result["success"] is False
    # Distinct from a generic LLM_ERROR so dashboards can tell them apart.
    assert result.get("reason") == "LLM_TIMEOUT"
    # The caller still gets usable text back (the original input), never None.
    assert result.get("text")


# --------------------------------------------------------------------------
# 4b. A hung provider must not starve the rest of the app's worker threads
# --------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_hung_calls_do_not_consume_the_default_executor(monkeypatch):
    """AI calls run in their own bounded pool.

    ``asyncio.to_thread`` uses the loop's *default* executor, shared with all
    other offloaded work. If AI calls lived there, threads stuck on a hung
    provider would eventually starve unrelated blocking work. Saturate the AI
    pool and prove ordinary ``to_thread`` work still runs immediately.
    """
    from services import ai_client

    monkeypatch.setenv("AI_REQUEST_TIMEOUT_SECONDS", "1")
    monkeypatch.setenv("AI_MAX_CONCURRENT_CALLS", "2")
    monkeypatch.setattr(ai_client, "_ai_executor", None)  # rebuild with the cap

    clients = [_FakeClient(delay=20.0) for _ in range(4)]
    calls = [
        asyncio.create_task(
            ai_chat_completion(c, purpose=PURPOSE_INTERACTIVE, model="gpt-5-mini",
                               messages=[{"role": "user", "content": "hi"}])
        )
        for c in clients
    ]
    await asyncio.sleep(0.3)  # let the pool fill up

    started = time.perf_counter()
    assert await asyncio.to_thread(lambda: "unrelated work") == "unrelated work"
    assert time.perf_counter() - started < 2.0, (
        "unrelated blocking work queued behind hung AI calls — AI is sharing "
        "the default executor"
    )

    for task in calls:
        with pytest.raises(AIProviderError):
            await task

    monkeypatch.setattr(ai_client, "_ai_executor", None)


# --------------------------------------------------------------------------
# 5. Regression guard: no unbounded AI call site may be reintroduced
# --------------------------------------------------------------------------
def _ai_call_sites():
    """Every `*.chat/responses/embeddings.create(...)` call in backend code."""
    sites = []
    skip_dirs = {"tests", "__pycache__", "alembic", ".venv", "node_modules"}
    for dirpath, dirnames, filenames in os.walk(BACKEND_DIR):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            if os.path.relpath(path, BACKEND_DIR) == os.path.join("services", "ai_client.py"):
                continue  # the wrapper itself — it supplies the timeout
            try:
                tree = ast.parse(open(path, encoding="utf-8").read())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                src = ast.unparse(node.func)
                if not src.endswith(
                    ("chat.completions.create", "responses.create", "embeddings.create")
                ):
                    continue
                # ``timeout=None`` would silently restore the SDK default, so
                # an explicit None does not count as bounded.
                def _real_value(value) -> bool:
                    return not (isinstance(value, ast.Constant) and value.value is None)

                kw_timeout = any(
                    k.arg == "timeout" and _real_value(k.value) for k in node.keywords
                )
                with_options_timeout = "with_options(" in src and "timeout=" in src \
                    and "timeout=None" not in src
                sites.append(
                    {
                        "where": f"{os.path.relpath(path, BACKEND_DIR)}:{node.lineno}",
                        "src": src,
                        "explicit_timeout": kw_timeout or with_options_timeout,
                    }
                )
    return sites


def test_every_direct_sdk_call_site_passes_an_explicit_timeout():
    """Direct SDK use is allowed only with an explicit timeout.

    Anything else must go through ``ai_chat_completion`` (which supplies the
    timeout, offloads the blocking call and records metrics).
    """
    unbounded = [s["where"] for s in _ai_call_sites() if not s["explicit_timeout"]]
    assert not unbounded, (
        "AI call sites without an explicit timeout (use services.ai_client."
        f"ai_chat_completion instead): {unbounded}"
    )


def test_openai_clients_are_built_through_the_factory():
    """No module may construct a raw ``OpenAI(...)`` client of its own."""
    offenders = []
    skip_dirs = {"tests", "__pycache__", "alembic", ".venv", "node_modules"}
    for dirpath, dirnames, filenames in os.walk(BACKEND_DIR):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            rel = os.path.relpath(path, BACKEND_DIR)
            if rel == os.path.join("services", "ai_client.py"):
                continue  # the factory itself
            try:
                tree = ast.parse(open(path, encoding="utf-8").read())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and ast.unparse(node.func) in (
                    "OpenAI",
                    "openai.OpenAI",
                    "AsyncOpenAI",
                    "openai.AsyncOpenAI",
                ):
                    offenders.append(f"{rel}:{node.lineno}")
    assert not offenders, (
        "raw OpenAI clients bypass the bounded-timeout factory "
        f"(use services.ai_client.build_openai_client): {offenders}"
    )
