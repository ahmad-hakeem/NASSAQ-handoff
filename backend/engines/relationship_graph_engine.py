"""
NASSAQ User Relationship Graph Engine
محرك العلاقات بين المستخدمين داخل منصة نَسَّق
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import uuid
from enum import Enum

from sqlalchemy import select, func

from engines.sql_utils import (
    model_to_dict, models_to_dicts,
    gd_find, gd_find_one, gd_insert, gd_update_one, gd_count, gd_delete_many,
)

logger = logging.getLogger("nassaq.relationship_graph")


class EntityType(str, Enum):
    STUDENT = "student"
    PARENT = "parent"
    TEACHER = "teacher"
    PRINCIPAL = "principal"
    SCHOOL = "school"
    CLASS = "class"
    GRADE = "grade"
    SUBJECT = "subject"
    SESSION = "session"
    ACADEMIC_YEAR = "academic_year"
    TERM = "term"


class RelationType(str, Enum):
    PARENT_OF = "parent_of"
    CHILD_OF = "child_of"
    GUARDIAN_OF = "guardian_of"
    TEACHES_CLASS = "teaches_class"
    TEACHES_SUBJECT = "teaches_subject"
    TEACHES_STUDENT = "teaches_student"
    ENROLLED_IN_SCHOOL = "enrolled_in_school"
    BELONGS_TO_GRADE = "belongs_to_grade"
    BELONGS_TO_CLASS = "belongs_to_class"
    EMPLOYED_AT = "employed_at"
    MANAGES_SCHOOL = "manages_school"
    HOMEROOM_FOR = "homeroom_for"
    LINKED_TO_SCHOOL = "linked_to_school"
    SUPERVISES_STUDENT = "supervises_student"
    ASSIGNED_TO = "assigned_to"


class RelationshipGraphEngine:
    def __init__(self, db):
        self.db = db

    @property
    def session(self):
        return self.db.session

    async def create_relationship(
        self,
        from_entity_type: str,
        from_entity_id: str,
        to_entity_type: str,
        to_entity_id: str,
        relationship_type: str,
        tenant_id: str,
        metadata: Optional[Dict] = None,
        academic_year_id: Optional[str] = None,
        term_id: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> Dict:
        existing = await gd_find_one(self.session, "user_relationships", {
            "from_entity_type": from_entity_type,
            "from_entity_id": from_entity_id,
            "to_entity_type": to_entity_type,
            "to_entity_id": to_entity_id,
            "relationship_type": relationship_type,
            "tenant_id": tenant_id,
            "status": "active"
        })
        if existing:
            return {"exists": True, "id": existing.get("id")}

        now = datetime.now(timezone.utc).isoformat()
        rel_id = str(uuid.uuid4())

        doc = {
            "id": rel_id,
            "from_entity_type": from_entity_type,
            "from_entity_id": from_entity_id,
            "to_entity_type": to_entity_type,
            "to_entity_id": to_entity_id,
            "relationship_type": relationship_type,
            "tenant_id": tenant_id,
            "academic_year_id": academic_year_id,
            "term_id": term_id,
            "metadata": metadata or {},
            "status": "active",
            "created_at": now,
            "updated_at": now,
            "created_by": created_by
        }

        await gd_insert(self.session, "user_relationships", doc)
        logger.info(f"Created relationship: {from_entity_type}({from_entity_id}) --{relationship_type}--> {to_entity_type}({to_entity_id})")
        return {"exists": False, "id": rel_id}

    async def deactivate_relationship(self, relationship_id: str, tenant_id: str, deactivated_by: Optional[str] = None) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        existing = await gd_find_one(self.session, "user_relationships", {
            "id": relationship_id, "tenant_id": tenant_id, "status": "active"
        })
        if not existing:
            return False
        await gd_update_one(self.session, "user_relationships", {"id": relationship_id}, {
            "status": "inactive",
            "updated_at": now,
            "deactivated_by": deactivated_by,
            "deactivated_at": now
        })
        return True

    async def update_relationship(self, relationship_id: str, tenant_id: str, updates: Dict) -> bool:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        existing = await gd_find_one(self.session, "user_relationships", {"id": relationship_id, "tenant_id": tenant_id})
        if not existing:
            return False
        await gd_update_one(self.session, "user_relationships", {"id": relationship_id}, updates)
        return True

    async def get_relationships(
        self,
        entity_id: str,
        tenant_id: str,
        entity_type: Optional[str] = None,
        relationship_type: Optional[str] = None,
        direction: str = "both",
        include_inactive: bool = False
    ) -> List[Dict]:
        results = []

        if direction in ("outgoing", "both"):
            filters: Dict[str, Any] = {"from_entity_id": entity_id, "tenant_id": tenant_id}
            if entity_type:
                filters["from_entity_type"] = entity_type
            if relationship_type:
                filters["relationship_type"] = relationship_type
            if not include_inactive:
                filters["status"] = "active"
            out = await gd_find(self.session, "user_relationships", filters, limit=200)
            results.extend(out)

        if direction in ("incoming", "both"):
            filters = {"to_entity_id": entity_id, "tenant_id": tenant_id}
            if entity_type:
                filters["to_entity_type"] = entity_type
            if relationship_type:
                filters["relationship_type"] = relationship_type
            if not include_inactive:
                filters["status"] = "active"
            inc = await gd_find(self.session, "user_relationships", filters, limit=200)
            results.extend(inc)

        return results

    async def get_parents_of_student(self, student_id: str, tenant_id: str) -> List[Dict]:
        from pg_models import Parent, User
        rels = await gd_find(self.session, "user_relationships", {
            "to_entity_id": student_id,
            "to_entity_type": "student",
            "tenant_id": tenant_id,
            "status": "active"
        }, limit=10)

        rels = [r for r in rels if r.get("relationship_type") in ("parent_of", "guardian_of")]

        parents = []
        for rel in rels:
            parent_id = rel.get("from_entity_id")
            stmt = select(Parent).where(Parent.id == parent_id).limit(1)
            result = await self.session.execute(stmt)
            parent = result.scalars().first()
            if not parent:
                stmt = select(User).where(User.id == parent_id, User.role == "parent").limit(1)
                result = await self.session.execute(stmt)
                parent = result.scalars().first()
            if parent:
                pd = model_to_dict(parent)
                pd["relationship_type"] = rel["relationship_type"]
                pd["relationship_id"] = rel["id"]
                pd["metadata"] = rel.get("metadata", {})
                parents.append(pd)

        return parents

    async def get_children_of_parent(self, parent_id: str, tenant_id: str) -> List[Dict]:
        from pg_models import Student
        rels = await gd_find(self.session, "user_relationships", {
            "from_entity_id": parent_id,
            "from_entity_type": "parent",
            "tenant_id": tenant_id,
            "status": "active"
        }, limit=20)

        rels = [r for r in rels if r.get("relationship_type") in ("parent_of", "guardian_of")]

        children = []
        for rel in rels:
            sid = rel.get("to_entity_id")
            stmt = select(Student).where(Student.id == sid, Student.school_id == tenant_id).limit(1)
            result = await self.session.execute(stmt)
            student = result.scalars().first()
            if student:
                sd = model_to_dict(student)
                sd["relationship_type"] = rel["relationship_type"]
                sd["relationship_id"] = rel["id"]
                children.append(sd)

        return children

    async def get_students_of_teacher(self, teacher_id: str, tenant_id: str) -> List[Dict]:
        from pg_models import Student
        class_rels = await gd_find(self.session, "user_relationships", {
            "from_entity_id": teacher_id,
            "from_entity_type": "teacher",
            "relationship_type": "teaches_class",
            "tenant_id": tenant_id,
            "status": "active"
        }, limit=30)

        class_ids = [r.get("to_entity_id") for r in class_rels]

        if not class_ids:
            assignments = await gd_find(self.session, "teacher_assignments", {
                "tenant_id": tenant_id,
                "teacher_id": teacher_id,
                "is_active": True,
            }, limit=30)
            class_ids = list({a.get("class_id") for a in assignments if a.get("class_id")})

        if not class_ids:
            return []

        stmt = select(Student).where(
            Student.school_id == tenant_id,
            Student.class_id.in_(class_ids)
        ).limit(500)
        result = await self.session.execute(stmt)
        students = result.scalars().all()
        return models_to_dicts(students)

    async def get_classes_of_teacher(self, teacher_id: str, tenant_id: str) -> List[Dict]:
        from pg_models import Class
        rels = await gd_find(self.session, "user_relationships", {
            "from_entity_id": teacher_id,
            "from_entity_type": "teacher",
            "tenant_id": tenant_id,
            "status": "active"
        }, limit=30)

        rels = [r for r in rels if r.get("relationship_type") in ("teaches_class", "homeroom_for")]

        classes = []
        seen = set()
        for rel in rels:
            cid = rel.get("to_entity_id")
            if cid in seen:
                continue
            seen.add(cid)
            stmt = select(Class).where(Class.id == cid, Class.tenant_id == tenant_id).limit(1)
            result = await self.session.execute(stmt)
            cls = result.scalars().first()
            if cls:
                cd = model_to_dict(cls)
                cd["relationship_type"] = rel["relationship_type"]
                cd["subject"] = rel.get("metadata", {}).get("subject_name") if isinstance(rel.get("metadata"), dict) else None
                classes.append(cd)

        if not classes:
            assignments = await gd_find(self.session, "teacher_assignments", {
                "tenant_id": tenant_id,
                "teacher_id": teacher_id,
                "is_active": True,
            }, limit=30)
            for a in assignments:
                cid = a.get("class_id")
                if cid and cid not in seen:
                    seen.add(cid)
                    classes.append({
                        "id": cid,
                        "name": a.get("class_name"),
                        "subject": a.get("subject_name"),
                        "relationship_type": "teaches_class"
                    })

        return classes

    async def sync_relationships_for_student(self, student_id: str, tenant_id: str, student_data: Dict, created_by: Optional[str] = None) -> None:
        if student_data.get("parent_id"):
            await self.create_relationship(
                "parent", student_data["parent_id"],
                "student", student_id,
                "parent_of", tenant_id,
                metadata={"relationship": student_data.get("parent_relationship", "parent")},
                created_by=created_by
            )

        if student_data.get("class_id"):
            await self.create_relationship(
                "student", student_id,
                "class", student_data["class_id"],
                "belongs_to_class", tenant_id,
                metadata={"class_name": student_data.get("class_name")},
                created_by=created_by
            )

        await self.create_relationship(
            "student", student_id,
            "school", tenant_id,
            "enrolled_in_school", tenant_id,
            created_by=created_by
        )

    async def sync_relationships_for_teacher(self, teacher_id: str, tenant_id: str, teacher_data: Dict, created_by: Optional[str] = None) -> None:
        await self.create_relationship(
            "teacher", teacher_id,
            "school", tenant_id,
            "employed_at", tenant_id,
            created_by=created_by
        )

        for subj_id in teacher_data.get("subject_ids", []):
            await self.create_relationship(
                "teacher", teacher_id,
                "subject", subj_id,
                "teaches_subject", tenant_id,
                metadata={"subject_id": subj_id},
                created_by=created_by
            )

    async def transfer_student_class(self, student_id: str, old_class_id: str, new_class_id: str, tenant_id: str, transferred_by: Optional[str] = None) -> None:
        from pg_models import Class
        if old_class_id:
            old_rels = await gd_find(self.session, "user_relationships", {
                "from_entity_id": student_id,
                "to_entity_id": old_class_id,
                "relationship_type": "belongs_to_class",
                "tenant_id": tenant_id,
                "status": "active"
            }, limit=5)
            for rel in old_rels:
                await self.deactivate_relationship(rel["id"], tenant_id, transferred_by)

        stmt = select(Class).where(Class.id == new_class_id, Class.tenant_id == tenant_id).limit(1)
        result = await self.session.execute(stmt)
        new_class = result.scalars().first()

        await self.create_relationship(
            "student", student_id,
            "class", new_class_id,
            "belongs_to_class", tenant_id,
            metadata={"class_name": model_to_dict(new_class).get("name") if new_class else None, "transferred_from": old_class_id},
            created_by=transferred_by
        )

    async def get_full_graph(self, entity_id: str, entity_type: str, tenant_id: str) -> Dict:
        from pg_models import Student, Teacher, Parent, User, Class

        outgoing = await gd_find(self.session, "user_relationships", {
            "from_entity_id": entity_id,
            "tenant_id": tenant_id,
            "status": "active"
        }, limit=100)

        incoming = await gd_find(self.session, "user_relationships", {
            "to_entity_id": entity_id,
            "tenant_id": tenant_id,
            "status": "active"
        }, limit=100)

        nodes = set()
        edges = []
        nodes.add((entity_type, entity_id))

        for rel in outgoing:
            nodes.add((rel["to_entity_type"], rel["to_entity_id"]))
            edges.append({
                "from": entity_id,
                "to": rel["to_entity_id"],
                "type": rel["relationship_type"],
                "metadata": rel.get("metadata", {})
            })

        for rel in incoming:
            nodes.add((rel["from_entity_type"], rel["from_entity_id"]))
            edges.append({
                "from": rel["from_entity_id"],
                "to": entity_id,
                "type": rel["relationship_type"],
                "metadata": rel.get("metadata", {})
            })

        node_details = []
        for ntype, nid in nodes:
            detail = {"type": ntype, "id": nid}
            if ntype == "student":
                stmt = select(Student).where(Student.id == nid).limit(1)
                result = await self.session.execute(stmt)
                s = result.scalars().first()
                if s:
                    detail["name"] = s.full_name
            elif ntype == "teacher":
                stmt = select(Teacher).where(Teacher.id == nid).limit(1)
                result = await self.session.execute(stmt)
                t = result.scalars().first()
                if not t:
                    stmt = select(User).where(User.id == nid).limit(1)
                    result = await self.session.execute(stmt)
                    t = result.scalars().first()
                if t:
                    detail["name"] = t.full_name
            elif ntype == "parent":
                stmt = select(Parent).where(Parent.id == nid).limit(1)
                result = await self.session.execute(stmt)
                p = result.scalars().first()
                if not p:
                    stmt = select(User).where(User.id == nid).limit(1)
                    result = await self.session.execute(stmt)
                    p = result.scalars().first()
                if p:
                    detail["name"] = p.full_name
            elif ntype == "class":
                stmt = select(Class).where(Class.id == nid).limit(1)
                result = await self.session.execute(stmt)
                c = result.scalars().first()
                if c:
                    detail["name"] = c.name
            node_details.append(detail)

        return {
            "center": {"type": entity_type, "id": entity_id},
            "nodes": node_details,
            "edges": edges,
            "total_nodes": len(node_details),
            "total_edges": len(edges)
        }

    async def get_relationship_stats(self, tenant_id: str) -> Dict:
        from pg_models import Student
        all_rels = await gd_find(self.session, "user_relationships", {
            "tenant_id": tenant_id,
            "status": "active"
        }, limit=10000)

        total = len(all_rels)
        type_counts: Dict[str, int] = {}
        for r in all_rels:
            rt = r.get("relationship_type", "unknown")
            type_counts[rt] = type_counts.get(rt, 0) + 1

        stmt = select(Student).where(Student.school_id == tenant_id, Student.is_active == True).limit(2000)
        result = await self.session.execute(stmt)
        all_students = result.scalars().all()

        unlinked_students = 0
        parent_rels_set = set()
        for r in all_rels:
            if r.get("relationship_type") in ("parent_of", "guardian_of"):
                parent_rels_set.add(r.get("to_entity_id"))

        for s in all_students:
            if s.id not in parent_rels_set:
                gl = await gd_find_one(self.session, "guardian_links", {
                    "student_id": s.id,
                    "tenant_id": tenant_id,
                    "is_active": True
                })
                if not gl and not s.parent_id:
                    unlinked_students += 1

        return {
            "total_relationships": total,
            "by_type": type_counts,
            "total_students": len(all_students),
            "unlinked_students": unlinked_students
        }
