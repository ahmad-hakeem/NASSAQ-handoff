import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Type

from sqlalchemy import select, and_, func, delete as sa_delete
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


async def gd_find(session, collection: str, filters: dict = None,
                  order_by: str = None, desc_order: bool = True,
                  limit: int = None, offset: int = None) -> List[dict]:
    from pg_models import GenericDocument
    stmt = select(GenericDocument).where(GenericDocument._collection == collection)
    if filters:
        for k, v in filters.items():
            if k == "id":
                stmt = stmt.where(GenericDocument.id == v)
            elif isinstance(v, dict):
                for op, val in v.items():
                    col_expr = GenericDocument.data[k].astext
                    if op == "$gte":
                        stmt = stmt.where(col_expr >= str(val))
                    elif op == "$lte":
                        stmt = stmt.where(col_expr <= str(val))
                    elif op == "$gt":
                        stmt = stmt.where(col_expr > str(val))
                    elif op == "$lt":
                        stmt = stmt.where(col_expr < str(val))
                    elif op == "$ne":
                        stmt = stmt.where(col_expr != str(val))
                    elif op == "$in":
                        stmt = stmt.where(col_expr.in_([str(x) for x in val]))
                    elif op == "$regex":
                        stmt = stmt.where(col_expr.op("~")(str(val)))
            elif isinstance(v, list):
                stmt = stmt.where(GenericDocument.data[k].astext.in_([str(x) for x in v]))
            else:
                if isinstance(v, bool):
                    stmt = stmt.where(GenericDocument.data[k].astext == str(v).lower())
                else:
                    stmt = stmt.where(GenericDocument.data[k].astext == str(v))
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
    if filters:
        for k, v in filters.items():
            if k == "id":
                stmt = stmt.where(GenericDocument.id == v)
            else:
                stmt = stmt.where(GenericDocument.data[k].astext == str(v))
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


async def gd_count(session, collection: str, filters: dict = None) -> int:
    from pg_models import GenericDocument
    stmt = select(func.count(GenericDocument.id)).where(
        GenericDocument._collection == collection
    )
    if filters:
        for k, v in filters.items():
            if k == "id":
                stmt = stmt.where(GenericDocument.id == v)
            elif isinstance(v, dict):
                for op, val in v.items():
                    col_expr = GenericDocument.data[k].astext
                    if op == "$gte":
                        stmt = stmt.where(col_expr >= str(val))
                    elif op == "$lte":
                        stmt = stmt.where(col_expr <= str(val))
                    elif op == "$ne":
                        stmt = stmt.where(col_expr != str(val))
                    elif op == "$in":
                        stmt = stmt.where(col_expr.in_([str(x) for x in val]))
            else:
                if isinstance(v, bool):
                    stmt = stmt.where(GenericDocument.data[k].astext == str(v).lower())
                else:
                    stmt = stmt.where(GenericDocument.data[k].astext == str(v))
    result = await session.execute(stmt)
    return result.scalar() or 0


async def gd_delete_one(session, collection: str, filters: dict) -> int:
    from pg_models import GenericDocument
    stmt = select(GenericDocument).where(GenericDocument._collection == collection)
    if filters:
        for k, v in filters.items():
            if k == "id":
                stmt = stmt.where(GenericDocument.id == v)
            else:
                stmt = stmt.where(GenericDocument.data[k].astext == str(v))
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
    if filters:
        for k, v in filters.items():
            if k == "id":
                sub = sub.where(GenericDocument.id == v)
            elif isinstance(v, dict):
                for op, val in v.items():
                    col_expr = GenericDocument.data[k].astext
                    if op == "$lt":
                        sub = sub.where(col_expr < str(val))
                    elif op == "$lte":
                        sub = sub.where(col_expr <= str(val))
                    elif op == "$gte":
                        sub = sub.where(col_expr >= str(val))
            else:
                if isinstance(v, bool):
                    sub = sub.where(GenericDocument.data[k].astext == str(v).lower())
                else:
                    sub = sub.where(GenericDocument.data[k].astext == str(v))
    stmt = sa_delete(GenericDocument).where(GenericDocument.id.in_(sub.scalar_subquery()))
    result = await session.execute(stmt)
    await session.flush()
    return result.rowcount
