"""
Schedule Master Grid Routes — مصفوفة الجداول الذكية الموحَّدة.

تُرجع كل البيانات اللازمة لعرض شاشة "إدارة الجداول الذكية":
- صفوف المعلمين × أعمدة (الأيام × الحصص).
- مؤشرات الأداء (KPIs): عدالة التوزيع، انتظار مُسند، معلم غائب، حصة شاغرة.
- تنبيه ديناميكي عند وجود حصص شاغرة.

تعتمد على المخازن الحالية (timetables, timetable_sessions, teachers, classes,
teacher_attendance) ولا تعدِّل أي endpoint قائم.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response

from dependencies import db, get_current_user
from engines.sql_utils import gd_count, gd_find, gd_find_one
from engines.timetable_session_lifecycle import find_live_timetable_sessions
from src.common.utils.tenant_scope import assert_school_access, resolve_school_id

logger = logging.getLogger("nassaq.schedule_master_grid")
router = APIRouter()


DAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday"]

# خرائط ترجمة أسماء الأيام: نموذج عدم التوفر يحفظ اليوم بالعربية
# (الأحد..الخميس)، أما الجلسات في timetable_sessions فتُخزَّن بالإنجليزية
# (sunday..thursday). نوحّد الاتجاهين عبر هذه الخريطة.
_AR_DAY_TO_EN = {
    "الأحد": "sunday",
    "الإثنين": "monday",
    "الاثنين": "monday",
    "الثلاثاء": "tuesday",
    "الأربعاء": "wednesday",
    "الخميس": "thursday",
    "الجمعة": "friday",
    "السبت": "saturday",
}
# DEFAULT_PERIODS هو fallback نهائي فقط عند تعذّر قراءة إعدادات المدرسة.
# في كل طلب نستخرج عدد الحصص الفعلي من school_settings.periods_per_day أو
# من time_slots المعرّفة لكل مدرسة — لا نفترض 7 حصص بعد الآن.
DEFAULT_PERIODS = list(range(1, 8))


async def _resolve_periods_for_school(school_id: str) -> list[int]:
    """Resolve the 1..N teaching periods for a school dynamically.

    Order of resolution (first non-empty wins):
      1. Teaching ``time_slots`` ordered by ``slot_number`` and re-indexed
         to a contiguous 1..N sequence (the master-grid columns are
         positional period indices, not raw slot numbers; raw slot numbers
         have gaps where breaks/prayer live and would emit columns like
         [1,2,3,5,6,7] for a 6-period school with a mid-day break).
      2. ``school_settings.periods_per_day`` → ``range(1, N+1)``.
      3. ``DEFAULT_PERIODS`` (legacy fallback only — should never trigger
         once a school has any saved schedule settings).
    """
    try:
        slots = await gd_find(db.session, "time_slots", {"school_id": school_id}, limit=200)
        teaching_slots: list[dict] = []
        for s in slots:
            slot_type = s.get("type") or ""
            if s.get("is_break") or s.get("is_prayer") or slot_type in ("break", "prayer"):
                continue
            teaching_slots.append(s)
        if teaching_slots:
            # Order by slot_number (then start_time as tiebreaker) and
            # re-index 1..N so breaks never punch holes in the period list.
            def _sort_key(s: dict) -> tuple[int, str]:
                try:
                    sn = int(s.get("slot_number") or 0)
                except (TypeError, ValueError):
                    sn = 0
                return (sn, str(s.get("start_time") or ""))
            teaching_slots.sort(key=_sort_key)
            return list(range(1, len(teaching_slots) + 1))

        settings = await gd_find_one(db.session, "school_settings", {"school_id": school_id})
        if settings:
            ppd = settings.get("periods_per_day")
            try:
                ppd_int = int(ppd) if ppd is not None else 0
            except (TypeError, ValueError):
                ppd_int = 0
            if ppd_int > 0:
                return list(range(1, ppd_int + 1))
    except Exception as _err:
        logger.warning("periods resolution failed for school %s: %s", school_id, _err)

    return list(DEFAULT_PERIODS)


async def _resolve_period_times(school_id: str, periods: list[int]) -> dict[str, dict]:
    """Build {period_number: {start, end}} for the given periods.

    Source order:
      1. ``time_slots`` rows (preferred — already accounts for breaks/prayer).
      2. Computed from ``school_settings`` (start_time + period_duration +
         break_duration + breaks[]) so the grid still shows times even before
         the time_slots table is generated.

    Returns string keys (so it serializes cleanly to JSON / matches the
    ``periods`` array elements after ``String(p)``).
    """
    out: dict[str, dict] = {}
    try:
        slots = await gd_find(db.session, "time_slots", {"school_id": school_id}, limit=200)
        teaching: list[dict] = []
        for s in slots:
            slot_type = s.get("type") or ""
            if s.get("is_break") or s.get("is_prayer") or slot_type in ("break", "prayer"):
                continue
            teaching.append(s)
        if teaching:
            # Re-index by sorted slot_number → contiguous 1..N positions so
            # the keys match what `_resolve_periods_for_school` returns
            # (raw slot_number can have gaps where breaks live).
            def _sort_key(s: dict) -> tuple[int, str]:
                try:
                    sn = int(s.get("slot_number") or 0)
                except (TypeError, ValueError):
                    sn = 0
                return (sn, str(s.get("start_time") or ""))
            teaching.sort(key=_sort_key)
            for idx, s in enumerate(teaching, start=1):
                start = s.get("start_time") or s.get("start") or ""
                end = s.get("end_time") or s.get("end") or ""
                out[str(idx)] = {"start": start, "end": end, "start_time": start, "end_time": end}
            return out

        # Fallback: compute from settings the same way regenerate_time_slots_from_settings does.
        settings = await gd_find_one(db.session, "school_settings", {"school_id": school_id}) or {}
        cs = settings.get("custom_settings") or {}
        nested = settings.get("settings") or {}

        def _pick(*vals, default=None):
            for v in vals:
                if v not in (None, ""):
                    return v
            return default

        day_start = _pick(
            cs.get("school_day_start"), nested.get("school_day_start"),
            settings.get("school_day_start"), settings.get("start_time"),
            default="07:00",
        )
        # Mirror the validation/clamping used by
        # ``regenerate_time_slots_from_settings`` exactly so header times
        # always match the generated time_slots table even before regen runs.
        try:
            parts = str(day_start).split(":")
            if len(parts) != 2 or not (0 <= int(parts[0]) <= 23 and 0 <= int(parts[1]) <= 59):
                day_start = "07:00"
        except (ValueError, AttributeError):
            day_start = "07:00"
        h, m = map(int, day_start.split(":"))

        try:
            period_dur_raw = int(_pick(
                cs.get("period_duration_minutes"), nested.get("period_duration_minutes"),
                settings.get("period_duration_minutes"), settings.get("period_duration"),
                default=45,
            ))
        except (TypeError, ValueError):
            period_dur_raw = 45
        period_dur = min(max(period_dur_raw, 20), 90)

        try:
            break_dur_raw = int(_pick(
                cs.get("break_duration_minutes"), nested.get("break_duration_minutes"),
                settings.get("break_duration_minutes"), settings.get("break_duration"),
                default=15,
            ))
        except (TypeError, ValueError):
            break_dur_raw = 15
        break_dur = min(max(break_dur_raw, 5), 60)

        try:
            prayer_dur_raw = int(_pick(
                cs.get("prayer_duration_minutes"), nested.get("prayer_duration_minutes"),
                default=20,
            ))
        except (TypeError, ValueError):
            prayer_dur_raw = 20
        prayer_dur = min(max(prayer_dur_raw, 5), 60)

        # Map "after period N → duration". Same defaults as regen: break
        # after 3 and prayer after 6 (when periods≥6) if no saved breaks.
        break_after: dict[int, int] = {}
        for b in (settings.get("breaks") or []):
            after = b.get("afterPeriod") or b.get("after_period")
            try:
                after = int(after) if after is not None else None
            except (TypeError, ValueError):
                after = None
            if after:
                try:
                    break_after[after] = int(b.get("duration") or break_dur)
                except (TypeError, ValueError):
                    break_after[after] = break_dur
        if not break_after:
            n_periods = len(periods)
            if n_periods >= 3:
                break_after[3] = break_dur
            if n_periods >= 6:
                break_after[6] = prayer_dur

        passing_time = 5
        cur = h * 60 + m
        for p in periods:
            try:
                p_int = int(p)
            except (TypeError, ValueError):
                continue
            sh, sm = divmod(cur, 60)
            end_min = cur + period_dur
            eh, em = divmod(end_min, 60)
            out[str(p_int)] = {
                "start": f"{sh:02d}:{sm:02d}",
                "end": f"{eh:02d}:{em:02d}",
            }
            cur = end_min
            cur += break_after.get(p_int, passing_time)
    except Exception as _err:
        logger.warning("period_times resolution failed for school %s: %s", school_id, _err)
    return out


def _today_day_key() -> str:
    """Returns the day-of-week key in lowercase English (sunday..saturday)."""
    return datetime.now(timezone.utc).strftime("%A").lower()


def _jains_fairness(values: list[float]) -> float:
    """مؤشر العدالة لـ Jain — يعيد قيمة من 0 إلى 1 (1 = توزيع متساوٍ تماماً)."""
    n = len(values)
    if n == 0:
        return 1.0
    s = sum(values)
    if s <= 0:
        return 1.0
    sq = sum(v * v for v in values)
    if sq <= 0:
        return 1.0
    return (s * s) / (n * sq)


_VALID_RANKS = {"expert", "advanced", "practitioner", "assistant"}

# Default weekly-period caps per rank — mirrors RANK_TOTAL_PERIODS in school_settings_mod.
# Used when a teacher has no explicit weekly_periods set so the master-grid quota cell
# shows the constraint-defined maximum instead of a blank dash.
_RANK_DEFAULT_QUOTA = {
    "expert": 24,
    "advanced": 22,
    "practitioner": 20,
    "assistant": 18,
}

_RANK_ALIASES = {
    "خبير": "expert",
    "متقدم": "advanced",
    "ممارس": "practitioner",
    "مساعد": "assistant",
    "senior": "expert",
    "junior": "assistant",
}


_BARE_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _clean_label(raw) -> str:
    """يُنظِّف تسمية تُعرَض في الجدول (اسم مادة/تخصّص).

    يُرجِع نصاً فارغاً إذا كانت القيمة معرّفاً (UUID) خاماً تسرّب من بيانات
    اختبار/إدخال غير سليم — كي لا تظهر سلسلة UUID مكان الاسم في الواجهة.
    """
    if not raw:
        return ""
    text = str(raw).strip()
    if _BARE_UUID_RE.match(text):
        return ""
    return text


def _normalize_rank(raw) -> str:
    """يُطبِّع قيمة rank المخزّنة كنص حر إلى مفاتيح TeacherRank القانونية.

    يُرجِع نصاً فارغاً إن لم يكن للقيمة معنى — لتجنّب كسر الواجهة.
    """
    if not raw:
        return ""
    val = str(raw).strip().lower()
    if val in _VALID_RANKS:
        return val
    return _RANK_ALIASES.get(val, _RANK_ALIASES.get(str(raw).strip(), ""))


async def _resolve_active_timetable(school_id: str, view: Optional[str] = None) -> Optional[dict]:
    """يختار آخر جدول للمدرسة (مسودة كان أو منشوراً) حسب تاريخ التحديث/الإنشاء.

    السلوك السابق كان يُفضِّل دائماً أحدث جدول منشور حتى لو وُجدت مسودة
    أحدث منه. النتيجة: بعد الضغط على "إنشاء الجدول تلقائياً" يُنشئ المحرك
    مسودة جديدة، لكن الشاشة كانت تظل تعرض الجدول المنشور القديم — وهو ما
    يبدو للمدير وكأن "الجدول لم يتحدّث". الآن نختار الجدول الأحدث فعلياً
    بصرف النظر عن حالته كي تظهر المسودة المُولَّدة فور انتهاء التوليد،
    ويبقى الجدول المنشور هو الظاهر متى لم تُولَّد مسودة بعده.

    المفتاح في الترتيب هو ``updated_at`` ثم ``created_at`` كاحتياط لسجلات
    قديمة ربما لم تكن تحفظ updated_at. نسحب أحدث 5 صفوف ثم نختار الأكبر
    في بايثون، لأن SQL وحده لا يتعامل بسهولة مع NULL coalescing عبر
    طبقة gd_find.
    """
    # Task #141 — explicit view filter. ``view="draft"`` returns the
    # latest DRAFT (or None), ``view="published"`` returns the active
    # PUBLISHED (or None). When ``view`` is omitted we keep the legacy
    # "newest of either" behaviour for backwards-compatibility with
    # callers that have not been updated yet.
    if view == "draft":
        status_filter: Any = "draft"
    elif view == "published":
        status_filter = "published"
    else:
        status_filter = {"$in": ["published", "draft"]}

    rows = await gd_find(
        db.session,
        "timetables",
        {"school_id": school_id, "status": status_filter},
        order_by="updated_at",
        desc_order=True,
        limit=5,
    )
    if not rows:
        return None

    def _ts(t: dict) -> str:
        # نُفضّل updated_at؛ وإن غاب نسقط إلى created_at؛ وإلا سلسلة فارغة.
        return str(t.get("updated_at") or t.get("created_at") or "")

    rows.sort(key=_ts, reverse=True)
    return rows[0]


def _date_matches_today(date_val, today_iso: str) -> bool:
    """يتحقق إن كانت قيمة التاريخ (نص/datetime/date) تخص يوم اليوم."""
    if date_val is None:
        return False
    if isinstance(date_val, str):
        return date_val.startswith(today_iso)
    # datetime / date objects
    iso_method = getattr(date_val, "isoformat", None)
    if callable(iso_method):
        try:
            return iso_method().startswith(today_iso)
        except Exception:
            return False
    return False


async def _absent_teacher_ids_today(
    school_id: str,
    valid_teacher_ids: set[str],
    user_id_to_teacher_id: dict[str, str] | None = None,
) -> dict[str, dict]:
    """يجمع معرفات المعلمين الغائبين اليوم من teacher_attendance أو attendance.

    يطبِّع الحقول: قد يأتي معرف المعلم في `teacher_id` أو `user_id`، وقد يكون
    التاريخ نصاً أو كائن datetime/date. يقتصر على المعرفات المعروفة كمعلمين
    (مع ترجمة `user_id` إلى `teacher_id` عبر `user_id_to_teacher_id`)
    لتجنّب الخلط مع المستخدمين غير المعلمين.

    يعيد قاموساً مفهرساً بـ teacher_id وقيمته بيانات سجل الغياب الأساسية
    (recorded_by / recorded_by_name / recorded_at) كي تتمكّن واجهة الجداول
    من عرض "سجَّله: …" عند تحويم المؤشر فوق شارة "غائب". يبقى الاستخدام
    `tid in absent_ids` صالحاً لأن `dict.__contains__` يفحص المفاتيح.
    """
    today_iso = datetime.now(timezone.utc).date().isoformat()
    absent_meta: dict[str, dict] = {}
    u2t = user_id_to_teacher_id or {}

    def _collect(rows):
        for r in rows:
            if not _date_matches_today(r.get("date"), today_iso):
                continue
            raw = r.get("teacher_id") or r.get("user_id")
            if not raw:
                continue
            # إذا كانت القيمة معرف مستخدم اربطها بمعرف المعلم
            tid = raw if raw in valid_teacher_ids else u2t.get(raw)
            if tid and tid in valid_teacher_ids:
                # نُسجّل بيانات أحدث صف غياب لهذا المعلم اليوم.
                meta = {
                    "recorded_by": r.get("recorded_by"),
                    "recorded_by_name": r.get("recorded_by_name") or "",
                    "recorded_at": r.get("recorded_at") or r.get("updated_at") or r.get("created_at"),
                }
                absent_meta[tid] = meta

    rows1 = await gd_find(
        db.session,
        "teacher_attendance",
        {"school_id": school_id, "status": "absent"},
        limit=2000,
    )
    _collect(rows1)

    if not absent_meta:
        rows2 = await gd_find(
            db.session,
            "attendance",
            {"school_id": school_id, "type": "teacher", "status": "absent"},
            limit=2000,
        )
        _collect(rows2)

    return absent_meta


@router.get("/schedule/master-grid")
async def get_master_grid(
    response: Response,
    school_id: Optional[str] = Query(None, description="معرف المدرسة (اختياري — يُشتق من المستخدم)"),
    view: Optional[str] = Query(None, description="draft | published — يحدد الجدول المعروض"),
    teacher_page: int = Query(1, ge=1, description="صفحة المعلمين (1-indexed) عند تفعيل التقسيم"),
    teacher_page_size: int = Query(0, ge=0, le=500, description="حجم صفحة المعلمين؛ 0 = عرض الكل (السلوك الافتراضي للتوافق)"),
    day: Optional[str] = Query(None, description="sunday..thursday — يُقيّد الجلسات بيوم واحد (وضع يومي)"),
    x_school_context: Optional[str] = Header(None),
    current_user: dict = Depends(get_current_user),
):
    """يُرجع البيانات الكاملة لشاشة المصفوفة الموحَّدة (Master Grid).

    البنية:
    - days: قائمة الأيام (sunday..thursday).
    - periods: قائمة الحصص (1..7).
    - teachers: صفوف المعلمين مع المعلومات (الاسم، التخصص، الرتبة، النصاب،
      عدد الحصص المُسندة، علم الغياب اليوم).
    - cells: قاموس مفهرس بـ teacher_id ثم اليوم ثم رقم الحصة.
    - kpis: مؤشرات الأداء الأربعة.
    - alert: نص تنبيه ديناميكي أو null.
    """
    sid = resolve_school_id(current_user, school_id or x_school_context)
    if not sid:
        raise HTTPException(status_code=400, detail="معرف المدرسة مطلوب")
    assert_school_access(current_user, str(sid))

    periods = await _resolve_periods_for_school(sid)
    period_times = await _resolve_period_times(sid, periods)

    teachers_all = await gd_find(
        db.session,
        "teachers",
        {"school_id": sid, "is_active": True},
        order_by="full_name",
        limit=2000,
    )

    # Task #142 — payload window scoping. When the client supplies
    # ``teacher_page_size > 0`` we slice the teacher list to a single
    # visible page and *also* scope the session fetch to those teachers
    # via ``teacher_id $in [...]``. This keeps the wire payload bounded
    # to "what's actually rendered" instead of shipping the full school
    # in a single response. ``teacher_page_size = 0`` preserves the
    # legacy "send everything" behaviour for callers that haven't opted
    # in (e.g. exports, the substitution drawer's bulk lookups).
    teachers_total = len(teachers_all)
    if teacher_page_size and teacher_page_size > 0:
        start_idx = (teacher_page - 1) * teacher_page_size
        end_idx = start_idx + teacher_page_size
        teachers = teachers_all[start_idx:end_idx]
    else:
        teachers = teachers_all
    visible_teacher_ids = [t.get("id") for t in teachers if t.get("id")]

    # Task #141 — accept ``view=draft|published`` and surface the
    # resolved timetable status + ``is_empty`` flag so the frontend can
    # render the right banner / empty-state without a second round-trip.
    requested_view = (view or "").strip().lower() or None
    if requested_view not in {None, "draft", "published"}:
        requested_view = None
    timetable = await _resolve_active_timetable(sid, view=requested_view)
    sessions: list[dict] = []
    # Task #142 — daily-mode payload scoping: when the client requests a
    # single day (daily view), filter sessions on that day so the wire
    # payload is roughly 1/5 of the weekly size. Weekly view leaves
    # ``day`` unset and gets the full week.
    requested_day = (day or "").strip().lower() or None
    if requested_day not in {None, *DAYS}:
        requested_day = None
    if timetable:
        # Scope the session fetch to the visible teacher window when
        # pagination is active; otherwise pull all sessions for the
        # timetable (legacy contract). Optionally narrow to a single
        # day when the client asks for daily-view scoping.
        sess_filter: dict = {"timetable_id": timetable.get("id")}
        if teacher_page_size and visible_teacher_ids:
            sess_filter["teacher_id"] = {"$in": visible_teacher_ids}
        elif teacher_page_size and not visible_teacher_ids:
            # Page is past the end of the teacher list — short-circuit
            # to an empty session set instead of issuing a wide query.
            sess_filter = None  # type: ignore[assignment]
        if sess_filter is not None and requested_day:
            sess_filter["day_of_week"] = requested_day
        if sess_filter is not None:
            sessions = await find_live_timetable_sessions(
                db.session,
                sess_filter,
                limit=10000,
            )

    class_ids = list({s.get("class_id") for s in sessions if s.get("class_id")})
    classes = (
        await gd_find(db.session, "classes", {"id": {"$in": class_ids}, "is_active": {"$ne": False}}, limit=len(class_ids) or 1)
        if class_ids
        else []
    )
    class_name_map = {
        c.get("id"): (c.get("name") or c.get("name_ar") or "") for c in classes
    }

    subject_ids = list({s.get("subject_id") for s in sessions if s.get("subject_id")})
    subjects = (
        await gd_find(db.session, "subjects", {"id": {"$in": subject_ids}}, limit=len(subject_ids) or 1)
        if subject_ids
        else []
    )
    subject_name_map = {
        s.get("id"): (s.get("name_ar") or s.get("name") or "") for s in subjects
    }

    # خرائط ربط: قد تأتي سجلات الحضور بمعرّف teacher.id أو user_id؛ نمرّر الاتجاهين
    # حتى نلتقط الغياب أينما حفظه نظام الحضور.
    teacher_id_to_user_id = {t.get("id"): t.get("user_id") for t in teachers if t.get("id")}
    user_id_to_teacher_id = {
        t.get("user_id"): t.get("id") for t in teachers if t.get("user_id") and t.get("id")
    }
    valid_teacher_ids = set(teacher_id_to_user_id.keys())
    absent_ids = await _absent_teacher_ids_today(
        sid, valid_teacher_ids, user_id_to_teacher_id
    )
    today_key = _today_day_key()

    # Resolve any missing recorder names so the غائب pill tooltip can show
    # "سجَّله: …" without a second round-trip from the client.
    missing_recorder_ids = {
        meta.get("recorded_by")
        for meta in absent_ids.values()
        if meta.get("recorded_by") and not meta.get("recorded_by_name")
    }
    if missing_recorder_ids:
        try:
            recorder_users = await gd_find(
                db.session,
                "users",
                {"id": {"$in": list(missing_recorder_ids)}},
                limit=len(missing_recorder_ids),
            )
            recorder_name_map = {
                u.get("id"): (u.get("full_name") or u.get("name") or u.get("email") or "")
                for u in recorder_users
                if u.get("id")
            }
            for meta in absent_ids.values():
                rid = meta.get("recorded_by")
                if rid and not meta.get("recorded_by_name"):
                    meta["recorded_by_name"] = recorder_name_map.get(rid, "")
        except Exception:
            # Tooltip enrichment is best-effort; never fail the grid for it.
            pass

    # ── Class-relocation overlay ─────────────────────────────────────────
    # When a class is marked unavailable with an alternative location, we
    # surface that on the matching grid cell so the assigned teacher can
    # immediately see "نُقل إلى: …" without leaving the schedule view. We
    # build two lookups keyed by class_id: one for recurring (day, period)
    # and one for long-term ranges that include today. Each lookup carries
    # both the location text and the unavailability_id so the frontend can
    # call the ack endpoint right from the cell popover.
    relocation_recurring: dict[str, dict[tuple[str, str], dict]] = {}
    relocation_today: dict[str, dict] = {}
    today_iso_for_unavail = datetime.now(timezone.utc).date().isoformat()
    try:
        unavail_rows = await gd_find(
            db.session,
            "unavailability",
            {"school_id": sid, "entity_type": "class"},
            limit=2000,
        )
    except Exception:
        unavail_rows = []
    # Pre-compute per-row "did the current viewer ack this?" so the cell
    # popover renders the right button label without an extra request.
    viewer_id = (current_user or {}).get("id")
    for row in unavail_rows:
        alt = (row.get("alternative_location") or "").strip()
        if not alt:
            continue
        cls_id = row.get("entity_id")
        if not cls_id:
            continue
        ack_list = row.get("acknowledged_by") or []
        if not isinstance(ack_list, list):
            ack_list = []
        recipients_list = row.get("recipient_ids") or []
        if not isinstance(recipients_list, list):
            recipients_list = []
        meta = {
            "alternative_location": alt,
            "unavailability_id": row.get("id"),
            "acknowledged_by_viewer": bool(viewer_id and viewer_id in ack_list),
            "viewer_is_recipient": bool(viewer_id and viewer_id in recipients_list),
        }
        utype = row.get("unavailability_type") or "recurring"
        if utype == "long_term":
            start = (row.get("start_date") or "")
            end = (row.get("end_date") or "")
            if start and end and start <= today_iso_for_unavail <= end:
                # Last-write wins; long-term records affect every cell of
                # this class on today's column.
                relocation_today[cls_id] = meta
        else:
            day_raw = (row.get("day") or "").strip()
            day_en = _AR_DAY_TO_EN.get(day_raw, day_raw.lower())
            try:
                period_key = str(int(row.get("period")))
            except (TypeError, ValueError):
                continue
            relocation_recurring.setdefault(cls_id, {})[(day_en, period_key)] = meta

    cells: dict[str, dict[str, dict[str, object]]] = {}
    assigned_count: dict[str, int] = {}

    for sess in sessions:
        tid = sess.get("teacher_id")
        day = (sess.get("day_of_week") or sess.get("day") or "").lower()
        period = sess.get("period_number")
        if not tid or not day or period is None:
            continue
        try:
            period_int = int(period)
        except (TypeError, ValueError):
            continue
        period_key = str(period_int)
        teacher_cells = cells.setdefault(tid, {})
        day_cells = teacher_cells.setdefault(day, {})
        cls_id = sess.get("class_id")
        cls_name = class_name_map.get(cls_id, sess.get("class_name") or "")
        subj_name = _clean_label(
            subject_name_map.get(sess.get("subject_id"), sess.get("subject_name") or "")
        )
        is_vacant_today = (day == today_key) and (tid in absent_ids)
        cell_doc: dict[str, object] = {
            "session_id": sess.get("id"),
            "class_id": cls_id,
            "class_name": cls_name,
            "subject_id": sess.get("subject_id"),
            "subject_name": subj_name,
            "is_vacant": is_vacant_today,
        }
        # Task #919: a lesson whose (teacher, class) pairing was later
        # unassigned is kept but flagged for review. Surface it so the grid
        # can render a subtle "بحاجة لمراجعة" indicator without a second call.
        if sess.get("needs_review"):
            cell_doc["needs_review"] = True
            cell_doc["review_reason"] = sess.get("review_reason")
        # Apply relocation overlay (recurring match first, then today's
        # long-term blanket). Both flags are additive — they never replace
        # is_vacant / is_substituted styling, the frontend just composes a
        # subtle "نُقل إلى" hint on top of existing states.
        alt_meta = None
        if cls_id and cls_id in relocation_recurring:
            alt_meta = relocation_recurring[cls_id].get((day, period_key))
        if not alt_meta and cls_id and day == today_key:
            alt_meta = relocation_today.get(cls_id)
        if alt_meta:
            cell_doc["is_relocated"] = True
            cell_doc["alternative_location"] = alt_meta.get("alternative_location")
            cell_doc["unavailability_id"] = alt_meta.get("unavailability_id")
            cell_doc["acknowledged_by_viewer"] = alt_meta.get("acknowledged_by_viewer", False)
            cell_doc["viewer_is_recipient"] = alt_meta.get("viewer_is_recipient", False)
        day_cells[period_key] = cell_doc
        assigned_count[tid] = assigned_count.get(tid, 0) + 1

    # ── Merge today's substitute assignments ──────────────────────────────
    # Substitutes don't mutate timetable_sessions; we overlay them onto cells
    # so the absent teacher's red cell flips to "تم الاستبدال" and the
    # substitute teacher gets a synthetic "بديل" cell in their row.
    today_iso = datetime.now(timezone.utc).date().isoformat()
    sub_rows = await gd_find(
        db.session, "substitute_assignments",
        {"school_id": sid, "absence_date": today_iso},
        limit=2000,
    )
    teacher_name_map = {t.get("id"): (t.get("full_name") or "") for t in teachers}
    substituted_today = 0
    # Task #142 — keep the substitution overlay inside the same visible
    # window as the rest of the payload. When the client requested a
    # paginated teacher slice, we must NOT inject synthetic cells for
    # off-page teachers (absent or substitute). When the client scoped
    # to a single day (daily view), the overlay must skip rows for any
    # other day. Substitutions are inherently "today" rows, so a daily
    # request for a non-today day yields no overlay at all.
    visible_teacher_set: set | None = (
        set(visible_teacher_ids) if teacher_page_size else None
    )
    for sub in sub_rows:
        sub_day = (sub.get("day_of_week") or "").lower()
        if sub_day != today_key:
            continue
        if requested_day and sub_day != requested_day:
            continue
        try:
            sub_period_int = int(sub.get("period_number"))
        except (TypeError, ValueError):
            continue
        sub_period_key = str(sub_period_int)
        absent_tid = sub.get("original_teacher_id")
        sub_tid = sub.get("substitute_teacher_id")

        # Re-evaluate relocation status for this substitute slot so the
        # synthetic cells we're about to write/patch carry the same overlay
        # the original timetable cells received above.
        sub_cls_id = sub.get("class_id")
        sub_alt_meta = None
        if sub_cls_id and sub_cls_id in relocation_recurring:
            sub_alt_meta = relocation_recurring[sub_cls_id].get((sub_day, sub_period_key))
        if not sub_alt_meta and sub_cls_id and sub_day == today_key:
            sub_alt_meta = relocation_today.get(sub_cls_id)

        # Flip the absent teacher's vacant cell to substituted.
        if absent_tid and (visible_teacher_set is None or absent_tid in visible_teacher_set):
            absent_day_cells = cells.setdefault(absent_tid, {}).setdefault(sub_day, {})
            existing = absent_day_cells.get(sub_period_key)
            if existing is not None:
                existing["is_vacant"] = False
                existing["is_substituted"] = True
                existing["substitution_id"] = sub.get("id")
                existing["substitute_teacher_id"] = sub_tid
                existing["substitute_teacher_name"] = teacher_name_map.get(sub_tid, "")
                if sub_alt_meta:
                    existing["is_relocated"] = True
                    existing["alternative_location"] = sub_alt_meta.get("alternative_location")
                    existing["unavailability_id"] = sub_alt_meta.get("unavailability_id")
                    existing["acknowledged_by_viewer"] = sub_alt_meta.get("acknowledged_by_viewer", False)
                    existing["viewer_is_recipient"] = sub_alt_meta.get("viewer_is_recipient", False)
                substituted_today += 1

        # Add synthetic cell to substitute teacher's row.
        if sub_tid and (visible_teacher_set is None or sub_tid in visible_teacher_set):
            sub_day_cells = cells.setdefault(sub_tid, {}).setdefault(sub_day, {})
            if sub_period_key not in sub_day_cells:
                synth: dict[str, object] = {
                    "session_id": sub.get("original_session_id"),
                    "class_id": sub_cls_id,
                    "class_name": sub.get("class_name") or class_name_map.get(sub_cls_id, ""),
                    "subject_id": sub.get("subject_id"),
                    "subject_name": sub.get("subject_name") or subject_name_map.get(sub.get("subject_id"), ""),
                    "is_vacant": False,
                    "is_substitute": True,
                    "substitution_id": sub.get("id"),
                    "original_teacher_id": absent_tid,
                    "original_teacher_name": teacher_name_map.get(absent_tid, ""),
                }
                if sub_alt_meta:
                    synth["is_relocated"] = True
                    synth["alternative_location"] = sub_alt_meta.get("alternative_location")
                    synth["unavailability_id"] = sub_alt_meta.get("unavailability_id")
                    synth["acknowledged_by_viewer"] = sub_alt_meta.get("acknowledged_by_viewer", False)
                    synth["viewer_is_recipient"] = sub_alt_meta.get("viewer_is_recipient", False)
                sub_day_cells[sub_period_key] = synth

    teacher_rows: list[dict] = []
    fairness_values: list[float] = []
    for t in teachers:
        tid = t.get("id")
        normalized_rank = _normalize_rank(t.get("rank"))
        quota = t.get("weekly_periods") or _RANK_DEFAULT_QUOTA.get(normalized_rank, 0)
        assigned = assigned_count.get(tid, 0)
        is_absent = tid in absent_ids
        absence_meta = absent_ids.get(tid) if is_absent else None
        teacher_rows.append({
            "id": tid,
            "full_name": t.get("full_name") or "",
            "subject": _clean_label(t.get("specialization") or t.get("subject") or ""),
            "rank": normalized_rank,
            "weekly_quota": quota,
            "assigned_periods": assigned,
            "is_absent_today": is_absent,
            # Audit trail surfaced in the grid tooltip when a teacher is absent.
            "absence_recorded_by": (absence_meta or {}).get("recorded_by"),
            "absence_recorded_by_name": (absence_meta or {}).get("recorded_by_name") or "",
            "absence_recorded_at": (absence_meta or {}).get("recorded_at"),
        })
        if quota and quota > 0:
            fairness_values.append(min(1.0, assigned / quota))

    fairness_pct = round(_jains_fairness(fairness_values) * 100)

    vacant_today_total = sum(
        1
        for s in sessions
        if (s.get("day_of_week") or s.get("day") or "").lower() == today_key
        and s.get("teacher_id") in absent_ids
    )
    # Substituted slots no longer count against the vacancy KPI.
    vacant_today = max(vacant_today_total - substituted_today, 0)
    # نصيب الأسبوع: مجموع الحصص المُسندة لمعلمين غائبين اليوم — تقريب لاحتياج الاستبدال
    # خلال بقية الأسبوع. (المرحلة التالية ستضيف derivation حقيقي من quota/demand.)
    vacant_week = sum(
        1
        for s in sessions
        if s.get("teacher_id") in absent_ids
    )

    assigned_waiting = 0
    if timetable:
        try:
            assigned_waiting = await gd_count(
                db.session,
                "timetable_unscheduled_demands",
                {"timetable_id": timetable.get("id")},
            )
        except Exception:  # collection may not exist yet
            assigned_waiting = 0

    kpis = {
        "fairness_pct": fairness_pct,
        "assigned_waiting": assigned_waiting,
        "absent_teachers_today": len(absent_ids),
        "vacant_sessions_today": vacant_today,
        "vacant_sessions_week": vacant_week,
        "substituted_sessions_today": substituted_today,
    }

    alert = None
    if vacant_today > 0:
        alert = (
            f"يوجد {vacant_today} حصة شاغرة بلا معلم — اضغط على الخلية الحمراء لعرض المرشحين"
        )

    # تعطيل أي طبقة كاش (متصفح/وسيط) — هذه الاستجابة تعتمد على آخر حالة
    # للجداول/الغياب/الاستبدالات وتُحدَّث فور أي تعديل، لذا لا يصحّ تقديم
    # نسخة مخزَّنة. أهم سيناريو: بعد ضغط "إنشاء الجدول تلقائياً" يجب أن
    # يلتقط GET التالي البيانات الجديدة لا نسخة سابقة من ذاكرة المتصفح.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    # Task #142 — surface a pagination block so the client knows whether
    # it's looking at a window or the full school. ``page_size=0`` means
    # "no pagination — full school payload" (legacy behaviour); any
    # positive value reflects the visible-window slice.
    pagination = {
        "page": teacher_page if teacher_page_size else 1,
        "page_size": teacher_page_size or teachers_total,
        "total": teachers_total,
        "windowed": bool(teacher_page_size),
        "day": requested_day,
    }

    return {
        "school_id": sid,
        "timetable_id": timetable.get("id") if timetable else None,
        "timetable_status": timetable.get("status") if timetable else None,
        # Task #141 — surface ``is_empty`` so the frontend can render
        # the explicit empty-state ("لا يوجد جدول منشور حالياً") when
        # the requested view has no matching timetable, instead of
        # falling back to the legacy "no teachers" placeholder.
        "is_empty": timetable is None,
        "view": requested_view,
        "days": DAYS,
        "periods": periods,
        "period_times": period_times,
        "today": today_key,
        "teachers": teacher_rows,
        "cells": cells,
        "kpis": kpis,
        "alert": alert,
        "pagination": pagination,
    }
