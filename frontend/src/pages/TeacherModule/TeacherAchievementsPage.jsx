import { useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Progress } from '../../components/ui/progress';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  BookOpen, ClipboardCheck, FileText, Award, Users, TrendingUp,
  Loader2, RefreshCw, Plus, Trash2, Edit3, ChevronDown, ChevronUp,
  FolderOpen, BarChart3, GraduationCap, MessageSquare, Briefcase,
  Activity, Settings, CheckCircle2, AlertCircle, Calendar,
  FileArchive, Eye, Search, X, Zap, Target
} from 'lucide-react';
import { useTranslation } from '../../contexts/ThemeContext';

const SECTION_CONFIG = [
  { key: 'teaching_plans', icon: BookOpen, color: 'text-blue-600 dark:text-blue-400', bg: 'bg-blue-50 dark:bg-blue-900/30', types: ['lesson_plan', 'weekly_plan', 'unit_plan'] },
  { key: 'applied_lessons', icon: FileText, color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-50 dark:bg-emerald-900/30', types: ['applied_lesson_report', 'collaborative_lesson'] },
  { key: 'assessment_grading', icon: GraduationCap, color: 'text-purple-600 dark:text-purple-400', bg: 'bg-purple-50 dark:bg-purple-900/30', types: ['exam_results', 'quiz_results', 'performance_task', 'exam_results_analysis', 'grade_analysis_tables'] },
  { key: 'attendance', icon: ClipboardCheck, color: 'text-green-600 dark:text-green-400', bg: 'bg-green-50 dark:bg-green-900/30', types: ['attendance_record', 'late_tracking'] },
  { key: 'behaviour_guidance', icon: Award, color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-50 dark:bg-amber-900/30', types: ['behaviour_tracking', 'struggling_student_plan', 'observation_notes'] },
  { key: 'parent_communication', icon: MessageSquare, color: 'text-pink-600 dark:text-pink-400', bg: 'bg-pink-50 dark:bg-pink-900/30', types: ['parent_communication_log', 'parent_meeting_minutes'] },
  { key: 'professional_development', icon: Briefcase, color: 'text-indigo-600 dark:text-indigo-400', bg: 'bg-indigo-50 dark:bg-indigo-900/30', types: ['training_certificate', 'workshop_attendance', 'peer_observation'] },
  { key: 'participation_activities', icon: Activity, color: 'text-cyan-600 dark:text-cyan-400', bg: 'bg-cyan-50 dark:bg-cyan-900/30', types: ['participation_tracking', 'extracurricular_activity'] },
  { key: 'administrative', icon: Settings, color: 'text-slate-600 dark:text-slate-400', bg: 'bg-slate-50 dark:bg-slate-900/30', types: ['annual_goals', 'self_evaluation', 'professional_growth_plan'] },
];

const SECTION_TITLE_KEYS = {
  teaching_plans: 'portfolioTeachingPlans',
  applied_lessons: 'portfolioAppliedLessons',
  assessment_grading: 'portfolioAssessmentGrading',
  attendance: 'portfolioAttendance',
  behaviour_guidance: 'portfolioBehaviourGuidance',
  parent_communication: 'portfolioParentCommunication',
  professional_development: 'portfolioProfessionalDevelopment',
  participation_activities: 'portfolioParticipationActivities',
  administrative: 'portfolioAdministrative',
};

const TYPE_LABEL_KEYS = {
  lesson_plan: 'portfolioLessonPlan',
  weekly_plan: 'portfolioWeeklyPlan',
  unit_plan: 'portfolioUnitPlan',
  applied_lesson_report: 'portfolioAppliedLessonReport',
  collaborative_lesson: 'portfolioCollaborativeLesson',
  exam_results: 'portfolioExamResults',
  quiz_results: 'portfolioQuizResults',
  performance_task: 'portfolioPerformanceTask',
  exam_results_analysis: 'portfolioExamResultsAnalysis',
  grade_analysis_tables: 'portfolioGradeAnalysisTables',
  attendance_record: 'portfolioAttendanceRecord',
  late_tracking: 'portfolioLateTracking',
  behaviour_tracking: 'portfolioBehaviourTracking',
  struggling_student_plan: 'portfolioStrugglingStudentPlan',
  observation_notes: 'portfolioObservationNotes',
  parent_communication_log: 'portfolioParentCommunicationLog',
  parent_meeting_minutes: 'portfolioParentMeetingMinutes',
  training_certificate: 'portfolioTrainingCertificate',
  workshop_attendance: 'portfolioWorkshopAttendance',
  peer_observation: 'portfolioPeerObservation',
  participation_tracking: 'portfolioParticipationTracking',
  extracurricular_activity: 'portfolioExtracurricularActivity',
  annual_goals: 'portfolioAnnualGoals',
  self_evaluation: 'portfolioSelfEvaluation',
  professional_growth_plan: 'portfolioProfessionalGrowthPlan',
};

const ALL_EVIDENCE_TYPES = Object.keys(TYPE_LABEL_KEYS);

export default function TeacherAchievementsPage() {
  const { t } = useTranslation();
  const { api, isRTL } = useAuth();
  const { showAlert } = useNassaqAlert();
  const [loading, setLoading] = useState(true);
  const [portfolio, setPortfolio] = useState(null);
  const [progress, setProgress] = useState(null);
  const [activeTab, setActiveTab] = useState('portfolio');
  const [expandedSections, setExpandedSections] = useState({});
  const [evidenceDialog, setEvidenceDialog] = useState({ open: false, mode: 'add', data: null });
  const [evidenceForm, setEvidenceForm] = useState({ evidence_type: '', title_ar: '', title_en: '', description_ar: '', description_en: '', date: '' });
  const [saving, setSaving] = useState(false);
  const [fileFilter, setFileFilter] = useState('');
  const [fileTypeFilter, setFileTypeFilter] = useState('all');

  const fetchPortfolio = useCallback(async () => {
    setLoading(true);
    try {
      const [portfolioRes, progressRes] = await Promise.all([
        api.get('/teacher/portfolio'),
        api.get('/teacher/portfolio/progress'),
      ]);
      setPortfolio(portfolioRes.data);
      setProgress(progressRes.data);
    } catch (err) {
      console.error('Portfolio fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => { fetchPortfolio(); }, [fetchPortfolio]);

  const toggleSection = (key) => {
    setExpandedSections(prev => ({ ...prev, [key]: !prev[key] }));
  };

  const openAddDialog = (sectionKey) => {
    const cfg = SECTION_CONFIG.find(s => s.key === sectionKey);
    const defaultType = cfg?.types?.[0] || '';
    setEvidenceForm({ evidence_type: defaultType, title_ar: '', title_en: '', description_ar: '', description_en: '', date: new Date().toISOString().split('T')[0] });
    setEvidenceDialog({ open: true, mode: 'add', data: null });
  };

  const openEditDialog = (evidence) => {
    setEvidenceForm({
      evidence_type: evidence.evidence_type || '',
      title_ar: evidence.title_ar || '',
      title_en: evidence.title_en || '',
      description_ar: evidence.description_ar || '',
      description_en: evidence.description_en || '',
      date: evidence.date || '',
    });
    setEvidenceDialog({ open: true, mode: 'edit', data: evidence });
  };

  const handleSaveEvidence = async () => {
    if (!evidenceForm.evidence_type || !evidenceForm.title_ar) return;
    setSaving(true);
    try {
      if (evidenceDialog.mode === 'add') {
        await api.post('/teacher/portfolio/evidence', evidenceForm);
        toast.success(t('portfolioSaveSuccess'));
      } else {
        await api.put(`/teacher/portfolio/evidence/${evidenceDialog.data.id}`, evidenceForm);
        toast.success(t('portfolioUpdateSuccess'));
      }
      setEvidenceDialog({ open: false, mode: 'add', data: null });
      fetchPortfolio();
    } catch (err) {
      console.error('Save evidence error:', err);
      toast.error(err?.response?.data?.detail || 'Error');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteEvidence = (evidence) => {
    showAlert({
      title: t('portfolioDeleteConfirm'),
      variant: 'danger',
      confirmText: t('delete'),
      onConfirm: async () => {
        try {
          await api.delete(`/teacher/portfolio/evidence/${evidence.id}`);
          toast.success(t('portfolioDeleteSuccess'));
          fetchPortfolio();
        } catch (err) {
          console.error('Delete error:', err);
        }
      },
    });
  };

  const allEvidence = useMemo(() => {
    if (!portfolio?.sections) return [];
    const items = [];
    Object.values(portfolio.sections).forEach(sec => {
      if (sec.items) items.push(...sec.items);
    });
    return items.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
  }, [portfolio]);

  const filteredFileEvidence = useMemo(() => {
    let items = allEvidence;
    if (fileTypeFilter && fileTypeFilter !== 'all') {
      items = items.filter(e => e.evidence_type === fileTypeFilter);
    }
    if (fileFilter) {
      const q = fileFilter.toLowerCase();
      items = items.filter(e =>
        (e.title_ar || '').toLowerCase().includes(q) ||
        (e.title_en || '').toLowerCase().includes(q) ||
        (e.description_ar || '').toLowerCase().includes(q)
      );
    }
    return items;
  }, [allEvidence, fileTypeFilter, fileFilter]);

  if (loading) {
    return (
      <Sidebar>
        <div className="flex items-center justify-center min-h-[60vh]">
          <Loader2 className="w-8 h-8 animate-spin text-brand-navy dark:text-brand-turquoise" />
        </div>
      </Sidebar>
    );
  }

  const coveragePercent = progress?.overall_percent || portfolio?.coverage_percent || 0;
  const totalEvidence = portfolio?.total_evidence || 0;
  const autoCount = portfolio?.auto_count || 0;
  const manualCount = portfolio?.manual_count || 0;

  return (
    <Sidebar>
      <div className={`p-4 md:p-6 space-y-6 max-w-6xl mx-auto ${isRTL ? 'text-right' : 'text-left'}`}>
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-2xl font-bold text-brand-navy dark:text-white font-cairo">
              {t('portfolioTitle')}
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 font-tajawal">
              {t('portfolioPatternAutoEvidence')}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={fetchPortfolio} className="gap-2">
            <RefreshCw className="w-4 h-4" />
            {t('refresh')}
          </Button>
        </div>

        <Card className="border-0 shadow-sm bg-white dark:bg-gray-800">
          <CardContent className="p-4 md:p-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
              <div className={`w-14 h-14 rounded-xl bg-brand-navy/10 dark:bg-brand-turquoise/10 flex items-center justify-center shrink-0`}>
                <Target className="w-7 h-7 text-brand-navy dark:text-brand-turquoise" />
              </div>
              <div className="flex-1 min-w-0 w-full">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-semibold text-gray-700 dark:text-gray-200 font-cairo">
                    {t('portfolioOverallProgress')}
                  </span>
                  <span className="text-lg font-bold text-brand-navy dark:text-brand-turquoise">
                    {coveragePercent}%
                  </span>
                </div>
                <Progress value={coveragePercent} className="h-3 mb-3" />
                <div className="flex flex-wrap gap-4 text-xs text-gray-500 dark:text-gray-400">
                  <span className="flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5" />
                    {totalEvidence} {t('portfolioEvidenceCount')}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5 text-amber-500" />
                    {autoCount} {t('portfolioAuto')}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Edit3 className="w-3.5 h-3.5 text-blue-500" />
                    {manualCount} {t('portfolioManual')}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <BarChart3 className="w-3.5 h-3.5 text-green-500" />
                    {progress?.overall_covered || 0}/{progress?.overall_total || 0} {t('portfolioTypesCount')}
                  </span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="flex gap-1 p-1 bg-gray-100 dark:bg-gray-800 rounded-lg w-fit">
          {['portfolio', 'files'].map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-sm font-medium rounded-md font-cairo ${
                activeTab === tab
                  ? 'bg-white dark:bg-gray-700 text-brand-navy dark:text-white shadow-sm'
                  : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
            >
              {tab === 'portfolio' ? t('portfolioTab') : t('portfolioFileLibrary')}
            </button>
          ))}
        </div>

        {activeTab === 'portfolio' && (
          <div className="space-y-3">
            {SECTION_CONFIG.map(section => {
              const sectionData = portfolio?.sections?.[section.key];
              const count = sectionData?.count || 0;
              const items = sectionData?.items || [];
              const isExpanded = expandedSections[section.key];
              const SIcon = section.icon;
              const sectionProgress = progress?.section_progress?.[section.key];
              const coveredTypes = sectionProgress?.covered_types || 0;
              const totalTypes = sectionProgress?.total_types || 0;

              return (
                <Card key={section.key} className="border-0 shadow-sm bg-white dark:bg-gray-800 overflow-hidden">
                  <button
                    onClick={() => toggleSection(section.key)}
                    className="w-full px-4 py-3 md:px-5 md:py-4 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-750"
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-lg ${section.bg} flex items-center justify-center`}>
                        <SIcon className={`w-5 h-5 ${section.color}`} />
                      </div>
                      <div className={`${isRTL ? 'text-right' : 'text-left'}`}>
                        <h3 className="text-sm font-semibold text-gray-800 dark:text-gray-100 font-cairo">
                          {t(SECTION_TITLE_KEYS[section.key])}
                        </h3>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-xs text-gray-500 dark:text-gray-400">
                            {count} {t('portfolioEvidenceCount')}
                          </span>
                          <span className="text-xs text-gray-400 dark:text-gray-500">|</span>
                          <span className="text-xs text-gray-500 dark:text-gray-400">
                            {coveredTypes}/{totalTypes} {t('portfolioSectionCovered')}
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {count > 0 && (
                        <Badge variant="secondary" className="text-xs">
                          {count}
                        </Badge>
                      )}
                      {isExpanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                    </div>
                  </button>

                  {isExpanded && (
                    <div className="px-4 pb-4 md:px-5 md:pb-5 border-t border-gray-100 dark:border-gray-700">
                      <div className="flex items-center justify-between py-3">
                        <div className="flex flex-wrap gap-1.5">
                          {section.types.map(typeKey => {
                            const isCovered = sectionProgress?.covered?.includes(typeKey);
                            return (
                              <Badge
                                key={typeKey}
                                variant={isCovered ? 'default' : 'outline'}
                                className={`text-[10px] ${isCovered ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300 border-green-200 dark:border-green-800' : 'text-gray-400 dark:text-gray-500 border-gray-200 dark:border-gray-700'}`}
                              >
                                {isCovered && <CheckCircle2 className={`w-3 h-3 ${isRTL ? 'ml-1' : 'mr-1'}`} />}
                                {!isCovered && <AlertCircle className={`w-3 h-3 ${isRTL ? 'ml-1' : 'mr-1'}`} />}
                                {t(TYPE_LABEL_KEYS[typeKey] || typeKey)}
                              </Badge>
                            );
                          })}
                        </div>
                        <Button size="sm" variant="outline" className="gap-1.5 text-xs shrink-0" onClick={() => openAddDialog(section.key)}>
                          <Plus className="w-3.5 h-3.5" />
                          {t('portfolioAddEvidence')}
                        </Button>
                      </div>

                      {items.length === 0 ? (
                        <div className="text-center py-8 text-gray-400 dark:text-gray-500">
                          <FolderOpen className="w-10 h-10 mx-auto mb-2 opacity-50" />
                          <p className="text-sm">{t('portfolioEmptySection')}</p>
                        </div>
                      ) : (
                        <div className="space-y-2">
                          {items.map(item => (
                            <div
                              key={item.id}
                              className="flex items-start gap-3 p-3 rounded-lg bg-gray-50 dark:bg-gray-750 hover:bg-gray-100 dark:hover:bg-gray-700"
                            >
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-1">
                                  <span className="text-sm font-medium text-gray-800 dark:text-gray-100 truncate font-tajawal">
                                    {isRTL ? item.title_ar : (item.title_en || item.title_ar)}
                                  </span>
                                  <Badge variant="outline" className={`text-[10px] shrink-0 ${item.source === 'auto' ? 'border-amber-300 text-amber-600 dark:border-amber-700 dark:text-amber-400' : 'border-blue-300 text-blue-600 dark:border-blue-700 dark:text-blue-400'}`}>
                                    {item.source === 'auto' ? t('portfolioAuto') : t('portfolioManual')}
                                  </Badge>
                                </div>
                                {(item.description_ar || item.description_en) && (
                                  <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-1">
                                    {isRTL ? item.description_ar : (item.description_en || item.description_ar)}
                                  </p>
                                )}
                                <div className="flex items-center gap-3 mt-1.5 text-[11px] text-gray-400 dark:text-gray-500">
                                  <span className="flex items-center gap-1">
                                    <Calendar className="w-3 h-3" />
                                    {item.date}
                                  </span>
                                  <span>{t(TYPE_LABEL_KEYS[item.evidence_type] || item.evidence_type)}</span>
                                </div>
                              </div>
                              {item.source === 'manual' && (
                                <div className="flex items-center gap-1 shrink-0">
                                  <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => openEditDialog(item)}>
                                    <Edit3 className="w-3.5 h-3.5 text-gray-400" />
                                  </Button>
                                  <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => handleDeleteEvidence(item)}>
                                    <Trash2 className="w-3.5 h-3.5 text-red-400" />
                                  </Button>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </Card>
              );
            })}
          </div>
        )}

        {activeTab === 'files' && (
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row gap-3">
              <div className="relative flex-1">
                <Search className={`absolute top-2.5 ${isRTL ? 'right-3' : 'left-3'} w-4 h-4 text-gray-400`} />
                <Input
                  placeholder={t('search')}
                  value={fileFilter}
                  onChange={(e) => setFileFilter(e.target.value)}
                  className={`${isRTL ? 'pr-9' : 'pl-9'} h-9`}
                />
              </div>
              <Select value={fileTypeFilter} onValueChange={setFileTypeFilter}>
                <SelectTrigger className="w-full sm:w-48 h-9">
                  <SelectValue placeholder={t('portfolioEvidenceType')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('portfolioAllEvidence')}</SelectItem>
                  {ALL_EVIDENCE_TYPES.map(type => (
                    <SelectItem key={type} value={type}>{t(TYPE_LABEL_KEYS[type])}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {filteredFileEvidence.length === 0 ? (
              <Card className="border-0 shadow-sm bg-white dark:bg-gray-800">
                <CardContent className="py-12 text-center">
                  <FileArchive className="w-12 h-12 mx-auto mb-3 text-gray-300 dark:text-gray-600" />
                  <p className="text-gray-500 dark:text-gray-400 text-sm">{t('portfolioEmptyState')}</p>
                </CardContent>
              </Card>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {filteredFileEvidence.map(item => {
                  const sectionCfg = SECTION_CONFIG.find(s => s.types.includes(item.evidence_type));
                  const SIcon = sectionCfg?.icon || FileText;
                  return (
                    <Card key={item.id} className="border-0 shadow-sm bg-white dark:bg-gray-800 hover:shadow-md">
                      <CardContent className="p-4">
                        <div className="flex items-start gap-3">
                          <div className={`w-9 h-9 rounded-lg ${sectionCfg?.bg || 'bg-gray-100 dark:bg-gray-700'} flex items-center justify-center shrink-0`}>
                            <SIcon className={`w-4 h-4 ${sectionCfg?.color || 'text-gray-500'}`} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium text-gray-800 dark:text-gray-100 truncate font-tajawal">
                              {isRTL ? item.title_ar : (item.title_en || item.title_ar)}
                            </p>
                            <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-0.5">
                              {t(TYPE_LABEL_KEYS[item.evidence_type] || item.evidence_type)}
                            </p>
                          </div>
                          <Badge variant="outline" className={`text-[10px] shrink-0 ${item.source === 'auto' ? 'border-amber-300 text-amber-600 dark:border-amber-700 dark:text-amber-400' : 'border-blue-300 text-blue-600 dark:border-blue-700 dark:text-blue-400'}`}>
                            {item.source === 'auto' ? t('portfolioAuto') : t('portfolioManual')}
                          </Badge>
                        </div>
                        {(item.description_ar || item.description_en) && (
                          <p className="text-xs text-gray-500 dark:text-gray-400 mt-2 line-clamp-2">
                            {isRTL ? item.description_ar : (item.description_en || item.description_ar)}
                          </p>
                        )}
                        <div className="flex items-center justify-between mt-3 pt-2 border-t border-gray-100 dark:border-gray-700">
                          <span className="text-[11px] text-gray-400 flex items-center gap-1">
                            <Calendar className="w-3 h-3" /> {item.date}
                          </span>
                          {item.source === 'manual' && (
                            <div className="flex gap-1">
                              <Button size="icon" variant="ghost" className="h-6 w-6" onClick={() => openEditDialog(item)}>
                                <Edit3 className="w-3 h-3 text-gray-400" />
                              </Button>
                              <Button size="icon" variant="ghost" className="h-6 w-6" onClick={() => handleDeleteEvidence(item)}>
                                <Trash2 className="w-3 h-3 text-red-400" />
                              </Button>
                            </div>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      <Dialog open={evidenceDialog.open} onOpenChange={(open) => { if (!open) setEvidenceDialog({ open: false, mode: 'add', data: null }); }}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-cairo">
              {evidenceDialog.mode === 'add' ? t('portfolioAddEvidence') : t('portfolioEditEvidence')}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label className="text-xs font-medium mb-1.5 block">{t('portfolioEvidenceType')}</Label>
              <Select value={evidenceForm.evidence_type} onValueChange={(v) => setEvidenceForm(prev => ({ ...prev, evidence_type: v }))}>
                <SelectTrigger className="h-9">
                  <SelectValue placeholder={t('portfolioEvidenceType')} />
                </SelectTrigger>
                <SelectContent>
                  {ALL_EVIDENCE_TYPES.map(type => (
                    <SelectItem key={type} value={type}>{t(TYPE_LABEL_KEYS[type])}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="text-xs font-medium mb-1.5 block">{t('portfolioTitleAr')}</Label>
              <Input value={evidenceForm.title_ar} onChange={(e) => setEvidenceForm(prev => ({ ...prev, title_ar: e.target.value }))} className="h-9" />
            </div>
            <div>
              <Label className="text-xs font-medium mb-1.5 block">{t('portfolioTitleEn')}</Label>
              <Input value={evidenceForm.title_en} onChange={(e) => setEvidenceForm(prev => ({ ...prev, title_en: e.target.value }))} className="h-9" />
            </div>
            <div>
              <Label className="text-xs font-medium mb-1.5 block">{t('portfolioDescriptionAr')}</Label>
              <Input value={evidenceForm.description_ar} onChange={(e) => setEvidenceForm(prev => ({ ...prev, description_ar: e.target.value }))} className="h-9" />
            </div>
            <div>
              <Label className="text-xs font-medium mb-1.5 block">{t('portfolioDescriptionEn')}</Label>
              <Input value={evidenceForm.description_en} onChange={(e) => setEvidenceForm(prev => ({ ...prev, description_en: e.target.value }))} className="h-9" />
            </div>
            <div>
              <Label className="text-xs font-medium mb-1.5 block">{t('portfolioEvidenceDate')}</Label>
              <Input type="date" value={evidenceForm.date} onChange={(e) => setEvidenceForm(prev => ({ ...prev, date: e.target.value }))} className="h-9" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEvidenceDialog({ open: false, mode: 'add', data: null })}>
              {t('cancel')}
            </Button>
            <Button onClick={handleSaveEvidence} disabled={saving || !evidenceForm.evidence_type || !evidenceForm.title_ar}>
              {saving && <Loader2 className={`w-4 h-4 animate-spin ${isRTL ? 'ml-2' : 'mr-2'}`} />}
              {t('save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Sidebar>
  );
}
