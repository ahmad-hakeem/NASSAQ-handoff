// Read-only in-session health & behavior detail dialog.
//
// Opened from the live-session roster (StudentRow health indicator). Fetches
// GET /session/{sessionId}/students/{studentId}/health FRESH on every open so
// the teacher always sees the latest saved data (parent edits included).
// Family-situation data never reaches this dialog — it is excluded
// server-side (backend/utils/student_health.py).
import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';
import { HEALTH_BADGES, BEHAVIOR_BADGES, badgeLabel } from '../../config/healthBadges';
import {
  HeartPulse, Loader2, AlertTriangle, Brain, ShieldCheck,
  Droplets, Pill, Siren, NotebookPen,
} from 'lucide-react';

const MEDICAL_ROWS = [
  { key: 'chronic_conditions', ar: 'أمراض مزمنة', icon: HeartPulse },
  { key: 'allergies', ar: 'الحساسية', icon: AlertTriangle },
  { key: 'disabilities', ar: 'إعاقات', icon: ShieldCheck },
  { key: 'current_medications', ar: 'أدوية حالية', icon: Pill },
  { key: 'special_care_notes', ar: 'رعاية خاصة', icon: NotebookPen },
  { key: 'emergency_medical_notes', ar: 'ملاحظات طوارئ', icon: Siren },
];

export default function StudentHealthDialog({ open, onClose, sessionId, student }) {
  const { api } = useAuth();
  const { language } = useTheme();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    if (!open || !sessionId || !student?.id) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setDetail(null);
    api.get(`/session/${sessionId}/students/${student.id}/health`)
      .then(res => { if (!cancelled) setDetail(res.data); })
      .catch(() => { if (!cancelled) setError('تعذر تحميل البيانات الصحية، حاول مرة أخرى'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [open, sessionId, student?.id, api]);

  const health = detail?.health || {};
  const behavior = detail?.behavior || {};
  const medicalRows = MEDICAL_ROWS
    .map(row => ({ ...row, value: health[row.key] }))
    .filter(row => row.value);
  const hasHealthSection = (health.conditions || []).length > 0
    || !!health.other_details || medicalRows.length > 0 || !!health.blood_type;
  const hasBehaviorSection = (behavior.aspects || []).length > 0 || !!behavior.other_details;

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose?.(); }}>
      <DialogContent className="max-w-md max-h-[85vh] overflow-y-auto" dir="rtl">
        <DialogHeader className="text-start">
          <DialogTitle className="font-cairo flex items-center gap-2">
            <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-rose-100 dark:bg-rose-500/20 flex-none">
              <HeartPulse className="h-4 w-4 text-rose-600" strokeWidth={1.5} aria-hidden="true" />
            </span>
            الملف الصحي — {student?.full_name}
          </DialogTitle>
          <DialogDescription className="font-cairo text-xs text-start">
            بيانات صحية وسلوكية للاطلاع فقط، تُعرض كما سجّلها ولي الأمر أو الإدارة
          </DialogDescription>
        </DialogHeader>

        {loading && (
          <div className="flex items-center justify-center gap-2 py-10 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
            <span className="font-cairo text-sm">جارٍ التحميل…</span>
          </div>
        )}

        {!loading && error && (
          <div className="flex items-center gap-2 rounded-lg border border-rose-400/40 bg-rose-500/10 px-3 py-3 text-rose-700 dark:text-rose-300">
            <AlertTriangle className="h-4 w-4 flex-none" strokeWidth={1.5} aria-hidden="true" />
            <span className="font-cairo text-sm">{error}</span>
          </div>
        )}

        {!loading && !error && detail && !detail.has_any && (
          <div className="flex flex-col items-center gap-2 py-8 text-muted-foreground">
            <ShieldCheck className="h-8 w-8 text-emerald-500" strokeWidth={1.5} aria-hidden="true" />
            <p className="font-cairo text-sm">لا توجد ملاحظات صحية أو سلوكية مسجلة لهذا الطالب</p>
          </div>
        )}

        {!loading && !error && detail && detail.has_any && (
          <div className="space-y-4">
            {hasHealthSection && (
              <section>
                <h4 className="font-cairo text-sm font-bold text-foreground flex items-center gap-1.5 mb-2">
                  <HeartPulse className="h-4 w-4 text-rose-500" strokeWidth={1.5} aria-hidden="true" />
                  المشاكل الصحية
                </h4>
                {(health.conditions || []).length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    {health.conditions.map(c => {
                      const def = HEALTH_BADGES[c];
                      const Icon = def?.icon || HeartPulse;
                      return (
                        <span key={c} className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-cairo font-medium ${def ? `${def.bg} ${def.color}` : 'bg-muted text-foreground'}`}>
                          <Icon className="h-3 w-3" strokeWidth={1.5} aria-hidden="true" />
                          {badgeLabel(HEALTH_BADGES, c, language)}
                        </span>
                      );
                    })}
                  </div>
                )}
                {health.other_details && (
                  <p className="font-cairo text-sm text-muted-foreground bg-muted/50 rounded-lg px-3 py-2 mb-2">{health.other_details}</p>
                )}
                {(medicalRows.length > 0 || health.blood_type) && (
                  <div className="rounded-lg border border-border divide-y divide-border">
                    {health.blood_type && (
                      <div className="flex items-start gap-2 px-3 py-2">
                        <Droplets className="h-4 w-4 text-rose-500 mt-0.5 flex-none" strokeWidth={1.5} aria-hidden="true" />
                        <div className="min-w-0">
                          <p className="font-cairo text-[11px] text-muted-foreground">فصيلة الدم</p>
                          <p className="font-cairo text-sm font-bold text-foreground" dir="ltr">{health.blood_type}</p>
                        </div>
                      </div>
                    )}
                    {medicalRows.map(row => {
                      const Icon = row.icon;
                      return (
                        <div key={row.key} className="flex items-start gap-2 px-3 py-2">
                          <Icon className="h-4 w-4 text-muted-foreground mt-0.5 flex-none" strokeWidth={1.5} aria-hidden="true" />
                          <div className="min-w-0">
                            <p className="font-cairo text-[11px] text-muted-foreground">{row.ar}</p>
                            <p className="font-cairo text-sm text-foreground break-words">{row.value}</p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </section>
            )}

            {hasBehaviorSection && (
              <section>
                <h4 className="font-cairo text-sm font-bold text-foreground flex items-center gap-1.5 mb-2">
                  <Brain className="h-4 w-4 text-violet-500" strokeWidth={1.5} aria-hidden="true" />
                  الجوانب السلوكية والتعلم
                </h4>
                {(behavior.aspects || []).length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    {behavior.aspects.map(b => {
                      const def = BEHAVIOR_BADGES[b];
                      const Icon = def?.icon || Brain;
                      return (
                        <span key={b} className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-cairo font-medium bg-violet-100 text-violet-700 dark:bg-violet-500/20 dark:text-violet-300">
                          <Icon className="h-3 w-3" strokeWidth={1.5} aria-hidden="true" />
                          {badgeLabel(BEHAVIOR_BADGES, b, language)}
                        </span>
                      );
                    })}
                  </div>
                )}
                {behavior.other_details && (
                  <p className="font-cairo text-sm text-muted-foreground bg-muted/50 rounded-lg px-3 py-2">{behavior.other_details}</p>
                )}
              </section>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
