from datetime import date
import uuid

import pytest

from dependencies import db
from engines.sql_utils import gd_find_one, gd_insert
from src.common.utils.date_only import normalize_optional_past_date


@pytest.mark.parametrize("value", [None, "", "   ", "\t\n"])
def test_optional_date_normalizes_blank_values_to_none(value):
    assert normalize_optional_past_date(value, today=date(2026, 9, 20)) is None


@pytest.mark.parametrize(
    "value",
    [
        "2026-2-03",
        "03-02-2026",
        "2026-02-03T00:00:00",
        " 2026-02-03 ",
        "not-a-date",
        20260203,
    ],
)
def test_optional_date_rejects_non_strict_gregorian_values(value):
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        normalize_optional_past_date(value, today=date(2026, 9, 20))


@pytest.mark.parametrize("value", ["2025-02-29", "2026-04-31", "2026-13-01"])
def test_optional_date_rejects_impossible_gregorian_dates(value):
    with pytest.raises(ValueError, match="valid Gregorian"):
        normalize_optional_past_date(value, today=date(2026, 9, 20))


def test_optional_date_accepts_leap_day_and_current_saudi_day():
    assert normalize_optional_past_date(
        "2024-02-29", today=date(2026, 9, 20)
    ) == "2024-02-29"
    assert normalize_optional_past_date(
        "2026-09-20", today=date(2026, 9, 20)
    ) == "2026-09-20"


def test_optional_date_rejects_dates_after_saudi_today():
    with pytest.raises(ValueError, match="future"):
        normalize_optional_past_date("2026-09-21", today=date(2026, 9, 20))


def _wizard_payload(suffix, date_of_birth, *, nested):
    common = {
        "full_name": f"اختبار الميلاد {suffix}",
        "email": f"birth_{suffix}@test.com",
        "phone": f"05{uuid.uuid4().int % 100000000:08d}",
        "national_id": f"10{uuid.uuid4().int % 100000000:08d}",
        "date_of_birth": date_of_birth,
    }
    if nested:
        return {"basic_info": {**common, "full_name_ar": common["full_name"]}}
    return common


@pytest.mark.asyncio
@pytest.mark.parametrize("nested", [True, False])
async def test_teacher_wizard_normalizes_blank_birth_date(
    client, school_principal_headers, nested
):
    suffix = uuid.uuid4().hex[:8]
    response = await client.post(
        "/teachers/create",
        json=_wizard_payload(suffix, "   ", nested=nested),
        headers=school_principal_headers,
    )
    assert response.status_code == 200, response.text
    teacher_id = response.json()["teacher"]["id"]
    teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id})
    assert teacher["date_of_birth"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("nested", [True, False])
async def test_teacher_wizard_rejects_invalid_birth_date(
    client, school_principal_headers, nested
):
    suffix = uuid.uuid4().hex[:8]
    response = await client.post(
        "/teachers/create",
        json=_wizard_payload(suffix, "2025-02-29", nested=nested),
        headers=school_principal_headers,
    )
    assert response.status_code == 422
    assert "date_of_birth" in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("clear_value", [None, " \t "])
async def test_principal_birth_date_update_distinguishes_omitted_and_clear(
    client, school_principal_headers, tenant_a, clear_value
):
    teacher_id = str(uuid.uuid4())
    await gd_insert(
        db.session,
        "teachers",
        {
            "id": teacher_id,
            "school_id": tenant_a,
            "tenant_id": tenant_a,
            "full_name": "اختبار تعديل الميلاد",
            "email": f"birth_update_{uuid.uuid4().hex[:8]}@test.com",
            "date_of_birth": "1990-05-06",
            "is_active": True,
        },
    )
    await db.session.flush()

    response = await client.put(
        f"/principal/teacher/{teacher_id}/basic-info",
        json={"nationality": "SA"},
        headers=school_principal_headers,
    )
    assert response.status_code == 200, response.text
    teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id})
    assert teacher["date_of_birth"] == "1990-05-06"

    response = await client.put(
        f"/principal/teacher/{teacher_id}/basic-info",
        json={"date_of_birth": clear_value},
        headers=school_principal_headers,
    )
    assert response.status_code == 200, response.text
    teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id})
    assert teacher["date_of_birth"] is None


@pytest.mark.asyncio
async def test_principal_birth_date_update_rejects_future_date(
    client, school_principal_headers, tenant_a
):
    teacher_id = str(uuid.uuid4())
    await gd_insert(
        db.session,
        "teachers",
        {
            "id": teacher_id,
            "school_id": tenant_a,
            "tenant_id": tenant_a,
            "full_name": "اختبار تاريخ مستقبلي",
            "email": f"birth_future_{uuid.uuid4().hex[:8]}@test.com",
            "date_of_birth": "1990-05-06",
            "is_active": True,
        },
    )
    await db.session.flush()
    response = await client.put(
        f"/principal/teacher/{teacher_id}/basic-info",
        json={"date_of_birth": "2999-01-01"},
        headers=school_principal_headers,
    )
    assert response.status_code == 422
    teacher = await gd_find_one(db.session, "teachers", {"id": teacher_id})
    assert teacher["date_of_birth"] == "1990-05-06"