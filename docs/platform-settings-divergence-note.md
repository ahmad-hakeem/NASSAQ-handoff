# Platform Settings — UI ↔ Backend Divergence Note

**Owner:** Platform Admin Settings
**Frontend:** `frontend/src/pages/PlatformSettingsPage.jsx`
**Backend (live):** `backend/routes/settings_routes.py` — mounted under `/api/settings/*`
**Backend (parallel):** `backend/routes/platform_routes_mod.py` — mounted under `/api/settings/platform/*` (and `/api/settings/api-keys/*`)
**Status (as of Task #172):** P0 truthfulness fixes shipped; this note inventories the remaining UI surfaces and the two-surface backend split. **Informational only — Task #172 does not propose a merge or migration.**

## What Task #172 already fixed (P0/P1)

| Surface | Previous behaviour | After #172 |
|---|---|---|
| "Two-Factor Authentication" toggle in Security & Sessions | Local-only `twoFactorEnabled` switch; value silently dropped on save (no schema field) | Removed. Replaced with a CTA button that deep-links to **Account Settings → Security** via `'/account/settings#security'`. `AccountSettingsPage` now reads the URL hash on mount and on `hashchange` to set `activeSection`. |
| `/settings/security` PUT schema (`SecuritySettings`) | `extra='ignore'` (default) — unknown fields silently dropped | `model_config = ConfigDict(extra='forbid')`. The PUT route validates manually and converts `ValidationError` into a safe Arabic HTTP 422 (`"حقول غير مدعومة في إعدادات الأمان: …"`) so the frontend renders it through `NassaqAlertDialog` instead of the default verbose Pydantic error array. |
| `DELETE /settings/sessions/{id}` and `POST /settings/sessions/end-all` | Authenticated only — no step-up gate | Both now stack `Depends(require_recent_mfa())`. `end-all` additionally fails closed with HTTP 400 + Arabic message when the bearer JWT has no `jti` (otherwise we'd silently revoke every session including the caller's). |
| Visual Identity tab (logo / favicon / primary / secondary / accent colours) | Editable inputs and upload buttons writing to local state only — no `/settings/branding` endpoint exists | Locked to **preview-only**: an Arabic "معاينة فقط" badge sits at the top of the card; colour `Input`s are `readOnly + disabled`; logo/favicon `Upload` buttons are `disabled`; **the global header Save button is disabled and relabeled "معاينة فقط" while `activeTab === 'brand'`**, and `handleSaveBrandSettings` is a defensive no-op (no toast). |

## Two-surface overlap inventory

The Platform Settings page has **two** parallel backend surfaces. Today the React page only calls the first one; the second one is mounted but unused by this page.

### Live surface — `settings_routes.py` (used by PlatformSettingsPage)

| HTTP route | Schema | Storage table / key | Frontend consumer (PlatformSettingsPage.jsx) |
|---|---|---|---|
| `GET  /settings/general` | `GeneralSettings` (platform_name, platform_name_en, browser_title, default_language, date_system, timezone) | `system_settings` where `type='general'` | `fetchSettings` → hydrates `generalSettings` |
| `PUT  /settings/general` | same | same | `handleSaveGeneralSettings` |
| `GET  /settings/maintenance` | `MaintenanceSettings` (maintenance_mode, registration_open, …messages) | `system_settings` where `type='maintenance'` | `fetchSettings` (read-only here; toggles ride along on `/settings/general` save) |
| `PUT  /settings/maintenance` | same | same | (not currently invoked from this page) |
| `GET  /settings/contact` | `ContactInfo` (email, phone, working_hours_*, address_*, social_*) | `system_settings` where `type='contact'` | `fetchSettings` → hydrates `contactInfo` |
| `PUT  /settings/contact` | same | same | `handleSaveContactSettings` |
| `GET  /settings/security` | `SecuritySettings` (session_duration_minutes, max_concurrent_sessions, min_password_length, require_*) | `system_settings` where `type='security'` | `fetchSettings` |
| `PUT  /settings/security` | same (now `extra='forbid'`, manual validation, Arabic 422) | same | `handleSaveSecuritySettings` |
| `GET/POST /settings/terms[/...]` | `TermsVersion` | `terms_versions` (versioned rows) | `fetchSettings`, `handleSaveTermsVersion` |
| `GET/POST /settings/privacy[/...]` | `PrivacyVersion` | `privacy_versions` | `fetchSettings`, `handleSavePrivacyVersion` |
| ~~`GET/PUT /settings/account`, `POST /settings/account/upload-picture`, `DELETE /settings/account/profile-picture`~~ | ~~`UserAccountSettings`~~ | ~~`users` (current user row)~~ | **Retired in Task #174.** Personal profile/avatar writes go through `PUT /users/me/profile` and `POST /users/me/avatar` (`routes/user_routes_mod.py`) exclusively. |
| `GET    /settings/sessions` | — | `user_sessions` | account tab session list |
| `DELETE /settings/sessions/{id}` | — | `user_sessions` + `revoked_tokens` | account tab "end this session" (now MFA-step-up gated) |
| `POST   /settings/sessions/end-all` | — | `user_sessions` + `revoked_tokens` | account tab "end all others" (now MFA-step-up gated, refuses on missing `jti`) |
| ~~`GET    /settings/titles`~~ | — | ~~static dictionary~~ | **Retired in Task #174** alongside `/settings/account*`. |

### Parallel surface — `platform_routes_mod.py` (NOT called by PlatformSettingsPage today)

| HTTP route | Schema | Storage table / key | Frontend consumer |
|---|---|---|---|
| `GET  /settings/platform` | `PlatformSettingsResponse` (composite: general, brand, contact, terms, privacy, security) | `platform_settings` where `type='platform'` (single row, all sections nested under one document) | none in `PlatformSettingsPage.jsx` (grep confirmed) |
| `PUT  /settings/platform/general` | `GeneralSettingsModel` (note: extra fields vs. live: `email_notifications`, `sms_notifications`, `push_notifications`, `ai_features`, `registration_open`, `maintenance_mode`; uses `date_format` instead of `date_system`; uses `platform_name_ar` instead of `platform_name`) | same `platform_settings.general` | none |
| `PUT  /settings/platform/brand` | `BrandSettingsModel` (logo, favicon, primary_color, secondary_color, accent_color) | same `platform_settings.brand` | none — this is the schema the locked Visual Identity tab would target if/when wired |
| `PUT  /settings/platform/contact` | `ContactInfoModel` (extra fields vs. live: `support_email`, `alternate_phone`, `website`, `owner_name`; flat `working_hours`/`address` instead of `_ar`/`_en`) | same `platform_settings.contact` | none |
| `PUT  /settings/platform/terms` | `LegalContentModel` (single content + version + effective_date; also writes a row to `legal_versions`) | `platform_settings.terms` + `legal_versions` rows | none |
| `PUT  /settings/platform/privacy` | `LegalContentModel` | `platform_settings.privacy` + `legal_versions` rows | none |
| `PUT  /settings/platform/security` | `SecuritySettingsModel` (extra field `two_factor_enabled` and uses camel-ish boolean names: `session_timeout`, `max_sessions`, `password_require_uppercase`, `password_require_numbers`, `password_require_special`) | `platform_settings.security` | none — and notably this is the only place where `two_factor_enabled` exists as a server-accepted field anywhere, but no route enforces it |
| `GET  /settings/legal-versions/{doc_type}` | — | `legal_versions` | none in this page |
| `POST/GET /settings/api-keys`, `POST .../revoke`, `DELETE .../{id}` | `APIKeyCreate`, `APIKeyResponse` | `api_keys` | none in this page |

### Observations

1. **Two storage shapes for the same product surface.** `system_settings` (key-per-section) vs. `platform_settings` (one composite row). Neither table is documented as canonical; both ship with default-row hydration code that masks emptiness.
2. **Field-name drift is real.** `platform_name` vs. `platform_name_ar`; `date_system` vs. `date_format`; `working_hours_ar/_en` vs. flat `working_hours`. A future merge cannot be a 1:1 rename — it needs a translation layer.
3. **`SecuritySettingsModel` is the only schema that still defines `two_factor_enabled`.** Even though no route enforces it, leaving it accepted by `PUT /settings/platform/security` is the same dishonesty pattern P0 just removed from the live `SecuritySettings`. A follow-up should either delete this field too or wire it to a real per-tenant policy.
4. **None of the `/settings/platform/*` PUTs require `require_recent_mfa()`**, while their `settings_routes.py` counterparts do. If any frontend ever switches to the parallel surface, the MFA step-up gate added in #172 would silently regress.
5. **`platform_routes_mod.py` security PUT writes only**; no audit-log row is inserted (the live `settings_routes.py` PUT does insert one with field-by-field diffs).

## Remaining UI ↔ backend divergences (NOT in scope for #172)

These are surfaces the #172 audit confirmed exceed the live backend; each is a candidate for its own follow-up.

1. **Visual Identity → branding persistence.** The locked controls would target `PUT /settings/platform/brand` if/when unlocked. To unlock honestly, pick a canonical surface (see below), wire `fetchSettings` and a real save handler, add `require_recent_mfa()` and an audit-log row, and remove the P1 preview-only lock.
2. **General Settings → `emailNotifications` / `smsNotifications` / `pushNotifications` / `aiFeatures` switches.** Populated from constants and posted to `/settings/general`, but the live `GeneralSettings` Pydantic model doesn't define them, so they're dropped on save the same way 2FA was. The parallel `GeneralSettingsModel` *does* accept them — but nothing reads them either. Mirror the #172 P0 fix: add the fields to the live schema with `extra='forbid'` and a feature-flag table, or hide the switches.
3. **Contact Info → `alternatePhone`, `website`, `ownerName`.** Present in `contactInfo` state but absent from the live `ContactInfo` model — drop-on-save. Parallel `ContactInfoModel` accepts them.
4. **Security & Sessions → `passwordMinLength`.** Persists correctly but `/auth/change-password` hardcodes its own 8-char minimum, so the stored value is advisory.
5. **`maintenanceMode` / `registrationOpen` switches.** Persist via `/settings/maintenance` but neither the login route nor the registration route consults the stored value — verify enforcement before claiming the controls are truthful.
6. **Terms & Privacy version metadata.** Editor allows creating a draft without ever publishing it; confirm the publish path is reachable from this page or document that publishing happens elsewhere.

## Canonical-surface recommendation (for the future merge task)

This is **not** a Task #172 deliverable — it's a guide for the follow-up that picks ONE surface and deletes the other.

* **Recommended canonical surface: `settings_routes.py` (`/api/settings/*`).**
  * It is what the live React page actually calls today, so picking it minimises frontend churn.
  * It already has the `require_recent_mfa()` step-up gate on session-revoke routes and (post-#172) strict-extra validation with safe Arabic 422 on `PUT /settings/security`.
  * It already inserts field-by-field audit-log rows on security changes.
  * Its key-per-section storage (`system_settings` rows keyed by `type`) is easier to migrate piecewise than the composite single-row `platform_settings` document.
* **What needs to happen in the merge task (out of scope for #172):**
  1. Add the genuinely missing fields from the parallel models to the live ones (notification flags on `GeneralSettings`; `support_email`, `alternate_phone`, `website`, `owner_name` on `ContactInfo`; `logo`, `favicon`, `primary_color`, `secondary_color`, `accent_color` as a brand-new `BrandSettings` schema). Apply `extra='forbid'` to each, with the same Arabic-422 wrapper pattern.
  2. Add `require_recent_mfa()` to every new `PUT` and an audit-log row on every change.
  3. Backfill `system_settings` rows from any existing `platform_settings` document, then delete the composite row and the `/settings/platform/*` routes (and the `BrandSettingsModel`/`SecuritySettingsModel` etc. classes) and the `/settings/platform` GET. Remove `two_factor_enabled` along the way.
  4. Unlock the Visual Identity tab once `BrandSettings` is real, replacing the #172 P1 preview lock.

## Deferred and explicitly out-of-scope

* **MFA core** (`mfa_routes.py`, `MfaSecuritySection.jsx`, factor model, audit hash chain, `require_recent_mfa` internals) — locked under Task #169 and not modified here. The #172 changes only *reuse* `require_recent_mfa()` on session-revoke routes.
* Any database migration, data backfill, or destructive cleanup. The merge outlined above is a future task; #172 ships only the truthfulness fixes and this inventory.
