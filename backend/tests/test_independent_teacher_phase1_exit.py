"""IT Phase 1 §5.9 exit-criteria consolidated test suite (Task #202).

Spec: docs/specs/2026-05-12-independent-teacher-phased-spec.md §5.9 + §8.

This file is a single, self-contained verification harness that maps 1:1
to the seven Phase 1 exit criteria. Each test (or parametrized group)
carries an inline `# §5.9 #N` marker so the QA doc
`docs/qa/2026-05-12-it-phase1-exit-criteria.md` can map criterion → test.

Coverage map:
  §5.9 #1  — B-1..B-6 in main with passing tests          (sanity import)
  §5.9 #2  — Cross-workspace isolation (6 collections,
             both LIST and BY-ID 404 invariants)          (parametrized)
  §5.9 #3  — Capability-gate negatives + principal-positive
             no-regression checks                          (parametrized)
  §5.9 #4  — Bootstrap idempotency                         (single test)
  §5.9 #5  — Communication cohort scoping (incl. shape)    (single test)
  §5.9 #6  — MFA Tier A on every §5.7 route, including the
             backfilled student/parent contact paths       (parametrized)
  §5.9 #7  — End-to-end loop driven by real backend APIs   (single test)

Shared helpers live in `backend/tests/_it_fixtures.py` so the per-feature
IT test files (`_communication`, `_invite_parent`, `_phase1_smoke`,
`_it_mfa_stepup_backfill`) can converge on the same workspace bootstrap.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.core.guards.tenant_guard import (
    INDEPENDENT_TEACHER_DENIED_AR,
    independent_workspace_id,
)
from dependencies import db, UserRole
from engines.sql_utils import gd_count, gd_find, gd_find_one, gd_insert

from tests._it_fixtures import (
    STEP_UP_CODES,
    headers,
    it_headers,
    mk_it_workspace,
    now_ts,
    seed_active_passkey,
)


def _stepup_code(payload: dict) -> str | None:
    """Extract canonical step-up code from either `{detail:{code}}`
    or wrapped `{error:{code}}` envelopes."""
    for key in ("detail", "error"):
        node = payload.get(key)
        if isinstance(node, dict) and node.get("code") in STEP_UP_CODES:
            return node["code"]
    return None


# ===========================================================================
# §5.9 #1 — B-1..B-6 in main with passing tests (sanity)
# ===========================================================================
def test_5_9_1_phase0_b_marker_symbols_present():  # §5.9 #1
    """Sanity: the canonical helpers/constants the rest of this suite
    parametrizes over MUST be importable. A regression that strips them
    would make §5.9 #2/#3 silently degrade — we want a loud failure."""
    from src.core.middleware.rbac import ROLE_PERMISSIONS, Permission
    from quotas.independent_teacher import MAX_CLASSES, MAX_STUDENTS
    from src.core.guards.tenant_guard import (  # noqa: F401  (import-only sanity)
        require_full_school_tenant,
        require_workspace_materialised,
        independent_workspace_id as _iwid,
    )
    from dependencies import (  # noqa: F401
        require_recent_mfa,
        require_recent_mfa_403,
        require_recent_mfa_403_if_independent_teacher,
    )

    it_perms = ROLE_PERMISSIONS["independent_teacher"]
    # B-1 / Task #194 — IT slice grants the canonical Phase 1 permissions.
    for required in (
        Permission.SCHEDULE_VIEW.value,
        Permission.ATTENDANCE_RECORD.value,
        Permission.ASSESSMENTS_GRADE.value,
        Permission.ASSESSMENTS_EDIT.value,
        Permission.NOTIFICATIONS_VIEW.value,
        Permission.NOTIFICATIONS_SEND.value,
    ):
        assert required in it_perms, required
    # B-5 — quota constants exist. Classes are now UNLIMITED (None); the
    # student cap remains a positive v1 value.
    assert MAX_CLASSES is None and MAX_STUDENTS > 0


# ===========================================================================
# §5.9 #2 — Cross-workspace isolation
# ===========================================================================
# Pattern from `backend/tests/test_ai_insights_security.py`: seed in IT-A,
# read as IT-B, expect zero leakage on BOTH list and by-id surfaces.
# §8 invariant 3 requires by-id reads to return 404 (never 403/200) so
# row existence in another workspace is not leaked.
#
# Each row in _ISOLATION_MATRIX carries:
#   collection — table to seed in IT-A
#   list_path  — IT-reachable list endpoint (or None if no IT list exists)
#   by_id_tpl  — IT-reachable by-id endpoint template (`{id}` placeholder)
#                that, when called as IT-B against the IT-A row id, MUST
#                return 404. None means no IT-reachable by-id exists.
# by_id_tpl semantics:
#   - "MUST be 404" surfaces use a plain template string. The cross-IT
#     lookup MUST return 404 per §8 invariant 3.
#   - Some production routes return a stricter envelope (assessments
#     returns 403 via the shared `tenant_scoped_find_one` helper, and
#     behaviour-records by-id has no tenant pinning at all in v1 — the
#     callers there go through `/behaviour-records/student/{id}` /
#     /class/{id}/...). Where the prod contract diverges from the §8
#     invariant in v1, we still pin the actual security property
#     (no leak of A's row contents) via `non_404_must_not_leak=True`
#     so the test fails loudly the day a real leak appears.
_ISOLATION_MATRIX = [
    # (collection, list_path, by_id_tpl, by_id_mode)
    # The only by_id_mode is "404" — §8 invariant 3. Where v1 prod
    # diverges (returning 403/200 instead) the entry is wrapped in
    # `pytest.xfail(strict=True)` with a documented deviation in
    # docs/qa/2026-05-12-it-phase1-exit-criteria.md so the suite flips
    # to xpass the day the fix lands and the contract tightens.
    ("students",         "/students",          "/students/{id}",                    "404"),
    ("classes",          "/classes",           "/classes/{id}",                     "404"),
    # Task #203 closed the prod gap: `/attendance/student/{id}` now
    # tenant-pins the student lookup before the relationship check, so
    # cross-workspace returns 404 (spec §8 invariant 3).
    ("attendance", None, "/attendance/student/{student_id}", "404"),
    # Task #203 closed the prod gap: `tenant_scoped_find_one` now falls
    # back to the IT synthetic workspace, so `/assessments/{id}` returns
    # 404 (not 403) cross-workspace.
    ("assessments", "/assessments", "/assessments/{id}", "404"),
    # Task #203 closed the prod gap: `/behaviour-records/{id}` now
    # tenant-pins via `require_request_school_id` and returns 404
    # cross-workspace instead of leaking A's row.
    ("behaviour_records", None, "/behaviour-records/{id}", "404"),
    ("notifications",    "/notifications",     None,                                None),
]


async def _seed_isolation_row(collection: str, a: dict, seeded_id: str) -> None:
    """Seed exactly one row in workspace A for `collection`."""
    if collection == "students":
        await gd_insert(db.session, "students", {
            "id": seeded_id, "school_id": a["wsid"], "tenant_id": a["wsid"],
            "class_id": a["class_id"], "full_name": "leak-A", "is_active": True,
        })
    elif collection == "classes":
        await gd_insert(db.session, "classes", {
            "id": seeded_id, "school_id": a["wsid"], "tenant_id": a["wsid"],
            "name": "leak-A", "is_active": True,
        })
    elif collection == "attendance":
        await gd_insert(db.session, "attendance", {
            "id": seeded_id, "school_id": a["wsid"], "tenant_id": a["wsid"],
            "class_id": a["class_id"], "student_id": a["student_id"],
            "date": "2026-05-12", "status": "present",
        })
    elif collection == "assessments":
        await gd_insert(db.session, "assessments", {
            "id": seeded_id, "school_id": a["wsid"], "tenant_id": a["wsid"],
            "class_id": a["class_id"], "name": "leak-A", "title": "leak-A",
            "type": "quiz", "max_score": 10, "weight": 1.0,
        })
    elif collection == "behaviour_records":
        await gd_insert(db.session, "behaviour_records", {
            "id": seeded_id, "school_id": a["wsid"],
            "class_id": a["class_id"], "student_id": a["student_id"],
            "teacher_id": a["teacher_id"],
            "type": "positive", "category": "participation",
            "severity": "minor", "points": 0,
            "description": "leak-A",
            "date": datetime.now(timezone.utc).isoformat(),
        })
    elif collection == "notifications":
        await gd_insert(db.session, "notifications", {
            "id": seeded_id, "user_id": a["uid"], "tenant_id": a["wsid"],
            "type": "system", "title": "leak-A", "message": "x",
            "is_read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })


@pytest.mark.asyncio
async def test_5_9_2_behaviour_record_by_id_owner_200_intruder_404(client):
    """Focused behaviour-record by-id contract (Task #203 review):
    - IT-A (owner) reads its own row → 200 (no regression: the legacy
      `behaviour_records` shape carries `school_id` only, no
      `tenant_id`; the gd_find_one TENANT_ALIAS must keep this readable
      when the route filters on `tenant_id`).
    - IT-B (intruder) reads the same row → 404 (§8 invariant 3).
    """
    a = await mk_it_workspace(with_passkey=False)
    b = await mk_it_workspace(with_passkey=False)
    seeded_id = str(uuid.uuid4())
    await gd_insert(db.session, "behaviour_records", {
        "id": seeded_id,
        "school_id": a["wsid"],  # legacy shape: school_id only
        "class_id": a["class_id"],
        "student_id": a["student_id"],
        "teacher_id": a["teacher_id"],
        "type": "positive",
        "category": "participation",
        "severity": "minor",
        "points": 0,
        "description": "owner-read",
        "date": datetime.now(timezone.utc).isoformat(),
    })
    await db.session.flush()

    r_owner = await client.get(
        f"/behaviour-records/{seeded_id}", headers=it_headers(a),
    )
    assert r_owner.status_code == 200, r_owner.text
    assert r_owner.json()["id"] == seeded_id

    r_intruder = await client.get(
        f"/behaviour-records/{seeded_id}", headers=it_headers(b),
    )
    assert r_intruder.status_code == 404, r_intruder.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "collection,list_path,by_id_tpl,by_id_mode",
    _ISOLATION_MATRIX,
    ids=lambda v: v if isinstance(v, str) else None,
)
async def test_5_9_2_cross_workspace_isolation_list_and_by_id(  # §5.9 #2
    client, collection, list_path, by_id_tpl, by_id_mode,
):
    """For each tenant-scoped collection in §5.9 #2, verify that an IT-A
    seeded row is invisible to IT-B on the list endpoint AND that the
    BY-ID read returns 404 (never 403, per §8 invariant 3)."""
    a = await mk_it_workspace(with_passkey=False)
    b = await mk_it_workspace(with_passkey=False)
    seeded_id = str(uuid.uuid4())
    await _seed_isolation_row(collection, a, seeded_id)

    # Sanity: the row really exists in A (otherwise the leak-test is vacuous).
    persisted = await gd_find(
        db.session, collection, {"id": seeded_id}, limit=1,
    )
    assert persisted, (collection, "fixture row missing — test would be vacuous")

    h_b = it_headers(b)

    # 1) LIST surface (where IT has one) — A's row must not appear.
    if list_path is not None:
        resp = await client.get(list_path, headers=h_b)
        assert resp.status_code == 200, (collection, list_path, resp.text)
        body = resp.json()
        items = body if isinstance(body, list) else (
            body.get("items") or body.get("data") or []
        )
        assert all(it.get("id") != seeded_id for it in items), (collection, items)
        assert all(
            it.get("school_id") != a["wsid"] for it in items
        ), (collection, items)

    # 2) BY-ID surface — §8 invariant 3: cross-workspace MUST be 404,
    #    never 403/200 (no existence leak). The deviating routes are
    #    pinned as `xfail(strict=True)` in `_ISOLATION_MATRIX` above so
    #    the suite flips to xpass the day prod is fixed.
    if by_id_tpl is not None:
        path = by_id_tpl.format(
            id=seeded_id,
            student_id=a["student_id"] if "{student_id}" in by_id_tpl else seeded_id,
        )
        resp = await client.get(path, headers=h_b)
        assert resp.status_code == 404, (
            collection, path, resp.status_code, resp.text,
        )


# ===========================================================================
# §5.9 #3 — Capability-gate negatives + principal-positive no-regression
# ===========================================================================
# Each row hits a capability gated 🔒 by `require_full_school_tenant` per
# §4.2. We assert TWO contracts per route:
#   (a) IT caller → 403 with the canonical `INDEPENDENT_TEACHER_DENIED_AR`
#   (b) Principal caller → response is NOT the canonical IT-deny envelope
#       (catches over-broad blocks that would also break real schools).
#
# The principal caller may legitimately get 200/404/422/etc depending on
# the route — what matters is that the IT-deny gate did NOT fire for them.

# Spec §4.2 enumerates the routers `require_full_school_tenant` is
# applied to. We exercise at least one representative WRITE surface
# from every gated router class plus the read surfaces that surface
# tenant-wide data to the IT FE — both halves of the contract matter
# for "no Phase-1 IT can reach a Phase-0 capability".
_CAPABILITY_DENY_ROUTES = [
    # ---- reads (existence-check + sidebar surfacing) ----------------
    ("GET",    "/smart-scheduling/timetable/versions",            None),
    ("GET",    "/standby/candidates",                              None),
    ("GET",    "/teacher-attendance",                              None),
    ("GET",    "/bulk/template/students",                          None),
    ("GET",    "/bulk/export/students",                            None),
    ("GET",    "/v1/hakeem-plan/tasks",                            None),
    ("GET",    "/principal/search-users",                          None),
    # ---- writes (the §4.2 deny-list backbone) -----------------------
    # scheduling_smart_engine_routes — generate / publish.
    ("POST",   "/timetable/generate-smart",
        {"school_id": "x", "academic_year_id": "y"}),
    # scheduling_smart_session_routes — session writes.
    ("POST",   "/smart-scheduling/sessions/swap",
        {"session_a_id": "a", "session_b_id": "b"}),
    ("POST",   "/smart-scheduling/session/add",
        {"day_of_week": "sun", "slot_number": 1, "class_id": "c", "subject_id": "s", "teacher_id": "t"}),
    # standby_routes — substitution writes.
    ("POST",   "/substitutions",
        {"original_session_id": "x", "substitute_teacher_id": "t", "date": "2026-05-12"}),
    ("POST",   "/standby/roster/regenerate",                       {}),
    # principal_management_routes — staff/student/parent writes.
    ("PUT",    "/principal/teacher/00000000-0000-0000-0000-000000000000/basic-info",
        {"full_name": "x"}),
    ("POST",   "/principal/generate-password",                     {}),
    # bulk_teacher_routes — bulk staff import.
    ("POST",   "/teachers/bulk/parse",                             {}),
    # hakeem_plan_routes_mod — task author write.
    ("POST",   "/v1/hakeem-plan/tasks",
        {"title": "x", "category": "academic", "priority": "medium", "due_at": "2026-05-12"}),
    # school_settings_mod — write surfaces (the gated module mounted
    # with `_full_tenant_dep`; the per-route paths in school_settings
    # _routes.py share the `/school/settings` prefix and IT-keeps-read
    # comes from §5.2).
    ("PUT",    "/school/settings",                                 {}),
    ("POST",   "/school/settings/holidays",
        {"name": "x", "date": "2026-05-12"}),
    # communication_routes — school-wide broadcast.
    ("POST",   "/communication/broadcast",
        {"title": "x", "content": "y", "audience": "all", "channels": ["in_app"]}),
]


def _is_it_deny_envelope(resp) -> bool:
    """True iff the response is the canonical IT capability-gate 403."""
    if resp.status_code != 403:
        return False
    try:
        payload = resp.json()
    except ValueError:
        return False
    msg = (
        (payload.get("error") or {}).get("message")
        or payload.get("detail")
        or ""
    )
    if isinstance(msg, dict):
        msg = msg.get("message") or msg.get("detail") or ""
    return INDEPENDENT_TEACHER_DENIED_AR in str(msg)


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", _CAPABILITY_DENY_ROUTES)
async def test_5_9_3_capability_gate_denies_independent_teacher(  # §5.9 #3
    client, method, path, body,
):
    """IT caller → 403 with the canonical Arabic deny message."""
    ctx = await mk_it_workspace(with_passkey=False)
    h = it_headers(ctx)
    resp = await client.request(method, path, headers=h, json=body)
    assert _is_it_deny_envelope(resp), (path, resp.status_code, resp.text)


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path,body", _CAPABILITY_DENY_ROUTES)
async def test_5_9_3_capability_gate_does_not_block_school_principal(  # §5.9 #3
    client, school_principal_headers, method, path, body,
):
    """Principal caller MUST NOT see the IT-deny envelope. The route
    may return 200/400/404/422 depending on its own contract — what we
    pin here is the no-regression invariant for real schools."""
    resp = await client.request(method, path, headers=school_principal_headers, json=body)
    assert not _is_it_deny_envelope(resp), (
        path, resp.status_code, resp.text,
        "principal saw the IT-deny envelope — capability gate is over-broad",
    )


# ---------------------------------------------------------------------------
# §5.9 #3 (Task #773) — class-scoped teaching endpoints are NOT behind the
# full-school-tenant gate. The curriculum-lesson + grade-column endpoints
# live on a separate (ungated) router so an IT caller can manage their own
# classes' curriculum/grades, while the smart-scheduling endpoints on the
# gated router stay denied. This locks in the split so the broad gate can't
# silently re-block the class endpoints again.
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_5_9_3_it_can_add_lesson_to_own_class_not_capability_blocked(client):
    """An IT account with a materialized workspace and an owned class can
    POST a curriculum lesson — it is NOT blocked by the capability gate."""
    ctx = await mk_it_workspace(with_passkey=False)
    h = it_headers(ctx)
    resp = await client.post(
        f"/class/{ctx['class_id']}/curriculum-plan/lesson",
        headers=h,
        json={"title": "الدرس الأول", "week": 1, "order": 1},
    )
    assert resp.status_code == 200, (resp.status_code, resp.text)
    body = resp.json()
    assert body["title"] == "الدرس الأول"
    assert body["class_id"] == ctx["class_id"]
    # Belt-and-suspenders: the response must NOT be the IT-deny envelope.
    assert not _is_it_deny_envelope(resp), resp.text

    # The lesson is readable back through the (also ungated) curriculum plan.
    plan = await client.get(
        f"/class/{ctx['class_id']}/curriculum-plan", headers=h,
    )
    assert plan.status_code == 200, plan.text
    assert any(l["id"] == body["id"] for l in plan.json()["lessons"])


@pytest.mark.asyncio
async def test_5_9_3_it_still_denied_on_smart_scheduling(client):
    """The same IT caller that can add lessons MUST still be denied on a
    representative smart-scheduling endpoint with the canonical envelope."""
    ctx = await mk_it_workspace(with_passkey=False)
    h = it_headers(ctx)
    resp = await client.post(
        "/smart-scheduling/session/add",
        headers=h,
        json={
            "day_of_week": "sun", "slot_number": 1,
            "class_id": ctx["class_id"], "subject_id": "s", "teacher_id": "t",
        },
    )
    assert _is_it_deny_envelope(resp), (resp.status_code, resp.text)


@pytest.mark.asyncio
async def test_5_9_3_it_cannot_add_lesson_cross_workspace(client):
    """Cross-workspace isolation is preserved: an IT caller cannot add a
    lesson to a class outside their own workspace (§8 inv. 3 → 404)."""
    a = await mk_it_workspace(with_passkey=False)
    b = await mk_it_workspace(with_passkey=False)
    resp = await client.post(
        f"/class/{a['class_id']}/curriculum-plan/lesson",
        headers=it_headers(b),
        json={"title": "leak", "week": 1, "order": 1},
    )
    assert resp.status_code == 404, (resp.status_code, resp.text)


# ===========================================================================
# §5.9 #4 — Bootstrap idempotency
# ===========================================================================
@pytest.mark.asyncio
async def test_5_9_4_bootstrap_replay_is_idempotent(client):  # §5.9 #4
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": f"it-{uid}@t.test",
        "full_name": f"IT-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
        "mfa_enrolled_at": datetime.now(timezone.utc).isoformat(),
    }
    await gd_insert(db.session, "users", user)
    wsid = independent_workspace_id(user)
    h = headers(uid, user["role"], None, mfa_recent_at=now_ts())

    payload = {
        "workspace_name_ar": "أكاديمية التجربة",
        "workspace_name_en": "Test Academy",
        "academic_year_label": "1447 - 1448 هـ",
        "term_label": "الفصل الأول",
        "working_days": ["sun", "mon", "tue", "wed", "thu"],
        "periods_per_day": 6,
    }

    first = await client.post(
        "/independent-teacher/bootstrap", headers=h, json=payload,
    )
    assert first.status_code == 200, first.text
    assert first.json()["already_materialised"] is False

    schools_before = await gd_count(db.session, "schools", {"id": wsid})
    years_before = await gd_count(db.session, "academic_years", {"school_id": wsid})
    teachers_before = await gd_count(db.session, "teachers", {"school_id": wsid})

    # Snapshot the caller's `users.tenant_id` before replay; idempotency
    # MUST keep this value stable (a bootstrap replay that flipped the
    # caller's tenant_id would break every subsequent IT request).
    user_before = await gd_find_one(db.session, "users", {"id": uid})
    tenant_id_before = user_before["tenant_id"]

    second = await client.post(
        "/independent-teacher/bootstrap", headers=h, json=payload,
    )
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["already_materialised"] is True
    assert body["workspace"]["workspace_id"] == wsid

    # Zero duplicate rows.
    assert await gd_count(db.session, "schools", {"id": wsid}) == schools_before
    assert await gd_count(db.session, "academic_years", {"school_id": wsid}) == years_before
    assert await gd_count(db.session, "teachers", {"school_id": wsid}) == teachers_before

    # users.tenant_id is unchanged by the replay (and equals wsid).
    user_after = await gd_find_one(db.session, "users", {"id": uid})
    assert user_after["tenant_id"] == tenant_id_before, (
        tenant_id_before, user_after["tenant_id"],
    )
    assert user_after["tenant_id"] == wsid, (wsid, user_after["tenant_id"])


# ===========================================================================
# §5.9 #5 — Communication cohort scoping (IT-A → only IT-A)
# ===========================================================================
@pytest.mark.asyncio
async def test_5_9_5_cohorts_scope_to_caller_workspace_only(client):  # §5.9 #5
    """IT-A's cohort lookup must (a) include A's own users, (b) exclude
    B's users, and (c) carry the documented response shape: every item
    has `user_id` + `student_id`, and `my_parents` items also surface
    the linked `parent_id` per `_resolve_my_parents_recipients`."""
    a = await mk_it_workspace(with_passkey=False)
    b = await mk_it_workspace(with_passkey=False)
    h_a = it_headers(a)

    expected_shape = {
        "my_students": ("user_id", "student_id"),
        "my_parents":  ("user_id", "student_id", "parent_id"),
    }

    for cohort, expected_uid, foreign_uid in (
        ("my_students", a["student_user_id"], b["student_user_id"]),
        ("my_parents",  a["parent_user_id"],  b["parent_user_id"]),
    ):
        resp = await client.get(
            f"/independent-teacher/communication/recipients?cohort={cohort}",
            headers=h_a,
        )
        assert resp.status_code == 200, (cohort, resp.text)
        items = resp.json().get("items") or []
        assert items, (cohort, "no items for caller's own workspace")
        user_ids = {i["user_id"] for i in items}
        assert expected_uid in user_ids, (cohort, items)
        assert foreign_uid not in user_ids, (cohort, items)

        # Shape contract — every item carries the documented keys
        # (asserted as "key present" rather than a value match so the
        # test stays robust to dedupe-path variations).
        for key in expected_shape[cohort]:
            assert all(key in it for it in items), (cohort, key, items)


# ===========================================================================
# §5.9 #6 — MFA Tier A enforced on every §5.7 route
# ===========================================================================
# Spec §5.7 enumerates: bootstrap, account-settings (email/phone/password/
# MFA), contact change on students/parents (incl. Invite Parent), data
# exports (reporting + IT schedule PDF), workspace deletion (Phase 2 only).
#
# An IT caller WITHOUT a recent MFA assertion must receive the canonical
# step-up envelope. The `acceptable_status` list reflects the documented
# split: bootstrap is 401 (its UX predates the FE replay interceptor and
# is handled by the wizard); every other surface is 403 so the AuthContext
# interceptor replays the call (`replit.md` IT §5.7).
_MFA_ROUTES = [
    # (label, method, path_template, json_body, acceptable_status)
    (
        "bootstrap",
        "POST", "/independent-teacher/bootstrap",
        {
            "workspace_name_ar": "أ", "workspace_name_en": "A",
            "academic_year_label": "1447", "term_label": "الفصل",
            "working_days": ["sun"], "periods_per_day": 5,
        },
        {401},
    ),
    (
        "profile_update",
        "PUT", "/users/me/profile",
        {"full_name": "اسم محدّث"},
        {403},
    ),
    (
        "report_export",
        "GET", "/export/report/school_attendance?format=xlsx", None,
        {403},
    ),
    (
        "attendance_export",
        "GET", "/export/attendance?format=xlsx", None,
        {403},
    ),
    (
        "schedule_export_pdf",
        "GET", "/independent-teacher/schedule/export.pdf", None,
        {403},
    ),
    # Backfilled §5.7 contact-change paths (Task #201) — the spec's
    # "Any contact change on `students` or `parents`" line.
    (
        "student_update",
        "PUT", "/students/{student_id}",
        {"full_name": "اسم محدّث"},
        {403},
    ),
    (
        "parent_delete",
        "DELETE", "/parents/{parent_id}", None,
        {403},
    ),
    (
        "invite_parent",
        "POST", "/independent-teacher/students/{student_id_unlinked}/invite-parent",
        {"full_name": "ولي أمر", "phone": "+966500000000"},
        {401, 403},
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "label,method,path_tpl,body,acceptable_status",
    _MFA_ROUTES,
    ids=[row[0] for row in _MFA_ROUTES],
)
async def test_5_9_6_mfa_required_routes_emit_stepup_envelope(  # §5.9 #6
    client, label, method, path_tpl, body, acceptable_status, enforce_mfa,
):
    if label == "bootstrap":
        # Bootstrap needs a pre-bootstrap caller (no synthetic schools row).
        uid = str(uuid.uuid4())
        user = {
            "id": uid,
            "role": UserRole.INDEPENDENT_TEACHER.value,
            "tenant_id": None,
            "email": f"it-{uid}@t.test",
            "full_name": f"IT-{uid[:6]}",
            "is_active": True,
            "password_hash": "x",
            "mfa_enrolled_at": datetime.now(timezone.utc).isoformat(),
        }
        await gd_insert(db.session, "users", user)
        h = headers(uid, user["role"], None, mfa_recent_at=None)
        path = path_tpl
    else:
        ctx = await mk_it_workspace()
        h = it_headers(ctx, with_mfa=False)
        # Seed an "unlinked" student for the invite-parent path so the
        # endpoint actually reaches its MFA gate (a linked student would
        # return 409 ALREADY_LINKED before hitting the gate).
        unlinked_sid = str(uuid.uuid4())
        await gd_insert(db.session, "students", {
            "id": unlinked_sid, "school_id": ctx["wsid"],
            "tenant_id": ctx["wsid"], "class_id": ctx["class_id"],
            "full_name": "طالب بلا ولي", "is_active": True,
        })
        path = path_tpl.format(
            student_id=ctx["student_id"],
            parent_id=ctx["parent_id"],
            student_id_unlinked=unlinked_sid,
        )

    resp = await client.request(method, path, headers=h, json=body)
    assert resp.status_code in acceptable_status, (
        label, resp.status_code, resp.text,
    )
    code = _stepup_code(resp.json())
    assert code in STEP_UP_CODES, (label, resp.json())


# ===========================================================================
# §5.9 #7 — End-to-end loop driven through real backend APIs
# ===========================================================================
# Spec: bootstrap → create class → create student → assign schedule slot →
# record attendance → grade an assessment → message a parent.
#
# Every step except the unavoidable fixture prerequisite (a `subjects`
# row, since IT has no public subject-create endpoint) is driven through
# a real HTTP route. Every persisted row must carry
# `school_id == itw_{user_id}`.

@pytest.mark.asyncio
async def test_5_9_7_end_to_end_independent_teacher_loop(client):  # §5.9 #7
    # 1) Bootstrap via the real endpoint.
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": f"it-{uid}@t.test",
        "full_name": f"IT-E2E-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
        "mfa_enrolled_at": datetime.now(timezone.utc).isoformat(),
    }
    await gd_insert(db.session, "users", user)
    await seed_active_passkey(uid)
    wsid = independent_workspace_id(user)

    h_pre = headers(uid, user["role"], None, mfa_recent_at=now_ts())
    bootstrap = await client.post(
        "/independent-teacher/bootstrap",
        headers=h_pre,
        json={
            "workspace_name_ar": "مساحة E2E",
            "workspace_name_en": "E2E",
            "academic_year_label": "1447 - 1448 هـ",
            "term_label": "الفصل الأول",
            "working_days": ["sun", "mon", "tue", "wed", "thu"],
            "periods_per_day": 6,
        },
    )
    assert bootstrap.status_code == 200, bootstrap.text
    teacher_row = await gd_find_one(db.session, "teachers", {"user_id": uid})
    assert teacher_row is not None
    teacher_id = teacher_row["id"]

    # Post-bootstrap token — the perimeter gate now accepts the wsid.
    h = headers(uid, user["role"], wsid, mfa_recent_at=now_ts())

    # 2) Create class via real route. Pin the IT as homeroom teacher in
    #    the request itself (the create endpoint accepts it) so the §5.6
    #    cohort sees the student created in step 3.
    create_class = await client.post(
        "/classes/create",
        headers=h,
        json={
            "name_ar": "فصل E2E",
            # Canonical grade id (digit fallback "1".."12") — the create
            # endpoint fail-closes on non-canonical grade ids since the
            # unified stage/grade validation.
            "grade_id": "5",
            "class_type": "regular",
            "capacity": 10,
            "homeroom_teacher_id": teacher_id,
        },
    )
    assert create_class.status_code == 200, create_class.text
    cls_rows = await gd_find(db.session, "classes", {"school_id": wsid}, limit=10)
    assert cls_rows, "class create did not persist"
    class_id = cls_rows[-1]["id"]
    assert all(c["school_id"] == wsid for c in cls_rows)
    cls_row = next(c for c in cls_rows if c["id"] == class_id)
    assert cls_row.get("homeroom_teacher_id") == teacher_id

    # 3) Create student via real /student-wizard/create (the IT-allowed
    #    creation route — `student_creation_routes.py:283` whitelists
    #    INDEPENDENT_TEACHER and accepts the workspace-mode zero-parent
    #    payload per §5.6).
    create_student = await client.post(
        "/student-wizard/create",
        headers=h,
        json={
            "full_name": "طالب E2E",
            "gender": "male",
            "date_of_birth": "2015-01-01",
            "education_level": "primary",
            "grade_id": "5",
            "class_id": class_id,
        },
    )
    assert create_student.status_code in (200, 201), create_student.text
    student_rows = await gd_find(
        db.session, "students",
        {"school_id": wsid, "class_id": class_id}, limit=5,
    )
    assert student_rows, "student create did not persist"
    student_id = student_rows[-1]["id"]
    assert all(s["school_id"] == wsid for s in student_rows)

    # 4) Assign a schedule slot via PUT /independent-teacher/schedule/slot.
    #    `subjects` has no IT-facing create endpoint, so we seed one
    #    directly (unavoidable fixture prerequisite).
    subject_id = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": subject_id, "name": "Math", "name_ar": "رياضيات",
        "school_id": wsid, "is_active": True,
    })
    # Active teacher→class assignment — attendance writes gate teacher/IT
    # callers via can_view_class(), which requires a teacher_assignments (or
    # class_sessions) link; homeroom_teacher_id and schedule_sessions rows
    # alone do not grant it.
    await gd_insert(db.session, "teacher_assignments", {
        "id": str(uuid.uuid4()), "school_id": wsid,
        "teacher_id": teacher_id, "class_id": class_id,
        "subject_id": subject_id, "is_active": True,
    })
    slot_resp = await client.put(
        "/independent-teacher/schedule/slot",
        headers=h,
        json={
            "day_of_week": "sun",
            "slot_number": 1,
            "class_id": class_id,
            "subject_id": subject_id,
            "expected_version": 0,
        },
    )
    assert slot_resp.status_code in (200, 201), slot_resp.text
    sched_rows = await gd_find(
        db.session, "schedule_sessions",
        {"school_id": wsid, "teacher_id": teacher_id}, limit=5,
    )
    assert sched_rows, "schedule slot did not persist"
    assert all(r["school_id"] == wsid for r in sched_rows)

    # 5) Record attendance via real route.
    att = await client.post(
        "/attendance",
        headers=h,
        json={
            "student_id": student_id,
            "class_id": class_id,
            "status": "present",
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        },
    )
    assert att.status_code in (200, 201), att.text
    att_rows = await gd_find(
        db.session, "attendance",
        {"student_id": student_id, "class_id": class_id}, limit=5,
    )
    assert att_rows and all(r["school_id"] == wsid for r in att_rows)

    # 6) Grade an assessment. Assessment authoring has no IT-only public
    #    create endpoint in v1 (the teacher slice is reused as-is per
    #    §5.5); seed the assessment row, then grade via real
    #    POST /grades/bulk.
    assessment_id = str(uuid.uuid4())
    await gd_insert(db.session, "assessments", {
        "id": assessment_id,
        "school_id": wsid,
        "tenant_id": wsid,
        "class_id": class_id,
        "subject_id": subject_id,
        "teacher_id": teacher_id,
        "name": "اختبار E2E",
        "title": "اختبار E2E",
        "type": "quiz",
        "max_score": 10,
        "weight": 1.0,
        "status": "draft",
    })
    grade = await client.post(
        "/grades/bulk",
        headers=h,
        json={
            "assessment_id": assessment_id,
            "grades": [{"student_id": student_id, "score": 9}],
        },
    )
    assert grade.status_code in (200, 201), grade.text

    # 7) Message a parent. Use the real Invite Parent route to link a
    #    parent into the workspace, then send via the cohort-bound
    #    /notifications/bulk. The invite route returns the new
    #    parent_id + parent_user_id so we don't have to re-derive them.
    invite = await client.post(
        f"/independent-teacher/students/{student_id}/invite-parent",
        headers=h,
        json={
            "full_name": "ولي أمر E2E",
            "phone": "+966500001234",
            "email": f"e2e-par-{uuid.uuid4()}@example.com",
        },
    )
    assert invite.status_code in (200, 201), invite.text

    link_row = await gd_find_one(
        db.session, "guardian_links",
        {"student_id": student_id, "tenant_id": wsid, "is_active": True},
    )
    assert link_row is not None, "invite-parent did not create guardian_link"
    parent_user_id = link_row.get("parent_ref")
    assert parent_user_id, link_row

    # Task #203 closed the prod gap: invite-parent now materialises a
    # workspace-scoped `users` row for the new parent on the new-parent
    # dedupe path, so the §5.9 #7 loop is fully real-route end-to-end.
    parent_user = await gd_find_one(
        db.session, "users",
        {"id": parent_user_id, "tenant_id": wsid},
    )
    assert parent_user is not None, (
        "invite-parent must materialise a workspace-scoped users row "
        "for the new parent (Task #203)"
    )
    assert parent_user.get("role") == "parent"

    msg = await client.post(
        "/notifications/bulk",
        headers=h,
        json={
            "title": "تنبيه E2E",
            "message": "نتيجة الاختبار جاهزة",
            "recipient_ids": [parent_user_id],
        },
    )
    assert msg.status_code == 200, msg.text
    persisted = await gd_find_one(
        db.session, "notifications",
        {"user_id": parent_user_id, "title": "تنبيه E2E"},
    )
    assert persisted is not None
    assert persisted.get("tenant_id") == wsid
