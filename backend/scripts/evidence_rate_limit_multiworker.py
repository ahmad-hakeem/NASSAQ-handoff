"""Phase-1 evidence for the distributed-rate-limit audit.

Run:  cd backend && ENVIRONMENT=development python3 scripts/evidence_rate_limit_multiworker.py

Demonstrates two things with measurements, not assertions:

1. The bypass. Two independent ``RateLimitStore`` instances model two
   uvicorn processes (autoscale runs one process per machine, N machines).
   A single attacker IP spread across them gets N x the intended budget.

2. The cost of the fix. Latency of the atomic Postgres upsert that a
   shared store would issue per throttled request, so we know whether a
   DB round-trip on the auth hot path is affordable.
"""
import asyncio
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server  # noqa: F401  (must import first: circular-import guard)

from middleware.rate_limiter import RateLimitStore  # noqa: E402


async def demo_bypass(workers: int, limit: int = 10, window: int = 60) -> int:
    stores = [RateLimitStore() for _ in range(workers)]
    allowed = 0
    attempt = 0
    # Round-robin, exactly how a load balancer spreads one IP's requests.
    while attempt < limit * workers + workers:
        store = stores[attempt % workers]
        limited, _remaining, _retry = await store.is_rate_limited(
            "203.0.113.7:/api/auth/login", limit, window
        )
        if not limited:
            allowed += 1
        attempt += 1
    return allowed


async def measure_upsert_latency(samples: int = 40) -> None:
    from datetime import datetime, timezone, timedelta

    from sqlalchemy import text

    from db import async_session_factory

    sql = text(
        """
        INSERT INTO public_hakim_rate_counters (key, count, expires_at)
        VALUES (:key, 1, :expires_at)
        ON CONFLICT (key) DO UPDATE
          SET count = public_hakim_rate_counters.count + 1
        RETURNING count
        """
    )
    expires = datetime.now(timezone.utc) + timedelta(minutes=5)
    timings = []
    async with async_session_factory() as session:
        for i in range(samples):
            t0 = time.perf_counter()
            await session.execute(sql, {"key": f"probe:latency:{i % 4}", "expires_at": expires})
            await session.commit()
            timings.append((time.perf_counter() - t0) * 1000)
        await session.execute(
            text("DELETE FROM public_hakim_rate_counters WHERE key LIKE 'probe:latency:%'")
        )
        await session.commit()
    timings.sort()
    print(f"  upsert+commit p50 = {statistics.median(timings):.2f} ms")
    print(f"  upsert+commit p95 = {timings[int(len(timings) * 0.95)]:.2f} ms")
    print(f"  upsert+commit max = {timings[-1]:.2f} ms")


async def main() -> None:
    print("== effective login budget for ONE attacker IP, limit 10 / 60 s ==")
    for workers in (1, 2, 4, 8):
        allowed = await demo_bypass(workers)
        print(f"  {workers} process(es): {allowed} attempts allowed  (intended 10)")

    print("\n== shared-store round-trip cost (Postgres upsert) ==")
    await measure_upsert_latency()


if __name__ == "__main__":
    asyncio.run(main())
