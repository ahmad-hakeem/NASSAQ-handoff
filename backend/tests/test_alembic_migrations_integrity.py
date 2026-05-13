"""Guard rail for Alembic migration files.

Catches the two failure modes that have historically slipped past review:

1. Two migration files declaring the same ``revision = "..."`` id (Alembic
   silently picks one, leaving fresh databases missing columns).
2. The migration graph having more than one head (downgrades/upgrades become
   ambiguous and a `merge` revision is required).
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import pytest

_VERSIONS_DIR = Path(__file__).resolve().parent.parent / "alembic" / "versions"
_REVISION_RE = re.compile(
    r"""^revision(?:\s*:\s*[^=]+)?\s*=\s*['"]([^'"]+)['"]""",
    re.MULTILINE,
)


def _iter_revision_files():
    return sorted(p for p in _VERSIONS_DIR.glob("*.py") if not p.name.startswith("_"))


def test_no_duplicate_alembic_revision_ids() -> None:
    revisions: dict[str, list[str]] = defaultdict(list)
    for path in _iter_revision_files():
        match = _REVISION_RE.search(path.read_text(encoding="utf-8"))
        assert match, f"{path.name} has no top-level `revision = \"...\"` declaration"
        revisions[match.group(1)].append(path.name)

    duplicates = {rev: files for rev, files in revisions.items() if len(files) > 1}
    assert not duplicates, (
        "Duplicate Alembic revision ids detected — Alembic will silently pick one "
        f"and skip the others, leaving fresh databases inconsistent: {duplicates}"
    )


def test_alembic_graph_has_single_head() -> None:
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory
    except ImportError:  # pragma: no cover - alembic is a hard dep in this repo
        pytest.skip("alembic not installed")

    ini_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    cfg = Config(str(ini_path))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1, (
        "Alembic migration graph has multiple heads — add a merge revision "
        f"(`alembic merge -m '...' {' '.join(heads)}`). Heads: {heads}"
    )
