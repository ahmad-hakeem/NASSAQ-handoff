import { Zap } from 'lucide-react';
import { useTranslation } from '../../contexts/ThemeContext';

export default function FollowupGradesTable({
  students = [],
  columns = [],
  gradesData = {},
  streakBonus = {},
  onGradeChange,
  onStudentClick,
  emptyMessage,
  t: tProp,
}) {
  const { t: tHook } = useTranslation();
  const t = tProp || tHook;

  // Full-row click opens the student profile, but interactive controls inside
  // the row (the grade number inputs) must keep working — so a click that
  // originates from a form control / button is ignored here.
  const handleRowClick = (student) => (e) => {
    if (!onStudentClick) return;
    if (e.target.closest('input, button, a, select, textarea, [role="button"], [contenteditable="true"]')) return;
    onStudentClick(student);
  };

  const visibleColumns = columns.filter(c => !c.hidden);
  const courseworkCols = visibleColumns.filter(c => c.group === 'coursework');
  const examCols = visibleColumns.filter(c => c.group === 'exams');

  const sumFor = (studentData, cols) =>
    cols.reduce((sum, col) => sum + (Number(studentData[col.id]) || 0), 0);
  const maxSum = (cols) =>
    cols.reduce((sum, col) => sum + (Number(col.maxGrade) || 0), 0);

  const courseworkMax = maxSum(courseworkCols);
  const examMax = maxSum(examCols);
  const grandMax = courseworkMax + examMax;

  const renderGroupedHeader = () => (
    <thead className="sticky top-0 z-10 bg-muted dark:bg-card">
      <tr>
        <th rowSpan={2} className="border px-2 py-2 text-center font-cairo font-bold text-xs sticky end-0 bg-muted dark:bg-card w-12">#</th>
        <th rowSpan={2} className="border px-3 py-2 text-start font-cairo font-bold text-xs sticky end-12 bg-muted dark:bg-card min-w-[160px]">{t('studentName') || 'اسم الطالب'}</th>
        {courseworkCols.length > 0 && (
          <th colSpan={courseworkCols.length + 1} className="border px-3 py-2 text-center font-cairo font-bold text-xs bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">
            أعمال سنة
          </th>
        )}
        {examCols.length > 0 && (
          <th colSpan={examCols.length + 1} className="border px-3 py-2 text-center font-cairo font-bold text-xs bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300">
            اختبارات
          </th>
        )}
        <th rowSpan={2} className="border px-3 py-2 text-center font-cairo font-bold text-xs bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 min-w-[80px]">
          <div>الكلي</div>
          <div className="text-[10px] font-normal opacity-70">/{grandMax}</div>
        </th>
      </tr>
      <tr>
        {courseworkCols.map(col => (
          <th key={col.id} className="border px-2 py-2 text-center font-cairo font-bold text-[11px] min-w-[90px]">
            <div className="truncate">{col.name}</div>
            <div className="text-[10px] text-muted-foreground font-normal">/{col.maxGrade}</div>
          </th>
        ))}
        {courseworkCols.length > 0 && (
          <th className="border px-2 py-2 text-center font-cairo font-bold text-[11px] bg-blue-50/60 dark:bg-blue-900/20 min-w-[80px]">
            <div>المجموع</div>
            <div className="text-[10px] text-muted-foreground font-normal">/{courseworkMax}</div>
          </th>
        )}
        {examCols.map(col => (
          <th key={col.id} className="border px-2 py-2 text-center font-cairo font-bold text-[11px] min-w-[90px]">
            <div className="truncate">{col.name}</div>
            <div className="text-[10px] text-muted-foreground font-normal">/{col.maxGrade}</div>
          </th>
        ))}
        {examCols.length > 0 && (
          <th className="border px-2 py-2 text-center font-cairo font-bold text-[11px] bg-amber-50/60 dark:bg-amber-900/20 min-w-[80px]">
            <div>المجموع</div>
            <div className="text-[10px] text-muted-foreground font-normal">/{examMax}</div>
          </th>
        )}
      </tr>
    </thead>
  );

  const renderGradeCell = (student, col) => {
    const studentData = gradesData[student.id] || {};
    const value = studentData[col.id] ?? '';
    return (
      <td key={col.id} className="border px-1 py-1.5">
        <input
          type="number"
          inputMode="numeric"
          value={value}
          onChange={e => {
            const raw = e.target.value;
            if (raw === '') {
              onGradeChange?.(student.id, col.id, '');
              return;
            }
            const v = Math.max(0, Math.min(parseInt(raw) || 0, col.maxGrade));
            onGradeChange?.(student.id, col.id, v);
          }}
          className="w-12 h-8 mx-auto block text-center text-xs font-medium bg-card dark:bg-muted outline-none border border-border dark:border-border rounded-full focus:border-brand-turquoise focus:ring-2 focus:ring-brand-turquoise/30 transition"
          min={0}
          max={col.maxGrade}
          placeholder="0"
          disabled={!onGradeChange}
        />
      </td>
    );
  };

  return (
    <div className="overflow-auto">
      <table className="text-sm border-collapse w-max min-w-full">
        {renderGroupedHeader()}
        <tbody>
          {students.map((student, si) => {
            const studentData = gradesData[student.id] || {};
            const cwSum = sumFor(studentData, courseworkCols);
            const exSum = sumFor(studentData, examCols);
            const total = cwSum + exSum;
            const ratio = grandMax > 0 ? total / grandMax : 0;
            const totalColor = ratio >= 0.6 ? 'text-emerald-600' : ratio >= 0.3 ? 'text-amber-600' : 'text-red-500';
            return (
              <tr
                key={student.id}
                className={`hover:bg-muted/40 dark:hover:bg-card/40 ${onStudentClick ? 'cursor-pointer' : ''}`}
                onClick={onStudentClick ? handleRowClick(student) : undefined}
              >
                <td className="border px-2 py-1.5 text-center text-[11px] text-muted-foreground sticky end-0 bg-card dark:bg-background">{si + 1}</td>
                <td className="border px-3 py-1.5 text-xs font-medium sticky end-12 bg-card dark:bg-background">
                  <div className="flex items-center gap-1.5">
                    {onStudentClick ? (
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); onStudentClick(student); }}
                        title={t('viewStudentProfile') || 'عرض ملف الطالب'}
                        className="text-start text-brand-turquoise hover:underline font-medium rounded outline-none focus-visible:ring-2 focus-visible:ring-brand-turquoise/40"
                      >
                        {student.full_name}
                      </button>
                    ) : (
                      student.full_name
                    )}
                    {(() => {
                      const sb = streakBonus[student.id];
                      const pts = Number(sb?.points) || 0;
                      if (pts <= 0) return null;
                      const label = `${t('streakBonus') || 'مكافأة تتابع'} +${pts}`;
                      return (
                        <span
                          title={label}
                          className="inline-flex items-center gap-0.5 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 px-1.5 py-0.5 text-[10px] font-bold whitespace-nowrap"
                        >
                          <Zap className="w-3 h-3" strokeWidth={1.5} aria-hidden="true" />
                          +{pts}
                        </span>
                      );
                    })()}
                  </div>
                </td>
                {courseworkCols.map(col => renderGradeCell(student, col))}
                {courseworkCols.length > 0 && (
                  <td className="border px-2 py-1.5 text-center text-xs font-bold bg-blue-50/40 dark:bg-blue-900/10">
                    {cwSum}
                  </td>
                )}
                {examCols.map(col => renderGradeCell(student, col))}
                {examCols.length > 0 && (
                  <td className="border px-2 py-1.5 text-center text-xs font-bold bg-amber-50/40 dark:bg-amber-900/10">
                    {exSum}
                  </td>
                )}
                <td className={`border px-2 py-1.5 text-center text-sm font-bold bg-emerald-50/40 dark:bg-emerald-900/10 ${totalColor}`}>
                  {total}
                </td>
              </tr>
            );
          })}
          {students.length === 0 && (
            <tr><td colSpan={visibleColumns.length + 4} className="text-center text-sm text-muted-foreground py-8">{emptyMessage || (t('noStudents') || 'لا يوجد طلاب')}</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
