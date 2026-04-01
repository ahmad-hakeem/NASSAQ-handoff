import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Brain, Send, ArrowRight, Bug, AlertTriangle, Lightbulb,
  Zap, Eye, Shield, Settings, Link2, HelpCircle, FileText,
  Monitor, Smartphone, Globe, ChevronDown, ChevronUp, Loader2
} from 'lucide-react';

const TYPE_ICONS = {
  bug: Bug, error: AlertTriangle, ui_issue: Eye, ux_issue: Lightbulb,
  performance: Zap, content: FileText, feature_request: Lightbulb,
  improvement: Settings, permission: Shield, workflow: Settings,
  integration: Link2, other: HelpCircle,
};

const DYNAMIC_FIELD_LABELS = {
  steps_to_reproduce: 'خطوات إعادة الإنتاج',
  reproducibility: 'قابلية التكرار',
  error_message: 'رسالة الخطأ',
  error_code: 'رمز الخطأ',
  screen_area: 'منطقة الشاشة',
  affected_elements: 'العناصر المتأثرة',
  user_journey: 'رحلة المستخدم',
  pain_point: 'نقطة الألم',
  load_time: 'وقت التحميل',
  affected_operation: 'العملية المتأثرة',
  content_location: 'موقع المحتوى',
  content_type: 'نوع المحتوى',
  use_case: 'حالة الاستخدام',
  business_value: 'القيمة التجارية',
  improvement_area: 'مجال التحسين',
  expected_impact: 'الأثر المتوقع',
  affected_role: 'الدور المتأثر',
  expected_access: 'الصلاحية المتوقعة',
  workflow_name: 'اسم سير العمل',
  broken_step: 'الخطوة المعطلة',
  integration_name: 'اسم التكامل',
  api_endpoint: 'نقطة API',
  additional_details: 'تفاصيل إضافية',
};

const REPRODUCIBILITY_OPTIONS = [
  { value: 'always', label: 'دائماً' },
  { value: 'sometimes', label: 'أحياناً' },
  { value: 'rarely', label: 'نادراً' },
  { value: 'once', label: 'مرة واحدة' },
];

export function ProductHubSubmitPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [config, setConfig] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [showDynamic, setShowDynamic] = useState(false);

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
  });

  const [dynamicFields, setDynamicFields] = useState({});

  useEffect(() => {
    axios.get('/api/product-hub/config')
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

  const handleDynamicChange = (field, value) => {
    setDynamicFields(f => ({ ...f, [field]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!form.employee_name?.trim()) {
      toast.error('اسم الموظف مطلوب');
      return;
    }
    if (!form.issue_type) {
      toast.error('نوع المشكلة مطلوب');
      return;
    }
    if (!form.account_type) {
      toast.error('نوع الحساب مطلوب');
      return;
    }
    if (!form.section) {
      toast.error('القسم مطلوب');
      return;
    }
    if (!form.page?.trim()) {
      toast.error('الصفحة مطلوبة');
      return;
    }
    if (!form.current_behavior?.trim()) {
      toast.error('السلوك الحالي مطلوب');
      return;
    }
    if (!form.expected_behavior?.trim()) {
      toast.error('السلوك المتوقع مطلوب');
      return;
    }

    setSubmitting(true);
    try {
      const payload = { ...form, ...dynamicFields };
      const res = await axios.post('/api/product-hub/issues', payload);
      toast.success('تم إرسال المشكلة بنجاح');
      navigate(`/admin/product-hub/issues/${res.data.id}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'فشل في إرسال المشكلة');
    } finally {
      setSubmitting(false);
    }
  };

  const TypeIcon = TYPE_ICONS[form.issue_type] || Bug;

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50/30" dir="rtl">
        <div className="p-4 lg:p-6 max-w-4xl mx-auto space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-brand-navy flex items-center gap-3">
                <Brain className="h-7 w-7 text-brand-turquoise" />
                إرسال مشكلة جديدة
              </h1>
              <p className="text-muted-foreground mt-1">حكيم سيحلل مشكلتك ويقترح الأولوية والفريق المناسب</p>
            </div>
            <Button variant="outline" onClick={() => navigate('/admin/product-hub')}>
              <ArrowRight className="h-4 w-4 ml-2" />
              رجوع
            </Button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            <Card className="border shadow-sm">
              <CardHeader className="pb-3">
                <CardTitle className="text-base">معلومات المُبلِّغ</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <Label className="text-sm font-medium">اسم الموظف <span className="text-red-500">*</span></Label>
                    <Input
                      value={form.employee_name}
                      onChange={(e) => handleChange('employee_name', e.target.value)}
                      placeholder="الاسم الكامل"
                      className="mt-1 text-right"
                    />
                  </div>
                  <div>
                    <Label className="text-sm font-medium">رقم الموظف</Label>
                    <Input
                      value={form.employee_id}
                      onChange={(e) => handleChange('employee_id', e.target.value)}
                      placeholder="اختياري"
                      className="mt-1 text-right"
                    />
                  </div>
                </div>
                <div>
                  <Label className="text-sm font-medium">نوع الحساب <span className="text-red-500">*</span></Label>
                  <Select value={form.account_type} onValueChange={(v) => handleChange('account_type', v)}>
                    <SelectTrigger className="mt-1"><SelectValue placeholder="اختر نوع الحساب" /></SelectTrigger>
                    <SelectContent>
                      {config?.account_types?.map(t => (
                        <SelectItem key={t} value={t}>{t}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </CardContent>
            </Card>

            <Card className="border shadow-sm">
              <CardHeader className="pb-3">
                <CardTitle className="text-base">تفاصيل المشكلة</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label className="text-sm font-medium">نوع المشكلة <span className="text-red-500">*</span></Label>
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2 mt-2">
                    {config?.issue_types?.map(t => {
                      const Icon = TYPE_ICONS[t.value] || Bug;
                      const selected = form.issue_type === t.value;
                      return (
                        <button
                          key={t.value}
                          type="button"
                          onClick={() => handleChange('issue_type', t.value)}
                          className={`p-3 rounded-lg border-2 text-sm font-medium flex items-center gap-2 transition-all
                            ${selected ? 'border-brand-turquoise bg-brand-turquoise/10 text-brand-navy' : 'border-gray-200 hover:border-gray-300 text-muted-foreground'}`}
                        >
                          <Icon className={`h-4 w-4 ${selected ? 'text-brand-turquoise' : ''}`} />
                          {t.label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <Label className="text-sm font-medium">القسم <span className="text-red-500">*</span></Label>
                    <Select value={form.section} onValueChange={(v) => handleChange('section', v)}>
                      <SelectTrigger className="mt-1"><SelectValue placeholder="اختر القسم" /></SelectTrigger>
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
                      className="mt-1 text-right"
                    />
                  </div>
                </div>

                <div>
                  <Label className="text-sm font-medium">السلوك الحالي <span className="text-red-500">*</span></Label>
                  <Textarea
                    value={form.current_behavior}
                    onChange={(e) => handleChange('current_behavior', e.target.value)}
                    placeholder="ما الذي يحدث حالياً؟"
                    className="mt-1 text-right min-h-[100px]"
                  />
                </div>

                <div>
                  <Label className="text-sm font-medium">السلوك المتوقع <span className="text-red-500">*</span></Label>
                  <Textarea
                    value={form.expected_behavior}
                    onChange={(e) => handleChange('expected_behavior', e.target.value)}
                    placeholder="ما الذي يجب أن يحدث؟"
                    className="mt-1 text-right min-h-[100px]"
                  />
                </div>
              </CardContent>
            </Card>

            {dynamicFieldList.length > 0 && (
              <Card className="border shadow-sm">
                <CardHeader className="pb-3 cursor-pointer" onClick={() => setShowDynamic(!showDynamic)}>
                  <CardTitle className="text-base flex items-center justify-between">
                    <span>حقول إضافية ({DYNAMIC_FIELD_LABELS[dynamicFieldList[0]] ? `بناءً على: ${config?.issue_types?.find(t => t.value === form.issue_type)?.label}` : ''})</span>
                    {showDynamic ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                  </CardTitle>
                </CardHeader>
                {showDynamic && (
                  <CardContent className="space-y-4">
                    {dynamicFieldList.map(field => (
                      <div key={field}>
                        <Label className="text-sm font-medium">{DYNAMIC_FIELD_LABELS[field] || field}</Label>
                        {field === 'reproducibility' ? (
                          <Select value={dynamicFields[field] || ''} onValueChange={(v) => handleDynamicChange(field, v)}>
                            <SelectTrigger className="mt-1"><SelectValue placeholder="اختر" /></SelectTrigger>
                            <SelectContent>
                              {REPRODUCIBILITY_OPTIONS.map(o => (
                                <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        ) : field.includes('steps') || field.includes('journey') || field.includes('details') ? (
                          <Textarea
                            value={dynamicFields[field] || ''}
                            onChange={(e) => handleDynamicChange(field, e.target.value)}
                            className="mt-1 text-right min-h-[80px]"
                          />
                        ) : (
                          <Input
                            value={dynamicFields[field] || ''}
                            onChange={(e) => handleDynamicChange(field, e.target.value)}
                            className="mt-1 text-right"
                          />
                        )}
                      </div>
                    ))}
                  </CardContent>
                )}
              </Card>
            )}

            <Card className="border shadow-sm border-brand-turquoise/30 bg-brand-turquoise/5">
              <CardContent className="p-4">
                <div className="flex items-center gap-3 text-sm text-muted-foreground">
                  <Monitor className="h-4 w-4" />
                  <span>سيتم التقاط: URL, الجهاز ({form.device}), المتصفح ({form.browser}) تلقائياً</span>
                </div>
              </CardContent>
            </Card>

            <div className="flex justify-end gap-3">
              <Button type="button" variant="outline" onClick={() => navigate('/admin/product-hub')}>
                إلغاء
              </Button>
              <Button
                type="submit"
                disabled={submitting}
                className="bg-brand-turquoise hover:bg-brand-turquoise/90 text-white min-w-[160px]"
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
            </div>
          </form>
        </div>
      </div>
    </Sidebar>
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
