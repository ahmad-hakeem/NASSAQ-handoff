"""
External audit sink (audit M-4).

Mirrors security-critical audit events to an append-only sink that lives
*outside* the application's primary database. Goal: a tamper-evident
trail an attacker who pivots into the app DB cannot quietly rewrite.

Configuration (env-driven, all optional — the sink is best-effort and
NEVER blocks request handling):

  AUDIT_SINK_BACKEND      "file" (default) | "s3" | "noop"
  AUDIT_SINK_PATH         filesystem path for the "file" backend.
                           Defaults to "/tmp/nassaq_audit.log".
                           Should be on an append-only / object-locked
                           volume in production.
  AUDIT_SINK_S3_BUCKET    bucket name (only used when backend == "s3")
  AUDIT_SINK_S3_PREFIX    key prefix (default "audit/")
  AUDIT_SINK_QUEUE_MAX    bounded queue size (default 1000). On overflow
                           events are DROPPED and a warning is logged
                           (drop-with-alert policy).

Design notes:

  * Events are enqueued from the request path via a non-blocking
    `put_nowait`. Slow sinks never stall the API.
  * A single background worker drains the queue and writes events
    serially in their arrival order (best-effort), so file/S3 writes
    don't fan out.
  * The S3 backend is loaded lazily via `boto3` only when configured —
    so the Python dep is not required for deployments using the file
    backend.
  * Event payloads MUST NOT contain raw passwords, tokens, reset
    material, JWTs, refresh tokens, or anything else listed in
    `_REDACT_KEYS`. The emit helper strips them defensively.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Mapping, MutableMapping, Optional

logger = logging.getLogger("nassaq.audit_sink")

_REDACT_KEYS = frozenset({
    "password", "passwd", "pwd",
    "token", "access_token", "refresh_token", "id_token", "reset_token",
    "secret", "api_key", "apikey", "authorization",
    "session_id", "session", "otp",
})


def _redact(value: Any, depth: int = 0) -> Any:
    if depth > 6:
        return "***DEPTH***"
    if isinstance(value, Mapping):
        out: MutableMapping[str, Any] = {}
        for k, v in value.items():
            if isinstance(k, str) and k.lower() in _REDACT_KEYS:
                out[k] = "***REDACTED***"
            else:
                out[k] = _redact(v, depth + 1)
        return out
    if isinstance(value, list):
        return [_redact(x, depth + 1) for x in value]
    return value


class _NullBackend:
    name = "noop"

    async def write(self, payload: str) -> None:  # noqa: D401
        return


class _FileBackend:
    name = "file"

    def __init__(self, path: str) -> None:
        self.path = path
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        except OSError as e:
            logger.warning("Could not ensure audit sink dir for %r: %s", self.path, e)

    async def write(self, payload: str) -> None:
        # Append + fsync to maximise the chance of durability if the
        # process is killed mid-write. Loop in the default executor so
        # the asyncio loop isn't blocked on disk.
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._write_sync, payload)

    def _write_sync(self, payload: str) -> None:
        try:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(payload)
                fh.write("\n")
                fh.flush()
                try:
                    os.fsync(fh.fileno())
                except OSError:
                    pass
        except OSError as e:
            logger.warning("Audit sink file write failed (%s): %s", self.path, e)


class _S3Backend:
    name = "s3"

    def __init__(self, bucket: str, prefix: str) -> None:
        self.bucket = bucket
        self.prefix = prefix.rstrip("/") + "/"
        try:
            import boto3  # type: ignore
        except ImportError:
            logger.warning("AUDIT_SINK_BACKEND=s3 but boto3 not installed; falling back to noop")
            self._client = None
            return
        self._client = boto3.client("s3")

    async def write(self, payload: str) -> None:
        if self._client is None:
            return
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._put_sync, payload)

    def _put_sync(self, payload: str) -> None:
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y/%m/%d/%H%M%S%f")
        key = f"{self.prefix}{ts}.json"
        try:
            self._client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=payload.encode("utf-8"),
                ContentType="application/json",
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Audit sink S3 put failed (s3://%s/%s): %s", self.bucket, key, e)


def _build_backend():
    name = (os.environ.get("AUDIT_SINK_BACKEND") or "file").strip().lower()
    if name == "noop":
        return _NullBackend()
    if name == "s3":
        bucket = os.environ.get("AUDIT_SINK_S3_BUCKET", "").strip()
        prefix = os.environ.get("AUDIT_SINK_S3_PREFIX", "audit/").strip()
        if not bucket:
            logger.warning("AUDIT_SINK_BACKEND=s3 but AUDIT_SINK_S3_BUCKET unset — using noop")
            return _NullBackend()
        return _S3Backend(bucket, prefix)
    path = os.environ.get("AUDIT_SINK_PATH", "/tmp/nassaq_audit.log")
    return _FileBackend(path)


class AuditSink:
    def __init__(self) -> None:
        self._queue: Optional[asyncio.Queue[str]] = None
        self._worker: Optional[asyncio.Task] = None
        self._backend = _build_backend()
        self._max = int(os.environ.get("AUDIT_SINK_QUEUE_MAX", "1000"))
        self._dropped = 0

    def _ensure_started(self) -> bool:
        if self._queue is not None:
            return True
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return False
        self._queue = asyncio.Queue(maxsize=self._max)
        self._worker = loop.create_task(self._run(), name="audit-sink-worker")
        logger.info(
            "AuditSink started (backend=%s, max_queue=%d)", self._backend.name, self._max
        )
        return True

    async def _run(self) -> None:
        assert self._queue is not None
        while True:
            try:
                payload = await self._queue.get()
            except asyncio.CancelledError:
                return
            try:
                await self._backend.write(payload)
            except Exception as e:  # noqa: BLE001
                logger.warning("Audit sink worker write failed: %s", e)
            finally:
                self._queue.task_done()

    def emit(self, event: Mapping[str, Any]) -> None:
        """Non-blocking enqueue. Drops the event (with a warning) if the
        queue is full or the loop isn't running yet."""
        if not self._ensure_started():
            return
        assert self._queue is not None
        safe = _redact(dict(event))
        safe.setdefault("emitted_at", datetime.now(timezone.utc).isoformat())
        try:
            payload = json.dumps(safe, default=str, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            logger.warning("Audit sink: refused to serialise event: %s", e)
            return
        try:
            self._queue.put_nowait(payload)
        except asyncio.QueueFull:
            self._dropped += 1
            if self._dropped <= 5 or self._dropped % 100 == 0:
                logger.warning(
                    "Audit sink queue full (max=%d); dropped %d events so far",
                    self._max, self._dropped,
                )

    @property
    def dropped(self) -> int:
        return self._dropped

    @property
    def backend_name(self) -> str:
        return self._backend.name

    async def drain(self, timeout: float = 5.0) -> int:
        """Best-effort flush of any in-flight events on shutdown.

        Wired into the FastAPI shutdown event so events queued in the
        last few hundred milliseconds before SIGTERM aren't silently
        lost. Returns the number of events still pending if the timeout
        was hit.
        """
        if self._queue is None:
            return 0
        try:
            await asyncio.wait_for(self._queue.join(), timeout=timeout)
            return 0
        except asyncio.TimeoutError:
            return self._queue.qsize()


audit_sink = AuditSink()


def emit_audit(event: Mapping[str, Any]) -> None:
    """Module-level helper used by route handlers."""
    audit_sink.emit(event)


__all__ = ["AuditSink", "audit_sink", "emit_audit"]
