# Platform teacher permanent-deletion diagnosis

## Request path and authorization

The Platform User Management detail and list screens send `DELETE /api/users/{user_id}`. Teacher targets delegate to the shared teacher permanent-deletion service, with an explicit expected account ID. School deletion remains tenant-scoped; platform deletion can address teachers across schools but does not override shared-identity safeguards.

Authentication validates the token and reloads the caller from the users table. The platform route requires the current database role `platform_admin`; frontend role labels and stale JWT role claims do not authorize deletion. This application uses role-based authorization here, not a permission named `users.permanent_delete`.

The historical screenshot's caller ID, token claims, HTTP response, and exact target identity could not be recovered from retained production logs. Do not represent the screenshot alone as a captured network trace.

## Confirmed false-positive condition

A read-only production inspection of a candidate teacher found an exact legacy default permission set:

`view_students`, `manage_attendance`, `manage_grades`, `view_schedule`, `manage_behavior`, `view_reports`.

The previous deletion guard accepted only the current thirteen teacher defaults, so this legacy standard account was classified as having custom permissions. The fix recognizes the exact legacy set in addition to the current defaults. Arbitrary extra grants and partial/custom sets remain blocked.

The candidate's user/profile links and tenant were consistent. The bounded reference inventory found six teaching assignments (cleanup-required), with no shared ownership, duplicate identity, linked generic documents, or mismatching incoming FK actions. This supports the false-positive diagnosis for that candidate, but does not prove it is the account shown in the screenshot.

## Deletion and diagnostic policy

- Eligible exclusive school-teacher accounts are permanently deleted, with historical attribution retained/anonymized under the existing policy.
- Shared identities, ambiguous ownership, foreign-tenant references and unclassified dependencies still block.
- Self-deletion and platform-administrator deletion remain protected; consequently the last active platform administrator cannot be deleted through this route.
- Non-teacher lifecycle behavior is unchanged; this patch does not introduce platform-wide hard deletion for every account type.
- Blocked responses distinguish dependency, configuration, authorization, protection and internal failures. Dependency details contain machine reasons, category, table, count and an actionable resolution—not related users' personal information.
- The confirmation dialog retains these details so administrators can act on them rather than lose them in a toast.
- Cleanup stays within the deletion transaction/savepoint. Failed attempts are recorded after rollback of deletion changes, without copying target names, email addresses or phone numbers.
- Auth checks reload account state; no new role cache is introduced. Successful list deletion forces a fresh list/count fetch; detail-page deletion returns to the list.

## Verification and production boundary

Focused tests cover the legacy allowlist, extra-grant rejection, stale-role authentication, protected accounts, tenant restrictions, dependency diagnostics, historical retention, rollback and frontend error handling.

Production inspection was read-only. No real account was deleted for verification, and the patch was not published by the agent. Production end-to-end success therefore remains unverified until publication and an authorized deletion.