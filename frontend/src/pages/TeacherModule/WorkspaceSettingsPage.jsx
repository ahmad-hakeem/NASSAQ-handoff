import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2, Save, Building2, Calendar, Clock } from 'lucide-react';

import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Button } from '../../components/ui/button';
import { Checkbox } from '../../components/ui/checkbox';

const WEEKDAYS = [
  { key: 'sun', ar: 'الأحد' },
  { key: 'mon', ar: 'الاثنين' },
  { key: 'tue', ar: 'الثلاثاء' },
  { key: 'wed', ar: 'الأربعاء' },
  { key: 'thu', ar: 'الخميس' },
  { key: 'fri', ar: 'الجمعة' },
  { key: 'sat', ar: 'السبت' },
];

const TIMEZONES = [
  'Asia/Riyadh',
  'Asia/Dubai',
  'Asia/Kuwait',
  'Asia/Baghdad',
  'Asia/Amman',
  'Africa/Cairo',
  'UTC',
];

export default function WorkspaceSettingsPage() {
  const navigate = useNavigate();
  const { api, user } = useAuth();
  const { isRTL } = useTheme();
  const { nassaqError, nassaqSuccess } = useNassaqAlert();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [nameAr, setNameAr] = useState('');
  const [nameEn, setNameEn] = useState('');
  const [logoUrl, setLogoUrl] = useState('');
  const [workingDays, setWorkingDays] = useState([]);
  const [periodsPerDay, setPeriodsPerDay] = useState(7);
  const [periodMinutes, setPeriodMinutes] = useState(45);
  const [tz, setTz] = useState('Asia/Riyadh');
  const [yearLabel, setYearLabel] = useState('');
  const [termLabel, setTermLabel] = useState('');

  const isIndependent = (user?.role || '').toLowerCase() === 'independent_teacher';

  useEffect(() => {
    if (!isIndependent) {
      navigate('/teacher', { replace: true });
    }
  }, [isIndependent, navigate]);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      if (!api || !isIndependent) return;
      setLoading(true);
      try {
        const { data } = await api.get('/independent-teacher/workspace/settings');
        if (cancelled) return;
        setNameAr(data?.name_ar || '');
        setNameEn(data?.name_en || '');
        setLogoUrl(data?.logo_url || '');
        setWorkingDays(Array.isArray(data?.working_days) ? data.working_days : []);
        setPeriodsPerDay(Number(data?.periods_per_day) || 7);
        setPeriodMinutes(Number(data?.period_minutes) || 45);
        setTz(data?.timezone || 'Asia/Riyadh');
        setYearLabel(data?.academic_year_label || '');
        setTermLabel(data?.academic_term_label || '');
      } catch (err) {
        const msg = err?.response?.data?.detail
          || err?.response?.data?.error?.message
          || 'تعذّر تحميل إعدادات مساحتك.';
        nassaqError(msg);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [api, isIndependent, nassaqError]);

  const toggleDay = (key) => {
    setWorkingDays(prev => prev.includes(key) ? prev.filter(d => d !== key) : [...prev, key]);
  };

  const handleSave = async () => {
    if (!nameAr.trim()) {
      nassaqError('اسم المساحة باللغة العربية مطلوب.');
      return;
    }
    if (!workingDays.length) {
      nassaqError('اختر يومًا واحدًا على الأقل ضمن أيام العمل.');
      return;
    }
    if (periodsPerDay < 1 || periodsPerDay > 12) {
      nassaqError('عدد الحصص اليومي يجب أن يكون بين ١ و١٢.');
      return;
    }
    if (periodMinutes < 10 || periodMinutes > 120) {
      nassaqError('مدة الحصة يجب أن تكون بين ١٠ و١٢٠ دقيقة.');
      return;
    }

    setSaving(true);
    try {
      const payload = {
        name_ar: nameAr.trim(),
        name_en: nameEn?.trim() || null,
        logo_url: logoUrl?.trim() || null,
        working_days: workingDays,
        periods_per_day: Number(periodsPerDay),
        period_minutes: Number(periodMinutes),
        timezone: tz,
      };
      if (yearLabel?.trim()) payload.academic_year_label = yearLabel.trim();
      if (termLabel?.trim()) payload.academic_term_label = termLabel.trim();
      await api.put('/independent-teacher/workspace/settings', payload);
      nassaqSuccess('تم حفظ إعدادات مساحتك.');
    } catch (err) {
      const msg = err?.response?.data?.detail
        || err?.response?.data?.error?.message
        || 'تعذّر حفظ إعدادات مساحتك.';
      nassaqError(msg);
    } finally {
      setSaving(false);
    }
  };

  const dir = isRTL ? 'rtl' : 'ltr';

  if (!isIndependent) return null;

  return (
    <div dir={dir} className="min-h-screen bg-slate-50 py-6 px-4">
      <div className="mx-auto max-w-4xl space-y-6">
        <div className="flex items-center justify-between">
          {/* Task #200 §5.8 — Sub-brand header confirmed on workspace-accent token. */}
          <div data-testid="workspace-settings-header">
            <p className="text-xs font-semibold text-workspace-accent uppercase tracking-wide">
              مساحتك التعليمية الخاصة
            </p>
            <h1 className="text-2xl font-bold text-workspace-accent-fg">إعدادات مساحتي</h1>
            <p className="text-sm text-slate-500 mt-1">
              النسخة المختصرة من إعدادات المساحة الخاصة بحساب المعلم المستقل.
            </p>
          </div>
          <Button
            onClick={handleSave}
            disabled={loading || saving}
            className="bg-workspace-accent hover:bg-workspace-accent-fg text-white px-6 h-11"
            data-testid="save-workspace-settings-btn"
          >
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin ms-2" />
            ) : (
              <Save className="h-4 w-4 ms-2" />
            )}
            حفظ التغييرات
          </Button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-24">
            <Loader2 className="h-8 w-8 animate-spin text-emerald-600" />
          </div>
        ) : (
          <>
            {/* Workspace identity */}
            <Card className="bg-white shadow-sm border-emerald-100">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-emerald-600 flex items-center justify-center">
                    <Building2 className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <CardTitle className="text-lg text-emerald-800">هوية المساحة</CardTitle>
                    <CardDescription>اسم المساحة وشعارها كما تظهران للطلاب وأولياء الأمور.</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <Label className="mb-2 block">اسم المساحة بالعربية *</Label>
                    <Input
                      dir="rtl"
                      value={nameAr}
                      onChange={e => setNameAr(e.target.value)}
                      className="h-11 border-slate-200 focus:border-emerald-600 text-right"
                      placeholder="مثال: فصل أ. سعد"
                      data-testid="workspace-name-ar-input"
                    />
                  </div>
                  <div>
                    <Label className="mb-2 block">اسم المساحة بالإنجليزية</Label>
                    <Input
                      dir="ltr"
                      value={nameEn}
                      onChange={e => setNameEn(e.target.value)}
                      className="h-11 border-slate-200 focus:border-emerald-600"
                      placeholder="e.g. Mr. Saad's Class"
                      data-testid="workspace-name-en-input"
                    />
                  </div>
                </div>
                <div>
                  <Label className="mb-2 block">رابط الشعار</Label>
                  <Input
                    dir="ltr"
                    value={logoUrl}
                    onChange={e => setLogoUrl(e.target.value)}
                    className="h-11 border-slate-200 focus:border-emerald-600"
                    placeholder="https://…"
                    data-testid="workspace-logo-url-input"
                  />
                </div>
              </CardContent>
            </Card>

            {/* Schedule baseline */}
            <Card className="bg-white shadow-sm border-emerald-100">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-emerald-600 flex items-center justify-center">
                    <Clock className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <CardTitle className="text-lg text-emerald-800">إعدادات الجدول</CardTitle>
                    <CardDescription>أيام العمل، عدد الحصص، ومدّتها.</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-5">
                <div>
                  <Label className="mb-3 block">أيام العمل *</Label>
                  <div className="flex flex-wrap gap-2">
                    {WEEKDAYS.map(d => {
                      const on = workingDays.includes(d.key);
                      return (
                        <label
                          key={d.key}
                          className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition ${on
                            ? 'bg-emerald-50 border-emerald-500 text-emerald-800'
                            : 'bg-white border-slate-200 text-slate-600 hover:border-emerald-300'
                          }`}
                          data-testid={`workspace-day-${d.key}`}
                        >
                          <Checkbox checked={on} onCheckedChange={() => toggleDay(d.key)} />
                          <span className="text-sm font-medium">{d.ar}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <Label className="mb-2 block">عدد الحصص اليومي</Label>
                    <Input
                      type="number"
                      min={1}
                      max={12}
                      value={periodsPerDay}
                      onChange={e => setPeriodsPerDay(parseInt(e.target.value || '0', 10))}
                      className="h-11 border-slate-200 focus:border-emerald-600"
                      data-testid="workspace-periods-input"
                    />
                  </div>
                  <div>
                    <Label className="mb-2 block">مدة الحصة (دقائق)</Label>
                    <Input
                      type="number"
                      min={10}
                      max={120}
                      value={periodMinutes}
                      onChange={e => setPeriodMinutes(parseInt(e.target.value || '0', 10))}
                      className="h-11 border-slate-200 focus:border-emerald-600"
                      data-testid="workspace-period-minutes-input"
                    />
                  </div>
                  <div>
                    <Label className="mb-2 block">المنطقة الزمنية</Label>
                    <select
                      dir="ltr"
                      value={tz}
                      onChange={e => setTz(e.target.value)}
                      className="w-full h-11 px-3 rounded-md border border-slate-200 focus:border-emerald-600 bg-white text-sm"
                      data-testid="workspace-timezone-select"
                    >
                      {TIMEZONES.map(z => <option key={z} value={z}>{z}</option>)}
                    </select>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Active academic year & term */}
            <Card className="bg-white shadow-sm border-emerald-100">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-emerald-600 flex items-center justify-center">
                    <Calendar className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <CardTitle className="text-lg text-emerald-800">العام والفصل النشط</CardTitle>
                    <CardDescription>إعادة تسمية العام الدراسي والفصل النشط فقط.</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label className="mb-2 block">اسم العام الدراسي</Label>
                  <Input
                    dir="rtl"
                    value={yearLabel}
                    onChange={e => setYearLabel(e.target.value)}
                    className="h-11 border-slate-200 focus:border-emerald-600 text-right"
                    placeholder="مثال: 1447 - 1448 هـ"
                    data-testid="workspace-year-label-input"
                  />
                </div>
                <div>
                  <Label className="mb-2 block">اسم الفصل النشط</Label>
                  <Input
                    dir="rtl"
                    value={termLabel}
                    onChange={e => setTermLabel(e.target.value)}
                    className="h-11 border-slate-200 focus:border-emerald-600 text-right"
                    placeholder="مثال: الفصل الأول"
                    data-testid="workspace-term-label-input"
                  />
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
