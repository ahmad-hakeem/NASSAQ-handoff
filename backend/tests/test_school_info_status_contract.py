"""School info is a read-only lifecycle projection, never an activation fallback."""
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from dependencies import get_current_user
from src.modules.schools.controllers.school_settings_mod import router
from src.modules.schools.services import school_settings_service as service


@pytest.mark.asyncio
@pytest.mark.parametrize("stored,expected", [
    ("active", "active"),
    ("suspended", "suspended"),
    ("pending", "pending"),
    ("setup", "setup"),
    ("archived", "archived"),
    ("pending_hard_delete", "pending_hard_delete"),
    (None, "unknown"),
    ("", "unknown"),
    ("inactive", "unknown"),
    ("ACTIVE", "unknown"),
    (" active ", "unknown"),
    ("legacy", "unknown"),
])
async def test_school_info_lifecycle_contract(monkeypatch, stored, expected):
    school = {"id": "school-status-test", "status": stored, "is_active": True}
    lookup = AsyncMock(side_effect=[school, None])
    monkeypatch.setattr(service, "gd_find_one", lookup)
    monkeypatch.setattr(service, "resolve_school_context", AsyncMock(return_value=school["id"]))
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "principal-test", "role": "school_principal", "tenant_id": school["id"],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/school/info")
    assert response.status_code == 200
    assert response.json()["status"] == expected
    assert "is_active" not in response.json()
    assert school["status"] == stored  # no read-time repair / activation
    assert lookup.await_args_list[0].args[2] == {"id": school["id"]}


@pytest.mark.asyncio
async def test_school_info_reloads_status_without_context_cache(monkeypatch):
    lookup = AsyncMock(side_effect=[
        {"id": "school", "status": "active"}, None,
        {"id": "school", "status": "suspended"}, None,
    ])
    monkeypatch.setattr(service, "gd_find_one", lookup)
    monkeypatch.setattr(service, "resolve_school_context", AsyncMock(return_value="school"))
    user = {"id": "principal", "tenant_id": "school", "role": "school_principal"}
    first = await service.SchoolSettingsService.get_school_info(None, user)
    second = await service.SchoolSettingsService.get_school_info(None, user)
    assert (first["status"], second["status"]) == ("active", "suspended")
    assert lookup.await_count == 4