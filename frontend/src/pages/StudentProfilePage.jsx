import { Sidebar } from '../components/layout/Sidebar';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '../components/ui/tabs';
import { LoadingState } from '../components/ui/LoadingState';
import { ScrollArea, ScrollBar } from '../components/ui/scroll-area';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger
} from '../components/ui/dropdown-menu';
import {
  User, Edit, Star, Download, Sun, Moon, Globe, GraduationCap,
  ChevronRight, ChevronLeft, Key, UserX, UserCheck, Trash2, Send,
  Calendar, CheckCircle, Sparkles, ThumbsUp, Trophy,
  MoreVertical, Eye, BarChart3, Heart, Medal, ClipboardList, ScrollText,
  RefreshCw, AlertTriangle
} from 'lucide-react';
import { StatCard } from '../components/student-profile/ProfileComponents';
import { OverviewTab, AcademicTab, TalentsTab, BehaviourTab, ActivitiesTab, PlansTab, LongitudinalTab } from '../components/student-profile/StudentTabsContent';
import { EditProfileModal, HealthModal, BehaviourModal, ExportPlanModal, ActivityModal, CertificateModal, FullProfileExportModal } from '../components/student-profile/StudentModals';
import { useStudentProfile } from '../hooks/useStudentProfile';
import { useCanViewInternalIds } from '../hooks/useCanViewInternalIds';

import { useTranslation } from '../contexts/ThemeContext';
const TABS = [
  { value: 'overview', label_ar: 'نظرة عامة', label_en: 'Overview', icon: Eye },
  { value: 'academic', label_ar: 'الأداء الأكاديمي', label_en: 'Academic', icon: BarChart3 },
  { value: 'talents', label_ar: 'المواهب والمهارات', label_en: 'Talents & Skills', icon: Sparkles },
  { value: 'behaviour', label_ar: 'السلوك والشخصية', label_en: 'Behavior', icon: Heart },
  { value: 'activities', label_ar: 'الأنشطة والإنجازات', label_en: 'Activities', icon: Medal },
  { value: 'plans', label_ar: 'الخطط', label_en: 'Plans', icon: ClipboardList },
  { value: 'longitudinal', label_ar: 'السجل التراكمي', label_en: 'Record', icon: ScrollText },
];

export default function StudentProfilePage() {
  const { t } = useTranslation();
  const canViewInternalIds = useCanViewInternalIds();
  const hook = useStudentProfile();
  const {
    isRTL, isDark, toggleTheme, toggleLanguage, navigate,
    student, loading, error, fetchStudent, rolePrefix, isTeacher,
    activeTab, setActiveTab,
    resolvedClassName, resolvedClassId,
    attendanceRate, loadingAttendance, homeworkRate, loadingHomework,
    positiveBehaviourCount, loadingBehaviour,
    activities, certificates, loadingActivities,
    remedialPlan, enrichmentPlan,
    setFormData, setEditProfileOpen, setProfileExportModalOpen,
    openExportModal, handleAction, handleBack,
  } = hook;

  // FIX (D9): The previous code used ChevronRight in both branches, breaking
  // the visual back-arrow direction in LTR. Use the proper mirrored icon.
  const BackArrow = isRTL ? ChevronRight : ChevronLeft;

  if (loading) {
    return (
      <div className="flex min-h-screen bg-background">
        <Sidebar />
        <main className="flex-1 overflow-auto">
          <LoadingState variant="fullpage" />
        </main>
      </div>
    );
  }

  if (error || !student) {
    return (
      <div className="flex min-h-screen bg-background">
        <Sidebar />
        <div className="flex-1 flex items-center justify-center p-4">
          <Card className="p-8 text-center max-w-md w-full space-y-5">
            <div className="w-14 h-14 rounded-2xl bg-red-100 dark:bg-red-900/30 flex items-center justify-center mx-auto">
              <AlertTriangle className="h-7 w-7 text-red-600" strokeWidth={1.5} aria-hidden="true" />
            </div>
            <p className="text-base font-semibold text-foreground">
              {error ? t('errorLoadingStudentData') : t('studentNotFound')}
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <Button onClick={() => fetchStudent()} className="w-full sm:w-auto">
                <RefreshCw className="h-4 w-4 me-2" strokeWidth={1.5} aria-hidden="true" />
                {t('retry')}
              </Button>
              <Button variant="outline" onClick={handleBack} className="w-full sm:w-auto">
                <BackArrow className="h-4 w-4 me-2" /> {t('goBack')}
              </Button>
            </div>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <header className="sticky top-0 z-30 backdrop-blur-xl bg-background/80 border-b px-4 md:px-6 py-3">
          <div className="flex items-center justify-between max-w-6xl mx-auto">
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" className="h-9 w-9" onClick={handleBack}>
                <BackArrow className="h-5 w-5" />
              </Button>
              <nav className="flex items-center gap-1 text-xs text-muted-foreground">
                <button onClick={() => navigate(`${rolePrefix}/users-management?filter=students`)} className="hover:text-foreground transition-colors font-cairo">
                  {t('userManagement')}
                </button>
                {resolvedClassName && (
                  <>
                    <ChevronRight className="h-3 w-3" />
                    <button onClick={() => resolvedClassId && navigate(`${rolePrefix}/classes/${resolvedClassId}`)} className="hover:text-foreground transition-colors font-cairo">
                      {resolvedClassName}
                    </button>
                  </>
                )}
                <ChevronRight className="h-3 w-3" />
                <span className="text-foreground font-medium font-cairo">{student.full_name}</span>
              </nav>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={toggleTheme}>
                {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </Button>
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={toggleLanguage}>
                <Globe className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </header>

        <div className="max-w-6xl mx-auto">
          <div className="relative overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-br from-brand-navy via-brand-navy/95 to-brand-purple opacity-95" />
            <div className="absolute inset-0 opacity-5" style={{ backgroundImage: 'url(/nassaq-pattern.png)', backgroundSize: '200px' }} />
            <div className="relative px-4 md:px-8 py-6 md:py-8">
              <div className="flex flex-col md:flex-row items-start gap-5">
                <div className="relative flex-shrink-0">
                  <div className={`w-24 h-24 md:w-28 md:h-28 rounded-full bg-gradient-to-br from-brand-turquoise to-brand-purple/80 flex items-center justify-center shadow-xl border-4 border-white/20 ${student.is_gifted ? 'ring-4 ring-amber-400/60 ring-offset-2 ring-offset-brand-navy' : ''}`}>
                    <span className="text-white font-bold text-4xl md:text-5xl font-cairo">{student.full_name?.charAt(0)}</span>
                  </div>
                  {student.is_gifted && (
                    <div className="absolute -top-1 -end-1 w-8 h-8 rounded-full bg-gradient-to-br from-yellow-400 to-amber-500 flex items-center justify-center shadow-lg border-2 border-white/30">
                      <Star className="h-4 w-4 text-white fill-white" />
                    </div>
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex flex-col sm:flex-row sm:items-start gap-3 mb-2">
                    <div className="flex-1 min-w-0">
                      <h1 className="text-2xl md:text-3xl font-bold text-white font-cairo leading-tight">{student.full_name}</h1>
                      <p className="text-white/70 text-sm mt-1 font-cairo flex items-center gap-2 flex-wrap">
                        <GraduationCap className="h-4 w-4" />
                        {student.grade || '-'} {resolvedClassName ? `— ${resolvedClassName}` : student.section ? `— ${student.section}` : ''}
                      </p>
                      <p className="text-white/50 text-xs mt-1 font-mono tracking-wider">
                        {student.student_number || student.national_id || (canViewInternalIds ? `ID: ${student.id?.slice(0, 8)}` : '—')}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 flex-wrap">
                      {student.is_gifted && (
                        <Badge className="bg-gradient-to-r from-yellow-400 to-amber-500 text-white border-0 px-3 py-1.5 font-cairo shadow-lg text-xs">
                          <Star className="h-3.5 w-3.5 fill-white me-1" />
                          {t('gifted')}
                        </Badge>
                      )}
                      <Badge variant={student.is_active !== false ? 'default' : 'destructive'} className={`text-xs px-2.5 py-1 ${student.is_active !== false ? 'bg-emerald-500/20 text-emerald-200 border-emerald-400/30' : ''}`}>
                        {student.is_active !== false ? (t('active')) : (t('suspended'))}
                      </Badge>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 mt-4 flex-wrap">
                    <Button size="sm" variant="secondary" className="gap-1.5 text-xs bg-white/10 hover:bg-white/20 text-white border-white/20 backdrop-blur-sm" onClick={() => { setFormData({ ...student }); setEditProfileOpen(true); }}>
                      <Edit className="h-3.5 w-3.5" /> {t('editProfile')}
                    </Button>
                    <Button size="sm" variant="secondary" className="gap-1.5 text-xs bg-white/10 hover:bg-white/20 text-white border-white/20 backdrop-blur-sm" onClick={() => setProfileExportModalOpen(true)}>
                      <Download className="h-3.5 w-3.5" /> {t('exportFullProfile')}
                    </Button>
                    {(remedialPlan || enrichmentPlan) && (
                      <Button size="sm" variant="secondary" className="gap-1.5 text-xs bg-white/10 hover:bg-white/20 text-white border-white/20 backdrop-blur-sm" onClick={() => openExportModal('both')}>
                        <Download className="h-3.5 w-3.5" /> {t('exportPlan')}
                      </Button>
                    )}
                    {student.parent_phone && (
                      <Button size="sm" variant="secondary" className="gap-1.5 text-xs bg-white/10 hover:bg-white/20 text-white border-white/20 backdrop-blur-sm" onClick={() => window.open(`https://wa.me/${student.parent_phone.replace(/\D/g, '')}`, '_blank')}>
                        <Send className="h-3.5 w-3.5" /> {t('messageParent')}
                      </Button>
                    )}
                    {!isTeacher && (
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button size="sm" variant="secondary" className="gap-1 text-xs bg-white/10 hover:bg-white/20 text-white border-white/20 backdrop-blur-sm px-2">
                            <MoreVertical className="h-3.5 w-3.5" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align={isRTL ? 'start' : 'end'} className="w-52">
                          <DropdownMenuItem onClick={() => handleAction('reset-password')} className="gap-2 font-cairo text-sm">
                            <Key className="h-4 w-4 text-blue-500" /> {t('resetPassword')}
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => handleAction(student.is_active !== false ? 'suspend' : 'activate')} className="gap-2 font-cairo text-sm">
                            {student.is_active !== false
                              ? <><UserX className="h-4 w-4 text-amber-500" /> {isRTL ? 'تعليق الحساب' : 'Suspend'}</>
                              : <><UserCheck className="h-4 w-4 text-green-500" /> {isRTL ? 'تفعيل الحساب' : 'Activate'}</>
                            }
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem onClick={() => handleAction('delete')} className="gap-2 font-cairo text-sm text-red-600 focus:text-red-600">
                            <Trash2 className="h-4 w-4" /> {t('deleteAccount')}
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-5 gap-2 md:gap-3 mt-6">
                <StatCard icon={Calendar} value={attendanceRate != null ? `${attendanceRate}%` : null} label={isRTL ? 'نسبة الحضور' : 'Attendance'} color="text-emerald-300" bg="bg-white/10 backdrop-blur-sm" loading={loadingAttendance} />
                <StatCard icon={CheckCircle} value={homeworkRate ? `${homeworkRate.rate}%` : null} label={t('performance2')} color="text-blue-300" bg="bg-white/10 backdrop-blur-sm" loading={loadingHomework} />
                <StatCard icon={Sparkles} value={student.talents?.length || 0} label={t('talents')} color="text-purple-300" bg="bg-white/10 backdrop-blur-sm" loading={false} />
                <StatCard icon={Trophy} value={(activities?.length || 0) + (certificates?.length || 0)} label={t('activities')} color="text-amber-300" bg="bg-white/10 backdrop-blur-sm" loading={loadingActivities} />
                <StatCard icon={ThumbsUp} value={positiveBehaviourCount} label={t('positive2')} color="text-green-300" bg="bg-white/10 backdrop-blur-sm" loading={loadingBehaviour} />
              </div>
            </div>
          </div>

          <div className="px-4 md:px-8 pb-8">
            <Tabs value={activeTab} onValueChange={setActiveTab} className="mt-0">
              <div className="sticky top-[57px] z-20 bg-background pt-3 pb-1 -mx-4 md:-mx-8 px-4 md:px-8 border-b">
                <ScrollArea className="w-full" dir={isRTL ? 'rtl' : 'ltr'}>
                  <TabsList className="inline-flex h-10 bg-transparent p-0 gap-0 w-full justify-start">
                    {TABS.map(tab => (
                      <TabsTrigger key={tab.value} value={tab.value}
                        className="relative px-4 py-2.5 text-xs font-cairo gap-1.5 rounded-none border-b-2 border-transparent data-[state=active]:border-brand-turquoise data-[state=active]:text-brand-turquoise data-[state=active]:shadow-none bg-transparent whitespace-nowrap">
                        <tab.icon className="h-3.5 w-3.5" />
                        {isRTL ? tab.label_ar : tab.label_en}
                      </TabsTrigger>
                    ))}
                  </TabsList>
                  <ScrollBar orientation="horizontal" />
                </ScrollArea>
              </div>

              <OverviewTab hook={hook} />
              <AcademicTab hook={hook} />
              <TalentsTab hook={hook} />
              <BehaviourTab hook={hook} />
              <ActivitiesTab hook={hook} />
              <PlansTab hook={hook} />
              <LongitudinalTab hook={hook} />
            </Tabs>
          </div>
        </div>
      </main>

      <EditProfileModal hook={hook} />
      <HealthModal hook={hook} />
      <BehaviourModal hook={hook} />
      <ExportPlanModal hook={hook} />
      <ActivityModal hook={hook} />
      <CertificateModal hook={hook} />
      <FullProfileExportModal hook={hook} />
    </div>
  );
}
