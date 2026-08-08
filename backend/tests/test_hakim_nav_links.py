"""Regression: Hakim chat nav links must be role-aware and real.

The old prompt gave ONE role-agnostic nav block with school-leadership
paths to every non-parent role, and several of those paths
(/school/assessments, /school/dashboard, /school/communication,
/school/ai-insights, /admin/reports) were never registered routes at all
— the frontend catch-all bounced users to the homepage.

These tests assert:
1. every path Hakim may emit exists in frontend/src/routes/appRoutes.js
2. teacher links stay in the teacher namespace
3. leadership gets canonical /principal paths and NO assessments link
   (module hidden)
4. unknown roles get a "no links" instruction rather than guessed paths
"""
import re
from pathlib import Path

import pytest

from routes.ai_routes_mod import _hakim_nav_links_for_role

APP_ROUTES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "routes" / "appRoutes.js"


def _registered_paths():
    src = APP_ROUTES.read_text(encoding="utf-8")
    return set(re.findall(r'Route path="([^"]+)"', src))


def _role_constants(src: str):
    """Resolve the role-array constants defined in appRoutes.js,
    including ...SPREADS of earlier constants."""
    consts = {}
    for name, body in re.findall(r"const (\w+_ROLES) = \[([^\]]*)\];", src):
        roles = set(re.findall(r"'([\w-]+)'", body))
        for spread in re.findall(r"\.\.\.(\w+)", body):
            roles |= consts.get(spread, set())
        consts[name] = roles
    return consts


def _route_allowed_roles():
    """Map each registered path → union of allowedRoles across its
    <ProtectedRoute> declarations. Paths without a ProtectedRoute
    (public/redirect routes) are omitted."""
    src = APP_ROUTES.read_text(encoding="utf-8")
    consts = _role_constants(src)
    allowed = {}
    pattern = re.compile(
        r'Route path="([^"]+)" element=\{\s*<ProtectedRoute allowedRoles=\{([^}]+)\}',
        re.DOTALL,
    )
    for path, expr in pattern.findall(src):
        roles = set(re.findall(r"'([\w-]+)'", expr))
        for name in re.findall(r"\b(\w+_ROLES)\b", expr):
            roles |= consts.get(name, set())
        allowed.setdefault(path, set()).update(roles)
    return allowed


def _emitted_paths(role: str):
    block = _hakim_nav_links_for_role(role)
    return re.findall(r'(/[\w/-]+)', block)


ALL_MAPPED_ROLES = [
    "teacher", "independent_teacher",
    "school_principal", "school_admin", "school_sub_admin",
    "platform_admin", "platform_sub_admin", "platform_operations_manager",
]


@pytest.mark.parametrize("role", ALL_MAPPED_ROLES)
def test_every_emitted_path_is_a_registered_route(role):
    registered = _registered_paths()
    paths = _emitted_paths(role)
    assert paths, f"role {role} should emit at least one link"
    missing = [p for p in paths if p not in registered]
    assert not missing, f"role {role} emits unregistered routes {missing} — these hit the catch-all and land on the homepage"


@pytest.mark.parametrize("role", ALL_MAPPED_ROLES)
def test_every_emitted_path_is_authorized_for_the_role(role):
    """A link the role cannot open makes ProtectedRoute bounce the user
    to their own dashboard — same broken-navigation class as a dead
    route. Every emitted path must list the role in allowedRoles."""
    allowed = _route_allowed_roles()
    for p in _emitted_paths(role):
        assert p in allowed, f"{p} has no ProtectedRoute declaration"
        assert role in allowed[p], (
            f"role {role} is not in allowedRoles for {p}: {sorted(allowed[p])}"
        )


def test_teacher_links_stay_in_teacher_namespace():
    for p in _emitted_paths("teacher"):
        assert p.startswith("/teacher/") or p == "/notifications", p


def test_teacher_assessments_link_is_teacher_scoped():
    block = _hakim_nav_links_for_role("teacher")
    assert "الاختبارات والتقييمات: /teacher/assessments" in block
    assert "/school/assessments" not in block


def test_leadership_has_no_assessments_link():
    """Assessments module is hidden for leadership (/admin/assessments
    redirects away; /school/assessments never existed)."""
    for role in ("school_principal", "school_admin", "school_sub_admin"):
        block = _hakim_nav_links_for_role(role)
        assert "assessments" not in block, role
        assert "/principal/schedule" in block, role


def test_leadership_uses_canonical_principal_namespace():
    for p in _emitted_paths("school_principal"):
        assert p.startswith("/principal") or p == "/notifications", p


def test_unknown_role_gets_no_links_instruction():
    block = _hakim_nav_links_for_role("student")
    assert "لا تُدرج أي روابط" in block
    assert not re.findall(r'\(/[\w/-]+\)', block)


def test_dead_routes_never_emitted():
    dead = {"/school/assessments", "/school/dashboard", "/school/communication",
            "/school/ai-insights", "/admin/reports", "/admin/behaviour"}
    for role in ALL_MAPPED_ROLES:
        emitted = set(_emitted_paths(role))
        assert not (emitted & dead), (role, emitted & dead)
