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


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
