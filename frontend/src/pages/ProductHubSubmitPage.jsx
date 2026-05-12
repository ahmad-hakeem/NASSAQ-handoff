import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Separator } from '../components/ui/separator';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Send, ArrowRight, Monitor, Loader2, CheckCircle2,
  User, FileText, Sparkles, Wand2, MessageCircle, Zap,
  Eye, Shield, Lightbulb, ArrowLeft, PenLine, RefreshCw, Calendar, Clock,
  ImagePlus, X, Image as ImageIcon, Camera,
} from 'lucide-react';

const authHeaders = () => {
  const t = localStorage.getItem('nassaq_token');
  return t ? { Authorization: `Bearer ${t}` } : {};
};

const HAKIM_FALLBACK = '/hakim-poses/friendly-greeting.png';
const hakimImgError = (e) => { if (e.target.src !== HAKIM_FALLBACK) e.target.src = HAKIM_FALLBACK; };

const MAX_EVIDENCE_IMAGES = 3;
const MAX_EVIDENCE_SIZE_MB = 5;
const ALLOWED_EVIDENCE_TYPES = ['image/png', 'image/jpeg', 'image/webp'];

const STEPS = [
  { key: 'reporter', label: 'المُبلِّغ', icon: User },
  { key: 'details', label: 'تفاصيل التحدي', icon: FileText },
  { key: 'review', label: 'مراجعة وإرسال', icon: Send },
];

const COMMENT_TYPE_OPTIONS = [
  { value: 'bug', labelAr: 'خطأ برمجي', labelEn: 'Bugs' },
  { value: 'error', labelAr: 'خطأ تقني', labelEn: 'Errors' },
  { value: 'ui_issue', labelAr: 'ملاحظة واجهة', labelEn: 'UI Issues' },
  { value: 'ux_issue', labelAr: 'ملاحظة تجربة مستخدم', labelEn: 'UX Issues' },
  { value: 'performance_issue', labelAr: 'ملاحظة أداء', labelEn: 'Performance Issues' },
  { value: 'feature_request', labelAr: 'طلب ميزة', labelEn: 'Feature Requests' },
  { value: 'improvement_suggestion', labelAr: 'اقتراح تحسين', labelEn: 'Improvement Suggestions' },
  { value: 'workflow_issue', labelAr: 'ملاحظة سير عمل', labelEn: 'Workflow Issues' },
  { value: 'permission_issue', labelAr: 'ملاحظة صلاحيات', labelEn: 'Permission Issues' },
  { value: 'integration_issue', labelAr: 'ملاحظة تكامل', labelEn: 'Integration Issues' },
];

const ACCOUNT_TYPE_LABELS = {
  platform_admin: 'Platform Admin — مدير المنصة',
  school_admin: 'School Admin — مدير المدرسة',
  teacher: 'Teacher — معلم',
  student: 'Student — طالب',
  parent: 'Parent — ولي أمر',
  website_user: 'Website User — زائر الموقع',
  entire_system: 'Entire System — النظام بالكامل',
};

const ACCOUNT_PAGES = {
  platform_admin: [
    'لوحة التحكم الرئيسية',
    'إدارة المدارس',
    'إدارة المستخدمين',
    'إدارة الاشتراكات',
    'التقارير والتحليلات',
    'الإعدادات العامة',
    'إدارة الأدوار والصلاحيات',
    'مركز ذكاء المنتج',
    'سجل النشاطات',
    'إدارة الإشعارات',
    'صفحة أخرى',
  ],
  school_admin: [
    'لوحة تحكم المدرسة',
    'إدارة المعلمين',
    'إدارة الطلاب',
    'إدارة الفصول',
    'الجدول الدراسي',
    'إدارة المواد',
    'التقارير المدرسية',
    'إعدادات المدرسة',
    'إدارة أولياء الأمور',
    'الحضور والغياب',
    'إدارة الامتحانات',
    'نظام الدرجات',
    'صفحة أخرى',
  ],
  teacher: [
    'لوحة تحكم المعلم',
    'إدارة الفصول',
    'الجدول الدراسي',
    'تسجيل الحضور',
    'إدارة الواجبات',
    'إدارة الاختبارات',
    'رصد الدرجات',
    'التواصل مع أولياء الأمور',
    'التقارير',
    'الملف الشخصي',
    'صفحة أخرى',
  ],
  student: [
    'لوحة تحكم الطالب',
    'الجدول الدراسي',
    'الواجبات',
    'الاختبارات',
    'النتائج والدرجات',
    'الحضور والغياب',
    'المواد الدراسية',
    'الملف الشخصي',
    'صفحة أخرى',
  ],
  parent: [
    'لوحة تحكم ولي الأمر',
    'متابعة الأبناء',
    'الحضور والغياب',
    'النتائج والدرجات',
    'التواصل مع المدرسة',
    'الإشعارات',
    'المدفوعات',
    'الملف الشخصي',
    'صفحة أخرى',
  ],
  website_user: [
    'الصفحة الرئيسية',
    'تسجيل الدخول',
    'التسجيل الجديد',
    'صفحة التسعير',
    'صفحة التواصل',
    'صفحة المميزات',
    'المدونة',
    'صفحة أخرى',
  ],
  entire_system: [
    'النظام بالكامل',
    'صفحة أخرى',
  ],
};

const HAKIM_STEP_MESSAGES = [
  [
    { text: 'أهلاً! أنا حكيم، مساعدك الذكي', pose: 'hand-wave-greeting' },
    { text: 'أخبرني من أنت ونوع التحدي وسأساعدك في توجيهه للفريق المناسب', pose: 'explaining-concept' },
    { text: 'كلما كانت المعلومات دقيقة، كان تحليلي أفضل!', pose: 'pointing-to-start' },
  ],
  [
    { text: 'ممتاز! الآن صف التحدي بالتفصيل', pose: 'giving-instructions' },
    { text: 'استخدم زر "تحسين بحكيم" وسأعيد صياغة النص ليكون أوضح', pose: 'explaining-concept' },
    { text: 'الوصف الدقيق يساعدني في اكتشاف التحديات المشابهة', pose: 'detecting-patterns' },
  ],
  [
    { text: 'راجع البيانات قبل الإرسال', pose: 'attention-gesture' },
    { text: 'بمجرد الإرسال سأحلل التحدي وأقترح الأولوية والفريق المناسب', pose: 'ai-thinking' },
    { text: 'سأبحث أيضاً عن تحديات مشابهة سابقة!', pose: 'detecting-patterns' },
  ],
];

const HAKIM_REACTION_POSES = {
  improved: 'positive-feedback',
  already_good: 'clapping-celebration',
  step_done: 'congratulating-student',
  account_selected: 'pointing-to-start',
  generating: 'ai-thinking-2',
  submitting: 'ai-thinking',
};

export function ProductHubSubmitPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [config, setConfig] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [step, setStep] = useState(0);
  const [improvingField, setImprovingField] = useState(null);
  const [generatingExpected, setGeneratingExpected] = useState(false);
  const [generatingTitle, setGeneratingTitle] = useState(false);
  const [titleSuggestions, setTitleSuggestions] = useState([]);
  const [uploadingEvidence, setUploadingEvidence] = useState(false);
  const [evidencePreview, setEvidencePreview] = useState(null);
  const [hakimMsgIndex, setHakimMsgIndex] = useState(0);
  const [hakimVisible, setHakimVisible] = useState(true);
  const [hakimTyping, setHakimTyping] = useState(false);
  const [hakimReaction, setHakimReaction] = useState(null);
  const [currentDateTime, setCurrentDateTime] = useState(new Date());

  const [form, setForm] = useState({
    issue_type: '',
    employee_name: user?.full_name || '',
    employee_id: '',
    account_type: '',
    title: '',
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
    additional_info: '',
  });

  useEffect(() => {
    axios.get('/api/product-hub/config', { headers: authHeaders() })
      .then(r => setConfig(r.data))
      .catch(err => { if (process.env.NODE_ENV === 'development') console.warn('Failed to fetch product hub config:', err.message); });
  }, []);

  useEffect(() => {
    const timer = setInterval(() => setCurrentDateTime(new Date()), 30000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (user?.full_name && !form.employee_name) {
      setForm(f => ({ ...f, employee_name: user.full_name }));
    }
  }, [user]);

  useEffect(() => {
    setHakimMsgIndex(0);
    setHakimTyping(true);
    const t = setTimeout(() => setHakimTyping(false), 800);
    return () => clearTimeout(t);
  }, [step]);

  useEffect(() => {
    const msgs = HAKIM_STEP_MESSAGES[step] || [];
    if (msgs.length <= 1) return;
    const interval = setInterval(() => {
      setHakimTyping(true);
      setTimeout(() => {
        setHakimMsgIndex(prev => (prev + 1) % msgs.length);
        setHakimTyping(false);
      }, 600);
    }, 6000);
    return () => clearInterval(interval);
  }, [step]);

  const triggerHakimReaction = useCallback((type) => {
    setHakimReaction(type);
    setTimeout(() => setHakimReaction(null), 2500);
  }, []);

  const handleChange = (field, value) => {
    setForm(f => ({ ...f, [field]: value }));
  };

  const handleAccountTypeChange = (value) => {
    setForm(f => ({ ...f, account_type: value, page: '' }));
    triggerHakimReaction('account_selected');
  };

  const availablePages = ACCOUNT_PAGES[form.account_type] || [];

  const improveWithHakim = useCallback(async (fieldName) => {
    const text = form[fieldName];
    if (!text || text.trim().length < 5) {
      toast.error('اكتب 5 أحرف على الأقل قبل التحسين');
      return;
    }
    setImprovingField(fieldName);
    try {
      const res = await axios.post('/api/product-hub/hakim-improve-text', {
        text: text.trim(),
        field_type: fieldName,
      }, { headers: authHeaders() });
      if (res.data.improved_text && res.data.improved_text !== text.trim()) {
        setForm(f => ({ ...f, [fieldName]: res.data.improved_text }));
        toast.success('حكيم حسّن النص بنجاح');
        triggerHakimReaction('improved');
      } else {
        toast.success('النص واضح ولا يحتاج تحسين');
        triggerHakimReaction('already_good');
      }
    } catch (e) {
      console.error('Error improving text:', e);
      toast.error('فشل تحسين النص');
    } finally {
      setImprovingField(null);
    }
  }, [form, triggerHakimReaction]);

  const generateExpected = useCallback(async () => {
    if (!form.current_behavior || form.current_behavior.trim().length < 10) {
      toast.error('اكتب وصف الوضع الحالي أولاً (10 أحرف على الأقل)');
      return;
    }
    setGeneratingExpected(true);
    triggerHakimReaction(null);
    try {
      const res = await axios.post('/api/product-hub/hakim-generate-expected', {
        title: form.title,
        current_behavior: form.current_behavior,
        issue_type: form.issue_type,
        page: form.page,
      }, { headers: authHeaders() });
      if (res.data.success && res.data.generated_text) {
        setForm(f => ({ ...f, expected_behavior: res.data.generated_text }));
        toast.success('حكيم أنشأ الوضع المتوقع — يمكنك تعديله');
        triggerHakimReaction('improved');
      } else {
        toast.error('لم يتمكن حكيم من إنشاء الوصف — حاول مرة أخرى');
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'object' && detail.message) {
        toast.error(detail.message);
      } else {
        toast.error('فشل في إنشاء الوضع المتوقع');
      }
    } finally {
      setGeneratingExpected(false);
    }
  }, [form, triggerHakimReaction]);

  const generateTitle = useCallback(async () => {
    if (!form.current_behavior || form.current_behavior.trim().length < 10 ||
        !form.expected_behavior || form.expected_behavior.trim().length < 10) {
      toast.error('يرجى استكمال الوضع الحالي والوضع المتوقع لإنشاء عنوان دقيق');
      return;
    }
    setGeneratingTitle(true);
    setTitleSuggestions([]);
    try {
      const res = await axios.post('/api/product-hub/hakim-generate-title', {
        current_behavior: form.current_behavior,
        expected_behavior: form.expected_behavior,
        additional_info: form.additional_info || '',
        issue_type: form.issue_type,
        page: form.page,
      }, { headers: authHeaders() });
      if (res.data.success && res.data.titles?.length > 0) {
        setTitleSuggestions(res.data.titles);
        setForm(f => ({ ...f, title: f.title?.trim() ? f.title : res.data.titles[0] }));
        toast.success('حكيم أنشأ اقتراحات للعنوان — اختر الأنسب');
        triggerHakimReaction('improved');
      } else {
        toast.error('لم يتمكن حكيم من إنشاء عنوان — حاول مرة أخرى');
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'object' && detail.message) {
        toast.error(detail.message);
      } else {
        toast.error('فشل في إنشاء العنوان');
      }
    } finally {
      setGeneratingTitle(false);
    }
  }, [form, triggerHakimReaction]);

  const handleEvidenceUpload = useCallback(async (files) => {
    if (!files || files.length === 0) return;
    const current = form.attachments || [];
    const remaining = MAX_EVIDENCE_IMAGES - current.length;
    if (remaining <= 0) {
      toast.error(`الحد الأقصى ${MAX_EVIDENCE_IMAGES} لقطات شاشة`);
      return;
    }
    const toUpload = Array.from(files).slice(0, remaining);
    if (files.length > remaining) {
      toast.error(`تم تجاهل ${files.length - remaining} ملف — الحد الأقصى ${MAX_EVIDENCE_IMAGES}`);
    }

    setUploadingEvidence(true);
    try {
      const uploaded = [];
      for (const file of toUpload) {
        if (!ALLOWED_EVIDENCE_TYPES.includes(file.type)) {
          toast.error(`نوع الملف غير مدعوم: ${file.name} — استخدم PNG أو JPG أو WEBP`);
          continue;
        }
        if (file.size > MAX_EVIDENCE_SIZE_MB * 1024 * 1024) {
          toast.error(`حجم ${file.name} يتجاوز ${MAX_EVIDENCE_SIZE_MB} ميغابايت`);
          continue;
        }
        const fd = new FormData();
        fd.append('file', file);
        try {
          const res = await axios.post('/api/product-hub/upload-evidence', fd, {
            headers: { ...authHeaders(), 'Content-Type': 'multipart/form-data' },
          });
          if (res.data?.file_url) uploaded.push(res.data.file_url);
        } catch (err) {
          const detail = err.response?.data?.detail;
          const msg = (typeof detail === 'object' && detail?.message)
            ? detail.message
            : (typeof detail === 'string' ? detail : `فشل رفع ${file.name}`);
          toast.error(msg);
        }
      }
      if (uploaded.length > 0) {
        setForm(f => ({ ...f, attachments: [...(f.attachments || []), ...uploaded] }));
        toast.success(`تم رفع ${uploaded.length} لقطة شاشة`);
        triggerHakimReaction('improved');
      }
    } finally {
      setUploadingEvidence(false);
    }
  }, [form.attachments, triggerHakimReaction]);

  const removeEvidence = useCallback((idx) => {
    setForm(f => ({
      ...f,
      attachments: (f.attachments || []).filter((_, i) => i !== idx),
    }));
  }, []);

  const validateStep = (stepIdx) => {
    if (stepIdx === 0) {
      if (!form.employee_name?.trim() || form.employee_name.trim().length < 3) return 'الاسم مطلوب (3 أحرف على الأقل)';
      if (!form.issue_type) return 'نوع التحدي مطلوب';
      if (!form.account_type) return 'نوع الحساب مطلوب';
    }
    if (stepIdx === 1) {
      if (!form.title?.trim()) return 'عنوان التحدي مطلوب';
      if (!form.page?.trim()) return 'الصفحة مطلوبة';
      if (!form.current_behavior?.trim()) return 'الوضع الحالي مطلوب';
      if (!form.expected_behavior?.trim()) return 'الوضع المتوقع مطلوب';
    }
    return null;
  };

  const goNext = () => {
    const err = validateStep(step);
    if (err) { toast.error(err); return; }
    setStep(s => Math.min(STEPS.length - 1, s + 1));
    triggerHakimReaction('step_done');
  };

  const goPrev = () => setStep(s => Math.max(0, s - 1));

  const handleSubmit = async () => {
    for (let i = 0; i < 2; i++) {
      const err = validateStep(i);
      if (err) { toast.error(err); setStep(i); return; }
    }

    setSubmitting(true);
    try {
      const payload = { ...form };
      if (!payload.additional_info?.trim()) delete payload.additional_info;
      if (payload.impact && payload.impact.length === 0) delete payload.impact;
      if (payload.related_to && payload.related_to.length === 0) delete payload.related_to;
      if (!payload.reproducibility) delete payload.reproducibility;
      if (payload.attachments && payload.attachments.length === 0) delete payload.attachments;
      if (!payload.employee_id?.trim()) delete payload.employee_id;
      const res = await axios.post('/api/product-hub/issues', payload, { headers: authHeaders() });
      const newId = res.data?.id || '';
      toast.success('تم إرسال التحدي بنجاح — حكيم يحلله الآن');
      navigate(`/admin/product-hub?tab=issues${newId ? `&highlight=${newId}` : ''}`);
    } catch (err) {
      console.error('[ProductHub] Submit failed:', err?.response?.status, err?.response?.data || err.message);
      const detail = err.response?.data?.detail;
      if (err?.response?.status === 401) {
        toast.error('انتهت صلاحية الجلسة — يرجى تسجيل الدخول مرة أخرى');
      } else if (typeof detail === 'object' && detail.message) {
        toast.error(detail.message);
      } else if (typeof detail === 'string') {
        toast.error(detail);
      } else if (Array.isArray(detail)) {
        const firstErr = detail[0]?.msg || detail[0]?.message || 'خطأ في البيانات';
        toast.error(firstErr);
      } else {
        toast.error('فشل في إرسال التحدي');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const stepProgress = useMemo(() => {
    const fields0 = [form.employee_name?.trim().length >= 3, !!form.issue_type, !!form.account_type];
    const fields1 = [!!form.title?.trim(), !!form.page?.trim(), !!form.current_behavior?.trim(), !!form.expected_behavior?.trim()];
    const done0 = fields0.filter(Boolean).length;
    const done1 = fields1.filter(Boolean).length;
    if (step === 0) return { filled: done0, total: fields0.length };
    if (step === 1) return { filled: done1, total: fields1.length };
    return { filled: done0 + done1, total: fields0.length + fields1.length };
  }, [step, form]);

  const currentHakimMsg = HAKIM_STEP_MESSAGES[step]?.[hakimMsgIndex] || HAKIM_STEP_MESSAGES[0][0];

  const hakimReactionText = useMemo(() => {
    if (hakimReaction === 'improved') return { key: 'improved', text: 'تم التحسين بنجاح!', color: 'text-emerald-600' };
    if (hakimReaction === 'already_good') return { key: 'already_good', text: 'النص ممتاز كما هو', color: 'text-blue-600' };
    if (hakimReaction === 'step_done') return { key: 'step_done', text: 'أحسنت! إلى الخطوة التالية', color: 'text-brand-turquoise' };
    if (hakimReaction === 'account_selected') return { key: 'account_selected', text: 'سأعرض لك الصفحات المتاحة', color: 'text-brand-purple' };
    return null;
  }, [hakimReaction]);

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50/20" dir="rtl">
        <div className="p-4 lg:p-8 max-w-4xl mx-auto space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-brand-turquoise/10 to-brand-purple/10 overflow-hidden shadow-md border border-brand-turquoise/20">
                <img src="/hakim-poses/inviting-to-begin.png" alt="حكيم" className="w-full h-full object-cover" onError={hakimImgError} />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-brand-navy">إضافة تحدي جديد</h1>
                <p className="text-muted-foreground mt-0.5 text-sm">حكيم سيحلل التحدي ويقترح الأولوية والفريق المناسب</p>
              </div>
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

          <HakimCompanion
            message={currentHakimMsg}
            typing={hakimTyping}
            reaction={hakimReactionText}
            visible={hakimVisible}
            onToggle={() => setHakimVisible(v => !v)}
            progress={stepProgress}
            step={step}
            improving={!!improvingField}
            submitting={submitting}
            generating={generatingExpected || generatingTitle}
          />

          {step === 0 && (
            <Card className="border shadow-sm rounded-xl">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <CardTitle className="text-base flex items-center gap-2">
                    <User className="h-4 w-4 text-brand-turquoise" />
                    معلومات المُبلِّغ
                  </CardTitle>
                  <div className="flex items-center gap-3 bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5">
                    <div className="flex items-center gap-1.5 text-[12px] text-brand-navy/70">
                      <Calendar className="h-3.5 w-3.5 text-brand-turquoise" />
                      <span>{currentDateTime.toLocaleDateString('ar-SA', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</span>
                    </div>
                    <div className="w-px h-4 bg-slate-300" />
                    <div className="flex items-center gap-1.5 text-[12px] text-brand-navy/70">
                      <Clock className="h-3.5 w-3.5 text-brand-purple" />
                      <span>{currentDateTime.toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  <div>
                    <Label className="text-sm font-medium">الاسم <span className="text-red-500">*</span></Label>
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
                  <Label className="text-sm font-medium">نوع التحدي <span className="text-red-500">*</span></Label>
                  <Select value={form.issue_type} onValueChange={(v) => handleChange('issue_type', v)}>
                    <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue placeholder="اختر نوع التحدي" /></SelectTrigger>
                    <SelectContent>
                      {COMMENT_TYPE_OPTIONS.map(opt => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.labelAr} — {opt.labelEn}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-sm font-medium">نوع الحساب <span className="text-red-500">*</span></Label>
                  <Select value={form.account_type} onValueChange={handleAccountTypeChange}>
                    <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue placeholder="اختر نوع الحساب" /></SelectTrigger>
                    <SelectContent>
                      {config?.account_types?.map(t => (
                        <SelectItem key={t} value={t}>{ACCOUNT_TYPE_LABELS[t] || t}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {form.issue_type && form.account_type && (
                  <HakimContextualTip
                    issueType={form.issue_type}
                    accountType={form.account_type}
                  />
                )}
              </CardContent>
            </Card>
          )}

          {step === 1 && (
            <Card className="border shadow-sm rounded-xl">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <FileText className="h-4 w-4 text-brand-turquoise" />
                  تفاصيل التحدي
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-5">
                <div>
                  <Label className="text-sm font-medium">الصفحة <span className="text-red-500">*</span></Label>
                  {availablePages.length > 0 ? (
                    <Select value={form.page} onValueChange={(v) => handleChange('page', v)}>
                      <SelectTrigger className="mt-1.5 rounded-lg"><SelectValue placeholder="اختر الصفحة" /></SelectTrigger>
                      <SelectContent>
                        {availablePages.map(p => (
                          <SelectItem key={p} value={p}>{p}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <Input
                      value={form.page}
                      onChange={(e) => handleChange('page', e.target.value)}
                      placeholder="اسم الصفحة أو الشاشة"
                      className="mt-1.5 text-right rounded-lg"
                    />
                  )}
                  {form.account_type && (
                    <p className="text-[11px] text-brand-turquoise mt-1 flex items-center gap-1">
                      <Sparkles className="h-3 w-3" />
                      صفحات {ACCOUNT_TYPE_LABELS[form.account_type]?.split('—')[1]?.trim() || form.account_type}
                    </p>
                  )}
                </div>

                <HakimTextArea
                  label="الوضع الحالي"
                  required
                  value={form.current_behavior}
                  onChange={(v) => handleChange('current_behavior', v)}
                  placeholder="صف ما يحدث حالياً بوضوح..."
                  fieldName="current_behavior"
                  improving={improvingField === 'current_behavior'}
                  onImprove={() => improveWithHakim('current_behavior')}
                  maxLength={5000}
                />

                <HakimTextArea
                  label="الوضع المتوقع"
                  required
                  value={form.expected_behavior}
                  onChange={(v) => handleChange('expected_behavior', v)}
                  placeholder="ما الذي يجب أن يحدث بدلاً من ذلك؟"
                  fieldName="expected_behavior"
                  improving={improvingField === 'expected_behavior'}
                  onImprove={() => improveWithHakim('expected_behavior')}
                  maxLength={5000}
                  onGenerate={generateExpected}
                  generating={generatingExpected}
                  canGenerate={form.current_behavior && form.current_behavior.trim().length >= 10}
                />

                <HakimTextArea
                  label="معلومات إضافية"
                  required={false}
                  value={form.additional_info || ''}
                  onChange={(v) => handleChange('additional_info', v)}
                  placeholder="أضف أي تفاصيل أو ملاحظات إضافية تساعد في فهم التحدي..."
                  fieldName="additional_info"
                  improving={improvingField === 'additional_info'}
                  onImprove={() => improveWithHakim('additional_info')}
                />

                <Separator className="my-2" />

                <HakimTitleGenerator
                  value={form.title}
                  onChange={(v) => { handleChange('title', v); setTitleSuggestions([]); }}
                  onSelectSuggestion={(v) => { handleChange('title', v); }}
                  onGenerate={generateTitle}
                  onRegenerate={generateTitle}
                  generating={generatingTitle}
                  suggestions={titleSuggestions}
                  canGenerate={
                    form.current_behavior && form.current_behavior.trim().length >= 10 &&
                    form.expected_behavior && form.expected_behavior.trim().length >= 10
                  }
                  improving={improvingField === 'title'}
                  onImprove={() => improveWithHakim('title')}
                />

                <Separator className="my-2" />

                <EvidenceUploader
                  attachments={form.attachments || []}
                  uploading={uploadingEvidence}
                  onUpload={handleEvidenceUpload}
                  onRemove={removeEvidence}
                  onPreview={setEvidencePreview}
                />
              </CardContent>
            </Card>
          )}

          {step === 2 && (
            <div className="space-y-5">
              <Card className="border shadow-sm rounded-xl">
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-brand-turquoise" />
                    مراجعة قبل الإرسال
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <ReviewRow label="الاسم" value={form.employee_name} />
                  <ReviewRow label="نوع التحدي" value={COMMENT_TYPE_OPTIONS.find(o => o.value === form.issue_type)?.labelAr || form.issue_type} />
                  <ReviewRow label="نوع الحساب" value={ACCOUNT_TYPE_LABELS[form.account_type] || form.account_type} />
                  <Separator />
                  <div className="bg-gradient-to-l from-brand-navy/5 via-brand-purple/5 to-brand-turquoise/5 rounded-xl p-4 border border-brand-navy/10">
                    <p className="text-[11px] text-muted-foreground mb-1.5">عنوان التحدي</p>
                    <h2 className="text-lg font-bold text-brand-navy leading-relaxed">{form.title}</h2>
                  </div>
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
                  {form.additional_info && (
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">معلومات إضافية</p>
                      <p className="text-sm bg-slate-50 p-3 rounded-lg border border-slate-200">{form.additional_info}</p>
                    </div>
                  )}
                  {(form.attachments || []).length > 0 && (
                    <div>
                      <p className="text-xs text-muted-foreground mb-2 flex items-center gap-1.5">
                        <ImageIcon className="h-3.5 w-3.5 text-brand-turquoise" />
                        لقطات الشاشة المرفقة ({form.attachments.length})
                      </p>
                      <div className="grid grid-cols-3 gap-3">
                        {form.attachments.map((url, idx) => (
                          <button
                            type="button"
                            key={idx}
                            onClick={() => setEvidencePreview(url)}
                            className="group relative aspect-video rounded-lg overflow-hidden border border-slate-200 bg-slate-50 hover:border-brand-turquoise hover:shadow-md transition-all"
                          >
                            <img src={url} alt={`دليل ${idx + 1}`} className="w-full h-full object-cover" />
                            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                              <Eye className="h-5 w-5 text-white opacity-0 group-hover:opacity-100 drop-shadow-md" />
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              <HakimPreSubmitCard submitting={submitting} />

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
                  <ArrowLeft className="h-4 w-4 mr-2" />
                </Button>
              ) : (
                <Button
                  onClick={handleSubmit}
                  disabled={submitting}
                  className="bg-brand-turquoise hover:bg-brand-turquoise/90 text-white rounded-lg min-w-[180px] shadow-lg shadow-brand-turquoise/20"
                >
                  {submitting ? (
                    <>
                      <img src="/hakim-poses/ai-thinking.png" alt="" className="h-5 w-5 rounded-full object-cover ml-2 border border-white/30" onError={hakimImgError} />
                      حكيم يحلل...
                    </>
                  ) : (
                    <>
                      <Send className="h-4 w-4 ml-2" />
                      إرسال التحدي
                    </>
                  )}
                </Button>
              )}
            </div>
          </div>
        </div>

        {evidencePreview && (
          <div
            className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-6"
            onClick={() => setEvidencePreview(null)}
          >
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); setEvidencePreview(null); }}
              className="absolute top-6 left-6 w-10 h-10 rounded-full bg-white/15 hover:bg-white/25 flex items-center justify-center text-white transition"
              aria-label="إغلاق"
            >
              <X className="h-5 w-5" />
            </button>
            <img
              src={evidencePreview}
              alt="معاينة"
              className="max-w-full max-h-full rounded-lg shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        )}
      </div>
    </Sidebar>
  );
}

function EvidenceUploader({ attachments, uploading, onUpload, onRemove, onPreview }) {
  const fileInputRef = React.useRef(null);
  const canAdd = attachments.length < MAX_EVIDENCE_IMAGES && !uploading;

  return (
    <div className="rounded-xl border border-brand-turquoise/20 bg-gradient-to-l from-brand-turquoise/5 via-white to-brand-purple/5 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-brand-turquoise/10 flex items-center justify-center">
            <Camera className="h-4 w-4 text-brand-turquoise" />
          </div>
          <div>
            <Label className="text-sm font-medium">لقطات شاشة كدليل</Label>
            <p className="text-[10px] text-muted-foreground">
              اختياري — حتى {MAX_EVIDENCE_IMAGES} صور (PNG / JPG / WEBP) بحد أقصى {MAX_EVIDENCE_SIZE_MB} ميغابايت لكل صورة
            </p>
          </div>
        </div>
        <span className="text-[11px] font-medium text-brand-navy/70">
          {attachments.length}/{MAX_EVIDENCE_IMAGES}
        </span>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        multiple
        className="hidden"
        onChange={(e) => {
          onUpload(e.target.files);
          if (fileInputRef.current) fileInputRef.current.value = '';
        }}
      />

      <div className="grid grid-cols-3 gap-3">
        {attachments.map((url, idx) => (
          <div
            key={idx}
            className="group relative aspect-video rounded-lg overflow-hidden border border-slate-200 bg-slate-50"
          >
            <img
              src={url}
              alt={`دليل ${idx + 1}`}
              className="w-full h-full object-cover cursor-zoom-in"
              onClick={() => onPreview(url)}
              onError={(e) => {
                e.currentTarget.style.display = 'none';
                e.currentTarget.parentElement.classList.add('flex', 'items-center', 'justify-center');
                const fallback = document.createElement('span');
                fallback.className = 'text-[11px] text-muted-foreground';
                fallback.textContent = 'تعذّر عرض الصورة';
                e.currentTarget.parentElement.appendChild(fallback);
              }}
            />
            <button
              type="button"
              onClick={() => onRemove(idx)}
              className="absolute top-1.5 right-1.5 w-7 h-7 rounded-full bg-red-500/90 hover:bg-red-600 text-white flex items-center justify-center shadow-md opacity-90 group-hover:opacity-100 transition"
              aria-label="حذف"
            >
              <X className="h-3.5 w-3.5" />
            </button>
            <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/60 to-transparent text-white text-[10px] px-2 py-1">
              لقطة {idx + 1}
            </div>
          </div>
        ))}

        {canAdd && (
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="aspect-video rounded-lg border-2 border-dashed border-brand-turquoise/40 hover:border-brand-turquoise hover:bg-brand-turquoise/5 transition flex flex-col items-center justify-center gap-1.5 text-brand-turquoise"
          >
            <ImagePlus className="h-5 w-5" />
            <span className="text-[11px] font-medium">إضافة لقطة</span>
          </button>
        )}

        {uploading && (
          <div className="aspect-video rounded-lg border border-brand-turquoise/30 bg-brand-turquoise/5 flex flex-col items-center justify-center gap-1.5 text-brand-turquoise">
            <Loader2 className="h-5 w-5 animate-spin" />
            <span className="text-[11px] font-medium">جارٍ الرفع...</span>
          </div>
        )}
      </div>

      {attachments.length === 0 && !uploading && (
        <p className="text-[11px] text-muted-foreground flex items-center gap-1.5">
          <Lightbulb className="h-3 w-3 text-brand-turquoise" />
          إرفاق لقطة شاشة يساعد الفريق على فهم المشكلة بشكل أسرع
        </p>
      )}
    </div>
  );
}

function HakimCompanion({ message, typing, reaction, visible, onToggle, progress, step, improving, submitting, generating }) {
  const activePose = useMemo(() => {
    if (submitting) return HAKIM_REACTION_POSES.submitting;
    if (generating) return HAKIM_REACTION_POSES.generating;
    if (improving) return 'ai-thinking';
    if (reaction) {
      const reactionPose = HAKIM_REACTION_POSES[reaction.key];
      if (reactionPose) return reactionPose;
    }
    return message.pose || 'friendly-greeting';
  }, [message.pose, improving, submitting, generating, reaction]);

  return (
    <div className="relative">
      <div
        className={`overflow-hidden transition-all duration-500 ease-in-out ${visible ? 'max-h-[300px] opacity-100' : 'max-h-0 opacity-0'}`}
      >
        <div className="rounded-2xl border border-brand-turquoise/20 bg-gradient-to-l from-brand-turquoise/5 via-white to-brand-purple/5 shadow-sm">
          <div className="p-4">
            <div className="flex items-start gap-4">
              <div className="relative flex-shrink-0">
                <div className={`w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-turquoise/10 to-brand-purple/10 overflow-hidden shadow-lg shadow-brand-turquoise/15 border border-brand-turquoise/20 ${improving || submitting || generating ? 'ring-2 ring-brand-turquoise/30 ring-offset-1' : ''}`}>
                  <img
                    src={`/hakim-poses/${activePose}.png`}
                    alt="حكيم"
                    className={`w-full h-full object-cover transition-all duration-500 ${improving || submitting || generating ? 'scale-105' : 'hover:scale-110'}`}
                    onError={hakimImgError}
                  />
                </div>
                <div className={`absolute -bottom-1 -left-1 w-4 h-4 rounded-full border-2 border-white flex items-center justify-center ${improving || generating ? 'bg-amber-400' : submitting ? 'bg-brand-turquoise' : 'bg-emerald-400'}`}>
                  <div className="w-1.5 h-1.5 bg-white rounded-full animate-pulse" />
                </div>
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-sm font-bold text-brand-navy">حكيم</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-brand-turquoise/10 text-brand-turquoise font-medium">
                    AI مساعد
                  </span>
                  {improving && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium flex items-center gap-1">
                      <Wand2 className="h-2.5 w-2.5" />
                      يحسّن النص
                    </span>
                  )}
                  {generating && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-brand-purple/10 text-brand-purple font-medium flex items-center gap-1 animate-pulse">
                      <PenLine className="h-2.5 w-2.5" />
                      يُنشئ نصاً
                    </span>
                  )}
                  {submitting && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-brand-turquoise/10 text-brand-turquoise font-medium flex items-center gap-1 animate-pulse">
                      <Zap className="h-2.5 w-2.5" />
                      يحلل التحدي
                    </span>
                  )}
                </div>

                <div className="relative">
                  {reaction ? (
                    <div className={`text-sm font-medium ${reaction.color} transition-all duration-300 animate-in fade-in slide-in-from-bottom-2`}>
                      {reaction.text}
                    </div>
                  ) : typing ? (
                    <div className="flex items-center gap-1.5">
                      <div className="flex gap-1">
                        <span className="w-1.5 h-1.5 bg-brand-turquoise/60 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                        <span className="w-1.5 h-1.5 bg-brand-turquoise/60 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                        <span className="w-1.5 h-1.5 bg-brand-turquoise/60 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                      <span className="text-[11px] text-muted-foreground">حكيم يكتب...</span>
                    </div>
                  ) : (
                    <p className="text-sm text-brand-navy/80 leading-relaxed transition-all duration-300">{message.text}</p>
                  )}
                </div>

                <div className="mt-3 flex items-center gap-3">
                  <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-l from-brand-turquoise to-brand-purple rounded-full transition-all duration-700 ease-out"
                      style={{ width: `${(progress.filled / progress.total) * 100}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-muted-foreground font-medium whitespace-nowrap">
                    {progress.filled}/{progress.total} حقول
                  </span>
                </div>
              </div>
            </div>
          </div>

          {step === 1 && (
            <div className="border-t border-brand-turquoise/10 px-4 py-2.5 bg-brand-turquoise/[0.02]">
              <div className="flex items-center gap-4 text-[11px]">
                <div className="flex items-center gap-1.5 text-brand-turquoise">
                  <Wand2 className="h-3 w-3" />
                  <span>اضغط "تحسين بحكيم" على أي حقل</span>
                </div>
                <div className="w-px h-3 bg-slate-200" />
                <div className="flex items-center gap-1.5 text-brand-purple">
                  <Sparkles className="h-3 w-3" />
                  <span>سأعيد الصياغة ليكون النص أوضح وأدق</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      <button
        onClick={onToggle}
        className="absolute -bottom-3 left-1/2 -translate-x-1/2 z-10 flex items-center gap-1.5 px-3 py-1 rounded-full bg-white border border-brand-turquoise/20 shadow-sm hover:shadow-md transition-all text-[11px] font-medium text-brand-navy hover:border-brand-turquoise/40"
      >
        <img src="/hakim-poses/friendly-greeting.png" alt="" className="h-4 w-4 rounded-full object-cover" onError={hakimImgError} />
        {visible ? 'إخفاء حكيم' : 'إظهار حكيم'}
        <MessageCircle className="h-3 w-3 text-brand-turquoise/60" />
      </button>
    </div>
  );
}

function HakimContextualTip({ issueType, accountType }) {
  const tipData = useMemo(() => {
    const tips = {
      bug: { text: 'حكيم سيبحث عن أخطاء مشابهة تم حلها سابقاً لتسريع الإصلاح', pose: 'detecting-patterns' },
      error: { text: 'حاول تضمين رسالة الخطأ الدقيقة في الخطوة التالية — يساعدني كثيراً!', pose: 'attention-gesture' },
      ui_issue: { text: 'صف الشكل الحالي والشكل المتوقع بدقة — يمكنك إرفاق لقطة شاشة لاحقاً', pose: 'explaining-concept' },
      ux_issue: { text: 'اشرح السيناريو الكامل الذي مررت به — من البداية للنهاية', pose: 'listening' },
      performance_issue: { text: 'حدد أين يحدث البطء بالضبط وكم يستغرق — سأحلل السبب', pose: 'ai-thinking' },
      feature_request: { text: 'اشرح المشكلة التي ستحلها هذه الميزة — ليس فقط الميزة نفسها', pose: 'giving-instructions' },
      improvement_suggestion: { text: 'صف كيف سيؤثر هذا التحسين على تجربة المستخدم اليومية', pose: 'motivating' },
      workflow_issue: { text: 'حدد الخطوة التي تتعطل فيها — سأتتبع مسار العمل كاملاً', pose: 'detecting-patterns' },
      permission_issue: { text: 'حدد الإجراء المطلوب والصلاحية المفقودة — سأراجع إعدادات الأدوار', pose: 'attention-gesture' },
      integration_issue: { text: 'حدد النظام الخارجي المتأثر — سأفحص نقاط التكامل', pose: 'ai-thinking-2' },
    };
    return tips[issueType] || { text: 'سأحلل التحدي وأوجهه للفريق المناسب', pose: 'explaining-concept' };
  }, [issueType]);

  return (
    <div className="mt-2 rounded-xl border border-brand-turquoise/15 bg-gradient-to-l from-brand-turquoise/5 to-transparent p-3">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-turquoise/10 to-brand-purple/10 overflow-hidden flex-shrink-0 border border-brand-turquoise/15 shadow-sm">
          <img
            src={`/hakim-poses/${tipData.pose}.png`}
            alt="حكيم"
            className="w-full h-full object-cover"
            onError={hakimImgError}
          />
        </div>
        <div className="pt-0.5">
          <p className="text-[11px] font-semibold text-brand-navy mb-0.5 flex items-center gap-1">
            <Lightbulb className="h-3 w-3 text-brand-turquoise" />
            نصيحة حكيم
          </p>
          <p className="text-[11px] text-brand-navy/70 leading-relaxed">{tipData.text}</p>
        </div>
      </div>
    </div>
  );
}

function HakimInput({ label, required, value, onChange, placeholder, improving, onImprove, maxLength, hint }) {
  const canImprove = value && value.trim().length >= 5;

  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <Label className="text-sm font-medium">
          {label} {required && <span className="text-red-500">*</span>}
        </Label>
        <button
          type="button"
          onClick={onImprove}
          disabled={improving || !canImprove}
          className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-[11px] font-semibold transition-all shadow-sm ${
            improving
              ? 'bg-brand-turquoise/20 text-brand-turquoise cursor-wait border border-brand-turquoise/30'
              : canImprove
                ? 'bg-brand-turquoise text-white hover:bg-brand-turquoise/90 hover:shadow-md hover:shadow-brand-turquoise/25 cursor-pointer border border-brand-turquoise'
                : 'bg-slate-100 text-slate-400 cursor-not-allowed border border-slate-200'
          }`}
        >
          {improving ? (
            <>
              <Loader2 className="h-3 w-3 animate-spin" />
              <span>حكيم يحسّن...</span>
            </>
          ) : (
            <>
              <Wand2 className="h-3 w-3" />
              <span>تحسين بحكيم</span>
              <img src="/hakim-poses/ai-thinking.png" alt="" className="h-4 w-4 rounded-full object-cover ring-1 ring-white/50" onError={hakimImgError} />
            </>
          )}
        </button>
      </div>
      <div className="relative">
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className={`text-right rounded-lg transition-all ${improving ? 'border-brand-turquoise/40 bg-brand-turquoise/5' : ''}`}
          maxLength={maxLength}
          disabled={improving}
        />
        {improving && (
          <div className="absolute inset-0 bg-brand-turquoise/5 rounded-lg flex items-center justify-center pointer-events-none">
            <div className="flex items-center gap-2 bg-white/90 backdrop-blur-sm px-4 py-2 rounded-full shadow-md border border-brand-turquoise/20">
              <img src="/hakim-poses/ai-thinking.png" alt="" className="h-6 w-6 rounded-full object-cover border border-brand-turquoise/20" onError={hakimImgError} />
              <span className="text-xs font-medium text-brand-navy">حكيم يحسّن العنوان...</span>
              <Sparkles className="h-3 w-3 text-brand-turquoise/60" />
            </div>
          </div>
        )}
      </div>
      <div className="flex items-center justify-between mt-1">
        {hint && <p className="text-[10px] text-muted-foreground">{hint}</p>}
        {maxLength && <p className="text-[10px] text-muted-foreground">{(value || '').length}/{maxLength}</p>}
      </div>
    </div>
  );
}

function HakimTextArea({ label, required, value, onChange, placeholder, fieldName, improving, onImprove, maxLength, onGenerate, generating, canGenerate }) {
  const canImprove = value && value.trim().length >= 5;
  const isDisabled = improving || generating;

  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <Label className="text-sm font-medium">
          {label} {required && <span className="text-red-500">*</span>}
        </Label>
        <div className="flex items-center gap-2">
          {onGenerate && (
            <button
              type="button"
              onClick={onGenerate}
              disabled={isDisabled || !canGenerate}
              className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-[11px] font-semibold transition-all shadow-sm ${
                generating
                  ? 'bg-brand-purple/20 text-brand-purple cursor-wait border border-brand-purple/30'
                  : canGenerate
                    ? 'bg-brand-purple text-white hover:bg-brand-purple/90 hover:shadow-md hover:shadow-brand-purple/25 cursor-pointer border border-brand-purple'
                    : 'bg-slate-100 text-slate-400 cursor-not-allowed border border-slate-200'
              }`}
            >
              {generating ? (
                <>
                  <Loader2 className="h-3 w-3 animate-spin" />
                  <span>حكيم يُنشئ...</span>
                </>
              ) : (
                <>
                  <PenLine className="h-3 w-3" />
                  <span>إنشاء بحكيم</span>
                  <img src="/hakim-poses/ai-thinking-2.png" alt="" className="h-4 w-4 rounded-full object-cover ring-1 ring-white/50" onError={hakimImgError} />
                </>
              )}
            </button>
          )}
          <button
            type="button"
            onClick={onImprove}
            disabled={isDisabled || !canImprove}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-[11px] font-semibold transition-all shadow-sm ${
              improving
                ? 'bg-brand-turquoise/20 text-brand-turquoise cursor-wait border border-brand-turquoise/30'
                : canImprove
                  ? 'bg-brand-turquoise text-white hover:bg-brand-turquoise/90 hover:shadow-md hover:shadow-brand-turquoise/25 cursor-pointer border border-brand-turquoise'
                  : 'bg-slate-100 text-slate-400 cursor-not-allowed border border-slate-200'
            }`}
          >
            {improving ? (
              <>
                <Loader2 className="h-3 w-3 animate-spin" />
                <span>حكيم يحسّن...</span>
              </>
            ) : (
              <>
                <Wand2 className="h-3 w-3" />
                <span>تحسين بحكيم</span>
                <img src="/hakim-poses/ai-thinking.png" alt="" className="h-4 w-4 rounded-full object-cover ring-1 ring-white/50" onError={hakimImgError} />
              </>
            )}
          </button>
        </div>
      </div>
      <div className="relative">
        <Textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className={`text-right min-h-[100px] rounded-lg transition-all ${
            generating ? 'border-brand-purple/40 bg-brand-purple/5' :
            improving ? 'border-brand-turquoise/40 bg-brand-turquoise/5' : ''
          }`}
          disabled={isDisabled}
        />
        {improving && (
          <div className="absolute inset-0 bg-brand-turquoise/5 rounded-lg flex items-center justify-center pointer-events-none">
            <div className="flex items-center gap-2 bg-white/90 backdrop-blur-sm px-4 py-2 rounded-full shadow-md border border-brand-turquoise/20">
              <img src="/hakim-poses/ai-thinking.png" alt="" className="h-6 w-6 rounded-full object-cover border border-brand-turquoise/20" onError={hakimImgError} />
              <span className="text-xs font-medium text-brand-navy">حكيم يحسّن النص...</span>
              <Sparkles className="h-3 w-3 text-brand-turquoise/60" />
            </div>
          </div>
        )}
        {generating && (
          <div className="absolute inset-0 bg-brand-purple/5 rounded-lg flex items-center justify-center pointer-events-none">
            <div className="flex items-center gap-2 bg-white/90 backdrop-blur-sm px-4 py-2 rounded-full shadow-md border border-brand-purple/20">
              <img src="/hakim-poses/ai-thinking-2.png" alt="" className="h-6 w-6 rounded-full object-cover border border-brand-purple/20" onError={hakimImgError} />
              <span className="text-xs font-medium text-brand-navy">حكيم يُنشئ الوضع المتوقع...</span>
              <PenLine className="h-3 w-3 text-brand-purple/60" />
            </div>
          </div>
        )}
      </div>
      <div className="flex items-center justify-between mt-1">
        <p className="text-[11px] text-muted-foreground">
          {onGenerate && !value?.trim() && canGenerate
            ? 'اضغط "إنشاء بحكيم" لتوليد وصف تلقائي من الوضع الحالي'
            : !required ? 'اختياري — يساعد حكيم في التحليل' : 'يساعد حكيم في التحليل'
          }
        </p>
        {maxLength && (
          <p className="text-[11px] text-muted-foreground">{(value || '').length}/{maxLength}</p>
        )}
      </div>
    </div>
  );
}

function HakimTitleGenerator({ value, onChange, onSelectSuggestion, onGenerate, onRegenerate, generating, suggestions, canGenerate, improving, onImprove }) {
  const canImprove = value && value.trim().length >= 5;
  const isDisabled = improving || generating;
  const hasSuggestions = suggestions && suggestions.length > 0;

  return (
    <div className="rounded-xl border border-brand-purple/20 bg-gradient-to-l from-brand-purple/5 via-white to-brand-turquoise/5 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <img src="/hakim-poses/giving-instructions.png" alt="" className="h-7 w-7 rounded-lg object-cover border border-brand-purple/15" onError={hakimImgError} />
          <div>
            <Label className="text-sm font-medium">
              عنوان التحدي <span className="text-red-500">*</span>
            </Label>
            <p className="text-[10px] text-muted-foreground">يُفضّل 3-5 كلمات بصياغة إيجابية</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onGenerate}
            disabled={isDisabled || !canGenerate}
            className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-[11px] font-semibold transition-all shadow-sm ${
              generating
                ? 'bg-brand-purple/20 text-brand-purple cursor-wait border border-brand-purple/30'
                : canGenerate
                  ? 'bg-brand-purple text-white hover:bg-brand-purple/90 hover:shadow-md hover:shadow-brand-purple/25 cursor-pointer border border-brand-purple'
                  : 'bg-slate-100 text-slate-400 cursor-not-allowed border border-slate-200'
            }`}
          >
            {generating ? (
              <>
                <Loader2 className="h-3 w-3 animate-spin" />
                <span>حكيم يُنشئ...</span>
              </>
            ) : (
              <>
                <PenLine className="h-3 w-3" />
                <span>إنشاء بحكيم</span>
                <img src="/hakim-poses/ai-thinking-2.png" alt="" className="h-4 w-4 rounded-full object-cover ring-1 ring-white/50" onError={hakimImgError} />
              </>
            )}
          </button>
          {canImprove && (
            <button
              type="button"
              onClick={onImprove}
              disabled={isDisabled}
              className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-[11px] font-semibold transition-all shadow-sm ${
                improving
                  ? 'bg-brand-turquoise/20 text-brand-turquoise cursor-wait border border-brand-turquoise/30'
                  : 'bg-brand-turquoise text-white hover:bg-brand-turquoise/90 hover:shadow-md hover:shadow-brand-turquoise/25 cursor-pointer border border-brand-turquoise'
              }`}
            >
              {improving ? (
                <>
                  <Loader2 className="h-3 w-3 animate-spin" />
                  <span>يحسّن...</span>
                </>
              ) : (
                <>
                  <Wand2 className="h-3 w-3" />
                  <span>تحسين</span>
                </>
              )}
            </button>
          )}
        </div>
      </div>

      <div className="relative">
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={canGenerate ? 'اكتب عنواناً أو اضغط "إنشاء بحكيم"' : 'أكمل الوضع الحالي والمتوقع أولاً'}
          className={`text-right rounded-lg transition-all ${
            generating ? 'border-brand-purple/40 bg-brand-purple/5' :
            improving ? 'border-brand-turquoise/40 bg-brand-turquoise/5' : ''
          }`}
          maxLength={200}
          disabled={isDisabled}
        />
        {generating && (
          <div className="absolute inset-0 bg-brand-purple/5 rounded-lg flex items-center justify-center pointer-events-none">
            <div className="flex items-center gap-2 bg-white/90 backdrop-blur-sm px-4 py-2 rounded-full shadow-md border border-brand-purple/20">
              <img src="/hakim-poses/ai-thinking-2.png" alt="" className="h-6 w-6 rounded-full object-cover border border-brand-purple/20" onError={hakimImgError} />
              <span className="text-xs font-medium text-brand-navy">حكيم يُنشئ عنواناً احترافياً...</span>
              <Sparkles className="h-3 w-3 text-brand-purple/60" />
            </div>
          </div>
        )}
        {improving && (
          <div className="absolute inset-0 bg-brand-turquoise/5 rounded-lg flex items-center justify-center pointer-events-none">
            <div className="flex items-center gap-2 bg-white/90 backdrop-blur-sm px-4 py-2 rounded-full shadow-md border border-brand-turquoise/20">
              <img src="/hakim-poses/ai-thinking.png" alt="" className="h-6 w-6 rounded-full object-cover border border-brand-turquoise/20" onError={hakimImgError} />
              <span className="text-xs font-medium text-brand-navy">حكيم يحسّن العنوان...</span>
              <Sparkles className="h-3 w-3 text-brand-turquoise/60" />
            </div>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between">
        {!canGenerate ? (
          <p className="text-[10px] text-amber-600 flex items-center gap-1">
            <Lightbulb className="h-3 w-3" />
            يرجى استكمال الوضع الحالي والوضع المتوقع لإنشاء عنوان دقيق
          </p>
        ) : (
          <p className="text-[10px] text-muted-foreground">
            {hasSuggestions ? 'اختر من الاقتراحات أو عدّل العنوان يدوياً' : 'يمكنك الكتابة يدوياً أو الإنشاء بواسطة حكيم'}
          </p>
        )}
        <p className="text-[10px] text-muted-foreground">{(value || '').length}/200</p>
      </div>

      {hasSuggestions && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-[11px] font-semibold text-brand-navy flex items-center gap-1.5">
              <img src="/hakim-poses/positive-feedback.png" alt="" className="h-5 w-5 rounded-full object-cover" onError={hakimImgError} />
              اقتراحات حكيم
            </p>
            <button
              type="button"
              onClick={onRegenerate}
              disabled={isDisabled}
              className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] text-brand-purple hover:bg-brand-purple/10 transition-all"
            >
              <RefreshCw className="h-3 w-3" />
              إعادة توليد
            </button>
          </div>
          <div className="grid gap-1.5">
            {suggestions.map((s, i) => (
              <button
                key={i}
                type="button"
                onClick={() => onSelectSuggestion(s)}
                className={`w-full text-right px-3 py-2 rounded-lg text-sm transition-all border ${
                  value === s
                    ? 'bg-brand-purple/10 border-brand-purple/30 text-brand-navy font-medium'
                    : 'bg-white border-slate-200 text-brand-navy/80 hover:bg-brand-purple/5 hover:border-brand-purple/20'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span>{s}</span>
                  {value === s && <CheckCircle2 className="h-3.5 w-3.5 text-brand-purple flex-shrink-0" />}
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function HakimPreSubmitCard({ submitting }) {
  return (
    <Card className="border shadow-sm rounded-2xl border-brand-turquoise/30 overflow-hidden">
      <div className="bg-gradient-to-l from-brand-turquoise/10 via-brand-purple/5 to-brand-turquoise/10">
        <CardContent className="p-5">
          <div className="flex items-start gap-4">
            <div className={`w-14 h-14 rounded-xl bg-gradient-to-br from-brand-turquoise/10 to-brand-purple/10 overflow-hidden shadow-lg shadow-brand-turquoise/20 flex-shrink-0 border border-brand-turquoise/20 ${submitting ? 'ring-2 ring-brand-turquoise/40 ring-offset-1' : ''}`}>
              <img
                src={`/hakim-poses/${submitting ? 'ai-thinking.png' : 'positive-feedback.png'}`}
                alt="حكيم"
                className={`w-full h-full object-cover transition-all duration-500 ${submitting ? 'scale-105' : ''}`}
                onError={hakimImgError}
              />
            </div>
            <div className="flex-1">
              <p className="font-bold text-brand-navy text-sm mb-2">
                {submitting ? 'حكيم يحلل التحدي الآن...' : 'ماذا سيفعل حكيم بعد الإرسال؟'}
              </p>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { icon: Zap, text: 'تحديد الأولوية تلقائياً', color: 'text-amber-500' },
                  { icon: Eye, text: 'اكتشاف التحديات المشابهة', color: 'text-blue-500' },
                  { icon: Shield, text: 'توجيه للفريق المناسب', color: 'text-emerald-500' },
                  { icon: Sparkles, text: 'تحليل الأثر والخطورة', color: 'text-brand-purple' },
                ].map((item, i) => (
                  <div key={i} className={`flex items-center gap-2 text-[11px] text-brand-navy/70 ${submitting ? 'animate-pulse' : ''}`} style={submitting ? { animationDelay: `${i * 200}ms` } : {}}>
                    <item.icon className={`h-3.5 w-3.5 ${item.color} flex-shrink-0`} />
                    <span>{item.text}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </CardContent>
      </div>
    </Card>
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
