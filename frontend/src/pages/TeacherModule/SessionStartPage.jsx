import { useState, useEffect, useMemo } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  Users, CheckCircle2, Loader2, Play,
  ArrowRight, UserCheck, UserX, Sun, Moon,
  LayoutGrid, List, BookOpen, Sparkles, GraduationCap,
  AlertCircle
} from 'lucide-react';

const STATUS_CONFIG = {
  present: {
    label: 'حاضر', labelEn: 'Present', short: 'ح', emoji: '✅',
    dark: { ring: 'ring-emerald-400', bg: 'bg-emerald-500', text: 'text-emerald-400', card: 'border-emerald-500/30 bg-emerald-500/10', glow: 'shadow-emerald-500/20' },
    light: { ring: 'ring-emerald-500', bg: 'bg-emerald-500', text: 'text-emerald-700', card: 'border-emerald-300 bg-emerald-50', glow: 'shadow-emerald-200/40' },
  },
  absent: {
    label: 'غائب', labelEn: 'Absent', short: 'غ', emoji: '❌',
    dark: { ring: 'ring-red-400', bg: 'bg-red-500', text: 'text-red-400', card: 'border-red-500/30 bg-red-500/10', glow: 'shadow-red-500/20' },
    light: { ring: 'ring-red-500', bg: 'bg-red-500', text: 'text-red-700', card: 'border-red-300 bg-red-50', glow: 'shadow-red-200/40' },
  },
};

const MALE_AVATARS = [
  (color) => `<svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="40" cy="40" r="40" fill="${color}"/><circle cx="40" cy="32" r="16" fill="#FBBF24"/><path d="M24 28c0-12 8-18 16-18s16 6 16 18" fill="#1E293B"/><circle cx="33" cy="32" r="2.5" fill="#1E293B"/><circle cx="47" cy="32" r="2.5" fill="#1E293B"/><path d="M36 40c0 2 1.8 3 4 3s4-1 4-3" stroke="#1E293B" stroke-width="1.5" stroke-linecap="round"/><rect x="28" y="48" width="24" height="20" rx="4" fill="#3B82F6"/></svg>`,
  (color) => `<svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="40" cy="40" r="40" fill="${color}"/><circle cx="40" cy="32" r="16" fill="#FCD34D"/><path d="M22 26c2-10 10-16 18-16s16 6 18 16c0 0-6-8-18-8S22 26 22 26z" fill="#374151"/><circle cx="34" cy="32" r="2" fill="#374151"/><circle cx="46" cy="32" r="2" fill="#374151"/><path d="M37 39h6" stroke="#374151" stroke-width="1.5" stroke-linecap="round"/><rect x="28" y="48" width="24" height="20" rx="4" fill="#6366F1"/></svg>`,
  (color) => `<svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="40" cy="40" r="40" fill="${color}"/><circle cx="40" cy="32" r="16" fill="#FDE68A"/><path d="M26 30c0-10 6-18 14-18s14 8 14 18" fill="#0F172A"/><circle cx="34" cy="33" r="2" fill="#0F172A"/><circle cx="46" cy="33" r="2" fill="#0F172A"/><path d="M36 39c1 2 3 3 4 3s3-1 4-3" stroke="#0F172A" stroke-width="1.5" stroke-linecap="round" fill="none"/><rect x="28" y="48" width="24" height="20" rx="4" fill="#0EA5E9"/></svg>`,
];

const FEMALE_AVATARS = [
  (color) => `<svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="40" cy="40" r="40" fill="${color}"/><circle cx="40" cy="32" r="16" fill="#FDE68A"/><path d="M20 34c0-14 9-24 20-24s20 10 20 24c-3-6-10-10-20-10S23 28 20 34z" fill="#7C3AED"/><circle cx="34" cy="32" r="2" fill="#1E293B"/><circle cx="46" cy="32" r="2" fill="#1E293B"/><path d="M36 39c1 2 3 3 4 3s3-1 4-3" stroke="#1E293B" stroke-width="1.5" stroke-linecap="round" fill="none"/><rect x="28" y="48" width="24" height="20" rx="4" fill="#EC4899"/></svg>`,
  (color) => `<svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="40" cy="40" r="40" fill="${color}"/><circle cx="40" cy="32" r="16" fill="#FBBF24"/><path d="M18 36c0-16 10-26 22-26s22 10 22 26c-4-8-12-12-22-12S22 28 18 36z" fill="#831843"/><circle cx="34" cy="32" r="2" fill="#1E293B"/><circle cx="46" cy="32" r="2" fill="#1E293B"/><path d="M36 40c0 2 1.8 3 4 3s4-1 4-3" stroke="#1E293B" stroke-width="1.5" stroke-linecap="round" fill="none"/><rect x="28" y="48" width="24" height="20" rx="4" fill="#F472B6"/></svg>`,
  (color) => `<svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="40" cy="40" r="40" fill="${color}"/><circle cx="40" cy="32" r="16" fill="#FCD34D"/><path d="M22 32c0-14 8-22 18-22s18 8 18 22" fill="#4C1D95"/><ellipse cx="18" cy="32" rx="4" ry="6" fill="#4C1D95"/><ellipse cx="62" cy="32" rx="4" ry="6" fill="#4C1D95"/><circle cx="34" cy="33" r="2" fill="#1E293B"/><circle cx="46" cy="33" r="2" fill="#1E293B"/><path d="M37 39h6" stroke="#1E293B" stroke-width="1.5" stroke-linecap="round"/><rect x="28" y="48" width="24" height="20" rx="4" fill="#A855F7"/></svg>`,
];

function getAvatarSvg(gender, index) {
  const avatars = gender === 'female' ? FEMALE_AVATARS : MALE_AVATARS;
  const bgColor = gender === 'female' ? '#FDF2F8' : '#EFF6FF';
  const fn = avatars[index % avatars.length];
  return `data:image/svg+xml,${encodeURIComponent(fn(bgColor))}`;
}

export default function SessionStartPage() {
  const { user, api, isRTL } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();

  const [step, setStep] = useState('starting');
  const [sessionId, setSessionId] = useState(null);
  const [sessionInfo, setSessionInfo] = useState(null);
  const [students, setStudents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [lessonData, setLessonData] = useState(null);
  const [genderSplit, setGenderSplit] = useState(true);
  const [transitionProgress, setTransitionProgress] = useState(0);

  const { nassaqError } = useNassaqAlert();
  const teacherId = user?.teacher_id || user?.id;

  useEffect(() => {
    if (location.state?.lesson) {
      setLessonData(location.state.lesson);
      return;
    }
    const stored = sessionStorage.getItem('current_lesson');
    if (stored) {
      try { setLessonData(JSON.parse(stored)?.lesson); return; } catch (e) { console.error('Error parsing stored lesson:', e); }
    }
    const t = setTimeout(() => { nassaqError('لم يتم تحديد الحصة'); navigate('/teacher/home'); }, 600);
    return () => clearTimeout(t);
  }, [location.state, navigate]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (lessonData && teacherId) startSession();
  }, [lessonData, teacherId]);

  const handleSessionResult = async (res, isRetry = false) => {
    const sid = res.data?.session_record_id;
    if (!sid) return false;
    const sessionStatus = res.data?.session_status;
    const teachingStatuses = ['teaching_in_progress', 'interaction_running', 'session_review'];
    if (res.data?.resumed && teachingStatuses.includes(sessionStatus)) {
      toast.info(isRTL ? 'استكمال الحصة الجارية' : 'Resuming session');
      navigate('/teacher/session/teach', {
        state: {
          sessionId: sid,
          className: res.data.class_name || lessonData.className,
          subjectName: res.data.subject_name || lessonData.subject,
        },
        replace: true
      });
      return true;
    }
    setSessionId(sid);
    setSessionInfo({
      className: res.data.class_name || lessonData.className,
      subjectName: res.data.subject_name || lessonData.subject,
      teacherName: res.data.teacher_name,
      studentCount: res.data.student_count,
    });
    try {
      await fetchStudents(sid);
    } catch (e) {
      console.error('Error fetching students for session:', e);
    }
    setStep('attendance');
    if (res.data?.resumed) {
      toast.info(isRTL ? 'استكمال الحصة الجارية' : 'Resuming session');
    } else {
      toast.success(isRTL ? 'تم بدء الحصة' : 'Session started');
    }
    return true;
  };

  const startSession = async () => {
    setLoading(true);
    const payload = {
      teacher_id: teacherId,
      schedule_session_id: lessonData.schedule_session_id || lessonData.id,
      class_id: lessonData.classId || lessonData.class_id,
      subject_id: lessonData.subjectId || lessonData.subject_id,
    };
    try {
      const res = await api.post('/session/start', payload);
      if (await handleSessionResult(res)) return;
    } catch (err) {
      const status = err.response?.status;
      const msg = err.response?.data?.detail || '';
      const isSessionConflict = status === 400 || status === 409 || msg.includes('إنهاء') || msg.includes('مسبق') || msg.includes('جارية');
      if (isSessionConflict) {
        toast.info(isRTL ? 'يتم إنشاء حصة جديدة...' : 'Creating new session...');
        try {
          const retryRes = await api.post('/session/start', { ...payload, force_new: true });
          if (await handleSessionResult(retryRes, true)) return;
        } catch (retryErr) {
          const retryMsg = retryErr.response?.data?.detail || msg;
          nassaqError(retryMsg || (isRTL ? 'خطأ في بدء الحصة' : 'Error starting session'));
        }
      } else if (status === 403) {
        nassaqError(msg || (isRTL ? 'ليس لديك صلاحية لبدء هذه الحصة' : 'No permission to start this session'));
      } else {
        nassaqError(msg || (isRTL ? 'خطأ في بدء الحصة' : 'Error starting session'));
      }
      navigate('/teacher/home');
    } finally {
      setLoading(false);
    }
  };

  const fetchStudents = async (sid) => {
    const res = await api.get(`/session/${sid}/students`);
    const list = (res.data?.students || []).map(s => ({
      ...s,
      attendance_status: s.attendance_status === 'absent' ? 'absent' : 'present',
    }));
    setStudents(list);
  };

  const updateAttendance = async (studentId, status) => {
    setStudents(prev => prev.map(s => s.id === studentId ? { ...s, attendance_status: status } : s));
    try {
      await api.put(`/session/${sessionId}/attendance/${studentId}`, { status });
    } catch (e) {
      console.error('Error updating attendance:', e);
      nassaqError('فشل حفظ الحضور');
    }
  };

  const markAll = async (status) => {
    const updated = students.map(s => ({ ...s, attendance_status: status }));
    setStudents(updated);
    try {
      await Promise.all(
        students.map(s => api.put(`/session/${sessionId}/attendance/${s.id}`, { status }))
      );
      toast.success(`تم تحديد الكل: ${STATUS_CONFIG[status].label}`);
    } catch (e) {
      console.error('Error bulk updating attendance:', e);
      nassaqError('خطأ في التحديث الجماعي');
    }
  };

  const approveAttendance = async () => {
    setSaving(true);
    try {
      const res = await api.post(`/session/${sessionId}/attendance/approve`);
      toast.success('تم اعتماد الحضور');
      setStep('done');
      setTransitionProgress(0);
      const startTime = Date.now();
      const duration = 2200;
      const animate = () => {
        const elapsed = Date.now() - startTime;
        const progress = Math.min(elapsed / duration, 1);
        setTransitionProgress(progress);
        if (progress < 1) {
          requestAnimationFrame(animate);
        } else {
          navigate('/teacher/session/teach', {
            state: {
              sessionId,
              sessionInfo,
              startTime: new Date().toISOString(),
              attendanceStats: res.data,
            },
          });
        }
      };
      requestAnimationFrame(animate);
    } catch (e) {
      console.error('Error approving attendance:', e);
      nassaqError('خطأ في اعتماد الحضور');
    } finally {
      setSaving(false);
    }
  };

  const stats = useMemo(() => ({
    total: students.length,
    present: students.filter(s => s.attendance_status !== 'absent').length,
    absent: students.filter(s => s.attendance_status === 'absent').length,
  }), [students]);

  const theme = isDark ? 'dark' : 'light';
  const t = {
    bg: isDark ? 'bg-gradient-to-b from-slate-900 via-slate-900 to-slate-950' : 'bg-gradient-to-b from-gray-50 via-white to-gray-100',
    headerBg: isDark ? 'bg-slate-900/95 backdrop-blur-xl border-white/10' : 'bg-white/95 backdrop-blur-xl border-gray-200',
    text: isDark ? 'text-white' : 'text-gray-900',
    textSub: isDark ? 'text-white/60' : 'text-gray-500',
    textMuted: isDark ? 'text-white/40' : 'text-gray-400',
    cardBg: isDark ? 'bg-slate-800/80 border-white/10' : 'bg-white border-gray-200 shadow-sm',
    sectionBg: isDark ? 'bg-slate-800/50 border-white/5' : 'bg-gray-50 border-gray-200',
    statBg: isDark ? 'bg-slate-800/60 border-white/5' : 'bg-white border-gray-200 shadow-sm',
    progressBg: isDark ? 'bg-slate-700' : 'bg-gray-200',
    btnBg: isDark ? 'bg-white/5 border-white/10 hover:bg-white/10' : 'bg-gray-100 border-gray-200 hover:bg-gray-200',
    btnText: isDark ? 'text-white/60' : 'text-gray-600',
    ringOffset: isDark ? 'ring-offset-slate-900' : 'ring-offset-white',
    divider: isDark ? 'bg-white/10' : 'bg-gray-200',
  };

  if (step === 'starting' || (loading && !students.length)) {
    return (
      <div className={`min-h-screen ${t.bg} flex items-center justify-center`} dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="text-center">
          <div className="relative mx-auto w-28 h-28 mb-8">
            <div className="absolute inset-0 rounded-full bg-brand-turquoise/20 animate-ping" />
            <div className="absolute inset-2 rounded-full bg-brand-turquoise/10 animate-pulse" />
            <div className="relative w-28 h-28 rounded-full bg-gradient-to-br from-brand-turquoise to-cyan-600 flex items-center justify-center shadow-2xl shadow-brand-turquoise/40">
              <Play className="h-12 w-12 text-white drop-shadow-lg" />
            </div>
          </div>
          <h2 className={`font-cairo text-3xl font-bold ${t.text} mb-3`}>جارٍ بدء الحصة…</h2>
          <p className={`${t.textSub} text-base mb-6 font-tajawal`}>يتم التحقق وإعداد سجل الحضور</p>
          <div className="flex items-center justify-center gap-3">
            <div className="w-2.5 h-2.5 rounded-full bg-brand-turquoise animate-bounce" style={{ animationDelay: '0ms' }} />
            <div className="w-2.5 h-2.5 rounded-full bg-brand-turquoise animate-bounce" style={{ animationDelay: '150ms' }} />
            <div className="w-2.5 h-2.5 rounded-full bg-brand-turquoise animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
        </div>
      </div>
    );
  }

  if (step === 'done') {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center overflow-hidden" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="absolute inset-0">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-brand-turquoise/5 animate-pulse" />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] rounded-full bg-brand-turquoise/10 animate-pulse" style={{ animationDelay: '300ms' }} />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[200px] h-[200px] rounded-full bg-brand-turquoise/15 animate-pulse" style={{ animationDelay: '600ms' }} />
        </div>

        <div className="relative text-center space-y-8 animate-fade-in z-10 px-4">
          <div className="relative mx-auto w-36 h-36">
            <div className="absolute inset-0 rounded-full bg-gradient-to-br from-brand-turquoise/30 to-cyan-500/20 animate-spin-slow" style={{ animationDuration: '3s' }} />
            <div className="absolute inset-2 rounded-full bg-gradient-to-br from-brand-turquoise to-cyan-500 flex items-center justify-center shadow-2xl shadow-brand-turquoise/50">
              <BookOpen className="h-16 w-16 text-white drop-shadow-lg" />
            </div>
          </div>

          <div className="space-y-4">
            <h1 className="font-cairo text-5xl font-black text-white tracking-tight">
              ابدأ الشرح الآن
            </h1>
            <p className="text-brand-turquoise/80 text-xl font-tajawal">جارٍ تجهيز واجهة التفاعل...</p>
          </div>

          <div className="flex items-center justify-center gap-4 text-white/50 text-sm font-tajawal">
            <span className="flex items-center gap-2 bg-white/5 px-4 py-2 rounded-full border border-white/10">
              <Users className="h-4 w-4 text-emerald-400" /> {stats.present} حاضر
            </span>
            <span className="flex items-center gap-2 bg-white/5 px-4 py-2 rounded-full border border-white/10">
              <GraduationCap className="h-4 w-4 text-brand-turquoise" /> {sessionInfo?.subjectName}
            </span>
            <span className="flex items-center gap-2 bg-white/5 px-4 py-2 rounded-full border border-white/10">
              {sessionInfo?.className}
            </span>
          </div>

          <div className="w-72 mx-auto">
            <div className="h-2 bg-white/10 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-brand-turquoise to-cyan-400 rounded-full transition-all duration-100"
                style={{ width: `${transitionProgress * 100}%` }}
              />
            </div>
          </div>

          <div className="flex items-center justify-center gap-2">
            <Sparkles className="h-6 w-6 text-brand-turquoise animate-pulse" />
          </div>
        </div>
      </div>
    );
  }

  const males = students.filter(s => s.gender !== 'female');
  const females = students.filter(s => s.gender === 'female');
  const hasBothGenders = females.length > 0 && males.length > 0;
  const showSplit = genderSplit && hasBothGenders;

  const presentPct = stats.total > 0 ? Math.round((stats.present / stats.total) * 100) : 0;

  return (
    <div className={`min-h-screen ${t.bg} flex flex-col transition-colors duration-300`} dir={isRTL ? 'rtl' : 'ltr'}>
      <header className={`${t.headerBg} border-b px-4 py-3 sticky top-0 z-20 transition-colors duration-300`}>
        <div className="max-w-5xl mx-auto flex items-center justify-between gap-3">
          <button onClick={() => navigate('/teacher')} className={`${t.textSub} ${isDark ? 'hover:text-white' : 'hover:text-gray-900'} p-2 rounded-xl ${t.btnBg} transition-all border`}>
            <ArrowRight className="h-5 w-5" />
          </button>

          <div className="text-center flex-1">
            <div className="flex items-center justify-center gap-2">
              <div className="w-6 h-6 rounded-lg bg-brand-turquoise/20 flex items-center justify-center">
                <GraduationCap className="h-3.5 w-3.5 text-brand-turquoise" />
              </div>
              <h1 className={`font-cairo font-bold ${t.text} text-base`}>{sessionInfo?.subjectName}</h1>
            </div>
            <p className={`${t.textSub} text-xs font-tajawal mt-0.5`}>{sessionInfo?.className}</p>
          </div>

          <div className="flex items-center gap-2">
            {hasBothGenders && (
              <button
                onClick={() => setGenderSplit(v => !v)}
                className={`p-2 rounded-xl transition-all border ${genderSplit
                  ? 'bg-brand-turquoise/20 text-brand-turquoise border-brand-turquoise/30'
                  : `${t.btnBg} ${t.btnText}`
                }`}
                title={genderSplit ? 'عرض موحد' : 'تقسيم حسب الجنس'}
              >
                {genderSplit ? <LayoutGrid className="h-4 w-4" /> : <List className="h-4 w-4" />}
              </button>
            )}
            <button
              onClick={toggleTheme}
              className={`p-2 rounded-xl transition-all border ${t.btnBg} ${t.btnText}`}
              title={isDark ? 'الوضع الفاتح' : 'الوضع الداكن'}
            >
              {isDark ? <Sun className="h-4 w-4 text-amber-400" /> : <Moon className="h-4 w-4" />}
            </button>
            <Badge className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-cairo text-xs">جارية</Badge>
          </div>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto p-4 space-y-5">

          <div className={`rounded-2xl border ${t.cardBg} p-5 transition-colors duration-300`}>
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-turquoise to-cyan-600 flex items-center justify-center shadow-lg shadow-brand-turquoise/20">
                  <Users className="h-5 w-5 text-white" />
                </div>
                <div>
                  <span className={`font-cairo font-bold ${t.text} text-sm block`}>سجل الحضور</span>
                  <span className={`${t.textMuted} text-xs font-tajawal`}>{stats.total} طالب</span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className={`px-4 py-2 rounded-xl ${isDark ? 'bg-emerald-500/15' : 'bg-emerald-50'} border ${isDark ? 'border-emerald-500/20' : 'border-emerald-200'}`}>
                  <span className={`font-mono font-bold text-2xl ${isDark ? 'text-emerald-400' : 'text-emerald-600'}`}>{presentPct}%</span>
                  <span className={`${t.textSub} text-xs ms-1 font-tajawal`}>حضور</span>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 mb-5">
              {[
                { key: 'present', icon: UserCheck, label: 'حاضر', gradient: 'from-emerald-500 to-emerald-600', numColor: isDark ? 'text-emerald-400' : 'text-emerald-600' },
                { key: 'absent', icon: UserX, label: 'غائب', gradient: 'from-red-500 to-red-600', numColor: isDark ? 'text-red-400' : 'text-red-600' },
              ].map(s => (
                <div key={s.key} className={`${t.statBg} rounded-xl p-3 text-center border transition-all duration-300 hover:scale-[1.02]`}>
                  <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${s.gradient} flex items-center justify-center mx-auto mb-2 shadow-sm`}>
                    <s.icon className="h-4 w-4 text-white" />
                  </div>
                  <div className={`text-2xl font-bold ${s.numColor} font-mono`}>{stats[s.key]}</div>
                  <div className={`${t.textMuted} text-[10px] mt-1 font-cairo font-medium`}>{s.label}</div>
                </div>
              ))}
            </div>

            <div className={`h-3 ${t.progressBg} rounded-full overflow-hidden flex transition-colors duration-300`}>
              {stats.total > 0 && <>
                <div className="bg-gradient-to-r from-emerald-500 to-emerald-400 transition-all duration-500 rounded-s-full" style={{ width: `${(stats.present / stats.total) * 100}%` }} />
                <div className="bg-gradient-to-r from-red-500 to-red-400 transition-all duration-500 rounded-e-full" style={{ width: `${(stats.absent / stats.total) * 100}%` }} />
              </>}
            </div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => markAll('present')}
              className="flex-1 h-12 rounded-xl bg-gradient-to-r from-emerald-600/20 to-emerald-500/10 border border-emerald-500/30 text-emerald-500 text-sm font-medium font-cairo hover:from-emerald-600/30 hover:to-emerald-500/20 active:scale-[0.98] transition-all flex items-center justify-center gap-2"
            >
              <UserCheck className="h-4 w-4" /> الكل حاضر
            </button>
            <button
              onClick={() => markAll('absent')}
              className="flex-1 h-12 rounded-xl bg-gradient-to-r from-red-600/20 to-red-500/10 border border-red-500/30 text-red-500 text-sm font-medium font-cairo hover:from-red-600/30 hover:to-red-500/20 active:scale-[0.98] transition-all flex items-center justify-center gap-2"
            >
              <UserX className="h-4 w-4" /> الكل غائب
            </button>
          </div>

          {showSplit ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <GenderSection
                students={isRTL ? males : females}
                gender={isRTL ? 'male' : 'female'}
                label={isRTL ? 'طلاب' : 'طالبات'}
                theme={theme}
                t={t}
                isDark={isDark}
                onUpdate={updateAttendance}
              />
              <GenderSection
                students={isRTL ? females : males}
                gender={isRTL ? 'female' : 'male'}
                label={isRTL ? 'طالبات' : 'طلاب'}
                theme={theme}
                t={t}
                isDark={isDark}
                onUpdate={updateAttendance}
              />
            </div>
          ) : (
            <div>
              <div className="flex items-center gap-2 mb-4">
                <div className="w-8 h-8 rounded-xl bg-brand-turquoise/20 flex items-center justify-center">
                  <Users className="h-4 w-4 text-brand-turquoise" />
                </div>
                <span className={`${t.text} text-sm font-cairo font-bold`}>الطلاب ({stats.total})</span>
                <div className={`flex-1 h-px ${t.divider}`} />
                <span className={`${t.textMuted} text-[10px] font-cairo flex items-center gap-1`}>
                  اضغط على الطالب لتسجيل غياب
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {students.map((student, idx) => (
                  <StudentCard key={student.id} student={student} index={idx} onUpdate={updateAttendance} theme={theme} t={t} isDark={isDark} />
                ))}
              </div>
            </div>
          )}

          {students.length === 0 && (
            <div className={`text-center py-20 ${t.textMuted}`}>
              <div className="w-24 h-24 rounded-2xl bg-gray-500/10 flex items-center justify-center mx-auto mb-5">
                <AlertCircle className="h-12 w-12 opacity-30" />
              </div>
              <p className="font-cairo text-xl font-bold mb-2">لا يوجد طلاب في هذا الفصل</p>
              <p className={`${t.textMuted} text-sm font-tajawal`}>تأكد من إضافة الطلاب إلى الفصل من لوحة الإدارة</p>
            </div>
          )}

          <div className="h-24" />
        </div>
      </div>

      <div className={`sticky bottom-0 p-4 ${isDark ? 'bg-gradient-to-t from-slate-900 via-slate-900/95 to-transparent' : 'bg-gradient-to-t from-white via-white/95 to-transparent'}`}>
        <div className="max-w-5xl mx-auto">
          <button
            onClick={approveAttendance}
            disabled={saving || students.length === 0}
            className="w-full h-14 rounded-2xl bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-400 hover:to-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-cairo font-bold text-lg flex items-center justify-center gap-3 transition-all shadow-xl shadow-emerald-500/30 active:scale-[0.98]"
          >
            {saving ? (
              <Loader2 className="h-6 w-6 animate-spin" />
            ) : (
              <CheckCircle2 className="h-6 w-6" />
            )}
            اعتماد الحضور والبدء
          </button>
        </div>
      </div>
    </div>
  );
}

function GenderSection({ students, gender, label, theme, t, isDark, onUpdate }) {
  const isMale = gender === 'male';

  const accentGradient = isMale ? 'from-sky-500 to-blue-600' : 'from-pink-500 to-rose-600';
  const accentBg = isMale ? 'bg-sky-500/20' : 'bg-pink-500/20';
  const badgeClass = isMale
    ? `bg-sky-500/20 ${isDark ? 'text-sky-400' : 'text-sky-600'} border-sky-500/30 text-xs`
    : `bg-pink-500/20 ${isDark ? 'text-pink-400' : 'text-pink-600'} border-pink-500/30 text-xs`;
  const headerBorder = isMale
    ? (isDark ? 'border-sky-500/20' : 'border-sky-200')
    : (isDark ? 'border-pink-500/20' : 'border-pink-200');

  return (
    <div className={`rounded-2xl border ${t.sectionBg} overflow-hidden transition-colors duration-300`}>
      <div className={`flex items-center gap-3 p-4 border-b ${headerBorder}`}>
        <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${accentGradient} flex items-center justify-center shadow-sm`}>
          <span className="text-lg">{isMale ? '👦' : '👧'}</span>
        </div>
        <span className={`${t.text} text-sm font-cairo font-bold`}>{label}</span>
        <Badge className={badgeClass}>
          {students.length}
        </Badge>
        <div className={`flex-1 h-px ${isDark ? 'bg-white/10' : 'bg-gray-200'}`} />
      </div>
      <div className="p-4 space-y-3">
        {students.map((student, idx) => (
          <StudentCard key={student.id} student={student} index={idx} onUpdate={onUpdate} theme={theme} t={t} isDark={isDark} />
        ))}
      </div>
    </div>
  );
}

function StudentCard({ student, index, onUpdate, theme, t, isDark }) {
  const status = student.attendance_status || 'present';
  const isAbsent = status === 'absent';
  const cfg = STATUS_CONFIG[isAbsent ? 'absent' : 'present'];
  const style = cfg[theme] || cfg.dark;

  const avatarSrc = student.avatar_url || getAvatarSvg(student.gender || 'male', index);
  const isFemale = student.gender === 'female';

  const handleToggle = () => {
    onUpdate(student.id, isAbsent ? 'present' : 'absent');
  };

  return (
    <button
      onClick={handleToggle}
      className={`w-full rounded-xl border ${style.card} overflow-hidden transition-all duration-200 shadow-md ${style.glow} active:scale-[0.97] flex items-center gap-3 p-3 text-start`}
    >
      <div className="relative flex-shrink-0">
        <div className={`w-12 h-12 rounded-full ring-2 ${style.ring} ring-offset-2 ${t.ringOffset} overflow-hidden transition-all ${isAbsent ? 'opacity-50 grayscale' : ''}`}>
          <img
            src={avatarSrc}
            alt={student.full_name}
            className="w-full h-full object-cover"
            onError={(e) => {
              e.target.src = getAvatarSvg(student.gender || 'male', index);
            }}
          />
        </div>
        <div className={`absolute -bottom-0.5 -end-0.5 w-5 h-5 rounded-full ${style.bg} flex items-center justify-center border-2 ${isDark ? 'border-slate-900' : 'border-white'} shadow-sm`}>
          <span className="text-white text-[8px] font-bold">{cfg.short}</span>
        </div>
      </div>

      <div className="flex-1 min-w-0">
        <p className={`${t.text} font-medium text-sm truncate font-cairo ${isAbsent ? 'line-through opacity-60' : ''}`}>
          {student.full_name || `طالب ${index + 1}`}
        </p>
        <div className="flex items-center gap-2 mt-0.5">
          <span className={`${t.textMuted} text-xs font-mono`}>{student.student_code}</span>
          {student.gender && (
            <span className={`text-[10px] px-1.5 py-0.5 rounded-md font-cairo ${
              isFemale
                ? (isDark ? 'bg-pink-500/15 text-pink-400' : 'bg-pink-100 text-pink-600')
                : (isDark ? 'bg-sky-500/15 text-sky-400' : 'bg-sky-100 text-sky-600')
            }`}>
              {isFemale ? 'طالبة' : 'طالب'}
            </span>
          )}
        </div>
      </div>

      <Badge className={`${style.bg} text-white text-xs font-cairo shadow-sm`}>{cfg.label}</Badge>
    </button>
  );
}
