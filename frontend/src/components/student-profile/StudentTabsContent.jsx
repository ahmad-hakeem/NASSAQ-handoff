import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Label } from '../ui/label';
import { Input } from '../ui/input';
import { Progress } from '../ui/progress';
import { TabsContent } from '../ui/tabs';
import { Skeleton } from '../ui/skeleton';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip as RechartsTooltip, Cell, RadarChart, PolarGrid,
  PolarAngleAxis, PolarRadiusAxis, Radar, LineChart, Line, Legend
} from 'recharts';
import {
  User, BookOpen, Shield, Brain, FileText, Edit,
  Calendar, ArrowLeft, ArrowRight, ChevronRight,
  Star, Loader2, Activity, Target, Sparkles, Clock,
  CheckCircle, AlertTriangle, Zap, Heart, Plus, XCircle,
  ThumbsUp, ThumbsDown, MessageSquare, Trophy,
  Eye, BarChart3, ScrollText,
  Medal, ClipboardList, TrendingUp, Briefcase, Crown, Layers,
  GraduationCap, Stethoscope, Rocket, Trash2
} from 'lucide-react';
import {
  TALENT_OPTIONS, getTalentConfig,
  HakimPlanCard, EmptyState, DataField
} from './ProfileComponents';
import { Download } from 'lucide-react';

import { useTranslation } from '../../contexts/ThemeContext';
import { formatBehaviorDate, localizeBehaviorEnum } from '../../utils/behaviorFormat';
export function OverviewTab({ hook }) {
  const { t } = useTranslation();
  const {
    isRTL, student, classNameFromState, classDetail,
    attendanceRate, loadingAttendance, homeworkRate, loadingHomework,
    behaviourSummary, loadingBehaviour, profileCompleteness,
    setFormData, setEditProfileOpen, setActiveTab, openHealthModal,
  } = hook;

  const relationshipMap = { father: t('father'), mother: t('mother'), guardian: isRTL ? 'ولي أمر' : 'Guardian', brother: t('brother'), sister: t('sister'), uncle: t('uncle'), other: t('other') };

  return (
    <TabsContent value="overview" className="mt-6 space-y-4">
      <Card className="border-brand-turquoise/20 bg-gradient-to-r from-brand-turquoise/5 to-brand-purple/5 dark:from-brand-turquoise/10 dark:to-brand-purple/10">
        <CardContent className="p-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-bold text-sm font-cairo flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-brand-turquoise" />
              {t('profileCompleteness')}
            </h3>
            <span className={`text-sm font-bold font-cairo tabular-nums ${profileCompleteness.percent === 100 ? 'text-green-600' : profileCompleteness.percent >= 70 ? 'text-brand-turquoise' : 'text-amber-600'}`}>{profileCompleteness.percent}%</span>
          </div>
          <Progress value={profileCompleteness.percent} className={`h-2.5 ${profileCompleteness.percent === 100 ? '[&>div]:bg-green-500' : profileCompleteness.percent >= 70 ? '[&>div]:bg-brand-turquoise' : '[&>div]:bg-amber-500'}`} />
          {profileCompleteness.missing.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2.5">
              <span className="text-[11px] text-muted-foreground font-cairo">{t('missing')}</span>
              {profileCompleteness.missing.slice(0, 4).map(f => (
                <Badge key={f.key} variant="outline" className="text-[10px] px-1.5 py-0 h-5 cursor-pointer hover:bg-brand-turquoise/10 border-dashed" onClick={() => { setFormData({ ...student }); setEditProfileOpen(true); }}>
                  {isRTL ? f.ar : f.en}
                </Badge>
              ))}
              {profileCompleteness.missing.length > 4 && (
                <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-5 cursor-pointer hover:bg-brand-turquoise/10 border-dashed" onClick={() => { setFormData({ ...student }); setEditProfileOpen(true); }}>
                  +{profileCompleteness.missing.length - 4}
                </Badge>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-5">
            <h3 className="font-bold text-sm font-cairo flex items-center gap-2 mb-4">
              <User className="h-4 w-4 text-brand-turquoise" />
              {isRTL ? 'البيانات الشخصية' : 'Personal Info'}
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <DataField label={t('fullName')} value={student.full_name} />
              <DataField label={t('nationalId')} value={student.national_id} icon={User} />
              <DataField label={t('email2')} value={student.email} icon={User} />
              <DataField label={t('phone2')} value={student.phone} icon={User} />
              <DataField label={t('gender')} value={student.gender === 'male' ? (t('male')) : student.gender === 'female' ? (t('female')) : null} />
              <DataField label={t('dateOfBirth')} value={student.date_of_birth} icon={Calendar} />
              <DataField label={t('nationality')} value={student.nationality} icon={User} />
              <DataField label={t('enrollmentDate')} value={student.enrollment_date} icon={Calendar} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-5">
            <h3 className="font-bold text-sm font-cairo flex items-center gap-2 mb-4">
              <Heart className="h-4 w-4 text-rose-500" />
              {t('guardianEmergency')}
            </h3>
            {student.parent_name ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <DataField label={t('name')} value={student.parent_name} />
                  <DataField label={t('relationship')} value={relationshipMap[student.parent_relationship] || student.parent_relationship} />
                  <DataField label={t('phone2')} value={student.parent_phone} icon={User} />
                  <DataField label={t('email')} value={student.parent_email} icon={User} />
                </div>
                {(student.emergency_contact || student.emergency_phone) && (
                  <div className="border-t pt-3">
                    <p className="text-[11px] text-muted-foreground font-cairo mb-2 flex items-center gap-1">
                      <AlertTriangle className="h-3 w-3 text-amber-500" />
                      {t('emergencyContact')}
                    </p>
                    <div className="grid grid-cols-2 gap-4">
                      <DataField label={t('name')} value={student.emergency_contact} />
                      <DataField label={t('phone2')} value={student.emergency_phone} icon={User} />
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <EmptyState icon={Heart} message={t('noGuardianInfoAdded')} actionLabel={t('addInfo')} onAction={() => { setFormData({ ...student }); setEditProfileOpen(true); }} />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-5">
            <h3 className="font-bold text-sm font-cairo flex items-center gap-2 mb-4">
              <GraduationCap className="h-4 w-4 text-brand-navy" />
              {t('academicSnapshot')}
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <DataField label={isRTL ? 'الصف' : 'Class'} value={student.class_name || classNameFromState} icon={BookOpen} />
              <DataField label={t('homeroomTeacher')} value={classDetail?.homeroom_teacher_name} icon={User} />
              <div className="col-span-2 grid grid-cols-3 gap-3 pt-1">
                <div className="text-center p-2.5 bg-green-50 dark:bg-green-950/20 rounded-lg">
                  <p className={`text-xl font-bold font-cairo ${attendanceRate !== null ? (attendanceRate >= 80 ? 'text-green-600' : attendanceRate >= 60 ? 'text-amber-600' : 'text-red-600') : 'text-muted-foreground'}`}>
                    {loadingAttendance ? '...' : attendanceRate !== null ? `${attendanceRate}%` : '—'}
                  </p>
                  <p className="text-[10px] text-muted-foreground font-cairo">{t('attendance2')}</p>
                </div>
                <div className="text-center p-2.5 bg-blue-50 dark:bg-blue-950/20 rounded-lg">
                  <p className={`text-xl font-bold font-cairo ${homeworkRate ? (homeworkRate.rate >= 80 ? 'text-green-600' : homeworkRate.rate >= 50 ? 'text-amber-600' : 'text-red-600') : 'text-muted-foreground'}`}>
                    {loadingHomework ? '...' : homeworkRate ? `${homeworkRate.rate}%` : '—'}
                  </p>
                  <p className="text-[10px] text-muted-foreground font-cairo">{t('academic2')}</p>
                </div>
                <div className="text-center p-2.5 bg-purple-50 dark:bg-purple-950/20 rounded-lg">
                  <p className="text-xl font-bold font-cairo text-brand-navy">
                    {loadingBehaviour ? '...' : behaviourSummary ? (behaviourSummary.total_points || 0) : '—'}
                  </p>
                  <p className="text-[10px] text-muted-foreground font-cairo">{t('behavior')}</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-sm font-cairo flex items-center gap-2">
                <Stethoscope className="h-4 w-4 text-rose-500" />
                {t('healthNotes')}
              </h3>
              {student.health_info && Object.keys(student.health_info).length > 0 && (
                <Button size="sm" variant="ghost" className="h-7 gap-1.5 text-xs text-brand-turquoise hover:text-brand-turquoise hover:bg-brand-turquoise/10" onClick={openHealthModal}>
                  <Edit className="h-3.5 w-3.5" /> {t('edit')}
                </Button>
              )}
            </div>
            {student.health_info && Object.keys(student.health_info).length > 0 ? (
              <div className="space-y-3">
                {student.health_info.blood_type && <DataField label={t('bloodType')} value={student.health_info.blood_type} />}
                {student.health_info.has_chronic_conditions && student.health_info.chronic_conditions && (
                  <div><p className="text-[11px] text-muted-foreground font-cairo mb-1">{t('chronicConditions')}</p><p className="text-sm font-cairo">{student.health_info.chronic_conditions}</p></div>
                )}
                {student.health_info.has_allergies && student.health_info.allergies && (
                  <div><p className="text-[11px] text-muted-foreground font-cairo mb-1">{t('allergies')}</p><p className="text-sm font-cairo">{student.health_info.allergies}</p></div>
                )}
                {student.health_info.has_disabilities && student.health_info.disabilities && (
                  <div><p className="text-[11px] text-muted-foreground font-cairo mb-1">{t('disabilities')}</p><p className="text-sm font-cairo">{student.health_info.disabilities}</p></div>
                )}
                {student.health_info.requires_special_care && student.health_info.special_care_notes && (
                  <div className="p-2 bg-amber-50 dark:bg-amber-950/20 rounded-lg border border-amber-200 dark:border-amber-800/30">
                    <p className="text-[11px] text-amber-600 font-cairo mb-1 flex items-center gap-1"><AlertTriangle className="h-3 w-3" />{t('specialCareNotes')}</p>
                    <p className="text-sm font-cairo">{student.health_info.special_care_notes}</p>
                  </div>
                )}
                {student.health_info.emergency_medical_notes && (
                  <div className="p-2 bg-red-50 dark:bg-red-950/20 rounded-lg border border-red-200 dark:border-red-800/30">
                    <p className="text-[11px] text-red-600 font-cairo mb-1 flex items-center gap-1"><Heart className="h-3 w-3" />{t('emergencyMedicalNotes')}</p>
                    <p className="text-sm font-cairo">{student.health_info.emergency_medical_notes}</p>
                  </div>
                )}
              </div>
            ) : (
              <EmptyState icon={Stethoscope} message={t('noHealthInfoRecorded')} actionLabel={t('addInfo')} onAction={openHealthModal} />
            )}
          </CardContent>
        </Card>
      </div>

      <ParentProvidedNotesCard student={student} isRTL={isRTL} />

      {(student.talents?.length > 0) && (
        <Card>
          <CardContent className="p-5">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-bold text-sm font-cairo flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-brand-turquoise" />
                {t('talents')}
              </h3>
              <Button variant="ghost" size="sm" className="text-xs text-brand-turquoise" onClick={() => setActiveTab('talents')}>
                {t('viewAll')} <ChevronRight className="h-3 w-3 ms-1" />
              </Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {student.talents.slice(0, 6).map(t => {
                const cfg = getTalentConfig(t);
                return (
                  <Badge key={t} variant="outline" className={`text-xs px-2.5 py-1 border ${cfg.color}`}>
                    <Star className="h-3 w-3 me-1 fill-current" />
                    {isRTL ? cfg.ar : cfg.en}
                  </Badge>
                );
              })}
              {student.talents.length > 6 && <Badge variant="outline" className="text-xs px-2.5 py-1">+{student.talents.length - 6}</Badge>}
            </div>
          </CardContent>
        </Card>
      )}
    </TabsContent>
  );
}

export function AcademicTab({ hook }) {
  const { t } = useTranslation();
  const {
    isRTL, attendanceSummary, loadingAttendance, loadingAttendanceHistory,
    attendanceChartData, homeworkRate, loadingHomework, loadingGrades,
    subjectGrades, riskData, loadingRisk, fetchRiskData,
    getRiskColor, getRiskLabel, getRiskBarColor,
  } = hook;

  return (
    <TabsContent value="academic" className="mt-6 space-y-4">
      <Card>
        <CardContent className="p-6 space-y-4">
          <h3 className="font-bold text-base font-cairo flex items-center gap-2">
            <Activity className="h-5 w-5 text-brand-turquoise" />
            {t('attendanceSummary')}
          </h3>
          {loadingAttendance ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">{[...Array(4)].map((_, i) => <Skeleton key={i} className="h-20 rounded-xl" />)}</div>
          ) : attendanceSummary ? (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: t('present'), value: attendanceSummary.present_days ?? attendanceSummary.present_count ?? attendanceSummary.present ?? 0, color: 'text-green-600', bg: 'bg-green-50 dark:bg-green-950/20' },
                  { label: t('absent'), value: attendanceSummary.absent_days ?? attendanceSummary.absent_count ?? attendanceSummary.absent ?? 0, color: 'text-red-600', bg: 'bg-red-50 dark:bg-red-950/20' },
                  { label: t('excused2'), value: attendanceSummary.excused_days ?? attendanceSummary.excused_count ?? attendanceSummary.excused ?? 0, color: 'text-blue-600', bg: 'bg-blue-50 dark:bg-blue-950/20' },
                ].map((item, i) => (
                  <div key={i} className={`text-center p-4 rounded-xl ${item.bg}`}>
                    <p className={`text-2xl font-bold font-cairo ${item.color}`}>{item.value}</p>
                    <p className="text-xs text-muted-foreground mt-1">{item.label}</p>
                  </div>
                ))}
              </div>
              {loadingAttendanceHistory ? (
                <div className="space-y-2 pt-2"><Skeleton className="h-4 w-32" /><Skeleton className="h-48 w-full rounded-xl" /></div>
              ) : attendanceChartData.length > 0 ? (
                <div>
                  <h4 className="text-sm font-medium font-cairo mb-2">{t('monthlyAttendance')}</h4>
                  <div className="h-52">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={attendanceChartData} barGap={2}>
                        <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                        <XAxis dataKey="month" tick={{ fontSize: 11 }} tickFormatter={v => v.substring(5)} />
                        <YAxis tick={{ fontSize: 11 }} />
                        <RechartsTooltip contentStyle={{ borderRadius: 8, fontSize: 12 }} />
                        <Bar dataKey="present" name={t('present')} fill="#22c55e" radius={[3, 3, 0, 0]} />
                        <Bar dataKey="absent" name={t('absent')} fill="#ef4444" radius={[3, 3, 0, 0]} />
                        <Bar dataKey="excused" name={t('excused2')} fill="#3b82f6" radius={[3, 3, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              ) : null}
            </div>
          ) : (
            <EmptyState icon={Calendar} message={t('noAttendanceDataAvailable')} />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-6 space-y-4">
          <h3 className="font-bold text-base font-cairo flex items-center gap-2">
            <CheckCircle className="h-5 w-5 text-indigo-500" />
            {t('gradesAcademicPerformance')}
          </h3>
          {loadingHomework || loadingGrades ? (
            <div className="space-y-3">
              <Skeleton className="h-4 w-full rounded" />
              <div className="grid grid-cols-2 gap-3"><Skeleton className="h-20 rounded-xl" /><Skeleton className="h-20 rounded-xl" /></div>
              <Skeleton className="h-48 rounded-xl" />
            </div>
          ) : (
            <div className="space-y-4">
              {homeworkRate && (
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <div className="flex-1">
                      <Progress value={homeworkRate.rate} className={`h-3 rounded-full bg-gray-100 dark:bg-gray-800 ${homeworkRate.rate >= 80 ? '[&>div]:bg-green-500' : homeworkRate.rate >= 50 ? '[&>div]:bg-amber-500' : '[&>div]:bg-red-500'}`} />
                    </div>
                    <span className={`text-lg font-bold font-cairo tabular-nums ${homeworkRate.rate >= 80 ? 'text-green-600' : homeworkRate.rate >= 50 ? 'text-amber-600' : 'text-red-600'}`}>{homeworkRate.rate}%</span>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="text-center p-3 bg-green-50 dark:bg-green-950/20 rounded-xl">
                      <p className="text-xl font-bold font-cairo text-green-600">{homeworkRate.completed}</p>
                      <p className="text-xs text-muted-foreground mt-1">{t('graded')}</p>
                    </div>
                    <div className="text-center p-3 bg-gray-50 dark:bg-gray-800/30 rounded-xl">
                      <p className="text-xl font-bold font-cairo text-gray-600">{homeworkRate.total}</p>
                      <p className="text-xs text-muted-foreground mt-1">{t('totalAssessments')}</p>
                    </div>
                  </div>
                </div>
              )}
              {subjectGrades.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium font-cairo mb-3 flex items-center gap-2">
                    <BookOpen className="h-4 w-4 text-brand-navy" />
                    {t('gradesBySubject')}
                  </h4>
                  <div className="rounded-lg border overflow-hidden">
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="bg-muted/50">
                            <th className="text-start p-3 font-medium font-cairo">{t('subject')}</th>
                            <th className="text-center p-3 font-medium font-cairo">{isRTL ? 'الدرجة' : 'Score'}</th>
                            <th className="text-center p-3 font-medium font-cairo">{t('outOf')}</th>
                            <th className="text-center p-3 font-medium font-cairo">%</th>
                          </tr>
                        </thead>
                        <tbody>
                          {subjectGrades.map((g, i) => {
                            const score = g.score ?? g.grade ?? g.marks ?? 0;
                            const total = g.total ?? g.max_score ?? g.out_of ?? 100;
                            const pct = total > 0 ? Math.round((score / total) * 100) : 0;
                            return (
                              <tr key={i} className="border-t hover:bg-muted/20 transition-colors">
                                <td className="p-3 font-cairo">{g.subject_name || g.subject || g.name || '—'}</td>
                                <td className="p-3 text-center font-cairo tabular-nums font-medium">{score}</td>
                                <td className="p-3 text-center font-cairo tabular-nums text-muted-foreground">{total}</td>
                                <td className="p-3 text-center">
                                  <span className={`font-bold font-cairo tabular-nums ${pct >= 80 ? 'text-green-600' : pct >= 60 ? 'text-amber-600' : 'text-red-600'}`}>{pct}%</span>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                  <div className="h-52 mt-4">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={subjectGrades.map(g => ({
                        name: (g.subject_name || g.subject || g.name || '').substring(0, 12),
                        score: g.score ?? g.grade ?? g.marks ?? 0,
                        total: g.total ?? g.max_score ?? g.out_of ?? 100,
                      }))}>
                        <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                        <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                        <YAxis tick={{ fontSize: 11 }} />
                        <RechartsTooltip contentStyle={{ borderRadius: 8, fontSize: 12 }} />
                        <Bar dataKey="score" name={isRTL ? 'الدرجة' : 'Score'} radius={[4, 4, 0, 0]}>
                          {subjectGrades.map((g, idx) => {
                            const score = g.score ?? g.grade ?? g.marks ?? 0;
                            const total = g.total ?? g.max_score ?? g.out_of ?? 100;
                            const pct = total > 0 ? (score / total) * 100 : 0;
                            return <Cell key={idx} fill={pct >= 80 ? '#22c55e' : pct >= 60 ? '#f59e0b' : '#ef4444'} />;
                          })}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}
              {!homeworkRate && subjectGrades.length === 0 && (
                <EmptyState icon={BarChart3} message={t('noGradesRecordedYet')} />
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-base font-cairo flex items-center gap-2">
              <Brain className="h-5 w-5 text-brand-purple" />
              {t('aiAnalysis2')}
            </h3>
            <Button variant="ghost" size="sm" onClick={fetchRiskData} className="text-xs">
              <Activity className="h-3.5 w-3.5 me-1" /> {t('refresh')}
            </Button>
          </div>
          {loadingRisk ? (
            <div className="space-y-3">
              <Skeleton className="h-24 rounded-xl" />
              <div className="grid grid-cols-4 gap-3">{[...Array(4)].map((_, i) => <Skeleton key={i} className="h-20 rounded-xl" />)}</div>
            </div>
          ) : riskData ? (
            <>
              <div className="bg-gradient-to-br from-brand-navy/5 to-brand-purple/5 dark:from-brand-navy/20 dark:to-brand-purple/10 p-4 rounded-xl">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-bold text-sm font-cairo">{t('overallPerformance')}</h4>
                  <Badge className={getRiskColor(riskData.risk_category)}>{getRiskLabel(riskData.risk_category)}</Badge>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex-1"><Progress value={riskData.risk_score || 0} className={`h-3 rounded-full bg-gray-100 dark:bg-gray-800 ${getRiskBarColor(riskData.risk_category)}`} /></div>
                  <span className="text-lg font-bold font-cairo tabular-nums">{Math.round(riskData.risk_score || 0)}%</span>
                </div>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {riskData.breakdown && Object.entries(riskData.breakdown).map(([key, val]) => {
                  const labels = {
                    attendance: { ar: 'الحضور', icon: <Calendar className="h-4 w-4" /> },
                    participation: { ar: 'المشاركة', icon: <Zap className="h-4 w-4" /> },
                    behaviour: { ar: 'السلوك', icon: <Shield className="h-4 w-4" /> },
                    academic: { ar: 'الأكاديمي', icon: <BookOpen className="h-4 w-4" /> },
                  };
                  const lbl = labels[key] || { ar: key, icon: <Activity className="h-4 w-4" /> };
                  const score = Math.round(typeof val === 'number' ? val : val?.score || 0);
                  const scoreColor = score >= 80 ? 'text-green-600' : score >= 60 ? 'text-amber-600' : 'text-red-600';
                  return (
                    <div key={key} className="text-center p-3 bg-muted/30 rounded-xl">
                      <div className="flex justify-center text-muted-foreground mb-1.5">{lbl.icon}</div>
                      <p className={`text-xl font-bold font-cairo ${scoreColor}`}>{score}%</p>
                      <p className="text-[11px] text-muted-foreground font-tajawal mt-0.5">{isRTL ? lbl.ar : key}</p>
                    </div>
                  );
                })}
              </div>
              {riskData.factors?.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium flex items-center gap-2"><Target className="h-4 w-4 text-brand-turquoise" /> {t('keyObservations')}</h4>
                  {riskData.factors.map((f, i) => (
                    <div key={i} className="flex items-start gap-2 text-sm p-2.5 bg-amber-50/60 dark:bg-amber-950/10 rounded-lg border border-amber-100 dark:border-amber-800/20">
                      <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
                      <span className="text-sm">{f.message || f.message_ar || f}</span>
                    </div>
                  ))}
                </div>
              )}
            </>
          ) : (
            <EmptyState icon={Brain} message={t('noAnalyticsAvailableYet')} />
          )}
        </CardContent>
      </Card>
    </TabsContent>
  );
}

export function TalentsTab({ hook }) {
  const { t } = useTranslation();
  const {
    isRTL, student, globalTalents, loadingGlobalTalents,
    customTalentName, setCustomTalentName, addingCustomTalent,
    savingTalent, radarChartData,
    handleAddTalent, handleRemoveTalent, handleAddCustomTalent,
    CAREER_AFFINITY_MAP,
  } = hook;

  return (
    <TabsContent value="talents" className="mt-6 space-y-4">
      <Card>
        <CardContent className="p-6 space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-base font-cairo flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-brand-turquoise" />
              {t('talentsSkills')}
            </h3>
            {student?.is_gifted && (
              <Badge className="bg-gradient-to-r from-yellow-400 to-amber-500 text-white border-0 px-3 py-1 font-cairo">
                <Trophy className="h-3.5 w-3.5 me-1" />
                {t('giftedStudent')}
              </Badge>
            )}
          </div>

          <div>
            <Label className="text-sm font-cairo mb-3 block text-muted-foreground">{t('currentTalents')}</Label>
            {(student?.talents?.length > 0) ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                {student.talents.map(t => {
                  const opt = TALENT_OPTIONS.find(o => o.value === t);
                  return (
                    <div key={t} className={`relative p-3 rounded-xl border text-center transition-all hover:shadow-sm ${opt?.color || 'bg-gray-50 text-gray-700 border-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-600'}`}>
                      <button onClick={() => handleRemoveTalent(t)} disabled={savingTalent}
                        className="absolute top-1.5 end-1.5 hover:text-red-500 transition-colors rounded-full p-0.5 opacity-50 hover:opacity-100">
                        <XCircle className="h-3.5 w-3.5" />
                      </button>
                      <Star className="h-5 w-5 mx-auto mb-1.5 fill-current opacity-60" />
                      <p className="text-sm font-cairo font-medium">{opt ? (isRTL ? opt.ar : opt.en) : t}</p>
                    </div>
                  );
                })}
              </div>
            ) : (
              <EmptyState icon={Sparkles} message={t('noTalentsSelectedYet')} />
            )}
          </div>

          <div>
            <Label className="text-sm font-cairo mb-3 block text-muted-foreground">{t('addTalent')}</Label>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
              {TALENT_OPTIONS.filter(o => !(student?.talents || []).includes(o.value)).map(opt => (
                <Button key={opt.value} variant="outline" size="sm" disabled={savingTalent} onClick={() => handleAddTalent(opt.value)}
                  className={`text-xs font-cairo justify-start gap-1.5 ${opt.color}`}>
                  <Plus className="h-3 w-3" />
                  {isRTL ? opt.ar : opt.en}
                </Button>
              ))}
            </div>
          </div>

          {globalTalents.length > 0 && (
            <div>
              <Label className="text-sm font-cairo mb-3 block text-muted-foreground">{t('schoolTalents')}</Label>
              <div className="flex flex-wrap gap-2">
                {globalTalents.filter(gt => !(student?.talents || []).includes(gt.value) && !TALENT_OPTIONS.some(o => o.value === gt.value)).map(gt => (
                  <Button key={gt.id} variant="outline" size="sm" disabled={savingTalent} onClick={() => handleAddTalent(gt.value)} className="text-xs font-cairo gap-1.5">
                    <Plus className="h-3 w-3" /> {isRTL ? gt.name_ar : (gt.name_en || gt.name_ar)}
                  </Button>
                ))}
              </div>
            </div>
          )}

          <div>
            <Label className="text-sm font-cairo mb-2 block text-muted-foreground">{t('addCustomTalent')}</Label>
            <div className="flex gap-2">
              <Input value={customTalentName} onChange={e => setCustomTalentName(e.target.value)}
                placeholder={t('typeTalentName')} className="flex-1 text-sm font-cairo"
                onKeyDown={e => e.key === 'Enter' && handleAddCustomTalent()} />
              <Button size="sm" disabled={addingCustomTalent || !customTalentName.trim()} onClick={handleAddCustomTalent} className="bg-brand-turquoise hover:bg-brand-turquoise/90 text-white">
                {addingCustomTalent ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              </Button>
            </div>
          </div>

          {loadingGlobalTalents && (
            <div className="flex justify-center py-4"><Loader2 className="h-6 w-6 animate-spin text-brand-turquoise" /></div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-6">
          <h3 className="font-bold text-base font-cairo flex items-center gap-2 mb-4">
            <Target className="h-5 w-5 text-brand-purple" />
            {t('skillsRadar')}
          </h3>
          {(student?.talents?.length > 0) ? (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart cx="50%" cy="50%" outerRadius="75%" data={radarChartData}>
                  <PolarGrid strokeDasharray="3 3" />
                  <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 11, fontFamily: 'Cairo' }} />
                  <PolarRadiusAxis angle={30} domain={[0, 100]} tick={{ fontSize: 9 }} />
                  <Radar name={t('skills')} dataKey="value" stroke="#46C1BE" fill="#46C1BE" fillOpacity={0.3} strokeWidth={2} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState icon={Target} message={t('addTalentsToSeeSkillsRadar')} />
          )}
        </CardContent>
      </Card>

      <Card className="border-brand-purple/20 bg-gradient-to-r from-brand-purple/5 to-brand-navy/5 dark:from-brand-purple/10 dark:to-brand-navy/10">
        <CardContent className="p-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-bold text-base font-cairo flex items-center gap-2">
              <Rocket className="h-5 w-5 text-brand-purple" />
              {t('careerAffinityIndicators')}
            </h3>
            <Badge variant="outline" className="text-[10px] border-dashed text-muted-foreground">
              {t('earlyIndicators')}
            </Badge>
          </div>
          {(student?.talents?.length > 0) ? (
            <div className="space-y-3">
              <div className="flex flex-wrap gap-2">
                {student.talents.map(t => CAREER_AFFINITY_MAP[t]).filter(Boolean).filter((v, i, a) => a.findIndex(x => x.en === v.en) === i).map((career, i) => (
                  <Badge key={i} className="bg-brand-purple/10 text-brand-purple border-brand-purple/20 px-3 py-1.5 font-cairo">
                    <GraduationCap className="h-3.5 w-3.5 me-1.5" />
                    {isRTL ? career.ar : career.en}
                  </Badge>
                ))}
              </div>
              <p className="text-[11px] text-muted-foreground font-cairo flex items-center gap-1.5 mt-2 p-2 bg-muted/30 rounded-lg">
                <Brain className="h-3.5 w-3.5 text-brand-purple shrink-0" />
                {t('earlyIndicatorsNotFinalThisSectionWillBeAipoweredI')}
              </p>
            </div>
          ) : (
            <EmptyState icon={Rocket} message={t('addTalentsToSeeCareerAffinity')} />
          )}
        </CardContent>
      </Card>
    </TabsContent>
  );
}

export function BehaviourTab({ hook }) {
  const { t, language } = useTranslation();
  const {
    isRTL, student, user, isTeacher,
    behaviourRecords, behaviourSummary, loadingBehaviour, behaviourTrendData,
    paginatedBehaviourRecords, behaviourPage, setBehaviourPage, behaviourTotalPages,
    savingCharacterTrait, newCharacterTrait, setNewCharacterTrait,
    openBehaviourModal, handleDeleteBehaviour,
    handleAddCharacterTrait, handleRemoveCharacterTrait,
    CHARACTER_TRAIT_OPTIONS,
  } = hook;

  return (
    <TabsContent value="behaviour" className="mt-6 space-y-4">
      {behaviourSummary && (
        <div className="grid grid-cols-3 gap-3">
          {[
            { icon: ThumbsUp, value: behaviourSummary.positive_count || 0, label: t('positive'), color: 'text-green-500', bg: 'bg-green-50 dark:bg-green-950/20', border: 'border-green-200 dark:border-green-800' },
            { icon: ThumbsDown, value: behaviourSummary.negative_count || 0, label: t('negative'), color: 'text-red-500', bg: 'bg-red-50 dark:bg-red-950/20', border: 'border-red-200 dark:border-red-800' },
            { icon: MessageSquare, value: behaviourSummary.total_records || behaviourRecords.length, label: t('totalRecords'), color: 'text-blue-500', bg: 'bg-blue-50 dark:bg-blue-950/20', border: 'border-blue-200 dark:border-blue-800' },
          ].map((s, i) => (
            <Card key={i} className={`${s.border} ${s.bg}`}>
              <CardContent className="p-4 text-center">
                <s.icon className={`h-5 w-5 mx-auto mb-1 ${s.color}`} />
                <div className={`text-2xl font-bold font-cairo ${s.color}`}>{s.value}</div>
                <p className="text-xs text-muted-foreground font-cairo">{s.label}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {behaviourTrendData.length > 0 && (
        <Card>
          <CardContent className="p-6">
            <h3 className="font-bold text-base font-cairo flex items-center gap-2 mb-4">
              <BarChart3 className="h-5 w-5 text-brand-navy" />
              {t('monthlyBehaviorTrend')}
            </h3>
            <div className="h-52">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={behaviourTrendData} barGap={4}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis dataKey="month" tick={{ fontSize: 11 }} tickFormatter={v => v.substring(5)} />
                  <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                  <RechartsTooltip contentStyle={{ borderRadius: 8, fontSize: 12 }} />
                  <Bar dataKey="positive" name={t('positive')} fill="#22c55e" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="negative" name={t('negative')} fill="#ef4444" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent className="p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-base font-cairo flex items-center gap-2">
              <Activity className="h-5 w-5 text-brand-navy" />
              {t('behaviorLog')}
            </h3>
            <Button size="sm" onClick={() => openBehaviourModal()} className="bg-brand-navy hover:bg-brand-navy/90 text-white gap-1 font-cairo">
              <Plus className="h-4 w-4" /> {t('addRecord')}
            </Button>
          </div>

          {loadingBehaviour ? (
            <div className="space-y-3">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}</div>
          ) : behaviourRecords.length === 0 ? (
            <EmptyState icon={Activity} message={t('noBehaviorRecordsYet')} actionLabel={t('addRecord')} onAction={() => openBehaviourModal()} />
          ) : (
            <>
              <div className="space-y-3">
                {paginatedBehaviourRecords.map(rec => {
                  const catColors = { positive: 'border-s-green-500 bg-green-50/50 dark:bg-green-900/10', negative: 'border-s-red-500 bg-red-50/50 dark:bg-red-900/10', neutral: 'border-s-gray-400 bg-gray-50/50 dark:bg-gray-900/10' };
                  const catIcons = { positive: ThumbsUp, negative: ThumbsDown, neutral: MessageSquare };
                  const CatIcon = catIcons[rec.category] || MessageSquare;
                  const severityColors = { minor: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300', moderate: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300', major: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300', severe: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300' };
                  const statusColors = { pending: 'bg-yellow-100 text-yellow-700', reviewed: 'bg-blue-100 text-blue-700', escalated: 'bg-red-100 text-red-700', resolved: 'bg-green-100 text-green-700', archived: 'bg-gray-100 text-gray-700' };
                  return (
                    <Card key={rec.id} className={`border-s-4 ${catColors[rec.category] || catColors.neutral}`}>
                      <CardContent className="p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1 flex-wrap">
                              <CatIcon className={`h-4 w-4 flex-shrink-0 ${rec.category === 'positive' ? 'text-green-500' : rec.category === 'negative' ? 'text-red-500' : 'text-gray-400'}`} />
                              <span className="font-semibold text-sm font-cairo truncate">{rec.title}</span>
                              {rec.points != null && (
                                <Badge variant="outline" className={`text-xs ${rec.points > 0 ? 'text-green-600 border-green-300' : rec.points < 0 ? 'text-red-600 border-red-300' : 'text-gray-500 border-gray-300'}`}>
                                  {rec.points > 0 ? '+' : ''}{rec.points}
                                </Badge>
                              )}
                              {rec.category && <Badge variant="outline" className="text-xs font-cairo">{localizeBehaviorEnum(t, rec.category)}</Badge>}
                              {rec.severity && <Badge className={`text-xs font-cairo ${severityColors[rec.severity] || ''}`}>{localizeBehaviorEnum(t, rec.severity)}</Badge>}
                              {rec.status && <Badge className={`text-xs font-cairo ${statusColors[rec.status] || ''}`}>{localizeBehaviorEnum(t, rec.status)}</Badge>}
                            </div>
                            {rec.description && <p className="text-xs text-muted-foreground font-cairo mt-1 line-clamp-2">{rec.description}</p>}
                            <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
                              <span className="flex items-center gap-1 font-cairo"><Calendar className="h-3 w-3" />{formatBehaviorDate(rec.incident_date || rec.created_at, language)}</span>
                              {rec.reported_by_name && <span className="flex items-center gap-1"><User className="h-3 w-3" />{rec.reported_by_name}</span>}
                            </div>
                          </div>
                          <div className="flex items-center gap-1 flex-shrink-0">
                            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openBehaviourModal(rec)}>
                              <Edit className="h-3.5 w-3.5" />
                            </Button>
                            {!isTeacher && (
                              <Button variant="ghost" size="icon" className="h-7 w-7 text-red-500 hover:text-red-700" onClick={() => handleDeleteBehaviour(rec)}>
                                <Trash2 className="h-3.5 w-3.5" />
                              </Button>
                            )}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
              {behaviourTotalPages > 1 && (
                <div className="flex items-center justify-center gap-2 pt-2">
                  <Button variant="outline" size="sm" disabled={behaviourPage <= 1} onClick={() => setBehaviourPage(p => p - 1)} className="font-cairo">
                    {isRTL ? <ArrowRight className="h-4 w-4" /> : <ArrowLeft className="h-4 w-4" />}
                  </Button>
                  <span className="text-sm text-muted-foreground font-cairo tabular-nums">{behaviourPage} / {behaviourTotalPages}</span>
                  <Button variant="outline" size="sm" disabled={behaviourPage >= behaviourTotalPages} onClick={() => setBehaviourPage(p => p + 1)} className="font-cairo">
                    {isRTL ? <ArrowLeft className="h-4 w-4" /> : <ArrowRight className="h-4 w-4" />}
                  </Button>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-6 space-y-4">
          <h3 className="font-bold text-base font-cairo flex items-center gap-2">
            <Heart className="h-5 w-5 text-rose-500" />
            {t('characterTraits')}
          </h3>
          <p className="text-xs text-muted-foreground font-cairo">
            {t('positivePersonalityTagsAddedByTeachersToDescribeTh')}
          </p>

          {(student?.character_traits?.length > 0) ? (
            <div className="flex flex-wrap gap-2">
              {student.character_traits.map(trait => (
                <Badge key={trait} className="bg-gradient-to-r from-rose-50 to-purple-50 dark:from-rose-950/20 dark:to-purple-950/20 text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-800 px-3 py-1.5 font-cairo text-sm">
                  {trait}
                  <button onClick={() => handleRemoveCharacterTrait(trait)} disabled={savingCharacterTrait}
                    className="ms-1.5 hover:text-red-500 transition-colors">
                    <XCircle className="h-3.5 w-3.5" />
                  </button>
                </Badge>
              ))}
            </div>
          ) : (
            <EmptyState icon={Heart} message={t('noCharacterTraitsAddedYet')} />
          )}

          <div>
            <Label className="text-sm font-cairo mb-2 block text-muted-foreground">{t('addTrait')}</Label>
            <div className="flex flex-wrap gap-1.5 mb-3">
              {CHARACTER_TRAIT_OPTIONS
                .filter(opt => !(student?.character_traits || []).includes(isRTL ? opt.ar : opt.en))
                .map(opt => (
                  <Button key={opt.en} variant="outline" size="sm" disabled={savingCharacterTrait}
                    onClick={() => handleAddCharacterTrait(isRTL ? opt.ar : opt.en)}
                    className="text-xs font-cairo gap-1 h-7 px-2.5 hover:bg-rose-50 hover:border-rose-200 dark:hover:bg-rose-950/20">
                    <Plus className="h-3 w-3" /> {isRTL ? opt.ar : opt.en}
                  </Button>
                ))}
            </div>
            <div className="flex gap-2">
              <Input value={newCharacterTrait} onChange={e => setNewCharacterTrait(e.target.value)}
                placeholder={t('orTypeACustomTrait')}
                className="flex-1 text-sm font-cairo"
                onKeyDown={e => e.key === 'Enter' && handleAddCharacterTrait(newCharacterTrait)} />
              <Button size="sm" disabled={savingCharacterTrait || !newCharacterTrait.trim()}
                onClick={() => handleAddCharacterTrait(newCharacterTrait)}
                className="bg-rose-500 hover:bg-rose-600 text-white">
                {savingCharacterTrait ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </TabsContent>
  );
}

export function ActivitiesTab({ hook }) {
  const { t } = useTranslation();
  const {
    isRTL, user, isTeacher, student,
    activities, certificates, loadingActivities, involvementScore,
    openActivityModal, handleDeleteActivity,
    openCertificateModal, handleDeleteCertificate,
    ACTIVITY_TYPE_OPTIONS,
  } = hook;

  return (
    <TabsContent value="activities" className="mt-6 space-y-4">
      <Card className="bg-gradient-to-r from-brand-turquoise/5 to-brand-navy/5 dark:from-brand-turquoise/10 dark:to-brand-navy/10 border-brand-turquoise/20">
        <CardContent className="p-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-bold text-sm font-cairo flex items-center gap-2">
              <Zap className="h-4 w-4 text-brand-turquoise" />
              {t('extracurricularInvolvement')}
            </h3>
            <Badge className={`${involvementScore.color} text-white border-0 text-xs font-cairo`}>{involvementScore.label}</Badge>
          </div>
          <Progress value={involvementScore.percent} className="h-2" />
          <p className="text-[11px] text-muted-foreground mt-1.5 font-cairo">
            {isRTL ? `${activities.length} أنشطة · ${certificates.length} شهادات/جوائز` : `${activities.length} activities · ${certificates.length} certificates/awards`}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-base font-cairo flex items-center gap-2">
              <Medal className="h-5 w-5 text-brand-navy" />
              {t('activities')}
            </h3>
            {(user?.role === 'school_admin' || user?.role === 'admin' || user?.role === 'super_admin' || isTeacher) && (
              <Button size="sm" onClick={() => openActivityModal()} className="bg-brand-navy hover:bg-brand-navy/90 text-white gap-1 font-cairo">
                <Plus className="h-4 w-4" /> {t('addActivity')}
              </Button>
            )}
          </div>
          {loadingActivities ? (
            <div className="space-y-3">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-20 rounded-xl" />)}</div>
          ) : activities.length === 0 ? (
            <EmptyState icon={Medal} message={t('noActivitiesRecordedYet')} actionLabel={t('addActivity')} onAction={() => openActivityModal()} />
          ) : (
            <div className="space-y-2">
              {activities.map(act => {
                const typeOpt = ACTIVITY_TYPE_OPTIONS.find(o => o.value === act.activity_type) || ACTIVITY_TYPE_OPTIONS[6];
                return (
                  <div key={act.id} className="flex items-center gap-3 p-3 rounded-xl border hover:shadow-sm transition-all">
                    <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-lg flex-shrink-0 border ${typeOpt.color}`}>{typeOpt.icon}</div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-sm font-cairo truncate">{act.name}</span>
                        <Badge variant="outline" className={`text-[10px] ${typeOpt.color}`}>{isRTL ? typeOpt.ar : typeOpt.en}</Badge>
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                        {act.date && <span className="flex items-center gap-1"><Calendar className="h-3 w-3" />{act.date}</span>}
                        {act.role && <span className="flex items-center gap-1"><User className="h-3 w-3" />{act.role}</span>}
                      </div>
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openActivityModal(act)}><Edit className="h-3.5 w-3.5" /></Button>
                      {(user?.role === 'school_admin' || user?.role === 'admin' || user?.role === 'super_admin') && (
                        <Button variant="ghost" size="icon" className="h-7 w-7 text-red-500 hover:text-red-700" onClick={() => handleDeleteActivity(act)}><Trash2 className="h-3.5 w-3.5" /></Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-base font-cairo flex items-center gap-2">
              <Trophy className="h-5 w-5 text-amber-500" />
              {t('certificatesAwards')}
            </h3>
            {(user?.role === 'school_admin' || user?.role === 'admin' || user?.role === 'super_admin' || isTeacher) && (
              <Button size="sm" onClick={() => openCertificateModal()} className="bg-amber-500 hover:bg-amber-600 text-white gap-1 font-cairo">
                <Plus className="h-4 w-4" /> {t('addCertificate')}
              </Button>
            )}
          </div>
          {loadingActivities ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">{[...Array(2)].map((_, i) => <Skeleton key={i} className="h-32 rounded-xl" />)}</div>
          ) : certificates.length === 0 ? (
            <EmptyState icon={Trophy} message={t('noCertificatesOrAwardsYet')} actionLabel={t('addCertificate')} onAction={() => openCertificateModal()} />
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {certificates.map(cert => (
                <Card key={cert.id} className="border-amber-200/50 dark:border-amber-800/30 bg-gradient-to-br from-amber-50/50 to-yellow-50/30 dark:from-amber-950/10 dark:to-yellow-950/10 overflow-hidden">
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <div className="w-8 h-8 rounded-lg bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center flex-shrink-0">
                            <Trophy className="h-4 w-4 text-amber-600" />
                          </div>
                          <h4 className="font-semibold text-sm font-cairo truncate">{cert.title}</h4>
                        </div>
                        {cert.issuing_body && <p className="text-xs text-muted-foreground font-cairo mt-1 flex items-center gap-1"><GraduationCap className="h-3 w-3" />{cert.issuing_body}</p>}
                        {cert.description && <p className="text-xs text-muted-foreground font-cairo mt-1 line-clamp-2">{cert.description}</p>}
                        {cert.date && <p className="text-[11px] text-muted-foreground font-cairo mt-2 flex items-center gap-1"><Calendar className="h-3 w-3" />{cert.date}</p>}
                      </div>
                      <div className="flex flex-col gap-1 flex-shrink-0">
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openCertificateModal(cert)}><Edit className="h-3.5 w-3.5" /></Button>
                        {(user?.role === 'school_admin' || user?.role === 'admin' || user?.role === 'super_admin') && (
                          <Button variant="ghost" size="icon" className="h-7 w-7 text-red-500 hover:text-red-700" onClick={() => handleDeleteCertificate(cert)}><Trash2 className="h-3.5 w-3.5" /></Button>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </TabsContent>
  );
}

export function PlansTab({ hook }) {
  const { t } = useTranslation();
  const {
    isRTL, remedialPlan, enrichmentPlan, loadingRemedial, loadingEnrichment,
    exportingPlan, generatePlan, openExportModal,
    planHistory, loadingPlanHistory,
  } = hook;

  return (
    <TabsContent value="plans" className="mt-6 space-y-4">
      <div className="relative my-2">
        <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-dashed border-brand-purple/20" /></div>
        <div className="relative flex justify-center">
          <span className="bg-background px-3 text-xs text-brand-purple font-cairo font-medium">{t('hakimAiPlans')}</span>
        </div>
      </div>

      <HakimPlanCard type="remedial" plan={remedialPlan} isRTL={isRTL} loading={loadingRemedial}
        onGenerate={() => generatePlan('remedial')} onExport={remedialPlan ? openExportModal : null} />

      <HakimPlanCard type="enrichment" plan={enrichmentPlan} isRTL={isRTL} loading={loadingEnrichment}
        onGenerate={() => generatePlan('enrichment')} onExport={enrichmentPlan ? openExportModal : null} />

      {remedialPlan && enrichmentPlan && (
        <Button variant="outline" className="w-full gap-2 border-brand-navy/20 text-brand-navy hover:bg-brand-navy/5 hover:text-brand-navy focus-visible:text-brand-navy"
          onClick={() => openExportModal('both')} disabled={exportingPlan}>
          {exportingPlan ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
          {t('exportBothPlans')}
        </Button>
      )}

      <Card>
        <CardContent className="p-6 space-y-3">
          <h3 className="font-bold text-base font-cairo flex items-center gap-2">
            <Clock className="h-5 w-5 text-brand-purple" />
            {t('planHistoryLog')}
          </h3>
          {loadingPlanHistory ? (
            <div className="space-y-2">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-14 rounded-xl" />)}</div>
          ) : planHistory.length === 0 ? (
            <EmptyState icon={Clock} message={t('noPlanHistoryYet')} />
          ) : (
            <div className="space-y-2">
              {planHistory.map((entry, i) => {
                const hasRemedial = !!entry.plans?.remedial_plan;
                const hasEnrichment = !!entry.plans?.enrichment_plan;
                return (
                  <div key={entry.id || i} className="flex items-center gap-3 p-3 rounded-xl border hover:bg-muted/20 transition-colors">
                    <div className="w-8 h-8 rounded-lg bg-brand-purple/10 flex items-center justify-center flex-shrink-0">
                      <FileText className="h-4 w-4 text-brand-purple" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        {hasRemedial && <Badge variant="outline" className="text-[10px] border-rose-200 text-rose-600 dark:border-rose-800 dark:text-rose-400">{t('remedial')}</Badge>}
                        {hasEnrichment && <Badge variant="outline" className="text-[10px] border-emerald-200 text-emerald-600 dark:border-emerald-800 dark:text-emerald-400">{t('enrichment')}</Badge>}
                        <Badge variant="outline" className="text-[10px]">{entry.plan_source === 'ai' ? 'AI' : t('fallback')}</Badge>
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1"><Calendar className="h-3 w-3" />{entry.generated_at?.split('T')[0]}</span>
                        {entry.generated_by_name && <span className="flex items-center gap-1"><User className="h-3 w-3" />{entry.generated_by_name}</span>}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </TabsContent>
  );
}

export function LongitudinalTab({ hook }) {
  const { t } = useTranslation();
  const { isRTL, longitudinalData, loadingLongitudinal } = hook;

  return (
    <TabsContent value="longitudinal" className="mt-6 space-y-6">
      {loadingLongitudinal ? (
        <div className="space-y-4">{[...Array(4)].map((_, i) => <Skeleton key={i} className="h-32 rounded-xl" />)}</div>
      ) : !longitudinalData ? (
        <Card><CardContent className="p-6"><EmptyState icon={ScrollText} message={t('noLongitudinalDataAvailable')} /></CardContent></Card>
      ) : (
        <>
          <Card className="border-0 shadow-md dark:bg-gray-900/50">
            <CardContent className="p-6">
              <h3 className="font-bold text-lg font-cairo flex items-center gap-2 mb-6">
                <Layers className="h-5 w-5 text-brand-navy" />
                {t('studentJourneyTimeline')}
              </h3>
              <div className="relative">
                <div className={`absolute ${isRTL ? 'right-4' : 'left-4'} top-0 bottom-0 w-0.5 bg-gradient-to-b from-brand-navy via-brand-turquoise to-brand-purple`} />
                <div className="space-y-6">
                  {(longitudinalData.timeline || []).map((entry, idx) => (
                    <div key={entry.year} className={`relative ${isRTL ? 'pr-12' : 'pl-12'}`}>
                      <div className={`absolute ${isRTL ? 'right-1' : 'left-1'} top-2 w-7 h-7 rounded-full bg-gradient-to-br from-brand-navy to-brand-turquoise flex items-center justify-center text-white text-xs font-bold shadow-lg z-10`}>{idx + 1}</div>
                      <Card className={`border transition-all hover:shadow-md ${idx === (longitudinalData.timeline || []).length - 1 ? 'ring-2 ring-brand-turquoise/40' : ''}`}>
                        <CardContent className="p-4">
                          <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
                            <div className="flex items-center gap-2">
                              <Badge className="bg-brand-navy/10 text-brand-navy border-brand-navy/20 font-bold">{entry.academic_year}</Badge>
                              {entry.grade && <Badge variant="outline" className="font-cairo text-xs">{entry.grade}</Badge>}
                              {entry.class_name && <span className="text-xs text-muted-foreground font-cairo">{entry.class_name}</span>}
                            </div>
                            {idx === (longitudinalData.timeline || []).length - 1 && (
                              <Badge className="bg-brand-turquoise/10 text-brand-turquoise border-brand-turquoise/20 text-xs">{t('current2')}</Badge>
                            )}
                          </div>
                          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                            <div className="text-center p-2 rounded-lg bg-blue-50 dark:bg-blue-950/20">
                              <div className="text-lg font-bold text-blue-600">{entry.attendance_rate}%</div>
                              <div className="text-[10px] text-muted-foreground font-cairo">{t('attendance2')}</div>
                            </div>
                            <div className="text-center p-2 rounded-lg bg-purple-50 dark:bg-purple-950/20">
                              <div className="text-lg font-bold text-purple-600">{entry.academic_average}%</div>
                              <div className="text-[10px] text-muted-foreground font-cairo">{t('average')}</div>
                            </div>
                            <div className="text-center p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/20">
                              <div className="text-lg font-bold text-emerald-600">{entry.behaviour_positive}</div>
                              <div className="text-[10px] text-muted-foreground font-cairo">{t('positive2')}</div>
                            </div>
                            <div className="text-center p-2 rounded-lg bg-rose-50 dark:bg-rose-950/20">
                              <div className="text-lg font-bold text-rose-600">{entry.behaviour_negative}</div>
                              <div className="text-[10px] text-muted-foreground font-cairo">{t('negative2')}</div>
                            </div>
                          </div>
                          {entry.top_talents?.length > 0 && (
                            <div className="mt-3 flex items-center gap-1.5 flex-wrap">
                              <Sparkles className="h-3.5 w-3.5 text-amber-500" />
                              {entry.top_talents.map((t, ti) => {
                                const opt = TALENT_OPTIONS.find(o => o.value === t);
                                return <Badge key={ti} variant="outline" className={`text-[10px] px-1.5 py-0 ${opt?.color || ''}`}>{isRTL ? (opt?.ar || t) : (opt?.en || t)}</Badge>;
                              })}
                            </div>
                          )}
                          {entry.achievements?.length > 0 && (
                            <div className="mt-2 flex items-center gap-1.5 flex-wrap">
                              <Trophy className="h-3.5 w-3.5 text-amber-500" />
                              {entry.achievements.slice(0, 3).map((a, ai) => (
                                <span key={ai} className="text-[11px] text-muted-foreground font-cairo bg-amber-50 dark:bg-amber-950/20 px-2 py-0.5 rounded-full">{a}</span>
                              ))}
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          {longitudinalData.skill_growth?.length > 0 && (
            <Card className="border-0 shadow-md dark:bg-gray-900/50">
              <CardContent className="p-6">
                <h3 className="font-bold text-lg font-cairo flex items-center gap-2 mb-4">
                  <TrendingUp className="h-5 w-5 text-brand-turquoise" />
                  {t('skillGrowthTracker')}
                </h3>
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={(() => {
                      const allYears = new Set();
                      longitudinalData.skill_growth.forEach(s => s.data.forEach(d => allYears.add(d.year)));
                      const years = [...allYears].sort();
                      return years.map(year => {
                        const point = { year };
                        longitudinalData.skill_growth.forEach(s => {
                          const found = s.data.find(d => d.year === year);
                          point[s.skill] = found ? found.level : null;
                        });
                        return point;
                      });
                    })()}>
                      <CartesianGrid strokeDasharray="3 3" className="opacity-30" />
                      <XAxis dataKey="year" />
                      <YAxis domain={[0, 5]} />
                      <RechartsTooltip />
                      <Legend />
                      {longitudinalData.skill_growth.map((s, i) => {
                        const colors = ['#1C3D74', '#46C1BE', '#615090', '#E14D2A', '#10B981', '#F59E0B', '#EC4899'];
                        return <Line key={s.skill} type="monotone" dataKey={s.skill} stroke={colors[i % colors.length]} strokeWidth={2} dot={{ r: 4 }} connectNulls />;
                      })}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          )}

          <Card className="border-0 shadow-md dark:bg-gray-900/50">
            <CardContent className="p-6">
              <h3 className="font-bold text-lg font-cairo flex items-center gap-2 mb-2">
                <Target className="h-5 w-5 text-brand-purple" />
                {t('readinessIndicators')}
              </h3>
              <p className="text-xs text-muted-foreground font-cairo mb-5 bg-amber-50 dark:bg-amber-950/20 p-2 rounded-lg border border-amber-200 dark:border-amber-800">
                {t('theseIndicatorsAreBasedOnCumulativeDataAndWillBeAi')}
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {[
                  { key: 'academic', icon: GraduationCap, label_ar: 'الاستعداد الأكاديمي', label_en: 'Academic Readiness', emoji: '🎓', color: 'blue' },
                  { key: 'social_emotional', icon: Heart, label_ar: 'الاستعداد الاجتماعي-العاطفي', label_en: 'Social-Emotional Readiness', emoji: '🤝', color: 'emerald' },
                  { key: 'leadership', icon: Crown, label_ar: 'إمكانات القيادة', label_en: 'Leadership Potential', emoji: '👑', color: 'amber' },
                  { key: 'career_alignment', icon: Briefcase, label_ar: 'التوافق المهني', label_en: 'Career Alignment', emoji: '💼', color: 'purple' },
                ].map(indicator => {
                  const score = longitudinalData.readiness?.[indicator.key] || 0;
                  const colorMap = { blue: 'bg-blue-500', emerald: 'bg-emerald-500', amber: 'bg-amber-500', purple: 'bg-purple-500' };
                  const bgMap = { blue: 'bg-blue-50 dark:bg-blue-950/20', emerald: 'bg-emerald-50 dark:bg-emerald-950/20', amber: 'bg-amber-50 dark:bg-amber-950/20', purple: 'bg-purple-50 dark:bg-purple-950/20' };
                  return (
                    <div key={indicator.key} className={`p-4 rounded-xl border ${bgMap[indicator.color]}`}>
                      <div className="flex items-center gap-2 mb-3">
                        <span className="text-xl">{indicator.emoji}</span>
                        <span className="font-semibold text-sm font-cairo">{isRTL ? indicator.label_ar : indicator.label_en}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="flex-1"><Progress value={score} className="h-3" /></div>
                        <span className="font-bold text-lg min-w-[3rem] text-end">{score}%</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          <Card className="border-0 shadow-md dark:bg-gray-900/50">
            <CardContent className="p-6">
              <h3 className="font-bold text-lg font-cairo flex items-center gap-2 mb-2">
                <Briefcase className="h-5 w-5 text-brand-navy" />
                {t('careerClusters')}
              </h3>
              <p className="text-xs text-muted-foreground font-cairo mb-5 bg-blue-50 dark:bg-blue-950/20 p-2 rounded-lg border border-blue-200 dark:border-blue-800">
                {t('earlyCareerAffinityIndicatorsDataBuildsOverTime')}
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {(longitudinalData.career_clusters || []).map((cluster, idx) => {
                  const clusterColors = ['from-blue-500 to-cyan-500', 'from-purple-500 to-pink-500', 'from-amber-500 to-orange-500'];
                  const clusterBgs = ['bg-blue-50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-800', 'bg-purple-50 dark:bg-purple-950/20 border-purple-200 dark:border-purple-800', 'bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800'];
                  return (
                    <div key={idx} className={`p-4 rounded-xl border ${clusterBgs[idx % 3]} relative overflow-hidden`}>
                      <div className={`absolute top-0 ${isRTL ? 'right-0' : 'left-0'} w-1 h-full bg-gradient-to-b ${clusterColors[idx % 3]}`} />
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="font-bold text-sm font-cairo">{isRTL ? cluster.name_ar : cluster.name_en}</h4>
                        <Badge className={`bg-gradient-to-r ${clusterColors[idx % 3]} text-white border-0 text-xs`}>{cluster.match}%</Badge>
                      </div>
                      <Progress value={cluster.match} className="h-2 mb-2" />
                      <p className="text-[11px] text-muted-foreground font-cairo leading-relaxed">{isRTL ? cluster.reason_ar : cluster.reason_en}</p>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-brand-navy via-brand-purple to-brand-navy p-6 text-center">
            <div className="absolute inset-0 nassaq-pattern opacity-5" />
            <div className="relative z-10">
              <Sparkles className="h-8 w-8 text-brand-turquoise mx-auto mb-3" />
              <p className="text-white/90 font-cairo text-sm leading-relaxed max-w-2xl mx-auto">
                {t('everyDataPointRecordedTodayIsBuildingThisStudentsF')}
              </p>
            </div>
          </div>
        </>
      )}
    </TabsContent>
  );
}
const PARENT_HEALTH_LABELS = {
  seasonal_allergy: { ar: 'حساسية موسمية', en: 'Seasonal Allergy' },
  nut_allergy: { ar: 'حساسية من المكسرات', en: 'Nut Allergy' },
  dust_allergy: { ar: 'حساسية من الغبار', en: 'Dust Allergy' },
  asthma: { ar: 'ربو', en: 'Asthma' },
  diabetes: { ar: 'سكري', en: 'Diabetes' },
  epilepsy: { ar: 'صرع', en: 'Epilepsy' },
  weak_vision: { ar: 'ضعف بصر', en: 'Weak Vision' },
  weak_hearing: { ar: 'ضعف سمع', en: 'Weak Hearing' },
  food_allergy: { ar: 'حساسية غذائية', en: 'Food Allergy' },
};

const PARENT_BEHAVIOURAL_LABELS = {
  hyperactivity: { ar: 'فرط حركة', en: 'Hyperactivity' },
  motor_anxiety: { ar: 'قلق حركي', en: 'Motor Anxiety' },
  speech_difficulty: { ar: 'صعوبة نطق', en: 'Speech Difficulty' },
  severe_shyness: { ar: 'خجل شديد', en: 'Severe Shyness' },
  aggression: { ar: 'عدوانية', en: 'Aggression' },
  stuttering: { ar: 'تأتأة', en: 'Stuttering' },
  anger: { ar: 'غضب', en: 'Anger' },
  sleep_disorder: { ar: 'اضطراب نوم', en: 'Sleep Disorder' },
  eating_difficulty: { ar: 'صعوبة أكل', en: 'Eating Difficulty' },
};

const PARENT_FAMILY_PRIMARY_LABELS = {
  both_parents: { ar: 'مع الوالدين', en: 'Both Parents' },
  mother_only: { ar: 'الأم فقط', en: 'Mother Only' },
  father_only: { ar: 'الأب فقط', en: 'Father Only' },
  other: { ar: 'أخرى', en: 'Other' },
};

const PARENT_FAMILY_OTHER_LABELS = {
  parents_separation: { ar: 'انفصال الوالدين', en: 'Parents Separated' },
  parent_traveling: { ar: 'سفر أحد الوالدين', en: 'Parent Traveling' },
  foster_family: { ar: 'أسرة بديلة', en: 'Foster Family' },
  orphan: { ar: 'يتيم', en: 'Orphan' },
  second_marriage: { ar: 'زواج ثانٍ', en: 'Second Marriage' },
  family_problems: { ar: 'مشاكل أسرية', en: 'Family Problems' },
};

function ParentChipGroup({ icon: Icon, iconClass, title, items, chipClass }) {
  if (!items || items.length === 0) return null;
  return (
    <div>
      <h4 className="text-xs font-cairo text-muted-foreground mb-2 flex items-center gap-1.5">
        <Icon className={`h-3.5 w-3.5 ${iconClass}`} />
        {title}
      </h4>
      <div className="flex flex-wrap gap-1.5">
        {items.map((label, idx) => (
          <span key={`${label}-${idx}`} className={`px-2.5 py-1 rounded-full text-[11px] font-cairo border ${chipClass}`}>
            {label}
          </span>
        ))}
      </div>
    </div>
  );
}

function ParentProvidedNotesCard({ student, isRTL }) {
  const ps = student?.profile_settings || {};
  const lang = isRTL ? 'ar' : 'en';

  const resolve = (ids, map) =>
    (Array.isArray(ids) ? ids : [])
      .map((id) => (map[id] ? map[id][lang] : id))
      .filter(Boolean);

  const health = resolve(ps.health_conditions, PARENT_HEALTH_LABELS);
  const behavioural = resolve(ps.behavioral_aspects, PARENT_BEHAVIOURAL_LABELS);

  const familyItems = [];
  if (ps.family_situation && PARENT_FAMILY_PRIMARY_LABELS[ps.family_situation]) {
    familyItems.push(PARENT_FAMILY_PRIMARY_LABELS[ps.family_situation][lang]);
  } else if (ps.family_situation) {
    familyItems.push(ps.family_situation);
  }
  familyItems.push(...resolve(ps.family_other_situations, PARENT_FAMILY_OTHER_LABELS));

  if (health.length === 0 && behavioural.length === 0 && familyItems.length === 0) {
    return null;
  }

  return (
    <Card className="border-brand-purple/20 bg-gradient-to-r from-brand-purple/5 to-brand-turquoise/5 dark:from-brand-purple/10 dark:to-brand-turquoise/10">
      <CardContent className="p-5">
        <div className="flex items-start justify-between mb-4 gap-3">
          <h3 className="font-bold text-sm font-cairo flex items-center gap-2">
            <Heart className="h-4 w-4 text-brand-purple" />
            {isRTL ? 'ملاحظات من ولي الأمر' : 'Notes from Parent'}
          </h3>
          <Badge variant="outline" className="text-[10px] font-cairo border-brand-purple/40 text-brand-purple bg-white/60 dark:bg-transparent">
            {isRTL ? 'مُقدَّمة من ولي الأمر' : 'Provided by parent'}
          </Badge>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <ParentChipGroup
            icon={Heart}
            iconClass="text-rose-500"
            title={isRTL ? 'المشاكل الصحية' : 'Health Conditions'}
            items={health}
            chipClass="bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-900/30 dark:text-rose-300 dark:border-rose-800"
          />
          <ParentChipGroup
            icon={Brain}
            iconClass="text-violet-500"
            title={isRTL ? 'الجوانب السلوكية والتعلم' : 'Behavioural & Learning'}
            items={behavioural}
            chipClass="bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-800"
          />
          <ParentChipGroup
            icon={User}
            iconClass="text-sky-500"
            title={isRTL ? 'الوضع العائلي' : 'Family Situation'}
            items={familyItems}
            chipClass="bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-900/30 dark:text-sky-300 dark:border-sky-800"
          />
        </div>
      </CardContent>
    </Card>
  );
}
