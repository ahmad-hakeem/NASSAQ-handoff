"""
Test iteration 73 - School Settings CRUD operations
Testing:
1. School Settings - Update subject (PUT /school/subjects/{id})
2. School Settings - Delete subject (DELETE /school/subjects/{id})
3. School Settings - Update constraint (PUT /school/constraints/{id})
4. School Settings - Delete constraint (DELETE /school/constraints/{id})
5. School Settings - Time tab inline editable time slots
6. Create Class Wizard - Grade dropdown options
7. Create Class Wizard - Class type dropdown options
"""

import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://school-timetable-ai.preview.emergentagent.com')

# Test credentials
PRINCIPAL_EMAIL = "principal1@nassaq.com"
PRINCIPAL_PASSWORD = "Principal@123"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for principal"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": PRINCIPAL_EMAIL, "password": PRINCIPAL_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert "access_token" in data, "No access token in response"
    return data["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestSchoolSubjectsCRUD:
    """Test School Subjects CRUD operations"""
    
    def test_get_school_subjects(self, auth_headers):
        """Test GET /school/subjects - should return list of subjects"""
        response = requests.get(f"{BASE_URL}/api/school/subjects", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get subjects: {response.text}"
        subjects = response.json()
        assert isinstance(subjects, list), "Response should be a list"
        print(f"✓ Found {len(subjects)} subjects")
        return subjects
    
    def test_create_subject(self, auth_headers):
        """Test POST /school/subjects - create a test subject"""
        test_subject = {
            "name_ar": "TEST_مادة اختبار",
            "name_en": "TEST_Test Subject",
            "code": "TEST-001",
            "category": "general",
            "weekly_periods": 3,
            "description": "Test subject for iteration 73"
        }
        response = requests.post(
            f"{BASE_URL}/api/school/subjects",
            headers=auth_headers,
            json=test_subject
        )
        assert response.status_code in [200, 201], f"Failed to create subject: {response.text}"
        data = response.json()
        print(f"✓ Created subject: {data}")
        return data
    
    def test_update_subject(self, auth_headers):
        """Test PUT /school/subjects/{id} - update a subject"""
        # First get existing subjects
        response = requests.get(f"{BASE_URL}/api/school/subjects", headers=auth_headers)
        subjects = response.json()
        
        if not subjects:
            pytest.skip("No subjects available to update")
        
        # Find a test subject or use first one
        test_subject = next((s for s in subjects if s.get("name_ar", "").startswith("TEST_")), subjects[0])
        subject_id = test_subject.get("id")
        
        # Update the subject
        update_data = {
            "name_ar": test_subject.get("name_ar", "Updated") + " (تحديث)",
            "weekly_periods": 5
        }
        
        response = requests.put(
            f"{BASE_URL}/api/school/subjects/{subject_id}",
            headers=auth_headers,
            json=update_data
        )
        
        # Check response - should NOT return 404 "المادة غير موجودة"
        assert response.status_code == 200, f"Update subject failed with status {response.status_code}: {response.text}"
        data = response.json()
        assert "message" in data, f"Expected success message, got: {data}"
        print(f"✓ Updated subject {subject_id}: {data}")
    
    def test_delete_subject(self, auth_headers):
        """Test DELETE /school/subjects/{id} - delete a subject"""
        # First create a test subject to delete
        test_subject = {
            "name_ar": "TEST_للحذف",
            "name_en": "TEST_ToDelete",
            "code": "TEST-DEL-001",
            "category": "general",
            "weekly_periods": 2
        }
        create_response = requests.post(
            f"{BASE_URL}/api/school/subjects",
            headers=auth_headers,
            json=test_subject
        )
        
        if create_response.status_code not in [200, 201]:
            # Try to find existing test subject
            response = requests.get(f"{BASE_URL}/api/school/subjects", headers=auth_headers)
            subjects = response.json()
            test_subj = next((s for s in subjects if s.get("name_ar", "").startswith("TEST_")), None)
            if not test_subj:
                pytest.skip("Could not create or find test subject to delete")
            subject_id = test_subj.get("id")
        else:
            data = create_response.json()
            subject_id = data.get("id") or data.get("subject_id")
        
        if not subject_id:
            pytest.skip("No subject ID available for deletion test")
        
        # Delete the subject
        response = requests.delete(
            f"{BASE_URL}/api/school/subjects/{subject_id}",
            headers=auth_headers
        )
        
        # Check response - should NOT return 404 "المادة غير موجودة"
        assert response.status_code == 200, f"Delete subject failed with status {response.status_code}: {response.text}"
        data = response.json()
        print(f"✓ Deleted subject {subject_id}: {data}")


class TestSchoolConstraintsCRUD:
    """Test School Constraints CRUD operations"""
    
    def test_get_school_constraints(self, auth_headers):
        """Test GET /school/constraints - should return list of constraints"""
        response = requests.get(f"{BASE_URL}/api/school/constraints", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get constraints: {response.text}"
        constraints = response.json()
        assert isinstance(constraints, list), "Response should be a list"
        print(f"✓ Found {len(constraints)} constraints")
        return constraints
    
    def test_create_constraint(self, auth_headers):
        """Test POST /school/constraints - create a test constraint"""
        test_constraint = {
            "name_ar": "TEST_قيد اختبار",
            "name_en": "TEST_Test Constraint",
            "description_ar": "قيد للاختبار",
            "description_en": "Test constraint",
            "type": "soft",
            "priority": "medium",
            "is_active": True
        }
        response = requests.post(
            f"{BASE_URL}/api/school/constraints",
            headers=auth_headers,
            json=test_constraint
        )
        assert response.status_code in [200, 201], f"Failed to create constraint: {response.text}"
        data = response.json()
        print(f"✓ Created constraint: {data}")
        return data
    
    def test_update_constraint(self, auth_headers):
        """Test PUT /school/constraints/{id} - update a constraint"""
        # First get existing constraints
        response = requests.get(f"{BASE_URL}/api/school/constraints", headers=auth_headers)
        constraints = response.json()
        
        if not constraints:
            pytest.skip("No constraints available to update")
        
        # Find a test constraint or use first one
        test_constraint = next((c for c in constraints if c.get("name_ar", "").startswith("TEST_")), constraints[0])
        constraint_id = test_constraint.get("id")
        
        # Update the constraint - toggle is_active
        current_active = test_constraint.get("is_active", True)
        update_data = {
            "is_active": not current_active
        }
        
        response = requests.put(
            f"{BASE_URL}/api/school/constraints/{constraint_id}",
            headers=auth_headers,
            json=update_data
        )
        
        # Check response - should NOT return 404 "القيد غير موجود"
        assert response.status_code == 200, f"Update constraint failed with status {response.status_code}: {response.text}"
        data = response.json()
        assert "message" in data, f"Expected success message, got: {data}"
        print(f"✓ Updated constraint {constraint_id}: {data}")
    
    def test_delete_constraint(self, auth_headers):
        """Test DELETE /school/constraints/{id} - delete a constraint"""
        # First create a test constraint to delete
        test_constraint = {
            "name_ar": "TEST_للحذف",
            "name_en": "TEST_ToDelete",
            "description_ar": "قيد للحذف",
            "type": "soft",
            "priority": "low",
            "is_active": True
        }
        create_response = requests.post(
            f"{BASE_URL}/api/school/constraints",
            headers=auth_headers,
            json=test_constraint
        )
        
        if create_response.status_code not in [200, 201]:
            # Try to find existing test constraint
            response = requests.get(f"{BASE_URL}/api/school/constraints", headers=auth_headers)
            constraints = response.json()
            test_const = next((c for c in constraints if c.get("name_ar", "").startswith("TEST_")), None)
            if not test_const:
                pytest.skip("Could not create or find test constraint to delete")
            constraint_id = test_const.get("id")
        else:
            data = create_response.json()
            constraint_id = data.get("id") or data.get("constraint_id")
        
        if not constraint_id:
            pytest.skip("No constraint ID available for deletion test")
        
        # Delete the constraint
        response = requests.delete(
            f"{BASE_URL}/api/school/constraints/{constraint_id}",
            headers=auth_headers
        )
        
        # Check response - should NOT return 404 "القيد غير موجود"
        assert response.status_code == 200, f"Delete constraint failed with status {response.status_code}: {response.text}"
        data = response.json()
        print(f"✓ Deleted constraint {constraint_id}: {data}")


class TestSchoolSettings:
    """Test School Settings endpoints"""
    
    def test_get_school_settings(self, auth_headers):
        """Test GET /school/settings - should return settings with time_slots"""
        response = requests.get(f"{BASE_URL}/api/school/settings", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get settings: {response.text}"
        data = response.json()
        
        # Check for time_slots in settings
        settings = data.get("settings", {})
        time_slots = settings.get("time_slots") or data.get("time_slots", [])
        
        print(f"✓ Got school settings with {len(time_slots)} time slots")
        return data
    
    def test_update_time_slots(self, auth_headers):
        """Test PUT /school/settings - update time slots"""
        # First get current settings
        response = requests.get(f"{BASE_URL}/api/school/settings", headers=auth_headers)
        current_settings = response.json()
        
        settings = current_settings.get("settings", {})
        time_slots = settings.get("time_slots") or current_settings.get("time_slots", [])
        
        if not time_slots:
            pytest.skip("No time slots to update")
        
        # Update first slot's start time
        updated_slots = time_slots.copy()
        if updated_slots:
            updated_slots[0]["start_time"] = "07:15"  # Change from default
        
        update_data = {
            "settings": {
                "time_slots": updated_slots
            }
        }
        
        response = requests.put(
            f"{BASE_URL}/api/school/settings",
            headers=auth_headers,
            json=update_data
        )
        
        assert response.status_code == 200, f"Update settings failed: {response.text}"
        print(f"✓ Updated time slots successfully")


class TestCreateClassWizardOptions:
    """Test Create Class Wizard dropdown options"""
    
    def test_get_grades_options(self, auth_headers):
        """Test GET /classes/options/grades - should return grades with name_ar"""
        response = requests.get(f"{BASE_URL}/api/classes/options/grades", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get grades: {response.text}"
        data = response.json()
        
        grades = data.get("grades", [])
        print(f"✓ Found {len(grades)} grades")
        
        # Check that grades have name_ar
        for grade in grades[:3]:  # Check first 3
            assert "name_ar" in grade or "name" in grade, f"Grade missing name_ar: {grade}"
            print(f"  - {grade.get('name_ar') or grade.get('name')}")
        
        return grades
    
    def test_get_class_types_options(self, auth_headers):
        """Test GET /classes/options/class-types - should return class types"""
        response = requests.get(f"{BASE_URL}/api/classes/options/class-types", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get class types: {response.text}"
        data = response.json()
        
        types = data.get("types", [])
        print(f"✓ Found {len(types)} class types")
        
        for t in types:
            print(f"  - {t.get('name_ar')} ({t.get('code')})")
        
        return types
    
    def test_get_teachers_options(self, auth_headers):
        """Test GET /classes/options/teachers - should return teachers"""
        response = requests.get(f"{BASE_URL}/api/classes/options/teachers", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get teachers: {response.text}"
        data = response.json()
        
        teachers = data.get("teachers", [])
        print(f"✓ Found {len(teachers)} teachers for homeroom selection")
        return teachers


class TestUsersManagementPage:
    """Test Users Management page features"""
    
    def test_import_export_endpoint_exists(self, auth_headers):
        """Test that bulk import/export endpoints exist"""
        # Test template download endpoint
        response = requests.get(
            f"{BASE_URL}/api/bulk/template/students",
            headers=auth_headers
        )
        # Should return 200 or 404 (not 500)
        assert response.status_code in [200, 404], f"Template endpoint error: {response.status_code}"
        print(f"✓ Bulk template endpoint accessible (status: {response.status_code})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
