"""
Regression tests for canonical stage/grade enforcement on real-school class
write paths (Task #839 — unify educational stage/grade).

The canonical model (`utils/canonical_grades.py`) defines exactly 3 stages and
12 grades. These tests lock the fail-closed behaviour on the three real-school
write routes and the create↔options parity that prevents false rejections:

  * POST /classes/create (wizard) — grade_id is authoritative, canonical label
    is persisted, off-list / empty / conflicting payloads are rejected, and an
    existing grade_levels row id is reused (linkage preserved).
  * POST /classes (non-wizard) — off-list grade_level rejected; canonical
    label persisted.
  * PUT /classes/{id} — off-list grade_level rejected; canonical label persisted.
  * /classes/options/grades emitted ids always succeed through /classes/create.
  * Independent-Teacher create is now canonicalized too — same fail-closed
    catalogue enforcement as real schools (IT stage/grade alignment).

The autouse `_db_session` fixture in conftest rolls back after each test, so no
rows persist and no cleanup is required.
"""
import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert, gd_find_one
from auth_scope import independent_workspace_id


_INVALID_MSG = "الصف المحدد غير صالح"


def _headers(user_id: str, role: str, tenant_id=None) -> dict:
    token = create_access_token({
        "sub": user_id,
        "role": role,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_school() -> str:
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await gd_insert(db.session, "schools", {
        "id": school_id,
        "name": "Test School",
        "code": school_id,
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    return school_id


async def _mk_principal(school_id: str) -> dict:
    uid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": school_id,
        "email": f"p-{uid}@t.test",
        "full_name": "Principal",
        "is_active": True,
        "password_hash": "x",
        "mfa_enrolled_at": now,
    })
    return {"id": uid, "school_id": school_id}


async def _mk_independent_teacher() -> dict:
    uid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    user = {
        "id": uid,
        "role": UserRole.INDEPENDENT_TEACHER.value,
        "tenant_id": None,
        "email": f"it-{uid}@t.test",
        "full_name": f"IT-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
        "mfa_enrolled_at": now,
    }
    await gd_insert(db.session, "users", user)
    wsid = independent_workspace_id(user)
    await gd_insert(db.session, "schools", {
        "id": wsid,
        "name": f"IT-Workspace-{uid[:6]}",
        "code": f"IT{uid[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })
    return {"id": uid, "wsid": wsid}


# ---------- POST /classes/create (wizard, real school) ----------

@pytest.mark.asyncio
async def test_wizard_create_canonical_numeric_grade_persists_label(client):
    """grade_id='7' + stage='middle' → 200, stored canonical label, id linkage."""
    school_id = await _mk_school()
    p = await _mk_principal(school_id)
    h = _headers(p["id"], UserRole.SCHOOL_PRINCIPAL.value, school_id)

    resp = await client.post("/classes/create", json={
        "name_ar": f"فصل {uuid.uuid4().hex[:5]}",
        "grade_id": "7",
        "stage": "middle",
        "section": "أ",
        "capacity": 30,
    }, headers=h)
    assert resp.status_code == 200, resp.text
    cid = resp.json()["class"]["id"]
    row = await gd_find_one(db.session, "classes", {"id": cid})
    assert row["grade_level"] == "الصف الأول المتوسط"
    assert row["grade_id"] == "7"
    assert row["school_id"] == school_id


@pytest.mark.asyncio
async def test_wizard_create_off_list_numeric_grade_rejected(client):
    """grade_id='99' is not a valid grade number → 404 (validate_stage_grade_pair)."""
    school_id = await _mk_school()
    p = await _mk_principal(school_id)
    h = _headers(p["id"], UserRole.SCHOOL_PRINCIPAL.value, school_id)

    resp = await client.post("/classes/create", json={
        "name_ar": "فصل غير صالح",
        "grade_id": "99",
        "capacity": 30,
    }, headers=h)
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_wizard_create_empty_grade_id_rejected(client):
    """Empty grade_id must not silently fall back to grade 1 → 422 safe Arabic."""
    school_id = await _mk_school()
    p = await _mk_principal(school_id)
    h = _headers(p["id"], UserRole.SCHOOL_PRINCIPAL.value, school_id)

    resp = await client.post("/classes/create", json={
        "name_ar": "فصل بدون صف",
        "grade_id": "",
        "capacity": 30,
    }, headers=h)
    assert resp.status_code == 422, resp.text
    assert _INVALID_MSG in resp.text


@pytest.mark.asyncio
async def test_wizard_create_conflicting_grade_and_grade_id_rejected(client):
    """grade_id authoritative: a caller-supplied grade that disagrees → 422."""
    school_id = await _mk_school()
    p = await _mk_principal(school_id)
    h = _headers(p["id"], UserRole.SCHOOL_PRINCIPAL.value, school_id)

    resp = await client.post("/classes/create", json={
        "name_ar": "فصل متعارض",
        "grade_id": "7",
        "grade": 1,
        "capacity": 30,
    }, headers=h)
    assert resp.status_code == 422, resp.text
    assert _INVALID_MSG in resp.text


@pytest.mark.asyncio
async def test_wizard_create_matching_grade_and_grade_id_accepted(client):
    """grade_id='7' + grade=7 (consistent) → 200, canonical persisted."""
    school_id = await _mk_school()
    p = await _mk_principal(school_id)
    h = _headers(p["id"], UserRole.SCHOOL_PRINCIPAL.value, school_id)

    resp = await client.post("/classes/create", json={
        "name_ar": f"فصل {uuid.uuid4().hex[:5]}",
        "grade_id": "7",
        "grade": 7,
        "capacity": 30,
    }, headers=h)
    assert resp.status_code == 200, resp.text
    cid = resp.json()["class"]["id"]
    row = await gd_find_one(db.session, "classes", {"id": cid})
    assert row["grade_level"] == "الصف الأول المتوسط"


@pytest.mark.asyncio
async def test_wizard_create_reuses_existing_grade_row_and_preserves_linkage(client):
    """A tenant grade_levels row (name='1') is matched and its id reused, with
    the canonical label persisted — existing linkage is preserved."""
    school_id = await _mk_school()
    p = await _mk_principal(school_id)
    h = _headers(p["id"], UserRole.SCHOOL_PRINCIPAL.value, school_id)

    grade_row_id = str(uuid.uuid4())
    await gd_insert(db.session, "grade_levels", {
        "id": grade_row_id,
        "school_id": school_id,
        "name": "1",            # real schools store the grade number here
        "code": "",
    })

    resp = await client.post("/classes/create", json={
        "name_ar": f"فصل {uuid.uuid4().hex[:5]}",
        "grade_id": grade_row_id,
        "capacity": 30,
    }, headers=h)
    assert resp.status_code == 200, resp.text
    cid = resp.json()["class"]["id"]
    row = await gd_find_one(db.session, "classes", {"id": cid})
    assert row["grade_level"] == "الصف الأول الابتدائي"
    assert row["grade_id"] == grade_row_id  # linkage to the real row preserved


@pytest.mark.asyncio
async def test_options_grades_ids_always_succeed_through_create(client):
    """Every id emitted by /classes/options/grades must be accepted by
    /classes/create (no false rejection for legacy-label tenants)."""
    school_id = await _mk_school()
    p = await _mk_principal(school_id)
    h = _headers(p["id"], UserRole.SCHOOL_PRINCIPAL.value, school_id)

    opts = await client.get("/classes/options/grades", headers=h)
    assert opts.status_code == 200, opts.text
    grades = opts.json()["grades"]
    assert len(grades) == 12
    # Every emitted grade must round-trip through create (catch per-grade
    # mapping regressions, not just one sample per stage).
    for g in grades:
        resp = await client.post("/classes/create", json={
            "name_ar": f"فصل {uuid.uuid4().hex[:6]}",
            "grade_id": g["id"],
            "stage": g["stage"],
            "capacity": 30,
        }, headers=h)
        assert resp.status_code == 200, (g, resp.text)
        cid = resp.json()["class"]["id"]
        row = await gd_find_one(db.session, "classes", {"id": cid})
        assert row["grade_level"] == g["name_ar"]


# ---------- POST /classes (non-wizard) ----------

@pytest.mark.asyncio
async def test_create_class_rejects_off_list_grade_level(client):
    school_id = await _mk_school()
    p = await _mk_principal(school_id)
    h = _headers(p["id"], UserRole.SCHOOL_PRINCIPAL.value, school_id)

    resp = await client.post("/classes", json={
        "name": "فصل غير صالح",
        "grade_level": "الصف السابع",  # legacy non-canonical wording
        "section": "أ",
        "capacity": 30,
    }, headers=h)
    assert resp.status_code == 422, resp.text
    assert _INVALID_MSG in resp.text


@pytest.mark.asyncio
async def test_create_class_persists_canonical_grade_level(client):
    school_id = await _mk_school()
    p = await _mk_principal(school_id)
    h = _headers(p["id"], UserRole.SCHOOL_PRINCIPAL.value, school_id)

    resp = await client.post("/classes", json={
        "name": f"فصل {uuid.uuid4().hex[:5]}",
        "grade_level": "الصف الثالث المتوسط",
        "section": "أ",
        "capacity": 30,
    }, headers=h)
    assert resp.status_code == 200, resp.text
    cid = resp.json()["id"]
    row = await gd_find_one(db.session, "classes", {"id": cid})
    assert row["grade_level"] == "الصف الثالث المتوسط"


# ---------- PUT /classes/{id} ----------

@pytest.mark.asyncio
async def test_update_class_rejects_off_list_grade_level(client):
    school_id = await _mk_school()
    p = await _mk_principal(school_id)
    h = _headers(p["id"], UserRole.SCHOOL_PRINCIPAL.value, school_id)

    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid,
        "school_id": school_id,
        "name": "فصل قائم",
        "grade_level": "الصف الأول المتوسط",
        "is_active": True,
    })

    resp = await client.put(f"/classes/{cid}", json={
        "grade_level": "الصف الثاني عشر",  # legacy non-canonical wording
    }, headers=h)
    assert resp.status_code == 422, resp.text
    assert _INVALID_MSG in resp.text
    # Stored value must be unchanged.
    row = await gd_find_one(db.session, "classes", {"id": cid})
    assert row["grade_level"] == "الصف الأول المتوسط"


@pytest.mark.asyncio
async def test_update_class_persists_canonical_grade_level(client):
    school_id = await _mk_school()
    p = await _mk_principal(school_id)
    h = _headers(p["id"], UserRole.SCHOOL_PRINCIPAL.value, school_id)

    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid,
        "school_id": school_id,
        "name": "فصل قائم",
        "grade_level": "الصف الأول المتوسط",
        "is_active": True,
    })

    resp = await client.put(f"/classes/{cid}", json={
        "grade_level": "الصف الثالث الثانوي",
    }, headers=h)
    assert resp.status_code == 200, resp.text
    row = await gd_find_one(db.session, "classes", {"id": cid})
    assert row["grade_level"] == "الصف الثالث الثانوي"


# ---------- Independent-Teacher canonicalization (now unified) ----------

@pytest.mark.asyncio
async def test_independent_teacher_create_is_canonicalized(client):
    """IT now uses the SAME canonical catalogue as real schools: a canonical
    grade id is accepted and the canonical Arabic label is persisted (no more
    custom/free-text grade storage)."""
    it = await _mk_independent_teacher()
    # Materialised workspace: the bearer carries the workspace id as tenant_id
    # (mirrors the post-bootstrap token; the gate reads it from the JWT).
    h = _headers(it["id"], UserRole.INDEPENDENT_TEACHER.value, it["wsid"])

    resp = await client.post("/classes/create", json={
        "name_ar": f"حلقة {uuid.uuid4().hex[:5]}",
        "grade_id": "1",
        "capacity": 10,
    }, headers=h)
    assert resp.status_code == 200, resp.text
    cid = resp.json()["class"]["id"]
    row = await gd_find_one(db.session, "classes", {"id": cid})
    # The canonical catalogue label is persisted, exactly like a real school.
    assert row["grade_level"] == "الصف الأول الابتدائي"
    assert row["school_id"] == it["wsid"]


@pytest.mark.asyncio
async def test_independent_teacher_create_off_list_grade_rejected(client):
    """A legacy / free-text grade row that does not resolve to the canonical
    catalogue is now rejected for IT too (fail-closed, safe Arabic 422)."""
    it = await _mk_independent_teacher()
    h = _headers(it["id"], UserRole.INDEPENDENT_TEACHER.value, it["wsid"])

    # Seed a non-canonical custom grade row so the tenant-scoped lookup
    # resolves but the canonical guard still refuses to persist it.
    label = "المرحلة المخصصة"
    await gd_insert(db.session, "grade_levels", {
        "id": label,
        "school_id": it["wsid"],
        "name": label,
        "name_ar": label,
        "code": "",
    })

    resp = await client.post("/classes/create", json={
        "name_ar": f"حلقة {uuid.uuid4().hex[:5]}",
        "grade_id": label,
        "capacity": 10,
    }, headers=h)
    assert resp.status_code == 422, resp.text
    assert _INVALID_MSG in resp.text


@pytest.mark.asyncio
async def test_create_class_rejects_foreign_tenant_grade_row_id(client):
    """A caller must not be able to resolve another tenant's grade_levels row by
    guessing its id. Every grade lookup on this route is tenant-scoped (the
    stage validator AND the canonical resolver), so a foreign UUID is rejected
    fail-closed (404 'grade not found in this school') and never reused."""
    # Victim tenant owns a perfectly canonical grade row.
    victim = await _mk_school()
    victim_grade_id = str(uuid.uuid4())
    await gd_insert(db.session, "grade_levels", {
        "id": victim_grade_id,
        "school_id": victim,
        "name": "1",
        "name_ar": "الصف الأول الابتدائي",
        "code": "",
    })

    # Attacker principal in a different tenant supplies the victim's row id.
    attacker = await _mk_school()
    p = await _mk_principal(attacker)
    h = _headers(p["id"], UserRole.SCHOOL_PRINCIPAL.value, attacker)

    resp = await client.post("/classes/create", json={
        "name_ar": "فصل مسروق",
        "grade_id": victim_grade_id,
        "capacity": 30,
    }, headers=h)
    assert resp.status_code == 404, resp.text
    # The class was NOT created in the attacker's tenant.
    assert await gd_find_one(db.session, "classes", {"school_id": attacker}) is None
