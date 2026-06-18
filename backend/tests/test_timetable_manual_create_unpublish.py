"""
Tests: POST /smart-scheduling/timetables/manual  (manual timetable creation)
       POST /smart-scheduling/timetable/{id}/unpublish  (unpublish)
       GET  /smart-scheduling/timetable/versions  (versions list with status filter)
       Timetable ORM audit columns (is_published, published_at, published_by, created_by, updated_by)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

PRINCIPAL_EMAIL = "mudeer@faarabi.edu"
PRINCIPAL_PASSWORD = "Test@1234"


class TestManualTimetableCreate:
    """POST /smart-scheduling/timetables/manual"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD,
        })
        if resp.status_code != 200:
            pytest.skip(f"Login failed: {resp.status_code} — {resp.text[:200]}")
        token = resp.json().get("access_token")
        user = resp.json().get("user", {})
        self.school_id = user.get("tenant_id") or user.get("school_id")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        if self.school_id:
            self.session.headers.update({"X-School-Context": self.school_id})

    def test_01_create_manual_timetable_succeeds(self):
        """Creating a named blank draft returns 201 with correct fields."""
        resp = self.session.post(f"{BASE_URL}/api/smart-scheduling/timetables/manual", json={
            "name": "جدول اختبار يدوي — pytest",
        })
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("status") == "draft"
        assert data.get("id")
        assert data.get("name") == "جدول اختبار يدوي — pytest"
        assert data.get("is_published") is False
        assert data.get("generation_mode") == "manual"

    def test_02_create_manual_timetable_missing_name_rejected(self):
        """Creating without a name should fail validation (422)."""
        resp = self.session.post(f"{BASE_URL}/api/smart-scheduling/timetables/manual", json={})
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"

    def test_03_create_manual_timetable_empty_name_rejected(self):
        """Creating with a whitespace-only name should fail validation (422)."""
        resp = self.session.post(f"{BASE_URL}/api/smart-scheduling/timetables/manual", json={
            "name": "   ",
        })
        # Either 422 (Pydantic min_length) or 400 (server strip+empty check)
        assert resp.status_code in (400, 422), f"Got {resp.status_code}: {resp.text}"

    def test_04_created_timetable_appears_in_versions_list(self):
        """A newly created manual timetable should appear in GET /versions."""
        name = "pytest-versions-visibility"
        create_resp = self.session.post(
            f"{BASE_URL}/api/smart-scheduling/timetables/manual",
            json={"name": name},
        )
        assert create_resp.status_code == 201, create_resp.text
        new_id = create_resp.json()["id"]

        versions_resp = self.session.get(f"{BASE_URL}/api/smart-scheduling/timetable/versions")
        assert versions_resp.status_code == 200, versions_resp.text
        versions = versions_resp.json().get("versions", [])
        ids = [v["id"] for v in versions]
        assert new_id in ids, f"New timetable {new_id} not found in versions: {ids}"


class TestTimetableVersionsFilter:
    """GET /smart-scheduling/timetable/versions status filter"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD,
        })
        if resp.status_code != 200:
            pytest.skip(f"Login failed: {resp.status_code}")
        token = resp.json().get("access_token")
        user = resp.json().get("user", {})
        self.school_id = user.get("tenant_id") or user.get("school_id")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        if self.school_id:
            self.session.headers.update({"X-School-Context": self.school_id})

    def test_versions_default_excludes_archived(self):
        """Default /versions must not return archived timetables."""
        resp = self.session.get(f"{BASE_URL}/api/smart-scheduling/timetable/versions")
        assert resp.status_code == 200, resp.text
        for v in resp.json().get("versions", []):
            assert v.get("status") != "archived", (
                f"Archived timetable {v['id']} leaked into default versions response"
            )

    def test_versions_status_filter_draft_only(self):
        """?status=draft must return only draft timetables."""
        resp = self.session.get(
            f"{BASE_URL}/api/smart-scheduling/timetable/versions",
            params={"status": "draft"},
        )
        assert resp.status_code == 200, resp.text
        for v in resp.json().get("versions", []):
            assert v.get("status") == "draft", (
                f"Non-draft timetable {v['id']} (status={v.get('status')}) "
                f"returned by ?status=draft"
            )

    def test_versions_response_includes_audit_fields(self):
        """Response items must include published_by and updated_by fields."""
        resp = self.session.get(f"{BASE_URL}/api/smart-scheduling/timetable/versions")
        assert resp.status_code == 200, resp.text
        versions = resp.json().get("versions", [])
        if versions:
            v = versions[0]
            assert "published_by" in v
            assert "updated_by" in v


class TestTimetableUnpublish:
    """POST /smart-scheduling/timetable/{id}/unpublish"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD,
        })
        if resp.status_code != 200:
            pytest.skip(f"Login failed: {resp.status_code}")
        token = resp.json().get("access_token")
        user = resp.json().get("user", {})
        self.school_id = user.get("tenant_id") or user.get("school_id")
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        if self.school_id:
            self.session.headers.update({"X-School-Context": self.school_id})

    def test_unpublish_draft_timetable_rejected(self):
        """Attempting to unpublish a draft timetable must return 409."""
        create_resp = self.session.post(
            f"{BASE_URL}/api/smart-scheduling/timetables/manual",
            json={"name": "pytest-unpublish-draft-guard"},
        )
        assert create_resp.status_code == 201, create_resp.text
        draft_id = create_resp.json()["id"]

        unpublish_resp = self.session.post(
            f"{BASE_URL}/api/smart-scheduling/timetable/{draft_id}/unpublish"
        )
        assert unpublish_resp.status_code == 409, (
            f"Expected 409 for unpublishing a draft, got {unpublish_resp.status_code}: "
            f"{unpublish_resp.text}"
        )
        body = unpublish_resp.json()
        # The middleware serializes HTTPException as {"error": {"code": ...}}
        # or {"detail": {...}}; accept both forms.
        error_code = (
            (body.get("error") or {}).get("code")
            or (body.get("detail") or {}).get("code") if isinstance(body.get("detail"), dict) else None
            or ("NOT_PUBLISHED" if "NOT_PUBLISHED" in unpublish_resp.text else None)
        )
        assert error_code == "NOT_PUBLISHED", f"Unexpected body: {unpublish_resp.text}"

    def test_unpublish_nonexistent_timetable_returns_404(self):
        """Unpublishing a nonexistent timetable must return 404."""
        resp = self.session.post(
            f"{BASE_URL}/api/smart-scheduling/timetable/nonexistent-id-000/unpublish"
        )
        assert resp.status_code == 404, f"Got {resp.status_code}: {resp.text}"
