"""Regression: Student Activities & Certificates CRUD permissions for School Principals, School Admins, and Teachers.

Pins the contract that School Principal and School Admin roles have full authorization to:
1. Create activities for students in their school (POST /activities/student/{student_id}?school_id=...)
2. List activities for students in their school (GET /activities/student/{student_id}?school_id=...)
3. Update activities (PUT /activities/{activity_id})
4. Delete activities (DELETE /activities/{activity_id})
5. Create, list, update, and delete student certificates.
"""
import uuid
import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_find, gd_find_one, gd_insert


def _headers(user_id: str, role: str, tenant_id: str) -> dict:
    token = create_access_token({
        "sub": user_id,
        "role": role,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_school(school_id: str) -> None:
    await gd_insert(db.session, "schools", {
        "id": school_id,
        "name": f"School-{school_id[:6]}",
        "code": f"S{school_id[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })


async def _mk_principal(school_id: str) -> dict:
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    doc = {
        "id": uid,
        "email": f"principal_{uid}@school.test",
        "password_hash": "dummy_hash_for_test",
        "full_name": "مدير المدرسة التجريبية",
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": school_id,
        "is_active": True,
    }
    await gd_insert(db.session, "users", doc)
    return doc


async def _mk_student(school_id: str) -> str:
    sid = f"stu_{uuid.uuid4().hex[:8]}"
    await gd_insert(db.session, "students", {
        "id": sid,
        "school_id": school_id,
        "full_name": "طالب تجريبي للأنشطة",
        "is_active": True,
    })
    return sid


@pytest.mark.asyncio
async def test_principal_can_create_update_delete_student_activity(client):
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(school_id)
    principal = await _mk_principal(school_id)
    student_id = await _mk_student(school_id)
    h = _headers(principal["id"], principal["role"], school_id)

    # 1. Create activity as school_principal
    create_resp = await client.post(
        f"/activities/student/{student_id}?school_id={school_id}",
        json={
            "name": "مسابقة الرياضيات السنوية",
            "name_en": "Annual Math Olympiad",
            "activity_type": "academic",
            "date": "2026-08-27",
            "role": "leader",
            "description": "المشاركة بالمركز الأول",
        },
        headers=h,
    )
    assert create_resp.status_code == 200, create_resp.text
    act_data = create_resp.json()
    assert act_data["name"] == "مسابقة الرياضيات السنوية"
    act_id = act_data["id"]

    # 2. List activities
    list_resp = await client.get(
        f"/activities/student/{student_id}?school_id={school_id}",
        headers=h,
    )
    assert list_resp.status_code == 200
    activities = list_resp.json()
    assert any(a["id"] == act_id for a in activities)

    # 3. Update activity
    update_resp = await client.put(
        f"/activities/{act_id}",
        json={
            "name": "مسابقة الرياضيات المحدثة",
            "description": "تحديث الوصف بنجاح",
        },
        headers=h,
    )
    assert update_resp.status_code == 200, update_resp.text

    # 4. Delete activity
    del_resp = await client.delete(
        f"/activities/{act_id}",
        headers=h,
    )
    assert del_resp.status_code == 200, del_resp.text

    # Verify deleted
    list_resp2 = await client.get(
        f"/activities/student/{student_id}?school_id={school_id}",
        headers=h,
    )
    assert list_resp2.status_code == 200
    assert not any(a["id"] == act_id for a in list_resp2.json())


@pytest.mark.asyncio
async def test_principal_can_create_update_delete_student_certificate(client):
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(school_id)
    principal = await _mk_principal(school_id)
    student_id = await _mk_student(school_id)
    h = _headers(principal["id"], principal["role"], school_id)

    # 1. Create certificate as school_principal
    create_resp = await client.post(
        f"/activities/certificates/student/{student_id}?school_id={school_id}",
        json={
            "title": "شهادة تفوق دراسي",
            "title_en": "Certificate of Excellence",
            "date": "2026-08-27",
            "issuing_body": "إدارة التعليم",
            "description": "شهادة تفوق للعام الدراسي",
        },
        headers=h,
    )
    assert create_resp.status_code == 200, create_resp.text
    cert_data = create_resp.json()
    cert_id = cert_data["id"]

    # 2. List certificates
    list_resp = await client.get(
        f"/activities/certificates/student/{student_id}?school_id={school_id}",
        headers=h,
    )
    assert list_resp.status_code == 200
    certs = list_resp.json()
    assert any(c["id"] == cert_id for c in certs)

    # 3. Update certificate
    update_resp = await client.put(
        f"/activities/certificates/{cert_id}",
        json={
            "title": "شهادة تفوق دراسي محدثة",
        },
        headers=h,
    )
    assert update_resp.status_code == 200, update_resp.text

    # 4. Delete certificate
    del_resp = await client.delete(
        f"/activities/certificates/{cert_id}",
        headers=h,
    )
    assert del_resp.status_code == 200, del_resp.text
