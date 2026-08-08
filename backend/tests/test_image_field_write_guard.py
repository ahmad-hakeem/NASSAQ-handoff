"""Every write path for users.avatar_url / schools.logo_url must be bounded.

Three routes were found bypassing the avatar/logo normaliser AFTER it was
added — allow-list copy loops, profile handlers accepting ``avatar_url``
straight from the body, and the IT bootstrap insert — because nothing fails
when a new route forgets to call it.

Two independent layers close that hole:

1. Static discovery (AST): every function in the backend source that writes
   to ``users`` or ``schools`` via the ``gd_*`` helpers AND touches the image
   field must also call one of the normalisers. A new unguarded write path
   fails this test the moment it is committed, even if no HTTP test drives it.

2. Persistence chokepoint: ``engines.sql_utils`` refuses to store a ``data:``
   URI larger than any normalised output can ever be
   (``MAX_STORED_IMAGE_CHARS``) on those two columns, so a path that somehow
   evades the static scan (e.g. copying an arbitrary request dict) still
   cannot persist an oversized image at runtime.
"""

import ast
from pathlib import Path

import pytest

from engines.sql_utils import gd_insert, gd_update_one, gd_update_many, gd_upsert
from utils.avatar_image import (
    MAX_STORED_IMAGE_CHARS,
    OversizedImageWriteError,
    assert_stored_image_bounded,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]

# Scan the entire backend source tree, minus test code and migrations.
_EXCLUDED_PARTS = {"tests", "alembic", "__pycache__", "node_modules", ".venv", "venv"}

_GUARDED = {"users": "avatar_url", "schools": "logo_url"}
# Direct ORM construction bypasses the gd_* helpers entirely (the
# IdentityEngine.create_user path); constructor keywords count as writes.
_ORM_CLASSES = {"User": "users", "School": "schools"}
_FIELD_TO_TABLE = {"avatar_url": "users", "logo_url": "schools"}
_IMAGE_FIELDS = set(_GUARDED.values())
_WRITE_FUNCS = {"gd_insert", "gd_insert_many", "gd_update_one", "gd_update_many", "gd_upsert"}
_NORMALIZERS = {
    "normalize_image_field_or_400",
    "normalize_avatar_data_url_async",
    "normalize_avatar_data_url",
    "_normalized_avatar",
}
# Reads: mentioning the field inside .get(...)/.pop(...) is not a write.
_SAFE_CALL_METHODS = {"get", "pop"}

# Reviewed exceptions: (relative file, function name) -> reason.
# Keep this EMPTY unless a flagged site has been manually verified to bound
# the value some other way; document the reason when adding one.
_ALLOWLIST: dict = {}


def _iter_source_files():
    for path in sorted(BACKEND_DIR.rglob("*.py")):
        if _EXCLUDED_PARTS.isdisjoint(path.relative_to(BACKEND_DIR).parts):
            yield path


def _call_name(node: ast.Call) -> str:
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return ""


def _collect_safe_nodes(func: ast.AST) -> set:
    """ids of Constant nodes that are provably NOT an unnormalised write.

    - dict literal key whose value is the constant ``None``
    - keyword argument ``avatar_url=None`` / ``logo_url=None``
    - arguments to ``.get(...)`` / ``.pop(...)`` (reads)
    """
    safe = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if (
                    isinstance(k, ast.Constant)
                    and k.value in _IMAGE_FIELDS
                    and isinstance(v, ast.Constant)
                    and v.value is None
                ):
                    safe.add(id(k))
        elif isinstance(node, ast.keyword):
            if (
                node.arg in _IMAGE_FIELDS
                and isinstance(node.value, ast.Constant)
                and node.value.value is None
            ):
                # keyword itself carries no Constant for the name; nothing to
                # mark — the field name never appears as a Constant here.
                pass
        elif isinstance(node, ast.Call) and _call_name(node) in _SAFE_CALL_METHODS:
            for arg in node.args:
                if isinstance(arg, ast.Constant) and arg.value in _IMAGE_FIELDS:
                    safe.add(id(arg))
    return safe


def _analyze_function(func: ast.AST):
    """Return (writes_guarded_tables, risky_field_ref, calls_normalizer)."""
    writes = set()
    calls_normalizer = False
    risky = False
    safe_nodes = _collect_safe_nodes(func)

    for node in ast.walk(func):
        # Skip nested function defs? No — a nested helper's writes belong to
        # the enclosing handler's context, so analysing them together is the
        # conservative (fail-closed) choice.
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name in _WRITE_FUNCS and len(node.args) >= 2:
                coll = node.args[1]
                if isinstance(coll, ast.Constant) and coll.value in _GUARDED:
                    writes.add(coll.value)
            if name in _ORM_CLASSES:
                # Direct model construction: User(avatar_url=...), School(logo_url=...).
                table = _ORM_CLASSES[name]
                for kw in node.keywords:
                    if kw.arg == _GUARDED[table] and not (
                        isinstance(kw.value, ast.Constant) and kw.value.value is None
                    ):
                        writes.add(table)
                        risky = True
            if name in _NORMALIZERS:
                calls_normalizer = True
        elif isinstance(node, (ast.Assign, ast.AugAssign)):
            # Attribute assignment on an ORM object: obj.avatar_url = value.
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Attribute) and t.attr in _FIELD_TO_TABLE:
                    value = getattr(node, "value", None)
                    if not (isinstance(value, ast.Constant) and value.value is None):
                        writes.add(_FIELD_TO_TABLE[t.attr])
                        risky = True
        if (
            isinstance(node, ast.Constant)
            and node.value in _IMAGE_FIELDS
            and id(node) not in safe_nodes
        ):
            risky = True

    return writes, risky, calls_normalizer


def test_every_write_path_for_image_columns_is_guarded():
    """Discovery: a route that writes users/schools and handles the image
    field without calling a normaliser fails here — including future ones."""
    offenders = []
    for path in _iter_source_files():
        rel = str(path.relative_to(BACKEND_DIR))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:  # pragma: no cover
            pytest.fail(f"unparseable source {rel}: {exc}")
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            writes, risky, normalized = _analyze_function(node)
            if not writes or not risky or normalized:
                continue
            # Only flag when the risky field actually matches a written table.
            if (rel, node.name) in _ALLOWLIST:
                continue
            offenders.append(f"{rel}:{node.lineno} {node.name} (writes {sorted(writes)})")

    assert not offenders, (
        "Write paths handle users.avatar_url / schools.logo_url without "
        "calling utils.avatar_image.normalize_image_field_or_400 (or add a "
        "reviewed entry to _ALLOWLIST with a reason):\n  "
        + "\n  ".join(offenders)
    )


def test_discovery_scan_actually_sees_the_known_write_sites():
    """Anti-vacuity: the scan must find the known guarded sites, or a rename
    of the helpers would silently make the discovery test prove nothing."""
    guarded_seen = 0
    for path in _iter_source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                writes, risky, normalized = _analyze_function(node)
                if writes and risky and normalized:
                    guarded_seen += 1
    # Known today: /users/me/avatar, /users/me/profile, admin user update,
    # PATCH+PUT /schools, IT workspace settings, IT bootstrap.
    assert guarded_seen >= 5, f"scan only saw {guarded_seen} guarded write sites"


# --------------------------------------------------------------------------
# Persistence chokepoint — the layer that catches paths the scan cannot see
# --------------------------------------------------------------------------

_OVERSIZED = "data:image/png;base64," + "A" * (MAX_STORED_IMAGE_CHARS + 1)


def test_bound_helper_rejects_oversized_and_passes_legit_values():
    with pytest.raises(OversizedImageWriteError):
        assert_stored_image_bounded("users", "avatar_url", _OVERSIZED)
    with pytest.raises(OversizedImageWriteError):
        assert_stored_image_bounded("schools", "logo_url", _OVERSIZED)
    # Normalised-sized data URIs, plain URLs, None: fine.
    assert_stored_image_bounded("users", "avatar_url", "data:image/webp;base64," + "A" * 20_000)
    assert_stored_image_bounded("users", "avatar_url", "https://cdn.example.com/a.png")
    assert_stored_image_bounded("users", "avatar_url", None)
    # Unguarded columns are untouched even with huge values.
    assert_stored_image_bounded("users", "bio", _OVERSIZED)
    assert_stored_image_bounded("classes", "logo_url", _OVERSIZED)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "op",
    [
        lambda s: gd_insert(s, "users", {"id": "x", "avatar_url": _OVERSIZED}),
        lambda s: gd_update_one(s, "users", {"id": "x"}, {"avatar_url": _OVERSIZED}),
        lambda s: gd_update_one(s, "users", {"id": "x"}, {"$set": {"avatar_url": _OVERSIZED}}),
        lambda s: gd_update_many(s, "users", {"id": "x"}, {"avatar_url": _OVERSIZED}),
        lambda s: gd_upsert(s, "schools", {"id": "x"}, {"logo_url": _OVERSIZED}),
        lambda s: gd_insert(s, "schools", {"id": "x", "logo_url": _OVERSIZED}),
    ],
)
async def test_persistence_layer_rejects_unnormalized_writes(op):
    """The guard fires BEFORE any session interaction, so no DB is needed:
    passing session=None proves the write was refused up front."""
    with pytest.raises(OversizedImageWriteError):
        await op(None)


def test_orm_model_rejects_unbounded_image_on_construction_and_assignment():
    """Direct ORM writes (the path that bypasses gd_* — e.g. engines that
    construct ``User(...)`` themselves) are stopped by column validators."""
    from pg_models import School, User

    with pytest.raises(OversizedImageWriteError):
        User(id="x", email="x@x", full_name="x", password_hash="h", role="teacher",
             avatar_url=_OVERSIZED)
    with pytest.raises(OversizedImageWriteError):
        School(id="x", name="x", code="x", logo_url=_OVERSIZED)

    u = User(id="x", email="x@x", full_name="x", password_hash="h", role="teacher")
    with pytest.raises(OversizedImageWriteError):
        u.avatar_url = _OVERSIZED
    u.avatar_url = "https://cdn.example.com/a.png"  # plain URL still fine

    s = School(id="x", name="x", code="x")
    with pytest.raises(OversizedImageWriteError):
        s.logo_url = _OVERSIZED
    s.logo_url = None


@pytest.mark.asyncio
async def test_identity_engine_create_user_bounds_the_avatar(monkeypatch):
    """IdentityEngine.create_user constructs User(...) directly; it must
    reject an oversized inline avatar before the row is built."""
    from engines.identity_engine import IdentityEngine
    from dependencies import UserRole

    engine = IdentityEngine.__new__(IdentityEngine)  # no DB needed: fails first

    class _Boom:
        def __getattr__(self, name):  # pragma: no cover - should not be reached
            raise AssertionError("DB touched before the avatar bound check")

    monkeypatch.setattr(IdentityEngine, "session", property(lambda self: _Boom()))
    with pytest.raises(ValueError):
        await engine.create_user(
            email="x@x", password_hash="h", full_name="x",
            primary_role=UserRole.TEACHER,
            avatar_url="data:image/png;base64," + "A" * (3 * 1024 * 1024),
        )
