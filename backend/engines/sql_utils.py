import re as _re_module
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Type

from dateutil.parser import isoparse
from sqlalchemy import select, and_, or_, func, delete as sa_delete
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import DateTime, Date

_sql_logger = logging.getLogger("nassaq.sql_utils")

TENANT_ALIAS = {"tenant_id": "school_id", "school_id": "tenant_id"}

_SKIP_KEYS = frozenset({"_collection"})

_SENSITIVE_FILTER_KEYS = frozenset({
    "password_hash", "password", "refresh_token", "reset_token",
})

_MAX_REGEX_LENGTH = 200


def _sanitize_regex(pattern: str) -> str:
    if len(pattern) > _MAX_REGEX_LENGTH:
        raise ValueError(f"Regex pattern too long ({len(pattern)} > {_MAX_REGEX_LENGTH})")
    return _re_module.escape(pattern)


def _get_orm_model(collection: str):
    from pg_models import (
        User, School, Teacher, Student, Parent, Class, Subject,
        TeacherAssignment, TimeSlot, Timetable, TimetableRun,
        ScheduleSession, Attendance, ProductIssue, IssueComment,
        IssueDuplicateMap, IssueActivityLog, BulkActionHistory,
        AuditLog, Notification, Assessment, AssessmentSubmission,
        BehaviourRecord, SchoolSettings, RegistrationRequest,
        TeacherSession, HakimInsight, PlatformSettings,
        AcademicYear, AcademicTerm, Counter, LookupOption,
        Message, ApprovalEvent, SkillType, StudentSkill,
        SessionInteraction, AIInsight, AIIntervention,
        SessionNote, SessionEventLog, TeacherClassAssignment,
        GradeLevel, EducationalStage, PhysicalClassroom,
        BehaviourType, TimetableConstraint, ApprovalRequest,
        Event, SystemSetting,
    )
    _ORM_REGISTRY = {
        "users": User,
        "schools": School,
        "teachers": Teacher,
        "students": Student,
        "parents": Parent,
        "classes": Class,
        "subjects": Subject,
        "teacher_assignments": TeacherAssignment,
        "time_slots": TimeSlot,
        "timetables": Timetable,
        "timetable_runs": TimetableRun,
        "schedule_sessions": ScheduleSession,
        "attendance": Attendance,
        "product_issues": ProductIssue,
        "issue_comments": IssueComment,
        "issue_duplicates_map": IssueDuplicateMap,
        "issue_activity_log": IssueActivityLog,
        "bulk_action_history": BulkActionHistory,
        "audit_logs": AuditLog,
        "notifications": Notification,
        "assessments": Assessment,
        "assessment_submissions": AssessmentSubmission,
        "behaviour_records": BehaviourRecord,
        "school_settings": SchoolSettings,
        "registration_requests": RegistrationRequest,
        "teacher_sessions": TeacherSession,
        "hakim_insights": HakimInsight,
        "platform_settings": PlatformSettings,
        "academic_years": AcademicYear,
        "academic_terms": AcademicTerm,
        "counters": Counter,
        "lookup_options": LookupOption,
        "messages": Message,
        "approval_events": ApprovalEvent,
        "skills_types": SkillType,
        "student_skills": StudentSkill,
        "session_interactions": SessionInteraction,
        "ai_insights": AIInsight,
        "ai_interventions": AIIntervention,
        "session_notes": SessionNote,
        "session_event_log": SessionEventLog,
        "teacher_class_assignments": TeacherClassAssignment,
        "grade_levels": GradeLevel,
        "educational_stages": EducationalStage,
        "physical_classrooms": PhysicalClassroom,
        "behaviour_types": BehaviourType,
        "timetable_constraints": TimetableConstraint,
        "approval_requests": ApprovalRequest,
        "events": Event,
        "system_settings": SystemSetting,
    }
    return _ORM_REGISTRY.get(collection)


def _coerce_value(col_attr, val):
    if val is None:
        return None
    col_type = getattr(col_attr.property.columns[0], "type", None) if hasattr(col_attr, "property") else None
    if col_type is not None and isinstance(col_type, (DateTime, Date)):
        if isinstance(val, str):
            try:
                return isoparse(val)
            except (ValueError, TypeError):
                return val
        if isinstance(val, (int, float)):
            return datetime.fromtimestamp(val, tz=timezone.utc)
    return val


def _build_orm_filter_conditions(model_cls, filters: dict):
    conds = []
    if not filters:
        return conds
    col_map = _col_key_map(model_cls)
    cols = set(col_map.keys())
    has_data = "data" in cols
    for k, v in filters.items():
        if k in ("_id",):
            k = "id"
        if k == "$or":
            or_conds = []
            for sub in v:
                sub_conds = _build_orm_filter_conditions(model_cls, sub)
                if sub_conds:
                    or_conds.append(and_(*sub_conds) if len(sub_conds) > 1 else sub_conds[0])
            if or_conds:
                conds.append(or_(*or_conds))
        elif k == "$and":
            for sub in v:
                sub_conds = _build_orm_filter_conditions(model_cls, sub)
                conds.extend(sub_conds)
        elif k in cols:
            if k in _SENSITIVE_FILTER_KEYS:
                _sql_logger.warning(f"Blocked filter on sensitive column: {k}")
                continue
            col = getattr(model_cls, col_map[k])
            if isinstance(v, dict):
                for op, val in v.items():
                    val = _coerce_value(col, val)
                    if op == "$gte":
                        conds.append(col >= val)
                    elif op == "$lte":
                        conds.append(col <= val)
                    elif op == "$gt":
                        conds.append(col > val)
                    elif op == "$lt":
                        conds.append(col < val)
                    elif op == "$ne":
                        if val is None:
                            conds.append(col.isnot(None))
                        else:
                            conds.append(col != val)
                    elif op == "$in":
                        conds.append(col.in_(val))
                    elif op == "$nin":
                        conds.append(~col.in_(val))
                    elif op == "$regex":
                        safe_pattern = _sanitize_regex(str(val))
                        options = v.get("$options", "") if isinstance(v, dict) else ""
                        if "i" in options:
                            conds.append(col.op("~*")(safe_pattern))
                        else:
                            conds.append(col.op("~")(safe_pattern))
                    elif op == "$options":
                        pass
                    elif op == "$exists":
                        if val:
                            conds.append(col.isnot(None))
                        else:
                            conds.append(col.is_(None))
            elif isinstance(v, list):
                conds.append(col.in_(v))
            else:
                v = _coerce_value(col, v)
                conds.append(col == v)
        elif TENANT_ALIAS.get(k) in cols:
            real_key = TENANT_ALIAS[k]
            col = getattr(model_cls, col_map[real_key])
            if isinstance(v, dict):
                for op, val in v.items():
                    if op == "$in":
                        conds.append(col.in_(val))
                    elif op == "$ne":
                        conds.append(col != val)
            elif isinstance(v, list):
                conds.append(col.in_(v))
            else:
                conds.append(col == v)
        elif has_data:
            data_attr = getattr(model_cls, col_map["data"])
            json_expr = data_attr[k]
            col_expr = json_expr.astext
            if isinstance(v, dict):
                for op, val in v.items():
                    if op == "$gte":
                        conds.append(col_expr >= str(val))
                    elif op == "$lte":
                        conds.append(col_expr <= str(val))
                    elif op == "$gt":
                        conds.append(col_expr > str(val))
                    elif op == "$lt":
                        conds.append(col_expr < str(val))
                    elif op == "$ne":
                        if val is None:
                            conds.append(col_expr.isnot(None))
                        else:
                            conds.append(col_expr != str(val))
                    elif op == "$in":
                        conds.append(col_expr.in_([str(x) for x in val]))
                    elif op == "$regex":
                        safe_pattern = _sanitize_regex(str(val))
                        options = v.get("$options", "") if isinstance(v, dict) else ""
                        if "i" in options:
                            conds.append(col_expr.op("~*")(safe_pattern))
                        else:
                            conds.append(col_expr.op("~")(safe_pattern))
                    elif op == "$options":
                        pass
                    elif op == "$exists":
                        if val:
                            conds.append(json_expr.isnot(None))
                        else:
                            conds.append(json_expr.is_(None))
            elif isinstance(v, bool):
                conds.append(col_expr == str(v).lower())
            elif v is None:
                conds.append(json_expr.is_(None))
            else:
                conds.append(col_expr == str(v))
    return conds


def model_to_dict(obj) -> Optional[dict]:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    d = {}
    mapper = sa_inspect(type(obj))
    data_val = None
    has_data_col = False
    # Iterate column_attrs (Python attribute names) rather than columns
    # (DB column names) so that columns whose DB name collides with a
    # reserved class attribute (e.g. ``metadata`` on DeclarativeBase) are
    # still read from the correct instance attribute. The dict key uses the
    # DB column name for backward-compatible API output.
    for attr in mapper.column_attrs:
        py_key = attr.key
        col = attr.columns[0]
        out_key = col.name
        if out_key in _SKIP_KEYS or py_key in _SKIP_KEYS:
            continue
        val = getattr(obj, py_key, None)
        if isinstance(val, datetime):
            val = val.isoformat()
        if out_key == "data":
            has_data_col = True
            if isinstance(val, dict):
                data_val = val
        d[out_key] = val
    if has_data_col and data_val:
        for k, v in data_val.items():
            if k not in d:
                d[k] = v
    if "id" in d:
        d["_id"] = d["id"]
    return d


def models_to_dicts(objs) -> List[dict]:
    return [model_to_dict(o) for o in objs]


def _col_key_map(model_cls) -> dict:
    """Return ``{db_column_name: python_attribute_name}``.

    The two differ when an ORM column declares a ``name`` that collides with
    a reserved DeclarativeBase attribute (e.g. ``metadata``). Generic
    helpers receive request/response keys as DB column names but must use
    Python attribute names when calling ``getattr``/``setattr`` or passing
    kwargs to ``Model(**kwargs)``.
    """
    mapper = sa_inspect(model_cls)
    out = {}
    for attr in mapper.column_attrs:
        col = attr.columns[0]
        out[col.name] = attr.key
    return out


def _col_keys(model_cls) -> set:
    return set(_col_key_map(model_cls).keys())


def dict_to_model(model_cls, data: dict):
    col_map = _col_key_map(model_cls)
    cols = set(col_map.keys())
    kwargs = {}
    extra = {}
    for k, v in data.items():
        if k == "_id":
            continue
        if k in cols:
            py_key = col_map[k]
            kwargs[py_key] = _coerce_model_value(model_cls, py_key, v)
        elif TENANT_ALIAS.get(k) in cols:
            real_key = TENANT_ALIAS[k]
            py_key = col_map[real_key]
            kwargs[py_key] = _coerce_model_value(model_cls, py_key, v)
        else:
            extra[k] = v
    if extra and "data" in cols:
        data_py_key = col_map["data"]
        existing = kwargs.get(data_py_key) or {}
        if isinstance(existing, dict):
            kwargs[data_py_key] = {**existing, **extra}
        else:
            kwargs[data_py_key] = extra
    return model_cls(**kwargs)


def _coerce_model_value(model_cls, key, val):
    """``key`` here is a Python attribute name (already mapped from DB col)."""
    if val is None:
        return None
    try:
        col_attr = getattr(model_cls, key, None)
        if col_attr is not None:
            return _coerce_value(col_attr, val)
    except Exception:
        pass
    return val


def apply_updates(obj, updates: dict, model_cls=None):
    if model_cls is None:
        model_cls = type(obj)
    col_map = _col_key_map(model_cls)
    cols = set(col_map.keys())
    extra = {}
    for k, v in updates.items():
        if k in ("id", "_id"):
            continue
        if k in cols:
            py_key = col_map[k]
            v = _coerce_model_value(model_cls, py_key, v)
            setattr(obj, py_key, v)
        elif TENANT_ALIAS.get(k) in cols:
            real_key = TENANT_ALIAS[k]
            py_key = col_map[real_key]
            v = _coerce_model_value(model_cls, py_key, v)
            setattr(obj, py_key, v)
        else:
            extra[k] = v
    if extra and "data" in cols:
        data_py_key = col_map["data"]
        current = getattr(obj, data_py_key, None)
        current = dict(current) if isinstance(current, dict) else {}
        for ek, ev in extra.items():
            if "." in ek:
                parts = ek.split(".")
                target = current
                for p in parts[:-1]:
                    if p not in target or not isinstance(target[p], dict):
                        target[p] = {}
                    target = target[p]
                target[parts[-1]] = ev
            else:
                current[ek] = ev
        setattr(obj, data_py_key, current)


def _resolve_json_path(model_cls, field_path: str):
    parts = field_path.split(".")
    expr = model_cls.data
    for part in parts:
        expr = expr[part]
    return expr

def _build_filter_conditions(model_cls, filters: dict):
    """Translate dict-style filter to SQLAlchemy WHERE conditions.

    Supported operators: $or, $and, $expr ($ne/$eq field comparisons),
    $gt/$gte/$lt/$lte/$ne/$in/$nin/$exists/$regex on JSONB fields.
    Dot-path keys resolve to nested JSONB paths.  Comparisons use
    JSONB .astext (lexical) — numeric comparisons need explicit casts.
    """
    conds = []
    if not filters:
        return conds
    for k, v in filters.items():
        if k in _SENSITIVE_FILTER_KEYS:
            _sql_logger.warning(f"Blocked filter on sensitive key: {k}")
            continue
        if k == "$or":
            or_conds = []
            for sub in v:
                sub_conds = _build_filter_conditions(model_cls, sub)
                if sub_conds:
                    or_conds.append(and_(*sub_conds) if len(sub_conds) > 1 else sub_conds[0])
            if or_conds:
                conds.append(or_(*or_conds))
        elif k == "$and":
            for sub in v:
                sub_conds = _build_filter_conditions(model_cls, sub)
                conds.extend(sub_conds)
        elif k == "$expr":
            if isinstance(v, dict):
                if "$ne" in v:
                    parts = v["$ne"]
                    if len(parts) == 2:
                        left = parts[0]
                        right = parts[1]
                        if isinstance(left, str) and left.startswith("$") and isinstance(right, str) and right.startswith("$"):
                            left_path = left[1:].split(".")
                            right_path = right[1:].split(".")
                            left_expr = model_cls.data
                            for p in left_path:
                                left_expr = left_expr[p]
                            right_expr = model_cls.data
                            for p in right_path:
                                right_expr = right_expr[p]
                            conds.append(left_expr.astext != right_expr.astext)
                elif "$eq" in v:
                    parts = v["$eq"]
                    if len(parts) == 2:
                        left = parts[0]
                        right = parts[1]
                        if isinstance(left, str) and left.startswith("$") and isinstance(right, str) and right.startswith("$"):
                            left_path = left[1:].split(".")
                            right_path = right[1:].split(".")
                            left_expr = model_cls.data
                            for p in left_path:
                                left_expr = left_expr[p]
                            right_expr = model_cls.data
                            for p in right_path:
                                right_expr = right_expr[p]
                            conds.append(left_expr.astext == right_expr.astext)
        elif k == "id":
            if isinstance(v, dict):
                for op, val in v.items():
                    if op == "$in":
                        conds.append(model_cls.id.in_(val))
                    elif op == "$ne":
                        conds.append(model_cls.id != val)
            else:
                conds.append(model_cls.id == v)
        elif isinstance(v, dict):
            json_expr = _resolve_json_path(model_cls, k)
            col_expr = json_expr.astext
            for op, val in v.items():
                if op == "$gte":
                    conds.append(col_expr >= str(val))
                elif op == "$lte":
                    conds.append(col_expr <= str(val))
                elif op == "$gt":
                    conds.append(col_expr > str(val))
                elif op == "$lt":
                    conds.append(col_expr < str(val))
                elif op == "$ne":
                    if val is None:
                        conds.append(col_expr.isnot(None))
                    elif isinstance(val, bool):
                        conds.append(col_expr != str(val).lower())
                    else:
                        conds.append(col_expr != str(val))
                elif op == "$in":
                    conds.append(col_expr.in_([str(x) for x in val]))
                elif op == "$nin":
                    conds.append(~col_expr.in_([str(x) for x in val]))
                elif op == "$regex":
                    safe_pattern = _sanitize_regex(str(val))
                    options = v.get("$options", "") if isinstance(v, dict) else ""
                    if "i" in options:
                        conds.append(col_expr.op("~*")(safe_pattern))
                    else:
                        conds.append(col_expr.op("~")(safe_pattern))
                elif op == "$options":
                    pass
                elif op == "$exists":
                    if val:
                        conds.append(json_expr.isnot(None))
                    else:
                        conds.append(json_expr.is_(None))
        elif isinstance(v, list):
            json_expr = _resolve_json_path(model_cls, k)
            conds.append(json_expr.astext.in_([str(x) for x in v]))
        elif isinstance(v, bool):
            json_expr = _resolve_json_path(model_cls, k)
            conds.append(json_expr.astext == str(v).lower())
        else:
            json_expr = _resolve_json_path(model_cls, k)
            conds.append(json_expr.astext == str(v))
    return conds


async def gd_find(session, collection: str, filters: dict = None,
                  order_by: str = None, desc_order: bool = True,
                  limit: int = None, offset: int = None) -> List[dict]:
    orm_model = _get_orm_model(collection)
    if orm_model is not None:
        return await _orm_find(session, orm_model, filters, order_by, desc_order, limit, offset)
    from pg_models import GenericDocument
    stmt = select(GenericDocument).where(GenericDocument._collection == collection)
    conds = _build_filter_conditions(GenericDocument, filters)
    if conds:
        stmt = stmt.where(and_(*conds))
    if order_by:
        if order_by == "id":
            col = GenericDocument.id
        elif order_by == "created_at":
            col = GenericDocument.created_at
        else:
            col = GenericDocument.data[order_by].astext
        stmt = stmt.order_by(col.desc() if desc_order else col.asc())
    if offset:
        stmt = stmt.offset(offset)
    if limit:
        stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return models_to_dicts(result.scalars().all())


async def _orm_find(session, model_cls, filters, order_by, desc_order, limit, offset):
    stmt = select(model_cls)
    conds = _build_orm_filter_conditions(model_cls, filters)
    if conds:
        stmt = stmt.where(and_(*conds))
    if order_by:
        cols = _col_keys(model_cls)
        if order_by in cols:
            col = getattr(model_cls, order_by)
        elif TENANT_ALIAS.get(order_by) in cols:
            col = getattr(model_cls, TENANT_ALIAS[order_by])
        elif hasattr(model_cls, "data"):
            col = model_cls.data[order_by].astext
        else:
            col = None
        if col is not None:
            stmt = stmt.order_by(col.desc() if desc_order else col.asc())
    if offset:
        stmt = stmt.offset(offset)
    if limit:
        stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    return models_to_dicts(result.scalars().all())


async def gd_find_one(session, collection: str, filters: dict = None, sort=None) -> Optional[dict]:
    order_by = None
    desc_order = True
    if sort and isinstance(sort, list) and len(sort) > 0:
        field, direction = sort[0]
        order_by = field
        desc_order = (direction == -1)
    results = await gd_find(session, collection, filters, order_by=order_by, desc_order=desc_order, limit=1)
    return results[0] if results else None


async def gd_insert(session, collection: str, doc: dict) -> str:
    orm_model = _get_orm_model(collection)
    if orm_model is not None:
        doc_id = doc.get("id") or str(uuid.uuid4())
        insert_data = {**doc, "id": doc_id}
        insert_data.pop("_id", None)
        obj = dict_to_model(orm_model, insert_data)
        session.add(obj)
        await session.flush()
        return doc_id
    from pg_models import GenericDocument
    doc_id = doc.get("id") or str(uuid.uuid4())
    data = {k: v for k, v in doc.items() if k not in ("id", "_id")}
    obj = GenericDocument(id=doc_id, _collection=collection, data=data)
    session.add(obj)
    await session.flush()
    return doc_id


async def gd_insert_many(session, collection: str, docs: list) -> List[str]:
    ids = []
    for doc in docs:
        doc_id = await gd_insert(session, collection, doc)
        ids.append(doc_id)
    return ids


def _apply_dict_updates(current_data: dict, updates: dict) -> dict:
    if "$set" in updates or "$push" in updates or "$pull" in updates or "$inc" in updates or "$unset" in updates:
        if "$set" in updates:
            for k, v in updates["$set"].items():
                _set_nested(current_data, k, v)
        if "$push" in updates:
            for k, v in updates["$push"].items():
                arr = current_data.get(k, [])
                if not isinstance(arr, list):
                    arr = []
                arr.append(v)
                current_data[k] = arr
        if "$pull" in updates:
            for k, v in updates["$pull"].items():
                arr = current_data.get(k, [])
                if isinstance(arr, list):
                    current_data[k] = [item for item in arr if item != v]
        if "$inc" in updates:
            for k, v in updates["$inc"].items():
                current_data[k] = (current_data.get(k) or 0) + v
        if "$unset" in updates:
            for k in updates["$unset"]:
                current_data.pop(k, None)
        return current_data
    for k, v in updates.items():
        _set_nested(current_data, k, v)
    return current_data


def _set_nested(data: dict, key: str, value) -> None:
    if "." in key:
        parts = key.split(".")
        target = data
        for p in parts[:-1]:
            if p not in target or not isinstance(target[p], dict):
                target[p] = {}
            target = target[p]
        target[parts[-1]] = value
    else:
        data[key] = value

async def gd_update_one(session, collection: str, filters: dict, updates: dict) -> int:
    orm_model = _get_orm_model(collection)
    if orm_model is not None:
        return await _orm_update_one(session, orm_model, filters, updates)
    from pg_models import GenericDocument
    stmt = select(GenericDocument).where(GenericDocument._collection == collection)
    conds = _build_filter_conditions(GenericDocument, filters)
    if conds:
        stmt = stmt.where(and_(*conds))
    stmt = stmt.limit(1).with_for_update()
    result = await session.execute(stmt)
    obj = result.scalars().first()
    if not obj:
        return 0
    current_data = dict(obj.data) if obj.data else {}
    _apply_dict_updates(current_data, updates)
    obj.data = current_data
    await session.flush()
    return 1


async def _orm_update_one(session, model_cls, filters, updates):
    stmt = select(model_cls)
    conds = _build_orm_filter_conditions(model_cls, filters)
    if conds:
        stmt = stmt.where(and_(*conds))
    stmt = stmt.limit(1)
    result = await session.execute(stmt)
    obj = result.scalars().first()
    if not obj:
        return 0
    flat_updates = _flatten_update_operators(updates)
    apply_updates(obj, flat_updates, model_cls)
    await session.flush()
    return 1


def _flatten_update_operators(updates: dict) -> dict:
    if "$set" in updates or "$inc" in updates or "$unset" in updates:
        flat = {}
        if "$set" in updates:
            flat.update(updates["$set"])
        if "$inc" in updates:
            for k, v in updates["$inc"].items():
                flat[k] = v
        if "$unset" in updates:
            for k in updates["$unset"]:
                flat[k] = None
        if "$push" in updates:
            flat["$push"] = updates["$push"]
        if "$pull" in updates:
            flat["$pull"] = updates["$pull"]
        return flat
    return updates


async def gd_upsert(session, collection: str, filters: dict, updates: dict) -> int:
    orm_model = _get_orm_model(collection)
    if orm_model is not None:
        stmt = select(orm_model)
        conds = _build_orm_filter_conditions(orm_model, filters)
        if conds:
            stmt = stmt.where(and_(*conds))
        stmt = stmt.limit(1)
        result = await session.execute(stmt)
        obj = result.scalars().first()
        if obj:
            flat_updates = _flatten_update_operators(updates)
            apply_updates(obj, flat_updates, orm_model)
            await session.flush()
            return 1
        else:
            merged = dict(filters)
            merged.update(updates)
            return await gd_insert(session, collection, merged)
    from pg_models import GenericDocument
    stmt = select(GenericDocument).where(GenericDocument._collection == collection)
    conds = _build_filter_conditions(GenericDocument, filters)
    if conds:
        stmt = stmt.where(and_(*conds))
    stmt = stmt.limit(1)
    result = await session.execute(stmt)
    obj = result.scalars().first()
    if obj:
        current_data = dict(obj.data) if obj.data else {}
        _apply_dict_updates(current_data, updates)
        obj.data = current_data
        await session.flush()
        return 1
    else:
        merged = dict(filters)
        merged.update(updates)
        return await gd_insert(session, collection, merged)


async def gd_update_many(session, collection: str, filters: dict, updates: dict) -> int:
    orm_model = _get_orm_model(collection)
    if orm_model is not None:
        stmt = select(orm_model)
        conds = _build_orm_filter_conditions(orm_model, filters)
        if conds:
            stmt = stmt.where(and_(*conds))
        result = await session.execute(stmt)
        objs = result.scalars().all()
        flat_updates = _flatten_update_operators(updates)
        count = 0
        for obj in objs:
            apply_updates(obj, flat_updates, orm_model)
            count += 1
        if count:
            await session.flush()
        return count
    from pg_models import GenericDocument
    stmt = select(GenericDocument).where(GenericDocument._collection == collection)
    conds = _build_filter_conditions(GenericDocument, filters)
    if conds:
        stmt = stmt.where(and_(*conds))
    stmt = stmt.with_for_update()
    result = await session.execute(stmt)
    objs = result.scalars().all()
    count = 0
    for obj in objs:
        current_data = dict(obj.data) if obj.data else {}
        _apply_dict_updates(current_data, updates)
        obj.data = current_data
        count += 1
    if count:
        await session.flush()
    return count


async def gd_count(session, collection: str, filters: dict = None) -> int:
    orm_model = _get_orm_model(collection)
    if orm_model is not None:
        stmt = select(func.count(orm_model.id))
        conds = _build_orm_filter_conditions(orm_model, filters)
        if conds:
            stmt = stmt.where(and_(*conds))
        result = await session.execute(stmt)
        return result.scalar() or 0
    from pg_models import GenericDocument
    stmt = select(func.count(GenericDocument.id)).where(
        GenericDocument._collection == collection
    )
    conds = _build_filter_conditions(GenericDocument, filters)
    if conds:
        stmt = stmt.where(and_(*conds))
    result = await session.execute(stmt)
    return result.scalar() or 0


async def gd_delete_one(session, collection: str, filters: dict) -> int:
    orm_model = _get_orm_model(collection)
    if orm_model is not None:
        stmt = select(orm_model)
        conds = _build_orm_filter_conditions(orm_model, filters)
        if conds:
            stmt = stmt.where(and_(*conds))
        stmt = stmt.limit(1)
        result = await session.execute(stmt)
        obj = result.scalars().first()
        if not obj:
            return 0
        await session.delete(obj)
        await session.flush()
        return 1
    from pg_models import GenericDocument
    stmt = select(GenericDocument).where(GenericDocument._collection == collection)
    conds = _build_filter_conditions(GenericDocument, filters)
    if conds:
        stmt = stmt.where(and_(*conds))
    stmt = stmt.limit(1)
    result = await session.execute(stmt)
    obj = result.scalars().first()
    if not obj:
        return 0
    await session.delete(obj)
    await session.flush()
    return 1


async def gd_delete_many(session, collection: str, filters: dict) -> int:
    orm_model = _get_orm_model(collection)
    if orm_model is not None:
        sub = select(orm_model.id)
        conds = _build_orm_filter_conditions(orm_model, filters)
        if conds:
            sub = sub.where(and_(*conds))
        stmt = sa_delete(orm_model).where(orm_model.id.in_(sub.scalar_subquery()))
        result = await session.execute(stmt)
        await session.flush()
        return result.rowcount
    from pg_models import GenericDocument
    sub = select(GenericDocument.id).where(GenericDocument._collection == collection)
    conds = _build_filter_conditions(GenericDocument, filters)
    if conds:
        sub = sub.where(and_(*conds))
    stmt = sa_delete(GenericDocument).where(GenericDocument.id.in_(sub.scalar_subquery()))
    result = await session.execute(stmt)
    await session.flush()
    return result.rowcount


async def gd_distinct(session, collection: str, field: str, filters: dict = None) -> List:
    orm_model = _get_orm_model(collection)
    if orm_model is not None:
        cols = _col_keys(orm_model)
        if field in cols:
            col_expr = getattr(orm_model, field)
        elif TENANT_ALIAS.get(field) in cols:
            col_expr = getattr(orm_model, TENANT_ALIAS[field])
        elif hasattr(orm_model, "data"):
            col_expr = orm_model.data[field].astext
        else:
            return []
        stmt = select(func.distinct(col_expr))
        conds = _build_orm_filter_conditions(orm_model, filters)
        if conds:
            stmt = stmt.where(and_(*conds))
        result = await session.execute(stmt)
        return [row[0] for row in result.fetchall()]
    from pg_models import GenericDocument
    col_expr = GenericDocument.data[field].astext
    stmt = select(func.distinct(col_expr)).where(
        GenericDocument._collection == collection
    )
    conds = _build_filter_conditions(GenericDocument, filters)
    if conds:
        stmt = stmt.where(and_(*conds))
    result = await session.execute(stmt)
    return [row[0] for row in result.fetchall()]


async def _gd_inc(session, collection: str, filters: dict, increments: dict) -> int:
    doc = await gd_find_one(session, collection, filters)
    if not doc:
        return 0
    updates = {}
    for k, v in increments.items():
        current = doc.get(k, 0)
        try:
            current = int(current) if current is not None else 0
        except (ValueError, TypeError):
            current = 0
        updates[k] = current + v
    return await gd_update_one(session, collection, filters, updates)


async def _gd_push(session, collection: str, filters: dict, push_fields: dict) -> int:
    doc = await gd_find_one(session, collection, filters)
    if not doc:
        return 0
    updates = {}
    for k, v in push_fields.items():
        current = doc.get(k, []) or []
        if not isinstance(current, list):
            current = []
        current.append(v)
        updates[k] = current
    return await gd_update_one(session, collection, filters, updates)


async def _gd_pull(session, collection: str, filters: dict, pull_fields: dict) -> int:
    doc = await gd_find_one(session, collection, filters)
    if not doc:
        return 0
    updates = {}
    for k, v in pull_fields.items():
        current = doc.get(k, []) or []
        if isinstance(current, list):
            current = [x for x in current if x != v]
        updates[k] = current
    return await gd_update_one(session, collection, filters, updates)


async def _gd_addtoset(session, collection: str, filters: dict, addtoset_fields: dict) -> int:
    doc = await gd_find_one(session, collection, filters)
    if not doc:
        return 0
    updates = {}
    for k, v in addtoset_fields.items():
        current = doc.get(k, []) or []
        if not isinstance(current, list):
            current = []
        if v not in current:
            current.append(v)
        updates[k] = current
    return await gd_update_one(session, collection, filters, updates)


async def _gd_unset(session, collection: str, filters: dict, unset_fields: dict) -> int:
    updates = {k: None for k in unset_fields}
    return await gd_update_one(session, collection, filters, updates)


def _resolve_dot_path(doc, path):
    parts = path.split(".")
    val = doc
    for p in parts:
        if isinstance(val, dict):
            val = val.get(p)
        else:
            return None
    return val

def _eval_agg_expr(expr, doc):
    if isinstance(expr, str) and expr.startswith("$"):
        return _resolve_dot_path(doc, expr[1:])
    if isinstance(expr, dict):
        if "$ifNull" in expr:
            parts = expr["$ifNull"]
            val = _eval_agg_expr(parts[0], doc)
            return val if val is not None else (parts[1] if len(parts) > 1 else None)
        if "$cond" in expr:
            cond = expr["$cond"]
            if isinstance(cond, list) and len(cond) == 3:
                test, t_val, f_val = cond
            elif isinstance(cond, dict):
                test, t_val, f_val = cond.get("if"), cond.get("then"), cond.get("else")
            else:
                return 0
            if _eval_match_expr(test, doc):
                return _eval_agg_expr(t_val, doc)
            return _eval_agg_expr(f_val, doc)
        if "$multiply" in expr:
            parts = expr["$multiply"]
            result = 1
            for p in parts:
                v = _eval_agg_expr(p, doc)
                result *= (v if v is not None else 0)
            return result
        if "$divide" in expr:
            parts = expr["$divide"]
            num = _eval_agg_expr(parts[0], doc) or 0
            den = _eval_agg_expr(parts[1], doc) or 1
            return num / den if den else 0
        if "$add" in expr:
            return sum(_eval_agg_expr(p, doc) or 0 for p in expr["$add"])
        if "$subtract" in expr:
            parts = expr["$subtract"]
            return (_eval_agg_expr(parts[0], doc) or 0) - (_eval_agg_expr(parts[1], doc) or 0)
        if "$size" in expr:
            arr = _eval_agg_expr(expr["$size"], doc)
            return len(arr) if isinstance(arr, list) else 0
        if "$slice" in expr:
            parts = expr["$slice"]
            arr = _eval_agg_expr(parts[0], doc) or []
            n = parts[1] if len(parts) > 1 else len(arr)
            return arr[:n]
    return expr

def _eval_match_expr(expr, doc):
    if isinstance(expr, dict):
        if "$eq" in expr:
            parts = expr["$eq"]
            return _eval_agg_expr(parts[0], doc) == _eval_agg_expr(parts[1], doc)
        if "$ne" in expr:
            parts = expr["$ne"]
            return _eval_agg_expr(parts[0], doc) != _eval_agg_expr(parts[1], doc)
        if "$gt" in expr:
            parts = expr["$gt"]
            a, b = _eval_agg_expr(parts[0], doc), _eval_agg_expr(parts[1], doc)
            return (a or 0) > (b or 0)
        if "$gte" in expr:
            parts = expr["$gte"]
            a, b = _eval_agg_expr(parts[0], doc), _eval_agg_expr(parts[1], doc)
            return (a or 0) >= (b or 0)
        if "$in" in expr:
            parts = expr["$in"]
            return _eval_agg_expr(parts[0], doc) in (_eval_agg_expr(parts[1], doc) or [])
    return bool(expr)

def _check_match_condition(doc, k, v):
    if k == "$or":
        return any(all(_check_match_condition(doc, sk, sv) for sk, sv in sub.items()) for sub in v)
    if k == "$and":
        return all(all(_check_match_condition(doc, sk, sv) for sk, sv in sub.items()) for sub in v)
    if k == "$expr":
        return _eval_match_expr(v, doc)
    dv = _resolve_dot_path(doc, k)
    if isinstance(v, dict):
        for op, ov in v.items():
            if op == "$gt" and not ((dv or 0) > ov):
                return False
            elif op == "$gte" and not ((dv or 0) >= ov):
                return False
            elif op == "$lt" and not ((dv or 0) < ov):
                return False
            elif op == "$lte" and not ((dv or 0) <= ov):
                return False
            elif op == "$ne" and dv == ov:
                return False
            elif op == "$in" and dv not in (ov or []):
                return False
            elif op == "$nin" and dv in (ov or []):
                return False
            elif op == "$exists":
                if ov and dv is None:
                    return False
                if not ov and dv is not None:
                    return False
            elif op == "$regex":
                pattern = _re_module.escape(str(ov))
                if not _re_module.search(pattern, str(dv or ""), _re_module.IGNORECASE):
                    return False
        return True
    return dv == v

def _apply_match_filter(docs, match_filter):
    result = []
    for doc in docs:
        if all(_check_match_condition(doc, k, v) for k, v in match_filter.items()):
            result.append(doc)
    return result

def _apply_group(docs, group_stage):
    group_id = group_stage.get("_id")
    groups = {}
    for doc in docs:
        if isinstance(group_id, str) and group_id.startswith("$"):
            key = _resolve_dot_path(doc, group_id[1:])
        elif isinstance(group_id, dict):
            key_parts = {}
            for gk, gv in group_id.items():
                if isinstance(gv, str) and gv.startswith("$"):
                    key_parts[gk] = _resolve_dot_path(doc, gv[1:])
                else:
                    key_parts[gk] = gv
            key = tuple(sorted(key_parts.items()))
        elif group_id is None:
            key = None
        else:
            key = group_id

        if key not in groups:
            groups[key] = {"_id": dict(key) if isinstance(key, tuple) else key, "_docs": []}
        groups[key]["_docs"].append(doc)

    result = []
    for key, group in groups.items():
        row = {"_id": group["_id"]}
        for field, expr in group_stage.items():
            if field == "_id":
                continue
            if isinstance(expr, dict):
                if "$sum" in expr:
                    sum_expr = expr["$sum"]
                    if isinstance(sum_expr, (int, float)):
                        row[field] = sum_expr * len(group["_docs"]) if sum_expr != 1 else len(group["_docs"])
                    elif isinstance(sum_expr, str) and sum_expr.startswith("$"):
                        row[field] = sum(doc.get(sum_expr[1:], 0) or 0 for doc in group["_docs"])
                    elif isinstance(sum_expr, dict):
                        row[field] = sum(_eval_agg_expr(sum_expr, doc) or 0 for doc in group["_docs"])
                    else:
                        row[field] = 0
                elif "$avg" in expr:
                    avg_field = expr["$avg"]
                    if isinstance(avg_field, str) and avg_field.startswith("$"):
                        vals = [doc.get(avg_field[1:], 0) or 0 for doc in group["_docs"]]
                        row[field] = sum(vals) / len(vals) if vals else 0
                elif "$first" in expr:
                    first_field = expr["$first"]
                    if isinstance(first_field, str) and first_field.startswith("$"):
                        row[field] = group["_docs"][0].get(first_field[1:]) if group["_docs"] else None
                elif "$push" in expr:
                    push_field = expr["$push"]
                    if isinstance(push_field, str) and push_field.startswith("$"):
                        row[field] = [doc.get(push_field[1:]) for doc in group["_docs"]]
                    elif isinstance(push_field, dict):
                        row[field] = [{pk: _eval_agg_expr(pv, doc) for pk, pv in push_field.items()} for doc in group["_docs"]]
                    else:
                        row[field] = [push_field for _ in group["_docs"]]
                elif "$max" in expr:
                    max_field = expr["$max"]
                    if isinstance(max_field, str) and max_field.startswith("$"):
                        vals = [doc.get(max_field[1:]) for doc in group["_docs"] if doc.get(max_field[1:]) is not None]
                        row[field] = max(vals) if vals else None
                elif "$min" in expr:
                    min_field = expr["$min"]
                    if isinstance(min_field, str) and min_field.startswith("$"):
                        vals = [doc.get(min_field[1:]) for doc in group["_docs"] if doc.get(min_field[1:]) is not None]
                        row[field] = min(vals) if vals else None
                elif "$count" in expr:
                    row[field] = len(group["_docs"])
            elif isinstance(expr, str) and expr.startswith("$"):
                row[field] = group["_docs"][0].get(expr[1:]) if group["_docs"] else None
        result.append(row)
    return result

async def _gd_aggregate(session, collection: str, pipeline: list) -> List[dict]:
    """Aggregate pipeline emulation over gd_find.

    Supported stages: $match, $group, $sort, $limit, $count, $addFields,
    $project, $unwind.  Fetches up to 50k docs from SQL then processes
    in Python.  Operators are text-based (JSONB .astext) so comparisons
    use lexical ordering — callers needing numeric/date-native ordering
    should cast values in route code.
    """
    initial_match = {}
    first_stage = pipeline[0] if pipeline else {}
    if "$match" in first_stage:
        initial_match = first_stage["$match"]

    docs = await gd_find(session, collection, initial_match, limit=50000)

    for stage in pipeline:
        if "$match" in stage:
            if stage is first_stage:
                continue
            docs = _apply_match_filter(docs, stage["$match"])
        elif "$group" in stage:
            docs = _apply_group(docs, stage["$group"])
        elif "$sort" in stage:
            for field, direction in reversed(list(stage["$sort"].items())):
                docs = sorted(docs, key=lambda d, f=field: d.get(f) or "", reverse=(direction == -1))
        elif "$limit" in stage:
            docs = docs[:stage["$limit"]]
        elif "$count" in stage:
            count_field = stage["$count"]
            docs = [{count_field: len(docs)}]
        elif "$addFields" in stage:
            for doc in docs:
                for k, v in stage["$addFields"].items():
                    doc[k] = _eval_agg_expr(v, doc)
        elif "$project" in stage:
            proj = stage["$project"]
            new_docs = []
            for doc in docs:
                new_doc = {}
                for k, v in proj.items():
                    if v == 0:
                        continue
                    elif v == 1:
                        new_doc[k] = doc.get(k)
                    elif isinstance(v, dict):
                        new_doc[k] = _eval_agg_expr(v, doc)
                    elif isinstance(v, str) and v.startswith("$"):
                        new_doc[k] = _resolve_dot_path(doc, v[1:])
                    else:
                        new_doc[k] = v
                for k in doc:
                    if k not in proj:
                        has_excludes = any(pv == 0 for pv in proj.values())
                        if has_excludes:
                            new_doc[k] = doc[k]
                new_docs.append(new_doc)
            docs = new_docs
        elif "$unwind" in stage:
            unwind = stage["$unwind"]
            if isinstance(unwind, str):
                field = unwind.lstrip("$")
            else:
                field = unwind.get("path", "").lstrip("$")
            new_docs = []
            for doc in docs:
                arr = doc.get(field, [])
                if isinstance(arr, list):
                    for item in arr:
                        new_doc = dict(doc)
                        new_doc[field] = item
                        new_docs.append(new_doc)
                else:
                    new_docs.append(doc)
            docs = new_docs

    return docs
