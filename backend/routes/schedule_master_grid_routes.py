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
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response

from dependencies import db, get_current_user
from engines.sql_utils import gd_count, gd_find, gd_find_one
from utils.tenant_scope import assert_school_access, resolve_school_id

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
      1. Distinct ``period_number`` from ``time_slots`` (excludes breaks/prayer
         when a slot type is provided).
      2. ``school_settings.periods_per_day`` → ``range(1, N+1)``.
      3. ``DEFAULT_PERIODS`` (legacy fallback only — should never trigger
         once a school has any saved schedule settings).
    """
    try:
        slots = await gd_find(db.session, "time_slots", {"school_id": school_id}, limit=200)
        teaching_periods: list[int] = []
        for s in slots:
            slot_type = s.get("type") or ""
            if s.get("is_break") or s.get("is_prayer") or slot_type in ("break", "prayer"):
                continue
            pn = s.get("period_number") or s.get("slot_number")
            if pn is None:
                continue
            try:
                teaching_periods.append(int(pn))
            except (TypeError, ValueError):
                continue
        if teaching_periods:
            return sorted(set(teaching_periods))

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
_RANK_ALIASES = {
    "خبير": "expert",
    "متقدم": "advanced",
    "ممارس": "practitioner",
    "مساعد": "assistant",
    "senior": "expert",
    "junior": "assistant",
}


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


async def _resolve_active_timetable(school_id: str) -> Optional[dict]:
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
    rows = await gd_find(
        db.session,
        "timetables",
        {"school_id": school_id, "status": {"$in": ["published", "draft"]}},
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

    teachers = await gd_find(
        db.session,
        "teachers",
        {"school_id": sid, "is_active": True},
        order_by="full_name",
        limit=2000,
    )

    timetable = await _resolve_active_timetable(sid)
    sessions: list[dict] = []
    if timetable:
        sessions = await gd_find(
            db.session,
            "timetable_sessions",
            {"timetable_id": timetable.get("id")},
            limit=10000,
        )

    class_ids = list({s.get("class_id") for s in sessions if s.get("class_id")})
    classes = (
        await gd_find(db.session, "classes", {"id": {"$in": class_ids}}, limit=len(class_ids) or 1)
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
    # and one for long-term ranges that include today.
    relocation_recurring: dict[str, dict[tuple[str, str], str]] = {}
    relocation_today: dict[str, str] = {}
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
    for row in unavail_rows:
        alt = (row.get("alternative_location") or "").strip()
        if not alt:
            continue
        cls_id = row.get("entity_id")
        if not cls_id:
            continue
        utype = row.get("unavailability_type") or "recurring"
        if utype == "long_term":
            start = (row.get("start_date") or "")
            end = (row.get("end_date") or "")
            if start and end and start <= today_iso_for_unavail <= end:
                # Last-write wins; long-term records affect every cell of
                # this class on today's column.
                relocation_today[cls_id] = alt
        else:
            day_raw = (row.get("day") or "").strip()
            day_en = _AR_DAY_TO_EN.get(day_raw, day_raw.lower())
            try:
                period_key = str(int(row.get("period")))
            except (TypeError, ValueError):
                continue
            relocation_recurring.setdefault(cls_id, {})[(day_en, period_key)] = alt

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
        subj_name = subject_name_map.get(sess.get("subject_id"), sess.get("subject_name") or "")
        is_vacant_today = (day == today_key) and (tid in absent_ids)
        cell_doc: dict[str, object] = {
            "session_id": sess.get("id"),
            "class_id": cls_id,
            "class_name": cls_name,
            "subject_id": sess.get("subject_id"),
            "subject_name": subj_name,
            "is_vacant": is_vacant_today,
        }
        # Apply relocation overlay (recurring match first, then today's
        # long-term blanket). Both flags are additive — they never replace
        # is_vacant / is_substituted styling, the frontend just composes a
        # subtle "نُقل إلى" hint on top of existing states.
        alt_loc = None
        if cls_id and cls_id in relocation_recurring:
            alt_loc = relocation_recurring[cls_id].get((day, period_key))
        if not alt_loc and cls_id and day == today_key:
            alt_loc = relocation_today.get(cls_id)
        if alt_loc:
            cell_doc["is_relocated"] = True
            cell_doc["alternative_location"] = alt_loc
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
    for sub in sub_rows:
        sub_day = (sub.get("day_of_week") or "").lower()
        if sub_day != today_key:
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
        sub_alt_loc = None
        if sub_cls_id and sub_cls_id in relocation_recurring:
            sub_alt_loc = relocation_recurring[sub_cls_id].get((sub_day, sub_period_key))
        if not sub_alt_loc and sub_cls_id and sub_day == today_key:
            sub_alt_loc = relocation_today.get(sub_cls_id)

        # Flip the absent teacher's vacant cell to substituted.
        if absent_tid:
            absent_day_cells = cells.setdefault(absent_tid, {}).setdefault(sub_day, {})
            existing = absent_day_cells.get(sub_period_key)
            if existing is not None:
                existing["is_vacant"] = False
                existing["is_substituted"] = True
                existing["substitution_id"] = sub.get("id")
                existing["substitute_teacher_id"] = sub_tid
                existing["substitute_teacher_name"] = teacher_name_map.get(sub_tid, "")
                if sub_alt_loc:
                    existing["is_relocated"] = True
                    existing["alternative_location"] = sub_alt_loc
                substituted_today += 1

        # Add synthetic cell to substitute teacher's row.
        if sub_tid:
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
                if sub_alt_loc:
                    synth["is_relocated"] = True
                    synth["alternative_location"] = sub_alt_loc
                sub_day_cells[sub_period_key] = synth

    teacher_rows: list[dict] = []
    fairness_values: list[float] = []
    for t in teachers:
        tid = t.get("id")
        quota = t.get("weekly_periods") or 0
        assigned = assigned_count.get(tid, 0)
        is_absent = tid in absent_ids
        absence_meta = absent_ids.get(tid) if is_absent else None
        teacher_rows.append({
            "id": tid,
            "full_name": t.get("full_name") or "",
            "subject": t.get("specialization") or t.get("subject") or "",
            "rank": _normalize_rank(t.get("rank")),
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

    return {
        "school_id": sid,
        "timetable_id": timetable.get("id") if timetable else None,
        "timetable_status": timetable.get("status") if timetable else None,
        "days": DAYS,
        "periods": periods,
        "today": today_key,
        "teachers": teacher_rows,
        "cells": cells,
        "kpis": kpis,
        "alert": alert,
    }
