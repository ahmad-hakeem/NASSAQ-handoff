# Parent Portal — Visible "Edit Student Profile" Entry Point

**Date:** 2026-05-17
**Status:** Approved (brainstorm)
**Scope:** UX-only — single-file change in `frontend/src/components/parent/panels/DetailsPanel.jsx` (the live parent details panel rendered by `ParentChildrenPage` for `/parent/children?tab=details`).

## Problem

The per-student profile editor (`StudentProfilePage` + `ProfileEditor`) already exists, is routed at `/parent/child/:childId/profile`, and is correctly scoped per child (server-enforced via `_verify_parent_access` in `backend/routes/parent_portal_routes.py`; client state reseeded on child switch by `ProfileEditor` and `ParentActiveStudentContext`). Parents cannot find it. The only entry point from the child detail view is an unlabeled ghost icon button (`<User />`) in the top-right of the gradient header card, which reads as part of the avatar treatment rather than as an action.

## Approved Direction (from brainstorm)

Make the entry point visible inside the child detail view only. Do not add new entry points elsewhere (children hub, shell, modal). Do not change the editor, the route, the API, or the data model.

## Change

The live parent details surface is **not** `ChildDetailsPage.jsx` — the route `/parent/child/:childId` is redirected to `/parent/children?child=...&tab=details`, which renders `components/parent/panels/DetailsPanel.jsx` inside `ParentChildrenPage`. The CTA must live there.

In `frontend/src/components/parent/panels/DetailsPanel.jsx`, add a clearly labeled secondary action button at the top of the panel:

- Label (Arabic): `تعديل ملف الطالب`
- Label (English): `Edit Student Profile`
- Icon: `Pencil` from `lucide-react`
- Visual: full-width outline button at the top of the Details panel, above the quick-stats cards
- Destination: `<Link to={\`/parent/child/${childId}/profile\`}>` where `childId` is the prop passed by `ParentChildrenPage` from `ParentActiveStudentContext` (auto-swaps with sibling switch)
- RTL/LTR: uses the existing `isRTL` flag and Cairo font
- Test id: `link-edit-student-profile`

## Out of Scope

- No backend changes.
- No new route.
- No change to `ProfileEditor`, `StudentProfilePage`, or `_verify_parent_access`.
- No change to `students.profile_settings` shape or any other schema.
- No new entry points on `/parent/children`, the shell, or as a modal.
- No pixel-match redesign of the editor to the attached screenshots.

## Acceptance

- A parent on the live details surface (`/parent/children?tab=details`, also reached via the legacy `/parent/child/:childId` redirect) sees a clearly labeled `تعديل ملف الطالب` / `Edit Student Profile` button at the top of the details panel without scanning.
- Clicking it opens the existing editor for that exact active `childId`.
- Switching children via `ShellStudentSwitcher` re-keys the panel (`key={\`details-${activeChild.id}\`}`) so the CTA always points at the currently active child; the editor itself is already sibling-safe (covered by `frontend/src/components/parent/__tests__/ProfileEditor.test.jsx`).
- No regression to the panel's quick-stats, inner sub-tabs, or `StudentInsightsPanel`.

## Files Touched

- `frontend/src/components/parent/panels/DetailsPanel.jsx` (CTA added at top of panel; `Link`, `Button`, `Pencil` imports added).
