"""Regression: student health_info persists via PUT /students/{id}.

Before this fix the student-update contract (``StudentUpdate``) had no
``health_info`` field and the ``PUT /students/{id}`` route never wrote it,
so a School Manager could never add or edit a student's Health & Notes
after creation. These tests pin down that:

1. A school principal can PUT a nested ``health_info`` object and a
   subsequent GET reflects the persisted values (create + prefill).
2. Editing existing ``health_info`` on the same write path persists, and
   leaves the rest of the student row untouched (no identity regression).
3. The cross-tenant write path returns a clean 404 (never 403/200) —
   §8 inv. 3, never confirms cross-tenant existence.
4. Unauthorized roles (teacher, parent) cannot update health.
"""
import uuid

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


def _headers(user_id: str, role: str, tenant_id) -> dict:
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


async def _mk_user(school_id: str, role: UserRole) -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": role.value,
        "tenant_id": school_id,
        "email": f"u-{uid}@t.test",
        "full_name": f"{role.value}",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    return user


async def _mk_student(school_id: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "full_name": "طالب اختبار",
        "school_id": school_id,
        "is_active": True,
    })
    return sid


@pytest.mark.asyncio
async def test_principal_can_persist_and_edit_health_info(client):
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(school_id)
    principal = await _mk_user(school_id, UserRole.SCHOOL_PRINCIPAL)
    student_id = await _mk_student(school_id)
    h = _headers(principal["id"], principal["role"], school_id)

    # Create health data on a student that had none.
    health = {
        "blood_type": "O+",
        "has_chronic_conditions": True,
        "chronic_conditions": "Asthma",
        "has_allergies": True,
        "allergies": "Peanuts",
        "has_disabilities": False,
        "disabilities": None,
        "current_medications": "Inhaler",
        "requires_special_care": True,
        "special_care_notes": "Keep inhaler nearby",
        "emergency_medical_notes": "Call guardian first",
    }
    resp = await client.put(
        f"/students/{student_id}",
        json={"health_info": health},
        headers=h,
    )
    assert resp.status_code == 200, resp.text

    # GET reflects persisted health (prefill source).
    resp_get = await client.get(f"/students/{student_id}", headers=h)
    assert resp_get.status_code == 200, resp_get.text
    body = resp_get.json()
    hi = body.get("health_info") or {}
    assert hi.get("blood_type") == "O+"
    assert hi.get("has_chronic_conditions") is True
    assert hi.get("chronic_conditions") == "Asthma"
    assert hi.get("has_allergies") is True
    assert hi.get("allergies") == "Peanuts"
    assert hi.get("emergency_medical_notes") == "Call guardian first"

    # Editing existing health persists, and identity is untouched.
    edited = dict(health, blood_type="A-", emergency_medical_notes="Updated note")
    resp2 = await client.put(
        f"/students/{student_id}",
        json={"health_info": edited},
        headers=h,
    )
    assert resp2.status_code == 200, resp2.text

    resp_get2 = await client.get(f"/students/{student_id}", headers=h)
    assert resp_get2.status_code == 200, resp_get2.text
    body2 = resp_get2.json()
    hi2 = body2.get("health_info") or {}
    assert hi2.get("blood_type") == "A-"
    assert hi2.get("emergency_medical_notes") == "Updated note"
    assert body2.get("full_name") == "طالب اختبار"


@pytest.mark.asyncio
async def test_principal_cross_tenant_health_update_returns_404(client):
    """Principal of school A updating health on a school-B student must
    get a clean 404 (not 200, not 403) — §8 inv. 3."""
    school_a = f"sch_{uuid.uuid4().hex[:8]}"
    school_b = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(school_a)
    await _mk_school(school_b)
    principal_a = await _mk_user(school_a, UserRole.SCHOOL_PRINCIPAL)
    student_b = await _mk_student(school_b)
    h_a = _headers(principal_a["id"], principal_a["role"], school_a)

    resp = await client.put(
        f"/students/{student_b}",
        json={"health_info": {"blood_type": "O+"}},
        headers=h_a,
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_teacher_cannot_update_health(client):
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(school_id)
    teacher = await _mk_user(school_id, UserRole.TEACHER)
    student_id = await _mk_student(school_id)
    h = _headers(teacher["id"], teacher["role"], school_id)

    resp = await client.put(
        f"/students/{student_id}",
        json={"health_info": {"blood_type": "O+"}},
        headers=h,
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_parent_cannot_update_health(client):
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(school_id)
    parent = await _mk_user(school_id, UserRole.PARENT)
    student_id = await _mk_student(school_id)
    h = _headers(parent["id"], parent["role"], school_id)

    resp = await client.put(
        f"/students/{student_id}",
        json={"health_info": {"blood_type": "O+"}},
        headers=h,
    )
    assert resp.status_code == 403, resp.text
