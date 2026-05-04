import './_group.css';
import { Lock, Repeat2, UserMinus, MapPin, Sparkles } from 'lucide-react';

const DAYS = [
  { key: 'sun', label: 'الأحد', code: 'SUN' },
  { key: 'mon', label: 'الاثنين', code: 'MON' },
  { key: 'tue', label: 'الثلاثاء', code: 'TUE' },
  { key: 'wed', label: 'الأربعاء', code: 'WED' },
  { key: 'thu', label: 'الخميس', code: 'THU' },
] as const;

const PERIODS = [
  { n: 1, time: '٧:٤٥ - ٨:٣٠' },
  { n: 2, time: '٨:٣٠ - ٩:١٥' },
  { n: 3, time: '٩:١٥ - ١٠:٠٠' },
  { n: 4, time: '١٠:٢٠ - ١١:٠٥' },
  { n: 5, time: '١١:٠٥ - ١١:٥٠' },
  { n: 6, time: '١٢:١٠ - ١٢:٥٥' },
  { n: 7, time: '١٢:٥٥ - ١:٤٠' },
];

type CellState = 'normal' | 'vacant' | 'substituted' | 'substitute' | 'relocated' | 'locked';
type Cell = {
  state: CellState;
  subject?: string;
  klass?: string;
  teacher?: string;
  room?: string;
  note?: string;
};

const sample: Record<string, Cell> = {
  'sun-1': { state: 'normal', subject: 'الرياضيات', klass: '٣/أ', teacher: 'أ. سارة المنصوري', room: 'غرفة ١٠٢' },
  'sun-2': { state: 'normal', subject: 'اللغة العربية', klass: '٣/أ', teacher: 'أ. هدى الراشد', room: 'غرفة ١٠٢' },
  'sun-3': { state: 'locked', subject: 'الفسحة', klass: '—', teacher: '—', room: 'الباحة' },
  'sun-4': { state: 'normal', subject: 'العلوم', klass: '٤/ب', teacher: 'أ. خالد الزهراني', room: 'مختبر ١' },
  'sun-5': { state: 'vacant', klass: '٤/ب' },
  'sun-6': { state: 'normal', subject: 'التربية الإسلامية', klass: '٢/ج', teacher: 'أ. منى السبيعي', room: 'غرفة ٩' },
  'sun-7': { state: 'normal', subject: 'الإنجليزية', klass: '٥/أ', teacher: 'أ. لينا قاسم', room: 'غرفة ١٤' },

  'mon-1': { state: 'normal', subject: 'العلوم', klass: '٤/ب', teacher: 'أ. خالد الزهراني', room: 'مختبر ١' },
  'mon-2': { state: 'substituted', subject: 'الرياضيات', klass: '٣/أ', teacher: 'أ. سارة المنصوري', room: 'غرفة ١٠٢', note: 'تم استبدالها' },
  'mon-3': { state: 'substitute', subject: 'الرياضيات', klass: '٣/أ', teacher: 'أ. نورة العتيبي', room: 'غرفة ١٠٢', note: 'بديلة عن سارة' },
  'mon-4': { state: 'normal', subject: 'الفنون', klass: '١/أ', teacher: 'أ. ريم الهاجري', room: 'مرسم' },
  'mon-5': { state: 'normal', subject: 'اللغة العربية', klass: '٣/ب', teacher: 'أ. هدى الراشد', room: 'غرفة ١٠٣' },
  'mon-6': { state: 'normal', subject: 'الرياضة', klass: '٥/ب', teacher: 'أ. ماجد الفهد', room: 'الملعب' },
  'mon-7': { state: 'vacant', klass: '٢/أ' },

  'tue-1': { state: 'normal', subject: 'الإنجليزية', klass: '٥/أ', teacher: 'أ. لينا قاسم', room: 'غرفة ١٤' },
  'tue-2': { state: 'normal', subject: 'الرياضيات', klass: '٣/أ', teacher: 'أ. سارة المنصوري', room: 'غرفة ١٠٢' },
  'tue-3': { state: 'locked', subject: 'الفسحة', klass: '—', teacher: '—', room: 'الباحة' },
  'tue-4': { state: 'relocated', subject: 'العلوم', klass: '٤/ب', teacher: 'أ. خالد الزهراني', room: 'مختبر ٢', note: 'نُقلت لمختبر ٢' },
  'tue-5': { state: 'normal', subject: 'التربية الإسلامية', klass: '٢/ج', teacher: 'أ. منى السبيعي', room: 'غرفة ٩' },
  'tue-6': { state: 'normal', subject: 'الفنون', klass: '١/أ', teacher: 'أ. ريم الهاجري', room: 'مرسم' },
  'tue-7': { state: 'normal', subject: 'اللغة العربية', klass: '٣/ب', teacher: 'أ. هدى الراشد', room: 'غرفة ١٠٣' },

  'wed-1': { state: 'normal', subject: 'العلوم', klass: '٤/ب', teacher: 'أ. خالد الزهراني', room: 'مختبر ١' },
  'wed-2': { state: 'normal', subject: 'اللغة العربية', klass: '٣/أ', teacher: 'أ. هدى الراشد', room: 'غرفة ١٠٢' },
  'wed-3': { state: 'normal', subject: 'الإنجليزية', klass: '٥/أ', teacher: 'أ. لينا قاسم', room: 'غرفة ١٤' },
  'wed-4': { state: 'normal', subject: 'الرياضة', klass: '٥/ب', teacher: 'أ. ماجد الفهد', room: 'الملعب' },
  'wed-5': { state: 'vacant', klass: '٢/أ' },
  'wed-6': { state: 'normal', subject: 'الرياضيات', klass: '٣/أ', teacher: 'أ. سارة المنصوري', room: 'غرفة ١٠٢' },
  'wed-7': { state: 'normal', subject: 'التربية الإسلامية', klass: '٢/ج', teacher: 'أ. منى السبيعي', room: 'غرفة ٩' },

  'thu-1': { state: 'normal', subject: 'الفنون', klass: '١/أ', teacher: 'أ. ريم الهاجري', room: 'مرسم' },
  'thu-2': { state: 'normal', subject: 'العلوم', klass: '٤/ب', teacher: 'أ. خالد الزهراني', room: 'مختبر ١' },
  'thu-3': { state: 'locked', subject: 'الفسحة', klass: '—', teacher: '—', room: 'الباحة' },
  'thu-4': { state: 'normal', subject: 'الرياضيات', klass: '٣/أ', teacher: 'أ. سارة المنصوري', room: 'غرفة ١٠٢' },
  'thu-5': { state: 'normal', subject: 'اللغة العربية', klass: '٣/أ', teacher: 'أ. هدى الراشد', room: 'غرفة ١٠٢' },
  'thu-6': { state: 'normal', subject: 'الإنجليزية', klass: '٥/أ', teacher: 'أ. لينا قاسم', room: 'غرفة ١٤' },
  'thu-7': { state: 'normal', subject: 'الرياضة', klass: '٥/ب', teacher: 'أ. ماجد الفهد', room: 'الملعب' },
};

function dayVars(key: string): React.CSSProperties {
  return {
    ['--tint' as any]: `var(--day-${key}-tint)`,
    ['--band' as any]: `var(--day-${key}-band)`,
    ['--ink' as any]: `var(--day-${key}-ink)`,
  };
}

function StatusChip({ state }: { state: CellState }) {
  if (state === 'normal') return null;
  const cfg: Record<Exclude<CellState,'normal'>, { label: string; cls: string; Icon: typeof Lock }> = {
    vacant:      { label: 'شاغرة',  cls: 'bg-slate-100 text-slate-600 border-slate-200',          Icon: Sparkles },
    substituted: { label: 'مُستبدَلة', cls: 'bg-rose-50 text-rose-700 border-rose-200',          Icon: UserMinus },
    substitute:  { label: 'بديلة',  cls: 'bg-amber-50 text-amber-800 border-amber-200',          Icon: Repeat2 },
    relocated:   { label: 'مُنتقلة', cls: 'bg-sky-50 text-sky-700 border-sky-200',                Icon: MapPin },
    locked:      { label: 'مغلقة',  cls: 'bg-slate-200/70 text-slate-600 border-slate-300',      Icon: Lock },
  };
  const c = cfg[state as Exclude<CellState,'normal'>];
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-bold rounded-full border px-1.5 py-0.5 ${c.cls}`}>
      <c.Icon className="w-3 h-3" />
      {c.label}
    </span>
  );
}

function SessionCell({ cell }: { cell?: Cell }) {
  if (!cell || cell.state === 'vacant') {
    return (
      <div
        className="sg-cell h-[88px] rounded-xl flex items-center justify-center text-[11px] font-bold cursor-pointer relative overflow-hidden"
        style={{
          background: 'var(--tint)',
          border: '1.5px dashed color-mix(in srgb, var(--band) 55%, white)',
          color: 'var(--ink)',
        }}
      >
        <span className="opacity-70">+ إضافة</span>
        {cell?.state === 'vacant' && (
          <span className="absolute top-1.5 left-1.5"><StatusChip state="vacant" /></span>
        )}
      </div>
    );
  }
  const isLocked = cell.state === 'locked';
  return (
    <div
      className="sg-cell h-[88px] rounded-xl p-2 flex flex-col justify-between cursor-pointer relative overflow-hidden"
      style={{
        background: 'var(--tint)',
        border: '1px solid rgba(255,255,255,0.7)',
        boxShadow: 'inset 0 0 0 1px rgba(0,0,0,0.03), 0 1px 2px rgba(28,61,116,0.04)',
      }}
    >
      {isLocked && (
        <div className="absolute inset-0 pointer-events-none" style={{
          background: 'repeating-linear-gradient(135deg, rgba(255,255,255,0.35) 0 6px, transparent 6px 12px)',
        }} />
      )}
      <div className="flex items-start justify-between gap-1">
        <div className="font-extrabold text-[13px] leading-tight" style={{ color: 'var(--ink)' }}>
          {cell.subject}
        </div>
        <StatusChip state={cell.state} />
      </div>
      <div className="space-y-0.5">
        <div className="text-[11px] font-bold text-slate-700 truncate">{cell.teacher}</div>
        <div className="flex items-center justify-between text-[10px] text-slate-500">
          <span className="font-semibold">{cell.klass}</span>
          <span className="inline-flex items-center gap-0.5">
            <MapPin className="w-2.5 h-2.5" />
            {cell.room}
          </span>
        </div>
      </div>
    </div>
  );
}

function DayHeader({ label, code, dayKey }: { label: string; code: string; dayKey: string }) {
  // Sun (navy) and Thu (purple) are dark enough for white text; lighter bands use dark ink for AA contrast.
  const lightBand = dayKey === 'mon' || dayKey === 'tue' || dayKey === 'wed';
  const textColor = lightBand ? `var(--day-${dayKey}-ink)` : '#fff';
  return (
    <div
      className="rounded-t-2xl px-3 py-2.5 text-center shadow-sm relative overflow-hidden"
      style={{
        background: `linear-gradient(135deg, var(--day-${dayKey}-band) 0%, color-mix(in srgb, var(--day-${dayKey}-band) 80%, white) 100%)`,
        color: textColor,
      }}
    >
      <div className="font-extrabold text-base leading-none">{label}</div>
      <div className="text-[10px] mt-1 font-mono tracking-widest font-bold" style={{ opacity: lightBand ? 0.95 : 0.85 }}>{code}</div>
    </div>
  );
}

export function MasterGrid() {
  return (
    <div className="sg-root p-6">
      <div className="max-w-[1200px] mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div>
            <h1 className="text-2xl font-extrabold text-[var(--brand-navy)] mb-1">جدول المدرسة الرئيسي</h1>
            <p className="text-sm text-slate-500">الأسبوع الحالي · ٢٢ من ٣٥ حصة مُسندة</p>
          </div>
          <div className="flex items-center gap-2">
            <button className="px-3 py-2 rounded-xl text-sm font-bold bg-white border border-slate-200 text-slate-700 shadow-sm">تصفية</button>
            <button className="px-3 py-2 rounded-xl text-sm font-bold text-white shadow-sm" style={{background: 'var(--brand-navy)'}}>
              تعديل الجدول
            </button>
          </div>
        </div>

        {/* Grid */}
        <div className="sg-glass rounded-2xl p-4">
          <div className="grid gap-2" style={{ gridTemplateColumns: '90px repeat(5, minmax(0, 1fr))' }}>
            {/* Header row */}
            <div></div>
            {DAYS.map((d) => (
              <DayHeader key={d.key} label={d.label} code={d.code} dayKey={d.key} />
            ))}

            {/* Period rows */}
            {PERIODS.map((p) => (
              <>
                <div key={`p-${p.n}`} className="flex flex-col items-center justify-center text-center bg-slate-50/60 rounded-xl border border-slate-200/60 py-2">
                  <div className="text-xs font-extrabold text-slate-700">حصة</div>
                  <div className="text-lg font-extrabold text-[var(--brand-navy)] leading-none">{p.n}</div>
                  <div className="text-[9px] text-slate-400 mt-1 font-mono">{p.time}</div>
                </div>
                {DAYS.map((d) => (
                  <div key={`${d.key}-${p.n}`} style={dayVars(d.key)}>
                    <SessionCell cell={sample[`${d.key}-${p.n}`]} />
                  </div>
                ))}
              </>
            ))}
          </div>
        </div>

        {/* Legend */}
        <div className="mt-4 flex flex-wrap gap-2 justify-center text-[11px]">
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-white border border-slate-200 font-bold text-slate-600">
            <span className="w-3 h-3 rounded" style={{background: 'var(--day-sun-tint)', border: '1px solid var(--day-sun-band)'}}></span>
            الأحد
          </span>
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-white border border-slate-200 font-bold text-slate-600">
            <span className="w-3 h-3 rounded" style={{background: 'var(--day-mon-tint)', border: '1px solid var(--day-mon-band)'}}></span>
            الاثنين
          </span>
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-white border border-slate-200 font-bold text-slate-600">
            <span className="w-3 h-3 rounded" style={{background: 'var(--day-tue-tint)', border: '1px solid var(--day-tue-band)'}}></span>
            الثلاثاء
          </span>
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-white border border-slate-200 font-bold text-slate-600">
            <span className="w-3 h-3 rounded" style={{background: 'var(--day-wed-tint)', border: '1px solid var(--day-wed-band)'}}></span>
            الأربعاء
          </span>
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-white border border-slate-200 font-bold text-slate-600">
            <span className="w-3 h-3 rounded" style={{background: 'var(--day-thu-tint)', border: '1px solid var(--day-thu-band)'}}></span>
            الخميس
          </span>
        </div>
      </div>
    </div>
  );
}
