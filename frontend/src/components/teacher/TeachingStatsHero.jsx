import { useEffect, useState } from 'react';
import { Award, BookOpen, Users, CheckCircle2, Activity, Flame } from 'lucide-react';
import { Card, CardContent } from '../ui/card';
import { useAuth } from '../../contexts/AuthContext';
import { useTranslation } from '../../contexts/ThemeContext';

// 2026-05-18 — Read-only "إحصائيات التدريس" hero card extracted
// from the legacy TeacherSettingsPage so the unified
// "الملف الشخصي والإعدادات" hub (AccountSettingsPage) can surface
// the same teaching overview at the top of the Profile tab for
// teacher / independent_teacher roles. Fetches the same two
// endpoints the legacy page used (class-metrics + dashboard) so
// the displayed numbers stay byte-identical and we don't widen
// any backend authz boundary. Silently no-ops for non-teacher
// roles or when neither endpoint returns data.
export default function TeachingStatsHero() {
  const { user, api } = useAuth();
  const { t } = useTranslation();
  const [stats, setStats] = useState(null);

  const role = (user?.role || '').toLowerCase();
  const isTeacherRole = role === 'teacher' || role === 'independent_teacher';
  const teacherId = user?.id;

  useEffect(() => {
    if (!isTeacherRole || !teacherId) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const [metricsRes, dashRes] = await Promise.all([
          api.get(`/teacher/${teacherId}/class-metrics`).catch(() => null),
          api.get(`/teacher/dashboard/${teacherId}`).catch(() => null),
        ]);
        if (cancelled) return;
        const next = {};
        if (metricsRes?.data) {
          const classes = Object.values(metricsRes.data);
          if (classes.length > 0) {
            next.avgAttendance = Math.round(
              classes.reduce((s, c) => s + (c.attendance_rate || 0), 0) / classes.length,
            );
            next.avgParticipation = Math.round(
              classes.reduce((s, c) => s + (c.participation_rate || 0), 0) / classes.length,
            );
            next.totalSessions = classes.reduce((s, c) => s + (c.total_sessions || 0), 0);
          }
        }
        if (dashRes?.data) {
          next.classesCount = dashRes.data.stats?.my_classes || 0;
          next.studentsCount = dashRes.data.stats?.my_students || 0;
        }
        if (Object.keys(next).length > 0) setStats(next);
      } catch {
        // Soft-fail — the stats card is informational; the rest of
        // the profile tab must keep working regardless.
      }
    })();
    return () => { cancelled = true; };
  }, [api, teacherId, isTeacherRole]);

  if (!isTeacherRole || !stats) return null;

  const cells = [
    { label: t('myClasses'),           value: stats.classesCount || 0,                 icon: BookOpen,     color: 'text-blue-600',    bg: 'bg-blue-50 dark:bg-blue-900/30' },
    { label: t('myStudents'),          value: stats.studentsCount || 0,                icon: Users,        color: 'text-green-600',   bg: 'bg-green-50 dark:bg-green-900/30' },
    { label: t('attendanceRateLabel'), value: `${stats.avgAttendance || 0}%`,          icon: CheckCircle2, color: 'text-emerald-600', bg: 'bg-emerald-50 dark:bg-emerald-900/30' },
    { label: t('participation'),       value: `${stats.avgParticipation || 0}%`,       icon: Activity,     color: 'text-purple-600',  bg: 'bg-purple-50 dark:bg-purple-900/30' },
    { label: t('totalSessionsLabel'),  value: stats.totalSessions || 0,                icon: Flame,        color: 'text-amber-600',   bg: 'bg-amber-50 dark:bg-amber-900/30' },
  ];

  return (
    <Card className="card-nassaq" data-testid="account-section-teaching-stats">
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-4">
          <Award className="h-4 w-4 text-brand-turquoise" />
          <span className="font-cairo font-bold text-sm text-brand-navy dark:text-brand-turquoise">
            {t('teachingStats')}
          </span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
          {cells.map((stat) => (
            <div
              key={stat.label}
              className={`flex items-center gap-2.5 p-3 rounded-xl ${stat.bg} border border-transparent`}
            >
              <stat.icon className={`h-5 w-5 ${stat.color} shrink-0`} />
              <div className="min-w-0">
                <p className="text-base font-bold font-cairo text-foreground">{stat.value}</p>
                <p className="text-[10px] text-muted-foreground truncate font-cairo">{stat.label}</p>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
