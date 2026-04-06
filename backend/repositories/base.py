import uuid
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type

from sqlalchemy import select, func, and_, or_, desc, asc, delete as sa_delete, update as sa_update, inspect as sa_inspect, text, case as sa_case, literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import DateTime as SADateTime
from sqlalchemy.orm import joinedload, selectinload
from dateutil import parser as dateutil_parser

from db import Base

logger = logging.getLogger("nassaq.repo")

COLUMN_ALIASES = {
    "tenant_id": "school_id",
    "school_id": "tenant_id",
}


def _gen_id() -> str:
    return str(uuid.uuid4())


def _utcnow():
    return datetime.now(timezone.utc)


def _coerce_dt(model_cls, key, value):
    if value is None or model_cls is None:
        return value
    mapper = sa_inspect(model_cls)
    col = mapper.columns.get(key)
    if col is not None and isinstance(col.type, SADateTime) and isinstance(value, str):
        try:
            return dateutil_parser.isoparse(value)
        except (ValueError, TypeError):
            return value
    return value


def _resolve_col(model_cls, key):
    mapper = sa_inspect(model_cls)
    if key in {c.key for c in mapper.columns}:
        return getattr(model_cls, key)
    alias = COLUMN_ALIASES.get(key)
    if alias and alias in {c.key for c in mapper.columns}:
        return getattr(model_cls, alias)
    return None


def _col_keys(model_cls):
    mapper = sa_inspect(model_cls)
    return {c.key for c in mapper.columns}


def _to_dict(obj) -> Optional[dict]:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    d = {}
    mapper = sa_inspect(type(obj))
    data_val = None
    has_data_col = False
    for col in mapper.columns:
        val = getattr(obj, col.key, None)
        if isinstance(val, datetime):
            val = val.isoformat()
        if col.key == "data":
            has_data_col = True
            if isinstance(val, dict):
                data_val = val
        d[col.key] = val
    if has_data_col and data_val:
        for k, v in data_val.items():
            if k not in d:
                d[k] = v
    if "id" in d:
        d["_id"] = d["id"]
    return d


def _build_conditions(model_cls, filters: dict):
    if not filters:
        return []
    conditions = []
    for key, value in filters.items():
        if key == "$or":
            or_parts = []
            for sub in value:
                sub_conds = _build_conditions(model_cls, sub)
                if sub_conds:
                    or_parts.append(and_(*sub_conds) if len(sub_conds) > 1 else sub_conds[0])
            if or_parts:
                conditions.append(or_(*or_parts))
            continue
        if key == "$and":
            for sub in value:
                conditions.extend(_build_conditions(model_cls, sub))
            continue
        if key.startswith("$"):
            continue

        if key == "_id":
            key = "id"

        if "." in key:
            parts = key.split(".", 1)
            parent_col = _resolve_col(model_cls, parts[0])
            if parent_col is not None:
                prop = getattr(parent_col, 'property', None)
                if prop:
                    col_type = getattr(prop.columns[0], 'type', None)
                    if isinstance(col_type, JSONB):
                        jsonb_path = parent_col[parts[1]]
                        if isinstance(value, dict):
                            for op, val in value.items():
                                if op == "$exists":
                                    conditions.append(jsonb_path.isnot(None) if val else jsonb_path.is_(None))
                                elif op == "$ne":
                                    conditions.append(jsonb_path.astext != str(val) if val is not None else jsonb_path.isnot(None))
                                elif op == "$in":
                                    conditions.append(jsonb_path.astext.in_([str(v) for v in val]))
                        else:
                            conditions.append(jsonb_path.astext == str(value))
            continue

        col = _resolve_col(model_cls, key)
        if col is None:
            continue

        if isinstance(value, dict):
            for op, val in value.items():
                cv = lambda v, k=key: _coerce_dt(model_cls, k, v)
                if op == "$in":
                    conditions.append(col.in_([cv(v) for v in val]))
                elif op == "$nin":
                    conditions.append(~col.in_([cv(v) for v in val]))
                elif op == "$ne":
                    conditions.append(col != cv(val))
                elif op == "$gte":
                    conditions.append(col >= cv(val))
                elif op == "$gt":
                    conditions.append(col > cv(val))
                elif op == "$lt":
                    conditions.append(col < cv(val))
                elif op == "$lte":
                    conditions.append(col <= cv(val))
                elif op == "$exists":
                    conditions.append(col.isnot(None) if val else col.is_(None))
                elif op == "$regex":
                    flags = value.get("$options", "")
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
                    if isinstance(val, dict):
                        for iop, ival in val.items():
                            if iop == "$regex":
                                iflags = val.get("$options", "")
                                ipat = ival.replace("%", r"\%").replace("_", r"\_")
                                if ipat.startswith("^"):
                                    ipat = ipat[1:]
                                like_p = f"{ipat}%"
                                if "i" in iflags:
                                    conditions.append(~col.ilike(like_p))
                                else:
                                    conditions.append(~col.like(like_p))
        elif isinstance(value, list):
            conditions.append(col.in_(value))
        elif value is None:
            conditions.append(col.is_(None))
        else:
            conditions.append(col == _coerce_dt(model_cls, key, value))
    return conditions


def _apply_sort(stmt, model_cls, sort_spec):
    if sort_spec is None:
        return stmt
    if isinstance(sort_spec, list):
        for field, direction in sort_spec:
            col = _resolve_col(model_cls, field)
            if col is None:
                continue
            stmt = stmt.order_by(desc(col) if direction == -1 else asc(col))
    elif isinstance(sort_spec, str):
        col = _resolve_col(model_cls, sort_spec)
        if col is not None:
            stmt = stmt.order_by(desc(col))
    return stmt


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


class UpdateOne:
    def __init__(self, filter_dict, update_dict, upsert=False):
        self.filter = filter_dict
        self.update = update_dict
        self.upsert = upsert


class RepoCursor:
    def __init__(self, repo, filter_dict, projection=None, options=None):
        self._repo = repo
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
        model = self._repo.model
        session = self._repo.session
        stmt = select(model)
        if self._options:
            for opt in self._options:
                stmt = stmt.options(opt)
        conds = _build_conditions(model, self._filter)
        if conds:
            stmt = stmt.where(and_(*conds))
        if self._sort_spec:
            stmt = _apply_sort(stmt, model, self._sort_spec)
        if self._skip_val:
            stmt = stmt.offset(self._skip_val)
        if self._limit_val:
            stmt = stmt.limit(self._limit_val)
        result = await session.execute(stmt)
        rows = result.scalars().all()
        docs = [_to_dict(r) for r in rows]
        if self._projection:
            docs = [_apply_projection(d, self._projection) for d in docs]
        self._results = docs
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


def _apply_projection(doc: dict, projection: dict) -> dict:
    if not projection or not doc:
        return doc
    exclude_id = projection.get("_id") == 0
    proj = {k: v for k, v in projection.items() if k != "_id"}
    includes = {k for k, v in proj.items() if v}
    excludes = {k for k, v in proj.items() if not v}
    if includes:
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


class AggregationCursor:
    def __init__(self, repo, pipeline: list):
        self._repo = repo
        self._pipeline = pipeline

    async def to_list(self, length=None):
        if self._repo is None:
            return []
        model = self._repo.model
        session = self._repo.session

        match_stage = {}
        group_stage = None
        sort_stage = None
        limit_stage = None
        skip_stage = None
        project_stage = None
        unwind_stage = None
        add_fields_stage = None

        for stage in self._pipeline:
            if "$match" in stage:
                match_stage.update(stage["$match"])
            elif "$group" in stage:
                group_stage = stage["$group"]
            elif "$sort" in stage:
                sort_stage = stage["$sort"]
            elif "$limit" in stage:
                limit_stage = stage["$limit"]
            elif "$skip" in stage:
                skip_stage = stage["$skip"]
            elif "$project" in stage:
                project_stage = stage["$project"]
            elif "$unwind" in stage:
                unwind_stage = stage["$unwind"]
            elif "$addFields" in stage:
                add_fields_stage = stage["$addFields"]

        if group_stage:
            return await self._handle_group(model, session, match_stage, group_stage, sort_stage, limit_stage, project_stage)

        stmt = select(model)
        conds = _build_conditions(model, match_stage)
        if conds:
            stmt = stmt.where(and_(*conds))
        if sort_stage:
            for field, direction in sort_stage.items():
                col = _resolve_col(model, field)
                if col is not None:
                    stmt = stmt.order_by(desc(col) if direction == -1 else asc(col))
        if skip_stage:
            stmt = stmt.offset(skip_stage)
        if limit_stage:
            stmt = stmt.limit(limit_stage)
        result = await session.execute(stmt)
        rows = result.scalars().all()
        docs = [_to_dict(r) for r in rows]
        if project_stage:
            docs = [_apply_projection(d, project_stage) for d in docs]
        if length is not None:
            return docs[:length]
        return docs

    async def _handle_group(self, model, session, match, group, sort_stage, limit_stage, project_stage):
        group_id = group.get("_id")
        cols = []
        labels = {}

        if group_id is None:
            pass
        elif isinstance(group_id, str) and group_id.startswith("$"):
            field = group_id[1:]
            col = _resolve_col(model, field)
            if col is not None:
                cols.append(col.label("_id"))
        elif isinstance(group_id, dict):
            for alias, expr in group_id.items():
                if isinstance(expr, str) and expr.startswith("$"):
                    field = expr[1:]
                    col = _resolve_col(model, field)
                    if col is not None:
                        cols.append(col.label(alias))

        for key, expr in group.items():
            if key == "_id":
                continue
            if isinstance(expr, dict):
                if "$sum" in expr:
                    val = expr["$sum"]
                    if val == 1:
                        cols.append(func.count().label(key))
                    elif isinstance(val, str) and val.startswith("$"):
                        field = val[1:]
                        col = _resolve_col(model, field)
                        if col is not None:
                            cols.append(func.sum(func.coalesce(col, 0)).label(key))
                elif "$avg" in expr:
                    val = expr["$avg"]
                    if isinstance(val, str) and val.startswith("$"):
                        field = val[1:]
                        col = _resolve_col(model, field)
                        if col is not None:
                            cols.append(func.avg(col).label(key))
                elif "$min" in expr:
                    val = expr["$min"]
                    if isinstance(val, str) and val.startswith("$"):
                        field = val[1:]
                        col = _resolve_col(model, field)
                        if col is not None:
                            cols.append(func.min(col).label(key))
                elif "$max" in expr:
                    val = expr["$max"]
                    if isinstance(val, str) and val.startswith("$"):
                        field = val[1:]
                        col = _resolve_col(model, field)
                        if col is not None:
                            cols.append(func.max(col).label(key))
                elif "$first" in expr:
                    val = expr["$first"]
                    if isinstance(val, str) and val.startswith("$"):
                        field = val[1:]
                        col = _resolve_col(model, field)
                        if col is not None:
                            cols.append(col.label(key))
                elif "$push" in expr:
                    val = expr["$push"]
                    if isinstance(val, str) and val.startswith("$"):
                        field = val[1:]
                        col = _resolve_col(model, field)
                        if col is not None:
                            cols.append(func.array_agg(col).label(key))
                elif "$addToSet" in expr:
                    val = expr["$addToSet"]
                    if isinstance(val, str) and val.startswith("$"):
                        field = val[1:]
                        col = _resolve_col(model, field)
                        if col is not None:
                            cols.append(func.array_agg(func.distinct(col)).label(key))
                elif "$count" in expr:
                    cols.append(func.count().label(key))

        if not cols:
            return []

        stmt = select(*cols).select_from(model)
        conds = _build_conditions(model, match)
        if conds:
            stmt = stmt.where(and_(*conds))

        group_cols = []
        if group_id is None:
            pass
        elif isinstance(group_id, str) and group_id.startswith("$"):
            field = group_id[1:]
            col = _resolve_col(model, field)
            if col is not None:
                group_cols.append(col)
        elif isinstance(group_id, dict):
            for alias, expr in group_id.items():
                if isinstance(expr, str) and expr.startswith("$"):
                    field = expr[1:]
                    col = _resolve_col(model, field)
                    if col is not None:
                        group_cols.append(col)

        if group_cols:
            stmt = stmt.group_by(*group_cols)

        if sort_stage:
            for field, direction in sort_stage.items():
                col = _resolve_col(model, field)
                if col is not None:
                    stmt = stmt.order_by(desc(col) if direction == -1 else asc(col))
                else:
                    for c in cols:
                        lbl = getattr(c, 'key', None) or getattr(c, '_label', None)
                        if lbl == field:
                            stmt = stmt.order_by(desc(c) if direction == -1 else asc(c))
                            break

        if limit_stage:
            stmt = stmt.limit(limit_stage)

        result = await session.execute(stmt)
        rows = result.fetchall()
        docs = []
        for row in rows:
            d = dict(row._mapping)
            if "_id" not in d and group_id is None:
                d["_id"] = None
            docs.append(d)
        return docs

    def __aiter__(self):
        self._iter_data = None
        self._iter_index = 0
        return self

    async def __anext__(self):
        if self._iter_data is None:
            self._iter_data = await self.to_list()
        if self._iter_index >= len(self._iter_data):
            raise StopAsyncIteration
        doc = self._iter_data[self._iter_index]
        self._iter_index += 1
        return doc


class BaseRepository:
    model: Type[Base] = None

    def __init__(self, session_or_holder):
        from repositories import Repos
        if isinstance(session_or_holder, Repos) or (session_or_holder is not None and hasattr(session_or_holder, 'session') and not isinstance(session_or_holder, AsyncSession)):
            self._holder = session_or_holder
            self._direct_session = None
        else:
            self._holder = None
            self._direct_session = session_or_holder

    @property
    def session(self):
        if self._holder is not None:
            return self._holder.session
        return self._direct_session

    async def get_by_id(self, id: str, options=None) -> Optional[dict]:
        stmt = select(self.model).where(self.model.id == id)
        if options:
            for opt in options:
                stmt = stmt.options(opt)
        result = await self.session.execute(stmt)
        return _to_dict(result.scalars().first())

    async def find_one(self, filter_dict=None, projection=None, sort=None, options=None, **kwargs) -> Optional[dict]:
        stmt = select(self.model)
        if options:
            for opt in options:
                stmt = stmt.options(opt)
        filters = filter_dict or {}
        if filters:
            conds = _build_conditions(self.model, filters)
            if conds:
                stmt = stmt.where(and_(*conds))
        if sort:
            stmt = _apply_sort(stmt, self.model, sort)
        stmt = stmt.limit(1)
        result = await self.session.execute(stmt)
        row = result.scalars().first()
        if row is None:
            return None
        d = _to_dict(row)
        if projection:
            d = _apply_projection(d, projection)
        return d

    def find(self, filter_dict=None, projection=None, options=None):
        return RepoCursor(self, filter_dict, projection, options)

    async def find_many(self, filters: dict = None, sort=None, limit: int = 100,
                        offset: int = 0, options=None) -> List[dict]:
        stmt = select(self.model)
        if options:
            for opt in options:
                stmt = stmt.options(opt)
        if filters:
            conds = _build_conditions(self.model, filters)
            if conds:
                stmt = stmt.where(and_(*conds))
        if sort:
            stmt = _apply_sort(stmt, self.model, sort)
        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return [_to_dict(r) for r in result.scalars().all()]

    async def create(self, data: dict) -> str:
        doc = dict(data)
        doc.pop("_id", None)
        if "id" not in doc or not doc["id"]:
            doc["id"] = _gen_id()
        doc_id = doc["id"]

        obj = self.model()
        cols = _col_keys(self.model)
        extra = {}
        for k, v in doc.items():
            if k in cols:
                setattr(obj, k, _coerce_dt(self.model, k, v))
            elif COLUMN_ALIASES.get(k) in cols:
                alias = COLUMN_ALIASES[k]
                setattr(obj, alias, _coerce_dt(self.model, alias, v))
            else:
                extra[k] = v
        if extra and "data" in cols:
            existing = getattr(obj, "data", None) or {}
            if isinstance(existing, dict):
                setattr(obj, "data", {**existing, **extra})
            else:
                setattr(obj, "data", extra)
        self.session.add(obj)
        await self.session.flush()
        return doc_id

    async def insert_one(self, document: dict) -> InsertOneResult:
        doc_id = await self.create(document)
        return InsertOneResult(doc_id)

    async def insert_many(self, documents: list):
        ids = []
        for doc in documents:
            r = await self.insert_one(doc)
            ids.append(r.inserted_id)
        return type("InsertManyResult", (), {"inserted_ids": ids})()

    async def update_by_id(self, id: str, data: dict) -> bool:
        stmt = select(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        obj = result.scalars().first()
        if obj is None:
            return False
        cols = _col_keys(self.model)
        extra = {}
        for k, v in data.items():
            if k in ("id", "_id"):
                continue
            if "." in k:
                parts = k.split(".", 1)
                parent_key = parts[0]
                if parent_key in cols:
                    current = getattr(obj, parent_key, None)
                    if isinstance(current, dict):
                        current = dict(current)
                        current[parts[1]] = v
                        setattr(obj, parent_key, current)
                    elif current is None:
                        setattr(obj, parent_key, {parts[1]: v})
                continue
            if k in cols:
                setattr(obj, k, _coerce_dt(self.model, k, v))
            elif COLUMN_ALIASES.get(k) in cols:
                alias = COLUMN_ALIASES[k]
                setattr(obj, alias, _coerce_dt(self.model, alias, v))
            else:
                extra[k] = v
        if extra and "data" in cols:
            current = getattr(obj, "data", None)
            current = dict(current) if isinstance(current, dict) else {}
            current.update(extra)
            setattr(obj, "data", current)
        await self.session.flush()
        return True

    async def update_one(self, filter_dict: dict, update_dict: dict, upsert=False) -> UpdateResult:
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

        stmt = select(self.model)
        conds = _build_conditions(self.model, filter_dict)
        if conds:
            stmt = stmt.where(and_(*conds))
        stmt = stmt.limit(1)
        result = await self.session.execute(stmt)
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

        cols = _col_keys(self.model)
        extra_set = {}
        for k, v in set_fields.items():
            if k == "_id":
                continue
            if "." in k:
                parts = k.split(".", 1)
                parent_key = parts[0]
                if parent_key in cols:
                    current = getattr(row, parent_key, None)
                    if isinstance(current, dict):
                        current = dict(current)
                        current[parts[1]] = v
                        setattr(row, parent_key, current)
                    elif current is None:
                        setattr(row, parent_key, {parts[1]: v})
                continue
            if k in cols:
                setattr(row, k, _coerce_dt(self.model, k, v))
            elif COLUMN_ALIASES.get(k) in cols:
                alias = COLUMN_ALIASES[k]
                setattr(row, alias, _coerce_dt(self.model, alias, v))
            else:
                extra_set[k] = v
        if extra_set and "data" in cols:
            current_data = getattr(row, "data", None)
            current_data = dict(current_data) if isinstance(current_data, dict) else {}
            current_data.update(extra_set)
            setattr(row, "data", current_data)

        for k in unset_fields:
            if k == "_id":
                continue
            if k in cols:
                setattr(row, k, None)

        for k, v in inc_fields.items():
            if k in cols:
                current = getattr(row, k, 0) or 0
                setattr(row, k, current + v)
            elif COLUMN_ALIASES.get(k) in cols:
                alias = COLUMN_ALIASES[k]
                current = getattr(row, alias, 0) or 0
                setattr(row, alias, current + v)

        for k, v in push_fields.items():
            if k in cols:
                current = getattr(row, k) or []
                if isinstance(current, list):
                    current = list(current)
                    current.append(v)
                    setattr(row, k, current)

        for k, v in pull_fields.items():
            if k in cols:
                current = getattr(row, k) or []
                if isinstance(current, list):
                    setattr(row, k, [x for x in current if x != v])

        for k, v in max_fields.items():
            if k in cols:
                current = getattr(row, k, 0) or 0
                setattr(row, k, max(current, v))

        for k, v in add_to_set_fields.items():
            if k in cols:
                current = getattr(row, k) or []
                if isinstance(current, list):
                    current = list(current)
                    if v not in current:
                        current.append(v)
                    setattr(row, k, current)

        await self.session.flush()
        return UpdateResult(1, 1)

    async def update_many(self, filter_dict: dict, update_dict: dict) -> UpdateResult:
        set_fields = update_dict.get("$set", {})
        unset_fields = update_dict.get("$unset", {})
        inc_fields = update_dict.get("$inc", {})

        if not any([set_fields, unset_fields, inc_fields]):
            if not any(k.startswith("$") for k in update_dict):
                set_fields = update_dict

        cols = _col_keys(self.model)
        conds = _build_conditions(self.model, filter_dict)

        has_complex = bool(inc_fields) or bool(unset_fields)
        if has_complex:
            stmt = select(self.model)
            if conds:
                stmt = stmt.where(and_(*conds))
            result = await self.session.execute(stmt)
            rows = result.scalars().all()
            count = 0
            for row in rows:
                for k, v in set_fields.items():
                    if k in cols:
                        setattr(row, k, _coerce_dt(self.model, k, v))
                for k, v in inc_fields.items():
                    if k in cols:
                        current = getattr(row, k, 0) or 0
                        setattr(row, k, current + v)
                for k in unset_fields:
                    if k in cols:
                        setattr(row, k, None)
                count += 1
            await self.session.flush()
            return UpdateResult(count, count)

        if set_fields:
            values = {}
            for k, v in set_fields.items():
                if k in cols:
                    values[k] = _coerce_dt(self.model, k, v)
                elif COLUMN_ALIASES.get(k) in cols:
                    alias = COLUMN_ALIASES[k]
                    values[alias] = _coerce_dt(self.model, alias, v)
            if values:
                stmt = sa_update(self.model.__table__)
                if conds:
                    stmt = stmt.where(and_(*conds))
                stmt = stmt.values(**values)
                result = await self.session.execute(stmt)
                return UpdateResult(result.rowcount, result.rowcount)
        return UpdateResult(0, 0)

    async def update_where(self, filters: dict, data: dict) -> int:
        cols = _col_keys(self.model)
        values = {}
        for k, v in data.items():
            if k in ("id", "_id"):
                continue
            if k in cols:
                values[k] = _coerce_dt(self.model, k, v)
            elif COLUMN_ALIASES.get(k) in cols:
                alias = COLUMN_ALIASES[k]
                values[alias] = _coerce_dt(self.model, alias, v)
        if not values:
            return 0
        conds = _build_conditions(self.model, filters)
        stmt = sa_update(self.model.__table__)
        if conds:
            stmt = stmt.where(and_(*conds))
        stmt = stmt.values(**values)
        result = await self.session.execute(stmt)
        return result.rowcount

    async def upsert(self, filters: dict, data: dict) -> str:
        existing = await self.find_one(filters)
        if existing:
            await self.update_by_id(existing["id"], data)
            return existing["id"]
        else:
            merged = {**{k: v for k, v in filters.items() if not k.startswith("$")}, **data}
            return await self.create(merged)

    async def delete_by_id(self, id: str) -> bool:
        stmt = sa_delete(self.model.__table__).where(self.model.id == id)
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def delete_one(self, filter_dict: dict) -> DeleteResult:
        conds = _build_conditions(self.model, filter_dict)
        if not conds:
            return DeleteResult(0)
        id_subq = select(self.model.id)
        id_subq = id_subq.where(and_(*conds)).limit(1).scalar_subquery()
        stmt = sa_delete(self.model.__table__).where(self.model.id == id_subq)
        result = await self.session.execute(stmt)
        return DeleteResult(result.rowcount)

    async def delete_many(self, filter_dict: dict = None) -> DeleteResult:
        stmt = sa_delete(self.model.__table__)
        if filter_dict:
            conds = _build_conditions(self.model, filter_dict)
            if conds:
                stmt = stmt.where(and_(*conds))
        result = await self.session.execute(stmt)
        return DeleteResult(result.rowcount)

    async def delete_where(self, filters: dict) -> int:
        r = await self.delete_many(filters)
        return r.deleted_count

    async def count(self, filters: dict = None) -> int:
        stmt = select(func.count()).select_from(self.model)
        if filters:
            conds = _build_conditions(self.model, filters)
            if conds:
                stmt = stmt.where(and_(*conds))
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def count_documents(self, filter_dict: dict = None) -> int:
        return await self.count(filter_dict)

    async def exists(self, filters: dict) -> bool:
        return (await self.count(filters)) > 0

    async def distinct(self, field: str, filter_dict: dict = None) -> list:
        col = _resolve_col(self.model, field)
        if col is None:
            return []
        stmt = select(col).distinct()
        if filter_dict:
            conds = _build_conditions(self.model, filter_dict)
            if conds:
                stmt = stmt.where(and_(*conds))
        result = await self.session.execute(stmt)
        return [row[0] for row in result.fetchall()]

    def aggregate(self, pipeline: list):
        return AggregationCursor(self, pipeline)

    async def find_one_and_update(self, filter_dict: dict, update_dict: dict,
                                   return_document=None, upsert=False, projection=None) -> Optional[dict]:
        set_fields = update_dict.get("$set", {})
        inc_fields = update_dict.get("$inc", {})
        push_fields = update_dict.get("$push", {})
        unset_fields = update_dict.get("$unset", {})
        set_on_insert = update_dict.get("$setOnInsert", {})

        if not any([set_fields, inc_fields, push_fields, unset_fields]):
            if not any(k.startswith("$") for k in update_dict):
                set_fields = update_dict

        stmt = select(self.model)
        conds = _build_conditions(self.model, filter_dict)
        if conds:
            stmt = stmt.where(and_(*conds))
        stmt = stmt.limit(1)
        result = await self.session.execute(stmt)
        row = result.scalars().first()

        if row is None:
            if upsert:
                doc = {}
                for k, v in filter_dict.items():
                    if not k.startswith("$") and not isinstance(v, dict):
                        doc[k] = v
                doc.update(set_on_insert)
                doc.update(set_fields)
                r = await self.insert_one(doc)
                found = await self.get_by_id(r.inserted_id)
                return found
            return None

        cols = _col_keys(self.model)
        for k, v in set_fields.items():
            if k == "_id":
                continue
            if "." in k:
                parts = k.split(".", 1)
                if parts[0] in cols:
                    current = getattr(row, parts[0], None)
                    if isinstance(current, dict):
                        current = dict(current)
                        current[parts[1]] = v
                        setattr(row, parts[0], current)
                    elif current is None:
                        setattr(row, parts[0], {parts[1]: v})
                continue
            if k in cols:
                setattr(row, k, _coerce_dt(self.model, k, v))
            elif COLUMN_ALIASES.get(k) in cols:
                alias = COLUMN_ALIASES[k]
                setattr(row, alias, _coerce_dt(self.model, alias, v))
        for k, v in inc_fields.items():
            if k in cols:
                current = getattr(row, k, 0) or 0
                setattr(row, k, current + v)
        for k, v in push_fields.items():
            if k in cols:
                current = getattr(row, k) or []
                if isinstance(current, list):
                    current = list(current)
                    current.append(v)
                    setattr(row, k, current)
        for k in unset_fields:
            if k in cols:
                setattr(row, k, None)
        await self.session.flush()
        d = _to_dict(row)
        if projection:
            d = _apply_projection(d, projection)
        return d

    async def bulk_write(self, operations: list):
        from repositories.base import InsertOneResult as _IR
        results = []
        for op in operations:
            if hasattr(op, 'filter') and hasattr(op, 'update'):
                r = await self.update_one(op.filter, op.update, upsert=getattr(op, 'upsert', False))
                results.append(r)
        return type("BulkWriteResult", (), {
            "modified_count": sum(r.modified_count for r in results),
            "matched_count": sum(r.matched_count for r in results),
        })()

    async def batched_counts(self, specs: dict) -> dict:
        results = {}
        for label, filter_dict in specs.items():
            results[label] = await self.count(filter_dict)
        return results

    async def increment(self, id: str, field: str, amount: int = 1) -> bool:
        col = _resolve_col(self.model, field)
        if col is None:
            return False
        stmt = (sa_update(self.model.__table__)
                .where(self.model.id == id)
                .values(**{field: func.coalesce(col, 0) + amount}))
        result = await self.session.execute(stmt)
        return result.rowcount > 0


class GenericCollectionRepository(BaseRepository):

    def __init__(self, session_or_holder, collection_name: str):
        super().__init__(session_or_holder)
        self._collection_name = collection_name
        from pg_models import GenericDocument
        self.model = GenericDocument

    def _scope_filter(self, filter_dict):
        f = dict(filter_dict) if filter_dict else {}
        f["_collection"] = self._collection_name
        return f

    def _separate_filters(self, filters: dict):
        real_cols = set()
        mapper = sa_inspect(self.model)
        for c in mapper.columns:
            real_cols.add(c.key)
        real_cols.discard("data")
        column_filters = {}
        data_filters = {}
        for key, value in filters.items():
            if key.startswith("$") or key == "_id":
                column_filters[key] = value
            elif key in real_cols:
                column_filters[key] = value
            else:
                data_filters[key] = value
        return column_filters, data_filters

    def _build_data_conditions(self, data_filters: dict):
        conds = []
        data_col = self.model.data
        for key, value in data_filters.items():
            if isinstance(value, dict):
                for op, val in value.items():
                    jsonb_path = data_col[key]
                    if op == "$in":
                        conds.append(jsonb_path.astext.in_([str(v) for v in val]))
                    elif op == "$nin":
                        conds.append(~jsonb_path.astext.in_([str(v) for v in val]))
                    elif op == "$ne":
                        if val is None:
                            conds.append(jsonb_path.isnot(None))
                        else:
                            conds.append(jsonb_path.astext != str(val))
                    elif op == "$gte":
                        conds.append(jsonb_path.astext >= str(val))
                    elif op == "$gt":
                        conds.append(jsonb_path.astext > str(val))
                    elif op == "$lte":
                        conds.append(jsonb_path.astext <= str(val))
                    elif op == "$lt":
                        conds.append(jsonb_path.astext < str(val))
                    elif op == "$exists":
                        conds.append(jsonb_path.isnot(None) if val else jsonb_path.is_(None))
                    elif op == "$regex":
                        flags = value.get("$options", "")
                        pattern = val
                        if "i" in flags:
                            conds.append(jsonb_path.astext.ilike(f"%{pattern}%"))
                        else:
                            conds.append(jsonb_path.astext.like(f"%{pattern}%"))
            elif isinstance(value, list):
                conds.append(data_col[key].astext.in_([str(v) for v in value]))
            elif isinstance(value, bool):
                conds.append(data_col[key].astext == str(value).lower())
            else:
                conds.append(data_col[key].astext == str(value))
        return conds

    def _full_conditions(self, filter_dict):
        scoped = self._scope_filter(filter_dict)
        col_filters, data_filters = self._separate_filters(scoped)
        conds = _build_conditions(self.model, col_filters)
        if data_filters:
            conds.extend(self._build_data_conditions(data_filters))
        return conds

    async def find_one(self, filter_dict=None, projection=None, sort=None, options=None, **kwargs):
        stmt = select(self.model)
        if options:
            for opt in options:
                stmt = stmt.options(opt)
        conds = self._full_conditions(filter_dict)
        if conds:
            stmt = stmt.where(and_(*conds))
        if sort:
            stmt = _apply_sort(stmt, self.model, sort)
        stmt = stmt.limit(1)
        result = await self.session.execute(stmt)
        row = result.scalars().first()
        if row is None:
            return None
        d = _to_dict(row)
        if projection:
            d = _apply_projection(d, projection)
        return d

    def find(self, filter_dict=None, projection=None, options=None):
        return GenericRepoCursor(self, filter_dict, projection, options)

    async def find_many(self, filters=None, sort=None, limit=100, offset=0, options=None):
        stmt = select(self.model)
        if options:
            for opt in options:
                stmt = stmt.options(opt)
        conds = self._full_conditions(filters)
        if conds:
            stmt = stmt.where(and_(*conds))
        if sort:
            stmt = _apply_sort(stmt, self.model, sort)
        if offset:
            stmt = stmt.offset(offset)
        if limit:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return [_to_dict(r) for r in result.scalars().all()]

    async def count_documents(self, filter_dict=None):
        stmt = select(func.count()).select_from(self.model)
        conds = self._full_conditions(filter_dict)
        if conds:
            stmt = stmt.where(and_(*conds))
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def insert_one(self, document: dict):
        doc = dict(document)
        if "id" not in doc and "_id" not in doc:
            doc["id"] = str(uuid.uuid4())
        elif "_id" in doc and "id" not in doc:
            doc["id"] = doc.pop("_id")
        real_cols = set()
        mapper = sa_inspect(self.model)
        for c in mapper.columns:
            real_cols.add(c.key)
        real_cols.discard("data")
        col_vals = {"_collection": self._collection_name}
        data_vals = {}
        for k, v in doc.items():
            if k == "_id":
                continue
            if k in real_cols:
                col_vals[k] = v
            else:
                data_vals[k] = v
        col_vals["data"] = data_vals
        obj = self.model(**col_vals)
        self.session.add(obj)
        await self.session.flush()
        return InsertOneResult(doc["id"])

    async def update_one(self, filter_dict, update, upsert=False, return_document=False, **kwargs):
        conds = self._full_conditions(filter_dict)
        stmt = select(self.model)
        if conds:
            stmt = stmt.where(and_(*conds))
        stmt = stmt.limit(1)
        result = await self.session.execute(stmt)
        obj = result.scalars().first()
        if obj is None:
            if upsert:
                merged = dict(filter_dict or {})
                sets = (update.get("$set") or {}) if isinstance(update, dict) else {}
                merged.update(sets)
                return await self.insert_one(merged)
            return type("UpdateResult", (), {"modified_count": 0, "matched_count": 0})()
        if isinstance(update, dict) and "$set" in update:
            sets = update["$set"]
            data = dict(obj.data or {})
            real_cols = set()
            mapper = sa_inspect(self.model)
            for c in mapper.columns:
                real_cols.add(c.key)
            real_cols.discard("data")
            for k, v in sets.items():
                if k in real_cols and k != "_collection":
                    setattr(obj, k, v)
                else:
                    data[k] = v
            obj.data = data
        if "$unset" in (update or {}):
            data = dict(obj.data or {})
            for k in update["$unset"]:
                data.pop(k, None)
            obj.data = data
        if "$inc" in (update or {}):
            data = dict(obj.data or {})
            for k, v in update["$inc"].items():
                data[k] = (data.get(k) or 0) + v
            obj.data = data
        await self.session.flush()
        if return_document:
            return _to_dict(obj)
        return type("UpdateResult", (), {"modified_count": 1, "matched_count": 1})()

    async def update_many(self, filter_dict, update, **kwargs):
        conds = self._full_conditions(filter_dict)
        stmt = select(self.model)
        if conds:
            stmt = stmt.where(and_(*conds))
        result = await self.session.execute(stmt)
        objs = result.scalars().all()
        count = 0
        for obj in objs:
            if isinstance(update, dict) and "$set" in update:
                sets = update["$set"]
                data = dict(obj.data or {})
                real_cols = set()
                mapper = sa_inspect(self.model)
                for c in mapper.columns:
                    real_cols.add(c.key)
                real_cols.discard("data")
                for k, v in sets.items():
                    if k in real_cols and k != "_collection":
                        setattr(obj, k, v)
                    else:
                        data[k] = v
                obj.data = data
            count += 1
        if count:
            await self.session.flush()
        return type("UpdateResult", (), {"modified_count": count, "matched_count": count})()

    async def delete_one(self, filter_dict):
        conds = self._full_conditions(filter_dict)
        stmt = select(self.model)
        if conds:
            stmt = stmt.where(and_(*conds))
        stmt = stmt.limit(1)
        result = await self.session.execute(stmt)
        obj = result.scalars().first()
        if obj:
            await self.session.delete(obj)
            await self.session.flush()
            return type("DeleteResult", (), {"deleted_count": 1})()
        return type("DeleteResult", (), {"deleted_count": 0})()

    async def delete_many(self, filter_dict=None):
        conds = self._full_conditions(filter_dict)
        stmt = sa_delete(self.model)
        if conds:
            stmt = stmt.where(and_(*conds))
        result = await self.session.execute(stmt)
        return type("DeleteResult", (), {"deleted_count": result.rowcount})()


class GenericRepoCursor:

    def __init__(self, repo: GenericCollectionRepository, filter_dict=None, projection=None, options=None):
        self._repo = repo
        self._filter = filter_dict
        self._projection = projection
        self._options = options
        self._sort_list = None
        self._skip_val = 0
        self._limit_val = None

    def sort(self, key_or_list, direction=None):
        if isinstance(key_or_list, str):
            self._sort_list = [(key_or_list, direction or 1)]
        else:
            self._sort_list = key_or_list
        return self

    def skip(self, n):
        self._skip_val = n
        return self

    def limit(self, n):
        self._limit_val = n
        return self

    async def to_list(self, length=None):
        stmt = select(self._repo.model)
        if self._options:
            for opt in self._options:
                stmt = stmt.options(opt)
        conds = self._repo._full_conditions(self._filter)
        if conds:
            stmt = stmt.where(and_(*conds))
        if self._sort_list:
            for field, direction in self._sort_list:
                data_col = self._repo.model.data
                real_col = _resolve_col(self._repo.model, field)
                if real_col is not None:
                    stmt = stmt.order_by(desc(real_col) if direction == -1 else asc(real_col))
                else:
                    jsonb_expr = data_col[field].astext
                    stmt = stmt.order_by(desc(jsonb_expr) if direction == -1 else asc(jsonb_expr))
        if self._skip_val:
            stmt = stmt.offset(self._skip_val)
        lim = self._limit_val if self._limit_val is not None else length
        if lim:
            stmt = stmt.limit(lim)
        result = await self._repo.session.execute(stmt)
        rows = [_to_dict(r) for r in result.scalars().all()]
        if self._projection:
            rows = [_apply_projection(r, self._projection) for r in rows]
        return rows

    async def __aiter__(self):
        rows = await self.to_list(self._limit_val or 10000)
        for row in rows:
            yield row
