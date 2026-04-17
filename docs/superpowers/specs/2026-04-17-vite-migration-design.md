# NASSAQ frontend: CRA → Vite migration

**Date:** 2026-04-17
**Status:** Design (awaiting user review)
**Owner:** Frontend toolchain
**Related:** Health-checkup finding F-05; unblocks F-03 (core-js dedupe), F-04 (date-fns-jalali eval), F-06 (strip console.log)

## 1. Background

The NASSAQ frontend is a React 19 SPA built with `react-scripts@5.0.1` + `@craco/craco@7.1.0`. Create React App was officially deprecated by the React team in February 2025 and no longer receives updates. The Phase-3 health checkup flagged the migration as the gating change for three remaining bundle-hygiene findings (F-03, F-04, F-06) and identified slow dev-server cold start and slow rebuilds as the primary developer-experience pain.

A migration audit found the codebase is a low-risk target:

| Signal | Value |
|---|---|
| TypeScript | None (uses `jsconfig.json`) |
| Jest / RTL tests | 0 |
| `import { ReactComponent as X } from '*.svg'` | 0 sites |
| `require()` calls in `src/` | 1 |
| `process.env.REACT_APP_*` reads | 17 |
| Custom webpack plugins | 1 (`plugins/health-check/`) |
| Custom dev proxy | `src/setupProxy.js`, 31 lines |
| `craco.config.js` | 122 lines |

## 2. Goals & non-goals

### Goals
- Replace `react-scripts` + `@craco/craco` with Vite as the canonical build for both `dev` and `build`.
- Preserve the `/__health` build-status endpoint contract used by the existing health-check webpack plugin.
- Keep the deployed FastAPI `StaticFiles` mount working unchanged (same `frontend/build/` output directory, same hashed-asset URL shape).
- Land the migration with **zero observable change** for end users on cutover day.
- Unblock follow-up findings F-03, F-04, F-06.

### Non-goals
- No TypeScript adoption.
- No test-framework introduction (no tests exist today; not in scope here).
- No new bundle-splitting strategy beyond what `appRoutes.js` already does — that work shipped earlier.
- No CI changes outside the frontend `package.json` scripts.

## 3. Definition of done

1. `vite` (dev) and `vite build` (production) produce a working app at parity with the current build.
2. The Replit `Frontend Dev` workflow runs Vite. CRA scripts remain in `package.json` as `start:cra` / `build:cra` for fallback during the soak period.
3. The custom health-check plugin works under Vite at `/__health` with the same JSON response shape.
4. The smoke checklist in §8 passes against a `vite preview` build.
5. The Vite dev workflow runs cleanly for ≥ 7 calendar days with no reported regression.
6. After the soak, a single cutover commit removes the CRA fallback and renames `REACT_APP_*` env vars to `VITE_*`.

## 4. Rollout strategy: side-by-side

The CRA build is preserved as a fallback during the soak so any single regression is recoverable in one commit revert.

```
frontend/
├── package.json              # both toolchains coexist during soak
│   ├── scripts.dev      = "vite"
│   ├── scripts.build    = "vite build"
│   ├── scripts.preview  = "vite preview"
│   ├── scripts.start:cra= "craco start"          ← fallback
│   └── scripts.build:cra= "craco build"          ← fallback
├── vite.config.js            # NEW
├── index.html                # NEW (moved from public/index.html)
├── plugins/
│   ├── health-check/         # CRA webpack plugin (kept untouched during soak)
│   └── vite-health-check/    # NEW
├── public/                   # static assets only (no index.html)
├── craco.config.js           # untouched during soak; deleted at cutover
└── src/
    ├── index.jsx             # renamed from index.js
    ├── env.js                # NEW — env shim, see §6
    └── setupProxy.js         # CRA-only; deleted at cutover
```

The two toolchains never run at once — they share `src/` but read different config files.

## 5. Vite configuration

`vite.config.js`:

- **Plugins**
  - `@vitejs/plugin-react` — React 19 fast refresh + automatic JSX runtime
  - Custom `vite-health-check` plugin (§7)
  - JSConfig path-alias resolution for the existing `jsconfig.json` aliases
- **Server**
  - `server.port = 5000`
  - `server.host = '0.0.0.0'`
  - `server.allowedHosts = true` (Replit preview proxy compatibility)
  - `server.hmr.clientPort = 443` (HMR over the Replit HTTPS proxy)
  - `server.proxy` — 1:1 port of `src/setupProxy.js` covering `/api`, `/system`, `/ws`, `/docs`, `/redoc`, `/openapi.json` → `http://localhost:8000`
- **Build**
  - `build.outDir = 'build'` (matches CRA so FastAPI `StaticFiles` mount path is unchanged)
  - `build.sourcemap = false` in production, `true` in dev
  - `build.target = 'es2020'` (drops legacy polyfills; modern browsers only — same audience CRA was already targeting in practice)
- **Env**
  - `envPrefix: ['VITE_', 'REACT_APP_']` during the soak so the existing `.env` keeps working unchanged
- **Production behavior**
  - `esbuild.drop = ['console', 'debugger']` in production builds (delivers F-06)
- **Dependency pre-bundling**
  - `optimizeDeps.include = ['react', 'react-dom', 'recharts', 'date-fns-jalali']`
- **Process shim**
  - `define: { 'process.env.NODE_ENV': JSON.stringify(mode) }` — narrow shim for libraries that still read it directly

## 6. Env-var rename strategy

The 17 `process.env.REACT_APP_*` sites are migrated in two steps to keep the soak period zero-risk:

**Step 1 (in the migration commit, soak-safe):**
- Add `frontend/src/env.js`:
  ```js
  // Compatibility shim — works in both Vite (import.meta.env) and CRA (process.env)
  export const env = (typeof import.meta !== 'undefined' && import.meta.env)
    ? import.meta.env
    : process.env;
  ```
- Mechanical replace across `src/`: `process.env.REACT_APP_X` → `env.REACT_APP_X` with the import added.
- `vite.config.js` keeps `envPrefix: ['VITE_', 'REACT_APP_']` so the existing `.env` continues to be read.

**Step 2 (in the cutover commit, after soak):**
- Rename `REACT_APP_*` → `VITE_*` across `src/` and `.env`.
- Drop `REACT_APP_` from `envPrefix` in `vite.config.js`.

This means the migration commit changes **zero behaviour** in env handling. The rename is a separate, mechanical follow-up.

## 7. Health-check Vite plugin

Port `frontend/plugins/health-check/index.js` to `frontend/plugins/vite-health-check/index.js`:

- Hooks Vite's `configureServer` to register a middleware on `GET /__health`.
- Maintains the same in-memory state shape: `{ status, lastBuildAt, errors[], warnings[] }`.
- Updates state from Vite hooks: `buildStart` → status='building', `buildEnd` → status='ok' or 'error', `handleHotUpdate` → bumps `lastBuildAt`.
- Gated on the same `ENABLE_HEALTH_CHECK=true` env flag the webpack plugin uses today, so default behaviour is unchanged.
- Returns the **identical JSON shape** as the CRA plugin, verified by a side-by-side `curl` diff against both servers as part of the smoke checklist.

## 8. Smoke checklist (cutover gate)

Run against a `vite preview` build of the Vite output. **All items must pass before the production deploy is flipped.**

- [ ] `vite build` exits 0 with no errors and no new warnings vs CRA baseline
- [ ] Bundle measurement: main entry chunk ≤ 1.3 MB; total bytes ≤ 6.5 MB (current CRA baseline from earlier in the health checkup)
- [ ] App mounts at `/`, language toggle works, RTL renders correctly
- [ ] Login as **principal**, **teacher**, **parent**, **student** — each lands on their portal
- [ ] One read API call per portal returns 200 (e.g. `/api/users/me`, `/api/teachers/me`, `/api/students/me`, `/api/parents/me`)
- [ ] One write API call (e.g. update profile) returns 200
- [ ] Browser console clean (no errors, no `process is not defined`, no MIME-type warnings)
- [ ] Network tab: lazy chunks load on route navigation, not on first paint
- [ ] `curl /__health` returns the same JSON shape under Vite as under CRA
- [ ] FastAPI `StaticFiles` serves the Vite `build/` output unchanged (visit one hashed `/static/...` asset)

## 9. Cutover & cleanup commit

Single commit, executed after the smoke checklist passes **and** the soak period (≥ 7 days) completes with no regression:

- Delete `craco.config.js`
- Delete `frontend/plugins/health-check/`
- Delete `frontend/src/setupProxy.js`
- Remove `react-scripts` and `@craco/craco` from `package.json`
- Delete the `start:cra` and `build:cra` scripts
- Rename all `REACT_APP_*` env-var reads to `VITE_*` and update `.env`
- Remove `'REACT_APP_'` from `envPrefix` in `vite.config.js`
- Run smoke checklist one more time post-cleanup

## 10. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Library that depends on CommonJS `require()` breaks under Vite | Low (1 site found) | Convert that one site to ESM during migration |
| `process.env` read at runtime by a transitive dep | Medium | `define: { 'process.env.NODE_ENV': ... }` shim + `optimizeDeps.include`; soak catches the rest |
| Replit preview proxy rejects Vite HMR websocket | Low | `server.hmr.clientPort = 443` + `server.allowedHosts = true` |
| Static-asset URL format changes | Low | `build.outDir = 'build'` and `base = '/'` keeps FastAPI mount unchanged |
| Bundle regression vs current CRA output | Low | Smoke checklist measures bundle bytes |
| `setupProxy.js` and `vite.config.js` drift during soak | Medium | Soak-period checklist item: diff the two proxy lists weekly |
| Cutover commit reintroduces a regression that the soak missed | Low | Re-run smoke checklist post-cutover; CRA fallback still recoverable via revert |

## 11. Effort estimate

| Phase | Active work |
|---|---|
| Vite config + entry move + dev workflow swap | ~3 h |
| Health-check Vite plugin port | ~2 h |
| Env-var shim + verify 17 call sites | ~1 h |
| Smoke checklist run + fixes | ~2 h |
| Cutover/cleanup commit | ~30 min |
| **Total active work** | **~1 day** |
| Soak period (calendar time) | ~7 days |
