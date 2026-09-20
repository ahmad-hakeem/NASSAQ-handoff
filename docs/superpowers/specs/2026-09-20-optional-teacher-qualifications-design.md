# Optional Teacher Qualifications Design

## Objective

Allow school principals to create and edit teachers without supplying an academic
degree, years of experience, or job rank. Values remain validated when supplied.
All identity, authentication, role, school-association, and duplicate-account
validation remains unchanged.

## User Experience

In the Add New Teacher wizard's Qualifications step:

- `الدرجة العلمية`, `سنوات الخبرة`, and `الرتبة الوظيفية` have no required
  asterisk.
- The principal can continue when any or all three fields are blank.
- An explicitly entered experience value of `0` is valid and distinct from a
  blank field.
- Invalid supplied values produce field-level errors and prevent continuing.
- The review step displays the supplied value, or `غير مضاف` when absent.

The existing teacher professional-information editor follows the same rules:
optional values may be added later or cleared.

## Data Contract and Normalization

The frontend sends absent qualification values as JSON `null` or omits them.
It must not coerce blank experience to `0`.

The backend accepts each optional field when it is:

- omitted;
- `null`; or
- a blank string.

Blank strings are normalized to `null`. Persisted absence therefore has one
representation: SQL `NULL`. An explicit numeric `0` for years of experience is
preserved.

When present:

- academic degree must match a supported degree option;
- job rank must match a supported rank option;
- years of experience must be an integer greater than or equal to zero.

Malformed supplied values return clear validation errors and are not persisted.

## Frontend Changes

Update the teacher wizard to:

- remove required-label rendering for the three fields;
- remove degree and rank from required step-completion checks;
- preserve an empty experience input as `null`;
- validate only non-empty values;
- render `غير مضاف` for absent values on the review step; and
- submit a normalized qualifications payload.

Update the professional-information editor only where necessary to support
clearing existing values and to use the same optional-value rules.

## Backend Changes

Use one shared normalization and validation rule at the teacher create/update
boundary:

- optional input becomes `None`;
- blank strings become `None`;
- present degree/rank values are checked against supported values;
- present experience is parsed as an integer and checked as non-negative.

The create route and the professional-information update route must both apply
the contract. Update logic must distinguish omitted fields ("leave unchanged")
from explicit `null` or blank fields ("clear this value").

No unrelated teacher fields become optional.

## Persistence Review

The existing teacher qualification, rank, and experience columns are nullable,
so no database migration is expected. Implementation must verify the current
schema and avoid introducing defaults that convert missing experience to zero.

## Error Handling

Validation errors are attached to the relevant field in the frontend. Backend
validation rejects unsupported option values, negative experience, non-integer
experience, and malformed input. Submission failures use the wizard's existing
error handling.

## Verification

Automated tests will cover:

1. All three qualification fields blank.
2. Degree only, experience only, rank only, degree plus experience, and all
   fields populated.
3. Explicit experience `0`.
4. Negative and non-numeric experience.
5. Unsupported degree and rank values.
6. Editing a teacher to add values, leave values unchanged, and clear values.
7. Review-step placeholders for absent values.
8. Existing required identity and school fields remain enforced.
9. Duplicate National ID and mobile protections remain active.
10. Created teachers still appear correctly in user management.

## Scope

This change is limited to qualification optionality and its create/edit/review
contracts. It does not alter authentication, teacher identity, role assignment,
school tenancy, or unrelated wizard steps.