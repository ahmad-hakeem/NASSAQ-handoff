"""Regression: linking a guardian to an EXISTING student persists the
relationship + email AND provisions/links a real parent account.

The bug (reproduced on Noor-imported students that arrive with empty
guardian data): ``PUT /students/{id}`` -> ``update_student`` mapped only
``parent_name`` + ``parent_phone`` onto the students row. It dropped
``parent_email`` and ``parent_relationship`` entirely and never created or
linked a ``parents`` / parent-``users`` account. So a School Manager could
type all four fields, see a success toast, and on reload find the email
and relationship gone and no parent portal account created.

The fix routes real-school guardian edits through the SAME canonical
service the manual student-creation wizard uses
(``services/parent_linking.py``), inside a savepoint, and enriches the
single-student GET from the canonical ``guardian_links`` store (the
students table has no ``parent_relationship`` column).

These tests pin down, for a real school (principal):
  1. A full guardian add to an empty-guardian student persists email +
     relationship, creates a parents row + parent user, mirrors contact
     onto the student, and the GET reflects all of it.
  2. The operation is idempotent (no duplicate parents / guardian_links).
  3. A relationship-only follow-up edit updates the existing link.
  4. Siblings with the same phone share ONE per-school parents row.
  5. A same phone in another tenant is NOT reused (tenant isolation).
  6. Reusing a non-parent email fails 409 with NO partial writes.
  7. A cross-tenant write still 404s and provisions nothing (§8 inv. 3).
"""
import uuid

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_find, gd_find_one, gd_insert


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


async def _mk_empty_guardian_student(school_id: str) -> str:
    """Seed a Noor-style student: NO parent name/phone/email/id at all."""
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "full_name": "طالب اختبار",
        "school_id": school_id,
        "is_active": True,
    })
    return sid


# ---------------------------------------------------------------------------
# 1) Full guardian add to an empty-guardian student
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_principal_links_full_guardian_to_empty_student(client):
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(school_id)
    principal = await _mk_principal(school_id)
    sid = await _mk_empty_guardian_student(school_id)
    h = _headers(principal["id"], principal["role"], school_id)

    email = f"guardian-{uuid.uuid4().hex[:8]}@example.com"
    phone = f"05{uuid.uuid4().int % 100000000:08d}"
    resp = await client.put(
        f"/students/{sid}",
        json={
            "parent_name": "أبو محمد",
            "parent_phone": phone,
            "parent_email": email,
            "parent_relationship": "father",
        },
        headers=h,
    )
    assert resp.status_code == 200, resp.text

    # --- GET reflects relationship + email (the dropped fields) ---
    got = await client.get(f"/students/{sid}", headers=h)
    assert got.status_code == 200, got.text
    body = got.json()
    assert body.get("parent_relationship") == "father"
    assert body.get("parent_email") == email
    assert body.get("parent_name") == "أبو محمد"
    assert body.get("parent_phone") == phone
    assert body.get("parent_id")

    # --- A per-school parents row was created ---
    parents = await gd_find(db.session, "parents", {"email": email, "school_id": school_id}, limit=5)
    assert len(parents) == 1, parents
    parent = parents[0]
    assert sid in (parent.get("student_ids") or [])

    # --- A parent users account was created (login material) ---
    parent_user = await gd_find_one(db.session, "users", {"email": email})
    assert parent_user is not None
    assert parent_user.get("role") == UserRole.PARENT.value

    # --- The canonical relationship lives in guardian_links, scoped ---
    links = await gd_find(db.session, "guardian_links", {"student_id": sid, "is_active": True}, limit=5)
    assert len(links) == 1, links
    link = links[0]
    assert link.get("relationship") == "father"
    assert link.get("tenant_id") == school_id
    assert link.get("parent_ref") == parent_user.get("id")
    assert link.get("parent_id") == parent.get("id")

    # --- The students row mirror points at the parent ---
    student_row = await gd_find_one(db.session, "students", {"id": sid, "school_id": school_id})
    assert student_row.get("parent_id") == parent.get("id")
    assert student_row.get("parent_email") == email


# ---------------------------------------------------------------------------
# 2) Idempotency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_guardian_link_is_idempotent(client):
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(school_id)
    principal = await _mk_principal(school_id)
    sid = await _mk_empty_guardian_student(school_id)
    h = _headers(principal["id"], principal["role"], school_id)

    email = f"guardian-{uuid.uuid4().hex[:8]}@example.com"
    phone = f"05{uuid.uuid4().int % 100000000:08d}"
    payload = {
        "parent_name": "أم خالد",
        "parent_phone": phone,
        "parent_email": email,
        "parent_relationship": "mother",
    }

    r1 = await client.put(f"/students/{sid}", json=payload, headers=h)
    assert r1.status_code == 200, r1.text
    r2 = await client.put(f"/students/{sid}", json=payload, headers=h)
    assert r2.status_code == 200, r2.text

    parents = await gd_find(db.session, "parents", {"email": email, "school_id": school_id}, limit=5)
    assert len(parents) == 1, "second identical save must not duplicate the parent"
    links = await gd_find(db.session, "guardian_links", {"student_id": sid, "is_active": True}, limit=5)
    assert len(links) == 1, "second identical save must not duplicate the guardian link"
    users = await gd_find(db.session, "users", {"email": email}, limit=5)
    assert len(users) == 1, "second identical save must not duplicate the parent user"


# ---------------------------------------------------------------------------
# 3) Relationship-only follow-up edit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_relationship_only_edit_updates_existing_link(client):
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(school_id)
    principal = await _mk_principal(school_id)
    sid = await _mk_empty_guardian_student(school_id)
    h = _headers(principal["id"], principal["role"], school_id)

    email = f"guardian-{uuid.uuid4().hex[:8]}@example.com"
    phone = f"05{uuid.uuid4().int % 100000000:08d}"
    r1 = await client.put(
        f"/students/{sid}",
        json={"parent_name": "والد", "parent_phone": phone, "parent_email": email,
              "parent_relationship": "father"},
        headers=h,
    )
    assert r1.status_code == 200, r1.text

    # Change ONLY the relationship — the student row already mirrors the
    # other fields, so the helper must match the existing parent by phone.
    r2 = await client.put(f"/students/{sid}", json={"parent_relationship": "guardian"}, headers=h)
    assert r2.status_code == 200, r2.text

    got = await client.get(f"/students/{sid}", headers=h)
    assert got.json().get("parent_relationship") == "guardian"

    links = await gd_find(db.session, "guardian_links", {"student_id": sid, "is_active": True}, limit=5)
    assert len(links) == 1
    assert links[0].get("relationship") == "guardian"
    parents = await gd_find(db.session, "parents", {"phone": phone, "school_id": school_id}, limit=5)
    assert len(parents) == 1, "relationship edit must not spawn a new parent"


# ---------------------------------------------------------------------------
# 4) Sibling dedupe within a school
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_siblings_same_phone_share_one_parent(client):
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(school_id)
    principal = await _mk_principal(school_id)
    sid1 = await _mk_empty_guardian_student(school_id)
    sid2 = await _mk_empty_guardian_student(school_id)
    h = _headers(principal["id"], principal["role"], school_id)

    phone = f"05{uuid.uuid4().int % 100000000:08d}"
    r1 = await client.put(
        f"/students/{sid1}",
        json={"parent_name": "الوالد", "parent_phone": phone, "parent_relationship": "father"},
        headers=h,
    )
    assert r1.status_code == 200, r1.text
    # Second child, same phone but a different typed name — must link to the
    # SAME parent and must NOT overwrite the established name.
    r2 = await client.put(
        f"/students/{sid2}",
        json={"parent_name": "اسم مختلف", "parent_phone": phone, "parent_relationship": "father"},
        headers=h,
    )
    assert r2.status_code == 200, r2.text

    parents = await gd_find(db.session, "parents", {"phone": phone, "school_id": school_id}, limit=5)
    assert len(parents) == 1, "siblings must share one per-school parents row"
    parent = parents[0]
    assert parent.get("full_name") == "الوالد", "conservative fill must not overwrite an established name"
    assert sid1 in (parent.get("student_ids") or [])
    assert sid2 in (parent.get("student_ids") or [])

    s2 = await gd_find_one(db.session, "students", {"id": sid2, "school_id": school_id})
    assert s2.get("parent_id") == parent.get("id")


# ---------------------------------------------------------------------------
# 5) Cross-tenant phone is NOT reused
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_same_phone_other_tenant_not_reused(client):
    school_a = f"sch_{uuid.uuid4().hex[:8]}"
    school_b = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(school_a)
    await _mk_school(school_b)
    principal_a = await _mk_principal(school_a)
    h_a = _headers(principal_a["id"], principal_a["role"], school_a)

    phone = f"05{uuid.uuid4().int % 100000000:08d}"
    # A parent with this phone already exists in tenant B.
    await gd_insert(db.session, "parents", {
        "id": str(uuid.uuid4()),
        "full_name": "Parent-B",
        "phone": phone,
        "school_id": school_b,
        "is_active": True,
    })

    sid_a = await _mk_empty_guardian_student(school_a)
    r = await client.put(
        f"/students/{sid_a}",
        json={"parent_name": "والد أ", "parent_phone": phone, "parent_relationship": "father"},
        headers=h_a,
    )
    assert r.status_code == 200, r.text

    a_parents = await gd_find(db.session, "parents", {"phone": phone, "school_id": school_a}, limit=5)
    b_parents = await gd_find(db.session, "parents", {"phone": phone, "school_id": school_b}, limit=5)
    assert len(a_parents) == 1, "tenant A must get its OWN parents row"
    assert len(b_parents) == 1, "tenant B's parents row must be untouched"
    assert a_parents[0]["id"] != b_parents[0]["id"]


# ---------------------------------------------------------------------------
# 6) Non-parent email conflict → 409, no partial writes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_parent_email_conflict_409_no_partial_writes(client):
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(school_id)
    principal = await _mk_principal(school_id)
    sid = await _mk_empty_guardian_student(school_id)
    h = _headers(principal["id"], principal["role"], school_id)

    # An email already owned by a NON-parent (teacher) account.
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    await gd_insert(db.session, "users", {
        "id": str(uuid.uuid4()),
        "role": UserRole.TEACHER.value,
        "tenant_id": school_id,
        "email": teacher_email,
        "full_name": "Teacher",
        "is_active": True,
        "password_hash": "x",
    })

    r = await client.put(
        f"/students/{sid}",
        json={"parent_name": "والد", "parent_phone": "0500000000", "parent_email": teacher_email,
              "parent_relationship": "father"},
        headers=h,
    )
    assert r.status_code == 409, r.text

    # No parents row, no guardian_link, and the student is untouched.
    parents = await gd_find(db.session, "parents", {"email": teacher_email, "school_id": school_id}, limit=5)
    assert parents == []
    links = await gd_find(db.session, "guardian_links", {"student_id": sid}, limit=5)
    assert links == []
    student_row = await gd_find_one(db.session, "students", {"id": sid, "school_id": school_id})
    assert not student_row.get("parent_id")
    assert not student_row.get("parent_email")


# ---------------------------------------------------------------------------
# 6b) Phone matches one parent, email belongs to a DIFFERENT parent -> 409
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_phone_email_identity_conflict_409_no_misbind(client):
    """The phone matches Parent B but the typed email belongs to Parent A.
    The service must refuse (409) instead of binding the student's guardian
    link to Parent A's account while parent_id points at Parent B."""
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(school_id)
    principal = await _mk_principal(school_id)
    h = _headers(principal["id"], principal["role"], school_id)

    phone_b = f"05{uuid.uuid4().int % 100000000:08d}"
    email_a = f"parentA-{uuid.uuid4().hex[:8]}@example.com"

    # Parent A: a real parent user that owns email_a (different phone).
    user_a_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": user_a_id,
        "role": UserRole.PARENT.value,
        "tenant_id": school_id,
        "email": email_a,
        "full_name": "Parent A",
        "is_active": True,
        "password_hash": "x",
    })
    await gd_insert(db.session, "parents", {
        "id": str(uuid.uuid4()),
        "user_id": user_a_id,
        "full_name": "Parent A",
        "email": email_a,
        "phone": f"05{uuid.uuid4().int % 100000000:08d}",
        "school_id": school_id,
        "is_active": True,
    })
    # Parent B: owns phone_b, no email on record.
    parent_b_id = str(uuid.uuid4())
    await gd_insert(db.session, "parents", {
        "id": parent_b_id,
        "full_name": "Parent B",
        "phone": phone_b,
        "school_id": school_id,
        "is_active": True,
    })

    sid = await _mk_empty_guardian_student(school_id)
    r = await client.put(
        f"/students/{sid}",
        json={"parent_name": "Parent B", "parent_phone": phone_b, "parent_email": email_a,
              "parent_relationship": "father"},
        headers=h,
    )
    assert r.status_code == 409, r.text

    # No mis-binding: no guardian_link for the student, Parent B's email
    # was not overwritten with Parent A's email, student untouched.
    links = await gd_find(db.session, "guardian_links", {"student_id": sid}, limit=5)
    assert links == []
    parent_b = await gd_find_one(db.session, "parents", {"id": parent_b_id, "school_id": school_id})
    assert not parent_b.get("email")
    student_row = await gd_find_one(db.session, "students", {"id": sid, "school_id": school_id})
    assert not student_row.get("parent_id")


@pytest.mark.asyncio
async def test_phone_match_email_owned_by_non_parent_409(client):
    """Phone matches an existing parent, but the typed email belongs to a
    NON-parent (teacher) account -> 409, nothing bound."""
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(school_id)
    principal = await _mk_principal(school_id)
    h = _headers(principal["id"], principal["role"], school_id)

    phone = f"05{uuid.uuid4().int % 100000000:08d}"
    teacher_email = f"teacher-{uuid.uuid4().hex[:8]}@example.com"
    await gd_insert(db.session, "users", {
        "id": str(uuid.uuid4()),
        "role": UserRole.TEACHER.value,
        "tenant_id": school_id,
        "email": teacher_email,
        "full_name": "Teacher",
        "is_active": True,
        "password_hash": "x",
    })
    parent_id = str(uuid.uuid4())
    await gd_insert(db.session, "parents", {
        "id": parent_id,
        "full_name": "والد قائم",
        "phone": phone,
        "school_id": school_id,
        "is_active": True,
    })

    sid = await _mk_empty_guardian_student(school_id)
    r = await client.put(
        f"/students/{sid}",
        json={"parent_name": "والد قائم", "parent_phone": phone, "parent_email": teacher_email,
              "parent_relationship": "father"},
        headers=h,
    )
    assert r.status_code == 409, r.text
    links = await gd_find(db.session, "guardian_links", {"student_id": sid}, limit=5)
    assert links == []
    parent_row = await gd_find_one(db.session, "parents", {"id": parent_id, "school_id": school_id})
    assert not parent_row.get("email")


# ---------------------------------------------------------------------------
# 7) Cross-tenant write 404s and provisions nothing (§8 inv. 3)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cross_tenant_guardian_write_404_no_provision(client):
    school_a = f"sch_{uuid.uuid4().hex[:8]}"
    school_b = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(school_a)
    await _mk_school(school_b)
    principal_a = await _mk_principal(school_a)
    sid_b = await _mk_empty_guardian_student(school_b)
    h_a = _headers(principal_a["id"], principal_a["role"], school_a)

    email = f"guardian-{uuid.uuid4().hex[:8]}@example.com"
    r = await client.put(
        f"/students/{sid_b}",
        json={"parent_name": "والد", "parent_phone": "0500000000", "parent_email": email,
              "parent_relationship": "father"},
        headers=h_a,
    )
    assert r.status_code == 404, r.text

    # Nothing was provisioned for the foreign student.
    parents = await gd_find(db.session, "parents", {"email": email}, limit=5)
    assert parents == []
    links = await gd_find(db.session, "guardian_links", {"student_id": sid_b}, limit=5)
    assert links == []


# ---------------------------------------------------------------------------
# 8) Editing newly added parent's info updates in-place (no duplicate parents)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_editing_newly_added_parent_updates_in_place_no_duplicate(client):
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(school_id)
    principal = await _mk_principal(school_id)
    sid = await _mk_empty_guardian_student(school_id)
    h = _headers(principal["id"], principal["role"], school_id)

    phone1 = f"05{uuid.uuid4().int % 100000000:08d}"
    phone2 = f"05{uuid.uuid4().int % 100000000:08d}"

    # Step 1: Principal adds parent to student
    r1 = await client.put(
        f"/students/{sid}",
        json={
            "parent_name": "ابو خليفة",
            "parent_phone": phone1,
            "parent_relationship": "father",
        },
        headers=h,
    )
    assert r1.status_code == 200, r1.text

    parents1 = await gd_find(db.session, "parents", {"school_id": school_id})
    assert len(parents1) == 1, "Must have exactly 1 parent after step 1"
    initial_parent_id = parents1[0]["id"]
    assert parents1[0]["full_name"] == "ابو خليفة"
    assert parents1[0]["phone"] == phone1

    # Step 2: Principal re-opens student profile and edits parent info (changing name and phone)
    r2 = await client.put(
        f"/students/{sid}",
        json={
            "parent_name": "ابو خليفة المحدث",
            "parent_phone": phone2,
            "parent_relationship": "father",
        },
        headers=h,
    )
    assert r2.status_code == 200, r2.text

    # Step 3: Verify no duplicate parent is created in parents list
    parents2 = await gd_find(db.session, "parents", {"school_id": school_id})
    assert len(parents2) == 1, f"Must have only 1 parent in school, but found {len(parents2)}"
    updated_parent = parents2[0]
    assert updated_parent["id"] == initial_parent_id, "Must update the same parent record"
    assert updated_parent["full_name"] == "ابو خليفة المحدث"
    assert updated_parent["phone"] == phone2

    # Verify student record reflects updated parent info
    student_row = await gd_find_one(db.session, "students", {"id": sid, "school_id": school_id})
    assert student_row["parent_id"] == initial_parent_id
    assert student_row["parent_name"] == "ابو خليفة المحدث"
    assert student_row["parent_phone"] == phone2

    # Verify GET /parents returns only 1 parent card
    parents_resp = await client.get("/parents", headers=h)
    assert parents_resp.status_code == 200, parents_resp.text
    parents_list = parents_resp.json()
    assert len(parents_list) == 1, f"Expected 1 parent card in GET /parents, got {len(parents_list)}"
    assert parents_list[0]["id"] == initial_parent_id
    assert parents_list[0]["full_name"] == "ابو خليفة المحدث"
    assert parents_list[0]["phone"] == phone2


# ---------------------------------------------------------------------------
# 9) Updating parent info via /principal/parent/{id}/basic-info syncs to student profile
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_updating_parent_from_parents_module_syncs_to_student_profile(client):
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(school_id)
    principal = await _mk_principal(school_id)
    sid = await _mk_empty_guardian_student(school_id)
    h = _headers(principal["id"], principal["role"], school_id)

    old_phone = "0550000422"
    new_phone = "0550000211"

    # Step 1: Link parent initially to student
    r1 = await client.put(
        f"/students/{sid}",
        json={
            "parent_name": "ابراهيم زهراني",
            "parent_phone": old_phone,
            "parent_relationship": "father",
        },
        headers=h,
    )
    assert r1.status_code == 200, r1.text

    # Verify student profile GET reflects initial parent phone
    s_resp1 = await client.get(f"/students/{sid}", headers=h)
    assert s_resp1.status_code == 200
    s_data1 = s_resp1.json()
    assert s_data1["parent_phone"] == old_phone
    parent_id = s_data1["parent_id"]

    # Step 2: Principal updates parent from Parents module (/principal/parent/{id}/basic-info)
    p_update_resp = await client.put(
        f"/principal/parent/{parent_id}/basic-info",
        json={
            "full_name": "ابراهيم زهراني المعدل",
            "phone": new_phone,
        },
        headers=h,
    )
    assert p_update_resp.status_code == 200, p_update_resp.text

    # Step 3: Verify parent profile in parents module reflects new phone
    parent_profile_resp = await client.get(f"/principal/parent/{parent_id}/full-profile", headers=h)
    assert parent_profile_resp.status_code == 200
    p_prof = parent_profile_resp.json()["profile"]
    assert p_prof["contact_info"]["phone"] == new_phone
    assert p_prof["basic_info"]["full_name"] == "ابراهيم زهراني المعدل"

    # Step 4: Verify student profile dynamically reflects new parent phone and name
    s_resp2 = await client.get(f"/students/{sid}", headers=h)
    assert s_resp2.status_code == 200
    s_data2 = s_resp2.json()
    assert s_data2["parent_phone"] == new_phone, f"Expected {new_phone}, got {s_data2.get('parent_phone')}"
    assert s_data2["parent_name"] == "ابراهيم زهراني المعدل"

    # Step 5: Verify students DB row is also synced
    student_row = await gd_find_one(db.session, "students", {"id": sid, "school_id": school_id})
    assert student_row["parent_phone"] == new_phone
    assert student_row["parent_name"] == "ابراهيم زهراني المعدل"


# ---------------------------------------------------------------------------
# 10) Editing student data persists National ID and personal fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_editing_student_persists_national_id_and_personal_fields(client):
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(school_id)
    principal = await _mk_principal(school_id)
    sid = await _mk_empty_guardian_student(school_id)
    h = _headers(principal["id"], principal["role"], school_id)

    national_id = "1231654512163"

    # Step 1: Verify student initially has no national_id
    got1 = await client.get(f"/students/{sid}", headers=h)
    assert got1.status_code == 200
    assert got1.json().get("national_id") is None

    # Step 2: Update student with National ID and Gender
    update_resp = await client.put(
        f"/students/{sid}",
        json={
            "national_id": national_id,
            "gender": "male",
            "full_name": "أحمد ابراهيم احمد الخليفه",
        },
        headers=h,
    )
    assert update_resp.status_code == 200, update_resp.text

    # Step 3: Verify GET /students/{id} returns updated national_id and gender
    got2 = await client.get(f"/students/{sid}", headers=h)
    assert got2.status_code == 200
    s_data = got2.json()
    assert s_data.get("national_id") == national_id, f"Expected {national_id}, got {s_data.get('national_id')}"
    assert s_data.get("gender") == "male"
    assert s_data.get("full_name") == "أحمد ابراهيم احمد الخليفه"

    # Step 4: Verify DB row persists national_id
    student_row = await gd_find_one(db.session, "students", {"id": sid, "school_id": school_id})
    assert student_row.get("national_id") == national_id
    assert student_row.get("gender") == "male"


# ---------------------------------------------------------------------------
# 11) Student API returns parent object relation (Single Source of Truth)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_student_api_returns_parent_object_relation(client):
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(school_id)
    principal = await _mk_principal(school_id)
    sid = await _mk_empty_guardian_student(school_id)
    h = _headers(principal["id"], principal["role"], school_id)

    # Step 1: Link a parent to student
    r1 = await client.put(
        f"/students/{sid}",
        json={
            "parent_name": "ابو خليفة 3",
            "parent_phone": "05454545",
            "parent_email": "p@gmail.com",
            "parent_relationship": "guardian",
        },
        headers=h,
    )
    assert r1.status_code == 200, r1.text

    # Step 2: Fetch student profile and verify `parent` object relation exists
    res = await client.get(f"/students/{sid}", headers=h)
    assert res.status_code == 200, res.text
    data = res.json()

    # Verify flat fields are populated
    assert data["parent_name"] == "ابو خليفة 3"
    assert data["parent_phone"] == "05454545"
    assert data["parent_email"] == "p@gmail.com"
    assert data["parent_relationship"] == "guardian"
    assert data["parent_id"]

    # Verify parent object relation
    assert "parent" in data
    assert data["parent"] is not None
    p_obj = data["parent"]
    assert p_obj["id"] == data["parent_id"]
    assert p_obj["full_name"] == "ابو خليفة 3"
    assert p_obj["phone"] == "05454545"
    assert p_obj["email"] == "p@gmail.com"
    assert p_obj["relationship"] == "guardian"

    # Step 3: Modify parent in parents table directly or via basic-info
    p_id = data["parent_id"]
    await client.put(
        f"/principal/parent/{p_id}/basic-info",
        json={
            "full_name": "ابو خليفة 3 المحدث",
            "phone": "0545454599",
        },
        headers=h,
    )

    # Step 4: Verify student profile dynamically reflects updated parent object relation
    res2 = await client.get(f"/students/{sid}", headers=h)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["parent"]["full_name"] == "ابو خليفة 3 المحدث"
    assert data2["parent"]["phone"] == "0545454599"
    assert data2["parent_name"] == "ابو خليفة 3 المحدث"
    assert data2["parent_phone"] == "0545454599"
