"""Focused auth contract tests that never connect to or write to a database.

The backend integration suite has useful end-to-end auth coverage, but its
autouse database fixture seeds temporary rows for most cases.  These tests
exercise the login and bearer-session decision points with the persistence,
audit, MFA-factor, and workspace calls mocked out.  They are intentionally
kept outside ``backend/tests`` so the backend database fixture is not loaded.
"""
from __future__ import annotations

import importlib
import os
import sys
from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi import Request
from fastapi.background import BackgroundTasks
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials


# Backend modules are not installed as a package in the workspace.  Do this
# before importing dependencies, whose import creates an engine but does not
# open a connection.
_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..", "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

import dependencies  # noqa: E402
from dependencies import UserRole, create_access_token  # noqa: E402
from shared_models import UserLogin  # noqa: E402
from src.modules.auth.controllers import auth_routes_mod as auth_routes  # noqa: E402


pytestmark = pytest.mark.asyncio

_TEST_EMAIL = "mocked-auth@example.com"
_TEST_PASSWORD = "Correct!123"


def _request(path: str = "/api/auth/login") -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "path": path,
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 8000),
            "server": ("test", 80),
        }
    )


def _user(role: str, *, active: bool = True) -> dict:
    uid = f"mock-{role}"
    return {
        "id": uid,
        "_id": uid,
        "email": _TEST_EMAIL,
        "full_name": f"Mock {role}",
        "role": role,
        "tenant_id": "mock-school",
        "is_active": active,
        "password_hash": "not-used-by-mock",
        "created_at": "2026-01-01T00:00:00+00:00",
        # These IDs prevent get_current_user's optional legacy auto-link
        # lookups from being reached in bearer-session tests.
        "teacher_id": "mock-teacher" if role == UserRole.TEACHER.value else None,
        "parent_id": "mock-parent" if role == UserRole.PARENT.value else None,
    }


@pytest.fixture
def mocked_login_dependencies(monkeypatch):
    """Replace every persistence/audit side effect used by ``login``."""
    lifecycle = importlib.import_module(
        "src.modules.independent_teacher.controllers."
        "independent_teacher_workspace_lifecycle_routes"
    )
    sql_utils = importlib.import_module("engines.sql_utils")
    rate_limiter = importlib.import_module("src.core.middleware.rate_limiter")

    monkeypatch.setattr(auth_routes, "_find_user_by_email_ci", AsyncMock())
    monkeypatch.setattr(auth_routes, "verify_password", lambda *_args: True)
    monkeypatch.setattr(auth_routes, "gd_find", AsyncMock(return_value=[]))
    monkeypatch.setattr(auth_routes, "gd_find_one", AsyncMock(return_value=None))
    monkeypatch.setattr(sql_utils, "gd_find", AsyncMock(return_value=[]))
    # Login's per-account limiter normally uses the shared Postgres-backed
    # store.  Keep this test entirely persistence-free as well.
    monkeypatch.setattr(
        rate_limiter.rate_store,
        "is_rate_limited",
        AsyncMock(return_value=(False, 9, 0)),
    )
    monkeypatch.setattr(auth_routes, "_record_session_from_token", AsyncMock())
    monkeypatch.setattr(
        auth_routes.audit_engine, "log_auth_event", AsyncMock()
    )
    monkeypatch.setattr(
        auth_routes, "attach_image_access_cookie", lambda *_args: None
    )
    monkeypatch.setattr(auth_routes, "signed_image_url", lambda *_args: None)
    monkeypatch.setattr(
        lifecycle, "maybe_flip_pending_hard_delete", AsyncMock(return_value=False)
    )
    monkeypatch.setattr(
        lifecycle, "fetch_workspace_lifecycle_for_user", AsyncMock(return_value=None)
    )
    return lifecycle


@pytest.mark.parametrize(
    "role",
    [
        UserRole.TEACHER.value,
        UserRole.INDEPENDENT_TEACHER.value,
        UserRole.SCHOOL_PRINCIPAL.value,
        UserRole.PLATFORM_ADMIN.value,
        UserRole.PARENT.value,
    ],
)
async def test_login_success_for_representative_roles(
    monkeypatch, mocked_login_dependencies, role
):
    """A valid password issues a session for each supported representative role."""
    user = _user(role)
    finder = AsyncMock(return_value=user)
    session_recorder = auth_routes._record_session_from_token
    monkeypatch.setattr(auth_routes, "_find_user_by_email_ci", finder)

    result = await auth_routes.login(
        UserLogin(email=_TEST_EMAIL, password=_TEST_PASSWORD),
        _request(),
        BackgroundTasks(),
        Response(),
    )

    assert result.access_token
    assert result.refresh_token
    assert result.user is not None
    assert result.user.role == UserRole(role)
    assert result.user.email == _TEST_EMAIL
    finder.assert_awaited_once_with(_TEST_EMAIL)
    session_recorder.assert_awaited_once()
    assert session_recorder.await_args.args[2] == user["id"]
    # No email provider is involved in this password-login path.
    assert not result.mfa_required


@pytest.mark.parametrize(
    ("case", "active", "password_ok", "expected_detail"),
    [
        ("unknown email", True, True, "بيانات الدخول غير صحيحة"),
        ("wrong password", True, False, "بيانات الدخول غير صحيحة"),
        ("inactive account", False, True, "الحساب معطل"),
    ],
)
async def test_login_rejects_unknown_wrong_password_and_inactive(
    monkeypatch,
    mocked_login_dependencies,
    case,
    active,
    password_ok,
    expected_detail,
):
    """Credential and account-state failures never issue access or refresh tokens."""
    user = _user(UserRole.TEACHER.value, active=active)
    monkeypatch.setattr(
        auth_routes,
        "_find_user_by_email_ci",
        AsyncMock(return_value=None if case == "unknown email" else user),
    )
    monkeypatch.setattr(auth_routes, "verify_password", lambda *_args: password_ok)

    with pytest.raises(HTTPException) as exc:
        await auth_routes.login(
            UserLogin(email=_TEST_EMAIL, password=_TEST_PASSWORD),
            _request(),
            BackgroundTasks(),
            Response(),
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == expected_detail
    auth_routes._record_session_from_token.assert_not_awaited()


async def test_student_login_is_blocked_before_token_issuance(
    monkeypatch, mocked_login_dependencies
):
    """The platform student-login block runs before MFA or token creation."""
    user = _user(UserRole.STUDENT.value)
    monkeypatch.setattr(
        auth_routes, "_find_user_by_email_ci", AsyncMock(return_value=user)
    )

    with pytest.raises(HTTPException) as exc:
        await auth_routes.login(
            UserLogin(email=_TEST_EMAIL, password=_TEST_PASSWORD),
            _request(),
            BackgroundTasks(),
            Response(),
        )

    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "STUDENT_LOGIN_DISABLED"
    assert exc.value.detail["message_ar"]
    auth_routes._record_session_from_token.assert_not_awaited()


def _credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.fixture
def mocked_session_dependencies(monkeypatch):
    """Mock both DB lookup locations used by ``get_current_user``."""
    sql_utils = importlib.import_module("engines.sql_utils")
    revoked_lookup = AsyncMock(return_value=None)
    user_lookup = AsyncMock()
    monkeypatch.setattr(sql_utils, "gd_find_one", revoked_lookup)
    monkeypatch.setattr(dependencies, "gd_find_one", user_lookup)
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "true")
    return user_lookup


async def test_me_accepts_teacher_and_parent_access_sessions(
    mocked_session_dependencies,
):
    """Valid non-expired bearer sessions resolve to their persisted role."""
    for role in (UserRole.TEACHER.value, UserRole.PARENT.value):
        user = _user(role)
        mocked_session_dependencies.return_value = user
        token = create_access_token(
            {"sub": user["id"], "role": role, "tenant_id": user["tenant_id"]}
        )

        resolved = await dependencies.get_current_user(
            _credentials(token), _request("/api/auth/me")
        )

        assert resolved["id"] == user["id"]
        assert resolved["role"] == role


async def test_me_rejects_expired_access_session(mocked_session_dependencies):
    """An expired access token is rejected without a user lookup."""
    token = create_access_token(
        {"sub": "expired-user", "role": UserRole.TEACHER.value},
        expires_delta=timedelta(seconds=-1),
    )

    with pytest.raises(HTTPException) as exc:
        await dependencies.get_current_user(
            _credentials(token), _request("/api/auth/me")
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == "Token expired"
    mocked_session_dependencies.assert_not_awaited()


async def test_me_rejects_inactive_session(mocked_session_dependencies):
    """A valid bearer for an inactive account cannot access /auth/me."""
    user = _user(UserRole.TEACHER.value, active=False)
    mocked_session_dependencies.return_value = user
    token = create_access_token({"sub": user["id"], "role": user["role"]})

    with pytest.raises(HTTPException) as exc:
        await dependencies.get_current_user(
            _credentials(token), _request("/api/auth/me")
        )

    assert exc.value.status_code == 401
    assert exc.value.detail == "Account is deactivated"


async def test_me_rejects_student_session_even_with_valid_access_token(
    mocked_session_dependencies,
):
    """Already-issued student access tokens are blocked defense-in-depth."""
    user = _user(UserRole.STUDENT.value)
    mocked_session_dependencies.return_value = user
    token = create_access_token({"sub": user["id"], "role": user["role"]})

    with pytest.raises(HTTPException) as exc:
        await dependencies.get_current_user(
            _credentials(token), _request("/api/auth/me")
        )

    assert exc.value.status_code == 401
    assert "الطالب" in exc.value.detail


async def test_me_db_failure_does_not_fail_open(mocked_session_dependencies):
    """A persistence failure aborts auth resolution instead of authenticating."""
    mocked_session_dependencies.side_effect = RuntimeError("database unavailable")
    token = create_access_token(
        {"sub": "db-failure-user", "role": UserRole.TEACHER.value}
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        await dependencies.get_current_user(
            _credentials(token), _request("/api/auth/me")
        )