"""
Unit & Integration Tests for Automated Scheduled Communication Dispatch.
"""

import sys
import os
import uuid
import asyncio
from datetime import datetime, timezone, timedelta

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dependencies import db
from src.core.database.db import async_session_factory
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_delete_many
from src.modules.communication.services.scheduled_dispatch_service import (
    is_scheduled_time_due,
    dispatch_single_scheduled_message,
    dispatch_due_scheduled_messages,
    dispatch_due_scheduled_notifications,
    dispatch_all_due_communications,
)


def test_is_scheduled_time_due_variations():
    now_utc = datetime(2026, 8, 27, 15, 0, 0, tzinfo=timezone.utc)

    # Past times -> True
    assert is_scheduled_time_due("2026-08-27T14:30:00Z", now_utc) is True
    assert is_scheduled_time_due("2026-08-27T14:30:00+00:00", now_utc) is True
    assert is_scheduled_time_due("2026-08-27T14:30", now_utc) is True  # datetime-local
    assert is_scheduled_time_due("2026-08-27T15:00:00Z", now_utc) is True  # exact now
    assert is_scheduled_time_due((now_utc - timedelta(minutes=5)).timestamp(), now_utc) is True
    assert is_scheduled_time_due((now_utc - timedelta(minutes=5)).timestamp() * 1000, now_utc) is True

    # Future times -> False
    assert is_scheduled_time_due("2026-08-27T15:30:00Z", now_utc) is False
    assert is_scheduled_time_due("2026-08-27T15:30:00+00:00", now_utc) is False
    assert is_scheduled_time_due("2026-08-27T15:30", now_utc) is False
    assert is_scheduled_time_due((now_utc + timedelta(minutes=10)).timestamp(), now_utc) is False
    assert is_scheduled_time_due((now_utc + timedelta(minutes=10)).timestamp() * 1000, now_utc) is False

    # Invalid / empty -> False
    assert is_scheduled_time_due("", now_utc) is False
    assert is_scheduled_time_due(None, now_utc) is False
    print("✓ test_is_scheduled_time_due_variations passed")


async def run_integration_tests():
    async with async_session_factory() as session:
        db.set_session(session)
        try:
            # 1. Test is_scheduled_time_due
            test_is_scheduled_time_due_variations()

            # 2. Test scheduled message automated dispatch
            test_school_id = f"sch_{uuid.uuid4().hex[:8]}"
            test_teacher_id = f"usr_{uuid.uuid4().hex[:8]}"
            test_parent_id = f"usr_{uuid.uuid4().hex[:8]}"
            test_principal_id = f"usr_{uuid.uuid4().hex[:8]}"

            # Seed school
            await gd_insert(session, "schools", {
                "id": test_school_id,
                "code": f"SCH_{test_school_id[:8]}",
                "name": "Test Dispatch School",
                "name_en": "Test Dispatch School",
                "school_type": "regular",
                "is_active": True,
            })

            # Seed users
            await gd_insert(session, "users", {
                "id": test_teacher_id,
                "full_name": "Test Teacher",
                "email": f"teacher_{test_teacher_id}@test.com",
                "password_hash": "hash_123",
                "role": "teacher",
                "tenant_id": test_school_id,
                "is_active": True,
            })
            await gd_insert(session, "users", {
                "id": test_parent_id,
                "full_name": "Test Parent",
                "email": f"parent_{test_parent_id}@test.com",
                "password_hash": "hash_123",
                "role": "parent",
                "tenant_id": test_school_id,
                "is_active": True,
            })
            await gd_insert(session, "users", {
                "id": test_principal_id,
                "full_name": "Test Principal",
                "email": f"principal_{test_principal_id}@test.com",
                "password_hash": "hash_123",
                "role": "school_principal",
                "tenant_id": test_school_id,
                "is_active": True,
            })

            past_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
            future_time = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()

            due_msg_id = f"msg_{uuid.uuid4().hex[:8]}"
            await gd_insert(session, "messages", {
                "id": due_msg_id,
                "title": "Due Scheduled Announcement",
                "content": "This is a due automated test message",
                "audience": "teachers",
                "audience_ids": [],
                "channels": ["in_app"],
                "status": "scheduled",
                "sent_count": 0,
                "recipient_count": 1,
                "school_id": test_school_id,
                "created_by": test_principal_id,
                "scheduled_at": past_time,
                "created_at": past_time,
            })

            future_msg_id = f"msg_{uuid.uuid4().hex[:8]}"
            await gd_insert(session, "messages", {
                "id": future_msg_id,
                "title": "Future Announcement",
                "content": "This should remain scheduled",
                "audience": "parents",
                "audience_ids": [],
                "channels": ["in_app"],
                "status": "scheduled",
                "sent_count": 0,
                "recipient_count": 1,
                "school_id": test_school_id,
                "created_by": test_principal_id,
                "scheduled_at": future_time,
                "created_at": past_time,
            })
            await session.commit()

            # Execute dispatch sweep
            dispatched = await dispatch_due_scheduled_messages(db)
            await session.commit()
            assert dispatched >= 1, f"Expected at least 1 dispatched, got {dispatched}"

            # Verify due message
            due_msg = await gd_find_one(session, "messages", {"id": due_msg_id})
            assert due_msg is not None
            assert due_msg["status"] == "sent"
            assert due_msg["sent_at"] is not None
            assert due_msg["sent_count"] >= 1

            # Verify per-user notification
            notifs = await gd_find(session, "notifications", {"user_id": test_teacher_id})
            assert len(notifs) >= 1
            assert notifs[0]["title"] == "Due Scheduled Announcement"

            # Verify future message stays scheduled
            future_msg = await gd_find_one(session, "messages", {"id": future_msg_id})
            assert future_msg is not None
            assert future_msg["status"] == "scheduled"
            assert future_msg.get("sent_at") is None

            print("✓ test_scheduled_message_automated_dispatch passed")

            # 3. Test scheduled notification automated dispatch
            sn_id = f"sn_{uuid.uuid4().hex[:8]}"
            await gd_insert(session, "scheduled_notifications", {
                "id": sn_id,
                "title": "Scheduled Alert",
                "message": "Testing scheduled notification sweep",
                "notification_type": "announcement",
                "priority": "high",
                "recipient_ids": [test_teacher_id],
                "scheduled_at": past_time,
                "is_sent": False,
                "school_id": test_school_id,
            })
            await session.commit()

            summary = await dispatch_all_due_communications(db)
            await session.commit()
            assert summary["notifications_dispatched"] >= 1

            sn = await gd_find_one(session, "scheduled_notifications", {"id": sn_id})
            assert sn is not None
            assert sn["is_sent"] is True
            assert sn["sent_at"] is not None

            print("✓ test_scheduled_notification_automated_dispatch passed")

            # Cleanup
            await gd_delete_many(session, "messages", {"id": {"$in": [due_msg_id, future_msg_id]}})
            await gd_delete_many(session, "scheduled_notifications", {"id": sn_id})
            await gd_delete_many(session, "notifications", {"tenant_id": test_school_id})
            await gd_delete_many(session, "users", {"tenant_id": test_school_id})
            await gd_delete_many(session, "schools", {"id": test_school_id})
            await session.commit()
            print("ALL SCHEDULED DISPATCH TESTS PASSED SUCCESSFULLY!")

        finally:
            db.set_session(None)


if __name__ == "__main__":
    asyncio.run(run_integration_tests())
