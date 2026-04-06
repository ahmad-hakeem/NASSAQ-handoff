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
import { Skeleton } from '../components/ui/skeleton';
import { Textarea } from '../components/ui/textarea';
import { ScrollArea, ScrollBar } from '../components/ui/scroll-area';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger
} from '../components/ui/dropdown-menu';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip as RechartsTooltip, Cell, RadarChart, PolarGrid,
  PolarAngleAxis, PolarRadiusAxis, Radar, LineChart, Line, Legend
} from 'recharts';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import { NotificationBell } from '../components/notifications/NotificationBell';
import {
  User, BookOpen, Shield, Brain, FileText, Edit, Save, X,
  Phone, Mail, Hash, Calendar, ArrowLeft, ArrowRight, ChevronRight,
  Star, Loader2, Activity, Target, Sparkles, Clock, Key, UserX,
  UserCheck, Trash2, Download, Sun, Moon, Globe, GraduationCap,
  Stethoscope, Rocket, ChevronDown, ChevronUp, CheckCircle,
  AlertTriangle, Zap, Heart, Plus, XCircle,
  ThumbsUp, ThumbsDown, MessageSquare, Trophy,
  MoreVertical, Eye, BarChart3, ScrollText, Send,
  Medal, ClipboardList, TrendingUp, Briefcase, Award, Crown, Layers, CheckSquare
} from 'lucide-react';

import {
  TALENT_OPTIONS, HAKIM_POSES, PLAN_CONFIG, getTalentConfig,
  HakimPlanCard, StatCard, EmptyState, DataField
} from '../components/student-profile/ProfileComponents';

export default function StudentProfilePage() {
  const { studentId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, api } = useAuth();
  const { isRTL, isDark, toggleTheme, toggleLanguage } = useTheme();
  const { nassaqConfirm, nassaqError, nassaqWarning } = useNassaqAlert();

  const classId = location.state?.classId;
  const classNameFromState = location.state?.className;
  const fromPath = location.state?.fromPath;

  const [student, setStudent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState({});
  const [activeTab, setActiveTab] = useState('overview');
  const [classes, setClasses] = useState([]);
  const [editProfileOpen, setEditProfileOpen] = useState(false);

  const [attendanceSummary, setAttendanceSummary] = useState(null);
  const [loadingAttendance, setLoadingAttendance] = useState(false);
  const [homeworkRate, setHomeworkRate] = useState(null);
  const [loadingHomework, setLoadingHomework] = useState(false);

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

  const [behaviourRecords, setBehaviourRecords] = useState([]);
  const [behaviourSummary, setBehaviourSummary] = useState(null);
  const [loadingBehaviour, setLoadingBehaviour] = useState(false);
  const [behaviourTypes, setBehaviourTypes] = useState([]);
  const [behaviourModalOpen, setBehaviourModalOpen] = useState(false);
  const [editingBehaviour, setEditingBehaviour] = useState(null);
  const [behaviourForm, setBehaviourForm] = useState({ category: 'positive', title: '', description: '', incident_date: new Date().toISOString().split('T')[0], behaviour_type_id: '' });
  const [savingBehaviour, setSavingBehaviour] = useState(false);

  const [globalTalents, setGlobalTalents] = useState([]);
  const [loadingGlobalTalents, setLoadingGlobalTalents] = useState(false);
  const [customTalentName, setCustomTalentName] = useState('');
  const [addingCustomTalent, setAddingCustomTalent] = useState(false);
  const [savingTalent, setSavingTalent] = useState(false);

  const [overviewLoaded, setOverviewLoaded] = useState(false);
  const [behaviourPage, setBehaviourPage] = useState(1);
  const [savingCharacterTrait, setSavingCharacterTrait] = useState(false);
  const [newCharacterTrait, setNewCharacterTrait] = useState('');

  const [activities, setActivities] = useState([]);
  const [certificates, setCertificates] = useState([]);
  const [loadingActivities, setLoadingActivities] = useState(false);
  const [activityModalOpen, setActivityModalOpen] = useState(false);
  const [editingActivity, setEditingActivity] = useState(null);
  const [activityForm, setActivityForm] = useState({ name: '', name_en: '', activity_type: 'academic', date: '', role: '', description: '' });
  const [savingActivity, setSavingActivity] = useState(false);
  const [certificateModalOpen, setCertificateModalOpen] = useState(false);
  const [editingCertificate, setEditingCertificate] = useState(null);
  const [certificateForm, setCertificateForm] = useState({ title: '', title_en: '', date: '', issuing_body: '', description: '' });
  const [savingCertificate, setSavingCertificate] = useState(false);
  const [planHistory, setPlanHistory] = useState([]);
  const [loadingPlanHistory, setLoadingPlanHistory] = useState(false);

  const [longitudinalData, setLongitudinalData] = useState(null);
  const [loadingLongitudinal, setLoadingLongitudinal] = useState(false);

  const [profileExportModalOpen, setProfileExportModalOpen] = useState(false);
  const [profileExportSections, setProfileExportSections] = useState(['personal', 'academic', 'talents', 'behaviour', 'activities', 'plans', 'longitudinal']);
  const [profileExportFormat, setProfileExportFormat] = useState('pdf');
  const [exportingProfile, setExportingProfile] = useState(false);

  const [attendanceHistory, setAttendanceHistory] = useState([]);
  const [loadingAttendanceHistory, setLoadingAttendanceHistory] = useState(false);
  const [gradesDetail, setGradesDetail] = useState(null);
  const [loadingGrades, setLoadingGrades] = useState(false);
  const [classDetail, setClassDetail] = useState(null);

  const headers = useMemo(() => {
    const h = {};
    const token = localStorage.getItem('nassaq_token');
    if (token) h.Authorization = `Bearer ${token}`;
    const tenantId = user?.tenant_id || localStorage.getItem('nassaq_tenant_id');
    if (tenantId) h['X-Tenant-ID'] = tenantId;
    return h;
  }, [user?.tenant_id]);

  const rolePrefix = user?.role === 'school_principal' ? '/principal' : '/admin';
  const tenantId = useMemo(() => user?.tenant_id || localStorage.getItem('nassaq_tenant_id'), [user?.tenant_id]);
  const isTeacher = user?.role === 'teacher';

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

  useEffect(() => { setOverviewLoaded(false); }, [studentId]);

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

  const fetchHomeworkRate = useCallback(async () => {
    if (!studentId) return;
    setLoadingHomework(true);
    try {
      const res = await api.get(`/grades/student/${studentId}`, { headers });
      const data = res.data;
      const grades = data?.grades || [];
      const stats = data?.statistics;
      if (grades.length > 0) {
        const graded = grades.filter(g => g.score !== null && g.score !== undefined).length;
        const avgScore = stats?.overall_average ? Math.round(stats.overall_average) : (graded > 0 ? Math.round(grades.reduce((sum, g) => sum + (g.percentage || g.score || 0), 0) / graded) : 0);
        setHomeworkRate({ completed: graded, total: grades.length, rate: avgScore });
      } else {
        setHomeworkRate(null);
      }
    } catch {
      setHomeworkRate(null);
    } finally {
      setLoadingHomework(false);
    }
  }, [api, studentId, headers]);

  const fetchBehaviourRecords = useCallback(async () => {
    if (!studentId || !tenantId) return;
    setLoadingBehaviour(true);
    try {
      const res = await api.get(`/behaviour-records/student/${studentId}?school_id=${tenantId}&limit=100`, { headers });
      setBehaviourRecords(res.data?.records || []);
      setBehaviourSummary(res.data?.summary || null);
    } catch {
      setBehaviourRecords([]);
      setBehaviourSummary(null);
    } finally {
      setLoadingBehaviour(false);
    }
  }, [api, studentId, tenantId, headers]);

  const fetchBehaviourTypes = useCallback(async () => {
    if (!tenantId) return;
    try {
      const res = await api.get(`/behaviour-types?school_id=${tenantId}`, { headers });
      setBehaviourTypes(res.data?.behaviour_types || []);
    } catch {
      setBehaviourTypes([]);
    }
  }, [api, tenantId, headers]);

  const fetchGlobalTalents = useCallback(async () => {
    setLoadingGlobalTalents(true);
    try {
      const res = await api.get('/talents', { headers });
      setGlobalTalents(res.data?.talents || []);
    } catch {
      setGlobalTalents([]);
    } finally {
      setLoadingGlobalTalents(false);
    }
  }, [api, headers]);

  const fetchAttendanceHistory = useCallback(async () => {
    if (!studentId) return;
    setLoadingAttendanceHistory(true);
    try {
      const res = await api.get(`/attendance/student/${studentId}`, { headers });
      setAttendanceHistory(res.data?.records || []);
    } catch {
      setAttendanceHistory([]);
    } finally {
      setLoadingAttendanceHistory(false);
    }
  }, [api, studentId, headers]);

  const fetchGradesDetail = useCallback(async () => {
    if (!studentId) return;
    setLoadingGrades(true);
    try {
      const res = await api.get(`/grades/student/${studentId}`, { headers });
      setGradesDetail(res.data);
    } catch {
      setGradesDetail(null);
    } finally {
      setLoadingGrades(false);
    }
  }, [api, studentId, headers]);

  const fetchClassDetail = useCallback(async () => {
    const cId = classId || student?.class_id;
    if (!cId) return;
    try {
      const res = await api.get(`/classes/${cId}`, { headers });
      setClassDetail(res.data);
    } catch {
      setClassDetail(null);
    }
  }, [api, classId, student?.class_id, headers]);

  const fetchActivities = useCallback(async () => {
    if (!studentId || !tenantId) return;
    setLoadingActivities(true);
    try {
      const [actRes, certRes] = await Promise.all([
        api.get(`/activities/student/${studentId}?school_id=${tenantId}`, { headers }),
        api.get(`/activities/certificates/student/${studentId}?school_id=${tenantId}`, { headers }),
      ]);
      setActivities(actRes.data || []);
      setCertificates(certRes.data || []);
    } catch (e) {
      console.error('[StudentProfile] fetchActivities failed:', e?.message);
    }
    setLoadingActivities(false);
  }, [studentId, tenantId]);

  const fetchLongitudinal = useCallback(async () => {
    if (!studentId) return;
    setLoadingLongitudinal(true);
    try {
      const res = await api.get(`/hakim/student/${studentId}/longitudinal`, { headers });
      setLongitudinalData(res.data);
    } catch (e) {
      console.error('[StudentProfile] fetchLongitudinal failed:', e?.message);
      setLongitudinalData(null);
    }
    setLoadingLongitudinal(false);
  }, [studentId]);

  const fetchPlanHistory = useCallback(async () => {
    if (!studentId) return;
    setLoadingPlanHistory(true);
    try {
      const res = await api.get(`/hakim/student/${studentId}/plan-history`, { headers });
      setPlanHistory(res.data || []);
    } catch (e) {
      console.error('[StudentProfile] fetchPlanHistory failed:', e?.message);
    }
    setLoadingPlanHistory(false);
  }, [studentId]);

  useEffect(() => {
    if (activeTab === 'overview' && !overviewLoaded && student) {
      fetchAttendance();
      fetchHomeworkRate();
      fetchBehaviourRecords();
      fetchClassDetail();
      setOverviewLoaded(true);
    } else if (activeTab === 'academic') {
      fetchAttendance();
      fetchAttendanceHistory();
      fetchRiskData();
      fetchHomeworkRate();
      fetchGradesDetail();
    } else if (activeTab === 'behaviour') {
      fetchBehaviourRecords();
      fetchBehaviourTypes();
    } else if (activeTab === 'talents') {
      fetchGlobalTalents();
    } else if (activeTab === 'activities') {
      fetchActivities();
    } else if (activeTab === 'plans') {
      fetchPlanHistory();
    } else if (activeTab === 'longitudinal') {
      fetchLongitudinal();
    }
  }, [activeTab, student, overviewLoaded, fetchAttendance, fetchAttendanceHistory, fetchRiskData, fetchHomeworkRate, fetchGradesDetail, fetchBehaviourRecords, fetchBehaviourTypes, fetchGlobalTalents, fetchClassDetail, fetchActivities, fetchPlanHistory, fetchLongitudinal]);

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
      const url = isPdf ? `/export/student-plans/${studentId}/pdf` : `/export/student-plans/${studentId}`;
      const mimeType = isPdf ? 'application/pdf' : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
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
      nassaqError(isRTL ? `فشل تصدير الخطة: ${detail || 'خطأ غير معروف'}` : `Failed to export plan: ${detail || 'Unknown error'}`);
    } finally {
      setExportingPlan(false);
    }
  };

  const ACTIVITY_TYPE_OPTIONS = [
    { value: 'academic', ar: 'أكاديمي', en: 'Academic', icon: '📚', color: 'bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-300' },
    { value: 'sports', ar: 'رياضي', en: 'Sports', icon: '⚽', color: 'bg-green-100 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-300' },
    { value: 'arts', ar: 'فنون', en: 'Arts', icon: '🎨', color: 'bg-purple-100 text-purple-700 border-purple-200 dark:bg-purple-900/30 dark:text-purple-300' },
    { value: 'community', ar: 'مجتمعي', en: 'Community', icon: '🤝', color: 'bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300' },
    { value: 'scientific', ar: 'علمي', en: 'Scientific', icon: '🔬', color: 'bg-cyan-100 text-cyan-700 border-cyan-200 dark:bg-cyan-900/30 dark:text-cyan-300' },
    { value: 'cultural', ar: 'ثقافي', en: 'Cultural', icon: '📖', color: 'bg-rose-100 text-rose-700 border-rose-200 dark:bg-rose-900/30 dark:text-rose-300' },
    { value: 'other', ar: 'أخرى', en: 'Other', icon: '📌', color: 'bg-gray-100 text-gray-700 border-gray-200 dark:bg-gray-900/30 dark:text-gray-300' },
  ];

  const handleExportFullProfile = async () => {
    if (!studentId || profileExportSections.length === 0) return;
    setExportingProfile(true);
    try {
      const isPdf = profileExportFormat === 'pdf';
      const url = isPdf ? `/hakim/export/student-profile/${studentId}/pdf` : `/hakim/export/student-profile/${studentId}`;
      const response = await fetch(`${api.defaults.baseURL}${url}`, {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ sections: profileExportSections }),
      });
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Export failed');
      }
      const blob = await response.blob();
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      const ext = isPdf ? 'pdf' : 'docx';
      link.download = `NASSAQ_Profile_${student?.full_name || 'student'}.${ext}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(link.href);
      toast.success(isRTL ? 'تم تصدير الملف الشامل بنجاح' : 'Full profile exported successfully');
      setProfileExportModalOpen(false);
    } catch (err) {
      nassaqError(isRTL ? `فشل التصدير: ${err.message}` : `Export failed: ${err.message}`);
    }
    setExportingProfile(false);
  };

  const toggleProfileSection = (section) => {
    setProfileExportSections(prev =>
      prev.includes(section) ? prev.filter(s => s !== section) : [...prev, section]
    );
  };

  const openActivityModal = (act = null) => {
    setEditingActivity(act);
    setActivityForm(act ? { name: act.name || '', name_en: act.name_en || '', activity_type: act.activity_type || 'academic', date: act.date || '', role: act.role || '', description: act.description || '' }
      : { name: '', name_en: '', activity_type: 'academic', date: new Date().toISOString().split('T')[0], role: '', description: '' });
    setActivityModalOpen(true);
  };

  const handleSaveActivity = async () => {
    if (!activityForm.name.trim()) return nassaqError(isRTL ? 'يرجى إدخال اسم النشاط' : 'Please enter activity name');
    setSavingActivity(true);
    try {
      if (editingActivity) {
        await api.put(`/activities/${editingActivity.id}`, activityForm, { headers });
      } else {
        await api.post(`/activities/student/${studentId}?school_id=${tenantId}`, activityForm, { headers });
      }
      toast.success(isRTL ? 'تم حفظ النشاط' : 'Activity saved');
      setActivityModalOpen(false);
      fetchActivities();
    } catch { nassaqError(isRTL ? 'فشل في حفظ النشاط' : 'Failed to save activity'); }
    setSavingActivity(false);
  };

  const handleDeleteActivity = async (act) => {
    const ok = await nassaqConfirm(isRTL ? 'هل تريد حذف هذا النشاط؟' : 'Delete this activity?');
    if (!ok) return;
    try {
      await api.delete(`/activities/${act.id}`, { headers });
      toast.success(isRTL ? 'تم حذف النشاط' : 'Activity deleted');
      fetchActivities();
    } catch { nassaqError(isRTL ? 'فشل في حذف النشاط' : 'Failed to delete activity'); }
  };

  const openCertificateModal = (cert = null) => {
    setEditingCertificate(cert);
    setCertificateForm(cert ? { title: cert.title || '', title_en: cert.title_en || '', date: cert.date || '', issuing_body: cert.issuing_body || '', description: cert.description || '' }
      : { title: '', title_en: '', date: new Date().toISOString().split('T')[0], issuing_body: '', description: '' });
    setCertificateModalOpen(true);
  };

  const handleSaveCertificate = async () => {
    if (!certificateForm.title.trim()) return nassaqError(isRTL ? 'يرجى إدخال عنوان الشهادة' : 'Please enter certificate title');
    setSavingCertificate(true);
    try {
      if (editingCertificate) {
        await api.put(`/activities/certificates/${editingCertificate.id}`, certificateForm, { headers });
      } else {
        await api.post(`/activities/certificates/student/${studentId}?school_id=${tenantId}`, certificateForm, { headers });
      }
      toast.success(isRTL ? 'تم حفظ الشهادة' : 'Certificate saved');
      setCertificateModalOpen(false);
      fetchActivities();
    } catch { nassaqError(isRTL ? 'فشل في حفظ الشهادة' : 'Failed to save certificate'); }
    setSavingCertificate(false);
  };

  const handleDeleteCertificate = async (cert) => {
    const ok = await nassaqConfirm(isRTL ? 'هل تريد حذف هذه الشهادة؟' : 'Delete this certificate?');
    if (!ok) return;
    try {
      await api.delete(`/activities/certificates/${cert.id}`, { headers });
      toast.success(isRTL ? 'تم حذف الشهادة' : 'Certificate deleted');
      fetchActivities();
    } catch { nassaqError(isRTL ? 'فشل في حذف الشهادة' : 'Failed to delete certificate'); }
  };

  const involvementScore = useMemo(() => {
    const total = activities.length + certificates.length;
    if (total === 0) return { level: 'low', label: isRTL ? 'منخفض' : 'Low', percent: 5, color: 'bg-gray-400' };
    if (total <= 2) return { level: 'moderate', label: isRTL ? 'متوسط' : 'Moderate', percent: 35, color: 'bg-yellow-500' };
    if (total <= 5) return { level: 'active', label: isRTL ? 'نشط' : 'Active', percent: 65, color: 'bg-green-500' };
    return { level: 'highly_active', label: isRTL ? 'نشط جداً' : 'Highly Active', percent: 90, color: 'bg-emerald-500' };
  }, [activities.length, certificates.length, isRTL]);

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
      if (formData.parent_email !== undefined && formData.parent_email !== student.parent_email) updateData.parent_email = formData.parent_email;
      if (formData.parent_relationship !== undefined && formData.parent_relationship !== student.parent_relationship) updateData.parent_relationship = formData.parent_relationship;
      if (formData.national_id !== undefined && formData.national_id !== student.national_id) updateData.national_id = formData.national_id;

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
      setEditProfileOpen(false);
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

  const openBehaviourModal = (record = null) => {
    if (record) {
      setEditingBehaviour(record);
      setBehaviourForm({
        category: record.category || 'positive',
        title: record.title || '',
        description: record.description || '',
        incident_date: record.incident_date || new Date().toISOString().split('T')[0],
        behaviour_type_id: record.behaviour_type_id || '',
      });
    } else {
      setEditingBehaviour(null);
      setBehaviourForm({ category: 'positive', title: '', description: '', incident_date: new Date().toISOString().split('T')[0], behaviour_type_id: '' });
    }
    setBehaviourModalOpen(true);
  };

  const handleSaveBehaviour = async () => {
    if (!behaviourForm.title.trim()) {
      nassaqError(isRTL ? 'يرجى إدخال عنوان السلوك' : 'Please enter a behavior title');
      return;
    }
    if (!behaviourForm.behaviour_type_id) {
      nassaqError(isRTL ? 'يرجى اختيار نوع السلوك' : 'Please select a behavior type');
      return;
    }
    setSavingBehaviour(true);
    try {
      if (editingBehaviour) {
        await api.put(`/behaviour-records/${editingBehaviour.id}?force=true`, {
          title: behaviourForm.title,
          description: behaviourForm.description,
          incident_date: behaviourForm.incident_date,
          category: behaviourForm.category,
          behaviour_type_id: behaviourForm.behaviour_type_id,
        }, { headers });
        toast.success(isRTL ? 'تم تعديل السجل بنجاح' : 'Record updated successfully');
      } else {
        await api.post(`/behaviour-records?school_id=${tenantId}`, {
          student_id: studentId,
          behaviour_type_id: behaviourForm.behaviour_type_id,
          title: behaviourForm.title,
          description: behaviourForm.description,
          incident_date: behaviourForm.incident_date,
          category: behaviourForm.category,
        }, { headers });
        toast.success(isRTL ? 'تم إضافة السجل بنجاح' : 'Record added successfully');
      }
      setBehaviourModalOpen(false);
      fetchBehaviourRecords();
    } catch (err) {
      const msg = err.response?.data?.detail;
      nassaqError(typeof msg === 'string' ? msg : (isRTL ? 'فشلت العملية' : 'Operation failed'));
    } finally {
      setSavingBehaviour(false);
    }
  };

  const handleDeleteBehaviour = (record) => {
    nassaqConfirm(
      isRTL ? 'هل أنت متأكد من حذف هذا السجل؟' : 'Are you sure you want to delete this record?',
      async () => {
        try {
          await api.delete(`/behaviour-records/${record.id}`, { headers });
          toast.success(isRTL ? 'تم حذف السجل' : 'Record deleted');
          fetchBehaviourRecords();
        } catch {
          nassaqError(isRTL ? 'فشل حذف السجل' : 'Failed to delete record');
        }
      },
      { title: isRTL ? 'تأكيد الحذف' : 'Confirm Delete', confirmText: isRTL ? 'نعم، احذف' : 'Yes, Delete', cancelText: isRTL ? 'إلغاء' : 'Cancel' }
    );
  };

  const handleAddTalent = async (talentValue) => {
    if (!student || !talentValue) return;
    const currentTalents = student.talents || [];
    if (currentTalents.includes(talentValue)) return;
    setSavingTalent(true);
    try {
      const newTalents = [...currentTalents, talentValue];
      await api.put(`/students/${student.id}`, { talents: newTalents }, { headers });
      toast.success(isRTL ? 'تمت إضافة الموهبة' : 'Talent added');
      fetchStudent();
    } catch (err) {
      const msg = err.response?.data?.detail;
      nassaqError(typeof msg === 'string' ? msg : (isRTL ? 'فشلت الإضافة' : 'Failed to add talent'));
    } finally {
      setSavingTalent(false);
    }
  };

  const handleRemoveTalent = async (talentValue) => {
    if (!student) return;
    const currentTalents = student.talents || [];
    const newTalents = currentTalents.filter(t => t !== talentValue);
    setSavingTalent(true);
    try {
      await api.put(`/students/${student.id}`, { talents: newTalents }, { headers });
      toast.success(isRTL ? 'تمت إزالة الموهبة' : 'Talent removed');
      fetchStudent();
    } catch {
      nassaqError(isRTL ? 'فشلت الإزالة' : 'Failed to remove talent');
    } finally {
      setSavingTalent(false);
    }
  };

  const handleAddCustomTalent = async () => {
    if (!customTalentName.trim()) return;
    setAddingCustomTalent(true);
    try {
      const res = await api.post('/talents', { name_ar: customTalentName.trim(), name_en: customTalentName.trim() }, { headers });
      const newTalent = res.data;
      setCustomTalentName('');
      fetchGlobalTalents();
      await handleAddTalent(newTalent.value || newTalent.name_ar);
    } catch (err) {
      const msg = err.response?.data?.detail;
      nassaqError(typeof msg === 'string' ? msg : (isRTL ? 'فشلت إضافة الموهبة المخصصة' : 'Failed to add custom talent'));
    } finally {
      setAddingCustomTalent(false);
    }
  };

  const handleAddCharacterTrait = async (trait) => {
    if (!student || !trait.trim()) return;
    const current = student.character_traits || [];
    if (current.includes(trait.trim())) return;
    setSavingCharacterTrait(true);
    try {
      await api.put(`/students/${student.id}`, { character_traits: [...current, trait.trim()] }, { headers });
      toast.success(isRTL ? 'تمت إضافة السمة' : 'Trait added');
      fetchStudent();
      setNewCharacterTrait('');
    } catch {
      nassaqError(isRTL ? 'فشلت الإضافة' : 'Failed to add trait');
    } finally {
      setSavingCharacterTrait(false);
    }
  };

  const handleRemoveCharacterTrait = async (trait) => {
    if (!student) return;
    const current = student.character_traits || [];
    setSavingCharacterTrait(true);
    try {
      await api.put(`/students/${student.id}`, { character_traits: current.filter(t => t !== trait) }, { headers });
      toast.success(isRTL ? 'تمت إزالة السمة' : 'Trait removed');
      fetchStudent();
    } catch {
      nassaqError(isRTL ? 'فشلت الإزالة' : 'Failed to remove trait');
    } finally {
      setSavingCharacterTrait(false);
    }
  };

  const handleBack = () => {
    if (fromPath) {
      navigate(fromPath);
    } else if (resolvedClassId) {
      navigate(`${rolePrefix}/classes/${resolvedClassId}`);
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
  const resolvedClassName = classObj?.name || classNameFromState || student?.class_name;
  const resolvedClassId = classId || student?.class_id;

  const attendanceRate = useMemo(() => {
    if (!attendanceSummary) return null;
    const present = attendanceSummary.present_count ?? attendanceSummary.present ?? 0;
    const total = (attendanceSummary.total_days ?? attendanceSummary.total ?? 0);
    return total > 0 ? Math.round((present / total) * 100) : 0;
  }, [attendanceSummary]);

  const positiveBehaviourCount = behaviourSummary?.positive_count || 0;

  const profileCompleteness = useMemo(() => {
    if (!student) return { percent: 0, missing: [] };
    const fields = [
      { key: 'full_name', ar: 'الاسم الكامل', en: 'Full Name' },
      { key: 'national_id', ar: 'رقم الهوية', en: 'National ID' },
      { key: 'email', ar: 'البريد الإلكتروني', en: 'Email' },
      { key: 'phone', ar: 'الهاتف', en: 'Phone' },
      { key: 'gender', ar: 'الجنس', en: 'Gender' },
      { key: 'date_of_birth', ar: 'تاريخ الميلاد', en: 'Date of Birth' },
      { key: 'nationality', ar: 'الجنسية', en: 'Nationality' },
      { key: 'parent_name', ar: 'اسم ولي الأمر', en: 'Guardian Name' },
      { key: 'parent_phone', ar: 'هاتف ولي الأمر', en: 'Guardian Phone' },
      { key: 'emergency_contact', ar: 'جهة اتصال الطوارئ', en: 'Emergency Contact' },
      { key: 'emergency_phone', ar: 'هاتف الطوارئ', en: 'Emergency Phone' },
    ];
    const filled = fields.filter(f => {
      const v = student[f.key];
      return v !== null && v !== undefined && v !== '';
    });
    const missing = fields.filter(f => {
      const v = student[f.key];
      return v === null || v === undefined || v === '';
    });
    return { percent: Math.round((filled.length / fields.length) * 100), missing };
  }, [student]);

  const attendanceChartData = useMemo(() => {
    if (!attendanceHistory || attendanceHistory.length === 0) return [];
    const monthly = {};
    attendanceHistory.forEach(r => {
      const d = r.date || r.attendance_date;
      if (!d) return;
      const month = d.substring(0, 7);
      if (!monthly[month]) monthly[month] = { month, present: 0, absent: 0, late: 0, excused: 0 };
      const status = (r.status || '').toLowerCase();
      if (status === 'present') monthly[month].present++;
      else if (status === 'absent') monthly[month].absent++;
      else if (status === 'late') monthly[month].late++;
      else if (status === 'excused') monthly[month].excused++;
    });
    return Object.values(monthly).sort((a, b) => a.month.localeCompare(b.month));
  }, [attendanceHistory]);

  const subjectGrades = useMemo(() => {
    if (!gradesDetail) return [];
    const grades = gradesDetail.grades || gradesDetail.subjects || gradesDetail;
    if (!Array.isArray(grades)) return [];
    return grades;
  }, [gradesDetail]);

  const radarChartData = useMemo(() => {
    if (!student) return [];
    const talents = student.talents || [];
    const dims = [
      { key: 'academic', ar: 'أكاديمي', en: 'Academic', match: ['academically_gifted', 'scientific'] },
      { key: 'creative', ar: 'إبداعي', en: 'Creative', match: ['artistic', 'musical', 'literary'] },
      { key: 'athletic', ar: 'رياضي', en: 'Athletic', match: ['athletic'] },
      { key: 'technical', ar: 'تقني', en: 'Technical', match: ['technological', 'scientific'] },
      { key: 'social', ar: 'اجتماعي', en: 'Social', match: ['leadership'] },
      { key: 'leadership', ar: 'قيادي', en: 'Leadership', match: ['leadership'] },
    ];
    return dims.map(d => {
      const matchCount = talents.filter(t => d.match.includes(t)).length;
      const base = matchCount > 0 ? Math.min(40 + matchCount * 30, 100) : 10;
      return { dimension: isRTL ? d.ar : d.en, value: base, fullMark: 100 };
    });
  }, [student, isRTL]);

  const behaviourTrendData = useMemo(() => {
    if (!behaviourRecords || behaviourRecords.length === 0) return [];
    const monthly = {};
    behaviourRecords.forEach(r => {
      const d = r.incident_date || r.created_at?.split('T')[0] || '';
      if (!d) return;
      const month = d.substring(0, 7);
      if (!monthly[month]) monthly[month] = { month, positive: 0, negative: 0 };
      if (r.category === 'positive') monthly[month].positive++;
      else if (r.category === 'negative') monthly[month].negative++;
    });
    return Object.values(monthly).sort((a, b) => a.month.localeCompare(b.month));
  }, [behaviourRecords]);

  const BEHAVIOUR_PAGE_SIZE = 10;
  const behaviourTotalPages = Math.max(1, Math.ceil(behaviourRecords.length / BEHAVIOUR_PAGE_SIZE));
  useEffect(() => {
    setBehaviourPage(p => Math.min(p, Math.max(1, Math.ceil(behaviourRecords.length / BEHAVIOUR_PAGE_SIZE))));
  }, [behaviourRecords.length]);
  const paginatedBehaviourRecords = useMemo(() => {
    const start = (behaviourPage - 1) * BEHAVIOUR_PAGE_SIZE;
    return behaviourRecords.slice(start, start + BEHAVIOUR_PAGE_SIZE);
  }, [behaviourRecords, behaviourPage]);

  const CAREER_AFFINITY_MAP = {
    academically_gifted: { ar: 'البحث العلمي', en: 'Research' },
    scientific: { ar: 'الهندسة والطب', en: 'Engineering & Medicine' },
    artistic: { ar: 'الفنون والتصميم', en: 'Arts & Design' },
    musical: { ar: 'الموسيقى والأداء', en: 'Music & Performance' },
    literary: { ar: 'الكتابة والإعلام', en: 'Writing & Media' },
    athletic: { ar: 'الرياضة والتدريب', en: 'Sports & Coaching' },
    technological: { ar: 'التقنية والبرمجة', en: 'Technology & Programming' },
    leadership: { ar: 'الإدارة والقيادة', en: 'Management & Leadership' },
  };

  const CHARACTER_TRAIT_OPTIONS = [
    { ar: 'مسؤول', en: 'Responsible' },
    { ar: 'متعاطف', en: 'Empathetic' },
    { ar: 'مبدع', en: 'Creative' },
    { ar: 'قيادي', en: 'Leader' },
    { ar: 'مثابر', en: 'Persistent' },
    { ar: 'فضولي', en: 'Curious' },
    { ar: 'متعاون', en: 'Collaborative' },
    { ar: 'منضبط', en: 'Disciplined' },
    { ar: 'صادق', en: 'Honest' },
    { ar: 'متفائل', en: 'Optimistic' },
    { ar: 'محترم', en: 'Respectful' },
    { ar: 'كريم', en: 'Generous' },
  ];

  const TABS = [
    { value: 'overview', label_ar: 'نظرة عامة', label_en: 'Overview', icon: Eye },
    { value: 'academic', label_ar: 'الأداء الأكاديمي', label_en: 'Academic', icon: BarChart3 },
    { value: 'talents', label_ar: 'المواهب والمهارات', label_en: 'Talents & Skills', icon: Sparkles },
    { value: 'behaviour', label_ar: 'السلوك والشخصية', label_en: 'Behavior', icon: Heart },
    { value: 'activities', label_ar: 'الأنشطة والإنجازات', label_en: 'Activities', icon: Medal },
    { value: 'plans', label_ar: 'الخطط', label_en: 'Plans', icon: ClipboardList },
    { value: 'longitudinal', label_ar: 'السجل التراكمي', label_en: 'Record', icon: ScrollText },
  ];

  if (loading) {
    return (
      <div className="flex min-h-screen bg-background">
        <Sidebar />
        <main className="flex-1 overflow-auto">
          <div className="p-6 max-w-6xl mx-auto space-y-6">
            <div className="flex items-center gap-4 mb-4">
              <Skeleton className="h-9 w-9 rounded-full" />
              <div className="space-y-2 flex-1">
                <Skeleton className="h-5 w-48" />
                <Skeleton className="h-3 w-72" />
              </div>
            </div>
            <div className="rounded-2xl border bg-gradient-to-r from-brand-turquoise/5 to-brand-purple/5 p-6">
              <div className="flex items-start gap-5">
                <Skeleton className="h-24 w-24 rounded-full" />
                <div className="flex-1 space-y-3">
                  <Skeleton className="h-7 w-56" />
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-3 w-24" />
                </div>
              </div>
              <div className="grid grid-cols-5 gap-3 mt-6">
                {[...Array(5)].map((_, i) => (
                  <Skeleton key={i} className="h-20 rounded-xl" />
                ))}
              </div>
            </div>
            <Skeleton className="h-10 w-full rounded-lg" />
            <div className="grid grid-cols-2 gap-4">
              <Skeleton className="h-40 rounded-xl" />
              <Skeleton className="h-40 rounded-xl" />
            </div>
          </div>
        </main>
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

  const relationshipMap = { father: isRTL ? 'أب' : 'Father', mother: isRTL ? 'أم' : 'Mother', guardian: isRTL ? 'ولي أمر' : 'Guardian', brother: isRTL ? 'أخ' : 'Brother', sister: isRTL ? 'أخت' : 'Sister', uncle: isRTL ? 'عم / خال' : 'Uncle', other: isRTL ? 'أخرى' : 'Other' };

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        {/* ===== STICKY HEADER ===== */}
        <header className="sticky top-0 z-30 backdrop-blur-xl bg-background/80 border-b px-4 md:px-6 py-3">
          <div className="flex items-center justify-between max-w-6xl mx-auto">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" className="h-9 w-9" onClick={handleBack}>
                <BackArrow className="h-5 w-5" />
              </Button>
              <nav className="flex items-center gap-1 text-xs text-muted-foreground">
                <button onClick={() => navigate(`${rolePrefix}/users-management?filter=students`)} className="hover:text-foreground transition-colors font-cairo">
                  {isRTL ? 'إدارة المستخدمين' : 'User Management'}
                </button>
                {resolvedClassName && (
                  <>
                    <ChevronRight className="h-3 w-3" />
                    <button onClick={() => resolvedClassId && navigate(`${rolePrefix}/classes/${resolvedClassId}`)} className="hover:text-foreground transition-colors font-cairo">
                      {resolvedClassName}
                    </button>
                  </>
                )}
                <ChevronRight className="h-3 w-3" />
                <span className="text-foreground font-medium font-cairo">{student.full_name}</span>
              </nav>
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

        <div className="max-w-6xl mx-auto">
          {/* ===== HERO SECTION ===== */}
          <div className="relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-br from-brand-navy via-brand-navy/95 to-brand-purple opacity-95" />
            <div className="absolute inset-0 opacity-5" style={{ backgroundImage: 'url(/nassaq-pattern.png)', backgroundSize: '200px' }} />
            <div className="relative px-4 md:px-8 py-6 md:py-8">
              <div className="flex flex-col md:flex-row items-start gap-5">
                {/* Avatar */}
                <div className="relative flex-shrink-0">
                  <div className={`w-24 h-24 md:w-28 md:h-28 rounded-full bg-gradient-to-br from-brand-turquoise to-brand-purple/80 flex items-center justify-center shadow-xl border-4 border-white/20 ${student.is_gifted ? 'ring-4 ring-amber-400/60 ring-offset-2 ring-offset-brand-navy' : ''}`}>
                    <span className="text-white font-bold text-4xl md:text-5xl font-cairo">{student.full_name?.charAt(0)}</span>
                  </div>
                  {student.is_gifted && (
                    <div className="absolute -top-1 -end-1 w-8 h-8 rounded-full bg-gradient-to-br from-yellow-400 to-amber-500 flex items-center justify-center shadow-lg border-2 border-white/30">
                      <Star className="h-4 w-4 text-white fill-white" />
                    </div>
                  )}
                </div>

                {/* Name & Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex flex-col sm:flex-row sm:items-start gap-3 mb-2">
                    <div className="flex-1 min-w-0">
                      <h1 className="text-2xl md:text-3xl font-bold text-white font-cairo leading-tight">{student.full_name}</h1>
                      <p className="text-white/70 text-sm mt-1 font-cairo flex items-center gap-2 flex-wrap">
                        <GraduationCap className="h-4 w-4" />
                        {student.grade || '-'} {resolvedClassName ? `— ${resolvedClassName}` : student.section ? `— ${student.section}` : ''}
                      </p>
                      <p className="text-white/50 text-xs mt-1 font-mono tracking-wider">
                        {student.student_number || student.national_id || `ID: ${student.id?.slice(0, 8)}`}
                      </p>
                    </div>

                    {/* Badges */}
                    <div className="flex items-center gap-2 flex-wrap">
                      {student.is_gifted && (
                        <Badge className="bg-gradient-to-r from-yellow-400 to-amber-500 text-white border-0 px-3 py-1.5 font-cairo shadow-lg text-xs">
                          <Star className="h-3.5 w-3.5 fill-white me-1" />
                          {isRTL ? 'طالب موهوب' : 'Gifted'}
                        </Badge>
                      )}
                      <Badge variant={student.is_active !== false ? 'default' : 'destructive'} className={`text-xs px-2.5 py-1 ${student.is_active !== false ? 'bg-emerald-500/20 text-emerald-200 border-emerald-400/30' : ''}`}>
                        {student.is_active !== false ? (isRTL ? 'نشط' : 'Active') : (isRTL ? 'معلق' : 'Suspended')}
                      </Badge>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="flex items-center gap-2 mt-4 flex-wrap">
                    <Button size="sm" variant="secondary" className="gap-1.5 text-xs bg-white/10 hover:bg-white/20 text-white border-white/20 backdrop-blur-sm" onClick={() => { setFormData({ ...student }); setEditProfileOpen(true); }}>
                      <Edit className="h-3.5 w-3.5" /> {isRTL ? 'تعديل الملف' : 'Edit Profile'}
                    </Button>
                    <Button size="sm" variant="secondary" className="gap-1.5 text-xs bg-white/10 hover:bg-white/20 text-white border-white/20 backdrop-blur-sm" onClick={() => setProfileExportModalOpen(true)}>
                      <Download className="h-3.5 w-3.5" /> {isRTL ? 'تصدير الملف الشامل' : 'Export Full Profile'}
                    </Button>
                    {(remedialPlan || enrichmentPlan) && (
                      <Button size="sm" variant="secondary" className="gap-1.5 text-xs bg-white/10 hover:bg-white/20 text-white border-white/20 backdrop-blur-sm" onClick={() => openExportModal('both')}>
                        <Download className="h-3.5 w-3.5" /> {isRTL ? 'تصدير الخطة' : 'Export Plan'}
                      </Button>
                    )}
                    {student.parent_phone && (
                      <Button size="sm" variant="secondary" className="gap-1.5 text-xs bg-white/10 hover:bg-white/20 text-white border-white/20 backdrop-blur-sm" onClick={() => window.open(`https://wa.me/${student.parent_phone.replace(/\D/g, '')}`, '_blank')}>
                        <Send className="h-3.5 w-3.5" /> {isRTL ? 'مراسلة ولي الأمر' : 'Message Parent'}
                      </Button>
                    )}
                    {!isTeacher && (
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button size="sm" variant="secondary" className="gap-1 text-xs bg-white/10 hover:bg-white/20 text-white border-white/20 backdrop-blur-sm px-2">
                            <MoreVertical className="h-3.5 w-3.5" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align={isRTL ? 'start' : 'end'} className="w-52">
                          <DropdownMenuItem onClick={() => handleAction('reset-password')} className="gap-2 font-cairo text-sm">
                            <Key className="h-4 w-4 text-blue-500" /> {isRTL ? 'إعادة تعيين كلمة المرور' : 'Reset Password'}
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => handleAction(student.is_active !== false ? 'suspend' : 'activate')} className="gap-2 font-cairo text-sm">
                            {student.is_active !== false
                              ? <><UserX className="h-4 w-4 text-amber-500" /> {isRTL ? 'تعليق الحساب' : 'Suspend'}</>
                              : <><UserCheck className="h-4 w-4 text-green-500" /> {isRTL ? 'تفعيل الحساب' : 'Activate'}</>
                            }
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem onClick={() => handleAction('delete')} className="gap-2 font-cairo text-sm text-red-600 focus:text-red-600">
                            <Trash2 className="h-4 w-4" /> {isRTL ? 'حذف الحساب' : 'Delete Account'}
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                  </div>
                </div>
              </div>

              {/* Quick Stats Bar */}
              <div className="grid grid-cols-5 gap-2 md:gap-3 mt-6">
                <StatCard icon={Calendar} value={attendanceRate != null ? `${attendanceRate}%` : null} label={isRTL ? 'نسبة الحضور' : 'Attendance'} color="text-emerald-300" bg="bg-white/10 backdrop-blur-sm" loading={loadingAttendance} />
                <StatCard icon={CheckCircle} value={homeworkRate ? `${homeworkRate.rate}%` : null} label={isRTL ? 'معدل الأداء' : 'Performance'} color="text-blue-300" bg="bg-white/10 backdrop-blur-sm" loading={loadingHomework} />
                <StatCard icon={Sparkles} value={student.talents?.length || 0} label={isRTL ? 'المواهب' : 'Talents'} color="text-purple-300" bg="bg-white/10 backdrop-blur-sm" loading={false} />
                <StatCard icon={Trophy} value={0} label={isRTL ? 'الأنشطة' : 'Activities'} color="text-amber-300" bg="bg-white/10 backdrop-blur-sm" loading={false} />
                <StatCard icon={ThumbsUp} value={positiveBehaviourCount} label={isRTL ? 'سلوك إيجابي' : 'Positive'} color="text-green-300" bg="bg-white/10 backdrop-blur-sm" loading={loadingBehaviour} />
              </div>
            </div>
          </div>

          {/* ===== TABS ===== */}
          <div className="px-4 md:px-8 pb-8">
            <Tabs value={activeTab} onValueChange={setActiveTab} className="mt-0">
              <div className="sticky top-[57px] z-20 bg-background pt-3 pb-1 -mx-4 md:-mx-8 px-4 md:px-8 border-b">
                <ScrollArea className="w-full" dir={isRTL ? 'rtl' : 'ltr'}>
                  <TabsList className="inline-flex h-10 bg-transparent p-0 gap-0 w-full justify-start">
                    {TABS.map(tab => (
                      <TabsTrigger key={tab.value} value={tab.value}
                        className="relative px-4 py-2.5 text-xs font-cairo gap-1.5 rounded-none border-b-2 border-transparent data-[state=active]:border-brand-turquoise data-[state=active]:text-brand-turquoise data-[state=active]:shadow-none bg-transparent whitespace-nowrap">
                        <tab.icon className="h-3.5 w-3.5" />
                        {isRTL ? tab.label_ar : tab.label_en}
                      </TabsTrigger>
                    ))}
                  </TabsList>
                  <ScrollBar orientation="horizontal" />
                </ScrollArea>
              </div>

              {/* ===== OVERVIEW TAB ===== */}
              <TabsContent value="overview" className="mt-6 space-y-4">
                {/* Profile Completeness Bar */}
                <Card className="border-brand-turquoise/20 bg-gradient-to-r from-brand-turquoise/5 to-brand-purple/5 dark:from-brand-turquoise/10 dark:to-brand-purple/10">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-bold text-sm font-cairo flex items-center gap-2">
                        <CheckCircle className="h-4 w-4 text-brand-turquoise" />
                        {isRTL ? 'اكتمال الملف الشخصي' : 'Profile Completeness'}
                      </h3>
                      <span className={`text-sm font-bold font-cairo tabular-nums ${profileCompleteness.percent === 100 ? 'text-green-600' : profileCompleteness.percent >= 70 ? 'text-brand-turquoise' : 'text-amber-600'}`}>{profileCompleteness.percent}%</span>
                    </div>
                    <Progress value={profileCompleteness.percent} className={`h-2.5 ${profileCompleteness.percent === 100 ? '[&>div]:bg-green-500' : profileCompleteness.percent >= 70 ? '[&>div]:bg-brand-turquoise' : '[&>div]:bg-amber-500'}`} />
                    {profileCompleteness.missing.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-2.5">
                        <span className="text-[11px] text-muted-foreground font-cairo">{isRTL ? 'ناقص:' : 'Missing:'}</span>
                        {profileCompleteness.missing.slice(0, 4).map(f => (
                          <Badge key={f.key} variant="outline" className="text-[10px] px-1.5 py-0 h-5 cursor-pointer hover:bg-brand-turquoise/10 border-dashed" onClick={() => { setFormData({ ...student }); setEditProfileOpen(true); }}>
                            {isRTL ? f.ar : f.en}
                          </Badge>
                        ))}
                        {profileCompleteness.missing.length > 4 && (
                          <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-5 cursor-pointer hover:bg-brand-turquoise/10 border-dashed" onClick={() => { setFormData({ ...student }); setEditProfileOpen(true); }}>
                            +{profileCompleteness.missing.length - 4}
                          </Badge>
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {/* Personal Info Card */}
                  <Card>
                    <CardContent className="p-5">
                      <h3 className="font-bold text-sm font-cairo flex items-center gap-2 mb-4">
                        <User className="h-4 w-4 text-brand-turquoise" />
                        {isRTL ? 'البيانات الشخصية' : 'Personal Info'}
                      </h3>
                      <div className="grid grid-cols-2 gap-4">
                        <DataField label={isRTL ? 'الاسم الكامل' : 'Full Name'} value={student.full_name} />
                        <DataField label={isRTL ? 'رقم الهوية' : 'National ID'} value={student.national_id} icon={Hash} />
                        <DataField label={isRTL ? 'البريد الإلكتروني' : 'Email'} value={student.email} icon={Mail} />
                        <DataField label={isRTL ? 'الهاتف' : 'Phone'} value={student.phone} icon={Phone} />
                        <DataField label={isRTL ? 'الجنس' : 'Gender'} value={student.gender === 'male' ? (isRTL ? 'ذكر' : 'Male') : student.gender === 'female' ? (isRTL ? 'أنثى' : 'Female') : null} />
                        <DataField label={isRTL ? 'تاريخ الميلاد' : 'Date of Birth'} value={student.date_of_birth} icon={Calendar} />
                        <DataField label={isRTL ? 'الجنسية' : 'Nationality'} value={student.nationality} icon={Globe} />
                        <DataField label={isRTL ? 'تاريخ التسجيل' : 'Enrollment Date'} value={student.enrollment_date} icon={Calendar} />
                      </div>
                    </CardContent>
                  </Card>

                  {/* Guardian & Emergency Card */}
                  <Card>
                    <CardContent className="p-5">
                      <h3 className="font-bold text-sm font-cairo flex items-center gap-2 mb-4">
                        <Heart className="h-4 w-4 text-rose-500" />
                        {isRTL ? 'ولي الأمر والطوارئ' : 'Guardian & Emergency'}
                      </h3>
                      {student.parent_name ? (
                        <div className="space-y-4">
                          <div className="grid grid-cols-2 gap-4">
                            <DataField label={isRTL ? 'الاسم' : 'Name'} value={student.parent_name} />
                            <DataField label={isRTL ? 'صلة القرابة' : 'Relationship'} value={relationshipMap[student.parent_relationship] || student.parent_relationship} />
                            <DataField label={isRTL ? 'الهاتف' : 'Phone'} value={student.parent_phone} icon={Phone} />
                            <DataField label={isRTL ? 'البريد' : 'Email'} value={student.parent_email} icon={Mail} />
                          </div>
                          {(student.emergency_contact || student.emergency_phone) && (
                            <div className="border-t pt-3">
                              <p className="text-[11px] text-muted-foreground font-cairo mb-2 flex items-center gap-1">
                                <AlertTriangle className="h-3 w-3 text-amber-500" />
                                {isRTL ? 'جهة اتصال الطوارئ' : 'Emergency Contact'}
                              </p>
                              <div className="grid grid-cols-2 gap-4">
                                <DataField label={isRTL ? 'الاسم' : 'Name'} value={student.emergency_contact} />
                                <DataField label={isRTL ? 'الهاتف' : 'Phone'} value={student.emergency_phone} icon={Phone} />
                              </div>
                            </div>
                          )}
                        </div>
                      ) : (
                        <EmptyState icon={Heart} message={isRTL ? 'لم يتم إضافة بيانات ولي الأمر' : 'No guardian info added'} actionLabel={isRTL ? 'إضافة بيانات' : 'Add Info'} onAction={() => { setFormData({ ...student }); setEditProfileOpen(true); }} />
                      )}
                    </CardContent>
                  </Card>

                  {/* Academic Snapshot Card */}
                  <Card>
                    <CardContent className="p-5">
                      <h3 className="font-bold text-sm font-cairo flex items-center gap-2 mb-4">
                        <GraduationCap className="h-4 w-4 text-brand-navy" />
                        {isRTL ? 'لمحة أكاديمية' : 'Academic Snapshot'}
                      </h3>
                      <div className="grid grid-cols-2 gap-4">
                        <DataField label={isRTL ? 'الصف' : 'Class'} value={student.class_name || classNameFromState} icon={BookOpen} />
                        <DataField label={isRTL ? 'معلم الفصل' : 'Homeroom Teacher'} value={classDetail?.homeroom_teacher_name} icon={User} />
                        <div className="col-span-2 grid grid-cols-3 gap-3 pt-1">
                          <div className="text-center p-2.5 bg-green-50 dark:bg-green-950/20 rounded-lg">
                            <p className={`text-xl font-bold font-cairo ${attendanceRate !== null ? (attendanceRate >= 80 ? 'text-green-600' : attendanceRate >= 60 ? 'text-amber-600' : 'text-red-600') : 'text-muted-foreground'}`}>
                              {loadingAttendance ? '...' : attendanceRate !== null ? `${attendanceRate}%` : '—'}
                            </p>
                            <p className="text-[10px] text-muted-foreground font-cairo">{isRTL ? 'الحضور' : 'Attendance'}</p>
                          </div>
                          <div className="text-center p-2.5 bg-blue-50 dark:bg-blue-950/20 rounded-lg">
                            <p className={`text-xl font-bold font-cairo ${homeworkRate ? (homeworkRate.rate >= 80 ? 'text-green-600' : homeworkRate.rate >= 50 ? 'text-amber-600' : 'text-red-600') : 'text-muted-foreground'}`}>
                              {loadingHomework ? '...' : homeworkRate ? `${homeworkRate.rate}%` : '—'}
                            </p>
                            <p className="text-[10px] text-muted-foreground font-cairo">{isRTL ? 'الأكاديمي' : 'Academic'}</p>
                          </div>
                          <div className="text-center p-2.5 bg-purple-50 dark:bg-purple-950/20 rounded-lg">
                            <p className="text-xl font-bold font-cairo text-brand-navy">
                              {loadingBehaviour ? '...' : behaviourSummary ? (behaviourSummary.total_points || 0) : '—'}
                            </p>
                            <p className="text-[10px] text-muted-foreground font-cairo">{isRTL ? 'السلوك' : 'Behavior'}</p>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  {/* Health & Notes Card */}
                  <Card>
                    <CardContent className="p-5">
                      <h3 className="font-bold text-sm font-cairo flex items-center gap-2 mb-4">
                        <Stethoscope className="h-4 w-4 text-rose-500" />
                        {isRTL ? 'الصحة والملاحظات' : 'Health & Notes'}
                      </h3>
                      {student.health_info && Object.keys(student.health_info).length > 0 ? (
                        <div className="space-y-3">
                          {student.health_info.blood_type && (
                            <DataField label={isRTL ? 'فصيلة الدم' : 'Blood Type'} value={student.health_info.blood_type} />
                          )}
                          {student.health_info.has_chronic_conditions && student.health_info.chronic_conditions && (
                            <div>
                              <p className="text-[11px] text-muted-foreground font-cairo mb-1">{isRTL ? 'أمراض مزمنة' : 'Chronic Conditions'}</p>
                              <p className="text-sm font-cairo">{student.health_info.chronic_conditions}</p>
                            </div>
                          )}
                          {student.health_info.has_allergies && student.health_info.allergies && (
                            <div>
                              <p className="text-[11px] text-muted-foreground font-cairo mb-1">{isRTL ? 'حساسية' : 'Allergies'}</p>
                              <p className="text-sm font-cairo">{student.health_info.allergies}</p>
                            </div>
                          )}
                          {student.health_info.has_disabilities && student.health_info.disabilities && (
                            <div>
                              <p className="text-[11px] text-muted-foreground font-cairo mb-1">{isRTL ? 'إعاقات' : 'Disabilities'}</p>
                              <p className="text-sm font-cairo">{student.health_info.disabilities}</p>
                            </div>
                          )}
                          {student.health_info.requires_special_care && student.health_info.special_care_notes && (
                            <div className="p-2 bg-amber-50 dark:bg-amber-950/20 rounded-lg border border-amber-200 dark:border-amber-800/30">
                              <p className="text-[11px] text-amber-600 font-cairo mb-1 flex items-center gap-1">
                                <AlertTriangle className="h-3 w-3" />
                                {isRTL ? 'ملاحظات رعاية خاصة' : 'Special Care Notes'}
                              </p>
                              <p className="text-sm font-cairo">{student.health_info.special_care_notes}</p>
                            </div>
                          )}
                          {student.health_info.emergency_medical_notes && (
                            <div className="p-2 bg-red-50 dark:bg-red-950/20 rounded-lg border border-red-200 dark:border-red-800/30">
                              <p className="text-[11px] text-red-600 font-cairo mb-1 flex items-center gap-1">
                                <Heart className="h-3 w-3" />
                                {isRTL ? 'ملاحظات طبية طارئة' : 'Emergency Medical Notes'}
                              </p>
                              <p className="text-sm font-cairo">{student.health_info.emergency_medical_notes}</p>
                            </div>
                          )}
                        </div>
                      ) : (
                        <EmptyState icon={Stethoscope} message={isRTL ? 'لا توجد بيانات صحية مسجلة' : 'No health info recorded'} actionLabel={isRTL ? 'إضافة بيانات' : 'Add Info'} onAction={() => { setFormData({ ...student }); setEditProfileOpen(true); }} />
                      )}
                    </CardContent>
                  </Card>
                </div>

                {/* Talents Preview */}
                {(student.talents?.length > 0) && (
                  <Card>
                    <CardContent className="p-5">
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="font-bold text-sm font-cairo flex items-center gap-2">
                          <Sparkles className="h-4 w-4 text-brand-turquoise" />
                          {isRTL ? 'المواهب' : 'Talents'}
                        </h3>
                        <Button variant="ghost" size="sm" className="text-xs text-brand-turquoise" onClick={() => setActiveTab('talents')}>
                          {isRTL ? 'عرض الكل' : 'View All'} <ChevronRight className="h-3 w-3 ms-1" />
                        </Button>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {student.talents.slice(0, 6).map(t => {
                          const cfg = getTalentConfig(t);
                          return (
                            <Badge key={t} variant="outline" className={`text-xs px-2.5 py-1 border ${cfg.color}`}>
                              <Star className="h-3 w-3 me-1 fill-current" />
                              {isRTL ? cfg.ar : cfg.en}
                            </Badge>
                          );
                        })}
                        {student.talents.length > 6 && (
                          <Badge variant="outline" className="text-xs px-2.5 py-1">+{student.talents.length - 6}</Badge>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                )}
              </TabsContent>

              {/* ===== ACADEMIC TAB ===== */}
              <TabsContent value="academic" className="mt-6 space-y-4">
                {/* Attendance Summary + Chart */}
                <Card>
                  <CardContent className="p-6 space-y-4">
                    <h3 className="font-bold text-base font-cairo flex items-center gap-2">
                      <Activity className="h-5 w-5 text-brand-turquoise" />
                      {isRTL ? 'ملخص الحضور' : 'Attendance Summary'}
                    </h3>
                    {loadingAttendance ? (
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-20 rounded-xl" />)}
                      </div>
                    ) : attendanceSummary ? (
                      <div className="space-y-4">
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
                        {loadingAttendanceHistory ? (
                          <div className="space-y-2 pt-2">
                            <Skeleton className="h-4 w-32" />
                            <Skeleton className="h-48 w-full rounded-xl" />
                          </div>
                        ) : attendanceChartData.length > 0 ? (
                          <div>
                            <h4 className="text-sm font-medium font-cairo mb-2">{isRTL ? 'الحضور الشهري' : 'Monthly Attendance'}</h4>
                            <div className="h-52">
                              <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={attendanceChartData} barGap={2}>
                                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                                  <XAxis dataKey="month" tick={{ fontSize: 11 }} tickFormatter={v => v.substring(5)} />
                                  <YAxis tick={{ fontSize: 11 }} />
                                  <RechartsTooltip contentStyle={{ borderRadius: 8, fontSize: 12 }} />
                                  <Bar dataKey="present" name={isRTL ? 'حاضر' : 'Present'} fill="#22c55e" radius={[3, 3, 0, 0]} />
                                  <Bar dataKey="absent" name={isRTL ? 'غائب' : 'Absent'} fill="#ef4444" radius={[3, 3, 0, 0]} />
                                  <Bar dataKey="late" name={isRTL ? 'متأخر' : 'Late'} fill="#f59e0b" radius={[3, 3, 0, 0]} />
                                  <Bar dataKey="excused" name={isRTL ? 'بعذر' : 'Excused'} fill="#3b82f6" radius={[3, 3, 0, 0]} />
                                </BarChart>
                              </ResponsiveContainer>
                            </div>
                          </div>
                        ) : null}
                      </div>
                    ) : (
                      <EmptyState icon={Calendar} message={isRTL ? 'لا توجد بيانات حضور' : 'No attendance data available'} />
                    )}
                  </CardContent>
                </Card>

                {/* Grades & Performance */}
                <Card>
                  <CardContent className="p-6 space-y-4">
                    <h3 className="font-bold text-base font-cairo flex items-center gap-2">
                      <CheckCircle className="h-5 w-5 text-indigo-500" />
                      {isRTL ? 'الأداء الأكاديمي والدرجات' : 'Grades & Academic Performance'}
                    </h3>
                    {loadingHomework || loadingGrades ? (
                      <div className="space-y-3">
                        <Skeleton className="h-4 w-full rounded" />
                        <div className="grid grid-cols-2 gap-3">
                          <Skeleton className="h-20 rounded-xl" />
                          <Skeleton className="h-20 rounded-xl" />
                        </div>
                        <Skeleton className="h-48 rounded-xl" />
                      </div>
                    ) : (
                      <div className="space-y-4">
                        {homeworkRate && (
                          <div className="space-y-3">
                            <div className="flex items-center gap-3">
                              <div className="flex-1">
                                <Progress value={homeworkRate.rate} className={`h-3 rounded-full bg-gray-100 dark:bg-gray-800 ${homeworkRate.rate >= 80 ? '[&>div]:bg-green-500' : homeworkRate.rate >= 50 ? '[&>div]:bg-amber-500' : '[&>div]:bg-red-500'}`} />
                              </div>
                              <span className={`text-lg font-bold font-cairo tabular-nums ${homeworkRate.rate >= 80 ? 'text-green-600' : homeworkRate.rate >= 50 ? 'text-amber-600' : 'text-red-600'}`}>{homeworkRate.rate}%</span>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                              <div className="text-center p-3 bg-green-50 dark:bg-green-950/20 rounded-xl">
                                <p className="text-xl font-bold font-cairo text-green-600">{homeworkRate.completed}</p>
                                <p className="text-xs text-muted-foreground mt-1">{isRTL ? 'درجات مسجلة' : 'Graded'}</p>
                              </div>
                              <div className="text-center p-3 bg-gray-50 dark:bg-gray-800/30 rounded-xl">
                                <p className="text-xl font-bold font-cairo text-gray-600">{homeworkRate.total}</p>
                                <p className="text-xs text-muted-foreground mt-1">{isRTL ? 'إجمالي التقييمات' : 'Total Assessments'}</p>
                              </div>
                            </div>
                          </div>
                        )}
                        {subjectGrades.length > 0 && (
                          <div>
                            <h4 className="text-sm font-medium font-cairo mb-3 flex items-center gap-2">
                              <BookOpen className="h-4 w-4 text-brand-navy" />
                              {isRTL ? 'الدرجات حسب المادة' : 'Grades by Subject'}
                            </h4>
                            <div className="rounded-lg border overflow-hidden">
                              <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                  <thead>
                                    <tr className="bg-muted/50">
                                      <th className="text-start p-3 font-medium font-cairo">{isRTL ? 'المادة' : 'Subject'}</th>
                                      <th className="text-center p-3 font-medium font-cairo">{isRTL ? 'الدرجة' : 'Score'}</th>
                                      <th className="text-center p-3 font-medium font-cairo">{isRTL ? 'من' : 'Out of'}</th>
                                      <th className="text-center p-3 font-medium font-cairo">%</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {subjectGrades.map((g, i) => {
                                      const score = g.score ?? g.grade ?? g.marks ?? 0;
                                      const total = g.total ?? g.max_score ?? g.out_of ?? 100;
                                      const pct = total > 0 ? Math.round((score / total) * 100) : 0;
                                      return (
                                        <tr key={i} className="border-t hover:bg-muted/20 transition-colors">
                                          <td className="p-3 font-cairo">{g.subject_name || g.subject || g.name || `—`}</td>
                                          <td className="p-3 text-center font-cairo tabular-nums font-medium">{score}</td>
                                          <td className="p-3 text-center font-cairo tabular-nums text-muted-foreground">{total}</td>
                                          <td className="p-3 text-center">
                                            <span className={`font-bold font-cairo tabular-nums ${pct >= 80 ? 'text-green-600' : pct >= 60 ? 'text-amber-600' : 'text-red-600'}`}>{pct}%</span>
                                          </td>
                                        </tr>
                                      );
                                    })}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                            <div className="h-52 mt-4">
                              <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={subjectGrades.map(g => ({
                                  name: (g.subject_name || g.subject || g.name || '').substring(0, 12),
                                  score: g.score ?? g.grade ?? g.marks ?? 0,
                                  total: g.total ?? g.max_score ?? g.out_of ?? 100,
                                }))}>
                                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                                  <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                                  <YAxis tick={{ fontSize: 11 }} />
                                  <RechartsTooltip contentStyle={{ borderRadius: 8, fontSize: 12 }} />
                                  <Bar dataKey="score" name={isRTL ? 'الدرجة' : 'Score'} radius={[4, 4, 0, 0]}>
                                    {subjectGrades.map((g, idx) => {
                                      const score = g.score ?? g.grade ?? g.marks ?? 0;
                                      const total = g.total ?? g.max_score ?? g.out_of ?? 100;
                                      const pct = total > 0 ? (score / total) * 100 : 0;
                                      return <Cell key={idx} fill={pct >= 80 ? '#22c55e' : pct >= 60 ? '#f59e0b' : '#ef4444'} />;
                                    })}
                                  </Bar>
                                </BarChart>
                              </ResponsiveContainer>
                            </div>
                          </div>
                        )}
                        {!homeworkRate && subjectGrades.length === 0 && (
                          <EmptyState icon={BarChart3} message={isRTL ? 'لا توجد درجات مسجلة بعد' : 'No grades recorded yet'} />
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* AI Analysis */}
                <Card>
                  <CardContent className="p-6 space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="font-bold text-base font-cairo flex items-center gap-2">
                        <Brain className="h-5 w-5 text-brand-purple" />
                        {isRTL ? 'التحليل الذكي' : 'AI Analysis'}
                      </h3>
                      <Button variant="ghost" size="sm" onClick={fetchRiskData} className="text-xs">
                        <Activity className="h-3.5 w-3.5 me-1" /> {isRTL ? 'تحديث' : 'Refresh'}
                      </Button>
                    </div>
                    {loadingRisk ? (
                      <div className="space-y-3">
                        <Skeleton className="h-24 rounded-xl" />
                        <div className="grid grid-cols-4 gap-3">
                          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-20 rounded-xl" />)}
                        </div>
                      </div>
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
                      <EmptyState icon={Brain} message={isRTL ? 'لا تتوفر بيانات تحليلية حالياً' : 'No analytics available yet'} />
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              {/* ===== TALENTS TAB ===== */}
              <TabsContent value="talents" className="mt-6 space-y-4">
                {/* Talent Badges Section */}
                <Card>
                  <CardContent className="p-6 space-y-6">
                    <div className="flex items-center justify-between">
                      <h3 className="font-bold text-base font-cairo flex items-center gap-2">
                        <Sparkles className="h-5 w-5 text-brand-turquoise" />
                        {isRTL ? 'المواهب والمهارات' : 'Talents & Skills'}
                      </h3>
                      {student?.is_gifted && (
                        <Badge className="bg-gradient-to-r from-yellow-400 to-amber-500 text-white border-0 px-3 py-1 font-cairo">
                          <Trophy className="h-3.5 w-3.5 me-1" />
                          {isRTL ? 'طالب موهوب' : 'Gifted Student'}
                        </Badge>
                      )}
                    </div>

                    <div>
                      <Label className="text-sm font-cairo mb-3 block text-muted-foreground">{isRTL ? 'المواهب الحالية' : 'Current Talents'}</Label>
                      {(student?.talents?.length > 0) ? (
                        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                          {student.talents.map(t => {
                            const opt = TALENT_OPTIONS.find(o => o.value === t);
                            return (
                              <div key={t} className={`relative p-3 rounded-xl border text-center transition-all hover:shadow-sm ${opt?.color || 'bg-gray-50 text-gray-700 border-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-600'}`}>
                                <button onClick={() => handleRemoveTalent(t)} disabled={savingTalent}
                                  className="absolute top-1.5 end-1.5 hover:text-red-500 transition-colors rounded-full p-0.5 opacity-50 hover:opacity-100">
                                  <XCircle className="h-3.5 w-3.5" />
                                </button>
                                <Star className="h-5 w-5 mx-auto mb-1.5 fill-current opacity-60" />
                                <p className="text-sm font-cairo font-medium">{opt ? (isRTL ? opt.ar : opt.en) : t}</p>
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <EmptyState icon={Sparkles} message={isRTL ? 'لم يتم تحديد مواهب بعد' : 'No talents selected yet'} />
                      )}
                    </div>

                    <div>
                      <Label className="text-sm font-cairo mb-3 block text-muted-foreground">{isRTL ? 'إضافة موهبة' : 'Add Talent'}</Label>
                      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                        {TALENT_OPTIONS.filter(o => !(student?.talents || []).includes(o.value)).map(opt => (
                          <Button key={opt.value} variant="outline" size="sm" disabled={savingTalent} onClick={() => handleAddTalent(opt.value)}
                            className={`text-xs font-cairo justify-start gap-1.5 ${opt.color}`}>
                            <Plus className="h-3 w-3" />
                            {isRTL ? opt.ar : opt.en}
                          </Button>
                        ))}
                      </div>
                    </div>

                    {globalTalents.length > 0 && (
                      <div>
                        <Label className="text-sm font-cairo mb-3 block text-muted-foreground">{isRTL ? 'مواهب المدرسة' : 'School Talents'}</Label>
                        <div className="flex flex-wrap gap-2">
                          {globalTalents.filter(gt => !(student?.talents || []).includes(gt.value) && !TALENT_OPTIONS.some(o => o.value === gt.value)).map(gt => (
                            <Button key={gt.id} variant="outline" size="sm" disabled={savingTalent} onClick={() => handleAddTalent(gt.value)} className="text-xs font-cairo gap-1.5">
                              <Plus className="h-3 w-3" /> {isRTL ? gt.name_ar : (gt.name_en || gt.name_ar)}
                            </Button>
                          ))}
                        </div>
                      </div>
                    )}

                    <div>
                      <Label className="text-sm font-cairo mb-2 block text-muted-foreground">{isRTL ? 'إضافة موهبة مخصصة' : 'Add Custom Talent'}</Label>
                      <div className="flex gap-2">
                        <Input value={customTalentName} onChange={e => setCustomTalentName(e.target.value)}
                          placeholder={isRTL ? 'اكتب اسم الموهبة...' : 'Type talent name...'} className="flex-1 text-sm font-cairo"
                          onKeyDown={e => e.key === 'Enter' && handleAddCustomTalent()} />
                        <Button size="sm" disabled={addingCustomTalent || !customTalentName.trim()} onClick={handleAddCustomTalent} className="bg-brand-turquoise hover:bg-brand-turquoise/90 text-white">
                          {addingCustomTalent ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                        </Button>
                      </div>
                    </div>

                    {loadingGlobalTalents && (
                      <div className="flex justify-center py-4"><Loader2 className="h-6 w-6 animate-spin text-brand-turquoise" /></div>
                    )}
                  </CardContent>
                </Card>

                {/* Skills Radar Chart */}
                <Card>
                  <CardContent className="p-6">
                    <h3 className="font-bold text-base font-cairo flex items-center gap-2 mb-4">
                      <Target className="h-5 w-5 text-brand-purple" />
                      {isRTL ? 'خريطة المهارات' : 'Skills Radar'}
                    </h3>
                    {(student?.talents?.length > 0) ? (
                      <div className="h-72">
                        <ResponsiveContainer width="100%" height="100%">
                          <RadarChart cx="50%" cy="50%" outerRadius="75%" data={radarChartData}>
                            <PolarGrid strokeDasharray="3 3" />
                            <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 11, fontFamily: 'Cairo' }} />
                            <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 9 }} />
                            <Radar name={isRTL ? 'المهارات' : 'Skills'} dataKey="value" stroke="#46C1BE" fill="#46C1BE" fillOpacity={0.3} strokeWidth={2} />
                          </RadarChart>
                        </ResponsiveContainer>
                      </div>
                    ) : (
                      <EmptyState icon={Target} message={isRTL ? 'أضف مواهب لعرض خريطة المهارات' : 'Add talents to see skills radar'} />
                    )}
                  </CardContent>
                </Card>

                {/* Future Career Affinity */}
                <Card className="border-brand-purple/20 bg-gradient-to-r from-brand-purple/5 to-brand-navy/5 dark:from-brand-purple/10 dark:to-brand-navy/10">
                  <CardContent className="p-6">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="font-bold text-base font-cairo flex items-center gap-2">
                        <Rocket className="h-5 w-5 text-brand-purple" />
                        {isRTL ? 'مؤشرات المسار المهني' : 'Career Affinity Indicators'}
                      </h3>
                      <Badge variant="outline" className="text-[10px] border-dashed text-muted-foreground">
                        {isRTL ? 'مؤشرات أولية' : 'Early Indicators'}
                      </Badge>
                    </div>
                    {(student?.talents?.length > 0) ? (
                      <div className="space-y-3">
                        <div className="flex flex-wrap gap-2">
                          {student.talents.map(t => CAREER_AFFINITY_MAP[t]).filter(Boolean).filter((v, i, a) => a.findIndex(x => x.en === v.en) === i).map((career, i) => (
                            <Badge key={i} className="bg-brand-purple/10 text-brand-purple border-brand-purple/20 px-3 py-1.5 font-cairo">
                              <GraduationCap className="h-3.5 w-3.5 me-1.5" />
                              {isRTL ? career.ar : career.en}
                            </Badge>
                          ))}
                        </div>
                        <p className="text-[11px] text-muted-foreground font-cairo flex items-center gap-1.5 mt-2 p-2 bg-muted/30 rounded-lg">
                          <Brain className="h-3.5 w-3.5 text-brand-purple shrink-0" />
                          {isRTL ? 'مؤشرات أولية — ليست نهائية. هذا القسم سيعمل بالذكاء الاصطناعي في إصدار مستقبلي.' : 'Early Indicators — Not Final. This section will be AI-powered in a future version.'}
                        </p>
                      </div>
                    ) : (
                      <EmptyState icon={Rocket} message={isRTL ? 'أضف مواهب لعرض مؤشرات المسار المهني' : 'Add talents to see career affinity'} />
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              {/* ===== BEHAVIOUR TAB ===== */}
              <TabsContent value="behaviour" className="mt-6 space-y-4">
                {/* Summary Counter Cards */}
                {behaviourSummary && (
                  <div className="grid grid-cols-3 gap-3">
                    {[
                      { icon: ThumbsUp, value: behaviourSummary.positive_count || 0, label: isRTL ? 'إيجابي' : 'Positive', color: 'text-green-500', bg: 'bg-green-50 dark:bg-green-950/20', border: 'border-green-200 dark:border-green-800' },
                      { icon: ThumbsDown, value: behaviourSummary.negative_count || 0, label: isRTL ? 'سلبي' : 'Negative', color: 'text-red-500', bg: 'bg-red-50 dark:bg-red-950/20', border: 'border-red-200 dark:border-red-800' },
                      { icon: MessageSquare, value: behaviourSummary.total_records || behaviourRecords.length, label: isRTL ? 'إجمالي السجلات' : 'Total Records', color: 'text-blue-500', bg: 'bg-blue-50 dark:bg-blue-950/20', border: 'border-blue-200 dark:border-blue-800' },
                    ].map((s, i) => (
                      <Card key={i} className={`${s.border} ${s.bg}`}>
                        <CardContent className="p-4 text-center">
                          <s.icon className={`h-5 w-5 mx-auto mb-1 ${s.color}`} />
                          <div className={`text-2xl font-bold font-cairo ${s.color}`}>{s.value}</div>
                          <p className="text-xs text-muted-foreground font-cairo">{s.label}</p>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}

                {/* Behavior Trend Chart */}
                {behaviourTrendData.length > 0 && (
                  <Card>
                    <CardContent className="p-6">
                      <h3 className="font-bold text-base font-cairo flex items-center gap-2 mb-4">
                        <BarChart3 className="h-5 w-5 text-brand-navy" />
                        {isRTL ? 'اتجاه السلوك الشهري' : 'Monthly Behavior Trend'}
                      </h3>
                      <div className="h-52">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={behaviourTrendData} barGap={4}>
                            <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                            <XAxis dataKey="month" tick={{ fontSize: 11 }} tickFormatter={v => v.substring(5)} />
                            <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                            <RechartsTooltip contentStyle={{ borderRadius: 8, fontSize: 12 }} />
                            <Bar dataKey="positive" name={isRTL ? 'إيجابي' : 'Positive'} fill="#22c55e" radius={[4, 4, 0, 0]} />
                            <Bar dataKey="negative" name={isRTL ? 'سلبي' : 'Negative'} fill="#ef4444" radius={[4, 4, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Behavior Log */}
                <Card>
                  <CardContent className="p-6 space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="font-bold text-base font-cairo flex items-center gap-2">
                        <Activity className="h-5 w-5 text-brand-navy" />
                        {isRTL ? 'سجل السلوك' : 'Behavior Log'}
                      </h3>
                      <Button size="sm" onClick={() => openBehaviourModal()} className="bg-brand-navy hover:bg-brand-navy/90 text-white gap-1 font-cairo">
                        <Plus className="h-4 w-4" /> {isRTL ? 'إضافة سجل' : 'Add Record'}
                      </Button>
                    </div>

                    {loadingBehaviour ? (
                      <div className="space-y-3">
                        {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}
                      </div>
                    ) : behaviourRecords.length === 0 ? (
                      <EmptyState icon={Activity} message={isRTL ? 'لا توجد سجلات سلوكية بعد' : 'No behavior records yet'} actionLabel={isRTL ? 'إضافة سجل' : 'Add Record'} onAction={() => openBehaviourModal()} />
                    ) : (
                      <>
                        <div className="space-y-3">
                          {paginatedBehaviourRecords.map(rec => {
                            const catColors = {
                              positive: 'border-s-green-500 bg-green-50/50 dark:bg-green-900/10',
                              negative: 'border-s-red-500 bg-red-50/50 dark:bg-red-900/10',
                              neutral: 'border-s-gray-400 bg-gray-50/50 dark:bg-gray-900/10'
                            };
                            const catIcons = { positive: ThumbsUp, negative: ThumbsDown, neutral: MessageSquare };
                            const CatIcon = catIcons[rec.category] || MessageSquare;
                            const severityColors = {
                              minor: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
                              moderate: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300',
                              major: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300',
                              severe: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300',
                            };
                            const statusColors = {
                              pending: 'bg-yellow-100 text-yellow-700',
                              reviewed: 'bg-blue-100 text-blue-700',
                              escalated: 'bg-red-100 text-red-700',
                              resolved: 'bg-green-100 text-green-700',
                              archived: 'bg-gray-100 text-gray-700',
                            };
                            return (
                              <Card key={rec.id} className={`border-s-4 ${catColors[rec.category] || catColors.neutral}`}>
                                <CardContent className="p-4">
                                  <div className="flex items-start justify-between gap-3">
                                    <div className="flex-1 min-w-0">
                                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                                        <CatIcon className={`h-4 w-4 flex-shrink-0 ${rec.category === 'positive' ? 'text-green-500' : rec.category === 'negative' ? 'text-red-500' : 'text-gray-400'}`} />
                                        <span className="font-semibold text-sm font-cairo truncate">{rec.title}</span>
                                        {rec.points != null && (
                                          <Badge variant="outline" className={`text-xs ${rec.points > 0 ? 'text-green-600 border-green-300' : rec.points < 0 ? 'text-red-600 border-red-300' : 'text-gray-500 border-gray-300'}`}>
                                            {rec.points > 0 ? '+' : ''}{rec.points}
                                          </Badge>
                                        )}
                                        {rec.severity && <Badge className={`text-xs ${severityColors[rec.severity] || ''}`}>{rec.severity}</Badge>}
                                        {rec.status && <Badge className={`text-xs ${statusColors[rec.status] || ''}`}>{rec.status}</Badge>}
                                      </div>
                                      {rec.description && <p className="text-xs text-muted-foreground font-cairo mt-1 line-clamp-2">{rec.description}</p>}
                                      <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                                        <span className="flex items-center gap-1"><Calendar className="h-3 w-3" />{rec.incident_date || rec.created_at?.split('T')[0]}</span>
                                        {rec.reported_by_name && <span className="flex items-center gap-1"><User className="h-3 w-3" />{rec.reported_by_name}</span>}
                                      </div>
                                    </div>
                                    <div className="flex items-center gap-1 flex-shrink-0">
                                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openBehaviourModal(rec)}>
                                        <Edit className="h-3.5 w-3.5" />
                                      </Button>
                                      {!isTeacher && (
                                        <Button variant="ghost" size="icon" className="h-7 w-7 text-red-500 hover:text-red-700" onClick={() => handleDeleteBehaviour(rec)}>
                                          <Trash2 className="h-3.5 w-3.5" />
                                        </Button>
                                      )}
                                    </div>
                                  </div>
                                </CardContent>
                              </Card>
                            );
                          })}
                        </div>
                        {behaviourTotalPages > 1 && (
                          <div className="flex items-center justify-center gap-2 pt-2">
                            <Button variant="outline" size="sm" disabled={behaviourPage <= 1} onClick={() => setBehaviourPage(p => p - 1)} className="font-cairo">
                              {isRTL ? <ArrowRight className="h-4 w-4" /> : <ArrowLeft className="h-4 w-4" />}
                            </Button>
                            <span className="text-sm text-muted-foreground font-cairo tabular-nums">{behaviourPage} / {behaviourTotalPages}</span>
                            <Button variant="outline" size="sm" disabled={behaviourPage >= behaviourTotalPages} onClick={() => setBehaviourPage(p => p + 1)} className="font-cairo">
                              {isRTL ? <ArrowLeft className="h-4 w-4" /> : <ArrowRight className="h-4 w-4" />}
                            </Button>
                          </div>
                        )}
                      </>
                    )}
                  </CardContent>
                </Card>

                {/* Character Traits Section */}
                <Card>
                  <CardContent className="p-6 space-y-4">
                    <h3 className="font-bold text-base font-cairo flex items-center gap-2">
                      <Heart className="h-5 w-5 text-rose-500" />
                      {isRTL ? 'السمات الشخصية' : 'Character Traits'}
                    </h3>
                    <p className="text-xs text-muted-foreground font-cairo">
                      {isRTL ? 'سمات إيجابية يضيفها المعلمون لوصف شخصية الطالب' : 'Positive personality tags added by teachers to describe the student'}
                    </p>

                    {(student?.character_traits?.length > 0) ? (
                      <div className="flex flex-wrap gap-2">
                        {student.character_traits.map(trait => (
                          <Badge key={trait} className="bg-gradient-to-r from-rose-50 to-purple-50 dark:from-rose-950/20 dark:to-purple-950/20 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800 px-3 py-1.5 font-cairo text-sm">
                            {trait}
                            <button onClick={() => handleRemoveCharacterTrait(trait)} disabled={savingCharacterTrait}
                              className="ms-1.5 hover:text-red-500 transition-colors">
                              <XCircle className="h-3.5 w-3.5" />
                            </button>
                          </Badge>
                        ))}
                      </div>
                    ) : (
                      <EmptyState icon={Heart} message={isRTL ? 'لم يتم إضافة سمات شخصية بعد' : 'No character traits added yet'} />
                    )}

                    <div>
                      <Label className="text-sm font-cairo mb-2 block text-muted-foreground">{isRTL ? 'إضافة سمة' : 'Add Trait'}</Label>
                      <div className="flex flex-wrap gap-1.5 mb-3">
                        {CHARACTER_TRAIT_OPTIONS
                          .filter(opt => !(student?.character_traits || []).includes(isRTL ? opt.ar : opt.en))
                          .map(opt => (
                            <Button key={opt.en} variant="outline" size="sm" disabled={savingCharacterTrait}
                              onClick={() => handleAddCharacterTrait(isRTL ? opt.ar : opt.en)}
                              className="text-xs font-cairo gap-1 h-7 px-2.5 hover:bg-rose-50 hover:border-rose-200 dark:hover:bg-rose-950/20">
                              <Plus className="h-3 w-3" /> {isRTL ? opt.ar : opt.en}
                            </Button>
                          ))}
                      </div>
                      <div className="flex gap-2">
                        <Input value={newCharacterTrait} onChange={e => setNewCharacterTrait(e.target.value)}
                          placeholder={isRTL ? 'أو اكتب سمة مخصصة...' : 'Or type a custom trait...'}
                          className="flex-1 text-sm font-cairo"
                          onKeyDown={e => e.key === 'Enter' && handleAddCharacterTrait(newCharacterTrait)} />
                        <Button size="sm" disabled={savingCharacterTrait || !newCharacterTrait.trim()}
                          onClick={() => handleAddCharacterTrait(newCharacterTrait)}
                          className="bg-rose-500 hover:bg-rose-600 text-white">
                          {savingCharacterTrait ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              {/* ===== ACTIVITIES TAB ===== */}
              <TabsContent value="activities" className="mt-6 space-y-4">
                {/* Involvement Score */}
                <Card className="bg-gradient-to-r from-brand-turquoise/5 to-brand-navy/5 dark:from-brand-turquoise/10 dark:to-brand-navy/10 border-brand-turquoise/20">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-bold text-sm font-cairo flex items-center gap-2">
                        <Zap className="h-4 w-4 text-brand-turquoise" />
                        {isRTL ? 'مؤشر المشاركة اللاصفية' : 'Extracurricular Involvement'}
                      </h3>
                      <Badge className={`${involvementScore.color} text-white border-0 text-xs font-cairo`}>{involvementScore.label}</Badge>
                    </div>
                    <Progress value={involvementScore.percent} className="h-2" />
                    <p className="text-[11px] text-muted-foreground mt-1.5 font-cairo">
                      {isRTL ? `${activities.length} أنشطة · ${certificates.length} شهادات/جوائز` : `${activities.length} activities · ${certificates.length} certificates/awards`}
                    </p>
                  </CardContent>
                </Card>

                {/* Activities List */}
                <Card>
                  <CardContent className="p-6 space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="font-bold text-base font-cairo flex items-center gap-2">
                        <Medal className="h-5 w-5 text-brand-navy" />
                        {isRTL ? 'الأنشطة' : 'Activities'}
                      </h3>
                      {(user?.role === 'school_admin' || user?.role === 'admin' || user?.role === 'super_admin' || isTeacher) && (
                        <Button size="sm" onClick={() => openActivityModal()} className="bg-brand-navy hover:bg-brand-navy/90 text-white gap-1 font-cairo">
                          <Plus className="h-4 w-4" /> {isRTL ? 'إضافة نشاط' : 'Add Activity'}
                        </Button>
                      )}
                    </div>
                    {loadingActivities ? (
                      <div className="space-y-3">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-20 rounded-xl" />)}</div>
                    ) : activities.length === 0 ? (
                      <EmptyState icon={Medal} message={isRTL ? 'لا توجد أنشطة مسجلة بعد' : 'No activities recorded yet'} actionLabel={isRTL ? 'إضافة نشاط' : 'Add Activity'} onAction={() => openActivityModal()} />
                    ) : (
                      <div className="space-y-2">
                        {activities.map(act => {
                          const typeOpt = ACTIVITY_TYPE_OPTIONS.find(o => o.value === act.activity_type) || ACTIVITY_TYPE_OPTIONS[6];
                          return (
                            <div key={act.id} className="flex items-center gap-3 p-3 rounded-xl border hover:shadow-sm transition-all">
                              <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-lg flex-shrink-0 border ${typeOpt.color}`}>
                                {typeOpt.icon}
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="font-semibold text-sm font-cairo truncate">{act.name}</span>
                                  <Badge variant="outline" className={`text-[10px] ${typeOpt.color}`}>{isRTL ? typeOpt.ar : typeOpt.en}</Badge>
                                </div>
                                <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                                  {act.date && <span className="flex items-center gap-1"><Calendar className="h-3 w-3" />{act.date}</span>}
                                  {act.role && <span className="flex items-center gap-1"><User className="h-3 w-3" />{act.role}</span>}
                                </div>
                              </div>
                              <div className="flex items-center gap-1 flex-shrink-0">
                                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openActivityModal(act)}><Edit className="h-3.5 w-3.5" /></Button>
                                {(user?.role === 'school_admin' || user?.role === 'admin' || user?.role === 'super_admin') && (
                                  <Button variant="ghost" size="icon" className="h-7 w-7 text-red-500 hover:text-red-700" onClick={() => handleDeleteActivity(act)}><Trash2 className="h-3.5 w-3.5" /></Button>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Certificates & Awards */}
                <Card>
                  <CardContent className="p-6 space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="font-bold text-base font-cairo flex items-center gap-2">
                        <Trophy className="h-5 w-5 text-amber-500" />
                        {isRTL ? 'الشهادات والجوائز' : 'Certificates & Awards'}
                      </h3>
                      {(user?.role === 'school_admin' || user?.role === 'admin' || user?.role === 'super_admin' || isTeacher) && (
                        <Button size="sm" onClick={() => openCertificateModal()} className="bg-amber-500 hover:bg-amber-600 text-white gap-1 font-cairo">
                          <Plus className="h-4 w-4" /> {isRTL ? 'إضافة شهادة' : 'Add Certificate'}
                        </Button>
                      )}
                    </div>
                    {loadingActivities ? (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">{[...Array(2)].map((_, i) => <Skeleton key={i} className="h-32 rounded-xl" />)}</div>
                    ) : certificates.length === 0 ? (
                      <EmptyState icon={Trophy} message={isRTL ? 'لا توجد شهادات أو جوائز بعد' : 'No certificates or awards yet'} actionLabel={isRTL ? 'إضافة شهادة' : 'Add Certificate'} onAction={() => openCertificateModal()} />
                    ) : (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {certificates.map(cert => (
                          <Card key={cert.id} className="border-amber-200/50 dark:border-amber-800/30 bg-gradient-to-br from-amber-50/50 to-yellow-50/30 dark:from-amber-950/10 dark:to-yellow-950/10 overflow-hidden">
                            <CardContent className="p-4">
                              <div className="flex items-start justify-between gap-2">
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2 mb-1">
                                    <div className="w-8 h-8 rounded-lg bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center flex-shrink-0">
                                      <Trophy className="h-4 w-4 text-amber-600" />
                                    </div>
                                    <h4 className="font-semibold text-sm font-cairo truncate">{cert.title}</h4>
                                  </div>
                                  {cert.issuing_body && <p className="text-xs text-muted-foreground font-cairo mt-1 flex items-center gap-1"><GraduationCap className="h-3 w-3" />{cert.issuing_body}</p>}
                                  {cert.description && <p className="text-xs text-muted-foreground font-cairo mt-1 line-clamp-2">{cert.description}</p>}
                                  {cert.date && <p className="text-[11px] text-muted-foreground font-cairo mt-2 flex items-center gap-1"><Calendar className="h-3 w-3" />{cert.date}</p>}
                                </div>
                                <div className="flex flex-col gap-1 flex-shrink-0">
                                  <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openCertificateModal(cert)}><Edit className="h-3.5 w-3.5" /></Button>
                                  {(user?.role === 'school_admin' || user?.role === 'admin' || user?.role === 'super_admin') && (
                                    <Button variant="ghost" size="icon" className="h-7 w-7 text-red-500 hover:text-red-700" onClick={() => handleDeleteCertificate(cert)}><Trash2 className="h-3.5 w-3.5" /></Button>
                                  )}
                                </div>
                              </div>
                            </CardContent>
                          </Card>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              {/* ===== PLANS TAB ===== */}
              <TabsContent value="plans" className="mt-6 space-y-4">
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

                {/* Plan History Log */}
                <Card>
                  <CardContent className="p-6 space-y-3">
                    <h3 className="font-bold text-base font-cairo flex items-center gap-2">
                      <Clock className="h-5 w-5 text-brand-purple" />
                      {isRTL ? 'سجل الخطط السابقة' : 'Plan History Log'}
                    </h3>
                    {loadingPlanHistory ? (
                      <div className="space-y-2">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-14 rounded-xl" />)}</div>
                    ) : planHistory.length === 0 ? (
                      <EmptyState icon={Clock} message={isRTL ? 'لا يوجد سجل خطط سابقة بعد' : 'No plan history yet'} />
                    ) : (
                      <div className="space-y-2">
                        {planHistory.map((entry, i) => {
                          const hasRemedial = !!entry.plans?.remedial_plan;
                          const hasEnrichment = !!entry.plans?.enrichment_plan;
                          return (
                            <div key={entry.id || i} className="flex items-center gap-3 p-3 rounded-xl border hover:bg-muted/20 transition-colors">
                              <div className="w-8 h-8 rounded-lg bg-brand-purple/10 flex items-center justify-center flex-shrink-0">
                                <FileText className="h-4 w-4 text-brand-purple" />
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 flex-wrap">
                                  {hasRemedial && <Badge variant="outline" className="text-[10px] border-rose-200 text-rose-600 dark:border-rose-800 dark:text-rose-400">{isRTL ? 'علاجية' : 'Remedial'}</Badge>}
                                  {hasEnrichment && <Badge variant="outline" className="text-[10px] border-emerald-200 text-emerald-600 dark:border-emerald-800 dark:text-emerald-400">{isRTL ? 'إثرائية' : 'Enrichment'}</Badge>}
                                  <Badge variant="outline" className="text-[10px]">{entry.plan_source === 'ai' ? 'AI' : isRTL ? 'افتراضي' : 'Fallback'}</Badge>
                                </div>
                                <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                                  <span className="flex items-center gap-1"><Calendar className="h-3 w-3" />{entry.generated_at?.split('T')[0]}</span>
                                  {entry.generated_by_name && <span className="flex items-center gap-1"><User className="h-3 w-3" />{entry.generated_by_name}</span>}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              {/* ===== LONGITUDINAL RECORD TAB ===== */}
              <TabsContent value="longitudinal" className="mt-6 space-y-6">
                {loadingLongitudinal ? (
                  <div className="space-y-4">{[...Array(4)].map((_, i) => <Skeleton key={i} className="h-32 rounded-xl" />)}</div>
                ) : !longitudinalData ? (
                  <Card><CardContent className="p-6"><EmptyState icon={ScrollText} message={isRTL ? 'لا توجد بيانات تراكمية' : 'No longitudinal data available'} /></CardContent></Card>
                ) : (
                  <>
                    {/* Student Journey Timeline */}
                    <Card className="border-0 shadow-md dark:bg-gray-900/50">
                      <CardContent className="p-6">
                        <h3 className="font-bold text-lg font-cairo flex items-center gap-2 mb-6">
                          <Layers className="h-5 w-5 text-brand-navy" />
                          {isRTL ? 'المسيرة الدراسية' : 'Student Journey Timeline'}
                        </h3>
                        <div className="relative">
                          <div className={`absolute ${isRTL ? 'right-4' : 'left-4'} top-0 bottom-0 w-0.5 bg-gradient-to-b from-brand-navy via-brand-turquoise to-brand-purple`} />
                          <div className="space-y-6">
                            {(longitudinalData.timeline || []).map((entry, idx) => (
                              <div key={entry.year} className={`relative ${isRTL ? 'pr-12' : 'pl-12'}`}>
                                <div className={`absolute ${isRTL ? 'right-1' : 'left-1'} top-2 w-7 h-7 rounded-full bg-gradient-to-br from-brand-navy to-brand-turquoise flex items-center justify-center text-white text-xs font-bold shadow-lg z-10`}>
                                  {idx + 1}
                                </div>
                                <Card className={`border transition-all hover:shadow-md ${idx === (longitudinalData.timeline || []).length - 1 ? 'ring-2 ring-brand-turquoise/40' : ''}`}>
                                  <CardContent className="p-4">
                                    <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
                                      <div className="flex items-center gap-2">
                                        <Badge className="bg-brand-navy/10 text-brand-navy border-brand-navy/20 font-bold">{entry.academic_year}</Badge>
                                        {entry.grade && <Badge variant="outline" className="font-cairo text-xs">{entry.grade}</Badge>}
                                        {entry.class_name && <span className="text-xs text-muted-foreground font-cairo">{entry.class_name}</span>}
                                      </div>
                                      {idx === (longitudinalData.timeline || []).length - 1 && (
                                        <Badge className="bg-brand-turquoise/10 text-brand-turquoise border-brand-turquoise/20 text-xs">{isRTL ? 'الحالي' : 'Current'}</Badge>
                                      )}
                                    </div>
                                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                                      <div className="text-center p-2 rounded-lg bg-blue-50 dark:bg-blue-950/20">
                                        <div className="text-lg font-bold text-blue-600">{entry.attendance_rate}%</div>
                                        <div className="text-[10px] text-muted-foreground font-cairo">{isRTL ? 'الحضور' : 'Attendance'}</div>
                                      </div>
                                      <div className="text-center p-2 rounded-lg bg-purple-50 dark:bg-purple-950/20">
                                        <div className="text-lg font-bold text-purple-600">{entry.academic_average}%</div>
                                        <div className="text-[10px] text-muted-foreground font-cairo">{isRTL ? 'المعدل' : 'Average'}</div>
                                      </div>
                                      <div className="text-center p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/20">
                                        <div className="text-lg font-bold text-emerald-600">{entry.behaviour_positive}</div>
                                        <div className="text-[10px] text-muted-foreground font-cairo">{isRTL ? 'سلوك إيجابي' : 'Positive'}</div>
                                      </div>
                                      <div className="text-center p-2 rounded-lg bg-rose-50 dark:bg-rose-950/20">
                                        <div className="text-lg font-bold text-rose-600">{entry.behaviour_negative}</div>
                                        <div className="text-[10px] text-muted-foreground font-cairo">{isRTL ? 'سلوك سلبي' : 'Negative'}</div>
                                      </div>
                                    </div>
                                    {entry.top_talents?.length > 0 && (
                                      <div className="mt-3 flex items-center gap-1.5 flex-wrap">
                                        <Sparkles className="h-3.5 w-3.5 text-amber-500" />
                                        {entry.top_talents.map((t, ti) => {
                                          const opt = TALENT_OPTIONS.find(o => o.value === t);
                                          return <Badge key={ti} variant="outline" className={`text-[10px] px-1.5 py-0 ${opt?.color || ''}`}>{isRTL ? (opt?.ar || t) : (opt?.en || t)}</Badge>;
                                        })}
                                      </div>
                                    )}
                                    {entry.achievements?.length > 0 && (
                                      <div className="mt-2 flex items-center gap-1.5 flex-wrap">
                                        <Trophy className="h-3.5 w-3.5 text-amber-500" />
                                        {entry.achievements.slice(0, 3).map((a, ai) => (
                                          <span key={ai} className="text-[11px] text-muted-foreground font-cairo bg-amber-50 dark:bg-amber-950/20 px-2 py-0.5 rounded-full">{a}</span>
                                        ))}
                                      </div>
                                    )}
                                  </CardContent>
                                </Card>
                              </div>
                            ))}
                          </div>
                        </div>
                      </CardContent>
                    </Card>

                    {/* Skill Growth Tracker */}
                    {longitudinalData.skill_growth?.length > 0 && (
                      <Card className="border-0 shadow-md dark:bg-gray-900/50">
                        <CardContent className="p-6">
                          <h3 className="font-bold text-lg font-cairo flex items-center gap-2 mb-4">
                            <TrendingUp className="h-5 w-5 text-brand-turquoise" />
                            {isRTL ? 'تطور المهارات' : 'Skill Growth Tracker'}
                          </h3>
                          <div className="h-72">
                            <ResponsiveContainer width="100%" height="100%">
                              <LineChart data={(() => {
                                const allYears = new Set();
                                longitudinalData.skill_growth.forEach(s => s.data.forEach(d => allYears.add(d.year)));
                                const years = [...allYears].sort();
                                return years.map(year => {
                                  const point = { year };
                                  longitudinalData.skill_growth.forEach(s => {
                                    const found = s.data.find(d => d.year === year);
                                    point[s.skill] = found ? found.level : null;
                                  });
                                  return point;
                                });
                              })()}>
                                <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                                <XAxis dataKey="year" />
                                <YAxis domain={[0, 5]} />
                                <RechartsTooltip />
                                <Legend />
                                {longitudinalData.skill_growth.map((s, i) => {
                                  const colors = ['#1C3D74', '#46C1BE', '#615090', '#E14D2A', '#10B981', '#F59E0B', '#EC4899'];
                                  return <Line key={s.skill} type="monotone" dataKey={s.skill} stroke={colors[i % colors.length]} strokeWidth={2} dot={{ r: 4 }} connectNulls />;
                                })}
                              </LineChart>
                            </ResponsiveContainer>
                          </div>
                        </CardContent>
                      </Card>
                    )}

                    {/* Readiness Indicators */}
                    <Card className="border-0 shadow-md dark:bg-gray-900/50">
                      <CardContent className="p-6">
                        <h3 className="font-bold text-lg font-cairo flex items-center gap-2 mb-2">
                          <Target className="h-5 w-5 text-brand-purple" />
                          {isRTL ? 'مؤشرات الاستعداد' : 'Readiness Indicators'}
                        </h3>
                        <p className="text-xs text-muted-foreground font-cairo mb-5 bg-amber-50 dark:bg-amber-950/20 p-2 rounded-lg border border-amber-200 dark:border-amber-800">
                          {isRTL
                            ? 'هذه المؤشرات مبنية على البيانات التراكمية وستكون مدعومة بالذكاء الاصطناعي في إصدار مستقبلي من نَسَّق.'
                            : 'These indicators are based on cumulative data and will be AI-powered in a future version of NASSAQ.'}
                        </p>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                          {[
                            { key: 'academic', icon: GraduationCap, label_ar: 'الاستعداد الأكاديمي', label_en: 'Academic Readiness', emoji: '🎓', color: 'blue' },
                            { key: 'social_emotional', icon: Heart, label_ar: 'الاستعداد الاجتماعي-العاطفي', label_en: 'Social-Emotional Readiness', emoji: '🤝', color: 'emerald' },
                            { key: 'leadership', icon: Crown, label_ar: 'إمكانات القيادة', label_en: 'Leadership Potential', emoji: '👑', color: 'amber' },
                            { key: 'career_alignment', icon: Briefcase, label_ar: 'التوافق المهني', label_en: 'Career Alignment', emoji: '💼', color: 'purple' },
                          ].map(indicator => {
                            const score = longitudinalData.readiness?.[indicator.key] || 0;
                            const colorMap = { blue: 'bg-blue-500', emerald: 'bg-emerald-500', amber: 'bg-amber-500', purple: 'bg-purple-500' };
                            const bgMap = { blue: 'bg-blue-50 dark:bg-blue-950/20', emerald: 'bg-emerald-50 dark:bg-emerald-950/20', amber: 'bg-amber-50 dark:bg-amber-950/20', purple: 'bg-purple-50 dark:bg-purple-950/20' };
                            return (
                              <div key={indicator.key} className={`p-4 rounded-xl border ${bgMap[indicator.color]}`}>
                                <div className="flex items-center gap-2 mb-3">
                                  <span className="text-xl">{indicator.emoji}</span>
                                  <span className="font-semibold text-sm font-cairo">{isRTL ? indicator.label_ar : indicator.label_en}</span>
                                </div>
                                <div className="flex items-center gap-3">
                                  <div className="flex-1">
                                    <Progress value={score} className="h-3" />
                                  </div>
                                  <span className="font-bold text-lg min-w-[3rem] text-end">{score}%</span>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </CardContent>
                    </Card>

                    {/* Career Clusters */}
                    <Card className="border-0 shadow-md dark:bg-gray-900/50">
                      <CardContent className="p-6">
                        <h3 className="font-bold text-lg font-cairo flex items-center gap-2 mb-2">
                          <Briefcase className="h-5 w-5 text-brand-navy" />
                          {isRTL ? 'المجالات المهنية المقترحة' : 'Career Clusters'}
                        </h3>
                        <p className="text-xs text-muted-foreground font-cairo mb-5 bg-blue-50 dark:bg-blue-950/20 p-2 rounded-lg border border-blue-200 dark:border-blue-800">
                          {isRTL ? 'مؤشرات مبكرة للميول المهنية — تتحسن مع تراكم البيانات' : 'Early career affinity indicators — data builds over time'}
                        </p>
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                          {(longitudinalData.career_clusters || []).map((cluster, idx) => {
                            const clusterColors = ['from-blue-500 to-cyan-500', 'from-purple-500 to-pink-500', 'from-amber-500 to-orange-500'];
                            const clusterBgs = ['bg-blue-50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-800', 'bg-purple-50 dark:bg-purple-950/20 border-purple-200 dark:border-purple-800', 'bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800'];
                            return (
                              <div key={idx} className={`p-4 rounded-xl border ${clusterBgs[idx % 3]} relative overflow-hidden`}>
                                <div className={`absolute top-0 ${isRTL ? 'right-0' : 'left-0'} w-1 h-full bg-gradient-to-b ${clusterColors[idx % 3]}`} />
                                <div className="flex items-center justify-between mb-2">
                                  <h4 className="font-bold text-sm font-cairo">{isRTL ? cluster.name_ar : cluster.name_en}</h4>
                                  <Badge className={`bg-gradient-to-r ${clusterColors[idx % 3]} text-white border-0 text-xs`}>{cluster.match}%</Badge>
                                </div>
                                <Progress value={cluster.match} className="h-2 mb-2" />
                                <p className="text-[11px] text-muted-foreground font-cairo leading-relaxed">
                                  {isRTL ? cluster.reason_ar : cluster.reason_en}
                                </p>
                              </div>
                            );
                          })}
                        </div>
                      </CardContent>
                    </Card>

                    {/* Vision Statement Banner */}
                    <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-brand-navy via-brand-purple to-brand-navy p-6 text-center">
                      <div className="absolute inset-0 nassaq-pattern opacity-5" />
                      <div className="relative z-10">
                        <Sparkles className="h-8 w-8 text-brand-turquoise mx-auto mb-3" />
                        <p className="text-white/90 font-cairo text-sm leading-relaxed max-w-2xl mx-auto">
                          {isRTL
                            ? 'كل نقطة بيانات يتم تسجيلها اليوم تبني مستقبل هذا الطالب. السجل التراكمي في نَسَّق سيدعم توصيات مهنية مدعومة بالذكاء الاصطناعي في المستقبل.'
                            : "Every data point recorded today is building this student's future. NASSAQ's longitudinal record will power AI-driven career recommendations in the future."}
                        </p>
                      </div>
                    </div>
                  </>
                )}
              </TabsContent>

            </Tabs>
          </div>
        </div>
      </main>

      {/* ===== EDIT PROFILE MODAL ===== */}
      <Dialog open={editProfileOpen} onOpenChange={(open) => { setEditProfileOpen(open); if (!open) setFormData({ ...student }); }}>
        <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto" dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader>
            <DialogTitle className="font-cairo flex items-center gap-2">
              <Edit className="h-5 w-5 text-brand-turquoise" />
              {isRTL ? 'تعديل بيانات الطالب' : 'Edit Student Profile'}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-6 py-2">
            <div>
              <h4 className="font-semibold text-sm font-cairo flex items-center gap-2 mb-4">
                <User className="h-4 w-4 text-brand-turquoise" />
                {isRTL ? 'البيانات الشخصية' : 'Personal Information'}
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label className="text-xs font-cairo">{isRTL ? 'الاسم الكامل' : 'Full Name'}</Label>
                  <Input value={formData.full_name || ''} onChange={(e) => setFormData({ ...formData, full_name: e.target.value })} />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-cairo">{isRTL ? 'رقم الهوية' : 'National ID'}</Label>
                  <Input value={formData.national_id || ''} onChange={(e) => setFormData({ ...formData, national_id: e.target.value })} />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-cairo">{isRTL ? 'البريد الإلكتروني' : 'Email'}</Label>
                  <Input value={formData.email || ''} onChange={(e) => setFormData({ ...formData, email: e.target.value })} />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-cairo">{isRTL ? 'الهاتف' : 'Phone'}</Label>
                  <Input value={formData.phone || ''} onChange={(e) => setFormData({ ...formData, phone: e.target.value })} />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-cairo">{isRTL ? 'الجنس' : 'Gender'}</Label>
                  <Select value={formData.gender || ''} onValueChange={(v) => setFormData({ ...formData, gender: v })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="male">{isRTL ? 'ذكر' : 'Male'}</SelectItem>
                      <SelectItem value="female">{isRTL ? 'أنثى' : 'Female'}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-cairo">{isRTL ? 'تاريخ الميلاد' : 'Date of Birth'}</Label>
                  <Input type="date" value={formData.date_of_birth || ''} onChange={(e) => setFormData({ ...formData, date_of_birth: e.target.value })} />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-cairo">{isRTL ? 'الصف' : 'Grade'}</Label>
                  <Input value={formData.grade || ''} onChange={(e) => setFormData({ ...formData, grade: e.target.value })} />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-cairo">{isRTL ? 'الفصل' : 'Class'}</Label>
                  <Select value={formData.class_id || ''} onValueChange={(v) => setFormData({ ...formData, class_id: v })}>
                    <SelectTrigger><SelectValue placeholder={isRTL ? 'اختر الفصل' : 'Select Class'} /></SelectTrigger>
                    <SelectContent>
                      {classes.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>

            <div className="border-t pt-4">
              <h4 className="font-semibold text-sm font-cairo flex items-center gap-2 mb-4">
                <Heart className="h-4 w-4 text-rose-500" />
                {isRTL ? 'بيانات ولي الأمر' : 'Guardian Information'}
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label className="text-xs font-cairo">{isRTL ? 'اسم ولي الأمر' : 'Guardian Name'}</Label>
                  <Input value={formData.parent_name || ''} onChange={(e) => setFormData({ ...formData, parent_name: e.target.value })} />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-cairo">{isRTL ? 'صلة القرابة' : 'Relationship'}</Label>
                  <Select value={formData.parent_relationship || ''} onValueChange={(v) => setFormData({ ...formData, parent_relationship: v })}>
                    <SelectTrigger><SelectValue placeholder={isRTL ? 'اختر صلة القرابة' : 'Select'} /></SelectTrigger>
                    <SelectContent>
                      {Object.entries({ father: isRTL ? 'أب' : 'Father', mother: isRTL ? 'أم' : 'Mother', guardian: isRTL ? 'ولي أمر' : 'Guardian', brother: isRTL ? 'أخ' : 'Brother', sister: isRTL ? 'أخت' : 'Sister', uncle: isRTL ? 'عم / خال' : 'Uncle', other: isRTL ? 'أخرى' : 'Other' }).map(([k, v]) => (
                        <SelectItem key={k} value={k}>{v}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-cairo">{isRTL ? 'هاتف ولي الأمر' : 'Guardian Phone'}</Label>
                  <Input value={formData.parent_phone || ''} onChange={(e) => setFormData({ ...formData, parent_phone: e.target.value })} />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-cairo">{isRTL ? 'بريد ولي الأمر' : 'Guardian Email'}</Label>
                  <Input type="email" value={formData.parent_email || ''} onChange={(e) => setFormData({ ...formData, parent_email: e.target.value })} />
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t">
              <Button variant="outline" onClick={() => setEditProfileOpen(false)} className="font-cairo">{isRTL ? 'إلغاء' : 'Cancel'}</Button>
              <Button onClick={handleSave} disabled={saving} className="bg-brand-navy hover:bg-brand-navy/90 text-white font-cairo gap-1.5">
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                {isRTL ? 'حفظ التعديلات' : 'Save Changes'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* ===== BEHAVIOUR MODAL ===== */}
      <Dialog open={behaviourModalOpen} onOpenChange={setBehaviourModalOpen}>
        <DialogContent className="sm:max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader>
            <DialogTitle className="font-cairo">{editingBehaviour ? (isRTL ? 'تعديل سجل السلوك' : 'Edit Behavior Record') : (isRTL ? 'إضافة سجل سلوك' : 'Add Behavior Record')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label className="font-cairo text-sm">{isRTL ? 'نوع السلوك' : 'Behavior Type'}</Label>
              <Select value={behaviourForm.behaviour_type_id} onValueChange={v => {
                const bt = behaviourTypes.find(bt => bt.id === v);
                setBehaviourForm(prev => ({
                  ...prev,
                  behaviour_type_id: v,
                  title: isRTL ? (bt?.name_ar || prev.title) : (bt?.name_en || bt?.name_ar || prev.title),
                  category: bt?.category || prev.category,
                }));
              }}>
                <SelectTrigger className="mt-1"><SelectValue placeholder={isRTL ? 'اختر النوع...' : 'Select type...'} /></SelectTrigger>
                <SelectContent>
                  {behaviourTypes.map(bt => {
                    const pts = bt.default_points ?? bt.points;
                    return (
                      <SelectItem key={bt.id} value={bt.id}>
                        <span className="font-cairo">{bt.name_ar || bt.name_en}</span>
                        {pts != null && <span className={`mr-2 text-xs ${pts > 0 ? 'text-green-600' : pts < 0 ? 'text-red-600' : ''}`}> ({pts > 0 ? '+' : ''}{pts})</span>}
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="font-cairo text-sm">{isRTL ? 'التصنيف' : 'Category'}</Label>
              <Select value={behaviourForm.category} onValueChange={v => setBehaviourForm(prev => ({ ...prev, category: v }))}>
                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="positive"><span className="font-cairo text-green-600">{isRTL ? 'إيجابي' : 'Positive'}</span></SelectItem>
                  <SelectItem value="negative"><span className="font-cairo text-red-600">{isRTL ? 'سلبي' : 'Negative'}</span></SelectItem>
                  <SelectItem value="neutral"><span className="font-cairo text-gray-500">{isRTL ? 'محايد' : 'Neutral'}</span></SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="font-cairo text-sm">{isRTL ? 'العنوان' : 'Title'}</Label>
              <Input value={behaviourForm.title} onChange={e => setBehaviourForm(prev => ({ ...prev, title: e.target.value }))} className="mt-1 font-cairo" placeholder={isRTL ? 'عنوان السلوك...' : 'Behavior title...'} />
            </div>
            <div>
              <Label className="font-cairo text-sm">{isRTL ? 'الوصف' : 'Description'}</Label>
              <Textarea value={behaviourForm.description} onChange={e => setBehaviourForm(prev => ({ ...prev, description: e.target.value }))} className="mt-1 font-cairo" rows={3} placeholder={isRTL ? 'تفاصيل إضافية...' : 'Additional details...'} />
            </div>
            <div>
              <Label className="font-cairo text-sm">{isRTL ? 'تاريخ الحادثة' : 'Incident Date'}</Label>
              <Input type="date" value={behaviourForm.incident_date} onChange={e => setBehaviourForm(prev => ({ ...prev, incident_date: e.target.value }))} className="mt-1" />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setBehaviourModalOpen(false)} className="font-cairo">{isRTL ? 'إلغاء' : 'Cancel'}</Button>
              <Button onClick={handleSaveBehaviour} disabled={savingBehaviour} className="bg-brand-navy hover:bg-brand-navy/90 text-white font-cairo gap-1">
                {savingBehaviour ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                {editingBehaviour ? (isRTL ? 'تحديث' : 'Update') : (isRTL ? 'حفظ' : 'Save')}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* ===== EXPORT PLAN MODAL ===== */}
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

            <Button className="w-full gap-2 bg-brand-navy hover:bg-brand-navy/90 text-white" onClick={() => handleExportPlan(exportPlanType, exportFormat)} disabled={exportingPlan}>
              {exportingPlan ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              {isRTL ? 'تحميل' : 'Download'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* ===== ACTIVITY MODAL ===== */}
      <Dialog open={activityModalOpen} onOpenChange={setActivityModalOpen}>
        <DialogContent className="sm:max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader>
            <DialogTitle className="font-cairo flex items-center gap-2">
              <Medal className="h-5 w-5 text-brand-navy" />
              {editingActivity ? (isRTL ? 'تعديل النشاط' : 'Edit Activity') : (isRTL ? 'إضافة نشاط' : 'Add Activity')}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label className="font-cairo text-sm">{isRTL ? 'اسم النشاط' : 'Activity Name'} *</Label>
              <Input value={activityForm.name} onChange={e => setActivityForm(prev => ({ ...prev, name: e.target.value }))} className="mt-1 font-cairo" placeholder={isRTL ? 'مثال: مسابقة الرياضيات' : 'e.g. Math Competition'} />
            </div>
            <div>
              <Label className="font-cairo text-sm">{isRTL ? 'نوع النشاط' : 'Activity Type'}</Label>
              <Select value={activityForm.activity_type} onValueChange={v => setActivityForm(prev => ({ ...prev, activity_type: v }))}>
                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {ACTIVITY_TYPE_OPTIONS.map(opt => (
                    <SelectItem key={opt.value} value={opt.value}><span className="font-cairo">{opt.icon} {isRTL ? opt.ar : opt.en}</span></SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="font-cairo text-sm">{isRTL ? 'التاريخ' : 'Date'}</Label>
                <Input type="date" value={activityForm.date} onChange={e => setActivityForm(prev => ({ ...prev, date: e.target.value }))} className="mt-1" />
              </div>
              <div>
                <Label className="font-cairo text-sm">{isRTL ? 'الدور / المركز' : 'Role / Position'}</Label>
                <Input value={activityForm.role} onChange={e => setActivityForm(prev => ({ ...prev, role: e.target.value }))} className="mt-1 font-cairo" placeholder={isRTL ? 'مثال: مشارك' : 'e.g. Participant'} />
              </div>
            </div>
            <div>
              <Label className="font-cairo text-sm">{isRTL ? 'وصف' : 'Description'}</Label>
              <Textarea value={activityForm.description} onChange={e => setActivityForm(prev => ({ ...prev, description: e.target.value }))} className="mt-1 font-cairo" rows={2} />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setActivityModalOpen(false)} className="font-cairo">{isRTL ? 'إلغاء' : 'Cancel'}</Button>
              <Button onClick={handleSaveActivity} disabled={savingActivity} className="bg-brand-navy hover:bg-brand-navy/90 text-white font-cairo gap-1.5">
                {savingActivity ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                {isRTL ? 'حفظ' : 'Save'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* ===== CERTIFICATE MODAL ===== */}
      <Dialog open={certificateModalOpen} onOpenChange={setCertificateModalOpen}>
        <DialogContent className="sm:max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader>
            <DialogTitle className="font-cairo flex items-center gap-2">
              <Trophy className="h-5 w-5 text-amber-500" />
              {editingCertificate ? (isRTL ? 'تعديل الشهادة' : 'Edit Certificate') : (isRTL ? 'إضافة شهادة / جائزة' : 'Add Certificate / Award')}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label className="font-cairo text-sm">{isRTL ? 'العنوان' : 'Title'} *</Label>
              <Input value={certificateForm.title} onChange={e => setCertificateForm(prev => ({ ...prev, title: e.target.value }))} className="mt-1 font-cairo" placeholder={isRTL ? 'مثال: شهادة تفوق' : 'e.g. Excellence Award'} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="font-cairo text-sm">{isRTL ? 'التاريخ' : 'Date'}</Label>
                <Input type="date" value={certificateForm.date} onChange={e => setCertificateForm(prev => ({ ...prev, date: e.target.value }))} className="mt-1" />
              </div>
              <div>
                <Label className="font-cairo text-sm">{isRTL ? 'الجهة المانحة' : 'Issuing Body'}</Label>
                <Input value={certificateForm.issuing_body} onChange={e => setCertificateForm(prev => ({ ...prev, issuing_body: e.target.value }))} className="mt-1 font-cairo" placeholder={isRTL ? 'مثال: وزارة التعليم' : 'e.g. Ministry of Education'} />
              </div>
            </div>
            <div>
              <Label className="font-cairo text-sm">{isRTL ? 'وصف' : 'Description'}</Label>
              <Textarea value={certificateForm.description} onChange={e => setCertificateForm(prev => ({ ...prev, description: e.target.value }))} className="mt-1 font-cairo" rows={2} />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" onClick={() => setCertificateModalOpen(false)} className="font-cairo">{isRTL ? 'إلغاء' : 'Cancel'}</Button>
              <Button onClick={handleSaveCertificate} disabled={savingCertificate} className="bg-amber-500 hover:bg-amber-600 text-white font-cairo gap-1.5">
                {savingCertificate ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                {isRTL ? 'حفظ' : 'Save'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* ===== FULL PROFILE EXPORT MODAL ===== */}
      <Dialog open={profileExportModalOpen} onOpenChange={setProfileExportModalOpen}>
        <DialogContent className="sm:max-w-lg" dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader>
            <DialogTitle className="font-cairo flex items-center gap-2">
              <Download className="h-5 w-5 text-brand-navy" />
              {isRTL ? 'تصدير الملف الشامل' : 'Export Full Profile'}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-5 pt-2">
            <div className="space-y-2">
              <Label className="text-sm font-medium font-cairo">{isRTL ? 'اختر الأقسام المطلوبة' : 'Select sections to include'}</Label>
              <div className="space-y-2">
                {[
                  { key: 'personal', icon: User, label_ar: 'المعلومات الشخصية وولي الأمر', label_en: 'Personal & Guardian Info' },
                  { key: 'academic', icon: BarChart3, label_ar: 'الأداء الأكاديمي', label_en: 'Academic Performance' },
                  { key: 'talents', icon: Sparkles, label_ar: 'المواهب والمهارات', label_en: 'Talents & Skills' },
                  { key: 'behaviour', icon: Heart, label_ar: 'السلوك', label_en: 'Behavior Record' },
                  { key: 'activities', icon: Medal, label_ar: 'الأنشطة والإنجازات', label_en: 'Activities & Achievements' },
                  { key: 'plans', icon: ClipboardList, label_ar: 'الخطط العلاجية / الإثرائية', label_en: 'Plans (Remedial / Enrichment)' },
                  { key: 'longitudinal', icon: ScrollText, label_ar: 'السجل التراكمي', label_en: 'Longitudinal Summary' },
                ].map(sec => {
                  const Icon = sec.icon;
                  const checked = profileExportSections.includes(sec.key);
                  return (
                    <label key={sec.key} className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${checked ? 'border-brand-navy/30 bg-brand-navy/5 dark:border-brand-navy/50 dark:bg-brand-navy/10' : 'border-border hover:border-brand-navy/20'}`} onClick={() => toggleProfileSection(sec.key)}>
                      <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-all ${checked ? 'bg-brand-navy border-brand-navy' : 'border-gray-300 dark:border-gray-600'}`}>
                        {checked && <CheckSquare className="h-3.5 w-3.5 text-white" />}
                      </div>
                      <Icon className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                      <span className="text-sm font-medium font-cairo">{isRTL ? sec.label_ar : sec.label_en}</span>
                    </label>
                  );
                })}
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-sm font-medium font-cairo">{isRTL ? 'صيغة الملف' : 'File Format'}</Label>
              <RadioGroup value={profileExportFormat} onValueChange={setProfileExportFormat} className="grid grid-cols-2 gap-2">
                <label className={`flex flex-col items-center gap-1.5 p-3 rounded-xl border cursor-pointer transition-all ${profileExportFormat === 'pdf' ? 'border-red-300 bg-red-50/50 dark:border-red-700 dark:bg-red-950/20 ring-1 ring-red-200 dark:ring-red-800' : 'border-border hover:border-red-200'}`}>
                  <RadioGroupItem value="pdf" className="sr-only" />
                  <div className="w-10 h-10 rounded-lg bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
                    <span className="text-red-600 dark:text-red-400 font-bold text-xs">PDF</span>
                  </div>
                  <span className="text-xs font-medium">{isRTL ? 'ملف PDF' : 'PDF File'}</span>
                </label>
                <label className={`flex flex-col items-center gap-1.5 p-3 rounded-xl border cursor-pointer transition-all ${profileExportFormat === 'docx' ? 'border-blue-300 bg-blue-50/50 dark:border-blue-700 dark:bg-blue-950/20 ring-1 ring-blue-200 dark:ring-blue-800' : 'border-border hover:border-blue-200'}`}>
                  <RadioGroupItem value="docx" className="sr-only" />
                  <div className="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                    <span className="text-blue-600 dark:text-blue-400 font-bold text-xs">DOCX</span>
                  </div>
                  <span className="text-xs font-medium">{isRTL ? 'ملف Word' : 'Word File'}</span>
                </label>
              </RadioGroup>
            </div>

            <Button
              className="w-full gap-2 bg-brand-navy hover:bg-brand-navy/90 text-white"
              onClick={handleExportFullProfile}
              disabled={exportingProfile || profileExportSections.length === 0}
            >
              {exportingProfile ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              {isRTL ? 'إنشاء وتحميل' : 'Generate & Download'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
