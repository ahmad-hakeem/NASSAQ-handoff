"""IT bulk-import extensions (Task #278).

Covers /classes/bulk, /subjects/bulk, and /schedule/duplicate-week:
  * parse rejects forbidden cross-tenant columns (422 + Arabic)
  * commit MFA step-up envelope (403 without recent MFA)
  * commit happy paths pin to itw_{user_id} and bump imports_today
  * classes commit succeeds beyond the old cap (classes are unlimited)
  * subjects parse refuses >50 rows (413)
  * duplicate-week validates the 7-day gap, copies rows, skips
    pre-existing target slots, and pins school_id to the workspace
  * cross-workspace school_id payload smuggling stays no-op
"""
from __future__ import annotations

import io
import uuid
from datetime import date, datetime, timezone

import pytest

from auth_scope import independent_workspace_id
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_count, gd_find, gd_find_one, gd_insert, gd_update_one


def _headers(uid: str, role: str, tenant_id=None, *, mfa_recent_at=None) -> dict:
    token = create_access_token(
        {"sub": uid, "role": role, "tenant_id": tenant_id},
        mfa_recent_at=mfa_recent_at,
        mfa_kind="webauthn" if mfa_recent_at else None,
    )
    return {"Authorization": f"Bearer {token}"}


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


async def _seed_passkey(user_id: str) -> None:
    await gd_insert(db.session, "mfa_factors", {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "kind": "webauthn",
        "is_active": True,
        "is_primary": True,
        "webauthn_credential_id": uuid.uuid4().bytes,
        "webauthn_public_key": b"\x00",
        "webauthn_sign_count": 0,
    })


async def _mk_it_workspace() -> dict:
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
    await gd_insert(db.session, "schools", {
        "id": wsid,
        "name": f"IT-WS-{uid[:6]}",
        "code": f"IT{uid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        "school_type": "independent_teacher_workspace",
    })
    await _seed_passkey(uid)
    user["tenant_id"] = wsid
    return user


def _csv(headers: list[str], *rows: tuple[str, ...]) -> bytes:
    body = ",".join(headers) + "\n" + "\n".join(",".join(r) for r in rows)
    return ("\ufeff" + body).encode("utf-8")


def _err_message(body: dict) -> str:
    """Extract a human-readable error message from any of the envelopes
    the backend may return (raw FastAPI `detail`, the wrapped `error`
    envelope, or pydantic 422 `detail` lists)."""
    if not isinstance(body, dict):
        return ""
    detail = body.get("detail")
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        return str(detail[0].get("msg") or detail[0])
    err = body.get("error") or {}
    if isinstance(err, dict):
        msg = err.get("message")
        if isinstance(msg, str):
            return msg
        nested = err.get("detail")
        if isinstance(nested, str):
            return nested
    return ""


def _err_code(body: dict) -> str | None:
    """Extract the structured error code from the MFA step-up envelope."""
    if not isinstance(body, dict):
        return None
    detail = body.get("detail")
    if isinstance(detail, dict):
        return detail.get("code")
    err = body.get("error") or {}
    if isinstance(err, dict):
        nested = err.get("detail")
        if isinstance(nested, dict):
            return nested.get("code")
        return err.get("code")
    return None


# ---------------- Classes ----------------

@pytest.mark.asyncio
async def test_classes_parse_rejects_forbidden_school_id_column(client):
    user = await _mk_it_workspace()
    h = _headers(user["id"], user["role"], user["tenant_id"])
    payload = _csv(["اسم الفصل", "school_id"], ("الفصل أ", "another_school"))
    resp = await client.post(
        "/independent-teacher/classes/bulk/parse",
        files={"file": ("c.csv", io.BytesIO(payload), "text/csv")},
        headers=h,
    )
    assert resp.status_code == 422
    assert "مدرسة" in _err_message(resp.json())


@pytest.mark.asyncio
async def test_classes_parse_returns_diagnostics(client):
    user = await _mk_it_workspace()
    h = _headers(user["id"], user["role"], user["tenant_id"])
    payload = _csv(
        ["اسم الفصل", "المرحلة"],
        ("حلقة الأول", "الصف الأول"),
        ("", "الصف الثاني"),  # invalid — name required
    )
    resp = await client.post(
        "/independent-teacher/classes/bulk/parse",
        files={"file": ("c.csv", io.BytesIO(payload), "text/csv")},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_rows"] == 2
    assert body["valid_count"] == 1
    assert body["invalid_count"] == 1
    assert body["quota"]["max_classes"] is None
    assert body["projected_classes"] == 1


@pytest.mark.asyncio
async def test_classes_commit_requires_recent_mfa_403(client):
    user = await _mk_it_workspace()
    h = _headers(user["id"], user["role"], user["tenant_id"])  # no mfa_recent_at
    rows = [{"row_number": 1, "name": "حلقة", "is_valid": True, "errors": []}]
    resp = await client.post(
        "/independent-teacher/classes/bulk/commit",
        json={"rows": rows}, headers=h,
    )
    assert resp.status_code == 403
    assert _err_code(resp.json()) in {
        "MFA_STEPUP_REQUIRED", "MFA_PASSKEY_REQUIRED", "MFA_RESTORE_REQUIRED",
    }


@pytest.mark.asyncio
async def test_classes_commit_happy_path_pins_workspace_and_bumps_counter(client):
    user = await _mk_it_workspace()
    wsid = user["tenant_id"]
    h = _headers(user["id"], user["role"], wsid, mfa_recent_at=_now_ts())
    rows = [
        {"row_number": 1, "name": "حلقة الأول", "grade_level": "الصف الأول",
         "default_subject": "القرآن", "is_valid": True, "errors": []},
        {"row_number": 2, "name": "حلقة الثاني", "is_valid": True, "errors": []},
    ]
    resp = await client.post(
        "/independent-teacher/classes/bulk/commit",
        json={"rows": rows}, headers=h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["inserted"] == 2
    persisted = await gd_find(db.session, "classes", {"school_id": wsid})
    assert len(persisted) == 2
    assert all(c["school_id"] == wsid for c in persisted)
    quota_row = await gd_find_one(
        db.session, "workspace_quota", {"workspace_school_id": wsid},
    )
    assert quota_row["imports_today"] == 1


@pytest.mark.asyncio
async def test_classes_commit_beyond_old_cap_succeeds(client):
    """Classes are unlimited for IT workspaces: committing rows that would
    have exceeded the old v1 cap now succeeds and inserts them all."""
    user = await _mk_it_workspace()
    wsid = user["tenant_id"]
    # pre-seed 4 existing classes (old cap was 5)
    for i in range(4):
        await gd_insert(db.session, "classes", {
            "id": str(uuid.uuid4()), "school_id": wsid,
            "name": f"existing-{i}", "is_active": True,
        })
    h = _headers(user["id"], user["role"], wsid, mfa_recent_at=_now_ts())
    rows = [
        {"row_number": 1, "name": "ا", "is_valid": True, "errors": []},
        {"row_number": 2, "name": "ب", "is_valid": True, "errors": []},
    ]
    resp = await client.post(
        "/independent-teacher/classes/bulk/commit",
        json={"rows": rows}, headers=h,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["inserted"] == 2
    # Both rows inserted on top of the 4 pre-seeded → 6 total (beyond old cap).
    assert await gd_count(db.session, "classes", {"school_id": wsid}) == 6


@pytest.mark.asyncio
async def test_classes_commit_rejects_extra_id_columns_in_payload_row(client):
    """Cross-tenant smuggling guard: pydantic ``extra='forbid'`` on the
    parsed-row models causes any non-whitelisted key (school_id /
    tenant_id / class_id / etc.) to fail validation with 422 rather
    than being silently dropped. Belt-and-suspenders complement to the
    parse-time CSV header check."""
    user = await _mk_it_workspace()
    wsid = user["tenant_id"]
    h = _headers(user["id"], user["role"], wsid, mfa_recent_at=_now_ts())
    foreign = "school_someone_else"
    rows = [{
        "row_number": 1, "name": "حلقة", "is_valid": True, "errors": [],
        "school_id": foreign, "tenant_id": foreign,
    }]
    resp = await client.post(
        "/independent-teacher/classes/bulk/commit",
        json={"rows": rows}, headers=h,
    )
    assert resp.status_code == 422, resp.text
    # Arabic safe message contract — must be the same _MSG_CROSS_TENANT
    # string the parse-time CSV-header guard uses, NOT a raw pydantic
    # validation blob.
    msg = _err_message(resp.json())
    assert "مدرسة" in msg or "حسابك" in msg, msg
    # No partial write happened in either tenant.
    assert await gd_find(db.session, "classes", {"school_id": foreign}) == []
    assert await gd_find(db.session, "classes", {"school_id": wsid}) == []


# ---------------- Subjects ----------------

@pytest.mark.asyncio
async def test_subjects_parse_too_many_rows_413(client):
    user = await _mk_it_workspace()
    h = _headers(user["id"], user["role"], user["tenant_id"])
    rows = tuple((f"مادة-{i}",) for i in range(51))
    payload = _csv(["اسم المادة"], *rows)
    resp = await client.post(
        "/independent-teacher/subjects/bulk/parse",
        files={"file": ("s.csv", io.BytesIO(payload), "text/csv")},
        headers=h,
    )
    assert resp.status_code == 413


@pytest.mark.asyncio
async def test_subjects_commit_happy_path(client):
    user = await _mk_it_workspace()
    wsid = user["tenant_id"]
    h = _headers(user["id"], user["role"], wsid, mfa_recent_at=_now_ts())
    rows = [
        {"row_number": 1, "name": "القرآن الكريم", "code": "QURAN",
         "is_valid": True, "errors": []},
        {"row_number": 2, "name": "التجويد", "is_valid": True, "errors": []},
    ]
    resp = await client.post(
        "/independent-teacher/subjects/bulk/commit",
        json={"rows": rows}, headers=h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["inserted"] == 2
    persisted = await gd_find(db.session, "subjects", {"school_id": wsid})
    names = {s.get("name") for s in persisted}
    assert names == {"القرآن الكريم", "التجويد"}
    assert all(s["school_id"] == wsid for s in persisted)


# ---------------- Duplicate week ----------------

@pytest.mark.asyncio
async def test_duplicate_week_rejects_bad_gap(client):
    user = await _mk_it_workspace()
    wsid = user["tenant_id"]
    h = _headers(user["id"], user["role"], wsid, mfa_recent_at=_now_ts())
    resp = await client.post(
        "/independent-teacher/schedule/duplicate-week",
        json={"from_week_start": "2026-05-10", "to_week_start": "2026-05-20"},
        headers=h,
    )
    assert resp.status_code == 422
    msg = _err_message(resp.json())
    assert "سبعة" in msg or "أسبوع" in msg


@pytest.mark.asyncio
async def test_duplicate_week_copies_rows_and_skips_existing(client):
    user = await _mk_it_workspace()
    wsid = user["tenant_id"]
    h = _headers(user["id"], user["role"], wsid, mfa_recent_at=_now_ts())

    # Seed 3 source weekly slots (any non-target schedule_id).
    base = {"school_id": wsid, "schedule_id": f"itw_schedule_{wsid}",
            "status": "scheduled"}
    src_rows = [
        {"id": str(uuid.uuid4()), **base, "day_of_week": "sun",
         "slot_number": 1, "subject_name": "S1"},
        {"id": str(uuid.uuid4()), **base, "day_of_week": "mon",
         "slot_number": 2, "subject_name": "S2"},
        {"id": str(uuid.uuid4()), **base, "day_of_week": "tue",
         "slot_number": 3, "subject_name": "S3"},
    ]
    for r in src_rows:
        await gd_insert(db.session, "schedule_sessions", r)

    target_sched = f"itw_schedule_{wsid}_w_2026-05-17"
    # One target slot already exists → must be skipped.
    await gd_insert(db.session, "schedule_sessions", {
        "id": str(uuid.uuid4()), "school_id": wsid,
        "schedule_id": target_sched, "day_of_week": "sun",
        "slot_number": 1, "status": "scheduled",
    })

    resp = await client.post(
        "/independent-teacher/schedule/duplicate-week",
        json={"from_week_start": "2026-05-10", "to_week_start": "2026-05-17"},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 2
    assert body["skipped"] == 1

    target_rows = await gd_find(
        db.session, "schedule_sessions",
        {"school_id": wsid, "schedule_id": target_sched},
    )
    assert len(target_rows) == 3  # 1 pre-existing + 2 new
    assert all(r["school_id"] == wsid for r in target_rows)


@pytest.mark.asyncio
async def test_duplicate_week_no_source_rows_422(client):
    user = await _mk_it_workspace()
    wsid = user["tenant_id"]
    h = _headers(user["id"], user["role"], wsid, mfa_recent_at=_now_ts())
    resp = await client.post(
        "/independent-teacher/schedule/duplicate-week",
        json={"from_week_start": "2026-05-10", "to_week_start": "2026-05-17"},
        headers=h,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_week_requires_recent_mfa_403(client):
    user = await _mk_it_workspace()
    wsid = user["tenant_id"]
    h = _headers(user["id"], user["role"], wsid)  # no mfa
    resp = await client.post(
        "/independent-teacher/schedule/duplicate-week",
        json={"from_week_start": "2026-05-10", "to_week_start": "2026-05-17"},
        headers=h,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_duplicate_week_filters_source_rows_by_from_week(client):
    """Source-week scoping (review fix): only rows tagged for the
    requested ``from_week_start`` (week-tagged ``schedule_id`` OR a
    matching ``start_time``) — plus the recurring/template rows — are
    eligible to be copied. Rows tagged for some OTHER prior week must
    NOT bleed into the new week."""
    user = await _mk_it_workspace()
    wsid = user["tenant_id"]
    h = _headers(user["id"], user["role"], wsid, mfa_recent_at=_now_ts())

    # Source week 2026-05-10 — these MUST be copied.
    src_sched = f"itw_schedule_{wsid}_w_2026-05-10"
    await gd_insert(db.session, "schedule_sessions", {
        "id": str(uuid.uuid4()), "school_id": wsid,
        "schedule_id": src_sched, "day_of_week": "sun",
        "slot_number": 1, "subject_name": "FROM-SRC",
        "status": "scheduled", "start_time": "2026-05-10",
    })
    # An older week 2026-05-03 — MUST be ignored (would otherwise leak
    # into the new week under the prior unfiltered behaviour).
    await gd_insert(db.session, "schedule_sessions", {
        "id": str(uuid.uuid4()), "school_id": wsid,
        "schedule_id": f"itw_schedule_{wsid}_w_2026-05-03",
        "day_of_week": "mon", "slot_number": 5,
        "subject_name": "OLD-WEEK-DO-NOT-COPY",
        "status": "scheduled", "start_time": "2026-05-03",
    })
    resp = await client.post(
        "/independent-teacher/schedule/duplicate-week",
        json={"from_week_start": "2026-05-10",
              "to_week_start": "2026-05-17"},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created"] == 1
    target_sched = f"itw_schedule_{wsid}_w_2026-05-17"
    target_rows = await gd_find(
        db.session, "schedule_sessions",
        {"school_id": wsid, "schedule_id": target_sched},
    )
    assert len(target_rows) == 1
    assert target_rows[0].get("subject_name") == "FROM-SRC"


@pytest.mark.asyncio
async def test_duplicate_week_dry_run_returns_preview_without_writing(client):
    """Preview mode (review fix): ``dry_run=True`` returns the per-slot
    plan (will_create / skipped) without inserting any rows or bumping
    the daily import counter — powers the FE's pre-confirmation
    conflict report."""
    user = await _mk_it_workspace()
    wsid = user["tenant_id"]
    h = _headers(user["id"], user["role"], wsid, mfa_recent_at=_now_ts())

    base = f"itw_schedule_{wsid}"
    for d, s, sn in [("sun", 1, "S1"), ("mon", 2, "S2")]:
        await gd_insert(db.session, "schedule_sessions", {
            "id": str(uuid.uuid4()), "school_id": wsid,
            "schedule_id": base, "day_of_week": d, "slot_number": s,
            "subject_name": sn, "status": "scheduled",
        })
    target_sched = f"itw_schedule_{wsid}_w_2026-05-17"
    await gd_insert(db.session, "schedule_sessions", {
        "id": str(uuid.uuid4()), "school_id": wsid,
        "schedule_id": target_sched, "day_of_week": "sun",
        "slot_number": 1, "status": "scheduled",
    })

    resp = await client.post(
        "/independent-teacher/schedule/duplicate-week",
        json={"from_week_start": "2026-05-10",
              "to_week_start": "2026-05-17", "dry_run": True},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["dry_run"] is True
    assert body["created"] == 1
    assert body["skipped"] == 1
    slots = body["slots"]
    assert len(slots) == 2
    by_key = {(s["day_of_week"], s["slot_number"]): s for s in slots}
    assert by_key[("sun", 1)]["will_create"] is False
    assert by_key[("mon", 2)]["will_create"] is True

    # Side-effect-free: only the pre-existing 1 target row remains.
    assert await gd_count(
        db.session, "schedule_sessions",
        {"school_id": wsid, "schedule_id": target_sched},
    ) == 1
    quota = await gd_find_one(
        db.session, "workspace_quota", {"workspace_school_id": wsid},
    )
    assert int((quota or {}).get("imports_today") or 0) == 0


@pytest.mark.asyncio
async def test_duplicate_week_handles_more_than_500_rows(client):
    """Pagination correctness (review fix): when a workspace's
    schedule_sessions table is larger than the per-page fetch size
    (500), the duplicate-week endpoint MUST still see every relevant
    row. We seed 600 source rows on the recurring template and 600
    pre-existing target rows; expected outcome is 0 created (all
    conflict-skipped) and 600 skipped — proving both source selection
    and target conflict detection are fully paginated."""
    user = await _mk_it_workspace()
    wsid = user["tenant_id"]
    h = _headers(user["id"], user["role"], wsid, mfa_recent_at=_now_ts())

    base = f"itw_schedule_{wsid}"
    target_sched = f"itw_schedule_{wsid}_w_2026-05-17"
    days = ["sun", "mon", "tue", "wed", "thu"]
    rows = []
    for i in range(600):
        d = days[i % len(days)]
        # slot_number must be unique per (day) to make 600 distinct
        # (day, slot) pairs; pack ~120 slots per day.
        s = (i // len(days)) + 1
        rows.append((d, s))
        await gd_insert(db.session, "schedule_sessions", {
            "id": str(uuid.uuid4()), "school_id": wsid,
            "schedule_id": base, "day_of_week": d, "slot_number": s,
            "subject_name": f"S{i}", "status": "scheduled",
        })
        await gd_insert(db.session, "schedule_sessions", {
            "id": str(uuid.uuid4()), "school_id": wsid,
            "schedule_id": target_sched, "day_of_week": d,
            "slot_number": s, "status": "scheduled",
        })

    resp = await client.post(
        "/independent-teacher/schedule/duplicate-week",
        json={"from_week_start": "2026-05-10",
              "to_week_start": "2026-05-17", "dry_run": True},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Every one of the 600 source slots conflicts with a pre-existing
    # target slot → all skipped, none created. If pagination were
    # broken on either side, these counts would be < 600.
    assert body["created"] == 0
    assert body["skipped"] == 600
    assert len(body["slots"]) == 600


@pytest.mark.asyncio
async def test_classes_commit_blocked_when_daily_import_cap_reached(client):
    user = await _mk_it_workspace()
    wsid = user["tenant_id"]
    today = date.today().isoformat()
    # Lazy-seed quota row by hitting parse first.
    h = _headers(user["id"], user["role"], wsid)
    payload = _csv(["اسم الفصل"], ("ا",))
    await client.post(
        "/independent-teacher/classes/bulk/parse",
        files={"file": ("c.csv", io.BytesIO(payload), "text/csv")},
        headers=h,
    )
    # Push counter to the cap.
    await gd_update_one(
        db.session, "workspace_quota",
        {"workspace_school_id": wsid},
        {"imports_today": 5, "imports_today_date": today},
    )
    h2 = _headers(user["id"], user["role"], wsid, mfa_recent_at=_now_ts())
    rows = [{"row_number": 1, "name": "ا", "is_valid": True, "errors": []}]
    resp = await client.post(
        "/independent-teacher/classes/bulk/commit",
        json={"rows": rows}, headers=h2,
    )
    assert resp.status_code == 429
