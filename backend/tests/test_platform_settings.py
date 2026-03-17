"""
Test Platform Settings APIs for NASSAQ School Management System
Tests: GET/PUT platform settings, API keys management
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "info@nassaqapp.com"
TEST_PASSWORD = "NassaqAdmin2026!##$$HBJ"


class TestPlatformSettingsAuth:
    """Authentication tests for platform settings"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for platform admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        return data["access_token"]
    
    def test_login_success(self):
        """Test platform admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["role"] == "platform_admin"
        print(f"✓ Login successful for {TEST_EMAIL}")


class TestGetPlatformSettings:
    """Test GET /api/settings/platform endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200
        return response.json()["access_token"]
    
    def test_get_platform_settings_success(self, auth_token):
        """Test fetching platform settings"""
        response = requests.get(
            f"{BASE_URL}/api/settings/platform",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "general" in data
        assert "brand" in data
        assert "contact" in data
        assert "terms" in data
        assert "privacy" in data
        assert "security" in data
        
        # Verify general settings structure
        general = data["general"]
        assert "platform_name_ar" in general
        assert "platform_name_en" in general
        assert "default_language" in general
        
        print(f"✓ Platform settings fetched successfully")
        print(f"  - Platform name: {general.get('platform_name_ar')}")
    
    def test_get_platform_settings_unauthorized(self):
        """Test fetching settings without auth"""
        response = requests.get(f"{BASE_URL}/api/settings/platform")
        assert response.status_code in [401, 403]
        print("✓ Unauthorized access correctly rejected")


class TestUpdateGeneralSettings:
    """Test PUT /api/settings/platform/general endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_update_general_settings(self, auth_token):
        """Test updating general settings"""
        payload = {
            "platform_name_ar": "نَسَّق | NASSAQ",
            "platform_name_en": "NASSAQ",
            "browser_title": "نَسَّق - منصة إدارة المدارس الذكية",
            "default_language": "ar",
            "date_format": "hijri",
            "timezone": "Asia/Riyadh",
            "email_notifications": True,
            "sms_notifications": False,
            "push_notifications": True,
            "ai_features": True,
            "registration_open": True,
            "maintenance_mode": False
        }
        
        response = requests.put(
            f"{BASE_URL}/api/settings/platform/general",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "settings" in data
        
        # Verify settings were saved
        settings = data["settings"]
        assert settings["platform_name_ar"] == payload["platform_name_ar"]
        assert settings["default_language"] == payload["default_language"]
        
        print("✓ General settings updated successfully")
    
    def test_verify_general_settings_persisted(self, auth_token):
        """Verify general settings were persisted"""
        response = requests.get(
            f"{BASE_URL}/api/settings/platform",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["general"]["platform_name_ar"] == "نَسَّق | NASSAQ"
        print("✓ General settings persistence verified")


class TestUpdateBrandSettings:
    """Test PUT /api/settings/platform/brand endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_update_brand_settings(self, auth_token):
        """Test updating brand/identity settings"""
        payload = {
            "logo": None,
            "favicon": None,
            "primary_color": "#1e3a5f",
            "secondary_color": "#3b82f6",
            "accent_color": "#10b981"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/settings/platform/brand",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "settings" in data
        
        settings = data["settings"]
        assert settings["primary_color"] == "#1e3a5f"
        
        print("✓ Brand settings updated successfully")


class TestUpdateContactSettings:
    """Test PUT /api/settings/platform/contact endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_update_contact_settings(self, auth_token):
        """Test updating contact information"""
        payload = {
            "primary_email": "info@nassaqapp.com",
            "support_email": "support@nassaqapp.com",
            "primary_phone": "+966 11 234 5678",
            "alternate_phone": "",
            "address": "الرياض، المملكة العربية السعودية",
            "working_hours": "الأحد - الخميس: 8:00 ص - 4:00 م",
            "website": "https://nassaqapp.com",
            "owner_name": "شركة نَسَّق للتقنية التعليمية",
            "social_media": {
                "twitter": "@nassaqapp",
                "facebook": "",
                "instagram": "",
                "linkedin": "",
                "youtube": ""
            }
        }
        
        response = requests.put(
            f"{BASE_URL}/api/settings/platform/contact",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "settings" in data
        
        settings = data["settings"]
        assert settings["primary_email"] == "info@nassaqapp.com"
        assert settings["social_media"]["twitter"] == "@nassaqapp"
        
        print("✓ Contact settings updated successfully")


class TestUpdateTermsSettings:
    """Test PUT /api/settings/platform/terms endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_update_terms_settings(self, auth_token):
        """Test updating terms and conditions"""
        payload = {
            "content": """الشروط والأحكام الخاصة باستخدام منصة نَسَّق التعليمية

1. مقدمة
مرحباً بكم في منصة نَسَّق التعليمية.

2. التعريفات
- "المنصة": تشير إلى منصة نَسَّق الإلكترونية.""",
            "version": "2.2",
            "effective_date": "2026-01-15T00:00:00Z"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/settings/platform/terms",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert data["version"] == "2.2"
        
        print("✓ Terms and conditions updated successfully")


class TestUpdatePrivacySettings:
    """Test PUT /api/settings/platform/privacy endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_update_privacy_settings(self, auth_token):
        """Test updating privacy policy"""
        payload = {
            "content": """سياسة الخصوصية لمنصة نَسَّق التعليمية

1. جمع المعلومات
نقوم بجمع المعلومات التي تقدمها لنا مباشرة.

2. استخدام المعلومات
نستخدم المعلومات المجمعة لتقديم وتحسين خدماتنا.""",
            "version": "2.1",
            "effective_date": "2026-01-15T00:00:00Z"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/settings/platform/privacy",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert data["version"] == "2.1"
        
        print("✓ Privacy policy updated successfully")


class TestUpdateSecuritySettings:
    """Test PUT /api/settings/platform/security endpoint"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_update_security_settings(self, auth_token):
        """Test updating security settings"""
        payload = {
            "two_factor_enabled": False,
            "session_timeout": 30,
            "max_sessions": 5,
            "password_min_length": 8,
            "password_require_uppercase": True,
            "password_require_numbers": True,
            "password_require_special": True
        }
        
        response = requests.put(
            f"{BASE_URL}/api/settings/platform/security",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "settings" in data
        
        settings = data["settings"]
        assert settings["session_timeout"] == 30
        assert settings["password_min_length"] == 8
        
        print("✓ Security settings updated successfully")


class TestAPIKeysManagement:
    """Test API Keys CRUD operations"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def created_key_id(self, auth_token):
        """Create a test API key and return its ID"""
        payload = {
            "name": f"TEST_API_Key_{uuid.uuid4().hex[:8]}",
            "permissions": "read_only"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/settings/api-keys",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        return data["id"]
    
    def test_create_api_key(self, auth_token):
        """Test creating a new API key"""
        payload = {
            "name": f"TEST_Create_Key_{uuid.uuid4().hex[:8]}",
            "permissions": "read_write"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/settings/api-keys",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "id" in data
        assert "name" in data
        assert "key" in data
        assert "secret" in data  # Only returned on creation
        assert "permissions" in data
        assert "is_active" in data
        assert data["is_active"] == True
        assert data["permissions"] == "read_write"
        
        # Verify key format
        assert data["key"].startswith("nsk_")
        assert data["secret"].startswith("nss_")
        
        print(f"✓ API key created: {data['name']}")
        print(f"  - Key prefix: {data['key'][:15]}...")
        
        # Cleanup - delete the test key
        requests.delete(
            f"{BASE_URL}/api/settings/api-keys/{data['id']}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
    
    def test_get_api_keys(self, auth_token):
        """Test fetching all API keys"""
        response = requests.get(
            f"{BASE_URL}/api/settings/api-keys",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "keys" in data
        assert isinstance(data["keys"], list)
        
        # Verify secret is not returned in list
        for key in data["keys"]:
            assert "secret" not in key or key.get("secret") is None
            assert "secret_hash" not in key
        
        print(f"✓ Retrieved {len(data['keys'])} API keys")
    
    def test_revoke_api_key(self, auth_token, created_key_id):
        """Test revoking an API key"""
        response = requests.post(
            f"{BASE_URL}/api/settings/api-keys/{created_key_id}/revoke",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        
        # Verify key is now inactive
        keys_response = requests.get(
            f"{BASE_URL}/api/settings/api-keys",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        keys = keys_response.json()["keys"]
        revoked_key = next((k for k in keys if k["id"] == created_key_id), None)
        assert revoked_key is not None
        assert revoked_key["is_active"] == False
        
        print(f"✓ API key revoked successfully")
    
    def test_revoke_nonexistent_key(self, auth_token):
        """Test revoking a non-existent API key"""
        fake_id = str(uuid.uuid4())
        response = requests.post(
            f"{BASE_URL}/api/settings/api-keys/{fake_id}/revoke",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 404
        print("✓ Non-existent key revoke correctly returns 404")


class TestLegalVersionHistory:
    """Test legal document version history"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_get_terms_version_history(self, auth_token):
        """Test fetching terms version history"""
        response = requests.get(
            f"{BASE_URL}/api/settings/legal-versions/terms",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "versions" in data
        print(f"✓ Terms version history: {len(data['versions'])} versions")
    
    def test_get_privacy_version_history(self, auth_token):
        """Test fetching privacy version history"""
        response = requests.get(
            f"{BASE_URL}/api/settings/legal-versions/privacy",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "versions" in data
        print(f"✓ Privacy version history: {len(data['versions'])} versions")
    
    def test_invalid_doc_type(self, auth_token):
        """Test invalid document type"""
        response = requests.get(
            f"{BASE_URL}/api/settings/legal-versions/invalid",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 400
        print("✓ Invalid doc type correctly returns 400")


class TestIntegrationsPage:
    """Test Integrations Page API endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_get_integrations(self, auth_token):
        """Test fetching integrations list"""
        response = requests.get(
            f"{BASE_URL}/api/integrations",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "integrations" in data
        print(f"✓ Retrieved {len(data['integrations'])} integrations")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
