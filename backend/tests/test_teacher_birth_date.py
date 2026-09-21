from datetime import date
import uuid

import pytest

from dependencies import db
from engines.sql_utils import gd_find_one, gd_insert
from src.common.utils.date_only import (
    normalize_optional_past_date,
    resolve_optional_birth_dates,
)


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


def test_hijri_only_resolves_to_canonical_gregorian_date():
    assert resolve_optional_birth_dates(
        None, "11/10/1410", today=date(2026, 9, 20)
    ) == ("1990-05-06", "11/10/1410")


@pytest.mark.parametrize(
    "value",
    ["1/10/1410", "1410-10-11", "31/10/1410", "11/13/1410", "aa/bb/1410"],
)
def test_hijri_date_rejects_malformed_or_impossible_values(value):
    with pytest.raises(ValueError, match="Hijri"):
        resolve_optional_birth_dates(None, value, today=date(2026, 9, 20))


def test_hijri_date_rejects_unsupported_umm_al_qura_year():
    with pytest.raises(ValueError, match="supported Umm al-Qura range"):
        resolve_optional_birth_dates(None, "01/01/1300", today=date(2026, 9, 20))


def test_hijri_date_rejects_dates_after_saudi_today():
    with pytest.raises(ValueError, match="future"):
        resolve_optional_birth_dates(
            None, "10/04/1448", today=date(2026, 9, 20)
        )


def test_birth_date_pair_rejects_conflicting_calendars():
    with pytest.raises(ValueError, match="do not represent the same date"):
        resolve_optional_birth_dates(
            "1990-05-07", "11/10/1410", today=date(2026, 9, 20)
        )


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
@pytest.mark.parametrize(
    ("nested", "hijri_key", "gregorian_key"),
    [
        (True, "birth_date_hijri", None),
        (False, "birthDateHijri", "birthDateGregorian"),
    ],
)
async def test_teacher_wizard_accepts_hijri_only_and_returns_both_dates(
    client,
    school_principal_headers,
    nested,
    hijri_key,
    gregorian_key,
):
    suffix = uuid.uuid4().hex[:8]
    payload = _wizard_payload(suffix, None, nested=nested)
    target = payload["basic_info"] if nested else payload
    target.pop("date_of_birth")
    target[hijri_key] = "11/10/1410"
    if gregorian_key:
        target[gregorian_key] = None

    response = await client.post(
        "/teachers/create", json=payload, headers=school_principal_headers
    )
    assert response.status_code == 200, response.text
    teacher = response.json()["teacher"]
    assert teacher["date_of_birth"] == "1990-05-06"
    assert teacher["birth_date_hijri"] == "11/10/1410"
    stored = await gd_find_one(db.session, "teachers", {"id": teacher["id"]})
    assert stored["date_of_birth"] == "1990-05-06"


@pytest.mark.asyncio
async def test_teacher_wizard_returns_derived_hijri_for_gregorian_only(
    client, school_principal_headers
):
    suffix = uuid.uuid4().hex[:8]
    response = await client.post(
        "/teachers/create",
        json=_wizard_payload(suffix, "1990-05-06", nested=False),
        headers=school_principal_headers,
    )
    assert response.status_code == 200, response.text
    teacher = response.json()["teacher"]
    assert teacher["date_of_birth"] == "1990-05-06"
    assert teacher["birth_date_hijri"] == "11/10/1410"


@pytest.mark.asyncio
async def test_teacher_wizard_rejects_conflicting_birth_dates(
    client, school_principal_headers
):
    suffix = uuid.uuid4().hex[:8]
    payload = _wizard_payload(suffix, "1990-05-07", nested=True)
    payload["basic_info"]["birth_date_hijri"] = "11/10/1410"
    response = await client.post(
        "/teachers/create", json=payload, headers=school_principal_headers
    )
    assert response.status_code == 422
    assert "same date" in response.text


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


@pytest.mark.asyncio
async def test_principal_can_edit_hijri_birth_date_and_roundtrip_both_dates(
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
            "full_name": "اختبار تعديل هجري",
            "email": f"hijri_update_{uuid.uuid4().hex[:8]}@test.com",
            "date_of_birth": "1990-05-06",
            "is_active": True,
        },
    )
    await db.session.flush()

    response = await client.put(
        f"/principal/teacher/{teacher_id}/basic-info",
        json={"birthDateHijri": "12/10/1410"},
        headers=school_principal_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["date_of_birth"] == "1990-05-07"
    assert response.json()["birth_date_hijri"] == "12/10/1410"

    profile = await client.get(
        f"/principal/teacher/{teacher_id}/full-profile",
        headers=school_principal_headers,
    )
    assert profile.status_code == 200, profile.text
    basic = profile.json()["profile"]["basic_info"]
    assert basic["date_of_birth"] == "1990-05-07"
    assert basic["birth_date_hijri"] == "12/10/1410"
    stored = await gd_find_one(db.session, "teachers", {"id": teacher_id})
    assert stored["date_of_birth"] == "1990-05-07"
    assert "birth_date_hijri" not in stored


@pytest.mark.asyncio
async def test_principal_hijri_clear_and_conflict_semantics(
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
            "full_name": "اختبار مسح هجري",
            "email": f"hijri_clear_{uuid.uuid4().hex[:8]}@test.com",
            "date_of_birth": "1990-05-06",
            "is_active": True,
        },
    )
    await db.session.flush()

    conflict = await client.put(
        f"/principal/teacher/{teacher_id}/basic-info",
        json={
            "birthDateGregorian": "1990-05-07",
            "birthDateHijri": "11/10/1410",
        },
        headers=school_principal_headers,
    )
    assert conflict.status_code == 422
    stored = await gd_find_one(db.session, "teachers", {"id": teacher_id})
    assert stored["date_of_birth"] == "1990-05-06"

    cleared = await client.put(
        f"/principal/teacher/{teacher_id}/basic-info",
        json={"birth_date_hijri": "  "},
        headers=school_principal_headers,
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["date_of_birth"] is None
    assert cleared.json()["birth_date_hijri"] is None
