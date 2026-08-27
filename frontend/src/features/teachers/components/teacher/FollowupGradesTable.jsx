import { Zap } from 'lucide-react';
import { useTranslation } from '@/shared/contexts/ThemeContext';

export default function FollowupGradesTable({
  students = [],
  columns = [],
  gradesData = {},
  streakBonus = {},
  showStreakColumn = false,
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

  // Only numeric (درجة) columns participate in totals — check (تحقق) and
  // text (نص) column values are statuses/notes, not scores.
  const isScorable = (col) => !col.type || col.type === 'grade';
  const sumFor = (studentData, cols) =>
    cols.reduce((sum, col) => sum + (isScorable(col) ? (Number(studentData[col.id]) || 0) : 0), 0);
  const maxSum = (cols) =>
    cols.reduce((sum, col) => sum + (isScorable(col) ? (Number(col.maxGrade) || 0) : 0), 0);

  const courseworkMax = maxSum(courseworkCols);
  const examMax = maxSum(examCols);
  const grandMax = courseworkMax + examMax;

  const getColumnDisplayName = (col) => {
    if (!col) return '';
    const standardNames = {
      participation: t('participation') || 'المشاركة',
      homework: t('homework') || 'الواجبات',
      performance_task: t('performanceTasks') || 'المهام الأدائية',
      short_test: t('shortQuiz') || t('shortTest') || 'اختبار قصير',
      final_test: t('periodFinalExam') || t('finalExam') || 'اختبار نهاية الفترة',
      'المشاركة': t('participation') || 'المشاركة',
      'الواجبات': t('homework') || 'الواجبات',
      'المهام الأدائية': t('performanceTasks') || 'المهام الأدائية',
      'الاختبار القصير': t('shortQuiz') || t('shortTest') || 'اختبار قصير',
      'اختبار قصير': t('shortQuiz') || t('shortTest') || 'اختبار قصير',
      'اختبار نهاية الفترة': t('periodFinalExam') || t('finalExam') || 'اختبار نهاية الفترة',
      'عمود جديد': t('newColumn') || 'عمود جديد',
    };
    return standardNames[col.id] || standardNames[col.name] || col.name;
  };

  const renderGroupedHeader = () => (
    <thead className="sticky top-0 z-20 bg-muted dark:bg-card">
      <tr>
        <th rowSpan={2} className="border px-2 py-2 text-center font-cairo font-bold text-xs sticky start-0 z-20 bg-muted dark:bg-card w-12">#</th>
        <th rowSpan={2} className="border px-3 py-2 text-start font-cairo font-bold text-xs sticky start-12 z-20 bg-muted dark:bg-card min-w-[160px] max-w-[220px]">
          <bdi dir="auto">{t('studentName') || 'اسم الطالب'}</bdi>
        </th>
        {showStreakColumn && (
          <th rowSpan={2} className="border px-2 py-2 text-center font-cairo font-bold text-[11px] bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 min-w-[90px]">
            <div className="flex items-center justify-center gap-1">
              <Zap className="w-3.5 h-3.5" strokeWidth={1.5} aria-hidden="true" />
              <bdi dir="auto">{t('excellenceScore') || 'درجات التميز'}</bdi>
            </div>
          </th>
        )}
        {courseworkCols.length > 0 && (
          <th colSpan={courseworkCols.length + 1} className="border px-3 py-2 text-center font-cairo font-bold text-xs bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">
            <bdi dir="auto">{t('coursework') || 'أعمال سنة'}</bdi>
          </th>
        )}
        {examCols.length > 0 && (
          <th colSpan={examCols.length + 1} className="border px-3 py-2 text-center font-cairo font-bold text-xs bg-amber-50 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300">
            <bdi dir="auto">{t('exams') || 'اختبارات'}</bdi>
          </th>
        )}
        <th rowSpan={2} className="border px-3 py-2 text-center font-cairo font-bold text-xs bg-emerald-50 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300 min-w-[80px]">
          <bdi dir="auto">{t('total') || 'الكلي'}</bdi>
          <div className="text-[10px] font-normal opacity-70 tabular-nums" dir="ltr">/{grandMax}</div>
        </th>
      </tr>
      <tr>
        {courseworkCols.map(col => (
          <th key={col.id} className="border px-2 py-2 text-center font-cairo font-bold text-[11px] min-w-[90px]">
            <bdi dir="auto" className="truncate block">{getColumnDisplayName(col)}</bdi>
            <div className="text-[10px] text-muted-foreground font-normal tabular-nums">
              {isScorable(col) ? <span dir="ltr">/{col.maxGrade}</span> : (col.type === 'check' ? (t('checkType') || 'تحقق') : (t('textType') || 'نص'))}
            </div>
          </th>
        ))}
        {courseworkCols.length > 0 && (
          <th className="border px-2 py-2 text-center font-cairo font-bold text-[11px] bg-blue-50/60 dark:bg-blue-900/20 min-w-[80px]">
            <bdi dir="auto">{t('sum') || 'المجموع'}</bdi>
            <div className="text-[10px] text-muted-foreground font-normal tabular-nums" dir="ltr">/{courseworkMax}</div>
          </th>
        )}
        {examCols.map(col => (
          <th key={col.id} className="border px-2 py-2 text-center font-cairo font-bold text-[11px] min-w-[90px]">
            <bdi dir="auto" className="truncate block">{getColumnDisplayName(col)}</bdi>
            <div className="text-[10px] text-muted-foreground font-normal tabular-nums">
              {isScorable(col) ? <span dir="ltr">/{col.maxGrade}</span> : (col.type === 'check' ? (t('checkType') || 'تحقق') : (t('textType') || 'نص'))}
            </div>
          </th>
        ))}
        {examCols.length > 0 && (
          <th className="border px-2 py-2 text-center font-cairo font-bold text-[11px] bg-amber-50/60 dark:bg-amber-900/20 min-w-[80px]">
            <bdi dir="auto">{t('sum') || 'المجموع'}</bdi>
            <div className="text-[10px] text-muted-foreground font-normal tabular-nums" dir="ltr">/{examMax}</div>
          </th>
        )}
      </tr>
    </thead>
  );

  const renderGradeCell = (student, col) => {
    const studentData = gradesData[student.id] || {};
    const value = studentData[col.id] ?? '';
    // تحقق — binary checkbox. Stored as 1 when checked; unchecked clears the
    // cell (empty = no value), so it never masquerades as a numeric score.
    if (col.type === 'check') {
      const checked = value !== '' && value !== 0 && value !== '0' && Boolean(value);
      return (
        <td key={col.id} className="border px-1 py-1.5 text-center">
          <input
            type="checkbox"
            checked={checked}
            onChange={e => onGradeChange?.(student.id, col.id, e.target.checked ? 1 : '')}
            className="h-4 w-4 mx-auto block accent-brand-turquoise cursor-pointer disabled:cursor-not-allowed"
            aria-label={`${col.name} — ${student.full_name}`}
            disabled={!onGradeChange}
          />
        </td>
      );
    }
    // نص — free text, never coerced to a number.
    if (col.type === 'text') {
      return (
        <td key={col.id} className="border px-1 py-1.5">
          <input
            type="text"
            dir="auto"
            value={value === 0 ? '' : String(value)}
            onChange={e => onGradeChange?.(student.id, col.id, e.target.value)}
            maxLength={120}
            className="w-24 h-8 mx-auto block text-center text-xs font-cairo bg-card dark:bg-muted outline-none border border-border dark:border-border rounded-full focus:border-brand-turquoise focus:ring-2 focus:ring-brand-turquoise/30 transition"
            aria-label={`${col.name} — ${student.full_name}`}
            disabled={!onGradeChange}
          />
        </td>
      );
    }
    return (
      <td key={col.id} className="border px-1 py-1.5">
        <input
          type="number"
          dir="ltr"
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
          className="w-12 h-8 mx-auto block text-center text-xs font-medium tabular-nums bg-card dark:bg-muted outline-none border border-border dark:border-border rounded-full focus:border-brand-turquoise focus:ring-2 focus:ring-brand-turquoise/30 transition"
          min={0}
          max={col.maxGrade}
          placeholder="0"
          disabled={!onGradeChange}
        />
      </td>
    );
  };

  return (
    <div className="overflow-auto" dir="inherit">
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
                <td className="border px-2 py-1.5 text-center text-[11px] text-muted-foreground sticky start-0 z-10 bg-card dark:bg-background tabular-nums">{si + 1}</td>
                <td className="border px-3 py-1.5 text-xs font-medium sticky start-12 z-10 bg-card dark:bg-background min-w-[160px] max-w-[220px]">
                  <bdi dir="auto" className="block truncate">
                    {onStudentClick ? (
                      <button
                        type="button"
                        onClick={(e) => { e.stopPropagation(); onStudentClick(student); }}
                        title={t('viewStudentProfile') || 'عرض ملف الطالب'}
                        className="text-start text-brand-turquoise hover:underline font-medium rounded outline-none focus-visible:ring-2 focus-visible:ring-brand-turquoise/40 truncate block w-full"
                      >
                        <bdi dir="auto">{student.full_name}</bdi>
                      </button>
                    ) : (
                      <bdi dir="auto">{student.full_name}</bdi>
                    )}
                  </bdi>
                </td>
                {showStreakColumn && (() => {
                  const pts = Number(streakBonus[student.id]?.points) || 0;
                  return (
                    <td className="border px-2 py-1.5 text-center bg-amber-50/40 dark:bg-amber-900/10">
                      {pts > 0 ? (
                        <span
                          title={`${t('streakBonus') || 'مكافأة التميز'} +${pts}`}
                          className="inline-flex items-center gap-0.5 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 px-1.5 py-0.5 text-[11px] font-bold whitespace-nowrap tabular-nums"
                          dir="ltr"
                        >
                          <Zap className="w-3 h-3" strokeWidth={1.5} aria-hidden="true" />
                          +{pts}
                        </span>
                      ) : (
                        <span className="text-[11px] text-muted-foreground tabular-nums">0</span>
                      )}
                    </td>
                  );
                })()}
                {courseworkCols.map(col => renderGradeCell(student, col))}
                {courseworkCols.length > 0 && (
                  <td className="border px-2 py-1.5 text-center text-xs font-bold bg-blue-50/40 dark:bg-blue-900/10 tabular-nums" dir="ltr">
                    {cwSum}
                  </td>
                )}
                {examCols.map(col => renderGradeCell(student, col))}
                {examCols.length > 0 && (
                  <td className="border px-2 py-1.5 text-center text-xs font-bold bg-amber-50/40 dark:bg-amber-900/10 tabular-nums" dir="ltr">
                    {exSum}
                  </td>
                )}
                <td className={`border px-2 py-1.5 text-center text-sm font-bold bg-emerald-50/40 dark:bg-emerald-900/10 tabular-nums ${totalColor}`} dir="ltr">
                  {total}
                </td>
              </tr>
            );
          })}
          {students.length === 0 && (
            <tr><td colSpan={visibleColumns.length + 4 + (showStreakColumn ? 1 : 0)} className="text-center text-sm text-muted-foreground py-8">{emptyMessage || (t('noStudents') || 'لا يوجد طلاب')}</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
