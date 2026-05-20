"""Task #473 — Audit of role_dashboards_mod.py.

Pins two contracts that close the failure mode that produced Task #470
(an unbound `pwd_context` reference shipped to production):

  1. Every handler in `backend/routes/role_dashboards_mod.py` resolves
     all of its referenced names — `pyflakes` reports zero undefined
     names. (Unused-import warnings are tolerated; undefined names are
     not.)

  2. The catch-all router never re-imports the credential / session
     primitives (`hash_password`, `verify_password`, `create_access_token`,
     `JWT_SECRET`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE`, `security`).
     Those primitives belong in `auth_routes_mod.py` /
     `user_routes_mod.py`, where the canonical MFA, audit, and
     session-revocation side-effects are enforced. If a future change
     re-introduces one of them here, the next reviewer is forced to
     justify it instead of silently shipping another half-wired
     password / role / credential surface.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest


_MODULE_PATH = (
    Path(__file__).resolve().parent.parent / "routes" / "role_dashboards_mod.py"
)


_FORBIDDEN_CREDENTIAL_NAMES = {
    "hash_password",
    "verify_password",
    "create_access_token",
    "JWT_SECRET",
    "JWT_ALGORITHM",
    "ACCESS_TOKEN_EXPIRE",
    "security",
}


def _imported_names(module_path: Path) -> set[str]:
    tree = ast.parse(module_path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
    return names


def test_no_undefined_names_in_role_dashboards_mod():
    """`pyflakes` must report zero undefined-name errors (F821-style).

    Unused-import warnings are tolerated — they are noise. An undefined
    name is the exact bug class (`NameError: pwd_context`) that
    Task #470 had to hot-fix in production.
    """
    try:
        out = subprocess.run(
            [sys.executable, "-m", "pyflakes", str(_MODULE_PATH)],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        pytest.skip("pyflakes not installed in this environment")
    if "No module named pyflakes" in (out.stderr or ""):
        pytest.skip("pyflakes not installed in this environment")

    bad = [
        line
        for line in (out.stdout or "").splitlines()
        if "undefined name" in line
    ]
    assert not bad, "pyflakes reported undefined names:\n" + "\n".join(bad)


def test_role_dashboards_does_not_import_credential_primitives():
    """The catch-all router must not pull in the credential / session
    helpers — see the module-level Task #473 comment for the rationale."""
    imported = _imported_names(_MODULE_PATH)
    leaked = imported & _FORBIDDEN_CREDENTIAL_NAMES
    assert not leaked, (
        "role_dashboards_mod.py re-imported credential primitives: "
        f"{sorted(leaked)}. Move any password / role-flip / "
        "account-state / credential-mint handler to auth_routes_mod.py "
        "or user_routes_mod.py."
    )


def test_role_dashboards_has_no_legacy_password_route():
    """No handler in this module may be mounted on a `/password` path —
    the canonical password change lives at `/auth/change-password`."""
    tree = ast.parse(_MODULE_PATH.read_text())
    bad: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for deco in node.decorator_list:
            if not isinstance(deco, ast.Call):
                continue
            # decorator like @router.post("/x/password")
            if not (
                isinstance(deco.func, ast.Attribute)
                and isinstance(deco.func.value, ast.Name)
                and deco.func.value.id == "router"
            ):
                continue
            if not deco.args:
                continue
            arg = deco.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if "/password" in arg.value or arg.value.endswith("password"):
                    bad.append(f"{node.name} -> {arg.value}")
    assert not bad, (
        "role_dashboards_mod.py exposes a password route — these belong "
        "in auth_routes_mod.py: " + ", ".join(bad)
    )
