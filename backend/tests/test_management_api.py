"""
NASSAQ Platform Management API Tests
Tests for Teachers, Students, Classes, and Subjects CRUD endpoints
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://school-timetable-ai.preview.emergentagent.com').rstrip('/')

# Test credentials
ADMIN_EMAIL = "info@nassaqapp.com"
ADMIN_PASSWORD = "NassaqAdmin2026!##$$HBJ"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def test_school(admin_token):
    """Create a test school for use in other tests"""
    unique_code = f"TEST{uuid.uuid4().hex[:6].upper()}"
    response = requests.post(
        f"{BASE_URL}/api/schools",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": f"مدرسة الاختبار {unique_code}",
            "name_en": f"Test School {unique_code}",
            "code": unique_code,
            "email": f"test{unique_code.lower()}@school.com",
            "city": "Riyadh",
            "student_capacity": 500
        }
    )
    assert response.status_code == 200, f"School creation failed: {response.text}"
    return response.json()


class TestTeachersAPI:
    """Teachers CRUD endpoint tests"""
    
    def test_get_teachers_list(self, admin_token):
        """Test getting teachers list"""
        response = requests.get(
            f"{BASE_URL}/api/teachers",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Retrieved {len(data)} teachers")
    
    def test_create_teacher(self, admin_token, test_school):
        """Test creating a new teacher"""
        unique_email = f"teacher_{uuid.uuid4().hex[:8]}@test.com"
        response = requests.post(
            f"{BASE_URL}/api/teachers",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "full_name": "معلم اختبار",
                "full_name_en": "Test Teacher",
                "email": unique_email,
                "phone": "+966501234567",
                "school_id": test_school["id"],
                "specialization": "رياضيات",
                "years_of_experience": 5,
                "qualification": "بكالوريوس",
                "gender": "male"
            }
        )
        assert response.status_code == 200, f"Teacher creation failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "id" in data
        assert data["full_name"] == "معلم اختبار"
        assert data["email"] == unique_email
        assert data["specialization"] == "رياضيات"
        assert data["is_active"] == True
        print(f"✓ Teacher created: {data['full_name']} ({data['id']})")
        return data
    
    def test_create_teacher_duplicate_email(self, admin_token, test_school):
        """Test creating teacher with duplicate email fails"""
        unique_email = f"teacher_dup_{uuid.uuid4().hex[:8]}@test.com"
        
        # Create first teacher
        requests.post(
            f"{BASE_URL}/api/teachers",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "full_name": "معلم أول",
                "email": unique_email,
                "school_id": test_school["id"],
                "specialization": "علوم"
            }
        )
        
        # Try to create second teacher with same email
        response = requests.post(
            f"{BASE_URL}/api/teachers",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "full_name": "معلم ثاني",
                "email": unique_email,
                "school_id": test_school["id"],
                "specialization": "فيزياء"
            }
        )
        assert response.status_code == 400
        print("✓ Duplicate email correctly rejected")
    
    def test_get_teacher_by_id(self, admin_token, test_school):
        """Test getting a specific teacher by ID"""
        # First create a teacher
        unique_email = f"teacher_get_{uuid.uuid4().hex[:8]}@test.com"
        create_response = requests.post(
            f"{BASE_URL}/api/teachers",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "full_name": "معلم للاسترجاع",
                "email": unique_email,
                "school_id": test_school["id"],
                "specialization": "لغة عربية"
            }
        )
        teacher_id = create_response.json()["id"]
        
        # Get teacher by ID
        response = requests.get(
            f"{BASE_URL}/api/teachers/{teacher_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == teacher_id
        assert data["full_name"] == "معلم للاسترجاع"
        print(f"✓ Teacher retrieved by ID: {data['full_name']}")
    
    def test_delete_teacher(self, admin_token, test_school):
        """Test deleting (soft delete) a teacher"""
        # First create a teacher
        unique_email = f"teacher_del_{uuid.uuid4().hex[:8]}@test.com"
        create_response = requests.post(
            f"{BASE_URL}/api/teachers",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "full_name": "معلم للحذف",
                "email": unique_email,
                "school_id": test_school["id"],
                "specialization": "تاريخ"
            }
        )
        teacher_id = create_response.json()["id"]
        
        # Delete teacher
        response = requests.delete(
            f"{BASE_URL}/api/teachers/{teacher_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        print(f"✓ Teacher deleted: {teacher_id}")


class TestStudentsAPI:
    """Students CRUD endpoint tests"""
    
    def test_get_students_list(self, admin_token):
        """Test getting students list"""
        response = requests.get(
            f"{BASE_URL}/api/students",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Retrieved {len(data)} students")
    
    def test_create_student(self, admin_token, test_school):
        """Test creating a new student"""
        student_number = f"STU{uuid.uuid4().hex[:8].upper()}"
        response = requests.post(
            f"{BASE_URL}/api/students",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "full_name": "طالب اختبار",
                "full_name_en": "Test Student",
                "school_id": test_school["id"],
                "student_number": student_number,
                "date_of_birth": "2010-05-15",
                "gender": "male",
                "parent_name": "ولي أمر الطالب",
                "parent_phone": "+966509876543"
            }
        )
        assert response.status_code == 200, f"Student creation failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "id" in data
        assert data["full_name"] == "طالب اختبار"
        assert data["student_number"] == student_number
        assert data["is_active"] == True
        print(f"✓ Student created: {data['full_name']} ({data['student_number']})")
        return data
    
    def test_get_student_by_id(self, admin_token, test_school):
        """Test getting a specific student by ID"""
        # First create a student
        student_number = f"STU{uuid.uuid4().hex[:8].upper()}"
        create_response = requests.post(
            f"{BASE_URL}/api/students",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "full_name": "طالب للاسترجاع",
                "school_id": test_school["id"],
                "student_number": student_number,
                "gender": "female"
            }
        )
        student_id = create_response.json()["id"]
        
        # Get student by ID
        response = requests.get(
            f"{BASE_URL}/api/students/{student_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == student_id
        assert data["full_name"] == "طالب للاسترجاع"
        print(f"✓ Student retrieved by ID: {data['full_name']}")
    
    def test_delete_student(self, admin_token, test_school):
        """Test deleting (soft delete) a student"""
        # First create a student
        student_number = f"STU{uuid.uuid4().hex[:8].upper()}"
        create_response = requests.post(
            f"{BASE_URL}/api/students",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "full_name": "طالب للحذف",
                "school_id": test_school["id"],
                "student_number": student_number
            }
        )
        student_id = create_response.json()["id"]
        
        # Delete student
        response = requests.delete(
            f"{BASE_URL}/api/students/{student_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        print(f"✓ Student deleted: {student_id}")


class TestClassesAPI:
    """Classes CRUD endpoint tests"""
    
    def test_get_classes_list(self, admin_token):
        """Test getting classes list"""
        response = requests.get(
            f"{BASE_URL}/api/classes",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Retrieved {len(data)} classes")
    
    def test_create_class(self, admin_token, test_school):
        """Test creating a new class"""
        response = requests.post(
            f"{BASE_URL}/api/classes",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "الأول الابتدائي - أ",
                "name_en": "Grade 1 - A",
                "school_id": test_school["id"],
                "grade_level": "الأول الابتدائي",
                "section": "أ",
                "capacity": 30
            }
        )
        assert response.status_code == 200, f"Class creation failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "id" in data
        assert data["name"] == "الأول الابتدائي - أ"
        assert data["grade_level"] == "الأول الابتدائي"
        assert data["section"] == "أ"
        assert data["capacity"] == 30
        assert data["current_students"] == 0
        assert data["is_active"] == True
        print(f"✓ Class created: {data['name']} ({data['id']})")
        return data
    
    def test_get_class_by_id(self, admin_token, test_school):
        """Test getting a specific class by ID"""
        # First create a class
        create_response = requests.post(
            f"{BASE_URL}/api/classes",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "الثاني الابتدائي - ب",
                "school_id": test_school["id"],
                "grade_level": "الثاني الابتدائي",
                "section": "ب",
                "capacity": 25
            }
        )
        class_id = create_response.json()["id"]
        
        # Get class by ID
        response = requests.get(
            f"{BASE_URL}/api/classes/{class_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == class_id
        assert data["name"] == "الثاني الابتدائي - ب"
        print(f"✓ Class retrieved by ID: {data['name']}")
    
    def test_delete_class(self, admin_token, test_school):
        """Test deleting (soft delete) a class"""
        # First create a class
        create_response = requests.post(
            f"{BASE_URL}/api/classes",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "فصل للحذف",
                "school_id": test_school["id"],
                "grade_level": "الثالث الابتدائي",
                "section": "ج"
            }
        )
        class_id = create_response.json()["id"]
        
        # Delete class
        response = requests.delete(
            f"{BASE_URL}/api/classes/{class_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        print(f"✓ Class deleted: {class_id}")


class TestSubjectsAPI:
    """Subjects CRUD endpoint tests"""
    
    def test_get_subjects_list(self, admin_token):
        """Test getting subjects list"""
        response = requests.get(
            f"{BASE_URL}/api/subjects",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Retrieved {len(data)} subjects")
    
    def test_create_subject(self, admin_token, test_school):
        """Test creating a new subject"""
        subject_code = f"SUBJ{uuid.uuid4().hex[:4].upper()}"
        response = requests.post(
            f"{BASE_URL}/api/subjects",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "الرياضيات",
                "name_en": "Mathematics",
                "school_id": test_school["id"],
                "code": subject_code,
                "description": "مادة الرياضيات للمرحلة الابتدائية",
                "weekly_hours": 5,
                "grade_levels": ["الأول الابتدائي", "الثاني الابتدائي"]
            }
        )
        assert response.status_code == 200, f"Subject creation failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "id" in data
        assert data["name"] == "الرياضيات"
        assert data["code"] == subject_code
        assert data["weekly_hours"] == 5
        assert data["is_active"] == True
        print(f"✓ Subject created: {data['name']} ({data['code']})")
        return data
    
    def test_get_subject_by_id(self, admin_token, test_school):
        """Test getting a specific subject by ID"""
        # First create a subject
        subject_code = f"SUBJ{uuid.uuid4().hex[:4].upper()}"
        create_response = requests.post(
            f"{BASE_URL}/api/subjects",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "العلوم",
                "school_id": test_school["id"],
                "code": subject_code,
                "weekly_hours": 4
            }
        )
        subject_id = create_response.json()["id"]
        
        # Get subject by ID
        response = requests.get(
            f"{BASE_URL}/api/subjects/{subject_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == subject_id
        assert data["name"] == "العلوم"
        print(f"✓ Subject retrieved by ID: {data['name']}")
    
    def test_update_subject(self, admin_token, test_school):
        """Test updating a subject"""
        # First create a subject
        subject_code = f"SUBJ{uuid.uuid4().hex[:4].upper()}"
        create_response = requests.post(
            f"{BASE_URL}/api/subjects",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "مادة للتحديث",
                "school_id": test_school["id"],
                "code": subject_code,
                "weekly_hours": 3
            }
        )
        subject_id = create_response.json()["id"]
        
        # Update subject
        response = requests.put(
            f"{BASE_URL}/api/subjects/{subject_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "مادة محدثة",
                "name_en": "Updated Subject",
                "school_id": test_school["id"],
                "code": subject_code,
                "description": "وصف محدث",
                "weekly_hours": 6,
                "grade_levels": ["الأول الابتدائي"]
            }
        )
        assert response.status_code == 200
        print(f"✓ Subject updated: {subject_id}")
        
        # Verify update
        get_response = requests.get(
            f"{BASE_URL}/api/subjects/{subject_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        data = get_response.json()
        assert data["name"] == "مادة محدثة"
        assert data["weekly_hours"] == 6
        print(f"✓ Subject update verified: {data['name']}")
    
    def test_delete_subject(self, admin_token, test_school):
        """Test deleting (soft delete) a subject"""
        # First create a subject
        subject_code = f"SUBJ{uuid.uuid4().hex[:4].upper()}"
        create_response = requests.post(
            f"{BASE_URL}/api/subjects",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "مادة للحذف",
                "school_id": test_school["id"],
                "code": subject_code
            }
        )
        subject_id = create_response.json()["id"]
        
        # Delete subject
        response = requests.delete(
            f"{BASE_URL}/api/subjects/{subject_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        print(f"✓ Subject deleted: {subject_id}")


class TestUnauthorizedAccess:
    """Test unauthorized access to management endpoints"""
    
    def test_teachers_unauthorized(self):
        """Test teachers endpoint without auth"""
        response = requests.get(f"{BASE_URL}/api/teachers")
        assert response.status_code in [401, 403]
        print("✓ Teachers endpoint correctly requires auth")
    
    def test_students_unauthorized(self):
        """Test students endpoint without auth"""
        response = requests.get(f"{BASE_URL}/api/students")
        assert response.status_code in [401, 403]
        print("✓ Students endpoint correctly requires auth")
    
    def test_classes_unauthorized(self):
        """Test classes endpoint without auth"""
        response = requests.get(f"{BASE_URL}/api/classes")
        assert response.status_code in [401, 403]
        print("✓ Classes endpoint correctly requires auth")
    
    def test_subjects_unauthorized(self):
        """Test subjects endpoint without auth"""
        response = requests.get(f"{BASE_URL}/api/subjects")
        assert response.status_code in [401, 403]
        print("✓ Subjects endpoint correctly requires auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
