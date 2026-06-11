"""Task #889 — regression coverage for the hardened undo/peek logic in
``TeacherSessionEngine``.

Task #888 changed undo/peek so they evaluate every candidate actor id as a
*union* and pick the truly most-recent unreversed event by timestamp, instead
of trying ids one at a time and stopping at the first id that had a match.
Historically the same logical action could be logged under either the
``Teachers.id`` or the caller's ``Users.id``; the one-id-at-a-time approach
could therefore reverse an *older* action recorded under the first id while a
newer action recorded under the second id was ignored.

These tests seed ``session_event_log`` with reversible events recorded under
DIFFERENT actor ids with interleaved timestamps and assert that:
- ``get_last_reversible_action`` returns the single most-recent unreversed
  event across the union of ids.
- ``undo_last_action`` reverses that most-recent event (not an older one),
  marks it reversed, and a repeat call walks back to the next-most-recent.
- ``count_reversible_actions`` counts across the union, matches the real total,
  and caps at 10.
- ``GET /session/{id}/undo/peek`` returns the same most-recent event and stack
  depth.
- The single-id (current production) shape still behaves correctly.
"""
import uuid
from datetime import datetime, timezone, timedelta

import pytest

from dependencies import db, create_access_token
from engines.sql_utils import gd_find_one, gd_insert
from engines.session_engine import (
    TeacherSessionEngine as SessionEngine,
    EventType,
)

BASE_TIME = datetime(2026, 6, 11, 8, 0, 0, tzinfo=timezone.utc)


def _engine():
    class _DBShim:
        @property
        def session(self):
            return db.session

    return SessionEngine(_DBShim())


async def _mk_session(tenant_id: str, teacher_id: str, status: str = "in_progress") -> str:
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    await gd_insert(db.session, "class_sessions", {
        "id": session_id,
        "school_id": tenant_id,
        "tenant_id": tenant_id,
        "teacher_id": teacher_id,
        "date": "2026-06-11",
        "status": status,
        "start_time": now,
        "created_at": now,
    })
    return session_id


async def _mk_student(tenant_id: str, name: str = "طالب") -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid,
        "tenant_id": tenant_id,
        "school_id": tenant_id,
        "full_name": name,
        "is_active": True,
    })
    return sid


async def _log(session_id: str, actor_id: str, *, offset_seconds: int,
               event_type: str = EventType.PARTICIPATION_RECORDED.value,
               student_id: str = None, reversed_: bool = False,
               score_change: int = 0) -> dict:
    """Insert a session_event_log row with a deterministic timestamp."""
    ts = (BASE_TIME + timedelta(seconds=offset_seconds)).isoformat()
    meta = {"score_change": score_change}
    if reversed_:
        meta["reversed"] = True
    event = {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "event_type": event_type,
        "actor_type": "teacher",
        "actor_id": actor_id,
        "student_id": student_id,
        "metadata": meta,
        "timestamp": ts,
        "offset_seconds": offset_seconds,
    }
    await gd_insert(db.session, "session_event_log", {
        k: v for k, v in event.items() if k != "offset_seconds"
    })
    return event


@pytest.mark.asyncio
async def test_get_last_reversible_action_picks_most_recent_across_union(tenant_a):
    """Most-recent unreversed event must win even when it was recorded under a
    different actor id than the older events."""
    teacher_id = str(uuid.uuid4())  # Teachers.id
    user_id = str(uuid.uuid4())     # Users.id
    session_id = await _mk_session(tenant_a, teacher_id)

    # Interleaved across both ids; the NEWEST (t+30) is under user_id.
    await _log(session_id, teacher_id, offset_seconds=10)
    await _log(session_id, teacher_id, offset_seconds=20)
    newest = await _log(session_id, user_id, offset_seconds=30)

    eng = _engine()
    action = await eng.get_last_reversible_action(session_id, [teacher_id, user_id])
    assert action is not None
    assert action["id"] == newest["id"]

    # A single id alone would only ever see its own (older) events.
    action_single = await eng.get_last_reversible_action(session_id, teacher_id)
    assert action_single is not None
    assert action_single["timestamp"] == (BASE_TIME + timedelta(seconds=20)).isoformat()


@pytest.mark.asyncio
async def test_undo_reverses_latest_then_walks_back(tenant_a):
    """undo_last_action reverses the truly most-recent event across the union,
    marks it reversed, and a repeat call moves to the next-most-recent."""
    teacher_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session_id = await _mk_session(tenant_a, teacher_id)
    student_id = await _mk_student(tenant_a)

    # Oldest under teacher_id, middle under user_id, newest under teacher_id.
    oldest = await _log(session_id, teacher_id, offset_seconds=10, student_id=student_id)
    middle = await _log(session_id, user_id, offset_seconds=20, student_id=student_id)
    newest = await _log(session_id, teacher_id, offset_seconds=30, student_id=student_id)

    eng = _engine()

    # First undo → newest.
    await eng.undo_last_action(session_id, teacher_id, user_id=user_id)
    ev_newest = await gd_find_one(db.session, "session_event_log", {"id": newest["id"]})
    assert (ev_newest.get("metadata") or {}).get("reversed") is True

    # Second undo → middle (recorded under the OTHER id).
    await eng.undo_last_action(session_id, teacher_id, user_id=user_id)
    ev_middle = await gd_find_one(db.session, "session_event_log", {"id": middle["id"]})
    assert (ev_middle.get("metadata") or {}).get("reversed") is True
    # Oldest still untouched at this point.
    ev_oldest = await gd_find_one(db.session, "session_event_log", {"id": oldest["id"]})
    assert (ev_oldest.get("metadata") or {}).get("reversed") is not True

    # Third undo → oldest.
    await eng.undo_last_action(session_id, teacher_id, user_id=user_id)
    ev_oldest = await gd_find_one(db.session, "session_event_log", {"id": oldest["id"]})
    assert (ev_oldest.get("metadata") or {}).get("reversed") is True

    # Nothing left → 400.
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await eng.undo_last_action(session_id, teacher_id, user_id=user_id)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_count_reversible_actions_union_and_cap(tenant_a):
    """count_reversible_actions counts across the union, matches the real total,
    ignores already-reversed events, and caps at 10."""
    teacher_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session_id = await _mk_session(tenant_a, teacher_id)

    # 2 under teacher, 3 under user, plus one already-reversed (excluded) and
    # one non-reversible event type (excluded).
    await _log(session_id, teacher_id, offset_seconds=10)
    await _log(session_id, teacher_id, offset_seconds=11)
    await _log(session_id, user_id, offset_seconds=12)
    await _log(session_id, user_id, offset_seconds=13)
    await _log(session_id, user_id, offset_seconds=14)
    await _log(session_id, user_id, offset_seconds=15, reversed_=True)
    await _log(session_id, teacher_id, offset_seconds=16,
               event_type=EventType.SESSION_OPENED.value)

    eng = _engine()
    count = await eng.count_reversible_actions(session_id, [teacher_id, user_id])
    assert count == 5

    # Cap at 10 even with more eligible events.
    big_session = await _mk_session(tenant_a, teacher_id)
    for i in range(12):
        actor = teacher_id if i % 2 == 0 else user_id
        await _log(big_session, actor, offset_seconds=i)
    capped = await eng.count_reversible_actions(big_session, [teacher_id, user_id])
    assert capped == 10


@pytest.mark.asyncio
async def test_count_matches_after_undos(tenant_a):
    """The depth count tracks reality as actions get reversed."""
    teacher_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    session_id = await _mk_session(tenant_a, teacher_id)
    student_id = await _mk_student(tenant_a)

    await _log(session_id, teacher_id, offset_seconds=10, student_id=student_id)
    await _log(session_id, user_id, offset_seconds=20, student_id=student_id)
    await _log(session_id, teacher_id, offset_seconds=30, student_id=student_id)

    eng = _engine()
    assert await eng.count_reversible_actions(session_id, [teacher_id, user_id]) == 3
    await eng.undo_last_action(session_id, teacher_id, user_id=user_id)
    assert await eng.count_reversible_actions(session_id, [teacher_id, user_id]) == 2
    await eng.undo_last_action(session_id, teacher_id, user_id=user_id)
    assert await eng.count_reversible_actions(session_id, [teacher_id, user_id]) == 1


@pytest.mark.asyncio
async def test_single_id_backward_compatibility(tenant_a):
    """Current production shape: every event recorded under the same single id
    still resolves and reverses newest-first."""
    teacher_id = str(uuid.uuid4())
    session_id = await _mk_session(tenant_a, teacher_id)
    student_id = await _mk_student(tenant_a)

    await _log(session_id, teacher_id, offset_seconds=10, student_id=student_id)
    newest = await _log(session_id, teacher_id, offset_seconds=20, student_id=student_id)

    eng = _engine()
    action = await eng.get_last_reversible_action(session_id, teacher_id)
    assert action["id"] == newest["id"]
    assert await eng.count_reversible_actions(session_id, teacher_id) == 2

    # Undo with only the single id available (user_id None) still works.
    await eng.undo_last_action(session_id, teacher_id, user_id=None)
    ev_newest = await gd_find_one(db.session, "session_event_log", {"id": newest["id"]})
    assert (ev_newest.get("metadata") or {}).get("reversed") is True
    assert await eng.count_reversible_actions(session_id, teacher_id) == 1


@pytest.mark.asyncio
async def test_peek_route_returns_most_recent_across_union(client, tenant_a):
    """GET /session/{id}/undo/peek evaluates Teachers.id + Users.id as a union
    and reports the most-recent event plus the full stack depth."""
    user_id = str(uuid.uuid4())     # Users.id (current_user["id"])
    teacher_id = str(uuid.uuid4())  # Teachers.id (current_user["teacher_id"])

    await gd_insert(db.session, "users", {
        "id": user_id, "role": "teacher", "tenant_id": tenant_a,
        "email": f"u-{user_id}@t.test", "full_name": "معلم", "is_active": True,
        "password_hash": "x",
    })
    # Linking the teachers row via user_id makes get_current_user resolve
    # teacher_id to this teachers.id.
    await gd_insert(db.session, "teachers", {
        "id": teacher_id, "user_id": user_id, "school_id": tenant_a,
        "tenant_id": tenant_a, "full_name": "معلم", "is_active": True,
    })
    student_id = await _mk_student(tenant_a)
    session_id = await _mk_session(tenant_a, teacher_id)

    await _log(session_id, teacher_id, offset_seconds=10, student_id=student_id)
    await _log(session_id, user_id, offset_seconds=20, student_id=student_id)
    newest = await _log(session_id, teacher_id, offset_seconds=30,
                        student_id=student_id,
                        event_type=EventType.BEHAVIOUR_RECORDED.value)

    token = create_access_token({"sub": user_id, "role": "teacher", "tenant_id": tenant_a})
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get(f"/session/{session_id}/undo/peek", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["has_reversible"] is True
    assert body["stack_depth"] == 3
    assert body["event_type"] == newest["event_type"]
    assert body["student_id"] == student_id
