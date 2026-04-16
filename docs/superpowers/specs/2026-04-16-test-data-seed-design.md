# Test Data Seed Design — NASSAQ Platform
**Date:** 2026-04-16
**Status:** Approved

---

## Objective

Populate the NASSAQ platform with realistic, comprehensive test data covering two fully isolated school tenants. The goal is to enable end-to-end testing of all platform features including multi-tenancy isolation, scheduling, attendance, behavior tracking, AI insights, the Product Hub, and the parent/student portals.

---

## Approach: Hybrid Seeding

- **Direct DB writes (SQLAlchemy)** for foundational structural data: schools, users, teachers, students, parents, classes, subjects, time slots, teacher assignments, and the timetable skeleton.
- **API calls (httpx against the live server)** for operational data: attendance records, behavior logs, product hub issues, and notifications — exercising the real endpoint logic.

The seed script is idempotent: it checks for existing data before inserting, so re-running it is safe.

---

## Section 1 — Schools (Tenants)

| Field | School A | School B |
|---|---|---|
| `name` (AR) | مدرسة الفارابي للتعليم الأساسي | أكاديمية ابن سينا الدولية |
| `name_en` | Al-Farabi School | Ibn Sina International Academy |
| Type | Public | Private / International |
| Grades | 1–12 | 1–12 |
| Status | active | active |
| Region | الرياض | جدة |

Each school is a fully isolated tenant. No users, students, classes, or operational data from School A should be visible in School B's context and vice versa.

---

## Section 2 — Users & Roles

### Platform Admin (shared, no tenant)
| Field | Value |
|---|---|
| Email | `admin@nassaq.com` |
| Password | `Test@1234` |
| Role | `platform_admin` |

### Per School — School Admin (×2)
| Role | Email Pattern | Notes |
|---|---|---|
| `school_admin` (primary) | `mudeer@faarabi.edu` / `mudeer@ibnsina.edu` | Full admin access |
| `school_admin` (deputy) | `naeb@faarabi.edu` / `naeb@ibnsina.edu` | Full admin access |

### Per School — Teachers (×18)
- 18 teachers per school
- Arabic full names, Gulf naming convention (e.g., أحمد بن خالد الرشيدي)
- Each teacher assigned a specialization matching the subjects they teach
- Email: `firstname.lastname@faarabi.edu` / `firstname.lastname@ibnsina.edu`
- Password: `Test@1234` for all
- Role: `teacher`

### Per School — Students (~175)
- Spread across grades 1–12 (~14–15 per grade)
- Gender mix: ~50/50
- Arabic full names
- Each linked to a class, parent, and grade
- Student numbers: `FAR-001` to `FAR-175` (School A), `IBN-001` to `IBN-175` (School B)

### Per School — Parents (~160)
- ~1 parent per student; siblings (where applicable) share one parent
- Role: `parent`
- Linked to 1–3 students via the `Parent.students` relationship
- Email: `walid.xxx@gmail.com` pattern
- Password: `Test@1234`

---

## Section 3 — Academic Structure

### Classes
- 12 grade levels per school
- Grades 1–6: 2 classes each (e.g., الصف الأول أ, الصف الأول ب)
- Grades 7–12: 1 class each
- Total: 18 classes per school

### Subjects (14 core subjects)
| Subject (AR) | Subject (EN) | Category |
|---|---|---|
| اللغة العربية | Arabic Language | Core |
| اللغة الإنجليزية | English Language | Core |
| الرياضيات | Mathematics | Core |
| العلوم | Science | Core |
| التربية الإسلامية | Islamic Studies | Core |
| الدراسات الاجتماعية | Social Studies | Core |
| التربية البدنية | Physical Education | Elective |
| التربية الفنية | Art | Elective |
| الحاسوب | Computer Science | Elective |
| التاريخ | History | Core |
| الجغرافيا | Geography | Core |
| الكيمياء | Chemistry | Secondary |
| الفيزياء | Physics | Secondary |
| الأحياء | Biology | Secondary |

### Teacher Assignments
- Each teacher assigned 1–3 subjects across specific grade levels
- No teacher assigned more than 28 periods/week
- No conflicts (teacher in two places at once)

### Time Slots (Gulf work week: Sunday–Thursday)
- 7 periods per day
- Period duration: 45 minutes
- Break: after period 4 (20 minutes)
- Times: 07:30, 08:15, 09:00, 09:45 | break | 10:45, 11:30, 12:15

### Timetable
- One complete weekly timetable per class
- All 18 classes × 7 periods × 5 days = 630 `ScheduleSession` records per school
- Seeded directly into DB

---

## Section 4 — Operational Data (API-Driven)

### Attendance
- **4 weeks** of historical records (Sun–Thu × 4 weeks × all sessions)
- Distribution: 85% present, 10% absent, 5% late
- Covers every student in every session they are scheduled
- API endpoint: `POST /api/attendance/bulk`

### Behavior Logs
- 3–5 entries per student
- Mix: positive commendations (~60%), minor incidents (~40%)
- Random distribution across the 4-week period
- API endpoint: `POST /api/behaviour`

### Product Hub Issues (~10 per school)
- Mix of statuses: open (4), in_progress (3), resolved (3)
- Mix of priorities: low, medium, high, critical
- Submitted by different user roles (admin, teacher, parent)
- API endpoint: `POST /api/product-hub/issues`

### Notifications
- At least 1 notification per parent (attendance alert or behavior update)
- At least 1 system notification per teacher (timetable update)
- API endpoint: `POST /api/notifications`

---

## Section 5 — Reference File

After seeding, `TEST_CREDENTIALS.md` is written to the project root with every login credential grouped by school and role. Format:

```
# NASSAQ Test Credentials

## Platform Admin (cross-school)
  Email: admin@nassaq.com
  Password: Test@1234

## School A — مدرسة الفارابي
  School Admin:  mudeer@faarabi.edu / Test@1234
  Deputy Admin:  naeb@faarabi.edu / Test@1234
  Teacher (sample): ahmad.rashidi@faarabi.edu / Test@1234
  Parent (sample):  walid.mansour@gmail.com / Test@1234

## School B — أكاديمية ابن سينا
  School Admin:  mudeer@ibnsina.edu / Test@1234
  ...
```

Full table of all 400+ users appended below the summary.

---

## Implementation Plan (High Level)

The seed is implemented as a single Python script: `backend/scripts/seed_test_data.py`

Execution order:
1. Create School A and School B records
2. Create platform admin user
3. Per school: create admin users, teachers, parents, students, classes, subjects
4. Per school: create time slots, teacher assignments, timetable + schedule sessions
5. Start API session, authenticate as school admin
6. Per school: POST attendance records (bulk), behavior logs, product hub issues, notifications
7. Write `TEST_CREDENTIALS.md`
8. Print summary statistics

---

## Success Criteria

- Two schools exist with zero shared data (verified by querying each tenant's records)
- All 5 role types have working login credentials
- Timetables are generated and conflict-free
- Attendance dashboard shows 4 weeks of data
- Behavior logs visible in student profiles
- Product Hub shows issues from both schools (filtered by tenant)
- Parent portal shows correct children for each parent
- `TEST_CREDENTIALS.md` exists and is accurate
