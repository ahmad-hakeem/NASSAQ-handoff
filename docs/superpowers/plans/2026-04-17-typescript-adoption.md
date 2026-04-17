# NASSAQ Frontend TypeScript Adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert all 264 frontend `.js`/`.jsx` files to `.ts`/`.tsx` in a planned sprint, gated by `tsc --noEmit`, lint rules enforcing layered architecture, a manual smoke checklist, and a 10-path Playwright E2E suite.

**Architecture:** Layered (Presentation → Application → Domain → Infrastructure) with the dependency direction enforced by `eslint-plugin-import`. Wire types are auto-generated from FastAPI's OpenAPI spec; UI components consume hand-written view models populated by pure mapping functions. Errors are tagged at the boundary; identifiers are branded.

**Tech Stack:** TypeScript 5.x, `openapi-typescript`, `typescript-eslint`, `eslint-plugin-react`, `eslint-plugin-react-hooks`, `eslint-plugin-import`, Prettier + husky + lint-staged, Playwright, Vite (already migrated per `2026-04-17-vite-migration-design.md`).

**Hard prerequisite:** The Vite migration spec (`2026-04-17-vite-migration-design.md`) must be implemented and cut over before this plan starts. Tasks below assume `vite.config.js` and a Vite-driven `frontend/` package.

---

## Phase 1 — Foundations (~2 days)

### Task 1: Make `/openapi.json` reachable for codegen

**Files:**
- Read: `backend/server.py`, `backend/app/middleware.py`
- Create: `backend/scripts/export_openapi.py`

- [ ] **Step 1: Verify current state of `/openapi.json`**

Run:
```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/openapi.json
```
Expected: `404` (current state) or `200`. If `200`, skip to Step 5.

- [ ] **Step 2: Decide between re-enable vs snapshot**

Inspect `backend/server.py` for `FastAPI(openapi_url=None)` or middleware that blocks `/openapi.json`. If re-enabling for dev is acceptable per the security posture from the recent health checkup, edit to allow it behind `ENVIRONMENT=development`. Otherwise proceed with the snapshot approach (Step 3).

- [ ] **Step 3: Create snapshot exporter**

Create `backend/scripts/export_openapi.py`:

```python
"""Export the FastAPI OpenAPI spec to a JSON file for frontend codegen.

Run from the backend dir:
    python scripts/export_openapi.py ../frontend/src/types/api.gen.json
"""
import json
import sys
from pathlib import Path

# Import the app without starting the server
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server import app  # noqa: E402

def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: export_openapi.py <output.json>", file=sys.stderr)
        sys.exit(2)
    out = Path(sys.argv[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False))
    print(f"Wrote {out}")

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the exporter and verify output**

```bash
cd backend && python scripts/export_openapi.py ../frontend/src/types/api.gen.json
```
Expected: file exists, contains `"openapi": "3."`, lists ≥ 50 paths.

- [ ] **Step 5: Audit endpoints missing `response_model`**

```bash
cd backend && grep -rEn "@(app|router)\.(get|post|put|patch|delete)\(" routes/ | wc -l
cd backend && grep -rEn "response_model=" routes/ | wc -l
```
Note the difference. List every route without `response_model` in `docs/superpowers/specs/2026-04-17-typescript-adoption-design.md` (append a "Backend prep" appendix section). These will surface in `api.ts` as `unknown` and need fixing during P3 portal conversion or as backend pre-work.

- [ ] **Step 6: Commit**

```bash
git add backend/scripts/export_openapi.py docs/superpowers/specs/2026-04-17-typescript-adoption-design.md
git commit -m "chore(backend): add OpenAPI snapshot exporter for frontend codegen"
```

---

### Task 2: Install TS toolchain and write `tsconfig.json`

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json` (for `vite.config`)

- [ ] **Step 1: Install dependencies**

```bash
cd frontend && npm install --save-dev \
  typescript@^5.4 \
  @types/react@^19 @types/react-dom@^19 @types/node \
  openapi-typescript@^7
```
Expected: `package-lock.json` updates, no peer warnings other than the React 19 set already present.

- [ ] **Step 2: Create `tsconfig.json`**

Create `frontend/tsconfig.json` exactly as defined in spec §7:

```jsonc
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noImplicitAny": false,
    "strictNullChecks": false,
    "noUncheckedIndexedAccess": false,
    "useUnknownInCatchVariables": false,
    "esModuleInterop": true,
    "isolatedModules": true,
    "skipLibCheck": true,
    "noEmit": true,
    "allowJs": false,
    "resolveJsonModule": true,
    "forceConsistentCasingInFileNames": true,
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] }
  },
  "include": ["src"],
  "exclude": ["node_modules", "build", "dist", "e2e"]
}
```

- [ ] **Step 3: Create `tsconfig.node.json` for Vite config**

```jsonc
{
  "compilerOptions": {
    "composite": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "skipLibCheck": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 4: Add scripts to `package.json`**

In `frontend/package.json`:

```jsonc
{
  "scripts": {
    "types:fetch": "(cd ../backend && python scripts/export_openapi.py ../frontend/src/types/api.gen.json)",
    "types:gen":   "openapi-typescript src/types/api.gen.json -o src/types/api.ts",
    "types:check": "tsc --noEmit",
    "lint":        "eslint src --max-warnings 0",
    "prebuild":    "npm run types:check && npm run lint"
  }
}
```

- [ ] **Step 5: Verify `types:check` runs (with no src yet typed it should still exit 0)**

Run:
```bash
cd frontend && npm run types:check
```
Expected: `tsc` exits 0 because `allowJs: false` excludes the existing `.js`/`.jsx`. If you get errors about no input files, that's fine — the next task adds the first `.ts` file.

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/tsconfig.json frontend/tsconfig.node.json
git commit -m "build(frontend): add TypeScript toolchain and tsconfig"
```

---

### Task 3: Generate wire types from OpenAPI spec

**Files:**
- Create: `frontend/src/types/api.gen.json` (generated)
- Create: `frontend/src/types/api.ts` (generated)

- [ ] **Step 1: Fetch the OpenAPI spec snapshot**

```bash
cd frontend && npm run types:fetch
```
Expected: `src/types/api.gen.json` exists with the full spec.

- [ ] **Step 2: Generate TS types**

```bash
cd frontend && npm run types:gen
```
Expected: `src/types/api.ts` is created and contains an `export interface paths` and `export interface components` block.

- [ ] **Step 3: Verify it compiles**

```bash
cd frontend && npm run types:check
```
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/api.gen.json frontend/src/types/api.ts
git commit -m "feat(frontend): generate wire types from OpenAPI spec"
```

---

### Task 4: Add ESLint with layered architecture rules

**Files:**
- Create: `frontend/.eslintrc.cjs`
- Create: `frontend/.eslintignore`
- Create: `frontend/.prettierrc.json`
- Modify: `frontend/package.json`

- [ ] **Step 1: Install ESLint + plugins + Prettier**

```bash
cd frontend && npm install --save-dev \
  eslint@^8 \
  @typescript-eslint/eslint-plugin@^7 @typescript-eslint/parser@^7 \
  eslint-plugin-react@^7 eslint-plugin-react-hooks@^4 \
  eslint-plugin-import@^2 eslint-import-resolver-typescript@^3 \
  prettier@^3 eslint-config-prettier@^9 eslint-plugin-prettier@^5 \
  husky@^9 lint-staged@^15
```

- [ ] **Step 2: Create `.eslintrc.cjs`**

Create `frontend/.eslintrc.cjs`:

```js
module.exports = {
  root: true,
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 2022,
    sourceType: 'module',
    ecmaFeatures: { jsx: true },
    project: './tsconfig.json',
  },
  settings: {
    react: { version: 'detect' },
    'import/resolver': {
      typescript: { project: './tsconfig.json' },
    },
  },
  plugins: ['@typescript-eslint', 'react', 'react-hooks', 'import', 'prettier'],
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react/recommended',
    'plugin:react/jsx-runtime',
    'plugin:react-hooks/recommended',
    'plugin:import/recommended',
    'plugin:import/typescript',
    'prettier',
  ],
  rules: {
    'prettier/prettier': 'error',
    '@typescript-eslint/no-explicit-any': 'error',
    '@typescript-eslint/consistent-type-imports': 'error',
    'react-hooks/rules-of-hooks': 'error',
    'react-hooks/exhaustive-deps': 'error',
    'import/no-cycle': ['error', { maxDepth: 5 }],
    'import/order': ['error', {
      groups: ['builtin', 'external', 'internal', 'parent', 'sibling', 'index'],
      'newlines-between': 'always',
      alphabetize: { order: 'asc' },
    }],
    'import/no-default-export': 'error',
    'no-restricted-imports': ['error', {
      paths: [
        { name: 'axios', message: 'Import axios only from src/services/http.ts' },
      ],
    }],
  },
  overrides: [
    // Layer rule: pages and components may not import from services/
    {
      files: ['src/pages/**/*.{ts,tsx}', 'src/components/**/*.{ts,tsx}'],
      rules: {
        'no-restricted-imports': ['error', {
          patterns: [
            { group: ['**/services/*', '@/services/*'], message: 'Use a hook; presentation may not import services directly.' },
          ],
        }],
      },
    },
    // Layer rule: types/ has no outward dependencies
    {
      files: ['src/types/**/*.ts'],
      rules: {
        'no-restricted-imports': ['error', {
          patterns: [
            { group: ['**/services/*', '**/hooks/*', '**/pages/*', '**/components/*', '**/contexts/*'], message: 'Domain (types/) has no outward dependencies.' },
          ],
        }],
      },
    },
    // Layer rule: services/ may not import presentation
    {
      files: ['src/services/**/*.ts'],
      rules: {
        'no-restricted-imports': ['error', {
          patterns: [
            { group: ['**/pages/*', '**/components/*'], message: 'Infrastructure may not import presentation.' },
          ],
        }],
      },
    },
    // Default-export allowance: route lazy-loaders need default export for React.lazy
    {
      files: ['src/routes/**/*.{ts,tsx}', 'src/pages/**/index.{ts,tsx}'],
      rules: { 'import/no-default-export': 'off' },
    },
    // Generated files — turn rules off
    {
      files: ['src/types/api.ts'],
      rules: {
        '@typescript-eslint/no-explicit-any': 'off',
        'prettier/prettier': 'off',
        'import/order': 'off',
      },
    },
  ],
};
```

- [ ] **Step 3: Create `.eslintignore`**

```
build
dist
node_modules
src/types/api.ts
*.config.js
```

- [ ] **Step 4: Create `.prettierrc.json`**

```json
{
  "semi": true,
  "singleQuote": true,
  "trailingComma": "all",
  "printWidth": 100,
  "arrowParens": "always"
}
```

- [ ] **Step 5: Wire husky + lint-staged**

```bash
cd frontend && npx husky init
echo "npx lint-staged" > .husky/pre-commit
```

In `frontend/package.json`:

```jsonc
{
  "lint-staged": {
    "src/**/*.{ts,tsx}": ["eslint --max-warnings 0 --fix", "prettier --write"]
  }
}
```

- [ ] **Step 6: Verify lint runs cleanly on the empty TS surface**

```bash
cd frontend && npm run lint
```
Expected: exits 0 (only `src/types/api.ts` exists and it's ignored).

- [ ] **Step 7: Commit**

```bash
git add frontend/.eslintrc.cjs frontend/.eslintignore frontend/.prettierrc.json frontend/.husky frontend/package.json frontend/package-lock.json
git commit -m "build(frontend): add ESLint, Prettier, husky with layer-import rules"
```

---

### Task 5: Wire CI gate (`tsc --noEmit` + lint) into the build

**Files:**
- Modify: `frontend/package.json`
- Modify: `.github/workflows/*.yml` if present, otherwise document

- [ ] **Step 1: Confirm `prebuild` runs both checks**

`prebuild` was added in Task 2. Verify:
```bash
cd frontend && npm run prebuild
```
Expected: PASS.

- [ ] **Step 2: Wire CI**

If `.github/workflows/` exists, add a `frontend-ci.yml`:

```yaml
name: frontend-ci
on:
  pull_request:
    paths: ['frontend/**']
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20', cache: 'npm', cache-dependency-path: 'frontend/package-lock.json' }
      - run: cd frontend && npm ci
      - run: cd frontend && npm run types:check
      - run: cd frontend && npm run lint
```

If no `.github/workflows/` exists in this project, document the gate in `frontend/README.md` instead and note that the team must run `npm run prebuild` before pushing.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/frontend-ci.yml || git add frontend/README.md
git commit -m "ci(frontend): gate PRs on tsc and lint"
```

---

## Phase 2 — Cross-cutting layer (~2 days)

### Task 6: Domain types — branded IDs, role enums, `Result<T,E>`

**Files:**
- Create: `frontend/src/types/shared.ts`

- [ ] **Step 1: Write the file**

```ts
// Branded types for identifiers — prevents the multi-tenant cross-id bugs
// the audit caught (e.g. passing a TeacherId where a StudentId was expected).
export type Branded<T, B extends string> = T & { readonly __brand: B };

export type UserId = Branded<string, 'UserId'>;
export type SchoolId = Branded<string, 'SchoolId'>;
export type TeacherId = Branded<string, 'TeacherId'>;
export type StudentId = Branded<string, 'StudentId'>;
export type ParentId = Branded<string, 'ParentId'>;
export type ClassId = Branded<string, 'ClassId'>;

export const asUserId = (s: string): UserId => s as UserId;
export const asSchoolId = (s: string): SchoolId => s as SchoolId;
export const asTeacherId = (s: string): TeacherId => s as TeacherId;
export const asStudentId = (s: string): StudentId => s as StudentId;
export const asParentId = (s: string): ParentId => s as ParentId;
export const asClassId = (s: string): ClassId => s as ClassId;

// Role union — single source of truth, replaces magic strings.
export const ROLES = ['principal', 'teacher', 'parent', 'student'] as const;
export type Role = (typeof ROLES)[number];
export const isRole = (s: unknown): s is Role =>
  typeof s === 'string' && (ROLES as readonly string[]).includes(s);

// Discriminated-union API state — replaces nullable-data + nullable-error pairs.
export type ApiState<T, E = ApiError> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'ok'; data: T }
  | { status: 'error'; error: E };

// Tagged error type used at the infrastructure boundary.
export interface ApiError {
  readonly kind: 'ApiError';
  readonly status: number;
  readonly code: string;
  readonly message: string;
  readonly body?: unknown;
}
export const isApiError = (e: unknown): e is ApiError =>
  typeof e === 'object' && e !== null && (e as { kind?: string }).kind === 'ApiError';
```

- [ ] **Step 2: Verify types compile and lint**

```bash
cd frontend && npm run types:check && npm run lint -- src/types/shared.ts
```
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/shared.ts
git commit -m "feat(frontend): add branded IDs, role enum, ApiState, ApiError"
```

---

### Task 7: Infrastructure — typed `http.ts` and `apiClient.ts`

**Files:**
- Read: `frontend/src/services/apiClient.js` (current implementation)
- Create: `frontend/src/services/http.ts`
- Create: `frontend/src/services/apiClient.ts`
- Delete: `frontend/src/services/apiClient.js` (after parity verified)

- [ ] **Step 1: Read the existing `apiClient.js`**

```bash
cat frontend/src/services/apiClient.js
```
Note: every function name, signature, and side-effect (token attach, refresh-on-401, error normalization). The new `apiClient.ts` must preserve every behaviour.

- [ ] **Step 2: Write `http.ts` (low-level transport)**

```ts
import axios, { AxiosError, type AxiosInstance, type AxiosRequestConfig } from 'axios';

import type { ApiError } from '@/types/shared';

const baseURL = import.meta.env.VITE_API_BASE_URL ?? '/api';

export const http: AxiosInstance = axios.create({
  baseURL,
  timeout: 30_000,
  withCredentials: true,
});

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function toApiError(err: unknown): ApiError {
  if (axios.isAxiosError(err)) {
    const e = err as AxiosError<{ detail?: string; code?: string }>;
    return {
      kind: 'ApiError',
      status: e.response?.status ?? 0,
      code: e.response?.data?.code ?? e.code ?? 'unknown',
      message: e.response?.data?.detail ?? e.message,
      body: e.response?.data,
    };
  }
  return {
    kind: 'ApiError',
    status: 0,
    code: 'unknown',
    message: err instanceof Error ? err.message : String(err),
  };
}

export async function request<T>(config: AxiosRequestConfig): Promise<T> {
  try {
    const res = await http.request<T>(config);
    return res.data;
  } catch (err) {
    throw toApiError(err);
  }
}
```

- [ ] **Step 3: Write `apiClient.ts` (typed wrapper over the OpenAPI surface)**

```ts
import type { components, paths } from '@/types/api';

import { request } from './http';

// Helpers — extract response type for a path + method
type Json<T> = T extends { 'application/json': infer J } ? J : never;
type ResponseOf<P extends keyof paths, M extends keyof paths[P]> =
  paths[P][M] extends { responses: infer R }
    ? R extends { 200: { content: infer C } } ? Json<C> : unknown
    : unknown;

// Typed call helpers — 1 per HTTP verb. Add specific endpoint wrappers below.
export const api = {
  get:  <P extends keyof paths>(url: P) =>
    request<ResponseOf<P, 'get' & keyof paths[P]>>({ url: url as string, method: 'GET' }),
  // post/put/patch/delete defined inline as endpoints are added
};

// --- Endpoint-specific wrappers (added incrementally; see Task 8 for the first one) ---

export type User = components['schemas']['User'];
export type TeacherMe = components['schemas']['TeacherMe'];
export type StudentMe = components['schemas']['StudentMe'];

export const getMe = () => api.get('/api/users/me');
export const getTeacherMe = () => api.get('/api/teachers/me');
export const getStudentMe = () => api.get('/api/students/me');
```

> If `components['schemas']['User']` (or any other) does not exist after `types:gen`, that means the backend route lacks a `response_model`. Open the audit list from Task 1 Step 5 and either fix the backend or use `unknown` and cast inside a view mapper.

- [ ] **Step 4: Verify it compiles**

```bash
cd frontend && npm run types:check
```
Expected: PASS.

- [ ] **Step 5: Run a smoke check against the backend**

Temporarily add a script that hits one endpoint and logs the typed response, then remove it. Or open the dev workflow and verify the React app still loads (the `.js` `apiClient` is still in place; `.ts` is unused yet).

- [ ] **Step 6: Do not delete `apiClient.js` yet**

Leaving it in place during P2/P3 means the migration is bite-sized — call sites switch import paths one feature at a time. The deletion happens at the end of P3 in Task 14.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/services/http.ts frontend/src/services/apiClient.ts
git commit -m "feat(frontend): add typed http and apiClient with ApiError boundary"
```

---

### Task 8: First view model — `user.view.ts` and `useUser` hook

**Files:**
- Create: `frontend/src/types/views/user.view.ts`
- Create: `frontend/src/hooks/useUser.ts`

- [ ] **Step 1: Write the view model**

```ts
import type { Role } from '@/types/shared';
import { asSchoolId, asUserId, isRole } from '@/types/shared';
import type { User as WireUser } from '@/services/apiClient';

import type { SchoolId, UserId } from '@/types/shared';

export interface UserView {
  readonly id: UserId;
  readonly schoolId: SchoolId;
  readonly fullName: string;
  readonly role: Role;
  readonly preferredLanguage: 'ar' | 'en';
}

export function toUserView(wire: WireUser): UserView {
  const role = isRole(wire.role) ? wire.role : 'student';
  return {
    id: asUserId(wire.id),
    schoolId: asSchoolId(wire.school_id),
    fullName: `${wire.first_name ?? ''} ${wire.last_name ?? ''}`.trim() || wire.username,
    role,
    preferredLanguage: wire.preferred_language === 'en' ? 'en' : 'ar',
  };
}
```

> Field names (`first_name`, `school_id`, `preferred_language`) come from the generated wire type. If `tsc` complains, open `src/types/api.ts` and adjust the mapping to the actual property names — the wire shape is the source of truth.

- [ ] **Step 2: Write the hook**

```ts
import { useEffect, useState } from 'react';

import { getMe } from '@/services/apiClient';
import type { ApiState } from '@/types/shared';

import type { UserView } from '@/types/views/user.view';
import { toUserView } from '@/types/views/user.view';

export function useUser(): ApiState<UserView> {
  const [state, setState] = useState<ApiState<UserView>>({ status: 'loading' });
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const wire = await getMe();
        if (!cancelled) setState({ status: 'ok', data: toUserView(wire) });
      } catch (error) {
        if (!cancelled) setState({ status: 'error', error: error as never });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);
  return state;
}
```

- [ ] **Step 3: Verify**

```bash
cd frontend && npm run types:check && npm run lint
```
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/views/user.view.ts frontend/src/hooks/useUser.ts
git commit -m "feat(frontend): add UserView, toUserView, useUser hook"
```

---

### Task 9: Convert `contexts/`, remaining `hooks/`, `lib/`, `utils/`, `services/`

**Files:**
- Modify: every `.js`/`.jsx` under `frontend/src/contexts/`, `frontend/src/hooks/`, `frontend/src/lib/`, `frontend/src/utils/`, `frontend/src/services/`
- Modify: `frontend/src/index.js` → `frontend/src/index.tsx`
- Modify: `frontend/src/App.js` → `frontend/src/App.tsx`

- [ ] **Step 1: List every file in scope**

```bash
cd frontend && find src/contexts src/hooks src/lib src/utils src/services -type f \( -name '*.js' -o -name '*.jsx' \) | sort
ls src/index.* src/App.*
```

- [ ] **Step 2: Convert each file**

For each file from Step 1, in order:

1. Rename the file (`.js` → `.ts`, `.jsx` → `.tsx`).
2. Add explicit types to props, function arguments, and return types where obvious. Use `unknown` over `any`.
3. Replace `import { X } from './foo.js'` (with extension) → `from './foo'`.
4. If a hook returns API state, refactor to `ApiState<T>` (Task 6).
5. If a service function calls `fetch`/`axios` directly, route it through `services/http.ts` (Task 7).
6. If a context exposes a user, expose `UserView` (Task 8), not the wire type.
7. Run `npm run types:check` after every batch of ~5 files.

- [ ] **Step 3: Verify**

```bash
cd frontend && npm run types:check && npm run lint
```
Expected: PASS, zero `any`, zero default exports outside the allow-list, no `axios`/`fetch` calls outside `services/`.

- [ ] **Step 4: Manual smoke**

Reload the app in the dev workflow. Verify:
- App mounts.
- Login still works.
- The `useUser` hook (or the existing user context) returns data.

- [ ] **Step 5: Commit per directory**

```bash
git add frontend/src/contexts && git commit -m "refactor(frontend): convert contexts/ to TypeScript"
git add frontend/src/hooks    && git commit -m "refactor(frontend): convert hooks/ to TypeScript"
git add frontend/src/lib      && git commit -m "refactor(frontend): convert lib/ to TypeScript"
git add frontend/src/utils    && git commit -m "refactor(frontend): convert utils/ to TypeScript"
git add frontend/src/services && git commit -m "refactor(frontend): convert services/ to TypeScript"
git add frontend/src/index.tsx frontend/src/App.tsx && git commit -m "refactor(frontend): convert app entry to TypeScript"
```

---

## Phase 3 — Pages & components by portal (~3.5 days)

> P3 is a mechanical sweep across 264 files. Each task below converts one bucket. Within each bucket the engineer follows the same per-file recipe (Task 9 Step 2). Tasks land as one commit per bucket so any regression is bisectable.

### Task 10: Convert shared `components/`

**Files:**
- Modify: every `.js`/`.jsx` under `frontend/src/components/` that is **not** under a portal-specific subfolder

- [ ] **Step 1: List in-scope files**

```bash
cd frontend && find src/components -maxdepth 4 -type f \( -name '*.js' -o -name '*.jsx' \) | sort > /tmp/p3-shared.txt
wc -l /tmp/p3-shared.txt
```

- [ ] **Step 2: Convert each file using the Task 9 Step 2 recipe**

Additional rules for components:
- Define `Props` in the same file, above the component.
- Use **named exports** (`export function Foo(props: Props) { ... }`); no `export default`.
- Component file ≤ 150 lines; if larger, leave a comment justifying or split it as part of the conversion.
- Replace any `<div className="...">` magic strings for routes/roles with imports from the constants module.

- [ ] **Step 3: Verify**

```bash
cd frontend && npm run types:check && npm run lint
```
Expected: PASS.

- [ ] **Step 4: Smoke**

Reload the dev workflow. Visit landing/login/header/footer pages where shared components render.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components
git commit -m "refactor(frontend): convert shared components/ to TypeScript"
```

---

### Task 11: Convert principal portal

**Files:**
- Modify: every `.js`/`.jsx` under `frontend/src/pages/principal/` (and the matching subfolder in `components/` if portals have dedicated subfolders)
- Modify: `frontend/src/routes/appRoutes.js` → `appRoutes.tsx`

- [ ] **Step 1: List in-scope files**

```bash
cd frontend && find src/pages/principal -type f \( -name '*.js' -o -name '*.jsx' \) | sort > /tmp/p3-principal.txt
wc -l /tmp/p3-principal.txt
```

- [ ] **Step 2: Convert `appRoutes.js`** if not already done in Task 9

The lazy-load wrappers convert to:

```tsx
const PrincipalDashboard = lazy(() => import('@/pages/principal/Dashboard'));
```

Note `import/no-default-export` is **off** for `src/routes/**`, so route modules may keep `export default`.

- [ ] **Step 3: Convert each principal page using the Task 9 Step 2 + Task 10 Step 2 recipe**

Additional rule: every `apiClient` call in a page must be moved to a hook in `src/hooks/` and the page consumes the hook. After this task, no page in the principal portal calls `apiClient` directly.

- [ ] **Step 4: Verify**

```bash
cd frontend && npm run types:check && npm run lint
```
Expected: PASS.

- [ ] **Step 5: Smoke**

In the dev workflow, log in as a principal. Verify dashboard, users list, schools list, settings — each page mounts without console errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/principal frontend/src/routes/appRoutes.tsx
git commit -m "refactor(frontend): convert principal portal to TypeScript"
```

---

### Task 12: Convert teacher portal

**Files:**
- Modify: every `.js`/`.jsx` under `frontend/src/pages/teacher/`

Follow the same recipe as Task 11. Smoke target: log in as teacher, dashboard renders, today's classes visible, mark attendance works, edit grade works.

- [ ] **Steps 1–4:** Mirror Task 11 Steps 1, 3, 4, 5
- [ ] **Step 5: Commit**
```bash
git add frontend/src/pages/teacher
git commit -m "refactor(frontend): convert teacher portal to TypeScript"
```

---

### Task 13: Convert parent and student portals

**Files:**
- Modify: every `.js`/`.jsx` under `frontend/src/pages/parent/` and `frontend/src/pages/student/`

- [ ] **Step 1: Convert parent portal** (mirror Task 11)
- [ ] **Step 2: Smoke as parent** (dashboard, view child grades)
- [ ] **Step 3: Commit parent**
```bash
git add frontend/src/pages/parent
git commit -m "refactor(frontend): convert parent portal to TypeScript"
```
- [ ] **Step 4: Convert student portal** (mirror Task 11)
- [ ] **Step 5: Smoke as student** (dashboard, today's schedule, view own grades)
- [ ] **Step 6: Commit student**
```bash
git add frontend/src/pages/student
git commit -m "refactor(frontend): convert student portal to TypeScript"
```

---

### Task 14: Sweep remaining `.js`/`.jsx` and delete the legacy `apiClient.js`

**Files:**
- Modify: any leftover `.js`/`.jsx` flagged below
- Delete: `frontend/src/services/apiClient.js`
- Delete: `frontend/jsconfig.json`

- [ ] **Step 1: List remaining files**

```bash
cd frontend && find src -type f \( -name '*.js' -o -name '*.jsx' \) | grep -v '/types/api.gen.json'
```
Expected: empty output. If anything remains, convert it using the recipe.

- [ ] **Step 2: Verify no call site still imports the old `apiClient.js`**

```bash
cd frontend && grep -rn "services/apiClient'" src/ | grep -v "apiClient.ts"
cd frontend && grep -rn "from '@/services/apiClient'" src/
```
The only matches must resolve to `apiClient.ts`. Delete `apiClient.js`.

- [ ] **Step 3: Delete `jsconfig.json`**

```bash
rm frontend/jsconfig.json
```
The path alias is now in `tsconfig.json`.

- [ ] **Step 4: Verify**

```bash
cd frontend && npm run types:check && npm run lint && npm run build
```
Expected: all PASS, build produces a working bundle.

- [ ] **Step 5: CI gate — no `.js`/`.jsx` allowed**

Add a one-line check to the `frontend-ci.yml` (or document):

```yaml
      - name: No .js/.jsx allowed in src
        run: |
          if find frontend/src -type f \( -name '*.js' -o -name '*.jsx' \) | grep -q .; then
            echo "Found legacy .js/.jsx files in src/"; exit 1
          fi
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(frontend): remove legacy apiClient.js and jsconfig.json"
```

---

## Phase 4 — Playwright safety net (~2 days)

### Task 15: Install Playwright and write the smoke config

**Files:**
- Create: `frontend/playwright.config.ts`
- Create: `frontend/e2e/fixtures.ts`
- Create: `frontend/e2e/helpers.ts`
- Modify: `frontend/package.json`

- [ ] **Step 1: Install Playwright**

```bash
cd frontend && npm install --save-dev @playwright/test@^1
npx playwright install --with-deps
```
If `--with-deps` fails in the Replit environment, fall back to `npx playwright install` and document the limitation.

- [ ] **Step 2: Create `playwright.config.ts`**

```ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: false, // serialize so role logins don't fight over a shared session
  retries: 1,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
});
```

- [ ] **Step 3: Create `e2e/helpers.ts`**

```ts
import type { Page } from '@playwright/test';

export interface TestUser {
  username: string;
  password: string;
  role: 'principal' | 'teacher' | 'parent' | 'student';
}

export async function login(page: Page, user: TestUser): Promise<void> {
  await page.goto('/login');
  await page.getByLabel(/username/i).fill(user.username);
  await page.getByLabel(/password/i).fill(user.password);
  await page.getByRole('button', { name: /log in|sign in/i }).click();
  await page.waitForURL(new RegExp(`/${user.role}`));
}
```

- [ ] **Step 4: Create `e2e/fixtures.ts`**

```ts
import { test as base } from '@playwright/test';

import type { TestUser } from './helpers';

export interface Users {
  principal: TestUser;
  teacher: TestUser;
  parent: TestUser;
  student: TestUser;
}

export const test = base.extend<{ users: Users }>({
  users: async ({}, use) => {
    use({
      principal: { username: process.env.E2E_PRINCIPAL_USER!, password: process.env.E2E_PRINCIPAL_PASS!, role: 'principal' },
      teacher:   { username: process.env.E2E_TEACHER_USER!,   password: process.env.E2E_TEACHER_PASS!,   role: 'teacher' },
      parent:    { username: process.env.E2E_PARENT_USER!,    password: process.env.E2E_PARENT_PASS!,    role: 'parent' },
      student:   { username: process.env.E2E_STUDENT_USER!,   password: process.env.E2E_STUDENT_PASS!,   role: 'student' },
    });
  },
});

export { expect } from '@playwright/test';
```

- [ ] **Step 5: Add npm scripts**

```jsonc
{
  "scripts": {
    "e2e":         "playwright test",
    "e2e:headed":  "playwright test --headed",
    "e2e:report":  "playwright show-report"
  }
}
```

- [ ] **Step 6: Commit**

```bash
git add frontend/playwright.config.ts frontend/e2e frontend/package.json frontend/package-lock.json
git commit -m "test(frontend): add Playwright E2E harness"
```

---

### Task 16: Write the 10 smoke E2E tests

**Files:**
- Create: `frontend/e2e/01-login-roles.spec.ts`
- Create: `frontend/e2e/02-principal.spec.ts`
- Create: `frontend/e2e/03-teacher.spec.ts`
- Create: `frontend/e2e/04-parent.spec.ts`
- Create: `frontend/e2e/05-student.spec.ts`
- Create: `frontend/e2e/06-logout.spec.ts`

- [ ] **Step 1: `01-login-roles.spec.ts` (4 tests, paths #1–4 from spec §9)**

```ts
import { expect, test } from './fixtures';
import { login } from './helpers';

test('principal lands on dashboard with school name', async ({ page, users }) => {
  await login(page, users.principal);
  await expect(page.getByRole('heading', { name: /dashboard/i })).toBeVisible();
  await expect(page.locator('[data-testid="school-name"]')).toBeVisible();
});

test('teacher lands on dashboard with today schedule', async ({ page, users }) => {
  await login(page, users.teacher);
  await expect(page.locator('[data-testid="todays-classes"]')).toBeVisible();
});

test('parent lands on dashboard with child name', async ({ page, users }) => {
  await login(page, users.parent);
  await expect(page.locator('[data-testid="child-name"]')).toBeVisible();
});

test('student lands on dashboard with today schedule', async ({ page, users }) => {
  await login(page, users.student);
  await expect(page.locator('[data-testid="todays-schedule"]')).toBeVisible();
});
```

> If any of those `data-testid` attributes don't exist yet, add them in the relevant component as part of this task (it's a tiny, high-value refactor for testability).

- [ ] **Step 2: `02-principal.spec.ts` (paths #5, #6)**

```ts
import { expect, test } from './fixtures';
import { login } from './helpers';

test('principal users list loads with rows', async ({ page, users }) => {
  await login(page, users.principal);
  await page.getByRole('link', { name: /users/i }).click();
  const rows = page.getByRole('row');
  await expect(rows).not.toHaveCount(0);
});

test('principal can create a user', async ({ page, users }) => {
  await login(page, users.principal);
  await page.goto('/principal/users/new');
  await page.getByLabel(/username/i).fill(`e2e-user-${Date.now()}`);
  await page.getByLabel(/full name/i).fill('E2E Test');
  await page.getByLabel(/role/i).selectOption('teacher');
  await page.getByRole('button', { name: /save|create/i }).click();
  await expect(page).toHaveURL(/\/principal\/users\/[\w-]+$/);
});
```

- [ ] **Step 3: `03-teacher.spec.ts` (paths #7, #8)**

```ts
import { expect, test } from './fixtures';
import { login } from './helpers';

test('teacher marks attendance and it persists', async ({ page, users }) => {
  await login(page, users.teacher);
  await page.getByRole('link', { name: /attendance/i }).first().click();
  await page.locator('[data-testid="attendance-row"]').first()
    .getByRole('button', { name: /present/i }).click();
  await page.getByRole('button', { name: /save/i }).click();
  await expect(page.getByText(/saved|success/i)).toBeVisible();
  await page.reload();
  await expect(
    page.locator('[data-testid="attendance-row"]').first()
        .getByRole('button', { name: /present/i }),
  ).toHaveAttribute('aria-pressed', 'true');
});

test('teacher edits a grade', async ({ page, users }) => {
  await login(page, users.teacher);
  await page.getByRole('link', { name: /grades/i }).click();
  const input = page.locator('[data-testid="grade-input"]').first();
  await input.fill('85');
  await page.getByRole('button', { name: /save/i }).click();
  await expect(page.getByText(/saved|success/i)).toBeVisible();
});
```

- [ ] **Step 4: `04-parent.spec.ts` (path #9)**

```ts
import { expect, test } from './fixtures';
import { login } from './helpers';

test('parent views child grades', async ({ page, users }) => {
  await login(page, users.parent);
  await page.getByRole('link', { name: /grades/i }).click();
  const rows = page.locator('[data-testid="grade-row"]');
  await expect(rows).not.toHaveCount(0);
});
```

- [ ] **Step 5: `05-student.spec.ts` (placeholder for future expansion — student can already login per Task 16 Step 1)**

(No additional spec required for sprint scope; spec §9 lists 10 paths and login-as-student covers #4.)

- [ ] **Step 6: `06-logout.spec.ts` (path #10)**

```ts
import { expect, test } from './fixtures';
import { login } from './helpers';

test('logout from any portal returns to login', async ({ page, users }) => {
  await login(page, users.teacher);
  await page.getByRole('button', { name: /log out|sign out/i }).click();
  await expect(page).toHaveURL(/\/login/);
});
```

- [ ] **Step 7: Provision test accounts**

Set the following env vars in the test environment (request from the user as secrets if not present):
- `E2E_PRINCIPAL_USER`, `E2E_PRINCIPAL_PASS`
- `E2E_TEACHER_USER`, `E2E_TEACHER_PASS`
- `E2E_PARENT_USER`, `E2E_PARENT_PASS`
- `E2E_STUDENT_USER`, `E2E_STUDENT_PASS`

Use existing seed accounts; do not commit credentials.

- [ ] **Step 8: Run the suite**

```bash
cd frontend && npm run build && npx vite preview --port 5000 &
sleep 3
cd frontend && npm run e2e
```
Expected: 10 tests pass. Fix any failing test by adding missing `data-testid` attributes — never weaken an assertion.

- [ ] **Step 9: Commit**

```bash
git add frontend/e2e
git commit -m "test(frontend): add Playwright E2E suite covering 10 critical paths"
```

---

## Phase 5 — Strictness ratchet (~1.5 days)

### Task 17: Flip `noImplicitAny: true`

**Files:**
- Modify: `frontend/tsconfig.json`
- Modify: any file flagged by the new check

- [ ] **Step 1: Flip the flag**

In `frontend/tsconfig.json` change `"noImplicitAny": false` → `true`.

- [ ] **Step 2: Run the check**

```bash
cd frontend && npm run types:check 2>&1 | tee /tmp/p5-noimplicitany.log
```

- [ ] **Step 3: Fix every error**

For each error, prefer adding the explicit type (e.g. `(e: React.MouseEvent<HTMLButtonElement>) =>`). `unknown` is acceptable when the value really is opaque. `// @ts-expect-error` is **not** acceptable here.

- [ ] **Step 4: Verify**

```bash
cd frontend && npm run types:check && npm run lint && npm run e2e
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(frontend): enable noImplicitAny"
```

---

### Task 18: Flip `strictNullChecks: true`

**Files:**
- Modify: `frontend/tsconfig.json`
- Modify: any file flagged

- [ ] **Step 1: Flip the flag**

`"strictNullChecks": true`.

- [ ] **Step 2: Run check**

```bash
cd frontend && npm run types:check 2>&1 | tee /tmp/p5-nullchecks.log
```

- [ ] **Step 3: Fix every error**

Patterns to apply:
- Replace `if (x)` with `if (x != null)` only where falsy values matter; otherwise narrow with type guards.
- Use optional chaining (`x?.y`) and nullish coalescing (`x ?? default`) instead of widening to `T | undefined`.
- For wire types where the backend declares an `Optional`, the view mapper must default the field — never let `undefined` reach a UI component.

- [ ] **Step 4: Verify**

```bash
cd frontend && npm run types:check && npm run lint && npm run e2e
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(frontend): enable strictNullChecks"
```

---

### Task 19: Flip `noUncheckedIndexedAccess` and `useUnknownInCatchVariables`

**Files:**
- Modify: `frontend/tsconfig.json`
- Modify: any file flagged

- [ ] **Step 1: Flip both flags**

`"noUncheckedIndexedAccess": true` and `"useUnknownInCatchVariables": true`.

- [ ] **Step 2: Fix `useUnknownInCatchVariables` errors first** (smaller blast radius)

Every `catch (e) { ... e.message ... }` becomes:

```ts
catch (e) {
  const msg = e instanceof Error ? e.message : String(e);
  ...
}
```

Or, where `apiClient` is the source, narrow with `isApiError(e)` from `src/types/shared.ts`.

- [ ] **Step 3: Fix `noUncheckedIndexedAccess` errors**

Indexed accesses now return `T | undefined`. Most fixes are either:
- Assert non-null with a guard above the access, or
- Use `.at()` and handle `undefined` explicitly, or
- Narrow with `if (arr.length > N)` before access.

- [ ] **Step 4: Verify**

```bash
cd frontend && npm run types:check && npm run lint && npm run e2e
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(frontend): enable noUncheckedIndexedAccess and useUnknownInCatchVariables"
```

---

### Task 20: Final smoke + report

**Files:**
- Modify: `docs/health-checkup/2026-04-17/06-fixes-and-verification.md` (append a "Phase 6 — TS adoption" section)

- [ ] **Step 1: Run the full smoke checklist** from spec §10

- [ ] **Step 2: Run the Playwright suite end-to-end one more time**

```bash
cd frontend && npm run build && npx vite preview --port 5000 &
sleep 3 && cd frontend && npm run e2e
```
Expected: PASS.

- [ ] **Step 3: Confirm CI gate is in effect**

Open a no-op PR (or local check) — `tsc --noEmit` and `eslint --max-warnings 0` block on errors.

- [ ] **Step 4: Append the wrap-up section to the health-checkup report**

Document:
- Total files converted (should be the original .js/.jsx count, ~264).
- Final tsconfig flags (all strict-family flags `true`).
- E2E suite path count and runtime.
- Any remaining `// @ts-expect-error` markers (target: 0; if non-zero, list with rationale).
- Any backend routes still missing `response_model` (from Task 1 Step 5 audit).

- [ ] **Step 5: Commit**

```bash
git add docs/health-checkup
git commit -m "docs: record TypeScript adoption sprint completion"
```

---

## Self-Review

**Spec coverage:** Every section of the spec has at least one task — Foundations (Tasks 1–5), Cross-cutting (6–9), Portals (10–13), Sweep + cleanup (14), Playwright (15–16), Strictness ratchet (17–19), Smoke + report (20). The hybrid-types architecture, layer lint rules, branded IDs, ApiState/ApiError, and named-export conventions all have explicit code shown.

**Placeholder scan:** No "TBD/TODO/implement later". Every code-changing step has a code block. Backend `response_model` audit is concrete (Task 1 Step 5). Test data-testid attributes are explicitly the responsibility of Task 16 (added in-line if missing).

**Type consistency:** `UserView`, `ApiState`, `ApiError`, `isApiError`, `toUserView`, `getMe`/`getTeacherMe`/`getStudentMe`, branded ID names (`UserId`, `SchoolId`, `TeacherId`, `StudentId`, `ParentId`, `ClassId`) are used consistently across Tasks 6, 7, 8, 9. Lint rule names (`import/no-cycle`, `import/no-default-export`, `no-restricted-imports`, `@typescript-eslint/no-explicit-any`) are referenced consistently across Tasks 4, 9, 10.

Plan ready for execution.
