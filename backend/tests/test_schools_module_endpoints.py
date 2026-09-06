import pytest
import uuid
from datetime import datetime, timezone
from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert, gd_delete_one
from src.modules.schools.services.school_crud_service import SchoolCrudService


@pytest.mark.asyncio
async def test_schools_numbers_aggregation():
    """Verify get_schools_numbers returns aggregated counts."""
    stats = await SchoolCrudService.get_schools_numbers(db.session)
    assert "total" in stats
    assert "active" in stats
    assert "suspended" in stats
    assert "pending" in stats
    assert "drafts" in stats
    assert "totalStudents" in stats
    assert "totalTeachers" in stats
    assert "totalClasses" in stats
    assert isinstance(stats["total"], int)
    assert isinstance(stats["totalStudents"], int)
    assert isinstance(stats["totalClasses"], int)


@pytest.mark.asyncio
async def test_get_draft_schools():
    """Verify get_draft_schools returns schools with setup status."""
    draft_id = f"test-draft-{uuid.uuid4()}"
    await gd_insert(db.session, "schools", {
        "id": draft_id,
        "name": "Test Draft School",
        "code": f"DRAFT-{uuid.uuid4().hex[:6].upper()}",
        "status": "setup",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.session.flush()

    try:
        drafts = await SchoolCrudService.get_draft_schools(db.session)
        found = any(d.id == draft_id for d in drafts)
        assert found, "Created draft school should be present in get_draft_schools output"
    finally:
        await gd_delete_one(db.session, "schools", {"id": draft_id})
        await db.session.flush()


@pytest.mark.asyncio
async def test_get_schools_list_with_class_counts():
    """Verify get_schools_list includes class_count and student_count."""
    schools = await SchoolCrudService.get_schools_list(db.session)
    assert isinstance(schools, list)
    if schools:
        first = schools[0]
        assert hasattr(first, "class_count")
        assert hasattr(first, "student_count")
        assert hasattr(first, "teacher_count")


@pytest.mark.asyncio
async def test_schools_routes_via_client(client, platform_admin_headers):
    """Verify HTTP endpoints /api/schools/numbers, /api/schools/draft, and /api/schools."""
    headers = platform_admin_headers

    # 1. /schools/numbers
    res_numbers = await client.get("/schools/numbers", headers=headers)
    assert res_numbers.status_code == 200
    data_numbers = res_numbers.json()
    assert "total" in data_numbers
    assert "active" in data_numbers
    assert "drafts" in data_numbers

    # 2. /schools/draft
    res_drafts = await client.get("/schools/draft", headers=headers)
    assert res_drafts.status_code == 200
    assert isinstance(res_drafts.json(), list)

    # 3. /schools (unpaginated backward-compatibility)
    res_schools = await client.get("/schools", headers=headers)
    assert res_schools.status_code == 200
    assert isinstance(res_schools.json(), list)

    # 4. /schools?page=1&limit=5 (paginated)
    res_paginated = await client.get("/schools?page=1&limit=5", headers=headers)
    assert res_paginated.status_code == 200
    data_paginated = res_paginated.json()
    assert "schools" in data_paginated
    assert "total" in data_paginated
    assert "page" in data_paginated
    assert "limit" in data_paginated
    assert "total_pages" in data_paginated
    assert data_paginated["page"] == 1
    assert data_paginated["limit"] == 5
    assert isinstance(data_paginated["schools"], list)
