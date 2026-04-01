import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Separator } from '../components/ui/separator';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import {
  TYPE_CONFIG, IMPACT_LABELS, REPRODUCIBILITY_OPTIONS, DYNAMIC_FIELD_LABELS,
} from '../components/product-hub';
import {
  Brain, Send, ArrowRight, Monitor, Loader2, CheckCircle2,
  User, FileText, Sparkles, Info, Globe, Smartphone, Laptop,
} from 'lucide-react';

const authHeaders = () => {
  const t = localStorage.getItem('nassaq_token');
  return t ? { Authorization: `Bearer ${t}` } : {};
};

const STEPS = [
  { key: 'reporter', label: 'المُبلِّغ', icon: User },
  { key: 'details', label: 'تفاصيل المشكلة', icon: FileText },
  { key: 'extra', label: 'معلومات إضافية', icon: Info },
  { key: 'review', label: 'مراجعة وإرسال', icon: Send },
];

const IMPACT_OPTIONS = Object.entries(IMPACT_LABELS).map(([value, label]) => ({ value, label }));

export function ProductHubSubmitPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [config, setConfig] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [step, setStep] = useState(0);

  const [form, setForm] = useState({
    issue_type: '',
    employee_name: user?.full_name || '',
    employee_id: '',
    account_type: '',
    section: '',
    page: '',
    current_behavior: '',
    expected_behavior: '',
    url: typeof window !== 'undefined' ? window.location.href : '',
    device: _detectDevice(),
    browser: _detectBrowser(),
    platform: 'web',
    impact: [],
    related_to: [],
    reproducibility: '',
    attachments: [],
  });

  const [dynamicFields, setDynamicFields] = useState({});

  useEffect(() => {
    axios.get('/api/product-hub/config', { headers: authHeaders() })
      .then(r => setConfig(r.data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (user?.full_name && !form.employee_name) {
      setForm(f => ({ ...f, employee_name: user.full_name }));
    }
  }, [user]);

  const dynamicFieldList = config?.dynamic_fields?.[form.issue_type] || [];

  const handleChange = (field, value) => {
    setForm(f => ({ ...f, [field]: value }));
  };

  const toggleImpact = (val) => {
    setForm(f => ({
      ...f,
      impact: f.impact.includes(val) ? f.impact.filter(v => v !== val) : [...f.impact, val],
    }));
  };

  const handleDynamicChange = (field, value) => {
    setDynamicFields(f => ({ ...f, [field]: value }));
  };

  const validateStep = (stepIdx) => {
    if (stepIdx === 0) {
      if (!form.employee_name?.trim() || form.employee_name.trim().length < 3) return 'اسم الموظف مطلوب (3 أحرف على الأقل)';
      if (!form.account_type) return 'نوع الحساب مطلوب';
    }
    if (stepIdx === 1) {
      if (!form.issue_type) return 'نوع المشكلة مطلوب';
      if (!form.section) return 'القسم مطلوب';
      if (!form.page?.trim()) return 'الصفحة مطلوبة';
      if (!form.current_behavior?.trim()) return 'السلوك الحالي مطلوب';
      if (!form.expected_behavior?.trim()) return 'السلوك المتوقع مطلوب';
    }
    return null;
  };

  const goNext = () => {
    const err = validateStep(step);
    if (err) { toast.error(err); return; }
    setStep(s => Math.min(STEPS.length - 1, s + 1));
  };

  const goPrev = () => setStep(s => Math.max(0, s - 1));

  const handleSubmit = async () => {
    for (let i = 0; i < 2; i++) {
      const err = validateStep(i);
      if (err) { toast.error(err); setStep(i); return; }
    }

    setSubmitting(true);
    try {
      const payload = { ...form, ...dynamicFields };
      if (payload.impact && payload.impact.length === 0) delete payload.impact;
      if (payload.related_to && payload.related_to.length === 0) delete payload.related_to;
      if (!payload.reproducibility) delete payload.reproducibility;
      const res = await axios.post('/api/product-hub/issues', payload, { headers: authHeaders() });
      toast.success('تم إرسال المشكلة بنجاح — حكيم يحللها الآن');
      navigate(`/admin/product-hub/issues/${res.data.id}`);
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'object' && detail.message) {
        toast.error(detail.message);
      } else if (typeof detail === 'string') {
        toast.error(detail);
      } else {
        toast.error('فشل في إرسال المشكلة');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50/20" dir="rtl">
        <div className="p-4 lg:p-8 max-w-4xl mx-auto space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-brand-navy flex items-center gap-3">
                <div className="p-2 rounded-xl bg-brand-turquoise/10">
                  <Brain className="h-6 w-6 text-brand-turquoise" />
                </div>
                إرسال مشكلة جديدة
              </h1>
              <p className="text-muted-foreground mt-1 text-sm">حكيم سيحلل مشكلتك ويقترح الأولوية والفريق المناسب</p>
            </div>
            <Button variant="outline" onClick={() => navigate('/admin/product-hub')} className="rounded-lg">
              <ArrowRight className="h-4 w-4 ml-2" />
              رجوع
            </Button>
          </div>

          <div className="flex items-center gap-2 bg-white rounded-xl border p-3 shadow-sm">
            {STEPS.map((s, i) => {
              const Icon = s.icon;
              const isActive = i === step;
              const isDone = i < step;
              return (
                <React.Fragment key={s.key}>
                  <button
                    onClick={() => { if (i < step) setStep(i); }}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                      isActive ? 'bg-brand-turquoise text-white shadow-sm' :
                      isDone ? 'bg-emerald-50 text-emerald-700 cursor-pointer hover:bg-emerald-100' :
                      'text-muted-foreground'
                    }`}
                  >
                    {isDone ? <CheckCircle2 className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
                    <span className="hidden sm:inline">{s.label}</span>
                  </button>
                  {i < STEPS.length - 1 && (
                    <div className={`flex-1 h-0.5 rounded ${i < step ? 'bg-emerald-400' : 'bg-slate-200'}`} />
                  )}
                </React.Fragment>
              );
            })}
          </div>

          {step === 0 && (
            <Card className="border shadow-sm rounded-xl">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <User className="h-4 w-4 text-brand-turquoise" />
                  معلومات المُبلِّغ
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  <div>
                    <Label className="text-sm font-medium">اسم الموظف <span className="text-red-500">*</span></Label>
                    <Input
                      value={form.employee_name}
                      onChange={(e) => handleChange('employee_name', e.target.value)}
                      placeholder="الاسم الكامل"
                      className="mt-1.5 text-right rounded-lg"
                    />
                    <p className="text-[11px] text-muted-foreground mt-1">3 أحرف على الأقل</p>
                  </div>
                  <div>
                    <Label className="text-sm font-medium">رقم الموظف</Label>
                    <Input
                      value={form.employee_id}
                      onChange={(e) => handleChange('employee_id', e.target.value)}
                      placeholder="اختياري"
                      className="mt-1.5 text-right rounded-lg"
                    />
                  </div>
                </div>
                <div>
                  <Label className="text-sm font-medium">نوع الحساب <span className="text-red-500">*</span></Label>
                  <Select value={form.account_type} onValueChange={(v) => handleChange('account_type', v)}>
                    <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue placeholder="اختر نوع الحساب" /></SelectTrigger>
                    <SelectContent>
                      {config?.account_types?.map(t => (
                        <SelectItem key={t} value={t}>{t}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-sm font-medium">المنصة</Label>
                  <div className="flex gap-2 mt-1.5">
                    {[
                      { value: 'web', label: 'ويب', icon: Globe },
                      { value: 'mobile', label: 'موبايل', icon: Smartphone },
                      { value: 'desktop', label: 'سطح المكتب', icon: Laptop },
                    ].map(p => (
                      <button
                        key={p.value}
                        type="button"
                        onClick={() => handleChange('platform', p.value)}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg border-2 text-sm transition-all ${
                          form.platform === p.value
                            ? 'border-brand-turquoise bg-brand-turquoise/10 text-brand-navy font-medium'
                            : 'border-slate-200 text-muted-foreground hover:border-slate-300'
                        }`}
                      >
                        <p.icon className="h-4 w-4" />
                        {p.label}
                      </button>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {step === 1 && (
            <Card className="border shadow-sm rounded-xl">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <FileText className="h-4 w-4 text-brand-turquoise" />
                  تفاصيل المشكلة
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-5">
                <div>
                  <Label className="text-sm font-medium">نوع المشكلة <span className="text-red-500">*</span></Label>
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2 mt-2">
                    {config?.issue_types?.map(t => {
                      const tc = TYPE_CONFIG[t.value] || TYPE_CONFIG.other;
                      const Icon = tc.icon;
                      const selected = form.issue_type === t.value;
                      return (
                        <button
                          key={t.value}
                          type="button"
                          onClick={() => handleChange('issue_type', t.value)}
                          className={`p-3 rounded-xl border-2 text-sm font-medium flex items-center gap-2 transition-all ${
                            selected ? 'border-brand-turquoise bg-brand-turquoise/10 text-brand-navy shadow-sm' : 'border-slate-200 hover:border-slate-300 text-muted-foreground'
                          }`}
                        >
                          <Icon className={`h-4 w-4 ${selected ? tc.color : ''}`} />
                          {t.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  <div>
                    <Label className="text-sm font-medium">القسم <span className="text-red-500">*</span></Label>
                    <Select value={form.section} onValueChange={(v) => handleChange('section', v)}>
                      <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue placeholder="اختر القسم" /></SelectTrigger>
                      <SelectContent>
                        {config?.sections?.map(s => (
                          <SelectItem key={s} value={s}>{s}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-sm font-medium">الصفحة <span className="text-red-500">*</span></Label>
                    <Input
                      value={form.page}
                      onChange={(e) => handleChange('page', e.target.value)}
                      placeholder="اسم الصفحة أو الشاشة"
                      className="mt-1.5 text-right rounded-lg"
                    />
                  </div>
                </div>

                <div>
                  <Label className="text-sm font-medium">السلوك الحالي <span className="text-red-500">*</span></Label>
                  <Textarea
                    value={form.current_behavior}
                    onChange={(e) => handleChange('current_behavior', e.target.value)}
                    placeholder="ما الذي يحدث حالياً؟ صف المشكلة بوضوح..."
                    className="mt-1.5 text-right min-h-[100px] rounded-lg"
                  />
                  <p className="text-[11px] text-muted-foreground mt-1 text-left">{(form.current_behavior || '').length}/5000</p>
                </div>

                <div>
                  <Label className="text-sm font-medium">السلوك المتوقع <span className="text-red-500">*</span></Label>
                  <Textarea
                    value={form.expected_behavior}
                    onChange={(e) => handleChange('expected_behavior', e.target.value)}
                    placeholder="ما الذي يجب أن يحدث بدلاً من ذلك؟"
                    className="mt-1.5 text-right min-h-[100px] rounded-lg"
                  />
                  <p className="text-[11px] text-muted-foreground mt-1 text-left">{(form.expected_behavior || '').length}/5000</p>
                </div>
              </CardContent>
            </Card>
          )}

          {step === 2 && (
            <div className="space-y-5">
              <Card className="border shadow-sm rounded-xl">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Info className="h-4 w-4 text-brand-turquoise" />
                    معلومات إضافية
                  </CardTitle>
                  <p className="text-xs text-muted-foreground">هذه الحقول اختيارية ولكنها تساعد حكيم في التحليل</p>
                </CardHeader>
                <CardContent className="space-y-5">
                  <div>
                    <Label className="text-sm font-medium">التأثير</Label>
                    <div className="flex flex-wrap gap-2 mt-2">
                      {IMPACT_OPTIONS.map(opt => (
                        <button
                          key={opt.value}
                          type="button"
                          onClick={() => toggleImpact(opt.value)}
                          className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all ${
                            form.impact.includes(opt.value)
                              ? 'border-brand-turquoise bg-brand-turquoise/10 text-brand-navy'
                              : 'border-slate-200 text-muted-foreground hover:border-slate-300'
                          }`}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <Label className="text-sm font-medium">قابلية التكرار</Label>
                    <div className="flex gap-2 mt-1.5">
                      {REPRODUCIBILITY_OPTIONS.map(opt => (
                        <button
                          key={opt.value}
                          type="button"
                          onClick={() => handleChange('reproducibility', opt.value)}
                          className={`px-4 py-2 rounded-lg border-2 text-sm transition-all ${
                            form.reproducibility === opt.value
                              ? 'border-brand-turquoise bg-brand-turquoise/10 text-brand-navy font-medium'
                              : 'border-slate-200 text-muted-foreground hover:border-slate-300'
                          }`}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>

              {dynamicFieldList.length > 0 && (
                <Card className="border shadow-sm rounded-xl">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center gap-2">
                      <Sparkles className="h-4 w-4 text-brand-turquoise" />
                      حقول خاصة بنوع المشكلة
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {dynamicFieldList.filter(f => f !== 'reproducibility').map(field => (
                      <div key={field}>
                        <Label className="text-sm font-medium">{DYNAMIC_FIELD_LABELS[field] || field}</Label>
                        {field.includes('steps') || field.includes('journey') || field.includes('details') || field.includes('value') ? (
                          <Textarea
                            value={dynamicFields[field] || ''}
                            onChange={(e) => handleDynamicChange(field, e.target.value)}
                            className="mt-1.5 text-right min-h-[80px] rounded-lg"
                          />
                        ) : (
                          <Input
                            value={dynamicFields[field] || ''}
                            onChange={(e) => handleDynamicChange(field, e.target.value)}
                            className="mt-1.5 text-right rounded-lg"
                          />
                        )}
                      </div>
                    ))}
                  </CardContent>
                </Card>
              )}
            </div>
          )}

          {step === 3 && (
            <div className="space-y-5">
              <Card className="border shadow-sm rounded-xl">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-brand-turquoise" />
                    مراجعة قبل الإرسال
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <ReviewRow label="اسم الموظف" value={form.employee_name} />
                  <ReviewRow label="نوع الحساب" value={form.account_type} />
                  <ReviewRow label="المنصة" value={form.platform} />
                  <Separator />
                  <ReviewRow label="نوع المشكلة" value={TYPE_CONFIG[form.issue_type]?.label || form.issue_type} />
                  <ReviewRow label="القسم" value={form.section} />
                  <ReviewRow label="الصفحة" value={form.page} />
                  <Separator />
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">السلوك الحالي</p>
                    <p className="text-sm bg-red-50 p-3 rounded-lg border border-red-100">{form.current_behavior}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">السلوك المتوقع</p>
                    <p className="text-sm bg-emerald-50 p-3 rounded-lg border border-emerald-100">{form.expected_behavior}</p>
                  </div>
                  {form.impact.length > 0 && (
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">التأثير</p>
                      <div className="flex flex-wrap gap-1.5">
                        {form.impact.map(i => (
                          <Badge key={i} variant="secondary" className="text-[11px]">{IMPACT_LABELS[i] || i}</Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {form.reproducibility && (
                    <ReviewRow label="قابلية التكرار" value={REPRODUCIBILITY_OPTIONS.find(o => o.value === form.reproducibility)?.label || form.reproducibility} />
                  )}
                </CardContent>
              </Card>

              <Card className="border shadow-sm rounded-xl border-brand-turquoise/30 bg-brand-turquoise/5">
                <CardContent className="p-4">
                  <div className="flex items-center gap-3 text-sm">
                    <Brain className="h-5 w-5 text-brand-turquoise flex-shrink-0" />
                    <div>
                      <p className="font-medium text-brand-navy">حكيم سيحلل مشكلتك تلقائياً</p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        سيقترح الأولوية والفريق المناسب ويكتشف المشاكل المشابهة ويُنشئ عنواناً واضحاً
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card className="border shadow-sm rounded-xl bg-slate-50">
                <CardContent className="p-3 flex items-center gap-3 text-xs text-muted-foreground">
                  <Monitor className="h-4 w-4 flex-shrink-0" />
                  <span>سيتم التقاط تلقائياً: الجهاز ({form.device}) • المتصفح ({form.browser}) • التاريخ والوقت</span>
                </CardContent>
              </Card>
            </div>
          )}

          <div className="flex items-center justify-between pt-2">
            <div>
              {step > 0 && (
                <Button variant="outline" onClick={goPrev} className="rounded-lg">
                  <ArrowRight className="h-4 w-4 ml-2" />
                  السابق
                </Button>
              )}
            </div>
            <div className="flex gap-3">
              <Button variant="outline" onClick={() => navigate('/admin/product-hub')} className="rounded-lg">
                إلغاء
              </Button>
              {step < STEPS.length - 1 ? (
                <Button onClick={goNext} className="bg-brand-navy hover:bg-brand-navy/90 text-white rounded-lg min-w-[120px]">
                  التالي
                  <ArrowRight className="h-4 w-4 mr-2 rotate-180" />
                </Button>
              ) : (
                <Button
                  onClick={handleSubmit}
                  disabled={submitting}
                  className="bg-brand-turquoise hover:bg-brand-turquoise/90 text-white rounded-lg min-w-[180px] shadow-lg shadow-brand-turquoise/20"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="h-4 w-4 ml-2 animate-spin" />
                      حكيم يحلل...
                    </>
                  ) : (
                    <>
                      <Send className="h-4 w-4 ml-2" />
                      إرسال المشكلة
                    </>
                  )}
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </Sidebar>
  );
}

function ReviewRow({ label, value }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium text-brand-navy">{value || '—'}</span>
    </div>
  );
}

function _detectDevice() {
  if (typeof navigator === 'undefined') return 'unknown';
  const ua = navigator.userAgent;
  if (/mobile/i.test(ua)) return 'mobile';
  if (/tablet|ipad/i.test(ua)) return 'tablet';
  return 'desktop';
}

function _detectBrowser() {
  if (typeof navigator === 'undefined') return 'unknown';
  const ua = navigator.userAgent;
  if (ua.includes('Chrome') && !ua.includes('Edg')) return 'Chrome';
  if (ua.includes('Firefox')) return 'Firefox';
  if (ua.includes('Safari') && !ua.includes('Chrome')) return 'Safari';
  if (ua.includes('Edg')) return 'Edge';
  return 'Other';
}

export default ProductHubSubmitPage;
