"""
Time Slots Service
Handles generation, regeneration, listing of time slots, and calculation of live school day status.
"""
from fastapi import HTTPException
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import uuid
import logging

from engines.sql_utils import (
    gd_find, gd_find_one, gd_insert_many, gd_update_one, gd_delete_many,
)
from src.core.guards.tenant_guard import is_independent_workspace_id, independent_workspace_id
from src.common.utils.it_schedule import synthesize_it_time_slots

logger = logging.getLogger("nassaq")
DEFAULT_SCHOOL_TZ = "Asia/Riyadh"


def arabic_ordinal(n: int) -> str:
    ordinals = {1: "الأولى", 2: "الثانية", 3: "الثالثة", 4: "الرابعة", 5: "الخامسة", 6: "السادسة", 7: "السابعة", 8: "الثامنة", 9: "التاسعة", 10: "العاشرة", 11: "الحادية عشرة", 12: "الثانية عشرة"}
    return ordinals.get(n, str(n))


class TimeSlotsService:
    """Service handling time slots generation, listing, and day-status calculation."""

    @staticmethod
    async def regenerate_time_slots(session, school_id: str) -> dict:
        """Regenerate the time_slots collection from current school_settings."""
        settings = await gd_find_one(session, "school_settings", {"school_id": school_id})
        if not settings:
            return {"regenerated": False, "reason": "no_settings"}

        timing = settings.get("timing", {})
        cs = settings.get("custom_settings") or {}
        nested = settings.get("settings", {}) or {}

        def _first(*values, default=None):
            for value in values:
                if value is not None and value != "":
                    return value
            return default

        def _bounded_int(value, default, minimum, maximum):
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                parsed = default
            return min(max(parsed, minimum), maximum)

        # Dedicated ORM columns are the canonical saved settings.  The nested
        # values below are migration aliases only and must not override them.
        day_start = _first(
            settings.get("start_time"),
            settings.get("school_day_start"),
            cs.get("school_day_start"),
            nested.get("school_day_start"),
            timing.get("start"),
            default="07:00",
        )
        try:
            parts = str(day_start).split(":")
            if len(parts) != 2 or not (0 <= int(parts[0]) <= 23 and 0 <= int(parts[1]) <= 59):
                day_start = "07:00"
            else:
                day_start = str(day_start)
        except (ValueError, AttributeError):
            day_start = "07:00"

        periods = _bounded_int(_first(
            settings.get("periods_per_day"),
            cs.get("periods_per_day"),
            nested.get("periods_per_day"),
            default=7,
        ), 7, 1, 12)
        period_dur = _bounded_int(_first(
            settings.get("period_duration"),
            settings.get("period_duration_minutes"),
            cs.get("period_duration_minutes"),
            nested.get("period_duration_minutes"),
            default=45,
        ), 45, 20, 90)
        break_dur = _bounded_int(_first(
            settings.get("break_duration"),
            settings.get("break_duration_minutes"),
            cs.get("break_duration_minutes"),
            nested.get("break_duration_minutes"),
            default=15,
        ), 15, 0, 60)
        prayer_dur = _bounded_int(_first(
            settings.get("prayer_duration_minutes"),
            cs.get("prayer_duration_minutes"),
            nested.get("prayer_duration_minutes"),
            default=20,
        ), 20, 0, 60)

        # Presence is meaningful: an explicitly saved [] means no breaks.
        # Only installations with no breaks key at all retain legacy defaults.
        breaks_are_explicit = "breaks" in cs or "breaks" in settings
        saved_breaks = cs.get("breaks") if "breaks" in cs else settings.get("breaks")
        if not isinstance(saved_breaks, list):
            saved_breaks = []
        break_after_map = {}
        for b in saved_breaks:
            if not isinstance(b, dict):
                continue
            after = b.get("afterPeriod") or b.get("after_period")
            if after:
                raw_duration = b.get("duration")
                break_after_map[int(after)] = {
                    "name": b.get("name", "استراحة"),
                    "name_en": b.get("name_en", "Break"),
                    # null inherits BASE; zero is a deliberate duration.
                    "duration": break_dur if raw_duration is None else int(raw_duration),
                    "is_prayer": b.get("type") == "prayer" or "صلا" in (b.get("name") or ""),
                }

        if not breaks_are_explicit and not break_after_map:
            if periods >= 3:
                break_after_map[3] = {"name": "الاستراحة", "name_en": "Break", "duration": break_dur, "is_prayer": False}
            if periods >= 6:
                break_after_map[6] = {"name": "الصلاة", "name_en": "Prayer", "duration": prayer_dur, "is_prayer": True}

        passing_time = 5
        h, m = map(int, day_start.split(":"))
        current_minutes = h * 60 + m
        slots = []
        slot_number = 0
        period_count = 0

        for i in range(1, periods + 1):
            slot_number += 1
            period_count += 1
            start_h, start_m = divmod(current_minutes, 60)
            end_minutes = current_minutes + period_dur
            end_h, end_m = divmod(end_minutes, 60)
            slots.append({
                "id": str(uuid.uuid4()),
                "school_id": school_id,
                "name": f"الحصة {arabic_ordinal(period_count)}",
                "name_en": f"Period {period_count}",
                "start_time": f"{start_h:02d}:{start_m:02d}",
                "end_time": f"{end_h:02d}:{end_m:02d}",
                "slot_number": slot_number,
                "period_number": period_count,
                "duration_minutes": period_dur,
                "type": "class",
                "is_break": False,
                "is_prayer": False,
                "is_active": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            current_minutes = end_minutes

            brk = break_after_map.get(i)
            if brk:
                slot_number += 1
                bs_h, bs_m = divmod(current_minutes, 60)
                be_minutes = current_minutes + brk["duration"]
                be_h, be_m = divmod(be_minutes, 60)
                slots.append({
                    "id": str(uuid.uuid4()),
                    "school_id": school_id,
                    "name": brk["name"],
                    "name_en": brk["name_en"],
                    "start_time": f"{bs_h:02d}:{bs_m:02d}",
                    "end_time": f"{be_h:02d}:{be_m:02d}",
                    "slot_number": slot_number,
                    "period_number": None,
                    "duration_minutes": brk["duration"],
                    "type": "prayer" if brk["is_prayer"] else "break",
                    "is_break": True,
                    "is_prayer": brk["is_prayer"],
                    "is_active": True,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
                current_minutes = be_minutes
            else:
                current_minutes += passing_time

        # Preserve the logical teaching period before replacing slot ids.  A
        # manual placement may store the old raw slot_number (which contains
        # gaps for breaks), so use the old slot id/raw-number maps as well as
        # period_number.
        old_slots = await gd_find(
            session, "time_slots", {"school_id": school_id},
            order_by="slot_number", desc_order=False, limit=200,
        )
        old_teaching = [slot for slot in old_slots if not slot.get("is_break")]
        old_id_to_period = {
            slot.get("id"): index
            for index, slot in enumerate(old_teaching, start=1)
            if slot.get("id")
        }
        old_raw_to_period = {
            int(slot["slot_number"]): index
            for index, slot in enumerate(old_teaching, start=1)
            if slot.get("slot_number") is not None
        }

        new_teaching = [slot for slot in slots if not slot.get("is_break")]
        new_by_period = {
            index: slot for index, slot in enumerate(new_teaching, start=1)
        }
        draft_sessions = []
        drafts = await gd_find(
            session, "timetables",
            {"school_id": school_id, "status": {"$in": ["draft", "DRAFT"]}},
            limit=100,
        )
        for draft in drafts:
            timetable_id = draft.get("id")
            if not timetable_id:
                continue
            rows = await gd_find(
                session, "timetable_sessions",
                {"timetable_id": timetable_id}, limit=50000,
            )
            for row in rows:
                if row.get("is_active") is False or row.get("status") == "cancelled":
                    continue
                logical_period = old_id_to_period.get(row.get("time_slot_id"))
                if logical_period is None:
                    for key in ("period_number", "period"):
                        try:
                            candidate = int(row.get(key))
                        except (TypeError, ValueError):
                            continue
                        if candidate > 0:
                            logical_period = candidate
                            break
                if logical_period is None:
                    try:
                        raw_slot = int(row.get("slot_number"))
                    except (TypeError, ValueError):
                        raw_slot = None
                    if raw_slot is not None:
                        logical_period = old_raw_to_period.get(raw_slot, raw_slot)

                if logical_period is not None and logical_period > periods:
                    raise HTTPException(
                        status_code=422,
                        detail={
                            "code": "draft_sessions_use_removed_periods",
                            "message": (
                                "Cannot reduce periods_per_day while draft timetable "
                                "sessions are assigned to a removed period."
                            ),
                            "timetable_id": timetable_id,
                            "session_id": row.get("id"),
                            "period_number": logical_period,
                        },
                    )
                if logical_period in new_by_period:
                    draft_sessions.append((row, logical_period))

        await gd_delete_many(session, "time_slots", {"school_id": school_id})
        if slots:
            await gd_insert_many(session, "time_slots", slots)

        # Only draft children are retargeted. Published and archived timetable
        # rows remain immutable history with their original denormalized times.
        for row, logical_period in draft_sessions:
            replacement = new_by_period[logical_period]
            await gd_update_one(
                session, "timetable_sessions", {"id": row.get("id")}, {
                    "time_slot_id": replacement["id"],
                    "start_time": replacement["start_time"],
                    "end_time": replacement["end_time"],
                },
            )

        final_h, final_m = divmod(current_minutes, 60)
        day_end = f"{final_h:02d}:{final_m:02d}"
        await gd_update_one(session, "school_settings", {"school_id": school_id}, {
            "school_day_end": day_end,
            "settings.school_day_end": day_end,
        })

        return {"regenerated": True, "count": len(slots), "day_end": day_end}

    @staticmethod
    async def list_time_slots(session, current_user: dict, x_school_context: str = None) -> list:
        from src.modules.schools.services.school_settings_service import resolve_school_context
        caller_role = (current_user or {}).get("role", "")
        if caller_role == "independent_teacher":
            school_id = independent_workspace_id(current_user)
        else:
            school_id = await resolve_school_context(current_user, x_school_context)

        if not school_id:
            return []

        slots = await gd_find(session, "time_slots", {"school_id": school_id}, order_by="slot_number", desc_order=False, limit=30)
        if not slots and is_independent_workspace_id(school_id):
            settings = await gd_find_one(session, "school_settings", {"school_id": school_id})
            return synthesize_it_time_slots(school_id, settings)

        if not slots:
            await TimeSlotsService.regenerate_time_slots(session, school_id)
            slots = await gd_find(session, "time_slots", {"school_id": school_id}, order_by="slot_number", desc_order=False, limit=30)

        return slots

    @staticmethod
    async def get_school_day_status(session, current_user: dict, x_school_context: str = None) -> dict:
        _neutral_payload = {
            "is_school_time": False,
            "is_working_day": False,
            "time_slots": [],
            "total_periods": 0,
            "current_period": 0,
            "progress": 0,
            "day_start": None,
            "day_end": None,
            "current_period_name": "",
            "is_break": False,
        }
        from src.modules.schools.services.school_settings_service import resolve_school_context
        caller_role = (current_user or {}).get("role", "")
        if caller_role == "independent_teacher":
            school_id = independent_workspace_id(current_user)
        else:
            caller_tenant = (current_user or {}).get("tenant_id") or (current_user or {}).get("school_id")
            if not caller_tenant:
                return _neutral_payload
            school_id = await resolve_school_context(current_user, x_school_context)
        if not school_id:
            return _neutral_payload

        settings = await gd_find_one(session, "school_settings", {"school_id": school_id})
        nested = (settings or {}).get("settings", {}) if settings else {}
        cs = (settings or {}).get("custom_settings") or {}

        def _first(*candidates, default=None):
            for c in candidates:
                if c is not None and c != "":
                    return c
            return default

        day_start_str = _first(
            cs.get("school_day_start"),
            nested.get("school_day_start"),
            (settings or {}).get("school_day_start"),
            (settings or {}).get("start_time"),
            default="07:00",
        )
        periods_per_day = int(_first(
            cs.get("periods_per_day"),
            nested.get("periods_per_day"),
            (settings or {}).get("periods_per_day"),
            default=7,
        ) or 7)
        period_duration = int(_first(
            cs.get("period_duration_minutes"),
            nested.get("period_duration_minutes"),
            (settings or {}).get("period_duration_minutes"),
            (settings or {}).get("period_duration"),
            default=45,
        ) or 45)
        break_duration = int(_first(
            cs.get("break_duration_minutes"),
            nested.get("break_duration_minutes"),
            (settings or {}).get("break_duration_minutes"),
            (settings or {}).get("break_duration"),
            default=20,
        ) or 20)

        time_slots_raw = await gd_find(session, "time_slots", {"school_id": school_id}, order_by="start_time", desc_order=False, limit=30)
        if not time_slots_raw and is_independent_workspace_id(school_id):
            time_slots_raw = synthesize_it_time_slots(school_id, settings)

        def parse_time(t):
            if not t or not isinstance(t, str) or ":" not in t:
                return None
            try:
                parts = t.split(":")
                return int(parts[0]) * 60 + int(parts[1])
            except (ValueError, IndexError):
                return None

        valid_slots = []
        for slot in time_slots_raw:
            st = parse_time(slot.get("start_time"))
            et = parse_time(slot.get("end_time"))
            if st is not None and et is not None:
                valid_slots.append(slot)

        period_slots = [s for s in valid_slots if not s.get("is_break", False)]
        total_periods = len(period_slots) if period_slots else int(periods_per_day)

        start_minutes = parse_time(day_start_str) or 420
        if period_slots:
            computed_end_minutes = parse_time(period_slots[-1].get("end_time")) or (start_minutes + total_periods * period_duration + break_duration)
        else:
            computed_end_minutes = start_minutes + (total_periods * period_duration) + break_duration
        end_h, end_m = divmod(computed_end_minutes, 60)
        day_end_str = f"{end_h % 24:02d}:{end_m:02d}"

        working_days = (settings or {}).get("working_days", nested.get("working_days", {}))
        day_names_map = {6: "sunday", 0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday", 4: "friday", 5: "saturday"}
        tz_name = nested.get("timezone") or (settings or {}).get("timezone") or DEFAULT_SCHOOL_TZ
        try:
            school_tz = ZoneInfo(tz_name)
        except Exception:
            school_tz = ZoneInfo(DEFAULT_SCHOOL_TZ)
        now = datetime.now(school_tz)
        today_key = day_names_map.get(now.weekday(), "")
        is_working_day = True
        if isinstance(working_days, dict) and working_days:
            is_working_day = working_days.get(today_key, False)

        now_minutes = now.hour * 60 + now.minute

        if period_slots:
            first_start = parse_time(period_slots[0].get("start_time")) or parse_time(day_start_str) or 420
            last_end = parse_time(period_slots[-1].get("end_time")) or parse_time(day_end_str) or 795
        else:
            first_start = parse_time(day_start_str) or 420
            last_end = parse_time(day_end_str) or 795

        is_school_time = is_working_day and first_start <= now_minutes <= last_end

        current_period = 0
        current_period_name = ""
        is_break = False

        if is_school_time:
            for slot in valid_slots:
                s = parse_time(slot.get("start_time"))
                e = parse_time(slot.get("end_time"))
                if s is not None and e is not None and s <= now_minutes < e:
                    if slot.get("is_break", False):
                        is_break = True
                        current_period_name = slot.get("name") or "استراحة"
                    else:
                        current_period = period_slots.index(slot) + 1 if slot in period_slots else 0
                        current_period_name = slot.get("name") or f"الحصة {current_period}"
                    break

            if current_period == 0 and not is_break:
                for i, slot in enumerate(period_slots):
                    e = parse_time(slot.get("end_time"))
                    if e is not None and now_minutes < e:
                        current_period = i + 1
                        break
                if current_period == 0:
                    current_period = total_periods

        elapsed = max(0, now_minutes - first_start)
        total_duration = max(1, last_end - first_start)
        progress = min(100, max(0, round((elapsed / total_duration) * 100)))
        if not is_working_day:
            progress = 0

        slots_formatted = []
        for s in time_slots_raw:
            slots_formatted.append({
                "start_time": s.get("start_time"),
                "end_time": s.get("end_time"),
                "is_break": s.get("is_break", False),
                "name": s.get("name", ""),
                "name_en": s.get("name_en", ""),
            })

        return {
            "day_start": day_start_str,
            "day_end": day_end_str,
            "total_periods": total_periods,
            "current_period": current_period,
            "current_period_name": current_period_name,
            "is_break": is_break,
            "is_school_time": is_school_time,
            "is_working_day": is_working_day,
            "progress": progress,
            "time_slots": slots_formatted,
        }
