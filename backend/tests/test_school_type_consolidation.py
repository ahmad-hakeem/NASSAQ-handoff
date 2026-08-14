"""Tests for the School-Type domain consolidation.

The deprecated UI option "خاصة" (stored as ``"special"`` /
``"special_needs"``) was consolidated into the canonical "أهلية"
(stored as ``"private"``). These tests pin:

1. The pure ``normalize_school_type`` helper round-trips every alias
   to the canonical value and leaves unrelated values untouched
   (including IT workspace tenant types).
2. Every Pydantic write schema that exposes ``school_type`` (or its
   API alias ``type``) normalizes the deprecated value at the API
   boundary, so the deprecated string can never reach the database
   via a fresh request.
3. The Alembic data-only migration
   ``c4d5e6f7a8b9_consolidate_school_type_special_to_private`` is a
   plain idempotent ``UPDATE`` against the two deprecated values and
   leaves all other values (including independent-teacher tenant
   types) alone.
"""
from src.common.utils.school_type import normalize_school_type


def test_normalize_helper_maps_deprecated_aliases_to_private():
    assert normalize_school_type("special") == "private"
    assert normalize_school_type("special_needs") == "private"
    assert normalize_school_type("خاصة") == "private"
    # Whitespace is tolerated so a stray UI submission still normalizes.
    assert normalize_school_type("  special  ") == "private"


def test_normalize_helper_passes_canonical_values_through():
    for v in ("public", "private", "international"):
        assert normalize_school_type(v) == v


def test_normalize_helper_leaves_unrelated_tenant_types_untouched():
    # Independent-teacher tenant types live in the same column but
    # belong to a different domain — the migration and helper must
    # never touch them.
    for v in ("independent_teacher", "independent_teacher_workspace"):
        assert normalize_school_type(v) == v


def test_normalize_helper_returns_none_for_none():
    assert normalize_school_type(None) is None


def test_school_create_schema_normalizes_at_api_boundary():
    from src.modules.schools.dto.school_dto import SchoolCreate
    assert SchoolCreate(name="X", school_type="special").school_type == "private"
    assert SchoolCreate(name="X", school_type="special_needs").school_type == "private"
    assert SchoolCreate(name="X", school_type="public").school_type == "public"


def test_school_update_schema_normalizes_at_api_boundary():
    from src.modules.schools.dto.school_dto import SchoolUpdate
    assert SchoolUpdate(school_type="special").school_type == "private"
    assert SchoolUpdate(school_type="special_needs").school_type == "private"
    # Optional field stays optional.
    assert SchoolUpdate().school_type is None


def test_shared_school_create_schema_normalizes():
    from shared_models import SchoolCreate
    assert SchoolCreate(name="Y", school_type="special").school_type == "private"


def test_school_settings_info_update_schema_normalizes_type_alias():
    # The settings page submits the column under its API alias ``type``;
    # the validator on that field must normalize before the route
    # writes ``school_type = update_data["type"]`` (school_settings_mod.py).
    from src.modules.schools.controllers.school_settings_mod import SchoolInfoUpdate
    assert SchoolInfoUpdate(type="special").type == "private"
    assert SchoolInfoUpdate(type="special_needs").type == "private"
    assert SchoolInfoUpdate(type="private").type == "private"
    assert SchoolInfoUpdate().type is None


def test_registration_request_schema_normalizes():
    from src.modules.registration.dto.registration_dto import RegistrationRequestBase
    req = RegistrationRequestBase(
        school_name="Z",
        school_type="special",
        region="r",
        city="c",
        principal_name="n",
        principal_email="a@b.com",
        principal_phone="1",
    )
    assert req.school_type == "private"


def test_school_type_enum_no_longer_exposes_special_needs():
    # SPECIAL_NEEDS was the duplicate option backing "خاصة"; after
    # consolidation it must not be a member of the enum so new code
    # cannot reintroduce the deprecated stored value.
    from src.common.dto.foundation import SchoolType
    assert not hasattr(SchoolType, "SPECIAL_NEEDS")
    assert {m.value for m in SchoolType} == {"public", "private", "international"}


def test_consolidation_migration_is_a_targeted_update_to_private():
    # The migration is data-only: a single UPDATE over the two
    # deprecated alias values, scoped to the ``schools`` table, with
    # no DDL. Pin its shape so future edits can't silently widen the
    # blast radius (e.g. into independent-teacher rows).
    import os
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(
        here,
        "alembic",
        "versions",
        "c4d5e6f7a8b9_consolidate_school_type_special_to_private.py",
    )
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    assert "UPDATE schools" in src
    assert "school_type = 'private'" in src
    assert "'special'" in src and "'special_needs'" in src
    # The actual SQL body — narrowed to the upgrade() function — must
    # NOT touch independent-teacher tenant types. (The module
    # docstring is allowed to mention them for context.)
    upgrade_start = src.index("def upgrade()")
    upgrade_end = src.index("def downgrade()")
    upgrade_body = src[upgrade_start:upgrade_end]
    assert "independent_teacher" not in upgrade_body
    assert "DROP" not in upgrade_body.upper()
    assert "DELETE" not in upgrade_body.upper()
