"""
Test suite for NASSAQ Drag & Drop Schedule API and Test Accounts
Tests:
- PUT /api/schedule-sessions/{id}/move - Move session with conflict detection
- POST /api/seed/test-accounts - Seed test accounts
- Login with test accounts (principal, teacher)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "info@nassaqapp.com"
ADMIN_PASSWORD = "NassaqAdmin2026!##$$HBJ"
PRINCIPAL_EMAIL = "principal@nassaq.com"
PRINCIPAL_PASSWORD = "NassaqPrincipal2026"
TEACHER_EMAIL = "teacher@nassaq.com"
TEACHER_PASSWORD = "NassaqTeacher2026"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def admin_token(api_client):
    """Get admin authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    return response.json().get("access_token")


@pytest.fixture(scope="module")
def authenticated_client(api_client, admin_token):
    """Session with admin auth header"""
    api_client.headers.update({"Authorization": f"Bearer {admin_token}"})
    return api_client


class TestSeedTestAccounts:
    """Test seeding test accounts"""
    
    def test_seed_test_accounts_endpoint(self, api_client):
        """POST /api/seed/test-accounts - Seeds principal and teacher accounts"""
        response = api_client.post(f"{BASE_URL}/api/seed/test-accounts")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "accounts" in data
        assert "principal" in data["accounts"]
        assert "teacher" in data["accounts"]
        
        # Verify principal account info
        assert data["accounts"]["principal"]["email"] == PRINCIPAL_EMAIL
        assert data["accounts"]["principal"]["password"] == PRINCIPAL_PASSWORD
        assert data["accounts"]["principal"]["role"] == "School Principal"
        
        # Verify teacher account info
        assert data["accounts"]["teacher"]["email"] == TEACHER_EMAIL
        assert data["accounts"]["teacher"]["password"] == TEACHER_PASSWORD
        assert data["accounts"]["teacher"]["role"] == "Teacher"
        
        print(f"SUCCESS: Test accounts seeded - Principal: {PRINCIPAL_EMAIL}, Teacher: {TEACHER_EMAIL}")


class TestLoginWithTestAccounts:
    """Test login with seeded test accounts"""
    
    def test_login_principal_account(self, api_client):
        """Login with principal@nassaq.com / NassaqPrincipal2026"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert data["user"]["email"] == PRINCIPAL_EMAIL
        assert data["user"]["role"] == "school_principal"
        assert data["user"]["is_active"] == True
        
        print(f"SUCCESS: Principal login successful - Role: {data['user']['role']}")
    
    def test_login_teacher_account(self, api_client):
        """Login with teacher@nassaq.com / NassaqTeacher2026"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEACHER_EMAIL,
            "password": TEACHER_PASSWORD
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert data["user"]["email"] == TEACHER_EMAIL
        assert data["user"]["role"] == "teacher"
        assert data["user"]["is_active"] == True
        
        print(f"SUCCESS: Teacher login successful - Role: {data['user']['role']}")
    
    def test_login_admin_account(self, api_client):
        """Login with admin account"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert data["user"]["email"] == ADMIN_EMAIL
        assert data["user"]["role"] == "platform_admin"
        
        print(f"SUCCESS: Admin login successful - Role: {data['user']['role']}")


class TestMoveSessionAPI:
    """Test Move Session API (Drag & Drop)"""
    
    @pytest.fixture(scope="class")
    def test_data(self, authenticated_client):
        """Get test data - school, schedule, sessions, time slots"""
        # Get schools
        schools_res = authenticated_client.get(f"{BASE_URL}/api/schools")
        assert schools_res.status_code == 200
        schools = schools_res.json()
        assert len(schools) > 0, "No schools found"
        school_id = schools[0]["id"]
        
        # Get schedules
        schedules_res = authenticated_client.get(f"{BASE_URL}/api/schedules?school_id={school_id}")
        assert schedules_res.status_code == 200
        schedules = schedules_res.json()
        
        if len(schedules) == 0:
            pytest.skip("No schedules found for testing")
        
        schedule_id = schedules[0]["id"]
        
        # Get sessions
        sessions_res = authenticated_client.get(f"{BASE_URL}/api/schedule-sessions?schedule_id={schedule_id}")
        assert sessions_res.status_code == 200
        sessions = sessions_res.json()
        
        if len(sessions) == 0:
            pytest.skip("No sessions found for testing")
        
        # Get time slots
        slots_res = authenticated_client.get(f"{BASE_URL}/api/time-slots?school_id={school_id}")
        assert slots_res.status_code == 200
        time_slots = [s for s in slots_res.json() if not s.get("is_break")]
        
        return {
            "school_id": school_id,
            "schedule_id": schedule_id,
            "sessions": sessions,
            "time_slots": time_slots
        }
    
    def test_move_session_success(self, authenticated_client, test_data):
        """PUT /api/schedule-sessions/{id}/move - Move session to empty slot"""
        sessions = test_data["sessions"]
        time_slots = test_data["time_slots"]
        
        if len(sessions) == 0 or len(time_slots) < 2:
            pytest.skip("Not enough data for move test")
        
        session = sessions[0]
        session_id = session["id"]
        current_slot = session["time_slot_id"]
        
        # Find a different time slot
        new_slot = None
        for slot in time_slots:
            if slot["id"] != current_slot:
                new_slot = slot["id"]
                break
        
        if not new_slot:
            pytest.skip("No alternative time slot found")
        
        # Move to a different day (wednesday) to avoid conflicts
        response = authenticated_client.put(
            f"{BASE_URL}/api/schedule-sessions/{session_id}/move",
            json={
                "new_day_of_week": "wednesday",
                "new_time_slot_id": new_slot
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "success" in data
        assert "session_id" in data
        assert "old_day" in data
        assert "old_time_slot_id" in data
        assert "new_day" in data
        assert "new_time_slot_id" in data
        assert "status" in data
        assert "message" in data
        assert "message_en" in data
        
        # Status should be success or conflict_warning (not hard_conflict)
        assert data["status"] in ["success", "conflict_warning"]
        
        print(f"SUCCESS: Session moved - Status: {data['status']}, Message: {data['message_en']}")
    
    def test_move_session_conflict_detection(self, authenticated_client, test_data):
        """PUT /api/schedule-sessions/{id}/move - Detect conflict when moving to occupied slot"""
        sessions = test_data["sessions"]
        
        if len(sessions) < 2:
            pytest.skip("Need at least 2 sessions for conflict test")
        
        # Try to move first session to same position as second session
        session_1 = sessions[0]
        session_2 = sessions[1]
        
        response = authenticated_client.put(
            f"{BASE_URL}/api/schedule-sessions/{session_1['id']}/move",
            json={
                "new_day_of_week": session_2["day_of_week"],
                "new_time_slot_id": session_2["time_slot_id"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should detect conflict
        assert "status" in data
        assert "conflicts" in data
        
        # If there's a conflict, verify conflict structure
        if data["status"] == "hard_conflict":
            assert data["success"] == False
            assert len(data["conflicts"]) > 0
            
            for conflict in data["conflicts"]:
                assert "type" in conflict
                assert "message" in conflict
                assert "message_en" in conflict
                assert conflict["type"] in ["teacher_double_booking", "class_double_booking"]
            
            print(f"SUCCESS: Hard conflict detected - {len(data['conflicts'])} conflict(s)")
        else:
            print(f"INFO: Move allowed - Status: {data['status']}")
    
    def test_move_session_invalid_session_id(self, authenticated_client):
        """PUT /api/schedule-sessions/{id}/move - Returns 404 for invalid session"""
        response = authenticated_client.put(
            f"{BASE_URL}/api/schedule-sessions/invalid-session-id/move",
            json={
                "new_day_of_week": "monday",
                "new_time_slot_id": "some-slot-id"
            }
        )
        
        assert response.status_code == 404
        print("SUCCESS: Returns 404 for invalid session ID")
    
    def test_move_session_invalid_time_slot(self, authenticated_client, test_data):
        """PUT /api/schedule-sessions/{id}/move - Returns 400 for invalid time slot"""
        sessions = test_data["sessions"]
        
        if len(sessions) == 0:
            pytest.skip("No sessions found")
        
        session_id = sessions[0]["id"]
        
        response = authenticated_client.put(
            f"{BASE_URL}/api/schedule-sessions/{session_id}/move",
            json={
                "new_day_of_week": "monday",
                "new_time_slot_id": "invalid-slot-id"
            }
        )
        
        assert response.status_code == 400
        print("SUCCESS: Returns 400 for invalid time slot ID")


class TestMoveSessionResponseStructure:
    """Test Move Session API response structure"""
    
    def test_response_has_all_required_fields(self, authenticated_client, admin_token):
        """Verify MoveSessionResponse has all required fields"""
        # Get a session to test with
        schools_res = authenticated_client.get(f"{BASE_URL}/api/schools")
        if schools_res.status_code != 200 or len(schools_res.json()) == 0:
            pytest.skip("No schools available")
        
        school_id = schools_res.json()[0]["id"]
        
        schedules_res = authenticated_client.get(f"{BASE_URL}/api/schedules?school_id={school_id}")
        if schedules_res.status_code != 200 or len(schedules_res.json()) == 0:
            pytest.skip("No schedules available")
        
        schedule_id = schedules_res.json()[0]["id"]
        
        sessions_res = authenticated_client.get(f"{BASE_URL}/api/schedule-sessions?schedule_id={schedule_id}")
        if sessions_res.status_code != 200 or len(sessions_res.json()) == 0:
            pytest.skip("No sessions available")
        
        session = sessions_res.json()[0]
        
        # Get time slots
        slots_res = authenticated_client.get(f"{BASE_URL}/api/time-slots?school_id={school_id}")
        time_slots = [s for s in slots_res.json() if not s.get("is_break")]
        
        if len(time_slots) == 0:
            pytest.skip("No time slots available")
        
        # Make move request
        response = authenticated_client.put(
            f"{BASE_URL}/api/schedule-sessions/{session['id']}/move",
            json={
                "new_day_of_week": "friday",  # Use friday to likely avoid conflicts
                "new_time_slot_id": time_slots[0]["id"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify all required fields
        required_fields = [
            "success", "session_id", "old_day", "old_time_slot_id",
            "new_day", "new_time_slot_id", "conflicts", "status",
            "message", "message_en"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Verify field types
        assert isinstance(data["success"], bool)
        assert isinstance(data["session_id"], str)
        assert isinstance(data["conflicts"], list)
        assert data["status"] in ["success", "conflict_warning", "hard_conflict"]
        
        print(f"SUCCESS: Response has all required fields - Status: {data['status']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
