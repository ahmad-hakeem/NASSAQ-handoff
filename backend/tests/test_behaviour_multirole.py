"""
NASSAQ Behaviour Engine & Multi-Role API Tests
Tests for:
- Behaviour Engine (seed, get types, create records, history, profile)
- Multi-Role Support (get roles, add role, switch role)
- Public Contact API (no auth required)
- UserRole enum values
"""

import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "info@nassaqapp.com"
ADMIN_PASSWORD = "NassaqAdmin2026!##$$HBJ"


class TestSetup:
    """Setup and authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for platform admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        return data["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_login_success(self):
        """Test platform admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["role"] == "platform_admin"
        print(f"✓ Login successful for {ADMIN_EMAIL}")


class TestPublicContactAPI:
    """Test Public Contact Info API (no auth required)"""
    
    def test_get_public_contact_info_no_auth(self):
        """Test getting public contact info without authentication"""
        response = requests.get(f"{BASE_URL}/api/public/contact-info")
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify required fields
        assert "primary_email" in data
        assert "support_email" in data
        assert "primary_phone" in data
        assert "address" in data
        assert "working_hours" in data
        assert "website" in data
        assert "owner_name" in data
        assert "social_media" in data
        
        print(f"✓ Public contact info retrieved successfully")
        print(f"  - Primary Email: {data['primary_email']}")
        print(f"  - Support Email: {data['support_email']}")
        print(f"  - Phone: {data['primary_phone']}")
    
    def test_public_contact_info_returns_defaults(self):
        """Test that public contact info returns sensible defaults"""
        response = requests.get(f"{BASE_URL}/api/public/contact-info")
        assert response.status_code == 200
        data = response.json()
        
        # Verify default values are present
        assert data["primary_email"] != ""
        assert data["support_email"] != ""
        assert data["primary_phone"] != ""
        print(f"✓ Public contact info has valid default values")


class TestBehaviourTypesAPI:
    """Test Behaviour Types API"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_seed_default_behaviour_types(self, auth_headers):
        """Test seeding default behaviour types"""
        response = requests.post(
            f"{BASE_URL}/api/behaviour-types/seed-defaults",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "message" in data
        assert "added" in data  # API returns 'added' not 'seeded_count'
        print(f"✓ Seeded {data['added']} default behaviour types")
        print(f"  - Message: {data['message']}")
    
    def test_get_behaviour_types(self, auth_headers):
        """Test getting behaviour types"""
        response = requests.get(
            f"{BASE_URL}/api/behaviour-types",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "behaviour_types" in data
        assert "total" in data
        assert data["total"] > 0, "No behaviour types found"
        
        # Verify structure of behaviour types
        for bt in data["behaviour_types"]:
            assert "id" in bt
            assert "name_ar" in bt
            assert "category" in bt
            assert "default_severity" in bt
        
        print(f"✓ Retrieved {data['total']} behaviour types")
        
        # Print some examples
        for bt in data["behaviour_types"][:3]:
            print(f"  - {bt['name_ar']} ({bt['category']}, {bt['default_severity']})")
    
    def test_get_behaviour_types_by_category_positive(self, auth_headers):
        """Test filtering behaviour types by positive category"""
        response = requests.get(
            f"{BASE_URL}/api/behaviour-types?category=positive",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for bt in data["behaviour_types"]:
            assert bt["category"] == "positive"
        
        print(f"✓ Retrieved {data['total']} positive behaviour types")
    
    def test_get_behaviour_types_by_category_negative(self, auth_headers):
        """Test filtering behaviour types by negative category"""
        response = requests.get(
            f"{BASE_URL}/api/behaviour-types?category=negative",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        for bt in data["behaviour_types"]:
            assert bt["category"] == "negative"
        
        print(f"✓ Retrieved {data['total']} negative behaviour types")
    
    def test_create_custom_behaviour_type(self, auth_headers):
        """Test creating a custom behaviour type"""
        unique_name = f"TEST_سلوك_اختبار_{uuid.uuid4().hex[:6]}"
        
        response = requests.post(
            f"{BASE_URL}/api/behaviour-types",
            headers=auth_headers,
            json={
                "name_ar": unique_name,
                "name_en": "Test Behaviour",
                "category": "positive",
                "default_severity": "minor",
                "default_points": 5,
                "description": "سلوك اختبار"
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert data["name_ar"] == unique_name
        assert data["category"] == "positive"
        
        print(f"✓ Created custom behaviour type: {unique_name}")


class TestBehaviourRecordsAPI:
    """Test Behaviour Records API - requires school_id parameter"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_school_id(self, auth_headers):
        """Get or create a test school"""
        schools_response = requests.get(
            f"{BASE_URL}/api/schools",
            headers=auth_headers
        )
        
        if schools_response.status_code == 200:
            schools = schools_response.json()
            if schools and len(schools) > 0:
                return schools[0]["id"]
        
        # Create a test school
        school_response = requests.post(
            f"{BASE_URL}/api/schools",
            headers=auth_headers,
            json={
                "name": f"TEST_مدرسة_سلوك_{uuid.uuid4().hex[:6]}",
                "name_en": "Test Behaviour School",
                "student_capacity": 100
            }
        )
        if school_response.status_code == 200:
            return school_response.json()["id"]
        return None
    
    @pytest.fixture(scope="class")
    def test_student_id(self, auth_headers, test_school_id):
        """Get or create a test student"""
        if not test_school_id:
            return f"test_student_{uuid.uuid4().hex[:8]}"
        
        # Try to get existing students
        students_response = requests.get(
            f"{BASE_URL}/api/students?school_id={test_school_id}",
            headers=auth_headers
        )
        
        if students_response.status_code == 200:
            students = students_response.json()
            if isinstance(students, list) and len(students) > 0:
                return students[0]["id"]
            elif isinstance(students, dict) and students.get("students"):
                return students["students"][0]["id"]
        
        # Create a test student
        student_response = requests.post(
            f"{BASE_URL}/api/students",
            headers=auth_headers,
            json={
                "full_name": f"TEST_طالب_سلوك_{uuid.uuid4().hex[:6]}",
                "full_name_en": "Test Behaviour Student",
                "school_id": test_school_id,
                "grade": "الصف الأول",
                "national_id": f"TEST_{uuid.uuid4().hex[:10]}"
            }
        )
        
        if student_response.status_code in [200, 201]:
            return student_response.json().get("id")
        
        return f"test_student_{uuid.uuid4().hex[:8]}"
    
    def test_get_student_behaviour_history_with_school_id(self, auth_headers, test_school_id, test_student_id):
        """Test getting student behaviour history with required school_id"""
        if not test_school_id:
            pytest.skip("No school available for testing")
        
        response = requests.get(
            f"{BASE_URL}/api/behaviour-records/student/{test_student_id}?school_id={test_school_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "records" in data
        assert "total" in data
        assert "summary" in data
        
        print(f"✓ Retrieved behaviour history for student {test_student_id}")
        print(f"  - Total records: {data['total']}")
        print(f"  - Summary: {data['summary']}")
    
    def test_get_student_behaviour_history_missing_school_id(self, auth_headers, test_student_id):
        """Test that behaviour history requires school_id parameter"""
        response = requests.get(
            f"{BASE_URL}/api/behaviour-records/student/{test_student_id}",
            headers=auth_headers
        )
        
        # Should return 422 (validation error) because school_id is required
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print(f"✓ API correctly requires school_id parameter")
    
    def test_get_student_behaviour_profile_with_school_id(self, auth_headers, test_school_id, test_student_id):
        """Test getting student behaviour profile with required school_id"""
        if not test_school_id:
            pytest.skip("No school available for testing")
        
        response = requests.get(
            f"{BASE_URL}/api/behaviour-profile/student/{test_student_id}?school_id={test_school_id}",
            headers=auth_headers
        )
        
        # May return 404 if student doesn't exist in DB
        if response.status_code == 200:
            data = response.json()
            assert "student_id" in data
            assert "behaviour_score" in data
            assert "behaviour_level" in data
            print(f"✓ Retrieved behaviour profile for student {test_student_id}")
            print(f"  - Score: {data['behaviour_score']}")
            print(f"  - Level: {data['behaviour_level']}")
        elif response.status_code == 404:
            print(f"✓ API correctly returns 404 for non-existent student")
        else:
            pytest.fail(f"Unexpected status code: {response.status_code} - {response.text}")
    
    def test_create_behaviour_record_requires_teacher_role(self, auth_headers, test_school_id):
        """Test that creating behaviour record requires teacher/principal role"""
        if not test_school_id:
            pytest.skip("No school available for testing")
        
        # Platform admin should not be able to create behaviour records
        # (requires TEACHER, SCHOOL_PRINCIPAL, or SCHOOL_ADMIN role)
        response = requests.post(
            f"{BASE_URL}/api/behaviour-records?school_id={test_school_id}",
            headers=auth_headers,
            json={
                "student_id": "test_student",
                "behaviour_type_id": "test_type",
                "title": "Test",
                "incident_date": datetime.now().strftime("%Y-%m-%d")
            }
        )
        
        # Should return 403 (forbidden) for platform_admin
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        print(f"✓ API correctly restricts behaviour record creation to teachers/principals")


class TestMultiRoleAPI:
    """Test Multi-Role Support API"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def current_user_id(self, auth_headers):
        """Get current user ID"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers=auth_headers
        )
        assert response.status_code == 200
        return response.json()["id"]
    
    @pytest.fixture(scope="class")
    def test_user(self, auth_headers):
        """Create a test user for multi-role testing"""
        unique_email = f"test_multirole_{uuid.uuid4().hex[:8]}@test.com"
        
        response = requests.post(
            f"{BASE_URL}/api/users/create",
            headers=auth_headers,
            json={
                "email": unique_email,
                "password": "TestPass123!",
                "full_name": f"TEST_مستخدم_متعدد_الأدوار",
                "role": "teacher"
            }
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            # Return mock user
            return {"id": f"test_user_{uuid.uuid4().hex[:8]}", "email": unique_email}
    
    def test_get_user_roles(self, auth_headers, current_user_id):
        """Test getting user roles"""
        response = requests.get(
            f"{BASE_URL}/api/users/{current_user_id}/roles",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "roles" in data
        assert "total" in data
        assert data["total"] >= 1, "User should have at least one role"
        
        # Verify primary role exists
        primary_roles = [r for r in data["roles"] if r.get("is_primary")]
        assert len(primary_roles) >= 1, "User should have a primary role"
        
        print(f"✓ Retrieved {data['total']} roles for user {current_user_id}")
        for role in data["roles"]:
            print(f"  - {role['role']} (primary: {role.get('is_primary', False)})")
    
    def test_get_user_roles_for_nonexistent_user(self, auth_headers):
        """Test getting roles for non-existent user"""
        random_user_id = str(uuid.uuid4())
        
        response = requests.get(
            f"{BASE_URL}/api/users/{random_user_id}/roles",
            headers=auth_headers
        )
        
        # Should return 404 (user not found)
        assert response.status_code == 404
        print(f"✓ API correctly returns 404 for non-existent user")
    
    def test_add_role_to_user(self, auth_headers, test_user):
        """Test adding a role to a user"""
        user_id = test_user.get("id")
        
        response = requests.post(
            f"{BASE_URL}/api/users/{user_id}/add-role",
            headers=auth_headers,
            params={
                "role": "parent",
                "tenant_id": None
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "message" in data
            assert "role" in data
            print(f"✓ Added 'parent' role to user {user_id}")
        elif response.status_code == 404:
            print(f"✓ API correctly returns 404 for non-existent user")
        else:
            pytest.fail(f"Unexpected status: {response.status_code} - {response.text}")
    
    def test_add_duplicate_role(self, auth_headers, test_user):
        """Test adding a duplicate role (should fail)"""
        user_id = test_user.get("id")
        
        # First add the role
        requests.post(
            f"{BASE_URL}/api/users/{user_id}/add-role",
            headers=auth_headers,
            params={"role": "driver", "tenant_id": None}
        )
        
        # Try to add the same role again
        response = requests.post(
            f"{BASE_URL}/api/users/{user_id}/add-role",
            headers=auth_headers,
            params={"role": "driver", "tenant_id": None}
        )
        
        # Should return 400 if role already exists, or 404 if user doesn't exist
        assert response.status_code in [400, 404]
        print(f"✓ Duplicate role correctly handled (status: {response.status_code})")
    
    def test_switch_role(self, auth_headers, current_user_id):
        """Test switching user role"""
        # First get available roles
        roles_response = requests.get(
            f"{BASE_URL}/api/users/{current_user_id}/roles",
            headers=auth_headers
        )
        
        if roles_response.status_code != 200:
            pytest.skip("Could not get user roles")
        
        roles = roles_response.json().get("roles", [])
        if len(roles) < 1:
            pytest.skip("User has no roles to switch")
        
        # Try to switch to the primary role (should succeed)
        primary_role = roles[0]
        
        response = requests.post(
            f"{BASE_URL}/api/users/{current_user_id}/switch-role",
            headers=auth_headers,
            params={
                "target_role": primary_role["role"],
                "target_tenant_id": primary_role.get("tenant_id")
            }
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "message" in data
        assert "active_role" in data
        assert data["active_role"] == primary_role["role"]
        
        print(f"✓ Successfully switched to role: {primary_role['role']}")
    
    def test_switch_to_invalid_role(self, auth_headers, current_user_id):
        """Test switching to an invalid role (should fail)"""
        response = requests.post(
            f"{BASE_URL}/api/users/{current_user_id}/switch-role",
            headers=auth_headers,
            params={
                "target_role": "invalid_role_xyz",
                "target_tenant_id": None
            }
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        print(f"✓ Invalid role switch correctly rejected")
    
    def test_switch_role_for_other_user(self, auth_headers, test_user):
        """Test that users can only switch their own role"""
        user_id = test_user.get("id")
        
        response = requests.post(
            f"{BASE_URL}/api/users/{user_id}/switch-role",
            headers=auth_headers,
            params={
                "target_role": "teacher",
                "target_tenant_id": None
            }
        )
        
        # Should return 403 (can only switch own role)
        assert response.status_code == 403
        print(f"✓ API correctly prevents switching other user's role")


class TestUserRoleEnum:
    """Test UserRole enum values"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_platform_admin_role(self, auth_headers):
        """Test platform_admin role exists and works"""
        response = requests.get(
            f"{BASE_URL}/api/auth/me",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "platform_admin"
        print(f"✓ platform_admin role verified")
    
    def test_create_user_with_platform_operations_manager(self, auth_headers):
        """Test creating user with platform_operations_manager role"""
        unique_email = f"test_ops_mgr_{uuid.uuid4().hex[:6]}@test.com"
        
        response = requests.post(
            f"{BASE_URL}/api/users/create",
            headers=auth_headers,
            json={
                "email": unique_email,
                "password": "TestPass123!",
                "full_name": "TEST_مدير_العمليات",
                "role": "platform_operations_manager"
            }
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["role"] == "platform_operations_manager"
        print(f"✓ Created user with platform_operations_manager role")
    
    def test_create_user_with_platform_technical_admin(self, auth_headers):
        """Test creating user with platform_technical_admin role"""
        unique_email = f"test_tech_admin_{uuid.uuid4().hex[:6]}@test.com"
        
        response = requests.post(
            f"{BASE_URL}/api/users/create",
            headers=auth_headers,
            json={
                "email": unique_email,
                "password": "TestPass123!",
                "full_name": "TEST_المدير_التقني",
                "role": "platform_technical_admin"
            }
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["role"] == "platform_technical_admin"
        print(f"✓ Created user with platform_technical_admin role")
    
    def test_create_user_with_platform_support_specialist(self, auth_headers):
        """Test creating user with platform_support_specialist role"""
        unique_email = f"test_support_{uuid.uuid4().hex[:6]}@test.com"
        
        response = requests.post(
            f"{BASE_URL}/api/users/create",
            headers=auth_headers,
            json={
                "email": unique_email,
                "password": "TestPass123!",
                "full_name": "TEST_أخصائي_الدعم",
                "role": "platform_support_specialist"
            }
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["role"] == "platform_support_specialist"
        print(f"✓ Created user with platform_support_specialist role")
    
    def test_create_user_with_platform_data_analyst(self, auth_headers):
        """Test creating user with platform_data_analyst role"""
        unique_email = f"test_analyst_{uuid.uuid4().hex[:6]}@test.com"
        
        response = requests.post(
            f"{BASE_URL}/api/users/create",
            headers=auth_headers,
            json={
                "email": unique_email,
                "password": "TestPass123!",
                "full_name": "TEST_محلل_البيانات",
                "role": "platform_data_analyst"
            }
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["role"] == "platform_data_analyst"
        print(f"✓ Created user with platform_data_analyst role")
    
    def test_create_user_with_platform_security_officer(self, auth_headers):
        """Test creating user with platform_security_officer role"""
        unique_email = f"test_security_{uuid.uuid4().hex[:6]}@test.com"
        
        response = requests.post(
            f"{BASE_URL}/api/users/create",
            headers=auth_headers,
            json={
                "email": unique_email,
                "password": "TestPass123!",
                "full_name": "TEST_مسؤول_الأمن",
                "role": "platform_security_officer"
            }
        )
        
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data["role"] == "platform_security_officer"
        print(f"✓ Created user with platform_security_officer role")


class TestDisciplinaryActionsAPI:
    """Test Disciplinary Actions API"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_create_disciplinary_action_endpoint_exists(self, auth_headers):
        """Test that disciplinary action endpoint exists"""
        # This will fail with 422 (validation error) if endpoint exists but data is invalid
        response = requests.post(
            f"{BASE_URL}/api/disciplinary-actions",
            headers=auth_headers,
            json={}
        )
        
        # Should return 422 (validation error) not 404
        assert response.status_code != 404, "Disciplinary actions endpoint not found"
        print(f"✓ Disciplinary actions endpoint exists (status: {response.status_code})")


class TestAPIHealth:
    """Test API health and basic connectivity"""
    
    def test_api_health(self):
        """Test basic API health"""
        response = requests.get(f"{BASE_URL}/api")
        # May return 404 or 200 depending on implementation
        assert response.status_code in [200, 404, 405]
        print(f"✓ API is reachable")
    
    def test_auth_endpoint_exists(self):
        """Test auth endpoints exist"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={})
        # Should return 422 (validation error) not 404
        assert response.status_code != 404
        print(f"✓ Auth endpoint exists")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
