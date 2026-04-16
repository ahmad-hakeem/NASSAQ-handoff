import pytest

ROUTES_GET = [
    "/ai/insights/students-overview",
    "/ai/insights/recommendations-ai",
    "/ai/insights/at-risk-students",
]
ROUTE_POST = "/ai/insights/intervention"


async def _stub_openai(monkeypatch):
    from routes import ai_routes_mod
    ai_routes_mod._REC_CACHE.clear()
    async def fake(prompt): return '[{"type":"positive","text":"ok"}]'
    monkeypatch.setattr(ai_routes_mod, "_call_openai_for_recommendations", fake)


async def _check_allowed(client, headers, seeded_school, monkeypatch):
    await _stub_openai(monkeypatch)
    for route in ROUTES_GET:
        r = await client.get(route, headers=headers)
        assert r.status_code == 200, (route, r.text)


async def _check_denied(client, headers):
    for route in ROUTES_GET:
        r = await client.get(route, headers=headers)
        assert r.status_code == 403, (route, r.status_code)


@pytest.mark.asyncio
async def test_get_allowed_school_admin(client, school_admin_headers, seeded_school, monkeypatch):
    await _check_allowed(client, school_admin_headers, seeded_school, monkeypatch)


@pytest.mark.asyncio
async def test_get_allowed_school_sub_admin(client, school_sub_admin_headers, seeded_school, monkeypatch):
    await _check_allowed(client, school_sub_admin_headers, seeded_school, monkeypatch)


@pytest.mark.asyncio
async def test_get_allowed_school_principal(client, school_principal_headers, seeded_school, monkeypatch):
    await _check_allowed(client, school_principal_headers, seeded_school, monkeypatch)


@pytest.mark.asyncio
async def test_get_denied_teacher(client, teacher_headers):
    await _check_denied(client, teacher_headers)


@pytest.mark.asyncio
async def test_get_denied_parent(client, parent_headers):
    await _check_denied(client, parent_headers)


@pytest.mark.asyncio
async def test_get_denied_student(client, student_headers):
    await _check_denied(client, student_headers)


@pytest.mark.asyncio
async def test_get_denied_platform_admin(client, platform_admin_headers):
    await _check_denied(client, platform_admin_headers)


async def _post_intervention(client, headers, student_id):
    return await client.post(ROUTE_POST, json={
        "student_id": student_id,
        "action_type": "schedule_followup",
        "data": {"follow_up_date": "2026-04-30"},
    }, headers=headers)


@pytest.mark.asyncio
async def test_post_allowed_school_admin(client, school_admin_headers, a_student):
    r = await _post_intervention(client, school_admin_headers, a_student["id"])
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_post_allowed_school_sub_admin(client, school_sub_admin_headers, a_student):
    r = await _post_intervention(client, school_sub_admin_headers, a_student["id"])
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_post_allowed_school_principal(client, school_principal_headers, a_student):
    r = await _post_intervention(client, school_principal_headers, a_student["id"])
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_post_denied_teacher(client, teacher_headers, a_student):
    r = await _post_intervention(client, teacher_headers, a_student["id"])
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_post_denied_parent(client, parent_headers, a_student):
    r = await _post_intervention(client, parent_headers, a_student["id"])
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_post_denied_student(client, student_headers, a_student):
    r = await _post_intervention(client, student_headers, a_student["id"])
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_post_denied_platform_admin(client, platform_admin_headers, a_student):
    r = await _post_intervention(client, platform_admin_headers, a_student["id"])
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_401(client, a_student):
    for route in ROUTES_GET:
        r = await client.get(route)
        assert r.status_code == 401, (route, r.status_code)
    r = await client.post(ROUTE_POST, json={
        "student_id": a_student["id"], "action_type": "schedule_followup",
        "data": {"follow_up_date": "2026-04-30"}})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_intervention_cross_tenant_404(client, tenant_a_admin, tenant_b_student):
    r = await _post_intervention(client, tenant_a_admin, tenant_b_student["id"])
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_overview_data_isolation(client, tenant_a_admin, tenant_b_students):
    r = await client.get("/ai/insights/students-overview", headers=tenant_a_admin)
    assert r.status_code == 200
    data = r.json()
    ids_returned = (
        {x["student_id"] for x in data.get("risk_map", [])}
        | {x["student_id"] for x in data.get("intervention_list", [])}
    )
    ids_b = {s["id"] for s in tenant_b_students}
    assert ids_returned.isdisjoint(ids_b)
