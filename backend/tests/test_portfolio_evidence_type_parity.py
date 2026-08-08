"""Regression: the portfolio evidence-type vocabulary must not drift between
backend and frontend.

The file library («مكتبة الملفات») filters client-side on `evidence_type`, and
its dropdown is built from the frontend registry. When the backend gained the
v2 vocabulary (curriculum_distribution_plan, oral_assessment, …) but the
frontend filter kept offering the legacy 25-type list, documents of the new
types became unfilterable: no option in the dropdown could ever match them,
and the teacher saw an empty library.

These tests keep frontend/src/pages/TeacherModule/portfolioEvidenceTypes.js in
lockstep with ALL_EVIDENCE_TYPES / EVIDENCE_SUBSECTIONS_V2 so a type added on
one side cannot silently go missing on the other.
"""
import re
from pathlib import Path

from engines.portfolio_evidence_engine import (
    ALL_EVIDENCE_TYPES,
    EVIDENCE_SUBSECTIONS_V2,
)

REGISTRY = (
    Path(__file__).resolve().parents[2]
    / "frontend" / "src" / "pages" / "TeacherModule" / "portfolioEvidenceTypes.js"
)


def _registry_src() -> str:
    return REGISTRY.read_text(encoding="utf-8")


def _fe_groups() -> dict:
    """Parse EVIDENCE_TYPE_GROUPS → {group key: [types]}."""
    src = _registry_src()
    block = src[src.index("export const EVIDENCE_TYPE_GROUPS"):]
    block = block[: block.index("\n];")]
    groups = {}
    for key, types in re.findall(
        r"key:\s*'([\w]+)',\s*title:[^\n]*\n\s*types:\s*\[([^\]]*)\]", block
    ):
        groups[key] = re.findall(r"'([\w]+)'", types)
    return groups


def _fe_labelled_types() -> set:
    """Types that resolve to a real label (v2 Arabic map or legacy i18n key)."""
    src = _registry_src()
    labelled = set()
    for const in ("TYPE_LABEL_AR", "LEGACY_TYPE_LABEL_KEYS"):
        block = src[src.index(f"export const {const} = {{"):]
        block = block[: block.index("\n};")]
        labelled |= set(re.findall(r"^\s*(\w+):", block, flags=re.MULTILINE))
    return labelled


def test_frontend_registry_covers_every_backend_type():
    fe_types = {t for types in _fe_groups().values() for t in types}
    missing = set(ALL_EVIDENCE_TYPES) - fe_types
    assert not missing, (
        "evidence types the backend stores but the file-library filter cannot "
        f"offer (documents of these types are unfilterable): {sorted(missing)}"
    )


def test_frontend_registry_invents_no_types():
    fe_types = {t for types in _fe_groups().values() for t in types}
    unknown = fe_types - set(ALL_EVIDENCE_TYPES)
    assert not unknown, (
        f"filter offers types the backend rejects on save: {sorted(unknown)}"
    )


def test_frontend_registry_has_no_duplicate_types():
    flat = [t for types in _fe_groups().values() for t in types]
    assert len(flat) == len(set(flat)), "a type is listed in two groups"


def test_v2_subsections_match_backend():
    fe_groups = _fe_groups()
    for key, types in EVIDENCE_SUBSECTIONS_V2.items():
        assert key in fe_groups, f"v2 sub-section {key} missing from the frontend"
        assert fe_groups[key] == list(types), (
            f"v2 sub-section {key} differs: backend={list(types)} frontend={fe_groups[key]}"
        )


def test_every_type_has_a_label():
    fe_types = {t for types in _fe_groups().values() for t in types}
    unlabelled = fe_types - _fe_labelled_types()
    assert not unlabelled, (
        "types that would render as the generic «مستند تعليمي» in both the "
        f"dropdown and the cards: {sorted(unlabelled)}"
    )
