"""
Tests for student bulk operations:
- POST /students/bulk-assign
- POST /students/bulk-delete
- Auto-provisioning classes during student import
"""
import uuid
from datetime import datetime, timezone
import pytest
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_update_one


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
async def test_bulk_assign_allows_students_beyond_legacy_capacity(
    client, school_principal_headers, tenant_a, _db_session
):
    # Legacy capacity metadata is 2, but rosters are open-ended and already
    # contain two students.
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

    assert res.status_code == 200, res.text
    assert res.json()["assigned_count"] == 1

    # Verify the student was assigned beyond the legacy value.
    st = await gd_find_one(_db_session, "students", {"id": new_sid})
    assert st["class_id"] == target_class_id
    target = await gd_find_one(_db_session, "classes", {"id": target_class_id})
    assert target["current_students"] == 3


@pytest.mark.asyncio
async def test_bulk_assign_allows_multiple_students_beyond_legacy_capacity(
    client, school_principal_headers, tenant_a, _db_session
):
    # Target class with legacy capacity 3 and 2 existing students. Both new
    # students must be accepted despite the old one-seat remainder.
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

    # 2 unassigned students, both accepted into the open-ended roster.
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

    assert res.status_code == 200, res.text
    assert res.json()["assigned_count"] == 2

    # Verify both students were assigned.
    s1 = await gd_find_one(_db_session, "students", {"id": s1_id})
    s2 = await gd_find_one(_db_session, "students", {"id": s2_id})
    assert s1["class_id"] == target_class_id
    assert s2["class_id"] == target_class_id
    target = await gd_find_one(_db_session, "classes", {"id": target_class_id})
    assert target["current_students"] == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("student_count", [31, 32, 50])
async def test_bulk_assign_accepts_large_roster_beyond_30(
    student_count, client, school_principal_headers, tenant_a, _db_session
):
    """The 31st, 32nd, and 50th student are valid roster assignments."""
    target_class_id = str(uuid.uuid4())
    await gd_insert(_db_session, "classes", {
        "id": target_class_id,
        "school_id": tenant_a,
        "name": f"فصل مفتوح {student_count}",
        "capacity": 30,
        "current_students": 0,
        "is_active": True,
    })

    now = datetime.now(timezone.utc).isoformat()
    student_ids = []
    for index in range(student_count):
        sid = str(uuid.uuid4())
        student_ids.append(sid)
        await gd_insert(_db_session, "students", {
            "id": sid,
            "school_id": tenant_a,
            "class_id": None,
            "full_name": f"طالب {index}",
            "national_id": f"9{sid.replace('-', '')[:9]}",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        })
    await _db_session.flush()

    res = await client.post(
        "/students/bulk-assign",
        json={"student_ids": student_ids, "target_class_id": target_class_id},
        headers=school_principal_headers,
    )

    assert res.status_code == 200, res.text
    assert res.json()["assigned_count"] == student_count
    assigned = await gd_find(
        _db_session, "students", {"school_id": tenant_a, "class_id": target_class_id}
    )
    assert len(assigned) == student_count
    target = await gd_find_one(_db_session, "classes", {"id": target_class_id})
    assert target["current_students"] == student_count


@pytest.mark.asyncio
async def test_auto_distribute_students_flow(
    client, school_principal_headers, tenant_a, _db_session
):
    # Existing class in Grade 1 with legacy capacity metadata and one existing
    # student. Auto-distribution must not create a second class for that value.
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
    assert data["classes_created_count"] == 0

    # Verify database: all 3 students are now assigned
    for sid in unassigned_ids:
        st = await gd_find_one(_db_session, "students", {"id": sid})
        assert st["class_id"] == c1_id


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

    # Parent 1: only has s1.  Without an ownership marker it must survive.
    p1_id = str(uuid.uuid4())
    u1_id = str(uuid.uuid4())
    await gd_insert(_db_session, "users", {
        "id": u1_id,
        "email": f"parent_{p1_id[:8]}@nassaq.local",
        "password_hash": "mock_hash",
        "role": "parent",
        "tenant_id": tenant_a,
        "full_name": "ولي أمر 1",
        "is_active": True,
        "created_at": now_iso,
    })
    await gd_insert(_db_session, "parents", {
        "id": p1_id,
        "school_id": tenant_a,
        # ``parents`` has no user_id column; the canonical relationship is
        # represented by guardian_links.parent_ref below.
        "email": f"parent_{p1_id[:8]}@nassaq.local",
        "full_name": "ولي أمر 1",
        "student_ids": [s1_id],
        "is_active": True,
        "created_at": now_iso,
    })

    # Parent 2: has s2 AND another student other_sid -> should be preserved with s2 removed
    p2_id = str(uuid.uuid4())
    u2_id = str(uuid.uuid4())
    other_sid = str(uuid.uuid4())
    await gd_insert(_db_session, "users", {
        "id": u2_id,
        "email": f"parent_{p2_id[:8]}@nassaq.local",
        "password_hash": "mock_hash",
        "role": "parent",
        "tenant_id": tenant_a,
        "full_name": "ولي أمر 2",
        "is_active": True,
        "created_at": now_iso,
    })
    await gd_insert(_db_session, "parents", {
        "id": p2_id,
        "school_id": tenant_a,
        "email": f"parent_{p2_id[:8]}@nassaq.local",
        "full_name": "ولي أمر 2",
        "student_ids": [s2_id, other_sid],
        "is_active": True,
        "created_at": now_iso,
    })
    await gd_insert(_db_session, "students", {
        "id": other_sid,
        "school_id": tenant_a,
        "full_name": "طالب مستقل",
        "national_id": f"60{other_sid[:8]}",
        "parent_id": p2_id,
        "is_active": True,
        "created_at": now_iso,
    })
    await gd_insert(_db_session, "guardian_links", {
        "id": str(uuid.uuid4()),
        "parent_ref": u1_id,
        "parent_id": p1_id,
        "student_id": s1_id,
        "tenant_id": tenant_a,
        "is_active": True,
    })
    await gd_insert(_db_session, "guardian_links", {
        "id": str(uuid.uuid4()),
        "parent_ref": u2_id,
        "parent_id": p2_id,
        "student_id": s2_id,
        "tenant_id": tenant_a,
        "is_active": True,
    })
    await gd_insert(_db_session, "guardian_links", {
        "id": str(uuid.uuid4()),
        "parent_ref": u2_id,
        "parent_id": p2_id,
        "student_id": other_sid,
        "tenant_id": tenant_a,
        "is_active": True,
    })

    for sid, name, pid in [(s1_id, "طالب استيراد 1", p1_id), (s2_id, "طالب استيراد 2", p2_id)]:
        await gd_insert(_db_session, "students", {
            "id": sid,
            "school_id": tenant_a,
            "class_id": new_cid,
            "parent_id": pid,
            "full_name": name,
            "national_id": f"50{sid[:8]}",
            "is_active": True,
            "created_at": now_iso,
            "updated_at": now_iso,
        })
    # Update p1 and p2 student_ids with new IDs
    await gd_update_one(_db_session, "parents", {"id": p1_id}, {"student_ids": [s1_id]})
    await gd_update_one(_db_session, "parents", {"id": p2_id}, {"student_ids": [s2_id, other_sid]})

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
        "created_parent_ids": [p1_id],
        "created_parent_user_ids": [u1_id],
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
    assert rb_data["rolled_back_parents"] == 0
    assert rb_data["rolled_back_users"] == 0

    # Verify students are removed completely so they can be re-imported cleanly
    s1 = await gd_find_one(_db_session, "students", {"id": s1_id})
    s2 = await gd_find_one(_db_session, "students", {"id": s2_id})
    assert s1 is None
    assert s2 is None

    # The restored schema has no ownership marker.  Student rollback remains
    # available, but parent/user cleanup is fail-closed without proven
    # ownership.
    preserved_p1 = await gd_find_one(_db_session, "parents", {"id": p1_id})
    preserved_u1 = await gd_find_one(_db_session, "users", {"id": u1_id})
    assert preserved_p1 is not None
    assert preserved_u1 is not None

    # Verify parent 2 was PRESERVED because they have other_sid
    preserved_p2 = await gd_find_one(_db_session, "parents", {"id": p2_id})
    preserved_u2 = await gd_find_one(_db_session, "users", {"id": u2_id})
    assert preserved_p2 is not None
    assert preserved_u2 is not None
    assert s2_id not in preserved_p2.get("student_ids", [])
    assert other_sid in preserved_p2.get("student_ids", [])

    # Verify class was deleted because it became empty
    c = await gd_find_one(_db_session, "classes", {"id": new_cid})
    assert c is None

    # 3. Test rolling back again returns 400
    rb_again = await client.post(f"/bulk/batches/{batch_id}/rollback", headers=school_principal_headers)
    assert rb_again.status_code == 400

    # 4. Test re-import after rollback: importing again with the same national IDs must succeed without constraint errors
    import io
    import random
    import pandas as pd
    unique_nid = f"19{random.randint(10000000, 99999999)}"
    df_reimport = pd.DataFrame([{
        "الاسم الأول": "طالب",
        "اسم العائلة": "معاد",
        "رقم الهوية": unique_nid,
        "جوال ولي الأمر": "0501234567",
        "الصف": "الصف الأول الابتدائي",
        "الفصل": "أ",
    }])
    output_buf = io.BytesIO()
    df_reimport.to_excel(output_buf, index=False)
    output_buf.seek(0)

    re_res = await client.post(
        "/bulk/import/students",
        files={"file": ("reimport_students.xlsx", output_buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=school_principal_headers
    )
    assert re_res.status_code == 200, re_res.text
    re_data = re_res.json()
    assert re_data["imported"] == 1, f"re_data={re_data}"
    assert re_data["failed"] == 0

    # 5. Test reactivation: when an existing student was soft-deleted (is_active=False),
    # importing the same national_id reactivates the record without uq_students_national_id_school error
    s_to_delete = await gd_find_one(_db_session, "students", {"national_id": unique_nid, "school_id": tenant_a})
    assert s_to_delete is not None
    del_res = await client.post(
        "/students/bulk-delete",
        json={"student_ids": [s_to_delete["id"]]},
        headers=school_principal_headers
    )
    assert del_res.status_code == 200, del_res.text

    df_reactivate = pd.DataFrame([{
        "الاسم الأول": "طالب",
        "اسم العائلة": "محدث",
        "رقم الهوية": unique_nid,
        "جوال ولي الأمر": "0501234567",
        "الصف": "الصف الأول الابتدائي",
        "الفصل": "أ",
    }])
    buf_reactivate = io.BytesIO()
    df_reactivate.to_excel(buf_reactivate, index=False)
    buf_reactivate.seek(0)

    react_res = await client.post(
        "/bulk/import/students",
        files={"file": ("reactivate_students.xlsx", buf_reactivate.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=school_principal_headers
    )
    assert react_res.status_code == 200, react_res.text
    react_data = react_res.json()
    assert react_data["imported"] == 1, f"Expected 1 imported, got: {react_data}"
    assert react_data["failed"] == 0

    # Verify student is now reactivated and name updated
    reactivated_student = await gd_find_one(_db_session, "students", {"national_id": unique_nid, "school_id": tenant_a})
    assert reactivated_student is not None
    assert reactivated_student["is_active"] is True
    assert "محدث" in reactivated_student["full_name"]


@pytest.mark.asyncio
async def test_bulk_import_300_students_performance(
    client, school_principal_headers, tenant_a, _db_session
):
    """Ensure importing 300 students completes quickly and does not trigger proxy/client timeouts."""
    import time
    import pandas as pd
    import io

    rows = []
    base_nid = 2000000000
    # ``الأول`` is intentionally ambiguous across stages; use the
    # stage-bearing alias and keep each generated class within capacity.
    for i in range(300):
        rows.append({
            "الاسم الأول": f"طالب{i}",
            "اسم العائلة": f"العائلة{i}",
            "رقم الهوية": str(base_nid + i),
            "جوال ولي الأمر": f"050000{i:04d}",
            "الصف": "الأول الابتدائي",
            "الفصل": f"أ-{i // 30 + 1}",
        })

    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)

    start_time = time.time()
    res = await client.post(
        "/bulk/import/students",
        files={"file": ("perf_300_students.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=school_principal_headers
    )
    elapsed = time.time() - start_time

    assert res.status_code == 200, res.text
    data = res.json()
    assert data["success"] is True
    assert data["imported"] == 300
    assert data["failed"] == 0
    # Must complete in under 10 seconds (previously took 80+ seconds)
    assert elapsed < 10.0, f"Import took too long: {elapsed:.2f}s"

    # Also test rollback of the 300 students and their parents
    batch_id = data["batch_id"]
    rb_start = time.time()
    rb_res = await client.post(f"/bulk/batches/{batch_id}/rollback", headers=school_principal_headers)
    rb_elapsed = time.time() - rb_start

    assert rb_res.status_code == 200, rb_res.text
    rb_data = rb_res.json()
    assert rb_data["success"] is True
    assert rb_data["rolled_back_students"] == 300
    assert rb_data["rolled_back_parents"] == 300
    assert rb_elapsed < 5.0, f"Rollback took too long: {rb_elapsed:.2f}s"



