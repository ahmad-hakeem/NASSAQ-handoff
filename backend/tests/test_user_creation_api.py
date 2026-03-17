"""
Test suite for /api/users/create endpoint
Tests the new teacher creation flow with region, city, educational_department, school_name fields
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "info@nassaqapp.com"
ADMIN_PASSWORD = "NassaqAdmin2026!##$$HBJ"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for platform admin"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture
def api_client(auth_token):
    """Create authenticated API client"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestUserCreationEndpoint:
    """Tests for /api/users/create endpoint"""
    
    def test_create_teacher_with_all_fields(self, api_client):
        """Test creating a teacher with all new fields (region, city, educational_department, school_name)"""
        timestamp = str(int(time.time()))
        
        user_data = {
            "email": f"test_teacher_{timestamp}@nassaq.com",
            "password": "TestPass123!",
            "full_name": "معلم اختبار كامل",
            "role": "teacher",
            "phone": f"055{timestamp[-7:]}",
            "region": "riyadh",
            "city": "riyadh",
            "educational_department": "riyadh_edu",
            "school_name_ar": "مدرسة الاختبار",
            "school_name_en": "Test School",
            "permissions": ["view_classes", "manage_own_class", "view_class_students"]
        }
        
        response = api_client.post(f"{BASE_URL}/api/users/create", json=user_data)
        
        assert response.status_code == 200, f"Failed to create user: {response.text}"
        
        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["full_name"] == user_data["full_name"]
        assert data["role"] == "teacher"
        assert data["region"] == "riyadh"
        assert data["city"] == "riyadh"
        assert data["educational_department"] == "riyadh_edu"
        assert data["school_name_ar"] == "مدرسة الاختبار"
        assert data["school_name_en"] == "Test School"
        assert data["is_active"] == True
        assert data["must_change_password"] == True
        assert "id" in data
        assert "created_at" in data
        
        print(f"✓ Created teacher with ID: {data['id']}")
    
    def test_create_teacher_minimal_fields(self, api_client):
        """Test creating a teacher with only required fields"""
        timestamp = str(int(time.time()))
        
        user_data = {
            "email": f"test_teacher_min_{timestamp}@nassaq.com",
            "password": "TestPass123!",
            "full_name": "معلم اختبار بسيط",
            "role": "teacher",
            "permissions": ["view_classes"]
        }
        
        response = api_client.post(f"{BASE_URL}/api/users/create", json=user_data)
        
        assert response.status_code == 200, f"Failed to create user: {response.text}"
        
        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["role"] == "teacher"
        # Optional fields should be None
        assert data.get("region") is None
        assert data.get("city") is None
        
        print(f"✓ Created teacher with minimal fields, ID: {data['id']}")
    
    def test_create_platform_operations_manager(self, api_client):
        """Test creating a platform operations manager"""
        timestamp = str(int(time.time()))
        
        user_data = {
            "email": f"test_ops_manager_{timestamp}@nassaq.com",
            "password": "TestPass123!",
            "full_name": "مدير عمليات اختبار",
            "role": "platform_operations_manager",
            "permissions": ["view_dashboard", "manage_operations"]
        }
        
        response = api_client.post(f"{BASE_URL}/api/users/create", json=user_data)
        
        assert response.status_code == 200, f"Failed to create user: {response.text}"
        
        data = response.json()
        assert data["role"] == "platform_operations_manager"
        
        print(f"✓ Created platform_operations_manager, ID: {data['id']}")
    
    def test_create_user_duplicate_email(self, api_client):
        """Test that duplicate email is rejected"""
        timestamp = str(int(time.time()))
        email = f"test_dup_{timestamp}@nassaq.com"
        
        user_data = {
            "email": email,
            "password": "TestPass123!",
            "full_name": "مستخدم أول",
            "role": "teacher",
            "permissions": ["view_classes"]
        }
        
        # Create first user
        response1 = api_client.post(f"{BASE_URL}/api/users/create", json=user_data)
        assert response1.status_code == 200
        
        # Try to create second user with same email
        user_data["full_name"] = "مستخدم ثاني"
        response2 = api_client.post(f"{BASE_URL}/api/users/create", json=user_data)
        
        assert response2.status_code == 400
        assert "البريد الإلكتروني مستخدم مسبقاً" in response2.text
        
        print("✓ Duplicate email correctly rejected")
    
    def test_create_user_invalid_role(self, api_client):
        """Test that invalid role is rejected"""
        timestamp = str(int(time.time()))
        
        user_data = {
            "email": f"test_invalid_role_{timestamp}@nassaq.com",
            "password": "TestPass123!",
            "full_name": "مستخدم دور خاطئ",
            "role": "invalid_role",
            "permissions": []
        }
        
        response = api_client.post(f"{BASE_URL}/api/users/create", json=user_data)
        
        assert response.status_code == 400
        assert "نوع الحساب غير مسموح به" in response.text
        
        print("✓ Invalid role correctly rejected")
    
    def test_create_user_all_allowed_roles(self, api_client):
        """Test creating users with all allowed roles"""
        allowed_roles = [
            'platform_operations_manager',
            'platform_technical_admin',
            'platform_support_specialist',
            'platform_data_analyst',
            'platform_security_officer',
            'testing_account',
            'teacher'
        ]
        
        for role in allowed_roles:
            timestamp = str(int(time.time() * 1000))  # Use milliseconds for uniqueness
            
            user_data = {
                "email": f"test_{role}_{timestamp}@nassaq.com",
                "password": "TestPass123!",
                "full_name": f"اختبار {role}",
                "role": role,
                "permissions": ["view_dashboard"]
            }
            
            response = api_client.post(f"{BASE_URL}/api/users/create", json=user_data)
            
            assert response.status_code == 200, f"Failed to create {role}: {response.text}"
            print(f"✓ Created user with role: {role}")
            
            time.sleep(0.1)  # Small delay to ensure unique timestamps


class TestUserCreationValidation:
    """Tests for input validation on user creation"""
    
    def test_missing_email(self, api_client):
        """Test that missing email is rejected"""
        user_data = {
            "password": "TestPass123!",
            "full_name": "مستخدم بدون بريد",
            "role": "teacher",
            "permissions": []
        }
        
        response = api_client.post(f"{BASE_URL}/api/users/create", json=user_data)
        
        assert response.status_code == 422  # Validation error
        print("✓ Missing email correctly rejected")
    
    def test_invalid_email_format(self, api_client):
        """Test that invalid email format is rejected"""
        user_data = {
            "email": "invalid-email",
            "password": "TestPass123!",
            "full_name": "مستخدم بريد خاطئ",
            "role": "teacher",
            "permissions": []
        }
        
        response = api_client.post(f"{BASE_URL}/api/users/create", json=user_data)
        
        assert response.status_code == 422  # Validation error
        print("✓ Invalid email format correctly rejected")
    
    def test_missing_password(self, api_client):
        """Test that missing password is rejected"""
        timestamp = str(int(time.time()))
        
        user_data = {
            "email": f"test_no_pass_{timestamp}@nassaq.com",
            "full_name": "مستخدم بدون كلمة مرور",
            "role": "teacher",
            "permissions": []
        }
        
        response = api_client.post(f"{BASE_URL}/api/users/create", json=user_data)
        
        assert response.status_code == 422  # Validation error
        print("✓ Missing password correctly rejected")


class TestUserCreationAuthorization:
    """Tests for authorization on user creation"""
    
    def test_unauthenticated_request(self):
        """Test that unauthenticated request is rejected"""
        timestamp = str(int(time.time()))
        
        user_data = {
            "email": f"test_unauth_{timestamp}@nassaq.com",
            "password": "TestPass123!",
            "full_name": "مستخدم غير مصرح",
            "role": "teacher",
            "permissions": []
        }
        
        response = requests.post(
            f"{BASE_URL}/api/users/create",
            json=user_data,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code in [401, 403]  # Either unauthorized or forbidden
        print("✓ Unauthenticated request correctly rejected")
    
    def test_invalid_token(self):
        """Test that invalid token is rejected"""
        timestamp = str(int(time.time()))
        
        user_data = {
            "email": f"test_invalid_token_{timestamp}@nassaq.com",
            "password": "TestPass123!",
            "full_name": "مستخدم توكن خاطئ",
            "role": "teacher",
            "permissions": []
        }
        
        response = requests.post(
            f"{BASE_URL}/api/users/create",
            json=user_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer invalid_token_here"
            }
        )
        
        assert response.status_code == 401
        print("✓ Invalid token correctly rejected")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
