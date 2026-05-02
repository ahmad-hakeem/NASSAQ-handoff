import { useState, useEffect, useMemo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import { Sidebar } from '../components/layout/Sidebar';
import { HakimAssistant } from '../components/hakim/HakimAssistant';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { CircularProgressRing } from '../components/ui/CircularProgressRing';
import { toast } from 'sonner';
import {
  CalendarCheck,
  Users,
  Clock,
  FileText,
  Sun,
  Moon,
  Globe,
  RefreshCw,
  Save,
  CheckCircle,
  XCircle,
  Briefcase,
  Shield,
} from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '../components/ui/popover';
import { Textarea } from '../components/ui/textarea';
import { History, UserCircle2, Undo2 } from 'lucide-react';

const statusConfig = {
  present: {
    label: { ar: 'حاضر', en: 'Present' },
    icon: CheckCircle,
    color: 'bg-green-500',
    bgColor: 'bg-green-100 dark:bg-green-900/30',
    textColor: 'text-green-700 dark:text-green-400',
  },
  absent: {
    label: { ar: 'غائب', en: 'Absent' },
    icon: XCircle,
    color: 'bg-red-500',
    bgColor: 'bg-red-100 dark:bg-red-900/30',
    textColor: 'text-red-700 dark:text-red-400',
  },
  late: {
    label: { ar: 'متأخر', en: 'Late' },
    icon: Clock,
    color: 'bg-yellow-500',
    bgColor: 'bg-yellow-100 dark:bg-yellow-900/30',
    textColor: 'text-yellow-700 dark:text-yellow-400',
    hidden: true,
  },
  excused: {
    label: { ar: 'بعذر', en: 'Excused' },
    icon: FileText,
    color: 'bg-blue-500',
    bgColor: 'bg-blue-100 dark:bg-blue-900/30',
    textColor: 'text-blue-700 dark:text-blue-400',
  },
};

// ─── Audit-trail helpers ──────────────────────────────────────────────────
function formatArabicRelativeTime(iso) {
  if (!iso) return '';
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return '';
  const diffSec = Math.round((Date.now() - then.getTime()) / 1000);
  if (diffSec < 5) return 'الآن';
  if (diffSec < 60) return `قبل ${diffSec} ثانية`;
  const mins = Math.round(diffSec / 60);
  if (mins < 60) return `قبل ${mins} دقيقة`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `قبل ${hours} ساعة`;
  const days = Math.round(hours / 24);
  if (days < 7) return `قبل ${days} يوم`;
  return then.toLocaleDateString('ar-EG');
}

function describeHistoryEntry(entry) {
  if (!entry) return '';
  if (entry.action === 'undone') return 'ألغى الغياب';
  if (entry.status === 'absent') return 'سجَّل غياباً';
  if (entry.status === 'present') return 'سجَّل حضوراً';
  if (entry.status === 'late') return 'سجَّل تأخراً';
  if (entry.status === 'excused') return 'سجَّل بعذر';
  return 'حدَّث الحالة';
}

export const TeacherAttendancePage = () => {
  const { t } = useTranslation();
  const { api } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  const { nassaqWarning, nassaqError } = useNassaqAlert();

  const todayDate = useMemo(() => new Date().toISOString().split('T')[0], []);

  const [teachersList, setTeachersList] = useState([]);
  const [adminsList, setAdminsList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [savingTeachers, setSavingTeachers] = useState(false);
  const [savingAdmins, setSavingAdmins] = useState(false);

  const [attendanceRecords, setAttendanceRecords] = useState({});
  const [notesDialog, setNotesDialog] = useState({ open: false, subjectId: null });
  const [noteText, setNoteText] = useState('');
  const [historyByTeacher, setHistoryByTeacher] = useState({});
  const [historyLoading, setHistoryLoading] = useState({});

  useEffect(() => {
    fetchAllStaffWithAttendance();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchAllStaffWithAttendance = async () => {
    try {
      setLoading(true);

      const [teachersRes, adminsRes, attendanceRes] = await Promise.all([
        api.get('/teachers').catch(() => ({ data: [] })),
        api.get('/teacher-attendance/school-admins').catch(() => ({ data: [] })),
        api.get(`/teacher-attendance?date=${todayDate}`).catch(() => ({ data: [] })),
      ]);

      setTeachersList(Array.isArray(teachersRes.data) ? teachersRes.data : []);
      setAdminsList(Array.isArray(adminsRes.data) ? adminsRes.data : []);

      const records = {};
      (attendanceRes.data || []).forEach((record) => {
        records[record.teacher_id] = {
          status: record.status,
          notes: record.notes || '',
          check_in_time: record.check_in_time,
          recorded_by: record.recorded_by || null,
          recorded_by_name: record.recorded_by_name || '',
          recorded_at: record.recorded_at || record.updated_at || null,
        };
      });
      setAttendanceRecords(records);
      setHistoryByTeacher({});
    } catch (error) {
      console.error('Failed to fetch staff attendance data:', error);
      nassaqError(t('failedToLoadTeachersData'));
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = (subjectId, status) => {
    const now = new Date().toTimeString().slice(0, 5);
    setAttendanceRecords((prev) => ({
      ...prev,
      [subjectId]: {
        ...prev[subjectId],
        status,
        check_in_time: status === 'present' ? now : null,
      },
    }));
  };

  const loadTeacherHistory = async (subjectId) => {
    if (!subjectId) return;
    setHistoryLoading((prev) => ({ ...prev, [subjectId]: true }));
    try {
      const res = await api.get('/teacher-attendance/history', {
        params: { teacher_id: subjectId, date: todayDate },
      });
      setHistoryByTeacher((prev) => ({
        ...prev,
        [subjectId]: Array.isArray(res.data?.history) ? res.data.history : [],
      }));
    } catch (error) {
      setHistoryByTeacher((prev) => ({ ...prev, [subjectId]: [] }));
    } finally {
      setHistoryLoading((prev) => ({ ...prev, [subjectId]: false }));
    }
  };

  const handleNotesSave = () => {
    if (notesDialog.subjectId) {
      setAttendanceRecords((prev) => ({
        ...prev,
        [notesDialog.subjectId]: {
          ...prev[notesDialog.subjectId],
          notes: noteText,
        },
      }));
    }
    setNotesDialog({ open: false, subjectId: null });
    setNoteText('');
  };

  const saveSection = async (sectionMembers, subjectType) => {
    const records = sectionMembers
      .map((member) => ({ member, data: attendanceRecords[member.id] }))
      .filter(({ data }) => data?.status)
      .map(({ member, data }) => ({
        teacher_id: member.id,
        date: todayDate,
        status: data.status,
        check_in_time: data.check_in_time || null,
        notes: data.notes || '',
        subject_type: subjectType,
      }));

    if (records.length === 0) {
      nassaqWarning(t('noAttendanceRecordsToSave'));
      return;
    }

    const unrecorded = sectionMembers.filter(
      (member) => !attendanceRecords[member.id]?.status
    );
    if (unrecorded.length > 0) {
      const noun = subjectType === 'admin'
        ? (isRTL ? 'إداري' : 'admin')
        : (isRTL ? 'معلم' : 'teacher');
      nassaqWarning(
        isRTL
          ? `يوجد ${unrecorded.length} ${noun} لم يتم تسجيل حضورهم بعد`
          : `${unrecorded.length} ${noun}${unrecorded.length === 1 ? '' : 's'} have not been recorded yet`
      );
    }

    const setSaving = subjectType === 'admin' ? setSavingAdmins : setSavingTeachers;
    setSaving(true);
    try {
      const BATCH_SIZE = 50;
      let totalSaved = 0;
      let totalUpdated = 0;
      for (let i = 0; i < records.length; i += BATCH_SIZE) {
        const batch = records.slice(i, i + BATCH_SIZE);
        const response = await api.post('/teacher-attendance/bulk', { records: batch });
        totalSaved += response.data?.saved || 0;
        totalUpdated += response.data?.updated || 0;
      }

      const totalCount = totalSaved + totalUpdated;
      const noun = subjectType === 'admin'
        ? (isRTL ? 'إداري' : 'admin')
        : (isRTL ? 'معلم' : 'teacher');
      toast.success(
        isRTL
          ? `تم حفظ حضور ${totalCount} ${noun} بنجاح`
          : `Saved attendance for ${totalCount} ${noun}${totalCount === 1 ? '' : 's'}`
      );

      const savedIds = new Set(sectionMembers.map((m) => m.id));
      await refreshRecordsForIds(savedIds);
    } catch (error) {
      console.error('Failed to save attendance:', error);
      const detail = error.response?.data?.detail;
      nassaqError(detail || (t('failedToSaveAttendance')));
    } finally {
      setSaving(false);
    }
  };

  const refreshRecordsForIds = async (idsToRefresh) => {
    try {
      const attendanceRes = await api.get(`/teacher-attendance?date=${todayDate}`);
      const fresh = {};
      (attendanceRes.data || []).forEach((record) => {
        if (!idsToRefresh.has(record.teacher_id)) return;
        fresh[record.teacher_id] = {
          status: record.status,
          notes: record.notes || '',
          check_in_time: record.check_in_time,
          recorded_by: record.recorded_by || null,
          recorded_by_name: record.recorded_by_name || '',
          recorded_at: record.recorded_at || record.updated_at || null,
        };
      });
      setAttendanceRecords((prev) => {
        const merged = { ...prev };
        Object.keys(fresh).forEach((id) => {
          merged[id] = fresh[id];
        });
        return merged;
      });
      setHistoryByTeacher((prev) => {
        const next = { ...prev };
        idsToRefresh.forEach((id) => {
          delete next[id];
        });
        return next;
      });
    } catch (error) {
      // best-effort refresh
    }
  };

  const handleMarkAllPresent = (sectionMembers, subjectLabelArSingular, subjectLabelEnSingular) => {
    const now = new Date().toTimeString().slice(0, 5);
    setAttendanceRecords((prev) => {
      const next = { ...prev };
      sectionMembers.forEach((member) => {
        next[member.id] = {
          status: 'present',
          notes: next[member.id]?.notes || '',
          check_in_time: next[member.id]?.check_in_time || now,
          recorded_by: next[member.id]?.recorded_by || null,
          recorded_by_name: next[member.id]?.recorded_by_name || '',
          recorded_at: next[member.id]?.recorded_at || null,
        };
      });
      return next;
    });
    toast.success(
      isRTL
        ? `تم تحديد ${sectionMembers.length} ${subjectLabelArSingular} حاضر`
        : `Marked ${sectionMembers.length} ${subjectLabelEnSingular}${sectionMembers.length === 1 ? '' : 's'} as present`
    );
  };

  const overallStats = useMemo(() => {
    const allMembers = [...teachersList, ...adminsList];
    const recorded = allMembers.filter(
      (m) => attendanceRecords[m.id]?.status
    );
    const present = recorded.filter(
      (m) => ['present', 'late'].includes(attendanceRecords[m.id]?.status)
    ).length;
    const total = allMembers.length;
    const recordedCount = recorded.length;
    const rate = recordedCount > 0
      ? Math.round((present / recordedCount) * 100)
      : 0;
    return { total, recorded: recordedCount, present, rate };
  }, [teachersList, adminsList, attendanceRecords]);

  const renderStaffCard = (member) => {
    const currentStatus = attendanceRecords[member.id]?.status;
    const statusInfo = currentStatus ? statusConfig[currentStatus] : null;
    const checkInTime = attendanceRecords[member.id]?.check_in_time;
    const recordedByName = attendanceRecords[member.id]?.recorded_by_name;
    const recordedAt = attendanceRecords[member.id]?.recorded_at;

    return (
      <Card
        key={member.id}
        className={`transition-all ${statusInfo ? statusInfo.bgColor : 'bg-muted/30'}`}
        data-testid={`teacher-card-${member.id}`}
      >
        <CardContent className="p-4">
          <div className="flex items-center gap-3 mb-3">
            <Avatar className="h-12 w-12">
              <AvatarImage src={member.avatar_url} />
              <AvatarFallback className="bg-brand-navy text-white">
                {member.full_name?.charAt(0)}
              </AvatarFallback>
            </Avatar>
            <div className="flex-1 min-w-0">
              <h4 className="font-medium truncate">{member.full_name}</h4>
              <p className="text-xs text-muted-foreground truncate">
                {member.specialization}
              </p>
            </div>
            <div className="text-end">
              {statusInfo && (
                <Badge className={`${statusInfo.color} text-white`}>
                  {isRTL ? statusInfo.label.ar : statusInfo.label.en}
                </Badge>
              )}
              {checkInTime && (
                <p className="text-xs text-muted-foreground mt-1">{checkInTime}</p>
              )}
            </div>
          </div>

          {/* Status Buttons */}
          <div className="grid grid-cols-4 gap-2">
            {Object.entries(statusConfig)
              .filter(([, c]) => !c.hidden)
              .map(([status, config]) => {
                const Icon = config.icon;
                const isSelected = currentStatus === status;
                return (
                  <Button
                    key={status}
                    variant={isSelected ? 'default' : 'outline'}
                    size="sm"
                    className={`rounded-xl ${isSelected ? config.color : ''}`}
                    onClick={() => handleStatusChange(member.id, status)}
                    data-testid={`status-btn-${status}-${member.id}`}
                  >
                    <Icon className="h-4 w-4" />
                  </Button>
                );
              })}
          </div>

          {currentStatus && recordedByName && (
            <div className="mt-2 flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
              <div className="flex items-center gap-1 min-w-0">
                <UserCircle2 className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">
                  <span className="font-semibold">سجَّله:</span>{' '}
                  {recordedByName}
                  {recordedAt && (
                    <span className="opacity-70">
                      {' '}
                      • {formatArabicRelativeTime(recordedAt)}
                    </span>
                  )}
                </span>
              </div>
              <Popover
                onOpenChange={(open) => {
                  if (open && historyByTeacher[member.id] === undefined) {
                    loadTeacherHistory(member.id);
                  }
                }}
              >
                <PopoverTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2 text-[11px]"
                    data-testid={`history-btn-${member.id}`}
                  >
                    <History className="h-3 w-3 me-1" />
                    السجل
                  </Button>
                </PopoverTrigger>
                <PopoverContent align="end" className="w-72 p-3" dir="rtl">
                  <div className="text-xs font-semibold mb-2 text-foreground">
                    آخر التغييرات (حتى ٣)
                  </div>
                  {historyLoading[member.id] ? (
                    <div className="text-xs text-muted-foreground py-2">
                      جارٍ التحميل…
                    </div>
                  ) : (historyByTeacher[member.id] || []).length === 0 ? (
                    <div className="text-xs text-muted-foreground py-2">
                      لا توجد تغييرات مسجَّلة لهذا اليوم.
                    </div>
                  ) : (
                    <ul className="space-y-2">
                      {(historyByTeacher[member.id] || []).map((entry, idx) => (
                        <li
                          key={`${member.id}-h-${idx}`}
                          className="flex items-start gap-2 text-xs border-b border-border last:border-b-0 pb-1.5 last:pb-0"
                        >
                          {entry.action === 'undone' ? (
                            <Undo2 className="h-3.5 w-3.5 mt-0.5 text-emerald-600 shrink-0" />
                          ) : (
                            <UserCircle2 className="h-3.5 w-3.5 mt-0.5 text-brand-navy shrink-0" />
                          )}
                          <div className="min-w-0 flex-1">
                            <p className="text-foreground">
                              <span className="font-semibold">
                                {entry.actor_name || '—'}
                              </span>{' '}
                              <span className="text-muted-foreground">
                                {describeHistoryEntry(entry)}
                              </span>
                            </p>
                            <p className="text-[10px] text-muted-foreground">
                              {formatArabicRelativeTime(entry.at)}
                            </p>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </PopoverContent>
              </Popover>
            </div>
          )}

          {/* Notes Button */}
          <Button
            variant="ghost"
            size="sm"
            className="w-full mt-2 text-xs"
            onClick={() => {
              setNoteText(attendanceRecords[member.id]?.notes || '');
              setNotesDialog({ open: true, subjectId: member.id });
            }}
          >
            <FileText className="h-3 w-3 me-1" />
            {attendanceRecords[member.id]?.notes
              ? t('editNote')
              : t('addNote')}
          </Button>
        </CardContent>
      </Card>
    );
  };

  const renderSection = ({
    titleKey,
    titleFallback,
    icon: Icon,
    members,
    saving,
    onSave,
    onMarkAll,
    emptyKey,
    emptyFallback,
    testIdPrefix,
  }) => {
    const recordedCount = members.filter(
      (m) => attendanceRecords[m.id]?.status
    ).length;
    return (
      <Card className="card-nassaq">
        <CardHeader>
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-brand-turquoise/10 flex items-center justify-center">
                <Icon className="h-5 w-5 text-brand-turquoise" />
              </div>
              <div>
                <CardTitle className="font-cairo">
                  {t(titleKey) || titleFallback}
                </CardTitle>
                <CardDescription>
                  {isRTL
                    ? `${recordedCount} من ${members.length} مسجَّل`
                    : `${recordedCount} of ${members.length} recorded`}
                </CardDescription>
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={onMarkAll}
                className="rounded-xl"
                disabled={members.length === 0}
                data-testid={`${testIdPrefix}-mark-all-present-btn`}
              >
                <CheckCircle className="h-4 w-4 me-2" />
                {t('allPresent')}
              </Button>
              <Button
                onClick={onSave}
                disabled={saving || recordedCount === 0}
                className="bg-brand-turquoise hover:bg-brand-turquoise-light rounded-xl"
                data-testid={`${testIdPrefix}-save-attendance-btn`}
              >
                <Save className="h-4 w-4 me-2" />
                {saving ? t('saving') : t('saveAttendance')}
              </Button>
            </div>
          </div>
        </CardHeader>

        <CardContent>
          {loading ? (
            <div className="text-center py-8 text-muted-foreground">
              {t('loading')}
            </div>
          ) : members.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              {t(emptyKey) || emptyFallback}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {members.map(renderStaffCard)}
            </div>
          )}
        </CardContent>
      </Card>
    );
  };

  return (
    <Sidebar>
      <div className="min-h-screen bg-background" data-testid="teacher-attendance-page">
        {/* Header */}
        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="font-cairo text-2xl font-bold text-foreground flex items-center gap-2">
                <CalendarCheck className="h-7 w-7 text-brand-turquoise" />
                {t('staffAttendanceMgmt')}
              </h1>
              <p className="text-sm text-muted-foreground font-tajawal">
                {t('trackAndManageStaffAttendanceInTheSchool')}
              </p>
            </div>

            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" onClick={toggleLanguage} className="rounded-xl">
                <Globe className="h-5 w-5" />
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme} className="rounded-xl">
                {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </Button>
              <Button variant="ghost" size="icon" onClick={fetchAllStaffWithAttendance} className="rounded-xl">
                <RefreshCw className="h-5 w-5" />
              </Button>
            </div>
          </div>
        </header>

        <div className="p-6 space-y-6">
          {/* Description Card */}
          <Card className="card-nassaq bg-brand-turquoise/5 border-brand-turquoise/20">
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-brand-turquoise/10 flex items-center justify-center flex-shrink-0">
                  <Briefcase className="h-5 w-5 text-brand-turquoise" />
                </div>
                <div>
                  <h3 className="font-semibold text-brand-turquoise mb-1">
                    {t('staffAttendance2')}
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    {t('thisPageIsDedicatedToTrackingAndManagingStaffAtten')}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {overallStats.total > 0 && (
            <Card className="card-nassaq">
              <CardContent className="p-4">
                <div className="flex items-center justify-between gap-6 flex-wrap">
                  <div className="flex items-center gap-5">
                    <CircularProgressRing
                      value={overallStats.rate}
                      size={140}
                      stroke={12}
                      color="#1B93A4"
                    />
                    <div>
                      <p className="text-base font-semibold text-foreground font-cairo">
                        {t('teacherAttendanceRate')}
                      </p>
                      <p className="text-xs text-muted-foreground font-tajawal mt-1">
                        {isRTL
                          ? `${overallStats.recorded} من ${overallStats.total} مسجَّل`
                          : `${overallStats.recorded} of ${overallStats.total} recorded`}
                      </p>
                      <p className="text-xs text-muted-foreground font-tajawal mt-0.5">
                        {isRTL
                          ? `${overallStats.total - overallStats.recorded} متبقي`
                          : `${overallStats.total - overallStats.recorded} remaining`}
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-3 text-xs text-muted-foreground font-tajawal">
                    <Badge variant="secondary" className="px-3 py-1.5">
                      <Users className="h-3.5 w-3.5 me-1.5" />
                      {isRTL ? 'المعلمون' : 'Teachers'}: {teachersList.length}
                    </Badge>
                    <Badge variant="secondary" className="px-3 py-1.5">
                      <Shield className="h-3.5 w-3.5 me-1.5" />
                      {isRTL ? 'الإداريون' : 'Admins'}: {adminsList.length}
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Teachers Section */}
          {renderSection({
            titleKey: 'teacherList',
            titleFallback: 'قائمة المعلمين',
            icon: Users,
            members: teachersList,
            saving: savingTeachers,
            onSave: () => saveSection(teachersList, 'teacher'),
            onMarkAll: () => handleMarkAllPresent(teachersList, 'معلم', 'teacher'),
            emptyKey: 'noTeachersFound',
            emptyFallback: 'لا يوجد معلمون',
            testIdPrefix: 'teachers',
          })}

          {/* Admins Section */}
          {renderSection({
            titleKey: 'adminList',
            titleFallback: 'قائمة الإداريين',
            icon: Shield,
            members: adminsList,
            saving: savingAdmins,
            onSave: () => saveSection(adminsList, 'admin'),
            onMarkAll: () => handleMarkAllPresent(adminsList, 'إداري', 'admin'),
            emptyKey: 'noAdminsFound',
            emptyFallback: 'لا يوجد إداريون',
            testIdPrefix: 'admins',
          })}
        </div>

        {/* Notes Dialog */}
        <Dialog
          open={notesDialog.open}
          onOpenChange={(open) =>
            setNotesDialog({ open, subjectId: notesDialog.subjectId })
          }
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="font-cairo">
                {t('attendanceNotes')}
              </DialogTitle>
              <DialogDescription>
                {t('addANoteAboutTeacherAttendance')}
              </DialogDescription>
            </DialogHeader>
            <Textarea
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
              placeholder={t('writeYourNoteHere')}
              className="min-h-[100px] rounded-xl"
            />
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setNotesDialog({ open: false, subjectId: null })}
                className="rounded-xl"
              >
                {t('cancel')}
              </Button>
              <Button onClick={handleNotesSave} className="bg-brand-navy rounded-xl">
                {t('save')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
      <HakimAssistant />
    </Sidebar>
  );
};
