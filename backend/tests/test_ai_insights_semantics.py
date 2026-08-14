"""
Semantic-classification tests for the AI Insights page.

The `/ai/insights/predictions` endpoint historically returned a mixed bag of
cards — trend observations, current-state readings, a "not enough data"
notice and a hard risk signal — with nothing on the payload distinguishing
them. The UI therefore rendered all of them under "Predictions & Forecasts"
and badged the data-gap card as "medium risk" with a 0% confidence gauge.

These tests pin the semantic contract:

  1. Every card declares an `insight_kind` from the closed vocabulary
     (forecast / trend / current_state / risk_signal / data_gap).
  2. A card may only use future-claim wording when it is a `forecast`.
  3. The insufficient-data card is classified `data_gap` with NO confidence
     number (a fabricated 0% reads as "0% likely", not "not applicable").
  4. Every card carries the time window it describes and the evidence
     (`basis`) it was computed from.
  5. Every recommendation carries actionable `context`: which classes /
     scope it applies to, the time window, and the numeric evidence.
"""
import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


VALID_KINDS = {"forecast", "trend", "current_state", "risk_signal", "data_gap"}

# Wording that asserts something about the FUTURE. Legitimate only on a card
# explicitly classified as a forecast.
FUTURE_CLAIM_TOKENS = [
    re.compile(r"الأسبوع القادم"),
    re.compile(r"من المتوقع"),
    re.compile(r"يُتوقع"),
    re.compile(r"سيرتفع"),
    re.compile(r"سينخفض"),
    re.compile(r"expected to", re.IGNORECASE),
    re.compile(r"will (?:rise|drop|increase|decrease)", re.IGNORECASE),
    re.compile(r"forecast", re.IGNORECASE),
    re.compile(r"predicted", re.IGNORECASE),
]


def _headers(user_id: str, role: str, tenant_id, *, teacher_id=None):
    payload = {"sub": user_id, "role": role, "tenant_id": tenant_id}
    if teacher_id is not None:
        payload["teacher_id"] = teacher_id
    return {"Authorization": f"Bearer {create_access_token(payload)}"}


def _texts(card: dict):
    out = []
    for key in ("title", "description", "basis"):
        blob = card.get(key)
        if isinstance(blob, dict):
            out.extend([v for v in blob.values() if isinstance(v, str)])
        elif isinstance(blob, str):
            out.append(blob)
    return out


async def _seed_class(school_id: str, name: str) -> str:
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": cid, "school_id": school_id, "name": name,
    })
    return cid


async def _seed_student(school_id: str, class_id: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "school_id": school_id, "full_name": f"S-{sid[:6]}",
        "class_id": class_id, "is_active": True,
    })
    return sid


async def _seed_teacher_user(school_id: str, class_id: str):
    user_id = str(uuid.uuid4())
    teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": user_id, "role": UserRole.TEACHER.value,
        "tenant_id": school_id, "teacher_id": teacher_id,
        "email": f"t-{user_id}@t.test", "full_name": f"T-{user_id[:6]}",
        "is_active": True, "password_hash": "x",
    })
    await gd_insert(db.session, "teachers", {
        "id": teacher_id, "school_id": school_id, "user_id": user_id,
        "full_name": f"T-{user_id[:6]}",
    })
    await gd_insert(db.session, "teacher_class_assignments", {
        "id": str(uuid.uuid4()), "teacher_id": teacher_id,
        "school_id": school_id, "class_id": class_id,
    })
    return user_id, teacher_id


async def _seed_attendance(school_id, class_id, student_ids, *,
                           days_ago_from, days_ago_to, present_ratio):
    """Insert one attendance row per student per day in the window."""
    today = datetime.now(timezone.utc)
    n = 0
    for sid in student_ids:
        for d in range(days_ago_to, days_ago_from):
            day = (today - timedelta(days=d)).strftime("%Y-%m-%d")
            status = "present" if (n % 10) < (present_ratio * 10) else "absent"
            n += 1
            await gd_insert(db.session, "attendance", {
                "id": str(uuid.uuid4()), "school_id": school_id,
                "student_id": sid, "class_id": class_id,
                "date": day, "status": status,
            })


# ------------------------------------------------------------------ tests


@pytest.mark.asyncio
async def test_every_prediction_card_declares_kind_window_and_basis(
    client, tenant_a
):
    """Each card must be self-describing: what type of insight it is, which
    time window it covers, and the evidence it was derived from."""
    cls = await _seed_class(tenant_a, "Sem-1A")
    students = [await _seed_student(tenant_a, cls) for _ in range(4)]
    user_id, teacher_id = await _seed_teacher_user(tenant_a, cls)
    # Two full comparable weeks so a real trend/current-state card is emitted.
    await _seed_attendance(tenant_a, cls, students,
                           days_ago_from=6, days_ago_to=1, present_ratio=0.9)
    await _seed_attendance(tenant_a, cls, students,
                           days_ago_from=13, days_ago_to=8, present_ratio=0.9)

    r = await client.get("/ai/insights/predictions", headers=_headers(
        user_id, UserRole.TEACHER.value, tenant_a, teacher_id=teacher_id))
    assert r.status_code == 200, r.text
    cards = r.json()
    assert isinstance(cards, list) and cards, "expected at least one card"

    for card in cards:
        kind = card.get("insight_kind")
        assert kind in VALID_KINDS, f"unclassified card: {card!r}"

        tw = card.get("time_window")
        assert isinstance(tw, dict), f"card missing time_window: {card!r}"
        assert tw.get("direction") in {"past", "future"}, tw
        assert isinstance(tw.get("days"), int) and tw["days"] > 0, tw
        assert (tw.get("label") or {}).get("ar"), tw

        basis = card.get("basis")
        assert isinstance(basis, dict) and basis.get("ar"), (
            f"card missing evidence/basis: {card!r}"
        )


@pytest.mark.asyncio
async def test_non_forecast_cards_never_claim_the_future(client, tenant_a):
    """A descriptive reading must not be worded as a future prediction."""
    cls = await _seed_class(tenant_a, "Sem-2A")
    students = [await _seed_student(tenant_a, cls) for _ in range(4)]
    user_id, teacher_id = await _seed_teacher_user(tenant_a, cls)
    # Strong week-over-week improvement — used to emit "Improvement expected
    # to continue next week", which is a forecast claim on a trend card.
    await _seed_attendance(tenant_a, cls, students,
                           days_ago_from=6, days_ago_to=1, present_ratio=1.0)
    await _seed_attendance(tenant_a, cls, students,
                           days_ago_from=13, days_ago_to=8, present_ratio=0.5)

    r = await client.get("/ai/insights/predictions", headers=_headers(
        user_id, UserRole.TEACHER.value, tenant_a, teacher_id=teacher_id))
    assert r.status_code == 200, r.text
    cards = r.json()
    assert cards

    for card in cards:
        if card.get("insight_kind") == "forecast":
            continue
        for text in _texts(card):
            for pat in FUTURE_CLAIM_TOKENS:
                assert not pat.search(text), (
                    f"non-forecast card ({card.get('insight_kind')}) claims "
                    f"the future: {text!r}"
                )


@pytest.mark.asyncio
async def test_insufficient_data_card_is_data_gap_without_confidence(
    client, tenant_a
):
    """The 'not enough attendance data' notice is a data-quality note, not a
    medium-risk prediction with 0% confidence."""
    cls = await _seed_class(tenant_a, "Sem-3A")
    students = [await _seed_student(tenant_a, cls) for _ in range(2)]
    user_id, teacher_id = await _seed_teacher_user(tenant_a, cls)
    # Only 2 records this week, none last week -> below MIN_ATT_RECORDS.
    await _seed_attendance(tenant_a, cls, students[:1],
                           days_ago_from=3, days_ago_to=1, present_ratio=1.0)

    r = await client.get("/ai/insights/predictions", headers=_headers(
        user_id, UserRole.TEACHER.value, tenant_a, teacher_id=teacher_id))
    assert r.status_code == 200, r.text
    cards = r.json()
    gaps = [c for c in cards if c.get("insight_kind") == "data_gap"]
    assert gaps, f"expected a data_gap card, got: {cards!r}"

    for card in gaps:
        assert card.get("confidence") is None, (
            "a data-gap notice must not carry a fabricated confidence number"
        )
        assert card.get("impact") not in {"high", "medium", "positive"}, (
            f"data-gap card must not read as a risk level: {card!r}"
        )


@pytest.mark.asyncio
async def test_recommendations_carry_actionable_context(client, tenant_a):
    """Every recommendation must say what it applies to (class/scope), over
    which window, and on what numeric evidence."""
    cls = await _seed_class(tenant_a, "Sem-4A")
    students = [await _seed_student(tenant_a, cls) for _ in range(5)]
    user_id, teacher_id = await _seed_teacher_user(tenant_a, cls)
    await _seed_attendance(tenant_a, cls, students,
                           days_ago_from=25, days_ago_to=1, present_ratio=0.5)

    r = await client.get("/ai/insights/recommendations", headers=_headers(
        user_id, UserRole.TEACHER.value, tenant_a, teacher_id=teacher_id))
    assert r.status_code == 200, r.text
    recs = r.json()
    assert isinstance(recs, list) and recs

    for rec in recs:
        ctx = rec.get("context")
        assert isinstance(ctx, dict), f"rec missing context: {rec!r}"
        assert (ctx.get("scope_label") or {}).get("ar"), (
            f"rec missing a scope label (which class/scope?): {rec!r}"
        )
        tw = ctx.get("time_window") or {}
        assert isinstance(tw.get("days"), int) and tw["days"] > 0, (
            f"rec missing its time window: {rec!r}"
        )
        assert (ctx.get("evidence") or {}).get("ar"), (
            f"rec missing numeric evidence: {rec!r}"
        )

    # A teacher-scoped card must name the actual class it refers to, not a
    # generic "your class".
    scoped = [r for r in recs
              if (r.get("context") or {}).get("scope_level") == "classroom"]
    assert scoped, "teacher should receive classroom-scoped cards"
    for rec in scoped:
        ctx = rec["context"]
        assert "Sem-4A" in (ctx.get("class_names") or []), (
            f"classroom card does not name the class: {rec!r}"
        )
        assert "Sem-4A" in ctx["scope_label"]["ar"], (
            f"scope label is not specific: {ctx['scope_label']!r}"
        )


def test_arabic_counted_nouns_agree_with_the_number():
    """Generated Arabic must inflect the counted noun (1 / 2 / 3-10 / 11+).

    "9 طالباً" and "16 فصول" are both broken Arabic; a native reader sees
    the card as machine-written rather than trustworthy.
    """
    from src.modules.ai.controllers.ai_routes_mod import _ar_count

    forms = ("طالب واحد", "طالبين", "طلاب", "طالباً")
    assert _ar_count(1, *forms) == "طالب واحد"
    assert _ar_count(2, *forms) == "طالبين"
    assert _ar_count(9, *forms) == "9 طلاب"
    assert _ar_count(16, *forms) == "16 طالباً"
    assert _ar_count(221, *forms) == "221 طالباً"
    # 103 ends in 3 -> plural form, matching spoken/written Arabic.
    assert _ar_count(103, *forms) == "103 طلاب"


def test_scope_label_inflects_the_class_count():
    """The scope label is the most-read generated sentence on the page."""
    from src.modules.ai.controllers.ai_routes_mod import _scope_descriptor_from_classes

    def _cls(name):
        return {"id": name, "name": name}

    teacher_many = _scope_descriptor_from_classes(
        [_cls(f"C{i}") for i in range(19)], is_teacher=True)
    assert "16 فصلاً آخر" in teacher_many["scope_label"]["ar"]

    teacher_five = _scope_descriptor_from_classes(
        [_cls(f"C{i}") for i in range(5)], is_teacher=True)
    assert "فصلين آخرين" in teacher_five["scope_label"]["ar"]

    school = _scope_descriptor_from_classes(
        [_cls(f"C{i}") for i in range(4)], is_teacher=False)
    assert school["scope_label"]["ar"] == "المدرسة كاملة (4 فصول)"


def test_every_recommendation_builder_returns_its_context():
    """A builder that accepts `context` but forgets to put it on the card
    silently breaks the contract for that whole recommendation family."""
    import inspect
    from routes import ai_routes_mod as mod

    sentinel = {"scope_level": "classroom",
                "scope_label": {"ar": "فصلك: أ", "en": "your class A"},
                "class_names": ["أ"],
                "time_window": {"direction": "past", "days": 30,
                                "label": {"ar": "آخر 30 يوماً",
                                          "en": "Last 30 days"}},
                "evidence": {"ar": "دليل", "en": "evidence"}}

    builders = [name for name in dir(mod)
                if name.startswith("_build_") and name.endswith("_rec")]
    assert builders, "no recommendation builders found"

    for name in builders:
        fn = getattr(mod, name)
        params = inspect.signature(fn).parameters
        assert "context" in params, f"{name} does not take a context"
        kwargs = {"context": sentinel, "is_teacher": True}
        for pname, p in params.items():
            if pname in kwargs or p.default is not inspect.Parameter.empty:
                continue
            if pname == "rec_id":
                kwargs[pname] = "1"
            elif "pct" in pname or "rate" in pname:
                kwargs[pname] = 42.0
            else:
                kwargs[pname] = "أ"
        for is_teacher in (True, False):
            card = fn(**{**kwargs, "is_teacher": is_teacher})
            assert card.get("context") is sentinel, (
                f"{name}(is_teacher={is_teacher}) dropped its context"
            )


def test_scope_label_reports_the_real_total_beyond_the_load_cap():
    """Class rows are loaded in a capped page; the label must state the true
    total, not the page size."""
    from src.modules.ai.controllers.ai_routes_mod import _scope_descriptor_from_classes

    page = [{"id": f"c{i}", "name": f"C{i}"} for i in range(100)]

    school = _scope_descriptor_from_classes(page, False, total_count=140)
    assert school["scope_label"]["ar"] == "المدرسة كاملة (140 فصلاً)"
    assert school["scope_label"]["en"] == "whole school (140 classes)"

    teacher = _scope_descriptor_from_classes(page, True, total_count=140)
    assert "137 فصلاً آخر" in teacher["scope_label"]["ar"]

    # A total smaller than the page (stale count) must never shrink the label
    # below what was actually loaded.
    safe = _scope_descriptor_from_classes(page, False, total_count=3)
    assert safe["scope_label"]["ar"] == "المدرسة كاملة (100 فصلاً)"
