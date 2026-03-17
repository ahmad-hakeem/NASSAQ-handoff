"""
Test Bulk Import/Export APIs
Tests for /api/bulk/template/{type}, /api/bulk/import/{type}, /api/bulk/export/{type}
"""

import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@nassaq.com"
ADMIN_PASSWORD = "Admin@123"


class TestBulkImportExport:
    """Test bulk import/export functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test - get admin token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as admin
        login_response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        
        if login_response.status_code == 200:
            data = login_response.json()
            self.token = data.get("access_token") or data.get("token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip(f"Admin login failed: {login_response.status_code}")
    
    # ============= TEMPLATE DOWNLOAD TESTS =============
    
    def test_admin_login(self):
        """Test admin login works"""
        response = self.session.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data or "token" in data
        print(f"✅ Admin login successful")
    
    def test_download_students_template(self):
        """Test downloading students import template"""
        response = self.session.get(
            f"{BASE_URL}/api/bulk/template/students",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Check content type is Excel
        content_type = response.headers.get('Content-Type', '')
        assert 'spreadsheet' in content_type or 'octet-stream' in content_type, f"Unexpected content type: {content_type}"
        
        # Check we got binary data
        assert len(response.content) > 0, "Template file is empty"
        print(f"✅ Students template downloaded: {len(response.content)} bytes")
    
    def test_download_teachers_template(self):
        """Test downloading teachers import template"""
        response = self.session.get(
            f"{BASE_URL}/api/bulk/template/teachers",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        # Check content type is Excel
        content_type = response.headers.get('Content-Type', '')
        assert 'spreadsheet' in content_type or 'octet-stream' in content_type, f"Unexpected content type: {content_type}"
        
        # Check we got binary data
        assert len(response.content) > 0, "Template file is empty"
        print(f"✅ Teachers template downloaded: {len(response.content)} bytes")
    
    def test_template_invalid_type(self):
        """Test template download with invalid type returns error"""
        response = self.session.get(
            f"{BASE_URL}/api/bulk/template/invalid_type",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        # Should return 422 (validation error) for invalid enum value
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print(f"✅ Invalid template type correctly rejected")
    
    # ============= EXPORT TESTS =============
    
    def test_export_students(self):
        """Test exporting students data"""
        response = self.session.get(
            f"{BASE_URL}/api/bulk/export/students?format=xlsx",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        # May return 404 if no students exist, or 200 with data
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')
            assert 'spreadsheet' in content_type or 'octet-stream' in content_type
            print(f"✅ Students exported: {len(response.content)} bytes")
        else:
            print(f"✅ No students to export (404 expected)")
    
    def test_export_teachers(self):
        """Test exporting teachers data"""
        response = self.session.get(
            f"{BASE_URL}/api/bulk/export/teachers?format=xlsx",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        # May return 404 if no teachers exist, or 200 with data
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')
            assert 'spreadsheet' in content_type or 'octet-stream' in content_type
            print(f"✅ Teachers exported: {len(response.content)} bytes")
        else:
            print(f"✅ No teachers to export (404 expected)")
    
    def test_export_schedule(self):
        """Test exporting schedule data"""
        response = self.session.get(
            f"{BASE_URL}/api/bulk/export/schedule?format=xlsx",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            print(f"✅ Schedule exported: {len(response.content)} bytes")
        else:
            print(f"✅ No schedule to export (404 expected)")
    
    def test_export_attendance(self):
        """Test exporting attendance data"""
        response = self.session.get(
            f"{BASE_URL}/api/bulk/export/attendance?format=xlsx",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            print(f"✅ Attendance exported: {len(response.content)} bytes")
        else:
            print(f"✅ No attendance to export (404 expected)")
    
    def test_export_grades(self):
        """Test exporting grades data"""
        response = self.session.get(
            f"{BASE_URL}/api/bulk/export/grades?format=xlsx",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            print(f"✅ Grades exported: {len(response.content)} bytes")
        else:
            print(f"✅ No grades to export (404 expected)")
    
    def test_export_csv_format(self):
        """Test exporting in CSV format"""
        response = self.session.get(
            f"{BASE_URL}/api/bulk/export/students?format=csv",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}: {response.text}"
        
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')
            assert 'csv' in content_type or 'text' in content_type or 'octet-stream' in content_type
            print(f"✅ CSV export successful: {len(response.content)} bytes")
        else:
            print(f"✅ No data to export in CSV (404 expected)")
    
    def test_export_invalid_type(self):
        """Test export with invalid type returns error"""
        response = self.session.get(
            f"{BASE_URL}/api/bulk/export/invalid_type?format=xlsx",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        # Should return 422 (validation error) for invalid enum value
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print(f"✅ Invalid export type correctly rejected")
    
    # ============= IMPORT TESTS =============
    
    def test_import_without_file(self):
        """Test import without file returns error"""
        response = self.session.post(
            f"{BASE_URL}/api/bulk/import/students",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        # Should return 422 (missing required file)
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        print(f"✅ Import without file correctly rejected")
    
    def test_import_invalid_file_type(self):
        """Test import with invalid file type"""
        # Create a fake text file
        files = {
            'file': ('test.txt', b'This is not an Excel file', 'text/plain')
        }
        
        # Remove Content-Type header for multipart
        headers = {"Authorization": f"Bearer {self.token}"}
        
        response = requests.post(
            f"{BASE_URL}/api/bulk/import/students",
            headers=headers,
            files=files
        )
        
        # Should return 400 (invalid file type)
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        print(f"✅ Invalid file type correctly rejected")
    
    # ============= AUTH TESTS =============
    
    def test_template_requires_auth(self):
        """Test template download requires authentication"""
        response = requests.get(f"{BASE_URL}/api/bulk/template/students")
        
        # Should return 401 or 403
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✅ Template endpoint requires authentication")
    
    def test_export_requires_auth(self):
        """Test export requires authentication"""
        response = requests.get(f"{BASE_URL}/api/bulk/export/students")
        
        # Should return 401 or 403
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✅ Export endpoint requires authentication")
    
    def test_import_requires_auth(self):
        """Test import requires authentication"""
        files = {'file': ('test.xlsx', b'test', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        response = requests.post(f"{BASE_URL}/api/bulk/import/students", files=files)
        
        # Should return 401 or 403
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✅ Import endpoint requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
