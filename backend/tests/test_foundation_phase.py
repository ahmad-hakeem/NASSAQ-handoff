"""
Test Foundation Phase APIs - نَسَّق
Tests for:
- GET /api/public/contact-info (no auth required)
- POST /api/academic/stages/seed-defaults (platform admin)
- GET /api/academic/stages (authenticated)
- New engines verification (SchedulingEngine, AttendanceEngine, AssessmentEngine, NotificationEngine, AuditLogEngine)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
PLATFORM_ADMIN_EMAIL = "info@nassaqapp.com"
PLATFORM_ADMIN_PASSWORD = "NassaqAdmin2026!##$$HBJ"


class TestPublicContactAPI:
    """Test public contact info API - no authentication required"""
    
    def test_get_contact_info_no_auth(self):
        """GET /api/public/contact-info should work without authentication"""
        response = requests.get(f"{BASE_URL}/api/public/contact-info")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify required fields exist
        assert "primary_email" in data, "Missing primary_email field"
        assert "support_email" in data, "Missing support_email field"
        assert "primary_phone" in data, "Missing primary_phone field"
        assert "address" in data, "Missing address field"
        assert "working_hours" in data, "Missing working_hours field"
        assert "website" in data, "Missing website field"
        assert "owner_name" in data, "Missing owner_name field"
        assert "social_media" in data, "Missing social_media field"
        
        # Verify default values
        assert data["primary_email"] == "info@nassaqapp.com", f"Unexpected primary_email: {data['primary_email']}"
        assert data["support_email"] == "support@nassaqapp.com", f"Unexpected support_email: {data['support_email']}"
        
        print(f"✓ Public contact info API working correctly")
        print(f"  - Primary Email: {data['primary_email']}")
        print(f"  - Support Email: {data['support_email']}")
        print(f"  - Phone: {data['primary_phone']}")
        print(f"  - Address: {data['address']}")
        print(f"  - Owner: {data['owner_name']}")


class TestAcademicStagesAPI:
    """Test academic stages APIs - requires authentication"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for platform admin"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": PLATFORM_ADMIN_EMAIL,
                "password": PLATFORM_ADMIN_PASSWORD
            }
        )
        
        if response.status_code != 200:
            pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")
        
        data = response.json()
        assert "access_token" in data, "Missing access_token in login response"
        
        print(f"✓ Authenticated as platform admin: {PLATFORM_ADMIN_EMAIL}")
        return data["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_seed_default_stages(self, auth_headers):
        """POST /api/academic/stages/seed-defaults should seed educational stages"""
        response = requests.post(
            f"{BASE_URL}/api/academic/stages/seed-defaults",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "message" in data, "Missing message field"
        assert "added" in data, "Missing added field"
        
        print(f"✓ Seed default stages API working")
        print(f"  - Message: {data['message']}")
        print(f"  - Added: {data['added']} stages")
    
    def test_get_educational_stages(self, auth_headers):
        """GET /api/academic/stages should return educational stages"""
        response = requests.get(
            f"{BASE_URL}/api/academic/stages",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify response structure
        assert "stages" in data, "Missing stages field"
        assert "total" in data, "Missing total field"
        assert isinstance(data["stages"], list), "stages should be a list"
        
        # Verify stages have required fields
        if data["stages"]:
            stage = data["stages"][0]
            assert "code" in stage, "Stage missing code field"
            assert "name_ar" in stage, "Stage missing name_ar field"
            assert "name_en" in stage, "Stage missing name_en field"
            assert "order" in stage, "Stage missing order field"
        
        print(f"✓ Get educational stages API working")
        print(f"  - Total stages: {data['total']}")
        
        for stage in data["stages"]:
            print(f"  - {stage.get('code')}: {stage.get('name_ar')} ({stage.get('name_en')})")
    
    def test_seed_stages_requires_auth(self):
        """POST /api/academic/stages/seed-defaults should require authentication"""
        response = requests.post(f"{BASE_URL}/api/academic/stages/seed-defaults")
        
        # Should return 403 (Forbidden) or 401 (Unauthorized)
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        
        print(f"✓ Seed stages correctly requires authentication (status: {response.status_code})")
    
    def test_get_stages_requires_auth(self):
        """GET /api/academic/stages should require authentication"""
        response = requests.get(f"{BASE_URL}/api/academic/stages")
        
        # Should return 403 (Forbidden) or 401 (Unauthorized)
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        
        print(f"✓ Get stages correctly requires authentication (status: {response.status_code})")


class TestEnginesExist:
    """Verify new engines are properly created and importable"""
    
    def test_scheduling_engine_exists(self):
        """Verify SchedulingEngine is properly defined"""
        # This test verifies the engine file exists and has proper structure
        # The engine is not yet connected to API routes
        import sys
        sys.path.insert(0, '/app/backend')
        
        from engines.scheduling_engine import SchedulingEngine, ScheduleStatus, SessionStatus, DayOfWeek
        
        assert SchedulingEngine is not None, "SchedulingEngine not found"
        assert ScheduleStatus is not None, "ScheduleStatus enum not found"
        assert SessionStatus is not None, "SessionStatus enum not found"
        assert DayOfWeek is not None, "DayOfWeek enum not found"
        
        # Verify enum values
        assert ScheduleStatus.DRAFT.value == "draft"
        assert ScheduleStatus.PUBLISHED.value == "published"
        assert ScheduleStatus.ARCHIVED.value == "archived"
        
        print("✓ SchedulingEngine exists with proper structure")
        print(f"  - ScheduleStatus: {[s.value for s in ScheduleStatus]}")
        print(f"  - SessionStatus: {[s.value for s in SessionStatus]}")
        print(f"  - DayOfWeek: {[d.value for d in DayOfWeek]}")
    
    def test_attendance_engine_exists(self):
        """Verify AttendanceEngine is properly defined"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        from engines.attendance_engine import AttendanceEngine, AttendanceStatus, ExcuseType
        
        assert AttendanceEngine is not None, "AttendanceEngine not found"
        assert AttendanceStatus is not None, "AttendanceStatus enum not found"
        assert ExcuseType is not None, "ExcuseType enum not found"
        
        # Verify enum values
        assert AttendanceStatus.PRESENT.value == "present"
        assert AttendanceStatus.ABSENT.value == "absent"
        assert AttendanceStatus.LATE.value == "late"
        assert AttendanceStatus.EXCUSED.value == "excused"
        
        print("✓ AttendanceEngine exists with proper structure")
        print(f"  - AttendanceStatus: {[s.value for s in AttendanceStatus]}")
        print(f"  - ExcuseType: {[e.value for e in ExcuseType]}")
    
    def test_assessment_engine_exists(self):
        """Verify AssessmentEngine is properly defined"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        from engines.assessment_engine import AssessmentEngine, AssessmentType, GradeScale
        
        assert AssessmentEngine is not None, "AssessmentEngine not found"
        assert AssessmentType is not None, "AssessmentType enum not found"
        assert GradeScale is not None, "GradeScale enum not found"
        
        # Verify enum values
        assert AssessmentType.QUIZ.value == "quiz"
        assert AssessmentType.EXAM.value == "exam"
        assert AssessmentType.MIDTERM.value == "midterm"
        assert AssessmentType.FINAL.value == "final"
        
        print("✓ AssessmentEngine exists with proper structure")
        print(f"  - AssessmentType: {[t.value for t in AssessmentType]}")
        print(f"  - GradeScale: {[g.value for g in GradeScale]}")
    
    def test_notification_engine_exists(self):
        """Verify NotificationEngine is properly defined"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        from engines.notification_engine import (
            NotificationEngine, 
            NotificationType, 
            NotificationPriority, 
            NotificationCategory
        )
        
        assert NotificationEngine is not None, "NotificationEngine not found"
        assert NotificationType is not None, "NotificationType enum not found"
        assert NotificationPriority is not None, "NotificationPriority enum not found"
        assert NotificationCategory is not None, "NotificationCategory enum not found"
        
        # Verify enum values
        assert NotificationType.INFO.value == "info"
        assert NotificationType.WARNING.value == "warning"
        assert NotificationPriority.HIGH.value == "high"
        assert NotificationCategory.ATTENDANCE.value == "attendance"
        
        print("✓ NotificationEngine exists with proper structure")
        print(f"  - NotificationType: {[t.value for t in NotificationType]}")
        print(f"  - NotificationPriority: {[p.value for p in NotificationPriority]}")
        print(f"  - NotificationCategory: {[c.value for c in NotificationCategory]}")
    
    def test_audit_engine_exists(self):
        """Verify AuditLogEngine is properly defined"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        from engines.audit_engine import AuditLogEngine, AuditAction, AuditSeverity
        
        assert AuditLogEngine is not None, "AuditLogEngine not found"
        assert AuditAction is not None, "AuditAction enum not found"
        assert AuditSeverity is not None, "AuditSeverity enum not found"
        
        # Verify enum values
        assert AuditAction.LOGIN.value == "auth.login"
        assert AuditAction.USER_CREATED.value == "user.created"
        assert AuditSeverity.CRITICAL.value == "critical"
        assert AuditSeverity.HIGH.value == "high"
        
        print("✓ AuditLogEngine exists with proper structure")
        print(f"  - AuditSeverity: {[s.value for s in AuditSeverity]}")
        print(f"  - Sample AuditActions: LOGIN={AuditAction.LOGIN.value}, USER_CREATED={AuditAction.USER_CREATED.value}")
    
    def test_engines_init_exports(self):
        """Verify engines __init__.py exports all engines"""
        import sys
        sys.path.insert(0, '/app/backend')
        
        from engines import (
            IdentityEngine,
            TenantEngine,
            AcademicStructureEngine,
            SchedulingEngine,
            AttendanceEngine,
            AssessmentEngine,
            BehaviourEngine,
            NotificationEngine,
            AuditLogEngine
        )
        
        assert IdentityEngine is not None
        assert TenantEngine is not None
        assert AcademicStructureEngine is not None
        assert SchedulingEngine is not None
        assert AttendanceEngine is not None
        assert AssessmentEngine is not None
        assert BehaviourEngine is not None
        assert NotificationEngine is not None
        assert AuditLogEngine is not None
        
        print("✓ All engines properly exported from engines/__init__.py")
        print("  - IdentityEngine")
        print("  - TenantEngine")
        print("  - AcademicStructureEngine")
        print("  - SchedulingEngine")
        print("  - AttendanceEngine")
        print("  - AssessmentEngine")
        print("  - BehaviourEngine")
        print("  - NotificationEngine")
        print("  - AuditLogEngine")


class TestHealthCheck:
    """Basic health check tests"""
    
    def test_api_root(self):
        """Test API root endpoint"""
        response = requests.get(f"{BASE_URL}/api/")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "message" in data or "status" in data, "Missing expected fields in response"
        
        print(f"✓ API root endpoint working: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
