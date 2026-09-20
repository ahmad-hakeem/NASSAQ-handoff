# Teacher Birth Calendars Implementation Plan

**Approved design:** Gregorian input with calculated Saudi Umm al-Qura Hijri display.

**Storage:** Preserve the existing nullable teacher date_of_birth column; new writes
use Gregorian YYYY-MM-DD only. No Hijri column, migration, age restriction, or
backfill. Blank clears, omitted updates preserve. Reject invalid/future dates.

**Conversion:** Reuse the installed hijri-converter table-based library, not Intl
or manual arithmetic. Derive Hijri on the frontend from canonical API dates;
the backend does not run a competing conversion. Explicitly report unsupported
conversion dates while preserving valid Gregorian dates and existing records.

## Backend
- Add failing tests for strict ISO Gregorian validation, impossible/leap/future
  dates, null/blank normalization, omitted edit preservation and explicit clear.
- Implement a shared date-only validator at teacher create and edit boundaries;
  audit other teacher write paths and consumers without changing identity/tenant rules.
- Run focused birth-date and existing teacher create/restore/profile suites.

## Frontend
- Add failing utility and component tests for deterministic conversion, range,
  blank/invalid/future values, wizard review and profile editing.
- Add a shared teacher birth-date field/display with labelled Gregorian input
  and read-only Hijri equivalent; use it in wizard and principal profile.
- Preserve Gregorian-only payloads and null semantics; localize all new messages.
- Audit teacher birth-date consumers and label any exposed calendar values.
- Run focused tests via craco test and production build.

## Verification
- Review combined changes against the attached specification.
- Restart backend and frontend once, inspect logs and preview.
- Report exact supported range, test evidence, and limits of environment checks.