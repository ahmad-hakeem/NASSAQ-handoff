"""
NASSAQ Backend API Tests - Iteration 50
Testing new features:
1. POST /api/schools/draft - Save school as draft
2. GET /api/users - Users list with filters
3. GET /api/schools - Schools list with status filters
4. Authentication endpoints
"""

import pytest
import requests
import os
from datetime import datetime

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://school-timetable-ai.preview.emergentagent.com"

print(f"Testing against: {BASE_URL}")


class TestAuthentication:
    """Test authentication endpoints"""
    
    def test_login_platform_admin(self):
        """Test login as platform admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nassaq.com",
            "password": "Admin@123"
        })
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "access_token" in data, "Missing access_token in response"
        assert "user" in data, "Missing user in response"
        assert data["user"]["email"] == "admin@nassaq.com"
        assert data["user"]["role"] == "platform_admin"
        print(f"✓ Platform admin login successful: {data['user']['full_name']}")
    
    def test_login_school_principal(self):
        """Test login as school principal"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        
        assert "access_token" in data
        assert data["user"]["role"] == "school_principal"
        print(f"✓ School principal login successful: {data['user']['full_name']}")
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "invalid@nassaq.com",
            "password": "WrongPassword"
        })
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Invalid credentials correctly rejected")


class TestSchoolDraftAPI:
    """Test POST /api/schools/draft endpoint"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nassaq.com",
            "password": "Admin@123"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Admin authentication failed")
    
    def test_create_school_draft(self, admin_token):
        """Test creating a school as draft (setup status)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Create draft school
        draft_data = {
            "name": f"TEST_مدرسة اختبار المسودة {datetime.now().strftime('%H%M%S')}",
            "name_en": "TEST Draft School",
            "city": "الرياض",
            "region": "الرياض",
            "country": "SA",
            "student_capacity": 300,
            "school_type": "private",
            "stage": "primary",
            "principal_name": "أحمد محمد",
            "principal_email": f"test_principal_{datetime.now().strftime('%H%M%S')}@test.com",
            "principal_phone": "0501234567"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/schools/draft",
            json=draft_data,
            headers=headers
        )
        
        assert response.status_code == 200, f"Draft creation failed: {response.text}"
        data = response.json()
        
        # Validate response
        assert "id" in data, "Missing id in response"
        assert data["status"] == "setup", f"Expected status 'setup', got '{data['status']}'"
        assert data["name"] == draft_data["name"]
        assert data["city"] == draft_data["city"]
        
        print(f"✓ Draft school created successfully: {data['name']} (status: {data['status']})")
        
        # Store for cleanup
        return data["id"]
    
    def test_create_school_draft_unauthorized(self):
        """Test that unauthorized users cannot create draft schools"""
        # Try without token
        response = requests.post(f"{BASE_URL}/api/schools/draft", json={
            "name": "Unauthorized School"
        })
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Unauthorized draft creation correctly rejected")
    
    def test_create_school_draft_as_principal(self):
        """Test that school principal cannot create draft schools"""
        # Login as principal
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        
        if login_response.status_code != 200:
            pytest.skip("Principal login failed")
        
        token = login_response.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/schools/draft",
            json={"name": "Principal Draft School"},
            headers=headers
        )
        
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print("✓ Principal correctly denied draft creation access")


class TestUsersAPI:
    """Test users management endpoints"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nassaq.com",
            "password": "Admin@123"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Admin authentication failed")
    
    def test_get_users_list(self, admin_token):
        """Test getting users list"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(f"{BASE_URL}/api/users", headers=headers)
        
        assert response.status_code == 200, f"Failed to get users: {response.text}"
        data = response.json()
        
        # Should return a list
        assert isinstance(data, list), "Expected list of users"
        print(f"✓ Users list retrieved: {len(data)} users")
    
    def test_get_teacher_requests(self, admin_token):
        """Test getting independent teacher requests"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(f"{BASE_URL}/api/teacher-requests", headers=headers)
        
        # May return 200 or 404 if no requests
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Teacher requests retrieved: {len(data) if isinstance(data, list) else 'N/A'}")
        else:
            print(f"Teacher requests endpoint returned: {response.status_code}")


class TestSchoolsAPI:
    """Test schools management endpoints"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nassaq.com",
            "password": "Admin@123"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Admin authentication failed")
    
    def test_get_schools_list(self, admin_token):
        """Test getting schools list"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        response = requests.get(f"{BASE_URL}/api/schools", headers=headers)
        
        assert response.status_code == 200, f"Failed to get schools: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "Expected list of schools"
        print(f"✓ Schools list retrieved: {len(data)} schools")
        
        # Check for schools with different statuses
        statuses = set(school.get("status") for school in data)
        print(f"  School statuses found: {statuses}")
        
        # Verify setup status schools exist
        setup_schools = [s for s in data if s.get("status") == "setup"]
        print(f"  Schools in 'setup' status: {len(setup_schools)}")
    
    def test_get_schools_by_status(self, admin_token):
        """Test filtering schools by status"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Test active filter
        response = requests.get(
            f"{BASE_URL}/api/schools?status=active",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Active schools: {len(data)}")
        
        # Test setup filter
        response = requests.get(
            f"{BASE_URL}/api/schools?status=setup",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Setup schools: {len(data)}")


class TestDashboardAPI:
    """Test dashboard endpoints"""
    
    @pytest.fixture
    def principal_token(self):
        """Get principal authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Principal authentication failed")
    
    def test_get_dashboard_stats(self, principal_token):
        """Test getting dashboard statistics"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Dashboard stats retrieved")
            if isinstance(data, dict):
                for key in data.keys():
                    print(f"  - {key}: {data[key]}")
        else:
            print(f"Dashboard stats endpoint returned: {response.status_code}")


class TestHealthCheck:
    """Test health check endpoint"""
    
    def test_health_check(self):
        """Test API health check"""
        response = requests.get(f"{BASE_URL}/api/health")
        
        assert response.status_code == 200, f"Health check failed: {response.text}"
        print("✓ API health check passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
