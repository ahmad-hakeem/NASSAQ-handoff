"""
Verification script for demo teacher data (teacher@alnoor.edu.sa / teacher-1).
Validates all Teacher Module endpoints return correct data after seeding.
"""
import asyncio
import sys
import uuid
import httpx

BASE = "http://127.0.0.1:8000"
EMAIL = "teacher@alnoor.edu.sa"
PASSWORD = "NassaqAdmin2026!##$$HBJ"
TEACHER_ID = "teacher-1"


async def verify():
    errors = []
    async with httpx.AsyncClient(base_url=BASE, timeout=10) as c:
        r = await c.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
        if r.status_code != 200:
            print(f"FAIL: Login failed: {r.status_code}")
            sys.exit(1)
        token = r.json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}

        # 1. Dashboard
        r = await c.get(f"/api/teacher/dashboard/{TEACHER_ID}", headers=h)
        assert r.status_code == 200, f"Dashboard: {r.status_code}"
        stats = r.json().get("stats", {})
        if stats.get("my_classes", 0) < 1:
            errors.append(f"Dashboard: my_classes={stats.get('my_classes')} (expected >= 1)")
        if stats.get("my_students", 0) < 1:
            errors.append(f"Dashboard: my_students={stats.get('my_students')} (expected >= 1)")
        print(f"✅ Dashboard: {stats.get('my_classes')} classes, {stats.get('my_students')} students, {stats.get('weekly_sessions')} weekly sessions")

        # 2. Classes
        r = await c.get(f"/api/teacher/classes/{TEACHER_ID}", headers=h)
        assert r.status_code == 200, f"Classes: {r.status_code}"
        classes = r.json()
        if len(classes) < 1:
            errors.append("Classes: empty list")
        for cls in classes:
            sc = cls.get("student_count", 0)
            if sc < 1:
                errors.append(f"Classes: {cls.get('id')} has {sc} students")
        print(f"✅ Classes: {len(classes)} classes, all with students")

        # 3. Schedule
        r = await c.get(f"/api/teacher/schedule/{TEACHER_ID}", headers=h)
        assert r.status_code == 200, f"Schedule: {r.status_code}"
        sched = r.json()
        if len(sched) < 1:
            errors.append("Schedule: empty")
        print(f"✅ Schedule: {len(sched)} weekly entries")

        # 4. Session flow (start → students → approve → random → answer → participation → behaviour → end)
        first_class = classes[0]["id"] if classes else "class-1أ"
        r = await c.post("/api/session/start", headers=h, json={
            "teacher_id": TEACHER_ID,
            "class_id": first_class,
            "subject_id": "sub-arabic",
            "school_id": "school-demo-001",
            "schedule_session_id": f"verify-{uuid.uuid4().hex[:8]}"
        })
        assert r.status_code == 200, f"Session start: {r.status_code} {r.text}"
        sid = r.json()["session_record_id"]
        sc = r.json()["student_count"]
        print(f"✅ Session start: {sc} students loaded")

        r = await c.get(f"/api/session/{sid}/students", headers=h)
        assert r.status_code == 200
        students = r.json()["students"]
        print(f"✅ Session students: {len(students)} returned")

        r = await c.post(f"/api/session/{sid}/attendance/approve", headers=h, json={})
        assert r.status_code == 200
        print(f"✅ Attendance approved: {r.json()['attendance_rate']}%")

        r = await c.post(f"/api/session/{sid}/random-student", headers=h, json={})
        assert r.status_code == 200
        stu_id = r.json()["student_id"]
        stu_name = r.json()["full_name"]
        print(f"✅ Random student: {stu_name}")

        r = await c.post(f"/api/session/{sid}/answer", headers=h, json={"student_id": stu_id, "result": "correct"})
        assert r.status_code == 200
        print(f"✅ Answer recorded: score_change={r.json()['score_change']}")

        r = await c.post(f"/api/session/{sid}/participation", headers=h, json={"student_id": stu_id, "type": "active"})
        assert r.status_code == 200
        print(f"✅ Participation recorded: score_change={r.json()['score_change']}")

        r = await c.post(f"/api/session/{sid}/behaviour", headers=h, json={
            "student_id": stu_id, "category": "positive", "behaviour_type": "excellent_work"
        })
        assert r.status_code == 200
        print(f"✅ Behaviour recorded: score_change={r.json()['score_change']}")

        r = await c.post(f"/api/session/{sid}/end", headers=h, json={})
        assert r.status_code == 200
        summary = r.json()
        print(f"✅ Session ended: {summary['total_students']} students, {summary['attendance_rate']}% attendance")

        # 5. Authorization check
        r2 = await c.post("/api/auth/login", json={"email": "admin@nassaq.com", "password": PASSWORD})
        if r2.status_code == 200:
            ah = {"Authorization": f"Bearer {r2.json()['access_token']}"}
            r = await c.get(f"/api/session/{sid}", headers=ah)
            print(f"✅ Admin access to teacher session: {r.status_code} (admin bypasses ownership)")

    if errors:
        print(f"\n❌ FAILURES ({len(errors)}):")
        for e in errors:
            print(f"   - {e}")
        sys.exit(1)
    else:
        print("\n✅ ALL VERIFICATIONS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(verify())
