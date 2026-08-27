"""
End-to-End Integration Tests for AI Insights Parent Message Delivery.
Verifies that POST /ai/insights/intervention with action_type='notify_parent':
1. Resolves the parent user across all linking methods (guardian_links, students.parent_id, parent_email).
2. Creates persistent notifications visible in the Parent's notification bell (GET /notifications).
3. Creates persistent message records visible in the Parent's message inbox (GET /parent-portal/messages).
4. Correctly rejects orphan students with 404 (no false positive).
"""

import os
import sys
import uuid
import asyncio
from datetime import datetime, timezone

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from dependencies import db, create_access_token, UserRole
from src.core.database.db import async_session_factory
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_delete_many
from src.common.utils.parent_resolution import (
    PARENT_NOT_FOUND_AR,
    resolve_student_parent_user_id,
)


def _tok(user: dict) -> dict:
    token = create_access_token(
        {"sub": user["id"], "role": user["role"], "tenant_id": user.get("tenant_id")}
    )
    return {"Authorization": f"Bearer {token}"}


async def run_tests():
    from httpx import AsyncClient, ASGITransport
    from server import app

    async with async_session_factory() as session:
        db.set_session(session)
        try:
            school_id = f"sch_{uuid.uuid4().hex[:8]}"
            principal_id = f"usr_{uuid.uuid4().hex[:8]}"
            parent_user_id = f"usr_{uuid.uuid4().hex[:8]}"
            parent_record_id = f"par_{uuid.uuid4().hex[:8]}"
            student_id = f"stu_{uuid.uuid4().hex[:8]}"
            orphan_student_id = f"stu_{uuid.uuid4().hex[:8]}"

            # 1. Seed School
            await gd_insert(session, "schools", {
                "id": school_id,
                "code": f"S{school_id[:6]}",
                "name": "AI Insights Test School",
                "name_en": "AI Insights Test School",
                "status": "active",
                "is_active": True,
            })

            # 2. Seed Principal User
            principal = {
                "id": principal_id,
                "email": "mudeer_test@example.com",
                "full_name": "مدير المدرسة التجريبي",
                "role": "school_principal",
                "tenant_id": school_id,
                "is_active": True,
                "password_hash": "hash123",
            }
            await gd_insert(session, "users", principal)

            # 3. Seed Parent User & Parent Profile
            parent_user = {
                "id": parent_user_id,
                "email": "om-youssef_test@gmail.com",
                "full_name": "أم يوسف",
                "role": "parent",
                "tenant_id": school_id,
                "parent_id": parent_record_id,
                "is_active": True,
                "password_hash": "hash123",
            }
            await gd_insert(session, "users", parent_user)

            await gd_insert(session, "parents", {
                "id": parent_record_id,
                "user_id": parent_user_id,
                "email": "om-youssef_test@gmail.com",
                "full_name": "أم يوسف",
                "school_id": school_id,
                "is_active": True,
                "student_ids": [student_id],
            })

            # 4. Seed Linked Student
            await gd_insert(session, "students", {
                "id": student_id,
                "school_id": school_id,
                "full_name": "يوسف محمد",
                "name": "يوسف محمد",
                "parent_id": parent_record_id,
                "parent_email": "om-youssef_test@gmail.com",
                "is_active": True,
            })

            # 5. Seed Guardian Link
            await gd_insert(session, "guardian_links", {
                "id": str(uuid.uuid4()),
                "student_id": student_id,
                "parent_user_id": parent_user_id,
                "parent_ref": parent_record_id,
                "tenant_id": school_id,
                "is_active": True,
            })

            # 6. Seed Orphan Student
            await gd_insert(session, "students", {
                "id": orphan_student_id,
                "school_id": school_id,
                "full_name": "طالب بدون ولي أمر",
                "name": "طالب بدون ولي أمر",
                "parent_id": None,
                "is_active": True,
            })
            await session.commit()

            print("✓ Database seeded successfully")

            # 7. Test parent resolution
            resolved_pid = await resolve_student_parent_user_id(student_id, school_id)
            assert resolved_pid == parent_user_id, f"Expected {parent_user_id}, got {resolved_pid}"
            print("✓ Parent resolution verified")

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                principal_headers = _tok(principal)
                parent_headers = _tok(parent_user)

                # 8. Test sending message to parent via POST /api/ai/insights/intervention
                payload = {
                    "student_id": student_id,
                    "action_type": "notify_parent",
                    "data": {
                        "message": "نود إبلاغكم بأن ابنكم يوسف بحاجة لمتابعة في مادة العلوم.",
                        "issue_type": "academic",
                    },
                }

                resp = await client.post("/api/ai/insights/intervention", json=payload, headers=principal_headers)
                assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
                resp_json = resp.json()
                assert resp_json.get("success") is True
                print("✓ POST /api/ai/insights/intervention succeeded")

                # 9. Verify Parent Bell Notifications (GET /api/notifications)
                notif_resp = await client.get("/api/notifications", headers=parent_headers)
                assert notif_resp.status_code == 200, f"Expected 200, got {notif_resp.status_code}: {notif_resp.text}"
                notifs = notif_resp.json()
                assert len(notifs) >= 1, "Parent received 0 notifications!"
                found_notif = any("يوسف" in (n.get("message") or "") for n in notifs)
                assert found_notif, "Parent notification with student message not found!"
                print("✓ Parent notification bell confirmed payload received")

                # 10. Verify Parent Message Inbox (GET /api/parent-portal/messages)
                msg_resp = await client.get("/api/parent-portal/messages", headers=parent_headers)
                assert msg_resp.status_code == 200, f"Expected 200, got {msg_resp.status_code}: {msg_resp.text}"
                parent_messages = msg_resp.json().get("messages", [])
                assert len(parent_messages) >= 1, "Parent message inbox is empty!"
                found_msg = any("يوسف" in (m.get("content") or "") for m in parent_messages)
                assert found_msg, "Parent message in inbox not found!"
                print("✓ Parent message inbox confirmed payload received")

                # 11. Test orphan student rejection (no false positive)
                orphan_payload = {
                    "student_id": orphan_student_id,
                    "action_type": "notify_parent",
                    "data": {
                        "message": "رسالة لطالب بدون ولي أمر",
                        "issue_type": "academic",
                    },
                }
                orphan_resp = await client.post("/api/ai/insights/intervention", json=orphan_payload, headers=principal_headers)
                assert orphan_resp.status_code == 404, f"Expected 404, got {orphan_resp.status_code}"
                assert PARENT_NOT_FOUND_AR in orphan_resp.text
                print("✓ Orphan student rejection verified (no false positive)")

            # Cleanup
            await gd_delete_many(session, "ai_interventions", {"school_id": school_id})
            await gd_delete_many(session, "messages", {"school_id": school_id})
            await gd_delete_many(session, "notifications", {"tenant_id": school_id})
            await gd_delete_many(session, "guardian_links", {"tenant_id": school_id})
            await gd_delete_many(session, "students", {"school_id": school_id})
            await gd_delete_many(session, "parents", {"school_id": school_id})
            await gd_delete_many(session, "users", {"tenant_id": school_id})
            await gd_delete_many(session, "schools", {"id": school_id})
            await session.commit()
            print("ALL AI INSIGHTS PARENT MESSAGE TESTS PASSED SUCCESSFULLY!")

        finally:
            db.set_session(None)


if __name__ == "__main__":
    asyncio.run(run_tests())
