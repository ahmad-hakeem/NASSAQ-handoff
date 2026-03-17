"""
Test New Routers - Scheduling, Attendance, Assessment, Audit
Tests the newly connected routers from Foundation Phase

Endpoints tested:
- GET /api/scheduling/schedules - جلب الجداول (يحتاج tenant_id)
- GET /api/scheduling/time-slots - جلب الفترات الزمنية
- GET /api/attendance/alerts/low-attendance - تنبيهات الحضور المنخفض
- GET /api/assessments/ - جلب التقييمات
- GET /api/audit/stats - إحصائيات التدقيق
- GET /api/audit/critical-events - الأحداث الحرجة
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://school-timetable-ai.preview.emergentagent.com')

# Test credentials
PLATFORM_ADMIN_EMAIL = "info@nassaqapp.com"
PLATFORM_ADMIN_PASSWORD = "NassaqAdmin2026!##$$HBJ"


class TestNewRouters:
    """Test the newly connected routers"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": PLATFORM_ADMIN_EMAIL,
                "password": PLATFORM_ADMIN_PASSWORD
            }
        )
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.user = login_response.json().get("user")
        else:
            pytest.skip(f"Login failed: {login_response.status_code}")
    
    # ============== SCHEDULING ROUTER TESTS ==============
    
    def test_scheduling_schedules_endpoint_exists(self):
        """Test GET /api/scheduling/schedules - endpoint exists and responds"""
        response = self.session.get(f"{BASE_URL}/api/scheduling/schedules")
        
        # Expected: 400 because platform_admin has no tenant_id
        # This is expected behavior per agent context
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}, body: {response.text}"
        
        if response.status_code == 400:
            # Verify it's the expected tenant_id error
            data = response.json()
            assert "detail" in data
            print(f"Expected behavior: {data['detail']}")
    
    def test_scheduling_time_slots_endpoint_exists(self):
        """Test GET /api/scheduling/time-slots - endpoint exists and responds"""
        response = self.session.get(f"{BASE_URL}/api/scheduling/time-slots")
        
        # Expected: 400 because platform_admin has no tenant_id
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}, body: {response.text}"
        
        if response.status_code == 400:
            data = response.json()
            assert "detail" in data
            print(f"Expected behavior: {data['detail']}")
    
    def test_scheduling_seed_time_slots_requires_tenant(self):
        """Test POST /api/scheduling/time-slots/seed-defaults - requires tenant"""
        response = self.session.post(f"{BASE_URL}/api/scheduling/time-slots/seed-defaults")
        
        # Expected: 400 because platform_admin has no tenant_id
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}, body: {response.text}"
    
    # ============== ATTENDANCE ROUTER TESTS ==============
    
    def test_attendance_low_attendance_alerts_endpoint(self):
        """Test GET /api/attendance/alerts/low-attendance - endpoint exists"""
        response = self.session.get(f"{BASE_URL}/api/attendance/alerts/low-attendance")
        
        # Expected: 400 because platform_admin has no tenant_id
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}, body: {response.text}"
        
        if response.status_code == 400:
            data = response.json()
            assert "detail" in data
            print(f"Expected behavior: {data['detail']}")
    
    def test_attendance_consecutive_absences_endpoint(self):
        """Test GET /api/attendance/alerts/consecutive-absences - endpoint exists"""
        response = self.session.get(f"{BASE_URL}/api/attendance/alerts/consecutive-absences")
        
        # Expected: 400 because platform_admin has no tenant_id
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}, body: {response.text}"
    
    # ============== ASSESSMENT ROUTER TESTS ==============
    
    def test_assessments_list_endpoint(self):
        """Test GET /api/assessments/ - endpoint exists and responds"""
        response = self.session.get(f"{BASE_URL}/api/assessments/")
        
        # Expected: 400 because platform_admin has no tenant_id
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}, body: {response.text}"
        
        if response.status_code == 400:
            data = response.json()
            assert "detail" in data
            print(f"Expected behavior: {data['detail']}")
    
    def test_assessments_grade_weights_endpoint(self):
        """Test GET /api/assessments/grade-weights/{subject_id} - endpoint exists"""
        # Use a dummy subject_id
        response = self.session.get(f"{BASE_URL}/api/assessments/grade-weights/test-subject-id")
        
        # Expected: 400 because platform_admin has no tenant_id
        assert response.status_code in [200, 400, 404], f"Unexpected status: {response.status_code}, body: {response.text}"
    
    # ============== AUDIT ROUTER TESTS ==============
    
    def test_audit_stats_endpoint(self):
        """Test GET /api/audit/stats - platform admin should have access"""
        response = self.session.get(f"{BASE_URL}/api/audit/stats")
        
        # Platform admin should be able to access audit stats
        assert response.status_code == 200, f"Unexpected status: {response.status_code}, body: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "period_days" in data
        assert "total_events" in data
        assert "by_action" in data
        assert "by_severity" in data
        assert "by_entity_type" in data
        assert "critical_count" in data
        assert "high_count" in data
        
        print(f"Audit stats: {data['total_events']} total events in {data['period_days']} days")
    
    def test_audit_critical_events_endpoint(self):
        """Test GET /api/audit/critical-events - platform admin should have access"""
        response = self.session.get(f"{BASE_URL}/api/audit/critical-events")
        
        # Platform admin should be able to access critical events
        assert response.status_code == 200, f"Unexpected status: {response.status_code}, body: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "period_days" in data
        assert "critical_events" in data
        assert "total" in data
        
        print(f"Critical events: {data['total']} events in {data['period_days']} days")
    
    def test_audit_logs_endpoint(self):
        """Test GET /api/audit/logs - platform admin should have access"""
        response = self.session.get(f"{BASE_URL}/api/audit/logs?limit=10")
        
        # Platform admin should be able to access audit logs
        assert response.status_code == 200, f"Unexpected status: {response.status_code}, body: {response.text}"
        
        data = response.json()
        # Response should be a list
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        
        print(f"Audit logs: Retrieved {len(data)} log entries")
    
    def test_audit_login_analytics_endpoint(self):
        """Test GET /api/audit/login-analytics - platform admin should have access"""
        response = self.session.get(f"{BASE_URL}/api/audit/login-analytics")
        
        # Platform admin should be able to access login analytics
        assert response.status_code == 200, f"Unexpected status: {response.status_code}, body: {response.text}"
        
        data = response.json()
        print(f"Login analytics response: {data}")


class TestRouterAuthentication:
    """Test that routers require authentication"""
    
    def test_scheduling_requires_auth(self):
        """Test scheduling endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/scheduling/schedules")
        assert response.status_code in [401, 403], f"Expected auth error, got: {response.status_code}"
    
    def test_attendance_requires_auth(self):
        """Test attendance endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/attendance/alerts/low-attendance")
        assert response.status_code in [401, 403], f"Expected auth error, got: {response.status_code}"
    
    def test_assessments_requires_auth(self):
        """Test assessments endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/assessments/")
        assert response.status_code in [401, 403], f"Expected auth error, got: {response.status_code}"
    
    def test_audit_requires_auth(self):
        """Test audit endpoints require authentication"""
        response = requests.get(f"{BASE_URL}/api/audit/stats")
        assert response.status_code in [401, 403], f"Expected auth error, got: {response.status_code}"


class TestRouterRoleAccess:
    """Test role-based access control for new routers"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as platform admin
        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": PLATFORM_ADMIN_EMAIL,
                "password": PLATFORM_ADMIN_PASSWORD
            }
        )
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip(f"Login failed: {login_response.status_code}")
    
    def test_audit_stats_platform_admin_access(self):
        """Platform admin should have full access to audit stats"""
        response = self.session.get(f"{BASE_URL}/api/audit/stats")
        assert response.status_code == 200, f"Platform admin should access audit stats: {response.text}"
    
    def test_audit_critical_events_platform_admin_access(self):
        """Platform admin should have access to critical events"""
        response = self.session.get(f"{BASE_URL}/api/audit/critical-events")
        assert response.status_code == 200, f"Platform admin should access critical events: {response.text}"
    
    def test_audit_export_platform_admin_access(self):
        """Platform admin should be able to export audit reports"""
        response = self.session.post(
            f"{BASE_URL}/api/audit/export-report",
            params={
                "start_date": "2026-01-01",
                "end_date": "2026-12-31",
                "format_type": "json"
            }
        )
        # Should work for platform admin
        assert response.status_code in [200, 400], f"Unexpected status: {response.status_code}, body: {response.text}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
