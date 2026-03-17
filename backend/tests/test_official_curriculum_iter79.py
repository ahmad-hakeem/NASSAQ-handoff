"""
Official Curriculum API Tests - Iteration 79
Tests for the official curriculum endpoints that provide read-only data from Saudi Ministry of Education
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://school-timetable-ai.preview.emergentagent.com')

class TestOfficialCurriculumStats:
    """Test /api/official-curriculum/stats endpoint"""
    
    def test_stats_returns_correct_counts(self):
        """Stats API should return correct counts for all curriculum data"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/stats")
        assert response.status_code == 200
        
        data = response.json()
        # Verify all required fields exist
        assert "stages" in data
        assert "tracks" in data
        assert "grades" in data
        assert "subjects" in data
        assert "grade_subject_mappings" in data
        assert "teacher_rank_loads" in data
        
        # Verify expected counts
        assert data["stages"] == 3, f"Expected 3 stages, got {data['stages']}"
        assert data["tracks"] == 8, f"Expected 8 tracks, got {data['tracks']}"
        assert data["grades"] == 29, f"Expected 29 grades, got {data['grades']}"
        assert data["subjects"] == 81, f"Expected 81 subjects, got {data['subjects']}"
        assert data["teacher_rank_loads"] == 7, f"Expected 7 teacher ranks, got {data['teacher_rank_loads']}"
        
        # Verify official data flags
        assert data["is_official"] == True
        assert data["is_locked"] == True
        assert "وزارة التعليم" in data.get("source", "")


class TestOfficialCurriculumStages:
    """Test /api/official-curriculum/stages endpoint"""
    
    def test_stages_returns_three_stages(self):
        """Stages API should return exactly 3 stages"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/stages")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3, f"Expected 3 stages, got {len(data)}"
        
    def test_stages_have_required_fields(self):
        """Each stage should have all required fields"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/stages")
        data = response.json()
        
        required_fields = ["id", "name_ar", "name_en", "order", "grades_count", "is_official", "is_locked"]
        
        for stage in data:
            for field in required_fields:
                assert field in stage, f"Stage missing field: {field}"
            assert stage["is_official"] == True
            assert stage["is_locked"] == True
            
    def test_stages_ordered_correctly(self):
        """Stages should be ordered: primary, middle, secondary"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/stages")
        data = response.json()
        
        assert data[0]["id"] == "stage-primary"
        assert data[1]["id"] == "stage-middle"
        assert data[2]["id"] == "stage-secondary"
        
        # Verify Arabic names
        assert "ابتدائية" in data[0]["name_ar"]
        assert "متوسطة" in data[1]["name_ar"]
        assert "ثانوية" in data[2]["name_ar"]


class TestOfficialCurriculumTracks:
    """Test /api/official-curriculum/tracks endpoint"""
    
    def test_tracks_returns_eight_tracks(self):
        """Tracks API should return exactly 8 tracks"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/tracks")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 8, f"Expected 8 tracks, got {len(data)}"
        
    def test_tracks_have_required_fields(self):
        """Each track should have all required fields"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/tracks")
        data = response.json()
        
        required_fields = ["id", "name_ar", "name_en", "applicable_stages", "order", "is_official", "is_locked"]
        
        for track in data:
            for field in required_fields:
                assert field in track, f"Track missing field: {field}"
            assert track["is_official"] == True
            assert track["is_locked"] == True
            assert isinstance(track["applicable_stages"], list)
            
    def test_tracks_filter_by_stage(self):
        """Tracks should be filterable by stage_id"""
        # Filter for secondary stage tracks
        response = requests.get(f"{BASE_URL}/api/official-curriculum/tracks?stage_id=stage-secondary")
        assert response.status_code == 200
        
        data = response.json()
        # Secondary stage should have 6 tracks (common first year + 5 specialized)
        assert len(data) >= 5, f"Expected at least 5 secondary tracks, got {len(data)}"
        
        for track in data:
            assert "stage-secondary" in track["applicable_stages"]


class TestOfficialCurriculumGrades:
    """Test /api/official-curriculum/grades endpoint"""
    
    def test_grades_returns_29_grades(self):
        """Grades API should return exactly 29 grades"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/grades")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 29, f"Expected 29 grades, got {len(data)}"
        
    def test_grades_have_required_fields(self):
        """Each grade should have all required fields"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/grades")
        data = response.json()
        
        required_fields = ["id", "stage_id", "track_id", "name_ar", "name_en", "grade_number", "order", "is_official", "is_locked"]
        
        for grade in data:
            for field in required_fields:
                assert field in grade, f"Grade missing field: {field}"
            assert grade["is_official"] == True
            assert grade["is_locked"] == True
            
    def test_grades_filter_by_stage(self):
        """Grades should be filterable by stage_id"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/grades?stage_id=stage-primary")
        assert response.status_code == 200
        
        data = response.json()
        # Primary stage should have grades (6 general + 6 quran = 12)
        assert len(data) >= 6, f"Expected at least 6 primary grades, got {len(data)}"
        
        for grade in data:
            assert grade["stage_id"] == "stage-primary"
            
    def test_grades_enriched_with_stage_track_names(self):
        """Grades should include stage_name_ar and track_name_ar"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/grades")
        data = response.json()
        
        for grade in data:
            assert "stage_name_ar" in grade
            assert "track_name_ar" in grade
            assert grade["stage_name_ar"] != ""
            assert grade["track_name_ar"] != ""


class TestOfficialCurriculumSubjects:
    """Test /api/official-curriculum/subjects endpoint"""
    
    def test_subjects_returns_81_subjects(self):
        """Subjects API should return exactly 81 subjects"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/subjects")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 81, f"Expected 81 subjects, got {len(data)}"
        
    def test_subjects_have_required_fields(self):
        """Each subject should have all required fields"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/subjects")
        data = response.json()
        
        required_fields = ["id", "name_ar", "name_en", "category", "is_official", "is_locked"]
        
        for subject in data:
            for field in required_fields:
                assert field in subject, f"Subject missing field: {field}"
            assert subject["is_official"] == True
            assert subject["is_locked"] == True
            
    def test_subjects_filter_by_category(self):
        """Subjects should be filterable by category"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/subjects?category=islamic")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) > 0, "Expected at least 1 islamic subject"
        
        for subject in data:
            assert subject["category"] == "islamic"


class TestOfficialCurriculumTeacherRankLoads:
    """Test /api/official-curriculum/teacher-rank-loads endpoint"""
    
    def test_rank_loads_returns_seven_ranks(self):
        """Teacher Rank Loads API should return exactly 7 ranks"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/teacher-rank-loads")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 7, f"Expected 7 teacher ranks, got {len(data)}"
        
    def test_rank_loads_have_required_fields(self):
        """Each rank should have all required fields"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/teacher-rank-loads")
        data = response.json()
        
        required_fields = ["id", "rank_name_ar", "rank_name_en", "weekly_periods", "is_special_ed", "is_official", "is_locked", "order"]
        
        for rank in data:
            for field in required_fields:
                assert field in rank, f"Rank missing field: {field}"
            assert rank["is_official"] == True
            assert rank["is_locked"] == True
            
    def test_rank_loads_weekly_periods_correct(self):
        """Verify weekly periods for each rank"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/teacher-rank-loads")
        data = response.json()
        
        # Expected weekly periods by rank
        expected_periods = {
            "rank-teacher": 24,
            "rank-practitioner": 24,
            "rank-advanced": 22,
            "rank-expert": 18,
            "rank-practitioner-sped": 18,
            "rank-advanced-sped": 16,
            "rank-expert-sped": 14
        }
        
        for rank in data:
            if rank["id"] in expected_periods:
                assert rank["weekly_periods"] == expected_periods[rank["id"]], \
                    f"Rank {rank['id']} expected {expected_periods[rank['id']]} periods, got {rank['weekly_periods']}"
                    
    def test_rank_loads_special_ed_flags(self):
        """Verify special education flags are correct"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/teacher-rank-loads")
        data = response.json()
        
        for rank in data:
            if "sped" in rank["id"]:
                assert rank["is_special_ed"] == True, f"Rank {rank['id']} should be special ed"
            else:
                assert rank["is_special_ed"] == False, f"Rank {rank['id']} should not be special ed"


class TestOfficialCurriculumGradeSubjects:
    """Test /api/official-curriculum/grade-subjects/{grade_id} endpoint"""
    
    def test_grade_subjects_returns_data(self):
        """Grade subjects API should return subject distribution for a grade"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/grade-subjects/grade-p1-gen")
        assert response.status_code == 200
        
        data = response.json()
        assert "grade" in data
        assert "subjects" in data
        assert "summary" in data
        assert data["is_official"] == True
        assert data["is_locked"] == True
        
    def test_grade_subjects_has_correct_structure(self):
        """Grade subjects should have correct structure"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/grade-subjects/grade-p1-gen")
        data = response.json()
        
        # Check grade info
        assert data["grade"]["id"] == "grade-p1-gen"
        assert data["grade"]["name_ar"] == "الصف الأول الابتدائي"
        
        # Check subjects list
        assert len(data["subjects"]) > 0
        
        # Check each subject has required fields
        for subject in data["subjects"]:
            assert "subject_name_ar" in subject
            assert "weekly_periods" in subject
            assert "annual_periods" in subject
            assert "period_type" in subject
            
    def test_grade_subjects_summary(self):
        """Grade subjects should include summary statistics"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/grade-subjects/grade-p1-gen")
        data = response.json()
        
        summary = data["summary"]
        assert "total_subjects" in summary
        assert "total_annual_periods" in summary
        assert summary["total_subjects"] > 0
        assert summary["total_annual_periods"] > 0
        
    def test_grade_subjects_not_found(self):
        """Grade subjects should return 404 for invalid grade_id"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/grade-subjects/invalid-grade-id")
        assert response.status_code == 404


class TestOfficialCurriculumStageFull:
    """Test /api/official-curriculum/stage/{stage_id}/full endpoint"""
    
    def test_stage_full_returns_complete_curriculum(self):
        """Stage full API should return complete curriculum for a stage"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/stage/stage-primary/full")
        assert response.status_code == 200
        
        data = response.json()
        assert "stage" in data
        assert "tracks" in data
        assert data["is_official"] == True
        assert data["is_locked"] == True
        
    def test_stage_full_has_tracks_with_grades(self):
        """Stage full should include tracks with their grades"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/stage/stage-primary/full")
        data = response.json()
        
        assert len(data["tracks"]) > 0
        
        for track in data["tracks"]:
            assert "grades" in track
            assert "grades_count" in track
            assert len(track["grades"]) > 0
            
    def test_stage_full_grades_have_subjects(self):
        """Each grade in stage full should have subjects"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/stage/stage-primary/full")
        data = response.json()
        
        for track in data["tracks"]:
            for grade in track["grades"]:
                assert "subjects" in grade
                assert "subjects_count" in grade
                assert "total_annual_periods" in grade
                assert len(grade["subjects"]) > 0
                
    def test_stage_full_not_found(self):
        """Stage full should return 404 for invalid stage_id"""
        response = requests.get(f"{BASE_URL}/api/official-curriculum/stage/invalid-stage-id/full")
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
