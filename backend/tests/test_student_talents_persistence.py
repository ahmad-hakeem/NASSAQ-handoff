"""Task #331 — Regression: student talents/character_traits/is_gifted persist.

Before this fix, the ``Student`` ORM model in ``pg_models.py`` had no
``talents`` / ``character_traits`` / ``is_gifted`` columns and no fallback
``data`` JSONB, so ``apply_updates`` silently dropped the fields written
by ``PUT /students/{id}``. The route returned 200 and the toast fired,
but the next ``GET`` came back with nothing. These tests pin down that:

1. As a school principal, ``PUT {talents: [...]}`` is reflected by a
   subsequent ``GET`` (and ``is_gifted`` flips to True automatically).
2. The cross-tenant write path still 404s for a foreign student
   (matches §8 inv. 3 — never confirms cross-tenant existence).
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


async def _mk_principal(school_id: str) -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": school_id,
        "email": f"p-{uid}@t.test",
        "full_name": "Principal",
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
async def test_principal_can_persist_student_talents(client):
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(school_id)
    principal = await _mk_principal(school_id)
    student_id = await _mk_student(school_id)
    h = _headers(principal["id"], principal["role"], school_id)

    # PUT a built-in talent.
    resp = await client.put(
        f"/students/{student_id}",
        json={"talents": ["scientific"]},
        headers=h,
    )
    assert resp.status_code == 200, resp.text

    # GET must reflect the persisted talent and flip is_gifted to True.
    resp_get = await client.get(f"/students/{student_id}", headers=h)
    assert resp_get.status_code == 200, resp_get.text
    body = resp_get.json()
    assert body.get("talents") == ["scientific"]
    assert body.get("is_gifted") is True

    # Adding a character trait on the same write path also persists.
    resp2 = await client.put(
        f"/students/{student_id}",
        json={"character_traits": ["leader"]},
        headers=h,
    )
    assert resp2.status_code == 200, resp2.text

    resp_get2 = await client.get(f"/students/{student_id}", headers=h)
    assert resp_get2.status_code == 200, resp_get2.text
    body2 = resp_get2.json()
    assert body2.get("character_traits") == ["leader"]
    # Talents must not have been clobbered by a partial update.
    assert body2.get("talents") == ["scientific"]

    # Removing the only talent flips is_gifted back to False.
    resp3 = await client.put(
        f"/students/{student_id}",
        json={"talents": []},
        headers=h,
    )
    assert resp3.status_code == 200, resp3.text

    resp_get3 = await client.get(f"/students/{student_id}", headers=h)
    body3 = resp_get3.json()
    assert body3.get("talents") == []
    assert body3.get("is_gifted") is False


@pytest.mark.asyncio
async def test_principal_cross_tenant_talents_update_returns_404(client):
    """A principal of school A trying to update a student in school B
    must get a clean 404 (not 200, not 403) — §8 inv. 3."""
    school_a = f"sch_{uuid.uuid4().hex[:8]}"
    school_b = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(school_a)
    await _mk_school(school_b)
    principal_a = await _mk_principal(school_a)
    student_b = await _mk_student(school_b)
    h_a = _headers(principal_a["id"], principal_a["role"], school_a)

    resp = await client.put(
        f"/students/{student_b}",
        json={"talents": ["scientific"]},
        headers=h_a,
    )
    assert resp.status_code == 404, resp.text
