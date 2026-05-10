import React, { useEffect, useState } from 'react';
import { useAuth } from '../../../contexts/AuthContext';
import { useTheme, useTranslation } from '../../../contexts/ThemeContext';
import { Card, CardContent } from '../../ui/card';
import { Badge } from '../../ui/badge';
import { Progress } from '../../ui/progress';
import { Skeleton } from '../../ui/skeleton';
import { ScrollArea } from '../../ui/scroll-area';
import CumulativeAnalytics from '../CumulativeAnalytics';
import {
  BookOpen, CheckCircle, XCircle, AlertCircle, Clock, Award, Calendar,
} from 'lucide-react';

const DetailsPanel = ({ childId }) => {
  const { t } = useTranslation();
  const { token, api } = useAuth();
  const { isRTL } = useTheme();
  const [loading, setLoading] = useState(true);
  const [grades, setGrades] = useState(null);
  const [attendance, setAttendance] = useState(null);
  const [section, setSection] = useState('analytics');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const [gradesRes, attendanceRes] = await Promise.all([
          api.get(`/parent-portal/child/${childId}/grades`).catch(() => ({ data: null })),
          api.get(`/parent-portal/child/${childId}/attendance`).catch(() => ({ data: null })),
        ]);
        if (cancelled) return;
        setGrades(gradesRes.data);
        setAttendance(attendanceRes.data);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [childId, token, api]);

  const getGradeColor = (p) => {
    if (p >= 90) return 'text-green-600 dark:text-green-400';
    if (p >= 75) return 'text-blue-600 dark:text-blue-400';
    if (p >= 60) return 'text-amber-600 dark:text-amber-400';
    return 'text-red-600 dark:text-red-400';
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'present': return <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400" />;
      case 'absent': return <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />;
      case 'late': return <Clock className="h-4 w-4 text-amber-600 dark:text-amber-400" />;
      default: return <AlertCircle className="h-4 w-4 text-muted-foreground" />;
    }
  };

  if (loading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-20 w-full rounded-2xl" />
        <Skeleton className="h-48 w-full rounded-2xl" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Quick stats */}
      <div className="grid grid-cols-2 gap-3">
        <Card className="rounded-xl border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="p-2 rounded-lg bg-green-100 dark:bg-green-900/40">
                <CheckCircle className="h-5 w-5 text-green-600 dark:text-green-400" />
              </div>
              <span className="text-2xl font-bold text-green-600 dark:text-green-400">
                {attendance?.statistics?.attendance_rate || 0}%
              </span>
            </div>
            <p className="text-xs text-muted-foreground">{isRTL ? 'نسبة الحضور' : 'Attendance'}</p>
            <Progress value={attendance?.statistics?.attendance_rate || 0} className="h-1.5 mt-2" />
          </CardContent>
        </Card>
        <Card className="rounded-xl border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="p-2 rounded-lg bg-blue-100 dark:bg-blue-900/40">
                <Award className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
              <span className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                {grades?.overall_average || 0}%
              </span>
            </div>
            <p className="text-xs text-muted-foreground">{t('average2')}</p>
            <Progress value={grades?.overall_average || 0} className="h-1.5 mt-2" />
          </CardContent>
        </Card>
      </div>

      {/* Inner sub-tabs */}
      <div className="flex bg-muted/40 rounded-xl p-1 gap-1 overflow-x-auto">
        {[
          { id: 'analytics', label: t('cumulativeAnalytics') },
          { id: 'grades', label: t('grades') },
          { id: 'attendance', label: t('attendance2') },
        ].map((s) => (
          <button
            key={s.id}
            onClick={() => setSection(s.id)}
            className={`flex-1 min-w-fit text-xs px-3 py-1.5 rounded-lg whitespace-nowrap transition ${
              section === s.id
                ? 'bg-card shadow-sm font-medium text-foreground'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {section === 'analytics' && (
        <CumulativeAnalytics childId={childId} viewerRole="parent" />
      )}

      {section === 'grades' && (
        <Card className="rounded-2xl border-0 shadow-sm">
          <CardContent className="p-4">
            <ScrollArea className="h-[400px]">
              {grades?.subjects?.length > 0 ? (
                <div className="space-y-4">
                  {grades.subjects.map((subject, idx) => (
                    <div key={idx} className="space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <BookOpen className={`h-4 w-4 ${getGradeColor(subject.average)}`} />
                          <span className="font-medium text-sm">{subject.subject}</span>
                        </div>
                        <span className={`font-bold ${getGradeColor(subject.average)}`}>
                          {subject.average}%
                        </span>
                      </div>
                      <Progress value={subject.average} className="h-2" />
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <Award className="h-12 w-12 mb-3 opacity-30" />
                  <p>{t('noGrades')}</p>
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>
      )}

      {section === 'attendance' && (
        <Card className="rounded-2xl border-0 shadow-sm">
          <CardContent className="p-4 space-y-3">
            <div className="grid grid-cols-4 gap-2 text-center">
              <div className="p-2 bg-green-50 dark:bg-green-950/30 rounded-lg">
                <p className="text-lg font-bold text-green-600 dark:text-green-400">{attendance?.statistics?.present || 0}</p>
                <p className="text-[10px] text-muted-foreground">{t('present')}</p>
              </div>
              <div className="p-2 bg-red-50 dark:bg-red-950/30 rounded-lg">
                <p className="text-lg font-bold text-red-600 dark:text-red-400">{attendance?.statistics?.absent || 0}</p>
                <p className="text-[10px] text-muted-foreground">{t('absent')}</p>
              </div>
              <div className="p-2 bg-amber-50 dark:bg-amber-950/30 rounded-lg">
                <p className="text-lg font-bold text-amber-600 dark:text-amber-400">{attendance?.statistics?.late || 0}</p>
                <p className="text-[10px] text-muted-foreground">{t('late')}</p>
              </div>
              <div className="p-2 bg-blue-50 dark:bg-blue-950/30 rounded-lg">
                <p className="text-lg font-bold text-blue-600 dark:text-blue-400">{attendance?.statistics?.excused || 0}</p>
                <p className="text-[10px] text-muted-foreground">{t('excused2')}</p>
              </div>
            </div>
            <ScrollArea className="h-[300px]">
              {attendance?.records?.length > 0 ? (
                <div className="space-y-2">
                  {attendance.records.slice(0, 20).map((record, idx) => (
                    <div key={idx} className="flex items-center justify-between p-3 bg-muted/40 rounded-lg">
                      <div className="flex items-center gap-2">
                        {getStatusIcon(record.status)}
                        <span className="text-sm">{record.date}</span>
                      </div>
                      <Badge variant="outline" className="text-xs">
                        {record.status === 'present' && t('present')}
                        {record.status === 'absent' && t('absent')}
                        {record.status === 'late' && t('late')}
                        {record.status === 'excused' && t('excused2')}
                      </Badge>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <Calendar className="h-12 w-12 mb-3 opacity-30" />
                  <p>{t('noRecords')}</p>
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default DetailsPanel;
