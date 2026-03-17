"""
Test Suite for Users & Classes Management - Iteration 80
Tests for:
1. PUT /api/students/{id} - partial field updates
2. PUT /api/classes/{id} - partial field updates
3. PUT /api/teachers/{id} - partial field updates
4. GET /api/teachers - for School Settings page
5. GET /api/classes - for School Settings page
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
PRINCIPAL_EMAIL = "principal1@nassaq.com"
PRINCIPAL_PASSWORD = "Principal@123"


class TestAuthentication:
    """Test authentication and get token"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for principal"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        return data["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    @pytest.fixture(scope="class")
    def user_info(self, auth_token):
        """Get current user info"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
        assert response.status_code == 200
        return response.json()
    
    def test_login_success(self, auth_token):
        """Test that login works"""
        assert auth_token is not None
        assert len(auth_token) > 0


class TestStudentPartialUpdate:
    """Test PUT /api/students/{id} with partial fields"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    @pytest.fixture(scope="class")
    def tenant_id(self, auth_headers):
        """Get tenant_id from current user"""
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        return response.json().get("tenant_id")
    
    @pytest.fixture(scope="class")
    def test_student(self, auth_headers, tenant_id):
        """Create a test student for update tests"""
        student_data = {
            "full_name": f"TEST_Student_{uuid.uuid4().hex[:8]}",
            "email": f"test_student_{uuid.uuid4().hex[:8]}@test.com",
            "phone": "0501234567",
            "school_id": tenant_id,
            "student_number": f"STU-{uuid.uuid4().hex[:8]}",
            "gender": "male",
            "is_active": True
        }
        response = requests.post(f"{BASE_URL}/api/students", json=student_data, headers=auth_headers)
        if response.status_code == 201 or response.status_code == 200:
            return response.json()
        # If creation fails, try to get existing student
        response = requests.get(f"{BASE_URL}/api/students", headers=auth_headers)
        students = response.json()
        if students and len(students) > 0:
            return students[0]
        pytest.skip("Could not create or find test student")
    
    def test_update_student_full_name_only(self, auth_headers, test_student):
        """Test updating only full_name field"""
        student_id = test_student.get("id")
        new_name = f"Updated_Name_{uuid.uuid4().hex[:6]}"
        
        response = requests.put(
            f"{BASE_URL}/api/students/{student_id}",
            json={"full_name": new_name},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert data.get("success") == True or "message" in data
        
        # Verify the update persisted
        get_response = requests.get(f"{BASE_URL}/api/students/{student_id}", headers=auth_headers)
        assert get_response.status_code == 200
        updated_student = get_response.json()
        assert updated_student.get("full_name") == new_name
    
    def test_update_student_email_only(self, auth_headers, test_student):
        """Test updating only email field"""
        student_id = test_student.get("id")
        new_email = f"updated_{uuid.uuid4().hex[:6]}@test.com"
        
        response = requests.put(
            f"{BASE_URL}/api/students/{student_id}",
            json={"email": new_email},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Update failed: {response.text}"
        
        # Verify the update persisted
        get_response = requests.get(f"{BASE_URL}/api/students/{student_id}", headers=auth_headers)
        assert get_response.status_code == 200
        updated_student = get_response.json()
        assert updated_student.get("email") == new_email
    
    def test_update_student_is_active_only(self, auth_headers, test_student):
        """Test updating only is_active field"""
        student_id = test_student.get("id")
        
        response = requests.put(
            f"{BASE_URL}/api/students/{student_id}",
            json={"is_active": False},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Update failed: {response.text}"
        
        # Verify the update persisted
        get_response = requests.get(f"{BASE_URL}/api/students/{student_id}", headers=auth_headers)
        assert get_response.status_code == 200
        updated_student = get_response.json()
        assert updated_student.get("is_active") == False
        
        # Restore to active
        requests.put(
            f"{BASE_URL}/api/students/{student_id}",
            json={"is_active": True},
            headers=auth_headers
        )
    
    def test_update_student_multiple_partial_fields(self, auth_headers, test_student):
        """Test updating multiple fields at once (but not all)"""
        student_id = test_student.get("id")
        new_name = f"MultiUpdate_{uuid.uuid4().hex[:6]}"
        new_phone = "0509876543"
        
        response = requests.put(
            f"{BASE_URL}/api/students/{student_id}",
            json={"full_name": new_name, "phone": new_phone},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Update failed: {response.text}"
        
        # Verify both fields updated
        get_response = requests.get(f"{BASE_URL}/api/students/{student_id}", headers=auth_headers)
        assert get_response.status_code == 200
        updated_student = get_response.json()
        assert updated_student.get("full_name") == new_name
        assert updated_student.get("phone") == new_phone


class TestTeacherPartialUpdate:
    """Test PUT /api/teachers/{id} with partial fields"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    @pytest.fixture(scope="class")
    def tenant_id(self, auth_headers):
        """Get tenant_id from current user"""
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        return response.json().get("tenant_id")
    
    @pytest.fixture(scope="class")
    def test_teacher(self, auth_headers, tenant_id):
        """Create a test teacher for update tests"""
        teacher_data = {
            "full_name": f"TEST_Teacher_{uuid.uuid4().hex[:8]}",
            "email": f"test_teacher_{uuid.uuid4().hex[:8]}@test.com",
            "phone": "0501234568",
            "school_id": tenant_id,
            "specialization": "رياضيات",
            "years_of_experience": 5
        }
        response = requests.post(f"{BASE_URL}/api/teachers", json=teacher_data, headers=auth_headers)
        if response.status_code == 201 or response.status_code == 200:
            return response.json()
        # If creation fails, try to get existing teacher
        response = requests.get(f"{BASE_URL}/api/teachers", headers=auth_headers)
        teachers = response.json()
        if teachers and len(teachers) > 0:
            return teachers[0]
        pytest.skip("Could not create or find test teacher")
    
    def test_update_teacher_full_name_only(self, auth_headers, test_teacher):
        """Test updating only full_name field"""
        teacher_id = test_teacher.get("id")
        new_name = f"Updated_Teacher_{uuid.uuid4().hex[:6]}"
        
        response = requests.put(
            f"{BASE_URL}/api/teachers/{teacher_id}",
            json={"full_name": new_name},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert data.get("success") == True or "message" in data
        
        # Verify the update persisted
        get_response = requests.get(f"{BASE_URL}/api/teachers/{teacher_id}", headers=auth_headers)
        assert get_response.status_code == 200
        updated_teacher = get_response.json()
        assert updated_teacher.get("full_name") == new_name
    
    def test_update_teacher_specialization_only(self, auth_headers, test_teacher):
        """Test updating only specialization field"""
        teacher_id = test_teacher.get("id")
        new_spec = "علوم"
        
        response = requests.put(
            f"{BASE_URL}/api/teachers/{teacher_id}",
            json={"specialization": new_spec},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Update failed: {response.text}"
        
        # Verify the update persisted
        get_response = requests.get(f"{BASE_URL}/api/teachers/{teacher_id}", headers=auth_headers)
        assert get_response.status_code == 200
        updated_teacher = get_response.json()
        assert updated_teacher.get("specialization") == new_spec
    
    def test_update_teacher_is_active_only(self, auth_headers, test_teacher):
        """Test updating only is_active field"""
        teacher_id = test_teacher.get("id")
        
        response = requests.put(
            f"{BASE_URL}/api/teachers/{teacher_id}",
            json={"is_active": False},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Update failed: {response.text}"
        
        # Verify the update persisted
        get_response = requests.get(f"{BASE_URL}/api/teachers/{teacher_id}", headers=auth_headers)
        assert get_response.status_code == 200
        updated_teacher = get_response.json()
        assert updated_teacher.get("is_active") == False
        
        # Restore to active
        requests.put(
            f"{BASE_URL}/api/teachers/{teacher_id}",
            json={"is_active": True},
            headers=auth_headers
        )
    
    def test_update_teacher_multiple_partial_fields(self, auth_headers, test_teacher):
        """Test updating multiple fields at once (but not all)"""
        teacher_id = test_teacher.get("id")
        new_name = f"MultiUpdate_Teacher_{uuid.uuid4().hex[:6]}"
        new_phone = "0509876544"
        
        response = requests.put(
            f"{BASE_URL}/api/teachers/{teacher_id}",
            json={"full_name": new_name, "phone": new_phone},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Update failed: {response.text}"
        
        # Verify both fields updated
        get_response = requests.get(f"{BASE_URL}/api/teachers/{teacher_id}", headers=auth_headers)
        assert get_response.status_code == 200
        updated_teacher = get_response.json()
        assert updated_teacher.get("full_name") == new_name
        assert updated_teacher.get("phone") == new_phone


class TestClassPartialUpdate:
    """Test PUT /api/classes/{id} with partial fields"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    @pytest.fixture(scope="class")
    def tenant_id(self, auth_headers):
        """Get tenant_id from current user"""
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        return response.json().get("tenant_id")
    
    @pytest.fixture(scope="class")
    def test_class(self, auth_headers, tenant_id):
        """Create a test class for update tests"""
        class_data = {
            "name": f"TEST_Class_{uuid.uuid4().hex[:8]}",
            "school_id": tenant_id,
            "grade_level": "الأول الابتدائي",
            "section": "أ",
            "capacity": 30
        }
        response = requests.post(f"{BASE_URL}/api/classes", json=class_data, headers=auth_headers)
        if response.status_code == 201 or response.status_code == 200:
            return response.json()
        # If creation fails, try to get existing class
        response = requests.get(f"{BASE_URL}/api/classes", headers=auth_headers)
        classes = response.json()
        if classes and len(classes) > 0:
            return classes[0]
        pytest.skip("Could not create or find test class")
    
    def test_update_class_name_only(self, auth_headers, test_class):
        """Test updating only name field"""
        class_id = test_class.get("id")
        new_name = f"Updated_Class_{uuid.uuid4().hex[:6]}"
        
        response = requests.put(
            f"{BASE_URL}/api/classes/{class_id}",
            json={"name": new_name},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert data.get("success") == True or "message" in data
        
        # Verify the update persisted
        get_response = requests.get(f"{BASE_URL}/api/classes/{class_id}", headers=auth_headers)
        assert get_response.status_code == 200
        updated_class = get_response.json()
        assert updated_class.get("name") == new_name
    
    def test_update_class_capacity_only(self, auth_headers, test_class):
        """Test updating only capacity field"""
        class_id = test_class.get("id")
        new_capacity = 35
        
        response = requests.put(
            f"{BASE_URL}/api/classes/{class_id}",
            json={"capacity": new_capacity},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Update failed: {response.text}"
        
        # Verify the update persisted
        get_response = requests.get(f"{BASE_URL}/api/classes/{class_id}", headers=auth_headers)
        assert get_response.status_code == 200
        updated_class = get_response.json()
        assert updated_class.get("capacity") == new_capacity
    
    def test_update_class_section_only(self, auth_headers, test_class):
        """Test updating only section field"""
        class_id = test_class.get("id")
        new_section = "ب"
        
        response = requests.put(
            f"{BASE_URL}/api/classes/{class_id}",
            json={"section": new_section},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Update failed: {response.text}"
        
        # Verify the update persisted
        get_response = requests.get(f"{BASE_URL}/api/classes/{class_id}", headers=auth_headers)
        assert get_response.status_code == 200
        updated_class = get_response.json()
        assert updated_class.get("section") == new_section
    
    def test_update_class_is_active_only(self, auth_headers, test_class):
        """Test updating only is_active field"""
        class_id = test_class.get("id")
        
        response = requests.put(
            f"{BASE_URL}/api/classes/{class_id}",
            json={"is_active": False},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Update failed: {response.text}"
        
        # Verify the update persisted
        get_response = requests.get(f"{BASE_URL}/api/classes/{class_id}", headers=auth_headers)
        assert get_response.status_code == 200
        updated_class = get_response.json()
        assert updated_class.get("is_active") == False
        
        # Restore to active
        requests.put(
            f"{BASE_URL}/api/classes/{class_id}",
            json={"is_active": True},
            headers=auth_headers
        )
    
    def test_update_class_multiple_partial_fields(self, auth_headers, test_class):
        """Test updating multiple fields at once (but not all)"""
        class_id = test_class.get("id")
        new_name = f"MultiUpdate_Class_{uuid.uuid4().hex[:6]}"
        new_capacity = 40
        
        response = requests.put(
            f"{BASE_URL}/api/classes/{class_id}",
            json={"name": new_name, "capacity": new_capacity},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Update failed: {response.text}"
        
        # Verify both fields updated
        get_response = requests.get(f"{BASE_URL}/api/classes/{class_id}", headers=auth_headers)
        assert get_response.status_code == 200
        updated_class = get_response.json()
        assert updated_class.get("name") == new_name
        assert updated_class.get("capacity") == new_capacity


class TestSchoolSettingsPageAPIs:
    """Test APIs used by School Settings page"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def test_get_teachers_returns_list(self, auth_headers):
        """Test GET /api/teachers returns a list"""
        response = requests.get(f"{BASE_URL}/api/teachers", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
    
    def test_get_classes_returns_list(self, auth_headers):
        """Test GET /api/classes returns a list"""
        response = requests.get(f"{BASE_URL}/api/classes", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
    
    def test_get_school_settings(self, auth_headers):
        """Test GET /api/school/settings"""
        response = requests.get(f"{BASE_URL}/api/school/settings", headers=auth_headers)
        # May return 200 or 404 if no settings exist
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
    
    def test_get_teacher_assignments(self, auth_headers):
        """Test GET /api/teacher-assignments"""
        response = requests.get(f"{BASE_URL}/api/teacher-assignments", headers=auth_headers)
        # May return 200 or 404 if no assignments exist
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
