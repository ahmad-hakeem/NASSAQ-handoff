"""
NASSAQ Name Validation Engine
التحقق من صحة أسماء المستخدمين — رفض الأسماء العامة/الوظيفية

Ensures every account uses a real personal name, not a generic role label.
"""

import re
from typing import Optional

GENERIC_NAMES_AR = {
    "مدير المنصة",
    "مدير المنصة الرئيسي",
    "مدير مدرسة",
    "مدير النظام",
    "مدير",
    "معلم",
    "طالب",
    "ولي أمر",
    "ولي الأمر",
    "مستخدم",
    "مستخدم جديد",
    "مستخدم تجريبي",
    "موقع",
    "ناظر",
    "وكيل",
    "مشرف",
    "مشرف عام",
    "إدارة",
    "حساب تجريبي",
    "حساب اختبار",
    "حساب جديد",
    "مسؤول",
    "مسؤول النظام",
    "موظف",
    "فني",
    "دعم فني",
    "خدمة العملاء",
}

GENERIC_NAMES_EN = {
    "platform admin",
    "school admin",
    "admin",
    "administrator",
    "teacher",
    "student",
    "parent",
    "user",
    "new user",
    "test user",
    "test",
    "demo",
    "demo user",
    "website",
    "manager",
    "principal",
    "super admin",
    "system admin",
    "system",
    "support",
    "technical support",
    "operations",
    "operations manager",
    "staff",
    "employee",
    "account",
    "default",
    "nassaq",
    "nassaq admin",
    "school manager",
}

GENERIC_PATTERNS = [
    r"^user\s*\d*$",
    r"^admin\s*\d*$",
    r"^test\s*\d*$",
    r"^demo\s*\d*$",
    r"^مستخدم\s*\d*$",
    r"^مدير\s*\d*$",
    r"^حساب\s*\d*$",
]


def is_generic_name(name: Optional[str]) -> bool:
    if not name or not name.strip():
        return True

    cleaned = name.strip()

    if len(cleaned) < 3:
        return True

    normalized = cleaned.lower().strip()

    if normalized in GENERIC_NAMES_EN:
        return True

    ar_normalized = cleaned.strip()
    if ar_normalized in GENERIC_NAMES_AR:
        return True

    for pattern in GENERIC_PATTERNS:
        if re.match(pattern, normalized, re.IGNORECASE):
            return True

    if re.match(r"^[\d\s]+$", cleaned):
        return True

    if re.match(r"^(.)\1+$", cleaned):
        return True

    return False


def validate_personal_name(name: Optional[str]) -> tuple:
    if not name or not name.strip():
        return False, "الاسم الشخصي مطلوب"

    cleaned = name.strip()

    if len(cleaned) < 3:
        return False, "الاسم قصير جداً — يجب أن يكون 3 أحرف على الأقل"

    if is_generic_name(cleaned):
        return False, "يجب استخدام اسمك الشخصي الحقيقي بدلاً من اسم عام أو وظيفي"

    if re.match(r"^[\d\s]+$", cleaned):
        return False, "الاسم يجب أن يحتوي على أحرف"

    return True, ""
