# NASSAQ Privacy Policy — Legal Review Notes

Companion checklist to `frontend/src/pages/PrivacyPolicyPage.jsx` (route `/privacy`, public).
This file lists every clause in the published Arabic policy that still needs business or
legal confirmation before the policy is treated as a final binding document. The page is
production-ready in terms of **structure, language, and product accuracy**, but the
items below must be resolved with founders / counsel before public release.

> Baseline law cited: **Saudi PDPL + implementing regulations** (primary). COPPA / FERPA
> are referenced **only as drafting benchmarks** for child/education-record language;
> the policy does **not** claim automatic compliance with non-Saudi laws.

---

## 1. Controller / Processor role (§3 — "أدوارنا في معالجة البيانات")
- Current wording: "in most cases the school is the controller and NASSAQ is the processor;
  for platform-level features (account security, MFA, audit logs, monitoring) NASSAQ acts as
  an independent controller; independent teachers act as controller for their own workspace."
- **Action**: Confirm this position contractually. Make sure the standard School Services
  Agreement (and the Independent Teacher ToS) explicitly designates the
  controller/processor split and incorporates a Data Processing Addendum (DPA).

## 2. Hosting location and international transfers (§11)
- Current wording: "we strive to host data inside KSA; when sub-processors process data
  abroad we apply safeguards under PDPL." Hosting location is left as a placeholder.
- **Action**: Confirm actual primary hosting region (Replit production region, any
  managed Postgres location, any object storage region). If any sub-processor is outside
  KSA, document the transfer mechanism (adequacy / contractual safeguards / approval).

## 3. Sub-processors list
- The policy intentionally does **not** name sub-processors.
- **Action**: Maintain a separate sub-processors register (hosting, database, email
  delivery provider, AI/LLM provider for the Hakim engine, monitoring/log aggregation,
  bulk-import providers if any). Decide whether to publish it as an appendix, link to it
  from the policy, or hold it as an enterprise document available on request.

## 4. Retention periods (§12)
- Current wording is principle-based ("only as long as necessary…") with a note on the
  Independent Teacher workspace lifecycle (export → soft-delete → reactivate ≤30d →
  hard-delete by platform admin).
- **Action**: Once retention schedules are formally approved (per data category: account,
  attendance, grades, behaviour, audit logs, AI insights, Noor import artefacts,
  email/notification logs), back-fill concrete maximum periods.

## 5. Cookies / analytics inventory (§14)
- Current wording: "essential cookies for session/auth/preferences; possibly internal
  measurement tools." No external analytics named.
- **Action**: Run a cookie audit on production. If GA, Hotjar, Sentry, PostHog, or any
  similar third-party SDK is loaded, list them with purpose + retention + vendor +
  transfer mechanism, and add a cookie banner / preference centre if PDPL or any
  applicable regulation requires opt-in for non-essential cookies.

## 6. AI features and automated decision-making (§9)
- Current wording: AI features are educational decision-support, not solely automated
  legally-significant decisions; pseudonymisation is applied "where possible"; human
  review channel is offered.
- **Action**: Confirm the LLM provider, whether prompt content leaves KSA, and whether a
  Data Processing Agreement is in place with that provider. Decide a public statement on
  model training (e.g. "your data is **not** used to train third-party general-purpose
  models") and add it if confirmed.

## 7. Privacy contact channel (§19)
- Placeholder: "[يحدَّد قبل النشر]" for the dedicated privacy email.
- **Action**: Publish a dedicated mailbox (e.g. `privacy@nassaqapp.com`) and SLA for
  response (PDPL allows up to 30 days; pick a target). Designate an internal
  Data Protection Officer / point of contact and document the escalation path.

## 8. Complaint authority (§17)
- Current wording: refers to "the competent authority for personal data protection in KSA".
- **Action**: When SDAIA's complaint channel for PDPL is formally operative, name it and
  link the official portal. Until then, keep the generic reference.

## 9. Children / student data (§7)
- Current wording: handles student data in educational context coordinated with the school
  and/or guardian; explicit reference to the Parent Charter blocking modal as the consent
  gateway; no direct minor sign-up.
- **Action**: Confirm with the product team that no path lets a minor self-register
  without school/guardian mediation (audit `RegisterPage`, parent-invitation accept,
  student portal first-login). If the school can grant a minor direct portal access,
  decide whether that requires explicit recorded guardian consent and update the policy
  + product to match.

## 10. Parent Charter wording (referenced from §7 and §8)
- The policy references the Parent Charter as the binding pre-portal acceptance step.
- **Action**: Treat the Arabic text inside `ParentCharterModal.jsx` as a legal artefact
  too — keep it under version control with a "charter version" column if it ever needs
  to be revised; re-prompt parents on material updates.

## 11. Data-subject rights workflow (§16)
- Current wording: users can self-serve some rights (name/email/phone/password/notification
  preferences) and the rest are fulfilled by support request.
- **Action**: When a self-service "export my data" or "delete my account" workflow is
  shipped for non-IT users, update this section. Until then, keep the manual-channel
  language. Confirm the SLA we commit to in writing.

## 12. Marketing / non-essential communications
- The policy intentionally does **not** mention marketing emails.
- **Action**: If marketing channels (newsletter, product announcements) are launched,
  add a section explaining the legal basis (consent), and ensure an unsubscribe path is
  shipped before publishing that section.

## 13. Independent-teacher tenant clarifications
- Current wording: "when a teacher operates without a school, the teacher is the
  controller for their students' and parents' data; NASSAQ acts as processor."
- **Action**: Make sure the Independent Teacher ToS reflects this allocation and that
  the in-app onboarding surfaces it. Confirm the lifecycle wording in §12 matches the
  documented IT §6.8 (export → soft-delete → reactivate ≤30d → platform-admin
  hard-delete) — it currently does.

## 14. Public landing/footer wiring
- The Footer link `t('privacyPolicy')` now points to `/privacy`.
- The `t('termsOfService')` link is still `href="#"`. Once the Terms of Service draft is
  approved, register an analogous public route (`/terms`) and wire the footer link.
  Also revisit `RegisterPage` (`acceptPrivacy` / `iAgreeToThePrivacyPolicyAndTermsOfUse`)
  to ensure both links point at the published documents at registration time.

## 15. Last-updated stamp
- `LAST_UPDATED` in `PrivacyPolicyPage.jsx` is hardcoded.
- **Action**: Update on every material revision and consider keeping a short version
  history at the bottom of the page once the second revision lands.

---

## Where the page lives
- Component: `frontend/src/pages/PrivacyPolicyPage.jsx`
- Route: `/privacy` (public, no auth), registered in `frontend/src/routes/appRoutes.js`
- Discoverability:
  - Linked from the main Footer (`frontend/src/components/layout/Footer.jsx`).
  - Should also be linked from `RegisterPage` consent label (action item #14).
  - The platform-admin-published per-tenant addenda continue to flow through the
    existing `LegalDocumentPage` (`/parent/legal/:docType`) — that surface is **not**
    replaced by this page; it serves as the public canonical policy while
    `LegalDocumentPage` shows school-customised supplements.

## Out of scope of this page
- Terms of Service.
- Cookie Preference Centre / consent banner.
- Per-school Data Processing Addendum / per-IT Workspace Agreement (contractual, not
  public policy).
- Sub-processors register (operational document).
