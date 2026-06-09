"""IT Phase 2 — Workspace student-report export (Task #840).

Covers the new ``GET /independent-teacher/reports/export`` endpoint:

  (a) non-IT role → 403 (role gate)
  (b) happy path: performance + attendance, PDF + xlsx, per-student and
      aggregate, stream a usable file pinned to the caller's workspace
  (c) cross-workspace ``student_id`` → 404 (spec §8 inv. 3)
  (d) cross-workspace ``class_id`` → 404 (spec §8 inv. 3)
  (e) inactive / unknown ``student_id`` → 404
  (f) MFA step-up gate: enforcement on + no recent MFA → 403 with the
      canonical step-up envelope; with recent MFA + active passkey → 200
  (g) invalid query params (bad kind/format) → 422

The default test env runs with the MFA demo kill switch ON
(``MFA_ENFORCEMENT_DISABLED=true``), so the happy-path cases don't need a
recent-MFA token; the gate test forces enforcement back on.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from dependencies import db, UserRole
from engines.sql_utils import gd_insert

from _it_fixtures import (
    headers,
    it_headers,
    mk_it_workspace,
    seed_active_passkey,
)


async def _mk_attendance(wsid: str, sid: str, cid, day: datetime, status: str) -> None:
    await gd_insert(db.session, "attendance", {
        "id": str(uuid.uuid4()),
        "school_id": wsid,
        "class_id": cid,
        "student_id": sid,
        "date": day.isoformat(),
        "status": status,
        "is_excused": status == "excused",
    })


# ----------------------------------------------------------------------
# (a) Non-IT role → 403
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_reports_export_non_it_role_is_forbidden(client):
    sid = str(uuid.uuid4())
    await gd_insert(db.session, "schools", {
        "id": sid, "name": "S", "code": f"S{sid[:6]}", "status": "active",
        "country": "SA", "language": "ar",
    })
    uid = str(uuid.uuid4())
    await gd_insert(db.session, "users", {
        "id": uid, "role": UserRole.SCHOOL_PRINCIPAL.value,
        "tenant_id": sid, "email": f"p-{uid}@t.test",
        "full_name": "P", "is_active": True, "password_hash": "x",
    })
    h = headers(uid, UserRole.SCHOOL_PRINCIPAL.value, sid)
    r = await client.get(
        "/independent-teacher/reports/export",
        headers=h, params={"kind": "attendance", "format": "pdf"},
    )
    assert r.status_code == 403, r.text


# ----------------------------------------------------------------------
# (b) Happy path — per-student + aggregate, both kinds, both formats
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_reports_export_per_student_attendance_pdf_and_xlsx(client):
    ctx = await mk_it_workspace()
    sid = ctx["student_id"]
    cid = ctx["class_id"]
    now = datetime.now(timezone.utc)
    for i in range(1, 4):
        await _mk_attendance(ctx["wsid"], sid, cid, now - timedelta(days=i), "present")

    h = it_headers(ctx)

    r = await client.get(
        "/independent-teacher/reports/export",
        headers=h,
        params={"kind": "attendance", "format": "pdf", "student_id": sid},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
    assert "attachment" in r.headers["content-disposition"]
    assert ".pdf" in r.headers["content-disposition"]

    r = await client.get(
        "/independent-teacher/reports/export",
        headers=h,
        params={"kind": "attendance", "format": "xlsx", "student_id": sid},
    )
    assert r.status_code == 200, r.text
    # xlsx (zip) magic bytes
    assert r.content[:2] == b"PK"
    cd = r.headers["content-disposition"]
    assert "attachment" in cd and ".xlsx" in cd


@pytest.mark.asyncio
async def test_reports_export_per_student_performance_pdf(client):
    ctx = await mk_it_workspace()
    sid = ctx["student_id"]
    h = it_headers(ctx)
    r = await client.get(
        "/independent-teacher/reports/export",
        headers=h,
        params={"kind": "performance", "format": "pdf", "student_id": sid},
    )
    assert r.status_code == 200, r.text
    assert r.content[:4] == b"%PDF"


@pytest.mark.asyncio
async def test_reports_export_aggregate_no_student_succeeds(client):
    # No student_id → aggregate report for the whole workspace. An empty
    # workspace still produces a usable file (empty data, not an error).
    ctx = await mk_it_workspace(with_student=False, with_parent=False)
    h = it_headers(ctx)
    for kind in ("attendance", "performance"):
        r = await client.get(
            "/independent-teacher/reports/export",
            headers=h, params={"kind": kind, "format": "xlsx"},
        )
        assert r.status_code == 200, (kind, r.text)
        assert r.content[:2] == b"PK", kind


# ----------------------------------------------------------------------
# (c) Cross-workspace student_id → 404 (spec §8 inv. 3)
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_reports_export_cross_workspace_student_404(client):
    a = await mk_it_workspace()
    b = await mk_it_workspace()
    h = it_headers(a)
    r = await client.get(
        "/independent-teacher/reports/export",
        headers=h,
        params={"kind": "attendance", "format": "pdf", "student_id": b["student_id"]},
    )
    assert r.status_code == 404, r.text


# ----------------------------------------------------------------------
# (d) Cross-workspace class_id → 404 (spec §8 inv. 3)
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_reports_export_cross_workspace_class_404(client):
    a = await mk_it_workspace()
    b = await mk_it_workspace()
    h = it_headers(a)
    r = await client.get(
        "/independent-teacher/reports/export",
        headers=h,
        params={"kind": "attendance", "format": "xlsx", "class_id": b["class_id"]},
    )
    assert r.status_code == 404, r.text


# ----------------------------------------------------------------------
# (e) Unknown / inactive student_id → 404
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_reports_export_unknown_student_404(client):
    ctx = await mk_it_workspace()
    h = it_headers(ctx)
    r = await client.get(
        "/independent-teacher/reports/export",
        headers=h,
        params={"kind": "performance", "format": "pdf", "student_id": str(uuid.uuid4())},
    )
    assert r.status_code == 404, r.text


# ----------------------------------------------------------------------
# (f) MFA step-up gate
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_reports_export_requires_recent_mfa(client, monkeypatch):
    # Default test env runs with the kill switch ON; force enforcement on so
    # the step-up gate fires. is_enforcement_disabled() reads env fresh.
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "false")
    ctx = await mk_it_workspace()
    h = it_headers(ctx, with_mfa=False)  # no mfa_recent_at claim
    r = await client.get(
        "/independent-teacher/reports/export",
        headers=h,
        params={"kind": "attendance", "format": "pdf", "student_id": ctx["student_id"]},
    )
    assert r.status_code == 403, r.text
    detail = r.json().get("detail") or r.json().get("error") or {}
    s = str(detail)
    assert "MFA_STEPUP_REQUIRED" in s or "MFA_PASSKEY_REQUIRED" in s


@pytest.mark.asyncio
async def test_reports_export_with_recent_mfa_succeeds(client, monkeypatch):
    monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "false")
    ctx = await mk_it_workspace()  # mk_it_workspace seeds an active passkey
    await seed_active_passkey(ctx["uid"])
    h = it_headers(ctx, with_mfa=True)
    r = await client.get(
        "/independent-teacher/reports/export",
        headers=h,
        params={"kind": "attendance", "format": "pdf", "student_id": ctx["student_id"]},
    )
    assert r.status_code == 200, r.text
    assert r.content[:4] == b"%PDF"


# ----------------------------------------------------------------------
# (g) XLSX/CSV formula-injection is neutralized (attacker-controlled name)
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_reports_export_xlsx_neutralizes_formula_injection():
    # The export writer is the security boundary: a stored student name that
    # begins with "=" must render as literal text, not an evaluated formula.
    from engines.export_engine import ExportEngine

    payload = "=HYPERLINK(\"http://evil\",\"x\")"
    data = {
        "summary": {"name": payload, "total": 3},
        "top_students": [{"name": payload, "absent_count": 1}],
    }
    eng = ExportEngine.__new__(ExportEngine)  # no DB needed for the writers
    xbuf = eng._to_xlsx("school_attendance", data, {}, "")
    assert xbuf.getvalue()[:2] == b"PK"

    import openpyxl  # bundled via pandas xlsx stack
    wb = openpyxl.load_workbook(xbuf)
    found = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            for cell in row:
                if isinstance(cell, str) and "HYPERLINK" in cell:
                    found.append(cell)
    assert found, "expected the payload cell to be present"
    # Every emitted copy must be neutralized (apostrophe-prefixed → literal).
    for cell in found:
        assert cell.startswith("'="), cell

    cbuf = eng._to_csv("school_attendance", data)
    text = cbuf.getvalue().decode("utf-8-sig")
    assert "HYPERLINK" in text
    # No bare leading "=" formula survives in the CSV body.
    assert "\n=" not in text and not text.lstrip().startswith("=")


# ----------------------------------------------------------------------
# (h) Invalid params → 422
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_reports_export_invalid_params_422(client):
    ctx = await mk_it_workspace()
    h = it_headers(ctx)
    for params in (
        {"kind": "behaviour", "format": "pdf"},   # bad kind
        {"kind": "attendance", "format": "csv"},  # csv not allowed on this route
        {"format": "pdf"},                          # missing kind
        {"kind": "attendance"},                     # missing format
    ):
        r = await client.get(
            "/independent-teacher/reports/export", headers=h, params=params,
        )
        assert r.status_code == 422, (params, r.text)
