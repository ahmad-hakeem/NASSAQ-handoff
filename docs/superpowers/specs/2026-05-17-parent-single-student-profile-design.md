# Parent Portal — One Student Profile

**Date:** 2026-05-17
**Status:** Approved (brainstorm)
**Supersedes:** `2026-05-17-parent-edit-student-profile-entry-design.md` (the CTA added to `DetailsPanel` is reverted as part of this work).

## Problem

The Parent Portal has two competing "Student Profile" surfaces:

- Sidebar `ملف الطالب` → `/parent/children` (`ParentChildrenPage`) — avatar + KPIs + Weekly Analysis + tabs (Details/Schedule/Homework/Behavior).
- Standalone `/parent/child/:childId/profile` (`StudentProfilePage`) — gradient header with Reports/Achievements/Edit icon actions and chip groups for Health/Behavior/Family.

Parents see two different "Student Profiles" depending on entry point.

## Goal

A single Student Profile = the sidebar `/parent/children`. The Health/Behavior/Family content lives inside a single **Edit Student Profile** modal opened from the page header. Achievements and Reports header actions are dropped (revisit later). Old route redirects.

## Change

### 1. New component — `frontend/src/components/parent/StudentProfileDialog.jsx`

Self-contained Radix `Dialog` (matches existing `components/ui/dialog.jsx`).

- Props: `childId`, `open`, `onOpenChange`.
- Fetches `GET /parent-portal/child/:childId/profile` when opened. Re-fetches on `childId` change.
- View mode (default): renders the chip groups currently in `StudentProfilePage` — Health Conditions (colored), Behavioral Aspects (amber), Family Situation (text + sky chips). Owns its own label maps (`HEALTH_LABELS`, `BEHAVIOR_LABELS`, `FAMILY_LABELS`, `FAMILY_OTHER_LABELS`) moved out of `StudentProfilePage`.
- Edit toggle swaps to the existing `<ProfileEditor>` (unchanged). On save, refetches and returns to view mode. Cancel closes back to view mode.
- Per-child safety: parent passes `key={activeChild.id}` so sibling switching unmounts/remounts. `ProfileEditor`'s existing sibling-reset behavior + test still apply.

### 2. `ParentChildrenPage.jsx`

Add a clearly labeled secondary button — **تعديل ملف الطالب** / **Edit Student Profile** with `Pencil` icon — into the summary header card (gradient block, below the name/grade lines). Opens `<StudentProfileDialog>` for `activeChild.id`.

Test id: `link-edit-student-profile`.

### 3. Drop

`AchievementsArchive` and `ReportsPanel` header actions are not rendered anywhere on the new surface.

### 4. Cleanup (same change)

- **Delete** `frontend/src/pages/ParentPortal/StudentProfilePage.jsx`.
- **Remove** `StudentProfilePage` export from `frontend/src/pages/ParentPortal/index.js`.
- **Routes** (`frontend/src/routes/appRoutes.js`):
  - Remove the `ParentStudentProfilePage` lazy import.
  - Replace the route element at `/parent/child/:childId/profile` with `<ParentStudentTabRedirect tab="details" />` so old bookmarks/notifications/emails land on the unified page with the active child preselected.
- **Revert** the CTA added to `frontend/src/components/parent/panels/DetailsPanel.jsx` in the prior spec (no longer needed — entry moved one level up).

### Untouched

- Backend (routes, `_verify_parent_access`, schema, `profile_settings` shape).
- `ProfileEditor.jsx` and its sibling-switch test.
- `/parent/child/:childId/analytics` route (separate concern, not a duplicate profile).
- `ChildDetailsPage.jsx` (already dead code; separate cleanup if desired).
- Tabs: Details / Schedule / Homework / Behavior; KPI cards; Weekly Analysis panel.

## Acceptance

- Sidebar `ملف الطالب` → `/parent/children` is the only Student Profile surface.
- A visible **تعديل ملف الطالب** button on the header opens a modal with Health/Behavior/Family chips for the currently active child.
- "Edit" inside the modal swaps to the form; Save persists via `PUT /parent-portal/child/:childId/profile` and the view refreshes; Cancel closes without changes.
- Navigating to `/parent/child/:childId/profile` redirects to `/parent/children?child=:childId&tab=details`.
- Switching siblings via the shell switcher closes the dialog (component re-keyed on `activeChild.id`) and re-points it at the new child.
- No regression to Details/Schedule/Homework/Behavior tabs, KPIs, or weekly analysis.

## Files Touched

- `frontend/src/components/parent/StudentProfileDialog.jsx` (new)
- `frontend/src/pages/ParentPortal/ParentChildrenPage.jsx` (add button + dialog)
- `frontend/src/components/parent/panels/DetailsPanel.jsx` (revert prior CTA)
- `frontend/src/pages/ParentPortal/StudentProfilePage.jsx` (deleted)
- `frontend/src/pages/ParentPortal/index.js` (remove export)
- `frontend/src/routes/appRoutes.js` (redirect old route, drop lazy import)
