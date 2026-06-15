import { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme , useTranslation } from '../../contexts/ThemeContext';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Progress } from '../ui/progress';
import { toast } from 'sonner';
import { useNassaqAlert } from '../ui/NassaqAlertDialog';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle
} from '../ui/dialog';
import { RadioGroup, RadioGroupItem } from '../ui/radio-group';
import { getFormErrorMessage } from '../../utils/apiError';
import {
  User, BookOpen, Shield, TrendingUp, Brain, FileText, Edit, Save, X,
  Phone, Mail, Hash, Calendar, MapPin, AlertTriangle, CheckCircle, Loader2,
  Key, UserX, UserCheck, Trash2, ArrowRightLeft, Star, Activity, Target,
  Sparkles, Clock, ChevronDown, ChevronUp, Stethoscope, Rocket, Zap, Download
} from 'lucide-react';

const HAKIM_POSES = {
  remedial: '/hakim-poses/support.png',
  enrichment: '/hakim-poses/motivating.png',
  thinking: '/hakim-poses/ai-thinking.png',
};

const PLAN_CONFIG = {
  remedial: {
    title_ar: 'الخطة العلاجية',
    title_en: 'Remedial Plan',
    desc_ar: 'خطة لمعالجة نقاط الضعف وتحسين الأداء الأكاديمي',
    desc_en: 'A plan to address weaknesses and improve academic performance',
    btn_ar: 'أنشئ الخطة العلاجية',
    btn_en: 'Generate Remedial Plan',
    icon: Stethoscope,
    gradient: 'from-rose-500 to-orange-500',
    bg: 'bg-gradient-to-br from-rose-50 to-orange-50/50 dark:from-rose-950/20 dark:to-orange-950/10',
    border: 'border-rose-200/70 dark:border-rose-800/30',
    iconBg: 'bg-rose-100 dark:bg-rose-900/40 text-rose-600 dark:text-rose-400',
    stepBg: 'bg-rose-50/80 dark:bg-rose-950/10 border-rose-100 dark:border-rose-800/20',
    btnClass: 'from-rose-500 to-orange-500',
  },
  enrichment: {
    title_ar: 'الخطة الإثرائية',
    title_en: 'Enrichment Plan',
    desc_ar: 'خطة لتعزيز نقاط القوة وتطوير المهارات المتميزة',
    desc_en: 'A plan to strengthen talents and develop advanced skills',
    btn_ar: 'أنشئ الخطة الإثرائية',
    btn_en: 'Generate Enrichment Plan',
    icon: Rocket,
    gradient: 'from-emerald-500 to-teal-500',
    bg: 'bg-gradient-to-br from-emerald-50 to-teal-50/50 dark:from-emerald-950/20 dark:to-teal-950/10',
    border: 'border-emerald-200/70 dark:border-emerald-800/30',
    iconBg: 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-600 dark:text-emerald-400',
    stepBg: 'bg-emerald-50/80 dark:bg-emerald-950/10 border-emerald-100 dark:border-emerald-800/20',
    btnClass: 'from-emerald-500 to-teal-500',
  },
};

const HakimPlanCard = ({ type, plan, isRTL, loading, onGenerate, onExport }) => {
  const { t } = useTranslation();
  const [stepsOpen, setStepsOpen] = useState(true);
  const [imgError, setImgError] = useState(false);
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
            <div className="w-16 h-16 rounded-2xl bg-white/80 dark:bg-gray-800/60 border border-white/50 dark:border-gray-700/50 shadow-sm flex items-center justify-center overflow-hidden flex-shrink-0">
              {imgError ? (
                <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${cfg.gradient} flex items-center justify-center`}>
                  <svg className="h-5 w-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                </div>
              ) : (
                <img
                  src={hakimPose}
                  alt="حكيم"
                  className={`w-14 h-14 object-contain ${loading ? 'animate-pulse' : ''}`}
                  onError={() => setImgError(true)}
                />
              )}
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <div className={`w-7 h-7 rounded-lg ${cfg.iconBg} flex items-center justify-center flex-shrink-0`}>
                  <Icon className="h-4 w-4" />
                </div>
                <h4 className="font-bold text-sm font-cairo">{isRTL ? cfg.title_ar : cfg.title_en}</h4>
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {isRTL ? cfg.desc_ar : cfg.desc_en}
              </p>

              {!hasPlan && !loading && (
                <Button
                  onClick={onGenerate}
                  size="sm"
                  className={`mt-3 bg-gradient-to-r ${cfg.btnClass} hover:opacity-90 text-white gap-1.5 text-xs h-8 shadow-sm`}
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  {isRTL ? cfg.btn_ar : cfg.btn_en}
                </Button>
              )}

              {loading && (
                <div className="flex items-center gap-2 mt-3">
                  <Loader2 className="h-4 w-4 animate-spin text-brand-purple" />
                  <span className="text-xs text-muted-foreground font-tajawal">
                    {t('hakimIsPreparingThePlan')}
                  </span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {hasPlan && (
        <>
          <button
            onClick={() => setStepsOpen(!stepsOpen)}
            className="w-full flex items-center justify-between px-4 py-2.5 border-t border-b border-border/30 bg-muted/20 hover:bg-muted/40 transition-colors"
          >
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 rounded-full bg-brand-purple/10 flex items-center justify-center flex-shrink-0">
                <img src={HAKIM_POSES[type]} alt="" className="hakim-img w-4 h-4 object-contain rounded-full" onError={(e) => { e.target.style.display = 'none'; }} />
              </div>
              <span className="text-xs font-medium font-cairo">{plan.title || (isRTL ? cfg.title_ar : cfg.title_en)}</span>
              {plan.steps && (
                <span className="text-[10px] text-muted-foreground">({plan.steps.length} {t('steps')})</span>
              )}
            </div>
            <div className="flex items-center gap-1">
              {onExport && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => { e.stopPropagation(); onExport(type); }}
                  className="h-6 px-2 text-[10px] gap-1 text-brand-turquoise hover:text-brand-turquoise"
                >
                  <Download className="h-3 w-3" />
                  {t('export')}
                </Button>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => { e.stopPropagation(); onGenerate(); }}
                className="h-6 px-2 text-[10px] gap-1 text-brand-purple hover:text-brand-purple"
              >
                <Sparkles className="h-3 w-3" />
                {t('redo')}
              </Button>
              {stepsOpen ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
            </div>
          </button>

          {stepsOpen && (
            <CardContent className="p-4 space-y-2.5">
              {plan.summary && (
                <p className="text-xs text-muted-foreground bg-muted/30 p-2.5 rounded-lg leading-relaxed font-tajawal">{plan.summary}</p>
              )}

              {plan.steps && plan.steps.map((step, i) => (
                <div key={i} className={`p-3 rounded-xl border ${cfg.stepBg}`}>
                  <div className="flex items-start gap-3">
                    <div className={`w-6 h-6 rounded-full ${cfg.iconBg} flex items-center justify-center flex-shrink-0 text-xs font-bold mt-0.5`}>
                      {i + 1}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-sm font-cairo">{step.title}</p>
                      <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{step.description}</p>
                      <div className="flex flex-wrap items-center gap-3 mt-2">
                        {step.duration && (
                          <span className="flex items-center gap-1 text-[11px] text-muted-foreground">
                            <Clock className="h-3 w-3" /> {step.duration}
                          </span>
                        )}
                        {step.responsible && (
                          <span className="flex items-center gap-1 text-[11px] text-muted-foreground">
                            <User className="h-3 w-3" /> {step.responsible}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ))}

              {plan.expected_outcome && (
                <div className="flex items-start gap-2 p-3 bg-blue-50/50 dark:bg-blue-950/10 rounded-xl border border-blue-100 dark:border-blue-800/20">
                  <Target className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-xs font-medium text-blue-700 dark:text-blue-300 font-cairo">
                      {t('expectedOutcome')}
                    </p>
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

export default function StudentProfileDialog({ open, onClose, student, classes = [], onRefresh }) {
  const { t } = useTranslation();
  const { api } = useAuth();
  const { isRTL } = useTheme();
  const { nassaqConfirm, nassaqError, nassaqWarning } = useNassaqAlert();
  const [activeTab, setActiveTab] = useState('info');
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState({});
  const [riskData, setRiskData] = useState(null);
  const [loadingRisk, setLoadingRisk] = useState(false);
  const [actionLoading, setActionLoading] = useState('');
  const [remedialPlan, setRemedialPlan] = useState(null);
  const [enrichmentPlan, setEnrichmentPlan] = useState(null);
  const [loadingRemedial, setLoadingRemedial] = useState(false);
  const [loadingEnrichment, setLoadingEnrichment] = useState(false);
  const [exportingPlan, setExportingPlan] = useState(false);
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const [exportPlanType, setExportPlanType] = useState('both');
  const [exportFormat, setExportFormat] = useState('pdf');

  useEffect(() => {
    if (student && open) {
      setFormData({ ...student });
      setEditing(false);
      setActiveTab('info');
      setRemedialPlan(null);
      setEnrichmentPlan(null);
      fetchRiskData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [student, open]);

  const fetchRiskData = async () => {
    if (!student?.id) return;
    setLoadingRisk(true);
    try {
      const res = await api.get(`/hakim/student/${student.id}/risk?days=30`);
      setRiskData(res.data?.data || res.data);
    } catch (e) {
      console.error('Error fetching risk data:', e);
      setRiskData(null);
    } finally {
      setLoadingRisk(false);
    }
  };

  const generatePlan = async (planType) => {
    if (!student?.id) return;
    const setLoading = planType === 'remedial' ? setLoadingRemedial : setLoadingEnrichment;
    const setPlan = planType === 'remedial' ? setRemedialPlan : setEnrichmentPlan;
    setLoading(true);
    try {
      const res = await api.post(`/hakim/student/${student.id}/ai-plans`);
      const plans = res.data?.plans;
      if (plans) {
        if (planType === 'remedial') {
          setPlan(plans.remedial_plan);
          if (!enrichmentPlan && plans.enrichment_plan) setEnrichmentPlan(plans.enrichment_plan);
        } else {
          setPlan(plans.enrichment_plan);
          if (!remedialPlan && plans.remedial_plan) setRemedialPlan(plans.remedial_plan);
        }
      }
      const label = planType === 'remedial'
        ? (t('remedialPlan'))
        : (t('enrichmentPlan'));
      toast.success(isRTL ? `تم توليد ${label} بواسطة حكيم` : `${label} generated by Hakim`);
    } catch (e) {
      console.error('Error generating plan:', e);
      nassaqError(t('failedToGeneratePlanPleaseTryAgain'));
    } finally {
      setLoading(false);
    }
  };

  const openExportModal = (planType) => {
    setExportPlanType(planType || 'both');
    setExportFormat('pdf');
    setExportModalOpen(true);
  };

  const handleExportPlan = async (planType, format = 'docx') => {
    if (!student?.id) return;
    const payload = { plan_type: planType };
    if (planType === 'remedial' || planType === 'both') payload.remedial_plan = remedialPlan;
    if (planType === 'enrichment' || planType === 'both') payload.enrichment_plan = enrichmentPlan;

    setExportingPlan(true);
    try {
      const isPdf = format === 'pdf';
      const endpoint = isPdf
        ? `/export/student-plans/${student.id}/pdf`
        : `/export/student-plans/${student.id}`;
      const mimeType = isPdf
        ? 'application/pdf'
        : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
      const ext = isPdf ? 'pdf' : 'docx';

      const res = await api.post(endpoint, payload, { responseType: 'blob' });

      if (res.data.type === 'application/json') {
        const text = await res.data.text();
        const errData = JSON.parse(text);
        throw new Error(errData.detail || 'Export failed');
      }

      const blob = new Blob([res.data], { type: mimeType });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      const safeName = (student.full_name || 'student').replace(/\s+/g, '_');
      const date = new Date().toISOString().split('T')[0];
      const suffix = planType === 'remedial' ? 'Remedial_Plan' : planType === 'enrichment' ? 'Enrichment_Plan' : 'Plans';
      a.href = url;
      a.download = `${safeName}_${suffix}_${date}.${ext}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
      toast.success(t('planExportedSuccessfully'));
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
      } else if (getFormErrorMessage(err, { t })) {
        detail = getFormErrorMessage(err, { t });
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
      if (formData.full_name) updateData.full_name = formData.full_name;
      if (formData.email && formData.email.includes('@')) updateData.email = formData.email;
      if (formData.phone) updateData.phone = formData.phone;
      if (formData.class_id) updateData.class_id = formData.class_id;
      if (formData.gender) updateData.gender = formData.gender;
      if (typeof formData.is_active === 'boolean') updateData.is_active = formData.is_active;
      if (formData.parent_name !== undefined && formData.parent_name !== student.parent_name) updateData.parent_name = formData.parent_name;
      if (formData.parent_phone !== undefined && formData.parent_phone !== student.parent_phone) updateData.parent_phone = formData.parent_phone;
      if (formData.parent_email !== undefined && formData.parent_email !== student.parent_email) updateData.parent_email = formData.parent_email;
      if (formData.parent_relationship !== undefined && formData.parent_relationship !== student.parent_relationship) updateData.parent_relationship = formData.parent_relationship;

      if (Object.keys(updateData).length === 0) {
        nassaqWarning(t('noChangesToSave'));
        setSaving(false);
        return;
      }

      await api.put(`/students/${student.id}`, updateData);
      toast.success(t('studentDataSavedToDatabaseSuccessfully'));
      setEditing(false);
      onRefresh?.();
    } catch (error) {
      const msg = getFormErrorMessage(error, { t });
      nassaqError(typeof msg === 'string' ? msg : (t('saveFailed')));
    } finally {
      setSaving(false);
    }
  };

  const handleAction = async (action) => {
    setActionLoading(action);
    try {
      switch (action) {
        case 'suspend':
          await api.put(`/principal/student/${student.id}/status`, { status: 'suspended' });
          toast.success(t('accountSuspended'));
          break;
        case 'activate':
          await api.put(`/principal/student/${student.id}/status`, { status: 'active' });
          toast.success(t('accountActivated'));
          break;
        case 'reset-password': {
          const genRes = await api.post('/principal/generate-password');
          const tempPass = genRes.data.password;
          await api.put(`/principal/student/${student.id}/credentials`, { new_password: tempPass });
          toast.success(isRTL ? `تم إعادة تعيين كلمة المرور إلى: ${tempPass}` : `Password reset to: ${tempPass}`);
          break;
        }
        case 'delete':
          nassaqConfirm(
            t('areYouSureYouWantToDeleteThisAccountThisActionCann'),
            async () => {
              try {
                await api.delete(`/students/${student.id}`);
                toast.success(t('accountDeleted'));
                onClose?.();
                onRefresh?.();
              } catch (err) {
                nassaqError(t('failedToDeleteAccount'));
              }
            },
            { title: t('confirmDelete'), confirmText: t('yesDelete'), cancelText: t('cancel') }
          );
          setActionLoading('');
          return;
        default:
          break;
      }
      onRefresh?.();
    } catch (error) {
      const msg = getFormErrorMessage(error, { t });
      nassaqError(typeof msg === 'string' ? msg : (isRTL ? 'فشلت العملية' : 'Operation failed'));
    } finally {
      setActionLoading('');
    }
  };

  const getRiskColor = (category) => {
    switch (category) {
      case 'critical': return 'bg-red-100 text-red-700 border-red-200';
      case 'high': return 'bg-orange-100 text-orange-700 border-orange-200';
      case 'medium': return 'bg-yellow-100 text-yellow-700 border-yellow-200';
      case 'low': return 'bg-green-100 text-green-700 border-green-200';
      default: return 'bg-gray-100 text-gray-700 border-gray-200';
    }
  };

  const getRiskLabel = (category) => {
    const labels = {
      critical: t('critical'),
      high: t('high'),
      medium: t('medium'),
      low: t('low'),
    };
    return labels[category] || category;
  };

  const getRiskBarColor = (category) => {
    switch (category) {
      case 'critical': return '[&>div]:bg-red-500';
      case 'high': return '[&>div]:bg-orange-500';
      case 'medium': return '[&>div]:bg-yellow-500';
      case 'low': return '[&>div]:bg-green-500';
      default: return '[&>div]:bg-gray-400';
    }
  };

  if (!student) return null;

  return (
    <>
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[800px] max-h-[90vh] overflow-y-auto p-0">
        <div className="bg-gradient-to-r from-brand-turquoise/10 to-brand-purple/10 p-6 border-b">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-full bg-gradient-to-br from-brand-turquoise to-brand-purple flex items-center justify-center shadow-lg">
                <span className="text-white font-bold text-2xl">{student.full_name?.charAt(0)}</span>
              </div>
              <div>
                <h2 className="text-xl font-bold">{student.full_name}</h2>
                <p className="text-sm text-muted-foreground">{student.student_number || student.id?.slice(0, 8)}</p>
                <div className="flex items-center gap-2 mt-1">
                  <Badge variant={student.is_active !== false ? 'default' : 'destructive'} className="text-xs">
                    {student.is_active !== false ? (t('active')) : (isRTL ? 'معلق' : 'Suspended')}
                  </Badge>
                  {student.grade && (
                    <Badge variant="outline" className="text-xs">
                      {student.grade} - {student.section || ''}
                    </Badge>
                  )}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-1">
              {!editing ? (
                <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
                  <Edit className="h-3.5 w-3.5 me-1" />
                  {t('edit')}
                </Button>
              ) : (
                <>
                  <Button size="sm" onClick={handleSave} disabled={saving}>
                    {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin me-1" /> : <Save className="h-3.5 w-3.5 me-1" />}
                    {t('save')}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => { setEditing(false); setFormData({ ...student }); }}>
                    <X className="h-3.5 w-3.5" />
                  </Button>
                </>
              )}
            </div>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="px-6 pt-4 pb-6">
          <TabsList className="grid grid-cols-4 mb-4">
            <TabsTrigger value="info" className="text-xs">
              <User className="h-3.5 w-3.5 me-1" />
              {t('info')}
            </TabsTrigger>
            <TabsTrigger value="academic" className="text-xs">
              <Brain className="h-3.5 w-3.5 me-1" />
              {t('aiAnalysis')}
            </TabsTrigger>
            <TabsTrigger value="behavior" className="text-xs">
              <Shield className="h-3.5 w-3.5 me-1" />
              {t('behavior')}
            </TabsTrigger>
            <TabsTrigger value="actions" className="text-xs">
              <FileText className="h-3.5 w-3.5 me-1" />
              {t('actions')}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="info" className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-xs text-muted-foreground">{t('fullName')}</Label>
                {editing ? (
                  <Input value={formData.full_name || ''} onChange={(e) => setFormData({ ...formData, full_name: e.target.value })} />
                ) : (
                  <p className="font-medium">{student.full_name}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label className="text-xs text-muted-foreground">{t('studentNumber')}</Label>
                <p className="font-medium flex items-center gap-1"><Hash className="h-3.5 w-3.5" /> {student.student_number || '-'}</p>
              </div>
              <div className="space-y-2">
                <Label className="text-xs text-muted-foreground">{t('email2')}</Label>
                {editing ? (
                  <Input value={formData.email || ''} onChange={(e) => setFormData({ ...formData, email: e.target.value })} />
                ) : (
                  <p className="font-medium flex items-center gap-1"><Mail className="h-3.5 w-3.5" /> {student.email || '-'}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label className="text-xs text-muted-foreground">{t('phone2')}</Label>
                {editing ? (
                  <Input value={formData.phone || ''} onChange={(e) => setFormData({ ...formData, phone: e.target.value })} />
                ) : (
                  <p className="font-medium flex items-center gap-1"><Phone className="h-3.5 w-3.5" /> {student.phone || '-'}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label className="text-xs text-muted-foreground">{t('grade')}</Label>
                <p className="font-medium flex items-center gap-1"><BookOpen className="h-3.5 w-3.5" /> {student.grade || '-'}</p>
              </div>
              <div className="space-y-2">
                <Label className="text-xs text-muted-foreground">{t('class')}</Label>
                {editing ? (
                  <Select value={formData.class_id || ''} onValueChange={(v) => setFormData({ ...formData, class_id: v })}>
                    <SelectTrigger><SelectValue placeholder={t('selectClass')} /></SelectTrigger>
                    <SelectContent>
                      {classes.map(c => (
                        <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <p className="font-medium">{student.class_name || student.section || '-'}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label className="text-xs text-muted-foreground">{t('gender')}</Label>
                {editing ? (
                  <Select value={formData.gender || ''} onValueChange={(v) => setFormData({ ...formData, gender: v })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="male">{t('male')}</SelectItem>
                      <SelectItem value="female">{t('female')}</SelectItem>
                    </SelectContent>
                  </Select>
                ) : (
                  <p className="font-medium">{student.gender === 'male' ? (t('male')) : student.gender === 'female' ? (t('female')) : '-'}</p>
                )}
              </div>
              <div className="space-y-2">
                <Label className="text-xs text-muted-foreground">{t('nationalId')}</Label>
                <p className="font-medium">{student.national_id || '-'}</p>
              </div>
            </div>

            <Card className="bg-muted/30">
              <CardContent className="p-4">
                <h4 className="font-medium text-sm mb-3 flex items-center gap-2">
                  <User className="h-4 w-4 text-brand-turquoise" />
                  {t('guardianInfo')}
                </h4>
                {editing ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <Label className="text-xs text-muted-foreground">{t('guardianName')}</Label>
                      <Input value={formData.parent_name || ''} onChange={(e) => setFormData({ ...formData, parent_name: e.target.value })} />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs text-muted-foreground">{t('relationship')}</Label>
                      <Select value={formData.parent_relationship || ''} onValueChange={(v) => setFormData({ ...formData, parent_relationship: v })}>
                        <SelectTrigger><SelectValue placeholder={t('select')} /></SelectTrigger>
                        <SelectContent>
                          {Object.entries({ father: t('father'), mother: t('mother'), guardian: isRTL ? 'ولي أمر' : 'Guardian', brother: t('brother'), sister: t('sister'), uncle: t('uncle'), other: t('other') }).map(([k, v]) => (
                            <SelectItem key={k} value={k}>{v}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs text-muted-foreground">{t('guardianPhone')}</Label>
                      <Input value={formData.parent_phone || ''} onChange={(e) => setFormData({ ...formData, parent_phone: e.target.value })} />
                    </div>
                    <div className="space-y-1.5">
                      <Label className="text-xs text-muted-foreground">{t('guardianEmail')}</Label>
                      <Input type="email" value={formData.parent_email || ''} onChange={(e) => setFormData({ ...formData, parent_email: e.target.value })} />
                    </div>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div><span className="text-muted-foreground">{t('name')}:</span> {student.parent_name || '-'}</div>
                    <div><span className="text-muted-foreground">{t('relationship')}:</span> {student.parent_relationship || '-'}</div>
                    <div><span className="text-muted-foreground">{t('phone2')}:</span> {student.parent_phone || '-'}</div>
                    <div><span className="text-muted-foreground">{t('email2')}:</span> {student.parent_email || '-'}</div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="academic" className="space-y-4">
            {loadingRisk ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-brand-turquoise" />
              </div>
            ) : riskData ? (
              <>
                <Card className="border overflow-hidden">
                  <div className="bg-gradient-to-br from-brand-navy/5 to-brand-purple/5 dark:from-brand-navy/20 dark:to-brand-purple/10 p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <Activity className="h-5 w-5 text-brand-purple" />
                        <h4 className="font-bold text-sm font-cairo">{t('overallPerformance')}</h4>
                      </div>
                      <Badge className={`${getRiskColor(riskData.risk_category)}`}>
                        {getRiskLabel(riskData.risk_category)}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="flex-1">
                        <Progress
                          value={riskData.risk_score || 0}
                          className={`h-3 rounded-full bg-gray-100 dark:bg-gray-800 ${getRiskBarColor(riskData.risk_category)}`}
                        />
                      </div>
                      <span className="text-lg font-bold font-cairo tabular-nums text-brand-navy dark:text-white">
                        {Math.round(riskData.risk_score || 0)}%
                      </span>
                    </div>
                  </div>
                  <CardContent className="p-4">
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      {riskData.breakdown && Object.entries(riskData.breakdown).map(([key, val]) => {
                        const labels = {
                          attendance: { ar: 'الحضور', icon: <Calendar className="h-4 w-4" /> },
                          participation: { ar: 'المشاركة', icon: <Zap className="h-4 w-4" /> },
                          behaviour: { ar: 'السلوك', icon: <Shield className="h-4 w-4" /> },
                          academic: { ar: 'الأكاديمي', icon: <BookOpen className="h-4 w-4" /> },
                        };
                        const label = labels[key] || { ar: key, icon: <Activity className="h-4 w-4" /> };
                        const score = Math.round(typeof val === 'number' ? val : val?.score || 0);
                        const scoreColor = score >= 80 ? 'text-green-600' : score >= 60 ? 'text-amber-600' : 'text-red-600';

                        return (
                          <div key={key} className="text-center p-3 bg-muted/30 rounded-xl">
                            <div className="flex justify-center text-muted-foreground mb-1.5">{label.icon}</div>
                            <p className={`text-xl font-bold font-cairo ${scoreColor}`}>{score}%</p>
                            <p className="text-[11px] text-muted-foreground font-tajawal mt-0.5">{isRTL ? label.ar : key}</p>
                          </div>
                        );
                      })}
                    </div>
                  </CardContent>
                </Card>

                {riskData.factors && riskData.factors.length > 0 && (
                  <Card>
                    <CardContent className="p-4">
                      <h4 className="font-medium text-sm mb-3 flex items-center gap-2">
                        <Target className="h-4 w-4 text-brand-turquoise" />
                        {t('keyObservations')}
                      </h4>
                      <div className="space-y-2">
                        {riskData.factors.map((factor, i) => (
                          <div key={i} className="flex items-start gap-2 text-sm p-2.5 bg-amber-50/60 dark:bg-amber-950/10 rounded-lg border border-amber-100 dark:border-amber-800/20">
                            <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
                            <span className="text-sm">{factor.message || factor.message_ar || factor}</span>
                          </div>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                )}

                <div className="relative">
                  <div className="absolute inset-0 flex items-center" aria-hidden="true">
                    <div className="w-full border-t border-dashed border-brand-purple/20" />
                  </div>
                  <div className="relative flex justify-center">
                    <span className="bg-background px-3 text-xs text-brand-purple font-cairo font-medium">
                      {t('hakimAiPlans')}
                    </span>
                  </div>
                </div>

                <HakimPlanCard
                  type="remedial"
                  plan={remedialPlan}
                  isRTL={isRTL}
                  loading={loadingRemedial}
                  onGenerate={() => generatePlan('remedial')}
                  onExport={remedialPlan ? openExportModal : null}
                />

                <HakimPlanCard
                  type="enrichment"
                  plan={enrichmentPlan}
                  isRTL={isRTL}
                  loading={loadingEnrichment}
                  onGenerate={() => generatePlan('enrichment')}
                  onExport={enrichmentPlan ? openExportModal : null}
                />

                {remedialPlan && enrichmentPlan && (
                  <Button
                    variant="outline"
                    className="w-full gap-2 border-brand-navy/20 text-brand-navy hover:bg-brand-navy/5 hover:text-brand-navy focus-visible:text-brand-navy"
                    onClick={() => openExportModal('both')}
                    disabled={exportingPlan}
                  >
                    {exportingPlan ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                    {t('exportBothPlans')}
                  </Button>
                )}
              </>
            ) : (
              <Card className="p-8 text-center">
                <Brain className="h-12 w-12 mx-auto text-muted-foreground/30 mb-3" />
                <p className="text-muted-foreground text-sm">
                  {t('noAnalyticsAvailableYetTheSystemNeedsAttendanceAnd')}
                </p>
                <Button variant="outline" size="sm" className="mt-3" onClick={fetchRiskData}>
                  <Activity className="h-3.5 w-3.5 me-1" />
                  {t('refreshAnalysis')}
                </Button>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="behavior" className="space-y-4">
            <Card className="p-8 text-center">
              <Shield className="h-12 w-12 mx-auto text-muted-foreground/30 mb-3" />
              <p className="text-muted-foreground text-sm mb-2">
                {t('behaviorDisciplineRecord')}
              </p>
              <p className="text-xs text-muted-foreground">
                {t('thisSectionIsAutoupdatedFromSessionAndEvaluationRe')}
              </p>
            </Card>
          </TabsContent>

          <TabsContent value="actions" className="space-y-3">
            <h4 className="font-medium text-sm text-muted-foreground mb-2">{t('accountActions')}</h4>

            <div className="grid grid-cols-2 gap-3">
              <Button
                variant="outline"
                className="justify-start h-auto py-3"
                onClick={() => handleAction('reset-password')}
                disabled={!!actionLoading}
              >
                <Key className="h-4 w-4 me-2 text-blue-500" />
                <div className="text-start">
                  <p className="text-sm font-medium">{t('resetPassword')}</p>
                  <p className="text-xs text-muted-foreground">{t('sendNewPassword')}</p>
                </div>
                {actionLoading === 'reset-password' && <Loader2 className="h-4 w-4 animate-spin ms-auto" />}
              </Button>

              {student.is_active !== false ? (
                <Button
                  variant="outline"
                  className="justify-start h-auto py-3 border-amber-200 hover:bg-amber-50"
                  onClick={() => handleAction('suspend')}
                  disabled={!!actionLoading}
                >
                  <UserX className="h-4 w-4 me-2 text-amber-500" />
                  <div className="text-start">
                    <p className="text-sm font-medium">{t('suspendAccount')}</p>
                    <p className="text-xs text-muted-foreground">{t('temporarilySuspend')}</p>
                  </div>
                  {actionLoading === 'suspend' && <Loader2 className="h-4 w-4 animate-spin ms-auto" />}
                </Button>
              ) : (
                <Button
                  variant="outline"
                  className="justify-start h-auto py-3 border-green-200 hover:bg-green-50"
                  onClick={() => handleAction('activate')}
                  disabled={!!actionLoading}
                >
                  <UserCheck className="h-4 w-4 me-2 text-green-500" />
                  <div className="text-start">
                    <p className="text-sm font-medium">{t('activateAccount')}</p>
                    <p className="text-xs text-muted-foreground">{t('reactivateAccount')}</p>
                  </div>
                  {actionLoading === 'activate' && <Loader2 className="h-4 w-4 animate-spin ms-auto" />}
                </Button>
              )}

              <Button
                variant="outline"
                className="justify-start h-auto py-3 border-red-200 hover:bg-red-50 col-span-2"
                onClick={() => handleAction('delete')}
                disabled={!!actionLoading}
              >
                <Trash2 className="h-4 w-4 me-2 text-red-500" />
                <div className="text-start">
                  <p className="text-sm font-medium text-red-600">{t('deleteAccountPermanently')}</p>
                  <p className="text-xs text-muted-foreground">{t('thisActionCannotBeUndone')}</p>
                </div>
                {actionLoading === 'delete' && <Loader2 className="h-4 w-4 animate-spin ms-auto" />}
              </Button>
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>

    <Dialog open={exportModalOpen} onOpenChange={setExportModalOpen}>
      <DialogContent className="sm:max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
        <DialogHeader>
          <DialogTitle className="font-cairo flex items-center gap-2">
            <Download className="h-5 w-5 text-brand-navy" />
            {t('exportPlan')}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-5 pt-2">
          <div className="space-y-2">
            <Label className="text-sm font-medium font-cairo">{t('planType')}</Label>
            <RadioGroup value={exportPlanType} onValueChange={setExportPlanType} className="space-y-2">
              {remedialPlan && (
                <label className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${exportPlanType === 'remedial' ? 'border-rose-300 bg-rose-50/50 dark:border-rose-700 dark:bg-rose-950/20' : 'border-border hover:border-rose-200'}`}>
                  <RadioGroupItem value="remedial" />
                  <Stethoscope className="h-4 w-4 text-rose-500 flex-shrink-0" />
                  <span className="text-sm font-medium">{t('remedialPlan')}</span>
                </label>
              )}
              {enrichmentPlan && (
                <label className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${exportPlanType === 'enrichment' ? 'border-emerald-300 bg-emerald-50/50 dark:border-emerald-700 dark:bg-emerald-950/20' : 'border-border hover:border-emerald-200'}`}>
                  <RadioGroupItem value="enrichment" />
                  <Rocket className="h-4 w-4 text-emerald-500 flex-shrink-0" />
                  <span className="text-sm font-medium">{t('enrichmentPlan')}</span>
                </label>
              )}
              {remedialPlan && enrichmentPlan && (
                <label className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${exportPlanType === 'both' ? 'border-brand-navy/30 bg-brand-navy/5 dark:border-brand-navy/50 dark:bg-brand-navy/10' : 'border-border hover:border-brand-navy/20'}`}>
                  <RadioGroupItem value="both" />
                  <FileText className="h-4 w-4 text-brand-navy flex-shrink-0" />
                  <span className="text-sm font-medium">{t('bothPlans')}</span>
                </label>
              )}
            </RadioGroup>
          </div>
          <div className="space-y-2">
            <Label className="text-sm font-medium font-cairo">{t('fileFormat')}</Label>
            <RadioGroup value={exportFormat} onValueChange={setExportFormat} className="grid grid-cols-2 gap-2">
              <label className={`flex flex-col items-center gap-1.5 p-3 rounded-xl border cursor-pointer transition-all ${exportFormat === 'pdf' ? 'border-red-300 bg-red-50/50 dark:border-red-700 dark:bg-red-950/20 ring-1 ring-red-200 dark:ring-red-800' : 'border-border hover:border-red-200'}`}>
                <RadioGroupItem value="pdf" className="sr-only" />
                <div className="w-10 h-10 rounded-lg bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
                  <span className="text-red-600 dark:text-red-400 font-bold text-xs">PDF</span>
                </div>
                <span className="text-xs font-medium">{t('pdfFile')}</span>
              </label>
              <label className={`flex flex-col items-center gap-1.5 p-3 rounded-xl border cursor-pointer transition-all ${exportFormat === 'docx' ? 'border-blue-300 bg-blue-50/50 dark:border-blue-700 dark:bg-blue-950/20 ring-1 ring-blue-200 dark:ring-blue-800' : 'border-border hover:border-blue-200'}`}>
                <RadioGroupItem value="docx" className="sr-only" />
                <div className="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                  <span className="text-blue-600 dark:text-blue-400 font-bold text-xs">DOCX</span>
                </div>
                <span className="text-xs font-medium">{t('wordFile')}</span>
              </label>
            </RadioGroup>
          </div>
          <Button
            className="w-full gap-2 bg-brand-navy hover:bg-brand-navy/90 text-white"
            onClick={() => handleExportPlan(exportPlanType, exportFormat)}
            disabled={exportingPlan}
          >
            {exportingPlan ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            {t('download')}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
    </>
  );
}
