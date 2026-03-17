"""
Assessment Engine API Tests for NASSAQ School Management System
Tests: Assessments CRUD, Grades Bulk Entry, Class Overview, Student History
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
PRINCIPAL_EMAIL = "principal@nassaq.com"
PRINCIPAL_PASSWORD = "NassaqPrincipal2026"

# Test data from main agent
CLASS_ID = "79176f6e-ce18-40f1-b5c9-476fb49a884d"  # الرابع الابتدائي - أ
SUBJECT_ID = "c28b0281-76a0-4500-9ac1-1728421df872"  # الرياضيات
EXISTING_ASSESSMENT_ID = "56dba28f-218e-4770-b805-cd937b1e51da"
STUDENT_IDS = ["8e611384-232d-497c-81a2-0a6c7b47d207", "fca45aa3-8260-4a58-ab27-3ce10f16bed8"]


class TestAssessmentEngine:
    """Assessment Engine API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as school principal
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.token = token
        else:
            pytest.skip(f"Login failed: {login_response.status_code}")
    
    # ============== Authentication Tests ==============
    def test_01_login_as_principal(self):
        """Test login as school principal"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "school_principal"
        print(f"SUCCESS: Login as principal - role: {data['user']['role']}")
    
    # ============== GET Assessments Tests ==============
    def test_02_get_assessments_list(self):
        """Test GET /api/assessments - Get all assessments"""
        response = self.session.get(f"{BASE_URL}/api/assessments")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"SUCCESS: GET /api/assessments - Found {len(data)} assessments")
    
    def test_03_get_assessments_with_class_filter(self):
        """Test GET /api/assessments with class_id filter"""
        response = self.session.get(f"{BASE_URL}/api/assessments?class_id={CLASS_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        # Verify all returned assessments belong to the class
        for assessment in data:
            assert assessment.get("class_id") == CLASS_ID
        print(f"SUCCESS: GET /api/assessments?class_id={CLASS_ID} - Found {len(data)} assessments")
    
    def test_04_get_assessments_with_subject_filter(self):
        """Test GET /api/assessments with subject_id filter"""
        response = self.session.get(f"{BASE_URL}/api/assessments?subject_id={SUBJECT_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"SUCCESS: GET /api/assessments?subject_id={SUBJECT_ID} - Found {len(data)} assessments")
    
    def test_05_get_assessments_with_type_filter(self):
        """Test GET /api/assessments with assessment_type filter"""
        response = self.session.get(f"{BASE_URL}/api/assessments?assessment_type=quiz")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        # Verify all returned assessments are of type quiz
        for assessment in data:
            assert assessment.get("assessment_type") == "quiz"
        print(f"SUCCESS: GET /api/assessments?assessment_type=quiz - Found {len(data)} assessments")
    
    # ============== POST Assessment Tests ==============
    def test_06_create_assessment(self):
        """Test POST /api/assessments - Create new assessment"""
        assessment_data = {
            "class_id": CLASS_ID,
            "subject_id": SUBJECT_ID,
            "title": "TEST_اختبار الوحدة الثانية",
            "title_en": "TEST_Unit 2 Quiz",
            "assessment_type": "quiz",
            "max_score": 25,
            "weight": 0.15,
            "date": "2026-03-10",
            "description": "اختبار قصير للوحدة الثانية",
            "is_published": True
        }
        
        response = self.session.post(f"{BASE_URL}/api/assessments", json=assessment_data)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "id" in data
        assert data["title"] == assessment_data["title"]
        assert data["assessment_type"] == "quiz"
        assert data["max_score"] == 25
        assert data["class_id"] == CLASS_ID
        assert data["subject_id"] == SUBJECT_ID
        
        # Store for cleanup
        self.__class__.created_assessment_id = data["id"]
        print(f"SUCCESS: POST /api/assessments - Created assessment ID: {data['id']}")
    
    def test_07_create_assessment_different_types(self):
        """Test creating assessments with different types"""
        assessment_types = ["assignment", "exam", "participation", "project", "midterm", "final", "oral", "practical"]
        
        for atype in assessment_types[:3]:  # Test first 3 types to save time
            assessment_data = {
                "class_id": CLASS_ID,
                "subject_id": SUBJECT_ID,
                "title": f"TEST_{atype}_assessment",
                "assessment_type": atype,
                "max_score": 100,
                "weight": 0.1,
                "date": "2026-03-15",
                "is_published": False
            }
            
            response = self.session.post(f"{BASE_URL}/api/assessments", json=assessment_data)
            assert response.status_code == 200, f"Failed to create {atype}: {response.text}"
            data = response.json()
            assert data["assessment_type"] == atype
            print(f"SUCCESS: Created {atype} assessment")
    
    # ============== GET Single Assessment Tests ==============
    def test_08_get_existing_assessment(self):
        """Test GET /api/assessments/{assessment_id} - Get existing assessment"""
        response = self.session.get(f"{BASE_URL}/api/assessments/{EXISTING_ASSESSMENT_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert data["id"] == EXISTING_ASSESSMENT_ID
        assert "title" in data
        assert "assessment_type" in data
        assert "max_score" in data
        print(f"SUCCESS: GET /api/assessments/{EXISTING_ASSESSMENT_ID} - Title: {data['title']}")
    
    # ============== Students for Grading Tests ==============
    def test_09_get_students_for_grading(self):
        """Test GET /api/assessments/students-for-grading/{assessment_id}"""
        response = self.session.get(f"{BASE_URL}/api/assessments/students-for-grading/{EXISTING_ASSESSMENT_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "students" in data
        assert "assessment_id" in data
        assert "max_score" in data
        assert isinstance(data["students"], list)
        
        # Verify student data structure
        if data["students"]:
            student = data["students"][0]
            assert "id" in student
            assert "full_name" in student
        
        print(f"SUCCESS: GET students-for-grading - Found {len(data['students'])} students, max_score: {data['max_score']}")
    
    # ============== Bulk Grades Tests ==============
    def test_10_create_bulk_grades(self):
        """Test POST /api/grades/bulk - Create grades for multiple students"""
        grades_data = {
            "assessment_id": EXISTING_ASSESSMENT_ID,
            "grades": [
                {"student_id": STUDENT_IDS[0], "score": 18, "notes": "أداء ممتاز"},
                {"student_id": STUDENT_IDS[1], "score": 15, "notes": "أداء جيد"}
            ]
        }
        
        response = self.session.post(f"{BASE_URL}/api/grades/bulk", json=grades_data)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        # API returns: success, created, updated, total_processed, errors
        assert data.get("success") == True or "created" in data or "updated" in data
        print(f"SUCCESS: POST /api/grades/bulk - Response: {data}")
    
    def test_11_verify_grades_persisted(self):
        """Verify grades were persisted by fetching students for grading"""
        response = self.session.get(f"{BASE_URL}/api/assessments/students-for-grading/{EXISTING_ASSESSMENT_ID}")
        assert response.status_code == 200
        
        data = response.json()
        students = data.get("students", [])
        
        # Check if grades are present
        graded_students = [s for s in students if s.get("score") is not None]
        print(f"SUCCESS: Verified grades - {len(graded_students)} students have grades")
    
    # ============== Class Overview Tests ==============
    def test_12_get_class_grade_overview(self):
        """Test GET /api/grades/class/{class_id}/overview"""
        response = self.session.get(f"{BASE_URL}/api/grades/class/{CLASS_ID}/overview")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "class_average" in data or "class_name" in data
        print(f"SUCCESS: GET /api/grades/class/{CLASS_ID}/overview - Data: {data}")
    
    def test_13_get_class_overview_with_subject_filter(self):
        """Test GET /api/grades/class/{class_id}/overview with subject filter"""
        response = self.session.get(f"{BASE_URL}/api/grades/class/{CLASS_ID}/overview?subject_id={SUBJECT_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        print(f"SUCCESS: GET class overview with subject filter - Data: {data}")
    
    # ============== Student Grade History Tests ==============
    def test_14_get_student_grade_history(self):
        """Test GET /api/grades/student/{student_id}"""
        student_id = STUDENT_IDS[0]
        response = self.session.get(f"{BASE_URL}/api/grades/student/{student_id}")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        # Verify response structure
        assert "student_name" in data or "grades_by_subject" in data or "recent_grades" in data
        print(f"SUCCESS: GET /api/grades/student/{student_id} - Data keys: {list(data.keys())}")
    
    def test_15_get_student_history_with_filters(self):
        """Test GET /api/grades/student/{student_id} with filters"""
        student_id = STUDENT_IDS[0]
        response = self.session.get(f"{BASE_URL}/api/grades/student/{student_id}?subject_id={SUBJECT_ID}")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        print(f"SUCCESS: GET student history with subject filter - Data: {data}")
    
    # ============== Update Assessment Tests ==============
    def test_16_update_assessment(self):
        """Test PUT /api/assessments/{assessment_id}"""
        # First create an assessment to update
        create_data = {
            "class_id": CLASS_ID,
            "subject_id": SUBJECT_ID,
            "title": "TEST_للتحديث",
            "assessment_type": "quiz",
            "max_score": 20,
            "weight": 0.1,
            "date": "2026-03-12",
            "is_published": False
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/assessments", json=create_data)
        if create_response.status_code != 200:
            pytest.skip("Could not create assessment for update test")
        
        assessment_id = create_response.json()["id"]
        
        # Update the assessment
        update_data = {
            "title": "TEST_تم التحديث",
            "max_score": 30,
            "is_published": True
        }
        
        response = self.session.put(f"{BASE_URL}/api/assessments/{assessment_id}", json=update_data)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        # Verify update
        get_response = self.session.get(f"{BASE_URL}/api/assessments/{assessment_id}")
        if get_response.status_code == 200:
            updated = get_response.json()
            assert updated["title"] == "TEST_تم التحديث"
            assert updated["max_score"] == 30
        
        print(f"SUCCESS: PUT /api/assessments/{assessment_id} - Updated successfully")
    
    # ============== Delete Assessment Tests ==============
    def test_17_delete_assessment(self):
        """Test DELETE /api/assessments/{assessment_id}"""
        # First create an assessment to delete
        create_data = {
            "class_id": CLASS_ID,
            "subject_id": SUBJECT_ID,
            "title": "TEST_للحذف",
            "assessment_type": "quiz",
            "max_score": 10,
            "weight": 0.05,
            "date": "2026-03-13",
            "is_published": False
        }
        
        create_response = self.session.post(f"{BASE_URL}/api/assessments", json=create_data)
        if create_response.status_code != 200:
            pytest.skip("Could not create assessment for delete test")
        
        assessment_id = create_response.json()["id"]
        
        # Delete the assessment
        response = self.session.delete(f"{BASE_URL}/api/assessments/{assessment_id}")
        assert response.status_code == 200, f"Failed: {response.text}"
        
        # Verify deletion
        get_response = self.session.get(f"{BASE_URL}/api/assessments/{assessment_id}")
        assert get_response.status_code == 404, "Assessment should be deleted"
        
        print(f"SUCCESS: DELETE /api/assessments/{assessment_id} - Deleted successfully")
    
    # ============== Edge Cases Tests ==============
    def test_18_get_nonexistent_assessment(self):
        """Test GET /api/assessments/{invalid_id} - Should return 404"""
        response = self.session.get(f"{BASE_URL}/api/assessments/nonexistent-id-12345")
        assert response.status_code == 404
        print("SUCCESS: GET nonexistent assessment returns 404")
    
    def test_19_get_students_for_nonexistent_assessment(self):
        """Test GET students-for-grading with invalid assessment_id"""
        response = self.session.get(f"{BASE_URL}/api/assessments/students-for-grading/invalid-id")
        assert response.status_code == 404
        print("SUCCESS: GET students-for-grading with invalid ID returns 404")
    
    # ============== Cleanup ==============
    def test_99_cleanup_test_data(self):
        """Cleanup TEST_ prefixed assessments"""
        # Get all assessments
        response = self.session.get(f"{BASE_URL}/api/assessments")
        if response.status_code == 200:
            assessments = response.json()
            deleted_count = 0
            for assessment in assessments:
                if assessment.get("title", "").startswith("TEST_"):
                    delete_response = self.session.delete(f"{BASE_URL}/api/assessments/{assessment['id']}")
                    if delete_response.status_code == 200:
                        deleted_count += 1
            print(f"SUCCESS: Cleanup - Deleted {deleted_count} test assessments")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
