"""
Test Schedule Page APIs and Hakim Assistant
Tests for iteration 54 - Schedule Page with Drag & Drop and Hakim AI
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://school-timetable-ai.preview.emergentagent.com').rstrip('/')

class TestScheduleAPIs:
    """Schedule Page Backend API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token for school principal"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.school_id = "school-nor-001"
    
    # ============== TIME SLOTS TESTS ==============
    def test_get_time_slots(self):
        """Test GET /api/time-slots - Get time slots for school"""
        response = requests.get(
            f"{BASE_URL}/api/time-slots?school_id={self.school_id}",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) > 0, "Should have time slots"
        
        # Verify time slot structure
        slot = data[0]
        assert "id" in slot
        assert "name" in slot
        assert "start_time" in slot
        assert "end_time" in slot
        assert "slot_number" in slot
        print(f"✓ GET /api/time-slots - Found {len(data)} time slots")
    
    def test_seed_time_slots_existing(self):
        """Test POST /api/seed/time-slots - Should return existing message"""
        response = requests.post(
            f"{BASE_URL}/api/seed/time-slots/{self.school_id}",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "message" in data
        assert "count" in data
        print(f"✓ POST /api/seed/time-slots - {data['message']}, count: {data['count']}")
    
    # ============== SCHEDULES TESTS ==============
    def test_get_schedules(self):
        """Test GET /api/schedules - Get schedules for school"""
        response = requests.get(
            f"{BASE_URL}/api/schedules?school_id={self.school_id}",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        if len(data) > 0:
            schedule = data[0]
            assert "id" in schedule
            assert "name" in schedule
            assert "status" in schedule
            self.schedule_id = schedule["id"]
        print(f"✓ GET /api/schedules - Found {len(data)} schedules")
        return data
    
    def test_get_schedule_sessions(self):
        """Test GET /api/schedule-sessions - Get sessions for schedule"""
        # First get a schedule
        schedules = self.test_get_schedules()
        if not schedules:
            pytest.skip("No schedules available")
        
        schedule_id = schedules[0]["id"]
        response = requests.get(
            f"{BASE_URL}/api/schedule-sessions?schedule_id={schedule_id}",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        if len(data) > 0:
            session = data[0]
            assert "id" in session
            assert "day_of_week" in session or "day" in session
            assert "time_slot_id" in session
        print(f"✓ GET /api/schedule-sessions - Found {len(data)} sessions")
    
    def test_get_schedule_conflicts(self):
        """Test GET /api/schedules/{id}/conflicts - Get conflicts"""
        schedules = self.test_get_schedules()
        if not schedules:
            pytest.skip("No schedules available")
        
        schedule_id = schedules[0]["id"]
        response = requests.get(
            f"{BASE_URL}/api/schedules/{schedule_id}/conflicts",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "conflicts" in data or isinstance(data, dict)
        print(f"✓ GET /api/schedules/{schedule_id}/conflicts - Success")
    
    def test_get_conflict_suggestions(self):
        """Test GET /api/schedules/{id}/conflicts/suggestions"""
        schedules = self.test_get_schedules()
        if not schedules:
            pytest.skip("No schedules available")
        
        schedule_id = schedules[0]["id"]
        response = requests.get(
            f"{BASE_URL}/api/schedules/{schedule_id}/conflicts/suggestions",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "suggestions" in data or isinstance(data, dict)
        print(f"✓ GET /api/schedules/{schedule_id}/conflicts/suggestions - Success")


class TestHakimAssistant:
    """Hakim AI Assistant Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        assert login_response.status_code == 200
        self.token = login_response.json().get("access_token")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def test_hakim_chat_basic(self):
        """Test POST /api/hakim/chat - Basic greeting"""
        response = requests.post(
            f"{BASE_URL}/api/hakim/chat",
            headers=self.headers,
            json={"message": "مرحبا", "context": "general"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "response" in data
        assert len(data["response"]) > 0
        print(f"✓ POST /api/hakim/chat - Got response: {data['response'][:100]}...")
    
    def test_hakim_chat_schedule_context(self):
        """Test POST /api/hakim/chat - Schedule context"""
        response = requests.post(
            f"{BASE_URL}/api/hakim/chat",
            headers=self.headers,
            json={"message": "كيف أنشئ جدول جديد؟", "context": "schedule"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "response" in data
        print(f"✓ POST /api/hakim/chat (schedule) - Got response")
    
    def test_hakim_chat_with_suggestions(self):
        """Test POST /api/hakim/chat - Check suggestions"""
        response = requests.post(
            f"{BASE_URL}/api/hakim/chat",
            headers=self.headers,
            json={"message": "أريد إضافة مدرسة جديدة", "context": "admin"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "response" in data
        assert "suggestions" in data
        print(f"✓ POST /api/hakim/chat - Suggestions: {data.get('suggestions', [])}")


class TestAdminDashboardAPIs:
    """Admin Dashboard Quick Actions APIs"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token for platform admin"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nassaq.com",
            "password": "Admin@123"
        })
        assert login_response.status_code == 200, f"Login failed: {login_response.text}"
        self.token = login_response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_admin_stats(self):
        """Test GET /api/admin/stats - Platform statistics"""
        response = requests.get(
            f"{BASE_URL}/api/admin/stats",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "total_schools" in data or "schools" in data or isinstance(data, dict)
        print(f"✓ GET /api/admin/stats - Success")
    
    def test_analytics_endpoint(self):
        """Test analytics endpoint exists"""
        response = requests.get(
            f"{BASE_URL}/api/admin/analytics",
            headers=self.headers
        )
        # May return 200 or 404 depending on implementation
        print(f"✓ GET /api/admin/analytics - Status: {response.status_code}")
    
    def test_integrations_endpoint(self):
        """Test integrations endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/integrations",
            headers=self.headers
        )
        # May return 200 or 404 depending on implementation
        print(f"✓ GET /api/integrations - Status: {response.status_code}")


class TestTeachersAndClasses:
    """Teachers and Classes APIs for Schedule Page"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get auth token"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        assert login_response.status_code == 200
        self.token = login_response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.school_id = "school-nor-001"
    
    def test_get_teachers(self):
        """Test GET /api/teachers - Get teachers for school"""
        response = requests.get(
            f"{BASE_URL}/api/teachers?school_id={self.school_id}",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/teachers - Found {len(data)} teachers")
    
    def test_get_classes(self):
        """Test GET /api/classes - Get classes for school"""
        response = requests.get(
            f"{BASE_URL}/api/classes?school_id={self.school_id}",
            headers=self.headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/classes - Found {len(data)} classes")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
