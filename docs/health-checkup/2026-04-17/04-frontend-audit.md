# Phase 3 — Frontend Audit

**Date:** 2026-04-17 · **Status:** ✅ Complete (audit only)
**Stack:** React 19 · react-scripts 5.0.1 + craco · react-router-dom 7 · Tailwind + shadcn (Radix) · sonner · recharts · jspdf · date-fns

## 1. Inventory

- **55 pages**, **22 top-level components**, **66 runtime dependencies**
- **3513 i18n keys × 2 languages, perfect parity** (en==ar, 0 missing)
- Production build size:
  - `main.25304d41.js`: **4 708 KB raw / 1 045 KB gzipped** ← dominant
  - 4 chunks (≤ 396 KB / 124 KB gz)
  - `main.css`: 272 KB raw / 41 KB gz

## 2. Findings

| ID | Sev | Finding |
|---|---|---|
| **F-01** | 🟧 High | **Almost no route-based code-splitting.** Only `AIInsightsPage` uses `React.lazy`. All other 54 pages are statically imported in `frontend/src/routes/appRoutes.js`, which is why `main.js` is 4.7 MB / 1 MB gz. Splitting Teacher/Parent/Student portals + Platform admin pages would cut initial bundle ~40-60%. |
| **F-02** | 🟧 High | **Heavyweight deps shipped to all users:** `jspdf` (29 MB unpacked), `react-day-picker` (44 MB), `html2canvas` (4.4 MB), `recharts` (9 MB), `lucide-react` (41 MB) all in main bundle. Most are used only by 1-2 pages (PDF export, date pickers, charts). Lazy-load by route to remove from first paint. |
| **F-03** | 🟨 Medium | **`date-fns-jalali` (16 MB) duplicated alongside `date-fns` (36 MB).** Dual locale libs — verify both are actually needed; if Hijri rendering can be done by `hijri-converter` (1.1 MB, already installed), drop `date-fns-jalali`. |
| **F-04** | 🟨 Medium | **`core-js` AND `core-js-pure` (15 MB each).** Likely accidental duplicate from a sub-dep. De-dupe via package resolution or upgrade. |
| **F-05** | 🟨 Medium | **CRA + craco on React 19** is an unusual / lightly-supported combo. CRA itself is unmaintained. Long-term plan: migrate to Vite (5–10× faster dev start, smaller prod bundles, native ESM, used by NASSAQ's mockup-sandbox already). |
| **F-06** | 🟩 Low | **`console.log/warn/error` calls** in 10+ runtime files (StudentsPage, AcademicStructurePage, CommunicationCenterPage, IntegrationsPage, hooks, contexts). Strip via babel plugin or guard with `__DEV__`. |
| **F-07** | 🟩 Low | **Browser-side WebSocket connects to `/api/ws/notifications`** (good). But the bare `/ws` endpoint receives unauthenticated probes (visible in backend logs) and is correctly rejected with 403 by the explicit `reject_bare_ws` handler. No action needed. |
| **F-08** | 🟩 Low | **i18n parity is perfect** (3513 keys both sides). No missing translations. |
| **F-09** | 🟩 Low | **CSS bundle 272 KB** — Tailwind purge appears active (only used utilities remain). 41 KB gz is acceptable. |
| **F-10** | ⚪ Polish | **Browser console errors observed during pre-scan** were 504-proxy errors that resolved as soon as the backend workflow was running — symptom of the dev-proxy retry behaviour, not an app bug. |

## 3. Recommendations (deferred to Phase 5 / future PRs)

- **F-01** lazy-load 4 portal modules (Teacher, Student, Parent, Platform admin) — biggest win, moderate risk (named-export wrapping). Recommended PR.
- **F-02** dynamically `import()` `jspdf`, `html2canvas`, `recharts` only where used.
- **F-03 / F-04** package-resolution dedupe.
- **F-05** Vite migration is a separate project.

## Gate

✅ Phase 3 complete. **Proceeding to Phase 4 (E2E reliability per role).**
