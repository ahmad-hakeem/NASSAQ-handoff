import { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTranslation } from '../../contexts/ThemeContext';
import { useNassaqAlert } from '../ui/NassaqAlertDialog';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '../ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Progress } from '../ui/progress';
import { Avatar, AvatarFallback, AvatarImage } from '../ui/avatar';
import {
  Loader2, ClipboardCheck, FileText, Star, TrendingUp, GraduationCap,
} from 'lucide-react';

const EMPTY_DETAILS = {
  attendance: { rate: 0, total: 0, present: 0, absent: 0, late: 0, trend: [], recent: [] },
  grades: { average: 0, count: 0, records: [] },
  participation: { total_interactions: 0, participation_count: 0, recent: [] },
  behavior: { total_points: 0, records: [], session_records: [] },
  skills: [],
};

const gradeColor = (grade) => {
  const g = Number(grade) || 0;
  if (g >= 90) return 'text-green-600';
  if (g >= 75) return 'text-blue-600';
  if (g >= 60) return 'text-amber-600';
  return 'text-red-600';
};

const fmtDate = (value) => {
  if (!value) return '';
  try {
    return new Date(value).toLocaleDateString('ar-SA');
  } catch (_e) {
    return '';
  }
};

/**
 * Read-only, teacher-scoped student profile shown as a modal from the
 * gradebook (My Classes -> Student Record). It self-fetches the same
 * `/students/{id}/analytics` summary the teacher students page already uses,
 * so it inherits the exact teacher object-level authorization (no new access).
 * It intentionally omits principal-only actions (edit / suspend / AI plans)
 * and parent messaging — it is purely for inspecting a student's details.
 */
export default function TeacherStudentProfileDialog({ student, open, onClose, classLabel }) {
  const { api, isRTL } = useAuth();
  const { t } = useTranslation();
  const { nassaqError } = useNassaqAlert();
  const [details, setDetails] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (!open || !student?.id) return undefined;
    setDetails(null);
    setLoading(true);
    (async () => {
      try {
        const res = await api.get(`/students/${student.id}/analytics`);
        if (!cancelled) setDetails(res?.data || EMPTY_DETAILS);
      } catch (_err) {
        if (!cancelled) {
          setDetails(EMPTY_DETAILS);
          nassaqError(isRTL ? 'تعذّر تحميل تفاصيل الطالب' : 'Could not load student details');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [open, student?.id, api, isRTL, nassaqError]);

  const handleOpenChange = (next) => {
    if (!next) onClose?.();
  };

  const attendanceRate = details?.attendance?.rate ?? student?.attendance_rate ?? 0;
  const gradeAverage = details?.grades?.average ?? student?.average_grade ?? 0;
  const behaviorPoints = details?.behavior?.total_points ?? student?.behavior_points ?? 0;
  const participationCount = details?.participation?.participation_count ?? 0;
  const behaviorEntries = [
    ...(details?.behavior?.records || []),
    ...(details?.behavior?.session_records || []),
  ];

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className="w-[95vw] max-w-2xl max-h-[85vh] overflow-y-auto"
        dir={isRTL ? 'rtl' : 'ltr'}
      >
        <DialogHeader>
          <DialogTitle className="font-cairo flex items-center gap-3 text-start">
            <Avatar className="h-12 w-12 border border-border">
              <AvatarImage src={student?.avatar || undefined} alt={student?.full_name || ''} />
              <AvatarFallback className="bg-brand-turquoise/10 text-brand-turquoise font-bold">
                {student?.full_name?.charAt(0) || '؟'}
              </AvatarFallback>
            </Avatar>
            <div className="min-w-0">
              <p className="truncate">{student?.full_name || (isRTL ? 'الطالب' : 'Student')}</p>
              <div className="flex flex-wrap items-center gap-2 mt-1">
                {student?.student_id && (
                  <span className="text-xs font-normal text-muted-foreground">
                    {student.student_id}
                  </span>
                )}
                {classLabel && (
                  <Badge variant="outline" className="text-[10px] gap-1 font-normal">
                    <GraduationCap className="h-3 w-3" aria-hidden="true" />
                    {classLabel}
                  </Badge>
                )}
              </div>
            </div>
          </DialogTitle>
        </DialogHeader>

        {loading || !details ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" aria-hidden="true" />
          </div>
        ) : (
          <Tabs defaultValue="overview" className="mt-4">
            <TabsList className="grid grid-cols-4 w-full">
              <TabsTrigger value="overview">{t('overview') || 'نظرة عامة'}</TabsTrigger>
              <TabsTrigger value="attendance">{t('attendance2') || 'الحضور'}</TabsTrigger>
              <TabsTrigger value="grades">{t('grades') || 'الدرجات'}</TabsTrigger>
              <TabsTrigger value="behavior">{t('behavior') || 'السلوك'}</TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="space-y-4 mt-4">
              <div className="grid grid-cols-2 gap-3">
                <Card>
                  <CardContent className="p-4 text-center">
                    <ClipboardCheck className="h-7 w-7 mx-auto mb-1 text-green-600" aria-hidden="true" />
                    <div className="text-2xl font-bold">{attendanceRate}%</div>
                    <div className="text-xs text-muted-foreground">{isRTL ? 'نسبة الحضور' : 'Attendance'}</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-4 text-center">
                    <FileText className="h-7 w-7 mx-auto mb-1 text-blue-600" aria-hidden="true" />
                    <div className={`text-2xl font-bold ${gradeColor(gradeAverage)}`}>{gradeAverage}</div>
                    <div className="text-xs text-muted-foreground">{t('avgGrade') || 'متوسط الدرجات'}</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-4 text-center">
                    <Star className="h-7 w-7 mx-auto mb-1 text-purple-600" aria-hidden="true" />
                    <div className="text-2xl font-bold">{behaviorPoints}</div>
                    <div className="text-xs text-muted-foreground">{t('behaviorPts') || 'نقاط السلوك'}</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-4 text-center">
                    <TrendingUp className="h-7 w-7 mx-auto mb-1 text-amber-600" aria-hidden="true" />
                    <div className="text-2xl font-bold">{participationCount}</div>
                    <div className="text-xs text-muted-foreground">{t('participations') || 'المشاركات'}</div>
                  </CardContent>
                </Card>
              </div>

              {(details?.skills || []).length > 0 && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">{t('recordedSkills') || 'المهارات المسجلة'}</CardTitle>
                  </CardHeader>
                  <CardContent className="flex flex-wrap gap-2">
                    {details.skills.slice(0, 8).map((skill, idx) => (
                      <Badge key={idx} variant="outline" className="text-xs">
                        {skill.skill_name} {skill.level ? `(${skill.level})` : ''}
                      </Badge>
                    ))}
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            <TabsContent value="attendance" className="mt-4 space-y-4">
              <div className="grid grid-cols-3 gap-2">
                <Card>
                  <CardContent className="p-3 text-center">
                    <div className="text-lg font-bold text-green-600">{details?.attendance?.present ?? 0}</div>
                    <div className="text-xs text-muted-foreground">{t('present') || 'حاضر'}</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-3 text-center">
                    <div className="text-lg font-bold text-red-600">{details?.attendance?.absent ?? 0}</div>
                    <div className="text-xs text-muted-foreground">{t('absent') || 'غائب'}</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-3 text-center">
                    <div className="text-lg font-bold text-amber-600">{details?.attendance?.late ?? 0}</div>
                    <div className="text-xs text-muted-foreground">{t('late') || 'متأخر'}</div>
                  </CardContent>
                </Card>
              </div>

              {(details?.attendance?.trend || []).length > 0 && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">{t('monthlyAttendanceTrend') || 'اتجاه الحضور الشهري'}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {details.attendance.trend.map((item, idx) => (
                        <div key={idx} className="flex items-center gap-3">
                          <span className="text-xs w-16 text-muted-foreground">{item.month}</span>
                          <div className="flex-1">
                            <Progress value={item.rate} className="h-2" />
                          </div>
                          <span className="text-xs font-medium w-10 text-end">{item.rate}%</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">{t('recentRecords') || 'أحدث السجلات'}</CardTitle>
                </CardHeader>
                <CardContent>
                  {(details?.attendance?.recent || []).length === 0 ? (
                    <p className="text-center text-muted-foreground py-4 text-sm">
                      {t('noAttendanceRecords') || 'لا توجد سجلات حضور'}
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {details.attendance.recent.map((record, idx) => (
                        <div key={idx} className="flex items-center justify-between p-2 rounded bg-muted/30">
                          <span className="text-sm">{fmtDate(record.date)}</span>
                          <Badge variant={record.status === 'present' ? 'default' : 'destructive'}>
                            {record.status === 'present' ? (t('present') || 'حاضر') :
                             record.status === 'absent' ? (t('absent') || 'غائب') :
                             (t('late') || 'متأخر')}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="grades" className="mt-4 space-y-4">
              {gradeAverage > 0 && (
                <Card>
                  <CardContent className="p-4 flex items-center justify-between">
                    <span className="text-sm font-medium">{t('overallAverage') || 'المعدل العام'}</span>
                    <div className={`text-2xl font-bold ${gradeColor(gradeAverage)}`}>{gradeAverage}</div>
                  </CardContent>
                </Card>
              )}
              <Card>
                <CardContent className="p-4">
                  {(details?.grades?.records || []).length === 0 ? (
                    <p className="text-center text-muted-foreground py-4 text-sm">
                      {t('noGrades') || 'لا توجد درجات'}
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {details.grades.records.map((grade, idx) => (
                        <div key={idx} className="flex items-center justify-between p-2 rounded bg-muted/30">
                          <div>
                            <p className="font-medium text-sm">{grade.assessment_name || grade.subject_name}</p>
                            <p className="text-xs text-muted-foreground">{grade.type || (t('assessment') || 'تقييم')}</p>
                          </div>
                          <Badge className={gradeColor(grade.score || 0)}>
                            {grade.score || 0} / {grade.max_score || 100}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="behavior" className="mt-4 space-y-4">
              <Card>
                <CardContent className="p-4 flex items-center justify-between">
                  <span className="text-sm font-medium">{t('totalPoints2') || 'إجمالي النقاط'}</span>
                  <div className={`text-2xl font-bold ${behaviorPoints >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {behaviorPoints >= 0 ? '+' : ''}{behaviorPoints}
                  </div>
                </CardContent>
              </Card>

              {(details?.participation?.recent || []).length > 0 && (
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">{t('sessionInteractions') || 'تفاعلات الحصص'}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {details.participation.recent.slice(0, 5).map((inter, idx) => (
                        <div key={idx} className="flex items-center justify-between p-2 rounded bg-muted/30">
                          <div>
                            <p className="text-sm font-medium">{inter.note || inter.type}</p>
                            <p className="text-xs text-muted-foreground">{fmtDate(inter.created_at)}</p>
                          </div>
                          {inter.points != null && (
                            <Badge variant={inter.points > 0 ? 'default' : 'destructive'}>
                              {inter.points > 0 ? '+' : ''}{inter.points}
                            </Badge>
                          )}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">{t('behaviorRecords2') || 'سجلات السلوك'}</CardTitle>
                </CardHeader>
                <CardContent>
                  {behaviorEntries.length === 0 ? (
                    <p className="text-center text-muted-foreground py-4 text-sm">
                      {t('noBehaviorRecords3') || 'لا توجد سجلات سلوك'}
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {behaviorEntries.slice(0, 10).map((record, idx) => (
                        <div
                          key={idx}
                          className={`p-2 rounded border ${
                            (record.points || 0) > 0
                              ? 'bg-green-50 dark:bg-green-950/30 border-green-200 dark:border-green-800'
                              : 'bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-800'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-medium text-sm">{record.note || (t('note') || 'ملاحظة')}</span>
                            <Badge variant={(record.points || 0) > 0 ? 'default' : 'destructive'}>
                              {(record.points || 0) > 0 ? '+' : ''}{record.points || 0}
                            </Badge>
                          </div>
                          <p className="text-xs text-muted-foreground mt-1">
                            {fmtDate(record.date || record.created_at)}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        )}
      </DialogContent>
    </Dialog>
  );
}
