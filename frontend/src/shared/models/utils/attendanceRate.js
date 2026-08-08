export function computeAttendanceRate(summary) {
  if (!summary) return null;
  // The backend /attendance/summary/student/{id} endpoint is authoritative and
  // already returns attendance_rate (present / total, late excluded). Mirror it
  // exactly rather than inventing our own semantics.
  if (summary.attendance_rate != null) return Math.round(summary.attendance_rate);
  // Fallback only for legacy/partial shapes that omit the computed rate.
  const present = summary.present_days ?? summary.present_count ?? summary.present ?? 0;
  const late = summary.late_days ?? summary.late_count ?? 0;
  const absent = summary.absent_days ?? summary.absent_count ?? 0;
  const excused = summary.excused_days ?? summary.excused_count ?? 0;
  const total = summary.total_days ?? summary.total ?? (present + late + absent + excused);
  return total > 0 ? Math.round((present / total) * 100) : 0;
}
