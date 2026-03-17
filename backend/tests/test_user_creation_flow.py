"""
Test User Creation API - Testing platform_admin role and CreateUserWizard flow
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://school-timetable-ai.preview.emergentagent.com')

class TestUserCreationAPI:
    """Test user creation endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login and get token"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "info@nassaqapp.com",
                "password": "NassaqAdmin2026!##$$HBJ"
            }
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json()["access_token"]
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def test_create_user_with_platform_admin_role(self):
        """Test creating a user with platform_admin role"""
        timestamp = str(int(time.time()))
        user_data = {
            "email": f"test_admin_{timestamp}@nassaq.com",
            "password": "TestPass123!@#",
            "full_name": "مستخدم اختبار مدير",
            "role": "platform_admin",
            "phone": f"05{timestamp[-10:]}",
            "permissions": ["manage_schools", "manage_users", "manage_roles"]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/users/create",
            json=user_data,
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Failed to create user: {response.text}"
        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["role"] == "platform_admin"
        assert data["full_name"] == user_data["full_name"]
        assert data["must_change_password"] == True
        print(f"✓ Created platform_admin user: {data['email']}")
    
    def test_create_user_with_operations_manager_role(self):
        """Test creating a user with platform_operations_manager role"""
        timestamp = str(int(time.time()))
        user_data = {
            "email": f"test_ops_{timestamp}@nassaq.com",
            "password": "TestPass123!@#",
            "full_name": "مدير عمليات اختبار",
            "role": "platform_operations_manager",
            "phone": f"05{timestamp[-10:]}1",
            "permissions": ["view_dashboard", "view_schools", "view_users"]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/users/create",
            json=user_data,
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Failed to create user: {response.text}"
        data = response.json()
        assert data["role"] == "platform_operations_manager"
        print(f"✓ Created operations_manager user: {data['email']}")
    
    def test_create_user_with_teacher_role(self):
        """Test creating a user with teacher role"""
        timestamp = str(int(time.time()))
        user_data = {
            "email": f"test_teacher_{timestamp}@nassaq.com",
            "password": "TestPass123!@#",
            "full_name": "معلم اختبار",
            "role": "teacher",
            "phone": f"05{timestamp[-10:]}2",
            "region": "riyadh",
            "city": "riyadh",
            "educational_department": "riyadh_edu",
            "school_name_ar": "مدرسة الاختبار",
            "school_name_en": "Test School",
            "permissions": ["view_classes", "manage_own_class"]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/users/create",
            json=user_data,
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Failed to create user: {response.text}"
        data = response.json()
        assert data["role"] == "teacher"
        assert data["region"] == "riyadh"
        assert data["city"] == "riyadh"
        print(f"✓ Created teacher user: {data['email']}")
    
    def test_create_user_with_testing_account_role(self):
        """Test creating a user with testing_account role"""
        timestamp = str(int(time.time()))
        user_data = {
            "email": f"test_account_{timestamp}@nassaq.com",
            "password": "TestPass123!@#",
            "full_name": "حساب اختبار",
            "role": "testing_account",
            "phone": f"05{timestamp[-10:]}3",
            "permissions": ["test_features", "view_test_data"]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/users/create",
            json=user_data,
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Failed to create user: {response.text}"
        data = response.json()
        assert data["role"] == "testing_account"
        print(f"✓ Created testing_account user: {data['email']}")
    
    def test_create_user_duplicate_email_fails(self):
        """Test that creating a user with duplicate email fails"""
        timestamp = str(int(time.time()))
        user_data = {
            "email": "info@nassaqapp.com",  # Existing email
            "password": "TestPass123!@#",
            "full_name": "مستخدم مكرر",
            "role": "platform_admin",
            "permissions": []
        }
        
        response = requests.post(
            f"{BASE_URL}/api/users/create",
            json=user_data,
            headers=self.headers
        )
        
        assert response.status_code == 400, f"Should fail with duplicate email: {response.text}"
        print("✓ Duplicate email correctly rejected")
    
    def test_create_user_invalid_role_fails(self):
        """Test that creating a user with invalid role fails"""
        timestamp = str(int(time.time()))
        user_data = {
            "email": f"test_invalid_{timestamp}@nassaq.com",
            "password": "TestPass123!@#",
            "full_name": "مستخدم غير صالح",
            "role": "invalid_role",
            "permissions": []
        }
        
        response = requests.post(
            f"{BASE_URL}/api/users/create",
            json=user_data,
            headers=self.headers
        )
        
        assert response.status_code == 400, f"Should fail with invalid role: {response.text}"
        print("✓ Invalid role correctly rejected")
    
    def test_get_platform_users(self):
        """Test getting list of platform users"""
        response = requests.get(
            f"{BASE_URL}/api/users/platform-users",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Failed to get users: {response.text}"
        data = response.json()
        assert "users" in data
        assert "total" in data
        print(f"✓ Retrieved {data['total']} platform users")


class TestTenantsManagementAPI:
    """Test schools/tenants management endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - login and get token"""
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": "info@nassaqapp.com",
                "password": "NassaqAdmin2026!##$$HBJ"
            }
        )
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json()["access_token"]
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def test_get_schools_list(self):
        """Test getting list of schools"""
        response = requests.get(
            f"{BASE_URL}/api/schools",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Failed to get schools: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Retrieved {len(data)} schools")
    
    def test_get_dashboard_stats(self):
        """Test getting dashboard statistics"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Failed to get stats: {response.text}"
        data = response.json()
        assert "total_schools" in data
        assert "total_students" in data
        assert "total_teachers" in data
        print(f"✓ Dashboard stats: {data['total_schools']} schools, {data['total_students']} students, {data['total_teachers']} teachers")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
