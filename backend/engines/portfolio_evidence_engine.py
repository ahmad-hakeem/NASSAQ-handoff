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

ALL_EVIDENCE_TYPES = []
for types in EVIDENCE_SECTIONS.values():
    ALL_EVIDENCE_TYPES.extend(types)

SECTION_FOR_TYPE: Dict[str, str] = {}
for section, types in EVIDENCE_SECTIONS.items():
    for t in types:
        SECTION_FOR_TYPE[t] = section


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

    async def get_teacher_portfolio(self, teacher_id: str, school_id: Optional[str] = None) -> Dict[str, Any]:
        query: Dict[str, Any] = {"teacher_id": teacher_id}
        if school_id:
            query["school_id"] = school_id

        evidence_list = await gd_find(self.db.session, "portfolio_evidence", query,
                                       order_by="created_at", desc_order=True, limit=5000)

        sections: Dict[str, Any] = {}
        for section_key, type_keys in EVIDENCE_SECTIONS.items():
            section_items = [e for e in evidence_list if e.get("evidence_type") in type_keys]
            sections[section_key] = {
                "count": len(section_items),
                "items": section_items[:20],
                "types_covered": list({e["evidence_type"] for e in section_items}),
            }

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
        if evidence.get("source") == "auto":
            return {"success": False, "error": "cannot_edit_auto_evidence"}

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
        if evidence.get("source") == "auto":
            return {"success": False, "error": "cannot_delete_auto_evidence"}
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
