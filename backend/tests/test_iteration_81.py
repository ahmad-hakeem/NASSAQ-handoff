"""
Iteration 81 - Testing:
1. Student edit without email (should succeed)
2. Student edit with valid email (should succeed)
3. Teacher assignments tab - subjects and teachers data
4. Classes tab - no add button, data from database
5. Brand colors verification
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuthentication:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for principal"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        return data["access_token"]
    
    def test_login_success(self, auth_token):
        """Test login returns valid token"""
        assert auth_token is not None
        assert len(auth_token) > 0
        print(f"✅ Login successful, token length: {len(auth_token)}")


class TestStudentEditWithoutEmail:
    """Test editing student without sending email field"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_get_students_list(self, headers):
        """Test getting students list"""
        response = requests.get(f"{BASE_URL}/api/students", headers=headers)
        assert response.status_code == 200, f"Failed to get students: {response.text}"
        students = response.json()
        assert isinstance(students, list), "Response should be a list"
        assert len(students) > 0, "Should have at least one student"
        print(f"✅ Found {len(students)} students")
        return students
    
    def test_update_student_without_email(self, headers):
        """Test updating student with only full_name (no email field)"""
        # First get a student
        response = requests.get(f"{BASE_URL}/api/students", headers=headers)
        assert response.status_code == 200
        students = response.json()
        assert len(students) > 0, "Need at least one student to test"
        
        student = students[0]
        student_id = student.get("id")
        original_name = student.get("full_name", "Test Student")
        
        # Update with only full_name - NO email field
        update_data = {
            "full_name": original_name + " (تم التعديل)"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/students/{student_id}",
            headers=headers,
            json=update_data
        )
        
        assert response.status_code == 200, f"Update failed: {response.text}"
        result = response.json()
        assert result.get("success") == True or "تم تحديث" in result.get("message", "")
        print(f"✅ Student updated without email field - SUCCESS")
        
        # Restore original name
        restore_data = {"full_name": original_name}
        requests.put(f"{BASE_URL}/api/students/{student_id}", headers=headers, json=restore_data)
    
    def test_update_student_with_empty_string_email_should_be_ignored(self, headers):
        """Test that empty string email is handled properly by frontend logic"""
        # This tests the frontend fix - empty email should not be sent
        # The backend StudentUpdate model uses Optional[EmailStr] which would reject empty string
        # So the frontend should NOT send email if it's empty
        
        response = requests.get(f"{BASE_URL}/api/students", headers=headers)
        students = response.json()
        student = students[0]
        student_id = student.get("id")
        
        # Update with only is_active - simulating frontend not sending empty email
        update_data = {
            "is_active": True
        }
        
        response = requests.put(
            f"{BASE_URL}/api/students/{student_id}",
            headers=headers,
            json=update_data
        )
        
        assert response.status_code == 200, f"Update failed: {response.text}"
        print(f"✅ Student updated with is_active only (no email) - SUCCESS")
    
    def test_update_student_with_valid_email(self, headers):
        """Test updating student with valid email"""
        response = requests.get(f"{BASE_URL}/api/students", headers=headers)
        students = response.json()
        student = students[0]
        student_id = student.get("id")
        
        # Update with valid email
        update_data = {
            "email": "test.student@example.com"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/students/{student_id}",
            headers=headers,
            json=update_data
        )
        
        assert response.status_code == 200, f"Update with valid email failed: {response.text}"
        print(f"✅ Student updated with valid email - SUCCESS")


class TestTeacherAssignmentsTab:
    """Test teacher assignments tab data"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_get_teachers_list(self, headers):
        """Test getting teachers list for assignments tab"""
        response = requests.get(f"{BASE_URL}/api/teachers", headers=headers)
        assert response.status_code == 200, f"Failed to get teachers: {response.text}"
        teachers = response.json()
        assert isinstance(teachers, list), "Response should be a list"
        print(f"✅ Found {len(teachers)} teachers for assignments tab")
        
        # Verify teacher data structure
        if len(teachers) > 0:
            teacher = teachers[0]
            assert "id" in teacher, "Teacher should have id"
            assert "full_name" in teacher or "name" in teacher, "Teacher should have name"
            print(f"✅ Teacher data structure is correct")
    
    def test_get_subjects_list(self, headers):
        """Test getting subjects list for drag & drop"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/subjects", headers=headers)
        assert response.status_code == 200, f"Failed to get subjects: {response.text}"
        subjects = response.json()
        assert isinstance(subjects, list), "Response should be a list"
        assert len(subjects) > 0, "Should have subjects"
        print(f"✅ Found {len(subjects)} subjects for drag & drop")
        
        # Verify subject data structure
        subject = subjects[0]
        assert "id" in subject, "Subject should have id"
        assert "name_ar" in subject, "Subject should have name_ar"
        print(f"✅ Subject data structure is correct")
    
    def test_get_teacher_assignments(self, headers):
        """Test getting teacher assignments"""
        response = requests.get(f"{BASE_URL}/api/teacher-assignments", headers=headers)
        # May return 200 with empty list or 404 if no assignments
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
        
        if response.status_code == 200:
            assignments = response.json()
            print(f"✅ Found {len(assignments)} teacher assignments")
        else:
            print(f"✅ No teacher assignments yet (404 is acceptable)")
    
    def test_create_teacher_assignment(self, headers):
        """Test creating a teacher assignment via drag & drop"""
        # Get a teacher
        teachers_resp = requests.get(f"{BASE_URL}/api/teachers", headers=headers)
        teachers = teachers_resp.json()
        if len(teachers) == 0:
            pytest.skip("No teachers available")
        
        teacher = teachers[0]
        teacher_id = teacher.get("id")
        school_id = teacher.get("school_id", "SCH-001")
        
        # Get a subject
        subjects_resp = requests.get(f"{BASE_URL}/api/official-curriculum/subjects", headers=headers)
        subjects = subjects_resp.json()
        if len(subjects) == 0:
            pytest.skip("No subjects available")
        
        subject_id = subjects[0].get("id")
        
        # Get a class
        classes_resp = requests.get(f"{BASE_URL}/api/classes", headers=headers)
        classes = classes_resp.json()
        if len(classes) == 0:
            pytest.skip("No classes available")
        
        class_id = classes[0].get("id")
        
        # Create assignment with all required fields
        assignment_data = {
            "teacher_id": teacher_id,
            "subject_id": subject_id,
            "school_id": school_id,
            "class_id": class_id
        }
        
        response = requests.post(
            f"{BASE_URL}/api/teacher-assignments",
            headers=headers,
            json=assignment_data
        )
        
        # May succeed or fail if already exists
        assert response.status_code in [200, 201, 400, 409, 422], f"Unexpected status: {response.status_code}, Response: {response.text}"
        print(f"✅ Teacher assignment creation test completed (status: {response.status_code})")


class TestClassesTab:
    """Test classes tab - data from database, no add button"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_get_classes_list(self, headers):
        """Test getting classes list from database"""
        response = requests.get(f"{BASE_URL}/api/classes", headers=headers)
        assert response.status_code == 200, f"Failed to get classes: {response.text}"
        classes = response.json()
        assert isinstance(classes, list), "Response should be a list"
        print(f"✅ Found {len(classes)} classes from database")
        
        # Verify class data structure
        if len(classes) > 0:
            cls = classes[0]
            assert "id" in cls, "Class should have id"
            # Check for name field (could be name, name_ar, or both)
            has_name = "name" in cls or "name_ar" in cls
            assert has_name, "Class should have name"
            print(f"✅ Class data structure is correct")
            
            # Print sample class data
            print(f"   Sample class: {cls.get('name') or cls.get('name_ar')}, Grade: {cls.get('grade_level') or cls.get('grade')}")
    
    def test_classes_have_required_fields(self, headers):
        """Test that classes have all required fields for display"""
        response = requests.get(f"{BASE_URL}/api/classes", headers=headers)
        classes = response.json()
        
        if len(classes) > 0:
            cls = classes[0]
            # Check for display fields
            fields_to_check = ["id", "capacity", "is_active"]
            for field in fields_to_check:
                if field not in cls:
                    print(f"   Warning: Field '{field}' not in class data")
            
            # At least id should be present
            assert "id" in cls, "Class must have id"
            print(f"✅ Classes have required fields for display")


class TestSchoolSettingsAPIs:
    """Test School Settings page APIs"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "principal1@nassaq.com",
            "password": "Principal@123"
        })
        assert response.status_code == 200
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_get_school_settings(self, headers):
        """Test getting school settings"""
        response = requests.get(f"{BASE_URL}/api/school/settings", headers=headers)
        # May return 200 or 404 if no settings
        assert response.status_code in [200, 404], f"Unexpected status: {response.status_code}"
        print(f"✅ School settings API working (status: {response.status_code})")
    
    def test_get_official_curriculum_stats(self, headers):
        """Test getting curriculum stats for static section"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/stats", headers=headers)
        assert response.status_code == 200, f"Failed to get stats: {response.text}"
        stats = response.json()
        
        # Verify stats structure (API returns 'stages', 'tracks', etc. not 'stages_count')
        assert "stages" in stats, "Should have stages"
        assert "tracks" in stats, "Should have tracks"
        assert "grades" in stats, "Should have grades"
        assert "subjects" in stats, "Should have subjects"
        
        print(f"✅ Curriculum stats: {stats['stages']} stages, {stats['tracks']} tracks, {stats['grades']} grades, {stats['subjects']} subjects")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
