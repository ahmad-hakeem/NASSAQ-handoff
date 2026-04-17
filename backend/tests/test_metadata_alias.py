"""Regression tests for the ``metadata`` column-name alias collision.

``Message.extra_data`` and ``Notification.extra_data`` are mapped to the DB
column ``metadata`` (which collides with SQLAlchemy DeclarativeBase's
reserved ``metadata`` registry). Generic ORM helpers must therefore map
between the DB column name and the Python attribute name.
"""

import uuid
import pytest
from fastapi.encoders import jsonable_encoder

from dependencies import db
from engines.sql_utils import (
    gd_insert,
    gd_find,
    gd_find_one,
    gd_update_one,
    model_to_dict,
)
from pg_models import Message, Notification


pytestmark = pytest.mark.asyncio


async def _mk_school():
    school = {"id": str(uuid.uuid4()), "name": "T", "code": f"T{uuid.uuid4().hex[:6]}"}
    await gd_insert(db.session, "schools", school)
    return school["id"]


async def _mk_user(tenant_id: str | None = None) -> str:
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid,
        "email": f"{uid}@t.test",
        "full_name": "u",
        "role": "school_admin",
        "tenant_id": tenant_id,
        "is_active": True,
        "password_hash": "x",
    })
    return uid


async def test_message_serializes_without_recursion():
    school_id = await _mk_school()
    sender = await _mk_user(school_id)
    recip = await _mk_user(school_id)
    msg = {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "sender_id": sender,
        "recipient_id": recip,
        "subject": "hi",
        "body": "yo",
        "metadata": {"foo": "bar"},
    }
    await gd_insert(db.session, "messages", msg)
    rows = await gd_find(db.session, "messages", {"school_id": school_id})
    assert len(rows) == 1
    encoded = jsonable_encoder(rows)
    assert encoded[0]["metadata"] == {"foo": "bar"}
    assert encoded[0]["subject"] == "hi"


async def test_notification_serializes_without_recursion():
    school_id = await _mk_school()
    user_id = await _mk_user(school_id)
    notif = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "tenant_id": school_id,
        "title": "t",
        "message": "m",
        "metadata": {"k": 1},
    }
    await gd_insert(db.session, "notifications", notif)
    rows = await gd_find(db.session, "notifications", {"id": notif["id"]})
    assert len(rows) == 1
    jsonable_encoder(rows)  # must not raise RecursionError
    assert rows[0]["metadata"] == {"k": 1}


async def test_message_filter_and_update_via_alias():
    school_id = await _mk_school()
    sender = await _mk_user(school_id)
    recip = await _mk_user(school_id)
    msg_id = str(uuid.uuid4())
    await gd_insert(db.session, "messages", {
        "id": msg_id,
        "school_id": school_id,
        "sender_id": sender,
        "recipient_id": recip,
        "subject": "s",
        "body": "b",
        "metadata": {"v": 1},
    })
    found = await gd_find_one(db.session, "messages", {"id": msg_id})
    assert found and found["metadata"] == {"v": 1}

    await gd_update_one(db.session, "messages", {"id": msg_id}, {"metadata": {"v": 2}, "subject": "s2"})
    found = await gd_find_one(db.session, "messages", {"id": msg_id})
    assert found["metadata"] == {"v": 2}
    assert found["subject"] == "s2"


async def test_message_order_by_created_at_works():
    school_id = await _mk_school()
    sender = await _mk_user(school_id)
    recip = await _mk_user(school_id)
    for _ in range(2):
        await gd_insert(db.session, "messages", {
            "id": str(uuid.uuid4()),
            "school_id": school_id,
            "sender_id": sender,
            "recipient_id": recip,
            "subject": "x",
            "body": "y",
        })
    rows = await gd_find(db.session, "messages", {"school_id": school_id},
                         order_by="created_at", desc_order=True, limit=5)
    assert len(rows) == 2
    jsonable_encoder(rows)


async def test_model_to_dict_uses_db_column_name_for_output():
    """Backward compat: dict key is DB column name, not Python attr."""
    msg = Message(
        id=str(uuid.uuid4()),
        school_id=str(uuid.uuid4()),
        sender_id=str(uuid.uuid4()),
        recipient_id=str(uuid.uuid4()),
        subject="s", body="b", extra_data={"a": 1},
    )
    d = model_to_dict(msg)
    assert "metadata" in d  # DB column name preserved for API consumers
    assert d["metadata"] == {"a": 1}
    # extra_data is the python attr; must NOT appear as a separate key
    assert "extra_data" not in d
