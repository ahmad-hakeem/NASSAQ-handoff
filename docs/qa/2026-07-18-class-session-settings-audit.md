# Audit — إعدادات الحصة on the Class Page (فصولي → تفاصيل الفصل)

**Date:** 2026-07-18
**Scope:** Rename "إعدادات الشريط الجانبي" → "إعدادات الحصة" on `TeacherClassDetailPage`, bring the dialog to full parity with the live-lesson settings dialog (behaviours / skills / evaluation elements + session configuration), and back both surfaces with a single synced source of truth — the `session_settings` template keyed by `(class_id, subject_id, tenant)`. Applies to **School Teacher** and **Independent Teacher (IT)**.

---

## 1. What changed

### Backend
| File | Change |
|---|---|
| `backend/utils/session_settings.py` (new) | Shared sanitizers for every user-controlled settings field. Both write routes funnel through these helpers so validation stays identical. Absent key = don't touch (partial POST never clobbers other fields). Session-scoped fields (`correct_answer_weight`, `streak_bonus_value`) are deliberately **not** handled here — they live only on the live-lesson route (stored on `class_sessions`). |
| `backend/routes/scheduling_smart_session_routes.py` | New `GET /class/{class_id}/session-settings?subject_id=…` and `POST /class/{class_id}/session-settings` (subject_id required — 422 if missing). Tenant is resolved from the **class row**, never from caller input. `_verify_class_access`: school teacher without linkage → 403; IT cross-workspace → **404** (spec §8 inv. 3 — never confirm foreign rows). |
| `backend/routes/role_dashboards_mod.py` | Live-lesson settings route refactored to use the same shared sanitizers (single validation path). |

### Frontend
| File | Change |
|---|---|
| `frontend/src/config/sessionElements.js` (new) | Single source for `DEFAULT_EVALUATION_ITEMS` / default element definitions shared by the teach page and the class page. |
| `frontend/src/pages/TeacherModule/TeacherClassDetailPage.jsx` | Button renamed to `t('sessionSettings')` ("إعدادات الحصة"). Dialog now receives the full element set: defaults ∪ custom behaviours (defaults `removable:false`), skills, evaluation items, and full `sessionConfig`. Template hydration per class+subject (`templateHydratedRef`, reset on class change) with a latest-wins request token so a superseded subject's GET can never hydrate (prevents a later silent save writing subject A's template into subject B's row). Explicit Save POSTs the template; closing the dialog performs a **silent save** (guarded so it never fires before hydration). Default eval item IDs are stripped before POST — the template stores only user-added items; defaults are re-prepended on hydrate. |
| `frontend/src/pages/TeacherModule/SessionTeachPage.jsx` | Reads the same defaults from `config/sessionElements.js`; missing `api` hook dependency fixed. |

### Intentional differences (class page vs live lesson)
- `correctAnswerWeight` and `streakBonusValue` are **session-scoped** (per live lesson, stored on `class_sessions`) and are not exposed or persisted by the class-page template. The template's tolerant sanitizer silently drops them if sent.
- Radix programmatic close does not fire `onOpenChange`, so an explicit Save never double-POSTs with the close-save.

---

## 2. Single source of truth

`session_settings` template rows keyed `(class_id, subject_id, tenant)`:
- The class-page dialog reads/writes the template directly via the new routes.
- The live-lesson settings route writes through the **same sanitizer module**, so a value valid on one surface is valid on the other.
- Partial writes only touch keys present in the payload (verified by test — customs/streak survive an unrelated partial POST).

---

## 3. Access control

| Case | Result |
|---|---|
| School teacher linked to class (teacher_assignments) | 200 |
| School teacher with no linkage to the class | 403 |
| IT owner, own workspace class | 200 |
| IT reaching another workspace's class by id | **404** (never 403/200 — §8 inv. 3) |
| POST without `subject_id` | 422 |
| Tenant resolution | From the class row (server-side), never caller-supplied |

---

## 4. Test coverage

`backend/tests/test_class_session_settings_template.py` — **6/6 passed**:
1. School-teacher roundtrip (POST → GET returns persisted template).
2. Partial POST does not clobber custom elements or streak toggle.
3. POST without subject_id → 422.
4. Unlinked school teacher → 403.
5. IT owner roundtrip.
6. IT cross-workspace by-id → 404 (never 403).

Regression suites re-run after the shared-sanitizer refactor — **66/66 passed**:
`test_streak_bonus_enabled_toggle.py`, `test_streak_bonus_value.py`, `test_participation_settings.py`, `test_correct_answer_weight_task1025.py`.

---

## 5. UI QA (Playwright, both roles)

Method: minted in-process tokens (IT token carries the `tenant_id: itw_…` claim), injected `nassaq_token`, navigated to `/teacher/class/{classId}` on the dev server, opened the dialog.

| Check | School Teacher | IT |
|---|---|---|
| Button labelled "إعدادات الحصة" | ✅ | ✅ |
| Dialog opens with title "إعدادات الحصة" | ✅ | ✅ |
| Element tabs: عناصر التقييم / السلوكيات / المهارات | ✅ | ✅ |
| Session config tabs: خيارات الحصة / أنماط التقييم | ✅ | ✅ |
| Default eval items visible (إجابة صحيحة +1 …) | ✅ | ✅ |
| Silent save POST on dialog close | ✅ (backend log) | ✅ (backend log) |
| JS console/page errors | none | none |

API smoke (both roles): GET 200, POST 200, re-GET reflects the change, POST without subject 422; `streak_bonus_value` correctly dropped by the template route (session-scoped by design).

---

## 6. Build health

- Backend: full new suite + 66 regression tests green; Backend API workflow serving normally.
- Frontend: dev server compiles; the two `react-hooks/exhaustive-deps` warnings surfaced in the edited files were fixed (stable `api` / `t` deps added). Production build (`fe-build`) green with **zero lint warnings in the edited files**.

---

## 7. Architect review (final, with git diff)

**Verdict: PASS — no blocking issues.** The reviewer independently re-ran all test suites (6/6 + 66/66 confirmed), verified `_verify_class_access` (IT cross-workspace 404, unlinked teacher 403, §6.7 read-only collaborators blocked from POST), and did a line-by-line comparison of the extracted sanitizers against the removed inline live-lesson code (behavior-preserving; the Arabic 422 and clamp rules identical).

Findings addressed post-review:
- **Subject-switch stale-response race** — fixed: `loadSessionTemplate` now uses a latest-wins request token; superseded responses are discarded. Re-verified in the browser after the fix (dialog opens, no JS errors).

Accepted as-is (non-blocking, by design or pre-existing):
- Switching subjects inside the dialog discards unsaved edits to the previous subject (no prompt) — accepted UX tradeoff.
- No IT §5.7 MFA step-up on the new POST — consistent with every sibling write on the same router (`add_lesson`, grade-columns); revisit only if a step-up backfill targets this router.
