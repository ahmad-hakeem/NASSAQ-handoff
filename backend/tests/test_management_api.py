"""
NASSAQ Platform Management API Tests
Tests for Teachers, Students, Classes, and Subjects CRUD endpoints.

Runs fully in-process against the ASGI app using the shared async ``client``
fixture (see ``conftest.py``) — no external server / live base URL required.
Each test seeds its own data via the conftest fixtures and asserts against the
in-process responses. The autouse ``_db_session`` fixture rolls everything back
between tests, so the suite is hermetic.
"""
import uuid


class TestTeachersAPI:
    """Teachers CRUD endpoint tests"""

    async def test_get_teachers_list(self, client, school_admin_headers):
        """Test getting teachers list"""
        response = await client.get("/teachers", headers=school_admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_create_teacher(self, client, school_admin_headers, tenant_a):
        """Test creating a new teacher"""
        unique_email = f"teacher_{uuid.uuid4().hex[:8]}@test.com"
        response = await client.post(
            "/teachers",
            headers=school_admin_headers,
            json={
                "full_name": "معلم اختبار",
                "full_name_en": "Test Teacher",
                "email": unique_email,
                "phone": "+966501234567",
                "school_id": tenant_a,
                "specialization": "رياضيات",
                "years_of_experience": 5,
                "qualification": "بكالوريوس",
                "gender": "male",
            },
        )
        assert response.status_code == 200, f"Teacher creation failed: {response.text}"
        data = response.json()

        assert "id" in data
        assert data["full_name"] == "معلم اختبار"
        assert data["email"] == unique_email
        assert data["specialization"] == "رياضيات"
        assert data["is_active"] is True

    async def test_create_teacher_duplicate_email(self, client, school_admin_headers, tenant_a):
        """Test creating teacher with duplicate email fails"""
        unique_email = f"teacher_dup_{uuid.uuid4().hex[:8]}@test.com"

        first = await client.post(
            "/teachers",
            headers=school_admin_headers,
            json={
                "full_name": "معلم أول",
                "email": unique_email,
                "school_id": tenant_a,
                "specialization": "علوم",
            },
        )
        assert first.status_code == 200, first.text

        response = await client.post(
            "/teachers",
            headers=school_admin_headers,
            json={
                "full_name": "معلم ثاني",
                "email": unique_email,
                "school_id": tenant_a,
                "specialization": "فيزياء",
            },
        )
        assert response.status_code == 400

    async def test_get_teacher_by_id(self, client, school_admin_headers, tenant_a):
        """Test getting a specific teacher by ID"""
        unique_email = f"teacher_get_{uuid.uuid4().hex[:8]}@test.com"
        create_response = await client.post(
            "/teachers",
            headers=school_admin_headers,
            json={
                "full_name": "معلم للاسترجاع",
                "email": unique_email,
                "school_id": tenant_a,
                "specialization": "لغة عربية",
            },
        )
        assert create_response.status_code == 200, create_response.text
        teacher_id = create_response.json()["id"]

        response = await client.get(f"/teachers/{teacher_id}", headers=school_admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == teacher_id
        assert data["full_name"] == "معلم للاسترجاع"

    async def test_delete_teacher(self, client, school_admin_headers, tenant_a):
        """Test deleting (soft delete) a teacher"""
        unique_email = f"teacher_del_{uuid.uuid4().hex[:8]}@test.com"
        create_response = await client.post(
            "/teachers",
            headers=school_admin_headers,
            json={
                "full_name": "معلم للحذف",
                "email": unique_email,
                "school_id": tenant_a,
                "specialization": "تاريخ",
            },
        )
        assert create_response.status_code == 200, create_response.text
        teacher_id = create_response.json()["id"]

        response = await client.delete(f"/teachers/{teacher_id}", headers=school_admin_headers)
        assert response.status_code == 200


class TestStudentsAPI:
    """Students CRUD endpoint tests"""

    async def test_get_students_list(self, client, school_admin_headers):
        """Test getting students list"""
        response = await client.get("/students", headers=school_admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_create_student(self, client, school_admin_headers, tenant_a):
        """Test creating a new student"""
        student_number = f"STU{uuid.uuid4().hex[:8].upper()}"
        response = await client.post(
            "/students",
            headers=school_admin_headers,
            json={
                "full_name": "طالب اختبار",
                "full_name_en": "Test Student",
                "school_id": tenant_a,
                "student_number": student_number,
                "date_of_birth": "2010-05-15",
                "gender": "male",
                "parent_name": "ولي أمر الطالب",
                "parent_phone": "+966509876543",
            },
        )
        assert response.status_code == 200, f"Student creation failed: {response.text}"
        data = response.json()

        assert "id" in data
        assert data["full_name"] == "طالب اختبار"
        assert data["student_number"] == student_number
        assert data["is_active"] is True

    async def test_get_student_by_id(self, client, school_admin_headers, tenant_a):
        """Test getting a specific student by ID"""
        student_number = f"STU{uuid.uuid4().hex[:8].upper()}"
        create_response = await client.post(
            "/students",
            headers=school_admin_headers,
            json={
                "full_name": "طالب للاسترجاع",
                "school_id": tenant_a,
                "student_number": student_number,
                "gender": "female",
            },
        )
        assert create_response.status_code == 200, create_response.text
        student_id = create_response.json()["id"]

        response = await client.get(f"/students/{student_id}", headers=school_admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == student_id
        assert data["full_name"] == "طالب للاسترجاع"

    async def test_delete_student(self, client, school_admin_headers, tenant_a):
        """Test deleting (soft delete) a student"""
        student_number = f"STU{uuid.uuid4().hex[:8].upper()}"
        create_response = await client.post(
            "/students",
            headers=school_admin_headers,
            json={
                "full_name": "طالب للحذف",
                "school_id": tenant_a,
                "student_number": student_number,
            },
        )
        assert create_response.status_code == 200, create_response.text
        student_id = create_response.json()["id"]

        response = await client.delete(f"/students/{student_id}", headers=school_admin_headers)
        assert response.status_code == 200


class TestClassesAPI:
    """Classes CRUD endpoint tests"""

    async def test_get_classes_list(self, client, school_admin_headers):
        """Test getting classes list"""
        response = await client.get("/classes", headers=school_admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_create_class(self, client, school_admin_headers, tenant_a):
        """Test creating a new class"""
        unique = uuid.uuid4().hex[:6]
        response = await client.post(
            "/classes",
            headers=school_admin_headers,
            json={
                "name": f"الأول الابتدائي - أ {unique}",
                "name_en": f"Grade 1 - A {unique}",
                "school_id": tenant_a,
                "grade_level": "الصف الأول الابتدائي",
                "grade_id": "1",  # canonical digit grade id (unified stage/grade validation)
                "section": "أ",
                "capacity": 30,
            },
        )
        assert response.status_code == 200, f"Class creation failed: {response.text}"
        data = response.json()

        assert "id" in data
        assert data["name"] == f"الأول الابتدائي - أ {unique}"
        assert data["section"] == "أ"
        assert data["capacity"] == 30
        assert data["current_students"] == 0
        assert data["is_active"] is True

    async def test_get_class_by_id(self, client, school_admin_headers, tenant_a):
        """Test getting a specific class by ID"""
        unique = uuid.uuid4().hex[:6]
        create_response = await client.post(
            "/classes",
            headers=school_admin_headers,
            json={
                "name": f"الثاني الابتدائي - ب {unique}",
                "school_id": tenant_a,
                "grade_level": "الصف الثاني الابتدائي",
                "grade_id": "2",  # canonical digit grade id
                "section": "ب",
                "capacity": 25,
            },
        )
        assert create_response.status_code == 200, create_response.text
        class_id = create_response.json()["id"]

        response = await client.get(f"/classes/{class_id}", headers=school_admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == class_id
        assert data["name"] == f"الثاني الابتدائي - ب {unique}"

    async def test_delete_class(self, client, school_admin_headers, tenant_a):
        """Test deleting (soft delete) a class"""
        unique = uuid.uuid4().hex[:6]
        create_response = await client.post(
            "/classes",
            headers=school_admin_headers,
            json={
                "name": f"فصل للحذف {unique}",
                "school_id": tenant_a,
                "grade_level": "الصف الثالث الابتدائي",
                "grade_id": "3",  # canonical digit grade id
                "section": "ج",
            },
        )
        assert create_response.status_code == 200, create_response.text
        class_id = create_response.json()["id"]

        response = await client.delete(f"/classes/{class_id}", headers=school_admin_headers)
        assert response.status_code == 200


class TestSubjectsAPI:
    """Subjects CRUD endpoint tests"""

    async def test_get_subjects_list(self, client, school_admin_headers):
        """Test getting subjects list"""
        response = await client.get("/subjects", headers=school_admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_create_subject(self, client, school_admin_headers, tenant_a):
        """Test creating a new subject"""
        subject_code = f"SUBJ{uuid.uuid4().hex[:4].upper()}"
        unique = uuid.uuid4().hex[:6]
        response = await client.post(
            "/subjects",
            headers=school_admin_headers,
            json={
                "name": f"الرياضيات {unique}",
                "name_en": "Mathematics",
                "school_id": tenant_a,
                "code": subject_code,
                "description": "مادة الرياضيات للمرحلة الابتدائية",
                "weekly_hours": 5,
                "grade_levels": ["الأول الابتدائي", "الثاني الابتدائي"],
            },
        )
        assert response.status_code == 200, f"Subject creation failed: {response.text}"
        data = response.json()

        assert "id" in data
        assert data["name"] == f"الرياضيات {unique}"
        assert data["code"] == subject_code
        assert "weekly_periods" in data
        assert data["is_active"] is True

    async def test_get_subject_by_id(self, client, school_admin_headers, tenant_a):
        """Test getting a specific subject by ID"""
        subject_code = f"SUBJ{uuid.uuid4().hex[:4].upper()}"
        unique = uuid.uuid4().hex[:6]
        create_response = await client.post(
            "/subjects",
            headers=school_admin_headers,
            json={
                "name": f"العلوم {unique}",
                "school_id": tenant_a,
                "code": subject_code,
                "weekly_hours": 4,
            },
        )
        assert create_response.status_code == 200, create_response.text
        subject_id = create_response.json()["id"]

        response = await client.get(f"/subjects/{subject_id}", headers=school_admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == subject_id
        assert data["name"] == f"العلوم {unique}"

    async def test_update_subject(self, client, school_admin_headers, tenant_a):
        """Test updating a subject"""
        subject_code = f"SUBJ{uuid.uuid4().hex[:4].upper()}"
        unique = uuid.uuid4().hex[:6]
        create_response = await client.post(
            "/subjects",
            headers=school_admin_headers,
            json={
                "name": f"مادة للتحديث {unique}",
                "school_id": tenant_a,
                "code": subject_code,
                "weekly_hours": 3,
            },
        )
        assert create_response.status_code == 200, create_response.text
        subject_id = create_response.json()["id"]

        updated_name = f"مادة محدثة {unique}"
        response = await client.put(
            f"/subjects/{subject_id}",
            headers=school_admin_headers,
            json={
                "name": updated_name,
                "name_en": "Updated Subject",
                "school_id": tenant_a,
                "code": subject_code,
                "description": "وصف محدث",
                "weekly_hours": 6,
                "grade_levels": ["الأول الابتدائي"],
            },
        )
        assert response.status_code == 200, response.text

        get_response = await client.get(f"/subjects/{subject_id}", headers=school_admin_headers)
        data = get_response.json()
        assert data["name"] == updated_name

    async def test_delete_subject(self, client, school_admin_headers, tenant_a):
        """Test deleting (soft delete) a subject"""
        subject_code = f"SUBJ{uuid.uuid4().hex[:4].upper()}"
        unique = uuid.uuid4().hex[:6]
        create_response = await client.post(
            "/subjects",
            headers=school_admin_headers,
            json={
                "name": f"مادة للحذف {unique}",
                "school_id": tenant_a,
                "code": subject_code,
            },
        )
        assert create_response.status_code == 200, create_response.text
        subject_id = create_response.json()["id"]

        response = await client.delete(f"/subjects/{subject_id}", headers=school_admin_headers)
        assert response.status_code == 200


class TestUnauthorizedAccess:
    """Test unauthorized access to management endpoints"""

    async def test_teachers_unauthorized(self, client):
        """Test teachers endpoint without auth"""
        response = await client.get("/teachers")
        assert response.status_code in [401, 403]

    async def test_students_unauthorized(self, client):
        """Test students endpoint without auth"""
        response = await client.get("/students")
        assert response.status_code in [401, 403]

    async def test_classes_unauthorized(self, client):
        """Test classes endpoint without auth"""
        response = await client.get("/classes")
        assert response.status_code in [401, 403]

    async def test_subjects_unauthorized(self, client):
        """Test subjects endpoint without auth"""
        response = await client.get("/subjects")
        assert response.status_code in [401, 403]
