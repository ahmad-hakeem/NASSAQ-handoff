import { useState, useEffect, useCallback, useRef, useLayoutEffect } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import SectionErrorBoundary from '../../components/SectionErrorBoundary';
import FollowupGradesTable from '../../components/teacher/FollowupGradesTable';
import SidebarSettingsDialog from '../../components/teacher/SidebarSettingsDialog';
import InlineAttendanceTable from '../../components/teacher/InlineAttendanceTable';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/avatar';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { Textarea } from '../../components/ui/textarea';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  Shuffle, CheckCircle2, XCircle, Loader2, Hand,
  Zap, AlertTriangle, Award, Star, Clock, Users,
  BookOpen, ClipboardCheck, FileQuestion, ThumbsUp,
  ThumbsDown, Minus, ChevronDown, BarChart2, MessageCircle,
  Smile, Frown, Activity, Heart, Send, Trophy, Sparkles,
  StickyNote, Plus, Trash2, PenLine, UserCheck,
  Download, History, FileSpreadsheet,
  Settings, UsersRound, User, Table2, GripVertical, Search, Mic,
  PanelRightClose, PanelRightOpen, ArrowRight, ArrowLeft, MoreHorizontal,
  Save, FileText, RotateCcw, Eye, ShieldAlert, X
} from 'lucide-react';
import confetti from 'canvas-confetti';

import { useTranslation } from '../../contexts/ThemeContext';
import { getApiErrorMessage } from '../../utils/apiError';
import {
  mergeFollowupData,
  mergeFollowupAbsences,
  isFollowupNoOpFlush,
  runFollowupClose,
  pickManualCells,
  computeManualKeys,
} from './followupPersistence';

// Health condition badges (mirrors SessionStartPage)
const HEALTH_BADGES = {
  diabetes: { icon: Heart, color: 'text-red-500', bg: 'bg-red-100 dark:bg-red-500/20', labelKey: 'healthBadgeDiabetes' },
  allergy: { icon: AlertTriangle, color: 'text-amber-500', bg: 'bg-amber-100 dark:bg-amber-500/20', labelKey: 'healthBadgeAllergy' },
  asthma: { icon: Heart, color: 'text-blue-500', bg: 'bg-blue-100 dark:bg-blue-500/20', labelKey: 'healthBadgeAsthma' },
  epilepsy: { icon: ShieldAlert, color: 'text-purple-500', bg: 'bg-purple-100 dark:bg-purple-500/20', labelKey: 'healthBadgeEpilepsy' },
  vision: { icon: Eye, color: 'text-cyan-500', bg: 'bg-cyan-100 dark:bg-cyan-500/20', labelKey: 'healthBadgeVision' },
  social_case: { icon: ShieldAlert, color: 'text-orange-500', bg: 'bg-orange-100 dark:bg-orange-500/20', labelKey: 'healthBadgeSocialCase' },
  special_needs: { icon: Heart, color: 'text-pink-500', bg: 'bg-pink-100 dark:bg-pink-500/20', labelKey: 'healthBadgeSpecialNeeds' },
};
const GENDER_COLORS = {
  male: { bg: 'bg-sky-600', ring: 'ring-sky-400', label: 'طلاب', labelKey: 'maleStudents', icon: 'M', light: 'bg-sky-500/10 dark:bg-sky-900/30' },
  female: { bg: 'bg-pink-600', ring: 'ring-pink-400', label: 'طالبات', labelKey: 'femaleStudents', icon: 'F', light: 'bg-pink-500/10 dark:bg-pink-900/30' },
};

const MODES = [
  { id: 'review', label: 'مراجعة', labelKey: 'modeReview', icon: BookOpen, color: 'bg-purple-600' },
  { id: 'homework', label: 'واجب', labelKey: 'modeHomework', icon: ClipboardCheck, color: 'bg-blue-600' },
  { id: 'quiz', label: 'اختبار', labelKey: 'modeQuiz', icon: FileQuestion, color: 'bg-amber-600' },
];

const PARTICIPATION = [
  { id: 'active', label: 'مشاركة', labelKey: 'participationActive', icon: Hand, color: 'bg-green-500', score: '+2' },
  { id: 'initiative', label: 'مبادرة', labelKey: 'participationInitiative', icon: Zap, color: 'bg-purple-500', score: '+3' },
  { id: 'inactive', label: 'لا يتفاعل', labelKey: 'participationInactive', icon: Minus, color: 'bg-amber-500', score: '0' },
  { id: 'refused', label: 'رفض', labelKey: 'participationRefused', icon: XCircle, color: 'bg-red-500', score: '-1' },
];

const BEHAVIOURS = {
  positive: [
    { id: 'respect', label: 'احترام', labelKey: 'behaviourRespect', points: '+2' },
    { id: 'commitment', label: 'التزام', labelKey: 'behaviourCommitment', points: '+2' },
    { id: 'helping_others', label: 'مساعدة الآخرين', labelKey: 'behaviourHelpingOthers', points: '+2' },
  ],
  negative: [
    { id: 'disruption', label: 'إزعاج', labelKey: 'behaviourDisruption', points: '-2' },
    { id: 'non_compliance', label: 'عدم التزام', labelKey: 'behaviourNonCompliance', points: '-2' },
    { id: 'interruption', label: 'مقاطعة', labelKey: 'behaviourInterruption', points: '-1' },
  ],
};

// Icon + color maps for evaluation items configured in the
// SidebarSettingsDialog. Mirrors the maps used inside that dialog so
// the sidebar buttons render with the same visual identity teachers
// pick when adding a new evaluation item.
const SIDEBAR_EVAL_ICONS = {
  CheckCircle2, XCircle, ClipboardCheck, Mic, Hand, Star, Sparkles,
};
const SIDEBAR_EVAL_COLORS = {
  emerald: 'bg-emerald-500/15 border-emerald-400/40 hover:bg-emerald-500/25',
  red:     'bg-rose-500/15 border-rose-400/40 hover:bg-rose-500/25',
  amber:   'bg-amber-500/15 border-amber-400/40 hover:bg-amber-500/25',
  sky:     'bg-sky-500/15 border-sky-400/40 hover:bg-sky-500/25',
  purple:  'bg-purple-500/15 border-purple-400/40 hover:bg-purple-500/25',
  gray:    'bg-foreground/5 border-border hover:bg-foreground/10',
};
// IDs of the four built-in evaluation items. The sidebar already
// renders dedicated, hard-wired buttons for these (they have bespoke
// confetti/scoring/recitation behavior), so we filter them out when
// rendering the *additional* user-added items below them.
const DEFAULT_EVAL_IDS = new Set([
  'eval_default_correct',
  'eval_default_wrong',
  'eval_default_homework',
  'eval_default_recite',
]);

const LOG_ICONS = {
  correct: CheckCircle2,
  wrong: XCircle,
  skip: Minus,
  note: StickyNote,
  behaviour: ThumbsUp,
  skill: Star,
  participation: Hand,
  action_reversed: RotateCcw,
};

/**
 * EvalPopover — context-aware floating popover anchored to a sidebar trigger button.
 * - Renders into a portal at <body> so it can't be clipped by overflow:auto ancestors.
 * - Auto-flips horizontally based on which half of the viewport the trigger is in
 *   (sidebar on the right edge in RTL → opens to the left of trigger; vice-versa for LTR).
 * - Clamps within viewport edges and recomputes on resize/scroll.
 * - Closes on outside click and Escape.
 */
function EvalPopover({ open, onClose, anchorRef, title, children, width = 320 }) {
  const popRef = useRef(null);
  const [pos, setPos] = useState({ left: 0, top: 0, ready: false });

  // Reset readiness on each open so a previously-cached position doesn't briefly flash
  // before we re-measure against the (possibly relocated) trigger.
  useLayoutEffect(() => {
    if (open) setPos(p => ({ ...p, ready: false }));
  }, [open]);

  useLayoutEffect(() => {
    if (!open || !anchorRef?.current) return;
    const recompute = () => {
      const a = anchorRef.current?.getBoundingClientRect();
      if (!a) return;
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      const margin = 8;
      const ph = popRef.current?.offsetHeight || 320;
      const pw = popRef.current?.offsetWidth || width;
      const triggerCenter = a.left + a.width / 2;
      const openLeft = triggerCenter > vw / 2;
      let left = openLeft ? a.left - pw - margin : a.right + margin;
      let top = a.top;
      if (left < margin) left = margin;
      if (left + pw > vw - margin) left = Math.max(margin, vw - pw - margin);
      if (top + ph > vh - margin) top = Math.max(margin, vh - ph - margin);
      if (top < margin) top = margin;
      setPos({ left, top, ready: true });
    };
    recompute();
    const r2 = () => recompute();
    window.addEventListener('resize', r2);
    window.addEventListener('scroll', r2, true);
    return () => {
      window.removeEventListener('resize', r2);
      window.removeEventListener('scroll', r2, true);
    };
  }, [open, anchorRef, width, children]);

  useEffect(() => {
    if (!open) return;
    const onMouseDown = (e) => {
      if (popRef.current?.contains(e.target)) return;
      if (anchorRef?.current?.contains(e.target)) return;
      onClose();
    };
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('mousedown', onMouseDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onMouseDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open, onClose, anchorRef]);

  if (!open) return null;
  return createPortal(
    <div
      ref={popRef}
      style={{
        position: 'fixed',
        left: pos.left,
        top: pos.top,
        width,
        zIndex: 9999,
        visibility: pos.ready ? 'visible' : 'hidden',
      }}
      className="max-w-[92vw] bg-background/95 backdrop-blur-xl border border-border rounded-xl shadow-[0_18px_50px_-12px_rgba(0,0,0,0.55)] ring-1 ring-amber-400/10 overflow-hidden animate-in fade-in zoom-in-95 duration-150"
      role="dialog"
      aria-modal="false"
      aria-label={typeof title === 'string' ? title : 'evaluation'}
    >
      {title && (
        <div className="px-3 py-2 border-b border-border bg-foreground/[0.04] flex items-center justify-between gap-2">
          <span className="text-xs font-bold text-foreground font-cairo truncate">{title}</span>
          <button
            type="button"
            onClick={onClose}
            className="p-1 hover:bg-foreground/10 rounded text-muted-foreground hover:text-foreground transition-colors"
            aria-label="close"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
      <div className="p-3 max-h-[60vh] overflow-y-auto scrollbar-thin">
        {children}
      </div>
    </div>,
    document.body
  );
}

function useSessionTimer(startTimeStr) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!startTimeStr) return;
    const start = new Date(startTimeStr).getTime();
    const tick = () => setElapsed(Math.floor((Date.now() - start) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startTimeStr]);
  const mins = Math.floor(elapsed / 60);
  const secs = elapsed % 60;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

export default function SessionTeachPage() {
  const { user, api, isRTL } = useAuth();
  const { t } = useTranslation();
  const { nassaqError, nassaqConfirm } = useNassaqAlert();
  const navigate = useNavigate();
  const location = useLocation();

  const [sessionId] = useState(location.state?.sessionId);
  const [sessionInfo, setSessionInfo] = useState(location.state?.sessionInfo || {});
  const [startTime, setStartTime] = useState(location.state?.startTime || null);
  const [students, setStudents] = useState([]);
  const [mode, setMode] = useState(null);
  const [loading, setLoading] = useState(false);
  const [flashId, setFlashId] = useState(null);
  const [showHakim, setShowHakim] = useState(false);
  const [showRandomPopup, setShowRandomPopup] = useState(false);
  const [showQuickNote, setShowQuickNote] = useState(false);
  const [showAttendanceModal, setShowAttendanceModal] = useState(false);
  // Tracks whether the live-session attendance register made a change so we
  // only re-finalize (approve + daily sync) when something actually changed.
  const attendanceDirtyRef = useRef(false);
  const [quickNoteText, setQuickNoteText] = useState('');
  const [quickNoteIds, setQuickNoteIds] = useState(() => new Set());
  const [quickNoteFilter, setQuickNoteFilter] = useState('');
  const [quickNoteSending, setQuickNoteSending] = useState(false);
  const [selectedStudent, setSelectedStudent] = useState(null);
  // ── Sidebar contextual popovers (replace the old central tabbed evaluation sheet).
  // Single open-at-a-time controller; null when nothing is open.
  // Values: 'positive' | 'negative' | 'recitation' | 'skill'
  const [openPopover, setOpenPopover] = useState(null);
  const positivePopRef = useRef(null);
  const negativePopRef = useRef(null);
  const recitationPopRef = useRef(null);
  const skillPopRef = useRef(null);
  // Auto-close the (now-deprecated) central action sheet AND any open popover whenever the
  // selected student changes/clears, so stale anchors and previous-student notes don't leak.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    setShowActionSheet(false);
    setOpenPopover(null);
  }, [selectedStudent?.id]);
  const [actionTab, setActionTab] = useState('question'); // question | participation | behaviour | skill | homework | recitation
  // If the underlying capability is toggled off while its popover is open, dismiss it
  // (otherwise we'd leave a stranded popover anchored to a button that no longer renders).
  const [behaviourCategory, setBehaviourCategory] = useState('positive');
  const [behaviourNote, setBehaviourNote] = useState('');
  const [recitationAttempts, setRecitationAttempts] = useState(1);
  const [recitationNote, setRecitationNote] = useState('');
  const [homeworkStatuses, setHomeworkStatuses] = useState({});
  const [skillTypes, setSkillTypes] = useState([]);
  const [skillNote, setSkillNote] = useState('');
  const [showEndDialog, setShowEndDialog] = useState(false);
  const [reviewData, setReviewData] = useState(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [closingNote, setClosingNote] = useState('');
  const [timeWarning, setTimeWarning] = useState(null);
  const [summary, setSummary] = useState(null);
  const [activityLog, setActivityLog] = useState([]);
  const [stats, setStats] = useState({ questions: 0, correct: 0, participation: 0 });
  const [rightPanel, setRightPanel] = useState(() => {
    if (typeof window === 'undefined') return 'log';
    try { return localStorage.getItem('sessionTeach.rightPanel') || 'log'; }
    catch { return 'log'; }
  });
  // Activity log panel always starts closed in the redesigned layout (mockup hides it).
  // Users can still open it from the overflow (⋯) menu during the session.
  const [panelOpen, setPanelOpen] = useState(false);
  const [notes, setNotes] = useState([]);
  const [newNote, setNewNote] = useState('');
  const [noteType, setNoteType] = useState('session');
  const [liveMetrics, setLiveMetrics] = useState(null);
  const [evalMode, setEvalMode] = useState(() => {
    if (typeof window === 'undefined') return 'individual';
    try { return localStorage.getItem('sessionTeach.evalMode') || 'individual'; }
    catch { return 'individual'; }
  });

  useEffect(() => { try { localStorage.setItem('sessionTeach.rightPanel', rightPanel); } catch {} }, [rightPanel]);
  useEffect(() => { try { localStorage.setItem('sessionTeach.panelOpen', panelOpen ? '1' : '0'); } catch {} }, [panelOpen]);
  useEffect(() => { try { localStorage.setItem('sessionTeach.evalMode', evalMode); } catch {} }, [evalMode]);
  const [groups, setGroups] = useState([]);
  // Backend is the source of truth for groups. This ref flips true only after
  // the initial backend load completes, so the debounced save effect never
  // clobbers the durable record with the empty/initial state on mount.
  const groupsLoadedRef = useRef(false);
  const groupsSaveRef = useRef(null);
  const [showGroupModal, setShowGroupModal] = useState(false);
  // Session settings (إعدادات الحصة) are now rendered as a tab group inside
  // SidebarSettingsDialog. The legacy `showSettingsModal` boolean is gone —
  // the gear button toggles `showSidebarSettings` for both groups.
  const [showSidebarSettings, setShowSidebarSettings] = useState(false);
  const [showFollowupRecord, setShowFollowupRecord] = useState(false);
  const [customPositiveBehaviours, setCustomPositiveBehaviours] = useState([]);
  const [customNegativeBehaviours, setCustomNegativeBehaviours] = useState([]);
  const [customSkills, setCustomSkills] = useState([]);
  const [customEvaluationItems, setCustomEvaluationItems] = useState([
    { id: 'eval_default_correct',  name: 'إجابة صحيحة',     color: 'emerald', icon: 'CheckCircle2',    points: 1  },
    { id: 'eval_default_wrong',    name: 'إجابة خاطئة',     color: 'red',     icon: 'XCircle',         points: 0  },
    { id: 'eval_default_homework', name: 'لم يسلّم الواجب',  color: 'amber',   icon: 'ClipboardCheck',  points: -1 },
    { id: 'eval_default_recite',   name: 'تسميع',           color: 'purple',  icon: 'Mic',             points: 2  },
  ]);
  const [followupData, setFollowupData] = useState({});
  const [followupColumns, setFollowupColumns] = useState([]);
  const [followupAbsences, setFollowupAbsences] = useState({});
  // Tracks "studentId:columnId" pairs the teacher has manually typed into,
  // so the live-refresh poll never overwrites an in-progress edit.
  const dirtyFollowupCells = useRef(new Set());
  // Persistent set of "studentId:columnId" cells the teacher has taken MANUAL
  // ownership of (typed a value into, or that came back as a stored override).
  // Unlike dirtyFollowupCells (cleared per-cell on every successful flush), this
  // survives flushes for the sheet's lifetime so each save sends the FULL manual
  // set — never a session-derived echo, which would freeze the cell against
  // later live scoring. Seeded from the GET `manual_keys` and restored from
  // sessionStorage so a reload can't wipe stored overrides.
  const manualFollowupCells = useRef(new Set());
  // Per-cell edit counter. A save snapshots each dirty cell's revision at send
  // time and, on success, clears ONLY the cells whose revision is unchanged —
  // so an edit made while a save is in flight keeps its dirty mark (and is not
  // clobbered by the 30 s merge poll) until its own later save persists it.
  const followupCellRev = useRef(new Map());
  // Same dirty/revision model for absence edits (keyed by student id), so an
  // absence add/remove is persisted and survives the merge poll / reopen the
  // same way a grade edit does.
  const dirtyFollowupAbsences = useRef(new Set());
  const followupAbsenceRev = useRef(new Map());
  const [followupTab, setFollowupTab] = useState('students');
  const [showAddColumnModal, setShowAddColumnModal] = useState(false);
  const [showColumnSettings, setShowColumnSettings] = useState(false);
  const [newColumnDraft, setNewColumnDraft] = useState({ name: '', group: 'coursework', maxGrade: 10 });
  const [absencePickerStudent, setAbsencePickerStudent] = useState(null);
  const [absencePickerDate, setAbsencePickerDate] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [showSearch, setShowSearch] = useState(false);
  // ===== Redesign state =====
  const [showActionSheet, setShowActionSheet] = useState(false); // opens existing action panel as modal
  const [savingSession, setSavingSession] = useState(false);
  // ===== Session settings (إعدادات الحصة) =====
  // (action-sheet auto-close on selected-student change is wired below, after selectedStudent is declared)
  const [subjectsList, setSubjectsList] = useState([]);
  const [settingsSubjectId, setSettingsSubjectId] = useState('');
  const [participationEnabled, setParticipationEnabled] = useState(true);
  const [homeworkEnabled, setHomeworkEnabled] = useState(true);
  const [homeworkViewMode, setHomeworkViewMode] = useState('not_submitted');
  const [recitationEnabled, setRecitationEnabled] = useState(false);
  const [recitationMaxAttempts, setRecitationMaxAttempts] = useState(1);
  const [skillEnabled, setSkillEnabled] = useState(false);
  const [showAddOtherItems, setShowAddOtherItems] = useState(false);
  const [participationScores, setParticipationScores] = useState({});
  const [correctAnswerWeight, setCorrectAnswerWeight] = useState(null);
  const [correctAnswerWeightDirty, setCorrectAnswerWeightDirty] = useState(false);
  const [effectiveCorrectAnswerWeight, setEffectiveCorrectAnswerWeight] = useState(5);
  const [savingSettings, setSavingSettings] = useState(false);
  // If the active action tab gets disabled by settings, switch to a safe default
  useEffect(() => {
    const disabled =
      (actionTab === 'participation' && !participationEnabled) ||
      (actionTab === 'homework' && !homeworkEnabled) ||
      (actionTab === 'recitation' && !recitationEnabled) ||
      (actionTab === 'skill' && !skillEnabled);
    if (disabled) setActionTab('question');
  }, [actionTab, participationEnabled, homeworkEnabled, recitationEnabled, skillEnabled]);
  // If the underlying capability is toggled OFF while its popover is open, dismiss it —
  // otherwise we'd leave a stranded popover anchored to a button that no longer renders.
  useEffect(() => {
    if (
      (openPopover === 'recitation' && !recitationEnabled) ||
      (openPopover === 'skill' && !skillEnabled)
    ) {
      setOpenPopover(null);
    }
  }, [openPopover, recitationEnabled, skillEnabled]);
  // Load homework statuses for the inline per-student toggle whenever the
  // homework feature is enabled and we have a roster. Defaults every present
  // student to "أنجز" (done) — see loadHomeworkStatuses.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (homeworkEnabled && sessionId && students.length > 0) {
      loadHomeworkStatuses(students);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [homeworkEnabled, sessionId, students.length]);
  const flashRef = useRef(null);
  useEffect(() => { return () => { if (flashRef.current) clearInterval(flashRef.current); }; }, []);
  const timer = useSessionTimer(startTime);

  const teacherId = user?.teacher_id || user?.id;

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!sessionId) {
      nassaqError(t('noActiveSessionFound'));
      navigate('/teacher');
      return;
    }
    let isMounted = true;
    loadStudents().then(studentList => {
      if (isMounted) loadSessionInfo(studentList);
    });
    loadSkillTypes();
    loadActivityLog();
    peekUndoState();
    loadSessionSettings();
    loadSubjectsList();
    loadGroups();
    return () => { isMounted = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  // Re-fetch skill types whenever the teacher opens the skill panel so that
  // skills created by an admin/principal after the page loaded are visible
  // immediately — without requiring a full page reload.
  useEffect(() => {
    if (actionTab === 'skill') {
      loadSkillTypes();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [actionTab]);

  const loadSessionInfo = async (studentList) => {
    try {
      const res = await api.get(`/session/${sessionId}`);
      if (res.data) {
        if (res.data.status === 'completed' || res.data.status === 'archived' || res.data.status === 'cancelled') {
          toast.info(t('thisSessionHasEndedPleaseStartANewOne'));
          navigate('/teacher', { replace: true });
          return;
        }
        setSessionInfo(prev => ({ ...prev, ...res.data }));
        if (res.data.start_time) setStartTime(res.data.start_time);
        if (res.data.interaction_mode) {
          const found = MODES.find(m => m.id === res.data.interaction_mode);
          if (found) {
            setMode(found);
            setActionTab(getTabForMode(found.id));
            if (found.id === 'homework') loadHomeworkStatuses(studentList);
          }
        }
        if (res.data.stats) {
          setStats({
            questions: res.data.stats.questions_asked || 0,
            correct: res.data.stats.correct_answers || 0,
            participation: 0,
          });
        }
      }
    } catch (e) { console.error('Error loading session data:', e); }
  };

  const loadSkillTypes = async () => {
    try {
      const res = await api.get('/skills-types');
      setSkillTypes(res.data || []);
    } catch (e) {
      console.error('Error loading skill types:', e);
    }
  };

  const loadSubjectsList = useCallback(async () => {
    try {
      const res = await api.get('/subjects');
      const data = res.data;
      setSubjectsList(Array.isArray(data) ? data : (data?.subjects || []));
    } catch (e) {
      console.error('Error loading subjects:', e);
    }
  }, [api]);

  const loadGroups = useCallback(async () => {
    if (!sessionId) return;
    try {
      const res = await api.get(`/session/${sessionId}/groups`);
      const list = Array.isArray(res.data?.groups) ? res.data.groups : [];
      // Backend is authoritative — overwrite any optimistic sessionStorage paint.
      setGroups(list);
    } catch (e) {
      console.error('Error loading groups:', e);
    } finally {
      groupsLoadedRef.current = true;
    }
  }, [api, sessionId]);

  const loadSessionSettings = useCallback(async () => {
    if (!sessionId) return;
    try {
      const res = await api.get(`/session/${sessionId}/settings`);
      const s = res.data || {};
      if (s.subject_id) setSettingsSubjectId(String(s.subject_id));
      setParticipationEnabled(s.participation_enabled !== false);
      setHomeworkEnabled(s.homework_enabled !== false);
      setHomeworkViewMode(s.homework_view_mode || 'not_submitted');
      setRecitationEnabled(!!s.recitation_enabled);
      setRecitationMaxAttempts(Number(s.recitation_max_attempts) || 1);
      setSkillEnabled(!!s.skill_enabled);
      // Hydrate followup columns from saved settings if any (single source of truth)
      if (Array.isArray(s.extra_columns) && s.extra_columns.length > 0) {
        setFollowupColumns(s.extra_columns.map(migrateColumn));
        setShowAddOtherItems(true);
      }
      if (s.participation_scores && typeof s.participation_scores === 'object') {
        setParticipationScores(s.participation_scores);
      }
      const caw = s.correct_answer_weight;
      setCorrectAnswerWeight(caw != null ? Number(caw) : null);
      setCorrectAnswerWeightDirty(false);
      // effective_correct_answer_weight is the resolved value after the
      // session-override → tenant-default → system-default (5) waterfall.
      const ecaw = s.effective_correct_answer_weight;
      setEffectiveCorrectAnswerWeight(ecaw != null ? Number(ecaw) : 5);
    } catch (e) {
      console.error('Error loading session settings:', e);
    }
  }, [api, sessionId]);

  const saveSessionSettings = async () => {
    // Subject is inherited from the active session context — the
    // teacher no longer picks it from the settings dialog. Fall back
    // to the session's own subject_id if the local settings state
    // hasn't been hydrated yet.
    const effectiveSubjectId = settingsSubjectId
      || sessionInfo?.subject_id
      || sessionInfo?.subjectId
      || '';
    if (!effectiveSubjectId) {
      toast.error(t('selectSubjectFirst'));
      return;
    }
    setSavingSettings(true);
    try {
      const settingsPayload = {
        subject_id: effectiveSubjectId,
        participation_enabled: participationEnabled,
        homework_enabled: homeworkEnabled,
        homework_view_mode: homeworkViewMode,
        recitation_enabled: recitationEnabled,
        recitation_max_attempts: recitationMaxAttempts,
        skill_enabled: skillEnabled,
        extra_columns: followupColumns,
        participation_scores: participationScores,
      };
      // Only include correct_answer_weight when the teacher explicitly changed
      // it in this dialog session. Omitting the key entirely means "don't touch"
      // on the backend, preventing an accidental clear of a previously saved weight.
      if (correctAnswerWeightDirty) {
        settingsPayload.correct_answer_weight = correctAnswerWeight;
      }
      await api.post(`/session/${sessionId}/settings`, settingsPayload);
      // Persist grade values via the serialized flush so this settings-save
      // can never race another follow-up writer. Columns are owned by the
      // class-level grade-columns API (single source of truth shared with سجل الطلاب).
      await flushFollowupRecord({ silent: true }).catch(() => {});
      toast.success(t('saved') || t('saveSettings'));
      setCorrectAnswerWeightDirty(false);
      setShowSidebarSettings(false);
      loadSessionSettings();
    } catch (e) {
      console.error('Error saving session settings:', e);
      toast.error(t('errorOccurred') || 'Error');
    } finally {
      setSavingSettings(false);
    }
  };

  const loadStudents = async () => {
    try {
      const res = await api.get(`/session/${sessionId}/students`);
      const list = (res.data?.students || []).map(s => ({
        ...s,
        // Server is the source of truth for the badge totals: interaction_count
        // is the per-student count of non-reversed session interactions, so a
        // post-undo refresh only changes the truly-reversed student's number
        // instead of zeroing the whole roster.
        interactionCount: s.interaction_count || 0,
        correctAnswers: s.correct_answers || 0,
        isFlashing: false,
      }));
      setStudents(list);
      // Keep the selected-student detail panel in sync with the authoritative
      // server totals so it agrees with the roster badge after an undo/refresh.
      setSelectedStudent(prev => {
        if (!prev) return prev;
        const fresh = list.find(s => s.id === prev.id);
        if (!fresh) return prev;
        return {
          ...prev,
          interactionCount: fresh.interactionCount,
          correctAnswers: fresh.correctAnswers,
          interaction_count: fresh.interaction_count,
          correct_answers: fresh.correct_answers,
          participation_count: fresh.participation_count,
        };
      });
      return list;
    } catch (e) {
      console.error('Error loading students:', e);
      return [];
    }
  };

  // Finalize the live-session attendance register: approve the canonical
  // session-attendance drafts (which also syncs the school-wide daily table)
  // and refresh the roster / live metrics / session info so the summary and
  // every live panel read the same persisted source of truth. Idempotent on
  // the backend, but we only run it when the register actually changed.
  const finalizeSessionAttendance = async () => {
    if (!sessionId || !attendanceDirtyRef.current) return;
    attendanceDirtyRef.current = false;
    try {
      await api.post(`/session/${sessionId}/attendance/approve`);
      const refreshed = await loadStudents();
      await loadSessionInfo(refreshed);
      loadLiveMetrics();
    } catch (e) {
      attendanceDirtyRef.current = true;
      nassaqError(getApiErrorMessage(e) || t('saveFailed') || 'فشل حفظ الحضور');
    }
  };

  const loadNotes = useCallback(async () => {
    if (!sessionId) return;
    try {
      const res = await api.get(`/session/${sessionId}/notes`);
      setNotes(res.data?.notes || []);
    } catch (e) { console.error('Error loading notes:', e); }
  }, [api, sessionId]);

  const peekUndoState = useCallback(async () => {
    if (!sessionId) return;
    try {
      const res = await api.get(`/session/${sessionId}/undo/peek`);
      const data = res.data || {};
      const hasReversible = data.has_reversible === true;
      setCanUndo(hasReversible);
      setUndoCount(hasReversible ? (data.stack_depth ?? 1) : 0);
      setUndoPeekData(
        hasReversible
          ? { event_type: data.event_type, student_name: data.student_name }
          : null
      );
    } catch (e) {
      // Non-fatal — leave canUndo as-is if the peek fails
    }
  }, [sessionId]);

  const loadActivityLog = async () => {
    try {
      const res = await api.get(`/session/${sessionId}/activity`);
      const entries = res.data?.activity || [];
      if (entries.length > 0) {
        setActivityLog(entries);
        setStats(prev => {
          const questions = entries.filter(e => e.emoji === 'correct' || e.emoji === 'wrong' || e.emoji === 'skip' || e.emoji === '✅' || e.emoji === '❌' || e.emoji === '⏭️').length;
          const correct = entries.filter(e => e.emoji === 'correct' || e.emoji === '✅').length;
          const participation = entries.filter(e => e.emoji === 'participation' || e.emoji === '🙋' || e.emoji === '😶').length;
          return {
            questions: Math.max(prev.questions, questions),
            correct: Math.max(prev.correct, correct),
            participation: Math.max(prev.participation, participation),
          };
        });
      }
    } catch (e) { console.error('Error loading activity log:', e); }
  };

  const loadLiveMetrics = useCallback(async () => {
    if (!sessionId) return;
    try {
      const res = await api.get(`/session/${sessionId}/live-metrics`);
      setLiveMetrics(res.data);
      if (res.data?.interaction) {
        setStats(prev => ({
          questions: res.data.interaction.total_questions || prev.questions,
          correct: res.data.interaction.correct_answers || prev.correct,
          participation: res.data.interaction.total_participations || prev.participation
        }));
      }
    } catch (e) { console.error('Error loading live metrics:', e); }
  }, [api, sessionId]);

  useEffect(() => {
    if (!sessionId) return;
    loadNotes();
    loadLiveMetrics();
    loadFollowupRecord();
    const interval = setInterval(loadLiveMetrics, 30000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, loadNotes, loadLiveMetrics]);

  const autoSaveRef = useRef(null);
  useEffect(() => {
    if (!sessionId) return;
    const saveState = () => {
      try {
        sessionStorage.setItem(`session_state_${sessionId}`, JSON.stringify({
          evalMode, groups, stats, mode: mode?.id, actionTab, followupData, followupColumns, followupAbsences,
          manualFollowupCells: [...manualFollowupCells.current],
          customPositiveBehaviours, customNegativeBehaviours, customSkills, customEvaluationItems
        }));
        // Follow-up grade/absence persistence now flows exclusively through the
        // serialized flush (debounce while typing + flush on close + Save Class).
        // The old direct POST here raced those writes and could land a stale
        // blob on the server; sessionStorage above remains the local backstop.
      } catch (e) { /* ignore */ }
    };
    autoSaveRef.current = setInterval(saveState, 10000);
    return () => { if (autoSaveRef.current) clearInterval(autoSaveRef.current); };
  }, [sessionId, evalMode, groups, stats, mode, actionTab, followupData, followupColumns, followupAbsences, api, customPositiveBehaviours, customNegativeBehaviours, customSkills, customEvaluationItems]);

  // ---- Follow-up record persistence (كشف المتابعة) -------------------------
  // The follow-up grade/absence state lives in this parent component so it
  // survives the dialog closing, but a close never persisted the pending edit
  // and the next reopen blind-replaced local state from a stale server copy —
  // losing the edit. We now (1) debounce a save while typing, (2) flush on
  // close, and (3) make the reopen reload wait for any in-flight flush. Refs
  // mirror the latest state so the flush always posts the most recent values
  // without recreating the callback on every keystroke.
  const followupDataRef = useRef(followupData);
  const followupAbsencesRef = useRef(followupAbsences);
  useEffect(() => { followupDataRef.current = followupData; }, [followupData]);
  useEffect(() => { followupAbsencesRef.current = followupAbsences; }, [followupAbsences]);
  const followupSaveTimer = useRef(null);
  // Serializes saves so an older (stale) snapshot can never land on the server
  // after a newer one. Each queued flush reads the latest refs at send time and
  // waits for the previous flush to finish, so the last write always wins. The
  // ref itself never rejects, so a reopen can await it safely.
  const followupFlushChain = useRef(Promise.resolve());

  const flushFollowupRecord = useCallback(({ silent = false } = {}) => {
    if (!sessionId) return Promise.resolve();
    const run = async () => {
      // Persist ONLY the cells the teacher has taken manual ownership of (and
      // that hold a non-empty value). Everything else is session-derived and is
      // re-hydrated live on read — re-posting a derived value as a manual
      // override would freeze the cell against later sidebar scoring. An empty
      // manual cell is an explicit "revert to derived": pickManualCells omits it
      // so the replace-on-save drops the stored override.
      const data = pickManualCells(followupDataRef.current || {}, manualFollowupCells.current);
      const absences = followupAbsencesRef.current || {};
      // Skip only when there is genuinely nothing to persist. An empty payload
      // WITH dirty cells/absences is meaningful — it's a deletion (e.g. the
      // teacher removed the last absence and there are no grades), so it must
      // still POST {} to clear the server record and release the dirty markers.
      if (isFollowupNoOpFlush(data, absences, dirtyFollowupCells.current, dirtyFollowupAbsences.current)) {
        return;
      }
      // Snapshot the revision of every dirty cell this POST is about to persist,
      // so a successful save only clears cells not edited again mid-flight.
      const sentRev = new Map();
      dirtyFollowupCells.current.forEach((k) => sentRev.set(k, followupCellRev.current.get(k) || 0));
      const sentAbsRev = new Map();
      dirtyFollowupAbsences.current.forEach((sid) => sentAbsRev.set(sid, followupAbsenceRev.current.get(sid) || 0));
      try {
        await api.post(`/session/${sessionId}/followup-record`, { data, absences });
        // Confirmed on the server: clear only the cells/students whose value did
        // not change since this POST's snapshot was taken (later edits stay dirty).
        sentRev.forEach((rev, k) => {
          if ((followupCellRev.current.get(k) || 0) === rev) dirtyFollowupCells.current.delete(k);
        });
        sentAbsRev.forEach((rev, sid) => {
          if ((followupAbsenceRev.current.get(sid) || 0) === rev) dirtyFollowupAbsences.current.delete(sid);
        });
      } catch (e) {
        // Never drop the edit on failure: surface a safe Arabic message (unless
        // this is the silent backstop) and keep the value — and its dirty mark —
        // in memory so a reopen merges around it instead of clobbering it.
        if (!silent) {
          nassaqError(getApiErrorMessage(e) || t('errorSaving') || 'تعذّر حفظ درجات الحصة');
        }
        throw e;
      }
    };
    // Append to the chain; a prior failure must not block later saves, and the
    // chain ref never rejects so the reopen effect can await it safely.
    const next = followupFlushChain.current.catch(() => {}).then(run);
    followupFlushChain.current = next.catch(() => {});
    return next;
  }, [api, sessionId, nassaqError, t]);

  // Debounced backstop: fires 1.5 s after the last edit so rapid consecutive
  // keystrokes cannot postpone a save indefinitely (the old 10 s interval reset
  // its timer on every keystroke). Silent — failures are retried/surfaced on close.
  const scheduleFollowupSave = useCallback(() => {
    if (followupSaveTimer.current) clearTimeout(followupSaveTimer.current);
    followupSaveTimer.current = setTimeout(() => {
      flushFollowupRecord({ silent: true }).catch(() => {});
    }, 1500);
  }, [flushFollowupRecord]);

  // Persist pending edits whenever the sheet closes — the إغلاق button, the
  // Escape key, and click-outside all route through the dialog's onOpenChange.
  // We persist FIRST and dismiss only after the save resolves: cancel the
  // debounce, flush non-silently, and close on success. On failure the sheet
  // stays open with the edit intact — flushFollowupRecord already surfaced a
  // safe Arabic NassaqAlertDialog — so the teacher can retry, never losing data.
  const handleFollowupOpenChange = useCallback(async (next) => {
    if (next) {
      setShowFollowupRecord(true);
      return;
    }
    const hadPending = !!followupSaveTimer.current;
    if (followupSaveTimer.current) {
      clearTimeout(followupSaveTimer.current);
      followupSaveTimer.current = null;
    }
    const needsFlush = hadPending
      || dirtyFollowupCells.current.size > 0
      || dirtyFollowupAbsences.current.size > 0;
    await runFollowupClose({
      needsFlush,
      flush: () => flushFollowupRecord(),
      dismiss: () => setShowFollowupRecord(false),
    });
  }, [flushFollowupRecord]);

  useEffect(() => {
    if (!sessionId) return;
    try {
      const saved = sessionStorage.getItem(`session_state_${sessionId}`);
      if (saved) {
        const state = JSON.parse(saved);
        if (state.evalMode) setEvalMode(state.evalMode);
        if (state.groups?.length) setGroups(state.groups);
        if (state.followupData && Object.keys(state.followupData).length > 0) setFollowupData(state.followupData);
        // Restore manual-override ownership so a flush before the first GET sends
        // the real overrides instead of {} (which would wipe the server record).
        if (Array.isArray(state.manualFollowupCells)) manualFollowupCells.current = new Set(state.manualFollowupCells);
        if (state.followupColumns?.length) setFollowupColumns(state.followupColumns.map(migrateColumn));
        if (state.followupAbsences && Object.keys(state.followupAbsences).length > 0) setFollowupAbsences(state.followupAbsences);
        // Migrate legacy string[] entries -> {id, name, points} objects
        const migrateBhv = (arr, defaultPoints) => (arr || []).map((b, i) => (
          typeof b === 'string'
            ? { id: `legacy_${defaultPoints > 0 ? 'p' : 'n'}_${i}_${b}`, name: b, points: defaultPoints }
            : b
        ));
        if (state.customPositiveBehaviours?.length) setCustomPositiveBehaviours(migrateBhv(state.customPositiveBehaviours, 2));
        if (state.customNegativeBehaviours?.length) setCustomNegativeBehaviours(migrateBhv(state.customNegativeBehaviours, -2));
        if (state.customSkills?.length) setCustomSkills(state.customSkills);
        if (state.customEvaluationItems?.length) setCustomEvaluationItems(state.customEvaluationItems);
      }
    } catch (e) { /* ignore */ }
  }, [sessionId]);

  // Persist groups to the durable session record (create/update/delete) whenever
  // they change. Debounced so rapid edits (drag, rename, add) coalesce into one
  // write. Gated on groupsLoadedRef so the initial mount/hydration never clobbers
  // the backend with empty state before the authoritative load completes.
  useEffect(() => {
    if (!sessionId || !groupsLoadedRef.current) return;
    if (groupsSaveRef.current) clearTimeout(groupsSaveRef.current);
    groupsSaveRef.current = setTimeout(() => {
      api.post(`/session/${sessionId}/groups`, { groups }).catch(() => {});
    }, 800);
    return () => { if (groupsSaveRef.current) clearTimeout(groupsSaveRef.current); };
  }, [groups, sessionId, api]);

  const [dragStudent, setDragStudent] = useState(null);

  const autoGroupByLevel = (studentsList = null) => {
    const list = studentsList || students.filter(s => s.attendance_status === 'present');
    if (list.length === 0) {
      setGroups([]);
      toast.success(t('groupsCreatedAutomatically'));
      return;
    }

    // Scenario A: try to bucket students by an explicit level signal
    // (high / medium / low). When no explicit `level` field is present
    // we derive a coarse signal from in-session activity so that classes
    // already running for a while still get differentiated buckets.
    const classify = (s) => {
      const level = s.level || s.student_level || s.academic_level;
      if (level === 'advanced'     || level === 'high'   || level === 'متقدم') return 'high';
      if (level === 'intermediate' || level === 'medium' || level === 'متوسط') return 'medium';
      if (level === 'beginner'     || level === 'low'    || level === 'مبتدئ') return 'low';
      const score = Number(s.correct_answers || s.correctAnswers || 0);
      const count = Number(s.interaction_count || s.interactionCount || 0);
      if (count >= 5 && score >= 3) return 'high';
      if (count >= 2) return 'medium';
      if (count > 0) return 'low';
      return null; // no signal available
    };

    const buckets = { high: [], medium: [], low: [] };
    let unsignalled = 0;
    list.forEach(s => {
      const tier = classify(s);
      if (tier) buckets[tier].push(s);
      else unsignalled += 1;
    });

    const filled = Object.values(buckets).filter(b => b.length > 0).length;
    const useLevels = filled >= 2 && unsignalled === 0;

    let newGroups = [];
    if (useLevels) {
      if (buckets.high.length)   newGroups.push({ id: 'g-high',   name: t('advancedLevel'),     color: 'bg-green-600', students: buckets.high.map(s => s.id) });
      if (buckets.medium.length) newGroups.push({ id: 'g-medium', name: t('intermediateLevel'), color: 'bg-blue-600',  students: buckets.medium.map(s => s.id) });
      if (buckets.low.length)    newGroups.push({ id: 'g-low',    name: t('beginnerLevel'),     color: 'bg-amber-600', students: buckets.low.map(s => s.id) });
    } else {
      // Scenario B: no useful level data (or every student lands in the
      // same bucket) — split the roster into 3 evenly-sized groups so the
      // teacher gets distinct cards instead of one giant pile.
      const palette = ['bg-green-600', 'bg-blue-600', 'bg-amber-600'];
      const groupCount = Math.min(3, list.length);
      const chunks = Array.from({ length: groupCount }, () => []);
      list.forEach((s, idx) => { chunks[idx % groupCount].push(s); }); // round-robin keeps sizes balanced
      newGroups = chunks
        .filter(c => c.length > 0)
        .map((chunk, i) => ({
          id: `g-auto-${i + 1}`,
          name: `${t('group')} ${i + 1}`,
          color: palette[i % palette.length],
          students: chunk.map(s => s.id),
        }));
    }

    setGroups(newGroups);
    toast.success(t('groupsCreatedAutomatically'));
  };

  const handleDragStart = (studentId) => setDragStudent(studentId);
  const handleDropOnGroup = (groupIndex) => {
    if (!dragStudent) return;
    const updated = groups.map((g, i) => ({
      ...g,
      students: i === groupIndex
        ? [...new Set([...(g.students || []), dragStudent])]
        : (g.students || []).filter(id => id !== dragStudent)
    }));
    setGroups(updated);
    setDragStudent(null);
  };

  const defaultColumns = [
    { id: 'participation', name: 'المشاركة', maxGrade: 10, type: 'grade', group: 'coursework' },
    { id: 'homework', name: 'الواجبات', maxGrade: 10, type: 'grade', group: 'coursework' },
    { id: 'performance_task', name: 'المهام الأدائية', maxGrade: 20, type: 'grade', group: 'coursework' },
    { id: 'short_test', name: 'الاختبار القصير', maxGrade: 20, type: 'grade', group: 'exams' },
    { id: 'final_test', name: 'اختبار نهاية الفترة', maxGrade: 40, type: 'grade', group: 'exams' },
  ];

  const migrateColumn = (col) => {
    if (col.group) return col;
    const idLower = String(col.id || '').toLowerCase();
    const nameStr = String(col.name || '');
    const isExam = /test|exam|quiz/.test(idLower) || /اختبار|امتحان/.test(nameStr);
    return { ...col, group: isExam ? 'exams' : 'coursework', hidden: !!col.hidden };
  };

  const loadFollowupRecord = useCallback(async () => {
    if (!sessionId) return;
    try {
      const res = await api.get(`/session/${sessionId}/followup-record`);
      // Columns are now loaded from the class-level endpoint (single source of
      // truth shared with فصولي → سجل الطلاب). The session record only stores
      // grade values and absence dates.
      setFollowupData(res.data?.data || {});
      setFollowupAbsences(res.data?.absences || {});
      // Seed manual-override ownership from the server (authoritative) plus any
      // still-unsaved local edit, so the next flush sends exactly the manual set.
      manualFollowupCells.current = computeManualKeys(res.data?.manual_keys, dirtyFollowupCells.current);
    } catch (e) { /* ignore */ }
  }, [api, sessionId]);

  // Polling variant: merges fresh server-derived values into followupData
  // without touching cells the teacher has already edited manually.
  const mergeFollowupRecord = useCallback(async () => {
    if (!sessionId) return;
    try {
      const res = await api.get(`/session/${sessionId}/followup-record`);
      const fresh = res.data?.data || {};
      setFollowupData(prev => mergeFollowupData(fresh, prev, dirtyFollowupCells.current));
      // Re-derive manual ownership: server truth ∪ unsaved-dirty. A cell the
      // teacher cleared falls out of both, so its override is forgotten and the
      // cell reverts to the live-derived value on the next flush.
      manualFollowupCells.current = computeManualKeys(res.data?.manual_keys, dirtyFollowupCells.current);
      // Merge absences around any student whose absence list the teacher is
      // mid-editing (dirty), so the poll can't clobber an unsaved absence edit;
      // non-dirty students always sync to the fresh server values.
      setFollowupAbsences(prev => mergeFollowupAbsences(res.data?.absences, prev, dirtyFollowupAbsences.current));
    } catch { /* silent — polling errors must not surface to the user */ }
  }, [api, sessionId]);

  // Adapt backend grade-column shape to FollowupGradesTable's local shape.
  // Both keep the backend UUID as `id` so grade values map correctly across UIs.
  const adaptBackendColumn = (c) => ({
    id: c.id,
    name: c.name,
    group: c.column_type === 'exams' ? 'exams' : 'coursework',
    maxGrade: c.max_grade,
    hidden: c.visible === false,
    type: 'grade',
    _order: c.order ?? 0,
  });

  const classIdForGrades = sessionInfo?.class_id || sessionInfo?.classId || null;

  const loadClassGradeColumns = useCallback(async () => {
    if (!classIdForGrades) return;
    try {
      const res = await api.get(`/class/${classIdForGrades}/grade-columns`);
      const list = Array.isArray(res.data) ? res.data : [];
      const adapted = list
        .map(adaptBackendColumn)
        .sort((a, b) => (a._order || 0) - (b._order || 0));
      setFollowupColumns(adapted);
    } catch (e) {
      console.error('loadClassGradeColumns failed', e);
    }
  }, [api, classIdForGrades]);

  const addClassGradeColumn = useCallback(async ({ name, group, maxGrade }) => {
    if (!classIdForGrades) {
      toast.error('لا يمكن حفظ العمود — معرف الفصل غير متوفر');
      return false;
    }
    if (!name || !name.trim()) {
      toast.error(t('columnNameRequired') || 'يرجى إدخال اسم العمود');
      return false;
    }
    try {
      await api.post(`/class/${classIdForGrades}/grade-columns`, {
        name: name.trim(),
        column_type: group === 'exams' ? 'exams' : 'coursework',
        max_grade: Math.max(1, Number(maxGrade) || 10),
        order: followupColumns.length + 1,
      });
      toast.success(t('columnAdded') || 'تم إضافة العمود');
      await loadClassGradeColumns();
      return true;
    } catch (err) {
      console.error(err);
      const detail = getApiErrorMessage(err) || err?.message || (t('saveFailed') || 'فشل الحفظ');
      toast.error(detail);
      return false;
    }
  }, [api, classIdForGrades, followupColumns.length, loadClassGradeColumns, t]);

  const updateClassGradeColumn = useCallback(async (columnId, patch) => {
    if (!columnId) return false;
    const body = {};
    if (patch.name !== undefined) body.name = patch.name;
    if (patch.maxGrade !== undefined) body.max_grade = Math.max(1, Number(patch.maxGrade) || 1);
    if (patch.hidden !== undefined) body.visible = !patch.hidden;
    if (patch.order !== undefined) body.order = patch.order;
    try {
      await api.put(`/grade-column/${columnId}`, body);
      await loadClassGradeColumns();
      return true;
    } catch (err) {
      console.error(err);
      const detail = getApiErrorMessage(err) || err?.message || (t('saveFailed') || 'فشل الحفظ');
      toast.error(detail);
      return false;
    }
  }, [api, loadClassGradeColumns, t]);

  const deleteClassGradeColumn = useCallback(async (columnId) => {
    if (!columnId) return false;
    try {
      await api.delete(`/grade-column/${columnId}`);
      toast.success(t('columnDeleted') || 'تم حذف العمود');
      await loadClassGradeColumns();
      return true;
    } catch (err) {
      console.error(err);
      const detail = getApiErrorMessage(err) || err?.message || (t('saveFailed') || 'فشل الحفظ');
      toast.error(detail);
      return false;
    }
  }, [api, loadClassGradeColumns, t]);

  // Re-fetch class-level columns AND the follow-up record whenever the
  // كشف المتابعة dialog is opened, so the Live Class always shows the same
  // columns as فصولي → سجل الطلاب, and the report reflects the latest
  // session-derived (live-scored) values once the columns are loaded.
  useEffect(() => {
    if (showFollowupRecord && classIdForGrades) {
      loadClassGradeColumns();
      // If a previous close is still flushing edits, wait for it first so the
      // GET returns the just-saved values. Then MERGE rather than blind-replace:
      // a successful flush leaves no dirty cells (merge == full refresh), but if
      // a close-save failed its cells stay dirty and the merge preserves the
      // teacher's unsaved edits instead of clobbering them with stale data.
      let cancelled = false;
      (async () => {
        const pending = followupFlushChain.current;
        if (pending) { try { await pending; } catch { /* surfaced on close */ } }
        if (!cancelled) mergeFollowupRecord();
      })();
      return () => { cancelled = true; };
    }
  }, [showFollowupRecord, classIdForGrades, loadClassGradeColumns, mergeFollowupRecord]);

  // While the dialog is open, poll every 30 s so that interaction-point totals
  // derived on the backend stay current without the teacher having to close and
  // re-open the report.  Uses mergeFollowupRecord (not loadFollowupRecord) so
  // cells the teacher is actively editing are preserved.
  useEffect(() => {
    if (!showFollowupRecord) return;
    const id = setInterval(mergeFollowupRecord, 30_000);
    return () => clearInterval(id);
  }, [showFollowupRecord, mergeFollowupRecord]);

  // Grade-change handler defined here (in SessionTeachPage scope) so it can
  // reference dirtyFollowupCells, which is also defined here.  Passed down to
  // FollowupRecordDialog as the onGradeChange prop.
  const handleFollowupGradeChange = useCallback((sid, cid, value) => {
    const key = `${sid}:${cid}`;
    dirtyFollowupCells.current.add(key);
    // The teacher took manual ownership of this cell — it must be sent on every
    // future flush (not just until the next successful save) so it overrides the
    // live-derived value instead of being treated as a derived echo and dropped.
    manualFollowupCells.current.add(key);
    followupCellRev.current.set(key, (followupCellRev.current.get(key) || 0) + 1);
    setFollowupData(prev => ({
      ...prev,
      [sid]: { ...(prev[sid] || {}), [cid]: value },
    }));
    scheduleFollowupSave();
  }, [scheduleFollowupSave]);

  // Absence add/remove run here (parent scope) so they can mark the per-student
  // dirty/revision state and schedule the same serialized flush as grade edits.
  const markFollowupAbsenceDirty = useCallback((studentId) => {
    dirtyFollowupAbsences.current.add(studentId);
    followupAbsenceRev.current.set(studentId, (followupAbsenceRev.current.get(studentId) || 0) + 1);
    scheduleFollowupSave();
  }, [scheduleFollowupSave]);
  const handleFollowupAbsenceAdd = useCallback((studentId, date) => {
    if (!date) return;
    setFollowupAbsences(prev => {
      const list = prev[studentId] || [];
      if (list.includes(date)) return prev;
      return { ...prev, [studentId]: [...list, date].sort() };
    });
    markFollowupAbsenceDirty(studentId);
  }, [markFollowupAbsenceDirty]);
  const handleFollowupAbsenceRemove = useCallback((studentId, date) => {
    setFollowupAbsences(prev => {
      const list = (prev[studentId] || []).filter(d => d !== date);
      const next = { ...prev };
      if (list.length === 0) delete next[studentId];
      else next[studentId] = list;
      return next;
    });
    markFollowupAbsenceDirty(studentId);
  }, [markFollowupAbsenceDirty]);

  const [canUndo, setCanUndo] = useState(false);
  const [undoCount, setUndoCount] = useState(0);
  const [undoPeekData, setUndoPeekData] = useState(null);
  const [undoLoading, setUndoLoading] = useState(false);

  const [remainingMinutes, setRemainingMinutes] = useState(null);

  useEffect(() => {
    const endStr = sessionInfo?.scheduled_end_time || sessionInfo?.scheduledEndTime
      || sessionInfo?.planned_end_time || sessionInfo?.plannedEndTime;
    if (!endStr) return;
    const checkTime = () => {
      const remaining = (new Date(endStr).getTime() - Date.now()) / 60000;
      setRemainingMinutes(Math.ceil(remaining));
      if (remaining <= 0 && timeWarning !== 'ended') {
        setTimeWarning('ended');
      } else if (remaining > 0 && remaining <= 10 && timeWarning !== '10min') {
        setTimeWarning('10min');
      }
    };
    checkTime();
    const id = setInterval(checkTime, 15000);
    return () => clearInterval(id);
  }, [sessionInfo, timeWarning]);

  const addNote = async () => {
    if (!newNote.trim()) return;
    try {
      await api.post(`/session/${sessionId}/note`, {
        text: newNote,
        note_type: noteType,
        student_id: selectedStudent?.id || null,
      });
      setNewNote('');
      toast.success(t('noteAdded'));
      loadNotes();
      addLog('note', `${t('note')}: ${newNote.slice(0, 30)}...`, 'text-amber-600');
    } catch (e) {
      console.error('Error adding note:', e);
      nassaqError(t('errorAddingNote'));
    }
  };

  const deleteNote = async (noteId) => {
    try {
      await api.delete(`/session/${sessionId}/note/${noteId}`);
      toast.success(t('noteDeleted'));
      loadNotes();
    } catch (e) {
      console.error('Error deleting note:', e);
      nassaqError(t('errorDeletingNote'));
    }
  };

  const getTabForMode = (modeId) => {
    if (modeId === 'quiz') return 'question';
    if (modeId === 'review') return 'participation';
    if (modeId === 'homework') return 'homework';
    return 'question';
  };

  const [homeworkLoading, setHomeworkLoading] = useState(false);

  const loadHomeworkStatuses = async (studentList) => {
    const list = studentList || students;
    setHomeworkLoading(true);
    try {
      const res = await api.get(`/session/${sessionId}/homework`);
      const serverStatuses = res.data?.statuses || {};
      const presentIds = list.filter(s => s.attendance_status === 'present').map(s => s.id);
      const merged = {};
      presentIds.forEach(id => { merged[id] = serverStatuses[id] || 'done'; });
      setHomeworkStatuses(merged);
    } catch (e) {
      console.error('Error loading homework statuses:', e);
      const presentIds = list.filter(s => s.attendance_status === 'present').map(s => s.id);
      const defaults = {};
      presentIds.forEach(id => { defaults[id] = 'done'; });
      setHomeworkStatuses(defaults);
    } finally {
      setHomeworkLoading(false);
    }
  };

  const toggleHomework = async (studentId) => {
    const current = homeworkStatuses[studentId];
    const newStatus = current === 'done' ? 'not_done' : 'done';
    setHomeworkStatuses(prev => ({ ...prev, [studentId]: newStatus }));
    try {
      await api.post(`/session/${sessionId}/homework`, {
        student_id: studentId,
        status: newStatus
      });
      const studentName = students.find(s => s.id === studentId)?.full_name?.split(' ')[0] || '';
      if (newStatus === 'done') {
        toast.success(`${t('submitted')} — ${studentName}`);
      } else {
        toast.success(`${t('notSubmitted')} — ${studentName}`);
      }
    } catch (e) {
      console.error('Error toggling homework:', e);
      setHomeworkStatuses(prev => ({ ...prev, [studentId]: current || 'not_done' }));
      nassaqError(t('errorUpdatingHomework'));
    }
  };

  const handleSetMode = async (m) => {
    if (mode?.id === m.id) return;
    try {
      await api.post(`/session/${sessionId}/mode`, { mode: m.id });
      setMode(m);
      setActionTab(getTabForMode(m.id));
      if (m.id === 'homework' && students.length > 0) loadHomeworkStatuses();
      toast.success(`${t('modeActivated')}: ${t(m.labelKey)}`, { id: 'session-mode' });
    } catch (e) {
      console.error('Error setting session mode:', e);
      nassaqError(t('errorSettingMode'));
    }
  };

  const selectRandom = async () => {
    if (loading) return;
    setLoading(true);
    setSelectedStudent(null);
    setShowHakim(true);

    const presentStudents = students.filter(s => s.attendance_status === 'present');
    if (!presentStudents.length) {
      nassaqError(t('noPresentStudents'));
      setLoading(false);
      setShowHakim(false);
      return;
    }

    let count = 0;
    const maxFlash = 20;
    flashRef.current = setInterval(() => {
      count++;
      const r = presentStudents[Math.floor(Math.random() * presentStudents.length)];
      setFlashId(r.id);
      if (count >= maxFlash) clearInterval(flashRef.current);
    }, 100);

    try {
      const res = await api.post(`/session/${sessionId}/random-student`);
      await new Promise(r => setTimeout(r, 2100));
      clearInterval(flashRef.current);
      const sel = res.data;
      setFlashId(sel.student_id);
      setSelectedStudent({
        id: sel.student_id,
        full_name: sel.full_name,
        student_code: sel.student_code,
        avatar_url: sel.avatar_url,
        gender: sel.gender || 'male',
        participation_count: sel.participation_count,
        correct_answers: sel.correct_answers || 0,
        interaction_count: sel.interaction_count || 0,
      });
      confetti({ particleCount: 30, spread: 50, origin: { y: 0.6 }, colors: ['#0ea5e9', '#14b8a6'] });
      setActionTab(getTabForMode(mode?.id));
      setShowRandomPopup(true);
    } catch (err) {
      clearInterval(flashRef.current);
      setFlashId(null);
      nassaqError(getApiErrorMessage(err) || t('errorPickingStudent'));
    } finally {
      setLoading(false);
      setTimeout(() => setShowHakim(false), 1500);
    }
  };

  const handleStudentClick = (student) => {
    if (student.attendance_status !== 'present') return;
    setFlashId(student.id);
    setSelectedStudent(student);
    setActionTab(getTabForMode(mode?.id));
  };

  // Open the Quick Note dialog with one student preselected (used by inline row action).
  const openQuickNoteForStudent = (student) => {
    if (!student?.id) return;
    setQuickNoteText('');
    setQuickNoteFilter('');
    setQuickNoteIds(new Set([student.id]));
    setShowQuickNote(true);
  };

  const addLog = (emoji, text, color = 'text-foreground') => {
    setActivityLog(prev => [{ id: Date.now(), emoji, text, color, time: new Date().toLocaleTimeString(isRTL ? 'ar' : 'en', { hour: '2-digit', minute: '2-digit' }) }, ...prev].slice(0, 30));
  };

  // Record a teacher-defined evaluation item from the right action
  // sidebar. Score-bearing items (points != 0) are routed through the
  // canonical scoring endpoint so the configured points reach the
  // Follow-up Report and the school / parent profiles; genuinely
  // non-scoring items stay a cosmetic note.
  const recordCustomEvaluation = async (item) => {
    if (!selectedStudent) { toast.error(t('selectStudentFirst') || 'اختر طالباً أولاً'); return; }
    const points = Number(item?.points) || 0;
    const signed = points > 0 ? `+${points}` : String(points);
    const firstName = selectedStudent.full_name?.split(' ')[0] || '';
    try {
      if (points !== 0) {
        // Score-bearing evaluation item: route through the canonical scoring
        // pipeline so the points reach the Follow-up Report and the school /
        // parent profiles instead of being a cosmetic note.
        await api.post(`/session/${sessionId}/evaluation`, {
          student_id: selectedStudent.id,
          name: item.name,
          points,
          item_id: item.id,
        });
        setStudents(prev => prev.map(s =>
          s.id === selectedStudent.id ? { ...s, interactionCount: (s.interactionCount || 0) + 1 } : s
        ));
        setSelectedStudent(prev => prev ? {
          ...prev,
          interactionCount: (prev.interactionCount || 0) + 1,
          interaction_count: (prev.interaction_count || 0) + 1,
        } : null);
      } else {
        // Genuinely non-scoring item stays a note.
        await api.post(`/session/${sessionId}/note`, {
          student_id: selectedStudent.id,
          text: `${item.name}`,
          note_type: 'evaluation',
        });
      }
      toast.success(`${firstName} — ${item.name}${points ? ` (${signed})` : ''}`);
      addLog(
        'note',
        `${firstName} — ${item.name}${points ? ` (${signed})` : ''}`,
        points > 0 ? 'text-emerald-700' : points < 0 ? 'text-red-600' : 'text-muted-foreground',
      );
    } catch (e) {
      console.error('Error recording evaluation:', e);
      nassaqError(t('errorRecordingAnswer'));
    }
  };

  const recordAnswer = async (result) => {
    if (!selectedStudent) return;
    try {
      const res = await api.post(`/session/${sessionId}/answer`, {
        student_id: selectedStudent.id,
        result,
      });
      const change = res.data?.score_change || 0;
      if (result === 'correct') {
        confetti({ particleCount: 80, spread: 70, origin: { y: 0.6 }, colors: ['#10b981', '#fbbf24', '#6366f1'] });
        setTimeout(() => confetti({ particleCount: 40, angle: 60, spread: 55, origin: { x: 0 } }), 200);
        setTimeout(() => confetti({ particleCount: 40, angle: 120, spread: 55, origin: { x: 1 } }), 400);
        toast.success(`${selectedStudent.full_name?.split(' ')[0]} ${t('answeredCorrectly')} +${change}`);
        addLog('correct', `${selectedStudent.full_name?.split(' ')[0]} — ${t('correctAnswer')} (+${change})`, 'text-green-700');
        setStats(p => ({ ...p, questions: p.questions + 1, correct: p.correct + 1 }));
      } else if (result === 'wrong') {
        toast.info(`${selectedStudent.full_name?.split(' ')[0]} — ${t('wrongAnswer')}`);
        addLog('wrong', `${selectedStudent.full_name?.split(' ')[0]} — ${t('wrongAnswer')}`, 'text-red-600');
        setStats(p => ({ ...p, questions: p.questions + 1 }));
      } else {
        toast.success(`${selectedStudent.full_name?.split(' ')[0]} — ${t('didNotAnswer')} (${change})`);
        addLog('skip', `${selectedStudent.full_name?.split(' ')[0]} — ${t('didNotAnswer')} (${change})`, 'text-amber-600');
        setStats(p => ({ ...p, questions: p.questions + 1 }));
      }
      setCanUndo(true);
      void peekUndoState();
      setStudents(prev => prev.map(s =>
        s.id === selectedStudent.id
          ? { ...s, interactionCount: s.interactionCount + 1, correctAnswers: result === 'correct' ? s.correctAnswers + 1 : s.correctAnswers }
          : s
      ));
      setSelectedStudent(prev => prev ? {
        ...prev,
        interactionCount: (prev.interactionCount || 0) + 1,
        interaction_count: (prev.interaction_count || 0) + 1,
        correctAnswers: result === 'correct' ? (prev.correctAnswers || 0) + 1 : (prev.correctAnswers || 0),
        correct_answers: result === 'correct' ? (prev.correct_answers || 0) + 1 : (prev.correct_answers || 0),
        participation_count: (prev.participation_count || 0) + 1,
      } : null);
    } catch (e) {
      console.error('Error recording answer:', e);
      nassaqError(t('errorRecordingAnswer'));
    }
  };

  const recordParticipation = async (pType) => {
    if (!selectedStudent) return;
    try {
      const payload = {
        student_id: selectedStudent.id,
        type: pType.id,
      };
      const configuredScore = participationScores[pType.id];
      if (Number.isFinite(Number(configuredScore)) && Number(configuredScore) > 0 && Number(configuredScore) <= 100) {
        payload.points_override = Number(configuredScore);
      }
      const res = await api.post(`/session/${sessionId}/participation`, payload);
      const change = res.data?.score_change || 0;
      toast.success(`${t(pType.labelKey)} — ${selectedStudent.full_name?.split(' ')[0]}`);
      addLog('participation', `${selectedStudent.full_name?.split(' ')[0]} — ${t(pType.labelKey)} (${change > 0 ? '+' : ''}${change})`, change >= 0 ? 'text-blue-700' : 'text-amber-700');
      setCanUndo(true);
      void peekUndoState();
      setStats(p => ({ ...p, participation: p.participation + 1 }));
      setStudents(prev => prev.map(s =>
        s.id === selectedStudent.id ? { ...s, interactionCount: s.interactionCount + 1 } : s
      ));
      setSelectedStudent(prev => prev ? {
        ...prev,
        interactionCount: (prev.interactionCount || 0) + 1,
        interaction_count: (prev.interaction_count || 0) + 1,
        participation_count: (prev.participation_count || 0) + 1,
      } : null);
    } catch (e) {
      console.error('Error recording participation:', e);
      nassaqError(t('errorRecordingParticipation'));
    }
  };

  const recordBehaviour = async (bType) => {
    if (!selectedStudent) return;
    try {
      const res = await api.post(`/session/${sessionId}/behaviour`, {
        student_id: selectedStudent.id,
        category: behaviourCategory,
        behaviour_type: bType.id,
        details: behaviourNote || null,
      });
      const change = res.data?.score_change || 0;
      const signed = change > 0 ? `+${change}` : String(change);
      const bLabel = bType.labelKey ? t(bType.labelKey) : bType.label;
      const firstName = selectedStudent.full_name?.split(' ')[0];
      const toastMsg = `${t('behaviour')}: ${bLabel} — ${firstName}${change ? ` (${signed})` : ''}`;
      // Sign-aware toast so a negative behaviour reads as a deduction, not a win.
      if (change < 0) {
        toast.info(toastMsg);
      } else {
        toast.success(toastMsg);
      }
      addLog('behaviour', `${firstName} — ${bLabel} (${signed})`, behaviourCategory === 'negative' ? 'text-red-600' : 'text-purple-700');
      setCanUndo(true);
      void peekUndoState();
      // Optimistically reflect the behaviour in the live student stats so the
      // teacher sees it register instantly (mirrors answers/participation). A
      // behaviour counts as an interaction in get_session_students, so only the
      // interaction tally is bumped here — participation_count stays server-owned.
      setStudents(prev => prev.map(s =>
        s.id === selectedStudent.id ? { ...s, interactionCount: (s.interactionCount || 0) + 1 } : s
      ));
      setSelectedStudent(prev => prev ? {
        ...prev,
        interactionCount: (prev.interactionCount || 0) + 1,
        interaction_count: (prev.interaction_count || 0) + 1,
      } : null);
      setBehaviourNote('');
    } catch (e) {
      console.error('Error recording behaviour:', e);
      nassaqError(t('errorRecordingBehaviour'));
    }
  };

  const recordSkill = async (skill) => {
    if (!selectedStudent) return;
    // `isCustom` is an explicit flag carried on the picker entry (see the
    // skill list builders below) — never re-derived from an id prefix. It only
    // routes whether the skill is an ad-hoc custom one (no stored skill type)
    // vs. a registered type; it does NOT decide whether the configured value
    // is honored. That value is always sent and is authoritative server-side.
    const isCustom = !!skill.isCustom;
    try {
      // Both predefined and custom skills go through the same `/skill`
      // endpoint so the student's score is updated in the backend (mirrors
      // how positive behaviours work). The skill's configured magnitude is
      // always carried through as `points_override` so the awarded points
      // match the badge shown on the button. For registered skill types the
      // backend treats its own stored value as authoritative; custom skills
      // additionally pass `custom_name` so they are recorded without a type.
      const payload = {
        student_id: selectedStudent.id,
        skill_type_id: skill.id,
        notes: skillNote || null,
      };
      const pts = Number(skill.points);
      if (Number.isFinite(pts)) payload.points_override = Math.abs(pts);
      if (isCustom) {
        payload.custom_name = skill.name_ar || skill.name;
      }
      const res = await api.post(`/session/${sessionId}/skill`, payload);
      const change = res?.data?.score_change || 0;
      confetti({ particleCount: 50, spread: 60, origin: { y: 0.6 }, colors: ['#8b5cf6', '#a78bfa', '#c4b5fd'] });
      toast.success(`${t('skill')}: ${skill.name_ar || skill.name} — ${selectedStudent.full_name?.split(' ')[0]}`);
      addLog('skill', `${selectedStudent.full_name?.split(' ')[0]} — ${skill.name_ar || skill.name} (${change > 0 ? '+' : ''}${change})`, 'text-purple-700');
      setCanUndo(true);
      void peekUndoState();
      setSkillNote('');
      setStudents(prev => prev.map(s =>
        s.id === selectedStudent.id ? { ...s, interactionCount: s.interactionCount + 1 } : s
      ));
      setSelectedStudent(prev => prev ? {
        ...prev,
        interactionCount: (prev.interactionCount || 0) + 1,
        interaction_count: (prev.interaction_count || 0) + 1,
      } : null);
    } catch (e) {
      console.error('Error recording skill:', e?.response?.status, e?.response?.data, e);
      const status = e?.response?.status;
      const detail = getApiErrorMessage(e) || e?.response?.data?.message || e?.message;
      if (status === 404) {
        // Skill type not found — refresh the list as a safety net.
        loadSkillTypes();
        nassaqError(detail ? `${t('errorRecordingSkill')}: ${detail}` : t('errorRecordingSkill'));
      } else {
        nassaqError(detail ? `${t('errorRecordingSkill')}: ${detail}` : t('errorRecordingSkill'));
      }
    }
  };

  const recordRecitation = async (mastered) => {
    if (!selectedStudent) return;
    try {
      const label = mastered ? t('recitationMastered') : t('recitationNotMastered');
      const noteSuffix = recitationNote ? ` - ${recitationNote}` : '';
      await api.post(`/session/${sessionId}/note`, {
        student_id: selectedStudent.id,
        text: `${t('recitation')}: ${label} (${t('attempts')}: ${recitationAttempts})${noteSuffix}`,
        note_type: 'recitation',
      });
      if (mastered) {
        confetti({ particleCount: 40, spread: 60, origin: { y: 0.6 }, colors: ['#10b981', '#34d399', '#6ee7b7'] });
      }
      toast.success(`${t('recitation')}: ${label} — ${selectedStudent.full_name?.split(' ')[0]}`);
      addLog('skill', `${selectedStudent.full_name?.split(' ')[0]} — ${t('recitation')} ${label} (${recitationAttempts})`, mastered ? 'text-emerald-700' : 'text-amber-700');
      setRecitationNote('');
      setRecitationAttempts(1);
      setStudents(prev => prev.map(s =>
        s.id === selectedStudent.id ? { ...s, interactionCount: (s.interactionCount || 0) + 1 } : s
      ));
      setSelectedStudent(prev => prev ? {
        ...prev,
        interactionCount: (prev.interactionCount || 0) + 1,
        interaction_count: (prev.interaction_count || 0) + 1,
      } : null);
    } catch (e) {
      console.error('Error recording recitation:', e);
      nassaqError(t('errorRecordingSkill'));
    }
  };

  const UNDO_EVENT_LABELS = {
    answer_recorded: t('undoEventAnswer') || 'إجابة',
    participation_recorded: t('undoEventParticipation') || 'مشاركة',
    behaviour_recorded: t('undoEventBehaviour') || 'سلوك',
    skill_recorded: t('undoEventSkill') || 'مهارة / تلاوة',
    evaluation_recorded: t('undoEventEvaluation') || 'تقييم',
  };

  const undoLastAction = () => {
    const peekLabel = undoPeekData
      ? `${UNDO_EVENT_LABELS[undoPeekData.event_type] || undoPeekData.event_type}${undoPeekData.student_name ? ` — ${undoPeekData.student_name}` : ''}`
      : null;
    const confirmMsg = peekLabel
      ? (t('undoLastActionConfirmSpecific') || 'تراجع: {action}. سيتم استعادة النقاط إن وُجدت.').replace('{action}', peekLabel)
      : t('undoLastActionConfirm') || 'هل تريد التراجع عن آخر إجراء؟ سيتم استعادة النقاط إن وُجدت.';
    nassaqConfirm(
      confirmMsg,
      async () => {
        setUndoLoading(true);
        try {
          await api.post(`/session/${sessionId}/undo`);
          toast.success(t('undoSuccess') || 'تم التراجع عن الإجراء بنجاح');
          await Promise.all([loadStudents(), loadActivityLog(), loadLiveMetrics(), peekUndoState(), loadFollowupRecord()]);
        } catch (e) {
          const status = e?.response?.status;
          if (status === 400) {
            nassaqError(t('undoNoAction') || 'لا توجد إجراءات يمكن التراجع عنها');
            setCanUndo(false);
            setUndoCount(0);
          } else if (status === 404) {
            nassaqError(t('undoSessionNotFound') || 'الجلسة غير موجودة');
            setCanUndo(false);
            setUndoCount(0);
          } else if (status === 403) {
            nassaqError(t('undoNotAllowed') || 'ليس لديك صلاحية للتراجع عن هذا الإجراء');
            setCanUndo(false);
            setUndoCount(0);
          } else if (status === 409) {
            nassaqError(t('undoSessionEnded') || 'لا يمكن التراجع — الحصة منتهية');
            setCanUndo(false);
            setUndoCount(0);
          } else {
            nassaqError(t('errorOccurred') || 'حدث خطأ');
          }
        } finally {
          setUndoLoading(false);
        }
      },
      { confirmText: t('undoLastAction') || 'تراجع' }
    );
  };

  const [pendingOps, setPendingOps] = useState([]);

  const checkPendingOps = useCallback(() => {
    const ops = [];
    const hasAttendance = sessionInfo?.attendance_approved || sessionInfo?.attendanceApproved;
    if (!hasAttendance) {
      ops.push({ id: 'attendance', label: t('attendanceNotApproved'), severity: 'error' });
    }
    if (stats.questions === 0 && stats.participation === 0) {
      ops.push({ id: 'no_interaction', label: t('noInteractionsRecorded'), severity: 'warning' });
    }
    return ops;
  }, [sessionInfo, stats, t]);

  const startEndReview = async () => {
    const ops = checkPendingOps();
    setPendingOps(ops);
    setReviewLoading(true);
    try {
      const res = await api.get(`/session/${sessionId}/review-preview`);
      setReviewData(res.data);
      setShowEndDialog(false);
    } catch (err) {
      nassaqError(getApiErrorMessage(err) || t('errorLoadingSessionSummary'));
    } finally {
      setReviewLoading(false);
    }
  };

  const confirmEndSession = async () => {
    setLoading(true);
    try {
      const body = closingNote.trim() ? { closing_note: closingNote.trim() } : {};
      const res = await api.post(`/session/${sessionId}/end`, body);
      setSummary(res.data);
      setReviewData(null);
      toast.success(t('sessionEndedSuccessfully'));
    } catch (err) {
      const detail = getApiErrorMessage(err) || '';
      if (detail.includes('إنهاء') && detail.includes('مسبق')) {
        toast.info(t('sessionAlreadyEnded'));
        navigate('/teacher', { replace: true });
      } else {
        nassaqError(detail || (t('errorEndingSession')));
      }
    } finally {
      setLoading(false);
    }
  };

  const returnFromReview = () => {
    setReviewData(null);
    setClosingNote('');
  };

  const presentStudents = students.filter(s => s.attendance_status === 'present');
  const maleStudents = presentStudents.filter(s => s.gender !== 'female');
  const femaleStudents = presentStudents.filter(s => s.gender === 'female');
  const hasGenderSplit = femaleStudents.length > 0 && maleStudents.length > 0;
  const accuracy = stats.questions > 0 ? Math.round((stats.correct / stats.questions) * 100) : 0;

  const filteredStudents = searchQuery
    ? presentStudents.filter(s => s.full_name?.toLowerCase().includes(searchQuery.toLowerCase()))
    : presentStudents;
  const getGroupForStudent = (studentId) => groups.find(g => g.students?.includes(studentId));
  const unassignedStudents = evalMode === 'group'
    ? filteredStudents.filter(s => !groups.some(g => g.students?.includes(s.id)))
    : [];

  if (reviewData) {
    return (
      <SectionErrorBoundary name="SessionReviewPhase" isRTL={isRTL}>
        <SessionReviewPhase
          reviewData={reviewData}
          sessionInfo={sessionInfo}
          closingNote={closingNote}
          setClosingNote={setClosingNote}
          onConfirm={confirmEndSession}
          onBack={returnFromReview}
          loading={loading}
          isRTL={isRTL}
        />
      </SectionErrorBoundary>
    );
  }

  if (summary) {
    return (
      <SectionErrorBoundary name="SessionSummary" isRTL={isRTL}>
        <SessionSummary summary={summary} sessionInfo={sessionInfo} onHome={() => navigate('/teacher')} isRTL={isRTL} />
      </SectionErrorBoundary>
    );
  }

  return (
    <SectionErrorBoundary name="SessionTeachView" isRTL={isRTL}>
    <div
      className="h-[100dvh] min-h-[100dvh] flex flex-col overflow-hidden text-foreground"
      dir={isRTL ? 'rtl' : 'ltr'}
      style={{
        backgroundColor: 'hsl(var(--background))',
        backgroundImage: `
          radial-gradient(ellipse 80% 60% at ${isRTL ? '85%' : '15%'} -10%, rgba(217, 165, 87, 0.10), transparent 60%),
          radial-gradient(ellipse 70% 50% at ${isRTL ? '15%' : '85%'} 110%, rgba(45, 212, 191, 0.08), transparent 60%),
          linear-gradient(180deg, hsl(var(--background)) 0%, hsl(var(--background)) 100%)
        `,
      }}
    >
      {/* ── Header — Compact (redesign) ── */}
      <header className="border-b border-border bg-background/80 backdrop-blur-md px-3 sm:px-4 py-2 flex-none shrink-0 relative">
        <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-amber-500/30 to-transparent" aria-hidden="true" />
        <div className="w-full flex items-center justify-between gap-3">
          {/* Right side (RTL): title + counts */}
          <div className="flex items-center gap-3 min-w-0 flex-1">
            <div className="w-[3px] self-stretch rounded-full bg-gradient-to-b from-amber-400 to-amber-600 shadow-[0_0_8px_rgba(217,165,87,0.5)]" aria-hidden="true" />
            <div className="min-w-0">
              <h1 className="font-cairo font-extrabold text-foreground text-sm sm:text-base leading-tight truncate">
                {sessionInfo?.subject_name || sessionInfo?.subjectName} {sessionInfo?.class_name ? `— ${sessionInfo.class_name}` : ''}
              </h1>
              <div className="flex items-center gap-3 mt-0.5">
                <span className="inline-flex items-center gap-1 text-[11px] font-cairo font-bold text-emerald-600 dark:text-emerald-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" aria-hidden="true" />
                  <span className="tabular-nums">{presentStudents.length}</span> {t('present')}
                </span>
                <span className="inline-flex items-center gap-1 text-[11px] font-cairo font-bold text-rose-600 dark:text-rose-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-rose-500" aria-hidden="true" />
                  <span className="tabular-nums">{Math.max(0, (students?.length || 0) - presentStudents.length)}</span> {t('absent')}
                </span>
                <span className="hidden sm:inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                  <Clock className="h-3 w-3 text-amber-500" />
                  <span className="font-mono tabular-nums">{timer}</span>
                </span>
              </div>
            </div>
          </div>

          {/* Left side: back arrow only (overflow menu removed; actions redistributed to header/footer/student rows) */}
          <div className="flex items-center gap-1 flex-none">
            <button
              onClick={() => navigate('/teacher')}
              aria-label={t('back') || 'رجوع'}
              className="p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-foreground/[0.06] transition-colors"
              title={t('back') || 'رجوع'}
            >
              {isRTL ? <ArrowLeft className="h-5 w-5" /> : <ArrowRight className="h-5 w-5" />}
            </button>
          </div>
        </div>
      </header>

      {/* ── Toolbar (redesign) ── */}
      <div className="flex-none border-b border-border bg-background/60 px-3 sm:px-4 py-2 flex items-center gap-2 flex-wrap">
        {/* Single refresh control for the page. The duplicate refresh
            icon that used to live in the bottom bar was removed; this
            labeled button is now the canonical "تحديث" action and is
            styled to match the other header buttons. */}
        <button
          onClick={() => { loadStudents(); loadActivityLog(); }}
          className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md text-xs font-cairo font-bold text-muted-foreground hover:text-foreground bg-foreground/[0.04] hover:bg-foreground/[0.08] border border-border transition-colors"
          title={t('refresh') || 'تحديث'}
          aria-label={t('refresh') || 'تحديث'}
        >
          <RotateCcw className="h-3.5 w-3.5" />
          <span>{t('refresh') || 'تحديث'}</span>
        </button>
        <button
          onClick={undoLastAction}
          disabled={!canUndo || undoLoading}
          className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md text-xs font-cairo font-bold border transition-colors disabled:opacity-40 disabled:cursor-not-allowed text-amber-700 dark:text-amber-300 border-amber-400/40 hover:bg-amber-500/10 enabled:hover:text-amber-800"
          title={t('undoLastAction') || 'تراجع عن آخر إجراء'}
          aria-label={t('undoLastAction') || 'تراجع عن آخر إجراء'}
        >
          {undoLoading
            ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            : <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />}
          <span className="hidden sm:inline">{t('undoLastAction') || 'تراجع'}</span>
          {canUndo && undoCount > 0 && (
            <span className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-700 dark:text-amber-300 border border-amber-400/40 leading-none tabular-nums">
              {undoCount}
            </span>
          )}
        </button>
        <div className="flex items-center bg-foreground/[0.04] border border-border rounded-md p-0.5">
          <button
            onClick={() => setEvalMode('individual')}
            aria-pressed={evalMode === 'individual'}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-bold transition-colors ${
              evalMode === 'individual' ? 'bg-foreground/10 text-amber-700 dark:text-amber-300' : 'text-muted-foreground hover:text-foreground/80'
            }`}
          >
            <User className="h-3 w-3" /> {t('individual')}
          </button>
          <button
            onClick={() => setEvalMode('group')}
            aria-pressed={evalMode === 'group'}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-bold transition-colors ${
              evalMode === 'group' ? 'bg-foreground/10 text-amber-700 dark:text-amber-300' : 'text-muted-foreground hover:text-foreground/80'
            }`}
          >
            <UsersRound className="h-3 w-3" /> {t('groups')}
          </button>
        </div>
        {/* Record Attendance (in-class) — opens unified inline-editable attendance modal */}
        <button
          onClick={() => setShowAttendanceModal(true)}
          disabled={!classIdForGrades}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-teal-500 hover:bg-teal-600 text-white text-[11px] font-bold shadow-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          title={t('recordAttendance') || 'تسجيل الحضور'}
          aria-label={t('recordAttendance') || 'تسجيل الحضور'}
          data-testid="open-attendance-modal-btn"
        >
          <ClipboardCheck className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">{t('recordAttendance') || 'تسجيل الحضور'}</span>
        </button>
        {/* Send Quick Note (global) — moved out of overflow menu */}
        <button
          onClick={() => {
            setQuickNoteText(''); setQuickNoteIds(new Set()); setQuickNoteFilter('');
            setShowQuickNote(true);
          }}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-amber-400/40 text-amber-700 dark:text-amber-300 hover:bg-amber-500/10 text-[11px] font-bold transition-colors"
          title={t('sendQuickNote') || 'إرسال ملاحظة سريعة'}
          aria-label={t('sendQuickNote') || 'إرسال ملاحظة سريعة'}
        >
          <StickyNote className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">{t('sendQuickNote') || 'إرسال ملاحظة سريعة'}</span>
        </button>
        {evalMode === 'group' && (
          <button
            onClick={() => setShowGroupModal(true)}
            className="p-2 rounded-md text-purple-700 dark:text-purple-300 hover:bg-purple-500/15 transition-colors"
            title={t('manageGroups')}
            aria-label={t('manageGroups')}
          >
            <Settings className="h-4 w-4" />
          </button>
        )}
        <button
          onClick={selectRandom}
          disabled={loading}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-md border border-amber-400/40 text-amber-700 dark:text-amber-300 hover:bg-amber-500/10 text-sm font-medium transition-colors disabled:opacity-50"
          title={t('randomStudentPick') || 'اختيار عشوائي'}
          aria-label={t('randomStudentPick') || 'اختيار عشوائي'}
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Shuffle className="h-4 w-4" />}
          <span className="hidden sm:inline">{t('randomStudentPick') || 'اختيار عشوائي'}</span>
        </button>
        <div className="flex-1 min-w-[140px] relative">
          <Search className="absolute start-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder={t('search')}
            className="w-full bg-foreground/[0.04] border border-border rounded-md ps-8 pe-2 py-1.5 text-xs outline-none focus:border-amber-400/60 placeholder:text-muted-foreground"
          />
        </div>
        {selectedStudent && (
          <span className="text-[11px] text-amber-700 dark:text-amber-300 font-bold flex items-center gap-1">
            <UserCheck className="h-3 w-3" /> {selectedStudent.full_name}
            <button onClick={() => { setSelectedStudent(null); setShowActionSheet(false); }} className="ms-1 hover:text-rose-500" aria-label="clear">
              <X className="h-3 w-3" />
            </button>
          </span>
        )}
      </div>

      {false && (
        <div className="w-full flex items-center justify-between gap-2 sm:gap-3 flex-wrap">
          <div className="flex items-center gap-3 min-w-0 flex-1 sm:flex-initial">
            {/* Gold accent rail + class info */}
            <div className="flex items-stretch gap-3 min-w-0">
              <div className="w-[3px] rounded-full bg-gradient-to-b from-amber-400 via-amber-500 to-amber-600 shadow-[0_0_8px_rgba(217,165,87,0.5)]" aria-hidden="true" />
              <div className="min-w-0 py-0.5">
                <div className="flex items-center gap-2">
                  <h1 className="font-cairo font-extrabold text-foreground text-base tracking-tight truncate leading-none">
                    {sessionInfo?.subject_name || sessionInfo?.subjectName}
                  </h1>
                  {mode && (
                    <span className="hidden sm:inline-flex items-center gap-1.5 text-emerald-700 dark:text-emerald-300 text-[10px] uppercase tracking-[0.18em] font-semibold">
                      <span className="relative flex h-1.5 w-1.5" aria-hidden="true">
                        <span className="absolute inset-0 rounded-full bg-emerald-400 animate-ping opacity-60" />
                        <span className="relative rounded-full h-1.5 w-1.5 bg-emerald-400" />
                      </span>
                      {t('teachingNow')}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                  <p className="text-muted-foreground text-[11px] tracking-wide truncate">{sessionInfo?.class_name || sessionInfo?.className}</p>
                  <span className="inline-flex items-center gap-1 text-[10px] font-cairo font-bold text-emerald-500/90" title={t('present')}>
                    <span className="w-1 h-1 rounded-full bg-emerald-500" aria-hidden="true" />
                    <span className="tabular-nums">{presentStudents.length}</span> {t('present')}
                  </span>
                  <span className="inline-flex items-center gap-1 text-[10px] font-cairo font-bold text-rose-500/90" title={t('absent')}>
                    <span className="w-1 h-1 rounded-full bg-rose-500" aria-hidden="true" />
                    <span className="tabular-nums">{Math.max(0, (students?.length || 0) - presentStudents.length)}</span> {t('absent')}
                  </span>
                </div>
              </div>
            </div>
            {/* Gold time chip */}
            <div className="hidden sm:flex items-center gap-1.5 ms-1 ps-3 border-s border-border">
              <Clock className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400/80" aria-hidden="true" />
              <span className="font-mono text-foreground text-sm font-bold tabular-nums tracking-wider">{timer}</span>
            </div>
          </div>

          {/* Live stats bar — editorial micro-labels */}
          <div className="hidden md:flex items-center gap-5 text-muted-foreground">
            <span className="flex flex-col items-center leading-none">
              <span className="text-foreground text-sm font-bold tabular-nums">{presentStudents.length}</span>
              <span className="text-[9px] uppercase tracking-[0.16em] text-muted-foreground mt-0.5">{t('present')}</span>
            </span>
            <span className="w-px h-6 bg-foreground/10" aria-hidden="true" />
            <span className="flex flex-col items-center leading-none">
              <span className="text-foreground text-sm font-bold tabular-nums">{stats.questions}</span>
              <span className="text-[9px] uppercase tracking-[0.16em] text-muted-foreground mt-0.5">{t('question')}</span>
            </span>
            <span className="w-px h-6 bg-foreground/10" aria-hidden="true" />
            <span className="flex flex-col items-center leading-none">
              <span className={`text-sm font-bold tabular-nums ${accuracy >= 60 ? 'text-emerald-700 dark:text-emerald-300' : 'text-rose-700 dark:text-rose-300'}`}>{accuracy}%</span>
              <span className="text-[9px] uppercase tracking-[0.16em] text-muted-foreground mt-0.5">{t('correct')}</span>
            </span>
          </div>

          <div className="flex items-center gap-1.5 flex-wrap justify-end">
            <button
              onClick={() => setShowSearch(v => !v)}
              aria-label={t('search')}
              className="p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-foreground/[0.06] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
              title={t('search')}
            >
              <Search className="h-4 w-4" />
            </button>

            <button
              onClick={() => {
                setQuickNoteText('');
                setQuickNoteIds(new Set());
                setQuickNoteFilter('');
                setShowQuickNote(true);
              }}
              aria-label={t('sendQuickNote') || 'إرسال ملاحظة'}
              className="p-2 rounded-md text-amber-700 dark:text-amber-300 hover:text-amber-200 hover:bg-amber-500/10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
              title={t('sendQuickNote') || 'إرسال ملاحظة'}
            >
              <StickyNote className="h-4 w-4" />
            </button>

            {/* Toggle right panel (desktop only) */}
            <button
              onClick={() => setPanelOpen(v => !v)}
              aria-label={panelOpen ? t('hideActivityPanel') : t('showActivityPanel')}
              aria-pressed={panelOpen}
              className="hidden lg:inline-flex p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-foreground/[0.06] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
              title={panelOpen ? t('hideActivityPanel') : t('showActivityPanel')}
            >
              {panelOpen
                ? <PanelRightClose className="h-4 w-4" />
                : <PanelRightOpen className="h-4 w-4" />}
            </button>

            <span className="hidden sm:block w-px h-5 bg-foreground/10 mx-1" aria-hidden="true" />

            <div className="hidden sm:flex items-center bg-foreground/[0.04] border border-border rounded-md p-0.5">
              <button
                onClick={() => setEvalMode('individual')}
                aria-pressed={evalMode === 'individual'}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[10px] uppercase tracking-[0.14em] font-semibold transition-colors ${
                  evalMode === 'individual' ? 'bg-foreground/10 text-amber-700 dark:text-amber-300' : 'text-muted-foreground hover:text-foreground/80'
                }`}
              >
                <User className="h-3 w-3" />
                {t('individual')}
              </button>
              <button
                onClick={() => setEvalMode('group')}
                aria-pressed={evalMode === 'group'}
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[10px] uppercase tracking-[0.14em] font-semibold transition-colors ${
                  evalMode === 'group' ? 'bg-foreground/10 text-amber-700 dark:text-amber-300' : 'text-muted-foreground hover:text-foreground/80'
                }`}
              >
                <UsersRound className="h-3 w-3" />
                {t('groups')}
              </button>
            </div>

            {evalMode === 'group' && (
              <button
                onClick={() => setShowGroupModal(true)}
                aria-label={t('manageGroups')}
                className="p-2 rounded-md text-purple-700 dark:text-purple-300 hover:bg-purple-500/15 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-400/70"
                title={t('manageGroups')}
              >
                <Settings className="h-4 w-4" />
              </button>
            )}

            {/* Mode segmented control — hidden per product requirement */}
            {false && (
              <>
                <span className="hidden sm:block w-px h-5 bg-foreground/10 mx-1" aria-hidden="true" />

                <div className="hidden sm:flex items-center gap-1">
                  {MODES.map(m => {
                    const active = mode?.id === m.id;
                    return (
                      <button
                        key={m.id}
                        onClick={() => handleSetMode(m)}
                        aria-pressed={active}
                        className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[11px] font-bold tracking-wide transition-all ${
                          active
                            ? `${m.color} text-foreground shadow-[0_0_0_1px_rgba(255,255,255,0.1)_inset]`
                            : 'text-muted-foreground hover:text-foreground hover:bg-foreground/[0.06]'
                        }`}
                      >
                        <m.icon className="h-3.5 w-3.5" />
                        {m.labelKey ? t(m.labelKey) : m.label}
                      </button>
                    );
                  })}
                </div>
              </>
            )}
            <button
              onClick={() => setShowSidebarSettings(true)}
              aria-label={t('sessionSettings')}
              className="ms-1 p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-foreground/[0.06] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
              title={t('sessionSettings')}
            >
              <Settings className="h-4 w-4" />
            </button>
            <Button
              size="sm"
              className="text-[11px] h-8 px-3 font-bold tracking-wide ms-1 bg-gradient-to-b from-rose-500 to-rose-600 hover:from-rose-400 hover:to-rose-500 text-foreground border border-rose-400/30 shadow-[0_4px_12px_-2px_rgba(244,63,94,0.4)] focus-visible:ring-rose-300"
              onClick={() => setShowEndDialog(true)}
              disabled={reviewLoading}
            >
              {reviewLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : t('endSession')}
            </Button>
          </div>
        </div>
      )}

      {timeWarning && (
        <div className={`flex-none px-4 py-2 text-center text-sm font-cairo font-bold flex items-center justify-center gap-2 ${
          timeWarning === 'ended' ? 'bg-red-600/90 text-foreground animate-pulse' : 'bg-amber-500/90 text-foreground'
        }`}>
          <Clock className="h-4 w-4" />
          {timeWarning === 'ended'
            ? t('sessionTimeEnded')
            : remainingMinutes !== null
              ? `${t('timeRemaining')}: ${remainingMinutes} ${t('minutes')}`
              : `${t('timeRemaining')}: 10 ${t('minutes')}`
          }
        </div>
      )}

      {/* ── Main layout: action sidebar on the visual right (mockup), student console on the left ── */}
      <div className={`flex-1 min-h-0 flex overflow-hidden w-full ${isRTL ? 'flex-row-reverse' : ''}`}>

        {/* ── Console (left 2/3) ── */}
        <div className="flex-1 flex flex-col overflow-hidden p-3 gap-3 min-h-0">

          {/* Search bar */}
          {showSearch && (
            <div className="flex-none">
              <div className="relative">
                <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  placeholder={t('searchStudentByName')}
                  className="w-full bg-foreground/10 text-foreground text-sm rounded-xl ps-10 pe-4 py-2.5 placeholder-muted-foreground outline-none border border-border focus:border-brand-turquoise/50 transition-colors"
                  autoFocus
                />
                {searchQuery && (
                  <button onClick={() => setSearchQuery('')} className="absolute end-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                    <XCircle className="h-4 w-4" />
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Hakim AI Selection Overlay */}
          {showHakim && (
            <div className="flex-none bg-gradient-to-r from-brand-turquoise/10 to-brand-navy/10 border border-brand-turquoise/30 rounded-xl px-4 py-2 flex items-center gap-3 animate-fade-in">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-brand-turquoise to-cyan-400 flex items-center justify-center shadow-lg shadow-brand-turquoise/40 animate-bounce">
                <Sparkles className="h-5 w-5 text-foreground" />
              </div>
              <div className="flex-1">
                <p className="text-brand-turquoise text-xs font-bold font-cairo">{t('hakimChoosing')}</p>
                <p className="text-muted-foreground text-[10px]">{t('findingBestStudent')}</p>
              </div>
              <Loader2 className="h-4 w-4 animate-spin text-brand-turquoise" />
            </div>
          )}

          {false && (() => {
            const accent = mode.id === 'review' ? 'purple' : mode.id === 'homework' ? 'blue' : 'amber';
            const ring = { purple: 'rgba(168,85,247,0.18)', blue: 'rgba(59,130,246,0.18)', amber: 'rgba(245,158,11,0.18)' }[accent];
            const text = { purple: 'text-purple-200', blue: 'text-sky-200', amber: 'text-amber-200' }[accent];
            const dot = { purple: 'bg-purple-400', blue: 'bg-sky-400', amber: 'bg-amber-400' }[accent];
            const label = { purple: 'text-purple-700 dark:text-purple-300/80', blue: 'text-sky-700 dark:text-sky-300/80', amber: 'text-amber-700 dark:text-amber-300/80' }[accent];
            const railFrom = { purple: 'from-purple-400', blue: 'from-sky-400', amber: 'from-amber-400' }[accent];
            const railTo = { purple: 'to-fuchsia-500', blue: 'to-blue-500', amber: 'to-orange-500' }[accent];
            return (
              <div
                className="relative flex-none shrink-0 flex items-center gap-3 ps-4 pe-3 py-2 rounded-md bg-foreground/[0.03] border border-border overflow-hidden"
                style={{ boxShadow: `inset 0 0 0 1px ${ring}` }}
              >
                <span className={`absolute inset-y-1 start-0 w-[3px] rounded-full bg-gradient-to-b ${railFrom} ${railTo}`} aria-hidden="true" />
                <mode.icon className={`h-4 w-4 ${text}`} aria-hidden="true" />
                <div className="flex-1 flex items-baseline gap-2 min-w-0">
                  <span className={`text-[9px] uppercase tracking-[0.2em] font-bold ${label}`}>{t('mode')}</span>
                  <span className={`text-xs font-semibold truncate ${text}`}>
                    {mode.id === 'review' ? t('reviewModeDesc') :
                     mode.id === 'homework' ? t('homeworkModeDesc') :
                     t('quizModeDesc')}
                  </span>
                </div>
                <span className={`w-1.5 h-1.5 rounded-full animate-pulse ${dot}`} aria-hidden="true" />
              </div>
            );
          })()}

          {/* Student grid — individual or group mode */}
          {/* Mode is no longer required to start the session — the grid renders immediately. */}
          <div className="flex-1 min-h-0 overflow-y-auto">
            {evalMode === 'group' ? (
              groups.length > 0 ? (
              <div className="space-y-3">
                {groups.map(group => {
                  const groupStudents = filteredStudents.filter(s => group.students?.includes(s.id));
                  if (groupStudents.length === 0) return null;
                  return (
                    <div key={group.id}>
                      <div className="flex items-center gap-2 mb-2">
                        <span className={`w-3 h-3 rounded-full ${group.color}`} />
                        <span className="text-muted-foreground text-xs font-medium font-cairo">{group.name} ({groupStudents.length})</span>
                        <div className="flex-1 h-px bg-foreground/10" />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        {groupStudents.map((student) => (
                          <StudentRow
                            key={student.id}
                            student={student}
                            isFlashing={flashId === student.id}
                            isSelected={selectedStudent?.id === student.id}
                            onClick={() => handleStudentClick(student)}
                            onSendNote={openQuickNoteForStudent}
                            homeworkEnabled={homeworkEnabled}
                            homeworkStatus={homeworkStatuses[student.id]}
                            onToggleHomework={toggleHomework}
                          />
                        ))}
                      </div>
                    </div>
                  );
                })}
                {unassignedStudents.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="w-3 h-3 rounded-full bg-brand-purple/40" />
                      <span className="text-muted-foreground text-xs font-medium font-cairo">{t('unassigned')} ({unassignedStudents.length})</span>
                      <div className="flex-1 h-px bg-foreground/10" />
                    </div>
                    <div className="flex flex-col gap-1.5">
                      {unassignedStudents.map((student) => (
                        <StudentRow
                          key={student.id}
                          student={student}
                          isFlashing={flashId === student.id}
                          isSelected={selectedStudent?.id === student.id}
                          onClick={() => handleStudentClick(student)}
                          onSendNote={openQuickNoteForStudent}
                          homeworkEnabled={homeworkEnabled}
                          homeworkStatus={homeworkStatuses[student.id]}
                          onToggleHomework={toggleHomework}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </div>
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-muted-foreground text-sm gap-3 py-8">
                  <UsersRound className="h-10 w-10 text-muted-foreground/50" />
                  <p className="font-cairo">{t('noGroupsCreated')}</p>
                  <button
                    onClick={() => setShowGroupModal(true)}
                    className="px-4 py-2 rounded-xl bg-purple-600/20 text-purple-600 dark:text-purple-400 text-sm font-medium hover:bg-purple-600/30 transition-colors border border-purple-500/30 flex items-center gap-2"
                  >
                    <UsersRound className="h-4 w-4" />
                    {t('manageGroups')}
                  </button>
                </div>
              )
            ) : hasGenderSplit ? (
              <div className="space-y-3">
                {[
                  { key: 'male', students: searchQuery ? filteredStudents.filter(s => s.gender !== 'female') : maleStudents },
                  { key: 'female', students: searchQuery ? filteredStudents.filter(s => s.gender === 'female') : femaleStudents },
                ].filter(g => g.students.length > 0).map(group => {
                  const gc = GENDER_COLORS[group.key];
                  const dotColor = group.key === 'male' ? 'bg-sky-400' : 'bg-pink-400';
                  const textColor = group.key === 'male' ? 'text-sky-200/90' : 'text-pink-200/90';
                  const countColor = group.key === 'male' ? 'text-sky-700 dark:text-sky-300' : 'text-pink-700 dark:text-pink-300';
                  return (
                    <div key={group.key}>
                      <div className="flex items-center gap-2 mb-2">
                        <span className={`w-2 h-2 rounded-full ${dotColor} shadow-[0_0_8px_currentColor]`} aria-hidden="true" />
                        <span className={`${textColor} text-[10px] uppercase tracking-[0.18em] font-bold`}>{gc.labelKey ? t(gc.labelKey) : gc.label}</span>
                        <span className={`${countColor} text-[10px] font-bold tabular-nums`}>({group.students.length})</span>
                        <div className="flex-1 h-px bg-foreground/10" />
                      </div>
                      <div className="flex flex-col gap-1.5">
                        {group.students.map((student) => (
                          <StudentRow
                            key={student.id}
                            student={student}
                            isFlashing={flashId === student.id}
                            isSelected={selectedStudent?.id === student.id}
                            onClick={() => handleStudentClick(student)}
                            onSendNote={openQuickNoteForStudent}
                            homeworkEnabled={homeworkEnabled}
                            homeworkStatus={homeworkStatuses[student.id]}
                            onToggleHomework={toggleHomework}
                          />
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="flex flex-col gap-1.5">
                {filteredStudents.map((student) => (
                  <StudentRow
                    key={student.id}
                    student={student}
                    isFlashing={flashId === student.id}
                    isSelected={selectedStudent?.id === student.id}
                    onClick={() => handleStudentClick(student)}
                    onSendNote={openQuickNoteForStudent}
                    homeworkEnabled={homeworkEnabled}
                    homeworkStatus={homeworkStatuses[student.id]}
                    onToggleHomework={toggleHomework}
                  />
                ))}
              </div>
            )}
          </div>

          {/* ── Central tabbed action panel — DEPRECATED (replaced by contextual popovers on the right sidebar). Gated to never render but kept for reference / fallback. ── */}
          {false && selectedStudent && showActionSheet && (
            <div className="flex-none shrink-0 flex flex-col bg-foreground/[0.02] rounded-xl border border-border overflow-hidden shadow-[0_8px_30px_-8px_rgba(0,0,0,0.5)] backdrop-blur-sm max-h-[60vh] sm:max-h-[55vh] relative">
              <button
                onClick={() => setShowActionSheet(false)}
                className="absolute top-2 end-2 z-20 p-1.5 rounded-md bg-foreground/10 hover:bg-foreground/20 text-muted-foreground hover:text-foreground"
                aria-label="close"
              >
                <X className="h-4 w-4" />
              </button>
              {/* Selected student header — Editorial profile */}
              <div className="flex-none shrink-0 px-5 py-4 border-b border-border bg-gradient-to-b from-foreground/[0.03] to-transparent relative overflow-hidden">
                <div className="absolute -top-8 -end-8 w-32 h-32 rounded-full bg-amber-500/[0.06] blur-2xl pointer-events-none" aria-hidden="true" />
                <div className="flex items-center gap-3 relative">
                  <div className="relative">
                    <Avatar className="h-14 w-14 ring-2 ring-amber-400/60 ring-offset-2 ring-offset-background shadow-[0_0_20px_rgba(245,158,11,0.25)]">
                      <AvatarImage src={selectedStudent.avatar_url} />
                      <AvatarFallback className={`${selectedStudent.gender === 'female' ? 'bg-gradient-to-br from-pink-500 to-rose-600' : 'bg-gradient-to-br from-sky-500 to-blue-600'} text-foreground text-base font-bold`}>
                        {selectedStudent.full_name?.charAt(0)}
                      </AvatarFallback>
                    </Avatar>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[9px] uppercase tracking-[0.22em] text-amber-700 dark:text-amber-300/90 font-bold mb-1">{t('selectedStudentLabel')}</p>
                    <p className="text-foreground font-cairo font-extrabold text-base truncate leading-tight">{selectedStudent.full_name}</p>
                    <p className="text-muted-foreground text-[11px] tracking-wide mt-0.5">{selectedStudent.student_code || sessionInfo?.class_name || sessionInfo?.className}</p>
                  </div>
                  <button
                    onClick={() => { setSelectedStudent(null); setFlashId(null); setShowActionSheet(false); }}
                    aria-label={t('close') || 'Close'}
                    className="text-muted-foreground hover:text-foreground p-1.5 rounded-md hover:bg-foreground/5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/60"
                  >
                    <XCircle className="h-5 w-5" />
                  </button>
                </div>
                <div className="grid grid-cols-3 gap-2 mt-3 relative">
                  {[
                    { value: selectedStudent.participation_count || selectedStudent.interactionCount || 0, labelKey: 'participations', accent: 'text-sky-700 dark:text-sky-300' },
                    { value: selectedStudent.correct_answers || selectedStudent.correctAnswers || 0, labelKey: 'correct', accent: 'text-emerald-700 dark:text-emerald-300' },
                    { value: selectedStudent.interaction_count || selectedStudent.interactionCount || 0, labelKey: 'interaction', accent: 'text-purple-700 dark:text-purple-300' },
                  ].map((kpi, i) => (
                    <div key={i} className="bg-foreground/[0.025] border border-border rounded-lg px-2 py-2 text-center">
                      <div className={`${kpi.accent} text-xl font-extrabold leading-none tabular-nums`}>{kpi.value}</div>
                      <div className="text-muted-foreground text-[9px] uppercase tracking-[0.14em] mt-1.5 font-semibold">{t(kpi.labelKey)}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Tabs */}
              <div className="flex-none shrink-0 flex border-b border-border overflow-x-auto">
                {[
                  { id: 'question', labelKey: 'question', icon: MessageCircle, forMode: 'quiz' },
                  { id: 'participation', labelKey: 'participationTab', icon: Hand, forMode: 'review', enabled: participationEnabled },
                  { id: 'homework', labelKey: 'modeHomework', icon: ClipboardCheck, forMode: 'homework', enabled: homeworkEnabled },
                  { id: 'recitation', labelKey: 'recitationTab', icon: Mic, enabled: recitationEnabled },
                  { id: 'behaviour', labelKey: 'behaviour', icon: ThumbsUp },
                  { id: 'skill', labelKey: 'skill', icon: Star, enabled: skillEnabled },
                ].filter(t => t.enabled !== false).map(tab => {
                  const isRecommended = tab.forMode && mode?.id === tab.forMode;
                  return (
                  <button
                    key={tab.id}
                    onClick={() => setActionTab(tab.id)}
                    className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-medium transition-colors relative ${
                      actionTab === tab.id ? 'text-brand-turquoise border-b-2 border-brand-turquoise' : 'text-muted-foreground hover:text-foreground/90'
                    }`}
                  >
                    <tab.icon className="h-3.5 w-3.5" />
                    {t(tab.labelKey)}
                    {isRecommended && actionTab !== tab.id && (
                      <span className="absolute top-1 end-2 w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                    )}
                  </button>
                  );
                })}
              </div>

              {/* Tab content */}
              <div className="flex-1 min-h-0 overflow-y-auto p-3 pb-4">
                {actionTab === 'question' && (
                  <div className="grid grid-cols-3 gap-2">
                    <ActionButton
                      color="bg-green-600 hover:bg-green-500"
                      icon={<CheckCircle2 className="h-5 w-5" />}
                      label={t('correct')}
                      sub="+5"
                      onClick={() => recordAnswer('correct')}
                    />
                    <ActionButton
                      color="bg-red-600 hover:bg-red-500"
                      icon={<XCircle className="h-5 w-5" />}
                      label={t('wrong')}
                      sub="0"
                      onClick={() => recordAnswer('wrong')}
                    />
                    <ActionButton
                      color="bg-muted hover:bg-brand-purple/40"
                      icon={<Minus className="h-5 w-5" />}
                      label={t('noAnswer')}
                      sub="-1"
                      onClick={() => recordAnswer('no_answer')}
                    />
                  </div>
                )}

                {actionTab === 'participation' && (
                  <div className="grid grid-cols-2 gap-2">
                    {PARTICIPATION.map(p => (
                      <ActionButton
                        key={p.id}
                        color={`${p.color} hover:opacity-80`}
                        icon={<p.icon className="h-4 w-4" />}
                        label={p.labelKey ? t(p.labelKey) : p.label}
                        sub={participationScores[p.id] ?? p.score}
                        onClick={() => recordParticipation(p)}
                      />
                    ))}
                  </div>
                )}

                {actionTab === 'homework' && (
                  <div className="space-y-2">
                    {homeworkLoading ? (
                      <div className="flex items-center justify-center py-6">
                        <Loader2 className="h-6 w-6 animate-spin text-blue-600 dark:text-blue-400" />
                      </div>
                    ) : <>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-muted-foreground text-xs font-cairo">{t('homeworkMarkNotSubmitted')}</span>
                      <span className="text-blue-600 dark:text-blue-400 text-xs font-bold font-cairo">
                        {Object.values(homeworkStatuses).filter(s => s === 'done').length}/{students.filter(s => s.attendance_status === 'present').length} {t('submitted')}
                      </span>
                    </div>
                    <div className="space-y-1.5 pe-1 max-h-[40vh] overflow-y-auto scrollbar-thin">
                      {students.filter(s => s.attendance_status === 'present').map(student => {
                        const isDone = homeworkStatuses[student.id] !== 'not_done';
                        return (
                          <button
                            key={student.id}
                            onClick={() => toggleHomework(student.id)}
                            className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg transition-colors active:scale-[0.97] ${
                              isDone
                                ? 'bg-green-600/20 border border-green-500/30'
                                : 'bg-foreground/5 border border-border hover:border-border'
                            }`}
                          >
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold shrink-0 ${
                              isDone ? 'bg-green-600 text-foreground' : 'bg-foreground/10 text-muted-foreground'
                            }`}>
                              {isDone ? <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" /> : <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />}
                            </div>
                            <span className={`flex-1 text-start text-sm font-cairo truncate ${
                              isDone ? 'text-foreground' : 'text-muted-foreground line-through'
                            }`}>
                              {student.full_name || t('student')}
                            </span>
                            <span className={`text-xs font-bold font-cairo px-2 py-0.5 rounded-full ${
                              isDone
                                ? 'bg-green-500/20 text-green-600 dark:text-green-400'
                                : 'bg-red-500/20 text-red-600 dark:text-red-400'
                            }`}>
                              {isDone ? t('homeworkDone') : t('homeworkNotDone')}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                    </>}
                  </div>
                )}

                {actionTab === 'recitation' && (
                  <div className="space-y-3">
                    <div>
                      <div className="text-muted-foreground text-[11px] mb-1.5 font-cairo">{t('attempts')}</div>
                      <div className="grid grid-cols-3 gap-1.5">
                        {[1, 2, 3].map(n => (
                          <button
                            key={n}
                            onClick={() => setRecitationAttempts(n)}
                            className={`py-1.5 rounded text-xs font-bold font-cairo transition-colors ${
                              recitationAttempts === n
                                ? 'bg-emerald-600 text-foreground'
                                : 'bg-foreground/10 text-muted-foreground hover:bg-foreground/15'
                            }`}
                          >
                            {n}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <ActionButton
                        color="bg-emerald-600 hover:bg-emerald-500"
                        icon={<CheckCircle2 className="h-5 w-5" />}
                        label={t('recitationMastered')}
                        sub="+3"
                        onClick={() => recordRecitation(true)}
                      />
                      <ActionButton
                        color="bg-red-600 hover:bg-red-500"
                        icon={<XCircle className="h-5 w-5" />}
                        label={t('recitationNotMastered')}
                        sub="0"
                        onClick={() => recordRecitation(false)}
                      />
                    </div>
                    <input
                      className="w-full bg-foreground/10 text-foreground text-xs rounded px-2 py-1.5 placeholder-muted-foreground outline-none font-cairo"
                      placeholder={t('optionalNote')}
                      value={recitationNote}
                      onChange={e => setRecitationNote(e.target.value)}
                    />
                  </div>
                )}

                {actionTab === 'behaviour' && (
                  <div className="space-y-2">
                    <div className="flex gap-1 mb-2">
                      {[
                        { id: 'positive', labelKey: 'positive', icon: ThumbsUp, color: 'bg-green-600' },
                        { id: 'negative', labelKey: 'negative', icon: AlertTriangle, color: 'bg-red-600' },
                      ].map(cat => (
                        <button
                          key={cat.id}
                          onClick={() => setBehaviourCategory(cat.id)}
                          className={`flex-1 py-1.5 rounded text-xs font-medium text-foreground transition-colors ${
                            behaviourCategory === cat.id ? cat.color : 'bg-foreground/10 text-muted-foreground'
                          }`}
                        >
                          <span className="flex items-center justify-center gap-1"><cat.icon className="h-3 w-3" />{t(cat.labelKey)}</span>
                        </button>
                      ))}
                    </div>
                    <div className="grid grid-cols-3 gap-1.5">
                      {[
                        ...(BEHAVIOURS[behaviourCategory] || []),
                        ...(behaviourCategory === 'positive' ? customPositiveBehaviours : customNegativeBehaviours).map(b => {
                          // Support both legacy string and new {id, name, points} shape.
                          // The displayed sign is always derived from the category list
                          // the item lives in (ignoring any stale stored sign), so the
                          // teacher sees a consistent +/- regardless of how the item was
                          // originally saved.
                          if (typeof b === 'string') {
                            return {
                              id: `custom_${b}`,
                              label: b,
                              points: behaviourCategory === 'positive' ? '+2' : '-2'
                            };
                          }
                          const abs = Math.abs(Number(b.points) || 0);
                          return {
                            id: b.id || `custom_${b.name}`,
                            label: b.name,
                            points: behaviourCategory === 'positive' ? `+${abs}` : `-${abs}`
                          };
                        })
                      ].map(b => (
                        <button
                          key={b.id}
                          onClick={() => recordBehaviour(b)}
                          className="bg-foreground/10 hover:bg-foreground/20 text-foreground rounded-lg py-2 px-1 text-xs text-center transition-colors"
                        >
                          <div className="font-medium truncate">{b.labelKey ? t(b.labelKey) : b.label}</div>
                          <div className={`text-[10px] mt-0.5 ${b.points.startsWith('-') ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>{b.points}</div>
                        </button>
                      ))}
                    </div>
                    <input
                      className="w-full bg-foreground/10 text-foreground text-xs rounded px-2 py-1.5 placeholder-muted-foreground outline-none"
                      placeholder={t('optionalNote')}
                      aria-label={t('optionalNote')}
                      value={behaviourNote}
                      onChange={e => setBehaviourNote(e.target.value)}
                    />
                  </div>
                )}

                {actionTab === 'skill' && (
                  <div className="space-y-2">
                    <div className="grid grid-cols-3 gap-1.5">
                      {[
                        // Registered skill types carry an explicit isCustom flag
                        // so the record action never re-derives "custom" from an
                        // id prefix. Their configured `points` (if any) passes
                        // through untouched; skills without one show/award the
                        // global special_skill default.
                        ...skillTypes.map(s => ({ ...s, isCustom: false })),
                        // Custom skills may be plain strings (legacy) or
                        // `{name, points}` objects since the settings UI
                        // now lets teachers configure a magnitude.
                        ...customSkills.map(s => {
                          if (typeof s === 'string') {
                            return { id: `custom_${s}`, name: s, name_ar: s, points: null, isCustom: true };
                          }
                          const name = s?.name ?? '';
                          const rawPts = Number(s?.points);
                          const points = Number.isFinite(rawPts) ? Math.abs(rawPts) : null;
                          const rawId = s?.id || `custom_${name}`;
                          const id = rawId.startsWith('custom_') ? rawId : `custom_${rawId}`;
                          return { id, name, name_ar: name, points, isCustom: true };
                        })
                      ].map(skill => {
                        const pts = Number(skill.points);
                        const display = Number.isFinite(pts) ? Math.abs(pts) : 3;
                        return (
                          <button
                            key={skill.id}
                            onClick={() => recordSkill(skill)}
                            className="bg-purple-500/10 dark:bg-purple-900/40 hover:bg-purple-800/60 text-foreground rounded-lg py-2 px-1 text-xs text-center transition-colors border border-purple-500/20"
                          >
                            <div className="font-medium truncate">{skill.name_ar || skill.name}</div>
                            <div className="text-[10px] mt-0.5 text-purple-700 dark:text-purple-300">+{display}</div>
                          </button>
                        );
                      })}
                    </div>
                    {skillTypes.length === 0 && customSkills.length === 0 && (
                      <p className="text-muted-foreground text-xs text-center py-2">{t('noSkillsRegistered')}</p>
                    )}
                    <input
                      className="w-full bg-foreground/10 text-foreground text-xs rounded px-2 py-1.5 placeholder-muted-foreground outline-none"
                      placeholder={t('optionalNote')}
                      aria-label={t('optionalNote')}
                      value={skillNote}
                      onChange={e => setSkillNote(e.target.value)}
                    />
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* ── Right Action Sidebar (redesign) ── */}
        <aside className="flex-none w-[78px] sm:w-[92px] border-e border-border bg-background/60 backdrop-blur-sm flex flex-col overflow-y-auto py-2 px-1.5 gap-3">
          {(() => {
            const guard = (fn) => () => {
              if (!selectedStudent) { toast.error(t('selectStudentFirst') || 'اختر طالباً أولاً'); return; }
              fn();
            };
            // Open one popover at a time. Re-clicking same button toggles it closed.
            const togglePopover = (key) => {
              if (!selectedStudent) { toast.error(t('selectStudentFirst') || 'اختر طالباً أولاً'); return; }
              if (key === 'positive' || key === 'negative') setBehaviourCategory(key);
              setOpenPopover(prev => prev === key ? null : key);
            };
            const SideBtn = ({ onClick, color, icon: Icon, label, disabled }) => (
              <button
                onClick={onClick}
                disabled={disabled}
                className={`w-full flex flex-col items-center gap-1 py-2 rounded-lg border ${color} text-foreground transition-all active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed`}
              >
                <Icon className="h-4 w-4" />
                <span className="text-[10px] font-cairo font-bold leading-tight text-center">{label}</span>
              </button>
            );
            // Trigger button that also forwards a ref so the popover can anchor to it.
            const TriggerBtn = ({ refEl, onClick, color, icon: Icon, label, isOpen, disabled }) => (
              <button
                ref={refEl}
                onClick={onClick}
                disabled={disabled}
                aria-haspopup="dialog"
                aria-expanded={isOpen}
                className={`w-full flex flex-col items-center gap-1 py-2 rounded-lg border ${color} text-foreground transition-all active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed ${isOpen ? 'ring-2 ring-amber-400/70 shadow-[0_0_0_2px_rgba(245,158,11,0.18)]' : ''}`}
              >
                <Icon className="h-4 w-4" />
                <span className="text-[10px] font-cairo font-bold leading-tight text-center">{label}</span>
              </button>
            );
            return (
              <>
                {/* التقييم */}
                <div className="space-y-1.5">
                  <div className="text-[9px] uppercase tracking-wider text-muted-foreground text-center font-bold">{t('evaluation') || 'التقييم'}</div>
                  <SideBtn onClick={guard(() => recordAnswer('correct'))} color="bg-emerald-500/15 border-emerald-400/40 hover:bg-emerald-500/25" icon={CheckCircle2} label={t('correct')} />
                  <SideBtn onClick={guard(() => recordAnswer('wrong'))} color="bg-rose-500/15 border-rose-400/40 hover:bg-rose-500/25" icon={XCircle} label={t('wrong')} />
                  <SideBtn onClick={guard(() => recordAnswer('no_answer'))} color="bg-amber-500/15 border-amber-400/40 hover:bg-amber-500/25" icon={Minus} label={t('noAnswer') || 'لم'} />
                  {recitationEnabled && (
                    <TriggerBtn
                      refEl={recitationPopRef}
                      onClick={() => togglePopover('recitation')}
                      isOpen={openPopover === 'recitation'}
                      color="bg-purple-500/15 border-purple-400/40 hover:bg-purple-500/25"
                      icon={Mic}
                      label={t('recitation')}
                    />
                  )}
                  {/* Teacher-defined evaluation items added via the
                      sidebar settings dialog. Re-renders automatically
                      whenever `customEvaluationItems` changes, so newly
                      added items appear immediately without a reload. */}
                  {customEvaluationItems
                    .filter(item => !DEFAULT_EVAL_IDS.has(item.id))
                    .map(item => {
                      const Icon = SIDEBAR_EVAL_ICONS[item.icon] || CheckCircle2;
                      const color = SIDEBAR_EVAL_COLORS[item.color] || SIDEBAR_EVAL_COLORS.gray;
                      return (
                        <SideBtn
                          key={item.id}
                          onClick={guard(() => recordCustomEvaluation(item))}
                          color={color}
                          icon={Icon}
                          label={item.name}
                        />
                      );
                    })}
                </div>
                {/* السلوك */}
                <div className="space-y-1.5">
                  <div className="text-[9px] uppercase tracking-wider text-muted-foreground text-center font-bold">{t('behaviour') || 'السلوك'}</div>
                  <TriggerBtn
                    refEl={positivePopRef}
                    onClick={() => togglePopover('positive')}
                    isOpen={openPopover === 'positive'}
                    color="bg-emerald-500/15 border-emerald-400/40 hover:bg-emerald-500/25"
                    icon={ThumbsUp}
                    label={t('positive')}
                  />
                  <TriggerBtn
                    refEl={negativePopRef}
                    onClick={() => togglePopover('negative')}
                    isOpen={openPopover === 'negative'}
                    color="bg-rose-500/15 border-rose-400/40 hover:bg-rose-500/25"
                    icon={ThumbsDown}
                    label={t('negative')}
                  />
                </div>
                {/* المهارات */}
                {skillEnabled && (
                  <div className="space-y-1.5">
                    <div className="text-[9px] uppercase tracking-wider text-muted-foreground text-center font-bold">{t('skills') || 'المهارات'}</div>
                    <TriggerBtn
                      refEl={skillPopRef}
                      onClick={() => togglePopover('skill')}
                      isOpen={openPopover === 'skill'}
                      color="bg-violet-500/15 border-violet-400/40 hover:bg-violet-500/25"
                      icon={Star}
                      label={t('skill')}
                    />
                  </div>
                )}
              </>
            );
          })()}

          {/* ── Contextual evaluation popovers — anchored to the sidebar triggers above ── */}
          {/* Positive behaviour popover */}
          <EvalPopover
            open={openPopover === 'positive' && !!selectedStudent}
            onClose={() => setOpenPopover(null)}
            anchorRef={positivePopRef}
            title={`${t('positive') || 'إيجابي'} — ${selectedStudent?.full_name || ''}`}
            width={300}
          >
            <div className="grid grid-cols-2 gap-1.5">
              {[
                ...(BEHAVIOURS.positive || []),
                ...customPositiveBehaviours.map(b => {
                  if (typeof b === 'string') return { id: `custom_${b}`, label: b, points: '+2' };
                  const abs = Math.abs(Number(b.points) || 0);
                  return { id: b.id || `custom_${b.name}`, label: b.name, points: `+${abs}` };
                })
              ].map(b => (
                <button
                  key={b.id}
                  onClick={async () => { setBehaviourCategory('positive'); await recordBehaviour(b); setOpenPopover(null); }}
                  className="bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-400/30 hover:border-emerald-400/60 text-foreground rounded-lg py-2 px-2 text-xs text-center transition-colors"
                >
                  <div className="font-medium font-cairo truncate">{b.labelKey ? t(b.labelKey) : b.label}</div>
                  <div className="text-[10px] mt-0.5 text-emerald-700 dark:text-emerald-300 font-bold">{b.points}</div>
                </button>
              ))}
            </div>
            <input
              className="mt-2 w-full bg-foreground/10 text-foreground text-xs rounded px-2 py-1.5 placeholder-muted-foreground outline-none focus:ring-2 focus:ring-emerald-400/40 font-cairo"
              placeholder={t('optionalNote') || 'ملاحظة اختيارية'}
              aria-label={t('optionalNote') || 'ملاحظة اختيارية'}
              value={behaviourNote}
              onChange={e => setBehaviourNote(e.target.value)}
            />
          </EvalPopover>

          {/* Negative behaviour popover */}
          <EvalPopover
            open={openPopover === 'negative' && !!selectedStudent}
            onClose={() => setOpenPopover(null)}
            anchorRef={negativePopRef}
            title={`${t('negative') || 'سلبي'} — ${selectedStudent?.full_name || ''}`}
            width={300}
          >
            <div className="grid grid-cols-2 gap-1.5">
              {[
                ...(BEHAVIOURS.negative || []),
                ...customNegativeBehaviours.map(b => {
                  if (typeof b === 'string') return { id: `custom_${b}`, label: b, points: '-2' };
                  const abs = Math.abs(Number(b.points) || 0);
                  return { id: b.id || `custom_${b.name}`, label: b.name, points: `-${abs}` };
                })
              ].map(b => (
                <button
                  key={b.id}
                  onClick={async () => { setBehaviourCategory('negative'); await recordBehaviour(b); setOpenPopover(null); }}
                  className="bg-rose-500/10 hover:bg-rose-500/20 border border-rose-400/30 hover:border-rose-400/60 text-foreground rounded-lg py-2 px-2 text-xs text-center transition-colors"
                >
                  <div className="font-medium font-cairo truncate">{b.labelKey ? t(b.labelKey) : b.label}</div>
                  <div className="text-[10px] mt-0.5 text-rose-700 dark:text-rose-300 font-bold">{b.points}</div>
                </button>
              ))}
            </div>
            <input
              className="mt-2 w-full bg-foreground/10 text-foreground text-xs rounded px-2 py-1.5 placeholder-muted-foreground outline-none focus:ring-2 focus:ring-rose-400/40 font-cairo"
              placeholder={t('optionalNote') || 'ملاحظة اختيارية'}
              aria-label={t('optionalNote') || 'ملاحظة اختيارية'}
              value={behaviourNote}
              onChange={e => setBehaviourNote(e.target.value)}
            />
          </EvalPopover>

          {/* Skills popover */}
          <EvalPopover
            open={openPopover === 'skill' && !!selectedStudent}
            onClose={() => setOpenPopover(null)}
            anchorRef={skillPopRef}
            title={`${t('skill') || 'مهارة'} — ${selectedStudent?.full_name || ''}`}
            width={300}
          >
            {(skillTypes.length === 0 && customSkills.length === 0) ? (
              <p className="text-muted-foreground text-xs text-center py-3 font-cairo">{t('noSkillsRegistered') || 'لا توجد مهارات مسجلة'}</p>
            ) : (
              <div className="grid grid-cols-2 gap-1.5">
                {[
                  // Registered skill types carry an explicit isCustom flag so
                  // the record action never re-derives "custom" from an id
                  // prefix; their configured `points` (if any) pass through.
                  ...skillTypes.map(s => ({ ...s, isCustom: false })),
                  ...customSkills.map(s => {
                    if (typeof s === 'string') {
                      return { id: `custom_${s}`, name: s, name_ar: s, points: null, isCustom: true };
                    }
                    const name = s?.name ?? '';
                    const rawPts = Number(s?.points);
                    const points = Number.isFinite(rawPts) ? Math.abs(rawPts) : null;
                    const rawId = s?.id || `custom_${name}`;
                    const id = rawId.startsWith('custom_') ? rawId : `custom_${rawId}`;
                    return { id, name, name_ar: name, points, isCustom: true };
                  })
                ].map(skill => {
                  const pts = Number(skill.points);
                  const display = Number.isFinite(pts) ? Math.abs(pts) : 3;
                  return (
                    <button
                      key={skill.id}
                      onClick={async () => { await recordSkill(skill); setOpenPopover(null); }}
                      className="bg-violet-500/10 hover:bg-violet-500/20 border border-violet-400/30 hover:border-violet-400/60 text-foreground rounded-lg py-2 px-2 text-xs text-center transition-colors"
                    >
                      <div className="font-medium font-cairo truncate">{skill.name_ar || skill.name}</div>
                      <div className="text-[10px] mt-0.5 text-violet-700 dark:text-violet-300 font-bold">+{display}</div>
                    </button>
                  );
                })}
              </div>
            )}
            <input
              className="mt-2 w-full bg-foreground/10 text-foreground text-xs rounded px-2 py-1.5 placeholder-muted-foreground outline-none focus:ring-2 focus:ring-violet-400/40 font-cairo"
              placeholder={t('optionalNote') || 'ملاحظة اختيارية'}
              aria-label={t('optionalNote') || 'ملاحظة اختيارية'}
              value={skillNote}
              onChange={e => setSkillNote(e.target.value)}
            />
          </EvalPopover>

          {/* Recitation popover */}
          <EvalPopover
            open={openPopover === 'recitation' && !!selectedStudent}
            onClose={() => setOpenPopover(null)}
            anchorRef={recitationPopRef}
            title={`${t('recitation') || 'التسميع'} — ${selectedStudent?.full_name || ''}`}
            width={300}
          >
            <div className="space-y-3">
              <div>
                <div className="text-muted-foreground text-[11px] mb-1.5 font-cairo">{t('attempts') || 'المحاولات'}</div>
                <div className="grid grid-cols-3 gap-1.5">
                  {[1, 2, 3].map(n => (
                    <button
                      key={n}
                      onClick={() => setRecitationAttempts(n)}
                      className={`py-1.5 rounded text-xs font-bold font-cairo transition-colors ${
                        recitationAttempts === n
                          ? 'bg-emerald-600 text-white'
                          : 'bg-foreground/10 text-muted-foreground hover:bg-foreground/15'
                      }`}
                    >
                      {n}
                    </button>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={async () => { await recordRecitation(true); setOpenPopover(null); }}
                  className="flex items-center justify-center gap-1.5 py-2 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-400/40 text-foreground text-xs font-cairo font-bold transition-colors"
                >
                  <CheckCircle2 className="h-4 w-4" />
                  <span>{t('recitationMastered') || 'متقن'}</span>
                </button>
                <button
                  onClick={async () => { await recordRecitation(false); setOpenPopover(null); }}
                  className="flex items-center justify-center gap-1.5 py-2 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 border border-rose-400/40 text-foreground text-xs font-cairo font-bold transition-colors"
                >
                  <XCircle className="h-4 w-4" />
                  <span>{t('recitationNotMastered') || 'لم يتقن'}</span>
                </button>
              </div>
              <input
                className="w-full bg-foreground/10 text-foreground text-xs rounded px-2 py-1.5 placeholder-muted-foreground outline-none focus:ring-2 focus:ring-purple-400/40 font-cairo"
                placeholder={t('optionalNote') || 'ملاحظة اختيارية'}
                aria-label={t('optionalNote') || 'ملاحظة اختيارية'}
                value={recitationNote}
                onChange={e => setRecitationNote(e.target.value)}
              />
            </div>
          </EvalPopover>

        </aside>

        {/* ── Right Panel (Activity Log + Notes, desktop only, collapsible) ── */}
        {panelOpen && (
        <div
          className="hidden lg:flex flex-col w-72 shrink-0 border-s border-border bg-background/50 backdrop-blur-sm overflow-hidden"
        >
          <div className="flex border-b border-border bg-foreground/[0.02]">
            {[
              { id: 'log', labelKey: 'activityLog', icon: Activity },
              { id: 'notes', labelKey: 'notes', icon: StickyNote },
              { id: 'metrics', labelKey: 'metrics', icon: BarChart2 },
            ].map(tab => {
              const active = rightPanel === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setRightPanel(tab.id)}
                  aria-pressed={active}
                  className={`relative flex-1 flex items-center justify-center gap-1.5 py-3 text-[10px] uppercase tracking-[0.14em] font-bold transition-colors focus-visible:outline-none focus-visible:bg-foreground/5 ${
                    active ? 'text-amber-700 dark:text-amber-300' : 'text-muted-foreground hover:text-muted-foreground'
                  }`}
                >
                  <tab.icon className="h-3.5 w-3.5" />
                  {t(tab.labelKey)}
                  {tab.id === 'notes' && notes.length > 0 && (
                    <span className="bg-amber-500 text-foreground text-[9px] rounded-full w-4 h-4 flex items-center justify-center font-bold tabular-nums">{notes.length}</span>
                  )}
                  {active && <span className="absolute inset-x-3 -bottom-px h-[2px] bg-gradient-to-r from-transparent via-amber-400 to-transparent" aria-hidden="true" />}
                </button>
              );
            })}
          </div>

          {rightPanel === 'log' && (
            <>
              <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
                {activityLog.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center px-4 gap-2">
                    <Activity className="h-8 w-8 text-muted-foreground/40" aria-hidden="true" />
                    <p className="text-muted-foreground text-xs font-medium">{t('noActivityYet')}</p>
                    <p className="text-muted-foreground/60 text-[10px] leading-relaxed">{t('noActivityHint')}</p>
                  </div>
                ) : (
                  activityLog.map(log => (
                    <div key={log.id} className={`rounded-lg px-2.5 py-2 ${log.reversed ? 'bg-muted/40 opacity-60' : 'bg-foreground/5'}`}>
                      <p className={`text-xs font-medium ${log.reversed ? 'text-muted-foreground' : log.color} flex items-center gap-1`}>
                        {(() => {
                          const IconComp = LOG_ICONS[log.emoji];
                          return IconComp ? <IconComp className="h-3 w-3 inline-block flex-shrink-0" aria-hidden="true" /> : <span>{log.emoji}</span>;
                        })()}
                        <span className={log.reversed ? 'line-through' : ''}>{log.text}</span>
                        {log.reversed && (
                          <span className="ms-1 inline-flex items-center rounded-full bg-muted border border-border px-1.5 py-0.5 text-[9px] font-semibold text-muted-foreground leading-none flex-shrink-0">
                            ↩ تم التراجع
                          </span>
                        )}
                      </p>
                      <p className="text-muted-foreground/70 text-[10px] mt-0.5">{log.time}</p>
                    </div>
                  ))
                )}
              </div>
              <div className="border-t border-border p-3 grid grid-cols-2 gap-2 bg-foreground/[0.015]">
                <div className="bg-foreground/[0.025] border border-border rounded-lg px-2.5 py-2">
                  <div className="text-foreground text-lg font-extrabold leading-none tabular-nums">{stats.questions}</div>
                  <div className="text-muted-foreground text-[9px] uppercase tracking-[0.14em] mt-1.5 font-semibold">{t('questions')}</div>
                </div>
                <div className="bg-foreground/[0.025] border border-border rounded-lg px-2.5 py-2">
                  <div className="text-emerald-700 dark:text-emerald-300 text-lg font-extrabold leading-none tabular-nums">{stats.correct}</div>
                  <div className="text-muted-foreground text-[9px] uppercase tracking-[0.14em] mt-1.5 font-semibold">{t('correct')}</div>
                </div>
                <div className="bg-foreground/[0.025] border border-border rounded-lg px-2.5 py-2">
                  <div className={`text-lg font-extrabold leading-none tabular-nums ${accuracy >= 60 ? 'text-emerald-700 dark:text-emerald-300' : 'text-rose-700 dark:text-rose-300'}`}>{accuracy}%</div>
                  <div className="text-muted-foreground text-[9px] uppercase tracking-[0.14em] mt-1.5 font-semibold">{t('accuracy')}</div>
                </div>
                <div className="bg-foreground/[0.025] border border-border rounded-lg px-2.5 py-2">
                  <div className="text-sky-700 dark:text-sky-300 text-lg font-extrabold leading-none tabular-nums">{stats.participation}</div>
                  <div className="text-muted-foreground text-[9px] uppercase tracking-[0.14em] mt-1.5 font-semibold">{t('interaction')}</div>
                </div>
              </div>
            </>
          )}

          {rightPanel === 'notes' && (
            <>
              <div className="flex-1 overflow-y-auto p-2 space-y-2">
                {notes.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center px-4 gap-2">
                    <StickyNote className="h-8 w-8 text-muted-foreground/40" aria-hidden="true" />
                    <p className="text-muted-foreground text-xs font-medium">{t('noNotesYet')}</p>
                    <p className="text-muted-foreground/60 text-[10px] leading-relaxed">{t('noNotesHint')}</p>
                  </div>
                ) : (
                  notes.map(note => (
                    <div key={note.id} className="bg-amber-500/10 dark:bg-amber-900/20 border border-amber-500/20 rounded-lg px-3 py-2">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-foreground text-xs leading-relaxed flex-1">{note.text}</p>
                        <button onClick={() => deleteNote(note.id)} className="text-muted-foreground/70 hover:text-red-600 dark:text-red-400 flex-shrink-0">
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                      <div className="flex items-center gap-2 mt-1.5">
                        <Badge className="bg-amber-500/20 text-amber-700 dark:text-amber-300 text-[9px] px-1.5 py-0">
                          {note.note_type === 'student' ? t('studentNoteShort')
                            : note.note_type === 'behavioural' ? t('behaviouralNoteShort')
                            : note.note_type === 'educational' ? t('educationalNoteShort')
                            : note.note_type === 'followup' ? t('followupNoteShort')
                            : t('general')}
                        </Badge>
                        {note.student_name && (
                          <span className="text-muted-foreground text-[10px]">{note.student_name}</span>
                        )}
                        <span className="text-muted-foreground/70 text-[10px] ms-auto">
                          {new Date(note.created_at).toLocaleTimeString(isRTL ? 'ar' : 'en', { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
              <div className="border-t border-border p-2 space-y-2">
                <div className="flex gap-1">
                  {[
                    { id: 'session', labelKey: 'general' },
                    { id: 'student', labelKey: 'student' },
                    { id: 'behavioural', labelKey: 'behaviour' },
                    { id: 'followup', labelKey: 'followUp' },
                  ].map(nt => (
                    <button
                      key={nt.id}
                      onClick={() => setNoteType(nt.id)}
                      className={`flex-1 py-1 rounded text-[10px] font-medium transition-colors ${
                        noteType === nt.id ? 'bg-amber-600 text-foreground' : 'bg-foreground/10 text-muted-foreground'
                      }`}
                    >
                      {t(nt.labelKey)}
                    </button>
                  ))}
                </div>
                {selectedStudent && noteType === 'student' && (
                  <div className="bg-foreground/5 rounded px-2 py-1 text-[10px] text-brand-turquoise flex items-center gap-1">
                    <UserCheck className="h-3 w-3" />
                    {selectedStudent.full_name}
                  </div>
                )}
                <div className="flex gap-1.5">
                  <input
                    className="flex-1 bg-foreground/10 text-foreground text-xs rounded px-2 py-1.5 placeholder-muted-foreground outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
                    placeholder={t('writeNoteShort')}
                    aria-label={t('writeNoteShort')}
                    value={newNote}
                    onChange={e => setNewNote(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && addNote()}
                  />
                  <button
                    onClick={addNote}
                    disabled={!newNote.trim()}
                    aria-label={t('add')}
                    className="bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-foreground rounded px-2 py-1.5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
                  >
                    <Plus className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </>
          )}

          {rightPanel === 'metrics' && (
            <div className="flex-1 overflow-y-auto p-3 space-y-3">
              {liveMetrics ? (
                <>
                  <div className="bg-foreground/5 rounded-lg p-3 space-y-2">
                    <h4 className="text-muted-foreground text-[10px] font-medium uppercase tracking-wider">{t('attendanceShort')}</h4>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="text-center">
                        <div className="text-green-600 dark:text-green-400 text-lg font-bold">{liveMetrics.attendance?.present || 0}</div>
                        <div className="text-muted-foreground text-[10px]">{t('present')}</div>
                      </div>
                      <div className="text-center">
                        <div className="text-red-600 dark:text-red-400 text-lg font-bold">{liveMetrics.attendance?.absent || 0}</div>
                        <div className="text-muted-foreground text-[10px]">{t('absent')}</div>
                      </div>
                    </div>
                    <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                      <div className="h-full bg-green-500 transition-colors" style={{ width: `${liveMetrics.attendance?.rate || 0}%` }} />
                    </div>
                    <div className="text-center text-muted-foreground text-[10px]">{liveMetrics.attendance?.rate || 0}% {t('present')}</div>
                  </div>

                  <div className="bg-foreground/5 rounded-lg p-3 space-y-2">
                    <h4 className="text-muted-foreground text-[10px] font-medium uppercase tracking-wider">{t('interaction')}</h4>
                    <div className="grid grid-cols-3 gap-2 text-center">
                      <div>
                        <div className="text-blue-600 dark:text-blue-400 text-lg font-bold">{liveMetrics.interaction?.total_questions || 0}</div>
                        <div className="text-muted-foreground text-[10px]">{t('questions')}</div>
                      </div>
                      <div>
                        <div className="text-green-600 dark:text-green-400 text-lg font-bold">{liveMetrics.interaction?.correct_answers || 0}</div>
                        <div className="text-muted-foreground text-[10px]">{t('correct')}</div>
                      </div>
                      <div>
                        <div className="text-red-600 dark:text-red-400 text-lg font-bold">{liveMetrics.interaction?.wrong_answers || 0}</div>
                        <div className="text-muted-foreground text-[10px]">{t('error')}</div>
                      </div>
                    </div>
                    <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                      <div className="h-full bg-blue-500 transition-colors" style={{ width: `${liveMetrics.interaction?.accuracy_rate || 0}%` }} />
                    </div>
                    <div className="text-center text-muted-foreground text-[10px]">{liveMetrics.interaction?.accuracy_rate || 0}% {t('accuracy')}</div>
                  </div>

                  <div className="bg-foreground/5 rounded-lg p-3 space-y-2">
                    <h4 className="text-muted-foreground text-[10px] font-medium uppercase tracking-wider">{t('participationLabel')}</h4>
                    <div className="grid grid-cols-2 gap-2 text-center">
                      <div>
                        <div className="text-purple-600 dark:text-purple-400 text-lg font-bold">{liveMetrics.interaction?.unique_participants || 0}</div>
                        <div className="text-muted-foreground text-[10px]">{t('participant')}</div>
                      </div>
                      <div>
                        <div className="text-amber-600 dark:text-amber-400 text-lg font-bold">{liveMetrics.interaction?.not_interacted || 0}</div>
                        <div className="text-muted-foreground text-[10px]">{t('notInteracted')}</div>
                      </div>
                    </div>
                    <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                      <div className="h-full bg-purple-500 transition-colors" style={{ width: `${liveMetrics.interaction?.participation_rate || 0}%` }} />
                    </div>
                  </div>

                  <div className="bg-foreground/5 rounded-lg p-3 space-y-2">
                    <h4 className="text-muted-foreground text-[10px] font-medium uppercase tracking-wider">{t('behaviourAndSkillsHeading')}</h4>
                    <div className="grid grid-cols-3 gap-2 text-center">
                      <div>
                        <div className="text-green-600 dark:text-green-400 text-base font-bold">{liveMetrics.behaviour?.positive || 0}</div>
                        <div className="text-muted-foreground text-[10px]">{t('positive')}</div>
                      </div>
                      <div>
                        <div className="text-red-600 dark:text-red-400 text-base font-bold">{liveMetrics.behaviour?.negative || 0}</div>
                        <div className="text-muted-foreground text-[10px]">{t('negative')}</div>
                      </div>
                      <div>
                        <div className="text-purple-600 dark:text-purple-400 text-base font-bold">{liveMetrics.skills_recorded || 0}</div>
                        <div className="text-muted-foreground text-[10px]">{t('skillsShort')}</div>
                      </div>
                    </div>
                  </div>

                  <div className="text-center text-muted-foreground/70 text-[10px] mt-2">
                    <Clock className="h-3 w-3 inline-block" /> {liveMetrics.duration_minutes || 0} {t('minutes')} | <StickyNote className="h-3 w-3 inline-block" /> {liveMetrics.notes_count || 0} {t('notes')}
                  </div>
                </>
              ) : (
                <div className="flex items-center justify-center h-full">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground/70" />
                </div>
              )}
            </div>
          )}
        </div>
        )}
      </div>

      {/* Bottom bar — distributed: 2 primary buttons start (RTL right), 2 secondary/destructive end (RTL left) */}
      <div className="flex-none shrink-0 bg-background/90 backdrop-blur-md border-t border-border px-3 sm:px-4 py-2.5 flex items-center justify-between w-full gap-2 sm:gap-3 relative z-10 flex-wrap">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-amber-500/30 to-transparent" aria-hidden="true" />

        {/* Right group (RTL start): Save Class + Follow-up Record.
            The duplicate refresh icon that used to sit here was
            removed; the toolbar button at the top of the page is now
            the single source of refresh. */}
        <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
          <Button
            onClick={async () => {
              setSavingSession(true);
              try {
                // Persist pending grade edits through the serialized flush
                // (silent: the catch below surfaces a single error dialog), then
                // commit. If the grade save fails it throws here, so commit-scores
                // is skipped and the report can't show points never persisted.
                await flushFollowupRecord({ silent: true });
                // Commit the session's accumulated live scores into the
                // persistent student-record layer (school + parent profiles).
                // Idempotent on the backend — safe to repeat. A failure here
                // MUST surface (not be swallowed): otherwise the report shows
                // points the student/parent profiles never received.
                await api.post(`/session/${sessionId}/commit-scores`);
                toast.success(t('savedSuccessfully') || 'تم الحفظ');
              } catch (e) {
                nassaqError(getApiErrorMessage(e) || t('errorSaving') || 'تعذّر حفظ درجات الحصة');
              } finally {
                setSavingSession(false);
              }
            }}
            disabled={savingSession}
            className="h-10 px-5 bg-gradient-to-b from-emerald-500 to-emerald-600 hover:from-emerald-400 hover:to-emerald-500 text-white font-cairo font-bold border border-emerald-400/40 shadow-[0_4px_12px_-2px_rgba(16,185,129,0.4)] gap-2"
          >
            {savingSession ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            {t('saveSession') || 'حفظ الحصة'}
          </Button>
          <Button
            onClick={() => setShowFollowupRecord(true)}
            className="h-10 px-5 bg-gradient-to-b from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-white font-cairo font-bold border border-sky-400/40 shadow-[0_4px_12px_-2px_rgba(59,130,246,0.4)] gap-2"
          >
            <FileText className="h-4 w-4" />
            {t('followupRecord')}
          </Button>
        </div>

        {/* Left group (RTL end): Sidebar Settings + End Class + autosave indicator */}
        <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
          <Button
            onClick={() => setShowSidebarSettings(true)}
            className="h-10 px-4 bg-gradient-to-b from-slate-500 to-slate-600 hover:from-slate-400 hover:to-slate-500 text-white font-cairo font-bold border border-slate-400/40 shadow-[0_4px_12px_-2px_rgba(100,116,139,0.35)] gap-2"
            title={t('sessionSettings')}
          >
            <Settings className="h-4 w-4" />
            <span className="hidden sm:inline">{t('sessionSettings')}</span>
          </Button>
          <Button
            onClick={() => setShowEndDialog(true)}
            disabled={reviewLoading}
            className="h-10 px-4 bg-gradient-to-b from-rose-500 to-rose-600 hover:from-rose-400 hover:to-rose-500 text-white font-cairo font-bold border border-rose-400/40 shadow-[0_4px_12px_-2px_rgba(244,63,94,0.4)] gap-2 disabled:opacity-60"
            title={t('endSession')}
          >
            {reviewLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <X className="h-4 w-4" />}
            <span className="hidden sm:inline">{t('endSession')}</span>
          </Button>
          <span className="hidden md:flex items-center gap-1.5 text-[10px] uppercase tracking-[0.14em] font-semibold text-emerald-700 dark:text-emerald-300/80" role="status">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inset-0 rounded-full bg-emerald-400 animate-ping opacity-60" />
              <span className="relative rounded-full h-1.5 w-1.5 bg-emerald-400" />
            </span>
            {t('autoSaveActive')}
          </span>
        </div>
      </div>

      {/* End Session Confirmation Dialog */}
      <Dialog open={showEndDialog} onOpenChange={setShowEndDialog}>
        <DialogContent className="max-w-sm" dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader>
            <DialogTitle className="font-cairo text-center">{t('endSession')}</DialogTitle>
          </DialogHeader>
          <p className="text-center text-muted-foreground text-sm py-2">
            {t('endSessionConfirmDesc')}
          </p>
          {(() => {
            const ops = checkPendingOps();
            return ops.length > 0 ? (
              <div className="space-y-2 mb-3">
                {ops.map(op => (
                  <div key={op.id} className={`flex items-center gap-2 text-xs rounded-lg px-3 py-2 ${
                    op.severity === 'error' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300 border border-red-200' : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300 border border-amber-200'
                  }`}>
                    <AlertTriangle className="h-3.5 w-3.5 flex-none" />
                    {op.label}
                  </div>
                ))}
              </div>
            ) : null;
          })()}
          <div className="flex gap-2">
            <Button variant="outline" className="flex-1" onClick={() => setShowEndDialog(false)}>{t('cancel')}</Button>
            <Button
              className="flex-1 bg-red-600 hover:bg-red-700"
              onClick={startEndReview}
              disabled={reviewLoading}
            >
              {reviewLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : t('reviewAndEnd')}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Group Management Modal */}
      <Dialog open={showGroupModal} onOpenChange={setShowGroupModal}>
        <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto" dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader>
            <DialogTitle className="font-cairo flex items-center gap-2">
              <UsersRound className="h-5 w-5 text-purple-500" />
              {t('manageGroups')}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <button
              onClick={() => autoGroupByLevel()}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-purple-600/20 text-purple-600 dark:text-purple-400 text-sm font-medium hover:bg-purple-600/30 transition-colors border border-purple-500/30"
            >
              <Zap className="h-4 w-4" />
              {t('autoGroupByLevel')}
            </button>

            {groups.map((group, gi) => (
              <div
                key={group.id}
                className={`bg-muted dark:bg-card rounded-xl p-3 space-y-2 ${dragStudent ? 'border-2 border-dashed border-transparent hover:border-brand-turquoise' : ''}`}
                onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add('border-brand-turquoise'); }}
                onDragLeave={e => e.currentTarget.classList.remove('border-brand-turquoise')}
                onDrop={e => { e.preventDefault(); e.currentTarget.classList.remove('border-brand-turquoise'); handleDropOnGroup(gi); }}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`w-3 h-3 rounded-full ${group.color}`} />
                    <input
                      value={group.name}
                      onChange={e => {
                        const updated = [...groups];
                        updated[gi] = { ...updated[gi], name: e.target.value };
                        setGroups(updated);
                      }}
                      className="bg-transparent text-sm font-cairo font-bold outline-none border-b border-transparent focus:border-brand-turquoise w-32"
                    />
                    <span className="text-xs text-muted-foreground">({group.students?.length || 0})</span>
                  </div>
                  <button
                    onClick={() => setGroups(groups.filter((_, i) => i !== gi))}
                    className="p-1 text-red-600 dark:text-red-400 hover:text-red-500"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {(group.students || []).map(sid => {
                    const st = presentStudents.find(s => s.id === sid);
                    if (!st) return null;
                    return (
                      <span
                        key={sid}
                        draggable
                        onDragStart={() => handleDragStart(sid)}
                        onDragEnd={() => setDragStudent(null)}
                        className="inline-flex items-center gap-1 bg-card dark:bg-muted px-2 py-1 rounded-lg text-[11px] cursor-grab active:cursor-grabbing"
                      >
                        <GripVertical className="h-3 w-3 text-muted-foreground flex-none" />
                        {st.full_name?.split(' ').slice(0, 2).join(' ')}
                        <button
                          onClick={() => {
                            const updated = [...groups];
                            updated[gi] = { ...updated[gi], students: updated[gi].students.filter(id => id !== sid) };
                            setGroups(updated);
                          }}
                          className="text-red-600 dark:text-red-400 hover:text-red-500"
                        >
                          <XCircle className="h-3 w-3" />
                        </button>
                      </span>
                    );
                  })}
                </div>
                <select
                  className="w-full text-xs p-1.5 rounded-lg border bg-card dark:bg-muted dark:border-border"
                  value=""
                  onChange={e => {
                    if (!e.target.value) return;
                    const sid = e.target.value;
                    const updated = groups.map((g, i) => ({
                      ...g,
                      students: i === gi
                        ? [...(g.students || []), sid]
                        : (g.students || []).filter(id => id !== sid)
                    }));
                    setGroups(updated);
                  }}
                >
                  <option value="">{t('addStudentToGroup')}</option>
                  {presentStudents
                    .filter(s => !group.students?.includes(s.id))
                    .map(s => <option key={s.id} value={s.id}>{s.full_name}</option>)}
                </select>
              </div>
            ))}

            {(() => {
              const assignedIds = new Set(groups.flatMap(g => g.students || []));
              const unassigned = presentStudents.filter(s => !assignedIds.has(s.id));
              if (unassigned.length === 0 || groups.length === 0) return null;
              return (
                <div className="bg-muted/40 dark:bg-muted/30 rounded-xl p-3 space-y-2 border border-dashed border-border">
                  <div className="text-xs font-medium text-muted-foreground">{t('unassignedStudents')} ({unassigned.length})</div>
                  <div className="flex flex-wrap gap-1.5">
                    {unassigned.map(s => (
                      <span
                        key={s.id}
                        draggable
                        onDragStart={() => handleDragStart(s.id)}
                        onDragEnd={() => setDragStudent(null)}
                        className="inline-flex items-center gap-1 bg-card dark:bg-muted px-2 py-1 rounded-lg text-[11px] cursor-grab active:cursor-grabbing"
                      >
                        <GripVertical className="h-3 w-3 text-muted-foreground flex-none" />
                        {s.full_name?.split(' ').slice(0, 2).join(' ')}
                      </span>
                    ))}
                  </div>
                </div>
              );
            })()}

            <button
              onClick={() => setGroups([...groups, {
                id: `group_${Date.now()}`,
                name: `${t('group')} ${groups.length + 1}`,
                color: ['bg-blue-500', 'bg-green-500', 'bg-purple-500', 'bg-orange-500', 'bg-pink-500', 'bg-cyan-500'][groups.length % 6],
                students: []
              }])}
              className="w-full flex items-center justify-center gap-2 py-2 rounded-xl border-2 border-dashed border-border dark:border-border text-muted-foreground text-sm hover:border-brand-turquoise hover:text-brand-turquoise transition-colors"
            >
              <Plus className="h-4 w-4" />
              {t('addNewGroup')}
            </button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Master Settings Dialog (إعدادات الحصة) —
          merges Group A (تعريفات العناصر) + Group B (تكوين الحصة).
          The legacy stand-alone "Session Settings" modal was deleted; its
          tabs are now rendered via the `sessionConfig` prop below. */}
      <SidebarSettingsDialog
        open={showSidebarSettings}
        onOpenChange={(open) => {
          setShowSidebarSettings(open);
          // Persist follow-up grade values on close through the serialized flush
          // so it can't race another writer (it self-guards empty/no session).
          if (!open) flushFollowupRecord({ silent: true }).catch(() => {});
        }}
        isRTL={isRTL}
        t={t}
        evaluationItems={customEvaluationItems}
        onAddEvaluationItem={(item) => setCustomEvaluationItems((prev) => [...prev, item])}
        onRemoveEvaluationItem={(id) => setCustomEvaluationItems((prev) => prev.filter((x) => x.id !== id))}
        positiveBehaviours={customPositiveBehaviours}
        negativeBehaviours={customNegativeBehaviours}
        onAddPositiveBehaviour={(item) => setCustomPositiveBehaviours((prev) => [...prev, item])}
        onAddNegativeBehaviour={(item) => setCustomNegativeBehaviours((prev) => [...prev, item])}
        onRemovePositiveBehaviour={(id) => setCustomPositiveBehaviours((prev) => prev.filter((x) => (typeof x === 'string' ? `custom_${x}` !== id : x.id !== id)))}
        onRemoveNegativeBehaviour={(id) => setCustomNegativeBehaviours((prev) => prev.filter((x) => (typeof x === 'string' ? `custom_${x}` !== id : x.id !== id)))}
        skillEnabled={skillEnabled}
        onToggleSkillEnabled={setSkillEnabled}
        skillTypes={skillTypes}
        customSkills={customSkills}
        onAddCustomSkill={(name) => setCustomSkills((prev) => [...prev, name])}
        onRemoveCustomSkill={(idx) => setCustomSkills((prev) => prev.filter((_, j) => j !== idx))}
        sessionConfig={{
          subjectsList,
          subjectId: settingsSubjectId,
          onSubjectIdChange: setSettingsSubjectId,
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
          correctAnswerWeight,
          effectiveCorrectAnswerWeight,
          onCorrectAnswerWeightChange: (v) => { setCorrectAnswerWeight(v); setCorrectAnswerWeightDirty(true); },
          onSave: saveSessionSettings,
          saving: savingSettings,
        }}
      />

      {/* The legacy stand-alone Session Settings modal was removed —
          its tabs now live inside SidebarSettingsDialog above. */}

      {/* Follow-up Record (كشف المتابعة) Dialog */}
      <FollowupRecordDialog
        open={showFollowupRecord}
        onOpenChange={handleFollowupOpenChange}
        isRTL={isRTL}
        students={students}
        followupColumns={followupColumns}
        setFollowupColumns={setFollowupColumns}
        followupData={followupData}
        setFollowupData={setFollowupData}
        followupAbsences={followupAbsences}
        onAbsenceAdd={handleFollowupAbsenceAdd}
        onAbsenceRemove={handleFollowupAbsenceRemove}
        followupTab={followupTab}
        setFollowupTab={setFollowupTab}
        showAddColumnModal={showAddColumnModal}
        setShowAddColumnModal={setShowAddColumnModal}
        showColumnSettings={showColumnSettings}
        setShowColumnSettings={setShowColumnSettings}
        newColumnDraft={newColumnDraft}
        setNewColumnDraft={setNewColumnDraft}
        absencePickerStudent={absencePickerStudent}
        setAbsencePickerStudent={setAbsencePickerStudent}
        absencePickerDate={absencePickerDate}
        setAbsencePickerDate={setAbsencePickerDate}
        classId={classIdForGrades}
        onAddColumn={addClassGradeColumn}
        onUpdateColumn={updateClassGradeColumn}
        onDeleteColumn={deleteClassGradeColumn}
        onGradeChange={handleFollowupGradeChange}
      />

      {/* Record Attendance (تسجيل الحضور) — opens the unified inline-editable
          attendance table reused from فصولي → تفاصيل الفصل. Toggling a status
          fires the API immediately and updates the live class state without
          leaving /teacher/session/teach. */}
      <Dialog
        open={showAttendanceModal}
        onOpenChange={(open) => {
          setShowAttendanceModal(open);
          if (!open) finalizeSessionAttendance();
        }}
      >
        <DialogContent
          className="max-w-3xl max-h-[85vh] overflow-y-auto"
          dir={isRTL ? 'rtl' : 'ltr'}
        >
          <DialogHeader>
            <DialogTitle className="font-cairo flex items-center gap-2 text-lg">
              <ClipboardCheck className="h-5 w-5 text-teal-500" />
              {t('attendanceLogTitle') || 'سجل الحضور والغياب'}
            </DialogTitle>
          </DialogHeader>
          <InlineAttendanceTable
            classId={classIdForGrades}
            sessionId={sessionId}
            students={students}
            classData={{
              grade_name: sessionInfo?.grade_name || sessionInfo?.gradeName,
              section: sessionInfo?.section,
            }}
            onStatusChange={(studentId, newStatus) => {
              attendanceDirtyRef.current = true;
              setStudents(prev => prev.map(s =>
                s.id === studentId ? { ...s, attendance_status: newStatus } : s
              ));
            }}
          />
        </DialogContent>
      </Dialog>

      <Dialog open={showQuickNote} onOpenChange={setShowQuickNote}>
        <DialogContent className="max-w-lg" dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader>
            <DialogTitle className="font-cairo flex items-center gap-2">
              <StickyNote className="h-5 w-5 text-amber-500" />
              {t('sendQuickNote') || 'إرسال ملاحظة'}
            </DialogTitle>
          </DialogHeader>
          {(() => {
            const presentList = students.filter(s => s.attendance_status === 'present');
            const filtered = quickNoteFilter
              ? presentList.filter(s => (s.full_name || '').toLowerCase().includes(quickNoteFilter.toLowerCase()))
              : presentList;
            const allSelected = presentList.length > 0 && presentList.every(s => quickNoteIds.has(s.id));
            const toggleAll = () => {
              if (allSelected) setQuickNoteIds(new Set());
              else setQuickNoteIds(new Set(presentList.map(s => s.id)));
            };
            const toggleOne = (sid) => {
              setQuickNoteIds(prev => {
                const next = new Set(prev);
                if (next.has(sid)) next.delete(sid); else next.add(sid);
                return next;
              });
            };
            const sendQuickNote = async () => {
              const text = quickNoteText.trim();
              const ids = Array.from(quickNoteIds);
              if (!text) { nassaqError(t('writeNoteShort') || 'اكتب نص الملاحظة'); return; }
              if (ids.length === 0) { nassaqError(t('selectAtLeastOneStudent') || 'حدد طالباً واحداً على الأقل'); return; }
              setQuickNoteSending(true);
              try {
                const res = await api.post(`/session/${sessionId}/note/parents`, { text, student_ids: ids });
                const sent = res.data?.notifications_sent ?? 0;
                const studentsWithParents = res.data?.students_with_parents ?? 0;
                const studentsTargeted = res.data?.students_targeted ?? ids.length;
                const failed = res.data?.notifications_failed ?? 0;

                if (sent > 0) {
                  toast.success(
                    `${t('noteSentToParents') || 'تم إرسال الملاحظة لأولياء الأمور'} — ${sent} ${t('parents') || 'ولي أمر'} / ${studentsWithParents} ${t('students') || 'طالب'}`
                  );
                  addLog('note', `${t('note')}: ${text.slice(0, 30)} → ${sent} ${t('parents') || 'ولي أمر'}`, 'text-amber-600');
                  setShowQuickNote(false);
                  setQuickNoteText('');
                  setQuickNoteIds(new Set());
                  loadNotes();
                } else if (studentsWithParents === 0) {
                  // No parents linked — warn teacher with actionable message, keep modal open
                  toast.warning(
                    t('noParentsLinkedWarn') ||
                    `لا يوجد ولي أمر مرتبط بأي من الطلاب المحددين (${studentsTargeted}). تواصل مع إدارة المدرسة لربط أولياء الأمور.`,
                    { duration: 6000 }
                  );
                  addLog('note', `${t('note')} — ${t('noParentsLinkedShort') || 'لا يوجد ولي أمر مرتبط'}`, 'text-amber-600');
                } else if (failed > 0) {
                  toast.error(
                    `${t('errorAddingNote') || 'تعذر إرسال الملاحظة'} — ${failed} ${t('failed') || 'فشل'}`
                  );
                } else {
                  toast.warning(t('nothingToSend') || 'لم يتم إرسال أي إشعار');
                }
              } catch (e) {
                console.error('Quick note error:', e);
                nassaqError(getApiErrorMessage(e) || t('errorAddingNote') || 'تعذر إرسال الملاحظة');
              } finally {
                setQuickNoteSending(false);
              }
            };
            return (
              <div className="space-y-3 pt-1">
                <Textarea
                  value={quickNoteText}
                  onChange={(e) => setQuickNoteText(e.target.value)}
                  placeholder={t('writeNoteShort') || 'اكتب نص الملاحظة...'}
                  className="min-h-[88px] font-tajawal text-sm resize-none"
                  dir={isRTL ? 'rtl' : 'ltr'}
                />

                <div className="flex items-center justify-between gap-2 pt-1">
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <Search className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                    <input
                      value={quickNoteFilter}
                      onChange={(e) => setQuickNoteFilter(e.target.value)}
                      placeholder={t('searchStudent') || t('search') || 'بحث'}
                      className="flex-1 bg-transparent outline-none text-sm border-b border-border focus:border-amber-400 transition-colors py-1"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={toggleAll}
                    className="text-xs font-cairo font-bold text-amber-700 dark:text-amber-300 hover:text-amber-800 dark:hover:text-amber-200 transition-colors px-2.5 py-1 rounded-md bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 flex-shrink-0"
                  >
                    {allSelected ? (t('deselectAll') || 'إلغاء التحديد') : (t('selectAll') || 'تحديد الكل')}
                  </button>
                </div>

                <div className="border border-border rounded-xl divide-y divide-border max-h-64 overflow-y-auto">
                  {filtered.length === 0 ? (
                    <div className="p-6 text-center text-sm text-muted-foreground font-tajawal">
                      {t('noPresentStudents') || 'لا يوجد طلاب حاضرون'}
                    </div>
                  ) : (
                    filtered.map((s) => {
                      const checked = quickNoteIds.has(s.id);
                      return (
                        <button
                          key={s.id}
                          type="button"
                          onClick={() => toggleOne(s.id)}
                          className={`w-full flex items-center gap-3 px-3 py-2 text-start transition-colors ${
                            checked ? 'bg-amber-500/10' : 'hover:bg-muted/40'
                          }`}
                        >
                          <span className={`w-5 h-5 rounded-md border flex items-center justify-center flex-shrink-0 transition-colors ${
                            checked ? 'bg-amber-500 border-amber-500' : 'border-border bg-background'
                          }`}>
                            {checked && <CheckCircle2 className="h-3.5 w-3.5 text-white" />}
                          </span>
                          <span className="font-cairo text-sm text-foreground flex-1 truncate">{s.full_name}</span>
                          {s.student_code && (
                            <span className="text-[10px] font-mono text-muted-foreground flex-shrink-0">{s.student_code}</span>
                          )}
                        </button>
                      );
                    })
                  )}
                </div>

                <div className="flex items-center justify-between pt-1">
                  <span className="text-xs font-cairo text-foreground/70">
                    {t('selected') || 'المحددون'}: <span className="text-amber-700 dark:text-amber-300 font-bold font-mono">{quickNoteIds.size}</span> <span className="text-muted-foreground">/ {presentList.length}</span>
                  </span>
                  <span className="text-[10px] text-foreground/70 font-tajawal flex items-center gap-1">
                    <Send className="h-3 w-3 text-amber-600 dark:text-amber-400" />
                    {t('sendsToParentsOnly') || 'تُرسل لأولياء الأمور فقط'}
                  </span>
                </div>

                <div className="flex gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowQuickNote(false)}
                    disabled={quickNoteSending}
                    className="flex-1 h-11 rounded-xl bg-muted hover:bg-muted/70 text-foreground text-sm font-cairo font-bold border border-border transition-colors disabled:opacity-50"
                  >
                    {t('close') || 'إغلاق'}
                  </button>
                  <button
                    type="button"
                    onClick={sendQuickNote}
                    disabled={quickNoteSending || !quickNoteText.trim() || quickNoteIds.size === 0}
                    className="flex-1 h-11 rounded-xl bg-gradient-to-r from-amber-600 to-orange-600 hover:from-amber-700 hover:to-orange-700 disabled:from-muted disabled:to-muted disabled:text-muted-foreground disabled:cursor-not-allowed text-white text-sm font-cairo font-bold flex items-center justify-center gap-2 transition-colors shadow-md disabled:shadow-none border border-amber-700/40 disabled:border-border"
                  >
                    {quickNoteSending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                    {t('send') || 'إرسال'} ({quickNoteIds.size})
                  </button>
                </div>
              </div>
            );
          })()}
        </DialogContent>
      </Dialog>

      <Dialog open={showRandomPopup && !!selectedStudent} onOpenChange={setShowRandomPopup}>
        <DialogContent className="max-w-md text-center" dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader>
            <DialogTitle className="text-center font-cairo">{t('randomStudentPick')}</DialogTitle>
          </DialogHeader>
          {selectedStudent && (
            <div className="space-y-5 pt-2">
              <div className="flex flex-col items-center gap-2">
                <div className="w-20 h-20 rounded-full overflow-hidden ring-4 ring-amber-400/40 shadow-lg">
                  <img
                    src={selectedStudent.avatar_url || `https://api.dicebear.com/9.x/adventurer/svg?seed=${selectedStudent.id}`}
                    alt={selectedStudent.full_name}
                    className="w-full h-full object-cover"
                    onError={(e) => { e.target.src = `https://api.dicebear.com/9.x/adventurer/svg?seed=${selectedStudent.id}`; }}
                  />
                </div>
                <h3 className="text-xl font-bold font-cairo text-foreground">{selectedStudent.full_name}</h3>
                <p className="text-sm text-muted-foreground font-tajawal">{t('randomlyChosenEvaluateNow') || 'تم اختياره عشوائياً – قيّمه الآن'}</p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={async () => { await recordAnswer('correct'); setShowRandomPopup(false); }}
                  className="h-14 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-white font-cairo font-bold text-sm flex items-center justify-center gap-2 active:scale-[0.97] transition-colors shadow-md"
                >
                  <CheckCircle2 className="h-5 w-5" /> {t('correctAnswer')}
                </button>
                <button
                  onClick={async () => { await recordAnswer('wrong'); setShowRandomPopup(false); }}
                  className="h-14 rounded-xl bg-red-500 hover:bg-red-600 text-white font-cairo font-bold text-sm flex items-center justify-center gap-2 active:scale-[0.97] transition-colors shadow-md"
                >
                  <XCircle className="h-5 w-5" /> {t('wrongAnswer')}
                </button>
                <button
                  onClick={async () => {
                    const sid = selectedStudent.id;
                    const studentName = selectedStudent.full_name?.split(' ')[0] || '';
                    try {
                      await api.post(`/session/${sessionId}/homework`, { student_id: sid, status: 'not_done' });
                      setHomeworkStatuses(prev => ({ ...prev, [sid]: 'not_done' }));
                      toast.success(`${t('notSubmitted')} — ${studentName}`);
                      addLog('homework', `${studentName} — ${t('didNotSubmitHomework') || 'لم يسلم الواجب'}`, 'text-amber-600');
                    } catch (e) {
                      console.error('Homework not-submitted error:', e);
                      nassaqError(getApiErrorMessage(e) || t('errorSavingHomework') || 'تعذر تسجيل الواجب');
                    }
                    setShowRandomPopup(false);
                  }}
                  className="h-14 rounded-xl bg-amber-500 hover:bg-amber-600 text-white font-cairo font-bold text-sm flex items-center justify-center gap-2 active:scale-[0.97] transition-colors shadow-md"
                >
                  <BookOpen className="h-5 w-5" /> {t('didNotSubmitHomework') || 'لم يسلم الواجب'}
                </button>
                <button
                  onClick={() => {
                    if (!recitationEnabled) {
                      toast.error(t('enableRecitationFirst') || 'فعّل التسميع من إعدادات الحصة أولاً');
                      return;
                    }
                    setActionTab('recitation');
                    setShowRandomPopup(false);
                    toast(t('recordRecitationInPanel') || 'سجّل التسميع من اللوحة الجانبية', { icon: '🎤' });
                  }}
                  className="h-14 rounded-xl bg-purple-500 hover:bg-purple-600 text-white font-cairo font-bold text-sm flex items-center justify-center gap-2 active:scale-[0.97] transition-colors shadow-md"
                >
                  <Mic className="h-5 w-5" /> {t('recitation')}
                </button>
              </div>
              <button
                onClick={() => setShowRandomPopup(false)}
                className="w-full h-10 rounded-xl bg-muted hover:bg-muted/80 text-foreground text-sm font-cairo transition-colors"
              >
                {t('close')}
              </button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
    </SectionErrorBoundary>
  );
}

function FollowupRecordDialog({
  open, onOpenChange, isRTL, students,
  followupColumns, setFollowupColumns,
  followupData, setFollowupData,
  followupAbsences, onAbsenceAdd, onAbsenceRemove,
  followupTab, setFollowupTab,
  showAddColumnModal, setShowAddColumnModal,
  showColumnSettings, setShowColumnSettings,
  newColumnDraft, setNewColumnDraft,
  absencePickerStudent, setAbsencePickerStudent,
  absencePickerDate, setAbsencePickerDate,
  classId,
  onAddColumn,
  onUpdateColumn,
  onDeleteColumn,
  onGradeChange,
}) {
  const { t } = useTranslation();
  const allStudents = students || [];

  // Used only for the footer "X عمود ظاهر" counter — table rendering itself
  // lives in FollowupGradesTable now.
  const visibleColumns = followupColumns.filter(c => !c.hidden);

  // Local edit state for inline column-name/max-grade edits inside the
  // Column Settings dialog. We persist via the parent callback on blur so we
  // don't fire a request on every keystroke.
  const [editingColumnDrafts, setEditingColumnDrafts] = useState({});
  const getDraftValue = (col, field) => {
    const draft = editingColumnDrafts[col.id];
    if (draft && draft[field] !== undefined) return draft[field];
    return field === 'name' ? col.name : col.maxGrade;
  };
  const setDraftValue = (col, field, value) => {
    setEditingColumnDrafts(prev => ({
      ...prev,
      [col.id]: { ...(prev[col.id] || {}), [field]: value },
    }));
  };
  const flushDraft = async (col, field) => {
    const draft = editingColumnDrafts[col.id];
    if (!draft || draft[field] === undefined) return;
    const next = draft[field];
    const current = field === 'name' ? col.name : col.maxGrade;
    if (String(next) === String(current)) {
      setEditingColumnDrafts(prev => {
        const copy = { ...prev };
        if (copy[col.id]) {
          const inner = { ...copy[col.id] };
          delete inner[field];
          if (Object.keys(inner).length === 0) delete copy[col.id]; else copy[col.id] = inner;
        }
        return copy;
      });
      return;
    }
    if (onUpdateColumn) {
      await onUpdateColumn(col.id, { [field]: next });
    }
    setEditingColumnDrafts(prev => {
      const copy = { ...prev };
      delete copy[col.id];
      return copy;
    });
  };

  const handleAddColumn = async () => {
    const name = newColumnDraft.name?.trim();
    if (!name) {
      toast.error(t('columnNameRequired') || 'يرجى إدخال اسم العمود');
      return;
    }
    if (onAddColumn && classId) {
      const ok = await onAddColumn({
        name,
        group: newColumnDraft.group,
        maxGrade: newColumnDraft.maxGrade,
      });
      if (ok) {
        setNewColumnDraft({ name: '', group: 'coursework', maxGrade: 10 });
        setShowAddColumnModal(false);
      }
      return;
    }
    // Fallback (no classId): keep legacy local-only behaviour so the dialog
    // still works in edge cases where session has no class context.
    const id = `col_${Date.now()}`;
    setFollowupColumns(prev => [...prev, {
      id, name,
      group: newColumnDraft.group,
      maxGrade: Math.max(1, Number(newColumnDraft.maxGrade) || 10),
      type: 'grade', hidden: false,
    }]);
    setNewColumnDraft({ name: '', group: 'coursework', maxGrade: 10 });
    setShowAddColumnModal(false);
  };

  const handleDeleteColumn = async (id) => {
    if (onDeleteColumn && classId) {
      await onDeleteColumn(id);
      return;
    }
    setFollowupColumns(prev => prev.filter(c => c.id !== id));
  };
  const handleToggleHidden = async (id) => {
    const col = followupColumns.find(c => c.id === id);
    if (!col) return;
    if (onUpdateColumn && classId) {
      await onUpdateColumn(id, { hidden: !col.hidden });
      return;
    }
    setFollowupColumns(prev => prev.map(c => c.id === id ? { ...c, hidden: !c.hidden } : c));
  };
  const handleEditMaxGrade = (id, value) => {
    const col = followupColumns.find(c => c.id === id);
    if (!col) return;
    if (classId) {
      setDraftValue(col, 'maxGrade', value);
      return;
    }
    const v = Math.max(1, Number(value) || 1);
    setFollowupColumns(prev => prev.map(c => c.id === id ? { ...c, maxGrade: v } : c));
  };
  const handleEditColumnName = (id, value) => {
    const col = followupColumns.find(c => c.id === id);
    if (!col) return;
    if (classId) {
      setDraftValue(col, 'name', value);
      return;
    }
    setFollowupColumns(prev => prev.map(c => c.id === id ? { ...c, name: value } : c));
  };

  const formatAbsence = (dateStr) => {
    try {
      const d = new Date(dateStr);
      const day = String(d.getDate()).padStart(2, '0');
      const month = String(d.getMonth() + 1).padStart(2, '0');
      return `${day}/${month}`;
    } catch { return dateStr; }
  };

  // Delegate to the parent handlers so absence edits mark dirty + schedule the
  // serialized flush (and survive the merge poll / reopen) like grade edits.
  const addAbsence = onAbsenceAdd;
  const removeAbsence = onAbsenceRemove;

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-6xl w-[95vw] max-h-[90vh] overflow-hidden flex flex-col p-0" dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader className="px-5 pt-5 pb-3 border-b">
            <DialogTitle className="font-cairo flex items-center gap-2">
              <FileSpreadsheet className="h-5 w-5 text-brand-turquoise" />
              {t('followupRecord') || 'كشف المتابعة'}
            </DialogTitle>
          </DialogHeader>

          {/* Tabs */}
          <div className="flex items-center gap-2 px-5 pt-3 border-b">
            <button
              onClick={() => setFollowupTab('students')}
              className={`px-4 py-2 text-sm font-cairo font-semibold rounded-t-lg transition ${
                followupTab === 'students'
                  ? 'bg-brand-turquoise/10 text-brand-turquoise border-b-2 border-brand-turquoise'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <span className="inline-flex items-center gap-2">
                <Table2 className="h-4 w-4" />
                سجل الطلاب
              </span>
            </button>
            {/* "سجل الغياب" tab hidden by request — absences are now managed
                from the unified attendance tab in فصولي → تفاصيل الفصل. */}
          </div>

          {/* Toolbar (students tab only) */}
          {followupTab === 'students' && (
            <div className="flex items-center justify-between gap-2 px-5 py-2.5 bg-muted/40 dark:bg-card/40 border-b">
              <div className="text-xs text-muted-foreground font-cairo">
                {allStudents.length} طالب
              </div>
              <div className="flex items-center gap-2">
                <Button size="sm" variant="outline" onClick={() => setShowColumnSettings(true)} className="font-cairo">
                  <Settings className="h-4 w-4 me-1.5" />
                  إعدادات الأعمدة
                </Button>
                <Button size="sm" onClick={() => setShowAddColumnModal(true)} className="font-cairo bg-brand-turquoise hover:bg-brand-turquoise/90">
                  <Plus className="h-4 w-4 me-1.5" />
                  إضافة عمود
                </Button>
              </div>
            </div>
          )}

          {/* Body */}
          <div className="flex-1 overflow-auto">
            {followupTab === 'students' ? (
              <FollowupGradesTable
                students={allStudents}
                columns={followupColumns}
                gradesData={followupData}
                onGradeChange={onGradeChange}
                t={t}
              />
            ) : (
              <div className="overflow-auto">
                <table className="w-full text-sm border-collapse">
                  <thead className="sticky top-0 bg-muted dark:bg-card z-10">
                    <tr>
                      <th className="border px-2 py-2 text-center font-cairo font-bold text-xs w-12">#</th>
                      <th className="border px-3 py-2 text-start font-cairo font-bold text-xs min-w-[160px]">اسم الطالب</th>
                      <th className="border px-3 py-2 text-start font-cairo font-bold text-xs">سجل الغياب</th>
                      <th className="border px-3 py-2 text-center font-cairo font-bold text-xs w-32">إجراء</th>
                    </tr>
                  </thead>
                  <tbody>
                    {allStudents.map((student, si) => {
                      const dates = followupAbsences[student.id] || [];
                      return (
                        <tr key={student.id} className="hover:bg-muted/40 dark:hover:bg-card/40">
                          <td className="border px-2 py-2 text-center text-[11px] text-muted-foreground">{si + 1}</td>
                          <td className="border px-3 py-2 text-xs font-medium">{student.full_name}</td>
                          <td className="border px-3 py-2">
                            {dates.length === 0 ? (
                              <span className="text-xs text-muted-foreground italic">لم يسجل عليه غياب</span>
                            ) : (
                              <div className="flex flex-wrap gap-1.5">
                                {dates.map(d => (
                                  <span
                                    key={d}
                                    className="group relative inline-flex items-center justify-center min-w-[52px] h-12 rounded-full bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800/60 text-[11px] font-bold font-cairo px-2"
                                    title={d}
                                  >
                                    {formatAbsence(d)}
                                    <button
                                      onClick={() => removeAbsence(student.id, d)}
                                      className="absolute -top-1 -end-1 w-4 h-4 rounded-full bg-red-500 text-foreground text-[10px] flex items-center justify-center opacity-0 group-hover:opacity-100 transition"
                                      aria-label="حذف"
                                    >
                                      ×
                                    </button>
                                  </span>
                                ))}
                              </div>
                            )}
                          </td>
                          <td className="border px-3 py-2 text-center">
                            <Button
                              size="sm"
                              variant="outline"
                              className="font-cairo text-xs"
                              onClick={() => {
                                setAbsencePickerStudent(student);
                                setAbsencePickerDate(new Date().toISOString().slice(0, 10));
                              }}
                            >
                              <Plus className="h-3 w-3 me-1" />
                              تسجيل غياب
                            </Button>
                          </td>
                        </tr>
                      );
                    })}
                    {allStudents.length === 0 && (
                      <tr><td colSpan={4} className="text-center text-sm text-muted-foreground py-8">لا يوجد طلاب</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="flex-none px-5 py-3 border-t flex items-center justify-between bg-muted/40 dark:bg-card/40">
            <span className="text-xs text-muted-foreground font-cairo">
              {followupTab === 'students'
                ? `${visibleColumns.length} عمود ظاهر`
                : `${Object.values(followupAbsences).reduce((s, arr) => s + arr.length, 0)} غياب مسجّل`}
            </span>
            <Button size="sm" onClick={() => onOpenChange(false)}>{t('close') || 'إغلاق'}</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Add Column Modal */}
      <Dialog open={showAddColumnModal} onOpenChange={setShowAddColumnModal}>
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
              <input
                type="text"
                value={newColumnDraft.name}
                onChange={e => setNewColumnDraft(d => ({ ...d, name: e.target.value }))}
                placeholder="مثال: نشاط صفي"
                className="w-full text-sm bg-card dark:bg-card border border-border dark:border-border rounded-lg px-3 py-2 outline-none focus:border-brand-turquoise"
              />
            </div>
            <div>
              <label className="block text-xs font-cairo font-semibold mb-1">نوع العمود</label>
              <select
                value={newColumnDraft.group}
                onChange={e => setNewColumnDraft(d => ({ ...d, group: e.target.value }))}
                className="w-full text-sm bg-card dark:bg-card border border-border dark:border-border rounded-lg px-3 py-2 outline-none focus:border-brand-turquoise"
              >
                <option value="coursework">أعمال سنة</option>
                <option value="exams">اختبارات</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-cairo font-semibold mb-1">الدرجة القصوى</label>
              <input
                type="number"
                min={1}
                value={newColumnDraft.maxGrade}
                onChange={e => setNewColumnDraft(d => ({ ...d, maxGrade: e.target.value }))}
                className="w-full text-sm bg-card dark:bg-card border border-border dark:border-border rounded-lg px-3 py-2 outline-none focus:border-brand-turquoise"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2 border-t">
            <Button variant="outline" size="sm" onClick={() => setShowAddColumnModal(false)}>إلغاء</Button>
            <Button size="sm" onClick={handleAddColumn} className="bg-brand-turquoise hover:bg-brand-turquoise/90">حفظ</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Column Settings Panel */}
      <Dialog open={showColumnSettings} onOpenChange={setShowColumnSettings}>
        <DialogContent className="max-w-lg max-h-[80vh] overflow-hidden flex flex-col" dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader>
            <DialogTitle className="font-cairo flex items-center gap-2">
              <Settings className="h-5 w-5 text-brand-turquoise" />
              إعدادات الأعمدة
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-auto space-y-2 py-2">
            {followupColumns.length === 0 && (
              <div className="text-center text-sm text-muted-foreground py-6">لا توجد أعمدة</div>
            )}
            {followupColumns.map(col => (
              <div key={col.id} className="flex items-center gap-2 p-2 rounded-lg border border-border dark:border-border bg-card dark:bg-card/40">
                <button
                  onClick={() => handleToggleHidden(col.id)}
                  className={`w-9 h-9 rounded-lg flex items-center justify-center transition ${
                    col.hidden
                      ? 'bg-muted dark:bg-muted text-muted-foreground'
                      : 'bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600'
                  }`}
                  title={col.hidden ? 'إظهار' : 'إخفاء'}
                >
                  {col.hidden ? <PanelRightClose className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
                </button>
                <input
                  type="text"
                  value={getDraftValue(col, 'name')}
                  onChange={e => handleEditColumnName(col.id, e.target.value)}
                  onBlur={() => flushDraft(col, 'name')}
                  className="flex-1 text-xs font-medium bg-transparent border border-border dark:border-border rounded px-2 py-1.5 outline-none focus:border-brand-turquoise"
                />
                <span className={`text-[10px] px-2 py-1 rounded font-cairo font-semibold ${
                  col.group === 'exams'
                    ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300'
                    : 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                }`}>
                  {col.group === 'exams' ? 'اختبارات' : 'أعمال سنة'}
                </span>
                <div className="flex items-center gap-1">
                  <span className="text-[10px] text-muted-foreground">/</span>
                  <input
                    type="number"
                    min={1}
                    value={getDraftValue(col, 'maxGrade')}
                    onChange={e => handleEditMaxGrade(col.id, e.target.value)}
                    onBlur={() => flushDraft(col, 'maxGrade')}
                    className="w-14 text-xs text-center bg-transparent border border-border dark:border-border rounded px-1 py-1.5 outline-none focus:border-brand-turquoise"
                  />
                </div>
                <button
                  onClick={() => handleDeleteColumn(col.id)}
                  className="w-9 h-9 rounded-lg flex items-center justify-center bg-red-50 dark:bg-red-900/20 text-red-500 hover:bg-red-100"
                  title="حذف"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
          <div className="flex justify-end pt-2 border-t">
            <Button size="sm" onClick={() => setShowColumnSettings(false)}>تم</Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Absence Date Picker */}
      <Dialog open={!!absencePickerStudent} onOpenChange={(o) => { if (!o) setAbsencePickerStudent(null); }}>
        <DialogContent className="max-w-sm" dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader>
            <DialogTitle className="font-cairo flex items-center gap-2">
              <UserCheck className="h-5 w-5 text-brand-turquoise" />
              تسجيل غياب
            </DialogTitle>
          </DialogHeader>
          <div className="py-2 space-y-3">
            <div className="text-sm font-cairo">
              <span className="text-muted-foreground">الطالب:</span>{' '}
              <span className="font-bold">{absencePickerStudent?.full_name}</span>
            </div>
            <div>
              <label className="block text-xs font-cairo font-semibold mb-1">تاريخ الغياب</label>
              <input
                type="date"
                value={absencePickerDate}
                onChange={e => setAbsencePickerDate(e.target.value)}
                className="w-full text-sm bg-card dark:bg-card border border-border dark:border-border rounded-lg px-3 py-2 outline-none focus:border-brand-turquoise"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2 border-t">
            <Button variant="outline" size="sm" onClick={() => setAbsencePickerStudent(null)}>إلغاء</Button>
            <Button
              size="sm"
              className="bg-brand-turquoise hover:bg-brand-turquoise/90"
              onClick={() => {
                if (absencePickerStudent && absencePickerDate) {
                  addAbsence(absencePickerStudent.id, absencePickerDate);
                }
                setAbsencePickerStudent(null);
              }}
            >
              حفظ
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

function SessionReviewPhase({ reviewData, sessionInfo, closingNote, setClosingNote, onConfirm, onBack, loading, isRTL }) {
  const { t } = useTranslation();
  const r = reviewData;
  return (
    <div className="min-h-screen bg-background p-4 flex items-center justify-center" dir={isRTL ? 'rtl' : 'ltr'}>
      <div className="w-full max-w-lg space-y-4 pb-6 max-h-screen overflow-y-auto">
        <div className="bg-gradient-to-br from-card to-background rounded-2xl p-5 border border-border text-center">
          <ClipboardCheck className="h-12 w-12 mx-auto mb-2 text-amber-600 dark:text-amber-400" />
          <h1 className="font-cairo text-xl font-bold text-foreground">{t('sessionSummaryReview')}</h1>
          <p className="text-muted-foreground text-sm mt-1">{sessionInfo?.subject_name || sessionInfo?.subjectName} — {sessionInfo?.class_name || sessionInfo?.className}</p>
          <div className="mt-3 text-2xl font-mono font-bold text-foreground">{r.duration_minutes || 0} <span className="text-sm text-muted-foreground">{t('durationMinutes')}</span></div>
        </div>

        {r.warnings?.length > 0 && (
          <div className="bg-amber-500/10 dark:bg-amber-900/30 border border-amber-500/30 rounded-xl p-4 space-y-2">
            <h3 className="text-amber-600 dark:text-amber-400 text-sm font-bold font-cairo flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" /> {t('warnings')}
            </h3>
            {r.warnings.map((w, i) => (
              <div key={i} className="flex items-center gap-2 text-amber-700 dark:text-amber-300 text-xs">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-none" />
                {w}
              </div>
            ))}
          </div>
        )}

        <div className="bg-card rounded-xl p-4">
          <h3 className="text-muted-foreground text-sm mb-3 font-cairo font-bold flex items-center gap-2">
            <Users className="h-4 w-4 text-green-600 dark:text-green-400" /> {t('attendanceData')}
          </h3>
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: t('registered'), value: r.attendance?.total, color: 'text-foreground' },
              { label: t('present'), value: r.attendance?.present, color: 'text-green-600 dark:text-green-400' },
              { label: t('absent'), value: r.attendance?.absent, color: 'text-red-600 dark:text-red-400' },
              { label: t('late'), value: r.attendance?.late, color: 'text-amber-600 dark:text-amber-400' },
              { label: t('excused'), value: r.attendance?.excused, color: 'text-blue-600 dark:text-blue-400' },
              { label: t('attendanceRate'), value: `${r.attendance?.rate || 0}%`, color: 'text-emerald-600 dark:text-emerald-400' },
            ].map(item => (
              <div key={item.label} className="bg-foreground/5 rounded-lg p-2 text-center">
                <div className={`text-lg font-bold ${item.color}`}>{item.value ?? 0}</div>
                <div className="text-muted-foreground text-[10px]">{item.label}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-card rounded-xl p-4">
          <h3 className="text-muted-foreground text-sm mb-3 font-cairo font-bold flex items-center gap-2">
            <Activity className="h-4 w-4 text-blue-600 dark:text-blue-400" /> {t('interactionData')}
          </h3>
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: t('participations'), value: r.interactions?.total_participations, color: 'text-blue-600 dark:text-blue-400' },
              { label: t('participatingStudents'), value: r.interactions?.participating_students, color: 'text-purple-600 dark:text-purple-400' },
              { label: t('evaluatedStudents'), value: r.interactions?.evaluated_students ?? r.interactions?.participating_students, color: 'text-indigo-600 dark:text-indigo-400' },
              { label: t('questions'), value: r.interactions?.questions_asked, color: 'text-cyan-600 dark:text-cyan-400' },
              { label: t('correctAnswers'), value: r.interactions?.correct_answers, color: 'text-green-600 dark:text-green-400' },
              { label: t('wrongAnswers'), value: r.interactions?.wrong_answers, color: 'text-red-600 dark:text-red-400' },
              { label: t('notesSent'), value: r.notes?.sent_to_parents ?? 0, color: 'text-emerald-600 dark:text-emerald-400' },
              { label: t('participationRate'), value: `${r.interactions?.participation_rate || 0}%`, color: 'text-emerald-600 dark:text-emerald-400' },
            ].map(item => (
              <div key={item.label} className="bg-foreground/5 rounded-lg p-2 text-center">
                <div className={`text-lg font-bold ${item.color}`}>{item.value ?? 0}</div>
                <div className="text-muted-foreground text-[10px]">{item.label}</div>
              </div>
            ))}
          </div>
        </div>

        {(r.behaviours?.total > 0) && (
          <div className="bg-card rounded-xl p-4">
            <h3 className="text-muted-foreground text-sm mb-3 font-cairo font-bold flex items-center gap-2">
              <Heart className="h-4 w-4 text-pink-600 dark:text-pink-400" /> {t('behaviourData')}
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-green-500/10 dark:bg-green-900/30 rounded-lg p-3 text-center">
                <ThumbsUp className="h-5 w-5 text-green-600 dark:text-green-400 mx-auto mb-1" />
                <div className="text-xl font-bold text-green-600 dark:text-green-400">{r.behaviours?.positive || 0}</div>
                <div className="text-muted-foreground text-[10px]">{t('positiveBehaviour')}</div>
              </div>
              <div className="bg-red-500/10 dark:bg-red-900/30 rounded-lg p-3 text-center">
                <ThumbsDown className="h-5 w-5 text-red-600 dark:text-red-400 mx-auto mb-1" />
                <div className="text-xl font-bold text-red-600 dark:text-red-400">{r.behaviours?.negative || 0}</div>
                <div className="text-muted-foreground text-[10px]">{t('negativeBehaviour')}</div>
              </div>
            </div>
          </div>
        )}

        {(r.skills?.recorded > 0) && (
          <div className="bg-card rounded-xl p-4">
            <h3 className="text-muted-foreground text-sm mb-3 font-cairo font-bold flex items-center gap-2">
              <Star className="h-4 w-4 text-purple-600 dark:text-purple-400" /> {t('skillsData')}
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-purple-500/10 dark:bg-purple-900/30 rounded-lg p-3 text-center">
                <div className="text-xl font-bold text-purple-600 dark:text-purple-400">{r.skills?.recorded}</div>
                <div className="text-muted-foreground text-[10px]">{t('recordedSkill')}</div>
              </div>
              <div className="bg-indigo-500/10 dark:bg-indigo-900/30 rounded-lg p-3 text-center">
                <div className="text-xl font-bold text-indigo-600 dark:text-indigo-400">{r.skills?.students_count}</div>
                <div className="text-muted-foreground text-[10px]">{t('student')}</div>
              </div>
            </div>
          </div>
        )}

        <div className="bg-card rounded-xl p-4">
          <h3 className="text-muted-foreground text-sm mb-3 font-cairo font-bold flex items-center gap-2">
            <StickyNote className="h-4 w-4 text-amber-500 dark:text-amber-400" /> {t('notesLabel')}
          </h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-amber-500/10 dark:bg-amber-900/30 border border-amber-500/20 dark:border-transparent rounded-lg p-3 text-center">
              <div className="text-xl font-bold text-amber-600 dark:text-amber-400">{r.notes?.total || 0}</div>
              <div className="text-muted-foreground text-[10px]">{t('totalNotes')}</div>
            </div>
            <div className="bg-amber-500/10 dark:bg-amber-900/30 border border-amber-500/20 dark:border-transparent rounded-lg p-3 text-center">
              <div className="text-xl font-bold text-amber-600 dark:text-amber-400">{r.notes?.teacher_notes || 0}</div>
              <div className="text-muted-foreground text-[10px]">{t('teacherNotes')}</div>
            </div>
          </div>
        </div>

        {r.needs_attention?.length > 0 && (
          <div className="bg-card rounded-xl p-4">
            <h3 className="text-muted-foreground text-sm mb-3 font-cairo font-bold flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-500 dark:text-amber-400" /> {t('needsAttention')}
            </h3>
            {r.needs_attention.map((s, i) => (
              <div key={i} className="flex items-center justify-between py-1.5 border-b border-border last:border-0">
                <span className="text-foreground text-sm font-cairo">{s.name}</span>
                <span className="text-[11px] font-tajawal px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400 border border-amber-500/20 dark:border-transparent">{s.reason}</span>
              </div>
            ))}
          </div>
        )}

        {r.top_participants?.length > 0 && (
          <div className="bg-card rounded-xl p-4">
            <h3 className="text-muted-foreground text-sm mb-3 font-cairo font-bold flex items-center gap-2">
              <Award className="h-4 w-4 text-amber-600 dark:text-amber-400" /> {t('topParticipants')}
            </h3>
            {r.top_participants.map((p, i) => (
              <div key={i} className="flex items-center justify-between py-1.5">
                <div className="flex items-center gap-2">
                  <span className="text-amber-600 dark:text-amber-400 text-xs font-bold w-5">#{i + 1}</span>
                  <span className="text-foreground text-sm">{p.name}</span>
                </div>
                <span className="text-green-600 dark:text-green-400 text-xs">{p.correct_answers} ✓ | {p.participations} {t('participation')}</span>
              </div>
            ))}
          </div>
        )}

        <div className="bg-card rounded-xl p-4">
          <h3 className="text-muted-foreground text-sm mb-3 font-cairo font-bold flex items-center gap-2">
            <PenLine className="h-4 w-4 text-cyan-600 dark:text-cyan-400" /> {t('closingNoteLabel')}
          </h3>
          <Textarea
            value={closingNote}
            onChange={(e) => setClosingNote(e.target.value)}
            placeholder={t('closingNotePlaceholder')}
            className="bg-background border-border text-foreground placeholder:text-muted-foreground/70 resize-none text-sm font-cairo"
            rows={3}
          />
        </div>

        <div className="flex gap-3 pt-2">
          <button
            onClick={onBack}
            className="flex-1 h-12 rounded-xl bg-muted hover:bg-muted text-foreground font-cairo font-bold text-sm transition-colors"
          >
            {t('back')}
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="flex-1 h-12 rounded-xl bg-red-600 hover:bg-red-500 disabled:opacity-60 text-foreground font-cairo font-bold text-sm flex items-center justify-center gap-2 transition-colors"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
            {t('confirmAndEnd')}
          </button>
        </div>
      </div>
    </div>
  );
}


function StudentRow({ student, isFlashing, isSelected, onClick, onMenu, onSendNote, homeworkEnabled, homeworkStatus, onToggleHomework }) {
  const { t } = useTranslation();
  const homeworkLabel = t('modeHomework');
  const noteLabel = t('note');
  const initials = student.full_name?.charAt(0) || '?';
  const count = student.interactionCount || 0;
  const correct = student.correctAnswers || 0;
  const isFemale = student.gender === 'female';
  const isAbsent = student.attendance_status === 'absent';
  // Default state for the inline homework toggle is "أنجز" (done) — only the
  // explicit 'not_done' status flips the badge to the muted/red state.
  const isHomeworkDone = homeworkStatus !== 'not_done';
  const avatarBg = isFemale ? 'bg-gradient-to-br from-pink-500 to-rose-600' : 'bg-gradient-to-br from-sky-500 to-blue-600';
  const conditions = student.health_conditions || student.conditions || [];
  const condList = Array.isArray(conditions) ? conditions : (typeof conditions === 'string' ? conditions.split(',').map(s => s.trim()).filter(Boolean) : []);

  return (
    <div
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick?.(); } }}
      className={`group relative flex items-center gap-3 px-3 py-2 rounded-lg border transition-all cursor-pointer ${
        isFlashing
          ? 'bg-amber-500/20 border-amber-400 ring-2 ring-amber-400 scale-[1.01]'
          : isSelected
          ? 'bg-amber-500/10 border-amber-400/60 ring-1 ring-amber-400/50'
          : isAbsent
          ? 'bg-rose-500/5 border-rose-400/30 hover:bg-rose-500/10'
          : 'bg-card/40 border-border hover:bg-foreground/[0.04]'
      }`}
    >
      <div className={`relative w-10 h-10 rounded-full flex-none flex items-center justify-center text-foreground font-bold shadow ${avatarBg}`}>
        {student.avatar_url ? (
          <img src={student.avatar_url} alt={initials} className="w-10 h-10 rounded-full object-cover" />
        ) : (
          <span className="text-sm">{initials}</span>
        )}
        {count > 0 && (
          <span className={`absolute -top-1 -end-1 min-w-[18px] h-[18px] px-1 rounded-full text-[10px] font-bold flex items-center justify-center text-white shadow-sm ${
            correct > 0 ? 'bg-emerald-500' : 'bg-amber-500'
          }`}>
            {count}
          </span>
        )}
      </div>
      <div className="flex-1 min-w-0 flex items-center gap-2 flex-wrap">
        <span className={`font-cairo text-sm font-bold truncate ${isAbsent ? 'text-rose-600 dark:text-rose-400 line-through opacity-70' : 'text-foreground'}`}>
          {student.full_name}
        </span>
        {student.student_code && (
          <span className="text-[10px] text-muted-foreground tabular-nums">#{student.student_code}</span>
        )}
        {isAbsent && (
          <span className="inline-flex items-center gap-1 text-[10px] font-bold text-rose-600 dark:text-rose-400 bg-rose-500/10 border border-rose-400/30 rounded px-1.5 py-0.5">
            <X className="h-3 w-3" /> غائب
          </span>
        )}
        {condList.slice(0, 4).map((c, i) => {
          const def = HEALTH_BADGES[c];
          if (!def) return null;
          const Icon = def.icon;
          return (
            <span key={i} title={c} className={`inline-flex items-center justify-center w-5 h-5 rounded-full ${def.bg}`}>
              <Icon className={`h-3 w-3 ${def.color}`} />
            </span>
          );
        })}
        {count > 0 && (
          <span className="ms-auto text-[10px] text-muted-foreground tabular-nums hidden sm:inline">
            <span className="text-emerald-600 dark:text-emerald-400 font-bold">{correct}</span>/{count}
          </span>
        )}
      </div>
      {homeworkEnabled && onToggleHomework && !isAbsent && (
        <button
          onClick={(e) => { e.stopPropagation(); onToggleHomework(student.id); }}
          className={`inline-flex items-center gap-1.5 flex-none rounded-full border px-2.5 py-1 text-[11px] font-bold transition-colors opacity-90 group-hover:opacity-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 focus-visible:ring-offset-background active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed ${
            isHomeworkDone
              ? 'text-emerald-700 dark:text-emerald-300 bg-emerald-500/10 border-emerald-400/40 hover:bg-emerald-500/20 focus-visible:ring-emerald-400'
              : 'text-rose-700 dark:text-rose-300 bg-rose-500/10 border-rose-400/40 hover:bg-rose-500/20 focus-visible:ring-rose-400'
          }`}
          aria-label={isHomeworkDone ? 'أنجز الواجب' : 'لم ينجز الواجب'}
          aria-pressed={isHomeworkDone}
          title={isHomeworkDone ? 'الواجب: أنجز' : 'الواجب: لم ينجز'}
        >
          <ClipboardCheck className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">{homeworkLabel}</span>
        </button>
      )}
      {onSendNote && !isAbsent && (
        <button
          onClick={(e) => { e.stopPropagation(); onSendNote(student); }}
          className="inline-flex items-center gap-1.5 flex-none rounded-full border px-2.5 py-1 text-[11px] font-bold text-amber-700 dark:text-amber-300 bg-amber-500/10 border-amber-400/40 hover:bg-amber-500/20 transition-colors opacity-90 group-hover:opacity-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-1 focus-visible:ring-offset-background active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
          aria-label={noteLabel}
          title={noteLabel}
        >
          <StickyNote className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">{noteLabel}</span>
        </button>
      )}
      {onMenu && (
        <button
          onClick={(e) => { e.stopPropagation(); onMenu(student); }}
          className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-foreground/10 opacity-60 group-hover:opacity-100"
          aria-label="more"
        >
          <MoreHorizontal className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}

function StudentCard({ student, isFlashing, isSelected, onClick }) {
  const initials = student.full_name?.charAt(0) || '?';
  const count = student.interactionCount || 0;
  const correct = student.correctAnswers || 0;
  const isFemale = student.gender === 'female';
  const avatarBg = isFlashing ? 'bg-foreground/20' : isFemale ? 'bg-gradient-to-br from-pink-500 to-rose-600' : 'bg-gradient-to-br from-sky-500 to-blue-600';

  const interactionLevel = count === 0 ? 'none' : count <= 2 ? 'low' : count <= 5 ? 'medium' : 'high';
  const interactionRing = {
    none: '',
    low: 'ring-2 ring-amber-500/40',
    medium: 'ring-2 ring-blue-500/50',
    high: 'ring-2 ring-green-500/60',
  }[interactionLevel];

  return (
    <button
      onClick={onClick}
      className={`relative rounded-xl p-2 text-center transition-colors duration-150 ${
        isFlashing
          ? 'bg-brand-turquoise ring-4 ring-brand-turquoise/50 scale-110 z-10 shadow-xl shadow-brand-turquoise/30'
          : isSelected
          ? 'bg-brand-navy/80 ring-2 ring-brand-turquoise scale-105'
          : 'bg-muted/60 hover:bg-muted/60 hover:scale-105'
      }`}
    >
      <div className={`relative w-12 h-12 rounded-full mx-auto mb-1.5 flex items-center justify-center text-foreground font-bold shadow-md ${avatarBg} ${interactionRing}`}>
        {student.avatar_url ? (
          <img src={student.avatar_url} alt={initials} className="w-12 h-12 rounded-full object-cover" />
        ) : (
          <span className="text-lg">{initials}</span>
        )}
        {count > 0 && (
          <span className={`absolute -top-1 -end-1 w-5 h-5 rounded-full text-[9px] font-bold flex items-center justify-center text-foreground shadow-sm ${
            correct > 0 ? 'bg-green-500' : 'bg-amber-500'
          }`}>
            {count}
          </span>
        )}
      </div>
      <p className="text-foreground text-[10px] font-medium leading-tight truncate">
        {student.full_name?.split(' ').slice(0, 2).join(' ')}
      </p>
      {count > 0 && (
        <div className="mt-0.5 flex items-center justify-center gap-1">
          <span className="text-green-600 dark:text-green-400 text-[9px] font-bold">{correct}</span>
          <span className="text-muted-foreground/70 text-[9px]">/</span>
          <span className="text-muted-foreground text-[9px]">{count}</span>
        </div>
      )}
    </button>
  );
}

function ActionButton({ color, icon, label, sub, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`${color} text-foreground rounded-lg py-3 px-2 flex flex-col items-center gap-1 transition-colors active:scale-95`}
    >
      {icon}
      <span className="text-xs font-medium">{label}</span>
      <span className="text-[10px] opacity-75">{sub}</span>
    </button>
  );
}

export function SessionSummary({ summary, sessionInfo, onHome, isRTL }) {
  const { t } = useTranslation();
  const { api } = useAuth();
  const { nassaqError, nassaqInfo } = useNassaqAlert();
  const navigate = useNavigate();
  const [exporting, setExporting] = useState(false);
  const [sendFailed, setSendFailed] = useState(false);
  const [resending, setResending] = useState(false);
  const hasSentReport = useRef(false);

  useEffect(() => {
    confetti({ particleCount: 120, spread: 80, origin: { y: 0.5 } });
    const t1 = setTimeout(() => confetti({ particleCount: 60, angle: 60, spread: 55, origin: { x: 0, y: 0.6 } }), 300);
    const t2 = setTimeout(() => confetti({ particleCount: 60, angle: 120, spread: 55, origin: { x: 1, y: 0.6 } }), 600);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, []);

  const sendParentNotifications = async () => {
    const storageKey = summary?.session_record_id ? `nassaq:summarySent:${summary.session_record_id}` : null;
    const clearGuardForRetry = () => {
      hasSentReport.current = false;
      if (storageKey) {
        try { sessionStorage.removeItem(storageKey); } catch (_) { /* noop */ }
      }
    };
    const setGuardSent = (value = '1') => {
      hasSentReport.current = true;
      if (storageKey) {
        try { sessionStorage.setItem(storageKey, value); } catch (_) { /* noop */ }
      }
    };
    const subjectName = sessionInfo?.subject_name || sessionInfo?.subjectName || '';
    const className = sessionInfo?.class_name || sessionInfo?.className || '';
    const durationMin = summary.duration_minutes || 0;
    const presentCount = summary.present_count || 0;
    const absentCount = summary.absent_count || 0;
    const questionsCount = summary.questions_asked || 0;
    const correctCount = summary.correct_answers || 0;
    const classId = sessionInfo?.class_id || sessionInfo?.classId;
    const notifPayload = {
      title: `${t('sessionSummary')} — ${subjectName}`,
      title_en: `Session Summary — ${subjectName}`,
      message: `${t('sessionSummaryMessage', {
        subject: subjectName,
        class: className,
        duration: durationMin,
        present: presentCount,
        absent: absentCount,
        questions: questionsCount,
        correct: correctCount
      })}`,
      message_en: `Session for ${subjectName} (${className}) completed. Duration: ${durationMin} min. Present: ${presentCount}, Absent: ${absentCount}. Questions: ${questionsCount}, Correct: ${correctCount}.`,
      notification_type: 'communication',
      priority: 'medium',
      recipient_role: 'parent',
      related_entity: 'session',
      related_entity_id: summary.session_record_id,
      scope_class_id: classId,
    };
    // Task #486 — management delivery is now the backend's responsibility
    // (`session_engine.end_session` persists a summary notification per
    // resolved school_principal / school_sub_admin in the session's tenant)
    // and reports back how many recipients were actually written via
    // `summary.management_notifications_sent`. The FE fires only the
    // parent-cohort POST here and picks a truthful toast.
    let resp;
    try {
      resp = await api.post('/notifications', notifPayload);
    } catch (e) {
      // A genuine delivery failure. Map the HTTP status to a DISTINCT, safe
      // Arabic message via NassaqAlertDialog — never the raw backend string
      // (it may carry the IT broadcast-deny wording) and never toast.error.
      // Clear the one-shot guard so the teacher can retry.
      clearGuardForRetry();
      setSendFailed(true);
      const status = e?.response?.status;
      if (status === 403) {
        nassaqError(t('reportSendPermissionDenied'));
      } else if (status === 404) {
        nassaqError(t('reportSendReportMissing'));
      } else {
        nassaqError(t('reportSendServiceError'));
      }
      return;
    }
    // The POST succeeded HTTP-wise, but a zero-delivery result (no active
    // linked parents) must NOT be shown as success. Inform the teacher and
    // keep the resend affordance so they can retry after linking a parent.
    const createdCount = Number(resp?.data?.created_count || 0);
    if (createdCount <= 0) {
      // Zero-delivery: no active linked parents yet. Arm the guard with a
      // DISTINCT value so a later reload does NOT auto-send again (which would
      // re-pop this info dialog), but instead re-surfaces the resend button so
      // the teacher can retry after linking/activating a parent.
      setGuardSent('zero');
      setSendFailed(true);
      nassaqInfo(t('reportNoLinkedParents'));
      return;
    }
    // Real delivery — re-arm the one-shot guard so a reload/re-mount (or a
    // manual resend after an earlier failure) never double-sends, clear the
    // failed state, and pick a truthful toast: parents+admin only when
    // management actually received the summary, otherwise parents-only.
    setGuardSent();
    setSendFailed(false);
    const mgmtSent = Number(summary?.management_notifications_sent || 0);
    if (mgmtSent > 0) {
      toast.success(t('reportSentToParentsAndAdmin'));
    } else {
      toast.success(t('reportSentToParentsOnly'));
    }
    confetti({ particleCount: 50, spread: 60, origin: { y: 0.7 }, colors: ['#10b981', '#34d399', '#6ee7b7'] });
  };

  useEffect(() => {
    if (hasSentReport.current) return;
    if (!summary || !summary.session_record_id) return;
    const storageKey = `nassaq:summarySent:${summary.session_record_id}`;
    let prior = null;
    try {
      prior = sessionStorage.getItem(storageKey);
    } catch (_) {
      // sessionStorage unavailable — fall back to ref-only guard below.
    }
    if (prior === '1') {
      // A real delivery already happened — never auto-send or prompt again.
      hasSentReport.current = true;
      return;
    }
    if (prior === 'zero') {
      // The previous attempt reached no active parents. Do NOT auto-send (that
      // would re-pop the info dialog on every reload); instead just re-surface
      // the resend button so the teacher can retry after linking a parent.
      hasSentReport.current = true;
      setSendFailed(true);
      return;
    }
    try {
      sessionStorage.setItem(storageKey, '1');
    } catch (_) {
      // sessionStorage unavailable — fall back to ref-only guard
    }
    hasSentReport.current = true;
    sendParentNotifications();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [summary?.session_record_id]);

  const handleResendReport = async () => {
    if (resending) return;
    setResending(true);
    try {
      await sendParentNotifications();
    } finally {
      setResending(false);
    }
  };

  const exportReport = async () => {
    setExporting(true);
    try {
      const res = await api.get(`/session/${summary.session_record_id}/export-report`);
      const data = res.data;
      const rows = [
        [t('studentName'), t('attendance'), t('correctAnswers'), t('wrongAnswers'), t('participations'), t('positiveBehaviour'), t('negativeBehaviour')],
        ...(data.students || []).map(s => [
          s.student_name, s.attendance_status, s.correct_answers, s.wrong_answers,
          s.participations, s.positive_behaviors, s.negative_behaviors
        ])
      ];
      const escapeCSV = (val) => {
        const str = String(val ?? '');
        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
          return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
      };
      const csvContent = '\uFEFF' + rows.map(r => r.map(escapeCSV).join(',')).join('\n');
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `session-report-${data.date || 'report'}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(t('reportExportedSuccessfully'));
    } catch (e) {
      console.error('Error exporting report:', e);
      toast.error(t('failedToExportReport'));
    } finally {
      setExporting(false);
    }
  };

  const hasBehaviours = (summary.positive_behaviours || 0) + (summary.negative_behaviours || 0) > 0;
  const hasSkills = (summary.skills_recorded || 0) > 0;

  return (
    <div className="min-h-screen bg-background p-4 flex items-center justify-center" dir={isRTL ? 'rtl' : 'ltr'}>
      <div className="w-full max-w-md space-y-4 pb-6">
        <div className="bg-gradient-to-br from-brand-turquoise to-brand-navy rounded-2xl p-6 text-white text-center relative overflow-hidden shadow-lg shadow-brand-navy/20">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_30%,rgba(255,255,255,0.18),transparent_60%)]" />
          <div className="absolute inset-0 bg-black/10" />
          <div className="relative z-10">
            <Trophy className="h-14 w-14 mx-auto mb-3 text-amber-300 drop-shadow-[0_2px_4px_rgba(0,0,0,0.4)]" />
            <h1 className="font-cairo text-2xl font-bold text-white drop-shadow-[0_1px_2px_rgba(0,0,0,0.5)]">{t('sessionEnded')}</h1>
            <p className="text-white/90 mt-1 drop-shadow-[0_1px_2px_rgba(0,0,0,0.4)]">{sessionInfo?.subject_name || sessionInfo?.subjectName} — {sessionInfo?.class_name || sessionInfo?.className}</p>
            <div className="mt-4 text-3xl font-mono font-bold text-white drop-shadow-[0_1px_2px_rgba(0,0,0,0.5)]">{summary.duration_minutes || 0} <span className="text-lg text-white/85 font-cairo">{t('durationMinutes')}</span></div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          {[
            { label: t('present'), value: summary.present_count, color: 'text-green-600 dark:text-green-400', bg: 'bg-green-500/10 dark:bg-green-900/30', icon: <UserCheck className="h-5 w-5 text-green-600 dark:text-green-400" /> },
            { label: t('absent'), value: summary.absent_count, color: 'text-red-600 dark:text-red-400', bg: 'bg-red-500/10 dark:bg-red-900/30', icon: <XCircle className="h-5 w-5 text-red-600 dark:text-red-400" /> },
            { label: t('evaluatedStudents'), value: summary.evaluated_students ?? summary.present_count, color: 'text-indigo-600 dark:text-indigo-400', bg: 'bg-indigo-500/10 dark:bg-indigo-900/30', icon: <ClipboardCheck className="h-5 w-5 text-indigo-600 dark:text-indigo-400" /> },
            { label: t('questions'), value: summary.questions_asked, color: 'text-blue-600 dark:text-blue-400', bg: 'bg-blue-500/10 dark:bg-blue-900/30', icon: <FileQuestion className="h-5 w-5 text-blue-600 dark:text-blue-400" /> },
            { label: t('correctAnswers'), value: summary.correct_answers, color: 'text-amber-600 dark:text-amber-400', bg: 'bg-amber-500/10 dark:bg-amber-900/30', icon: <CheckCircle2 className="h-5 w-5 text-amber-600 dark:text-amber-400" /> },
            { label: t('notesSent'), value: summary.notes_sent ?? 0, color: 'text-emerald-600 dark:text-emerald-400', bg: 'bg-emerald-500/10 dark:bg-emerald-900/30', icon: <Send className="h-5 w-5 text-emerald-600 dark:text-emerald-400" /> },
          ].map(item => (
            <div key={item.label} className={`${item.bg} rounded-xl p-4 text-center`}>
              <div className="text-lg mb-1">{item.icon}</div>
              <div className={`text-2xl font-bold ${item.color}`}>{item.value ?? 0}</div>
              <div className="text-muted-foreground text-xs mt-1">{item.label}</div>
            </div>
          ))}
        </div>

        {(hasBehaviours || hasSkills) && (
          <div className="bg-card rounded-xl p-4">
            <h3 className="text-muted-foreground text-sm mb-3 flex items-center gap-2">
              <Heart className="h-4 w-4 text-pink-600 dark:text-pink-400" /> {t('behaviourData')}
            </h3>
            <div className={`grid ${hasSkills ? 'grid-cols-3' : 'grid-cols-2'} gap-3`}>
              {hasBehaviours && (
                <>
                  <div className="bg-green-500/10 dark:bg-green-900/30 rounded-lg p-3 text-center">
                    <ThumbsUp className="h-5 w-5 text-green-600 dark:text-green-400 mx-auto mb-1" />
                    <div className="text-xl font-bold text-green-600 dark:text-green-400">{summary.positive_behaviours || 0}</div>
                    <div className="text-muted-foreground text-[10px]">{t('positiveBehaviour')}</div>
                  </div>
                  <div className="bg-red-500/10 dark:bg-red-900/30 rounded-lg p-3 text-center">
                    <ThumbsDown className="h-5 w-5 text-red-600 dark:text-red-400 mx-auto mb-1" />
                    <div className="text-xl font-bold text-red-600 dark:text-red-400">{summary.negative_behaviours || 0}</div>
                    <div className="text-muted-foreground text-[10px]">{t('negativeBehaviour')}</div>
                  </div>
                </>
              )}
              {hasSkills && (
                <div className="bg-purple-500/10 dark:bg-purple-900/30 rounded-lg p-3 text-center">
                  <Star className="h-5 w-5 text-purple-600 dark:text-purple-400 mx-auto mb-1" />
                  <div className="text-xl font-bold text-purple-600 dark:text-purple-400">{summary.skills_recorded}</div>
                  <div className="text-muted-foreground text-[10px]">{t('recordedSkill')}</div>
                </div>
              )}
            </div>
          </div>
        )}

        {summary.participation_rate !== undefined && (
          <div className="bg-card rounded-xl p-4">
            <div className="flex justify-between text-sm text-muted-foreground mb-2">
              <span>{t('participationRate')}</span>
              <span className="text-foreground font-bold">{Math.round(summary.participation_rate)}%</span>
            </div>
            <div className="h-2.5 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-brand-turquoise to-brand-navy transition-colors"
                style={{ width: `${summary.participation_rate}%` }}
              />
            </div>
          </div>
        )}

        {summary.needs_attention?.length > 0 && (
          <div className="bg-card rounded-xl p-4">
            <h3 className="text-muted-foreground text-sm mb-3 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400" /> {t('needsAttention')}
            </h3>
            {summary.needs_attention.map((s, i) => (
              <div key={i} className="flex items-center justify-between py-1.5 border-b border-border last:border-0">
                <span className="text-foreground text-sm">{s.name}</span>
                <span className="text-amber-600 dark:text-amber-400 text-xs">{s.reason}</span>
              </div>
            ))}
          </div>
        )}

        {summary.top_participants?.length > 0 && (
          <div className="bg-card rounded-xl p-4">
            <h3 className="text-muted-foreground text-sm mb-3 flex items-center gap-2">
              <Award className="h-4 w-4 text-amber-600 dark:text-amber-400" /> {t('topParticipants')}
            </h3>
            {summary.top_participants.map((p, i) => (
              <div key={i} className="flex items-center justify-between py-1.5">
                <div className="flex items-center gap-2">
                  <span className="text-amber-600 dark:text-amber-400 text-xs font-bold w-5">#{i + 1}</span>
                  <span className="text-foreground text-sm">{p.name}</span>
                </div>
                <Badge className="bg-amber-500/10 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300 text-xs">{p.correct_answers} ✓</Badge>
              </div>
            ))}
          </div>
        )}

        {sendFailed && (
          <button
            onClick={handleResendReport}
            disabled={resending}
            className="w-full h-11 rounded-xl bg-brand-turquoise/10 border border-brand-turquoise text-brand-turquoise disabled:opacity-60 font-cairo font-bold text-sm flex items-center justify-center gap-2 transition-colors hover:bg-brand-turquoise/20"
          >
            {resending
              ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              : <RotateCcw className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />}
            {t('resendReport')}
          </button>
        )}

        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={exportReport}
            disabled={exporting}
            className="h-11 rounded-xl bg-muted hover:bg-muted disabled:opacity-60 text-foreground font-cairo font-bold text-sm flex items-center justify-center gap-2 transition-colors"
          >
            {exporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            {t('exportReport')}
          </button>
          <button
            onClick={() => navigate('/teacher/classes?tab=sessions')}
            className="h-11 rounded-xl bg-muted hover:bg-muted text-foreground font-cairo font-bold text-sm flex items-center justify-center gap-2 transition-colors"
          >
            <History className="h-4 w-4" />
            {t('sessionLog')}
          </button>
        </div>

        <button
          onClick={onHome}
          className="w-full h-12 rounded-xl bg-brand-turquoise text-foreground font-cairo font-bold text-base hover:opacity-90 transition-colors shadow-lg shadow-brand-turquoise/20"
        >
          {t('backToHome')}
        </button>
      </div>
    </div>
  );
}
