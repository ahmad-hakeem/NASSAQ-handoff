import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Progress } from '../ui/progress';
import { Skeleton } from '../ui/skeleton';
import { GaugeChart, PerformanceLine, SubjectRadar } from './AnalyticsCharts';
import {
  TrendingUp, Award, Target, AlertTriangle,
  CheckCircle, BookOpen, ClipboardCheck, Users,
  ThumbsUp, ThumbsDown, Home, BarChart3, Activity
} from 'lucide-react';

const CumulativeAnalytics = ({ childId, viewerRole = 'parent' }) => {
  const { t } = useTranslation();
  const { api } = useAuth();
  const { isRTL } = useTheme();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!childId) return;
    const fetchAnalytics = async () => {
      setLoading(true);
      setError(false);
      try {
        const endpoint = viewerRole === 'student'
          ? '/student-portal/my-analytics'
          : `/parent-portal/child/${childId}/analytics`;
        const res = await api.get(endpoint);
        setData(res.data);
      } catch (err) {
        console.error('Error fetching analytics:', err);
        setError(true);
      } finally {
        setLoading(false);
      }
    };
    fetchAnalytics();
  }, [childId, api, viewerRole]);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-32 rounded-2xl" />
        <Skeleton className="h-48 rounded-2xl" />
        <Skeleton className="h-64 rounded-2xl" />
        <Skeleton className="h-48 rounded-2xl" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <Card className="rounded-2xl border-0 shadow-sm">
        <CardContent className="py-12 text-center">
          <BarChart3 className="h-12 w-12 mx-auto mb-3 text-gray-300" />
          <p className="text-muted-foreground">{t('noAnalyticsData')}</p>
        </CardContent>
      </Card>
    );
  }

  const { summary, gauge_data, line_chart_data, radar_data, strengths, weaknesses, follow_up } = data;
  const isStudent = viewerRole === 'student';

  const getLevelColor = (level) => {
    const colorMap = {
      'ممتاز': 'text-green-600 bg-green-50',
      'جيد جداً': 'text-blue-600 bg-blue-50',
      'جيد': 'text-indigo-600 bg-indigo-50',
      'مقبول': 'text-amber-600 bg-amber-50',
      'ضعيف': 'text-red-600 bg-red-50',
    };
    return colorMap[level] || 'text-gray-600 bg-gray-50';
  };

  const getFollowUpConfig = (status) => {
    const configs = {
      'مستقر': { color: 'bg-green-100 text-green-700 border-green-200', icon: CheckCircle, iconColor: 'text-green-600' },
      'يحتاج متابعة': { color: 'bg-amber-100 text-amber-700 border-amber-200', icon: AlertTriangle, iconColor: 'text-amber-600' },
      'بحاجة دعم': { color: 'bg-red-100 text-red-700 border-red-200', icon: AlertTriangle, iconColor: 'text-red-600' },
    };
    return configs[status] || configs['مستقر'];
  };

  const followUpConfig = follow_up ? getFollowUpConfig(follow_up.status) : null;
  const FollowUpIcon = followUpConfig?.icon;

  return (
    <div className="space-y-4">
      <Card className="rounded-2xl border-0 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <Activity className="h-5 w-5 text-indigo-600" />
            {t('performanceSummary')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-3">
            <div className="text-center p-3 bg-indigo-50 rounded-xl">
              <Award className="h-6 w-6 mx-auto mb-1 text-indigo-600" />
              <p className={`text-lg font-bold ${getLevelColor(summary?.level).split(' ')[0]}`}>
                {summary?.level}
              </p>
              <p className="text-[10px] text-muted-foreground">{t('overallLevel')}</p>
            </div>
            <div className="text-center p-3 bg-blue-50 rounded-xl">
              <TrendingUp className="h-6 w-6 mx-auto mb-1 text-blue-600" />
              <p className="text-lg font-bold text-blue-600">{summary?.overall_average}%</p>
              <p className="text-[10px] text-muted-foreground">{t('overallAverage')}</p>
            </div>
            <div className="text-center p-3 bg-purple-50 rounded-xl">
              <Users className="h-6 w-6 mx-auto mb-1 text-purple-600" />
              <p className="text-lg font-bold text-purple-600">{summary?.class_average}%</p>
              <p className="text-[10px] text-muted-foreground">{t('classAverage')}</p>
            </div>
          </div>

          {summary?.overall_average > 0 && summary?.class_average > 0 && (
            <div className="mt-3 p-3 bg-gray-50 rounded-xl">
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-muted-foreground">{t('comparedToClass')}</span>
                <span className={`font-bold ${
                  summary.overall_average >= summary.class_average ? 'text-green-600' : 'text-amber-600'
                }`}>
                  {summary.overall_average >= summary.class_average ? '+' : ''}
                  {(summary.overall_average - summary.class_average).toFixed(1)}%
                </span>
              </div>
              <Progress
                value={Math.min(100, (summary.overall_average / Math.max(summary.class_average, 1)) * 50)}
                className="h-2"
              />
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="rounded-2xl border-0 shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-base flex items-center gap-2">
            <Target className="h-5 w-5 text-indigo-600" />
            {t('performanceTrend')}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {gauge_data && (
            <div className="flex justify-center">
              <GaugeChart value={gauge_data.value} level={gauge_data.level} />
            </div>
          )}

          {line_chart_data?.length > 0 && (
            <div>
              <p className="text-xs text-muted-foreground mb-2 text-center">{t('monthlyTrajectory')}</p>
              <PerformanceLine data={line_chart_data} />
            </div>
          )}
        </CardContent>
      </Card>

      {radar_data?.length > 0 && (
        <Card className="rounded-2xl border-0 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <BookOpen className="h-5 w-5 text-indigo-600" />
              {t('subjectDistribution')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <SubjectRadar data={radar_data} />
            <div className="grid grid-cols-2 gap-2 mt-2">
              {radar_data.map((item) => (
                <div key={item.subject} className="flex items-center justify-between text-xs p-2 bg-gray-50 rounded-lg">
                  <span>{item.subject}</span>
                  <span className={`font-bold ${
                    item.score >= 80 ? 'text-green-600' : item.score >= 60 ? 'text-amber-600' : 'text-red-600'
                  }`}>{item.score}%</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {(strengths?.length > 0 || weaknesses?.length > 0) && (
        <div className="grid grid-cols-1 gap-3">
          {strengths?.length > 0 && (
            <Card className="rounded-2xl border-0 shadow-sm border-s-4 border-s-green-500">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2 text-green-700">
                  <ThumbsUp className="h-4 w-4" />
                  {t('strengths')}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="space-y-2">
                  {strengths.map((s, i) => (
                    <div key={i} className="flex items-start gap-2 p-2 bg-green-50 rounded-lg">
                      <CheckCircle className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
                      <div>
                        <p className="text-sm font-medium text-green-800">{s.area}</p>
                        <p className="text-xs text-green-600">{s.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {weaknesses?.length > 0 && (
            <Card className="rounded-2xl border-0 shadow-sm border-s-4 border-s-amber-500">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2 text-amber-700">
                  <ThumbsDown className="h-4 w-4" />
                  {t('areasForImprovement')}
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="space-y-2">
                  {weaknesses.map((w, i) => (
                    <div key={i} className="flex items-start gap-2 p-2 bg-amber-50 rounded-lg">
                      <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
                      <div>
                        <p className="text-sm font-medium text-amber-800">{w.area}</p>
                        <p className="text-xs text-amber-600">{w.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {!isStudent && follow_up && (
        <Card className="rounded-2xl border-0 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <Home className="h-5 w-5 text-indigo-600" />
              {t('homeFollowUp')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`flex items-center gap-3 p-4 rounded-xl border ${followUpConfig?.color}`}>
              {FollowUpIcon && <FollowUpIcon className={`h-8 w-8 ${followUpConfig?.iconColor}`} />}
              <div>
                <p className="text-lg font-bold">{follow_up.status}</p>
                <p className="text-xs opacity-80">
                  {t('compositeScore')}: {follow_up.score}%
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 mt-3">
              <div className="p-2 bg-gray-50 rounded-lg text-center">
                <p className="text-xs text-muted-foreground">{t('attendanceRate')}</p>
                <p className="text-sm font-bold">{follow_up.breakdown?.attendance_rate}%</p>
              </div>
              <div className="p-2 bg-gray-50 rounded-lg text-center">
                <p className="text-xs text-muted-foreground">{t('homeworkCompletion')}</p>
                <p className="text-sm font-bold">{follow_up.breakdown?.homework_rate}%</p>
              </div>
              <div className="p-2 bg-gray-50 rounded-lg text-center">
                <p className="text-xs text-muted-foreground">{t('participation')}</p>
                <p className="text-sm font-bold">{follow_up.breakdown?.participation_score}%</p>
              </div>
              <div className="p-2 bg-gray-50 rounded-lg text-center">
                <p className="text-xs text-muted-foreground">{t('academicAverage')}</p>
                <p className="text-sm font-bold">{follow_up.breakdown?.academic_average}%</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default CumulativeAnalytics;
