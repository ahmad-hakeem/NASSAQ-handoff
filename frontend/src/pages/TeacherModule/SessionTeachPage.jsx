import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
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
  Download, History, FileSpreadsheet
} from 'lucide-react';
import confetti from 'canvas-confetti';

const GENDER_COLORS = {
  male: { bg: 'bg-sky-600', ring: 'ring-sky-400', label: 'طلاب', icon: '👦', light: 'bg-sky-900/30' },
  female: { bg: 'bg-pink-600', ring: 'ring-pink-400', label: 'طالبات', icon: '👧', light: 'bg-pink-900/30' },
};

const MODES = [
  { id: 'review', label: 'مراجعة', icon: BookOpen, color: 'bg-purple-600' },
  { id: 'homework', label: 'واجب', icon: ClipboardCheck, color: 'bg-blue-600' },
  { id: 'quiz', label: 'اختبار', icon: FileQuestion, color: 'bg-amber-600' },
];

const PARTICIPATION = [
  { id: 'active', label: 'مشاركة', icon: Hand, color: 'bg-green-500', score: '+2' },
  { id: 'initiative', label: 'مبادرة', icon: Zap, color: 'bg-purple-500', score: '+3' },
  { id: 'inactive', label: 'لا يتفاعل', icon: Minus, color: 'bg-amber-500', score: '0' },
  { id: 'refused', label: 'رفض', icon: XCircle, color: 'bg-red-500', score: '-1' },
];

const BEHAVIOURS = {
  positive: [
    { id: 'respect', label: 'احترام', points: '+2' },
    { id: 'commitment', label: 'التزام', points: '+2' },
    { id: 'helping_others', label: 'مساعدة الآخرين', points: '+2' },
  ],
  negative: [
    { id: 'disruption', label: 'إزعاج', points: '-2' },
    { id: 'non_compliance', label: 'عدم التزام', points: '-2' },
    { id: 'interruption', label: 'مقاطعة', points: '-1' },
  ],
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
  const [actionTab, setActionTab] = useState('question'); // question | participation | behaviour | skill | homework
  const [behaviourCategory, setBehaviourCategory] = useState('positive');
  const [behaviourNote, setBehaviourNote] = useState('');
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
  const flashRef = useRef(null);
  useEffect(() => { return () => { if (flashRef.current) clearInterval(flashRef.current); }; }, []);
  const timer = useSessionTimer(startTime);

  const teacherId = user?.teacher_id || user?.id;

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!sessionId) {
      nassaqError('لم يتم العثور على جلسة نشطة');
      navigate('/teacher');
      return;
    }
    loadStudents();
    loadSessionInfo();
    loadSkillTypes();
    loadActivityLog();
  }, [sessionId]);

  const loadSessionInfo = async () => {
    try {
      const res = await api.get(`/session/${sessionId}`);
      if (res.data) {
        if (res.data.status === 'completed' || res.data.status === 'archived' || res.data.status === 'cancelled') {
          toast.info(isRTL ? 'هذه الحصة منتهية، يرجى بدء حصة جديدة' : 'This session has ended, please start a new one');
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
            if (found.id === 'homework') loadHomeworkStatuses();
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
    } catch {}
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
    } catch (e) {
      console.error('Error loading students:', e);
    }
  };

  const loadNotes = useCallback(async () => {
    if (!sessionId) return;
    try {
      const res = await api.get(`/session/${sessionId}/notes`);
      setNotes(res.data?.notes || []);
    } catch {}
  }, [api, sessionId]);

  const loadActivityLog = async () => {
    try {
      const res = await api.get(`/session/${sessionId}/activity`);
      const entries = res.data?.activity || [];
      if (entries.length > 0) {
        setActivityLog(entries);
        setStats(prev => {
          const questions = entries.filter(e => e.emoji === '✅' || e.emoji === '❌' || e.emoji === '⏭️').length;
          const correct = entries.filter(e => e.emoji === '✅').length;
          const participation = entries.filter(e => e.emoji === '🙋' || e.emoji === '😶').length;
          return {
            questions: Math.max(prev.questions, questions),
            correct: Math.max(prev.correct, correct),
            participation: Math.max(prev.participation, participation),
          };
        });
      }
    } catch {}
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
    } catch {}
  }, [api, sessionId]);

  useEffect(() => {
    if (!sessionId) return;
    loadNotes();
    loadLiveMetrics();
    const interval = setInterval(loadLiveMetrics, 30000);
    return () => clearInterval(interval);
  }, [sessionId, loadNotes, loadLiveMetrics]);

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
      toast.success('تم إضافة الملاحظة');
      loadNotes();
      addLog('📝', `ملاحظة: ${newNote.slice(0, 30)}...`, 'text-amber-600');
    } catch {
      nassaqError('خطأ في إضافة الملاحظة');
    }
  };

  const deleteNote = async (noteId) => {
    try {
      await api.delete(`/session/${sessionId}/note/${noteId}`);
      toast.success('تم حذف الملاحظة');
      loadNotes();
    } catch {
      nassaqError('خطأ في حذف الملاحظة');
    }
  };

  const getTabForMode = (modeId) => {
    if (modeId === 'quiz') return 'question';
    if (modeId === 'review') return 'participation';
    if (modeId === 'homework') return 'homework';
    return 'question';
  };

  const [homeworkLoading, setHomeworkLoading] = useState(false);

  const loadHomeworkStatuses = async () => {
    setHomeworkLoading(true);
    try {
      const res = await api.get(`/session/${sessionId}/homework`);
      setHomeworkStatuses(res.data?.statuses || {});
    } catch {
      nassaqError('خطأ في تحميل حالات الواجب');
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
        toast.success(`✅ حل — ${studentName}`);
      } else {
        toast.success(`❌ ما حل — ${studentName}`);
      }
    } catch {
      setHomeworkStatuses(prev => ({ ...prev, [studentId]: current || 'not_done' }));
      nassaqError('خطأ في تحديث حالة الواجب');
    }
  };

  const handleSetMode = async (m) => {
    if (mode?.id === m.id) return;
    try {
      await api.post(`/session/${sessionId}/mode`, { mode: m.id });
      setMode(m);
      setActionTab(getTabForMode(m.id));
      if (m.id === 'homework') loadHomeworkStatuses();
      toast.success(`تم تفعيل نمط: ${m.label}`, { id: 'session-mode' });
    } catch {
      nassaqError('خطأ في تحديد النمط');
    }
  };

  const selectRandom = async () => {
    if (loading) return;
    setLoading(true);
    setSelectedStudent(null);
    setShowHakim(true);

    const presentStudents = students.filter(s => s.attendance_status === 'present');
    if (!presentStudents.length) {
      nassaqError('لا يوجد طلاب حاضرون');
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
        toast.success(`🎉 ${selectedStudent.full_name?.split(' ')[0]} أجاب صحيحاً! +${change} نقطة`);
        addLog('✅', `${selectedStudent.full_name?.split(' ')[0]} — إجابة صحيحة (+${change})`, 'text-green-700');
        setStats(p => ({ ...p, questions: p.questions + 1, correct: p.correct + 1 }));
      } else if (result === 'wrong') {
        toast.info(`❌ ${selectedStudent.full_name?.split(' ')[0]} — إجابة خاطئة`);
        addLog('❌', `${selectedStudent.full_name?.split(' ')[0]} — إجابة خاطئة`, 'text-red-600');
        setStats(p => ({ ...p, questions: p.questions + 1 }));
      } else {
        toast.success(`⏭️ ${selectedStudent.full_name?.split(' ')[0]} — لم يجب (${change} نقطة)`);
        addLog('⏭️', `${selectedStudent.full_name?.split(' ')[0]} — لم يجب (${change})`, 'text-amber-600');
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
    } catch {
      nassaqError('خطأ في تسجيل الإجابة');
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
      const emoji = pType.id === 'active' || pType.id === 'initiative' ? '🙋' : pType.id === 'refused' ? '🚫' : '😐';
      toast.success(`${emoji} ${pType.label} — ${selectedStudent.full_name?.split(' ')[0]}`);
      addLog(emoji, `${selectedStudent.full_name?.split(' ')[0]} — ${pType.label} (${change > 0 ? '+' : ''}${change})`, change >= 0 ? 'text-blue-700' : 'text-amber-700');
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
    } catch {
      nassaqError('خطأ في تسجيل المشاركة');
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
      const emoji = behaviourCategory === 'negative' ? '⚠️' : behaviourCategory === 'skill' ? '⭐' : '👍';
      toast.success(`${emoji} سلوك: ${bType.label} — ${selectedStudent.full_name?.split(' ')[0]}`);
      addLog(emoji, `${selectedStudent.full_name?.split(' ')[0]} — ${bType.label} (${change > 0 ? '+' : ''}${change})`, behaviourCategory === 'negative' ? 'text-red-600' : 'text-purple-700');
      setBehaviourNote('');
    } catch {
      nassaqError('خطأ في تسجيل السلوك');
    }
  };

  const recordSkill = async (skill) => {
    if (!selectedStudent) return;
    try {
      const res = await api.post(`/session/${sessionId}/skill`, {
        student_id: selectedStudent.id,
        skill_type_id: skill.id,
        notes: skillNote || null,
      });
      const change = res.data?.score_change || 0;
      confetti({ particleCount: 50, spread: 60, origin: { y: 0.6 }, colors: ['#8b5cf6', '#a78bfa', '#c4b5fd'] });
      toast.success(`⭐ مهارة: ${skill.name_ar || skill.name} — ${selectedStudent.full_name?.split(' ')[0]}`);
      addLog('⭐', `${selectedStudent.full_name?.split(' ')[0]} — ${skill.name_ar || skill.name} (+${change})`, 'text-purple-700');
      setSkillNote('');
      setStudents(prev => prev.map(s =>
        s.id === selectedStudent.id ? { ...s, interactionCount: s.interactionCount + 1 } : s
      ));
      setSelectedStudent(prev => prev ? {
        ...prev,
        interactionCount: (prev.interactionCount || 0) + 1,
        interaction_count: (prev.interaction_count || 0) + 1,
      } : null);
    } catch {
      nassaqError('خطأ في تسجيل المهارة');
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
      toast.success(isRTL ? 'تم إنهاء الحصة بنجاح' : 'Session ended successfully');
    } catch (err) {
      const detail = err.response?.data?.detail || '';
      if (detail.includes('إنهاء') && detail.includes('مسبق')) {
        toast.info(isRTL ? 'الحصة منتهية بالفعل' : 'Session already ended');
        navigate('/teacher', { replace: true });
      } else {
        nassaqError(detail || (isRTL ? 'خطأ في إنهاء الحصة' : 'Error ending session'));
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

  if (reviewData) {
    return (
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
    );
  }

  if (summary) {
    return <SessionSummary summary={summary} sessionInfo={sessionInfo} onHome={() => navigate('/teacher')} isRTL={isRTL} />;
  }

  return (
    <div className="h-screen bg-slate-900 flex flex-col overflow-hidden" dir={isRTL ? 'rtl' : 'ltr'}>
      {/* ── Header ── */}
      <header className="bg-brand-navy border-b border-white/10 px-4 py-3 flex-none">
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
                    يشرح الدرس الآن
                  </span>
                )}
              </div>
              <p className="text-white/60 text-xs truncate">{sessionInfo?.class_name || sessionInfo?.className}</p>
            </div>
          </div>

          {/* Live stats bar */}
          <div className="hidden md:flex items-center gap-4 text-xs text-white/70">
            <span className="flex items-center gap-1">
              <Users className="h-3.5 w-3.5" /> {presentStudents.length} حاضر
            </span>
            <span className="flex items-center gap-1">
              <Activity className="h-3.5 w-3.5" /> {stats.questions} سؤال
            </span>
            <span className={`flex items-center gap-1 ${accuracy >= 60 ? 'text-green-400' : 'text-red-400'}`}>
              <BarChart2 className="h-3.5 w-3.5" /> {accuracy}% صحيح
            </span>
          </div>

          <div className="flex items-center gap-2">
            {/* Mode selector */}
            <div className="flex gap-1">
              {MODES.map(m => (
                <button
                  key={m.id}
                  onClick={() => handleSetMode(m)}
                  className={`hidden sm:flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-all ${
                    mode?.id === m.id ? `${m.color} text-white` : 'bg-white/10 text-white/60 hover:bg-white/20'
                  }`}
                >
                  <m.icon className="h-3 w-3" />
                  {m.label}
                </button>
              ))}
            </div>
            <Button
              size="sm"
              variant="destructive"
              className="text-xs h-8"
              onClick={() => setShowEndDialog(true)}
              disabled={reviewLoading}
            >
              {reviewLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : 'إنهاء'}
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
            ? 'انتهى وقت الحصة'
            : remainingMinutes !== null
              ? `تبقى ${remainingMinutes} ${remainingMinutes === 1 ? 'دقيقة' : 'دقائق'} على نهاية الحصة`
              : 'تبقى 10 دقائق على نهاية الحصة'
          }
        </div>
      )}

      {/* ── Main layout: left = console, right = log ── */}
      <div className="flex-1 flex overflow-hidden max-w-5xl w-full mx-auto">

        {/* ── Console (left 2/3) ── */}
        <div className="flex-1 flex flex-col overflow-hidden p-3 gap-3">

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
            className={`flex-none w-full h-14 rounded-xl font-cairo font-bold text-white text-base flex items-center justify-center gap-2 shadow-lg hover:opacity-90 active:scale-95 transition-all disabled:opacity-60 ${
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
              <><Shuffle className="h-5 w-5" /> اختيار طالب عشوائي</>
            )}
          </button>

          {/* Mode selector (mobile) */}
          <div className="sm:hidden grid grid-cols-3 gap-2">
            {MODES.map(m => (
              <button key={m.id} onClick={() => handleSetMode(m)}
                className={`rounded-lg py-2 text-xs font-medium flex flex-col items-center gap-1 transition-all ${
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
                  {mode.id === 'review' ? 'نمط المراجعة — مراجعة الدرس والمشاركة الصفية' :
                   mode.id === 'homework' ? 'نمط الواجب — متابعة حل الواجبات (حل / ما حل)' :
                   'نمط الاختبار — أسئلة سريعة وتقييم الإجابات'}
                </span>
              </div>
              <span className={`w-2 h-2 rounded-full animate-pulse ${
                mode.id === 'review' ? 'bg-purple-400' :
                mode.id === 'homework' ? 'bg-blue-400' : 'bg-amber-400'
              }`} />
            </div>
          )}

          {/* Student grid — gender split */}
          <div className="flex-1 overflow-y-auto">
            {!mode ? (
              <div className="h-full flex items-center justify-center text-white/40 text-sm">
                اختر نمط الحصة أعلاه للبدء
              </div>
            ) : hasGenderSplit ? (
              <div className="space-y-3">
                {[
                  { key: 'male', students: maleStudents },
                  { key: 'female', students: femaleStudents },
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
                {presentStudents.map((student) => (
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
            <div className="flex-none bg-slate-800 rounded-xl border border-white/10 overflow-hidden">
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
                    <div className="text-white/30 text-[9px]">مشاركات</div>
                  </div>
                  <div className="flex-1 bg-white/5 rounded-lg px-2 py-1 text-center">
                    <div className="text-green-400 text-xs font-bold">{selectedStudent.correct_answers || selectedStudent.correctAnswers || 0}</div>
                    <div className="text-white/30 text-[9px]">صحيحة</div>
                  </div>
                  <div className="flex-1 bg-white/5 rounded-lg px-2 py-1 text-center">
                    <div className="text-purple-400 text-xs font-bold">{selectedStudent.interaction_count || selectedStudent.interactionCount || 0}</div>
                    <div className="text-white/30 text-[9px]">تفاعلات</div>
                  </div>
                </div>
              </div>

              {/* Tabs */}
              <div className="flex border-b border-white/10">
                {[
                  { id: 'question', label: 'سؤال', icon: MessageCircle, forMode: 'quiz' },
                  { id: 'participation', label: 'مشاركة', icon: Hand, forMode: 'review' },
                  { id: 'homework', label: 'واجب', icon: ClipboardCheck, forMode: 'homework' },
                  { id: 'behaviour', label: 'سلوك', icon: ThumbsUp },
                  { id: 'skill', label: 'مهارة', icon: Star },
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
                    {tab.label}
                    {isRecommended && actionTab !== tab.id && (
                      <span className="absolute top-1 end-2 w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                    )}
                  </button>
                  );
                })}
              </div>

              {/* Tab content */}
              <div className="p-3">
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
                      <span className="text-white/60 text-xs font-cairo">اضغط على الطالب لتبديل حالة الواجب</span>
                      <span className="text-blue-400 text-xs font-bold font-cairo">
                        {Object.values(homeworkStatuses).filter(s => s === 'done').length}/{students.filter(s => s.attendance_status === 'present').length} حل
                      </span>
                    </div>
                    <div className="max-h-[300px] overflow-y-auto space-y-1.5 scrollbar-thin">
                      {students.filter(s => s.attendance_status === 'present').map(student => {
                        const isDone = homeworkStatuses[student.id] === 'done';
                        return (
                          <button
                            key={student.id}
                            onClick={() => toggleHomework(student.id)}
                            className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg transition-all active:scale-[0.97] ${
                              isDone
                                ? 'bg-green-600/20 border border-green-500/30'
                                : 'bg-white/5 border border-white/10 hover:border-white/20'
                            }`}
                          >
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold shrink-0 ${
                              isDone ? 'bg-green-600 text-white' : 'bg-white/10 text-white/40'
                            }`}>
                              {isDone ? '✅' : '❌'}
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

                {actionTab === 'behaviour' && (
                  <div className="space-y-2">
                    <div className="flex gap-1 mb-2">
                      {[
                        { id: 'positive', label: '👍 إيجابي', color: 'bg-green-600' },
                        { id: 'negative', label: '⚠️ سلبي', color: 'bg-red-600' },
                      ].map(cat => (
                        <button
                          key={cat.id}
                          onClick={() => setBehaviourCategory(cat.id)}
                          className={`flex-1 py-1.5 rounded text-xs font-medium text-white transition-all ${
                            behaviourCategory === cat.id ? cat.color : 'bg-white/10 text-white/60'
                          }`}
                        >
                          {cat.label}
                        </button>
                      ))}
                    </div>
                    <div className="grid grid-cols-3 gap-1.5">
                      {(BEHAVIOURS[behaviourCategory] || []).map(b => (
                        <button
                          key={b.id}
                          onClick={() => recordBehaviour(b)}
                          className="bg-white/10 hover:bg-white/20 text-white rounded-lg py-2 px-1 text-xs text-center transition-all"
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
                      {skillTypes.map(skill => (
                        <button
                          key={skill.id}
                          onClick={() => recordSkill(skill)}
                          className="bg-purple-900/40 hover:bg-purple-800/60 text-white rounded-lg py-2 px-1 text-xs text-center transition-all border border-purple-500/20"
                        >
                          <div className="font-medium truncate">{skill.name_ar || skill.name}</div>
                          <div className="text-[10px] mt-0.5 text-purple-300">+3</div>
                        </button>
                      ))}
                    </div>
                    {skillTypes.length === 0 && (
                      <p className="text-white/40 text-xs text-center py-2">لا توجد مهارات مسجلة</p>
                    )}
                    <input
                      className="w-full bg-white/10 text-white text-xs rounded px-2 py-1.5 placeholder-white/30 outline-none"
                      placeholder="ملاحظة اختيارية..."
                      value={skillNote}
                      onChange={e => setSkillNote(e.target.value)}
                    />
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* ── Right Panel (Activity Log + Notes, desktop only) ── */}
        <div className="hidden lg:flex flex-col w-72 border-r border-white/10 bg-slate-800/50 overflow-hidden">
          <div className="flex border-b border-white/10">
            {[
              { id: 'log', label: 'النشاط', icon: Activity },
              { id: 'notes', label: 'ملاحظات', icon: StickyNote },
              { id: 'metrics', label: 'المؤشرات', icon: BarChart2 },
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setRightPanel(tab.id)}
                className={`flex-1 flex items-center justify-center gap-1 py-2.5 text-xs font-medium transition-colors ${
                  rightPanel === tab.id ? 'text-brand-turquoise border-b-2 border-brand-turquoise' : 'text-white/50 hover:text-white/80'
                }`}
              >
                <tab.icon className="h-3.5 w-3.5" />
                {tab.label}
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
                      <p className={`text-xs font-medium ${log.color}`}>{log.emoji} {log.text}</p>
                      <p className="text-white/30 text-[10px] mt-0.5">{log.time}</p>
                    </div>
                  ))
                )}
              </div>
              <div className="border-t border-white/10 p-3 space-y-2">
                <div className="flex justify-between text-xs text-white/50">
                  <span>أسئلة</span><span className="text-white font-bold">{stats.questions}</span>
                </div>
                <div className="flex justify-between text-xs text-white/50">
                  <span>صحيح</span><span className="text-green-400 font-bold">{stats.correct}</span>
                </div>
                <div className="flex justify-between text-xs text-white/50">
                  <span>دقة</span>
                  <span className={`font-bold ${accuracy >= 60 ? 'text-green-400' : 'text-red-400'}`}>{accuracy}%</span>
                </div>
                <div className="flex justify-between text-xs text-white/50">
                  <span>تفاعل</span><span className="text-blue-400 font-bold">{stats.participation}</span>
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
                    { id: 'session', label: 'عامة' },
                    { id: 'student', label: 'طالب' },
                    { id: 'behavioural', label: 'سلوكية' },
                    { id: 'followup', label: 'متابعة' },
                  ].map(t => (
                    <button
                      key={t.id}
                      onClick={() => setNoteType(t.id)}
                      className={`flex-1 py-1 rounded text-[10px] font-medium transition-all ${
                        noteType === t.id ? 'bg-amber-600 text-white' : 'bg-white/10 text-white/50'
                      }`}
                    >
                      {t.label}
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
                    className="bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-white rounded px-2 py-1.5 transition-all"
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
                      <div className="h-full bg-green-500 transition-all" style={{ width: `${liveMetrics.attendance?.rate || 0}%` }} />
                    </div>
                    <div className="text-center text-white/50 text-[10px]">{liveMetrics.attendance?.rate || 0}% حضور</div>
                  </div>

                  <div className="bg-white/5 rounded-lg p-3 space-y-2">
                    <h4 className="text-white/60 text-[10px] font-medium uppercase tracking-wider">التفاعل</h4>
                    <div className="grid grid-cols-3 gap-2 text-center">
                      <div>
                        <div className="text-blue-400 text-lg font-bold">{liveMetrics.interaction?.total_questions || 0}</div>
                        <div className="text-white/40 text-[10px]">أسئلة</div>
                      </div>
                      <div>
                        <div className="text-green-400 text-lg font-bold">{liveMetrics.interaction?.correct_answers || 0}</div>
                        <div className="text-white/40 text-[10px]">صحيح</div>
                      </div>
                      <div>
                        <div className="text-red-400 text-lg font-bold">{liveMetrics.interaction?.wrong_answers || 0}</div>
                        <div className="text-white/40 text-[10px]">خطأ</div>
                      </div>
                    </div>
                    <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                      <div className="h-full bg-blue-500 transition-all" style={{ width: `${liveMetrics.interaction?.accuracy_rate || 0}%` }} />
                    </div>
                    <div className="text-center text-white/50 text-[10px]">{liveMetrics.interaction?.accuracy_rate || 0}% دقة</div>
                  </div>

                  <div className="bg-white/5 rounded-lg p-3 space-y-2">
                    <h4 className="text-white/60 text-[10px] font-medium uppercase tracking-wider">المشاركة</h4>
                    <div className="grid grid-cols-2 gap-2 text-center">
                      <div>
                        <div className="text-purple-400 text-lg font-bold">{liveMetrics.interaction?.unique_participants || 0}</div>
                        <div className="text-white/40 text-[10px]">مشارك</div>
                      </div>
                      <div>
                        <div className="text-amber-400 text-lg font-bold">{liveMetrics.interaction?.not_interacted || 0}</div>
                        <div className="text-white/40 text-[10px]">لم يتفاعل</div>
                      </div>
                    </div>
                    <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                      <div className="h-full bg-purple-500 transition-all" style={{ width: `${liveMetrics.interaction?.participation_rate || 0}%` }} />
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
                    ⏱️ {liveMetrics.duration_minutes || 0} دقيقة | 📝 {liveMetrics.notes_count || 0} ملاحظة
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

      {/* End Session Confirmation Dialog */}
      <Dialog open={showEndDialog} onOpenChange={setShowEndDialog}>
        <DialogContent className="max-w-sm" dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader>
            <DialogTitle className="font-cairo text-center">إنهاء الحصة</DialogTitle>
          </DialogHeader>
          <p className="text-center text-muted-foreground text-sm py-2">
            سيتم عرض ملخص الحصة للمراجعة قبل الإنهاء النهائي.
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
            <Button variant="outline" className="flex-1" onClick={() => setShowEndDialog(false)}>إلغاء</Button>
            <Button
              className="flex-1 bg-red-600 hover:bg-red-700"
              onClick={startEndReview}
              disabled={reviewLoading}
            >
              {reviewLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'مراجعة وإنهاء'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SessionReviewPhase({ reviewData, sessionInfo, closingNote, setClosingNote, onConfirm, onBack, loading, isRTL }) {
  const r = reviewData;
  return (
    <div className="min-h-screen bg-slate-900 p-4 flex items-center justify-center" dir={isRTL ? 'rtl' : 'ltr'}>
      <div className="w-full max-w-lg space-y-4 pb-6 max-h-screen overflow-y-auto">
        <div className="bg-gradient-to-br from-slate-800 to-slate-900 rounded-2xl p-5 border border-white/10 text-center">
          <ClipboardCheck className="h-12 w-12 mx-auto mb-2 text-amber-400" />
          <h1 className="font-cairo text-xl font-bold text-white">مراجعة ملخص الحصة</h1>
          <p className="text-white/50 text-sm mt-1">{sessionInfo?.subject_name || sessionInfo?.subjectName} — {sessionInfo?.class_name || sessionInfo?.className}</p>
          <div className="mt-3 text-2xl font-mono font-bold text-white">{r.duration_minutes || 0} <span className="text-sm text-white/50">دقيقة</span></div>
        </div>

        {r.warnings?.length > 0 && (
          <div className="bg-amber-900/30 border border-amber-500/30 rounded-xl p-4 space-y-2">
            <h3 className="text-amber-400 text-sm font-bold font-cairo flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" /> تنبيهات
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
            <Users className="h-4 w-4 text-green-400" /> بيانات الحضور
          </h3>
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: 'مسجلين', value: r.attendance?.total, color: 'text-white' },
              { label: 'حاضر', value: r.attendance?.present, color: 'text-green-400' },
              { label: 'غائب', value: r.attendance?.absent, color: 'text-red-400' },
              { label: 'متأخر', value: r.attendance?.late, color: 'text-amber-400' },
              { label: 'مستأذن', value: r.attendance?.excused, color: 'text-blue-400' },
              { label: 'نسبة الحضور', value: `${r.attendance?.rate || 0}%`, color: 'text-emerald-400' },
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
            <Activity className="h-4 w-4 text-blue-400" /> بيانات التفاعل
          </h3>
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: 'مشاركات', value: r.interactions?.total_participations, color: 'text-blue-400' },
              { label: 'طلاب شاركوا', value: r.interactions?.participating_students, color: 'text-purple-400' },
              { label: 'أسئلة', value: r.interactions?.questions_asked, color: 'text-cyan-400' },
              { label: 'إجابات صحيحة', value: r.interactions?.correct_answers, color: 'text-green-400' },
              { label: 'إجابات خاطئة', value: r.interactions?.wrong_answers, color: 'text-red-400' },
              { label: 'معدل المشاركة', value: `${r.interactions?.participation_rate || 0}%`, color: 'text-emerald-400' },
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
              <Heart className="h-4 w-4 text-pink-400" /> بيانات السلوك
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-green-900/30 rounded-lg p-3 text-center">
                <ThumbsUp className="h-5 w-5 text-green-400 mx-auto mb-1" />
                <div className="text-xl font-bold text-green-400">{r.behaviours?.positive || 0}</div>
                <div className="text-white/50 text-[10px]">سلوك إيجابي</div>
              </div>
              <div className="bg-red-900/30 rounded-lg p-3 text-center">
                <ThumbsDown className="h-5 w-5 text-red-400 mx-auto mb-1" />
                <div className="text-xl font-bold text-red-400">{r.behaviours?.negative || 0}</div>
                <div className="text-white/50 text-[10px]">سلوك سلبي</div>
              </div>
            </div>
          </div>
        )}

        {(r.skills?.recorded > 0) && (
          <div className="bg-slate-800 rounded-xl p-4">
            <h3 className="text-white/70 text-sm mb-3 font-cairo font-bold flex items-center gap-2">
              <Star className="h-4 w-4 text-purple-400" /> بيانات المهارات
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-purple-900/30 rounded-lg p-3 text-center">
                <div className="text-xl font-bold text-purple-400">{r.skills?.recorded}</div>
                <div className="text-white/50 text-[10px]">مهارة مسجلة</div>
              </div>
              <div className="bg-indigo-900/30 rounded-lg p-3 text-center">
                <div className="text-xl font-bold text-indigo-400">{r.skills?.students_count}</div>
                <div className="text-white/50 text-[10px]">طالب</div>
              </div>
            </div>
          </div>
        )}

        <div className="bg-slate-800 rounded-xl p-4">
          <h3 className="text-white/70 text-sm mb-3 font-cairo font-bold flex items-center gap-2">
            <StickyNote className="h-4 w-4 text-amber-400" /> الملاحظات
          </h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-amber-900/30 rounded-lg p-3 text-center">
              <div className="text-xl font-bold text-amber-400">{r.notes?.total || 0}</div>
              <div className="text-white/50 text-[10px]">إجمالي الملاحظات</div>
            </div>
            <div className="bg-orange-900/30 rounded-lg p-3 text-center">
              <div className="text-xl font-bold text-orange-400">{r.notes?.teacher_notes || 0}</div>
              <div className="text-white/50 text-[10px]">ملاحظات المعلم</div>
            </div>
          </div>
        </div>

        {r.needs_attention?.length > 0 && (
          <div className="bg-slate-800 rounded-xl p-4">
            <h3 className="text-white/70 text-sm mb-3 font-cairo font-bold flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-400" /> يحتاج متابعة
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
              <Award className="h-4 w-4 text-amber-400" /> الأكثر تفاعلاً
            </h3>
            {r.top_participants.map((p, i) => (
              <div key={i} className="flex items-center justify-between py-1.5">
                <div className="flex items-center gap-2">
                  <span className="text-amber-400 text-xs font-bold w-5">#{i + 1}</span>
                  <span className="text-white text-sm">{p.name}</span>
                </div>
                <span className="text-green-400 text-xs">{p.correct_answers} ✓ | {p.participations} مشاركة</span>
              </div>
            ))}
          </div>
        )}

        <div className="bg-slate-800 rounded-xl p-4">
          <h3 className="text-white/70 text-sm mb-3 font-cairo font-bold flex items-center gap-2">
            <PenLine className="h-4 w-4 text-cyan-400" /> ملاحظة ختامية
          </h3>
          <Textarea
            value={closingNote}
            onChange={(e) => setClosingNote(e.target.value)}
            placeholder="أضف ملاحظة ختامية للحصة... (اختياري)"
            className="bg-slate-900 border-white/10 text-white placeholder:text-white/30 resize-none text-sm font-cairo"
            rows={3}
          />
          <p className="text-white/30 text-[10px] mt-1">مثال: مستوى فهم الطلاب، تقدم الدرس، خطة المتابعة</p>
        </div>

        <div className="flex gap-3 pt-2">
          <button
            onClick={onBack}
            className="flex-1 h-12 rounded-xl bg-slate-700 hover:bg-slate-600 text-white font-cairo font-bold text-sm transition-all"
          >
            العودة للحصة
          </button>
          <button
            onClick={onConfirm}
            disabled={loading}
            className="flex-1 h-12 rounded-xl bg-red-600 hover:bg-red-500 disabled:opacity-60 text-white font-cairo font-bold text-sm flex items-center justify-center gap-2 transition-all"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
            تأكيد إنهاء الحصة
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
      className={`relative rounded-xl p-2 text-center transition-all duration-150 ${
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
      className={`${color} text-white rounded-lg py-3 px-2 flex flex-col items-center gap-1 transition-all active:scale-95`}
    >
      {icon}
      <span className="text-xs font-medium">{label}</span>
      <span className="text-[10px] opacity-75">{sub}</span>
    </button>
  );
}

function SessionSummary({ summary, sessionInfo, onHome, isRTL }) {
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
    if (!summary.top_participants?.length) return;
    setSendingNotif(true);
    const subjectName = sessionInfo?.subject_name || sessionInfo?.subjectName || '';
    try {
      const promises = summary.top_participants.map(p =>
        api.post('/notifications', {
          title: `تقرير إيجابي — ${p.name}`,
          title_en: `Positive Report — ${p.name}`,
          message: `تميّز ${p.name} في حصة ${subjectName} اليوم — ${p.correct_answers} إجابة صحيحة`,
          message_en: `${p.name} excelled in ${subjectName} today — ${p.correct_answers} correct answers`,
          notification_type: 'communication',
          priority: 'medium',
          recipient_role: 'parent',
          related_entity: 'student',
          related_entity_id: p.student_id,
        })
      );
      const results = await Promise.allSettled(promises);
      const successCount = results.filter(r => r.status === 'fulfilled').length;
      if (successCount > 0) {
        setNotifSent(true);
        toast.success(`تم إرسال ${successCount} تقرير إيجابي لأولياء الأمور`);
        confetti({ particleCount: 50, spread: 60, origin: { y: 0.7 }, colors: ['#10b981', '#34d399', '#6ee7b7'] });
      } else {
        nassaqError('فشل إرسال الإشعارات');
      }
    } catch {
      nassaqError('فشل إرسال الإشعارات');
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
      toast.success(isRTL ? 'تم تصدير التقرير بنجاح' : 'Report exported successfully');
    } catch {
      toast.error(isRTL ? 'فشل تصدير التقرير' : 'Failed to export report');
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
            <h1 className="font-cairo text-2xl font-bold">انتهت الحصة</h1>
            <p className="text-white/70 mt-1">{sessionInfo?.subject_name || sessionInfo?.subjectName} — {sessionInfo?.class_name || sessionInfo?.className}</p>
            <div className="mt-4 text-3xl font-mono font-bold">{summary.duration_minutes || 0} <span className="text-lg text-white/60">دقيقة</span></div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          {[
            { label: 'حاضر', value: summary.present_count, color: 'text-green-400', bg: 'bg-green-900/30', icon: '✅' },
            { label: 'غائب', value: summary.absent_count, color: 'text-red-400', bg: 'bg-red-900/30', icon: '❌' },
            { label: 'أسئلة', value: summary.questions_asked, color: 'text-blue-400', bg: 'bg-blue-900/30', icon: '❓' },
            { label: 'إجابات صحيحة', value: summary.correct_answers, color: 'text-amber-400', bg: 'bg-amber-900/30', icon: '🎯' },
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
              <Heart className="h-4 w-4 text-pink-400" /> السلوك والمهارات
            </h3>
            <div className={`grid ${hasSkills ? 'grid-cols-3' : 'grid-cols-2'} gap-3`}>
              {hasBehaviours && (
                <>
                  <div className="bg-green-900/30 rounded-lg p-3 text-center">
                    <ThumbsUp className="h-5 w-5 text-green-400 mx-auto mb-1" />
                    <div className="text-xl font-bold text-green-400">{summary.positive_behaviours || 0}</div>
                    <div className="text-white/50 text-[10px]">سلوك إيجابي</div>
                  </div>
                  <div className="bg-red-900/30 rounded-lg p-3 text-center">
                    <ThumbsDown className="h-5 w-5 text-red-400 mx-auto mb-1" />
                    <div className="text-xl font-bold text-red-400">{summary.negative_behaviours || 0}</div>
                    <div className="text-white/50 text-[10px]">سلوك سلبي</div>
                  </div>
                </>
              )}
              {hasSkills && (
                <div className="bg-purple-900/30 rounded-lg p-3 text-center">
                  <Star className="h-5 w-5 text-purple-400 mx-auto mb-1" />
                  <div className="text-xl font-bold text-purple-400">{summary.skills_recorded}</div>
                  <div className="text-white/50 text-[10px]">مهارة مسجلة</div>
                </div>
              )}
            </div>
          </div>
        )}

        {summary.participation_rate !== undefined && (
          <div className="bg-slate-800 rounded-xl p-4">
            <div className="flex justify-between text-sm text-white/70 mb-2">
              <span>معدل المشاركة</span>
              <span className="text-white font-bold">{Math.round(summary.participation_rate)}%</span>
            </div>
            <div className="h-2.5 bg-slate-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-brand-turquoise to-brand-navy transition-all"
                style={{ width: `${summary.participation_rate}%` }}
              />
            </div>
          </div>
        )}

        {summary.needs_attention?.length > 0 && (
          <div className="bg-slate-800 rounded-xl p-4">
            <h3 className="text-white/70 text-sm mb-3 flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-400" /> يحتاج متابعة
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
              <Award className="h-4 w-4 text-amber-400" /> الأكثر تفاعلاً
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

            {!notifSent && (
              <button
                onClick={sendParentNotifications}
                disabled={sendingNotif}
                className="w-full mt-3 h-10 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-60 text-white text-xs font-cairo font-bold flex items-center justify-center gap-2 transition-all"
              >
                {sendingNotif ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
                إرسال تقرير إيجابي لأولياء الأمور
              </button>
            )}
            {notifSent && (
              <div className="mt-3 flex items-center justify-center gap-2 text-emerald-400 text-xs">
                <CheckCircle2 className="h-4 w-4" />
                <span>تم الإرسال بنجاح</span>
              </div>
            )}
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={exportReport}
            disabled={exporting}
            className="h-11 rounded-xl bg-slate-700 hover:bg-slate-600 disabled:opacity-60 text-white font-cairo font-bold text-sm flex items-center justify-center gap-2 transition-all"
          >
            {exporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
            تصدير التقرير
          </button>
          <button
            onClick={() => navigate('/teacher/classes?tab=sessions')}
            className="h-11 rounded-xl bg-slate-700 hover:bg-slate-600 text-white font-cairo font-bold text-sm flex items-center justify-center gap-2 transition-all"
          >
            <History className="h-4 w-4" />
            سجل الحصص
          </button>
        </div>

        <button
          onClick={onHome}
          className="w-full h-12 rounded-xl bg-brand-turquoise text-white font-cairo font-bold text-base hover:opacity-90 transition-all shadow-lg shadow-brand-turquoise/20"
        >
          العودة للرئيسية
        </button>
      </div>
    </div>
  );
}
