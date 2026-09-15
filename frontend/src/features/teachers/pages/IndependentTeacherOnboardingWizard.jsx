import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, ArrowRight, ArrowLeft, Check, Sparkles } from 'lucide-react';

import { useAuth } from '@/shared/contexts/AuthContext';
import { useTheme, useTranslation } from '@/shared/contexts/ThemeContext';
import { useNassaqAlert } from '@/shared/components/ui/NassaqAlertDialog';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Card, CardContent, CardHeader } from '@/shared/components/ui/card';
import { Checkbox } from '@/shared/components/ui/checkbox';
import { ImageCropModal } from '@/shared/components/ui/ImageCropModal';
import { formatHijriDate, getHijriDate } from '@/shared/models/utils/hijriDate';
import { getApiErrorMessage } from '@/shared/models/utils/apiError';

const WEEKDAYS = [
  { key: 'sun', ar: 'الأحد', en: 'Sun' },
  { key: 'mon', ar: 'الاثنين', en: 'Mon' },
  { key: 'tue', ar: 'الثلاثاء', en: 'Tue' },
  { key: 'wed', ar: 'الأربعاء', en: 'Wed' },
  { key: 'thu', ar: 'الخميس', en: 'Thu' },
  { key: 'fri', ar: 'الجمعة', en: 'Fri' },
  { key: 'sat', ar: 'السبت', en: 'Sat' },
];

const SAUDI_DEFAULT_DAYS = ['sun', 'mon', 'tue', 'wed', 'thu'];

export default function IndependentTeacherOnboardingWizard() {
  const navigate = useNavigate();
  const { user, applyAuthSession, fetchPermissions, api } = useAuth();
  const { isRTL } = useTheme();
  const { t } = useTranslation();
  const { nassaqError, nassaqWarning, nassaqSuccess, nassaqConfirm } = useNassaqAlert();
  const [avatarCropOpen, setAvatarCropOpen] = useState(false);

  const todayHijri = useMemo(() => getHijriDate(new Date()), []);
  const defaultYearLabel = useMemo(() => {
    const start = todayHijri.hijriYear;
    return `${start} - ${start + 1} هـ`;
  }, [todayHijri]);

  const [step, setStep] = useState(1);
  const [submitting, setSubmitting] = useState(false);

  // Step 1 — workspace identity
  const [workspaceNameAr, setWorkspaceNameAr] = useState('');
  const [workspaceNameEn, setWorkspaceNameEn] = useState('');
  const [avatarUrl, setAvatarUrl] = useState('');

  // Step 2 — academic + schedule baseline
  const [academicYearLabel, setAcademicYearLabel] = useState(defaultYearLabel);
  const [academicYearStart, setAcademicYearStart] = useState('');
  const [academicYearEnd, setAcademicYearEnd] = useState('');
  const [termLabel, setTermLabel] = useState('الفصل الأول');
  const [workingDays, setWorkingDays] = useState(SAUDI_DEFAULT_DAYS);
  const [periodsPerDay, setPeriodsPerDay] = useState(7);

  // Step 3 — optional first class
  const [createFirstClass, setCreateFirstClass] = useState(false);
  const [firstClassName, setFirstClassName] = useState('');
  const [firstClassGrade, setFirstClassGrade] = useState('');
  const [firstClassSubject, setFirstClassSubject] = useState('');

  // Guardrail — wrong role / already materialised: bounce out.
  useEffect(() => {
    if (!user) return;
    if (user.role !== 'independent_teacher') {
      navigate('/dashboard', { replace: true });
      return;
    }
    if (user.tenant_id) {
      navigate('/teacher', { replace: true });
    }
  }, [user, navigate]);

  const toggleDay = (dayKey) => {
    setWorkingDays((prev) =>
      prev.includes(dayKey) ? prev.filter((d) => d !== dayKey) : [...prev, dayKey]
    );
  };

  const validateStep = (which) => {
    if (which === 1) {
      if (!workspaceNameAr.trim()) {
        nassaqWarning('اسم المساحة باللغة العربية مطلوب.');
        return false;
      }
    }
    if (which === 2) {
      if (!academicYearLabel.trim()) {
        nassaqWarning('عنوان السنة الدراسية مطلوب.');
        return false;
      }
      if (workingDays.length === 0) {
        nassaqWarning('اختر يومًا واحدًا على الأقل ضمن أيام العمل.');
        return false;
      }
      if (periodsPerDay < 1 || periodsPerDay > 12) {
        nassaqWarning('عدد الحصص اليومي يجب أن يكون بين ١ و١٢.');
        return false;
      }
    }
    if (which === 3 && createFirstClass) {
      if (!firstClassName.trim()) {
        nassaqWarning('اسم الفصل مطلوب.');
        return false;
      }
    }
    return true;
  };

  // Step transition is gated by NassaqAlertDialog confirms so the user
  // explicitly acknowledges each step's data before it freezes into the
  // bootstrap payload (spec §5.1 first-login orchestration).
  const STEP_CONFIRM_LABELS = {
    1: { title: 'تأكيد بيانات المساحة', message: 'هل البيانات أعلاه صحيحة؟ سننتقل لخطوة السنة والجدول.' },
    2: { title: 'تأكيد السنة والجدول', message: 'هل تريد المتابعة بهذه السنة الدراسية وأيام العمل؟' },
  };
  const next = () => {
    if (!validateStep(step)) return;
    const cfg = STEP_CONFIRM_LABELS[step];
    if (cfg) {
      nassaqConfirm(
        cfg.message,
        () => setStep((s) => Math.min(3, s + 1)),
        { title: cfg.title, confirmText: 'متابعة', cancelText: 'مراجعة' }
      );
      return;
    }
    setStep((s) => Math.min(3, s + 1));
  };
  const back = () => setStep((s) => Math.max(1, s - 1));

  const handleAvatarCropSave = async (base64) => {
    // ImageCropModal hands back a data:image/...;base64,... URL. We
    // store it verbatim — bootstrap forwards it to the new workspace.
    setAvatarUrl(base64);
  };

  const submit = async () => {
    if (!validateStep(1) || !validateStep(2) || !validateStep(3)) return;

    // Final confirm — spec requires an explicit acknowledgement before
    // the irreversible workspace materialisation.
    nassaqConfirm(
      'سيتم إنشاء مساحتك الآن بشكل دائم. هل أنت متأكد؟',
      () => doSubmit(),
      { title: 'إنشاء المساحة', confirmText: 'نعم، أنشئ المساحة', cancelText: 'إلغاء' }
    );
  };

  const doSubmit = async () => {
    setSubmitting(true);
    try {
      const payload = {
        workspace_name_ar: workspaceNameAr.trim(),
        workspace_name_en: workspaceNameEn.trim() || null,
        avatar_url: avatarUrl.trim() || null,
        academic_year_label: academicYearLabel.trim(),
        academic_year_start: academicYearStart || null,
        academic_year_end: academicYearEnd || null,
        term_label: termLabel.trim() || null,
        working_days: workingDays,
        periods_per_day: Number(periodsPerDay) || 7,
        first_class: createFirstClass
          ? {
              name: firstClassName.trim(),
              grade_level: firstClassGrade.trim() || null,
              subject: firstClassSubject.trim() || null,
            }
          : null,
      };

      // IMPORTANT: must POST through the AuthContext-scoped axios `api`
      // instance — its response interceptor implements the global step-up
      // modal contract for 401 + MFA_STEPUP_REQUIRED (auto-pops the
      // dialog, awaits a fresh assertion, replays this very POST with a
      // freshly-stamped bearer). A raw axios.post would bypass that
      // interceptor and surface the 401 as a generic error.
      const res = await api.post('/independent-teacher/bootstrap', payload);

      const data = res.data || {};
      if (data.access_token && data.user) {
        applyAuthSession({
          access_token: data.access_token,
          refresh_token: data.refresh_token,
          user: data.user,
        });
        // Rebuild the cached permission set under the freshly-set
        // tenant_id so any IT-scoped UI gates the user lands on next
        // see the materialised workspace's permissions.
        try {
          await fetchPermissions({ force: true });
        } catch {
          /* non-fatal — /auth/me/permissions has its own retry path */
        }
      }
      nassaqSuccess('تم إنشاء مساحتك بنجاح.');
      navigate('/teacher', { replace: true });
    } catch (err) {
      // Recent-MFA failure surfaces as 401 + MFA_STEPUP_REQUIRED and
      // is fully owned by the global axios step-up modal interceptor
      // (AuthContext.js): it pops the step-up dialog and replays this
      // very POST with a freshly-stamped token. We deliberately do NOT
      // route the user away here.
      const errBody = err?.response?.data?.error || getApiErrorMessage(err);
      const code = typeof errBody === 'object' ? errBody?.code : null;
      const message =
        (typeof errBody === 'object' ? errBody?.message : errBody) ||
        'تعذّر إنشاء مساحتك. حاول مرة أخرى.';

      if (code === 'mfa_enrollment_required') {
        nassaqWarning(message);
        navigate('/auth/mfa/enroll');
        return;
      }
      nassaqError(typeof message === 'string' ? message : 'تعذّر إنشاء مساحتك.');
    } finally {
      setSubmitting(false);
    }
  };

  const stepLabel = (n, label) => (
    <div className="flex items-center gap-2">
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
          step >= n ? 'bg-emerald-600 text-white' : 'bg-slate-200 text-slate-600'
        }`}
      >
        {step > n ? <Check className="w-4 h-4" /> : n}
      </div>
      <span className={step === n ? 'font-semibold' : 'text-slate-500'}>{label}</span>
    </div>
  );

  return (
    <div
      dir={isRTL ? 'rtl' : 'ltr'}
      className="min-h-screen bg-gradient-to-br from-workspace-accent-light via-white to-sky-50 p-4 sm:p-8"
      data-testid="it-onboarding-wizard"
    >
      <div className="max-w-3xl mx-auto">
        {/* Task #200 §5.8 — Sub-brand header. Canonical IT label per spec:
            "مساحتك التعليمية الخاصة". Workspace-accent token applied. */}
        <div className="mb-6 flex items-center gap-3" data-testid="it-onboarding-header">
          <div className="w-11 h-11 rounded-2xl bg-workspace-accent flex items-center justify-center shadow-sm">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-workspace-accent-fg">مرحبًا بك في نَسَّق</h1>
            <p className="text-xs font-semibold text-workspace-accent uppercase tracking-wide">
              مساحتك التعليمية الخاصة
            </p>
            <p className="text-sm text-slate-600 mt-0.5">
              {formatHijriDate(new Date(), { locale: 'ar', includeWeekday: true })}
            </p>
          </div>
        </div>

        <Card className="border-emerald-100 shadow-sm">
          <CardHeader className="border-b">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              {stepLabel(1, 'مساحتك')}
              <div className="h-px bg-slate-200 flex-1 min-w-4" />
              {stepLabel(2, 'السنة والجدول')}
              <div className="h-px bg-slate-200 flex-1 min-w-4" />
              {stepLabel(3, 'فصلك الأول')}
            </div>
          </CardHeader>

          <CardContent className="p-6 space-y-5">
            {step === 1 && (
              <div className="space-y-4" data-testid="it-onboarding-step-1">
                <div>
                  <Label htmlFor="ws-name-ar">اسم المساحة (بالعربية)</Label>
                  <Input
                    id="ws-name-ar"
                    value={workspaceNameAr}
                    onChange={(e) => setWorkspaceNameAr(e.target.value)}
                    placeholder="مثال: أكاديمية الأستاذ أحمد"
                    data-testid="it-ws-name-ar"
                  />
                </div>
                <div>
                  <Label htmlFor="ws-name-en">Workspace name (English, optional)</Label>
                  <Input
                    id="ws-name-en"
                    value={workspaceNameEn}
                    onChange={(e) => setWorkspaceNameEn(e.target.value)}
                    placeholder="Ahmed Academy"
                  />
                </div>
                <div>
                  <Label>شعار المساحة (اختياري)</Label>
                  <div className="mt-2 flex items-center gap-3">
                    <div className="w-14 h-14 rounded-full overflow-hidden border border-emerald-200 bg-slate-50 flex items-center justify-center">
                      {avatarUrl ? (
                        <img
                          src={avatarUrl}
                          alt="workspace avatar"
                          className="w-full h-full object-cover"
                          data-testid="it-avatar-preview"
                        />
                      ) : (
                        <Sparkles className="w-5 h-5 text-emerald-500/60" />
                      )}
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setAvatarCropOpen(true)}
                      data-testid="it-avatar-upload-btn"
                    >
                      {avatarUrl ? 'تغيير الشعار' : 'رفع شعار'}
                    </Button>
                    {avatarUrl && (
                      <Button
                        type="button"
                        variant="ghost"
                        onClick={() => setAvatarUrl('')}
                      >
                        إزالة
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="space-y-4" data-testid="it-onboarding-step-2">
                <div>
                  <Label htmlFor="ay-label">عنوان السنة الدراسية (هجري)</Label>
                  <Input
                    id="ay-label"
                    value={academicYearLabel}
                    onChange={(e) => setAcademicYearLabel(e.target.value)}
                    placeholder={defaultYearLabel}
                    data-testid="it-ay-label"
                  />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <Label htmlFor="ay-start">تاريخ البداية (ميلادي)</Label>
                    <Input
                      id="ay-start"
                      type="date"
                      value={academicYearStart}
                      onChange={(e) => setAcademicYearStart(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="ay-end">تاريخ النهاية (ميلادي)</Label>
                    <Input
                      id="ay-end"
                      type="date"
                      value={academicYearEnd}
                      onChange={(e) => setAcademicYearEnd(e.target.value)}
                    />
                  </div>
                </div>
                <div>
                  <Label htmlFor="term-label">اسم الفصل الدراسي</Label>
                  <Input
                    id="term-label"
                    value={termLabel}
                    onChange={(e) => setTermLabel(e.target.value)}
                  />
                </div>

                <div>
                  <Label>أيام العمل</Label>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {WEEKDAYS.map((d) => {
                      const active = workingDays.includes(d.key);
                      return (
                        <button
                          key={d.key}
                          type="button"
                          onClick={() => toggleDay(d.key)}
                          className={`px-3 py-1.5 rounded-full text-sm border transition ${
                            active
                              ? 'bg-emerald-600 text-white border-emerald-600'
                              : 'bg-white text-slate-700 border-slate-300'
                          }`}
                          data-testid={`it-day-${d.key}`}
                        >
                          {d.ar}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div>
                  <Label htmlFor="periods">عدد الحصص اليومي</Label>
                  <Input
                    id="periods"
                    type="number"
                    min={1}
                    max={12}
                    value={periodsPerDay}
                    onChange={(e) => setPeriodsPerDay(Number(e.target.value || 0))}
                    data-testid="it-periods-per-day"
                  />
                </div>
              </div>
            )}

            {step === 3 && (
              <div className="space-y-4" data-testid="it-onboarding-step-3">
                <div className="flex items-start gap-2">
                  <Checkbox
                    id="create-first-class"
                    checked={createFirstClass}
                    onCheckedChange={(v) => setCreateFirstClass(Boolean(v))}
                  />
                  <Label htmlFor="create-first-class" className="leading-relaxed">
                    أرغب بإنشاء فصلي الأول الآن (يمكنك تخطّي هذه الخطوة وإضافة الفصول لاحقًا).
                  </Label>
                </div>

                {createFirstClass && (
                  <div className="space-y-3 border rounded-md p-4 bg-slate-50">
                    <div>
                      <Label htmlFor="cls-name">اسم الفصل</Label>
                      <Input
                        id="cls-name"
                        value={firstClassName}
                        onChange={(e) => setFirstClassName(e.target.value)}
                        placeholder="مثال: ١-أ"
                        data-testid="it-class-name"
                      />
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div>
                        <Label htmlFor="cls-grade">المرحلة / الصف</Label>
                        <Input
                          id="cls-grade"
                          value={firstClassGrade}
                          onChange={(e) => setFirstClassGrade(e.target.value)}
                          placeholder="مثال: الأول الابتدائي"
                        />
                      </div>
                      <div>
                        <Label htmlFor="cls-subject">المادة (اختياري)</Label>
                        <Input
                          id="cls-subject"
                          value={firstClassSubject}
                          onChange={(e) => setFirstClassSubject(e.target.value)}
                          placeholder="مثال: الرياضيات"
                        />
                      </div>
                    </div>
                  </div>
                )}

                <p className="text-xs text-slate-500">
                  بعد الإنشاء سيتم تجهيز مساحتك وفتح لوحة المعلم.
                </p>
              </div>
            )}

            <div className="flex items-center justify-between pt-2 gap-3">
              <Button
                type="button"
                variant="outline"
                onClick={back}
                disabled={step === 1 || submitting}
              >
                {isRTL ? <ArrowRight className="w-4 h-4" /> : <ArrowLeft className="w-4 h-4" />}
                <span className="mx-1">السابق</span>
              </Button>

              {step < 3 ? (
                <Button type="button" onClick={next} disabled={submitting}>
                  <span className="mx-1">التالي</span>
                  {isRTL ? <ArrowLeft className="w-4 h-4" /> : <ArrowRight className="w-4 h-4" />}
                </Button>
              ) : (
                <Button
                  type="button"
                  onClick={submit}
                  disabled={submitting}
                  data-testid="it-onboarding-submit"
                >
                  {submitting ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Check className="w-4 h-4" />
                  )}
                  <span className="mx-1">إنشاء المساحة</span>
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      <ImageCropModal
        open={avatarCropOpen}
        onOpenChange={setAvatarCropOpen}
        onSave={handleAvatarCropSave}
        isRTL={isRTL}
      />
    </div>
  );
}
