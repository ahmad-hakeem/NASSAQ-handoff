"""Regression tests for Task #758 — drag-drop student transfer.

The legacy POST /students/transfer-class handler wrote to columns that do
not exist on the ORM models (`student_count`, `student_ids` on classes,
`class_name` on students), so those writes were silently dropped and the
class counters never moved. These tests assert that a transfer:

- moves the student to the target class via the real `class_id` column,
- re-derives the canonical `current_students` counter for BOTH classes,
- returns the fresh counts so the frontend can refresh without drift,
- is rejected cleanly (404, no mutation) for a cross-tenant target class.
"""
import uuid
import pytest


@pytest.mark.asyncio
async def test_transfer_moves_student_and_updates_both_counts(
    client, school_principal_headers, tenant_a, _db_session
):
    from engines.sql_utils import gd_insert, gd_find_one

    class_a = str(uuid.uuid4())
    class_b = str(uuid.uuid4())
    await gd_insert(_db_session, "classes", {"id": class_a, "school_id": tenant_a, "name": "1A", "current_students": 0})
    await gd_insert(_db_session, "classes", {"id": class_b, "school_id": tenant_a, "name": "1B", "current_students": 0})

    # Two students in A, one in B.
    a_students = []
    for _ in range(2):
        sid = str(uuid.uuid4())
        await gd_insert(_db_session, "students", {
            "id": sid, "school_id": tenant_a, "full_name": f"A-{sid[:6]}",
            "class_id": class_a, "is_active": True,
        })
        a_students.append(sid)
    b_sid = str(uuid.uuid4())
    await gd_insert(_db_session, "students", {
        "id": b_sid, "school_id": tenant_a, "full_name": "B-orig",
        "class_id": class_b, "is_active": True,
    })
    await _db_session.flush()

    moving = a_students[0]
    r = await client.post(
        "/students/transfer-class",
        json={"student_id": moving, "target_class_id": class_b},
        headers=school_principal_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True
    assert body.get("old_class_id") == class_a
    assert body.get("target_class_id") == class_b
    assert body.get("old_class_current_students") == 1
    assert body.get("target_class_current_students") == 2

    # Student actually moved.
    row = await gd_find_one(_db_session, "students", {"id": moving})
    assert row.get("class_id") == class_b

    # Persisted canonical counters reflect the move.
    ca = await gd_find_one(_db_session, "classes", {"id": class_a})
    cb = await gd_find_one(_db_session, "classes", {"id": class_b})
    assert ca.get("current_students") == 1
    assert cb.get("current_students") == 2

    # The live-aggregated /classes endpoint agrees.
    r = await client.get("/classes", headers=school_principal_headers)
    assert r.status_code == 200
    by_id = {c["id"]: c for c in r.json()}
    assert by_id[class_a]["student_count"] == 1
    assert by_id[class_b]["student_count"] == 2


@pytest.mark.asyncio
async def test_transfer_same_class_is_noop(
    client, school_principal_headers, tenant_a, _db_session
):
    from engines.sql_utils import gd_insert

    cls = str(uuid.uuid4())
    await gd_insert(_db_session, "classes", {"id": cls, "school_id": tenant_a, "name": "2A"})
    sid = str(uuid.uuid4())
    await gd_insert(_db_session, "students", {
        "id": sid, "school_id": tenant_a, "full_name": "Same", "class_id": cls, "is_active": True,
    })
    await _db_session.flush()

    r = await client.post(
        "/students/transfer-class",
        json={"student_id": sid, "target_class_id": cls},
        headers=school_principal_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json().get("success") is True


@pytest.mark.asyncio
async def test_transfer_cross_tenant_target_rejected_no_mutation(
    client, school_principal_headers, tenant_a, tenant_b, _db_session
):
    from engines.sql_utils import gd_insert, gd_find_one

    src_class = str(uuid.uuid4())
    foreign_class = str(uuid.uuid4())
    await gd_insert(_db_session, "classes", {"id": src_class, "school_id": tenant_a, "name": "3A"})
    await gd_insert(_db_session, "classes", {"id": foreign_class, "school_id": tenant_b, "name": "Foreign"})
    sid = str(uuid.uuid4())
    await gd_insert(_db_session, "students", {
        "id": sid, "school_id": tenant_a, "full_name": "Stayput",
        "class_id": src_class, "is_active": True,
    })
    await _db_session.flush()

    r = await client.post(
        "/students/transfer-class",
        json={"student_id": sid, "target_class_id": foreign_class},
        headers=school_principal_headers,
    )
    assert r.status_code == 404, r.text
    body = r.json()
    # The global StarletteHTTPException handler reshapes the body to
    # {"success": False, "error": {"code", "message"}}; the safe Arabic
    # message lives at error.message (the FE reads it from there).
    msg = (body.get("error") or {}).get("message")
    assert isinstance(msg, str) and msg

    # Student must not have moved.
    row = await gd_find_one(_db_session, "students", {"id": sid})
    assert row.get("class_id") == src_class
