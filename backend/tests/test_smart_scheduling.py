"""
Smart Scheduling Engine API Tests
=================================
Tests for NASSAQ Smart Scheduling Engine APIs:
- Data validation
- Timetable generation
- Sessions and conflicts
- Pre-check and matrices
- Timetable management (publish, archive, delete)
"""

import pytest
import requests
import os
from datetime import datetime

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
PRINCIPAL_EMAIL = "principal1@nassaq.com"
PRINCIPAL_PASSWORD = "Principal@123"
SCHOOL_ID = "SCH-001"

# Existing timetable IDs from database (provided by main agent)
EXISTING_TIMETABLE_IDS = [
    "901d6395-fec3-4629-b349-2a19d56fc86d",
    "f08e70fa-a0e7-496e-a240-52d7c5b386bf"
]


class TestSmartSchedulingAuth:
    """Authentication tests for Smart Scheduling APIs"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for principal"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": PRINCIPAL_EMAIL, "password": PRINCIPAL_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        return data["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_login_success(self, auth_token):
        """Test principal login succeeds"""
        assert auth_token is not None
        assert len(auth_token) > 0
        print(f"✓ Login successful, token length: {len(auth_token)}")


class TestSmartSchedulingValidation:
    """Tests for data validation API"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": PRINCIPAL_EMAIL, "password": PRINCIPAL_PASSWORD}
        )
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_validate_data_readiness(self, auth_headers):
        """Test GET /api/smart-scheduling/validate/{school_id}"""
        response = requests.get(
            f"{BASE_URL}/api/smart-scheduling/validate/{SCHOOL_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Validation failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "school_id" in data
        assert "is_valid" in data
        assert "can_proceed" in data
        assert "issues" in data
        assert "summary" in data
        assert "message_ar" in data
        assert "message_en" in data
        
        # Verify school_id matches
        assert data["school_id"] == SCHOOL_ID
        
        # Verify summary contains expected fields
        summary = data["summary"]
        assert "school" in summary
        assert "grades" in summary
        assert "classes" in summary
        assert "teachers" in summary
        
        print(f"✓ Validation API works - is_valid: {data['is_valid']}, can_proceed: {data['can_proceed']}")
        print(f"  Summary: {summary.get('classes')} classes, {summary.get('teachers')} teachers")
    
    def test_validate_invalid_school(self, auth_headers):
        """Test validation with non-existent school"""
        response = requests.get(
            f"{BASE_URL}/api/smart-scheduling/validate/INVALID-SCHOOL-ID",
            headers=auth_headers
        )
        
        # Should return 200 with is_valid=False or 404
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            data = response.json()
            assert data["is_valid"] == False
            assert data["can_proceed"] == False
            print("✓ Invalid school returns is_valid=False")
        else:
            print("✓ Invalid school returns 404")


class TestSmartSchedulingPreCheck:
    """Tests for pre-scheduling check API"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": PRINCIPAL_EMAIL, "password": PRINCIPAL_PASSWORD}
        )
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_pre_scheduling_check(self, auth_headers):
        """Test GET /api/smart-scheduling/pre-check/{school_id}"""
        response = requests.get(
            f"{BASE_URL}/api/smart-scheduling/pre-check/{SCHOOL_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Pre-check failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "school_id" in data
        assert "can_schedule" in data
        assert "warnings" in data
        assert "errors" in data
        assert "statistics" in data
        assert "message_ar" in data
        assert "message_en" in data
        
        # Verify statistics
        stats = data["statistics"]
        assert "total_demand_periods" in stats
        assert "total_teacher_capacity" in stats
        assert "total_classes" in stats
        assert "total_teachers" in stats
        
        print(f"✓ Pre-check API works - can_schedule: {data['can_schedule']}")
        print(f"  Stats: demand={stats.get('total_demand_periods')}, capacity={stats.get('total_teacher_capacity')}")


class TestSmartSchedulingMatrices:
    """Tests for demand and resource matrix APIs"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": PRINCIPAL_EMAIL, "password": PRINCIPAL_PASSWORD}
        )
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_demand_matrix(self, auth_headers):
        """Test GET /api/smart-scheduling/demand-matrix/{school_id}"""
        response = requests.get(
            f"{BASE_URL}/api/smart-scheduling/demand-matrix/{SCHOOL_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Demand matrix failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "school_id" in data
        assert "total_classes" in data
        assert "total_demand_periods" in data
        assert "demands" in data
        
        # Verify demands structure if any exist
        if data["demands"]:
            demand = data["demands"][0]
            assert "class_id" in demand
            assert "class_name" in demand
            assert "subjects" in demand
            assert "total_periods_required" in demand
        
        print(f"✓ Demand matrix API works - {data['total_classes']} classes, {data['total_demand_periods']} periods")
    
    def test_resource_matrix(self, auth_headers):
        """Test GET /api/smart-scheduling/resource-matrix/{school_id}"""
        response = requests.get(
            f"{BASE_URL}/api/smart-scheduling/resource-matrix/{SCHOOL_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Resource matrix failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "school_id" in data
        assert "total_teachers" in data
        assert "total_capacity" in data
        assert "resources" in data
        
        # Verify resources structure if any exist
        if data["resources"]:
            resource = data["resources"][0]
            assert "teacher_id" in resource
            assert "teacher_name" in resource
            assert "weekly_load" in resource
            assert "availability" in resource
        
        print(f"✓ Resource matrix API works - {data['total_teachers']} teachers, {data['total_capacity']} capacity")


class TestSmartSchedulingTimetables:
    """Tests for timetable listing and retrieval APIs"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": PRINCIPAL_EMAIL, "password": PRINCIPAL_PASSWORD}
        )
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_get_school_timetables(self, auth_headers):
        """Test GET /api/smart-scheduling/timetables/{school_id}"""
        response = requests.get(
            f"{BASE_URL}/api/smart-scheduling/timetables/{SCHOOL_ID}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Get timetables failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "school_id" in data
        assert "total" in data
        assert "timetables" in data
        
        print(f"✓ Get timetables API works - {data['total']} timetables found")
        
        # Return timetables for use in other tests
        return data["timetables"]
    
    def test_get_timetable_details(self, auth_headers):
        """Test GET /api/smart-scheduling/timetable/{timetable_id}"""
        # Use existing timetable ID
        timetable_id = EXISTING_TIMETABLE_IDS[0]
        
        response = requests.get(
            f"{BASE_URL}/api/smart-scheduling/timetable/{timetable_id}",
            headers=auth_headers
        )
        
        # May return 404 if timetable doesn't exist
        if response.status_code == 404:
            print(f"⚠ Timetable {timetable_id} not found - skipping detail test")
            pytest.skip("Timetable not found")
        
        assert response.status_code == 200, f"Get timetable failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "id" in data
        assert "school_id" in data
        assert "status" in data
        
        print(f"✓ Get timetable details API works - status: {data.get('status')}")
    
    def test_get_nonexistent_timetable(self, auth_headers):
        """Test getting a non-existent timetable returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/smart-scheduling/timetable/nonexistent-id-12345",
            headers=auth_headers
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Non-existent timetable returns 404")


class TestSmartSchedulingSessions:
    """Tests for timetable sessions API"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": PRINCIPAL_EMAIL, "password": PRINCIPAL_PASSWORD}
        )
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_get_timetable_sessions(self, auth_headers):
        """Test GET /api/smart-scheduling/timetable/{id}/sessions"""
        timetable_id = EXISTING_TIMETABLE_IDS[0]
        
        response = requests.get(
            f"{BASE_URL}/api/smart-scheduling/timetable/{timetable_id}/sessions",
            headers=auth_headers
        )
        
        # May return 200 with empty sessions if timetable doesn't exist
        assert response.status_code == 200, f"Get sessions failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "timetable_id" in data
        assert "total" in data
        assert "sessions" in data
        
        print(f"✓ Get sessions API works - {data['total']} sessions found")
        
        # Verify session structure if any exist
        if data["sessions"]:
            session = data["sessions"][0]
            assert "id" in session
            assert "day_of_week" in session
            assert "period_number" in session
            print(f"  First session: day={session.get('day_of_week')}, period={session.get('period_number')}")
    
    def test_get_sessions_with_filters(self, auth_headers):
        """Test sessions API with day filter"""
        timetable_id = EXISTING_TIMETABLE_IDS[0]
        
        response = requests.get(
            f"{BASE_URL}/api/smart-scheduling/timetable/{timetable_id}/sessions",
            params={"day_of_week": "sunday"},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Get sessions with filter failed: {response.text}"
        data = response.json()
        
        # All sessions should be for Sunday
        for session in data.get("sessions", []):
            assert session.get("day_of_week") == "sunday", f"Session not on Sunday: {session}"
        
        print(f"✓ Sessions filter works - {data['total']} Sunday sessions")


class TestSmartSchedulingConflicts:
    """Tests for timetable conflicts API"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": PRINCIPAL_EMAIL, "password": PRINCIPAL_PASSWORD}
        )
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_get_timetable_conflicts(self, auth_headers):
        """Test GET /api/smart-scheduling/timetable/{id}/conflicts"""
        timetable_id = EXISTING_TIMETABLE_IDS[0]
        
        response = requests.get(
            f"{BASE_URL}/api/smart-scheduling/timetable/{timetable_id}/conflicts",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Get conflicts failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "timetable_id" in data
        assert "total" in data
        assert "critical_count" in data
        assert "high_count" in data
        assert "conflicts" in data
        
        print(f"✓ Get conflicts API works - {data['total']} conflicts ({data['critical_count']} critical)")


class TestSmartSchedulingGeneration:
    """Tests for timetable generation API"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": PRINCIPAL_EMAIL, "password": PRINCIPAL_PASSWORD}
        )
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_generate_timetable(self, auth_headers):
        """Test POST /api/smart-scheduling/generate/{school_id}"""
        response = requests.post(
            f"{BASE_URL}/api/smart-scheduling/generate/{SCHOOL_ID}",
            headers=auth_headers,
            json={}  # Empty request body uses defaults
        )
        
        assert response.status_code == 200, f"Generate timetable failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "success" in data
        assert "run_id" in data
        assert "status" in data
        assert "completion_percentage" in data
        assert "total_sessions" in data
        assert "scheduled_sessions" in data
        assert "conflicts_count" in data
        assert "message_ar" in data
        assert "message_en" in data
        
        print(f"✓ Generate timetable API works")
        print(f"  Success: {data['success']}")
        print(f"  Status: {data['status']}")
        print(f"  Sessions: {data['scheduled_sessions']}/{data['total_sessions']}")
        print(f"  Conflicts: {data['conflicts_count']}")
        
        # Store timetable_id for cleanup
        if data.get("timetable_id"):
            return data["timetable_id"]


class TestSmartSchedulingDelete:
    """Tests for timetable deletion API"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": PRINCIPAL_EMAIL, "password": PRINCIPAL_PASSWORD}
        )
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    def test_delete_nonexistent_timetable(self, auth_headers):
        """Test DELETE /api/smart-scheduling/timetable/{id} with non-existent ID"""
        response = requests.delete(
            f"{BASE_URL}/api/smart-scheduling/timetable/nonexistent-id-12345",
            headers=auth_headers
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        print("✓ Delete non-existent timetable returns 404")
    
    def test_delete_timetable_flow(self, auth_headers):
        """Test full flow: generate then delete timetable"""
        # First generate a new timetable
        gen_response = requests.post(
            f"{BASE_URL}/api/smart-scheduling/generate/{SCHOOL_ID}",
            headers=auth_headers,
            json={}
        )
        
        if gen_response.status_code != 200:
            pytest.skip("Could not generate timetable for delete test")
        
        gen_data = gen_response.json()
        timetable_id = gen_data.get("timetable_id")
        
        if not timetable_id:
            pytest.skip("No timetable_id returned from generation")
        
        print(f"  Generated timetable: {timetable_id}")
        
        # Now delete it
        del_response = requests.delete(
            f"{BASE_URL}/api/smart-scheduling/timetable/{timetable_id}",
            headers=auth_headers
        )
        
        assert del_response.status_code == 200, f"Delete failed: {del_response.text}"
        del_data = del_response.json()
        
        assert del_data.get("success") == True
        print(f"✓ Delete timetable API works - deleted {timetable_id}")
        
        # Verify it's deleted
        get_response = requests.get(
            f"{BASE_URL}/api/smart-scheduling/timetable/{timetable_id}",
            headers=auth_headers
        )
        
        assert get_response.status_code == 404, "Timetable should be deleted"
        print("✓ Verified timetable is deleted")


class TestSmartSchedulingUnauthorized:
    """Tests for unauthorized access"""
    
    def test_validate_without_auth(self):
        """Test validation API without authentication"""
        response = requests.get(
            f"{BASE_URL}/api/smart-scheduling/validate/{SCHOOL_ID}"
        )
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Validation without auth returns 401/403")
    
    def test_generate_without_auth(self):
        """Test generation API without authentication"""
        response = requests.post(
            f"{BASE_URL}/api/smart-scheduling/generate/{SCHOOL_ID}",
            json={}
        )
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Generation without auth returns 401/403")
    
    def test_delete_without_auth(self):
        """Test delete API without authentication"""
        response = requests.delete(
            f"{BASE_URL}/api/smart-scheduling/timetable/some-id"
        )
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Delete without auth returns 401/403")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
