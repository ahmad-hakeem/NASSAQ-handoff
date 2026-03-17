"""
Test Teacher Wizard API - Tests for teacher management endpoints and test accounts
Tests:
- All 6 test account logins
- Teacher management option endpoints
- Teacher creation API
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test accounts credentials
TEST_ACCOUNTS = [
    {"email": "admin@nassaq.com", "password": "Admin@123", "role": "platform_admin", "name": "Admin"},
    {"email": "principal@nassaq.com", "password": "Principal@123", "role": "school_principal", "name": "Principal"},
    {"email": "teacher@nassaq.com", "password": "Teacher@123", "role": "teacher", "name": "Teacher"},
    {"email": "student@nassaq.com", "password": "Student@123", "role": "student", "name": "Student"},
    {"email": "parent@nassaq.com", "password": "Parent@123", "role": "parent", "name": "Parent"},
    {"email": "independent.teacher@nassaq.com", "password": "Teacher@123", "role": "independent_teacher", "name": "Independent Teacher"},
]


class TestAccountLogins:
    """Test all 6 test account logins"""
    
    @pytest.fixture
    def api_client(self):
        session = requests.Session()
        session.headers.update({"Content-Type": "application/json"})
        return session
    
    @pytest.mark.parametrize("account", TEST_ACCOUNTS, ids=[a["name"] for a in TEST_ACCOUNTS])
    def test_account_login(self, api_client, account):
        """Test login for each test account"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json={
            "email": account["email"],
            "password": account["password"]
        })
        
        # Check status code
        assert response.status_code == 200, f"Login failed for {account['email']}: {response.text}"
        
        # Validate response structure
        data = response.json()
        assert "access_token" in data, f"No access_token in response for {account['email']}"
        assert "user" in data, f"No user in response for {account['email']}"
        
        # Validate user data
        user = data["user"]
        assert user.get("email") == account["email"], f"Email mismatch for {account['email']}"
        print(f"✓ {account['name']} login successful - Role: {user.get('role')}")


class TestTeacherOptionsEndpoints:
    """Test teacher management option endpoints"""
    
    @pytest.fixture
    def principal_token(self):
        """Get principal auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal@nassaq.com",
            "password": "Principal@123"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Principal login failed")
    
    @pytest.fixture
    def auth_headers(self, principal_token):
        return {"Authorization": f"Bearer {principal_token}", "Content-Type": "application/json"}
    
    def test_get_subjects(self, auth_headers):
        """Test GET /api/teachers/options/subjects"""
        response = requests.get(f"{BASE_URL}/api/teachers/options/subjects", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "subjects" in data, "No subjects key in response"
        subjects = data["subjects"]
        assert len(subjects) > 0, "No subjects returned"
        
        # Validate subject structure
        first_subject = subjects[0]
        assert "id" in first_subject, "Subject missing id"
        assert "name_ar" in first_subject, "Subject missing name_ar"
        assert "name_en" in first_subject, "Subject missing name_en"
        print(f"✓ Got {len(subjects)} subjects")
    
    def test_get_grades(self, auth_headers):
        """Test GET /api/teachers/options/grades"""
        response = requests.get(f"{BASE_URL}/api/teachers/options/grades", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "grades" in data, "No grades key in response"
        grades = data["grades"]
        assert len(grades) > 0, "No grades returned"
        
        # Validate grade structure
        first_grade = grades[0]
        assert "id" in first_grade, "Grade missing id"
        assert "name_ar" in first_grade, "Grade missing name_ar"
        print(f"✓ Got {len(grades)} grades")
    
    def test_get_academic_degrees(self, auth_headers):
        """Test GET /api/teachers/options/academic-degrees"""
        response = requests.get(f"{BASE_URL}/api/teachers/options/academic-degrees", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "degrees" in data, "No degrees key in response"
        degrees = data["degrees"]
        assert len(degrees) >= 4, "Expected at least 4 degrees (diploma, bachelor, master, doctorate)"
        print(f"✓ Got {len(degrees)} academic degrees")
    
    def test_get_teacher_ranks(self, auth_headers):
        """Test GET /api/teachers/options/teacher-ranks"""
        response = requests.get(f"{BASE_URL}/api/teachers/options/teacher-ranks", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "ranks" in data, "No ranks key in response"
        ranks = data["ranks"]
        assert len(ranks) >= 4, "Expected at least 4 ranks"
        print(f"✓ Got {len(ranks)} teacher ranks")
    
    def test_get_contract_types(self, auth_headers):
        """Test GET /api/teachers/options/contract-types"""
        response = requests.get(f"{BASE_URL}/api/teachers/options/contract-types", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "types" in data, "No types key in response"
        types = data["types"]
        assert len(types) >= 3, "Expected at least 3 contract types"
        print(f"✓ Got {len(types)} contract types")
    
    def test_get_nationalities(self, auth_headers):
        """Test GET /api/teachers/options/nationalities"""
        response = requests.get(f"{BASE_URL}/api/teachers/options/nationalities", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        
        data = response.json()
        assert "nationalities" in data, "No nationalities key in response"
        nationalities = data["nationalities"]
        assert len(nationalities) >= 10, "Expected at least 10 nationalities"
        print(f"✓ Got {len(nationalities)} nationalities")


class TestTeacherCreation:
    """Test teacher creation API"""
    
    @pytest.fixture
    def principal_token(self):
        """Get principal auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal@nassaq.com",
            "password": "Principal@123"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Principal login failed")
    
    @pytest.fixture
    def auth_headers(self, principal_token):
        return {"Authorization": f"Bearer {principal_token}", "Content-Type": "application/json"}
    
    def test_create_teacher_full_flow(self, auth_headers):
        """Test POST /api/teachers/create with full data"""
        timestamp = int(time.time())
        
        teacher_data = {
            "basic_info": {
                "full_name_ar": f"معلم اختبار {timestamp}",
                "full_name_en": f"Test Teacher {timestamp}",
                "national_id": f"10{timestamp % 100000000:08d}",  # 10 digit ID
                "date_of_birth": "1985-05-15",
                "gender": "male",
                "nationality": "SA",
                "phone": f"05{timestamp % 100000000:08d}",
                "email": f"test.teacher.{timestamp}@test.com"
            },
            "qualifications": {
                "academic_degree": "bachelor",
                "specialization": "Mathematics",
                "university": "King Saud University",
                "graduation_year": 2010,
                "years_of_experience": 10,
                "teacher_rank": "advanced",
                "certifications": ["Teaching Certificate", "ICDL"]
            },
            "subjects": {
                "subject_ids": ["math", "science"],
                "grade_ids": ["grade_1", "grade_2", "grade_3"],
                "primary_subject_id": "math",
                "max_periods_per_week": 24
            },
            "schedule": {
                "contract_type": "permanent",
                "available_days": ["sunday", "monday", "tuesday", "wednesday", "thursday"],
                "preferred_periods": [1, 2, 3, 4],
                "notes": "Test teacher creation"
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/teachers/create", json=teacher_data, headers=auth_headers)
        
        # Check status code
        assert response.status_code == 200, f"Teacher creation failed: {response.text}"
        
        # Validate response
        data = response.json()
        assert data.get("success") == True, f"Success flag not true: {data}"
        assert "teacher_id" in data, "No teacher_id in response"
        assert "qr_code" in data, "No qr_code in response"
        
        # Validate user account creation
        user_account = data.get("user_account", {})
        assert user_account.get("created") == True, "User account not created"
        assert "temp_password" in user_account, "No temp_password in response"
        
        print(f"✓ Teacher created successfully: {data['teacher_id']}")
        print(f"  - User account: {user_account.get('email')}")
        print(f"  - Temp password: {user_account.get('temp_password')}")
    
    def test_validate_national_id(self, auth_headers):
        """Test POST /api/teachers/validate/national-id"""
        response = requests.post(
            f"{BASE_URL}/api/teachers/validate/national-id",
            json={"value": "1234567890"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Validation failed: {response.text}"
        
        data = response.json()
        assert "valid" in data, "No valid key in response"
        print(f"✓ National ID validation: valid={data['valid']}")
    
    def test_validate_email(self, auth_headers):
        """Test POST /api/teachers/validate/email"""
        response = requests.post(
            f"{BASE_URL}/api/teachers/validate/email",
            json={"value": "unique.email.test@test.com"},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Validation failed: {response.text}"
        
        data = response.json()
        assert "valid" in data, "No valid key in response"
        print(f"✓ Email validation: valid={data['valid']}")
    
    def test_list_teachers(self, auth_headers):
        """Test GET /api/teachers/"""
        response = requests.get(f"{BASE_URL}/api/teachers/", headers=auth_headers)
        assert response.status_code == 200, f"List teachers failed: {response.text}"
        
        data = response.json()
        assert "teachers" in data, "No teachers key in response"
        assert "total" in data, "No total key in response"
        print(f"✓ Listed {data['total']} teachers")


class TestPrincipalDashboard:
    """Test principal dashboard access"""
    
    @pytest.fixture
    def principal_token(self):
        """Get principal auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal@nassaq.com",
            "password": "Principal@123"
        })
        if response.status_code == 200:
            return response.json().get("access_token")
        pytest.skip("Principal login failed")
    
    @pytest.fixture
    def auth_headers(self, principal_token):
        return {"Authorization": f"Bearer {principal_token}", "Content-Type": "application/json"}
    
    def test_principal_auth_me(self, auth_headers):
        """Test GET /api/auth/me for principal"""
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers)
        assert response.status_code == 200, f"Auth me failed: {response.text}"
        
        data = response.json()
        assert data.get("email") == "principal@nassaq.com", "Email mismatch"
        assert data.get("role") == "school_principal", f"Role mismatch: {data.get('role')}"
        print(f"✓ Principal auth verified: {data.get('full_name', data.get('email'))}")
    
    def test_notifications_unread_count(self, auth_headers):
        """Test GET /api/notifications/unread-count"""
        response = requests.get(f"{BASE_URL}/api/notifications/unread-count", headers=auth_headers)
        assert response.status_code == 200, f"Notifications failed: {response.text}"
        
        data = response.json()
        # API returns unread_count key
        assert "unread_count" in data, "No unread_count in response"
        print(f"✓ Unread notifications: {data['unread_count']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
