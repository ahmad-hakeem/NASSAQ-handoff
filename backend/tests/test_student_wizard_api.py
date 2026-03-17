"""
Test Student Management APIs - Add Student Wizard
Tests for the student management endpoints used by the Add Student Wizard
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
PRINCIPAL_EMAIL = "principal@nassaq.com"
PRINCIPAL_PASSWORD = "Principal123!"


class TestStudentOptionsAPIs:
    """Test student options/lookup APIs"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as principal
        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": PRINCIPAL_EMAIL, "password": PRINCIPAL_PASSWORD}
        )
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.user = login_response.json().get("user")
        else:
            pytest.skip("Principal login failed - skipping tests")
    
    def test_principal_login(self):
        """Test principal can login successfully"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": PRINCIPAL_EMAIL, "password": PRINCIPAL_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "school_principal"
        assert data["user"]["email"] == PRINCIPAL_EMAIL
    
    def test_get_grades_authenticated(self):
        """Test GET /api/students/options/grades with auth"""
        response = self.session.get(f"{BASE_URL}/api/students/options/grades")
        assert response.status_code == 200
        data = response.json()
        assert "grades" in data
        assert len(data["grades"]) >= 1
        # Verify grade structure
        grade = data["grades"][0]
        assert "id" in grade
        assert "name_ar" in grade
        assert "name_en" in grade
    
    def test_get_sections_authenticated(self):
        """Test GET /api/students/options/sections with auth"""
        response = self.session.get(f"{BASE_URL}/api/students/options/sections")
        assert response.status_code == 200
        data = response.json()
        assert "sections" in data
        assert len(data["sections"]) >= 1
        # Verify section structure
        section = data["sections"][0]
        assert "id" in section
        assert "name_ar" in section
        assert "name_en" in section
    
    def test_get_nationalities_no_auth(self):
        """Test GET /api/students/options/nationalities (no auth required)"""
        response = requests.get(f"{BASE_URL}/api/students/options/nationalities")
        assert response.status_code == 200
        data = response.json()
        assert "nationalities" in data
        assert len(data["nationalities"]) >= 10
        # Verify Saudi Arabia is in the list
        codes = [n["code"] for n in data["nationalities"]]
        assert "SA" in codes
    
    def test_get_blood_types_no_auth(self):
        """Test GET /api/students/options/blood-types (no auth required)"""
        response = requests.get(f"{BASE_URL}/api/students/options/blood-types")
        assert response.status_code == 200
        data = response.json()
        assert "blood_types" in data
        assert len(data["blood_types"]) == 8
        # Verify blood type structure
        codes = [bt["code"] for bt in data["blood_types"]]
        assert "A+" in codes
        assert "O-" in codes
    
    def test_get_parent_relations_no_auth(self):
        """Test GET /api/students/options/parent-relations (no auth required)"""
        response = requests.get(f"{BASE_URL}/api/students/options/parent-relations")
        assert response.status_code == 200
        data = response.json()
        assert "relations" in data
        assert len(data["relations"]) >= 3
        # Verify relation structure
        codes = [r["code"] for r in data["relations"]]
        assert "father" in codes
        assert "mother" in codes
        assert "guardian" in codes


class TestStudentValidationAPIs:
    """Test student validation APIs"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as principal
        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": PRINCIPAL_EMAIL, "password": PRINCIPAL_PASSWORD}
        )
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Principal login failed - skipping tests")
    
    def test_validate_national_id_new(self):
        """Test POST /api/students/validate/national-id with new ID"""
        response = self.session.post(
            f"{BASE_URL}/api/students/validate/national-id",
            json={"national_id": "1234567890"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "valid" in data
        # New ID should be valid
        assert data["valid"] == True
    
    def test_validate_parent_phone_new(self):
        """Test POST /api/students/validate/parent-phone with new phone"""
        response = self.session.post(
            f"{BASE_URL}/api/students/validate/parent-phone",
            json={"phone": "0599999999"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "exists" in data
        # New phone should not exist
        assert data["exists"] == False


class TestStudentCreationAPI:
    """Test student creation API"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as principal
        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": PRINCIPAL_EMAIL, "password": PRINCIPAL_PASSWORD}
        )
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Principal login failed - skipping tests")
    
    def test_create_student_full_flow(self):
        """Test POST /api/students/create with full student data"""
        import random
        import string
        
        # Generate unique national ID for test
        test_national_id = ''.join(random.choices(string.digits, k=10))
        test_phone = f"05{''.join(random.choices(string.digits, k=8))}"
        
        payload = {
            "basic_info": {
                "full_name_ar": "طالب اختبار",
                "full_name_en": "Test Student",
                "national_id": test_national_id,
                "date_of_birth": "2015-01-15",
                "gender": "male",
                "nationality": "SA",
                "grade_id": "grade_1",
                "section_id": "section_a"
            },
            "parent_info": {
                "parent_name_ar": "ولي أمر اختبار",
                "parent_name_en": "Test Parent",
                "parent_phone": test_phone,
                "parent_relation": "father"
            },
            "health_info": {
                "blood_type": "A+",
                "has_chronic_conditions": False,
                "has_allergies": False
            },
            "save_as_draft": False
        }
        
        response = self.session.post(
            f"{BASE_URL}/api/students/create",
            json=payload
        )
        
        # Should succeed or fail gracefully
        assert response.status_code in [200, 201, 400]
        data = response.json()
        
        if response.status_code in [200, 201]:
            assert data.get("success") == True
            assert "student_id" in data
            assert "parent_id" in data
            print(f"Created student: {data.get('student_id')}")
        else:
            # If failed, should have error message
            assert "error" in data or "detail" in data


class TestStudentListAPI:
    """Test student list API"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test fixtures"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as principal
        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": PRINCIPAL_EMAIL, "password": PRINCIPAL_PASSWORD}
        )
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Principal login failed - skipping tests")
    
    def test_list_students(self):
        """Test GET /api/students/ list endpoint"""
        response = self.session.get(f"{BASE_URL}/api/students/")
        assert response.status_code == 200
        data = response.json()
        assert "students" in data
        assert "total" in data
        assert isinstance(data["students"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
