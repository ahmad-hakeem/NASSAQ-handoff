import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Progress } from '../../components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { toast } from 'sonner';
import {
  Award, Star, Trophy, Target, Flame, TrendingUp, Users,
  BookOpen, ClipboardCheck, RefreshCw, Loader2, CheckCircle2,
  Zap, Crown, Medal, Heart, Activity, BarChart3, Calendar,
  Sparkles, Shield, GraduationCap, ThumbsUp, Clock
} from 'lucide-react';

import { useTranslation } from '../../contexts/ThemeContext';
const BADGE_META = {
  sessions_10: { icon: BookOpen, title_ar: 'بداية التدريس', title_en: 'Teaching Start', desc_ar: 'أكمل 10 حصص دراسية', desc_en: 'Complete 10 sessions', gradient: 'from-blue-500 to-blue-600', bg: 'bg-blue-100 dark:bg-blue-900/40', text: 'text-blue-700 dark:text-blue-300' },
  sessions_50: { icon: Flame, title_ar: 'معلم نشط', title_en: 'Active Teacher', desc_ar: 'أكمل 50 حصة', desc_en: 'Complete 50 sessions', gradient: 'from-orange-500 to-red-500', bg: 'bg-orange-100 dark:bg-orange-900/40', text: 'text-orange-700 dark:text-orange-300' },
  sessions_100: { icon: Crown, title_ar: 'معلم متميز', title_en: 'Distinguished Teacher', desc_ar: 'أكمل 100 حصة', desc_en: 'Complete 100 sessions', gradient: 'from-amber-500 to-yellow-500', bg: 'bg-amber-100 dark:bg-amber-900/40', text: 'text-amber-700 dark:text-amber-300' },
  attendance_90: { icon: ClipboardCheck, title_ar: 'حضور ممتاز', title_en: 'Excellent Attendance', desc_ar: 'حافظ على حضور 90%+', desc_en: 'Maintain 90%+ attendance', gradient: 'from-green-500 to-emerald-600', bg: 'bg-green-100 dark:bg-green-900/40', text: 'text-green-700 dark:text-green-300' },
  students_50: { icon: Users, title_ar: 'مؤثر في الطلاب', title_en: 'Student Impact', desc_ar: 'قم بتدريس 50 طالب+', desc_en: 'Teach 50+ students', gradient: 'from-purple-500 to-purple-600', bg: 'bg-purple-100 dark:bg-purple-900/40', text: 'text-purple-700 dark:text-purple-300' },
  participation_80: { icon: Star, title_ar: 'محفز المشاركة', title_en: 'Engagement Champion', desc_ar: 'حقق مشاركة 80%+', desc_en: 'Achieve 80%+ participation', gradient: 'from-pink-500 to-rose-500', bg: 'bg-pink-100 dark:bg-pink-900/40', text: 'text-pink-700 dark:text-pink-300' },
  performance_85: { icon: Target, title_ar: 'أداء عالي', title_en: 'High Performance', desc_ar: 'حقق أداء 85%+ للطلاب', desc_en: 'Achieve 85%+ avg performance', gradient: 'from-cyan-500 to-teal-500', bg: 'bg-cyan-100 dark:bg-cyan-900/40', text: 'text-cyan-700 dark:text-cyan-300' },
  classes_5: { icon: BookOpen, title_ar: 'متعدد الفصول', title_en: 'Multi-Class', desc_ar: 'درّس 5 فصول+', desc_en: 'Teach 5+ classes', gradient: 'from-indigo-500 to-indigo-600', bg: 'bg-indigo-100 dark:bg-indigo-900/40', text: 'text-indigo-700 dark:text-indigo-300' },
  assessments_20: { icon: GraduationCap, title_ar: 'مُقيّم فعّال', title_en: 'Active Evaluator', desc_ar: 'سجّل 20 تقييم+', desc_en: 'Record 20+ assessments', gradient: 'from-violet-500 to-violet-600', bg: 'bg-violet-100 dark:bg-violet-900/40', text: 'text-violet-700 dark:text-violet-300' },
  behavior_positive_50: { icon: ThumbsUp, title_ar: 'داعم السلوك', title_en: 'Behavior Champion', desc_ar: 'سجّل 50 سلوك إيجابي+', desc_en: 'Record 50+ positive behaviors', gradient: 'from-emerald-500 to-teal-500', bg: 'bg-emerald-100 dark:bg-emerald-900/40', text: 'text-emerald-700 dark:text-emerald-300' },
  regularity_95: { icon: Shield, title_ar: 'منتظم بامتياز', title_en: 'Perfect Regularity', desc_ar: 'نسبة انتظام 95%+', desc_en: '95%+ session regularity', gradient: 'from-slate-500 to-gray-600', bg: 'bg-slate-100 dark:bg-slate-900/40', text: 'text-slate-700 dark:text-slate-300' },
};

export default function TeacherAchievementsPage() {
  const { t } = useTranslation();
  const { user, api, isRTL } = useAuth();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [activeTab, setActiveTab] = useState('badges');

  const teacherId = user?.teacher_id || user?.id;

  const fetchData = useCallback(async () => {
    if (!teacherId) return;
    setLoading(true);
    try {
      const res = await api.get(`/teacher/achievements/${teacherId}`);
      setData(res.data);
    } catch (error) {
      console.error('Error fetching achievements:', error);
    } finally {
      setLoading(false);
    }
  }, [api, teacherId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const m = data?.metrics || {};
  const earnedCount = data?.total_earned || 0;
  const totalCount = data?.total_badges || 0;
  const levelPercent = totalCount > 0 ? Math.round((earnedCount / totalCount) * 100) : 0;

  const levelTitle = earnedCount >= 9 ? (t('legendaryTeacher'))
    : earnedCount >= 6 ? (isRTL ? 'معلم خبير' : 'Expert Teacher')
    : earnedCount >= 3 ? (t('advancedTeacher'))
    : earnedCount >= 1 ? (t('beginnerTeacher'))
    : (t('startYourJourney'));

  const renderBadgeCard = (badge, isEarned) => {
    const meta = BADGE_META[badge.id] || {};
    const Icon = meta.icon || Award;
    return (
      <div key={badge.id} className={`group relative p-4 rounded-2xl border transition-all duration-300 ${isEarned ? 'bg-card hover:shadow-lg hover:shadow-brand-turquoise/5 border-brand-turquoise/20' : 'bg-muted/20 border-border/50 hover:bg-muted/40'}`}>
        {isEarned && <div className={`absolute top-0 inset-x-0 h-1 rounded-t-2xl bg-gradient-to-r ${meta.gradient}`} />}
        <div className="flex items-start gap-3">
          <div className={`w-12 h-12 rounded-xl flex items-center justify-center shrink-0 shadow-sm ${isEarned ? `bg-gradient-to-br ${meta.gradient}` : 'bg-muted'}`}>
            <Icon className={`w-6 h-6 ${isEarned ? 'text-white' : 'text-muted-foreground/50'}`} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <h3 className={`font-semibold text-sm ${isEarned ? 'text-foreground' : 'text-muted-foreground'}`}>
                {isRTL ? meta.title_ar : meta.title_en}
              </h3>
              {isEarned && (
                <Badge className="bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 border-0 text-[10px] px-1.5 h-5">
                  <CheckCircle2 className="w-3 h-3 me-0.5" />
                  {t('earned')}
                </Badge>
              )}
            </div>
            <p className="text-xs text-muted-foreground mb-2">{isRTL ? meta.desc_ar : meta.desc_en}</p>
            {!isEarned && (
              <div className="space-y-1">
                <div className="flex justify-between text-[10px] text-muted-foreground">
                  <span>{badge.current}/{badge.threshold}</span>
                  <span>{badge.progress}%</span>
                </div>
                <Progress value={badge.progress} className="h-1.5" />
              </div>
            )}
          </div>
        </div>
      </div>
    );
  };

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="sticky top-0 z-20 bg-white/90 dark:bg-gray-900/90 backdrop-blur-sm border-b p-4">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-2xl font-bold text-brand-navy dark:text-brand-turquoise font-cairo">
                {t('myAchievements')}
              </h1>
              <p className="text-sm text-muted-foreground">
                {t('trackYourTeachingAchievementsAndProfessionalProgre')}
              </p>
            </div>
            <Button onClick={fetchData} variant="outline" size="sm" disabled={loading}>
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
              <span className="ms-2">{t('refresh')}</span>
            </Button>
          </div>
        </div>

        <div className="p-4 max-w-[1400px] mx-auto space-y-5">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 gap-3">
              <Loader2 className="h-8 w-8 animate-spin text-amber-500" />
              <p className="text-sm text-muted-foreground font-tajawal">{t('loadingAchievements')}</p>
            </div>
          ) : !data ? (
            <Card>
              <CardContent className="text-center py-16">
                <Trophy className="h-16 w-16 mx-auto mb-4 text-muted-foreground/30" />
                <p className="text-muted-foreground font-cairo">{t('noDataAvailable')}</p>
              </CardContent>
            </Card>
          ) : (
            <>
              <Card className="border-0 shadow-md overflow-hidden">
                <div className="bg-gradient-to-r from-amber-500 via-orange-500 to-red-500 p-5 text-white">
                  <div className="flex items-center justify-between flex-wrap gap-4">
                    <div className="flex items-center gap-4">
                      <div className="w-16 h-16 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
                        <Trophy className="w-8 h-8 text-white" />
                      </div>
                      <div>
                        <h2 className="text-xl font-bold font-cairo">{levelTitle}</h2>
                        <p className="text-white/80 text-sm mt-0.5">
                          {isRTL ? `حصلت على ${earnedCount} من أصل ${totalCount} إنجاز` : `Earned ${earnedCount} of ${totalCount} achievements`}
                        </p>
                      </div>
                    </div>
                    <div className="text-center">
                      <div className="text-4xl font-bold font-cairo">{earnedCount}</div>
                      <div className="text-white/70 text-sm">/{totalCount}</div>
                    </div>
                  </div>
                  <div className="mt-4">
                    <Progress value={levelPercent} className="h-3 bg-white/20" />
                  </div>
                </div>
              </Card>

              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 lg:grid-cols-5 gap-3">
                {[
                  { label: isRTL ? 'الحصص' : 'Sessions', value: m.total_sessions, icon: BookOpen, color: 'text-blue-600', bg: 'bg-blue-50 dark:bg-blue-950/30' },
                  { label: t('students'), value: m.total_students, icon: Users, color: 'text-green-600', bg: 'bg-green-50 dark:bg-green-950/30' },
                  { label: t('classes2'), value: m.total_classes, icon: BookOpen, color: 'text-indigo-600', bg: 'bg-indigo-50 dark:bg-indigo-950/30' },
                  { label: t('attendance2'), value: `${m.attendance_rate}%`, icon: ClipboardCheck, color: 'text-emerald-600', bg: 'bg-emerald-50 dark:bg-emerald-950/30' },
                  { label: t('performance3'), value: `${m.avg_performance}%`, icon: Target, color: 'text-cyan-600', bg: 'bg-cyan-50 dark:bg-cyan-950/30' },
                ].map((stat, i) => (
                  <Card key={i} className="overflow-hidden">
                    <CardContent className={`p-3 text-center ${stat.bg}`}>
                      <stat.icon className={`w-5 h-5 mx-auto mb-1 ${stat.color}`} />
                      <div className={`text-xl font-bold font-cairo ${stat.color}`}>{stat.value}</div>
                      <div className="text-[10px] text-muted-foreground font-tajawal">{stat.label}</div>
                    </CardContent>
                  </Card>
                ))}
              </div>

              <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList className="mb-4 bg-muted/50">
                  <TabsTrigger value="badges" className="gap-1.5">
                    <Award className="h-3.5 w-3.5" />
                    {t('badges')}
                    <Badge className="bg-amber-500 text-white text-[9px] px-1.5 h-4 border-0">{earnedCount}/{totalCount}</Badge>
                  </TabsTrigger>
                  <TabsTrigger value="stats" className="gap-1.5">
                    <BarChart3 className="h-3.5 w-3.5" />
                    {t('statistics2')}
                  </TabsTrigger>
                  <TabsTrigger value="timeline" className="gap-1.5">
                    <Clock className="h-3.5 w-3.5" />
                    {t('monthlyActivity')}
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="badges">
                  <div className="space-y-5">
                    {(data.earned_badges || []).length > 0 && (
                      <div>
                        <h2 className="text-base font-semibold mb-3 flex items-center gap-2 font-cairo">
                          <CheckCircle2 className="w-5 h-5 text-green-500" />
                          {t('earnedAchievements')}
                          <Badge className="bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300 border-0">{data.earned_badges.length}</Badge>
                        </h2>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          {data.earned_badges.map(b => renderBadgeCard(b, true))}
                        </div>
                      </div>
                    )}

                    {(data.in_progress_badges || []).length > 0 && (
                      <div>
                        <h2 className="text-base font-semibold mb-3 flex items-center gap-2 font-cairo">
                          <Target className="w-5 h-5 text-amber-500" />
                          {t('inProgress')}
                        </h2>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          {data.in_progress_badges.map(b => renderBadgeCard(b, false))}
                        </div>
                      </div>
                    )}

                    {earnedCount === 0 && (data.in_progress_badges || []).length === 0 && (
                      <Card>
                        <CardContent className="p-10 text-center">
                          <Sparkles className="w-14 h-14 mx-auto text-amber-400 mb-4" />
                          <h3 className="font-bold text-lg font-cairo mb-2">{t('startYourTeachingJourney')}</h3>
                          <p className="text-sm text-muted-foreground">{t('earnYourFirstAchievementByConductingSessionsAndEng')}</p>
                        </CardContent>
                      </Card>
                    )}
                  </div>
                </TabsContent>

                <TabsContent value="stats">
                  <div className="grid md:grid-cols-2 gap-4">
                    <Card>
                      <CardHeader className="pb-3">
                        <CardTitle className="text-base font-cairo flex items-center gap-2">
                          <Activity className="h-4 w-4 text-brand-turquoise" />
                          {t('detailedPerformanceMetrics')}
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        {[
                          { label: t('sessionsCompleted'), value: m.total_sessions, max: 100, color: 'bg-blue-500' },
                          { label: t('regularityRate'), value: m.regularity_rate, max: 100, suffix: '%', color: 'bg-emerald-500' },
                          { label: t('attendanceRate'), value: m.attendance_rate, max: 100, suffix: '%', color: 'bg-green-500' },
                          { label: t('participationRate'), value: m.participation_rate, max: 100, suffix: '%', color: 'bg-pink-500' },
                          { label: t('avgPerformance'), value: m.avg_performance, max: 100, suffix: '%', color: 'bg-cyan-500' },
                        ].map((item, i) => (
                          <div key={i}>
                            <div className="flex justify-between text-sm mb-1">
                              <span className="text-muted-foreground text-xs">{item.label}</span>
                              <span className="font-bold font-cairo text-xs">{item.value}{item.suffix || ''}</span>
                            </div>
                            <div className="h-2 bg-muted/30 rounded-full overflow-hidden">
                              <div className={`h-full ${item.color} rounded-full transition-all duration-700`} style={{ width: `${Math.min(100, (item.value / item.max) * 100)}%` }} />
                            </div>
                          </div>
                        ))}
                      </CardContent>
                    </Card>

                    <Card>
                      <CardHeader className="pb-3">
                        <CardTitle className="text-base font-cairo flex items-center gap-2">
                          <BarChart3 className="h-4 w-4 text-amber-500" />
                          {t('additionalStats')}
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="grid grid-cols-2 gap-3">
                          {[
                            { label: t('assessments'), value: m.total_assessments, icon: GraduationCap, color: 'text-violet-600', bg: 'bg-violet-50 dark:bg-violet-950/30' },
                            { label: t('positive2'), value: m.positive_behavior, icon: ThumbsUp, color: 'text-green-600', bg: 'bg-green-50 dark:bg-green-950/30' },
                            { label: t('negative2'), value: m.negative_behavior, icon: TrendingUp, color: 'text-red-600', bg: 'bg-red-50 dark:bg-red-950/30' },
                            { label: isRTL ? 'الملاحظات' : 'Records', value: m.total_behavior_records, icon: ClipboardCheck, color: 'text-blue-600', bg: 'bg-blue-50 dark:bg-blue-950/30' },
                          ].map((s, i) => (
                            <div key={i} className={`p-3 rounded-xl text-center ${s.bg}`}>
                              <s.icon className={`w-5 h-5 mx-auto mb-1 ${s.color}`} />
                              <div className={`text-xl font-bold font-cairo ${s.color}`}>{s.value}</div>
                              <div className="text-[10px] text-muted-foreground">{s.label}</div>
                            </div>
                          ))}
                        </div>

                        {data.school_comparison && Object.keys(data.school_comparison).length > 0 && (
                          <div className="mt-4 p-3 rounded-xl border bg-gradient-to-r from-brand-turquoise/5 to-brand-navy/5 border-brand-turquoise/20">
                            <h4 className="text-xs font-semibold font-cairo mb-2 flex items-center gap-1.5">
                              <TrendingUp className="w-3.5 h-3.5 text-brand-turquoise" />
                              {t('schoolComparison')}
                            </h4>
                            <div className="flex justify-between text-xs">
                              <span className="text-muted-foreground">{t('avgSessionsteacher')}</span>
                              <span className="font-bold font-cairo">{data.school_comparison.avg_sessions}</span>
                            </div>
                            <div className="flex justify-between text-xs mt-1">
                              <span className="text-muted-foreground">{t('yourSessions')}</span>
                              <span className={`font-bold font-cairo ${m.total_sessions >= (data.school_comparison.avg_sessions || 0) ? 'text-green-600' : 'text-amber-600'}`}>{m.total_sessions}</span>
                            </div>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  </div>
                </TabsContent>

                <TabsContent value="timeline">
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base font-cairo flex items-center gap-2">
                        <Calendar className="h-4 w-4 text-brand-turquoise" />
                        {t('monthlyActivityCompletedSessions')}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      {Object.keys(data.monthly_sessions || {}).length === 0 ? (
                        <div className="text-center py-10">
                          <Calendar className="h-10 w-10 mx-auto mb-3 text-muted-foreground/30" />
                          <p className="text-sm text-muted-foreground font-cairo">{t('noActivityDataYet')}</p>
                        </div>
                      ) : (
                        <div className="space-y-4">
                          <div className="flex items-end gap-2 h-40">
                            {Object.entries(data.monthly_sessions).sort(([a], [b]) => a.localeCompare(b)).slice(-12).map(([month, count], i) => {
                              const maxCount = Math.max(...Object.values(data.monthly_sessions));
                              const heightPct = maxCount > 0 ? (count / maxCount) * 100 : 0;
                              const barColor = count >= 20 ? 'bg-green-500' : count >= 10 ? 'bg-blue-500' : count >= 5 ? 'bg-amber-500' : 'bg-gray-400';
                              return (
                                <div key={month} className="flex-1 flex flex-col items-center gap-1">
                                  <span className="text-[10px] font-bold font-cairo text-muted-foreground">{count}</span>
                                  <div className="w-full bg-muted/30 rounded-t-lg overflow-hidden" style={{ height: '120px' }}>
                                    <div className={`w-full ${barColor} rounded-t-lg transition-all duration-700`} style={{ height: `${heightPct}%`, marginTop: `${100 - heightPct}%` }} />
                                  </div>
                                  <span className="text-[9px] text-muted-foreground text-center leading-tight">{month.slice(5)}</span>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </TabsContent>
              </Tabs>
            </>
          )}
        </div>
      </div>
    </Sidebar>
  );
}
