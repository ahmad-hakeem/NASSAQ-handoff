"""Single-source-of-truth helpers for teacher class/subject assignments
(Task #919).

``teacher_assignments`` (collection) is the canonical table read by the
principal's School Timetable Settings, the teacher's own "فصولي" page, the
class-access permission layer (``utils.tenant_scope``) and the scheduler's
eligibility input. The principal assigns a teacher to a CLASS (class-only in
the UI); the subject is auto-filled here as ``teacher subjects ∩ class grade
curriculum``.

Unassigning a (teacher, class) pairing must STICK across every surface and
across re-derivation passes (the published-schedule reconciler and the default
"all teachers ↔ all classes" materializer both run additively). We record an
explicit removal in the generic-document collection
``teacher_assignment_removals`` (a "tombstone"). gd_* falls back to
``GenericDocument`` JSONB for unregistered collections, so no Alembic migration
is required.

Everything here is REAL-school only: Independent-Teacher synthetic workspaces
(``itw_*``) manage their own model and are skipped by callers.
"""
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from auth_scope import is_independent_workspace_id
from engines.sql_utils import gd_find, gd_insert, gd_update_one, gd_delete_many

logger = logging.getLogger(__name__)

TOMBSTONE_COLLECTION = "teacher_assignment_removals"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Tombstones (explicit removals)
# ---------------------------------------------------------------------------
async def load_tombstones(session, school_id: str, teacher_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return removal records for a school (optionally a single teacher)."""
    if not school_id:
        return []
    flt: Dict[str, Any] = {"school_id": school_id}
    if teacher_id:
        flt["teacher_id"] = teacher_id
    try:
        return await gd_find(session, TOMBSTONE_COLLECTION, flt, limit=20000)
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("load_tombstones failed for school %s: %s", school_id, e)
        return []


def is_tombstoned(
    tombstones: List[Dict[str, Any]],
    teacher_id: str,
    class_id: Optional[str],
    subject_id: Optional[str],
) -> bool:
    """True when (teacher, class, subject) has an explicit removal.

    Matching rules:
      * class-level removal: ``class_id`` matches and the tombstone's
        ``subject_id`` is None (whole class removed for the teacher) or equals
        the candidate subject.
      * subject-level removal (school-wide): tombstone ``class_id`` is None and
        its ``subject_id`` equals the candidate subject.
    """
    for t in tombstones:
        if t.get("teacher_id") != teacher_id:
            continue
        t_class = t.get("class_id")
        t_subject = t.get("subject_id")
        if t_class and class_id and t_class == class_id:
            if t_subject is None or t_subject == subject_id:
                return True
        elif t_class is None and t_subject is not None and t_subject == subject_id:
            return True
    return False


async def add_tombstone(
    session,
    school_id: str,
    teacher_id: str,
    class_id: Optional[str],
    subject_id: Optional[str],
    created_by: Optional[str] = None,
) -> None:
    """Record an explicit removal. ``subject_id=None`` with a ``class_id`` means
    the whole class was unassigned for the teacher."""
    try:
        await gd_insert(session, TOMBSTONE_COLLECTION, {
            "id": str(uuid.uuid4()),
            "school_id": school_id,
            "teacher_id": teacher_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "created_at": _now(),
            "created_by": created_by,
        })
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(
            "add_tombstone failed teacher=%s class=%s subject=%s: %s",
            teacher_id, class_id, subject_id, e,
        )


async def clear_tombstones(
    session,
    school_id: str,
    teacher_id: str,
    class_id: Optional[str] = None,
    subject_id: Optional[str] = None,
) -> int:
    """Remove tombstones that would block re-assigning (teacher, class[, subject]).

    Re-assigning a class clears every removal for that (teacher, class) pair
    (class-level and per-subject). Re-assigning a school-wide subject clears the
    matching subject-level removal.
    """
    removed = 0
    all_t = await load_tombstones(session, school_id, teacher_id)
    for t in all_t:
        match = False
        if class_id is not None and t.get("class_id") == class_id:
            match = True
        elif class_id is None and subject_id is not None and t.get("class_id") is None and t.get("subject_id") == subject_id:
            match = True
        if match:
            try:
                removed += await gd_delete_many(
                    session, TOMBSTONE_COLLECTION, {"id": t.get("id"), "school_id": school_id}
                )
            except Exception as e:  # pragma: no cover - defensive
                logger.warning("clear_tombstones failed id=%s: %s", t.get("id"), e)
    return removed


# ---------------------------------------------------------------------------
# Subject resolution (teacher subjects ∩ class grade curriculum)
# ---------------------------------------------------------------------------
def _grade_keys(class_doc: Dict[str, Any]) -> List[str]:
    """Candidate grade keys for a class, canonical first (mirrors the engine's
    best-effort resolution without importing the heavy engine module)."""
    keys: List[str] = []
    for raw in (class_doc.get("grade_id"), class_doc.get("grade_level"), class_doc.get("level")):
        if raw and str(raw) not in keys:
            keys.append(str(raw))
    return keys


async def get_grade_subject_ids(session, school_id: str, class_doc: Dict[str, Any]) -> Set[str]:
    """Subject ids in the class's grade curriculum (``grade_subjects``)."""
    for key in _grade_keys(class_doc):
        rows = await gd_find(
            session, "grade_subjects",
            {"school_id": school_id, "grade_id": key, "is_active": True}, limit=200,
        )
        ids = {r.get("subject_id") for r in rows if r.get("subject_id")}
        if ids:
            return ids
    return set()


_AR_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")

# Legacy/imported teacher records store the specialization as an English key
# ("math", "arabic", ...) while the school's subjects are named in Arabic.
# Each entry lists normalized Arabic names to try, most specific first; the
# first name that exists in the school's catalogue wins (so a school that has
# both "عربي" and "اللغة العربية" still resolves to exactly one subject).
_SPECIALIZATION_ALIASES: Dict[str, Tuple[str, ...]] = {
    "math": ("رياضيات",),
    "maths": ("رياضيات",),
    "mathematics": ("رياضيات",),
    "arabic": ("لغه العربيه", "عربي", "لغه عربيه"),
    "english": ("لغه الانجليزيه", "انجليزي", "لغه انجليزيه"),
    "science": ("علوم",),
    "islamic": ("تربيه الاسلاميه", "تربيه اسلاميه"),
    "islamic studies": ("تربيه الاسلاميه", "تربيه اسلاميه"),
    "pe": ("تربيه البدنيه", "تربيه بدنيه"),
    "physical education": ("تربيه البدنيه", "تربيه بدنيه"),
    "art": ("تربيه الفنيه", "تربيه فنيه"),
    "computer": ("حاسوب", "حاسب الالي", "مهارات رقميه"),
    "it": ("حاسوب", "مهارات رقميه"),
    "social": ("دراسات الاجتماعيه", "دراسات اجتماعيه"),
    "history": ("تاريخ",),
    "geography": ("جغرافيا",),
    "chemistry": ("كيمياء",),
    "physics": ("فيزياء",),
    "biology": ("احياء",),
}


def normalize_subject_name(value: Any) -> str:
    """Normalize a subject/specialization name for matching.

    Arabic subject catalogues and free-text teacher specializations rarely
    agree character-for-character: "رياضيات" (specialization) vs "الرياضيات"
    (subject name), أ/إ/آ vs ا, ة vs ه, stray diacritics/tatweel. Exact string
    matching made the auto-resolver miss the teacher's own subject and raise a
    false "no suitable subject" error, so every comparison goes through here.
    """
    if not value:
        return ""
    s = str(value).strip()
    s = s.replace("\u0640", "")  # tatweel
    s = _AR_DIACRITICS.sub("", s)
    s = re.sub(r"[أإآٱ]", "ا", s)
    s = s.replace("ة", "ه").replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")
    s = re.sub(r"\s+", " ", s).strip().lower()
    # Definite article: "الرياضيات" == "رياضيات". Guarded by a length floor so
    # short words that merely start with those letters are left alone.
    if s.startswith("ال") and len(s) > 4:
        s = s[2:]
    return s


def build_subject_name_index(subjects: List[Dict[str, Any]]) -> Dict[str, str]:
    """name (ar/en) -> subject_id, for resolving a teacher's text specialization.

    Both the raw and the normalized name are indexed so callers can match a
    free-text specialization that differs only in orthography.
    """
    by_name: Dict[str, str] = {}
    norm_hits: Dict[str, Set[str]] = {}
    for s in subjects:
        sid = s.get("id") or s.get("subject_id")
        if not sid:
            continue
        for key in ("name_ar", "name", "name_en"):
            v = s.get(key)
            if not v:
                continue
            by_name.setdefault(str(v).strip(), sid)
            norm = normalize_subject_name(v)
            if norm:
                norm_hits.setdefault(norm, set()).add(sid)
    # Normalized keys never override an exact name, and a key claimed by two
    # different subjects (e.g. both "الرياضيات" and "رياضيات" exist) is dropped:
    # matching stays deterministic and the choice goes to the principal instead
    # of depending on whichever row the database returned first.
    for norm, ids in norm_hits.items():
        if len(ids) == 1:
            by_name.setdefault(norm, next(iter(ids)))
    return by_name


def match_subject_by_name(name: Any, subject_by_name: Dict[str, str]) -> Optional[str]:
    """Resolve a free-text subject/specialization to a subject id."""
    if not name or not subject_by_name:
        return None
    raw = str(name).strip()
    if raw in subject_by_name:
        return subject_by_name[raw]
    norm = normalize_subject_name(raw)
    if norm and norm in subject_by_name:
        return subject_by_name[norm]
    for alias in _SPECIALIZATION_ALIASES.get(norm, ()):  # English legacy keys
        if alias in subject_by_name:
            return subject_by_name[alias]
    return None


def teacher_subject_ids_from_doc(
    teacher_doc: Dict[str, Any],
    subject_by_name: Optional[Dict[str, str]] = None,
    extra_subject_ids: Optional[Set[str]] = None,
) -> Set[str]:
    """Subjects a teacher can teach, derived from the teacher record (and any
    explicit subject-level ``teacher_assignments`` passed via ``extra_subject_ids``)."""
    ids: Set[str] = set()
    primary = teacher_doc.get("primary_subject_id")
    if primary:
        ids.add(primary)
    for sid in (teacher_doc.get("subject_ids") or []):
        if sid:
            ids.add(sid)
    if subject_by_name:
        for key in ("subject", "specialization"):
            sid = match_subject_by_name(teacher_doc.get(key), subject_by_name)
            if sid:
                ids.add(sid)
    if extra_subject_ids:
        ids |= extra_subject_ids
    return ids


def resolve_subject(
    teacher_doc: Dict[str, Any],
    grade_subject_ids: Set[str],
    teacher_subject_ids: Set[str],
) -> Tuple[Optional[str], str]:
    """Auto-fill the subject for a (teacher, class) class-only assignment.

    Returns ``(subject_id, reason)``. ``subject_id`` is None when the choice is
    ambiguous or there is no overlap — callers turn that into a "subject
    required" signal (interactive) or skip silently (bulk default).
    """
    matched = grade_subject_ids & teacher_subject_ids
    primary = teacher_doc.get("primary_subject_id")
    if primary and primary in matched:
        return primary, "primary"
    if len(matched) == 1:
        return next(iter(matched)), "single"
    if len(matched) > 1:
        return None, "ambiguous"
    # No curriculum overlap. If the grade has no curriculum at all and the
    # teacher has exactly one subject, fall back to it so curriculum-less
    # schools still get a sensible default.
    if not grade_subject_ids and len(teacher_subject_ids) == 1:
        return next(iter(teacher_subject_ids)), "no_curriculum_single"
    if not grade_subject_ids and len(teacher_subject_ids) > 1:
        # The teacher can teach several subjects and the grade has no
        # curriculum to narrow them down: this is a CHOICE, not a missing
        # assignment — say so, so the caller offers a picker instead of
        # telling the principal to assign a subject they already assigned.
        return None, "ambiguous"
    return None, "none"


async def resolve_class_subject(
    session, school_id: str, teacher_doc: Dict[str, Any], class_doc: Dict[str, Any]
) -> Tuple[Optional[str], str]:
    """Resolve the subject for an interactive (teacher, class) assignment.

    Resolution order:
      1. "previous" — a deactivated canonical row for this exact pair keeps the
         subject that was valid before the unassignment; reassigning restores
         it (the unassign → reassign lifecycle must be a clean inverse).
      2. Own-doc subjects (primary/subject_ids/specialization name match) —
         the teacher's own subject must not be drowned out by unrelated
         subjects harvested from other class rows.
      3. Legacy widened pool (own ∪ subjects on the teacher's other active
         assignment rows) — preserved as a fallback for teachers whose record
         carries no resolvable subject of its own.
    """
    subjects = await gd_find(session, "subjects", {"school_id": school_id}, limit=5000)
    subject_ids = {(s.get("id") or s.get("subject_id")) for s in subjects}
    subject_by_name = build_subject_name_index(subjects)
    teacher_id = teacher_doc.get("id")
    class_id = class_doc.get("id")

    # 1) Reassignment of a previously assigned pair: reuse its subject.
    if teacher_id and class_id:
        prior_rows = await gd_find(session, "teacher_assignments", {
            "school_id": school_id, "teacher_id": teacher_id,
            "class_id": class_id, "is_active": False,
        }, limit=50)
        prior_rows = [r for r in prior_rows if r.get("subject_id") in subject_ids]
        if prior_rows:
            prior_rows.sort(
                key=lambda r: (r.get("updated_at") or r.get("created_at") or ""),
                reverse=True,
            )
            return prior_rows[0].get("subject_id"), "previous"

    grade_subj = await get_grade_subject_ids(session, school_id, class_doc)

    # 2) Own-doc subjects first.
    own_subj = teacher_subject_ids_from_doc(teacher_doc, subject_by_name, None)
    sid, reason = resolve_subject(teacher_doc, grade_subj, own_subj)
    if sid:
        return sid, reason

    # 3) Widen with subjects from the teacher's other active assignment rows.
    ta = await gd_find(
        session, "teacher_assignments",
        {"school_id": school_id, "teacher_id": teacher_id, "is_active": True}, limit=2000,
    )
    extra = {a.get("subject_id") for a in ta if a.get("subject_id")}
    if not extra:
        return sid, reason
    return resolve_subject(teacher_doc, grade_subj, own_subj | extra)


async def class_subject_candidates(
    session, school_id: str, teacher_doc: Dict[str, Any], class_doc: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Subjects the principal can choose from when auto-resolution fails.

    Narrowest useful set first: the teacher's own + assigned subjects (limited
    to the class grade's curriculum when the school has one), falling back to
    the grade curriculum and finally to the whole school catalogue — so the
    "pick a subject" dialog is never empty and the pairing is never a dead end.
    """
    subjects = await gd_find(session, "subjects", {"school_id": school_id}, limit=5000)
    by_id = {
        (s.get("id") or s.get("subject_id")): s
        for s in subjects
        if (s.get("id") or s.get("subject_id")) and s.get("is_active") is not False
    }
    subject_by_name = build_subject_name_index(subjects)

    own = teacher_subject_ids_from_doc(teacher_doc, subject_by_name, None)
    ta = await gd_find(
        session, "teacher_assignments",
        {"school_id": school_id, "teacher_id": teacher_doc.get("id"), "is_active": True},
        limit=2000,
    )
    pool = own | {a.get("subject_id") for a in ta if a.get("subject_id")}

    grade_subj = await get_grade_subject_ids(session, school_id, class_doc)
    if grade_subj:
        pool = (pool & grade_subj) or pool or grade_subj
    if not pool:
        pool = set(by_id)

    out = [
        {"id": sid, "name": (by_id[sid].get("name_ar") or by_id[sid].get("name") or "")}
        for sid in pool if sid in by_id
    ]
    out.sort(key=lambda x: x["name"])
    return out


# ---------------------------------------------------------------------------
# Default materialization ("all teachers ↔ all classes" where a subject resolves)
# ---------------------------------------------------------------------------
async def materialize_default_class_assignments(
    school_id: str,
    teacher_ids: Optional[List[str]] = None,
    class_ids: Optional[List[str]] = None,
) -> int:
    """Materialize canonical ``teacher_assignments`` (teacher, class, subject)
    for every teacher×class whose subject resolves unambiguously, preserving the
    product default that teachers are linked to all classes they can teach.

    ADDITIVE + idempotent + tombstone-aware: never recreates an explicitly
    removed pairing, never duplicates an active pair, reactivates a matching
    soft-deactivated row. Real schools only.

    Runs from GET handlers, so it uses a dedicated session with an explicit
    commit (``pg_session_middleware`` rolls back GET-request transactions).
    """
    if not school_id or is_independent_workspace_id(school_id):
        return 0

    from db import async_session_factory

    created = 0
    async with async_session_factory() as ses:
        teachers = await gd_find(ses, "teachers", {"school_id": school_id, "is_active": {"$ne": False}}, limit=5000)
        classes = await gd_find(ses, "classes", {"school_id": school_id, "is_active": {"$ne": False}}, limit=2000)
        if teacher_ids is not None:
            tset = set(teacher_ids)
            teachers = [t for t in teachers if t.get("id") in tset]
        if class_ids is not None:
            cset = set(class_ids)
            classes = [c for c in classes if c.get("id") in cset]
        if not teachers or not classes:
            return 0

        subjects = await gd_find(ses, "subjects", {"school_id": school_id}, limit=10000)
        subject_by_name = build_subject_name_index(subjects)

        existing = await gd_find(ses, "teacher_assignments", {"school_id": school_id}, limit=50000)
        active_pairs = {
            (a.get("teacher_id"), a.get("class_id"), a.get("subject_id"))
            for a in existing if a.get("is_active") is not False
        }
        inactive_by_key = {
            (a.get("teacher_id"), a.get("class_id"), a.get("subject_id")): a
            for a in existing if a.get("is_active") is False
        }
        # A teacher with ANY active class assignment is considered already set up;
        # we still backfill teachers that have none.
        teacher_has_active_class = {
            a.get("teacher_id") for a in existing
            if a.get("is_active") is not False and a.get("class_id")
        }
        subject_assign_by_teacher: Dict[str, Set[str]] = {}
        for a in existing:
            if a.get("is_active") is not False and a.get("subject_id"):
                subject_assign_by_teacher.setdefault(a.get("teacher_id"), set()).add(a.get("subject_id"))

        tombstones = await load_tombstones(ses, school_id)

        # grade curriculum cache: grade_key -> set(subject_id)
        grade_cache: Dict[str, Set[str]] = {}

        async def _grade_ids(class_doc) -> Set[str]:
            for key in _grade_keys(class_doc):
                if key in grade_cache:
                    if grade_cache[key]:
                        return grade_cache[key]
                    continue
                rows = await gd_find(
                    ses, "grade_subjects",
                    {"school_id": school_id, "grade_id": key, "is_active": True}, limit=200,
                )
                ids = {r.get("subject_id") for r in rows if r.get("subject_id")}
                grade_cache[key] = ids
                if ids:
                    return ids
            return set()

        now = _now()
        for t in teachers:
            tid = t.get("id")
            if not tid:
                continue
            # Only seed defaults for teachers that have no class assignment yet
            # (preserve a principal's curated set; never widen it here).
            if tid in teacher_has_active_class:
                continue
            teacher_subj = teacher_subject_ids_from_doc(
                t, subject_by_name, subject_assign_by_teacher.get(tid),
            )
            if not teacher_subj:
                continue
            for c in classes:
                cid = c.get("id")
                if not cid:
                    continue
                grade_subj = await _grade_ids(c)
                sid, _reason = resolve_subject(t, grade_subj, teacher_subj)
                if not sid:
                    continue
                if (tid, cid, sid) in active_pairs:
                    continue
                if is_tombstoned(tombstones, tid, cid, sid):
                    continue
                try:
                    async with ses.begin_nested():
                        revived = inactive_by_key.get((tid, cid, sid))
                        if revived:
                            await gd_update_one(
                                ses, "teacher_assignments", {"id": revived.get("id")},
                                {"is_active": True, "updated_at": now},
                            )
                        else:
                            await gd_insert(ses, "teacher_assignments", {
                                "id": str(uuid.uuid4()),
                                "school_id": school_id,
                                "teacher_id": tid,
                                "class_id": cid,
                                "subject_id": sid,
                                "teacher_name": t.get("full_name"),
                                "is_active": True,
                                "auto_assigned": True,
                                "created_at": now,
                            })
                    created += 1
                    active_pairs.add((tid, cid, sid))
                except Exception as e:
                    logger.warning(
                        "default materialize failed teacher=%s class=%s subject=%s: %s",
                        tid, cid, sid, e,
                    )
        if created:
            try:
                await ses.commit()
            except Exception as e:
                logger.warning("default materialize commit failed for school %s: %s", school_id, e)
                await ses.rollback()
                return 0
    return created


def resolve_teacher_single_subject(
    teacher_doc: Dict[str, Any],
    subject_by_id: Dict[str, Any],
    subject_by_name: Dict[str, str],
) -> Optional[str]:
    """Resolve the ONE subject a teacher teaches, mirroring the scheduler's
    legacy ``teacher_subject_map``: ``primary_subject_id`` first (when it names a
    real subject), then the teacher's ``subject``/``specialization`` text matched
    against the subject-name index. Used to backfill canonical rows from legacy
    ``teacher_class_assignments`` links with EXACTLY the eligibility the old
    scheduler synthesised, so retiring the TCA read introduces no behaviour
    change."""
    primary = teacher_doc.get("primary_subject_id")
    if primary and primary in subject_by_id:
        return primary
    for key in ("subject", "specialization"):
        name = teacher_doc.get(key)
        if name:
            sid = subject_by_name.get(str(name).strip())
            if sid:
                return sid
    return None


async def materialize_class_assignments_from_legacy_tca(school_id: str) -> int:
    """Backfill canonical ``teacher_assignments`` from legacy
    ``teacher_class_assignments`` (TCA) links (Task #919).

    Each active TCA (teacher, class) link is materialized as a canonical
    (teacher, class, resolved-subject) row, where the subject is resolved the
    same single-subject way the scheduler's old ``class_tca_map`` did. This makes
    canonical the complete eligibility source so the scheduler can stop reading
    TCA directly without losing any existing-school eligibility.

    ADDITIVE + idempotent + tombstone-aware + real-schools only. Never recreates
    an explicitly removed pairing, never duplicates an active pair, reactivates a
    matching soft-deactivated row. Uses a dedicated session with an explicit
    commit (safe to call from GET/engine paths)."""
    if not school_id or is_independent_workspace_id(school_id):
        return 0

    from db import async_session_factory

    created = 0
    async with async_session_factory() as ses:
        try:
            tca_links = await gd_find(
                ses, "teacher_class_assignments",
                {"school_id": school_id, "is_active": True}, limit=20000,
            )
        except Exception:
            tca_links = []
        if not tca_links:
            return 0

        subjects = await gd_find(ses, "subjects", {"school_id": school_id}, limit=10000)
        subject_by_id = {(s.get("id") or s.get("subject_id")): s for s in subjects if (s.get("id") or s.get("subject_id"))}
        subject_by_name = build_subject_name_index(subjects)
        teachers = await gd_find(ses, "teachers", {"school_id": school_id, "is_active": {"$ne": False}}, limit=10000)
        teacher_by_id = {t.get("id"): t for t in teachers if t.get("id")}

        existing = await gd_find(ses, "teacher_assignments", {"school_id": school_id}, limit=50000)
        active_pairs = {
            (a.get("teacher_id"), a.get("class_id"), a.get("subject_id"))
            for a in existing if a.get("is_active") is not False
        }
        inactive_by_key = {
            (a.get("teacher_id"), a.get("class_id"), a.get("subject_id")): a
            for a in existing if a.get("is_active") is False
        }
        tombstones = await load_tombstones(ses, school_id)

        now = _now()
        seen: Set[Tuple[str, str, str]] = set()
        for link in tca_links:
            tid = link.get("teacher_id")
            cid = link.get("class_id")
            if not tid or not cid:
                continue
            t = teacher_by_id.get(tid)
            if not t:
                continue
            sid = resolve_teacher_single_subject(t, subject_by_id, subject_by_name)
            if not sid:
                continue
            key = (tid, cid, sid)
            if key in seen or key in active_pairs:
                continue
            seen.add(key)
            if is_tombstoned(tombstones, tid, cid, sid):
                continue
            try:
                async with ses.begin_nested():
                    revived = inactive_by_key.get(key)
                    if revived:
                        await gd_update_one(
                            ses, "teacher_assignments", {"id": revived.get("id")},
                            {"is_active": True, "updated_at": now},
                        )
                    else:
                        await gd_insert(ses, "teacher_assignments", {
                            "id": str(uuid.uuid4()),
                            "school_id": school_id,
                            "teacher_id": tid,
                            "class_id": cid,
                            "subject_id": sid,
                            "teacher_name": t.get("full_name"),
                            "is_active": True,
                            "auto_assigned": True,
                            "created_at": now,
                        })
                created += 1
                active_pairs.add(key)
            except Exception as e:
                logger.warning(
                    "legacy-TCA backfill failed teacher=%s class=%s subject=%s: %s",
                    tid, cid, sid, e,
                )
        if created:
            try:
                await ses.commit()
            except Exception as e:
                logger.warning("legacy-TCA backfill commit failed for school %s: %s", school_id, e)
                await ses.rollback()
                return 0
    return created
