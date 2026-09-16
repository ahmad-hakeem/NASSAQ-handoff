"""Regression guards for the export engine's import-time work."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_dependencies_import_does_not_load_export_only_libraries():
    """The common dependency graph must not initialize export libraries."""
    probe = (
        "import sys; import dependencies; "
        "print('\\n'.join(name for name in "
        "('pandas', 'reportlab', 'arabic_reshaper', 'bidi') "
        "if name in sys.modules))"
    )
    env = os.environ.copy()
    env["JWT_SECRET_KEY"] = "startup-regression-test-only"

    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=BACKEND_DIR,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == ""