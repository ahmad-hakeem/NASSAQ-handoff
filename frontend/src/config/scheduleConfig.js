// frontend/src/config/scheduleConfig.js
//
// Master-grid request-window configuration.
//
// MASTER_GRID_TEACHER_WINDOW represents "a large realistic single-school
// teacher window" — the number of teacher rows the master timetable
// requests in a single payload so every teacher in any realistic single
// school is rendered in one paint. It is NOT a pagination page size;
// the page no longer exposes a pager UI (see Task 3). The underlying
// backend `teacher_page` / `teacher_page_size` contract from Task #142
// is preserved exactly — only the UI affordance is removed.
//
// If a deployment ever exceeds this value, the no-silent-truncation
// fallback (see Task 9) surfaces a NassaqAlertDialog notice; the
// constant can then be bumped, or virtualization introduced as a
// follow-up. Do not inline this literal anywhere else; import it.

export const MASTER_GRID_TEACHER_WINDOW = 200;
