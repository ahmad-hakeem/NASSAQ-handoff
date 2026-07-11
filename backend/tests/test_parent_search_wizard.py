"""Regression: Add-Student wizard "link to existing parent" search.

The bug (School Principal -> Add New Student -> "الربط بولي أمر حالي"):
searching for a registered parent returned "لم يتم العثور على نتائج" for
valid queries. Two independent root causes in
``GET /student-wizard/search-parents``:

1. ``email`` was never in the ``$or`` filter (only full_name + phone), so
   any email query returned nothing even for an exact stored address.
2. The route pre-escaped the query with ``re.escape()`` while gd_find's
   ``_sanitize_regex`` escapes AGAIN — double-escaping. Any query
   containing a regex-special character (``.``, ``@``, even a SPACE,
   which Python's re.escape escapes) became a pattern with literal
   backslashes that never matches: "إبراهيم الجهني" -> 0 rows,
   "x.y@gmail.com" -> 0 rows.

These tests pin down, for a school principal:
  * email search (exact + partial) finds the parent
  * full-name-with-space search finds the parent
  * single-word name and bare phone still work
  * leading/trailing whitespace is tolerated
  * Arabic-Indic digit phone queries are normalized to ASCII
  * regex metacharacters are treated literally (no 500, no false match)
  * tenant isolation: a parent in another school is never returned
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


async def _mk_parent(school_id: str, *, full_name: str, email: str,
                     phone: str) -> str:
    pid = str(uuid.uuid4())
    await gd_insert(db.session, "parents", {
        "id": pid,
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "school_id": school_id,
        "student_ids": [],
        "is_active": True,
    })
    return pid


async def _search(client, headers, q):
    resp = await client.get(
        "/student-wizard/search-parents",
        params={"q": q},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json().get("parents", [])


@pytest.fixture
async def seeded(client):
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(school_id)
    principal = await _mk_principal(school_id)
    tag = uuid.uuid4().hex[:6]
    email = f"ibrahym.aljhny.{tag}@example.com"
    phone = f"05{uuid.uuid4().int % 100000000:08d}"
    pid = await _mk_parent(
        school_id,
        full_name="إبراهيم الجهني",
        email=email,
        phone=phone,
    )
    h = _headers(principal["id"], principal["role"], school_id)
    return {
        "school_id": school_id,
        "headers": h,
        "parent_id": pid,
        "email": email,
        "phone": phone,
        "tag": tag,
    }


@pytest.mark.asyncio
async def test_search_by_exact_email(client, seeded):
    parents = await _search(client, seeded["headers"], seeded["email"])
    assert [p["id"] for p in parents] == [seeded["parent_id"]]


@pytest.mark.asyncio
async def test_search_by_partial_email(client, seeded):
    parents = await _search(
        client, seeded["headers"], f"ibrahym.aljhny.{seeded['tag']}")
    assert [p["id"] for p in parents] == [seeded["parent_id"]]


@pytest.mark.asyncio
async def test_search_by_full_name_with_space(client, seeded):
    parents = await _search(client, seeded["headers"], "إبراهيم الجهني")
    assert seeded["parent_id"] in [p["id"] for p in parents]


@pytest.mark.asyncio
async def test_search_by_single_name_word(client, seeded):
    parents = await _search(client, seeded["headers"], "الجهني")
    assert seeded["parent_id"] in [p["id"] for p in parents]


@pytest.mark.asyncio
async def test_search_by_phone(client, seeded):
    parents = await _search(client, seeded["headers"], seeded["phone"])
    assert [p["id"] for p in parents] == [seeded["parent_id"]]


@pytest.mark.asyncio
async def test_search_trims_whitespace(client, seeded):
    parents = await _search(
        client, seeded["headers"], f"  {seeded['email']}  ")
    assert [p["id"] for p in parents] == [seeded["parent_id"]]


@pytest.mark.asyncio
async def test_search_phone_with_arabic_indic_digits(client, seeded):
    western_to_arabic = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")
    arabic_phone = seeded["phone"].translate(western_to_arabic)
    parents = await _search(client, seeded["headers"], arabic_phone)
    assert [p["id"] for p in parents] == [seeded["parent_id"]]


@pytest.mark.asyncio
async def test_regex_metacharacters_are_literal(client, seeded):
    # ".*" must NOT act as a wildcard that matches everything.
    parents = await _search(client, seeded["headers"], ".*")
    assert parents == []
    # A malformed-regex-looking query must not 500.
    parents = await _search(client, seeded["headers"], "([a-z")
    assert parents == []


@pytest.mark.asyncio
async def test_tenant_isolation(client, seeded):
    other_school = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(other_school)
    other_principal = await _mk_principal(other_school)
    other_h = _headers(
        other_principal["id"], other_principal["role"], other_school)
    # The other school's principal must never see this parent.
    for q in (seeded["email"], "إبراهيم الجهني", seeded["phone"]):
        parents = await _search(client, other_h, q)
        assert seeded["parent_id"] not in [p["id"] for p in parents]
