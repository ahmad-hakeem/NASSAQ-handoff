"""Automated coverage for the "Generate with Hakim" subject-code suggestion.

The suggestion feature was previously verified only by hand. The deterministic
normalizer + collision-avoidance in
``backend/routes/academics_subject_routes.py`` is the authority for the code's
format and uniqueness, so these tests lock down:

1. ``_code_letters`` / ``_build_subject_code`` pure-function behaviour:
   English-name prefix, Arabic-only + category fallback, generic ``SUBJ``
   fallback, numeric-suffix bump on collision, and LLM-prefix sanitization
   (junk characters stripped, LLM takes precedence over the English name).
2. The ``POST /api/subjects/hakim-code`` endpoint: role gating
   (principal/admin allowed, teacher/parent/student rejected), school-scoping
   of the collision set (another tenant's codes never widen the set), and the
   ``NAME_REQUIRED`` envelope when no name is supplied.

The optional LLM refinement is patched out so the deterministic path is what is
under test and no network call happens.
"""
from __future__ import annotations

import uuid

import pytest

from dependencies import db, UserRole
from engines.sql_utils import gd_insert
from routes.academics_subject_routes import _build_subject_code, _code_letters
from tests.conftest import _mk_user, _headers


# ---------------------------------------------------------------------------
# 1. Pure-function unit tests — _code_letters
# ---------------------------------------------------------------------------


def test_code_letters_uppercases_and_strips_non_letters():
    # Junk chars, digits and spaces are dropped; result is upper A-Z only.
    assert _code_letters("ma-th_99!!") == "MATH"
    assert _code_letters("Science") == "SCIE"  # first 4 letters, uppercased


def test_code_letters_caps_at_limit():
    assert _code_letters("Mathematics") == "MATH"
    assert _code_letters("Mathematics", limit=2) == "MA"


def test_code_letters_empty_for_falsy_or_no_letters():
    assert _code_letters(None) == ""
    assert _code_letters("") == ""
    assert _code_letters("123 @#$") == ""
    # Arabic-only input has no A-Z letters → empty.
    assert _code_letters("رياضيات") == ""


# ---------------------------------------------------------------------------
# 1. Pure-function unit tests — _build_subject_code
# ---------------------------------------------------------------------------


def test_build_code_uses_english_name_prefix():
    code = _build_subject_code(
        name_en="Mathematics", category=None, llm_prefix=None, existing_codes=set()
    )
    assert code == "MATH101"


def test_build_code_arabic_only_falls_back_to_category():
    # No usable English name (builder only receives name_en) and no LLM prefix:
    # the category supplies the deterministic ASCII prefix.
    code = _build_subject_code(
        name_en="", category="science", llm_prefix=None, existing_codes=set()
    )
    assert code == "SCI101"


def test_build_code_generic_subj_fallback():
    # No name, no LLM prefix, unknown/blank category → generic SUBJ.
    code = _build_subject_code(
        name_en=None, category=None, llm_prefix=None, existing_codes=set()
    )
    assert code == "SUBJ101"

    code_unknown = _build_subject_code(
        name_en=None, category="not-a-category", llm_prefix=None, existing_codes=set()
    )
    assert code_unknown == "SUBJ101"


def test_build_code_bumps_numeric_suffix_on_collision():
    code = _build_subject_code(
        name_en="Mathematics",
        category=None,
        llm_prefix=None,
        existing_codes={"MATH101", "MATH102"},
    )
    assert code == "MATH103"


def test_build_code_collision_set_is_case_insensitive():
    code = _build_subject_code(
        name_en="Mathematics",
        category=None,
        llm_prefix=None,
        existing_codes={"math101"},
    )
    assert code == "MATH102"


def test_build_code_sanitizes_llm_prefix_and_prefers_it():
    # The LLM output is only a candidate prefix: junk chars are stripped and a
    # usable LLM prefix wins over the English name.
    code = _build_subject_code(
        name_en="Mathematics",
        category=None,
        llm_prefix="b!i@o#123",
        existing_codes=set(),
    )
    assert code == "BIO101"


def test_build_code_ignores_unusable_llm_prefix():
    # A too-short LLM prefix (after sanitization) is unusable; the category
    # fallback supplies the prefix when no English name is present.
    code = _build_subject_code(
        name_en="",
        category="arts",
        llm_prefix="@@@",
        existing_codes=set(),
    )
    assert code == "ART101"


# ---------------------------------------------------------------------------
# 2. Endpoint tests — POST /api/subjects/hakim-code
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _stub_llm(monkeypatch):
    """Force the deterministic path: the optional LLM refinement returns no
    usable prefix so the server normalizer/de-duplicator is what is exercised
    (and no network call is made)."""
    async def _fake_generate(*_a, **_k):
        return {"success": False, "text": None}

    monkeypatch.setattr(
        "services.hakim_llm_service.hakim_generate", _fake_generate
    )


@pytest.mark.asyncio
async def test_hakim_code_principal_allowed(client, tenant_a):
    headers = _headers(await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_a))
    resp = await client.post(
        "/subjects/hakim-code",
        headers=headers,
        json={"name": "رياضيات", "name_en": "Mathematics"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["code"] == "MATH101"


@pytest.mark.asyncio
async def test_hakim_code_admin_allowed(client, tenant_a):
    headers = _headers(await _mk_user(UserRole.SCHOOL_ADMIN, tenant_a))
    resp = await client.post(
        "/subjects/hakim-code",
        headers=headers,
        json={"name_en": "Science"},
    )
    assert resp.status_code == 200, resp.text
    # "Science" → first 4 A-Z letters → SCIE.
    assert resp.json()["code"] == "SCIE101"


# Student login is blocked at the auth layer (401) before role gating runs, so
# the role-gate (403) is asserted with the other non-admin school roles.
@pytest.mark.parametrize("role", [UserRole.TEACHER, UserRole.PARENT])
@pytest.mark.asyncio
async def test_hakim_code_other_roles_rejected(client, tenant_a, role):
    headers = _headers(await _mk_user(role, tenant_a))
    resp = await client.post(
        "/subjects/hakim-code",
        headers=headers,
        json={"name_en": "Mathematics"},
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_hakim_code_name_required_envelope(client, tenant_a):
    headers = _headers(await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_a))
    resp = await client.post("/subjects/hakim-code", headers=headers, json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is False
    assert body["reason"] == "NAME_REQUIRED"


@pytest.mark.asyncio
async def test_hakim_code_collision_set_is_school_scoped(client, tenant_a, tenant_b):
    """The collision set is read only within the caller's tenant. A foreign
    tenant's code must never bump the suggested number."""
    # tenant_a already uses MATH101; tenant_b uses MATH102 (must be ignored).
    await gd_insert(db.session, "subjects", {
        "id": str(uuid.uuid4()),
        "school_id": tenant_a,
        "code": "MATH101",
        "name": "رياضيات",
        "is_active": True,
    })
    await gd_insert(db.session, "subjects", {
        "id": str(uuid.uuid4()),
        "school_id": tenant_b,
        "code": "MATH102",
        "name": "رياضيات",
        "is_active": True,
    })

    headers = _headers(await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_a))
    resp = await client.post(
        "/subjects/hakim-code",
        headers=headers,
        json={"name_en": "Mathematics"},
    )
    assert resp.status_code == 200, resp.text
    # MATH101 is taken in tenant_a, MATH102 belongs to tenant_b and is NOT
    # counted, so the next free code within tenant_a is MATH102.
    assert resp.json()["code"] == "MATH102"


# ---------------------------------------------------------------------------
# 3. End-to-end — the suggested code is accepted by POST /api/subjects
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suggested_code_is_accepted_by_create_flow(client, tenant_a):
    """The whole point of the suggestion is to feed POST /subjects. Prove the
    generated code is in a format/uniqueness the create path accepts (200),
    not rejected as malformed or duplicate."""
    headers = _headers(await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_a))

    suggest = await client.post(
        "/subjects/hakim-code",
        headers=headers,
        json={"name": "رياضيات", "name_en": "Mathematics"},
    )
    assert suggest.status_code == 200, suggest.text
    code = suggest.json()["code"]
    assert code == "MATH101"

    created = await client.post(
        "/subjects",
        headers=headers,
        json={"name": "Mathematics", "name_en": "Mathematics", "code": code},
    )
    assert created.status_code == 200, created.text
    # The create path persists the suggested code unchanged.
    assert created.json()["code"] == code


@pytest.mark.asyncio
async def test_suggested_code_avoids_collision_with_existing_subject(client, tenant_a):
    """When a subject already exists, the suggestion must produce a
    non-colliding code that the create path then accepts (200)."""
    # An existing active subject already owns MATH101 in this tenant.
    await gd_insert(db.session, "subjects", {
        "id": str(uuid.uuid4()),
        "school_id": tenant_a,
        "code": "MATH101",
        "name": "رياضيات قديمة",
        "is_active": True,
    })

    headers = _headers(await _mk_user(UserRole.SCHOOL_PRINCIPAL, tenant_a))

    suggest = await client.post(
        "/subjects/hakim-code",
        headers=headers,
        json={"name_en": "Mathematics"},
    )
    assert suggest.status_code == 200, suggest.text
    code = suggest.json()["code"]
    # MATH101 is taken, so the suggestion bumps to the next free code.
    assert code == "MATH102"

    created = await client.post(
        "/subjects",
        headers=headers,
        json={"name": "Mathematics", "name_en": "Mathematics", "code": code},
    )
    assert created.status_code == 200, created.text
    assert created.json()["code"] == code
