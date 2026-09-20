import uuid
import pytest
from dependencies import db
from engines.sql_utils import gd_insert, gd_find_one


@pytest.mark.asyncio
async def test_teacher_full_profile_returns_professional_data(client, school_principal_headers, tenant_a):
    # 1. Create a teacher with wizard payload
    wizard_payload = {
        "basic_info": {
            "full_name_ar": "أحمد المهني",
            "email": f"ahmed_{uuid.uuid4().hex[:6]}@test.com",
            "phone": f"05{uuid.uuid4().int % 100000000:08d}",
            "national_id": f"10{uuid.uuid4().int % 100000000:08d}",
            "gender": "male",
            "nationality": "SA",
        },
        "qualifications": {
            "academic_degree": "bachelor",
            "specialization": "رياضيات",
            "teacher_rank": "teacher",
            "years_of_experience": 4,
        },
        "subjects": {
            "subject_ids": [],
            "grade_ids": [],
            "max_periods_per_week": 24,
        },
        "schedule": {
            "contract_type": "permanent",
            "available_days": ["sunday", "monday", "tuesday", "wednesday", "thursday"],
        },
    }

    create_resp = await client.post(
        "/teachers/create",
        json=wizard_payload,
        headers=school_principal_headers,
    )
    assert create_resp.status_code == 200, create_resp.text
    create_data = create_resp.json()
    assert create_data.get("success") is True
    teacher_id = create_data.get("teacher", {}).get("id") or create_data.get("teacher_id")

    # 2. Query full-profile endpoint
    profile_resp = await client.get(
        f"/principal/teacher/{teacher_id}/full-profile",
        headers=school_principal_headers,
    )
    assert profile_resp.status_code == 200, profile_resp.text
    profile_data = profile_resp.json()
    assert profile_data.get("success") is True

    prof_info = profile_data["profile"]["professional_info"]
    assert prof_info["academic_degree"] == "bachelor"
    assert prof_info["teacher_rank"] == "teacher"
    assert prof_info["contract_type"] == "permanent"
    assert prof_info["years_of_experience"] == 4
    assert prof_info["specialization"] == "رياضيات"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "qualifications, expected",
    [
        ({}, (None, None, None)),
        (
            {"academic_degree": None, "teacher_rank": None, "years_of_experience": None},
            (None, None, None),
        ),
        (
            {"academic_degree": "", "teacher_rank": "   ", "years_of_experience": ""},
            (None, None, None),
        ),
        ({"years_of_experience": "   "}, (None, None, None)),
        ({"academic_degree": "bachelor"}, ("bachelor", None, None)),
        (
            {"academic_degree": "master", "years_of_experience": 7},
            ("master", None, 7),
        ),
        ({"teacher_rank": "teacher"}, (None, "teacher", None)),
        ({"years_of_experience": 0}, (None, None, 0)),
        (
            {
                "academic_degree": "bachelor",
                "teacher_rank": "teacher",
                "years_of_experience": 6,
            },
            ("bachelor", "teacher", 6),
        ),
    ],
)
async def test_teacher_create_normalizes_optional_qualifications(
    client, school_principal_headers, qualifications, expected
):
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "basic_info": {
            "full_name_ar": f"اختبار المؤهلات {suffix}",
            "email": f"qual_{suffix}@test.com",
            "phone": f"05{uuid.uuid4().int % 100000000:08d}",
            "national_id": f"10{uuid.uuid4().int % 100000000:08d}",
        },
        "qualifications": qualifications,
        "subjects": {"subject_ids": [], "grade_ids": []},
    }
    response = await client.post("/teachers/create", json=payload, headers=school_principal_headers)
    assert response.status_code == 200, response.text
    teacher_id = response.json()["teacher"]["id"]
    profile = await client.get(
        f"/principal/teacher/{teacher_id}/full-profile",
        headers=school_principal_headers,
    )
    assert profile.status_code == 200, profile.text
    professional = profile.json()["profile"]["professional_info"]
    assert (
        professional["academic_degree"],
        professional["teacher_rank"],
        professional["years_of_experience"],
    ) == expected
    teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id})
    assert teacher["academic_degree"] == expected[0]
    assert teacher["qualification"] == expected[0]
    assert teacher["teacher_rank"] == expected[1]
    assert teacher["rank"] == expected[1]
    assert teacher["years_of_experience"] == expected[2]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "qualifications, field",
    [
        ({"years_of_experience": -1}, "years_of_experience"),
        ({"years_of_experience": "not-a-number"}, "years_of_experience"),
        ({"academic_degree": "unsupported-degree"}, "academic_degree"),
        ({"teacher_rank": "unsupported-rank"}, "teacher_rank"),
    ],
)
async def test_teacher_create_rejects_invalid_qualifications(
    client, school_principal_headers, qualifications, field
):
    suffix = uuid.uuid4().hex[:8]
    payload = {
        "basic_info": {
            "full_name_ar": f"اختبار مؤهل غير صالح {suffix}",
            "email": f"invalid_qual_{suffix}@test.com",
            "phone": f"05{uuid.uuid4().int % 100000000:08d}",
            "national_id": f"10{uuid.uuid4().int % 100000000:08d}",
        },
        "qualifications": qualifications,
    }
    response = await client.post("/teachers/create", json=payload, headers=school_principal_headers)
    assert response.status_code == 422, response.text
    assert field in response.text


@pytest.mark.asyncio
async def test_teacher_full_profile_legacy_field_fallback(client, school_principal_headers, tenant_a):
    # Setup legacy teacher in DB with 'qualification' and 'rank' and 'contract'
    legacy_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": legacy_id,
        "school_id": tenant_a,
        "tenant_id": tenant_a,
        "full_name": "سارة القديمة",
        "email": f"sara_{uuid.uuid4().hex[:6]}@test.com",
        "phone": f"05{uuid.uuid4().int % 100000000:08d}",
        "qualification": "master",
        "rank": "senior_teacher",
        "contract": "contract",
        "years_of_experience": 8,
        "is_active": True,
    })
    await db.session.flush()

    resp = await client.get(
        f"/principal/teacher/{legacy_id}/full-profile",
        headers=school_principal_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    prof_info = data["profile"]["professional_info"]

    assert prof_info["academic_degree"] == "master"
    assert prof_info["teacher_rank"] == "senior_teacher"
    assert prof_info["contract_type"] == "contract"
    assert prof_info["years_of_experience"] == 8


@pytest.mark.asyncio
async def test_update_teacher_professional_info_persists_and_reflects(client, school_principal_headers, tenant_a):
    # 1. Create a teacher
    t_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": t_id,
        "school_id": tenant_a,
        "tenant_id": tenant_a,
        "full_name": "خالد التحديث",
        "email": f"khaled_{uuid.uuid4().hex[:6]}@test.com",
        "phone": f"05{uuid.uuid4().int % 100000000:08d}",
        "academic_degree": "bachelor",
        "teacher_rank": "teacher",
        "contract_type": "permanent",
        "years_of_experience": 2,
        "is_active": True,
    })
    await db.session.flush()

    # 2. Update professional info
    update_payload = {
        "academic_degree": "doctorate",
        "teacher_rank": "expert",
        "contract_type": "contract",
        "years_of_experience": 10,
        "employee_number": "EMP-5555",
    }
    put_resp = await client.put(
        f"/principal/teacher/{t_id}/professional-info",
        json=update_payload,
        headers=school_principal_headers,
    )
    assert put_resp.status_code == 200, put_resp.text
    assert put_resp.json()["success"] is True

    # 3. Verify via full-profile
    get_resp = await client.get(
        f"/principal/teacher/{t_id}/full-profile",
        headers=school_principal_headers,
    )
    assert get_resp.status_code == 200
    prof = get_resp.json()["profile"]["professional_info"]
    assert prof["academic_degree"] == "doctorate"
    assert prof["teacher_rank"] == "expert"
    assert prof["contract_type"] == "contract"
    assert prof["years_of_experience"] == 10
    assert prof["employee_number"] == "EMP-5555"


@pytest.mark.asyncio
async def test_update_teacher_professional_info_distinguishes_omitted_and_cleared_fields(
    client, school_principal_headers, tenant_a
):
    teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": teacher_id,
        "school_id": tenant_a,
        "tenant_id": tenant_a,
        "full_name": "اختبار مسح المؤهلات",
        "email": f"clear_{uuid.uuid4().hex[:8]}@test.com",
        "academic_degree": "master",
        "qualification": "master",
        "teacher_rank": "expert",
        "rank": "expert",
        "years_of_experience": 7,
        "is_active": True,
    })
    await db.session.flush()

    response = await client.put(
        f"/principal/teacher/{teacher_id}/professional-info",
        json={"academic_degree": None, "teacher_rank": "", "years_of_experience": None},
        headers=school_principal_headers,
    )
    assert response.status_code == 200, response.text
    teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id})
    assert teacher["academic_degree"] is None
    assert teacher["qualification"] is None
    assert teacher["teacher_rank"] is None
    assert teacher["rank"] is None
    assert teacher["years_of_experience"] is None

    response = await client.put(
        f"/principal/teacher/{teacher_id}/professional-info",
        json={"contract_type": "contract"},
        headers=school_principal_headers,
    )
    assert response.status_code == 200, response.text
    teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id})
    assert teacher["contract_type"] == "contract"
    assert teacher["academic_degree"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {"academic_degree": "unsupported-degree"},
    {"teacher_rank": "unsupported-rank"},
    {"years_of_experience": -1},
    {"years_of_experience": "not-a-number"},
])
async def test_update_teacher_professional_info_rejects_invalid_qualifications(
    client, school_principal_headers, tenant_a, payload
):
    teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "teachers", {
        "id": teacher_id, "school_id": tenant_a, "tenant_id": tenant_a,
        "full_name": "اختبار تحقق المؤهلات",
        "email": f"invalid_edit_{uuid.uuid4().hex[:8]}@test.com",
        "academic_degree": "master", "teacher_rank": "teacher",
        "years_of_experience": 1, "is_active": True,
    })
    await db.session.flush()
    response = await client.put(
        f"/principal/teacher/{teacher_id}/professional-info",
        json=payload, headers=school_principal_headers,
    )
    assert response.status_code == 422, response.text
