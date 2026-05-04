import './_group.css';
import { Lock, RefreshCw, AlertTriangle, Filter, Pencil } from 'lucide-react';

const DAYS = [
  { key: 'sun', label: 'الأحد' },
  { key: 'mon', label: 'الاثنين' },
  { key: 'tue', label: 'الثلاثاء' },
  { key: 'wed', label: 'الأربعاء' },
  { key: 'thu', label: 'الخميس' },
] as const;

const PERIODS = [1, 2, 3, 4, 5, 6, 7];
const AR_DIGIT: Record<number, string> = { 1: '١', 2: '٢', 3: '٣', 4: '٤', 5: '٥', 6: '٦', 7: '٧' };

type DayKey = typeof DAYS[number]['key'];
type CellState = 'normal' | 'locked' | 'substitute' | 'substituted' | 'relocated';
type Cell = { subject?: string; klass?: string; state?: CellState };
type Row = {
  id: string;
  name: string;
  specialty: string;
  badge?: string;
  initials: string;
  color: string;
  empty?: boolean;
  cells: Record<DayKey, (Cell | null)[]>;
};

const C = (subject: string, klass: string, state: CellState = 'normal'): Cell => ({ subject, klass, state });
const L = (): Cell => ({ state: 'locked' });
const N = (): null => null;

const TEACHERS: Row[] = [
  {
    id: 't1', name: 'أ. محمد المتيمي', specialty: 'رياضيات', initials: 'مم', color: '#1C3D74',
    cells: {
      sun: [C('رياض','١أ'), C('رياض','٢ب'), L(),         C('رياض','٤ج'), C('رياض','١أ'), C('رياض','٣أ'), N()],
      mon: [C('رياض','٢ب'), C('رياض','١أ'), C('رياض','٣ب'), L(),         C('رياض','٤أ'), C('رياض','٢أ'), N()],
      tue: [C('رياض','٣أ'), C('رياض','١ب'), C('رياض','٢أ'), C('رياض','٤ب'), L(),         C('رياض','١أ'), N()],
      wed: [C('رياض','١أ'), C('رياض','٤أ'), C('رياض','٣ب'), C('رياض','٢أ'), C('رياض','١ب'), L(),         N()],
      thu: [C('رياض','٢ب'), C('رياض','١ج'), C('رياض','٤ب',  'substitute'), L(),         N(),         N(),         N()],
    },
  },
  {
    id: 't2', name: 'أ. سعد الدوسري', specialty: 'علوم', initials: 'سد', color: '#46C1BE',
    cells: {
      sun: [C('علوم','١أ'), C('علوم','٢ب'), C('علوم','٣ج'), L(),         C('علوم','٤أ'), C('علوم','١ب'), N()],
      mon: [C('علوم','٢أ'), C('علوم','١ج'), C('علوم','٣أ'), C('علوم','٤ب'), L(),         C('علوم','٢ب'), N()],
      tue: [C('علوم','١ب'), C('علوم','٤أ'), L(),         C('علوم','٣ب'), C('علوم','٢أ'), C('علوم','١أ'), N()],
      wed: [C('علوم','٣ب'), L(),         C('علوم','٢ج'), C('علوم','١أ'), C('علوم','٤أ'), C('علوم','٣أ'), N()],
      thu: [C('علوم','٤ب'), C('علوم','٢أ'), C('علوم','١ب'), C('علوم','٣ج'), L(),         N(),         N()],
    },
  },
  {
    id: 't3', name: 'أ. فهد القحطاني', specialty: 'لغة دولية', badge: 'دولية', initials: 'فق', color: '#615090',
    cells: { sun: [], mon: [], tue: [], wed: [], thu: [] }, empty: true,
  },
  {
    id: 't4', name: 'أ. خالد الحرب', specialty: 'احتساب', badge: '١ نشاط', initials: 'خح', color: '#D4A23C',
    cells: {
      sun: [C('احتس','٢ب'), C('احتس','١أ'), L(),         C('احتس','٣ب'), C('احتس','٤أ'), C('احتس','٢أ'), N()],
      mon: [C('احتس','١ج'), C('احتس','٣أ'), C('احتس','٢ب'), L(),         C('احتس','١أ'), C('احتس','٤ب'), N()],
      tue: [C('احتس','٤أ'), C('احتس','١ب'), C('احتس','٣ج'), C('احتس','٢أ'), L(),         C('احتس','١أ'), N()],
      wed: [C('احتس','٢أ'), C('احتس','٣ب'), C('احتس','١أ'), C('احتس','٤ج'), C('احتس','٢ب'), L(),         N()],
      thu: [C('احتس','١أ'), C('احتس','٢ج'), L(),         C('احتس','٣أ'), N(),         N(),         N()],
    },
  },
  {
    id: 't5', name: 'أ. عبدالله الشهري', specialty: 'تربية إسلامية', initials: 'عش', color: '#7AA169',
    cells: {
      sun: [C('تر إس','٣أ'), C('تر إس','٤ب'), C('تر إس','١أ'), C('تر إس','٢ج'), L(),         C('تر إس','٣ب'), N()],
      mon: [C('تر إس','١أ'), C('تر إس','٢ب','relocated'), L(),         C('تر إس','٣أ'), C('تر إس','٤ب'), C('تر إس','١ب'), N()],
      tue: [C('تر إس','٢ج'), L(),         C('تر إس','٤أ'), C('تر إس','٣ب'), C('تر إس','١أ'), C('تر إس','٢ب'), N()],
      wed: [L(),         C('تر إس','٣ج'), C('تر إس','١ب'), C('تر إس','٤أ'), C('تر إس','٢أ'), C('تر إس','٣أ'), N()],
      thu: [C('تر إس','١أ'), C('تر إس','٤ب'), C('تر إس','٢ج','substitute'), L(),         N(),         N(),         N()],
    },
  },
  {
    id: 't6', name: 'أ. أحمد العايدي', specialty: 'تربية', badge: '١ نشاط', initials: 'أع', color: '#46C1BE',
    cells: {
      sun: [C('تربية','٢أ'), C('تربية','١ب'), C('تربية','٣ج'), L(),         C('تربية','٤أ'), C('تربية','١أ'), N()],
      mon: [C('تربية','١ب'), C('تربية','٤أ'), C('تربية','٢أ'), C('تربية','٣ب'), L(),         C('تربية','١أ'), N()],
      tue: [C('تربية','٣أ'), C('تربية','١أ'), L(),         C('تربية','٢ب'), C('تربية','٤ج'), C('تربية','٣ب'), N()],
      wed: [C('تربية','٤أ'), L(),         C('تربية','٢ب'), C('تربية','١أ'), C('تربية','٣أ'), C('تربية','٤ب'), N()],
      thu: [C('تربية','١أ'), C('تربية','٢ب'), C('تربية','٣ج'), L(),         N(),         N(),         N()],
    },
  },
  {
    id: 't7', name: 'أ. ياسر الغامدي', specialty: 'تربية صحية', initials: 'يغ', color: '#615090',
    cells: {
      sun: [C('صحة','١أ'), C('صحة','٢ب'), C('صحة','٤ج'), C('صحة','٣أ'), L(),         C('صحة','١ب'), N()],
      mon: [L(),         C('صحة','٣أ'), C('صحة','٤ب'), C('صحة','١أ'), C('صحة','٢ب'), C('صحة','٣ج'), N()],
      tue: [C('صحة','٢أ'), C('صحة','١ج'), C('صحة','٣ب'), L(),         C('صحة','٤أ'), C('صحة','١أ'), N()],
      wed: [C('صحة','٤ج'), C('صحة','٣أ'), C('صحة','١أ'), C('صحة','٢ب'), L(),         C('صحة','٤ب'), N()],
      thu: [C('صحة','١أ','substituted'), C('صحة','٢ب'), L(),         C('صحة','٤ج'), N(),         N(),         N()],
    },
  },
  {
    id: 't8', name: 'أ. بندر السبيعي', specialty: 'تربية', badge: '١ نشاط', initials: 'بس', color: '#D4A23C',
    cells: {
      sun: [C('تربية','٣ب'), C('تربية','١أ'), L(),         C('تربية','٢أ'), C('تربية','٤ب'), C('تربية','١ج'), N()],
      mon: [C('تربية','٤أ'), C('تربية','٢ب'), C('تربية','١أ'), L(),         C('تربية','٣ج'), C('تربية','٢أ'), N()],
      tue: [L(),         C('تربية','٤ج'), C('تربية','٢ب'), C('تربية','١أ'), C('تربية','٣ب'), C('تربية','٤أ'), N()],
      wed: [C('تربية','٣أ'), C('تربية','١ب'), C('تربية','٢ج'), L(),         C('تربية','٤ب'), C('تربية','١أ'), N()],
      thu: [C('تربية','٤ب'), L(),         C('تربية','١أ'), C('تربية','٣ج'), N(),         N(),         N()],
    },
  },
  {
    id: 't9', name: 'أ. يوسف المطيري', specialty: 'رياضيات', initials: 'يم', color: '#1C3D74',
    cells: {
      sun: [C('رياض','٤ب'), C('رياض','٣أ'), C('رياض','٢ج'), L(),         C('رياض','١أ'), C('رياض','٢ب'), N()],
      mon: [C('رياض','٢أ'), L(),         C('رياض','٣ب'), C('رياض','٤أ'), C('رياض','١ب'), C('رياض','٣ج'), N()],
      tue: [C('رياض','١أ'), C('رياض','٤ب'), L(),         C('رياض','٢أ'), C('رياض','٣ب'), C('رياض','١ج'), N()],
      wed: [C('رياض','٣أ'), C('رياض','١ب'), C('رياض','٤ج'), C('رياض','٢ب'), L(),         C('رياض','٣ب'), N()],
      thu: [L(),         C('رياض','٤أ'), C('رياض','٢ب'), C('رياض','١ج'), N(),         N(),         N()],
    },
  },
  {
    id: 't10', name: 'أ. راشد العنزي', specialty: 'تربية', initials: 'رع', color: '#7AA169',
    cells: {
      sun: [C('تربية','١أ'), C('تربية','٢ج'), C('تربية','٣أ'), C('تربية','٤ب'), C('تربية','١ب'), L(),         N()],
      mon: [C('تربية','٣ب'), C('تربية','٤أ'), L(),         C('تربية','٢أ'), C('تربية','١ج'), C('تربية','٣أ'), N()],
      tue: [C('تربية','٢ب'), C('تربية','١أ'), C('تربية','٤ج'), L(),         C('تربية','٣أ'), C('تربية','٢أ'), N()],
      wed: [L(),         C('تربية','٣ب'), C('تربية','١أ'), C('تربية','٤أ'), C('تربية','٢ج'), C('تربية','١ب'), N()],
      thu: [C('تربية','٣أ'), C('تربية','١ب'), C('تربية','٢ج'), L(),         N(),         N(),         N()],
    },
  },
];

function PeriodCell({ cell, dayKey }: { cell: Cell | null; dayKey: DayKey }) {
  const tint = `var(--day-${dayKey}-tint)`;
  const ink = `var(--day-${dayKey}-ink)`;
  const band = `var(--day-${dayKey}-band)`;

  if (cell === null) {
    return <div className="h-[52px]" style={{ background: '#fff' }} />;
  }
  if (cell.state === 'locked') {
    return (
      <div
        className="sg-cell h-[52px] flex items-center justify-center cursor-pointer relative"
        style={{
          background: tint,
          backgroundImage: 'repeating-linear-gradient(135deg, rgba(255,255,255,0.55) 0 5px, transparent 5px 10px)',
          borderInline: '1px solid rgba(255,255,255,0.85)',
        }}
      >
        <div
          className="w-7 h-7 rounded-full flex items-center justify-center"
          style={{ background: 'rgba(255,255,255,0.9)', color: '#E4572E', boxShadow: '0 2px 6px rgba(228,87,46,0.25)' }}
        >
          <Lock className="w-3.5 h-3.5" strokeWidth={2.5} />
        </div>
      </div>
    );
  }

  const isSub = cell.state === 'substitute';
  const isSubstituted = cell.state === 'substituted';
  const isReloc = cell.state === 'relocated';

  return (
    <div
      className="sg-cell h-[52px] px-1.5 flex flex-col items-center justify-center cursor-pointer relative"
      style={{
        background: tint,
        borderInline: '1px solid rgba(255,255,255,0.85)',
        outline: isSub ? `2px solid ${band}` : undefined,
        outlineOffset: isSub ? '-2px' : undefined,
      }}
    >
      {(isSub || isSubstituted || isReloc) && (
        <span
          className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full"
          style={{ background: isSub ? '#46C1BE' : isSubstituted ? '#E4572E' : '#3B82F6' }}
        />
      )}
      <div className="font-extrabold text-[12px] leading-tight" style={{ color: ink }}>{cell.subject}</div>
      <div className="font-mono text-[11px] leading-tight font-bold" style={{ color: ink, opacity: 0.7 }}>{cell.klass}</div>
    </div>
  );
}

function DayBandHeader({ dayKey, label }: { dayKey: DayKey; label: string }) {
  const lightBand = dayKey === 'mon' || dayKey === 'tue' || dayKey === 'wed';
  return (
    <div
      className="col-span-7 px-3 py-2 text-center font-extrabold text-[15px] flex items-center justify-center gap-2"
      style={{
        background: `linear-gradient(180deg, var(--day-${dayKey}-band) 0%, color-mix(in srgb, var(--day-${dayKey}-band) 82%, white) 100%)`,
        color: lightBand ? `var(--day-${dayKey}-ink)` : '#fff',
        borderInline: '1px solid rgba(255,255,255,0.6)',
      }}
    >
      {label}
    </div>
  );
}

function PeriodNumberCell({ dayKey, n }: { dayKey: DayKey; n: number }) {
  const lightBand = dayKey === 'mon' || dayKey === 'tue' || dayKey === 'wed';
  return (
    <div
      className="text-center text-[11px] font-mono font-bold py-1"
      style={{
        background: `color-mix(in srgb, var(--day-${dayKey}-band) 88%, white)`,
        color: lightBand ? `var(--day-${dayKey}-ink)` : '#fff',
        borderInline: '1px solid rgba(255,255,255,0.5)',
      }}
    >
      {AR_DIGIT[n]}
    </div>
  );
}

function TeacherCell({ row, isFirst, isLast }: { row: Row; isFirst: boolean; isLast: boolean }) {
  return (
    <div
      className="px-3 py-2 flex items-center gap-2.5 bg-white"
      style={{
        borderTop: isFirst ? 'none' : '1px solid #E5EAF2',
        borderBottom: isLast ? 'none' : 'none',
      }}
    >
      <div
        className="w-9 h-9 rounded-full flex items-center justify-center text-white font-extrabold text-[12px] shrink-0"
        style={{ background: row.color, boxShadow: `0 0 0 2px white, 0 0 0 3px ${row.color}33` }}
      >
        {row.initials}
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-extrabold text-[13px] leading-tight text-slate-800 truncate">{row.name}</div>
        <div className="flex items-center gap-1.5 mt-0.5">
          <span className="text-[10.5px] text-slate-500 truncate">{row.specialty}</span>
          {row.badge && (
            <span
              className="text-[9.5px] px-1.5 py-0.5 rounded-full font-bold whitespace-nowrap"
              style={{ background: '#FFF4D9', color: '#7A5616' }}
            >
              {row.badge}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

export function MasterGrid() {
  // 5 days × 7 periods + 1 teacher column = 36 columns. Fixed widths so teacher names are readable.
  const PERIOD_W = 56;
  const TEACHER_W = 240;
  const totalW = 5 * 7 * PERIOD_W + TEACHER_W;
  // Teacher first (rightmost under RTL), then days Sun→Thu (right-to-left under RTL)
  const gridCols = `${TEACHER_W}px repeat(${5 * 7}, ${PERIOD_W}px)`;

  return (
    <div className="sg-root p-5">
      {/* Top bar */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-2">
          <button
            className="px-4 py-2 rounded-xl font-bold text-[13px] text-white shadow-md flex items-center gap-2"
            style={{ background: 'var(--brand-navy)' }}
          >
            <Pencil className="w-3.5 h-3.5" /> تعديل الجدول
          </button>
          <button className="px-4 py-2 rounded-xl font-bold text-[13px] text-slate-700 bg-white border border-slate-200 flex items-center gap-2">
            <Filter className="w-3.5 h-3.5" /> تصفية
          </button>
        </div>
        <div className="text-right">
          <h1 className="text-[22px] font-extrabold leading-none" style={{ color: 'var(--brand-navy)' }}>
            جدول المدرسة الرئيسي
          </h1>
          <p className="text-[12px] text-slate-500 mt-1">الأسبوع الحالي ‏· ٣٢٠ من ٣٥٠ حصة مُسندة</p>
        </div>
      </div>

      {/* Grid (horizontally scrollable on narrow viewports) */}
      <div className="rounded-2xl overflow-x-auto shadow-sm border border-slate-200 bg-white">
       <div style={{ minWidth: `${totalW}px` }}>
        {/* Header row 1: teacher header (right) + day bands */}
        <div className="grid" style={{ gridTemplateColumns: gridCols }}>
          <div
            className="px-3 py-3 text-center font-extrabold text-[13px] text-white flex items-center justify-center"
            style={{ background: 'var(--brand-navy)' }}
          >
            اسم المعلم
          </div>
          {DAYS.map((d) => (
            <DayBandHeader key={d.key} dayKey={d.key} label={d.label} />
          ))}
        </div>

        {/* Header row 2: period numbers under each day band */}
        <div className="grid" style={{ gridTemplateColumns: gridCols }}>
          <div className="bg-slate-50 border-t border-slate-100" />
          {DAYS.map((d) =>
            PERIODS.map((p) => <PeriodNumberCell key={`${d.key}-${p}`} dayKey={d.key} n={p} />)
          )}
        </div>

        {/* Body rows */}
        {TEACHERS.map((row, rIdx) => {
          const isFirst = rIdx === 0;
          const isLast = rIdx === TEACHERS.length - 1;

          if (row.empty) {
            return (
              <div key={row.id} className="grid" style={{ gridTemplateColumns: gridCols, borderTop: '1px solid #EEF2F8' }}>
                <TeacherCell row={row} isFirst={isFirst} isLast={isLast} />
                <div
                  className="flex items-center justify-center gap-2 text-[12.5px] font-bold text-amber-800 py-3"
                  style={{ gridColumn: 'span 35', background: 'linear-gradient(180deg,#FFF7E2 0%,#FFEFCB 100%)', borderTop: '1px solid #F5E2B0', borderBottom: '1px solid #F5E2B0' }}
                >
                  <AlertTriangle className="w-4 h-4" />
                  منطقة الإدارة المختصة ‏· لا توجد حصص مجدولة
                </div>
              </div>
            );
          }

          return (
            <div key={row.id} className="grid" style={{ gridTemplateColumns: gridCols, borderTop: rIdx === 0 ? 'none' : '1px solid #EEF2F8' }}>
              <TeacherCell row={row} isFirst={isFirst} isLast={isLast} />
              {DAYS.map((d) =>
                row.cells[d.key].length === 0
                  ? PERIODS.map((p) => <div key={`${d.key}-${p}`} className="h-[52px] bg-white" />)
                  : PERIODS.map((p, i) => (
                      <PeriodCell key={`${d.key}-${p}`} cell={row.cells[d.key][i] ?? null} dayKey={d.key} />
                    ))
              )}
            </div>
          );
        })}
       </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center justify-center gap-2 mt-4 text-[11.5px]">
        {DAYS.map((d) => (
          <span
            key={d.key}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white border border-slate-200 font-bold"
            style={{ color: `var(--day-${d.key}-ink)` }}
          >
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: `var(--day-${d.key}-band)` }} />
            {d.label}
          </span>
        ))}
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white border border-slate-200 font-bold text-slate-600">
          <Lock className="w-3 h-3 text-rose-500" /> فسحة / مغلقة
        </span>
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white border border-slate-200 font-bold text-slate-600">
          <RefreshCw className="w-3 h-3 text-teal-500" /> بديلة
        </span>
      </div>
    </div>
  );
}
