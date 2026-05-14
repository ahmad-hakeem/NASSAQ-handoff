"""Regression tests for Bug #372 — class roster delete must reflect
persisted state immediately on the post-delete refetch."""
import uuid
import pytest


@pytest.mark.asyncio
async def test_delete_student_refetched_roster_and_count(
    client, school_principal_headers, tenant_a, _db_session
):
    from engines.sql_utils import gd_insert, gd_find_one
    cls_id = str(uuid.uuid4())
    await gd_insert(_db_session, "classes", {"id": cls_id, "school_id": tenant_a, "name": "1A"})
    sids = []
    for _ in range(3):
        sid = str(uuid.uuid4())
        await gd_insert(_db_session, "students", {
            "id": sid, "school_id": tenant_a, "full_name": f"S-{sid[:6]}",
            "class_id": cls_id, "is_active": True,
        })
        sids.append(sid)
    await _db_session.flush()

    target = sids[0]
    r = await client.delete(f"/students/{target}", headers=school_principal_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("success") is True

    assert await gd_find_one(_db_session, "students", {"id": target}) is None

    r = await client.get(f"/classes/{cls_id}/students", headers=school_principal_headers)
    assert r.status_code == 200
    assert r.headers.get("cache-control") == "no-store"
    remaining = [s["id"] for s in r.json()]
    assert target not in remaining
    assert set(remaining) == set(sids[1:])

    r = await client.get(f"/classes/{cls_id}", headers=school_principal_headers)
    assert r.status_code == 200
    assert r.headers.get("cache-control") == "no-store"
    assert r.json().get("student_count") == 2


@pytest.mark.asyncio
async def test_delete_student_cross_tenant_404_no_mutation(
    client, school_principal_headers, tenant_b, _db_session
):
    from engines.sql_utils import gd_insert, gd_find_one
    other_sid = str(uuid.uuid4())
    await gd_insert(_db_session, "students", {
        "id": other_sid, "school_id": tenant_b, "full_name": "Other",
        "is_active": True,
    })
    await _db_session.flush()

    r = await client.delete(f"/students/{other_sid}", headers=school_principal_headers)
    assert r.status_code == 404
    assert await gd_find_one(_db_session, "students", {"id": other_sid}) is not None
