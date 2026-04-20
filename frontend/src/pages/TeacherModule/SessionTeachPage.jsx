import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import SectionErrorBoundary from '../../components/SectionErrorBoundary';
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
  Settings, UsersRound, User, Table2, GripVertical, Search, Mic
} from 'lucide-react';
import confetti from 'canvas-confetti';

import { useTranslation } from '../../contexts/ThemeContext';
const GENDER_COLORS = {
  male: { bg: 'bg-sky-600', ring: 'ring-sky-400', label: 'طلاب', labelKey: 'maleStudents', icon: 'M', light: 'bg-sky-900/30' },
  female: { bg: 'bg-pink-600', ring: 'ring-pink-400', label: 'طالبات', labelKey: 'femaleStudents', icon: 'F', light: 'bg-pink-900/30' },
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

const LOG_ICONS = {
  correct: CheckCircle2,
  wrong: XCircle,
  skip: Minus,
  note: StickyNote,
  behaviour: ThumbsUp,
  skill: Star,
  participation: Hand,
};

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
  const { nassaqError } = useNassaqAlert();
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
  const [selectedStudent, setSelectedStudent] = useState(null);
  const [actionTab, setActionTab] = useState('question'); // question | participation | behaviour | skill | homework | recitation
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
  const [rightPanel, setRightPanel] = useState('log');
  const [notes, setNotes] = useState([]);
  const [newNote, setNewNote] = useState('');
  const [noteType, setNoteType] = useState('session');
  const [liveMetrics, setLiveMetrics] = useState(null);
  const [evalMode, setEvalMode] = useState('individual');
  const [groups, setGroups] = useState([]);
  const [showGroupModal, setShowGroupModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showFollowupRecord, setShowFollowupRecord] = useState(false);
  const [customPositiveBehaviours, setCustomPositiveBehaviours] = useState([]);
  const [customNegativeBehaviours, setCustomNegativeBehaviours] = useState([]);
  const [customSkills, setCustomSkills] = useState([]);
  const [followupData, setFollowupData] = useState({});
  const [followupColumns, setFollowupColumns] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [showSearch, setShowSearch] = useState(false);
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
    return () => { isMounted = false; };
  }, [sessionId]);

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

  const loadStudents = async () => {
    try {
      const res = await api.get(`/session/${sessionId}/students`);
      const list = (res.data?.students || []).map(s => ({
        ...s,
        interactionCount: s.participation_count || 0,
        correctAnswers: s.correct_answers || 0,
        isFlashing: false,
      }));
      setStudents(list);
      return list;
    } catch (e) {
      console.error('Error loading students:', e);
      return [];
    }
  };

  const loadNotes = useCallback(async () => {
    if (!sessionId) return;
    try {
      const res = await api.get(`/session/${sessionId}/notes`);
      setNotes(res.data?.notes || []);
    } catch (e) { console.error('Error loading notes:', e); }
  }, [api, sessionId]);

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
  }, [sessionId, loadNotes, loadLiveMetrics]);

  const autoSaveRef = useRef(null);
  useEffect(() => {
    if (!sessionId) return;
    const saveState = () => {
      try {
        sessionStorage.setItem(`session_state_${sessionId}`, JSON.stringify({
          evalMode, groups, stats, mode: mode?.id, actionTab, followupData, followupColumns,
          customPositiveBehaviours, customNegativeBehaviours, customSkills
        }));
        if (followupColumns.length > 0 || Object.keys(followupData).length > 0) {
          api.post(`/session/${sessionId}/followup-record`, {
            columns: followupColumns, data: followupData
          }).catch(() => {});
        }
      } catch (e) { /* ignore */ }
    };
    autoSaveRef.current = setInterval(saveState, 10000);
    return () => { if (autoSaveRef.current) clearInterval(autoSaveRef.current); };
  }, [sessionId, evalMode, groups, stats, mode, actionTab, followupData, followupColumns, api, customPositiveBehaviours, customNegativeBehaviours, customSkills]);

  useEffect(() => {
    if (!sessionId) return;
    try {
      const saved = sessionStorage.getItem(`session_state_${sessionId}`);
      if (saved) {
        const state = JSON.parse(saved);
        if (state.evalMode) setEvalMode(state.evalMode);
        if (state.groups?.length) setGroups(state.groups);
        if (state.followupData && Object.keys(state.followupData).length > 0) setFollowupData(state.followupData);
        if (state.followupColumns?.length) setFollowupColumns(state.followupColumns);
        if (state.customPositiveBehaviours?.length) setCustomPositiveBehaviours(state.customPositiveBehaviours);
        if (state.customNegativeBehaviours?.length) setCustomNegativeBehaviours(state.customNegativeBehaviours);
        if (state.customSkills?.length) setCustomSkills(state.customSkills);
      }
    } catch (e) { /* ignore */ }
  }, [sessionId]);

  const [dragStudent, setDragStudent] = useState(null);

  const autoGroupByLevel = (studentsList = null) => {
    const list = studentsList || students.filter(s => s.attendance_status === 'present');
    const levels = { high: [], medium: [], low: [], unassigned: [] };
    list.forEach(s => {
      const level = s.level || s.student_level || s.academic_level;
      if (level === 'advanced' || level === 'high' || level === 'متقدم') levels.high.push(s);
      else if (level === 'intermediate' || level === 'medium' || level === 'متوسط') levels.medium.push(s);
      else if (level === 'beginner' || level === 'low' || level === 'مبتدئ') levels.low.push(s);
      else {
        const score = s.correct_answers || s.correctAnswers || 0;
        const count = s.interaction_count || s.interactionCount || 0;
        if (count >= 5 && score >= 3) levels.high.push(s);
        else if (count >= 2) levels.medium.push(s);
        else if (count > 0) levels.low.push(s);
        else levels.unassigned.push(s);
      }
    });
    const newGroups = [];
    if (levels.high.length > 0) newGroups.push({ id: 'g-high', name: t('advancedLevel'), color: 'bg-green-600', students: levels.high.map(s => s.id) });
    if (levels.medium.length > 0) newGroups.push({ id: 'g-medium', name: t('intermediateLevel'), color: 'bg-blue-600', students: levels.medium.map(s => s.id) });
    if (levels.low.length > 0) newGroups.push({ id: 'g-low', name: t('beginnerLevel'), color: 'bg-amber-600', students: levels.low.map(s => s.id) });
    if (levels.unassigned.length > 0 && newGroups.length === 0) {
      newGroups.push({ id: 'g-all', name: t('group') + ' 1', color: 'bg-slate-600', students: levels.unassigned.map(s => s.id) });
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
    { id: 'participation', name: t('participation'), maxGrade: 10, type: 'grade' },
    { id: 'homework', name: t('homework'), maxGrade: 10, type: 'grade' },
    { id: 'performance_task', name: t('performanceTask'), maxGrade: 10, type: 'grade' },
    { id: 'test', name: t('test'), maxGrade: 10, type: 'grade' },
  ];

  const loadFollowupRecord = useCallback(async () => {
    if (!sessionId) return;
    try {
      const res = await api.get(`/session/${sessionId}/followup-record`);
      setFollowupData(res.data?.data || {});
      if (res.data?.columns?.length) setFollowupColumns(res.data.columns);
      else if (followupColumns.length === 0) setFollowupColumns(defaultColumns);
    } catch (e) {
      if (followupColumns.length === 0) setFollowupColumns(defaultColumns);
    }
  }, [api, sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

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
    } catch (err) {
      clearInterval(flashRef.current);
      setFlashId(null);
      nassaqError(err.response?.data?.detail || 'خطأ في اختيار الطالب');
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

  const addLog = (emoji, text, color = 'text-gray-700') => {
    setActivityLog(prev => [{ id: Date.now(), emoji, text, color, time: new Date().toLocaleTimeString('ar', { hour: '2-digit', minute: '2-digit' }) }, ...prev].slice(0, 30));
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
      const res = await api.post(`/session/${sessionId}/participation`, {
        student_id: selectedStudent.id,
        type: pType.id,
      });
      const change = res.data?.score_change || 0;
      toast.success(`${t(pType.labelKey)} — ${selectedStudent.full_name?.split(' ')[0]}`);
      addLog('participation', `${selectedStudent.full_name?.split(' ')[0]} — ${t(pType.labelKey)} (${change > 0 ? '+' : ''}${change})`, change >= 0 ? 'text-blue-700' : 'text-amber-700');
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
      toast.success(`${t('behaviour')}: ${bType.label || t(bType.labelKey)} — ${selectedStudent.full_name?.split(' ')[0]}`);
      addLog('behaviour', `${selectedStudent.full_name?.split(' ')[0]} — ${bType.label || t(bType.labelKey)} (${change > 0 ? '+' : ''}${change})`, behaviourCategory === 'negative' ? 'text-red-600' : 'text-purple-700');
      setBehaviourNote('');
    } catch (e) {
      console.error('Error recording behaviour:', e);
      nassaqError(t('errorRecordingBehaviour'));
    }
  };

  const recordSkill = async (skill) => {
    if (!selectedStudent) return;
    const isCustom = String(skill.id).startsWith('custom_');
    try {
      if (isCustom) {
        await api.post(`/session/${sessionId}/note`, {
          student_id: selectedStudent.id,
          content: `${t('skill')}: ${skill.name_ar || skill.name}${skillNote ? ' - ' + skillNote : ''}`,
          type: 'skill',
        });
      } else {
        await api.post(`/session/${sessionId}/skill`, {
          student_id: selectedStudent.id,
          skill_type_id: skill.id,
          notes: skillNote || null,
        });
      }
      confetti({ particleCount: 50, spread: 60, origin: { y: 0.6 }, colors: ['#8b5cf6', '#a78bfa', '#c4b5fd'] });
      toast.success(`${t('skill')}: ${skill.name_ar || skill.name} — ${selectedStudent.full_name?.split(' ')[0]}`);
      addLog('skill', `${selectedStudent.full_name?.split(' ')[0]} — ${skill.name_ar || skill.name}`, 'text-purple-700');
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
      console.error('Error recording skill:', e);
      nassaqError(t('errorRecordingSkill'));
    }
  };

  const recordRecitation = async (mastered) => {
    if (!selectedStudent) return;
    try {
      const label = mastered ? t('recitationMastered') : t('recitationNotMastered');
      const noteSuffix = recitationNote ? ` - ${recitationNote}` : '';
      await api.post(`/session/${sessionId}/note`, {
        student_id: selectedStudent.id,
        content: `${t('recitation')}: ${label} (${t('attempts')}: ${recitationAttempts})${noteSuffix}`,
        type: 'recitation',
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

  const [pendingOps, setPendingOps] = useState([]);

  const checkPendingOps = useCallback(() => {
    const ops = [];
    const hasAttendance = sessionInfo?.attendance_approved || sessionInfo?.attendanceApproved;
    if (!hasAttendance) {
      ops.push({ id: 'attendance', label: 'لم يتم اعتماد الحضور', severity: 'error' });
    }
    if (stats.questions === 0 && stats.participation === 0) {
      ops.push({ id: 'no_interaction', label: 'لا توجد تفاعلات مسجلة', severity: 'warning' });
    }
    return ops;
  }, [sessionInfo, stats]);

  const startEndReview = async () => {
    const ops = checkPendingOps();
    setPendingOps(ops);
    setReviewLoading(true);
    try {
      const res = await api.get(`/session/${sessionId}/review-preview`);
      setReviewData(res.data);
      setShowEndDialog(false);
    } catch (err) {
      nassaqError(err.response?.data?.detail || 'خطأ في تحميل ملخص الحصة');
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
      const detail = err.response?.data?.detail || '';
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
    <div className="h-screen bg-slate-900 flex flex-col overflow-hidden" dir={isRTL ? 'rtl' : 'ltr'}>
      {/* ── Header ── */}
      <header className="bg-brand-navy border-b border-white/10 px-4 py-3 flex-none shrink-0">
        <div className="max-w-5xl mx-auto flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="hidden sm:flex items-center gap-1.5 bg-white/10 rounded-lg px-3 py-1.5">
              <Clock className="h-4 w-4 text-brand-turquoise" />
              <span className="font-mono text-white text-sm font-bold">{timer}</span>
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="font-cairo font-bold text-white text-sm sm:text-base truncate">
                  {sessionInfo?.subject_name || sessionInfo?.subjectName}
                </h1>
                {mode && (
                  <span className="hidden sm:inline-flex items-center gap-1 bg-green-500/20 text-green-400 text-[10px] px-2 py-0.5 rounded-full border border-green-500/30 animate-pulse">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
                    {t('teachingNow')}
                  </span>
                )}
              </div>
              <p className="text-white/60 text-xs truncate">{sessionInfo?.class_name || sessionInfo?.className}</p>
            </div>
          </div>

          {/* Live stats bar */}
          <div className="hidden md:flex items-center gap-4 text-xs text-white/70">
            <span className="flex items-center gap-1">
              <Users className="h-3.5 w-3.5" /> {presentStudents.length} {t('present')}
            </span>
            <span className="flex items-center gap-1">
              <Activity className="h-3.5 w-3.5" /> {stats.questions} {t('question')}
            </span>
            <span className={`flex items-center gap-1 ${accuracy >= 60 ? 'text-green-400' : 'text-red-400'}`}>
              <BarChart2 className="h-3.5 w-3.5" /> {accuracy}% {t('correct')}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSearch(v => !v)}
              className="p-1.5 rounded-lg bg-white/10 text-white/60 hover:bg-white/20 transition-colors"
              title={t('search')}
            >
              <Search className="h-3.5 w-3.5" />
            </button>

            <div className="hidden sm:flex items-center bg-white/10 rounded-lg p-0.5">
              <button
                onClick={() => setEvalMode('individual')}
                className={`flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium transition-colors ${
                  evalMode === 'individual' ? 'bg-brand-turquoise text-white' : 'text-white/50 hover:text-white/80'
                }`}
              >
                <User className="h-3 w-3" />
                {t('individual')}
              </button>
              <button
                onClick={() => setEvalMode('group')}
                className={`flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium transition-colors ${
                  evalMode === 'group' ? 'bg-brand-turquoise text-white' : 'text-white/50 hover:text-white/80'
                }`}
              >
                <UsersRound className="h-3 w-3" />
                {t('groups')}
              </button>
            </div>

            {evalMode === 'group' && (
              <button
                onClick={() => setShowGroupModal(true)}
                className="p-1.5 rounded-lg bg-purple-600/30 text-purple-300 hover:bg-purple-600/50 transition-colors border border-purple-500/30"
                title={t('manageGroups')}
              >
                <Settings className="h-3.5 w-3.5" />
              </button>
            )}

            <div className="flex gap-1">
              {MODES.map(m => (
                <button
                  key={m.id}
                  onClick={() => handleSetMode(m)}
                  className={`hidden sm:flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors ${
                    mode?.id === m.id ? `${m.color} text-white` : 'bg-white/10 text-white/60 hover:bg-white/20'
                  }`}
                >
                  <m.icon className="h-3 w-3" />
                  {m.label}
                </button>
              ))}
            </div>
            <button
              onClick={() => setShowSettingsModal(true)}
              className="p-1.5 rounded-lg bg-white/10 text-white/60 hover:bg-white/20 transition-colors"
              title={t('evaluationSettings')}
            >
              <Settings className="h-3.5 w-3.5" />
            </button>
            <Button
              size="sm"
              variant="destructive"
              className="text-xs h-8"
              onClick={() => setShowEndDialog(true)}
              disabled={reviewLoading}
            >
              {reviewLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : t('endSession')}
            </Button>
          </div>
        </div>
      </header>

      {timeWarning && (
        <div className={`flex-none px-4 py-2 text-center text-sm font-cairo font-bold flex items-center justify-center gap-2 ${
          timeWarning === 'ended' ? 'bg-red-600/90 text-white animate-pulse' : 'bg-amber-500/90 text-white'
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

      {/* ── Main layout: left = console, right = log ── */}
      <div className="flex-1 min-h-0 flex overflow-hidden max-w-5xl w-full mx-auto">

        {/* ── Console (left 2/3) ── */}
        <div className="flex-1 flex flex-col overflow-hidden p-3 gap-3 min-h-0">

          {/* Search bar */}
          {showSearch && (
            <div className="flex-none">
              <div className="relative">
                <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/40" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  placeholder={t('searchStudentByName')}
                  className="w-full bg-white/10 text-white text-sm rounded-xl ps-10 pe-4 py-2.5 placeholder-white/30 outline-none border border-white/10 focus:border-brand-turquoise/50 transition-colors"
                  autoFocus
                />
                {searchQuery && (
                  <button onClick={() => setSearchQuery('')} className="absolute end-3 top-1/2 -translate-y-1/2 text-white/40 hover:text-white">
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
                <Sparkles className="h-5 w-5 text-white" />
              </div>
              <div className="flex-1">
                <p className="text-brand-turquoise text-xs font-bold font-cairo">حكيم يختار...</p>
                <p className="text-white/50 text-[10px]">جارٍ البحث عن الطالب الأنسب للمشاركة</p>
              </div>
              <Loader2 className="h-4 w-4 animate-spin text-brand-turquoise" />
            </div>
          )}

          {/* Random student button */}
          <button
            onClick={selectRandom}
            disabled={loading}
            className={`flex-none w-full h-14 rounded-xl font-cairo font-bold text-white text-base flex items-center justify-center gap-2 shadow-lg hover:opacity-90 active:scale-95 transition-colors disabled:opacity-60 ${
              selectedStudent
                ? 'bg-gradient-to-r from-amber-500 to-orange-600'
                : 'bg-gradient-to-r from-brand-turquoise to-brand-navy'
            }`}
          >
            {loading ? (
              <><Loader2 className="h-5 w-5 animate-spin" /> حكيم يختار...</>
            ) : selectedStudent ? (
              <><Shuffle className="h-5 w-5" /> اختيار عشوائي آخر</>
            ) : (
              <><Shuffle className="h-5 w-5" /> {t('randomStudentPick')}</>
            )}
          </button>

          {/* Mode selector (mobile) */}
          <div className="sm:hidden grid grid-cols-3 gap-2">
            {MODES.map(m => (
              <button key={m.id} onClick={() => handleSetMode(m)}
                className={`rounded-lg py-2 text-xs font-medium flex flex-col items-center gap-1 transition-colors ${
                  mode?.id === m.id ? `${m.color} text-white ring-2 ring-white/30` : 'bg-white/10 text-white/60'
                }`}>
                <m.icon className="h-4 w-4" />
                {m.label}
              </button>
            ))}
          </div>

          {mode && (
            <div className={`flex items-center gap-2 px-3 py-2 rounded-lg mx-2 mb-2 border ${
              mode.id === 'review' ? 'bg-purple-900/30 border-purple-500/30' :
              mode.id === 'homework' ? 'bg-blue-900/30 border-blue-500/30' :
              'bg-amber-900/30 border-amber-500/30'
            }`}>
              <mode.icon className={`h-4 w-4 ${
                mode.id === 'review' ? 'text-purple-400' :
                mode.id === 'homework' ? 'text-blue-400' : 'text-amber-400'
              }`} />
              <div className="flex-1">
                <span className={`text-xs font-bold ${
                  mode.id === 'review' ? 'text-purple-300' :
                  mode.id === 'homework' ? 'text-blue-300' : 'text-amber-300'
                }`}>
                  {mode.id === 'review' ? t('reviewModeDesc') :
                   mode.id === 'homework' ? t('homeworkModeDesc') :
                   t('quizModeDesc')}
                </span>
              </div>
              <span className={`w-2 h-2 rounded-full animate-pulse ${
                mode.id === 'review' ? 'bg-purple-400' :
                mode.id === 'homework' ? 'bg-blue-400' : 'bg-amber-400'
              }`} />
            </div>
          )}

          {/* Student grid — individual or group mode */}
          <div className={`overflow-y-auto min-h-0 ${selectedStudent ? 'flex-none shrink-0 max-h-[22vh]' : 'flex-1'}`}>
            {!mode ? (
              <div className="h-full flex items-center justify-center text-white/40 text-sm">
                {t('selectSessionModeToStart')}
              </div>
            ) : evalMode === 'group' ? (
              groups.length > 0 ? (
              <div className="space-y-3">
                {groups.map(group => {
                  const groupStudents = filteredStudents.filter(s => group.students?.includes(s.id));
                  if (groupStudents.length === 0) return null;
                  return (
                    <div key={group.id}>
                      <div className="flex items-center gap-2 mb-2">
                        <span className={`w-3 h-3 rounded-full ${group.color}`} />
                        <span className="text-white/70 text-xs font-medium font-cairo">{group.name} ({groupStudents.length})</span>
                        <div className="flex-1 h-px bg-white/10" />
                      </div>
                      <div className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 gap-2">
                        {groupStudents.map((student) => (
                          <StudentCard
                            key={student.id}
                            student={student}
                            isFlashing={flashId === student.id}
                            isSelected={selectedStudent?.id === student.id}
                            onClick={() => handleStudentClick(student)}
                          />
                        ))}
                      </div>
                    </div>
                  );
                })}
                {unassignedStudents.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="w-3 h-3 rounded-full bg-slate-500" />
                      <span className="text-white/50 text-xs font-medium font-cairo">{t('unassigned')} ({unassignedStudents.length})</span>
                      <div className="flex-1 h-px bg-white/10" />
                    </div>
                    <div className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 gap-2">
                      {unassignedStudents.map((student) => (
                        <StudentCard
                          key={student.id}
                          student={student}
                          isFlashing={flashId === student.id}
                          isSelected={selectedStudent?.id === student.id}
                          onClick={() => handleStudentClick(student)}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </div>
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-white/40 text-sm gap-3 py-8">
                  <UsersRound className="h-10 w-10 text-white/20" />
                  <p className="font-cairo">{t('noGroupsCreated')}</p>
                  <button
                    onClick={() => setShowGroupModal(true)}
                    className="px-4 py-2 rounded-xl bg-purple-600/20 text-purple-400 text-sm font-medium hover:bg-purple-600/30 transition-colors border border-purple-500/30 flex items-center gap-2"
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
                  return (
                    <div key={group.key}>
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-sm">{gc.icon}</span>
                        <span className="text-white/50 text-xs font-medium">{gc.label} ({group.students.length})</span>
                        <div className="flex-1 h-px bg-white/10" />
                      </div>
                      <div className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 gap-2">
                        {group.students.map((student) => (
                          <StudentCard
                            key={student.id}
                            student={student}
                            isFlashing={flashId === student.id}
                            isSelected={selectedStudent?.id === student.id}
                            onClick={() => handleStudentClick(student)}
                          />
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="grid grid-cols-4 sm:grid-cols-5 md:grid-cols-6 gap-2">
                {filteredStudents.map((student) => (
                  <StudentCard
                    key={student.id}
                    student={student}
                    isFlashing={flashId === student.id}
                    isSelected={selectedStudent?.id === student.id}
                    onClick={() => handleStudentClick(student)}
                  />
                ))}
              </div>
            )}
          </div>

          {/* ── Action Panel ── */}
          {selectedStudent && (
            <div className="flex-1 min-h-0 flex flex-col bg-slate-800 rounded-xl border border-white/10 overflow-hidden">
              {/* Selected student header — enhanced per spec */}
              <div className="px-4 py-3 border-b border-white/10">
                <div className="flex items-center gap-3">
                  <Avatar className="h-12 w-12 ring-2 ring-brand-turquoise ring-offset-2 ring-offset-slate-800">
                    <AvatarImage src={selectedStudent.avatar_url} />
                    <AvatarFallback className={`${selectedStudent.gender === 'female' ? 'bg-gradient-to-br from-pink-500 to-rose-600' : 'bg-gradient-to-br from-sky-500 to-blue-600'} text-white text-sm font-bold`}>
                      {selectedStudent.full_name?.charAt(0)}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex-1 min-w-0">
                    <p className="text-white font-cairo font-bold text-sm truncate">{selectedStudent.full_name}</p>
                    <p className="text-white/40 text-[10px]">{selectedStudent.student_code || sessionInfo?.class_name || sessionInfo?.className}</p>
                  </div>
                  <button
                    onClick={() => { setSelectedStudent(null); setFlashId(null); }}
                    className="text-white/40 hover:text-white/80 p-1"
                  >
                    <XCircle className="h-5 w-5" />
                  </button>
                </div>
                <div className="flex items-center gap-3 mt-2">
                  <div className="flex-1 bg-white/5 rounded-lg px-2 py-1 text-center">
                    <div className="text-blue-400 text-xs font-bold">{selectedStudent.participation_count || selectedStudent.interactionCount || 0}</div>
                    <div className="text-white/30 text-[9px]">{t('participations')}</div>
                  </div>
                  <div className="flex-1 bg-white/5 rounded-lg px-2 py-1 text-center">
                    <div className="text-green-400 text-xs font-bold">{selectedStudent.correct_answers || selectedStudent.correctAnswers || 0}</div>
                    <div className="text-white/30 text-[9px]">{t('correct')}</div>
                  </div>
                  <div className="flex-1 bg-white/5 rounded-lg px-2 py-1 text-center">
                    <div className="text-purple-400 text-xs font-bold">{selectedStudent.interaction_count || selectedStudent.interactionCount || 0}</div>
                    <div className="text-white/30 text-[9px]">{t('interaction')}</div>
                  </div>
                </div>
              </div>

              {/* Tabs */}
              <div className="flex border-b border-white/10">
                {[
                  { id: 'question', labelKey: 'question', icon: MessageCircle, forMode: 'quiz' },
                  { id: 'participation', labelKey: 'participationTab', icon: Hand, forMode: 'review' },
                  { id: 'homework', labelKey: 'modeHomework', icon: ClipboardCheck, forMode: 'homework' },
                  { id: 'recitation', labelKey: 'recitationTab', icon: Mic },
                  { id: 'behaviour', labelKey: 'behaviour', icon: ThumbsUp },
                  { id: 'skill', labelKey: 'skill', icon: Star },
                ].map(tab => {
                  const isRecommended = tab.forMode && mode?.id === tab.forMode;
                  return (
                  <button
                    key={tab.id}
                    onClick={() => setActionTab(tab.id)}
                    className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-medium transition-colors relative ${
                      actionTab === tab.id ? 'text-brand-turquoise border-b-2 border-brand-turquoise' : 'text-white/50 hover:text-white/80'
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
              <div className="p-3 h-[calc(100vh-250px)] overflow-y-auto scrollbar-thin">
                {actionTab === 'question' && (
                  <div className="grid grid-cols-3 gap-2">
                    <ActionButton
                      color="bg-green-600 hover:bg-green-500"
                      icon={<CheckCircle2 className="h-5 w-5" />}
                      label="صحيح"
                      sub="+5"
                      onClick={() => recordAnswer('correct')}
                    />
                    <ActionButton
                      color="bg-red-600 hover:bg-red-500"
                      icon={<XCircle className="h-5 w-5" />}
                      label="خطأ"
                      sub="0"
                      onClick={() => recordAnswer('wrong')}
                    />
                    <ActionButton
                      color="bg-slate-600 hover:bg-slate-500"
                      icon={<Minus className="h-5 w-5" />}
                      label="لم يجب"
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
                        label={p.label}
                        sub={p.score}
                        onClick={() => recordParticipation(p)}
                      />
                    ))}
                  </div>
                )}

                {actionTab === 'homework' && (
                  <div className="space-y-2">
                    {homeworkLoading ? (
                      <div className="flex items-center justify-center py-6">
                        <Loader2 className="h-6 w-6 animate-spin text-blue-400" />
                      </div>
                    ) : <>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-white/60 text-xs font-cairo">{t('homeworkMarkNotSubmitted')}</span>
                      <span className="text-blue-400 text-xs font-bold font-cairo">
                        {Object.values(homeworkStatuses).filter(s => s === 'done').length}/{students.filter(s => s.attendance_status === 'present').length} {t('submitted')}
                      </span>
                    </div>
                    <div className="space-y-1.5 pr-1">
                      {students.filter(s => s.attendance_status === 'present').map(student => {
                        const isDone = homeworkStatuses[student.id] !== 'not_done';
                        return (
                          <button
                            key={student.id}
                            onClick={() => toggleHomework(student.id)}
                            className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg transition-colors active:scale-[0.97] ${
                              isDone
                                ? 'bg-green-600/20 border border-green-500/30'
                                : 'bg-white/5 border border-white/10 hover:border-white/20'
                            }`}
                          >
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold shrink-0 ${
                              isDone ? 'bg-green-600 text-white' : 'bg-white/10 text-white/40'
                            }`}>
                              {isDone ? <CheckCircle2 className="h-4 w-4 text-green-400" /> : <XCircle className="h-4 w-4 text-red-400" />}
                            </div>
                            <span className={`flex-1 text-start text-sm font-cairo truncate ${
                              isDone ? 'text-white' : 'text-white/50 line-through'
                            }`}>
                              {student.full_name || 'طالب'}
                            </span>
                            <span className={`text-xs font-bold font-cairo px-2 py-0.5 rounded-full ${
                              isDone
                                ? 'bg-green-500/20 text-green-400'
                                : 'bg-red-500/20 text-red-400'
                            }`}>
                              {isDone ? 'حل' : 'ما حل'}
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
                      <div className="text-white/60 text-[11px] mb-1.5 font-cairo">{t('attempts')}</div>
                      <div className="grid grid-cols-3 gap-1.5">
                        {[1, 2, 3].map(n => (
                          <button
                            key={n}
                            onClick={() => setRecitationAttempts(n)}
                            className={`py-1.5 rounded text-xs font-bold font-cairo transition-colors ${
                              recitationAttempts === n
                                ? 'bg-emerald-600 text-white'
                                : 'bg-white/10 text-white/60 hover:bg-white/15'
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
                      className="w-full bg-white/10 text-white text-xs rounded px-2 py-1.5 placeholder-white/30 outline-none font-cairo"
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
                          className={`flex-1 py-1.5 rounded text-xs font-medium text-white transition-colors ${
                            behaviourCategory === cat.id ? cat.color : 'bg-white/10 text-white/60'
                          }`}
                        >
                          <span className="flex items-center justify-center gap-1"><cat.icon className="h-3 w-3" />{t(cat.labelKey)}</span>
                        </button>
                      ))}
                    </div>
                    <div className="grid grid-cols-3 gap-1.5">
                      {[
                        ...(BEHAVIOURS[behaviourCategory] || []),
                        ...(behaviourCategory === 'positive' ? customPositiveBehaviours : customNegativeBehaviours).map(name => ({
                          id: `custom_${name}`,
                          label: name,
                          points: behaviourCategory === 'positive' ? '+2' : '-2'
                        }))
                      ].map(b => (
                        <button
                          key={b.id}
                          onClick={() => recordBehaviour(b)}
                          className="bg-white/10 hover:bg-white/20 text-white rounded-lg py-2 px-1 text-xs text-center transition-colors"
                        >
                          <div className="font-medium truncate">{b.label}</div>
                          <div className={`text-[10px] mt-0.5 ${b.points.startsWith('-') ? 'text-red-400' : 'text-green-400'}`}>{b.points}</div>
                        </button>
                      ))}
                    </div>
                    <input
                      className="w-full bg-white/10 text-white text-xs rounded px-2 py-1.5 placeholder-white/30 outline-none"
                      placeholder="ملاحظة اختيارية..."
                      value={behaviourNote}
                      onChange={e => setBehaviourNote(e.target.value)}
                    />
                  </div>
                )}

                {actionTab === 'skill' && (
                  <div className="space-y-2">
                    <div className="grid grid-cols-3 gap-1.5">
                      {[
                        ...skillTypes,
                        ...customSkills.map(name => ({ id: `custom_${name}`, name, name_ar: name }))
                      ].map(skill => (
                        <button
                          key={skill.id}
                          onClick={() => recordSkill(skill)}
                          className="bg-purple-900/40 hover:bg-purple-800/60 text-white rounded-lg py-2 px-1 text-xs text-center transition-colors border border-purple-500/20"
                        >
                          <div className="font-medium truncate">{skill.name_ar || skill.name}</div>
                          <div className="text-[10px] mt-0.5 text-purple-300">+3</div>
                        </button>
                      ))}
                    </div>
                    {skillTypes.length === 0 && customSkills.length === 0 && (
                      <p className="text-white/40 text-xs text-center py-2">{t('noSkillsRegistered')}</p>
                    )}
                    <input
                      className="w-full bg-white/10 text-white text-xs rounded px-2 py-1.5 placeholder-white/30 outline-none"
                      placeholder="ملاحظة اختيارية..."
                      value={skillNote}
                      onChange={e => setSkillNote(e.target.value)}
                    />
                  </div>
                )}

                {/* Hardcoded physical spacer to guarantee footer never overlaps content */}
                <div style={{ minHeight: '100px', flexShrink: 0, width: '100%' }} aria-hidden="true"></div>
              </div>
            </div>
          )}
        </div>

        {/* ── Right Panel (Activity Log + Notes, desktop only) ── */}
        <div className="hidden lg:flex flex-col w-72 border-r border-white/10 bg-slate-800/50 overflow-hidden">
          <div className="flex border-b border-white/10">
            {[
              { id: 'log', labelKey: 'activityLog', icon: Activity },
              { id: 'notes', labelKey: 'notes', icon: StickyNote },
              { id: 'metrics', labelKey: 'metrics', icon: BarChart2 },
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setRightPanel(tab.id)}
                className={`flex-1 flex items-center justify-center gap-1 py-2.5 text-xs font-medium transition-colors ${
                  rightPanel === tab.id ? 'text-brand-turquoise border-b-2 border-brand-turquoise' : 'text-white/50 hover:text-white/80'
                }`}
              >
                <tab.icon className="h-3.5 w-3.5" />
                {t(tab.labelKey)}
                {tab.id === 'notes' && notes.length > 0 && (
                  <span className="bg-amber-500 text-white text-[9px] rounded-full w-4 h-4 flex items-center justify-center">{notes.length}</span>
                )}
              </button>
            ))}
          </div>

          {rightPanel === 'log' && (
            <>
              <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
                {activityLog.length === 0 ? (
                  <p className="text-white/30 text-xs text-center mt-4">لا يوجد نشاط بعد</p>
                ) : (
                  activityLog.map(log => (
                    <div key={log.id} className="bg-white/5 rounded-lg px-2.5 py-2">
                      <p className={`text-xs font-medium ${log.color} flex items-center gap-1`}>
                        {(() => {
                          const IconComp = LOG_ICONS[log.emoji];
                          return IconComp ? <IconComp className="h-3 w-3 inline-block flex-shrink-0" /> : <span>{log.emoji}</span>;
                        })()}
                        <span>{log.text}</span>
                      </p>
                      <p className="text-white/30 text-[10px] mt-0.5">{log.time}</p>
                    </div>
                  ))
                )}
              </div>
              <div className="border-t border-white/10 p-3 space-y-2">
                <div className="flex justify-between text-xs text-white/50">
                  <span>{t('questions')}</span><span className="text-white font-bold">{stats.questions}</span>
                </div>
                <div className="flex justify-between text-xs text-white/50">
                  <span>{t('correct')}</span><span className="text-green-400 font-bold">{stats.correct}</span>
                </div>
                <div className="flex justify-between text-xs text-white/50">
                  <span>{t('accuracy')}</span>
                  <span className={`font-bold ${accuracy >= 60 ? 'text-green-400' : 'text-red-400'}`}>{accuracy}%</span>
                </div>
                <div className="flex justify-between text-xs text-white/50">
                  <span>{t('interaction')}</span><span className="text-blue-400 font-bold">{stats.participation}</span>
                </div>
              </div>
            </>
          )}

          {rightPanel === 'notes' && (
            <>
              <div className="flex-1 overflow-y-auto p-2 space-y-2">
                {notes.length === 0 ? (
                  <p className="text-white/30 text-xs text-center mt-4">لا توجد ملاحظات</p>
                ) : (
                  notes.map(note => (
                    <div key={note.id} className="bg-amber-900/20 border border-amber-500/20 rounded-lg px-3 py-2">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-white/90 text-xs leading-relaxed flex-1">{note.text}</p>
                        <button onClick={() => deleteNote(note.id)} className="text-white/30 hover:text-red-400 flex-shrink-0">
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                      <div className="flex items-center gap-2 mt-1.5">
                        <Badge className="bg-amber-500/20 text-amber-300 text-[9px] px-1.5 py-0">
                          {note.note_type === 'student' ? 'طالب' : note.note_type === 'behavioural' ? 'سلوكية' : note.note_type === 'educational' ? 'تعليمية' : note.note_type === 'followup' ? 'متابعة' : 'عامة'}
                        </Badge>
                        {note.student_name && (
                          <span className="text-white/40 text-[10px]">{note.student_name}</span>
                        )}
                        <span className="text-white/30 text-[10px] mr-auto">
                          {new Date(note.created_at).toLocaleTimeString('ar', { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>
              <div className="border-t border-white/10 p-2 space-y-2">
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
                        noteType === nt.id ? 'bg-amber-600 text-white' : 'bg-white/10 text-white/50'
                      }`}
                    >
                      {t(nt.labelKey)}
                    </button>
                  ))}
                </div>
                {selectedStudent && noteType === 'student' && (
                  <div className="bg-white/5 rounded px-2 py-1 text-[10px] text-brand-turquoise flex items-center gap-1">
                    <UserCheck className="h-3 w-3" />
                    {selectedStudent.full_name}
                  </div>
                )}
                <div className="flex gap-1.5">
                  <input
                    className="flex-1 bg-white/10 text-white text-xs rounded px-2 py-1.5 placeholder-white/30 outline-none"
                    placeholder="اكتب ملاحظة..."
                    value={newNote}
                    onChange={e => setNewNote(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && addNote()}
                  />
                  <button
                    onClick={addNote}
                    disabled={!newNote.trim()}
                    className="bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-white rounded px-2 py-1.5 transition-colors"
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
                  <div className="bg-white/5 rounded-lg p-3 space-y-2">
                    <h4 className="text-white/60 text-[10px] font-medium uppercase tracking-wider">الحضور</h4>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="text-center">
                        <div className="text-green-400 text-lg font-bold">{liveMetrics.attendance?.present || 0}</div>
                        <div className="text-white/40 text-[10px]">حاضر</div>
                      </div>
                      <div className="text-center">
                        <div className="text-red-400 text-lg font-bold">{liveMetrics.attendance?.absent || 0}</div>
                        <div className="text-white/40 text-[10px]">غائب</div>
                      </div>
                    </div>
                    <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                      <div className="h-full bg-green-500 transition-colors" style={{ width: `${liveMetrics.attendance?.rate || 0}%` }} />
                    </div>
                    <div className="text-center text-white/50 text-[10px]">{liveMetrics.attendance?.rate || 0}% {t('present')}</div>
                  </div>

                  <div className="bg-white/5 rounded-lg p-3 space-y-2">
                    <h4 className="text-white/60 text-[10px] font-medium uppercase tracking-wider">{t('interaction')}</h4>
                    <div className="grid grid-cols-3 gap-2 text-center">
                      <div>
                        <div className="text-blue-400 text-lg font-bold">{liveMetrics.interaction?.total_questions || 0}</div>
                        <div className="text-white/40 text-[10px]">{t('questions')}</div>
                      </div>
                      <div>
                        <div className="text-green-400 text-lg font-bold">{liveMetrics.interaction?.correct_answers || 0}</div>
                        <div className="text-white/40 text-[10px]">{t('correct')}</div>
                      </div>
                      <div>
                        <div className="text-red-400 text-lg font-bold">{liveMetrics.interaction?.wrong_answers || 0}</div>
                        <div className="text-white/40 text-[10px]">{t('error')}</div>
                      </div>
                    </div>
                    <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                      <div className="h-full bg-blue-500 transition-colors" style={{ width: `${liveMetrics.interaction?.accuracy_rate || 0}%` }} />
                    </div>
                    <div className="text-center text-white/50 text-[10px]">{liveMetrics.interaction?.accuracy_rate || 0}% {t('accuracy')}</div>
                  </div>

                  <div className="bg-white/5 rounded-lg p-3 space-y-2">
                    <h4 className="text-white/60 text-[10px] font-medium uppercase tracking-wider">{t('participationLabel')}</h4>
                    <div className="grid grid-cols-2 gap-2 text-center">
                      <div>
                        <div className="text-purple-400 text-lg font-bold">{liveMetrics.interaction?.unique_participants || 0}</div>
                        <div className="text-white/40 text-[10px]">{t('participant')}</div>
                      </div>
                      <div>
                        <div className="text-amber-400 text-lg font-bold">{liveMetrics.interaction?.not_interacted || 0}</div>
                        <div className="text-white/40 text-[10px]">لم يتفاعل</div>
                      </div>
                    </div>
                    <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                      <div className="h-full bg-purple-500 transition-colors" style={{ width: `${liveMetrics.interaction?.participation_rate || 0}%` }} />
                    </div>
                  </div>

                  <div className="bg-white/5 rounded-lg p-3 space-y-2">
                    <h4 className="text-white/60 text-[10px] font-medium uppercase tracking-wider">السلوك والمهارات</h4>
                    <div className="grid grid-cols-3 gap-2 text-center">
                      <div>
                        <div className="text-green-400 text-base font-bold">{liveMetrics.behaviour?.positive || 0}</div>
                        <div className="text-white/40 text-[10px]">إيجابي</div>
                      </div>
                      <div>
                        <div className="text-red-400 text-base font-bold">{liveMetrics.behaviour?.negative || 0}</div>
                        <div className="text-white/40 text-[10px]">سلبي</div>
                      </div>
                      <div>
                        <div className="text-purple-400 text-base font-bold">{liveMetrics.skills_recorded || 0}</div>
                        <div className="text-white/40 text-[10px]">مهارات</div>
                      </div>
                    </div>
                  </div>

                  <div className="text-center text-white/30 text-[10px] mt-2">
                    <Clock className="h-3 w-3 inline-block" /> {liveMetrics.duration_minutes || 0} {t('minutes')} | <StickyNote className="h-3 w-3 inline-block" /> {liveMetrics.notes_count || 0} {t('notes')}
                  </div>
                </>
              ) : (
                <div className="flex items-center justify-center h-full">
                  <Loader2 className="h-5 w-5 animate-spin text-white/30" />
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Follow-up record bottom bar */}
      <div className="fixed bottom-0 w-full z-50 bg-slate-800 border-t border-white/10 px-4 py-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowFollowupRecord(true)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-brand-turquoise/20 text-brand-turquoise text-xs font-medium hover:bg-brand-turquoise/30 transition-colors border border-brand-turquoise/30"
          >
            <Table2 className="h-3.5 w-3.5" />
            {t('followupRecord')}
          </button>
          {evalMode === 'group' && groups.length > 0 && (
            <span className="text-white/40 text-[10px]">
              {groups.length} {t('groups')} | {unassignedStudents.length} {t('unassigned')}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 text-white/30 text-[10px]">
          <span className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
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
                    op.severity === 'error' ? 'bg-red-100 text-red-700 border border-red-200' : 'bg-amber-100 text-amber-700 border border-amber-200'
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
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-purple-600/20 text-purple-400 text-sm font-medium hover:bg-purple-600/30 transition-colors border border-purple-500/30"
            >
              <Zap className="h-4 w-4" />
              {t('autoGroupByLevel')}
            </button>

            {groups.map((group, gi) => (
              <div
                key={group.id}
                className={`bg-slate-100 dark:bg-slate-800 rounded-xl p-3 space-y-2 ${dragStudent ? 'border-2 border-dashed border-transparent hover:border-brand-turquoise' : ''}`}
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
                    className="p-1 text-red-400 hover:text-red-500"
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
                        className="inline-flex items-center gap-1 bg-white dark:bg-slate-700 px-2 py-1 rounded-lg text-[11px] cursor-grab active:cursor-grabbing"
                      >
                        <GripVertical className="h-3 w-3 text-muted-foreground flex-none" />
                        {st.full_name?.split(' ').slice(0, 2).join(' ')}
                        <button
                          onClick={() => {
                            const updated = [...groups];
                            updated[gi] = { ...updated[gi], students: updated[gi].students.filter(id => id !== sid) };
                            setGroups(updated);
                          }}
                          className="text-red-400 hover:text-red-500"
                        >
                          <XCircle className="h-3 w-3" />
                        </button>
                      </span>
                    );
                  })}
                </div>
                <select
                  className="w-full text-xs p-1.5 rounded-lg border bg-white dark:bg-slate-700 dark:border-slate-600"
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
                <div className="bg-slate-200/50 dark:bg-slate-700/30 rounded-xl p-3 space-y-2 border border-dashed border-slate-400/30">
                  <div className="text-xs font-medium text-muted-foreground">{t('unassignedStudents')} ({unassigned.length})</div>
                  <div className="flex flex-wrap gap-1.5">
                    {unassigned.map(s => (
                      <span
                        key={s.id}
                        draggable
                        onDragStart={() => handleDragStart(s.id)}
                        onDragEnd={() => setDragStudent(null)}
                        className="inline-flex items-center gap-1 bg-white dark:bg-slate-600 px-2 py-1 rounded-lg text-[11px] cursor-grab active:cursor-grabbing"
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
              className="w-full flex items-center justify-center gap-2 py-2 rounded-xl border-2 border-dashed border-slate-300 dark:border-slate-600 text-muted-foreground text-sm hover:border-brand-turquoise hover:text-brand-turquoise transition-colors"
            >
              <Plus className="h-4 w-4" />
              {t('addNewGroup')}
            </button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Evaluation Settings Modal */}
      <Dialog open={showSettingsModal} onOpenChange={(open) => {
        setShowSettingsModal(open);
        if (!open && sessionId && (followupColumns.length > 0 || Object.keys(followupData).length > 0)) {
          api.post(`/session/${sessionId}/followup-record`, {
            columns: followupColumns, data: followupData
          }).catch(() => {});
        }
      }}>
        <DialogContent className="max-w-md max-h-[80vh] overflow-y-auto" dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader>
            <DialogTitle className="font-cairo flex items-center gap-2">
              <Settings className="h-5 w-5 text-brand-turquoise" />
              {t('evaluationSettings')}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-5">
            <div className="space-y-2">
              <label className="text-sm font-medium">{t('evaluationMode')}</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => setEvalMode('individual')}
                  className={`flex items-center justify-center gap-2 p-3 rounded-xl border-2 text-sm font-medium transition-colors ${
                    evalMode === 'individual' ? 'border-brand-turquoise bg-brand-turquoise/10 text-brand-turquoise' : 'border-slate-200 dark:border-slate-700'
                  }`}
                >
                  <User className="h-4 w-4" />
                  {t('individual')}
                </button>
                <button
                  onClick={() => setEvalMode('group')}
                  className={`flex items-center justify-center gap-2 p-3 rounded-xl border-2 text-sm font-medium transition-colors ${
                    evalMode === 'group' ? 'border-brand-turquoise bg-brand-turquoise/10 text-brand-turquoise' : 'border-slate-200 dark:border-slate-700'
                  }`}
                >
                  <UsersRound className="h-4 w-4" />
                  {t('groups')}
                </button>
              </div>
            </div>

            <div className="border-t border-slate-200 dark:border-slate-700" />

            <div className="space-y-2">
              <label className="text-sm font-medium flex items-center gap-2">
                <FileSpreadsheet className="h-4 w-4 text-brand-turquoise" />
                {t('followupColumns')}
              </label>
              {followupColumns.map((col, ci) => (
                <div key={col.id} className="flex items-center gap-2 bg-slate-50 dark:bg-slate-800 rounded-lg p-2">
                  <GripVertical className="h-3.5 w-3.5 text-muted-foreground flex-none" />
                  <input
                    value={col.name}
                    onChange={e => {
                      const updated = [...followupColumns];
                      updated[ci] = { ...updated[ci], name: e.target.value };
                      setFollowupColumns(updated);
                    }}
                    className="flex-1 bg-transparent text-sm outline-none"
                  />
                  <select
                    value={col.type || 'grade'}
                    onChange={e => {
                      const updated = [...followupColumns];
                      updated[ci] = { ...updated[ci], type: e.target.value };
                      setFollowupColumns(updated);
                    }}
                    className="text-[10px] bg-white dark:bg-slate-700 rounded border px-1 py-0.5"
                  >
                    <option value="grade">{t('gradeType')}</option>
                    <option value="check">{t('checkType')}</option>
                    <option value="text">{t('textType')}</option>
                  </select>
                  <input
                    type="number"
                    value={col.maxGrade}
                    onChange={e => {
                      const updated = [...followupColumns];
                      updated[ci] = { ...updated[ci], maxGrade: parseInt(e.target.value) || 0 };
                      setFollowupColumns(updated);
                    }}
                    className="w-14 text-center text-xs bg-white dark:bg-slate-700 rounded border px-1 py-0.5"
                    min={0}
                    max={100}
                  />
                  <span className="text-[10px] text-muted-foreground">{t('maxGrade')}</span>
                  {followupColumns.length > 1 && (
                    <button onClick={() => setFollowupColumns(followupColumns.filter((_, i) => i !== ci))} className="text-red-400 hover:text-red-500">
                      <Trash2 className="h-3 w-3" />
                    </button>
                  )}
                </div>
              ))}
              <button
                onClick={() => setFollowupColumns([...followupColumns, {
                  id: `col_${Date.now()}`,
                  name: t('newColumn'),
                  maxGrade: 10,
                  type: 'grade'
                }])}
                className="w-full flex items-center justify-center gap-1.5 py-2 rounded-lg border border-dashed border-slate-300 dark:border-slate-600 text-muted-foreground text-xs hover:text-brand-turquoise hover:border-brand-turquoise transition-colors"
              >
                <Plus className="h-3.5 w-3.5" />
                {t('addColumn')}
              </button>
            </div>

            <div className="border-t border-slate-200 dark:border-slate-700" />

            <div className="space-y-2">
              <label className="text-sm font-medium flex items-center gap-2">
                <Heart className="h-4 w-4 text-pink-500" />
                {t('behaviourItems')}
              </label>
              <p className="text-[11px] text-muted-foreground">{t('behaviourItemsHint')}</p>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-2 space-y-1">
                  <span className="text-[10px] font-bold text-green-600 dark:text-green-400 flex items-center gap-1">
                    <ThumbsUp className="h-3 w-3" /> {t('positiveBehaviour')}
                  </span>
                  {[...(sessionInfo?.positive_behaviours || []), ...customPositiveBehaviours].map((b, i) => (
                    <div key={i} className="text-[10px] text-slate-600 dark:text-slate-400 flex items-center gap-1">
                      <CheckCircle2 className="h-2.5 w-2.5 text-green-500 flex-none" />
                      <span className="flex-1">{b}</span>
                      {i >= (sessionInfo?.positive_behaviours?.length || 0) && (
                        <button onClick={() => setCustomPositiveBehaviours(prev => prev.filter((_, j) => j !== i - (sessionInfo?.positive_behaviours?.length || 0)))} className="text-red-400 hover:text-red-500">
                          <XCircle className="h-2.5 w-2.5" />
                        </button>
                      )}
                    </div>
                  ))}
                  <div className="flex items-center gap-1 mt-1">
                    <input
                      className="flex-1 text-[10px] bg-white dark:bg-slate-700 rounded border px-1.5 py-0.5 outline-none focus:border-green-500"
                      placeholder={t('addItem')}
                      onKeyDown={e => {
                        if (e.key === 'Enter' && e.target.value.trim()) {
                          setCustomPositiveBehaviours(prev => [...prev, e.target.value.trim()]);
                          e.target.value = '';
                        }
                      }}
                    />
                    <Plus className="h-3 w-3 text-green-500" />
                  </div>
                </div>
                <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-2 space-y-1">
                  <span className="text-[10px] font-bold text-red-600 dark:text-red-400 flex items-center gap-1">
                    <ThumbsDown className="h-3 w-3" /> {t('negativeBehaviour')}
                  </span>
                  {[...(sessionInfo?.negative_behaviours || []), ...customNegativeBehaviours].map((b, i) => (
                    <div key={i} className="text-[10px] text-slate-600 dark:text-slate-400 flex items-center gap-1">
                      <XCircle className="h-2.5 w-2.5 text-red-500 flex-none" />
                      <span className="flex-1">{b}</span>
                      {i >= (sessionInfo?.negative_behaviours?.length || 0) && (
                        <button onClick={() => setCustomNegativeBehaviours(prev => prev.filter((_, j) => j !== i - (sessionInfo?.negative_behaviours?.length || 0)))} className="text-red-400 hover:text-red-500">
                          <Trash2 className="h-2.5 w-2.5" />
                        </button>
                      )}
                    </div>
                  ))}
                  <div className="flex items-center gap-1 mt-1">
                    <input
                      className="flex-1 text-[10px] bg-white dark:bg-slate-700 rounded border px-1.5 py-0.5 outline-none focus:border-red-500"
                      placeholder={t('addItem')}
                      onKeyDown={e => {
                        if (e.key === 'Enter' && e.target.value.trim()) {
                          setCustomNegativeBehaviours(prev => [...prev, e.target.value.trim()]);
                          e.target.value = '';
                        }
                      }}
                    />
                    <Plus className="h-3 w-3 text-red-500" />
                  </div>
                </div>
              </div>
            </div>

            <div className="border-t border-slate-200 dark:border-slate-700" />

            <div className="space-y-2">
              <label className="text-sm font-medium flex items-center gap-2">
                <Star className="h-4 w-4 text-purple-500" />
                {t('skillItems')}
              </label>
              <p className="text-[11px] text-muted-foreground">{t('skillItemsHint')}</p>
              <div className="flex flex-wrap gap-1.5">
                {[
                  ...(skillTypes.length > 0 ? skillTypes.map(s => s.name || s.label || s) : []),
                  ...customSkills
                ].map((skill, i) => {
                  const isCustom = i >= (skillTypes.length > 0 ? skillTypes.length : 0);
                  return (
                    <span key={i} className="inline-flex items-center gap-1 bg-purple-50 dark:bg-purple-900/20 px-2 py-1 rounded-lg text-[11px] text-purple-700 dark:text-purple-300">
                      <Star className="h-2.5 w-2.5" />
                      {skill}
                      {isCustom && (
                        <button onClick={() => setCustomSkills(prev => prev.filter((_, j) => j !== i - (skillTypes.length > 0 ? skillTypes.length : 0)))} className="text-red-400 hover:text-red-500">
                          <XCircle className="h-2.5 w-2.5" />
                        </button>
                      )}
                    </span>
                  );
                })}
              </div>
              <div className="flex items-center gap-1.5">
                <input
                  className="flex-1 text-[11px] bg-white dark:bg-slate-700 rounded-lg border px-2 py-1 outline-none focus:border-purple-500"
                  placeholder={t('addItem')}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && e.target.value.trim()) {
                      setCustomSkills(prev => [...prev, e.target.value.trim()]);
                      e.target.value = '';
                    }
                  }}
                />
                <button
                  onClick={e => {
                    const input = e.currentTarget.previousElementSibling;
                    if (input?.value?.trim()) {
                      setCustomSkills(prev => [...prev, input.value.trim()]);
                      input.value = '';
                    }
                  }}
                  className="p-1 rounded-lg bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 hover:bg-purple-200 dark:hover:bg-purple-900/50 transition-colors"
                >
                  <Plus className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Follow-up Record (كشف المتابعة) Dialog */}
      <Dialog open={showFollowupRecord} onOpenChange={setShowFollowupRecord}>
        <DialogContent className="max-w-4xl max-h-[85vh] overflow-hidden flex flex-col" dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader>
            <DialogTitle className="font-cairo flex items-center gap-2">
              <FileSpreadsheet className="h-5 w-5 text-brand-turquoise" />
              {t('followupRecord')}
            </DialogTitle>
          </DialogHeader>
          <div className="flex-1 overflow-auto">
            <table className="w-full text-sm border-collapse">
              <thead className="sticky top-0 bg-slate-100 dark:bg-slate-800">
                <tr>
                  <th className="border px-3 py-2 text-start font-cairo font-bold text-xs">#</th>
                  <th className="border px-3 py-2 text-start font-cairo font-bold text-xs">{t('studentName')}</th>
                  {followupColumns.map(col => (
                    <th key={col.id} className="border px-3 py-2 text-center font-cairo font-bold text-xs">
                      <div>{col.name}</div>
                      <div className="text-[10px] text-muted-foreground font-normal">/{col.maxGrade}</div>
                    </th>
                  ))}
                  <th className="border px-3 py-2 text-center font-cairo font-bold text-xs">{t('total')}</th>
                </tr>
              </thead>
              <tbody>
                {presentStudents.map((student, si) => {
                  const studentData = followupData[student.id] || {};
                  const numericCols = followupColumns.filter(c => c.type !== 'text');
                  const total = numericCols.reduce((sum, col) => sum + (Number(studentData[col.id]) || 0), 0);
                  const maxTotal = numericCols.reduce((sum, col) => sum + col.maxGrade, 0);
                  return (
                    <tr key={student.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                      <td className="border px-3 py-1.5 text-xs text-muted-foreground">{si + 1}</td>
                      <td className="border px-3 py-1.5 text-xs font-medium">{student.full_name}</td>
                      {followupColumns.map(col => (
                        <td key={col.id} className="border px-1 py-1">
                          {col.type === 'check' ? (
                            <div className="flex items-center justify-center">
                              <input
                                type="checkbox"
                                checked={!!studentData[col.id]}
                                onChange={e => {
                                  setFollowupData(prev => ({
                                    ...prev,
                                    [student.id]: { ...(prev[student.id] || {}), [col.id]: e.target.checked ? 1 : 0 }
                                  }));
                                }}
                                className="w-4 h-4 rounded border-slate-300 text-brand-turquoise focus:ring-brand-turquoise"
                              />
                            </div>
                          ) : col.type === 'text' ? (
                            <input
                              type="text"
                              value={studentData[col.id] || ''}
                              onChange={e => {
                                setFollowupData(prev => ({
                                  ...prev,
                                  [student.id]: { ...(prev[student.id] || {}), [col.id]: e.target.value }
                                }));
                              }}
                              className="w-full text-center text-xs bg-transparent outline-none border rounded p-1 focus:border-brand-turquoise"
                            />
                          ) : (
                            <input
                              type="number"
                              value={studentData[col.id] || ''}
                              onChange={e => {
                                const val = Math.min(parseInt(e.target.value) || 0, col.maxGrade);
                                setFollowupData(prev => ({
                                  ...prev,
                                  [student.id]: { ...(prev[student.id] || {}), [col.id]: val }
                                }));
                              }}
                              className="w-full text-center text-xs bg-transparent outline-none border rounded p-1 focus:border-brand-turquoise"
                              min={0}
                              max={col.maxGrade}
                            />
                          )}
                        </td>
                      ))}
                      <td className="border px-3 py-1.5 text-center text-xs font-bold">
                        <span className={total >= maxTotal * 0.6 ? 'text-green-600' : total >= maxTotal * 0.3 ? 'text-amber-600' : 'text-red-600'}>
                          {total}
                        </span>
                        <span className="text-muted-foreground">/{maxTotal}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="flex-none pt-3 border-t flex items-center justify-between">
            <span className="text-xs text-muted-foreground">{presentStudents.length} {t('students')}</span>
            <Button size="sm" onClick={() => setShowFollowupRecord(false)}>{t('close')}</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
    </SectionErrorBoundary>
  );
}

function SessionReviewPhase({ reviewData, sessionInfo, closingNote, setClosingNote, onConfirm, onBack, loading, isRTL }) {
  const { t } = useTranslation();
  const r = reviewData;
  return (
    <div className="min-h-screen bg-slate-900 p-4 flex items-center justify-center" dir={isRTL ? 'rtl' : 'ltr'}>
      <div className="w-full max-w-lg space-y-4 pb-6 max-h-screen overflow-y-auto">
        <div className="bg-gradient-to-br from-slate-800 to-slate-900 rounded-2xl p-5 border border-white/10 text-center">
          <ClipboardCheck className="h-12 w-12 mx-auto mb-2 text-amber-400" />
          <h1 className="font-cairo text-xl font-bold text-white">{t('sessionSummaryReview')}</h1>
          <p className="text-white/50 text-sm mt-1">{sessionInfo?.subject_name || sessionInfo?.subjectName} — {sessionInfo?.class_name || sessionInfo?.className}</p>
          <div className="mt-3 text-2xl font-mono font-bold text-white">{r.duration_minutes || 0} <span className="text-sm text-white/50">{t('durationMinutes')}</span></div>
        </div>

        {r.warnings?.length > 0 && (
          <div className="bg-amber-900/30 border border-amber-500/30 rounded-xl p-4 space-y-2">
            <h3 className="text-amber-400 text-sm font-bold font-cairo flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" /> {t('warnings')}
            </h3>
            {r.warnings.map((w, i) => (
              <div key={i} className="flex items-center gap-2 text-amber-300 text-xs">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 flex-none" />
                {w}
              </div>
            ))}
          </div>
        )}

        <div className="bg-slate-800 rounded-xl p-4">
          <h3 className="text-white/70 text-sm mb-3 font-cairo font-bold flex items-center gap-2">
            <Users className="h-4 w-4 text-green-400" /> {t('attendanceData')}
          </h3>
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: t('registered'), value: r.attendance?.total, color: 'text-white' },
              { label: t('present'), value: r.attendance?.present, color: 'text-green-400' },
              { label: t('absent'), value: r.attendance?.absent, color: 'text-red-400' },
              { label: t('late'), value: r.attendance?.late, color: 'text-amber-400' },
              { label: t('excused'), value: r.attendance?.excused, color: 'text-blue-400' },
              { label: t('attendanceRate'), value: `${r.attendance?.rate || 0}%`, color: 'text-emerald-400' },
            ].map(item => (
              <div key={item.label} className="bg-white/5 rounded-lg p-2 text-center">
                <div className={`text-lg font-bold ${item.color}`}>{item.value ?? 0}</div>
                <div className="text-white/40 text-[10px]">{item.label}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-slate-800 rounded-xl p-4">
          <h3 className="text-white/70 text-sm mb-3 font-cairo font-bold flex items-center gap-2">
            <Activity className="h-4 w-4 text-blue-400" /> {t('interactionData')}
          </h3>
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: t('participations'), value: r.interactions?.total_participations, color: 'text-blue-400' },
              { label: t('participatingStudents'), value: r.interactions?.participating_students, color: 'text-purple-400' },
              { label: t('evaluatedStudents'), value: r.interactions?.evaluated_students ?? r.interactions?.participating_students, color: 'text-indigo-400' },
              { label: t('questions'), value: r.interactions?.questions_asked, color: 'text-cyan-400' },
              { label: t('correctAnswers'), value: r.interactions?.correct_answers, color: 'text-green-400' },
              { label: t('wrongAnswers'), value: r.interactions?.wrong_answers, color: 'text-red-400' },
              { label: t('notesSent'), value: r.notes?.sent_to_parents ?? 0, color: 'text-emerald-400' },
              { label: t('participationRate'), value: `${r.interactions?.participation_rate || 0}%`, color: 'text-emerald-400' },
            ].map(item => (
              <div key={item.label} className="bg-white/5 rounded-lg p-2 text-center">
                <div className={`text-lg font-bold ${item.color}`}>{item.value ?? 0}</div>
                <div className="text-white/40 text-[10px]">{item.label}</div>
              </div>
            ))}
          </div>
        </div>

        {(r.behaviours?.total > 0) && (
          <div className="bg-slate-800 rounded-xl p-4">
            <h3 className="text-white/70 text-sm mb-3 font-cairo font-bold flex items-center gap-2">
              <Heart className="h-4 w-4 text-pink-400" /> {t('behaviourData')}
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-green-900/30 rounded-lg p-3 text-center">
                <ThumbsUp className="h-5 w-5 text-green-400 mx-auto mb-1" />
                <div className="text-xl font-bold text-green-400">{r.behaviours?.positive || 0}</div>
                <div className="text-white/50 text-[10px]">{t('positiveBehaviour')}</div>
              </div>
              <div className="bg-red-900/30 rounded-lg p-3 text-center">
                <ThumbsDown className="h-5 w-5 text-red-400 mx-auto mb-1" />
                <div className="text-xl font-bold text-red-400">{r.behaviours?.negative || 0}</div>
                <div className="text-white/50 text-[10px]">{t('negativeBehaviour')}</div>
              </div>
            </div>
          </div>
        )}

        {(r.skills?.recorded > 0) && (
          <div className="bg-slate-800 rounded-xl p-4">
            <h3 className="text-white/70 text-sm mb-3 font-cairo font-bold flex items-center gap-2">
              <Star className="h-4 w-4 text-purple-400" /> {t('skillsData')}
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-purple-900/30 rounded-lg p-3 text-center">
                <div className="text-xl font-bold text-purple-400">{r.skills?.recorded}</div>
                <div className="text-white/50 text-[10px]">{t('recordedSkill')}</div>
              </div>
              <div className="bg-indigo-900/30 rounded-lg p-3 text-center">
                <div className="text-xl font-bold text-indigo-400">{r.skills?.students_count}</div>
                <div className="text-white/50 text-[10px]">{t('student')}</div>
              </div>
            </div>
          </div>
        )}

        <div className="bg-slate-800 rounded-xl p-4">
          <h3 className="text-white/70 text-sm mb-3 font-cairo font-bold flex items-center gap-2">
            <StickyNote className="h-4 w-4 text-amber-400" /> {t('notesLabel')}
          </h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-amber-900/30 rounded-lg p-3 text-center">
              <div className="text-xl font-bold text-amber-400">{r.notes?.total || 0}</div>
              <div className="text-white/50 text-[10px]">{t('totalNotes')}</div>
            </div>
            <div className="bg-orange-900/30 rounded-lg p-3 text-center">
              <div className="text-xl font-bold text-orange-400">{r.notes?.teacher_notes || 0}</div>
              <div className="text-white/50 text-[10px]">{t('teacherNotes')}</div>
            </div>
          </div>
        </div>

        {r.needs_attention?.length > 0 && (
          <div className="bg-slate-800 rounded-xl p-4">
            <h3 className="text-white/70 text-sm mb-3 font-cairo font-bold flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-400" /> {t('needsAttention')}
            </h3>
            {r.needs_attention.map((s, i) => (
              <div key={i} className="flex items-center justify-between py-1.5 border-b border-white/5 last:border-0">
                <span className="text-white text-sm">{s.name}</span>
                <span className="text-amber-400 text-xs">{s.reason}</span>
              </div>
            ))}
          </div>
        )}

        {r.top_participants?.length > 0 && (
          <div className="bg-slate-800 rounded-xl p-4">
            <h3 className="text-white/70 text-sm mb-3 font-cairo font-bold flex items-center gap-2">
              <Award className="h-4 w-4 text-amber-400" /> {t('topParticipants')}
            </h3>
            {r.top_participants.map((p, i) => (
              <div key={i} className="flex items-center justify-between py-1.5">
                <div className="flex items-center gap-2">
                  <span className="text-amber-400 text-xs font-bold w-5">#{i + 1}</span>
                  <span className="text-white text-sm">{p.name}</span>
                </div>
                <span className="text-green-400 text-xs">{p.correct_answers} ✓ | {p.participations} {t('participation')}</span>
              </div>
            ))}
          </div>
        )}

        <div className="bg-slate-800 rounded-xl p-4">
          <h3 className="text-white/70 text-sm mb-3 font-cairo font-bold flex items-center gap-2">
            <PenLine className="h-4 w-4 text-cyan-400" /> {t('closingNoteLabel')}
          </h3>
          <Textarea
            value={closingNote}
            onChange={(e) => setClosingNote(e.target.value)}
            placeholder={t('closingNotePlaceholder')}
            className="bg-slate-900 border-white/10 text-white placeholder:text-white/30 resize-none text-sm font-cairo"
            rows={3}
          />
        </div>

        <div className="flex gap-3 pt-2">
          <button
            onClick={onBack}
            className="flex-1 h-12 rounded-xl bg-slate-700 hover:bg-slate-600 text-white font-cairo font-bold text-sm transition-colors"
          >
            {t('back')}
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="flex-1 h-12 rounded-xl bg-red-600 hover:bg-red-500 disabled:opacity-60 text-white font-cairo font-bold text-sm flex items-center justify-center gap-2 transition-colors"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
            {t('confirmAndEnd')}
          </button>
        </div>
      </div>
    </div>
  );
}


function StudentCard({ student, isFlashing, isSelected, onClick }) {
  const initials = student.full_name?.charAt(0) || '?';
  const count = student.interactionCount || 0;
  const correct = student.correctAnswers || 0;
  const isFemale = student.gender === 'female';
  const avatarBg = isFlashing ? 'bg-white/20' : isFemale ? 'bg-gradient-to-br from-pink-500 to-rose-600' : 'bg-gradient-to-br from-sky-500 to-blue-600';

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
          : 'bg-slate-700/60 hover:bg-slate-600/60 hover:scale-105'
      }`}
    >
      <div className={`relative w-12 h-12 rounded-full mx-auto mb-1.5 flex items-center justify-center text-white font-bold shadow-md ${avatarBg} ${interactionRing}`}>
        {student.avatar_url ? (
          <img src={student.avatar_url} alt={initials} className="w-12 h-12 rounded-full object-cover" />
        ) : (
          <span className="text-lg">{initials}</span>
        )}
        {count > 0 && (
          <span className={`absolute -top-1 -right-1 w-5 h-5 rounded-full text-[9px] font-bold flex items-center justify-center text-white shadow-sm ${
            correct > 0 ? 'bg-green-500' : 'bg-amber-500'
          }`}>
            {count}
          </span>
        )}
      </div>
      <p className="text-white text-[10px] font-medium leading-tight truncate">
        {student.full_name?.split(' ').slice(0, 2).join(' ')}
      </p>
      {count > 0 && (
        <div className="mt-0.5 flex items-center justify-center gap-1">
          <span className="text-green-400 text-[9px] font-bold">{correct}</span>
          <span className="text-white/30 text-[9px]">/</span>
          <span className="text-white/50 text-[9px]">{count}</span>
        </div>
      )}
    </button>
  );
}

function ActionButton({ color, icon, label, sub, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`${color} text-white rounded-lg py-3 px-2 flex flex-col items-center gap-1 transition-colors active:scale-95`}
    >
      {icon}
      <span className="text-xs font-medium">{label}</span>
      <span className="text-[10px] opacity-75">{sub}</span>
    </button>
  );
}

function SessionSummary({ summary, sessionInfo, onHome, isRTL }) {
  const { t } = useTranslation();
  const { api } = useAuth();
  const { nassaqError } = useNassaqAlert();
  const navigate = useNavigate();
  const [sendingNotif, setSendingNotif] = useState(false);
  const [notifSent, setNotifSent] = useState(false);
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    confetti({ particleCount: 120, spread: 80, origin: { y: 0.5 } });
    const t1 = setTimeout(() => confetti({ particleCount: 60, angle: 60, spread: 55, origin: { x: 0, y: 0.6 } }), 300);
    const t2 = setTimeout(() => confetti({ particleCount: 60, angle: 120, spread: 55, origin: { x: 1, y: 0.6 } }), 600);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, []);

  const sendParentNotifications = async () => {
    setSendingNotif(true);
    const subjectName = sessionInfo?.subject_name || sessionInfo?.subjectName || '';
    const className = sessionInfo?.class_name || sessionInfo?.className || '';
    const durationMin = summary.duration_minutes || 0;
    const presentCount = summary.present_count || 0;
    const absentCount = summary.absent_count || 0;
    const questionsCount = summary.questions_asked || 0;
    const correctCount = summary.correct_answers || 0;
    try {
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
      const adminNotif = {
        ...notifPayload,
        recipient_role: 'admin',
        scope_class_id: undefined,
      };
      const results = await Promise.allSettled([
        api.post('/notifications', notifPayload),
        api.post('/notifications', adminNotif),
      ]);
      const successCount = results.filter(r => r.status === 'fulfilled').length;
      if (successCount > 0) {
        setNotifSent(true);
        toast.success(t('reportSentToParentsAndAdmin'));
        confetti({ particleCount: 50, spread: 60, origin: { y: 0.7 }, colors: ['#10b981', '#34d399', '#6ee7b7'] });
      } else {
        nassaqError(t('failedToSendNotifications'));
      }
    } catch (e) {
      console.error('Error sending notifications:', e);
      nassaqError(t('failedToSendNotifications'));
    } finally {
      setSendingNotif(false);
    }
  };

  const exportReport = async () => {
    setExporting(true);
    try {
      const res = await api.get(`/session/${summary.session_record_id}/export-report`);
      const data = res.data;
      const rows = [
        ['اسم الطالب', 'الحضور', 'إجابات صحيحة', 'إجابات خاطئة', 'مشاركات', 'سلوك إيجابي', 'سلوك سلبي'],
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
    <div className="min-h-screen bg-slate-900 p-4 flex items-center justify-center" dir={isRTL ? 'rtl' : 'ltr'}>
      <div className="w-full max-w-md space-y-4 pb-6">
        <div className="bg-gradient-to-br from-brand-turquoise to-brand-navy rounded-2xl p-6 text-white text-center relative overflow-hidden">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_30%,rgba(255,255,255,0.08),transparent_60%)]" />
          <div className="relative z-10">
            <Trophy className="h-14 w-14 mx-auto mb-3 text-amber-300" />
            <h1 className="font-cairo text-2xl font-bold">{t('sessionEnded')}</h1>
            <p className="text-white/70 mt-1">{sessionInfo?.subject_name || sessionInfo?.subjectName} — {sessionInfo?.class_name || sessionInfo?.className}</p>
            <div className="mt-4 text-3xl font-mono font-bold">{summary.duration_minutes || 0} <span className="text-lg text-white/60">{t('durationMinutes')}</span></div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          {[
            { label: t('present'), value: summary.present_count, color: 'text-green-400', bg: 'bg-green-900/30', icon: <UserCheck className="h-5 w-5 text-green-400" /> },
            { label: t('absent'), value: summary.absent_count, color: 'text-red-400', bg: 'bg-red-900/30', icon: <XCircle className="h-5 w-5 text-red-400" /> },
            { label: t('evaluatedStudents'), value: summary.evaluated_students ?? summary.present_count, color: 'text-indigo-400', bg: 'bg-indigo-900/30', icon: <ClipboardCheck className="h-5 w-5 text-indigo-400" /> },
            { label: t('questions'), value: summary.questions_asked, color: 'text-blue-400', bg: 'bg-blue-900/30', icon: <FileQuestion className="h-5 w-5 text-blue-400" /> },
            { label: t('correctAnswers'), value: summary.correct_answers, color: 'text-amber-400', bg: 'bg-amber-900/30', icon: <CheckCircle2 className="h-5 w-5 text-amber-400" /> },
            { label: t('notesSent'), value: summary.notes_sent ?? 0, color: 'text-emerald-400', bg: 'bg-emerald-900/30', icon: <Send className="h-5 w-5 text-emerald-400" /> },
          ].map(item => (
            <div key={item.label} className={`${item.bg} rounded-xl p-4 text-center`}>
              <div className="text-lg mb-1">{item.icon}</div>
              <div className={`text-2xl font-bold ${item.color}`}>{item.value ?? 0}</div>
              <div className="text-white/60 text-xs mt-1">{item.label}</div>
            </div>
          ))}
        </div>

        {(hasBehaviours || hasSkills) && (
          <div className="bg-slate-800 rounded-xl p-4">
            <h3 className="text-white/70 text-sm mb-3 flex items-center gap-2">
              <Heart className="h-4 w-4 text-pink-400" /> {t('behaviourData')}
            </h3>
            <div className={`grid ${hasSkills ? 'grid-cols-3' : 'grid-cols-2'} gap-3`}>
              {hasBehaviours && (
                <>
                  <div className="bg-green-900/30 rounded-lg p-3 text-center">
                    <ThumbsUp className="h-5 w-5 text-green-400 mx-auto mb-1" />
                    <div className="text-xl font-bold text-green-400">{summary.positive_behaviours || 0}</div>
                    <div className="text-white/50 text-[10px]">{t('positiveBehaviour')}</div>
                  </div>
                  <div className="bg-red-900/30 rounded-lg p-3 text-center">
                    <ThumbsDown className="h-5 w-5 text-red-400 mx-auto mb-1" />
                    <div className="text-xl font-bold text-red-400">{summary.negative_behaviours || 0}</div>
                    <div className="text-white/50 text-[10px]">{t('negativeBehaviour')}</div>
                  </div>
                </>
              )}
              {hasSkills && (
                <div className="bg-purple-900/30 rounded-lg p-3 text-center">
                  <Star className="h-5 w-5 text-purple-400 mx-auto mb-1" />
                  <div className="text-xl font-bold text-purple-400">{summary.skills_recorded}</div>
                  <div className="text-white/50 text-[10px]">{t('recordedSkill')}</div>
                </div>
              )}
            </div>
          </div>
        )}

        {summary.participation_rate !== undefined && (
          <div className="bg-slate-800 rounded-xl p-4">
            <div className="flex justify-between text-sm text-white/70 mb-2">
              <span>{t('participationRate')}</span>
              <span className="text-white font-bold">{Math.round(summary.participation_rate)}%</span>
            </div>
            <div className="h-2.5 bg-slate-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-brand-turquoise to-brand-navy transition-colors"
                style={{ width: `${summary.participation_rate}%` }}
              />
            </div>
          </div>
        )}

        {summary.needs_attention?.length > 0 && (
          <div className="bg-slate-800 rounded-xl p-4">
            <h3 className="text-white/70 text-sm mb-3 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-400" /> {t('needsAttention')}
            </h3>
            {summary.needs_attention.map((s, i) => (
              <div key={i} className="flex items-center justify-between py-1.5 border-b border-white/5 last:border-0">
                <span className="text-white text-sm">{s.name}</span>
                <span className="text-amber-400 text-xs">{s.reason}</span>
              </div>
            ))}
          </div>
        )}

        {summary.top_participants?.length > 0 && (
          <div className="bg-slate-800 rounded-xl p-4">
            <h3 className="text-white/70 text-sm mb-3 flex items-center gap-2">
              <Award className="h-4 w-4 text-amber-400" /> {t('topParticipants')}
            </h3>
            {summary.top_participants.map((p, i) => (
              <div key={i} className="flex items-center justify-between py-1.5">
                <div className="flex items-center gap-2">
                  <span className="text-amber-400 text-xs font-bold w-5">#{i + 1}</span>
                  <span className="text-white text-sm">{p.name}</span>
                </div>
                <Badge className="bg-amber-900/50 text-amber-300 text-xs">{p.correct_answers} ✓</Badge>
              </div>
            ))}
          </div>
        )}

        {!notifSent ? (
          <button
            onClick={sendParentNotifications}
            disabled={sendingNotif}
            className="w-full h-11 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-60 text-white text-sm font-cairo font-bold flex items-center justify-center gap-2 transition-colors"
          >
            {sendingNotif ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
            {t('sendSummaryToParentsAndAdmin')}
          </button>
        ) : (
          <div className="flex items-center justify-center gap-2 text-emerald-400 text-sm py-2">
            <CheckCircle2 className="h-4 w-4" />
            <span>{t('sentSuccessfully')}</span>
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={exportReport}
            disabled={exporting}
            className="h-11 rounded-xl bg-slate-700 hover:bg-slate-600 disabled:opacity-60 text-white font-cairo font-bold text-sm flex items-center justify-center gap-2 transition-colors"
          >
            {exporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            {t('exportReport')}
          </button>
          <button
            onClick={() => navigate('/teacher/classes?tab=sessions')}
            className="h-11 rounded-xl bg-slate-700 hover:bg-slate-600 text-white font-cairo font-bold text-sm flex items-center justify-center gap-2 transition-colors"
          >
            <History className="h-4 w-4" />
            {t('sessionLog')}
          </button>
        </div>

        <button
          onClick={onHome}
          className="w-full h-12 rounded-xl bg-brand-turquoise text-white font-cairo font-bold text-base hover:opacity-90 transition-colors shadow-lg shadow-brand-turquoise/20"
        >
          {t('backToHome')}
        </button>
      </div>
    </div>
  );
}
