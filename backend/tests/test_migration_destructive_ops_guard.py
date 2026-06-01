"""
DEPLOYMENT SAFETY — destructive-migration guard.

Scans every Alembic migration's ``upgrade()`` body for DATA-DESTRUCTIVE
operations (dropping a table/column, or executing raw DROP TABLE / TRUNCATE /
DELETE FROM SQL). Any such migration MUST be explicitly acknowledged in
``ALLOWED_DESTRUCTIVE`` below with a human-written reason.

This is the enforcement the project's docs/config previously only described:
``backend/config.py`` defines ``DESTRUCTIVE_MIGRATION_OPS`` and the policy
"destructive migrations are BLOCKED in production", but nothing checked it.
A new destructive migration now fails this test until a maintainer consciously
allowlists it — that allowlist edit IS the sign-off.

Index/constraint drops are intentionally NOT flagged: they are schema-shape
changes, not data loss.

Run: cd backend && pytest tests/test_migration_destructive_ops_guard.py -v
"""
import ast
import glob
import os

# revision id -> reason it is allowed to destroy column/table data.
# Add an entry here ONLY when the data loss is intentional and reviewed.
ALLOWED_DESTRUCTIVE = {
    "a1b2c3d4e5f6": "Consolidates product_issues.type into a single field; legacy column removed.",
    "d1e2f3a4b5c6": "Cleanup of redundant denormalized counters and unused tenant_id columns.",
    "f3a4b5c6d7e8": "Drops extraneous columns added in error by a prior migration.",
    "h1i2j3k4l5m6": "Data migration: after copying events/system_settings into dedicated tables, removes the now-migrated rows from generic_documents.",
    "l1m2n3o4p5q6": "Removes orphaned approval_events rows (request_id with no matching request) before adding the FK constraint.",
}

VERSIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "alembic", "versions")

_DESTRUCTIVE_CALLS = {"drop_table", "drop_column"}
_DESTRUCTIVE_SQL = ("DROP TABLE", "TRUNCATE", "DELETE FROM", "DROP COLUMN")


def _revision_id(path: str) -> str:
    """Read the actual ``revision = "..."`` assignment from the file."""
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == "revision":
                    if isinstance(node.value, ast.Constant):
                        return str(node.value.value)
    # Fallback to filename prefix.
    return os.path.basename(path).split("_")[0]


def _string_literals(node: ast.AST):
    """Yield string literals reachable from a call argument, descending one
    level into wrapper calls like ``sa.text("...")`` / ``text("...")``."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node.value
    elif isinstance(node, ast.Call):
        for a in node.args:
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                yield a.value


def _destructive_ops_in_upgrade(path: str) -> list:
    tree = ast.parse(open(path, encoding="utf-8").read())
    hits: list = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "upgrade":
            for n in ast.walk(node):
                if isinstance(n, ast.Call):
                    name = getattr(n.func, "attr", None)
                    if name in _DESTRUCTIVE_CALLS:
                        hits.append(name)
                    elif name == "execute":
                        for arg in n.args:
                            for literal in _string_literals(arg):
                                up = literal.upper()
                                for kw in _DESTRUCTIVE_SQL:
                                    if kw in up:
                                        hits.append(f"execute:{kw}")
    return hits


def test_destructive_migrations_are_allowlisted():
    offenders = {}
    seen_revisions = set()
    for path in sorted(glob.glob(os.path.join(VERSIONS_DIR, "*.py"))):
        rev = _revision_id(path)
        seen_revisions.add(rev)
        hits = _destructive_ops_in_upgrade(path)
        if hits and rev not in ALLOWED_DESTRUCTIVE:
            offenders[os.path.basename(path)] = hits

    assert not offenders, (
        "Destructive migration(s) found in upgrade() that are not allowlisted. "
        "If the data loss is intentional and reviewed, add the revision id to "
        "ALLOWED_DESTRUCTIVE in this test with a reason. Offenders: " + repr(offenders)
    )

    # Keep the allowlist honest: every allowlisted revision must still exist
    # and must still actually contain a destructive op (otherwise remove it).
    stale = sorted(r for r in ALLOWED_DESTRUCTIVE if r not in seen_revisions)
    assert not stale, f"ALLOWED_DESTRUCTIVE has stale revisions no longer present: {stale}"


def test_allowlisted_revisions_still_destructive():
    by_rev = {}
    for path in sorted(glob.glob(os.path.join(VERSIONS_DIR, "*.py"))):
        by_rev[_revision_id(path)] = path
    no_longer = []
    for rev in ALLOWED_DESTRUCTIVE:
        path = by_rev.get(rev)
        if path and not _destructive_ops_in_upgrade(path):
            no_longer.append(rev)
    assert not no_longer, (
        "These revisions are allowlisted but no longer perform destructive ops "
        f"— remove them from ALLOWED_DESTRUCTIVE: {no_longer}"
    )
