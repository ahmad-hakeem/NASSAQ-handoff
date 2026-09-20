# Task 1169 browser verification evidence

## Status

Executed against the restarted Frontend Dev server on `http://localhost:5000`.

Final run:

```text
E2E_BASE_URL=http://localhost:5000 npx playwright test \
  e2e/management/external-import-review.task1169.spec.ts \
  --project=chromium --reporter=list

2 passed (11.7s)
```

The first exploratory run exposed an incorrect fixture role (`principal` rather
than the application's canonical `school_principal`) and a brittle teacher-type
locator. Both browser-fixture issues were corrected before the final passing
run; neither required application changes.

## Owned artifact

- `frontend/e2e/management/external-import-review.task1169.spec.ts`

## Coverage boundary

### Real when executed

- Chromium browser and rendered React application.
- Restarted frontend bundle, route guards, authenticated app shell, Users &
  Classes route, Arabic/RTL theme state, `ExternalImportReview`, and the
  existing Noor panel.
- DOM interaction, responsive layout at 390×844, file chooser behavior, search, pagination, checkboxes, disabled states, cancel interaction, and result rendering.

### Mocked when executed

- Authentication bootstrap (`GET /api/auth/me` and permissions) because no
  `E2E_PRINCIPAL_EMAIL` / `E2E_PRINCIPAL_PASSWORD` were available.
- Unrelated management-directory and Noor API reads were intercepted with
  empty development fixtures. Therefore "Noor remains usable" means its real
  rendered panel and controls remained present and enabled; it does **not**
  claim live Noor history/preview backend coverage.
- `POST /api/bulk/preview/students`
- `POST /api/bulk/preview/teachers`
- `POST /api/bulk/confirm`
- `POST /api/bulk/draft/{draft_id}/discard`

The intercepted responses follow `docs/external-import-api.md`. Mocking these write/draft endpoints makes student/teacher preview, conflict, warning, confirmation, and cancellation deterministic and guarantees the browser check cannot import domain records. The spec additionally asserts the exact confirm body and observes discard requests.

### Not covered by this browser script

- Spreadsheet parsing and persistence against the real backend; those belong to backend/integration coverage.
- Real principal password authentication and real management/Noor reads in
  this run (credentials were unavailable).
- A real destructive import or any production endpoint.
- Cross-browser engines other than Chromium.
- Pixel-diff visual regression.

## Evidence

- `artifacts/task1169/students-mobile-search.png` — mocked student preview,
  filtered to one Arabic/RTL row at 390×844.
- `artifacts/task1169/teachers-blocked-noor.png` — mocked teacher conflict,
  whole-import disabled confirmation, with the real Noor panel still rendered.
- The student scenario observed the discard call and asserted the confirm JSON
  was exactly `draft_id`, `fingerprint`, `preview_version`, and
  `acknowledged: true`.
- The teacher conflict scenario observed zero confirm calls.
- No production URL was used. Every external-import draft/mutation route was
  intercepted.

## Visual note

The 390×844 full-page evidence shows a fixed application overlay/drawer
covering part of the lower review area after resizing from desktop. The review
itself had no horizontal overflow and remained interactable, so the scripted
responsive assertions passed, but the overlay is a visible mobile-layout
concern worth triaging separately. No application code was changed here.