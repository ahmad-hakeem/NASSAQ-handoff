"""
Regression tests for the Student Risk Radar scale semantics.

Bug fixed: GET /ai/insights/at-risk-students returned the raw health
metric (attendance % / grade %) as `risk_level`, while the frontend
renders `risk_level` as a TRUE risk scale (>=70 red/high, >=50 amber).
A student with 75% attendance was shown as HIGH risk while a student
with 20% attendance was shown as LOW risk.

Contract locked in here (teacher path + admin path):
  - `risk_level` is 0..100 where HIGHER = MORE risk.
  - A severely absent student must have a HIGHER risk_level than a
    mildly absent one.
  - A mildly at-risk student (75% attendance, no grade issues) must be
    flagged but land BELOW the FE moderate band (risk_level < 50).
  - A severely absent student (20% attendance) must land in the FE high
    band (risk_level >= 70).
  - The list is sorted worst-first (non-increasing risk_level).
  - The attendance factor label discloses the 30-day window so it can't
    be confused with the profile's all-time attendance rate.
"""
import uuid
import pytest
from datetime import datetime, timedelta, timezone

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_insert


async def _seed_attendance_mix(school_id: str, student_id: str,
                               present: int, absent: int) -> None:
    """Seed recent (within 30d) attendance rows: `present` present days
    then `absent` absent days, most recent first."""
    today = datetime.now(timezone.utc)
    day = 1
    for _ in range(present):
        await gd_insert(db.session, "attendance", {
            "id": str(uuid.uuid4()),
            "school_id": school_id,
            "student_id": student_id,
            "date": (today - timedelta(days=day)).strftime("%Y-%m-%d"),
            "status": "present",
        })
        day += 1
    for _ in range(absent):
        await gd_insert(db.session, "attendance", {
            "id": str(uuid.uuid4()),
            "school_id": school_id,
            "student_id": student_id,
            "date": (today - timedelta(days=day)).strftime("%Y-%m-%d"),
            "status": "absent",
        })
        day += 1


async def _mk_school_teacher_with_class(tenant_id: str):
    user_id = str(uuid.uuid4())
    teacher_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": user_id, "role": UserRole.TEACHER.value, "tenant_id": tenant_id,
        "teacher_id": teacher_id, "email": f"rt-{user_id}@t.test",
        "full_name": "RadarTeacher", "is_active": True, "password_hash": "x",
    })
    await gd_insert(db.session, "teachers", {
        "id": teacher_id, "school_id": tenant_id, "user_id": user_id,
        "full_name": "RadarTeacher",
    })
    class_id = str(uuid.uuid4())
    await gd_insert(db.session, "classes", {
        "id": class_id, "school_id": tenant_id, "name": "Radar-class",
    })
    await gd_insert(db.session, "teacher_class_assignments", {
        "id": str(uuid.uuid4()), "teacher_id": teacher_id,
        "school_id": tenant_id, "class_id": class_id,
    })
    headers = {"Authorization": "Bearer " + create_access_token({
        "sub": user_id, "role": UserRole.TEACHER.value,
        "tenant_id": tenant_id, "teacher_id": teacher_id,
    })}
    return {"headers": headers, "class_id": class_id}


async def _seed_student(tenant_id: str, class_id: str, name: str) -> str:
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "students", {
        "id": sid, "school_id": tenant_id, "full_name": name,
        "class_id": class_id, "is_active": True,
    })
    return sid


@pytest.mark.asyncio
async def test_teacher_radar_risk_scale_higher_means_worse(client, tenant_a):
    t = await _mk_school_teacher_with_class(tenant_a)

    # Mild: 15 present / 5 absent = 75% attendance -> flagged (<80) but
    # must NOT be rendered as high risk.
    mild_id = await _seed_student(tenant_a, t["class_id"], "Mild-Risk")
    await _seed_attendance_mix(tenant_a, mild_id, present=15, absent=5)

    # Severe: 2 present / 8 absent = 20% attendance -> must be high risk.
    severe_id = await _seed_student(tenant_a, t["class_id"], "Severe-Risk")
    await _seed_attendance_mix(tenant_a, severe_id, present=2, absent=8)

    # Healthy: 100% attendance -> must not be flagged at all.
    healthy_id = await _seed_student(tenant_a, t["class_id"], "Healthy")
    await _seed_attendance_mix(tenant_a, healthy_id, present=10, absent=0)

    r = await client.get("/ai/insights/at-risk-students", headers=t["headers"])
    assert r.status_code == 200, r.text
    body = r.json()
    by_id = {row["id"]: row for row in body}

    assert healthy_id not in by_id, "healthy student must not be flagged"
    assert mild_id in by_id and severe_id in by_id

    mild = by_id[mild_id]
    severe = by_id[severe_id]

    # True risk scale: higher = worse.
    assert 0 <= mild["risk_level"] <= 100
    assert 0 <= severe["risk_level"] <= 100
    assert severe["risk_level"] > mild["risk_level"], (
        f"severe (20% att) risk_level={severe['risk_level']} must exceed "
        f"mild (75% att) risk_level={mild['risk_level']}"
    )
    # 75% attendance -> risk 25: below the FE moderate band (>=50).
    assert mild["risk_level"] < 50, (
        f"mild student must not reach the FE moderate/high bands, "
        f"got {mild['risk_level']}"
    )
    # 20% attendance -> risk 80: inside the FE high band (>=70).
    assert severe["risk_level"] >= 70, (
        f"severe student must reach the FE high band, got {severe['risk_level']}"
    )

    # Worst-first ordering so the [:20] cut keeps the worst cases.
    levels = [row["risk_level"] for row in body]
    assert levels == sorted(levels, reverse=True)

    # The attendance factor must disclose the 30-day window.
    assert any("30" in f for f in mild["factors"]), mild["factors"]
    assert mild["risk_type"] == "attendance"


@pytest.mark.asyncio
async def test_admin_radar_risk_scale_inverted_from_health(
    client, seeded_school
):
    """Admin path maps the hakim health score (higher = better) onto the
    radar risk scale (higher = worse). The worst student in the
    intervention list must come out FIRST with the HIGHEST risk_level."""
    target = seeded_school.students[0]
    today = datetime.now(timezone.utc)
    for i in range(10):
        await gd_insert(db.session, "attendance", {
            "id": str(uuid.uuid4()),
            "school_id": seeded_school.id,
            "student_id": target["id"],
            "date": (today - timedelta(days=i + 1)).strftime("%Y-%m-%d"),
            "status": "absent",
        })
    await gd_insert(db.session, "student_grades", {
        "id": str(uuid.uuid4()),
        "tenant_id": seeded_school.id,
        "student_id": target["id"],
        "percentage": 35.0,
        "graded_at": datetime.now(timezone.utc).isoformat(),
    })

    admin_id = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": admin_id, "role": UserRole.SCHOOL_ADMIN.value,
        "tenant_id": seeded_school.id, "email": f"ad-{admin_id}@t.test",
        "full_name": "Radar Admin", "is_active": True, "password_hash": "x",
    })
    headers = {"Authorization": "Bearer " + create_access_token({
        "sub": admin_id, "role": UserRole.SCHOOL_ADMIN.value,
        "tenant_id": seeded_school.id,
    })}

    # Bust the 5-minute overview cache so this test sees fresh data.
    from routes import ai_routes_mod
    ai_routes_mod._OVERVIEW_CACHE.clear()

    r = await client.get("/ai/insights/at-risk-students", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body, "seeded chronic-absence student must produce a non-empty list"

    for row in body:
        assert 0 <= row["risk_level"] <= 100

    # intervention_list is ordered worst-health-first; after inversion the
    # radar list must be non-increasing in risk_level (worst first).
    levels = [row["risk_level"] for row in body]
    assert levels == sorted(levels, reverse=True)

    # The seeded chronic-absence + failing-grade student is the worst
    # signal in the school; it must surface with a meaningfully high risk
    # (the old bug would have returned its low HEALTH score directly and
    # any healthy-ish flagged student would have outranked it).
    target_rows = [row for row in body if row["id"] == target["id"]]
    assert target_rows, "seeded at-risk student missing from radar"
    assert target_rows[0]["risk_level"] == max(levels), (
        "worst student must carry the highest risk_level"
    )
    # Window disclosure applies to the 30-day-windowed components only
    # (attendance/participation/behaviour); the academic fallback reads
    # all-time grades, so its label must NOT claim a 30-day window.
    row = target_rows[0]
    assert row["factors"], "factors must not be empty"
    if row["risk_type"] == "academic":
        assert all("30" not in f for f in row["factors"]), row["factors"]
    else:
        assert any("30" in f for f in row["factors"]), row["factors"]
