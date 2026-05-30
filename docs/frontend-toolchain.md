# Frontend toolchain decision: stay on CRA, stabilize the pinning

**Date:** 2026-05-30
**Status:** Decided — stabilize the current Create React App (CRA) setup. Do **not** migrate to Vite at this time.

## Context

The frontend builds with `react-scripts` 5.0.1 (Create React App), which is no
longer maintained. The project force-upgrades `webpack-dev-server` to **v5** via
a security resolution. CRA 5.0.1 was written for webpack-dev-server **v4** and
emits v4-only options (`onBeforeSetupMiddleware`, `onAfterSetupMiddleware`,
top-level `https`). webpack-dev-server v5 removed those keys and hard-fails
schema validation when they are present.

That mismatch already broke the dev preview once and was patched with a
compatibility shim in `frontend/craco.config.js`. The risk going forward is a
*silent* re-break: any future `webpack-dev-server` bump can change the schema
again, and nothing today would catch it until the dev server failed to boot.

## Options considered

### Option A — Migrate to Vite

- **Pros:** Maintained toolchain, faster dev server/HMR, no v4↔v5 shim.
- **Cons / risk surface (why we did not pick this now):**
  - `craco test` (CRA's Jest) backs 7 existing test files plus the
    `test:button-contrast` script — a migration means moving to Vitest.
  - `src/setupProxy.js` uses CRA's dev-server proxy convention.
  - `@emergentbase/visual-edits` is a proprietary webpack/CRA plugin shipped as a
    tarball dependency; Vite compatibility is unknown.
  - Custom webpack health-check plugins under `frontend/plugins/health-check/`.
  - The dev-server CSP/security headers and the Replit-proxy HMR workaround live
    in the craco dev-server hook.
  - `build.sh` (the deploy pipeline) and `.replit` workflows call `craco`.
  - Env convention `REACT_APP_BACKEND_URL` would move to `import.meta.env`.
  - This touches many working flows at once and conflicts with the project rule
    "do not break existing working flows." It is a larger, riskier change that
    should be a deliberate, separately scheduled migration — not folded into a
    stabilization task.

### Option B — Stabilize the current CRA + webpack-dev-server v5 pinning (chosen)

The shim already works; the only real fragility is *silent* breakage on
dependency drift. We address that directly and cheaply:

1. **Pin `webpack-dev-server` to an exact version** (`5.2.4`, no caret) in both
   `resolutions` and `overrides` in `frontend/package.json`. Previously `^5.2.4`
   allowed any 5.x to be pulled on a fresh install, which could change the schema
   the shim targets without warning. The bump is now an explicit, reviewable
   edit.
2. **Cover the shim with a regression test**
   (`frontend/src/__tests__/cracoDevServer.test.js`). It feeds the shim a
   realistic CRA v4 dev-server config and asserts the legacy keys are stripped /
   translated, then validates the transformed config against
   webpack-dev-server's own `options.json` schema via `schema-utils` (the same
   validator wds uses internally). Because that schema has
   `additionalProperties: false`, any stale key the shim fails to strip — or any
   future schema change — fails the test instead of crashing the dev server.
3. **Document** the contract (this file + the comments in `craco.config.js`).

## Consequences

- Dev preview and production build both start cleanly (verified 2026-05-30).
- A future webpack-dev-server upgrade is now a deliberate step: bump the exact
  pin, run `npx craco test --testPathPattern=cracoDevServer`, and adjust the shim
  if the schema test fails. No more silent breakage.
- Migrating off CRA remains a reasonable future project; this decision just
  scopes it out of the stabilization work so it can be planned and tested on its
  own.

## How to upgrade webpack-dev-server safely

1. Change the exact version in `resolutions` **and** `overrides` in
   `frontend/package.json`.
2. `cd frontend && npm install --legacy-peer-deps`.
3. `npx craco test --watchAll=false --testPathPattern=cracoDevServer`.
   - If the schema-validation test fails, the new wds version changed its
     options schema. Update the shim in `frontend/craco.config.js` to translate
     whatever CRA still emits into the new API, then re-run.
4. Restart the `Frontend Dev` workflow and confirm the preview loads.
