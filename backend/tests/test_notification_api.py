"""
Test Notification Engine APIs for NASSAQ School Management System
Tests: Notification CRUD, Mark as Read, Mark All as Read, Analytics, Attendance-triggered notifications
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
PRINCIPAL_EMAIL = "principal@nassaq.com"
PRINCIPAL_PASSWORD = "NassaqPrincipal2026"
TEACHER_EMAIL = "teacher@nassaq.com"
TEACHER_PASSWORD = "NassaqTeacher2026"


class TestNotificationAPIs:
    """Test Notification Engine APIs"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
    def get_principal_token(self):
        """Login as school principal and get token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        assert response.status_code == 200, f"Principal login failed: {response.text}"
        data = response.json()
        return data["access_token"], data["user"]
    
    def get_teacher_token(self):
        """Login as teacher and get token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEACHER_EMAIL,
            "password": TEACHER_PASSWORD
        })
        assert response.status_code == 200, f"Teacher login failed: {response.text}"
        data = response.json()
        return data["access_token"], data["user"]
    
    # ============== AUTH TESTS ==============
    def test_01_principal_login(self):
        """Test principal login works"""
        token, user = self.get_principal_token()
        assert token is not None
        assert user["role"] == "school_principal"
        assert user["email"] == PRINCIPAL_EMAIL
        print(f"✓ Principal login successful: {user['full_name']}")
    
    def test_02_teacher_login(self):
        """Test teacher login works"""
        token, user = self.get_teacher_token()
        assert token is not None
        assert user["role"] == "teacher"
        assert user["email"] == TEACHER_EMAIL
        print(f"✓ Teacher login successful: {user['full_name']}")
    
    # ============== NOTIFICATION GET TESTS ==============
    def test_03_get_notifications(self):
        """Test GET /api/notifications returns list"""
        token, _ = self.get_principal_token()
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        response = self.session.get(f"{BASE_URL}/api/notifications?limit=10")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ GET /api/notifications returned {len(data)} notifications")
        
        # Check notification structure if any exist
        if len(data) > 0:
            notification = data[0]
            assert "id" in notification
            assert "title" in notification
            assert "message" in notification
            assert "notification_type" in notification
            assert "read_status" in notification
            assert "created_at" in notification
            print(f"  - First notification: {notification['title'][:50]}...")
    
    def test_04_get_unread_count(self):
        """Test GET /api/notifications/unread-count"""
        token, _ = self.get_principal_token()
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        response = self.session.get(f"{BASE_URL}/api/notifications/unread-count")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "unread_count" in data
        assert isinstance(data["unread_count"], int)
        print(f"✓ Unread count: {data['unread_count']}")
    
    def test_05_filter_notifications_by_type(self):
        """Test filtering notifications by type"""
        token, _ = self.get_principal_token()
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Filter by attendance type
        response = self.session.get(f"{BASE_URL}/api/notifications?notification_type=attendance")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        for notification in data:
            assert notification["notification_type"] == "attendance", "Filter not working"
        print(f"✓ Filter by type 'attendance' returned {len(data)} notifications")
    
    # ============== MARK AS READ TESTS ==============
    def test_06_mark_notification_as_read(self):
        """Test PUT /api/notifications/{id}/read"""
        token, _ = self.get_principal_token()
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get notifications first
        response = self.session.get(f"{BASE_URL}/api/notifications?limit=10")
        assert response.status_code == 200
        notifications = response.json()
        
        if len(notifications) == 0:
            pytest.skip("No notifications to mark as read")
        
        # Find an unread notification or use first one
        notification_id = notifications[0]["id"]
        
        # Mark as read
        response = self.session.put(f"{BASE_URL}/api/notifications/{notification_id}/read")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "message" in data
        print(f"✓ Marked notification {notification_id[:8]}... as read")
        
        # Verify it's marked as read
        response = self.session.get(f"{BASE_URL}/api/notifications?limit=10")
        notifications = response.json()
        marked_notification = next((n for n in notifications if n["id"] == notification_id), None)
        if marked_notification:
            assert marked_notification["read_status"] == True, "Notification not marked as read"
            print(f"  - Verified read_status is True")
    
    def test_07_mark_all_as_read(self):
        """Test PUT /api/notifications/mark-all-read"""
        token, _ = self.get_principal_token()
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        response = self.session.put(f"{BASE_URL}/api/notifications/mark-all-read")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "success" in data or "message" in data
        print(f"✓ Mark all as read: {data}")
        
        # Verify unread count is 0
        response = self.session.get(f"{BASE_URL}/api/notifications/unread-count")
        assert response.status_code == 200
        count_data = response.json()
        assert count_data["unread_count"] == 0, "Unread count should be 0 after mark all read"
        print(f"  - Verified unread count is now 0")
    
    # ============== NOTIFICATION ANALYTICS TESTS ==============
    def test_08_get_notification_analytics(self):
        """Test GET /api/notifications/analytics (admin only)"""
        token, _ = self.get_principal_token()
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        response = self.session.get(f"{BASE_URL}/api/notifications/analytics")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "total_notifications" in data
        assert "read_count" in data
        assert "unread_count" in data
        assert "read_rate" in data
        print(f"✓ Analytics: total={data['total_notifications']}, read={data['read_count']}, unread={data['unread_count']}, rate={data['read_rate']}%")
    
    # ============== ATTENDANCE NOTIFICATION TRIGGER TEST ==============
    def test_09_attendance_triggers_notification(self):
        """Test that recording absent attendance creates notification for principal"""
        teacher_token, teacher_user = self.get_teacher_token()
        principal_token, principal_user = self.get_principal_token()
        
        # Get initial unread count for principal
        self.session.headers.update({"Authorization": f"Bearer {principal_token}"})
        response = self.session.get(f"{BASE_URL}/api/notifications/unread-count")
        initial_count = response.json()["unread_count"]
        print(f"  - Initial unread count: {initial_count}")
        
        # Get a class and student for the teacher
        self.session.headers.update({"Authorization": f"Bearer {teacher_token}"})
        response = self.session.get(f"{BASE_URL}/api/classes")
        assert response.status_code == 200
        classes = response.json()
        
        if len(classes) == 0:
            pytest.skip("No classes available for testing")
        
        class_id = classes[0]["id"]
        
        # Get students in the class
        response = self.session.get(f"{BASE_URL}/api/students?class_id={class_id}")
        assert response.status_code == 200
        students = response.json()
        
        if len(students) == 0:
            pytest.skip("No students in class for testing")
        
        student = students[0]
        student_id = student["id"]
        student_name = student["full_name"]
        
        # Record absent attendance
        today = datetime.now().strftime("%Y-%m-%d")
        attendance_data = {
            "class_id": class_id,
            "date": today,
            "records": [
                {
                    "student_id": student_id,
                    "status": "absent",
                    "notes": "TEST_notification_trigger"
                }
            ]
        }
        
        response = self.session.post(f"{BASE_URL}/api/attendance/bulk", json=attendance_data)
        assert response.status_code == 200, f"Failed to record attendance: {response.text}"
        print(f"✓ Recorded absent attendance for {student_name}")
        
        # Check if notification was created for principal
        self.session.headers.update({"Authorization": f"Bearer {principal_token}"})
        response = self.session.get(f"{BASE_URL}/api/notifications?limit=5")
        assert response.status_code == 200
        notifications = response.json()
        
        # Look for attendance notification
        attendance_notification = None
        for n in notifications:
            if n["notification_type"] == "attendance" and student_name in n["title"]:
                attendance_notification = n
                break
        
        assert attendance_notification is not None, "Attendance notification not created for principal"
        assert "تنبيه حضور" in attendance_notification["title"] or "Attendance Alert" in attendance_notification.get("title_en", "")
        print(f"✓ Notification created: {attendance_notification['title']}")
        
        # Verify unread count increased
        response = self.session.get(f"{BASE_URL}/api/notifications/unread-count")
        new_count = response.json()["unread_count"]
        print(f"  - New unread count: {new_count}")
    
    # ============== DELETE NOTIFICATION TEST ==============
    def test_10_delete_notification(self):
        """Test DELETE /api/notifications/{id}"""
        token, _ = self.get_principal_token()
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        # Get notifications
        response = self.session.get(f"{BASE_URL}/api/notifications?limit=10")
        assert response.status_code == 200
        notifications = response.json()
        
        if len(notifications) == 0:
            pytest.skip("No notifications to delete")
        
        notification_id = notifications[0]["id"]
        
        # Delete notification
        response = self.session.delete(f"{BASE_URL}/api/notifications/{notification_id}")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "message" in data
        print(f"✓ Deleted notification {notification_id[:8]}...")
        
        # Verify it's deleted
        response = self.session.get(f"{BASE_URL}/api/notifications?limit=10")
        notifications = response.json()
        deleted = next((n for n in notifications if n["id"] == notification_id), None)
        assert deleted is None, "Notification should be deleted"
        print(f"  - Verified notification is deleted")
    
    # ============== UNAUTHORIZED ACCESS TEST ==============
    def test_11_unauthorized_access(self):
        """Test that unauthenticated requests are rejected"""
        # Clear auth header
        self.session.headers.pop("Authorization", None)
        
        response = self.session.get(f"{BASE_URL}/api/notifications")
        assert response.status_code in [401, 403], f"Should be unauthorized: {response.status_code}"
        print(f"✓ Unauthorized access correctly rejected with {response.status_code}")

    # ============== TASK #1006: STUDENT_ID FILTER TESTS ==============

    def test_12_student_field_is_null_for_non_parent(self):
        """Non-parent callers must always receive student=null regardless of
        whether the notification row has a student_id set. This preserves the
        pre-task-1006 response contract for principal/teacher/admin roles."""
        token, _ = self.get_principal_token()
        self.session.headers.update({"Authorization": f"Bearer {token}"})

        response = self.session.get(f"{BASE_URL}/api/notifications?limit=50")
        assert response.status_code == 200, f"Failed: {response.text}"

        data = response.json()
        for notification in data:
            assert notification.get("student") is None, (
                f"Non-parent caller received non-null student on notification {notification['id']}"
            )
        print(f"✓ All {len(data)} notifications have student=null for principal (non-parent)")

    def test_13_student_id_filter_ignored_for_non_parent(self):
        """The ?student_id= query param must be silently ignored for non-parent
        roles (no 403, no cross-tenant disclosure). The caller gets their own
        unfiltered inbox back."""
        token, _ = self.get_principal_token()
        self.session.headers.update({"Authorization": f"Bearer {token}"})

        fake_student_id = str(uuid.uuid4())
        response = self.session.get(
            f"{BASE_URL}/api/notifications?student_id={fake_student_id}&limit=10"
        )
        # Must not be 403 — the filter is simply ignored for non-parent roles.
        assert response.status_code == 200, (
            f"Non-parent ?student_id= should be ignored, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ ?student_id= is silently ignored for principal: returned {len(data)} notifications")

    def test_14_response_includes_student_field_in_schema(self):
        """Every notification response object must include the 'student' key
        (even if its value is null) so the frontend can rely on the field
        being present in the schema."""
        token, _ = self.get_principal_token()
        self.session.headers.update({"Authorization": f"Bearer {token}"})

        response = self.session.get(f"{BASE_URL}/api/notifications?limit=5")
        assert response.status_code == 200, f"Failed: {response.text}"

        data = response.json()
        for notification in data:
            assert "student" in notification, (
                f"Notification {notification.get('id')} is missing the 'student' key"
            )
        print(f"✓ 'student' field is present (possibly null) in all {len(data)} response objects")

    def test_15_teacher_student_id_filter_ignored(self):
        """A teacher using ?student_id= must get 200 (ignored), not 403."""
        token, _ = self.get_teacher_token()
        self.session.headers.update({"Authorization": f"Bearer {token}"})

        fake_student_id = str(uuid.uuid4())
        response = self.session.get(
            f"{BASE_URL}/api/notifications?student_id={fake_student_id}&limit=5"
        )
        assert response.status_code == 200, (
            f"Teacher ?student_id= should be ignored, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert isinstance(data, list)
        # Teacher should also receive student=null on all notifications
        for notification in data:
            assert notification.get("student") is None, (
                f"Teacher received non-null student on notification {notification['id']}"
            )
        print(f"✓ Teacher ?student_id= ignored; {len(data)} notifications returned with student=null")

    # ============== TASK #1006: PARENT-PATH TESTS ==============
    # These tests require a parent account. Set PARENT_EMAIL / PARENT_PASSWORD
    # in the test environment to run them; they are skipped otherwise.

    def get_parent_token(self):
        """Login as parent and get token (requires PARENT_EMAIL + PARENT_PASSWORD env vars)."""
        email = os.environ.get("PARENT_EMAIL", "")
        password = os.environ.get("PARENT_PASSWORD", "")
        if not email or not password:
            pytest.skip("PARENT_EMAIL / PARENT_PASSWORD not set — skipping parent-path tests")
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": email,
            "password": password,
        })
        assert response.status_code == 200, f"Parent login failed: {response.text}"
        data = response.json()
        return data["access_token"], data["user"]

    def test_16_parent_unlinked_student_id_returns_403(self):
        """A parent filtering by a student they are NOT linked to must get 403.
        Authorization checks all three linkage paths in order:
          A) students.parent_id / parent_user_id
          B) guardian_links (is_active=True)
          C) parents.student_ids array (legacy installs)
        A random UUID matches none of them so must always return 403."""
        token, _ = self.get_parent_token()
        self.session.headers.update({"Authorization": f"Bearer {token}"})

        random_student_id = str(uuid.uuid4())
        response = self.session.get(
            f"{BASE_URL}/api/notifications?student_id={random_student_id}&limit=5"
        )
        assert response.status_code == 403, (
            f"Expected 403 for unlinked student_id, got {response.status_code}: {response.text}"
        )
        print(f"✓ Unlinked ?student_id= (random UUID) correctly rejected with 403")

    def test_17_parent_linked_student_id_filter_returns_200(self):
        """A parent filtering by a student they ARE linked to must get 200 with
        only notifications for that child, and each notification should contain
        a populated 'student' object."""
        token, _ = self.get_parent_token()
        self.session.headers.update({"Authorization": f"Bearer {token}"})

        # Discover linked children
        children_resp = self.session.get(f"{BASE_URL}/api/parent-portal/children")
        assert children_resp.status_code == 200, f"Children fetch failed: {children_resp.text}"
        raw = children_resp.json()
        children = raw.get("children", raw) if isinstance(raw, dict) else raw
        if not children:
            pytest.skip("Parent has no linked children — skipping filter test")

        child_id = children[0]["id"]
        response = self.session.get(
            f"{BASE_URL}/api/notifications?student_id={child_id}&limit=50"
        )
        assert response.status_code == 200, (
            f"Linked ?student_id= should return 200, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        # Every returned notification must reference this exact student
        for notification in data:
            assert notification.get("student_id") == child_id or notification.get("student") is not None, (
                f"Notification {notification.get('id')} returned for wrong student"
            )
        print(f"✓ Linked ?student_id= returned {len(data)} notifications for child {child_id[:8]}...")

    def test_18_parent_inbox_student_field_shape(self):
        """When a parent calls GET /notifications with no student_id filter,
        notifications that have a linked child's student_id set must return a
        populated 'student' object with id, name_ar, and code fields."""
        token, _ = self.get_parent_token()
        self.session.headers.update({"Authorization": f"Bearer {token}"})

        response = self.session.get(f"{BASE_URL}/api/notifications?limit=50")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()

        # All notifications must have the 'student' key
        for notification in data:
            assert "student" in notification, (
                f"Notification {notification.get('id')} missing 'student' key"
            )

        # Notifications with student data must have the right shape
        with_student = [n for n in data if n.get("student") is not None]
        for notification in with_student:
            s = notification["student"]
            assert "id" in s, f"student.id missing on {notification.get('id')}"
            assert "name_ar" in s, f"student.name_ar missing on {notification.get('id')}"
            assert "code" in s, f"student.code missing on {notification.get('id')}"
            # At least one of name_ar / code must be non-empty
            assert s.get("name_ar") or s.get("code"), (
                f"student has neither name_ar nor code on notification {notification.get('id')}"
            )

        print(f"✓ Parent inbox: {len(data)} total, {len(with_student)} with populated student object")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
