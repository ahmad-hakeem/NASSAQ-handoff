"""
Test Settings Routes APIs for NASSAQ School Management System
Tests: General, Maintenance, Terms, Privacy, Contact, Security, Account settings
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Admin credentials
ADMIN_EMAIL = "admin@nassaq.com"
ADMIN_PASSWORD = "Admin@123"


class TestSettingsAuth:
    """Authentication tests for settings APIs"""
    
    def test_admin_login(self):
        """Test admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        print(f"✓ Admin login successful for {ADMIN_EMAIL}")
        print(f"  - Role: {data['user'].get('role')}")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Login failed: {response.text}")
    return response.json()["access_token"]


class TestGeneralSettings:
    """Test /api/settings/general endpoints"""
    
    def test_get_general_settings(self, auth_token):
        """Test GET /api/settings/general"""
        response = requests.get(
            f"{BASE_URL}/api/settings/general",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "platform_name" in data or "platform_name_ar" in data or data.get("platform_name") is not None
        print(f"✓ GET /api/settings/general - Success")
        print(f"  - Platform name: {data.get('platform_name', data.get('platform_name_ar', 'N/A'))}")
    
    def test_put_general_settings(self, auth_token):
        """Test PUT /api/settings/general"""
        payload = {
            "platform_name": "نَسَّق | NASSAQ",
            "platform_name_en": "NASSAQ",
            "browser_title": "نَسَّق - منصة إدارة المدارس الذكية",
            "default_language": "ar",
            "date_system": "both",
            "timezone": "Asia/Riyadh"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/settings/general",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=payload
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True or "message" in data
        print(f"✓ PUT /api/settings/general - Success")
    
    def test_get_general_settings_unauthorized(self):
        """Test GET /api/settings/general without auth"""
        response = requests.get(f"{BASE_URL}/api/settings/general")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Unauthorized access correctly rejected")


class TestMaintenanceSettings:
    """Test /api/settings/maintenance endpoints"""
    
    def test_get_maintenance_settings(self, auth_token):
        """Test GET /api/settings/maintenance"""
        response = requests.get(
            f"{BASE_URL}/api/settings/maintenance",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "maintenance_mode" in data
        assert "registration_open" in data
        print(f"✓ GET /api/settings/maintenance - Success")
        print(f"  - Maintenance mode: {data.get('maintenance_mode')}")
        print(f"  - Registration open: {data.get('registration_open')}")
    
    def test_put_maintenance_settings(self, auth_token):
        """Test PUT /api/settings/maintenance"""
        payload = {
            "maintenance_mode": False,
            "registration_open": True,
            "maintenance_message_ar": "نحيطكم علمًا أن النظام يخضع حاليًا لأعمال صيانة",
            "maintenance_message_en": "The system is currently undergoing maintenance."
        }
        
        response = requests.put(
            f"{BASE_URL}/api/settings/maintenance",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=payload
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True or "message" in data
        print(f"✓ PUT /api/settings/maintenance - Success")


class TestTermsSettings:
    """Test /api/settings/terms endpoints"""
    
    def test_get_terms_versions(self, auth_token):
        """Test GET /api/settings/terms/versions"""
        response = requests.get(
            f"{BASE_URL}/api/settings/terms/versions",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Should return a list
        assert isinstance(data, list)
        print(f"✓ GET /api/settings/terms/versions - Success")
        print(f"  - Found {len(data)} versions")
    
    def test_create_terms_version(self, auth_token):
        """Test POST /api/settings/terms"""
        response = requests.post(
            f"{BASE_URL}/api/settings/terms",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={
                "content_ar": "الشروط والأحكام الخاصة باستخدام منصة نَسَّق التعليمية - نسخة اختبار",
                "content_en": "Terms and conditions for NASSAQ platform - Test version"
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True or "version_number" in data
        print(f"✓ POST /api/settings/terms - Success")
        if "version_number" in data:
            print(f"  - New version: {data['version_number']}")


class TestPrivacySettings:
    """Test /api/settings/privacy endpoints"""
    
    def test_get_privacy_versions(self, auth_token):
        """Test GET /api/settings/privacy/versions"""
        response = requests.get(
            f"{BASE_URL}/api/settings/privacy/versions",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Should return a list
        assert isinstance(data, list)
        print(f"✓ GET /api/settings/privacy/versions - Success")
        print(f"  - Found {len(data)} versions")
    
    def test_create_privacy_version(self, auth_token):
        """Test POST /api/settings/privacy"""
        response = requests.post(
            f"{BASE_URL}/api/settings/privacy",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={
                "content_ar": "سياسة الخصوصية لمنصة نَسَّق التعليمية - نسخة اختبار",
                "content_en": "Privacy policy for NASSAQ platform - Test version"
            }
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True or "version_number" in data
        print(f"✓ POST /api/settings/privacy - Success")
        if "version_number" in data:
            print(f"  - New version: {data['version_number']}")


class TestContactSettings:
    """Test /api/settings/contact endpoints"""
    
    def test_get_contact_info(self, auth_token):
        """Test GET /api/settings/contact"""
        response = requests.get(
            f"{BASE_URL}/api/settings/contact",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "email" in data or "phone" in data
        print(f"✓ GET /api/settings/contact - Success")
        print(f"  - Email: {data.get('email', 'N/A')}")
        print(f"  - Phone: {data.get('phone', 'N/A')}")
    
    def test_put_contact_info(self, auth_token):
        """Test PUT /api/settings/contact"""
        payload = {
            "email": "info@nassaqapp.com",
            "phone": "+966 11 234 5678",
            "working_hours_ar": "الأحد - الخميس: 8:00 ص - 4:00 م",
            "working_hours_en": "Sunday - Thursday: 8:00 AM - 4:00 PM",
            "address_ar": "الرياض، المملكة العربية السعودية",
            "address_en": "Riyadh, Saudi Arabia",
            "social_twitter": "https://twitter.com/nassaqapp",
            "social_linkedin": "https://linkedin.com/company/nassaq",
            "social_instagram": "",
            "social_facebook": "",
            "social_youtube": ""
        }
        
        response = requests.put(
            f"{BASE_URL}/api/settings/contact",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=payload
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True or "message" in data
        print(f"✓ PUT /api/settings/contact - Success")


class TestSecuritySettings:
    """Test /api/settings/security endpoints"""
    
    def test_get_security_settings(self, auth_token):
        """Test GET /api/settings/security"""
        response = requests.get(
            f"{BASE_URL}/api/settings/security",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "session_duration_minutes" in data or "max_concurrent_sessions" in data
        print(f"✓ GET /api/settings/security - Success")
        print(f"  - Session duration: {data.get('session_duration_minutes', 'N/A')} minutes")
        print(f"  - Max sessions: {data.get('max_concurrent_sessions', 'N/A')}")
    
    def test_put_security_settings(self, auth_token):
        """Test PUT /api/settings/security"""
        payload = {
            "session_duration_minutes": 60,
            "max_concurrent_sessions": 3,
            "min_password_length": 8,
            "require_uppercase": 1,
            "require_lowercase": 1,
            "require_numbers": 1,
            "require_special_chars": 1
        }
        
        response = requests.put(
            f"{BASE_URL}/api/settings/security",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=payload
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True or "message" in data
        print(f"✓ PUT /api/settings/security - Success")


class TestAccountSettings:
    """Test /api/settings/account endpoints"""
    
    def test_get_account_settings(self, auth_token):
        """Test GET /api/settings/account"""
        response = requests.get(
            f"{BASE_URL}/api/settings/account",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify structure
        print(f"✓ GET /api/settings/account - Success")
        print(f"  - Name: {data.get('name', 'N/A')}")
        print(f"  - Language: {data.get('language', 'N/A')}")
    
    def test_put_account_settings(self, auth_token):
        """Test PUT /api/settings/account"""
        payload = {
            "name": "مدير المنصة",
            "title": "",
            "phone": "+966500000000",
            "language": "ar"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/settings/account",
            headers={"Authorization": f"Bearer {auth_token}"},
            json=payload
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("success") == True or "message" in data
        print(f"✓ PUT /api/settings/account - Success")


class TestTitlesEndpoint:
    """Test /api/settings/titles endpoint"""
    
    def test_get_titles(self, auth_token):
        """Test GET /api/settings/titles"""
        response = requests.get(
            f"{BASE_URL}/api/settings/titles",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify structure
        assert "ar" in data
        assert "en" in data
        assert isinstance(data["ar"], list)
        assert isinstance(data["en"], list)
        print(f"✓ GET /api/settings/titles - Success")
        print(f"  - Arabic titles: {len(data['ar'])}")
        print(f"  - English titles: {len(data['en'])}")


class TestActiveSessionsEndpoint:
    """Test /api/settings/sessions/active endpoint"""
    
    def test_get_active_sessions(self, auth_token):
        """Test GET /api/settings/sessions/active"""
        response = requests.get(
            f"{BASE_URL}/api/settings/sessions/active",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Should return a list
        assert isinstance(data, list)
        print(f"✓ GET /api/settings/sessions/active - Success")
        print(f"  - Active sessions: {len(data)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
