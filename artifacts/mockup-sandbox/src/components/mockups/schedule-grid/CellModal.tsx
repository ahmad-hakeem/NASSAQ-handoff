import './_group.css';
import { Pencil, ArrowLeftRight, Lock, X, MapPin, User, Hash, Clock, BookOpen, Calendar, FileText } from 'lucide-react';

export function CellModal() {
  const dayKey = 'tue';
  return (
    <div className="sg-root p-6 relative" style={{ minHeight: '100vh' }}>
      {/* Faded grid background */}
      <div className="absolute inset-0 pointer-events-none opacity-40 p-6">
        <div className="max-w-[1200px] mx-auto">
          <div className="sg-glass rounded-2xl p-4">
            <div className="grid gap-2" style={{ gridTemplateColumns: 'repeat(5, minmax(0, 1fr))' }}>
              {(['sun','mon','tue','wed','thu'] as const).map((d) => (
                <div key={d} className="rounded-t-2xl px-3 py-2.5 text-white text-center"
                  style={{ background: `var(--day-${d}-band)` }}>
                  <div className="font-extrabold text-sm">{
                    {sun:'الأحد', mon:'الاثنين', tue:'الثلاثاء', wed:'الأربعاء', thu:'الخميس'}[d]
                  }</div>
                </div>
              ))}
              {Array.from({length: 25}).map((_, i) => {
                const d = (['sun','mon','tue','wed','thu'] as const)[i % 5];
                return (
                  <div key={i} className="h-[80px] rounded-xl"
                    style={{ background: `var(--day-${d}-tint)`, border: '1px solid rgba(255,255,255,0.6)' }} />
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Backdrop blur */}
      <div className="absolute inset-0 backdrop-blur-md bg-slate-900/20" />

      {/* Modal */}
      <div className="relative z-10 flex items-center justify-center min-h-[88vh]">
        <div className="sg-glass rounded-3xl w-[520px] overflow-hidden">
          {/* Day-coded band header — dark ink on lighter bands (mon/tue/wed) for AA contrast */}
          <div
            className="px-6 py-5 relative overflow-hidden"
            style={{
              background: `linear-gradient(135deg, var(--day-${dayKey}-band) 0%, color-mix(in srgb, var(--day-${dayKey}-band) 78%, white) 100%)`,
              color: (dayKey === 'mon' || dayKey === 'tue' || dayKey === 'wed') ? `var(--day-${dayKey}-ink)` : '#fff',
            }}
          >
            <button className="absolute top-3 left-3 w-8 h-8 rounded-full bg-white/40 hover:bg-white/60 flex items-center justify-center transition">
              <X className="w-4 h-4" />
            </button>
            <div className="flex items-center gap-2 text-[12px] font-bold mb-1" style={{opacity: 0.95}}>
              <Calendar className="w-3.5 h-3.5" />
              <span>الثلاثاء · حصة ٤ · ١٠:٢٠ - ١١:٠٥</span>
            </div>
            <div className="text-2xl font-extrabold leading-tight">العلوم</div>
            <div className="flex items-center gap-3 mt-2 text-sm font-bold">
              <span className="inline-flex items-center gap-1"><Hash className="w-3.5 h-3.5" />٤/ب</span>
              <span className="inline-flex items-center gap-1"><User className="w-3.5 h-3.5" />أ. خالد الزهراني</span>
            </div>
          </div>

          {/* Status banner (relocated example) */}
          <div className="px-6 py-2.5 bg-sky-50 border-b border-sky-100 flex items-center gap-2 text-sm">
            <MapPin className="w-4 h-4 text-sky-600" />
            <span className="font-bold text-sky-800">نُقلت إلى مختبر ٢</span>
            <span className="text-sky-600 text-xs mr-auto">منذ ٣ ساعات · بواسطة أ. ليلى</span>
          </div>

          {/* Body — 7 fields */}
          <div className="px-6 py-5 bg-white/55 space-y-3">
            <Field icon={BookOpen} label="المادة" value="العلوم" />
            <Field icon={Hash}     label="الصف"   value="٤/ب · ٢٨ طالبًا" />
            <Field icon={User}     label="المعلم" value="أ. خالد الزهراني" />
            <Field icon={MapPin}   label="القاعة" value="مختبر ٢ (مُنقولة من مختبر ١)" />
            <Field icon={Clock}    label="التوقيت" value="١٠:٢٠ ص — ١١:٠٥ ص" />
            <Field icon={Calendar} label="اليوم"   value="الثلاثاء · الحصة الرابعة" />
            <Field icon={FileText} label="ملاحظة"  value="تجربة مخبرية تتطلب التحضير" muted />
          </div>

          {/* Quick actions */}
          <div className="px-6 py-4 bg-white/70 border-t border-white/60 grid grid-cols-3 gap-2">
            <ActionButton icon={Pencil} label="تعديل" tone="primary" />
            <ActionButton icon={ArrowLeftRight} label="نقل" tone="muted" />
            <ActionButton icon={Lock} label="قفل" tone="muted" />
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ icon: Icon, label, value, muted }: { icon: typeof MapPin; label: string; value: string; muted?: boolean }) {
  return (
    <div className="flex items-start gap-3">
      <div className="w-8 h-8 rounded-lg bg-[var(--brand-navy)]/8 flex items-center justify-center shrink-0" style={{background: 'rgba(28,61,116,0.08)'}}>
        <Icon className="w-4 h-4 text-[var(--brand-navy)]" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">{label}</div>
        <div className={`text-sm font-bold ${muted ? 'text-slate-500' : 'text-slate-800'} mt-0.5`}>{value}</div>
      </div>
    </div>
  );
}

function ActionButton({ icon: Icon, label, tone }: { icon: typeof Pencil; label: string; tone: 'primary' | 'muted' }) {
  const isPrimary = tone === 'primary';
  return (
    <button
      className={`flex items-center justify-center gap-1.5 py-2.5 rounded-xl text-sm font-extrabold transition ${
        isPrimary
          ? 'text-white shadow-sm'
          : 'bg-white/70 text-slate-700 border border-slate-200 hover:bg-white'
      }`}
      style={isPrimary ? { background: 'var(--brand-navy)' } : undefined}
    >
      <Icon className="w-4 h-4" />
      {label}
    </button>
  );
}
