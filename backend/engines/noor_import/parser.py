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
    """Raised when a Noor workbook cannot be parsed safely.

    `diagnostics` (when present) carries server-side context — filename,
    size, leading-bytes hex, and per-reader exception class+message — that
    callers should log at WARNING level. It is NEVER surfaced to the user.
    """

    def __init__(self, message: str, diagnostics: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.diagnostics = diagnostics


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

_OLE2_MAGIC = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"


def _looks_like_html(content: bytes) -> bool:
    """Sniff whether the leading bytes look like an HTML document.

    Tolerates a UTF-8/UTF-16 BOM and any leading whitespace, then checks
    for an HTML/table opening tag. Used as a guard before invoking the
    pandas HTML fallback so corrupt binary files are not mis-parsed as a
    one-cell HTML table.
    """
    if not content:
        return False
    head = content[:4096]
    # Strip common BOMs
    for bom in (b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff"):
        if head.startswith(bom):
            head = head[len(bom):]
            break
    head = head.lstrip()
    if not head.startswith(b"<"):
        return False
    lowered = head[:512].lower()
    return any(
        tag in lowered
        for tag in (b"<html", b"<table", b"<!doctype html", b"<meta", b"<body")
    )


def _read_workbook(content: bytes, filename: str) -> List[Tuple[str, List[List[Any]]]]:
    """
    Returns [(sheet_name, rows)] where rows is a list-of-lists of raw cell
    values. Picks the reader by the filename extension; falls back to the
    other reader if the first attempt fails (some Noor exports mislabel the
    extension). When BOTH binary readers fail and the leading bytes look
    like HTML, falls back to a pandas/lxml HTML-table reader so Noor
    exports that save as `<table>`-disguised `.xls` still parse.

    On total failure, raises NoorParseError carrying structured server-only
    diagnostics so the caller can log what each reader saw without
    surfacing it to the user.
    """
    name = (filename or "").lower()
    if name.endswith(".xls"):
        readers = [_read_xls, _read_xlsx]
    else:
        readers = [_read_xlsx, _read_xls]
    reader_errors: List[Tuple[str, str, str]] = []
    for reader in readers:
        try:
            return reader(content)
        except NoorParseError:
            raise
        except Exception as e:  # noqa: BLE001 — try the other reader
            reader_errors.append((reader.__name__, type(e).__name__, str(e)[:200]))
            logger.debug("Noor reader %s failed: %s", reader.__name__, e)

    # HTML fallback — only when the leading bytes actually look like HTML so
    # a corrupt binary file does not get mis-parsed as a one-cell table.
    if _looks_like_html(content):
        try:
            return _read_html(content)
        except NoorParseError:
            raise
        except Exception as e:  # noqa: BLE001
            reader_errors.append(("_read_html", type(e).__name__, str(e)[:200]))
            logger.debug("Noor reader _read_html failed: %s", e)

    diagnostics = {
        "filename": filename,
        "size": len(content),
        "head_hex": content[:16].hex(),
        "looks_like_html": _looks_like_html(content),
        "readers_tried": [
            {"reader": r, "error_type": t, "error_message": m}
            for r, t, m in reader_errors
        ],
    }
    raise NoorParseError(
        "تعذّر قراءة الملف — تأكد من أنه ملف Excel صالح من نظام نور",
        diagnostics=diagnostics,
    )


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

    try:
        book = xlrd.open_workbook(file_contents=content, formatting_info=False)
    except Exception:
        # Some Noor exports start with the OLE2 magic but have stray bytes
        # appended past the end of the compound document (a trailing
        # newline or framing junk) which trips xlrd 2.x. Try once more
        # after trimming trailing junk on a 512-byte sector boundary.
        if content.startswith(_OLE2_MAGIC) and len(content) > 512:
            trimmed_len = (len(content) // 512) * 512
            if trimmed_len != len(content) and trimmed_len >= 512:
                book = xlrd.open_workbook(
                    file_contents=content[:trimmed_len], formatting_info=False
                )
            else:
                raise
        else:
            raise
    out: List[Tuple[str, List[List[Any]]]] = []
    for sheet in book.sheets():
        rows: List[List[Any]] = []
        for r in range(sheet.nrows):
            rows.append([sheet.cell_value(r, c) for c in range(sheet.ncols)])
        out.append((sheet.name, rows))
    return out


def _read_html(content: bytes) -> List[Tuple[str, List[List[Any]]]]:
    """Fallback for Noor `.xls` exports that are actually HTML `<table>`
    documents. Uses pandas/lxml. Each table becomes a sheet so the
    downstream detection / header-scan code is unchanged.
    """
    import pandas as pd  # local import — cold path

    try:
        tables = pd.read_html(io.BytesIO(content), flavor="lxml", header=None)
    except ValueError as e:
        # pd.read_html raises ValueError("No tables found") — bubble up so
        # _read_workbook records it as a reader failure.
        raise RuntimeError(f"no html tables: {e}")
    out: List[Tuple[str, List[List[Any]]]] = []
    for idx, df in enumerate(tables):
        rows: List[List[Any]] = []
        for record in df.itertuples(index=False, name=None):
            rows.append(
                [None if (isinstance(v, float) and v != v) else v for v in record]
            )
        out.append((f"Table{idx + 1}", rows))
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
