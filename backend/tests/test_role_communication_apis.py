"""
Test Role Switching and Communication APIs - Iteration 57
Tests for:
1. Role Switcher APIs (/api/user-roles/*)
2. Communication APIs (/api/communication/*)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@nassaq.com"
ADMIN_PASSWORD = "Admin@123"


class TestAdminLogin:
    """Test admin login to get token"""
    
    def test_admin_login(self):
        """Test admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        assert data.get("user", {}).get("role") == "platform_admin", "User is not platform_admin"
        print(f"Admin login successful, role: {data.get('user', {}).get('role')}")
        return data["access_token"]


@pytest.fixture(scope="module")
def admin_token():
    """Get admin token for authenticated requests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Admin login failed - skipping authenticated tests")


@pytest.fixture
def auth_headers(admin_token):
    """Get auth headers"""
    return {"Authorization": f"Bearer {admin_token}"}


class TestUserRolesAPIs:
    """Test User Roles APIs - /api/user-roles/*"""
    
    def test_get_my_roles(self, auth_headers):
        """Test GET /api/user-roles/my-roles - Get available roles for current user"""
        response = requests.get(f"{BASE_URL}/api/user-roles/my-roles", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get roles: {response.text}"
        
        data = response.json()
        assert "current_role" in data, "Missing current_role in response"
        assert "available_roles" in data, "Missing available_roles in response"
        assert "can_switch" in data, "Missing can_switch in response"
        
        # Platform admin should have multiple roles available (including preview as school principal)
        available_roles = data.get("available_roles", [])
        assert len(available_roles) >= 1, "Should have at least 1 role available"
        
        # Check role structure
        for role in available_roles:
            assert "role" in role, "Role missing 'role' field"
            assert "role_name_ar" in role, "Role missing 'role_name_ar' field"
            assert "role_name_en" in role, "Role missing 'role_name_en' field"
            assert "is_current" in role, "Role missing 'is_current' field"
        
        print(f"Current role: {data.get('current_role')}")
        print(f"Available roles count: {len(available_roles)}")
        print(f"Can switch: {data.get('can_switch')}")
    
    def test_get_my_roles_unauthorized(self):
        """Test GET /api/user-roles/my-roles without auth"""
        response = requests.get(f"{BASE_URL}/api/user-roles/my-roles")
        assert response.status_code in [401, 403], "Should require authentication"
    
    def test_switch_role_to_school_principal(self, auth_headers):
        """Test POST /api/user-roles/switch - Switch to school principal preview"""
        # First get available roles to find a school to preview
        roles_response = requests.get(f"{BASE_URL}/api/user-roles/my-roles", headers=auth_headers)
        assert roles_response.status_code == 200
        
        available_roles = roles_response.json().get("available_roles", [])
        
        # Find a school principal preview role
        preview_role = None
        for role in available_roles:
            if role.get("role") == "school_principal" and role.get("is_preview"):
                preview_role = role
                break
        
        if not preview_role:
            pytest.skip("No school principal preview role available")
        
        # Switch to school principal
        response = requests.post(f"{BASE_URL}/api/user-roles/switch", 
            headers=auth_headers,
            json={
                "target_role": "school_principal",
                "target_tenant_id": preview_role.get("tenant_id")
            }
        )
        assert response.status_code == 200, f"Failed to switch role: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Switch should be successful"
        assert "access_token" in data, "Should return new access token"
        assert data.get("role") == "school_principal", "Should switch to school_principal"
        
        print(f"Switched to: {data.get('role')} at {data.get('tenant_name')}")
    
    def test_return_to_original_role(self, auth_headers):
        """Test POST /api/user-roles/return-to-original"""
        response = requests.post(f"{BASE_URL}/api/user-roles/return-to-original", headers=auth_headers)
        assert response.status_code == 200, f"Failed to return to original: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Return should be successful"
        assert "access_token" in data, "Should return new access token"
        
        print(f"Returned to original role: {data.get('role')}")
    
    def test_get_switch_history(self, auth_headers):
        """Test GET /api/user-roles/switch-history"""
        response = requests.get(f"{BASE_URL}/api/user-roles/switch-history", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get switch history: {response.text}"
        
        data = response.json()
        assert "history" in data, "Missing history in response"
        
        print(f"Switch history entries: {len(data.get('history', []))}")


class TestCommunicationAPIs:
    """Test Communication APIs - /api/communication/*"""
    
    def test_get_communication_stats(self, auth_headers):
        """Test GET /api/communication/stats"""
        response = requests.get(f"{BASE_URL}/api/communication/stats", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get stats: {response.text}"
        
        data = response.json()
        # Check expected fields
        expected_fields = ["sent", "scheduled", "drafts", "templates"]
        for field in expected_fields:
            assert field in data, f"Missing {field} in stats"
        
        print(f"Communication stats: sent={data.get('sent')}, scheduled={data.get('scheduled')}")
    
    def test_get_audience_counts(self, auth_headers):
        """Test GET /api/communication/audience-counts"""
        response = requests.get(f"{BASE_URL}/api/communication/audience-counts", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get audience counts: {response.text}"
        
        data = response.json()
        # Check expected audience types
        expected_audiences = ["all", "schools", "teachers", "students"]
        for audience in expected_audiences:
            assert audience in data, f"Missing {audience} in audience counts"
            assert isinstance(data[audience], int), f"{audience} should be an integer"
        
        print(f"Audience counts: all={data.get('all')}, schools={data.get('schools')}, teachers={data.get('teachers')}, students={data.get('students')}")
    
    def test_get_scheduled_messages(self, auth_headers):
        """Test GET /api/communication/scheduled"""
        response = requests.get(f"{BASE_URL}/api/communication/scheduled", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get scheduled messages: {response.text}"
        
        data = response.json()
        assert "messages" in data, "Missing messages in response"
        assert isinstance(data["messages"], list), "messages should be a list"
        
        print(f"Scheduled messages count: {len(data.get('messages', []))}")
    
    def test_get_sent_messages(self, auth_headers):
        """Test GET /api/communication/sent"""
        response = requests.get(f"{BASE_URL}/api/communication/sent", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get sent messages: {response.text}"
        
        data = response.json()
        assert "messages" in data, "Missing messages in response"
        assert isinstance(data["messages"], list), "messages should be a list"
        
        print(f"Sent messages count: {len(data.get('messages', []))}")
    
    def test_send_broadcast_message(self, auth_headers):
        """Test POST /api/communication/broadcast - Send broadcast message"""
        response = requests.post(f"{BASE_URL}/api/communication/broadcast",
            headers=auth_headers,
            json={
                "title": "TEST_رسالة اختبار",
                "content": "هذه رسالة اختبار من نظام الاختبار الآلي",
                "audience": "all",
                "channels": ["in_app"]
            }
        )
        assert response.status_code == 200, f"Failed to send broadcast: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, "Broadcast should be successful"
        assert "message_id" in data, "Should return message_id"
        assert "recipients_count" in data, "Should return recipients_count"
        
        print(f"Broadcast sent to {data.get('recipients_count')} recipients")
    
    def test_get_message_templates(self, auth_headers):
        """Test GET /api/communication/templates"""
        response = requests.get(f"{BASE_URL}/api/communication/templates", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get templates: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Templates should be a list"
        
        if len(data) > 0:
            template = data[0]
            assert "id" in template, "Template missing id"
            assert "name" in template, "Template missing name"
        
        print(f"Message templates count: {len(data)}")
    
    def test_get_audience_stats(self, auth_headers):
        """Test GET /api/communication/audience"""
        response = requests.get(f"{BASE_URL}/api/communication/audience", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get audience stats: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Audience stats should be a list"
        
        if len(data) > 0:
            audience = data[0]
            assert "id" in audience, "Audience missing id"
            assert "name" in audience, "Audience missing name"
            assert "count" in audience, "Audience missing count"
        
        print(f"Audience groups: {len(data)}")


class TestTeacherRequestsAPIs:
    """Test Teacher Registration Requests APIs"""
    
    def test_get_teacher_requests(self, auth_headers):
        """Test GET /api/registration-requests - Get teacher registration requests"""
        response = requests.get(f"{BASE_URL}/api/registration-requests", 
            headers=auth_headers,
            params={"account_type": "teacher"}
        )
        assert response.status_code == 200, f"Failed to get requests: {response.text}"
        
        data = response.json()
        # Handle both response formats
        requests_list = data.get("requests", data) if isinstance(data, dict) else data
        assert isinstance(requests_list, list), "Requests should be a list"
        
        print(f"Teacher requests count: {len(requests_list)}")
        
        # Check request structure if any exist
        if len(requests_list) > 0:
            request = requests_list[0]
            expected_fields = ["id", "full_name", "email", "status"]
            for field in expected_fields:
                assert field in request, f"Request missing {field}"
            print(f"First request status: {request.get('status')}")


class TestNotificationsAPIs:
    """Test Notifications APIs"""
    
    def test_get_notifications(self, auth_headers):
        """Test GET /api/notifications"""
        response = requests.get(f"{BASE_URL}/api/notifications", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get notifications: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Notifications should be a list"
        
        print(f"Notifications count: {len(data)}")
    
    def test_get_notifications_analytics(self, auth_headers):
        """Test GET /api/notifications/analytics"""
        response = requests.get(f"{BASE_URL}/api/notifications/analytics", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get analytics: {response.text}"
        
        data = response.json()
        print(f"Notifications analytics: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
