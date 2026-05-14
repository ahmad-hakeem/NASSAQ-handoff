"""
Noor (Saudi MoE) workbook parser.

Detects the report type, locates the real Arabic header row dynamically,
and produces normalized typed dicts for downstream upsert. NEVER trusts a
hard-coded row index — Noor reports start with several merged title rows
and the data starts mid-sheet.

Public API:
    detect_report_type(workbook) -> "teachers" | "students" | None
    parse_workbook_bytes(content, filename) ->
        {"detected_type", "header_row", "mapped_columns",
         "rows": [{row_index, data}], "sheet_name"}

This module performs NO database access and NO business validation.
"""
from __future__ import annotations

import io
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

TEACHER_REPORT = "teachers"
STUDENT_REPORT = "students"


class NoorParseError(Exception):
    """Raised when a Noor workbook cannot be parsed safely."""


# ---------------------------------------------------------------------------
# Arabic / unicode helpers
# ---------------------------------------------------------------------------

# RTL/LTR marks, BOM, zero-width joiners that frequently appear in Noor cells
_INVISIBLE = "".join(
    [
        "\u200b",  # zero-width space
        "\u200c",  # zero-width non-joiner
        "\u200d",  # zero-width joiner
        "\u200e",  # LTR mark
        "\u200f",  # RTL mark
        "\u202a",  # LRE
        "\u202b",  # RLE
        "\u202c",  # PDF
        "\u202d",  # LRO
        "\u202e",  # RLO
        "\ufeff",  # BOM
        "\u00a0",  # nbsp
    ]
)
_INVISIBLE_RE = re.compile(f"[{re.escape(_INVISIBLE)}]")

# Arabic-Indic and Eastern Arabic-Indic digit ranges
_AR_DIGITS = {
    **{chr(0x0660 + i): str(i) for i in range(10)},
    **{chr(0x06F0 + i): str(i) for i in range(10)},
}


def _strip_text(value: Any) -> str:
    """Trim, drop invisible marks, normalise whitespace."""
    if value is None:
        return ""
    # xlrd surfaces every numeric cell as a float (e.g. "12345.0" for the
    # national/student id column). Drop the spurious decimal so dedupe
    # against the DB (which stores ids as strings) works.
    if isinstance(value, float) and value.is_integer():
        s = str(int(value))
    else:
        s = str(value)
    s = _INVISIBLE_RE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _ascii_digits(value: Any) -> str:
    s = _strip_text(value)
    return "".join(_AR_DIGITS.get(ch, ch) for ch in s)


def _norm_header(value: Any) -> str:
    """Normalise a header cell for label matching (alif variants etc.)."""
    s = _strip_text(value)
    if not s:
        return ""
    # Common Noor variant: الإسم vs الاسم
    s = s.replace("الإسم", "الاسم")
    s = s.replace("ـ", "")  # tatweel
    return s


# ---------------------------------------------------------------------------
# Header label sets (deterministic anchors)
# ---------------------------------------------------------------------------

# Teacher report header tokens (verified against the real fixture).
# Merged 2-row sub-headers are flattened by openpyxl into the top cell only,
# so we only need to recognise the parent labels here.
_TEACHER_HEADERS = {
    "الاسم": "full_name",
    "رقم الهوية": "national_id",
    "البريد الإلكتروني": "email",
    "الجوال": "mobile",
    "هاتف 1": "phone1",
    "هاتف 2": "phone2",
    "العنوان": "address",
    "صندوق البريد": "postal_box",
    "الرمز البريدي": "postal_code",
    "تاريخ الولادة": "dob",
    "مكان الولادة": "birth_place",
    "الحالة الإجتماعية": "marital_status",
    "الحالة الاجتماعية": "marital_status",
    "عدد الأبناء": "children_count",
    "الجنس": "gender",
}

_TEACHER_REQUIRED = {"الاسم", "رقم الهوية"}
_TEACHER_TITLE_ANCHOR = "بيانات معلمي المدرسة"

# Student report — locked to what the real .xls actually exposes.
_STUDENT_HEADERS = {
    "رقم الطالب": "student_number",
    "اسم الطالب": "full_name",
    "رقم الصف": "grade_code",
    "الفصل": "section_code",
    "الجوال": "mobile",
}

_STUDENT_REQUIRED = {"رقم الطالب", "اسم الطالب"}
_STUDENT_TITLE_ANCHORS = ("Student Info Table", "بيانات الطلاب")


# ---------------------------------------------------------------------------
# Workbook readers — tolerant of .xlsx (openpyxl) and .xls (xlrd)
# ---------------------------------------------------------------------------

def _read_workbook(content: bytes, filename: str) -> List[Tuple[str, List[List[Any]]]]:
    """
    Returns [(sheet_name, rows)] where rows is a list-of-lists of raw cell
    values. Picks the reader by the filename extension; falls back to the
    other reader if the first attempt fails (some Noor exports mislabel the
    extension).
    """
    name = (filename or "").lower()
    readers = []
    if name.endswith(".xls"):
        readers = [_read_xls, _read_xlsx]
    else:
        readers = [_read_xlsx, _read_xls]
    last_err: Optional[Exception] = None
    for reader in readers:
        try:
            return reader(content)
        except NoorParseError:
            raise
        except Exception as e:  # noqa: BLE001 — try the other reader
            last_err = e
            logger.debug("Noor reader %s failed: %s", reader.__name__, e)
    raise NoorParseError("تعذّر قراءة الملف — تأكد من أنه ملف Excel صالح من نظام نور")


def _read_xlsx(content: bytes) -> List[Tuple[str, List[List[Any]]]]:
    from openpyxl import load_workbook  # local import to keep cold-path light

    wb = load_workbook(io.BytesIO(content), data_only=True, read_only=True)
    out: List[Tuple[str, List[List[Any]]]] = []
    for sheet in wb.worksheets:
        rows = [list(r) for r in sheet.iter_rows(values_only=True)]
        out.append((sheet.title, rows))
    return out


def _read_xls(content: bytes) -> List[Tuple[str, List[List[Any]]]]:
    import xlrd  # type: ignore[import-not-found]

    book = xlrd.open_workbook(file_contents=content, formatting_info=False)
    out: List[Tuple[str, List[List[Any]]]] = []
    for sheet in book.sheets():
        rows: List[List[Any]] = []
        for r in range(sheet.nrows):
            rows.append([sheet.cell_value(r, c) for c in range(sheet.ncols)])
        out.append((sheet.name, rows))
    return out


# ---------------------------------------------------------------------------
# Detection + header-row scan
# ---------------------------------------------------------------------------

def _row_label_set(row: List[Any]) -> set:
    return {_norm_header(c) for c in row if _strip_text(c)}


def detect_report_type(sheets: List[Tuple[str, List[List[Any]]]]) -> Optional[str]:
    """
    Walk the first ~30 rows of each sheet looking for the deterministic
    Noor anchor labels. Returns "teachers" | "students" | None.
    """
    for _name, rows in sheets:
        for row in rows[:30]:
            joined = " ".join(_norm_header(c) for c in row if _strip_text(c))
            if not joined:
                continue
            if _TEACHER_TITLE_ANCHOR in joined:
                return TEACHER_REPORT
            for anchor in _STUDENT_TITLE_ANCHORS:
                if anchor in joined:
                    return STUDENT_REPORT
        # Header-only fallback
        for row in rows[:30]:
            labels = _row_label_set(row)
            if _TEACHER_REQUIRED.issubset(labels):
                return TEACHER_REPORT
            if _STUDENT_REQUIRED.issubset(labels):
                return STUDENT_REPORT
    return None


def _find_header_row(
    rows: List[List[Any]], required_labels: set, known_labels: set
) -> Optional[int]:
    """
    Scan rows[0:60] and return the index of the first row whose label set
    fully covers `required_labels` (and overlaps `known_labels` by ≥3 cells
    total). Returns None when no row matches.
    """
    best: Optional[int] = None
    best_overlap = 0
    for idx, row in enumerate(rows[:60]):
        labels = _row_label_set(row)
        if not required_labels.issubset(labels):
            continue
        overlap = len(labels & known_labels)
        if overlap >= 3 and overlap > best_overlap:
            best, best_overlap = idx, overlap
    return best


def _build_column_map(
    header_row: List[Any], known_headers: Dict[str, str]
) -> Dict[int, str]:
    """Map worksheet column index → internal field name."""
    out: Dict[int, str] = {}
    for col_idx, raw in enumerate(header_row):
        label = _norm_header(raw)
        if not label:
            continue
        # Try exact match first, then a fuzzy contains-match (Noor sometimes
        # appends "(2)" or wraps in parentheses).
        if label in known_headers:
            out[col_idx] = known_headers[label]
            continue
        for k, v in known_headers.items():
            if k in label and v not in out.values():
                out[col_idx] = v
                break
    return out


# ---------------------------------------------------------------------------
# Row normalisation
# ---------------------------------------------------------------------------

def _normalise_teacher_row(raw: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    out["full_name"] = _strip_text(raw.get("full_name"))
    out["national_id"] = _ascii_digits(raw.get("national_id")) or None
    email = _strip_text(raw.get("email")).lower() or None
    out["email"] = email if email and "@" in email and " " not in email else None
    # Phones — first non-empty across mobile/phone1/phone2 wins for `phone`.
    mobile = _ascii_digits(raw.get("mobile")) or None
    phone1 = _ascii_digits(raw.get("phone1")) or None
    phone2 = _ascii_digits(raw.get("phone2")) or None
    out["mobile"] = mobile
    out["phone1"] = phone1
    out["phone2"] = phone2
    out["phone"] = mobile or phone1 or phone2
    out["address"] = _strip_text(raw.get("address")) or None
    out["postal_box"] = _strip_text(raw.get("postal_box")) or None
    out["postal_code"] = _ascii_digits(raw.get("postal_code")) or None
    out["dob"] = _strip_text(raw.get("dob")) or None
    out["birth_place"] = _strip_text(raw.get("birth_place")) or None
    out["marital_status"] = _strip_text(raw.get("marital_status")) or None
    g = _strip_text(raw.get("gender"))
    if g in {"ذكر", "Male", "male", "M", "m"}:
        out["gender"] = "male"
    elif g in {"أنثى", "انثى", "Female", "female", "F", "f"}:
        out["gender"] = "female"
    else:
        out["gender"] = None
    return out


def _normalise_student_row(raw: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    out["student_number"] = _ascii_digits(raw.get("student_number")) or None
    out["full_name"] = _strip_text(raw.get("full_name"))
    out["grade_code"] = _ascii_digits(raw.get("grade_code")) or None
    out["section_code"] = _strip_text(raw.get("section_code")) or None
    out["mobile"] = _ascii_digits(raw.get("mobile")) or None
    return out


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_workbook_bytes(content: bytes, filename: str) -> Dict[str, Any]:
    """
    Parse a raw Noor workbook. Raises NoorParseError on unrecoverable issues
    (returns no rows). Per-row normalisation issues live in the caller's
    dedupe pass — this function only handles physical parse + mapping.
    """
    if not content:
        raise NoorParseError("الملف فارغ")
    if len(content) > 10 * 1024 * 1024:
        raise NoorParseError("حجم الملف يتجاوز الحد المسموح (10 ميغابايت)")

    sheets = _read_workbook(content, filename)
    detected = detect_report_type(sheets)
    if detected is None:
        raise NoorParseError(
            "تعذّر التعرّف على نوع تقرير نور — حمّل تقرير المعلمين أو تقرير الطلاب"
        )

    if detected == TEACHER_REPORT:
        known = _TEACHER_HEADERS
        required = _TEACHER_REQUIRED
        normaliser = _normalise_teacher_row
    else:
        known = _STUDENT_HEADERS
        required = _STUDENT_REQUIRED
        normaliser = _normalise_student_row

    known_labels = set(known.keys())

    # Pick the sheet that actually carries the header row.
    chosen_sheet = None
    chosen_rows: List[List[Any]] = []
    header_idx: Optional[int] = None
    for name, rows in sheets:
        idx = _find_header_row(rows, required, known_labels)
        if idx is not None:
            chosen_sheet, chosen_rows, header_idx = name, rows, idx
            break

    if header_idx is None:
        raise NoorParseError(
            "تعذّر العثور على رؤوس الأعمدة — تأكد من أن الملف هو تقرير نور غير معدّل"
        )

    header_row = chosen_rows[header_idx]
    column_map = _build_column_map(header_row, known)
    required_internal = {known[k] for k in required}
    if not required_internal.issubset(set(column_map.values())):
        raise NoorParseError(
            "بعض الأعمدة المطلوبة غير موجودة في رؤوس التقرير"
        )

    parsed_rows: List[Dict[str, Any]] = []
    for offset, raw_row in enumerate(chosen_rows[header_idx + 1 :], start=1):
        if not raw_row or all(_strip_text(c) == "" for c in raw_row):
            continue
        raw_dict: Dict[str, Any] = {}
        for col_idx, field in column_map.items():
            if col_idx < len(raw_row):
                raw_dict[field] = raw_row[col_idx]
        normalised = normaliser(raw_dict)
        # Skip rows where the primary key field is blank (trailing junk rows).
        if detected == TEACHER_REPORT:
            if not normalised.get("national_id") and not normalised.get("full_name"):
                continue
        else:
            if not normalised.get("student_number") and not normalised.get("full_name"):
                continue
        parsed_rows.append(
            {"row_index": header_idx + offset + 1, "data": normalised}
        )

    return {
        "detected_type": detected,
        "sheet_name": chosen_sheet,
        "header_row": header_idx + 1,  # 1-based for UI display
        "mapped_columns": {str(k): v for k, v in column_map.items()},
        "rows": parsed_rows,
    }
