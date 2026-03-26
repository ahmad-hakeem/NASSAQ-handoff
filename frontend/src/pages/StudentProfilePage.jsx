import { useState, useEffect, useMemo, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { Sidebar } from '../components/layout/Sidebar';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Label } from '../components/ui/label';
import { Progress } from '../components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { RadioGroup, RadioGroupItem } from '../components/ui/radio-group';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import { NotificationBell } from '../components/notifications/NotificationBell';
import {
  User, BookOpen, Shield, Brain, FileText, Edit, Save, X,
  Phone, Mail, Hash, Calendar, ArrowLeft, ArrowRight, ChevronRight,
  Star, Loader2, Activity, Target, Sparkles, Clock, Key, UserX,
  UserCheck, Trash2, Download, Sun, Moon, Globe, GraduationCap,
  Stethoscope, Rocket, ChevronDown, ChevronUp, CheckCircle,
  AlertTriangle, Zap, Heart, Award, Plus, XCircle
} from 'lucide-react';

const TALENT_OPTIONS = [
  { value: 'academically_gifted', ar: 'متفوق أكاديمياً', en: 'Academically Gifted', color: 'bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-700' },
  { value: 'artistic', ar: 'فنان', en: 'Artistic', color: 'bg-purple-100 text-purple-700 border-purple-200 dark:bg-purple-900/30 dark:text-purple-300 dark:border-purple-700' },
  { value: 'athletic', ar: 'رياضي', en: 'Athletic', color: 'bg-green-100 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-300 dark:border-green-700' },
  { value: 'scientific', ar: 'علمي', en: 'Scientific', color: 'bg-cyan-100 text-cyan-700 border-cyan-200 dark:bg-cyan-900/30 dark:text-cyan-300 dark:border-cyan-700' },
  { value: 'leadership', ar: 'قيادي', en: 'Leadership', color: 'bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-700' },
  { value: 'literary', ar: 'أدبي', en: 'Literary', color: 'bg-rose-100 text-rose-700 border-rose-200 dark:bg-rose-900/30 dark:text-rose-300 dark:border-rose-700' },
  { value: 'musical', ar: 'موسيقي', en: 'Musical', color: 'bg-indigo-100 text-indigo-700 border-indigo-200 dark:bg-indigo-900/30 dark:text-indigo-300 dark:border-indigo-700' },
  { value: 'technological', ar: 'تقني', en: 'Technological', color: 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-900/30 dark:text-slate-300 dark:border-slate-700' },
];

const HAKIM_POSES = {
  remedial: '/hakim-poses/support.png',
  enrichment: '/hakim-poses/motivating.png',
  thinking: '/hakim-poses/ai-thinking.png',
};

const PLAN_CONFIG = {
  remedial: {
    title_ar: 'الخطة العلاجية', title_en: 'Remedial Plan',
    desc_ar: 'خطة لمعالجة نقاط الضعف وتحسين الأداء الأكاديمي',
    desc_en: 'A plan to address weaknesses and improve academic performance',
    btn_ar: 'أنشئ الخطة العلاجية', btn_en: 'Generate Remedial Plan',
    icon: Stethoscope, gradient: 'from-rose-500 to-orange-500',
    bg: 'bg-gradient-to-br from-rose-50 to-orange-50/50 dark:from-rose-950/20 dark:to-orange-950/10',
    border: 'border-rose-200/70 dark:border-rose-800/30',
    iconBg: 'bg-rose-100 dark:bg-rose-900/40 text-rose-600 dark:text-rose-400',
    stepBg: 'bg-rose-50/80 dark:bg-rose-950/10 border-rose-100 dark:border-rose-800/20',
    btnClass: 'from-rose-500 to-orange-500',
  },
  enrichment: {
    title_ar: 'الخطة الإثرائية', title_en: 'Enrichment Plan',
    desc_ar: 'خطة لتعزيز نقاط القوة وتطوير المهارات المتميزة',
    desc_en: 'A plan to strengthen talents and develop advanced skills',
    btn_ar: 'أنشئ الخطة الإثرائية', btn_en: 'Generate Enrichment Plan',
    icon: Rocket, gradient: 'from-emerald-500 to-teal-500',
    bg: 'bg-gradient-to-br from-emerald-50 to-teal-50/50 dark:from-emerald-950/20 dark:to-teal-950/10',
    border: 'border-emerald-200/70 dark:border-emerald-800/30',
    iconBg: 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-600 dark:text-emerald-400',
    stepBg: 'bg-emerald-50/80 dark:bg-emerald-950/10 border-emerald-100 dark:border-emerald-800/20',
    btnClass: 'from-emerald-500 to-teal-500',
  },
};

const getTalentConfig = (value) => TALENT_OPTIONS.find(t => t.value === value) || { value, ar: value, en: value, color: 'bg-gray-100 text-gray-700 border-gray-200' };

const HakimPlanCard = ({ type, plan, isRTL, loading, onGenerate, onExport }) => {
  const [stepsOpen, setStepsOpen] = useState(true);
  const cfg = PLAN_CONFIG[type];
  const Icon = cfg.icon;
  const hakimPose = loading ? HAKIM_POSES.thinking : HAKIM_POSES[type];
  const hasPlan = !!plan;

  return (
    <Card className={`border ${cfg.border} overflow-hidden`}>
      <div className={`relative ${cfg.bg}`}>
        <div className={`absolute top-0 left-0 right-0 h-1 bg-gradient-to-l ${cfg.gradient}`} />
        <div className="p-4 pt-5">
          <div className="flex items-start gap-3">
            <div className="w-14 h-14 rounded-2xl bg-white/80 dark:bg-gray-800/60 border border-white/50 dark:border-gray-700/50 shadow-sm flex items-center justify-center overflow-hidden flex-shrink-0">
              <img src={hakimPose} alt="حكيم" className={`w-12 h-12 object-contain ${loading ? 'animate-pulse' : ''}`}
                onError={(e) => { e.target.style.display = 'none'; }} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <div className={`w-7 h-7 rounded-lg ${cfg.iconBg} flex items-center justify-center flex-shrink-0`}>
                  <Icon className="h-4 w-4" />
                </div>
                <h4 className="font-bold text-sm font-cairo">{isRTL ? cfg.title_ar : cfg.title_en}</h4>
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">{isRTL ? cfg.desc_ar : cfg.desc_en}</p>
              {!hasPlan && !loading && (
                <Button onClick={onGenerate} size="sm"
                  className={`mt-3 bg-gradient-to-r ${cfg.btnClass} hover:opacity-90 text-white gap-1.5 text-xs h-8 shadow-sm`}>
                  <Sparkles className="h-3.5 w-3.5" />
                  {isRTL ? cfg.btn_ar : cfg.btn_en}
                </Button>
              )}
              {loading && (
                <div className="flex items-center gap-2 mt-3">
                  <Loader2 className="h-4 w-4 animate-spin text-brand-purple" />
                  <span className="text-xs text-muted-foreground font-tajawal">{isRTL ? 'حكيم يحلل ويُعد الخطة...' : 'Hakim is preparing the plan...'}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
      {hasPlan && (
        <>
          <button onClick={() => setStepsOpen(!stepsOpen)}
            className="w-full flex items-center justify-between px-4 py-2.5 border-t border-b border-border/30 bg-muted/20 hover:bg-muted/40 transition-colors">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium font-cairo">{plan.title || (isRTL ? cfg.title_ar : cfg.title_en)}</span>
              {plan.steps && <span className="text-[10px] text-muted-foreground">({plan.steps.length} {isRTL ? 'خطوات' : 'steps'})</span>}
            </div>
            <div className="flex items-center gap-1">
              {onExport && (
                <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); onExport(type); }}
                  className="h-6 px-2 text-[10px] gap-1 text-brand-turquoise hover:text-brand-turquoise">
                  <Download className="h-3 w-3" /> {isRTL ? 'تصدير' : 'Export'}
                </Button>
              )}
              <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); onGenerate(); }}
                className="h-6 px-2 text-[10px] gap-1 text-brand-purple hover:text-brand-purple">
                <Sparkles className="h-3 w-3" /> {isRTL ? 'إعادة' : 'Redo'}
              </Button>
              {stepsOpen ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
            </div>
          </button>
          {stepsOpen && (
            <CardContent className="p-4 space-y-2.5">
              {plan.summary && <p className="text-xs text-muted-foreground bg-muted/30 p-2.5 rounded-lg leading-relaxed font-tajawal">{plan.summary}</p>}
              {plan.steps?.map((step, i) => (
                <div key={i} className={`p-3 rounded-xl border ${cfg.stepBg}`}>
                  <div className="flex items-start gap-3">
                    <div className={`w-6 h-6 rounded-full ${cfg.iconBg} flex items-center justify-center flex-shrink-0 text-xs font-bold mt-0.5`}>{i + 1}</div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-sm font-cairo">{step.title}</p>
                      <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{step.description}</p>
                      <div className="flex flex-wrap items-center gap-3 mt-2">
                        {step.duration && <span className="flex items-center gap-1 text-[11px] text-muted-foreground"><Clock className="h-3 w-3" /> {step.duration}</span>}
                        {step.responsible && <span className="flex items-center gap-1 text-[11px] text-muted-foreground"><User className="h-3 w-3" /> {step.responsible}</span>}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
              {plan.expected_outcome && (
                <div className="flex items-start gap-2 p-3 bg-blue-50/50 dark:bg-blue-950/10 rounded-xl border border-blue-100 dark:border-blue-800/20">
                  <Target className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-xs font-medium text-blue-700 dark:text-blue-300 font-cairo">{isRTL ? 'النتيجة المتوقعة' : 'Expected Outcome'}</p>
                    <p className="text-xs text-blue-600/80 dark:text-blue-400/80 mt-0.5">{plan.expected_outcome}</p>
                  </div>
                </div>
              )}
            </CardContent>
          )}
        </>
      )}
    </Card>
  );
};

const TalentSelector = ({ talents = [], onChange, isRTL, editing }) => {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const available = TALENT_OPTIONS.filter(t => !talents.includes(t.value));

  if (!editing) {
    if (!talents.length) return null;
    return (
      <div className="flex flex-wrap gap-1.5">
        {talents.map(t => {
          const cfg = getTalentConfig(t);
          return (
            <Badge key={t} variant="outline" className={`text-[11px] px-2 py-0.5 border ${cfg.color}`}>
              <Star className="h-3 w-3 me-1 fill-current" />
              {isRTL ? cfg.ar : cfg.en}
            </Badge>
          );
        })}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {talents.map(t => {
          const cfg = getTalentConfig(t);
          return (
            <Badge key={t} variant="outline" className={`text-[11px] px-2 py-0.5 border ${cfg.color} cursor-pointer hover:opacity-80`}
              onClick={() => onChange(talents.filter(x => x !== t))}>
              {isRTL ? cfg.ar : cfg.en}
              <XCircle className="h-3 w-3 ms-1" />
            </Badge>
          );
        })}
      </div>
      {available.length > 0 && (
        <div className="relative">
          <Button variant="outline" size="sm" className="h-7 text-xs gap-1" onClick={() => setDropdownOpen(!dropdownOpen)}>
            <Plus className="h-3 w-3" />
            {isRTL ? 'إضافة موهبة' : 'Add Talent'}
          </Button>
          {dropdownOpen && (
            <div className="absolute z-50 mt-1 w-56 rounded-lg border bg-popover shadow-lg p-1 max-h-48 overflow-y-auto">
              {available.map(opt => (
                <button key={opt.value}
                  className="w-full flex items-center gap-2 px-3 py-2 text-xs rounded-md hover:bg-muted transition-colors text-start"
                  onClick={() => { onChange([...talents, opt.value]); setDropdownOpen(false); }}>
                  <Star className="h-3 w-3 text-amber-500" />
                  {isRTL ? opt.ar : opt.en}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default function StudentProfilePage() {
  const { studentId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, api } = useAuth();
  const { isRTL, isDark, toggleTheme, toggleLanguage } = useTheme();
  const { nassaqConfirm, nassaqError, nassaqWarning } = useNassaqAlert();

  const classId = location.state?.classId;
  const className = location.state?.className;
  const fromPath = location.state?.fromPath;

  const [student, setStudent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState({});
  const [activeTab, setActiveTab] = useState('info');
  const [classes, setClasses] = useState([]);

  const [attendanceSummary, setAttendanceSummary] = useState(null);
  const [loadingAttendance, setLoadingAttendance] = useState(false);

  const [riskData, setRiskData] = useState(null);
  const [loadingRisk, setLoadingRisk] = useState(false);
  const [remedialPlan, setRemedialPlan] = useState(null);
  const [enrichmentPlan, setEnrichmentPlan] = useState(null);
  const [loadingRemedial, setLoadingRemedial] = useState(false);
  const [loadingEnrichment, setLoadingEnrichment] = useState(false);
  const [exportingPlan, setExportingPlan] = useState(false);
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [exportPlanType, setExportPlanType] = useState('both');
  const [exportFormat, setExportFormat] = useState('pdf');
  const [actionLoading, setActionLoading] = useState('');

  const headers = useMemo(() => {
    const h = {};
    const token = localStorage.getItem('nassaq_token');
    if (token) h.Authorization = `Bearer ${token}`;
    const tenantId = user?.tenant_id || localStorage.getItem('nassaq_tenant_id');
    if (tenantId) h['X-Tenant-ID'] = tenantId;
    return h;
  }, [user?.tenant_id]);

  const rolePrefix = user?.role === 'school_principal' ? '/principal' : '/admin';

  const fetchStudent = useCallback(async () => {
    setLoading(true);
    try {
      const [studentRes, classesRes] = await Promise.all([
        api.get(`/students/${studentId}`, { headers }),
        api.get('/classes', { headers }).catch(() => ({ data: [] })),
      ]);
      const s = studentRes.data;
      setStudent(s);
      setFormData({ ...s });
      setClasses(Array.isArray(classesRes.data) ? classesRes.data : []);
    } catch {
      nassaqError(isRTL ? 'خطأ في تحميل بيانات الطالب' : 'Error loading student data');
    } finally {
      setLoading(false);
    }
  }, [api, studentId, headers, isRTL, nassaqError]);

  useEffect(() => { fetchStudent(); }, [fetchStudent]);

  const fetchAttendance = useCallback(async () => {
    if (!studentId) return;
    setLoadingAttendance(true);
    try {
      const res = await api.get(`/attendance/summary/student/${studentId}`, { headers });
      setAttendanceSummary(res.data);
    } catch {
      setAttendanceSummary(null);
    } finally {
      setLoadingAttendance(false);
    }
  }, [api, studentId, headers]);

  const fetchRiskData = useCallback(async () => {
    if (!studentId) return;
    setLoadingRisk(true);
    try {
      const res = await api.get(`/hakim/student/${studentId}/risk?days=30`, { headers });
      setRiskData(res.data?.data || res.data);
    } catch {
      setRiskData(null);
    } finally {
      setLoadingRisk(false);
    }
  }, [api, studentId, headers]);

  useEffect(() => {
    if (activeTab === 'academic') {
      fetchAttendance();
      fetchRiskData();
    }
  }, [activeTab, fetchAttendance, fetchRiskData]);

  const generatePlan = async (planType) => {
    if (!studentId) return;
    const setLoadFn = planType === 'remedial' ? setLoadingRemedial : setLoadingEnrichment;
    const setPlanFn = planType === 'remedial' ? setRemedialPlan : setEnrichmentPlan;
    setLoadFn(true);
    try {
      const res = await api.post(`/hakim/student/${studentId}/ai-plans`, {}, { headers });
      const plans = res.data?.plans;
      if (plans) {
        if (planType === 'remedial') {
          setPlanFn(plans.remedial_plan);
          if (!enrichmentPlan && plans.enrichment_plan) setEnrichmentPlan(plans.enrichment_plan);
        } else {
          setPlanFn(plans.enrichment_plan);
          if (!remedialPlan && plans.remedial_plan) setRemedialPlan(plans.remedial_plan);
        }
      }
      toast.success(isRTL ? 'تم توليد الخطة بواسطة حكيم' : 'Plan generated by Hakim');
    } catch {
      nassaqError(isRTL ? 'فشل في توليد الخطة' : 'Failed to generate plan');
    } finally {
      setLoadFn(false);
    }
  };

  const openExportModal = (planType) => {
    setExportPlanType(planType || 'both');
    setExportFormat('pdf');
    setExportModalOpen(true);
  };

  const handleExportPlan = async (planType, format = 'docx') => {
    if (!studentId) return;
    const payload = { plan_type: planType };
    if (planType === 'remedial' || planType === 'both') payload.remedial_plan = remedialPlan;
    if (planType === 'enrichment' || planType === 'both') payload.enrichment_plan = enrichmentPlan;
    setExportingPlan(true);
    try {
      const isPdf = format === 'pdf';
      const url = isPdf
        ? `/export/student-plans/${studentId}/pdf`
        : `/export/student-plans/${studentId}`;
      const mimeType = isPdf
        ? 'application/pdf'
        : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
      const ext = isPdf ? 'pdf' : 'docx';

      const res = await api.post(url, payload, { headers, responseType: 'blob' });

      if (res.data.type === 'application/json') {
        const text = await res.data.text();
        const errData = JSON.parse(text);
        throw new Error(errData.detail || 'Export failed');
      }

      const blob = new Blob([res.data], { type: mimeType });
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      const safeName = (student?.full_name || 'student').replace(/\s+/g, '_');
      const date = new Date().toISOString().split('T')[0];
      const suffix = planType === 'remedial' ? 'Remedial_Plan' : planType === 'enrichment' ? 'Enrichment_Plan' : 'Plans';
      a.href = blobUrl;
      a.download = `${safeName}_${suffix}_${date}.${ext}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(blobUrl);
      a.remove();
      toast.success(isRTL ? 'تم تصدير الخطة بنجاح' : 'Plan exported successfully');
      setExportModalOpen(false);
    } catch (err) {
      console.error('Plan export error:', err);
      let detail = err?.message || '';
      if (err?.response?.data instanceof Blob) {
        try {
          const text = await err.response.data.text();
          const parsed = JSON.parse(text);
          detail = parsed.detail || detail;
        } catch (_) {}
      } else if (err?.response?.data?.detail) {
        detail = err.response.data.detail;
      }
      nassaqError(isRTL
        ? `فشل تصدير الخطة: ${detail || 'خطأ غير معروف'}`
        : `Failed to export plan: ${detail || 'Unknown error'}`);
    } finally {
      setExportingPlan(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const updateData = {};
      if (formData.full_name && formData.full_name !== student.full_name) updateData.full_name = formData.full_name;
      if (formData.email && formData.email !== student.email) updateData.email = formData.email;
      if (formData.phone !== undefined && formData.phone !== student.phone) updateData.phone = formData.phone;
      if (formData.grade !== undefined && formData.grade !== student.grade) updateData.grade = formData.grade;
      if (formData.class_id && formData.class_id !== student.class_id) updateData.class_id = formData.class_id;
      if (formData.gender && formData.gender !== student.gender) updateData.gender = formData.gender;
      if (formData.date_of_birth !== undefined && formData.date_of_birth !== student.date_of_birth) updateData.date_of_birth = formData.date_of_birth;
      if (formData.parent_name !== undefined && formData.parent_name !== student.parent_name) updateData.parent_name = formData.parent_name;
      if (formData.parent_phone !== undefined && formData.parent_phone !== student.parent_phone) updateData.parent_phone = formData.parent_phone;

      const currentTalents = JSON.stringify(formData.talents || []);
      const originalTalents = JSON.stringify(student.talents || []);
      if (currentTalents !== originalTalents) {
        updateData.talents = formData.talents || [];
      }

      if (Object.keys(updateData).length === 0) {
        nassaqWarning(isRTL ? 'لا توجد تغييرات للحفظ' : 'No changes to save');
        setSaving(false);
        return;
      }

      await api.put(`/students/${student.id}`, updateData, { headers });
      toast.success(isRTL ? 'تم حفظ بيانات الطالب بنجاح' : 'Student data saved successfully');
      setEditing(false);
      fetchStudent();
    } catch (error) {
      const msg = error.response?.data?.detail;
      nassaqError(typeof msg === 'string' ? msg : (isRTL ? 'فشل الحفظ' : 'Save failed'));
    } finally {
      setSaving(false);
    }
  };

  const handleAction = async (action) => {
    setActionLoading(action);
    try {
      switch (action) {
        case 'suspend':
          await api.put(`/principal/student/${student.id}/status`, { status: 'suspended' }, { headers });
          toast.success(isRTL ? 'تم تعليق الحساب' : 'Account suspended');
          break;
        case 'activate':
          await api.put(`/principal/student/${student.id}/status`, { status: 'active' }, { headers });
          toast.success(isRTL ? 'تم تفعيل الحساب' : 'Account activated');
          break;
        case 'reset-password': {
          const genRes = await api.post('/principal/generate-password', {}, { headers });
          const tempPass = genRes.data.password;
          await api.put(`/principal/student/${student.id}/credentials`, { new_password: tempPass }, { headers });
          toast.success(isRTL ? `تم إعادة تعيين كلمة المرور إلى: ${tempPass}` : `Password reset to: ${tempPass}`);
          break;
        }
        case 'delete':
          nassaqConfirm(
            isRTL ? 'هل أنت متأكد من حذف هذا الحساب؟ لا يمكن التراجع.' : 'Are you sure you want to delete this account? This cannot be undone.',
            async () => {
              try {
                await api.delete(`/students/${student.id}`, { headers });
                toast.success(isRTL ? 'تم حذف الحساب' : 'Account deleted');
                handleBack();
              } catch {
                nassaqError(isRTL ? 'فشل حذف الحساب' : 'Failed to delete account');
              }
            },
            { title: isRTL ? 'تأكيد الحذف' : 'Confirm Delete', confirmText: isRTL ? 'نعم، احذف' : 'Yes, Delete', cancelText: isRTL ? 'إلغاء' : 'Cancel' }
          );
          setActionLoading('');
          return;
        default: break;
      }
      fetchStudent();
    } catch (error) {
      const msg = error.response?.data?.detail;
      nassaqError(typeof msg === 'string' ? msg : (isRTL ? 'فشلت العملية' : 'Operation failed'));
    } finally {
      setActionLoading('');
    }
  };

  const handleBack = () => {
    if (fromPath) {
      navigate(fromPath);
    } else if (classId) {
      navigate(`${rolePrefix}/classes/${classId}`);
    } else {
      navigate(`${rolePrefix}/users-management?filter=students`);
    }
  };

  const getRiskColor = (c) => {
    const map = { critical: 'bg-red-100 text-red-700 border-red-200', high: 'bg-orange-100 text-orange-700 border-orange-200', medium: 'bg-yellow-100 text-yellow-700 border-yellow-200', low: 'bg-green-100 text-green-700 border-green-200' };
    return map[c] || 'bg-gray-100 text-gray-700 border-gray-200';
  };
  const getRiskLabel = (c) => {
    const map = { critical: isRTL ? 'حرج' : 'Critical', high: isRTL ? 'مرتفع' : 'High', medium: isRTL ? 'متوسط' : 'Medium', low: isRTL ? 'منخفض' : 'Low' };
    return map[c] || c;
  };
  const getRiskBarColor = (c) => {
    const map = { critical: '[&>div]:bg-red-500', high: '[&>div]:bg-orange-500', medium: '[&>div]:bg-yellow-500', low: '[&>div]:bg-green-500' };
    return map[c] || '[&>div]:bg-gray-400';
  };

  const BackArrow = isRTL ? ArrowRight : ArrowLeft;

  const classObj = classes.find(c => c.id === student?.class_id);

  if (loading) {
    return (
      <div className="flex min-h-screen bg-background">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
        </div>
      </div>
    );
  }

  if (!student) {
    return (
      <div className="flex min-h-screen bg-background">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center">
          <Card className="p-8 text-center max-w-md">
            <User className="h-12 w-12 mx-auto text-muted-foreground/30 mb-3" />
            <p className="text-muted-foreground">{isRTL ? 'لم يتم العثور على الطالب' : 'Student not found'}</p>
            <Button variant="outline" className="mt-4" onClick={handleBack}>
              <BackArrow className="h-4 w-4 me-2" /> {isRTL ? 'العودة' : 'Go Back'}
            </Button>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <header className="sticky top-0 z-30 backdrop-blur-xl bg-background/80 border-b px-4 md:px-6 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" className="h-9 w-9" onClick={handleBack}>
                <BackArrow className="h-5 w-5" />
              </Button>
              <div>
                <h1 className="text-lg font-bold font-cairo">{student.full_name}</h1>
                <nav className="flex items-center gap-1 text-xs text-muted-foreground">
                  <button onClick={() => navigate(`${rolePrefix}/users-management?filter=students`)} className="hover:text-foreground transition-colors">
                    {isRTL ? 'إدارة المستخدمين' : 'User Management'}
                  </button>
                  {className && (
                    <>
                      <ChevronRight className="h-3 w-3" />
                      <button onClick={() => classId && navigate(`${rolePrefix}/classes/${classId}`)} className="hover:text-foreground transition-colors">
                        {className}
                      </button>
                    </>
                  )}
                  <ChevronRight className="h-3 w-3" />
                  <span className="text-foreground font-medium">{student.full_name}</span>
                </nav>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <NotificationBell />
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={toggleTheme}>
                {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </Button>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={toggleLanguage}>
                <Globe className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </header>

        <div className="p-4 md:p-6 max-w-5xl mx-auto space-y-6">
          <div className="bg-gradient-to-r from-brand-turquoise/10 to-brand-purple/10 dark:from-brand-turquoise/5 dark:to-brand-purple/5 rounded-2xl border p-6">
            <div className="flex flex-col sm:flex-row items-start gap-4">
              <div className={`relative w-20 h-20 rounded-full bg-gradient-to-br from-brand-turquoise to-brand-purple flex items-center justify-center shadow-lg ${student.is_gifted ? 'ring-3 ring-amber-400 ring-offset-2' : ''}`}>
                <span className="text-white font-bold text-3xl">{student.full_name?.charAt(0)}</span>
                {student.is_gifted && (
                  <div className="absolute -top-1 -end-1 w-6 h-6 rounded-full bg-amber-400 flex items-center justify-center shadow-md">
                    <Star className="h-3.5 w-3.5 text-white fill-white" />
                  </div>
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex flex-col sm:flex-row sm:items-center gap-2 mb-2">
                  <h2 className="text-2xl font-bold font-cairo">{student.full_name}</h2>
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge variant={student.is_active !== false ? 'default' : 'destructive'} className="text-xs">
                      {student.is_active !== false ? (isRTL ? 'نشط' : 'Active') : (isRTL ? 'معلق' : 'Suspended')}
                    </Badge>
                    {student.grade && (
                      <Badge variant="outline" className="text-xs">
                        <GraduationCap className="h-3 w-3 me-1" />
                        {student.grade} {classObj ? `- ${classObj.name}` : student.section ? `- ${student.section}` : ''}
                      </Badge>
                    )}
                  </div>
                </div>
                <p className="text-sm text-muted-foreground">{student.student_number || student.id?.slice(0, 8)}</p>
                {(student.talents?.length > 0) && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {student.talents.map(t => {
                      const cfg = getTalentConfig(t);
                      return (
                        <Badge key={t} variant="outline" className={`text-[11px] px-2 py-0.5 border ${cfg.color}`}>
                          <Star className="h-3 w-3 me-1 fill-current" />
                          {isRTL ? cfg.ar : cfg.en}
                        </Badge>
                      );
                    })}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-2 shrink-0">
                {!editing ? (
                  <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
                    <Edit className="h-3.5 w-3.5 me-1" /> {isRTL ? 'تعديل' : 'Edit'}
                  </Button>
                ) : (
                  <>
                    <Button size="sm" onClick={handleSave} disabled={saving}>
                      {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin me-1" /> : <Save className="h-3.5 w-3.5 me-1" />}
                      {isRTL ? 'حفظ' : 'Save'}
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => { setEditing(false); setFormData({ ...student }); }}>
                      <X className="h-3.5 w-3.5" />
                    </Button>
                  </>
                )}
              </div>
            </div>
          </div>

          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="grid grid-cols-4 mb-4">
              <TabsTrigger value="info" className="text-xs gap-1">
                <User className="h-3.5 w-3.5" /> {isRTL ? 'البيانات' : 'Info'}
              </TabsTrigger>
              <TabsTrigger value="guardian" className="text-xs gap-1">
                <Heart className="h-3.5 w-3.5" /> {isRTL ? 'ولي الأمر' : 'Guardian'}
              </TabsTrigger>
              <TabsTrigger value="academic" className="text-xs gap-1">
                <Brain className="h-3.5 w-3.5" /> {isRTL ? 'الأكاديمي' : 'Academic'}
              </TabsTrigger>
              <TabsTrigger value="actions" className="text-xs gap-1">
                <Shield className="h-3.5 w-3.5" /> {isRTL ? 'إجراءات' : 'Actions'}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="info">
              <Card>
                <CardContent className="p-6 space-y-6">
                  <h3 className="font-bold text-base font-cairo flex items-center gap-2">
                    <User className="h-5 w-5 text-brand-turquoise" />
                    {isRTL ? 'بيانات الطالب' : 'Student Information'}
                  </h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                    <div className="space-y-1.5">
                      <Label className="text-xs text-muted-foreground">{isRTL ? 'الاسم الكامل' : 'Full Name'}</Label>
                      {editing ? (
                        <Input value={formData.full_name || ''} onChange={(e) => setFormData({ ...formData, full_name: e.target.value })} />
                      ) : (
                        <p className="font-medium text-sm">{student.full_name}</p>
                      )}
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs text-muted-foreground">{isRTL ? 'رقم الطالب / الهوية' : 'Student ID / National ID'}</Label>
                      <p className="font-medium text-sm flex items-center gap-1.5"><Hash className="h-3.5 w-3.5 text-muted-foreground" /> {student.student_number || student.national_id || '-'}</p>
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs text-muted-foreground">{isRTL ? 'الصف والفصل' : 'Grade & Class'}</Label>
                      {editing ? (
                        <div className="flex gap-2">
                          <Input value={formData.grade || ''} onChange={(e) => setFormData({ ...formData, grade: e.target.value })} placeholder={isRTL ? 'الصف' : 'Grade'} className="flex-1" />
                          <Select value={formData.class_id || ''} onValueChange={(v) => setFormData({ ...formData, class_id: v })}>
                            <SelectTrigger className="flex-1"><SelectValue placeholder={isRTL ? 'الفصل' : 'Class'} /></SelectTrigger>
                            <SelectContent>
                              {classes.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                            </SelectContent>
                          </Select>
                        </div>
                      ) : (
                        <p className="font-medium text-sm flex items-center gap-1.5">
                          <BookOpen className="h-3.5 w-3.5 text-muted-foreground" />
                          {student.grade || '-'} {classObj ? `- ${classObj.name}` : student.section ? `- ${student.section}` : ''}
                        </p>
                      )}
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs text-muted-foreground">{isRTL ? 'الجنس' : 'Gender'}</Label>
                      {editing ? (
                        <Select value={formData.gender || ''} onValueChange={(v) => setFormData({ ...formData, gender: v })}>
                          <SelectTrigger><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="male">{isRTL ? 'ذكر' : 'Male'}</SelectItem>
                            <SelectItem value="female">{isRTL ? 'أنثى' : 'Female'}</SelectItem>
                          </SelectContent>
                        </Select>
                      ) : (
                        <p className="font-medium text-sm">
                          {student.gender === 'male' ? (isRTL ? 'ذكر' : 'Male') : student.gender === 'female' ? (isRTL ? 'أنثى' : 'Female') : '-'}
                        </p>
                      )}
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs text-muted-foreground">{isRTL ? 'تاريخ الميلاد' : 'Date of Birth'}</Label>
                      {editing ? (
                        <Input type="date" value={formData.date_of_birth || ''} onChange={(e) => setFormData({ ...formData, date_of_birth: e.target.value })} />
                      ) : (
                        <p className="font-medium text-sm flex items-center gap-1.5">
                          <Calendar className="h-3.5 w-3.5 text-muted-foreground" /> {student.date_of_birth || '-'}
                        </p>
                      )}
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs text-muted-foreground">{isRTL ? 'البريد الإلكتروني' : 'Email'}</Label>
                      {editing ? (
                        <Input value={formData.email || ''} onChange={(e) => setFormData({ ...formData, email: e.target.value })} />
                      ) : (
                        <p className="font-medium text-sm flex items-center gap-1.5"><Mail className="h-3.5 w-3.5 text-muted-foreground" /> {student.email || '-'}</p>
                      )}
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs text-muted-foreground">{isRTL ? 'الهاتف' : 'Phone'}</Label>
                      {editing ? (
                        <Input value={formData.phone || ''} onChange={(e) => setFormData({ ...formData, phone: e.target.value })} />
                      ) : (
                        <p className="font-medium text-sm flex items-center gap-1.5"><Phone className="h-3.5 w-3.5 text-muted-foreground" /> {student.phone || '-'}</p>
                      )}
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs text-muted-foreground">{isRTL ? 'الحالة الأكاديمية' : 'Academic Status'}</Label>
                      <Badge variant={student.is_active !== false ? 'default' : 'destructive'}>
                        {student.is_active !== false ? (isRTL ? 'نشط' : 'Active') : (isRTL ? 'معلق' : 'Suspended')}
                      </Badge>
                    </div>
                  </div>

                  <div className="border-t pt-5 space-y-3">
                    <h4 className="font-semibold text-sm font-cairo flex items-center gap-2">
                      <Award className="h-4 w-4 text-amber-500" />
                      {isRTL ? 'المواهب والتميز' : 'Talents & Gifts'}
                      {student.is_gifted && (
                        <Badge className="bg-amber-100 text-amber-700 border-amber-200 text-[10px]">
                          <Star className="h-3 w-3 me-0.5 fill-current" /> {isRTL ? 'موهوب' : 'Gifted'}
                        </Badge>
                      )}
                    </h4>
                    <TalentSelector
                      talents={editing ? (formData.talents || []) : (student.talents || [])}
                      onChange={(newTalents) => setFormData({ ...formData, talents: newTalents })}
                      isRTL={isRTL}
                      editing={editing}
                    />
                    {!editing && (!student.talents || student.talents.length === 0) && (
                      <p className="text-xs text-muted-foreground">{isRTL ? 'لم يتم تحديد مواهب بعد' : 'No talents assigned yet'}</p>
                    )}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="guardian">
              <Card>
                <CardContent className="p-6 space-y-6">
                  <h3 className="font-bold text-base font-cairo flex items-center gap-2">
                    <Heart className="h-5 w-5 text-rose-500" />
                    {isRTL ? 'بيانات ولي الأمر' : 'Guardian Information'}
                  </h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                    <div className="space-y-1.5">
                      <Label className="text-xs text-muted-foreground">{isRTL ? 'اسم ولي الأمر' : 'Guardian Full Name'}</Label>
                      {editing ? (
                        <Input value={formData.parent_name || ''} onChange={(e) => setFormData({ ...formData, parent_name: e.target.value })} />
                      ) : (
                        <p className="font-medium text-sm">{student.parent_name || '-'}</p>
                      )}
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs text-muted-foreground">{isRTL ? 'رقم الهاتف' : 'Phone Number'}</Label>
                      {editing ? (
                        <Input value={formData.parent_phone || ''} onChange={(e) => setFormData({ ...formData, parent_phone: e.target.value })} />
                      ) : (
                        <p className="font-medium text-sm flex items-center gap-1.5 direction-ltr">
                          <Phone className="h-3.5 w-3.5 text-muted-foreground" /> {student.parent_phone || '-'}
                        </p>
                      )}
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs text-muted-foreground">{isRTL ? 'البريد الإلكتروني' : 'Email'}</Label>
                      <p className="font-medium text-sm flex items-center gap-1.5">
                        <Mail className="h-3.5 w-3.5 text-muted-foreground" /> {student.parent_email || '-'}
                      </p>
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs text-muted-foreground">{isRTL ? 'صلة القرابة' : 'Relationship'}</Label>
                      <p className="font-medium text-sm">{student.parent_relationship || (isRTL ? 'ولي أمر' : 'Parent/Guardian')}</p>
                    </div>
                  </div>
                  {!student.parent_name && !editing && (
                    <div className="text-center py-6">
                      <Heart className="h-10 w-10 mx-auto text-muted-foreground/20 mb-2" />
                      <p className="text-sm text-muted-foreground">{isRTL ? 'لم يتم إضافة بيانات ولي الأمر بعد' : 'No guardian info added yet'}</p>
                      <Button variant="outline" size="sm" className="mt-3" onClick={() => { setEditing(true); setActiveTab('guardian'); }}>
                        <Plus className="h-3.5 w-3.5 me-1" /> {isRTL ? 'إضافة بيانات ولي الأمر' : 'Add Guardian Info'}
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="academic" className="space-y-4">
              <Card>
                <CardContent className="p-6 space-y-4">
                  <h3 className="font-bold text-base font-cairo flex items-center gap-2">
                    <Activity className="h-5 w-5 text-brand-turquoise" />
                    {isRTL ? 'ملخص الحضور' : 'Attendance Summary'}
                  </h3>
                  {loadingAttendance ? (
                    <div className="flex justify-center py-4"><Loader2 className="h-5 w-5 animate-spin text-brand-turquoise" /></div>
                  ) : attendanceSummary ? (
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      {[
                        { label: isRTL ? 'حاضر' : 'Present', value: attendanceSummary.present_count ?? attendanceSummary.present ?? 0, color: 'text-green-600', bg: 'bg-green-50 dark:bg-green-950/20' },
                        { label: isRTL ? 'غائب' : 'Absent', value: attendanceSummary.absent_count ?? attendanceSummary.absent ?? 0, color: 'text-red-600', bg: 'bg-red-50 dark:bg-red-950/20' },
                        { label: isRTL ? 'متأخر' : 'Late', value: attendanceSummary.late_count ?? attendanceSummary.late ?? 0, color: 'text-amber-600', bg: 'bg-amber-50 dark:bg-amber-950/20' },
                        { label: isRTL ? 'بعذر' : 'Excused', value: attendanceSummary.excused_count ?? attendanceSummary.excused ?? 0, color: 'text-blue-600', bg: 'bg-blue-50 dark:bg-blue-950/20' },
                      ].map((item, i) => (
                        <div key={i} className={`text-center p-4 rounded-xl ${item.bg}`}>
                          <p className={`text-2xl font-bold font-cairo ${item.color}`}>{item.value}</p>
                          <p className="text-xs text-muted-foreground mt-1">{item.label}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground text-center py-4">{isRTL ? 'لا توجد بيانات حضور' : 'No attendance data available'}</p>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardContent className="p-6 space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="font-bold text-base font-cairo flex items-center gap-2">
                      <Brain className="h-5 w-5 text-brand-purple" />
                      {isRTL ? 'التحليل الذكي والخطط' : 'AI Analysis & Plans'}
                    </h3>
                    <Button variant="ghost" size="sm" onClick={fetchRiskData} className="text-xs">
                      <Activity className="h-3.5 w-3.5 me-1" /> {isRTL ? 'تحديث' : 'Refresh'}
                    </Button>
                  </div>

                  {loadingRisk ? (
                    <div className="flex justify-center py-6"><Loader2 className="h-6 w-6 animate-spin text-brand-turquoise" /></div>
                  ) : riskData ? (
                    <>
                      <div className="bg-gradient-to-br from-brand-navy/5 to-brand-purple/5 dark:from-brand-navy/20 dark:to-brand-purple/10 p-4 rounded-xl">
                        <div className="flex items-center justify-between mb-3">
                          <h4 className="font-bold text-sm font-cairo">{isRTL ? 'مؤشر الأداء العام' : 'Overall Performance'}</h4>
                          <Badge className={getRiskColor(riskData.risk_category)}>{getRiskLabel(riskData.risk_category)}</Badge>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="flex-1">
                            <Progress value={riskData.risk_score || 0} className={`h-3 rounded-full bg-gray-100 dark:bg-gray-800 ${getRiskBarColor(riskData.risk_category)}`} />
                          </div>
                          <span className="text-lg font-bold font-cairo tabular-nums">{Math.round(riskData.risk_score || 0)}%</span>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        {riskData.breakdown && Object.entries(riskData.breakdown).map(([key, val]) => {
                          const labels = {
                            attendance: { ar: 'الحضور', icon: <Calendar className="h-4 w-4" /> },
                            participation: { ar: 'المشاركة', icon: <Zap className="h-4 w-4" /> },
                            behaviour: { ar: 'السلوك', icon: <Shield className="h-4 w-4" /> },
                            academic: { ar: 'الأكاديمي', icon: <BookOpen className="h-4 w-4" /> },
                          };
                          const lbl = labels[key] || { ar: key, icon: <Activity className="h-4 w-4" /> };
                          const score = Math.round(typeof val === 'number' ? val : val?.score || 0);
                          const scoreColor = score >= 80 ? 'text-green-600' : score >= 60 ? 'text-amber-600' : 'text-red-600';
                          return (
                            <div key={key} className="text-center p-3 bg-muted/30 rounded-xl">
                              <div className="flex justify-center text-muted-foreground mb-1.5">{lbl.icon}</div>
                              <p className={`text-xl font-bold font-cairo ${scoreColor}`}>{score}%</p>
                              <p className="text-[11px] text-muted-foreground font-tajawal mt-0.5">{isRTL ? lbl.ar : key}</p>
                            </div>
                          );
                        })}
                      </div>

                      {riskData.factors?.length > 0 && (
                        <div className="space-y-2">
                          <h4 className="text-sm font-medium flex items-center gap-2">
                            <Target className="h-4 w-4 text-brand-turquoise" /> {isRTL ? 'نقاط الملاحظة' : 'Key Observations'}
                          </h4>
                          {riskData.factors.map((f, i) => (
                            <div key={i} className="flex items-start gap-2 text-sm p-2.5 bg-amber-50/60 dark:bg-amber-950/10 rounded-lg border border-amber-100 dark:border-amber-800/20">
                              <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
                              <span className="text-sm">{f.message || f.message_ar || f}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="text-center py-6">
                      <Brain className="h-10 w-10 mx-auto text-muted-foreground/20 mb-2" />
                      <p className="text-sm text-muted-foreground">{isRTL ? 'لا تتوفر بيانات تحليلية حالياً' : 'No analytics available yet'}</p>
                    </div>
                  )}
                </CardContent>
              </Card>

              <div className="relative my-2">
                <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-dashed border-brand-purple/20" /></div>
                <div className="relative flex justify-center">
                  <span className="bg-background px-3 text-xs text-brand-purple font-cairo font-medium">{isRTL ? 'خطط حكيم الذكية' : 'Hakim AI Plans'}</span>
                </div>
              </div>

              <HakimPlanCard type="remedial" plan={remedialPlan} isRTL={isRTL} loading={loadingRemedial}
                onGenerate={() => generatePlan('remedial')} onExport={remedialPlan ? openExportModal : null} />

              <HakimPlanCard type="enrichment" plan={enrichmentPlan} isRTL={isRTL} loading={loadingEnrichment}
                onGenerate={() => generatePlan('enrichment')} onExport={enrichmentPlan ? openExportModal : null} />

              {remedialPlan && enrichmentPlan && (
                <Button variant="outline" className="w-full gap-2 border-brand-navy/20 text-brand-navy hover:bg-brand-navy/5"
                  onClick={() => openExportModal('both')} disabled={exportingPlan}>
                  {exportingPlan ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                  {isRTL ? 'تصدير الخطتين معاً' : 'Export Both Plans'}
                </Button>
              )}
            </TabsContent>

            <TabsContent value="actions">
              <Card>
                <CardContent className="p-6 space-y-4">
                  <h3 className="font-bold text-base font-cairo flex items-center gap-2">
                    <Shield className="h-5 w-5 text-brand-navy" />
                    {isRTL ? 'إجراءات الحساب' : 'Account Actions'}
                  </h3>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <Button variant="outline" className="justify-start h-auto py-3" onClick={() => handleAction('reset-password')} disabled={!!actionLoading}>
                      <Key className="h-4 w-4 me-2 text-blue-500" />
                      <div className="text-start">
                        <p className="text-sm font-medium">{isRTL ? 'إعادة تعيين كلمة المرور' : 'Reset Password'}</p>
                        <p className="text-xs text-muted-foreground">{isRTL ? 'إرسال كلمة مرور جديدة' : 'Send new password'}</p>
                      </div>
                      {actionLoading === 'reset-password' && <Loader2 className="h-4 w-4 animate-spin ms-auto" />}
                    </Button>

                    {student.is_active !== false ? (
                      <Button variant="outline" className="justify-start h-auto py-3 border-amber-200 hover:bg-amber-50"
                        onClick={() => handleAction('suspend')} disabled={!!actionLoading}>
                        <UserX className="h-4 w-4 me-2 text-amber-500" />
                        <div className="text-start">
                          <p className="text-sm font-medium">{isRTL ? 'تعليق الحساب' : 'Suspend Account'}</p>
                          <p className="text-xs text-muted-foreground">{isRTL ? 'تعليق مؤقت للحساب' : 'Temporarily suspend'}</p>
                        </div>
                        {actionLoading === 'suspend' && <Loader2 className="h-4 w-4 animate-spin ms-auto" />}
                      </Button>
                    ) : (
                      <Button variant="outline" className="justify-start h-auto py-3 border-green-200 hover:bg-green-50"
                        onClick={() => handleAction('activate')} disabled={!!actionLoading}>
                        <UserCheck className="h-4 w-4 me-2 text-green-500" />
                        <div className="text-start">
                          <p className="text-sm font-medium">{isRTL ? 'تفعيل الحساب' : 'Activate Account'}</p>
                          <p className="text-xs text-muted-foreground">{isRTL ? 'إعادة تفعيل الحساب' : 'Re-activate account'}</p>
                        </div>
                        {actionLoading === 'activate' && <Loader2 className="h-4 w-4 animate-spin ms-auto" />}
                      </Button>
                    )}

                    <Button variant="outline" className="justify-start h-auto py-3 border-red-200 hover:bg-red-50 sm:col-span-2"
                      onClick={() => handleAction('delete')} disabled={!!actionLoading}>
                      <Trash2 className="h-4 w-4 me-2 text-red-500" />
                      <div className="text-start">
                        <p className="text-sm font-medium text-red-600">{isRTL ? 'حذف الحساب نهائياً' : 'Delete Account Permanently'}</p>
                        <p className="text-xs text-muted-foreground">{isRTL ? 'لا يمكن التراجع عن هذا الإجراء' : 'This action cannot be undone'}</p>
                      </div>
                      {actionLoading === 'delete' && <Loader2 className="h-4 w-4 animate-spin ms-auto" />}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </main>

      <Dialog open={exportModalOpen} onOpenChange={setExportModalOpen}>
        <DialogContent className="sm:max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader>
            <DialogTitle className="font-cairo flex items-center gap-2">
              <Download className="h-5 w-5 text-brand-navy" />
              {isRTL ? 'تصدير الخطة' : 'Export Plan'}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-5 pt-2">
            <div className="space-y-2">
              <Label className="text-sm font-medium font-cairo">{isRTL ? 'نوع الخطة' : 'Plan Type'}</Label>
              <RadioGroup value={exportPlanType} onValueChange={setExportPlanType} className="space-y-2">
                {remedialPlan && (
                  <label className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${exportPlanType === 'remedial' ? 'border-rose-300 bg-rose-50/50 dark:border-rose-700 dark:bg-rose-950/20' : 'border-border hover:border-rose-200'}`}>
                    <RadioGroupItem value="remedial" />
                    <Stethoscope className="h-4 w-4 text-rose-500 flex-shrink-0" />
                    <span className="text-sm font-medium">{isRTL ? 'الخطة العلاجية' : 'Remedial Plan'}</span>
                  </label>
                )}
                {enrichmentPlan && (
                  <label className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${exportPlanType === 'enrichment' ? 'border-emerald-300 bg-emerald-50/50 dark:border-emerald-700 dark:bg-emerald-950/20' : 'border-border hover:border-emerald-200'}`}>
                    <RadioGroupItem value="enrichment" />
                    <Rocket className="h-4 w-4 text-emerald-500 flex-shrink-0" />
                    <span className="text-sm font-medium">{isRTL ? 'الخطة الإثرائية' : 'Enrichment Plan'}</span>
                  </label>
                )}
                {remedialPlan && enrichmentPlan && (
                  <label className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${exportPlanType === 'both' ? 'border-brand-navy/30 bg-brand-navy/5 dark:border-brand-navy/50 dark:bg-brand-navy/10' : 'border-border hover:border-brand-navy/20'}`}>
                    <RadioGroupItem value="both" />
                    <FileText className="h-4 w-4 text-brand-navy flex-shrink-0" />
                    <span className="text-sm font-medium">{isRTL ? 'الخطتين معاً' : 'Both Plans'}</span>
                  </label>
                )}
              </RadioGroup>
            </div>

            <div className="space-y-2">
              <Label className="text-sm font-medium font-cairo">{isRTL ? 'صيغة الملف' : 'File Format'}</Label>
              <RadioGroup value={exportFormat} onValueChange={setExportFormat} className="grid grid-cols-2 gap-2">
                <label className={`flex flex-col items-center gap-1.5 p-3 rounded-xl border cursor-pointer transition-all ${exportFormat === 'pdf' ? 'border-red-300 bg-red-50/50 dark:border-red-700 dark:bg-red-950/20 ring-1 ring-red-200 dark:ring-red-800' : 'border-border hover:border-red-200'}`}>
                  <RadioGroupItem value="pdf" className="sr-only" />
                  <div className="w-10 h-10 rounded-lg bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
                    <span className="text-red-600 dark:text-red-400 font-bold text-xs">PDF</span>
                  </div>
                  <span className="text-xs font-medium">{isRTL ? 'ملف PDF' : 'PDF File'}</span>
                </label>
                <label className={`flex flex-col items-center gap-1.5 p-3 rounded-xl border cursor-pointer transition-all ${exportFormat === 'docx' ? 'border-blue-300 bg-blue-50/50 dark:border-blue-700 dark:bg-blue-950/20 ring-1 ring-blue-200 dark:ring-blue-800' : 'border-border hover:border-blue-200'}`}>
                  <RadioGroupItem value="docx" className="sr-only" />
                  <div className="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                    <span className="text-blue-600 dark:text-blue-400 font-bold text-xs">DOCX</span>
                  </div>
                  <span className="text-xs font-medium">{isRTL ? 'ملف Word' : 'Word File'}</span>
                </label>
              </RadioGroup>
            </div>

            <div className="bg-muted/30 rounded-lg p-3 text-xs text-muted-foreground space-y-1">
              <p className="font-medium">{isRTL ? 'معاينة اسم الملف:' : 'File name preview:'}</p>
              <p className="font-mono text-[11px] break-all direction-ltr">
                {(student?.full_name || 'Student').replace(/\s+/g, '_')}_{exportPlanType === 'remedial' ? 'Remedial_Plan' : exportPlanType === 'enrichment' ? 'Enrichment_Plan' : 'Plans'}_{new Date().toISOString().split('T')[0]}.{exportFormat === 'pdf' ? 'pdf' : 'docx'}
              </p>
            </div>

            <Button
              className="w-full gap-2 bg-brand-navy hover:bg-brand-navy/90 text-white"
              onClick={() => handleExportPlan(exportPlanType, exportFormat)}
              disabled={exportingPlan}
            >
              {exportingPlan ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              {isRTL ? 'تحميل' : 'Download'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
