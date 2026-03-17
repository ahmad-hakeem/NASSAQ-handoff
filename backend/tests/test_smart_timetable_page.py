"""
Test Smart Timetable Page APIs - Iteration 69
Tests for the new SmartTimetablePage and related APIs
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestSmartTimetableAPIs:
    """Tests for Smart Timetable Page APIs"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as principal
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        
        token = login_response.json().get("access_token")
        assert token, "No access token received"
        
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        self.school_id = "SCH-001"
    
    def test_get_timetables_for_school(self):
        """Test GET /api/smart-scheduling/timetables/{school_id}"""
        response = self.session.get(f"{BASE_URL}/api/smart-scheduling/timetables/{self.school_id}")
        
        assert response.status_code == 200, f"Failed to get timetables: {response.text}"
        
        data = response.json()
        assert "timetables" in data, "Response should contain 'timetables' key"
        assert isinstance(data["timetables"], list), "Timetables should be a list"
        
        # Verify we have timetables
        assert len(data["timetables"]) > 0, "Should have at least one timetable"
        
        # Verify timetable structure
        timetable = data["timetables"][0]
        assert "id" in timetable, "Timetable should have 'id'"
        assert "status" in timetable, "Timetable should have 'status'"
        
        print(f"✓ Found {len(data['timetables'])} timetables for school {self.school_id}")
        return data["timetables"][0]["id"]
    
    def test_get_timetable_sessions(self):
        """Test GET /api/smart-scheduling/timetable/{id}/sessions"""
        # First get a timetable ID
        timetables_response = self.session.get(f"{BASE_URL}/api/smart-scheduling/timetables/{self.school_id}")
        timetable_id = timetables_response.json()["timetables"][0]["id"]
        
        # Get sessions
        response = self.session.get(f"{BASE_URL}/api/smart-scheduling/timetable/{timetable_id}/sessions")
        
        assert response.status_code == 200, f"Failed to get sessions: {response.text}"
        
        data = response.json()
        assert "sessions" in data, "Response should contain 'sessions' key"
        assert isinstance(data["sessions"], list), "Sessions should be a list"
        
        # Verify we have sessions
        assert len(data["sessions"]) > 0, "Should have at least one session"
        
        # Verify session structure
        session = data["sessions"][0]
        assert "subject_name" in session, "Session should have 'subject_name'"
        assert "teacher_name" in session, "Session should have 'teacher_name'"
        assert "class_name" in session, "Session should have 'class_name'"
        assert "day_of_week" in session, "Session should have 'day_of_week'"
        assert "period_number" in session, "Session should have 'period_number'"
        
        print(f"✓ Found {len(data['sessions'])} sessions for timetable {timetable_id}")
    
    def test_get_timetable_conflicts(self):
        """Test GET /api/smart-scheduling/timetable/{id}/conflicts"""
        # First get a timetable ID
        timetables_response = self.session.get(f"{BASE_URL}/api/smart-scheduling/timetables/{self.school_id}")
        timetable_id = timetables_response.json()["timetables"][0]["id"]
        
        # Get conflicts
        response = self.session.get(f"{BASE_URL}/api/smart-scheduling/timetable/{timetable_id}/conflicts")
        
        assert response.status_code == 200, f"Failed to get conflicts: {response.text}"
        
        data = response.json()
        assert "conflicts" in data, "Response should contain 'conflicts' key"
        assert isinstance(data["conflicts"], list), "Conflicts should be a list"
        
        print(f"✓ Found {len(data['conflicts'])} conflicts for timetable {timetable_id}")
    
    def test_filter_sessions_by_day(self):
        """Test filtering sessions by day_of_week"""
        # First get a timetable ID
        timetables_response = self.session.get(f"{BASE_URL}/api/smart-scheduling/timetables/{self.school_id}")
        timetable_id = timetables_response.json()["timetables"][0]["id"]
        
        # Get sessions filtered by day
        response = self.session.get(
            f"{BASE_URL}/api/smart-scheduling/timetable/{timetable_id}/sessions",
            params={"day_of_week": "sunday"}
        )
        
        assert response.status_code == 200, f"Failed to get filtered sessions: {response.text}"
        
        data = response.json()
        sessions = data.get("sessions", [])
        
        # Verify all sessions are for Sunday
        for session in sessions:
            assert session.get("day_of_week") == "sunday", f"Session should be for Sunday, got {session.get('day_of_week')}"
        
        print(f"✓ Found {len(sessions)} Sunday sessions")
    
    def test_filter_sessions_by_class(self):
        """Test filtering sessions by class_id"""
        # First get a timetable ID
        timetables_response = self.session.get(f"{BASE_URL}/api/smart-scheduling/timetables/{self.school_id}")
        timetable_id = timetables_response.json()["timetables"][0]["id"]
        
        # Get all sessions first to find a class_id
        all_sessions_response = self.session.get(f"{BASE_URL}/api/smart-scheduling/timetable/{timetable_id}/sessions")
        all_sessions = all_sessions_response.json().get("sessions", [])
        
        if len(all_sessions) > 0:
            class_id = all_sessions[0].get("class_id")
            
            # Get sessions filtered by class
            response = self.session.get(
                f"{BASE_URL}/api/smart-scheduling/timetable/{timetable_id}/sessions",
                params={"class_id": class_id}
            )
            
            assert response.status_code == 200, f"Failed to get filtered sessions: {response.text}"
            
            data = response.json()
            sessions = data.get("sessions", [])
            
            # Verify all sessions are for the specified class
            for session in sessions:
                assert session.get("class_id") == class_id, f"Session should be for class {class_id}"
            
            print(f"✓ Found {len(sessions)} sessions for class {class_id}")
    
    def test_filter_sessions_by_teacher(self):
        """Test filtering sessions by teacher_id"""
        # First get a timetable ID
        timetables_response = self.session.get(f"{BASE_URL}/api/smart-scheduling/timetables/{self.school_id}")
        timetable_id = timetables_response.json()["timetables"][0]["id"]
        
        # Get all sessions first to find a teacher_id
        all_sessions_response = self.session.get(f"{BASE_URL}/api/smart-scheduling/timetable/{timetable_id}/sessions")
        all_sessions = all_sessions_response.json().get("sessions", [])
        
        if len(all_sessions) > 0:
            teacher_id = all_sessions[0].get("teacher_id")
            
            # Get sessions filtered by teacher
            response = self.session.get(
                f"{BASE_URL}/api/smart-scheduling/timetable/{timetable_id}/sessions",
                params={"teacher_id": teacher_id}
            )
            
            assert response.status_code == 200, f"Failed to get filtered sessions: {response.text}"
            
            data = response.json()
            sessions = data.get("sessions", [])
            
            # Verify all sessions are for the specified teacher
            for session in sessions:
                assert session.get("teacher_id") == teacher_id, f"Session should be for teacher {teacher_id}"
            
            print(f"✓ Found {len(sessions)} sessions for teacher {teacher_id}")
    
    def test_get_classes(self):
        """Test GET /api/classes - needed for class view"""
        response = self.session.get(f"{BASE_URL}/api/classes", params={"school_id": self.school_id})
        
        assert response.status_code == 200, f"Failed to get classes: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Classes should be a list"
        assert len(data) > 0, "Should have at least one class"
        
        # Verify class structure
        cls = data[0]
        assert "id" in cls, "Class should have 'id'"
        assert "name" in cls or "name_ar" in cls, "Class should have 'name' or 'name_ar'"
        
        print(f"✓ Found {len(data)} classes")
    
    def test_get_teachers(self):
        """Test GET /api/teachers - needed for teacher view"""
        response = self.session.get(f"{BASE_URL}/api/teachers", params={"school_id": self.school_id})
        
        assert response.status_code == 200, f"Failed to get teachers: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Teachers should be a list"
        assert len(data) > 0, "Should have at least one teacher"
        
        # Verify teacher structure
        teacher = data[0]
        assert "id" in teacher or "teacher_id" in teacher, "Teacher should have 'id' or 'teacher_id'"
        assert "full_name" in teacher or "full_name_ar" in teacher, "Teacher should have 'full_name' or 'full_name_ar'"
        
        print(f"✓ Found {len(data)} teachers")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
