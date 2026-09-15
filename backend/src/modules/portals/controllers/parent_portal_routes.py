"""
NASSAQ - Parent Portal Routes
مسارات بوابة ولي الأمر
"""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

SAUDI_TZ = ZoneInfo("Asia/Riyadh")
import uuid
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, gd_upsert
from src.core.guards.tenant_guard import is_independent_workspace_id
from src.common.utils.it_schedule import normalize_it_day, compute_it_slot_times
from src.common.utils.subject_display import build_subject_name_map

import logging

from sqlalchemy.exc import ProgrammingError, OperationalError
from sqlalchemy import select, func, and_, cast, bindparam, text as sa_text
from sqlalchemy.types import Date as _SADate

logger = logging.getLogger("nassaq.parent_portal_routes")


# ---------------------------------------------------------------------------
# SQL attendance table helpers (replaces gd_find/gd_count/gd_distinct on the
# empty generic_documents "attendance" collection — real data lives in the
# pg `attendance` table via pg_models.Attendance).
# ---------------------------------------------------------------------------

def _att_where(model, filters: dict):
    """Build SQLAlchemy WHERE conditions from a filter dict.

    attendance.date is DateTime(timezone=True) → timestamptz.  Passing bare
    ISO strings lets asyncpg bind them as varchar, which Postgres rejects with
    "operator does not exist: timestamptz >= character varying".  We convert
    string values to datetime.date so asyncpg sends the correct type; Postgres
    implicitly casts date → timestamptz for the comparison.
    """
    from datetime import date as _pydate

    def _coerce_date(v):
        if isinstance(v, str):
            try:
                return _pydate.fromisoformat(v)
            except ValueError:
                return v
        return v

    conds = []
    for key, val in (filters or {}).items():
        if key == "student_id":
            conds.append(model.student_id == val)
        elif key == "school_id":
            conds.append(model.school_id == val)
        elif key == "class_id":
            conds.append(model.class_id == val)
        elif key == "status":
            conds.append(model.status == val)
        elif key == "date" and isinstance(val, dict):
            if "$gte" in val:
                conds.append(model.date >= _coerce_date(val["$gte"]))
            if "$lte" in val:
                conds.append(model.date <= _coerce_date(val["$lte"]))
            if "$lt" in val:
                conds.append(model.date < _coerce_date(val["$lt"]))
        elif key == "date":
            conds.append(model.date == _coerce_date(val))
    return conds


async def _att_count(session, filters: dict) -> int:
    from pg_models import Attendance as _A
    stmt = select(func.count()).select_from(_A)
    conds = _att_where(_A, filters)
    if conds:
        stmt = stmt.where(and_(*conds))
    result = await session.execute(stmt)
    return result.scalar() or 0


async def _att_distinct_days(session, filters: dict) -> set:
    """Return a set of distinct YYYY-MM-DD strings from the SQL attendance table."""
    from pg_models import Attendance as _A
    stmt = select(func.distinct(cast(_A.date, _SADate))).select_from(_A)
    conds = _att_where(_A, filters)
    if conds:
        stmt = stmt.where(and_(*conds))
    result = await session.execute(stmt)
    return {str(row[0]) for row in result.fetchall() if row[0]}


async def _att_find(session, filters: dict, order_by_date_desc: bool = False, limit: int = 500) -> list:
    """Query SQL attendance table; return list of dicts compatible with gd_find output."""
    from pg_models import Attendance as _A
    stmt = select(_A)
    conds = _att_where(_A, filters)
    if conds:
        stmt = stmt.where(and_(*conds))
    if order_by_date_desc:
        stmt = stmt.order_by(_A.date.desc())
    stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "student_id": r.student_id,
            "class_id": r.class_id,
            "school_id": r.school_id,
            "status": r.status,
            "date": r.date.isoformat() if r.date else None,
            "notes": r.notes,
            "is_excused": r.is_excused,
            "session_id": r.session_id,
        }
        for r in rows
    ]

# Narrow set of DB errors that indicate the optional legacy linkage
# surfaces (`guardian_links` join table, `parents.student_ids` array)
# are unreachable in this environment — typically a missing table /
# missing column / connection blip. We swallow these so the canonical
# `students.parent_id` resolution still works; everything else (auth,
# tenant scoping, programming bugs) bubbles up as before.
_LEGACY_LINKAGE_DB_ERRORS = (ProgrammingError, OperationalError)


# ---------------------------------------------------------------------------
# Parent schedule period normalization
# ---------------------------------------------------------------------------
# The parent timetable grid must render rows from a single canonical period
# source, place each session on its TRUE teaching-period row, and never pack
# sessions by array index. Sessions store `period_number`, but the encoding
# differs per timetable:
#   - GENERATOR timetables → contiguous period_number (1..N), slot_number null.
#   - MANUAL timetables     → raw slot_number (gapped, e.g. 1,2,3,5,6,7,9 when
#                             breaks occupy slots 4 and 8), start_time often "".
# `_build_parent_period_model` resolves the canonical period list and returns a
# mapper(raw_period) -> canonical 1..N index (or None to clamp out sessions
# that are not part of the base timetable: break slots, orphans, nulls).
# Resolution order: teaching time_slots → school_settings.periods_per_day →
# distinct session periods (legacy fallback). It is a pure function so it can be
# unit-tested without a DB.

def _build_parent_period_model(teaching_slots, periods_per_day, session_periods,
                               sessions_have_times=False):
    """Return (periods, mapper) for the parent schedule grid.

    ``periods``  -> ordered list of {period, label, start_time, end_time} where
                    ``period`` is the canonical contiguous teaching index 1..N.
    ``mapper``   -> callable(raw_period:int|None) -> canonical period int | None.
                    Returns None for sessions that do not belong to the base
                    timetable (break slots, orphans beyond N, null periods).

    ``teaching_slots`` must already exclude breaks; it may be unordered.
    ``sessions_have_times`` is the structural tie-breaker used only when the
    session period values themselves give no raw-vs-contiguous evidence:
    manual timetables store empty ``start_time`` (raw-slot encoding) while
    generator timetables carry real slot times (contiguous encoding).
    """
    clean_periods = [p for p in (session_periods or []) if isinstance(p, int)]

    # 1) Canonical teaching slots from time_slots.
    slots = []
    for s in (teaching_slots or []):
        try:
            sn = int(s.get("slot_number"))
        except (TypeError, ValueError):
            continue
        slots.append((sn, s))
    if slots:
        slots.sort(key=lambda x: (x[0], str(x[1].get("start_time") or "")))
        raw_numbers = [sn for sn, _ in slots]
        n = len(slots)
        contiguous = list(range(1, n + 1))
        raw_to_index = {sn: i + 1 for i, (sn, _) in enumerate(slots)}
        periods = [
            {
                "period": i + 1,
                "label": str(i + 1),
                "start_time": s.get("start_time") or "",
                "end_time": s.get("end_time") or "",
            }
            for i, (_, s) in enumerate(slots)
        ]

        if raw_numbers == contiguous:
            # No break gaps → slot numbers already are the teaching index.
            def mapper(p):
                return p if isinstance(p, int) and 1 <= p <= n else None
            return periods, mapper

        # Gapped slot numbers → decide whether sessions use the raw-slot
        # (manual) or contiguous (generator) encoding. Prefer hard evidence
        # from the period values themselves: a period that only exists in the
        # raw-slot set (e.g. 9 when N=7) proves raw; one that only exists in the
        # contiguous set (e.g. 4 when slot 4 is a break) proves contiguous.
        raw_only = set(raw_numbers) - set(contiguous)
        contig_only = set(contiguous) - set(raw_numbers)
        n_raw = sum(1 for p in clean_periods if p in raw_only)
        n_contig = sum(1 for p in clean_periods if p in contig_only)
        if n_raw != n_contig:
            use_raw = n_raw > n_contig
        else:
            # No distinguishing period-value evidence (every session falls in
            # the set shared by both encodings). Fall back to the structural
            # signal rather than blindly assuming raw: generator timetables
            # carry slot times, manual ones do not. Choosing contiguous here
            # also never drops a session (every value is <= N); it only changes
            # which true row it lands on.
            use_raw = not sessions_have_times
        if use_raw:
            def mapper(p):  # raw-slot encoding
                return raw_to_index.get(p) if isinstance(p, int) else None
        else:
            def mapper(p):  # contiguous encoding
                return p if isinstance(p, int) and 1 <= p <= n else None
        return periods, mapper

    # 2) school_settings.periods_per_day → contiguous 1..N (no times).
    try:
        ppd = int(periods_per_day) if periods_per_day is not None else 0
    except (TypeError, ValueError):
        ppd = 0
    if ppd > 0:
        periods = [
            {"period": i + 1, "label": str(i + 1), "start_time": "", "end_time": ""}
            for i in range(ppd)
        ]

        def mapper(p):
            return p if isinstance(p, int) and 1 <= p <= ppd else None
        return periods, mapper

    # 3) Legacy fallback: re-index the distinct session periods to 1..N so
    #    nothing is dropped when a school has no configured period structure.
    distinct = sorted(set(clean_periods))
    if distinct:
        raw_to_index = {raw: i + 1 for i, raw in enumerate(distinct)}
        periods = [
            {"period": i + 1, "label": str(i + 1), "start_time": "", "end_time": ""}
            for i in range(len(distinct))
        ]

        def mapper(p):
            return raw_to_index.get(p) if isinstance(p, int) else None
        return periods, mapper

    return [], (lambda p: None)


async def _resolve_parent_period_model(session, school_id, session_periods,
                                       sessions_have_times=False):
    """Async wrapper: fetch the period config for ``school_id`` then build the
    canonical period model via :func:`_build_parent_period_model`."""
    teaching_slots = []
    periods_per_day = None
    try:
        slots = await gd_find(session, "time_slots", {"school_id": school_id}, limit=200)
        for s in slots or []:
            if s.get("is_break"):
                continue
            if s.get("is_active") is False:
                continue
            teaching_slots.append(s)
    except Exception as err:  # pragma: no cover - defensive
        logger.warning("parent schedule: time_slots resolve failed for %s: %s", school_id, err)
    if not teaching_slots:
        try:
            settings = await gd_find_one(session, "school_settings", {"school_id": school_id})
            if settings:
                periods_per_day = settings.get("periods_per_day")
        except Exception as err:  # pragma: no cover - defensive
            logger.warning("parent schedule: settings resolve failed for %s: %s", school_id, err)
    return _build_parent_period_model(
        teaching_slots, periods_per_day, session_periods, sessions_have_times
    )


def _norm_hhmm(value) -> str:
    """Normalize a clock string to zero-padded ``HH:MM``.

    Manual timetable sessions can carry non-padded times (e.g. ``"9:00"``),
    which break the lexicographic ``start <= now < end`` comparisons that drive
    the live "where is my child now" widget. Returns ``""`` when the value is
    missing or unparseable so callers fall back to the canonical slot time.
    """
    text = str(value or "").strip()
    if not text:
        return ""
    parts = text.split(":")
    if len(parts) < 2:
        return ""
    try:
        hh = int(parts[0])
        mm = int(parts[1])
    except (TypeError, ValueError):
        return ""
    return f"{hh:02d}:{mm:02d}"


async def _resolve_class_today_sessions(session, school_id, class_id, today_en):
    """Resolve a class's sessions for ``today_en`` with canonical period times.

    Single source of truth for the parent "where is my child now" widget. It
    mirrors the weekly schedule grid's canonical resolution
    (:func:`_resolve_parent_period_model`) so the home widget and the schedule
    page never disagree about when a lesson runs.

    Manual timetables store sessions with EMPTY ``start_time``/``end_time``
    (raw-slot encoding). Reading those fields directly makes every session look
    time-less, which collapsed the live widget into a perpetual "school day
    ended / not started". Resolving times from the canonical period model — the
    school's ``time_slots`` layout — fixes that.

    Returns an ordered list of dicts:
        {period, raw_period, subject_id, teacher_id, start_time, end_time}
    """
    if not class_id or not today_en:
        return []

    # Independent-Teacher synthetic workspaces (spec §5.4) store their grid
    # directly in `schedule_sessions` (status="scheduled", short day codes,
    # empty start/end times) with NO timetables/timetable_sessions parent —
    # the modern-engine read below would always return []. Mirror the IT
    # teacher-schedule reader: slot_number IS the period, times come from the
    # workspace period config clock.
    if is_independent_workspace_id(school_id):
        rows = await gd_find(session, "schedule_sessions", {
            "school_id": school_id,
            "class_id": class_id,
            "status": "scheduled",
        }, limit=500)
        settings = await gd_find_one(session, "school_settings", {"school_id": school_id}) or {}
        slot_times = compute_it_slot_times(settings)
        resolved = []
        seen = set()
        for r in rows:
            if normalize_it_day(r.get("day_of_week")) != today_en:
                continue
            try:
                slot_int = int(r.get("slot_number"))
            except (TypeError, ValueError):
                continue
            if slot_int in seen:  # stale duplicate row can't double up
                continue
            seen.add(slot_int)
            slot_start, slot_end = slot_times.get(slot_int, ("", ""))
            resolved.append({
                "period": slot_int,
                "raw_period": slot_int,
                "subject_id": r.get("subject_id"),
                "teacher_id": r.get("teacher_id"),
                # Denormalised names ride along so the today-live widget can
                # fall back to them when the teachers/subjects lookup misses.
                "subject_name": r.get("subject_name") or "",
                "teacher_name": r.get("teacher_name") or "",
                "start_time": _norm_hhmm(slot_start),
                "end_time": _norm_hhmm(slot_end),
            })
        resolved.sort(key=lambda x: (x.get("period") or 0))
        return resolved

    timetable = await gd_find_one(session, "timetables", {
        "school_id": school_id,
        "status": "published",
    }) or await gd_find_one(session, "timetables", {
        "school_id": school_id,
    }, sort=[("created_at", -1)])
    if not timetable:
        return []

    all_sessions = await gd_find(session, "timetable_sessions", {
        "timetable_id": timetable.get("id"),
        "class_id": class_id,
    }, limit=500)
    if not all_sessions:
        return []

    raw_session_periods = []
    for s in all_sessions:
        try:
            raw_session_periods.append(int(s.get("period_number")))
        except (TypeError, ValueError):
            continue
    sessions_have_times = any(
        str(s.get("start_time") or "").strip() for s in all_sessions
    )

    periods, mapper = await _resolve_parent_period_model(
        session, school_id, raw_session_periods, sessions_have_times
    )
    period_times = {
        p["period"]: (p.get("start_time") or "", p.get("end_time") or "")
        for p in periods
    }

    resolved = []
    for s in all_sessions:
        if s.get("day_of_week") != today_en:
            continue
        try:
            raw_period = int(s.get("period_number"))
        except (TypeError, ValueError):
            raw_period = None
        canonical = mapper(raw_period) if raw_period is not None else None
        if canonical is None:
            continue
        slot_start, slot_end = period_times.get(canonical, ("", ""))
        resolved.append({
            "period": canonical,
            "raw_period": raw_period,
            "subject_id": s.get("subject_id"),
            "teacher_id": s.get("teacher_id"),
            # Modern-engine rows may also carry denormalised names (written by
            # the manual timetable editor). Carry them the same way the IT
            # branch does so the caller can fall back to them when the
            # subjects/teachers lookup misses (deleted or dangling id).
            "subject_name": s.get("subject_name") or "",
            "teacher_name": s.get("teacher_name") or "",
            "start_time": _norm_hhmm(s.get("start_time")) or _norm_hhmm(slot_start),
            "end_time": _norm_hhmm(s.get("end_time")) or _norm_hhmm(slot_end),
        })
    resolved.sort(key=lambda x: (x.get("period") or 0))
    return resolved


async def _merged_homework_counts(session, child: dict, school_id,
                                  week_start: str = None, week_end: str = None):
    """Merged homework (done, total) across BOTH homework data models.

    Homework lives in two disjoint stores that any summary metric must merge
    (the الواجبات tab already does — see get_child_homework):
      1. Digital assignments: `student_assignments` posts (class/grade scoped)
         paired with `assignment_submissions` by the student.
      2. Lesson-recorded homework: `session_homework` rows the teacher marks
         during a live lesson ("سلم"/"لم يسلم", status done/not_done).

    Counting only the digital model made the cumulative analytics show 0%
    for lesson-only schools while the homework tab showed real submissions.

    `session_homework` has no school_id column, so each lesson row is only
    counted when its session resolves to a `class_sessions` row in the
    caller's tenant (same fail-closed rule as the homework tab).

    Optional week bounds (ISO date strings) scope digital assignments by
    due_date and lesson homework by the session date.
    """
    child_id = child.get("id")
    child_school = child.get("school_id") or school_id
    class_id = child.get("class_id")
    grade_id = child.get("grade_id") or child.get("grade")

    done = 0
    total = 0

    # ── Digital assignments (same scoping as the الواجبات tab) ────────────
    query = {"school_id": child_school, "is_active": True}
    if class_id:
        query["$or"] = [
            {"class_ids": class_id},
            {"class_id": class_id},
            {"grade_id": grade_id},
        ]
    if week_start and week_end:
        query["due_date"] = {"$gte": week_start, "$lte": week_end}
    assignments = await gd_find(session, "student_assignments", query, limit=200)
    if assignments:
        submissions = await gd_find(
            session, "assignment_submissions", {"student_id": child_id}, limit=500
        )
        submitted_ids = {s.get("assignment_id") for s in submissions}
        total += len(assignments)
        done += sum(1 for a in assignments if a.get("id") in submitted_ids)

    # ── Lesson-recorded homework (teacher follow-up sheet) ────────────────
    lesson_hw = await gd_find(
        session, "session_homework", {"student_id": child_id}, limit=500
    )
    lesson_hw = [h for h in lesson_hw if h.get("status") in ("done", "not_done")]
    if lesson_hw:
        sess_ids = list({h.get("session_id") for h in lesson_hw if h.get("session_id")})
        sess_rows = await gd_find(
            session, "class_sessions", {"id": {"$in": sess_ids}}, limit=len(sess_ids)
        ) if sess_ids else []
        sess_map = {s.get("id"): s for s in sess_rows}
        for h in lesson_hw:
            sess = sess_map.get(h.get("session_id"))
            # Fail closed: unresolvable session = tenant unprovable.
            if not sess:
                continue
            sess_school = sess.get("school_id") or sess.get("tenant_id")
            if sess_school and child_school and sess_school != child_school:
                continue
            if week_start and week_end:
                sess_date = str(sess.get("date") or h.get("recorded_at") or "")[:10]
                if not (week_start[:10] <= sess_date <= week_end[:10]):
                    continue
            total += 1
            if h.get("status") == "done":
                done += 1

    return done, total


# Session rows in these states describe a lesson that is NOT taking place, so
# they must never be the reason a teacher becomes messageable.
_INACTIVE_SESSION_STATUSES = {"cancelled", "canceled", "deleted", "removed", "archived"}


def _teacher_user_in_tenant(user: dict, school_id: str) -> bool:
    """Is this ``users`` row an acceptable recipient for ``school_id``?

    The tenant proof for a teacher is the school-pinned ``teachers`` row, not
    the nullable ``users.tenant_id`` column: legacy teacher accounts were
    provisioned without a tenant and were silently dropped from the parent's
    recipient list even though they teach the child every week. A user row
    that carries a DIFFERENT tenant is still rejected (fail closed).
    """
    if not user:
        return False
    user_tenant = user.get("tenant_id")
    return not user_tenant or user_tenant == school_id


def _active_schedule_sessions(rows: list) -> list:
    """Drop ``schedule_sessions`` rows that describe a lesson which is not
    taking place (cancelled/deleted); a cancelled period must never be the
    reason a teacher becomes messageable.

    Deliberately does NOT try to pick a single "current" ``schedule_id`` per
    class: independent-teacher workspaces store legitimate week-specific
    schedule generations side by side, so a newest-generation-wins rule would
    hide a teacher who only teaches that class in another week. The legacy
    ``schedules`` parent collection carries no status to anchor on either.
    """
    return [
        r for r in rows
        if str(r.get("status") or "").strip().lower() not in _INACTIVE_SESSION_STATUSES
    ]


def setup_parent_portal_routes(db, get_current_user, require_roles, UserRole):
    """Setup parent portal routes"""

    router = APIRouter(prefix="/parent-portal", tags=["Parent Portal"])

    @router.post("/accept-charter")
    async def accept_parent_charter(
        current_user: dict = Depends(require_roles([UserRole.PARENT])),
    ):
        """Mark the authenticated parent as having accepted the mandatory
        ميثاق ولي الأمر. The FE CharterGuard blocks every /parent/* route
        until ``charter_accepted_at`` is non-NULL, so this is the single
        gateway out of the blocking modal. Idempotent — re-accepting
        keeps the original acceptance timestamp."""
        user_id = current_user.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="غير مصرح")

        now = datetime.now(timezone.utc)
        # Atomic "set only if currently NULL" so two concurrent accept
        # requests cannot overwrite the original acceptance timestamp.
        await gd_update_one(
            db.session, "users",
            {"id": user_id, "charter_accepted_at": None},
            {"$set": {"charter_accepted_at": now}},
        )

        # Re-read so we return whatever value is actually persisted —
        # either ``now`` (we won the race / first acceptance) or the
        # previously stored timestamp (idempotent re-accept).
        existing = await gd_find_one(db.session, "users", {"id": user_id})
        if not existing:
            raise HTTPException(status_code=404, detail="المستخدم غير موجود")

        accepted_at = existing.get("charter_accepted_at") or now
        if isinstance(accepted_at, datetime):
            iso = accepted_at.isoformat()
        else:
            iso = str(accepted_at)

        return {
            "success": True,
            "charter_accepted_at": iso,
            "message": "تم قبول الميثاق",
        }

    def _parent_or_conditions(parent_user_id: str, parent_phone: Optional[str] = None, parent_record_id: Optional[str] = None, parent_email: Optional[str] = None) -> list:
        """Build an $or list that matches students based solely on canonical
        parent identifiers (user.id / parents.id).  Mutable contact fields
        such as phone and email are intentionally excluded because they can be
        changed by the authenticated user and must not be used as an
        authorization key.
        """
        conditions = []
        seen = set()
        for pid in (parent_user_id, parent_record_id):
            if pid and pid not in seen:
                conditions.append({"parent_id": pid})
                conditions.append({"parent_user_id": pid})
                seen.add(pid)
        return conditions

    def _parent_refs(current_user: dict) -> List[str]:
        """Return all identifiers that may have been used as a parent link: user.id
        and parents.id (if resolvable)."""
        refs = []
        uid = current_user.get("id")
        pid = current_user.get("parent_id")
        if uid:
            refs.append(uid)
        if pid and pid != uid:
            refs.append(pid)
        return refs

    async def _get_linked_student_ids(current_user: dict, school_id: Optional[str] = None) -> List[str]:
        """Resolve extra student ids via the non-canonical linkage paths
        (`guardian_links` join table and `parents.student_ids` array).

        Both paths are best-effort and MUST fail safe: the canonical
        `students.parent_id` resolution in `_find_children` is the primary
        source of truth, and a missing/empty join table or a malformed
        parent record must not 500 the parent dashboard. Each lookup is
        isolated so one broken path does not poison the other.
        """
        refs = _parent_refs(current_user)
        if not refs:
            return []
        student_ids: set = set()

        # Path A: guardian_links (preferred when present). Tolerate the
        # table being absent in environments that never installed it —
        # those installs rely entirely on parents.student_ids and the
        # canonical students.parent_id back-reference.
        query = {"parent_ref": {"$in": refs}, "is_active": True}
        if school_id:
            query["tenant_id"] = school_id
        try:
            links = await gd_find(db.session, "guardian_links", query, limit=50)
            for link in links:
                sid = link.get("student_id")
                if sid:
                    student_ids.add(sid)
        except _LEGACY_LINKAGE_DB_ERRORS as exc:
            logger.debug("guardian_links lookup degraded for parent %s: %s",
                         current_user.get("id"), exc)

        # Path B: parents.student_ids array on the parent record.
        parent_record_id = current_user.get("parent_id")
        if parent_record_id:
            try:
                parent_rec = await gd_find_one(db.session, "parents", {"id": parent_record_id})
                if parent_rec and isinstance(parent_rec.get("student_ids"), list):
                    for sid in parent_rec["student_ids"]:
                        if sid:
                            student_ids.add(sid)
            except _LEGACY_LINKAGE_DB_ERRORS as exc:
                logger.debug("parents.student_ids lookup degraded for parent %s: %s",
                             current_user.get("id"), exc)

        return list(student_ids)

    async def _find_children(current_user_or_id, parent_phone: Optional[str] = None, school_id: Optional[str] = None):
        """Back-compat signature: accepts either a full user dict or a user id
        followed by parent_phone/school_id. Delegates to the shared
        canonical resolver in `utils.parent_children_resolution` so the
        parent portal and the Hakim assistant always see the same
        allow-list of children."""
        if isinstance(current_user_or_id, dict):
            current_user = current_user_or_id
            school_id = school_id or current_user.get("tenant_id")
        else:
            current_user = {"id": current_user_or_id, "phone": parent_phone, "tenant_id": school_id}

        from src.common.utils.parent_children_resolution import resolve_parent_children
        return await resolve_parent_children(
            current_user,
            school_id,
            allow_cross_school_guardian_links=True,
        )

    async def _enrich_children_for_their_schools(
        children: List[dict],
        fallback_school_id: Optional[str],
    ) -> List[dict]:
        """Enrich mixed-school children without dropping foreign classes.

        A reused parent account may legitimately have children in more than
        one school.  ``enrich_children_with_class_names`` intentionally pins
        each classes query to one school, so call it once per child's
        effective school rather than passing the parent's historical tenant
        for the entire list.
        """
        from src.common.utils.parent_children_resolution import enrich_children_with_class_names

        by_school: dict[str, List[dict]] = {}
        for child in children:
            child_school_id = child.get("school_id") or fallback_school_id
            if not child_school_id:
                # A student without a school cannot be enriched safely; leave
                # its denormalized class_name untouched rather than issuing an
                # unscoped classes query.
                continue
            by_school.setdefault(child_school_id, []).append(child)
        for child_school_id, school_children in by_school.items():
            await enrich_children_with_class_names(
                school_children,
                db.session,
                child_school_id,
            )
        return children

    # ============= DASHBOARD =============

    @router.get("/dashboard")
    async def get_parent_dashboard(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """لوحة تحكم ولي الأمر"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")

        children = await _find_children(current_user, parent_phone, school_id)

        children = await _enrich_children_for_their_schools(children, school_id)

        # ------------------------------------------------------------------
        # Batched enrichment (was a textbook N+1: per child ~5-6 queries —
        # distinct-days + present/late counts + recent grades + all grades +
        # school lookup). Replaced with a fixed handful of set-based queries
        # whose semantics mirror the per-child helpers exactly.
        # ------------------------------------------------------------------
        # Resolve each child's effective school id once; the class-level path
        # requires BOTH class_id and school_id (mirrors the old `if` branch).
        _child_school = {
            c.get("id"): (c.get("school_id") or school_id) for c in children
        }
        # (school_id, class_id) pairs whose distinct-day denominator we need.
        _class_pairs = sorted({
            (_child_school[c.get("id")], c.get("class_id"))
            for c in children
            if c.get("class_id") and _child_school[c.get("id")]
        })
        # (school_id, student_id) that use the no-class fallback branch.
        _fallback_children = [
            c for c in children
            if not (c.get("class_id") and _child_school[c.get("id")])
        ]

        # (1) Distinct teaching-day count per (school_id, class_id) — the
        #     class-level denominator, cast(date AS date) DISTINCT, mirroring
        #     _att_distinct_days scoped by {school_id, class_id}.
        _distinct_days_by_pair: dict = {}
        if _class_pairs:
            _pair_school_ids = list({p[0] for p in _class_pairs})
            _pair_class_ids = list({p[1] for p in _class_pairs})
            _dd_rows = (await db.session.execute(
                sa_text(
                    "SELECT school_id, class_id, COUNT(DISTINCT date::date) AS cnt "
                    "FROM attendance "
                    "WHERE school_id IN :sids AND class_id IN :cids "
                    "GROUP BY school_id, class_id"
                ).bindparams(
                    bindparam("sids", expanding=True),
                    bindparam("cids", expanding=True),
                ),
                {"sids": _pair_school_ids, "cids": _pair_class_ids},
            )).all()
            _distinct_days_by_pair = {(r[0], r[1]): int(r[2]) for r in _dd_rows}

        # (2) present+late row counts per (school_id, class_id, student_id) for
        #     class-scoped children — mirrors the two _att_count(present)+
        #     _att_count(late) calls.
        _present_by_triple: dict = {}
        _class_child_ids = [
            c.get("id") for c in children
            if c.get("class_id") and _child_school[c.get("id")]
        ]
        if _class_child_ids:
            # Tenant scope: the old per-child helper filtered school_id AND
            # class_id explicitly — keep the query bounded to the children's
            # own (school, class) universe, never a bare student_id scan.
            _cc_school_ids = list({p[0] for p in _class_pairs})
            _cc_class_ids = list({p[1] for p in _class_pairs})
            _pl_rows = (await db.session.execute(
                sa_text(
                    "SELECT school_id, class_id, student_id, COUNT(id) AS cnt "
                    "FROM attendance "
                    "WHERE student_id IN :stids AND school_id IN :sids "
                    "AND class_id IN :cids AND status IN ('present','late') "
                    "GROUP BY school_id, class_id, student_id"
                ).bindparams(
                    bindparam("stids", expanding=True),
                    bindparam("sids", expanding=True),
                    bindparam("cids", expanding=True),
                ),
                {"stids": _class_child_ids, "sids": _cc_school_ids,
                 "cids": _cc_class_ids},
            )).all()
            _present_by_triple = {(r[0], r[1], r[2]): int(r[3]) for r in _pl_rows}

        # (3) Fallback branch (no class): total rows per (school_id, student_id)
        #     and present+late per (school_id, student_id).
        _fb_total_by_pair: dict = {}
        _fb_present_by_pair: dict = {}
        if _fallback_children:
            _fb_ids = [c.get("id") for c in _fallback_children]
            # Tenant scope: the old per-child helper filtered school_id too.
            _fb_school_ids = list({
                _child_school[c.get("id")] for c in _fallback_children
                if _child_school[c.get("id")]
            }) or [school_id]
            _fb_total_rows = (await db.session.execute(
                sa_text(
                    "SELECT school_id, student_id, COUNT(id) AS cnt "
                    "FROM attendance "
                    "WHERE student_id IN :stids AND school_id IN :sids "
                    "GROUP BY school_id, student_id"
                ).bindparams(
                    bindparam("stids", expanding=True),
                    bindparam("sids", expanding=True),
                ),
                {"stids": _fb_ids, "sids": _fb_school_ids},
            )).all()
            _fb_total_by_pair = {(r[0], r[1]): int(r[2]) for r in _fb_total_rows}
            _fb_present_rows = (await db.session.execute(
                sa_text(
                    "SELECT school_id, student_id, COUNT(id) AS cnt "
                    "FROM attendance "
                    "WHERE student_id IN :stids AND school_id IN :sids "
                    "AND status IN ('present','late') "
                    "GROUP BY school_id, student_id"
                ).bindparams(
                    bindparam("stids", expanding=True),
                    bindparam("sids", expanding=True),
                ),
                {"stids": _fb_ids, "sids": _fb_school_ids},
            )).all()
            _fb_present_by_pair = {(r[0], r[1]): int(r[2]) for r in _fb_present_rows}

        # (4) One grades fetch for ALL children, split in memory. `grades`
        #     lives in generic_documents; gd_find supports {"$in": ids}.
        _all_child_ids = [c.get("id") for c in children if c.get("id")]
        _grades_by_child: dict = {}
        if _all_child_ids:
            _grades = await gd_find(
                db.session, "grades", {"student_id": {"$in": _all_child_ids}}, limit=500 * len(_all_child_ids)
            )
            for g in _grades:
                _grades_by_child.setdefault(g.get("student_id"), []).append(g)

        # (5) One schools fetch via $in for the school-name fallback.
        school_name_cache = {}
        _missing_school_ids = list({
            (c.get("school_id") or school_id)
            for c in children
            if not c.get("school_name") and (c.get("school_id") or school_id)
        })
        if _missing_school_ids:
            _school_docs = await gd_find(
                db.session, "schools", {"id": {"$in": _missing_school_ids}}, limit=len(_missing_school_ids)
            )
            _school_by_id = {s.get("id"): s for s in _school_docs}
            for sid in _missing_school_ids:
                s_doc = _school_by_id.get(sid)
                school_name_cache[sid] = s_doc.get("name") if s_doc else sid

        children_data = []
        for child in children:
            child_id = child.get("id")

            # Use class-level distinct dates as denominator (same pattern as
            # the new dashboard path lines 276-296 and detail endpoint 561-575).
            # Raw gd_count(student rows) == gd_count(present rows) when absent
            # students have no row → always 100%. Scope by school_id always.
            child_class_id = child.get("class_id")
            child_school_id = child.get("school_id") or school_id
            if child_class_id and child_school_id:
                total_days = _distinct_days_by_pair.get((child_school_id, child_class_id), 0)
                # Count present + late as "attended" (late = physically present,
                # just tardy). Consistent with the weekly-analysis formula (line 1557).
                present_days = _present_by_triple.get((child_school_id, child_class_id, child_id), 0)
            else:
                total_days = _fb_total_by_pair.get((child_school_id, child_id), 0)
                present_days = _fb_present_by_pair.get((child_school_id, child_id), 0)
            # Honest empty: no sessions → null, not invented 100%. (Audit 2026-05-10.)
            attendance_rate = (present_days / total_days * 100) if total_days > 0 else None

            _child_grades = _grades_by_child.get(child_id, [])
            # recent_grades: ORDER BY date DESC LIMIT 3 (mirrors gd_find).
            recent_grades = sorted(
                _child_grades, key=lambda g: g.get("date") or "", reverse=True
            )[:3]
            all_grades = _child_grades
            # Honest empty for academics too — no grades => null, not a fake 0%.
            avg_score = (sum(g.get("percentage", 0) for g in all_grades) / len(all_grades)) if all_grades else None

            child_school_name = child.get("school_name")
            if not child_school_name:
                sid = child.get("school_id") or school_id
                child_school_name = school_name_cache.get(sid, "")

            children_data.append({
                "id": child_id,
                "name": child.get("full_name"),
                "grade": child.get("grade_level") or child.get("grade"),
                "class_name": child.get("class_name"),
                "class_id": child.get("class_id"),
                "school_name": child_school_name,
                "profile_picture": child.get("profile_picture"),
                "attendance_rate": round(attendance_rate, 1) if attendance_rate is not None else None,
                "average_score": round(avg_score, 1) if avg_score is not None else None,
                "recent_grades": [
                    {
                        "subject": g.get("subject"),
                        "score": g.get("score"),
                        "max_score": g.get("max_score"),
                        "date": g.get("date")
                    }
                    for g in recent_grades
                ]
            })

        unread_notifications = await gd_count(db.session, "notifications", {
            "recipient_id": parent_id,
            "read_status": False
        })

        unread_messages = await gd_count(db.session, "messages", {
            "receiver_id": parent_id,
            "read_status": False
        })

        return {
            "parent": {
                "id": parent_id,
                "name": current_user.get("full_name"),
                "email": current_user.get("email"),
                "phone": parent_phone
            },
            "children": children_data,
            "children_count": len(children_data),
            "unread_notifications": unread_notifications,
            "unread_messages": unread_messages
        }

    # ============= CHILDREN LIST =============

    @router.get("/children")
    async def get_parent_children(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """قائمة أبناء ولي الأمر"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")

        students = await _find_children(current_user, parent_phone, school_id)

        students = await _enrich_children_for_their_schools(students, school_id)

        school_name_cache = {}
        children = []
        for s in students:
            child_id = s.get("id")

            # Root-cause fix: some UI paths (e.g. "mark all present") only
            # write DB rows for present students; absent students get no row.
            # Counting only this student's own rows makes denominator == present
            # count → always 100%. The correct denominator is the number of
            # distinct calendar dates the class had ANY attendance recorded
            # (i.e. how many days the teacher took attendance). We also scope
            # every query by school_id to prevent cross-tenant bleed-in.
            child_school_id = s.get("school_id") or school_id
            child_class_id = s.get("class_id")

            if child_class_id and child_school_id:
                distinct_days = len(await _att_distinct_days(
                    db.session,
                    {"school_id": child_school_id, "class_id": child_class_id},
                ))
                present_days = await _att_count(
                    db.session,
                    {"school_id": child_school_id, "class_id": child_class_id,
                     "student_id": child_id, "status": "present"},
                )
                att_rate = round((present_days / distinct_days * 100), 1) if distinct_days > 0 else None
            else:
                total_days = await _att_count(
                    db.session,
                    {"school_id": child_school_id, "student_id": child_id},
                )
                present_days = await _att_count(
                    db.session,
                    {"school_id": child_school_id, "student_id": child_id, "status": "present"},
                )
                att_rate = round((present_days / total_days * 100), 1) if total_days > 0 else None

            all_grades = await gd_find(db.session, "grades", {"student_id": child_id}, limit=500)
            avg_score = None
            if all_grades:
                avg_score = round(sum(g.get("percentage", 0) for g in all_grades) / len(all_grades), 1)

            child_school_name = s.get("school_name")
            if not child_school_name:
                sid = s.get("school_id") or school_id
                if sid and sid not in school_name_cache:
                    s_doc = await gd_find_one(db.session, "schools", {"id": sid})
                    school_name_cache[sid] = s_doc.get("name") if s_doc else sid
                child_school_name = school_name_cache.get(sid, "")

            # Task #277 — Independent-Teacher workspace context. When the
            # student lives in an `itw_{user_id}` workspace, surface the
            # owning teacher's display name + a flag so the parent FE can
            # swap school metadata for IT-context affordances. Falls back
            # silently if the user lookup misses.
            child_sid = s.get("school_id") or school_id
            is_it_ws = isinstance(child_sid, str) and child_sid.startswith("itw_")
            teacher_display_name = None
            if is_it_ws:
                owner_uid = child_sid[len("itw_"):]
                owner = await gd_find_one(db.session, "users", {"id": owner_uid}) if owner_uid else None
                teacher_display_name = (owner or {}).get("full_name") or None

            children.append({
                "id": child_id,
                "name": s.get("full_name", s.get("name", "")),
                "name_ar": s.get("full_name", ""),
                "grade": s.get("grade_level", s.get("grade", "")),
                "class_name": s.get("class_name", ""),
                "grade_id": s.get("grade_id"),
                "class_id": s.get("class_id"),
                "school_id": child_sid,
                "school_name": child_school_name,
                "is_independent_teacher_workspace": bool(is_it_ws),
                "teacher_display_name": teacher_display_name,
                "photo_url": s.get("photo_url", ""),
                "profile_picture": s.get("photo_url", s.get("profile_picture", "")),
                "attendance_rate": att_rate,
                "average_score": avg_score,
                "gender": s.get("gender", ""),
                # المواهب والمهارات — same fields the School-Admin profile
                # stores on the students row; parents see the identical
                # read-only values (is_gifted derivation mirrors the admin
                # serializer in academics_student_routes.py).
                "talents": s.get("talents") or [],
                "is_gifted": len(s.get("talents") or []) > 0 or bool(s.get("is_gifted")),
            })

        return {"children": children, "total": len(children)}

    # ============= CHILD DETAILS =============

    async def _verify_parent_access(parent_id: str, parent_phone: Optional[str], child_id: str, school_id: Optional[str] = None, *, current_user: Optional[dict] = None):
        # Keep list and by-id authorization on the same canonical resolver.
        # In particular, the resolver's narrowly validated
        # guardian_links.parent_ref exception is what permits a reused/global
        # parent account to reach a child in another school.
        resolver_user = current_user or {
            "id": parent_id,
            "phone": parent_phone,
            "role": "parent",
            "tenant_id": school_id,
        }
        from src.common.utils.parent_children_resolution import resolve_parent_children

        children = await resolve_parent_children(
            resolver_user,
            school_id,
            allow_cross_school_guardian_links=True,
        )
        return next(
            (child for child in children if child.get("id") == child_id),
            None,
        )

    @router.get("/child/{child_id}")
    async def get_child_details(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """تفاصيل الابن"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"), current_user=current_user)

        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        # Issue #30: enrich with live class name from classes table (stale denorm fix).
        from src.common.utils.parent_children_resolution import enrich_children_with_class_names
        [child] = await enrich_children_with_class_names([child], db.session, child.get("school_id") or current_user.get("tenant_id"))

        child_sid = child.get("school_id") or current_user.get("tenant_id")
        child_school_name = child.get("school_name")
        if not child_school_name and child_sid:
            s_doc = await gd_find_one(db.session, "schools", {"id": child_sid})
            child_school_name = s_doc.get("name") if s_doc else None

        # Task #277 — surface IT context so the parent FE swaps the school
        # label for the inviting teacher's workspace and hides school-only
        # surfaces (peer roster, principal contact, school events).
        is_it_ws = isinstance(child_sid, str) and child_sid.startswith("itw_")
        teacher_display_name = None
        if is_it_ws:
            owner_uid = child_sid[len("itw_"):]
            owner = await gd_find_one(db.session, "users", {"id": owner_uid})
            teacher_display_name = (owner or {}).get("full_name") or None

        return {
            "id": child.get("id"),
            "name": child.get("full_name"),
            "national_id": child.get("national_id"),
            "birth_date": child.get("date_of_birth"),
            "gender": child.get("gender"),
            "grade": child.get("grade_level"),
            "class_name": child.get("class_name"),
            "class_id": child.get("class_id"),
            "school_id": child_sid,
            "school_name": child_school_name,
            "is_independent_teacher_workspace": bool(is_it_ws),
            "teacher_display_name": teacher_display_name,
            "student_number": child.get("student_number"),
            "enrollment_date": child.get("enrollment_date"),
            "profile_picture": child.get("profile_picture"),
            # المواهب والمهارات — read-only mirror of the admin-managed fields.
            "talents": child.get("talents") or [],
            "is_gifted": len(child.get("talents") or []) > 0 or bool(child.get("is_gifted")),
        }

    # ============= CHILD GRADES =============

    @router.get("/child/{child_id}/grades")
    async def get_child_grades(
        child_id: str,
        subject: Optional[str] = None,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """درجات الابن"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"), current_user=current_user)

        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        query = {"student_id": child_id}
        school_id = current_user.get("tenant_id")
        if school_id:
            query["school_id"] = school_id
        if subject:
            query["$or"] = [
                {"subject": subject},
                {"subject_name": subject},
                {"subject_id": subject},
            ]

        grades = await gd_find(db.session, "grades", query, order_by="date", desc_order=True, limit=500)

        subjects_data = {}
        for grade in grades:
            subj = grade.get("subject_name") or grade.get("subject") or grade.get("subject_id") or "غير محدد"
            if subj not in subjects_data:
                subjects_data[subj] = {"subject": subj, "grades": [], "total_score": 0, "total_max": 0}

            subjects_data[subj]["grades"].append({
                "score": grade.get("score"),
                "max_score": grade.get("max_score"),
                "percentage": grade.get("percentage"),
                "assessment_type": grade.get("assessment_type"),
                "date": grade.get("date")
            })
            subjects_data[subj]["total_score"] += grade.get("score", 0)
            subjects_data[subj]["total_max"] += grade.get("max_score", 100)

        for subj in subjects_data:
            data = subjects_data[subj]
            data["average"] = round((data["total_score"] / data["total_max"]) * 100, 1) if data["total_max"] > 0 else 0

        total_grades = len(grades)
        # Return null (not 0) when there are no grades so the frontend can
        # distinguish "no data yet" from a genuine 0% score. (Mirrors the
        # honest-empty pattern used by the attendance and children endpoints.)
        overall_avg = (sum(g.get("percentage", 0) for g in grades) / total_grades) if total_grades > 0 else None

        return {
            "child_name": child.get("full_name"),
            "subjects": list(subjects_data.values()),
            "total_grades": total_grades,
            "overall_average": round(overall_avg, 1) if overall_avg is not None else None,
        }

    # ============= CHILD ATTENDANCE =============

    @router.get("/child/{child_id}/attendance")
    async def get_child_attendance(
        child_id: str,
        month: Optional[int] = None,
        year: Optional[int] = None,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """سجل حضور الابن"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"), current_user=current_user)

        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        # Scope queries by school_id to prevent cross-tenant bleed-in.
        child_school_id = child.get("school_id") or current_user.get("tenant_id")
        child_class_id = child.get("class_id")

        query = {"school_id": child_school_id, "student_id": child_id}

        date_filter = None
        if month and year:
            start_date = f"{year}-{month:02d}-01"
            if month == 12:
                end_date = f"{year + 1}-01-01"
            else:
                end_date = f"{year}-{month + 1:02d}-01"
            date_filter = {"$gte": start_date, "$lt": end_date}
            query["date"] = date_filter

        records = await _att_find(db.session, query, order_by_date_desc=True, limit=500)

        # Statistics — scope numerator to the student's current class so
        # cross-class history cannot make rate > 100%.
        if child_class_id:
            stat_records = [r for r in records if r.get("class_id") == child_class_id]
        else:
            stat_records = records

        present = sum(1 for r in stat_records if r.get("status") == "present")
        absent = sum(1 for r in stat_records if r.get("status") == "absent")
        late = sum(1 for r in stat_records if r.get("status") == "late")
        excused = sum(1 for r in stat_records if r.get("status") == "excused")

        # Denominator: class-level distinct calendar days so absent students
        # with no row still count toward the total.
        if child_class_id and child_school_id:
            class_date_q: dict = {"school_id": child_school_id, "class_id": child_class_id}
            if date_filter:
                class_date_q["date"] = date_filter
            total_days = len(await _att_distinct_days(db.session, class_date_q))
        else:
            total_days = len(records)

        return {
            "child_name": child.get("full_name"),
            "records": [
                {
                    "date": r.get("date"),
                    "status": r.get("status"),
                    "check_in_time": r.get("check_in_time"),
                    "check_out_time": r.get("check_out_time"),
                    "notes": r.get("notes")
                }
                for r in records
            ],
            "statistics": {
                "total_days": total_days,
                "present": present,
                "absent": absent,
                "late": late,
                "excused": excused,
                # Honest empty: no records => null, not a fake 100%.
                # Frontend renders a placeholder when null. (Audit 2026-05-10.)
                # Include late in the rate — a late student is physically at
                # school (consistent with weekly-analysis formula).
                "attendance_rate": round(((present + late) / total_days * 100), 1) if total_days > 0 else None
            }
        }

    # ============= CHILD SCHEDULE =============

    @router.get("/child/{child_id}/schedule")
    async def get_child_schedule(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """الجدول الدراسي للابن"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"), current_user=current_user)

        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        school_id = child.get("school_id")

        day_en_to_ar = {
            "sunday": "الأحد", "monday": "الاثنين", "tuesday": "الثلاثاء",
            "wednesday": "الأربعاء", "thursday": "الخميس",
            "friday": "الجمعة", "saturday": "السبت"
        }
        days_order = ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس"]
        schedule_by_day = {day: [] for day in days_order}
        periods: list = []

        # Independent-Teacher synthetic workspaces (spec §5.4) store the grid
        # directly in `schedule_sessions` (status="scheduled") with short day
        # codes ("sun"), slot_number as the period, denormalised
        # subject/teacher names and EMPTY start/end times — and never create a
        # timetables/timetable_sessions parent, so the modern-engine read
        # below always came back empty for IT children. Mirror the IT
        # teacher-schedule reader (`_resolve_it_teacher_sessions`): slot times
        # come from the workspace period-config clock, and weekend days
        # (IT teachers can schedule Saturday/Friday) are appended to the day
        # list only when sessions actually exist there.
        if child.get("class_id") and is_independent_workspace_id(school_id):
            rows = await gd_find(db.session, "schedule_sessions", {
                "school_id": school_id,
                "class_id": child.get("class_id"),
                "status": "scheduled",
            }, limit=500)

            settings = await gd_find_one(db.session, "school_settings", {"school_id": school_id}) or {}
            slot_times = compute_it_slot_times(settings)

            # Fallback names for rows missing the denormalised copy (no N+1).
            sub_ids = list({s.get("subject_id") for s in rows if s.get("subject_id")})
            subs = await gd_find(db.session, "subjects", {"id": {"$in": sub_ids}}, limit=100) if sub_ids else []
            sub_map = build_subject_name_map(subs)

            weekend_present = []  # ordered: friday then saturday, if used
            seen = set()
            max_slot = 0
            for r in rows:
                day_full = normalize_it_day(r.get("day_of_week"))
                day_ar = day_en_to_ar.get(day_full, "")
                if not day_ar:
                    continue
                try:
                    slot_int = int(r.get("slot_number"))
                except (TypeError, ValueError):
                    continue
                if (day_ar, slot_int) in seen:  # stale duplicate rows
                    continue
                seen.add((day_ar, slot_int))
                if day_ar not in schedule_by_day:
                    schedule_by_day[day_ar] = []
                    if day_ar not in weekend_present:
                        weekend_present.append(day_ar)
                max_slot = max(max_slot, slot_int)
                slot_start, slot_end = slot_times.get(slot_int, ("", ""))
                schedule_by_day[day_ar].append({
                    "period": slot_int,
                    "raw_period": slot_int,
                    "subject": r.get("subject_name") or sub_map.get(r.get("subject_id")) or "غير محدد",
                    # Denormalised name on the row is the primary source
                    # (written by the IT editor at save time).
                    "teacher": r.get("teacher_name") or "غير محدد",
                    "start_time": slot_start or "",
                    "end_time": slot_end or "",
                })

            # Weekend columns at the end, Friday before Saturday (matches the
            # IT teacher read page's _DAY_ORDER).
            for day_ar in ("الجمعة", "السبت"):
                if day_ar in weekend_present:
                    days_order.append(day_ar)

            # Canonical period rows for the grid view: the full workspace
            # period clock (same rows the IT teacher's own grid shows),
            # extended if a stored slot exceeds the configured count.
            n_periods = max(len(slot_times), max_slot)
            periods = [
                {
                    "period": i,
                    "label": str(i),
                    "start_time": (slot_times.get(i) or ("", ""))[0] or "",
                    "end_time": (slot_times.get(i) or ("", ""))[1] or "",
                }
                for i in range(1, n_periods + 1)
            ]
        elif child.get("class_id"):
            timetable = await gd_find_one(db.session, "timetables", {"school_id": school_id, "status": "published"}) or await gd_find_one(db.session, "timetables", {"school_id": school_id},
                sort=[("created_at", -1)])
            if timetable:
                all_sessions = await gd_find(db.session, "timetable_sessions", {
                        "timetable_id": timetable.get("id"),
                        "class_id": child.get("class_id")
                    }, limit=500)

                sub_ids = list(set(s.get("subject_id") for s in all_sessions if s.get("subject_id")))
                tch_ids = list(set(s.get("teacher_id") for s in all_sessions if s.get("teacher_id")))
                subs = await gd_find(db.session, "subjects", {"id": {"$in": sub_ids}}, limit=100)
                tchs = await gd_find(db.session, "teachers", {"id": {"$in": tch_ids}}, limit=100)
                sub_map = build_subject_name_map(subs)
                tch_map = {t["id"]: (t.get("full_name") or "") for t in tchs}

                # Resolve the canonical teaching-period model once, then place
                # every session on its TRUE period row (no array-index packing)
                # and clamp out sessions that are not part of the base timetable
                # (break slots, orphans beyond N, null periods).
                raw_session_periods = []
                for s in all_sessions:
                    try:
                        raw_session_periods.append(int(s.get("period_number")))
                    except (TypeError, ValueError):
                        continue
                # Structural tie-breaker for gapped schools: manual timetables
                # store empty start_time (raw-slot encoding) while generator
                # timetables carry real slot times (contiguous encoding).
                sessions_have_times = any(
                    str(s.get("start_time") or "").strip() for s in all_sessions
                )
                periods, period_mapper = await _resolve_parent_period_model(
                    db.session, school_id, raw_session_periods, sessions_have_times
                )
                period_times = {p["period"]: (p.get("start_time"), p.get("end_time")) for p in periods}

                for session in all_sessions:
                    day_ar = day_en_to_ar.get(session.get("day_of_week", ""), "")
                    if day_ar not in schedule_by_day:
                        continue
                    try:
                        raw_period = int(session.get("period_number"))
                    except (TypeError, ValueError):
                        raw_period = None
                    canonical = period_mapper(raw_period) if raw_period is not None else None
                    if canonical is None:
                        continue
                    slot_start, slot_end = period_times.get(canonical, ("", ""))
                    schedule_by_day[day_ar].append({
                        "period": canonical,
                        "raw_period": raw_period,
                        # Row-level denormalised names are the last resort
                        # before the placeholder: a session whose subject was
                        # deleted (dangling subject_id) still knows what it was.
                        "subject": (sub_map.get(session.get("subject_id"))
                                    or (session.get("subject_name") or "").strip()
                                    or "غير محدد"),
                        "teacher": (tch_map.get(session.get("teacher_id"))
                                    or (session.get("teacher_name") or "").strip()
                                    or "غير محدد"),
                        "start_time": session.get("start_time") or slot_start or "",
                        "end_time": session.get("end_time") or slot_end or ""
                    })

        for day in schedule_by_day:
            schedule_by_day[day] = sorted(schedule_by_day[day], key=lambda x: x.get("period", 0))

        return {
            "child_name": child.get("full_name"),
            "class_name": child.get("class_name"),
            "schedule": schedule_by_day,
            "days": days_order,
            "periods": periods
        }

    # ============= TODAY LIVE =============

    @router.get("/child/{child_id}/today-live")
    async def get_child_today_live(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, school_id, current_user=current_user)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        # Resolve the live class name from the classes table so the home-hero
        # tag shows the student's real current class. The raw students row has
        # no class_name column, so without this the hero would render a blank
        # class and only the bare grade number. Mirrors the enrichment already
        # applied by /child/{child_id} and the other parent-portal routes.
        from src.common.utils.parent_children_resolution import enrich_children_with_class_names
        [child] = await enrich_children_with_class_names(
            [child], db.session, child.get("school_id") or school_id
        )

        now = datetime.now(SAUDI_TZ)
        current_time = now.strftime("%H:%M")
        # Friday/Saturday included so IT-workspace children (whose teachers
        # can schedule weekend lessons) resolve a real "today"; real schools
        # simply have no sessions on those days → no_schedule, as before.
        day_map = {6: "sunday", 0: "monday", 1: "tuesday", 2: "wednesday",
                   3: "thursday", 4: "friday", 5: "saturday"}
        today_en = day_map.get(now.weekday(), "")

        resolved_today = await _resolve_class_today_sessions(
            db.session, child.get("school_id", school_id), child.get("class_id"), today_en
        )

        today_sessions = []
        if resolved_today:
            sub_ids = list({s.get("subject_id") for s in resolved_today if s.get("subject_id")})
            tch_ids = list({s.get("teacher_id") for s in resolved_today if s.get("teacher_id")})
            subs = await gd_find(db.session, "subjects", {"id": {"$in": sub_ids}}, limit=50) if sub_ids else []
            tchs = await gd_find(db.session, "teachers", {"id": {"$in": tch_ids}}, limit=50) if tch_ids else []
            sub_map = build_subject_name_map(subs)
            tch_map = {t["id"]: (t.get("full_name") or "") for t in tchs}

            for s in resolved_today:
                today_sessions.append({
                    "period": s.get("period"),
                    # IT rows carry denormalised names as a fallback when the
                    # subjects/teachers lookup misses.
                    "subject": sub_map.get(s.get("subject_id")) or s.get("subject_name") or "غير محدد",
                    "subject_id": s.get("subject_id"),
                    "teacher": tch_map.get(s.get("teacher_id")) or s.get("teacher_name") or "غير محدد",
                    "teacher_id": s.get("teacher_id"),
                    "start_time": s.get("start_time"),
                    "end_time": s.get("end_time"),
                })

        current_class = None
        upcoming_classes = []
        completed_count = 0
        for session in today_sessions:
            start = session.get("start_time", "")
            end = session.get("end_time", "")
            if start and end:
                if current_time >= end:
                    completed_count += 1
                elif start <= current_time < end:
                    current_class = {**session, "is_current": True}
                else:
                    upcoming_classes.append(session)

        # Day status drives the home "where is my child now" message so the
        # widget distinguishes before-school / in-class / break / after-school
        # instead of collapsing every non-active moment into "day ended".
        timed_sessions = [s for s in today_sessions if s.get("start_time") and s.get("end_time")]
        if not today_sessions:
            day_status = "no_schedule"
        elif not timed_sessions:
            # Sessions exist but the school has no resolvable period times — we
            # cannot place "now", so let the UI fall back to a neutral message.
            day_status = "unknown"
        elif current_class:
            day_status = "in_class"
        else:
            first_start = min(s["start_time"] for s in timed_sessions)
            last_end = max(s["end_time"] for s in timed_sessions)
            if current_time < first_start:
                day_status = "before_school"
            elif current_time >= last_end:
                day_status = "after_school"
            else:
                day_status = "break"

        today_date = now.date()
        days_offset = today_date.weekday() + 1 if today_date.weekday() != 6 else 0
        week_start = today_date - timedelta(days=days_offset)
        last_week_start = week_start - timedelta(days=7)
        last_week_end = week_start - timedelta(days=1)

        this_week_grades = await gd_find(db.session, "grades", {
            "student_id": child_id,
            "date": {"$gte": week_start.isoformat(), "$lte": today_date.isoformat()}
        }, limit=200)
        last_week_grades = await gd_find(db.session, "grades", {
            "student_id": child_id,
            "date": {"$gte": last_week_start.isoformat(), "$lte": last_week_end.isoformat()}
        }, limit=200)

        all_grades = await gd_find(db.session, "grades", {"student_id": child_id}, limit=500)
        overall_avg = round(sum(g.get("percentage", 0) for g in all_grades) / len(all_grades), 1) if all_grades else 0

        this_avg = round(sum(g.get("percentage", 0) for g in this_week_grades) / len(this_week_grades), 1) if this_week_grades else overall_avg
        last_avg = round(sum(g.get("percentage", 0) for g in last_week_grades) / len(last_week_grades), 1) if last_week_grades else this_avg
        trend = round(this_avg - last_avg, 1)

        if overall_avg >= 90:
            level = "ممتاز"
        elif overall_avg >= 80:
            level = "جيد جداً"
        elif overall_avg >= 70:
            level = "جيد ومستقر"
        elif overall_avg >= 60:
            level = "مقبول"
        else:
            level = "يحتاج تحسين"

        if trend > 2:
            phrase = "استمروا على هذا التقدم الرائع!"
        elif trend < -2:
            phrase = "لا تقلقوا، بالمتابعة سيتحسن الأداء"
        else:
            phrase = "أداء مستقر، واصلوا الدعم"

        child_school_name = child.get("school_name", "")
        if not child_school_name:
            sid = child.get("school_id") or school_id
            if sid:
                s_doc = await gd_find_one(db.session, "schools", {"id": sid})
                child_school_name = s_doc.get("name") if s_doc else ""

        # Task #277 — IT-workspace context for the parent home hero.
        child_sid = child.get("school_id") or school_id
        is_it_ws = isinstance(child_sid, str) and child_sid.startswith("itw_")
        teacher_display_name = None
        if is_it_ws:
            owner_uid = child_sid[len("itw_"):]
            owner = await gd_find_one(db.session, "users", {"id": owner_uid}) if owner_uid else None
            teacher_display_name = (owner or {}).get("full_name") or None

        return {
            "student": {
                "name": child.get("full_name"),
                "school_id": child_sid,
                "school_name": child_school_name,
                "grade_level": child.get("grade_level", child.get("grade", "")),
                "class_name": child.get("class_name", ""),
                "is_independent_teacher_workspace": bool(is_it_ws),
                "teacher_display_name": teacher_display_name,
            },
            "school_day": {
                "today": today_en,
                "total_periods": len(today_sessions),
                "completed_periods": completed_count,
                "remaining_periods": len(upcoming_classes) + (1 if current_class else 0),
                "all_sessions": today_sessions,
                # Sun–Thu are always school days (pre-existing behaviour).
                # Friday/Saturday only count as a school day when sessions
                # actually exist (IT workspaces can schedule weekend lessons);
                # real schools keep the weekend "outside school hours" caption.
                "is_school_day": (today_en not in ("friday", "saturday")) or bool(today_sessions),
                "server_time": current_time,
                "day_status": day_status,
            },
            "current_class": current_class,
            "upcoming_classes": upcoming_classes,
            "performance": {
                "level": level,
                "overall_average": overall_avg,
                "trend": trend,
                "trend_direction": "up" if trend > 2 else ("down" if trend < -2 else "stable"),
                "phrase": phrase,
            }
        }

    # ============= WEEKLY STORY =============

    def _rank_weekly_cards(signals: dict) -> list:
        """Build a small, ranked, UI-ready cards list from the weekly signals.

        Card schema: {kind, tone, icon, title_ar, value, metric}
          - kind:   participation | positive_behaviour | skill | strong_subject |
                    weak_subject | late | absent | homework_high | homework_low |
                    remedial
          - tone:   positive | concern | academic
          - icon:   stable lucide name the FE maps to a component
          - value:  optional short value (e.g. "92%", "3")
        Selection: at most 4 cards = top 2 positive + top 1 concern + top 1
        academic. Slots collapse upward when a tier is empty so we never pad
        with empty tiles. Returns [] when no usable signals exist.
        """
        positive: list = []
        concern: list = []
        academic: list = []

        participation = int(signals.get("participation_count") or 0)
        positive_b = int(signals.get("positive_behaviors") or 0)
        skills = signals.get("acquired_skills") or []
        strong = signals.get("strong_subjects") or []
        weak = signals.get("weak_subjects") or []
        remedial = signals.get("remedial_plans") or []
        late_count = int(signals.get("late_count") or 0)
        absent_count = int(signals.get("absent_count") or 0)
        hw_total = int(signals.get("homework_total") or 0)
        hw_done = int(signals.get("homework_done") or 0)
        hw_rate = round((hw_done / hw_total) * 100) if hw_total > 0 else None

        # ---- positive tier ----
        if participation >= 1:
            positive.append({
                "kind": "participation",
                "tone": "positive",
                "icon": "Star",
                "title_ar": f"شارك بفعالية في {participation} حصة" if participation > 1
                            else "شارك بفعالية في حصة واحدة",
                "value": str(participation),
                "metric": "participation_count",
            })
        if positive_b >= 1:
            positive.append({
                "kind": "positive_behaviour",
                "tone": "positive",
                "icon": "Award",
                "title_ar": f"حصل على {positive_b} ملاحظة إيجابية" if positive_b > 1
                            else "حصل على ملاحظة إيجابية",
                "value": str(positive_b),
                "metric": "positive_behaviors",
            })
        if skills:
            positive.append({
                "kind": "skill",
                "tone": "positive",
                "icon": "Sparkles",
                "title_ar": f"اكتسب مهارة: {skills[0]}",
                "value": None,
                "metric": "acquired_skills",
            })
        if hw_rate is not None and hw_rate >= 80:
            positive.append({
                "kind": "homework_high",
                "tone": "positive",
                "icon": "CheckCircle2",
                "title_ar": f"أتم {hw_rate}% من الواجبات",
                "value": f"{hw_rate}%",
                "metric": "homework_rate",
            })

        # ---- concern tier ----
        if late_count >= 1:
            concern.append({
                "kind": "late",
                "tone": "concern",
                "icon": "Clock",
                "title_ar": f"تأخر {late_count} مرات" if late_count > 1
                            else "تأخر مرة واحدة",
                "value": str(late_count),
                "metric": "late_count",
            })
        if absent_count >= 1:
            concern.append({
                "kind": "absent",
                "tone": "concern",
                "icon": "AlertCircle",
                "title_ar": f"تغيّب {absent_count} مرات" if absent_count > 1
                            else "تغيّب مرة واحدة",
                "value": str(absent_count),
                "metric": "absent_count",
            })
        if hw_rate is not None and hw_rate < 60:
            concern.append({
                "kind": "homework_low",
                "tone": "concern",
                "icon": "FileText",
                "title_ar": f"أتم {hw_rate}% فقط من الواجبات",
                "value": f"{hw_rate}%",
                "metric": "homework_rate",
            })
        if weak:
            w0 = weak[0]
            subj = w0.get("subject") if isinstance(w0, dict) else str(w0)
            avg = w0.get("average") if isinstance(w0, dict) else None
            concern.append({
                "kind": "weak_subject",
                "tone": "concern",
                "icon": "TrendingDown",
                "title_ar": f"يحتاج دعمًا في {subj}" + (f" ({avg}%)" if avg is not None else ""),
                "value": f"{avg}%" if avg is not None else None,
                "metric": "weak_subjects",
            })

        # ---- academic tier ----
        if strong:
            s0 = strong[0]
            subj = s0.get("subject") if isinstance(s0, dict) else str(s0)
            avg = s0.get("average") if isinstance(s0, dict) else None
            academic.append({
                "kind": "strong_subject",
                "tone": "academic",
                "icon": "GraduationCap",
                "title_ar": f"تميّز في {subj}" + (f" ({avg}%)" if avg is not None else ""),
                "value": f"{avg}%" if avg is not None else None,
                "metric": "strong_subjects",
            })
        if remedial:
            r0 = remedial[0]
            title = (r0.get("title") if isinstance(r0, dict) else str(r0)) or "خطة علاجية"
            academic.append({
                "kind": "remedial",
                "tone": "academic",
                "icon": "BookOpen",
                "title_ar": f"خطة علاجية: {title}",
                "value": None,
                "metric": "remedial_plans",
            })

        cards: list = []
        cards.extend(positive[:2])
        cards.extend(concern[:1])
        cards.extend(academic[:1])
        # Backfill if we have fewer than 4 and more available in any tier.
        if len(cards) < 4:
            extras = positive[2:] + concern[1:] + academic[1:]
            cards.extend(extras[: 4 - len(cards)])
        return cards[:4]

    async def _get_or_build_parent_weekly_insight(
        *,
        child_id: str,
        school_id: Optional[str],
        week_start: str,
        week_end: str,
        signals: dict,
        cards: Optional[list] = None,
    ) -> dict:
        """Return the Hakim-generated weekly story+tip envelope for a child.

        Status values:
          - "available"          → story + tip generated by Hakim (or served from this week's cache)
          - "insufficient_data"  → student has too few weekly signals; no LLM call, no fabrication
          - "unavailable"        → Hakim service is disabled or both attempts failed

        Cache key: ai_insights row with insight_type='parent_weekly_brief',
        entity_type='student', entity_id=child_id, school_id=school_id,
        and data.week_start matching the current Saudi week start.
        """
        # 1) Sufficiency gate — when the caller already ranked cards, defer
        #    to that decision (zero usable cards => insufficient data).
        #    Otherwise fall back to the legacy "≥2 of 5 raw signals" rule.
        if cards is not None:
            insufficient = len(cards) == 0
        else:
            signal_flags = [
                signals.get("participation_count", 0) > 0,
                signals.get("positive_behaviors", 0) > 0,
                bool(signals.get("strong_subjects")) or bool(signals.get("weak_subjects")),
                bool(signals.get("acquired_skills")),
                bool(signals.get("remedial_plans")),
            ]
            insufficient = sum(1 for f in signal_flags if f) < 2
        if insufficient:
            return {
                "status": "insufficient_data",
                "story": None,
                "tip": None,
                "generated_at": None,
                "week_start": week_start,
                "week_end": week_end,
            }

        # 2) Cache lookup (per child + per Saudi week)
        cached = None
        try:
            cached_row = await gd_find_one(db.session, "ai_insights", {
                "insight_type": "parent_weekly_brief",
                "entity_type": "student",
                "entity_id": child_id,
                "school_id": school_id,
            })
            if cached_row and isinstance(cached_row.get("data"), dict):
                if cached_row["data"].get("week_start") == week_start:
                    cached = cached_row["data"]
        except Exception as e:
            logger.debug(f"weekly_insight cache lookup failed: {e}")

        if cached and cached.get("story") and cached.get("tip"):
            return {
                "status": "available",
                "story": cached.get("story"),
                "tip": cached.get("tip"),
                "generated_at": cached.get("generated_at"),
                "week_start": week_start,
                "week_end": week_end,
                "from_cache": True,
            }

        # 3) Real Hakim generation — story + tip
        try:
            from services.hakim_llm_service import hakim_generate, is_available as hakim_available
        except Exception as e:
            logger.warning(f"hakim_llm_service import failed: {e}")
            return {
                "status": "unavailable",
                "story": None,
                "tip": None,
                "generated_at": None,
                "week_start": week_start,
                "week_end": week_end,
            }

        if not hakim_available():
            return {
                "status": "unavailable",
                "story": None,
                "tip": None,
                "generated_at": None,
                "week_start": week_start,
                "week_end": week_end,
            }

        ctx = {
            "week_start": week_start,
            "week_end": week_end,
            "grade_level": signals.get("grade_level") or "",
            "participation_count": signals.get("participation_count", 0),
            "positive_behaviors": signals.get("positive_behaviors", 0),
            "acquired_skills": signals.get("acquired_skills") or [],
            "strong_subjects": signals.get("strong_subjects") or [],
            "weak_subjects": signals.get("weak_subjects") or [],
            "remedial_plans": [
                f"{p.get('title','')} ({p.get('subject','')})".strip(" ()")
                for p in (signals.get("remedial_plans") or [])
            ],
        }

        # Tip context is intentionally tighter than the story context: the
        # advice card must be tied to the ranked headline metrics shown to
        # the parent, never to raw teacher notes or unbounded extras. We
        # pass only the short title strings of the chosen cards.
        tip_ctx = {
            "week_start": week_start,
            "week_end": week_end,
            "grade_level": signals.get("grade_level") or "",
            "acquired_skills": [
                c.get("title_ar") for c in (cards or [])
                if isinstance(c, dict) and c.get("title_ar")
            ],
        }

        # Wrap LLM calls so any unexpected exception fails closed to a
        # structured "unavailable" status rather than bubbling a 500.
        try:
            story_res = await hakim_generate(
                mode="generate", field="parent_weekly_story",
                text="", context=ctx, language="ar", tone="educational",
                tenant_id=school_id,
            )
            tip_res = await hakim_generate(
                mode="generate", field="parent_weekly_tip",
                text="", context=(tip_ctx if cards else ctx),
                language="ar", tone="educational",
                tenant_id=school_id,
            )
        except Exception as e:
            logger.warning(f"weekly_insight hakim_generate raised: {e}")
            return {
                "status": "unavailable",
                "story": None,
                "tip": None,
                "generated_at": None,
                "week_start": week_start,
                "week_end": week_end,
            }

        story_ok = bool(story_res.get("success")) and bool(story_res.get("text"))
        tip_ok = bool(tip_res.get("success")) and bool(tip_res.get("text"))
        if not (story_ok and tip_ok):
            return {
                "status": "unavailable",
                "story": None,
                "tip": None,
                "generated_at": None,
                "week_start": week_start,
                "week_end": week_end,
            }

        generated_at = datetime.now(timezone.utc).isoformat()
        payload_data = {
            "story": story_res["text"],
            "tip": tip_res["text"],
            "generated_at": generated_at,
            "week_start": week_start,
            "week_end": week_end,
            "model": story_res.get("model"),
        }

        # 4) Upsert cache row (best-effort; never fail the request on cache write)
        try:
            existing = await gd_find_one(db.session, "ai_insights", {
                "insight_type": "parent_weekly_brief",
                "entity_type": "student",
                "entity_id": child_id,
                "school_id": school_id,
            })
            if existing:
                await gd_update_one(db.session, "ai_insights", {
                    "insight_type": "parent_weekly_brief",
                    "entity_type": "student",
                    "entity_id": child_id,
                    "school_id": school_id,
                }, {"data": payload_data})
            else:
                await gd_insert(db.session, "ai_insights", {
                    "id": str(uuid.uuid4()),
                    "school_id": school_id,
                    "entity_type": "student",
                    "entity_id": child_id,
                    "insight_type": "parent_weekly_brief",
                    "title": "قصة الأسبوع",
                    "content": payload_data["story"][:500],
                    "data": payload_data,
                    "severity": "info",
                    "is_actionable": False,
                })
        except Exception as e:
            logger.debug(f"weekly_insight cache write failed: {e}")

        return {
            "status": "available",
            "story": payload_data["story"],
            "tip": payload_data["tip"],
            "generated_at": generated_at,
            "week_start": week_start,
            "week_end": week_end,
            "from_cache": False,
        }

    @router.get("/child/{child_id}/weekly-story")
    async def get_child_weekly_story(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, school_id, current_user=current_user)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        now = datetime.now(SAUDI_TZ)
        today = now.date()
        days_since_saturday = (today.weekday() + 2) % 7
        week_start = today - timedelta(days=days_since_saturday)
        week_end = week_start + timedelta(days=5)

        # Tenant scoping: enforce school_id on every weekly signal query so a
        # parent can never see data outside their tenant, even on UUID collision.
        tenant_school_id = child.get("school_id") or school_id

        participation = await gd_find(db.session, "participation_records", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "created_at": {"$gte": week_start.isoformat(), "$lte": (week_end + timedelta(days=1)).isoformat()}
        }, limit=200)
        participation_count = len(participation)
        # Display-only annotation: how much of this week's participation came from
        # 3-in-a-row streak bonuses, so the parent view can explain the same
        # base + streak split the teacher saw live. Never changes any grade total.
        streak_bonus_points = 0
        streak_bonus_count = 0
        for p in participation:
            try:
                streak_bonus_points += int(p.get("streak_bonus_points") or 0)
                streak_bonus_count += int(p.get("streak_bonus_count") or 0)
            except (TypeError, ValueError):
                continue

        positive_behaviors = await gd_count(db.session, "behaviour_records", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "type": "positive",
            "created_at": {"$gte": week_start.isoformat(), "$lte": (week_end + timedelta(days=1)).isoformat()}
        })

        skills = await gd_find(db.session, "session_interactions", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "created_at": {"$gte": week_start.isoformat(), "$lte": (week_end + timedelta(days=1)).isoformat()}
        }, limit=200)
        acquired_skills = list(set(
            s.get("skill_tag") for s in skills if s.get("skill_tag")
        ))

        week_grades = await gd_find(db.session, "grades", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "date": {"$gte": week_start.isoformat(), "$lte": week_end.isoformat()}
        }, limit=200)
        subject_scores = {}
        for g in week_grades:
            subj = g.get("subject_name") or g.get("subject_id", "عام")
            if subj not in subject_scores:
                subject_scores[subj] = []
            subject_scores[subj].append(g.get("percentage", 0))

        strong_subjects = []
        weak_subjects = []
        for subj, scores in subject_scores.items():
            avg = sum(scores) / len(scores) if scores else 0
            if avg >= 80:
                strong_subjects.append({"subject": subj, "average": round(avg, 1)})
            elif avg < 60:
                weak_subjects.append({"subject": subj, "average": round(avg, 1)})

        remedial_plans = await gd_find(db.session, "student_plans", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "plan_type": "remedial",
            "created_at": {"$gte": week_start.isoformat(), "$lte": (week_end + timedelta(days=1)).isoformat()}
        }, limit=20)

        # ----- Lateness / absence (this week) -----
        late_count = await _att_count(db.session, {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "status": "late",
            "date": {"$gte": week_start.isoformat(), "$lte": week_end.isoformat()}
        })
        absent_count = await _att_count(db.session, {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "status": "absent",
            "date": {"$gte": week_start.isoformat(), "$lte": week_end.isoformat()}
        })

        # ----- Homework completion (this week, best-effort) -----
        # Honest empty: when the school doesn't track homework we leave
        # both at 0 so the ranker simply skips the homework cards.
        # Merged sources: digital assignments + lesson-recorded homework
        # ("سلم"/"لم يسلم"), same as the الواجبات tab and cumulative analytics.
        homework_total = 0
        homework_done = 0
        try:
            homework_done, homework_total = await _merged_homework_counts(
                db.session, child, tenant_school_id,
                week_start.isoformat(), week_end.isoformat(),
            )
        except Exception as e:
            logger.debug(f"weekly homework signal lookup failed: {e}")

        daily_data = []
        day_names_ar = ["السبت", "الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس"]
        for i in range(6):
            day_date = week_start + timedelta(days=i)
            day_str = day_date.isoformat()
            day_participation = sum(1 for p in participation if str(p.get("created_at", "")).startswith(day_str))
            day_behavior = await gd_count(db.session, "behaviour_records", {
                "student_id": child_id,
                "school_id": tenant_school_id,
                "type": "positive",
                "created_at": {"$gte": day_str, "$lt": (day_date + timedelta(days=1)).isoformat()}
            })
            daily_data.append({
                "day": day_names_ar[i],
                "date": day_str,
                "participation": day_participation,
                "positive_behavior": day_behavior,
            })

        remedial_plans_payload = [
            {
                "id": p.get("id"),
                "title": p.get("title", "خطة علاجية"),
                "description": p.get("description", ""),
                "subject": p.get("subject", ""),
                "teacher_name": p.get("teacher_name", ""),
                "created_at": p.get("created_at"),
            }
            for p in remedial_plans
        ]

        # ----- Compact ranked cards (top 2 positive + 1 concern + 1 academic)
        ranked_signals = {
            "grade_level": child.get("grade_level") or child.get("grade") or "",
            "participation_count": participation_count,
            "positive_behaviors": positive_behaviors,
            "acquired_skills": acquired_skills[:8],
            "strong_subjects": strong_subjects,
            "weak_subjects": weak_subjects,
            "remedial_plans": [
                {"title": p.get("title"), "subject": p.get("subject")}
                for p in remedial_plans_payload[:3]
            ],
            "late_count": late_count,
            "absent_count": absent_count,
            "homework_total": homework_total,
            "homework_done": homework_done,
        }
        cards = _rank_weekly_cards(ranked_signals)
        status = "available" if cards else "insufficient_data"

        # ----- Real Hakim insight (story + tip). The advice card is fed
        # ONLY by the structured ranked metrics — never by raw teacher notes.
        weekly_insight = await _get_or_build_parent_weekly_insight(
            child_id=child_id,
            school_id=child.get("school_id") or school_id,
            week_start=week_start.isoformat(),
            week_end=week_end.isoformat(),
            signals=ranked_signals,
            cards=cards,
        )

        # Advice card payload — present only when Hakim returned a real tip.
        # When the LLM is unavailable we omit it gracefully (FE skips it).
        advice = None
        if weekly_insight.get("status") == "available" and weekly_insight.get("tip"):
            advice = {
                "text_ar": weekly_insight.get("tip"),
                "generated_at": weekly_insight.get("generated_at"),
            }

        return {
            "status": status,
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            # New compact, UI-ready payload (Task #324)
            "cards": cards,
            "advice": advice,
            # ---- Back-compat: keep legacy fields so older clients don't break
            "participation_count": participation_count,
            # Display-only: this week's streak-bonus total + how many answers
            # earned one, so the parent view explains the base + streak split.
            "streak_bonus_points": streak_bonus_points,
            "streak_bonus_count": streak_bonus_count,
            "positive_behaviors": positive_behaviors,
            "acquired_skills": acquired_skills,
            "strong_subjects": strong_subjects,
            "weak_subjects": weak_subjects,
            "remedial_plans": remedial_plans_payload,
            "daily_chart_data": daily_data,
            "weekly_insight": weekly_insight,
            "weekly_tip": weekly_insight.get("tip") if weekly_insight.get("status") == "available" else None,
        }

    # ============= WEEKLY ACADEMIC ANALYSIS =============
    # Backend-aggregated weekly pulse for the Parent Portal student profile
    # (التحليل الأكاديمي الأسبوعي). One endpoint, one student, one
    # parent-authorized context. Reuses _verify_parent_access as the sole
    # authorization boundary and enforces tenant scoping on every signal.
    @router.get("/child/{child_id}/weekly-analysis")
    async def get_child_weekly_analysis(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, school_id, current_user=current_user)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        # Saudi academic week: Saturday → Thursday (mirrors weekly-story).
        now = datetime.now(SAUDI_TZ)
        today = now.date()
        days_since_saturday = (today.weekday() + 2) % 7
        week_start = today - timedelta(days=days_since_saturday)
        week_end = week_start + timedelta(days=5)
        prev_week_start = week_start - timedelta(days=7)
        prev_week_end = week_end - timedelta(days=7)

        tenant_school_id = child.get("school_id") or school_id

        def _date_range(start, end):
            # inclusive [start, end] on a date column stored as ISO date.
            return {"$gte": start.isoformat(), "$lte": end.isoformat()}

        def _ts_range(start, end):
            # inclusive [start, end] on a timestamp column.
            return {"$gte": start.isoformat(), "$lt": (end + timedelta(days=1)).isoformat()}

        child_class_id = child.get("class_id")

        # ----- Attendance (this week) -----
        attendance_records = await _att_find(db.session, {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "date": _date_range(week_start, week_end),
        }, limit=50)

        att_counts = {"present": 0, "absent": 0, "late": 0, "excused": 0}
        per_day_status = {}
        for rec in attendance_records:
            status = (rec.get("status") or "").lower()
            if status in att_counts:
                att_counts[status] += 1
            day_key = str(rec.get("date") or "")[:10]
            if day_key:
                per_day_status[day_key] = status

        # Denominator: class-level distinct dates so absent students with no
        # row still count toward total (mirrors dashboard/children fix, Issue #30).
        if child_class_id:
            att_total = len(await _att_distinct_days(
                db.session,
                {"school_id": tenant_school_id, "class_id": child_class_id,
                 "date": _date_range(week_start, week_end)},
            ))
        else:
            att_total = len({str(r.get("date") or "")[:10] for r in attendance_records if r.get("date")}) or sum(att_counts.values())
        att_rate = round(((att_counts["present"] + att_counts["late"]) / att_total) * 100) if att_total > 0 else None

        # Prior-week attendance for trend
        prev_attendance = await _att_find(db.session, {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "date": _date_range(prev_week_start, prev_week_end),
        }, limit=50)
        prev_present = sum(1 for r in prev_attendance if (r.get("status") or "").lower() in ("present", "late"))
        if child_class_id:
            prev_total = len(await _att_distinct_days(
                db.session,
                {"school_id": tenant_school_id, "class_id": child_class_id,
                 "date": _date_range(prev_week_start, prev_week_end)},
            ))
        else:
            prev_total = len(prev_attendance)
        prev_att_rate = round((prev_present / prev_total) * 100) if prev_total > 0 else None
        att_trend = (att_rate - prev_att_rate) if (att_rate is not None and prev_att_rate is not None) else None

        # ----- Behaviour (this week) -----
        positive_behaviour = await gd_count(db.session, "behaviour_records", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "type": "positive",
            "created_at": _ts_range(week_start, week_end),
        })
        negative_behaviour = await gd_count(db.session, "behaviour_records", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "type": "negative",
            "created_at": _ts_range(week_start, week_end),
        })
        behaviour_total = positive_behaviour + negative_behaviour
        behaviour_score = round((positive_behaviour / behaviour_total) * 100) if behaviour_total > 0 else None

        # ----- Assessments / grades (this week) -----
        week_grades = await gd_find(db.session, "grades", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "date": _date_range(week_start, week_end),
        }, limit=200)
        subj_buckets = {}
        all_pcts = []
        for g in week_grades:
            pct = g.get("percentage")
            if pct is None:
                continue
            try:
                pct_val = float(pct)
            except (TypeError, ValueError):
                continue
            all_pcts.append(pct_val)
            subj = g.get("subject_name") or g.get("subject_id") or "عام"
            subj_buckets.setdefault(subj, []).append(pct_val)
        grades_avg = round(sum(all_pcts) / len(all_pcts)) if all_pcts else None
        subjects_payload = [
            {"subject": s, "average": round(sum(v) / len(v), 1), "items": len(v)}
            for s, v in subj_buckets.items()
        ]
        subjects_payload.sort(key=lambda x: x["average"], reverse=True)

        # ----- Homework (this week, best-effort) -----
        # Merged sources: digital assignments + lesson-recorded homework
        # ("سلم"/"لم يسلم"), same as the الواجبات tab and cumulative analytics.
        hw_total = 0
        hw_done = 0
        try:
            hw_done, hw_total = await _merged_homework_counts(
                db.session, child, tenant_school_id,
                week_start.isoformat(), week_end.isoformat(),
            )
        except Exception as e:
            logger.debug(f"weekly-analysis homework lookup failed: {e}")
        hw_available = hw_total > 0
        hw_rate = round((hw_done / hw_total) * 100) if hw_total > 0 else None

        # ----- Per-day attendance series for the chart -----
        day_names_ar = ["السبت", "الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس"]
        daily = []
        for i in range(6):
            d = week_start + timedelta(days=i)
            iso = d.isoformat()
            status = per_day_status.get(iso)
            daily.append({
                "day_ar": day_names_ar[i],
                "date": iso,
                "status": status,             # null when no record yet
                "is_future": d > today,
                "is_today": d == today,
            })

        # ----- Metric envelope (each carries an availability flag) -----
        metrics = [
            {
                "key": "attendance",
                "label_ar": "الحضور",
                "available": att_rate is not None,
                "value": att_rate,
                "unit": "%",
                "trend": att_trend,
                "details": {
                    "present": att_counts["present"],
                    "absent": att_counts["absent"],
                    "late": att_counts["late"],
                    "excused": att_counts["excused"],
                    "total": att_total,
                },
            },
            {
                "key": "assessments",
                "label_ar": "التقييمات",
                "available": grades_avg is not None,
                "value": grades_avg,
                "unit": "%",
                "trend": None,
                "details": {"items": len(all_pcts), "subjects": subjects_payload[:5]},
            },
            {
                "key": "behaviour",
                "label_ar": "السلوك",
                "available": behaviour_score is not None,
                "value": behaviour_score,
                "unit": "%",
                "trend": None,
                "details": {
                    "positive": positive_behaviour,
                    "negative": negative_behaviour,
                    "total": behaviour_total,
                },
            },
            {
                "key": "homework",
                "label_ar": "الواجبات",
                "available": hw_available,
                "value": hw_rate,
                "unit": "%",
                "trend": None,
                "details": {"done": hw_done, "total": hw_total},
            },
        ]

        any_available = any(m["available"] for m in metrics)
        status = "available" if any_available else "insufficient_data"

        # Short Arabic headline derived ONLY from real metrics (no LLM here).
        if not any_available:
            headline_ar = "لا توجد بيانات كافية للأسبوع الحالي"
        else:
            parts = []
            if att_rate is not None:
                parts.append(f"الحضور {att_rate}%")
            if grades_avg is not None:
                parts.append(f"المعدل {grades_avg}%")
            if behaviour_total > 0:
                parts.append(f"{positive_behaviour} ملاحظة إيجابية")
            headline_ar = " · ".join(parts) if parts else "ملخص الأسبوع متاح"

        return {
            "status": status,
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "headline_ar": headline_ar,
            "metrics": metrics,
            "daily_attendance": daily,
            "last_updated": now.isoformat(),
            "empty_hint_ar": "لا توجد بيانات كافية للأسبوع الحالي",
        }

    # ============= STUDENT INSIGHTS (cohesive parent-facing) =============
    # GET /parent-portal/child/{child_id}/insights
    #
    # One backend-aggregated payload powering the cohesive Parent Portal
    # Student-Profile insights surface:
    #   - generalInsights.strengths / weaknesses  (deterministic tags from real data)
    #   - subjects[] accordion with per-subject score, trend, level, tags, action plan
    #   - hakimSummary  (grounded narrative; reuses existing hakim_llm_service)
    #   - parentTips    (Hakim subject-focused tip on the most attention-needing subject)
    #   - insufficientDataFlags
    #
    # Authorization: reuses _verify_parent_access (the sole parent ↔ student
    # boundary used everywhere in this module). Tenant scoping is enforced
    # on every signal query. Hakim is called at most twice and falls back
    # cleanly to deterministic output when unavailable / disabled.
    @router.get("/child/{child_id}/insights")
    async def get_child_insights(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, school_id, current_user=current_user)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        tenant_school_id = child.get("school_id") or school_id
        now = datetime.now(SAUDI_TZ)
        today = now.date()
        # Two ~30-day windows so we have a real "previous" baseline for trend.
        window_days = 30
        current_start = today - timedelta(days=window_days - 1)
        previous_start = today - timedelta(days=2 * window_days - 1)
        previous_end = current_start - timedelta(days=1)

        # ---- Grades (single bulk fetch, then split into current vs previous) ----
        all_grades = await gd_find(db.session, "grades", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "date": {"$gte": previous_start.isoformat(), "$lte": today.isoformat()},
        }, order_by="date", desc_order=True, limit=500)

        def _pct(g):
            v = g.get("percentage")
            if v is None:
                try:
                    score = float(g.get("score") or 0)
                    mx = float(g.get("max_score") or 0)
                    return (score / mx) * 100 if mx > 0 else None
                except (TypeError, ValueError):
                    return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        # Group per subject (key on subject_id when present, else name) and
        # keep both current and previous buckets in one O(N) pass.
        subjects_acc = {}
        for g in all_grades:
            pct = _pct(g)
            if pct is None:
                continue
            subj_id = g.get("subject_id") or ""
            subj_name = g.get("subject_name") or g.get("subject") or "غير محدد"
            key = subj_id or subj_name
            d_str = str(g.get("date") or "")[:10]
            if not d_str:
                continue
            try:
                d = datetime.fromisoformat(d_str).date()
            except ValueError:
                continue
            bucket = subjects_acc.setdefault(key, {
                "subject_id": subj_id or None,
                "subject_name": subj_name,
                "current": [],
                "previous": [],
                "teacher_id": g.get("teacher_id"),
            })
            if d >= current_start:
                bucket["current"].append(pct)
            elif previous_start <= d <= previous_end:
                bucket["previous"].append(pct)

        # ---- Bulk teacher-name lookup (no N+1) ----
        teacher_ids = {b["teacher_id"] for b in subjects_acc.values() if b.get("teacher_id")}
        teacher_name_map = {}
        if teacher_ids:
            try:
                tch_rows = await gd_find(db.session, "teachers", {
                    "id": {"$in": list(teacher_ids)},
                    "school_id": tenant_school_id,
                }, limit=200)
                for t in tch_rows:
                    teacher_name_map[t.get("id")] = t.get("full_name") or t.get("name")
                # Fallback to users table for any unresolved teacher_id.
                missing = [tid for tid in teacher_ids if tid not in teacher_name_map]
                if missing:
                    # Tenant-scope the users fallback so a foreign-tenant
                    # teacher_id stamped on a grade row can never resolve to
                    # a name from another school (PII isolation).
                    u_rows = await gd_find(db.session, "users", {
                        "id": {"$in": missing},
                        "school_id": tenant_school_id,
                    }, limit=200)
                    for u in u_rows:
                        teacher_name_map[u.get("id")] = u.get("full_name") or u.get("name")
            except Exception as e:
                logger.debug(f"insights teacher name lookup failed: {e}")

        # ---- Attendance & behaviour (current window only, for general tags) ----
        attendance_records = await _att_find(db.session, {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "date": {"$gte": current_start.isoformat(), "$lte": today.isoformat()},
        }, limit=500)
        att_present = sum(1 for r in attendance_records if (r.get("status") or "").lower() == "present")
        att_late = sum(1 for r in attendance_records if (r.get("status") or "").lower() == "late")
        att_absent = sum(1 for r in attendance_records if (r.get("status") or "").lower() == "absent")
        att_total = att_present + att_late + att_absent + sum(
            1 for r in attendance_records if (r.get("status") or "").lower() == "excused"
        )
        att_rate = round(((att_present + att_late) / att_total) * 100) if att_total > 0 else None

        positive_b = await gd_count(db.session, "behaviour_records", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "type": "positive",
            "created_at": {"$gte": current_start.isoformat(), "$lt": (today + timedelta(days=1)).isoformat()},
        })
        negative_b = await gd_count(db.session, "behaviour_records", {
            "student_id": child_id,
            "school_id": tenant_school_id,
            "type": "negative",
            "created_at": {"$gte": current_start.isoformat(), "$lt": (today + timedelta(days=1)).isoformat()},
        })

        # ---- Per-subject deterministic computation ----
        def _level(score):
            if score is None:
                return "insufficient"
            if score >= 85:
                return "advanced"        # متقدم
            if score >= 70:
                return "intermediate"    # متوسط
            return "needs_focus"         # يحتاج تركيز

        def _trend(curr_avg, prev_avg):
            if curr_avg is None or prev_avg is None:
                return "insufficient"
            delta = curr_avg - prev_avg
            if delta >= 3:
                return "improving"
            if delta <= -3:
                return "declining"
            return "stable"

        subjects_payload = []
        for key, b in subjects_acc.items():
            curr_avg = round(sum(b["current"]) / len(b["current"]), 1) if b["current"] else None
            prev_avg = round(sum(b["previous"]) / len(b["previous"]), 1) if b["previous"] else None
            level = _level(curr_avg)
            trend = _trend(curr_avg, prev_avg)

            # Deterministic per-subject tags. Empty by design when there is
            # not enough evidence — Hakim never invents tags.
            strengths = []
            weaknesses = []
            if curr_avg is not None:
                if curr_avg >= 90:
                    strengths.append("أداء متميز")
                elif curr_avg >= 80:
                    strengths.append("أداء قوي")
                if trend == "improving":
                    strengths.append("اتجاه تحسن")
                if curr_avg < 60:
                    weaknesses.append("معدل منخفض")
                elif curr_avg < 70:
                    weaknesses.append("يحتاج تعزيز")
                if trend == "declining":
                    weaknesses.append("اتجاه تراجع")

            # Deterministic action plan (rule-based; Hakim only refines wording).
            action_plan = None
            if curr_avg is not None and len(b["current"]) >= 1:
                if level == "advanced":
                    action_plan = {
                        "type": "enrichment",
                        "title": "خطة إثرائية",
                        "description": "اقترحوا أنشطة إثرائية بسيطة في المنزل تواكب تميّز الطالب في هذه المادة.",
                        "hint": "تحديات إضافية لتنمية الموهبة",
                    }
                elif level == "needs_focus":
                    action_plan = {
                        "type": "remedial",
                        "title": "خطة علاجية",
                        "description": "خصّصوا وقتاً قصيراً يومياً لمراجعة المفاهيم الأساسية بأسلوب هادئ ومتكرر.",
                        "hint": "خطوات يومية بسيطة في المنزل",
                    }

            subjects_payload.append({
                "id": b["subject_id"] or key,
                "name": b["subject_name"],
                "score": curr_avg,
                "previous_score": prev_avg,
                "trend_status": trend,
                "level": level,
                "teacher_name": teacher_name_map.get(b.get("teacher_id")) if b.get("teacher_id") else None,
                "items_current": len(b["current"]),
                "items_previous": len(b["previous"]),
                "strengths": strengths,
                "weaknesses": weaknesses,
                "action_plan": action_plan,
            })

        # Sort: weakest first if any are weak (parent attention), else strongest first.
        subjects_payload.sort(key=lambda s: (s["score"] is None, s["score"] or 0))

        # ---- General strengths / weaknesses (deterministic only) ----
        general_strengths = []
        general_weaknesses = []
        if att_rate is not None and att_rate >= 90:
            general_strengths.append("التزام جيد بالحضور")
        if att_rate is not None and att_rate < 75 and att_total >= 5:
            general_weaknesses.append("الحضور والانضباط")
        if positive_b >= 3 and positive_b > negative_b:
            general_strengths.append("سلوك إيجابي ملحوظ")
        if negative_b >= 3 and negative_b > positive_b:
            general_weaknesses.append("ملاحظات سلوكية تحتاج متابعة")

        strong_subjects_names = [s["name"] for s in subjects_payload if s["level"] == "advanced"]
        weak_subjects_names = [s["name"] for s in subjects_payload if s["level"] == "needs_focus"]
        improving_names = [s["name"] for s in subjects_payload if s["trend_status"] == "improving"]
        declining_names = [s["name"] for s in subjects_payload if s["trend_status"] == "declining"]

        if strong_subjects_names:
            general_strengths.append(f"تميّز في {('، '.join(strong_subjects_names[:2]))}")
        if improving_names and not strong_subjects_names:
            general_strengths.append(f"تحسّن في {('، '.join(improving_names[:2]))}")
        if weak_subjects_names:
            general_weaknesses.append(f"تركيز إضافي في {('، '.join(weak_subjects_names[:2]))}")
        if declining_names and not weak_subjects_names:
            general_weaknesses.append(f"تراجع في {('، '.join(declining_names[:2]))}")

        # Deduplicate while preserving order
        def _dedupe(lst):
            seen = set()
            out = []
            for x in lst:
                if x and x not in seen:
                    seen.add(x)
                    out.append(x)
            return out
        general_strengths = _dedupe(general_strengths)[:4]
        general_weaknesses = _dedupe(general_weaknesses)[:4]

        # ---- Insufficient-data flags ----
        insufficient_flags = {
            "general_strengths": len(general_strengths) == 0,
            "general_weaknesses": len(general_weaknesses) == 0,
            "subjects": len(subjects_payload) == 0,
            "no_grades_at_all": len(all_grades) == 0,
        }

        overall_trend = "stable"
        if improving_names and not declining_names:
            overall_trend = "improving"
        elif declining_names and not improving_names:
            overall_trend = "declining"
        elif not subjects_payload:
            overall_trend = "insufficient"

        # ---- Hakim narrative + per-subject tip (grounded; safe fallback) ----
        hakim_summary = {"status": "insufficient_data", "text": None}
        parent_tips = []
        try:
            from services.hakim_llm_service import hakim_generate, is_available as hakim_available
        except Exception as e:
            logger.debug(f"insights: hakim service unavailable: {e}")
            hakim_generate = None
            hakim_available = lambda: False  # noqa: E731

        # Only call Hakim when we actually have something factual to summarize.
        has_signal = bool(general_strengths or general_weaknesses or subjects_payload)

        # SECURITY (task #438): per-child, per-day AI cache.  Check the
        # ai_insights table before triggering any LLM calls.  This mirrors
        # the weekly-story cache pattern and ensures that repeated requests
        # from the same parent within a calendar day do not re-invoke Hakim.
        _insights_cache_date_key = today.isoformat()
        _insights_cached_ai = None
        if has_signal:
            try:
                _cache_row = await gd_find_one(db.session, "ai_insights", {
                    "insight_type": "parent_insights_daily",
                    "entity_type": "student",
                    "entity_id": child_id,
                    "school_id": tenant_school_id,
                })
                if _cache_row and isinstance(_cache_row.get("data"), dict):
                    if _cache_row["data"].get("cache_date") == _insights_cache_date_key:
                        _insights_cached_ai = _cache_row["data"]
            except Exception as _ce:
                logger.debug(f"insights: ai cache lookup failed: {_ce}")

        if _insights_cached_ai:
            hakim_summary = _insights_cached_ai.get("hakim_summary", {"status": "insufficient_data", "text": None})
            parent_tips = _insights_cached_ai.get("parent_tips", [])
        elif has_signal and hakim_generate and hakim_available():
            summary_ctx = {
                "grade_level": child.get("grade_level") or child.get("grade") or "",
                "general_strengths": general_strengths,
                "general_weaknesses": general_weaknesses,
                "strong_subjects": strong_subjects_names[:3],
                "weak_subjects": weak_subjects_names[:3],
                "overall_trend": {
                    "improving": "تحسن",
                    "declining": "تراجع",
                    "stable": "مستقر",
                    "insufficient": "غير كافٍ",
                }.get(overall_trend, "مستقر"),
            }
            try:
                summary_res = await hakim_generate(
                    mode="generate", field="parent_insights_summary",
                    text="", context=summary_ctx, language="ar", tone="educational",
                    tenant_id=tenant_school_id,
                )
                if summary_res.get("success") and summary_res.get("text"):
                    hakim_summary = {"status": "available", "text": summary_res["text"]}
                else:
                    hakim_summary = {"status": "unavailable", "text": None}
            except Exception as e:
                logger.warning(f"insights: parent_insights_summary failed: {e}")
                hakim_summary = {"status": "unavailable", "text": None}

            # Single subject-focused tip on the highest-attention subject
            # (weakest available with at least one current grade).
            focus_subject = next(
                (s for s in subjects_payload if s["score"] is not None and s["level"] == "needs_focus"),
                None,
            ) or next(
                (s for s in subjects_payload if s["score"] is not None and s["level"] == "advanced"),
                None,
            )
            if focus_subject:
                tip_ctx = {
                    "subject_name": focus_subject["name"],
                    "subject_score": focus_subject["score"],
                    "subject_trend": {
                        "improving": "تحسن",
                        "declining": "تراجع",
                        "stable": "مستقر",
                        "insufficient": "غير كافٍ",
                    }.get(focus_subject["trend_status"], "مستقر"),
                    "subject_strengths": focus_subject["strengths"],
                    "subject_weaknesses": focus_subject["weaknesses"],
                    "subject_level": {
                        "advanced": "متقدم",
                        "intermediate": "متوسط",
                        "needs_focus": "يحتاج تركيز",
                    }.get(focus_subject["level"], "متوسط"),
                }
                try:
                    tip_res = await hakim_generate(
                        mode="generate", field="parent_subject_focus_tip",
                        text="", context=tip_ctx, language="ar", tone="educational",
                        tenant_id=tenant_school_id,
                    )
                    if tip_res.get("success") and tip_res.get("text"):
                        parent_tips.append({
                            "subject": focus_subject["name"],
                            "text": tip_res["text"],
                        })
                except Exception as e:
                    logger.debug(f"insights: parent_subject_focus_tip failed: {e}")

            # SECURITY (task #438): persist AI results so repeat requests
            # within the same calendar day are served from cache without
            # triggering further LLM calls.  Best-effort — never fail the
            # request on a cache write error.
            if hakim_summary.get("status") == "available":
                try:
                    _cache_payload = {
                        "cache_date": _insights_cache_date_key,
                        "hakim_summary": hakim_summary,
                        "parent_tips": parent_tips,
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                    }
                    _existing_cache = await gd_find_one(db.session, "ai_insights", {
                        "insight_type": "parent_insights_daily",
                        "entity_type": "student",
                        "entity_id": child_id,
                        "school_id": tenant_school_id,
                    })
                    if _existing_cache:
                        await gd_update_one(db.session, "ai_insights", {
                            "insight_type": "parent_insights_daily",
                            "entity_type": "student",
                            "entity_id": child_id,
                            "school_id": tenant_school_id,
                        }, {"data": _cache_payload})
                    else:
                        await gd_insert(db.session, "ai_insights", {
                            "id": str(uuid.uuid4()),
                            "school_id": tenant_school_id,
                            "entity_type": "student",
                            "entity_id": child_id,
                            "insight_type": "parent_insights_daily",
                            "title": "رؤى الطالب اليومية",
                            "content": (hakim_summary.get("text") or "")[:500],
                            "data": _cache_payload,
                            "severity": "info",
                            "is_actionable": False,
                        })
                except Exception as _cwe:
                    logger.debug(f"insights: ai cache write failed: {_cwe}")
        elif has_signal:
            hakim_summary = {"status": "unavailable", "text": None}

        return {
            "status": "available" if has_signal else "insufficient_data",
            "window": {
                "current_start": current_start.isoformat(),
                "current_end": today.isoformat(),
                "previous_start": previous_start.isoformat(),
                "previous_end": previous_end.isoformat(),
            },
            "general_insights": {
                "strengths": general_strengths,
                "weaknesses": general_weaknesses,
            },
            "overall_trend": overall_trend,
            "subjects": subjects_payload,
            "hakim_summary": hakim_summary,
            "parent_tips": parent_tips,
            "insufficient_data_flags": insufficient_flags,
            "empty_hint_ar": "لا توجد بيانات كافية لعرض الرؤى بعد",
            "last_updated": now.isoformat(),
        }

    # ============= STUDENT PROFILE =============

    @router.get("/child/{child_id}/profile")
    async def get_child_profile(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"), current_user=current_user)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح")

        # Issue #30: enrich with live class name from classes table (stale denorm fix).
        from src.common.utils.parent_children_resolution import enrich_children_with_class_names
        [child] = await enrich_children_with_class_names([child], db.session, child.get("school_id") or current_user.get("tenant_id"))

        sid = child.get("school_id") or current_user.get("tenant_id")
        school_name = child.get("school_name", "")
        if not school_name and sid:
            s_doc = await gd_find_one(db.session, "schools", {"id": sid})
            school_name = s_doc.get("name") if s_doc else ""

        # Task #277 — IT context for the parent profile page header.
        is_it_ws = isinstance(sid, str) and sid.startswith("itw_")
        teacher_display_name = None
        if is_it_ws:
            owner_uid = sid[len("itw_"):]
            owner = await gd_find_one(db.session, "users", {"id": owner_uid})
            teacher_display_name = (owner or {}).get("full_name") or None

        return {
            "id": child.get("id"),
            "name": child.get("full_name"),
            "grade_level": child.get("grade_level", child.get("grade", "")),
            "class_name": child.get("class_name", ""),
            "school_id": sid,
            "school_name": school_name,
            "is_independent_teacher_workspace": bool(is_it_ws),
            "teacher_display_name": teacher_display_name,
            "emoji": (child.get("profile_settings") or {}).get("emoji") or child.get("emoji") or "👦",
            "profile_picture": child.get("profile_picture", ""),
            "gender": child.get("gender", ""),
            "health_conditions": (child.get("profile_settings") or {}).get("health_conditions", []),
            "behavioral_aspects": (child.get("profile_settings") or {}).get("behavioral_aspects", []),
            "family_situation": (child.get("profile_settings") or {}).get("family_situation", ""),
            "family_other_situations": (child.get("profile_settings") or {}).get("family_other_situations", []),
            # Free-text "Other" details for health and behavior — these
            # complement the strict enum lists above and let parents
            # describe conditions/aspects the curated catalogue does not
            # cover. Bounded by _PROFILE_OTHER_TEXT_MAX on write.
            "other_health_details": (child.get("profile_settings") or {}).get("other_health_details", ""),
            "other_behavior_details": (child.get("profile_settings") or {}).get("other_behavior_details", ""),
            # المواهب والمهارات — read-only for parents (managed by the school
            # admin from the full student profile; PUT below never touches it).
            "talents": child.get("talents") or [],
            "is_gifted": len(child.get("talents") or []) > 0 or bool(child.get("is_gifted")),
        }

    # Whitelist of values allowed in each list/single-value profile field.
    # Centralised so the FE chip catalogue and BE persisted values cannot
    # drift apart and so an attacker cannot persist arbitrary tag strings
    # on another family's child record.
    _PROFILE_HEALTH_ALLOWED = {
        "asthma", "weak_vision", "weak_hearing", "allergy", "heart",
        "food_allergy", "nut_allergy", "dust_allergy", "seasonal_allergy",
        "diabetes", "epilepsy",
    }
    _PROFILE_BEHAVIOR_ALLOWED = {
        "shyness", "severe_shyness", "hyperactivity", "motor_anxiety",
        "concentration_difficulty", "speech_difficulty", "stuttering",
        "aggression", "anger", "sleep_disorder", "eating_difficulty",
    }
    _PROFILE_FAMILY_ALLOWED = {
        "both_parents", "father_only", "mother_only", "other",
    }
    _PROFILE_FAMILY_OTHER_ALLOWED = {
        "parents_separation", "parent_traveling", "foster_family",
        "orphan", "second_marriage", "family_problems",
    }
    _PROFILE_EMOJI_ALLOWED = {
        "👦", "👧", "🧒", "👨‍🎓", "👩‍🎓", "🦸‍♂️", "🦸‍♀️",
        "🧑‍💻", "🎨", "⚽", "🎵", "📚", "🌟", "🦋", "🚀", "🎯",
    }
    # Hard cap on the free-text "Other" descriptions so a malicious
    # parent can't grow the per-student JSONB row indefinitely. 255
    # matches the FE textarea maxLength.
    _PROFILE_OTHER_TEXT_MAX = 255

    def _sanitize_other_text(raw) -> str:
        if not isinstance(raw, str):
            return ""
        cleaned = raw.strip()
        if not cleaned:
            return ""
        return cleaned[:_PROFILE_OTHER_TEXT_MAX]

    def _sanitize_str_list(raw, allowed: set) -> list:
        if not isinstance(raw, list):
            return []
        seen = set()
        out = []
        for item in raw:
            if isinstance(item, str) and item in allowed and item not in seen:
                seen.add(item)
                out.append(item)
        return out

    @router.put("/child/{child_id}/profile")
    async def update_child_profile(
        child_id: str,
        data: dict,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        child = await _verify_parent_access(
            parent_id, parent_phone, child_id,
            current_user.get("tenant_id"), current_user=current_user,
        )
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح")

        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail="بيانات غير صالحة")

        # Merge into the existing per-student profile_settings JSONB so a
        # partial save (e.g. only family_situation) does not clobber the
        # other groups the parent had previously stored for this child.
        current_settings = dict(child.get("profile_settings") or {})

        if "emoji" in data:
            emoji = data.get("emoji")
            if isinstance(emoji, str) and emoji in _PROFILE_EMOJI_ALLOWED:
                current_settings["emoji"] = emoji
        if "health_conditions" in data:
            current_settings["health_conditions"] = _sanitize_str_list(
                data.get("health_conditions"), _PROFILE_HEALTH_ALLOWED,
            )
        if "behavioral_aspects" in data:
            current_settings["behavioral_aspects"] = _sanitize_str_list(
                data.get("behavioral_aspects"), _PROFILE_BEHAVIOR_ALLOWED,
            )
        if "family_situation" in data:
            fs = data.get("family_situation")
            if fs in _PROFILE_FAMILY_ALLOWED:
                current_settings["family_situation"] = fs
            elif fs in (None, ""):
                current_settings["family_situation"] = ""
        if "family_other_situations" in data:
            current_settings["family_other_situations"] = _sanitize_str_list(
                data.get("family_other_situations"), _PROFILE_FAMILY_OTHER_ALLOWED,
            )
        # Free-text complements to the strict enum lists. Sending an
        # empty string clears the prior value so the FE can switch the
        # "أخرى" pill off without leaving stale text behind.
        if "other_health_details" in data:
            current_settings["other_health_details"] = _sanitize_other_text(
                data.get("other_health_details"),
            )
        if "other_behavior_details" in data:
            current_settings["other_behavior_details"] = _sanitize_other_text(
                data.get("other_behavior_details"),
            )

        if current_settings == (child.get("profile_settings") or {}):
            return {
                "success": True,
                "message": "لا توجد تغييرات",
                "profile_settings": current_settings,
            }

        # Write is scoped by students.id AND school_id so a parent cannot
        # widen the write past the tenant boundary enforced by
        # _verify_parent_access above (defence-in-depth).
        write_filter = {"id": child_id}
        sid = child.get("school_id") or current_user.get("tenant_id")
        if sid:
            write_filter["school_id"] = sid
        await gd_update_one(
            db.session, "students", write_filter,
            {"$set": {"profile_settings": current_settings}},
        )
        return {
            "success": True,
            "message": "تم تحديث الملف بنجاح",
            "profile_settings": current_settings,
        }

    # ============= ACHIEVEMENTS =============

    @router.get("/child/{child_id}/achievements")
    async def get_child_achievements(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"), current_user=current_user)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح")

        achievements = await gd_find(
            db.session, "student_achievements",
            {"student_id": child_id},
            order_by="created_at", desc_order=True, limit=100
        )
        return {"achievements": achievements, "total": len(achievements)}

    @router.post("/child/{child_id}/achievements")
    async def add_child_achievement(
        child_id: str,
        data: dict,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")
        child = await _verify_parent_access(parent_id, parent_phone, child_id, school_id, current_user=current_user)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح")

        ALLOWED_TYPES = {"academic", "sports", "arts", "behavior", "other"}

        ach_name = (data.get("name") or "").strip()
        if not ach_name:
            raise HTTPException(status_code=400, detail="اسم الإنجاز مطلوب")

        ach_type = data.get("type", "other")
        if ach_type not in ALLOWED_TYPES:
            ach_type = "other"

        achievement = {
            "id": str(uuid.uuid4()),
            "student_id": child_id,
            "school_id": child.get("school_id", school_id),
            "name": ach_name,
            "type": ach_type,
            "source": "parent",
            "source_user_id": parent_id,
            "file_url": "",
            "file_data": "",
            "file_name": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await gd_insert(db.session, "student_achievements", achievement)
        return {"success": True, "achievement": achievement}

    ALLOWED_ACHIEVEMENT_MIMES = {
        "image/jpeg", "image/png", "image/gif", "image/webp",
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }

    @router.post("/child/{child_id}/achievements/upload")
    async def upload_child_achievement(
        child_id: str,
        name: str = Form(...),
        type: str = Form("other"),
        file: UploadFile = File(None),
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        import base64
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")
        child = await _verify_parent_access(parent_id, parent_phone, child_id, school_id, current_user=current_user)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح")

        clean_name = name.strip()
        if not clean_name:
            raise HTTPException(status_code=400, detail="اسم الإنجاز مطلوب")

        allowed_types = {"academic", "sports", "arts", "behavior", "other"}
        if type not in allowed_types:
            type = "other"

        file_data = ""
        file_name = ""
        if file and file.filename:
            if file.content_type not in ALLOWED_ACHIEVEMENT_MIMES:
                raise HTTPException(status_code=400, detail="نوع الملف غير مسموح — يرجى رفع صورة أو PDF أو مستند Word")
            content = await file.read()
            if len(content) > 5 * 1024 * 1024:
                raise HTTPException(status_code=400, detail="حجم الملف يجب أن يكون أقل من 5 ميجابايت")
            encoded = base64.b64encode(content).decode("utf-8")
            file_data = f"data:{file.content_type};base64,{encoded}"
            file_name = file.filename

        achievement = {
            "id": str(uuid.uuid4()),
            "student_id": child_id,
            "school_id": child.get("school_id", school_id),
            "name": clean_name,
            "type": type,
            "source": "parent",
            "source_user_id": parent_id,
            "file_data": file_data,
            "file_name": file_name,
            "file_url": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await gd_insert(db.session, "student_achievements", achievement)
        return {"success": True, "achievement": achievement}

    # ============= ANALYTICS =============

    @router.get("/child/{child_id}/analytics")
    async def get_child_analytics(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")
        child = await _verify_parent_access(parent_id, parent_phone, child_id, school_id, current_user=current_user)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح")

        all_grades = await gd_find(db.session, "grades", {"student_id": child_id}, limit=1000)
        overall_avg = round(sum(g.get("percentage", 0) for g in all_grades) / len(all_grades), 1) if all_grades else 0

        # Build the radar from real subjects the student actually has grades
        # in — never inject hardcoded subject names with 0% scores, which
        # would invent failing subjects the student never took.
        # (Audit 2026-05-10.)
        subject_all = {}
        for g in all_grades:
            subj = g.get("subject_name") or g.get("subject_id", "عام")
            if subj not in subject_all:
                subject_all[subj] = []
            subject_all[subj].append(g.get("percentage", 0))

        radar_data = sorted(
            [
                {"subject": subj, "score": round(sum(scores) / len(scores), 1)}
                for subj, scores in subject_all.items() if scores
            ],
            key=lambda r: r["score"],
            reverse=True,
        )[:6]

        monthly_data = {}
        for g in all_grades:
            date_str = str(g.get("date", ""))
            if date_str and len(date_str) >= 7:
                month_key = date_str[:7]
                if month_key not in monthly_data:
                    monthly_data[month_key] = []
                monthly_data[month_key].append(g.get("percentage", 0))

        line_chart_data = sorted([
            {"month": k, "average": round(sum(v) / len(v), 1)}
            for k, v in monthly_data.items()
        ], key=lambda x: x["month"])

        class_id = child.get("class_id")
        class_avg = 0
        child_school_id = child.get("school_id") or school_id
        if class_id:
            classmates = await gd_find(db.session, "students", {"class_id": class_id, "school_id": child_school_id}, limit=100)
            classmate_ids = [c.get("id") for c in classmates if c.get("id") != child_id]
            if classmate_ids:
                class_grades = await gd_find(db.session, "grades", {
                    "student_id": {"$in": classmate_ids}
                }, limit=5000)
                class_avg = round(sum(g.get("percentage", 0) for g in class_grades) / len(class_grades), 1) if class_grades else 0

        strengths = []
        weaknesses = []
        for subj, scores in subject_all.items():
            avg = round(sum(scores) / len(scores), 1) if scores else 0
            if avg >= 80:
                strengths.append({"area": subj, "detail": f"متوسط {avg}%"})
            elif avg < 60:
                weaknesses.append({"area": subj, "detail": f"متوسط {avg}%"})

        total_participation = await gd_count(db.session, "participation_records", {"student_id": child_id})
        if total_participation > 20:
            strengths.append({"area": "مشاركة صفية", "detail": f"{total_participation} مشاركة مسجلة"})

        total_att = await _att_count(db.session, {"student_id": child_id})
        present_att = await _att_count(db.session, {"student_id": child_id, "status": "present"})
        att_rate = round((present_att / total_att * 100), 1) if total_att > 0 else 0

        # Merged homework metric: digital assignments AND lesson-recorded
        # homework ("سلم"/"لم يسلم") — the same two sources the الواجبات tab
        # shows, so the summary can never contradict the homework list.
        hw_done, hw_total = await _merged_homework_counts(
            db.session, child, child_school_id
        )
        homework_rate = round(hw_done / hw_total * 100, 1) if hw_total > 0 else None

        if homework_rate is not None and homework_rate < 60:
            weaknesses.append({"area": "واجبات غير مكتملة", "detail": f"نسبة إنجاز {homework_rate}%"})

        # Composite: when the school tracks no homework at all (neither
        # digital nor lesson-recorded), the homework component is excluded
        # and the remaining weights are renormalized — an untracked metric
        # must not drag the score to "بحاجة دعم".
        participation_score = min(total_participation, 50) / 50 * 100
        weighted = [(att_rate, 0.3), (participation_score, 0.2), (overall_avg, 0.2)]
        if homework_rate is not None:
            weighted.append((homework_rate, 0.3))
        follow_up_score = sum(v * w for v, w in weighted) / sum(w for _, w in weighted)
        if follow_up_score >= 75:
            follow_up_status = "مستقر"
        elif follow_up_score >= 50:
            follow_up_status = "يحتاج متابعة"
        else:
            follow_up_status = "بحاجة دعم"

        if overall_avg >= 90:
            level = "ممتاز"
        elif overall_avg >= 80:
            level = "جيد جداً"
        elif overall_avg >= 70:
            level = "جيد"
        elif overall_avg >= 60:
            level = "مقبول"
        else:
            level = "ضعيف"

        return {
            "student_name": child.get("full_name"),
            "summary": {
                "overall_average": overall_avg,
                "level": level,
                "class_average": class_avg,
                "total_assessments": len(all_grades),
            },
            "gauge_data": {"value": overall_avg, "level": level},
            "line_chart_data": line_chart_data,
            "radar_data": radar_data,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "follow_up": {
                "score": round(follow_up_score, 1),
                "status": follow_up_status,
                "breakdown": {
                    "attendance_rate": att_rate,
                    "homework_rate": homework_rate,
                    "participation_score": round(min(total_participation, 50) / 50 * 100, 1),
                    "academic_average": overall_avg,
                }
            }
        }

    # ============= OPEN REQUESTS COUNT =============

    @router.get("/open-requests-count")
    async def get_open_requests_count(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        open_messages = await gd_count(db.session, "messages", {
            "sender_id": parent_id,
            "status": {"$in": ["open", "pending", "sent"]}
        })
        open_excuses = await gd_count(db.session, "absence_excuses", {
            "parent_id": parent_id,
            "status": {"$in": ["pending", "submitted"]}
        })
        open_meetings = await gd_count(db.session, "meeting_requests", {
            "parent_id": parent_id,
            "status": {"$in": ["pending", "submitted"]}
        })
        total_open = open_messages + open_excuses + open_meetings
        # The hard 3-open-request cap was removed (messages stayed "sent"
        # forever, permanently locking parents out). Counts are still
        # returned for display; ``limit``/``can_submit`` are kept for
        # backwards compatibility with older clients.
        return {
            "total_open": total_open,
            "limit": None,
            "can_submit": True,
            "breakdown": {
                "messages": open_messages,
                "excuses": open_excuses,
                "meetings": open_meetings,
            }
        }

    # ============= MESSAGE RECIPIENTS (teachers of parent's children) =============

    async def _resolve_parent_teacher_recipients(current_user: dict) -> dict:
        """Resolve the set of teacher *user* accounts that the authenticated
        parent is allowed to message. Walks parent → children → the child's
        current class schedule (``schedule_sessions``, the canonical live
        timetable table) → teachers.user_id → users(role=teacher,
        tenant_id=school_id, is_active=true). Returns a dict:
        {"teachers": [{recipient_user_id, teacher_name, child_ids: [..],
        child_labels: [..]}], "children": [{student_id, name}]}. Never
        includes cross-tenant users; on resolution ambiguity, omits the
        entry.

        NOTE: the recipient set is the union of two schedule sources:

        1. ``schedule_sessions`` (legacy live timetable table), scoped by
           both class and tenant, minus cancelled/deleted periods (see
           ``_active_schedule_sessions``).
        2. ``timetable_sessions`` rows anchored to the school's LATEST
           PUBLISHED ``timetables`` row (the modern smart-engine store).
           Classes scheduled by the modern engine have NO
           ``schedule_sessions`` rows at all, so without this source their
           parents saw an empty recipient list.

        ``timetable_sessions`` must NEVER be queried by class alone — it
        accumulates rows per historical timetable run, so an unanchored
        query returns every teacher ever associated with the class
        (over-disclosure). Anchoring to the single latest published
        timetable keeps the set equal to the child's current schedule.
        See docs/qa/2026-05-31-parent-dropdowns-audit.md (Finding 1)."""
        school_id = current_user.get("tenant_id")
        if not school_id:
            return {"teachers": [], "children": []}
        children = await _find_children(current_user, current_user.get("phone"), school_id)
        # Keep only children in this tenant. ALL tenant-scoped children are
        # returned (even without a class) so the admin flow can attach any
        # child; only classed children feed the teacher mapping.
        children_out: list = []
        seen_child_ids: set = set()
        class_to_children: dict = {}  # class_id -> [(student_id, label), ...]
        for child in children:
            if child.get("school_id") and child.get("school_id") != school_id:
                continue
            sid = child.get("id")
            label = child.get("full_name") or child.get("name") or ""
            if sid and sid not in seen_child_ids:
                seen_child_ids.add(sid)
                children_out.append({"student_id": sid, "name": label})
            cid = child.get("class_id")
            if not cid:
                continue
            class_to_children.setdefault(cid, []).append((sid, label))
        if not class_to_children:
            return {"teachers": [], "children": children_out}
        class_ids = list(class_to_children.keys())
        # Source 1: ``schedule_sessions`` (legacy live timetable table),
        # scoped by BOTH class and tenant.
        sessions = await gd_find(db.session, "schedule_sessions",
                                 {"class_id": {"$in": class_ids},
                                  "school_id": school_id}, limit=2000)
        # ...minus cancelled/deleted periods, which never make a teacher
        # messageable.
        sessions = _active_schedule_sessions(sessions)
        teacher_to_classes: dict = {}
        for s in sessions:
            tid = s.get("teacher_id")
            cid = s.get("class_id")
            if not tid or not cid:
                continue
            teacher_to_classes.setdefault(tid, set()).add(cid)
        # Source 2: the modern smart-engine store. Classes scheduled by the
        # modern engine have no ``schedule_sessions`` rows; their current
        # teachers live in ``timetable_sessions`` anchored to the school's
        # latest PUBLISHED timetable. Anchoring to that single timetable (and
        # never querying by class alone) preserves the anti-over-disclosure
        # decision in the docstring / audit Finding 1.
        published = await gd_find(
            db.session, "timetables",
            {"school_id": school_id, "status": "published"},
            order_by="published_at", desc_order=True, limit=10,
        )
        if published:
            published.sort(
                key=lambda r: (str(r.get("published_at") or ""),
                               str(r.get("updated_at") or "")),
                reverse=True,
            )
            tt_id = published[0].get("id")
            if tt_id:
                tt_sessions = await gd_find(
                    db.session, "timetable_sessions",
                    {"timetable_id": tt_id, "class_id": {"$in": class_ids}},
                    limit=2000,
                )
                for s in tt_sessions:
                    tid = s.get("teacher_id")
                    cid = s.get("class_id")
                    if not tid or not cid:
                        continue
                    teacher_to_classes.setdefault(tid, set()).add(cid)
        if not teacher_to_classes:
            return {"teachers": [], "children": children_out}
        teacher_ids = list(teacher_to_classes.keys())
        # Bulk-resolve teachers -> user_id in this tenant
        teacher_rows = await gd_find(db.session, "teachers",
                                     {"id": {"$in": teacher_ids},
                                      "school_id": school_id,
                                      "is_active": True},
                                     limit=1000)
        user_ids = [t.get("user_id") for t in teacher_rows if t.get("user_id")]
        if not user_ids:
            return {"teachers": [], "children": children_out}
        # ``independent_teacher`` is included because in an IT workspace the
        # workspace owner IS the child's teacher (same teachers-row +
        # schedule_sessions chain), just under a different user role.
        users = await gd_find(db.session, "users",
                              {"id": {"$in": user_ids},
                               "role": {"$in": ["teacher", "independent_teacher"]},
                               "is_active": True},
                              limit=1000)
        # Tenant proof is the school-pinned teachers row resolved above; the
        # nullable users.tenant_id only rejects a FOREIGN tenant.
        users_by_id = {
            u["id"]: u for u in users
            if u.get("id") and _teacher_user_in_tenant(u, school_id)
        }
        seen: set = set()
        recipients = []
        for t in teacher_rows:
            uid = t.get("user_id")
            if not uid or uid in seen:
                continue
            user = users_by_id.get(uid)
            if not user:
                continue
            child_pairs = []
            for cid in teacher_to_classes.get(t.get("id"), set()):
                child_pairs.extend(class_to_children.get(cid, []))
            # Dedupe child ids/labels preserving order
            seen_ids_local = set()
            seen_labels = set()
            uniq_ids = []
            uniq_labels = []
            for sid, lbl in child_pairs:
                if sid and sid not in seen_ids_local:
                    seen_ids_local.add(sid)
                    uniq_ids.append(sid)
                if lbl and lbl not in seen_labels:
                    seen_labels.add(lbl)
                    uniq_labels.append(lbl)
            recipients.append({
                "recipient_user_id": uid,
                # The teachers row is the authoritative academic identity (it
                # is what the Teachers page / schedule / lesson report show);
                # a divergent users.full_name would surface a name the parent
                # has never seen next to their child's class.
                "teacher_name": t.get("full_name") or user.get("full_name") or "",
                "child_ids": uniq_ids,
                "child_labels": uniq_labels,
            })
            seen.add(uid)
        recipients.sort(key=lambda r: r.get("teacher_name") or "")
        return {"teachers": recipients, "children": children_out}

    @router.get("/message-recipients/teachers")
    async def list_message_recipient_teachers(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """Return the teachers a parent is allowed to message (teachers of
        the parent's children's classes, in the same tenant) plus the
        parent's children so the UI can run the child-first flow."""
        return await _resolve_parent_teacher_recipients(current_user)

    async def _resolve_admin_recipient(school_id: str) -> Optional[dict]:
        """Deterministically resolve the principal user for a tenant. Prefers
        the earliest-created active school_principal; falls back to the
        earliest-created active school_admin if no principal exists."""
        if not school_id:
            return None
        principals = await gd_find(
            db.session, "users",
            {"tenant_id": school_id, "role": "school_principal", "is_active": True},
            order_by="created_at", desc_order=False, limit=1,
        )
        if principals:
            return principals[0]
        admins = await gd_find(
            db.session, "users",
            {"tenant_id": school_id, "role": "school_admin", "is_active": True},
            order_by="created_at", desc_order=False, limit=1,
        )
        if admins:
            return admins[0]
        # Independent-Teacher workspace: principals/admins never exist there —
        # the workspace owner IS the administration. Strictly gated on the
        # schools-row discriminator (tenant_type/school_type) so real schools
        # without an admin stay fail-closed (503), never a silent fallback.
        school = await gd_find_one(db.session, "schools", {"id": school_id})
        if school and (
            school.get("tenant_type") == "independent_teacher"
            or school.get("school_type") == "independent_teacher"
        ):
            owners = await gd_find(
                db.session, "users",
                {"tenant_id": school_id, "role": "independent_teacher",
                 "is_active": True},
                order_by="created_at", desc_order=False, limit=1,
            )
            if owners:
                return owners[0]
        return None

    # ============= QUICK MESSAGE (Communication Center) =============

    @router.post("/quick-message")
    async def send_quick_message(
        data: dict,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        school_id = current_user.get("tenant_id")
        content = (data.get("content") or "").strip()
        message_type = data.get("message_type", "note")
        recipient_type = data.get("recipient_type", "admin")
        student_id = (data.get("student_id") or "").strip()

        if not content:
            raise HTTPException(status_code=400, detail="محتوى الرسالة مطلوب")
        if not student_id:
            raise HTTPException(status_code=400, detail="يرجى تحديد الطالب المعني بالرسالة")

        # Child-first flow (spec 2026-07-10): the message must reference one
        # of the caller's own tenant-scoped children — fail closed.
        resolved = await _resolve_parent_teacher_recipients(current_user)
        child_names = {c["student_id"]: c["name"] for c in resolved["children"]}
        if student_id not in child_names:
            raise HTTPException(status_code=400, detail="الطالب المحدد غير متاح")
        student_name = child_names[student_id]

        receiver = None
        if recipient_type == "admin":
            receiver = await _resolve_admin_recipient(school_id)
            if not receiver:
                raise HTTPException(
                    status_code=503,
                    detail="لا يوجد مسؤول متاح لاستلام الرسالة حالياً"
                )
        elif recipient_type == "teacher":
            requested_uid = (data.get("recipient_user_id") or "").strip()
            if not requested_uid:
                raise HTTPException(status_code=400, detail="المعلم المحدد غير متاح للمراسلة")
            allowed_row = next(
                (r for r in resolved["teachers"]
                 if r["recipient_user_id"] == requested_uid),
                None,
            )
            # The chosen teacher must actually teach THE selected child, not
            # just any of the parent's children.
            if not allowed_row or student_id not in (allowed_row.get("child_ids") or []):
                raise HTTPException(status_code=400, detail="المعلم المحدد غير متاح للمراسلة")
            receiver = await gd_find_one(db.session, "users", {
                "id": requested_uid,
                "role": {"$in": ["teacher", "independent_teacher"]},
                "is_active": True,
            })
            # Same tenant rule as the recipient list: the school-pinned
            # teachers row (already proven by ``allowed_row``) is the tenant
            # anchor; a users row from ANOTHER tenant is still rejected.
            if not receiver or not _teacher_user_in_tenant(receiver, school_id):
                raise HTTPException(status_code=400, detail="المعلم المحدد غير متاح للمراسلة")
        else:
            raise HTTPException(status_code=400, detail="نوع المستلم غير صالح")

        receiver_id = receiver.get("id", "")
        receiver_name = receiver.get("full_name") or receiver.get("name", "") or ""

        type_labels = {"note": "ملاحظة", "suggestion": "اقتراح", "inquiry": "استفسار"}
        subject = (
            type_labels.get(message_type, "رسالة")
            + f" من ولي الأمر {current_user.get('full_name', '')}"
            + f" بخصوص الطالب {student_name}"
        )

        now_iso = datetime.now(timezone.utc).isoformat()
        message = {
            "id": str(uuid.uuid4()),
            "subject": subject,
            # ``title`` mirrors the subject: the Communication Center inbox
            # renders ``msg.title``.
            "title": subject,
            "body": content,
            "content": content,
            "sender_id": parent_id,
            "sender_name": current_user.get("full_name"),
            "sender_role": "parent",
            "recipient_id": receiver_id,
            "receiver_id": receiver_id,
            "receiver_name": receiver_name,
            "student_id": student_id,
            "student_name": student_name,
            "message_type": message_type,
            "is_read": False,
            "read_status": False,
            "status": "sent",
            # audience="custom" + audience_ids + sent_at make the row appear
            # in the recipient's /communication/received inbox (previously
            # the body was unreachable — only a subject-line notification).
            "audience": "custom",
            "audience_ids": [receiver_id],
            "sent_at": now_iso,
            "school_id": school_id,
            "created_at": now_iso,
        }
        await gd_insert(db.session, "messages", message)

        if receiver_id:
            await gd_insert(db.session, "notifications", {
                "id": str(uuid.uuid4()),
                "user_id": receiver_id,
                "recipient_id": receiver_id,
                "tenant_id": school_id,
                "type": "message",
                "notification_type": "message",
                "title": f"رسالة جديدة من ولي أمر: {current_user.get('full_name')} بخصوص الطالب {student_name}",
                "message": content,
                "is_read": False,
                "read_status": False,
                "created_at": now_iso,
            })

        return {"success": True, "message": "تم استلام رسالتكم، رضاكم محل اهتمامنا"}

    # ============= MESSAGES =============

    @router.get("/messages")
    async def get_parent_messages(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """رسائل ولي الأمر"""
        parent_user_id = current_user.get("id")
        parent_record_id = current_user.get("parent_id")
        school_id = current_user.get("tenant_id")

        p_ids = [parent_user_id]
        if parent_record_id and parent_record_id != parent_user_id:
            p_ids.append(parent_record_id)

        msg_query = {
            "$or": [
                {"sender_id": {"$in": p_ids}},
                {"receiver_id": {"$in": p_ids}},
                {"recipient_id": {"$in": p_ids}},
                {"recipient_ids": {"$in": p_ids}},
                {"user_id": {"$in": p_ids}},
            ]
        }
        if school_id:
            msg_query["school_id"] = school_id
        messages = await gd_find(db.session, "messages", msg_query, order_by="created_at", desc_order=True, limit=100)

        return {
            "messages": [
                {
                    "id": m.get("id"),
                    "subject": m.get("subject") or m.get("title", ""),
                    "content": m.get("content") or m.get("body") or m.get("message", ""),
                    "sender_id": m.get("sender_id"),
                    "sender_name": m.get("sender_name") or "إدارة المدرسة",
                    "sender_type": m.get("sender_type"),
                    "receiver_id": m.get("receiver_id") or m.get("recipient_id"),
                    "receiver_name": m.get("receiver_name"),
                    "student_name": m.get("student_name"),
                    "type": m.get("type", "note"),
                    "is_sent": m.get("sender_id") in p_ids,
                    "read_status": m.get("read_status", False) or m.get("is_read", False),
                    "created_at": m.get("created_at")
                }
                for m in messages
            ]
        }

    @router.post("/messages")
    async def send_parent_message(
        receiver_id: str,
        subject: str,
        content: str,
        child_id: Optional[str] = None,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """هذا المسار القديم مغلق — يُرجى استخدام /parent-portal/quick-message"""
        raise HTTPException(
            status_code=410,
            detail="هذا المسار غير متاح. يُرجى استخدام نقطة النهاية المعتمدة /parent-portal/quick-message"
        )

    # ============= CHILD TEACHERS =============

    @router.get("/child/{child_id}/teachers")
    async def get_child_teachers(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """معلمي الابن"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"), current_user=current_user)

        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        school_id = child.get("school_id")
        teachers = []

        if child.get("class_id"):
            timetable = await gd_find_one(db.session, "timetables", {"school_id": school_id, "status": "published"}) or await gd_find_one(db.session, "timetables", {"school_id": school_id},
                sort=[("created_at", -1)])
            if timetable:
                sessions = await gd_find(db.session, "timetable_sessions", {
                        "timetable_id": timetable.get("id"),
                        "class_id": child.get("class_id")
                    }, limit=500)

                teacher_subject_map = {}
                for s in sessions:
                    tid = s.get("teacher_id")
                    sid = s.get("subject_id")
                    if tid:
                        if tid not in teacher_subject_map:
                            teacher_subject_map[tid] = set()
                        if sid:
                            teacher_subject_map[tid].add(sid)

                if teacher_subject_map:
                    sub_ids = list(set(sid for sids in teacher_subject_map.values() for sid in sids))
                    subs = await gd_find(db.session, "subjects", {"id": {"$in": sub_ids}}, limit=100)
                    sub_name_map = build_subject_name_map(subs)

                    teacher_docs = await gd_find(db.session, "teachers", {"id": {"$in": list(teacher_subject_map.keys())}, "school_id": school_id}, limit=100)

                    for t in teacher_docs:
                        tid = t.get("id")
                        subject_names = [sub_name_map.get(sid, "") for sid in teacher_subject_map.get(tid, set()) if sub_name_map.get(sid)]
                        teachers.append({
                            "id": tid,
                            "name": t.get("full_name"),
                            "subjects": subject_names,
                            "email": t.get("email"),
                            "profile_picture": t.get("profile_picture")
                        })

        return {
            "child_name": child.get("full_name"),
            "teachers": teachers
        }

    @router.get("/child/{child_id}/progress-report")
    async def get_child_progress_report(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """تقرير تقدم الطفل الشامل"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"), current_user=current_user)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لهذا الطالب")

        present = await _att_count(db.session, {"student_id": child_id, "status": "present"})
        absent = await _att_count(db.session, {"student_id": child_id, "status": "absent"})
        late = await _att_count(db.session, {"student_id": child_id, "status": "late"})
        _pr_school_id = child.get("school_id") or current_user.get("tenant_id")
        _pr_class_id = child.get("class_id")
        if _pr_class_id and _pr_school_id:
            total_attendance = len(await _att_distinct_days(
                db.session,
                {"school_id": _pr_school_id, "class_id": _pr_class_id},
            ))
        else:
            total_attendance = await _att_count(db.session, {"student_id": child_id})
        attendance_rate = round(((present + late) / total_attendance * 100), 1) if total_attendance > 0 else None

        grades = await gd_find(db.session, "grades", {"student_id": child_id}, limit=500)
        subjects_grades = {}
        for g in grades:
            subj = g.get("subject_name") or g.get("subject_id", "عام")
            if subj not in subjects_grades:
                subjects_grades[subj] = []
            subjects_grades[subj].append(g.get("percentage", 0))

        subject_averages = {}
        for subj, scores in subjects_grades.items():
            subject_averages[subj] = round(sum(scores) / len(scores), 1) if scores else 0

        # Single authoritative overall_average path: arithmetic mean of raw
        # grade percentages (matches /grades and /analytics). The previous
        # mean-of-subject-means produced a different number for the same
        # student. (Audit 2026-05-10.)
        overall_avg = round(sum(g.get("percentage", 0) for g in grades) / len(grades), 1) if grades else None

        behaviour_pos = await gd_count(db.session, "behaviour_records", {"student_id": child_id, "type": "positive"})
        behaviour_neg = await gd_count(db.session, "behaviour_records", {"student_id": child_id, "type": "negative"})
        behaviour_total = behaviour_pos + behaviour_neg

        participation = await gd_find(db.session, "participation_records", {"student_id": child_id}, limit=500)
        total_participation_points = sum(p.get("points", 0) for p in participation)

        return {
            "student": {
                "id": child_id,
                "name": child.get("full_name"),
                "class": child.get("class_name"),
                "grade_level": child.get("grade_level")
            },
            "attendance": {
                "total_days": total_attendance,
                "present": present,
                "absent": absent,
                "late": late,
                "rate": attendance_rate
            },
            "academics": {
                "overall_average": overall_avg,
                "subject_averages": subject_averages,
                "total_assessments": len(grades)
            },
            "behaviour": {
                "positive": behaviour_pos,
                "negative": behaviour_neg,
                "total": behaviour_total,
                "ratio": round(behaviour_pos / max(1, behaviour_total) * 100, 1)
            },
            "participation": {
                "total_records": len(participation),
                "total_points": total_participation_points
            }
        }

    @router.get("/child/{child_id}/behaviour")
    async def get_child_behaviour(
        child_id: str,
        limit: int = 20,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """سجل سلوك الطفل"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"), current_user=current_user)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح")

        records = await gd_find(db.session, "behaviour_records", {"student_id": child_id}, order_by="created_at", desc_order=True, limit=limit)

        return {"records": records, "total": len(records)}

    # ============= CHILD HOMEWORK =============

    @router.get("/child/{child_id}/homework")
    async def get_child_homework(
        child_id: str,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")

        child = await _verify_parent_access(parent_id, parent_phone, child_id, current_user.get("tenant_id"), current_user=current_user)
        if not child:
            raise HTTPException(status_code=403, detail="غير مصرح")

        school_id = child.get("school_id")
        class_id = child.get("class_id")
        grade_id = child.get("grade_id") or child.get("grade")

        query = {"school_id": school_id, "is_active": True}
        if class_id:
            query["$or"] = [
                {"class_ids": class_id},
                {"class_id": class_id},
                {"grade_id": grade_id}
            ]

        assignments = await gd_find(db.session, "student_assignments", query, order_by="due_date", desc_order=True, limit=100)

        submissions = await gd_find(db.session, "assignment_submissions", {"student_id": child_id}, limit=500)
        submission_map = {s.get("assignment_id"): s for s in submissions}

        now = datetime.now(timezone.utc)
        result = []
        for a in assignments:
            aid = a.get("id")
            sub = submission_map.get(aid)
            due_str = a.get("due_date")
            try:
                if isinstance(due_str, str):
                    due = datetime.fromisoformat(due_str.replace('Z', '+00:00'))
                else:
                    due = due_str or (now + timedelta(days=7))
            except Exception as e:
                logger.debug(f"Failed to parse due_date '{due_str}': {e}")
                due = now + timedelta(days=7)

            if sub:
                st = "graded" if sub.get("grade") is not None else "submitted"
            elif due < now:
                st = "late"
            else:
                st = "pending"

            result.append({
                "id": aid,
                "title": a.get("title", ""),
                "subject_id": a.get("subject_id"),
                "due_date": due_str,
                "status": st,
                "grade": sub.get("grade") if sub else None,
                "submission_date": sub.get("submitted_at") if sub else None,
            })

        # ── Lesson-recorded homework (teacher follow-up sheet) ────────────────
        # The الواجبات tab must ALSO reflect homework the teacher marks during a
        # live lesson ("سلم"/"لم يسلم"), stored in `session_homework`
        # (status "done"/"not_done"). That is a different data model from the
        # digital `student_assignments` posts above, so without this merge the
        # parent saw 0/0 even after the teacher recorded submissions. We add the
        # lesson records to the same list (mapped to submitted/not_submitted) so
        # the summary counters and the entries both reflect real teacher input.
        lesson_hw = await gd_find(
            db.session, "session_homework", {"student_id": child_id},
            order_by="recorded_at", desc_order=True, limit=200
        )
        if lesson_hw:
            sess_ids = list({h.get("session_id") for h in lesson_hw if h.get("session_id")})
            sess_rows = await gd_find(
                db.session, "class_sessions", {"id": {"$in": sess_ids}}, limit=len(sess_ids)
            ) if sess_ids else []
            sess_map = {s.get("id"): s for s in sess_rows}
            subj_ids = list({
                (sess_map.get(h.get("session_id")) or {}).get("subject_id")
                for h in lesson_hw
            } - {None, ""})
            subj_rows = await gd_find(
                db.session, "subjects", {"id": {"$in": subj_ids}}, limit=len(subj_ids)
            ) if subj_ids else []
            subj_map = {
                s.get("id"): (s.get("name_ar") or s.get("name") or s.get("name_en") or "")
                for s in subj_rows
            }
            for h in lesson_hw:
                status = h.get("status")
                # Only the two known lesson-homework states map to this view.
                if status not in ("done", "not_done"):
                    continue
                sess = sess_map.get(h.get("session_id"))
                # Skip rows whose session cannot be resolved: their tenant can't
                # be proven, so they must not be surfaced to the parent.
                if not sess:
                    continue
                # Defense-in-depth: never surface a session from another tenant.
                sess_school = sess.get("school_id") or sess.get("tenant_id")
                if sess_school and school_id and sess_school != school_id:
                    continue
                done = status == "done"
                subj_id = sess.get("subject_id")
                subj_name = subj_map.get(subj_id) or sess.get("subject_name") or ""
                title = ("واجب " + subj_name).strip()
                result.append({
                    "id": h.get("id") or f"sess:{h.get('session_id')}:hw",
                    "title": title,
                    "subject_id": subj_id,
                    "due_date": sess.get("date") or h.get("recorded_at") or "",
                    "status": "submitted" if done else "not_submitted",
                    "grade": None,
                    "submission_date": h.get("recorded_at") if done else None,
                    "source": "lesson",
                })

        # Newest homework first regardless of source (digital due_date or lesson date).
        result.sort(key=lambda a: a.get("due_date") or "", reverse=True)

        def _count(*statuses):
            return len([a for a in result if a["status"] in statuses])

        return {
            "child_name": child.get("full_name"),
            "assignments": result,
            "statistics": {
                "pending": _count("pending"),
                "submitted": _count("submitted"),
                "graded": _count("graded"),
                "late": _count("late"),
                "not_submitted": _count("not_submitted"),
            }
        }

    @router.get("/settings")
    async def get_parent_settings(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """إعدادات ولي الأمر"""
        settings = await gd_find_one(db.session, "user_preferences", {"user_id": current_user["id"]}) or {}

        return {
            "notification_preferences": settings.get("notification_preferences", {
                "email": True,
                "sms": True,
                "push": True,
                "attendance_alerts": True,
                "grade_alerts": True,
                "behaviour_alerts": True
            }),
            "language": settings.get("language", "ar"),
            "timezone": settings.get("timezone", "Asia/Riyadh")
        }

    @router.put("/settings")
    async def update_parent_settings(
        data: dict,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """تحديث إعدادات ولي الأمر"""
        now = datetime.now(timezone.utc).isoformat()

        await gd_upsert(
            db.session,
            "user_preferences",
            {"user_id": current_user["id"]},
            {**data, "user_id": current_user["id"], "updated_at": now},
        )

        return {"message": "تم تحديث الإعدادات بنجاح"}

    @router.get("/notifications")
    async def get_parent_notifications(
        limit: int = 20,
        unread_only: bool = False,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """إشعارات ولي الأمر"""
        query = {"recipient_id": current_user["id"]}
        if unread_only:
            query["read_status"] = False

        notifications = await gd_find(db.session, "notifications", query, order_by="created_at", desc_order=True, limit=limit)

        unread_count = await gd_count(db.session, "notifications", {"recipient_id": current_user["id"], "read_status": False})

        return {"notifications": notifications, "unread_count": unread_count}

    # ============= REPORTS =============

    @router.get("/reports")
    async def get_parent_reports(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        """تقارير ولي الأمر - ملخص لجميع الأبناء"""
        parent_id = current_user.get("id")
        parent_phone = current_user.get("phone")
        school_id = current_user.get("tenant_id")

        students = await _find_children(current_user, parent_phone, school_id)

        # ------------------------------------------------------------------
        # Batched enrichment (was N+1: per student 4 attendance COUNTs + one
        # grades fetch + one behaviour fetch). Replaced with one grouped
        # attendance count, one grades fetch, one behaviour fetch — all split
        # in memory. Attendance is scoped by student_id only (no school scope),
        # mirroring the original _att_count filters exactly.
        # ------------------------------------------------------------------
        _student_ids = [s.get("id") for s in students if s.get("id")]

        # (1) status row counts per (student_id, status) — one grouped query
        #     replaces total/present/absent/late COUNTs per student. total_att
        #     mirrors _att_count({student_id}) = sum over all statuses.
        _att_by_student: dict = {}
        if _student_ids:
            _att_rows = (await db.session.execute(
                sa_text(
                    "SELECT student_id, status, COUNT(id) AS cnt "
                    "FROM attendance WHERE student_id IN :stids "
                    "GROUP BY student_id, status"
                ).bindparams(bindparam("stids", expanding=True)),
                {"stids": _student_ids},
            )).all()
            for r in _att_rows:
                _att_by_student.setdefault(r[0], {})[r[1]] = int(r[2])

        # (2) One grades fetch for all students, split in memory.
        _grades_by_student: dict = {}
        if _student_ids:
            _grades_all = await gd_find(
                db.session, "grades", {"student_id": {"$in": _student_ids}}, limit=500 * len(_student_ids)
            )
            for g in _grades_all:
                _grades_by_student.setdefault(g.get("student_id"), []).append(g)

        # (3) One behaviour fetch for all students, split in memory.
        _behaviour_by_student: dict = {}
        if _student_ids:
            _beh_all = await gd_find(
                db.session, "behaviour_records", {"student_id": {"$in": _student_ids}}, limit=200 * len(_student_ids)
            )
            for b in _beh_all:
                _behaviour_by_student.setdefault(b.get("student_id"), []).append(b)

        reports = []
        for s in students:
            sid = s.get("id")

            _status_counts = _att_by_student.get(sid, {})
            present = _status_counts.get("present", 0)
            absent = _status_counts.get("absent", 0)
            late = _status_counts.get("late", 0)
            total_att = sum(_status_counts.values())
            att_rate = round((present / total_att * 100), 1) if total_att > 0 else 0

            grades = _grades_by_student.get(sid, [])
            avg_grade = 0
            if grades:
                avg_grade = round(sum(g.get("percentage", 0) for g in grades) / len(grades), 1)

            behaviour_records = _behaviour_by_student.get(sid, [])
            positive = sum(1 for b in behaviour_records if b.get("category") in ["positive", "إيجابي"])
            negative = sum(1 for b in behaviour_records if b.get("category") in ["negative", "سلبي"])

            reports.append({
                "student_id": sid,
                "student_name": s.get("full_name", s.get("name", "")),
                "grade": s.get("grade_level", s.get("grade", "")),
                "class_name": s.get("class_name", ""),
                "attendance": {
                    "rate": att_rate,
                    "present": present,
                    "absent": absent,
                    "late": late,
                    "total": total_att
                },
                "academic": {
                    "average_grade": avg_grade,
                    "total_grades": len(grades)
                },
                "behaviour": {
                    "positive": positive,
                    "negative": negative,
                    "total": len(behaviour_records)
                }
            })

        return {"reports": reports, "total": len(reports)}

    # ============= ABSENCE EXCUSES =============

    @router.post("/absence-excuse")
    async def submit_absence_excuse(
        data: dict,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        school_id = current_user.get("tenant_id")

        child_id = data.get("child_id")
        absence_date = data.get("absence_date")
        reason = data.get("reason", "").strip()

        if not child_id or not absence_date or not reason:
            raise HTTPException(status_code=400, detail="child_id, absence_date, and reason are required")

        children = await _find_children(current_user, current_user.get("phone"), school_id)
        child_ids = [c.get("id") for c in children]
        if child_id not in child_ids:
            raise HTTPException(status_code=403, detail="Child not linked to this parent")

        child = next((c for c in children if c.get("id") == child_id), {})

        excuse = {
            "id": str(uuid.uuid4()),
            "parent_id": parent_id,
            "parent_name": current_user.get("full_name", ""),
            "child_id": child_id,
            "child_name": child.get("full_name", child.get("name", "")),
            "school_id": school_id,
            "absence_date": absence_date,
            "reason": reason,
            "attachment_url": data.get("attachment_url"),
            "attachment_name": data.get("attachment_name"),
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await gd_insert(db.session, "absence_excuses", excuse)
        excuse.pop("_id", None)
        return {"message": "تم إرسال العذر بنجاح", "excuse": excuse}

    @router.post("/upload-attachment")
    async def upload_attachment(
        file: UploadFile = File(...),
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        import base64
        MAX_SIZE = 5 * 1024 * 1024
        ALLOWED_TYPES = {
            "image/jpeg", "image/png", "image/gif", "image/webp",
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }

        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail="صيغة الملف غير مدعومة")

        content = await file.read()
        if len(content) > MAX_SIZE:
            raise HTTPException(status_code=400, detail="حجم الملف يتجاوز الحد المسموح (5 ميغابايت)")

        encoded = base64.b64encode(content).decode('utf-8')
        data_url = f"data:{file.content_type};base64,{encoded}"

        return {
            "success": True,
            "attachment_url": data_url,
            "attachment_name": file.filename,
        }

    @router.get("/absence-excuses")
    async def get_absence_excuses(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        excuses = await gd_find(db.session, "absence_excuses", {"parent_id": parent_id}, order_by="created_at", desc_order=True, limit=100)
        return {"excuses": excuses, "total": len(excuses)}

    # ============= MEETING REQUESTS =============

    @router.post("/meeting-request")
    async def submit_meeting_request(
        data: dict,
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        school_id = current_user.get("tenant_id")

        preferred_date = data.get("preferred_date")
        preferred_time = data.get("preferred_time")
        topic = data.get("topic", "").strip()
        contact_preference = data.get("contact_preference", "in_person")

        if not preferred_date or not topic:
            raise HTTPException(status_code=400, detail="preferred_date and topic are required")

        meeting = {
            "id": str(uuid.uuid4()),
            "parent_id": parent_id,
            "parent_name": current_user.get("full_name", ""),
            "parent_phone": current_user.get("phone", ""),
            "parent_email": current_user.get("email", ""),
            "school_id": school_id,
            "preferred_date": preferred_date,
            "preferred_time": preferred_time or "",
            "topic": topic,
            "details": data.get("details", "").strip(),
            "contact_preference": contact_preference,
            "status": "pending",
            "admin_notes": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await gd_insert(db.session, "meeting_requests", meeting)
        meeting.pop("_id", None)
        return {"message": "تم إرسال طلب الاجتماع بنجاح", "meeting": meeting}

    @router.get("/meeting-requests")
    async def get_meeting_requests(
        current_user: dict = Depends(require_roles([UserRole.PARENT]))
    ):
        parent_id = current_user.get("id")
        meetings = await gd_find(db.session, "meeting_requests", {"parent_id": parent_id}, order_by="created_at", desc_order=True, limit=100)
        return {"meetings": meetings, "total": len(meetings)}

    return router
