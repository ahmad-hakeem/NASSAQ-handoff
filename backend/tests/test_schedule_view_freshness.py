"""Task #122 — regression guard for the Smart Schedule view freshness bug
fixed in Task #121.

The bug: after the school admin clicked "إنشاء الجدول تلقائياً" on the
Smart Schedule page, a brand-new *draft* timetable was written to the
database, but ``GET /api/schedule/master-grid`` kept returning the
previously *published* timetable. The page therefore appeared to "not
refresh" even though generation had succeeded.

The fix lives in three places — and each needs an automated guard so a
future change cannot silently regress it:

1. ``_resolve_active_timetable`` must pick the most recently *updated*
   timetable across both ``draft`` and ``published`` statuses, instead
   of always preferring the latest published one. Three precedence
   cases are exercised:
     a. older published + newer draft  → returns the new draft
     b. newer published + older draft  → returns the published one
     c. only one timetable exists      → returns it (draft or published)

2. ``GET /api/schedule/master-grid`` must set ``Cache-Control: no-store``
   plus the legacy ``Pragma`` and ``Expires`` headers so the browser /
   any proxy never serves a stale copy of the previous timetable after
   a fresh generation.

3. End-to-end: POST ``/smart-scheduling/generate/{school_id}`` and then
   immediately GET ``/schedule/master-grid`` — the response's
   ``timetable_id`` must match the freshly generated draft and the
   ``cells`` payload must be non-empty. This is the contract the
   Smart Schedule page relies on for ``loadGrid`` after
   ``handleAutoGenerate``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from dependencies import db
from engines.sql_utils import gd_insert
from routes.schedule_master_grid_routes import _resolve_active_timetable

# Reuse the heavy generation seed from the dynamic-periods test so we
# don't duplicate ~90 lines of setup. The helper inserts the minimum
# academic year / term / grade / class / subjects / teachers /
# assignments + 10 teaching periods that ``generate_timetable`` needs
# to produce a non-empty draft.
from tests.test_master_grid_dynamic_periods import _seed_full_ten_period_school


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _mk_timetable(
    school_id: str,
    *,
    status: str,
    updated_offset_minutes: int,
    name: str | None = None,
) -> str:
    """Insert a timetables row whose ``updated_at`` is offset from "now".

    Negative ``updated_offset_minutes`` means older; positive means newer.
    ``created_at`` mirrors ``updated_at`` so the resolver's fallback path
    (created_at when updated_at is missing) is unaffected.
    """
    base = datetime.now(timezone.utc)
    ts = (base + timedelta(minutes=updated_offset_minutes)).isoformat()
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "timetables", {
        "id": tid,
        "school_id": school_id,
        "name": name or f"TT-{status}-{tid[:6]}",
        "academic_year": "2026-2027",
        "semester": 1,
        "status": status,
        "version": 1,
        "total_sessions": 0,
        "created_at": ts,
        "updated_at": ts,
    })
    return tid


# ---------------------------------------------------------------------------
# 1. _resolve_active_timetable — precedence by recency, not by status.
# ---------------------------------------------------------------------------


async def test_resolver_prefers_newer_draft_over_older_published(tenant_a):
    """Original Task #121 bug scenario: a newer draft must win over an
    older published timetable. This is the case that was broken before
    the fix — the resolver kept returning the published row.
    """
    older_published = await _mk_timetable(
        tenant_a, status="published", updated_offset_minutes=-60,
    )
    newer_draft = await _mk_timetable(
        tenant_a, status="draft", updated_offset_minutes=-1,
    )

    picked = await _resolve_active_timetable(tenant_a)

    assert picked is not None, "Resolver returned None despite two timetables"
    assert picked["id"] == newer_draft, (
        "Resolver must return the newer draft; instead returned "
        f"id={picked['id']} (status={picked.get('status')}). "
        f"newer_draft={newer_draft} older_published={older_published}"
    )
    assert picked.get("status") == "draft"


async def test_resolver_prefers_newer_published_over_older_draft(tenant_a):
    """Symmetric case: a newer published timetable must beat an older
    draft. Guards against an over-eager fix that would always prefer
    drafts and bring back the inverse bug.
    """
    older_draft = await _mk_timetable(
        tenant_a, status="draft", updated_offset_minutes=-120,
    )
    newer_published = await _mk_timetable(
        tenant_a, status="published", updated_offset_minutes=-5,
    )

    picked = await _resolve_active_timetable(tenant_a)

    assert picked is not None
    assert picked["id"] == newer_published, (
        "Resolver must return the newer published timetable; got "
        f"id={picked['id']} (status={picked.get('status')}). "
        f"newer_published={newer_published} older_draft={older_draft}"
    )
    assert picked.get("status") == "published"


@pytest.mark.parametrize("only_status", ["draft", "published"])
async def test_resolver_returns_the_only_timetable_regardless_of_status(
    tenant_a, only_status,
):
    """When a school has exactly one timetable, the resolver must
    surface it whether it's a draft or published — never None.
    """
    tid = await _mk_timetable(
        tenant_a, status=only_status, updated_offset_minutes=-10,
    )

    picked = await _resolve_active_timetable(tenant_a)

    assert picked is not None, (
        f"Resolver returned None even though a {only_status} timetable exists"
    )
    assert picked["id"] == tid
    assert picked.get("status") == only_status


# ---------------------------------------------------------------------------
# 2. Master-grid response must disable caching.
# ---------------------------------------------------------------------------


async def test_master_grid_response_disables_caching(
    client, school_principal_headers, tenant_a,
):
    """The Smart Schedule page re-fetches /schedule/master-grid right
    after triggering generation. If the response is cacheable, the
    browser (or any intermediary proxy) can serve the *previous* grid
    and re-introduce the Task #121 bug at the network layer — even if
    the resolver itself is correct.

    The fix sets three explicit no-cache headers; this test guards all
    three so removing any one of them fails the build.
    """
    r = await client.get(
        f"/schedule/master-grid?school_id={tenant_a}",
        headers=school_principal_headers,
    )
    assert r.status_code == 200, r.text

    cache_control = r.headers.get("cache-control", "")
    assert "no-store" in cache_control.lower(), (
        f"Cache-Control must include 'no-store'; got: {cache_control!r}"
    )
    # The full directive set we ship — keep the assertion strict so a
    # casual rewrite that drops the belt-and-braces directives surfaces.
    for directive in ("no-cache", "must-revalidate", "max-age=0"):
        assert directive in cache_control.lower(), (
            f"Cache-Control must include '{directive}'; got: {cache_control!r}"
        )

    assert r.headers.get("pragma", "").lower() == "no-cache", (
        f"Pragma must be 'no-cache'; got: {r.headers.get('pragma')!r}"
    )
    assert r.headers.get("expires") == "0", (
        f"Expires must be '0'; got: {r.headers.get('expires')!r}"
    )


# ---------------------------------------------------------------------------
# 3. End-to-end: generate then refetch returns the freshly generated draft.
# ---------------------------------------------------------------------------


async def test_generate_then_master_grid_returns_fresh_draft(
    client, school_principal_headers, tenant_a,
):
    """Reproduces the user-facing flow that Task #121 fixed:

      1. POST /smart-scheduling/generate/{school_id} — engine writes a
         brand-new draft timetable.
      2. GET /schedule/master-grid?school_id=... — the page's loadGrid
         call.

    The refetched payload's ``timetable_id`` must equal the freshly
    generated draft id, and ``cells`` must be non-empty. If the
    resolver regresses to "always prefer published", the generate call
    still succeeds but the GET will either return a stale id or an
    empty grid — both caught here.

    To make the regression unambiguous we *also* seed an older
    published timetable for the same school so the resolver has a
    real choice to make. Without this seeded competitor the test
    would pass even if the resolver ignored status entirely.
    """
    # 1) Pre-seed an older published timetable so the resolver has to
    #    actively prefer the newer draft over it. We give it the same
    #    school_id so the master-grid filter picks it up.
    stale_published_id = await _mk_timetable(
        tenant_a, status="published", updated_offset_minutes=-90,
        name="Stale Published",
    )

    # 2) Seed everything generate_timetable needs to produce sessions.
    await _seed_full_ten_period_school(tenant_a)
    await db.session.commit()

    # 3) Trigger generation as a school principal (allowed role).
    gen = await client.post(
        f"/smart-scheduling/generate/{tenant_a}",
        headers=school_principal_headers,
        json={},
    )
    assert gen.status_code == 200, (
        f"Generation must succeed; got {gen.status_code}: {gen.text}"
    )
    gen_body = gen.json()
    assert gen_body.get("success") is True, (
        f"Generation reported failure: {gen_body.get('message_ar') or gen_body}"
    )
    fresh_draft_id = gen_body.get("timetable_id")
    assert fresh_draft_id, (
        f"Generation response must expose timetable_id; got keys: "
        f"{list(gen_body.keys())}"
    )
    assert fresh_draft_id != stale_published_id, (
        "Sanity: the engine should have minted a new draft, not reused "
        "the seeded stale published id"
    )
    assert (gen_body.get("scheduled_sessions") or 0) > 0, (
        "Generation produced zero sessions — seed/engine drift, this "
        "test cannot validate freshness without real sessions."
    )

    # 4) The refetch the frontend issues immediately after generation.
    grid = await client.get(
        f"/schedule/master-grid?school_id={tenant_a}",
        headers=school_principal_headers,
    )
    assert grid.status_code == 200, grid.text
    body = grid.json()

    assert body.get("timetable_id") == fresh_draft_id, (
        "Master Grid must surface the freshly generated draft (the "
        "Task #121 bug). Expected timetable_id="
        f"{fresh_draft_id} (status=draft) but got "
        f"timetable_id={body.get('timetable_id')} "
        f"(status={body.get('timetable_status')}). "
        f"Stale published competitor was {stale_published_id}."
    )
    assert body.get("timetable_status") == "draft", (
        "The fresh timetable should still be a draft right after "
        f"generation; got status={body.get('timetable_status')!r}"
    )

    # 5) The cells payload must be non-empty — proves the grid actually
    #    rendered the new sessions, not just the matching id.
    cells = body.get("cells") or {}
    cell_count = sum(
        len(period_map)
        for day_map in cells.values()
        for period_map in day_map.values()
    )
    assert cell_count > 0, (
        "Master Grid returned the fresh timetable_id but zero cells — "
        "session payload is empty, breaking the rendered schedule."
    )
