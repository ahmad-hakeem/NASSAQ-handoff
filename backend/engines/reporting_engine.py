"""
Reporting Engine — محرك التقارير المركزي
نَسَّق | NASSAQ

Centralized report generation with aggregation pipelines.

Report types:
  School-level:
    1. school_attendance   — daily/weekly/monthly attendance with class breakdown
    2. school_participation — session interactions by class and student
    3. school_behaviour     — behaviour incidents, trends, type breakdown
    4. school_academic      — grade distribution, class comparisons, top/bottom

  Teacher-level:
    5. teacher_activity     — sessions conducted, total interactions
    6. teacher_session      — avg participation rate, engagement metrics per session

  Student-level:
    7. student_progress     — attendance trend, grade trend, participation trend
    8. student_attendance   — attendance history with calendar-view data
    9. student_performance  — risk score (Hakim AI), strengths, areas for improvement

All reports return:
  { report_type, period, data, generated_at, school_id }
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import logging
import math

from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_count, gd_delete_one, gd_delete_many, gd_iter_rows

logger = logging.getLogger("nassaq.reporting_engine")


async def _empty_rows():
    """Async-iterable stand-in for "nothing to stream"."""
    return
    yield  # pragma: no cover - makes this an async generator


REPORT_TYPES = [
    "school_attendance",
    "school_participation",
    "school_behaviour",
    "school_academic",
    "teacher_activity",
    "teacher_session",
    "student_progress",
    "student_attendance",
    "student_performance",
    "class_report",
    "timetable",
]


def _date_range(start_date: Optional[str], end_date: Optional[str]):
    if start_date and end_date:
        return start_date, end_date
    now = datetime.now(timezone.utc)
    if not end_date:
        end_date = now.strftime("%Y-%m-%d")
    if not start_date:
        start_date = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    return start_date, end_date


def _week_key(date_str: str) -> str:
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        iso = dt.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    except Exception as e:
        logger.debug("Could not parse week key from '%s': %s", date_str, e)
        return "unknown"


def _month_key(date_str: str) -> str:
    try:
        return date_str[:7]
    except Exception as e:
        logger.debug("Could not parse month key from '%s': %s", date_str, e)
        return "unknown"


class ReportingEngine:
    def __init__(self, db, hakim_engine=None):
        self.db = db
        self.hakim_engine = hakim_engine

    @property
    def session(self):
        return self.db.session

    async def _paginated_find(self, collection_name, query: dict, projection: dict = None, page_size: int = 5000, sort_key: str = None, sort_dir: int = 1):
        all_docs = []
        offset = 0
        while True:
            batch = await gd_find(self.session, collection_name, query,
                                  order_by=sort_key,
                                  desc_order=(sort_dir == -1) if sort_key else True,
                                  limit=page_size, offset=offset if offset > 0 else None)
            if not batch:
                break
            all_docs.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
        return all_docs

    def _wrap(self, report_type: str, school_id: str, period: dict, data: dict) -> dict:
        return {
            "report_type": report_type,
            "school_id": school_id,
            "period": period,
            "data": data,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def generate(
        self,
        report_type: str,
        school_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        class_id: Optional[str] = None,
        teacher_id: Optional[str] = None,
        student_id: Optional[str] = None,
    ) -> dict:
        """Dispatch report generation by type and return structured report data."""
        sd, ed = _date_range(start_date, end_date)
        kwargs = dict(
            school_id=school_id,
            start_date=sd,
            end_date=ed,
            class_id=class_id,
            teacher_id=teacher_id,
            student_id=student_id,
        )
        handler = {
            "school_attendance": self._school_attendance,
            "school_participation": self._school_participation,
            "school_behaviour": self._school_behaviour,
            "school_academic": self._school_academic,
            "teacher_activity": self._teacher_activity,
            "teacher_session": self._teacher_session,
            "student_progress": self._student_progress,
            "student_attendance": self._student_attendance,
            "student_performance": self._student_performance,
            "class_report": self._class_report,
            "timetable": self._timetable_report,
        }.get(report_type)

        if handler is None:
            return {"error": f"نوع التقرير غير معروف: {report_type}",
                    "available_types": REPORT_TYPES}

        return await handler(**kwargs)

    # ------------------------------------------------------------------
    # 1. School Attendance Report
    # ------------------------------------------------------------------
    async def _school_attendance(self, school_id: str, start_date: str,
                                  end_date: str, **_kw) -> dict:
        base_filter = {"school_id": school_id, "date": {"$gte": start_date, "$lte": end_date}}
        class_id = _kw.get("class_id")
        if class_id:
            base_filter["class_id"] = class_id

        raw_records = await gd_find(self.session, "attendance", base_filter, limit=10000)

        daily: Dict[str, dict] = {}
        for r in raw_records:
            d = r.get("date", "")
            s = r.get("status", "absent")
            if d not in daily:
                daily[d] = {"date": d, "present": 0, "absent": 0, "late": 0, "excused": 0, "total": 0}
            daily[d][s] = daily[d].get(s, 0) + 1
            daily[d]["total"] += 1
        for v in daily.values():
            v["rate"] = round((v["present"] + v.get("late", 0)) / v["total"] * 100, 1) if v["total"] else 0

        weekly: Dict[str, dict] = {}
        for d, v in daily.items():
            wk = _week_key(d)
            if wk not in weekly:
                weekly[wk] = {"week": wk, "present": 0, "absent": 0, "late": 0, "total": 0}
            for k in ("present", "absent", "late", "total"):
                weekly[wk][k] += v.get(k, 0)
        for v in weekly.values():
            v["rate"] = round((v["present"] + v.get("late", 0)) / v["total"] * 100, 1) if v["total"] else 0

        monthly: Dict[str, dict] = {}
        for d, v in daily.items():
            mk = _month_key(d)
            if mk not in monthly:
                monthly[mk] = {"month": mk, "present": 0, "absent": 0, "late": 0, "total": 0}
            for k in ("present", "absent", "late", "total"):
                monthly[mk][k] += v.get(k, 0)
        for v in monthly.values():
            v["rate"] = round((v["present"] + v.get("late", 0)) / v["total"] * 100, 1) if v["total"] else 0

        by_class: Dict[str, dict] = {}
        for r in raw_records:
            cid = r.get("class_id", "unknown")
            s = r.get("status", "absent")
            if cid not in by_class:
                by_class[cid] = {"class_id": cid, "present": 0, "absent": 0, "late": 0, "total": 0}
            by_class[cid][s] = by_class[cid].get(s, 0) + 1
            by_class[cid]["total"] += 1
        for v in by_class.values():
            v["rate"] = round((v["present"] + v.get("late", 0)) / v["total"] * 100, 1) if v["total"] else 0

        classes = await gd_find(self.session, "classes", {"school_id": school_id}, limit=200)
        name_map = {c["id"]: c.get("name_ar") or c.get("name", c["id"]) for c in classes}
        for v in by_class.values():
            v["class_name"] = name_map.get(v["class_id"], v["class_id"])

        total_records = sum(v["total"] for v in daily.values())
        total_present = sum(v["present"] + v.get("late", 0) for v in daily.values())

        data = {
            "summary": {
                "total_records": total_records,
                "overall_rate": round(total_present / total_records * 100, 1) if total_records else 0,
            },
            "daily": sorted(daily.values(), key=lambda x: x["date"]),
            "weekly": sorted(weekly.values(), key=lambda x: x["week"]),
            "monthly": sorted(monthly.values(), key=lambda x: x["month"]),
            "by_class": sorted(by_class.values(), key=lambda x: x.get("class_name", "")),
        }
        return self._wrap("school_attendance", school_id,
                           {"start_date": start_date, "end_date": end_date}, data)

    # ------------------------------------------------------------------
    # 2. School Participation Report
    # ------------------------------------------------------------------
    async def _school_participation(self, school_id: str, start_date: str,
                                     end_date: str, **_kw) -> dict:
        class_id = _kw.get("class_id")
        session_query: dict = {"school_id": school_id, "status": "completed"}
        if start_date:
            session_query["date"] = {"$gte": start_date, "$lte": end_date}
        if class_id:
            session_query["class_id"] = class_id

        sessions = await gd_find(self.session, "class_sessions", session_query, limit=2000)
        session_ids = [s["id"] for s in sessions]
        session_class = {s["id"]: s.get("class_id") for s in sessions}

        if not session_ids:
            return self._wrap("school_participation", school_id,
                               {"start_date": start_date, "end_date": end_date},
                               {"summary": {"total_sessions": 0, "total_interactions": 0},
                                "by_class": [], "by_type": [], "top_students": []})

        all_interactions = await gd_find(self.session, "session_interactions", {"session_id": {"$in": session_ids}}, limit=50000)

        type_counts: Dict[str, int] = {}
        for i in all_interactions:
            itype = i.get("interaction_type", "unknown")
            type_counts[itype] = type_counts.get(itype, 0) + 1
        by_type = [{"type": t, "count": c} for t, c in type_counts.items()]

        student_agg: Dict[str, dict] = {}
        for i in all_interactions:
            sid = i.get("student_id")
            if not sid:
                continue
            if sid not in student_agg:
                student_agg[sid] = {"interactions": 0, "correct": 0}
            student_agg[sid]["interactions"] += 1
            if i.get("answer_result") == "correct":
                student_agg[sid]["correct"] += 1
        top_sorted = sorted(student_agg.items(), key=lambda x: -x[1]["interactions"])[:20]

        student_ids = [s[0] for s in top_sorted if s[0]]
        students = await gd_find(self.session, "students", {"id": {"$in": student_ids}, "school_id": school_id, "is_active": True}, limit=200) if student_ids else []
        stu_map = {s["id"]: s for s in students}

        top_students = []
        for sid, agg in top_sorted:
            stu = stu_map.get(sid, {})
            top_students.append({
                "student_id": sid,
                "student_name": stu.get("name_ar") or stu.get("full_name") or stu.get("name", ""),
                "class_id": stu.get("class_id"),
                "interactions": agg["interactions"],
                "correct_answers": agg["correct"],
            })

        session_date = {s["id"]: s.get("date", "") for s in sessions}

        session_inter_counts: Dict[str, int] = {}
        for i in all_interactions:
            ssid = i.get("session_id", "")
            session_inter_counts[ssid] = session_inter_counts.get(ssid, 0) + 1

        by_class_counts: Dict[str, int] = {}
        weekly_counts: Dict[str, int] = {}
        for ssid, cnt in session_inter_counts.items():
            cid = session_class.get(ssid, "unknown")
            by_class_counts[cid] = by_class_counts.get(cid, 0) + cnt
            wk = _week_key(session_date.get(ssid, ""))
            weekly_counts[wk] = weekly_counts.get(wk, 0) + cnt

        classes = await gd_find(self.session, "classes", {"school_id": school_id}, limit=200)
        cn_map = {c["id"]: c.get("name_ar") or c.get("name", c["id"]) for c in classes}

        by_class = [
            {"class_id": cid, "class_name": cn_map.get(cid, cid), "interactions": cnt}
            for cid, cnt in sorted(by_class_counts.items(), key=lambda x: -x[1])
        ]

        trend = [{"week": w, "interactions": c} for w, c in sorted(weekly_counts.items())]

        total_interactions = sum(type_counts.values())

        data = {
            "summary": {
                "total_sessions": len(sessions),
                "total_interactions": total_interactions,
            },
            "by_type": by_type,
            "by_class": by_class,
            "top_students": top_students,
            "trend": trend,
        }
        return self._wrap("school_participation", school_id,
                           {"start_date": start_date, "end_date": end_date}, data)

    # ------------------------------------------------------------------
    # 3. School Behaviour Report
    # ------------------------------------------------------------------
    async def _school_behaviour(self, school_id: str, start_date: str,
                                 end_date: str, **_kw) -> dict:
        class_id = _kw.get("class_id")

        match_created: dict = {"school_id": school_id, "created_at": {"$gte": start_date, "$lte": end_date}}
        if class_id:
            match_created["class_id"] = class_id
        match_date: dict = {"school_id": school_id, "date": {"$gte": start_date, "$lte": end_date}}
        if class_id:
            match_date["class_id"] = class_id

        records_created = await gd_find(self.session, "behavior", match_created, limit=10000)
        records_date = await gd_find(self.session, "behavior", match_date, limit=10000)

        seen_ids = set()
        all_records = []
        for r in records_created + records_date:
            rid = r.get("id", id(r))
            if rid not in seen_ids:
                seen_ids.add(rid)
                all_records.append(r)

        type_counts: Dict[str, int] = {}
        for r in all_records:
            btype = r.get("type") or r.get("behavior_type") or "other"
            type_counts[btype] = type_counts.get(btype, 0) + 1
        by_type = sorted([{"type": t, "count": c} for t, c in type_counts.items()], key=lambda x: -x["count"])
        total_incidents = sum(type_counts.values())

        classes = await gd_find(self.session, "classes", {"school_id": school_id}, limit=200)
        cn_map = {c["id"]: c.get("name_ar") or c.get("name", c["id"]) for c in classes}

        class_data: Dict[str, dict] = {}
        for r in all_records:
            cid = r.get("class_id", "unknown")
            btype = r.get("type") or r.get("behavior_type") or "other"
            if cid not in class_data:
                class_data[cid] = {"class_id": cid, "class_name": cn_map.get(cid, cid), "total": 0, "breakdown": {}}
            class_data[cid]["breakdown"][btype] = class_data[cid]["breakdown"].get(btype, 0) + 1
            class_data[cid]["total"] += 1
        by_class = sorted(class_data.values(), key=lambda x: -x["total"])

        daily_counts: Dict[str, int] = {}
        for r in all_records:
            day = (r.get("date") or r.get("created_at") or "")[:10]
            if day:
                daily_counts[day] = daily_counts.get(day, 0) + 1
        trend = sorted([{"date": d, "count": c} for d, c in daily_counts.items()], key=lambda x: x["date"])

        sorted_records = sorted(all_records, key=lambda x: x.get("created_at", ""), reverse=True)[:10]
        student_ids_needed = list(set(r.get("student_id") for r in sorted_records if r.get("student_id")))
        stu_docs = await gd_find(self.session, "students", {"id": {"$in": student_ids_needed}, "school_id": school_id, "is_active": True}, limit=100) if student_ids_needed else []
        stu_map = {s["id"]: s.get("name_ar") or s.get("full_name") or s.get("name", "") for s in stu_docs}
        recent_items = []
        for r in sorted_records:
            recent_items.append({
                "student_id": r.get("student_id"),
                "student_name": stu_map.get(r.get("student_id"), ""),
                "type": r.get("type") or r.get("behavior_type"),
                "note": r.get("note") or r.get("description") or r.get("notes", ""),
                "date": (r.get("created_at") or r.get("date", ""))[:10],
            })

        data = {
            "summary": {"total_incidents": total_incidents, "type_breakdown": type_counts},
            "by_type": by_type,
            "by_class": by_class,
            "trend": trend,
            "recent": recent_items,
        }
        return self._wrap("school_behaviour", school_id,
                           {"start_date": start_date, "end_date": end_date}, data)

    # ------------------------------------------------------------------
    # 4. School Academic Performance Report
    # ------------------------------------------------------------------
    async def _school_academic(self, school_id: str, start_date: str,
                                end_date: str, **_kw) -> dict:
        class_id = _kw.get("class_id")

        score_filter: dict = {"school_id": school_id, "date": {"$gte": start_date, "$lte": end_date}}
        if class_id:
            score_filter["class_id"] = class_id

        all_scores = await gd_find(self.session, "student_daily_scores", score_filter, limit=50000)

        class_groups: Dict[str, list] = {}
        for s in all_scores:
            cid = s.get("class_id", "unknown")
            if cid not in class_groups:
                class_groups[cid] = []
            class_groups[cid].append(s.get("score", 0) or 0)

        classes = await gd_find(self.session, "classes", {"school_id": school_id}, limit=200)
        cn_map = {c["id"]: c.get("name_ar") or c.get("name", c["id"]) for c in classes}

        class_performance = []
        for cid, scores_list in sorted(class_groups.items(), key=lambda x: -(sum(x[1]) / len(x[1]) if x[1] else 0)):
            avg_s = sum(scores_list) / len(scores_list) if scores_list else 0
            class_performance.append({
                "class_id": cid,
                "class_name": cn_map.get(cid, cid or "unknown"),
                "avg_score": round(avg_s, 1),
                "max_score": max(scores_list) if scores_list else 0,
                "min_score": min(scores_list) if scores_list else 0,
                "records": len(scores_list),
            })

        boundaries = [0, 50, 60, 70, 80, 90, 101]
        labels = {0: "0-49", 50: "50-59", 60: "60-69", 70: "70-79", 80: "80-89", 90: "90-100"}
        bucket_counts: Dict[int, int] = {}
        for s in all_scores:
            score_val = s.get("score", 0) or 0
            for i in range(len(boundaries) - 1):
                if boundaries[i] <= score_val < boundaries[i + 1]:
                    bucket_counts[boundaries[i]] = bucket_counts.get(boundaries[i], 0) + 1
                    break
        distribution = []
        for b in [0, 50, 60, 70, 80, 90]:
            if b in bucket_counts:
                distribution.append({"range": labels.get(b, str(b)), "count": bucket_counts[b]})

        student_scores: Dict[str, list] = {}
        for s in all_scores:
            sid = s.get("student_id")
            if sid:
                if sid not in student_scores:
                    student_scores[sid] = []
                student_scores[sid].append(s.get("score", 0) or 0)

        student_avgs = [(sid, sum(sc) / len(sc), len(sc)) for sid, sc in student_scores.items()]
        student_avgs_sorted = sorted(student_avgs, key=lambda x: -x[1])
        top_raw = student_avgs_sorted[:10]
        bottom_raw = sorted(student_avgs, key=lambda x: x[1])[:10]

        all_stu_ids = list(set(
            [r[0] for r in top_raw if r[0]] +
            [r[0] for r in bottom_raw if r[0]]
        ))
        stu_docs = await gd_find(self.session, "students", {"id": {"$in": all_stu_ids}, "school_id": school_id, "is_active": True}, limit=200)
        stu_map = {s["id"]: s for s in stu_docs}

        def _stu_row(r):
            s = stu_map.get(r[0], {})
            return {
                "student_id": r[0],
                "student_name": s.get("name_ar") or s.get("full_name") or s.get("name", ""),
                "class_id": s.get("class_id"),
                "avg_score": round(r[1], 1),
                "records": r[2],
            }

        overall_avg = round(sum(s.get("score", 0) or 0 for s in all_scores) / len(all_scores), 1) if all_scores else 0
        overall_count = len(all_scores)

        session_match: dict = {
            "school_id": school_id,
            "status": "completed",
            "date": {"$gte": start_date, "$lte": end_date},
        }
        if class_id:
            session_match["class_id"] = class_id

        completed_sessions = await gd_find(self.session, "class_sessions", session_match, limit=2000)
        session_ids = [s["id"] for s in completed_sessions]

        if session_ids:
            all_interactions = await gd_find(self.session, "session_interactions", {"session_id": {"$in": session_ids}}, limit=50000)
        else:
            all_interactions = []

        session_inter_map: Dict[str, list] = {}
        for i in all_interactions:
            ssid = i.get("session_id", "")
            if ssid not in session_inter_map:
                session_inter_map[ssid] = []
            session_inter_map[ssid].append(i)

        session_subject = {s["id"]: s.get("subject_id") for s in completed_sessions}
        session_class_map = {s["id"]: s.get("class_id") for s in completed_sessions}

        subject_data: Dict[str, dict] = {}
        for s in completed_sessions:
            subj_id = s.get("subject_id")
            if not subj_id:
                continue
            if subj_id not in subject_data:
                subject_data[subj_id] = {"sessions": 0, "classes": set(), "total_interactions": 0}
            subject_data[subj_id]["sessions"] += 1
            if s.get("class_id"):
                subject_data[subj_id]["classes"].add(s.get("class_id"))
            subject_data[subj_id]["total_interactions"] += len(session_inter_map.get(s["id"], []))

        subject_ids = list(subject_data.keys())
        subjects = await gd_find(self.session, "subjects", {"id": {"$in": subject_ids}, "school_id": school_id}, limit=200) if subject_ids else []
        subj_map = {s["id"]: s for s in subjects}

        subject_performance = []
        for sid, sd in sorted(subject_data.items(), key=lambda x: -x[1]["sessions"]):
            subj = subj_map.get(sid, {})
            subject_performance.append({
                "subject_id": sid,
                "subject_name": subj.get("name_ar") or subj.get("name_en") or sid,
                "sessions": sd["sessions"],
                "classes_count": len(sd["classes"]),
                "total_interactions": sd["total_interactions"],
                "avg_interactions_per_session": round(sd["total_interactions"] / sd["sessions"], 1) if sd["sessions"] else 0,
            })

        data = {
            "summary": {"overall_average": overall_avg, "total_records": overall_count},
            "class_performance": class_performance,
            "subject_performance": subject_performance,
            "grade_distribution": distribution,
            "top_performers": [_stu_row(r) for r in top_raw],
            "bottom_performers": [_stu_row(r) for r in bottom_raw],
        }
        return self._wrap("school_academic", school_id,
                           {"start_date": start_date, "end_date": end_date}, data)

    # ------------------------------------------------------------------
    # 5. Teacher Activity Report
    # ------------------------------------------------------------------
    async def _teacher_activity(self, school_id: str, start_date: str,
                                 end_date: str, **_kw) -> dict:
        teacher_id = _kw.get("teacher_id")
        if not teacher_id:
            return self._wrap("teacher_activity", school_id,
                               {"start_date": start_date, "end_date": end_date},
                               {"error": "teacher_id مطلوب"})

        teacher = await gd_find_one(self.session, "teachers", {"id": teacher_id, "school_id": school_id})
        if not teacher:
            user = await gd_find_one(self.session, "users", {"teacher_id": teacher_id, "tenant_id": school_id})
            teacher = user or {"id": teacher_id}

        session_match = {
            "teacher_id": teacher_id,
            "school_id": school_id,
            "status": "completed",
        }
        if start_date:
            session_match["date"] = {"$gte": start_date, "$lte": end_date}

        sessions = await self._paginated_find("class_sessions", session_match)
        session_ids = [s["id"] for s in sessions]

        total_interactions = 0
        if session_ids:
            total_interactions = await gd_count(self.session, "session_interactions",
                {"session_id": {"$in": session_ids}})

        classes_taught = list(set(s.get("class_id") for s in sessions if s.get("class_id")))

        classes_docs = await gd_find(self.session, "classes", {"id": {"$in": classes_taught}, "school_id": school_id}, limit=200)
        cn_map = {c["id"]: c.get("name_ar") or c.get("name", c["id"]) for c in classes_docs}

        class_session_counts: Dict[str, int] = {}
        for s in sessions:
            cid = s.get("class_id", "unknown")
            class_session_counts[cid] = class_session_counts.get(cid, 0) + 1

        class_breakdown = [
            {"class_id": cid, "class_name": cn_map.get(cid, cid), "sessions": cnt}
            for cid, cnt in sorted(class_session_counts.items(), key=lambda x: -x[1])
        ]

        avg_per_session = round(total_interactions / len(sessions), 1) if sessions else 0

        data = {
            "teacher": {
                "teacher_id": teacher_id,
                "name": teacher.get("full_name") or teacher.get("name", ""),
                "email": teacher.get("email", ""),
            },
            "summary": {
                "total_sessions": len(sessions),
                "total_interactions": total_interactions,
                "avg_interactions_per_session": avg_per_session,
                "classes_taught": len(classes_taught),
            },
            "class_breakdown": class_breakdown,
        }
        return self._wrap("teacher_activity", school_id,
                           {"start_date": start_date, "end_date": end_date}, data)

    # ------------------------------------------------------------------
    # 6. Teacher Session Report
    # ------------------------------------------------------------------
    async def _teacher_session(self, school_id: str, start_date: str,
                                end_date: str, **_kw) -> dict:
        teacher_id = _kw.get("teacher_id")
        if not teacher_id:
            return self._wrap("teacher_session", school_id,
                               {"start_date": start_date, "end_date": end_date},
                               {"error": "teacher_id مطلوب"})

        session_match = {
            "teacher_id": teacher_id,
            "school_id": school_id,
            "status": "completed",
        }
        if start_date:
            session_match["date"] = {"$gte": start_date, "$lte": end_date}

        sessions = await self._paginated_find("class_sessions", session_match)
        session_ids = [s["id"] for s in sessions]

        if not session_ids:
            return self._wrap("teacher_session", school_id,
                               {"start_date": start_date, "end_date": end_date},
                               {"sessions": [], "class_engagement": []})

        sess_agg: Dict[str, dict] = {}
        async for i in gd_iter_rows(self.session, "session_interactions",
                                    {"session_id": {"$in": session_ids}}, max_rows=50000):
            ssid = i.get("session_id", "")
            if ssid not in sess_agg:
                sess_agg[ssid] = {"total_interactions": 0, "unique_students": set(), "correct": 0, "questions": 0}
            sess_agg[ssid]["total_interactions"] += 1
            if i.get("student_id"):
                sess_agg[ssid]["unique_students"].add(i.get("student_id"))
            if i.get("answer_result") == "correct":
                sess_agg[ssid]["correct"] += 1
            if i.get("interaction_type") == "question":
                sess_agg[ssid]["questions"] += 1

        session_details = []
        for s in sessions:
            sid = s["id"]
            agg = sess_agg.get(sid, {})
            unique = len(agg.get("unique_students", set()))
            total_inter = agg.get("total_interactions", 0)
            questions = agg.get("questions", 0)
            correct = agg.get("correct", 0)
            session_details.append({
                "session_id": sid,
                "class_id": s.get("class_id"),
                "date": s.get("date"),
                "duration": s.get("duration"),
                "interactions": total_inter,
                "unique_participants": unique,
                "questions_asked": questions,
                "correct_answers": correct,
                "accuracy_rate": round(correct / questions * 100, 1) if questions else 0,
            })

        session_details.sort(key=lambda x: x.get("date", ""), reverse=True)

        classes_docs = await gd_find(self.session, "classes", {"school_id": school_id}, limit=200)
        cn_map = {c["id"]: c.get("name_ar") or c.get("name", c["id"]) for c in classes_docs}

        class_engagement: Dict[str, dict] = {}
        for sd in session_details:
            cid = sd.get("class_id", "unknown")
            if cid not in class_engagement:
                class_engagement[cid] = {
                    "class_id": cid,
                    "class_name": cn_map.get(cid, cid),
                    "sessions": 0,
                    "total_interactions": 0,
                    "total_participants": 0,
                }
            class_engagement[cid]["sessions"] += 1
            class_engagement[cid]["total_interactions"] += sd["interactions"]
            class_engagement[cid]["total_participants"] += sd["unique_participants"]
        for v in class_engagement.values():
            v["avg_interactions_per_session"] = round(
                v["total_interactions"] / v["sessions"], 1) if v["sessions"] else 0
            v["avg_participants_per_session"] = round(
                v["total_participants"] / v["sessions"], 1) if v["sessions"] else 0

        data = {
            "sessions": session_details,
            "class_engagement": sorted(class_engagement.values(),
                                        key=lambda x: -x["avg_interactions_per_session"]),
        }
        return self._wrap("teacher_session", school_id,
                           {"start_date": start_date, "end_date": end_date}, data)

    # ------------------------------------------------------------------
    # 7. Student Progress Report
    # ------------------------------------------------------------------
    async def _student_progress(self, school_id: str, start_date: str,
                                 end_date: str, **_kw) -> dict:
        student_id = _kw.get("student_id")
        if not student_id:
            return self._wrap("student_progress", school_id,
                               {"start_date": start_date, "end_date": end_date},
                               {"error": "student_id مطلوب"})

        student = await gd_find_one(self.session, "students", {"id": student_id, "school_id": school_id, "is_active": True})
        if not student:
            return self._wrap("student_progress", school_id,
                               {"start_date": start_date, "end_date": end_date},
                               {"error": "الطالب غير موجود"})

        att_records = await self._paginated_find("attendance", {
            "student_id": student_id, "school_id": school_id,
            "date": {"$gte": start_date, "$lte": end_date},
        })

        att_weekly: Dict[str, dict] = {}
        for r in att_records:
            wk = _week_key(r.get("date", ""))
            if wk not in att_weekly:
                att_weekly[wk] = {"week": wk, "total": 0, "present": 0}
            att_weekly[wk]["total"] += 1
            if r.get("status") in ("present", "late"):
                att_weekly[wk]["present"] += 1
        for v in att_weekly.values():
            v["rate"] = round(v["present"] / v["total"] * 100, 1) if v["total"] else 0
        att_trend = sorted(att_weekly.values(), key=lambda x: x["week"])

        scores = await gd_find(self.session, "student_daily_scores", {
            "student_id": student_id, "school_id": school_id,
            "date": {"$gte": start_date, "$lte": end_date},
        }, order_by="date", desc_order=False, limit=5000)
        grade_trend = [{"date": s.get("date"), "score": s.get("score", 0)} for s in scores]

        session_ids_raw = await self._paginated_find("class_sessions",
            {"school_id": school_id, "date": {"$gte": start_date, "$lte": end_date}})
        sid_date = {s["id"]: s.get("date", "") for s in session_ids_raw}
        all_sids = list(sid_date.keys())

        interactions = await self._paginated_find("session_interactions",
            {"session_id": {"$in": all_sids}, "student_id": student_id}) if all_sids else []

        part_weekly: Dict[str, int] = {}
        for i in interactions:
            d = sid_date.get(i.get("session_id"), "")
            wk = _week_key(d)
            part_weekly[wk] = part_weekly.get(wk, 0) + 1
        participation_trend = [{"week": w, "interactions": c} for w, c in sorted(part_weekly.items())]

        data = {
            "student": {
                "student_id": student_id,
                "name": student.get("name_ar") or student.get("full_name") or student.get("name", ""),
                "class_id": student.get("class_id"),
            },
            "attendance_trend": att_trend,
            "grade_trend": grade_trend,
            "participation_trend": participation_trend,
        }
        return self._wrap("student_progress", school_id,
                           {"start_date": start_date, "end_date": end_date}, data)

    # ------------------------------------------------------------------
    # 8. Student Attendance Report (calendar view)
    # ------------------------------------------------------------------
    async def _student_attendance(self, school_id: str, start_date: str,
                                   end_date: str, **_kw) -> dict:
        student_id = _kw.get("student_id")
        if not student_id:
            return self._wrap("student_attendance", school_id,
                               {"start_date": start_date, "end_date": end_date},
                               {"error": "student_id مطلوب"})

        records = await self._paginated_find("attendance", {
            "student_id": student_id, "school_id": school_id,
            "date": {"$gte": start_date, "$lte": end_date},
        }, sort_key="date")

        total = len(records)
        present = sum(1 for r in records if r.get("status") in ("present", "late"))
        absent = sum(1 for r in records if r.get("status") == "absent")
        late = sum(1 for r in records if r.get("status") == "late")
        excused = sum(1 for r in records if r.get("status") == "excused")

        calendar = {}
        for r in records:
            d = r.get("date", "")
            calendar[d] = r.get("status", "unknown")

        monthly_summary: Dict[str, dict] = {}
        for r in records:
            mk = _month_key(r.get("date", ""))
            if mk not in monthly_summary:
                monthly_summary[mk] = {"month": mk, "total": 0, "present": 0, "absent": 0, "late": 0}
            monthly_summary[mk]["total"] += 1
            s = r.get("status", "absent")
            if s in ("present", "late"):
                monthly_summary[mk]["present"] += 1
            if s == "absent":
                monthly_summary[mk]["absent"] += 1
            if s == "late":
                monthly_summary[mk]["late"] += 1
        for v in monthly_summary.values():
            v["rate"] = round(v["present"] / v["total"] * 100, 1) if v["total"] else 0

        data = {
            "summary": {
                "total_days": total,
                "present": present,
                "absent": absent,
                "late": late,
                "excused": excused,
                "attendance_rate": round(present / total * 100, 1) if total else 0,
            },
            "calendar": calendar,
            "monthly": sorted(monthly_summary.values(), key=lambda x: x["month"]),
        }
        return self._wrap("student_attendance", school_id,
                           {"start_date": start_date, "end_date": end_date}, data)

    # ------------------------------------------------------------------
    # 9. Student Performance Report (Hakim AI integration)
    # ------------------------------------------------------------------
    async def _student_performance(self, school_id: str, start_date: str,
                                    end_date: str, **_kw) -> dict:
        student_id = _kw.get("student_id")
        if not student_id:
            return self._wrap("student_performance", school_id,
                               {"start_date": start_date, "end_date": end_date},
                               {"error": "student_id مطلوب"})

        student = await gd_find_one(self.session, "students", {"id": student_id, "school_id": school_id, "is_active": True})
        if not student:
            return self._wrap("student_performance", school_id,
                               {"start_date": start_date, "end_date": end_date},
                               {"error": "الطالب غير موجود"})

        att_total = await gd_count(self.session, "attendance", {
            "student_id": student_id, "school_id": school_id,
            "date": {"$gte": start_date, "$lte": end_date},
        })
        att_present = await gd_count(self.session, "attendance", {
            "student_id": student_id, "school_id": school_id,
            "date": {"$gte": start_date, "$lte": end_date},
            "status": {"$in": ["present", "late"]},
        })

        score_records = await gd_find(self.session, "student_daily_scores", {
            "student_id": student_id, "school_id": school_id,
            "date": {"$gte": start_date, "$lte": end_date},
        }, limit=5000)
        score_values = [s.get("score", 0) or 0 for s in score_records]
        score_stats = {}
        if score_values:
            score_stats = {
                "avg_score": sum(score_values) / len(score_values),
                "max_score": max(score_values),
                "min_score": min(score_values),
                "count": len(score_values),
            }

        session_ids_raw = await self._paginated_find("class_sessions",
            {"school_id": school_id, "date": {"$gte": start_date, "$lte": end_date}})
        all_sids = [s["id"] for s in session_ids_raw]

        participation_breakdown: Dict[str, dict] = {}
        async for i in gd_iter_rows(
            self.session, "session_interactions",
            {"session_id": {"$in": all_sids}, "student_id": student_id},
            max_rows=50000,
        ) if all_sids else _empty_rows():
            itype = i.get("interaction_type", "unknown")
            if itype not in participation_breakdown:
                participation_breakdown[itype] = {"count": 0, "correct": 0}
            participation_breakdown[itype]["count"] += 1
            if i.get("answer_result") == "correct":
                participation_breakdown[itype]["correct"] += 1

        total_interactions = sum(v["count"] for v in participation_breakdown.values())
        total_questions = participation_breakdown.get("question", {}).get("count", 0)
        total_correct = participation_breakdown.get("question", {}).get("correct", 0)

        risk_doc = await gd_find_one(self.session, "ai_insights",
            {"type": "student_risk", "entity_id": student_id, "school_id": school_id})
        risk_data = risk_doc.get("data") if risk_doc else None

        if not risk_data and self.hakim_engine:
            try:
                live_risk = await self.hakim_engine.analyze_student_risk(student_id, school_id)
                if live_risk and not live_risk.get("error"):
                    risk_data = live_risk
            except Exception as e:
                logger.debug("Live risk analysis unavailable for student %s: %s", student_id, e)

        strengths = []
        improvements = []
        att_rate = round(att_present / att_total * 100, 1) if att_total else 0
        avg_score = round(score_stats.get("avg_score", 0) or 0, 1)

        if att_rate >= 90:
            strengths.append("انتظام ممتاز في الحضور")
        elif att_rate < 75:
            improvements.append("تحسين نسبة الحضور")

        if avg_score >= 80:
            strengths.append("أداء أكاديمي متميز")
        elif avg_score < 60:
            improvements.append("رفع المستوى الأكاديمي")

        if total_interactions >= 10:
            strengths.append("مشاركة فعّالة في الحصص")
        elif total_interactions < 3:
            improvements.append("زيادة المشاركة الصفية")

        accuracy = round(total_correct / total_questions * 100, 1) if total_questions else 0
        if accuracy >= 80:
            strengths.append("دقة عالية في الإجابات")
        elif accuracy < 50 and total_questions >= 3:
            improvements.append("تحسين دقة الإجابات")

        data = {
            "student": {
                "student_id": student_id,
                "name": student.get("name_ar") or student.get("full_name") or student.get("name", ""),
                "class_id": student.get("class_id"),
            },
            "attendance": {
                "total_days": att_total,
                "present": att_present,
                "rate": att_rate,
            },
            "academic": {
                "avg_score": avg_score,
                "max_score": score_stats.get("max_score", 0) or 0,
                "min_score": score_stats.get("min_score", 0) or 0,
                "records": score_stats.get("count", 0),
            },
            "participation": {
                "total_interactions": total_interactions,
                "questions_answered": total_questions,
                "correct_answers": total_correct,
                "accuracy_rate": accuracy,
                "breakdown": participation_breakdown,
            },
            "risk": risk_data,
            "strengths": strengths,
            "areas_for_improvement": improvements,
        }
        return self._wrap("student_performance", school_id,
                           {"start_date": start_date, "end_date": end_date}, data)

    # ------------------------------------------------------------------
    # Legacy methods (preserved original response shapes for backward compat)
    # ------------------------------------------------------------------

    async def generate_student_report(self, student_id: str, school_id: str) -> dict:
        """Generate a comprehensive report for a single student."""
        student = await gd_find_one(self.session, "students", {"id": student_id, "school_id": school_id, "is_active": True})
        if not student:
            return {"error": "الطالب غير موجود"}

        att_total = await gd_count(self.session, "attendance", {
            "student_id": student_id, "school_id": school_id
        })
        att_present = await gd_count(self.session, "attendance", {
            "student_id": student_id, "school_id": school_id,
            "status": {"$in": ["present", "late"]}
        })
        att_absent = att_total - att_present
        att_rate = round((att_present / att_total * 100) if att_total > 0 else 0, 1)

        scores = await gd_find(self.session, "student_daily_scores", {
            "student_id": student_id, "school_id": school_id
        }, limit=5000)
        total_score = sum(s.get("score", 0) for s in scores)

        session_ids = [s["id"] for s in await self._paginated_find("class_sessions",
            {"school_id": school_id})]
        inter_query: dict = {"student_id": student_id}
        if session_ids:
            inter_query["session_id"] = {"$in": session_ids}

        type_result_counts: Dict[str, Dict[str, int]] = {}
        async for i in gd_iter_rows(self.session, "session_interactions", inter_query, max_rows=50000):
            itype = i.get("interaction_type", "unknown")
            result = i.get("answer_result", "none")
            key = f"{itype}|{result}"
            if key not in type_result_counts:
                type_result_counts[key] = {"type": itype, "result": result, "count": 0}
            type_result_counts[key]["count"] += 1

        total_interactions = 0
        questions_total = 0
        correct = 0
        participations = 0
        for r in type_result_counts.values():
            itype = r["type"]
            result = r["result"]
            cnt = r["count"]
            total_interactions += cnt
            if itype == "question":
                questions_total += cnt
                if result == "correct":
                    correct += cnt
            elif itype == "participation":
                participations += cnt

        risk_doc = await gd_find_one(self.session, "ai_insights",
            {"type": "student_risk", "entity_id": student_id, "school_id": school_id})

        for key in ("_id", "created_at", "updated_at"):
            student.pop(key, None)

        return {
            "report_type": "student_report",
            "student": student,
            "attendance": {
                "total_days": att_total,
                "present_days": att_present,
                "absent_days": att_absent,
                "attendance_rate": att_rate,
            },
            "participation": {
                "total_interactions": total_interactions,
                "questions_asked": questions_total,
                "correct_answers": correct,
                "active_participations": participations,
                "accuracy_rate": round((correct / questions_total * 100) if questions_total else 0, 1),
            },
            "academic": {
                "total_score_points": total_score,
            },
            "risk": risk_doc.get("data") if risk_doc else None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _class_report(self, school_id: str, start_date: str,
                              end_date: str, **kw) -> dict:
        class_id = kw.get("class_id")
        if not class_id:
            classes = await gd_find(self.session, "classes", {"school_id": school_id}, limit=200)
            class_summaries = []
            for cls in classes:
                cid = cls["id"]
                stu_count = await gd_count(self.session, "students",
                    {"class_id": cid, "school_id": school_id, "is_active": True})
                att_total = await gd_count(self.session, "attendance",
                    {"class_id": cid, "school_id": school_id,
                     "date": {"$gte": start_date, "$lte": end_date}})
                att_present = await gd_count(self.session, "attendance",
                    {"class_id": cid, "school_id": school_id,
                     "date": {"$gte": start_date, "$lte": end_date},
                     "status": {"$in": ["present", "late"]}})
                class_summaries.append({
                    "class_id": cid,
                    "class_name": cls.get("name", cid),
                    "students": stu_count,
                    "attendance_rate": round((att_present / att_total * 100) if att_total else 0, 1),
                })
            return {
                "report_type": "class_report",
                "school_id": school_id,
                "period": {"start_date": start_date, "end_date": end_date},
                "data": {
                    "summary": {"total_classes": len(classes)},
                    "classes": class_summaries,
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        report = await self.generate_class_report(class_id, school_id)
        return {
            "report_type": "class_report",
            "school_id": school_id,
            "period": {"start_date": start_date, "end_date": end_date},
            "data": report,
            "generated_at": report.get("generated_at", datetime.now(timezone.utc).isoformat()),
        }

    async def _timetable_report(self, school_id: str, start_date: str,
                                  end_date: str, **kw) -> dict:
        tt = await gd_find_one(self.session, "timetables",
            {"school_id": school_id, "status": "published"})
        sessions = []
        if tt:
            raw = await self._paginated_find("timetable_sessions",
                {"timetable_id": tt["id"], "school_id": school_id})
            class_ids = list(set(s.get("class_id", "") for s in raw))
            teacher_ids = list(set(s.get("teacher_id", "") for s in raw))
            subject_ids = list(set(s.get("subject_id", "") for s in raw))
            classes_list = await gd_find(self.session, "classes", {"id": {"$in": class_ids}}, limit=500)
            classes = {c["id"]: c.get("name", c["id"]) for c in classes_list}
            teachers_list = await gd_find(self.session, "teachers", {"id": {"$in": teacher_ids}}, limit=500)
            teachers = {t["id"]: t.get("full_name", t["id"]) for t in teachers_list}
            subjects_list = await gd_find(self.session, "subjects", {"id": {"$in": subject_ids}}, limit=500)
            subjects = {s["id"]: s.get("name_ar", s.get("name", s["id"])) for s in subjects_list}
            for s in raw:
                sessions.append({
                    "day": s.get("day", ""),
                    "period": s.get("period", ""),
                    "class_name": classes.get(s.get("class_id", ""), s.get("class_id", "")),
                    "teacher_name": teachers.get(s.get("teacher_id", ""), s.get("teacher_id", "")),
                    "subject_name": subjects.get(s.get("subject_id", ""), s.get("subject_id", "")),
                    "room": s.get("room", ""),
                })
        return {
            "report_type": "timetable",
            "school_id": school_id,
            "period": {"start_date": start_date, "end_date": end_date},
            "data": {
                "timetable": {
                    "id": tt.get("id", "") if tt else "",
                    "name": tt.get("name", "") if tt else "لا يوجد جدول منشور",
                    "status": tt.get("status", "") if tt else "",
                    "total_sessions": tt.get("total_sessions", len(sessions)) if tt else 0,
                },
                "sessions": sessions,
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def generate_class_report(self, class_id: str, school_id: str) -> dict:
        """Generate an aggregate report for a class including attendance and grades."""
        cls = await gd_find_one(self.session, "classes", {"id": class_id, "school_id": school_id})
        students = await gd_find(self.session, "students",
            {"class_id": class_id, "school_id": school_id, "is_active": True}, limit=200)

        student_ids = [s["id"] for s in students]
        name_map = {s["id"]: s.get("full_name", "") for s in students}

        att_total = await gd_count(self.session, "attendance", {
            "class_id": class_id, "school_id": school_id
        })
        att_present = await gd_count(self.session, "attendance", {
            "class_id": class_id, "school_id": school_id,
            "status": {"$in": ["present", "late"]}
        })
        att_rate = round((att_present / att_total * 100) if att_total > 0 else 0, 1)

        sessions = await gd_find(self.session, "class_sessions", {
            "class_id": class_id, "school_id": school_id, "status": "completed"
        }, limit=500)
        session_ids = [s["id"] for s in sessions]

        # One streaming pass builds the per-student interaction counts that
        # the summaries below need, instead of holding every interaction and
        # re-scanning the list once per student.
        interaction_counts: Dict[str, int] = {}
        if session_ids:
            async for r in gd_iter_rows(
                self.session, "session_interactions",
                {"session_id": {"$in": session_ids}, "student_id": {"$in": student_ids}},
                max_rows=50000,
            ):
                rid = r.get("student_id")
                interaction_counts[rid] = interaction_counts.get(rid, 0) + 1
        participating_students = set(interaction_counts.keys())
        participation_rate = round((len(participating_students) / len(students) * 100) if students else 0, 1)

        health_doc = await gd_find_one(self.session, "ai_insights",
            {"type": "class_health", "entity_id": class_id, "school_id": school_id})

        student_summaries = []
        for stu in students:
            sid = stu["id"]
            s_att = await gd_count(self.session, "attendance", {
                "student_id": sid, "school_id": school_id,
                "status": {"$in": ["present", "late"]}
            })
            s_total = await gd_count(self.session, "attendance", {
                "student_id": sid, "school_id": school_id
            })
            s_interactions = interaction_counts.get(sid, 0)
            student_summaries.append({
                "student_id": sid,
                "full_name": name_map.get(sid, ""),
                "attendance_rate": round((s_att / s_total * 100) if s_total > 0 else 0, 1),
                "interactions": s_interactions,
            })
        student_summaries.sort(key=lambda x: x["attendance_rate"], reverse=True)

        return {
            "report_type": "class_report",
            "class_id": class_id,
            "class_name": cls.get("name") if cls else class_id,
            "total_students": len(students),
            "total_sessions": len(sessions),
            "attendance_rate": att_rate,
            "participation_rate": participation_rate,
            "health": health_doc.get("data") if health_doc else None,
            "student_summaries": student_summaries,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def generate_attendance_report(
        self, school_id: str, start_date: str, end_date: str,
        class_id: Optional[str] = None,
    ) -> dict:
        """Generate an attendance summary report over a date range."""
        query: dict = {
            "school_id": school_id,
            "date": {"$gte": start_date, "$lte": end_date},
        }
        if class_id:
            query["class_id"] = class_id

        status_totals: Dict[str, int] = {}
        by_date: Dict[str, Dict] = {}
        by_class: Dict[str, Dict] = {}
        total = 0
        async for r in gd_iter_rows(self.session, "attendance", query, max_rows=50000):
            total += 1
            st = r.get("status", "absent")
            status_totals[st] = status_totals.get(st, 0) + 1

            d = r.get("date", "unknown")
            if d not in by_date:
                by_date[d] = {"date": d, "total": 0, "present": 0, "absent": 0, "late": 0}
            by_date[d]["total"] += 1
            by_date[d][st] = by_date[d].get(st, 0) + 1

            cid = r.get("class_id") or "unknown"
            if cid not in by_class:
                by_class[cid] = {"class_id": cid, "total": 0, "present": 0, "absent": 0, "late": 0}
            by_class[cid]["total"] += 1
            by_class[cid][st] = by_class[cid].get(st, 0) + 1

        present = status_totals.get("present", 0)
        late = status_totals.get("late", 0)
        absent = status_totals.get("absent", 0)

        daily = sorted(by_date.values(), key=lambda x: x["date"])
        class_summary = sorted(by_class.values(), key=lambda x: x["class_id"])

        return {
            "report_type": "attendance_report",
            "school_id": school_id,
            "start_date": start_date,
            "end_date": end_date,
            "class_id": class_id,
            "total_records": total,
            "present": present,
            "late": late,
            "absent": absent,
            "overall_rate": round((present + late) / total * 100 if total else 0, 1),
            "daily_breakdown": daily,
            "class_breakdown": class_summary,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def generate_teacher_report(self, teacher_id: str, school_id: str) -> dict:
        """Generate a performance and workload report for a teacher."""
        teacher = await gd_find_one(self.session, "teachers", {"id": teacher_id, "school_id": school_id})
        if not teacher:
            user = await gd_find_one(self.session, "users", {"teacher_id": teacher_id, "tenant_id": school_id})
            teacher = user or {}

        assignments = await gd_find(self.session, "teacher_assignments",
            {"teacher_id": teacher_id, "school_id": school_id}, limit=50)

        sessions = await gd_find(self.session, "class_sessions",
            {"teacher_id": teacher_id, "school_id": school_id, "status": "completed"}, limit=1000)
        session_ids = [s["id"] for s in sessions]

        if session_ids:
            inter_count = await gd_count(self.session, "session_interactions",
                {"session_id": {"$in": session_ids}})
        else:
            inter_count = 0
        avg_interactions = round(inter_count / len(sessions), 1) if sessions else 0

        att_total = 0
        sa_totals: Dict[str, int] = {}
        if session_ids:
            async for r in gd_iter_rows(self.session, "session_attendance",
                                        {"session_id": {"$in": session_ids}}, max_rows=50000):
                att_total += 1
                st = r.get("status", "absent")
                sa_totals[st] = sa_totals.get(st, 0) + 1
        att_present = sa_totals.get("present", 0)
        att_rate = round((att_present / att_total * 100) if att_total else 0, 1)

        # Only the count is reported - count in the database instead of
        # dragging every interaction row into the process.
        total_interactions = await gd_count(self.session, "session_interactions",
                                            {"session_id": {"$in": session_ids}}) if session_ids else 0

        return {
            "report_type": "teacher_report",
            "teacher_id": teacher_id,
            "teacher_name": teacher.get("full_name"),
            "email": teacher.get("email"),
            "assignments": len(assignments),
            "total_sessions": len(sessions),
            "total_interactions": total_interactions,
            "avg_interactions_per_session": avg_interactions,
            "attendance_rate": att_rate,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def generate_school_report(self, school_id: str) -> dict:
        """Generate a whole-school overview report with key statistics."""
        school = await gd_find_one(self.session, "schools", {"id": school_id})
        if not school:
            return {"error": "المدرسة غير موجودة"}

        total_students = await gd_count(self.session, "students", {"school_id": school_id, "is_active": True})
        total_teachers = await gd_count(self.session, "teachers", {"school_id": school_id})
        total_classes = await gd_count(self.session, "classes", {"school_id": school_id})

        att_total = await gd_count(self.session, "attendance", {"school_id": school_id})
        att_present = await gd_count(self.session, "attendance", {
            "school_id": school_id, "status": {"$in": ["present", "late"]}
        })
        att_rate = round((att_present / att_total * 100) if att_total else 0, 1)

        sessions_total = await gd_count(self.session, "class_sessions",
            {"school_id": school_id, "status": "completed"})

        analysis = await gd_find_one(self.session, "ai_insights",
            {"type": "full_school_analysis", "school_id": school_id})

        return {
            "report_type": "school_report",
            "school_id": school_id,
            "school_name": school.get("name", school.get("name_ar")),
            "total_students": total_students,
            "total_teachers": total_teachers,
            "total_classes": total_classes,
            "total_sessions": sessions_total,
            "overall_attendance_rate": att_rate,
            "latest_analysis": analysis.get("data") if analysis else None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
