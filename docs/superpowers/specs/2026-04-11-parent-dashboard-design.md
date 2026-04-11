# Parent Dashboard (PRD) — Architecture & Design Spec

## Overview
A complete redesign of the parent portal in NASSAQ to provide parents with real-time student tracking, weekly analytics, a communication center, student profile management, cumulative analytics, and an AI chatbot — all in an Arabic-first RTL interface.

## Architecture Decisions

### Frontend Architecture
- **Framework**: React (existing CRA + CRACO setup)
- **UI**: Tailwind CSS + shadcn/ui components (existing)
- **Charts**: Recharts (already installed, v3.6.0)
- **Icons**: lucide-react (existing)
- **State**: React hooks + Context API (existing pattern)
- **i18n**: `useTranslation()` from ThemeContext (existing)
- **Layout**: `PortalLayout` component with `portalType="parent"` (existing)
- **Typography**: Cairo/Tajawal for Arabic (existing Tailwind config)

### Backend Architecture
- **Framework**: FastAPI (existing)
- **Data access**: `gd_*` helpers from `engines/sql_utils.py` (existing pattern)
- **Auth**: JWT + `require_roles([UserRole.PARENT])` (existing)
- **AI**: OpenAI integration via `hakim_ai_engine.py` (existing)
- **Parent-child linking**: `_find_children()` and `_verify_parent_access()` helpers (existing)

### File Organization (Frontend)
All new parent portal code lives under `frontend/src/pages/ParentPortal/` and `frontend/src/components/parent/`. This follows the existing pattern where portal pages are in `pages/ParentPortal/` and shared sub-components are extracted into `components/`.

```
frontend/src/
├── pages/ParentPortal/
│   ├── ParentPortalDashboard.jsx    # REWRITE — main dashboard (sections 1-7)
│   ├── ParentCommunicationCenter.jsx # NEW — unified comm center (section 8)
│   ├── StudentProfilePage.jsx        # NEW — profile + achievements (sections 9-10)
│   ├── StudentAnalyticsPage.jsx      # NEW — cumulative analytics (section 11)
│   ├── ChildDetailsPage.jsx          # KEEP — minor updates
│   ├── ChildSchedulePage.jsx         # KEEP
│   ├── ...other existing pages
│   └── index.js                      # UPDATE — add new exports
├── components/parent/
│   ├── StudentSwitcher.jsx           # NEW — child selector component
│   ├── SchoolDayProgress.jsx         # NEW — animated school day progress bar
│   ├── CurrentClassCard.jsx          # NEW — "where is student now" with countdown
│   ├── UpcomingClasses.jsx           # NEW — remaining classes list
│   ├── PerformanceIndicator.jsx      # NEW — performance card with trend
│   ├── WeeklyStory.jsx              # NEW — weekly analytics section
│   ├── HakimChatWidget.jsx          # NEW — floating AI chatbot
│   ├── ProfileEditor.jsx            # NEW — profile edit form with icons
│   ├── AchievementsArchive.jsx      # NEW — achievements list + upload
│   └── AnalyticsCharts.jsx          # NEW — radar/gauge/line chart components
└── hooks/
    └── useParentDashboard.js         # NEW — custom hook for dashboard state
```

### File Organization (Backend)
New endpoints are added to the existing `parent_portal_routes.py` file, keeping with the project pattern. If it grows too large, we split into a sub-module.

```
backend/routes/
├── parent_portal_routes.py          # EXTEND — new endpoints for all 5 tasks
```

## Section-by-Section Design

### 1. Student Selector (StudentSwitcher)
- Horizontal scrollable pill/chip bar at the top
- Each child shows avatar (emoji or photo) + first name
- Active child highlighted with brand color
- Switching triggers full dashboard data reload for that child
- State managed in `useParentDashboard` hook

### 2. Student Header + School Day Progress Bar
- Card showing: student name, school name, grade level
- Below: an animated horizontal progress bar representing the full school day
- Bar segments = periods from timetable (with start/end times)
- Current time position shown as a marker
- Completed periods filled/grayed, current period highlighted, remaining empty
- Auto-updates via `setInterval` (every 30 seconds)
- Text showing: "X حصص متبقية" (X periods remaining)

**Data source**: `/parent-portal/child/{id}/today-live` (NEW endpoint)

### 3. Top Navigation Icons
- Two icon buttons in the header area:
  1. **Calendar icon**: Opens weekly timetable (navigates to existing `/parent/child/{id}/schedule`)
  2. **Bell icon**: Opens notification panel with two tabs: "تنبيهات الإدارة" (Admin) and "تنبيهات المعلم" (Teacher)
- Notification badge count shows unread total
- Split notifications filtered by `sender_role` field

**Data source**: Existing `/parent-portal/notifications` endpoint with added `sender_role` filter

### 4. Performance Indicator Card
- Clean card showing:
  - Performance level text (e.g., "جيد ومستقر") derived from overall average
  - Trend arrow + percentage vs last week (e.g., "تحسن ٨٪")
  - Short motivational phrase (selected based on trend direction)
- Performance levels: ممتاز (≥90), جيد جداً (≥80), جيد (≥70), مقبول (≥60), يحتاج تحسين (<60)
- Trend calculated server-side comparing this week's avg vs last week's

**Data source**: `/parent-portal/child/{id}/today-live` includes `performance` object

### 5. "Where Is the Student Now?" Card
- Shows when school is in session:
  - "أين {name} الآن؟" header
  - Current subject name (large text)
  - Teacher name
  - Period time range
  - Live countdown timer (mm:ss) — client-side `setInterval`
- Outside school hours: shows "اليوم الدراسي انتهى" or "لم يبدأ بعد"
- Data comes from timetable sessions matched against current time + day

**Data source**: `/parent-portal/child/{id}/today-live` includes `current_class` object

### 6. Upcoming Classes
- Simple list below the current class card
- Each row: subject name, start time — end time
- Only shows remaining periods (after current time)
- Sorted by period number

**Data source**: `/parent-portal/child/{id}/today-live` includes `upcoming_classes` array

### 7. Weekly Story
- The ONLY analytical content on the main dashboard
- Card with sections:
  - Participation count (number badge)
  - Positive behaviors count (number badge)
  - Skills acquired (tag chips)
  - Strong subjects (green badges)
  - Subjects needing improvement (amber badges)
  - Remedial plans from teachers (expandable list)
  - Bar chart showing daily participation/behavior scores (Recharts BarChart)
  - Activity indicators (visual dots/progress)
  - "نصيحة الأسبوع" — weekly tip text
- Auto-refreshes every Sunday (server returns current week's data)
- Period: Saturday through Thursday of the current/most recent week

**Data source**: `/parent-portal/child/{id}/weekly-story` (NEW endpoint)

### 8. Communication Center (Separate Page)
- Accessible from portal navigation (not embedded in dashboard)
- Three sections:
  1. **Send Message**: Form with type dropdown (ملاحظة/اقتراح/استفسار), recipient picker (teacher/admin), message text. Success toast: "تم استلام رسالتكم، رضاكم محل اهتمامنا"
  2. **Medical Excuse**: Form with description, file upload (to admin only)
  3. **Conversation Inbox**: List of message threads with status
- System constraint: max 3 open requests. New submissions blocked with clear message until one closes.
- Open requests counted server-side per parent

**Data source**: Existing message/excuse endpoints + new limit enforcement

### 9. Student Profile (Separate Section)
- Profile Card showing: name, emoji/photo, grade, school, edit icon
- Edit mode (inline, same page):
  - Emoji picker (grid of emoji options)
  - Health conditions: icon-based multi-select (asthma, weak eyesight, allergies, etc.)
  - Behavioral aspects ("سلوك يحتاج تحسين"): icon-based multi-select (shyness, hyperactivity, difficulty concentrating)
  - Family situation: radio/dropdown (مع الوالدين / مع الأب فقط / مع الأم فقط / طرف آخر)
- "إنجازاتي" icon in profile card opens achievements archive

**Data source**: New profile fields on student record + new endpoints

### 10. Achievements Archive
- List/grid of all achievements (from parent, teacher, admin)
- Each achievement shows: name, type, source, date, file link
- Upload form: name, type selector, file upload
- Source badge: ولي الأمر / المعلم / الإدارة

**Data source**: New `student_achievements` collection/table + CRUD endpoints

### 11. Student Analytics (Inside Profile)
- Cumulative long-term analysis section
- Components:
  - Performance summary: overall level, average, class comparison
  - Gauge Chart: current performance level (Recharts custom)
  - Line Chart: performance trajectory over time
  - Radar Chart: subject distribution (Math, Science, Arabic, English, Digital Skills)
  - Strength/weakness cards: auto-generated from data patterns
  - Home follow-up indicator: composite score → status (مستقر / يحتاج متابعة / بحاجة دعم)
- Permission filtering:
  - Parent: sees ALL data (health, behavioral, social + academic)
  - Student: sees ONLY academic data, schedule, achievements

**Data source**: `/parent-portal/child/{id}/analytics` (NEW endpoint)

### 12. Hakim AI Chatbot
- Floating button (bottom-left for RTL) labeled "حكيم"
- Opens chat drawer/sheet
- Parent types question → Hakim responds with personalized advice
- Context: selected child's data (grades, weaknesses, behavior)
- Uses existing Hakim AI engine with parent-specific system prompt
- Conversation persists within session (React state)

**Data source**: Existing `/hakim/chat` endpoint with parent context extension

## New Backend Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/parent-portal/child/{id}/today-live` | GET | Current class, upcoming classes, school day progress, performance indicator |
| `/parent-portal/child/{id}/weekly-story` | GET | Weekly analytics: participation, behaviors, skills, subjects, tips |
| `/parent-portal/child/{id}/profile` | GET/PUT | Extended profile (emoji, health, behavior, family) |
| `/parent-portal/child/{id}/achievements` | GET/POST | Achievement archive CRUD |
| `/parent-portal/child/{id}/analytics` | GET | Cumulative analytics with charts data |
| `/parent-portal/child/{id}/analytics/class-comparison` | GET | Class average comparison |
| `/parent-portal/open-requests-count` | GET | Count of open requests for limit enforcement |
| `/hakim/parent-chat` | POST | Parent-context Hakim chat |

## Data Model Extensions

### Student record extensions (existing `students` table)
```
emoji: string (nullable)
health_conditions: string[] (e.g., ["asthma", "weak_vision", "allergy"])
behavioral_aspects: string[] (e.g., ["shyness", "hyperactivity", "concentration_difficulty"])
family_situation: string (nullable, enum: "both_parents", "father_only", "mother_only", "other")
```

### New: student_achievements collection
```
id: uuid
student_id: string (FK)
school_id: string (FK, tenant)
name: string
type: string (e.g., "academic", "sports", "arts", "other")
source: string (enum: "parent", "teacher", "admin")
source_user_id: string
file_url: string (nullable)
created_at: datetime
```

## Permission Model
| Data | Parent View | Student View |
|------|------------|--------------|
| Academic (grades, schedule, homework) | Yes | Yes |
| Achievements | Yes | Yes |
| Health conditions | Yes | No |
| Behavioral aspects | Yes | No |
| Family situation | Yes | No |
| Analytics (full) | Yes | Academic only |
| Communication center | Yes | No |

## Design System Alignment
- Colors: Indigo palette for parent portal (existing `PortalLayout` theming)
- Brand colors: brand-navy (#1C3D74), brand-purple (#615090), brand-turquoise (#46C1BE)
- Typography: Cairo/Tajawal (Arabic), existing Tailwind config
- Components: shadcn/ui Card, Badge, Button, Progress, Avatar, Tabs, Dialog, Sheet
- Charts: Recharts BarChart, LineChart, RadarChart, PieChart (for gauge)
- Alerts: `useNassaqAlert()` for errors/warnings
- Success notifications: `toast.success()` from sonner
- Loading: Skeleton screens (existing pattern)
- RTL: `dir="rtl"` with Tailwind logical properties (me/ms/ps/pe)
