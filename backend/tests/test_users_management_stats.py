"""The Users Management "pending requests" stat must count every OPEN status.

Registration requests queue with several still-open statuses (public signup
writes `pending_review`; the reviewer flow also produces `under_review`,
`info_required`, `more_info_requested`). The stat used to count only the
literal status "pending", so the entire school-teacher approval backlog
showed as 0 pending requests — one of the reasons queued teachers were
undiscoverable from the admin UI.
"""
import uuid

import pytest

from dependencies import db
from engines.approval_engine import PENDING_STATUSES
from engines.sql_utils import gd_insert
from src.modules.users.controllers.user_routes_mod import get_users_management_stats


async def _queue_request(status: str, req_type: str = "teacher") -> str:
    suffix = uuid.uuid4().hex[:10]
    rid = str(uuid.uuid4())
    await gd_insert(db.session, "registration_requests", {
        "id": rid,
        "type": req_type,
        "name": f"متقدم {suffix}",
        "email": f"applicant.{suffix}@example.com",
        "status": status,
        "source": "public_signup",
    })
    return rid


@pytest.mark.asyncio
async def test_pending_requests_counts_every_open_status(_db_session):
    admin = {"id": str(uuid.uuid4()), "role": "platform_admin"}

    baseline = (await get_users_management_stats(current_user=admin))["pending_requests"]

    # One request per open status, plus closed ones that must NOT count.
    for status in sorted(PENDING_STATUSES):
        await _queue_request(status)
    await _queue_request("approved")
    await _queue_request("rejected")

    stats = await get_users_management_stats(current_user=admin)
    assert stats["pending_requests"] == baseline + len(PENDING_STATUSES)


@pytest.mark.asyncio
async def test_pending_review_school_teacher_request_is_counted(_db_session):
    """The exact shape the public /register wizard creates."""
    admin = {"id": str(uuid.uuid4()), "role": "platform_admin"}
    baseline = (await get_users_management_stats(current_user=admin))["pending_requests"]

    await _queue_request("pending_review", req_type="teacher")

    stats = await get_users_management_stats(current_user=admin)
    assert stats["pending_requests"] == baseline + 1
