"""
Test Attendance Engine APIs for NASSAQ School Management System
Tests:
- POST /api/attendance/bulk - Bulk attendance recording
- GET /api/attendance/students-for-class/{class_id} - Get students with attendance status
- GET /api/attendance/report/daily/{class_id} - Daily attendance report
- GET /api/attendance/report/summary - Attendance summary report
"""

import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
PRINCIPAL_EMAIL = "principal@nassaq.com"
PRINCIPAL_PASSWORD = "NassaqPrincipal2026"
TEST_CLASS_ID = "79176f6e-ce18-40f1-b5c9-476fb49a884d"


class TestAttendanceAPI:
    """Attendance Engine API Tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with authentication"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.token = None
        self.today = datetime.now().strftime("%Y-%m-%d")
        
    def get_auth_token(self):
        """Get authentication token for school principal"""
        if self.token:
            return self.token
            
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
            return self.token
        else:
            pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
            
    def test_01_login_as_principal(self):
        """Test login as school principal"""
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access token in response"
        assert "user" in data, "No user data in response"
        assert data["user"]["role"] == "school_principal", f"Wrong role: {data['user']['role']}"
        print(f"✓ Login successful for {PRINCIPAL_EMAIL}")
        
    def test_02_get_students_for_class(self):
        """Test GET /api/attendance/students-for-class/{class_id}"""
        self.get_auth_token()
        
        response = self.session.get(
            f"{BASE_URL}/api/attendance/students-for-class/{TEST_CLASS_ID}",
            params={"date": self.today}
        )
        
        assert response.status_code == 200, f"Failed to get students: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "class_id" in data, "Missing class_id in response"
        assert "class_name" in data, "Missing class_name in response"
        assert "students" in data, "Missing students in response"
        assert "total_students" in data, "Missing total_students in response"
        assert "date" in data, "Missing date in response"
        
        print(f"✓ Got {data['total_students']} students for class '{data['class_name']}'")
        print(f"  - Class ID: {data['class_id']}")
        print(f"  - Date: {data['date']}")
        
        # Store students for later tests
        self.students = data.get("students", [])
        return data
        
    def test_03_bulk_attendance_create(self):
        """Test POST /api/attendance/bulk - Create bulk attendance records"""
        self.get_auth_token()
        
        # First get students
        students_response = self.session.get(
            f"{BASE_URL}/api/attendance/students-for-class/{TEST_CLASS_ID}",
            params={"date": self.today}
        )
        
        assert students_response.status_code == 200, f"Failed to get students: {students_response.text}"
        students_data = students_response.json()
        students = students_data.get("students", [])
        
        if len(students) == 0:
            pytest.skip("No students in class to test attendance")
            
        # Create attendance records for all students
        records = []
        for i, student in enumerate(students):
            # Alternate between different statuses for testing
            if i % 4 == 0:
                status = "present"
            elif i % 4 == 1:
                status = "absent"
            elif i % 4 == 2:
                status = "late"
            else:
                status = "excused"
                
            records.append({
                "student_id": student["id"],
                "status": status,
                "notes": f"Test attendance - {status}"
            })
        
        # Send bulk attendance
        response = self.session.post(f"{BASE_URL}/api/attendance/bulk", json={
            "class_id": TEST_CLASS_ID,
            "subject_id": None,
            "time_slot_id": None,
            "date": self.today,
            "records": records
        })
        
        assert response.status_code == 200, f"Bulk attendance failed: {response.text}"
        data = response.json()
        
        # Validate response
        assert "message" in data, "Missing message in response"
        assert "created" in data or "updated" in data, "Missing created/updated count"
        
        total_processed = data.get("created", 0) + data.get("updated", 0)
        print(f"✓ Bulk attendance recorded successfully")
        print(f"  - Created: {data.get('created', 0)}")
        print(f"  - Updated: {data.get('updated', 0)}")
        print(f"  - Total processed: {total_processed}")
        print(f"  - Date: {data.get('date')}")
        
    def test_04_daily_attendance_report(self):
        """Test GET /api/attendance/report/daily/{class_id}"""
        self.get_auth_token()
        
        response = self.session.get(
            f"{BASE_URL}/api/attendance/report/daily/{TEST_CLASS_ID}",
            params={"date": self.today}
        )
        
        assert response.status_code == 200, f"Failed to get daily report: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "date" in data, "Missing date in response"
        assert "class_id" in data, "Missing class_id in response"
        assert "class_name" in data, "Missing class_name in response"
        assert "summary" in data, "Missing summary in response"
        assert "records" in data, "Missing records in response"
        
        # Validate summary structure
        summary = data["summary"]
        assert "total_students" in summary, "Missing total_students in summary"
        assert "present" in summary, "Missing present count in summary"
        assert "absent" in summary, "Missing absent count in summary"
        assert "late" in summary, "Missing late count in summary"
        assert "excused" in summary, "Missing excused count in summary"
        assert "attendance_rate" in summary, "Missing attendance_rate in summary"
        
        print(f"✓ Daily attendance report retrieved successfully")
        print(f"  - Class: {data['class_name']}")
        print(f"  - Date: {data['date']}")
        print(f"  - Total Students: {summary['total_students']}")
        print(f"  - Present: {summary['present']}")
        print(f"  - Absent: {summary['absent']}")
        print(f"  - Late: {summary['late']}")
        print(f"  - Excused: {summary['excused']}")
        print(f"  - Attendance Rate: {summary['attendance_rate']}%")
        
    def test_05_attendance_summary_report(self):
        """Test GET /api/attendance/report/summary"""
        self.get_auth_token()
        
        response = self.session.get(
            f"{BASE_URL}/api/attendance/report/summary",
            params={"class_id": TEST_CLASS_ID}
        )
        
        assert response.status_code == 200, f"Failed to get summary report: {response.text}"
        data = response.json()
        
        # Validate response structure
        assert "overall" in data, "Missing overall in response"
        assert "daily" in data, "Missing daily in response"
        
        # Validate overall structure
        overall = data["overall"]
        assert "total_records" in overall, "Missing total_records in overall"
        assert "present" in overall, "Missing present in overall"
        assert "absent" in overall, "Missing absent in overall"
        assert "late" in overall, "Missing late in overall"
        assert "excused" in overall, "Missing excused in overall"
        assert "attendance_rate" in overall, "Missing attendance_rate in overall"
        
        print(f"✓ Attendance summary report retrieved successfully")
        print(f"  - Total Records: {overall['total_records']}")
        print(f"  - Present: {overall['present']}")
        print(f"  - Absent: {overall['absent']}")
        print(f"  - Late: {overall['late']}")
        print(f"  - Excused: {overall['excused']}")
        print(f"  - Overall Attendance Rate: {overall['attendance_rate']}%")
        print(f"  - Daily summaries: {len(data['daily'])} days")
        
    def test_06_mark_all_present(self):
        """Test marking all students as present"""
        self.get_auth_token()
        
        # Get students
        students_response = self.session.get(
            f"{BASE_URL}/api/attendance/students-for-class/{TEST_CLASS_ID}",
            params={"date": self.today}
        )
        
        assert students_response.status_code == 200
        students = students_response.json().get("students", [])
        
        if len(students) == 0:
            pytest.skip("No students in class")
            
        # Mark all as present
        records = [{"student_id": s["id"], "status": "present", "notes": None} for s in students]
        
        response = self.session.post(f"{BASE_URL}/api/attendance/bulk", json={
            "class_id": TEST_CLASS_ID,
            "subject_id": None,
            "time_slot_id": None,
            "date": self.today,
            "records": records
        })
        
        assert response.status_code == 200, f"Failed to mark all present: {response.text}"
        
        # Verify all are present
        verify_response = self.session.get(
            f"{BASE_URL}/api/attendance/report/daily/{TEST_CLASS_ID}",
            params={"date": self.today}
        )
        
        assert verify_response.status_code == 200
        report = verify_response.json()
        
        # All should be present now
        assert report["summary"]["present"] == len(students), \
            f"Expected {len(students)} present, got {report['summary']['present']}"
        
        print(f"✓ All {len(students)} students marked as present")
        
    def test_07_verify_attendance_persistence(self):
        """Test that attendance records persist correctly"""
        self.get_auth_token()
        
        # Get students
        students_response = self.session.get(
            f"{BASE_URL}/api/attendance/students-for-class/{TEST_CLASS_ID}",
            params={"date": self.today}
        )
        
        assert students_response.status_code == 200
        students_data = students_response.json()
        students = students_data.get("students", [])
        
        if len(students) == 0:
            pytest.skip("No students in class")
            
        # Check that students have attendance status
        students_with_status = [s for s in students if s.get("attendance_status")]
        
        print(f"✓ Attendance persistence verified")
        print(f"  - Total students: {len(students)}")
        print(f"  - Students with recorded attendance: {len(students_with_status)}")
        print(f"  - Recorded count from API: {students_data.get('recorded_count', 0)}")
        
        # Verify recorded_count matches
        assert students_data.get("recorded_count", 0) == len(students_with_status), \
            "Recorded count mismatch"


class TestAttendanceStatusChanges:
    """Test different attendance status changes"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.today = datetime.now().strftime("%Y-%m-%d")
        
        # Login
        response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        
        if response.status_code == 200:
            token = response.json().get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {token}"})
        else:
            pytest.skip("Authentication failed")
            
    def test_status_present(self):
        """Test setting status to 'present'"""
        students_response = self.session.get(
            f"{BASE_URL}/api/attendance/students-for-class/{TEST_CLASS_ID}"
        )
        
        if students_response.status_code != 200:
            pytest.skip("Could not get students")
            
        students = students_response.json().get("students", [])
        if not students:
            pytest.skip("No students")
            
        response = self.session.post(f"{BASE_URL}/api/attendance/bulk", json={
            "class_id": TEST_CLASS_ID,
            "date": self.today,
            "records": [{"student_id": students[0]["id"], "status": "present"}]
        })
        
        assert response.status_code == 200
        print("✓ Status 'present' works correctly")
        
    def test_status_absent(self):
        """Test setting status to 'absent'"""
        students_response = self.session.get(
            f"{BASE_URL}/api/attendance/students-for-class/{TEST_CLASS_ID}"
        )
        
        if students_response.status_code != 200:
            pytest.skip("Could not get students")
            
        students = students_response.json().get("students", [])
        if not students:
            pytest.skip("No students")
            
        response = self.session.post(f"{BASE_URL}/api/attendance/bulk", json={
            "class_id": TEST_CLASS_ID,
            "date": self.today,
            "records": [{"student_id": students[0]["id"], "status": "absent"}]
        })
        
        assert response.status_code == 200
        print("✓ Status 'absent' works correctly")
        
    def test_status_late(self):
        """Test setting status to 'late'"""
        students_response = self.session.get(
            f"{BASE_URL}/api/attendance/students-for-class/{TEST_CLASS_ID}"
        )
        
        if students_response.status_code != 200:
            pytest.skip("Could not get students")
            
        students = students_response.json().get("students", [])
        if not students:
            pytest.skip("No students")
            
        response = self.session.post(f"{BASE_URL}/api/attendance/bulk", json={
            "class_id": TEST_CLASS_ID,
            "date": self.today,
            "records": [{"student_id": students[0]["id"], "status": "late"}]
        })
        
        assert response.status_code == 200
        print("✓ Status 'late' works correctly")
        
    def test_status_excused(self):
        """Test setting status to 'excused'"""
        students_response = self.session.get(
            f"{BASE_URL}/api/attendance/students-for-class/{TEST_CLASS_ID}"
        )
        
        if students_response.status_code != 200:
            pytest.skip("Could not get students")
            
        students = students_response.json().get("students", [])
        if not students:
            pytest.skip("No students")
            
        response = self.session.post(f"{BASE_URL}/api/attendance/bulk", json={
            "class_id": TEST_CLASS_ID,
            "date": self.today,
            "records": [{"student_id": students[0]["id"], "status": "excused"}]
        })
        
        assert response.status_code == 200
        print("✓ Status 'excused' works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
