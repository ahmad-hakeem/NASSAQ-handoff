"""
NASSAQ PostgreSQL Adapter - MongoDB-compatible API over SQLAlchemy
Translates MongoDB motor driver patterns (find_one, find, insert_one, etc.)
to SQLAlchemy async session operations, enabling migration with minimal
changes to routes and engines.
"""
import uuid
import re
import logging
import contextvars
from datetime import datetime, timezone
from dateutil import parser as dateutil_parser
from typing import Any, Dict, List, Optional, Type

from sqlalchemy import select, func, and_, or_, desc, asc, inspect, text, delete as sa_delete, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import DateTime
from sqlalchemy.orm import joinedload, selectinload

from db import Base, async_session_factory

logger = logging.getLogger("nassaq.pg_adapter")

_pg_session_var: contextvars.ContextVar[Optional[AsyncSession]] = contextvars.ContextVar(
    "_pg_session", default=None
)


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def _gen_id():
    return str(uuid.uuid4())


def _coerce_value_for_column(model, key, value):
    if value is None or model is None:
        return value
    mapper = inspect(model)
    col_obj = mapper.columns.get(key)
    if col_obj is None:
        alias = COLUMN_ALIASES.get(key)
        if alias:
            col_obj = mapper.columns.get(alias)
    if col_obj is not None and isinstance(col_obj.type, DateTime) and isinstance(value, str):
        try:
            return dateutil_parser.isoparse(value)
        except (ValueError, TypeError):
            return value
    return value


COLUMN_ALIASES = {
    "tenant_id": "school_id",
    "school_id": "tenant_id",
}


def _build_collection_map():
    from pg_models import (
        User, School, Teacher, Student, Parent, Class, Subject,
        TeacherAssignment, TimeSlot, Timetable, TimetableRun, ScheduleSession,
        Attendance, ProductIssue, IssueComment, IssueDuplicateMap, IssueActivityLog,
        BulkActionHistory, AuditLog, Notification, Assessment, AssessmentSubmission,
        BehaviourRecord, SchoolSettings, RegistrationRequest, TeacherSession,
        HakimInsight, PlatformSettings, AcademicYear, AcademicTerm, Counter,
        LookupOption, Message, ApprovalEvent, SkillType, StudentSkill,
        SessionInteraction, AIInsight, AIIntervention, SessionNote,
        SessionEventLog, TeacherClassAssignment, GradeLevel, EducationalStage,
        PhysicalClassroom, BehaviourType, TimetableConstraint, ApprovalRequest,
        Event, SystemSetting, GenericDocument,
    )
    return {
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
        "timetable_sessions": ScheduleSession,
        "attendance": Attendance,
        "product_issues": ProductIssue,
        "issue_comments": IssueComment,
        "issue_duplicates_map": IssueDuplicateMap,
        "issue_activity_log": IssueActivityLog,
        "bulk_action_history": BulkActionHistory,
        "audit_logs": AuditLog,
        "audit_log": AuditLog,
        "notifications": Notification,
        "assessments": Assessment,
        "assessment_submissions": AssessmentSubmission,
        "behaviour_records": BehaviourRecord,
        "behavior": BehaviourRecord,
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
        "skill_types": SkillType,
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
        "timetable_hard_constraints": TimetableConstraint,
        "timetable_soft_constraints": TimetableConstraint,
        "approval_requests": ApprovalRequest,
        "events": Event,
        "system_settings": SystemSetting,
    }


_COLLECTION_MAP: Optional[dict] = None


def _get_collection_map():
    global _COLLECTION_MAP
    if _COLLECTION_MAP is None:
        _COLLECTION_MAP = _build_collection_map()
    return _COLLECTION_MAP


def _model_has_column(model, col_name: str) -> bool:
    if model is None:
        return False
    mapper = inspect(model)
    return col_name in {c.key for c in mapper.columns}


def _resolve_column(model, key: str):
    if _model_has_column(model, key):
        return getattr(model, key)
    alias = COLUMN_ALIASES.get(key)
    if alias and _model_has_column(model, alias):
        return getattr(model, alias)
    return None


def _build_condition(model, key: str, value, is_generic: bool = False):
    if is_generic:
        from pg_models import GenericDocument
        if key == "id":
            return GenericDocument.id == value
        if key == "_id":
            return GenericDocument.id == (str(value) if not isinstance(value, str) else value)
        return GenericDocument.data[key].astext == str(value) if not isinstance(value, dict) else _build_operator_condition_generic(key, value)
    if key == "_id":
        col = _resolve_column(model, "id")
        if col is not None:
            v = str(value) if not isinstance(value, (str, dict)) else value
            if isinstance(v, dict):
                return _build_operator_condition(model, "id", v)
            return col == v
        return None

    if "." in key:
        parts = key.split(".", 1)
        parent_col = _resolve_column(model, parts[0])
        if parent_col is not None:
            from sqlalchemy.dialects.postgresql import JSONB as _JSONB
            col_type = getattr(parent_col.property.columns[0], 'type', None) if hasattr(parent_col, 'property') else None
            if isinstance(col_type, _JSONB):
                jsonb_path = parent_col[parts[1]]
                if isinstance(value, dict):
                    conditions = []
                    for op, val in value.items():
                        if op == "$exists":
                            conditions.append(jsonb_path.isnot(None) if val else jsonb_path.is_(None))
                        elif op == "$ne":
                            conditions.append(jsonb_path.astext != str(val) if val is not None else jsonb_path.isnot(None))
                        elif op == "$in":
                            conditions.append(jsonb_path.astext.in_([str(v) for v in val]))
                    if len(conditions) == 1:
                        return conditions[0]
                    return and_(*conditions) if conditions else None
                return jsonb_path.astext == str(value)
        return None

    col = _resolve_column(model, key)
    if col is None:
        return None

    if isinstance(value, dict):
        return _build_operator_condition(model, key, value, col)
    resolved_key = key if key != "_id" else "id"
    return col == _coerce_value_for_column(model, resolved_key, value)


def _build_operator_condition(model, key, ops: dict, col=None):
    if col is None:
        col = _resolve_column(model, key)
    if col is None:
        return None

    def _cv(v):
        return _coerce_value_for_column(model, key, v) if model is not None else v

    conditions = []
    for op, val in ops.items():
        if op == "$in":
            conditions.append(col.in_([_cv(v) for v in val]))
        elif op == "$nin":
            conditions.append(~col.in_([_cv(v) for v in val]))
        elif op == "$ne":
            conditions.append(col != _cv(val))
        elif op == "$gte":
            conditions.append(col >= _cv(val))
        elif op == "$gt":
            conditions.append(col > _cv(val))
        elif op == "$lt":
            conditions.append(col < _cv(val))
        elif op == "$lte":
            conditions.append(col <= _cv(val))
        elif op == "$exists":
            conditions.append(col.isnot(None) if val else col.is_(None))
        elif op == "$regex":
            flags = ops.get("$options", "")
            pattern = val
            starts = pattern.startswith("^")
            ends = pattern.endswith("$")
            if starts:
                pattern = pattern[1:]
            if ends:
                pattern = pattern[:-1]
            pattern = pattern.replace("%", r"\%").replace("_", r"\_")
            if starts and ends:
                like_pat = pattern
            elif starts:
                like_pat = f"{pattern}%"
            elif ends:
                like_pat = f"%{pattern}"
            else:
                like_pat = f"%{pattern}%"
            if "i" in flags:
                conditions.append(col.ilike(like_pat))
            else:
                conditions.append(col.like(like_pat))
        elif op == "$not":
            inner = _build_operator_condition(model, key, val, col)
            if inner is not None:
                conditions.append(~inner)
    if len(conditions) == 1:
        return conditions[0]
    return and_(*conditions) if conditions else None


def _build_operator_condition_generic(key, ops: dict):
    from pg_models import GenericDocument
    data_col = GenericDocument.data
    conditions = []
    for op, val in ops.items():
        if op == "$ne":
            conditions.append(data_col[key].astext != str(val))
        elif op == "$gte":
            conditions.append(data_col[key].astext >= str(val))
        elif op == "$gt":
            conditions.append(data_col[key].astext > str(val))
        elif op == "$lt":
            conditions.append(data_col[key].astext < str(val))
        elif op == "$lte":
            conditions.append(data_col[key].astext <= str(val))
        elif op == "$in":
            conditions.append(data_col[key].astext.in_([str(v) for v in val]))
        elif op == "$exists":
            conditions.append(data_col.has_key(key) if val else ~data_col.has_key(key))
    if len(conditions) == 1:
        return conditions[0]
    return and_(*conditions) if conditions else None


def _translate_filter(model, filter_dict: dict, is_generic: bool = False):
    if not filter_dict:
        return []
    conditions = []
    for key, value in filter_dict.items():
        if key == "$or":
            or_parts = []
            for sub in value:
                sub_conds = _translate_filter(model, sub, is_generic)
                if sub_conds:
                    or_parts.append(and_(*sub_conds) if len(sub_conds) > 1 else sub_conds[0])
            if or_parts:
                conditions.append(or_(*or_parts))
        elif key == "$and":
            for sub in value:
                conditions.extend(_translate_filter(model, sub, is_generic))
        elif key == "$expr":
            pass
        else:
            c = _build_condition(model, key, value, is_generic)
            if c is not None:
                conditions.append(c)
    return conditions


def _has_expr_filter(filter_dict):
    return "$expr" in filter_dict if filter_dict else False


def _apply_expr_filter(docs, expr):
    if not expr or not isinstance(expr, dict):
        return docs
    agg = AggregationCursor(None, [])
    return [d for d in docs if agg._eval_condition(expr, d)]


def _apply_sort(stmt, model, sort_spec, is_generic=False):
    if sort_spec is None:
        return stmt
    if isinstance(sort_spec, list):
        for field, direction in sort_spec:
            if is_generic:
                from pg_models import GenericDocument
                col = GenericDocument.data[field].astext
            else:
                col = _resolve_column(model, field)
                if col is None:
                    continue
            stmt = stmt.order_by(desc(col) if direction == -1 else asc(col))
    elif isinstance(sort_spec, str):
        if is_generic:
            from pg_models import GenericDocument
            col = GenericDocument.data[sort_spec].astext
        else:
            col = _resolve_column(model, sort_spec)
            if col is None:
                return stmt
        stmt = stmt.order_by(desc(col))
    return stmt


def _orm_to_dict(obj) -> dict:
    if obj is None:
        return None
    if isinstance(obj, dict):
        if "id" in obj and "_id" not in obj:
            obj["_id"] = obj["id"]
        return obj
    d = {}
    mapper = inspect(type(obj))
    has_data_col = False
    data_val = None
    for col in mapper.columns:
        val = getattr(obj, col.key, None)
        if isinstance(val, datetime):
            val = val.isoformat()
        if col.key == "data":
            has_data_col = True
            if isinstance(val, dict):
                data_val = val
            d[col.key] = val
        else:
            d[col.key] = val
    if has_data_col and data_val:
        for k, v in data_val.items():
            if k not in d:
                d[k] = v
    if "id" in d:
        d["_id"] = d["id"]
    return d


def _get_nested_value(doc, path, default=None):
    parts = path.split(".")
    current = doc
    for p in parts:
        if isinstance(current, dict):
            current = current.get(p, default)
        else:
            return default
    return current


def _set_nested_value(doc, path, value):
    parts = path.split(".")
    current = doc
    for p in parts[:-1]:
        if p not in current or not isinstance(current.get(p), dict):
            current[p] = {}
        current = current[p]
    current[parts[-1]] = value


def _apply_projection(doc: dict, projection: dict) -> dict:
    if not projection or not doc:
        return doc
    exclude_id = projection.get("_id") == 0
    proj = {k: v for k, v in projection.items() if k != "_id"}
    includes = {k for k, v in proj.items() if v}
    excludes = {k for k, v in proj.items() if not v}
    if includes:
        has_dotted = any("." in k for k in includes)
        if has_dotted:
            result = {}
            if not exclude_id:
                result["id"] = doc.get("id")
                result["_id"] = doc.get("_id", doc.get("id"))
            else:
                result["id"] = doc.get("id")
            for k in includes:
                if "." in k:
                    val = _get_nested_value(doc, k)
                    if val is not None:
                        _set_nested_value(result, k, val)
                else:
                    if k in doc:
                        result[k] = doc[k]
            return result
        result = {}
        for k, v in doc.items():
            if k == "_id":
                if not exclude_id:
                    result[k] = v
            elif k in includes or k == "id":
                result[k] = v
        return result
    if excludes or exclude_id:
        result = {}
        for k, v in doc.items():
            if k in excludes:
                continue
            if k == "_id" and exclude_id:
                continue
            result[k] = v
        return result
    return doc


class DuplicateKeyError(Exception):
    pass


class InsertOneResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class UpdateResult:
    def __init__(self, matched=0, modified=0, upserted=False):
        self.matched_count = matched
        self.modified_count = modified
        self.upserted_count = 1 if upserted else 0
        self.raw_result = {"n": matched, "nModified": modified}


class DeleteResult:
    def __init__(self, deleted=0):
        self.deleted_count = deleted


class PgCursor:
    def __init__(self, collection, filter_dict, projection=None, options=None):
        self._collection = collection
        self._filter = filter_dict or {}
        self._projection = projection
        self._options = options
        self._sort_spec = None
        self._limit_val = None
        self._skip_val = 0
        self._results = None

    def sort(self, key_or_list, direction=None):
        if isinstance(key_or_list, str):
            self._sort_spec = [(key_or_list, direction if direction is not None else -1)]
        elif isinstance(key_or_list, list):
            self._sort_spec = key_or_list
        return self

    def limit(self, n: int):
        self._limit_val = n
        return self

    def skip(self, n: int):
        self._skip_val = n
        return self

    async def _execute(self):
        if self._results is not None:
            return self._results
        session = self._collection._db._get_session()
        own_session = False
        if session is None:
            session = self._collection._db.session_factory()
            own_session = True
        try:
            model = self._collection._model
            is_generic = self._collection._is_generic

            if is_generic:
                from pg_models import GenericDocument
                stmt = select(GenericDocument).where(
                    GenericDocument._collection == self._collection._name
                )
                conds = _translate_filter(model, self._filter, is_generic=True)
                if conds:
                    stmt = stmt.where(and_(*conds))
                stmt = _apply_sort(stmt, model, self._sort_spec, is_generic=True)
            else:
                stmt = select(model)
                if self._options:
                    for opt in self._options:
                        stmt = stmt.options(opt)
                conds = _translate_filter(model, self._filter)
                if conds:
                    stmt = stmt.where(and_(*conds))
                stmt = _apply_sort(stmt, model, self._sort_spec)

            if self._skip_val:
                stmt = stmt.offset(self._skip_val)
            if self._limit_val:
                stmt = stmt.limit(self._limit_val)

            result = await session.execute(stmt)
            rows = result.scalars().all()

            if is_generic:
                docs = []
                for r in rows:
                    d = dict(r.data) if r.data else {}
                    d["id"] = r.id
                    d["_id"] = r.id
                    docs.append(d)
            else:
                docs = [_orm_to_dict(r) for r in rows]

            if self._projection:
                docs = [_apply_projection(d, self._projection) for d in docs]

            self._results = docs
        finally:
            if own_session:
                await session.close()
        return self._results

    async def to_list(self, length=None):
        results = await self._execute()
        if length is not None:
            return results[:length]
        return results

    def __aiter__(self):
        self._iter_index = 0
        return self

    async def __anext__(self):
        results = await self._execute()
        if self._iter_index >= len(results):
            raise StopAsyncIteration
        doc = results[self._iter_index]
        self._iter_index += 1
        return doc


class AggregationCursor:
    def __init__(self, collection, pipeline):
        self._collection = collection
        self._pipeline = pipeline
        self._results = None

    def _parse_pipeline(self):
        match_filter = {}
        group_stage = None
        sort_spec = None
        limit_val = None
        project_stage = None
        unwind_field = None
        post_match = None
        has_bucket = False
        count_stage_field = None

        _KNOWN_STAGES = {"$match", "$group", "$sort", "$limit", "$project", "$unwind", "$bucket", "$count"}
        has_unknown_stage = False

        seen_group = False
        for stage in self._pipeline:
            if "$match" in stage:
                if seen_group:
                    post_match = stage["$match"]
                else:
                    match_filter.update(stage["$match"])
            elif "$group" in stage:
                group_stage = stage["$group"]
                seen_group = True
            elif "$sort" in stage:
                sort_spec = stage["$sort"]
            elif "$limit" in stage:
                limit_val = stage["$limit"]
            elif "$project" in stage:
                project_stage = stage["$project"]
            elif "$unwind" in stage:
                val = stage["$unwind"]
                unwind_field = val if isinstance(val, str) else val.get("path", "")
                if unwind_field.startswith("$"):
                    unwind_field = unwind_field[1:]
            elif "$bucket" in stage:
                has_bucket = True
            elif "$count" in stage:
                count_stage_field = stage["$count"]
            else:
                stage_keys = set(stage.keys())
                if not stage_keys.issubset(_KNOWN_STAGES):
                    has_unknown_stage = True

        return match_filter, group_stage, sort_spec, limit_val, project_stage, unwind_field, post_match, has_bucket, has_unknown_stage, count_stage_field

    def _can_translate_to_sql(self, group_stage, sort_spec, project_stage, unwind_field, post_match, has_bucket, has_unknown_stage):
        if self._collection is None or self._collection._is_generic:
            return False
        if self._collection._model is None:
            return False
        if has_bucket or unwind_field or post_match or has_unknown_stage:
            return False
        if project_stage:
            return False
        if group_stage is None:
            return False

        model = self._collection._model
        group_key = group_stage.get("_id")
        if not self._is_simple_group_key(group_key):
            return False

        if isinstance(group_key, str):
            field = group_key.lstrip("$")
            if _resolve_column(model, field) is None:
                return False
        elif isinstance(group_key, dict):
            for alias, ref in group_key.items():
                field = ref.lstrip("$")
                if _resolve_column(model, field) is None:
                    return False

        accumulators = {k: v for k, v in group_stage.items() if k != "_id"}
        acc_names = set()
        for acc_name, acc_spec in accumulators.items():
            if not isinstance(acc_spec, dict):
                return False
            op = list(acc_spec.keys())[0] if acc_spec else None
            if op not in ("$sum", "$avg", "$min", "$max", "$count"):
                return False
            acc_names.add(acc_name)
            val = acc_spec[op]
            if op == "$sum":
                if isinstance(val, dict):
                    return False
                if isinstance(val, str) and val.startswith("$"):
                    field = val[1:]
                    if "." in field:
                        return False
                    if _resolve_column(model, field) is None:
                        return False
            elif op in ("$avg", "$min", "$max"):
                if not isinstance(val, str) or not val.startswith("$"):
                    return False
                field = val[1:]
                if "." in field:
                    return False
                if _resolve_column(model, field) is None:
                    return False

        if sort_spec:
            for field in sort_spec.keys():
                if field in acc_names:
                    continue
                if field == "_id":
                    continue
                if field.startswith("_id.") and isinstance(group_key, dict):
                    sub = field[4:]
                    if sub in group_key:
                        continue
                return False

        return True

    @staticmethod
    def _is_simple_group_key(group_key):
        if group_key is None:
            return True
        if isinstance(group_key, str) and group_key.startswith("$"):
            return "." not in group_key
        if isinstance(group_key, dict):
            for alias, ref in group_key.items():
                if not isinstance(ref, str) or not ref.startswith("$"):
                    return False
                if "." in ref:
                    return False
            return True
        return False

    async def _execute_sql(self, match_filter, group_stage, sort_spec, limit_val):
        model = self._collection._model
        group_key = group_stage.get("_id")
        accumulators = {k: v for k, v in group_stage.items() if k != "_id"}

        group_columns = []
        group_labels = []

        if group_key is None:
            pass
        elif isinstance(group_key, str):
            field = group_key.lstrip("$")
            col = _resolve_column(model, field)
            if col is not None:
                group_columns.append(col)
                group_labels.append(("_id_single", field))
        elif isinstance(group_key, dict):
            for alias, ref in group_key.items():
                field = ref.lstrip("$")
                col = _resolve_column(model, field)
                if col is not None:
                    group_columns.append(col.label(f"_gk_{alias}"))
                    group_labels.append(("_id_dict", alias, field))

        select_cols = list(group_columns)
        acc_info = []
        acc_zero_default = set()

        for acc_name, acc_spec in accumulators.items():
            op = list(acc_spec.keys())[0]
            val = acc_spec[op]

            if op == "$sum":
                if isinstance(val, (int, float)):
                    if val == 0:
                        from sqlalchemy import literal
                        sql_expr = literal(0).label(acc_name)
                    elif val == 1:
                        sql_expr = func.count().label(acc_name)
                    else:
                        sql_expr = (func.count() * val).label(acc_name)
                elif isinstance(val, str) and val.startswith("$"):
                    field = val[1:]
                    col = _resolve_column(model, field)
                    sql_expr = func.coalesce(func.sum(col), 0).label(acc_name)
                else:
                    sql_expr = func.count().label(acc_name)
            elif op == "$avg":
                field = val[1:]
                col = _resolve_column(model, field)
                sql_expr = func.coalesce(func.avg(col), 0).label(acc_name)
            elif op == "$min":
                field = val[1:]
                col = _resolve_column(model, field)
                sql_expr = func.min(col).label(acc_name)
            elif op == "$max":
                field = val[1:]
                col = _resolve_column(model, field)
                sql_expr = func.max(col).label(acc_name)
            elif op == "$count":
                sql_expr = func.count().label(acc_name)
            else:
                continue

            select_cols.append(sql_expr)
            acc_info.append(acc_name)
            if op in ("$sum", "$count", "$avg"):
                acc_zero_default.add(acc_name)

        stmt = select(*select_cols).select_from(model)

        conds = _translate_filter(model, match_filter)
        if conds:
            stmt = stmt.where(and_(*conds))

        for gc in group_columns:
            base_col = gc.element if hasattr(gc, 'element') else gc
            stmt = stmt.group_by(base_col)

        if sort_spec:
            for field, direction in sort_spec.items():
                sort_col = None
                if field in acc_info:
                    for sc in select_cols:
                        label_name = getattr(sc, 'key', None) or getattr(sc, 'name', None)
                        if label_name == field:
                            sort_col = sc.element if hasattr(sc, 'element') else sc
                            break
                elif field == "_id" and group_columns:
                    sort_col = group_columns[0].element if hasattr(group_columns[0], 'element') else group_columns[0]
                elif field.startswith("_id.") and isinstance(group_key, dict):
                    sub_field = field[4:]
                    for gc in group_columns:
                        label_name = getattr(gc, 'key', None) or getattr(gc, 'name', None)
                        if label_name == f"_gk_{sub_field}":
                            sort_col = gc.element if hasattr(gc, 'element') else gc
                            break

                if sort_col is not None:
                    stmt = stmt.order_by(desc(sort_col) if direction == -1 else asc(sort_col))

        if limit_val:
            stmt = stmt.limit(limit_val)

        session, own = await self._collection._get_session()
        try:
            result = await session.execute(stmt)
            rows = result.all()
        finally:
            if own:
                await session.close()

        results = []
        for row in rows:
            doc = {}

            if group_key is None:
                doc["_id"] = None
            elif isinstance(group_key, str):
                doc["_id"] = row[0]
                row_offset = 1
            elif isinstance(group_key, dict):
                id_dict = {}
                for i, (_, alias, _field) in enumerate(group_labels):
                    val = row[i]
                    if hasattr(val, 'value'):
                        val = val.value
                    id_dict[alias] = val
                doc["_id"] = id_dict
                row_offset = len(group_labels)
            else:
                row_offset = 0

            if group_key is None:
                row_offset = 0

            for j, acc_name in enumerate(acc_info):
                val = row[row_offset + j]
                if val is not None:
                    if isinstance(val, float):
                        doc[acc_name] = val
                    else:
                        try:
                            doc[acc_name] = int(val) if float(val) == int(float(val)) else float(val)
                        except (ValueError, TypeError):
                            doc[acc_name] = val
                else:
                    doc[acc_name] = 0 if acc_name in acc_zero_default else None

            results.append(doc)

        return results

    async def _execute_count_stage(self, match_filter, count_field):
        if self._collection is None or self._collection._is_generic or self._collection._model is None:
            return None
        model = self._collection._model
        stmt = select(func.count().label("cnt")).select_from(model)
        conds = _translate_filter(model, match_filter)
        if conds:
            stmt = stmt.where(and_(*conds))
        session, own = await self._collection._get_session()
        try:
            result = await session.execute(stmt)
            row = result.one()
            return [{count_field: row.cnt}]
        finally:
            if own:
                await session.close()

    async def _execute(self):
        if self._results is not None:
            return self._results

        match_filter, group_stage, sort_spec, limit_val, project_stage, unwind_field, post_match, has_bucket, has_unknown_stage, count_stage_field = self._parse_pipeline()

        if count_stage_field and not group_stage and not unwind_field and not has_bucket and not has_unknown_stage:
            try:
                result = await self._execute_count_stage(match_filter, count_stage_field)
                if result is not None:
                    self._results = result
                    return self._results
            except Exception as e:
                logger.warning(f"SQL $count stage failed for {self._collection._name}, falling back to in-memory: {e}")

        if group_stage and self._can_translate_to_sql(group_stage, sort_spec, project_stage, unwind_field, post_match, has_bucket, has_unknown_stage):
            try:
                self._results = await self._execute_sql(match_filter, group_stage, sort_spec, limit_val)
                return self._results
            except Exception as e:
                logger.warning(f"SQL aggregation failed for {self._collection._name}, falling back to in-memory: {e}")

        cursor = self._collection.find(match_filter)
        all_docs = await cursor.to_list(50000)

        if group_stage:
            all_docs = self._apply_group(all_docs, group_stage)

        if post_match:
            all_docs = [d for d in all_docs if self._doc_matches(d, post_match)]

        if count_stage_field:
            all_docs = [{count_stage_field: len(all_docs)}]

        if sort_spec:
            for field, direction in reversed(list(sort_spec.items())):
                all_docs.sort(key=lambda d: d.get(field, 0) or 0, reverse=(direction == -1))

        if limit_val:
            all_docs = all_docs[:limit_val]

        if project_stage:
            all_docs = self._apply_project(all_docs, project_stage)

        self._results = all_docs
        return self._results

    def _apply_group(self, docs, group_spec):
        group_key = group_spec.get("_id")
        accumulators = {k: v for k, v in group_spec.items() if k != "_id"}

        groups = {}
        for doc in docs:
            if group_key is None:
                gk = None
            elif isinstance(group_key, str):
                field = group_key.lstrip("$")
                gk = self._get_nested(doc, field)
            elif isinstance(group_key, dict):
                gk_parts = {}
                for alias, ref in group_key.items():
                    if isinstance(ref, str) and ref.startswith("$"):
                        gk_parts[alias] = self._get_nested(doc, ref[1:])
                    else:
                        gk_parts[alias] = ref
                gk = tuple(sorted(gk_parts.items()))
            else:
                gk = group_key

            hashable_gk = str(gk) if not isinstance(gk, (str, int, float, bool, type(None), tuple)) else gk
            if hashable_gk not in groups:
                groups[hashable_gk] = {"_gk_raw": gk, "_docs": []}
            groups[hashable_gk]["_docs"].append(doc)

        results = []
        for _, group_data in groups.items():
            gk_raw = group_data["_gk_raw"]
            group_docs = group_data["_docs"]

            result_doc = {}
            if isinstance(gk_raw, tuple):
                result_doc["_id"] = dict(gk_raw)
            else:
                result_doc["_id"] = gk_raw

            for acc_name, acc_spec in accumulators.items():
                if isinstance(acc_spec, dict):
                    if "$sum" in acc_spec:
                        val = acc_spec["$sum"]
                        if val == 1:
                            result_doc[acc_name] = len(group_docs)
                        elif isinstance(val, str) and val.startswith("$"):
                            field = val[1:]
                            result_doc[acc_name] = sum(
                                self._get_nested(d, field, 0) or 0 for d in group_docs
                            )
                        elif isinstance(val, dict) and "$cond" in val:
                            total = 0
                            for d in group_docs:
                                total += self._eval_expr(val, d)
                            result_doc[acc_name] = total
                        elif isinstance(val, (int, float)):
                            result_doc[acc_name] = val * len(group_docs)
                        else:
                            result_doc[acc_name] = 0
                    elif "$first" in acc_spec:
                        field = acc_spec["$first"]
                        if isinstance(field, str) and field.startswith("$"):
                            result_doc[acc_name] = self._get_nested(group_docs[0], field[1:]) if group_docs else None
                        else:
                            result_doc[acc_name] = field
                    elif "$last" in acc_spec:
                        field = acc_spec["$last"]
                        if isinstance(field, str) and field.startswith("$"):
                            result_doc[acc_name] = self._get_nested(group_docs[-1], field[1:]) if group_docs else None
                        else:
                            result_doc[acc_name] = field
                    elif "$max" in acc_spec:
                        field = acc_spec["$max"]
                        if isinstance(field, str) and field.startswith("$"):
                            vals = [self._get_nested(d, field[1:]) for d in group_docs]
                            vals = [v for v in vals if v is not None]
                            result_doc[acc_name] = max(vals) if vals else None
                        else:
                            result_doc[acc_name] = field
                    elif "$min" in acc_spec:
                        field = acc_spec["$min"]
                        if isinstance(field, str) and field.startswith("$"):
                            vals = [self._get_nested(d, field[1:]) for d in group_docs]
                            vals = [v for v in vals if v is not None]
                            result_doc[acc_name] = min(vals) if vals else None
                        else:
                            result_doc[acc_name] = field
                    elif "$avg" in acc_spec:
                        field = acc_spec["$avg"]
                        if isinstance(field, str) and field.startswith("$"):
                            vals = [self._get_nested(d, field[1:]) for d in group_docs]
                            vals = [v for v in vals if v is not None]
                            result_doc[acc_name] = sum(vals) / len(vals) if vals else 0
                        else:
                            result_doc[acc_name] = field
                    elif "$push" in acc_spec:
                        field = acc_spec["$push"]
                        if isinstance(field, str) and field.startswith("$"):
                            result_doc[acc_name] = [self._get_nested(d, field[1:]) for d in group_docs]
                        elif field == "$$ROOT":
                            result_doc[acc_name] = group_docs
                        elif isinstance(field, dict):
                            pushed = []
                            for d in group_docs:
                                obj = {}
                                for fk, fv in field.items():
                                    if isinstance(fv, str) and fv.startswith("$"):
                                        obj[fk] = self._get_nested(d, fv[1:])
                                    else:
                                        obj[fk] = fv
                                pushed.append(obj)
                            result_doc[acc_name] = pushed
                        else:
                            result_doc[acc_name] = [field for _ in group_docs]
                    elif "$addToSet" in acc_spec:
                        field = acc_spec["$addToSet"]
                        if isinstance(field, str) and field.startswith("$"):
                            vals = [self._get_nested(d, field[1:]) for d in group_docs]
                            result_doc[acc_name] = list(set(v for v in vals if v is not None))
                        else:
                            result_doc[acc_name] = [field]
                    elif "$count" in acc_spec:
                        result_doc[acc_name] = len(group_docs)
                    else:
                        result_doc[acc_name] = None
                else:
                    result_doc[acc_name] = acc_spec

            results.append(result_doc)
        return results

    def _apply_project(self, docs, project_spec):
        has_exclusion = any(v == 0 for v in project_spec.values())
        has_inclusion = any(
            v == 1 or (isinstance(v, str) and v.startswith("$")) or isinstance(v, dict)
            for v in project_spec.values() if v != 0
        )
        result = []
        for doc in docs:
            if has_exclusion and not has_inclusion:
                r = dict(doc)
                for k, v in project_spec.items():
                    if v == 0:
                        r.pop(k, None)
                result.append(r)
            else:
                projected = {}
                for k, v in project_spec.items():
                    if v == 0:
                        continue
                    elif v == 1:
                        projected[k] = doc.get(k)
                    elif isinstance(v, str) and v.startswith("$"):
                        projected[k] = self._get_nested(doc, v[1:])
                    elif isinstance(v, dict):
                        projected[k] = self._eval_expr(v, doc)
                    else:
                        projected[k] = v
                result.append(projected)
        return result

    @staticmethod
    def _get_nested(doc, path, default=None):
        parts = path.split(".")
        current = doc
        for p in parts:
            if isinstance(current, dict):
                current = current.get(p, default)
            else:
                return default
        return current

    def _resolve_val(self, val, doc):
        if isinstance(val, str) and val.startswith("$"):
            return self._get_nested(doc, val[1:], 0)
        elif isinstance(val, dict):
            return self._eval_expr(val, doc)
        return val

    def _eval_expr(self, expr, doc):
        if not isinstance(expr, dict):
            if isinstance(expr, str) and expr.startswith("$"):
                return self._get_nested(doc, expr[1:])
            return expr

        if "$cond" in expr:
            cond_spec = expr["$cond"]
            if isinstance(cond_spec, list) and len(cond_spec) == 3:
                condition, true_val, false_val = cond_spec
                if self._eval_condition(condition, doc):
                    return self._resolve_val(true_val, doc)
                return self._resolve_val(false_val, doc)
            elif isinstance(cond_spec, dict):
                if self._eval_condition(cond_spec.get("if", {}), doc):
                    return self._resolve_val(cond_spec.get("then", 0), doc)
                return self._resolve_val(cond_spec.get("else", 0), doc)

        if "$multiply" in expr:
            parts = expr["$multiply"]
            result = 1
            for p in parts:
                v = self._resolve_val(p, doc)
                result *= (v if v is not None else 0)
            return result

        if "$divide" in expr:
            parts = expr["$divide"]
            if len(parts) == 2:
                numerator = self._resolve_val(parts[0], doc)
                denominator = self._resolve_val(parts[1], doc)
                if denominator:
                    return (numerator or 0) / denominator
                return 0

        if "$add" in expr:
            return sum(self._resolve_val(p, doc) or 0 for p in expr["$add"])

        if "$subtract" in expr:
            parts = expr["$subtract"]
            if len(parts) == 2:
                return (self._resolve_val(parts[0], doc) or 0) - (self._resolve_val(parts[1], doc) or 0)

        if "$slice" in expr:
            parts = expr["$slice"]
            if len(parts) == 2:
                arr = self._resolve_val(parts[0], doc)
                count = parts[1]
                if isinstance(arr, list):
                    return arr[:count]
                return []

        return doc.get(list(expr.keys())[0]) if expr else None

    def _eval_condition(self, condition, doc):
        if isinstance(condition, dict):
            if "$ne" in condition:
                parts = condition["$ne"]
                if len(parts) == 2:
                    a = self._resolve_val(parts[0], doc)
                    b = self._resolve_val(parts[1], doc)
                    return a != b
            if "$eq" in condition:
                parts = condition["$eq"]
                if len(parts) == 2:
                    a = self._resolve_val(parts[0], doc)
                    b = self._resolve_val(parts[1], doc)
                    return a == b
            if "$gt" in condition:
                parts = condition["$gt"]
                if len(parts) == 2:
                    a = self._resolve_val(parts[0], doc)
                    b = self._resolve_val(parts[1], doc)
                    return (a or 0) > (b or 0)
            if "$gte" in condition:
                parts = condition["$gte"]
                if len(parts) == 2:
                    a = self._resolve_val(parts[0], doc)
                    b = self._resolve_val(parts[1], doc)
                    return (a or 0) >= (b or 0)
            if "$and" in condition:
                return all(self._eval_condition(c, doc) for c in condition["$and"])
            if "$or" in condition:
                return any(self._eval_condition(c, doc) for c in condition["$or"])
        return bool(condition)

    @staticmethod
    def _doc_matches(doc, match_spec):
        for k, v in match_spec.items():
            val = doc.get(k)
            if isinstance(v, dict):
                for op, cmp_val in v.items():
                    if op == "$ne" and val == cmp_val:
                        return False
                    elif op == "$gt" and (val is None or val <= cmp_val):
                        return False
                    elif op == "$gte" and (val is None or val < cmp_val):
                        return False
                    elif op == "$lt" and (val is None or val >= cmp_val):
                        return False
                    elif op == "$in" and val not in cmp_val:
                        return False
                    elif op == "$exists":
                        if cmp_val and val is None:
                            return False
                        if not cmp_val and val is not None:
                            return False
            elif val != v:
                return False
        return True

    async def to_list(self, length=None):
        results = await self._execute()
        if length is not None:
            return results[:length]
        return results

    def __aiter__(self):
        self._iter_index = 0
        return self

    async def __anext__(self):
        results = await self._execute()
        if self._iter_index >= len(results):
            raise StopAsyncIteration
        doc = results[self._iter_index]
        self._iter_index += 1
        return doc


class PgCollection:
    def __init__(self, name: str, db_instance):
        self._name = name
        self._db = db_instance
        cmap = _get_collection_map()
        self._model = cmap.get(name)
        self._is_generic = self._model is None

    async def _get_session(self):
        session = self._db._get_session()
        if session is None:
            session = self._db.session_factory()
            return session, True
        return session, False

    async def find_one(self, filter_dict=None, projection=None, sort=None, options=None, **kwargs):
        session, own = await self._get_session()
        try:
            filter_dict = filter_dict or {}
            model = self._model
            is_generic = self._is_generic

            if is_generic:
                from pg_models import GenericDocument
                stmt = select(GenericDocument).where(
                    GenericDocument._collection == self._name
                )
                conds = _translate_filter(model, filter_dict, is_generic=True)
                if conds:
                    stmt = stmt.where(and_(*conds))
                if sort:
                    stmt = _apply_sort(stmt, model, sort, is_generic=True)
                stmt = stmt.limit(1)
                result = await session.execute(stmt)
                row = result.scalars().first()
                if row is None:
                    return None
                d = dict(row.data) if row.data else {}
                d["id"] = row.id
                d["_id"] = row.id
                return _apply_projection(d, projection) if projection else d
            else:
                stmt = select(model)
                if options:
                    for opt in options:
                        stmt = stmt.options(opt)
                conds = _translate_filter(model, filter_dict)
                if conds:
                    stmt = stmt.where(and_(*conds))
                if sort:
                    stmt = _apply_sort(stmt, model, sort)
                stmt = stmt.limit(1)
                result = await session.execute(stmt)
                row = result.scalars().first()
                if row is None:
                    return None
                d = _orm_to_dict(row)
                return _apply_projection(d, projection) if projection else d
        finally:
            if own:
                await session.close()

    def find(self, filter_dict=None, projection=None, options=None, **kwargs):
        return PgCursor(self, filter_dict, projection, options=options)

    async def insert_one(self, document: dict):
        session, own = await self._get_session()
        try:
            doc = dict(document)
            doc.pop("_id", None)
            if "id" not in doc or not doc["id"]:
                doc["id"] = _gen_id()
            doc_id = doc["id"]

            if self._is_generic:
                from pg_models import GenericDocument
                obj = GenericDocument(
                    id=doc_id,
                    _collection=self._name,
                    data=doc,
                )
                session.add(obj)
            else:
                model = self._model
                obj = model()
                mapper = inspect(model)
                col_keys = {c.key for c in mapper.columns}
                extra_fields = {}
                for k, v in doc.items():
                    if k in col_keys:
                        setattr(obj, k, _coerce_value_for_column(model, k, v))
                    elif COLUMN_ALIASES.get(k) in col_keys:
                        alias = COLUMN_ALIASES[k]
                        setattr(obj, alias, _coerce_value_for_column(model, alias, v))
                    else:
                        extra_fields[k] = v
                if extra_fields and "data" in col_keys:
                    existing_data = getattr(obj, "data", None) or {}
                    if isinstance(existing_data, dict):
                        merged = {**existing_data, **extra_fields}
                    else:
                        merged = extra_fields
                    setattr(obj, "data", merged)
                session.add(obj)

            await session.flush()
            if own:
                await session.commit()
            return InsertOneResult(doc_id)
        except Exception as e:
            if own:
                await session.rollback()
            else:
                try:
                    await session.rollback()
                except Exception:
                    pass
            from sqlalchemy.exc import IntegrityError
            if isinstance(e, IntegrityError):
                detail = str(e.orig) if hasattr(e, 'orig') else str(e)
                if "unique" in detail.lower() or "duplicate" in detail.lower():
                    raise DuplicateKeyError(f"Duplicate key in {self._name}: {detail}")
                raise ValueError(f"Integrity error in {self._name}: {detail}")
            raise
        finally:
            if own:
                await session.close()

    async def insert_many(self, documents: list):
        results = []
        for doc in documents:
            r = await self.insert_one(doc)
            results.append(r.inserted_id)
        return type("InsertManyResult", (), {"inserted_ids": results})()

    def _can_use_statement_update(self, update_dict):
        push_fields = update_dict.get("$push", {})
        pull_fields = update_dict.get("$pull", {})
        add_to_set_fields = update_dict.get("$addToSet", {})
        return not any([push_fields, pull_fields, add_to_set_fields])

    def _build_update_values(self, model, update_dict):
        set_fields = update_dict.get("$set", {})
        unset_fields = update_dict.get("$unset", {})
        inc_fields = update_dict.get("$inc", {})
        max_fields = update_dict.get("$max", {})

        if not any([set_fields, unset_fields, inc_fields]):
            if not any(k.startswith("$") for k in update_dict):
                set_fields = update_dict

        mapper = inspect(model)
        col_keys = {c.key for c in mapper.columns}
        values = {}
        has_extra = False
        for k, v in set_fields.items():
            if k == "_id":
                continue
            resolved_key = k
            if k not in col_keys and COLUMN_ALIASES.get(k) in col_keys:
                resolved_key = COLUMN_ALIASES[k]
            if resolved_key in col_keys:
                if "." in k:
                    continue
                values[resolved_key] = _coerce_value_for_column(model, resolved_key, v)
            elif "." not in k:
                has_extra = True
        for k in unset_fields:
            if k == "_id":
                continue
            resolved_key = k
            if k not in col_keys and COLUMN_ALIASES.get(k) in col_keys:
                resolved_key = COLUMN_ALIASES[k]
            if resolved_key in col_keys:
                values[resolved_key] = None
        for k, v in inc_fields.items():
            resolved_key = k
            if k not in col_keys and COLUMN_ALIASES.get(k) in col_keys:
                resolved_key = COLUMN_ALIASES[k]
            if resolved_key in col_keys:
                col_obj = getattr(model, resolved_key)
                values[resolved_key] = func.coalesce(col_obj, 0) + v
        from sqlalchemy import case as sa_case, literal
        for k, v in max_fields.items():
            resolved_key = k
            if k not in col_keys and COLUMN_ALIASES.get(k) in col_keys:
                resolved_key = COLUMN_ALIASES[k]
            if resolved_key in col_keys:
                col_obj = getattr(model, resolved_key)
                values[resolved_key] = sa_case(
                    (col_obj.is_(None), literal(v)),
                    else_=func.greatest(col_obj, v)
                )
        return values, set_fields, has_extra

    def _has_dotted_set(self, set_fields):
        return any("." in k for k in set_fields)

    async def update_one(self, filter_dict: dict, update_dict: dict, upsert=False):
        session, own = await self._get_session()
        try:
            set_fields = update_dict.get("$set", {})
            unset_fields = update_dict.get("$unset", {})
            inc_fields = update_dict.get("$inc", {})
            push_fields = update_dict.get("$push", {})
            pull_fields = update_dict.get("$pull", {})
            max_fields = update_dict.get("$max", {})
            add_to_set_fields = update_dict.get("$addToSet", {})
            set_on_insert_fields = update_dict.get("$setOnInsert", {})

            if not any([set_fields, unset_fields, inc_fields, push_fields, pull_fields, max_fields, add_to_set_fields, set_on_insert_fields]):
                if not any(k.startswith("$") for k in update_dict):
                    set_fields = update_dict

            if self._is_generic:
                from pg_models import GenericDocument
                stmt = select(GenericDocument).where(
                    GenericDocument._collection == self._name
                )
                conds = _translate_filter(None, filter_dict, is_generic=True)
                if conds:
                    stmt = stmt.where(and_(*conds))
                stmt = stmt.limit(1)
                result = await session.execute(stmt)
                row = result.scalars().first()
                if row is None:
                    if upsert:
                        doc = {**filter_dict, **set_on_insert_fields, **set_fields}
                        doc.pop("$or", None)
                        doc.pop("$and", None)
                        await self.insert_one(doc)
                        return UpdateResult(1, 1, upserted=True)
                    return UpdateResult(0, 0)
                data = dict(row.data) if row.data else {}
                data.update(set_fields)
                for k in unset_fields:
                    data.pop(k, None)
                for k, v in inc_fields.items():
                    data[k] = (data.get(k, 0) or 0) + v
                for k, v in push_fields.items():
                    arr = data.get(k, [])
                    if isinstance(arr, list):
                        arr.append(v)
                        data[k] = arr
                for k, v in pull_fields.items():
                    arr = data.get(k, [])
                    if isinstance(arr, list):
                        data[k] = [x for x in arr if x != v]
                for k, v in max_fields.items():
                    current = data.get(k, 0) or 0
                    data[k] = max(current, v)
                for k, v in add_to_set_fields.items():
                    arr = data.get(k, [])
                    if isinstance(arr, list):
                        if v not in arr:
                            arr.append(v)
                        data[k] = arr
                row.data = data
                await session.flush()
                if own:
                    await session.commit()
                return UpdateResult(1, 1)
            else:
                model = self._model
                can_statement = self._can_use_statement_update(update_dict) and not self._has_dotted_set(set_fields)

                if can_statement and not upsert:
                    values, _, has_extra = self._build_update_values(model, update_dict)
                    if values and not has_extra:
                        conds = _translate_filter(model, filter_dict)
                        id_subq = select(model.id)
                        if conds:
                            id_subq = id_subq.where(and_(*conds))
                        id_subq = id_subq.limit(1).scalar_subquery()
                        stmt = sa_update(model.__table__).where(model.id == id_subq).values(**values)
                        result = await session.execute(stmt)
                        if own:
                            await session.commit()
                        count = result.rowcount
                        return UpdateResult(count, count)

                stmt = select(model)
                conds = _translate_filter(model, filter_dict)
                if conds:
                    stmt = stmt.where(and_(*conds))
                stmt = stmt.limit(1)
                result = await session.execute(stmt)
                row = result.scalars().first()
                if row is None:
                    if upsert:
                        doc = {}
                        for k, v in filter_dict.items():
                            if not k.startswith("$") and not isinstance(v, dict):
                                doc[k] = v
                        doc.update(set_on_insert_fields)
                        doc.update(set_fields)
                        await self.insert_one(doc)
                        return UpdateResult(1, 1, upserted=True)
                    return UpdateResult(0, 0)
                mapper = inspect(model)
                col_keys = {c.key for c in mapper.columns}
                extra_set = {}
                for k, v in set_fields.items():
                    if k == "_id":
                        continue
                    if "." in k:
                        parts = k.split(".", 1)
                        parent_key = parts[0]
                        if parent_key in col_keys:
                            current = getattr(row, parent_key, None)
                            if isinstance(current, dict):
                                current = dict(current)
                                current[parts[1]] = v
                                setattr(row, parent_key, current)
                            elif current is None:
                                setattr(row, parent_key, {parts[1]: v})
                        continue
                    if k in col_keys:
                        setattr(row, k, _coerce_value_for_column(model, k, v))
                    elif COLUMN_ALIASES.get(k) in col_keys:
                        alias = COLUMN_ALIASES[k]
                        setattr(row, alias, _coerce_value_for_column(model, alias, v))
                    else:
                        extra_set[k] = v
                if extra_set and "data" in col_keys:
                    current_data = getattr(row, "data", None)
                    current_data = dict(current_data) if isinstance(current_data, dict) else {}
                    current_data.update(extra_set)
                    setattr(row, "data", current_data)
                for k in unset_fields:
                    if k == "_id":
                        continue
                    if k in col_keys:
                        setattr(row, k, None)
                for k, v in inc_fields.items():
                    if k in col_keys:
                        current = getattr(row, k, 0) or 0
                        setattr(row, k, current + v)
                for k, v in push_fields.items():
                    if k in col_keys:
                        current = getattr(row, k) or []
                        if isinstance(current, list):
                            current = list(current)
                            current.append(v)
                            setattr(row, k, current)
                for k, v in pull_fields.items():
                    if k in col_keys:
                        current = getattr(row, k) or []
                        if isinstance(current, list):
                            setattr(row, k, [x for x in current if x != v])
                for k, v in max_fields.items():
                    if k in col_keys:
                        current = getattr(row, k, 0) or 0
                        setattr(row, k, max(current, v))
                for k, v in add_to_set_fields.items():
                    if k in col_keys:
                        current = getattr(row, k) or []
                        if isinstance(current, list):
                            current = list(current)
                            if v not in current:
                                current.append(v)
                            setattr(row, k, current)
                await session.flush()
                if own:
                    await session.commit()
                return UpdateResult(1, 1)
        except Exception:
            if own:
                await session.rollback()
            raise
        finally:
            if own:
                await session.close()

    async def update_many(self, filter_dict: dict, update_dict: dict):
        session, own = await self._get_session()
        try:
            set_fields = update_dict.get("$set", {})
            unset_fields = update_dict.get("$unset", {})
            inc_fields = update_dict.get("$inc", {})

            if not any([set_fields, unset_fields, inc_fields]):
                if not any(k.startswith("$") for k in update_dict):
                    set_fields = update_dict

            if self._is_generic:
                from pg_models import GenericDocument
                stmt = select(GenericDocument).where(
                    GenericDocument._collection == self._name
                )
                conds = _translate_filter(None, filter_dict, is_generic=True)
                if conds:
                    stmt = stmt.where(and_(*conds))
                result = await session.execute(stmt)
                rows = result.scalars().all()
                for row in rows:
                    data = dict(row.data) if row.data else {}
                    data.update(set_fields)
                    for k in unset_fields:
                        data.pop(k, None)
                    for k, v in inc_fields.items():
                        data[k] = (data.get(k, 0) or 0) + v
                    row.data = data
                await session.flush()
                if own:
                    await session.commit()
                return UpdateResult(len(rows), len(rows))
            else:
                model = self._model
                has_unsupported = any(update_dict.get(op) for op in ("$push", "$pull", "$addToSet"))
                can_statement = not has_unsupported and not self._has_dotted_set(set_fields)

                if can_statement:
                    values, _, has_extra = self._build_update_values(model, update_dict)
                    if values and not has_extra:
                        conds = _translate_filter(model, filter_dict)
                        stmt = sa_update(model.__table__)
                        if conds:
                            stmt = stmt.where(and_(*conds))
                        stmt = stmt.values(**values)
                        result = await session.execute(stmt)
                        if own:
                            await session.commit()
                        count = result.rowcount
                        return UpdateResult(count, count)

                stmt = select(model)
                conds = _translate_filter(model, filter_dict)
                if conds:
                    stmt = stmt.where(and_(*conds))
                result = await session.execute(stmt)
                rows = result.scalars().all()
                mapper = inspect(model)
                col_keys = {c.key for c in mapper.columns}
                for row in rows:
                    for k, v in set_fields.items():
                        if k == "_id":
                            continue
                        if k in col_keys:
                            setattr(row, k, _coerce_value_for_column(model, k, v))
                        elif COLUMN_ALIASES.get(k) in col_keys:
                            alias = COLUMN_ALIASES[k]
                            setattr(row, alias, _coerce_value_for_column(model, alias, v))
                    for k in unset_fields:
                        if k == "_id":
                            continue
                        if k in col_keys:
                            setattr(row, k, None)
                    for k, v in inc_fields.items():
                        if k in col_keys:
                            current = getattr(row, k, 0) or 0
                            setattr(row, k, current + v)
                await session.flush()
                if own:
                    await session.commit()
                return UpdateResult(len(rows), len(rows))
        except Exception:
            if own:
                await session.rollback()
            raise
        finally:
            if own:
                await session.close()

    async def delete_one(self, filter_dict: dict):
        session, own = await self._get_session()
        try:
            if self._is_generic:
                from pg_models import GenericDocument
                stmt = select(GenericDocument).where(
                    GenericDocument._collection == self._name
                )
                conds = _translate_filter(None, filter_dict, is_generic=True)
                if conds:
                    stmt = stmt.where(and_(*conds))
                stmt = stmt.limit(1)
                result = await session.execute(stmt)
                row = result.scalars().first()
                if row:
                    await session.delete(row)
                    await session.flush()
                    if own:
                        await session.commit()
                    return DeleteResult(1)
                return DeleteResult(0)
            else:
                model = self._model
                stmt = select(model)
                conds = _translate_filter(model, filter_dict)
                if conds:
                    stmt = stmt.where(and_(*conds))
                stmt = stmt.limit(1)
                result = await session.execute(stmt)
                row = result.scalars().first()
                if row:
                    await session.delete(row)
                    await session.flush()
                    if own:
                        await session.commit()
                    return DeleteResult(1)
                return DeleteResult(0)
        except Exception:
            if own:
                await session.rollback()
            raise
        finally:
            if own:
                await session.close()

    async def delete_many(self, filter_dict: dict):
        session, own = await self._get_session()
        try:
            if self._is_generic:
                from pg_models import GenericDocument
                stmt = select(GenericDocument).where(
                    GenericDocument._collection == self._name
                )
                conds = _translate_filter(None, filter_dict, is_generic=True)
                if conds:
                    stmt = stmt.where(and_(*conds))
                result = await session.execute(stmt)
                rows = result.scalars().all()
                for row in rows:
                    await session.delete(row)
                await session.flush()
                if own:
                    await session.commit()
                return DeleteResult(len(rows))
            else:
                model = self._model
                stmt = select(model)
                conds = _translate_filter(model, filter_dict)
                if conds:
                    stmt = stmt.where(and_(*conds))
                result = await session.execute(stmt)
                rows = result.scalars().all()
                for row in rows:
                    await session.delete(row)
                await session.flush()
                if own:
                    await session.commit()
                return DeleteResult(len(rows))
        except Exception:
            if own:
                await session.rollback()
            raise
        finally:
            if own:
                await session.close()

    async def batched_counts(self, filters: dict):
        if not filters:
            return {}
        session, own = await self._get_session()
        try:
            if self._is_generic:
                from pg_models import GenericDocument
                cols = []
                keys = list(filters.keys())
                for key in keys:
                    f = filters[key]
                    conds = _translate_filter(None, f, is_generic=True) if f else []
                    base_cond = GenericDocument._collection == self._name
                    if conds:
                        cols.append(func.count().filter(and_(base_cond, *conds)).label(key))
                    else:
                        cols.append(func.count().filter(base_cond).label(key))
                stmt = select(*cols).select_from(GenericDocument)
            else:
                model = self._model
                cols = []
                keys = list(filters.keys())
                for key in keys:
                    f = filters[key]
                    conds = _translate_filter(model, f) if f else []
                    if conds:
                        cols.append(func.count().filter(and_(*conds)).label(key))
                    else:
                        cols.append(func.count().label(key))
                stmt = select(*cols).select_from(model)
            result = await session.execute(stmt)
            row = result.one()
            return {keys[i]: row[i] or 0 for i in range(len(keys))}
        finally:
            if own:
                await session.close()

    async def count_documents(self, filter_dict=None):
        filter_dict = filter_dict or {}
        if _has_expr_filter(filter_dict):
            docs = await self.find(filter_dict).to_list(100000)
            expr = filter_dict.get("$expr")
            docs = _apply_expr_filter(docs, expr)
            return len(docs)
        session, own = await self._get_session()
        try:
            if self._is_generic:
                from pg_models import GenericDocument
                stmt = select(func.count()).select_from(GenericDocument).where(
                    GenericDocument._collection == self._name
                )
                conds = _translate_filter(None, filter_dict, is_generic=True)
                if conds:
                    stmt = stmt.where(and_(*conds))
            else:
                model = self._model
                stmt = select(func.count()).select_from(model)
                conds = _translate_filter(model, filter_dict)
                if conds:
                    stmt = stmt.where(and_(*conds))
            result = await session.execute(stmt)
            return result.scalar() or 0
        finally:
            if own:
                await session.close()

    async def distinct(self, field: str, filter_dict=None):
        session, own = await self._get_session()
        try:
            filter_dict = filter_dict or {}
            if self._is_generic:
                from pg_models import GenericDocument
                stmt = select(GenericDocument.data[field].astext).distinct().where(
                    GenericDocument._collection == self._name
                )
                conds = _translate_filter(None, filter_dict, is_generic=True)
                if conds:
                    stmt = stmt.where(and_(*conds))
            else:
                col = _resolve_column(self._model, field)
                if col is None:
                    return []
                stmt = select(col).distinct()
                conds = _translate_filter(self._model, filter_dict)
                if conds:
                    stmt = stmt.where(and_(*conds))
            result = await session.execute(stmt)
            return [r[0] for r in result.fetchall() if r[0] is not None]
        finally:
            if own:
                await session.close()

    def aggregate(self, pipeline: list):
        return AggregationCursor(self, pipeline)

    async def find_one_and_update(self, filter_dict: dict, update_dict: dict,
                                  return_document=None, upsert=False, projection=None):
        if not self._is_generic and self._can_use_statement_update(update_dict):
            set_fields = update_dict.get("$set", {})
            if not self._has_dotted_set(set_fields):
                if return_document:
                    session, own = await self._get_session()
                    try:
                        model = self._model
                        values, _, has_extra = self._build_update_values(model, update_dict)
                        conds = _translate_filter(model, filter_dict)
                        if values and not has_extra:
                            id_subq = select(model.id)
                            if conds:
                                id_subq = id_subq.where(and_(*conds))
                            id_subq = id_subq.limit(1).scalar_subquery()
                            stmt = sa_update(model.__table__).where(model.id == id_subq).values(**values).returning(*model.__table__.columns)
                            result = await session.execute(stmt)
                            row = result.fetchone()
                            if row is None:
                                if upsert:
                                    doc = {}
                                    for k, v in filter_dict.items():
                                        if not k.startswith("$") and not isinstance(v, dict):
                                            doc[k] = v
                                    soi = update_dict.get("$setOnInsert", {})
                                    doc.update(soi)
                                    doc.update(set_fields)
                                    await self.insert_one(doc)
                                    return await self.find_one(filter_dict, projection)
                                return None
                            if own:
                                await session.commit()
                            d = dict(row._mapping)
                            d.pop("_id", None)
                            return _apply_projection(d, projection) if projection else d
                        else:
                            return await self.find_one(filter_dict, projection)
                    except Exception:
                        if own:
                            await session.rollback()
                        raise
                    finally:
                        if own:
                            await session.close()

        old_doc = await self.find_one(filter_dict, projection)
        await self.update_one(filter_dict, update_dict, upsert=upsert)
        if return_document:
            return await self.find_one(filter_dict, projection)
        return old_doc

    async def bulk_write(self, operations, ordered=True):
        from bson_compat import UpdateOne as _UpdateOne
        modified = 0
        upserted = 0
        matched = 0
        for op in operations:
            if isinstance(op, _UpdateOne):
                result = await self.update_one(op.filter, op.update, upsert=op.upsert)
                modified += result.modified_count
                matched += result.matched_count
                upserted += result.upserted_count
        return type("BulkWriteResult", (), {
            "modified_count": modified,
            "matched_count": matched,
            "upserted_count": upserted,
        })()

    async def create_index(self, *args, **kwargs):
        pass

    async def drop(self):
        session, own = await self._get_session()
        try:
            if self._is_generic:
                from pg_models import GenericDocument
                stmt = sa_delete(GenericDocument).where(
                    GenericDocument._collection == self._name
                )
            else:
                stmt = sa_delete(self._model)
            await session.execute(stmt)
            await session.flush()
            if own:
                await session.commit()
        except Exception:
            if own:
                await session.rollback()
            raise
        finally:
            if own:
                await session.close()


class PgDatabase:
    def __init__(self, sf=None):
        self.session_factory = sf or async_session_factory
        self._collections: dict = {}

    def set_session(self, session: Optional[AsyncSession]):
        _pg_session_var.set(session)

    def _get_session(self) -> Optional[AsyncSession]:
        return _pg_session_var.get()

    def __getattr__(self, name: str):
        if name.startswith("_") or name in ("session_factory", "set_session"):
            raise AttributeError(name)
        if name not in self._collections:
            self._collections[name] = PgCollection(name, self)
        return self._collections[name]

    def get_collection(self, name: str):
        return getattr(self, name)


pg_db = PgDatabase()
