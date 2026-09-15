"""Transactional legacy student spreadsheet import.

The legacy ``/bulk/import/students`` endpoint predates the Noor importer and
has a deliberately small contract: a row identifies a student, a canonical
grade, and a class/section.  This module keeps the row pipeline separate from
the route so the resolution and savepoint rules can be tested without
exercising FastAPI.

Important invariants:

* grades are resolved through the canonical twelve-grade catalogue;
* classes are always resolved inside the importing school and grade;
* a row either writes its class, guardian, and student together, or writes
  nothing;
* national IDs are tenant-scoped and idempotent (active rows are updated and
  inactive rows are restored);
* the school-wide transaction advisory lock serialises class/student/guardian
  deduplication for concurrent imports.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
from sqlalchemy import text

from engines.sql_utils import (
    gd_find,
    gd_find_one,
    gd_insert,
    gd_update_one,
)
from src.common.utils.canonical_grades import CANONICAL_GRADES, normalize_canonical_grade


_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_NAN_VALUES = {"", "nan", "none", "null", "nat"}


# Header names are intentionally aliases rather than an exact-match mapping.
# ``_normalise_header`` removes the required marker and normalises whitespace,
# which keeps this table readable and makes English/Arabic uploads equivalent.
_HEADER_ALIASES = {
    "first_name": {
        "first name", "firstname", "student first name", "given name",
        "الاسم الأول", "الاسم الاول", "اسم الطالب الأول", "اسم الطالب الاول",
    },
    "father_name": {
        "father name", "middle name", "second name", "اسم الأب", "اسم الاب",
        "الاسم الأوسط", "الاسم الاوسط",
    },
    "grandfather_name": {
        "grandfather name", "third name", "اسم الجد", "اسم الجد الأكبر",
        "اسم الجد الاكبر",
    },
    "last_name": {
        "last name", "lastname", "family name", "surname",
        "اسم العائلة", "الاسم الأخير", "الاسم الاخير",
    },
    "full_name": {
        "full name", "student name", "name", "الاسم الكامل", "اسم الطالب",
    },
    "national_id": {
        "national id", "national number", "identity number", "id number",
        "student id", "iqama", "رقم الهوية", "رقم الهوية الوطنية",
        "رقم السجل المدني", "رقم الإقامة", "رقم الاقامة",
    },
    "date_of_birth": {
        "date of birth", "birth date", "dob", "تاريخ الميلاد",
    },
    "gender": {"gender", "sex", "الجنس", "النوع"},
    "grade": {
        "grade", "grade level", "school grade", "class grade",
        "الصف", "الصف الدراسي", "المرحلة الدراسية",
    },
    "class_name": {
        "class", "class name", "section", "class section", "class/section",
        "الفصل", "اسم الفصل", "الشعبة", "الفصل/الشعبة",
    },
    "email": {"email", "student email", "البريد الإلكتروني", "البريد الالكتروني"},
    "phone": {"phone", "mobile", "mobile number", "student phone", "رقم الجوال", "الجوال"},
    "parent_name": {
        "parent name", "guardian name", "اسم ولي الأمر", "اسم ولي الامر",
        "اسم الوالد", "اسم الوصي",
    },
    "parent_phone": {
        "parent phone", "guardian phone", "parent mobile", "رقم جوال ولي الأمر",
        "جوال ولي الأمر", "جوال ولي الامر", "هاتف ولي الأمر", "هاتف ولي الامر",
    },
    "parent_email": {
        "parent email", "guardian email", "بريد ولي الأمر", "بريد ولي الامر",
    },
    "health_status": {"health status", "medical status", "الحالة الصحية"},
    "notes": {"notes", "remarks", "ملاحظات"},
}

_HEADER_INDEX = {
    " ".join(str(alias).translate(_ARABIC_DIGITS).split()).casefold(): field
    for field, aliases in _HEADER_ALIASES.items()
    for alias in aliases
}


class StudentImportRowError(ValueError):
    """A safe, user-facing failure for one row."""


class StudentImportRelationshipError(StudentImportRowError):
    """A persisted class/grade/parent relationship failed validation."""


def _normalise_header(value: Any) -> str:
    raw = "" if value is None else str(value)
    raw = raw.replace("\u00a0", " ").translate(_ARABIC_DIGITS).strip()
    # Parenthesised header annotations are metadata, not part of the field's
    # identity: ``(مطلوب)``, ``(required)``, ``(YYYY-MM-DD)``, and
    # ``(ذكر/أنثى)`` are all common template variants.
    raw = re.sub(r"\s*[\(\[\{][^)\]}]*[\)\]\}]", "", raw)
    raw = raw.replace("_", " ").replace("-", " ")
    raw = re.sub(r"\s+", " ", raw).strip().casefold()
    return raw


def normalise_cell(value: Any) -> Optional[str]:
    """Return a whitespace/digit-normalised spreadsheet value."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    value = str(value).replace("\u00a0", " ").translate(_ARABIC_DIGITS).strip()
    if not value or value.casefold() in _NAN_VALUES:
        return None
    # Excel commonly turns an all-numeric cell into ``1234567890.0``.
    if re.fullmatch(r"\d+\.0", value):
        value = value[:-2]
    return re.sub(r"\s+", " ", value).strip() or None


def _normalise_token(value: Any) -> str:
    return " ".join((normalise_cell(value) or "").split()).casefold()


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map known Arabic/English header aliases to stable internal names."""
    rename: Dict[Any, str] = {}
    seen: Dict[str, List[str]] = {}
    for column in df.columns:
        normalised = _normalise_header(column)
        target = _HEADER_INDEX.get(normalised, normalised)
        rename[column] = target
        seen.setdefault(target, []).append(str(column))
    duplicate_headers = [
        {
            "field": field,
            "headers": headers,
        }
        for field, headers in seen.items()
        if len(headers) > 1
    ]
    result = df.rename(columns=rename)
    # DataFrame.attrs survives the rename and lets the service return a
    # user-facing validation error instead of allowing pandas' duplicate
    # column semantics to silently select an arbitrary value.
    result.attrs["duplicate_headers"] = duplicate_headers
    return result


def _clean_national_id(value: Any) -> str:
    raw = normalise_cell(value) or ""
    return re.sub(r"\D", "", raw)


def _clean_phone(value: Any) -> str:
    raw = normalise_cell(value) or ""
    return re.sub(r"[\s\-()]", "", raw)


def _safe_error(
    row: int,
    field: str,
    message: str,
    *,
    student_name: str = "",
    suggested_correction: Optional[str] = None,
) -> dict:
    suggestions = {
        "الاسم الأول": "أدخل الاسم الأول للطالب.",
        "اسم العائلة": "أدخل اسم العائلة للطالب.",
        "رقم الهوية": "أدخل رقم هوية مكوّناً من 10 أرقام.",
        "جوال ولي الأمر": "أدخل رقم جوال ولي الأمر مع 9 أرقام على الأقل.",
        "البريد الإلكتروني": "أدخل بريداً إلكترونياً صحيحاً أو اتركه فارغاً.",
        "بريد ولي الأمر": "أدخل بريداً إلكترونياً صحيحاً أو اتركه فارغاً.",
        "الصف": "استخدم صفاً canonical مثل «الصف الأول الابتدائي» أو رقمه من 1 إلى 12.",
        "الفصل": "أدخل اسم الشعبة، مثل «أ»، أو الاسم الكامل مع بادئة الصف غير الملتبسة.",
        "grade": "احتفظ بعمود واحد للصف واستخدم قيمة من القائمة المعتمدة.",
        "class_name": "احتفظ بعمود واحد للفصل وأدخل قيمة شعبة واضحة.",
        "headers": "احذف العمود المكرر واحتفظ بعمود واحد لكل حقل.",
        "relationships": "تحقق من الصف والفصل وبيانات ولي الأمر ثم أعد المحاولة.",
        "عام": "صحح البيانات المشار إليها ثم أعد استيراد الصف.",
    }
    return {
        "row": row,
        "field": field,
        "message": message,
        "student_name": student_name,
        "suggested_correction": suggested_correction or suggestions.get(field, suggestions["عام"]),
    }


def _exception_message(exc: Exception) -> str:
    detail = getattr(exc, "detail", None)
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("code") or "تعذر حفظ الصف")
    return str(detail or exc or "تعذر حفظ الصف")


async def acquire_school_import_lock(session, school_id: str) -> None:
    """Serialise all legacy student imports for one school.

    ``pg_advisory_xact_lock`` is transaction scoped, so the request middleware
    owns the eventual commit/rollback and the lock cannot leak on errors.
    The key includes a flow-specific namespace to avoid blocking unrelated
    school operations that use advisory locks.
    """
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
        {"lock_key": f"legacy_bulk_student_import:{school_id}"},
    )


async def _supports_batch_ownership_version(session) -> bool:
    """Detect the optional ownership marker without requiring a migration.

    Deployments that predate the ownership migration must keep importing
    successfully.  Their manifests intentionally remain legacy/unsafe for
    destructive parent cleanup; once the column is present, new manifests
    carry version 2 and rollback can use the proven ownership lists.
    """
    # Unit-test sessions model persistence with an in-memory ``rows`` store.
    if hasattr(session, "rows"):
        return True
    try:
        result = await session.execute(text("""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'bulk_import_batches'
                  AND column_name = 'ownership_version'
            )
        """))
        scalar = getattr(result, "scalar", None)
        return bool(scalar() if callable(scalar) else False)
    except Exception:
        return False


def _canonical_grade(value: Any) -> Optional[dict]:
    raw = normalise_cell(value)
    if raw is None:
        return None
    canonical = normalize_canonical_grade(raw)
    if canonical:
        return canonical

    # The spreadsheet template historically omitted the ``الصف`` prefix
    # from otherwise canonical labels (for example ``الأول الابتدائي``).
    # Resolve only aliases that retain the stage, so the bare ordinal
    # ``الأول`` remains fail-closed instead of being guessed as primary.
    alias_token = " ".join(
        raw.removeprefix("الصف ").split()
    ).replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    matches = []
    for entry in CANONICAL_GRADES:
        label = str(entry["label_ar"]).removeprefix("الصف ")
        label_token = " ".join(label.split()).replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
        if alias_token == label_token:
            matches.append(entry)
    return dict(matches[0]) if len(matches) == 1 else None


def _grade_index(rows: Iterable[dict]) -> Tuple[Dict[str, dict], Dict[str, str]]:
    """Build tenant grade-row indexes without assuming a phantom ``grade`` column."""
    by_value: Dict[str, dict] = {}
    id_to_value: Dict[str, str] = {}
    for row in rows:
        canonical = None
        for candidate in (
            row.get("name_ar"), row.get("name"), row.get("name_en"),
            row.get("code"), row.get("id"),
        ):
            canonical = _canonical_grade(candidate)
            if canonical:
                break
        if not canonical:
            continue
        # A grade row without a persisted id cannot be used for relational
        # class linkage.  Treat it as corrupt/absent so the import can create
        # one canonical tenant-scoped row instead of reporting a false reuse.
        if not row.get("id"):
            continue
        value = str(canonical["grade"])
        by_value[value] = row
        if row.get("id"):
            id_to_value[str(row["id"])] = value
        for candidate in (
            row.get("name_ar"), row.get("name"), row.get("name_en"),
            row.get("code"), row.get("id"),
        ):
            if candidate is not None:
                by_value[_normalise_token(candidate)] = row
    return by_value, id_to_value


def _class_canonical_grade(class_doc: dict, grade_rows: Dict[str, dict], grade_ids: Dict[str, str]) -> Optional[dict]:
    # Class.grade_level is the persisted display value.  grade_id is used only
    # as a linkage fallback; ``grade_levels.grade`` is deliberately not read
    # because that column does not exist in the current schema.
    canonical = _canonical_grade(class_doc.get("grade_level"))
    if canonical:
        return canonical
    gid = class_doc.get("grade_id")
    if gid is not None:
        canonical = _canonical_grade(gid)
        if canonical:
            return canonical
        grade_number = grade_ids.get(str(gid))
        if grade_number:
            return _canonical_grade(grade_number)
        row = grade_rows.get(_normalise_token(gid))
        if row:
            for candidate in (row.get("name_ar"), row.get("name"), row.get("name_en"), row.get("code")):
                canonical = _canonical_grade(candidate)
                if canonical:
                    return canonical
    return None


_SECTION_LETTER_ALIASES = {
    "a": "أ",
    "أ": "أ",
    "ا": "أ",
    "إ": "أ",
    "آ": "أ",
}


def _arabic_prefix_fold(value: Any) -> str:
    """Fold only Arabic hamza variants while resolving a known prefix."""
    return (
        str(value or "")
        .replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
    )


def _canonical_section_atom(value: Any) -> str:
    """Canonicalise a bare section letter without touching opaque labels."""
    raw = normalise_cell(value) or ""
    if len(raw) == 1:
        return _SECTION_LETTER_ALIASES.get(raw.casefold(), raw)
    return raw


def _section_match_token(value: Any) -> str:
    """Build a comparison token while preserving opaque suffixes.

    ``أ-1`` and ``ا-1`` are the same section identity, but ``ا-1`` and
    ``ا-2`` remain different because only the hamza-family letters are folded.
    This is used for matching only; persisted/displayed section text remains
    the importer's original canonical value.
    """
    return _normalise_token(_arabic_prefix_fold(normalise_cell(value) or ""))


def _section_from_input(value: str, grade: dict) -> str:
    """Extract a stable section token while accepting unambiguous prefixes.

    Grade prefixes are interpreted only when they are provably the selected
    grade (the canonical Arabic label, its hamza-folded form, an ordinal
    form, or the exact numeric grade).  Other separator-containing values stay
    opaque: ``ا-1`` and ``ا-2`` must not collapse to ``1`` and ``2`` or to
    one another.
    """
    raw = normalise_cell(value) or ""
    if not raw:
        return ""

    # A bare Arabic/Latin section letter is safe to alias.  This special case
    # deliberately runs before prefix parsing so ``ا-1`` remains opaque.
    bare = _canonical_section_atom(raw)
    if bare != raw or len(raw) == 1:
        return bare

    folded = _arabic_prefix_fold(raw)
    grade_number = str(grade["grade"])
    ordinal = str(grade["label_ar"]).split()[1]
    prefixes = (
        str(grade["label_ar"]),
        str(grade["label_ar"]).replace("الصف ", "", 1),
        f"الصف {ordinal}",
        ordinal,
        f"Grade {grade_number}",
        grade_number,
    )
    for prefix in prefixes:
        prefix_folded = _arabic_prefix_fold(prefix)
        pattern = rf"^{re.escape(prefix_folded)}(?:\s+|[-–—/:])(.+)$"
        match = re.match(pattern, folded, flags=re.IGNORECASE)
        if match:
            return _canonical_section_atom(match.group(1).strip(" -–—/:"))

    # No grade prefix was proven.  Keep the entire opaque section identity.
    return _canonical_section_atom(raw)


def _class_matches(class_doc: dict, raw_name: str, section: str, grade: dict) -> bool:
    incoming_section = _section_from_input(section, grade)
    incoming = {
        _normalise_token(raw_name),
        _normalise_token(section),
        _normalise_token(incoming_section),
        _section_match_token(section),
        _section_match_token(incoming_section),
    }
    class_name = class_doc.get("name")
    class_name_en = class_doc.get("name_en")
    class_section = class_doc.get("section") or _section_from_input(class_name or "", grade)
    class_section = _section_from_input(class_section, grade)
    known = {
        _normalise_token(class_name),
        _normalise_token(class_name_en),
        _normalise_token(class_section),
        _section_match_token(class_section),
    }
    return bool((incoming - {""}) & (known - {""}))


def _class_key(grade: dict, section: str) -> Tuple[str, str]:
    return str(grade["grade"]), _section_match_token(section)


def _new_class_doc(
    *,
    school_id: str,
    grade: dict,
    raw_name: str,
    section: str,
    grade_row: Optional[dict],
    user: dict,
) -> dict:
    section = section or raw_name
    raw_token = _normalise_token(raw_name)
    if raw_token in {
        _normalise_token(grade["label_ar"]),
        _normalise_token(f"{grade['label_ar']} - {section}"),
    } or raw_token.startswith(_normalise_token(grade["label_ar"])):
        display_name = raw_name
    else:
        display_name = f"{grade['label_ar']} - {section}"
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "school_id": school_id,
        "name": display_name,
        "name_en": f"Grade {grade['grade']} - {section}",
        "grade_level": grade["label_ar"],
        "section": section,
        # Class capacity is a nullable legacy field, not an import policy.
        # Imports must not manufacture a finite roster limit for new classes.
        "capacity": None,
        "current_students": 0,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
        "created_by": user.get("id"),
        "import_source": "legacy_student_import",
    }
    # grade_id is a real Class column and is persisted only when a real,
    # tenant-scoped grade row exists.  Never invent a grade-level id.
    if grade_row and grade_row.get("id"):
        doc["grade_id"] = grade_row["id"]
    return doc


def _new_grade_doc(*, school_id: str, grade: dict) -> dict:
    """Build the tenant grade row used by classes and student imports."""
    return {
        "id": str(uuid.uuid4()),
        "name": grade["label_ar"],
        "name_ar": grade["label_ar"],
        "name_en": grade["label_en"],
        "stage": grade["stage"],
        "order": grade["grade"],
        "is_active": True,
        "school_id": school_id,
    }


def _provided(row: pd.Series, field: str) -> Tuple[Optional[str], bool]:
    if field not in row.index:
        return None, False
    value = normalise_cell(row.get(field))
    return value, value is not None


def _split_full_name(full_name: Optional[str]) -> Tuple[str, str, str]:
    parts = (full_name or "").split()
    if len(parts) < 2:
        return (parts[0] if parts else "", "", "")
    return parts[0], " ".join(parts[1:-1]), parts[-1]


def _row_student_name(row: pd.Series) -> str:
    """Return a useful student label for every row-level error."""
    full_name = normalise_cell(row.get("full_name")) if "full_name" in row.index else None
    if full_name:
        return full_name
    parts = [
        normalise_cell(row.get(field))
        for field in ("first_name", "father_name", "grandfather_name", "last_name")
        if field in row.index
    ]
    return " ".join(part for part in parts if part).strip()


async def _validate_persisted_relationships(
    session,
    *,
    school_id: str,
    student_doc: dict,
    class_doc: dict,
    grade_row: dict,
) -> None:
    """Fail the row savepoint unless its canonical links are queryable."""
    persisted_class = await gd_find_one(session, "classes", {
        "id": class_doc["id"],
        "school_id": school_id,
    })
    if not persisted_class:
        raise StudentImportRelationshipError("لم يتم حفظ الفصل المرتبط بالطالب")

    grade_id = grade_row.get("id") if grade_row else None
    if not grade_id:
        raise StudentImportRelationshipError("لم يتم تحديد المرحلة الدراسية المرتبطة بالفصل")
    persisted_grade = await gd_find_one(session, "grade_levels", {
        "id": grade_id,
        "school_id": school_id,
    })
    if not persisted_grade:
        raise StudentImportRelationshipError("لم يتم حفظ المرحلة الدراسية المرتبطة بالفصل")
    if persisted_class.get("grade_id") != grade_id:
        raise StudentImportRelationshipError("الفصل المحفوظ لا يرتبط بالمرحلة الدراسية المحددة")

    persisted_student = await gd_find_one(session, "students", {
        "id": student_doc["id"],
        "school_id": school_id,
    })
    if not persisted_student or persisted_student.get("class_id") != class_doc["id"]:
        raise StudentImportRelationshipError("لم يتم ربط الطالب بالفصل المحفوظ")
    if str(persisted_student.get("grade")) != str(grade_row.get("order")):
        raise StudentImportRelationshipError("الطالب المحفوظ لا يرتبط بالمرحلة الدراسية المحددة")

    parent_id = student_doc.get("parent_id")
    if not parent_id:
        raise StudentImportRelationshipError("لم يتم ربط الطالب بولي أمر حقيقي")
    persisted_parent = await gd_find_one(session, "parents", {
        "id": parent_id,
        "school_id": school_id,
    })
    if not persisted_parent:
        raise StudentImportRelationshipError("لم يتم حفظ حساب ولي الأمر المرتبط")
    persisted_link = await gd_find_one(session, "guardian_links", {
        "student_id": student_doc["id"],
        "tenant_id": school_id,
        "parent_id": parent_id,
        "is_active": True,
    })
    if not persisted_link:
        raise StudentImportRelationshipError("لم يتم حفظ علاقة ولي الأمر بالطالب")


async def import_students(
    db,
    df: pd.DataFrame,
    school_id: str,
    user: dict,
    errors: list,
    warnings: list,
    filename: Optional[str] = None,
) -> dict:
    """Import legacy student rows with per-row savepoints and counters."""
    await acquire_school_import_lock(db.session, school_id)
    df = _normalise_columns(df)

    # A grade/class-less upload cannot satisfy the endpoint's assignment
    # contract.  Report the exact missing field on every non-empty row rather
    # than creating students that appear to import successfully but are
    # unassigned.
    required_header_fields = {
        "grade": "الصف",
        "class_name": "الفصل",
    }
    missing_headers = [
        (field, label)
        for field, label in required_header_fields.items()
        if field not in df.columns
    ]

    skipped = 0
    data_rows = []
    for idx, row in df.iterrows():
        row_num = int(idx) + 2
        if row.dropna().empty:
            skipped += 1
            continue
        data_rows.append((row_num, row))
    duplicate_headers = df.attrs.get("duplicate_headers") or []
    if duplicate_headers:
        for duplicate in duplicate_headers:
            headers = "، ".join(duplicate["headers"])
            errors.append(_safe_error(
                1,
                "headers",
                f"الأعمدة ({headers}) تشير إلى الحقل نفسه ({duplicate['field']}) ولا يمكن اختيار قيمة بينها تلقائياً",
            ))
        return _result(
            imported=0,
            failed=1,
            skipped=skipped,
            validation_errors=1,
        )
    if missing_headers:
        for row_num, _row in data_rows or [(1, None)]:
            for field, label in missing_headers:
                errors.append(_safe_error(
                    row_num,
                    field,
                    f"{label}: عمود مطلوب لاستيراد الطلاب وتعيينهم إلى فصل",
                    student_name=_row_student_name(_row) if _row is not None else "",
                ))
        return _result(
            imported=0,
            failed=len({e.get("row") for e in errors if e.get("row")}),
            skipped=skipped,
            validation_errors=len({e.get("row") for e in errors if e.get("row")}),
        )

    # Load all tenant-scoped rows while the import lock is held.  This is the
    # snapshot used for deterministic class matching and national-ID reuse.
    grade_rows = await gd_find(db.session, "grade_levels", {"school_id": school_id}, limit=500)
    grade_values, grade_ids = _grade_index(grade_rows)
    classes = await gd_find(db.session, "classes", {"school_id": school_id}, limit=10000)
    students = await gd_find(db.session, "students", {"school_id": school_id}, limit=100000)

    existing_by_nid: Dict[str, dict] = {}
    for student in students:
        existing_nid = _clean_national_id(student.get("national_id"))
        if len(existing_nid) == 9:
            existing_nid = existing_nid.zfill(10)
        if len(existing_nid) == 10:
            existing_by_nid[existing_nid] = student
    seen_nids: Dict[str, int] = {}
    seen_emails: Dict[str, int] = {}
    valid_records: List[dict] = []
    validation_error_rows: set[int] = set()
    relationship_error_rows: set[int] = set()

    for row_num, row in data_rows:
        row_errors: List[dict] = []
        try:
            first_name, has_first = _provided(row, "first_name")
            father_name, _has_father = _provided(row, "father_name")
            grandfather_name, _has_grandfather = _provided(row, "grandfather_name")
            last_name, has_last = _provided(row, "last_name")
            full_name_value, has_full_name = _provided(row, "full_name")
            if (not first_name or not last_name) and has_full_name:
                derived_first, derived_father, derived_last = _split_full_name(full_name_value)
                first_name = first_name or derived_first
                last_name = last_name or derived_last
                father_name = father_name or derived_father
            first_name = first_name or ""
            last_name = last_name or ""
            father_name = father_name or ""
            grandfather_name = grandfather_name or ""

            if not first_name:
                row_errors.append(_safe_error(row_num, "الاسم الأول", "الاسم الأول: حقل مطلوب"))
            if not last_name:
                row_errors.append(_safe_error(row_num, "اسم العائلة", "اسم العائلة: حقل مطلوب"))

            national_raw, _ = _provided(row, "national_id")
            clean_nid = _clean_national_id(national_raw)
            if not clean_nid:
                row_errors.append(_safe_error(row_num, "رقم الهوية", "رقم الهوية: حقل مطلوب"))
            elif len(clean_nid) == 9:
                clean_nid = clean_nid.zfill(10)
            elif len(clean_nid) != 10:
                row_errors.append(_safe_error(
                    row_num, "رقم الهوية",
                    f"رقم الهوية ({national_raw}): يجب أن يتكون من 10 أرقام",
                ))
            if clean_nid:
                if clean_nid in seen_nids:
                    row_errors.append(_safe_error(
                        row_num, "رقم الهوية",
                        f"رقم الهوية ({clean_nid}): مكرر داخل نفس الملف مع الصف {seen_nids[clean_nid]}",
                    ))
                else:
                    seen_nids[clean_nid] = row_num

            parent_phone, _ = _provided(row, "parent_phone")
            clean_parent_phone = _clean_phone(parent_phone)
            if not clean_parent_phone:
                row_errors.append(_safe_error(row_num, "جوال ولي الأمر", "جوال ولي الأمر: حقل مطلوب"))
            elif len(re.sub(r"\D", "", clean_parent_phone)) < 9:
                row_errors.append(_safe_error(
                    row_num, "جوال ولي الأمر",
                    f"جوال ولي الأمر ({parent_phone}): رقم هاتف غير صالح",
                ))

            email, has_email = _provided(row, "email")
            if has_email:
                email = email.strip()
                if "@" not in email or "." not in email:
                    row_errors.append(_safe_error(
                        row_num, "البريد الإلكتروني",
                        f"البريد الإلكتروني ({email}): صيغة بريد غير صالحة",
                    ))
                elif email.casefold() in seen_emails:
                    row_errors.append(_safe_error(
                        row_num, "البريد الإلكتروني",
                        f"البريد الإلكتروني ({email}): مكرر داخل نفس الملف مع الصف {seen_emails[email.casefold()]}",
                    ))
                else:
                    seen_emails[email.casefold()] = row_num

            parent_email, has_parent_email = _provided(row, "parent_email")
            if has_parent_email and ("@" not in parent_email or "." not in parent_email):
                row_errors.append(_safe_error(
                    row_num, "بريد ولي الأمر",
                    f"بريد ولي الأمر ({parent_email}): صيغة بريد غير صالحة",
                ))

            grade_raw, has_grade = _provided(row, "grade")
            grade = _canonical_grade(grade_raw)
            if not has_grade:
                row_errors.append(_safe_error(row_num, "الصف", "الصف: حقل مطلوب"))
            elif not grade:
                row_errors.append(_safe_error(
                    row_num, "الصف",
                    f"الصف ({grade_raw}): يجب أن يكون صفاً من القائمة المعتمدة",
                ))

            class_raw, has_class = _provided(row, "class_name")
            if not has_class:
                row_errors.append(_safe_error(row_num, "الفصل", "الفصل: حقل مطلوب"))

            if row_errors:
                validation_error_rows.add(row_num)
                student_name = " ".join(
                    part for part in (
                        first_name, father_name, grandfather_name, last_name
                    ) if part
                ).strip()
                for row_error in row_errors:
                    row_error["student_name"] = student_name
                errors.extend(row_errors)
                continue

            # Optional values are tracked so an idempotent update does not
            # erase existing data merely because a spreadsheet omitted a
            # non-required column.
            optional_values = {}
            for field in (
                "date_of_birth", "gender", "email", "phone", "parent_email",
                "health_status", "notes",
            ):
                value, supplied = _provided(row, field)
                if supplied:
                    optional_values[field] = value
            gender_raw = optional_values.get("gender")
            if gender_raw:
                gender_token = gender_raw.casefold()
                optional_values["gender"] = (
                    "female" if gender_token in {"female", "f", "أنثى", "انثى"} else "male"
                )
            parent_name, has_parent_name = _provided(row, "parent_name")
            full_name = " ".join(
                p for p in (
                    first_name, father_name, grandfather_name, last_name
                ) if p
            ).strip()
            if not parent_name:
                parent_name = f"ولي أمر {full_name}"

            valid_records.append({
                "row_num": row_num,
                "first_name": first_name,
                "father_name": father_name,
                "grandfather_name": grandfather_name,
                "last_name": last_name,
                "full_name": full_name,
                "national_id": clean_nid,
                "grade": grade,
                "raw_class_name": class_raw,
                "section": _section_from_input(class_raw, grade),
                "parent_name": parent_name,
                "parent_phone": clean_parent_phone,
                "parent_email": parent_email if has_parent_email else None,
                "optional_values": optional_values,
                "existing": existing_by_nid.get(clean_nid),
            })
        except Exception as exc:
            validation_error_rows.add(row_num)
            errors.append(_safe_error(
                row_num,
                "عام",
                f"خطأ في معالجة الصف: {_exception_message(exc)}",
                student_name=_row_student_name(row),
            ))

    counters = {
        "created": 0,
        "updated": 0,
        "restored": 0,
        "assigned": 0,
        "classes_created": 0,
        "parents_created": 0,
    }
    imported_student_ids: List[str] = []
    created_student_ids: List[str] = []
    updated_student_ids: List[str] = []
    restored_student_ids: List[str] = []
    created_class_ids: List[str] = []
    created_parent_ids: List[str] = []
    created_parent_user_ids: List[str] = []
    initial_class_ids = {str(class_doc.get("id")) for class_doc in classes if class_doc.get("id")}
    reused_class_ids: set[str] = set()
    reused_parent_ids: set[str] = set()
    linked_student_ids: set[str] = set()
    created_grade_ids: set[str] = set()
    reused_grade_ids: set[str] = set()
    touched_class_ids: set[str] = set()
    imported = 0

    # The cache starts as an immutable snapshot.  A class created/reactivated
    # during a row is added only after that row's savepoint succeeds.
    class_docs = list(classes)
    grade_rows_by_number = dict(grade_values)
    from dependencies import generate_secure_password, hash_password
    from services.parent_linking import link_or_update_real_school_guardian

    batch_temp_password = generate_secure_password()
    batch_temp_hash = hash_password(batch_temp_password)
    batch_hash = lambda _password: batch_temp_hash
    batch_password = lambda: batch_temp_password

    for item in valid_records:
        class_doc = None
        class_was_created = False
        new_class_doc = None
        grade_row = grade_rows_by_number.get(str(item["grade"]["grade"]))
        grade_was_created = grade_row is None
        if grade_was_created:
            grade_row = _new_grade_doc(school_id=school_id, grade=item["grade"])
        try:
            candidates = []
            for candidate in class_docs:
                candidate_grade = _class_canonical_grade(candidate, grade_values, grade_ids)
                if not candidate_grade or candidate_grade["grade"] != item["grade"]["grade"]:
                    continue
                if _class_matches(candidate, item["raw_class_name"], item["section"], item["grade"]):
                    candidates.append(candidate)
            if len(candidates) > 1:
                raise StudentImportRowError(
                    f"الصف {item['row_num']}: يوجد أكثر من فصل مطابق للصف والشعبة المحددين"
                )
            if candidates:
                class_doc = candidates[0]
            else:
                new_class_doc = _new_class_doc(
                    school_id=school_id,
                    grade=item["grade"],
                    raw_name=item["raw_class_name"],
                    section=item["section"],
                    grade_row=grade_row,
                    user=user,
                )
                class_doc = new_class_doc
                class_was_created = True

            existing = item["existing"]
            student_id = existing.get("id") if existing else str(uuid.uuid4())
            now_iso = datetime.now(timezone.utc).isoformat()
            student_doc = {
                "id": student_id,
                "school_id": school_id,
                "full_name": item["full_name"],
                "national_id": item["national_id"],
                "grade": str(item["grade"]["grade"]),
                "class_id": class_doc["id"],
                "parent_name": item["parent_name"],
                "parent_phone": item["parent_phone"],
                "is_active": True,
                "updated_at": now_iso,
            }
            if not existing:
                student_doc["created_at"] = now_iso
            # Update only optional values present in the spreadsheet.  New
            # rows still receive explicit NULLs for schema columns where no
            # value was supplied.
            for field, value in item["optional_values"].items():
                if field == "health_status":
                    student_doc["health_info"] = {"general_condition": value}
                elif field == "notes":
                    # ``students`` has no notes column; intentionally do not
                    # invent a schema field.
                    continue
                else:
                    student_doc[field] = value
            if not existing:
                student_doc.setdefault("date_of_birth", None)
                student_doc.setdefault("gender", "male")
                student_doc.setdefault("email", None)
                student_doc.setdefault("phone", None)
                student_doc.setdefault("parent_email", item["parent_email"])
                student_doc.setdefault("health_info", {})

            parent_created = None
            parent_user_created = None
            needs_grade_link_repair = (
                not class_doc.get("grade_id")
                or str(class_doc.get("grade_id") or "").isdigit()
            )
            async with db.session.begin_nested():
                if grade_was_created:
                    await gd_insert(db.session, "grade_levels", grade_row)
                if class_was_created:
                    await gd_insert(db.session, "classes", new_class_doc)
                elif class_doc.get("is_active") is False:
                    # Only the class used by a successful row is restored.
                    await gd_update_one(
                        db.session,
                        "classes",
                        {"id": class_doc["id"], "school_id": school_id},
                        {"$set": {"is_active": True, "updated_at": now_iso}},
                    )
                # Older schools may have persisted the canonical number
                # (for example ``"1"``) in classes.grade_id before tenant
                # grade rows were introduced.  Once this import resolves the
                # real grade row, repair that legacy link in place rather
                # than rejecting an otherwise matching existing class.
                if needs_grade_link_repair:
                    await gd_update_one(
                        db.session,
                        "classes",
                        {"id": class_doc["id"], "school_id": school_id},
                        {"$set": {"grade_id": grade_row["id"], "updated_at": now_iso}},
                    )

                guardian_fields = await link_or_update_real_school_guardian(
                    db.session,
                    student=student_doc if not existing else {**existing, **student_doc},
                    school_id=school_id,
                    created_by=user.get("id"),
                    parent_name=item["parent_name"],
                    parent_phone=item["parent_phone"],
                    parent_email=item["parent_email"],
                    parent_relationship="guardian",
                    hash_password=batch_hash,
                    generate_secure_password=batch_password,
                )
                student_doc.update({
                    key: guardian_fields.get(key)
                    for key in ("parent_id", "parent_name", "parent_phone", "parent_email")
                })
                if guardian_fields.get("is_new"):
                    parent_created = guardian_fields.get("parent_id")
                if guardian_fields.get("is_new_user"):
                    parent_user_created = guardian_fields.get("parent_user_id")

                if existing:
                    await gd_update_one(
                        db.session,
                        "students",
                        {"id": existing["id"], "school_id": school_id},
                        {"$set": student_doc},
                    )
                else:
                    await gd_insert(db.session, "students", student_doc)
                await _validate_persisted_relationships(
                    db.session,
                    school_id=school_id,
                    student_doc=student_doc,
                    class_doc=class_doc,
                    grade_row=grade_row,
                )

            # Everything below this point is cache/counter bookkeeping.  It
            # deliberately occurs after the savepoint exits successfully.
            if needs_grade_link_repair:
                # ``class_doc`` may be an entry in the matching cache.  Do not
                # mutate it until the savepoint has committed: a guardian or
                # relationship failure restores the database but cannot undo
                # mutations to this in-memory object.
                class_doc["grade_id"] = grade_row["id"]
            grade_number = str(item["grade"]["grade"])
            if grade_was_created:
                grade_rows_by_number[grade_number] = dict(grade_row)
                grade_values[grade_number] = dict(grade_row)
                grade_ids[str(grade_row["id"])] = grade_number
                created_grade_ids.add(str(grade_row["id"]))
            else:
                reused_grade_ids.add(str(grade_row["id"]))
            if class_was_created:
                class_docs.append(dict(new_class_doc))
                created_class_ids.append(new_class_doc["id"])
                counters["classes_created"] += 1
            else:
                if class_doc.get("is_active") is False:
                    class_doc["is_active"] = True
                if str(class_doc.get("id")) in initial_class_ids:
                    reused_class_ids.add(str(class_doc["id"]))
            if parent_created:
                if parent_created not in created_parent_ids:
                    created_parent_ids.append(parent_created)
                    counters["parents_created"] += 1
            if parent_user_created:
                if parent_user_created not in created_parent_user_ids:
                    created_parent_user_ids.append(parent_user_created)
            parent_id = guardian_fields.get("parent_id")
            if parent_id and not guardian_fields.get("is_new"):
                reused_parent_ids.add(str(parent_id))

            prior_class_id = existing.get("class_id") if existing else None
            if prior_class_id:
                touched_class_ids.add(prior_class_id)
            touched_class_ids.add(class_doc["id"])
            counters["assigned"] += 1
            if student_doc.get("parent_id"):
                linked_student_ids.add(student_id)

            imported += 1
            imported_student_ids.append(student_id)
            if existing:
                if existing.get("is_active") is False:
                    counters["restored"] += 1
                    restored_student_ids.append(student_id)
                else:
                    counters["updated"] += 1
                    updated_student_ids.append(student_id)
            else:
                counters["created"] += 1
                created_student_ids.append(student_id)
        except StudentImportRelationshipError as exc:
            relationship_error_rows.add(item["row_num"])
            errors.append(_safe_error(
                item["row_num"],
                "relationships",
                _exception_message(exc),
                student_name=item.get("full_name", ""),
            ))
        except Exception as exc:
            validation_error_rows.add(item["row_num"])
            errors.append(_safe_error(
                item["row_num"],
                "عام",
                _exception_message(exc),
                student_name=item.get("full_name", ""),
            ))

    if imported:
        from engines.entity_counts import reconcile_class_counts, reconcile_school_counts
        try:
            await reconcile_school_counts(db.session, school_id)
        except Exception as exc:
            warnings.append({
                "row": 0,
                "field": "counters",
                "message": f"تعذر تحديث عدادات المدرسة بعد الاستيراد: {_exception_message(exc)}",
            })
        for class_id in touched_class_ids:
            try:
                await reconcile_class_counts(db.session, class_id, school_id)
            except Exception as exc:
                warnings.append({
                    "row": 0,
                    "field": "counters",
                    "message": f"تعذر تحديث عداد الفصل {class_id}: {_exception_message(exc)}",
                })

        batch_id = str(uuid.uuid4())
        try:
            batch_manifest = {
                "id": batch_id,
                "school_id": school_id,
                "actor_id": user.get("id"),
                "actor_name": user.get("full_name") or user.get("name"),
                "import_type": "students",
                "file_name": filename or "students.xlsx",
                "imported_count": imported,
                # Rollback is allowed to delete only rows created by this
                # batch; updated/restored ids are returned separately and are
                # not stored in the rollback manifest.
                "student_ids": created_student_ids,
                "created_class_ids": created_class_ids,
                "created_parent_ids": created_parent_ids,
                "created_parent_user_ids": created_parent_user_ids,
                "status": "active",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            # The ownership migration is deliberately optional for this
            # import path.  Without it the row is still committed, but
            # rollback will treat the manifest as legacy and preserve all
            # parent/user resources.
            if await _supports_batch_ownership_version(db.session):
                batch_manifest["ownership_version"] = 2
            await gd_insert(db.session, "bulk_import_batches", batch_manifest)
        except Exception:
            # The import itself is already committed at row savepoint scope;
            # a reporting-manifest failure must not turn successful rows into
            # a request-wide rollback.
            batch_id = None
    else:
        batch_id = None

    failed = len({e.get("row") for e in errors if e.get("row") is not None})
    return _result(
        imported=imported,
        failed=failed,
        skipped=skipped,
        batch_id=batch_id,
        student_ids=imported_student_ids,
        created_student_ids=created_student_ids,
        updated_student_ids=updated_student_ids,
        restored_student_ids=restored_student_ids,
        existing_student_ids=updated_student_ids + restored_student_ids,
        created_class_ids=created_class_ids,
        created_parent_ids=created_parent_ids,
        classes_reused=len(reused_class_ids),
        # A resource created by an earlier successful row may be returned as
        # "reused" by a later row in the same upload.  It is still created
        # from the import's perspective, so the two counters must be
        # disjoint.
        parents_reused=len(
            reused_parent_ids - {str(parent_id) for parent_id in created_parent_ids}
        ),
        students_linked_to_parents=len(linked_student_ids),
        grades_created=len(created_grade_ids),
        grades_reused=len(reused_grade_ids - created_grade_ids),
        validation_errors=len(validation_error_rows),
        relationship_errors=len(relationship_error_rows),
        created_parent_user_ids=created_parent_user_ids,
        **counters,
    )


def _result(
    *,
    imported: int,
    failed: int,
    skipped: int,
    batch_id: Optional[str] = None,
    student_ids: Optional[list] = None,
    created_student_ids: Optional[list] = None,
    updated_student_ids: Optional[list] = None,
    restored_student_ids: Optional[list] = None,
    existing_student_ids: Optional[list] = None,
    created_class_ids: Optional[list] = None,
    created_parent_ids: Optional[list] = None,
    created_parent_user_ids: Optional[list] = None,
    created: int = 0,
    updated: int = 0,
    restored: int = 0,
    assigned: int = 0,
    classes_created: int = 0,
    classes_reused: int = 0,
    parents_created: int = 0,
    parents_reused: int = 0,
    students_linked_to_parents: int = 0,
    grades_created: int = 0,
    grades_reused: int = 0,
    validation_errors: int = 0,
    relationship_errors: int = 0,
) -> dict:
    return {
        "imported": imported,
        "failed": failed,
        "skipped": skipped,
        "created": created,
        "updated": updated,
        "restored": restored,
        "assigned": assigned,
        "classes_created": classes_created,
        "classes_reused": classes_reused,
        "parents_created": parents_created,
        "parents_reused": parents_reused,
        "students_linked_to_parents": students_linked_to_parents,
        "grades_created": grades_created,
        "grades_reused": grades_reused,
        "validation_errors": validation_errors,
        "relationship_errors": relationship_errors,
        "existing": updated + restored,
        "batch_id": batch_id,
        "student_ids": student_ids or [],
        "created_student_ids": created_student_ids or [],
        "updated_student_ids": updated_student_ids or [],
        "restored_student_ids": restored_student_ids or [],
        "existing_student_ids": existing_student_ids or [],
        "created_class_ids": created_class_ids or [],
        "created_parent_ids": created_parent_ids or [],
        "created_parent_user_ids": created_parent_user_ids or [],
    }