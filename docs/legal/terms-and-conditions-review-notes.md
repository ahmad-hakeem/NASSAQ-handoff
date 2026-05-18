# NASSAQ Terms & Conditions — Legal / Business Review Notes

Companion checklist to `frontend/src/pages/TermsAndConditionsPage.jsx` (route `/terms`, public).
The page is production-ready in **structure, language, and product accuracy**, but the
items below need founder / legal / business sign-off before the document is treated as
binding for any school or end user.

> Baseline jurisdiction: **Kingdom of Saudi Arabia**. The current draft uses balanced
> Arabic SaaS-for-education language, avoids inventing legal facts, and explicitly flags
> commercial / jurisdictional placeholders inside the page wording.

---

## 1. Contracting entity (§1, §17, §25)
- The page refers to the service provider only as "منصة نسّق" (the brand).
- **Action**: Confirm the legal entity name that contracts with schools (e.g.
  full company name, license number / CR, address), and add a "Service Provider"
  identification block at the top once approved. Saudi e-commerce transparency
  expectations call for clear provider identification on commercial digital services.

## 2. Contracting model (§5, §6, §18)
- Current wording assumes:
  - For schools — the **school/institution is the customer**, with authorized users
    (principal/admin/teacher) acting under the school's master account; a separate
    "School Services Agreement / order form" governs commercial terms.
  - For Independent Teachers — the **individual teacher is the customer** and the
    controller for their workspace data.
  - For parents/students — access is **derivative** (invited and authorized by the
    school or the IT workspace), not an independent commercial relationship.
- **Action**: Confirm this allocation business-wise. If parents will ever be billed
  directly, or if NASSAQ ever sells directly to teachers' students, this section must
  be revised.

## 3. Subscription / billing / refunds (§18)
- Current wording is intentionally conservative: "commercial terms are governed by the
  applicable order form / proposal / invoice / separate agreement."
- **Action**: When pricing model is finalized (per-school subscription, per-seat,
  per-student, IT plans, trials, freemium, etc.), draft a concrete commercial annex
  covering: billing cycle, invoicing currency, VAT treatment, late-payment handling,
  refund policy, suspension-for-nonpayment grace period, auto-renewal, and price
  changes. Until then, keep the current neutral wording.

## 4. SLA / availability commitments (§14, §20)
- Current wording promises **no specific uptime**; it uses "as is / as available" plus a
  reasonable best-effort statement.
- **Action**: If/when an enterprise SLA is offered to schools, publish target uptime,
  scheduled-maintenance windows, incident-credit policy, and support response times
  separately (do not embed numbers here without legal sign-off).

## 5. Governing law and dispute resolution (§24)
- Current wording: KSA law, amicable resolution first, then "competent court in KSA",
  with the city/circuit and any arbitration preference explicitly left as
  "[يحدَّد قبل النشر]".
- **Action**: Confirm with counsel whether to:
  (a) name a specific Saudi court (e.g. Riyadh commercial court) for B2C / parent
      disputes, **and/or**
  (b) keep arbitration optional inside the per-school commercial agreement only.

## 6. Privacy linkage (§16)
- Already cross-links to `/privacy` (the unified public Privacy Policy).
- **Action**: Whenever the Privacy Policy version changes materially, re-stamp the
  `LAST_UPDATED` on both pages together and consider re-prompting active users.

## 7. AI features clauses (§13)
- Wording explicitly states: AI outputs are decision-**support**, never sole authority
  for academic / scheduling / assessment / communication decisions; human review is
  required.
- **Action**: Confirm with product/legal whether to add an explicit statement that
  NASSAQ does not allow third-party LLM providers to train on customer data. If so,
  word it conservatively and align with the actual Hakim engine vendor contract.

## 8. Student access rights (§8)
- Wording does **not** grant students self-service editing of academic/behavior
  records, matching the current product model (student portal is read-mostly and
  school/parent-mediated).
- **Action**: If the product ever opens student self-edit (e.g. profile photo, prefs),
  update this section to specify exactly what minors may change.

## 9. Independent Teacher lifecycle (§6, §19)
- Wording aligns with IT §6.8: export → soft-delete → reactivate ≤30d →
  platform-admin hard-delete.
- **Action**: Keep in sync with `docs/it-phase2-reference.md` if the lifecycle policy
  is revised.

## 10. Acceptable Use Policy
- Currently inlined as §10 ("Prohibited Use"). For enterprise sales, it is common to
  split AUP into a separate referenced document.
- **Action**: Decide whether to keep inline or extract into a standalone AUP page later.

## 11. Children & guardian consent
- Wording requires Parent Charter acceptance before parent portal use and forbids
  parents from accessing children outside their documented family relationship.
- **Action**: Make sure the Parent Charter modal text remains version-controlled and
  is re-prompted on material revisions.

## 12. Notices / official communication channel (§25, §26)
- Currently says notices go via in-platform channels or registered email; legal contact
  email is left as "[يحدَّد قبل النشر]".
- **Action**: Publish a dedicated `legal@…` or `contact@…` mailbox; designate the
  official notice address and the SLA for legal correspondence.

## 13. Indemnity & liability cap (§21, §22)
- Liability cap is currently principle-based ("to the extent permitted by law") with
  no monetary cap.
- **Action**: Confirm with counsel whether to add a monetary cap (commonly "fees paid
  in the prior 12 months"). For B2C / parents, do not weaken statutory rights.

## 14. Marketing / promotional communications
- Intentionally **not** mentioned in this draft.
- **Action**: If newsletters or product-marketing emails launch, add a section with
  the legal basis (consent), an unsubscribe path, and align with Privacy Policy.

## 15. Last-updated stamp & version history
- `LAST_UPDATED` in `TermsAndConditionsPage.jsx` is hardcoded ("١٨ مايو ٢٠٢٦").
- **Action**: Bump on every material change. Consider keeping a short revision history
  at the bottom of the page after the first revision.

---

## Where the page lives
- Component: `frontend/src/pages/TermsAndConditionsPage.jsx`
- Route: `/terms` (public, no auth), registered in `frontend/src/routes/appRoutes.js`
- Discoverability across the whole platform:
  - **Public footer** (`frontend/src/components/layout/Footer.jsx`) — "شروط الاستخدام".
  - **Registration consent step** (`frontend/src/pages/RegisterPage.jsx`) — clickable
    "(الشروط والأحكام)" alongside the Privacy link.
  - **Account Settings → "الوثائق القانونية"** (`AccountSettingsPage.jsx`) — visible to
    every authenticated role (principal, teacher, parent, student, IT, platform admin)
    via `ALL_AUTHENTICATED_ROLES`, alongside the Privacy Policy link.
  - **Parent Portal → Settings** (`ParentSettingsPage.jsx`) — "الشروط والأحكام" row now
    navigates to `/terms`.
  - Legacy `/parent/legal/terms` URL now `<Navigate replace>`s to `/terms` so any
    bookmark or in-app deep link keeps working.

## Out of scope of this page
- Privacy Policy (lives at `/privacy`, with its own legal review notes file).
- Per-school Data Processing Addendum / order form / pricing annex (separate
  commercial documents, signed with each school).
- Acceptable Use Policy as a standalone document (currently inlined as §10).
- Sub-processors register (operational document referenced from the Privacy Policy).
