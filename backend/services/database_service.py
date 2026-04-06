"""
NASSAQ - Database Service
Database connection and utilities (PostgreSQL via SQLAlchemy)
"""
from repositories import Repos

_db = Repos()


def get_database():
    return _db


async def close_database():
    from db import close_pg_engine
    await close_pg_engine()


def serialize_doc(doc: dict) -> dict:
    if doc is None:
        return None
    result = dict(doc)
    if "_id" in result:
        result["id"] = str(result["_id"])
        del result["_id"]
    return result


def serialize_docs(docs: list) -> list:
    return [serialize_doc(doc) for doc in docs if doc]


async def create_indexes(db):
    pass
