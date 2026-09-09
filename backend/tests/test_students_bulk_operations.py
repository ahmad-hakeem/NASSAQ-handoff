"""
Tests for student bulk operations:
- POST /students/bulk-assign
- POST /students/bulk-delete
- Auto-provisioning classes during student import
"""
import uuid
from datetime import datetime, timezone
import pytest
from engines.sql_utils import gd_find, gd_find_one, gd_insert


@pytest.mark.asyncio
async def test_bulk_assign_students_to_class(
    client, school_principal_headers, tenant_a, _db_session
):
    # Create target class
    target_class_id = str(uuid.uuid4())
    await gd_insert(_db_session, "classes", {
        "id": target_class_id,
        "school_id": tenant_a,
        "name": "الصف الأول - أ",
        "name_ar": "الصف الأول - أ",
        "grade_level": "1",
        "section": "أ",
        "capacity": 35,
        "current_students": 0,
        "is_active": True,
    })

    # Create 3 unassigned students
    s1_id = str(uuid.uuid4())
    s2_id = str(uuid.uuid4())
    s3_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    for sid, name in [(s1_id, "طالب أ"), (s2_id, "طالب ب"), (s3_id, "طالب ج")]:
        await gd_insert(_db_session, "students", {
            "id": sid,
            "school_id": tenant_a,
            "class_id": None,
            "full_name": name,
            "national_id": f"10{sid[:8]}",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        })
    await _db_session.flush()

    res = await client.post(
        "/students/bulk-assign",
        json={
            "student_ids": [s1_id, s2_id, s3_id],
            "target_class_id": target_class_id,
        },
        headers=school_principal_headers,
    )

    assert res.status_code == 200, res.text
    data = res.json()
    assert data["success"] is True
    assert data["assigned_count"] == 3
    assert data["target_class_id"] == target_class_id

    # Verify database state
    s1 = await gd_find_one(_db_session, "students", {"id": s1_id})
    s2 = await gd_find_one(_db_session, "students", {"id": s2_id})
    s3 = await gd_find_one(_db_session, "students", {"id": s3_id})

    assert s1["class_id"] == target_class_id
    assert s2["class_id"] == target_class_id
    assert s3["class_id"] == target_class_id

    # Verify class count was reconciled
    target_class = await gd_find_one(_db_session, "classes", {"id": target_class_id})
    assert target_class["current_students"] == 3


@pytest.mark.asyncio
async def test_bulk_delete_students(
    client, school_principal_headers, tenant_a, _db_session
):
    s1_id = str(uuid.uuid4())
    s2_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    for sid, name in [(s1_id, "طالب حذف 1"), (s2_id, "طالب حذف 2")]:
        await gd_insert(_db_session, "students", {
            "id": sid,
            "school_id": tenant_a,
            "class_id": None,
            "full_name": name,
            "national_id": f"10{sid[:8]}",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        })
    await _db_session.flush()

    res = await client.post(
        "/students/bulk-delete",
        json={
            "student_ids": [s1_id, s2_id],
        },
        headers=school_principal_headers,
    )

    assert res.status_code == 200, res.text
    data = res.json()
    assert data["success"] is True
    assert data["deleted_count"] == 2

    # Verify both students are soft-deleted
    s1 = await gd_find_one(_db_session, "students", {"id": s1_id})
    s2 = await gd_find_one(_db_session, "students", {"id": s2_id})
    assert s1["is_active"] is False
    assert s2["is_active"] is False


@pytest.mark.asyncio
async def test_bulk_assign_cross_tenant_rejection(
    client, school_principal_headers, tenant_a, tenant_b, _db_session
):
    # Class in school B (tenant_b)
    class_b_id = str(uuid.uuid4())
    await gd_insert(_db_session, "classes", {
        "id": class_b_id, "school_id": tenant_b, "name": "فصل مدرسة ب", "is_active": True
    })

    # Student in school A (tenant_a)
    s_id = str(uuid.uuid4())
    await gd_insert(_db_session, "students", {
        "id": s_id, "school_id": tenant_a, "full_name": "طالب", "is_active": True
    })
    await _db_session.flush()

    res = await client.post(
        "/students/bulk-assign",
        json={"student_ids": [s_id], "target_class_id": class_b_id},
        headers=school_principal_headers,
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_auto_provision_classes_during_student_import(
    client, school_principal_headers, tenant_a, _db_session
):
    import io
    import pandas as pd

    # Verify no classes exist initially
    initial_classes = await gd_find_one(_db_session, "classes", {"school_id": tenant_a})
    assert initial_classes is None

    nid_1 = f"11{uuid.uuid4().int % 100000000:08d}"
    nid_2 = f"12{uuid.uuid4().int % 100000000:08d}"

    # Construct Excel DataFrame with Grade and Section
    df = pd.DataFrame([{
        "الاسم الأول": "سالم",
        "اسم العائلة": "القحطاني",
        "رقم الهوية": nid_1,
        "جوال ولي الأمر": "0501234567",
        "الصف": "الأول الابتدائي",
        "الفصل": "أ",
    }, {
        "الاسم الأول": "فهد",
        "اسم العائلة": "العتيبي",
        "رقم الهوية": nid_2,
        "جوال ولي الأمر": "0501234568",
        "الصف": "الأول الابتدائي",
        "الفصل": "أ",
    }])

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    buf.seek(0)

    res = await client.post(
        "/bulk/import/students",
        files={"file": ("test_students.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=school_principal_headers,
    )

    assert res.status_code == 200, res.text
    data = res.json()
    assert data["imported"] == 2
    assert data["failed"] == 0

    all_classes = await gd_find(_db_session, "classes", {"school_id": tenant_a})
    s1 = await gd_find_one(_db_session, "students", {"national_id": nid_1, "school_id": tenant_a})
    s2 = await gd_find_one(_db_session, "students", {"national_id": nid_2, "school_id": tenant_a})
    assert len(all_classes) == 1
    assert "الأول الابتدائي" in all_classes[0]["name"]
    assert all_classes[0]["current_students"] == 2
    assert s1["class_id"] == all_classes[0]["id"]
    assert s2["class_id"] == all_classes[0]["id"]


@pytest.mark.asyncio
async def test_bulk_assign_rejects_when_class_full(
    client, school_principal_headers, tenant_a, _db_session
):
    # Target class with capacity 2 and already 2 students
    target_class_id = str(uuid.uuid4())
    await gd_insert(_db_session, "classes", {
        "id": target_class_id,
        "school_id": tenant_a,
        "name": "فصل ممتلئ",
        "name_ar": "فصل ممتلئ",
        "capacity": 2,
        "current_students": 2,
        "is_active": True,
    })

    now = datetime.now(timezone.utc).isoformat()
    # 2 existing students in the class
    for i in range(2):
        sid = str(uuid.uuid4())
        await gd_insert(_db_session, "students", {
            "id": sid,
            "school_id": tenant_a,
            "class_id": target_class_id,
            "full_name": f"طالب قديم {i}",
            "national_id": f"20{sid[:8]}",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        })

    # 1 unassigned student to assign
    new_sid = str(uuid.uuid4())
    await gd_insert(_db_session, "students", {
        "id": new_sid,
        "school_id": tenant_a,
        "class_id": None,
        "full_name": "طالب جديد",
        "national_id": f"21{new_sid[:8]}",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    })
    await _db_session.flush()

    res = await client.post(
        "/students/bulk-assign",
        json={
            "student_ids": [new_sid],
            "target_class_id": target_class_id,
        },
        headers=school_principal_headers,
    )

    assert res.status_code == 409
    body = res.json()
    err = body.get("error") or {}
    assert err.get("code") == "CLASS_CAPACITY_REACHED"
    assert "ممتلئ" in err.get("message", "")

    # Verify student was not assigned
    st = await gd_find_one(_db_session, "students", {"id": new_sid})
    assert st["class_id"] is None


@pytest.mark.asyncio
async def test_bulk_assign_rejects_when_exceeding_capacity(
    client, school_principal_headers, tenant_a, _db_session
):
    # Target class with capacity 3 and 2 existing students (1 seat left)
    target_class_id = str(uuid.uuid4())
    await gd_insert(_db_session, "classes", {
        "id": target_class_id,
        "school_id": tenant_a,
        "name": "فصل شبه ممتلئ",
        "name_ar": "فصل شبه ممتلئ",
        "capacity": 3,
        "current_students": 2,
        "is_active": True,
    })

    now = datetime.now(timezone.utc).isoformat()
    # 2 existing students in the class
    for i in range(2):
        sid = str(uuid.uuid4())
        await gd_insert(_db_session, "students", {
            "id": sid,
            "school_id": tenant_a,
            "class_id": target_class_id,
            "full_name": f"طالب موجود {i}",
            "national_id": f"30{sid[:8]}",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        })

    # 2 unassigned students trying to fit into 1 seat
    s1_id = str(uuid.uuid4())
    s2_id = str(uuid.uuid4())
    for sid, name in [(s1_id, "طالب أ"), (s2_id, "طالب ب")]:
        await gd_insert(_db_session, "students", {
            "id": sid,
            "school_id": tenant_a,
            "class_id": None,
            "full_name": name,
            "national_id": f"31{sid[:8]}",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        })
    await _db_session.flush()

    res = await client.post(
        "/students/bulk-assign",
        json={
            "student_ids": [s1_id, s2_id],
            "target_class_id": target_class_id,
        },
        headers=school_principal_headers,
    )

    assert res.status_code == 409
    body = res.json()
    err = body.get("error") or {}
    assert err.get("code") == "CLASS_CAPACITY_REACHED"
    assert "لا يتسع" in err.get("message", "")

    # Verify students were not assigned
    s1 = await gd_find_one(_db_session, "students", {"id": s1_id})
    s2 = await gd_find_one(_db_session, "students", {"id": s2_id})
    assert s1["class_id"] is None
    assert s2["class_id"] is None


@pytest.mark.asyncio
async def test_auto_distribute_students_flow(
    client, school_principal_headers, tenant_a, _db_session
):
    # Existing class in Grade 1 with capacity 2 and 1 existing student (1 seat open)
    c1_id = str(uuid.uuid4())
    await gd_insert(_db_session, "classes", {
        "id": c1_id,
        "school_id": tenant_a,
        "name": "الصف 1 - أ",
        "name_ar": "الصف 1 - أ",
        "grade_level": "1",
        "grade": "1",
        "section": "أ",
        "capacity": 2,
        "current_students": 1,
        "is_active": True,
    })

    now = datetime.now(timezone.utc).isoformat()
    # 1 student in class c1
    s_existing = str(uuid.uuid4())
    await gd_insert(_db_session, "students", {
        "id": s_existing,
        "school_id": tenant_a,
        "class_id": c1_id,
        "full_name": "طالب قديم",
        "national_id": f"40{s_existing[:8]}",
        "grade": "1",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    })

    # 3 unassigned students in Grade 1
    unassigned_ids = []
    for i in range(3):
        sid = str(uuid.uuid4())
        unassigned_ids.append(sid)
        await gd_insert(_db_session, "students", {
            "id": sid,
            "school_id": tenant_a,
            "class_id": None,
            "full_name": f"طالب غير مسند {i}",
            "national_id": f"41{sid[:8]}",
            "grade": "1",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        })
    await _db_session.flush()

    # Call auto-distribute
    res = await client.post(
        "/students/auto-distribute",
        json={"default_capacity": 2},
        headers=school_principal_headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["success"] is True
    assert data["total_assigned"] == 3
    assert data["classes_created_count"] == 1

    # Verify database: all 3 students are now assigned
    for sid in unassigned_ids:
        st = await gd_find_one(_db_session, "students", {"id": sid})
        assert st["class_id"] is not None


@pytest.mark.asyncio
async def test_bulk_import_batches_tracking_and_rollback(
    client, school_principal_headers, tenant_a, _db_session
):
    now_iso = datetime.now(timezone.utc).isoformat()
    now_dt = datetime.now(timezone.utc)

    # 1 auto-created class
    new_cid = str(uuid.uuid4())
    await gd_insert(_db_session, "classes", {
        "id": new_cid,
        "school_id": tenant_a,
        "name": "الصف الأول - أ",
        "name_ar": "الصف الأول - أ",
        "grade_level": "1",
        "section": "أ",
        "capacity": 30,
        "current_students": 2,
        "is_active": True,
        "created_at": now_iso,
        "updated_at": now_iso,
    })

    # 2 students imported
    s1_id = str(uuid.uuid4())
    s2_id = str(uuid.uuid4())
    for sid, name in [(s1_id, "طالب استيراد 1"), (s2_id, "طالب استيراد 2")]:
        await gd_insert(_db_session, "students", {
            "id": sid,
            "school_id": tenant_a,
            "class_id": new_cid,
            "full_name": name,
            "national_id": f"50{sid[:8]}",
            "is_active": True,
            "created_at": now_iso,
            "updated_at": now_iso,
        })

    # Batch record
    batch_id = str(uuid.uuid4())
    await gd_insert(_db_session, "bulk_import_batches", {
        "id": batch_id,
        "school_id": tenant_a,
        "actor_id": "test-user",
        "actor_name": "مدير النظام",
        "import_type": "students",
        "file_name": "test_students.xlsx",
        "imported_count": 2,
        "student_ids": [s1_id, s2_id],
        "created_class_ids": [new_cid],
        "status": "active",
        "created_at": now_dt,
        "updated_at": now_dt,
    })
    await _db_session.flush()

    # 1. Test GET /bulk/batches/latest
    latest_res = await client.get("/bulk/batches/latest", headers=school_principal_headers)
    assert latest_res.status_code == 200, latest_res.text
    latest_data = latest_res.json()
    assert latest_data.get("batch") is not None
    assert latest_data["batch"]["id"] == batch_id

    # 2. Test POST /bulk/batches/{batch_id}/rollback
    rb_res = await client.post(f"/bulk/batches/{batch_id}/rollback", headers=school_principal_headers)
    assert rb_res.status_code == 200, rb_res.text
    rb_data = rb_res.json()
    assert rb_data["success"] is True
    assert rb_data["rolled_back_students"] == 2
    assert rb_data["rolled_back_classes"] == 1

    # Verify students are soft-deleted
    s1 = await gd_find_one(_db_session, "students", {"id": s1_id})
    s2 = await gd_find_one(_db_session, "students", {"id": s2_id})
    assert s1["is_active"] is False
    assert s2["is_active"] is False

    # Verify class was soft-deleted because it became empty
    c = await gd_find_one(_db_session, "classes", {"id": new_cid})
    assert c["is_active"] is False

    # 3. Test rolling back again returns 400
    rb_again = await client.post(f"/bulk/batches/{batch_id}/rollback", headers=school_principal_headers)
    assert rb_again.status_code == 400


