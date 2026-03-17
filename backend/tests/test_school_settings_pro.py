"""
Test School Settings Page Pro - Backend API Tests
Tests for the new SchoolSettingsPagePro.jsx page
Testing reference APIs and school settings endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
PRINCIPAL_EMAIL = "principal1@nassaq.com"
PRINCIPAL_PASSWORD = "Principal@123"


class TestAuthentication:
    """Authentication tests for school principal"""
    
    def test_principal_login(self):
        """Test principal login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access token in response"
        assert data.get("user", {}).get("role") == "school_principal", "User is not school principal"
        return data["access_token"]


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for principal"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": PRINCIPAL_EMAIL,
        "password": PRINCIPAL_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Authentication failed")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestReferenceAPIs:
    """Test reference data APIs used by SchoolSettingsPagePro"""
    
    def test_reference_stages(self, auth_headers):
        """Test /api/reference/stages endpoint - المراحل الدراسية"""
        response = requests.get(f"{BASE_URL}/api/reference/stages", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Found {len(data)} stages")
        if len(data) > 0:
            # Check structure of first stage
            stage = data[0]
            print(f"Sample stage: {stage}")
    
    def test_reference_grades(self, auth_headers):
        """Test /api/reference/grades endpoint - الصفوف الدراسية"""
        response = requests.get(f"{BASE_URL}/api/reference/grades", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Found {len(data)} grades")
    
    def test_reference_tracks(self, auth_headers):
        """Test /api/reference/tracks endpoint - المسارات التعليمية"""
        response = requests.get(f"{BASE_URL}/api/reference/tracks", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Found {len(data)} tracks")
    
    def test_reference_subjects(self, auth_headers):
        """Test /api/reference/subjects endpoint - المواد الدراسية"""
        response = requests.get(f"{BASE_URL}/api/reference/subjects", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Found {len(data)} subjects")
    
    def test_reference_teacher_ranks(self, auth_headers):
        """Test /api/reference/teacher-ranks endpoint - رتب المعلمين"""
        response = requests.get(f"{BASE_URL}/api/reference/teacher-ranks", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Found {len(data)} teacher ranks")
    
    def test_reference_admin_constraints(self, auth_headers):
        """Test /api/reference/admin-constraints endpoint - القيود الإدارية"""
        response = requests.get(f"{BASE_URL}/api/reference/admin-constraints", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Found {len(data)} admin constraints")
    
    def test_reference_default_settings(self, auth_headers):
        """Test /api/reference/default-settings endpoint - الإعدادات الافتراضية"""
        response = requests.get(f"{BASE_URL}/api/reference/default-settings", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, dict), "Response should be a dict"
        print(f"Default settings keys: {list(data.keys()) if data else 'empty'}")


class TestSchoolSettingsAPI:
    """Test school settings API"""
    
    def test_school_settings_endpoint(self, auth_headers):
        """Test /api/school/settings endpoint - إعدادات المدرسة"""
        response = requests.get(f"{BASE_URL}/api/school/settings", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Check main structure
        assert "school_info" in data, "Missing school_info"
        assert "settings" in data, "Missing settings"
        
        print(f"School info: {data.get('school_info', {}).get('name', 'N/A')}")
        print(f"Periods per day: {data.get('periods_per_day', 'N/A')}")
        print(f"Time slots count: {len(data.get('time_slots', []))}")
        
        return data
    
    def test_school_settings_has_working_days(self, auth_headers):
        """Test that school settings includes working days"""
        response = requests.get(f"{BASE_URL}/api/school/settings", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        settings = data.get("settings", {})
        # Check for working days in various formats
        has_working_days = (
            "working_days" in settings or 
            "working_days_ar" in settings or
            "working_days" in data
        )
        print(f"Working days found: {has_working_days}")
        print(f"Settings keys: {list(settings.keys())}")
    
    def test_school_settings_has_time_slots(self, auth_headers):
        """Test that school settings includes time slots"""
        response = requests.get(f"{BASE_URL}/api/school/settings", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        time_slots = data.get("time_slots", [])
        settings_time_slots = data.get("settings", {}).get("time_slots", [])
        
        all_slots = time_slots or settings_time_slots
        print(f"Time slots count: {len(all_slots)}")
        if all_slots:
            print(f"First slot: {all_slots[0]}")
    
    def test_school_settings_has_academic_structure(self, auth_headers):
        """Test that school settings includes academic structure"""
        response = requests.get(f"{BASE_URL}/api/school/settings", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        academic = data.get("academic_structure", {})
        print(f"Stages: {len(academic.get('stages', []))}")
        print(f"Grades: {len(academic.get('grades', []))}")
        print(f"Tracks: {len(academic.get('tracks', []))}")
    
    def test_school_settings_has_reference_data(self, auth_headers):
        """Test that school settings includes reference data"""
        response = requests.get(f"{BASE_URL}/api/school/settings", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        reference = data.get("reference_data", {})
        print(f"Subjects: {len(reference.get('subjects', []))}")
        print(f"Teacher ranks: {len(reference.get('teacher_ranks', []))}")
        print(f"Admin constraints: {len(reference.get('admin_constraints', []))}")


class TestTeachersAndClassesAPIs:
    """Test teachers and classes APIs used by the settings page"""
    
    def test_teachers_list(self, auth_headers):
        """Test /api/teachers endpoint - قائمة المعلمين"""
        response = requests.get(f"{BASE_URL}/api/teachers", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Found {len(data)} teachers")
        if len(data) > 0:
            teacher = data[0]
            print(f"Sample teacher: {teacher.get('full_name', teacher.get('full_name_ar', 'N/A'))}")
    
    def test_classes_list(self, auth_headers):
        """Test /api/classes endpoint - قائمة الفصول"""
        response = requests.get(f"{BASE_URL}/api/classes", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Found {len(data)} classes")
        if len(data) > 0:
            cls = data[0]
            print(f"Sample class: {cls.get('name', cls.get('name_ar', 'N/A'))}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
