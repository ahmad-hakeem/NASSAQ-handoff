# Timetable System — Full Stack A-to-Z Audit

**Date:** 2026-04-17
**Type:** Read-only audit (no code changes)
**Deliverable:** Single markdown report at `docs/audits/2026-04-17-timetable-audit.md`

---

## 1. Goal

Produce one comprehensive audit report covering the entire school timetable
subsystem — backend, frontend, data quality, and end-to-end flow — with every
finding ranked by severity and tied to concrete file locations and recommended
fixes.

The audit is investigative and fresh: no prior assumptions about which areas
are weak. The report itself is the only output; no code is changed during the
audit.

## 2. Approach

Layer-by-layer sweep in dependency order, followed by a short end-to-end flow
walkthrough and a cross-cutting section. This gives a navigable single report
without duplicating findings.

### Method rules

- Read-only. No edits to source, schema, or data during the audit.
- Evidence-based. Every finding cites `path/to/file:line` (or a line range).
- Severity scale:
  - **Critical** — data loss, generation broken, security/RBAC hole,
    multi-tenant leak.
  - **High** — feature broken or unusable for a real school.
  - **Medium** — works but wrong, fragile, or poor UX.
  - **Low** — cleanup, polish, dead code, nits.
- Each finding records: ID, severity, title, location, description, why it
  matters, recommended fix, effort estimate (S/M/L).

## 3. Layers in scope (audit order)

1. **Data model & migrations**
   `backend/models/scheduling.py`, `backend/pg_models.py`,
   `backend/shared_models.py`, alembic versions touching timetable /
   constraints / time slots. Check entities, FKs, nullables, indexes,
   uniqueness, and tenant-scoped columns.

2. **Seed & reference data**
   `backend/seeds/timetable_hard_constraints.py`,
   `backend/seeds/timetable_soft_constraints.py`, default time slots /
   period templates, any default rooms or break periods. Completeness,
   realism, multi-tenancy.

3. **Constraints (hard + soft)**
   Definitions, evaluation logic, where they are enforced (DB / engine /
   API / UI). Coverage versus what a real school needs.

4. **Generation engine**
   `backend/engines/`, `backend/services/scheduling_service.py`, smart
   engine routes. Algorithm correctness, conflict detection
   (teacher/class/room), partial-data handling, timeouts, determinism,
   error reporting.

5. **API routes**
   `scheduling_*`, `principal_timetable_*`, `timetable_readiness_*`,
   `schedule_management_*`, `scheduling_smart_*`. Auth/RBAC, input
   validation, error responses, idempotency, pagination, tenant scoping.

6. **Frontend wizards & pages**
   `CreateScheduleWizard`, `SchedulePageNew`, `PrincipalTimetablePage`,
   `TeacherSchedulePage`, `TimeSlotsPage`, parent and student views.
   Loading / empty / error states, validation, i18n (en + ar with RTL).

7. **End-to-end flow**
   Empty school → academic year/term → classes / subjects / teachers →
   time slots → constraints → readiness check → generate → review →
   publish → consumed by teacher / student / parent.

8. **Cross-cutting**
   Multi-tenant isolation, performance on realistic school size,
   security/RBAC, audit logging, i18n, accessibility, automated test
   coverage for the timetable subsystem.

## 4. Report structure

The audit report at `docs/audits/2026-04-17-timetable-audit.md` will contain:

1. **Executive summary** — One paragraph plus a count table of
   Critical/High/Medium/Low per layer.
2. **Top 10 critical/high findings** — At-a-glance list for decision making.
3. **Layer-by-layer findings** — Sections matching layers 1–8 above. Each
   layer section opens with a short "what I looked at" (files inspected),
   followed by findings in the format defined in §2.
4. **End-to-end flow walkthrough** — Principal journey from empty school to
   published timetable, with any flow-only issues called out.
5. **Cross-cutting findings** — Tenancy, perf, security, i18n, a11y, tests.
6. **What works well** — Short positives section so the report is balanced.
7. **Recommended next steps** — Suggested order to address Critical → High
   items, grouped where one fix unblocks others.

## 5. Out of scope

- Any code, schema, or data changes (read-only audit).
- Re-architecture proposals unless a specific finding requires one.
- Unrelated modules (assessments, attendance, communications, billing,
  AI insights) except where they directly intersect timetable.
- Load testing or production data analysis. Where these would be valuable,
  the report will note it as a recommendation rather than perform it.

## 6. Deliverables

- Design spec: `docs/superpowers/specs/2026-04-17-timetable-audit-design.md`
  (this file).
- Audit report: `docs/audits/2026-04-17-timetable-audit.md` (produced by
  the implementation phase).

## 7. Success criteria

- Every layer in §3 has its own findings section in the report (or an
  explicit "no issues found" note).
- Every finding has severity, location, and a recommended fix.
- Top 10 list and executive summary make the state of the system
  understandable in under five minutes.
- Report is a single self-contained markdown file, navigable by section.
