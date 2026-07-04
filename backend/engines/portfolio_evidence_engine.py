"""
NASSAQ Portfolio Evidence Engine
Captures, deduplicates, and manages teacher portfolio evidence.
Event-driven: hooks in session/assessment/attendance/behaviour/participation/communication
routes call capture_evidence() in fire-and-forget mode.
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from engines.sql_utils import (
    gd_find, gd_find_one, gd_insert, gd_update_one,
    gd_delete_one, gd_count,
)

logger = logging.getLogger("nassaq.portfolio")

EVIDENCE_SECTIONS = {
    "teaching_plans": [
        "lesson_plan", "weekly_plan", "unit_plan",
    ],
    "applied_lessons": [
        "applied_lesson_report", "collaborative_lesson",
    ],
    "assessment_grading": [
        "exam_results", "quiz_results", "performance_task",
        "exam_results_analysis", "grade_analysis_tables",
    ],
    "attendance": [
        "attendance_record", "late_tracking",
    ],
    "behaviour_guidance": [
        "behaviour_tracking", "struggling_student_plan", "observation_notes",
    ],
    "parent_communication": [
        "parent_communication_log", "parent_meeting_minutes",
    ],
    "professional_development": [
        "training_certificate", "workshop_attendance", "peer_observation",
    ],
    "participation_activities": [
        "participation_tracking", "extracurricular_activity",
    ],
    "administrative": [
        "annual_goals", "self_evaluation", "professional_growth_plan",
    ],
}

# v2 layout — six sub-sections shown under "شواهد الأداء الوظيفي" in the new portfolio UI.
# Each entry maps a UI sub-section key to the list of evidence_type keys that belong there.
# Many types reuse existing keys (so previously-captured evidence is still visible);
# new types are added below to ALL_EVIDENCE_TYPES so they can be captured/saved manually.
EVIDENCE_SUBSECTIONS_V2 = {
    "planning": [
        "curriculum_distribution_plan", "weekly_plan", "lesson_plan",
        "preparation_record", "unit_plan", "classroom_activity_plan",
        "struggling_student_plan", "gifted_student_plan", "learning_loss_plan",
    ],
    "execution": [
        "classroom_activity_photos", "student_worksheets",
        "applied_lesson_report", "lesson_video_recording",
        "collaborative_lesson", "teaching_strategies",
    ],
    "assessment": [
        "exam_results", "quiz_results", "assessment_worksheet",
        "performance_task", "student_portfolio_files", "student_project",
        "oral_assessment", "classroom_observation",
    ],
    "results": [
        "exam_results_analysis", "class_results_analysis",
        "student_progress_report", "grade_analysis_tables",
        "before_after_comparison", "results_improvement_plan",
    ],
    "community": [
        "parent_communication_log", "parent_meeting_minutes",
        "school_activity_participation", "school_event_participation",
    ],
    "professional_development": [
        "training_attendance_report", "professional_growth_plan",
        "plc_participation", "peer_observation",
        "workshop_attendance", "workshop_delivery", "volunteer_activity_report",
    ],
}

# Newly introduced types that did not exist in the legacy 9-section layout.
# Adding them here registers them as valid evidence_type values.
_NEW_EVIDENCE_TYPES = [
    "curriculum_distribution_plan", "preparation_record",
    "classroom_activity_plan", "gifted_student_plan", "learning_loss_plan",
    "classroom_activity_photos", "student_worksheets",
    "lesson_video_recording", "teaching_strategies",
    "assessment_worksheet", "student_portfolio_files", "student_project",
    "oral_assessment", "classroom_observation",
    "class_results_analysis", "student_progress_report",
    "before_after_comparison", "results_improvement_plan",
    "school_activity_participation", "school_event_participation",
    "training_attendance_report", "plc_participation",
    "workshop_delivery", "volunteer_activity_report",
]

# Build the full set of valid evidence types (legacy + new)
_seen = set()
ALL_EVIDENCE_TYPES = []
for types in EVIDENCE_SECTIONS.values():
    for t in types:
        if t not in _seen:
            _seen.add(t)
            ALL_EVIDENCE_TYPES.append(t)
for t in _NEW_EVIDENCE_TYPES:
    if t not in _seen:
        _seen.add(t)
        ALL_EVIDENCE_TYPES.append(t)

SECTION_FOR_TYPE: Dict[str, str] = {}
for section, types in EVIDENCE_SECTIONS.items():
    for t in types:
        SECTION_FOR_TYPE.setdefault(t, section)
# Fallback section for new types that aren't in the legacy mapping
for t in _NEW_EVIDENCE_TYPES:
    SECTION_FOR_TYPE.setdefault(t, "administrative")


class PortfolioEvidenceEngine:
    def __init__(self, db):
        self.db = db

    async def capture_evidence(
        self,
        teacher_id: str,
        school_id: str,
        evidence_type: str,
        title_ar: str,
        title_en: str,
        description_ar: Optional[str] = None,
        description_en: Optional[str] = None,
        source: str = "auto",
        source_entity_type: Optional[str] = None,
        source_entity_id: Optional[str] = None,
        class_id: Optional[str] = None,
        subject_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        event_date: Optional[str] = None,
    ) -> Optional[str]:
        if evidence_type not in ALL_EVIDENCE_TYPES:
            logger.warning("Unknown evidence type: %s", evidence_type)
            return None

        today = event_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if source_entity_id:
            existing = await gd_find_one(self.db.session, "portfolio_evidence", {
                "teacher_id": teacher_id,
                "evidence_type": evidence_type,
                "source_entity_id": source_entity_id,
            })
            if existing:
                logger.debug("Dedup: %s already captured for entity %s", evidence_type, source_entity_id)
                return existing["id"]

        if evidence_type == "parent_communication_log":
            existing_today = await gd_find_one(self.db.session, "portfolio_evidence", {
                "teacher_id": teacher_id,
                "evidence_type": "parent_communication_log",
                "date": today,
            })
            if existing_today:
                count = (existing_today.get("metadata") or {}).get("message_count", 1) + 1
                meta = existing_today.get("metadata") or {}
                meta["message_count"] = count
                await gd_update_one(self.db.session, "portfolio_evidence",
                    {"id": existing_today["id"]},
                    {"metadata": meta, "updated_at": datetime.now(timezone.utc).isoformat()})
                return existing_today["id"]

        if evidence_type == "attendance_record" and class_id:
            existing_att = await gd_find_one(self.db.session, "portfolio_evidence", {
                "teacher_id": teacher_id,
                "evidence_type": "attendance_record",
                "date": today,
                "class_id": class_id,
            })
            if existing_att:
                await gd_update_one(self.db.session, "portfolio_evidence",
                    {"id": existing_att["id"]},
                    {"updated_at": datetime.now(timezone.utc).isoformat(),
                     "metadata": metadata or existing_att.get("metadata")})
                return existing_att["id"]

        evidence_id = str(uuid.uuid4())
        section = SECTION_FOR_TYPE.get(evidence_type, "administrative")
        now = datetime.now(timezone.utc).isoformat()

        doc = {
            "id": evidence_id,
            "teacher_id": teacher_id,
            "school_id": school_id,
            "evidence_type": evidence_type,
            "section": section,
            "title_ar": title_ar,
            "title_en": title_en,
            "description_ar": description_ar,
            "description_en": description_en,
            "source": source,
            "source_entity_type": source_entity_type,
            "source_entity_id": source_entity_id,
            "class_id": class_id,
            "subject_id": subject_id,
            "date": today,
            "metadata": metadata or {},
            "file_url": None,
            "file_name": None,
            "created_at": now,
            "updated_at": now,
        }

        await gd_insert(self.db.session, "portfolio_evidence", doc)
        logger.info("Evidence captured: %s / %s for teacher %s", evidence_type, evidence_id, teacher_id)
        return evidence_id

    async def sync_curriculum_plan_evidence(
        self,
        portfolio_teacher_id: str,
        plan_teacher_id: str,
        school_id: str,
        class_id: str,
        subject_id: str,
        class_name: str = "",
        subject_name: str = "",
    ) -> Optional[str]:
        """Keep the auto "curriculum_distribution_plan" portfolio card in sync
        with one teacher's curriculum plan for a single (class, subject).

        Unlike ``capture_evidence`` (which dedups and never refreshes), this is a
        true upsert so the card's lesson count always mirrors the live plan:
        - counts the teacher's lessons for (class, subject) — ``plan_teacher_id``
          is the id stored on ``curriculum_lessons`` (may be a ``teachers.id``);
        - ``portfolio_teacher_id`` is the ``users.id`` the portfolio reads by, so
          the card shows up under the teacher's own portfolio;
        - deletes the auto card when the plan becomes empty so no stale total
          lingers. A teacher's own manually-added planning cards are never
          touched (they carry no ``source_entity_id`` and ``source == "manual"``).
        Returns the evidence id, or ``None`` when the plan is empty.
        """
        source_entity_id = f"curriculum_plan:{class_id}:{subject_id or ''}"

        lesson_query: Dict[str, Any] = {
            "class_id": class_id,
            "teacher_id": plan_teacher_id,
            "subject_id": subject_id or "",
        }
        lessons = await gd_find(self.db.session, "curriculum_lessons", lesson_query, limit=500)
        total = len(lessons)
        completed = len([l for l in lessons if l.get("is_completed")])

        existing = await gd_find_one(self.db.session, "portfolio_evidence", {
            "teacher_id": portfolio_teacher_id,
            "evidence_type": "curriculum_distribution_plan",
            "source_entity_id": source_entity_id,
        })

        now = datetime.now(timezone.utc).isoformat()

        if total == 0:
            if existing and existing.get("source") == "auto":
                await gd_delete_one(self.db.session, "portfolio_evidence", {"id": existing["id"]})
            return None

        scope = " - ".join([p for p in [class_name, subject_name] if p])
        title_ar = "خطة توزيع المنهج" + (f" - {scope}" if scope else "")
        title_en = "Curriculum Distribution Plan" + (f" - {scope}" if scope else "")
        desc_ar = f"عدد الدروس: {total} • الدروس المكتملة: {completed}"
        desc_en = f"Lessons: {total} • Completed: {completed}"
        metadata = {
            "lesson_count": total,
            "completed_count": completed,
            "class_id": class_id,
            "subject_id": subject_id or "",
        }

        if existing:
            await gd_update_one(self.db.session, "portfolio_evidence", {"id": existing["id"]}, {
                "title_ar": title_ar,
                "title_en": title_en,
                "description_ar": desc_ar,
                "description_en": desc_en,
                "metadata": metadata,
                "class_id": class_id,
                "subject_id": subject_id or "",
                "updated_at": now,
            })
            return existing["id"]

        evidence_id = str(uuid.uuid4())
        doc = {
            "id": evidence_id,
            "teacher_id": portfolio_teacher_id,
            "school_id": school_id,
            "evidence_type": "curriculum_distribution_plan",
            "section": SECTION_FOR_TYPE.get("curriculum_distribution_plan", "administrative"),
            "title_ar": title_ar,
            "title_en": title_en,
            "description_ar": desc_ar,
            "description_en": desc_en,
            "source": "auto",
            "source_entity_type": "curriculum_plan",
            "source_entity_id": source_entity_id,
            "class_id": class_id,
            "subject_id": subject_id or "",
            "date": now[:10],
            "metadata": metadata,
            "file_url": None,
            "file_name": None,
            "created_at": now,
            "updated_at": now,
        }
        await gd_insert(self.db.session, "portfolio_evidence", doc)
        logger.info("Curriculum plan evidence synced: %s for teacher %s (%d lessons)",
                    evidence_id, portfolio_teacher_id, total)
        return evidence_id

    async def get_teacher_portfolio(self, teacher_id: str, school_id: Optional[str] = None) -> Dict[str, Any]:
        query: Dict[str, Any] = {"teacher_id": teacher_id}
        if school_id:
            query["school_id"] = school_id

        evidence_list = await gd_find(self.db.session, "portfolio_evidence", query,
                                       order_by="created_at", desc_order=True, limit=5000)

        # Bucket every evidence into a section using the complete type→section map.
        # SECTION_FOR_TYPE includes both legacy types and the V2 new types (which fall back
        # to "administrative"). Without this, evidence with V2-only types (e.g.
        # curriculum_distribution_plan, student_worksheets) would silently disappear from
        # the portfolio response, so the Files tab shows 0 even after saving.
        sections: Dict[str, Any] = {key: {"count": 0, "items": [], "types_covered": []} for key in EVIDENCE_SECTIONS.keys()}
        bucketed_types: Dict[str, set] = {key: set() for key in sections.keys()}
        for ev in evidence_list:
            etype = ev.get("evidence_type")
            section_key = SECTION_FOR_TYPE.get(etype, "administrative")
            if section_key not in sections:
                sections[section_key] = {"count": 0, "items": [], "types_covered": []}
                bucketed_types[section_key] = set()
            sections[section_key]["items"].append(ev)
            if etype:
                bucketed_types[section_key].add(etype)
        for key, bucket in sections.items():
            bucket["count"] = len(bucket["items"])
            bucket["types_covered"] = list(bucketed_types.get(key, set()))

        total = len(evidence_list)
        auto_count = sum(1 for e in evidence_list if e.get("source") == "auto")
        manual_count = total - auto_count
        types_covered = list({e["evidence_type"] for e in evidence_list})

        return {
            "teacher_id": teacher_id,
            "total_evidence": total,
            "auto_count": auto_count,
            "manual_count": manual_count,
            "types_covered": types_covered,
            "coverage_percent": round(len(types_covered) / len(ALL_EVIDENCE_TYPES) * 100, 1) if ALL_EVIDENCE_TYPES else 0,
            "sections": sections,
        }

    async def get_evidence_list(
        self,
        teacher_id: str,
        school_id: Optional[str] = None,
        evidence_type: Optional[str] = None,
        section: Optional[str] = None,
        source: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        query: Dict[str, Any] = {"teacher_id": teacher_id}
        if school_id:
            query["school_id"] = school_id
        if evidence_type:
            query["evidence_type"] = evidence_type
        if section:
            query["section"] = section
        if source:
            query["source"] = source
        if start_date or end_date:
            date_filter: Dict[str, str] = {}
            if start_date:
                date_filter["$gte"] = start_date
            if end_date:
                date_filter["$lte"] = end_date
            query["date"] = date_filter

        total = await gd_count(self.db.session, "portfolio_evidence", query)
        items = await gd_find(self.db.session, "portfolio_evidence", query,
                              order_by="created_at", desc_order=True, offset=skip, limit=limit)

        return {"items": items, "total": total, "skip": skip, "limit": limit}

    async def add_manual_evidence(
        self,
        teacher_id: str,
        school_id: str,
        evidence_type: str,
        title_ar: str,
        title_en: str,
        description_ar: Optional[str] = None,
        description_en: Optional[str] = None,
        date: Optional[str] = None,
        class_id: Optional[str] = None,
        subject_id: Optional[str] = None,
        file_url: Optional[str] = None,
        file_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if evidence_type not in ALL_EVIDENCE_TYPES:
            return {"success": False, "error": "invalid_evidence_type"}

        evidence_id = str(uuid.uuid4())
        section = SECTION_FOR_TYPE.get(evidence_type, "administrative")
        now = datetime.now(timezone.utc).isoformat()

        doc = {
            "id": evidence_id,
            "teacher_id": teacher_id,
            "school_id": school_id,
            "evidence_type": evidence_type,
            "section": section,
            "title_ar": title_ar,
            "title_en": title_en,
            "description_ar": description_ar,
            "description_en": description_en,
            "source": "manual",
            "source_entity_type": None,
            "source_entity_id": None,
            "class_id": class_id,
            "subject_id": subject_id,
            "date": date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "metadata": metadata or {},
            "file_url": file_url,
            "file_name": file_name,
            "created_at": now,
            "updated_at": now,
        }

        await gd_insert(self.db.session, "portfolio_evidence", doc)
        return {"success": True, "id": evidence_id, "evidence": doc}

    async def update_evidence(
        self,
        evidence_id: str,
        teacher_id: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        evidence = await gd_find_one(self.db.session, "portfolio_evidence", {
            "id": evidence_id, "teacher_id": teacher_id
        })
        if not evidence:
            return {"success": False, "error": "not_found"}

        protected = {"id", "teacher_id", "school_id", "source", "source_entity_type",
                      "source_entity_id", "created_at"}
        clean = {k: v for k, v in updates.items() if k not in protected}
        clean["updated_at"] = datetime.now(timezone.utc).isoformat()

        if "evidence_type" in clean:
            if clean["evidence_type"] not in ALL_EVIDENCE_TYPES:
                return {"success": False, "error": "invalid_evidence_type"}
            clean["section"] = SECTION_FOR_TYPE.get(clean["evidence_type"], "administrative")

        await gd_update_one(self.db.session, "portfolio_evidence",
                            {"id": evidence_id}, clean)
        updated = await gd_find_one(self.db.session, "portfolio_evidence", {"id": evidence_id})
        return {"success": True, "evidence": updated}

    async def delete_evidence(self, evidence_id: str, teacher_id: str) -> Dict[str, Any]:
        evidence = await gd_find_one(self.db.session, "portfolio_evidence", {
            "id": evidence_id, "teacher_id": teacher_id
        })
        if not evidence:
            return {"success": False, "error": "not_found"}
        await gd_delete_one(self.db.session, "portfolio_evidence", {"id": evidence_id})
        return {"success": True}

    async def get_portfolio_progress(self, teacher_id: str, school_id: Optional[str] = None) -> Dict[str, Any]:
        query: Dict[str, Any] = {"teacher_id": teacher_id}
        if school_id:
            query["school_id"] = school_id

        evidence_list = await gd_find(self.db.session, "portfolio_evidence", query, limit=5000)
        types_found = {e["evidence_type"] for e in evidence_list}

        section_progress = {}
        for section_key, type_keys in EVIDENCE_SECTIONS.items():
            covered = [t for t in type_keys if t in types_found]
            section_progress[section_key] = {
                "total_types": len(type_keys),
                "covered_types": len(covered),
                "covered": covered,
                "missing": [t for t in type_keys if t not in types_found],
                "percent": round(len(covered) / len(type_keys) * 100, 1) if type_keys else 0,
            }

        overall_covered = len(types_found & set(ALL_EVIDENCE_TYPES))
        overall_total = len(ALL_EVIDENCE_TYPES)

        return {
            "teacher_id": teacher_id,
            "overall_covered": overall_covered,
            "overall_total": overall_total,
            "overall_percent": round(overall_covered / overall_total * 100, 1) if overall_total else 0,
            "total_evidence_count": len(evidence_list),
            "section_progress": section_progress,
        }
