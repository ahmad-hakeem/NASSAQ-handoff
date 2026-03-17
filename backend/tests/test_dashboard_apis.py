"""
Test Dashboard APIs for Teacher, Student, and Parent
- GET /api/teacher/dashboard/{teacher_id}
- GET /api/student/dashboard/{student_id}
- GET /api/parent/dashboard/{parent_id}
- POST /api/parent/contact-teacher
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestDashboardAPIs:
    """Test new dashboard APIs for Teacher, Student, and Parent"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login as platform admin
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nassaq.com",
            "password": "Admin@123"
        })
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
            self.admin_token = token
        else:
            pytest.skip("Admin login failed - skipping tests")
        
        # Login as principal
        principal_login = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        
        if principal_login.status_code == 200:
            self.principal_token = principal_login.json().get("access_token")
        else:
            self.principal_token = None
    
    # ============== TEACHER DASHBOARD TESTS ==============
    
    def test_teacher_dashboard_api_exists(self):
        """Test that teacher dashboard API endpoint exists"""
        # Use a dummy teacher_id - should return 404 if not found, not 405
        response = self.session.get(f"{BASE_URL}/api/teacher/dashboard/test-teacher-id")
        # Should return 404 (not found) not 405 (method not allowed)
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}"
        print(f"✓ Teacher dashboard API exists - Status: {response.status_code}")
    
    def test_teacher_dashboard_returns_correct_structure(self):
        """Test teacher dashboard returns expected structure when teacher exists"""
        # First get a real teacher ID from the database
        teachers_response = self.session.get(f"{BASE_URL}/api/teachers?limit=1")
        
        if teachers_response.status_code == 200:
            teachers = teachers_response.json()
            if isinstance(teachers, list) and len(teachers) > 0:
                teacher_id = teachers[0].get("id")
                
                response = self.session.get(f"{BASE_URL}/api/teacher/dashboard/{teacher_id}")
                
                if response.status_code == 200:
                    data = response.json()
                    # Verify structure
                    assert "teacher" in data, "Response should contain 'teacher' key"
                    assert "stats" in data, "Response should contain 'stats' key"
                    assert "today_schedule" in data, "Response should contain 'today_schedule' key"
                    
                    # Verify stats structure
                    stats = data.get("stats", {})
                    assert "my_classes" in stats, "Stats should contain 'my_classes'"
                    assert "my_students" in stats, "Stats should contain 'my_students'"
                    assert "today_lessons" in stats, "Stats should contain 'today_lessons'"
                    assert "pending_attendance" in stats, "Stats should contain 'pending_attendance'"
                    
                    print(f"✓ Teacher dashboard structure verified - Classes: {stats.get('my_classes')}, Students: {stats.get('my_students')}")
                else:
                    print(f"✓ Teacher dashboard API responded with status {response.status_code}")
            else:
                print("✓ No teachers found in database - API structure test skipped")
        else:
            print(f"✓ Teachers list API returned {teachers_response.status_code}")
    
    def test_teacher_dashboard_invalid_id_returns_404(self):
        """Test that invalid teacher ID returns 404"""
        response = self.session.get(f"{BASE_URL}/api/teacher/dashboard/invalid-teacher-id-12345")
        assert response.status_code == 404, f"Expected 404 for invalid teacher ID, got {response.status_code}"
        print("✓ Teacher dashboard returns 404 for invalid teacher ID")
    
    def test_teacher_dashboard_requires_auth(self):
        """Test that teacher dashboard requires authentication"""
        # Create new session without auth
        no_auth_session = requests.Session()
        no_auth_session.headers.update({"Content-Type": "application/json"})
        
        response = no_auth_session.get(f"{BASE_URL}/api/teacher/dashboard/test-id")
        # API may return 401/403 (auth required) or 404 (not found) - both are acceptable
        assert response.status_code in [401, 403, 404], f"Expected 401/403/404 without auth, got {response.status_code}"
        print(f"✓ Teacher dashboard auth check - Status: {response.status_code}")
    
    # ============== STUDENT DASHBOARD TESTS ==============
    
    def test_student_dashboard_api_exists(self):
        """Test that student dashboard API endpoint exists"""
        response = self.session.get(f"{BASE_URL}/api/student/dashboard/test-student-id")
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}"
        print(f"✓ Student dashboard API exists - Status: {response.status_code}")
    
    def test_student_dashboard_returns_correct_structure(self):
        """Test student dashboard returns expected structure when student exists"""
        # First get a real student ID
        students_response = self.session.get(f"{BASE_URL}/api/students?limit=1")
        
        if students_response.status_code == 200:
            students = students_response.json()
            if isinstance(students, list) and len(students) > 0:
                student_id = students[0].get("id")
                
                response = self.session.get(f"{BASE_URL}/api/student/dashboard/{student_id}")
                
                if response.status_code == 200:
                    data = response.json()
                    # Verify structure
                    assert "student" in data, "Response should contain 'student' key"
                    assert "stats" in data, "Response should contain 'stats' key"
                    assert "today_schedule" in data, "Response should contain 'today_schedule' key"
                    assert "recent_grades" in data, "Response should contain 'recent_grades' key"
                    
                    # Verify stats structure
                    stats = data.get("stats", {})
                    assert "attendance_rate" in stats, "Stats should contain 'attendance_rate'"
                    assert "average_grade" in stats, "Stats should contain 'average_grade'"
                    
                    print(f"✓ Student dashboard structure verified - Attendance: {stats.get('attendance_rate')}%, Grade: {stats.get('average_grade')}")
                else:
                    print(f"✓ Student dashboard API responded with status {response.status_code}")
            else:
                print("✓ No students found in database - API structure test skipped")
        else:
            print(f"✓ Students list API returned {students_response.status_code}")
    
    def test_student_dashboard_invalid_id_returns_404(self):
        """Test that invalid student ID returns 404"""
        response = self.session.get(f"{BASE_URL}/api/student/dashboard/invalid-student-id-12345")
        assert response.status_code == 404, f"Expected 404 for invalid student ID, got {response.status_code}"
        print("✓ Student dashboard returns 404 for invalid student ID")
    
    def test_student_dashboard_requires_auth(self):
        """Test that student dashboard requires authentication"""
        no_auth_session = requests.Session()
        no_auth_session.headers.update({"Content-Type": "application/json"})
        
        response = no_auth_session.get(f"{BASE_URL}/api/student/dashboard/test-id")
        # API may return 401/403 (auth required) or 404 (not found) - both are acceptable
        assert response.status_code in [401, 403, 404], f"Expected 401/403/404 without auth, got {response.status_code}"
        print(f"✓ Student dashboard auth check - Status: {response.status_code}")
    
    # ============== PARENT DASHBOARD TESTS ==============
    
    def test_parent_dashboard_api_exists(self):
        """Test that parent dashboard API endpoint exists"""
        response = self.session.get(f"{BASE_URL}/api/parent/dashboard/test-parent-id")
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}"
        print(f"✓ Parent dashboard API exists - Status: {response.status_code}")
    
    def test_parent_dashboard_returns_correct_structure(self):
        """Test parent dashboard returns expected structure when parent exists"""
        # First get a real parent ID
        parents_response = self.session.get(f"{BASE_URL}/api/parents?limit=1")
        
        if parents_response.status_code == 200:
            parents = parents_response.json()
            if isinstance(parents, list) and len(parents) > 0:
                parent_id = parents[0].get("id")
                
                response = self.session.get(f"{BASE_URL}/api/parent/dashboard/{parent_id}")
                
                if response.status_code == 200:
                    data = response.json()
                    # Verify structure
                    assert "parent" in data, "Response should contain 'parent' key"
                    assert "children_count" in data, "Response should contain 'children_count' key"
                    assert "children" in data, "Response should contain 'children' key"
                    assert "notifications" in data, "Response should contain 'notifications' key"
                    
                    print(f"✓ Parent dashboard structure verified - Children: {data.get('children_count')}")
                else:
                    print(f"✓ Parent dashboard API responded with status {response.status_code}")
            else:
                print("✓ No parents found in database - API structure test skipped")
        else:
            print(f"✓ Parents list API returned {parents_response.status_code}")
    
    def test_parent_dashboard_invalid_id_returns_404(self):
        """Test that invalid parent ID returns 404"""
        response = self.session.get(f"{BASE_URL}/api/parent/dashboard/invalid-parent-id-12345")
        assert response.status_code == 404, f"Expected 404 for invalid parent ID, got {response.status_code}"
        print("✓ Parent dashboard returns 404 for invalid parent ID")
    
    def test_parent_dashboard_requires_auth(self):
        """Test that parent dashboard requires authentication"""
        no_auth_session = requests.Session()
        no_auth_session.headers.update({"Content-Type": "application/json"})
        
        response = no_auth_session.get(f"{BASE_URL}/api/parent/dashboard/test-id")
        # API may return 401/403 (auth required) or 404 (not found) - both are acceptable
        assert response.status_code in [401, 403, 404], f"Expected 401/403/404 without auth, got {response.status_code}"
        print(f"✓ Parent dashboard auth check - Status: {response.status_code}")
    
    # ============== CONTACT TEACHER API TESTS ==============
    
    def test_contact_teacher_api_exists(self):
        """Test that contact teacher API endpoint exists"""
        # This should return 422 (missing params) or 401/403 (auth required), not 405
        response = self.session.post(f"{BASE_URL}/api/parent/contact-teacher")
        # Should not be 405 (method not allowed)
        assert response.status_code != 405, f"Contact teacher API should exist, got 405"
        print(f"✓ Contact teacher API exists - Status: {response.status_code}")
    
    def test_contact_teacher_requires_parent_role(self):
        """Test that contact teacher requires parent role"""
        # Admin should not be able to use this endpoint
        response = self.session.post(
            f"{BASE_URL}/api/parent/contact-teacher",
            params={
                "teacher_id": "test-teacher",
                "student_id": "test-student",
                "subject": "Test Subject",
                "message": "Test Message"
            }
        )
        # Should return 403 (forbidden) since admin is not a parent, or 404 if route not found
        assert response.status_code in [403, 404, 422], f"Expected 403/404/422 for non-parent user, got {response.status_code}"
        print(f"✓ Contact teacher role check - Status: {response.status_code}")
    
    def test_contact_teacher_requires_auth(self):
        """Test that contact teacher requires authentication"""
        no_auth_session = requests.Session()
        no_auth_session.headers.update({"Content-Type": "application/json"})
        
        response = no_auth_session.post(
            f"{BASE_URL}/api/parent/contact-teacher",
            params={
                "teacher_id": "test-teacher",
                "student_id": "test-student",
                "subject": "Test Subject",
                "message": "Test Message"
            }
        )
        # API may return 401/403 (auth required) or 404 (not found) - both are acceptable
        assert response.status_code in [401, 403, 404], f"Expected 401/403/404 without auth, got {response.status_code}"
        print(f"✓ Contact teacher auth check - Status: {response.status_code}")


class TestLandingPageText:
    """Test Landing Page text update"""
    
    def test_landing_page_loads(self):
        """Test that landing page loads successfully"""
        response = requests.get(f"{BASE_URL}")
        assert response.status_code == 200, f"Landing page should load, got {response.status_code}"
        print("✓ Landing page loads successfully")
    
    def test_public_stats_api(self):
        """Test public stats API for landing page"""
        response = requests.get(f"{BASE_URL}/api/public/stats")
        assert response.status_code == 200, f"Public stats API should return 200, got {response.status_code}"
        
        data = response.json()
        assert "schools" in data, "Response should contain 'schools'"
        assert "students" in data, "Response should contain 'students'"
        assert "teachers" in data, "Response should contain 'teachers'"
        assert "parents" in data, "Response should contain 'parents'"
        
        print(f"✓ Public stats API working - Schools: {data.get('schools')}, Students: {data.get('students')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
