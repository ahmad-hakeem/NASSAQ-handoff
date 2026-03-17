"""
Test Suite for NASSAQ Smart Scheduling Engine
Tests:
1. GET /api/schedules/{schedule_id}/conflicts - Conflict detection with statistics
2. POST /api/schedules/{schedule_id}/generate - Smart schedule generation with statistics
"""

import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
PRINCIPAL_EMAIL = "principal1@nassaq.com"
PRINCIPAL_PASSWORD = "Principal@123"
ADMIN_EMAIL = "admin@nassaq.com"
ADMIN_PASSWORD = "Admin@123"


class TestSchedulingSmartEngine:
    """Tests for the Smart Scheduling Engine APIs"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session and authenticate"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as principal
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.user = login_response.json().get("user", {})
            self.tenant_id = self.user.get("tenant_id")
        else:
            pytest.skip(f"Login failed: {login_response.status_code}")
    
    # ============== CONFLICT DETECTION API TESTS ==============
    
    def test_conflicts_api_returns_statistics(self):
        """Test that conflicts API returns statistics object"""
        # First get a schedule
        schedules_response = self.session.get(f"{BASE_URL}/api/schedules", params={"school_id": self.tenant_id})
        
        if schedules_response.status_code != 200:
            pytest.skip("No schedules available for testing")
        
        schedules = schedules_response.json()
        if not schedules:
            pytest.skip("No schedules found")
        
        schedule_id = schedules[0].get("id")
        
        # Test conflicts API
        response = self.session.get(f"{BASE_URL}/api/schedules/{schedule_id}/conflicts")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify statistics object exists
        assert "statistics" in data, "Response should contain 'statistics' object"
        
        stats = data["statistics"]
        assert "teacher_conflicts" in stats, "Statistics should contain 'teacher_conflicts'"
        assert "class_conflicts" in stats, "Statistics should contain 'class_conflicts'"
        assert "room_conflicts" in stats, "Statistics should contain 'room_conflicts'"
        assert "total_sessions" in stats, "Statistics should contain 'total_sessions'"
        assert "sessions_with_conflicts" in stats, "Statistics should contain 'sessions_with_conflicts'"
        
        # Verify has_blocking_conflicts field
        assert "has_blocking_conflicts" in data, "Response should contain 'has_blocking_conflicts'"
        assert isinstance(data["has_blocking_conflicts"], bool), "has_blocking_conflicts should be boolean"
        
        print(f"✓ Conflicts API returns statistics: {stats}")
        print(f"✓ has_blocking_conflicts: {data['has_blocking_conflicts']}")
    
    def test_conflicts_api_returns_conflicts_list(self):
        """Test that conflicts API returns conflicts list with proper structure"""
        schedules_response = self.session.get(f"{BASE_URL}/api/schedules", params={"school_id": self.tenant_id})
        
        if schedules_response.status_code != 200 or not schedules_response.json():
            pytest.skip("No schedules available")
        
        schedule_id = schedules_response.json()[0].get("id")
        
        response = self.session.get(f"{BASE_URL}/api/schedules/{schedule_id}/conflicts")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "conflicts" in data, "Response should contain 'conflicts' list"
        assert "total_conflicts" in data, "Response should contain 'total_conflicts'"
        assert isinstance(data["conflicts"], list), "conflicts should be a list"
        
        # If there are conflicts, verify structure
        if data["conflicts"]:
            conflict = data["conflicts"][0]
            assert "type" in conflict, "Conflict should have 'type'"
            assert conflict["type"] in ["teacher_overlap", "class_overlap", "room_overlap"], \
                f"Invalid conflict type: {conflict['type']}"
            assert "day_of_week" in conflict, "Conflict should have 'day_of_week'"
            
        print(f"✓ Total conflicts: {data['total_conflicts']}")
    
    def test_conflicts_api_with_nonexistent_schedule(self):
        """Test conflicts API with non-existent schedule ID"""
        response = self.session.get(f"{BASE_URL}/api/schedules/nonexistent-id-12345/conflicts")
        
        # Should return empty conflicts, not error (based on implementation)
        assert response.status_code == 200
        data = response.json()
        assert data["total_conflicts"] == 0
        print("✓ Non-existent schedule returns empty conflicts")
    
    # ============== SCHEDULE GENERATION API TESTS ==============
    
    def test_generate_api_returns_statistics(self):
        """Test that generate API returns statistics and success_rate"""
        # First, we need a schedule to generate
        schedules_response = self.session.get(f"{BASE_URL}/api/schedules", params={"school_id": self.tenant_id})
        
        if schedules_response.status_code != 200 or not schedules_response.json():
            pytest.skip("No schedules available for testing")
        
        schedule_id = schedules_response.json()[0].get("id")
        
        # Test generate API
        response = self.session.post(f"{BASE_URL}/api/schedules/{schedule_id}/generate")
        
        # May return 400 if no assignments exist, which is valid
        if response.status_code == 400:
            error_detail = response.json().get("detail", "")
            if "إسنادات" in error_detail or "assignments" in error_detail.lower():
                pytest.skip("No teacher assignments available for generation")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify required fields
        assert "success" in data, "Response should contain 'success'"
        assert "success_rate" in data, "Response should contain 'success_rate'"
        assert "generation_time_seconds" in data, "Response should contain 'generation_time_seconds'"
        assert "statistics" in data, "Response should contain 'statistics'"
        
        # Verify statistics structure
        stats = data["statistics"]
        assert "placement_attempts" in stats, "Statistics should contain 'placement_attempts'"
        assert "conflicts_avoided" in stats, "Statistics should contain 'conflicts_avoided'"
        assert "teachers_scheduled" in stats, "Statistics should contain 'teachers_scheduled'"
        
        # Verify other fields
        assert "sessions_created" in data, "Response should contain 'sessions_created'"
        assert "sessions_requested" in data, "Response should contain 'sessions_requested'"
        assert "unplaced_sessions" in data, "Response should contain 'unplaced_sessions'"
        
        print(f"✓ Generate API returns statistics: {stats}")
        print(f"✓ Success rate: {data['success_rate']}%")
        print(f"✓ Generation time: {data['generation_time_seconds']}s")
    
    def test_generate_api_returns_messages(self):
        """Test that generate API returns Arabic and English messages"""
        schedules_response = self.session.get(f"{BASE_URL}/api/schedules", params={"school_id": self.tenant_id})
        
        if schedules_response.status_code != 200 or not schedules_response.json():
            pytest.skip("No schedules available")
        
        schedule_id = schedules_response.json()[0].get("id")
        
        response = self.session.post(f"{BASE_URL}/api/schedules/{schedule_id}/generate")
        
        if response.status_code == 400:
            pytest.skip("No assignments for generation")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data, "Response should contain Arabic 'message'"
        assert "message_en" in data, "Response should contain English 'message_en'"
        
        print(f"✓ Arabic message: {data['message']}")
        print(f"✓ English message: {data['message_en']}")
    
    def test_generate_api_with_nonexistent_schedule(self):
        """Test generate API with non-existent schedule"""
        response = self.session.post(f"{BASE_URL}/api/schedules/nonexistent-id-12345/generate")
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Non-existent schedule returns 404")
    
    def test_generate_api_with_options(self):
        """Test generate API with custom options"""
        schedules_response = self.session.get(f"{BASE_URL}/api/schedules", params={"school_id": self.tenant_id})
        
        if schedules_response.status_code != 200 or not schedules_response.json():
            pytest.skip("No schedules available")
        
        schedule_id = schedules_response.json()[0].get("id")
        
        # Test with custom parameters
        response = self.session.post(
            f"{BASE_URL}/api/schedules/{schedule_id}/generate",
            params={
                "respect_workload": True,
                "balance_daily": True,
                "avoid_consecutive": True,
                "max_daily_per_teacher": 5
            }
        )
        
        if response.status_code == 400:
            pytest.skip("No assignments for generation")
        
        assert response.status_code == 200
        print("✓ Generate API accepts custom options")


class TestSchedulingIntegration:
    """Integration tests for scheduling workflow"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Admin login failed")
    
    def test_schedules_list_endpoint(self):
        """Test that schedules list endpoint works"""
        response = self.session.get(f"{BASE_URL}/api/schedules")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert isinstance(response.json(), list), "Response should be a list"
        print(f"✓ Schedules list returns {len(response.json())} schedules")
    
    def test_time_slots_endpoint(self):
        """Test time slots endpoint"""
        response = self.session.get(f"{BASE_URL}/api/time-slots")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ Time slots endpoint working")
    
    def test_teacher_assignments_endpoint(self):
        """Test teacher assignments endpoint"""
        response = self.session.get(f"{BASE_URL}/api/teacher-assignments")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print(f"✓ Teacher assignments endpoint working")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
