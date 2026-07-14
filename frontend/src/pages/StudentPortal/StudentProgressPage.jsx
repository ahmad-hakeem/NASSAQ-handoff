import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme , useTranslation } from '../../contexts/ThemeContext';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Progress } from '../../components/ui/progress';
import { LoadingState } from '../../components/ui/LoadingState';
import {
  CheckCircle, BookOpen, Users, Heart, TrendingUp,
  BarChart3, AlertCircle
} from 'lucide-react';


const ProgressCard = ({ icon: Icon, title, value, maxValue, color, detail }) => (
  <Card className="rounded-2xl border-0 shadow-sm">
    <CardContent className="p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={`p-2 rounded-lg bg-${color}-100`}>
            <Icon className={`h-5 w-5 text-${color}-600`} />
          </div>
          <span className="font-medium text-sm">{title}</span>
        </div>
        <span className={`text-xl font-bold text-${color}-600`}>{value}%</span>
      </div>
      <Progress value={value} className="h-2.5 mb-2" />
      {detail && <p className="text-xs text-muted-foreground">{detail}</p>}
    </CardContent>
  </Card>
);

const StudentProgressPage = () => {
  const { t } = useTranslation();
  const { token, api } = useAuth();
  const { isRTL } = useTheme();
  const { nassaqError } = useNassaqAlert();
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchProgress = async () => {
      try {
        const res = await api.get('/student-portal/progress');
        setProgress(res.data);
        setError(null);
      } catch (err) {
        // FIX (C9): Surface fetch failures to the user via the standard
        // dialog and an inline error state instead of a silent console.error.
        console.error('Error fetching progress:', err);
        setError(t('errorFetchingProgress'));
        nassaqError(t('errorFetchingProgress'));
      } finally {
        setLoading(false);
      }
    };
    fetchProgress();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  if (!loading && error && !progress) {
    return (
      <PortalLayout portalType="student">
        <div className="p-6 text-center text-destructive flex flex-col items-center gap-2">
          <AlertCircle className="h-10 w-10 opacity-70" />
          <p>{error}</p>
        </div>
      </PortalLayout>
    );
  }

  if (loading) {
    return (
      <PortalLayout portalType="student">
        <LoadingState variant="fullpage" />
      </PortalLayout>
    );
  }

  if (!progress) {
    return (
      <PortalLayout portalType="student">
        <div className="p-4">
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardContent className="py-16 text-center">
              <AlertCircle className="h-16 w-16 mx-auto mb-4 text-gray-300" />
              <p className="text-muted-foreground">{t('couldNotLoadData')}</p>
            </CardContent>
          </Card>
        </div>
      </PortalLayout>
    );
  }

  const { attendance, academics, participation, behaviour } = progress;

  return (
    <PortalLayout portalType="student">
      <div className="p-4 space-y-4" data-testid="student-progress-page">
        <div className="flex items-center gap-2 mb-2">
          <BarChart3 className="h-6 w-6 text-emerald-600" />
          <h1 className="text-xl font-bold font-cairo">
            {t('myProgress')}
          </h1>
        </div>

        <ProgressCard
          icon={CheckCircle}
          title={t('attendanceRate')}
          value={attendance?.rate || 0}
          color="green"
          detail={isRTL
            ? `حاضر ${attendance?.present || 0} | غائب ${attendance?.absent || 0} | متأخر ${attendance?.late || 0}`
            : `Present ${attendance?.present || 0} | Absent ${attendance?.absent || 0} | Late ${attendance?.late || 0}`}
        />

        <ProgressCard
          icon={TrendingUp}
          title={t('academicAverage')}
          value={academics?.average || 0}
          color="blue"
          detail={isRTL
            ? `${academics?.total_grades || 0} تقييم`
            : `${academics?.total_grades || 0} assessments`}
        />

        <ProgressCard
          icon={Users}
          title={t('participationLevel')}
          value={participation?.rate || 0}
          color="amber"
          detail={isRTL
            ? `${participation?.count || 0} مشاركة`
            : `${participation?.count || 0} participations`}
        />

        <ProgressCard
          icon={Heart}
          title={t('behaviorQuality')}
          value={behaviour?.quality || 0}
          color="red"
          detail={isRTL
            ? `إيجابي ${behaviour?.positive || 0} | سلبي ${behaviour?.negative || 0}`
            : `Positive ${behaviour?.positive || 0} | Negative ${behaviour?.negative || 0}`}
        />

        {academics?.subject_averages?.length > 0 && (
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <BookOpen className="h-5 w-5 text-emerald-600" />
                {t('averageBySubject')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {academics.subject_averages.map((s, idx) => (
                <div key={idx}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium">{s.subject}</span>
                    <span className={`text-sm font-bold ${
                      s.average >= 90 ? 'text-green-600' :
                      s.average >= 75 ? 'text-blue-600' :
                      s.average >= 60 ? 'text-amber-600' : 'text-red-600'
                    }`}>{s.average}%</span>
                  </div>
                  <Progress value={s.average} className="h-2" />
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {academics?.monthly_trend?.length > 0 && (
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <TrendingUp className="h-5 w-5 text-emerald-600" />
                {t('monthlyPerformanceTrend')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-end gap-2 h-40">
                {academics.monthly_trend.map((m, idx) => {
                  const height = Math.max(10, (m.average / 100) * 100);
                  return (
                    <div key={idx} className="flex-1 flex flex-col items-center gap-1">
                      <span className="text-xs font-bold text-emerald-600">{m.average}%</span>
                      <div
                        className="w-full bg-gradient-to-t from-emerald-500 to-teal-400 rounded-t-lg transition-all"
                        style={{ height: `${height}%` }}
                      />
                      <span className="text-[10px] text-muted-foreground">{m.month.slice(5)}</span>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </PortalLayout>
  );
};

export default StudentProgressPage;
