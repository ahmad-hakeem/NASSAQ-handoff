#!/usr/bin/env bash
# SECURITY (audit C-3 / Phase 1): grep gate that fails any NEW
# `gd_find_one(... {"id": ...})` lookup against a tenant-owned table that does
# not include a tenant filter. Tenant-owned `GET /{id}` lookups MUST go through
# `utils.tenant_scope.tenant_scoped_find_one` (or include an explicit
# tenant_id/school_id filter at the call site).
#
# A baseline of currently-known unscoped lookups is checked into
# `scripts/tenant_lookup_baseline.txt`. The audit-recommended fix is to
# migrate them table-by-table in follow-up tasks; this gate's job is to
# prevent new ones from sneaking in.
#
# Usage:
#   bash scripts/check_tenant_scoped_lookups.sh           # check
#   bash scripts/check_tenant_scoped_lookups.sh --update  # regenerate baseline
#
# Exits 0 when no new violations, 1 when new violations are found.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BASELINE="scripts/tenant_lookup_baseline.txt"

# Tables we consider tenant-owned. Keep in sync with
# backend/utils/tenant_scope.py::_TENANT_OWNED_TABLES.
TENANT_TABLES=(
  "academic_years"
  "terms"
  "academic_terms"
  "grade_levels"
  "educational_stages"
  "physical_classrooms"
  "assessments"
  "assessment_submissions"
  "student_grades"
  "behaviour_records"
  "attendance"
  "classes"
  "subjects"
  "teachers"
  "students"
  "parents"
  "teacher_assignments"
  "teacher_class_assignments"
  "timetables"
  "timetable_runs"
  "schedule_sessions"
  "time_slots"
  "timetable_constraints"
  "calendar_events"
  "events"
  "messages"
  "notifications"
  "approval_requests"
  "school_settings"
  "registration_requests"
  "guardian_links"
  "user_relationships"
)

scan() {
  for table in "${TENANT_TABLES[@]}"; do
    # gd_find_one(... "<table>", { ... "id": ... })
    rg -n --no-heading -t py \
        "gd_find_one\([^,]+,\s*\"${table}\"\s*,\s*\{[^}]*\"id\"[^}]*\}\)" \
        backend/routes 2>/dev/null \
      | rg -v "school_id|tenant_id" \
      | sed "s|^|${table}\t|" || true
    # gd_find(... "<table>", { ... }) — bulk reads against tenant-owned tables
    # must also pin school_id/tenant_id, otherwise they leak cross-tenant rows.
    rg -n --no-heading -t py \
        "\bgd_find\([^,]+,\s*\"${table}\"\s*," \
        backend/routes 2>/dev/null \
      | rg -v "school_id|tenant_id" \
      | sed "s|^|${table}\t|" || true
  done | sort
}

CURRENT="$(scan)"

if [[ "${1:-}" == "--update" ]]; then
  printf '%s\n' "$CURRENT" > "$BASELINE"
  echo "Baseline regenerated at $BASELINE ($(wc -l < "$BASELINE") entries)"
  exit 0
fi

if [[ ! -f "$BASELINE" ]]; then
  echo "❌ Baseline missing: $BASELINE"
  echo "Run: bash scripts/check_tenant_scoped_lookups.sh --update"
  exit 1
fi

# Strip line numbers before diffing so unrelated edits in the same file don't
# spuriously trigger the gate; only the (table, file, matched-call) tuple
# matters for newness.
strip_linenos() {
  sed -E 's/:[0-9]+:/:/'
}

NEW="$(diff <(printf '%s\n' "$CURRENT" | strip_linenos | sort -u) \
            <(strip_linenos < "$BASELINE" | sort -u) \
        | grep -E '^<' | sed 's/^< //' || true)"

if [[ -n "$NEW" ]]; then
  echo "❌ New unscoped tenant lookups detected (not in baseline):"
  echo "$NEW"
  echo ""
  echo "Tenant-owned tables MUST be looked up through"
  echo "  utils.tenant_scope.tenant_scoped_find_one"
  echo "or with an explicit school_id/tenant_id filter on the same call."
  echo "See docs/security/PHASE1_REPORT.md and finding C-3 in"
  echo "docs/security/SECURITY_AUDIT_2026-05-11.md."
  echo ""
  echo "If a new entry is intentional and explicitly scoped some other way,"
  echo "regenerate the baseline:"
  echo "  bash scripts/check_tenant_scoped_lookups.sh --update"
  exit 1
fi

echo "✅ Tenant-scoped lookup audit clean (no new violations)."
