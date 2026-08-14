"""Regression tests for the IT workspace Excel export's spreadsheet
formula-injection hardening.

The export writer is the trust boundary: an attacker-controllable roster
value (student / parent name, behaviour note, etc.) that begins with a
formula trigger char (= + - @) must be neutralized to literal text so it
cannot execute when the workbook is opened in Excel / LibreOffice / Sheets.

These tests exercise the pure ``_build_workbook`` writer directly so no DB
fixtures are required — the security property lives in the writer.
"""
import io

import openpyxl

from src.modules.independent_teacher.controllers.independent_teacher_workspace_excel_export_routes import (
    _build_workbook,
    _sanitize_cell,
)


def test_sanitize_cell_prefixes_formula_triggers():
    for payload in ("=1+1", "+1", "-1", "@SUM(A1)", "\tx", "\rx"):
        out = _sanitize_cell(payload)
        assert out == "'" + payload, payload
    # Benign strings and non-strings pass through untouched.
    assert _sanitize_cell("Ahmad") == "Ahmad"
    assert _sanitize_cell("") == ""
    assert _sanitize_cell(5) == 5
    assert _sanitize_cell(None) is None


def test_workbook_neutralizes_formula_injection_in_cells_and_headers():
    payload = '=HYPERLINK("http://evil","x")'
    sheets = {
        "الطلاب": [
            {"الاسم الكامل": payload, "ملاحظات": "+cmd|'/c calc'!A1"},
        ],
    }
    raw = _build_workbook(sheets)
    assert raw[:2] == b"PK"  # valid xlsx (zip) container

    wb = openpyxl.load_workbook(io.BytesIO(raw))
    seen_formula_like = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            for cell in row:
                if isinstance(cell, str) and (
                    "HYPERLINK" in cell or "cmd" in cell
                ):
                    seen_formula_like.append(cell)
                # No cell may be stored as an evaluated formula.
                if isinstance(cell, str):
                    assert not cell.startswith("="), cell

    assert seen_formula_like, "expected payload cells to be present"
    for cell in seen_formula_like:
        assert cell.startswith("'"), cell
