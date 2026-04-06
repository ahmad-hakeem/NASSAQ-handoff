"""
NASSAQ User Relationship Graph Engine
محرك العلاقات بين المستخدمين داخل منصة نَسَّق
Manages: relationship creation, querying, updating, and inference between all entities
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import uuid
from enum import Enum

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
        self.relationships = db.user_relationships

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
        """Create a new relationship link between two entities."""
        existing = await self.relationships.find_one({
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

        await self.relationships.insert_one(doc)
        logger.info(f"Created relationship: {from_entity_type}({from_entity_id}) --{relationship_type}--> {to_entity_type}({to_entity_id})")
        return {"exists": False, "id": rel_id}

    async def deactivate_relationship(self, relationship_id: str, tenant_id: str, deactivated_by: Optional[str] = None) -> bool:
        """Soft-delete a relationship by marking it inactive."""
        result = await self.relationships.update_one(
            {"id": relationship_id, "tenant_id": tenant_id, "status": "active"},
            {"$set": {
                "status": "inactive",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "deactivated_by": deactivated_by,
                "deactivated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        return result.modified_count > 0

    async def update_relationship(self, relationship_id: str, tenant_id: str, updates: Dict) -> bool:
        """Update metadata on an existing relationship."""
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        result = await self.relationships.update_one(
            {"id": relationship_id, "tenant_id": tenant_id},
            {"$set": updates}
        )
        return result.modified_count > 0

    async def get_relationships(
        self,
        entity_id: str,
        tenant_id: str,
        entity_type: Optional[str] = None,
        relationship_type: Optional[str] = None,
        direction: str = "both",
        include_inactive: bool = False
    ) -> List[Dict]:
        """Query relationships with optional entity and type filters."""
        conditions = []
        if direction in ("outgoing", "both"):
            q = {"from_entity_id": entity_id, "tenant_id": tenant_id}
            if entity_type:
                q["from_entity_type"] = entity_type
            if relationship_type:
                q["relationship_type"] = relationship_type
            if not include_inactive:
                q["status"] = "active"
            conditions.append(q)

        if direction in ("incoming", "both"):
            q = {"to_entity_id": entity_id, "tenant_id": tenant_id}
            if entity_type:
                q["to_entity_type"] = entity_type
            if relationship_type:
                q["relationship_type"] = relationship_type
            if not include_inactive:
                q["status"] = "active"
            conditions.append(q)

        if not conditions:
            return []

        results = await self.relationships.find(
            {"$or": conditions}, {"_id": 0}
        ).to_list(200)

        return results

    async def get_parents_of_student(self, student_id: str, tenant_id: str) -> List[Dict]:
        """Return all parent/guardian relationships for a student."""
        rels = await self.relationships.find({
            "to_entity_id": student_id,
            "to_entity_type": "student",
            "relationship_type": {"$in": ["parent_of", "guardian_of"]},
            "tenant_id": tenant_id,
            "status": "active"
        }, {"_id": 0}).to_list(10)

        parents = []
        for rel in rels:
            parent = await self.db.parents.find_one(
                {"id": rel["from_entity_id"]},
                {"_id": 0, "id": 1, "full_name": 1, "phone": 1, "email": 1}
            )
            if not parent:
                parent = await self.db.users.find_one(
                    {"id": rel["from_entity_id"], "role": "parent"},
                    {"_id": 0, "id": 1, "full_name": 1, "phone": 1, "email": 1}
                )
            if parent:
                parent["relationship_type"] = rel["relationship_type"]
                parent["relationship_id"] = rel["id"]
                parent["metadata"] = rel.get("metadata", {})
                parents.append(parent)

        return parents

    async def get_children_of_parent(self, parent_id: str, tenant_id: str) -> List[Dict]:
        """Return all student relationships for a parent."""
        rels = await self.relationships.find({
            "from_entity_id": parent_id,
            "from_entity_type": "parent",
            "relationship_type": {"$in": ["parent_of", "guardian_of"]},
            "tenant_id": tenant_id,
            "status": "active"
        }, {"_id": 0}).to_list(20)

        children = []
        for rel in rels:
            student = await self.db.students.find_one(
                {"id": rel["to_entity_id"], "tenant_id": tenant_id},
                {"_id": 0, "id": 1, "full_name": 1, "class_name": 1, "grade_level": 1,
                 "gender": 1, "status": 1, "education_level": 1}
            )
            if student:
                student["relationship_type"] = rel["relationship_type"]
                student["relationship_id"] = rel["id"]
                children.append(student)

        return children

    async def get_students_of_teacher(self, teacher_id: str, tenant_id: str) -> List[Dict]:
        """Return all students taught by a teacher."""
        class_rels = await self.relationships.find({
            "from_entity_id": teacher_id,
            "from_entity_type": "teacher",
            "relationship_type": "teaches_class",
            "tenant_id": tenant_id,
            "status": "active"
        }, {"_id": 0, "to_entity_id": 1, "metadata": 1}).to_list(30)

        class_ids = [r["to_entity_id"] for r in class_rels]
        if not class_ids:
            assignments = await self.db.teacher_assignments.find(
                {"tenant_id": tenant_id, "teacher_id": teacher_id, "is_active": True},
                {"_id": 0, "class_id": 1}
            ).to_list(30)
            class_ids = list({a["class_id"] for a in assignments if a.get("class_id")})

        if not class_ids:
            return []

        students = await self.db.students.find(
            {"tenant_id": tenant_id, "class_id": {"$in": class_ids}},
            {"_id": 0, "id": 1, "full_name": 1, "class_name": 1, "class_id": 1,
             "grade_level": 1, "gender": 1, "status": 1}
        ).to_list(500)

        return students

    async def get_classes_of_teacher(self, teacher_id: str, tenant_id: str) -> List[Dict]:
        """Return all classes assigned to a teacher."""
        rels = await self.relationships.find({
            "from_entity_id": teacher_id,
            "from_entity_type": "teacher",
            "relationship_type": {"$in": ["teaches_class", "homeroom_for"]},
            "tenant_id": tenant_id,
            "status": "active"
        }, {"_id": 0}).to_list(30)

        classes = []
        seen = set()
        for rel in rels:
            cid = rel["to_entity_id"]
            if cid in seen:
                continue
            seen.add(cid)
            cls = await self.db.classes.find_one(
                {"id": cid, "tenant_id": tenant_id},
                {"_id": 0, "id": 1, "name": 1, "grade_level": 1, "section": 1, "capacity": 1}
            )
            if cls:
                cls["relationship_type"] = rel["relationship_type"]
                cls["subject"] = rel.get("metadata", {}).get("subject_name")
                classes.append(cls)

        if not classes:
            assignments = await self.db.teacher_assignments.find(
                {"tenant_id": tenant_id, "teacher_id": teacher_id, "is_active": True},
                {"_id": 0, "class_id": 1, "class_name": 1, "subject_name": 1}
            ).to_list(30)
            for a in assignments:
                if a.get("class_id") and a["class_id"] not in seen:
                    seen.add(a["class_id"])
                    classes.append({
                        "id": a["class_id"],
                        "name": a.get("class_name"),
                        "subject": a.get("subject_name"),
                        "relationship_type": "teaches_class"
                    })

        return classes

    async def sync_relationships_for_student(self, student_id: str, tenant_id: str, student_data: Dict, created_by: str = None):
        """Rebuild relationship edges for a student from source records."""
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

    async def sync_relationships_for_teacher(self, teacher_id: str, tenant_id: str, teacher_data: Dict, created_by: str = None):
        """Rebuild relationship edges for a teacher from source records."""
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

    async def transfer_student_class(self, student_id: str, old_class_id: str, new_class_id: str, tenant_id: str, transferred_by: str = None):
        """Move a student to a new class and update relationships."""
        if old_class_id:
            old_rels = await self.relationships.find({
                "from_entity_id": student_id,
                "to_entity_id": old_class_id,
                "relationship_type": "belongs_to_class",
                "tenant_id": tenant_id,
                "status": "active"
            }).to_list(5)
            for rel in old_rels:
                await self.deactivate_relationship(rel["id"], tenant_id, transferred_by)

        new_class = await self.db.classes.find_one(
            {"id": new_class_id, "tenant_id": tenant_id},
            {"_id": 0, "name": 1}
        )

        await self.create_relationship(
            "student", student_id,
            "class", new_class_id,
            "belongs_to_class", tenant_id,
            metadata={"class_name": new_class.get("name") if new_class else None, "transferred_from": old_class_id},
            created_by=transferred_by
        )

    async def get_full_graph(self, entity_id: str, entity_type: str, tenant_id: str) -> Dict:
        """Build the complete relationship graph for a school."""
        outgoing = await self.relationships.find({
            "from_entity_id": entity_id,
            "tenant_id": tenant_id,
            "status": "active"
        }, {"_id": 0}).to_list(100)

        incoming = await self.relationships.find({
            "to_entity_id": entity_id,
            "tenant_id": tenant_id,
            "status": "active"
        }, {"_id": 0}).to_list(100)

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
                s = await self.db.students.find_one({"id": nid}, {"_id": 0, "full_name": 1, "class_name": 1})
                if s:
                    detail["name"] = s.get("full_name")
                    detail["class_name"] = s.get("class_name")
            elif ntype == "teacher":
                t = await self.db.teachers.find_one({"id": nid}, {"_id": 0, "full_name": 1})
                if not t:
                    t = await self.db.users.find_one({"id": nid}, {"_id": 0, "full_name": 1})
                if t:
                    detail["name"] = t.get("full_name")
            elif ntype == "parent":
                p = await self.db.parents.find_one({"id": nid}, {"_id": 0, "full_name": 1})
                if not p:
                    p = await self.db.users.find_one({"id": nid}, {"_id": 0, "full_name": 1})
                if p:
                    detail["name"] = p.get("full_name")
            elif ntype == "class":
                c = await self.db.classes.find_one({"id": nid}, {"_id": 0, "name": 1})
                if c:
                    detail["name"] = c.get("name")
            node_details.append(detail)

        return {
            "center": {"type": entity_type, "id": entity_id},
            "nodes": node_details,
            "edges": edges,
            "total_nodes": len(node_details),
            "total_edges": len(edges)
        }

    async def get_relationship_stats(self, tenant_id: str) -> Dict:
        """Return aggregate statistics on relationships within a school."""
        total = await self.relationships.count_documents({"tenant_id": tenant_id, "status": "active"})

        pipeline = [
            {"$match": {"tenant_id": tenant_id, "status": "active"}},
            {"$group": {"_id": "$relationship_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        type_counts = {}
        async for doc in self.relationships.aggregate(pipeline):
            type_counts[doc["_id"]] = doc["count"]

        unlinked_students = 0
        all_students = await self.db.students.find(
            {"tenant_id": tenant_id, "status": {"$ne": "deleted"}},
            {"_id": 0, "id": 1}
        ).to_list(2000)
        for s in all_students:
            parent_rel = await self.relationships.find_one({
                "to_entity_id": s["id"],
                "relationship_type": {"$in": ["parent_of", "guardian_of"]},
                "tenant_id": tenant_id,
                "status": "active"
            })
            if not parent_rel:
                gl = await self.db.guardian_links.find_one({
                    "student_id": s["id"],
                    "tenant_id": tenant_id,
                    "is_active": True
                })
                if not gl:
                    has_parent = await self.db.students.find_one(
                        {"id": s["id"], "parent_id": {"$exists": True, "$ne": None}},
                        {"_id": 0, "id": 1}
                    )
                    if not has_parent:
                        unlinked_students += 1

        return {
            "total_relationships": total,
            "by_type": type_counts,
            "total_students": len(all_students),
            "unlinked_students": unlinked_students
        }
