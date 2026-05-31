import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Checkbox } from '../../components/ui/checkbox';
import { Progress } from '../../components/ui/progress';
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
  Users, BookOpen, Search, RefreshCw, Loader2,
  GraduationCap, ClipboardCheck, BarChart3, Calendar, Hourglass, Sparkles,
  TrendingUp, LayoutGrid, List, Clock, Play,
  ChevronLeft, Star, AlertTriangle, CheckCircle2,
  ArrowUpDown, Settings, Plus, FileSpreadsheet,
  FileImage, FileText, Upload, Info, X, Pencil, Trash2, Save
} from 'lucide-react';
import SessionsManageTab from './SessionsManageTab';
import StandbyTab from './StandbyTab';
// 2026-05-18 — Lesson planner was relocated from the main sidebar
// into a tab here. We import the named headless panel (NOT the
// default page export) so we don't render a nested Sidebar inside
// the Classes-page layout. Same Panel/Page split used for the IT
// activity-log relocation into Account Settings (same day).
import { LessonPlannerPanel } from './LessonPlannerPage';
// 2026-05-18 — Embedded "المواد" tab (IT-only). The standalone
// /teacher/subjects sidebar entry has been retired; the route now
// redirects here with ?tab=subjects so all teacher-slice surfaces
// (classes / sessions / lesson-planner / schedule / subjects) live
// under one mounted page shell. Same backend contract — no
// permission widening.
import { TeacherSubjectsPanel } from './TeacherSubjectsPage';
// 2026-05-19 — IA refactor: the standalone "استيراد الطلاب" and
// "الاستيراد الجماعي" sidebar entries were merged into a single
// "استيراد البيانات" tab here. We import the named headless panel
// (NOT the default page export) so the embedded tab doesn't render
// a nested Sidebar / page-header shell. Backend contracts, RBAC
// slices and MFA step-up envelopes are unchanged — the tab is purely
// a frontend IA refactor.
//
// 2026-05-19 (later) — The three time-management tabs (schedule /
// personal calendar / schedule settings) were extracted into the
// dedicated `/teacher/planning` hub (TimeManagementHubPage), so the
// `WorkspaceSchedulePanel` and `TeacherPersonalCalendarPanel`
// imports were removed alongside the related state and tab buttons.
import { BulkImportPanel } from './BulkImportPage';
// 2026-05-19 — IT-only "الطلاب" tab. Embeds the existing student
// directory (CRUD, class filter, edit/delete, add-student wizard)
// from TeacherStudentsPage as a sub-tab inside فصولي so imported
// students from the bulk-import flow are immediately viewable and
// assignable to classes without leaving the page. Headless variant
// skips the nested Sidebar shell; backend RBAC / quotas unchanged.
import { TeacherStudentsPanel } from './TeacherStudentsPage';
import SidebarSettingsDialog from '../../components/teacher/SidebarSettingsDialog';
import { ResponsiveTable } from '../../components/ui/ResponsiveTable';

import { useTranslation } from '../../contexts/ThemeContext';

const DAY_KEYS = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday'];

/** Normalize API error bodies: raw FastAPI `{detail}` or server `{success,error}`. */
function extractFastApiDetailFromResponseData(data) {
  if (!data || typeof data !== 'object') return '';
  if (typeof data.detail === 'string') return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail
      .map((e) => (e && typeof e === 'object' && e.msg != null ? String(e.msg) : String(e)))
      .filter(Boolean)
      .join(' ');
  }
  if (data.detail && typeof data.detail === 'object' && data.detail.message != null) {
    return String(data.detail.message);
  }
  const err = data.error;
  if (err && typeof err === 'object') {
    if (typeof err.message === 'string' && err.message.trim()) return err.message;
    const d = err.detail;
    if (typeof d === 'string') return d;
    if (d && typeof d === 'object' && d.message != null) return String(d.message);
  }
  const ve = data.meta?.validation_errors;
  if (Array.isArray(ve) && ve.length) {
    return ve.map((e) => (e && e.message) || '').filter(Boolean).join(' ');
  }
  return '';
}

// 2026-05-19 — The IT_SETTINGS_WEEKDAYS / IT_SETTINGS_TIMEZONES
// constants moved with the schedule-settings tab into the
// `/teacher/planning` hub (TimeManagementHubPage).

const GRADE_COLORS = {
  '1': { bg: 'from-sky-500 to-sky-600', light: 'bg-sky-50 dark:bg-sky-900/20', text: 'text-sky-700 dark:text-sky-300', border: 'border-sky-200 dark:border-sky-800' },
  '2': { bg: 'from-emerald-500 to-emerald-600', light: 'bg-emerald-50 dark:bg-emerald-900/20', text: 'text-emerald-700 dark:text-emerald-300', border: 'border-emerald-200 dark:border-emerald-800' },
  '3': { bg: 'from-violet-500 to-violet-600', light: 'bg-violet-50 dark:bg-violet-900/20', text: 'text-violet-700 dark:text-violet-300', border: 'border-violet-200 dark:border-violet-800' },
  '4': { bg: 'from-amber-500 to-amber-600', light: 'bg-amber-50 dark:bg-amber-900/20', text: 'text-amber-700 dark:text-amber-300', border: 'border-amber-200 dark:border-amber-800' },
  '5': { bg: 'from-rose-500 to-rose-600', light: 'bg-rose-50 dark:bg-rose-900/20', text: 'text-rose-700 dark:text-rose-300', border: 'border-rose-200 dark:border-rose-800' },
  '6': { bg: 'from-indigo-500 to-indigo-600', light: 'bg-indigo-50 dark:bg-indigo-900/20', text: 'text-indigo-700 dark:text-indigo-300', border: 'border-indigo-200 dark:border-indigo-800' },
};

const getGradeColor = (grade) => GRADE_COLORS[String(grade)] || GRADE_COLORS['1'];

export default function TeacherClassesPage() {
  const { user, api, isRTL, token, fetchPermissions } = useAuth();
  // 2026-05-18 — Mirror the Sidebar's Phase 0 §4.B-6 permission gate
  // for the new "lesson-planner" tab. Items that require a backend
  // RBAC slice (here: `ai.lesson_plans`) are hidden until the lazy
  // /auth/me/permissions fetch resolves. Fail-closed while loading.
  const [perms, setPerms] = useState(null);
  useEffect(() => {
    let cancelled = false;
    if (!token || !fetchPermissions) return undefined;
    (async () => {
      try {
        const data = await fetchPermissions();
        if (cancelled) return;
        const list = Array.isArray(data?.permissions)
          ? data.permissions
          : Array.isArray(data?.effective_permissions)
            ? data.effective_permissions
            : Array.isArray(data) ? data : [];
        setPerms(new Set(list.map((p) => String(p))));
      } catch {
        if (!cancelled) setPerms(new Set());
      }
    })();
    return () => { cancelled = true; };
  }, [token, fetchPermissions]);
  const canUseLessonPlanner = !!(perms && perms.has('ai.lesson_plans'));
  // 2026-05-19 — IA refactor: the "استيراد البيانات" and "تقويمي الشخصي"
  // tabs replace standalone sidebar entries that were each permission-
  // gated. Mirror those gates here so merging them into TeacherClasses
  // doesn't widen the FE authorization surface for users who lack the
  // underlying RBAC slices (the redirect routes still gate too).
  //  - import tab: shown if the user has EITHER of the two bulk-import
  //    permissions the retired sidebar entries required, matching
  //    BulkImportPanel's four sub-tab surface.
  //  - calendar tab: shown only when `events.author_own` is granted,
  //    matching the retired /teacher/calendar sidebar entry.
  const canBulkImport = !!(perms && (
    perms.has('students.bulk_import_workspace') ||
    perms.has('classes.bulk_import_workspace')
  ));
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const _rawTab = searchParams.get('tab');
  // 2026-05-18: the "حصص الانتظار" (standby) tab is hidden for
  // Independent-Teacher accounts because the feature relies on
  // school-admin assignment which doesn't exist in workspace mode.
  // The components and API surface are intentionally KEPT so the
  // feature can be re-enabled later — we only suppress the entry
  // point + URL deep-link here.
  const _isITUser = user?.role === 'independent_teacher';
  // 2026-05-18 — `lesson-planner` is an IT-only tab. The activeTab
  // resolver mirrors the standby-tab IT guard: if a non-IT user
  // somehow lands on ?tab=lesson-planner we silently fall back to
  // the default "classes" view rather than rendering a forbidden
  // panel. (Backend RBAC still gates the underlying AI route.)
  // 2026-05-19 — The legacy ?tab=schedule|calendar|settings deep
  // links were extracted into `/teacher/planning`. A redirect effect
  // below rewrites them in-place so existing bookmarks land on the
  // new hub instead of falling through to the classes default.
  const activeTab = _rawTab === 'sessions' ? 'sessions'
    : (_rawTab === 'standby' && !_isITUser) ? 'standby'
    : (_rawTab === 'lesson-planner' && _isITUser && canUseLessonPlanner) ? 'lesson-planner'
    // 2026-05-18 — IT-only "المواد" tab. Backend /subjects CRUD is
    // pinned to school_id == itw_{user_id}; non-IT users have no
    // workspace subjects to manage, so we silently coerce back.
    : (_rawTab === 'subjects' && _isITUser) ? 'subjects'
    // 2026-05-19 — IT-only "استيراد البيانات" tab. Merges the two
    // retired sidebar entries into one unified import surface.
    : (_rawTab === 'import' && _isITUser && canBulkImport) ? 'import'
    // 2026-05-19 — IT-only "الطلاب" tab. Surfaces the workspace
    // student directory inline so imported students are immediately
    // visible / editable / assignable to classes.
    : (_rawTab === 'students' && _isITUser) ? 'students'
    : 'classes';
  const [loading, setLoading] = useState(true);
  const [classes, setClasses] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState('card');
  const [gradeFilter, setGradeFilter] = useState('all');
  const [sortBy, setSortBy] = useState('grade');

  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [settingsSubject, setSettingsSubject] = useState('');
  const [settingsLoading, setSettingsLoading] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);
  // Snake-case keys mirror the `/teacher/{id}/session-settings` payload contract
  // so we can spread them directly into the PUT body without remapping.
  const [sessionConfig, setSessionConfig] = useState({
    participation_enabled: true,
    homework_enabled: false,
    homework_mode: 'didnt_submit',
    recitation_enabled: false,
    recitation_attempts: 1,
    skills_enabled: false,
    custom_skills: [],
  });
  // Transient local state for the canonical SidebarSettingsDialog's Group A
  // tabs (evaluation items + behaviours). The current /teacher/{id}/session-settings
  // contract doesn't persist these, but we still back them with real state so
  // the add/remove interactions work identically to the Interactive Class flow
  // — i.e. the UI is fully functional within the open session, even if the
  // values are not yet persisted server-side.
  const [classEvaluationItems, setClassEvaluationItems] = useState([]);
  const [classPositiveBehaviours, setClassPositiveBehaviours] = useState([]);
  const [classNegativeBehaviours, setClassNegativeBehaviours] = useState([]);

  const [showAddClassDialog, setShowAddClassDialog] = useState(false);
  const [addClassForm, setAddClassForm] = useState({ name: '', grade: '', section: '', weekly_count: 5 });
  // Workspace-mode (Independent-Teacher) form state. Mirrors spec
  // §5.3: Arabic name + free-text grade label + subject (from
  // workspace's existing subjects) + capacity (≤ 50, default 30).
  const [workspaceClassForm, setWorkspaceClassForm] = useState({
    name_ar: '', grade_label: '', subject_id: '', capacity: 30,
  });
  const [addingClass, setAddingClass] = useState(false);
  const [gradeOptions, setGradeOptions] = useState([]);
  // Subject options for the IT workspace dialog. Sourced from /subjects
  // which is already tenant-scoped server-side via `current_user.tenant_id`.
  const [workspaceSubjects, setWorkspaceSubjects] = useState([]);
  // Tracks a failed /subjects load for the Add-Class dialog so the subject
  // dropdown can surface an inline error + retry instead of a blank list.
  const [workspaceSubjectsError, setWorkspaceSubjectsError] = useState(false);
  // Subjects fetched for the Lesson Settings modal. Populated for all
  // teacher roles (not just IT) via the /subjects endpoint which is
  // already tenant-scoped server-side.
  const [subjectsForSettings, setSubjectsForSettings] = useState([]);
  const [subjectsLoading, setSubjectsLoading] = useState(false);
  // Authoritative tenant-scoped class count for the "X من 5 فصول" chip
  // (spec §5.3 step 4). Sourced from /classes (tenant-scoped server-side
  // via require_request_school_id) rather than the teacher-assignment
  // listing, so the chip never disagrees with the server-enforced quota.
  const [workspaceClassCount, setWorkspaceClassCount] = useState(null);

  const [showImportDialog, setShowImportDialog] = useState(false);
  const fileInputRef = useRef(null);
  const [importType, setImportType] = useState('');

  // 2026-05-19 — The "إعدادات الجدول" tab state (working_days,
  // periods_per_day, period_minutes, timezone, year/term labels) and
  // its GET/PUT handlers moved with the tab into TimeManagementHubPage.

  const { t } = useTranslation();
  const { nassaqError, nassaqWarning, nassaqConfirm, nassaqInfo } = useNassaqAlert();
  const [editClassDialog, setEditClassDialog] = useState(null); // { id, name, capacity }
  const [editClassSaving, setEditClassSaving] = useState(false);
  const teacherId = user?.teacher_id || user?.id;
  const isIndependentTeacher = user?.role === 'independent_teacher';

  // Non-IT teachers fall through to the existing "managed by school admin"
  // copy. The Independent-Teacher branch was removed when class creation
  // was enabled in workspace mode (Task #188 / spec §5.3).
  const friendlyTeacherWriteMessage = (fallbackKey = 'teacherActionNotAllowed') => t(fallbackKey);

  const isPermissionError = (err) => {
    const status = err?.response?.status;
    if (status === 401 || status === 403) return true;
    const detail = err?.response?.data?.detail;
    if (typeof detail === 'string') {
      const d = detail.toLowerCase();
      return d.includes('insufficient permission')
        || d.includes('not allowed')
        || d.includes('forbidden')
        || d.includes('ليس لديك صلاحية')
        || d.includes('غير مصرح');
    }
    return false;
  };

  const handleTabChange = (tab) => {
    // Guard: even if a stale link tries to navigate an IT user to the
    // standby tab, fall through to the default "classes" view rather
    // than surfacing the "ميزة غير متاحة" modal.
    const safeTab = (tab === 'standby' && _isITUser) ? 'classes'
      : (tab === 'lesson-planner' && (!_isITUser || !canUseLessonPlanner)) ? 'classes'
      : (tab === 'subjects' && !_isITUser) ? 'classes'
      : (tab === 'import' && (!_isITUser || !canBulkImport)) ? 'classes'
      : (tab === 'students' && !_isITUser) ? 'classes'
      : tab;
    setSearchParams(
      safeTab === 'sessions' ? { tab: 'sessions' }
      : safeTab === 'standby' ? { tab: 'standby' }
      : safeTab === 'lesson-planner' ? { tab: 'lesson-planner' }
      : safeTab === 'subjects' ? { tab: 'subjects' }
      : safeTab === 'import' ? { tab: 'import' }
      : safeTab === 'students' ? { tab: 'students' }
      : {}
    );
  };

  // Route guard for IT users who land on ?tab=standby via a stale
  // bookmark or external deep-link: silently rewrite the URL to the
  // default classes view so they don't sit on a blank/error state.
  useEffect(() => {
    if (_isITUser && _rawTab === 'standby') {
      setSearchParams({}, { replace: true });
    }
  }, [_isITUser, _rawTab, setSearchParams]);

  // 2026-05-19 — Back-compat redirect: the three time-management
  // tabs (schedule / calendar / settings) were extracted into the
  // dedicated `/teacher/planning` hub. Old deep links that still
  // hit `/teacher/classes?tab=schedule|calendar|settings` are
  // rewritten in-place to the new hub so bookmarks keep working.
  useEffect(() => {
    if (!_isITUser) return;
    if (_rawTab === 'schedule' || _rawTab === 'calendar' || _rawTab === 'settings') {
      navigate(`/teacher/planning?tab=${_rawTab}`, { replace: true });
    }
  }, [_isITUser, _rawTab, navigate]);

  const fetchClasses = useCallback(async () => {
    if (!teacherId) return;
    setLoading(true);
    try {
      // IT §6.7 (Task #210): an Independent-Teacher caller may also be
      // an accepted *collaborator* on classes owned by another IT
      // workspace. Surface those alongside their own classes with a
      // "shared with <host>" badge so the entry point exists.
      const [classesRes, metricsRes, sharedRes] = await Promise.all([
        api.get(`/teacher/classes/${teacherId}`),
        api.get(`/teacher/${teacherId}/class-metrics`).catch(() => ({ data: {} })),
        isIndependentTeacher
          ? api.get('/independent-teacher/workspace-collaborators/shared-with-me').catch(() => ({ data: { items: [] } }))
          : Promise.resolve({ data: { items: [] } }),
      ]);
      const classesData = classesRes.data || [];
      const metricsData = metricsRes.data || {};
      const sharedItems = (sharedRes.data?.items) || [];

      const enriched = classesData.map(cls => {
        const m = metricsData[cls.id] || {};
        return {
          ...cls,
          attendance_rate: m.attendance_rate ?? 0,
          participation_rate: m.participation_rate ?? 0,
          avg_performance: m.avg_performance ?? 0,
          total_sessions: m.total_sessions ?? 0,
        };
      });
      // Append shared classes that aren't already in the list, tagged
      // with `_collab` so the card can render the badge from
      // `t('collabSharedWithBadge')` and route to the read-only view.
      const existingIds = new Set(enriched.map(c => c.id));
      for (const it of sharedItems) {
        if (!it?.class_id || existingIds.has(it.class_id)) continue;
        enriched.push({
          id: it.class_id,
          name: it.class_name || it.class_id,
          _collab: { mode: it.scope?.mode || 'read', host_school_id: it.host_school_id, host_workspace_name: it.host_workspace_name || '' },
          attendance_rate: 0, participation_rate: 0, avg_performance: 0, total_sessions: 0,
        });
      }
      setClasses(enriched);
    } catch (error) {
      console.error('Error fetching classes:', error);
      nassaqError(t('errorLoadingClasses'));
    } finally {
      setLoading(false);
    }
  }, [api, teacherId, nassaqError, t]);

  useEffect(() => {
    fetchClasses();
  }, [fetchClasses]);

  const allSubjects = useMemo(() => {
    const subjectMap = new Map();
    classes.forEach(cls => {
      if (cls.subjects_data) {
        cls.subjects_data.forEach(s => {
          if (s.id && s.name) subjectMap.set(s.id, s.name);
        });
      } else if (cls.subjects && cls.subject_ids) {
        cls.subjects.forEach((name, idx) => {
          const id = cls.subject_ids?.[idx];
          if (id) subjectMap.set(id, name);
        });
      }
    });
    return Array.from(subjectMap, ([id, name]) => ({ id, name }));
  }, [classes]);

  const loadSessionSettings = useCallback(async (subjectId) => {
    if (!subjectId || !teacherId) return;
    setSettingsLoading(true);
    try {
      const res = await api.get(`/teacher/${teacherId}/session-settings?subject_id=${subjectId}`);
      if (res.data && !Array.isArray(res.data)) {
        setSessionConfig({
          participation_enabled: res.data.participation_enabled ?? true,
          homework_enabled: res.data.homework_enabled ?? false,
          homework_mode: res.data.homework_mode ?? 'didnt_submit',
          recitation_enabled: res.data.recitation_enabled ?? false,
          recitation_attempts: res.data.recitation_attempts ?? 1,
          skills_enabled: res.data.skills_enabled ?? false,
          custom_skills: res.data.custom_skills ?? [],
        });
      } else {
        setSessionConfig({
          participation_enabled: true,
          homework_enabled: false,
          homework_mode: 'didnt_submit',
          recitation_enabled: false,
          recitation_attempts: 1,
          skills_enabled: false,
          custom_skills: [],
        });
      }
    } catch (err) {
      console.error('Error loading session settings:', err);
      nassaqError(t('errorLoadingSessionSettings'));
    } finally {
      setSettingsLoading(false);
    }
  }, [api, teacherId, nassaqError, t]);

  const handleSubjectChange = (subjectId) => {
    setSettingsSubject(subjectId);
    loadSessionSettings(subjectId);
  };

  // Persist the current sessionConfig to the per-teacher / per-subject template.
  // Reused as the canonical SidebarSettingsDialog Save handler — the legacy
  // "add more elements?" confirm step was removed to match the Interactive
  // Class UX, which saves directly with no intermediate prompt.
  const doSaveSettings = async () => {
    if (!settingsSubject) {
      nassaqError(t('noSubjectSelected') || t('selectSubjectFirst'));
      return;
    }
    setSettingsSaving(true);
    try {
      await api.put(`/teacher/${teacherId}/session-settings`, {
        subject_id: settingsSubject,
        ...sessionConfig,
      });
      toast.success(t('patternSaved'));
      setShowSettingsModal(false);
      setSettingsSubject('');
    } catch (err) {
      console.error('Error saving session settings:', err);
      if (isPermissionError(err)) {
        nassaqError(friendlyTeacherWriteMessage('teacherActionNotAllowed'));
      } else {
        nassaqError(t('errorSavingSessionSettings'));
      }
    } finally {
      setSettingsSaving(false);
    }
  };

  const fetchGradeOptions = useCallback(async () => {
    try {
      const res = await api.get('/classes/options/grades').catch(() => ({ data: { grades: [] } }));
      const grades = res.data?.grades || [];
      setGradeOptions(grades);
    } catch (err) {
      console.error('Error fetching grades:', err);
    }
  }, [api]);

  // Workspace-mode subject loader. Independent-Teacher accounts have no
  // school directory to pick from, so we list the subjects already
  // provisioned in their workspace (typically the optional first-class
  // subject seeded at bootstrap, plus anything added later).
  const fetchWorkspaceSubjects = useCallback(async () => {
    if (!isIndependentTeacher) return;
    try {
      const res = await api.get('/subjects');
      const subjects = Array.isArray(res.data) ? res.data : (res.data?.subjects || []);
      // Defensive filter: backend already excludes soft-deleted rows, but
      // belt-and-suspenders so a stale cache never surfaces a tombstoned
      // subject in the create-class dropdown (Task #190).
      setWorkspaceSubjects(subjects.filter(s => s?.is_active !== false));
      setWorkspaceSubjectsError(false);
    } catch (err) {
      console.error('Error fetching subjects:', err);
      setWorkspaceSubjectsError(true);
    }
  }, [api, isIndependentTeacher]);

  // Subject loader for the Lesson Settings modal. Runs for all teacher
  // roles — the /subjects endpoint is already tenant-scoped server-side,
  // so regular school teachers get their school's subjects and IT accounts
  // get their workspace subjects. The IT guard on fetchWorkspaceSubjects
  // is intentionally kept separate so the add-class dialog keeps its own
  // independent subject state.
  const fetchSubjectsForSettings = useCallback(async () => {
    setSubjectsLoading(true);
    try {
      const res = await api.get('/subjects');
      const subjects = Array.isArray(res.data) ? res.data : (res.data?.subjects || []);
      setSubjectsForSettings(subjects.filter(s => s?.is_active !== false));
    } catch (err) {
      console.error('Error fetching subjects for settings:', err);
      setSubjectsForSettings([]);
    } finally {
      setSubjectsLoading(false);
    }
  }, [api]);

  // Authoritative tenant-scoped class count from /classes for the IT
  // usage chip. Independent of the per-teacher assignment listing.
  const fetchWorkspaceClassCount = useCallback(async () => {
    if (!isIndependentTeacher) return;
    try {
      const res = await api.get('/classes').catch(() => ({ data: [] }));
      const list = Array.isArray(res.data) ? res.data : (res.data?.classes || []);
      setWorkspaceClassCount(list.length);
    } catch (err) {
      console.error('Error fetching workspace class count:', err);
    }
  }, [api, isIndependentTeacher]);

  useEffect(() => {
    if (isIndependentTeacher) {
      fetchWorkspaceSubjects();
      fetchGradeOptions();
      fetchWorkspaceClassCount();
    }
  }, [isIndependentTeacher, fetchWorkspaceSubjects, fetchGradeOptions, fetchWorkspaceClassCount]);

  // Fetch subjects for the Lesson Settings modal on page load so the
  // dropdown is ready immediately when the modal opens, then re-fetch
  // whenever the modal opens to pick up any server-side changes.
  useEffect(() => {
    fetchSubjectsForSettings();
  }, [fetchSubjectsForSettings]);

  useEffect(() => {
    if (showSettingsModal) {
      fetchSubjectsForSettings();
    }
  }, [showSettingsModal, fetchSubjectsForSettings]);

  // 2026-05-19 — The IT schedule-settings GET/PUT handlers and the
  // toggleItWorkingDay helper moved with the tab into the
  // `/teacher/planning` hub (TimeManagementHubPage).

  const handleOpenAddClassDialog = () => {
    // Independent-Teacher (workspace mode): open the simplified create-class
    // dialog wired to /classes/create with server-side tenant pinning. For
    // non-IT teachers, classes are still provisioned by the school admin so
    // we keep the friendly toast explanation.
    if (isIndependentTeacher) {
      setWorkspaceClassForm({ name_ar: '', grade_label: '', subject_id: '', capacity: 30 });
      fetchWorkspaceSubjects();
      fetchGradeOptions();
      setShowAddClassDialog(true);
      return;
    }
    toast.info(friendlyTeacherWriteMessage('teacherCreateClassNotAvailable'), { duration: 6000 });
  };

  const handleAddClass = async () => {
    // ---- Workspace-mode (Independent-Teacher) submit ----
    if (isIndependentTeacher) {
      const f = workspaceClassForm;
      if (!f.name_ar?.trim() || !f.grade_label?.trim() || !f.subject_id) {
        nassaqError(t('pleaseFillAllFields'));
        return;
      }
      const cap = parseInt(f.capacity, 10);
      if (!Number.isFinite(cap) || cap < 1 || cap > 50) {
        nassaqError(t('pleaseFillAllFields'));
        return;
      }
      setAddingClass(true);
      try {
        // Free-text grade label handling (spec §5.3 step 3): try to reuse
        // an existing grade row in this workspace whose label matches the
        // user's input; if none exists, auto-create one via the existing
        // grade-create surface (`POST /grade-levels`, now permitted for
        // IT and tenant-pinned server-side) and use the returned id.
        const label = f.grade_label.trim();
        const labelLc = label.toLowerCase();
        const matched = gradeOptions.find(g =>
          (g.name_ar || '').trim().toLowerCase() === labelLc
          || (g.name_en || '').trim().toLowerCase() === labelLc
          || (g.name || '').trim().toLowerCase() === labelLc
        );
        let gradeId;
        if (matched) {
          gradeId = matched.id;
        } else {
          // Auto-create. school_id is required by the schema but the
          // server overrides it with the IT workspace id, so any
          // placeholder is fine — we send the label as a sentinel.
          const createGradeRes = await api.post('/grade-levels', {
            name: label,
            name_en: label,
            order: (gradeOptions?.length || 0) + 1,
            is_active: true,
            school_id: 'workspace',
          });
          gradeId = createGradeRes.data?.id;
          // Refresh local cache so the next submit reuses this row.
          fetchGradeOptions();
        }

        // NOTE: school_id / tenant_id are intentionally never sent —
        // server resolves them from the JWT via require_request_school_id
        // (spec §5.3 architectural invariant).
        await api.post('/classes/create', {
          name_ar: f.name_ar.trim(),
          grade_id: gradeId,
          subject_id: f.subject_id,
          capacity: cap,
        });
        toast.success(t('classAddedSuccessfully'));
        setShowAddClassDialog(false);
        setWorkspaceClassForm({ name_ar: '', grade_label: '', subject_id: '', capacity: 30 });
        // Fetch workspace classes directly — more reliable than the
        // assignment-scoped /teacher/classes endpoint which may lag behind
        // newly created workspace classes (IT §5.3 stale-list fix).
        try {
          const wsRes = await api.get('/classes').catch(() => ({ data: [] }));
          const wsList = Array.isArray(wsRes.data) ? wsRes.data : (wsRes.data?.classes || []);
          setClasses(prev => {
            const collabOnly = prev.filter(c => c._collab);
            const wsEnriched = wsList.map(cls => {
              const existing = prev.find(c => c.id === cls.id);
              return {
                ...cls,
                attendance_rate: existing?.attendance_rate ?? 0,
                participation_rate: existing?.participation_rate ?? 0,
                avg_performance: existing?.avg_performance ?? 0,
                total_sessions: existing?.total_sessions ?? 0,
              };
            });
            const wsIds = new Set(wsList.map(c => c.id));
            return [...wsEnriched, ...collabOnly.filter(c => !wsIds.has(c.id))];
          });
        } catch (_) {
          fetchClasses();
        }
        fetchWorkspaceClassCount();
      } catch (err) {
        const status = err?.response?.status;
        const rawDetail = err?.response?.data;
        const msg = extractFastApiDetailFromResponseData(rawDetail) || t('errorAddingClass');
        if (status === 409) {
          nassaqWarning(msg, { title: t('error') });
        } else {
          nassaqError(msg, { title: t('error') });
        }
      } finally {
        setAddingClass(false);
      }
      return;
    }

    // ---- Legacy (school-affiliated teacher) submit — unchanged ----
    if (!addClassForm.name || !addClassForm.grade || !addClassForm.section) {
      nassaqError(t('pleaseFillAllFields'));
      return;
    }
    setAddingClass(true);
    try {
      await api.post('/classes/create', {
        name_ar: addClassForm.name,
        grade_id: addClassForm.grade,
        section: addClassForm.section,
        capacity: 30,
      });
      toast.success(t('classAddedSuccessfully'));
      setShowAddClassDialog(false);
      setAddClassForm({ name: '', grade: '', section: '', weekly_count: 5 });
      fetchClasses();
    } catch (err) {
      console.error('Error adding class:', err);
      if (isPermissionError(err)) {
        setShowAddClassDialog(false);
        nassaqError(friendlyTeacherWriteMessage('teacherCreateClassNotAvailable'));
      } else {
        const rawDetail = err.response?.data;
        const msg = extractFastApiDetailFromResponseData(rawDetail) || t('errorAddingClass');
        nassaqError(msg, { title: t('error') });
      }
    } finally {
      setAddingClass(false);
    }
  };

  const handleOpenImportDialog = () => {
    // Import is also a school-admin / future independent-teacher capability.
    toast.info(friendlyTeacherWriteMessage('teacherImportNotAvailable'), { duration: 6000 });
  };

  const handleImportSelect = (type) => {
    setImportType(type);
    setShowImportDialog(false);
    toast.info(friendlyTeacherWriteMessage('teacherImportNotAvailable'), { duration: 6000 });
  };

  const handleFileSelected = (e) => {
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const resolveGradeName = useCallback((cls) => {
    if (cls.grade_id && gradeOptions.length > 0) {
      const opt = gradeOptions.find(g => g.id === cls.grade_id);
      if (opt) {
        return isRTL
          ? (opt.name_ar || opt.name_en || opt.name || '')
          : (opt.name_en || opt.name_ar || opt.name || '');
      }
    }
    return cls.grade_name || '';
  }, [gradeOptions, isRTL]);

  const grades = useMemo(() => {
    const seen = new Map();
    for (const c of classes) {
      const rawId = c.grade_level || c.grade_id || '';
      if (!rawId || seen.has(rawId)) continue;
      let label = '';
      if (c.grade_id && gradeOptions.length > 0) {
        const opt = gradeOptions.find(g => g.id === c.grade_id);
        if (opt) {
          label = isRTL
            ? (opt.name_ar || opt.name_en || opt.name || '')
            : (opt.name_en || opt.name_ar || opt.name || '');
        }
      }
      if (!label) label = c.grade_name || rawId;
      seen.set(rawId, label);
    }
    return [...seen.entries()].map(([id, label]) => ({ id, label })).sort((a, b) => a.id.localeCompare(b.id));
  }, [classes, gradeOptions, isRTL]);

  const filteredClasses = useMemo(() => {
    let result = classes.filter(cls => {
      const matchSearch = !searchQuery ||
        cls.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        cls.grade_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (cls.subjects || []).some(s => s.toLowerCase().includes(searchQuery.toLowerCase()));
      const matchGrade = gradeFilter === 'all' || String(cls.grade_level || cls.grade_id) === gradeFilter;
      return matchSearch && matchGrade;
    });

    if (sortBy === 'grade') {
      result.sort((a, b) => (a.grade_level || '0').localeCompare(b.grade_level || '0') || a.name?.localeCompare(b.name));
    } else if (sortBy === 'students') {
      result.sort((a, b) => (b.student_count || 0) - (a.student_count || 0));
    } else if (sortBy === 'attendance') {
      result.sort((a, b) => (b.attendance_rate || 0) - (a.attendance_rate || 0));
    } else if (sortBy === 'name') {
      result.sort((a, b) => (a.name || '').localeCompare(b.name || ''));
    }
    return result;
  }, [classes, searchQuery, gradeFilter, sortBy]);

  const stats = useMemo(() => {
    if (!classes.length) return null;
    return {
      totalClasses: classes.length,
      totalStudents: classes.reduce((s, c) => s + (c.student_count || 0), 0),
      totalSubjects: [...new Set(classes.flatMap(c => c.subjects || []))].length,
      avgAttendance: Math.round(classes.reduce((s, c) => s + (c.attendance_rate || 0), 0) / classes.length),
      totalSessions: classes.reduce((s, c) => s + (c.weekly_periods || 0), 0),
    };
  }, [classes]);

  const getStatusBadge = (cls) => {
    if (cls.next_session) {
      return (
        <Badge className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300 border-0 text-[10px]">
          <CheckCircle2 className="h-3 w-3 me-1" />
          {t('active')}
        </Badge>
      );
    }
    if (cls.status === 'no_upcoming') {
      return (
        <Badge className="bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300 border-0 text-[10px]">
          <AlertTriangle className="h-3 w-3 me-1" />
          {t('noSession')}
        </Badge>
      );
    }
    return (
      <Badge variant="secondary" className="text-[10px]">
        {t('enrolled2')}
      </Badge>
    );
  };

  const renderNextSession = (cls) => {
    if (!cls.next_session) return null;
    const ns = cls.next_session;
    const dayLabel = t(ns.day) || ns.day;
    return (
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground mt-1">
        <Clock className="h-3 w-3 text-brand-turquoise flex-shrink-0" />
        <span className="truncate">
          {dayLabel} • {ns.start_time} {ns.subject_name ? `• ${ns.subject_name}` : ''}
        </span>
      </div>
    );
  };

  const handleEditClass = (e, cls) => {
    e.stopPropagation();
    setEditClassDialog({
      id: cls.id,
      name: cls.name || '',
      capacity: cls.capacity || 30,
    });
  };

  const handleDeleteClass = (e, cls) => {
    e.stopPropagation();
    nassaqConfirm(
      isRTL
        ? `هل تريد حذف الفصل "${cls.name}"؟ لا يمكن حذفه إذا كان به طلاب.`
        : `Delete class "${cls.name}"? It can't be deleted while it has students.`,
      async () => {
        try {
          await api.delete(`/classes/${cls.id}`);
          setClasses((prev) => prev.filter((c) => c.id !== cls.id));
          toast.success(isRTL ? `تم حذف الفصل "${cls.name}"` : `Class "${cls.name}" deleted`);
          fetchWorkspaceClassCount();
        } catch (err) {
          const detail = err?.response?.data?.detail;
          nassaqError(typeof detail === 'string' ? detail : (isRTL ? 'تعذّر حذف الفصل' : 'Could not delete class'));
        }
      }
    );
  };

  const saveEditClass = async () => {
    if (!editClassDialog) return;
    const name = (editClassDialog.name || '').trim();
    if (!name) {
      nassaqError(isRTL ? 'الاسم مطلوب' : 'Name is required');
      return;
    }
    setEditClassSaving(true);
    try {
      await api.put(`/classes/${editClassDialog.id}`, {
        name,
        capacity: Number(editClassDialog.capacity) || 30,
      });
      setEditClassDialog(null);
      await fetchClasses();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      nassaqError(typeof detail === 'string' ? detail : (isRTL ? 'تعذّر التحديث' : 'Could not update'));
    } finally {
      setEditClassSaving(false);
    }
  };

  const ClassCard = ({ cls }) => {
    const gc = getGradeColor(cls.grade_level || cls.grade_id);
    const curriculumPct = cls.curriculum_completion ?? cls.progress ?? Math.min(100, Math.round((cls.total_sessions || 0) * 2.5));
    return (
      <Card
        className={`group hover:shadow-xl transition-shadow duration-300 cursor-pointer border-2 hover:border-brand-turquoise/50 overflow-hidden ${gc.border}`}
        onClick={() => navigate(`/teacher/class/${cls.id}`)}
      >
        <div className={`h-1.5 bg-gradient-to-r ${gc.bg}`} />
        <CardHeader className="pb-2 pt-4">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3 min-w-0">
              <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${gc.bg} flex items-center justify-center shadow-md flex-shrink-0`}>
                <GraduationCap className="h-5 w-5 text-white" />
              </div>
              <div className="min-w-0">
                <CardTitle className="text-base font-cairo truncate">{cls.name}</CardTitle>
                <p className={`text-xs ${gc.text} font-medium`}>{resolveGradeName(cls)}</p>
                {renderNextSession(cls)}
              </div>
            </div>
            <div className="flex flex-col items-end gap-1">
              {getStatusBadge(cls)}
              <ChevronLeft className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3 pt-0">
          <div className="grid grid-cols-3 gap-1.5 text-center">
            <div className={`p-2 rounded-lg ${gc.light}`}>
              <Users className={`h-3.5 w-3.5 mx-auto mb-0.5 ${gc.text}`} />
              <div className={`text-lg font-bold ${gc.text}`}>{cls.student_count || 0}</div>
              <div className="text-[10px] text-muted-foreground">{t('students')}</div>
            </div>
            <div className="p-2 rounded-lg bg-muted/40">
              <BookOpen className="h-3.5 w-3.5 mx-auto mb-0.5 text-blue-500" />
              <div className="text-lg font-bold text-foreground">{cls.subjects?.length || 0}</div>
              <div className="text-[10px] text-muted-foreground">{t('subjects')}</div>
            </div>
            <div className="p-2 rounded-lg bg-muted/40">
              <Calendar className="h-3.5 w-3.5 mx-auto mb-0.5 text-purple-500" />
              <div className="text-lg font-bold text-foreground">{cls.weekly_periods || 0}</div>
              <div className="text-[10px] text-muted-foreground">{t('perWeek')}</div>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-muted-foreground">{t('attendance2')}</span>
              <span className={`font-bold ${
                cls.attendance_rate >= 90 ? 'text-emerald-600' :
                cls.attendance_rate >= 80 ? 'text-amber-600' : 'text-red-500'
              }`}>{cls.attendance_rate}%</span>
            </div>
            <Progress
              value={cls.attendance_rate || 0}
              className="h-1.5"
            />
          </div>

          <div>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="text-muted-foreground">{t('curriculumProgress')}</span>
              <span className="font-bold text-brand-turquoise">{curriculumPct}%</span>
            </div>
            <Progress
              value={curriculumPct}
              className="h-1.5"
            />
          </div>

          {cls.subjects && cls.subjects.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {cls.subjects.slice(0, 3).map((subject, idx) => (
                <Badge key={idx} variant="outline" className="text-[10px] py-0.5 font-tajawal">
                  {subject}
                </Badge>
              ))}
              {cls.subjects.length > 3 && (
                <Badge variant="outline" className="text-[10px] py-0.5">
                  +{cls.subjects.length - 3}
                </Badge>
              )}
            </div>
          )}

          <div className="flex gap-1.5 pt-2 border-t border-border/50">
            <Button
              variant="outline"
              size="sm"
              className="flex-1 h-8 text-xs"
              onClick={(e) => { e.stopPropagation(); navigate(`/teacher/class/${cls.id}`); }}
            >
              <Users className="h-3 w-3 me-1" />
              {t('students')}
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="flex-1 h-8 text-xs"
              onClick={(e) => { e.stopPropagation(); navigate(`/teacher/attendance?class=${cls.id}`); }}
            >
              <ClipboardCheck className="h-3 w-3 me-1" />
              {t('attendance2')}
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="flex-1 h-8 text-xs"
              onClick={(e) => { e.stopPropagation(); navigate(`/ai-insights`); }}
            >
              <BarChart3 className="h-3 w-3 me-1" />
              {t('reports2')}
            </Button>
          </div>
          {isIndependentTeacher && !cls._collab && (
            <div className="flex gap-1.5 pt-1.5">
              <Button
                variant="ghost"
                size="sm"
                className="flex-1 h-7 text-xs"
                onClick={(e) => handleEditClass(e, cls)}
                data-testid={`class-edit-${cls.id}`}
              >
                <Pencil className="h-3 w-3 me-1" />
                {isRTL ? 'تعديل' : 'Edit'}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="flex-1 h-7 text-xs text-red-600 hover:bg-red-50 hover:text-red-700"
                onClick={(e) => handleDeleteClass(e, cls)}
                data-testid={`class-delete-${cls.id}`}
              >
                <Trash2 className="h-3 w-3 me-1" />
                {isRTL ? 'حذف' : 'Delete'}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    );
  };

  const classListColumns = [
    {
      key: 'class',
      header: t('class'),
      primary: true,
      render: (cls) => {
        const gc = getGradeColor(cls.grade_level || cls.grade_id);
        return (
          <div className="flex items-center gap-3">
            <div className={`w-9 h-9 rounded-lg bg-gradient-to-br ${gc.bg} flex items-center justify-center shadow-sm flex-shrink-0`}>
              <GraduationCap className="h-4 w-4 text-white" />
            </div>
            <div className="min-w-0">
              <p className="font-medium font-cairo text-sm truncate">{cls.name}</p>
              <p className={`text-xs ${gc.text}`}>{resolveGradeName(cls)}</p>
            </div>
          </div>
        );
      },
    },
    {
      key: 'subjects',
      header: t('subjects'),
      render: (cls) => (
        <div className="flex flex-wrap gap-1">
          {(cls.subjects || []).slice(0, 2).map((s, i) => (
            <Badge key={i} variant="outline" className="text-[10px] py-0">{s}</Badge>
          ))}
          {(cls.subjects || []).length > 2 && (
            <Badge variant="outline" className="text-[10px] py-0">+{cls.subjects.length - 2}</Badge>
          )}
        </div>
      ),
    },
    {
      key: 'students',
      header: t('students'),
      cellClassName: 'text-center',
      headerClassName: 'text-center',
      render: (cls) => (
        <div className="flex items-center justify-center gap-1">
          <Users className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="font-bold">{cls.student_count || 0}</span>
        </div>
      ),
    },
    {
      key: 'attendance',
      header: t('attendance2'),
      cellClassName: 'text-center',
      headerClassName: 'text-center',
      render: (cls) => (
        <span className={`font-bold text-sm ${
          cls.attendance_rate >= 90 ? 'text-emerald-600' :
          cls.attendance_rate >= 80 ? 'text-amber-600' : 'text-red-500'
        }`}>{cls.attendance_rate}%</span>
      ),
    },
    {
      key: 'nextSession',
      header: t('nextSession'),
      render: (cls) => (
        cls.next_session ? (
          <div className="flex items-center gap-1.5 text-xs">
            <Clock className="h-3 w-3 text-brand-turquoise" />
            <span>{t(cls.next_session.day) || cls.next_session.day} {cls.next_session.start_time}</span>
          </div>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )
      ),
    },
    {
      key: 'status',
      header: t('status2'),
      render: (cls) => getStatusBadge(cls),
    },
    {
      key: 'actions',
      header: t('actions'),
      mobileFullWidth: true,
      render: (cls) => (
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={(e) => { e.stopPropagation(); navigate(`/teacher/class/${cls.id}`); }}>
            <Users className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={(e) => { e.stopPropagation(); navigate(`/teacher/attendance?class=${cls.id}`); }}>
            <ClipboardCheck className="h-3.5 w-3.5" />
          </Button>
        </div>
      ),
    },
  ];

  // The "Class Settings" entry from "My Classes" now opens the same canonical
  // SidebarSettingsDialog used by the Interactive Class flow (SessionTeachPage).
  // We provide a `sessionConfig` payload here so the dialog renders the full
  // tab set (تعريفات العناصر + تكوين الحصة) and we opt-in to the embedded
  // subject picker via `showSubjectPicker`, since "My Classes" persists a
  // per-(teacher, subject) template instead of a per-session record.
  //
  // Field translation between the dialog's camelCase props and the
  // `/teacher/{id}/session-settings` snake_case payload happens here so the
  // backend contract is unchanged.
  const renderSettingsModal = () => {
    const customSkillNames = (sessionConfig.custom_skills || []).map((s) =>
      typeof s === 'string' ? s : (s?.name || '')
    );
    return (
      <SidebarSettingsDialog
        open={showSettingsModal}
        onOpenChange={(open) => {
          setShowSettingsModal(open);
          if (!open) setSettingsSubject('');
        }}
        isRTL={isRTL}
        t={t}
        // Group A — element definitions. "My Classes" only persists custom
        // skill names through the existing PUT contract; evaluation items and
        // behaviours are kept in transient local state so add/remove behaves
        // identically to the Interactive Class flow without forking the
        // backend payload.
        evaluationItems={classEvaluationItems}
        onAddEvaluationItem={(item) => setClassEvaluationItems((prev) => [...prev, item])}
        onRemoveEvaluationItem={(id) =>
          setClassEvaluationItems((prev) => prev.filter((x) => x.id !== id))
        }
        positiveBehaviours={classPositiveBehaviours}
        negativeBehaviours={classNegativeBehaviours}
        onAddPositiveBehaviour={(item) => setClassPositiveBehaviours((prev) => [...prev, item])}
        onAddNegativeBehaviour={(item) => setClassNegativeBehaviours((prev) => [...prev, item])}
        onRemovePositiveBehaviour={(id) =>
          setClassPositiveBehaviours((prev) =>
            prev.filter((x) => (typeof x === 'string' ? `custom_${x}` !== id : x.id !== id))
          )
        }
        onRemoveNegativeBehaviour={(id) =>
          setClassNegativeBehaviours((prev) =>
            prev.filter((x) => (typeof x === 'string' ? `custom_${x}` !== id : x.id !== id))
          )
        }
        skillEnabled={!!sessionConfig.skills_enabled}
        onToggleSkillEnabled={(v) => setSessionConfig((p) => ({ ...p, skills_enabled: v }))}
        skillTypes={[]}
        customSkills={customSkillNames}
        onAddCustomSkill={(item) => {
          const name = typeof item === 'string' ? item : (item?.name || '');
          if (!name.trim()) return;
          setSessionConfig((p) => ({ ...p, custom_skills: [...(p.custom_skills || []), name.trim()] }));
        }}
        onRemoveCustomSkill={(idx) =>
          setSessionConfig((p) => ({
            ...p,
            custom_skills: (p.custom_skills || []).filter((_, i) => i !== idx),
          }))
        }
        // Group B — session configuration (camelCase props mirror the
        // canonical Interactive Class wiring).
        sessionConfig={{
          showSubjectPicker: true,
          subjectsList: subjectsForSettings,
          subjectsLoading: subjectsLoading,
          subjectId: settingsSubject,
          onSubjectIdChange: handleSubjectChange,
          participationEnabled: sessionConfig.participation_enabled,
          onParticipationEnabledChange: (v) =>
            setSessionConfig((p) => ({ ...p, participation_enabled: v })),
          homeworkEnabled: sessionConfig.homework_enabled,
          onHomeworkEnabledChange: (v) =>
            setSessionConfig((p) => ({ ...p, homework_enabled: v })),
          // Backend stores 'didnt_submit' / 'submitted'; canonical UI uses
          // 'not_submitted' / 'submitted'. Translate at the boundary.
          homeworkViewMode:
            sessionConfig.homework_mode === 'didnt_submit'
              ? 'not_submitted'
              : sessionConfig.homework_mode || 'not_submitted',
          onHomeworkViewModeChange: (v) =>
            setSessionConfig((p) => ({
              ...p,
              homework_mode: v === 'not_submitted' ? 'didnt_submit' : v,
            })),
          recitationEnabled: sessionConfig.recitation_enabled,
          onRecitationEnabledChange: (v) =>
            setSessionConfig((p) => ({ ...p, recitation_enabled: v })),
          recitationMaxAttempts: sessionConfig.recitation_attempts,
          onRecitationMaxAttemptsChange: (v) =>
            setSessionConfig((p) => ({ ...p, recitation_attempts: v })),
          // The per-subject template doesn't carry follow-up columns —
          // those are session-bound. Provide a no-op so the canonical
          // patterns tab still renders consistently.
          followupColumns: [],
          onFollowupColumnsChange: () => {},
          showAddOtherItems: false,
          onShowAddOtherItemsChange: () => {},
          onSave: doSaveSettings,
          saving: settingsSaving || settingsLoading,
        }}
      />
    );
  };

  const renderAddClassDialog = () => (
    <Dialog open={showAddClassDialog} onOpenChange={setShowAddClassDialog}>
      <DialogContent className="max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
        <DialogHeader>
          <DialogTitle className="font-cairo flex items-center gap-2">
            <Plus className="h-5 w-5 text-brand-turquoise" />
            {t('addClassForm')}
          </DialogTitle>
        </DialogHeader>
        {isIndependentTeacher ? (
          // Workspace-mode dialog body (spec §5.3): minimal fields only —
          // Arabic name, free-text grade label, subject from workspace,
          // capacity. NO section / weekly_count — those are not part of
          // the IT v1 contract.
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="font-cairo text-sm">{t('courseName')}</Label>
              <Input
                value={workspaceClassForm.name_ar}
                onChange={(e) => setWorkspaceClassForm(p => ({ ...p, name_ar: e.target.value }))}
                placeholder={t('courseName')}
              />
            </div>
            <div className="space-y-2">
              <Label className="font-cairo text-sm">{t('workspaceClassGradeLabel')}</Label>
              <Input
                value={workspaceClassForm.grade_label}
                onChange={(e) => setWorkspaceClassForm(p => ({ ...p, grade_label: e.target.value }))}
                placeholder={t('workspaceClassGradeLabelPlaceholder')}
              />
            </div>
            <div className="space-y-2">
              <Label className="font-cairo text-sm">{t('workspaceClassSubject')}</Label>
              <Select
                value={workspaceClassForm.subject_id}
                onValueChange={(v) => setWorkspaceClassForm(p => ({ ...p, subject_id: v }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder={t('workspaceClassSubjectPlaceholder')} />
                </SelectTrigger>
                <SelectContent>
                  {workspaceSubjectsError ? (
                    <div className="px-3 py-2 space-y-2">
                      <div className="text-xs text-destructive font-tajawal">
                        {t('workspaceClassSubjectsLoadError')}
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        className="font-cairo gap-1 w-full"
                        onClick={() => fetchWorkspaceSubjects()}
                      >
                        <RefreshCw className="h-3.5 w-3.5" />
                        {t('retry')}
                      </Button>
                    </div>
                  ) : workspaceSubjects.length > 0 ? workspaceSubjects.map(s => (
                    <SelectItem key={s.id} value={s.id}>
                      {isRTL ? (s.name_ar || s.name) : (s.name_en || s.name || s.name_ar)}
                    </SelectItem>
                  )) : (
                    <div className="px-3 py-2 space-y-2">
                      <div className="text-xs text-muted-foreground font-tajawal">
                        {t('workspaceClassNoSubjects')}
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        className="font-cairo gap-1 w-full"
                        onClick={() => {
                          // 2026-05-18 — Was navigate('/teacher/subjects')
                          // which now redirects to ?tab=subjects on the
                          // same page; swap to an in-page tab switch so
                          // we avoid an extra route hop and keep all
                          // mounted state inside this shell.
                          setShowAddClassDialog(false);
                          handleTabChange('subjects');
                        }}
                      >
                        <Plus className="h-3.5 w-3.5" />
                        {t('addSubject') || 'إضافة مادة'}
                      </Button>
                    </div>
                  )}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label className="font-cairo text-sm">{t('capacity') || 'السعة'}</Label>
              <Input
                type="number"
                min={1}
                max={50}
                value={workspaceClassForm.capacity}
                onChange={(e) => setWorkspaceClassForm(p => ({ ...p, capacity: parseInt(e.target.value) || 30 }))}
              />
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="font-cairo text-sm">{t('courseName')}</Label>
              <Input
                value={addClassForm.name}
                onChange={(e) => setAddClassForm(p => ({ ...p, name: e.target.value }))}
                placeholder={t('courseName')}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label className="font-cairo text-sm">{t('gradeLevel')}</Label>
                <Select value={addClassForm.grade} onValueChange={(v) => setAddClassForm(p => ({ ...p, grade: v }))}>
                  <SelectTrigger>
                    <SelectValue placeholder={t('gradeLevel')} />
                  </SelectTrigger>
                  <SelectContent>
                    {gradeOptions.length > 0 ? gradeOptions.map(g => (
                      <SelectItem key={g.id} value={g.id}>
                        {isRTL ? (g.name_ar || g.name) : (g.name_en || g.name)}
                      </SelectItem>
                    )) : [1,2,3,4,5,6].map(g => (
                      <SelectItem key={g} value={String(g)}>
                        {t('gradeLevel')} {g}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="font-cairo text-sm">{t('sectionName')}</Label>
                <Input
                  value={addClassForm.section}
                  onChange={(e) => setAddClassForm(p => ({ ...p, section: e.target.value }))}
                  placeholder={t('sectionName')}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label className="font-cairo text-sm">{t('weeklyClassCount')}</Label>
              <Input
                type="number"
                min={1}
                max={20}
                value={addClassForm.weekly_count}
                onChange={(e) => setAddClassForm(p => ({ ...p, weekly_count: parseInt(e.target.value) || 5 }))}
              />
            </div>
            <div className="flex items-start gap-2 p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
              <Info className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
              <p className="text-xs text-blue-700 dark:text-blue-300 font-tajawal">{t('classDataLinkedToAdmin')}</p>
            </div>
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => setShowAddClassDialog(false)}>{t('cancel')}</Button>
          <Button
            className="bg-brand-navy hover:bg-brand-navy-dark text-white"
            onClick={handleAddClass}
            disabled={addingClass}
          >
            {addingClass ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Plus className="h-4 w-4 me-2" />}
            {t('addClass')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );

  const renderImportDialog = () => (
    <Dialog open={showImportDialog} onOpenChange={setShowImportDialog}>
      <DialogContent className="max-w-sm" dir={isRTL ? 'rtl' : 'ltr'}>
        <DialogHeader>
          <DialogTitle className="font-cairo flex items-center gap-2">
            <Upload className="h-5 w-5 text-brand-turquoise" />
            {t('importClassData')}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-2">
          {[
            { type: 'excel', icon: FileSpreadsheet, label: t('importFromExcel'), color: 'text-green-600', bg: 'bg-green-50 dark:bg-green-900/20 hover:bg-green-100 dark:hover:bg-green-900/30' },
            { type: 'pdf', icon: FileText, label: t('importFromPdf'), color: 'text-red-600', bg: 'bg-red-50 dark:bg-red-900/20 hover:bg-red-100 dark:hover:bg-red-900/30' },
            { type: 'image', icon: FileImage, label: t('importFromImage'), color: 'text-blue-600', bg: 'bg-blue-50 dark:bg-blue-900/20 hover:bg-blue-100 dark:hover:bg-blue-900/30' },
          ].map(item => (
            <button
              key={item.type}
              className={`w-full flex items-center gap-3 p-3.5 rounded-lg border transition-colors duration-150 text-start ${item.bg}`}
              onClick={() => handleImportSelect(item.type)}
            >
              <item.icon className={`h-5 w-5 ${item.color}`} />
              <span className="font-medium text-sm font-cairo">{item.label}</span>
            </button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );

  const acceptMap = { excel: '.xlsx,.xls,.csv', pdf: '.pdf', image: '.jpg,.jpeg,.png,.webp' };

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white dark:bg-gray-900" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="sticky top-0 z-20 bg-white/90 dark:bg-gray-900/90 backdrop-blur-xl border-b border-border/50 shadow-sm">
          <div className="px-4 sm:px-6 py-4">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div>
                <h1 className="text-2xl font-bold text-brand-navy dark:text-brand-turquoise font-cairo flex items-center gap-2">
                  <GraduationCap className="h-7 w-7" />
                  {t('myClasses')}
                </h1>
                <p className="text-sm text-muted-foreground mt-0.5 font-tajawal">
                  {t('manageAndTrackYourClassesAndSessions')}
                </p>
              </div>
              {activeTab === 'classes' && (
                <div className="flex items-center gap-2 flex-wrap">
                  {isIndependentTeacher && (
                    <>
                      {/* Quota usage chip — informational; the authoritative
                          limit is enforced server-side via the 409 returned by
                          enforce_class_quota. (Spec §5.3 step 4.) */}
                      <Badge
                        variant="outline"
                        className="h-9 px-3 font-cairo text-xs flex items-center"
                      >
                        {(t('workspaceClassesUsageChip') || '{0} / {1}')
                          .replace('{0}', classes.length)
                          .replace('{1}', 5)}
                      </Badge>
                      <Button
                        size="sm"
                        className="h-9 gap-1.5 bg-brand-navy hover:bg-brand-navy-dark text-white"
                        onClick={handleOpenAddClassDialog}
                      >
                        <Plus className="h-4 w-4" />
                        <span className="hidden sm:inline">{t('addClass')}</span>
                      </Button>
                      <div className="hidden sm:block h-6 w-px bg-border" />
                    </>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-9 gap-1.5"
                    onClick={() => setShowSettingsModal(true)}
                  >
                    <Settings className="h-4 w-4" />
                    <span className="hidden sm:inline">{t('sessionSettings')}</span>
                  </Button>
                  <div className="hidden sm:block h-6 w-px bg-border" />
                  <div className="relative">
                    <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder={t('searchClassesOrSubjects')}
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="ps-9 w-full sm:w-[220px] h-9"
                    />
                  </div>
                  <Select value={gradeFilter} onValueChange={setGradeFilter}>
                    <SelectTrigger className="w-[130px] h-9">
                      <SelectValue placeholder={t('allGrades')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">{t('allGrades')}</SelectItem>
                      {grades.map(g => (
                        <SelectItem key={g.id} value={String(g.id)}>
                          {g.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <div className="flex items-center border rounded-lg overflow-hidden h-9">
                    <Button
                      variant={viewMode === 'card' ? 'default' : 'ghost'}
                      size="sm"
                      className="h-full rounded-none px-2.5"
                      onClick={() => setViewMode('card')}
                    >
                      <LayoutGrid className="h-4 w-4" />
                    </Button>
                    <Button
                      variant={viewMode === 'table' ? 'default' : 'ghost'}
                      size="sm"
                      className="h-full rounded-none px-2.5"
                      onClick={() => setViewMode('table')}
                    >
                      <List className="h-4 w-4" />
                    </Button>
                  </div>
                  <Button variant="outline" size="sm" className="h-9" onClick={fetchClasses} disabled={loading}>
                    <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                  </Button>
                </div>
              )}
            </div>
          </div>
          {/* 2026-05-19 — IA refactor: the tab strip now hosts up to
              seven IT-only entries (classes / sessions / lesson-planner
              / schedule / subjects / settings / import / calendar) plus
              the role-gated "حصص الانتظار". `overflow-x-auto flex-nowrap`
              keeps the strip a single horizontal scroller in RTL on
              narrow viewports instead of wrapping into a second row
              that breaks the sticky-band layout. `scrollbar-thin`
              keeps the scrollbar unobtrusive when it does appear. */}
          <div className="px-4 sm:px-6 flex gap-0 border-t border-border/30 overflow-x-auto flex-nowrap scrollbar-thin">
            <button
              onClick={() => handleTabChange('classes')}
              className={`px-5 py-2.5 text-sm font-medium font-cairo transition-colors relative ${
                activeTab === 'classes'
                  ? 'text-brand-navy dark:text-brand-turquoise'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <span className="flex items-center gap-1.5">
                <GraduationCap className="h-4 w-4" />
                {t('myClasses')}
              </span>
              {activeTab === 'classes' && (
                <span className="absolute bottom-0 inset-x-0 h-0.5 bg-brand-turquoise rounded-full" />
              )}
            </button>
            <button
              onClick={() => handleTabChange('sessions')}
              className={`px-5 py-2.5 text-sm font-medium font-cairo transition-colors relative ${
                activeTab === 'sessions'
                  ? 'text-brand-navy dark:text-brand-turquoise'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <span className="flex items-center gap-1.5">
                <ClipboardCheck className="h-4 w-4" />
                {t('sessionManagement')}
              </span>
              {activeTab === 'sessions' && (
                <span className="absolute bottom-0 inset-x-0 h-0.5 bg-brand-turquoise rounded-full" />
              )}
            </button>
            {/* 2026-05-18: standby tab is hidden for Independent-Teacher
                accounts (feature kept in the codebase for future re-enable). */}
            {!_isITUser && (
              <button
                onClick={() => handleTabChange('standby')}
                className={`px-5 py-2.5 text-sm font-medium font-cairo transition-colors relative ${
                  activeTab === 'standby'
                    ? 'text-brand-navy dark:text-brand-turquoise'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
                data-testid="teacher-classes-standby-tab"
              >
                <span className="flex items-center gap-1.5">
                  <Hourglass className="h-4 w-4" />
                  حصص الانتظار
                </span>
                {activeTab === 'standby' && (
                  <span className="absolute bottom-0 inset-x-0 h-0.5 bg-brand-turquoise rounded-full" />
                )}
              </button>
            )}
            {/* 2026-05-18 — IT-only "مساعد خطط الدروس" tab. The
                old sidebar entry was removed; this tab is the
                primary entry point now. Sparkles icon mirrors the
                spec's "with a sparkle icon if possible" hint. */}
            {_isITUser && canUseLessonPlanner && (
              <button
                onClick={() => handleTabChange('lesson-planner')}
                className={`px-5 py-2.5 text-sm font-medium font-cairo transition-colors relative ${
                  activeTab === 'lesson-planner'
                    ? 'text-brand-navy dark:text-brand-turquoise'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
                data-testid="teacher-classes-lesson-planner-tab"
              >
                <span className="flex items-center gap-1.5">
                  <Sparkles className="h-4 w-4 text-amber-500" />
                  مساعد خطط الدروس
                </span>
                {activeTab === 'lesson-planner' && (
                  <span className="absolute bottom-0 inset-x-0 h-0.5 bg-brand-turquoise rounded-full" />
                )}
              </button>
            )}
            {/* 2026-05-19 — The "جدولي" (schedule) tab was extracted
                into the dedicated `/teacher/planning` hub
                (TimeManagementHubPage). The redirect effect above
                rewrites `?tab=schedule` deep links so bookmarks
                keep working. */}
            {/* 2026-05-18 — IT-only "المواد" tab. Mirrors the retired
                sidebar entry that pointed at /teacher/subjects. The
                BookOpen icon matches the old sidebar item so IT
                users recognize the same surface in its new location. */}
            {_isITUser && (
              <button
                onClick={() => handleTabChange('subjects')}
                className={`px-5 py-2.5 text-sm font-medium font-cairo transition-colors relative ${
                  activeTab === 'subjects'
                    ? 'text-brand-navy dark:text-brand-turquoise'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
                data-testid="teacher-classes-subjects-tab"
              >
                <span className="flex items-center gap-1.5">
                  <BookOpen className="h-4 w-4" />
                  {t('subjects') || 'المواد'}
                </span>
                {activeTab === 'subjects' && (
                  <span className="absolute bottom-0 inset-x-0 h-0.5 bg-brand-turquoise rounded-full" />
                )}
              </button>
            )}
            {/* 2026-05-19 — The "إعدادات الجدول" tab was extracted
                into the dedicated `/teacher/planning` hub
                (TimeManagementHubPage). The redirect effect above
                rewrites `?tab=settings` deep links. */}
            {/* 2026-05-19 — IT-only "استيراد البيانات" tab. Merges the
                two retired sidebar entries ("استيراد الطلاب" +
                "الاستيراد الجماعي") into one unified import surface
                rendered by BulkImportPanel (which itself hosts the
                four sub-tabs: students / classes / subjects /
                duplicate-week). The Upload icon matches the retired
                sidebar items so the visual grammar carries over.
                Permission-gated on EITHER bulk-import slice so a user
                with only one of the two retired sidebar entries still
                sees the merged tab (BulkImportPanel sub-tabs continue
                to be gated server-side per action). */}
            {/* 2026-05-19 — IT-only "الطلاب" tab. Lives next to فصولي
                so the imported student directory is one click away.
                Server-side scoping (school_id == itw_{user_id}) is
                unchanged; this tab is purely an IA addition. */}
            {_isITUser && (
              <button
                onClick={() => handleTabChange('students')}
                className={`px-5 py-2.5 text-sm font-medium font-cairo transition-colors relative ${
                  activeTab === 'students'
                    ? 'text-brand-navy dark:text-brand-turquoise'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
                data-testid="teacher-classes-students-tab"
              >
                <span className="flex items-center gap-1.5">
                  <Users className="h-4 w-4" />
                  {t('myStudents') || 'الطلاب'}
                </span>
                {activeTab === 'students' && (
                  <span className="absolute bottom-0 inset-x-0 h-0.5 bg-brand-turquoise rounded-full" />
                )}
              </button>
            )}
            {_isITUser && canBulkImport && (
              <button
                onClick={() => handleTabChange('import')}
                className={`px-5 py-2.5 text-sm font-medium font-cairo transition-colors relative whitespace-nowrap ${
                  activeTab === 'import'
                    ? 'text-brand-navy dark:text-brand-turquoise'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
                data-testid="teacher-classes-import-tab"
              >
                <span className="flex items-center gap-1.5">
                  <Upload className="h-4 w-4" />
                  {t('itImportDataTab')}
                </span>
                {activeTab === 'import' && (
                  <span className="absolute bottom-0 inset-x-0 h-0.5 bg-brand-turquoise rounded-full" />
                )}
              </button>
            )}
            {/* 2026-05-19 — The "تقويمي الشخصي" tab was extracted
                into the dedicated `/teacher/planning` hub
                (TimeManagementHubPage). The redirect effect above
                rewrites `?tab=calendar` deep links. */}
          </div>
        </div>

        <div className="px-4 sm:px-6 py-4 space-y-4">
        {activeTab === 'sessions' ? (
          <SessionsManageTab />
        ) : activeTab === 'standby' ? (
          <StandbyTab />
        ) : activeTab === 'lesson-planner' ? (
          <LessonPlannerPanel embedded />
        ) : activeTab === 'subjects' ? (
          // Embedded variant drops the Sidebar + main wrapper so the
          // panel inherits the host page's spacing and doesn't render
          // a duplicate page-level header. Dialog renders via Radix
          // portal so the tab's overflow doesn't clip the modal.
          <TeacherSubjectsPanel embedded />
        ) : activeTab === 'students' ? (
          // 2026-05-19 — Embedded student directory. Same CRUD, class
          // filter, search, AddStudentWizard, and per-row edit/delete
          // as the standalone /teacher/students route, minus the
          // nested Sidebar shell. Backend tenant scoping
          // (school_id == itw_{user_id}) is unchanged.
          <TeacherStudentsPanel />
        ) : activeTab === 'import' ? (
          // 2026-05-19 — Unified IT import surface. BulkImportPanel
          // already exposes its own sub-tabs (students / classes /
          // subjects / duplicate-week); the students sub-tab uses the
          // headless ImportStudentsPanel directly so no nested Sidebar
          // or page header is rendered. Backend RBAC + MFA step-up
          // are enforced server-side per sub-tab as before.
          <div className="max-w-5xl mx-auto" data-testid="it-import-data-tab">
            {/* Pass the full perms Set so sub-tab visibility matches
                the per-permission Sidebar gating the retired entries
                used to enforce: students sub-tab requires
                students.bulk_import_workspace; classes/subjects/
                duplicate-week sub-tabs require
                classes.bulk_import_workspace. */}
            <BulkImportPanel permissions={perms} />
          </div>
        ) : activeTab === '__deprecated_extracted_tabs__' ? (
          // 2026-05-19 — The schedule / calendar / settings tabs were
          // extracted into the `/teacher/planning` hub. This branch is
          // kept only as a defensive no-op for any in-flight render
          // between the URL rewrite and the next pass; the redirect
          // effect above ensures it is never actually selected.
          null
        ) : (
          <>
          {!loading && stats && (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              {[
                { label: t('classes4'), value: stats.totalClasses, icon: GraduationCap, gradient: 'from-blue-500 to-blue-600', light: 'bg-blue-50 dark:bg-blue-900/20' },
                { label: t('students'), value: stats.totalStudents, icon: Users, gradient: 'from-emerald-500 to-emerald-600', light: 'bg-emerald-50 dark:bg-emerald-900/20' },
                { label: t('subjects'), value: stats.totalSubjects, icon: BookOpen, gradient: 'from-purple-500 to-purple-600', light: 'bg-purple-50 dark:bg-purple-900/20' },
                { label: t('perWeek'), value: stats.totalSessions, icon: Calendar, gradient: 'from-amber-500 to-amber-600', light: 'bg-amber-50 dark:bg-amber-900/20' },
                { label: t('avgAttendance'), value: `${stats.avgAttendance}%`, icon: TrendingUp, gradient: 'from-cyan-500 to-cyan-600', light: 'bg-cyan-50 dark:bg-cyan-900/20' },
              ].map(({ label, value, icon: Icon, gradient, light }) => (
                <Card key={label} className={`${light} border-0 shadow-sm`}>
                  <CardContent className="p-3 flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${gradient} flex items-center justify-center shadow-md flex-shrink-0`}>
                      <Icon className="h-5 w-5 text-white" />
                    </div>
                    <div>
                      <div className="text-xl font-bold text-foreground">{value}</div>
                      <div className="text-[10px] text-muted-foreground">{label}</div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 gap-3">
              <Loader2 className="h-10 w-10 animate-spin text-brand-turquoise" />
              <p className="text-sm text-muted-foreground font-tajawal">{t('loadingClasses')}</p>
            </div>
          ) : filteredClasses.length === 0 ? (
            // Task #200 §5.8 — IT-focused empty state: sub-brand workspace
            // accent + IT-targeted Arabic copy + a primary CTA that opens
            // the create-class flow. Other roles keep the existing neutral
            // empty state untouched.
            user?.role === 'independent_teacher' && !(searchQuery || gradeFilter !== 'all') ? (
              <Card
                className="border-dashed border-workspace-accent-border bg-workspace-accent-light/30"
                data-testid="teacher-classes-empty-state-it"
              >
                <CardContent className="text-center py-16">
                  <GraduationCap className="h-16 w-16 mx-auto mb-4 text-workspace-accent" />
                  <h3 className="font-bold text-lg mb-2 font-cairo text-workspace-accent-fg">
                    {t('itEmptyClassesTitle')}
                  </h3>
                  <p className="text-muted-foreground text-sm font-tajawal mb-5 max-w-md mx-auto">
                    {t('itEmptyClassesDescription')}
                  </p>
                  <Button
                    onClick={handleOpenAddClassDialog}
                    className="bg-workspace-accent hover:bg-workspace-accent-fg text-white rounded-xl gap-2 px-5"
                    data-testid="teacher-classes-empty-state-cta"
                  >
                    <Plus className="h-4 w-4" />
                    {t('itEmptyClassesCta')}
                  </Button>
                </CardContent>
              </Card>
            ) : (
              <Card className="border-dashed" data-testid="teacher-classes-empty-state">
                <CardContent className="text-center py-16">
                  <GraduationCap className="h-16 w-16 mx-auto mb-4 text-muted-foreground/20" />
                  <h3 className="font-bold text-lg mb-2 font-cairo">
                    {searchQuery || gradeFilter !== 'all'
                      ? (t('noResults'))
                      : (t('noClassesFound2'))}
                  </h3>
                  <p className="text-muted-foreground text-sm font-tajawal">
                    {searchQuery || gradeFilter !== 'all'
                      ? (t('tryChangingSearchCriteria'))
                      : (t('noClassesAssignedToYouYet'))}
                  </p>
                </CardContent>
              </Card>
            )
          ) : (
            <>
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground font-tajawal">
                  {t('showingXOfYClasses').replace ? t('showingXOfYClasses').replace('{0}', filteredClasses.length).replace('{1}', classes.length) : `${filteredClasses.length} / ${classes.length}`}
                </p>
                <Select value={sortBy} onValueChange={setSortBy}>
                  <SelectTrigger className="w-[140px] h-8 text-xs">
                    <ArrowUpDown className="h-3 w-3 me-1" />
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="grade">{t('gradeLevel')}</SelectItem>
                    <SelectItem value="name">{t('name')}</SelectItem>
                    <SelectItem value="students">{t('byStudents')}</SelectItem>
                    <SelectItem value="attendance">{t('attendance2')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {viewMode === 'card' ? (
                <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  {filteredClasses.map(cls => (
                    <ClassCard key={cls.id} cls={cls} />
                  ))}
                </div>
              ) : (
                <Card className="overflow-hidden">
                  <ResponsiveTable
                    ariaLabel={t('myClasses')}
                    rows={filteredClasses}
                    getRowKey={(cls) => cls.id}
                    onRowClick={(cls) => navigate(`/teacher/class/${cls.id}`)}
                    columns={classListColumns}
                  />
                </Card>
              )}
            </>
          )}

          {/* 2026-05-19 — Hide the "data is linked to the school
             administration and updates automatically" banner for
             independent-teacher accounts. The statement is false for
             that role: ITs manage their own rosters via the import
             tools and have no school admin syncing data on their
             behalf. Regular school teachers still see it. */}
          {!loading && !isIndependentTeacher && (
            <div className="mt-6 flex items-start gap-3 p-4 rounded-xl bg-blue-50/70 dark:bg-blue-950/30 border border-blue-200/60 dark:border-blue-800/40">
              <div className="w-9 h-9 rounded-lg bg-blue-100 dark:bg-blue-900/40 flex items-center justify-center flex-shrink-0">
                <Info className="h-4.5 w-4.5 text-blue-600 dark:text-blue-300" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-semibold font-cairo text-blue-900 dark:text-blue-200 mb-0.5">
                  {t('classDataLinkedToAdmin')}
                </p>
                <p className="text-xs text-blue-700/90 dark:text-blue-300/90 font-tajawal leading-relaxed">
                  {t('classDataAutoSyncNotice')}
                </p>
              </div>
            </div>
          )}
          </>
        )}
        </div>
      </div>

      {renderSettingsModal()}
      {renderAddClassDialog()}
      {/* Edit class dialog (IT only) */}
      <Dialog open={!!editClassDialog} onOpenChange={(o) => !o && setEditClassDialog(null)}>
        <DialogContent className="max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader>
            <DialogTitle className="font-cairo flex items-center gap-2">
              <Pencil className="h-5 w-5 text-brand-turquoise" />
              {isRTL ? 'تعديل بيانات الفصل' : 'Edit class'}
            </DialogTitle>
          </DialogHeader>
          {editClassDialog && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label className="font-cairo text-sm">{t('courseName')}</Label>
                <Input
                  value={editClassDialog.name}
                  onChange={(e) => setEditClassDialog((p) => ({ ...p, name: e.target.value }))}
                />
              </div>
              <div className="space-y-2">
                <Label className="font-cairo text-sm">{isRTL ? 'السعة' : 'Capacity'}</Label>
                <Input
                  type="number"
                  min={1}
                  max={200}
                  value={editClassDialog.capacity}
                  onChange={(e) => setEditClassDialog((p) => ({ ...p, capacity: e.target.value }))}
                />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditClassDialog(null)}>{t('cancel')}</Button>
            <Button onClick={saveEditClass} disabled={editClassSaving}>
              {editClassSaving ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : null}
              {t('save') || (isRTL ? 'حفظ' : 'Save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {renderImportDialog()}

      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        accept={acceptMap[importType] || '*'}
        onChange={handleFileSelected}
      />
    </Sidebar>
  );
}
