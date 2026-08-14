"""
Regression tests for Task #762 — false "رمز المدرسة مستخدم مسبقاً" on signup.

Covers:
  (a) A valid, unique new-school public signup succeeds (school + principal
      created once, auth token returned) with no false duplicate-code error.
  (b) An auto-generated school-code collision is recovered silently: the
      hardened insert regenerates a fresh unique code and still succeeds,
      leaving exactly one school row (clean rollback, no partial/orphan rows).
  (c) A genuinely duplicated operator-supplied custom code on the admin path
      is still rejected with the correct Arabic message.
"""
from __future__ import annotations

import uuid

import pytest

from dependencies import db
from engines.sql_utils import gd_insert, gd_find, gd_find_one, gd_count
import src.common.utils.school_code as sc


# ---------------------------------------------------------------------------
# (a) Successful unique public signup
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_public_signup_creates_unique_school(client):
    suffix = uuid.uuid4().hex[:10]
    school_name = f"مدرسة الاختبار {suffix}"
    payload = {
        "full_name": "مدير المدرسة التجريبية",
        "phone": f"05{uuid.uuid4().int % 100000000:08d}",
        "account_type": "school",
        "school_name": school_name,
        "school_email": f"school-{suffix}@example.com",
        "school_city": "الرياض",
        "school_address": "شارع الاختبار",
        "student_capacity": "500",
        "password": "StrongPass123",
    }

    resp = await client.post("/registration-requests", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data.get("account_type") == "school"
    assert data.get("access_token")
    assert data.get("user", {}).get("role") == "school_principal"
    code = data.get("school_code")
    assert code and code.startswith("NSS-SA-")

    # Exactly one school row + one principal user created.
    schools = await gd_find(db.session, "schools", {"name": school_name})
    assert len(schools) == 1
    assert schools[0]["code"] == code
    principal = await gd_find_one(db.session, "users", {"email": payload["school_email"]})
    assert principal is not None
    assert principal["role"] == "school_principal"


# ---------------------------------------------------------------------------
# (b) Auto-recovery from a forced code collision (no error, clean state)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_public_signup_recovers_from_code_collision(client, monkeypatch):
    prefix = sc.school_code_prefix("SA")
    collide_code = f"{prefix}9001"

    # Pre-occupy the code the generator will hand out on the first attempt.
    await gd_insert(db.session, "schools", {
        "id": str(uuid.uuid4()),
        "name": f"Occupant-{uuid.uuid4().hex[:6]}",
        "code": collide_code,
        "status": "active",
        "country": "SA",
    })

    async def fake_generate(session, country="SA", offset=0):
        # offset 0 collides; any retry yields a fresh unique code.
        return f"{prefix}{str(9001 + offset).zfill(4)}"

    monkeypatch.setattr(sc, "generate_school_code", fake_generate)

    suffix = uuid.uuid4().hex[:10]
    school_name = f"مدرسة التصادم {suffix}"
    payload = {
        "full_name": "مدير مدرسة التصادم",
        "phone": f"05{uuid.uuid4().int % 100000000:08d}",
        "account_type": "school",
        "school_name": school_name,
        "school_email": f"collide-{suffix}@example.com",
        "school_city": "جدة",
        "password": "StrongPass123",
    }

    resp = await client.post("/registration-requests", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Recovered to a different (fresh) code — not the colliding one.
    assert data["school_code"] != collide_code
    assert data["school_code"].startswith(prefix)

    # Clean rollback: exactly one school row for the new name, and the
    # colliding occupant row is untouched (still exactly one).
    new_schools = await gd_find(db.session, "schools", {"name": school_name})
    assert len(new_schools) == 1
    assert new_schools[0]["code"] == data["school_code"]
    occupants = await gd_count(db.session, "schools", {"code": collide_code})
    assert occupants == 1


# ---------------------------------------------------------------------------
# (b') Helper-level: insert regenerates on collision and never double-inserts
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_insert_helper_regenerates_on_collision(monkeypatch):
    prefix = sc.school_code_prefix("SA")
    taken = f"{prefix}8001"
    await gd_insert(db.session, "schools", {
        "id": str(uuid.uuid4()),
        "name": f"Taken-{uuid.uuid4().hex[:6]}",
        "code": taken,
        "status": "active",
        "country": "SA",
    })

    async def fake_generate(session, country="SA", offset=0):
        return f"{prefix}{str(8001 + offset).zfill(4)}"

    monkeypatch.setattr(sc, "generate_school_code", fake_generate)

    school_id = str(uuid.uuid4())
    name = f"Helper-{uuid.uuid4().hex[:8]}"

    def build(code):
        return {
            "id": school_id,
            "name": name,
            "code": code,
            "status": "active",
            "country": "SA",
        }

    code, obj = await sc.insert_school_with_unique_code(db.session, build, country="SA")
    assert code != taken
    rows = await gd_find(db.session, "schools", {"name": name})
    assert len(rows) == 1
    assert rows[0]["code"] == code


# ---------------------------------------------------------------------------
# (c) Genuine custom-duplicate-code rejection on the admin path
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_admin_custom_duplicate_code_rejected(client, platform_admin_headers):
    custom_code = f"CUSTOM-{uuid.uuid4().hex[:8].upper()}"
    await gd_insert(db.session, "schools", {
        "id": str(uuid.uuid4()),
        "name": f"Existing-{uuid.uuid4().hex[:6]}",
        "code": custom_code,
        "status": "active",
        "country": "SA",
    })

    resp = await client.post(
        "/schools",
        json={"name": f"مدرسة جديدة {uuid.uuid4().hex[:6]}", "code": custom_code},
        headers=platform_admin_headers,
    )
    assert resp.status_code == 400, resp.text
    message = resp.json().get("error", {}).get("message", "")
    assert "رمز المدرسة مستخدم مسبقاً" in message

    # No second school created for that code.
    assert await gd_count(db.session, "schools", {"code": custom_code}) == 1
