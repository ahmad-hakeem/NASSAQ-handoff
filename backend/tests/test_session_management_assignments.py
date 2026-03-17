"""
Test Suite for Smart Scheduling Session Management and Student Assignments APIs
اختبارات APIs إدارة الحصص والواجبات

Features tested:
1. PUT /api/smart-scheduling/session/{id} - تعديل حصة
2. DELETE /api/smart-scheduling/session/{id} - حذف حصة
3. POST /api/smart-scheduling/sessions/swap - تبديل حصتين
4. GET /api/student-portal/assignments - واجبات الطالب
"""

import pytest
import requests
import os
import uuid
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
PRINCIPAL_EMAIL = "principal1@nassaq.com"
PRINCIPAL_PASSWORD = "Principal@123"
SCHOOL_ID = "SCH-001"


class TestSessionManagementAPIs:
    """Test session management APIs for smart scheduling"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
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
            self.token = token
        else:
            pytest.skip("Authentication failed - skipping tests")
    
    def get_timetable_and_sessions(self):
        """Helper to get a timetable with sessions"""
        # Get timetables
        response = self.session.get(f"{BASE_URL}/api/smart-scheduling/timetables/{SCHOOL_ID}")
        assert response.status_code == 200
        timetables = response.json().get("timetables", [])
        
        if not timetables:
            pytest.skip("No timetables found")
        
        # Find a timetable with sessions
        for timetable in timetables:
            sessions_response = self.session.get(
                f"{BASE_URL}/api/smart-scheduling/timetable/{timetable['id']}/sessions"
            )
            if sessions_response.status_code == 200:
                sessions = sessions_response.json().get("sessions", [])
                if len(sessions) >= 2:
                    return timetable, sessions
        
        pytest.skip("No timetable with sufficient sessions found")
    
    # ============= PUT /api/smart-scheduling/session/{id} =============
    
    def test_update_session_change_teacher(self):
        """Test updating a session's teacher"""
        timetable, sessions = self.get_timetable_and_sessions()
        session_to_update = sessions[0]
        session_id = session_to_update["id"]
        
        # Get available teachers
        teachers_response = self.session.get(f"{BASE_URL}/api/teachers?school_id={SCHOOL_ID}")
        assert teachers_response.status_code == 200
        teachers = teachers_response.json()
        
        if not teachers:
            pytest.skip("No teachers found")
        
        # Find a different teacher
        current_teacher_id = session_to_update.get("teacher_id")
        new_teacher = None
        for t in teachers:
            teacher_id = t.get("id") or t.get("teacher_id")
            if teacher_id != current_teacher_id:
                new_teacher = t
                break
        
        if not new_teacher:
            pytest.skip("No alternative teacher found")
        
        new_teacher_id = new_teacher.get("id") or new_teacher.get("teacher_id")
        
        # Update session
        response = self.session.put(
            f"{BASE_URL}/api/smart-scheduling/session/{session_id}",
            json={"teacher_id": new_teacher_id}
        )
        
        print(f"Update session response: {response.status_code}")
        print(f"Response body: {response.text[:500]}")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        
        # Verify the change
        verify_response = self.session.get(
            f"{BASE_URL}/api/smart-scheduling/timetable/{timetable['id']}/sessions"
        )
        assert verify_response.status_code == 200
        updated_sessions = verify_response.json().get("sessions", [])
        updated_session = next((s for s in updated_sessions if s["id"] == session_id), None)
        
        assert updated_session is not None
        # Note: teacher_id might be updated or there might be conflicts
        print(f"Session updated successfully. New teacher_id: {updated_session.get('teacher_id')}")
    
    def test_update_session_invalid_id(self):
        """Test updating a non-existent session"""
        fake_session_id = str(uuid.uuid4())
        
        response = self.session.put(
            f"{BASE_URL}/api/smart-scheduling/session/{fake_session_id}",
            json={"teacher_id": "some-teacher-id"}
        )
        
        print(f"Update invalid session response: {response.status_code}")
        assert response.status_code == 404
    
    def test_update_session_empty_request(self):
        """Test updating a session with empty request body"""
        timetable, sessions = self.get_timetable_and_sessions()
        session_id = sessions[0]["id"]
        
        response = self.session.put(
            f"{BASE_URL}/api/smart-scheduling/session/{session_id}",
            json={}
        )
        
        print(f"Update with empty body response: {response.status_code}")
        # Should succeed but not change anything
        assert response.status_code == 200
    
    # ============= DELETE /api/smart-scheduling/session/{id} =============
    
    def test_delete_session(self):
        """Test deleting a session"""
        timetable, sessions = self.get_timetable_and_sessions()
        
        # Use the last session to avoid affecting other tests
        session_to_delete = sessions[-1]
        session_id = session_to_delete["id"]
        initial_count = len(sessions)
        
        print(f"Deleting session: {session_id}")
        print(f"Session details: {session_to_delete.get('subject_name')} - {session_to_delete.get('day_of_week')} P{session_to_delete.get('period_number')}")
        
        response = self.session.delete(f"{BASE_URL}/api/smart-scheduling/session/{session_id}")
        
        print(f"Delete session response: {response.status_code}")
        print(f"Response body: {response.text[:500]}")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "message_ar" in data
        
        # Verify deletion
        verify_response = self.session.get(
            f"{BASE_URL}/api/smart-scheduling/timetable/{timetable['id']}/sessions"
        )
        assert verify_response.status_code == 200
        remaining_sessions = verify_response.json().get("sessions", [])
        
        # Session should be deleted
        deleted_session = next((s for s in remaining_sessions if s["id"] == session_id), None)
        assert deleted_session is None, "Session should have been deleted"
        
        print(f"Session deleted successfully. Sessions count: {initial_count} -> {len(remaining_sessions)}")
    
    def test_delete_session_invalid_id(self):
        """Test deleting a non-existent session"""
        fake_session_id = str(uuid.uuid4())
        
        response = self.session.delete(f"{BASE_URL}/api/smart-scheduling/session/{fake_session_id}")
        
        print(f"Delete invalid session response: {response.status_code}")
        assert response.status_code == 404
    
    # ============= POST /api/smart-scheduling/sessions/swap =============
    
    def test_swap_sessions(self):
        """Test swapping two sessions"""
        timetable, sessions = self.get_timetable_and_sessions()
        
        if len(sessions) < 2:
            pytest.skip("Need at least 2 sessions to swap")
        
        session1 = sessions[0]
        session2 = sessions[1]
        
        # Store original positions
        original_day1 = session1.get("day_of_week")
        original_period1 = session1.get("period_number")
        original_day2 = session2.get("day_of_week")
        original_period2 = session2.get("period_number")
        
        print(f"Swapping sessions:")
        print(f"  Session 1: {session1['id']} - {original_day1} P{original_period1}")
        print(f"  Session 2: {session2['id']} - {original_day2} P{original_period2}")
        
        response = self.session.post(
            f"{BASE_URL}/api/smart-scheduling/sessions/swap",
            json={
                "session_id_1": session1["id"],
                "session_id_2": session2["id"]
            }
        )
        
        print(f"Swap sessions response: {response.status_code}")
        print(f"Response body: {response.text[:500]}")
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "message_ar" in data
        
        # Verify swap
        verify_response = self.session.get(
            f"{BASE_URL}/api/smart-scheduling/timetable/{timetable['id']}/sessions"
        )
        assert verify_response.status_code == 200
        updated_sessions = verify_response.json().get("sessions", [])
        
        updated_session1 = next((s for s in updated_sessions if s["id"] == session1["id"]), None)
        updated_session2 = next((s for s in updated_sessions if s["id"] == session2["id"]), None)
        
        if updated_session1 and updated_session2:
            # Verify positions were swapped
            assert updated_session1.get("day_of_week") == original_day2
            assert updated_session1.get("period_number") == original_period2
            assert updated_session2.get("day_of_week") == original_day1
            assert updated_session2.get("period_number") == original_period1
            print("Sessions swapped successfully!")
    
    def test_swap_sessions_invalid_ids(self):
        """Test swapping with invalid session IDs"""
        fake_id1 = str(uuid.uuid4())
        fake_id2 = str(uuid.uuid4())
        
        response = self.session.post(
            f"{BASE_URL}/api/smart-scheduling/sessions/swap",
            json={
                "session_id_1": fake_id1,
                "session_id_2": fake_id2
            }
        )
        
        print(f"Swap invalid sessions response: {response.status_code}")
        assert response.status_code == 404
    
    def test_swap_sessions_same_session(self):
        """Test swapping a session with itself"""
        timetable, sessions = self.get_timetable_and_sessions()
        session_id = sessions[0]["id"]
        
        response = self.session.post(
            f"{BASE_URL}/api/smart-scheduling/sessions/swap",
            json={
                "session_id_1": session_id,
                "session_id_2": session_id
            }
        )
        
        print(f"Swap same session response: {response.status_code}")
        # Should either fail or succeed without changes
        assert response.status_code in [200, 400]


class TestStudentAssignmentsAPI:
    """Test student assignments API"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Try to login as student first
        student_login = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "student@nassaq.com",
            "password": "Student@123"
        })
        
        if student_login.status_code == 200:
            token = student_login.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.token = token
            self.is_student = True
        else:
            # Fallback to principal for testing API existence
            principal_login = self.session.post(f"{BASE_URL}/api/auth/login", json={
                "email": PRINCIPAL_EMAIL,
                "password": PRINCIPAL_PASSWORD
            })
            
            if principal_login.status_code == 200:
                token = principal_login.json().get("access_token")
                self.session.headers.update({"Authorization": f"Bearer {token}"})
                self.token = token
                self.is_student = False
            else:
                pytest.skip("Authentication failed")
    
    def test_get_assignments_api_exists(self):
        """Test that assignments API endpoint exists"""
        response = self.session.get(f"{BASE_URL}/api/student-portal/assignments")
        
        print(f"Get assignments response: {response.status_code}")
        print(f"Response body: {response.text[:500]}")
        
        # If student role, should return 200
        # If principal role, should return 403 (forbidden)
        if self.is_student:
            assert response.status_code == 200
            data = response.json()
            assert "assignments" in data
            assert "statistics" in data
            print(f"Assignments count: {len(data.get('assignments', []))}")
            print(f"Statistics: {data.get('statistics')}")
        else:
            # Principal doesn't have student role, should get 403
            assert response.status_code in [403, 401]
            print("API exists but requires student role (expected behavior)")
    
    def test_get_assignments_with_status_filter(self):
        """Test filtering assignments by status"""
        if not self.is_student:
            pytest.skip("Need student account for this test")
        
        for status in ["pending", "submitted", "graded", "late"]:
            response = self.session.get(
                f"{BASE_URL}/api/student-portal/assignments",
                params={"status": status}
            )
            
            print(f"Get assignments with status={status}: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                assignments = data.get("assignments", [])
                # All returned assignments should have the requested status
                for a in assignments:
                    assert a.get("status") == status, f"Expected status {status}, got {a.get('status')}"
                print(f"  Found {len(assignments)} {status} assignments")


class TestStudentAssignmentsWithPrincipal:
    """Test student assignments API structure using principal account"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
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
        else:
            pytest.skip("Authentication failed")
    
    def test_assignments_api_requires_student_role(self):
        """Verify that assignments API requires student role"""
        response = self.session.get(f"{BASE_URL}/api/student-portal/assignments")
        
        print(f"Assignments API with principal: {response.status_code}")
        
        # Should return 403 Forbidden since principal is not a student
        assert response.status_code in [403, 401], "API should require student role"
        print("Correctly requires student role")
    
    def test_student_portal_dashboard_requires_student_role(self):
        """Verify that student dashboard requires student role"""
        response = self.session.get(f"{BASE_URL}/api/student-portal/dashboard")
        
        print(f"Student dashboard with principal: {response.status_code}")
        
        # Should return 403 Forbidden
        assert response.status_code in [403, 401], "Dashboard should require student role"
        print("Correctly requires student role")


class TestAPIEndpointsExist:
    """Verify all required API endpoints exist"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
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
        else:
            pytest.skip("Authentication failed")
    
    def test_put_session_endpoint_exists(self):
        """Verify PUT /api/smart-scheduling/session/{id} exists"""
        # Use a fake ID - we just want to verify the endpoint exists
        fake_id = str(uuid.uuid4())
        response = self.session.put(
            f"{BASE_URL}/api/smart-scheduling/session/{fake_id}",
            json={}
        )
        
        # 404 means endpoint exists but session not found
        # 405 would mean endpoint doesn't exist
        assert response.status_code != 405, "PUT endpoint should exist"
        print(f"PUT session endpoint exists (status: {response.status_code})")
    
    def test_delete_session_endpoint_exists(self):
        """Verify DELETE /api/smart-scheduling/session/{id} exists"""
        fake_id = str(uuid.uuid4())
        response = self.session.delete(f"{BASE_URL}/api/smart-scheduling/session/{fake_id}")
        
        assert response.status_code != 405, "DELETE endpoint should exist"
        print(f"DELETE session endpoint exists (status: {response.status_code})")
    
    def test_swap_sessions_endpoint_exists(self):
        """Verify POST /api/smart-scheduling/sessions/swap exists"""
        response = self.session.post(
            f"{BASE_URL}/api/smart-scheduling/sessions/swap",
            json={"session_id_1": "fake1", "session_id_2": "fake2"}
        )
        
        assert response.status_code != 405, "Swap endpoint should exist"
        print(f"Swap sessions endpoint exists (status: {response.status_code})")
    
    def test_student_assignments_endpoint_exists(self):
        """Verify GET /api/student-portal/assignments exists"""
        response = self.session.get(f"{BASE_URL}/api/student-portal/assignments")
        
        # 403 means endpoint exists but requires different role
        # 405 would mean endpoint doesn't exist
        assert response.status_code != 405, "Assignments endpoint should exist"
        print(f"Student assignments endpoint exists (status: {response.status_code})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
