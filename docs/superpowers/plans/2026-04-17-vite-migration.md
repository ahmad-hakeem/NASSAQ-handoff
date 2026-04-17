# NASSAQ Frontend Vite Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `react-scripts@5` + `@craco/craco` with Vite as the canonical dev and build toolchain for the NASSAQ frontend, side-by-side with the existing CRA scripts during a 7-day soak before cutover.

**Architecture:** Side-by-side rollout — Vite becomes the default `dev`/`build`; CRA remains as `start:cra` / `build:cra` until soak passes. The custom webpack health-check plugin is ported to a small Vite plugin preserving the `/__health` JSON contract. Env vars use a compat shim so the same `.env` works under both toolchains during soak.

**Tech Stack:** Vite 5.x, `@vitejs/plugin-react`, custom Vite middleware plugin for `/__health`, npm.

**Reference spec:** `docs/superpowers/specs/2026-04-17-vite-migration-design.md`.

**Known constraints surfaced from the codebase audit:**
- `craco.config.js` integrates `@emergentbase/visual-edits/craco` (Replit visual editing). No Vite equivalent ships with the package. **Decision (Task 1):** disable visual edits under the Vite build during the soak. CRA fallback retains them. If the team relies on visual edits day-to-day, the cutover stays gated on a Vite-compatible solution.
- `src/setupProxy.js` proxies only `/api` (with `ws: true`) and `/system` to `http://localhost:8000`. The Vite proxy must match exactly.
- `public/index.html` uses CRA's `%PUBLIC_URL%` placeholder. Vite uses absolute `/` paths from `public/`.
- `.env` includes `WDS_SOCKET_PORT=443` (CRA HMR over Replit HTTPS proxy). Vite equivalent: `server.hmr.clientPort = 443`.

---

## Phase 1 — Pre-flight decisions and harness (~1 hour)

### Task 1: Confirm visual-edits decision and snapshot current behaviour

**Files:** read-only

- [ ] **Step 1: Confirm with the user that visual edits is acceptable to disable under Vite during soak**

Decision was captured in the spec brainstorming session, but re-confirm before touching code. If the answer flips, this plan stops and the spec is revised.

- [ ] **Step 2: Capture CRA build baseline for the smoke checklist**

```bash
cd frontend && npm run build
echo "=== Bundle size baseline ==="
du -sh build
ls -la build/static/js/*.js | sort -k5 -n -r | head -5
```
Save the numbers in `/tmp/cra-baseline.txt`. The Vite smoke checklist will compare against these.

- [ ] **Step 3: Capture CRA dev-server URL behaviour**

```bash
curl -s -I http://localhost:5000/ | head -10
curl -s http://localhost:5000/api/health 2>&1 | head -5
```
Note: status codes, security headers, proxy behaviour. The Vite setup must reproduce these.

- [ ] **Step 4: Commit baseline doc**

Create `docs/superpowers/plans/2026-04-17-vite-migration-baseline.md` with the captured numbers and curl output.

```bash
git add docs/superpowers/plans/2026-04-17-vite-migration-baseline.md
git commit -m "docs(frontend): record CRA baseline before Vite migration"
```

---

## Phase 2 — Vite install and minimal config (~3 hours)

### Task 2: Install Vite and React plugin

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Install dev deps**

```bash
cd frontend && npm install --save-dev \
  vite@^5.4 \
  @vitejs/plugin-react@^4.3
```
Expected: no peer warnings against React 19 (the plugin supports React 19).

- [ ] **Step 2: Verify installation**

```bash
cd frontend && npx vite --version
```
Expected: `vite/5.x` printed.

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "build(frontend): add Vite and @vitejs/plugin-react"
```

---

### Task 3: Move and rewrite `index.html`

**Files:**
- Create: `frontend/index.html` (root, copied from `public/index.html` with adjustments)
- Keep untouched during soak: `frontend/public/index.html` (CRA still uses it)

- [ ] **Step 1: Copy `public/index.html` → `index.html`**

```bash
cd frontend && cp public/index.html index.html
```

- [ ] **Step 2: Edit `frontend/index.html`**

Apply three changes:

1. Replace every `%PUBLIC_URL%` with `/`. CRA's placeholder doesn't exist in Vite; static assets in `public/` are served at the root in both toolchains.
2. Add a `<script type="module" src="/src/index.jsx"></script>` just before `</body>`. (Vite needs an explicit entry-point script in the HTML.) The file is renamed to `.jsx` in Task 4.
3. Leave the rest (head meta, OG/Twitter cards, structured data, skip-link styles) unchanged.

Example diff for the bottom of `<body>`:

```html
    <noscript>You need to enable JavaScript to run this app.</noscript>
    <div id="root"></div>
    <script type="module" src="/src/index.jsx"></script>
  </body>
</html>
```

- [ ] **Step 3: Verify `%PUBLIC_URL%` is fully gone**

```bash
cd frontend && grep -c "%PUBLIC_URL%" index.html
```
Expected: `0`.

- [ ] **Step 4: Do not delete `public/index.html` yet**

CRA fallback still references it during the soak. Deletion happens in Task 13.

- [ ] **Step 5: Commit**

```bash
git add frontend/index.html
git commit -m "build(frontend): add Vite-compatible index.html at project root"
```

---

### Task 4: Rename `src/index.js` → `src/index.jsx`

**Files:**
- Modify: `frontend/src/index.js` → `frontend/src/index.jsx`

- [ ] **Step 1: Rename**

```bash
cd frontend && git mv src/index.js src/index.jsx
```

> CRA accepts JSX in `.js` files because of its babel preset; Vite's `@vitejs/plugin-react` requires JSX-bearing files to use `.jsx`/`.tsx`. CRA still resolves `.jsx` (it falls back to webpack's resolve extensions), so the file works for both toolchains.

- [ ] **Step 2: Verify CRA still loads it**

Restart the `Frontend Dev` workflow (still on CRA at this point):
```bash
# In Replit, restart the Frontend Dev workflow
```
Expected: app mounts, no console errors.

- [ ] **Step 3: Commit**

```bash
git commit -m "refactor(frontend): rename index.js to index.jsx for Vite compatibility"
```

---

### Task 5: Write `vite.config.js` (minimal, no health-check plugin yet)

**Files:**
- Create: `frontend/vite.config.js`

- [ ] **Step 1: Create the config**

```js
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), ['VITE_', 'REACT_APP_']);
  const isProd = mode === 'production';

  return {
    plugins: [react()],

    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src'),
      },
    },

    envPrefix: ['VITE_', 'REACT_APP_'],

    server: {
      host: '0.0.0.0',
      port: 5000,
      strictPort: true,
      allowedHosts: true,
      hmr: { clientPort: 443 },
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          ws: true,
          timeout: 30_000,
          proxyTimeout: 30_000,
        },
        '/system': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
      headers: {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=()',
        'Content-Security-Policy':
          "default-src 'self'; " +
          "script-src 'self' 'unsafe-inline' 'unsafe-eval'; " +
          "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; " +
          "font-src 'self' https://fonts.gstatic.com data:; " +
          "img-src 'self' data: blob: https:; " +
          "media-src 'self' https:; " +
          "connect-src 'self' wss: ws: http://localhost:8000; " +
          "frame-ancestors 'none';",
        'Cache-Control': 'public, max-age=0, must-revalidate',
      },
    },

    build: {
      outDir: 'build',
      sourcemap: false,
      target: 'es2020',
      emptyOutDir: true,
    },

    define: {
      'process.env.NODE_ENV': JSON.stringify(mode),
    },

    optimizeDeps: {
      include: ['react', 'react-dom', 'recharts', 'date-fns-jalali'],
    },

    esbuild: isProd ? { drop: ['console', 'debugger'] } : {},
  };
});
```

> Notes:
> - `envPrefix` includes `REACT_APP_` for soak compatibility. Cutover (Task 13) drops it.
> - Headers mirror the CRA dev-server headers from `craco.config.js`. The deprecated `X-XSS-Protection` from CRA is intentionally **not** carried over (matches health-checkup B-20).
> - `optimizeDeps.include` pre-bundles the heavy libs to keep first dev-server load fast.
> - `esbuild.drop` delivers F-06 (strip `console.log` in prod) for free.

- [ ] **Step 2: Smoke-test the Vite dev server (without touching CRA)**

```bash
cd frontend && npx vite --port 5001
```
In a second terminal:
```bash
curl -s -I http://localhost:5001/ | head -5
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5001/api/users/me  # expect proxy → 401
```
Expected: HTML root returns 200 with the security headers; the API proxy reaches the backend.

Stop the Vite dev server.

- [ ] **Step 3: Commit**

```bash
git add frontend/vite.config.js
git commit -m "build(frontend): add minimal vite.config.js with proxy and security headers"
```

---

## Phase 3 — Env-var compat shim (~1 hour)

### Task 6: Add `src/env.js` and migrate the 6 call sites

**Files:**
- Create: `frontend/src/env.js`
- Modify: `frontend/src/contexts/WebSocketContext.jsx`
- Modify: `frontend/src/contexts/AuthContext.js`
- Modify: `frontend/src/pages/UserDetailsPage.jsx`
- Modify: `frontend/src/pages/IntegrationsPage.jsx`
- Modify: `frontend/src/pages/ForgotPasswordPage.jsx`
- Modify: `frontend/src/pages/ResetPasswordPage.jsx`

- [ ] **Step 1: Create the shim**

```js
// frontend/src/env.js
// Compatibility shim — works under both Vite (import.meta.env) and CRA (process.env).
// During the soak both toolchains share the same .env file with REACT_APP_* prefixes.
// Cutover task drops the REACT_APP_ prefix and this shim collapses to import.meta.env.

const viteEnv =
  typeof import.meta !== 'undefined' && import.meta.env ? import.meta.env : null;

export const env = viteEnv ?? (typeof process !== 'undefined' ? process.env : {});
```

- [ ] **Step 2: Update each of the 6 call sites**

For each file in the list above, replace:
```js
const API_URL = process.env.REACT_APP_BACKEND_URL;        // or || ''
```
with:
```js
import { env } from '@/env';
const API_URL = env.REACT_APP_BACKEND_URL;                // or || ''
```

Preserve any `|| ''` defaults at the original site.

- [ ] **Step 3: Verify no `process.env.REACT_APP_` reads remain in `src/`**

```bash
cd frontend && grep -rn "process\.env\.REACT_APP_" src/
```
Expected: empty output.

- [ ] **Step 4: Verify CRA still works**

Restart the `Frontend Dev` workflow (CRA). Open the app, log in, hit a page that uses `API_URL`. Expected: behaves identically.

- [ ] **Step 5: Verify Vite reads the same env**

```bash
cd frontend && npx vite --port 5001
# In another terminal:
curl -s http://localhost:5001/ | grep -c '<div id="root">'  # expect 1
```
Visit `http://localhost:5001/` in the preview, log in, confirm `API_URL` resolves correctly via the network tab.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/env.js frontend/src/contexts frontend/src/pages
git commit -m "refactor(frontend): route REACT_APP_BACKEND_URL through env shim"
```

---

## Phase 4 — Port the health-check plugin (~2 hours)

### Task 7: Read the existing CRA plugin to lock down the contract

**Files:** read-only — `frontend/plugins/health-check/webpack-health-plugin.js`, `frontend/plugins/health-check/health-endpoints.js`

- [ ] **Step 1: Read both files**

```bash
cat frontend/plugins/health-check/webpack-health-plugin.js
cat frontend/plugins/health-check/health-endpoints.js
```

- [ ] **Step 2: Note the exact JSON contract for every endpoint**

In a scratch file (`/tmp/health-contract.md`), record:
- Every URL the existing plugin registers (e.g. `/__health`, `/__health/build`, etc.).
- The exact JSON shape returned by each one.
- The build-event hooks the plugin listens to (`compile`, `done`, `failed`, etc.) and what state they mutate.
- The env-flag gate (`ENABLE_HEALTH_CHECK=true`).

This contract is the **only** acceptance criterion for the Vite port. The Vite plugin must reproduce the JSON byte-for-byte (within reason — timestamps will differ).

- [ ] **Step 3: Run a curl reference**

With `ENABLE_HEALTH_CHECK=true npm start` in another terminal:
```bash
curl -s http://localhost:5000/__health | tee /tmp/cra-health-output.json
# Repeat for every endpoint discovered in Step 2.
```
Save the outputs; the Vite plugin's outputs must diff to identical structure.

---

### Task 8: Write the Vite health-check plugin

**Files:**
- Create: `frontend/plugins/vite-health-check/index.js`
- Modify: `frontend/vite.config.js`

- [ ] **Step 1: Create the plugin module**

```js
// frontend/plugins/vite-health-check/index.js
//
// Vite equivalent of plugins/health-check/. Registers the same /__health endpoint(s)
// and reproduces the JSON shape the CRA webpack plugin returned.
// Gated on ENABLE_HEALTH_CHECK=true (matches the CRA flag).

const ENABLED = process.env.ENABLE_HEALTH_CHECK === 'true';

function createState() {
  return {
    status: 'idle',           // idle | building | ok | error
    lastBuildAt: null,        // ISO timestamp
    lastBuildDurationMs: null,
    errors: [],
    warnings: [],
  };
}

function jsonResponse(res, body, status = 200) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json');
  res.end(JSON.stringify(body));
}

export default function viteHealthCheck() {
  if (!ENABLED) {
    return { name: 'vite-health-check-disabled' };
  }

  const state = createState();
  let buildStartedAt = null;

  return {
    name: 'vite-health-check',
    apply: 'serve',  // dev only

    buildStart() {
      state.status = 'building';
      state.errors = [];
      state.warnings = [];
      buildStartedAt = Date.now();
    },

    buildEnd(err) {
      state.lastBuildAt = new Date().toISOString();
      state.lastBuildDurationMs = buildStartedAt ? Date.now() - buildStartedAt : null;
      if (err) {
        state.status = 'error';
        state.errors.push(String(err.message ?? err));
      } else {
        state.status = 'ok';
      }
    },

    handleHotUpdate() {
      state.lastBuildAt = new Date().toISOString();
    },

    configureServer(server) {
      server.middlewares.use('/__health', (req, res, next) => {
        if (req.method !== 'GET') return next();
        // Match the CRA plugin's response shape exactly. If the contract
        // captured in Task 7 differs from this, adjust here.
        jsonResponse(res, {
          status: state.status,
          lastBuildAt: state.lastBuildAt,
          lastBuildDurationMs: state.lastBuildDurationMs,
          errors: state.errors,
          warnings: state.warnings,
        });
      });
    },
  };
}
```

> If Task 7 turned up additional sub-routes (e.g. `/__health/build`, `/__health/errors`) or fields, extend the plugin accordingly. The contract from Task 7 wins over the shape sketched here.

- [ ] **Step 2: Wire the plugin into `vite.config.js`**

Edit `frontend/vite.config.js` to import and use the plugin:

```js
import viteHealthCheck from './plugins/vite-health-check/index.js';
// ...
return {
  plugins: [react(), viteHealthCheck()],
  // ...
};
```

- [ ] **Step 3: Smoke-test the plugin**

```bash
cd frontend && ENABLE_HEALTH_CHECK=true npx vite --port 5001
# In another terminal:
curl -s http://localhost:5001/__health | tee /tmp/vite-health-output.json
diff <(jq -S 'del(.lastBuildAt,.lastBuildDurationMs)' /tmp/cra-health-output.json) \
     <(jq -S 'del(.lastBuildAt,.lastBuildDurationMs)' /tmp/vite-health-output.json)
```
Expected: empty diff (after stripping timestamps). If the diff is non-empty, fix the plugin until it's empty — that's the contract.

- [ ] **Step 4: Smoke-test with the flag off**

```bash
cd frontend && ENABLE_HEALTH_CHECK=false npx vite --port 5001
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5001/__health
```
Expected: `404` (matches the CRA behaviour when the flag is off).

- [ ] **Step 5: Commit**

```bash
git add frontend/plugins/vite-health-check frontend/vite.config.js
git commit -m "build(frontend): port health-check webpack plugin to Vite"
```

---

## Phase 5 — Side-by-side scripts and workflow swap (~1 hour)

### Task 9: Update `package.json` scripts so Vite is the default and CRA is the fallback

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Edit `scripts`**

In `frontend/package.json`:

```jsonc
{
  "scripts": {
    "start":      "vite",
    "build":      "vite build",
    "preview":    "vite preview --port 5000 --strictPort",
    "start:cra":  "craco start",
    "build:cra":  "craco build",
    "test:cra":   "craco test"
  }
}
```

> `npm test` is removed from default — there are zero tests in the project today (verified by audit). Existing CI / scripts that called `npm test` should be updated; failing fast on a missing script is preferable to silent regressions.

- [ ] **Step 2: Verify both toolchains still build**

```bash
cd frontend && npm run build:cra
ls -la build && du -sh build > /tmp/cra-build-size.txt
cd frontend && npm run build
ls -la build && du -sh build > /tmp/vite-build-size.txt
```
Expected: both succeed and write to `frontend/build/`. The two builds clobber each other in `build/`; that's fine because only one ships at a time.

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json
git commit -m "build(frontend): switch default scripts to Vite, keep CRA as fallback"
```

---

### Task 10: Switch the `Frontend Dev` workflow to Vite

**Files:**
- Modify: Replit workflow `Frontend Dev`

- [ ] **Step 1: Update the workflow command**

Change `Frontend Dev` from:
```
cd frontend && PORT=5000 BROWSER=none npx craco start
```
to:
```
cd frontend && npm run start
```

The `vite.config.js` already pins port 5000, host 0.0.0.0, allowed hosts, and HMR client port.

- [ ] **Step 2: Restart the workflow**

```bash
# Restart Frontend Dev via the workflow tool
```
Expected: Vite logs `VITE v5.x  ready in ~Xms` and `Local: http://localhost:5000/`.

- [ ] **Step 3: Open the preview pane**

Verify the app mounts. Log in. Navigate to a page that exercises the API proxy (e.g. principal dashboard). Verify the network tab shows `/api/...` calls succeeding through the proxy.

- [ ] **Step 4: Verify HMR over the Replit HTTPS proxy**

Edit `src/App.js`/`App.jsx` (a trivial change), save, and verify the change appears in the preview without a full reload.

- [ ] **Step 5: If anything fails, roll back the workflow command to CRA**

`cd frontend && PORT=5000 BROWSER=none npx craco start` — the side-by-side setup means rollback is instant. Then debug the Vite path with the dev server stopped on the workflow side.

- [ ] **Step 6: Commit (workflow change is environment, not file — note in the report)**

Workflow definitions live in `.replit` or environment config. If the change is reflected in a tracked file, commit it; otherwise document the change in `docs/superpowers/plans/2026-04-17-vite-migration-baseline.md` so the cutover task knows to verify the workflow state.

---

## Phase 6 — Smoke checklist (the cutover gate, ~2 hours)

### Task 11: Run the spec §8 smoke checklist against a Vite preview build

**Files:** none — this is verification only.

- [ ] **Step 1: Build with Vite and start a preview**

```bash
cd frontend && npm run build
cd frontend && npm run preview &
sleep 3
```

- [ ] **Step 2: Walk the checklist**

Tick each item. **Every box must be checked before the cutover proceeds.**

- [ ] `vite build` exits 0 with no warnings.
- [ ] Bundle size: main entry chunk ≤ 1.3 MB; total `build/` ≤ 6.5 MB. Compare against `/tmp/cra-baseline.txt` from Task 1.
  ```bash
  du -sh build
  ls -la build/assets/*.js | sort -k5 -n -r | head -5
  ```
- [ ] App mounts at `/`, language toggle works, RTL renders correctly.
- [ ] Login as **principal**, **teacher**, **parent**, **student** — each lands on the right portal.
- [ ] One read API call per portal returns 200 (e.g. `/api/users/me`, `/api/teachers/me`, `/api/students/me`, `/api/parents/me`).
- [ ] One write API call per portal returns 200 and persists on reload.
- [ ] Browser console clean: no errors, no `process is not defined`, no MIME-type warnings.
- [ ] Network tab: lazy chunks load on route navigation, not on first paint.
- [ ] `curl http://localhost:5000/__health` returns the same JSON shape as the CRA version (Task 8 Step 3).
- [ ] FastAPI `StaticFiles` serves the Vite `build/` output unchanged. Verify by visiting one hashed `/static/...` asset (or whatever the deployed mount path is) against a build dropped into the deploy environment.

- [ ] **Step 3: Capture the checklist results**

Append the ticked checklist to `docs/superpowers/plans/2026-04-17-vite-migration-baseline.md`. If any item fails, fix it on Vite (do **not** weaken the checklist) and re-run.

- [ ] **Step 4: Commit checklist record**

```bash
git add docs/superpowers/plans/2026-04-17-vite-migration-baseline.md
git commit -m "docs(frontend): record Vite smoke checklist pass"
```

---

## Phase 7 — Soak (calendar time, ~7 days)

### Task 12: Run on Vite for 7 days; collect regressions

**Files:** none active; tracking only.

- [ ] **Step 1: Open a tracking note**

Create `docs/superpowers/plans/2026-04-17-vite-soak-log.md`. Each day, append:
- Anything broken or noticeably different from CRA.
- Build-time / dev-server-start time samples (rough is fine).
- Console errors not seen on CRA.

- [ ] **Step 2: Mid-soak proxy-drift check**

Once during the soak, diff `src/setupProxy.js` against `vite.config.js`'s `server.proxy` block:
```bash
cd frontend && cat src/setupProxy.js
cd frontend && grep -A 20 "proxy:" vite.config.js
```
If they've drifted, sync them. (CRA fallback may still be exercised, so they must match.)

- [ ] **Step 3: At day 7, decide**

- All clear → proceed to Task 13 (cutover).
- Regressions found and unfixed → fix, then restart soak day count.
- Regressions are blocking and unfixable → roll back the workflow to CRA (`craco start`), document, and pause the migration.

- [ ] **Step 4: Commit the soak log**

```bash
git add docs/superpowers/plans/2026-04-17-vite-soak-log.md
git commit -m "docs(frontend): record 7-day Vite soak results"
```

---

## Phase 8 — Cutover (~30 min)

### Task 13: Single cutover commit

**Files:**
- Delete: `frontend/craco.config.js`
- Delete: `frontend/plugins/health-check/`
- Delete: `frontend/src/setupProxy.js`
- Delete: `frontend/public/index.html`
- Modify: `frontend/package.json`
- Modify: `frontend/vite.config.js`
- Modify: `frontend/.env`
- Modify: every file imports from `@/env` that uses `REACT_APP_BACKEND_URL`

- [ ] **Step 1: Re-run the smoke checklist** (Task 11). The cutover commit lands only after a clean run.

- [ ] **Step 2: Delete the CRA artefacts**

```bash
cd frontend
rm craco.config.js
rm -rf plugins/health-check
rm src/setupProxy.js
rm public/index.html
```

- [ ] **Step 3: Remove CRA deps and scripts from `package.json`**

Edit `frontend/package.json`:
- Remove from `dependencies` / `devDependencies`: `react-scripts`, `@craco/craco`.
- Remove from `scripts`: `start:cra`, `build:cra`, `test:cra`.

```bash
cd frontend && npm uninstall react-scripts @craco/craco
```

- [ ] **Step 4: Rename env vars `REACT_APP_*` → `VITE_*`**

```bash
cd frontend && grep -rln "REACT_APP_BACKEND_URL" src/ .env
```
For each file in the output, replace `REACT_APP_BACKEND_URL` with `VITE_BACKEND_URL`. Keep the same value in `.env`.

- [ ] **Step 5: Drop the `REACT_APP_` prefix from `vite.config.js`**

In `frontend/vite.config.js` change:
```js
envPrefix: ['VITE_', 'REACT_APP_'],
```
to:
```js
envPrefix: 'VITE_',
```

- [ ] **Step 6: Remove `process.env` fallback from `src/env.js`**

The shim collapses to:
```js
// frontend/src/env.js
export const env = import.meta.env;
```

- [ ] **Step 7: Verify**

```bash
cd frontend && npm run build && npm run preview &
sleep 3
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5000/    # expect 200
```
Walk the smoke checklist one more time. Every box still ticks.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "build(frontend): complete Vite cutover, remove CRA fallback"
```

- [ ] **Step 9: Post-cutover note**

Append to `docs/superpowers/plans/2026-04-17-vite-soak-log.md`: cutover date, final bundle sizes, anything unexpected. If `@emergentbase/visual-edits` is still needed by the team, open a separate ticket to find or build a Vite plugin equivalent — that work is **not** in this plan.

---

## Self-Review

**Spec coverage:**
- §3 Definition of done (1) Vite dev/build → Tasks 5, 9, 10. (2) Both scripts coexist → Task 9. (3) Health-check at `/__health` → Tasks 7, 8. (4) Smoke checklist passes → Task 11. (5) 7-day soak → Task 12. (6) Cutover commit → Task 13. ✓
- §4 Side-by-side rollout → Tasks 9, 10. ✓
- §5 Vite config (plugins, server, build, env, dependency pre-bundling, process shim) → Task 5. ✓
- §6 Env-var two-step strategy → Task 6 (shim) + Task 13 Steps 4–6 (rename + drop prefix). ✓
- §7 Health-check Vite plugin → Tasks 7, 8. ✓
- §8 Smoke checklist → Task 11. ✓
- §9 Cutover & cleanup → Task 13. ✓
- §10 Risk register → mitigations land in Tasks 6 (env shim), 5 (HMR/proxy/headers), 1 (visual-edits decision), 12 (soak proxy-drift check), 11/13 (re-run smoke at cutover). ✓

**Placeholder scan:** No "TBD/TODO/implement later". Code blocks present for every code-changing step. Health-check plugin contract is explicitly anchored to a captured Task 7 baseline (not invented). The visual-edits constraint is named, not waved away.

**Type/symbol consistency:**
- Plugin folder/name `frontend/plugins/vite-health-check/index.js` is consistent across Tasks 8, 13.
- `env` shim path `@/env` is consistent across Tasks 6, 13.
- Env-var rename target `VITE_BACKEND_URL` is consistent in Task 13 (single rename, no aliases).
- Workflow command `cd frontend && npm run start` is consistent with the `package.json` script in Task 9.

**One known imperfection accepted:** the workflow file change in Task 10 may not be a tracked file. The plan handles both cases (commit if tracked; document if not).

Plan ready for execution.
