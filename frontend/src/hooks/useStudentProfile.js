import { useState, useEffect, useMemo, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import { toast } from 'sonner';

export function useStudentProfile() {
  const { studentId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, api } = useAuth();
  const { isRTL, isDark, toggleTheme, toggleLanguage } = useTheme();
  const { t } = useTranslation();
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
    } catch (e) {
      console.error('Error loading student data:', e);
      nassaqError(t('errorLoadingStudentData'));
    } finally {
      setLoading(false);
    }
  }, [api, studentId, headers, isRTL, nassaqError]);

  useEffect(() => { fetchStudent(); }, [fetchStudent]);
  useEffect(() => { setOverviewLoaded(false); }, [studentId]);

  const fetchAttendance = useCallback(async () => {
    if (!studentId) return;
    setLoadingAttendance(true);
    try { const res = await api.get(`/attendance/summary/student/${studentId}`, { headers }); setAttendanceSummary(res.data); }
    catch (e) { console.error('Error fetching attendance:', e); setAttendanceSummary(null); }
    finally { setLoadingAttendance(false); }
  }, [api, studentId, headers]);

  const fetchRiskData = useCallback(async () => {
    if (!studentId) return;
    setLoadingRisk(true);
    try { const res = await api.get(`/hakim/student/${studentId}/risk?days=30`, { headers }); setRiskData(res.data?.data || res.data); }
    catch (e) { console.error('Error fetching risk data:', e); setRiskData(null); }
    finally { setLoadingRisk(false); }
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
      } else { setHomeworkRate(null); }
    } catch (e) { console.error('Error fetching homework rate:', e); setHomeworkRate(null); }
    finally { setLoadingHomework(false); }
  }, [api, studentId, headers]);

  const fetchBehaviourRecords = useCallback(async () => {
    if (!studentId || !tenantId) return;
    setLoadingBehaviour(true);
    try { const res = await api.get(`/behaviour-records/student/${studentId}?school_id=${tenantId}&limit=100`, { headers }); setBehaviourRecords(res.data?.records || []); setBehaviourSummary(res.data?.summary || null); }
    catch (e) { console.error('Error fetching behaviour records:', e); setBehaviourRecords([]); setBehaviourSummary(null); }
    finally { setLoadingBehaviour(false); }
  }, [api, studentId, tenantId, headers]);

  const fetchBehaviourTypes = useCallback(async () => {
    if (!tenantId) return;
    try { const res = await api.get(`/behaviour-types?school_id=${tenantId}`, { headers }); setBehaviourTypes(res.data?.behaviour_types || []); }
    catch (e) { console.error('Error fetching behaviour types:', e); setBehaviourTypes([]); }
  }, [api, tenantId, headers]);

  const fetchGlobalTalents = useCallback(async () => {
    setLoadingGlobalTalents(true);
    try { const res = await api.get('/talents', { headers }); setGlobalTalents(res.data?.talents || []); }
    catch (e) { console.error('Error fetching global talents:', e); setGlobalTalents([]); }
    finally { setLoadingGlobalTalents(false); }
  }, [api, headers]);

  const fetchAttendanceHistory = useCallback(async () => {
    if (!studentId) return;
    setLoadingAttendanceHistory(true);
    try { const res = await api.get(`/attendance/student/${studentId}`, { headers }); setAttendanceHistory(res.data?.records || []); }
    catch (e) { console.error('Error fetching attendance history:', e); setAttendanceHistory([]); }
    finally { setLoadingAttendanceHistory(false); }
  }, [api, studentId, headers]);

  const fetchGradesDetail = useCallback(async () => {
    if (!studentId) return;
    setLoadingGrades(true);
    try { const res = await api.get(`/grades/student/${studentId}`, { headers }); setGradesDetail(res.data); }
    catch (e) { console.error('Error fetching grades:', e); setGradesDetail(null); }
    finally { setLoadingGrades(false); }
  }, [api, studentId, headers]);

  const fetchClassDetail = useCallback(async () => {
    const cId = classId || student?.class_id;
    if (!cId) return;
    try { const res = await api.get(`/classes/${cId}`, { headers }); setClassDetail(res.data); }
    catch (e) { console.error('Error fetching class detail:', e); setClassDetail(null); }
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
    } catch (e) { console.error('[StudentProfile] fetchActivities failed:', e?.message); }
    setLoadingActivities(false);
  }, [studentId, tenantId]);

  const fetchLongitudinal = useCallback(async () => {
    if (!studentId) return;
    setLoadingLongitudinal(true);
    try { const res = await api.get(`/hakim/student/${studentId}/longitudinal`, { headers }); setLongitudinalData(res.data); }
    catch (e) { console.error('[StudentProfile] fetchLongitudinal failed:', e?.message); setLongitudinalData(null); }
    setLoadingLongitudinal(false);
  }, [studentId]);

  const fetchPlanHistory = useCallback(async () => {
    if (!studentId) return;
    setLoadingPlanHistory(true);
    try { const res = await api.get(`/hakim/student/${studentId}/plan-history`, { headers }); setPlanHistory(res.data || []); }
    catch (e) { console.error('[StudentProfile] fetchPlanHistory failed:', e?.message); }
    setLoadingPlanHistory(false);
  }, [studentId]);

  useEffect(() => {
    if (activeTab === 'overview' && !overviewLoaded && student) {
      fetchAttendance(); fetchHomeworkRate(); fetchBehaviourRecords(); fetchClassDetail(); setOverviewLoaded(true);
    } else if (activeTab === 'academic') {
      fetchAttendance(); fetchAttendanceHistory(); fetchRiskData(); fetchHomeworkRate(); fetchGradesDetail();
    } else if (activeTab === 'behaviour') { fetchBehaviourRecords(); fetchBehaviourTypes(); }
    else if (activeTab === 'talents') { fetchGlobalTalents(); }
    else if (activeTab === 'activities') { fetchActivities(); }
    else if (activeTab === 'plans') { fetchPlanHistory(); }
    else if (activeTab === 'longitudinal') { fetchLongitudinal(); }
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
        if (planType === 'remedial') { setPlanFn(plans.remedial_plan); if (!enrichmentPlan && plans.enrichment_plan) setEnrichmentPlan(plans.enrichment_plan); }
        else { setPlanFn(plans.enrichment_plan); if (!remedialPlan && plans.remedial_plan) setRemedialPlan(plans.remedial_plan); }
      }
      toast.success(t('planGeneratedByHakim'));
    } catch (e) { console.error('Error generating plan:', e); nassaqError(t('failedToGeneratePlan')); }
    finally { setLoadFn(false); }
  };

  const openExportModal = (planType) => {
  setExportPlanType(planType || 'both'); setExportFormat('pdf'); setExportModalOpen(true); };

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
      if (res.data.type === 'application/json') { const text = await res.data.text(); const errData = JSON.parse(text); throw new Error(errData.detail || 'Export failed'); }
      const blob = new Blob([res.data], { type: mimeType });
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      const safeName = (student?.full_name || 'student').replace(/\s+/g, '_');
      const date = new Date().toISOString().split('T')[0];
      const suffix = planType === 'remedial' ? 'Remedial_Plan' : planType === 'enrichment' ? 'Enrichment_Plan' : 'Plans';
      a.href = blobUrl; a.download = `${safeName}_${suffix}_${date}.${ext}`;
      document.body.appendChild(a); a.click(); window.URL.revokeObjectURL(blobUrl); a.remove();
      toast.success(t('planExportedSuccessfully'));
      setExportModalOpen(false);
    } catch (err) {
      let detail = err?.message || '';
      if (err?.response?.data instanceof Blob) { try { const text = await err.response.data.text(); const parsed = JSON.parse(text); detail = parsed.detail || detail; } catch (_) {} }
      else if (err?.response?.data?.detail) { detail = err.response.data.detail; }
      nassaqError(isRTL ? `فشل تصدير الخطة: ${detail || 'خطأ غير معروف'}` : `Failed to export plan: ${detail || 'Unknown error'}`);
    } finally { setExportingPlan(false); }
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
      const response = await fetch(`${api.defaults.baseURL}${url}`, { method: 'POST', headers: { ...headers, 'Content-Type': 'application/json' }, body: JSON.stringify({ sections: profileExportSections }) });
      if (!response.ok) { const errData = await response.json().catch(() => ({})); throw new Error(errData.detail || 'Export failed'); }
      const blob = await response.blob();
      const link = document.createElement('a'); link.href = URL.createObjectURL(blob);
      const ext = isPdf ? 'pdf' : 'docx';
      link.download = `NASSAQ_Profile_${student?.full_name || 'student'}.${ext}`;
      document.body.appendChild(link); link.click(); document.body.removeChild(link); URL.revokeObjectURL(link.href);
      toast.success(t('fullProfileExportedSuccessfully'));
      setProfileExportModalOpen(false);
    } catch (err) { nassaqError(isRTL ? `فشل التصدير: ${err.message}` : `Export failed: ${err.message}`); }
    setExportingProfile(false);
  };

  const toggleProfileSection = (section) => {
    setProfileExportSections(prev => prev.includes(section) ? prev.filter(s => s !== section) : [...prev, section]);
  };

  const openActivityModal = (act = null) => {
    setEditingActivity(act);
    setActivityForm(act ? { name: act.name || '', name_en: act.name_en || '', activity_type: act.activity_type || 'academic', date: act.date || '', role: act.role || '', description: act.description || '' }
      : { name: '', name_en: '', activity_type: 'academic', date: new Date().toISOString().split('T')[0], role: '', description: '' });
    setActivityModalOpen(true);
  };

  const handleSaveActivity = async () => {
    if (!activityForm.name.trim()) return nassaqError(t('pleaseEnterActivityName'));
    setSavingActivity(true);
    try {
      if (editingActivity) { await api.put(`/activities/${editingActivity.id}`, activityForm, { headers }); }
      else { await api.post(`/activities/student/${studentId}?school_id=${tenantId}`, activityForm, { headers }); }
      toast.success(t('activitySaved'));
      setActivityModalOpen(false); fetchActivities();
    } catch (e) { console.error('Error saving activity:', e); nassaqError(t('failedToSaveActivity')); }
    setSavingActivity(false);
  };

  const handleDeleteActivity = async (act) => {
    const ok = await nassaqConfirm(t('deleteThisActivity'));
    if (!ok) return;
    try { await api.delete(`/activities/${act.id}`, { headers }); toast.success(t('activityDeleted')); fetchActivities(); }
    catch (e) { console.error('Error deleting activity:', e); nassaqError(t('failedToDeleteActivity')); }
  };

  const openCertificateModal = (cert = null) => {
    setEditingCertificate(cert);
    setCertificateForm(cert ? { title: cert.title || '', title_en: cert.title_en || '', date: cert.date || '', issuing_body: cert.issuing_body || '', description: cert.description || '' }
      : { title: '', title_en: '', date: new Date().toISOString().split('T')[0], issuing_body: '', description: '' });
    setCertificateModalOpen(true);
  };

  const handleSaveCertificate = async () => {
    if (!certificateForm.title.trim()) return nassaqError(t('pleaseEnterCertificateTitle'));
    setSavingCertificate(true);
    try {
      if (editingCertificate) { await api.put(`/activities/certificates/${editingCertificate.id}`, certificateForm, { headers }); }
      else { await api.post(`/activities/certificates/student/${studentId}?school_id=${tenantId}`, certificateForm, { headers }); }
      toast.success(t('certificateSaved'));
      setCertificateModalOpen(false); fetchActivities();
    } catch (e) { console.error('Error saving certificate:', e); nassaqError(t('failedToSaveCertificate')); }
    setSavingCertificate(false);
  };

  const handleDeleteCertificate = async (cert) => {
    const ok = await nassaqConfirm(t('deleteThisCertificate'));
    if (!ok) return;
    try { await api.delete(`/activities/certificates/${cert.id}`, { headers }); toast.success(t('certificateDeleted')); fetchActivities(); }
    catch (e) { console.error('Error deleting certificate:', e); nassaqError(t('failedToDeleteCertificate')); }
  };

  const involvementScore = useMemo(() => {
    const total = activities.length + certificates.length;
    if (total === 0) return { level: 'low', label: t('low'), percent: 5, color: 'bg-gray-400' };
    if (total <= 2) return { level: 'moderate', label: isRTL ? 'متوسط' : 'Moderate', percent: 35, color: 'bg-yellow-500' };
    if (total <= 5) return { level: 'active', label: t('active'), percent: 65, color: 'bg-green-500' };
    return { level: 'highly_active', label: t('highlyActive'), percent: 90, color: 'bg-emerald-500' };
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
      if (currentTalents !== originalTalents) updateData.talents = formData.talents || [];
      if (Object.keys(updateData).length === 0) { nassaqWarning(t('noChangesToSave')); setSaving(false); return; }
      await api.put(`/students/${student.id}`, updateData, { headers });
      toast.success(t('studentDataSavedSuccessfully'));
      setEditProfileOpen(false); fetchStudent();
    } catch (error) {
      const msg = error.response?.data?.detail;
      nassaqError(typeof msg === 'string' ? msg : (t('saveFailed')));
    } finally { setSaving(false); }
  };

  const handleAction = async (action) => {
    setActionLoading(action);
    try {
      switch (action) {
        case 'suspend': await api.put(`/principal/student/${student.id}/status`, { status: 'suspended' }, { headers }); toast.success(t('accountSuspended')); break;
        case 'activate': await api.put(`/principal/student/${student.id}/status`, { status: 'active' }, { headers }); toast.success(t('accountActivated')); break;
        case 'reset-password': {
          const genRes = await api.post('/principal/generate-password', {}, { headers });
          const tempPass = genRes.data.password;
          await api.put(`/principal/student/${student.id}/credentials`, { new_password: tempPass }, { headers });
          toast.success(isRTL ? `تم إعادة تعيين كلمة المرور إلى: ${tempPass}` : `Password reset to: ${tempPass}`); break;
        }
        case 'delete':
          nassaqConfirm(t('areYouSureYouWantToDeleteThisAccountThisCannotBeUn'),
            async () => {
              try { await api.delete(`/students/${student.id}`, { headers }); toast.success(t('accountDeleted')); handleBack(); }
              catch (e) { console.error('Error deleting account:', e); nassaqError(t('failedToDeleteAccount')); }
            }, { title: t('confirmDelete'), confirmText: t('yesDelete'), cancelText: t('cancel') }
          );
          setActionLoading(''); return;
        default: break;
      }
      fetchStudent();
    } catch (error) {
      const msg = error.response?.data?.detail;
      nassaqError(typeof msg === 'string' ? msg : (isRTL ? 'فشلت العملية' : 'Operation failed'));
    } finally { setActionLoading(''); }
  };

  const openBehaviourModal = (record = null) => {
    if (record) {
      setEditingBehaviour(record);
      setBehaviourForm({ category: record.category || 'positive', title: record.title || '', description: record.description || '', incident_date: record.incident_date || new Date().toISOString().split('T')[0], behaviour_type_id: record.behaviour_type_id || '' });
    } else {
      setEditingBehaviour(null);
      setBehaviourForm({ category: 'positive', title: '', description: '', incident_date: new Date().toISOString().split('T')[0], behaviour_type_id: '' });
    }
    setBehaviourModalOpen(true);
  };

  const handleSaveBehaviour = async () => {
    if (!behaviourForm.title.trim()) { nassaqError(t('pleaseEnterABehaviorTitle')); return; }
    if (!behaviourForm.behaviour_type_id) { nassaqError(t('pleaseSelectABehaviorType')); return; }
    setSavingBehaviour(true);
    try {
      if (editingBehaviour) {
        await api.put(`/behaviour-records/${editingBehaviour.id}?force=true`, { title: behaviourForm.title, description: behaviourForm.description, incident_date: behaviourForm.incident_date, category: behaviourForm.category, behaviour_type_id: behaviourForm.behaviour_type_id }, { headers });
        toast.success(t('recordUpdatedSuccessfully'));
      } else {
        await api.post(`/behaviour-records?school_id=${tenantId}`, { student_id: studentId, behaviour_type_id: behaviourForm.behaviour_type_id, title: behaviourForm.title, description: behaviourForm.description, incident_date: behaviourForm.incident_date, category: behaviourForm.category }, { headers });
        toast.success(t('recordAddedSuccessfully'));
      }
      setBehaviourModalOpen(false); fetchBehaviourRecords();
    } catch (err) {
      const msg = err.response?.data?.detail;
      nassaqError(typeof msg === 'string' ? msg : (isRTL ? 'فشلت العملية' : 'Operation failed'));
    } finally { setSavingBehaviour(false); }
  };

  const handleDeleteBehaviour = (record) => {
    nassaqConfirm(t('areYouSureYouWantToDeleteThisRecord'),
      async () => {
        try { await api.delete(`/behaviour-records/${record.id}`, { headers }); toast.success(t('recordDeleted')); fetchBehaviourRecords(); }
        catch (e) { console.error('Error deleting record:', e); nassaqError(t('failedToDeleteRecord')); }
      }, { title: t('confirmDelete'), confirmText: t('yesDelete'), cancelText: t('cancel') }
    );
  };

  const handleAddTalent = async (talentValue) => {
    if (!student || !talentValue) return;
    const currentTalents = student.talents || [];
    if (currentTalents.includes(talentValue)) return;
    setSavingTalent(true);
    try { const newTalents = [...currentTalents, talentValue]; await api.put(`/students/${student.id}`, { talents: newTalents }, { headers }); toast.success(t('talentAdded')); fetchStudent(); }
    catch (err) { const msg = err.response?.data?.detail; nassaqError(typeof msg === 'string' ? msg : (t('failedToAddTalent'))); }
    finally { setSavingTalent(false); }
  };

  const handleRemoveTalent = async (talentValue) => {
    if (!student) return;
    const newTalents = (student.talents || []).filter(t => t !== talentValue);
    setSavingTalent(true);
    try { await api.put(`/students/${student.id}`, { talents: newTalents }, { headers }); toast.success(t('talentRemoved')); fetchStudent(); }
    catch (e) { console.error('Error removing talent:', e); nassaqError(t('failedToRemoveTalent')); }
    finally { setSavingTalent(false); }
  };

  const handleAddCustomTalent = async () => {
    if (!customTalentName.trim()) return;
    setAddingCustomTalent(true);
    try {
      const res = await api.post('/talents', { name_ar: customTalentName.trim(), name_en: customTalentName.trim() }, { headers });
      const newTalent = res.data;
      setCustomTalentName(''); fetchGlobalTalents();
      await handleAddTalent(newTalent.value || newTalent.name_ar);
    } catch (err) { const msg = err.response?.data?.detail; nassaqError(typeof msg === 'string' ? msg : (t('failedToAddCustomTalent'))); }
    finally { setAddingCustomTalent(false); }
  };

  const handleAddCharacterTrait = async (trait) => {
    if (!student || !trait.trim()) return;
    const current = student.character_traits || [];
    if (current.includes(trait.trim())) return;
    setSavingCharacterTrait(true);
    try { await api.put(`/students/${student.id}`, { character_traits: [...current, trait.trim()] }, { headers }); toast.success(t('traitAdded')); fetchStudent(); setNewCharacterTrait(''); }
    catch (e) { console.error('Error adding trait:', e); nassaqError(isRTL ? 'فشلت الإضافة' : 'Failed to add trait'); }
    finally { setSavingCharacterTrait(false); }
  };

  const handleRemoveCharacterTrait = async (trait) => {
    if (!student) return;
    const current = student.character_traits || [];
    setSavingCharacterTrait(true);
    try { await api.put(`/students/${student.id}`, { character_traits: current.filter(t => t !== trait) }, { headers }); toast.success(t('traitRemoved')); fetchStudent(); }
    catch (e) { console.error('Error removing trait:', e); nassaqError(isRTL ? 'فشلت الإزالة' : 'Failed to remove trait'); }
    finally { setSavingCharacterTrait(false); }
  };

  const classObj = classes.find(c => c.id === student?.class_id);
  const resolvedClassName = classObj?.name || classNameFromState || student?.class_name;
  const resolvedClassId = classId || student?.class_id;

  const handleBack = () => {
    if (fromPath) navigate(fromPath);
    else if (resolvedClassId) navigate(`${rolePrefix}/classes/${resolvedClassId}`);
    else navigate(`${rolePrefix}/users-management?filter=students`);
  };

  const getRiskColor = (c) => { const map = { critical: 'bg-red-100 text-red-700 border-red-200', high: 'bg-orange-100 text-orange-700 border-orange-200', medium: 'bg-yellow-100 text-yellow-700 border-yellow-200', low: 'bg-green-100 text-green-700 border-green-200' }; return map[c] || 'bg-gray-100 text-gray-700 border-gray-200'; };
  const getRiskLabel = (c) => { const map = { critical: t('critical'), high: t('high'), medium: t('medium'), low: t('low') }; return map[c] || c; };
  const getRiskBarColor = (c) => { const map = { critical: '[&>div]:bg-red-500', high: '[&>div]:bg-orange-500', medium: '[&>div]:bg-yellow-500', low: '[&>div]:bg-green-500' }; return map[c] || '[&>div]:bg-gray-400'; };

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
      { key: 'full_name', ar: 'الاسم الكامل', en: 'Full Name' }, { key: 'national_id', ar: 'رقم الهوية', en: 'National ID' },
      { key: 'email', ar: 'البريد الإلكتروني', en: 'Email' }, { key: 'phone', ar: 'الهاتف', en: 'Phone' },
      { key: 'gender', ar: 'الجنس', en: 'Gender' }, { key: 'date_of_birth', ar: 'تاريخ الميلاد', en: 'Date of Birth' },
      { key: 'nationality', ar: 'الجنسية', en: 'Nationality' }, { key: 'parent_name', ar: 'اسم ولي الأمر', en: 'Guardian Name' },
      { key: 'parent_phone', ar: 'هاتف ولي الأمر', en: 'Guardian Phone' }, { key: 'emergency_contact', ar: 'جهة اتصال الطوارئ', en: 'Emergency Contact' },
      { key: 'emergency_phone', ar: 'هاتف الطوارئ', en: 'Emergency Phone' },
    ];
    const filled = fields.filter(f => { const v = student[f.key]; return v !== null && v !== undefined && v !== ''; });
    const missing = fields.filter(f => { const v = student[f.key]; return v === null || v === undefined || v === ''; });
    return { percent: Math.round((filled.length / fields.length) * 100), missing };
  }, [student]);

  const attendanceChartData = useMemo(() => {
    if (!attendanceHistory || attendanceHistory.length === 0) return [];
    const monthly = {};
    attendanceHistory.forEach(r => {
      const d = r.date || r.attendance_date; if (!d) return;
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
    return Array.isArray(grades) ? grades : [];
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
      const d = r.incident_date || r.created_at?.split('T')[0] || ''; if (!d) return;
      const month = d.substring(0, 7);
      if (!monthly[month]) monthly[month] = { month, positive: 0, negative: 0 };
      if (r.category === 'positive') monthly[month].positive++;
      else if (r.category === 'negative') monthly[month].negative++;
    });
    return Object.values(monthly).sort((a, b) => a.month.localeCompare(b.month));
  }, [behaviourRecords]);

  const BEHAVIOUR_PAGE_SIZE = 10;
  const behaviourTotalPages = Math.max(1, Math.ceil(behaviourRecords.length / BEHAVIOUR_PAGE_SIZE));
  useEffect(() => { setBehaviourPage(p => Math.min(p, Math.max(1, Math.ceil(behaviourRecords.length / BEHAVIOUR_PAGE_SIZE)))); }, [behaviourRecords.length]);
  const paginatedBehaviourRecords = useMemo(() => {
    const start = (behaviourPage - 1) * BEHAVIOUR_PAGE_SIZE;
    return behaviourRecords.slice(start, start + BEHAVIOUR_PAGE_SIZE);
  }, [behaviourRecords, behaviourPage]);

  const CAREER_AFFINITY_MAP = {
    academically_gifted: { ar: 'البحث العلمي', en: 'Research' }, scientific: { ar: 'الهندسة والطب', en: 'Engineering & Medicine' },
    artistic: { ar: 'الفنون والتصميم', en: 'Arts & Design' }, musical: { ar: 'الموسيقى والأداء', en: 'Music & Performance' },
    literary: { ar: 'الكتابة والإعلام', en: 'Writing & Media' }, athletic: { ar: 'الرياضة والتدريب', en: 'Sports & Coaching' },
    technological: { ar: 'التقنية والبرمجة', en: 'Technology & Programming' }, leadership: { ar: 'الإدارة والقيادة', en: 'Management & Leadership' },
  };

  const CHARACTER_TRAIT_OPTIONS = [
    { ar: 'مسؤول', en: 'Responsible' }, { ar: 'متعاطف', en: 'Empathetic' }, { ar: 'مبدع', en: 'Creative' },
    { ar: 'قيادي', en: 'Leader' }, { ar: 'مثابر', en: 'Persistent' }, { ar: 'فضولي', en: 'Curious' },
    { ar: 'متعاون', en: 'Collaborative' }, { ar: 'منضبط', en: 'Disciplined' }, { ar: 'صادق', en: 'Honest' },
    { ar: 'متفائل', en: 'Optimistic' }, { ar: 'محترم', en: 'Respectful' }, { ar: 'كريم', en: 'Generous' },
  ];

  return {
    studentId, navigate, user, isRTL, isDark, toggleTheme, toggleLanguage, nassaqConfirm, nassaqError, nassaqWarning,
    classNameFromState, rolePrefix, isTeacher, headers,
    student, loading, saving, formData, setFormData, activeTab, setActiveTab, classes,
    editProfileOpen, setEditProfileOpen,
    attendanceSummary, loadingAttendance, homeworkRate, loadingHomework,
    riskData, loadingRisk, remedialPlan, enrichmentPlan, loadingRemedial, loadingEnrichment,
    exportingPlan, exportModalOpen, setExportModalOpen, exportPlanType, setExportPlanType,
    exportFormat, setExportFormat, actionLoading,
    behaviourRecords, behaviourSummary, loadingBehaviour, behaviourTypes,
    behaviourModalOpen, setBehaviourModalOpen, editingBehaviour, behaviourForm, setBehaviourForm, savingBehaviour,
    globalTalents, loadingGlobalTalents, customTalentName, setCustomTalentName,
    addingCustomTalent, savingTalent,
    behaviourPage, setBehaviourPage, savingCharacterTrait, newCharacterTrait, setNewCharacterTrait,
    activities, certificates, loadingActivities,
    activityModalOpen, setActivityModalOpen, editingActivity, activityForm, setActivityForm, savingActivity,
    certificateModalOpen, setCertificateModalOpen, editingCertificate, certificateForm, setCertificateForm, savingCertificate,
    planHistory, loadingPlanHistory,
    longitudinalData, loadingLongitudinal,
    profileExportModalOpen, setProfileExportModalOpen, profileExportSections, profileExportFormat, setProfileExportFormat, exportingProfile,
    attendanceHistory, loadingAttendanceHistory, gradesDetail, loadingGrades, classDetail,
    resolvedClassName, resolvedClassId,
    attendanceRate, positiveBehaviourCount, profileCompleteness,
    attendanceChartData, subjectGrades, radarChartData, behaviourTrendData,
    paginatedBehaviourRecords, behaviourTotalPages, BEHAVIOUR_PAGE_SIZE,
    CAREER_AFFINITY_MAP, CHARACTER_TRAIT_OPTIONS, ACTIVITY_TYPE_OPTIONS, involvementScore,
    fetchStudent, fetchRiskData, generatePlan, openExportModal, handleExportPlan,
    handleExportFullProfile, toggleProfileSection,
    openActivityModal, handleSaveActivity, handleDeleteActivity,
    openCertificateModal, handleSaveCertificate, handleDeleteCertificate,
    handleSave, handleAction, handleBack,
    openBehaviourModal, handleSaveBehaviour, handleDeleteBehaviour,
    handleAddTalent, handleRemoveTalent, handleAddCustomTalent,
    handleAddCharacterTrait, handleRemoveCharacterTrait,
    getRiskColor, getRiskLabel, getRiskBarColor,
  };
}
