"""Approving a school-teacher request must mint a SCHOOL teacher, linked to a school.

A queued `registration_requests` row of type "teacher" is a SCHOOL teacher who
asked to join an existing school (the public /register wizard). Independent
Teachers never reach the approval queue — their signup is instant and
auto-approved via `_create_independent_teacher_instant`.

Two defects are pinned here:

1. `TeacherApprovalHandler` used to mint the account with role="teacher" but
   account_type="independent_teacher". `users` has no account_type column (and
   no `data` overflow column), so dict_to_model dropped that key and it never
   persisted — the declaration was inert rather than actively harmful. It is
   still a latent trap worth pinning: `auth_scope.is_independent_teacher()`
   returns True on the account_type fallback *regardless of role*, so if that
   key ever becomes storable the approved school teacher would be scoped to a
   synthetic `itw_{user_id}` workspace instead of a school tenant.

2. The handler hardcoded `teachers.school_id = None`, so an approved teacher
   belonged to no school at all. The signup form's school field is optional
   free text, so the school is now chosen by the reviewing admin and passed in
   as approval context.
"""
import uuid

import pytest

from auth_scope import is_independent_teacher, independent_workspace_id
from engines.approval_handlers import TeacherApprovalHandler
from engines.sql_utils import model_to_dict
from pg_models import User, Teacher, School
from sqlalchemy import select


def _pending_school_teacher_request() -> dict:
    """A queued public-signup request as /registration-requests stores it."""
    suffix = uuid.uuid4().hex[:10]
    return {
        "id": str(uuid.uuid4()),
        "full_name": "أحمد بن سالم",
        "email": f"school.teacher.{suffix}@example.com",
        "phone": f"05{suffix[:8]}",
        "national_id": f"1{suffix[:9]}",
        "account_type": "teacher",
        "specialization": "رياضيات",
        "years_of_experience": "5",
        # Free text the applicant typed; deliberately NOT a usable link.
        "school_mentioned": "مدرسة ذكرها المتقدم",
    }


async def _make_school(
    session, *, school_type="public", tenant_type="production", school_id=None
) -> str:
    suffix = uuid.uuid4().hex[:10]
    school = School(
        id=school_id or str(uuid.uuid4()),
        name=f"مدرسة الاختبار {suffix}",
        code=f"TST-{suffix}",
        school_type=school_type,
        tenant_type=tenant_type,
        status="active",
    )
    session.add(school)
    await session.flush()
    return school.id


async def _approve(request: dict, school_id: str):
    handler = TeacherApprovalHandler()
    result = await handler.create_entities(
        request, approved_by={"id": None}, context={"school_id": school_id}
    )
    assert result.success is True, result.message
    return result


@pytest.mark.asyncio
async def test_approved_school_teacher_is_not_an_independent_teacher(_db_session):
    """The regression oracle: role AND account_type must both say school teacher."""
    school_id = await _make_school(_db_session)
    request = _pending_school_teacher_request()
    result = await _approve(request, school_id)

    user = (
        await _db_session.execute(
            select(User).where(User.id == result.created_entities["user_id"]).limit(1)
        )
    ).scalars().first()
    assert user is not None

    assert user.role == "teacher"

    user_dict = model_to_dict(user)
    # Whatever the handler declares must never say Independent Teacher. Today
    # `users` has no account_type column so this reads back as None; the guard
    # holds either way and starts biting the moment the key becomes storable.
    assert user_dict.get("account_type") != "independent_teacher"

    # The derived tenant scoping must agree: a school teacher gets no synthetic
    # itw_{user_id} workspace, it gets the real school tenant.
    assert is_independent_teacher(user_dict) is False
    assert independent_workspace_id(user_dict) is None
    assert user.tenant_id == school_id


@pytest.mark.asyncio
async def test_approved_school_teacher_gets_a_teachers_row_linked_to_the_school(_db_session):
    """The authoritative `teachers` row is created AND attached to the school."""
    school_id = await _make_school(_db_session)
    request = _pending_school_teacher_request()
    result = await _approve(request, school_id)

    teacher = (
        await _db_session.execute(
            select(Teacher).where(Teacher.user_id == result.created_entities["user_id"]).limit(1)
        )
    ).scalars().first()

    assert teacher is not None
    assert teacher.is_active is True
    assert teacher.specialization == "رياضيات"
    assert teacher.school_id == school_id

    # The post-approval verification hook must agree the link exists.
    handler = TeacherApprovalHandler()
    assert await handler.verify_after_approve(request, result) is None


@pytest.mark.asyncio
async def test_approval_is_blocked_when_the_reviewer_picks_no_school(_db_session):
    """No school chosen => a clear message, and nothing is created."""
    handler = TeacherApprovalHandler()
    request = _pending_school_teacher_request()

    message = await handler.validate_before_approve(request, context={})
    assert message is not None
    assert "المدرسة" in message

    result = await handler.create_entities(request, approved_by={"id": None}, context={})
    assert result.success is False

    orphan = (
        await _db_session.execute(select(User).where(User.email == request["email"]).limit(1))
    ).scalars().first()
    assert orphan is None


@pytest.mark.asyncio
async def test_approval_is_blocked_for_an_unknown_school(_db_session):
    handler = TeacherApprovalHandler()
    request = _pending_school_teacher_request()

    message = await handler.validate_before_approve(
        request, context={"school_id": str(uuid.uuid4())}
    )
    assert message is not None
    assert "غير موجودة" in message


@pytest.mark.asyncio
async def test_school_teacher_cannot_be_attached_to_an_independent_teacher_workspace(_db_session):
    """IT workspaces live in the same `schools` table — they must be rejected."""
    handler = TeacherApprovalHandler()
    workspace_id = await _make_school(
        _db_session, school_type="independent_teacher", tenant_type="independent_teacher"
    )
    request = _pending_school_teacher_request()

    message = await handler.validate_before_approve(request, context={"school_id": workspace_id})
    assert message is not None
    assert "مستقل" in message

    result = await handler.create_entities(
        request, approved_by={"id": None}, context={"school_id": workspace_id}
    )
    assert result.success is False


@pytest.mark.asyncio
async def test_school_teacher_cannot_be_attached_to_a_legacy_itw_workspace(_db_session):
    """Legacy IT rows carry NO type markers — only the canonical `itw_` id prefix.

    Filtering on school_type/tenant_type alone silently lets these through and
    scopes a school teacher to an Independent-Teacher tenant.
    """
    handler = TeacherApprovalHandler()
    workspace_id = await _make_school(
        _db_session,
        school_id=f"itw_{uuid.uuid4()}",
        school_type="public",
        tenant_type="production",
    )
    request = _pending_school_teacher_request()

    message = await handler.validate_before_approve(request, context={"school_id": workspace_id})
    assert message is not None, "legacy itw_* workspace was accepted as a real school"
    assert "مستقل" in message

    result = await handler.create_entities(
        request, approved_by={"id": None}, context={"school_id": workspace_id}
    )
    assert result.success is False


@pytest.mark.asyncio
async def test_handler_is_labelled_as_school_teacher(_db_session):
    """The admin approval queue must not call these requests "معلم مستقل"."""
    handler = TeacherApprovalHandler()
    assert handler.request_type == "teacher"
    assert "مستقل" not in handler.display_name_ar
    assert "Independent" not in handler.display_name
