"""
NASSAQ Platform API Tests
Tests for authentication, registration requests, schools, and dashboard endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://school-timetable-ai.preview.emergentagent.com').rstrip('/')

# Test credentials
ADMIN_EMAIL = "info@nassaqapp.com"
ADMIN_PASSWORD = "NassaqAdmin2026!##$$HBJ"


class TestHealthCheck:
    """Basic health check tests"""
    
    def test_api_root(self):
        """Test API root endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print(f"✓ API root returns: {data['message']}")


class TestAuthentication:
    """Authentication endpoint tests"""
    
    def test_login_success(self):
        """Test successful login with admin credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "access_token" in data
        assert "token_type" in data
        assert "user" in data
        assert data["token_type"] == "bearer"
        
        # Verify user data
        user = data["user"]
        assert user["email"] == ADMIN_EMAIL
        assert user["role"] == "platform_admin"
        assert user["is_active"] == True
        print(f"✓ Login successful for {user['email']} with role {user['role']}")
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@example.com",
            "password": "wrongpassword"
        })
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data
        print(f"✓ Invalid login correctly rejected: {data['detail']}")
    
    def test_login_missing_fields(self):
        """Test login with missing fields"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL
        })
        assert response.status_code == 422  # Validation error
        print("✓ Missing password correctly rejected")
    
    def test_get_current_user(self):
        """Test getting current user with valid token"""
        # First login to get token
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = login_response.json()["access_token"]
        
        # Get current user
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == ADMIN_EMAIL
        assert data["role"] == "platform_admin"
        print(f"✓ Current user retrieved: {data['full_name']}")
    
    def test_get_current_user_invalid_token(self):
        """Test getting current user with invalid token"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401
        print("✓ Invalid token correctly rejected")


class TestRegistrationRequests:
    """Registration requests endpoint tests"""
    
    def test_create_school_registration_request(self):
        """Test creating a school registration request"""
        response = requests.post(f"{BASE_URL}/api/registration-requests", json={
            "full_name": "Test School Admin",
            "phone": "+966501234567",
            "account_type": "school",
            "school_name": "Test School API",
            "school_email": "testapi@school.com",
            "school_city": "Riyadh"
        })
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "id" in data
        assert data["full_name"] == "Test School Admin"
        assert data["account_type"] == "school"
        assert data["status"] == "pending"
        print(f"✓ School registration request created with ID: {data['id']}")
    
    def test_create_teacher_registration_request(self):
        """Test creating a teacher registration request"""
        response = requests.post(f"{BASE_URL}/api/registration-requests", json={
            "full_name": "Test Teacher",
            "phone": "+966509876543",
            "account_type": "teacher",
            "email": "testteacher@school.com",
            "specialization": "Mathematics"
        })
        assert response.status_code == 200
        data = response.json()
        
        assert data["full_name"] == "Test Teacher"
        assert data["account_type"] == "teacher"
        assert data["status"] == "pending"
        print(f"✓ Teacher registration request created with ID: {data['id']}")
    
    def test_get_registration_requests_admin(self):
        """Test getting registration requests as admin"""
        # Login as admin
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = login_response.json()["access_token"]
        
        # Get registration requests
        response = requests.get(
            f"{BASE_URL}/api/registration-requests",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Retrieved {len(data)} registration requests")
    
    def test_get_registration_requests_unauthorized(self):
        """Test getting registration requests without auth"""
        response = requests.get(f"{BASE_URL}/api/registration-requests")
        assert response.status_code in [401, 403]
        print("✓ Unauthorized access correctly rejected")


class TestDashboardStats:
    """Dashboard statistics endpoint tests"""
    
    def test_get_dashboard_stats(self):
        """Test getting dashboard statistics"""
        # Login as admin
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = login_response.json()["access_token"]
        
        # Get dashboard stats
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "total_schools" in data
        assert "total_students" in data
        assert "total_teachers" in data
        assert "active_schools" in data
        assert "pending_schools" in data
        assert "total_users" in data
        
        # Verify data types
        assert isinstance(data["total_schools"], int)
        assert isinstance(data["total_students"], int)
        print(f"✓ Dashboard stats: {data['total_schools']} schools, {data['total_users']} users")
    
    def test_get_dashboard_stats_unauthorized(self):
        """Test getting dashboard stats without auth"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats")
        assert response.status_code in [401, 403]
        print("✓ Unauthorized access correctly rejected")


class TestSchools:
    """Schools endpoint tests"""
    
    def test_get_schools_admin(self):
        """Test getting schools list as admin"""
        # Login as admin
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = login_response.json()["access_token"]
        
        # Get schools
        response = requests.get(
            f"{BASE_URL}/api/schools",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Retrieved {len(data)} schools")
        
        # Verify school structure if any exist
        if len(data) > 0:
            school = data[0]
            assert "id" in school
            assert "name" in school
            assert "code" in school
            assert "status" in school
            print(f"✓ First school: {school['name']} ({school['code']})")
    
    def test_create_school_admin(self):
        """Test creating a school as admin"""
        # Login as admin
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = login_response.json()["access_token"]
        
        import uuid
        unique_code = f"TEST{uuid.uuid4().hex[:6].upper()}"
        
        # Create school
        response = requests.post(
            f"{BASE_URL}/api/schools",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "مدرسة الاختبار API",
                "code": unique_code,
                "email": f"test{unique_code.lower()}@school.com",
                "city": "Riyadh",
                "student_capacity": 500
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["name"] == "مدرسة الاختبار API"
        assert data["code"] == unique_code
        assert data["status"] == "pending"
        print(f"✓ School created: {data['name']} with code {data['code']}")
    
    def test_get_schools_unauthorized(self):
        """Test getting schools without auth"""
        response = requests.get(f"{BASE_URL}/api/schools")
        assert response.status_code in [401, 403]
        print("✓ Unauthorized access correctly rejected")


class TestHakimAI:
    """Hakim AI assistant endpoint tests"""
    
    def test_hakim_chat(self):
        """Test Hakim AI chat endpoint"""
        response = requests.post(f"{BASE_URL}/api/hakim/chat", json={
            "message": "مرحبا، كيف يمكنني إضافة مدرسة جديدة؟"
        })
        assert response.status_code == 200
        data = response.json()
        
        assert "response" in data
        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)
        print(f"✓ Hakim response: {data['response'][:100]}...")
    
    def test_hakim_chat_with_context(self):
        """Test Hakim AI chat with context"""
        response = requests.post(f"{BASE_URL}/api/hakim/chat", json={
            "message": "أريد معرفة المزيد عن إدارة الطلاب",
            "context": "admin_dashboard",
            "user_role": "platform_admin"
        })
        assert response.status_code == 200
        data = response.json()
        
        assert "response" in data
        print(f"✓ Hakim contextual response received")


class TestSeedData:
    """Seed data endpoint tests"""
    
    def test_seed_admin(self):
        """Test seeding admin user"""
        response = requests.post(f"{BASE_URL}/api/seed/admin")
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "email" in data
        assert data["email"] == "info@nassaqapp.com"
        print(f"✓ Admin seed: {data['message']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
