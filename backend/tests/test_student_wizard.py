"""
Test Student Wizard - إنشاء طالب جديد

Tests for the student creation wizard functionality including:
- Reference grades / academic structure lookups
- Creating a student (with/without class, with health info)
- Linking a sibling to an existing parent
- Validation and unauthorized handling
- Class roster + count regression (Task #361)

Runs fully in-process against the ASGI app using the shared async ``client``
fixture (see ``conftest.py``) — no external server / live base URL required.
Tokens are minted via the conftest header fixtures and data is seeded with
``gd_insert``. The autouse ``_db_session`` fixture rolls everything back between
tests, so the suite is hermetic.
"""

import uuid

from dependencies import db, UserRole, hash_password
from engines.sql_utils import gd_find, gd_find_one, gd_insert


async def _mk_login_user(role: UserRole, tenant_id: str, email: str, password: str) -> dict:
    """Seed a user row whose password is verifiable by /auth/login."""
    uid = str(uuid.uuid4())
    user = {
        "id": uid,
        "role": role.value,
        "tenant_id": tenant_id,
        "school_id": tenant_id,
        "email": email,
        "full_name": f"{role.value} user",
        "is_active": True,
        "password_hash": hash_password(password),
    }
    await gd_insert(db.session, "users", user)
    await db.session.flush()
    return user


class TestAuthentication:
    """Authentication tests — seeded accounts, in-process /auth/login."""

    async def test_principal_login(self, client, tenant_a):
        email = f"principal_{uuid.uuid4().hex[:8]}@nassaq.com"
        password = "Principal@123"
        await _mk_login_user(UserRole.SCHOOL_PRINCIPAL, tenant_a, email, password)

        response = await client.post("/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "school_principal"

    async def test_admin_login(self, client, tenant_a):
        email = f"admin_{uuid.uuid4().hex[:8]}@nassaq.com"
        password = "Admin@123"
        await _mk_login_user(UserRole.PLATFORM_ADMIN, tenant_a, email, password)

        response = await client.post("/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "platform_admin"


class TestGradesAndClasses:
    """Test grades and classes APIs - required for student wizard"""

    async def test_get_reference_grades(self, client, school_principal_headers):
        """Test GET /api/reference/grades - grades dropdown data"""
        response = await client.get("/reference/grades", headers=school_principal_headers)
        assert response.status_code == 200, f"Failed to get grades: {response.text}"
        grades = response.json()
        assert isinstance(grades, list), "Grades should be a list"
        if grades:
            grade = grades[0]
            has_name = "name_ar" in grade or "name_en" in grade or "name" in grade
            assert has_name, "Grade should have name_ar, name_en, or name field"

    async def test_get_classes(self, client, school_principal_headers):
        """Test GET /api/classes - classes dropdown data"""
        response = await client.get("/classes", headers=school_principal_headers)
        assert response.status_code == 200, f"Failed to get classes: {response.text}"
        classes = response.json()
        assert isinstance(classes, list), "Classes should be a list"

    async def test_get_academic_structure(self, client, school_principal_headers):
        """Test GET /api/reference/academic-structure - full academic structure"""
        response = await client.get(
            "/reference/academic-structure", headers=school_principal_headers
        )
        assert response.status_code == 200, f"Failed to get academic structure: {response.text}"
        data = response.json()
        assert isinstance(data.get("grades", []), list)


class TestStudentWizardAPI:
    """Test student wizard API endpoints"""

    async def test_check_parent_no_params(self, client, school_principal_headers):
        """Test check-parent with no parameters"""
        response = await client.post(
            "/student-wizard/check-parent", headers=school_principal_headers
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("found") is False

    async def test_check_parent_with_phone(self, client, school_principal_headers):
        """Test check-parent with phone number"""
        response = await client.post(
            "/student-wizard/check-parent?phone=0500000000",
            headers=school_principal_headers,
        )
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        assert data.get("found") is False

    async def test_create_student_minimal(self, client, school_principal_headers):
        """Test creating student with minimal data"""
        unique_id = uuid.uuid4().hex[:8]
        student_data = {
            "full_name": f"TEST_طالب اختبار {unique_id}",
            "gender": "male",
            "date_of_birth": "2015-01-15",
            "education_level": "primary",
            "grade_id": "grade-1",
            "parent": {
                "full_name": f"TEST_ولي أمر {unique_id}",
                "phone": f"05{unique_id}",
                "relationship": "father",
            },
        }

        response = await client.post(
            "/student-wizard/create", json=student_data, headers=school_principal_headers
        )

        assert response.status_code == 200, f"Failed to create student: {response.text}"
        data = response.json()

        assert data.get("success") is True, "Response should have success=true"
        assert "student" in data, "Response should have student object"
        assert "parent" in data, "Response should have parent object"

        student = data["student"]
        assert student.get("id"), "Student should have id"
        assert student.get("student_id") or student.get("student_number"), "Student should have student_id/number"
        assert student.get("full_name") == student_data["full_name"], "Student name should match"
        assert student.get("temp_password"), "Student should have temp_password"
        assert student.get("qr_code"), "Student should have QR code"

        parent = data["parent"]
        assert parent.get("id"), "Parent should have id"
        assert parent.get("full_name") == student_data["parent"]["full_name"], "Parent name should match"
        assert parent.get("is_new") is True, "Parent should be marked as new"
        assert parent.get("temp_password"), "Parent should have temp_password"

    async def test_create_student_with_class(self, client, school_principal_headers, tenant_a):
        """Test creating student with class assignment"""
        class_id = str(uuid.uuid4())
        await gd_insert(db.session, "classes", {
            "id": class_id,
            "school_id": tenant_a,
            "name": f"WizardClass-{class_id[:6]}",
            "is_active": True,
        })
        await db.session.flush()

        unique_id = uuid.uuid4().hex[:8]
        student_data = {
            "full_name": f"TEST_طالب مع فصل {unique_id}",
            "gender": "female",
            "date_of_birth": "2014-06-20",
            "education_level": "primary",
            "grade_id": "grade-2",
            "class_id": class_id,
            "parent": {
                "full_name": f"TEST_أم الطالب {unique_id}",
                "phone": f"05{unique_id}",
                "email": f"test_parent_{unique_id}@test.com",
                "relationship": "mother",
            },
        }

        response = await client.post(
            "/student-wizard/create", json=student_data, headers=school_principal_headers
        )

        assert response.status_code == 200, f"Failed to create student: {response.text}"
        data = response.json()
        assert data.get("success") is True
        assert data["student"]["id"]

    async def test_bulk_import_keeps_full_legacy_class_assignment(
        self, client, school_principal_headers, tenant_a
    ):
        """Student-wizard bulk import is open-ended for class rosters.

        A class with a legacy capacity of one still receives every requested
        row, including its parent link, rather than silently nulling
        ``class_id`` or dropping rows.
        """
        class_id = str(uuid.uuid4())
        await gd_insert(db.session, "classes", {
            "id": class_id,
            "school_id": tenant_a,
            "name": f"WizardBulkClass-{class_id[:6]}",
            "is_active": True,
            "capacity": 1,
            "current_students": 0,
        })
        await db.session.flush()

        students = []
        for index in range(31):
            unique = uuid.uuid4().hex[:8]
            students.append({
                "full_name": f"TEST_bulk_{index}_{unique}",
                "email": f"bulk_student_{unique}@test.com",
                "national_id": f"{1000000000 + index:010d}",
                "gender": "male",
                "date_of_birth": "2015-01-15",
                "education_level": "primary",
                "grade_id": "grade-1",
                "class_id": class_id,
                "parent_name": f"TEST_bulk_parent_{index}_{unique}",
                "parent_phone": f"05{index:08d}",
                "parent_email": f"bulk_parent_{unique}@test.com",
                "parent_relationship": "father",
            })

        response = await client.post(
            "/student-wizard/bulk-import",
            json={"students": students},
            headers=school_principal_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["success"] is True
        assert body["results"]["success"] == 31
        assert body["results"]["failed"] == 0

        imported = await gd_find(
            db.session,
            "students",
            {"school_id": tenant_a, "class_id": class_id},
            limit=100,
        )
        assert len(imported) == 31
        assert len({student["id"] for student in imported}) == 31
        assert all(student["class_id"] == class_id for student in imported)

        class_row = await gd_find_one(db.session, "classes", {"id": class_id})
        assert class_row["current_students"] == 31
        links = await gd_find(
            db.session,
            "guardian_links",
            {"tenant_id": tenant_a},
            limit=100,
        )
        imported_ids = {student["id"] for student in imported}
        assert len(
            [link for link in links if link.get("student_id") in imported_ids]
        ) == 31

    async def test_bulk_import_rejects_foreign_class_reference(
        self, client, school_principal_headers, tenant_a
    ):
        foreign_class_id = str(uuid.uuid4())
        student_data = {
            "full_name": f"TEST_foreign_bulk_{uuid.uuid4().hex[:8]}",
            "national_id": "9876543210",
            "gender": "male",
            "date_of_birth": "2015-01-15",
            "education_level": "primary",
            "grade_id": "grade-1",
            "class_id": foreign_class_id,
            "parent_name": "TEST_foreign_parent",
            "parent_phone": "0599999999",
        }

        response = await client.post(
            "/student-wizard/bulk-import",
            json={"students": [student_data]},
            headers=school_principal_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["success"] is False
        assert body["results"]["success"] == 0
        assert body["results"]["failed"] == 1
        assert body["results"]["errors"][0]["error"] == "الفصل غير موجود"
        assert not await gd_find(
            db.session,
            "students",
            {"school_id": tenant_a, "national_id": "9876543210"},
            limit=10,
        )

    async def test_create_student_with_health_info(self, client, school_principal_headers):
        """Test creating student with health information"""
        unique_id = uuid.uuid4().hex[:8]
        student_data = {
            "full_name": f"TEST_طالب صحي {unique_id}",
            "gender": "male",
            "date_of_birth": "2013-03-10",
            "education_level": "primary",
            "grade_id": "grade-3",
            "parent": {
                "full_name": f"TEST_ولي أمر صحي {unique_id}",
                "phone": f"05{unique_id}",
                "relationship": "guardian",
            },
            "health": {
                "health_status": "جيدة",
                "allergies": "حساسية الفول السوداني, حساسية الغبار",
                "medications": "فيتامين د",
                "special_needs": None,
                "notes": "يحتاج متابعة دورية",
            },
        }

        response = await client.post(
            "/student-wizard/create", json=student_data, headers=school_principal_headers
        )

        assert response.status_code == 200, f"Failed to create student: {response.text}"
        data = response.json()
        assert data.get("success") is True

    async def test_create_student_link_existing_parent(self, client, school_principal_headers):
        """Test creating student linked to existing parent (sibling)"""
        unique_id = uuid.uuid4().hex[:8]
        parent_phone = f"05{unique_id}"

        first_student_data = {
            "full_name": f"TEST_الطالب الأول {unique_id}",
            "gender": "male",
            "date_of_birth": "2012-01-01",
            "education_level": "primary",
            "grade_id": "grade-4",
            "parent": {
                "full_name": f"TEST_ولي أمر مشترك {unique_id}",
                "phone": parent_phone,
                "relationship": "father",
            },
        }

        response1 = await client.post(
            "/student-wizard/create", json=first_student_data, headers=school_principal_headers
        )
        assert response1.status_code == 200, response1.text
        first_data = response1.json()
        parent_id = first_data["parent"]["id"]

        check_response = await client.post(
            f"/student-wizard/check-parent?phone={parent_phone}",
            headers=school_principal_headers,
        )
        assert check_response.status_code == 200
        check_data = check_response.json()
        assert check_data.get("found") is True, "Parent should be found"

        sibling_data = {
            "full_name": f"TEST_الطالب الثاني (شقيق) {unique_id}",
            "gender": "female",
            "date_of_birth": "2014-05-15",
            "education_level": "primary",
            "grade_id": "grade-2",
            "link_to_parent_id": parent_id,
        }

        response2 = await client.post(
            "/student-wizard/create", json=sibling_data, headers=school_principal_headers
        )
        assert response2.status_code == 200, f"Failed to create sibling: {response2.text}"
        sibling_data_response = response2.json()
        assert sibling_data_response.get("success") is True

        parent = sibling_data_response.get("parent")
        if parent:
            assert parent.get("is_new") is False or parent.get("temp_password") is None, \
                "Linked parent should not be marked as new"


class TestStudentWizardValidation:
    """Test validation and error handling"""

    async def test_create_student_missing_name(self, client, school_principal_headers):
        """Test creating student without name - should fail"""
        student_data = {
            "gender": "male",
            "date_of_birth": "2015-01-15",
            "parent": {
                "full_name": "ولي أمر",
                "phone": "0500000001",
                "relationship": "father",
            },
        }

        response = await client.post(
            "/student-wizard/create", json=student_data, headers=school_principal_headers
        )
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"

    async def test_create_student_without_auth(self, client):
        """Test creating student without authentication - should fail"""
        student_data = {
            "full_name": "طالب بدون توثيق",
            "gender": "male",
            "parent": {
                "full_name": "ولي أمر",
                "phone": "0500000002",
                "relationship": "father",
            },
        }

        response = await client.post("/student-wizard/create", json=student_data)
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"


class TestClassRosterAndCount:
    """Regression: Task #361 — wizard launched from a class page must
    persist `class_id`, increment `classes.current_students`, and the
    new student must immediately show in `/classes/{id}/students`.
    Delete must reverse both. Cross-tenant ids must 404."""

    async def _seed_class(self, tenant_a):
        class_id = str(uuid.uuid4())
        await gd_insert(db.session, "classes", {
            "id": class_id,
            "school_id": tenant_a,
            "name": f"RosterClass-{class_id[:6]}",
            "is_active": True,
            "current_students": 0,
        })
        await db.session.flush()
        return class_id

    async def _class_count(self, client, headers, class_id):
        r = await client.get(f"/classes/{class_id}", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        return int(body.get("student_count") or body.get("current_students") or 0)

    async def _roster_ids(self, client, headers, class_id):
        r = await client.get(f"/classes/{class_id}/students", headers=headers)
        assert r.status_code == 200, r.text
        return {s.get("id") for s in r.json()}

    async def test_add_then_delete_updates_roster_and_count(
        self, client, school_principal_headers, tenant_a
    ):
        headers = school_principal_headers
        class_id = await self._seed_class(tenant_a)
        before_count = await self._class_count(client, headers, class_id)
        before_ids = await self._roster_ids(client, headers, class_id)

        unique = uuid.uuid4().hex[:8]
        payload = {
            "full_name": f"TEST_T361_{unique}",
            "gender": "male",
            "date_of_birth": "2014-01-01",
            "education_level": "primary",
            "grade_id": "grade-1",
            "class_id": class_id,
            "parent": {
                "full_name": f"TEST_T361_parent_{unique}",
                "phone": f"05{unique}9",
                "relationship": "father",
            },
        }
        r = await client.post(
            "/student-wizard/create", json=payload, headers=headers
        )
        assert r.status_code == 200, r.text
        new_id = r.json()["student"]["id"]

        sr = await client.get(f"/students/{new_id}", headers=headers)
        assert sr.status_code == 200, sr.text
        assert sr.json().get("class_id") == class_id, (
            f"Persisted class_id mismatch: got {sr.json().get('class_id')!r}, expected {class_id!r}"
        )

        after_ids = await self._roster_ids(client, headers, class_id)
        assert new_id in after_ids, "New student must appear in class roster"
        assert new_id not in before_ids
        assert await self._class_count(client, headers, class_id) == before_count + 1, "Count must increment by 1"

        d = await client.delete(f"/students/{new_id}", headers=headers)
        assert d.status_code == 200, d.text
        assert new_id not in await self._roster_ids(client, headers, class_id), "Student must be gone from roster"
        assert await self._class_count(client, headers, class_id) == before_count, "Count must drop back"

    async def test_delete_foreign_student_id_fails_closed(self, client, school_principal_headers):
        # An unknown / foreign-tenant student id must 404 from delete,
        # never 200/403 (preserves §8 invariant 3 for student-by-id).
        unknown = str(uuid.uuid4())
        r = await client.delete(f"/students/{unknown}", headers=school_principal_headers)
        assert r.status_code == 404, f"Expected 404 for foreign student_id, got {r.status_code}: {r.text}"

    async def test_foreign_class_id_fails_closed(self, client, school_principal_headers):
        # A random unknown class id from another tenant must 404, not silently
        # create an orphan student.
        unique = str(uuid.uuid4())
        payload = {
            "full_name": f"TEST_T361_foreign_{unique[:8]}",
            "gender": "male",
            "date_of_birth": "2014-01-01",
            "education_level": "primary",
            "grade_id": "grade-1",
            "class_id": unique,
            "parent": {
                "full_name": "TEST_T361_p",
                "phone": f"05{unique[:8]}",
                "relationship": "father",
            },
        }
        r = await client.post(
            "/student-wizard/create", json=payload, headers=school_principal_headers
        )
        assert r.status_code == 404, f"Expected 404 for foreign class_id, got {r.status_code}: {r.text}"

    async def test_roster_pagination_preserves_bare_array_and_reports_totals(
        self, client, school_principal_headers, tenant_a
    ):
        class_id = await self._seed_class(tenant_a)
        for index in range(5):
            await gd_insert(db.session, "students", {
                "id": f"roster-page-{index:02d}",
                "school_id": tenant_a,
                "class_id": class_id,
                "full_name": f"Roster page {index}",
                "is_active": True,
            })
        await db.session.flush()

        first = await client.get(
            f"/classes/{class_id}/students?offset=1&limit=2",
            headers=school_principal_headers,
        )
        assert first.status_code == 200, first.text
        assert [row["id"] for row in first.json()] == [
            "roster-page-01", "roster-page-02"
        ]
        assert first.headers["X-Total-Count"] == "5"
        assert first.headers["X-Has-More"] == "true"
        assert first.headers["X-Next-Offset"] == "3"

        final = await client.get(
            f"/classes/{class_id}/students?offset=3&limit=2",
            headers=school_principal_headers,
        )
        assert final.status_code == 200, final.text
        assert [row["id"] for row in final.json()] == [
            "roster-page-03", "roster-page-04"
        ]
        assert final.headers["X-Total-Count"] == "5"
        assert final.headers["X-Has-More"] == "false"
        assert final.headers["X-Next-Offset"] == ""

    async def test_student_directory_pagination_preserves_bare_array_and_totals(
        self, client, school_principal_headers, tenant_a
    ):
        for index in range(5):
            await gd_insert(db.session, "students", {
                "id": f"directory-page-{index:02d}",
                "school_id": tenant_a,
                "full_name": f"Directory page {index}",
                "is_active": True,
            })
        await db.session.flush()

        page = await client.get(
            "/students?offset=2&limit=2", headers=school_principal_headers
        )
        assert page.status_code == 200, page.text
        assert [row["id"] for row in page.json()] == [
            "directory-page-02", "directory-page-03"
        ]
        assert page.headers["X-Total-Count"] == "5"
        assert page.headers["X-Has-More"] == "true"
        assert page.headers["X-Next-Offset"] == "4"
