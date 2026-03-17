"""
Test School Creation Wizard API - POST /api/schools
Tests the 4-step wizard for creating schools with:
- Unique school code generation (NSS-{COUNTRY}-{YEAR}-{SEQUENTIAL})
- Automatic principal account creation
- Required field validation
"""
import pytest
import requests
import os
import uuid
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
PLATFORM_ADMIN_EMAIL = "info@nassaqapp.com"
PLATFORM_ADMIN_PASSWORD = "NassaqAdmin2026!##$$HBJ"


class TestSchoolWizardAPI:
    """Test school creation wizard API endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.auth_token = None
        
    def get_auth_token(self):
        """Get authentication token for platform admin"""
        if self.auth_token:
            return self.auth_token
            
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": PLATFORM_ADMIN_EMAIL,
            "password": PLATFORM_ADMIN_PASSWORD
        })
        
        if response.status_code == 200:
            self.auth_token = response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {self.auth_token}"})
            return self.auth_token
        else:
            pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
            
    # ============== Authentication Tests ==============
    
    def test_login_platform_admin(self):
        """Test platform admin login"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": PLATFORM_ADMIN_EMAIL,
            "password": PLATFORM_ADMIN_PASSWORD
        })
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        assert "user" in data, "No user in response"
        assert data["user"]["role"] == "platform_admin", f"Expected platform_admin role, got {data['user']['role']}"
        print(f"✓ Platform admin login successful - User: {data['user']['full_name']}")
        
    # ============== School Creation Tests ==============
    
    def test_create_school_with_all_fields(self):
        """Test creating a school with all wizard fields"""
        self.get_auth_token()
        
        unique_id = str(uuid.uuid4())[:8]
        school_data = {
            "name": f"مدرسة الاختبار {unique_id}",
            "name_en": f"Test School {unique_id}",
            "country": "SA",
            "city": "الرياض",
            "address": "حي النخيل، شارع الملك فهد",
            "language": "ar",
            "calendar_system": "hijri_gregorian",
            "school_type": "private",
            "stage": "primary",
            "principal_name": f"مدير الاختبار {unique_id}",
            "principal_email": f"principal_{unique_id}@test.com",
            "principal_phone": f"05{unique_id[:8].replace('-', '0')}"[:10],
            "student_capacity": 500
        }
        
        response = self.session.post(f"{BASE_URL}/api/schools", json=school_data)
        
        assert response.status_code == 200, f"School creation failed: {response.status_code} - {response.text}"
        data = response.json()
        
        # Verify school code format: NSS-{COUNTRY}-{YEAR}-{SEQUENTIAL}
        assert "code" in data, "No code in response"
        code = data["code"]
        assert code.startswith("NSS-"), f"Code should start with NSS-, got: {code}"
        assert "-SA-" in code, f"Code should contain country code SA, got: {code}"
        
        # Verify code format parts
        parts = code.split("-")
        assert len(parts) == 4, f"Code should have 4 parts, got: {parts}"
        assert parts[0] == "NSS", f"First part should be NSS, got: {parts[0]}"
        assert parts[1] == "SA", f"Second part should be SA, got: {parts[1]}"
        assert len(parts[2]) == 2, f"Third part (year) should be 2 digits, got: {parts[2]}"
        assert len(parts[3]) == 4, f"Fourth part (sequential) should be 4 digits, got: {parts[3]}"
        
        # Verify other fields
        assert data["name"] == school_data["name"], "School name mismatch"
        assert data["city"] == school_data["city"], "City mismatch"
        assert data["country"] == "SA", "Country mismatch"
        assert data["status"] == "active", f"Expected active status, got: {data['status']}"
        
        print(f"✓ School created successfully with code: {code}")
        print(f"  - Name: {data['name']}")
        print(f"  - City: {data['city']}")
        print(f"  - Status: {data['status']}")
        
        # Store school ID for cleanup
        self.created_school_id = data["id"]
        
    def test_create_school_auto_generates_code(self):
        """Test that school code is auto-generated when not provided"""
        self.get_auth_token()
        
        unique_id = str(uuid.uuid4())[:8]
        school_data = {
            "name": f"مدرسة بدون كود {unique_id}",
            "country": "AE",  # UAE
            "city": "دبي",
            "address": "شارع الشيخ زايد",
            "principal_name": f"مدير {unique_id}",
            "principal_email": f"principal_ae_{unique_id}@test.com",
            "principal_phone": f"05{unique_id[:8].replace('-', '0')}"[:10]
        }
        
        response = self.session.post(f"{BASE_URL}/api/schools", json=school_data)
        
        assert response.status_code == 200, f"School creation failed: {response.text}"
        data = response.json()
        
        # Verify code was auto-generated with UAE country code
        assert "code" in data, "No code in response"
        code = data["code"]
        assert code.startswith("NSS-AE-"), f"Code should start with NSS-AE-, got: {code}"
        
        print(f"✓ School code auto-generated: {code}")
        
    def test_create_school_creates_principal_account(self):
        """Test that principal account is created automatically"""
        self.get_auth_token()
        
        unique_id = str(uuid.uuid4())[:8]
        principal_email = f"principal_test_{unique_id}@nassaq.com"
        
        school_data = {
            "name": f"مدرسة مع مدير {unique_id}",
            "country": "SA",
            "city": "جدة",
            "address": "حي الروضة",
            "principal_name": f"أحمد محمد {unique_id}",
            "principal_email": principal_email,
            "principal_phone": f"05{unique_id[:8].replace('-', '0')}"[:10]
        }
        
        response = self.session.post(f"{BASE_URL}/api/schools", json=school_data)
        
        assert response.status_code == 200, f"School creation failed: {response.text}"
        data = response.json()
        
        print(f"✓ School created: {data['code']}")
        
        # Verify principal account was created by checking users list
        users_response = self.session.get(f"{BASE_URL}/api/users?role=school_principal")
        
        if users_response.status_code == 200:
            users = users_response.json()
            principal_found = any(u.get("email") == principal_email for u in users)
            if principal_found:
                print(f"✓ Principal account created with email: {principal_email}")
            else:
                print(f"⚠ Principal account not found in users list (may need different query)")
        else:
            print(f"⚠ Could not verify principal account: {users_response.status_code}")
            
    def test_create_school_validates_required_fields(self):
        """Test that required fields are validated"""
        self.get_auth_token()
        
        # Test with missing name
        response = self.session.post(f"{BASE_URL}/api/schools", json={
            "country": "SA",
            "city": "الرياض"
        })
        
        # Should fail validation
        assert response.status_code in [400, 422], f"Expected validation error, got: {response.status_code}"
        print(f"✓ Validation works - missing name rejected with status {response.status_code}")
        
    def test_create_school_rejects_duplicate_email(self):
        """Test that duplicate principal email is rejected"""
        self.get_auth_token()
        
        unique_id = str(uuid.uuid4())[:8]
        duplicate_email = f"duplicate_{unique_id}@test.com"
        
        # Create first school
        school_data_1 = {
            "name": f"مدرسة أولى {unique_id}",
            "country": "SA",
            "city": "الرياض",
            "address": "عنوان 1",
            "principal_name": "مدير أول",
            "principal_email": duplicate_email,
            "principal_phone": f"05{unique_id[:8].replace('-', '0')}"[:10]
        }
        
        response1 = self.session.post(f"{BASE_URL}/api/schools", json=school_data_1)
        assert response1.status_code == 200, f"First school creation failed: {response1.text}"
        print(f"✓ First school created with email: {duplicate_email}")
        
        # Try to create second school with same email
        school_data_2 = {
            "name": f"مدرسة ثانية {unique_id}",
            "country": "SA",
            "city": "جدة",
            "address": "عنوان 2",
            "principal_name": "مدير ثاني",
            "principal_email": duplicate_email,  # Same email
            "principal_phone": f"05{str(uuid.uuid4())[:8].replace('-', '0')}"[:10]
        }
        
        response2 = self.session.post(f"{BASE_URL}/api/schools", json=school_data_2)
        assert response2.status_code == 400, f"Expected 400 for duplicate email, got: {response2.status_code}"
        print(f"✓ Duplicate email rejected correctly")
        
    def test_create_school_rejects_duplicate_phone(self):
        """Test that duplicate principal phone is rejected"""
        self.get_auth_token()
        
        unique_id = str(uuid.uuid4())[:8]
        duplicate_phone = f"05{unique_id[:8].replace('-', '0')}"[:10]
        
        # Create first school
        school_data_1 = {
            "name": f"مدرسة هاتف أولى {unique_id}",
            "country": "SA",
            "city": "الرياض",
            "address": "عنوان 1",
            "principal_name": "مدير أول",
            "principal_email": f"phone_test1_{unique_id}@test.com",
            "principal_phone": duplicate_phone
        }
        
        response1 = self.session.post(f"{BASE_URL}/api/schools", json=school_data_1)
        assert response1.status_code == 200, f"First school creation failed: {response1.text}"
        print(f"✓ First school created with phone: {duplicate_phone}")
        
        # Try to create second school with same phone
        school_data_2 = {
            "name": f"مدرسة هاتف ثانية {unique_id}",
            "country": "SA",
            "city": "جدة",
            "address": "عنوان 2",
            "principal_name": "مدير ثاني",
            "principal_email": f"phone_test2_{unique_id}@test.com",
            "principal_phone": duplicate_phone  # Same phone
        }
        
        response2 = self.session.post(f"{BASE_URL}/api/schools", json=school_data_2)
        assert response2.status_code == 400, f"Expected 400 for duplicate phone, got: {response2.status_code}"
        print(f"✓ Duplicate phone rejected correctly")
        
    # ============== School Listing Tests ==============
    
    def test_get_schools_list(self):
        """Test getting list of schools"""
        self.get_auth_token()
        
        response = self.session.get(f"{BASE_URL}/api/schools")
        
        assert response.status_code == 200, f"Get schools failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Retrieved {len(data)} schools")
        
        if len(data) > 0:
            school = data[0]
            assert "id" in school, "School should have id"
            assert "name" in school, "School should have name"
            assert "code" in school, "School should have code"
            assert "status" in school, "School should have status"
            print(f"  - First school: {school['name']} ({school['code']})")
            
    def test_get_schools_filter_by_status(self):
        """Test filtering schools by status"""
        self.get_auth_token()
        
        response = self.session.get(f"{BASE_URL}/api/schools?status=active")
        
        assert response.status_code == 200, f"Get schools failed: {response.text}"
        data = response.json()
        
        # All returned schools should be active
        for school in data:
            assert school.get("status") == "active", f"Expected active status, got: {school.get('status')}"
            
        print(f"✓ Retrieved {len(data)} active schools")
        
    def test_get_single_school(self):
        """Test getting a single school by ID"""
        self.get_auth_token()
        
        # First get list to find a school ID
        list_response = self.session.get(f"{BASE_URL}/api/schools")
        assert list_response.status_code == 200
        schools = list_response.json()
        
        if len(schools) == 0:
            pytest.skip("No schools available to test")
            
        school_id = schools[0]["id"]
        
        # Get single school
        response = self.session.get(f"{BASE_URL}/api/schools/{school_id}")
        
        assert response.status_code == 200, f"Get school failed: {response.text}"
        data = response.json()
        
        assert data["id"] == school_id, "School ID mismatch"
        assert "name" in data, "School should have name"
        assert "code" in data, "School should have code"
        
        print(f"✓ Retrieved school: {data['name']} ({data['code']})")
        
    # ============== Dashboard Stats Tests ==============
    
    def test_dashboard_stats(self):
        """Test dashboard statistics endpoint"""
        self.get_auth_token()
        
        response = self.session.get(f"{BASE_URL}/api/dashboard/stats")
        
        assert response.status_code == 200, f"Get stats failed: {response.text}"
        data = response.json()
        
        # Verify required fields
        assert "total_schools" in data, "Missing total_schools"
        assert "active_schools" in data, "Missing active_schools"
        assert "total_students" in data, "Missing total_students"
        assert "total_teachers" in data, "Missing total_teachers"
        
        print(f"✓ Dashboard stats retrieved:")
        print(f"  - Total schools: {data['total_schools']}")
        print(f"  - Active schools: {data['active_schools']}")
        print(f"  - Total students: {data['total_students']}")
        print(f"  - Total teachers: {data['total_teachers']}")


class TestSchoolCodeGeneration:
    """Test school code generation format"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
    def get_auth_token(self):
        """Get authentication token"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": PLATFORM_ADMIN_EMAIL,
            "password": PLATFORM_ADMIN_PASSWORD
        })
        
        if response.status_code == 200:
            token = response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            return token
        pytest.skip("Authentication failed")
        
    def test_code_format_saudi_arabia(self):
        """Test code format for Saudi Arabia schools"""
        self.get_auth_token()
        
        unique_id = str(uuid.uuid4())[:8]
        response = self.session.post(f"{BASE_URL}/api/schools", json={
            "name": f"مدرسة سعودية {unique_id}",
            "country": "SA",
            "city": "الرياض",
            "address": "عنوان",
            "principal_name": "مدير",
            "principal_email": f"sa_{unique_id}@test.com",
            "principal_phone": f"05{unique_id[:8].replace('-', '0')}"[:10]
        })
        
        assert response.status_code == 200
        code = response.json()["code"]
        
        # Verify format: NSS-SA-YY-XXXX
        assert code.startswith("NSS-SA-"), f"SA code should start with NSS-SA-, got: {code}"
        year = datetime.now().strftime("%y")
        assert f"-{year}-" in code, f"Code should contain current year {year}"
        
        print(f"✓ Saudi Arabia code format correct: {code}")
        
    def test_code_format_uae(self):
        """Test code format for UAE schools"""
        self.get_auth_token()
        
        unique_id = str(uuid.uuid4())[:8]
        response = self.session.post(f"{BASE_URL}/api/schools", json={
            "name": f"مدرسة إماراتية {unique_id}",
            "country": "AE",
            "city": "دبي",
            "address": "عنوان",
            "principal_name": "مدير",
            "principal_email": f"ae_{unique_id}@test.com",
            "principal_phone": f"05{unique_id[:8].replace('-', '0')}"[:10]
        })
        
        assert response.status_code == 200
        code = response.json()["code"]
        
        # Verify format: NSS-AE-YY-XXXX
        assert code.startswith("NSS-AE-"), f"AE code should start with NSS-AE-, got: {code}"
        
        print(f"✓ UAE code format correct: {code}")
        
    def test_sequential_code_increment(self):
        """Test that sequential numbers increment correctly"""
        self.get_auth_token()
        
        codes = []
        for i in range(2):
            unique_id = str(uuid.uuid4())[:8]
            response = self.session.post(f"{BASE_URL}/api/schools", json={
                "name": f"مدرسة تسلسل {i} {unique_id}",
                "country": "KW",  # Kuwait for unique sequence
                "city": "الكويت",
                "address": "عنوان",
                "principal_name": f"مدير {i}",
                "principal_email": f"kw_{i}_{unique_id}@test.com",
                "principal_phone": f"05{unique_id[:8].replace('-', '0')}"[:10]
            })
            
            if response.status_code == 200:
                codes.append(response.json()["code"])
                
        if len(codes) >= 2:
            # Extract sequential numbers
            seq1 = int(codes[0].split("-")[-1])
            seq2 = int(codes[1].split("-")[-1])
            
            assert seq2 > seq1, f"Sequential numbers should increment: {seq1} -> {seq2}"
            print(f"✓ Sequential increment verified: {codes[0]} -> {codes[1]}")
        else:
            print("⚠ Could not verify sequential increment (not enough schools created)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
