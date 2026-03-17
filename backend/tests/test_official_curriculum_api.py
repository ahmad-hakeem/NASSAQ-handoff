"""
Test Official Curriculum APIs - المنهج الرسمي
Tests for the official curriculum endpoints from Saudi Ministry of Education
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://school-timetable-ai.preview.emergentagent.com')

class TestOfficialCurriculumStats:
    """Test /api/official-curriculum/stats endpoint"""
    
    def test_get_stats_returns_200(self):
        """Test that stats endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/stats")
        assert response.status_code == 200
        
    def test_stats_contains_required_fields(self):
        """Test that stats response contains all required fields"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/stats")
        data = response.json()
        
        # Verify all required fields exist
        assert "stages" in data
        assert "tracks" in data
        assert "grades" in data
        assert "subjects" in data
        assert "grade_subject_mappings" in data
        assert "teacher_rank_loads" in data
        assert "subject_categories" in data
        assert "source" in data
        assert "is_official" in data
        assert "is_locked" in data
        
    def test_stats_values_are_positive(self):
        """Test that stats values are positive integers"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/stats")
        data = response.json()
        
        assert data["stages"] > 0
        assert data["tracks"] > 0
        assert data["grades"] > 0
        assert data["subjects"] > 0
        assert data["is_official"] == True
        assert data["is_locked"] == True


class TestOfficialCurriculumStages:
    """Test /api/official-curriculum/stages endpoint"""
    
    def test_get_stages_returns_200(self):
        """Test that stages endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/stages")
        assert response.status_code == 200
        
    def test_stages_returns_list(self):
        """Test that stages returns a list"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/stages")
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 3  # Elementary, Middle, Secondary
        
    def test_stage_structure(self):
        """Test that each stage has required fields"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/stages")
        data = response.json()
        
        for stage in data:
            assert "id" in stage
            assert "code" in stage
            assert "name_ar" in stage
            assert "name_en" in stage
            assert "order" in stage
            assert "grades_count" in stage
            assert "is_official" in stage
            assert "is_locked" in stage
            
    def test_stages_include_elementary(self):
        """Test that elementary stage exists"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/stages")
        data = response.json()
        
        elementary = next((s for s in data if s["code"] == "elementary"), None)
        assert elementary is not None
        assert elementary["name_ar"] == "المرحلة الابتدائية"


class TestOfficialCurriculumTracks:
    """Test /api/official-curriculum/tracks endpoint"""
    
    def test_get_tracks_returns_200(self):
        """Test that tracks endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/tracks")
        assert response.status_code == 200
        
    def test_tracks_returns_list(self):
        """Test that tracks returns a list"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/tracks")
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2  # At least general and quran tracks
        
    def test_track_structure(self):
        """Test that each track has required fields"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/tracks")
        data = response.json()
        
        for track in data:
            assert "id" in track
            assert "code" in track
            assert "name_ar" in track
            assert "name_en" in track
            assert "applicable_stages" in track
            assert "order" in track
            assert "is_official" in track
            assert "is_locked" in track
            
    def test_filter_tracks_by_stage(self):
        """Test filtering tracks by stage_id"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/tracks?stage_id=stage-secondary")
        assert response.status_code == 200
        data = response.json()
        
        # All returned tracks should be applicable to secondary stage
        for track in data:
            assert "stage-secondary" in track["applicable_stages"]


class TestOfficialCurriculumGrades:
    """Test /api/official-curriculum/grades endpoint"""
    
    def test_get_grades_returns_200(self):
        """Test that grades endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/grades")
        assert response.status_code == 200
        
    def test_grades_returns_list(self):
        """Test that grades returns a list"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/grades")
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 6  # At least 6 elementary grades
        
    def test_grade_structure(self):
        """Test that each grade has required fields"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/grades")
        data = response.json()
        
        for grade in data[:5]:  # Check first 5 grades
            assert "id" in grade
            assert "stage_id" in grade
            assert "track_id" in grade
            assert "name_ar" in grade
            assert "name_en" in grade
            assert "order" in grade
            assert "year_number" in grade
            assert "is_official" in grade
            assert "is_locked" in grade
            
    def test_filter_grades_by_stage(self):
        """Test filtering grades by stage_id"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/grades?stage_id=stage-elementary")
        assert response.status_code == 200
        data = response.json()
        
        # All returned grades should belong to elementary stage
        for grade in data:
            assert grade["stage_id"] == "stage-elementary"
            
    def test_grades_include_stage_and_track_names(self):
        """Test that grades include enriched stage and track names"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/grades?stage_id=stage-elementary")
        data = response.json()
        
        if len(data) > 0:
            grade = data[0]
            assert "stage_name_ar" in grade
            assert "track_name_ar" in grade


class TestOfficialCurriculumTeacherRankLoads:
    """Test /api/official-curriculum/teacher-rank-loads endpoint"""
    
    def test_get_rank_loads_returns_200(self):
        """Test that teacher rank loads endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/teacher-rank-loads")
        assert response.status_code == 200
        
    def test_rank_loads_returns_list(self):
        """Test that rank loads returns a list"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/teacher-rank-loads")
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 4  # At least 4 teacher ranks
        
    def test_rank_load_structure(self):
        """Test that each rank load has required fields"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/teacher-rank-loads")
        data = response.json()
        
        for rank in data:
            assert "id" in rank
            assert "rank_code" in rank
            assert "rank_name_ar" in rank
            assert "rank_name_en" in rank
            assert "weekly_periods" in rank
            assert "is_special_education" in rank
            assert "is_official" in rank
            assert "is_locked" in rank
            
    def test_rank_loads_have_valid_periods(self):
        """Test that weekly periods are within valid range"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/teacher-rank-loads")
        data = response.json()
        
        for rank in data:
            assert 10 <= rank["weekly_periods"] <= 30  # Valid range for teacher loads
            
    def test_filter_special_education_ranks(self):
        """Test filtering special education ranks"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/teacher-rank-loads?is_special_education=true")
        assert response.status_code == 200
        data = response.json()
        
        for rank in data:
            assert rank["is_special_education"] == True


class TestOfficialCurriculumForGrade:
    """Test /api/official-curriculum/curriculum-for-grade/{grade_id} endpoint"""
    
    def test_get_curriculum_for_grade_returns_200(self):
        """Test that curriculum for grade endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/curriculum-for-grade/grade-elem-1-general")
        assert response.status_code == 200
        
    def test_curriculum_structure(self):
        """Test that curriculum response has required structure"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/curriculum-for-grade/grade-elem-1-general")
        data = response.json()
        
        assert "grade" in data
        assert "stage" in data
        assert "track" in data
        assert "subjects" in data
        assert "summary" in data
        assert "is_official" in data
        assert "is_locked" in data
        
    def test_curriculum_grade_info(self):
        """Test that grade info is correct"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/curriculum-for-grade/grade-elem-1-general")
        data = response.json()
        
        assert data["grade"]["id"] == "grade-elem-1-general"
        assert data["grade"]["name_ar"] == "الصف الأول الابتدائي"
        assert data["stage"]["name_ar"] == "المرحلة الابتدائية"
        assert data["track"]["name_ar"] == "التعليم العام"
        
    def test_curriculum_subjects_list(self):
        """Test that subjects list is populated"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/curriculum-for-grade/grade-elem-1-general")
        data = response.json()
        
        assert len(data["subjects"]) > 0
        
        for subject in data["subjects"]:
            assert "subject_id" in subject
            assert "subject_name_ar" in subject
            assert "annual_periods" in subject
            assert "weekly_periods" in subject
            assert "category" in subject
            
    def test_curriculum_summary(self):
        """Test that summary contains correct totals"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/curriculum-for-grade/grade-elem-1-general")
        data = response.json()
        
        summary = data["summary"]
        assert "subjects_count" in summary
        assert "total_annual_periods" in summary
        assert "total_weekly_periods" in summary
        assert summary["subjects_count"] > 0
        assert summary["total_annual_periods"] > 0
        
    def test_invalid_grade_returns_404(self):
        """Test that invalid grade ID returns 404"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/curriculum-for-grade/invalid-grade-id")
        assert response.status_code == 404


class TestOfficialCurriculumSubjects:
    """Test /api/official-curriculum/subjects endpoint"""
    
    def test_get_subjects_returns_200(self):
        """Test that subjects endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/subjects")
        assert response.status_code == 200
        
    def test_subjects_returns_list(self):
        """Test that subjects returns a list"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/subjects")
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 10  # At least 10 subjects
        
    def test_subject_structure(self):
        """Test that each subject has required fields"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/subjects")
        data = response.json()
        
        for subject in data[:5]:  # Check first 5 subjects
            assert "id" in subject
            assert "code" in subject
            assert "name_ar" in subject
            assert "name_en" in subject
            assert "category" in subject
            assert "is_core" in subject
            assert "is_official" in subject
            assert "is_locked" in subject


class TestOfficialCurriculumSearch:
    """Test /api/official-curriculum/search endpoint"""
    
    def test_search_returns_200(self):
        """Test that search endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/search?q=رياضيات")
        assert response.status_code == 200
        
    def test_search_returns_results_structure(self):
        """Test that search returns proper structure"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/search?q=رياضيات")
        data = response.json()
        
        assert "stages" in data
        assert "tracks" in data
        assert "grades" in data
        assert "subjects" in data
        
    def test_search_finds_math_subject(self):
        """Test that search finds math subject"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/search?q=رياضيات")
        data = response.json()
        
        # Should find math in subjects
        assert len(data["subjects"]) > 0
        
    def test_search_with_type_filter(self):
        """Test search with type filter"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/search?q=ابتدائي&type=stage")
        assert response.status_code == 200
        data = response.json()
        
        # Should only search in stages
        assert len(data["stages"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
