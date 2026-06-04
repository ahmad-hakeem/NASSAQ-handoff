"""Direct unit tests for the shared IT parent-link writer
(``backend/utils/it_parent_link.py``).

This module is the ONE canonical writer behind BOTH the IT invite-parent
flow and the IT create-student auto-link (Task #817). It was previously
exercised only indirectly through route tests; these tests call the
helper directly so the frozen behaviour is locked down independently of
either caller:

  * The frozen four-step dedupe order (national_id → phone+email →
    phone → email), first-match-wins, scoped to the workspace.
  * The no-match (create) branch.
  * Conservative NULL-only fill — established values are never
    overwritten.
  * ``guardian_links.tenant_id == workspace_id``.
  * The ``INDEPENDENT_TEACHER_PARENT_LINK`` audit entry.
  * The workspace ``users`` row materialise on every new-parent path
    (sentinel password + @invite.nassaq.invalid fallback).

Per the helper's contract, every call is wrapped in a caller-owned
SAVEPOINT (``db.session.begin_nested()``).
"""
from __future__ import annotations

import uuid

import pytest

from auth_scope import independent_workspace_id
from dependencies import db, UserRole
from engines.sql_utils import gd_find, gd_find_one, gd_insert
from utils.it_parent_link import (
    _conservative_fill,
    dedupe_workspace_parent,
    link_workspace_parent_to_student,
)


# ----------------------------------------------------------------------
# Fixtures / helpers
# ----------------------------------------------------------------------
async def _mk_workspace() -> dict:
    """Insert an IT actor user + workspace school. Returns the actor."""
    uid = str(uuid.uuid4())
    actor = {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": f"it-{uid}@t.test",
        "full_name": f"IT-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", actor)
    wsid = independent_workspace_id(actor)
    actor["tenant_id"] = wsid
    await gd_insert(db.session, "schools", {
        "id": wsid,
        "name": f"IT-Workspace-{uid[:6]}",
        "code": f"IT{uid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        "school_type": "independent_teacher",
    })
    return actor


async def _mk_pending_student(wsid: str, **pending) -> dict:
    sid = str(uuid.uuid4())
    doc = {
        "id": sid,
        "school_id": wsid,
        "tenant_id": wsid,
        "full_name": "طالب",
        "is_active": True,
    }
    doc.update(pending)
    await gd_insert(db.session, "students", doc)
    return doc


async def _seed_parent(wsid: str, **fields) -> str:
    pid = str(uuid.uuid4())
    doc = {"id": pid, "school_id": wsid, "is_active": True, "full_name": "ولي"}
    doc.update(fields)
    await gd_insert(db.session, "parents", doc)
    return pid


async def _link(actor: dict, student: dict, *, wsid: str, **kw):
    """Invoke the writer inside a caller-owned SAVEPOINT, as the
    helper's contract requires."""
    params = dict(
        full_name=None,
        phone=None,
        email=None,
        national_id=None,
        relationship=None,
    )
    params.update(kw)
    async with db.session.begin_nested():
        return await link_workspace_parent_to_student(
            db.session,
            student=student,
            workspace_id=wsid,
            school_id=wsid,
            actor=actor,
            **params,
        )


# ======================================================================
# A. _conservative_fill — pure function, no DB
# ======================================================================
def test_conservative_fill_fills_only_null_columns():
    existing = {
        "full_name": "اسم موجود",     # set → must NOT be overwritten
        "phone": None,                 # NULL → fill
        "email": "old@example.com",   # set → must NOT be overwritten
        "national_id": None,           # NULL → fill
    }
    updates = _conservative_fill(
        existing,
        full_name="اسم جديد",
        phone="+966500000000",
        email="new@example.com",
        national_id="1234567890",
    )
    assert updates["phone"] == "+966500000000"
    assert updates["national_id"] == "1234567890"
    assert "full_name" not in updates
    assert "email" not in updates
    assert "updated_at" in updates


def test_conservative_fill_empty_when_nothing_to_fill():
    existing = {
        "full_name": "اسم",
        "phone": "+966500111111",
        "email": "a@b.test",
        "national_id": "1010101010",
    }
    updates = _conservative_fill(
        existing,
        full_name="آخر",
        phone="+966509999999",
        email="z@z.test",
        national_id="9999999999",
    )
    assert updates == {}


def test_conservative_fill_no_updated_at_when_no_changes():
    # Falsy incoming values can never fill an existing NULL.
    existing = {"full_name": None, "phone": None, "email": None, "national_id": None}
    updates = _conservative_fill(
        existing, full_name=None, phone=None, email=None, national_id=None,
    )
    assert updates == {}


# ======================================================================
# B. dedupe_workspace_parent — frozen order, workspace-scoped
# ======================================================================
@pytest.mark.asyncio
async def test_dedupe_matches_national_id():
    actor = await _mk_workspace()
    wsid = actor["tenant_id"]
    pid = await _seed_parent(wsid, national_id="1234567890", full_name="أب")

    row, matched_by = await dedupe_workspace_parent(
        db.session, national_id="1234567890", phone=None, email=None,
        workspace_id=wsid,
    )
    assert matched_by == "national_id"
    assert row["id"] == pid


@pytest.mark.asyncio
async def test_dedupe_matches_phone_email_pair():
    actor = await _mk_workspace()
    wsid = actor["tenant_id"]
    pid = await _seed_parent(wsid, phone="+966500222222", email="mom@example.com")

    row, matched_by = await dedupe_workspace_parent(
        db.session, national_id=None, phone="+966500222222",
        email="mom@example.com", workspace_id=wsid,
    )
    assert matched_by == "phone_email"
    assert row["id"] == pid


@pytest.mark.asyncio
async def test_dedupe_matches_phone_alone_only_when_email_absent():
    actor = await _mk_workspace()
    wsid = actor["tenant_id"]
    pid = await _seed_parent(wsid, phone="+966500333333")

    row, matched_by = await dedupe_workspace_parent(
        db.session, national_id=None, phone="+966500333333", email=None,
        workspace_id=wsid,
    )
    assert matched_by == "phone"
    assert row["id"] == pid


@pytest.mark.asyncio
async def test_dedupe_matches_email_alone_only_when_phone_absent():
    actor = await _mk_workspace()
    wsid = actor["tenant_id"]
    pid = await _seed_parent(wsid, email="guardian@example.com")

    row, matched_by = await dedupe_workspace_parent(
        db.session, national_id=None, phone=None,
        email="guardian@example.com", workspace_id=wsid,
    )
    assert matched_by == "email"
    assert row["id"] == pid


@pytest.mark.asyncio
async def test_dedupe_no_match_returns_new():
    actor = await _mk_workspace()
    wsid = actor["tenant_id"]

    row, matched_by = await dedupe_workspace_parent(
        db.session, national_id="0000000000", phone="+966500000000",
        email="nobody@example.com", workspace_id=wsid,
    )
    assert row is None
    assert matched_by == "new"


@pytest.mark.asyncio
async def test_dedupe_national_id_wins_over_phone():
    """First match wins: national_id (step 1) beats a phone (step 3)
    match on a different row."""
    actor = await _mk_workspace()
    wsid = actor["tenant_id"]
    nat_pid = await _seed_parent(wsid, national_id="1111111111")
    await _seed_parent(wsid, phone="+966500444444")

    row, matched_by = await dedupe_workspace_parent(
        db.session, national_id="1111111111", phone="+966500444444",
        email=None, workspace_id=wsid,
    )
    assert matched_by == "national_id"
    assert row["id"] == nat_pid


@pytest.mark.asyncio
async def test_dedupe_phone_alone_skipped_when_email_present():
    """Step 3 (phone alone) only fires when email is absent. With both
    phone+email present and no exact-pair match, dedupe falls through to
    'new' rather than reusing a phone-only row."""
    actor = await _mk_workspace()
    wsid = actor["tenant_id"]
    await _seed_parent(wsid, phone="+966500555555")  # phone only, no email

    row, matched_by = await dedupe_workspace_parent(
        db.session, national_id=None, phone="+966500555555",
        email="different@example.com", workspace_id=wsid,
    )
    assert row is None
    assert matched_by == "new"


@pytest.mark.asyncio
async def test_dedupe_scoped_to_workspace_ignores_cross_tenant():
    """A matching national_id in a DIFFERENT workspace must not match —
    prevents cross-tenant family merges."""
    actor = await _mk_workspace()
    wsid = actor["tenant_id"]
    other = await _mk_workspace()
    other_wsid = other["tenant_id"]
    await _seed_parent(other_wsid, national_id="9999988888")

    row, matched_by = await dedupe_workspace_parent(
        db.session, national_id="9999988888", phone=None, email=None,
        workspace_id=wsid,
    )
    assert row is None
    assert matched_by == "new"


# ======================================================================
# C. link_workspace_parent_to_student — no-match (create) branch
# ======================================================================
@pytest.mark.asyncio
async def test_link_new_parent_creates_atomic_link():
    actor = await _mk_workspace()
    wsid = actor["tenant_id"]
    student = await _mk_pending_student(
        wsid,
        pending_parent_name="ولي مؤقت",
        pending_parent_phone="+966500111000",
    )

    result = await _link(
        actor, student, wsid=wsid,
        full_name="أحمد المعلم",
        phone="+966500111111",
        email="newdad@example.com",
        relationship="father",
    )
    assert result["matched_by"] == "new"
    parent_id = result["parent_id"]

    # students.parent_id flipped + trigger cleared pending_*.
    student_row = await gd_find_one(db.session, "students", {"id": student["id"]})
    assert student_row["parent_id"] == parent_id
    assert student_row.get("pending_parent_name") is None
    assert student_row.get("pending_parent_phone") is None

    # parents row created in the workspace.
    parent_row = await gd_find_one(db.session, "parents", {"id": parent_id})
    assert parent_row["school_id"] == wsid
    assert parent_row["phone"] == "+966500111111"
    assert parent_row["email"] == "newdad@example.com"

    # guardian_links: tenant_id == workspace id, primary on first link.
    links = await gd_find(db.session, "guardian_links",
                          {"student_id": student["id"], "is_active": True})
    assert len(links) == 1
    assert links[0]["tenant_id"] == wsid
    assert links[0]["is_primary"] is True
    assert links[0]["parent_id"] == parent_id


@pytest.mark.asyncio
async def test_link_new_parent_materialises_workspace_user():
    actor = await _mk_workspace()
    wsid = actor["tenant_id"]
    student = await _mk_pending_student(wsid)

    result = await _link(
        actor, student, wsid=wsid,
        full_name="ولي بدون بريد", phone="+966500202020",
    )
    assert result["matched_by"] == "new"
    assert result["parent_user_materialised"] is True

    parent_user_id = result["parent_user_id"]
    assert parent_user_id != result["parent_id"]  # synthetic users.id
    parent_user = await gd_find_one(db.session, "users", {"id": parent_user_id})
    assert parent_user is not None
    assert parent_user["role"] == "parent"
    assert parent_user["tenant_id"] == wsid
    assert parent_user["password_hash"] == "!invite-pending"
    # No email in payload → deterministic non-deliverable placeholder.
    assert parent_user["email"].endswith("@invite.nassaq.invalid")
    assert result["parent_id"] in parent_user["email"]


@pytest.mark.asyncio
async def test_link_new_parent_email_collision_falls_back_to_placeholder():
    actor = await _mk_workspace()
    wsid = actor["tenant_id"]
    student = await _mk_pending_student(wsid)

    # A global users row already owns this email (different workspace), so
    # materialise must fall back to the .invalid placeholder rather than
    # raising a unique-index violation.
    other = await _mk_workspace()
    colliding_email = f"collide-{uuid.uuid4()}@example.com"
    await gd_insert(db.session, "users", {
        "id": str(uuid.uuid4()),
        "role": "parent",
        "tenant_id": other["tenant_id"],
        "email": colliding_email,
        "full_name": "آخر",
        "password_hash": "!seed",
        "is_active": True,
        "preferred_language": "ar",
        "preferred_theme": "light",
    })
    await db.session.flush()

    result = await _link(
        actor, student, wsid=wsid,
        full_name="ولي بإيميل متعارض", email=colliding_email,
    )
    assert result["matched_by"] == "new"
    parent_user = await gd_find_one(
        db.session, "users", {"id": result["parent_user_id"]})
    assert parent_user["tenant_id"] == wsid
    assert parent_user["email"].endswith("@invite.nassaq.invalid")
    assert parent_user["email"] != colliding_email


@pytest.mark.asyncio
async def test_link_new_parent_default_name_when_blank():
    """No full_name and no pending_parent_name → the default Arabic
    parent label is used."""
    actor = await _mk_workspace()
    wsid = actor["tenant_id"]
    student = await _mk_pending_student(wsid)

    result = await _link(actor, student, wsid=wsid, phone="+966500606060")
    parent_row = await gd_find_one(db.session, "parents", {"id": result["parent_id"]})
    assert parent_row["full_name"] == "ولي الأمر"


# ======================================================================
# D. link_workspace_parent_to_student — dedupe (reuse) branches
# ======================================================================
@pytest.mark.asyncio
async def test_link_dedupes_by_national_id_reuses_row():
    actor = await _mk_workspace()
    wsid = actor["tenant_id"]
    existing_id = await _seed_parent(
        wsid, national_id="1234567890", full_name="أب موجود",
        phone="+966500999999", email="existing@example.com",
    )
    student = await _mk_pending_student(wsid)

    result = await _link(
        actor, student, wsid=wsid,
        national_id="1234567890", phone="+966500000000",
    )
    assert result["matched_by"] == "national_id"
    assert result["parent_id"] == existing_id
    # Dedupe path keeps legacy parent_ref == parent_id (no new users row).
    assert result["parent_user_materialised"] is False
    assert result["parent_user_id"] == existing_id


@pytest.mark.asyncio
async def test_link_dedupes_by_phone_email_pair_reuses_row():
    actor = await _mk_workspace()
    wsid = actor["tenant_id"]
    existing_id = await _seed_parent(
        wsid, phone="+966500222222", email="mom@example.com", full_name="أم",
    )
    student = await _mk_pending_student(wsid)

    result = await _link(
        actor, student, wsid=wsid,
        phone="+966500222222", email="mom@example.com",
    )
    assert result["matched_by"] == "phone_email"
    assert result["parent_id"] == existing_id


@pytest.mark.asyncio
async def test_link_dedupes_by_phone_alone_reuses_row():
    actor = await _mk_workspace()
    wsid = actor["tenant_id"]
    existing_id = await _seed_parent(wsid, phone="+966500333333", full_name="والد")
    student = await _mk_pending_student(wsid)

    result = await _link(actor, student, wsid=wsid, phone="+966500333333")
    assert result["matched_by"] == "phone"
    assert result["parent_id"] == existing_id


@pytest.mark.asyncio
async def test_link_dedupes_by_email_alone_reuses_row():
    actor = await _mk_workspace()
    wsid = actor["tenant_id"]
    existing_id = await _seed_parent(wsid, email="guardian@example.com", full_name="ولي")
    student = await _mk_pending_student(wsid)

    result = await _link(actor, student, wsid=wsid, email="guardian@example.com")
    assert result["matched_by"] == "email"
    assert result["parent_id"] == existing_id


# ======================================================================
# E. Conservative fill on the dedupe path (DB-level)
# ======================================================================
@pytest.mark.asyncio
async def test_link_conservative_fill_never_overwrites_established_fields():
    actor = await _mk_workspace()
    wsid = actor["tenant_id"]
    existing_id = await _seed_parent(
        wsid,
        national_id="1234567890",
        full_name="أب موجود",
        phone="+966500999999",
        email="existing@example.com",
    )
    student = await _mk_pending_student(wsid)

    # Match by national_id, then try to clobber every established field.
    await _link(
        actor, student, wsid=wsid,
        national_id="1234567890",
        full_name="اسم جديد",
        phone="+966500000000",
        email="new@example.com",
    )
    p = await gd_find_one(db.session, "parents", {"id": existing_id})
    assert p["full_name"] == "أب موجود"
    assert p["phone"] == "+966500999999"
    assert p["email"] == "existing@example.com"


@pytest.mark.asyncio
async def test_link_conservative_fill_fills_null_columns_only():
    actor = await _mk_workspace()
    wsid = actor["tenant_id"]
    # Existing row matched by national_id has NULL phone/email but a set name.
    existing_id = await _seed_parent(
        wsid, national_id="1234567890", full_name="أب موجود",
    )
    student = await _mk_pending_student(wsid)

    await _link(
        actor, student, wsid=wsid,
        national_id="1234567890",
        full_name="اسم جديد",
        phone="+966500777777",
        email="filled@example.com",
    )
    p = await gd_find_one(db.session, "parents", {"id": existing_id})
    # NULLs filled.
    assert p["phone"] == "+966500777777"
    assert p["email"] == "filled@example.com"
    # Established name untouched.
    assert p["full_name"] == "أب موجود"


# ======================================================================
# F. guardian_links.tenant_id + audit entry invariants
# ======================================================================
@pytest.mark.asyncio
async def test_link_guardian_link_tenant_id_equals_workspace():
    actor = await _mk_workspace()
    wsid = actor["tenant_id"]
    student = await _mk_pending_student(wsid)

    result = await _link(actor, student, wsid=wsid, phone="+966500808080")
    link_row = result["link"]
    assert link_row["tenant_id"] == wsid
    # Re-read from DB to be sure it persisted with the workspace tenant_id.
    persisted = await gd_find_one(
        db.session, "guardian_links", {"id": link_row["id"]})
    assert persisted["tenant_id"] == wsid


@pytest.mark.asyncio
async def test_link_writes_audit_entry():
    actor = await _mk_workspace()
    wsid = actor["tenant_id"]
    student = await _mk_pending_student(wsid)

    result = await _link(
        actor, student, wsid=wsid,
        national_id="5544332211", phone="+966500909090",
    )
    audits = await gd_find(db.session, "audit_logs", {
        "action": "INDEPENDENT_TEACHER_PARENT_LINK",
        "entity_id": student["id"],
    })
    assert len(audits) == 1
    audit = audits[0]
    assert audit["school_id"] == wsid
    assert audit["performed_by"] == actor["id"]
    assert audit["details"]["matched_by"] == "new"
    assert audit["details"]["tenant_id"] == wsid
    assert audit["details"]["parent_id"] == result["parent_id"]
    assert audit["details"]["parent_user_materialised"] is True


@pytest.mark.asyncio
async def test_link_audit_matched_by_reflects_dedupe_path():
    actor = await _mk_workspace()
    wsid = actor["tenant_id"]
    await _seed_parent(wsid, email="dedupe@example.com")
    student = await _mk_pending_student(wsid)

    await _link(actor, student, wsid=wsid, email="dedupe@example.com")
    audits = await gd_find(db.session, "audit_logs", {
        "action": "INDEPENDENT_TEACHER_PARENT_LINK",
        "entity_id": student["id"],
    })
    assert len(audits) == 1
    assert audits[0]["details"]["matched_by"] == "email"
    assert audits[0]["details"]["parent_user_materialised"] is False
