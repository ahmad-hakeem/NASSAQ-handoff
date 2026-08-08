# CI Quarantine List

Tests excluded from the merge gate. Every entry needs: test id(s), failure mode,
root-cause note, and a follow-up owner. Removing an entry = deleting its skip
marker and proving the test green. Adding an entry requires the same rigor as
this list's existing entries — no drive-by skips.

| Test(s) | Quarantined | Failure mode | Root cause | Follow-up |
|---|---|---|---|---|
| `tests/test_session_homework_grade_sync_task969.py::test_no_auto_submission_when_mode_is_didnt_submit`, `::test_flip_done_no_grade_rows_for_non_submitted_mode` | 2026-07-25 | Expected didnt_submit mode to skip grade-sync; engine produces grades anyway. | Route persists `homework_mode` but grade-sync engine only consults `homework_enabled` — product gap needing sign-off. | Product decision on `homework_mode` vs. `homework_enabled` semantics. |
| `tests/test_independent_teacher_phase2_workspace_lifecycle.py::test_soft_delete_409_when_already_archived`, `::test_reactivate_happy_path_within_window`, `::test_reactivate_410_past_30_day_window`, `::test_banner_appears_after_reactivate`, `::test_banner_hides_after_dismiss`, `::test_banner_rearms_after_second_archive_reactivate_cycle`, `::test_dismiss_with_forged_tenant_claim_cannot_touch_foreign_workspace` | 2026-07-25 | Each drives an archive→(reactivate\|dismiss\|soft-delete) cycle on the owner's own bearer token and expects the documented 200/409/410. The archived-workspace auth gate in `get_current_user` now rejects the request with **401** (`تم أرشفة مساحة العمل…`) before the lifecycle handler runs, so reactivate/dismiss/soft-delete-while-archived are unreachable via self-service. | Intentional session-cut hardening (§6.8 gate in `backend/dependencies.py::get_current_user` + the archived-login gate in `backend/routes/auth_routes_mod.py` + the `last_password_change` bump on soft-delete) cuts **all** of an archived IT workspace's sessions. But `docs/it-phase2-reference.md` §6.8 still promises a 30-day *self-service* reactivation window (reactivate → 200 within window, 410 past it). Genuine contract conflict: the hardened auth layer makes the documented reactivate/dismiss flow impossible via the owner's token, and the login gate points the user to a "support link" (`رابط الدعم`) instead. A real fix must choose and wire one reactivation channel end-to-end (support/admin-driven reactivation vs. a dedicated reactivation token vs. a path-exemption in the archived gate **plus** a login affordance so the user can obtain a usable token). That spans `dependencies.py` + `auth_routes_mod.py` + the lifecycle routes + the doc — a multi-file behavioral repair, out of scope for the merge-gate baseline triage. Not fixed by a localized single guard: exempting only the archived gate would make these tests green while the real production flow (blocked login + `last_password_change` cut) stays broken — a false green. | **User decision on the archived-workspace reactivation contract.** Decide how an archived IT owner reactivates within the 30-day window, then implement that flow and its auth path, delete these skip markers, and prove the tests green (or rewrite them against the chosen contract). Owner: product + IT-phase2 backend. |
| `tests/test_workspace_archive_reminder.py::test_reactivate_clears_reminder_stamp`, `tests/test_workspace_erasure.py::test_request_erasure_idempotent_409`, `::test_reactivate_410_once_erasure_requested` | 2026-07-25 | Same §6.8 conflict class as the row above: each replays the owner's original bearer against reactivate / a second request-erasure and expects the route-level 200/409/410, but the request 401s (`تم أرشفة مساحة العمل…`) before the handler runs. | For the reminder test it is the archived-workspace gate in `get_current_user`; for the two erasure tests it is the erasure route's own session cut (`is_active=False` + `last_password_change` bump) — by design the same token can never come back. Same multi-file contract repair as above (choose one reactivation channel end-to-end); a localized gate exemption was tried and reverted because production login stays blocked and archived tokens are cut anyway. | Same user decision as the row above (§6.8 reactivation channel). |

## Environment-gated (skipped in the gate, runnable manually)

| Test(s) | Gated | Why | How to run |
|---|---|---|---|
| ~55 legacy live-server modules (every test module defining a module-level `BASE_URL` from `REACT_APP_BACKEND_URL`, e.g. `tests/test_assessment_api.py`, `tests/test_behaviour_multirole.py`, `tests/test_bulk_import_export.py`, the `test_iteration_*.py` family, …) plus the two localhost-defaulting scripts `tests/test_session_revocation_refresh_jti.py` and `tests/test_integration_phase5.py` | 2026-07-25 | Legacy HTTP integration scripts: they drive a **running**, pre-seeded backend via `requests`/`websockets`/`httpx` and hardcoded workspace data (ids, credentials). In the CI gate there is no server and no seeded data — they errored with `MissingSchema` (or would hit a dead `localhost:8000`). | Skipped wholesale by the `pytest_collection_modifyitems` hook in `tests/conftest.py` (keyed on the module-level `BASE_URL` convention) unless `REACT_APP_BACKEND_URL` is an absolute URL; the two localhost-defaulting files carry their own explicit `skipif` (`REACT_APP_BACKEND_URL` / `TEST_BASE_URL` must be explicitly set). To run: point the respective env var at a running, seeded backend. Follow-up: port valuable coverage to the in-process `httpx` client + per-test fixtures like the rest of the suite, and remove hardcoded credentials (violates the no-hardcoded-passwords rule). New tests must NOT follow the `BASE_URL` pattern. |

## Notes

### Not quarantined (fixed in the same pass — for the record)

The same two files carried additional red that was **stale-test drift**, not a
contract conflict, so those were fixed rather than quarantined:

- **MFA step-up / challenge tests** (`test_export_requires_recent_mfa`,
  `test_soft_delete_requires_recent_mfa`, `test_reactivate_requires_recent_mfa`,
  `test_post_login_workspace_lifecycle.py::test_mfa_verify_embeds_reactivation_banner_for_freshly_reactivated_it_user`)
  were failing only because this environment runs with the demo kill switch
  `MFA_ENFORCEMENT_DISABLED=true` (see `backend/services/mfa_policy.py`), which
  no-ops the step-up dependency and skips the login challenge. Fixed by adding
  `monkeypatch.setenv("MFA_ENFORCEMENT_DISABLED", "false")` — the established
  convention already used by ~10 sibling suites (e.g.
  `test_independent_teacher_students.py`, `test_independent_teacher_invite_parent.py`).

- **Public download tests** (`test_export_payload_isolated_to_caller_workspace`,
  `test_export_bundle_omits_non_whitelisted_tables`, `test_public_download_is_single_use`,
  `test_export_remint_invalidates_prior_token`) called `GET /public/workspace-export/{token}`
  without a bearer and expected 200/404, but Task #369 (documented in the route
  docstring and already enforced by sibling tests
  `test_download_requires_bearer_token` / `test_download_rejects_wrong_user`)
  now requires the exporting owner's bearer → 403 without it. Fixed by adding the
  owner bearer header to the GET calls. NB: `docs/it-phase2-reference.md` §6.8
  still calls this endpoint "unauth" and is stale relative to §369; the route
  docstring + passing sibling tests are the authoritative contract.
