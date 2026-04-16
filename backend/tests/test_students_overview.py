import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_overview_happy_path(client: AsyncClient, school_admin_headers, seeded_school):
    r = await client.get("/ai/insights/students-overview", headers=school_admin_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert set(data["summary"].keys()) >= {"total_students", "stable", "needs_followup", "at_risk", "excelling"}
    s = data["summary"]
    assert s["stable"]["count"] + s["needs_followup"]["count"] + s["at_risk"]["count"] + s["excelling"]["count"] <= s["total_students"]
    assert all(k in data["root_causes"] for k in ("attendance", "participation", "behaviour", "academic"))
    for row in data["risk_map"]:
        assert 0 <= row["x_academic"] <= 100
        assert 0 <= row["y_engagement"] <= 100
        assert row["category"] in {"stable", "needs_followup", "at_risk", "excelling"}
    for row in data["intervention_list"]:
        assert row["category"] in {"needs_followup", "at_risk"}


@pytest.mark.asyncio
async def test_overview_sorted_and_capped(client, school_admin_headers, many_students_school):
    r = await client.get("/ai/insights/students-overview", headers=school_admin_headers)
    assert r.status_code == 200, r.text
    items = r.json()["intervention_list"]
    assert len(items) <= 50
    scores = [x["risk_score"] for x in items]
    assert scores == sorted(scores)


@pytest.mark.asyncio
async def test_overview_tenant_isolation(client, tenant_a_admin, tenant_b_students):
    r = await client.get("/ai/insights/students-overview", headers=tenant_a_admin)
    assert r.status_code == 200, r.text
    ids_returned = {x["student_id"] for x in r.json()["risk_map"]}
    ids_b = {s["id"] for s in tenant_b_students}
    assert ids_returned.isdisjoint(ids_b)


@pytest.mark.asyncio
async def test_overview_refresh_busts_cache(client, school_admin_headers, seeded_school):
    r1 = await client.get("/ai/insights/students-overview", headers=school_admin_headers)
    assert r1.status_code == 200
    ts1 = r1.json()["last_updated"]
    r2 = await client.get("/ai/insights/students-overview?refresh=1", headers=school_admin_headers)
    assert r2.json()["last_updated"] >= ts1


@pytest.mark.asyncio
async def test_overview_denies_teacher(client, teacher_headers):
    r = await client.get("/ai/insights/students-overview", headers=teacher_headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_at_risk_legacy_shape_preserved(client, school_admin_headers, seeded_school):
    r = await client.get("/ai/insights/at-risk-students", headers=school_admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) <= 20
    if data:
        item = data[0]
        assert {"id", "name", "grade", "risk_level", "risk_type", "factors"} <= set(item.keys())


@pytest.mark.asyncio
async def test_at_risk_requires_admin_role(client, teacher_headers):
    r = await client.get("/ai/insights/at-risk-students", headers=teacher_headers)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_recommendations_ai_happy(client, school_admin_headers, seeded_school, monkeypatch):
    from routes import ai_routes_mod
    ai_routes_mod._REC_CACHE.clear()
    async def fake_openai(prompt: str):
        return '[{"type":"quantitative","text":"5 طلاب"},{"type":"positive","text":"تحسن"}]'
    monkeypatch.setattr(ai_routes_mod, "_call_openai_for_recommendations", fake_openai)
    r = await client.get("/ai/insights/recommendations-ai", headers=school_admin_headers)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["source"] == "openai"
    assert 1 <= len(j["recommendations"]) <= 6
    for x in j["recommendations"]:
        assert x["type"] in {"quantitative","academic","statistical_alert","positive","administrative"}
        assert x["text"] and x["icon"]


@pytest.mark.asyncio
async def test_recommendations_ai_fallback(client, school_admin_headers, seeded_school, monkeypatch):
    from routes import ai_routes_mod
    ai_routes_mod._REC_CACHE.clear()
    async def boom(prompt: str): raise RuntimeError("openai down")
    monkeypatch.setattr(ai_routes_mod, "_call_openai_for_recommendations", boom)
    r = await client.get("/ai/insights/recommendations-ai", headers=school_admin_headers)
    assert r.status_code == 200
    assert r.json()["source"] == "fallback"
    assert len(r.json()["recommendations"]) == 1


@pytest.mark.asyncio
async def test_recommendations_ai_role(client, teacher_headers):
    r = await client.get("/ai/insights/recommendations-ai", headers=teacher_headers)
    assert r.status_code == 403
