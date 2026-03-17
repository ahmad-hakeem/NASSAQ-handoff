"""
Test cases for School Settings Edit Dialog and Constraint Toggle APIs
Tests for iteration 66 - تعديل مواعيد اليوم الدراسي وأزرار تفعيل/تعطيل القيود
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuthentication:
    """Authentication tests for principal login"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for principal"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        return data["access_token"]
    
    def test_principal_login(self, auth_token):
        """Test principal can login successfully"""
        assert auth_token is not None
        assert len(auth_token) > 0


class TestSchoolSettingsAPI:
    """Test PUT /api/school/settings API for editing day times"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for principal"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_school_settings(self, auth_headers):
        """Test GET /api/school/settings returns current settings"""
        response = requests.get(f"{BASE_URL}/api/school/settings", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get settings: {response.text}"
        data = response.json()
        # Verify settings structure
        assert "settings" in data or "school_day_start" in data or "periods_per_day" in data
    
    def test_update_school_settings_day_times(self, auth_headers):
        """Test PUT /api/school/settings updates day times correctly"""
        # First get current settings
        get_response = requests.get(f"{BASE_URL}/api/school/settings", headers=auth_headers)
        assert get_response.status_code == 200
        
        # Update settings with new day times
        update_data = {
            "settings": {
                "school_day_start": "07:30",
                "school_day_end": "13:30",
                "periods_per_day": 7,
                "period_duration_minutes": 45,
                "break_duration_minutes": 20,
                "prayer_duration_minutes": 20,
                "time_slots": [
                    {
                        "slot_number": 1,
                        "name_ar": "الحصة الأولى",
                        "name": "Period 1",
                        "start_time": "07:30",
                        "end_time": "08:15",
                        "duration_minutes": 45,
                        "type": "period",
                        "is_break": False
                    },
                    {
                        "slot_number": 2,
                        "name_ar": "الحصة الثانية",
                        "name": "Period 2",
                        "start_time": "08:15",
                        "end_time": "09:00",
                        "duration_minutes": 45,
                        "type": "period",
                        "is_break": False
                    },
                    {
                        "slot_number": 3,
                        "name_ar": "الحصة الثالثة",
                        "name": "Period 3",
                        "start_time": "09:00",
                        "end_time": "09:45",
                        "duration_minutes": 45,
                        "type": "period",
                        "is_break": False
                    },
                    {
                        "slot_number": None,
                        "name_ar": "الاستراحة",
                        "name": "Break",
                        "start_time": "09:45",
                        "end_time": "10:05",
                        "duration_minutes": 20,
                        "type": "break",
                        "is_break": True
                    }
                ]
            }
        }
        
        response = requests.put(f"{BASE_URL}/api/school/settings", 
                               headers=auth_headers, 
                               json=update_data)
        assert response.status_code == 200, f"Failed to update settings: {response.text}"
        data = response.json()
        assert "message" in data
        
    def test_update_school_settings_periods_count(self, auth_headers):
        """Test updating periods per day"""
        update_data = {
            "settings": {
                "periods_per_day": 6
            }
        }
        
        response = requests.put(f"{BASE_URL}/api/school/settings", 
                               headers=auth_headers, 
                               json=update_data)
        assert response.status_code == 200, f"Failed to update periods: {response.text}"


class TestConstraintToggleAPI:
    """Test PUT /api/school/constraints/{id} API for toggling constraints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for principal"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_admin_constraints(self, auth_headers):
        """Test GET /api/reference/admin-constraints returns constraints list"""
        response = requests.get(f"{BASE_URL}/api/reference/admin-constraints", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get constraints: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Constraints should be a list"
        if len(data) > 0:
            # Verify constraint structure
            constraint = data[0]
            assert "id" in constraint, "Constraint should have id"
            assert "name_ar" in constraint, "Constraint should have name_ar"
    
    def test_toggle_constraint_active(self, auth_headers):
        """Test toggling constraint is_active status"""
        # First get constraints
        get_response = requests.get(f"{BASE_URL}/api/reference/admin-constraints", headers=auth_headers)
        assert get_response.status_code == 200
        constraints = get_response.json()
        
        if len(constraints) == 0:
            pytest.skip("No constraints available to test")
        
        # Get first constraint
        constraint = constraints[0]
        constraint_id = constraint.get("id")
        current_status = constraint.get("is_active", True)
        
        # Toggle the status
        toggle_data = {"is_active": not current_status}
        response = requests.put(f"{BASE_URL}/api/school/constraints/{constraint_id}", 
                               headers=auth_headers, 
                               json=toggle_data)
        assert response.status_code == 200, f"Failed to toggle constraint: {response.text}"
        data = response.json()
        assert "message" in data
        
        # Toggle back to original
        toggle_back_data = {"is_active": current_status}
        response_back = requests.put(f"{BASE_URL}/api/school/constraints/{constraint_id}", 
                                    headers=auth_headers, 
                                    json=toggle_back_data)
        assert response_back.status_code == 200
    
    def test_toggle_constraint_invalid_id(self, auth_headers):
        """Test toggling non-existent constraint returns 404"""
        toggle_data = {"is_active": False}
        response = requests.put(f"{BASE_URL}/api/school/constraints/invalid-constraint-id-12345", 
                               headers=auth_headers, 
                               json=toggle_data)
        assert response.status_code == 404, "Should return 404 for invalid constraint"


class TestScheduleGenerationErrors:
    """Test schedule generation error handling"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for principal"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_schedules(self, auth_headers):
        """Test GET /api/schedules returns schedules list"""
        response = requests.get(f"{BASE_URL}/api/schedules", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get schedules: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Schedules should be a list"
    
    def test_get_schedule_sessions(self, auth_headers):
        """Test GET /api/schedule-sessions returns sessions"""
        # First get schedules
        schedules_response = requests.get(f"{BASE_URL}/api/schedules", headers=auth_headers)
        assert schedules_response.status_code == 200
        schedules = schedules_response.json()
        
        if len(schedules) == 0:
            pytest.skip("No schedules available")
        
        schedule_id = schedules[0].get("id")
        response = requests.get(f"{BASE_URL}/api/schedule-sessions?schedule_id={schedule_id}", 
                               headers=auth_headers)
        assert response.status_code == 200, f"Failed to get sessions: {response.text}"


class TestTimeSlots:
    """Test time slots API"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers for principal"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_time_slots(self, auth_headers):
        """Test GET /api/time-slots returns time slots"""
        response = requests.get(f"{BASE_URL}/api/time-slots", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get time slots: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Time slots should be a list"
        if len(data) > 0:
            slot = data[0]
            # Verify slot structure
            assert "start_time" in slot or "slot_number" in slot
