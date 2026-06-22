"""Regression: a follow-up sheet (كشف المتابعة) edit must survive a POST→GET
round-trip and a second save must update the single record in place — never
insert a duplicate row.

This backs the frontend fix where closing the follow-up dialog now flushes the
pending edit (previously the close persisted nothing and the next reopen
blind-replaced local state from a stale server copy, losing the edit). The
persistence route is shared by normal school teachers and independent teachers,
so every case runs against both tenant types.

The assertions key on a custom column id that the coursework hydration never
touches, so the GET reflects exactly what was saved (no derived overlay noise).
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, create_access_token
from engines.sql_utils import gd_find, gd_insert


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth(user_id: str, role: str, tenant_id: str) -> dict:
    token = create_access_token({"sub": user_id, "role": role, "tenant_id": tenant_id})
    return {"Authorization": f"Bearer {token}"}


async def _mk_school(tenant_id: str, school_type: str) -> None:
    await gd_insert(db.session, "schools", {
        "id": tenant_id,
        "name": f"مدرسة-{tenant_id[:6]}",
        "code": f"S{tenant_id[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
        "school_type": school_type,
        "tenant_type": school_type,
    })


async def _mk_teacher(tenant_id: str) -> str:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "role": "teacher", "tenant_id": tenant_id,
        "email": f"t-{uid}@t.test", "full_name": "معلم",
        "is_active": True, "password_hash": "x",
    })
    return uid


async def _mk_class(tenant_id: str) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid, "school_id": tenant_id, "tenant_id": tenant_id, "name": "1A",
    })
    return cid


async def _mk_subject(tenant_id: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": sid, "school_id": tenant_id, "tenant_id": tenant_id,
        "name": "الرياضيات", "name_ar": "الرياضيات",
    })
    return sid


async def _mk_student(tenant_id: str, class_id: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "tenant_id": tenant_id, "school_id": tenant_id,
        "class_id": class_id, "full_name": f"طالب-{sid[:6]}", "is_active": True,
    })
    return sid


async def _mk_session(tenant_id: str, class_id: str, subject_id: str, teacher_id: str) -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "class_sessions", {
        "id": session_id,
        "school_id": tenant_id,
        "tenant_id": tenant_id,
        "class_id": class_id,
        "subject_id": subject_id,
        "teacher_id": teacher_id,
        "date": "2026-06-22",
        "status": "active",
        "start_time": now,
        "created_at": now,
    })
    return session_id


async def _setup(tenant_id: str, school_type: str):
    await _mk_school(tenant_id, school_type)
    teacher_id = await _mk_teacher(tenant_id)
    class_id = await _mk_class(tenant_id)
    subject_id = await _mk_subject(tenant_id)
    student_id = await _mk_student(tenant_id, class_id)
    session_id = await _mk_session(tenant_id, class_id, subject_id, teacher_id)
    return {
        "teacher_id": teacher_id, "class_id": class_id, "subject_id": subject_id,
        "student_id": student_id, "session_id": session_id,
        "headers": _auth(teacher_id, "teacher", tenant_id),
    }


# Custom column id the coursework hydration never overlays, so GET == saved.
COL = "c-custom-quiz"


async def _save(client, ctx, value):
    return await client.post(
        f"/session/{ctx['session_id']}/followup-record",
        headers=ctx["headers"],
        json={"data": {ctx["student_id"]: {COL: value}}, "absences": {}},
    )


async def _read(client, ctx):
    resp = await client.get(
        f"/session/{ctx['session_id']}/followup-record", headers=ctx["headers"]
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"].get(ctx["student_id"], {})


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_edit_persists_across_post_then_get(client, school_type):
    """A saved score is read back unchanged — the core 'edit survives close and
    reopen' guarantee, proven at the persistence layer the close flush hits."""
    ctx = await _setup(str(uuid.uuid4()), school_type)

    r = await _save(client, ctx, 7)
    assert r.status_code == 200, r.text
    assert r.json().get("success") is True

    assert (await _read(client, ctx)).get(COL) == 7


@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_second_save_updates_in_place_no_duplicate_row(client, school_type):
    """Saving again (the reopen-after-edit case) must overwrite the single
    record keyed by {class_id, subject_id}, never insert a second row."""
    ctx = await _setup(str(uuid.uuid4()), school_type)

    assert (await _save(client, ctx, 4)).status_code == 200
    assert (await _save(client, ctx, 9)).status_code == 200

    rows = await gd_find(db.session, "followup_records", {
        "class_id": ctx["class_id"], "subject_id": ctx["subject_id"],
    })
    assert len(rows) == 1, f"expected exactly one record, got {len(rows)}"
    assert (await _read(client, ctx)).get(COL) == 9


@pytest.mark.asyncio
@pytest.mark.parametrize("school_type", ["real", "independent_teacher"])
async def test_repeated_edits_increment_decrement_and_zero_transitions(client, school_type):
    """Editing the same cell multiple times — increment, decrement,
    zero→nonzero and nonzero→another-nonzero — always reads back the latest
    value, and still leaves a single record."""
    ctx = await _setup(str(uuid.uuid4()), school_type)

    for value in [0, 3, 5, 2, 8]:  # 0→3 up, 3→5 up, 5→2 down, 2→8 up (nonzero→nonzero)
        assert (await _save(client, ctx, value)).status_code == 200
        assert (await _read(client, ctx)).get(COL) == value

    rows = await gd_find(db.session, "followup_records", {
        "class_id": ctx["class_id"], "subject_id": ctx["subject_id"],
    })
    assert len(rows) == 1, f"repeated edits must not multiply rows, got {len(rows)}"
