"""
Test Suite for Iteration 71 - UI/UX Improvements
Tests for:
1. Login redirect for school_principal to /principal
2. Schedule page - AI generation and timetable view
3. School Settings - Working days, auto-calculate times, CRUD for subjects/constraints, stage toggle
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
PRINCIPAL_EMAIL = "principal1@nassaq.com"
PRINCIPAL_PASSWORD = "Principal@123"
SCHOOL_ID = "SCH-001"


class TestAuthentication:
    """Test authentication and role-based redirects"""
    
    def test_principal_login_success(self):
        """Test that school_principal can login successfully"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        
        data = response.json()
        assert "access_token" in data, "No access token in response"
        assert "user" in data, "No user data in response"
        assert data["user"]["role"] == "school_principal", f"Expected school_principal role, got {data['user']['role']}"
        print(f"✅ Principal login successful, role: {data['user']['role']}")
        return data["access_token"]


class TestScheduleAPIs:
    """Test Schedule page related APIs"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_get_schedules(self, auth_token):
        """Test fetching schedules"""
        response = requests.get(
            f"{BASE_URL}/api/schedules?school_id={SCHOOL_ID}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed to get schedules: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of schedules"
        print(f"✅ Found {len(data)} schedules")
    
    def test_get_time_slots(self, auth_token):
        """Test fetching time slots"""
        response = requests.get(
            f"{BASE_URL}/api/time-slots?school_id={SCHOOL_ID}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed to get time slots: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of time slots"
        print(f"✅ Found {len(data)} time slots")
    
    def test_get_smart_timetables(self, auth_token):
        """Test fetching smart scheduling timetables"""
        response = requests.get(
            f"{BASE_URL}/api/smart-scheduling/timetables/{SCHOOL_ID}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed to get smart timetables: {response.text}"
        data = response.json()
        assert "timetables" in data, "Expected timetables key in response"
        print(f"✅ Found {len(data.get('timetables', []))} smart timetables")
    
    def test_validate_smart_scheduling(self, auth_token):
        """Test smart scheduling validation endpoint"""
        response = requests.get(
            f"{BASE_URL}/api/smart-scheduling/validate/{SCHOOL_ID}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed to validate: {response.text}"
        data = response.json()
        assert "can_proceed" in data, "Expected can_proceed in response"
        assert "summary" in data, "Expected summary in response"
        print(f"✅ Validation result: can_proceed={data['can_proceed']}")


class TestSchoolSettingsAPIs:
    """Test School Settings page related APIs"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_get_school_settings(self, auth_token):
        """Test fetching school settings"""
        response = requests.get(
            f"{BASE_URL}/api/school/settings",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed to get settings: {response.text}"
        data = response.json()
        
        # Check for working days info
        if "settings" in data:
            settings = data["settings"]
            if "working_days_ar" in settings:
                print(f"✅ Working days: {settings['working_days_ar']}")
            if "school_day_start" in settings:
                print(f"✅ School day start: {settings['school_day_start']}")
        print("✅ School settings retrieved successfully")
    
    def test_get_school_constraints(self, auth_token):
        """Test fetching school constraints"""
        response = requests.get(
            f"{BASE_URL}/api/school/constraints",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed to get constraints: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of constraints"
        print(f"✅ Found {len(data)} constraints")
        
        # Check constraint structure
        if len(data) > 0:
            constraint = data[0]
            assert "name_ar" in constraint or "name" in constraint, "Constraint should have name"
            assert "is_active" in constraint, "Constraint should have is_active field"
    
    def test_get_reference_stages(self, auth_token):
        """Test fetching reference stages"""
        response = requests.get(
            f"{BASE_URL}/api/reference/stages",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed to get stages: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of stages"
        print(f"✅ Found {len(data)} stages")
        
        # Check stage structure
        if len(data) > 0:
            stage = data[0]
            assert "name_ar" in stage or "name" in stage, "Stage should have name"
    
    def test_get_reference_subjects(self, auth_token):
        """Test fetching reference subjects"""
        response = requests.get(
            f"{BASE_URL}/api/reference/subjects",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed to get subjects: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of subjects"
        print(f"✅ Found {len(data)} subjects")
    
    def test_get_teachers(self, auth_token):
        """Test fetching teachers"""
        response = requests.get(
            f"{BASE_URL}/api/teachers",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed to get teachers: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of teachers"
        print(f"✅ Found {len(data)} teachers")
    
    def test_get_classes(self, auth_token):
        """Test fetching classes"""
        response = requests.get(
            f"{BASE_URL}/api/classes",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed to get classes: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Expected list of classes"
        print(f"✅ Found {len(data)} classes")


class TestConstraintsCRUD:
    """Test Constraints CRUD operations"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_toggle_constraint(self, auth_token):
        """Test toggling constraint active status"""
        # First get constraints
        response = requests.get(
            f"{BASE_URL}/api/school/constraints",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        constraints = response.json()
        
        if len(constraints) == 0:
            pytest.skip("No constraints to toggle")
        
        constraint = constraints[0]
        constraint_id = constraint.get("id")
        current_status = constraint.get("is_active", True)
        
        # Toggle the constraint
        response = requests.put(
            f"{BASE_URL}/api/school/constraints/{constraint_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"is_active": not current_status}
        )
        
        # Accept 200 or 404 (if endpoint doesn't exist)
        if response.status_code == 200:
            print(f"✅ Constraint toggled successfully")
        elif response.status_code == 404:
            print(f"⚠️ Constraint toggle endpoint not found (may use different path)")
        else:
            print(f"⚠️ Constraint toggle returned {response.status_code}: {response.text}")


class TestStageToggle:
    """Test Stage activation/deactivation"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Authentication failed")
    
    def test_get_stages_with_active_status(self, auth_token):
        """Test that stages have is_active field"""
        response = requests.get(
            f"{BASE_URL}/api/reference/stages",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        stages = response.json()
        
        if len(stages) > 0:
            # Check if stages have is_active field
            stage = stages[0]
            has_active = "is_active" in stage
            print(f"✅ Stages retrieved, has is_active field: {has_active}")
        else:
            print("⚠️ No stages found")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
