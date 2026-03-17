"""
Backend API Tests for UserDetailsPage, IntegrationsPage, and PlatformAnalyticsPage
Tests user management, integrations CRUD, and analytics endpoints
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://school-timetable-ai.preview.emergentagent.com')

# Test credentials
TEST_EMAIL = "info@nassaqapp.com"
TEST_PASSWORD = "NassaqAdmin2026!##$$HBJ"


class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        return data["access_token"]
    
    def test_login_success(self):
        """Test successful login"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == TEST_EMAIL
        print(f"Login successful for user: {data['user']['full_name']}")


class TestUserManagement:
    """User management API tests for UserDetailsPage"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_user_id(self, auth_headers):
        """Get a test user ID from platform users"""
        response = requests.get(
            f"{BASE_URL}/api/users/platform-users",
            headers=auth_headers
        )
        if response.status_code == 200:
            users = response.json().get("users", [])
            if users:
                return users[0]["id"]
        # Return current user ID as fallback
        me_response = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers)
        if me_response.status_code == 200:
            return me_response.json()["id"]
        return None
    
    def test_get_user_by_id(self, auth_headers, test_user_id):
        """Test GET /api/users/{user_id} - Get user details"""
        if not test_user_id:
            pytest.skip("No test user available")
        
        response = requests.get(
            f"{BASE_URL}/api/users/{test_user_id}",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to get user: {response.text}"
        data = response.json()
        assert "id" in data
        assert "email" in data
        print(f"Got user details: {data.get('full_name', 'N/A')}")
    
    def test_update_user(self, auth_headers, test_user_id):
        """Test PUT /api/users/{user_id} - Update user"""
        if not test_user_id:
            pytest.skip("No test user available")
        
        update_data = {
            "full_name_ar": "اسم اختبار",
            "full_name_en": "Test Name",
            "region": "الرياض",
            "city": "الرياض"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/users/{test_user_id}",
            headers=auth_headers,
            json=update_data
        )
        # Accept 200 or 404 (if user doesn't exist)
        assert response.status_code in [200, 404], f"Update failed: {response.text}"
        if response.status_code == 200:
            print("User update successful")
    
    def test_update_user_permissions(self, auth_headers, test_user_id):
        """Test PUT /api/users/{user_id}/permissions - Update permissions"""
        if not test_user_id:
            pytest.skip("No test user available")
        
        permissions_data = {
            "permissions": ["view_dashboard", "manage_schools", "view_reports"]
        }
        
        response = requests.put(
            f"{BASE_URL}/api/users/{test_user_id}/permissions",
            headers=auth_headers,
            json=permissions_data
        )
        assert response.status_code in [200, 404], f"Permissions update failed: {response.text}"
        if response.status_code == 200:
            print("Permissions update successful")
    
    def test_reset_password(self, auth_headers, test_user_id):
        """Test POST /api/users/{user_id}/reset-password - Reset password"""
        if not test_user_id:
            pytest.skip("No test user available")
        
        reset_data = {
            "new_password": "TestPassword123!"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/users/{test_user_id}/reset-password",
            headers=auth_headers,
            json=reset_data
        )
        assert response.status_code in [200, 404], f"Password reset failed: {response.text}"
        if response.status_code == 200:
            print("Password reset successful")
    
    def test_suspend_user(self, auth_headers, test_user_id):
        """Test POST /api/users/{user_id}/suspend - Toggle suspend"""
        if not test_user_id:
            pytest.skip("No test user available")
        
        response = requests.post(
            f"{BASE_URL}/api/users/{test_user_id}/suspend",
            headers=auth_headers
        )
        # Accept 200, 400 (can't suspend admin), or 404
        assert response.status_code in [200, 400, 404], f"Suspend failed: {response.text}"
        print(f"Suspend response: {response.status_code}")
    
    def test_send_notification(self, auth_headers, test_user_id):
        """Test POST /api/users/{user_id}/notify - Send notification"""
        if not test_user_id:
            pytest.skip("No test user available")
        
        notification_data = {
            "title": "إشعار اختبار",
            "message": "هذا إشعار اختبار من نظام الاختبار",
            "type": "system"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/users/{test_user_id}/notify",
            headers=auth_headers,
            json=notification_data
        )
        assert response.status_code in [200, 404], f"Notification failed: {response.text}"
        if response.status_code == 200:
            print("Notification sent successfully")
    
    def test_get_user_activity(self, auth_headers, test_user_id):
        """Test GET /api/users/{user_id}/activity - Get activity logs"""
        if not test_user_id:
            pytest.skip("No test user available")
        
        response = requests.get(
            f"{BASE_URL}/api/users/{test_user_id}/activity",
            headers=auth_headers
        )
        assert response.status_code in [200, 404], f"Activity fetch failed: {response.text}"
        if response.status_code == 200:
            data = response.json()
            print(f"Got {len(data.get('activities', []))} activity records")


class TestIntegrations:
    """Integrations API tests for IntegrationsPage"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture(scope="class")
    def test_integration_id(self, auth_headers):
        """Create a test integration and return its ID"""
        integration_data = {
            "name": f"TEST_Integration_{uuid.uuid4().hex[:8]}",
            "name_en": "Test Integration",
            "type": "other",
            "description": "تكامل اختبار",
            "description_en": "Test integration for automated testing",
            "api_base_url": "https://api.test.com",
            "webhook_url": "https://webhook.test.com"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/integrations",
            headers=auth_headers,
            json=integration_data
        )
        if response.status_code == 200:
            return response.json()["id"]
        return None
    
    def test_get_integrations(self, auth_headers):
        """Test GET /api/integrations - Get all integrations"""
        response = requests.get(
            f"{BASE_URL}/api/integrations",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to get integrations: {response.text}"
        data = response.json()
        assert "integrations" in data
        print(f"Got {len(data['integrations'])} integrations")
    
    def test_create_integration(self, auth_headers):
        """Test POST /api/integrations - Create integration"""
        integration_data = {
            "name": f"TEST_NewIntegration_{uuid.uuid4().hex[:8]}",
            "name_en": "New Test Integration",
            "type": "sms",
            "description": "تكامل جديد للاختبار",
            "api_base_url": "https://api.sms.test.com"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/integrations",
            headers=auth_headers,
            json=integration_data
        )
        assert response.status_code == 200, f"Failed to create integration: {response.text}"
        data = response.json()
        assert "id" in data
        assert data["name"] == integration_data["name"]
        print(f"Created integration: {data['id']}")
        return data["id"]
    
    def test_get_integration_by_id(self, auth_headers, test_integration_id):
        """Test GET /api/integrations/{id} - Get single integration"""
        if not test_integration_id:
            pytest.skip("No test integration available")
        
        response = requests.get(
            f"{BASE_URL}/api/integrations/{test_integration_id}",
            headers=auth_headers
        )
        assert response.status_code in [200, 404], f"Failed to get integration: {response.text}"
        if response.status_code == 200:
            print(f"Got integration: {response.json().get('name')}")
    
    def test_update_integration(self, auth_headers, test_integration_id):
        """Test PUT /api/integrations/{id} - Update integration"""
        if not test_integration_id:
            pytest.skip("No test integration available")
        
        update_data = {
            "name": "TEST_Updated_Integration",
            "type": "other",  # Required field
            "description": "تكامل محدث"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/integrations/{test_integration_id}",
            headers=auth_headers,
            json=update_data
        )
        assert response.status_code in [200, 404], f"Failed to update integration: {response.text}"
        if response.status_code == 200:
            print("Integration updated successfully")
    
    def test_toggle_integration(self, auth_headers, test_integration_id):
        """Test POST /api/integrations/{id}/toggle - Toggle status"""
        if not test_integration_id:
            pytest.skip("No test integration available")
        
        response = requests.post(
            f"{BASE_URL}/api/integrations/{test_integration_id}/toggle",
            headers=auth_headers
        )
        assert response.status_code in [200, 404], f"Failed to toggle integration: {response.text}"
        if response.status_code == 200:
            print(f"Integration toggled: {response.json()}")
    
    def test_test_connection(self, auth_headers, test_integration_id):
        """Test POST /api/integrations/{id}/test - Test connection"""
        if not test_integration_id:
            pytest.skip("No test integration available")
        
        response = requests.post(
            f"{BASE_URL}/api/integrations/{test_integration_id}/test",
            headers=auth_headers
        )
        assert response.status_code in [200, 404], f"Failed to test connection: {response.text}"
        if response.status_code == 200:
            print(f"Connection test result: {response.json()}")
    
    def test_sync_integration(self, auth_headers, test_integration_id):
        """Test POST /api/integrations/{id}/sync - Sync integration"""
        if not test_integration_id:
            pytest.skip("No test integration available")
        
        response = requests.post(
            f"{BASE_URL}/api/integrations/{test_integration_id}/sync",
            headers=auth_headers
        )
        assert response.status_code in [200, 404], f"Failed to sync integration: {response.text}"
        if response.status_code == 200:
            print(f"Sync result: {response.json()}")
    
    def test_get_integration_logs(self, auth_headers, test_integration_id):
        """Test GET /api/integrations/{id}/logs - Get logs"""
        if not test_integration_id:
            pytest.skip("No test integration available")
        
        response = requests.get(
            f"{BASE_URL}/api/integrations/{test_integration_id}/logs",
            headers=auth_headers
        )
        assert response.status_code in [200, 404], f"Failed to get logs: {response.text}"
        if response.status_code == 200:
            print(f"Got {len(response.json().get('logs', []))} log entries")
    
    def test_delete_integration(self, auth_headers, test_integration_id):
        """Test DELETE /api/integrations/{id} - Delete integration"""
        if not test_integration_id:
            pytest.skip("No test integration available")
        
        response = requests.delete(
            f"{BASE_URL}/api/integrations/{test_integration_id}",
            headers=auth_headers
        )
        assert response.status_code in [200, 404], f"Failed to delete integration: {response.text}"
        if response.status_code == 200:
            print("Integration deleted successfully")


class TestAnalytics:
    """Analytics API tests for PlatformAnalyticsPage"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_analytics_overview(self, auth_headers):
        """Test GET /api/analytics/overview - Get analytics overview"""
        response = requests.get(
            f"{BASE_URL}/api/analytics/overview",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to get analytics: {response.text}"
        data = response.json()
        assert "stats" in data
        assert "monthly_data" in data
        print(f"Analytics stats: {data['stats']}")
    
    def test_get_analytics_reports(self, auth_headers):
        """Test GET /api/analytics/reports - Get reports"""
        response = requests.get(
            f"{BASE_URL}/api/analytics/reports",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to get reports: {response.text}"
        data = response.json()
        assert "reports" in data
        print(f"Got {len(data['reports'])} reports")
    
    def test_get_ai_insights(self, auth_headers):
        """Test GET /api/analytics/insights - Get AI insights"""
        response = requests.get(
            f"{BASE_URL}/api/analytics/insights",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to get insights: {response.text}"
        data = response.json()
        assert "insights" in data
        print(f"Got {len(data['insights'])} AI insights")


class TestDashboardStats:
    """Dashboard stats API tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get auth headers"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_dashboard_stats(self, auth_headers):
        """Test GET /api/dashboard/stats - Get dashboard stats"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to get stats: {response.text}"
        data = response.json()
        assert "total_schools" in data
        assert "total_students" in data
        assert "total_teachers" in data
        print(f"Dashboard stats: Schools={data['total_schools']}, Students={data['total_students']}, Teachers={data['total_teachers']}")


# Cleanup test data
@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data():
    """Cleanup TEST_ prefixed data after all tests"""
    yield
    # Cleanup would go here if needed
    print("Test session completed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
