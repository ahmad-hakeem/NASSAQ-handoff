"""
Test Suite for Principal Timetable Page APIs - Iteration 81
Tests the new timetable page APIs for the PrincipalTimetablePage component

APIs tested:
- GET /api/smart-scheduling/timetable/versions - Get timetable versions
- GET /api/timetable-readiness/check - Check readiness for timetable generation
- GET /api/school/info - Get school information
- GET /api/smart-scheduling/timetable/active/sessions - Get active timetable sessions
- GET /api/classes - Get classes list
- GET /api/teachers - Get teachers list
- GET /api/school/subjects/unique - Get unique subjects
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "principal1@nassaq.com"
TEST_PASSWORD = "Principal@123"


class TestAuthentication:
    """Authentication tests"""
    
    def test_login_success(self):
        """Test login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data or "token" in data, "No token in response"
        return data.get("access_token") or data.get("token")


class TestTimetableVersionsAPI:
    """Tests for /api/smart-scheduling/timetable/versions"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token") or data.get("token")
            self.school_id = data.get("school_id") or data.get("user", {}).get("school_id")
            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "X-School-Context": self.school_id or "SCH-001"
            }
        else:
            pytest.skip("Authentication failed")
    
    def test_get_timetable_versions(self):
        """Test getting timetable versions list"""
        response = requests.get(
            f"{BASE_URL}/api/smart-scheduling/timetable/versions",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "versions" in data, "Response should contain 'versions' key"
        assert isinstance(data["versions"], list), "versions should be a list"
        assert "total" in data, "Response should contain 'total' key"
        
        # If versions exist, verify structure
        if len(data["versions"]) > 0:
            version = data["versions"][0]
            assert "id" in version, "Version should have 'id'"
            assert "status" in version, "Version should have 'status'"


class TestTimetableReadinessAPI:
    """Tests for /api/timetable-readiness/check"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token") or data.get("token")
            self.school_id = data.get("school_id") or data.get("user", {}).get("school_id")
            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "X-School-Context": self.school_id or "SCH-001"
            }
        else:
            pytest.skip("Authentication failed")
    
    def test_get_readiness_check(self):
        """Test getting timetable readiness check"""
        response = requests.get(
            f"{BASE_URL}/api/timetable-readiness/check",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "status" in data, "Response should contain 'status'"
        assert data["status"] in ["NOT_READY", "PARTIALLY_READY", "FULLY_READY"], \
            f"Invalid status: {data['status']}"
        assert "percentage" in data, "Response should contain 'percentage'"
        assert "can_generate" in data, "Response should contain 'can_generate'"
        assert "categories" in data, "Response should contain 'categories'"
        
        # Verify categories structure
        categories = data["categories"]
        expected_categories = [
            "academic_context", "school_days", "day_structure", 
            "classes", "teachers", "teacher_assignments"
        ]
        for cat in expected_categories:
            assert cat in categories, f"Missing category: {cat}"
            assert "score" in categories[cat], f"Category {cat} missing 'score'"
            assert "max_score" in categories[cat], f"Category {cat} missing 'max_score'"


class TestSchoolInfoAPI:
    """Tests for /api/school/info"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token") or data.get("token")
            self.school_id = data.get("school_id") or data.get("user", {}).get("school_id")
            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "X-School-Context": self.school_id or "SCH-001"
            }
        else:
            pytest.skip("Authentication failed")
    
    def test_get_school_info(self):
        """Test getting school information"""
        response = requests.get(
            f"{BASE_URL}/api/school/info",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response has school data
        # School info can have various structures, check for common fields
        assert data is not None, "Response should not be empty"
        # Check for at least one identifying field
        has_identifier = any([
            data.get("name_ar"),
            data.get("school_name_ar"),
            data.get("name"),
            data.get("id"),
            data.get("school_id")
        ])
        assert has_identifier, "School info should have at least one identifier"


class TestActiveTimetableSessionsAPI:
    """Tests for /api/smart-scheduling/timetable/active/sessions"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token") or data.get("token")
            self.school_id = data.get("school_id") or data.get("user", {}).get("school_id")
            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "X-School-Context": self.school_id or "SCH-001"
            }
        else:
            pytest.skip("Authentication failed")
    
    def test_get_active_sessions(self):
        """Test getting active timetable sessions"""
        response = requests.get(
            f"{BASE_URL}/api/smart-scheduling/timetable/active/sessions",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "sessions" in data, "Response should contain 'sessions'"
        assert isinstance(data["sessions"], list), "sessions should be a list"
        assert "total" in data, "Response should contain 'total'"


class TestClassesAPI:
    """Tests for /api/classes"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token") or data.get("token")
            self.school_id = data.get("school_id") or data.get("user", {}).get("school_id")
            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "X-School-Context": self.school_id or "SCH-001"
            }
        else:
            pytest.skip("Authentication failed")
    
    def test_get_classes(self):
        """Test getting classes list"""
        response = requests.get(
            f"{BASE_URL}/api/classes",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Response can be list or dict with classes key
        if isinstance(data, list):
            classes = data
        else:
            classes = data.get("classes", [])
        
        assert isinstance(classes, list), "Classes should be a list"
        
        # If classes exist, verify structure
        if len(classes) > 0:
            cls = classes[0]
            assert "id" in cls, "Class should have 'id'"


class TestTeachersAPI:
    """Tests for /api/teachers"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token") or data.get("token")
            self.school_id = data.get("school_id") or data.get("user", {}).get("school_id")
            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "X-School-Context": self.school_id or "SCH-001"
            }
        else:
            pytest.skip("Authentication failed")
    
    def test_get_teachers(self):
        """Test getting teachers list"""
        response = requests.get(
            f"{BASE_URL}/api/teachers",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Response can be list or dict with teachers key
        if isinstance(data, list):
            teachers = data
        else:
            teachers = data.get("teachers", [])
        
        assert isinstance(teachers, list), "Teachers should be a list"
        
        # If teachers exist, verify structure
        if len(teachers) > 0:
            teacher = teachers[0]
            assert "id" in teacher, "Teacher should have 'id'"


class TestSubjectsAPI:
    """Tests for /api/school/subjects/unique"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token") or data.get("token")
            self.school_id = data.get("school_id") or data.get("user", {}).get("school_id")
            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "X-School-Context": self.school_id or "SCH-001"
            }
        else:
            pytest.skip("Authentication failed")
    
    def test_get_unique_subjects(self):
        """Test getting unique subjects list"""
        response = requests.get(
            f"{BASE_URL}/api/school/subjects/unique",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Response can be list or dict with subjects key
        if isinstance(data, list):
            subjects = data
        else:
            subjects = data.get("subjects", [])
        
        assert isinstance(subjects, list), "Subjects should be a list"


class TestTimeSlotsAPI:
    """Tests for /api/time-slots (Note: frontend calls /api/school-settings/time-slots which is wrong)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token") or data.get("token")
            self.school_id = data.get("school_id") or data.get("user", {}).get("school_id")
            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "X-School-Context": self.school_id or "SCH-001"
            }
        else:
            pytest.skip("Authentication failed")
    
    def test_get_time_slots_correct_endpoint(self):
        """Test getting time slots from correct endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/time-slots",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Response should be a list
        assert isinstance(data, list), "Time slots should be a list"
    
    def test_get_time_slots_wrong_endpoint_returns_404(self):
        """Test that wrong endpoint returns 404 (frontend bug)"""
        response = requests.get(
            f"{BASE_URL}/api/school-settings/time-slots",
            headers=self.headers
        )
        # This should return 404 - documenting the bug
        assert response.status_code == 404, \
            f"Expected 404 for wrong endpoint, got {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
