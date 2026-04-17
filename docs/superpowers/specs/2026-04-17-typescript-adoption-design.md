# NASSAQ frontend: full TypeScript adoption sprint

**Date:** 2026-04-17
**Status:** Design (awaiting user review)
**Owner:** Frontend toolchain
**Depends on:** `2026-04-17-vite-migration-design.md` (this sprint runs **after** the Vite cutover)

## 1. Background

The NASSAQ frontend is a React 19 SPA with 264 source files (236 `.jsx`, 28 `.js`), zero PropTypes, zero JSDoc types, and zero existing tests. The backend (FastAPI) defines 177 Pydantic response models across 65 route files in 667 lines of `shared_models.py` — a rich, typeable surface ready for OpenAPI codegen.

The Phase-1 / Phase-4 health checkup uncovered several bug classes that a typed contract eliminates at compile time:
- `preferred_language` returned `null` when the response model said `str`
- `/api/users` 500 because the response model didn't allow `Optional`
- Cross-tenant identifier confusion in fallback lookups

Adopting TypeScript gives us automatic alignment with the backend's OpenAPI surface, catches whole bug classes at the IDE, and unlocks safer refactors going forward.

## 2. Goals & non-goals

### Goals
- Convert all 264 `.js`/`.jsx` files to `.ts`/`.tsx` in a single planned sprint.
- Establish a layered architecture enforced by tooling, not convention.
- Land an OpenAPI-driven type pipeline so backend changes propagate to the frontend by running one command.
- Add a small Playwright E2E suite that locks in the behaviour we're refactoring around.
- Leave the codebase under `tsc --noEmit` + `eslint --max-warnings 0` as a CI gate.

### Non-goals
- No backend changes beyond making `/openapi.json` reachable for codegen (currently 404).
- No new feature work in the same sprint.
- No mass redesign of pages — conversion preserves behaviour.
- No state-management library swap.

## 3. Definition of done

1. Every file in `src/` is `.ts` or `.tsx`. No `.js`/`.jsx` remain (verified by CI).
2. `tsc --noEmit` exits 0 with `strict: true`. (`noImplicitAny` and `strictNullChecks` ratchet in P5; both end the sprint as `true`.)
3. `pnpm types:gen` produces `src/types/api.ts` from `/openapi.json`, runs as a `prebuild` hook, and the generated file is committed.
4. The hybrid type architecture (§5) is in place: generated wire types + hand-written `*.view.ts` view models + pure mapping functions.
5. Layer-import lint rules pass (no presentation→infrastructure imports, no cycles, no domain imports of UI).
6. `eslint --max-warnings 0` passes with the rules in §E enabled.
7. Smoke checklist (login per role + sample CRUD per portal) passes manually on a Vite preview build.
8. Playwright E2E suite (10 paths, §9) runs green.
9. The strictness ratchet PR (P5) lands with `noImplicitAny: true`, `strictNullChecks: true`, `noUncheckedIndexedAccess: true`, `useUnknownInCatchVariables: true`.

## 4. Pre-sprint blocker

`/openapi.json` returns 404 in this environment — recent security work likely gated FastAPI's docs surface.

**Day-1 task:** confirm whether the spec is reachable behind auth, then either:
- Re-enable it for dev/staging behind a known auth header, or
- Have the codegen script consume a checked-in snapshot exported from a one-shot script (`backend/scripts/export-openapi.py`).

The hybrid types plan cannot start until codegen has an input.

## 5. Architecture

### 5.1 Layered architecture (dependency direction always inward)

```
Presentation   (pages/, components/)
        │  depends on ↓
Application    (hooks/, contexts/)
        │  depends on ↓
Domain         (types/, types/views/, transforms)
        │  depends on ↓
Infrastructure (services/apiClient.ts, services/http.ts)
```

Enforced by `eslint-plugin-import` rules:
- `pages/` and `components/` may not import from `services/` directly. They go through hooks.
- `types/` may not import from `services/`, `hooks/`, `pages/`, `components/`. Domain has zero outward dependencies.
- `services/` may not import from `pages/` or `components/`.
- `no-cycle` enforced repo-wide.

### 5.2 Hybrid type pipeline

```
src/
├── types/
│   ├── api.ts              ← AUTO-GENERATED from /openapi.json (do not edit)
│   ├── api.gen.json        ← committed snapshot of the spec used for codegen
│   ├── views/              ← hand-written view models
│   │   ├── user.view.ts          (e.g. flattened User+Profile)
│   │   ├── attendance.view.ts    (e.g. with computed totals)
│   │   └── ...
│   ├── shims/              ← ambient .d.ts for libs with missing/wrong types
│   └── shared.ts           ← role enums, branded IDs, Result<T,E>
├── services/
│   ├── http.ts             ← low-level transport (axios/fetch wrapper)
│   ├── apiClient.ts        ← typed wrapper, returns wire types from api.ts
│   └── ...
├── hooks/
│   ├── useUser.ts          ← calls apiClient, applies toUserView, exposes UserView
│   └── ...
└── components/, pages/     ← consume View types only; never import api.ts
```

**Rules**
- Wire types come from `api.ts`. Never edited by hand.
- UI consumes **view types**, never wire types.
- Mapping functions live next to the view type and are **pure** (no React, no I/O).
- Backend response shape changes break only the mapping function, in one place.

### 5.3 Codegen workflow

```jsonc
// package.json scripts
{
  "types:gen":   "openapi-typescript src/types/api.gen.json -o src/types/api.ts",
  "types:fetch": "curl -s http://localhost:8000/openapi.json -o src/types/api.gen.json",
  "types:check": "tsc --noEmit",
  "lint":        "eslint src --max-warnings 0",
  "prebuild":    "npm run types:gen && npm run types:check && npm run lint"
}
```

`api.gen.json` is committed so the build is reproducible without a live backend. `types:fetch` is run manually when intentionally pulling a backend update.

## 6. Sprint structure (5 phases, ~11 working days)

| Phase | What lands | Effort |
|---|---|---|
| **P1 — Foundations** | `tsconfig.json`, `pnpm types:gen` + committed `api.gen.json`, typed `apiClient.ts`, layer-import lint rules, Prettier + husky + lint-staged, `tsc --noEmit` + `eslint --max-warnings 0` CI gate | ~2 days |
| **P2 — Cross-cutting layer** | `auth context`, role types, route defs, all `hooks/use*`, `services/`, `contexts/`, `lib/`, `utils/` converted. Branded ID types, `ApiError` boundary, discriminated-union API states. New code defaults to `.tsx`. | ~2 days |
| **P3 — Pages & components by portal** | Convert in this order: shared `components/` → principal portal → teacher portal → parent portal → student portal. Commit per portal so any regression is bisectable. | ~3.5 days |
| **P4 — Safety net** | Playwright E2E suite (10 paths, §9). Hits the typed `apiClient` mockable seam — no network monkey-patching. | ~2 days |
| **P5 — Strictness ratchet** | Flip `noImplicitAny: true`, fix fallout. Then `strictNullChecks: true`, fix fallout. Then `noUncheckedIndexedAccess: true` + `useUnknownInCatchVariables: true`. Each lands as a separate commit. | ~1.5 days |
| **Total active work** | | **~11 working days** |

P3 and P4 can overlap (E2E author works in parallel with portal conversion).

## 7. tsconfig.json (initial)

```jsonc
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noImplicitAny": false,            // ratcheted in P5
    "strictNullChecks": false,         // ratcheted in P5
    "noUncheckedIndexedAccess": false, // ratcheted in P5
    "useUnknownInCatchVariables": false, // ratcheted in P5
    "esModuleInterop": true,
    "isolatedModules": true,
    "skipLibCheck": true,
    "noEmit": true,
    "allowJs": false,                  // hard cutover — no mixed mode
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] }
  },
  "include": ["src"]
}
```

`allowJs: false` is deliberate — mixed-mode tolerance hides conversions we forgot.

## 8. Clean-code conventions (enforced where possible)

### 8.1 File & module conventions

| Rule | Enforcement |
|---|---|
| One React component per file. Filename matches component name. | Lint + reviewer checklist |
| **Named exports only** for components and hooks (no `export default`). | `import/no-default-export` |
| Hooks live in `hooks/`, prefixed `use`, one hook per file. | Reviewer checklist |
| View types live next to their mapping function. Pure, no React imports. | Reviewer checklist |
| **No barrel `index.ts` re-exports** in `components/` or `pages/`. Allowed only for `types/` and `lib/`. | Lint rule |
| Soft cap **300 lines per file**, **150 lines per component**. Above the cap requires a justifying comment. | Lint warning |
| **No magic strings** for routes, roles, permissions, query keys. Use constants modules. | Reviewer checklist |
| `services/apiClient.ts` is the **only** module that calls `fetch`/`axios`. | `no-restricted-imports` outside `services/` |

### 8.2 Type-safety conventions beyond `tsc`

- **No `any`** in new code. `unknown` + narrowing instead. ESLint `@typescript-eslint/no-explicit-any: error`.
- **`catch` clauses** type errors as `unknown` (P5). Errors narrowed before use.
- **Discriminated unions** for API states: `{ status: 'idle' } | { status: 'loading' } | { status: 'ok'; data: T } | { status: 'error'; error: ApiError }`. No nullable `data + error` pairs.
- **Branded types** for identifiers: `type UserId = string & { readonly __brand: 'UserId' }`, `SchoolId`, `TeacherId`, `StudentId`. Prevents the multi-tenant cross-id bugs the audit flagged.
- **Readonly by default** for props and state shapes.

### 8.3 Boundary discipline

- **Wire types never leak into components.** A component needing a `User` imports `UserView`, not `components['schemas']['User']`.
- **Mapping functions are pure.** Easy to unit-test later.
- **Errors are typed at the boundary**: `apiClient` throws a tagged `ApiError` with status, code, and the typed response body. Hooks catch and translate to UI-friendly state. UI never sees raw HTTP errors.

### 8.4 Linting & formatting (the automated half of clean code)

Sprint includes wiring:
- `typescript-eslint/recommended` + `typescript-eslint/recommended-requiring-type-checking`
- `eslint-plugin-react` + `eslint-plugin-react-hooks` (`rules-of-hooks`, `exhaustive-deps` as **errors**)
- `eslint-plugin-import` with `no-cycle`, `no-default-export` (where applicable), `order`, `no-restricted-imports`
- Prettier with project config; `lint-staged` + `husky` so commits auto-format
- `tsc --noEmit` + `eslint --max-warnings 0` as CI gate, blocking merge

## 9. Playwright E2E safety net

| # | Path | Asserts |
|---|---|---|
| 1 | Login as principal | Principal dashboard renders, school name visible |
| 2 | Login as teacher | Teacher dashboard renders, today's classes visible |
| 3 | Login as parent | Parent dashboard renders, child name visible |
| 4 | Login as student | Student dashboard renders, today's schedule visible |
| 5 | Principal → Users list | Table loads with > 0 rows |
| 6 | Principal → Create user | Form submits, redirect to user detail |
| 7 | Teacher → Mark attendance | Save returns success toast, persists on reload |
| 8 | Teacher → Edit a grade | Save returns success toast |
| 9 | Parent → View child grades | Page loads, > 0 grade rows |
| 10 | Logout from any portal | Redirects to login |

Suite lives in `frontend/e2e/`, runs against a Vite preview build with the backend dev server live, and is part of the sprint deliverable.

## 10. Smoke checklist (manual, run before P5 starts)

- [ ] Login per role (principal, teacher, parent, student) reaches the right portal
- [ ] One read endpoint per portal returns 200
- [ ] One write endpoint per portal returns 200 and persists on reload
- [ ] RTL renders correctly; language toggle works
- [ ] Browser console clean (no errors, no `any`-cast warnings, no missing-prop warnings)
- [ ] Network tab: lazy chunks still load on route navigation, not on first paint
- [ ] `tsc --noEmit` exits 0
- [ ] `eslint --max-warnings 0` passes

## 11. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Behavioural regression from a wrong rename or import shuffle | High (264 files, no tests today) | Playwright suite + per-portal commit boundaries + manual checklist |
| Library missing or wrong `@types` | Medium (esp. `date-fns-jalali`, niche RTL libs) | Allow ambient `.d.ts` shims under `src/types/shims/`; track count |
| OpenAPI spec incomplete (route without declared `response_model`) | Medium | P1 audit step: list endpoints with no `response_model`; either add them as a backend pre-task or accept `unknown` for those wire shapes |
| Strictness ratchet reveals more null-handling bugs than estimated | Medium | P5 timeboxed to 1.5 days; overflow lands as a follow-up PR rather than blocking the sprint |
| Sprint stalls mid-portal | Low | Per-portal commit means partial state still ships; the dev workflow runs fine on a partially-typed tree because everything compiles |
| Replit dev environment lacks Playwright browser deps | Medium | P4 first task: confirm `npx playwright install --with-deps` works; fallback is to run E2E from a separate worker |
| Lint rules block legitimate work mid-sprint | Low | All new lint rules land in P1 with an explicit allow-list for any pre-existing violation; allow-list is burned down through P3 |

## 12. What gets deleted at the end

- `jsconfig.json` (replaced by `tsconfig.json`)
- All `.js`/`.jsx` files in `src/` (verified by a CI check)
- Sprint-time `// @ts-expect-error` markers (tracked, fixed in P5)
- Any pre-existing barrel `index.ts` files in `components/` or `pages/` flagged by the new lint rule
- Any direct `axios`/`fetch` calls outside `services/`

## 13. Effort estimate

| Phase | Active work |
|---|---|
| P1 Foundations | ~2 days |
| P2 Cross-cutting layer | ~2 days |
| P3 Pages & components | ~3.5 days |
| P4 Playwright safety net | ~2 days |
| P5 Strictness ratchet | ~1.5 days |
| **Total** | **~11 working days** |
