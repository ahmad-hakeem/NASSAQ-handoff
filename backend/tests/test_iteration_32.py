"""
Test iteration 32: Testing new dashboard routes and backend APIs
- Landing page loads
- Login flow works
- New routes: /student, /parent, /principal
- Backend APIs: scheduling, attendance, assessment, audit
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuthentication:
    """Test authentication and login"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for platform_admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "info@nassaqapp.com",
            "password": "NassaqAdmin2026!##$$HBJ"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        return data["access_token"]
    
    def test_login_success(self):
        """Test platform_admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "info@nassaqapp.com",
            "password": "NassaqAdmin2026!##$$HBJ"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["role"] == "platform_admin"
        print(f"Login successful for user: {data['user']['email']}")


class TestPublicEndpoints:
    """Test public endpoints"""
    
    def test_public_contact_info(self):
        """Test public contact info endpoint"""
        response = requests.get(f"{BASE_URL}/api/public/contact-info")
        assert response.status_code == 200
        data = response.json()
        print(f"Contact info: {data}")


class TestSchedulingAPI:
    """Test scheduling API endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "info@nassaqapp.com",
            "password": "NassaqAdmin2026!##$$HBJ"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_scheduling_schedules_endpoint(self, auth_headers):
        """Test scheduling schedules endpoint - expects 400 for platform_admin without tenant"""
        response = requests.get(f"{BASE_URL}/api/scheduling/schedules", headers=auth_headers)
        # Platform admin without tenant_id should get 400
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}"
        print(f"Scheduling schedules response: {response.status_code}")
    
    def test_scheduling_time_slots_endpoint(self, auth_headers):
        """Test scheduling time-slots endpoint"""
        response = requests.get(f"{BASE_URL}/api/scheduling/time-slots", headers=auth_headers)
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}"
        print(f"Scheduling time-slots response: {response.status_code}")


class TestAttendanceAPI:
    """Test attendance API endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "info@nassaqapp.com",
            "password": "NassaqAdmin2026!##$$HBJ"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_attendance_alerts_low_attendance(self, auth_headers):
        """Test attendance low attendance alerts endpoint"""
        response = requests.get(f"{BASE_URL}/api/attendance/alerts/low-attendance", headers=auth_headers)
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}"
        print(f"Attendance low-attendance alerts response: {response.status_code}")
    
    def test_attendance_alerts_consecutive_absences(self, auth_headers):
        """Test attendance consecutive absences alerts endpoint"""
        response = requests.get(f"{BASE_URL}/api/attendance/alerts/consecutive-absences", headers=auth_headers)
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}"
        print(f"Attendance consecutive-absences alerts response: {response.status_code}")


class TestAssessmentAPI:
    """Test assessment API endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "info@nassaqapp.com",
            "password": "NassaqAdmin2026!##$$HBJ"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_assessments_list_endpoint(self, auth_headers):
        """Test assessments list endpoint"""
        response = requests.get(f"{BASE_URL}/api/assessments/", headers=auth_headers)
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}"
        print(f"Assessments list response: {response.status_code}")


class TestAuditAPI:
    """Test audit API endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "info@nassaqapp.com",
            "password": "NassaqAdmin2026!##$$HBJ"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_audit_stats_endpoint(self, auth_headers):
        """Test audit stats endpoint"""
        response = requests.get(f"{BASE_URL}/api/audit/stats", headers=auth_headers)
        assert response.status_code == 200, f"Unexpected status: {response.status_code}"
        data = response.json()
        print(f"Audit stats: {data}")
    
    def test_audit_critical_events_endpoint(self, auth_headers):
        """Test audit critical events endpoint"""
        response = requests.get(f"{BASE_URL}/api/audit/critical-events", headers=auth_headers)
        assert response.status_code == 200, f"Unexpected status: {response.status_code}"
        print(f"Audit critical events response: {response.status_code}")
    
    def test_audit_logs_endpoint(self, auth_headers):
        """Test audit logs endpoint"""
        response = requests.get(f"{BASE_URL}/api/audit/logs", headers=auth_headers)
        assert response.status_code == 200, f"Unexpected status: {response.status_code}"
        print(f"Audit logs response: {response.status_code}")
    
    def test_audit_login_analytics_endpoint(self, auth_headers):
        """Test audit login analytics endpoint"""
        response = requests.get(f"{BASE_URL}/api/audit/login-analytics", headers=auth_headers)
        assert response.status_code == 200, f"Unexpected status: {response.status_code}"
        print(f"Audit login analytics response: {response.status_code}")


class TestDashboardStats:
    """Test dashboard stats endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "info@nassaqapp.com",
            "password": "NassaqAdmin2026!##$$HBJ"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_dashboard_stats(self, auth_headers):
        """Test dashboard stats endpoint"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        assert response.status_code == 200, f"Unexpected status: {response.status_code}"
        data = response.json()
        print(f"Dashboard stats: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
