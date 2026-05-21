"""Task #484 — Hakim parent → linked-child resolution.

Regression coverage for the bug where a parent with a properly linked
child saw the Arabic "no linked student" fallback from Hakim because
the ad-hoc resolver in `ai_routes_mod.py` only matched
`guardian_links.parent_ref == users.id` and treated `students.parent_id`
as a `users.id`. The fix routes Hakim through the same canonical
resolver (`utils.parent_children_resolution.resolve_parent_children`)
the parent portal already uses.

Coverage:
  - Linked via guardian_links.parent_ref carrying users.id (the path
    Hakim already handled — guard against regression).
  - Linked via guardian_links.parent_ref carrying parents.id (the
    principal-managed linkage path — Hakim previously missed this).
  - Linked only via students.parent_id (FK to parents.id) — Hakim
    previously missed this.
  - Parent with no linked children → safe Arabic fallback.
  - child_id for a child belonging to a different parent in the same
    tenant → 403.
  - child_id for a child in a different tenant → 403.
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


NO_LINKED_FALLBACK_AR = "لم أعثر على أي طالب مرتبط بحسابك"
IDOR_DENY_AR = "ليس لديك صلاحية الوصول إلى بيانات هذا الطالب"


def _parent_headers(user_id: str, tenant_id: str) -> dict:
    token = create_access_token({
        "sub": user_id,
        "role": UserRole.PARENT.value,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_parent_user(tenant_id: str, *, parent_id: str | None = None) -> dict:
    """Create a parent users row. If `parent_id` is given, the user's
    `parent_id` column points at that parents row (mirrors what the
    auth dependency populates onto `current_user` in production)."""
    uid = str(uuid.uuid4())
    row = {
        "id": uid,
        "role": UserRole.PARENT.value,
        "tenant_id": tenant_id,
        "email": f"u-{uid}@t.test",
        "full_name": f"Parent-{uid[:6]}",
        "is_active": True,
        "password_hash": "x",
    }
    if parent_id:
        row["parent_id"] = parent_id
    await gd_insert(db.session, "users", row)
    return {"id": uid, "parent_id": parent_id, "tenant_id": tenant_id}


async def _mk_parents_row(tenant_id: str) -> str:
    pid = str(uuid.uuid4())
    await gd_insert(db.session, "parents", {
        "id": pid,
        "full_name": f"Parent-{pid[:6]}",
        "email": f"p-{pid}@t.test",
        "school_id": tenant_id,
        "is_active": True,
    })
    return pid


async def _mk_student(tenant_id: str, *, parent_id: str | None = None) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "school_id": tenant_id,
        "full_name": f"ST-{sid[:6]}",
        "parent_id": parent_id,
        "is_active": True,
    })
    return sid


async def _link_guardian(
    student_id: str,
    parent_ref: str,
    tenant_id: str,
    *,
    parent_user_id: str | None = None,
) -> None:
    row = {
        "id": str(uuid.uuid4()),
        "student_id": student_id,
        "parent_ref": parent_ref,
        "tenant_id": tenant_id,
        "is_active": True,
        "relationship_type": "father",
    }
    if parent_user_id is not None:
        row["parent_user_id"] = parent_user_id
    await gd_insert(db.session, "guardian_links", row)


async def _link_guardian_by_user_id(student_id: str, user_id: str, tenant_id: str) -> None:
    """Insert a guardian_links row that ONLY populates `parent_user_id`
    (the canonical column). `parent_ref` is deliberately set to an
    unrelated UUID so the test fails unless the resolver actually
    queries `parent_user_id`."""
    await gd_insert(db.session, "guardian_links", {
        "id": str(uuid.uuid4()),
        "student_id": student_id,
        "parent_ref": str(uuid.uuid4()),
        "parent_user_id": user_id,
        "tenant_id": tenant_id,
        "is_active": True,
        "relationship_type": "mother",
    })


class _FakeChat:
    """Minimal stand-in for the OpenAI chat client used by Hakim.

    We do not want real LLM traffic in unit tests; the bug under test
    is purely about the linked-child resolution path before the LLM is
    called. A non-empty `response` keeps the route on the success path.
    """

    def __init__(self):
        self.completions = self

    def create(self, **kwargs):  # noqa: D401 - mimic OpenAI sync surface
        class _Msg:
            content = "تم"

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]

        return _Resp()


class _FakeOpenAI:
    def __init__(self):
        self.chat = _FakeChat()


@pytest.fixture
def _patched_openai():
    """Swap Hakim's OpenAI client for a deterministic stub for the
    duration of one test."""
    from routes import ai_routes_mod as ai_mod
    with patch.object(ai_mod, "get_openai_client", return_value=_FakeOpenAI()):
        yield


async def _post_chat(client, headers, **extra) -> "httpx.Response":
    body = {
        "message": "كيف أداء ابني الدراسي؟",
        "context": "parent_portal",
        "user_role": "parent",
    }
    body.update(extra)
    return await client.post("/hakim/chat", json=body, headers=headers)


# ---------------------------------------------------------------------------
# Linkage paths the FIX must cover
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hakim_resolves_child_via_guardian_links_parent_ref_as_users_id(
    client, tenant_a, _patched_openai,
):
    """guardian_links.parent_ref == users.id — the only path the old
    Hakim resolver actually handled. Guard against regression."""
    parent = await _mk_parent_user(tenant_a)
    student_id = await _mk_student(tenant_a)
    await _link_guardian(student_id, parent["id"], tenant_a)

    res = await _post_chat(client, _parent_headers(parent["id"], tenant_a))
    assert res.status_code == 200, res.text
    assert NO_LINKED_FALLBACK_AR not in (res.json().get("response") or "")


@pytest.mark.asyncio
async def test_hakim_resolves_child_via_guardian_links_parent_user_id(
    client, tenant_a, _patched_openai,
):
    """Canonical column: guardian_links.parent_user_id = users.id.
    `parent_ref` is set to an unrelated UUID, so this only passes if the
    shared resolver actually queries `parent_user_id`."""
    parent = await _mk_parent_user(tenant_a)
    student_id = await _mk_student(tenant_a)
    await _link_guardian_by_user_id(student_id, parent["id"], tenant_a)

    res = await _post_chat(client, _parent_headers(parent["id"], tenant_a))
    assert res.status_code == 200, res.text
    assert NO_LINKED_FALLBACK_AR not in (res.json().get("response") or "")


@pytest.mark.asyncio
async def test_hakim_resolves_child_via_guardian_links_parent_ref_as_parents_id(
    client, tenant_a, _patched_openai,
):
    """Principal-managed linkage path — parent_ref holds a parents.id.
    This is one of the two paths the old Hakim resolver missed."""
    parents_id = await _mk_parents_row(tenant_a)
    parent = await _mk_parent_user(tenant_a, parent_id=parents_id)
    student_id = await _mk_student(tenant_a)
    await _link_guardian(student_id, parents_id, tenant_a)

    res = await _post_chat(client, _parent_headers(parent["id"], tenant_a))
    assert res.status_code == 200, res.text
    assert NO_LINKED_FALLBACK_AR not in (res.json().get("response") or "")


@pytest.mark.asyncio
async def test_hakim_resolves_child_via_students_parent_id_fk(
    client, tenant_a, _patched_openai,
):
    """students.parent_id is an FK to parents.id, not users.id. The old
    Hakim resolver compared it against users.id and missed every student
    created through the principal flow."""
    parents_id = await _mk_parents_row(tenant_a)
    parent = await _mk_parent_user(tenant_a, parent_id=parents_id)
    await _mk_student(tenant_a, parent_id=parents_id)  # no guardian_links

    res = await _post_chat(client, _parent_headers(parent["id"], tenant_a))
    assert res.status_code == 200, res.text
    assert NO_LINKED_FALLBACK_AR not in (res.json().get("response") or "")


# ---------------------------------------------------------------------------
# Negative paths the fix must preserve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hakim_returns_arabic_fallback_when_no_linked_children(
    client, tenant_a, _patched_openai,
):
    parent = await _mk_parent_user(tenant_a)
    res = await _post_chat(client, _parent_headers(parent["id"], tenant_a))
    assert res.status_code == 200, res.text
    body = res.json()
    assert NO_LINKED_FALLBACK_AR in (body.get("response") or "")
    assert "suggestions" in body


@pytest.mark.asyncio
async def test_hakim_rejects_child_id_for_other_parent_same_tenant(
    client, tenant_a, _patched_openai,
):
    """Parent A asking about Parent B's child in the same school → 403."""
    parent_a = await _mk_parent_user(tenant_a)
    student_a = await _mk_student(tenant_a)
    await _link_guardian(student_a, parent_a["id"], tenant_a)

    other_parents_id = await _mk_parents_row(tenant_a)
    other_student = await _mk_student(tenant_a, parent_id=other_parents_id)

    res = await _post_chat(
        client,
        _parent_headers(parent_a["id"], tenant_a),
        child_id=other_student,
    )
    assert res.status_code == 403, res.text
    assert IDOR_DENY_AR in res.text


@pytest.mark.asyncio
async def test_hakim_rejects_child_id_cross_tenant(
    client, tenant_a, tenant_b, _patched_openai,
):
    """Parent A asking about a student in tenant B → 403, regardless of
    what the client claims in `tenant_id`."""
    parent_a = await _mk_parent_user(tenant_a)
    own_student = await _mk_student(tenant_a)
    await _link_guardian(own_student, parent_a["id"], tenant_a)

    foreign_student = await _mk_student(tenant_b)

    res = await _post_chat(
        client,
        _parent_headers(parent_a["id"], tenant_a),
        child_id=foreign_student,
        tenant_id=tenant_b,  # client lying about tenant must not help
    )
    assert res.status_code == 403, res.text
    assert IDOR_DENY_AR in res.text
