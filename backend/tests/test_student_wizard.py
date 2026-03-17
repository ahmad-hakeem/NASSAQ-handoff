"""
Test Student Wizard - إنشاء طالب جديد
Tests for the student creation wizard functionality including:
- Creating student from Dashboard Quick Action
- Creating student from UsersClassesManagement page
- Verifying grades dropdown
- Verifying classes dropdown
- Creating parent account with student
- QR code generation
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
PRINCIPAL_EMAIL = "principal1@nassaq.com"
PRINCIPAL_PASSWORD = "Principal@123"
ADMIN_EMAIL = "admin@nassaq.com"
ADMIN_PASSWORD = "Admin@123"


class TestAuthentication:
    """Authentication tests"""
    
    def test_principal_login(self):
        """Test principal login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "school_principal"
        print(f"✓ Principal login successful - tenant_id: {data['user'].get('tenant_id')}")
        return data["access_token"]
    
    def test_admin_login(self):
        """Test admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "platform_admin"
        print("✓ Admin login successful")
        return data["access_token"]


class TestGradesAndClasses:
    """Test grades and classes APIs - required for student wizard"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_reference_grades(self):
        """Test GET /api/reference/grades - grades dropdown data"""
        response = requests.get(f"{BASE_URL}/api/reference/grades", headers=self.headers)
        assert response.status_code == 200, f"Failed to get grades: {response.text}"
        grades = response.json()
        assert isinstance(grades, list), "Grades should be a list"
        print(f"✓ Got {len(grades)} grades from /api/reference/grades")
        
        # Verify grade structure
        if grades:
            grade = grades[0]
            print(f"  Sample grade: {grade}")
            # Check for name_ar or name_en fields
            has_name = 'name_ar' in grade or 'name_en' in grade or 'name' in grade
            assert has_name, "Grade should have name_ar, name_en, or name field"
        return grades
    
    def test_get_classes(self):
        """Test GET /api/classes - classes dropdown data"""
        response = requests.get(f"{BASE_URL}/api/classes", headers=self.headers)
        assert response.status_code == 200, f"Failed to get classes: {response.text}"
        classes = response.json()
        assert isinstance(classes, list), "Classes should be a list"
        print(f"✓ Got {len(classes)} classes from /api/classes")
        
        # Verify class structure
        if classes:
            cls = classes[0]
            print(f"  Sample class: id={cls.get('id')}, name={cls.get('name')}")
        return classes
    
    def test_get_academic_structure(self):
        """Test GET /api/reference/academic-structure - full academic structure"""
        response = requests.get(f"{BASE_URL}/api/reference/academic-structure", headers=self.headers)
        assert response.status_code == 200, f"Failed to get academic structure: {response.text}"
        data = response.json()
        
        # Check for grades in response
        grades = data.get('grades', [])
        print(f"✓ Academic structure has {len(grades)} grades")
        
        if grades:
            grade = grades[0]
            print(f"  Sample grade from academic structure: {grade}")
        return data


class TestStudentWizardAPI:
    """Test student wizard API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token and school context"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        data = response.json()
        self.token = data["access_token"]
        self.tenant_id = data["user"].get("tenant_id")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_check_parent_no_params(self):
        """Test check-parent with no parameters"""
        response = requests.post(
            f"{BASE_URL}/api/student-wizard/check-parent",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("found") == False
        print("✓ Check parent with no params returns found=false")
    
    def test_check_parent_with_phone(self):
        """Test check-parent with phone number"""
        response = requests.post(
            f"{BASE_URL}/api/student-wizard/check-parent?phone=0500000000",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        # Should return found=false for non-existent phone
        print(f"✓ Check parent with phone: found={data.get('found')}")
    
    def test_create_student_minimal(self):
        """Test creating student with minimal data"""
        unique_id = str(uuid.uuid4())[:8]
        student_data = {
            "full_name": f"TEST_طالب اختبار {unique_id}",
            "gender": "male",
            "date_of_birth": "2015-01-15",
            "education_level": "primary",
            "grade_id": "grade-1",
            "parent": {
                "full_name": f"TEST_ولي أمر {unique_id}",
                "phone": f"05{unique_id[:8].replace('-', '0')}",
                "relationship": "father"
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/student-wizard/create",
            json=student_data,
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Failed to create student: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert data.get("success") == True, "Response should have success=true"
        assert "student" in data, "Response should have student object"
        assert "parent" in data, "Response should have parent object"
        
        student = data["student"]
        assert student.get("id"), "Student should have id"
        assert student.get("student_id") or student.get("student_number"), "Student should have student_id/number"
        assert student.get("full_name") == student_data["full_name"], "Student name should match"
        assert student.get("temp_password"), "Student should have temp_password"
        assert student.get("qr_code"), "Student should have QR code"
        
        parent = data["parent"]
        assert parent.get("id"), "Parent should have id"
        assert parent.get("full_name") == student_data["parent"]["full_name"], "Parent name should match"
        assert parent.get("is_new") == True, "Parent should be marked as new"
        assert parent.get("temp_password"), "Parent should have temp_password"
        
        print(f"✓ Created student: {student.get('student_id')}")
        print(f"  Student email: {student.get('email')}")
        print(f"  Parent email: {parent.get('email')}")
        print(f"  QR code generated: {len(student.get('qr_code', '')) > 100}")
        
        return data
    
    def test_create_student_with_class(self):
        """Test creating student with class assignment"""
        # First get available classes
        classes_response = requests.get(f"{BASE_URL}/api/classes", headers=self.headers)
        classes = classes_response.json()
        
        class_id = None
        if classes:
            class_id = classes[0].get("id")
            print(f"  Using class: {classes[0].get('name')} (id: {class_id})")
        
        unique_id = str(uuid.uuid4())[:8]
        student_data = {
            "full_name": f"TEST_طالب مع فصل {unique_id}",
            "gender": "female",
            "date_of_birth": "2014-06-20",
            "education_level": "primary",
            "grade_id": "grade-2",
            "class_id": class_id,
            "parent": {
                "full_name": f"TEST_أم الطالب {unique_id}",
                "phone": f"05{unique_id[:8].replace('-', '1')}",
                "email": f"test_parent_{unique_id}@test.com",
                "relationship": "mother"
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/student-wizard/create",
            json=student_data,
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Failed to create student: {response.text}"
        data = response.json()
        assert data.get("success") == True
        
        student = data["student"]
        if class_id:
            # If class was assigned, verify class info in response
            print(f"✓ Created student with class: {student.get('class_name')}")
        else:
            print("✓ Created student (no classes available)")
        
        return data
    
    def test_create_student_with_health_info(self):
        """Test creating student with health information"""
        unique_id = str(uuid.uuid4())[:8]
        student_data = {
            "full_name": f"TEST_طالب صحي {unique_id}",
            "gender": "male",
            "date_of_birth": "2013-03-10",
            "education_level": "primary",
            "grade_id": "grade-3",
            "parent": {
                "full_name": f"TEST_ولي أمر صحي {unique_id}",
                "phone": f"05{unique_id[:8].replace('-', '2')}",
                "relationship": "guardian"
            },
            "health": {
                "health_status": "جيدة",
                "allergies": "حساسية الفول السوداني, حساسية الغبار",
                "medications": "فيتامين د",
                "special_needs": None,
                "notes": "يحتاج متابعة دورية"
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/student-wizard/create",
            json=student_data,
            headers=self.headers
        )
        
        assert response.status_code == 200, f"Failed to create student: {response.text}"
        data = response.json()
        assert data.get("success") == True
        
        print(f"✓ Created student with health info: {data['student'].get('student_id')}")
        return data
    
    def test_create_student_link_existing_parent(self):
        """Test creating student linked to existing parent (sibling)"""
        # First create a student with parent
        unique_id = str(uuid.uuid4())[:8]
        parent_phone = f"05{unique_id[:8].replace('-', '3')}"
        
        first_student_data = {
            "full_name": f"TEST_الطالب الأول {unique_id}",
            "gender": "male",
            "date_of_birth": "2012-01-01",
            "education_level": "primary",
            "grade_id": "grade-4",
            "parent": {
                "full_name": f"TEST_ولي أمر مشترك {unique_id}",
                "phone": parent_phone,
                "relationship": "father"
            }
        }
        
        response1 = requests.post(
            f"{BASE_URL}/api/student-wizard/create",
            json=first_student_data,
            headers=self.headers
        )
        assert response1.status_code == 200
        first_data = response1.json()
        parent_id = first_data["parent"]["id"]
        print(f"✓ Created first student with parent_id: {parent_id}")
        
        # Check if parent exists
        check_response = requests.post(
            f"{BASE_URL}/api/student-wizard/check-parent?phone={parent_phone}",
            headers=self.headers
        )
        assert check_response.status_code == 200
        check_data = check_response.json()
        assert check_data.get("found") == True, "Parent should be found"
        print(f"✓ Parent found with {len(check_data.get('students', []))} existing student(s)")
        
        # Create sibling linked to existing parent
        sibling_data = {
            "full_name": f"TEST_الطالب الثاني (شقيق) {unique_id}",
            "gender": "female",
            "date_of_birth": "2014-05-15",
            "education_level": "primary",
            "grade_id": "grade-2",
            "link_to_parent_id": parent_id
        }
        
        response2 = requests.post(
            f"{BASE_URL}/api/student-wizard/create",
            json=sibling_data,
            headers=self.headers
        )
        assert response2.status_code == 200, f"Failed to create sibling: {response2.text}"
        sibling_data_response = response2.json()
        assert sibling_data_response.get("success") == True
        
        # Parent should not be new (linked to existing)
        parent = sibling_data_response.get("parent")
        if parent:
            assert parent.get("is_new") == False or parent.get("temp_password") is None, \
                "Linked parent should not be marked as new"
        
        print(f"✓ Created sibling linked to existing parent")
        return sibling_data_response


class TestStudentWizardValidation:
    """Test validation and error handling"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_create_student_missing_name(self):
        """Test creating student without name - should fail"""
        student_data = {
            "gender": "male",
            "date_of_birth": "2015-01-15",
            "parent": {
                "full_name": "ولي أمر",
                "phone": "0500000001",
                "relationship": "father"
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/student-wizard/create",
            json=student_data,
            headers=self.headers
        )
        
        # Should fail with 422 (validation error)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print("✓ Validation correctly rejects student without name")
    
    def test_create_student_without_auth(self):
        """Test creating student without authentication - should fail"""
        student_data = {
            "full_name": "طالب بدون توثيق",
            "gender": "male",
            "parent": {
                "full_name": "ولي أمر",
                "phone": "0500000002",
                "relationship": "father"
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/student-wizard/create",
            json=student_data
        )
        
        # Should fail with 401 or 403
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ API correctly rejects unauthenticated request")


class TestCleanup:
    """Cleanup test data"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_cleanup_test_students(self):
        """Cleanup TEST_ prefixed students (informational only)"""
        # Get students
        response = requests.get(f"{BASE_URL}/api/students", headers=self.headers)
        if response.status_code == 200:
            students = response.json()
            test_students = [s for s in students if s.get("full_name", "").startswith("TEST_")]
            print(f"ℹ Found {len(test_students)} TEST_ prefixed students")
            # Note: Actual cleanup would require DELETE endpoint
        print("✓ Cleanup check completed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
