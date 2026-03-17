"""
NASSAQ Route Module: User Relationship Graph + Guardian Linking Engine
Manages relationships between users (parent-student, teacher-class, etc.)
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
from enum import Enum
import uuid

from dependencies import (
    db, get_current_user, require_roles, UserRole, logger
)

router = APIRouter()


class RelationshipTypeEnum(str, Enum):
    PARENT_STUDENT = "parent_student"
    TEACHER_CLASS = "teacher_class"
    TEACHER_SUBJECT = "teacher_subject"
    PRINCIPAL_SCHOOL = "principal_school"
    GUARDIAN_STUDENT = "guardian_student"


class GuardianRelationEnum(str, Enum):
    FATHER = "father"
    MOTHER = "mother"
    GUARDIAN = "guardian"
    GRANDFATHER = "grandfather"
    GRANDMOTHER = "grandmother"
    UNCLE = "uncle"
    AUNT = "aunt"
    SIBLING = "sibling"
    OTHER = "other"


class GuardianLinkRequest(BaseModel):
    student_id: str
    parent_id: Optional[str] = None
    parent_user_id: Optional[str] = None
    relationship: GuardianRelationEnum = GuardianRelationEnum.GUARDIAN
    is_primary: bool = False
    can_pickup: bool = True
    can_view_grades: bool = True
    can_view_attendance: bool = True
    can_communicate: bool = True
    notes: Optional[str] = None


class GuardianUpdateRequest(BaseModel):
    relationship: Optional[str] = None
    is_primary: Optional[bool] = None
    can_pickup: Optional[bool] = None
    can_view_grades: Optional[bool] = None
    can_view_attendance: Optional[bool] = None
    can_communicate: Optional[bool] = None
    notes: Optional[str] = None


@router.post("/guardian/link")
async def link_guardian_to_student(
    data: GuardianLinkRequest,
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL,
        UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN
    ]))
):
    """Link a guardian/parent to a student"""
    school_id = current_user.get("tenant_id")
    if not school_id:
        raise HTTPException(status_code=400, detail="معرف المدرسة مطلوب")

    student = await db.students.find_one(
        {"id": data.student_id, "tenant_id": school_id}, {"_id": 0, "full_name": 1}
    )
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")

    parent = None
    if data.parent_id:
        parent = await db.parents.find_one({"id": data.parent_id}, {"_id": 0, "full_name": 1, "id": 1})
    elif data.parent_user_id:
        parent = await db.users.find_one({"id": data.parent_user_id}, {"_id": 0, "full_name": 1, "id": 1})

    if not parent:
        raise HTTPException(status_code=404, detail="ولي الأمر غير موجود")

    parent_ref = data.parent_id or data.parent_user_id
    existing = await db.guardian_links.find_one({
        "tenant_id": school_id,
        "student_id": data.student_id,
        "parent_ref": parent_ref,
        "is_active": True
    })
    if existing:
        raise HTTPException(status_code=400, detail="الربط موجود بالفعل")

    link_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    if data.is_primary:
        await db.guardian_links.update_many(
            {"tenant_id": school_id, "student_id": data.student_id, "is_primary": True},
            {"$set": {"is_primary": False}}
        )

    link_doc = {
        "id": link_id,
        "tenant_id": school_id,
        "student_id": data.student_id,
        "student_name": student.get("full_name"),
        "parent_id": data.parent_id,
        "parent_user_id": data.parent_user_id,
        "parent_ref": parent_ref,
        "parent_name": parent.get("full_name"),
        "relationship": data.relationship.value,
        "is_primary": data.is_primary,
        "is_active": True,
        "permissions": {
            "can_pickup": data.can_pickup,
            "can_view_grades": data.can_view_grades,
            "can_view_attendance": data.can_view_attendance,
            "can_communicate": data.can_communicate
        },
        "notes": data.notes,
        "linked_by": current_user["id"],
        "linked_at": now,
        "updated_at": now
    }

    await db.guardian_links.insert_one(link_doc)

    await db.students.update_one(
        {"id": data.student_id},
        {"$addToSet": {"guardian_ids": parent_ref}}
    )
    if data.parent_id:
        await db.parents.update_one(
            {"id": data.parent_id},
            {"$addToSet": {"student_ids": data.student_id}}
        )

    link_doc.pop("_id", None)
    return link_doc


@router.delete("/guardian/unlink/{link_id}")
async def unlink_guardian(
    link_id: str,
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL,
        UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN
    ]))
):
    """Unlink a guardian from a student (soft delete)"""
    school_id = current_user.get("tenant_id")
    link = await db.guardian_links.find_one({"id": link_id, "tenant_id": school_id})
    if not link:
        raise HTTPException(status_code=404, detail="الربط غير موجود")

    await db.guardian_links.update_one(
        {"id": link_id},
        {"$set": {
            "is_active": False,
            "unlinked_by": current_user["id"],
            "unlinked_at": datetime.now(timezone.utc).isoformat()
        }}
    )

    return {"message": "تم فك الربط بنجاح", "id": link_id}


@router.put("/guardian/link/{link_id}")
async def update_guardian_link(
    link_id: str,
    data: GuardianUpdateRequest,
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL,
        UserRole.SCHOOL_ADMIN, UserRole.SCHOOL_SUB_ADMIN
    ]))
):
    """Update guardian link permissions and details"""
    school_id = current_user.get("tenant_id")
    link = await db.guardian_links.find_one({"id": link_id, "tenant_id": school_id})
    if not link:
        raise HTTPException(status_code=404, detail="الربط غير موجود")

    updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if data.relationship is not None:
        updates["relationship"] = data.relationship
    if data.is_primary is not None:
        if data.is_primary:
            await db.guardian_links.update_many(
                {"tenant_id": school_id, "student_id": link["student_id"], "is_primary": True},
                {"$set": {"is_primary": False}}
            )
        updates["is_primary"] = data.is_primary
    if data.notes is not None:
        updates["notes"] = data.notes

    perm_updates = {}
    if data.can_pickup is not None:
        perm_updates["permissions.can_pickup"] = data.can_pickup
    if data.can_view_grades is not None:
        perm_updates["permissions.can_view_grades"] = data.can_view_grades
    if data.can_view_attendance is not None:
        perm_updates["permissions.can_view_attendance"] = data.can_view_attendance
    if data.can_communicate is not None:
        perm_updates["permissions.can_communicate"] = data.can_communicate

    await db.guardian_links.update_one(
        {"id": link_id},
        {"$set": {**updates, **perm_updates}}
    )

    return {"message": "تم تحديث الربط بنجاح", "id": link_id}


@router.get("/guardian/student/{student_id}")
async def get_student_guardians(
    student_id: str,
    include_inactive: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """Get all guardians linked to a student"""
    school_id = current_user.get("tenant_id")
    query = {"tenant_id": school_id, "student_id": student_id}
    if not include_inactive:
        query["is_active"] = True

    links = await db.guardian_links.find(query, {"_id": 0}).sort("is_primary", -1).to_list(20)
    return {"guardians": links, "total": len(links)}


@router.get("/guardian/parent/{parent_ref}")
async def get_parent_children(
    parent_ref: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all children linked to a parent/guardian"""
    school_id = current_user.get("tenant_id")
    links = await db.guardian_links.find(
        {"tenant_id": school_id, "parent_ref": parent_ref, "is_active": True},
        {"_id": 0}
    ).to_list(20)

    children = []
    for link in links:
        student = await db.students.find_one(
            {"id": link["student_id"], "tenant_id": school_id},
            {"_id": 0, "id": 1, "full_name": 1, "class_name": 1, "grade_level": 1, "gender": 1}
        )
        if student:
            children.append({
                **student,
                "relationship": link.get("relationship"),
                "is_primary": link.get("is_primary"),
                "link_id": link.get("id"),
                "permissions": link.get("permissions", {})
            })

    return {"children": children, "total": len(children), "parent_ref": parent_ref}


@router.post("/guardian/transfer-custody")
async def transfer_custody(
    data: dict = Body(...),
    current_user: dict = Depends(require_roles([
        UserRole.PLATFORM_ADMIN, UserRole.SCHOOL_PRINCIPAL
    ]))
):
    """Transfer primary custody of a student from one guardian to another"""
    school_id = current_user.get("tenant_id")
    student_id = data.get("student_id")
    from_parent = data.get("from_parent_ref")
    to_parent = data.get("to_parent_ref")
    reason = data.get("reason", "")

    if not all([student_id, from_parent, to_parent]):
        raise HTTPException(status_code=400, detail="جميع الحقول مطلوبة")

    from_link = await db.guardian_links.find_one({
        "tenant_id": school_id, "student_id": student_id,
        "parent_ref": from_parent, "is_active": True
    })
    to_link = await db.guardian_links.find_one({
        "tenant_id": school_id, "student_id": student_id,
        "parent_ref": to_parent, "is_active": True
    })

    if not from_link:
        raise HTTPException(status_code=404, detail="الولي المصدر غير مرتبط بالطالب")
    if not to_link:
        raise HTTPException(status_code=404, detail="الولي المستلم غير مرتبط بالطالب")

    now = datetime.now(timezone.utc).isoformat()

    await db.guardian_links.update_one(
        {"id": from_link["id"]},
        {"$set": {"is_primary": False, "updated_at": now}}
    )
    await db.guardian_links.update_one(
        {"id": to_link["id"]},
        {"$set": {"is_primary": True, "updated_at": now}}
    )

    await db.custody_transfers.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": school_id,
        "student_id": student_id,
        "from_parent_ref": from_parent,
        "to_parent_ref": to_parent,
        "reason": reason,
        "transferred_by": current_user["id"],
        "transferred_at": now
    })

    return {"message": "تم نقل الحضانة بنجاح"}


@router.get("/relationships/graph/{entity_id}")
async def get_relationship_graph(
    entity_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get relationship graph for any entity (student, teacher, parent)"""
    school_id = current_user.get("tenant_id")

    student = await db.students.find_one(
        {"id": entity_id, "school_id": school_id},
        {"_id": 0, "id": 1, "full_name": 1, "class_id": 1, "class_name": 1, "school_id": 1, "grade_level": 1}
    )

    if student:
        guardians = await db.guardian_links.find(
            {"tenant_id": school_id, "student_id": entity_id, "is_active": True},
            {"_id": 0}
        ).to_list(10)

        teacher_assignments_raw = await db.teacher_assignments.find(
            {"school_id": school_id, "class_id": student.get("class_id"), "is_active": True},
            {"_id": 0, "teacher_id": 1, "teacher_name": 1, "subject_name": 1, "subject_id": 1}
        ).to_list(20)

        ta_teacher_ids = list({a.get("teacher_id") for a in teacher_assignments_raw if a.get("teacher_id")})
        ta_subject_ids = list({a.get("subject_id") for a in teacher_assignments_raw if a.get("subject_id")})
        ta_teachers = {}
        if ta_teacher_ids:
            tch_docs = await db.teachers.find({"id": {"$in": ta_teacher_ids}}, {"_id": 0, "id": 1, "full_name": 1}).to_list(50)
            ta_teachers = {t["id"]: t.get("full_name", "") for t in tch_docs}
        ta_subjects = {}
        if ta_subject_ids:
            sub_docs = await db.subjects.find({"id": {"$in": ta_subject_ids}}, {"_id": 0, "id": 1, "name_ar": 1}).to_list(50)
            ta_subjects = {s["id"]: s.get("name_ar", "") for s in sub_docs}

        classmates = await db.students.find(
            {"school_id": school_id, "class_id": student.get("class_id"), "id": {"$ne": entity_id}},
            {"_id": 0, "id": 1, "full_name": 1}
        ).limit(50).to_list(50)

        siblings_rels = await db.user_relationships.find(
            {"$or": [
                {"from_entity_id": entity_id, "relationship_type": "sibling", "status": "active"},
                {"to_entity_id": entity_id, "relationship_type": "sibling", "status": "active"},
                {"user_id_1": entity_id, "relationship_type": "sibling", "is_active": True},
                {"user_id_2": entity_id, "relationship_type": "sibling", "is_active": True},
            ]},
            {"_id": 0, "user_id_1": 1, "user_id_2": 1, "from_entity_id": 1, "to_entity_id": 1}
        ).to_list(20)
        sibling_ids = set()
        for r in siblings_rels:
            fid = r.get("from_entity_id") or r.get("user_id_1")
            tid = r.get("to_entity_id") or r.get("user_id_2")
            if fid and fid != entity_id:
                sibling_ids.add(fid)
            if tid and tid != entity_id:
                sibling_ids.add(tid)
        sibling_ids = list(sibling_ids)
        siblings = []
        if sibling_ids:
            siblings = await db.students.find(
                {"id": {"$in": sibling_ids}},
                {"_id": 0, "id": 1, "full_name": 1, "class_name": 1, "grade_level": 1}
            ).to_list(20)

        return {
            "entity_type": "student",
            "entity": student,
            "guardians": [{"id": g.get("parent_ref"), "name": g.get("parent_name"), "relationship": g.get("relationship"), "is_primary": g.get("is_primary")} for g in guardians],
            "teachers": [
                {
                    "id": t.get("teacher_id"),
                    "name": t.get("teacher_name") or ta_teachers.get(t.get("teacher_id"), ""),
                    "subject": t.get("subject_name") or ta_subjects.get(t.get("subject_id"), "")
                }
                for t in teacher_assignments_raw
            ],
            "siblings": siblings,
            "classmates_count": len(classmates),
            "class_name": student.get("class_name")
        }

    teacher = await db.users.find_one(
        {"id": entity_id, "tenant_id": school_id, "role": "teacher"},
        {"_id": 0, "id": 1, "full_name": 1, "email": 1, "teacher_id": 1}
    )

    if teacher:
        teacher_record_id = teacher.get("teacher_id") or entity_id
        teacher_rec = await db.teachers.find_one(
            {"$or": [{"id": entity_id}, {"user_id": entity_id}, {"id": teacher_record_id}], "school_id": school_id},
            {"_id": 0, "id": 1}
        )
        lookup_id = teacher_rec["id"] if teacher_rec else teacher_record_id

        assignments = await db.teacher_assignments.find(
            {"school_id": school_id, "teacher_id": lookup_id, "is_active": True},
            {"_id": 0, "class_id": 1, "class_name": 1, "subject_name": 1, "subject_id": 1}
        ).to_list(30)

        sub_ids = list({a.get("subject_id") for a in assignments if a.get("subject_id")})
        sub_names = {}
        if sub_ids:
            subs = await db.subjects.find({"id": {"$in": sub_ids}}, {"_id": 0, "id": 1, "name_ar": 1}).to_list(50)
            sub_names = {s["id"]: s.get("name_ar", "") for s in subs}

        cls_ids = list({a.get("class_id") for a in assignments if a.get("class_id")})
        cls_names = {}
        if cls_ids:
            classes_docs = await db.classes.find({"id": {"$in": cls_ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(50)
            cls_names = {c["id"]: c.get("name", "") for c in classes_docs}

        classes = list({a["class_id"] for a in assignments if a.get("class_id")})
        student_count = 0
        for cid in classes:
            student_count += await db.students.count_documents({"school_id": school_id, "class_id": cid})

        return {
            "entity_type": "teacher",
            "entity": teacher,
            "classes": [
                {
                    "class_id": a.get("class_id"),
                    "class_name": a.get("class_name") or cls_names.get(a.get("class_id"), ""),
                    "subject": a.get("subject_name") or sub_names.get(a.get("subject_id"), "")
                }
                for a in assignments
            ],
            "total_students": student_count,
            "total_classes": len(classes)
        }

    parent_query = {"id": entity_id, "role": "parent"}
    if school_id:
        parent_query["tenant_id"] = school_id
    parent = await db.users.find_one(
        parent_query,
        {"_id": 0, "id": 1, "full_name": 1, "email": 1, "phone": 1}
    )
    if parent:
        link_query = {"parent_ref": entity_id, "is_active": True}
        if school_id:
            link_query["tenant_id"] = school_id
        children_links = await db.guardian_links.find(
            link_query,
            {"_id": 0}
        ).to_list(20)

        children = []
        for link in children_links:
            child_query = {"id": link["student_id"]}
            if school_id:
                child_query["school_id"] = school_id
            child = await db.students.find_one(
                child_query,
                {"_id": 0, "id": 1, "full_name": 1, "class_name": 1, "grade_level": 1}
            )
            if child:
                children.append({**child, "relationship": link.get("relationship")})

        return {
            "entity_type": "parent",
            "entity": parent,
            "children": children,
            "total_children": len(children)
        }

    raise HTTPException(status_code=404, detail="الكيان غير موجود")


@router.get("/relationships/siblings/{student_id}")
async def get_siblings(
    student_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get siblings of a student (shared parents)"""
    school_id = current_user.get("tenant_id")

    links = await db.guardian_links.find(
        {"tenant_id": school_id, "student_id": student_id, "is_active": True},
        {"_id": 0, "parent_ref": 1}
    ).to_list(10)

    parent_refs = [l["parent_ref"] for l in links]
    if not parent_refs:
        parent = await db.students.find_one({"id": student_id}, {"_id": 0, "parent_id": 1, "parent_user_id": 1})
        if parent:
            if parent.get("parent_id"):
                parent_refs.append(parent["parent_id"])
            if parent.get("parent_user_id"):
                parent_refs.append(parent["parent_user_id"])

    if not parent_refs:
        return {"siblings": [], "total": 0}

    sibling_ids = set()
    for pref in parent_refs:
        sibling_links = await db.guardian_links.find(
            {"tenant_id": school_id, "parent_ref": pref, "is_active": True},
            {"_id": 0, "student_id": 1}
        ).to_list(20)
        for sl in sibling_links:
            if sl["student_id"] != student_id:
                sibling_ids.add(sl["student_id"])

    also_siblings = await db.students.find(
        {"school_id": school_id,
         "$or": [{"parent_id": {"$in": parent_refs}}, {"parent_user_id": {"$in": parent_refs}}],
         "id": {"$ne": student_id}},
        {"_id": 0, "id": 1}
    ).to_list(20)
    for s in also_siblings:
        sibling_ids.add(s["id"])

    siblings = []
    for sid in sibling_ids:
        s = await db.students.find_one(
            {"id": sid, "school_id": school_id},
            {"_id": 0, "id": 1, "full_name": 1, "class_name": 1, "grade_level": 1}
        )
        if s:
            siblings.append(s)

    return {"siblings": siblings, "total": len(siblings)}
