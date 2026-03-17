"""
Test Suite for NASSAQ School Management System - Iteration 66
Tests for:
1. Subjects CRUD APIs (POST/PUT/DELETE /api/school/subjects)
2. Constraints CRUD APIs (POST/PUT/DELETE /api/school/constraints)
3. Active Role Context APIs (GET/POST /api/auth/active-role)
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
PRINCIPAL_EMAIL = "principal1@nassaq.com"
PRINCIPAL_PASSWORD = "Principal@123"
ADMIN_EMAIL = "admin@nassaq.com"
ADMIN_PASSWORD = "Admin@123"


class TestAuthentication:
    """Authentication tests"""
    
    def test_principal_login(self):
        """Test school principal login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "school_principal"
        print(f"✓ Principal login successful: {data['user']['full_name']}")
    
    def test_admin_login(self):
        """Test platform admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "platform_admin"
        print(f"✓ Admin login successful: {data['user']['full_name']}")


@pytest.fixture
def principal_token():
    """Get principal auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": PRINCIPAL_EMAIL,
        "password": PRINCIPAL_PASSWORD
    })
    if response.status_code == 200:
        return response.json()["access_token"]
    pytest.skip("Principal authentication failed")


@pytest.fixture
def admin_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json()["access_token"]
    pytest.skip("Admin authentication failed")


@pytest.fixture
def principal_headers(principal_token):
    """Get headers with principal auth"""
    return {
        "Authorization": f"Bearer {principal_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture
def admin_headers(admin_token):
    """Get headers with admin auth"""
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }


class TestActiveRoleContext:
    """Tests for Active Role Context APIs"""
    
    def test_get_active_role_principal(self, principal_headers):
        """Test GET /api/auth/active-role for principal"""
        response = requests.get(
            f"{BASE_URL}/api/auth/active-role",
            headers=principal_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "user_identity_id" in data
        assert "role_id" in data
        assert "role_name" in data
        assert data["role_id"] == "school_principal"
        assert data["role_name"] == "مدير المدرسة"
        print(f"✓ Active role for principal: {data['role_name']}")
    
    def test_get_active_role_admin(self, admin_headers):
        """Test GET /api/auth/active-role for admin"""
        response = requests.get(
            f"{BASE_URL}/api/auth/active-role",
            headers=admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "role_id" in data
        assert data["role_id"] == "platform_admin"
        assert data["role_name"] == "مدير المنصة"
        print(f"✓ Active role for admin: {data['role_name']}")
    
    def test_set_active_role(self, principal_headers):
        """Test POST /api/auth/set-active-role"""
        response = requests.post(
            f"{BASE_URL}/api/auth/set-active-role",
            headers=principal_headers,
            json={
                "role_id": "school_principal",
                "school_id": "SCH-001"
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert data["role_id"] == "school_principal"
        assert data["is_active"] == True
        print(f"✓ Set active role successful: {data['role_name']}")


class TestSubjectsCRUD:
    """Tests for Subjects CRUD APIs"""
    
    created_subject_id = None
    
    def test_get_school_subjects(self, principal_headers):
        """Test GET /api/school/subjects"""
        response = requests.get(
            f"{BASE_URL}/api/school/subjects",
            headers=principal_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list)
        print(f"✓ Got {len(data)} subjects")
    
    def test_create_subject(self, principal_headers):
        """Test POST /api/school/subjects - إضافة مادة جديدة"""
        unique_id = str(uuid.uuid4())[:8]
        subject_data = {
            "name_ar": f"TEST_مادة اختبار {unique_id}",
            "name_en": f"TEST_Test Subject {unique_id}",
            "weekly_periods": 4,
            "category": "science",
            "description": "مادة اختبار للتحقق من API"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/school/subjects",
            headers=principal_headers,
            json=subject_data
        )
        assert response.status_code == 200, f"Failed to create subject: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert "message" in data
        assert data["message"] == "تم إضافة المادة بنجاح"
        
        # Store for later tests
        TestSubjectsCRUD.created_subject_id = data["id"]
        print(f"✓ Created subject: {data['id']}")
        
        # Verify by GET
        get_response = requests.get(
            f"{BASE_URL}/api/school/subjects",
            headers=principal_headers
        )
        subjects = get_response.json()
        created = next((s for s in subjects if s["id"] == data["id"]), None)
        assert created is not None, "Created subject not found in list"
        assert created["name_ar"] == subject_data["name_ar"]
        print(f"✓ Verified subject creation via GET")
    
    def test_update_subject(self, principal_headers):
        """Test PUT /api/school/subjects/{id} - تعديل مادة"""
        if not TestSubjectsCRUD.created_subject_id:
            pytest.skip("No subject created to update")
        
        subject_id = TestSubjectsCRUD.created_subject_id
        update_data = {
            "name_ar": "TEST_مادة معدلة",
            "weekly_periods": 6,
            "category": "language"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/school/subjects/{subject_id}",
            headers=principal_headers,
            json=update_data
        )
        assert response.status_code == 200, f"Failed to update subject: {response.text}"
        data = response.json()
        
        assert data["message"] == "تم تحديث المادة بنجاح"
        print(f"✓ Updated subject: {subject_id}")
        
        # Verify update via GET
        get_response = requests.get(
            f"{BASE_URL}/api/school/subjects",
            headers=principal_headers
        )
        subjects = get_response.json()
        updated = next((s for s in subjects if s["id"] == subject_id), None)
        assert updated is not None, "Updated subject not found"
        assert updated["name_ar"] == update_data["name_ar"]
        assert updated["weekly_periods"] == update_data["weekly_periods"]
        print(f"✓ Verified subject update via GET")
    
    def test_delete_subject(self, principal_headers):
        """Test DELETE /api/school/subjects/{id} - حذف مادة"""
        if not TestSubjectsCRUD.created_subject_id:
            pytest.skip("No subject created to delete")
        
        subject_id = TestSubjectsCRUD.created_subject_id
        
        response = requests.delete(
            f"{BASE_URL}/api/school/subjects/{subject_id}",
            headers=principal_headers
        )
        assert response.status_code == 200, f"Failed to delete subject: {response.text}"
        data = response.json()
        
        assert data["message"] == "تم حذف المادة بنجاح"
        print(f"✓ Deleted subject: {subject_id}")
        
        # Verify deletion (soft delete - should not appear in active list)
        get_response = requests.get(
            f"{BASE_URL}/api/school/subjects",
            headers=principal_headers
        )
        subjects = get_response.json()
        deleted = next((s for s in subjects if s["id"] == subject_id), None)
        assert deleted is None, "Deleted subject still appears in active list"
        print(f"✓ Verified subject deletion via GET")


class TestConstraintsCRUD:
    """Tests for Admin Constraints CRUD APIs"""
    
    created_constraint_id = None
    
    def test_get_school_constraints(self, principal_headers):
        """Test GET /api/school/constraints"""
        response = requests.get(
            f"{BASE_URL}/api/school/constraints",
            headers=principal_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list)
        print(f"✓ Got {len(data)} constraints")
    
    def test_create_constraint(self, principal_headers):
        """Test POST /api/school/constraints - إضافة قيد جديد"""
        unique_id = str(uuid.uuid4())[:8]
        constraint_data = {
            "name_ar": f"TEST_قيد اختبار {unique_id}",
            "name_en": f"TEST_Test Constraint {unique_id}",
            "description_ar": "قيد اختبار للتحقق من API",
            "type": "hard",
            "priority": "high",
            "restricted_periods": [1, 7],
            "max_consecutive_periods": 3
        }
        
        response = requests.post(
            f"{BASE_URL}/api/school/constraints",
            headers=principal_headers,
            json=constraint_data
        )
        assert response.status_code == 200, f"Failed to create constraint: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert "message" in data
        assert data["message"] == "تم إضافة القيد بنجاح"
        
        # Store for later tests
        TestConstraintsCRUD.created_constraint_id = data["id"]
        print(f"✓ Created constraint: {data['id']}")
        
        # Verify by GET
        get_response = requests.get(
            f"{BASE_URL}/api/school/constraints",
            headers=principal_headers
        )
        constraints = get_response.json()
        created = next((c for c in constraints if c["id"] == data["id"]), None)
        assert created is not None, "Created constraint not found in list"
        assert created["name_ar"] == constraint_data["name_ar"]
        print(f"✓ Verified constraint creation via GET")
    
    def test_update_constraint(self, principal_headers):
        """Test PUT /api/school/constraints/{id} - تعديل قيد"""
        if not TestConstraintsCRUD.created_constraint_id:
            pytest.skip("No constraint created to update")
        
        constraint_id = TestConstraintsCRUD.created_constraint_id
        update_data = {
            "name_ar": "TEST_قيد معدل",
            "priority": "critical",
            "is_active": True
        }
        
        response = requests.put(
            f"{BASE_URL}/api/school/constraints/{constraint_id}",
            headers=principal_headers,
            json=update_data
        )
        assert response.status_code == 200, f"Failed to update constraint: {response.text}"
        data = response.json()
        
        assert data["message"] == "تم تحديث القيد بنجاح"
        print(f"✓ Updated constraint: {constraint_id}")
        
        # Verify update via GET
        get_response = requests.get(
            f"{BASE_URL}/api/school/constraints",
            headers=principal_headers
        )
        constraints = get_response.json()
        updated = next((c for c in constraints if c["id"] == constraint_id), None)
        assert updated is not None, "Updated constraint not found"
        assert updated["name_ar"] == update_data["name_ar"]
        assert updated["priority"] == update_data["priority"]
        print(f"✓ Verified constraint update via GET")
    
    def test_toggle_constraint_active(self, principal_headers):
        """Test toggling constraint is_active status"""
        if not TestConstraintsCRUD.created_constraint_id:
            pytest.skip("No constraint created to toggle")
        
        constraint_id = TestConstraintsCRUD.created_constraint_id
        
        # Deactivate
        response = requests.put(
            f"{BASE_URL}/api/school/constraints/{constraint_id}",
            headers=principal_headers,
            json={"is_active": False}
        )
        assert response.status_code == 200, f"Failed to deactivate: {response.text}"
        print(f"✓ Deactivated constraint")
        
        # Reactivate
        response = requests.put(
            f"{BASE_URL}/api/school/constraints/{constraint_id}",
            headers=principal_headers,
            json={"is_active": True}
        )
        assert response.status_code == 200, f"Failed to reactivate: {response.text}"
        print(f"✓ Reactivated constraint")
    
    def test_delete_constraint(self, principal_headers):
        """Test DELETE /api/school/constraints/{id} - حذف قيد"""
        if not TestConstraintsCRUD.created_constraint_id:
            pytest.skip("No constraint created to delete")
        
        constraint_id = TestConstraintsCRUD.created_constraint_id
        
        response = requests.delete(
            f"{BASE_URL}/api/school/constraints/{constraint_id}",
            headers=principal_headers
        )
        assert response.status_code == 200, f"Failed to delete constraint: {response.text}"
        data = response.json()
        
        assert data["message"] == "تم حذف القيد بنجاح"
        print(f"✓ Deleted constraint: {constraint_id}")


class TestReferenceAPIs:
    """Tests for reference data APIs used by settings page"""
    
    def test_get_reference_subjects(self, principal_headers):
        """Test GET /api/reference/subjects"""
        response = requests.get(
            f"{BASE_URL}/api/reference/subjects",
            headers=principal_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Got {len(data)} reference subjects")
    
    def test_get_reference_admin_constraints(self, principal_headers):
        """Test GET /api/reference/admin-constraints"""
        response = requests.get(
            f"{BASE_URL}/api/reference/admin-constraints",
            headers=principal_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Got {len(data)} reference admin constraints")
    
    def test_get_school_settings(self, principal_headers):
        """Test GET /api/school/settings"""
        response = requests.get(
            f"{BASE_URL}/api/school/settings",
            headers=principal_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify time_slots are present
        assert "time_slots" in data or "settings" in data
        print(f"✓ Got school settings")
    
    def test_get_time_slots(self, principal_headers):
        """Test GET /api/time-slots - verify time slots for schedule page"""
        response = requests.get(
            f"{BASE_URL}/api/time-slots",
            headers=principal_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list)
        if len(data) > 0:
            slot = data[0]
            # Verify slot structure
            assert "start_time" in slot or "slot_number" in slot
        print(f"✓ Got {len(data)} time slots")


class TestSchedulePageAPIs:
    """Tests for Schedule Page related APIs"""
    
    def test_get_schedule_sessions(self, principal_headers):
        """Test GET /api/schedule-sessions - requires schedule_id"""
        # First get schedules to find a valid schedule_id
        schedules_response = requests.get(
            f"{BASE_URL}/api/schedules",
            headers=principal_headers
        )
        if schedules_response.status_code != 200:
            pytest.skip("Could not get schedules")
        
        schedules = schedules_response.json()
        if not schedules:
            pytest.skip("No schedules available")
        
        schedule_id = schedules[0].get("id")
        
        response = requests.get(
            f"{BASE_URL}/api/schedule-sessions?schedule_id={schedule_id}",
            headers=principal_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list)
        if len(data) > 0:
            session = data[0]
            # Verify session has required fields
            assert "teacher_name" in session or "subject_name" in session
        print(f"✓ Got {len(data)} schedule sessions")
    
    def test_get_teachers(self, principal_headers):
        """Test GET /api/teachers"""
        response = requests.get(
            f"{BASE_URL}/api/teachers",
            headers=principal_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list)
        print(f"✓ Got {len(data)} teachers")
    
    def test_get_classes(self, principal_headers):
        """Test GET /api/classes"""
        response = requests.get(
            f"{BASE_URL}/api/classes",
            headers=principal_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list)
        print(f"✓ Got {len(data)} classes")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
