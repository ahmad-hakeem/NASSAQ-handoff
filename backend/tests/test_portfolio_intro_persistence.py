"""
Integration test: PUT /teacher/portfolio/intro → GET /teacher/portfolio/sections
round-trip persistence.

Covers:
- successful save returns {success: True, intro: <text>}
- subsequent GET /sections reflects saved intro.text
- non-teacher caller receives 403
- empty/whitespace payload saves as empty string (strip behaviour)
- backend hard-fails (500) when gd_upsert raises (mocked path)
"""
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from server import app
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _token(user_id: str, role: str, tenant_id: str) -> str:
    return create_access_token({"sub": user_id, "role": role, "tenant_id": tenant_id})


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _mk_school(school_id: str) -> None:
    await gd_insert(db.session, "schools", {
        "id": school_id,
        "name": f"School-{school_id[:6]}",
        "code": f"S{school_id[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })


async def _mk_user(role: str, tenant_id: str) -> dict:
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": role,
        "tenant_id": tenant_id,
        "email": f"{uid}@test.invalid",
        "full_name": f"{role} user",
        "is_active": True,
        "password_hash": "x",
    }
    await gd_insert(db.session, "users", user)
    return user


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def http():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api") as c:
        yield c


@pytest_asyncio.fixture
async def teacher_ctx():
    tid = str(uuid.uuid4())
    await _mk_school(tid)
    user = await _mk_user("teacher", tid)
    token = _token(user["id"], "teacher", tid)
    return {"user": user, "token": token, "headers": _auth(token)}


@pytest_asyncio.fixture
async def parent_ctx():
    tid = str(uuid.uuid4())
    await _mk_school(tid)
    user = await _mk_user("parent", tid)
    token = _token(user["id"], "parent", tid)
    return {"user": user, "token": token, "headers": _auth(token)}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPortfolioIntroPersistence:

    @pytest.mark.asyncio
    async def test_save_intro_returns_success_and_intro_text(self, http, teacher_ctx):
        """PUT /teacher/portfolio/intro returns {success: true, intro: <text>}."""
        intro = "مقدمة تجريبية للاختبار"
        res = await http.put(
            "/teacher/portfolio/intro",
            json={"text": intro},
            headers=teacher_ctx["headers"],
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body.get("success") is True, f"Expected success=True, got: {body}"
        assert body.get("intro") == intro, (
            f"Returned intro '{body.get('intro')}' does not match sent '{intro}'"
        )

    @pytest.mark.asyncio
    async def test_save_intro_persists_in_sections(self, http, teacher_ctx):
        """After PUT, GET /teacher/portfolio/sections reflects the saved intro.text."""
        intro = f"مقدمة مخصصة {uuid.uuid4().hex[:8]}"

        put_res = await http.put(
            "/teacher/portfolio/intro",
            json={"text": intro},
            headers=teacher_ctx["headers"],
        )
        assert put_res.status_code == 200, put_res.text
        assert put_res.json().get("success") is True

        get_res = await http.get(
            "/teacher/portfolio/sections",
            headers=teacher_ctx["headers"],
        )
        assert get_res.status_code == 200, get_res.text
        sections = get_res.json()
        saved_text = (sections.get("intro") or {}).get("text", "__missing__")
        assert saved_text == intro, (
            f"GET /sections intro.text='{saved_text}' does not match saved '{intro}'"
        )

    @pytest.mark.asyncio
    async def test_update_intro_overwrites_previous(self, http, teacher_ctx):
        """A second PUT overwrites the first; GET reflects the latest value."""
        first = "المقدمة الأولى"
        second = "المقدمة المحدّثة"

        for text in (first, second):
            res = await http.put(
                "/teacher/portfolio/intro",
                json={"text": text},
                headers=teacher_ctx["headers"],
            )
            assert res.status_code == 200, res.text

        get_res = await http.get(
            "/teacher/portfolio/sections",
            headers=teacher_ctx["headers"],
        )
        assert get_res.status_code == 200, get_res.text
        saved = (get_res.json().get("intro") or {}).get("text")
        assert saved == second, (
            f"Expected latest intro '{second}', but GET returned '{saved}'"
        )

    @pytest.mark.asyncio
    async def test_whitespace_intro_saved_as_empty(self, http, teacher_ctx):
        """Whitespace-only text is stripped to '' before storage."""
        res = await http.put(
            "/teacher/portfolio/intro",
            json={"text": "   \n\t  "},
            headers=teacher_ctx["headers"],
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body.get("intro") == "", (
            f"Expected empty string after strip, got: '{body.get('intro')}'"
        )

    @pytest.mark.asyncio
    async def test_non_teacher_role_is_rejected(self, http, parent_ctx):
        """Callers who are not teachers receive 403."""
        res = await http.put(
            "/teacher/portfolio/intro",
            json={"text": "يجب أن يُرفض هذا"},
            headers=parent_ctx["headers"],
        )
        assert res.status_code == 403, (
            f"Expected 403 for parent caller, got {res.status_code}: {res.text}"
        )

    @pytest.mark.asyncio
    async def test_unauthenticated_request_rejected(self, http):
        """Request without a bearer token receives 401/403."""
        res = await http.put("/teacher/portfolio/intro", json={"text": "test"})
        assert res.status_code in (401, 403), (
            f"Expected 401/403 for unauthenticated, got {res.status_code}"
        )

    @pytest.mark.asyncio
    async def test_storage_exception_returns_500_arabic_detail(self, http, teacher_ctx):
        """If _save_meta raises, route returns 500 with Arabic detail (no raw exception)."""
        intro = "مقدمة بها خطأ في الحفظ"
        with patch(
            "routes.portfolio_routes_mod._save_meta",
            new=AsyncMock(side_effect=RuntimeError("db gone")),
        ):
            res = await http.put(
                "/teacher/portfolio/intro",
                json={"text": intro},
                headers=teacher_ctx["headers"],
            )
        assert res.status_code == 500, f"Expected 500 on storage error, got {res.status_code}"
        body = res.json()
        # Custom error handler wraps into {"success": false, "error": {"code": ..., "message": ...}}
        error_msg = (body.get("error") or {}).get("message", "")
        assert "db gone" not in error_msg, "Raw exception must not be exposed to client"
        assert error_msg, "error.message should contain an Arabic error description"
