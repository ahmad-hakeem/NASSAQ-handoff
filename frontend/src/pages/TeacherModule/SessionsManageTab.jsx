import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../../components/ui/dialog';
import { Progress } from '../../components/ui/progress';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  ClipboardList, Calendar, Clock, Search, RefreshCw, Loader2,
  Users, BookOpen, CheckCircle2, XCircle, Play,
  ChevronRight, ChevronLeft, FileText, BarChart3,
  Timer, Activity, Award,
  StickyNote, AlertTriangle
} from 'lucide-react';

import { useTranslation } from '../../contexts/ThemeContext';
const STATUS_MAP = {
  completed: { label: 'مكتملة', labelEn: 'Completed', color: 'bg-green-100 text-green-700 border-green-200' },
  ended: { label: 'منتهية', labelEn: 'Ended', color: 'bg-green-100 text-green-700 border-green-200' },
  in_progress: { label: 'جارية', labelEn: 'Active', color: 'bg-blue-100 text-blue-700 border-blue-200' },
  session_opened: { label: 'مفتوحة', labelEn: 'Opened', color: 'bg-sky-100 text-sky-700 border-sky-200' },
  attendance_in_progress: { label: 'تسجيل حضور', labelEn: 'Attendance', color: 'bg-indigo-100 text-indigo-700 border-indigo-200' },
  attendance_approved: { label: 'حضور مؤكد', labelEn: 'Att. Approved', color: 'bg-cyan-100 text-cyan-700 border-cyan-200' },
  teaching_in_progress: { label: 'تدريس', labelEn: 'Teaching', color: 'bg-teal-100 text-teal-700 border-teal-200' },
  interaction_running: { label: 'تفاعل', labelEn: 'Interaction', color: 'bg-violet-100 text-violet-700 border-violet-200' },
  session_review: { label: 'مراجعة', labelEn: 'Review', color: 'bg-amber-100 text-amber-700 border-amber-200' },
  cancelled: { label: 'ملغاة', labelEn: 'Cancelled', color: 'bg-red-100 text-red-700 border-red-200' },
  auto_closed: { label: 'أُغلقت تلقائياً', labelEn: 'Auto Closed', color: 'bg-orange-100 text-orange-700 border-orange-200' },
  paused: { label: 'متوقفة مؤقتاً', labelEn: 'Paused', color: 'bg-yellow-100 text-yellow-700 border-yellow-200' },
};

export default function SessionsManageTab() {
  const { user, api, isRTL } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [sessions, setSessions] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [dateFilter, setDateFilter] = useState('all');
  const [selectedSession, setSelectedSession] = useState(null);
  const [showDetail, setShowDetail] = useState(false);
  const [sessionReport, setSessionReport] = useState(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [stats, setStats] = useState({ total: 0, completed: 0, cancelled: 0, avg_attendance: 0 });

  const { nassaqError } = useNassaqAlert();
  const teacherId = user?.teacher_id || user?.id;

  const fetchSessions = useCallback(async () => {
    if (!teacherId) return;
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: page.toString(), limit: '20' });
      if (statusFilter !== 'all') params.append('status', statusFilter);

      const res = await api.get(`/teacher/${teacherId}/sessions-history?${params}`);
      const data = res.data;

      if (data?.sessions) {
        setSessions(data.sessions);
        setTotalPages(data.pages || 1);
        setTotalCount(data.total || 0);
        setStats({
          total: data.total || data.sessions.length,
          completed: data.sessions.filter(s => s.status === 'completed' || s.status === 'ended').length,
          cancelled: data.sessions.filter(s => s.status === 'cancelled' || s.status === 'auto_closed').length,
          avg_attendance: data.sessions.length > 0
            ? Math.round(data.sessions.reduce((sum, s) => sum + (s.attendance_rate || 0), 0) / data.sessions.length)
            : 0
        });
      } else {
        const arr = Array.isArray(res.data) ? res.data : [];
        const sorted = arr.sort((a, b) => new Date(b.date || b.created_at) - new Date(a.date || a.created_at));
        setSessions(sorted);
        const completed = sorted.filter(s => s.status === 'completed' || s.status === 'ended').length;
        const cancelled = sorted.filter(s => s.status === 'cancelled').length;
        const avgAtt = sorted.length > 0
          ? Math.round(sorted.reduce((sum, s) => sum + (s.attendance_rate || 0), 0) / sorted.length)
          : 0;
        setStats({ total: sorted.length, completed, cancelled, avg_attendance: avgAtt });
      }
    } catch (error) {
      console.error('Error fetching sessions:', error);
      try {
        const res = await api.get(`/teacher/sessions/${teacherId}`);
        const arr = Array.isArray(res.data) ? res.data : (res.data?.sessions || []);
        const sorted = arr.sort((a, b) => new Date(b.date || b.created_at) - new Date(a.date || a.created_at));
        setSessions(sorted);
        const completed = sorted.filter(s => s.status === 'completed' || s.status === 'ended').length;
        setStats({ total: sorted.length, completed, cancelled: sorted.filter(s => s.status === 'cancelled').length, avg_attendance: 0 });
      } catch (e) {
        console.error('Error fetching sessions:', e);
        setSessions([]);
      }
    } finally {
      setLoading(false);
    }
  }, [api, teacherId, page, statusFilter]);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const filteredSessions = sessions.filter(s => {
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      if (!(s.subject_name || '').toLowerCase().includes(q) &&
          !(s.class_name || '').toLowerCase().includes(q) &&
          !(s.topic || '').toLowerCase().includes(q)) return false;
    }
    if (dateFilter === 'today') {
      const today = new Date().toISOString().split('T')[0];
      if (!(s.date || s.created_at || '').startsWith(today)) return false;
    } else if (dateFilter === 'week') {
      const weekAgo = new Date(); weekAgo.setDate(weekAgo.getDate() - 7);
      if (new Date(s.date || s.created_at) < weekAgo) return false;
    } else if (dateFilter === 'month') {
      const monthAgo = new Date(); monthAgo.setMonth(monthAgo.getMonth() - 1);
      if (new Date(s.date || s.created_at) < monthAgo) return false;
    }
    return true;
  });

  const getStatusBadge = (status) => {
  const { t } = useTranslation();
    const s = STATUS_MAP[status] || { label: status || 'مجدولة', labelEn: status || 'Scheduled', color: 'bg-gray-100 text-gray-700 border-gray-200' };
    return <Badge className={s.color}>{isRTL ? s.label : s.labelEn}</Badge>;
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    try {
      return new Date(dateStr).toLocaleDateString(isRTL ? 'ar-SA' : 'en-US', {
        weekday: 'short', year: 'numeric', month: 'short', day: 'numeric'
      });
    } catch (e) { console.error('Date format error:', e); return dateStr; }
  };

  const openSessionDetail = async (session) => {
    setSelectedSession(session);
    setSessionReport(null);
    setShowDetail(true);
    if (session.status === 'completed' || session.status === 'ended') {
      setReportLoading(true);
      try {
        const res = await api.get(`/session/${session.id || session._id}/report`);
        setSessionReport(res.data);
      } catch (e) {
        console.error('Error fetching session report:', e);
        setSessionReport(null);
      } finally {
        setReportLoading(false);
      }
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <p className="text-sm text-muted-foreground font-tajawal">
          {t('reviewAndManageTeachingSessionRecords')}
        </p>
        <Button onClick={fetchSessions} variant="outline" size="sm" disabled={loading}>
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          <span className={isRTL ? 'mr-2' : 'ml-2'}>{t('refresh')}</span>
        </Button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card className="border-0 shadow-sm bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-800/20">
          <CardContent className="p-3 text-center">
            <ClipboardList className="w-7 h-7 mx-auto text-blue-600 mb-1" />
            <div className="text-2xl font-bold text-blue-700 dark:text-blue-300">{stats.total}</div>
            <div className="text-[10px] text-blue-600 dark:text-blue-400">{t('totalSessions')}</div>
          </CardContent>
        </Card>
        <Card className="border-0 shadow-sm bg-gradient-to-br from-green-50 to-green-100 dark:from-green-900/20 dark:to-green-800/20">
          <CardContent className="p-3 text-center">
            <CheckCircle2 className="w-7 h-7 mx-auto text-green-600 mb-1" />
            <div className="text-2xl font-bold text-green-700 dark:text-green-300">{stats.completed}</div>
            <div className="text-[10px] text-green-600 dark:text-green-400">{t('completed')}</div>
          </CardContent>
        </Card>
        <Card className="border-0 shadow-sm bg-gradient-to-br from-red-50 to-red-100 dark:from-red-900/20 dark:to-red-800/20">
          <CardContent className="p-3 text-center">
            <XCircle className="w-7 h-7 mx-auto text-red-600 mb-1" />
            <div className="text-2xl font-bold text-red-700 dark:text-red-300">{stats.cancelled}</div>
            <div className="text-[10px] text-red-600 dark:text-red-400">{t('cancelled3')}</div>
          </CardContent>
        </Card>
        <Card className="border-0 shadow-sm bg-gradient-to-br from-purple-50 to-purple-100 dark:from-purple-900/20 dark:to-purple-800/20">
          <CardContent className="p-3 text-center">
            <Users className="w-7 h-7 mx-auto text-purple-600 mb-1" />
            <div className="text-2xl font-bold text-purple-700 dark:text-purple-300">{stats.avg_attendance}%</div>
            <div className="text-[10px] text-purple-600 dark:text-purple-400">{t('avgAttendance')}</div>
          </CardContent>
        </Card>
      </div>

      <Card className="border-0 shadow-sm">
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className={`absolute ${isRTL ? 'right-3' : 'left-3'} top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400`} />
              <Input
                placeholder={t('searchBySubjectClassOrTopic')}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className={`${isRTL ? 'pr-10' : 'pl-10'}`}
              />
            </div>
            <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setPage(1); }}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder={t('status2')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('all')}</SelectItem>
                <SelectItem value="completed">{t('completed')}</SelectItem>
                <SelectItem value="ended">{t('ended')}</SelectItem>
                <SelectItem value="cancelled">{t('cancelled3')}</SelectItem>
                <SelectItem value="in_progress">{t('active3')}</SelectItem>
                <SelectItem value="auto_closed">{t('autoClosed')}</SelectItem>
              </SelectContent>
            </Select>
            <Select value={dateFilter} onValueChange={setDateFilter}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder={t('period')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('allTime')}</SelectItem>
                <SelectItem value="today">{t('today2')}</SelectItem>
                <SelectItem value="week">{t('thisWeek2')}</SelectItem>
                <SelectItem value="month">{t('thisMonth2')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <div className="flex justify-center items-center py-16">
          <Loader2 className="w-8 h-8 animate-spin text-brand-turquoise" />
        </div>
      ) : filteredSessions.length === 0 ? (
        <Card className="border-0 shadow-sm">
          <CardContent className="p-12 text-center">
            <ClipboardList className="w-16 h-16 mx-auto text-gray-300 dark:text-gray-600 mb-4" />
            <h3 className="text-lg font-medium text-gray-600 dark:text-gray-400">
              {t('noSessionsRecorded')}
            </h3>
            <p className="text-sm text-gray-400 dark:text-gray-500 mt-2">
              {t('sessionRecordsWillAppearHereAfterYouStartUsingTheS')}
            </p>
            <Button className="mt-4" onClick={() => navigate('/teacher/schedule')}>
              <Calendar className="w-4 h-4" />
              <span className={isRTL ? 'mr-2' : 'ml-2'}>{isRTL ? 'عرض الجدول' : 'View Schedule'}</span>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          <div className="text-sm text-gray-500 dark:text-gray-400 flex items-center gap-2">
            <FileText className="w-4 h-4" />
            {isRTL
              ? `عرض ${filteredSessions.length} حصة من أصل ${totalCount || sessions.length}`
              : `Showing ${filteredSessions.length} of ${totalCount || sessions.length} sessions`}
          </div>
          {filteredSessions.map((session) => (
            <Card
              key={session.id || session._id}
              className="border-0 shadow-sm hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => openSessionDetail(session)}
            >
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4 flex-1">
                    <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                      session.status === 'completed' || session.status === 'ended'
                        ? 'bg-green-100 dark:bg-green-900/30'
                        : session.status === 'cancelled' || session.status === 'auto_closed'
                        ? 'bg-red-100 dark:bg-red-900/30'
                        : 'bg-blue-100 dark:bg-blue-900/30'
                    }`}>
                      <BookOpen className={`w-6 h-6 ${
                        session.status === 'completed' || session.status === 'ended'
                          ? 'text-green-600'
                          : session.status === 'cancelled' || session.status === 'auto_closed'
                          ? 'text-red-600'
                          : 'text-blue-600'
                      }`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-semibold text-gray-900 dark:text-gray-100 truncate">
                          {session.subject_name || (isRTL ? 'حصة دراسية' : 'Class Session')}
                        </h3>
                        {getStatusBadge(session.status)}
                      </div>
                      <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400 flex-wrap">
                        <span className="flex items-center gap-1">
                          <Users className="w-3.5 h-3.5" />
                          {session.class_name || (isRTL ? 'فصل' : 'Class')}
                        </span>
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3.5 h-3.5" />
                          {formatDate(session.date || session.created_at)}
                        </span>
                        {session.duration_minutes > 0 && (
                          <span className="flex items-center gap-1">
                            <Timer className="w-3.5 h-3.5" />
                            {session.duration_minutes} {t('min')}
                          </span>
                        )}
                        {(session.interaction_count > 0 || session.questions_asked > 0) && (
                          <span className="flex items-center gap-1">
                            <Activity className="w-3.5 h-3.5" />
                            {session.interaction_count || session.questions_asked} {t('interactions2')}
                          </span>
                        )}
                      </div>
                      {session.topic && (
                        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1 truncate">{session.topic}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {(session.present_students !== undefined || session.present_count !== undefined || session.attendance_count !== undefined) && (
                      <div className="text-center">
                        <div className="text-lg font-bold text-gray-700 dark:text-gray-300">
                          {session.present_students ?? session.present_count ?? session.attendance_count ?? 0}
                          <span className="text-sm text-gray-400">/{session.total_students || '?'}</span>
                        </div>
                        <div className="text-xs text-gray-400">{t('present3')}</div>
                      </div>
                    )}
                    <ChevronRight className={`w-5 h-5 text-gray-400 ${isRTL ? 'rotate-180' : ''}`} />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-3 pt-4">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage(p => Math.max(1, p - 1))}
              >
                <ChevronRight className={`w-4 h-4 ${isRTL ? '' : 'rotate-180'}`} />
                {isRTL ? 'السابق' : 'Previous'}
              </Button>
              <span className="text-sm text-gray-500">
                {isRTL ? `صفحة ${page} من ${totalPages}` : `Page ${page} of ${totalPages}`}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage(p => p + 1)}
              >
                {t('next')}
                <ChevronLeft className={`w-4 h-4 ${isRTL ? '' : 'rotate-180'}`} />
              </Button>
            </div>
          )}
        </div>
      )}

      <Dialog open={showDetail} onOpenChange={setShowDetail}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader>
            <DialogTitle>{t('sessionReport')}</DialogTitle>
          </DialogHeader>
          {selectedSession && (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-blue-100 flex items-center justify-center">
                  <BookOpen className="w-6 h-6 text-blue-600" />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-lg">
                    {selectedSession.subject_name || (isRTL ? 'حصة' : 'Session')}
                  </h3>
                  <p className="text-sm text-gray-500">{selectedSession.class_name}</p>
                </div>
                {getStatusBadge(selectedSession.status)}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <div className="text-xs text-gray-500 mb-1">{t('date')}</div>
                  <div className="font-medium text-sm">{formatDate(selectedSession.date || selectedSession.created_at)}</div>
                </div>
                <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <div className="text-xs text-gray-500 mb-1">{t('duration')}</div>
                  <div className="font-medium text-sm">
                    {selectedSession.duration_minutes || 0} {t('minutes')}
                  </div>
                </div>
                <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <div className="text-xs text-gray-500 mb-1">{t('attendance2')}</div>
                  <div className="font-medium text-sm">
                    {selectedSession.present_students ?? selectedSession.present_count ?? 0} / {selectedSession.total_students || 0}
                  </div>
                </div>
                <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <div className="text-xs text-gray-500 mb-1">{t('interactions')}</div>
                  <div className="font-medium text-sm">{selectedSession.interaction_count || 0}</div>
                </div>
              </div>

              {reportLoading ? (
                <div className="flex justify-center py-6">
                  <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
                </div>
              ) : sessionReport?.summary ? (
                <>
                  <div className="grid grid-cols-4 gap-2">
                    {(() => {
                      const rpt = sessionReport.summary;
                      const wrongCount = (rpt.questions_asked || 0) - (rpt.correct_answers || 0);
                      const behaviours = sessionReport.students || [];
                      const posB = behaviours.reduce((sum, s) => sum + (s.behaviours?.filter(b => b.category === 'positive').length || 0), 0);
                      const negB = behaviours.reduce((sum, s) => sum + (s.behaviours?.filter(b => b.category === 'negative').length || 0), 0);
                      return [
                        { label: t('correct'), value: rpt.correct_answers || 0, color: 'text-green-600', bg: 'bg-green-50', icon: '✅' },
                        { label: isRTL ? 'خطأ' : 'Wrong', value: wrongCount, color: 'text-red-600', bg: 'bg-red-50', icon: '❌' },
                        { label: t('positive'), value: posB, color: 'text-emerald-600', bg: 'bg-emerald-50', icon: '👍' },
                        { label: t('negative'), value: negB, color: 'text-orange-600', bg: 'bg-orange-50', icon: '⚠️' },
                      ];
                    })().map(item => (
                      <div key={item.label} className={`${item.bg} rounded-lg p-2 text-center`}>
                        <div className="text-sm">{item.icon}</div>
                        <div className={`text-lg font-bold ${item.color}`}>{item.value}</div>
                        <div className="text-gray-500 text-[10px]">{item.label}</div>
                      </div>
                    ))}
                  </div>

                  {sessionReport.summary.attendance_rate !== undefined && (
                    <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-3">
                      <div className="flex justify-between text-sm text-gray-600 dark:text-gray-400 mb-1.5">
                        <span>{t('attendanceRate')}</span>
                        <span className="font-bold">{Math.round(sessionReport.summary.attendance_rate)}%</span>
                      </div>
                      <Progress value={sessionReport.summary.attendance_rate} className="h-2" />
                    </div>
                  )}

                  {sessionReport.students?.length > 0 && (() => {
                    const topStudents = sessionReport.students
                      .map(s => ({ name: s.name, correct: s.answers?.filter(a => a === 'correct').length || 0 }))
                      .sort((a, b) => b.correct - a.correct)
                      .filter(s => s.correct > 0)
                      .slice(0, 5);
                    if (topStudents.length === 0) return null;
                    return (
                      <div className="bg-amber-50 dark:bg-amber-900/20 rounded-lg p-3">
                        <h4 className="text-sm font-medium text-amber-700 dark:text-amber-300 mb-2 flex items-center gap-1.5">
                          <Award className="w-4 h-4" />
                          {t('topParticipants')}
                        </h4>
                        {topStudents.map((p, i) => (
                          <div key={i} className="flex items-center justify-between py-1">
                            <span className="text-sm text-gray-700 dark:text-gray-300">
                              <span className="text-amber-500 font-bold text-xs">#{i + 1}</span> {p.name}
                            </span>
                            <Badge className="bg-amber-100 text-amber-700 text-xs">{p.correct} ✓</Badge>
                          </div>
                        ))}
                      </div>
                    );
                  })()}

                  {sessionReport.students?.length > 0 && (() => {
                    const needsAtt = sessionReport.students.filter(s => {
                      const allWrong = s.answers?.length > 0 && s.answers.every(a => a !== 'correct');
                      const hasBadBehaviour = s.behaviours?.some(b => b.category === 'negative');
                      return allWrong || hasBadBehaviour;
                    }).map(s => ({
                      name: s.name,
                      reason: s.behaviours?.some(b => b.category === 'negative')
                        ? (isRTL ? 'سلوك سلبي' : 'Negative behaviour')
                        : (t('wrongAnswers'))
                    }));
                    if (needsAtt.length === 0) return null;
                    return (
                      <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-3">
                        <h4 className="text-sm font-medium text-red-700 dark:text-red-300 mb-2 flex items-center gap-1.5">
                          <AlertTriangle className="w-4 h-4" />
                          {t('needsAttention')}
                        </h4>
                        {needsAtt.map((s, i) => (
                          <div key={i} className="flex items-center justify-between py-1">
                            <span className="text-sm text-gray-700 dark:text-gray-300">{s.name}</span>
                            <span className="text-xs text-red-600">{s.reason}</span>
                          </div>
                        ))}
                      </div>
                    );
                  })()}

                  {sessionReport.notes?.length > 0 && (
                    <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-3">
                      <h4 className="text-sm font-medium text-blue-700 dark:text-blue-300 mb-2 flex items-center gap-1.5">
                        <StickyNote className="w-4 h-4" />
                        {isRTL ? `الملاحظات (${sessionReport.notes.length})` : `Notes (${sessionReport.notes.length})`}
                      </h4>
                      {sessionReport.notes.slice(0, 5).map((note, i) => (
                        <div key={i} className="py-1 border-b border-blue-100 dark:border-blue-800 last:border-0">
                          <p className="text-xs text-gray-700 dark:text-gray-300">{note.text}</p>
                          <span className="text-[10px] text-blue-500">{note.note_type}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              ) : null}

              {selectedSession.topic && (
                <div className="p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                  <div className="text-xs text-blue-600 mb-1">{t('sessionTopic')}</div>
                  <div className="text-sm font-medium text-blue-800 dark:text-blue-200">{selectedSession.topic}</div>
                </div>
              )}

              <div className="flex gap-2 pt-2">
                {(selectedSession.status === 'in_progress' || selectedSession.status === 'teaching_in_progress' || selectedSession.status === 'interaction_running') && (
                  <Button
                    size="sm"
                    className="flex-1 bg-blue-600 hover:bg-blue-700"
                    onClick={() => { setShowDetail(false); navigate(`/teacher/session/${selectedSession.id || selectedSession._id}`); }}
                  >
                    <Play className="w-4 h-4" />
                    <span className={isRTL ? 'mr-2' : 'ml-2'}>{t('continueSession')}</span>
                  </Button>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1"
                  onClick={() => setShowDetail(false)}
                >
                  {t('close')}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
