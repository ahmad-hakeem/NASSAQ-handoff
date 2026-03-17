"""
Test Teacher Module APIs - NASSAQ Platform
Tests for:
- Teacher login with correct teacher_id
- Teacher Dashboard API
- Teacher Classes API
- Teacher Schedule API
- Teacher Assessments API
- Behavior API
- Resources API
- Messages API
- Grades API
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEACHER_EMAIL = "teacher1@nor.edu.sa"
TEACHER_PASSWORD = "Teacher@123"
ADMIN_EMAIL = "admin@nassaq.com"
ADMIN_PASSWORD = "Admin@123"


class TestTeacherLogin:
    """Test teacher login returns correct teacher_id"""
    
    def test_teacher_login_success(self):
        """Test teacher can login and receives teacher_id"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEACHER_EMAIL,
            "password": TEACHER_PASSWORD
        })
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "access_token" in data, "Missing access_token in response"
        assert "user" in data, "Missing user in response"
        
        user = data["user"]
        assert user.get("role") == "teacher", f"Expected role 'teacher', got '{user.get('role')}'"
        assert user.get("email") == TEACHER_EMAIL, f"Email mismatch"
        
        # Verify teacher_id is returned
        teacher_id = user.get("teacher_id") or user.get("id")
        assert teacher_id is not None, "Missing teacher_id in user response"
        print(f"Teacher login successful. teacher_id: {teacher_id}")
        
        return data


class TestTeacherDashboardAPI:
    """Test Teacher Dashboard API"""
    
    @pytest.fixture
    def auth_token_and_teacher_id(self):
        """Get auth token and teacher_id"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEACHER_EMAIL,
            "password": TEACHER_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        token = data.get("access_token")
        user = data.get("user", {})
        teacher_id = user.get("teacher_id") or user.get("id")
        return token, teacher_id
    
    def test_teacher_dashboard_api(self, auth_token_and_teacher_id):
        """Test GET /api/teacher/dashboard/{teacher_id}"""
        token, teacher_id = auth_token_and_teacher_id
        
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{BASE_URL}/api/teacher/dashboard/{teacher_id}",
            headers=headers
        )
        
        assert response.status_code == 200, f"Dashboard API failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "teacher" in data, "Missing 'teacher' in response"
        assert "stats" in data, "Missing 'stats' in response"
        
        # Verify stats structure
        stats = data.get("stats", {})
        expected_stats = ["my_classes", "my_students", "today_lessons", "pending_attendance"]
        for stat in expected_stats:
            assert stat in stats, f"Missing '{stat}' in stats"
        
        print(f"Dashboard API response: {data}")
        return data


class TestTeacherClassesAPI:
    """Test Teacher Classes API"""
    
    @pytest.fixture
    def auth_token_and_teacher_id(self):
        """Get auth token and teacher_id"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEACHER_EMAIL,
            "password": TEACHER_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        token = data.get("access_token")
        user = data.get("user", {})
        teacher_id = user.get("teacher_id") or user.get("id")
        return token, teacher_id
    
    def test_teacher_classes_api(self, auth_token_and_teacher_id):
        """Test GET /api/teacher/classes/{teacher_id}"""
        token, teacher_id = auth_token_and_teacher_id
        
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{BASE_URL}/api/teacher/classes/{teacher_id}",
            headers=headers
        )
        
        assert response.status_code == 200, f"Classes API failed: {response.text}"
        data = response.json()
        
        # Response should be a list
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        
        print(f"Teacher classes count: {len(data)}")
        if data:
            print(f"First class: {data[0]}")
        
        return data


class TestTeacherScheduleAPI:
    """Test Teacher Schedule API"""
    
    @pytest.fixture
    def auth_token_and_teacher_id(self):
        """Get auth token and teacher_id"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEACHER_EMAIL,
            "password": TEACHER_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        token = data.get("access_token")
        user = data.get("user", {})
        teacher_id = user.get("teacher_id") or user.get("id")
        return token, teacher_id
    
    def test_teacher_schedule_api(self, auth_token_and_teacher_id):
        """Test GET /api/teacher/schedule/{teacher_id}"""
        token, teacher_id = auth_token_and_teacher_id
        
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{BASE_URL}/api/teacher/schedule/{teacher_id}",
            headers=headers
        )
        
        assert response.status_code == 200, f"Schedule API failed: {response.text}"
        data = response.json()
        
        # Response should be a list
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        
        print(f"Teacher schedule sessions count: {len(data)}")
        if data:
            print(f"First session: {data[0]}")
        
        return data


class TestTeacherAssessmentsAPI:
    """Test Teacher Assessments API"""
    
    @pytest.fixture
    def auth_token_and_teacher_id(self):
        """Get auth token and teacher_id"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEACHER_EMAIL,
            "password": TEACHER_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        token = data.get("access_token")
        user = data.get("user", {})
        teacher_id = user.get("teacher_id") or user.get("id")
        return token, teacher_id
    
    def test_teacher_assessments_api(self, auth_token_and_teacher_id):
        """Test GET /api/teacher/assessments/{teacher_id}"""
        token, teacher_id = auth_token_and_teacher_id
        
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{BASE_URL}/api/teacher/assessments/{teacher_id}",
            headers=headers
        )
        
        assert response.status_code == 200, f"Assessments API failed: {response.text}"
        data = response.json()
        
        # Response should be a list
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        
        print(f"Teacher assessments count: {len(data)}")
        return data


class TestBehaviorAPI:
    """Test Behavior API - GET and POST"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEACHER_EMAIL,
            "password": TEACHER_PASSWORD
        })
        assert response.status_code == 200
        return response.json().get("access_token")
    
    def test_get_behavior_records(self, auth_token):
        """Test GET /api/behavior"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/behavior", headers=headers)
        
        assert response.status_code == 200, f"GET behavior failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        
        print(f"Behavior records count: {len(data)}")
        return data
    
    def test_create_behavior_record(self, auth_token):
        """Test POST /api/behavior"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        behavior_data = {
            "student_id": f"TEST_student_{uuid.uuid4().hex[:8]}",
            "class_id": "test-class-001",
            "type": "positive",
            "description": "TEST: طالب متميز في المشاركة",
            "date": "2025-01-15"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/behavior",
            headers=headers,
            json=behavior_data
        )
        
        assert response.status_code == 200, f"POST behavior failed: {response.text}"
        data = response.json()
        
        assert "message" in data, "Missing message in response"
        assert "record" in data, "Missing record in response"
        
        record = data.get("record", {})
        assert record.get("type") == "positive", "Type mismatch"
        
        print(f"Created behavior record: {record.get('id')}")
        return data


class TestResourcesAPI:
    """Test Resources API - GET and POST"""
    
    @pytest.fixture
    def auth_token_and_teacher_id(self):
        """Get auth token and teacher_id"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEACHER_EMAIL,
            "password": TEACHER_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        token = data.get("access_token")
        user = data.get("user", {})
        teacher_id = user.get("teacher_id") or user.get("id")
        return token, teacher_id
    
    def test_get_resources(self, auth_token_and_teacher_id):
        """Test GET /api/resources"""
        token, teacher_id = auth_token_and_teacher_id
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/resources", headers=headers)
        
        assert response.status_code == 200, f"GET resources failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        
        print(f"Resources count: {len(data)}")
        return data
    
    def test_create_resource(self, auth_token_and_teacher_id):
        """Test POST /api/resources"""
        token, teacher_id = auth_token_and_teacher_id
        headers = {"Authorization": f"Bearer {token}"}
        
        resource_data = {
            "teacher_id": teacher_id,
            "title": f"TEST: مصدر تعليمي {uuid.uuid4().hex[:6]}",
            "type": "document",
            "subject": "الرياضيات",
            "description": "TEST: ملف تعليمي للاختبار",
            "url": "https://example.com/test-resource.pdf"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/resources",
            headers=headers,
            json=resource_data
        )
        
        assert response.status_code == 200, f"POST resources failed: {response.text}"
        data = response.json()
        
        assert "message" in data, "Missing message in response"
        assert "resource" in data, "Missing resource in response"
        
        resource = data.get("resource", {})
        assert resource.get("title") == resource_data["title"], "Title mismatch"
        
        print(f"Created resource: {resource.get('id')}")
        return data


class TestMessagesAPI:
    """Test Messages API - GET and POST"""
    
    @pytest.fixture
    def auth_token_and_teacher_id(self):
        """Get auth token and teacher_id"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEACHER_EMAIL,
            "password": TEACHER_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        token = data.get("access_token")
        user = data.get("user", {})
        teacher_id = user.get("teacher_id") or user.get("id")
        return token, teacher_id
    
    def test_get_messages(self, auth_token_and_teacher_id):
        """Test GET /api/messages"""
        token, teacher_id = auth_token_and_teacher_id
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/messages", headers=headers)
        
        assert response.status_code == 200, f"GET messages failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        
        print(f"Messages count: {len(data)}")
        return data
    
    def test_send_message(self, auth_token_and_teacher_id):
        """Test POST /api/messages"""
        token, teacher_id = auth_token_and_teacher_id
        headers = {"Authorization": f"Bearer {token}"}
        
        message_data = {
            "sender_id": teacher_id,
            "recipient_type": "parent",
            "recipient_id": f"TEST_parent_{uuid.uuid4().hex[:8]}",
            "subject": f"TEST: رسالة اختبار {uuid.uuid4().hex[:6]}",
            "content": "TEST: هذه رسالة اختبار من المعلم",
            "class_id": "test-class-001"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/messages",
            headers=headers,
            json=message_data
        )
        
        assert response.status_code == 200, f"POST messages failed: {response.text}"
        data = response.json()
        
        assert "message" in data, "Missing message in response"
        assert "data" in data, "Missing data in response"
        
        msg = data.get("data", {})
        assert msg.get("status") == "sent", f"Expected status 'sent', got '{msg.get('status')}'"
        
        print(f"Sent message: {msg.get('id')}")
        return data


class TestGradesAPI:
    """Test Grades API"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEACHER_EMAIL,
            "password": TEACHER_PASSWORD
        })
        assert response.status_code == 200
        return response.json().get("access_token")
    
    def test_get_grades(self, auth_token):
        """Test GET /api/grades"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        response = requests.get(f"{BASE_URL}/api/grades", headers=headers)
        
        assert response.status_code == 200, f"GET grades failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        
        print(f"Grades count: {len(data)}")
        return data


class TestAssessmentsCreateAPI:
    """Test Assessments Create API"""
    
    @pytest.fixture
    def auth_token_and_teacher_id(self):
        """Get auth token and teacher_id"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEACHER_EMAIL,
            "password": TEACHER_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        token = data.get("access_token")
        user = data.get("user", {})
        teacher_id = user.get("teacher_id") or user.get("id")
        return token, teacher_id
    
    def test_create_assessment(self, auth_token_and_teacher_id):
        """Test POST /api/assessments - uses Pydantic model with title and assessment_type"""
        token, teacher_id = auth_token_and_teacher_id
        headers = {"Authorization": f"Bearer {token}"}
        
        # First get teacher's classes to use a real class_id
        classes_response = requests.get(
            f"{BASE_URL}/api/teacher/classes/{teacher_id}",
            headers=headers
        )
        
        # If teacher has no classes, skip this test
        if classes_response.status_code != 200 or not classes_response.json():
            pytest.skip("Teacher has no assigned classes - skipping assessment creation test")
        
        classes = classes_response.json()
        class_id = classes[0].get("id") if classes else None
        
        if not class_id:
            pytest.skip("No valid class_id found")
        
        # Note: POST /api/assessments uses Pydantic model requiring 'title' and 'assessment_type'
        assessment_data = {
            "teacher_id": teacher_id,
            "title": f"TEST: اختبار {uuid.uuid4().hex[:6]}",
            "assessment_type": "quiz",  # Must be one of: quiz, exam, homework, project, participation
            "class_id": class_id,
            "max_score": 100,
            "date": "2025-01-20"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/assessments",
            headers=headers,
            json=assessment_data
        )
        
        assert response.status_code == 200, f"POST assessments failed: {response.text}"
        data = response.json()
        
        # Response uses AssessmentResponse model
        assert "id" in data, "Missing id in response"
        assert data.get("title") == assessment_data["title"], "Title mismatch"
        
        print(f"Created assessment: {data.get('id')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
