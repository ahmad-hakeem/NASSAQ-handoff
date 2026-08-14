"""Task 5 — publish-gate via HardConstraintRegistry.

Covers:
  5a. SmartSchedulingEngine.validate_before_publish dispatches via the
      registry, partitioning HIGH/CRITICAL → blocking, MEDIUM → warnings.
  5b. assert_publishable helper raises HTTPException(409) and is wired
      into every publish endpoint.
"""

import uuid

import pytest
from fastapi import HTTPException

from dependencies import db
from engines.smart_scheduling_engine import (
    AcademicDemand,
    ConflictSeverity,
    SmartSchedulingEngine,
)
from engines.sql_utils import gd_insert, gd_find_one, gd_update_many
from src.modules.scheduling.controllers._publish_gate import assert_publishable


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _mk_timetable(school_id: str) -> str:
    tid = str(uuid.uuid4())
    await gd_insert(db.session, "timetables", {
        "id": tid, "school_id": school_id,
        "name": "T", "academic_year": "2026-2027", "semester": 1,
        "status": "draft", "version": 1, "total_sessions": 0,
    })
    return tid


async def _mk_session(school_id: str, timetable_id: str, **fields) -> str:
    sid = str(uuid.uuid4())
    row = {
        "id": sid,
        "school_id": school_id,
        "timetable_id": timetable_id,
        "day_of_week": "sunday",
        "period_number": 1,
    }
    row.update(fields)
    await gd_insert(db.session, "timetable_sessions", row)
    return sid


async def _isolate_hc():
    """Disable every existing timetable_hard_constraints row so the test
    can opt in to exactly the validators it cares about. The shared test
    DB (no transactional isolation across tests) accumulates leaked rows
    from prior runs and is_seeded with all 17 HCs in some environments;
    this helper makes the test deterministic regardless."""
    await gd_update_many(
        db.session, "timetable_hard_constraints", {}, {"is_active": False}
    )


async def _mk_hc(validation_key: str, code: str, severity: str = "critical", is_active: bool = True):
    """Insert (or override) a hard-constraint row for a given validation_key.

    If a row with this validation_key already exists (e.g. from a startup
    seed), update it to match the requested is_active/severity so the test
    sees a single authoritative row.
    """
    from engines.sql_utils import gd_find_one as _gd_find_one, gd_update_one
    existing = await _gd_find_one(
        db.session, "timetable_hard_constraints", {"validation_key": validation_key}
    )
    if existing:
        await gd_update_one(
            db.session,
            "timetable_hard_constraints",
            {"id": existing["id"]},
            {"is_active": is_active, "severity": severity},
        )
        return existing["id"]
    cid = str(uuid.uuid4())
    await gd_insert(db.session, "timetable_hard_constraints", {
        "id": cid,
        "code": code,
        "name_ar": code, "name_en": code,
        "description_ar": "", "description_en": "",
        "category": "test",
        "severity": severity,
        "is_system": True,
        "is_active": is_active,
        "can_disable": False,
        "validation_key": validation_key,
    })
    return cid


# ---------------------------------------------------------------------------
# 5a — engine.validate_before_publish
# ---------------------------------------------------------------------------

async def test_validate_before_publish_uses_registry(school_a_id):
    await _isolate_hc()
    tt_id = await _mk_timetable(school_a_id)
    await _mk_hc("teacher_overlap", "HC-01")
    teacher = str(uuid.uuid4())
    await _mk_session(school_a_id, tt_id, teacher_id=teacher,
                      class_id=str(uuid.uuid4()), subject_id=str(uuid.uuid4()),
                      day_of_week="sunday", period_number=1)
    await _mk_session(school_a_id, tt_id, teacher_id=teacher,
                      class_id=str(uuid.uuid4()), subject_id=str(uuid.uuid4()),
                      day_of_week="sunday", period_number=1)

    engine = SmartSchedulingEngine(db)
    result = await engine.validate_before_publish(school_id=school_a_id, timetable_id=tt_id)

    assert result["is_publishable"] is False
    keys = {v["validation_key"] for v in result["violations"]}
    assert "teacher_overlap" in keys


async def test_validate_before_publish_passes_clean_timetable(school_a_id):
    await _isolate_hc()
    tt_id = await _mk_timetable(school_a_id)
    await _mk_hc("teacher_overlap", "HC-01")
    await _mk_session(school_a_id, tt_id,
                      teacher_id=str(uuid.uuid4()),
                      class_id=str(uuid.uuid4()),
                      subject_id=str(uuid.uuid4()),
                      day_of_week="sunday", period_number=1)
    await _mk_session(school_a_id, tt_id,
                      teacher_id=str(uuid.uuid4()),
                      class_id=str(uuid.uuid4()),
                      subject_id=str(uuid.uuid4()),
                      day_of_week="sunday", period_number=2)

    engine = SmartSchedulingEngine(db)
    result = await engine.validate_before_publish(school_id=school_a_id, timetable_id=tt_id)

    assert result["is_publishable"] is True
    assert result["violations"] == []


async def test_validate_before_publish_warns_on_medium_severity(school_a_id):
    await _isolate_hc()
    tt_id = await _mk_timetable(school_a_id)
    await _mk_hc("no_consecutive_subject", "HC-10", severity="medium")
    cls = str(uuid.uuid4())
    subj = str(uuid.uuid4())
    await _mk_session(school_a_id, tt_id,
                      teacher_id=str(uuid.uuid4()), class_id=cls, subject_id=subj,
                      day_of_week="sunday", period_number=1)
    await _mk_session(school_a_id, tt_id,
                      teacher_id=str(uuid.uuid4()), class_id=cls, subject_id=subj,
                      day_of_week="sunday", period_number=2)

    engine = SmartSchedulingEngine(db)
    result = await engine.validate_before_publish(school_id=school_a_id, timetable_id=tt_id)

    assert result["is_publishable"] is True
    assert any(w["validation_key"] == "no_consecutive_subject" for w in result["warnings"])


async def test_validate_before_publish_respects_inactive_constraints(school_a_id):
    await _isolate_hc()
    tt_id = await _mk_timetable(school_a_id)
    await _mk_hc("teacher_overlap", "HC-01", is_active=False)
    teacher = str(uuid.uuid4())
    await _mk_session(school_a_id, tt_id, teacher_id=teacher,
                      class_id=str(uuid.uuid4()), subject_id=str(uuid.uuid4()),
                      day_of_week="sunday", period_number=1)
    await _mk_session(school_a_id, tt_id, teacher_id=teacher,
                      class_id=str(uuid.uuid4()), subject_id=str(uuid.uuid4()),
                      day_of_week="sunday", period_number=1)

    engine = SmartSchedulingEngine(db)
    result = await engine.validate_before_publish(school_id=school_a_id, timetable_id=tt_id)

    assert result["is_publishable"] is True


async def test_validate_before_publish_under_warns_over_blocks(school_a_id):
    """Period-quota policy at the publish gate: a subject placed FEWER times
    than its weekly demand (under-placement / incomplete schedule) is a
    non-blocking warning, while a subject placed MORE times than demanded
    (over-placement) still blocks publish. Exercises HC-09
    (subject_weekly_periods) and HC-14 (schedule_completeness) end-to-end
    through validate_before_publish's severity partitioning.

    build_academic_demand reads real curriculum data; here it is stubbed on
    the instance so the test controls the demand without seeding a full
    academic structure."""
    await _isolate_hc()
    tt_id = await _mk_timetable(school_a_id)
    await _mk_hc("subject_weekly_periods", "HC-09", severity="high")
    await _mk_hc("schedule_completeness", "HC-14", severity="medium")

    under_cls, under_subj = str(uuid.uuid4()), str(uuid.uuid4())
    over_cls, over_subj = str(uuid.uuid4()), str(uuid.uuid4())
    # Under-placed: demand 4, place 3.
    for p in range(1, 4):
        await _mk_session(school_a_id, tt_id, teacher_id=str(uuid.uuid4()),
                          class_id=under_cls, subject_id=under_subj,
                          day_of_week="sunday", period_number=p)
    # Over-placed: demand 1, place 3.
    for p in range(1, 4):
        await _mk_session(school_a_id, tt_id, teacher_id=str(uuid.uuid4()),
                          class_id=over_cls, subject_id=over_subj,
                          day_of_week="monday", period_number=p)

    engine = SmartSchedulingEngine(db)

    async def _stub_demand(*_a, **_k):
        return [
            AcademicDemand(
                class_id=under_cls, class_name="Under", grade_id=str(uuid.uuid4()),
                subjects=[{"subject_id": under_subj, "weekly_periods": 4,
                           "suitable_teachers": []}],
                total_periods_required=4,
            ),
            AcademicDemand(
                class_id=over_cls, class_name="Over", grade_id=str(uuid.uuid4()),
                subjects=[{"subject_id": over_subj, "weekly_periods": 1,
                           "suitable_teachers": []}],
                total_periods_required=1,
            ),
        ]

    engine.build_academic_demand = _stub_demand

    result = await engine.validate_before_publish(
        school_id=school_a_id, timetable_id=tt_id
    )

    # Over-placement must block publish.
    assert result["is_publishable"] is False
    block = result["violations"]
    assert any(
        v["validation_key"] == "subject_weekly_periods"
        and v["refs"].get("class_id") == over_cls
        for v in block
    )
    # Under-placement must NOT block — it is surfaced only as a warning.
    assert not any(v["refs"].get("class_id") == under_cls for v in block)
    warn_keys = {w["validation_key"] for w in result["warnings"]}
    assert "schedule_completeness" in warn_keys
    assert any(
        w["validation_key"] == "subject_weekly_periods"
        and w["refs"].get("class_id") == under_cls
        for w in result["warnings"]
    )


async def _mk_subject(school_id: str, *, is_active: bool = True) -> str:
    """Insert a real subjects-table row for the school."""
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "subjects", {
        "id": sid,
        "school_id": school_id,
        "name": "مادة",
        "is_active": is_active,
    })
    return sid


def _flagged_subject_ids(result: dict) -> set:
    """Subject ids flagged as orphan references by HC-16 (entity_integrity).
    HC-16 refs carry {"field": "subject_id", "value": <id>}."""
    return {
        v["refs"].get("value")
        for v in result["violations"]
        if v["validation_key"] == "entity_integrity"
        and v["refs"].get("field") == "subject_id"
    }


async def test_validate_before_publish_active_subject_without_demand_not_orphan(
    school_a_id,
):
    """Regression: HC-16 (entity_integrity) must NOT flag a real, ACTIVE
    school subject referenced by a manually-built timetable just because the
    subject is absent from the academic-demand matrix (no curriculum row /
    no class-scoped teacher assignment).

    Previously ctx.resources['subjects'] was derived solely from demand, so
    an active subject missing from demand produced a false
    'مرجع غير صالح subject_id=...' that blocked publish. validate_before_publish
    now seeds the subject universe from the subjects table. A subject id that
    does NOT exist (deleted/never-created) must still be flagged."""
    await _isolate_hc()
    await _mk_hc("entity_integrity", "HC-16", severity="critical")
    tt_id = await _mk_timetable(school_a_id)

    good_subj = await _mk_subject(school_a_id, is_active=True)
    bad_subj = str(uuid.uuid4())  # never inserted → genuinely orphan

    # Active subject, not part of any demand → must NOT be flagged.
    await _mk_session(school_a_id, tt_id, teacher_id=str(uuid.uuid4()),
                      class_id=str(uuid.uuid4()), subject_id=good_subj,
                      day_of_week="sunday", period_number=1)
    # Nonexistent subject → must STILL be flagged.
    await _mk_session(school_a_id, tt_id, teacher_id=str(uuid.uuid4()),
                      class_id=str(uuid.uuid4()), subject_id=bad_subj,
                      day_of_week="sunday", period_number=2)

    engine = SmartSchedulingEngine(db)
    result = await engine.validate_before_publish(
        school_id=school_a_id, timetable_id=tt_id
    )

    flagged_subjects = _flagged_subject_ids(result)
    assert good_subj not in flagged_subjects, (
        "active subject without demand was wrongly flagged as orphan"
    )
    assert bad_subj in flagged_subjects, (
        "nonexistent subject must still be flagged by HC-16"
    )


async def test_validate_before_publish_inactive_subject_still_orphan(school_a_id):
    """An INACTIVE (soft-deleted) subject must remain an HC-16 orphan: the
    publish-time seed loads active subjects only, so deactivated subjects are
    correctly still blocked."""
    await _isolate_hc()
    await _mk_hc("entity_integrity", "HC-16", severity="critical")
    tt_id = await _mk_timetable(school_a_id)

    inactive_subj = await _mk_subject(school_a_id, is_active=False)
    await _mk_session(school_a_id, tt_id, teacher_id=str(uuid.uuid4()),
                      class_id=str(uuid.uuid4()), subject_id=inactive_subj,
                      day_of_week="sunday", period_number=1)

    engine = SmartSchedulingEngine(db)
    result = await engine.validate_before_publish(
        school_id=school_a_id, timetable_id=tt_id
    )

    assert inactive_subj in _flagged_subject_ids(result)


# ---------------------------------------------------------------------------
# 5b — assert_publishable helper + endpoint enforcement
# ---------------------------------------------------------------------------

async def test_assert_publishable_helper_exists_and_raises_http_exception():
    class _StubEngine:
        async def validate_before_publish(self, *, school_id, timetable_id):
            return {
                "is_publishable": False,
                "violations": [{
                    "code": "HC-01",
                    "validation_key": "teacher_overlap",
                    "severity": "critical",
                    "message_en": "x", "message_ar": "x", "refs": {},
                }],
                "warnings": [],
            }

    with pytest.raises(HTTPException) as exc:
        await assert_publishable(_StubEngine(), school_id="s", timetable_id="t")
    assert exc.value.status_code == 409
    detail = exc.value.detail
    assert isinstance(detail, dict)
    assert detail.get("code") == "PUBLISH_BLOCKED"
    assert detail.get("violations")


async def test_publish_endpoint_blocks_when_assert_publishable_raises(
    client, school_principal_headers, tenant_a
):
    await _isolate_hc()
    tt_id = await _mk_timetable(tenant_a)
    await _mk_hc("teacher_overlap", "HC-01")
    teacher = str(uuid.uuid4())
    await _mk_session(tenant_a, tt_id, teacher_id=teacher,
                      class_id=str(uuid.uuid4()), subject_id=str(uuid.uuid4()),
                      day_of_week="sunday", period_number=1)
    await _mk_session(tenant_a, tt_id, teacher_id=teacher,
                      class_id=str(uuid.uuid4()), subject_id=str(uuid.uuid4()),
                      day_of_week="sunday", period_number=1)
    await db.session.commit()

    r = await client.post(
        f"/smart-scheduling/timetable/{tt_id}/publish",
        headers=school_principal_headers,
    )
    assert r.status_code == 409, r.text
    body = r.json()
    # The app's StarletteHTTPException handler passes the structured
    # detail through: {"success": False, "error": {"code": "PUBLISH_BLOCKED",
    # "detail": {..., "violations": [...]}, ...}}
    err = body.get("error") if isinstance(body, dict) else None
    assert err is not None
    assert err.get("code") == "PUBLISH_BLOCKED"
    assert "teacher_overlap" in r.text  # violation constraint key present


async def test_publish_endpoint_succeeds_when_no_blocking_violations(
    client, school_principal_headers, tenant_a
):
    tt_id = await _mk_timetable(tenant_a)
    # Disable any active hard constraints so the gate is purely permissive.
    await _mk_hc("teacher_overlap", "HC-01", is_active=False)
    await _mk_hc("entity_integrity", "HC-16", is_active=False)
    await _mk_hc("schedule_completeness", "HC-14", is_active=False)
    await _mk_session(tenant_a, tt_id,
                      teacher_id=str(uuid.uuid4()),
                      class_id=str(uuid.uuid4()),
                      subject_id=str(uuid.uuid4()),
                      day_of_week="sunday", period_number=1)
    await db.session.commit()

    r = await client.post(
        f"/smart-scheduling/timetable/{tt_id}/publish",
        headers=school_principal_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # Either the route returns success directly or wraps in envelope.
    assert body.get("success") is True or body.get("status") == "published"


async def test_publish_endpoint_uses_same_gate_logic_as_validate_before_publish(
    client, school_principal_headers, tenant_a
):
    tt_id = await _mk_timetable(tenant_a)
    await _mk_hc("teacher_overlap", "HC-01")
    teacher = str(uuid.uuid4())
    await _mk_session(tenant_a, tt_id, teacher_id=teacher,
                      class_id=str(uuid.uuid4()), subject_id=str(uuid.uuid4()),
                      day_of_week="sunday", period_number=1)
    await _mk_session(tenant_a, tt_id, teacher_id=teacher,
                      class_id=str(uuid.uuid4()), subject_id=str(uuid.uuid4()),
                      day_of_week="sunday", period_number=1)
    await db.session.commit()

    engine = SmartSchedulingEngine(db)
    engine_result = await engine.validate_before_publish(
        school_id=tenant_a, timetable_id=tt_id
    )

    r = await client.post(
        f"/smart-scheduling/timetable/{tt_id}/publish",
        headers=school_principal_headers,
    )
    endpoint_blocked = r.status_code == 409
    assert endpoint_blocked == (not engine_result["is_publishable"])
