"""IT Phase 2 — Workspace student-report export (Task #840).

A single IT-only endpoint that lets an Independent Teacher export the
parent/school-facing student reports (Performance, Attendance) for their
own synthetic workspace as PDF or Excel:

    GET /independent-teacher/reports/export
        ?kind=performance|attendance
        &format=pdf|xlsx
        &student_id=...      (optional — per-student report)
        &class_id=...        (optional — scope an aggregate to one class)
        &from=ISO&to=ISO     (optional — date window)

Workspace pinning rules (spec §8 inv. 1 + inv. 3):
  * ``school_id`` is ALWAYS derived server-side from
    ``itw_{user_id}`` — a client-supplied ``school_id`` is never honoured.
  * ``student_id`` is resolved through ``tenant_scoped_find_one`` and
    ``class_id`` through the IT's own ``classes`` rows; an unknown /
    cross-workspace id returns **404** so the API does not confirm the
    existence of foreign-tenant rows.

Authorization:
  * IT role gate (``is_independent_teacher``) AND
  * ``Permission.ANALYTICS_READ_OWN_WORKSPACE`` (same entitlement the
    analytics dashboard/export already requires), both enforced at the
    route layer, AND
  * ``require_recent_mfa_403`` — exports are write-equivalent disclosure
    actions and must carry a fresh MFA proof. The 403 envelope lets the
    FE axios interceptor replay the request after passkey assertion.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from auth_scope import (
    INDEPENDENT_TEACHER_DENIED_AR,
    independent_workspace_id,
    is_independent_teacher,
)
from dependencies import (
    db, get_current_user, export_engine, require_recent_mfa_403,
)
from engines.sql_utils import gd_find_one
from middleware.rbac import Permission, ROLE_PERMISSIONS
from utils.tenant_scope import tenant_scoped_find_one


logger = logging.getLogger("nassaq.it_reports")

router = APIRouter(
    prefix="/independent-teacher/reports",
    tags=["IT Reports"],
)

_MSG_PERMISSION = "ليست لديك صلاحية تصدير التقارير."
_MSG_STUDENT_NOT_FOUND = "الطالب غير موجود في مساحتك."
_MSG_CLASS_NOT_FOUND = "الفصل غير موجود في مساحتك."
_MSG_BAD_PARAMS = "معاملات التقرير غير صالحة."
_MSG_EXPORT_FAILED = "تعذّر تصدير التقرير — حاول لاحقًا."

# kind -> (per-student report_type, aggregate report_type)
_KIND_MAP = {
    "performance": ("student_performance", "school_academic"),
    "attendance": ("student_attendance", "school_attendance"),
}

# Exports are write-equivalent disclosure actions — require fresh MFA.
_recent_mfa_403 = require_recent_mfa_403()


async def _require_independent_teacher(
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not is_independent_teacher(current_user):
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)
    # Permission gate (independent of the role default mapping). Check both
    # the JWT-carried slice and the role default so a future role-permission
    # tweak cannot silently widen access without an explicit RBAC decision.
    perm = Permission.ANALYTICS_READ_OWN_WORKSPACE.value
    perms = current_user.get("permissions") or []
    role_perms = ROLE_PERMISSIONS.get(current_user.get("role") or "", [])
    if perm not in perms and perm not in role_perms:
        raise HTTPException(status_code=403, detail=_MSG_PERMISSION)
    return current_user


@router.get("/export")
async def export_workspace_report(
    kind: str = Query(..., pattern="^(performance|attendance)$"),
    format: str = Query(..., pattern="^(pdf|xlsx)$"),
    student_id: Optional[str] = Query(default=None),
    class_id: Optional[str] = Query(default=None),
    from_: Optional[str] = Query(default=None, alias="from"),
    to: Optional[str] = Query(default=None),
    current_user: dict = Depends(_require_independent_teacher),
    _mfa: dict = Depends(_recent_mfa_403),
):
    workspace_id = independent_workspace_id(current_user)
    if not workspace_id:
        # An IT account must always resolve to its synthetic workspace.
        raise HTTPException(status_code=403, detail=INDEPENDENT_TEACHER_DENIED_AR)

    per_student_type, aggregate_type = _KIND_MAP[kind]

    # Validate the requested scope BEFORE generating anything. A foreign /
    # unknown id must 404 (never 403/200) so the API does not confirm the
    # existence of cross-workspace rows (spec §8 inv. 3).
    if student_id:
        student = await tenant_scoped_find_one(
            db.session, "students", student_id, current_user,
        )
        if not student or not student.get("is_active", True):
            raise HTTPException(status_code=404, detail=_MSG_STUDENT_NOT_FOUND)
        report_type = per_student_type
    else:
        report_type = aggregate_type

    if class_id:
        cls_row = await gd_find_one(
            db.session, "classes", {"id": class_id, "school_id": workspace_id},
        )
        if not cls_row:
            raise HTTPException(status_code=404, detail=_MSG_CLASS_NOT_FOUND)

    try:
        buf, media_type, filename = await export_engine.export(
            report_type=report_type,
            fmt=format,
            school_id=workspace_id,
            start_date=from_,
            end_date=to,
            class_id=class_id,
            student_id=student_id,
        )
    except ValueError:
        raise HTTPException(status_code=400, detail=_MSG_BAD_PARAMS)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("IT workspace report export failed: %s", exc)
        raise HTTPException(status_code=500, detail=_MSG_EXPORT_FAILED)

    return StreamingResponse(
        buf,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
