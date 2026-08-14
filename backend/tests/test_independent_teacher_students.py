"""
Independent-Teacher student creation tests
(spec: docs/specs/2026-05-12-independent-teacher-phased-spec.md §5.3, §5.6,
Task #192).

Covers the workspace-mode `POST /student-wizard/create` flow:
  * No parent payload — student lands with NULL parent_id and NULL
    pending_parent_*; no parents row is materialised.
  * Partial parent payload (only name/email, no phone) — pending_parent_*
    columns populated, parents row still NOT materialised.
  * Spoofed `school_id` / `tenant_id` — defensive tenant pin overrides.
  * Quota — 201st student returns 409 with Arabic message.
  * Cross-tenant `GET /students/{id}` — returns 404 (not 403) so the
    route never confirms cross-tenant existence.
  * Principal regression — full-school create (with parent) still works.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert, gd_find, gd_find_one, gd_count
from src.core.guards.tenant_guard import independent_workspace_id
from quotas.independent_teacher import MAX_STUDENTS


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _headers(user_id: str, role: str, tenant_id=None) -> dict:
    token = create_access_token({
        "sub": user_id,
        "role": role,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


def _mfa_headers(user_id: str, role: str, tenant_id=None) -> dict:
    """Bearer carrying a fresh passkey MFA proof — required by the IT
    auto-link sub-path (Task #817 → §5.7 step-up)."""
    token = create_access_token(
        {"sub": user_id, "role": role, "tenant_id": tenant_id},
        mfa_recent_at=_now_ts(),
        mfa_kind="webauthn",
    )
    return {"Authorization": f"Bearer {token}"}


async def _seed_active_passkey(user_id: str) -> None:
    """Tier-A users need at least one active webauthn factor for
    require_recent_mfa to clear the passkey gate."""
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


async def _mk_independent_teacher() -> dict:
    """Create an IT user and seed its synthetic workspace as a `schools`
    row so FK-style lookups resolve. Also seeds an active passkey so the
    §5.7 step-up gate on the auto-link sub-path can clear."""
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
        "name": f"IT-Workspace-{uid[:6]}",
        "code": f"IT{uid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        "school_type": "independent_teacher",
    })
    await _seed_active_passkey(uid)
    return user


def _student_payload(**overrides) -> dict:
    base = {
        "full_name": "طالب اختبار",
        "gender": "male",
        "date_of_birth": "2015-01-01",
        "education_level": "primary",
        "grade_id": "الصف الأول",
    }
    base.update(overrides)
    return base


# ----------------------------------------------------------------------
# (a) No parent payload — pending_parent_* stay NULL, no parents row.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_independent_teacher_create_student_without_parent(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)

    payload = _student_payload(parent=None)
    resp = await client.post("/student-wizard/create", json=payload, headers=h)
    assert resp.status_code == 200, resp.text
    sid = resp.json()["student"]["id"]

    row = await gd_find_one(db.session, "students", {"id": sid})
    assert row is not None
    assert row["school_id"] == wsid
    assert row.get("parent_id") is None
    assert row.get("pending_parent_name") is None
    assert row.get("pending_parent_phone") is None
    assert row.get("pending_parent_email") is None

    # No parents row should have been materialised in this workspace.
    parents_in_ws = await gd_count(db.session, "parents", {"school_id": wsid})
    assert parents_in_ws == 0


# ----------------------------------------------------------------------
# (b) Phone-only parent payload — Task #817: a usable identifier (phone)
# now AUTO-LINKS at create-time via the canonical workspace writer instead
# of landing in pending_parent_*. Matches the principal create-link flow.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_independent_teacher_create_student_phone_only_auto_links(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _mfa_headers(user["id"], user["role"], wsid)

    payload = _student_payload(parent={"phone": "+966500000001"})
    resp = await client.post("/student-wizard/create", json=payload, headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    sid = body["student"]["id"]

    row = await gd_find_one(db.session, "students", {"id": sid})
    # parent_id flipped, pending_* never set (auto-link bypasses pending).
    assert row.get("parent_id") is not None
    assert row.get("pending_parent_phone") is None
    assert row.get("pending_parent_name") is None
    assert row.get("pending_parent_email") is None
    # Denormalised display column mirrors the linked parent.
    assert row.get("parent_phone") == "+966500000001"

    # Canonical writer materialised exactly one workspace-scoped parents row.
    parents_in_ws = await gd_count(db.session, "parents", {"school_id": wsid})
    assert parents_in_ws == 1
    parent_row = await gd_find_one(db.session, "parents", {"id": row["parent_id"]})
    assert parent_row["school_id"] == wsid
    assert parent_row["phone"] == "+966500000001"

    # guardian_links row tagged with the workspace tenant_id.
    links = await gd_find(db.session, "guardian_links",
                          {"student_id": sid, "is_active": True})
    assert len(links) == 1
    assert links[0]["tenant_id"] == wsid
    assert links[0]["parent_id"] == row["parent_id"]

    # Audit trail identical to the invite-parent transition.
    audits = await gd_find(db.session, "audit_logs", {
        "action": "INDEPENDENT_TEACHER_PARENT_LINK",
        "entity_id": sid,
    })
    assert len(audits) == 1
    # First parent in the workspace — no pre-existing row to dedupe against.
    assert audits[0]["details"]["matched_by"] == "new"
    assert body["parent"]["matched_by"] == "new"
    assert body["parent"]["is_new"] is True


# ----------------------------------------------------------------------
# (b2) Name + email parent payload — Task #817: email is a usable
# identifier, so this AUTO-LINKS too (matched_by == "email").
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_independent_teacher_create_student_name_email_auto_links(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _mfa_headers(user["id"], user["role"], wsid)

    payload = _student_payload(parent={
        "full_name": "أحمد ولي الأمر",
        "email": "guardian@example.com",
    })
    resp = await client.post("/student-wizard/create", json=payload, headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    sid = body["student"]["id"]

    row = await gd_find_one(db.session, "students", {"id": sid})
    assert row.get("parent_id") is not None
    assert row.get("pending_parent_name") is None
    assert row.get("pending_parent_email") is None
    assert row.get("parent_name") == "أحمد ولي الأمر"
    assert row.get("parent_email") == "guardian@example.com"

    parents_in_ws = await gd_count(db.session, "parents", {"school_id": wsid})
    assert parents_in_ws == 1
    parent_row = await gd_find_one(db.session, "parents", {"id": row["parent_id"]})
    assert parent_row["email"] == "guardian@example.com"
    assert parent_row["full_name"] == "أحمد ولي الأمر"
    # First parent in the workspace — created fresh, no dedupe match.
    assert body["parent"]["matched_by"] == "new"
    assert body["parent"]["is_new"] is True


# ----------------------------------------------------------------------
# (b3) Name-ONLY parent payload (no usable identifier) — Task #817:
# preserves the §5.6 pending behaviour. No parents row, no MFA needed.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_independent_teacher_create_student_name_only_writes_pending(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)

    payload = _student_payload(parent={"full_name": "ولي بلا تواصل"})
    resp = await client.post("/student-wizard/create", json=payload, headers=h)
    assert resp.status_code == 200, resp.text
    sid = resp.json()["student"]["id"]

    row = await gd_find_one(db.session, "students", {"id": sid})
    assert row.get("parent_id") is None
    assert row.get("pending_parent_name") == "ولي بلا تواصل"
    assert row.get("pending_parent_phone") is None
    assert row.get("pending_parent_email") is None

    parents_in_ws = await gd_count(db.session, "parents", {"school_id": wsid})
    assert parents_in_ws == 0, "Name-only parent must NOT materialise a parents row"


# ----------------------------------------------------------------------
# (b4) Auto-link sub-path requires fresh MFA (§5.7). Without a recent
# passkey proof the create returns the 403 step-up envelope and writes
# NOTHING — neither the student nor a parents row is persisted.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_independent_teacher_auto_link_requires_recent_mfa(client, monkeypatch):
    # This env runs with the demo kill switch (MFA_ENFORCEMENT_DISABLED=true).
    # The auto-link MFA gate only fires when enforcement is on, so force it
    # on for this negative test. is_enforcement_disabled() reads the env
    # fresh on every call, so this takes effect immediately.
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "false")
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)  # no mfa_recent_at

    payload = _student_payload(parent={"phone": "+966500000077"})
    resp = await client.post("/student-wizard/create", json=payload, headers=h)
    assert resp.status_code == 403, resp.text
    body = resp.json()
    code = (body.get("error") or {}).get("code") or (
        body.get("detail") if isinstance(body.get("detail"), dict) else {}
    ).get("code")
    assert code in {"MFA_STEPUP_REQUIRED", "MFA_PASSKEY_REQUIRED", "MFA_RESTORE_REQUIRED"}

    # The guard runs BEFORE any write — no student, no parent persisted.
    assert await gd_count(db.session, "students", {"school_id": wsid}) == 0
    assert await gd_count(db.session, "parents", {"school_id": wsid}) == 0


# ----------------------------------------------------------------------
# (b5) national_id dedupe — a second student created with the SAME
# national_id links to the EXISTING parent (no duplicate parents row).
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_independent_teacher_auto_link_dedupes_by_national_id(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _mfa_headers(user["id"], user["role"], wsid)

    nid = "1234567890"
    p1 = _student_payload(full_name="طالب أول", parent={
        "full_name": "والد مشترك", "national_id": nid, "phone": "+966500000010",
    })
    r1 = await client.post("/student-wizard/create", json=p1, headers=h)
    assert r1.status_code == 200, r1.text
    parent_id_1 = r1.json()["parent"]["id"]

    p2 = _student_payload(full_name="طالب ثانٍ", parent={
        "full_name": "والد مشترك", "national_id": nid,
    })
    r2 = await client.post("/student-wizard/create", json=p2, headers=h)
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["parent"]["id"] == parent_id_1
    assert body2["parent"]["matched_by"] == "national_id"

    # Only ONE parents row across both linked students.
    assert await gd_count(db.session, "parents", {"school_id": wsid}) == 1


# ----------------------------------------------------------------------
# (c) Defensive tenant pin — spoofed school_id ignored.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_independent_teacher_create_student_ignores_spoofed_school_id(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)

    foreign = "school_someone_else"
    payload = _student_payload(
        parent=None,
        school_id=foreign,
        tenant_id=foreign,
    )
    resp = await client.post("/student-wizard/create", json=payload, headers=h)
    assert resp.status_code == 200, resp.text
    sid = resp.json()["student"]["id"]

    row = await gd_find_one(db.session, "students", {"id": sid})
    assert row["school_id"] == wsid
    assert row["school_id"] != foreign
    foreign_count = await gd_count(db.session, "students", {"school_id": foreign})
    assert foreign_count == 0


# ----------------------------------------------------------------------
# (d) Quota — 201st student blocked with Arabic 409.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_independent_teacher_create_student_quota_boundary(client):
    user = await _mk_independent_teacher()
    wsid = independent_workspace_id(user)
    h = _headers(user["id"], user["role"], wsid)

    # Pre-seed MAX_STUDENTS rows directly to keep the test fast.
    for _ in range(MAX_STUDENTS):
        await gd_insert(db.session, "students", {
            "id": str(uuid.uuid4()),
            "school_id": wsid,
            "full_name": "x",
            "is_active": True,
        })

    resp = await client.post("/student-wizard/create",
                             json=_student_payload(parent=None), headers=h)
    assert resp.status_code == 409, resp.text
    body = resp.json()
    msg = (body.get("error") or {}).get("message") or body.get("detail") or ""
    assert "الحد الأقصى" in msg


# ----------------------------------------------------------------------
# (e) Cross-tenant GET /students/{id} returns 404 (NOT 403).
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_independent_teacher_get_student_cross_tenant_returns_404(client):
    user_a = await _mk_independent_teacher()
    user_b = await _mk_independent_teacher()
    wsid_a = independent_workspace_id(user_a)
    wsid_b = independent_workspace_id(user_b)
    h_a = _headers(user_a["id"], user_a["role"], wsid_a)
    h_b = _headers(user_b["id"], user_b["role"], wsid_b)

    # IT-A creates a student.
    resp = await client.post("/student-wizard/create",
                             json=_student_payload(parent=None), headers=h_a)
    assert resp.status_code == 200, resp.text
    sid = resp.json()["student"]["id"]

    # Owner can read.
    resp_owner = await client.get(f"/students/{sid}", headers=h_a)
    assert resp_owner.status_code == 200, resp_owner.text

    # Foreign IT MUST get a clean 404 (not 200, not 403).
    resp_foreign = await client.get(f"/students/{sid}", headers=h_b)
    assert resp_foreign.status_code == 404, resp_foreign.text
    body = resp_foreign.json()
    msg = (body.get("error") or {}).get("message") or body.get("detail") or ""
    assert "غير موجود" in msg


# ----------------------------------------------------------------------
# (f) Principal regression — full-school create still requires parent.
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_principal_create_student_without_parent_rejected(client):
    """The defensive IT-only optional-parent path must NOT loosen the
    school-admin contract: omitting `parent` for a principal still 422s."""
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await gd_insert(db.session, "schools", {
        "id": school_id,
        "name": "Test School",
        "code": school_id,
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": school_id,
        "email": f"p-{uid}@t.test",
        "full_name": "Principal",
        "is_active": True,
        "password_hash": "x",
    })
    h = _headers(uid, UserRole.SCHOOL_PRINCIPAL.value, school_id)

    resp = await client.post("/student-wizard/create",
                             json=_student_payload(parent=None), headers=h)
    assert resp.status_code == 422, resp.text
    body = resp.json()
    msg = (body.get("error") or {}).get("message") or body.get("detail") or ""
    assert "ولي الأمر" in msg


# ----------------------------------------------------------------------
# (g) Principal regression — full-school create WITH parent succeeds and
# materialises a real parents row (workspace-mode gate must NOT bleed
# into the school-admin path).
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_principal_create_student_with_parent_succeeds(client):
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await gd_insert(db.session, "schools", {
        "id": school_id,
        "name": "Test School",
        "code": school_id,
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": school_id,
        "email": f"p2-{uid}@t.test",
        "full_name": "Principal2",
        "is_active": True,
        "password_hash": "x",
    })
    h = _headers(uid, UserRole.SCHOOL_PRINCIPAL.value, school_id)

    payload = _student_payload(parent={
        "full_name": "محمد ولي الأمر",
        "phone": "+966500000099",
        "relationship": "father",
    })
    resp = await client.post("/student-wizard/create", json=payload, headers=h)
    assert resp.status_code == 200, resp.text
    sid = resp.json()["student"]["id"]

    row = await gd_find_one(db.session, "students", {"id": sid})
    assert row["school_id"] == school_id
    # Standard school-admin path materialises a parents row + parent_id link.
    assert row.get("parent_id") is not None
    parents_in_school = await gd_count(db.session, "parents", {"school_id": school_id})
    assert parents_in_school == 1
    # Pending columns must remain unused on the standard path.
    assert row.get("pending_parent_name") is None
    assert row.get("pending_parent_phone") is None
