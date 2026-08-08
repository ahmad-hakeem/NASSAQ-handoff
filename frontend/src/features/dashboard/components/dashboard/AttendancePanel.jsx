import { useTranslation } from '@/shared/contexts/ThemeContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Users, GraduationCap, UserCheck, UserX, Clock, Timer } from 'lucide-react';

export const AttendanceRadial = ({ data, isRTL }) => {
  const { t } = useTranslation();
  const studentTotalRaw = data?.students?.total || 0;
  const studentPresent = data?.students?.present || 0;
  const studentAbsent = data?.students?.absent || 0;
  const studentExcused = data?.students?.excused || 0;
  const studentLate = data?.students?.late || 0;
  const studentPercent = Math.round((studentPresent / Math.max(studentTotalRaw, 1)) * 100);
  const teacherTotalRaw = data?.teachers?.total || 0;
  const teacherPresent = data?.teachers?.present || 0;
  const teacherAbsent = data?.teachers?.absent || 0;
  const teacherExcused = data?.teachers?.excused || 0;
  const teacherLate = data?.teachers?.late || 0;
  const teacherPercent = Math.round((teacherPresent / Math.max(teacherTotalRaw, 1)) * 100);

  const overallTotal = studentTotalRaw + teacherTotalRaw;
  const overallPresent = studentPresent + teacherPresent;
  const overallPercent = Math.round((overallPresent / Math.max(overallTotal, 1)) * 100);

  const getColor = (pct) => {
    if (pct >= 90) return { ring: '#10b981', bg: 'rgba(16,185,129,0.15)', label: t('excellent'), labelColor: 'text-emerald-600 dark:text-emerald-400' };
    if (pct >= 75) return { ring: '#f59e0b', bg: 'rgba(245,158,11,0.15)', label: t('good'), labelColor: 'text-amber-600 dark:text-amber-400' };
    return { ring: '#ef4444', bg: 'rgba(239,68,68,0.15)', label: t('needsAttention'), labelColor: 'text-red-600 dark:text-red-400' };
  };

  const RadialRing = ({ percent, size = 130, strokeWidth = 12, color }) => {
    const radius = (size - strokeWidth) / 2;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (percent / 100) * circumference;
    return (
      <svg width={size} height={size} className="transform -rotate-90 drop-shadow-sm">
        <circle cx={size/2} cy={size/2} r={radius} stroke={color.bg} strokeWidth={strokeWidth} fill="none" />
        <circle cx={size/2} cy={size/2} r={radius} stroke={color.ring} strokeWidth={strokeWidth} fill="none"
          strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 1s ease-in-out', filter: `drop-shadow(0 0 6px ${color.ring}40)` }}
        />
      </svg>
    );
  };

  const StatBar = ({ label, value, total, color, icon: Icon }) => {

    const pct = total > 0 ? Math.round((value / total) * 100) : 0;
    return (
      <div className="flex items-center gap-2.5">
        <div className={`w-7 h-7 rounded-lg ${color} flex items-center justify-center shrink-0`}>
          <Icon className="h-3.5 w-3.5 text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between mb-0.5">
            <span className="text-[11px] font-tajawal text-muted-foreground">{label}</span>
            <span className="text-[11px] font-cairo font-bold">{value}<span className="text-muted-foreground font-normal">/{total}</span></span>
          </div>
          <div className="h-1.5 rounded-full bg-muted overflow-hidden">
            <div className={`h-full rounded-full ${color} transition-all duration-700`} style={{ width: `${pct}%` }} />
          </div>
        </div>
      </div>
    );
  };

  const categories = [
    { 
      label: t('students'), 
      percent: studentPercent, present: studentPresent, absent: studentAbsent, 
      excused: studentExcused, late: studentLate, total: studentTotalRaw, icon: Users 
    },
    { 
      label: t('teachers'), 
      percent: teacherPercent, present: teacherPresent, absent: teacherAbsent, 
      excused: teacherExcused, late: teacherLate, total: teacherTotalRaw, icon: GraduationCap 
    },
  ];

  const overallColor = getColor(overallPercent);

  return (
    <Card className="card-nassaq">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 font-cairo text-lg">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-brand-turquoise to-brand-turquoise/70 flex items-center justify-center">
              <UserCheck className="h-4.5 w-4.5 text-white" />
            </div>
            {t('attendanceDashboard')}
          </CardTitle>
          <div className={`px-2.5 py-1 rounded-lg text-[11px] font-tajawal font-medium ${overallColor.labelColor} bg-current/5`}
            style={{ backgroundColor: `${overallColor.ring}15` }}>
            {overallColor.label}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid grid-cols-2 gap-4 max-md:grid-cols-1">
          {categories.map((cat) => {
            const color = getColor(cat.percent);
            return (
              <div key={cat.label} className="relative p-4 rounded-2xl bg-muted/30 border border-border/50">
                <div className="flex flex-col items-center text-center mb-4">
                  <div className="relative mb-2">
                    <RadialRing percent={cat.percent} color={color} />
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <span className="text-3xl font-bold font-cairo" style={{ color: color.ring }}>{cat.percent}%</span>
                      <span className={`text-[10px] font-tajawal font-medium ${color.labelColor}`}>{color.label}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <cat.icon className="h-4 w-4 text-muted-foreground" />
                    <span className="font-tajawal text-sm font-semibold">{cat.label}</span>
                    <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4 font-cairo">{cat.total}</Badge>
                  </div>
                </div>

                <div className="space-y-2.5">
                  <StatBar label={t('present')} value={cat.present} total={cat.total} color="bg-emerald-500" icon={UserCheck} />
                  <StatBar label={t('absent')} value={cat.absent} total={cat.total} color="bg-red-500" icon={UserX} />
                  <StatBar label={t('excused')} value={cat.excused} total={cat.total} color="bg-amber-500" icon={Clock} />
                  {cat.late > 0 && (
                    <StatBar label={t('late')} value={cat.late} total={cat.total} color="bg-orange-500" icon={Timer} />
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <div className="flex items-center gap-3 p-3 rounded-xl bg-gradient-to-r from-brand-navy/5 to-brand-turquoise/5 dark:from-brand-navy/20 dark:to-brand-turquoise/20 border border-brand-turquoise/10">
          <div className="relative shrink-0">
            <RadialRing percent={overallPercent} size={56} strokeWidth={6} color={overallColor} />
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-sm font-bold font-cairo" style={{ color: overallColor.ring }}>{overallPercent}%</span>
            </div>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-cairo font-semibold">{t('overallAttendance')}</p>
            <p className="text-[11px] text-muted-foreground font-tajawal">
              {isRTL ? `${overallPresent} من ${overallTotal} حاضرون اليوم` : `${overallPresent} of ${overallTotal} present today`}
            </p>
          </div>
          <div className="text-end shrink-0">
            <p className="text-lg font-bold font-cairo" style={{ color: overallColor.ring }}>{overallPresent}</p>
            <p className="text-[10px] text-muted-foreground font-tajawal">{isRTL ? 'حاضر' : 'present'}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default AttendanceRadial;
