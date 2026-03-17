"""
Reporting Engine — محرك التقارير المركزي
نَسَّق | NASSAQ

Centralized report generation with MongoDB aggregation pipelines.

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
import math


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
    except Exception:
        return "unknown"


def _month_key(date_str: str) -> str:
    try:
        return date_str[:7]
    except Exception:
        return "unknown"


class ReportingEngine:
    def __init__(self, db, hakim_engine=None):
        self.db = db
        self.hakim_engine = hakim_engine

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
        date_field = "date"
        base_match = {"school_id": school_id, date_field: {"$gte": start_date, "$lte": end_date}}
        class_id = _kw.get("class_id")
        if class_id:
            base_match["class_id"] = class_id

        pipeline_daily = [
            {"$match": base_match},
            {"$group": {
                "_id": {"date": f"${date_field}", "status": "$status"},
                "count": {"$sum": 1},
            }},
            {"$sort": {"_id.date": 1}},
        ]
        raw = await self.db.attendance.aggregate(pipeline_daily).to_list(100000)

        daily: Dict[str, dict] = {}
        for r in raw:
            d = r["_id"]["date"]
            s = r["_id"]["status"]
            if d not in daily:
                daily[d] = {"date": d, "present": 0, "absent": 0, "late": 0, "excused": 0, "total": 0}
            daily[d][s] = daily[d].get(s, 0) + r["count"]
            daily[d]["total"] += r["count"]
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

        pipeline_class = [
            {"$match": base_match},
            {"$group": {
                "_id": {"class_id": "$class_id", "status": "$status"},
                "count": {"$sum": 1},
            }},
        ]
        raw_class = await self.db.attendance.aggregate(pipeline_class).to_list(10000)
        by_class: Dict[str, dict] = {}
        for r in raw_class:
            cid = r["_id"].get("class_id", "unknown")
            s = r["_id"]["status"]
            if cid not in by_class:
                by_class[cid] = {"class_id": cid, "present": 0, "absent": 0, "late": 0, "total": 0}
            by_class[cid][s] = by_class[cid].get(s, 0) + r["count"]
            by_class[cid]["total"] += r["count"]
        for v in by_class.values():
            v["rate"] = round((v["present"] + v.get("late", 0)) / v["total"] * 100, 1) if v["total"] else 0

        classes = await self.db.classes.find(
            {"school_id": school_id}, {"_id": 0, "id": 1, "name": 1, "name_ar": 1}
        ).to_list(200)
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

        sessions = await self.db.class_sessions.find(
            session_query, {"_id": 0, "id": 1, "class_id": 1, "date": 1}
        ).to_list(5000)
        session_ids = [s["id"] for s in sessions]
        session_class = {s["id"]: s.get("class_id") for s in sessions}

        if not session_ids:
            return self._wrap("school_participation", school_id,
                               {"start_date": start_date, "end_date": end_date},
                               {"summary": {"total_sessions": 0, "total_interactions": 0},
                                "by_class": [], "by_type": [], "top_students": []})

        pipeline = [
            {"$match": {"session_id": {"$in": session_ids}}},
            {"$group": {
                "_id": "$interaction_type",
                "count": {"$sum": 1},
            }},
        ]
        type_agg = await self.db.session_interactions.aggregate(pipeline).to_list(50)
        by_type = [{"type": r["_id"], "count": r["count"]} for r in type_agg]

        pipeline_student = [
            {"$match": {"session_id": {"$in": session_ids}}},
            {"$group": {
                "_id": "$student_id",
                "interactions": {"$sum": 1},
                "correct": {"$sum": {"$cond": [{"$eq": ["$answer_result", "correct"]}, 1, 0]}},
            }},
            {"$sort": {"interactions": -1}},
            {"$limit": 20},
        ]
        top_raw = await self.db.session_interactions.aggregate(pipeline_student).to_list(20)

        student_ids = [r["_id"] for r in top_raw if r["_id"]]
        students = await self.db.students.find(
            {"id": {"$in": student_ids}, "school_id": school_id},
            {"_id": 0, "id": 1, "full_name": 1, "name": 1, "name_ar": 1, "class_id": 1}
        ).to_list(200)
        stu_map = {s["id"]: s for s in students}

        top_students = []
        for r in top_raw:
            stu = stu_map.get(r["_id"], {})
            top_students.append({
                "student_id": r["_id"],
                "student_name": stu.get("name_ar") or stu.get("full_name") or stu.get("name", ""),
                "class_id": stu.get("class_id"),
                "interactions": r["interactions"],
                "correct_answers": r["correct"],
            })

        session_date = {s["id"]: s.get("date", "") for s in sessions}

        pipeline_by_session = [
            {"$match": {"session_id": {"$in": session_ids}}},
            {"$group": {
                "_id": "$session_id",
                "count": {"$sum": 1},
            }},
        ]
        sess_counts = await self.db.session_interactions.aggregate(pipeline_by_session).to_list(5000)

        by_class_counts: Dict[str, int] = {}
        weekly_counts: Dict[str, int] = {}
        for sc in sess_counts:
            cid = session_class.get(sc["_id"], "unknown")
            by_class_counts[cid] = by_class_counts.get(cid, 0) + sc["count"]
            wk = _week_key(session_date.get(sc["_id"], ""))
            weekly_counts[wk] = weekly_counts.get(wk, 0) + sc["count"]

        classes = await self.db.classes.find(
            {"school_id": school_id}, {"_id": 0, "id": 1, "name": 1, "name_ar": 1}
        ).to_list(200)
        cn_map = {c["id"]: c.get("name_ar") or c.get("name", c["id"]) for c in classes}

        by_class = [
            {"class_id": cid, "class_name": cn_map.get(cid, cid), "interactions": cnt}
            for cid, cnt in sorted(by_class_counts.items(), key=lambda x: -x[1])
        ]

        trend = [{"week": w, "interactions": c} for w, c in sorted(weekly_counts.items())]

        total_interactions = sum(r["count"] for r in type_agg)

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
        match: dict = {"school_id": school_id}
        date_filter = {"$gte": start_date, "$lte": end_date}
        match["$or"] = [{"created_at": date_filter}, {"date": date_filter}]
        if class_id:
            match["class_id"] = class_id

        pipeline_type = [
            {"$match": match},
            {"$group": {
                "_id": {"$ifNull": ["$type", {"$ifNull": ["$behavior_type", "other"]}]},
                "count": {"$sum": 1},
            }},
            {"$sort": {"count": -1}},
        ]
        type_agg = await self.db.behavior.aggregate(pipeline_type).to_list(50)
        by_type = [{"type": r["_id"], "count": r["count"]} for r in type_agg]
        type_counts = {r["_id"]: r["count"] for r in type_agg}
        total_incidents = sum(r["count"] for r in type_agg)

        pipeline_class = [
            {"$match": match},
            {"$group": {
                "_id": {
                    "class_id": {"$ifNull": ["$class_id", "unknown"]},
                    "type": {"$ifNull": ["$type", {"$ifNull": ["$behavior_type", "other"]}]},
                },
                "count": {"$sum": 1},
            }},
        ]
        class_agg = await self.db.behavior.aggregate(pipeline_class).to_list(1000)

        classes = await self.db.classes.find(
            {"school_id": school_id}, {"_id": 0, "id": 1, "name": 1, "name_ar": 1}
        ).to_list(200)
        cn_map = {c["id"]: c.get("name_ar") or c.get("name", c["id"]) for c in classes}

        class_data: Dict[str, dict] = {}
        for r in class_agg:
            cid = r["_id"]["class_id"]
            btype = r["_id"]["type"]
            if cid not in class_data:
                class_data[cid] = {"class_id": cid, "class_name": cn_map.get(cid, cid), "total": 0, "breakdown": {}}
            class_data[cid]["breakdown"][btype] = r["count"]
            class_data[cid]["total"] += r["count"]
        by_class = sorted(class_data.values(), key=lambda x: -x["total"])

        pipeline_daily = [
            {"$match": match},
            {"$project": {
                "day": {"$substr": [{"$ifNull": ["$date", {"$ifNull": ["$created_at", ""]}]}, 0, 10]},
            }},
            {"$group": {"_id": "$day", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ]
        daily_agg = await self.db.behavior.aggregate(pipeline_daily).to_list(1000)
        trend = [{"date": r["_id"], "count": r["count"]} for r in daily_agg if r["_id"]]

        recent_records = await self.db.behavior.find(
            match, {"_id": 0}
        ).sort("created_at", -1).limit(10).to_list(10)
        student_ids_needed = list(set(r.get("student_id") for r in recent_records if r.get("student_id")))
        stu_docs = await self.db.students.find(
            {"id": {"$in": student_ids_needed}, "school_id": school_id},
            {"_id": 0, "id": 1, "name_ar": 1, "full_name": 1, "name": 1}
        ).to_list(100) if student_ids_needed else []
        stu_map = {s["id"]: s.get("name_ar") or s.get("full_name") or s.get("name", "") for s in stu_docs}
        recent_items = []
        for r in recent_records:
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

        score_match: dict = {"school_id": school_id, "date": {"$gte": start_date, "$lte": end_date}}
        if class_id:
            score_match["class_id"] = class_id

        pipeline_class = [
            {"$match": score_match},
            {"$group": {
                "_id": "$class_id",
                "avg_score": {"$avg": "$score"},
                "max_score": {"$max": "$score"},
                "min_score": {"$min": "$score"},
                "count": {"$sum": 1},
            }},
            {"$sort": {"avg_score": -1}},
        ]
        class_agg = await self.db.student_daily_scores.aggregate(pipeline_class).to_list(200)

        classes = await self.db.classes.find(
            {"school_id": school_id}, {"_id": 0, "id": 1, "name": 1, "name_ar": 1}
        ).to_list(200)
        cn_map = {c["id"]: c.get("name_ar") or c.get("name", c["id"]) for c in classes}

        class_performance = []
        for r in class_agg:
            class_performance.append({
                "class_id": r["_id"],
                "class_name": cn_map.get(r["_id"], r["_id"] or "unknown"),
                "avg_score": round(r["avg_score"], 1) if r["avg_score"] is not None else 0,
                "max_score": r["max_score"] or 0,
                "min_score": r["min_score"] or 0,
                "records": r["count"],
            })

        pipeline_dist = [
            {"$match": score_match},
            {"$bucket": {
                "groupBy": "$score",
                "boundaries": [0, 50, 60, 70, 80, 90, 101],
                "default": "other",
                "output": {"count": {"$sum": 1}},
            }},
        ]
        try:
            dist_raw = await self.db.student_daily_scores.aggregate(pipeline_dist).to_list(20)
        except Exception:
            dist_raw = []

        labels = {0: "0-49", 50: "50-59", 60: "60-69", 70: "70-79", 80: "80-89", 90: "90-100"}
        distribution = []
        for r in dist_raw:
            bucket = r["_id"]
            distribution.append({
                "range": labels.get(bucket, str(bucket)),
                "count": r["count"],
            })

        pipeline_top = [
            {"$match": score_match},
            {"$group": {
                "_id": "$student_id",
                "avg_score": {"$avg": "$score"},
                "total": {"$sum": 1},
            }},
            {"$sort": {"avg_score": -1}},
            {"$limit": 10},
        ]
        top_raw = await self.db.student_daily_scores.aggregate(pipeline_top).to_list(10)

        pipeline_bottom = [
            {"$match": score_match},
            {"$group": {
                "_id": "$student_id",
                "avg_score": {"$avg": "$score"},
                "total": {"$sum": 1},
            }},
            {"$sort": {"avg_score": 1}},
            {"$limit": 10},
        ]
        bottom_raw = await self.db.student_daily_scores.aggregate(pipeline_bottom).to_list(10)

        all_stu_ids = list(set(
            [r["_id"] for r in top_raw if r["_id"]] +
            [r["_id"] for r in bottom_raw if r["_id"]]
        ))
        stu_docs = await self.db.students.find(
            {"id": {"$in": all_stu_ids}, "school_id": school_id},
            {"_id": 0, "id": 1, "name_ar": 1, "full_name": 1, "name": 1, "class_id": 1}
        ).to_list(200)
        stu_map = {s["id"]: s for s in stu_docs}

        def _stu_row(r):
            s = stu_map.get(r["_id"], {})
            return {
                "student_id": r["_id"],
                "student_name": s.get("name_ar") or s.get("full_name") or s.get("name", ""),
                "class_id": s.get("class_id"),
                "avg_score": round(r["avg_score"], 1) if r["avg_score"] is not None else 0,
                "records": r["total"],
            }

        overall_avg_pipeline = [
            {"$match": score_match},
            {"$group": {"_id": None, "avg": {"$avg": "$score"}, "count": {"$sum": 1}}},
        ]
        overall = await self.db.student_daily_scores.aggregate(overall_avg_pipeline).to_list(1)
        overall_avg = round(overall[0]["avg"], 1) if overall and overall[0].get("avg") is not None else 0
        overall_count = overall[0]["count"] if overall else 0

        session_match: dict = {
            "school_id": school_id,
            "status": "completed",
            "date": {"$gte": start_date, "$lte": end_date},
        }
        if class_id:
            session_match["class_id"] = class_id
        pipeline_subject_interactions = [
            {"$match": session_match},
            {"$lookup": {
                "from": "session_interactions",
                "localField": "id",
                "foreignField": "session_id",
                "as": "interactions",
            }},
            {"$group": {
                "_id": "$subject_id",
                "sessions": {"$sum": 1},
                "classes": {"$addToSet": "$class_id"},
                "total_interactions": {"$sum": {"$size": "$interactions"}},
            }},
            {"$sort": {"sessions": -1}},
        ]
        subject_inter_agg = await self.db.class_sessions.aggregate(
            pipeline_subject_interactions
        ).to_list(100)

        subject_ids = [r["_id"] for r in subject_inter_agg if r["_id"]]
        subjects = await self.db.subjects.find(
            {"id": {"$in": subject_ids}, "school_id": school_id},
            {"_id": 0, "id": 1, "name_ar": 1, "name_en": 1}
        ).to_list(200) if subject_ids else []
        subj_map = {s["id"]: s for s in subjects}

        subject_performance = []
        for r in subject_inter_agg:
            sid = r["_id"]
            if not sid:
                continue
            subj = subj_map.get(sid, {})
            subject_performance.append({
                "subject_id": sid,
                "subject_name": subj.get("name_ar") or subj.get("name_en") or sid,
                "sessions": r["sessions"],
                "classes_count": len(r.get("classes", [])),
                "total_interactions": r["total_interactions"],
                "avg_interactions_per_session": round(r["total_interactions"] / r["sessions"], 1) if r["sessions"] else 0,
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

        teacher = await self.db.teachers.find_one(
            {"id": teacher_id, "school_id": school_id}, {"_id": 0, "id": 1, "full_name": 1, "name": 1, "email": 1}
        )
        if not teacher:
            user = await self.db.users.find_one(
                {"teacher_id": teacher_id, "tenant_id": school_id},
                {"_id": 0, "full_name": 1, "email": 1}
            )
            teacher = user or {"id": teacher_id}

        session_match = {
            "teacher_id": teacher_id,
            "school_id": school_id,
            "status": "completed",
        }
        if start_date:
            session_match["date"] = {"$gte": start_date, "$lte": end_date}

        sessions = await self.db.class_sessions.find(
            session_match, {"_id": 0, "id": 1, "class_id": 1, "date": 1, "duration": 1}
        ).to_list(5000)
        session_ids = [s["id"] for s in sessions]

        total_interactions = 0
        if session_ids:
            total_interactions = await self.db.session_interactions.count_documents(
                {"session_id": {"$in": session_ids}}
            )

        classes_taught = list(set(s.get("class_id") for s in sessions if s.get("class_id")))

        classes_docs = await self.db.classes.find(
            {"id": {"$in": classes_taught}, "school_id": school_id}, {"_id": 0, "id": 1, "name": 1, "name_ar": 1}
        ).to_list(200)
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

        sessions = await self.db.class_sessions.find(
            session_match, {"_id": 0, "id": 1, "class_id": 1, "date": 1, "duration": 1}
        ).to_list(5000)
        session_ids = [s["id"] for s in sessions]

        if not session_ids:
            return self._wrap("teacher_session", school_id,
                               {"start_date": start_date, "end_date": end_date},
                               {"sessions": [], "class_engagement": []})

        pipeline = [
            {"$match": {"session_id": {"$in": session_ids}}},
            {"$group": {
                "_id": "$session_id",
                "total_interactions": {"$sum": 1},
                "unique_students": {"$addToSet": "$student_id"},
                "correct": {"$sum": {"$cond": [{"$eq": ["$answer_result", "correct"]}, 1, 0]}},
                "questions": {"$sum": {"$cond": [{"$eq": ["$interaction_type", "question"]}, 1, 0]}},
            }},
        ]
        sess_agg = await self.db.session_interactions.aggregate(pipeline).to_list(5000)
        sess_map = {r["_id"]: r for r in sess_agg}

        session_details = []
        for s in sessions:
            sid = s["id"]
            agg = sess_map.get(sid, {})
            unique = len(agg.get("unique_students", []))
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

        classes_docs = await self.db.classes.find(
            {"school_id": school_id}, {"_id": 0, "id": 1, "name": 1, "name_ar": 1}
        ).to_list(200)
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

        student = await self.db.students.find_one(
            {"id": student_id, "school_id": school_id},
            {"_id": 0, "id": 1, "full_name": 1, "name": 1, "name_ar": 1, "class_id": 1}
        )
        if not student:
            return self._wrap("student_progress", school_id,
                               {"start_date": start_date, "end_date": end_date},
                               {"error": "الطالب غير موجود"})

        att_records = await self.db.attendance.find({
            "student_id": student_id, "school_id": school_id,
            "date": {"$gte": start_date, "$lte": end_date},
        }, {"_id": 0, "date": 1, "status": 1}).to_list(10000)

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

        scores = await self.db.student_daily_scores.find({
            "student_id": student_id, "school_id": school_id,
            "date": {"$gte": start_date, "$lte": end_date},
        }, {"_id": 0, "date": 1, "score": 1}).sort("date", 1).to_list(5000)
        grade_trend = [{"date": s.get("date"), "score": s.get("score", 0)} for s in scores]

        session_ids_raw = await self.db.class_sessions.find(
            {"school_id": school_id, "date": {"$gte": start_date, "$lte": end_date}},
            {"_id": 0, "id": 1, "date": 1}
        ).to_list(10000)
        sid_date = {s["id"]: s.get("date", "") for s in session_ids_raw}
        all_sids = list(sid_date.keys())

        interactions = await self.db.session_interactions.find(
            {"session_id": {"$in": all_sids}, "student_id": student_id},
            {"_id": 0, "session_id": 1, "interaction_type": 1}
        ).to_list(10000) if all_sids else []

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

        records = await self.db.attendance.find({
            "student_id": student_id, "school_id": school_id,
            "date": {"$gte": start_date, "$lte": end_date},
        }, {"_id": 0, "date": 1, "status": 1}).sort("date", 1).to_list(10000)

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

        student = await self.db.students.find_one(
            {"id": student_id, "school_id": school_id},
            {"_id": 0, "id": 1, "full_name": 1, "name": 1, "name_ar": 1, "class_id": 1}
        )
        if not student:
            return self._wrap("student_performance", school_id,
                               {"start_date": start_date, "end_date": end_date},
                               {"error": "الطالب غير موجود"})

        att_total = await self.db.attendance.count_documents({
            "student_id": student_id, "school_id": school_id,
            "date": {"$gte": start_date, "$lte": end_date},
        })
        att_present = await self.db.attendance.count_documents({
            "student_id": student_id, "school_id": school_id,
            "date": {"$gte": start_date, "$lte": end_date},
            "status": {"$in": ["present", "late"]},
        })

        score_pipeline = [
            {"$match": {
                "student_id": student_id, "school_id": school_id,
                "date": {"$gte": start_date, "$lte": end_date},
            }},
            {"$group": {
                "_id": None,
                "avg_score": {"$avg": "$score"},
                "max_score": {"$max": "$score"},
                "min_score": {"$min": "$score"},
                "count": {"$sum": 1},
            }},
        ]
        score_agg = await self.db.student_daily_scores.aggregate(score_pipeline).to_list(1)
        score_stats = score_agg[0] if score_agg else {}

        session_ids_raw = await self.db.class_sessions.find(
            {"school_id": school_id, "date": {"$gte": start_date, "$lte": end_date}},
            {"_id": 0, "id": 1}
        ).to_list(10000)
        all_sids = [s["id"] for s in session_ids_raw]

        inter_pipeline = [
            {"$match": {"session_id": {"$in": all_sids}, "student_id": student_id}},
            {"$group": {
                "_id": "$interaction_type",
                "count": {"$sum": 1},
                "correct": {"$sum": {"$cond": [{"$eq": ["$answer_result", "correct"]}, 1, 0]}},
            }},
        ] if all_sids else []
        inter_agg = await self.db.session_interactions.aggregate(inter_pipeline).to_list(50) if inter_pipeline else []

        participation_breakdown = {r["_id"]: {"count": r["count"], "correct": r["correct"]} for r in inter_agg}
        total_interactions = sum(r["count"] for r in inter_agg)
        total_questions = participation_breakdown.get("question", {}).get("count", 0)
        total_correct = participation_breakdown.get("question", {}).get("correct", 0)

        risk_doc = await self.db.ai_insights.find_one(
            {"type": "student_risk", "entity_id": student_id, "school_id": school_id},
            {"_id": 0, "data": 1}
        )
        risk_data = risk_doc.get("data") if risk_doc else None

        if not risk_data and self.hakim_engine:
            try:
                live_risk = await self.hakim_engine.analyze_student_risk(student_id, school_id)
                if live_risk and not live_risk.get("error"):
                    risk_data = live_risk
            except Exception:
                pass

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
        student = await self.db.students.find_one(
            {"id": student_id, "school_id": school_id}, {"_id": 0}
        )
        if not student:
            return {"error": "الطالب غير موجود"}

        att_total = await self.db.attendance.count_documents({
            "student_id": student_id, "school_id": school_id
        })
        att_present = await self.db.attendance.count_documents({
            "student_id": student_id, "school_id": school_id,
            "status": {"$in": ["present", "late"]}
        })
        att_absent = att_total - att_present
        att_rate = round((att_present / att_total * 100) if att_total > 0 else 0, 1)

        scores = await self.db.student_daily_scores.find({
            "student_id": student_id, "school_id": school_id
        }, {"_id": 0, "score": 1}).to_list(5000)
        total_score = sum(s.get("score", 0) for s in scores)

        session_ids = [s["id"] for s in await self.db.class_sessions.find(
            {"school_id": school_id}, {"_id": 0, "id": 1}
        ).to_list(50000)]
        inter_query: dict = {"student_id": student_id}
        if session_ids:
            inter_query["session_id"] = {"$in": session_ids}
        interactions = await self.db.session_interactions.find(
            inter_query, {"_id": 0, "interaction_type": 1, "answer_result": 1}
        ).to_list(5000)

        questions = [i for i in interactions if i.get("interaction_type") == "question"]
        correct = sum(1 for q in questions if q.get("answer_result") == "correct")
        participations = sum(1 for i in interactions if i.get("interaction_type") == "participation")

        risk_doc = await self.db.ai_insights.find_one(
            {"type": "student_risk", "entity_id": student_id, "school_id": school_id},
            {"_id": 0, "data": 1}
        )

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
                "total_interactions": len(interactions),
                "questions_asked": len(questions),
                "correct_answers": correct,
                "active_participations": participations,
                "accuracy_rate": round((correct / len(questions) * 100) if questions else 0, 1),
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
            classes = await self.db.classes.find(
                {"school_id": school_id}, {"_id": 0, "id": 1, "name": 1}
            ).to_list(200)
            class_summaries = []
            for cls in classes:
                cid = cls["id"]
                stu_count = await self.db.students.count_documents(
                    {"class_id": cid, "school_id": school_id, "is_active": True}
                )
                att_total = await self.db.attendance.count_documents(
                    {"class_id": cid, "school_id": school_id,
                     "date": {"$gte": start_date, "$lte": end_date}}
                )
                att_present = await self.db.attendance.count_documents(
                    {"class_id": cid, "school_id": school_id,
                     "date": {"$gte": start_date, "$lte": end_date},
                     "status": {"$in": ["present", "late"]}}
                )
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
        tt = await self.db.timetables.find_one(
            {"school_id": school_id, "status": "published"},
            {"_id": 0, "id": 1, "name": 1, "status": 1, "created_at": 1, "total_sessions": 1}
        )
        sessions = []
        if tt:
            raw = await self.db.timetable_sessions.find(
                {"timetable_id": tt["id"], "school_id": school_id},
                {"_id": 0, "day": 1, "period": 1, "class_id": 1, "teacher_id": 1,
                 "subject_id": 1, "room": 1}
            ).to_list(5000)
            class_ids = list(set(s.get("class_id", "") for s in raw))
            teacher_ids = list(set(s.get("teacher_id", "") for s in raw))
            subject_ids = list(set(s.get("subject_id", "") for s in raw))
            classes = {c["id"]: c.get("name", c["id"]) for c in await self.db.classes.find(
                {"id": {"$in": class_ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(500)}
            teachers = {t["id"]: t.get("full_name", t["id"]) for t in await self.db.teachers.find(
                {"id": {"$in": teacher_ids}}, {"_id": 0, "id": 1, "full_name": 1}).to_list(500)}
            subjects = {s["id"]: s.get("name_ar", s.get("name", s["id"])) for s in await self.db.subjects.find(
                {"id": {"$in": subject_ids}}, {"_id": 0, "id": 1, "name_ar": 1, "name": 1}).to_list(500)}
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
        cls = await self.db.classes.find_one(
            {"id": class_id, "school_id": school_id}, {"_id": 0, "name": 1, "id": 1}
        )
        students = await self.db.students.find(
            {"class_id": class_id, "school_id": school_id, "is_active": True},
            {"_id": 0, "id": 1, "full_name": 1}
        ).to_list(200)

        student_ids = [s["id"] for s in students]
        name_map = {s["id"]: s.get("full_name", "") for s in students}

        att_total = await self.db.attendance.count_documents({
            "class_id": class_id, "school_id": school_id
        })
        att_present = await self.db.attendance.count_documents({
            "class_id": class_id, "school_id": school_id,
            "status": {"$in": ["present", "late"]}
        })
        att_rate = round((att_present / att_total * 100) if att_total > 0 else 0, 1)

        sessions = await self.db.class_sessions.find({
            "class_id": class_id, "school_id": school_id, "status": "completed"
        }, {"_id": 0, "id": 1}).to_list(500)
        session_ids = [s["id"] for s in sessions]

        interactions = await self.db.session_interactions.find({
            "session_id": {"$in": session_ids},
            "student_id": {"$in": student_ids},
        }, {"_id": 0, "student_id": 1}).to_list(50000) if session_ids else []

        participating_students = set(i["student_id"] for i in interactions)
        participation_rate = round((len(participating_students) / len(students) * 100) if students else 0, 1)

        health_doc = await self.db.ai_insights.find_one(
            {"type": "class_health", "entity_id": class_id, "school_id": school_id},
            {"_id": 0, "data": 1}
        )

        student_summaries = []
        for stu in students:
            sid = stu["id"]
            s_att = await self.db.attendance.count_documents({
                "student_id": sid, "school_id": school_id,
                "status": {"$in": ["present", "late"]}
            })
            s_total = await self.db.attendance.count_documents({
                "student_id": sid, "school_id": school_id
            })
            s_interactions = sum(1 for i in interactions if i["student_id"] == sid)
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
        query: dict = {
            "school_id": school_id,
            "date": {"$gte": start_date, "$lte": end_date},
        }
        if class_id:
            query["class_id"] = class_id

        records = await self.db.attendance.find(query, {"_id": 0}).to_list(100000)

        total = len(records)
        present = sum(1 for r in records if r.get("status") == "present")
        late = sum(1 for r in records if r.get("status") == "late")
        absent = sum(1 for r in records if r.get("status") == "absent")

        by_date: Dict[str, Dict] = {}
        by_class: Dict[str, Dict] = {}

        for r in records:
            d = r.get("date", "")
            if d not in by_date:
                by_date[d] = {"date": d, "total": 0, "present": 0, "absent": 0, "late": 0}
            by_date[d]["total"] += 1
            by_date[d][r.get("status", "absent")] = by_date[d].get(r.get("status", "absent"), 0) + 1

            cid = r.get("class_id", "unknown")
            if cid not in by_class:
                by_class[cid] = {"class_id": cid, "total": 0, "present": 0, "absent": 0, "late": 0}
            by_class[cid]["total"] += 1
            by_class[cid][r.get("status", "absent")] = by_class[cid].get(r.get("status", "absent"), 0) + 1

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
        teacher = await self.db.teachers.find_one(
            {"id": teacher_id, "school_id": school_id}, {"_id": 0}
        )
        if not teacher:
            user = await self.db.users.find_one(
                {"teacher_id": teacher_id, "tenant_id": school_id},
                {"_id": 0, "full_name": 1, "email": 1}
            )
            teacher = user or {}

        assignments = await self.db.teacher_assignments.find(
            {"teacher_id": teacher_id, "school_id": school_id}, {"_id": 0}
        ).to_list(50)

        sessions = await self.db.class_sessions.find(
            {"teacher_id": teacher_id, "school_id": school_id, "status": "completed"},
            {"_id": 0, "id": 1}
        ).to_list(1000)
        session_ids = [s["id"] for s in sessions]

        interactions = await self.db.session_interactions.find(
            {"session_id": {"$in": session_ids}},
            {"_id": 0, "session_id": 1}
        ).to_list(50000) if session_ids else []

        avg_interactions = round(len(interactions) / len(sessions), 1) if sessions else 0

        sa_records = await self.db.session_attendance.find(
            {"session_id": {"$in": session_ids}},
            {"_id": 0, "status": 1}
        ).to_list(50000) if session_ids else []
        att_total = len(sa_records)
        att_present = sum(1 for r in sa_records if r.get("status") == "present")
        att_rate = round((att_present / att_total * 100) if att_total else 0, 1)

        return {
            "report_type": "teacher_report",
            "teacher_id": teacher_id,
            "teacher_name": teacher.get("full_name"),
            "email": teacher.get("email"),
            "assignments": len(assignments),
            "total_sessions": len(sessions),
            "total_interactions": len(interactions),
            "avg_interactions_per_session": avg_interactions,
            "attendance_rate": att_rate,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def generate_school_report(self, school_id: str) -> dict:
        school = await self.db.schools.find_one({"id": school_id}, {"_id": 0})
        if not school:
            return {"error": "المدرسة غير موجودة"}

        total_students = await self.db.students.count_documents({"school_id": school_id, "is_active": True})
        total_teachers = await self.db.teachers.count_documents({"school_id": school_id})
        total_classes = await self.db.classes.count_documents({"school_id": school_id})

        att_total = await self.db.attendance.count_documents({"school_id": school_id})
        att_present = await self.db.attendance.count_documents({
            "school_id": school_id, "status": {"$in": ["present", "late"]}
        })
        att_rate = round((att_present / att_total * 100) if att_total else 0, 1)

        sessions_total = await self.db.class_sessions.count_documents(
            {"school_id": school_id, "status": "completed"})

        analysis = await self.db.ai_insights.find_one(
            {"type": "full_school_analysis", "school_id": school_id},
            {"_id": 0}
        )

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
