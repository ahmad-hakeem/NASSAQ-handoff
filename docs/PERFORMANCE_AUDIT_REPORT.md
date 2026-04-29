# Frontend Performance & UX Audit — Diagnostic Report

**Scope:** `frontend/` (CRA + react-router-dom v7, React 19, axios, no client cache)
**Mode:** Read-only diagnosis. No code changes performed. Awaiting approval before fixes.
**Date:** 2026-04-29

---

## TL;DR — Why the app feels sluggish

Three reinforcing problems are fighting each other on every navigation:

1. **There is no app shell.** The Sidebar/Header are *not* a parent layout — they are duplicated inside every page chunk (58 pages re-import and re-render `<Sidebar>` themselves). Combined with one big `<Suspense>` wrapping all `<Routes>`, every route change unmounts the previous Sidebar and shows a full-screen spinner until the new chunk + its first paint resolve.
2. **There is no client-side data cache.** No React Query / SWR / RTK Query is installed (`grep` confirms zero usage). Every page mount fires its own `Promise.all([...])` of 3–7 REST calls. Navigating Admin → Schools → back to Admin re-runs the full burst each time.
3. **Two of the global Providers create new object/function references on every render**, which cascades re-renders into all consumers (`useAuth`, `useTheme`) — that's most of the tree.

Below: ranked findings with file/line evidence and a phased action plan.

---

## 🔍 Suspect Area 1 — Data Fetching & Caching  (HIGHEST IMPACT)

### Findings

**1.1 No client-side cache layer at all.**
`rg "react-query|@tanstack|swr|useSWR" frontend/src` → **zero hits**. Data fetching is hand-rolled `axios` inside per-component `useEffect`s. Nothing is cached, deduped, or revalidated in the background. A user revisiting the same page 4× pays the full network cost 4×.

**1.2 Per-page bursts of parallel REST calls.**
Each page mount issues a `Promise.all([...])` of 2–7 endpoints. Examples (file:line):

| Page | Endpoints called in parallel on mount |
|---|---|
| `pages/AdminDashboard.jsx:38` | `/analytics/overview`, `/reports/school/overview`, `/reports/school/behavior` |
| `pages/UsersClassesManagement.jsx:930` | `/students`, `/teachers`, `/classes`, `/grades`, `/parents` |
| `pages/AssessmentPage.jsx:1184` | `/classes`, `/teachers`, `/committees`, `/schedule` |
| `pages/AccountSettingsPage.jsx:248` | `/roles`, `/notifications`, `/preferences`, `/sessions` |
| `pages/SchedulePageNew.jsx:328` | `/slots`, `/teachers`, `/classes`, `/timetables` |
| `pages/AIInsightsPage.jsx:658` | `/overview`, `/predictions`, `/recommendations`, `/alerts`, `/risks` |
| `pages/StudentsPage.jsx:101` | `/students`, `/classes`, `/grades` |
| `components/wizards/SendNotificationWizard.jsx:80` | 5 lookup endpoints, fired again every time the wizard opens |
| `pages/SystemMonitoringPage.jsx` | **11** distinct `api.get`/`api.post` calls |

`rg -c "useEffect" frontend/src/pages/*.jsx` shows 5–9 effects per dashboard page; many fetch on every mount unconditionally. None of these results are remembered after unmount.

**1.3 Duplicate / overlapping fetches.**
- `NotificationBell` (`components/notifications/NotificationBell.jsx:73`) polls `/notifications/unread-count` every **30 s** and re-mounts on every navigation (because it lives inside per-page `<Sidebar>` instances — see §2). So in a 5-minute browsing session that visits 6 pages you can rack up the unread-count call 16+ times.
- `Sidebar` (`components/layout/Sidebar.jsx:101`) calls `/user-roles/my-roles` on every mount with a 100 ms `setTimeout` debounce — but because the Sidebar lives inside each route, it remounts on every navigation, so this fires every page change.
- `AuthContext` `fetchUser` (`contexts/AuthContext.js:188`) is wired through a `useCallback([token, api])` but `api` is stable (memoized) so this is fine. The effect itself uses a 20 s timeout with one retry — 40 s of patience before falling back. If `/auth/me` is slow the whole app sits behind the protected-route spinner for that long.

**1.4 No request de-duplication.**
Two components mounting at the same time and asking for the same endpoint will fire two HTTP requests. There is no in-flight request map.

**1.5 No HTTP-level caching headers being leveraged.**
Axios instance (`contexts/AuthContext.js:79`) sets only `Content-Type`. No conditional GETs, no `etag` handling. The dev server (`craco.config.js`) sets `Cache-Control: public, max-age=0, must-revalidate` for all assets, which forces revalidation on every load (correct for HTML, but applied broadly).

### Anti-patterns
- "Fetch on mount, throw on unmount" everywhere.
- Promise.all stampedes (the user's screen is white until the *slowest* of 7 calls returns).
- Toast spam (`toast.error` from inside the response interceptor at `AuthContext.js:174` will fire for every failed call in a stampede).

### Impact
Every navigation = ~3–7 fresh HTTP round trips (often the same data the previous page already had). This is, by a wide margin, the largest contributor to perceived sluggishness.

---

## 🔍 Suspect Area 2 — Routing & App-Shell Rendering  (HIGH IMPACT, LOW EFFORT TO FIX)

### Findings

**2.1 No layout route for the main app. The Sidebar is part of each page.**
`rg -l "<Sidebar[ />]" frontend/src/pages | wc -l` → **57 pages** (verified). Every non-portal page imports `Sidebar` and renders it itself, e.g.:
- `pages/AdminDashboard.jsx:5,245,312` (`<Sidebar>...</Sidebar>` wraps the page body)
- `pages/SchoolDashboard.jsx:4,22`
- `pages/TeacherDashboard.jsx:14,142` (sibling layout)
- + 54 others

**Partial exception — student/parent portals.** `frontend/src/components/portal/PortalLayout.jsx` exists and *is* used by the Student/Parent portal pages (e.g. `pages/StudentPortal/*`, `pages/ParentPortal/*` — 10+ files reference it). However, those portal pages are themselves declared at the *route level* as lazy chunks (see `routes/appRoutes.js:89-111`). So when navigating *between portal pages*, `PortalLayout` is re-mounted from inside each lazy chunk too — same shell-flash problem, just for a smaller layout. There is no route-level layout that survives across navigations.

Result: when react-router swaps routes, the entire previous Sidebar/PortalLayout (and Header, NotificationBell) is unmounted along with the previous page, then a new one is mounted inside the next chunk. Sidebar then re-fires `/user-roles/my-roles`, NotificationBell re-fires `/notifications/unread-count`.

**2.2 One `<Suspense>` wraps every route, and its fallback is a full-page spinner.**
`routes/appRoutes.js:151`:
```jsx
<Suspense fallback={<RouteFallback />}>
  <Routes> ... </Routes>
</Suspense>
```
`RouteFallback` is a `min-h: 60vh` centered spinner. While the next lazy chunk is downloading/parsing, this spinner replaces *everything inside the router* — which, given §2.1, includes the previous Sidebar/Header. **This is exactly the "white screen with spinner during navigation" symptom.**

**2.3 Protected/Public guards add a second full-page spinner.**
`components/guards/RouteGuards.js:16-26`:
```jsx
if (loading) return <LoadingSpinner />;  // min-h-screen, replaces the shell
```
While `AuthContext.loading === true` (initial `/auth/me`, plus any background refresh), the guard returns a `min-h-screen` spinner and unmounts the entire route tree (Sidebar included). For the first page load this is up to ~20 s with one retry (`AuthContext.js:214`).

**2.4 Public landing/login eagerly imported, but everything else is lazy — no preloading on hover/auth.**
Lazy chunks are only fetched when the user clicks. There's no `<link rel="prefetch">` and no programmatic preload (e.g., on hover of a sidebar link, on successful login, or for the user's role-default dashboard). So every first-visit to a route incurs a chunk-download stall on top of the data stall.

### Anti-patterns
- App shell rebuilt per route.
- `Suspense` placed too high (covers the shell instead of just the page outlet).
- Auth `loading` state used as an unconditional full-screen blocker even when the user already has a cached `user` available from a prior login.

### Impact
This is what makes the navigation *visibly* janky. The shell flash is the single biggest UX irritant and the cheapest to fix.

---

## 🔍 Suspect Area 3 — Unnecessary Re-renders (React perf)

### Findings

**3.1 `AuthContext.value` is rebuilt on every render and is NOT memoized.**
**Verified line-level** — `contexts/AuthContext.js:454` reads literally `const value = {` (a plain object literal, no `useMemo` wrapper), and the provider returns it directly at line 485: `return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>`. (`useMemo` is imported and *is* used elsewhere in the file — for `api` at line 79 — but not here.) The literal contains:
- `apiServices: createApiService(api)` at line 482 → **new object tree every render** (`services/apiClient.js:1` builds a fresh nested object).
- `login` (l. 257), `register` (l. 305), `updateToken` (l. 352), `updatePreferences` (l. 411), `updateUser` (l. 422), `refreshUser` (l. 427), `enterSchoolContext` (l. 367), `exitSchoolContext` (l. 384), `getEffectiveRole` (l. 392), `getEffectiveTenantId` (l. 400) — all defined as plain functions inside the component body (no `useCallback`). New refs every render. `logout` (l. 321) *is* `useCallback`'d.
- `isAuthenticated`, `isPlatformAdmin`, `isSchoolPrincipal`, `isTeacher`, `isStudent`, `isParent` — recomputed inline each render (lines 466-471).

Consequences:
- Every consumer of `useAuth()` re-renders whenever `AuthProvider` re-renders, even if only `loading` flipped.
- Any `useEffect(..., [apiServices])` or `[login]` etc. fires every render → potential infinite-fetch hazards. (We didn't find a runaway loop today, but it's a loaded gun.)
- `<WebSocketProvider>` consumes `useAuth` and itself re-renders, triggering its `useEffect([token, connect, disconnect])`. `connect` is a `useCallback([token, handleNotification])` and `handleNotification` is a `useCallback([playNotificationSound, showBrowserNotification])` — those are stable, so the WS doesn't churn, **but** the chain is fragile.

**3.2 `ThemeContext` is correctly memoized — keep as reference.**
`contexts/ThemeContext.js:108` uses `useMemo` for `value`. Good. (One nit: `setForceUpdate` in `toggleLanguage` at line 102 re-renders the entire provider just to refresh translation strings — `useTranslation` already depends on `language`, so this `setForceUpdate` is redundant and causes an extra app-wide render on every language toggle.)

**3.3 Heavy lists/tables without memoization.**
`rg -c "React\.memo|memo\(|useMemo|useCallback"` on the four largest dashboards:
- `AdminDashboard.jsx`: **2** memo hooks (the file is 700+ lines with charts)
- `ParentDashboard.jsx`: 2
- `TeacherDashboard.jsx`: 2
- `SchoolDashboard.jsx`: 0

Tables/lists in `UsersClassesManagement.jsx` (2,082 lines), `PlatformSettingsPage.jsx` (2,134 lines), `SchedulePageNew.jsx` (1,609 lines), `AssessmentPage.jsx` (1,300 lines) render large arrays without `React.memo`'d row components and without virtualization. Filter/search inputs in those pages will re-render the full list every keystroke.

**3.4 `AuthContext` re-render fan-out.**
Sidebar, Header, NotificationBell, RouteGuards, ProtectedRoute, every page → all subscribe to `useAuth`. Because the context value identity changes on every Auth render, this is an app-wide re-render storm any time `loading`/`token`/`user`/`schoolContext` changes (login, role switch, school-context enter/exit).

### Impact
Mostly invisible *until* the user opens a long table or switches roles, but contributes to general "feels heavy" perception and to the input-lag class of complaints.

---

## 🔍 Suspect Area 4 — Bundle Size & Code Splitting

### Findings (the good news first)

**4.1 Route-level code splitting IS in place.**
`routes/appRoutes.js:14-111` lazy-loads ~70 routes via `React.lazy(() => import(...))`. The two eager pages (`LandingPage`, `LoginPage`) are correct first-paint choices.

**4.2 Heavy libs are isolated per chunk by webpack dedupe**, per the comments at `appRoutes.js:9-12`. That's mostly true *if* a heavy library is only imported by one route. Check:

- **`recharts`** is imported by **both** `pages/AdminDashboard.jsx:22` AND `pages/SystemMonitoringPage.jsx`, plus `components/parent/AnalyticsCharts.jsx`, `components/parent/WeeklyStory.jsx`, `components/student-profile/StudentTabsContent.jsx`, `components/student-performance/RootCauseChart.jsx`, `components/student-performance/StudentRiskMap.jsx`, `pages/TeacherModule/TeacherCommunicationPage.jsx`. Webpack will hoist recharts into a shared chunk, but anyone visiting *any* of those routes pays the recharts download (~150 KB gz).
- **`jspdf` + `jspdf-autotable` + `html2canvas`** — listed in deps (`frontend/package.json`). Comment says `SecurityCenterPage` dynamic-imports them at click time. Worth verifying these are *only* dynamic-imported everywhere — a single static import will pull them into the route chunk.
- **`framer-motion`** — heavy (~120 KB gz). Need to check static usage spread.
- **`lucide-react`** — looks like named imports (e.g. `Sidebar.jsx:17-53` imports ~30 icons). With CRA + react-scripts 5 this *should* tree-shake to ESM, but every page importing 20–40 icons individually is still a meaningful chunk surface. The Sidebar imports 36 icons.

**4.3 Initial bundle includes large always-present providers.**
`App.js` eagerly pulls `AuthProvider`, `WebSocketProvider`, `ThemeProvider`, `NassaqAlertProvider`, `ErrorBoundary`, `GenericNameGuard`, `BetaBanner`, `Toaster` (sonner), plus `LandingPage` and `LoginPage`. WebSocket logic + sonner + the `Toaster` are not tiny.

**4.4 No bundle analyzer / no `webpack-bundle-analyzer` plugin** in `craco.config.js`. We can't quantify chunk sizes precisely without one.

**4.5 React 19 + react-router-dom 7 are loaded as ESM, but no service-worker / no precaching.** First load over a slow connection = full bundle each time.

### Impact
Less severe than (1) and (2). The biggest concrete wins here are: (a) make sure `recharts/jspdf/html2canvas/framer-motion` are *only* dynamically imported from leaf components, (b) add bundle analyzer to ground-truth this, (c) preload the user's likely next chunk.

---

## 🧨 Other things found while looking

- `index.js:74` installs a `MutationObserver` on `document.documentElement` with `subtree:true` *in dev only* to suppress the ResizeObserver overlay. Harmless in prod but adds DOM churn cost in dev — can mislead profiling.
- `index.js:18-31` wraps every `ResizeObserver` callback in `requestAnimationFrame`. This is a global change — fine, but worth being aware of when measuring.
- `AuthContext.js:79-186` `useEffect([api])` registers/ejects axios interceptors. Because `api` is `useMemo([])`, this runs once. OK. But if you ever add a dep to that `useMemo`, every change re-installs interceptors and you'll get duplicates until an old ejector runs — fragile.
- `AuthContext.js:135-155` on 401 it does `window.location.href = '/login'` instead of `navigate('/login')`. Full-page reload throws away every cache and chunk. Annoying after a token expiry.
- `AuthContext.js:166-176` 5xx errors trigger a global `toast.error`. With the burst-fetch pattern, a brief backend hiccup will show 5+ stacked toasts.
- `WebSocketContext.jsx:69` constructs the `Audio()` for the notification ping at provider mount time, downloading from `assets.mixkit.co` on every cold start (small, but it's a third-party request the user didn't ask for and it blocks nothing useful).
- `ThemeContext.js:88-94` issues a `fetch` to `/api/auth/preferences?...` from inside `setTheme`'s updater — calling a side effect inside a setState updater is a React footgun (will run twice in StrictMode dev). Functionally fine in prod, but worth flagging.

---

## ✅ Prioritized Action Plan (highest impact / lowest effort first)

> **Wait for approval before executing any of these.** Each step is sized so it can be shipped independently and rolled back independently.

> **Sizing caveat.** Effort estimates assume the dominant page family (the 57 Sidebar-using pages). The Student/Parent portals already use `PortalLayout` and may need a slightly different (but smaller) treatment — adds ~½ day.

### Phase 1 — Stop the shell flash (1 day, huge UX win)

**P1.1** Introduce a **layout route** in `routes/appRoutes.js`:
```
<Route element={<AppShell />}>
  <Route path="/admin" element={<AdminDashboard />} />
  ...
</Route>
```
`AppShell` renders Sidebar + Header + `<Outlet />` and never unmounts on navigation.

**P1.2** Move the `<Suspense fallback={…}>` from wrapping `<Routes>` to wrapping only the `<Outlet />` *inside* `AppShell`. The shell stays painted while only the inner outlet shows the spinner. Better still, swap the spinner for a **skeleton** sized to the destination page (or just the previous page's content kept visible — react-router 7 supports `useNavigation()` for "pending" navigation styling).

**P1.3** Strip `<Sidebar>` out of all 58 pages — they should just render their own page content. (Mechanical refactor; safe to do per-page.)

**P1.4** In `RouteGuards.js`, only show `<LoadingSpinner>` when `loading && !user`. If we already have a `user` in memory, render `children` immediately and let `/auth/me` revalidate in the background.

Expected effect: navigation feels **instant**. Sidebar/Header never flash. Spinner only inside the content area.

---

### Phase 2 — Add a real data cache (1–2 days, biggest perf win)

**P2.1** Install `@tanstack/react-query` (or SWR — equivalent for our needs). Wrap the tree with `<QueryClientProvider>` configured with:
- `staleTime: 30s` default (tunable per query)
- `gcTime: 5 min`
- `refetchOnWindowFocus: false` for dashboards
- `retry: 1`

**P2.2** Convert the highest-traffic fetches first:
1. `NotificationBell` → `useQuery(['notifications','unreadCount'])` with `refetchInterval: 30_000`. Mount/unmount stops triggering new requests.
2. `Sidebar` → `useQuery(['user-roles'])`. Stops re-firing on every navigation.
3. `AdminDashboard`, `SchoolDashboard`, `ParentDashboard`, `TeacherDashboard` `Promise.all`s → split each endpoint into its own `useQuery` so they share cache with their detail pages and stream in independently.
4. `UsersClassesManagement`, `SchedulePageNew`, `AssessmentPage`, `AIInsightsPage` next.

**P2.3** Use `placeholderData: keepPreviousData` so list pages don't blank out while filters change.

**P2.4** Delete the in-component `loading` booleans / try-catch boilerplate as queries replace them.

Expected effect: the second visit to any page is **free** (data served from cache). Filter/sort no longer triggers a full reload.

---

### Phase 3 — Tame the AuthContext re-render fan-out (half day)

**P3.1** Memoize the `value` object in `AuthProvider` (`contexts/AuthContext.js:454`) with `useMemo`, dependent on the actual primitive state (`user`, `token`, `loading`, `schoolContext`, `isImpersonating`).

**P3.2** Wrap `login`, `register`, `updateToken`, `updatePreferences`, `updateUser`, `refreshUser`, `enterSchoolContext`, `exitSchoolContext`, `getEffectiveRole`, `getEffectiveTenantId` in `useCallback`.

**P3.3** Lift `apiServices = createApiService(api)` to `useMemo([api])`.

**P3.4** Split the context: a small `AuthStateContext` (user/token/loading) and a stable `AuthActionsContext` (functions + `api` + `apiServices`). Components that only call actions stop re-rendering on user/token changes.

**P3.5** Replace `window.location.href = '/login'` (`AuthContext.js:140,153`) with `navigate('/login', { replace: true })` so we don't blow away the SPA on token expiry.

**P3.6** Drop `setForceUpdate` in `ThemeContext.toggleLanguage` (`contexts/ThemeContext.js:102`) — it's a no-op given `useTranslation` already reacts to `language`.

---

### Phase 4 — Trim re-renders in heavy lists (1–2 days, medium impact)

**P4.1** Identify the worst offenders by length: `UsersClassesManagement.jsx` (2,082), `PlatformSettingsPage.jsx` (2,134), `SchedulePageNew.jsx` (1,609), `AssessmentPage.jsx` (1,300), `IntegrationsPage.jsx` (1,456), `SecurityCenterPage.jsx` (1,456). For each:
- Extract the row component into its own file, wrap in `React.memo`.
- Memoize derived data with `useMemo`.
- Wrap event handlers passed to rows in `useCallback`.

**P4.2** For tables >500 rows, evaluate `@tanstack/react-virtual` (no extra dep beyond what react-query already pulls).

**P4.3** Debounce search inputs with a 200 ms `useDeferredValue` or simple debounce.

---

### Phase 5 — Bundle work (1 day)

**P5.1** Add `webpack-bundle-analyzer` (CRACO plugin) to ground-truth chunk sizes. Ship the report.

**P5.2** Verify `jspdf`, `jspdf-autotable`, `html2canvas`, `framer-motion` have **no** static imports; convert any to dynamic.

**P5.3** Move `recharts` users to a single `<LazyChart>` wrapper that `React.lazy`-imports the actual chart component, so dashboards don't ship recharts unless the chart card is actually scrolled to / a toggle is on.

**P5.4** Programmatic preload after login: `import('../pages/AdminDashboard')` etc., based on `user.role`. Eliminates the first-navigation chunk stall.

**P5.5** Optionally: switch the icon imports from `lucide-react` to `lucide-react/dist/esm/icons/<name>` deep-imports (or replace with an `<Icon name="..."/>` lazy registry) to make icon usage truly tree-shaken in the dev server.

---

### Phase 6 — Polish & guardrails (half day)

**P6.1** Suppress the toast spam in the response interceptor (`AuthContext.js:174`) by deduping with `toast.error(msg, { id: 'server-conn-error' })` (already partially done) **and** rate-limiting to 1 per 10 s.

**P6.2** Replace the 20 s × 2 retry on `/auth/me` (`AuthContext.js:214`) with a single 10 s timeout — 40 s of "blank" is unacceptable; fail fast and let the user retry.

**P6.3** Remove the `Audio()` preload in `WebSocketContext` (`contexts/WebSocketContext.jsx:69`) until the first notification arrives; lazy-load it.

**P6.4** Add a tiny perf-budget CI check: `react-scripts build` size threshold per chunk so this doesn't regress.

---

## What I would do FIRST if I had only one day

1. **P1.1 + P1.2 + P1.4** — kill the shell flash. (2–4 hours, instantly visible.)
2. **P2.1 + P2.2 (NotificationBell + Sidebar + AdminDashboard only)** — install React Query and convert the three components users see most. (3–4 hours.)
3. **P3.1 + P3.5** — memoize `AuthContext.value` and stop the full-page reload on 401. (1 hour.)

That alone should remove the white-screen flashes, make repeat-navigation feel instant, and stop the toast pile-up. Everything else is incremental.

---

## Files I read (for the record)

- `frontend/src/App.js`, `frontend/src/index.js`
- `frontend/src/routes/appRoutes.js`
- `frontend/src/contexts/AuthContext.js`, `ThemeContext.js`, `WebSocketContext.jsx`
- `frontend/src/services/apiClient.js`
- `frontend/src/components/guards/RouteGuards.js`
- `frontend/src/components/layout/{Header,Sidebar,Navbar,Footer,PageHeader}.jsx`
- `frontend/src/components/notifications/NotificationBell.jsx`
- `frontend/src/pages/AdminDashboard.jsx` (top), `ParentDashboard.jsx` (top)
- `frontend/craco.config.js`, `frontend/package.json`
- Counts/searches across all of `frontend/src/**`

No code in the project was modified.
