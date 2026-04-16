"""
Hakim AI Engine — محرك حكيم للذكاء الأكاديمي
نَسَّق | NASSAQ

Academic Intelligence Layer that analyzes real data from:
- attendance, participation, behaviour, session results, grades

Modules:
1. Student Early Warning System (risk scoring)
2. Participation Intelligence (active/silent students)
3. Behaviour Pattern Detection (trends, repeated issues)
4. Teacher Session Analytics (session quality)
5. Class Health Score (composite class metric)

All insights are stored in the `ai_insights` collection.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import uuid

from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_count, gd_delete_one, gd_delete_many


RISK_WEIGHTS = {
    "attendance": 0.35,
    "participation": 0.25,
    "behaviour": 0.20,
    "academic": 0.20,
}

RISK_CATEGORIES = [
    (0, 25, "critical", "حرج"),
    (25, 50, "high", "مرتفع"),
    (50, 75, "medium", "متوسط"),
    (75, 101, "low", "منخفض"),
]

RISK_RECOMMENDATIONS = {
    "critical": "⚠️ يحتاج تدخل فوري — يُنصح بعقد اجتماع مع ولي الأمر والمرشد الطلابي",
    "high": "يحتاج متابعة مكثفة — يُنصح بوضع خطة تحسين فردية ومتابعة أسبوعية",
    "medium": "يحتاج تحفيز إضافي — يُنصح بمراجعة أدائه وإشراكه في أنشطة تفاعلية",
    "low": "أداء جيد — يُنصح بالاستمرار في التشجيع والمتابعة الدورية",
}


class HakimAIEngine:
    def __init__(self, db):
        self.db = db

    @property
    def session(self):
        return self.db.session

    # ------------------------------------------------------------------
    # 1. Student Early Warning System
    # ------------------------------------------------------------------

    async def analyze_student_risk(
        self, student_id: str, school_id: str, days_back: int = 30
    ) -> Dict[str, Any]:
        """Assess risk factors for a student based on attendance, grades, and behaviour."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")

        attendance_score = await self._calc_attendance_score(student_id, school_id, cutoff)
        participation_score = await self._calc_participation_score(student_id, school_id, cutoff)
        behaviour_score = await self._calc_behaviour_score(student_id, school_id, cutoff)
        academic_score = await self._calc_academic_score(student_id, school_id, cutoff)

        risk_score = round(
            attendance_score * RISK_WEIGHTS["attendance"]
            + participation_score * RISK_WEIGHTS["participation"]
            + behaviour_score * RISK_WEIGHTS["behaviour"]
            + academic_score * RISK_WEIGHTS["academic"],
            1,
        )

        risk_category = "low"
        risk_label_ar = "منخفض"
        for lo, hi, cat, label in RISK_CATEGORIES:
            if lo <= risk_score < hi:
                risk_category = cat
                risk_label_ar = label
                break

        factors = []
        if attendance_score < 50:
            factors.append("انخفاض الحضور")
        if participation_score < 50:
            factors.append("انخفاض المشاركة")
        if behaviour_score < 50:
            factors.append("مشاكل سلوكية")
        if academic_score < 50:
            factors.append("تدني الأداء الأكاديمي")

        student = await gd_find_one(self.session, "students", {"id": student_id, "school_id": school_id})

        return {
            "student_id": student_id,
            "student_name": student.get("full_name") if student else None,
            "class_id": student.get("class_id") if student else None,
            "risk_score": risk_score,
            "risk_score_interpretation": "stability_score: higher = more stable/less at risk (0-100)",
            "risk_category": risk_category,
            "risk_label_ar": risk_label_ar,
            "recommendation": RISK_RECOMMENDATIONS.get(risk_category, ""),
            "factors": factors,
            "breakdown": {
                "attendance": round(attendance_score, 1),
                "participation": round(participation_score, 1),
                "behaviour": round(behaviour_score, 1),
                "academic": round(academic_score, 1),
            },
            "period_days": days_back,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _calc_attendance_score(self, student_id: str, school_id: str, cutoff: str) -> float:
        total = await gd_count(self.session, "attendance", {
            "student_id": student_id, "school_id": school_id, "date": {"$gte": cutoff}
        })
        if total == 0:
            return 100.0
        present = await gd_count(self.session, "attendance", {
            "student_id": student_id, "school_id": school_id,
            "date": {"$gte": cutoff}, "status": {"$in": ["present", "late"]}
        })
        return (present / total) * 100

    async def _calc_participation_score(self, student_id: str, school_id: str, cutoff: str) -> float:
        session_ids = await self._get_school_session_ids(school_id, cutoff)
        if not session_ids:
            return 50.0

        sessions_with_student = await gd_count(self.session, "session_attendance", {
            "student_id": student_id, "status": "present",
            "session_id": {"$in": session_ids},
        })
        if sessions_with_student == 0:
            return 50.0

        interactions = await gd_count(self.session, "session_interactions", {
            "student_id": student_id,
            "session_id": {"$in": session_ids},
        })

        ratio = interactions / max(sessions_with_student, 1)
        return min(100.0, ratio * 100)

    async def _calc_behaviour_score(self, student_id: str, school_id: str, cutoff: str) -> float:
        session_ids = await self._get_school_session_ids(school_id, cutoff)
        if not session_ids:
            return 75.0

        interactions = await gd_find(self.session, "session_interactions", {
            "student_id": student_id, "interaction_type": "behaviour", "session_id": {"$in": session_ids}
        }, limit=500)

        if not interactions:
            return 75.0

        positive = sum(1 for i in interactions if (i.get("behaviour_type") == "positive") or (i.get("behaviour_category") in ("positive", "respect", "teamwork")))
        negative = sum(1 for i in interactions if (i.get("behaviour_type") == "negative") or (i.get("behaviour_category") in ("negative", "disruption")))
        total = len(interactions)
        if total == 0:
            return 75.0

        return min(100.0, (positive / total) * 100 + 25)

    async def _calc_academic_score(self, student_id: str, school_id: str, cutoff: str) -> float:
        scores = await gd_find(self.session, "student_daily_scores", {
            "student_id": student_id,
            "school_id": school_id,
            "date": {"$gte": cutoff},
        }, limit=500)

        if not scores:
            grades = await gd_find(self.session, "student_grades", {
                "student_id": student_id,
                "tenant_id": school_id,
            }, limit=100)
            if grades:
                avg = sum(g.get("percentage", 0) for g in grades) / len(grades)
                return min(100.0, avg)
            return 60.0

        total_score = sum(s.get("score", 0) for s in scores)
        max_possible = len(scores) * 5
        if max_possible <= 0:
            return 60.0
        return min(100.0, (total_score / max_possible) * 100)

    async def _get_school_session_ids(self, school_id: str, cutoff: str) -> List[str]:
        sessions = await gd_find(self.session, "class_sessions", {
            "school_id": school_id, "status": "completed",
            "date": {"$gte": cutoff},
        }, limit=5000)
        return [s["id"] for s in sessions]

    # ------------------------------------------------------------------
    # 2. Participation Intelligence
    # ------------------------------------------------------------------

    async def analyze_class_participation(
        self, class_id: str, school_id: str, days_back: int = 30
    ) -> Dict[str, Any]:
        """Evaluate participation patterns across a class."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")

        students = await gd_find(self.session, "students", {
            "class_id": class_id, "school_id": school_id, "is_active": True
        }, limit=200)

        if not students:
            return {"class_id": class_id, "students": [], "summary": {}}

        student_ids = [s["id"] for s in students]
        name_map = {s["id"]: s.get("full_name", "") for s in students}

        sessions = await gd_find(self.session, "class_sessions", {
            "class_id": class_id, "school_id": school_id, "status": "completed",
            "date": {"$gte": cutoff},
        }, limit=500)
        session_ids = [s["id"] for s in sessions]

        interactions = await gd_find(self.session, "session_interactions", {
            "session_id": {"$in": session_ids},
            "student_id": {"$in": student_ids},
        }, limit=10000)

        student_stats: Dict[str, Dict] = {}
        for sid in student_ids:
            student_stats[sid] = {
                "student_id": sid,
                "full_name": name_map.get(sid, ""),
                "total_interactions": 0,
                "questions": 0,
                "correct_answers": 0,
                "participations": 0,
                "behaviours": 0,
            }

        for inter in interactions:
            sid = inter["student_id"]
            if sid not in student_stats:
                continue
            student_stats[sid]["total_interactions"] += 1
            itype = inter.get("interaction_type")
            if itype == "question":
                student_stats[sid]["questions"] += 1
                if inter.get("answer_result") == "correct":
                    student_stats[sid]["correct_answers"] += 1
            elif itype == "participation":
                student_stats[sid]["participations"] += 1
            elif itype == "behaviour":
                student_stats[sid]["behaviours"] += 1

        ranked = sorted(student_stats.values(), key=lambda x: x["total_interactions"], reverse=True)

        most_active = ranked[:5] if len(ranked) >= 5 else ranked
        silent = [s for s in ranked if s["total_interactions"] == 0]
        needs_motivation = [s for s in ranked if 0 < s["total_interactions"] <= 2]

        total_interactions = sum(s["total_interactions"] for s in ranked)
        avg_interactions = total_interactions / len(ranked) if ranked else 0

        return {
            "class_id": class_id,
            "total_sessions": len(sessions),
            "total_students": len(students),
            "total_interactions": total_interactions,
            "average_interactions_per_student": round(avg_interactions, 1),
            "most_active": most_active,
            "silent_students": silent,
            "needs_motivation": needs_motivation,
            "all_students": ranked,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # 3. Behaviour Pattern Detection
    # ------------------------------------------------------------------

    async def analyze_student_behaviour_patterns(
        self, student_id: str, school_id: str, days_back: int = 60
    ) -> Dict[str, Any]:
        """Detect recurring behaviour trends for a student."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
        session_ids = await self._get_school_session_ids(school_id, cutoff)

        if session_ids:
            interactions = await gd_find(self.session, "session_interactions", {
                "student_id": student_id, "interaction_type": "behaviour", "session_id": {"$in": session_ids}
            }, limit=500)
        else:
            interactions = []

        behaviour_records = await gd_find(self.session, "behaviour_records", {
            "student_id": student_id,
            "tenant_id": school_id,
            "incident_date": {"$gte": cutoff},
        }, limit=500)

        positive_count = 0
        negative_count = 0
        type_freq: Dict[str, int] = {}

        for inter in interactions:
            bcat = inter.get("behaviour_category", inter.get("behaviour_type", ""))
            if bcat in ("positive", "respect", "teamwork"):
                positive_count += 1
            elif bcat in ("negative", "disruption"):
                negative_count += 1
            bt = inter.get("behaviour_type") or bcat
            type_freq[bt] = type_freq.get(bt, 0) + 1

        for rec in behaviour_records:
            cat = rec.get("category", "")
            if cat == "positive":
                positive_count += 1
            elif cat == "negative":
                negative_count += 1
            bt = rec.get("behaviour_type_name", cat)
            type_freq[bt] = type_freq.get(bt, 0) + 1

        total = positive_count + negative_count
        if total == 0:
            trend = "neutral"
        elif positive_count >= negative_count * 2:
            trend = "improving"
        elif negative_count >= positive_count * 2:
            trend = "declining"
        else:
            trend = "stable"

        repeated = {k: v for k, v in type_freq.items() if v >= 3}

        student = await gd_find_one(self.session, "students", {"id": student_id, "school_id": school_id})

        return {
            "student_id": student_id,
            "student_name": student.get("full_name") if student else None,
            "positive_count": positive_count,
            "negative_count": negative_count,
            "trend": trend,
            "repeated_patterns": repeated,
            "type_frequency": type_freq,
            "total_records": total,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # 4. Teacher Session Analytics
    # ------------------------------------------------------------------

    async def analyze_teacher_sessions(
        self, teacher_id: str, school_id: str, days_back: int = 30
    ) -> Dict[str, Any]:
        """Analyze session metrics and teaching patterns for a teacher."""
        try:
            return await self._analyze_teacher_sessions_impl(teacher_id, school_id, days_back)
        except Exception as e:
            import logging
            logging.getLogger("nassaq.hakim").error(f"analyze_teacher_sessions failed: {e}", exc_info=True)
            return {
                "teacher_id": teacher_id,
                "error": "تعذّر تحليل بيانات المعلم مؤقتاً",
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            }

    async def _analyze_teacher_sessions_impl(
        self, teacher_id: str, school_id: str, days_back: int = 30
    ) -> Dict[str, Any]:
        """Internal implementation for teacher session analysis."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")

        sessions = await gd_find(self.session, "class_sessions", {
            "teacher_id": teacher_id, "school_id": school_id, "status": "completed",
            "date": {"$gte": cutoff},
        }, limit=1000)

        if not sessions:
            return {
                "teacher_id": teacher_id,
                "total_sessions": 0,
                "message": "لا توجد حصص مكتملة",
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            }

        session_ids = [s["id"] for s in sessions]
        total_sessions = len(sessions)

        interactions = await gd_find(self.session, "session_interactions", {
            "session_id": {"$in": session_ids},
        }, limit=50000)

        session_interaction_count: Dict[str, int] = {}
        total_questions = 0
        total_correct = 0
        total_participations = 0
        total_behaviours = 0

        for inter in interactions:
            sid = inter["session_id"]
            session_interaction_count[sid] = session_interaction_count.get(sid, 0) + 1
            itype = inter.get("interaction_type")
            if itype == "question":
                total_questions += 1
                if inter.get("answer_result") == "correct":
                    total_correct += 1
            elif itype == "participation":
                total_participations += 1
            elif itype == "behaviour":
                total_behaviours += 1

        avg_interactions_per_session = len(interactions) / total_sessions if total_sessions else 0

        sa_records = await gd_find(self.session, "session_attendance", {
            "session_id": {"$in": session_ids},
        }, limit=50000)

        total_attendance = len(sa_records)
        total_present = sum(1 for r in sa_records if r.get("status") == "present")
        attendance_rate = (total_present / total_attendance * 100) if total_attendance > 0 else 0

        sessions_with_interactions = len(session_interaction_count)
        engagement_rate = (sessions_with_interactions / total_sessions * 100) if total_sessions else 0

        quality_score = min(100, round(
            (attendance_rate * 0.3)
            + (engagement_rate * 0.3)
            + (min(avg_interactions_per_session / 8, 1) * 100 * 0.4)
        ))

        classes_taught = list(set(s.get("class_id") for s in sessions if s.get("class_id")))
        all_classes = await gd_find(self.session, "classes", {"id": {"$in": classes_taught}, "school_id": school_id})
        class_lookup = {c["id"]: c for c in all_classes}
        class_breakdown = []
        for cid in classes_taught:
            c_sessions = [s for s in sessions if s.get("class_id") == cid]
            c_sids = {s["id"] for s in c_sessions}
            c_interactions = sum(1 for i in interactions if i["session_id"] in c_sids)
            cls = class_lookup.get(cid, {})
            class_breakdown.append({
                "class_id": cid,
                "class_name": cls.get("name") if cls else cid,
                "sessions": len(c_sessions),
                "interactions": c_interactions,
                "avg_interactions": round(c_interactions / len(c_sessions), 1) if c_sessions else 0,
            })

        teacher = await gd_find_one(self.session, "teachers", {"id": teacher_id, "school_id": school_id})
        if not teacher:
            user = await gd_find_one(self.session, "users", {"teacher_id": teacher_id, "tenant_id": school_id})
            teacher = user or {}

        return {
            "teacher_id": teacher_id,
            "teacher_name": teacher.get("full_name"),
            "total_sessions": total_sessions,
            "total_interactions": len(interactions),
            "avg_interactions_per_session": round(avg_interactions_per_session, 1),
            "total_questions": total_questions,
            "correct_answer_rate": round((total_correct / total_questions * 100) if total_questions else 0, 1),
            "total_participations": total_participations,
            "total_behaviours": total_behaviours,
            "attendance_rate": round(attendance_rate, 1),
            "engagement_rate": round(engagement_rate, 1),
            "quality_score": quality_score,
            "classes_taught": len(classes_taught),
            "class_breakdown": class_breakdown,
            "period_days": days_back,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # 5. Class Health Score
    # ------------------------------------------------------------------

    async def analyze_class_health(
        self, class_id: str, school_id: str, days_back: int = 30
    ) -> Dict[str, Any]:
        """Compute a composite health score for a class."""
        try:
            return await self._analyze_class_health_impl(class_id, school_id, days_back)
        except Exception as e:
            import logging
            logging.getLogger("nassaq.hakim").error(f"analyze_class_health failed: {e}", exc_info=True)
            return {
                "class_id": class_id,
                "error": "تعذّر تحليل صحة الفصل مؤقتاً",
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            }

    async def _analyze_class_health_impl(
        self, class_id: str, school_id: str, days_back: int = 30
    ) -> Dict[str, Any]:
        """Internal implementation for class health analysis."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")

        students = await gd_find(self.session, "students", {
            "class_id": class_id, "school_id": school_id, "is_active": True
        }, limit=200)
        student_ids = [s["id"] for s in students]
        total_students = len(student_ids)

        if total_students == 0:
            return {
                "class_id": class_id,
                "health_score": 0,
                "message": "لا يوجد طلاب في الفصل",
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            }

        att_total = await gd_count(self.session, "attendance", {
            "class_id": class_id, "school_id": school_id, "date": {"$gte": cutoff}
        })
        att_present = await gd_count(self.session, "attendance", {
            "class_id": class_id, "school_id": school_id,
            "date": {"$gte": cutoff}, "status": {"$in": ["present", "late"]}
        })
        attendance_rate = (att_present / att_total * 100) if att_total > 0 else 85

        sessions = await gd_find(self.session, "class_sessions", {
            "class_id": class_id, "school_id": school_id, "status": "completed",
            "date": {"$gte": cutoff},
        }, limit=500)
        session_ids = [s["id"] for s in sessions]

        interactions = await gd_find(self.session, "session_interactions", {
            "session_id": {"$in": session_ids},
            "student_id": {"$in": student_ids},
        }, limit=10000)

        participating_students = set(i["student_id"] for i in interactions)
        participation_rate = (len(participating_students) / total_students * 100) if total_students else 0

        positive_b = sum(1 for i in interactions if (i.get("interaction_type") == "behaviour") and ((i.get("behaviour_type") == "positive") or (i.get("behaviour_category") in ("positive", "respect", "teamwork"))))
        negative_b = sum(1 for i in interactions if (i.get("interaction_type") == "behaviour") and ((i.get("behaviour_type") == "negative") or (i.get("behaviour_category") in ("negative", "disruption"))))
        total_b = positive_b + negative_b
        behaviour_score = ((positive_b / total_b) * 100) if total_b > 0 else 75

        scores = await gd_find(self.session, "student_daily_scores", {
            "student_id": {"$in": student_ids},
            "school_id": school_id,
            "date": {"$gte": cutoff},
        }, limit=10000)
        if scores:
            total_score = sum(s.get("score", 0) for s in scores)
            max_possible = len(scores) * 5
            academic_score = min(100, (total_score / max_possible * 100)) if max_possible > 0 else 60
        else:
            academic_score = 60

        health_score = round(
            attendance_rate * 0.30
            + participation_rate * 0.25
            + behaviour_score * 0.25
            + academic_score * 0.20,
            1,
        )

        if health_score >= 80:
            health_label = "ممتاز"
            health_category = "excellent"
        elif health_score >= 65:
            health_label = "جيد"
            health_category = "good"
        elif health_score >= 50:
            health_label = "متوسط"
            health_category = "average"
        else:
            health_label = "يحتاج تحسين"
            health_category = "needs_improvement"

        cls = await gd_find_one(self.session, "classes", {"id": class_id, "school_id": school_id})

        return {
            "class_id": class_id,
            "class_name": cls.get("name") if cls else class_id,
            "health_score": health_score,
            "health_category": health_category,
            "health_label_ar": health_label,
            "total_students": total_students,
            "total_sessions": len(sessions),
            "breakdown": {
                "attendance_rate": round(attendance_rate, 1),
                "participation_rate": round(participation_rate, 1),
                "behaviour_score": round(behaviour_score, 1),
                "academic_score": round(academic_score, 1),
            },
            "period_days": days_back,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Batch Analysis — full school
    # ------------------------------------------------------------------

    async def run_full_analysis(self, school_id: str, days_back: int = 30) -> Dict[str, Any]:
        """Execute all analysis pipelines for a school and store insights."""
        now = datetime.now(timezone.utc)

        students = await gd_find(self.session, "students", {
            "school_id": school_id, "is_active": True
        }, limit=10000)
        class_ids = list(set(s.get("class_id") for s in students if s.get("class_id")))

        student_risks = []
        risk_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for student in students:
            risk = await self.analyze_student_risk(student["id"], school_id, days_back)
            student_risks.append(risk)
            risk_counts[risk["risk_category"]] = risk_counts.get(risk["risk_category"], 0) + 1

        class_healths = []
        class_participations = []
        for cid in class_ids:
            health = await self.analyze_class_health(cid, school_id, days_back)
            class_healths.append(health)
            participation = await self.analyze_class_participation(cid, school_id, days_back)
            class_participations.append(participation)

        student_behaviours = []
        for student in students:
            bp = await self.analyze_student_behaviour_patterns(student["id"], school_id, days_back)
            student_behaviours.append(bp)

        teacher_ids_list = await gd_find(self.session, "teacher_assignments", {
            "school_id": school_id, "is_active": True
        }, limit=200)
        teacher_ids = list(set(t["teacher_id"] for t in teacher_ids_list))

        teacher_analytics = []
        for tid in teacher_ids:
            ta = await self.analyze_teacher_sessions(tid, school_id, days_back)
            teacher_analytics.append(ta)

        at_risk = [r for r in student_risks if r["risk_category"] in ("critical", "high")]
        at_risk.sort(key=lambda x: x["risk_score"])

        insights = []
        if risk_counts["critical"] > 0:
            insights.append({
                "type": "warning",
                "title_ar": f"يوجد {risk_counts['critical']} طالب بحاجة تدخل فوري",
                "category": "student_risk",
                "severity": "critical",
            })
        if risk_counts["high"] > 0:
            insights.append({
                "type": "warning",
                "title_ar": f"يوجد {risk_counts['high']} طالب بمخاطر مرتفعة",
                "category": "student_risk",
                "severity": "high",
            })

        low_health_classes = [c for c in class_healths if c["health_score"] < 50]
        if low_health_classes:
            names = ", ".join(c.get("class_name", c["class_id"]) for c in low_health_classes[:3])
            insights.append({
                "type": "warning",
                "title_ar": f"فصول تحتاج تحسين: {names}",
                "category": "class_health",
                "severity": "high",
            })

        best_classes = sorted(class_healths, key=lambda x: x["health_score"], reverse=True)[:3]
        if best_classes:
            insights.append({
                "type": "achievement",
                "title_ar": f"أفضل فصل: {best_classes[0].get('class_name', '')} ({best_classes[0]['health_score']}%)",
                "category": "class_health",
                "severity": "info",
            })

        silent_students_total = sum(len(p.get("silent_students", [])) for p in class_participations)
        if silent_students_total > 0:
            insights.append({
                "type": "info",
                "title_ar": f"يوجد {silent_students_total} طالب لم يشارك في أي حصة",
                "category": "participation",
                "severity": "medium",
            })

        declining_behaviour = [b for b in student_behaviours if b.get("trend") == "declining"]
        if declining_behaviour:
            insights.append({
                "type": "warning",
                "title_ar": f"يوجد {len(declining_behaviour)} طالب بسلوك متراجع",
                "category": "behaviour",
                "severity": "high",
            })

        analysis_id = str(uuid.uuid4())
        analysis_doc = {
            "id": analysis_id,
            "type": "full_school_analysis",
            "entity_id": school_id,
            "school_id": school_id,
            "data": {
                "risk_counts": risk_counts,
                "at_risk_students": [{"student_id": r["student_id"], "student_name": r["student_name"], "risk_score": r["risk_score"], "risk_category": r["risk_category"]} for r in at_risk[:20]],
                "class_healths": [{"class_id": c["class_id"], "class_name": c.get("class_name"), "health_score": c["health_score"], "health_category": c["health_category"]} for c in class_healths],
                "class_participations": [{"class_id": p["class_id"], "total_interactions": p.get("total_interactions", 0), "silent_count": len(p.get("silent_students", []))} for p in class_participations],
                "teacher_analytics": [{"teacher_id": t["teacher_id"], "teacher_name": t.get("teacher_name"), "quality_score": t.get("quality_score", 0), "total_sessions": t["total_sessions"]} for t in teacher_analytics],
                "behaviour_summary": {"declining": len(declining_behaviour), "total_analyzed": len(student_behaviours)},
                "insights": insights,
            },
            "created_at": now.isoformat(),
        }

        await gd_insert(self.session, "ai_insights", analysis_doc)

        created_at_iso = now.isoformat()

        for risk in student_risks:
            await self._upsert_insight("student_risk", risk["student_id"], school_id, risk, created_at_iso)

        for health in class_healths:
            await self._upsert_insight("class_health", health["class_id"], school_id, health, created_at_iso)

        for participation in class_participations:
            await self._upsert_insight("class_participation", participation["class_id"], school_id, participation, created_at_iso)

        for bp in student_behaviours:
            await self._upsert_insight("student_behaviour", bp["student_id"], school_id, bp, created_at_iso)

        for ta in teacher_analytics:
            await self._upsert_insight("teacher_analytics", ta["teacher_id"], school_id, ta, created_at_iso)

        return {
            "analysis_id": analysis_id,
            "school_id": school_id,
            "students_analyzed": len(students),
            "classes_analyzed": len(class_ids),
            "teachers_analyzed": len(teacher_ids),
            "risk_counts": risk_counts,
            "at_risk_students_count": len(at_risk),
            "at_risk_students": [{"student_id": r["student_id"], "student_name": r["student_name"], "risk_score": r["risk_score"], "risk_category": r["risk_category"]} for r in at_risk[:20]],
            "insights": insights,
            "class_health_summary": [{"class_id": c["class_id"], "class_name": c.get("class_name"), "health_score": c["health_score"]} for c in sorted(class_healths, key=lambda x: x["health_score"])],
            "analyzed_at": now.isoformat(),
        }

    async def _upsert_insight(self, insight_type: str, entity_id: str, school_id: str, data: Dict, created_at: str):
        existing = await gd_find_one(self.session, "ai_insights", {"type": insight_type, "entity_id": entity_id, "school_id": school_id})
        if existing:
            await gd_update_one(self.session, "ai_insights", {"type": insight_type, "entity_id": entity_id, "school_id": school_id}, {
                "data": data,
                "updated_at": created_at,
            })
        else:
            await gd_insert(self.session, "ai_insights", {
                "id": str(uuid.uuid4()),
                "type": insight_type,
                "entity_id": entity_id,
                "school_id": school_id,
                "data": data,
                "created_at": created_at,
            })

    # ------------------------------------------------------------------
    # Insight retrieval helpers
    # ------------------------------------------------------------------

    async def get_stored_insight(self, insight_type: str, entity_id: str, school_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a previously stored AI insight by ID."""
        doc = await gd_find_one(self.session, "ai_insights", {
            "type": insight_type, "entity_id": entity_id, "school_id": school_id
        })
        return doc

    async def get_school_insights(self, school_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """List stored AI insights for a school, with optional filters."""
        docs = await gd_find(self.session, "ai_insights", {
            "school_id": school_id
        }, order_by="created_at", desc_order=True, limit=limit)
        return docs

    # ------------------------------------------------------------------
    # 6. Auto-Intervention System
    # ------------------------------------------------------------------

    async def execute_auto_interventions(
        self, school_id: str, days_back: int = 30
    ) -> Dict[str, Any]:
        """Trigger automatic interventions based on risk thresholds."""
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(days=days_back)).strftime("%Y-%m-%d")

        students = await gd_find(self.session, "students", {
            "school_id": school_id, "is_active": True
        }, limit=10000)

        interventions_created = []
        notifications_sent = []

        for student in students:
            risk = await self.analyze_student_risk(student["id"], school_id, days_back)
            if risk["risk_category"] not in ("critical", "high"):
                continue

            existing = await gd_find_one(self.session, "ai_interventions", {
                "student_id": student["id"],
                "school_id": school_id,
                "status": {"$in": ["active", "pending"]},
                "created_at": {"$gte": (now - timedelta(days=14)).isoformat()},
            })
            if existing:
                continue

            plan = self._build_intervention_plan(risk)
            intervention_id = str(uuid.uuid4())
            intervention = {
                "id": intervention_id,
                "student_id": student["id"],
                "student_name": student.get("full_name"),
                "class_id": student.get("class_id"),
                "school_id": school_id,
                "risk_score": risk["risk_score"],
                "risk_category": risk["risk_category"],
                "factors": risk["factors"],
                "plan": plan,
                "status": "active",
                "created_at": now.isoformat(),
                "expires_at": (now + timedelta(days=30)).isoformat(),
                "follow_ups": [],
            }
            await gd_insert(self.session, "ai_interventions", intervention)
            interventions_created.append(intervention)

            notif_id = str(uuid.uuid4())
            severity = "urgent" if risk["risk_category"] == "critical" else "high"
            notif = {
                "id": notif_id,
                "tenant_id": school_id,
                "type": "ai_intervention",
                "title": f"⚠️ تنبيه: الطالب {student.get('full_name', '')} يحتاج تدخل",
                "body": f"مستوى الخطورة: {risk.get('risk_label_ar', risk['risk_category'])}. {risk['recommendation']}",
                "priority": severity,
                "target_roles": ["school_principal", "school_admin"],
                "data": {"intervention_id": intervention_id, "student_id": student["id"]},
                "is_read": False,
                "created_at": now.isoformat(),
            }
            await gd_insert(self.session, "notifications", notif)
            notifications_sent.append(notif_id)

        return {
            "school_id": school_id,
            "students_scanned": len(students),
            "interventions_created": len(interventions_created),
            "notifications_sent": len(notifications_sent),
            "interventions": [
                {
                    "student_id": i["student_id"],
                    "student_name": i["student_name"],
                    "risk_category": i["risk_category"],
                    "risk_score": i["risk_score"],
                    "plan_actions": len(i["plan"]["actions"]),
                }
                for i in interventions_created
            ],
            "executed_at": now.isoformat(),
        }

    def _build_intervention_plan(self, risk: Dict) -> Dict:
        actions = []
        priority = 1
        factors = risk.get("factors", [])
        category = risk.get("risk_category", "medium")

        if "انخفاض الحضور" in factors:
            actions.append({
                "priority": priority,
                "type": "attendance_followup",
                "title_ar": "متابعة الحضور",
                "description_ar": "التواصل مع ولي الأمر بشأن الغياب المتكرر ووضع خطة حضور",
                "responsible": "class_teacher",
                "deadline_days": 3,
            })
            priority += 1

        if "انخفاض المشاركة" in factors:
            actions.append({
                "priority": priority,
                "type": "participation_boost",
                "title_ar": "تعزيز المشاركة",
                "description_ar": "إشراك الطالب بأنشطة تفاعلية واستخدام الاختيار العشوائي لتشجيعه",
                "responsible": "subject_teachers",
                "deadline_days": 7,
            })
            priority += 1

        if "مشاكل سلوكية" in factors:
            actions.append({
                "priority": priority,
                "type": "behaviour_plan",
                "title_ar": "خطة تعديل سلوك",
                "description_ar": "إعداد خطة تعديل سلوك بالتنسيق مع المرشد الطلابي",
                "responsible": "counselor",
                "deadline_days": 5,
            })
            priority += 1

        if "تدني الأداء الأكاديمي" in factors:
            actions.append({
                "priority": priority,
                "type": "academic_support",
                "title_ar": "دعم أكاديمي",
                "description_ar": "توفير حصص تقوية ومتابعة أسبوعية للأداء الأكاديمي",
                "responsible": "subject_teachers",
                "deadline_days": 7,
            })
            priority += 1

        if category == "critical":
            actions.append({
                "priority": 0,
                "type": "parent_meeting",
                "title_ar": "اجتماع عاجل مع ولي الأمر",
                "description_ar": "عقد اجتماع فوري مع ولي الأمر والمرشد الطلابي لمناقشة الوضع",
                "responsible": "school_principal",
                "deadline_days": 2,
            })

        actions.sort(key=lambda x: x["priority"])

        return {
            "risk_category": category,
            "total_actions": len(actions),
            "actions": actions,
            "review_after_days": 14 if category == "critical" else 30,
        }

    # ------------------------------------------------------------------
    # 7. Improvement Plan for Individual Student
    # ------------------------------------------------------------------

    async def generate_improvement_plan(
        self, student_id: str, school_id: str, days_back: int = 30
    ) -> Dict[str, Any]:
        """Create a structured improvement plan for a student."""
        risk = await self.analyze_student_risk(student_id, school_id, days_back)
        behaviour = await self.analyze_student_behaviour_patterns(student_id, school_id, days_back)
        grade_trend = await self.detect_student_grade_trend(student_id, school_id)

        plan = self._build_intervention_plan(risk)

        strengths = []
        weaknesses = []

        bd = risk.get("breakdown", {})
        if bd.get("attendance", 0) >= 80:
            strengths.append("انتظام في الحضور")
        else:
            weaknesses.append("تراجع في الحضور")

        if bd.get("participation", 0) >= 60:
            strengths.append("مشاركة فعّالة")
        else:
            weaknesses.append("ضعف المشاركة")

        if bd.get("behaviour", 0) >= 70:
            strengths.append("سلوك إيجابي")
        elif behaviour.get("trend") == "declining":
            weaknesses.append("سلوك متراجع")

        if bd.get("academic", 0) >= 70:
            strengths.append("أداء أكاديمي جيد")
        else:
            weaknesses.append("تدني الأداء الأكاديمي")

        if grade_trend.get("trend") == "declining":
            weaknesses.append("تراجع في الدرجات")
        elif grade_trend.get("trend") == "improving":
            strengths.append("تحسن في الدرجات")

        goals = []
        if "تراجع في الحضور" in weaknesses:
            goals.append({"goal_ar": "رفع نسبة الحضور إلى 90% خلال شهر", "metric": "attendance_rate", "target": 90})
        if "ضعف المشاركة" in weaknesses:
            goals.append({"goal_ar": "المشاركة في 3 حصص على الأقل أسبوعياً", "metric": "weekly_participations", "target": 3})
        if "تدني الأداء الأكاديمي" in weaknesses:
            goals.append({"goal_ar": "رفع المعدل الأكاديمي إلى 70% خلال شهرين", "metric": "academic_average", "target": 70})
        if "سلوك متراجع" in weaknesses:
            goals.append({"goal_ar": "تقليل الملاحظات السلبية إلى صفر خلال أسبوعين", "metric": "negative_behaviours", "target": 0})

        student = await gd_find_one(self.session, "students", {
            "id": student_id, "school_id": school_id
        })

        return {
            "student_id": student_id,
            "student_name": student.get("full_name") if student else None,
            "class_id": student.get("class_id") if student else None,
            "risk_assessment": {
                "score": risk["risk_score"],
                "category": risk["risk_category"],
                "label_ar": risk["risk_label_ar"],
            },
            "strengths": strengths,
            "weaknesses": weaknesses,
            "goals": goals,
            "action_plan": plan,
            "grade_trend": grade_trend.get("trend", "stable"),
            "behaviour_trend": behaviour.get("trend", "neutral"),
            "review_date": (datetime.now(timezone.utc) + timedelta(days=plan["review_after_days"])).strftime("%Y-%m-%d"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # 8. Grade Decline Detection
    # ------------------------------------------------------------------

    async def detect_student_grade_trend(
        self, student_id: str, school_id: str
    ) -> Dict[str, Any]:
        """Compute the grade trend direction for a student."""
        grades = await gd_find(self.session, "student_grades", {
            "student_id": student_id, "tenant_id": school_id
        }, order_by="graded_at", desc_order=False, limit=200)

        if len(grades) < 2:
            return {"student_id": student_id, "trend": "insufficient_data", "grades_count": len(grades)}

        mid = len(grades) // 2
        first_half = grades[:mid]
        second_half = grades[mid:]

        avg_first = sum(g.get("percentage", 0) for g in first_half) / len(first_half)
        avg_second = sum(g.get("percentage", 0) for g in second_half) / len(second_half)
        change = avg_second - avg_first

        if change <= -10:
            trend = "declining"
        elif change >= 10:
            trend = "improving"
        elif change <= -5:
            trend = "slightly_declining"
        elif change >= 5:
            trend = "slightly_improving"
        else:
            trend = "stable"

        subject_trends = {}
        subject_grades: Dict[str, List] = {}
        for g in grades:
            sid = g.get("subject_id", "unknown")
            if sid not in subject_grades:
                subject_grades[sid] = []
            subject_grades[sid].append(g.get("percentage", 0))

        for sid, sg in subject_grades.items():
            if len(sg) >= 2:
                s_mid = len(sg) // 2
                s_avg1 = sum(sg[:s_mid]) / len(sg[:s_mid])
                s_avg2 = sum(sg[s_mid:]) / len(sg[s_mid:])
                s_change = s_avg2 - s_avg1
                if s_change <= -10:
                    subject_trends[sid] = "declining"
                elif s_change >= 10:
                    subject_trends[sid] = "improving"
                else:
                    subject_trends[sid] = "stable"

        return {
            "student_id": student_id,
            "trend": trend,
            "average_change": round(change, 1),
            "first_period_avg": round(avg_first, 1),
            "second_period_avg": round(avg_second, 1),
            "grades_count": len(grades),
            "subject_trends": subject_trends,
        }

    async def detect_grade_decline_alerts(
        self, school_id: str, threshold: float = -10.0
    ) -> Dict[str, Any]:
        """Identify students with significant grade declines."""
        students = await gd_find(self.session, "students", {
            "school_id": school_id, "is_active": True
        }, limit=10000)

        declining_students = []
        for student in students:
            trend_data = await self.detect_student_grade_trend(student["id"], school_id)
            if trend_data.get("trend") in ("declining", "slightly_declining"):
                declining_students.append({
                    "student_id": student["id"],
                    "student_name": student.get("full_name"),
                    "class_id": student.get("class_id"),
                    "trend": trend_data["trend"],
                    "average_change": trend_data.get("average_change", 0),
                    "first_period_avg": trend_data.get("first_period_avg", 0),
                    "second_period_avg": trend_data.get("second_period_avg", 0),
                    "subject_trends": trend_data.get("subject_trends", {}),
                })

        declining_students.sort(key=lambda x: x.get("average_change", 0))

        return {
            "school_id": school_id,
            "total_students_checked": len(students),
            "declining_count": len(declining_students),
            "threshold": threshold,
            "declining_students": declining_students,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # 9. Schedule Adjustment Suggestions
    # ------------------------------------------------------------------

    async def suggest_schedule_adjustments(
        self, school_id: str
    ) -> Dict[str, Any]:
        """Recommend timetable changes based on performance data."""
        now = datetime.now(timezone.utc)
        week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")

        teachers = await gd_find(self.session, "teachers", {
            "school_id": school_id, "is_active": True
        }, limit=500)
        teacher_map = {t["id"]: t.get("full_name", "") for t in teachers}

        assignments = await gd_find(self.session, "teacher_assignments", {
            "school_id": school_id, "is_active": True
        }, limit=2000)

        teacher_load: Dict[str, int] = {}
        for a in assignments:
            tid = a.get("teacher_id")
            periods = a.get("weekly_periods", 0)
            teacher_load[tid] = teacher_load.get(tid, 0) + periods

        suggestions = []

        overloaded = [(tid, load) for tid, load in teacher_load.items() if load > 24]
        underloaded = [(tid, load) for tid, load in teacher_load.items() if load < 10]

        for tid, load in overloaded:
            candidates = [
                {"teacher_id": ut, "name": teacher_map.get(ut, ut), "current_load": ul}
                for ut, ul in underloaded
            ]
            suggestions.append({
                "type": "load_balance",
                "severity": "high",
                "title_ar": f"المعلم {teacher_map.get(tid, tid)} لديه نصاب مرتفع ({load} حصة/أسبوع)",
                "description_ar": f"يُنصح بتوزيع بعض الحصص على معلمين بنصاب أقل",
                "teacher_id": tid,
                "current_load": load,
                "suggested_max": 24,
                "candidate_teachers": candidates[:3],
            })

        absent_teachers = await gd_find(self.session, "teacher_attendance", {
            "school_id": school_id, "date": {"$gte": week_ago}, "status": "absent"
        }, limit=500)

        absent_counts: Dict[str, int] = {}
        for rec in absent_teachers:
            tid = rec.get("teacher_id")
            absent_counts[tid] = absent_counts.get(tid, 0) + 1

        frequent_absent = [(tid, cnt) for tid, cnt in absent_counts.items() if cnt >= 2]
        for tid, cnt in frequent_absent:
            subs = [
                {"teacher_id": ut, "name": teacher_map.get(ut, ut), "current_load": teacher_load.get(ut, 0)}
                for ut, ul in teacher_load.items() if ul < 18 and ut != tid
            ][:3]
            suggestions.append({
                "type": "substitute_needed",
                "severity": "medium",
                "title_ar": f"المعلم {teacher_map.get(tid, tid)} غاب {cnt} مرات هذا الأسبوع",
                "description_ar": "يُنصح بتجهيز معلم بديل أو إعادة توزيع الحصص",
                "teacher_id": tid,
                "absences_this_week": cnt,
                "suggested_substitutes": subs,
            })

        classes = await gd_find(self.session, "classes", {
            "school_id": school_id
        }, limit=500)

        for cls in classes:
            health_insight = await gd_find_one(self.session, "ai_insights", {
                "type": "class_health", "entity_id": cls["id"], "school_id": school_id
            })
            if health_insight:
                health_score = health_insight.get("data", {}).get("health_score", 100)
                if health_score < 50:
                    suggestions.append({
                        "type": "class_intervention",
                        "severity": "high",
                        "title_ar": f"الفصل {cls.get('name', cls['id'])} يحتاج تدخل (صحة: {health_score}%)",
                        "description_ar": "يُنصح بمراجعة التوزيع الدراسي وزيادة الحصص التفاعلية",
                        "class_id": cls["id"],
                        "health_score": health_score,
                    })

        suggestions.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.get("severity", "low"), 3))

        return {
            "school_id": school_id,
            "total_suggestions": len(suggestions),
            "suggestions": suggestions,
            "teacher_load_summary": {
                "total_teachers": len(teachers),
                "overloaded": len(overloaded),
                "underloaded": len(underloaded),
                "balanced": len(teachers) - len(overloaded) - len(underloaded),
            },
            "generated_at": now.isoformat(),
        }

    # ------------------------------------------------------------------
    # 10. Periodic Scan with Auto-Actions
    # ------------------------------------------------------------------

    async def run_periodic_scan(
        self, school_id: str, days_back: int = 30
    ) -> Dict[str, Any]:
        """Run the scheduled background analysis scan for a school."""
        now = datetime.now(timezone.utc)

        analysis = await self.run_full_analysis(school_id, days_back)

        interventions = await self.execute_auto_interventions(school_id, days_back)

        grade_alerts = await self.detect_grade_decline_alerts(school_id)

        schedule_suggestions = await self.suggest_schedule_adjustments(school_id)

        if grade_alerts["declining_count"] > 0:
            notif = {
                "id": str(uuid.uuid4()),
                "tenant_id": school_id,
                "type": "ai_grade_alert",
                "title": f"📉 تنبيه: {grade_alerts['declining_count']} طالب بدرجات متراجعة",
                "body": "يُرجى مراجعة قائمة الطلاب ذوي الدرجات المتراجعة واتخاذ الإجراءات اللازمة",
                "priority": "high",
                "target_roles": ["school_principal", "school_admin"],
                "data": {"declining_count": grade_alerts["declining_count"]},
                "is_read": False,
                "created_at": now.isoformat(),
            }
            await gd_insert(self.session, "notifications", notif)

        scan_record = {
            "id": str(uuid.uuid4()),
            "type": "periodic_scan",
            "school_id": school_id,
            "results": {
                "students_analyzed": analysis.get("students_analyzed", 0),
                "at_risk_count": analysis.get("at_risk_students_count", 0),
                "interventions_created": interventions.get("interventions_created", 0),
                "declining_grades": grade_alerts.get("declining_count", 0),
                "schedule_suggestions": schedule_suggestions.get("total_suggestions", 0),
                "insights_count": len(analysis.get("insights", [])),
            },
            "created_at": now.isoformat(),
        }
        await gd_insert(self.session, "ai_insights", scan_record)

        return {
            "school_id": school_id,
            "scan_summary": scan_record["results"],
            "analysis_insights": analysis.get("insights", []),
            "interventions": interventions,
            "grade_alerts": {
                "declining_count": grade_alerts["declining_count"],
                "top_declining": grade_alerts["declining_students"][:5],
            },
            "schedule_suggestions": {
                "count": schedule_suggestions["total_suggestions"],
                "top_suggestions": schedule_suggestions["suggestions"][:5],
            },
            "scanned_at": now.isoformat(),
        }
