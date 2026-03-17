"""
Test cases for Schedule Page New and School Settings Page Pro
Tests the new schedule page with class/teacher view and updated settings page
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://school-timetable-ai.preview.emergentagent.com')

class TestAuthentication:
    """Authentication tests"""
    
    def test_principal_login(self):
        """Test principal login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "school_principal"
        return data["access_token"]


class TestScheduleAPIs:
    """Schedule-related API tests"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        return response.json()["access_token"]
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Get auth headers"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_get_schedules(self, auth_headers):
        """Test getting schedules list"""
        response = requests.get(f"{BASE_URL}/api/schedules?school_id=SCH-001", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        # Verify schedule structure
        schedule = data[0]
        assert "id" in schedule
        assert "name" in schedule
        assert "school_id" in schedule
        assert schedule["school_id"] == "SCH-001"
    
    def test_get_schedule_sessions(self, auth_headers):
        """Test getting schedule sessions with teacher and subject names"""
        schedule_id = "b7858446-9dbf-48f1-914c-b96cf7b1d414"
        response = requests.get(f"{BASE_URL}/api/schedule-sessions?schedule_id={schedule_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 35  # 35 sessions as per requirement
        
        # Verify session structure includes teacher and subject names
        session = data[0]
        assert "id" in session
        assert "teacher_name" in session
        assert "subject_name" in session
        assert "class_name" in session
        assert "day_of_week" in session
        assert "time_slot_id" in session
        
        # Verify names are populated (not None)
        assert session["teacher_name"] is not None
        assert session["subject_name"] is not None
        assert session["class_name"] is not None
    
    def test_get_time_slots(self, auth_headers):
        """Test getting time slots"""
        response = requests.get(f"{BASE_URL}/api/time-slots?school_id=SCH-001", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 9  # 7 periods + break + prayer
        
        # Verify time slot structure
        slot = data[0]
        assert "id" in slot
        assert "name" in slot
        assert "start_time" in slot
        assert "end_time" in slot
        assert "slot_number" in slot
        assert "is_break" in slot
    
    def test_get_teachers(self, auth_headers):
        """Test getting teachers list"""
        response = requests.get(f"{BASE_URL}/api/teachers?school_id=SCH-001", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 5  # 5 teachers
        
        # Verify teacher structure
        teacher = data[0]
        assert "id" in teacher
        assert "full_name" in teacher
        assert "school_id" in teacher
    
    def test_get_classes(self, auth_headers):
        """Test getting classes list"""
        response = requests.get(f"{BASE_URL}/api/classes?school_id=SCH-001", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3  # 3 classes
        
        # Verify class structure
        class_item = data[0]
        assert "id" in class_item
        assert "name" in class_item
        assert "school_id" in class_item


class TestScheduleSessionsFiltering:
    """Test schedule sessions filtering by teacher and class"""
    
    @pytest.fixture
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        return {"Authorization": f"Bearer {response.json()['access_token']}"}
    
    def test_sessions_have_correct_days(self, auth_headers):
        """Test that sessions have correct day_of_week values"""
        schedule_id = "b7858446-9dbf-48f1-914c-b96cf7b1d414"
        response = requests.get(f"{BASE_URL}/api/schedule-sessions?schedule_id={schedule_id}", headers=auth_headers)
        data = response.json()
        
        valid_days = ["sunday", "monday", "tuesday", "wednesday", "thursday"]
        for session in data:
            assert session["day_of_week"] in valid_days or session["day"] in valid_days
    
    def test_sessions_have_teacher_info(self, auth_headers):
        """Test that all sessions have teacher information"""
        schedule_id = "b7858446-9dbf-48f1-914c-b96cf7b1d414"
        response = requests.get(f"{BASE_URL}/api/schedule-sessions?schedule_id={schedule_id}", headers=auth_headers)
        data = response.json()
        
        for session in data:
            assert session.get("teacher_id") is not None
            assert session.get("teacher_name") is not None
    
    def test_sessions_have_subject_info(self, auth_headers):
        """Test that all sessions have subject information"""
        schedule_id = "b7858446-9dbf-48f1-914c-b96cf7b1d414"
        response = requests.get(f"{BASE_URL}/api/schedule-sessions?schedule_id={schedule_id}", headers=auth_headers)
        data = response.json()
        
        for session in data:
            assert session.get("subject_id") is not None
            assert session.get("subject_name") is not None


class TestSchoolSettingsAPIs:
    """School settings API tests"""
    
    @pytest.fixture
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        return {"Authorization": f"Bearer {response.json()['access_token']}"}
    
    def test_school_settings_endpoint(self, auth_headers):
        """Test school settings endpoint"""
        response = requests.get(f"{BASE_URL}/api/school/settings", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "school_info" in data or "settings" in data
    
    def test_reference_teacher_ranks(self, auth_headers):
        """Test teacher ranks reference data"""
        response = requests.get(f"{BASE_URL}/api/reference/teacher-ranks", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
    
    def test_reference_admin_constraints(self, auth_headers):
        """Test admin constraints reference data"""
        response = requests.get(f"{BASE_URL}/api/reference/admin-constraints", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
