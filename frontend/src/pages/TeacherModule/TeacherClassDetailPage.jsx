import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Progress } from '../../components/ui/progress';
import { Switch } from '../../components/ui/switch';
import { Checkbox } from '../../components/ui/checkbox';
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
  Users, BookOpen, ClipboardCheck, FileText, Star, Calendar,
  ArrowRight, Loader2, RefreshCw, BarChart3, TrendingUp,
  GraduationCap, Clock, ChevronLeft, ChevronDown, ChevronUp,
  Play, Search, AlertTriangle, CheckCircle2, Award, Activity,
  Eye, EyeOff, Plus, Trash2, Edit3, Upload, FileSpreadsheet,
  Settings, Info, X, Check, Minus, CircleDot, History, XCircle,
  Sparkles
} from 'lucide-react';
import HakimPresence from '../../components/hakim/HakimPresence';
import FollowupGradesTable from '../../components/teacher/FollowupGradesTable';
import SidebarSettingsDialog from '../../components/teacher/SidebarSettingsDialog';
import InlineAttendanceTable from '../../components/teacher/InlineAttendanceTable';
import CollaboratorsTab from '../../components/teacher/CollaboratorsTab';
import TeacherStudentProfileDialog from '../../components/teacher/TeacherStudentProfileDialog';
import LessonPlanDetailsDialog from './LessonPlanDetailsDialog';

import { useTranslation } from '../../contexts/ThemeContext';
import { getApiErrorMessage } from '../../utils/apiError';
import { BEHAVIOURS, DEFAULT_EVALUATION_ITEMS, DEFAULT_EVAL_IDS } from '../../config/sessionElements';

const GRADE_COLORS = {
  '1': 'bg-sky-500 dark:bg-sky-600',
  '2': 'bg-emerald-500 dark:bg-emerald-600',
  '3': 'bg-violet-500 dark:bg-violet-600',
  '4': 'bg-amber-500 dark:bg-amber-600',
  '5': 'bg-rose-500 dark:bg-rose-600',
  '6': 'bg-indigo-500 dark:bg-indigo-600',
};

export default function TeacherClassDetailPage() {
  const { t } = useTranslation();
  const { nassaqError } = useNassaqAlert();
  const { classId } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user, api, isRTL } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [classData, setClassData] = useState(null);
  const [students, setStudents] = useState([]);
  const [schedule, setSchedule] = useState([]);
  const [profileStudent, setProfileStudent] = useState(null);

  // IT §6.7 host-only gate: the "collaborators" tab is only meaningful
  // for the workspace that *owns* the class. A collaborator viewing the
  // shared class must not see the management surface.
  const isHostOfClass = !!(classData?.school_id && user?.tenant_id && classData.school_id === user.tenant_id);
  const VALID_TABS = isHostOfClass
    ? ['curriculum', 'records', 'attendance', 'collaborators']
    : ['curriculum', 'records', 'attendance'];
  const tabFromUrl = searchParams.get('tab');
  // Map legacy 'absence' tab key to the new unified 'attendance' tab
  const normalizedTabFromUrl = tabFromUrl === 'absence' ? 'attendance' : tabFromUrl;
  const activeTab = VALID_TABS.includes(normalizedTabFromUrl) ? normalizedTabFromUrl : 'curriculum';
  const setActiveTab = (tab) => {
    setSearchParams({ tab }, { replace: true });
  };

  const [curriculumData, setCurriculumData] = useState({ lessons: [], total: 0, completed: 0, progress: 0, curriculum_start_date: null, curriculum_end_date: null });
  const [curriculumLoading, setCurriculumLoading] = useState(false);
  const [curriculumError, setCurriculumError] = useState(false);
  // Curriculum plans are private per (class, subject, teacher). When the teacher
  // teaches more than one subject in this class, they pick which subject's plan
  // to view/edit; the backend always scopes by the signed-in teacher regardless.
  const [curriculumSubjects, setCurriculumSubjects] = useState([]);
  const [selectedSubjectId, setSelectedSubjectId] = useState(null);
  const [expandedWeeks, setExpandedWeeks] = useState({});
  // Smart Lesson Plan Assistant plans saved to this class (returned by the
  // curriculum-plan endpoint as `assistant_plans`). Clicking one opens the
  // shared LessonPlanDetailsDialog in view mode.
  const [assistantPlanDialog, setAssistantPlanDialog] = useState(null);
  const [showAddLesson, setShowAddLesson] = useState(false);
  const [newLessonTitle, setNewLessonTitle] = useState('');
  const [newLessonWeek, setNewLessonWeek] = useState(1);
  // Lesson dialog mode: 'add' creates a new lesson, 'edit' updates an existing one.
  // Both modes share the same form fields/state below so create & edit stay in sync.
  const [lessonDialogMode, setLessonDialogMode] = useState('add');
  const [editingLessonId, setEditingLessonId] = useState(null);

  // Add/Edit Lesson — date & override state
  const [lessonMeta, setLessonMeta] = useState(null);
  const [lessonMetaLoading, setLessonMetaLoading] = useState(false);
  const [lessonStartDate, setLessonStartDate] = useState('');
  const [lessonEndDate, setLessonEndDate] = useState('');
  const [overrideChecked, setOverrideChecked] = useState(false);
  const [overrideReason, setOverrideReason] = useState('');
  const [showConflictDialog, setShowConflictDialog] = useState(false);
  const overrideReasonRef = useRef(null);

  const [gradeColumns, setGradeColumns] = useState([]);
  const [studentGrades, setStudentGrades] = useState({});
  const [gradesLoading, setGradesLoading] = useState(false);
  // Records tab must know the class's subject list BEFORE fetching grades,
  // otherwise the first fetch would mix all subjects together (the exact
  // ambiguity this scoping exists to prevent). false = context not resolved
  // yet; true = subjects known (possibly empty → legacy unscoped fallback).
  // NOTE: deliberately separate from curriculumSubjects — the record list is
  // CLASS-WIDE (all subjects taught in the class, per spec) while curriculum
  // subjects are private to the signed-in teacher.
  const [recordSubjects, setRecordSubjects] = useState([]);
  const [recordSubjectId, setRecordSubjectId] = useState(null);
  const [recordSubjectsReady, setRecordSubjectsReady] = useState(false);
  const [showColumnSettings, setShowColumnSettings] = useState(false);
  const [showQuickAddCol, setShowQuickAddCol] = useState(false);
  const [newColName, setNewColName] = useState('');
  const [newColType, setNewColType] = useState('coursework');
  const [newColMax, setNewColMax] = useState(10);
  const [editingCol, setEditingCol] = useState(null);
  const [editingColMax, setEditingColMax] = useState(10);

  const [studentSearch, setStudentSearch] = useState('');

  // ===== إعدادات الحصة — class+subject session_settings template =====
  // The server template (same row the live lesson hydrates from via
  // /session/{sid}/settings) is the single source of truth. The legacy
  // localStorage blob is read ONCE as a migration fallback when no server
  // template exists yet, and deleted after the first successful save.
  const SIDEBAR_KEY = `class_sidebar_settings_${classId || 'unknown'}`;
  const [showSidebarSettings, setShowSidebarSettings] = useState(false);
  const [customSkills, setCustomSkills] = useState([]);
  const [customPositiveBehaviours, setCustomPositiveBehaviours] = useState([]);
  const [customNegativeBehaviours, setCustomNegativeBehaviours] = useState([]);
  const [customEvaluationItems, setCustomEvaluationItems] = useState([...DEFAULT_EVALUATION_ITEMS]);
  const [behaviourScoreOverrides, setBehaviourScoreOverrides] = useState({});
  // Skills toggle (preserves legacy toggle row in the Skills tab UI)
  const [skillEnabled, setSkillEnabled] = useState(false);
  const [skillTypes, setSkillTypes] = useState([]);
  const [settingsSubjectId, setSettingsSubjectId] = useState(null);
  const [settingsSubjectsLoading, setSettingsSubjectsLoading] = useState(false);
  const [participationEnabled, setParticipationEnabled] = useState(true);
  const [homeworkEnabled, setHomeworkEnabled] = useState(true);
  const [homeworkViewMode, setHomeworkViewMode] = useState('not_submitted');
  const [recitationEnabled, setRecitationEnabled] = useState(false);
  const [recitationMaxAttempts, setRecitationMaxAttempts] = useState(1);
  const [streakBonusEnabled, setStreakBonusEnabled] = useState(true);
  const [participationScores, setParticipationScores] = useState({});
  const [showAddOtherItems, setShowAddOtherItems] = useState(false);
  // أنماط التقييم draft inside the dialog — diffed against the last-loaded
  // grade-columns baseline on Save (same pattern as the live lesson).
  const [followupColumns, setFollowupColumns] = useState([]);
  const followupColumnsBaseline = useRef([]);
  const followupColumnsLoaded = useRef(false);
  const [savingSettings, setSavingSettings] = useState(false);
  // Guards the silent on-close save: never POST until the template GET for
  // the current subject has resolved, or a fast open→close could overwrite
  // an existing template with pristine defaults.
  const templateHydratedRef = useRef(false);
  const templateRequestRef = useRef(0);

  // Edit the score of an already-listed behaviour from the settings dialog.
  // Built-in ids go into the override map; custom ids update the matching
  // array entry, keeping the sign convention (+ for positive, - for
  // negative). Identical logic to SessionTeachPage.updateBehaviourScore.
  const updateBehaviourScore = (category, id, magnitude) => {
    const mag = Math.round(Math.abs(Number(magnitude)));
    if (!Number.isFinite(mag) || mag <= 0 || mag > 100) return;
    const isBuiltIn = (BEHAVIOURS[category] || []).some((b) => b.id === id);
    if (isBuiltIn) {
      setBehaviourScoreOverrides((prev) => ({ ...prev, [id]: mag }));
      return;
    }
    const signed = category === 'positive' ? mag : -mag;
    const setter = category === 'positive' ? setCustomPositiveBehaviours : setCustomNegativeBehaviours;
    setter((prev) => prev.map((x) => (
      typeof x === 'object' && x !== null && x.id === id ? { ...x, points: signed } : x
    )));
  };

  // Reset template state when navigating between classes so one class's
  // settings can never leak into another's dialog.
  useEffect(() => {
    setSettingsSubjectId(null);
    setCustomSkills([]);
    setCustomPositiveBehaviours([]);
    setCustomNegativeBehaviours([]);
    setCustomEvaluationItems([...DEFAULT_EVALUATION_ITEMS]);
    setBehaviourScoreOverrides({});
    setSkillEnabled(false);
    followupColumnsLoaded.current = false;
    templateHydratedRef.current = false;
  }, [classId]);

  const teacherId = user?.teacher_id || user?.id;
  const fileInputRef = useRef(null);

  const fetchClassData = useCallback(async () => {
    if (!classId) return;
    setLoading(true);
    setError(false);
    try {
      const [classRes, studentsRes, scheduleRes, statsRes] = await Promise.all([
        api.get(`/classes/${classId}`).catch(() => null),
        api.get(`/classes/${classId}/students`).catch(() => null),
        teacherId ? api.get(`/teacher/schedule/${teacherId}`).catch(() => null) : Promise.resolve(null),
        api.get(`/classes/${classId}/student-stats`).catch(() => null),
      ]);

      // The class record is the single record this page is built around;
      // if it failed to load, surface a recoverable error screen rather
      // than rendering an empty placeholder shell.
      if (!classRes) {
        setError(true);
        return;
      }

      const scheduleData = Array.isArray(scheduleRes?.data) ? scheduleRes.data : [];
      const classSchedule = scheduleData.filter(s => s.class_id === classId);
      const studentsList = Array.isArray(studentsRes?.data)
        ? [...studentsRes.data].sort((a, b) =>
            (a.full_name || '').localeCompare(b.full_name || '', 'ar', { sensitivity: 'base' })
          )
        : [];
      const statsMap = (statsRes?.data && typeof statsRes.data === 'object' && !Array.isArray(statsRes.data)) ? statsRes.data : {};

      const enrichedStudents = studentsList.map(student => {
        const s = statsMap[student.id] || {};
        return {
          ...student,
          attendance_rate: s.attendance_rate ?? 0,
          average_grade: s.average_grade ?? 0,
          behavior_points: s.behavior_points ?? 0,
          participation_rate: s.participation_rate ?? 0,
          total_sessions: s.total_sessions_attended ?? 0,
        };
      });

      const avgAttendance = enrichedStudents.length > 0
        ? enrichedStudents.reduce((sum, s) => sum + (s.attendance_rate || 0), 0) / enrichedStudents.length
        : 0;
      const avgParticipation = enrichedStudents.length > 0
        ? enrichedStudents.reduce((sum, s) => sum + (s.participation_rate || 0), 0) / enrichedStudents.length
        : 0;

      const cls = (classRes?.data && typeof classRes.data === 'object') ? classRes.data : {};
      const gl = cls.grade_level || cls.grade_id || '';
      const gradeOrdinals = { '1': t('gradeOrdinal1'), '2': t('gradeOrdinal2'), '3': t('gradeOrdinal3'), '4': t('gradeOrdinal4'), '5': t('gradeOrdinal5'), '6': t('gradeOrdinal6') };
      const gradeNum = typeof gl === 'string' ? gl.match(/\d+/)?.[0] : String(gl);
      const gradeName = cls.grade_name || (gradeNum ? `${t('gradeLevel')} ${gradeOrdinals[gradeNum] || gradeNum}` : cls.name || '');

      setClassData({
        ...(typeof cls === 'object' ? cls : {}),
        id: classId,
        name: cls.name || cls.name_ar || t('class'),
        grade_name: gradeName,
        grade_level: gl,
        student_count: studentsList.length,
        attendance_rate: Math.round(avgAttendance),
        participation_rate: Math.round(avgParticipation),
        weekly_periods: classSchedule.length,
      });

      setStudents(enrichedStudents);
      setSchedule(classSchedule);
    } catch (error) {
      console.error('Error loading class data:', error);
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [api, classId, teacherId, t]);

  useEffect(() => {
    fetchClassData();
  }, [fetchClassData]);

  // Reset the subject scope when navigating between classes so a stale subject
  // from a previous class can't leak into the new class's curriculum fetch.
  useEffect(() => {
    setSelectedSubjectId(null);
    setCurriculumSubjects([]);
    setRecordSubjects([]);
    setRecordSubjectId(null);
    setRecordSubjectsReady(false);
  }, [classId]);

  // Resolve the subject context for the Student Record tab: all subjects
  // taught in the class + which of them actually have grades. The default
  // selection is server-decided (the caller's own subject when they teach
  // in the class, else the first subject with grades).
  useEffect(() => {
    if (activeTab !== 'records' || recordSubjectsReady || !classId) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get(`/class/${classId}/subjects`);
        if (cancelled) return;
        const subs = Array.isArray(res.data?.subjects) ? res.data.subjects : [];
        setRecordSubjects(subs);
        if (subs.length > 0) {
          const def = res.data?.default_subject_id || subs[0].id;
          setRecordSubjectId((prev) => prev || def);
        }
      } catch (err) {
        // Fall back to the unscoped legacy view rather than an empty tab.
        console.error('Error loading class subjects:', err);
      } finally {
        if (!cancelled) setRecordSubjectsReady(true);
      }
    })();
    return () => { cancelled = true; };
  }, [activeTab, recordSubjectsReady, api, classId]);

  const fetchCurriculum = useCallback(async () => {
    if (!classId) return;
    setCurriculumLoading(true);
    setCurriculumError(false);
    try {
      const params = selectedSubjectId ? { subject_id: selectedSubjectId } : {};
      const res = await api.get(`/class/${classId}/curriculum-plan`, { params });
      const data = res.data || { lessons: [], total: 0, completed: 0, progress: 0 };
      setCurriculumData(data);
      const subjects = Array.isArray(data.subjects) ? data.subjects : [];
      setCurriculumSubjects(subjects);
      // Auto-pick the first subject so the plan is scoped to a single
      // (subject, teacher) bucket as soon as we learn the teacher's subjects.
      // The forced re-fetch (selectedSubjectId dependency) then narrows it.
      if (!selectedSubjectId && subjects.length > 0) {
        setSelectedSubjectId(subjects[0].id);
      }
      const weeks = {};
      (data.lessons || []).forEach(l => { weeks[l.week] = true; });
      setExpandedWeeks(weeks);
    } catch (err) {
      setCurriculumError(true);
    } finally {
      setCurriculumLoading(false);
    }
  }, [api, classId, selectedSubjectId]);

  const fetchGradeColumns = useCallback(async () => {
    if (!classId) return;
    setGradesLoading(true);
    // Wait for the subject context: fetching before subjects resolve would
    // briefly show grades mixed across ALL subjects. The subjects effect
    // flips recordSubjectsReady and this callback re-runs.
    if (!recordSubjectsReady) return;
    try {
      // Columns + stored grades load together: the record must show the
      // accumulated per-student values committed by live sessions, not an
      // empty (all-zeros) sheet. Server values are the baseline; local
      // (unsaved) typing only overlays after load.
      const gradesParams = recordSubjectId
        ? { params: { subject_id: recordSubjectId } }
        : undefined;
      const [colsRes, gradesRes] = await Promise.all([
        api.get(`/class/${classId}/grade-columns`),
        // Degrade gracefully: if the grades read fails, still show the
        // columns (empty sheet) instead of blanking the whole tab.
        api.get(`/class/${classId}/student-grades`, gradesParams).catch((e) => {
          console.error('Error loading student grades:', e);
          return null;
        }),
      ]);
      setGradeColumns(colsRes.data || []);
      if (gradesRes) {
        const stored = {};
        (gradesRes.data?.grades || []).forEach((g) => {
          stored[`${g.student_id}_${g.column_id}`] = g.score;
        });
        // Wholesale replace so no stale scores from the previous subject
        // linger after a switch.
        setStudentGrades(stored);
      }
    } catch (err) {
      console.error('Error loading grade columns:', err);
    } finally {
      setGradesLoading(false);
    }
  }, [api, classId, recordSubjectsReady, recordSubjectId]);

  useEffect(() => {
    if (activeTab === 'curriculum') fetchCurriculum();
    else if (activeTab === 'records') fetchGradeColumns();
  }, [activeTab, fetchCurriculum, fetchGradeColumns]);

  // ===== إعدادات الحصة dialog wiring =====

  // Legacy localStorage blob — migration fallback only (read when the server
  // template does not exist yet). Migrates legacy string[] behaviours to
  // {id, name, points} objects, same as the old hydrate effect did.
  const readLegacySidebarSettings = useCallback(() => {
    try {
      const raw = localStorage.getItem(SIDEBAR_KEY);
      if (!raw) return null;
      const s = JSON.parse(raw);
      const migrate = (arr, defaultPoints) => (arr || []).map((b, i) => (
        typeof b === 'string'
          ? { id: `legacy_${defaultPoints > 0 ? 'p' : 'n'}_${i}_${b}`, name: b, points: defaultPoints }
          : b
      ));
      return {
        customSkills: Array.isArray(s.customSkills) ? s.customSkills : [],
        customPositiveBehaviours: migrate(s.customPositiveBehaviours, 2),
        customNegativeBehaviours: migrate(s.customNegativeBehaviours, -2),
        customEvaluationItems: Array.isArray(s.customEvaluationItems) ? s.customEvaluationItems : [],
        skillEnabled: typeof s.skillEnabled === 'boolean' ? s.skillEnabled : null,
      };
    } catch { return null; }
  }, [SIDEBAR_KEY]);

  const loadSkillTypes = useCallback(async () => {
    try {
      const res = await api.get('/skills-types');
      setSkillTypes(res.data || []);
    } catch (e) {
      console.error('Error loading skill types:', e);
    }
  }, [api]);

  // Persist a new score weight (وزن الدرجة) for a registered skill —
  // durable and school-scoped server-side, same as the live lesson.
  const updateSkillType = async (skillId, points) => {
    try {
      await api.put(`/skills-types/${skillId}`, { points });
      await loadSkillTypes();
      toast.success(t('scoreWeightUpdated') || 'تم تحديث وزن الدرجة');
    } catch (e) {
      console.error('Error updating skill type:', e);
      toast.error(getApiErrorMessage(e) || t('errorOccurred') || 'Error');
    }
  };

  // Adapt backend grade-column shape to the dialog's local column shape
  // (identical to the live lesson's adapter so ids/groups stay aligned).
  const adaptDialogColumn = (c) => ({
    id: c.id,
    name: c.name,
    group: c.column_type === 'exams' ? 'exams' : 'coursework',
    maxGrade: c.max_grade,
    hidden: c.visible === false,
    type: 'grade',
    _order: c.order ?? 0,
  });

  const loadDialogGradeColumns = useCallback(async () => {
    if (!classId) return;
    try {
      const res = await api.get(`/class/${classId}/grade-columns`);
      const adapted = (Array.isArray(res.data) ? res.data : [])
        .map(adaptDialogColumn)
        .sort((a, b) => (a._order || 0) - (b._order || 0));
      setFollowupColumns(adapted);
      followupColumnsBaseline.current = adapted;
      followupColumnsLoaded.current = true;
      if (adapted.length > 0) setShowAddOtherItems(true);
    } catch (e) {
      console.error('loadDialogGradeColumns failed', e);
    }
  }, [api, classId]);

  // Hydrate all dialog state from the class+subject template. When no
  // template exists yet, fall back ONCE to the legacy localStorage blob so
  // previously saved local customs survive the migration.
  const loadSessionTemplate = useCallback(async (subjectId) => {
    if (!classId || !subjectId) return;
    templateHydratedRef.current = false;
    // Latest-wins guard: if the teacher switches subjects while a GET is in
    // flight, the superseded response must never hydrate (or a later silent
    // close-save would write subject A's template into subject B's row).
    const requestToken = ++templateRequestRef.current;
    try {
      const res = await api.get(`/class/${classId}/session-settings`, {
        params: { subject_id: subjectId },
      });
      if (requestToken !== templateRequestRef.current) return;
      const s = res.data || {};
      setParticipationEnabled(s.participation_enabled !== false);
      setHomeworkEnabled(s.homework_enabled !== false);
      setHomeworkViewMode(s.homework_view_mode || 'not_submitted');
      setRecitationEnabled(!!s.recitation_enabled);
      setRecitationMaxAttempts(Number(s.recitation_max_attempts) || 1);
      setStreakBonusEnabled(s.streak_bonus_enabled !== false);
      setSkillEnabled(!!s.skill_enabled);
      setParticipationScores(
        s.participation_scores && typeof s.participation_scores === 'object'
          ? s.participation_scores : {}
      );
      if (s.exists) {
        setCustomPositiveBehaviours(Array.isArray(s.custom_positive_behaviours) ? s.custom_positive_behaviours : []);
        setCustomNegativeBehaviours(Array.isArray(s.custom_negative_behaviours) ? s.custom_negative_behaviours : []);
        setCustomSkills(Array.isArray(s.custom_skills) ? s.custom_skills : []);
        // The template stores only user-added evaluation items; the four
        // built-ins are re-prepended locally (defaults ∪ custom).
        setCustomEvaluationItems([
          ...DEFAULT_EVALUATION_ITEMS,
          ...(Array.isArray(s.custom_evaluation_items) ? s.custom_evaluation_items : [])
            .filter((x) => x && !DEFAULT_EVAL_IDS.has(x.id)),
        ]);
        setBehaviourScoreOverrides(
          s.behaviour_score_overrides && typeof s.behaviour_score_overrides === 'object'
            ? s.behaviour_score_overrides : {}
        );
      } else {
        const legacy = readLegacySidebarSettings();
        setCustomPositiveBehaviours(legacy?.customPositiveBehaviours || []);
        setCustomNegativeBehaviours(legacy?.customNegativeBehaviours || []);
        setCustomSkills(legacy?.customSkills || []);
        setCustomEvaluationItems(
          legacy?.customEvaluationItems?.length
            ? [
                ...DEFAULT_EVALUATION_ITEMS,
                ...legacy.customEvaluationItems.filter((x) => x && !DEFAULT_EVAL_IDS.has(x.id)),
              ]
            : [...DEFAULT_EVALUATION_ITEMS]
        );
        setBehaviourScoreOverrides({});
        if (typeof legacy?.skillEnabled === 'boolean') setSkillEnabled(legacy.skillEnabled);
      }
      templateHydratedRef.current = true;
    } catch (e) {
      console.error('Error loading session-settings template:', e);
    }
  }, [api, classId, readLegacySidebarSettings]);

  // Resolve the class's subject list for the dialog picker. Reuses the
  // records-tab list when already loaded, otherwise fetches it (the dialog
  // can be opened from any tab).
  const ensureSettingsSubjects = useCallback(async () => {
    if (recordSubjects.length > 0) {
      return recordSubjectId || recordSubjects[0]?.id || null;
    }
    setSettingsSubjectsLoading(true);
    try {
      const res = await api.get(`/class/${classId}/subjects`);
      const subs = Array.isArray(res.data?.subjects) ? res.data.subjects : [];
      setRecordSubjects(subs);
      setRecordSubjectsReady(true);
      const def = res.data?.default_subject_id || subs[0]?.id || null;
      if (def) setRecordSubjectId((prev) => prev || def);
      return def;
    } catch (e) {
      console.error('Error loading class subjects:', e);
      return null;
    } finally {
      setSettingsSubjectsLoading(false);
    }
  }, [api, classId, recordSubjects, recordSubjectId]);

  const openSessionSettings = useCallback(async () => {
    setShowSidebarSettings(true);
    loadSkillTypes();
    loadDialogGradeColumns();
    const def = await ensureSettingsSubjects();
    const chosen = settingsSubjectId || def || null;
    if (chosen) {
      setSettingsSubjectId(chosen);
      loadSessionTemplate(chosen);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ensureSettingsSubjects, loadDialogGradeColumns, loadSessionTemplate, loadSkillTypes, settingsSubjectId]);

  // Propagate أنماط التقييم edits (add / rename / re-score / delete) to the
  // class-level grade-columns API by diffing the dialog draft against the
  // last-loaded baseline — same contract as the live lesson's حفظ النمط.
  const syncDialogColumns = useCallback(async () => {
    if (!classId) return true;
    if (!followupColumnsLoaded.current) {
      await loadDialogGradeColumns();
      if (!followupColumnsLoaded.current) {
        nassaqError(t('saveFailed') || 'فشل حفظ أعمدة النمط');
        return false;
      }
      return true;
    }
    const baseline = followupColumnsBaseline.current || [];
    const baselineById = new Map(baseline.map((c) => [String(c.id), c]));
    const currentIds = new Set(followupColumns.map((c) => String(c.id)));
    const ops = [];
    let nextOrder = baseline.reduce((m, c) => Math.max(m, Number(c._order) || 0), 0);
    followupColumns.forEach((col) => {
      const base = baselineById.get(String(col.id));
      if (!base) {
        nextOrder += 1;
        ops.push(api.post(`/class/${classId}/grade-columns`, {
          name: String(col.name || '').trim() || (t('newColumn') || 'عمود جديد'),
          column_type: col.group === 'exams' ? 'exams' : 'coursework',
          max_grade: Math.max(1, Number(col.maxGrade) || 10),
          order: nextOrder,
        }));
        return;
      }
      const body = {};
      const trimmedName = String(col.name || '').trim();
      if (trimmedName && trimmedName !== String(base.name)) body.name = trimmedName;
      if (Number(col.maxGrade) !== Number(base.maxGrade)) {
        body.max_grade = Math.max(1, Number(col.maxGrade) || 1);
      }
      if (Object.keys(body).length > 0) {
        ops.push(api.put(`/grade-column/${col.id}`, body));
      }
    });
    baseline.forEach((col) => {
      if (!currentIds.has(String(col.id))) {
        ops.push(api.delete(`/grade-column/${col.id}`));
      }
    });
    if (ops.length === 0) return true;
    const results = await Promise.allSettled(ops);
    const failed = results.filter((r) => r.status === 'rejected');
    await loadDialogGradeColumns();
    if (failed.length > 0) {
      const err = failed[0].reason;
      nassaqError(getApiErrorMessage(err) || (t('saveFailed') || 'فشل حفظ أعمدة النمط'));
      return false;
    }
    return true;
  }, [api, classId, followupColumns, loadDialogGradeColumns, nassaqError, t]);

  // Persist the full template. Explicit Save (dialog button) also syncs the
  // pattern columns and closes the dialog; the silent variant runs on dialog
  // close so تعريفات العناصر edits (no Save button on those tabs) are never
  // lost, and skips columns (those keep requiring an explicit Save).
  const saveSessionTemplate = useCallback(async ({ silent = false } = {}) => {
    const subjectId = settingsSubjectId;
    if (!subjectId) {
      if (!silent) toast.error(t('selectSubjectFirst') || 'اختر المادة أولاً');
      return false;
    }
    if (silent && !templateHydratedRef.current) return false;
    if (!silent) setSavingSettings(true);
    try {
      if (!silent) {
        const columnsSynced = await syncDialogColumns();
        if (!columnsSynced) return false;
      }
      await api.post(`/class/${classId}/session-settings`, {
        subject_id: subjectId,
        participation_enabled: participationEnabled,
        homework_enabled: homeworkEnabled,
        homework_view_mode: homeworkViewMode,
        recitation_enabled: recitationEnabled,
        recitation_max_attempts: recitationMaxAttempts,
        streak_bonus_enabled: streakBonusEnabled,
        skill_enabled: skillEnabled,
        participation_scores: participationScores,
        custom_positive_behaviours: customPositiveBehaviours,
        custom_negative_behaviours: customNegativeBehaviours,
        custom_skills: customSkills,
        custom_evaluation_items: customEvaluationItems.filter((x) => x && !DEFAULT_EVAL_IDS.has(x.id)),
        behaviour_score_overrides: behaviourScoreOverrides,
      });
      // Server template now owns these settings — retire the legacy blob.
      try { localStorage.removeItem(SIDEBAR_KEY); } catch { /* ignore */ }
      if (!silent) {
        toast.success(t('saved') || 'تم الحفظ');
        setShowSidebarSettings(false);
        // Refresh the records tab so column edits show up immediately.
        fetchGradeColumns();
      }
      return true;
    } catch (e) {
      console.error('Error saving session-settings template:', e);
      if (!silent) toast.error(getApiErrorMessage(e) || t('errorOccurred') || 'Error');
      return false;
    } finally {
      if (!silent) setSavingSettings(false);
    }
  }, [
    api, classId, settingsSubjectId, participationEnabled, homeworkEnabled,
    homeworkViewMode, recitationEnabled, recitationMaxAttempts,
    streakBonusEnabled, skillEnabled, participationScores,
    customPositiveBehaviours, customNegativeBehaviours, customSkills,
    customEvaluationItems, behaviourScoreOverrides, syncDialogColumns,
    fetchGradeColumns, SIDEBAR_KEY, t,
  ]);

  const handleToggleLesson = async (lesson) => {
    try {
      await api.put(`/curriculum-lesson/${lesson.id}`, { is_completed: !lesson.is_completed });
      toast.success(lesson.is_completed ? t('lessonMarkedIncomplete') : t('lessonCompleted'));
      fetchCurriculum();
    } catch (err) {
      console.error(err);
      nassaqError(t('errorLoadingCurriculum'));
    }
  };

  const handleSkipLesson = async (lesson) => {
    try {
      await api.put(`/curriculum-lesson/${lesson.id}`, { is_skipped: !lesson.is_skipped });
      toast.success(lesson.is_skipped ? t('lessonUpdated') : t('skipped'));
      fetchCurriculum();
    } catch (err) {
      nassaqError(t('errorSkippingLesson'));
    }
  };

  const handleDeleteLesson = async (lessonId) => {
    try {
      await api.delete(`/curriculum-lesson/${lessonId}`);
      toast.success(t('lessonDeleted'));
      fetchCurriculum();
    } catch (err) {
      nassaqError(t('errorDeletingLesson'));
    }
  };

  const resetAddLessonForm = () => {
    setLessonDialogMode('add');
    setEditingLessonId(null);
    setNewLessonTitle('');
    setNewLessonWeek(1);
    setLessonMeta(null);
    setLessonStartDate('');
    setLessonEndDate('');
    setOverrideChecked(false);
    setOverrideReason('');
    setShowConflictDialog(false);
  };

  const openAddLesson = async () => {
    resetAddLessonForm();
    setShowAddLesson(true);
    setLessonMetaLoading(true);
    try {
      const res = await api.get(`/class/${classId}/curriculum-plan/lesson/new-metadata`);
      const meta = res.data || {};
      setLessonMeta(meta);
      setLessonStartDate(meta.default_start_date || '');
      setLessonEndDate(meta.default_end_date || '');
    } catch {
      setLessonMeta({});
    } finally {
      setLessonMetaLoading(false);
    }
  };

  const openEditLesson = async (lesson) => {
    // Prefill the shared lesson form with the lesson's current saved values,
    // then switch the dialog into edit mode.
    resetAddLessonForm();
    setLessonDialogMode('edit');
    setEditingLessonId(lesson.id);
    setNewLessonTitle(lesson.title || '');
    setNewLessonWeek(lesson.week || 1);
    setLessonStartDate((lesson.start_date || '').slice(0, 10));
    setLessonEndDate((lesson.end_date || '').slice(0, 10));
    setShowAddLesson(true);
    setLessonMetaLoading(true);
    try {
      const res = await api.get(`/class/${classId}/curriculum-plan/lesson/new-metadata`);
      setLessonMeta(res.data || {});
    } catch {
      setLessonMeta({});
    } finally {
      setLessonMetaLoading(false);
    }
  };

  const datesOutOfRange = (() => {
    if (!lessonMeta) return false;
    const { curriculum_start_date: cs, curriculum_end_date: ce } = lessonMeta;
    if (!cs || !ce) return false;
    const inRange = (d) => {
      if (!d) return true;
      try {
        return d >= cs && d <= ce;
      } catch { return true; }
    };
    return !inRange(lessonStartDate) || !inRange(lessonEndDate);
  })();

  const handleAddLesson = async () => {
    if (!newLessonTitle.trim()) return;
    try {
      const weekLessons = curriculumData.lessons.filter(l => l.week === newLessonWeek);
      const body = {
        title: newLessonTitle.trim(),
        week: newLessonWeek,
        order: weekLessons.length + 1,
      };
      if (lessonStartDate) body.start_date = lessonStartDate;
      if (lessonEndDate) body.end_date = lessonEndDate;
      if (overrideChecked) {
        body.override_curriculum = true;
        body.override_reason = overrideReason.trim();
      }
      await api.post(
        `/class/${classId}/curriculum-plan/lesson`,
        body,
        selectedSubjectId ? { params: { subject_id: selectedSubjectId } } : undefined,
      );
      toast.success(t('lessonAdded'));
      resetAddLessonForm();
      setShowAddLesson(false);
      fetchCurriculum();
    } catch (err) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      if (status === 409 && detail?.code === 'curriculum_date_conflict') {
        setShowConflictDialog(true);
        return;
      }
      const msg = getApiErrorMessage(err);
      nassaqError(typeof msg === 'string' ? msg : t('errorAddingLesson'));
    }
  };

  const handleEditLesson = async () => {
    if (!newLessonTitle.trim() || !editingLessonId) return;
    try {
      const body = {
        title: newLessonTitle.trim(),
        week: newLessonWeek,
      };
      if (lessonStartDate) body.start_date = lessonStartDate;
      if (lessonEndDate) body.end_date = lessonEndDate;
      if (overrideChecked) {
        body.override_curriculum = true;
        body.override_reason = overrideReason.trim();
      }
      await api.put(`/curriculum-lesson/${editingLessonId}`, body);
      toast.success(t('lessonUpdated'));
      resetAddLessonForm();
      setShowAddLesson(false);
      fetchCurriculum();
    } catch (err) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      if (status === 409 && detail?.code === 'curriculum_date_conflict') {
        setShowConflictDialog(true);
        return;
      }
      const msg = getApiErrorMessage(err);
      nassaqError(typeof msg === 'string' ? msg : t('errorEditingLesson'));
    }
  };

  // Dispatches the lesson dialog's submit action based on the active mode.
  const handleSubmitLesson = () => (
    lessonDialogMode === 'edit' ? handleEditLesson() : handleAddLesson()
  );

  const handleAddColumn = async () => {
    if (!newColName.trim()) {
      toast.error(t('columnNameRequired'));
      return;
    }
    try {
      await api.post(`/class/${classId}/grade-columns`, {
        name: newColName.trim(),
        column_type: newColType,
        max_grade: newColMax,
        order: gradeColumns.length + 1,
      });
      toast.success(t('columnAdded'));
      setNewColName('');
      setNewColType('coursework');
      setNewColMax(10);
      setShowQuickAddCol(false);
      fetchGradeColumns();
    } catch (err) {
      console.error(err);
      const detail = getApiErrorMessage(err) || err?.message || t('saveFailed');
      toast.error(detail);
    }
  };

  const handleToggleColumnVisibility = async (col) => {
    try {
      await api.put(`/grade-column/${col.id}`, { visible: !col.visible });
      toast.success(t('columnUpdated'));
      fetchGradeColumns();
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteColumn = async (colId) => {
    try {
      await api.delete(`/grade-column/${colId}`);
      toast.success(t('columnDeleted'));
      fetchGradeColumns();
    } catch (err) {
      console.error(err);
    }
  };

  const handleEditColumnMax = async (col) => {
    try {
      await api.put(`/grade-column/${col.id}`, { max_grade: editingColMax });
      toast.success(t('columnUpdated'));
      setEditingCol(null);
      fetchGradeColumns();
    } catch (err) {
      console.error(err);
    }
  };

  const handleReorderColumn = async (col, direction) => {
    const sorted = [...gradeColumns].sort((a, b) => (a.order || 0) - (b.order || 0));
    const idx = sorted.findIndex(c => c.id === col.id);
    const swapIdx = direction === 'up' ? idx - 1 : idx + 1;
    if (swapIdx < 0 || swapIdx >= sorted.length) return;
    try {
      await Promise.all([
        api.put(`/grade-column/${sorted[idx].id}`, { order: sorted[swapIdx].order }),
        api.put(`/grade-column/${sorted[swapIdx].id}`, { order: sorted[idx].order }),
      ]);
      toast.success(t('columnUpdated'));
      fetchGradeColumns();
    } catch (err) {
      console.error(err);
    }
  };

  const handleGradeChange = (studentId, colId, value) => {
    setStudentGrades(prev => ({
      ...prev,
      [`${studentId}_${colId}`]: value,
    }));
  };

  const filteredStudents = useMemo(() => {
    if (!studentSearch) return students;
    return students.filter(s =>
      s.full_name?.toLowerCase().includes(studentSearch.toLowerCase()) ||
      s.student_number?.toLowerCase().includes(studentSearch.toLowerCase())
    );
  }, [students, studentSearch]);

  const weekGroups = useMemo(() => {
    const groups = {};
    (curriculumData.lessons || []).forEach(l => {
      const w = l.week || 1;
      if (!groups[w]) groups[w] = [];
      groups[w].push(l);
    });
    Object.keys(groups).forEach(w => {
      groups[w].sort((a, b) => (a.order || 0) - (b.order || 0));
    });
    return groups;
  }, [curriculumData.lessons]);

  const maxWeek = useMemo(() => {
    const weeks = Object.keys(weekGroups).map(Number);
    return weeks.length > 0 ? Math.max(...weeks) : 0;
  }, [weekGroups]);

  const { currentLessonId, nextLessonId } = useMemo(() => {
    const allLessons = (curriculumData.lessons || [])
      .filter(l => !l.is_skipped)
      .sort((a, b) => (a.week || 0) - (b.week || 0) || (a.order || 0) - (b.order || 0));
    const firstIncomplete = allLessons.find(l => !l.is_completed);
    const firstIncompleteIdx = firstIncomplete ? allLessons.indexOf(firstIncomplete) : -1;
    const nextIdx = firstIncompleteIdx >= 0 ? firstIncompleteIdx + 1 : -1;
    return {
      currentLessonId: firstIncomplete?.id || null,
      nextLessonId: nextIdx < allLessons.length && nextIdx >= 0 ? allLessons[nextIdx]?.id : null,
    };
  }, [curriculumData.lessons]);

  const isBehind = (() => {
    if (!curriculumData.total || !curriculumData.curriculum_start_date || !curriculumData.curriculum_end_date) return false;
    const start = new Date(curriculumData.curriculum_start_date).getTime();
    const end = new Date(curriculumData.curriculum_end_date).getTime();
    const now = Date.now();
    const termLength = end - start;
    if (termLength <= 0) return false;
    const elapsed = Math.min(Math.max(now - start, 0), termLength);
    const expectedProgress = (elapsed / termLength) * 100;
    return curriculumData.progress < expectedProgress - 15;
  })();

  const visibleColumns = gradeColumns.filter(c => c.visible !== false);

  const gc = GRADE_COLORS[String(classData?.grade_level)] || 'bg-blue-500 dark:bg-blue-600';

  const getColumnDisplay = (col) => {
    if (!isRTL && col.name_en) return col.name_en;
    return col.name;
  };

  const assistantPlans = Array.isArray(curriculumData.assistant_plans)
    ? curriculumData.assistant_plans
    : [];

  const renderCurriculumTab = () => (
    <div className="space-y-4">
      {curriculumError && (
        <div className="flex items-center justify-between gap-3 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-red-500 flex-shrink-0" aria-hidden="true" />
            <p className="text-sm text-red-700 dark:text-red-300 font-tajawal">{t('errorLoadingCurriculum')}</p>
          </div>
          <Button size="sm" variant="outline" className="gap-1.5 border-red-300 text-red-700 hover:bg-red-100 dark:border-red-700 dark:text-red-300 dark:hover:bg-red-900/30 shrink-0" onClick={fetchCurriculum}>
            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            {t('retry')}
          </Button>
        </div>
      )}
      <div className="grid sm:grid-cols-3 gap-3">
        <Card className="bg-brand-turquoise/5 border-brand-turquoise/20">
          <CardContent className="p-4 text-center">
            <div className="text-3xl font-bold text-brand-turquoise">{curriculumData.progress}%</div>
            <div className="text-xs text-muted-foreground mt-1">{t('planProgress')}</div>
            <Progress value={curriculumData.progress} className="h-2 mt-2" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-3xl font-bold text-emerald-600">{curriculumData.completed}</div>
            <div className="text-xs text-muted-foreground mt-1">{t('completedLessons')}</div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 text-center">
            <div className="text-3xl font-bold text-foreground">{curriculumData.total}</div>
            <div className="text-xs text-muted-foreground mt-1">{t('totalLessons')}</div>
          </CardContent>
        </Card>
      </div>

      {isBehind && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
          <AlertTriangle className="h-4 w-4 text-amber-500 flex-shrink-0" />
          <p className="text-sm text-amber-700 dark:text-amber-300 font-tajawal">{t('curriculumBehindSchedule')}</p>
          <Badge className="bg-amber-100 text-amber-700 border-0 ms-auto text-xs">{t('behind')}</Badge>
        </div>
      )}

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          {curriculumSubjects.length > 1 && (
            <Select value={selectedSubjectId || ''} onValueChange={(v) => setSelectedSubjectId(v)}>
              <SelectTrigger className="h-9 w-[180px] gap-1.5">
                <BookOpen className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
                <SelectValue placeholder={t('selectSubject')} />
              </SelectTrigger>
              <SelectContent>
                {curriculumSubjects.map((s) => (
                  <SelectItem key={s.id} value={s.id}>{s.name || s.id}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          <Button size="sm" variant="outline" className="gap-1.5" onClick={openAddLesson}>
            <Plus className="h-3.5 w-3.5" />
            {t('addLesson')}
          </Button>
          <Button size="sm" variant="outline" className="gap-1.5" onClick={() => fileInputRef.current?.click()}>
            <Upload className="h-3.5 w-3.5" />
            {t('importPlan')}
          </Button>
        </div>
        <Badge variant="secondary" className="text-xs">
          {curriculumData.progress >= 80 ? t('onSchedule') : isBehind ? t('behind') : t('onSchedule')}
        </Badge>
      </div>

      {/* Smart Lesson Plan Assistant plans saved to this class. Rendered as a
          distinct AI (purple) group — they live in the assistant's own store,
          not the weekly curriculum_lessons plan, so they carry no week/order
          and never affect the progress metrics above. */}
      {!curriculumLoading && assistantPlans.length > 0 && (
        <Card className="border-brand-purple/25 bg-brand-purple/5 dark:bg-brand-purple/10 overflow-hidden">
          <CardContent className="p-4 space-y-3">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-brand-purple/15 flex items-center justify-center flex-shrink-0">
                <Sparkles className="h-4 w-4 text-brand-purple" strokeWidth={1.5} aria-hidden="true" />
              </div>
              <div className="min-w-0">
                <p className="font-medium text-sm font-cairo">{t('assistantPlansSection')}</p>
                <p className="text-xs text-muted-foreground font-tajawal">{t('assistantPlansHint')}</p>
              </div>
              <Badge className="ms-auto bg-brand-purple/15 text-brand-purple border-0 text-xs shrink-0">
                {assistantPlans.length}
              </Badge>
            </div>
            <div className="space-y-1.5">
              {assistantPlans.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => setAssistantPlanDialog(p)}
                  className="w-full flex items-center gap-3 p-2.5 rounded-lg bg-background/70 hover:bg-background transition-colors duration-150 text-start"
                >
                  <BookOpen className="h-4 w-4 text-brand-purple flex-shrink-0" strokeWidth={1.5} aria-hidden="true" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-tajawal truncate">{p.plan?.title || p.topic}</p>
                    <p className="text-xs text-muted-foreground truncate">
                      {[p.subject, p.duration_minutes ? `${p.duration_minutes} ${t('minutes')}` : null]
                        .filter(Boolean)
                        .join(' · ')}
                    </p>
                  </div>
                  <span className="text-xs text-brand-purple font-medium shrink-0">{t('viewDetails')}</span>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {curriculumLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
        </div>
      ) : Object.keys(weekGroups).length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="text-center py-16">
            <BookOpen className="h-14 w-14 mx-auto mb-4 text-muted-foreground/20" />
            <h3 className="font-bold text-lg mb-2 font-cairo">{t('noLessonsInPlan')}</h3>
            <p className="text-sm text-muted-foreground font-tajawal">{t('addLessonsToStartTracking')}</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {Object.keys(weekGroups).sort((a, b) => Number(a) - Number(b)).map(week => {
            const lessons = weekGroups[week];
            const weekCompleted = lessons.filter(l => l.is_completed).length;
            const isExpanded = expandedWeeks[week];
            return (
              <Card key={week} className="overflow-hidden">
                <button
                  className="w-full flex items-center justify-between p-3 hover:bg-muted/30 transition-colors duration-150"
                  onClick={() => setExpandedWeeks(prev => ({ ...prev, [week]: !prev[week] }))}
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-brand-navy/10 dark:bg-brand-turquoise/10 flex items-center justify-center">
                      <span className="text-sm font-bold text-brand-navy dark:text-brand-turquoise">{week}</span>
                    </div>
                    <div className="text-start">
                      <p className="font-medium text-sm font-cairo">{t('weekNumber')} {week}</p>
                      <p className="text-xs text-muted-foreground">{weekCompleted}/{lessons.length} {t('completedLessons')}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Progress value={lessons.length > 0 ? (weekCompleted / lessons.length) * 100 : 0} className="w-20 h-1.5" />
                    {isExpanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
                  </div>
                </button>
                {isExpanded && (
                  <div className="border-t border-border/50 px-3 pb-3 space-y-1">
                    {lessons.map((lesson, idx) => {
                      const isCurrent = lesson.id === currentLessonId;
                      const isNext = lesson.id === nextLessonId;
                      return (
                      <div
                        key={lesson.id}
                        className={`flex items-center gap-3 p-2.5 rounded-lg transition-colors duration-150 ${
                          isCurrent ? 'bg-brand-turquoise/10 dark:bg-brand-turquoise/5 ring-1 ring-brand-turquoise/30' :
                          lesson.is_completed ? 'bg-emerald-50/50 dark:bg-emerald-900/10' :
                          lesson.is_skipped ? 'bg-red-50/50 dark:bg-red-900/10 opacity-60' :
                          isNext ? 'bg-blue-50/50 dark:bg-blue-900/10' : 'hover:bg-muted/30'
                        }`}
                      >
                        <Checkbox
                          checked={lesson.is_completed}
                          onCheckedChange={() => handleToggleLesson(lesson)}
                          disabled={lesson.is_skipped}
                          className="data-[state=checked]:bg-emerald-500 data-[state=checked]:border-emerald-500"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className={`text-sm font-tajawal ${
                              lesson.is_completed ? 'line-through text-muted-foreground' :
                              lesson.is_skipped ? 'line-through text-red-400' : ''
                            }`}>
                              {lesson.title}
                            </p>
                            {isCurrent && (
                              <Badge className="bg-brand-turquoise/20 text-brand-turquoise border-0 text-[10px] px-1.5 py-0">
                                {t('currentLesson')}
                              </Badge>
                            )}
                            {isNext && !isCurrent && (
                              <Badge variant="outline" className="text-blue-500 border-blue-200 text-[10px] px-1.5 py-0">
                                {t('nextLesson')}
                              </Badge>
                            )}
                            {lesson.is_skipped && (
                              <Badge className="bg-red-100 text-red-500 border-0 text-[10px] px-1.5 py-0">
                                {t('skipped')}
                              </Badge>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-0.5">
                          <Button
                            size="sm" variant="ghost" className="h-7 w-7 p-0"
                            title={lesson.is_skipped ? t('markComplete') : t('skipped')}
                            onClick={() => handleSkipLesson(lesson)}
                          >
                            <Minus className={`h-3 w-3 ${lesson.is_skipped ? 'text-red-400' : 'text-muted-foreground'}`} />
                          </Button>
                          <Button
                            size="sm" variant="ghost" className="h-7 w-7 p-0"
                            onClick={() => openEditLesson(lesson)}
                          >
                            <Edit3 className="h-3 w-3 text-muted-foreground" />
                          </Button>
                          <Button
                            size="sm" variant="ghost" className="h-7 w-7 p-0"
                            onClick={() => handleDeleteLesson(lesson.id)}
                          >
                            <Trash2 className="h-3 w-3 text-red-400" />
                          </Button>
                        </div>
                      </div>
                      );
                    })}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );

  const renderRecordsTab = () => {
    const visibleColCount = gradeColumns.filter(c => c.visible !== false).length;
    return (
      <div className="space-y-4">
        {/* Search row */}
        <div className="relative">
          <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder={t('searchByNameOrId')}
            value={studentSearch}
            onChange={(e) => setStudentSearch(e.target.value)}
            className="ps-9 h-9"
          />
        </div>

        {/* Toolbar — mirrors كشف المتابعة */}
        <div className="flex items-center justify-between gap-2 px-3 py-2.5 rounded-lg bg-muted/40 dark:bg-card/40 border border-border">
          <div className="flex items-center gap-2 flex-wrap">
            {/* Subject context: switcher for multi-subject classes, a static
                badge for single-subject ones — the teacher must always know
                WHICH subject's record is on screen. */}
            {recordSubjects.length > 1 ? (
              <Select value={recordSubjectId || ''} onValueChange={(v) => setRecordSubjectId(v)}>
                <SelectTrigger className="h-9 min-w-[180px] gap-1.5 bg-background" data-testid="records-subject-select">
                  <BookOpen className="h-3.5 w-3.5 text-brand-turquoise" strokeWidth={1.5} aria-hidden="true" />
                  <SelectValue placeholder={t('selectSubject')} />
                </SelectTrigger>
                <SelectContent>
                  {recordSubjects.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      <span className="flex items-center gap-2">
                        {s.name || s.id}
                        {s.has_grades && (
                          <span className="h-1.5 w-1.5 rounded-full bg-brand-turquoise inline-block" aria-hidden="true" />
                        )}
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : recordSubjects.length === 1 ? (
              <Badge variant="secondary" className="gap-1.5 h-7 px-2.5 font-cairo text-xs" data-testid="records-subject-badge">
                <BookOpen className="h-3.5 w-3.5 text-brand-turquoise" strokeWidth={1.5} aria-hidden="true" />
                {recordSubjects[0].name || recordSubjects[0].id}
              </Badge>
            ) : null}
            <div className="text-xs text-muted-foreground font-cairo">
              {students.length} طالب
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Button size="sm" variant="outline" className="gap-1.5 font-cairo" onClick={() => fileInputRef.current?.click()}>
              <FileSpreadsheet className="h-3.5 w-3.5" />
              {t('importGrades')}
            </Button>
            <Button size="sm" variant="outline" className="gap-1.5 font-cairo" onClick={() => setShowColumnSettings(true)}>
              <Settings className="h-3.5 w-3.5" />
              إعدادات الأعمدة
            </Button>
            <Button
              size="sm"
              className="gap-1.5 font-cairo bg-brand-turquoise hover:bg-brand-turquoise/90 text-white"
              onClick={() => setShowQuickAddCol(true)}
            >
              <Plus className="h-3.5 w-3.5" />
              إضافة عمود
            </Button>
          </div>
        </div>

        {gradesLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
          </div>
        ) : (
          <Card className="overflow-hidden">
            {(() => {
              // Adapt class-detail data shapes to the shared FollowupGradesTable contract.
              const adaptedColumns = gradeColumns.map(c => ({
                id: c.id,
                name: getColumnDisplay(c),
                group: c.column_type === 'exams' ? 'exams' : 'coursework',
                maxGrade: c.max_grade,
                hidden: c.visible === false,
              }));
              const adaptedGrades = {};
              filteredStudents.forEach(s => {
                const row = {};
                gradeColumns.forEach(c => {
                  const raw = studentGrades[`${s.id}_${c.id}`];
                  if (raw !== undefined && raw !== '') row[c.id] = raw;
                });
                adaptedGrades[s.id] = row;
              });
              return (
                <FollowupGradesTable
                  students={filteredStudents}
                  columns={adaptedColumns}
                  gradesData={adaptedGrades}
                  onGradeChange={(sid, cid, value) => handleGradeChange(sid, cid, value)}
                  onStudentClick={setProfileStudent}
                  emptyMessage={t('noStudents')}
                  t={t}
                />
              );
            })()}
          </Card>
        )}

        {/* Footer chip — visible columns count */}
        <div className="flex items-center justify-end px-1">
          <span className="text-xs text-muted-foreground font-cairo">
            {visibleColCount} عمود ظاهر
          </span>
        </div>
      </div>
    );
  };

  const resetNewColumnForm = () => {
    setNewColName('');
    setNewColType('coursework');
    setNewColMax(10);
  };

  const renderQuickAddColumnDialog = () => (
    <Dialog
      open={showQuickAddCol}
      onOpenChange={(o) => {
        setShowQuickAddCol(o);
        if (!o) resetNewColumnForm();
      }}
    >
      <DialogContent className="max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
        <DialogHeader>
          <DialogTitle className="font-cairo flex items-center gap-2">
            <Plus className="h-5 w-5 text-brand-turquoise" />
            إضافة عمود جديد
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div>
            <label className="block text-xs font-cairo font-semibold mb-1">اسم العمود</label>
            <Input
              type="text"
              value={newColName}
              onChange={(e) => setNewColName(e.target.value)}
              placeholder="مثال: نشاط صفي"
              onKeyDown={(e) => e.key === 'Enter' && handleAddColumn()}
            />
          </div>
          <div>
            <label className="block text-xs font-cairo font-semibold mb-1">نوع العمود</label>
            <Select value={newColType} onValueChange={setNewColType}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="coursework">أعمال سنة</SelectItem>
                <SelectItem value="exams">اختبارات</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="block text-xs font-cairo font-semibold mb-1">الدرجة القصوى</label>
            <Input
              type="number"
              min={1}
              max={100}
              value={newColMax}
              onChange={(e) => setNewColMax(parseInt(e.target.value) || 10)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            size="sm"
            onClick={() => { setShowQuickAddCol(false); resetNewColumnForm(); }}
          >
            {t('cancel') || 'إلغاء'}
          </Button>
          <Button size="sm" onClick={handleAddColumn} className="bg-brand-turquoise hover:bg-brand-turquoise/90 text-white">
            {t('save') || 'حفظ'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );

  const renderAttendanceTab = () => (
    <InlineAttendanceTable
      classId={classId}
      students={students}
      classData={classData}
    />
  );

  const renderAddLessonDialog = () => {
    const cs = lessonMeta?.curriculum_start_date;
    const ce = lessonMeta?.curriculum_end_date;
    const hasCurriculumRange = !!(cs && ce);
    const savable = !(datesOutOfRange && (!overrideChecked || overrideReason.trim().length < 10));

    return (
      <>
        <Dialog open={showAddLesson} onOpenChange={(open) => {
          if (!open) { resetAddLessonForm(); }
          setShowAddLesson(open);
        }}>
          <DialogContent className="max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
            <DialogHeader>
              <DialogTitle className="font-cairo flex items-center gap-2">
                {lessonDialogMode === 'edit' ? (
                  <Edit3 className="h-5 w-5 text-brand-turquoise" aria-hidden="true" />
                ) : (
                  <Plus className="h-5 w-5 text-brand-turquoise" aria-hidden="true" />
                )}
                {lessonDialogMode === 'edit' ? t('editLesson') : t('addLesson')}
              </DialogTitle>
            </DialogHeader>

            {lessonMetaLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-brand-turquoise" aria-hidden="true" />
              </div>
            ) : (
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label className="font-cairo text-sm">{t('lessonTitle')}</Label>
                  <Input
                    value={newLessonTitle}
                    onChange={(e) => setNewLessonTitle(e.target.value)}
                    placeholder={t('lessonTitle')}
                    onKeyDown={(e) => e.key === 'Enter' && savable && handleSubmitLesson()}
                  />
                </div>

                <div className="space-y-2">
                  <Label className="font-cairo text-sm">{t('weekNumber')}</Label>
                  <Input
                    type="number"
                    min={1}
                    max={52}
                    value={newLessonWeek}
                    onChange={(e) => setNewLessonWeek(parseInt(e.target.value) || 1)}
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <Label className="font-cairo text-sm">{t('lessonStartDate')}</Label>
                    <Input
                      type="date"
                      dir="ltr"
                      value={lessonStartDate}
                      onChange={(e) => setLessonStartDate(e.target.value)}
                      className="text-start"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label className="font-cairo text-sm">{t('lessonEndDate')}</Label>
                    <Input
                      type="date"
                      dir="ltr"
                      value={lessonEndDate}
                      onChange={(e) => setLessonEndDate(e.target.value)}
                      className="text-start"
                    />
                  </div>
                </div>

                {hasCurriculumRange && (
                  <p className="text-xs text-muted-foreground font-tajawal">
                    {t('curriculumRange')}: <span dir="ltr" className="inline-block">{cs} — {ce}</span>
                  </p>
                )}

                {datesOutOfRange && (
                  <div className="space-y-3">
                    <div className="flex items-start gap-2 p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
                      <AlertTriangle className="h-4 w-4 text-amber-500 flex-shrink-0 mt-0.5" aria-hidden="true" />
                      <p className="text-sm text-amber-700 dark:text-amber-300 font-tajawal">{t('datesOutsideCurriculumRange')}</p>
                    </div>

                    <div className="flex items-center gap-2">
                      <Checkbox
                        id="override-checkbox"
                        checked={overrideChecked}
                        onCheckedChange={(v) => setOverrideChecked(!!v)}
                      />
                      <Label htmlFor="override-checkbox" className="font-cairo text-sm cursor-pointer">
                        {t('overrideCurriculumWarning')}
                      </Label>
                    </div>

                    {overrideChecked && (
                      <div className="space-y-1">
                        <Label className="font-cairo text-sm">{t('overrideReason')}</Label>
                        <textarea
                          ref={overrideReasonRef}
                          value={overrideReason}
                          onChange={(e) => setOverrideReason(e.target.value)}
                          placeholder={t('overrideReasonPlaceholder')}
                          rows={3}
                          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-tajawal resize-none focus:outline-none focus:ring-2 focus:ring-ring"
                        />
                        {overrideReason.trim().length > 0 && overrideReason.trim().length < 10 && (
                          <p className="text-xs text-red-500 font-tajawal">{t('overrideReasonTooShort')}</p>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            <DialogFooter>
              <Button variant="outline" onClick={() => { resetAddLessonForm(); setShowAddLesson(false); }}>{t('cancel')}</Button>
              <Button
                className="bg-brand-navy hover:bg-brand-navy-dark text-white"
                onClick={handleSubmitLesson}
                disabled={!newLessonTitle.trim() || lessonMetaLoading || !savable}
              >
                {lessonDialogMode === 'edit' ? (
                  <Check className="h-4 w-4 me-2" aria-hidden="true" />
                ) : (
                  <Plus className="h-4 w-4 me-2" aria-hidden="true" />
                )}
                {lessonDialogMode === 'edit' ? t('save') : t('add')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* 409 Curriculum date conflict dialog */}
        <Dialog open={showConflictDialog} onOpenChange={setShowConflictDialog}>
          <DialogContent className="max-w-sm" dir={isRTL ? 'rtl' : 'ltr'}>
            <DialogHeader>
              <DialogTitle className="font-cairo flex items-center gap-2 text-amber-600">
                <AlertTriangle className="h-5 w-5" aria-hidden="true" />
                {t('curriculumDateConflict')}
              </DialogTitle>
            </DialogHeader>
            <p className="text-sm font-tajawal text-muted-foreground py-2">{t('curriculumDateConflictDesc')}</p>
            <DialogFooter className="flex-col sm:flex-row gap-2">
              <Button
                variant="outline"
                className="w-full sm:w-auto"
                onClick={() => setShowConflictDialog(false)}
              >
                {t('editDates')}
              </Button>
              <Button
                className="w-full sm:w-auto bg-amber-600 hover:bg-amber-700 text-white"
                onClick={() => {
                  setShowConflictDialog(false);
                  setOverrideChecked(true);
                  setTimeout(() => overrideReasonRef.current?.focus(), 100);
                }}
              >
                {t('overrideWithReason')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </>
    );
  };

  const renderColumnSettings = () => (
    <Dialog open={showColumnSettings} onOpenChange={setShowColumnSettings}>
      <DialogContent className="max-w-md max-h-[80vh] overflow-y-auto" dir={isRTL ? 'rtl' : 'ltr'}>
        <DialogHeader>
          <DialogTitle className="font-cairo flex items-center gap-2">
            <Settings className="h-5 w-5 text-brand-turquoise" />
            {t('columnSettings')}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            {[...gradeColumns].sort((a, b) => (a.order || 0) - (b.order || 0)).map((col, idx) => (
              <div key={col.id} className="p-2.5 rounded-lg border bg-card space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Switch
                      checked={col.visible !== false}
                      onCheckedChange={() => handleToggleColumnVisibility(col)}
                    />
                    <div>
                      <p className="text-sm font-medium font-cairo">{getColumnDisplay(col)}</p>
                      <p className="text-[10px] text-muted-foreground">
                        {col.column_type === 'exams' ? t('exams') : t('coursework')}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-0.5">
                    <Button size="sm" variant="ghost" className="h-7 w-7 p-0" disabled={idx === 0}
                      onClick={() => handleReorderColumn(col, 'up')}>
                      <ChevronUp className="h-3.5 w-3.5" />
                    </Button>
                    <Button size="sm" variant="ghost" className="h-7 w-7 p-0" disabled={idx === gradeColumns.length - 1}
                      onClick={() => handleReorderColumn(col, 'down')}>
                      <ChevronDown className="h-3.5 w-3.5" />
                    </Button>
                    <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={() => handleDeleteColumn(col.id)}>
                      <Trash2 className="h-3.5 w-3.5 text-red-400" />
                    </Button>
                  </div>
                </div>
                <div className="flex items-center gap-2 ps-10">
                  <Label className="text-[11px] text-muted-foreground whitespace-nowrap">{t('maxGrade')}:</Label>
                  {editingCol === col.id ? (
                    <div className="flex items-center gap-1">
                      <Input
                        type="number" min={1} max={100} value={editingColMax}
                        onChange={(e) => setEditingColMax(parseFloat(e.target.value) || 10)}
                        className="h-7 w-16 text-sm text-center"
                      />
                      <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={() => handleEditColumnMax(col)}>
                        <Check className="h-3 w-3 text-emerald-500" />
                      </Button>
                      <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={() => setEditingCol(null)}>
                        <X className="h-3 w-3" />
                      </Button>
                    </div>
                  ) : (
                    <button
                      className="text-sm font-medium text-blue-600 hover:underline"
                      onClick={() => { setEditingCol(col.id); setEditingColMax(col.max_grade); }}
                    >
                      {col.max_grade}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="border-t border-border pt-4 space-y-3">
            <p className="text-sm font-medium font-cairo">{t('addColumn')}</p>
            <div className="space-y-2">
              <Input
                placeholder={t('columnName')}
                value={newColName}
                onChange={(e) => setNewColName(e.target.value)}
              />
              <div className="grid grid-cols-2 gap-2">
                <Select value={newColType} onValueChange={setNewColType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="coursework">{t('coursework')}</SelectItem>
                    <SelectItem value="exams">{t('exams')}</SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  type="number"
                  min={1}
                  max={100}
                  value={newColMax}
                  onChange={(e) => setNewColMax(parseInt(e.target.value) || 10)}
                  placeholder={t('maxGrade')}
                />
              </div>
              <Button className="w-full bg-brand-navy hover:bg-brand-navy-dark text-white" onClick={handleAddColumn}>
                <Plus className="h-4 w-4 me-2" />
                {t('addColumn')}
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );

  if (error) {
    return (
      <Sidebar>
        <div className="min-h-screen bg-gray-50 dark:bg-gray-900 flex items-center justify-center p-4" dir={isRTL ? 'rtl' : 'ltr'}>
          <Card className="max-w-md w-full rounded-2xl border-0 shadow-sm">
            <CardContent className="py-12 text-center">
              <AlertTriangle className="h-16 w-16 mx-auto mb-4 text-red-400" strokeWidth={1.5} aria-hidden="true" />
              <h3 className="font-bold text-lg text-foreground mb-4 font-cairo">{t('couldNotLoadData')}</h3>
              <div className="flex items-center justify-center gap-3">
                <Button onClick={fetchClassData} className="gap-2">
                  <RefreshCw className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />
                  {t('retry')}
                </Button>
                <Button variant="outline" onClick={() => navigate('/teacher/classes')} className="gap-2">
                  <ChevronLeft className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />
                  {t('goBack')}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </Sidebar>
    );
  }

  return (
    <Sidebar>
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="sticky top-0 z-20 bg-white/90 dark:bg-gray-900/90 backdrop-blur-xl border-b border-border/50 shadow-sm">
          <div className="px-4 sm:px-6 py-4">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-3">
                <Button variant="ghost" size="icon" className="h-9 w-9" onClick={() => navigate('/teacher/classes')}>
                  <ArrowRight className="h-5 w-5" />
                </Button>
                <div className={`w-10 h-10 rounded-xl ${gc} flex items-center justify-center shadow-md`}>
                  <GraduationCap className="h-5 w-5 text-white" />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-brand-navy dark:text-brand-turquoise font-cairo">
                    {classData?.name || t('class')}
                  </h1>
                  <p className="text-sm text-muted-foreground">
                    {classData?.grade_name || ''} {classData?.student_count ? `• ${classData.student_count} ${t('students')}` : ''}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="h-9 gap-1.5 font-cairo"
                  onClick={openSessionSettings}
                  title={t('sessionSettings')}
                  aria-label={t('sessionSettings')}
                >
                  <Settings className="h-4 w-4" />
                  <span className="hidden sm:inline text-xs">{t('sessionSettings')}</span>
                </Button>
                <Button variant="outline" size="sm" className="h-9" onClick={fetchClassData} disabled={loading}>
                  <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                </Button>
              </div>
            </div>
          </div>

          <div className="px-4 sm:px-6 flex gap-0 border-t border-border/30">
            {[
              { key: 'curriculum', label: t('curriculumPlan'), icon: BookOpen },
              { key: 'records', label: t('studentRecords'), icon: ClipboardCheck },
              { key: 'attendance', label: t('attendanceLog') || 'الحضور والغياب', icon: Calendar },
              ...(isHostOfClass
                ? [{ key: 'collaborators', label: t('collabTabTitle'), icon: Users }]
                : []),
            ].map(tab => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`px-4 sm:px-5 py-2.5 text-sm font-medium font-cairo transition-colors relative ${
                  activeTab === tab.key
                    ? 'text-brand-navy dark:text-brand-turquoise'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <span className="flex items-center gap-1.5">
                  <tab.icon className="h-4 w-4" />
                  <span className="hidden sm:inline">{tab.label}</span>
                </span>
                {activeTab === tab.key && (
                  <span className="absolute bottom-0 inset-x-0 h-0.5 bg-brand-turquoise rounded-full" />
                )}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3">
            <Loader2 className="h-10 w-10 animate-spin text-brand-turquoise" />
            <p className="text-sm text-muted-foreground font-tajawal">{t('loading2')}</p>
          </div>
        ) : (
          /* pb-24 keeps the last curriculum-row edit/delete actions clear of
             the global Hakim launcher zone (bottom inline-end corner). */
          <div className="px-4 sm:px-6 pt-4 pb-24 space-y-4">
            <div className="flex items-center gap-3 p-3 rounded-2xl bg-violet-50/80 dark:bg-violet-950/30 border border-violet-100/50 dark:border-violet-800/30">
              <HakimPresence size="xs" showMessage={true} messagePosition="bottom" />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: t('students'), value: classData?.student_count || 0, icon: Users, iconBg: 'bg-blue-500 dark:bg-blue-600', light: 'bg-blue-50 dark:bg-blue-900/20' },
                { label: t('attendance2'), value: `${classData?.attendance_rate || 0}%`, icon: ClipboardCheck, iconBg: 'bg-emerald-500 dark:bg-emerald-600', light: 'bg-emerald-50 dark:bg-emerald-900/20' },
                { label: t('participation'), value: `${classData?.participation_rate || 0}%`, icon: Activity, iconBg: 'bg-purple-500 dark:bg-purple-600', light: 'bg-purple-50 dark:bg-purple-900/20' },
                { label: t('perWeek'), value: classData?.weekly_periods || 0, icon: Calendar, iconBg: 'bg-amber-500 dark:bg-amber-600', light: 'bg-amber-50 dark:bg-amber-900/20' },
              ].map(({ label, value, icon: Icon, iconBg, light }) => (
                <Card key={label} className={`${light} border-0 shadow-sm`}>
                  <CardContent className="p-3">
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-xl ${iconBg} flex items-center justify-center shadow-md flex-shrink-0`}>
                        <Icon className="h-5 w-5 text-white" />
                      </div>
                      <div>
                        <div className="text-xl font-bold text-foreground">{value}</div>
                        <div className="text-[10px] text-muted-foreground">{label}</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>

            {activeTab === 'curriculum' && renderCurriculumTab()}
            {activeTab === 'records' && renderRecordsTab()}
            {activeTab === 'attendance' && renderAttendanceTab()}
            {activeTab === 'collaborators' && isHostOfClass && <CollaboratorsTab classId={classId} />}
          </div>
        )}
      </div>

      {renderAddLessonDialog()}
      {renderColumnSettings()}
      {renderQuickAddColumnDialog()}

      <TeacherStudentProfileDialog
        student={profileStudent}
        open={!!profileStudent}
        onClose={() => setProfileStudent(null)}
        classLabel={classData?.grade_name}
      />

      {/* Details for a Smart Lesson Plan Assistant plan saved to this class —
          same shared dialog as the assistant page, so edits stay in sync. */}
      <LessonPlanDetailsDialog
        plan={assistantPlanDialog}
        open={!!assistantPlanDialog}
        onOpenChange={(open) => { if (!open) setAssistantPlanDialog(null); }}
        classes={classData ? [classData] : []}
        onSaved={fetchCurriculum}
      />

      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        accept=".xlsx,.xls,.csv,.pdf"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) toast.success(t('importData') + ': ' + file.name);
          if (fileInputRef.current) fileInputRef.current.value = '';
        }}
      />

      {/* إعدادات الحصة — same master dialog as the live lesson (Group A
          تعريفات العناصر + Group B تكوين الحصة), editing the shared
          class+subject session_settings template. */}
      <SidebarSettingsDialog
        open={showSidebarSettings}
        onOpenChange={(open) => {
          setShowSidebarSettings(open);
          // Persist تعريفات العناصر edits on close — those tabs have no Save
          // button. Guarded so a pre-hydration close can't clobber the template.
          if (!open) saveSessionTemplate({ silent: true }).catch(() => {});
        }}
        isRTL={isRTL}
        t={t}
        evaluationItems={customEvaluationItems}
        onAddEvaluationItem={(item) => setCustomEvaluationItems((prev) => [...prev, item])}
        onRemoveEvaluationItem={(id) => setCustomEvaluationItems((prev) => prev.filter((x) => x.id !== id))}
        positiveBehaviours={[
          // Built-in defaults render (read-only) alongside custom entries —
          // the same defaults ∪ custom union the live-lesson dialog shows.
          ...BEHAVIOURS.positive.map((b) => ({
            id: b.id,
            name: b.labelKey ? (t(b.labelKey) || b.label) : b.label,
            points: Number(behaviourScoreOverrides[b.id]) > 0
              ? Number(behaviourScoreOverrides[b.id])
              : (Math.abs(Number(b.points)) || 0),
            removable: false,
          })),
          ...customPositiveBehaviours,
        ]}
        negativeBehaviours={[
          ...BEHAVIOURS.negative.map((b) => ({
            id: b.id,
            name: b.labelKey ? (t(b.labelKey) || b.label) : b.label,
            points: Number(behaviourScoreOverrides[b.id]) > 0
              ? Number(behaviourScoreOverrides[b.id])
              : (Math.abs(Number(b.points)) || 0),
            removable: false,
          })),
          ...customNegativeBehaviours,
        ]}
        onAddPositiveBehaviour={(item) => setCustomPositiveBehaviours((prev) => [...prev, item])}
        onAddNegativeBehaviour={(item) => setCustomNegativeBehaviours((prev) => [...prev, item])}
        onRemovePositiveBehaviour={(id) => setCustomPositiveBehaviours((prev) => prev.filter((x) => (typeof x === 'string' ? `custom_${x}` !== id : x.id !== id)))}
        onRemoveNegativeBehaviour={(id) => setCustomNegativeBehaviours((prev) => prev.filter((x) => (typeof x === 'string' ? `custom_${x}` !== id : x.id !== id)))}
        onUpdateBehaviourScore={updateBehaviourScore}
        skillEnabled={skillEnabled}
        onToggleSkillEnabled={setSkillEnabled}
        skillTypes={skillTypes}
        customSkills={customSkills}
        onAddCustomSkill={(name) => setCustomSkills((prev) => [...prev, name])}
        onRemoveCustomSkill={(idx) => setCustomSkills((prev) => prev.filter((_, j) => j !== idx))}
        onUpdateSkillType={updateSkillType}
        onUpdateCustomSkill={(idx, points) => setCustomSkills((prev) => prev.map((s, j) => {
          if (j !== idx) return s;
          if (typeof s === 'string') return { name: s, points };
          return { ...s, points };
        }))}
        sessionConfig={{
          showSubjectPicker: true,
          subjectsList: recordSubjects.map((s) => ({ id: s.id, name: s.name })),
          subjectsLoading: settingsSubjectsLoading,
          subjectId: settingsSubjectId,
          onSubjectIdChange: (id) => {
            setSettingsSubjectId(id);
            loadSessionTemplate(id);
          },
          participationEnabled,
          onParticipationEnabledChange: setParticipationEnabled,
          homeworkEnabled,
          onHomeworkEnabledChange: setHomeworkEnabled,
          homeworkViewMode,
          onHomeworkViewModeChange: setHomeworkViewMode,
          recitationEnabled,
          onRecitationEnabledChange: setRecitationEnabled,
          recitationMaxAttempts,
          onRecitationMaxAttemptsChange: setRecitationMaxAttempts,
          followupColumns,
          onFollowupColumnsChange: setFollowupColumns,
          showAddOtherItems,
          onShowAddOtherItemsChange: setShowAddOtherItems,
          participationScores,
          onParticipationScoresChange: setParticipationScores,
          streakBonusEnabled,
          onStreakBonusEnabledChange: setStreakBonusEnabled,
          onSave: () => saveSessionTemplate(),
          saving: savingSettings,
        }}
      />

    </Sidebar>
  );
}
