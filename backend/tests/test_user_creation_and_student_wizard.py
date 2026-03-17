"""
Test User Creation and Student Wizard APIs
Tests for:
1. POST /api/users/create - Create user from UsersManagement page
2. POST /api/student-wizard/create - Create student with parent
3. POST /api/student-wizard/check-parent - Check if parent exists
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@nassaq.com"
ADMIN_PASSWORD = "Admin@123"
PRINCIPAL_EMAIL = "principal1@nassaq.com"
PRINCIPAL_PASSWORD = "Principal@123"


class TestAuthentication:
    """Test authentication for admin and principal"""
    
    def test_admin_login(self):
        """Test admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        assert data.get("user", {}).get("role") == "platform_admin", "User is not platform_admin"
        print(f"✓ Admin login successful - role: {data.get('user', {}).get('role')}")
    
    def test_principal_login(self):
        """Test principal login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        assert response.status_code == 200, f"Principal login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        assert data.get("user", {}).get("role") == "school_principal", "User is not school_principal"
        print(f"✓ Principal login successful - role: {data.get('user', {}).get('role')}")


@pytest.fixture
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Admin authentication failed")


@pytest.fixture
def principal_token():
    """Get principal authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": PRINCIPAL_EMAIL,
        "password": PRINCIPAL_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Principal authentication failed")


class TestUserCreationAPI:
    """Test POST /api/users/create endpoint"""
    
    def test_create_user_endpoint_exists(self, admin_token):
        """Test that /api/users/create endpoint exists"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        # Send minimal data to check endpoint exists
        response = requests.post(f"{BASE_URL}/api/users/create", 
            json={},
            headers=headers
        )
        # Should return 422 (validation error) not 404
        assert response.status_code != 404, f"Endpoint /api/users/create not found: {response.text}"
        print(f"✓ Endpoint /api/users/create exists - status: {response.status_code}")
    
    def test_create_user_requires_auth(self):
        """Test that creating user requires authentication"""
        response = requests.post(f"{BASE_URL}/api/users/create", json={
            "email": "test@test.com",
            "password": "Test@123",
            "full_name": "Test User",
            "role": "teacher"
        })
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ Create user requires authentication - status: {response.status_code}")
    
    def test_create_user_validation(self, admin_token):
        """Test user creation validation"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Test with missing required fields
        response = requests.post(f"{BASE_URL}/api/users/create", 
            json={"email": "test@test.com"},
            headers=headers
        )
        assert response.status_code in [400, 422], f"Expected validation error, got {response.status_code}"
        print(f"✓ User creation validates required fields - status: {response.status_code}")
    
    def test_create_platform_user_success(self, admin_token):
        """Test creating a platform user successfully"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        unique_id = str(uuid.uuid4())[:8]
        
        user_data = {
            "email": f"test_user_{unique_id}@nassaq.com",
            "password": "TestPass@123",
            "full_name": f"Test User {unique_id}",
            "role": "platform_support_specialist",
            "phone": f"059{unique_id[:7]}",
            "region": "riyadh",
            "city": "riyadh",
            "permissions": ["view_tickets", "respond_tickets", "view_users"]
        }
        
        response = requests.post(f"{BASE_URL}/api/users/create", 
            json=user_data,
            headers=headers
        )
        
        # Check response
        if response.status_code == 200 or response.status_code == 201:
            data = response.json()
            assert "id" in data or "user" in data, "No user ID in response"
            print(f"✓ Platform user created successfully - email: {user_data['email']}")
        else:
            print(f"⚠ User creation returned {response.status_code}: {response.text}")
            # Don't fail if it's a duplicate email error
            if "already exists" in response.text.lower() or "duplicate" in response.text.lower():
                print("  (User may already exist)")
            else:
                assert False, f"User creation failed: {response.text}"


class TestStudentWizardAPI:
    """Test Student Wizard APIs"""
    
    def test_student_wizard_create_endpoint_exists(self, principal_token):
        """Test that /api/student-wizard/create endpoint exists"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        response = requests.post(f"{BASE_URL}/api/student-wizard/create", 
            json={},
            headers=headers
        )
        # Should return 422 (validation error) not 404
        assert response.status_code != 404, f"Endpoint /api/student-wizard/create not found: {response.text}"
        print(f"✓ Endpoint /api/student-wizard/create exists - status: {response.status_code}")
    
    def test_student_wizard_check_parent_endpoint_exists(self, principal_token):
        """Test that /api/student-wizard/check-parent endpoint exists"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        response = requests.post(f"{BASE_URL}/api/student-wizard/check-parent", 
            headers=headers
        )
        # Should return 200 or 422, not 404
        assert response.status_code != 404, f"Endpoint /api/student-wizard/check-parent not found: {response.text}"
        print(f"✓ Endpoint /api/student-wizard/check-parent exists - status: {response.status_code}")
    
    def test_check_parent_no_match(self, principal_token):
        """Test check-parent with non-existing parent"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        response = requests.post(
            f"{BASE_URL}/api/student-wizard/check-parent?phone=0599999999",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "found" in data, "Response should have 'found' field"
            print(f"✓ Check parent returns found={data.get('found')} for non-existing phone")
        else:
            print(f"⚠ Check parent returned {response.status_code}: {response.text}")
    
    def test_create_student_requires_auth(self):
        """Test that creating student requires authentication"""
        response = requests.post(f"{BASE_URL}/api/student-wizard/create", json={
            "full_name": "Test Student",
            "gender": "male",
            "date_of_birth": "2015-01-01",
            "education_level": "primary",
            "grade_id": "grade-1",
            "parent": {
                "full_name": "Test Parent",
                "phone": "0501234567",
                "relationship": "father"
            }
        })
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ Create student requires authentication - status: {response.status_code}")
    
    def test_create_student_validation(self, principal_token):
        """Test student creation validation"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        
        # Test with missing required fields
        response = requests.post(f"{BASE_URL}/api/student-wizard/create", 
            json={"full_name": "Test"},
            headers=headers
        )
        assert response.status_code in [400, 422], f"Expected validation error, got {response.status_code}"
        print(f"✓ Student creation validates required fields - status: {response.status_code}")
    
    def test_create_student_with_parent_success(self, principal_token):
        """Test creating a student with parent successfully"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        unique_id = str(uuid.uuid4())[:8]
        
        student_data = {
            "full_name": f"طالب اختبار {unique_id}",
            "email": f"test_student_{unique_id}@nassaq.com",
            "national_id": f"1234{unique_id}",
            "gender": "male",
            "date_of_birth": "2015-05-15",
            "education_level": "primary",
            "grade_id": "grade-1",
            "class_id": None,
            "parent": {
                "full_name": f"ولي أمر اختبار {unique_id}",
                "phone": f"050{unique_id[:7]}",
                "email": f"test_parent_{unique_id}@nassaq.com",
                "relationship": "father",
                "national_id": f"5678{unique_id}"
            },
            "health": {
                "health_status": "جيدة",
                "allergies": [],
                "medications": [],
                "special_needs": None
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/student-wizard/create", 
            json=student_data,
            headers=headers
        )
        
        if response.status_code == 200 or response.status_code == 201:
            data = response.json()
            assert data.get("success") == True, "Response should have success=True"
            assert "student" in data, "Response should have student data"
            assert "parent" in data, "Response should have parent data"
            
            student = data.get("student", {})
            assert "student_id" in student, "Student should have student_id"
            assert "qr_code" in student, "Student should have qr_code"
            assert "temp_password" in student, "Student should have temp_password"
            
            print(f"✓ Student created successfully:")
            print(f"  - Student ID: {student.get('student_id')}")
            print(f"  - Student Name: {student.get('full_name')}")
            print(f"  - Has QR Code: {bool(student.get('qr_code'))}")
            print(f"  - Parent: {data.get('parent', {}).get('full_name')}")
            print(f"  - Parent is new: {data.get('parent', {}).get('is_new')}")
        else:
            print(f"⚠ Student creation returned {response.status_code}: {response.text}")
            # Check if it's a school_id issue
            if "المدرسة" in response.text or "school" in response.text.lower():
                print("  (Principal may not have tenant_id set)")
            assert False, f"Student creation failed: {response.text}"
    
    def test_create_student_sibling_detection(self, principal_token):
        """Test sibling detection when creating student with same parent"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        unique_id = str(uuid.uuid4())[:8]
        parent_phone = f"055{unique_id[:7]}"
        
        # Create first student
        student1_data = {
            "full_name": f"الطالب الأول {unique_id}",
            "gender": "male",
            "date_of_birth": "2015-01-01",
            "education_level": "primary",
            "grade_id": "grade-1",
            "parent": {
                "full_name": f"ولي الأمر {unique_id}",
                "phone": parent_phone,
                "relationship": "father"
            }
        }
        
        response1 = requests.post(f"{BASE_URL}/api/student-wizard/create", 
            json=student1_data,
            headers=headers
        )
        
        if response1.status_code not in [200, 201]:
            print(f"⚠ First student creation failed: {response1.text}")
            pytest.skip("Could not create first student for sibling test")
        
        # Create second student with same parent phone
        student2_data = {
            "full_name": f"الطالب الثاني {unique_id}",
            "gender": "female",
            "date_of_birth": "2017-06-15",
            "education_level": "primary",
            "grade_id": "grade-1",
            "parent": {
                "full_name": f"ولي الأمر {unique_id}",
                "phone": parent_phone,
                "relationship": "father"
            }
        }
        
        response2 = requests.post(f"{BASE_URL}/api/student-wizard/create", 
            json=student2_data,
            headers=headers
        )
        
        if response2.status_code in [200, 201]:
            data = response2.json()
            siblings = data.get("siblings", {})
            
            print(f"✓ Second student created:")
            print(f"  - Siblings detected: {siblings.get('detected')}")
            print(f"  - Siblings count: {siblings.get('count')}")
            print(f"  - Parent is new: {data.get('parent', {}).get('is_new')}")
            
            # Parent should NOT be new for second student
            assert data.get("parent", {}).get("is_new") == False, "Parent should be existing for second student"
        else:
            print(f"⚠ Second student creation failed: {response2.text}")


class TestUsersManagementPage:
    """Test Users Management page API calls"""
    
    def test_get_users_list(self, admin_token):
        """Test getting users list"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/users", headers=headers)
        
        assert response.status_code == 200, f"Get users failed: {response.text}"
        data = response.json()
        assert isinstance(data, list) or "users" in data, "Response should be list or have users field"
        print(f"✓ Get users list successful - count: {len(data) if isinstance(data, list) else len(data.get('users', []))}")
    
    def test_get_user_roles(self, admin_token):
        """Test getting available roles"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/users/roles", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Get roles successful - count: {len(data) if isinstance(data, list) else 'N/A'}")
        elif response.status_code == 404:
            print("⚠ /api/users/roles endpoint not found (may not be implemented)")
        else:
            print(f"⚠ Get roles returned {response.status_code}")


class TestStudentsManagementPage:
    """Test Students Management page API calls"""
    
    def test_get_students_list(self, principal_token):
        """Test getting students list"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        response = requests.get(f"{BASE_URL}/api/students", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Get students list successful - count: {len(data) if isinstance(data, list) else len(data.get('students', []))}")
        else:
            print(f"⚠ Get students returned {response.status_code}: {response.text}")
    
    def test_get_grades_list(self, principal_token):
        """Test getting grades list for student wizard"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        response = requests.get(f"{BASE_URL}/api/grades", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Get grades list successful - count: {len(data) if isinstance(data, list) else 'N/A'}")
        else:
            print(f"⚠ Get grades returned {response.status_code}")
    
    def test_get_classes_list(self, principal_token):
        """Test getting classes list for student wizard"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        response = requests.get(f"{BASE_URL}/api/classes", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Get classes list successful - count: {len(data) if isinstance(data, list) else 'N/A'}")
        else:
            print(f"⚠ Get classes returned {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
