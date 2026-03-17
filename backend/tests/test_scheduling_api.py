"""
Scheduling Engine API Tests for NASSAQ Platform
Tests for: Time Slots, Teacher Assignments, School Schedules, Schedule Sessions,
Auto-generate Schedule, Conflict Detection, Teacher Rank, Teacher Workload

Test School ID: d3addce7-919b-4f5a-ba0c-0c2dc71599e9
"""

import pytest
import requests
import os
import uuid

# Base URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://school-timetable-ai.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_EMAIL = "info@nassaqapp.com"
TEST_PASSWORD = "NassaqAdmin2026!##$$HBJ"

# Test school ID
TEST_SCHOOL_ID = "d3addce7-919b-4f5a-ba0c-0c2dc71599e9"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for tests"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert "access_token" in data
    return data["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


# ============== TIME SLOTS TESTS ==============
class TestTimeSlots:
    """Time Slots API Tests - الفترات الزمنية"""
    
    def test_get_time_slots_for_school(self, auth_headers):
        """Test GET /api/time-slots - Get time slots for a school"""
        response = requests.get(
            f"{BASE_URL}/api/time-slots",
            params={"school_id": TEST_SCHOOL_ID},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to get time slots: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} time slots for school")
        
        # Verify time slot structure if any exist
        if len(data) > 0:
            slot = data[0]
            assert "id" in slot
            assert "school_id" in slot
            assert "name" in slot
            assert "start_time" in slot
            assert "end_time" in slot
            assert "slot_number" in slot
            print(f"✓ Time slot structure validated: {slot['name']}")
    
    def test_create_time_slot(self, auth_headers):
        """Test POST /api/time-slots - Create a new time slot"""
        unique_id = str(uuid.uuid4())[:8]
        slot_data = {
            "school_id": TEST_SCHOOL_ID,
            "name": f"TEST_حصة اختبار {unique_id}",
            "name_en": f"TEST Period {unique_id}",
            "start_time": "14:00",
            "end_time": "14:45",
            "slot_number": 99,
            "duration_minutes": 45,
            "is_break": False
        }
        
        response = requests.post(
            f"{BASE_URL}/api/time-slots",
            json=slot_data,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to create time slot: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert data["name"] == slot_data["name"]
        assert data["start_time"] == slot_data["start_time"]
        assert data["end_time"] == slot_data["end_time"]
        assert data["is_active"] == True
        print(f"✓ Created time slot: {data['id']}")
        
        # Store for cleanup
        return data["id"]
    
    def test_delete_time_slot(self, auth_headers):
        """Test DELETE /api/time-slots/{slot_id} - Delete a time slot"""
        # First create a slot to delete
        unique_id = str(uuid.uuid4())[:8]
        slot_data = {
            "school_id": TEST_SCHOOL_ID,
            "name": f"TEST_حصة للحذف {unique_id}",
            "name_en": f"TEST Delete Period {unique_id}",
            "start_time": "15:00",
            "end_time": "15:45",
            "slot_number": 100,
            "duration_minutes": 45,
            "is_break": False
        }
        
        create_response = requests.post(
            f"{BASE_URL}/api/time-slots",
            json=slot_data,
            headers=auth_headers
        )
        assert create_response.status_code == 200
        slot_id = create_response.json()["id"]
        
        # Now delete it
        delete_response = requests.delete(
            f"{BASE_URL}/api/time-slots/{slot_id}",
            headers=auth_headers
        )
        assert delete_response.status_code == 200, f"Failed to delete time slot: {delete_response.text}"
        print(f"✓ Deleted time slot: {slot_id}")


# ============== TEACHER ASSIGNMENTS TESTS ==============
class TestTeacherAssignments:
    """Teacher Assignments API Tests - إسناد المعلمين"""
    
    @pytest.fixture(scope="class")
    def test_teacher_id(self, auth_headers):
        """Get a teacher ID for testing"""
        response = requests.get(
            f"{BASE_URL}/api/teachers",
            params={"school_id": TEST_SCHOOL_ID},
            headers=auth_headers
        )
        if response.status_code == 200 and len(response.json()) > 0:
            return response.json()[0]["id"]
        pytest.skip("No teachers found for testing")
    
    @pytest.fixture(scope="class")
    def test_class_id(self, auth_headers):
        """Get a class ID for testing"""
        response = requests.get(
            f"{BASE_URL}/api/classes",
            params={"school_id": TEST_SCHOOL_ID},
            headers=auth_headers
        )
        if response.status_code == 200 and len(response.json()) > 0:
            return response.json()[0]["id"]
        pytest.skip("No classes found for testing")
    
    @pytest.fixture(scope="class")
    def test_subject_id(self, auth_headers):
        """Get a subject ID for testing"""
        response = requests.get(
            f"{BASE_URL}/api/subjects",
            params={"school_id": TEST_SCHOOL_ID},
            headers=auth_headers
        )
        if response.status_code == 200 and len(response.json()) > 0:
            return response.json()[0]["id"]
        pytest.skip("No subjects found for testing")
    
    def test_get_teacher_assignments(self, auth_headers):
        """Test GET /api/teacher-assignments - Get all assignments"""
        response = requests.get(
            f"{BASE_URL}/api/teacher-assignments",
            params={"school_id": TEST_SCHOOL_ID},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to get assignments: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} teacher assignments")
        
        # Verify structure if any exist
        if len(data) > 0:
            assignment = data[0]
            assert "id" in assignment
            assert "teacher_id" in assignment
            assert "class_id" in assignment
            assert "subject_id" in assignment
            assert "weekly_sessions" in assignment
            print(f"✓ Assignment structure validated")
    
    def test_create_teacher_assignment(self, auth_headers, test_teacher_id, test_class_id, test_subject_id):
        """Test POST /api/teacher-assignments - Create a new assignment"""
        assignment_data = {
            "school_id": TEST_SCHOOL_ID,
            "teacher_id": test_teacher_id,
            "class_id": test_class_id,
            "subject_id": test_subject_id,
            "weekly_sessions": 3,
            "academic_year": "2026-2027",
            "semester": 1
        }
        
        response = requests.post(
            f"{BASE_URL}/api/teacher-assignments",
            json=assignment_data,
            headers=auth_headers
        )
        
        # May return 400 if assignment already exists
        if response.status_code == 400:
            print(f"✓ Assignment already exists (expected behavior)")
            return
        
        assert response.status_code == 200, f"Failed to create assignment: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert data["teacher_id"] == test_teacher_id
        assert data["class_id"] == test_class_id
        assert data["subject_id"] == test_subject_id
        assert data["weekly_sessions"] == 3
        print(f"✓ Created teacher assignment: {data['id']}")
    
    def test_delete_teacher_assignment(self, auth_headers, test_teacher_id, test_class_id, test_subject_id):
        """Test DELETE /api/teacher-assignments/{assignment_id} - Delete an assignment"""
        # First get existing assignments
        response = requests.get(
            f"{BASE_URL}/api/teacher-assignments",
            params={"school_id": TEST_SCHOOL_ID},
            headers=auth_headers
        )
        
        if response.status_code == 200 and len(response.json()) > 0:
            # Find a TEST_ prefixed assignment or use the last one
            assignments = response.json()
            assignment_id = assignments[-1]["id"]
            
            delete_response = requests.delete(
                f"{BASE_URL}/api/teacher-assignments/{assignment_id}",
                headers=auth_headers
            )
            assert delete_response.status_code == 200, f"Failed to delete assignment: {delete_response.text}"
            print(f"✓ Deleted teacher assignment: {assignment_id}")
        else:
            print("✓ No assignments to delete (skipped)")


# ============== SCHOOL SCHEDULES TESTS ==============
class TestSchoolSchedules:
    """School Schedules API Tests - الجداول المدرسية"""
    
    created_schedule_id = None
    
    def test_get_schedules(self, auth_headers):
        """Test GET /api/schedules - Get all schedules"""
        response = requests.get(
            f"{BASE_URL}/api/schedules",
            params={"school_id": TEST_SCHOOL_ID},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to get schedules: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} schedules")
        
        # Verify structure if any exist
        if len(data) > 0:
            schedule = data[0]
            assert "id" in schedule
            assert "school_id" in schedule
            assert "name" in schedule
            assert "status" in schedule
            assert "working_days" in schedule
            print(f"✓ Schedule structure validated: {schedule['name']}")
    
    def test_create_schedule(self, auth_headers):
        """Test POST /api/schedules - Create a new schedule"""
        unique_id = str(uuid.uuid4())[:8]
        schedule_data = {
            "school_id": TEST_SCHOOL_ID,
            "name": f"TEST_جدول اختبار {unique_id}",
            "name_en": f"TEST Schedule {unique_id}",
            "academic_year": "2026-2027",
            "semester": 1,
            "effective_from": "2026-09-01",
            "effective_to": "2027-01-15",
            "working_days": ["sunday", "monday", "tuesday", "wednesday", "thursday"]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/schedules",
            json=schedule_data,
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to create schedule: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert data["name"] == schedule_data["name"]
        assert data["status"] == "draft"
        assert data["total_sessions"] == 0
        print(f"✓ Created schedule: {data['id']}")
        
        # Store for other tests
        TestSchoolSchedules.created_schedule_id = data["id"]
        return data["id"]
    
    def test_get_schedule_by_id(self, auth_headers):
        """Test GET /api/schedules/{schedule_id} - Get specific schedule"""
        if not TestSchoolSchedules.created_schedule_id:
            pytest.skip("No schedule created yet")
        
        response = requests.get(
            f"{BASE_URL}/api/schedules/{TestSchoolSchedules.created_schedule_id}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to get schedule: {response.text}"
        data = response.json()
        
        assert data["id"] == TestSchoolSchedules.created_schedule_id
        print(f"✓ Retrieved schedule by ID: {data['name']}")
    
    def test_publish_schedule(self, auth_headers):
        """Test PUT /api/schedules/{schedule_id}/publish - Publish a schedule"""
        if not TestSchoolSchedules.created_schedule_id:
            pytest.skip("No schedule created yet")
        
        response = requests.put(
            f"{BASE_URL}/api/schedules/{TestSchoolSchedules.created_schedule_id}/publish",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to publish schedule: {response.text}"
        print(f"✓ Published schedule: {TestSchoolSchedules.created_schedule_id}")
        
        # Verify status changed
        get_response = requests.get(
            f"{BASE_URL}/api/schedules/{TestSchoolSchedules.created_schedule_id}",
            headers=auth_headers
        )
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "published"
        print(f"✓ Verified schedule status is 'published'")
    
    def test_delete_schedule(self, auth_headers):
        """Test DELETE /api/schedules/{schedule_id} - Archive a schedule"""
        if not TestSchoolSchedules.created_schedule_id:
            pytest.skip("No schedule created yet")
        
        response = requests.delete(
            f"{BASE_URL}/api/schedules/{TestSchoolSchedules.created_schedule_id}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to delete schedule: {response.text}"
        print(f"✓ Archived schedule: {TestSchoolSchedules.created_schedule_id}")


# ============== SCHEDULE SESSIONS TESTS ==============
class TestScheduleSessions:
    """Schedule Sessions API Tests - حصص الجدول"""
    
    test_schedule_id = None
    test_assignment_id = None
    test_time_slot_id = None
    created_session_id = None
    
    @pytest.fixture(scope="class", autouse=True)
    def setup_test_data(self, auth_headers):
        """Setup test data for session tests"""
        # Create a test schedule
        unique_id = str(uuid.uuid4())[:8]
        schedule_data = {
            "school_id": TEST_SCHOOL_ID,
            "name": f"TEST_جدول حصص {unique_id}",
            "name_en": f"TEST Session Schedule {unique_id}",
            "academic_year": "2026-2027",
            "semester": 1,
            "effective_from": "2026-09-01",
            "working_days": ["sunday", "monday", "tuesday", "wednesday", "thursday"]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/schedules",
            json=schedule_data,
            headers=auth_headers
        )
        if response.status_code == 200:
            TestScheduleSessions.test_schedule_id = response.json()["id"]
            print(f"✓ Created test schedule: {TestScheduleSessions.test_schedule_id}")
        
        # Get a time slot
        slots_response = requests.get(
            f"{BASE_URL}/api/time-slots",
            params={"school_id": TEST_SCHOOL_ID},
            headers=auth_headers
        )
        if slots_response.status_code == 200 and len(slots_response.json()) > 0:
            TestScheduleSessions.test_time_slot_id = slots_response.json()[0]["id"]
        
        # Get an assignment
        assignments_response = requests.get(
            f"{BASE_URL}/api/teacher-assignments",
            params={"school_id": TEST_SCHOOL_ID},
            headers=auth_headers
        )
        if assignments_response.status_code == 200 and len(assignments_response.json()) > 0:
            TestScheduleSessions.test_assignment_id = assignments_response.json()[0]["id"]
        
        yield
        
        # Cleanup - delete the test schedule
        if TestScheduleSessions.test_schedule_id:
            requests.delete(
                f"{BASE_URL}/api/schedules/{TestScheduleSessions.test_schedule_id}",
                headers=auth_headers
            )
    
    def test_create_schedule_session(self, auth_headers):
        """Test POST /api/schedule-sessions - Create a session"""
        if not all([TestScheduleSessions.test_schedule_id, 
                    TestScheduleSessions.test_assignment_id,
                    TestScheduleSessions.test_time_slot_id]):
            pytest.skip("Missing test data for session creation")
        
        session_data = {
            "school_id": TEST_SCHOOL_ID,
            "schedule_id": TestScheduleSessions.test_schedule_id,
            "assignment_id": TestScheduleSessions.test_assignment_id,
            "day_of_week": "sunday",
            "time_slot_id": TestScheduleSessions.test_time_slot_id,
            "room_id": None
        }
        
        response = requests.post(
            f"{BASE_URL}/api/schedule-sessions",
            json=session_data,
            headers=auth_headers
        )
        
        # May return 400 if session already exists
        if response.status_code == 400:
            print(f"✓ Session already exists (expected behavior)")
            return
        
        assert response.status_code == 200, f"Failed to create session: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert data["schedule_id"] == TestScheduleSessions.test_schedule_id
        assert data["day_of_week"] == "sunday"
        assert data["status"] == "scheduled"
        print(f"✓ Created schedule session: {data['id']}")
        
        TestScheduleSessions.created_session_id = data["id"]
    
    def test_get_schedule_sessions(self, auth_headers):
        """Test GET /api/schedule-sessions - Get sessions for a schedule"""
        if not TestScheduleSessions.test_schedule_id:
            pytest.skip("No test schedule available")
        
        response = requests.get(
            f"{BASE_URL}/api/schedule-sessions",
            params={"schedule_id": TestScheduleSessions.test_schedule_id},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to get sessions: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Found {len(data)} sessions in schedule")
        
        # Verify structure if any exist
        if len(data) > 0:
            session = data[0]
            assert "id" in session
            assert "schedule_id" in session
            assert "day_of_week" in session
            assert "time_slot_id" in session
            print(f"✓ Session structure validated")
    
    def test_get_sessions_by_day(self, auth_headers):
        """Test GET /api/schedule-sessions with day filter"""
        if not TestScheduleSessions.test_schedule_id:
            pytest.skip("No test schedule available")
        
        response = requests.get(
            f"{BASE_URL}/api/schedule-sessions",
            params={
                "schedule_id": TestScheduleSessions.test_schedule_id,
                "day_of_week": "sunday"
            },
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to get sessions by day: {response.text}"
        data = response.json()
        
        # All returned sessions should be for Sunday
        for session in data:
            assert session["day_of_week"] == "sunday"
        print(f"✓ Found {len(data)} sessions for Sunday")
    
    def test_delete_schedule_session(self, auth_headers):
        """Test DELETE /api/schedule-sessions/{session_id} - Delete a session"""
        if not TestScheduleSessions.created_session_id:
            pytest.skip("No session created to delete")
        
        response = requests.delete(
            f"{BASE_URL}/api/schedule-sessions/{TestScheduleSessions.created_session_id}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to delete session: {response.text}"
        print(f"✓ Deleted schedule session: {TestScheduleSessions.created_session_id}")


# ============== AUTO-GENERATE SCHEDULE TESTS ==============
class TestAutoGenerateSchedule:
    """Auto-generate Schedule API Tests - توليد الجدول تلقائياً"""
    
    test_schedule_id = None
    
    @pytest.fixture(scope="class", autouse=True)
    def setup_schedule(self, auth_headers):
        """Create a schedule for auto-generation testing"""
        unique_id = str(uuid.uuid4())[:8]
        schedule_data = {
            "school_id": TEST_SCHOOL_ID,
            "name": f"TEST_جدول توليد تلقائي {unique_id}",
            "name_en": f"TEST Auto-gen Schedule {unique_id}",
            "academic_year": "2026-2027",
            "semester": 1,
            "effective_from": "2026-09-01",
            "working_days": ["sunday", "monday", "tuesday", "wednesday", "thursday"]
        }
        
        response = requests.post(
            f"{BASE_URL}/api/schedules",
            json=schedule_data,
            headers=auth_headers
        )
        if response.status_code == 200:
            TestAutoGenerateSchedule.test_schedule_id = response.json()["id"]
            print(f"✓ Created schedule for auto-generation: {TestAutoGenerateSchedule.test_schedule_id}")
        
        yield
        
        # Cleanup
        if TestAutoGenerateSchedule.test_schedule_id:
            requests.delete(
                f"{BASE_URL}/api/schedules/{TestAutoGenerateSchedule.test_schedule_id}",
                headers=auth_headers
            )
    
    def test_auto_generate_schedule(self, auth_headers):
        """Test POST /api/schedules/{schedule_id}/generate - Auto-generate schedule"""
        if not TestAutoGenerateSchedule.test_schedule_id:
            pytest.skip("No schedule available for auto-generation")
        
        response = requests.post(
            f"{BASE_URL}/api/schedules/{TestAutoGenerateSchedule.test_schedule_id}/generate",
            params={"respect_workload": True, "max_iterations": 100},
            headers=auth_headers
        )
        
        # May return 400 if no assignments exist
        if response.status_code == 400:
            print(f"✓ No assignments to generate schedule (expected if no data)")
            return
        
        assert response.status_code == 200, f"Failed to generate schedule: {response.text}"
        data = response.json()
        
        assert "success" in data
        assert "schedule_id" in data
        assert "sessions_created" in data
        print(f"✓ Auto-generated schedule: {data['sessions_created']} sessions created")
        print(f"  Success: {data['success']}, Unplaced: {data.get('unplaced_sessions', 0)}")


# ============== CONFLICT DETECTION TESTS ==============
class TestConflictDetection:
    """Conflict Detection API Tests - اكتشاف التعارضات"""
    
    def test_check_schedule_conflicts(self, auth_headers):
        """Test GET /api/schedules/{schedule_id}/conflicts - Check for conflicts"""
        # First get an existing schedule
        schedules_response = requests.get(
            f"{BASE_URL}/api/schedules",
            params={"school_id": TEST_SCHOOL_ID},
            headers=auth_headers
        )
        
        if schedules_response.status_code != 200 or len(schedules_response.json()) == 0:
            pytest.skip("No schedules available for conflict check")
        
        schedule_id = schedules_response.json()[0]["id"]
        
        response = requests.get(
            f"{BASE_URL}/api/schedules/{schedule_id}/conflicts",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to check conflicts: {response.text}"
        data = response.json()
        
        assert "schedule_id" in data
        assert "total_conflicts" in data
        assert "conflicts" in data
        assert isinstance(data["conflicts"], list)
        print(f"✓ Conflict check completed: {data['total_conflicts']} conflicts found")
        
        # Verify conflict structure if any exist
        if len(data["conflicts"]) > 0:
            conflict = data["conflicts"][0]
            assert "type" in conflict
            assert "day" in conflict
            assert "time_slot_id" in conflict
            print(f"  Conflict type: {conflict['type']}")


# ============== TEACHER RANK TESTS ==============
class TestTeacherRank:
    """Teacher Rank API Tests - رتب المعلمين"""
    
    test_teacher_id = None
    original_rank = None
    
    @pytest.fixture(scope="class", autouse=True)
    def setup_teacher(self, auth_headers):
        """Get a teacher for rank testing"""
        response = requests.get(
            f"{BASE_URL}/api/teachers",
            params={"school_id": TEST_SCHOOL_ID},
            headers=auth_headers
        )
        if response.status_code == 200 and len(response.json()) > 0:
            TestTeacherRank.test_teacher_id = response.json()[0]["id"]
            TestTeacherRank.original_rank = response.json()[0].get("rank", "practitioner")
            print(f"✓ Using teacher for rank tests: {TestTeacherRank.test_teacher_id}")
        
        yield
        
        # Restore original rank
        if TestTeacherRank.test_teacher_id and TestTeacherRank.original_rank:
            requests.put(
                f"{BASE_URL}/api/teachers/{TestTeacherRank.test_teacher_id}/rank",
                params={"rank": TestTeacherRank.original_rank},
                headers=auth_headers
            )
    
    def test_update_teacher_rank_expert(self, auth_headers):
        """Test PUT /api/teachers/{teacher_id}/rank - Update to expert"""
        if not TestTeacherRank.test_teacher_id:
            pytest.skip("No teacher available for rank update")
        
        response = requests.put(
            f"{BASE_URL}/api/teachers/{TestTeacherRank.test_teacher_id}/rank",
            params={"rank": "expert"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to update rank: {response.text}"
        print(f"✓ Updated teacher rank to 'expert'")
    
    def test_update_teacher_rank_advanced(self, auth_headers):
        """Test PUT /api/teachers/{teacher_id}/rank - Update to advanced"""
        if not TestTeacherRank.test_teacher_id:
            pytest.skip("No teacher available for rank update")
        
        response = requests.put(
            f"{BASE_URL}/api/teachers/{TestTeacherRank.test_teacher_id}/rank",
            params={"rank": "advanced"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to update rank: {response.text}"
        print(f"✓ Updated teacher rank to 'advanced'")
    
    def test_update_teacher_rank_practitioner(self, auth_headers):
        """Test PUT /api/teachers/{teacher_id}/rank - Update to practitioner"""
        if not TestTeacherRank.test_teacher_id:
            pytest.skip("No teacher available for rank update")
        
        response = requests.put(
            f"{BASE_URL}/api/teachers/{TestTeacherRank.test_teacher_id}/rank",
            params={"rank": "practitioner"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to update rank: {response.text}"
        print(f"✓ Updated teacher rank to 'practitioner'")
    
    def test_update_teacher_rank_assistant(self, auth_headers):
        """Test PUT /api/teachers/{teacher_id}/rank - Update to assistant"""
        if not TestTeacherRank.test_teacher_id:
            pytest.skip("No teacher available for rank update")
        
        response = requests.put(
            f"{BASE_URL}/api/teachers/{TestTeacherRank.test_teacher_id}/rank",
            params={"rank": "assistant"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to update rank: {response.text}"
        print(f"✓ Updated teacher rank to 'assistant'")
    
    def test_update_rank_invalid_teacher(self, auth_headers):
        """Test PUT /api/teachers/{teacher_id}/rank - Invalid teacher ID"""
        response = requests.put(
            f"{BASE_URL}/api/teachers/invalid-teacher-id/rank",
            params={"rank": "expert"},
            headers=auth_headers
        )
        assert response.status_code == 404, f"Expected 404 for invalid teacher: {response.text}"
        print(f"✓ Correctly returned 404 for invalid teacher ID")


# ============== TEACHER WORKLOAD TESTS ==============
class TestTeacherWorkload:
    """Teacher Workload API Tests - نصاب المعلم"""
    
    def test_get_teacher_workload(self, auth_headers):
        """Test GET /api/teachers/{teacher_id}/workload - Get workload"""
        # Get a teacher
        teachers_response = requests.get(
            f"{BASE_URL}/api/teachers",
            params={"school_id": TEST_SCHOOL_ID},
            headers=auth_headers
        )
        
        if teachers_response.status_code != 200 or len(teachers_response.json()) == 0:
            pytest.skip("No teachers available for workload test")
        
        teacher_id = teachers_response.json()[0]["id"]
        
        response = requests.get(
            f"{BASE_URL}/api/teachers/{teacher_id}/workload",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to get workload: {response.text}"
        data = response.json()
        
        assert "teacher_id" in data
        assert "teacher_name" in data
        assert "rank" in data
        assert "weekly_hours_min" in data
        assert "weekly_hours_max" in data
        assert "daily_sessions_max" in data
        assert "total_assigned_sessions" in data
        assert "is_overloaded" in data
        assert "is_underloaded" in data
        
        print(f"✓ Teacher workload retrieved:")
        print(f"  Name: {data['teacher_name']}")
        print(f"  Rank: {data['rank']}")
        print(f"  Weekly limits: {data['weekly_hours_min']}-{data['weekly_hours_max']}")
        print(f"  Assigned sessions: {data['total_assigned_sessions']}")
        print(f"  Overloaded: {data['is_overloaded']}, Underloaded: {data['is_underloaded']}")
    
    def test_get_workload_with_schedule(self, auth_headers):
        """Test GET /api/teachers/{teacher_id}/workload with schedule_id"""
        # Get a teacher
        teachers_response = requests.get(
            f"{BASE_URL}/api/teachers",
            params={"school_id": TEST_SCHOOL_ID},
            headers=auth_headers
        )
        
        if teachers_response.status_code != 200 or len(teachers_response.json()) == 0:
            pytest.skip("No teachers available")
        
        teacher_id = teachers_response.json()[0]["id"]
        
        # Get a schedule
        schedules_response = requests.get(
            f"{BASE_URL}/api/schedules",
            params={"school_id": TEST_SCHOOL_ID},
            headers=auth_headers
        )
        
        if schedules_response.status_code != 200 or len(schedules_response.json()) == 0:
            pytest.skip("No schedules available")
        
        schedule_id = schedules_response.json()[0]["id"]
        
        response = requests.get(
            f"{BASE_URL}/api/teachers/{teacher_id}/workload",
            params={"schedule_id": schedule_id},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to get workload with schedule: {response.text}"
        data = response.json()
        
        assert "actual_scheduled_sessions" in data
        assert "sessions_by_day" in data
        print(f"✓ Workload with schedule: {data['actual_scheduled_sessions']} actual sessions")
    
    def test_workload_invalid_teacher(self, auth_headers):
        """Test GET /api/teachers/{teacher_id}/workload - Invalid teacher"""
        response = requests.get(
            f"{BASE_URL}/api/teachers/invalid-teacher-id/workload",
            headers=auth_headers
        )
        assert response.status_code == 404, f"Expected 404 for invalid teacher: {response.text}"
        print(f"✓ Correctly returned 404 for invalid teacher ID")


# ============== SEED TIME SLOTS TEST ==============
class TestSeedTimeSlots:
    """Seed Time Slots API Test - إنشاء الفترات الزمنية الافتراضية"""
    
    def test_seed_time_slots(self, auth_headers):
        """Test POST /api/seed/time-slots/{school_id} - Seed default time slots"""
        response = requests.post(
            f"{BASE_URL}/api/seed/time-slots/{TEST_SCHOOL_ID}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to seed time slots: {response.text}"
        data = response.json()
        
        assert "message" in data
        assert "count" in data
        print(f"✓ Seed time slots: {data['message']}, count: {data['count']}")


# ============== ERROR HANDLING TESTS ==============
class TestErrorHandling:
    """Error Handling Tests - اختبارات معالجة الأخطاء"""
    
    def test_get_nonexistent_schedule(self, auth_headers):
        """Test GET /api/schedules/{schedule_id} - Non-existent schedule"""
        response = requests.get(
            f"{BASE_URL}/api/schedules/nonexistent-schedule-id",
            headers=auth_headers
        )
        assert response.status_code == 404, f"Expected 404: {response.text}"
        print(f"✓ Correctly returned 404 for non-existent schedule")
    
    def test_delete_nonexistent_time_slot(self, auth_headers):
        """Test DELETE /api/time-slots/{slot_id} - Non-existent slot"""
        response = requests.delete(
            f"{BASE_URL}/api/time-slots/nonexistent-slot-id",
            headers=auth_headers
        )
        assert response.status_code == 404, f"Expected 404: {response.text}"
        print(f"✓ Correctly returned 404 for non-existent time slot")
    
    def test_unauthorized_access(self):
        """Test API access without authentication"""
        response = requests.get(
            f"{BASE_URL}/api/schedules",
            params={"school_id": TEST_SCHOOL_ID}
        )
        assert response.status_code == 403, f"Expected 403 for unauthorized: {response.text}"
        print(f"✓ Correctly returned 403 for unauthorized access")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
