"""
Test Command Center Stats API - Iteration 63
Tests for /api/admin/command-center/stats endpoint
Verifies dynamic data from database for admin dashboard
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuthentication:
    """Authentication tests for different user roles"""
    
    def test_admin_login(self):
        """Test platform admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nassaq.com",
            "password": "Admin@123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "platform_admin"
        assert data["user"]["full_name"] == "مدير منصة نَسَّق"
        return data["access_token"]
    
    def test_principal1_login(self):
        """Test school principal login for مدرسة النور"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "school_principal"
        return data["access_token"]
    
    def test_principal4_login(self):
        """Test school principal login for مدرسة الأحساء"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal4@nassaq.com",
            "password": "Principal@123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "school_principal"
        return data["access_token"]


class TestCommandCenterStats:
    """Tests for Command Center Stats API"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nassaq.com",
            "password": "Admin@123"
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Admin authentication failed")
    
    def test_command_center_stats_endpoint(self, admin_token):
        """Test /api/admin/command-center/stats returns correct data"""
        response = requests.get(
            f"{BASE_URL}/api/admin/command-center/stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields exist
        assert "registered_schools" in data
        assert "registered_students" in data
        assert "teachers_in_schools" in data
        assert "independent_teachers" in data
        assert "platform_accounts" in data
        assert "pending_requests" in data
        assert "ai_enabled_schools" in data
        assert "student_attendance_rate" in data
        assert "teacher_attendance_rate" in data
    
    def test_teachers_count_is_10(self, admin_token):
        """Verify teachers_in_schools equals 10 (5 per school x 2 schools)"""
        response = requests.get(
            f"{BASE_URL}/api/admin/command-center/stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Expected: 10 teachers (5 per school x 2 schools)
        assert data["teachers_in_schools"] == 10, f"Expected 10 teachers, got {data['teachers_in_schools']}"
    
    def test_students_count_is_50(self, admin_token):
        """Verify registered_students equals 50 (25 per school x 2 schools)"""
        response = requests.get(
            f"{BASE_URL}/api/admin/command-center/stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Expected: 50 students (25 per school x 2 schools)
        assert data["registered_students"] == 50, f"Expected 50 students, got {data['registered_students']}"
    
    def test_schools_count_is_2(self, admin_token):
        """Verify registered_schools equals 2"""
        response = requests.get(
            f"{BASE_URL}/api/admin/command-center/stats",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Expected: 2 schools
        assert data["registered_schools"] == 2, f"Expected 2 schools, got {data['registered_schools']}"
    
    def test_unauthorized_access(self):
        """Test that endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/admin/command-center/stats")
        assert response.status_code in [401, 403]
    
    def test_non_admin_access_denied(self):
        """Test that non-admin users cannot access command center stats"""
        # Login as principal
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        if login_response.status_code != 200:
            pytest.skip("Principal login failed")
        
        principal_token = login_response.json()["access_token"]
        
        # Try to access command center stats
        response = requests.get(
            f"{BASE_URL}/api/admin/command-center/stats",
            headers={"Authorization": f"Bearer {principal_token}"}
        )
        # Should be forbidden for non-admin
        assert response.status_code == 403


class TestTeachersAPI:
    """Tests for Teachers API to verify data consistency"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nassaq.com",
            "password": "Admin@123"
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Admin authentication failed")
    
    def test_total_teachers_count(self, admin_token):
        """Verify total teachers count from /api/teachers"""
        response = requests.get(
            f"{BASE_URL}/api/teachers",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        teachers = response.json()
        
        # Expected: 10 teachers total
        assert len(teachers) == 10, f"Expected 10 teachers, got {len(teachers)}"
    
    def test_school_001_teachers(self, admin_token):
        """Verify مدرسة النور (SCH-001) has 5 teachers"""
        response = requests.get(
            f"{BASE_URL}/api/teachers?school_id=SCH-001",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        teachers = response.json()
        
        assert len(teachers) == 5, f"Expected 5 teachers for SCH-001, got {len(teachers)}"
    
    def test_school_002_teachers(self, admin_token):
        """Verify مدرسة الأحساء (SCH-002) has 5 teachers"""
        response = requests.get(
            f"{BASE_URL}/api/teachers?school_id=SCH-002",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        teachers = response.json()
        
        assert len(teachers) == 5, f"Expected 5 teachers for SCH-002, got {len(teachers)}"


class TestSchoolDashboard:
    """Tests for School Dashboard API"""
    
    @pytest.fixture
    def principal1_token(self):
        """Get principal1 authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Principal1 authentication failed")
    
    def test_school_dashboard_stats(self, principal1_token):
        """Verify school dashboard shows correct counts"""
        response = requests.get(
            f"{BASE_URL}/api/school/dashboard",
            headers={"Authorization": f"Bearer {principal1_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify metrics
        metrics = data.get("metrics", data)
        
        # Check for expected values (25 students, 5 teachers, 3 classes)
        # API returns metrics as objects with 'value' key
        if "totalStudents" in metrics:
            students_val = metrics["totalStudents"]
            if isinstance(students_val, dict):
                students_val = students_val.get("value", students_val)
            assert students_val == 25, f"Expected 25 students, got {students_val}"
        if "totalTeachers" in metrics:
            teachers_val = metrics["totalTeachers"]
            if isinstance(teachers_val, dict):
                teachers_val = teachers_val.get("value", teachers_val)
            assert teachers_val == 5, f"Expected 5 teachers, got {teachers_val}"
        if "totalClasses" in metrics:
            classes_val = metrics["totalClasses"]
            if isinstance(classes_val, dict):
                classes_val = classes_val.get("value", classes_val)
            assert classes_val == 3, f"Expected 3 classes, got {classes_val}"


class TestSchoolSettings:
    """Tests for School Settings API"""
    
    @pytest.fixture
    def principal1_token(self):
        """Get principal1 authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Principal1 authentication failed")
    
    def test_school_settings_returns_data(self, principal1_token):
        """Verify school settings endpoint returns school data"""
        response = requests.get(
            f"{BASE_URL}/api/school/settings",
            headers={"Authorization": f"Bearer {principal1_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify school settings data exists (may contain academic_structure, subjects, etc.)
        assert len(data) > 0, "School settings should return data"
        # Check for common settings keys
        has_valid_data = any(key in data for key in ["school_info", "academic_structure", "subjects", "teacher_ranks", "school"])
        assert has_valid_data, f"Expected school settings data, got keys: {list(data.keys())}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
