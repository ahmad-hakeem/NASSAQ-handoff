import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Type

from sqlalchemy import select, and_, or_, func, delete as sa_delete
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession

TENANT_ALIAS = {"tenant_id": "school_id", "school_id": "tenant_id"}

_SKIP_KEYS = frozenset({"_collection"})


def model_to_dict(obj) -> Optional[dict]:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    d = {}
    mapper = sa_inspect(type(obj))
    data_val = None
    has_data_col = False
    for col in mapper.columns:
        if col.key in _SKIP_KEYS:
            continue
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


def models_to_dicts(objs) -> List[dict]:
    return [model_to_dict(o) for o in objs]


def _col_keys(model_cls) -> set:
    mapper = sa_inspect(model_cls)
    return {c.key for c in mapper.columns}


def dict_to_model(model_cls, data: dict):
    cols = _col_keys(model_cls)
    kwargs = {}
    extra = {}
    for k, v in data.items():
        if k == "_id":
            continue
        if k in cols:
            kwargs[k] = v
        elif TENANT_ALIAS.get(k) in cols:
            kwargs[TENANT_ALIAS[k]] = v
        else:
            extra[k] = v
    if extra and "data" in cols:
        existing = kwargs.get("data") or {}
        if isinstance(existing, dict):
            kwargs["data"] = {**existing, **extra}
        else:
            kwargs["data"] = extra
    return model_cls(**kwargs)


def apply_updates(obj, updates: dict, model_cls=None):
    if model_cls is None:
        model_cls = type(obj)
    cols = _col_keys(model_cls)
    extra = {}
    for k, v in updates.items():
        if k in ("id", "_id"):
            continue
        if k in cols:
            setattr(obj, k, v)
        elif TENANT_ALIAS.get(k) in cols:
            setattr(obj, TENANT_ALIAS[k], v)
        else:
            extra[k] = v
    if extra and "data" in cols:
        current = getattr(obj, "data", None)
        current = dict(current) if isinstance(current, dict) else {}
        current.update(extra)
        setattr(obj, "data", current)


def _build_filter_conditions(model_cls, filters: dict):
    conds = []
    if not filters:
        return conds
    for k, v in filters.items():
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
            col_expr = model_cls.data[k].astext
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
                    conds.append(col_expr.op("~")(str(val)))
                elif op == "$exists":
                    if val:
                        conds.append(model_cls.data[k].isnot(None))
                    else:
                        conds.append(model_cls.data[k].is_(None))
        elif isinstance(v, list):
            conds.append(model_cls.data[k].astext.in_([str(x) for x in v]))
        elif isinstance(v, bool):
            conds.append(model_cls.data[k].astext == str(v).lower())
        else:
            conds.append(model_cls.data[k].astext == str(v))
    return conds


async def gd_find(session, collection: str, filters: dict = None,
                  order_by: str = None, desc_order: bool = True,
                  limit: int = None, offset: int = None) -> List[dict]:
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


async def gd_find_one(session, collection: str, filters: dict = None) -> Optional[dict]:
    results = await gd_find(session, collection, filters, limit=1)
    return results[0] if results else None


async def gd_insert(session, collection: str, doc: dict) -> str:
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


async def gd_update_one(session, collection: str, filters: dict, updates: dict) -> int:
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
    current_data = dict(obj.data) if obj.data else {}
    current_data.update(updates)
    obj.data = current_data
    await session.flush()
    return 1


async def gd_update_many(session, collection: str, filters: dict, updates: dict) -> int:
    from pg_models import GenericDocument
    stmt = select(GenericDocument).where(GenericDocument._collection == collection)
    conds = _build_filter_conditions(GenericDocument, filters)
    if conds:
        stmt = stmt.where(and_(*conds))
    result = await session.execute(stmt)
    objs = result.scalars().all()
    count = 0
    for obj in objs:
        current_data = dict(obj.data) if obj.data else {}
        current_data.update(updates)
        obj.data = current_data
        count += 1
    if count:
        await session.flush()
    return count


async def gd_count(session, collection: str, filters: dict = None) -> int:
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


async def _gd_aggregate(session, collection: str, pipeline: list) -> List[dict]:
    match_filter = {}
    for stage in pipeline:
        if "$match" in stage:
            match_filter = stage["$match"]
            break
    docs = await gd_find(session, collection, match_filter, limit=50000)
    
    group_stage = None
    sort_stage = None
    limit_val = None
    project_stage = None
    add_fields_stage = None
    
    for stage in pipeline:
        if "$group" in stage:
            group_stage = stage["$group"]
        elif "$sort" in stage:
            sort_stage = stage["$sort"]
        elif "$limit" in stage:
            limit_val = stage["$limit"]
        elif "$project" in stage:
            project_stage = stage["$project"]
        elif "$addFields" in stage:
            add_fields_stage = stage["$addFields"]
    
    if group_stage:
        group_id = group_stage.get("_id")
        groups = {}
        for doc in docs:
            if isinstance(group_id, str) and group_id.startswith("$"):
                key = doc.get(group_id[1:])
            elif isinstance(group_id, dict):
                key_parts = {}
                for gk, gv in group_id.items():
                    if isinstance(gv, str) and gv.startswith("$"):
                        key_parts[gk] = doc.get(gv[1:])
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
                        if isinstance(sum_expr, str) and sum_expr.startswith("$"):
                            row[field] = sum(doc.get(sum_expr[1:], 0) or 0 for doc in group["_docs"])
                        elif sum_expr == 1:
                            row[field] = len(group["_docs"])
                        else:
                            row[field] = sum_expr * len(group["_docs"])
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
                    elif "$count" in expr:
                        row[field] = len(group["_docs"])
                elif isinstance(expr, str) and expr.startswith("$"):
                    row[field] = group["_docs"][0].get(expr[1:]) if group["_docs"] else None
            result.append(row)
        docs = result
    
    if sort_stage:
        for field, direction in reversed(list(sort_stage.items())):
            docs = sorted(docs, key=lambda d: d.get(field, ""), reverse=(direction == -1))
    
    if limit_val:
        docs = docs[:limit_val]
    
    return docs
