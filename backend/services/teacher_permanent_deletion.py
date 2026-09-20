"""Fail-closed permanent deletion of an exclusively school teacher account.

No ORM cascade is trusted: incoming FKs are inventoried before deletion, active
relations removed explicitly, and educational references moved to a non-login
school-local deleted-teacher marker. Unknown JSON relationships require review.
"""
import uuid
import re
import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import String, JSON, Text, case, cast, delete, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert

from pg_models import Base, GenericDocument, Teacher, User
from engines.entity_counts import reconcile_school_counts
from engines.sql_utils import gd_insert
from src.common.utils.tenant_scope import assert_school_access
from src.core.guards.tenant_guard import is_independent_workspace_id
from src.core.middleware.rbac import ROLE_PERMISSIONS


REVIEW = "لا يمكن حذف هذا الحساب نهائياً لوجود ارتباطات مشتركة أو غير مؤكدة. يلزم مراجعة مسؤول المنصة."
LABEL = "معلم محذوف"
logger = logging.getLogger(__name__)
ACTIVE_TABLES = {
    "teacher_assignments", "teacher_class_assignments", "user_sessions",
    "notifications", "notifications_preferences", "mfa_factors", "mfa_recovery_codes",
    "mfa_pending_challenges", "mfa_email_otps", "mfa_webauthn_challenges",
}
ACTIVE_DOCUMENTS = {
    "teacher_subjects", "teacher_assignments", "teacher_class_assignments",
    "user_roles", "school_memberships", "role_assignments", "user_relationships",
    "refresh_tokens", "refresh_token_families", "password_reset_tokens",
    "notifications", "notification_preferences", "teacher_preferences",
    "teacher_constraints", "teacher_availability", "teacher_schedule_preferences",
    "api_keys", "teacher_qr_codes", "teacher_other_duties", "teacher_lesson_plan_quota",
    "unavailability", "standby_overrides", "session_settings",
}
HISTORY_DOCUMENTS = {
    "timetable_sessions", "class_sessions", "schedules", "timetables", "timetable_runs",
    "attendance", "assessments", "assessment_submissions", "student_grades",
    "behaviour_records", "session_notes", "session_interactions", "session_event_logs",
    "teacher_sessions", "lesson_plans", "portfolio", "portfolios", "student_portfolios",
    "messages", "audit_logs", "monitoring_records", "teacher_monitoring",
    "substitution_assignments", "teacher_absences", "standby_assignments",
    "absence_excuses", "ai_operations", "ai_session_insights", "curriculum_lesson_audit",
    "curriculum_lessons", "exam_periods", "exam_schedule", "followup_records", "grades",
    "notification_logs", "participation_records", "plan_history", "portfolio_evidence",
    "portfolio_files", "session_analytics", "session_attendance", "session_homework",
    "student_activities", "student_certificates", "student_daily_scores",
    "student_score_ledger", "substitute_assignments", "teacher_assignment_removals",
    "teacher_attendance", "teacher_portfolio_meta", "timetable_conflicts",
    "timetable_hard_constraints", "timetable_run_logs", "timetable_soft_constraints",
    "timetable_unscheduled_demands",
}
MEMBERSHIP_DOCUMENTS = {"user_roles", "school_memberships", "role_assignments"}


def canonical(value, field):
    if not value:
        return None
    if field == "email":
        return value.strip().lower()
    digits = re.sub(r"\D", "", value)
    if field == "phone":
        if digits.startswith("00966"):
            digits = digits[2:]
        if digits.startswith("966") and len(digits) == 12:
            digits = "0" + digits[3:]
    return digits or None


def identity_column(column, field):
    if field == "email":
        return func.lower(func.trim(column))
    digits = func.regexp_replace(column, r"\D", "", "g")
    if field != "phone":
        return digits
    digits = case((digits.like("00966%"), func.substr(digits, 3)), else_=digits)
    return case(
        ((digits.like("966%")) & (func.length(digits) == 12), "0" + func.substr(digits, 4)),
        else_=digits,
    )


def review(reason="unclassified_guard", *, table="unknown", count=1):
    """Fail closed while recording a non-PII reason and affected row count."""
    logger.warning(
        "teacher_permanent_delete_blocked reason=%s table=%s count=%d",
        reason, table, count,
    )
    raise HTTPException(status_code=409, detail=REVIEW)


def contains(value, needles):
    if isinstance(value, dict):
        return any(k in needles or contains(v, needles) for k, v in value.items())
    if isinstance(value, list):
        return any(contains(v, needles) for v in value)
    return isinstance(value, str) and value in needles


def redact(value, replacements):
    """Rewrite nested arrays/objects and keyed identity maps, not just root IDs."""
    if isinstance(value, dict):
        return {replacements.get(k, k): redact(v, replacements) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, replacements) for v in value]
    return replacements.get(value, value) if isinstance(value, str) else value


def json_matches(column, ids):
    return or_(*(cast(column, Text).contains(value, autoescape=True) for value in ids))


def retire_schedule(value, ids):
    if isinstance(value, list):
        return [retire_schedule(v, ids) for v in value]
    if isinstance(value, dict):
        result = {k: retire_schedule(v, ids) for k, v in value.items()}
        if any(value.get(k) in ids for k in ("teacher_id", "substitute_teacher_id", "assigned_teacher_id")
               if isinstance(value.get(k), str)):
            result.update(is_active=False, status="cancelled")
        return result
    return value


def verify_document_scope(value, ids, school_id):
    if isinstance(value, list):
        for child in value:
            verify_document_scope(child, ids, school_id)
    elif isinstance(value, dict):
        if contains(value, ids):
            for key in ("school_id", "tenant_id", "workspace_school_id"):
                if value.get(key) not in (None, "", school_id):
                    review("foreign_nested_document_scope", table="json_document")
        for child in value.values():
            verify_document_scope(child, ids, school_id)


async def verify_teacher_relationship(session, document, teacher_id, school_id):
    """Only remove graph edges whose teacher role and typed endpoints are proven.

    IdentityEngine's user_id_1/user_id_2 format resolves *both* endpoints through
    get_user_by_id. Its teacher_class/teacher_subject enum labels therefore do
    not prove a class/subject endpoint or tenant ownership. Those legacy edges,
    including mixed schemas, require platform review rather than deletion.
    """
    if "user_id_1" in document or "user_id_2" in document:
        review("untyped_legacy_relationship", table="user_relationships")
    allowed_fields = {
        "id", "from_entity_type", "from_entity_id", "to_entity_type", "to_entity_id",
        "relationship_type", "tenant_id", "academic_year_id", "term_id", "metadata",
        "status", "created_at", "updated_at", "created_by",
    }
    if set(document) - allowed_fields:
        review("unknown_relationship_fields", table="user_relationships",
               count=len(set(document) - allowed_fields))
    targets = {
        "teaches_class": ("class", "classes"), "homeroom_for": ("class", "classes"),
        "teaches_subject": ("subject", "subjects"), "teaches_student": ("student", "students"),
        "employed_at": ("school", "schools"),
    }
    expected = targets.get(document.get("relationship_type"))
    if (
        expected is None or document.get("from_entity_type") != "teacher"
        or document.get("from_entity_id") != teacher_id
        or document.get("tenant_id") != school_id
        or document.get("to_entity_type") != expected[0]
        or not isinstance(document.get("to_entity_id"), str)
    ):
        review("invalid_teacher_relationship_shape", table="user_relationships")
    table = Base.metadata.tables[expected[1]]
    target = (await session.execute(select(table).where(
        table.c.id == document["to_entity_id"]
    ).with_for_update())).mappings().first()
    if target is None or (
        target["id"] if expected[0] == "school" else target["school_id"]
    ) != school_id:
        review("missing_or_foreign_relationship_target", table=expected[1], count=0 if target is None else 1)


async def _unmapped_references(session, ids, mutate=False):
    """Inspect live FK-less tables omitted from Base (auth + legacy migrations).

    Unknown matching columns fail closed. Identifiers come only from the catalog
    and are quoted; user-controlled values are always bind parameters.
    """
    columns = (await session.execute(text("""
        SELECT table_name, column_name FROM information_schema.columns
        WHERE table_schema=current_schema() AND data_type IN ('text','character varying')
        AND (column_name LIKE '%user_id' OR column_name LIKE '%teacher_id'
             OR column_name IN ('owner_id','principal_id','created_by','updated_by',
                               'recorded_by','performed_by','assessed_by','graded_by',
                               'reviewed_by','requested_by','approved_by'))
    """))).all()
    quote = session.bind.dialect.identifier_preparer.quote
    for table, column in columns:
        if table in Base.metadata.tables and column in Base.metadata.tables[table].c:
            continue
        qtable, qcol = quote(table), quote(column)
        condition = f"{qcol} IN (:teacher, :user)"
        params = {"teacher": ids[0], "user": ids[1]}
        found = (await session.execute(text(
            f"SELECT 1 FROM {qtable} WHERE {condition} LIMIT 1"
        ), params)).first()
        if not found:
            continue
        if table == "impersonation_sessions":
            if column == "original_user_id":
                review("impersonation_origin_claim", table="impersonation_sessions")
            if mutate:
                await session.execute(text(f"""
                    UPDATE {qtable} SET target_user_id=NULL, ended_at=COALESCE(ended_at,now()),
                    end_reason='teacher_permanently_deleted', reason='teacher_permanently_deleted'
                    WHERE {condition}
                """), params)
        elif table == "revoked_token_families":
            if mutate:
                await session.execute(text(f"UPDATE {qtable} SET {qcol}=NULL WHERE {condition}"), params)
        elif table == "teacher_record_backfill_794":
            # A rollback ledger cannot be allowed to recreate this deleted identity.
            if mutate:
                await session.execute(text(f"DELETE FROM {qtable} WHERE {condition}"), params)
        elif table == "teachers" and column == "created_by":
            # Present in the inspected database but not in the Teacher ORM.
            if mutate:
                await session.execute(text(
                    f"UPDATE {qtable} SET {qcol}='deleted-user' WHERE {condition}"
                ), params)
        else:
            review("unknown_unmapped_reference", table=table)


async def write_deletion_audit(session, teacher_id, school_id, actor, cleanup):
    await gd_insert(session, "audit_logs", {
        "id": str(uuid.uuid4()), "school_id": school_id, "action": "permanent_delete",
        "entity_type": "teacher", "entity_id": teacher_id, "performed_by": actor["id"],
        "new_state": {"permanent": True, "cleanup": cleanup},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def _verify_live_fks(session):
    """Reject schema drift rather than silently allowing an unknown DB CASCADE."""
    rows = (await session.execute(text("""
        SELECT c.conrelid::regclass::text AS source, a.attname AS col,
               c.confrelid::regclass::text AS target, c.confdeltype::text
        FROM pg_constraint c
        JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=ANY(c.conkey)
        WHERE c.contype='f' AND c.confrelid IN (
            SELECT oid FROM pg_class WHERE relname=ANY(:targets)
            AND relnamespace=current_schema()::regnamespace
        )
    """), {"targets": sorted(ACTIVE_TABLES | {"users", "teachers"})})).all()
    actions = {"CASCADE": "c", "SET NULL": "n", "RESTRICT": "r", "NO ACTION": "a", "SET DEFAULT": "d"}
    for source, col, target, action in rows:
        table = Base.metadata.tables.get(source)
        if table is None or col not in table.c or not any(
            fk.column.table.name == target and actions.get(fk.ondelete or "NO ACTION") == action
            for fk in table.c[col].foreign_keys
        ):
            review("live_fk_schema_drift", table=source)


async def permanently_delete_teacher(session, teacher_id, actor, *, expected_user_id=None):
    if actor.get("role") not in {"platform_admin", "school_principal", "school_admin"}:
        raise HTTPException(403, "غير مصرح")
    # School/user/profile links include legacy FK-less fields. Serialize writes to
    # these tables as well as taking row locks; row locks alone cannot stop a new
    # Teacher.user_id or GenericDocument membership from being inserted.
    try:
        async with session.begin_nested():
            await session.execute(text(
                "LOCK TABLE users, teachers, generic_documents, schools, "
                "workspace_collaborators IN SHARE ROW EXCLUSIVE MODE"
            ))
            expected_user = None
            if expected_user_id is not None:
                expected_user = (await session.execute(select(User).where(
                    User.id == expected_user_id).with_for_update())).scalar_one_or_none()
                if expected_user is None:
                    raise HTTPException(404, "المستخدم غير موجود")

            # Legacy rows can have only one side of the user/profile link. Resolve
            # them only when the remaining scalar link proves one unique profile;
            # role alone is never evidence of ownership.
            profile_claims = []
            if teacher_id:
                profile_claims.extend((Teacher.id == teacher_id, Teacher.teacher_id == teacher_id))
            if expected_user_id is not None:
                profile_claims.append(Teacher.user_id == expected_user_id)
                if expected_user and expected_user.teacher_id:
                    profile_claims.extend((
                        Teacher.id == expected_user.teacher_id,
                        Teacher.teacher_id == expected_user.teacher_id,
                    ))
            teachers = (await session.execute(select(Teacher).where(
                or_(*profile_claims)).with_for_update())).scalars().all() if profile_claims else []
            teachers = list({row.id: row for row in teachers}.values())
            if not teachers:
                if expected_user_id is not None:
                    review("missing_teacher_profile", table="teachers", count=0)
                raise HTTPException(404, "المعلم غير موجود")
            if len(teachers) != 1:
                review("ambiguous_teacher_profiles", table="teachers", count=len(teachers))
            teacher = teachers[0]
            teacher_id = teacher.id
            assert_school_access(actor, teacher.school_id)
            if not teacher.school_id or is_independent_workspace_id(teacher.school_id):
                review("non_school_teacher_profile", table="teachers")
            school_table = Base.metadata.tables["schools"]
            school = (await session.execute(select(school_table).where(
                school_table.c.id == teacher.school_id))).mappings().one()
            if {school.get("tenant_type"), school.get("school_type")} & {
                "independent_teacher", "independent_workspace", "independent_teacher_workspace",
            }:
                review("independent_school_type", table="schools")
            users = (await session.execute(select(User).where(or_(
                User.id == teacher.user_id, User.teacher_id == teacher_id,
                User.id == expected_user_id if expected_user_id is not None else False,
            )).with_for_update())).scalars().all()
            users = list({row.id: row for row in users}.values())
            if len(users) != 1:
                review("ambiguous_user_accounts", table="users", count=len(users))
            user = users[0]
            # User-management deletion addresses an account, not just a profile.
            # Verify the requested account under the same locks as all cleanup.
            if expected_user_id is not None and user.id != expected_user_id:
                review("requested_user_mismatch", table="users")
            teacher_claim = teacher.user_id == user.id
            user_claim = user.teacher_id == teacher_id
            if ((teacher.user_id is not None and not teacher_claim)
                    or (user.teacher_id is not None and not user_claim)
                    or not (teacher_claim or user_claim)
                    or (expected_user_id is None and not (teacher_claim and user_claim))
                    or user.tenant_id != teacher.school_id or user.role != "teacher"
                    or user.linked_roles or user.parent_id or user.student_id
                    or user.primary_tenant_id not in (None, teacher.school_id)):
                review("account_ownership_mismatch", table="users", count=1)
            default_permissions = set(ROLE_PERMISSIONS["teacher"])
            permissions = user.permissions or []
            if (
                not isinstance(permissions, list)
                or (permissions and set(permissions) != default_permissions)
            ):
                review("custom_teacher_permissions", table="users", count=len(permissions) if isinstance(permissions, list) else 1)
            other_profile_claims = [Teacher.user_id == user.id]
            if user.teacher_id:
                other_profile_claims.extend((
                    Teacher.id == user.teacher_id,
                    Teacher.teacher_id == user.teacher_id,
                ))
            profiles = (await session.execute(select(Teacher.id).where(
                or_(*other_profile_claims)
            ))).scalars().all()
            profiles = set(profiles)
            if profiles != {teacher_id}:
                review("additional_profile_claims", table="teachers", count=len(profiles))
            # Linked-role payloads are not relational FKs. Another account that
            # claims this profile is ambiguity even when User.teacher_id is NULL.
            if (await session.execute(select(User.id).where(
                User.id != user.id,
                json_matches(User.linked_roles, {teacher_id, user.id}),
            ).limit(1))).first():
                review("linked_role_profile_claim", table="users")
            for field in ("email", "phone", "national_id"):
                a, b = getattr(teacher, field), getattr(user, field)
                if a and b and canonical(a, field) != canonical(b, field):
                    review("profile_account_identity_mismatch", table="users")
            for model, own_id in ((Teacher, teacher_id), (User, user.id)):
                matches = []
                for field in ("email", "phone", "national_id"):
                    identity = canonical(getattr(teacher, field) or getattr(user, field), field)
                    if identity:
                        matches.append(identity_column(getattr(model, field), field) == identity)
                if matches and (await session.execute(select(model.id).where(
                    model.id != own_id, or_(*matches)
                ).limit(1))).first():
                    review("duplicate_identity_owner", table=model.__tablename__)
            ids = {teacher_id, user.id}
            if (await session.execute(select(school_table.c.id).where(
                    or_(school_table.c.principal_id == user.id,
                        school_table.c.id == f"itw_{user.id}")))).first():
                review("school_ownership_claim", table="schools")
            collaborators = Base.metadata.tables["workspace_collaborators"]
            if (await session.execute(select(collaborators.c.id).where(
                    collaborators.c.collaborator_user_id == user.id))).first():
                review("workspace_collaborator_claim", table="workspace_collaborators")
            await _verify_live_fks(session)
            await _unmapped_references(session, (teacher_id, user.id))

            # Inventory all mapped scalar/JSON references, including non-FK legacy
            # attribution fields and nested cached schedules. No collection limit.
            docs = (await session.execute(select(GenericDocument).where(
                json_matches(GenericDocument.data, ids)
            ).with_for_update())).scalars().all()
            linked_docs = []
            for doc in docs:
                if not contains(doc.data, ids):
                    continue
                collection = doc._collection
                if collection not in ACTIVE_DOCUMENTS | HISTORY_DOCUMENTS:
                    review("unknown_linked_document_collection", table=collection)
                verify_document_scope(doc.data, ids, teacher.school_id)
                if collection == "user_relationships":
                    await verify_teacher_relationship(session, doc.data, teacher_id, teacher.school_id)
                if collection in MEMBERSHIP_DOCUMENTS and (
                    doc.data.get("role", "teacher") != "teacher"
                    or (doc.data.get("school_id") or doc.data.get("tenant_id")) != teacher.school_id
                    or doc.data.get("roles") or doc.data.get("linked_roles")
                ):
                    review("invalid_membership_document", table=collection)
                scopes = {doc.data.get(k) for k in ("school_id", "tenant_id", "workspace_school_id")} - {None, ""}
                if scopes - {teacher.school_id}:
                    review("foreign_document_scope", table=collection)
                linked_docs.append(doc)

            references = []
            for table in Base.metadata.sorted_tables:
                if table.name in {"users", "teachers", "generic_documents", "revoked_tokens"}:
                    continue
                for col in table.c:
                    if not isinstance(col.type, String) or not (
                        col.name.endswith("_id") or col.name in {"created_by", "updated_by", "recorded_by",
                                                               "performed_by", "assessed_by", "graded_by",
                                                               "reviewed_by", "requested_by", "approved_by"}
                    ):
                        continue
                    rows = (await session.execute(select(table).where(col.in_(ids)).with_for_update())).mappings().all()
                    if not rows:
                        continue
                    # Role/ownership evidence outside the canonical profile is
                    # never erased to make a shared account appear exclusive.
                    if table.name in {"students", "parents", "schools", "workspace_collaborators", "lesson_plans", "noor_import_drafts"}:
                        review("shared_or_owner_reference", table=table.name, count=len(rows))
                    for row in rows:
                        scopes = {row.get(k) for k in ("school_id", "tenant_id", "workspace_school_id")} - {None, ""}
                        if scopes - {teacher.school_id}:
                            review("foreign_scalar_reference", table=table.name, count=len(rows))
                    targets = {fk.column.table.name for fk in col.foreign_keys}
                    if table.name not in ACTIVE_TABLES and "users" in targets and not col.nullable:
                        review("nonnullable_user_reference", table=table.name, count=len(rows))
                    references.append((table, col, targets))

            # Preflight and lock *all* typed JSON references before any write.
            # A snapshot can contain a teacher ID with no scalar teacher FK;
            # validate both its containing row and nested tenant scopes.
            json_references = []
            for table in Base.metadata.sorted_tables:
                if table.name in {"users", "teachers", "generic_documents"}:
                    continue
                json_columns = [c for c in table.c if isinstance(c.type, JSON)]
                if not json_columns:
                    continue
                for row in (await session.execute(select(table).where(
                    or_(*(json_matches(c, ids) for c in json_columns))
                ).with_for_update())).mappings():
                    matched = {c.name: row[c.name] for c in json_columns if contains(row[c.name], ids)}
                    if matched:
                        verify_document_scope(dict(row), ids, teacher.school_id)
                        json_references.append((
                            table, {c.name: row[c.name] for c in table.primary_key.columns}, matched,
                        ))

            marker_id = f"deleted-teacher:{teacher.school_id}"
            await session.execute(insert(Teacher).values(
                id=marker_id, school_id=None, full_name=LABEL,
                is_active=False, preferences={}, constraints={},
            ).on_conflict_do_nothing(index_elements=["id"]))
            # The marker never carries credentials, identity, or deleted_at (and
            # therefore cannot appear as a restorable teacher).
            marker = (await session.execute(select(Teacher).where(Teacher.id == marker_id))).scalar_one()
            if marker.school_id or marker.user_id or marker.email or marker.phone or marker.national_id or marker.is_active or marker.deleted_at:
                review("invalid_deleted_teacher_marker", table="teachers")
            replacements = {teacher_id: marker_id, user.id: "deleted-user"}
            for obj in (teacher, user):
                for field in ("email", "phone", "national_id", "full_name", "full_name_en"):
                    value = getattr(obj, field, None)
                    if value:
                        replacements[value] = LABEL
            cleanup = {}
            # Explicit cleanup precedes parent deletion; never rely on ORM
            # relationship cascades (teacher_sessions has ON DELETE CASCADE).
            for table, col, targets in references:
                condition = col.in_(ids)
                if table.name in ACTIVE_TABLES:
                    result = await session.execute(delete(table).where(condition))
                else:
                    replacement = marker_id if "teachers" in targets else (
                        None if "users" in targets else "deleted-user" if "user" in col.name or col.name.endswith("_by") else marker_id
                    )
                    values = {col.name: replacement}
                    if "teacher_name" in table.c:
                        values["teacher_name"] = LABEL
                    if table.name == "schedule_sessions":
                        values["status"] = "cancelled"
                        values[col.name] = None
                    if table.name == "classes":
                        # A deleted marker is historical attribution, not an
                        # active homeroom appointment.
                        values[col.name] = None
                    if table.name == "teacher_sessions":
                        # Preserve completed lessons; cancel pending teaching work.
                        await session.execute(update(table).where(condition, table.c.status == "scheduled")
                                              .values(status="cancelled"))
                    result = await session.execute(update(table).where(condition).values(**values))
                cleanup[table.name] = cleanup.get(table.name, 0) + result.rowcount
            for doc in linked_docs:
                if doc._collection in ACTIVE_DOCUMENTS:
                    await session.delete(doc)
                else:
                    doc.data = redact(retire_schedule(doc.data, ids), replacements) if doc._collection in {
                        "schedules", "timetables", "timetable_sessions", "class_sessions",
                        "standby_assignments", "substitution_assignments", "substitute_assignments",
                    } else redact(doc.data, replacements)
                    if doc._collection in {"timetable_sessions", "class_sessions", "standby_assignments", "substitution_assignments", "substitute_assignments"}:
                        doc.data = {**doc.data, "is_active": False}
                cleanup[doc._collection] = cleanup.get(doc._collection, 0) + 1
            # Rewrite only the locked, tenant-validated preflight inventory.
            for table, primary_key, matched in json_references:
                await session.execute(update(table).where(*(
                    table.c[name] == value for name, value in primary_key.items()
                )).values(**{name: redact(value, replacements) for name, value in matched.items()}))
            await _unmapped_references(session, (teacher_id, user.id), mutate=True)
            await session.execute(update(User).where(User.created_by == user.id).values(created_by="deleted-user"))
            await session.execute(update(Teacher).where(Teacher.deleted_by == user.id).values(deleted_by="deleted-user"))
            await session.flush()
            await session.execute(delete(Teacher).where(Teacher.id == teacher_id))
            await session.execute(delete(User).where(User.id == user.id))
            cleanup.update(teacher_profile=1, user_account=1)
            await reconcile_school_counts(session, teacher.school_id)
            await write_deletion_audit(session, teacher_id, teacher.school_id, actor, cleanup)
            await session.flush()
        # Middleware commits 4xx too: nested rollback protects *every* failure;
        # this commit ensures success cannot precede a durability failure.
    except Exception:
        # begin_nested already restored the pre-operation state. Do not roll
        # back the caller's unrelated work on a guard failure.
        raise
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return {"success": True, "permanent": True, "message": "تم حذف المعلم نهائياً", "cleanup": cleanup}