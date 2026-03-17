"""
Test Registration Requests APIs and User Creation
Tests for:
- POST /api/users/create - Create new user (Platform Admin, Teacher)
- GET /api/registration-requests - Get pending registration requests
- POST /api/registration-requests/{id}/approve - Approve teacher request
- POST /api/registration-requests/{id}/reject - Reject teacher request
- POST /api/registration-requests/{id}/request-info - Request additional info
"""

import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "info@nassaqapp.com"
ADMIN_PASSWORD = "NassaqAdmin2026!##$$HBJ"


class TestAuthAndSetup:
    """Authentication and setup tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for admin"""
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
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_admin_login(self):
        """Test admin login works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "platform_admin"
        print(f"✓ Admin login successful - Role: {data['user']['role']}")


class TestUserCreation:
    """Test user creation API - POST /api/users/create"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["access_token"]
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def test_create_platform_admin_user(self, auth_headers):
        """Test creating a platform admin user"""
        unique_id = str(uuid.uuid4())[:8]
        user_data = {
            "email": f"TEST_admin_{unique_id}@nassaq.com",
            "password": "TestPass123!@#",
            "full_name": f"TEST مدير اختبار {unique_id}",
            "role": "platform_operations_manager",
            "phone": f"05{unique_id[:8]}",
            "region": "riyadh",
            "city": "riyadh",
            "permissions": ["view_dashboard", "view_schools", "view_users"]
        }
        
        response = requests.post(f"{BASE_URL}/api/users/create", json=user_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed to create user: {response.text}"
        
        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["full_name"] == user_data["full_name"]
        assert data["role"] == user_data["role"]
        assert data["must_change_password"] == True
        print(f"✓ Created platform user: {data['email']} with role: {data['role']}")
        
        # Cleanup - delete the test user
        requests.delete(f"{BASE_URL}/api/users/{data['id']}", headers=auth_headers)
    
    def test_create_teacher_user(self, auth_headers):
        """Test creating a teacher user directly"""
        unique_id = str(uuid.uuid4())[:8]
        user_data = {
            "email": f"TEST_teacher_{unique_id}@nassaq.com",
            "password": "TeacherPass123!@#",
            "full_name": f"TEST معلم اختبار {unique_id}",
            "role": "teacher",
            "phone": f"05{unique_id[:8]}",
            "region": "riyadh",
            "city": "riyadh",
            "school_name_ar": "مدرسة الاختبار",
            "school_name_en": "Test School",
            "permissions": ["view_classes", "manage_own_class", "record_attendance"]
        }
        
        response = requests.post(f"{BASE_URL}/api/users/create", json=user_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed to create teacher: {response.text}"
        
        data = response.json()
        assert data["email"] == user_data["email"]
        assert data["role"] == "teacher"
        assert data["school_name_ar"] == user_data["school_name_ar"]
        print(f"✓ Created teacher user: {data['email']}")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/users/{data['id']}", headers=auth_headers)
    
    def test_create_user_duplicate_email(self, auth_headers):
        """Test creating user with duplicate email fails"""
        # First create a user
        unique_id = str(uuid.uuid4())[:8]
        user_data = {
            "email": f"TEST_dup_{unique_id}@nassaq.com",
            "password": "TestPass123!@#",
            "full_name": f"TEST مستخدم مكرر {unique_id}",
            "role": "testing_account",
            "permissions": []
        }
        
        response1 = requests.post(f"{BASE_URL}/api/users/create", json=user_data, headers=auth_headers)
        assert response1.status_code == 200
        created_user = response1.json()
        
        # Try to create another user with same email
        response2 = requests.post(f"{BASE_URL}/api/users/create", json=user_data, headers=auth_headers)
        assert response2.status_code == 400
        assert "مستخدم" in response2.json().get("detail", "") or "email" in response2.json().get("detail", "").lower()
        print("✓ Duplicate email correctly rejected")
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/users/{created_user['id']}", headers=auth_headers)
    
    def test_create_user_invalid_role(self, auth_headers):
        """Test creating user with invalid role fails"""
        unique_id = str(uuid.uuid4())[:8]
        user_data = {
            "email": f"TEST_invalid_{unique_id}@nassaq.com",
            "password": "TestPass123!@#",
            "full_name": "TEST مستخدم غير صالح",
            "role": "invalid_role_xyz",
            "permissions": []
        }
        
        response = requests.post(f"{BASE_URL}/api/users/create", json=user_data, headers=auth_headers)
        assert response.status_code == 400
        print("✓ Invalid role correctly rejected")


class TestRegistrationRequests:
    """Test registration requests APIs"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["access_token"]
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    @pytest.fixture(scope="class")
    def test_request(self, auth_headers):
        """Create a test registration request"""
        unique_id = str(uuid.uuid4())[:8]
        request_data = {
            "full_name": f"TEST معلم طلب {unique_id}",
            "phone": f"05{unique_id[:8]}",
            "account_type": "teacher",
            "email": f"TEST_request_{unique_id}@test.com",
            "national_id": f"10{unique_id[:8]}",
            "subject": "الرياضيات",
            "educational_level": "ابتدائي",
            "school_mentioned": "مدرسة الاختبار",
            "country": "السعودية",
            "years_of_experience": "5"
        }
        
        response = requests.post(f"{BASE_URL}/api/registration-requests", json=request_data)
        assert response.status_code == 200, f"Failed to create request: {response.text}"
        return response.json()
    
    def test_get_registration_requests(self, auth_headers):
        """Test GET /api/registration-requests"""
        response = requests.get(f"{BASE_URL}/api/registration-requests", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "requests" in data
        assert "total" in data
        print(f"✓ Got {data['total']} registration requests")
    
    def test_get_pending_teacher_requests(self, auth_headers):
        """Test GET /api/registration-requests with filters"""
        response = requests.get(
            f"{BASE_URL}/api/registration-requests",
            params={"status": "pending", "account_type": "teacher"},
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "requests" in data
        # All returned requests should be pending teachers
        for req in data["requests"]:
            assert req.get("status") == "pending" or req.get("account_type") == "teacher"
        print(f"✓ Got {len(data['requests'])} pending teacher requests")
    
    def test_create_registration_request(self):
        """Test POST /api/registration-requests - Create new request"""
        unique_id = str(uuid.uuid4())[:8]
        request_data = {
            "full_name": f"TEST معلم جديد {unique_id}",
            "phone": f"05{unique_id[:8]}",
            "account_type": "teacher",
            "email": f"TEST_new_{unique_id}@test.com",
            "national_id": f"11{unique_id[:8]}",
            "subject": "العلوم",
            "educational_level": "متوسط",
            "school_mentioned": "مدرسة المستقبل",
            "country": "السعودية",
            "years_of_experience": "3"
        }
        
        response = requests.post(f"{BASE_URL}/api/registration-requests", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["full_name"] == request_data["full_name"]
        assert data["status"] == "pending"
        assert data["account_type"] == "teacher"
        print(f"✓ Created registration request: {data['id']}")
        return data["id"]


class TestApproveRequest:
    """Test approve teacher request API"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["access_token"]
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def test_approve_teacher_request(self, auth_headers):
        """Test POST /api/registration-requests/{id}/approve"""
        # First create a request to approve
        unique_id = str(uuid.uuid4())[:8]
        request_data = {
            "full_name": f"TEST معلم للموافقة {unique_id}",
            "phone": f"05{unique_id[:8]}",
            "account_type": "teacher",
            "email": f"TEST_approve_{unique_id}@test.com",
            "national_id": f"12{unique_id[:8]}",
            "subject": "اللغة العربية",
            "educational_level": "ثانوي",
            "school_mentioned": "ثانوية الملك فهد",
            "country": "السعودية",
            "years_of_experience": "7"
        }
        
        create_response = requests.post(f"{BASE_URL}/api/registration-requests", json=request_data)
        assert create_response.status_code == 200
        request_id = create_response.json()["id"]
        
        # Now approve the request
        approve_response = requests.post(
            f"{BASE_URL}/api/registration-requests/{request_id}/approve",
            json={"send_notification": True},
            headers=auth_headers
        )
        assert approve_response.status_code == 200, f"Approve failed: {approve_response.text}"
        
        data = approve_response.json()
        assert data["success"] == True
        assert "teacher_id" in data
        assert "temporary_password" in data
        assert "qr_code" in data
        assert "email" in data
        assert "message_template" in data
        
        # Verify teacher_id format (TCH-XXXXXX)
        assert data["teacher_id"].startswith("TCH-")
        
        print(f"✓ Approved request - Teacher ID: {data['teacher_id']}")
        print(f"  Email: {data['email']}")
        print(f"  Temp Password: {data['temporary_password'][:4]}****")
        
        # Cleanup - delete the created user
        if "user_id" in data:
            requests.delete(f"{BASE_URL}/api/users/{data['user_id']}", headers=auth_headers)
    
    def test_approve_nonexistent_request(self, auth_headers):
        """Test approving non-existent request returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/registration-requests/nonexistent-id-12345/approve",
            json={"send_notification": True},
            headers=auth_headers
        )
        assert response.status_code == 404
        print("✓ Non-existent request correctly returns 404")
    
    def test_approve_already_approved_request(self, auth_headers):
        """Test approving already approved request fails"""
        # Create and approve a request
        unique_id = str(uuid.uuid4())[:8]
        request_data = {
            "full_name": f"TEST معلم مكرر {unique_id}",
            "phone": f"05{unique_id[:8]}",
            "account_type": "teacher",
            "email": f"TEST_double_{unique_id}@test.com",
            "national_id": f"13{unique_id[:8]}",
            "subject": "الفيزياء",
            "educational_level": "ثانوي"
        }
        
        create_response = requests.post(f"{BASE_URL}/api/registration-requests", json=request_data)
        request_id = create_response.json()["id"]
        
        # First approval
        first_approve = requests.post(
            f"{BASE_URL}/api/registration-requests/{request_id}/approve",
            json={"send_notification": True},
            headers=auth_headers
        )
        assert first_approve.status_code == 200
        user_id = first_approve.json().get("user_id")
        
        # Second approval should fail
        second_approve = requests.post(
            f"{BASE_URL}/api/registration-requests/{request_id}/approve",
            json={"send_notification": True},
            headers=auth_headers
        )
        assert second_approve.status_code == 400
        print("✓ Double approval correctly rejected")
        
        # Cleanup
        if user_id:
            requests.delete(f"{BASE_URL}/api/users/{user_id}", headers=auth_headers)


class TestRejectRequest:
    """Test reject teacher request API"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["access_token"]
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def test_reject_teacher_request(self, auth_headers):
        """Test POST /api/registration-requests/{id}/reject"""
        # Create a request to reject
        unique_id = str(uuid.uuid4())[:8]
        request_data = {
            "full_name": f"TEST معلم للرفض {unique_id}",
            "phone": f"05{unique_id[:8]}",
            "account_type": "teacher",
            "email": f"TEST_reject_{unique_id}@test.com",
            "national_id": f"14{unique_id[:8]}",
            "subject": "الكيمياء",
            "educational_level": "ثانوي"
        }
        
        create_response = requests.post(f"{BASE_URL}/api/registration-requests", json=request_data)
        request_id = create_response.json()["id"]
        
        # Reject the request
        reject_response = requests.post(
            f"{BASE_URL}/api/registration-requests/{request_id}/reject",
            json={"reason": "عدم استيفاء الشروط المطلوبة - اختبار"},
            headers=auth_headers
        )
        assert reject_response.status_code == 200, f"Reject failed: {reject_response.text}"
        
        data = reject_response.json()
        assert data["success"] == True
        assert "rejection_reason" in data
        print(f"✓ Rejected request with reason: {data['rejection_reason'][:30]}...")
    
    def test_reject_without_reason(self, auth_headers):
        """Test rejecting without reason fails"""
        # Create a request
        unique_id = str(uuid.uuid4())[:8]
        request_data = {
            "full_name": f"TEST معلم بدون سبب {unique_id}",
            "phone": f"05{unique_id[:8]}",
            "account_type": "teacher",
            "email": f"TEST_noreason_{unique_id}@test.com"
        }
        
        create_response = requests.post(f"{BASE_URL}/api/registration-requests", json=request_data)
        request_id = create_response.json()["id"]
        
        # Try to reject without reason
        reject_response = requests.post(
            f"{BASE_URL}/api/registration-requests/{request_id}/reject",
            json={"reason": ""},
            headers=auth_headers
        )
        assert reject_response.status_code == 400
        print("✓ Rejection without reason correctly rejected")
    
    def test_reject_with_short_reason(self, auth_headers):
        """Test rejecting with too short reason fails"""
        unique_id = str(uuid.uuid4())[:8]
        request_data = {
            "full_name": f"TEST معلم سبب قصير {unique_id}",
            "phone": f"05{unique_id[:8]}",
            "account_type": "teacher",
            "email": f"TEST_short_{unique_id}@test.com"
        }
        
        create_response = requests.post(f"{BASE_URL}/api/registration-requests", json=request_data)
        request_id = create_response.json()["id"]
        
        # Try to reject with short reason
        reject_response = requests.post(
            f"{BASE_URL}/api/registration-requests/{request_id}/reject",
            json={"reason": "لا"},
            headers=auth_headers
        )
        assert reject_response.status_code == 400
        print("✓ Short rejection reason correctly rejected")


class TestRequestMoreInfo:
    """Test request more info API"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        token = response.json()["access_token"]
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def test_request_more_info(self, auth_headers):
        """Test POST /api/registration-requests/{id}/request-info"""
        # Create a request
        unique_id = str(uuid.uuid4())[:8]
        request_data = {
            "full_name": f"TEST معلم معلومات {unique_id}",
            "phone": f"05{unique_id[:8]}",
            "account_type": "teacher",
            "email": f"TEST_info_{unique_id}@test.com",
            "national_id": f"15{unique_id[:8]}",
            "subject": "الأحياء",
            "educational_level": "متوسط"
        }
        
        create_response = requests.post(f"{BASE_URL}/api/registration-requests", json=request_data)
        request_id = create_response.json()["id"]
        
        # Request more info
        info_response = requests.post(
            f"{BASE_URL}/api/registration-requests/{request_id}/request-info",
            json={"message": "يرجى إرفاق صورة من الشهادة الجامعية وشهادة الخبرة"},
            headers=auth_headers
        )
        assert info_response.status_code == 200, f"Request info failed: {info_response.text}"
        
        data = info_response.json()
        assert data["success"] == True
        print(f"✓ Requested more info successfully")
    
    def test_request_info_short_message(self, auth_headers):
        """Test requesting info with short message fails"""
        unique_id = str(uuid.uuid4())[:8]
        request_data = {
            "full_name": f"TEST معلم رسالة قصيرة {unique_id}",
            "phone": f"05{unique_id[:8]}",
            "account_type": "teacher",
            "email": f"TEST_shortmsg_{unique_id}@test.com"
        }
        
        create_response = requests.post(f"{BASE_URL}/api/registration-requests", json=request_data)
        request_id = create_response.json()["id"]
        
        # Try with short message
        info_response = requests.post(
            f"{BASE_URL}/api/registration-requests/{request_id}/request-info",
            json={"message": "أرسل"},
            headers=auth_headers
        )
        assert info_response.status_code == 400
        print("✓ Short info message correctly rejected")
    
    def test_request_info_on_approved_request(self, auth_headers):
        """Test requesting info on approved request fails"""
        # Create and approve a request
        unique_id = str(uuid.uuid4())[:8]
        request_data = {
            "full_name": f"TEST معلم موافق {unique_id}",
            "phone": f"05{unique_id[:8]}",
            "account_type": "teacher",
            "email": f"TEST_approved_{unique_id}@test.com",
            "national_id": f"16{unique_id[:8]}"
        }
        
        create_response = requests.post(f"{BASE_URL}/api/registration-requests", json=request_data)
        request_id = create_response.json()["id"]
        
        # Approve first
        approve_response = requests.post(
            f"{BASE_URL}/api/registration-requests/{request_id}/approve",
            json={"send_notification": True},
            headers=auth_headers
        )
        user_id = approve_response.json().get("user_id")
        
        # Try to request info on approved request
        info_response = requests.post(
            f"{BASE_URL}/api/registration-requests/{request_id}/request-info",
            json={"message": "يرجى إرفاق المزيد من المستندات"},
            headers=auth_headers
        )
        assert info_response.status_code == 400
        print("✓ Request info on approved request correctly rejected")
        
        # Cleanup
        if user_id:
            requests.delete(f"{BASE_URL}/api/users/{user_id}", headers=auth_headers)


class TestUnauthorizedAccess:
    """Test unauthorized access to APIs"""
    
    def test_get_requests_without_auth(self):
        """Test GET /api/registration-requests without auth fails"""
        response = requests.get(f"{BASE_URL}/api/registration-requests")
        assert response.status_code in [401, 403]
        print("✓ Unauthorized access to registration requests correctly rejected")
    
    def test_approve_without_auth(self):
        """Test approve without auth fails"""
        response = requests.post(
            f"{BASE_URL}/api/registration-requests/some-id/approve",
            json={"send_notification": True}
        )
        assert response.status_code in [401, 403]
        print("✓ Unauthorized approve correctly rejected")
    
    def test_create_user_without_auth(self):
        """Test create user without auth fails"""
        response = requests.post(
            f"{BASE_URL}/api/users/create",
            json={
                "email": "test@test.com",
                "password": "test123",
                "full_name": "Test",
                "role": "teacher"
            }
        )
        assert response.status_code in [401, 403]
        print("✓ Unauthorized user creation correctly rejected")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
