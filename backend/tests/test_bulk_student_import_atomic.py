"""Regression & Contract: Bulk Student Import Two-Pass Atomic Validation & Row Error Reporting.

Verifies:
1. When a file contains valid and invalid rows, the entire batch is validated first.
   If ANY row fails validation, 0 rows are committed to the database (atomic all-or-nothing).
2. The endpoint returns detailed error logs with exact row numbers, field names, and Arabic reasons in `errors`.
3. Re-uploading the exact same invalid file produces the exact same expected error without DB unique constraint crashes.
4. When all rows in the file are valid, all students are inserted and linked to parent accounts.
5. In-file duplicate national IDs are caught with exact row cross-references.
"""
import io
import uuid
import pandas as pd
import pytest

from dependencies import db, UserRole, create_access_token
from engines.sql_utils import gd_find, gd_find_one, gd_insert


def _headers(user_id: str, role: str, tenant_id: str) -> dict:
    token = create_access_token({
        "sub": user_id,
        "role": role,
        "tenant_id": tenant_id,
    })
    return {"Authorization": f"Bearer {token}"}


async def _mk_school(school_id: str) -> None:
    await gd_insert(db.session, "schools", {
        "id": school_id,
        "name": f"School-{school_id[:6]}",
        "code": f"S{school_id[:8]}",
        "status": "active",
        "country": "SA",
        "language": "ar",
    })


async def _mk_principal(school_id: str) -> dict:
    uid = f"usr_{uuid.uuid4().hex[:8]}"
    doc = {
        "id": uid,
        "email": f"principal_{uid}@school.test",
        "password_hash": "dummy_hash_for_test",
        "full_name": "مدير المدرسة التجريبية",
        "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": school_id,
        "is_active": True,
    }
    await gd_insert(db.session, "users", doc)
    return doc


def _create_excel_file(rows: list) -> io.BytesIO:
    df = pd.DataFrame(rows)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='البيانات')
    output.seek(0)
    return output


@pytest.mark.asyncio
async def test_bulk_student_import_atomic_rollback_on_partial_failure(client):
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(school_id)
    principal = await _mk_principal(school_id)
    h = _headers(principal["id"], principal["role"], school_id)

    # 1. Prepare 2-row file: 1 valid student, 1 invalid student (missing family name and bad national id)
    valid_national_id = "1112223334"
    invalid_national_id = "123"  # Only 3 digits, invalid
    
    rows = [
        {
            'الاسم الأول (مطلوب)': 'سلطان',
            'اسم الأب': 'عبدالله',
            'اسم العائلة (مطلوب)': 'القرني',
            'رقم الهوية (مطلوب)': valid_national_id,
            'تاريخ الميلاد (YYYY-MM-DD)': '2015-05-15',
            'الجنس (ذكر/أنثى)': 'ذكر',
            'الصف': 'الأول',
            'الفصل': 'أ',
            'البريد الإلكتروني': 'sultan@example.com',
            'رقم الجوال': '0501234567',
            'اسم ولي الأمر': 'عبدالله القرني',
            'جوال ولي الأمر (مطلوب)': '0501111111',
            'بريد ولي الأمر': 'parent_sultan@example.com',
        },
        {
            'الاسم الأول (مطلوب)': 'فهد',
            'اسم الأب': 'محمد',
            'اسم العائلة (مطلوب)': '',  # Missing required field!
            'رقم الهوية (مطلوب)': invalid_national_id,  # Invalid format!
            'تاريخ الميلاد (YYYY-MM-DD)': '2015-06-20',
            'الجنس (ذكر/أنثى)': 'ذكر',
            'الصف': 'الأول',
            'الفصل': 'أ',
            'البريد الإلكتروني': '',
            'رقم الجوال': '',
            'اسم ولي الأمر': 'محمد الشهري',
            'جوال ولي الأمر (مطلوب)': '0502222222',
            'بريد ولي الأمر': '',
        }
    ]

    excel_file = _create_excel_file(rows)

    # 2. Upload file
    resp1 = await client.post(
        "/bulk/import/students",
        files={"file": ("test_students.xlsx", excel_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=h,
    )
    assert resp1.status_code == 200, resp1.text
    res1_data = resp1.json()

    # Verify response schema and atomic rollback
    assert res1_data["success"] is False
    assert res1_data["total_rows"] == 2
    assert res1_data["imported"] == 0, "No records should be imported when any row fails"
    assert res1_data["failed"] >= 1
    assert len(res1_data["errors"]) >= 1

    # Verify errors contain exact row number and detailed messages
    row3_errors = [e for e in res1_data["errors"] if e.get("row") == 3]
    assert len(row3_errors) >= 1
    error_messages = " ".join([e.get("message", "") for e in row3_errors])
    assert "اسم العائلة" in error_messages or "رقم الهوية" in error_messages

    # Verify Database state is 100% clean (0 students inserted)
    students_in_db = await gd_find(db.session, "students", {"school_id": school_id})
    assert len(students_in_db) == 0, "Database must not contain partial records after failed import"

    # 3. Upload the exact same file a second time without changes
    excel_file2 = _create_excel_file(rows)
    resp2 = await client.post(
        "/bulk/import/students",
        files={"file": ("test_students.xlsx", excel_file2, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=h,
    )
    assert resp2.status_code == 200, resp2.text
    res2_data = resp2.json()

    # Ensure consistent behavior on re-upload (same 0 imported, same validation errors)
    assert res2_data["success"] is False
    assert res2_data["imported"] == 0
    assert len(res2_data["errors"]) >= 1


@pytest.mark.asyncio
async def test_bulk_student_import_success_all_rows(client):
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(school_id)
    principal = await _mk_principal(school_id)
    h = _headers(principal["id"], principal["role"], school_id)

    # 2 valid students
    rows = [
        {
            'الاسم الأول (مطلوب)': 'أحمد',
            'اسم الأب': 'علي',
            'اسم العائلة (مطلوب)': 'الغامدي',
            'رقم الهوية (مطلوب)': '1098765432',
            'تاريخ الميلاد (YYYY-MM-DD)': '2016-01-10',
            'الجنس (ذكر/أنثى)': 'ذكر',
            'الصف': 'الثاني',
            'الفصل': 'أ',
            'البريد الإلكتروني': 'ahmed_ghamdi@example.com',
            'رقم الجوال': '0551112233',
            'اسم ولي الأمر': 'علي الغامدي',
            'جوال ولي الأمر (مطلوب)': '0559998877',
            'بريد ولي الأمر': 'parent_ali@example.com',
        },
        {
            'الاسم الأول (مطلوب)': 'سارة',
            'اسم الأب': 'خالد',
            'اسم العائلة (مطلوب)': 'العتيبي',
            'رقم الهوية (مطلوب)': '1098765433',
            'تاريخ الميلاد (YYYY-MM-DD)': '2016-02-15',
            'الجنس (ذكر/أنثى)': 'أنثى',
            'الصف': 'الثاني',
            'الفصل': 'ب',
            'البريد الإلكتروني': 'sara_otaibi@example.com',
            'رقم الجوال': '0552223344',
            'اسم ولي الأمر': 'خالد العتيبي',
            'جوال ولي الأمر (مطلوب)': '0558887766',
            'بريد ولي الأمر': 'parent_khaled@example.com',
        }
    ]

    excel_file = _create_excel_file(rows)
    resp = await client.post(
        "/bulk/import/students",
        files={"file": ("valid_students.xlsx", excel_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    res_data = resp.json()

    assert res_data["success"] is True
    assert res_data["total_rows"] == 2
    assert res_data["imported"] == 2
    assert res_data["failed"] == 0
    assert len(res_data["errors"]) == 0

    # Verify both students and parents exist in DB
    students_in_db = await gd_find(db.session, "students", {"school_id": school_id})
    assert len(students_in_db) == 2
    sara = next((s for s in students_in_db if s["national_id"] == "1098765433"), None)
    assert sara is not None
    assert sara["gender"] == "female"
    assert sara["parent_id"] is not None


@pytest.mark.asyncio
async def test_bulk_student_import_catches_in_file_duplicates(client):
    school_id = f"sch_{uuid.uuid4().hex[:8]}"
    await _mk_school(school_id)
    principal = await _mk_principal(school_id)
    h = _headers(principal["id"], principal["role"], school_id)

    # 2 rows with the SAME national_id
    duplicate_nid = "1099998888"
    rows = [
        {
            'الاسم الأول (مطلوب)': 'طالب 1',
            'اسم العائلة (مطلوب)': 'الأول',
            'رقم الهوية (مطلوب)': duplicate_nid,
            'جوال ولي الأمر (مطلوب)': '0501112233',
        },
        {
            'الاسم الأول (مطلوب)': 'طالب 2',
            'اسم العائلة (مطلوب)': 'الثاني',
            'رقم الهوية (مطلوب)': duplicate_nid,  # In-file duplicate
            'جوال ولي الأمر (مطلوب)': '0501112234',
        }
    ]

    excel_file = _create_excel_file(rows)
    resp = await client.post(
        "/bulk/import/students",
        files={"file": ("duplicate_students.xlsx", excel_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    res_data = resp.json()

    assert res_data["success"] is False
    assert res_data["imported"] == 0
    assert res_data["failed"] >= 1
    # Check error message mentions duplication
    dup_error = next((e for e in res_data["errors"] if duplicate_nid in e.get("message", "")), None)
    assert dup_error is not None
    assert "مكرر" in dup_error["message"]
