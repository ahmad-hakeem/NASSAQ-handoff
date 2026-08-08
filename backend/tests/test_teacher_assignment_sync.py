"""
Tests for Task #919 — `teacher_assignments` as the single source of truth for
teacher class/subject assignments.

Covers the shared sync util (`backend/utils/teacher_assignment_sync.py`):
  * Pure subject auto-resolution (teacher subjects ∩ class grade curriculum):
    primary preference, single overlap, ambiguous, no overlap, and the
    curriculum-less single-subject fallback.
  * `is_tombstoned` matching rules (class-level vs subject-level removals).
  * Tombstone round-trip: add → load → clear.

And the reconciler's tombstone-awareness
(`routes.role_dashboards_mod._reconcile_teacher_assignments_from_schedule`):
an explicitly UNASSIGNED (teacher, class) pairing must NOT be resurrected from
the published schedule, even though the teacher still has scheduled lessons for
it (those lessons are kept-but-flagged elsewhere).
"""
import contextlib
import uuid

import pytest

from dependencies import db
from engines.sql_utils import gd_insert, gd_find
import routes.role_dashboards_mod as rd
from utils.teacher_assignment_sync import (
    normalize_subject_name,
    build_subject_name_index,
    match_subject_by_name,
    teacher_subject_ids_from_doc,
    resolve_subject,
    resolve_class_subject,
    resolve_teacher_single_subject,
    is_tombstoned,
    add_tombstone,
    load_tombstones,
    clear_tombstones,
    materialize_class_assignments_from_legacy_tca,
)


# ----------------------------------------------------------------------
# Pure subject resolution
# ----------------------------------------------------------------------
def test_resolve_subject_prefers_primary():
    sid, reason = resolve_subject(
        {"primary_subject_id": "s1"},
        grade_subject_ids={"s1", "s2"},
        teacher_subject_ids={"s1", "s2"},
    )
    assert sid == "s1"
    assert reason == "primary"


def test_resolve_subject_single_overlap():
    sid, reason = resolve_subject(
        {}, grade_subject_ids={"s1", "s9"}, teacher_subject_ids={"s1", "s7"})
    assert sid == "s1"
    assert reason == "single"


def test_resolve_subject_ambiguous_returns_none():
    sid, reason = resolve_subject(
        {}, grade_subject_ids={"s1", "s2"}, teacher_subject_ids={"s1", "s2"})
    assert sid is None
    assert reason == "ambiguous"


def test_resolve_subject_no_overlap_returns_none():
    sid, reason = resolve_subject(
        {}, grade_subject_ids={"s1"}, teacher_subject_ids={"s2"})
    assert sid is None
    assert reason == "none"


def test_resolve_subject_no_curriculum_single_fallback():
    sid, reason = resolve_subject(
        {}, grade_subject_ids=set(), teacher_subject_ids={"s7"})
    assert sid == "s7"
    assert reason == "no_curriculum_single"


def test_resolve_subject_no_curriculum_multiple_is_ambiguous():
    """Several teachable subjects and no curriculum to narrow them: this is a
    CHOICE, not a missing assignment — the caller must offer a picker instead
    of telling the principal to assign a subject they already assigned."""
    sid, reason = resolve_subject(
        {}, grade_subject_ids=set(), teacher_subject_ids={"s1", "s2"})
    assert sid is None
    assert reason == "ambiguous"


# ----------------------------------------------------------------------
# Arabic-aware subject name matching
# ----------------------------------------------------------------------
def test_normalize_subject_name_strips_article_and_orthography():
    assert normalize_subject_name("الرياضيات") == normalize_subject_name("رياضيات")
    assert normalize_subject_name(" الأحياء ") == normalize_subject_name("احياء")
    assert normalize_subject_name("اللغة العربية") == normalize_subject_name("اللغه العربيه")
    assert normalize_subject_name(None) == ""


def test_match_subject_by_name_definite_article():
    """The production bug: teacher specialization "رياضيات" vs subject
    "الرياضيات" — exact matching missed it and the pairing 409'd."""
    index = build_subject_name_index([
        {"id": "s-math", "name_ar": "الرياضيات"},
        {"id": "s-mathtest", "name_ar": "رياضيات اختبار"},
    ])
    assert match_subject_by_name("رياضيات", index) == "s-math"
    assert match_subject_by_name("الرياضيات", index) == "s-math"
    # Near-miss names must NOT collide (normalized-exact, never fuzzy).
    assert match_subject_by_name("رياضيات اختبار", index) == "s-mathtest"
    assert match_subject_by_name("تاريخ", index) is None


def test_match_subject_by_name_drops_colliding_normalized_key():
    """Both "الرياضيات" and "رياضيات" exist as separate subjects: the normalized
    key is genuinely ambiguous, so matching declines (the principal picks) and
    each exact name still resolves to its own subject."""
    index = build_subject_name_index([
        {"id": "s-a", "name_ar": "الرياضيات"},
        {"id": "s-b", "name_ar": "رياضيات"},
    ])
    # Exact names always win over the normalized key…
    assert index["الرياضيات"] == "s-a"
    assert index["رياضيات"] == "s-b"
    assert match_subject_by_name("رياضيات", index) == "s-b"
    # …and when the ambiguous key matches no exact name, matching declines.
    index2 = build_subject_name_index([
        {"id": "s-a", "name_ar": "الرياضيات"},
        {"id": "s-b", "name_ar": "الرياضيّات"},
    ])
    assert match_subject_by_name("رياضيات", index2) is None


def test_match_subject_by_name_english_legacy_key():
    index = build_subject_name_index([{"id": "s-math", "name_ar": "الرياضيات"}])
    assert match_subject_by_name("math", index) == "s-math"
    assert match_subject_by_name("Mathematics", index) == "s-math"


def test_teacher_subject_ids_from_doc_uses_normalized_specialization():
    index = build_subject_name_index([{"id": "s-sci", "name_ar": "العلوم"}])
    ids = teacher_subject_ids_from_doc({"specialization": "علوم"}, index, None)
    assert ids == {"s-sci"}


# ----------------------------------------------------------------------
# Tombstone matching
# ----------------------------------------------------------------------
def test_is_tombstoned_class_level_blocks_any_subject():
    tombs = [{"teacher_id": "t1", "class_id": "c1", "subject_id": None}]
    assert is_tombstoned(tombs, "t1", "c1", "anything") is True
    assert is_tombstoned(tombs, "t1", "c2", "anything") is False
    assert is_tombstoned(tombs, "t2", "c1", "anything") is False


def test_is_tombstoned_subject_level_school_wide():
    tombs = [{"teacher_id": "t1", "class_id": None, "subject_id": "s1"}]
    assert is_tombstoned(tombs, "t1", "c1", "s1") is True
    assert is_tombstoned(tombs, "t1", "c1", "s2") is False


def test_is_tombstoned_class_and_subject_specific():
    tombs = [{"teacher_id": "t1", "class_id": "c1", "subject_id": "s1"}]
    assert is_tombstoned(tombs, "t1", "c1", "s1") is True
    assert is_tombstoned(tombs, "t1", "c1", "s2") is False


# ----------------------------------------------------------------------
# Tombstone round-trip (DB)
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tombstone_add_load_clear_roundtrip():
    school_id = str(uuid.uuid4())
    teacher_id = str(uuid.uuid4())
    class_id = str(uuid.uuid4())

    await add_tombstone(db.session, school_id, teacher_id, class_id, None, created_by="tester")
    loaded = await load_tombstones(db.session, school_id, teacher_id)
    assert any(t.get("class_id") == class_id for t in loaded)

    removed = await clear_tombstones(db.session, school_id, teacher_id, class_id=class_id)
    assert removed >= 1
    after = await load_tombstones(db.session, school_id, teacher_id)
    assert not any(t.get("class_id") == class_id for t in after)


# ----------------------------------------------------------------------
# Reconciler tombstone-awareness
# ----------------------------------------------------------------------
async def _mk_school() -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": sid, "name": f"School-{sid[:6]}", "code": f"S{sid[:8]}",
        "status": "active", "country": "SA", "language": "ar",
    })
    return sid


async def _mk_teacher(school_id: str) -> str:
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid, "school_id": school_id, "full_name": "أحمد المعلم", "is_active": True,
    })
    return tid


async def _mk_class(school_id: str) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid, "school_id": school_id, "name": f"Class-{cid[:6]}",
    })
    return cid


async def _mk_subject(school_id: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": sid, "school_id": school_id, "name": f"Subject-{sid[:6]}",
    })
    return sid


def _patch_dedicated_session(monkeypatch):
    @contextlib.asynccontextmanager
    async def _factory():
        original_commit = db.session.commit

        async def _noop_commit():
            await db.session.flush()

        monkeypatch.setattr(db.session, "commit", _noop_commit, raising=False)
        try:
            yield db.session
        finally:
            monkeypatch.setattr(db.session, "commit", original_commit, raising=False)

    import db as db_module
    monkeypatch.setattr(db_module, "async_session_factory", _factory, raising=False)


def _patch_sessions(monkeypatch, sessions):
    async def _fake_resolve(school_id, teacher_id):
        return sessions
    monkeypatch.setattr(rd, "_resolve_teacher_sessions", _fake_resolve)


async def _active_assignments(teacher_id, school_id):
    rows = await gd_find(
        db.session, "teacher_assignments",
        {"teacher_id": teacher_id, "school_id": school_id}, limit=1000,
    )
    return [r for r in rows if r.get("is_active") is not False]


@pytest.mark.asyncio
async def test_reconciler_skips_tombstoned_pair(monkeypatch):
    """A class-level removal must keep the pairing unassigned even though the
    teacher still has a scheduled lesson for it."""
    school_id = await _mk_school()
    teacher_id = await _mk_teacher(school_id)
    c1, c2 = await _mk_class(school_id), await _mk_class(school_id)
    s1, s2 = await _mk_subject(school_id), await _mk_subject(school_id)

    # (c1, s1) was explicitly unassigned by the principal.
    await add_tombstone(db.session, school_id, teacher_id, c1, None)

    _patch_sessions(monkeypatch, [
        {"class_id": c1, "subject_id": s1},  # tombstoned -> must be skipped
        {"class_id": c2, "subject_id": s2},  # normal -> materialized
    ])
    _patch_dedicated_session(monkeypatch)

    created = await rd._reconcile_teacher_assignments_from_schedule(
        school_id, teacher_id, "أحمد المعلم")
    assert created == 1

    active = await _active_assignments(teacher_id, school_id)
    pairs = {(a.get("class_id"), a.get("subject_id")) for a in active}
    assert pairs == {(c2, s2)}
    assert (c1, s1) not in pairs


@pytest.mark.asyncio
async def test_reconciler_all_tombstoned_creates_nothing(monkeypatch):
    school_id = await _mk_school()
    teacher_id = await _mk_teacher(school_id)
    c1, s1 = await _mk_class(school_id), await _mk_subject(school_id)
    await add_tombstone(db.session, school_id, teacher_id, c1, None)

    _patch_sessions(monkeypatch, [{"class_id": c1, "subject_id": s1}])
    _patch_dedicated_session(monkeypatch)

    created = await rd._reconcile_teacher_assignments_from_schedule(
        school_id, teacher_id, None)
    assert created == 0
    assert await _active_assignments(teacher_id, school_id) == []


# ----------------------------------------------------------------------
# resolve_teacher_single_subject (mirrors the scheduler's legacy map)
# ----------------------------------------------------------------------
def test_resolve_teacher_single_subject_prefers_primary():
    sid = resolve_teacher_single_subject(
        {"primary_subject_id": "s1"}, subject_by_id={"s1": {}}, subject_by_name={})
    assert sid == "s1"


def test_resolve_teacher_single_subject_falls_back_to_name():
    sid = resolve_teacher_single_subject(
        {"specialization": "رياضيات"}, subject_by_id={"s9": {}},
        subject_by_name={"رياضيات": "s9"})
    assert sid == "s9"


def test_resolve_teacher_single_subject_unresolved_returns_none():
    assert resolve_teacher_single_subject({}, {}, {}) is None


# ----------------------------------------------------------------------
# Legacy-TCA → canonical backfill (Task #919 single-source-of-truth fix)
# ----------------------------------------------------------------------
async def _mk_named_subject(school_id: str, name: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": sid, "school_id": school_id, "name": name,
    })
    return sid


async def _mk_teacher_specialized(school_id: str, subject_name: str) -> str:
    """Real `teachers` rows carry no `primary_subject_id`; the single subject is
    resolved from the `specialization`/`subject` name (mirrors the scheduler)."""
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": tid, "school_id": school_id, "full_name": "أحمد المعلم",
        "specialization": subject_name, "is_active": True,
    })
    return tid


async def _mk_tca(school_id: str, teacher_id: str, class_id: str):
    await gd_insert(db.session, "teacher_class_assignments", {
        "id": str(uuid.uuid4()), "school_id": school_id,
        "teacher_id": teacher_id, "class_id": class_id, "is_active": True,
    })


@pytest.mark.asyncio
async def test_legacy_tca_backfill_materializes_canonical(monkeypatch):
    """An active TCA link becomes a canonical (teacher, class, subject) row."""
    school_id = await _mk_school()
    s1 = await _mk_named_subject(school_id, "رياضيات")
    teacher_id = await _mk_teacher_specialized(school_id, "رياضيات")
    c1 = await _mk_class(school_id)
    await _mk_tca(school_id, teacher_id, c1)
    _patch_dedicated_session(monkeypatch)

    created = await materialize_class_assignments_from_legacy_tca(school_id)
    assert created == 1
    pairs = {(a.get("class_id"), a.get("subject_id")) for a in await _active_assignments(teacher_id, school_id)}
    assert pairs == {(c1, s1)}


@pytest.mark.asyncio
async def test_legacy_tca_backfill_skips_tombstoned(monkeypatch):
    """A tombstoned (teacher, class) is never resurrected by the backfill."""
    school_id = await _mk_school()
    await _mk_named_subject(school_id, "علوم")
    teacher_id = await _mk_teacher_specialized(school_id, "علوم")
    c1 = await _mk_class(school_id)
    await _mk_tca(school_id, teacher_id, c1)
    await add_tombstone(db.session, school_id, teacher_id, c1, None)
    _patch_dedicated_session(monkeypatch)

    created = await materialize_class_assignments_from_legacy_tca(school_id)
    assert created == 0
    assert await _active_assignments(teacher_id, school_id) == []


@pytest.mark.asyncio
async def test_legacy_tca_backfill_is_idempotent(monkeypatch):
    """Running the backfill twice does not duplicate canonical rows."""
    school_id = await _mk_school()
    await _mk_named_subject(school_id, "إنجليزي")
    teacher_id = await _mk_teacher_specialized(school_id, "إنجليزي")
    c1 = await _mk_class(school_id)
    await _mk_tca(school_id, teacher_id, c1)
    _patch_dedicated_session(monkeypatch)

    assert await materialize_class_assignments_from_legacy_tca(school_id) == 1
    assert await materialize_class_assignments_from_legacy_tca(school_id) == 0
    assert len(await _active_assignments(teacher_id, school_id)) == 1


# ----------------------------------------------------------------------
# resolve_class_subject — reassign lifecycle + polluted-pool regression
# ----------------------------------------------------------------------
async def _mk_ta_row(school_id, teacher_id, class_id, subject_id, is_active=True):
    await gd_insert(db.session, "teacher_assignments", {
        "id": str(uuid.uuid4()), "school_id": school_id,
        "teacher_id": teacher_id, "class_id": class_id,
        "subject_id": subject_id, "is_active": is_active,
    })


@pytest.mark.asyncio
async def test_resolve_class_subject_reuses_prior_pair_subject():
    """Unassign → reassign the SAME (teacher, class): the subject from the
    deactivated canonical row must be reused instead of failing resolution."""
    school_id = await _mk_school()
    s1 = await _mk_named_subject(school_id, "التاريخ")
    teacher_id = await _mk_teacher(school_id)  # no specialization at all
    c1 = await _mk_class(school_id)
    await _mk_ta_row(school_id, teacher_id, c1, s1, is_active=False)

    teacher = (await gd_find(db.session, "teachers", {"id": teacher_id}, limit=1))[0]
    class_doc = (await gd_find(db.session, "classes", {"id": c1}, limit=1))[0]
    sid, reason = await resolve_class_subject(db.session, school_id, teacher, class_doc)
    assert sid == s1
    assert reason == "previous"


@pytest.mark.asyncio
async def test_resolve_class_subject_own_subject_beats_polluted_pool():
    """A teacher whose own subject resolves by name must not be blocked just
    because OTHER active class rows carry many unrelated subjects (the
    production reassign bug: empty curriculum + polluted extra pool)."""
    school_id = await _mk_school()
    s_hist = await _mk_named_subject(school_id, "التاريخ")
    s_math = await _mk_named_subject(school_id, "الرياضيات")
    s_sci = await _mk_named_subject(school_id, "العلوم")
    teacher_id = await _mk_teacher_specialized(school_id, "التاريخ")
    c_target = await _mk_class(school_id)
    c_other1, c_other2 = await _mk_class(school_id), await _mk_class(school_id)
    # Polluting active rows on other classes with unrelated subjects.
    await _mk_ta_row(school_id, teacher_id, c_other1, s_math)
    await _mk_ta_row(school_id, teacher_id, c_other2, s_sci)

    teacher = (await gd_find(db.session, "teachers", {"id": teacher_id}, limit=1))[0]
    class_doc = (await gd_find(db.session, "classes", {"id": c_target}, limit=1))[0]
    sid, _reason = await resolve_class_subject(db.session, school_id, teacher, class_doc)
    assert sid == s_hist


@pytest.mark.asyncio
async def test_resolve_class_subject_extra_pool_still_used_as_fallback():
    """A teacher with NO doc-level subject but exactly one subject across
    active assignment rows must still resolve (pre-fix behavior preserved)."""
    school_id = await _mk_school()
    s1 = await _mk_named_subject(school_id, "الجغرافيا")
    teacher_id = await _mk_teacher(school_id)  # no specialization
    c_target, c_other = await _mk_class(school_id), await _mk_class(school_id)
    await _mk_ta_row(school_id, teacher_id, c_other, s1)

    teacher = (await gd_find(db.session, "teachers", {"id": teacher_id}, limit=1))[0]
    class_doc = (await gd_find(db.session, "classes", {"id": c_target}, limit=1))[0]
    sid, _reason = await resolve_class_subject(db.session, school_id, teacher, class_doc)
    assert sid == s1


@pytest.mark.asyncio
async def test_legacy_tca_backfill_skips_unresolvable_subject(monkeypatch):
    """A TCA link for a teacher with no resolvable subject yields no row —
    matching the old scheduler, which also skipped such links."""
    school_id = await _mk_school()
    teacher_id = await _mk_teacher(school_id)  # no primary_subject_id / specialization
    c1 = await _mk_class(school_id)
    await _mk_tca(school_id, teacher_id, c1)
    _patch_dedicated_session(monkeypatch)

    created = await materialize_class_assignments_from_legacy_tca(school_id)
    assert created == 0
    assert await _active_assignments(teacher_id, school_id) == []
