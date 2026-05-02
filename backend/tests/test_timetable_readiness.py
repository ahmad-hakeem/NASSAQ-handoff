"""
Test Timetable Readiness Engine APIs
Tests for School Settings Readiness Engine - نظام التحقق من جاهزية إعدادات المدرسة

Endpoints tested:
- GET /api/timetable-readiness/check - Full readiness check
- GET /api/timetable-readiness/summary - Quick summary
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://school-timetable-ai.preview.emergentagent.com')

class TestTimetableReadinessCheck:
    """Tests for GET /api/timetable-readiness/check endpoint"""
    
    def test_readiness_check_returns_200(self):
        """Test that readiness check endpoint returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/timetable-readiness/check",
            headers={"X-School-Context": "school-001"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Readiness check endpoint returns 200")
    
    def test_readiness_check_response_structure(self):
        """Test that readiness check returns correct response structure"""
        response = requests.get(
            f"{BASE_URL}/api/timetable-readiness/check",
            headers={"X-School-Context": "school-001"}
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # Check required top-level fields
        required_fields = [
            "status", "overall_score", "max_score", "percentage",
            "categories", "critical_issues", "warnings", "info_items",
            "can_generate", "generated_at", "summary"
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        print("✓ Response contains all required fields")
    
    def test_readiness_check_status_values(self):
        """Test that status is one of valid values"""
        response = requests.get(
            f"{BASE_URL}/api/timetable-readiness/check",
            headers={"X-School-Context": "school-001"}
        )
        assert response.status_code == 200
        
        data = response.json()
        valid_statuses = ["NOT_READY", "PARTIALLY_READY", "FULLY_READY"]
        assert data["status"] in valid_statuses, f"Invalid status: {data['status']}"
        print(f"✓ Status is valid: {data['status']}")
    
    def test_readiness_check_categories_structure(self):
        """Test that all 8 categories are present with correct structure"""
        response = requests.get(
            f"{BASE_URL}/api/timetable-readiness/check",
            headers={"X-School-Context": "school-001"}
        )
        assert response.status_code == 200
        
        data = response.json()
        categories = data.get("categories", {})
        
        # Check all 8 categories are present
        expected_categories = [
            "academic_context",      # السياق الأكاديمي
            "school_days",           # أيام الدراسة
            "day_structure",         # هيكل اليوم
            "classes",               # الفصول
            "teachers",              # المعلمون
            "teacher_assignments",   # الإسنادات
            "constraints",           # القيود
            "official_curriculum"    # المنهج الرسمي
        ]
        
        for cat in expected_categories:
            assert cat in categories, f"Missing category: {cat}"
            
            # Check category structure
            cat_data = categories[cat]
            assert "name_ar" in cat_data, f"Category {cat} missing name_ar"
            assert "name_en" in cat_data, f"Category {cat} missing name_en"
            assert "score" in cat_data, f"Category {cat} missing score"
            assert "max_score" in cat_data, f"Category {cat} missing max_score"
            assert "status" in cat_data, f"Category {cat} missing status"
            assert "issues" in cat_data, f"Category {cat} missing issues"
        
        print(f"✓ All 8 categories present with correct structure")
    
    def test_readiness_check_percentage_calculation(self):
        """Test that percentage is correctly calculated"""
        response = requests.get(
            f"{BASE_URL}/api/timetable-readiness/check",
            headers={"X-School-Context": "school-001"}
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify percentage calculation
        expected_percentage = round((data["overall_score"] / data["max_score"]) * 100, 1)
        assert abs(data["percentage"] - expected_percentage) < 0.2, \
            f"Percentage mismatch: expected {expected_percentage}, got {data['percentage']}"
        
        print(f"✓ Percentage correctly calculated: {data['percentage']}%")
    
    def test_readiness_check_issues_have_fix_links(self):
        """Test that critical issues have fix_link for navigation"""
        response = requests.get(
            f"{BASE_URL}/api/timetable-readiness/check",
            headers={"X-School-Context": "school-001"}
        )
        assert response.status_code == 200
        
        data = response.json()
        critical_issues = data.get("critical_issues", [])
        
        # Check that critical issues have fix_link
        for issue in critical_issues:
            assert "id" in issue, "Issue missing id"
            assert "type" in issue, "Issue missing type"
            assert "message_ar" in issue, "Issue missing message_ar"
            assert "message_en" in issue, "Issue missing message_en"
            # fix_link is optional but, when present, must be an in-app
            # path. After Task #115 the schedule settings sub-tabs live
            # under `/school/schedule?tab=settings&sub=...`; other
            # categories still link to standalone pages such as
            # `/school/teachers` or `/academic-structure`.
            if issue.get("fix_link"):
                allowed_prefixes = (
                    "/school/schedule?tab=settings",
                    "/school/settings",
                    "/school/classes",
                    "/school/teachers",
                    "/school/subjects",
                    "/academic-structure",
                )
                assert issue["fix_link"].startswith(allowed_prefixes), \
                    f"Invalid fix_link format: {issue['fix_link']}"
        
        print(f"✓ Critical issues ({len(critical_issues)}) have proper structure")
    
    def test_readiness_check_can_generate_logic(self):
        """Test that can_generate is false when there are critical issues"""
        response = requests.get(
            f"{BASE_URL}/api/timetable-readiness/check",
            headers={"X-School-Context": "school-001"}
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # If there are critical issues, can_generate should be false
        if len(data.get("critical_issues", [])) > 0:
            assert data["can_generate"] == False, \
                "can_generate should be False when critical issues exist"
            assert data["status"] == "NOT_READY", \
                "Status should be NOT_READY when critical issues exist"
        
        print(f"✓ can_generate logic is correct: {data['can_generate']}")
    
    def test_readiness_check_summary_counts(self):
        """Test that summary counts match actual issues"""
        response = requests.get(
            f"{BASE_URL}/api/timetable-readiness/check",
            headers={"X-School-Context": "school-001"}
        )
        assert response.status_code == 200
        
        data = response.json()
        summary = data.get("summary", {})
        
        # Verify counts match
        assert summary.get("critical_count") == len(data.get("critical_issues", [])), \
            "Critical count mismatch"
        assert summary.get("warning_count") == len(data.get("warnings", [])), \
            "Warning count mismatch"
        assert summary.get("info_count") == len(data.get("info_items", [])), \
            "Info count mismatch"
        
        print(f"✓ Summary counts match: {summary.get('critical_count')} critical, {summary.get('warning_count')} warnings")


class TestTimetableReadinessSummary:
    """Tests for GET /api/timetable-readiness/summary endpoint"""
    
    def test_summary_returns_200(self):
        """Test that summary endpoint returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/timetable-readiness/summary",
            headers={"X-School-Context": "school-001"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Summary endpoint returns 200")
    
    def test_summary_response_structure(self):
        """Test that summary returns correct response structure"""
        response = requests.get(
            f"{BASE_URL}/api/timetable-readiness/summary",
            headers={"X-School-Context": "school-001"}
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # Check required fields
        required_fields = [
            "status", "status_message_ar", "status_message_en",
            "status_color", "status_icon", "percentage",
            "can_generate", "critical_count", "warning_count"
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        print("✓ Summary contains all required fields")
    
    def test_summary_status_color_mapping(self):
        """Test that status color matches status"""
        response = requests.get(
            f"{BASE_URL}/api/timetable-readiness/summary",
            headers={"X-School-Context": "school-001"}
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify color mapping
        status_color_map = {
            "NOT_READY": "red",
            "PARTIALLY_READY": "yellow",
            "FULLY_READY": "green"
        }
        
        expected_color = status_color_map.get(data["status"])
        assert data["status_color"] == expected_color, \
            f"Color mismatch: expected {expected_color}, got {data['status_color']}"
        
        print(f"✓ Status color correctly mapped: {data['status']} -> {data['status_color']}")
    
    def test_summary_status_icon_mapping(self):
        """Test that status icon matches status"""
        response = requests.get(
            f"{BASE_URL}/api/timetable-readiness/summary",
            headers={"X-School-Context": "school-001"}
        )
        assert response.status_code == 200
        
        data = response.json()
        
        # Verify icon mapping
        status_icon_map = {
            "NOT_READY": "x-circle",
            "PARTIALLY_READY": "alert-triangle",
            "FULLY_READY": "check-circle"
        }
        
        expected_icon = status_icon_map.get(data["status"])
        assert data["status_icon"] == expected_icon, \
            f"Icon mismatch: expected {expected_icon}, got {data['status_icon']}"
        
        print(f"✓ Status icon correctly mapped: {data['status']} -> {data['status_icon']}")
    
    def test_summary_arabic_messages(self):
        """Test that Arabic messages are present and non-empty"""
        response = requests.get(
            f"{BASE_URL}/api/timetable-readiness/summary",
            headers={"X-School-Context": "school-001"}
        )
        assert response.status_code == 200
        
        data = response.json()
        
        assert data["status_message_ar"], "Arabic message should not be empty"
        assert data["status_message_en"], "English message should not be empty"
        
        # Verify Arabic message contains Arabic characters
        assert any('\u0600' <= c <= '\u06FF' for c in data["status_message_ar"]), \
            "Arabic message should contain Arabic characters"
        
        print(f"✓ Arabic message present: {data['status_message_ar'][:50]}...")
    
    def test_summary_consistency_with_full_check(self):
        """Test that summary is consistent with full check"""
        # Get full check
        full_response = requests.get(
            f"{BASE_URL}/api/timetable-readiness/check",
            headers={"X-School-Context": "school-001"}
        )
        full_data = full_response.json()
        
        # Get summary
        summary_response = requests.get(
            f"{BASE_URL}/api/timetable-readiness/summary",
            headers={"X-School-Context": "school-001"}
        )
        summary_data = summary_response.json()
        
        # Verify consistency
        assert full_data["status"] == summary_data["status"], "Status mismatch"
        assert full_data["percentage"] == summary_data["percentage"], "Percentage mismatch"
        assert full_data["can_generate"] == summary_data["can_generate"], "can_generate mismatch"
        assert full_data["summary"]["critical_count"] == summary_data["critical_count"], "Critical count mismatch"
        assert full_data["summary"]["warning_count"] == summary_data["warning_count"], "Warning count mismatch"
        
        print("✓ Summary is consistent with full check")


class TestTimetableReadinessWithDifferentSchools:
    """Tests for readiness check with different school contexts"""
    
    def test_readiness_with_default_school(self):
        """Test readiness check without school context header"""
        response = requests.get(f"{BASE_URL}/api/timetable-readiness/check")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Readiness check works without school context (uses default)")
    
    def test_readiness_with_explicit_school_context(self):
        """Test readiness check with explicit school context"""
        response = requests.get(
            f"{BASE_URL}/api/timetable-readiness/check",
            headers={"X-School-Context": "school-001"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "categories" in data
        
        print("✓ Readiness check works with explicit school context")


class TestTimetableReadinessCategories:
    """Detailed tests for each readiness category"""
    
    def test_academic_context_category(self):
        """Test academic context category (العام الدراسي والفصل)"""
        response = requests.get(
            f"{BASE_URL}/api/timetable-readiness/check",
            headers={"X-School-Context": "school-001"}
        )
        data = response.json()
        
        cat = data["categories"]["academic_context"]
        assert cat["name_ar"] == "السياق الأكاديمي"
        assert cat["name_en"] == "Academic Context"
        assert cat["max_score"] == 20
        
        print(f"✓ Academic context: {cat['score']}/{cat['max_score']} - {cat['status']}")
    
    def test_school_days_category(self):
        """Test school days category (أيام الدراسة)"""
        response = requests.get(
            f"{BASE_URL}/api/timetable-readiness/check",
            headers={"X-School-Context": "school-001"}
        )
        data = response.json()
        
        cat = data["categories"]["school_days"]
        assert cat["name_ar"] == "أيام الدراسة"
        assert cat["name_en"] == "School Days"
        assert cat["max_score"] == 15
        
        print(f"✓ School days: {cat['score']}/{cat['max_score']} - {cat['status']}")
    
    def test_day_structure_category(self):
        """Test day structure category (هيكل اليوم)"""
        response = requests.get(
            f"{BASE_URL}/api/timetable-readiness/check",
            headers={"X-School-Context": "school-001"}
        )
        data = response.json()
        
        cat = data["categories"]["day_structure"]
        assert cat["name_ar"] == "هيكل اليوم الدراسي"
        assert cat["name_en"] == "Day Structure"
        assert cat["max_score"] == 25
        
        print(f"✓ Day structure: {cat['score']}/{cat['max_score']} - {cat['status']}")
    
    def test_classes_category(self):
        """Test classes category (الفصول)"""
        response = requests.get(
            f"{BASE_URL}/api/timetable-readiness/check",
            headers={"X-School-Context": "school-001"}
        )
        data = response.json()
        
        cat = data["categories"]["classes"]
        assert cat["name_ar"] == "الفصول الدراسية"
        assert cat["name_en"] == "Classes"
        assert cat["max_score"] == 20
        
        print(f"✓ Classes: {cat['score']}/{cat['max_score']} - {cat['status']}")
    
    def test_teachers_category(self):
        """Test teachers category (المعلمون)"""
        response = requests.get(
            f"{BASE_URL}/api/timetable-readiness/check",
            headers={"X-School-Context": "school-001"}
        )
        data = response.json()
        
        cat = data["categories"]["teachers"]
        assert cat["name_ar"] == "المعلمون"
        assert cat["name_en"] == "Teachers"
        assert cat["max_score"] == 15
        
        print(f"✓ Teachers: {cat['score']}/{cat['max_score']} - {cat['status']}")
    
    def test_teacher_assignments_category(self):
        """Test teacher assignments category (الإسنادات)"""
        response = requests.get(
            f"{BASE_URL}/api/timetable-readiness/check",
            headers={"X-School-Context": "school-001"}
        )
        data = response.json()
        
        cat = data["categories"]["teacher_assignments"]
        assert cat["name_ar"] == "إسنادات المعلمين"
        assert cat["name_en"] == "Teacher Assignments"
        assert cat["max_score"] == 25
        
        print(f"✓ Teacher assignments: {cat['score']}/{cat['max_score']} - {cat['status']}")
    
    def test_constraints_category(self):
        """Test constraints category (القيود)"""
        response = requests.get(
            f"{BASE_URL}/api/timetable-readiness/check",
            headers={"X-School-Context": "school-001"}
        )
        data = response.json()
        
        cat = data["categories"]["constraints"]
        assert cat["name_ar"] == "القيود"
        assert cat["name_en"] == "Constraints"
        assert cat["max_score"] == 10
        
        print(f"✓ Constraints: {cat['score']}/{cat['max_score']} - {cat['status']}")
    
    def test_official_curriculum_category(self):
        """Test official curriculum category (المنهج الرسمي)"""
        response = requests.get(
            f"{BASE_URL}/api/timetable-readiness/check",
            headers={"X-School-Context": "school-001"}
        )
        data = response.json()
        
        cat = data["categories"]["official_curriculum"]
        assert cat["name_ar"] == "المنهج الرسمي"
        assert cat["name_en"] == "Official Curriculum"
        assert cat["max_score"] == 10
        
        print(f"✓ Official curriculum: {cat['score']}/{cat['max_score']} - {cat['status']}")


class TestFixLinkRegressions:
    """Static regression tests guarding the readiness `fix_link` URLs.

    These tests inspect the readiness route source so they do not need
    the backend to be running. They guarantee that:
      1. No legacy `/school/settings?tab=...` fix_link slips back in
         for the schedule-related categories that moved under
         `/school/schedule?tab=settings&sub=...` in Task #114/#115.
      2. A handful of representative issue IDs continue to point at
         the exact, currently-correct destinations.
    """

    ROUTE_FILE = os.path.join(
        os.path.dirname(__file__), "..", "routes", "timetable_readiness_routes.py"
    )

    @classmethod
    def _source(cls):
        with open(os.path.normpath(cls.ROUTE_FILE), encoding="utf-8") as f:
            return f.read()

    def test_no_legacy_settings_tab_fix_links(self):
        """The pre-Task-#114 `/school/settings?tab=...` deep links must
        not reappear in any `fix_link` value."""
        import re
        source = self._source()
        offenders = re.findall(
            r'fix_link\s*=\s*"(/school/settings\?tab=[^"]+)"', source
        )
        assert not offenders, (
            "Legacy /school/settings?tab=... fix_link(s) found — these "
            "tabs moved to /school/schedule?tab=settings&sub=...:\n  "
            + "\n  ".join(offenders)
        )

    def test_representative_issue_fix_links(self):
        """Spot-check that key issue IDs land on the expected sub-tab.

        Walks every `ReadinessIssue(...)` call in the source and pulls
        out its `id` and `fix_link` fields. We can't use a single greedy
        regex because some `message_ar`/`message_en` f-strings contain
        unbalanced `)` that confuse character-class scans.
        """
        import re
        source = self._source()
        expected = {
            "no-working-days":   "/school/schedule?tab=settings&sub=timings",
            "no-periods":        "/school/schedule?tab=settings&sub=timings",
            "no-duration":       "/school/schedule?tab=settings&sub=timings",
            "no-day-start":      "/school/schedule?tab=settings&sub=timings",
            "incomplete-time-slots":
                                 "/school/schedule?tab=settings&sub=timings",
            "no-hard-constraints":
                                 "/school/schedule?tab=settings&sub=constraints",
            "no-soft-constraints":
                                 "/school/schedule?tab=settings&sub=constraints",
            "no-class-subjects":
                                 "/school/schedule?tab=settings&sub=teacher-assignments",
            "capacity-overflow":
                                 "/school/schedule?tab=settings&sub=teacher-assignments",
            "no-grade-subject-links":
                                 "/school/settings?section=academic",
        }

        # Build a {issue_id -> fix_link} index by scanning each
        # ReadinessIssue(...) call. We look at the chunk of text from
        # one call's opening `(` up to (but not including) the next
        # call's opening — which always contains both id= and fix_link=.
        starts = [m.start() for m in re.finditer(r'ReadinessIssue\(', source)]
        starts.append(len(source))
        fix_links = {}
        overload_links = []
        for i in range(len(starts) - 1):
            chunk = source[starts[i]:starts[i + 1]]
            id_m = re.search(r'\bid\s*=\s*"([^"]+)"', chunk)
            fid_m = re.search(r'\bid\s*=\s*f"([^"]+)"', chunk)
            link_m = re.search(r'\bfix_link\s*=\s*"([^"]+)"', chunk)
            if not link_m:
                continue
            if id_m:
                fix_links[id_m.group(1)] = link_m.group(1)
            elif fid_m and fid_m.group(1).startswith("teacher-overload-"):
                overload_links.append(link_m.group(1))

        for issue_id, want_link in expected.items():
            assert issue_id in fix_links, (
                f"Could not locate fix_link for issue id={issue_id!r}"
            )
            got = fix_links[issue_id]
            assert got == want_link, (
                f"fix_link for {issue_id!r} regressed: "
                f"expected {want_link!r}, got {got!r}"
            )

        # Spot-check the dynamic teacher-overload-N family too.
        assert overload_links, "Could not locate teacher-overload-N fix_link"
        for got in overload_links:
            assert got == (
                "/school/schedule?tab=settings&sub=teacher-assignments"
            ), f"teacher-overload-N fix_link regressed: {got!r}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
