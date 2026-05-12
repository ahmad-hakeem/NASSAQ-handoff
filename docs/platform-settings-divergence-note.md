# Platform Settings — UI ↔ Backend Divergence Note

**Owner:** Platform Admin Settings
**Frontend:** `frontend/src/pages/PlatformSettingsPage.jsx`
**Backend:** `backend/routes/settings_routes.py`
**Status (as of Task #172):** P0 truthfulness fixes shipped; this note tracks
the remaining UI surfaces whose values are *not* persisted by the API.

This is a divergence inventory only — no merge or migration is proposed here.
Each row is a separate follow-up item to be triaged later.

## What Task #172 already fixed (P0/P1)

| Surface | Previous behaviour | After #172 |
|---|---|---|
| "Two-Factor Authentication" toggle in Security & Sessions | Local-only `twoFactorEnabled` switch; value silently dropped on save (no schema field) | Removed. Replaced with a CTA button that deep-links to **Account Settings → Security** (`/account/settings`), where `MfaSecuritySection` is the real per-account MFA UI. The legacy `twoFactorEnabled` field was also removed from `securitySettings` state and from the `/settings/security` GET hydrator. |
| `/settings/security` PUT schema (`SecuritySettings`) | `extra='ignore'` (default) — unknown fields silently dropped | `model_config = ConfigDict(extra='forbid')`. The PUT route validates manually and converts `ValidationError` into a safe Arabic HTTP 422 (`"حقول غير مدعومة في إعدادات الأمان: …"`) so the frontend renders it through `NassaqAlertDialog` instead of the default verbose Pydantic error array. |
| `DELETE /settings/sessions/{id}` and `POST /settings/sessions/end-all` | Authenticated only — no step-up gate | Both now stack `Depends(require_recent_mfa())`. `end-all` additionally fails closed with HTTP 400 + Arabic message when the bearer JWT has no `jti` (otherwise we'd silently revoke every session including the caller's). |
| Visual Identity tab (logo / favicon / primary / secondary / accent colours) | Editable inputs and upload buttons that wrote to local state only — no `/settings/branding` endpoint exists | Locked to **preview-only**: an Arabic "معاينة فقط" badge sits at the top of the card; colour `Input`s are `readOnly` + `disabled`; logo/favicon `Upload` buttons are `disabled`. The card layout is preserved so existing screenshots/docs still match. |

## Remaining divergences (NOT in scope for #172 — follow-up only)

These are surfaces I confirmed during the #172 audit where the visible control
still exceeds what the backend stores. None are dishonest after #172 (they're
either preview-locked, role-gated to admins who can verify, or otherwise
non-misleading), but each warrants a future task to either add a real backend
or remove the surface.

1. **Visual Identity → branding persistence.** No `/settings/branding`
   endpoint exists. To unlock the controls again, the follow-up needs a
   `branding` row in `system_settings` (logo URL, favicon URL, primaryColor,
   secondaryColor, accentColor), a PUT schema with strict validation, an
   audit-log entry on change, and frontend code that reads/writes it. Until
   then the preview-only lock from P1 stands.

2. **General Settings → `emailNotifications` / `smsNotifications` /
   `pushNotifications` / `aiFeatures` switches.** These are populated from
   constants in `fetchSettings` and posted to `/settings/general`, but the
   `GeneralSettings` Pydantic model (lines 33–40) doesn't define any of them,
   so they're dropped on save the same way 2FA was. Mirror the #172 P0 fix:
   either add the fields to the schema and a feature-flag table, or hide the
   switches.

3. **Contact Info → `alternatePhone`, `website`, `ownerName`.** These three
   are present in the `contactInfo` state and rendered in the Contact tab but
   `ContactInfo` Pydantic model has no equivalent fields (lines 79–91). Same
   "drop-on-save" pattern. Either extend `ContactInfo` or remove the inputs.

4. **Security & Sessions → `passwordMinLength` slider/select.** Persisted
   correctly, but the policy is never enforced at password-set time (the
   `/auth/change-password` endpoint hardcodes its own 8-char minimum). The
   stored value is therefore advisory. Wire it into the password validator or
   make the control read-only.

5. **`maintenanceMode` / `registrationOpen` switches.** These DO persist via
   `/settings/maintenance`, but neither the login route nor the registration
   route currently consults the stored value. Verify enforcement before
   declaring the controls truthful.

6. **Terms & Privacy version metadata.** The "lastUpdated" / "currentVersion"
   chips are read from the latest published row, but the editor allows
   creating a draft without ever publishing it. Confirm the publish path is
   reachable from this page (or document that publishing must happen
   elsewhere).

## Deferred and explicitly out-of-scope

* **MFA core** (`mfa_routes.py`, `MfaSecuritySection.jsx`, factor model,
  audit hash chain, `require_recent_mfa` internals) — locked under Task #169
  and not modified here. The #172 changes only *reuse* `require_recent_mfa()`
  on session-revoke routes.

* Any database migration, data backfill, or destructive cleanup.
