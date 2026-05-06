"""Task #142 — guard the visible-window pagination contract on
``GET /api/schedule/master-grid``.

The redesigned Master Schedule workspace can opt into a paginated
teacher window via ``?teacher_page_size=N&teacher_page=K``. When this
opt-in is active, the response must:

  1. Include only the requested teacher slice (length <= page_size).
  2. Surface a ``pagination`` block reflecting the full school total.
  3. Restrict the ``cells`` payload to the visible teacher ids — no
     leakage of session data for teachers outside the window.

When the opt-in is *not* active (page_size = 0 or omitted), the legacy
"send everything" behaviour must be preserved so existing callers
(exports, the substitution drawer's bulk lookups, etc.) keep working.
"""

from __future__ import annotations

import uuid

import pytest

from datetime import datetime, timezone

from dependencies import db
from engines.sql_utils import gd_insert


pytestmark = pytest.mark.asyncio


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime("%A").lower()


async def _seed_substitute(
    school_id: str,
    *,
    absent_tid: str,
    sub_tid: str,
    day: str,
    period: int = 1,
) -> str:
    """Insert a single substitute_assignments row for today (the
    overlay code only injects rows where absence_date == today)."""
    sub_id = str(uuid.uuid4())
    today_iso = datetime.now(timezone.utc).date().isoformat()
    await gd_insert(db.session, "substitute_assignments", {
        "id": sub_id,
        "school_id": school_id,
        "original_session_id": str(uuid.uuid4()),
        "original_teacher_id": absent_tid,
        "substitute_teacher_id": sub_tid,
        "absence_date": today_iso,
        "day_of_week": day,
        "period_number": period,
        "class_id": None,
        "class_name": "س1/1",
        "subject_id": None,
        "subject_name": "اختبار",
    })
    await db.session.commit()
    return sub_id


async def _seed_teachers(school_id: str, n: int) -> list[str]:
    """Insert ``n`` active teachers ordered by full_name (T01..Tnn)."""
    ids: list[str] = []
    for i in range(1, n + 1):
        tid = str(uuid.uuid4())
        await gd_insert(db.session, "teachers", {
            "id": tid,
            "school_id": school_id,
            "full_name": f"T{i:02d} مدرس",
            "is_active": True,
        })
        ids.append(tid)
    await db.session.commit()
    return ids


async def test_paginated_window_returns_bounded_teacher_slice(
    client, school_principal_headers, tenant_a,
):
    """page_size=3 must return at most 3 teachers and report the full total."""
    await _seed_teachers(tenant_a, 7)

    r = await client.get(
        f"/schedule/master-grid?school_id={tenant_a}"
        f"&teacher_page=1&teacher_page_size=3",
        headers=school_principal_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()

    assert len(body["teachers"]) <= 3, (
        f"Window must cap teachers at page_size=3; got {len(body['teachers'])}"
    )
    pg = body.get("pagination")
    assert pg is not None, "Paginated response must surface a pagination block"
    assert pg["windowed"] is True
    assert pg["page"] == 1
    assert pg["page_size"] == 3
    assert pg["total"] >= 7, (
        "Pagination.total must reflect the full school size, not the "
        f"window size; got {pg['total']}"
    )


async def test_unpaginated_default_preserves_legacy_full_payload(
    client, school_principal_headers, tenant_a,
):
    """Without page_size, the response must include every active teacher
    and mark itself as non-windowed (legacy contract)."""
    await _seed_teachers(tenant_a, 4)

    r = await client.get(
        f"/schedule/master-grid?school_id={tenant_a}",
        headers=school_principal_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()

    pg = body.get("pagination")
    assert pg is not None
    assert pg["windowed"] is False, (
        "Without teacher_page_size the response must report windowed=False "
        "so legacy callers know they're getting the full payload."
    )
    # All seeded teachers must appear in the unpaginated response.
    assert len(body["teachers"]) >= 4


async def test_day_param_scopes_response_to_single_day(
    client, school_principal_headers, tenant_a,
):
    """When the client requests ``day=sunday`` (daily-view scoping), the
    response's pagination block must echo the requested day so the
    client knows the payload is windowed by day, and any cells returned
    must only carry sessions for that day."""
    await _seed_teachers(tenant_a, 2)

    r = await client.get(
        f"/schedule/master-grid?school_id={tenant_a}&day=sunday",
        headers=school_principal_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()

    pg = body.get("pagination") or {}
    assert pg.get("day") == "sunday", (
        f"pagination.day must echo the requested day; got {pg.get('day')!r}"
    )

    # Every cell entry must be keyed by 'sunday' only — no other day
    # should appear when the request is scoped to a single day.
    for teacher_id, days_dict in (body.get("cells") or {}).items():
        other_days = set(days_dict.keys()) - {"sunday"}
        assert not other_days, (
            f"cells for teacher {teacher_id} leaked days outside the "
            f"requested window: {other_days}"
        )


async def test_invalid_day_param_is_ignored_gracefully(
    client, school_principal_headers, tenant_a,
):
    """An unknown day string must not crash the route; the response
    should fall back to the full-week contract (pagination.day=null)."""
    r = await client.get(
        f"/schedule/master-grid?school_id={tenant_a}&day=funday",
        headers=school_principal_headers,
    )
    assert r.status_code == 200, r.text
    pg = r.json().get("pagination") or {}
    assert pg.get("day") is None, (
        f"Invalid day must be ignored, not echoed; got {pg.get('day')!r}"
    )


async def test_substitution_overlay_respects_paginated_window(
    client, school_principal_headers, tenant_a,
):
    """Regression for the substitution-overlay leak: when the request
    is windowed (teacher_page_size=2), the overlay must NOT inject
    synthetic cells for absent or substitute teachers that live on
    other pages. We seed 5 teachers, ask for page 1 (teachers 1–2),
    and pin a substitution between teachers 4 and 5 (both off-window).
    The cells dict must not gain keys for the off-window teachers."""
    seeded_ids = set(await _seed_teachers(tenant_a, 5))
    today = _today_key()

    # Discover which teachers actually land on page 1 vs off-window
    # (other tests in this fixture may have already populated the
    # tenant, and the route orders by full_name — so we can't assume a
    # particular alphabetical position).
    probe = await client.get(
        f"/schedule/master-grid?school_id={tenant_a}"
        f"&teacher_page=1&teacher_page_size=2",
        headers=school_principal_headers,
    )
    assert probe.status_code == 200, probe.text
    page_one_ids = {t["id"] for t in probe.json()["teachers"]}
    off_window = [tid for tid in seeded_ids if tid not in page_one_ids]
    assert len(off_window) >= 2, (
        "expected at least 2 seeded teachers to fall outside page 1 of size 2"
    )
    absent_tid, sub_tid = off_window[0], off_window[1]

    await _seed_substitute(
        tenant_a,
        absent_tid=absent_tid,
        sub_tid=sub_tid,
        day=today,
    )

    r = await client.get(
        f"/schedule/master-grid?school_id={tenant_a}"
        f"&teacher_page=1&teacher_page_size=2",
        headers=school_principal_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()

    visible = {t["id"] for t in body["teachers"]}
    assert len(visible) <= 2, "page_size=2 must return at most 2 teachers"
    assert absent_tid not in visible, "absent teacher must be off-window"
    assert sub_tid not in visible, "substitute teacher must be off-window"

    cell_ids = set(body.get("cells", {}).keys())
    assert absent_tid not in cell_ids, (
        "substitution overlay leaked a cell for the off-window absent teacher"
    )
    assert sub_tid not in cell_ids, (
        "substitution overlay leaked a synthetic cell for the off-window substitute"
    )
    leaked = cell_ids - visible
    assert not leaked, (
        f"substitution overlay leaked cells for off-window teachers: {leaked}"
    )


async def test_substitution_overlay_respects_day_scope(
    client, school_principal_headers, tenant_a,
):
    """When the client requests a single day in daily mode, the
    substitution overlay must skip rows for any other day. We seed a
    substitute on today, then request a different day — the cells
    payload must not contain any keys for today (or any day other
    than the requested one)."""
    teacher_ids = await _seed_teachers(tenant_a, 2)
    today = _today_key()
    await _seed_substitute(
        tenant_a,
        absent_tid=teacher_ids[0],
        sub_tid=teacher_ids[1],
        day=today,
    )

    # Pick a non-today day from the working week so the overlay must
    # be filtered out by the day scope.
    other_day = next(
        d for d in ("sunday", "monday", "tuesday", "wednesday", "thursday")
        if d != today
    )
    r = await client.get(
        f"/schedule/master-grid?school_id={tenant_a}&day={other_day}",
        headers=school_principal_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()

    for tid, days_dict in (body.get("cells") or {}).items():
        leaked_days = set(days_dict.keys()) - {other_day}
        assert not leaked_days, (
            f"substitution overlay leaked off-day cells for teacher {tid}: "
            f"{leaked_days} (requested only {other_day})"
        )


async def test_paginated_cells_do_not_leak_outside_window(
    client, school_principal_headers, tenant_a,
):
    """The cells payload must only contain teacher ids inside the
    requested window — never sessions for teachers on other pages."""
    teacher_ids = await _seed_teachers(tenant_a, 5)

    r = await client.get(
        f"/schedule/master-grid?school_id={tenant_a}"
        f"&teacher_page=1&teacher_page_size=2",
        headers=school_principal_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()

    visible_ids = {t["id"] for t in body["teachers"]}
    assert len(visible_ids) <= 2

    # The cells dict is keyed by teacher_id. Every key must belong to
    # the visible window — no session data for off-page teachers.
    cell_ids = set(body.get("cells", {}).keys())
    assert cell_ids.issubset(visible_ids), (
        "cells contains teacher ids outside the visible window: "
        f"leaked={cell_ids - visible_ids}, visible={visible_ids}, "
        f"all_seeded={set(teacher_ids)}"
    )
