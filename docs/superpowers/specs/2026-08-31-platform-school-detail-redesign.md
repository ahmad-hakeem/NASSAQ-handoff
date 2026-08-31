# Design Specification: Platform School Detail Page Overhaul

## 1. Overview
Redesign and polish the Platform Admin School Detail Page (`/platform/schools/:schoolId` - `PlatformSchoolDetailPage.jsx` and its sub-components) into a modern, enterprise SaaS management hub with clean code, harmonious colors (Nassaq brand palette: `#1C3D74` Navy, `#46C1BE` Teal, `#615090` Purple), balanced spacing, robust dark mode support, and an intuitive user experience.

---

## 2. Visual & Structural Design System

### 2.1 Color Tokens & Accents
- **Primary Brand**: `#1C3D74` (Deep Nassaq Navy) - Used for primary actions, header backdrop, and focused branding.
- **Teal Accent**: `#46C1BE` / `#38a19e` - Used for metric highlights, badges, active progress states, and action callouts.
- **Purple Accent**: `#615090` - Used for academic/classes badges and secondary category indicators.
- **Surfaces & Cards**:
  - Light: `bg-white` with subtle `border-slate-200/80` and multi-layered shadows (`shadow-sm`, `shadow-md`).
  - Dark: `dark:bg-slate-900` with `dark:border-slate-800` and dark slate backgrounds (`dark:bg-slate-950`).
- **Typography**:
  - Titles & Numbers: `font-cairo` for bold, readable headers and tabular numbers.
  - Body Text: `font-tajawal` for clean readability across Arabic and English.

---

## 3. Component Architecture & Modules

### 3.1 `PlatformSchoolDetailPage.jsx` (Main Container)
- **Top Bar / Breadcrumbs**: Clean, interactive navigation with back button to Schools Management, breadcrumb trail, and reload state.
- **Error & Loading States**: Polished animated spinner (`Loader2`) with branded teal color and centered error card with retry button.
- **Floating Modals**: Seamless integration with `SchoolCredentialsDialog` and `SchoolActionDialogs`.

### 3.2 `SchoolDetailHeader.jsx` (Hero Header & KPI Ribbon)
- **Hero Banner**: Deep gradient card (`#1C3D74` to `#152e57`) with subtle background pattern, school initials avatar badge, bilingual name display, code pill, and animated status pulse.
- **Action Bar**:
  - "Open School Dashboard" button with vibrant teal accent.
  - "Refresh" button with loading spinner when refreshing.
  - "Suspend / Activate" button with dynamic state handling.
- **KPI Metrics Ribbon**:
  - 4 high-impact metric cards (Students, Teachers, Classes, Total Users) with colored icons and clean typography.

### 3.3 `GeneralInfoTab.jsx` (Bento-Grid Layout)
- **Identity & System Card**: Tenant code, Internal ID, Creation date, and Account status badge.
- **Contact & Geographic Info Card**: Arabic name, English name, Official email, Contact phone, City, Region with smooth inline edit mode.
- **Suspension Alert**: Clear warning banner if the school is currently suspended with the recorded reason and timestamp.
- **Principal Credentials Card**: Integrated `SchoolCredentialsCard` with active credentials status, account details, and quick action to copy a formatted welcome email.

### 3.4 `SchoolCredentialsCard.jsx` & `SchoolCredentialsDialog.jsx`
- **Card**: Clean visual status indicating whether the principal account is provisioned or pending.
- **Dialog**: Responsive modal with email input, principal name, secure password generator with copy feature, and confirmation validation.
- **Welcome Message Generator**: Quick copyable text block pre-filled with login credentials and school portal link.

### 3.5 `SchoolUsersTab.jsx` (Users Directory)
- **Header**: User count badge and fast client-side search bar (filtering by name, email, or role).
- **Table View**: Polished table with initial avatars, bilingual role chips, status badges, and formatted timestamps.
- **Empty State**: Friendly illustration/icon for empty directory or unmatched search queries.

### 3.6 `AcademicStructureTab.jsx` (Students & Classes)
- **Students Table**: List of registered students with grade levels, enrollment status, and responsive scroll.
- **Classes Grid**: Bento cards showing class names, grades, and section icons.

### 3.7 `BillingSubscriptionTab.jsx` (Quota & Capacity)
- **Subscription Tier Card**: Enterprise plan overview and status badge.
- **Capacity Utilization Card**: Interactive student capacity meter (`utilizationPercent`) with progress bar and statistics.
- **Contract Information**: Information banner describing the enterprise cloud agreement.

### 3.8 `SchoolActivityTab.jsx` (Activity & Audit Timeline)
- **Vertical Timeline**: Activity entries with contextual action icons, actor email, formatted timestamps, and reason cards.
- **Empty State**: Clear indicator when no audit logs are available.

---

## 4. Verification & Testing
- Test with mock & live school IDs in light and dark modes.
- Test inline editing of school information.
- Test credential generation and copy functionality.
- Test school suspension and activation dialog flows.
- Verify responsive layout on mobile, tablet, and desktop screens.
