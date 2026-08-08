import { useState, useEffect, lazy, Suspense } from 'react';
import { useAuth } from '@/shared/contexts/AuthContext';
import { useTheme , useTranslation } from '@/shared/contexts/ThemeContext';
import { Sidebar } from '@/shared/components/layout/Sidebar';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Badge } from '@/shared/components/ui/badge';
import { toast } from 'sonner';
import { useNassaqAlert } from '@/shared/components/ui/NassaqAlertDialog';
import {
  FolderOpen,
  Plus,
  Search,
  MoreHorizontal,
  Sun,
  Moon,
  Globe,
  Trash2,
  Edit,
  Users,
  Loader2,
  ArrowLeft,
  UserCheck,
  RotateCcw,
  ChevronDown,
  ChevronUp,
  Undo2,
} from 'lucide-react';
import { CANONICAL_GRADES } from '@/shared/models/utils/stageGrade';
import { Switch } from '@/shared/components/ui/switch';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/shared/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/shared/components/ui/table';
import { Link } from 'react-router-dom';
import { getApiErrorMessage } from '@/shared/models/utils/apiError';

const RelinkAssignmentsWizard = lazy(() => import('@/features/academics/components/classes/RelinkAssignmentsWizard').then(m => ({ default: m.RelinkAssignmentsWizard })));

export const ClassesPage = () => {
  const { t } = useTranslation();
  const { user, api } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  const [classes, setClasses] = useState([]);
  const [schools, setSchools] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSchool, setSelectedSchool] = useState('all');
  const [submitting, setSubmitting] = useState(false);
  const [showInactive, setShowInactive] = useState(false);
  const [deletedExpanded, setDeletedExpanded] = useState(false);
  const [restoringId, setRestoringId] = useState(null);
  const [relinkClassId, setRelinkClassId] = useState(null);
  const [relinkOpen, setRelinkOpen] = useState(false);

  // Check if user is a school-level user (not platform admin)
  const { nassaqError, nassaqWarning, nassaqConfirm, nassaqSuccess, showAlert } = useNassaqAlert();
  const isSchoolLevel = user?.role && !user.role.startsWith('platform_');
  const userSchoolId = user?.tenant_id;
  
  // Single source of truth for the 12 canonical grade labels (stage-ordered).
  const gradeLevels = CANONICAL_GRADES.map((g) => g.label_ar);
  
  const sections = ['أ', 'ب', 'ج', 'د', 'هـ'];
  
  const [newClass, setNewClass] = useState({
    name: '',
    name_en: '',
    school_id: userSchoolId || '',
    grade_level: '',
    section: '',
    capacity: 30,
    homeroom_teacher_id: '',
  });

  const fetchData = async (opts = {}) => {
    const includeInactive = opts.includeInactive ?? showInactive;
    try {
      // For school-level users, only fetch classes and teachers (tenant-scoped by backend)
      // For platform admins, also fetch schools for filtering
      // Task #631 — always request include_deleted=true so the
      // "Recently deleted" section is populated regardless of the
      // showInactive toggle. The backend silently ignores the flag for
      // non-admin callers.
      const classParams = { include_deleted: true };
      if (includeInactive) classParams.include_inactive = true;
      const [classesRes, teachersRes] = await Promise.all([
        api.get('/classes', { params: classParams }),
        api.get('/teachers'),
      ]);
      setClasses(classesRes.data);
      setTeachers(teachersRes.data);
      
      // Platform admins get the full schools list; school-level users get only their own school
      if (!isSchoolLevel) {
        try {
          const schoolsRes = await api.get('/schools');
          setSchools(schoolsRes.data);
        } catch (e) {
          console.error('Error fetching schools list:', e);
          setSchools([]);
        }
      } else if (userSchoolId) {
        try {
          const schoolRes = await api.get(`/schools/${userSchoolId}`);
          setSchools([schoolRes.data]);
        } catch (e) {
          console.error('Error fetching own school:', e);
          setSchools([]);
        }
      }
    } catch (error) {
      console.error('Failed to fetch data:', error);
      nassaqError(t('failedToLoadData'));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (!user) return;
    fetchData({ includeInactive: showInactive });
    // Set default school_id for new class form
    if (userSchoolId) {
      setNewClass(prev => ({ ...prev, school_id: userSchoolId }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, showInactive]);

  // Auto-generate class name
  useEffect(() => {
    if (newClass.grade_level && newClass.section) {
      const name = `${newClass.grade_level} - ${newClass.section}`;
      setNewClass(prev => ({ ...prev, name }));
    }
  }, [newClass.grade_level, newClass.section]);

  const handleCreateClass = async () => {
    // Use user's school_id for school-level users
    const schoolId = isSchoolLevel ? userSchoolId : newClass.school_id;
    
    if (!newClass.name || !schoolId || !newClass.grade_level) {
      nassaqError(t('pleaseFillAllRequiredFields'));
      return;
    }

    setSubmitting(true);
    try {
      await api.post('/classes', { ...newClass, school_id: schoolId });
      toast.success(t('classAddedSuccessfully'));
      setCreateDialogOpen(false);
      setNewClass({
        name: '',
        name_en: '',
        school_id: userSchoolId || '',
        grade_level: '',
        section: '',
        capacity: 30,
        homeroom_teacher_id: '',
      });
      await fetchData({ includeInactive: showInactive });
    } catch (error) {
      nassaqError(getApiErrorMessage(error) || (t('failedToAddClass')));
    } finally {
      setSubmitting(false);
    }
  };

  const handleReactivateClass = async (classId) => {
    try {
      let inactiveDependents = null;
      try {
        const res = await api.post(`/classes/${classId}/restore`);
        inactiveDependents = res.data?.inactive_dependents || null;
      } catch (restoreErr) {
        // Fallback to the legacy reactivate path when /restore isn't applicable:
        //  - 404: the class was merely deactivated (no deleted_at), so it isn't
        //    restorable through /restore.
        //  - 403: the caller's role (e.g. school_sub_admin) is allowed to
        //    reactivate via PUT but not to call /restore.
        const status = restoreErr.response?.status;
        if (status === 404 || status === 403) {
          await api.put(`/classes/${classId}`, { is_active: true });
        } else {
          throw restoreErr;
        }
      }
      toast.success(t('classReactivated'));
      await fetchData({ includeInactive: showInactive });
      const hasDependents =
        inactiveDependents &&
        Object.values(inactiveDependents).some((v) => Number(v) > 0);
      if (hasDependents) {
        setRelinkClassId(classId);
        setRelinkOpen(true);
      }
    } catch (error) {
      nassaqError(getApiErrorMessage(error) || (t('operationFailed')));
    }
  };

  // Task #637 — dependency-aware delete with optional force fallback.
  const performDeleteClass = async (classId, { force = false } = {}) => {
    try {
      const res = await api.delete(`/classes/${classId}`, force ? { params: { force: true } } : undefined);
      const data = res?.data;

      if (data && data.requires_confirmation) {
        const deps = data.dependencies || {};
        const teacherAssignments = deps.teacher_assignments || 0;
        const classSubjects = deps.class_subjects || 0;
        const timetableSessions = deps.timetable_sessions || 0;
        const lines = [
          data.message || 'هذا الفصل مرتبط بسجلات أخرى.',
          teacherAssignments > 0 ? `• ${t('teacherAssignments') || 'إسنادات المعلمين'}: ${teacherAssignments}` : null,
          classSubjects > 0 ? `• ${t('classSubjects') || 'المواد الدراسية'}: ${classSubjects}` : null,
          timetableSessions > 0 ? `• ${t('scheduleSessions') || 'الحصص في الجدول'}: ${timetableSessions}` : null,
        ].filter(Boolean);
        nassaqConfirm(lines.join('\n'), async () => {
          await performDeleteClass(classId, { force: true });
        }, {
          title: t('dependenciesFound') || 'توجد ارتباطات',
          confirmText: t('forceDelete') || 'حذف إجباري',
          cancelText: t('cancel') || 'إلغاء',
        });
        return;
      }

      const deactivated = data?.deactivated;
      let msg = t('classDeletedSuccessfully');
      if (deactivated) {
        const parts = Object.entries(deactivated).filter(([_, v]) => v > 0).map(([k, v]) => `${k}: ${v}`);
        if (parts.length > 0) msg += ` (${parts.join(', ')})`;
      }
      toast.success(msg);
      await fetchData({ includeInactive: showInactive });
    } catch (error) {
      const status = error?.response?.status;
      const detail = getApiErrorMessage(error);
      if (status === 409) {
        nassaqError(
          typeof detail === 'string'
            ? detail
            : 'لا يمكن حذف الفصل بسبب وجود بيانات مرتبطة به. يرجى نقل الطلاب أولاً.',
          { title: t('cannotDelete') || 'تعذّر الحذف' }
        );
      } else {
        nassaqError(
          typeof detail === 'string'
            ? detail
            : 'حدث خطأ أثناء الحذف. يرجى المحاولة مرة أخرى.',
          { title: t('error') || 'خطأ' }
        );
      }
    }
  };

  // Task #631 — restore a soft-deleted class. The backend keeps the
  // class's dependent rows (teacher_assignments, class_subjects,
  // timetable_sessions, class_sessions, curriculum_lessons,
  // teacher_class_assignments) inactive on purpose so the principal can
  // re-link them deliberately. We surface those counts in a
  // NassaqAlertDialog so they know what still needs attention.
  const handleRestoreClass = async (cls) => {
    const className = cls?.name || '';
    nassaqConfirm(
      isRTL
        ? `هل تريد استعادة الفصل "${className}"؟ سيظهر الفصل مرة أخرى في القائمة، لكنك ستحتاج إلى إعادة ربط المعلمين والمواد والجدول يدويًا.`
        : `Restore class "${className}"? It will reappear in the list, but you'll need to re-link its teachers, subjects, and schedule manually.`,
      async () => {
        setRestoringId(cls.id);
        try {
          const res = await api.post(`/classes/${cls.id}/restore`);
          const dependents = res?.data?.inactive_dependents || {};
          const labelMap = {
            teacher_assignments: isRTL ? 'إسنادات المعلمين' : 'Teacher assignments',
            teacher_class_assignments: isRTL ? 'إسنادات معلم-فصل' : 'Teacher–class links',
            class_subjects: isRTL ? 'المواد الدراسية' : 'Class subjects',
            timetable_sessions: isRTL ? 'حصص الجدول' : 'Timetable sessions',
            class_sessions: isRTL ? 'حصص الفصل' : 'Class sessions',
            curriculum_lessons: isRTL ? 'دروس المنهج' : 'Curriculum lessons',
          };
          const lines = Object.entries(dependents)
            .filter(([, v]) => Number(v) > 0)
            .map(([k, v]) => `• ${labelMap[k] || k}: ${v}`);
          const header = isRTL
            ? `تمت استعادة الفصل "${className}" بنجاح.`
            : `Class "${className}" was restored successfully.`;
          const followUp = lines.length
            ? (isRTL
                ? `\n\nهذه العناصر المرتبطة لا تزال غير مُفعَّلة وتحتاج إلى إعادة ربط:\n${lines.join('\n')}`
                : `\n\nThe following linked items are still inactive and need to be re-linked:\n${lines.join('\n')}`)
            : (isRTL
                ? '\n\nلا توجد عناصر مرتبطة بحاجة إلى إعادة ربط.'
                : '\n\nNo linked items need re-linking.');
          // Task #644 — when at least one dependent count > 0, offer a
          // one-click "Reactivate linked items" companion action that
          // calls POST /classes/{id}/reactivate-dependents and reports
          // the per-table counts in a follow-up dialog.
          const hasDependents = lines.length > 0;
          showAlert({
            type: hasDependents ? 'warning' : 'success',
            title: isRTL ? 'تمت استعادة الفصل' : 'Class restored',
            message: header + followUp,
            confirmText: isRTL ? 'حسناً' : 'OK',
            secondaryActionText: hasDependents
              ? (isRTL ? 'إعادة تفعيل العناصر المرتبطة' : 'Reactivate linked items')
              : undefined,
            onSecondaryAction: hasDependents
              ? () => handleReactivateDependents(cls)
              : undefined,
          });
          await fetchData({ includeInactive: showInactive });
        } catch (error) {
          nassaqError(
            getApiErrorMessage(error)
              || (isRTL ? 'فشل استعادة الفصل' : 'Failed to restore class')
          );
        } finally {
          setRestoringId(null);
        }
      },
      {
        title: isRTL ? 'تأكيد الاستعادة' : 'Confirm restore',
        confirmText: isRTL ? 'نعم، استعادة' : 'Yes, restore',
        cancelText: isRTL ? 'إلغاء' : 'Cancel',
      }
    );
  };

  // Task #644 — companion to handleRestoreClass. Calls
  // POST /classes/{id}/reactivate-dependents which flips
  // teacher_assignments, teacher_class_assignments, class_subjects,
  // timetable_sessions, class_sessions, and curriculum_lessons rows for
  // this class back to is_active=True in one shot, then reports the
  // per-table counts in a follow-up dialog.
  const handleReactivateDependents = async (cls) => {
    const className = cls?.name || '';
    setRestoringId(cls.id);
    try {
      const res = await api.post(`/classes/${cls.id}/reactivate-dependents`);
      const reactivated = res?.data?.reactivated || {};
      const labelMap = {
        teacher_assignments: isRTL ? 'إسنادات المعلمين' : 'Teacher assignments',
        teacher_class_assignments: isRTL ? 'إسنادات معلم-فصل' : 'Teacher–class links',
        class_subjects: isRTL ? 'المواد الدراسية' : 'Class subjects',
        timetable_sessions: isRTL ? 'حصص الجدول' : 'Timetable sessions',
        class_sessions: isRTL ? 'حصص الفصل' : 'Class sessions',
        curriculum_lessons: isRTL ? 'دروس المنهج' : 'Curriculum lessons',
      };
      const lines = Object.entries(reactivated)
        .filter(([, v]) => Number(v) > 0)
        .map(([k, v]) => `• ${labelMap[k] || k}: ${v}`);
      const total = Object.values(reactivated).reduce((a, b) => a + Number(b || 0), 0);
      const header = isRTL
        ? `تمت إعادة تفعيل العناصر المرتبطة بالفصل "${className}".`
        : `Linked items for class "${className}" have been reactivated.`;
      const body = total
        ? (isRTL ? `\n\nتم تفعيل:\n${lines.join('\n')}` : `\n\nReactivated:\n${lines.join('\n')}`)
        : (isRTL ? '\n\nلا توجد عناصر بحاجة إلى إعادة تفعيل.' : '\n\nNo items needed reactivation.');
      showAlert({
        type: 'success',
        title: isRTL ? 'تم إعادة التفعيل' : 'Reactivation complete',
        message: header + body,
        confirmText: isRTL ? 'حسناً' : 'OK',
      });
      await fetchData({ includeInactive: showInactive });
    } catch (error) {
      nassaqError(
        getApiErrorMessage(error)
          || (isRTL ? 'فشل إعادة تفعيل العناصر المرتبطة' : 'Failed to reactivate linked items')
      );
    } finally {
      setRestoringId(null);
    }
  };

  const formatDeletedAt = (iso) => {
    if (!iso) return '-';
    try {
      const d = new Date(iso);
      return d.toLocaleString(isRTL ? 'ar' : 'en', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return iso;
    }
  };

  const handleDeleteClass = async (classId) => {
    nassaqConfirm(
      t('areYouSureYouWantToDeleteThisClassAllRelatedDataWi'),
      async () => {
        await performDeleteClass(classId);
      },
      { title: t('confirmPermanentDelete'), confirmText: t('yesDeletePermanently'), cancelText: t('cancel') }
    );
  };

  // Task #631 — soft-deleted classes (is_active=false AND deleted_at!=null)
  // live in their own "Recently deleted" section, not the main table.
  const isDeleted = (cls) => cls.is_active === false && !!cls.deleted_at;

  const filteredClasses = classes.filter(cls => {
    if (isDeleted(cls)) return false;
    if (!showInactive && cls.is_active === false) return false;
    const matchesSearch = cls.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         cls.grade_level.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesSchool = selectedSchool === 'all' || cls.school_id === selectedSchool;
    return matchesSearch && matchesSchool;
  }).sort((a, b) => a.name.localeCompare(b.name, 'ar'));

  const deletedClasses = classes
    .filter(cls => isDeleted(cls))
    .filter(cls => selectedSchool === 'all' || cls.school_id === selectedSchool)
    .sort((a, b) => {
      const ad = a.deleted_at || '';
      const bd = b.deleted_at || '';
      return bd.localeCompare(ad);
    });

  const activeCount = filteredClasses.length;

  const getSchoolName = (schoolId) => {
    const school = schools.find(s => s.id === schoolId);
    return school?.name || '-';
  };

  const filteredTeachers = teachers.filter(t => t.school_id === newClass.school_id);

  return (
    <Sidebar>
      <div className="min-h-screen bg-background" data-testid="classes-page">
        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="icon" asChild className="rounded-xl">
                <Link to="/admin">
                  <ArrowLeft className="h-5 w-5" />
                </Link>
              </Button>
              <div>
                <h1 className="font-cairo text-2xl font-bold text-foreground">
                  {t('classesManagement')}
                </h1>
                <p className="text-sm text-muted-foreground font-tajawal">
                  {isRTL ? `${activeCount} فصل` : `${activeCount} classes`}
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" onClick={toggleLanguage} className="rounded-xl">
                <Globe className="h-5 w-5" />
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme} className="rounded-xl">
                {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </Button>
            </div>
          </div>
        </header>

        <div className="p-6 space-y-6">
          <div className="flex flex-col md:flex-row gap-4 justify-between">
            <div className="flex flex-1 gap-4">
              <div className="relative flex-1 max-w-sm">
                <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                <Input
                  placeholder={t('searchClasses')}
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="ps-10 rounded-xl"
                  data-testid="search-classes-input"
                />
              </div>
              
              <div className="flex items-center gap-2 px-3 rounded-xl border border-border bg-background">
                <Switch
                  id="show-inactive-classes"
                  checked={showInactive}
                  onCheckedChange={setShowInactive}
                  data-testid="toggle-show-inactive-classes"
                />
                <Label htmlFor="show-inactive-classes" className="text-sm font-tajawal cursor-pointer whitespace-nowrap">
                  {t('showInactiveClasses')}
                </Label>
              </div>

              {/* Only show school filter for platform admins */}
              {!isSchoolLevel && schools.length > 0 && (
                <Select value={selectedSchool} onValueChange={setSelectedSchool}>
                  <SelectTrigger className="w-[200px] rounded-xl">
                    <SelectValue placeholder={t('school')} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t('allSchools')}</SelectItem>
                    {schools.map(school => (
                      <SelectItem key={school.id} value={school.id}>{school.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>

            <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
              <DialogTrigger asChild>
                <Button className="bg-brand-turquoise hover:bg-brand-turquoise-light rounded-xl" data-testid="add-class-btn">
                  <Plus className="h-5 w-5 me-2" />
                  {t('addClass')}
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                  <DialogTitle className="font-cairo">
                    {t('addNewClass')}
                  </DialogTitle>
                  <DialogDescription>
                    {t('enterTheNewClassDetails')}
                  </DialogDescription>
                </DialogHeader>
                
                <div className="grid gap-4 py-4">
                  <div className="space-y-2">
                    <Label>{t('school2')}</Label>
                    <Select 
                      value={newClass.school_id} 
                      onValueChange={(value) => setNewClass({ ...newClass, school_id: value, homeroom_teacher_id: '' })}
                      disabled={isSchoolLevel}
                    >
                      <SelectTrigger
                        className="rounded-xl disabled:opacity-100 disabled:cursor-default"
                        data-testid="class-school-select"
                      >
                        <SelectValue placeholder={t('selectSchool')} />
                      </SelectTrigger>
                      <SelectContent>
                        {schools.map(school => (
                          <SelectItem key={school.id} value={school.id}>{school.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>{t('gradeLevel')}</Label>
                      <Select 
                        value={newClass.grade_level} 
                        onValueChange={(value) => setNewClass({ ...newClass, grade_level: value })}
                      >
                        <SelectTrigger className="rounded-xl" data-testid="class-grade-select">
                          <SelectValue placeholder={t('selectGrade')} />
                        </SelectTrigger>
                        <SelectContent>
                          {gradeLevels.map(level => (
                            <SelectItem key={level} value={level}>{level}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>{t('section')}</Label>
                      <Select 
                        value={newClass.section} 
                        onValueChange={(value) => setNewClass({ ...newClass, section: value })}
                      >
                        <SelectTrigger className="rounded-xl">
                          <SelectValue placeholder={t('selectSection')} />
                        </SelectTrigger>
                        <SelectContent>
                          {sections.map(sec => (
                            <SelectItem key={sec} value={sec}>{sec}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    <Label>{t('className')}</Label>
                    <Input
                      value={newClass.name}
                      onChange={(e) => setNewClass({ ...newClass, name: e.target.value })}
                      className="rounded-xl"
                      placeholder={t('autogenerated')}
                    />
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>{t('capacity2')}</Label>
                      <Input
                        type="number"
                        value={newClass.capacity}
                        onChange={(e) => setNewClass({ ...newClass, capacity: parseInt(e.target.value) || 30 })}
                        className="rounded-xl"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>{t('homeroomTeacher')}</Label>
                      <Select 
                        value={newClass.homeroom_teacher_id} 
                        onValueChange={(value) => setNewClass({ ...newClass, homeroom_teacher_id: value })}
                      >
                        <SelectTrigger className="rounded-xl">
                          <SelectValue placeholder={t('selectTeacher')} />
                        </SelectTrigger>
                        <SelectContent>
                          {filteredTeachers.map(teacher => (
                            <SelectItem key={teacher.id} value={teacher.id}>{teacher.full_name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>
                
                <DialogFooter>
                  <Button variant="outline" onClick={() => setCreateDialogOpen(false)} className="rounded-xl">
                    {t('cancel')}
                  </Button>
                  <Button 
                    onClick={handleCreateClass} 
                    className="bg-brand-navy rounded-xl" 
                    disabled={submitting}
                    data-testid="create-class-btn"
                  >
                    {submitting ? (
                      <><Loader2 className="h-4 w-4 animate-spin me-2" />{t('adding')}</>
                    ) : (
                      t('add')
                    )}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>

          <Card className="card-nassaq">
            <CardContent className="p-0">
              {isLoading ? (
                <div className="flex items-center justify-center py-20">
                  <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
                </div>
              ) : (
                <div className="rounded-xl overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('class')}</TableHead>
                        <TableHead>{t('gradeLabel')}</TableHead>
                        <TableHead>{t('school')}</TableHead>
                        <TableHead>{t('homeroomLabel')}</TableHead>
                        <TableHead>{t('students')}</TableHead>
                        <TableHead>{t('status2')}</TableHead>
                        <TableHead className="w-12"></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredClasses.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={7} className="text-center py-12 text-muted-foreground">
                            <FolderOpen className="h-12 w-12 mx-auto mb-4 opacity-20" />
                            <p>{t('noClassesFound')}</p>
                          </TableCell>
                        </TableRow>
                      ) : (
                        filteredClasses.map((cls) => (
                          <TableRow
                            key={cls.id}
                            data-testid={`class-row-${cls.id}`}
                            className={cls.is_active === false ? 'opacity-60' : ''}
                          >
                            <TableCell>
                              <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-full bg-brand-navy/10 flex items-center justify-center">
                                  <FolderOpen className="h-5 w-5 text-brand-navy" />
                                </div>
                                <div>
                                  <div className="font-medium">{cls.name}</div>
                                  {cls.section && (
                                    <div className="text-sm text-muted-foreground">
                                      {isRTL ? `شعبة ${cls.section}` : `Section ${cls.section}`}
                                    </div>
                                  )}
                                </div>
                              </div>
                            </TableCell>
                            <TableCell>
                              <Badge variant="outline" className="rounded-lg">
                                {cls.grade_level}
                              </Badge>
                            </TableCell>
                            <TableCell>{getSchoolName(cls.school_id)}</TableCell>
                            <TableCell>
                              {cls.homeroom_teacher_name ? (
                                <div className="flex items-center gap-1">
                                  <UserCheck className="h-4 w-4 text-brand-purple" />
                                  {cls.homeroom_teacher_name}
                                </div>
                              ) : '-'}
                            </TableCell>
                            <TableCell>
                              <div className="flex items-center gap-1">
                                <Users className="h-4 w-4 text-brand-turquoise" />
                                {cls.current_students} / {cls.capacity}
                              </div>
                            </TableCell>
                            <TableCell>
                              {cls.deleted_at ? (
                                <Badge
                                  className="bg-red-100 text-red-700"
                                  data-testid={`class-deleted-badge-${cls.id}`}
                                >
                                  {isRTL ? 'محذوف' : 'Deleted'}
                                </Badge>
                              ) : (
                                <Badge className={cls.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}>
                                  {cls.is_active ? (t('active')) : (t('inactive'))}
                                </Badge>
                              )}
                            </TableCell>
                            <TableCell>
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button variant="ghost" size="icon">
                                    <MoreHorizontal className="h-4 w-4" />
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                  <DropdownMenuItem
                                    disabled={cls.is_active === false}
                                    data-testid={`edit-class-${cls.id}`}
                                  >
                                    <Edit className="h-4 w-4 me-2" />
                                    {t('edit')}
                                  </DropdownMenuItem>
                                  {cls.is_active === false && (
                                    <DropdownMenuItem
                                      onClick={() => handleReactivateClass(cls.id)}
                                      data-testid={`reactivate-class-${cls.id}`}
                                    >
                                      <RotateCcw className="h-4 w-4 me-2" />
                                      {t('reactivate')}
                                    </DropdownMenuItem>
                                  )}
                                  <DropdownMenuItem 
                                    className="text-red-600"
                                    onClick={() => handleDeleteClass(cls.id)}
                                  >
                                    <Trash2 className="h-4 w-4 me-2" />
                                    {t('delete')}
                                  </DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenu>
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Task #631 — Recently deleted classes (soft-deleted rows that
              can be restored via POST /classes/{id}/restore). Only
              rendered when there is at least one such row. */}
          {deletedClasses.length > 0 && (
            <Card className="card-nassaq border-red-200" data-testid="recently-deleted-classes-card">
              <CardContent className="p-0">
                <button
                  type="button"
                  onClick={() => setDeletedExpanded(v => !v)}
                  className="w-full flex items-center justify-between px-6 py-4 text-start"
                  data-testid="recently-deleted-toggle"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-red-50 flex items-center justify-center">
                      <Trash2 className="h-5 w-5 text-red-600" aria-hidden="true" strokeWidth={1.5} />
                    </div>
                    <div>
                      <div className="font-cairo font-bold text-foreground">
                        {isRTL ? 'الفصول المحذوفة حديثاً' : 'Recently deleted classes'}
                      </div>
                      <div className="text-sm text-muted-foreground font-tajawal">
                        {isRTL
                          ? `${deletedClasses.length} فصل قابل للاستعادة`
                          : `${deletedClasses.length} class${deletedClasses.length === 1 ? '' : 'es'} can be restored`}
                      </div>
                    </div>
                  </div>
                  {deletedExpanded ? (
                    <ChevronUp className="h-5 w-5 text-muted-foreground" aria-hidden="true" strokeWidth={1.5} />
                  ) : (
                    <ChevronDown className="h-5 w-5 text-muted-foreground" aria-hidden="true" strokeWidth={1.5} />
                  )}
                </button>

                {deletedExpanded && (
                  <div className="rounded-b-xl overflow-hidden border-t border-border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>{t('class')}</TableHead>
                          <TableHead>{isRTL ? 'حُذف بواسطة' : 'Deleted by'}</TableHead>
                          <TableHead>{isRTL ? 'تاريخ الحذف' : 'Deleted at'}</TableHead>
                          {!isSchoolLevel && <TableHead>{t('school')}</TableHead>}
                          <TableHead className="w-32"></TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {deletedClasses.map((cls) => (
                          <TableRow
                            key={cls.id}
                            data-testid={`deleted-class-row-${cls.id}`}
                          >
                            <TableCell>
                              <div className="flex items-center gap-3">
                                <div className="w-9 h-9 rounded-full bg-red-50 flex items-center justify-center">
                                  <FolderOpen className="h-4 w-4 text-red-600" aria-hidden="true" strokeWidth={1.5} />
                                </div>
                                <div>
                                  <div className="font-medium">{cls.name}</div>
                                  <div className="text-xs text-muted-foreground">{cls.grade_level}</div>
                                </div>
                              </div>
                            </TableCell>
                            <TableCell className="text-sm">
                              {cls.deleted_by_name
                                || (cls.deleted_by ? (isRTL ? 'مستخدم محذوف' : 'Unknown user') : '-')}
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              {formatDeletedAt(cls.deleted_at)}
                            </TableCell>
                            {!isSchoolLevel && (
                              <TableCell>{getSchoolName(cls.school_id)}</TableCell>
                            )}
                            <TableCell>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleRestoreClass(cls)}
                                disabled={restoringId === cls.id}
                                className="rounded-xl border-brand-turquoise text-brand-turquoise hover:bg-brand-turquoise/10 hover:text-brand-turquoise"
                                data-testid={`restore-class-${cls.id}`}
                              >
                                {restoringId === cls.id ? (
                                  <Loader2 className="h-4 w-4 animate-spin me-2" aria-hidden="true" />
                                ) : (
                                  <Undo2 className="h-4 w-4 me-2" aria-hidden="true" strokeWidth={1.5} />
                                )}
                                {isRTL ? 'استعادة' : 'Restore'}
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
      <Suspense fallback={null}>
        {relinkOpen && (
          <RelinkAssignmentsWizard
            open={relinkOpen}
            onOpenChange={setRelinkOpen}
            classId={relinkClassId}
            api={api}
            onDone={() => fetchData({ includeInactive: showInactive })}
          />
        )}
      </Suspense>
    </Sidebar>
  );
};
