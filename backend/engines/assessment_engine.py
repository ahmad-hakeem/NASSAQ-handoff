"""
NASSAQ Assessment Engine
محرك التقييم والاختبارات لمنصة نَسَّق

Handles:
- Assessment creation and management
- Grading and scoring
- Grade calculations and weighting
- Performance tracking
- Report card generation
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import uuid
import logging

logger = logging.getLogger("nassaq.assessment_engine")


class AssessmentType(str, Enum):
    QUIZ = "quiz"
    EXAM = "exam"
    MIDTERM = "midterm"
    FINAL = "final"
    ASSIGNMENT = "assignment"
    HOMEWORK = "homework"
    PROJECT = "project"
    PARTICIPATION = "participation"
    PRACTICAL = "practical"


class GradeScale(str, Enum):
    PERCENTAGE = "percentage"       # 0-100
    LETTER = "letter"               # A, B, C, D, F
    POINTS = "points"               # Custom points
    PASS_FAIL = "pass_fail"         # Pass/Fail


class AssessmentEngine:
    """
    Core Assessment Engine for NASSAQ
    Manages assessments, grading, and academic performance
    """
    
    def __init__(self, db, audit_engine=None):
        self.db = db
        self.assessments_collection = db.assessments
        self.grades_collection = db.student_grades
        self.grade_weights_collection = db.grade_weights
        self.report_cards_collection = db.report_cards
        self.audit_collection = db.audit_logs
        self._audit_engine = audit_engine
    
    # ============== ASSESSMENT MANAGEMENT ==============
    
    async def create_assessment(
        self,
        tenant_id: str,
        subject_id: str,
        section_ids: List[str],
        title: str,
        assessment_type: str,
        max_score: float,
        created_by: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a new assessment"""
        assessment_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        assessment_doc = {
            "id": assessment_id,
            "tenant_id": tenant_id,
            "subject_id": subject_id,
            "section_ids": section_ids,
            "title": title,
            "title_en": kwargs.get("title_en"),
            "description": kwargs.get("description"),
            "assessment_type": assessment_type,
            "max_score": max_score,
            "passing_score": kwargs.get("passing_score", max_score * 0.5),
            "weight": kwargs.get("weight", 1.0),
            "due_date": kwargs.get("due_date"),
            "assessment_date": kwargs.get("assessment_date"),
            "duration_minutes": kwargs.get("duration_minutes"),
            "is_published": False,
            "is_graded": False,
            "academic_year": kwargs.get("academic_year"),
            "semester": kwargs.get("semester"),
            "created_at": now,
            "created_by": created_by,
            "metadata": {
                "total_submissions": 0,
                "graded_submissions": 0,
                "average_score": 0,
                "highest_score": 0,
                "lowest_score": 0
            }
        }
        
        await self.assessments_collection.insert_one(assessment_doc)
        
        if self._audit_engine:
            try:
                from engines.audit_engine import AuditAction
                await self._audit_engine.log(
                    action=AuditAction.ASSESSMENT_CREATED.value,
                    performed_by=created_by,
                    tenant_id=tenant_id,
                    entity_type="assessment",
                    entity_id=assessment_id,
                    details={
                        "title": title,
                        "assessment_type": assessment_type,
                        "max_score": max_score,
                        "subject_id": subject_id,
                        "section_ids": section_ids,
                    },
                )
            except Exception as e:
                logger.warning(f"Audit log failed for assessment creation: {e}")
        
        return assessment_doc
    
    async def get_assessments(
        self,
        tenant_id: str,
        subject_id: Optional[str] = None,
        section_id: Optional[str] = None,
        assessment_type: Optional[str] = None,
        academic_year: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get assessments"""
        query = {"tenant_id": tenant_id}
        
        if subject_id:
            query["subject_id"] = subject_id
        if section_id:
            query["section_ids"] = section_id
        if assessment_type:
            query["assessment_type"] = assessment_type
        if academic_year:
            query["academic_year"] = academic_year
        
        assessments = await self.assessments_collection.find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).to_list(1000)
        
        return assessments
    
    async def get_assessment_by_id(self, assessment_id: str) -> Optional[Dict[str, Any]]:
        """Get assessment by ID"""
        return await self.assessments_collection.find_one(
            {"id": assessment_id},
            {"_id": 0}
        )
    
    async def update_assessment(
        self,
        assessment_id: str,
        updates: Dict[str, Any],
        updated_by: str
    ) -> Dict[str, Any]:
        """Update an assessment"""
        now = datetime.now(timezone.utc).isoformat()
        
        protected = ["id", "tenant_id", "created_at", "created_by"]
        for field in protected:
            updates.pop(field, None)
        
        updates["updated_at"] = now
        updates["updated_by"] = updated_by
        
        await self.assessments_collection.update_one(
            {"id": assessment_id},
            {"$set": updates}
        )
        
        return await self.get_assessment_by_id(assessment_id)
    
    async def publish_assessment(
        self,
        assessment_id: str,
        published_by: str
    ) -> Dict[str, Any]:
        """Publish an assessment"""
        now = datetime.now(timezone.utc).isoformat()
        
        await self.assessments_collection.update_one(
            {"id": assessment_id},
            {
                "$set": {
                    "is_published": True,
                    "published_at": now,
                    "published_by": published_by
                }
            }
        )
        
        return await self.get_assessment_by_id(assessment_id)
    
    async def delete_assessment(
        self,
        assessment_id: str,
        deleted_by: str
    ) -> bool:
        """Delete an assessment and its grades"""
        assessment = await self.get_assessment_by_id(assessment_id)
        if not assessment:
            return False
        
        # Delete all grades for this assessment
        await self.grades_collection.delete_many({"assessment_id": assessment_id})
        
        # Delete assessment
        await self.assessments_collection.delete_one({"id": assessment_id})
        
        return True
    
    # ============== GRADING ==============
    
    async def record_grade(
        self,
        assessment_id: str,
        student_id: str,
        score: float,
        graded_by: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Record a grade for a student"""
        assessment = await self.get_assessment_by_id(assessment_id)
        if not assessment:
            raise ValueError("التقييم غير موجود")
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Check if grade already exists
        existing = await self.grades_collection.find_one({
            "assessment_id": assessment_id,
            "student_id": student_id
        })
        
        # Calculate percentage
        max_score = assessment.get("max_score", 100)
        percentage = round((score / max_score * 100) if max_score > 0 else 0, 2)
        passing_score = assessment.get("passing_score", max_score * 0.5)
        is_passing = score >= passing_score
        
        if existing:
            old_score = existing.get("score")
            updates = {
                "score": score,
                "percentage": percentage,
                "is_passing": is_passing,
                "updated_at": now,
                "graded_by": graded_by,
                "feedback": kwargs.get("feedback"),
                "notes": kwargs.get("notes")
            }
            
            await self.grades_collection.update_one(
                {"id": existing["id"]},
                {"$set": updates}
            )
            
            existing.update(updates)
            existing.pop("_id", None)
            
            await self._update_assessment_metadata(assessment_id)
            
            if self._audit_engine:
                try:
                    from engines.audit_engine import AuditAction
                    await self._audit_engine.log(
                        action=AuditAction.GRADE_UPDATED.value,
                        performed_by=graded_by,
                        tenant_id=assessment.get("tenant_id"),
                        entity_type="grade",
                        entity_id=existing["id"],
                        details={
                            "assessment_id": assessment_id,
                            "student_id": student_id,
                            "old_score": old_score,
                            "new_score": score,
                            "max_score": max_score,
                            "percentage": percentage,
                        },
                    )
                except Exception as e:
                    logger.warning(f"Audit log failed for grade update: {e}")
            
            existing["_was_update"] = True
            return existing
        
        grade_id = str(uuid.uuid4())
        
        grade_doc = {
            "id": grade_id,
            "assessment_id": assessment_id,
            "tenant_id": assessment.get("tenant_id"),
            "subject_id": assessment.get("subject_id"),
            "student_id": student_id,
            "score": score,
            "max_score": max_score,
            "percentage": percentage,
            "is_passing": is_passing,
            "feedback": kwargs.get("feedback"),
            "notes": kwargs.get("notes"),
            "graded_at": now,
            "graded_by": graded_by,
            "submitted_at": kwargs.get("submitted_at"),
            "academic_year": assessment.get("academic_year"),
            "semester": assessment.get("semester")
        }
        
        await self.grades_collection.insert_one(grade_doc)
        
        await self._update_assessment_metadata(assessment_id)
        
        if self._audit_engine:
            try:
                from engines.audit_engine import AuditAction
                await self._audit_engine.log(
                    action=AuditAction.GRADE_RECORDED.value,
                    performed_by=graded_by,
                    tenant_id=assessment.get("tenant_id"),
                    entity_type="grade",
                    entity_id=grade_id,
                    details={
                        "assessment_id": assessment_id,
                        "student_id": student_id,
                        "score": score,
                        "max_score": max_score,
                        "percentage": percentage,
                    },
                )
            except Exception as e:
                logger.warning(f"Audit log failed for grade recording: {e}")
        
        return grade_doc
    
    async def record_bulk_grades(
        self,
        assessment_id: str,
        grades: List[Dict[str, Any]],
        graded_by: str,
        tenant_id: str = None,
    ) -> Dict[str, Any]:
        """Record grades for multiple students using batch operations.

        If *tenant_id* is supplied, the assessment must belong to that tenant.
        Student existence and score-range validation are enforced in-engine.
        """
        results = {
            "processed": 0,
            "created": 0,
            "updated": 0,
            "errors": [],
            "created_student_ids": [],
        }

        assessment = await self.get_assessment_by_id(assessment_id)
        if not assessment:
            results["errors"].append({"error": "التقييم غير موجود"})
            return results

        if tenant_id:
            assess_tenant = assessment.get("tenant_id") or assessment.get("school_id")
            if assess_tenant and assess_tenant != tenant_id:
                results["errors"].append({"error": "التقييم لا ينتمي لهذه المدرسة"})
                return results

        max_score = assessment.get("max_score", 100)
        passing_score = assessment.get("passing_score", max_score * 0.5)
        now = datetime.now(timezone.utc).isoformat()

        valid_entries = []
        seen_ids = set()
        for gd in grades:
            sid = gd.get("student_id")
            score = gd.get("score")
            if not sid:
                results["errors"].append({"error": "معرف الطالب مفقود"})
                continue
            if score is None:
                results["errors"].append({"student_id": sid, "error": "الدرجة مفقودة"})
                continue
            try:
                score_f = float(score)
            except (ValueError, TypeError):
                results["errors"].append({"student_id": sid, "error": "الدرجة غير صالحة"})
                continue
            if score_f < 0 or score_f > max_score:
                results["errors"].append({"student_id": sid, "error": f"الدرجة خارج النطاق (0-{max_score})"})
                continue
            if sid in seen_ids:
                continue
            seen_ids.add(sid)
            valid_entries.append(gd)

        if not valid_entries:
            return results

        student_ids = [g["student_id"] for g in valid_entries]

        students_found = await self.db.students.find(
            {"id": {"$in": student_ids}}, {"_id": 0, "id": 1}
        ).to_list(len(student_ids))
        valid_student_set = {s["id"] for s in students_found}
        verified_entries = []
        for gd in valid_entries:
            if gd["student_id"] not in valid_student_set:
                results["errors"].append({"student_id": gd["student_id"], "error": "الطالب غير موجود"})
            else:
                verified_entries.append(gd)
        valid_entries = verified_entries
        if not valid_entries:
            return results
        student_ids = [g["student_id"] for g in valid_entries]

        existing_rows = await self.grades_collection.find(
            {"assessment_id": assessment_id, "student_id": {"$in": student_ids}},
            {"_id": 0}
        ).to_list(len(student_ids))
        existing_map = {r["student_id"]: r for r in existing_rows}

        to_insert = []
        to_update = []
        for gd in valid_entries:
            try:
                sid = gd["student_id"]
                score = float(gd["score"])
                percentage = round((score / max_score * 100) if max_score > 0 else 0, 2)
                is_passing = score >= passing_score
                existing = existing_map.get(sid)

                if existing:
                    to_update.append({
                        "id": existing["id"],
                        "score": score,
                        "percentage": percentage,
                        "is_passing": is_passing,
                        "updated_at": now,
                        "recorded_by": graded_by,
                        "recorded_at": now,
                        "feedback": gd.get("feedback"),
                        "notes": gd.get("notes"),
                    })
                    results["updated"] += 1
                else:
                    doc = {
                        "id": str(uuid.uuid4()),
                        "assessment_id": assessment_id,
                        "tenant_id": assessment.get("tenant_id") or assessment.get("school_id"),
                        "subject_id": assessment.get("subject_id"),
                        "class_id": assessment.get("class_id"),
                        "student_id": sid,
                        "score": score,
                        "max_score": max_score,
                        "percentage": percentage,
                        "is_passing": is_passing,
                        "feedback": gd.get("feedback"),
                        "notes": gd.get("notes"),
                        "recorded_at": now,
                        "recorded_by": graded_by,
                        "academic_year": assessment.get("academic_year"),
                        "semester": assessment.get("semester"),
                    }
                    to_insert.append(doc)
                    results["created"] += 1
                    results["created_student_ids"].append(sid)
                results["processed"] += 1
            except Exception as e:
                results["errors"].append({"student_id": gd.get("student_id"), "error": str(e)})

        if to_update:
            await self.grades_collection.batch_update_by_ids(to_update)
        if to_insert:
            await self.grades_collection.insert_many(to_insert)

        await self._update_assessment_metadata(assessment_id)

        if self._audit_engine:
            try:
                from engines.audit_engine import AuditAction
                await self._audit_engine.log(
                    action=AuditAction.GRADES_BULK_RECORDED.value,
                    performed_by=graded_by,
                    tenant_id=assessment.get("tenant_id", ""),
                    entity_type="assessment",
                    entity_id=assessment_id,
                    details={
                        "total_submitted": len(grades),
                        "processed": results["processed"],
                        "created": results["created"],
                        "updated": results["updated"],
                        "errors_count": len(results["errors"]),
                    },
                )
            except Exception as e:
                logger.warning(f"Audit log failed for bulk grade recording: {e}")

        return results
    
    async def get_student_grades(
        self,
        tenant_id: str,
        student_id: str,
        subject_id: Optional[str] = None,
        academic_year: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get grades for a student"""
        query = {
            "tenant_id": tenant_id,
            "student_id": student_id
        }
        
        if subject_id:
            query["subject_id"] = subject_id
        if academic_year:
            query["academic_year"] = academic_year
        
        grades = await self.grades_collection.find(
            query,
            {"_id": 0}
        ).sort("graded_at", -1).to_list(1000)
        
        return grades
    
    async def get_assessment_grades(
        self,
        assessment_id: str
    ) -> List[Dict[str, Any]]:
        """Get all grades for an assessment"""
        grades = await self.grades_collection.find(
            {"assessment_id": assessment_id},
            {"_id": 0}
        ).sort("score", -1).to_list(1000)
        
        return grades
    
    # ============== GRADE WEIGHTS ==============
    
    async def set_grade_weights(
        self,
        tenant_id: str,
        subject_id: str,
        weights: Dict[str, float],
        set_by: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Set grade weights for a subject"""
        now = datetime.now(timezone.utc).isoformat()
        
        # Validate weights sum to 100
        total = sum(weights.values())
        if abs(total - 100) > 0.01:
            raise ValueError(f"مجموع الأوزان يجب أن يساوي 100 (الحالي: {total})")
        
        # Check if weights exist
        existing = await self.grade_weights_collection.find_one({
            "tenant_id": tenant_id,
            "subject_id": subject_id,
            "academic_year": kwargs.get("academic_year"),
            "semester": kwargs.get("semester")
        })
        
        if existing:
            await self.grade_weights_collection.update_one(
                {"id": existing["id"]},
                {
                    "$set": {
                        "weights": weights,
                        "updated_at": now,
                        "updated_by": set_by
                    }
                }
            )
            existing["weights"] = weights
            existing.pop("_id", None)
            return existing
        
        weight_id = str(uuid.uuid4())
        
        weight_doc = {
            "id": weight_id,
            "tenant_id": tenant_id,
            "subject_id": subject_id,
            "weights": weights,
            "academic_year": kwargs.get("academic_year"),
            "semester": kwargs.get("semester"),
            "created_at": now,
            "created_by": set_by
        }
        
        await self.grade_weights_collection.insert_one(weight_doc)
        
        return weight_doc
    
    async def get_grade_weights(
        self,
        tenant_id: str,
        subject_id: str,
        **kwargs
    ) -> Dict[str, float]:
        """Get grade weights for a subject"""
        query = {
            "tenant_id": tenant_id,
            "subject_id": subject_id
        }
        
        if kwargs.get("academic_year"):
            query["academic_year"] = kwargs["academic_year"]
        if kwargs.get("semester"):
            query["semester"] = kwargs["semester"]
        
        weights = await self.grade_weights_collection.find_one(
            query,
            {"_id": 0}
        )
        
        if weights:
            return weights.get("weights", {})
        
        # Return default weights
        return {
            "quiz": 10,
            "assignment": 10,
            "midterm": 30,
            "final": 40,
            "participation": 10
        }
    
    # ============== GRADE CALCULATIONS ==============
    
    async def calculate_student_average(
        self,
        tenant_id: str,
        student_id: str,
        subject_id: str,
        academic_year: Optional[str] = None,
        semester: Optional[int] = None
    ) -> Dict[str, Any]:
        """Calculate weighted average for a student in a subject (batch-fetched assessments)"""
        weights = await self.get_grade_weights(
            tenant_id,
            subject_id,
            academic_year=academic_year,
            semester=semester
        )

        query = {
            "tenant_id": tenant_id,
            "student_id": student_id,
            "subject_id": subject_id
        }
        if academic_year:
            query["academic_year"] = academic_year
        if semester:
            query["semester"] = semester

        grades = await self.grades_collection.find(query, {"_id": 0}).to_list(1000)

        assessment_ids = list({g.get("assessment_id") for g in grades if g.get("assessment_id")})
        assessments_list = await self.assessments_collection.find(
            {"id": {"$in": assessment_ids}}, {"_id": 0, "id": 1, "assessment_type": 1}
        ).to_list(len(assessment_ids)) if assessment_ids else []
        assessment_type_map = {a["id"]: a.get("assessment_type", "other") for a in assessments_list}

        weighted_sum = 0
        weight_total = 0
        grade_breakdown = {}

        for grade in grades:
            assessment_type = assessment_type_map.get(grade.get("assessment_id"), "other")
            weight = weights.get(assessment_type, 0)

            if weight > 0:
                percentage = grade.get("percentage", 0)
                if assessment_type not in grade_breakdown:
                    grade_breakdown[assessment_type] = {
                        "grades": [],
                        "weight": weight,
                        "average": 0
                    }
                grade_breakdown[assessment_type]["grades"].append(percentage)

        for atype, data in grade_breakdown.items():
            if data["grades"]:
                avg = sum(data["grades"]) / len(data["grades"])
                data["average"] = round(avg, 2)
                weighted_sum += avg * (data["weight"] / 100)
                weight_total += data["weight"]

        final_average = round(weighted_sum * (100 / weight_total) if weight_total > 0 else 0, 2)
        letter_grade = await self._get_letter_grade(tenant_id, final_average)

        return {
            "student_id": student_id,
            "subject_id": subject_id,
            "academic_year": academic_year,
            "semester": semester,
            "final_average": final_average,
            "letter_grade": letter_grade,
            "grade_breakdown": grade_breakdown,
            "total_assessments": len(grades)
        }
    
    async def calculate_class_statistics(
        self,
        assessment_id: str
    ) -> Dict[str, Any]:
        """Calculate statistics for an assessment"""
        grades = await self.get_assessment_grades(assessment_id)
        
        if not grades:
            return {
                "assessment_id": assessment_id,
                "total_students": 0,
                "graded_students": 0,
                "average": 0,
                "highest": 0,
                "lowest": 0,
                "median": 0,
                "passing_count": 0,
                "failing_count": 0,
                "pass_rate": 0
            }
        
        scores = [g.get("percentage", 0) for g in grades]
        scores.sort()
        
        passing = len([g for g in grades if g.get("is_passing", False)])
        failing = len(grades) - passing
        
        # Calculate median
        n = len(scores)
        median = scores[n // 2] if n % 2 != 0 else (scores[n // 2 - 1] + scores[n // 2]) / 2
        
        return {
            "assessment_id": assessment_id,
            "total_students": len(grades),
            "graded_students": len(grades),
            "average": round(sum(scores) / len(scores), 2),
            "highest": max(scores),
            "lowest": min(scores),
            "median": round(median, 2),
            "passing_count": passing,
            "failing_count": failing,
            "pass_rate": round(passing / len(grades) * 100, 2)
        }
    
    # ============== REPORT CARDS ==============
    
    async def generate_report_card(
        self,
        tenant_id: str,
        student_id: str,
        academic_year: str,
        semester: int,
        generated_by: str
    ) -> Dict[str, Any]:
        """Generate a report card for a student"""
        now = datetime.now(timezone.utc).isoformat()
        
        # Get all subjects for the student's grades
        grades = await self.grades_collection.find(
            {
                "tenant_id": tenant_id,
                "student_id": student_id,
                "academic_year": academic_year,
                "semester": semester
            },
            {"_id": 0}
        ).to_list(1000)
        
        # Get unique subjects
        subject_ids = list(set(g.get("subject_id") for g in grades if g.get("subject_id")))
        
        # Calculate average for each subject
        subjects = []
        total_average = 0
        
        for subject_id in subject_ids:
            result = await self.calculate_student_average(
                tenant_id=tenant_id,
                student_id=student_id,
                subject_id=subject_id,
                academic_year=academic_year,
                semester=semester
            )
            
            subjects.append({
                "subject_id": subject_id,
                "average": result["final_average"],
                "letter_grade": result["letter_grade"],
                "total_assessments": result["total_assessments"]
            })
            
            total_average += result["final_average"]
        
        # Overall GPA
        gpa = round(total_average / len(subjects), 2) if subjects else 0
        
        report_card_id = str(uuid.uuid4())
        
        report_card = {
            "id": report_card_id,
            "tenant_id": tenant_id,
            "student_id": student_id,
            "academic_year": academic_year,
            "semester": semester,
            "subjects": subjects,
            "gpa": gpa,
            "overall_letter_grade": await self._get_letter_grade(tenant_id, gpa),
            "generated_at": now,
            "generated_by": generated_by,
            "status": "draft"
        }
        
        await self.report_cards_collection.insert_one(report_card)
        
        return report_card
    
    async def get_report_card(
        self,
        tenant_id: str,
        student_id: str,
        academic_year: str,
        semester: int
    ) -> Optional[Dict[str, Any]]:
        """Get report card for a student"""
        return await self.report_cards_collection.find_one(
            {
                "tenant_id": tenant_id,
                "student_id": student_id,
                "academic_year": academic_year,
                "semester": semester
            },
            {"_id": 0}
        )
    
    # ============== HELPER METHODS ==============

    DEFAULT_LETTER_GRADE_SCALE = [
        (95, "A+"), (90, "A"), (85, "B+"), (80, "B"),
        (75, "C+"), (70, "C"), (65, "D+"), (60, "D"),
    ]

    def _percentage_to_letter(self, percentage: float, scale=None) -> str:
        """Convert percentage to letter grade using given or default scale"""
        used_scale = scale or self.DEFAULT_LETTER_GRADE_SCALE
        for threshold, letter in used_scale:
            if percentage >= threshold:
                return letter
        return "F"

    async def _load_tenant_grade_scale(self, tenant_id: str) -> list:
        """Load tenant-specific letter grade scale, or return default"""
        try:
            settings = await self.db.tenant_settings.find_one(
                {"tenant_id": tenant_id, "setting_key": "letter_grade_scale"},
                {"_id": 0}
            )
            if settings and settings.get("value"):
                raw = settings["value"]
                if isinstance(raw, list) and raw:
                    return [(entry.get("min", 0), entry.get("grade", "F")) for entry in raw]
        except Exception:
            pass
        return self.DEFAULT_LETTER_GRADE_SCALE

    async def _get_letter_grade(self, tenant_id: str, percentage: float) -> str:
        """Get letter grade using tenant-specific scale if configured"""
        scale = await self._load_tenant_grade_scale(tenant_id)
        return self._percentage_to_letter(percentage, scale)
    
    async def _update_assessment_metadata(self, assessment_id: str):
        """Update assessment metadata after grading"""
        grades = await self.get_assessment_grades(assessment_id)
        
        if not grades:
            return
        
        scores = [g.get("score", 0) for g in grades]
        
        metadata = {
            "total_submissions": len(grades),
            "graded_submissions": len(grades),
            "average_score": round(sum(scores) / len(scores), 2),
            "highest_score": max(scores),
            "lowest_score": min(scores)
        }
        
        await self.assessments_collection.update_one(
            {"id": assessment_id},
            {
                "$set": {
                    "metadata": metadata,
                    "is_graded": True
                }
            }
        )


    # ============== CROSS-SECTION COMPARISON ==============

    async def compare_sections(
        self,
        tenant_id: str,
        assessment_id: Optional[str] = None,
        subject_id: Optional[str] = None,
        academic_year: Optional[str] = None,
        semester: Optional[int] = None
    ) -> Dict[str, Any]:
        if assessment_id:
            assessment = await self.get_assessment_by_id(assessment_id)
            if not assessment:
                return {"error": "التقييم غير موجود", "sections": []}
            section_ids = assessment.get("section_ids", [])
            grades = await self.grades_collection.find(
                {"assessment_id": assessment_id},
                {"_id": 0}
            ).to_list(5000)
        else:
            query = {"tenant_id": tenant_id}
            if subject_id:
                query["subject_id"] = subject_id
            if academic_year:
                query["academic_year"] = academic_year
            if semester:
                query["semester"] = semester
            grades = await self.grades_collection.find(query, {"_id": 0}).to_list(10000)
            section_ids = []

        students_coll = self.db
        student_ids = list(set(g.get("student_id") for g in grades))
        students = await students_coll.students.find(
            {"id": {"$in": student_ids}},
            {"_id": 0, "id": 1, "class_id": 1, "full_name": 1}
        ).to_list(10000)
        student_class_map = {s["id"]: s.get("class_id", "unknown") for s in students}

        section_data: Dict[str, List[float]] = {}
        for g in grades:
            sid = g.get("student_id")
            class_id = student_class_map.get(sid, "unknown")
            if class_id not in section_data:
                section_data[class_id] = []
            section_data[class_id].append(g.get("percentage", 0))

        sections_result = []
        for class_id, scores in section_data.items():
            scores.sort()
            n = len(scores)
            median = scores[n // 2] if n % 2 != 0 else (scores[n // 2 - 1] + scores[n // 2]) / 2 if n > 0 else 0
            passing = len([s for s in scores if s >= 50])

            cls = await students_coll.classes.find_one({"id": class_id}, {"_id": 0, "name": 1})

            sections_result.append({
                "class_id": class_id,
                "class_name": cls.get("name") if cls else class_id,
                "student_count": n,
                "average": round(sum(scores) / n, 2) if n else 0,
                "highest": max(scores) if scores else 0,
                "lowest": min(scores) if scores else 0,
                "median": round(median, 2),
                "pass_rate": round(passing / n * 100, 2) if n else 0,
                "passing_count": passing,
                "failing_count": n - passing,
            })

        sections_result.sort(key=lambda x: x["average"], reverse=True)

        for i, s in enumerate(sections_result):
            s["rank"] = i + 1

        overall_scores = [s for scores_list in section_data.values() for s in scores_list]
        overall_avg = round(sum(overall_scores) / len(overall_scores), 2) if overall_scores else 0

        return {
            "tenant_id": tenant_id,
            "assessment_id": assessment_id,
            "subject_id": subject_id,
            "sections_count": len(sections_result),
            "overall_average": overall_avg,
            "total_students": len(overall_scores),
            "sections": sections_result,
        }

    # ============== STUDENT RANKING ==============

    async def get_student_ranking(
        self,
        tenant_id: str,
        class_id: str,
        subject_id: Optional[str] = None,
        academic_year: Optional[str] = None,
        semester: Optional[int] = None,
    ) -> Dict[str, Any]:
        students = await self.db.students.find(
            {"school_id": tenant_id, "class_id": class_id, "is_active": True},
            {"_id": 0, "id": 1, "full_name": 1}
        ).to_list(500)
        student_ids = [s["id"] for s in students]
        name_map = {s["id"]: s.get("full_name", "") for s in students}

        query: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "student_id": {"$in": student_ids},
        }
        if subject_id:
            query["subject_id"] = subject_id
        if academic_year:
            query["academic_year"] = academic_year
        if semester:
            query["semester"] = semester

        grades = await self.grades_collection.find(query, {"_id": 0}).to_list(10000)

        student_avgs: Dict[str, Dict] = {}
        for g in grades:
            sid = g.get("student_id")
            if sid not in student_avgs:
                student_avgs[sid] = {"total": 0, "count": 0}
            student_avgs[sid]["total"] += g.get("percentage", 0)
            student_avgs[sid]["count"] += 1

        scale = await self._load_tenant_grade_scale(tenant_id)
        rankings = []
        for sid, data in student_avgs.items():
            avg = round(data["total"] / data["count"], 2) if data["count"] else 0
            rankings.append({
                "student_id": sid,
                "student_name": name_map.get(sid, ""),
                "average": avg,
                "letter_grade": self._percentage_to_letter(avg, scale),
                "assessments_count": data["count"],
            })

        rankings.sort(key=lambda x: x["average"], reverse=True)
        for i, r in enumerate(rankings):
            r["rank"] = i + 1
            if i == 0:
                r["badge"] = "🥇"
            elif i == 1:
                r["badge"] = "🥈"
            elif i == 2:
                r["badge"] = "🥉"
            else:
                r["badge"] = ""

        no_grades = [
            {"student_id": sid, "student_name": name_map.get(sid, ""), "average": 0, "rank": None}
            for sid in student_ids if sid not in student_avgs
        ]

        return {
            "class_id": class_id,
            "subject_id": subject_id,
            "total_students": len(students),
            "ranked_students": len(rankings),
            "ungraded_students": len(no_grades),
            "class_average": round(sum(r["average"] for r in rankings) / len(rankings), 2) if rankings else 0,
            "rankings": rankings,
            "ungraded": no_grades,
        }

    # ============== PERFORMANCE TREND ==============

    async def get_performance_trend(
        self,
        tenant_id: str,
        student_id: str,
        subject_id: Optional[str] = None,
        periods: int = 6,
    ) -> Dict[str, Any]:
        query: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "student_id": student_id,
        }
        if subject_id:
            query["subject_id"] = subject_id

        grades = await self.grades_collection.find(
            query, {"_id": 0, "percentage": 1, "graded_at": 1, "subject_id": 1}
        ).sort("graded_at", 1).to_list(1000)

        if len(grades) < 2:
            return {
                "student_id": student_id,
                "trend": "insufficient_data",
                "data_points": len(grades),
                "periods": [],
            }

        chunk_size = max(1, len(grades) // periods)
        period_data = []
        for i in range(0, len(grades), chunk_size):
            chunk = grades[i:i + chunk_size]
            avg = round(sum(g.get("percentage", 0) for g in chunk) / len(chunk), 2)
            period_data.append({
                "period": len(period_data) + 1,
                "average": avg,
                "count": len(chunk),
                "from_date": chunk[0].get("graded_at", ""),
                "to_date": chunk[-1].get("graded_at", ""),
            })

        if len(period_data) >= 2:
            first_avg = period_data[0]["average"]
            last_avg = period_data[-1]["average"]
            change = last_avg - first_avg

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
        else:
            trend = "stable"
            change = 0

        subject_breakdown = {}
        by_subject: Dict[str, List] = {}
        for g in grades:
            sid = g.get("subject_id", "unknown")
            if sid not in by_subject:
                by_subject[sid] = []
            by_subject[sid].append(g.get("percentage", 0))

        for sid, sg in by_subject.items():
            if len(sg) >= 2:
                mid = len(sg) // 2
                early = round(sum(sg[:mid]) / len(sg[:mid]), 2)
                late = round(sum(sg[mid:]) / len(sg[mid:]), 2)
                sub_change = late - early
                if sub_change <= -10:
                    sub_trend = "declining"
                elif sub_change >= 10:
                    sub_trend = "improving"
                else:
                    sub_trend = "stable"
                subject_breakdown[sid] = {
                    "early_avg": early,
                    "recent_avg": late,
                    "change": round(sub_change, 2),
                    "trend": sub_trend,
                }

        return {
            "student_id": student_id,
            "subject_id": subject_id,
            "trend": trend,
            "total_change": round(change, 2),
            "data_points": len(grades),
            "periods": period_data,
            "subject_breakdown": subject_breakdown,
        }

    # ============== GRADE DECLINE ALERTS ==============

    async def get_grade_decline_alerts(
        self,
        tenant_id: str,
        class_id: Optional[str] = None,
        threshold: float = -10.0,
    ) -> Dict[str, Any]:
        query: Dict[str, Any] = {"school_id": tenant_id, "is_active": True}
        if class_id:
            query["class_id"] = class_id

        students = await self.db.students.find(
            query, {"_id": 0, "id": 1, "full_name": 1, "class_id": 1}
        ).to_list(10000)

        alerts = []
        for student in students:
            trend = await self.get_performance_trend(tenant_id, student["id"])
            if trend.get("trend") in ("declining", "slightly_declining"):
                declining_subjects = [
                    sid for sid, data in trend.get("subject_breakdown", {}).items()
                    if data.get("trend") == "declining"
                ]
                alerts.append({
                    "student_id": student["id"],
                    "student_name": student.get("full_name", ""),
                    "class_id": student.get("class_id", ""),
                    "trend": trend["trend"],
                    "total_change": trend.get("total_change", 0),
                    "declining_subjects_count": len(declining_subjects),
                    "declining_subjects": declining_subjects,
                    "data_points": trend.get("data_points", 0),
                })

        alerts.sort(key=lambda x: x.get("total_change", 0))

        return {
            "tenant_id": tenant_id,
            "class_id": class_id,
            "total_students_checked": len(students),
            "alerts_count": len(alerts),
            "threshold": threshold,
            "alerts": alerts,
        }

    # ============== SUBJECT STATISTICS ==============

    async def get_subject_statistics(
        self,
        tenant_id: str,
        subject_id: str,
        academic_year: Optional[str] = None,
        semester: Optional[int] = None,
    ) -> Dict[str, Any]:
        query: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "subject_id": subject_id,
        }
        if academic_year:
            query["academic_year"] = academic_year
        if semester:
            query["semester"] = semester

        grades = await self.grades_collection.find(query, {"_id": 0}).to_list(10000)

        if not grades:
            return {
                "subject_id": subject_id,
                "total_grades": 0,
                "message": "لا توجد درجات مسجلة لهذه المادة",
            }

        percentages = [g.get("percentage", 0) for g in grades]
        percentages.sort()
        n = len(percentages)
        median = percentages[n // 2] if n % 2 != 0 else (percentages[n // 2 - 1] + percentages[n // 2]) / 2

        passing = len([p for p in percentages if p >= 50])

        scale = await self._load_tenant_grade_scale(tenant_id)
        grade_dist = {"A+": 0, "A": 0, "B+": 0, "B": 0, "C+": 0, "C": 0, "D+": 0, "D": 0, "F": 0}
        for p in percentages:
            letter = self._percentage_to_letter(p, scale)
            if letter in grade_dist:
                grade_dist[letter] += 1

        student_ids = list(set(g.get("student_id") for g in grades))
        students = await self.db.students.find(
            {"id": {"$in": student_ids}},
            {"_id": 0, "id": 1, "class_id": 1}
        ).to_list(10000)
        class_ids = list(set(s.get("class_id", "") for s in students))
        student_class = {s["id"]: s.get("class_id", "") for s in students}

        section_averages = {}
        for g in grades:
            cid = student_class.get(g.get("student_id"), "unknown")
            if cid not in section_averages:
                section_averages[cid] = []
            section_averages[cid].append(g.get("percentage", 0))

        sections_comparison = []
        for cid, scores in section_averages.items():
            cls = await self.db.classes.find_one({"id": cid}, {"_id": 0, "name": 1})
            sections_comparison.append({
                "class_id": cid,
                "class_name": cls.get("name") if cls else cid,
                "average": round(sum(scores) / len(scores), 2),
                "student_count": len(scores),
            })
        sections_comparison.sort(key=lambda x: x["average"], reverse=True)

        return {
            "subject_id": subject_id,
            "academic_year": academic_year,
            "semester": semester,
            "total_grades": n,
            "unique_students": len(student_ids),
            "sections_count": len(class_ids),
            "statistics": {
                "average": round(sum(percentages) / n, 2),
                "highest": max(percentages),
                "lowest": min(percentages),
                "median": round(median, 2),
                "pass_rate": round(passing / n * 100, 2),
                "passing_count": passing,
                "failing_count": n - passing,
            },
            "grade_distribution": grade_dist,
            "sections_comparison": sections_comparison,
        }


# Export
__all__ = ["AssessmentEngine", "AssessmentType", "GradeScale"]
