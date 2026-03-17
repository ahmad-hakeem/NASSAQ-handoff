"""
Test Student and Parent Portal APIs
اختبار واجهات برمجة بوابة الطالب وولي الأمر
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://school-timetable-ai.preview.emergentagent.com')

# Test credentials
STUDENT_EMAIL = "student@nassaq.com"
STUDENT_PASSWORD = "Student@123"
PARENT_EMAIL = "parent@nassaq.com"
PARENT_PASSWORD = "Parent@123"


class TestStudentLogin:
    """Test student authentication"""
    
    def test_student_login_success(self):
        """Test student login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": STUDENT_EMAIL,
            "password": STUDENT_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "student"
        assert data["user"]["email"] == STUDENT_EMAIL
        print(f"✓ Student login successful - Role: {data['user']['role']}")
    
    def test_student_login_invalid_password(self):
        """Test student login with invalid password"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": STUDENT_EMAIL,
            "password": "WrongPassword123"
        })
        assert response.status_code in [401, 400]
        print("✓ Invalid password rejected correctly")


class TestStudentPortalDashboard:
    """Test student portal dashboard API"""
    
    @pytest.fixture
    def student_token(self):
        """Get student auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": STUDENT_EMAIL,
            "password": STUDENT_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Student login failed")
    
    def test_dashboard_returns_student_info(self, student_token):
        """Test dashboard returns student information"""
        response = requests.get(
            f"{BASE_URL}/api/student-portal/dashboard",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify student info
        assert "student" in data
        assert "name" in data["student"]
        assert "grade" in data["student"]
        assert "class_name" in data["student"]
        print(f"✓ Student info: {data['student']['name']} - {data['student']['grade']}")
    
    def test_dashboard_returns_attendance_stats(self, student_token):
        """Test dashboard returns attendance statistics"""
        response = requests.get(
            f"{BASE_URL}/api/student-portal/dashboard",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify attendance stats
        assert "attendance" in data
        assert "total_days" in data["attendance"]
        assert "present" in data["attendance"]
        assert "absent" in data["attendance"]
        assert "late" in data["attendance"]
        assert "rate" in data["attendance"]
        print(f"✓ Attendance rate: {data['attendance']['rate']}%")
    
    def test_dashboard_returns_recent_grades(self, student_token):
        """Test dashboard returns recent grades"""
        response = requests.get(
            f"{BASE_URL}/api/student-portal/dashboard",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify grades
        assert "recent_grades" in data
        assert "average_score" in data
        if data["recent_grades"]:
            grade = data["recent_grades"][0]
            assert "subject" in grade
            assert "score" in grade
            assert "max_score" in grade
        print(f"✓ Average score: {data['average_score']}%")
    
    def test_dashboard_requires_auth(self):
        """Test dashboard requires authentication"""
        response = requests.get(f"{BASE_URL}/api/student-portal/dashboard")
        assert response.status_code in [401, 403]
        print("✓ Dashboard requires authentication")


class TestStudentGrades:
    """Test student grades API"""
    
    @pytest.fixture
    def student_token(self):
        """Get student auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": STUDENT_EMAIL,
            "password": STUDENT_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Student login failed")
    
    def test_grades_returns_subjects(self, student_token):
        """Test grades API returns subjects with grades"""
        response = requests.get(
            f"{BASE_URL}/api/student-portal/grades",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "subjects" in data
        assert "total_grades" in data
        assert "overall_average" in data
        
        if data["subjects"]:
            subject = data["subjects"][0]
            assert "subject" in subject
            assert "grades" in subject
            assert "average" in subject
        print(f"✓ Total grades: {data['total_grades']}, Overall average: {data['overall_average']}%")
    
    def test_grades_requires_auth(self):
        """Test grades requires authentication"""
        response = requests.get(f"{BASE_URL}/api/student-portal/grades")
        assert response.status_code in [401, 403]
        print("✓ Grades requires authentication")


class TestStudentAttendance:
    """Test student attendance API"""
    
    @pytest.fixture
    def student_token(self):
        """Get student auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": STUDENT_EMAIL,
            "password": STUDENT_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Student login failed")
    
    def test_attendance_returns_records(self, student_token):
        """Test attendance API returns records"""
        response = requests.get(
            f"{BASE_URL}/api/student-portal/attendance",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "records" in data
        assert "statistics" in data
        
        stats = data["statistics"]
        assert "total_days" in stats
        assert "present" in stats
        assert "absent" in stats
        assert "attendance_rate" in stats
        print(f"✓ Attendance records: {stats['total_days']} days, Rate: {stats['attendance_rate']}%")
    
    def test_attendance_filter_by_month(self, student_token):
        """Test attendance can be filtered by month"""
        response = requests.get(
            f"{BASE_URL}/api/student-portal/attendance",
            headers={"Authorization": f"Bearer {student_token}"},
            params={"month": 2, "year": 2026}
        )
        assert response.status_code == 200
        data = response.json()
        assert "records" in data
        print(f"✓ Filtered attendance: {len(data['records'])} records for Feb 2026")


class TestStudentSchedule:
    """Test student schedule API"""
    
    @pytest.fixture
    def student_token(self):
        """Get student auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": STUDENT_EMAIL,
            "password": STUDENT_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Student login failed")
    
    def test_schedule_returns_days(self, student_token):
        """Test schedule API returns schedule by days"""
        response = requests.get(
            f"{BASE_URL}/api/student-portal/schedule",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "schedule" in data
        assert "days" in data
        assert "student_info" in data
        
        # Verify days structure
        expected_days = ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس"]
        for day in expected_days:
            assert day in data["schedule"]
        print(f"✓ Schedule returned for {len(data['days'])} days")


class TestParentLogin:
    """Test parent authentication"""
    
    def test_parent_login_success(self):
        """Test parent login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PARENT_EMAIL,
            "password": PARENT_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "parent"
        assert data["user"]["email"] == PARENT_EMAIL
        print(f"✓ Parent login successful - Role: {data['user']['role']}")


class TestParentPortalDashboard:
    """Test parent portal dashboard API"""
    
    @pytest.fixture
    def parent_token(self):
        """Get parent auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PARENT_EMAIL,
            "password": PARENT_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Parent login failed")
    
    def test_dashboard_returns_parent_info(self, parent_token):
        """Test dashboard returns parent information"""
        response = requests.get(
            f"{BASE_URL}/api/parent-portal/dashboard",
            headers={"Authorization": f"Bearer {parent_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "parent" in data
        assert "name" in data["parent"]
        assert "email" in data["parent"]
        print(f"✓ Parent info: {data['parent']['name']}")
    
    def test_dashboard_returns_children(self, parent_token):
        """Test dashboard returns children list"""
        response = requests.get(
            f"{BASE_URL}/api/parent-portal/dashboard",
            headers={"Authorization": f"Bearer {parent_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "children" in data
        assert "children_count" in data
        assert data["children_count"] >= 1
        
        if data["children"]:
            child = data["children"][0]
            assert "id" in child
            assert "name" in child
            assert "grade" in child
            assert "attendance_rate" in child
            assert "average_score" in child
        print(f"✓ Children count: {data['children_count']}")
    
    def test_dashboard_requires_auth(self):
        """Test dashboard requires authentication"""
        response = requests.get(f"{BASE_URL}/api/parent-portal/dashboard")
        assert response.status_code in [401, 403]
        print("✓ Parent dashboard requires authentication")


class TestParentChildDetails:
    """Test parent child details API"""
    
    @pytest.fixture
    def parent_token(self):
        """Get parent auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PARENT_EMAIL,
            "password": PARENT_PASSWORD
        })
        if response.status_code == 200:
            return response.json()["access_token"]
        pytest.skip("Parent login failed")
    
    @pytest.fixture
    def child_id(self, parent_token):
        """Get first child ID"""
        response = requests.get(
            f"{BASE_URL}/api/parent-portal/dashboard",
            headers={"Authorization": f"Bearer {parent_token}"}
        )
        if response.status_code == 200 and response.json()["children"]:
            return response.json()["children"][0]["id"]
        pytest.skip("No children found")
    
    def test_child_details(self, parent_token, child_id):
        """Test get child details"""
        response = requests.get(
            f"{BASE_URL}/api/parent-portal/child/{child_id}",
            headers={"Authorization": f"Bearer {parent_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert "name" in data
        assert "grade" in data
        assert "class_name" in data
        print(f"✓ Child details: {data['name']} - {data['grade']}")
    
    def test_child_grades(self, parent_token, child_id):
        """Test get child grades"""
        response = requests.get(
            f"{BASE_URL}/api/parent-portal/child/{child_id}/grades",
            headers={"Authorization": f"Bearer {parent_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "child_name" in data
        assert "subjects" in data
        assert "overall_average" in data
        print(f"✓ Child grades: {data['overall_average']}% average")
    
    def test_child_attendance(self, parent_token, child_id):
        """Test get child attendance"""
        response = requests.get(
            f"{BASE_URL}/api/parent-portal/child/{child_id}/attendance",
            headers={"Authorization": f"Bearer {parent_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "child_name" in data
        assert "records" in data
        assert "statistics" in data
        print(f"✓ Child attendance: {data['statistics']['attendance_rate']}% rate")
    
    def test_child_schedule(self, parent_token, child_id):
        """Test get child schedule"""
        response = requests.get(
            f"{BASE_URL}/api/parent-portal/child/{child_id}/schedule",
            headers={"Authorization": f"Bearer {parent_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "child_name" in data
        assert "schedule" in data
        assert "days" in data
        print(f"✓ Child schedule returned for {len(data['days'])} days")
    
    def test_unauthorized_child_access(self, parent_token):
        """Test cannot access other parent's child"""
        response = requests.get(
            f"{BASE_URL}/api/parent-portal/child/invalid-child-id",
            headers={"Authorization": f"Bearer {parent_token}"}
        )
        assert response.status_code in [403, 404]
        print("✓ Unauthorized child access blocked")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
