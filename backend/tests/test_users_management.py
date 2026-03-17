"""
Backend API Tests for Users Management
Tests for /api/users/create and /api/users/platform-users endpoints
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "info@nassaqapp.com"
ADMIN_PASSWORD = "NassaqAdmin2026!##$$HBJ"


class TestAuthentication:
    """Test authentication flow"""
    
    def test_login_success(self):
        """Test successful login with admin credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == ADMIN_EMAIL
        print(f"✓ Login successful for {ADMIN_EMAIL}")
        return data["access_token"]
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@email.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        print("✓ Invalid credentials correctly rejected")


class TestUserCreation:
    """Test /api/users/create endpoint"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_create_teacher_with_all_fields(self, auth_token):
        """Test creating a teacher with all new fields"""
        unique_id = str(uuid.uuid4())[:8]
        payload = {
            "email": f"test_teacher_{unique_id}@nassaq.com",
            "password": "TestPassword123!",
            "full_name": "معلم اختبار",
            "role": "teacher",
            "phone": f"05{unique_id[:8]}",
            "region": "riyadh",
            "city": "riyadh",
            "educational_department": "riyadh_edu",
            "school_name_ar": "مدرسة الاختبار",
            "school_name_en": "Test School",
            "permissions": ["view_students", "manage_grades"]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/users/create",
            json=payload,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200, f"Create user failed: {response.text}"
        data = response.json()
        assert data["email"] == payload["email"]
        assert data["full_name"] == payload["full_name"]
        assert data["role"] == "teacher"
        assert data["region"] == "riyadh"
        assert data["city"] == "riyadh"
        assert data["must_change_password"] == True
        print(f"✓ Teacher created successfully: {data['email']}")
    
    def test_create_platform_operations_manager(self, auth_token):
        """Test creating a platform operations manager"""
        unique_id = str(uuid.uuid4())[:8]
        payload = {
            "email": f"test_ops_{unique_id}@nassaq.com",
            "password": "TestPassword123!",
            "full_name": "مدير عمليات اختبار",
            "role": "platform_operations_manager",
            "phone": f"05{unique_id[:8]}",
            "permissions": ["manage_schools", "view_reports"]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/users/create",
            json=payload,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200, f"Create user failed: {response.text}"
        data = response.json()
        assert data["role"] == "platform_operations_manager"
        print(f"✓ Operations manager created: {data['email']}")
    
    def test_create_user_duplicate_email(self, auth_token):
        """Test that duplicate email is rejected"""
        # First create a user
        unique_id = str(uuid.uuid4())[:8]
        payload = {
            "email": f"test_dup_{unique_id}@nassaq.com",
            "password": "TestPassword123!",
            "full_name": "مستخدم مكرر",
            "role": "teacher"
        }
        
        response1 = requests.post(
            f"{BASE_URL}/api/users/create",
            json=payload,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response1.status_code == 200
        
        # Try to create with same email
        response2 = requests.post(
            f"{BASE_URL}/api/users/create",
            json=payload,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response2.status_code == 400
        print("✓ Duplicate email correctly rejected")
    
    def test_create_user_invalid_role(self, auth_token):
        """Test that invalid role is rejected"""
        unique_id = str(uuid.uuid4())[:8]
        payload = {
            "email": f"test_invalid_{unique_id}@nassaq.com",
            "password": "TestPassword123!",
            "full_name": "مستخدم غير صالح",
            "role": "invalid_role"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/users/create",
            json=payload,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 400
        print("✓ Invalid role correctly rejected")
    
    def test_create_user_unauthenticated(self):
        """Test that unauthenticated request is rejected"""
        payload = {
            "email": "test@nassaq.com",
            "password": "TestPassword123!",
            "full_name": "Test User",
            "role": "teacher"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/users/create",
            json=payload
        )
        assert response.status_code == 403
        print("✓ Unauthenticated request correctly rejected")


class TestPlatformUsers:
    """Test /api/users/platform-users endpoint"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_get_platform_users(self, auth_token):
        """Test fetching platform users list"""
        response = requests.get(
            f"{BASE_URL}/api/users/platform-users",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200, f"Get users failed: {response.text}"
        data = response.json()
        assert "users" in data
        assert "total" in data
        assert isinstance(data["users"], list)
        print(f"✓ Platform users fetched: {data['total']} users")
    
    def test_get_platform_users_with_role_filter(self, auth_token):
        """Test fetching users with role filter"""
        response = requests.get(
            f"{BASE_URL}/api/users/platform-users",
            params={"role": "teacher"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        # All returned users should have teacher role
        for user in data["users"]:
            assert user["role"] == "teacher"
        print(f"✓ Filtered by role: {len(data['users'])} teachers")
    
    def test_get_platform_users_with_search(self, auth_token):
        """Test fetching users with search query"""
        response = requests.get(
            f"{BASE_URL}/api/users/platform-users",
            params={"search": "test"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Search results: {len(data['users'])} users matching 'test'")
    
    def test_get_platform_users_unauthenticated(self):
        """Test that unauthenticated request is rejected"""
        response = requests.get(f"{BASE_URL}/api/users/platform-users")
        assert response.status_code == 403
        print("✓ Unauthenticated request correctly rejected")


class TestDashboardStats:
    """Test dashboard statistics endpoint"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_get_dashboard_stats(self, auth_token):
        """Test fetching dashboard statistics"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200, f"Get stats failed: {response.text}"
        data = response.json()
        
        # Check required fields
        assert "total_schools" in data
        assert "total_students" in data
        assert "total_teachers" in data
        assert "active_schools" in data
        assert "pending_requests" in data
        
        print(f"✓ Dashboard stats: {data['total_schools']} schools, {data['total_students']} students, {data['total_teachers']} teachers")


class TestRegistrationRequests:
    """Test registration requests endpoints"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_get_registration_requests(self, auth_token):
        """Test fetching registration requests"""
        response = requests.get(
            f"{BASE_URL}/api/registration-requests",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200, f"Get requests failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Registration requests fetched: {len(data)} requests")
    
    def test_get_pending_requests(self, auth_token):
        """Test fetching pending registration requests"""
        response = requests.get(
            f"{BASE_URL}/api/registration-requests",
            params={"status": "pending"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        # All returned requests should be pending
        for req in data:
            assert req["status"] == "pending"
        print(f"✓ Pending requests: {len(data)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
