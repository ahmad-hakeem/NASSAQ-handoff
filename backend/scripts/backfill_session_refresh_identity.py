"""
Task #376 — Force re-login for user_sessions rows minted before
Task #374's migration (revision ``c9d0e1f2a3b4``).

Why this exists
---------------
Task #374 added two columns to ``user_sessions``:

  * ``refresh_jti``         — the JWT id of the refresh token paired with
                              the row's access ``jti``.
  * ``refresh_family_id``   — the rotation lineage of that refresh token.

``settings_routes._revoke_session_refresh_chain`` uses both to kill the
refresh path when a user clicks "End session". Rows minted before the
migration carry NULL on both columns and silently degrade to access-JTI-
only revocation: the "ended" device's short-lived access token gets
rejected, but its still-valid refresh token mints a new pair and the
session reappears on the next request.

A true "populate refresh_jti / refresh_family_id from token history"
backfill is impossible — the server never persisted the refresh JTI
before Task #374; it only ever lived in the client cookie / response
body. So this script takes the alternative path the task description
allows: forcibly invalidate the legacy tokens so the next request
forces the user to sign in again.

Strategy
--------
Token validity in this codebase is enforced by JWT signature + the
``users.last_password_change`` cutoff (see ``dependencies.get_current_user``
and ``auth_routes_mod.refresh_access_token``): any token whose ``iat``
is older than ``last_password_change`` is rejected on both the access
and refresh paths. We piggy-back on that mechanism.

For every user that owns at least one *active* (revoked_at IS NULL,
not past expires_at) ``user_sessions`` row with NULL ``refresh_jti``,
we bump ``users.last_password_change`` to ``now``. That immediately
invalidates every access AND refresh token issued before ``now``
for that user — including the legacy ones we cannot revoke by JTI —
so the device is bounced through the login form, and its replacement
``user_sessions`` row is minted via ``_record_session_from_token``
with both new columns populated.

Side effect: a user with both legacy rows and post-fix rows has all
of their active sessions invalidated, not just the legacy ones. That
is the unavoidable cost of not knowing the legacy refresh JTI; it is
also exactly the "force them to sign in again" outcome the task
description asks for.

We then ALSO close the legacy rows themselves (``revoked_at = now``)
so the success-criterion query

    SELECT COUNT(*) FROM user_sessions
     WHERE revoked_at IS NULL AND refresh_jti IS NULL;

returns 0 immediately. Stale rows already past their access-token
expiry are flipped too — they were already invisible to
``/settings/sessions``, but it keeps the table tidy and makes the
invariant easy to assert in monitoring.

Run
---
    cd backend && python scripts/backfill_session_refresh_identity.py --dry-run
    cd backend && python scripts/backfill_session_refresh_identity.py
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


async def _connect():
    import asyncpg

    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(2)

    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    sslmode = params.get("sslmode", [None])[0]
    ssl_arg = "require" if sslmode and sslmode != "disable" else False
    return await asyncpg.connect(url, ssl=ssl_arg)


ACTIVE_LEGACY_SQL = """
    SELECT COUNT(*) FROM user_sessions
     WHERE revoked_at IS NULL
       AND refresh_jti IS NULL
       AND (expires_at IS NULL OR expires_at > NOW())
"""

STALE_LEGACY_SQL = """
    SELECT COUNT(*) FROM user_sessions
     WHERE revoked_at IS NULL
       AND refresh_jti IS NULL
       AND expires_at IS NOT NULL
       AND expires_at <= NOW()
"""

AFFECTED_USERS_SQL = """
    SELECT DISTINCT user_id
      FROM user_sessions
     WHERE revoked_at IS NULL
       AND refresh_jti IS NULL
       AND (expires_at IS NULL OR expires_at > NOW())
"""


async def run(dry_run: bool) -> int:
    conn = await _connect()
    try:
        active_legacy = await conn.fetchval(ACTIVE_LEGACY_SQL)
        stale_legacy = await conn.fetchval(STALE_LEGACY_SQL)
        affected_user_rows = await conn.fetch(AFFECTED_USERS_SQL)
        affected_user_ids = [r["user_id"] for r in affected_user_rows if r["user_id"]]

        print("=" * 60)
        print("Task #376 — legacy session forced re-login")
        print("=" * 60)
        print(f"Active legacy rows  (NULL refresh_jti, not expired):     {active_legacy}")
        print(f"Stale  legacy rows  (NULL refresh_jti, past expires_at): {stale_legacy}")
        print(f"Distinct users to be forced through re-login:            {len(affected_user_ids)}")

        if not active_legacy and not stale_legacy:
            print("\nNothing to do — no NULL-refresh_jti rows present.")
            return 0

        if dry_run:
            print("\n--dry-run set; no rows modified.")
            return 0

        now = datetime.now(timezone.utc)

        # 1. Bump users.last_password_change for every affected user.
        #    This is the canonical session-cutoff in this codebase
        #    (Task #342). Every access AND refresh token already in the
        #    user's possession has iat < now, so both will be rejected
        #    by get_current_user / refresh_access_token on the next
        #    request — bouncing the device through /auth/login.
        users_updated_tag = "UPDATE 0"
        if affected_user_ids:
            users_updated_tag = await conn.execute(
                """
                UPDATE users
                   SET last_password_change = $1
                 WHERE id = ANY($2::text[])
                """,
                now,
                affected_user_ids,
            )

        # 2. Close the legacy session rows themselves so the success-
        #    criterion query returns 0. This also stops them from
        #    cluttering /settings/sessions for the affected user.
        active_updated_tag = await conn.execute(
            """
            UPDATE user_sessions
               SET revoked_at = $1
             WHERE revoked_at IS NULL
               AND refresh_jti IS NULL
               AND (expires_at IS NULL OR expires_at > NOW())
            """,
            now,
        )
        stale_updated_tag = await conn.execute(
            """
            UPDATE user_sessions
               SET revoked_at = $1
             WHERE revoked_at IS NULL
               AND refresh_jti IS NULL
               AND expires_at IS NOT NULL
               AND expires_at <= NOW()
            """,
            now,
        )

        def _n(tag: str) -> str:
            try:
                return tag.split()[-1]
            except Exception:
                return tag

        print(f"\nBumped users.last_password_change on {_n(users_updated_tag)} user(s).")
        print(f"Closed {_n(active_updated_tag)} active legacy session row(s).")
        print(f"Closed {_n(stale_updated_tag)} stale  legacy session row(s).")

        # 3. Verify the success criterion + the cutoff coverage.
        remaining_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM user_sessions "
            "WHERE revoked_at IS NULL AND refresh_jti IS NULL"
        )
        users_without_cutoff = 0
        if affected_user_ids:
            users_without_cutoff = await conn.fetchval(
                "SELECT COUNT(*) FROM users "
                "WHERE id = ANY($1::text[]) "
                "AND (last_password_change IS NULL OR last_password_change < $2)",
                affected_user_ids,
                now,
            )

        print(f"\nRemaining active rows with NULL refresh_jti: {remaining_rows}")
        print(f"Affected users still missing the cutoff:    {users_without_cutoff}")

        if remaining_rows or users_without_cutoff:
            print(
                "WARNING: expected 0 on both — investigate before "
                "considering the backfill complete.",
                file=sys.stderr,
            )
            return 1

        print(
            "\nOK — success criterion met:\n"
            "  * legacy NULL-refresh_jti rows: closed\n"
            "  * affected users: forced through re-login on next request"
        )
        return 0
    finally:
        await conn.close()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts without modifying any rows.",
    )
    args = p.parse_args()
    sys.exit(asyncio.run(run(dry_run=args.dry_run)))


if __name__ == "__main__":
    main()
