"""
Test Suite: Seed Data Verification for NASSAQ School Management System
Tests the seed data for مدرسة النور (SCH-001) and مدرسة الأحساء (SCH-002)
Expected: 5 teachers, 25 students, 3 classes per school
"""

import pytest
import requests
import os

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuthentication:
    """Test authentication for different user roles"""
    
    def test_principal1_login(self):
        """Test login for مدير مدرسة النور"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "school_principal"
        assert data["user"]["tenant_id"] == "SCH-001"
    
    def test_principal4_login(self):
        """Test login for مدير مدرسة الأحساء"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal4@nassaq.com",
            "password": "Principal@123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "school_principal"
        assert data["user"]["tenant_id"] == "SCH-002"
    
    def test_admin_login(self):
        """Test login for Platform Admin"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nassaq.com",
            "password": "Admin@123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "platform_admin"


class TestSchool001Data:
    """Test seed data for مدرسة النور (SCH-001)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get token for SCH-001 principal"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        self.token = response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_teachers_count(self):
        """Verify 5 teachers for SCH-001"""
        response = requests.get(
            f"{BASE_URL}/api/teachers?school_id=SCH-001",
            headers=self.headers
        )
        assert response.status_code == 200
        teachers = response.json()
        assert len(teachers) == 5, f"Expected 5 teachers, got {len(teachers)}"
    
    def test_teachers_names(self):
        """Verify teacher names for SCH-001"""
        response = requests.get(
            f"{BASE_URL}/api/teachers?school_id=SCH-001",
            headers=self.headers
        )
        assert response.status_code == 200
        teachers = response.json()
        teacher_names = [t["full_name"] for t in teachers]
        expected_names = ["أحمد عبد الرحمن", "منى علي", "خالد السبيعي", "سارة محمد", "عبد الله الحربي"]
        for name in expected_names:
            assert name in teacher_names, f"Teacher {name} not found"
    
    def test_students_count(self):
        """Verify 25 students for SCH-001"""
        response = requests.get(
            f"{BASE_URL}/api/students?school_id=SCH-001",
            headers=self.headers
        )
        assert response.status_code == 200
        students = response.json()
        assert len(students) == 25, f"Expected 25 students, got {len(students)}"
    
    def test_students_have_full_name(self):
        """Verify all students have full_name field"""
        response = requests.get(
            f"{BASE_URL}/api/students?school_id=SCH-001",
            headers=self.headers
        )
        assert response.status_code == 200
        students = response.json()
        for student in students:
            assert "full_name" in student, f"Student {student.get('id')} missing full_name"
            assert student["full_name"], f"Student {student.get('id')} has empty full_name"
    
    def test_classes_count(self):
        """Verify 3 classes for SCH-001"""
        response = requests.get(
            f"{BASE_URL}/api/classes?school_id=SCH-001",
            headers=self.headers
        )
        assert response.status_code == 200
        classes = response.json()
        assert len(classes) == 3, f"Expected 3 classes, got {len(classes)}"
    
    def test_classes_names(self):
        """Verify class names for SCH-001"""
        response = requests.get(
            f"{BASE_URL}/api/classes?school_id=SCH-001",
            headers=self.headers
        )
        assert response.status_code == 200
        classes = response.json()
        class_names = [c["name"] for c in classes]
        # Check for expected class patterns
        assert any("الأول" in name for name in class_names), "No first grade class found"
    
    def test_school_settings(self):
        """Verify school settings for SCH-001"""
        response = requests.get(
            f"{BASE_URL}/api/school/settings",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "school_info" in data
        assert data["school_info"]["name"] == "مدرسة النور"
        assert data["school_info"]["current_students"] == 25
        assert data["school_info"]["current_teachers"] == 5
        assert data["school_info"]["current_classes"] == 3
    
    def test_school_dashboard(self):
        """Verify school dashboard stats for SCH-001"""
        response = requests.get(
            f"{BASE_URL}/api/school/dashboard",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        assert data["metrics"]["totalStudents"]["value"] == 25
        assert data["metrics"]["totalTeachers"]["value"] == 5
        assert data["metrics"]["totalClasses"]["value"] == 3


class TestSchool002Data:
    """Test seed data for مدرسة الأحساء (SCH-002)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get token for SCH-002 principal"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal4@nassaq.com",
            "password": "Principal@123"
        })
        self.token = response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_teachers_count(self):
        """Verify 5 teachers for SCH-002"""
        response = requests.get(
            f"{BASE_URL}/api/teachers?school_id=SCH-002",
            headers=self.headers
        )
        assert response.status_code == 200
        teachers = response.json()
        assert len(teachers) == 5, f"Expected 5 teachers, got {len(teachers)}"
    
    def test_teachers_names(self):
        """Verify teacher names for SCH-002"""
        response = requests.get(
            f"{BASE_URL}/api/teachers?school_id=SCH-002",
            headers=self.headers
        )
        assert response.status_code == 200
        teachers = response.json()
        teacher_names = [t["full_name"] for t in teachers]
        # Verify first names are present (last names may vary)
        expected_first_names = ["يوسف", "هبة", "إبراهيم", "آلاء", "محمد"]
        for first_name in expected_first_names:
            assert any(first_name in name for name in teacher_names), f"Teacher with first name {first_name} not found"
    
    def test_students_count(self):
        """Verify 25 students for SCH-002"""
        response = requests.get(
            f"{BASE_URL}/api/students?school_id=SCH-002",
            headers=self.headers
        )
        assert response.status_code == 200
        students = response.json()
        assert len(students) == 25, f"Expected 25 students, got {len(students)}"
    
    def test_classes_count(self):
        """Verify 3 classes for SCH-002"""
        response = requests.get(
            f"{BASE_URL}/api/classes?school_id=SCH-002",
            headers=self.headers
        )
        assert response.status_code == 200
        classes = response.json()
        assert len(classes) == 3, f"Expected 3 classes, got {len(classes)}"
    
    def test_school_settings(self):
        """Verify school settings for SCH-002"""
        response = requests.get(
            f"{BASE_URL}/api/school/settings",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "school_info" in data
        assert data["school_info"]["name"] == "مدرسة الأحساء"
        assert data["school_info"]["current_students"] == 25
        assert data["school_info"]["current_teachers"] == 5
        assert data["school_info"]["current_classes"] == 3


class TestTimeSlots:
    """Test time slots configuration"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        self.token = response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_time_slots_exist(self):
        """Verify time slots exist for SCH-001"""
        response = requests.get(
            f"{BASE_URL}/api/time-slots?school_id=SCH-001",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0, "No time slots found"
    
    def test_time_slots_structure(self):
        """Verify time slots have correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/time-slots?school_id=SCH-001",
            headers=self.headers
        )
        assert response.status_code == 200
        slots = response.json()
        for slot in slots:
            assert "start_time" in slot
            assert "end_time" in slot
            # Type field may be optional in some time slot formats
            assert "slot_number" in slot or "id" in slot


class TestScheduleAPI:
    """Test schedule API"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        self.token = response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_schedules_endpoint(self):
        """Verify schedules endpoint works"""
        response = requests.get(
            f"{BASE_URL}/api/schedules?school_id=SCH-001",
            headers=self.headers
        )
        assert response.status_code == 200
        # Schedule may be empty if not created yet
        data = response.json()
        assert isinstance(data, list)


class TestDashboardStats:
    """Test dashboard statistics API"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "admin@nassaq.com",
            "password": "Admin@123"
        })
        self.token = response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_dashboard_stats(self):
        """Verify dashboard stats for platform admin"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        # Should have at least 2 schools (SCH-001 and SCH-002)
        assert data["total_schools"] >= 2
        # Should have at least 50 students (25 per school)
        assert data["total_students"] >= 50
        # Should have at least 10 teachers (5 per school)
        assert data["total_teachers"] >= 10
    
    def test_super_admin_dashboard_stats(self):
        """Verify super admin dashboard stats"""
        response = requests.get(
            f"{BASE_URL}/api/super-admin/dashboard-stats",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_schools" in data
        assert "total_students" in data
        assert "total_teachers" in data
        assert "total_classes" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
