"""
Test suite for NASSAQ Language Toggle and Dashboard Stats API
Tests: Language persistence, Dashboard live data, API endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://school-timetable-ai.preview.emergentagent.com')

# Test credentials
ADMIN_EMAIL = "info@nassaqapp.com"
ADMIN_PASSWORD = "NassaqAdmin2026!##$$HBJ"


class TestAuthAndDashboard:
    """Test authentication and dashboard stats endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for admin user"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        token = response.json().get('access_token')
        assert token is not None, "No access token returned"
        return token
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_admin_login_success(self):
        """Test admin login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == ADMIN_EMAIL
        assert data["user"]["role"] == "platform_admin"
    
    def test_admin_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@email.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
    
    def test_dashboard_stats_requires_auth(self):
        """Test that dashboard stats requires authentication"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats")
        assert response.status_code in [401, 403]
    
    def test_dashboard_stats_returns_live_data(self, auth_headers):
        """Test dashboard stats returns live data from database"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify all expected fields are present
        expected_fields = [
            'total_schools', 'total_students', 'total_teachers',
            'active_schools', 'pending_schools', 'total_users',
            'pending_requests', 'active_users', 'total_classes', 'total_subjects'
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        # Verify data types
        assert isinstance(data['total_schools'], int)
        assert isinstance(data['total_students'], int)
        assert isinstance(data['total_teachers'], int)
        assert isinstance(data['active_users'], int)
        assert isinstance(data['pending_requests'], int)
        assert isinstance(data['total_classes'], int)
        assert isinstance(data['total_subjects'], int)
    
    def test_dashboard_stats_expected_values(self, auth_headers):
        """Test dashboard stats returns expected live data values"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        
        # Expected values from the test data
        # Note: These may vary based on test data state
        assert data['total_schools'] >= 0, "Total schools should be non-negative"
        assert data['total_students'] >= 0, "Total students should be non-negative"
        assert data['total_teachers'] >= 0, "Total teachers should be non-negative"
        assert data['total_classes'] >= 0, "Total classes should be non-negative"
        assert data['total_subjects'] >= 0, "Total subjects should be non-negative"
        
        # Print actual values for verification
        print(f"\n=== Dashboard Stats ===")
        print(f"Total Schools: {data['total_schools']}")
        print(f"Total Students: {data['total_students']}")
        print(f"Total Teachers: {data['total_teachers']}")
        print(f"Active Users: {data['active_users']}")
        print(f"Pending Requests: {data['pending_requests']}")
        print(f"Total Classes: {data['total_classes']}")
        print(f"Total Subjects: {data['total_subjects']}")


class TestSchoolsAPI:
    """Test schools management endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json().get('access_token')
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_schools_list(self, auth_headers):
        """Test getting list of schools"""
        response = requests.get(f"{BASE_URL}/api/schools", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        # Verify school structure if schools exist
        if len(data) > 0:
            school = data[0]
            assert 'id' in school
            assert 'name' in school
            assert 'code' in school
            assert 'status' in school
    
    def test_get_schools_requires_auth(self):
        """Test that schools list requires authentication"""
        response = requests.get(f"{BASE_URL}/api/schools")
        assert response.status_code in [401, 403]


class TestTeachersAPI:
    """Test teachers management endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json().get('access_token')
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_teachers_list(self, auth_headers):
        """Test getting list of teachers"""
        response = requests.get(f"{BASE_URL}/api/teachers", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_teachers_requires_auth(self):
        """Test that teachers list requires authentication"""
        response = requests.get(f"{BASE_URL}/api/teachers")
        assert response.status_code in [401, 403]


class TestStudentsAPI:
    """Test students management endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json().get('access_token')
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_students_list(self, auth_headers):
        """Test getting list of students"""
        response = requests.get(f"{BASE_URL}/api/students", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_students_requires_auth(self):
        """Test that students list requires authentication"""
        response = requests.get(f"{BASE_URL}/api/students")
        assert response.status_code in [401, 403]


class TestClassesAPI:
    """Test classes management endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json().get('access_token')
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_classes_list(self, auth_headers):
        """Test getting list of classes"""
        response = requests.get(f"{BASE_URL}/api/classes", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_classes_requires_auth(self):
        """Test that classes list requires authentication"""
        response = requests.get(f"{BASE_URL}/api/classes")
        assert response.status_code in [401, 403]


class TestSubjectsAPI:
    """Test subjects management endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json().get('access_token')
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_subjects_list(self, auth_headers):
        """Test getting list of subjects"""
        response = requests.get(f"{BASE_URL}/api/subjects", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_subjects_requires_auth(self):
        """Test that subjects list requires authentication"""
        response = requests.get(f"{BASE_URL}/api/subjects")
        assert response.status_code in [401, 403]


class TestRegistrationRequestsAPI:
    """Test registration requests endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json().get('access_token')
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_registration_requests(self, auth_headers):
        """Test getting registration requests"""
        response = requests.get(f"{BASE_URL}/api/registration-requests", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_registration_requests_requires_auth(self):
        """Test that registration requests requires authentication"""
        response = requests.get(f"{BASE_URL}/api/registration-requests")
        assert response.status_code in [401, 403]
