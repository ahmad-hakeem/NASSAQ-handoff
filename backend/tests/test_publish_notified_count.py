"""Regression tests — schedule-publish "تم إبلاغ N معلماً" recipient count.

Production report: publishing the schedule for a school with 108 teachers
showed "تم نشر الجدول وإبلاغ 109 معلماً". Root cause: the ``all_teachers``
cohort in ``SchoolNotificationEngine._resolve_recipients`` selected users by
ROLE alone (``users.role IN ('teacher', ...)``), so an active user account
with a teacher-type role but NO row in ``teachers`` (an orphaned test
account) was notified and counted — while every admin surface (master-grid
header, teacher management, dashboards) counts active ``teachers`` rows.

The cohort is now derived from the school's ACTIVE ``teachers`` rows joined
to their ACTIVE linked user accounts (``teachers.user_id → users.id``),
deduplicated on user_id, so the publish toast count always equals the
number of real teachers actually notified.
"""

import uuid
from datetime import datetime, timezone

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_find, gd_insert, gd_update_many
from engines.school_notification_engine import (
    SchoolNotificationEngine,
    RecipientType,
    SendNotificationRequest,
    NotificationType,
    NotificationPriority,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _mk_role_user(tenant_id, *, role: str = "teacher", active: bool = True) -> str:
    """Insert a bare ``users`` row with a teacher-type role (no teachers row)."""
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "role": role,
        "tenant_id": tenant_id,
        "email": f"u-{uid}@t.test",
        "full_name": f"user-{uid[:6]}",
        "is_active": active,
        "password_hash": "x",
    })
    return uid


async def _mk_teacher_row(school_id, user_id, *, active: bool = True) -> str:
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid,
        "full_name": f"teacher-{tid[:6]}",
        "school_id": school_id,
        "user_id": user_id,
        "is_active": active,
    })
    return tid


async def _mk_real_teacher(tenant_id, *, user_active: bool = True,
                           teacher_active: bool = True) -> str:
    """Teacher the way the product creates one: users row + linked teachers row."""
    uid = await _mk_role_user(tenant_id, active=user_active)
    await _mk_teacher_row(tenant_id, uid, active=teacher_active)
    return uid


async def _resolve_teacher_cohort(tenant_id) -> set:
    engine = SchoolNotificationEngine(db)
    rows = await engine._resolve_recipients(RecipientType.all_teachers, None, tenant_id)
    return {r["user_id"] for r in rows}


# ---------------------------------------------------------------------------
# 1. Cohort-level guarantees
# ---------------------------------------------------------------------------


async def test_orphan_teacher_role_user_is_not_notified_or_counted(tenant_a):
    """The 109-vs-108 bug: an active user with role=teacher but no
    ``teachers`` row must be excluded from the all_teachers cohort."""
    real = {await _mk_real_teacher(tenant_a) for _ in range(3)}
    orphan = await _mk_role_user(tenant_a)  # no teachers row

    cohort = await _resolve_teacher_cohort(tenant_a)

    assert cohort == real, (
        f"Cohort must be exactly the {len(real)} real teachers; got {len(cohort)}"
    )
    assert orphan not in cohort


async def test_cohort_dedups_and_excludes_inactive_rows(tenant_a, tenant_b):
    """Unique-recipient rules:
    - two active teacher rows → same user account counts ONCE;
    - inactive (archived) teacher row → excluded even if the user is active;
    - active teacher row with a deactivated user account → excluded
      (no deliverable inbox → must not inflate the count);
    - teacher row linked to a user of another tenant → excluded.
    """
    dup_user = await _mk_role_user(tenant_a)
    await _mk_teacher_row(tenant_a, dup_user, active=True)
    await _mk_teacher_row(tenant_a, dup_user, active=True)  # duplicate link

    await _mk_real_teacher(tenant_a, teacher_active=False)   # archived teacher
    await _mk_real_teacher(tenant_a, user_active=False)      # disabled account

    foreign_user = await _mk_role_user(tenant_b)
    await _mk_teacher_row(tenant_a, foreign_user, active=True)  # cross-tenant link

    cohort = await _resolve_teacher_cohort(tenant_a)

    assert cohort == {dup_user}


async def test_cohort_empty_for_school_without_teachers(tenant_a):
    """Zero-teacher school → empty cohort → engine reports no recipients
    and the publish route surfaces notified_count = 0 (not a fabricated N)."""
    orphan = await _mk_role_user(tenant_a)  # role user only, still no teachers row

    assert await _resolve_teacher_cohort(tenant_a) == set()

    engine = SchoolNotificationEngine(db)
    result = await engine.send_notification(
        SendNotificationRequest(
            title_ar="ت", message_ar="ن",
            recipient_type=RecipientType.all_teachers,
            notification_type=NotificationType.announcement,
            priority=NotificationPriority.high,
        ),
        tenant_id=tenant_a,
        sent_by="system",
    )
    assert result.get("success") is False
    assert await gd_find(db.session, "notifications", {"user_id": orphan}, limit=5) == []


async def test_delivered_count_matches_unique_real_teachers(tenant_a):
    """End-to-end engine send: delivered_count == unique real teachers, and
    exactly one inbox row per teacher is created (none for the orphan)."""
    real = [await _mk_real_teacher(tenant_a) for _ in range(2)]
    orphan = await _mk_role_user(tenant_a)

    engine = SchoolNotificationEngine(db)
    result = await engine.send_notification(
        SendNotificationRequest(
            title_ar="تم نشر جدول جديد", message_ar="افتح شاشة جدولي.",
            recipient_type=RecipientType.all_teachers,
            notification_type=NotificationType.announcement,
            priority=NotificationPriority.high,
        ),
        tenant_id=tenant_a,
        sent_by="system",
    )

    assert result.get("success") is True
    assert result.get("delivered_count") == 2
    assert result.get("recipient_count") == 2

    for uid in real:
        rows = await gd_find(db.session, "notifications", {"user_id": uid}, limit=5)
        assert len(rows) == 1, f"expected exactly one inbox row for {uid}"
    assert await gd_find(db.session, "notifications", {"user_id": orphan}, limit=5) == []


# ---------------------------------------------------------------------------
# 2. Route-level guarantee — POST /schedule/publish returns the real count
# ---------------------------------------------------------------------------


async def test_publish_endpoint_reports_real_teacher_count(client, tenant_a):
    """Publishing a draft must return notified_count == number of the
    school's real active teachers — the same number the admin sees in the
    master grid — even when an orphaned teacher-role user exists."""
    real = [await _mk_real_teacher(tenant_a) for _ in range(2)]
    orphan = await _mk_role_user(tenant_a)

    admin_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": admin_id,
        "role": UserRole.SCHOOL_ADMIN.value,
        "tenant_id": tenant_a,
        "email": f"adm-{admin_id}@t.test",
        "full_name": "school admin",
        "is_active": True,
        "password_hash": "x",
        "mfa_enrolled_at": datetime.now(timezone.utc).isoformat(),
    })
    headers = {"Authorization": "Bearer " + create_access_token({
        "sub": admin_id, "role": UserRole.SCHOOL_ADMIN.value, "tenant_id": tenant_a,
    })}

    # Draft timetable with no sessions; disable every hard constraint so
    # the publish gate is deterministic in the shared test DB (same
    # pattern as tests/test_publish_gate_registry.py).
    await gd_update_many(
        db.session, "timetable_hard_constraints", {}, {"is_active": False}
    )
    draft_id = str(uuid.uuid4())
    await gd_insert(db.session, "timetables", {
        "id": draft_id, "school_id": tenant_a,
        "name": "TT", "academic_year": "2026-2027", "semester": 1,
        "status": "draft", "version": 1, "total_sessions": 0,
    })

    r = await client.post(
        "/schedule/publish",
        json={"school_id": tenant_a, "timetable_id": draft_id},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["notified_count"] == 2, (
        "notified_count must equal the school's real active teachers "
        f"(2), got {body['notified_count']} — orphan role-user must not inflate it"
    )
    for uid in real:
        rows = await gd_find(db.session, "notifications", {"user_id": uid}, limit=5)
        assert len(rows) == 1
    assert await gd_find(db.session, "notifications", {"user_id": orphan}, limit=5) == []


# ---------------------------------------------------------------------------
# 3. Legacy teacher accounts provisioned without users.tenant_id
# ---------------------------------------------------------------------------


async def test_legacy_null_tenant_teacher_is_notified_and_counted(tenant_a):
    """Production report: a school with 9 teachers saw "وإبلاغ 8 معلماً".

    The missing teacher's ``users`` row carries NO ``tenant_id`` (legacy
    provisioning — 15 such accounts exist in production). The cohort join
    required ``users.tenant_id == school``, so that teacher was neither
    counted NOR notified: a delivery bug, not just a display one. The
    school-pinned ``teachers`` row is the tenant proof; the nullable user
    column may only reject a user belonging to ANOTHER school.
    """
    normal = await _mk_real_teacher(tenant_a)
    legacy_user = await _mk_role_user(None)          # users.tenant_id IS NULL
    await _mk_teacher_row(tenant_a, legacy_user)

    assert await _resolve_teacher_cohort(tenant_a) == {normal, legacy_user}

    engine = SchoolNotificationEngine(db)
    result = await engine.send_notification(
        SendNotificationRequest(
            title_ar="تم نشر جدول جديد", message_ar="افتح شاشة جدولي.",
            recipient_type=RecipientType.all_teachers,
            notification_type=NotificationType.announcement,
            priority=NotificationPriority.high,
        ),
        tenant_id=tenant_a,
        sent_by="system",
    )
    assert result.get("delivered_count") == 2
    # ...and the legacy teacher really has an inbox row (the teacher inbox
    # reads by user_id, so a NULL-tenant account can still receive it).
    assert len(await gd_find(db.session, "notifications",
                             {"user_id": legacy_user}, limit=5)) == 1


async def test_publish_toast_count_includes_legacy_null_tenant_teacher(client, tenant_a):
    """Route-level: the number the admin reads in the publish toast."""
    await _mk_real_teacher(tenant_a)
    legacy_user = await _mk_role_user(None)
    await _mk_teacher_row(tenant_a, legacy_user)

    admin_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": admin_id,
        "role": UserRole.SCHOOL_ADMIN.value,
        "tenant_id": tenant_a,
        "email": f"adm-{admin_id}@t.test",
        "full_name": "school admin",
        "is_active": True,
        "password_hash": "x",
        "mfa_enrolled_at": datetime.now(timezone.utc).isoformat(),
    })
    headers = {"Authorization": "Bearer " + create_access_token({
        "sub": admin_id, "role": UserRole.SCHOOL_ADMIN.value, "tenant_id": tenant_a,
    })}

    await gd_update_many(
        db.session, "timetable_hard_constraints", {}, {"is_active": False}
    )
    draft_id = str(uuid.uuid4())
    await gd_insert(db.session, "timetables", {
        "id": draft_id, "school_id": tenant_a,
        "name": "TT", "academic_year": "2026-2027", "semester": 1,
        "status": "draft", "version": 1, "total_sessions": 0,
    })

    r = await client.post(
        "/schedule/publish",
        json={"school_id": tenant_a, "timetable_id": draft_id},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["notified_count"] == 2, (
        "toast must count every real teacher of the school, including the "
        "legacy account whose users row has no tenant_id"
    )


async def test_unpinned_user_claimed_by_two_schools_is_excluded_from_both(tenant_a, tenant_b):
    """``teachers.user_id`` has no uniqueness constraint, so an account with
    NO ``users.tenant_id`` could be claimed by active teacher rows in two
    schools. Such an account has no trustworthy owner — it must not receive
    EITHER school's broadcast (fail closed), while each school's properly
    pinned teachers keep being notified."""
    pinned_a = await _mk_real_teacher(tenant_a)
    pinned_b = await _mk_real_teacher(tenant_b)

    ambiguous = await _mk_role_user(None)          # users.tenant_id IS NULL
    await _mk_teacher_row(tenant_a, ambiguous)
    await _mk_teacher_row(tenant_b, ambiguous)

    assert await _resolve_teacher_cohort(tenant_a) == {pinned_a}
    assert await _resolve_teacher_cohort(tenant_b) == {pinned_b}
