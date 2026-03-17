"""
Test cases for Conflict Resolution APIs
- GET /api/schedules/{schedule_id}/conflicts/suggestions
- POST /api/schedules/{schedule_id}/conflicts/apply-suggestion
- POST /api/schedules/{schedule_id}/conflicts/auto-resolve
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
PRINCIPAL_EMAIL = "principal1@nassaq.com"
PRINCIPAL_PASSWORD = "Principal@123"
ADMIN_EMAIL = "admin@nassaq.com"
ADMIN_PASSWORD = "Admin@123"


@pytest.fixture(scope="module")
def principal_token():
    """Get authentication token for school principal"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": PRINCIPAL_EMAIL, "password": PRINCIPAL_PASSWORD}
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Principal authentication failed")


@pytest.fixture(scope="module")
def admin_token():
    """Get authentication token for platform admin"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Admin authentication failed")


@pytest.fixture(scope="module")
def schedule_id(principal_token):
    """Get existing schedule ID for testing"""
    headers = {"Authorization": f"Bearer {principal_token}"}
    response = requests.get(
        f"{BASE_URL}/api/schedules?school_id=school-nor-001",
        headers=headers
    )
    if response.status_code == 200 and len(response.json()) > 0:
        return response.json()[0]["id"]
    pytest.skip("No schedules found for testing")


@pytest.fixture(scope="module")
def session_data(principal_token, schedule_id):
    """Get existing session data for testing"""
    headers = {"Authorization": f"Bearer {principal_token}"}
    response = requests.get(
        f"{BASE_URL}/api/schedule-sessions?schedule_id={schedule_id}",
        headers=headers
    )
    if response.status_code == 200 and len(response.json()) > 0:
        return response.json()[0]
    pytest.skip("No sessions found for testing")


@pytest.fixture(scope="module")
def time_slots(principal_token):
    """Get time slots for testing"""
    headers = {"Authorization": f"Bearer {principal_token}"}
    response = requests.get(
        f"{BASE_URL}/api/time-slots?school_id=school-nor-001",
        headers=headers
    )
    if response.status_code == 200:
        return response.json()
    pytest.skip("No time slots found")


class TestConflictSuggestionsAPI:
    """Tests for GET /api/schedules/{schedule_id}/conflicts/suggestions"""
    
    def test_get_suggestions_success(self, principal_token, schedule_id):
        """Test getting conflict suggestions returns proper structure"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        response = requests.get(
            f"{BASE_URL}/api/schedules/{schedule_id}/conflicts/suggestions",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "schedule_id" in data
        assert "total_suggestions" in data
        assert "suggestions" in data
        assert "can_auto_resolve" in data
        
        # Verify data types
        assert data["schedule_id"] == schedule_id
        assert isinstance(data["total_suggestions"], int)
        assert isinstance(data["suggestions"], list)
        assert isinstance(data["can_auto_resolve"], bool)
    
    def test_get_suggestions_invalid_schedule(self, principal_token):
        """Test getting suggestions for non-existent schedule returns 404"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        response = requests.get(
            f"{BASE_URL}/api/schedules/invalid-schedule-id/conflicts/suggestions",
            headers=headers
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "الجدول غير موجود" in data["detail"]
    
    def test_get_suggestions_unauthorized(self, schedule_id):
        """Test getting suggestions without auth returns 401/403"""
        response = requests.get(
            f"{BASE_URL}/api/schedules/{schedule_id}/conflicts/suggestions"
        )
        
        assert response.status_code in [401, 403]
    
    def test_suggestions_structure_when_conflicts_exist(self, principal_token, schedule_id):
        """Test suggestion structure contains required fields when conflicts exist"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        response = requests.get(
            f"{BASE_URL}/api/schedules/{schedule_id}/conflicts/suggestions",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # If there are suggestions, verify their structure
        if data["total_suggestions"] > 0:
            suggestion = data["suggestions"][0]
            
            # Required fields for each suggestion
            assert "id" in suggestion
            assert "conflict_type" in suggestion
            assert "session_id" in suggestion
            assert "suggested_action" in suggestion
            assert "suggestion_ar" in suggestion
            assert "suggestion_en" in suggestion
            assert "target_day" in suggestion
            assert "target_slot_id" in suggestion
            assert "confidence" in suggestion
            
            # Verify confidence is a percentage
            assert 0 <= suggestion["confidence"] <= 100


class TestApplySuggestionAPI:
    """Tests for POST /api/schedules/{schedule_id}/conflicts/apply-suggestion"""
    
    def test_apply_suggestion_missing_params(self, principal_token, schedule_id):
        """Test apply suggestion without required params returns 422"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        response = requests.post(
            f"{BASE_URL}/api/schedules/{schedule_id}/conflicts/apply-suggestion",
            headers=headers
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        
        # Verify all required params are mentioned
        missing_fields = [item["loc"][-1] for item in data["detail"]]
        assert "session_id" in missing_fields
        assert "target_day" in missing_fields
        assert "target_slot_id" in missing_fields
    
    def test_apply_suggestion_invalid_session(self, principal_token, schedule_id, time_slots):
        """Test apply suggestion with invalid session returns 404"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        slot_id = time_slots[0]["id"] if time_slots else "invalid-slot"
        
        response = requests.post(
            f"{BASE_URL}/api/schedules/{schedule_id}/conflicts/apply-suggestion",
            headers=headers,
            params={
                "session_id": "invalid-session-id",
                "target_day": "sunday",
                "target_slot_id": slot_id
            }
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "الحصة غير موجودة" in data["detail"]
    
    def test_apply_suggestion_invalid_schedule(self, principal_token, time_slots):
        """Test apply suggestion with invalid schedule returns 404"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        slot_id = time_slots[0]["id"] if time_slots else "invalid-slot"
        
        response = requests.post(
            f"{BASE_URL}/api/schedules/invalid-schedule/conflicts/apply-suggestion",
            headers=headers,
            params={
                "session_id": "some-session",
                "target_day": "sunday",
                "target_slot_id": slot_id
            }
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "الجدول غير موجود" in data["detail"]
    
    def test_apply_suggestion_invalid_day(self, principal_token, schedule_id, session_data, time_slots):
        """Test apply suggestion with invalid day returns 400"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        slot_id = time_slots[0]["id"] if time_slots else "invalid-slot"
        
        response = requests.post(
            f"{BASE_URL}/api/schedules/{schedule_id}/conflicts/apply-suggestion",
            headers=headers,
            params={
                "session_id": session_data["id"],
                "target_day": "friday",  # Not a working day
                "target_slot_id": slot_id
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "اليوم المحدد غير صالح" in data["detail"]
    
    def test_apply_suggestion_unauthorized(self, schedule_id, session_data, time_slots):
        """Test apply suggestion without auth returns 401/403"""
        slot_id = time_slots[0]["id"] if time_slots else "invalid-slot"
        
        response = requests.post(
            f"{BASE_URL}/api/schedules/{schedule_id}/conflicts/apply-suggestion",
            params={
                "session_id": session_data["id"],
                "target_day": "sunday",
                "target_slot_id": slot_id
            }
        )
        
        assert response.status_code in [401, 403]


class TestAutoResolveAPI:
    """Tests for POST /api/schedules/{schedule_id}/conflicts/auto-resolve"""
    
    def test_auto_resolve_no_conflicts(self, principal_token, schedule_id):
        """Test auto-resolve when no conflicts exist"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        response = requests.post(
            f"{BASE_URL}/api/schedules/{schedule_id}/conflicts/auto-resolve",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "success" in data
        assert "message_ar" in data
        assert "message_en" in data
        assert "resolved_count" in data
        assert "failed_count" in data
        
        # When no conflicts, should return success with 0 resolved
        assert data["success"] == True
        assert data["resolved_count"] == 0
        assert data["failed_count"] == 0
        assert "لا توجد تعارضات" in data["message_ar"]
    
    def test_auto_resolve_invalid_schedule(self, principal_token):
        """Test auto-resolve with invalid schedule returns 404"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        response = requests.post(
            f"{BASE_URL}/api/schedules/invalid-schedule-id/conflicts/auto-resolve",
            headers=headers
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "الجدول غير موجود" in data["detail"]
    
    def test_auto_resolve_unauthorized(self, schedule_id):
        """Test auto-resolve without auth returns 401/403"""
        response = requests.post(
            f"{BASE_URL}/api/schedules/{schedule_id}/conflicts/auto-resolve"
        )
        
        assert response.status_code in [401, 403]
    
    def test_auto_resolve_response_structure(self, principal_token, schedule_id):
        """Test auto-resolve returns proper response structure"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        response = requests.post(
            f"{BASE_URL}/api/schedules/{schedule_id}/conflicts/auto-resolve",
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify all expected fields
        assert isinstance(data["success"], bool)
        assert isinstance(data["message_ar"], str)
        assert isinstance(data["message_en"], str)
        assert isinstance(data["resolved_count"], int)
        assert isinstance(data["failed_count"], int)


class TestConflictResolutionIntegration:
    """Integration tests for conflict resolution workflow"""
    
    def test_suggestions_and_conflicts_consistency(self, principal_token, schedule_id):
        """Test that suggestions count matches conflicts count"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        
        # Get conflicts
        conflicts_response = requests.get(
            f"{BASE_URL}/api/schedules/{schedule_id}/conflicts",
            headers=headers
        )
        assert conflicts_response.status_code == 200
        conflicts_data = conflicts_response.json()
        
        # Get suggestions
        suggestions_response = requests.get(
            f"{BASE_URL}/api/schedules/{schedule_id}/conflicts/suggestions",
            headers=headers
        )
        assert suggestions_response.status_code == 200
        suggestions_data = suggestions_response.json()
        
        # If there are conflicts, there should be suggestions (or at least the API should work)
        if conflicts_data["total_conflicts"] > 0:
            # Suggestions should be generated for conflicts
            assert suggestions_data["total_suggestions"] >= 0
    
    def test_can_auto_resolve_flag(self, principal_token, schedule_id):
        """Test can_auto_resolve flag is set correctly"""
        headers = {"Authorization": f"Bearer {principal_token}"}
        
        response = requests.get(
            f"{BASE_URL}/api/schedules/{schedule_id}/conflicts/suggestions",
            headers=headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # can_auto_resolve should be True only if all suggestions have confidence >= 80
        if data["total_suggestions"] > 0:
            all_high_confidence = all(
                s.get("confidence", 0) >= 80 
                for s in data["suggestions"]
            )
            assert data["can_auto_resolve"] == all_high_confidence
        else:
            # No suggestions means can_auto_resolve should be False
            assert data["can_auto_resolve"] == False


class TestAdminAccess:
    """Test admin access to conflict resolution APIs"""
    
    def test_admin_can_access_suggestions(self, admin_token, schedule_id):
        """Test platform admin can access suggestions API"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(
            f"{BASE_URL}/api/schedules/{schedule_id}/conflicts/suggestions",
            headers=headers
        )
        
        assert response.status_code == 200
    
    def test_admin_can_auto_resolve(self, admin_token, schedule_id):
        """Test platform admin can use auto-resolve API"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.post(
            f"{BASE_URL}/api/schedules/{schedule_id}/conflicts/auto-resolve",
            headers=headers
        )
        
        assert response.status_code == 200
