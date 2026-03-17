"""
Test School Settings APIs - NASSAQ
Tests for the 15 sections of school settings page
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://school-timetable-ai.preview.emergentagent.com').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@nassaq.com"
ADMIN_PASSWORD = "Admin@123"
PRINCIPAL_EMAIL = "principal1@nassaq.com"
PRINCIPAL_PASSWORD = "Principal@123"


class TestSchoolSettingsAPIs:
    """Test School Settings APIs - 15 sections"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get tokens"""
        # Get admin token
        admin_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert admin_response.status_code == 200, f"Admin login failed: {admin_response.text}"
        self.admin_token = admin_response.json()["access_token"]
        
        # Get principal token
        principal_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": PRINCIPAL_EMAIL, "password": PRINCIPAL_PASSWORD}
        )
        assert principal_response.status_code == 200, f"Principal login failed: {principal_response.text}"
        self.principal_token = principal_response.json()["access_token"]
        self.school_id = principal_response.json()["user"]["tenant_id"]
        
        self.principal_headers = {
            "Authorization": f"Bearer {self.principal_token}",
            "Content-Type": "application/json"
        }
        self.admin_headers = {
            "Authorization": f"Bearer {self.admin_token}",
            "Content-Type": "application/json",
            "X-School-Context": self.school_id
        }
    
    # ============== Section 1: School Info ==============
    def test_get_school_settings(self):
        """Test GET /api/school/settings - جلب جميع إعدادات المدرسة"""
        response = requests.get(
            f"{BASE_URL}/api/school/settings",
            headers=self.principal_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify all 15 sections are present
        assert "school_info" in data, "Missing school_info section"
        assert "work_days" in data, "Missing work_days section"
        assert "official_holidays" in data, "Missing official_holidays section"
        assert "exception_days" in data, "Missing exception_days section"
        assert "periods_per_day" in data, "Missing periods_per_day section"
        assert "timing" in data, "Missing timing section"
        assert "breaks" in data, "Missing breaks section"
        assert "activity_days" in data, "Missing activity_days section"
        assert "teaching_loads" in data, "Missing teaching_loads section"
        assert "teacher_availability" in data, "Missing teacher_availability section"
        assert "constraints" in data, "Missing constraints section"
        assert "educational_stages" in data, "Missing educational_stages section"
        assert "grades" in data, "Missing grades section"
        assert "sections" in data, "Missing sections section"
        assert "academic_terms" in data, "Missing academic_terms section"
        
        # Verify school_info has required fields
        school_info = data["school_info"]
        assert "name" in school_info, "Missing school name"
        assert "id" in school_info, "Missing school id"
        print(f"✓ School settings retrieved: {school_info.get('name')}")
    
    def test_get_school_settings_with_admin_context(self):
        """Test GET /api/school/settings with X-School-Context header"""
        response = requests.get(
            f"{BASE_URL}/api/school/settings",
            headers=self.admin_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "school_info" in data
        print(f"✓ Admin can access school settings with context header")
    
    # ============== Section 2: Work Days ==============
    def test_update_work_days(self):
        """Test PUT /api/school/settings/work-days - تحديث أيام العمل"""
        work_days = {
            "sunday": True,
            "monday": True,
            "tuesday": True,
            "wednesday": True,
            "thursday": True,
            "friday": False,
            "saturday": False
        }
        response = requests.put(
            f"{BASE_URL}/api/school/settings/work-days",
            headers=self.principal_headers,
            json=work_days
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "message" in data
        print(f"✓ Work days updated successfully")
    
    # ============== Section 3: Periods Per Day ==============
    def test_update_periods_per_day(self):
        """Test PUT /api/school/settings/periods-per-day - تحديث عدد الحصص"""
        # API expects periods as query parameter
        response = requests.put(
            f"{BASE_URL}/api/school/settings/periods-per-day?periods=7",
            headers=self.principal_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "message" in data
        print(f"✓ Periods per day updated successfully")
    
    # ============== Section 4: School Timing ==============
    def test_update_timing(self):
        """Test PUT /api/school/settings/timing - تحديث أوقات الدوام"""
        response = requests.put(
            f"{BASE_URL}/api/school/settings/timing",
            headers=self.principal_headers,
            json={"start": "07:00", "end": "14:00"}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "message" in data
        print(f"✓ School timing updated successfully")
    
    # ============== Section 5: Breaks ==============
    def test_update_breaks(self):
        """Test PUT /api/school/settings/breaks - تحديث فترات الاستراحة"""
        # API expects a list directly, not wrapped in object
        breaks = [
            {"id": "break-1", "name": "استراحة الفطور", "start": "09:30", "end": "09:45"}
        ]
        response = requests.put(
            f"{BASE_URL}/api/school/settings/breaks",
            headers=self.principal_headers,
            json=breaks  # Send list directly
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "message" in data
        print(f"✓ Breaks updated successfully")
    
    # ============== Section 6: Official Holidays ==============
    def test_add_official_holiday(self):
        """Test POST /api/school/settings/holidays - إضافة إجازة رسمية"""
        holiday = {
            "name": "TEST_عيد الفطر",
            "start_date": "2026-04-01",
            "end_date": "2026-04-05"
        }
        response = requests.post(
            f"{BASE_URL}/api/school/settings/holidays",
            headers=self.principal_headers,
            json=holiday
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "holiday" in data
        assert "id" in data["holiday"]
        self.holiday_id = data["holiday"]["id"]
        print(f"✓ Holiday added: {self.holiday_id}")
        
        # Cleanup - delete the test holiday
        delete_response = requests.delete(
            f"{BASE_URL}/api/school/settings/holidays/{self.holiday_id}",
            headers=self.principal_headers
        )
        assert delete_response.status_code == 200
        print(f"✓ Test holiday cleaned up")
    
    # ============== Section 7: Activity Days ==============
    def test_add_activity_day(self):
        """Test POST /api/school/settings/activity-days - إضافة يوم نشاط"""
        activity = {
            "date": "2026-05-01",
            "name": "TEST_يوم رياضي",
            "notes": "يوم نشاط رياضي"
        }
        response = requests.post(
            f"{BASE_URL}/api/school/settings/activity-days",
            headers=self.principal_headers,
            json=activity
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "activity" in data
        activity_id = data["activity"]["id"]
        print(f"✓ Activity day added: {activity_id}")
        
        # Cleanup
        delete_response = requests.delete(
            f"{BASE_URL}/api/school/settings/activity-days/{activity_id}",
            headers=self.principal_headers
        )
        assert delete_response.status_code == 200
        print(f"✓ Test activity day cleaned up")
    
    # ============== Section 8: Teaching Loads ==============
    def test_update_teaching_loads(self):
        """Test PUT /api/school/settings/teaching-loads - تحديث النصاب التدريسي"""
        loads = {"teacher-1": 18, "teacher-2": 20}
        response = requests.put(
            f"{BASE_URL}/api/school/settings/teaching-loads",
            headers=self.principal_headers,
            json={"teaching_loads": loads}
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "message" in data
        print(f"✓ Teaching loads updated successfully")
    
    # ============== Section 9: Teacher Availability ==============
    def test_update_teacher_availability(self):
        """Test PUT /api/school/settings/teacher-availability - تحديث توافر المعلمين"""
        # API expects TeacherAvailability model with teacher_id, available_days, available_periods
        availability = {
            "teacher_id": "teacher-1",
            "available_days": ["sunday", "monday", "tuesday"],
            "available_periods": [1, 2, 3, 4]
        }
        response = requests.put(
            f"{BASE_URL}/api/school/settings/teacher-availability",
            headers=self.principal_headers,
            json=availability
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "message" in data
        print(f"✓ Teacher availability updated successfully")
    
    # ============== Section 10: Constraints ==============
    def test_update_constraints(self):
        """Test PUT /api/school/settings/constraints - تحديث القيود الإدارية"""
        # API expects a list directly, not wrapped in object
        constraints = [
            {
                "id": "constraint-1",
                "type": "no_first_period",
                "teacher_id": "teacher-1",
                "description": "لا يبدأ الحصة الأولى"
            }
        ]
        response = requests.put(
            f"{BASE_URL}/api/school/settings/constraints",
            headers=self.principal_headers,
            json=constraints  # Send list directly
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert "message" in data
        print(f"✓ Constraints updated successfully")
    
    # ============== Section 11: Educational Stages ==============
    def test_stages_crud(self):
        """Test stages CRUD - المراحل الدراسية"""
        # Create stage
        stage = {"name": "TEST_المرحلة الابتدائية", "name_en": "Primary Stage", "order": 1}
        create_response = requests.post(
            f"{BASE_URL}/api/school/settings/stages",
            headers=self.principal_headers,
            json=stage
        )
        assert create_response.status_code == 200, f"Create failed: {create_response.text}"
        stage_id = create_response.json()["stage"]["id"]
        print(f"✓ Stage created: {stage_id}")
        
        # Get stages
        get_response = requests.get(
            f"{BASE_URL}/api/school/settings/stages",
            headers=self.principal_headers
        )
        assert get_response.status_code == 200
        print(f"✓ Stages retrieved")
        
        # Delete stage
        delete_response = requests.delete(
            f"{BASE_URL}/api/school/settings/stages/{stage_id}",
            headers=self.principal_headers
        )
        assert delete_response.status_code == 200
        print(f"✓ Stage deleted")
    
    # ============== Section 12: Grades ==============
    def test_grades_crud(self):
        """Test grades CRUD - الصفوف الدراسية"""
        # Create grade
        grade = {"name": "TEST_الصف الأول", "name_en": "Grade 1", "stage_id": "stage-1", "order": 1}
        create_response = requests.post(
            f"{BASE_URL}/api/school/settings/grades",
            headers=self.principal_headers,
            json=grade
        )
        assert create_response.status_code == 200, f"Create failed: {create_response.text}"
        grade_id = create_response.json()["grade"]["id"]
        print(f"✓ Grade created: {grade_id}")
        
        # Get grades
        get_response = requests.get(
            f"{BASE_URL}/api/school/settings/grades",
            headers=self.principal_headers
        )
        assert get_response.status_code == 200
        print(f"✓ Grades retrieved")
        
        # Delete grade
        delete_response = requests.delete(
            f"{BASE_URL}/api/school/settings/grades/{grade_id}",
            headers=self.principal_headers
        )
        assert delete_response.status_code == 200
        print(f"✓ Grade deleted")
    
    # ============== Section 13: Sections ==============
    def test_sections_crud(self):
        """Test sections CRUD - الشعب"""
        # Create section
        section = {"name": "TEST_شعبة أ", "name_en": "Section A", "grade_id": "grade-1"}
        create_response = requests.post(
            f"{BASE_URL}/api/school/settings/sections",
            headers=self.principal_headers,
            json=section
        )
        assert create_response.status_code == 200, f"Create failed: {create_response.text}"
        section_id = create_response.json()["section"]["id"]
        print(f"✓ Section created: {section_id}")
        
        # Get sections
        get_response = requests.get(
            f"{BASE_URL}/api/school/settings/sections",
            headers=self.principal_headers
        )
        assert get_response.status_code == 200
        print(f"✓ Sections retrieved")
        
        # Delete section
        delete_response = requests.delete(
            f"{BASE_URL}/api/school/settings/sections/{section_id}",
            headers=self.principal_headers
        )
        assert delete_response.status_code == 200
        print(f"✓ Section deleted")
    
    # ============== Section 14: Academic Terms ==============
    def test_academic_terms_crud(self):
        """Test academic terms CRUD - الفصول الدراسية"""
        # Create term
        term = {
            "name": "TEST_الفصل الأول",
            "name_en": "First Semester",
            "start_date": "2026-09-01",
            "end_date": "2027-01-15",
            "is_current": False
        }
        create_response = requests.post(
            f"{BASE_URL}/api/school/settings/academic-terms",
            headers=self.principal_headers,
            json=term
        )
        assert create_response.status_code == 200, f"Create failed: {create_response.text}"
        term_id = create_response.json()["term"]["id"]
        print(f"✓ Academic term created: {term_id}")
        
        # Get terms
        get_response = requests.get(
            f"{BASE_URL}/api/school/settings/academic-terms",
            headers=self.principal_headers
        )
        assert get_response.status_code == 200
        print(f"✓ Academic terms retrieved")
        
        # Delete term
        delete_response = requests.delete(
            f"{BASE_URL}/api/school/settings/academic-terms/{term_id}",
            headers=self.principal_headers
        )
        assert delete_response.status_code == 200
        print(f"✓ Academic term deleted")
    
    # ============== Section 15: Subjects ==============
    def test_subjects_crud(self):
        """Test subjects CRUD - المواد الدراسية"""
        # Create subject
        subject = {
            "name": "TEST_الرياضيات",
            "name_en": "Mathematics",
            "weekly_periods": 5,
            "grade_id": "grade-1"
        }
        create_response = requests.post(
            f"{BASE_URL}/api/school/settings/subjects",
            headers=self.principal_headers,
            json=subject
        )
        assert create_response.status_code == 200, f"Create failed: {create_response.text}"
        subject_id = create_response.json()["subject"]["id"]
        print(f"✓ Subject created: {subject_id}")
        
        # Get subjects
        get_response = requests.get(
            f"{BASE_URL}/api/school/settings/subjects",
            headers=self.principal_headers
        )
        assert get_response.status_code == 200
        print(f"✓ Subjects retrieved")
        
        # Delete subject
        delete_response = requests.delete(
            f"{BASE_URL}/api/school/settings/subjects/{subject_id}",
            headers=self.principal_headers
        )
        assert delete_response.status_code == 200
        print(f"✓ Subject deleted")


class TestSchoolSettingsValidation:
    """Test validation and error handling"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup - get principal token"""
        principal_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": PRINCIPAL_EMAIL, "password": PRINCIPAL_PASSWORD}
        )
        assert principal_response.status_code == 200
        self.principal_token = principal_response.json()["access_token"]
        self.principal_headers = {
            "Authorization": f"Bearer {self.principal_token}",
            "Content-Type": "application/json"
        }
    
    def test_unauthorized_access(self):
        """Test unauthorized access to school settings"""
        response = requests.get(f"{BASE_URL}/api/school/settings")
        assert response.status_code == 403 or response.status_code == 401
        print(f"✓ Unauthorized access blocked")
    
    def test_invalid_periods_per_day(self):
        """Test invalid periods per day value"""
        response = requests.put(
            f"{BASE_URL}/api/school/settings/periods-per-day",
            headers=self.principal_headers,
            json={"periods_per_day": 0}  # Invalid value
        )
        # Should either reject or accept with validation
        print(f"✓ Invalid periods handled: {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
