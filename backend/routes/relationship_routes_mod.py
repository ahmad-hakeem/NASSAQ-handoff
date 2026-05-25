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
from engines.sql_utils import gd_find, gd_find_one, gd_insert, gd_insert_many, gd_update_one, gd_update_many, gd_count, gd_delete_one, gd_delete_many, gd_distinct, _gd_addtoset


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

    student = await gd_find_one(db.session, "students", {"id": data.student_id, "tenant_id": school_id, "is_active": True})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")

    parent = None
    resolved_parent_user_id = data.parent_user_id
    if data.parent_id:
        parent = await gd_find_one(db.session, "parents", {"id": data.parent_id, "school_id": school_id})
        if parent and not resolved_parent_user_id:
            resolved_parent_user_id = parent.get("user_id")
    elif data.parent_user_id:
        parent = await gd_find_one(db.session, "users", {"id": data.parent_user_id, "tenant_id": school_id, "role": "parent"})

    if not parent:
        raise HTTPException(status_code=404, detail="ولي الأمر غير موجود")

    parent_ref = data.parent_id or data.parent_user_id
    existing = await gd_find_one(db.session, "guardian_links", {
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
        await gd_update_many(db.session, "guardian_links", {"tenant_id": school_id, "student_id": data.student_id, "is_primary": True}, {"is_primary": False})

    link_doc = {
        "id": link_id,
        "tenant_id": school_id,
        "student_id": data.student_id,
        "student_name": student.get("full_name"),
        "parent_id": data.parent_id,
        "parent_user_id": resolved_parent_user_id,
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

    await gd_insert(db.session, "guardian_links", link_doc)

    await _gd_addtoset(db.session, "students", {"id": data.student_id}, {"guardian_ids": parent_ref})
    if data.parent_id:
        await _gd_addtoset(db.session, "parents", {"id": data.parent_id}, {"student_ids": data.student_id})

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
    link = await gd_find_one(db.session, "guardian_links", {"id": link_id, "tenant_id": school_id})
    if not link:
        raise HTTPException(status_code=404, detail="الربط غير موجود")

    await gd_update_one(db.session, "guardian_links", {"id": link_id}, {
            "is_active": False,
            "unlinked_by": current_user["id"],
            "unlinked_at": datetime.now(timezone.utc).isoformat()
        })

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
    link = await gd_find_one(db.session, "guardian_links", {"id": link_id, "tenant_id": school_id})
    if not link:
        raise HTTPException(status_code=404, detail="الربط غير موجود")

    updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if data.relationship is not None:
        updates["relationship"] = data.relationship
    if data.is_primary is not None:
        if data.is_primary:
            await gd_update_many(db.session, "guardian_links", {"tenant_id": school_id, "student_id": link["student_id"], "is_primary": True}, {"is_primary": False})
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

    await gd_update_one(db.session, "guardian_links", {"id": link_id}, {**updates, **perm_updates})

    return {"message": "تم تحديث الربط بنجاح", "id": link_id}


@router.get("/guardian/student/{student_id}")
async def get_student_guardians(
    student_id: str,
    include_inactive: bool = False,
    current_user: dict = Depends(get_current_user)
):
    """Get all guardians linked to a student.

    SECURITY: Guardian data is sensitive family information. The caller
    must be the student themselves, one of the student's own guardians, a
    teacher assigned to the student's class, or a school admin. Same-tenant
    membership alone is not sufficient.
    """
    from utils.tenant_scope import can_view_student, require_can_view_student_sync_check
    allowed = await can_view_student(db.session, current_user, student_id)
    require_can_view_student_sync_check(allowed)
    school_id = current_user.get("tenant_id")
    query = {"tenant_id": school_id, "student_id": student_id}
    if not include_inactive:
        query["is_active"] = True

    links = await gd_find(db.session, "guardian_links", query, order_by="is_primary", desc_order=True, limit=20)
    return {"guardians": links, "total": len(links)}


@router.get("/guardian/parent/{parent_ref}")
async def get_parent_children(
    parent_ref: str,
    current_user: dict = Depends(get_current_user)
):
    """Get all children linked to a parent/guardian.

    SECURITY: A caller may only see their own children list (parent_ref
    matches their user id) or must be a school admin / platform admin.
    Any other caller receives 403.
    """
    _ADMIN_ROLES = frozenset({
        UserRole.PLATFORM_ADMIN.value,
        UserRole.SCHOOL_PRINCIPAL.value,
        UserRole.SCHOOL_ADMIN.value,
        UserRole.SCHOOL_SUB_ADMIN.value,
    })
    caller_role = current_user.get("role", "")
    caller_id = current_user.get("id", "")
    is_admin = caller_role in _ADMIN_ROLES

    if not is_admin:
        if caller_role != UserRole.PARENT.value:
            raise HTTPException(
                status_code=403,
                detail="لا يمكنك الاطلاع على أبناء ولي أمر آخر"
            )
        # parent_ref may be a parent-table row ID or a user ID; check both.
        is_self_parent = caller_id == parent_ref
        if not is_self_parent:
            parent_row = await gd_find_one(db.session, "parents", {"id": parent_ref})
            if parent_row and parent_row.get("user_id") == caller_id:
                is_self_parent = True
        if not is_self_parent:
            parent_row = await gd_find_one(db.session, "parents", {"user_id": parent_ref})
            if parent_row and parent_row.get("user_id") == caller_id:
                is_self_parent = True
        if not is_self_parent:
            raise HTTPException(
                status_code=403,
                detail="لا يمكنك الاطلاع على أبناء ولي أمر آخر"
            )


    school_id = current_user.get("tenant_id")
    links = await gd_find(db.session, "guardian_links", {"tenant_id": school_id, "parent_ref": parent_ref, "is_active": True}, limit=20)

    children = []
    for link in links:
        student = await gd_find_one(db.session, "students", {"id": link["student_id"], "tenant_id": school_id, "is_active": True})
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

    from_link = await gd_find_one(db.session, "guardian_links", {
        "tenant_id": school_id, "student_id": student_id,
        "parent_ref": from_parent, "is_active": True
    })
    to_link = await gd_find_one(db.session, "guardian_links", {
        "tenant_id": school_id, "student_id": student_id,
        "parent_ref": to_parent, "is_active": True
    })

    if not from_link:
        raise HTTPException(status_code=404, detail="الولي المصدر غير مرتبط بالطالب")
    if not to_link:
        raise HTTPException(status_code=404, detail="الولي المستلم غير مرتبط بالطالب")

    now = datetime.now(timezone.utc).isoformat()

    await gd_update_one(db.session, "guardian_links", {"id": from_link["id"]}, {"is_primary": False, "updated_at": now})
    await gd_update_one(db.session, "guardian_links", {"id": to_link["id"]}, {"is_primary": True, "updated_at": now})

    await gd_insert(db.session, "custody_transfers", {
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
    """Get relationship graph for any entity (student, teacher, parent).

    SECURITY: The student graph exposes family structure, guardian names,
    sibling records, and class context. For student entities the caller must
    be authorized to view that student (self / guardian / assigned teacher /
    admin). For teacher and parent entities the caller must be the entity
    themselves or an admin.
    """
    role = current_user.get("role", "")
    _admin_roles = frozenset({"platform_admin", "school_principal", "school_admin", "school_sub_admin"})
    caller_id = current_user.get("id", "")
    school_id = current_user.get("tenant_id")

    student = await gd_find_one(db.session, "students", {"id": entity_id, "school_id": school_id, "is_active": True})

    if student:
        from utils.tenant_scope import can_view_student, require_can_view_student_sync_check
        allowed = await can_view_student(db.session, current_user, entity_id)
        require_can_view_student_sync_check(allowed)

        guardians = await gd_find(db.session, "guardian_links", {"tenant_id": school_id, "student_id": entity_id, "is_active": True}, limit=10)

        teacher_assignments_raw = await gd_find(db.session, "teacher_assignments", {"school_id": school_id, "class_id": student.get("class_id"), "is_active": True}, limit=20)

        ta_teacher_ids = list({a.get("teacher_id") for a in teacher_assignments_raw if a.get("teacher_id")})
        ta_subject_ids = list({a.get("subject_id") for a in teacher_assignments_raw if a.get("subject_id")})
        ta_teachers = {}
        if ta_teacher_ids:
            tch_docs = await gd_find(db.session, "teachers", {"id": {"$in": ta_teacher_ids}}, limit=50)
            ta_teachers = {t["id"]: t.get("full_name", "") for t in tch_docs}
        ta_subjects = {}
        if ta_subject_ids:
            sub_docs = await gd_find(db.session, "subjects", {"id": {"$in": ta_subject_ids}}, limit=50)
            ta_subjects = {s["id"]: s.get("name_ar", "") for s in sub_docs}

        classmates = await gd_find(db.session, "students", {"school_id": school_id, "class_id": student.get("class_id"), "id": {"$ne": entity_id}}, limit=50)

        siblings_rels = await gd_find(db.session, "user_relationships", {"$or": [
                {"from_entity_id": entity_id, "relationship_type": "sibling", "status": "active"},
                {"to_entity_id": entity_id, "relationship_type": "sibling", "status": "active"},
                {"user_id_1": entity_id, "relationship_type": "sibling", "is_active": True},
                {"user_id_2": entity_id, "relationship_type": "sibling", "is_active": True},
            ]}, limit=20)
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
            raw_siblings = await gd_find(db.session, "students", {"id": {"$in": sibling_ids}}, limit=20)
            for sib in raw_siblings:
                sib_allowed = await can_view_student(db.session, current_user, sib["id"])
                if sib_allowed:
                    siblings.append(sib)

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

    teacher = await gd_find_one(db.session, "users", {"id": entity_id, "tenant_id": school_id, "role": "teacher"})

    if teacher:
        # SECURITY: a caller may view a teacher's relationship graph only
        # if they are that teacher themselves or a school/platform admin.
        if role not in _admin_roles and caller_id != entity_id:
            raise HTTPException(status_code=403, detail="لا يمكنك عرض بيانات معلم آخر")

        teacher_record_id = teacher.get("teacher_id") or entity_id
        teacher_rec = await gd_find_one(db.session, "teachers", {"$or": [{"id": entity_id}, {"user_id": entity_id}, {"id": teacher_record_id}], "school_id": school_id})
        lookup_id = teacher_rec["id"] if teacher_rec else teacher_record_id

        assignments = await gd_find(db.session, "teacher_assignments", {"school_id": school_id, "teacher_id": lookup_id, "is_active": True}, limit=30)

        sub_ids = list({a.get("subject_id") for a in assignments if a.get("subject_id")})
        sub_names = {}
        if sub_ids:
            subs = await gd_find(db.session, "subjects", {"id": {"$in": sub_ids}}, limit=50)
            sub_names = {s["id"]: s.get("name_ar", "") for s in subs}

        cls_ids = list({a.get("class_id") for a in assignments if a.get("class_id")})
        cls_names = {}
        if cls_ids:
            classes_docs = await gd_find(db.session, "classes", {"id": {"$in": cls_ids}}, limit=50)
            cls_names = {c["id"]: c.get("name", "") for c in classes_docs}

        classes = list({a["class_id"] for a in assignments if a.get("class_id")})
        student_count = 0
        for cid in classes:
            student_count += await gd_count(db.session, "students", {"school_id": school_id, "class_id": cid})

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
    parent = await gd_find_one(db.session, "users", parent_query)
    if parent:
        # SECURITY: a caller may view a parent's relationship graph only
        # if they are that parent themselves or a school/platform admin.
        # This prevents same-tenant users from enumerating other families'
        # children via the graph endpoint.
        if role not in _admin_roles and caller_id != entity_id:
            raise HTTPException(status_code=403, detail="لا يمكنك عرض بيانات ولي أمر آخر")

        link_query = {"parent_ref": entity_id, "is_active": True}
        if school_id:
            link_query["tenant_id"] = school_id
        children_links = await gd_find(db.session, "guardian_links", link_query, limit=20)

        children = []
        for link in children_links:
            child_query = {"id": link["student_id"]}
            if school_id:
                child_query["school_id"] = school_id
            child = await gd_find_one(db.session, "students", child_query)
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
    """Get siblings of a student (shared parents).

    SECURITY: Sibling data reveals family structure for other children.
    The caller must have a legitimate relationship to the target student
    (self / guardian / assigned teacher / admin).
    """
    from utils.tenant_scope import can_view_student, require_can_view_student_sync_check
    allowed = await can_view_student(db.session, current_user, student_id)
    require_can_view_student_sync_check(allowed)
    school_id = current_user.get("tenant_id")

    links = await gd_find(db.session, "guardian_links", {"tenant_id": school_id, "student_id": student_id, "is_active": True}, limit=10)

    parent_refs = [l["parent_ref"] for l in links]
    if not parent_refs:
        parent = await gd_find_one(db.session, "students", {"id": student_id, "is_active": True})
        if parent:
            if parent.get("parent_id"):
                parent_refs.append(parent["parent_id"])
            if parent.get("parent_user_id"):
                parent_refs.append(parent["parent_user_id"])

    if not parent_refs:
        return {"siblings": [], "total": 0}

    sibling_ids = set()
    for pref in parent_refs:
        sibling_links = await gd_find(db.session, "guardian_links", {"tenant_id": school_id, "parent_ref": pref, "is_active": True}, limit=20)
        for sl in sibling_links:
            if sl["student_id"] != student_id:
                sibling_ids.add(sl["student_id"])

    also_siblings = await gd_find(db.session, "students", {"school_id": school_id,
         "$or": [{"parent_id": {"$in": parent_refs}}, {"parent_user_id": {"$in": parent_refs}}],
         "id": {"$ne": student_id}}, limit=20)
    for s in also_siblings:
        sibling_ids.add(s["id"])

    from utils.tenant_scope import can_view_student
    siblings = []
    for sid in sibling_ids:
        s = await gd_find_one(db.session, "students", {"id": sid, "school_id": school_id, "is_active": True})
        if s:
            sib_allowed = await can_view_student(db.session, current_user, sid)
            if sib_allowed:
                siblings.append(s)

    return {"siblings": siblings, "total": len(siblings)}
