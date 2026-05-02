"""
Map PostgreSQL integrity-violation messages to actionable, field-specific
Arabic error messages so the UI can tell the user exactly what's wrong
instead of showing a generic "Record already exists" dialog.
"""

from typing import Tuple


_CONSTRAINT_MAP = {
    "uq_students_national_id_school": (
        "DUPLICATE_STUDENT_NATIONAL_ID",
        "رقم هوية الطالب مسجل مسبقاً في هذه المدرسة",
    ),
    "uq_students_number_school": (
        "DUPLICATE_STUDENT_NUMBER",
        "رقم الطالب مستخدم مسبقاً، حاول مرة أخرى",
    ),
    "uq_teachers_national_id_school": (
        "DUPLICATE_TEACHER_NATIONAL_ID",
        "رقم هوية المعلم مسجل مسبقاً في هذه المدرسة",
    ),
    "users_email_key": (
        "DUPLICATE_EMAIL",
        "البريد الإلكتروني مستخدم مسبقاً",
    ),
    "schools_code_key": (
        "DUPLICATE_SCHOOL_CODE",
        "رمز المدرسة مستخدم مسبقاً",
    ),
}


# Heuristic column → message map used when the constraint name isn't in
# the table above (e.g. ad-hoc unique indexes added later).
_COLUMN_HINTS = (
    ("national_id", "students", "رقم هوية الطالب مسجل مسبقاً"),
    ("national_id", "teachers", "رقم هوية المعلم مسجل مسبقاً"),
    ("national_id", "parents", "رقم هوية ولي الأمر مسجل مسبقاً"),
    ("student_number", None, "رقم الطالب مستخدم مسبقاً"),
    ("email", "users", "البريد الإلكتروني مستخدم مسبقاً"),
    ("phone", "users", "رقم الجوال مستخدم مسبقاً"),
    ("phone", "parents", "رقم جوال ولي الأمر مستخدم مسبقاً"),
    ("code", "schools", "رمز المدرسة مستخدم مسبقاً"),
)


def describe_integrity_error(raw_message: str) -> Tuple[str, str]:
    """
    Inspect a database error message and return (error_code, user_message)
    in Arabic. Falls back to a generic conflict message when the constraint
    can't be identified.
    """
    msg = raw_message or ""
    lower = msg.lower()

    # Direct constraint-name lookup (most reliable).
    for constraint, (code, user_msg) in _CONSTRAINT_MAP.items():
        if constraint in lower:
            return code, user_msg

    if "unique" in lower or "duplicate key" in lower:
        for column, table, user_msg in _COLUMN_HINTS:
            if column in lower and (table is None or table in lower):
                return "DUPLICATE_RECORD", user_msg
        return "DUPLICATE_RECORD", "هذا السجل موجود مسبقاً"

    if "foreign key" in lower:
        return "INVALID_REFERENCE", "مرجع غير صالح في البيانات المُرسَلة"

    if "not null" in lower or "null value" in lower:
        return "MISSING_REQUIRED", "حقل مطلوب مفقود"

    if "check constraint" in lower:
        return "INVALID_VALUE", "قيمة غير صالحة في البيانات"

    return "DATA_CONFLICT", "تعارض في البيانات"
