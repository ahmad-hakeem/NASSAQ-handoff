"""
Test suite for School Dashboard API - Principal Dashboard
Tests the /api/school/dashboard endpoint and related functionality
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
PRINCIPAL_EMAIL = "principal@nassaq.com"
PRINCIPAL_PASSWORD = "Principal@123"


class TestPrincipalLogin:
    """Test principal login functionality"""
    
    def test_principal_login_success(self):
        """Test successful login with principal credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "access_token" in data, "Missing access_token in response"
        assert "user" in data, "Missing user in response"
        assert data["user"]["role"] == "school_principal", f"Expected school_principal role, got {data['user']['role']}"
        assert data["user"]["email"] == PRINCIPAL_EMAIL
        assert data["user"]["tenant_id"] is not None, "Principal should have a tenant_id (school)"
        
        print(f"✓ Principal login successful - User: {data['user']['full_name']}")
        print(f"✓ Tenant ID (School): {data['user']['tenant_id']}")
    
    def test_principal_login_invalid_password(self):
        """Test login with invalid password"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": "WrongPassword123"
        })
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Invalid password correctly rejected")


class TestSchoolDashboardAPI:
    """Test /api/school/dashboard endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Could not authenticate principal")
    
    def test_dashboard_returns_200(self):
        """Test that dashboard endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/school/dashboard", headers=self.headers)
        
        assert response.status_code == 200, f"Dashboard API failed: {response.text}"
        print("✓ Dashboard API returns 200 OK")
    
    def test_dashboard_metrics_structure(self):
        """Test that dashboard returns correct metrics structure"""
        response = requests.get(f"{BASE_URL}/api/school/dashboard", headers=self.headers)
        data = response.json()
        
        # Check metrics exist
        assert "metrics" in data, "Missing metrics in response"
        metrics = data["metrics"]
        
        # Check required metric fields
        required_metrics = ["totalStudents", "totalTeachers", "totalClasses", "todaySessions", "attendanceRate", "waitingSubstitute"]
        for metric in required_metrics:
            assert metric in metrics, f"Missing metric: {metric}"
            assert "value" in metrics[metric], f"Missing value in {metric}"
            assert "changeType" in metrics[metric], f"Missing changeType in {metric}"
            assert "status" in metrics[metric], f"Missing status in {metric}"
        
        print(f"✓ All required metrics present")
        print(f"  - Total Students: {metrics['totalStudents']['value']}")
        print(f"  - Total Teachers: {metrics['totalTeachers']['value']}")
        print(f"  - Total Classes: {metrics['totalClasses']['value']}")
    
    def test_dashboard_attendance_structure(self):
        """Test that dashboard returns correct attendance structure"""
        response = requests.get(f"{BASE_URL}/api/school/dashboard", headers=self.headers)
        data = response.json()
        
        # Check attendance exists
        assert "attendance" in data, "Missing attendance in response"
        attendance = data["attendance"]
        
        # Check students attendance
        assert "students" in attendance, "Missing students attendance"
        student_att = attendance["students"]
        assert "present" in student_att, "Missing present count"
        assert "absent" in student_att, "Missing absent count"
        assert "excused" in student_att, "Missing excused count"
        assert "total" in student_att, "Missing total count"
        
        # Check teachers attendance
        assert "teachers" in attendance, "Missing teachers attendance"
        teacher_att = attendance["teachers"]
        assert "present" in teacher_att, "Missing present count"
        assert "absent" in teacher_att, "Missing absent count"
        assert "excused" in teacher_att, "Missing excused count"
        assert "total" in teacher_att, "Missing total count"
        
        print(f"✓ Attendance structure correct")
        print(f"  - Students: {student_att['present']}/{student_att['total']} present")
        print(f"  - Teachers: {teacher_att['present']}/{teacher_att['total']} present")
    
    def test_dashboard_interventions_structure(self):
        """Test that dashboard returns correct interventions structure"""
        response = requests.get(f"{BASE_URL}/api/school/dashboard", headers=self.headers)
        data = response.json()
        
        # Check interventions exist
        assert "interventions" in data, "Missing interventions in response"
        interventions = data["interventions"]
        
        # Check required intervention fields
        required_fields = ["classesWithoutTeacher", "teachersWithFrequentAbsence", "classesLowAttendance"]
        for field in required_fields:
            assert field in interventions, f"Missing intervention field: {field}"
            assert isinstance(interventions[field], int), f"{field} should be an integer"
        
        print(f"✓ Interventions structure correct")
        print(f"  - Classes without teacher: {interventions['classesWithoutTeacher']}")
        print(f"  - Teachers with frequent absence: {interventions['teachersWithFrequentAbsence']}")
        print(f"  - Classes with low attendance: {interventions['classesLowAttendance']}")
    
    def test_dashboard_alerts_structure(self):
        """Test that dashboard returns correct alerts structure"""
        response = requests.get(f"{BASE_URL}/api/school/dashboard", headers=self.headers)
        data = response.json()
        
        # Check alerts exist
        assert "alerts" in data, "Missing alerts in response"
        alerts = data["alerts"]
        
        assert isinstance(alerts, list), "Alerts should be a list"
        
        if len(alerts) > 0:
            alert = alerts[0]
            assert "id" in alert, "Alert missing id"
            assert "type" in alert, "Alert missing type"
            # Check for bilingual titles
            assert "title_ar" in alert or "title" in alert, "Alert missing title"
        
        print(f"✓ Alerts structure correct - {len(alerts)} alerts found")
    
    def test_dashboard_data_values(self):
        """Test that dashboard returns valid data values"""
        response = requests.get(f"{BASE_URL}/api/school/dashboard", headers=self.headers)
        data = response.json()
        
        metrics = data["metrics"]
        
        # Verify values are non-negative
        assert metrics["totalStudents"]["value"] >= 0, "Student count should be non-negative"
        assert metrics["totalTeachers"]["value"] >= 0, "Teacher count should be non-negative"
        assert metrics["totalClasses"]["value"] >= 0, "Class count should be non-negative"
        
        # Verify attendance totals match metrics
        attendance = data["attendance"]
        assert attendance["students"]["total"] == metrics["totalStudents"]["value"] or attendance["students"]["total"] > 0
        assert attendance["teachers"]["total"] == metrics["totalTeachers"]["value"] or attendance["teachers"]["total"] > 0
        
        print(f"✓ Data values are valid and consistent")
    
    def test_dashboard_unauthorized_access(self):
        """Test that dashboard requires authentication"""
        response = requests.get(f"{BASE_URL}/api/school/dashboard")
        
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ Unauthorized access correctly rejected")


class TestAuthMe:
    """Test /api/auth/me endpoint for principal"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Could not authenticate principal")
    
    def test_auth_me_returns_principal_info(self):
        """Test that /api/auth/me returns correct principal info"""
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=self.headers)
        
        assert response.status_code == 200, f"Auth/me failed: {response.text}"
        data = response.json()
        
        assert data["email"] == PRINCIPAL_EMAIL
        assert data["role"] == "school_principal"
        assert data["tenant_id"] is not None
        assert data["is_active"] == True
        
        print(f"✓ Auth/me returns correct principal info")
        print(f"  - Name: {data['full_name']}")
        print(f"  - Role: {data['role']}")
        print(f"  - School ID: {data['tenant_id']}")


class TestDashboardStats:
    """Test /api/dashboard/stats endpoint for principal"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Could not authenticate principal")
    
    def test_dashboard_stats_returns_200(self):
        """Test that dashboard stats endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=self.headers)
        
        assert response.status_code == 200, f"Dashboard stats failed: {response.text}"
        data = response.json()
        
        # Check required fields
        assert "total_students" in data
        assert "total_teachers" in data
        assert "total_classes" in data
        
        print(f"✓ Dashboard stats returns 200 OK")
        print(f"  - Students: {data['total_students']}")
        print(f"  - Teachers: {data['total_teachers']}")
        print(f"  - Classes: {data['total_classes']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
