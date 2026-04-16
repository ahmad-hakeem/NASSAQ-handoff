import pytest
from engines.sql_utils import gd_find
from dependencies import db as _db


@pytest.mark.asyncio
async def test_notify_parent_creates_notification(client, school_admin_headers, student_with_parent):
    body = {"student_id": student_with_parent["id"], "action_type": "notify_parent",
            "data": {"message": "يرجى مراجعة المدرسة", "issue_type": "attendance"}}
    r = await client.post("/ai/insights/intervention", json=body, headers=school_admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True
    notifs = await gd_find(_db.session, "notifications",
                           {"user_id": student_with_parent["parent_id"],
                            "tenant_id": student_with_parent["school_id"]})
    assert any("يرجى مراجعة المدرسة" in (n.get("message") or "") for n in notifs)


@pytest.mark.asyncio
async def test_remedial_plan_persisted(client, school_admin_headers, a_student):
    body = {"student_id": a_student["id"], "action_type": "remedial_plan",
            "data": {"issue_type": "academic", "description": "خطة دعم",
                     "target_date": "2026-05-01", "milestones": ["مراجعة", "اختبار"]}}
    r = await client.post("/ai/insights/intervention", json=body, headers=school_admin_headers)
    assert r.status_code == 200, r.text
    inv_id = r.json()["intervention_id"]
    assert inv_id
    rows = await gd_find(_db.session, "ai_interventions", {"id": inv_id})
    assert len(rows) == 1
    assert rows[0]["type"] == "plan"


@pytest.mark.asyncio
async def test_cross_tenant_student_404(client, tenant_a_admin, tenant_b_student):
    body = {"student_id": tenant_b_student["id"], "action_type": "schedule_followup",
            "data": {"follow_up_date": "2026-04-30", "notes": ""}}
    r = await client.post("/ai/insights/intervention", json=body, headers=tenant_a_admin)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_intervention_role_denied_for_teacher(client, teacher_headers, a_student):
    body = {"student_id": a_student["id"], "action_type": "schedule_followup",
            "data": {"follow_up_date": "2026-04-30"}}
    r = await client.post("/ai/insights/intervention", json=body, headers=teacher_headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_intervention_writes_audit_log(client, school_admin_headers, a_student):
    body = {"student_id": a_student["id"], "action_type": "schedule_followup",
            "data": {"follow_up_date": "2026-04-30"}}
    r = await client.post("/ai/insights/intervention", json=body, headers=school_admin_headers)
    assert r.status_code == 200, r.text
    logs = await gd_find(_db.session, "audit_logs",
                         {"entity_id": a_student["id"], "action": "intervention.schedule_followup"})
    assert logs, "audit row missing"


@pytest.mark.asyncio
async def test_notify_parent_without_parent_400(client, school_admin_headers, orphan_student):
    body = {"student_id": orphan_student["id"], "action_type": "notify_parent",
            "data": {"message": "x", "issue_type": "attendance"}}
    r = await client.post("/ai/insights/intervention", json=body, headers=school_admin_headers)
    assert r.status_code == 400
