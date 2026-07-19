"""Teacher-permissions audit (2026-07-19) — enrichment/remedial plan surfaces.

Locks the permission model for the plan-producing and plan-exporting routes
around the AI Insights Risk Radar:

  * POST /hakim/student/{id}/ai-plans   — leadership trio + independent_teacher
    ONLY (LLM generation + persisted plan_history). Teachers, parents, students
    and platform_admin are denied, mirroring the tested sibling contract on
    POST /ai/insights/intervention.
  * POST /export/student-plans/{id}[,/pdf] — same role gate + can_view_student
    (previously ANY same-tenant account could export a school-stamped document
    for any student).
  * PUT /hakim/interventions/{id}/status — school_sub_admin included (it can
    create and list interventions; excluding it from status updates was an
    inconsistency) and the modification is audit-logged.
  * plan_history.generated_by attribution is populated (was always NULL).
"""

import pytest

from engines.sql_utils import gd_find
from dependencies import db as _db

AI_PLANS = "/hakim/student/{sid}/ai-plans"
EXPORT_DOCX = "/export/student-plans/{sid}"
EXPORT_PDF = "/export/student-plans/{sid}/pdf"

PLAN_BODY = {
    "plan_type": "remedial",
    "remedial_plan": {
        "title": "الخطة العلاجية",
        "summary": "خطة اختبارية",
        "steps": [
            {"title": "خطوة", "description": "وصف", "duration": "أسبوع", "responsible": "معلم المادة"},
        ],
        "expected_outcome": "تحسن ملموس",
    },
}


def _force_fallback(monkeypatch):
    """Force the deterministic fallback path — no live LLM calls in tests."""
    from routes import ai_routes_mod
    monkeypatch.setattr(ai_routes_mod, "get_openai_client", lambda: None)


# ---------------------------------------------------------------------------
# POST /hakim/student/{id}/ai-plans — role matrix
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ai_plans_allowed_school_admin_fallback(client, school_admin_headers, a_student, monkeypatch):
    _force_fallback(monkeypatch)
    r = await client.post(AI_PLANS.format(sid=a_student["id"]), headers=school_admin_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["success"] is True
    assert "remedial_plan" in data.get("plans", {}) or data.get("plans")


@pytest.mark.asyncio
async def test_ai_plans_allowed_sub_admin_and_principal(client, school_sub_admin_headers, school_principal_headers, a_student, monkeypatch):
    _force_fallback(monkeypatch)
    for headers in (school_sub_admin_headers, school_principal_headers):
        r = await client.post(AI_PLANS.format(sid=a_student["id"]), headers=headers)
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_ai_plans_denied_teacher(client, teacher_headers, a_student, monkeypatch):
    _force_fallback(monkeypatch)
    r = await client.post(AI_PLANS.format(sid=a_student["id"]), headers=teacher_headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_ai_plans_denied_parent(client, parent_headers, a_student, monkeypatch):
    _force_fallback(monkeypatch)
    r = await client.post(AI_PLANS.format(sid=a_student["id"]), headers=parent_headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_ai_plans_denied_student(client, student_headers, a_student, monkeypatch):
    """Student bearer tokens are rejected at the auth boundary with 401 while
    ``dependencies.STUDENT_LOGIN_DISABLED`` is True (see
    test_session_management_assignments) — an even earlier denial than the
    role gate's 403."""
    _force_fallback(monkeypatch)
    r = await client.post(AI_PLANS.format(sid=a_student["id"]), headers=student_headers)
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_ai_plans_denied_platform_admin(client, platform_admin_headers, a_student, monkeypatch):
    """Mirrors the sibling intervention contract: platform_admin is deliberately
    NOT in the gate (a previewing admin carries a switched school-role token)."""
    _force_fallback(monkeypatch)
    r = await client.post(AI_PLANS.format(sid=a_student["id"]), headers=platform_admin_headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_ai_plans_cross_tenant_404(client, tenant_a_admin, tenant_b_student, monkeypatch):
    _force_fallback(monkeypatch)
    r = await client.post(AI_PLANS.format(sid=tenant_b_student["id"]), headers=tenant_a_admin)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_ai_plans_writes_attribution_and_audit_log(client, school_admin_headers, a_student, monkeypatch):
    _force_fallback(monkeypatch)
    r = await client.post(AI_PLANS.format(sid=a_student["id"]), headers=school_admin_headers)
    assert r.status_code == 200, r.text

    history = await gd_find(_db.session, "plan_history", {"student_id": a_student["id"]})
    assert history, "plan_history row missing"
    assert any(h.get("generated_by") for h in history), \
        "generated_by attribution is NULL — the old current_user['user_id'] bug"

    logs = await gd_find(_db.session, "audit_logs",
                         {"entity_id": a_student["id"], "action": "ai_plans.generate"})
    assert logs, "ai_plans.generate audit row missing"


# ---------------------------------------------------------------------------
# POST /export/student-plans/{id} (+ /pdf) — role matrix
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_docx_allowed_school_admin(client, school_admin_headers, a_student):
    r = await client.post(EXPORT_DOCX.format(sid=a_student["id"]), json=PLAN_BODY,
                          headers=school_admin_headers)
    assert r.status_code == 200, r.text
    assert "wordprocessingml" in r.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_export_pdf_allowed_school_admin(client, school_admin_headers, a_student):
    r = await client.post(EXPORT_PDF.format(sid=a_student["id"]), json=PLAN_BODY,
                          headers=school_admin_headers)
    assert r.status_code == 200, r.text
    assert "pdf" in r.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_export_docx_denied_teacher_parent_student(client, teacher_headers, parent_headers, student_headers, a_student):
    for headers in (teacher_headers, parent_headers):
        r = await client.post(EXPORT_DOCX.format(sid=a_student["id"]), json=PLAN_BODY, headers=headers)
        assert r.status_code == 403, (r.status_code, r.text)
    # student tokens die at the auth boundary (STUDENT_LOGIN_DISABLED) → 401
    r = await client.post(EXPORT_DOCX.format(sid=a_student["id"]), json=PLAN_BODY, headers=student_headers)
    assert r.status_code in (401, 403), (r.status_code, r.text)


@pytest.mark.asyncio
async def test_export_pdf_denied_teacher_parent_student(client, teacher_headers, parent_headers, student_headers, a_student):
    for headers in (teacher_headers, parent_headers):
        r = await client.post(EXPORT_PDF.format(sid=a_student["id"]), json=PLAN_BODY, headers=headers)
        assert r.status_code == 403, (r.status_code, r.text)
    # student tokens die at the auth boundary (STUDENT_LOGIN_DISABLED) → 401
    r = await client.post(EXPORT_PDF.format(sid=a_student["id"]), json=PLAN_BODY, headers=student_headers)
    assert r.status_code in (401, 403), (r.status_code, r.text)


@pytest.mark.asyncio
async def test_export_docx_cross_tenant_404(client, tenant_a_admin, tenant_b_student):
    r = await client.post(EXPORT_DOCX.format(sid=tenant_b_student["id"]), json=PLAN_BODY,
                          headers=tenant_a_admin)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_export_pdf_cross_tenant_404(client, tenant_a_admin, tenant_b_student):
    r = await client.post(EXPORT_PDF.format(sid=tenant_b_student["id"]), json=PLAN_BODY,
                          headers=tenant_a_admin)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# independent_teacher — the one allowed role beyond the leadership trio
# ---------------------------------------------------------------------------

async def _seed_it_workspace():
    """IT workspace = schools row with school_type=independent_teacher so the
    users.tenant_id FK resolves (mirrors test_skill_type_update_weight)."""
    import uuid as _uuid
    from engines.sql_utils import gd_insert
    from dependencies import create_access_token

    uid = str(_uuid.uuid4())
    itw = f"itw_{uid}"
    await gd_insert(_db.session, "schools", {
        "id": itw, "name": "IT Workspace", "code": f"IT{uid[:8]}",
        "status": "active", "country": "SA", "language": "ar",
        "school_type": "independent_teacher",
    })
    await gd_insert(_db.session, "users", {
        "id": uid, "role": "independent_teacher", "tenant_id": itw,
        "email": f"it-{uid}@t.test", "full_name": "معلم مستقل",
        "is_active": True, "password_hash": "x",
    })
    student_id = str(_uuid.uuid4())
    await gd_insert(_db.session, "students", {
        "id": student_id, "full_name": "طالب مستقل", "school_id": itw,
        "is_active": True,
    })
    token = create_access_token({"sub": uid, "role": "independent_teacher", "tenant_id": itw})
    return {"Authorization": f"Bearer {token}"}, student_id


@pytest.mark.asyncio
async def test_ai_plans_allowed_independent_teacher(client, monkeypatch):
    _force_fallback(monkeypatch)
    headers, student_id = await _seed_it_workspace()
    r = await client.post(AI_PLANS.format(sid=student_id), headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True


@pytest.mark.asyncio
async def test_export_docx_allowed_independent_teacher(client):
    headers, student_id = await _seed_it_workspace()
    r = await client.post(EXPORT_DOCX.format(sid=student_id), json=PLAN_BODY, headers=headers)
    assert r.status_code == 200, r.text
    assert "wordprocessingml" in r.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# PUT /hakim/interventions/{id}/status — sub_admin parity + audit logging
# ---------------------------------------------------------------------------

async def _create_intervention(client, headers, student_id):
    body = {"student_id": student_id, "action_type": "schedule_followup",
            "data": {"follow_up_date": "2026-08-01", "notes": ""}}
    r = await client.post("/ai/insights/intervention", json=body, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["intervention_id"]


@pytest.mark.asyncio
async def test_status_update_allowed_sub_admin_and_audited(client, school_admin_headers, school_sub_admin_headers, a_student):
    inv_id = await _create_intervention(client, school_admin_headers, a_student["id"])
    r = await client.put(f"/hakim/interventions/{inv_id}/status",
                         params={"new_status": "completed"},
                         headers=school_sub_admin_headers)
    assert r.status_code == 200, r.text

    logs = await gd_find(_db.session, "audit_logs",
                         {"entity_id": a_student["id"], "action": "intervention.status_change"})
    assert logs, "intervention.status_change audit row missing"
    assert any((l.get("details") or {}).get("intervention_id") == inv_id for l in logs)


@pytest.mark.asyncio
async def test_status_update_denied_teacher(client, school_admin_headers, teacher_headers, a_student):
    inv_id = await _create_intervention(client, school_admin_headers, a_student["id"])
    r = await client.put(f"/hakim/interventions/{inv_id}/status",
                         params={"new_status": "completed"},
                         headers=teacher_headers)
    assert r.status_code == 403
