# Platform School Detail Page Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the Platform Admin School Detail Page (`/platform/schools/:schoolId`) and its subcomponents with a modern SaaS Bento-grid layout, cohesive Nassaq palette (`#1C3D74` Navy, `#46C1BE` Teal, `#615090` Purple), balanced spacing, robust dark mode styling, and polished UX.

**Architecture:** Component modularization under `src/admin/features/schools/components/detail/` with clean props, centralized status/labels in `schoolConstants.js`, and reactive state management in `PlatformSchoolDetailPage.jsx`.

**Tech Stack:** React 18, Tailwind CSS, Lucide React, Radix UI (shadcn primitives), Sonner toasts.

---

### Task 1: Refactor and Enhance `SchoolDetailHeader.jsx`
**Files:**
- Modify: `frontend/src/admin/features/schools/components/detail/SchoolDetailHeader.jsx`

- [ ] **Step 1: Implement the Glassmorphic Hero Banner, bilingual title, status pulse badge, quick action buttons, and floating KPI metrics cards.**
- [ ] **Step 2: Verify light/dark theme contrast and responsiveness across screen sizes.**

---

### Task 2: Refactor `GeneralInfoTab.jsx` with Bento-Grid Layout
**Files:**
- Modify: `frontend/src/admin/features/schools/components/detail/GeneralInfoTab.jsx`

- [ ] **Step 1: Re-architect into clean grouped bento cards (Identity & System info, Contact & Location info, and Suspension details).**
- [ ] **Step 2: Implement smooth inline editing mode with proper input styling, clear validation cues, and clean action buttons.**

---

### Task 3: Enhance `SchoolCredentialsCard.jsx` & `SchoolCredentialsDialog.jsx`
**Files:**
- Modify: `frontend/src/admin/features/schools/components/detail/SchoolCredentialsCard.jsx`
- Modify: `frontend/src/admin/features/schools/components/detail/SchoolCredentialsDialog.jsx`

- [ ] **Step 1: Polish the Principal Credentials Card layout, status badge, copy-to-clipboard actions, and dynamic credentials alert with formatted welcome message generator.**
- [ ] **Step 2: Polish the Credentials Modal Dialog with password generator, visibility toggle, matching validation, and loading indicators.**

---

### Task 4: Enhance `SchoolUsersTab.jsx` (Users Directory)
**Files:**
- Modify: `frontend/src/admin/features/schools/components/detail/SchoolUsersTab.jsx`

- [ ] **Step 1: Enhance search filter (real-time name/email/role), responsive styled table, avatar initial bubbles, role badge pill styles, and empty states.**

---

### Task 5: Enhance `AcademicStructureTab.jsx` & `BillingSubscriptionTab.jsx`
**Files:**
- Modify: `frontend/src/admin/features/schools/components/detail/AcademicStructureTab.jsx`
- Modify: `frontend/src/admin/features/schools/components/detail/BillingSubscriptionTab.jsx`

- [ ] **Step 1: Redesign Academic Structure with tabbed/split view of students and modern class cards grid.**
- [ ] **Step 2: Redesign Billing & Subscription tab with student capacity utilization gauge, plan overview, and enterprise badge.**

---

### Task 6: Enhance `SchoolActivityTab.jsx` & `PlatformSchoolDetailPage.jsx` Integration
**Files:**
- Modify: `frontend/src/admin/features/schools/components/detail/SchoolActivityTab.jsx`
- Modify: `frontend/src/admin/features/schools/pages/PlatformSchoolDetailPage.jsx`

- [ ] **Step 1: Refactor Activity Log into an interactive vertical timeline with action icons, actor tags, and collapsible details.**
- [ ] **Step 2: Polish the main `PlatformSchoolDetailPage.jsx` page container, breadcrumbs, loading state, error card, and tab bar navigation.**

---

### Task 7: Full End-to-End Verification
- [ ] **Step 1: Verify all tabs (General Info, Users, Academic Structure, Billing, Activity Logs) on `http://localhost:3000/platform/schools/b7ae6a4a-a5fb-4278-8184-469e2bd6b237`.**
- [ ] **Step 2: Verify RTL and LTR support, dark mode, inline editing, and modal dialogs.**
