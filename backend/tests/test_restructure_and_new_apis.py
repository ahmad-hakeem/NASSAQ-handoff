"""
NASSAQ - Test Restructured APIs and New Features
Tests for:
1. Login API (verify restructure didn't break existing APIs)
2. Dashboard Stats API (verify restructure didn't break existing APIs)
3. Teacher Attendance API (new) - GET and POST
4. Communication API (new) - Stats, Audience, Templates, Send Message
"""
import pytest
import requests
import os
from datetime import datetime

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
PRINCIPAL_EMAIL = "principal1@nassaq.com"
PRINCIPAL_PASSWORD = "Principal@123"
ADMIN_EMAIL = "admin@nassaq.com"
ADMIN_PASSWORD = "Admin@123"


class TestAuthAPI:
    """Test that restructure didn't break Login API"""
    
    def test_login_principal_success(self):
        """Test principal login works after restructure"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "Missing access_token in response"
        assert "user" in data, "Missing user in response"
        assert data["user"]["email"] == PRINCIPAL_EMAIL
        assert data["user"]["role"] == "school_principal"
        print(f"✓ Principal login successful - role: {data['user']['role']}")
    
    def test_login_admin_success(self):
        """Test admin login works after restructure"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "Missing access_token in response"
        assert "user" in data, "Missing user in response"
        assert data["user"]["email"] == ADMIN_EMAIL
        assert data["user"]["role"] == "platform_admin"
        print(f"✓ Admin login successful - role: {data['user']['role']}")
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials returns 401"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "invalid@test.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Invalid credentials correctly rejected with 401")


class TestDashboardStatsAPI:
    """Test that restructure didn't break Dashboard Stats API"""
    
    @pytest.fixture
    def principal_token(self):
        """Get principal auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Principal login failed")
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Admin login failed")
    
    def test_dashboard_stats_principal(self, principal_token):
        """Test dashboard stats for principal"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=headers)
        assert response.status_code == 200, f"Dashboard stats failed: {response.text}"
        data = response.json()
        # Verify expected fields exist
        assert "total_students" in data, "Missing total_students"
        assert "total_teachers" in data, "Missing total_teachers"
        assert "total_classes" in data, "Missing total_classes"
        print(f"✓ Dashboard stats for principal - students: {data['total_students']}, teachers: {data['total_teachers']}")
    
    def test_dashboard_stats_admin(self, admin_token):
        """Test dashboard stats for admin"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=headers)
        assert response.status_code == 200, f"Dashboard stats failed: {response.text}"
        data = response.json()
        # Verify expected fields exist
        assert "total_schools" in data, "Missing total_schools"
        assert "total_students" in data, "Missing total_students"
        assert "total_teachers" in data, "Missing total_teachers"
        assert "active_schools" in data, "Missing active_schools"
        print(f"✓ Dashboard stats for admin - schools: {data['total_schools']}, students: {data['total_students']}")


class TestTeacherAttendanceAPI:
    """Test new Teacher Attendance API endpoints"""
    
    @pytest.fixture
    def principal_token(self):
        """Get principal auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Principal login failed")
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Admin login failed")
    
    def test_get_teacher_attendance_today(self, principal_token):
        """Test GET teacher attendance for today"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        today = datetime.now().strftime("%Y-%m-%d")
        response = requests.get(f"{BASE_URL}/api/teacher-attendance?date={today}", headers=headers)
        assert response.status_code == 200, f"Get teacher attendance failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list response"
        print(f"✓ GET teacher attendance for {today} - {len(data)} records found")
    
    def test_post_bulk_teacher_attendance(self, principal_token):
        """Test POST bulk teacher attendance"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        today = datetime.now().strftime("%Y-%m-%d")
        
        # First get teachers to get valid teacher IDs
        teachers_response = requests.get(f"{BASE_URL}/api/teachers", headers=headers)
        if teachers_response.status_code != 200:
            pytest.skip("Could not fetch teachers")
        
        teachers = teachers_response.json()
        if not teachers or len(teachers) == 0:
            pytest.skip("No teachers found to test attendance")
        
        # Create test attendance records for first 2 teachers
        test_records = []
        for i, teacher in enumerate(teachers[:2]):
            teacher_id = teacher.get("id") or teacher.get("user_id")
            if teacher_id:
                test_records.append({
                    "teacher_id": teacher_id,
                    "date": today,
                    "status": "present" if i == 0 else "late",
                    "check_in_time": "08:00" if i == 0 else "08:15",
                    "notes": f"TEST_attendance_record_{i}"
                })
        
        if not test_records:
            pytest.skip("No valid teacher IDs found")
        
        response = requests.post(
            f"{BASE_URL}/api/teacher-attendance/bulk",
            headers=headers,
            json={"records": test_records}
        )
        assert response.status_code == 200, f"Bulk attendance save failed: {response.text}"
        data = response.json()
        assert "message" in data, "Missing message in response"
        assert "saved" in data or "updated" in data, "Missing saved/updated count"
        print(f"✓ POST bulk teacher attendance - saved: {data.get('saved', 0)}, updated: {data.get('updated', 0)}")
    
    def test_get_teacher_attendance_summary(self, principal_token):
        """Test GET teacher attendance summary report"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        response = requests.get(f"{BASE_URL}/api/teacher-attendance/report/summary", headers=headers)
        assert response.status_code == 200, f"Get attendance summary failed: {response.text}"
        data = response.json()
        assert "overall" in data, "Missing overall stats"
        assert "daily" in data, "Missing daily stats"
        assert "attendance_rate" in data["overall"], "Missing attendance_rate in overall"
        print(f"✓ GET teacher attendance summary - rate: {data['overall']['attendance_rate']}%")


class TestCommunicationAPI:
    """Test new Communication API endpoints"""
    
    @pytest.fixture
    def principal_token(self):
        """Get principal auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Principal login failed")
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Admin login failed")
    
    def test_get_communication_stats(self, principal_token):
        """Test GET communication stats"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        response = requests.get(f"{BASE_URL}/api/communication/stats", headers=headers)
        assert response.status_code == 200, f"Get communication stats failed: {response.text}"
        data = response.json()
        assert "sent" in data, "Missing sent count"
        assert "scheduled" in data, "Missing scheduled count"
        assert "drafts" in data, "Missing drafts count"
        assert "templates" in data, "Missing templates count"
        print(f"✓ GET communication stats - sent: {data['sent']}, scheduled: {data['scheduled']}")
    
    def test_get_audience_stats(self, principal_token):
        """Test GET audience stats for messaging"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        response = requests.get(f"{BASE_URL}/api/communication/audience", headers=headers)
        assert response.status_code == 200, f"Get audience stats failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list response"
        assert len(data) >= 4, "Expected at least 4 audience groups (all, teachers, students, parents)"
        
        # Verify audience groups have required fields
        for group in data:
            assert "id" in group, "Missing id in audience group"
            assert "name" in group, "Missing name in audience group"
            assert "count" in group, "Missing count in audience group"
        
        print(f"✓ GET audience stats - {len(data)} groups found")
        for group in data:
            print(f"  - {group['id']}: {group['count']} members")
    
    def test_get_message_templates(self, principal_token):
        """Test GET message templates"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        response = requests.get(f"{BASE_URL}/api/communication/templates", headers=headers)
        assert response.status_code == 200, f"Get templates failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list response"
        assert len(data) >= 1, "Expected at least 1 template"
        
        # Verify template structure
        for template in data:
            assert "id" in template, "Missing id in template"
            assert "name" in template, "Missing name in template"
        
        print(f"✓ GET message templates - {len(data)} templates found")
    
    def test_send_message(self, principal_token):
        """Test POST send message"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        
        message_payload = {
            "title": "TEST_رسالة اختبار",
            "content": "هذه رسالة اختبار من نظام الاختبار الآلي. TEST_message_content",
            "audience": "teachers",
            "channels": ["in_app"]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/communication",
            headers=headers,
            json=message_payload
        )
        assert response.status_code == 200, f"Send message failed: {response.text}"
        data = response.json()
        assert "message" in data, "Missing message in response"
        assert "id" in data, "Missing message id in response"
        assert "status" in data, "Missing status in response"
        assert data["status"] == "sent", f"Expected status 'sent', got '{data['status']}'"
        print(f"✓ POST send message - id: {data['id']}, status: {data['status']}, recipients: {data.get('recipient_count', 0)}")
    
    def test_get_messages_list(self, principal_token):
        """Test GET messages list"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        response = requests.get(f"{BASE_URL}/api/communication?limit=10", headers=headers)
        assert response.status_code == 200, f"Get messages failed: {response.text}"
        data = response.json()
        assert "messages" in data, "Missing messages in response"
        assert "total" in data, "Missing total in response"
        assert isinstance(data["messages"], list), "Expected messages to be a list"
        print(f"✓ GET messages list - {len(data['messages'])} messages, total: {data['total']}")
    
    def test_schedule_message(self, principal_token):
        """Test POST schedule message for future"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        
        # Schedule for tomorrow
        from datetime import timedelta
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT10:00:00")
        
        message_payload = {
            "title": "TEST_رسالة مجدولة",
            "content": "هذه رسالة مجدولة للاختبار. TEST_scheduled_message",
            "audience": "all",
            "channels": ["in_app"],
            "scheduled_at": tomorrow
        }
        
        response = requests.post(
            f"{BASE_URL}/api/communication",
            headers=headers,
            json=message_payload
        )
        assert response.status_code == 200, f"Schedule message failed: {response.text}"
        data = response.json()
        assert "status" in data, "Missing status in response"
        assert data["status"] == "scheduled", f"Expected status 'scheduled', got '{data['status']}'"
        print(f"✓ POST schedule message - id: {data['id']}, status: {data['status']}, scheduled_at: {tomorrow}")


class TestTeachersAPI:
    """Test that teachers API still works after restructure"""
    
    @pytest.fixture
    def principal_token(self):
        """Get principal auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Principal login failed")
    
    def test_get_teachers_list(self, principal_token):
        """Test GET teachers list"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        response = requests.get(f"{BASE_URL}/api/teachers", headers=headers)
        assert response.status_code == 200, f"Get teachers failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list response"
        print(f"✓ GET teachers list - {len(data)} teachers found")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
