import { useState, useEffect, useMemo, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { Sidebar } from '../components/layout/Sidebar';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import {
  Users, GraduationCap, Search, Sun, Moon, Globe, MoreHorizontal,
  Edit, Trash2, BookOpen, Loader2, Eye, UserCheck, Key, Building2, RefreshCw, AlertTriangle,
  UserX, ArrowLeft, ArrowRight, ChevronRight, Star, UserPlus,
  Calendar, Hash, LayoutGrid, List, Download
} from 'lucide-react';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuTrigger, DropdownMenuSeparator
} from '../components/ui/dropdown-menu';
import AddStudentWizard from '../components/wizards/AddStudentWizard';
import { getApiErrorMessage } from '../utils/apiError';
import { useSchoolNavigation } from '../utils/studentNavigation';
import { useCanViewInternalIds } from '../hooks/useCanViewInternalIds';

const CartoonMaleAvatar = ({ name, size = 'md' }) => {
  const { t } = useTranslation();
  const dims = size === 'lg' ? 56 : size === 'sm' ? 32 : 44;
  return (
    <svg width={dims} height={dims} viewBox="0 0 100 100" className="shrink-0">
      <defs>
        <linearGradient id="maleBgCd" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#1B2A4A" />
          <stop offset="100%" stopColor="#2563eb" />
        </linearGradient>
      </defs>
      <circle cx="50" cy="50" r="48" fill="url(#maleBgCd)" />
      <ellipse cx="50" cy="42" rx="20" ry="22" fill="#FDDCB5" />
      <path d="M30 30 Q35 15 50 18 Q65 15 70 30 Q72 22 65 20 Q55 10 45 12 Q35 10 28 22 Z" fill="#3B2314" />
      <ellipse cx="41" cy="40" rx="3.5" ry="4" fill="#2d1810" />
      <ellipse cx="59" cy="40" rx="3.5" ry="4" fill="#2d1810" />
      <circle cx="42.5" cy="39" r="1.2" fill="white" />
      <circle cx="60.5" cy="39" r="1.2" fill="white" />
      <path d="M44 51 Q50 56 56 51" stroke="#c0392b" strokeWidth="2.5" fill="none" strokeLinecap="round" />
      <ellipse cx="33" cy="45" rx="4" ry="3" fill="#F4B8A5" opacity="0.5" />
      <ellipse cx="67" cy="45" rx="4" ry="3" fill="#F4B8A5" opacity="0.5" />
      <path d="M30 70 Q50 62 70 70 L75 90 Q50 85 25 90 Z" fill="#1B2A4A" />
      <text x="50" y="82" textAnchor="middle" fill="white" fontSize="11" fontWeight="bold" fontFamily="Arial">{name?.charAt(0) || ''}</text>
    </svg>
  );
};

const CartoonFemaleAvatar = ({ name, size = 'md' }) => {
  const dims = size === 'lg' ? 56 : size === 'sm' ? 32 : 44;
  return (
    <svg width={dims} height={dims} viewBox="0 0 100 100" className="shrink-0">
      <defs>
        <linearGradient id="femaleBgCd" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#ec4899" />
          <stop offset="100%" stopColor="#f43f5e" />
        </linearGradient>
      </defs>
      <circle cx="50" cy="50" r="48" fill="url(#femaleBgCd)" />
      <ellipse cx="50" cy="42" rx="20" ry="22" fill="#FDDCB5" />
      <path d="M25 35 Q28 12 50 15 Q72 12 75 35 Q76 28 72 22 Q65 8 50 10 Q35 8 28 22 Q24 28 25 35 Z" fill="#5C3317" />
      <path d="M25 35 Q24 50 28 60" stroke="#5C3317" strokeWidth="5" fill="none" strokeLinecap="round" />
      <path d="M75 35 Q76 50 72 60" stroke="#5C3317" strokeWidth="5" fill="none" strokeLinecap="round" />
      <ellipse cx="41" cy="40" rx="3" ry="3.5" fill="#2d1810" />
      <ellipse cx="59" cy="40" rx="3" ry="3.5" fill="#2d1810" />
      <circle cx="42" cy="39" r="1" fill="white" />
      <circle cx="60" cy="39" r="1" fill="white" />
      <path d="M36 35 Q41 32 46 35" stroke="#5C3317" strokeWidth="1.5" fill="none" />
      <path d="M54 35 Q59 32 64 35" stroke="#5C3317" strokeWidth="1.5" fill="none" />
      <path d="M45 51 Q50 55 55 51" stroke="#e74c6f" strokeWidth="2" fill="none" strokeLinecap="round" />
      <ellipse cx="34" cy="45" rx="4" ry="3" fill="#F4B8A5" opacity="0.6" />
      <ellipse cx="66" cy="45" rx="4" ry="3" fill="#F4B8A5" opacity="0.6" />
      <path d="M30 70 Q50 62 70 70 L75 90 Q50 85 25 90 Z" fill="#ec4899" />
      <text x="50" y="82" textAnchor="middle" fill="white" fontSize="11" fontWeight="bold" fontFamily="Arial">{name?.charAt(0) || ''}</text>
    </svg>
  );
};

const StudentAvatar = ({ student, size = 'md' }) => {
  const gender = student.gender?.toLowerCase();
  if (gender === 'female') return <CartoonFemaleAvatar name={student.full_name} size={size} />;
  return <CartoonMaleAvatar name={student.full_name} size={size} />;
};

const THEME_COLORS = {
  student: {
    gradient: 'from-[#1B2A4A] to-[#2563eb]',
    bg: 'bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20',
    border: 'border-blue-200/50 dark:border-blue-800',
    hoverBorder: 'hover:border-[#1B2A4A]/40',
    text: 'text-[#1B2A4A]',
    accent: 'text-blue-600',
    badge: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    badgeDot: 'bg-blue-500',
    bar: 'bg-gradient-to-r from-[#1B2A4A] to-[#2563eb]',
    icon: 'text-blue-500',
  },
};

const StudentCard = ({ student, isRTL, onView, onEdit, onDelete, onAction, viewMode = 'grid' }) => {
  const { t } = useTranslation();
  const canViewInternalIds = useCanViewInternalIds();
  const tc = THEME_COLORS.student;
  if (viewMode === 'list') {
    return (
      <Card className={`group hover:shadow-md transition-all duration-200 border-border/50 ${tc.hoverBorder} cursor-pointer overflow-hidden`}
        onClick={() => onView(student)}>
        <div className={`h-0.5 ${tc.bar}`} />
        <CardContent className="p-3 flex items-center gap-3">
          <div className="relative">
            <div className={`rounded-full ring-2 ${student.is_gifted ? 'ring-amber-400' : 'ring-transparent'}`}>
              <StudentAvatar student={student} size="sm" />
            </div>
            {student.is_gifted && (
              <div className="absolute -top-0.5 -end-0.5 w-3.5 h-3.5 rounded-full bg-amber-400 flex items-center justify-center shadow-sm">
                <Star className="h-2 w-2 text-white fill-white" />
              </div>
            )}
          </div>
          <div className="flex-1 min-w-0 flex items-center gap-4">
            <h3 className="font-semibold text-sm truncate w-[140px] flex items-center gap-1.5">
              {student.full_name}
              {student.is_gifted && <Star className="h-3 w-3 text-amber-500 fill-amber-500 shrink-0" />}
            </h3>
            <span className="text-xs text-muted-foreground truncate hidden sm:inline">{student.grade || '-'} • {student.section || student.class_name || '-'}</span>
            <span className="text-[10px] text-muted-foreground font-mono hidden md:inline">{student.student_number || (canViewInternalIds ? student.id?.slice(0, 8) : '—')}</span>
          </div>
          <Badge variant={student.is_active !== false ? 'default' : 'destructive'}
            className={`text-[10px] h-5 rounded-full border-0 ${student.is_active !== false ? tc.badge : ''}`}>
            <span className={`w-1.5 h-1.5 rounded-full me-1 ${student.is_active !== false ? tc.badgeDot : 'bg-red-500'}`} />
            {student.is_active !== false ? (t('active')) : (t('suspended'))}
          </Badge>
          <DropdownMenu>
            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
              <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0"><MoreHorizontal className="h-4 w-4" /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48" onClick={(e) => e.stopPropagation()}>
              <DropdownMenuItem onClick={() => onView(student)}><Eye className="h-3.5 w-3.5 me-2" />{t('viewProfile2')}</DropdownMenuItem>
              <DropdownMenuItem onClick={() => onEdit(student)}><Edit className="h-3.5 w-3.5 me-2" />{t('editInfo')}</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => onAction(student, 'reset-password')}><Key className="h-3.5 w-3.5 me-2" />{t('resetPassword')}</DropdownMenuItem>
              <DropdownMenuItem onClick={() => onDelete(student)} className="text-red-600"><Trash2 className="h-3.5 w-3.5 me-2" />{t('delete')}</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={`group hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 border-border/50 ${tc.hoverBorder} h-full cursor-pointer overflow-hidden`}
      onClick={() => onView(student)}>
      <div className={`h-1.5 ${tc.bar}`} />
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className="relative">
              <div className={`rounded-full ring-2 ${student.is_gifted ? 'ring-amber-400' : 'ring-transparent'}`}>
                <StudentAvatar student={student} />
              </div>
              {student.is_gifted && (
                <div className="absolute -top-0.5 -end-0.5 w-3.5 h-3.5 rounded-full bg-amber-400 flex items-center justify-center shadow-sm">
                  <Star className="h-2 w-2 text-white fill-white" />
                </div>
              )}
            </div>
            <div className="min-w-0">
              <h3 className="font-semibold text-sm truncate max-w-[140px] flex items-center gap-1.5">
                {student.full_name}
                {student.is_gifted && <Star className="h-3 w-3 text-amber-500 fill-amber-500 shrink-0" />}
              </h3>
              <p className="text-[10px] text-muted-foreground font-mono">{student.student_number || (canViewInternalIds ? student.id?.slice(0, 8) : '—')}</p>
              {student.talents?.length > 0 && (
                <div className="flex flex-wrap gap-0.5 mt-1">
                  {student.talents.slice(0, 2).map(talent => (
                    <span key={talent} className="text-[8px] px-1.5 py-0 rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300 border border-amber-200 dark:border-amber-700">
                      {String(talent).replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()).substring(0, 12)}
                    </span>
                  ))}
                  {student.talents.length > 2 && (
                    <span className="text-[8px] px-1 text-amber-600 dark:text-amber-400">+{student.talents.length - 2}</span>
                  )}
                </div>
              )}
            </div>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
              <Button variant="ghost" size="icon" className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity"><MoreHorizontal className="h-4 w-4" /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48" onClick={(e) => e.stopPropagation()}>
              <DropdownMenuItem onClick={() => onView(student)}><Eye className="h-3.5 w-3.5 me-2" />{t('viewProfile2')}</DropdownMenuItem>
              <DropdownMenuItem onClick={() => onEdit(student)}><Edit className="h-3.5 w-3.5 me-2" />{t('editInfo')}</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => onAction(student, 'reset-password')}><Key className="h-3.5 w-3.5 me-2" />{t('resetPassword')}</DropdownMenuItem>
              <DropdownMenuItem onClick={() => onAction(student, student.is_active !== false ? 'suspend' : 'activate')}>
                {student.is_active !== false ? <UserX className="h-3.5 w-3.5 me-2" /> : <UserCheck className="h-3.5 w-3.5 me-2" />}
                {student.is_active !== false ? (t('suspendAccount')) : (t('activateAccount'))}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => onDelete(student)} className="text-red-600"><Trash2 className="h-3.5 w-3.5 me-2" />{t('delete')}</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <div className="space-y-1.5 text-xs mb-3">
          <div className="flex items-center gap-2 text-muted-foreground">
            <BookOpen className="h-3 w-3 shrink-0" />
            <span className="truncate">{student.grade || '-'}</span>
            <span className="text-muted-foreground/30 mx-0.5">•</span>
            <span className="truncate">{student.section || student.class_name || '-'}</span>
          </div>
          {student.education_level && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <GraduationCap className="h-3 w-3 shrink-0" />
              <span className="truncate">{student.education_level}</span>
            </div>
          )}
        </div>
        <div className="flex items-center justify-between pt-2.5 border-t border-border/40">
          <Badge variant={student.is_active !== false ? 'default' : 'destructive'}
            className={`text-[10px] h-5 rounded-full border-0 ${student.is_active !== false ? tc.badge : ''}`}>
            <span className={`w-1.5 h-1.5 rounded-full me-1 ${student.is_active !== false ? tc.badgeDot : 'bg-red-500'}`} />
            {student.is_active !== false ? (t('active')) : (t('suspended'))}
          </Badge>
          <ChevronRight className={`h-3.5 w-3.5 text-muted-foreground/30 group-hover:${tc.accent} group-hover:translate-x-0.5 transition-all`} />
        </div>
      </CardContent>
    </Card>
  );
};

export default function ClassDetailPage() {
  const { t } = useTranslation();
  const { classId } = useParams();
  const navigate = useNavigate();
  const { user, api, schoolContext, isImpersonating } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  const { nassaqConfirm, nassaqError } = useNassaqAlert();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [classData, setClassData] = useState(null);
  const [students, setStudents] = useState([]);
  const [classes, setClasses] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState('grid');
  const [showStudentWizard, setShowStudentWizard] = useState(false);
  const [grades, setGrades] = useState([]);

  // Principal route audit 2026-07-28: this page is SCHOOL_ROLES-only (all
  // leadership), so the management breadcrumb always points at the canonical
  // /principal URL — the old role ternary leaked school_admin/sub_admin into
  // the legacy /admin namespace.
  const managementPath = '/principal/users-management';

  const headers = useMemo(() => {
    const h = {};
    if (isImpersonating && schoolContext?.school_id) h['X-School-Context'] = schoolContext.school_id;
    return h;
  }, [isImpersonating, schoolContext]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const [classRes, studentsRes, classesRes, gradesRes] = await Promise.all([
        api.get(`/classes/${classId}`, { headers }),
        api.get(`/classes/${classId}/students`, { headers }),
        api.get('/classes', { headers }).catch(() => ({ data: [] })),
        api.get('/reference/grades', { headers }).catch(() => ({ data: [] })),
      ]);
      setClassData(classRes.data);
      setStudents(Array.isArray(studentsRes.data) ? studentsRes.data : []);
      setClasses(Array.isArray(classesRes.data) ? classesRes.data : []);
      setGrades(Array.isArray(gradesRes.data) ? gradesRes.data : []);
    } catch (error) {
      setError(true);
      const status = error?.response?.status;
      if (status === 403) {
        nassaqError('هذا الفصل غير مسند إليك أو لا تملك صلاحية استعراضه');
      } else if (status === 404) {
        nassaqError('الفصل غير موجود');
      } else {
        nassaqError(t('errorLoadingClassData'));
      }
    } finally {
      setLoading(false);
    }
  }, [api, classId, headers, isRTL, nassaqError]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const filteredStudents = useMemo(() => {
    if (!searchQuery.trim()) return students;
    const q = searchQuery.toLowerCase();
    return students.filter(s =>
      (s.full_name || '').toLowerCase().includes(q) ||
      (s.student_number || '').toLowerCase().includes(q) ||
      (s.email || '').toLowerCase().includes(q)
    );
  }, [students, searchQuery]);

  // Student category filter tabs were removed from the UI; the list now
  // always shows all students (subject only to the search query).
  const displayedStudents = filteredStudents;

  const { rolePrefix, getStudentDetailPath } = useSchoolNavigation();

  const navigateToStudent = (student) => {
    navigate(getStudentDetailPath(student.id), {
      state: { classId, className: classData?.name, fromPath: `${rolePrefix}/classes/${classId}` }
    });
  };

  const handleView = (student) => {
    navigateToStudent(student);
  };

  const handleEdit = (student) => {
    navigateToStudent(student);
  };

  const handleDelete = async (student) => {
    const confirmed = await nassaqConfirm(
      isRTL ? `هل أنت متأكد من حذف الطالب "${student.full_name}"؟` : `Are you sure you want to delete "${student.full_name}"?`
    );
    if (!confirmed) return;
    try {
      const res = await api.delete(`/students/${student.id}`, { headers });
      if (res?.data && res.data.success === false) {
        // Backend returned 2xx but explicitly signalled failure — treat as error.
        const msg = res.data.detail || res.data.message;
        nassaqError(typeof msg === 'string' ? msg : (t('deleteFailed2')));
        return;
      }
      // Bug #372 — optimistically remove the deleted student from local
      // state so the card disappears and the count drops the moment the
      // success toast appears, then reconcile via fetchData(). This
      // shields us from any browser-cached GET response on the post-
      // delete refetch (the backend now also sets Cache-Control:
      // no-store on the two GET endpoints).
      setStudents(prev => prev.filter(s => s.id !== student.id));
      setClassData(prev => prev ? {
        ...prev,
        student_count: Math.max(0, (prev.student_count || prev.current_students || 0) - 1),
        current_students: Math.max(0, (prev.current_students || prev.student_count || 0) - 1),
      } : prev);
      toast.success(t('studentDeleted'));
      fetchData();
    } catch (error) {
      const msg = getApiErrorMessage(error);
      nassaqError(typeof msg === 'string' ? msg : (t('deleteFailed2')));
    }
  };

  const handleAccountAction = async (student, action) => {
    try {
      switch (action) {
        case 'reset-password': {
          const genRes = await api.post('/principal/generate-password');
          const tempPass = genRes.data.password;
          await api.put(`/principal/student/${student.id}/credentials`, { new_password: tempPass });
          toast.success(isRTL ? `تم إعادة تعيين كلمة المرور إلى: ${tempPass}` : `Password reset to: ${tempPass}`);
          break;
        }
        case 'suspend':
          await api.put(`/principal/student/${student.id}/status`, { status: 'suspended' });
          toast.success(t('accountSuspended'));
          fetchData();
          break;
        case 'activate':
          await api.put(`/principal/student/${student.id}/status`, { status: 'active' });
          toast.success(t('accountActivated'));
          fetchData();
          break;
        default: break;
      }
    } catch (error) {
      const msg = getApiErrorMessage(error);
      nassaqError(typeof msg === 'string' ? msg : (t('operationFailed')));
    }
  };

  const handleExportClassList = async () => {
    try {
      const className = encodeURIComponent(classData?.name || '');
      const res = await api.get(`/bulk/export/students?format=xlsx&class_name=${className}`, { headers, responseType: 'blob' });
      const blob = new Blob([res.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${(classData?.name || 'class').replace(/\s+/g, '_')}_students.xlsx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
      toast.success(t('classListExported'));
    } catch (e) {
      console.error('Error exporting class list:', e);
      nassaqError(t('exportFailed'));
    }
  };

  const BackArrow = isRTL ? ArrowRight : ArrowLeft;


  if (loading) {
    return (
      <Sidebar>
        <div className="min-h-screen flex items-center justify-center">
          <div className="text-center">
            <Loader2 className="h-10 w-10 animate-spin text-brand-turquoise mx-auto mb-3" />
            <p className="text-sm text-muted-foreground">{t('loadingClassData')}</p>
          </div>
        </div>
      </Sidebar>
    );
  }

  if (error || !classData) {
    return (
      <Sidebar>
        <div className="min-h-screen flex items-center justify-center p-4">
          <div className="text-center max-w-md w-full space-y-5">
            <div className="w-14 h-14 rounded-2xl bg-red-100 dark:bg-red-900/30 flex items-center justify-center mx-auto">
              <AlertTriangle className="h-7 w-7 text-red-600" strokeWidth={1.5} aria-hidden="true" />
            </div>
            <p className="text-lg font-semibold">
              {error ? t('errorLoadingClassData') : t('classNotFound')}
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <Button onClick={() => fetchData()} className="w-full sm:w-auto">
                <RefreshCw className="h-4 w-4 me-2" strokeWidth={1.5} aria-hidden="true" />
                {t('retry')}
              </Button>
              <Button variant="outline" onClick={() => navigate(managementPath)} className="w-full sm:w-auto">
                <BackArrow className="h-4 w-4 me-2" />
                {t('backToUserManagement')}
              </Button>
            </div>
          </div>
        </div>
      </Sidebar>
    );
  }

  const capacityPct = Math.min(100, ((classData.student_count || students.length) / (classData.capacity || 30)) * 100);

  return (
    <Sidebar>
      <div className="min-h-screen" data-testid="class-detail-page">
        <header className="sticky top-0 z-30 glass border-b border-border/50 px-4 sm:px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3 min-w-0">
              <Button variant="ghost" size="icon" className="shrink-0 h-9 w-9" onClick={() => navigate(managementPath)}>
                <BackArrow className="h-5 w-5" />
              </Button>
              <div className="min-w-0">
                <nav className="flex items-center gap-1.5 text-xs text-muted-foreground mb-0.5 flex-wrap">
                  <Link to={managementPath} className="hover:text-foreground transition-colors">
                    {t('userManagement')}
                  </Link>
                  <ChevronRight className="h-3 w-3 shrink-0 rtl:rotate-180" />
                  <span className="text-foreground font-medium truncate">{classData.name}</span>
                </nav>
                <h1 className="font-cairo text-xl sm:text-2xl font-bold truncate">{classData.name}</h1>
              </div>
            </div>
            <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
              <Button onClick={() => setShowStudentWizard(true)} className="bg-brand-turquoise hover:bg-brand-turquoise/90 rounded-xl h-9 sm:h-10 shadow-md text-xs sm:text-sm">
                <UserPlus className="h-4 w-4 me-1 sm:me-1.5" />
                <span className="hidden sm:inline">{t('addStudent')}</span>
                <span className="sm:hidden">{t('add')}</span>
              </Button>
              <Button variant="ghost" size="icon" className="h-9 w-9" onClick={toggleLanguage}><Globe className="h-5 w-5" /></Button>
              <Button variant="ghost" size="icon" className="h-9 w-9" onClick={toggleTheme}>{isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}</Button>
            </div>
          </div>
        </header>

        <main className="p-4 sm:p-6 space-y-6">
          <Card className="overflow-hidden border-border/50">
            <div className="h-2 bg-gradient-to-r from-purple-600 via-brand-turquoise to-brand-navy rounded-t-lg" />
            <CardContent className="p-4 sm:p-6">
              <div className="flex flex-col sm:flex-row sm:items-center gap-4">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-purple-600 to-purple-700 flex items-center justify-center shadow-lg shrink-0">
                  <Building2 className="h-7 w-7 text-white" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <h2 className="font-cairo text-xl font-bold">{classData.name}</h2>
                    {classData.class_type && (
                      <Badge variant="outline" className="text-[10px]">{classData.class_type}</Badge>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm text-muted-foreground">
                    <div className="flex items-center gap-1.5">
                      <GraduationCap className="h-3.5 w-3.5 shrink-0" />
                      <span>{classData.grade || '-'}{classData.section ? ` - ${classData.section}` : ''}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <UserCheck className="h-3.5 w-3.5 shrink-0" />
                      <span>{classData.homeroom_teacher_name || (t('noTeacherAssigned2'))}</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Users className="h-3.5 w-3.5 shrink-0" />
                      <span>{students.length} {t('studentsLower')}</span>
                    </div>
                    {classData.academic_year_id && (
                      <div className="flex items-center gap-1.5">
                        <Calendar className="h-3.5 w-3.5 shrink-0" />
                        <span>{classData.academic_year_id}</span>
                      </div>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <div className="text-center px-3">
                    <div className="text-2xl font-bold">{students.length}</div>
                    <div className="text-[10px] text-muted-foreground">/ {classData.capacity || 30}</div>
                  </div>
                  <div className="w-20">
                    <div className={`text-[10px] font-medium text-center mb-1 ${capacityPct > 90 ? 'text-red-500' : capacityPct > 70 ? 'text-amber-500' : 'text-emerald-500'}`}>
                      {Math.round(capacityPct)}% {t('full')}
                    </div>
                    <div className="w-full bg-muted rounded-full h-2">
                      <div className={`h-2 rounded-full transition-all duration-500 ${capacityPct > 90 ? 'bg-gradient-to-r from-red-400 to-red-500' : capacityPct > 70 ? 'bg-gradient-to-r from-amber-400 to-orange-500' : 'bg-gradient-to-r from-emerald-400 to-green-500'}`}
                        style={{ width: `${capacityPct}%` }} />
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="flex flex-col sm:flex-row sm:items-center justify-end gap-3">
            <div className="flex items-center gap-2">
              <div className="relative flex-1 sm:w-64">
                <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder={t('searchStudents')}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="ps-9 h-9 rounded-xl"
                />
              </div>
              <div className="flex items-center border rounded-lg overflow-hidden">
                <Button variant={viewMode === 'grid' ? 'default' : 'ghost'} size="icon" className="h-9 w-9 rounded-none"
                  onClick={() => setViewMode('grid')}><LayoutGrid className="h-4 w-4" /></Button>
                <Button variant={viewMode === 'list' ? 'default' : 'ghost'} size="icon" className="h-9 w-9 rounded-none"
                  onClick={() => setViewMode('list')}><List className="h-4 w-4" /></Button>
              </div>
              <Button variant="outline" size="sm" className="h-9 gap-1.5 text-xs rounded-xl" onClick={handleExportClassList}>
                <Download className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">{t('export')}</span>
              </Button>
            </div>
          </div>

          {displayedStudents.length === 0 ? (
            <Card className="p-12 text-center border-dashed">
              <GraduationCap className="h-16 w-16 mx-auto text-muted-foreground/15 mb-4" />
              <p className="text-muted-foreground font-medium">
                {searchQuery
                  ? (t('noMatchingStudents'))
                  : (t('noStudentsInThisClass'))}
              </p>
              <p className="text-sm text-muted-foreground/60 mt-1">
                {searchQuery
                  ? (t('tryADifferentSearch'))
                  : (t('addStudentsToThisClass'))}
              </p>
              {!searchQuery && (
                <Button variant="outline" className="mt-4" onClick={() => setShowStudentWizard(true)}>
                  <UserPlus className="h-4 w-4 me-2" />
                  {t('addStudent')}
                </Button>
              )}
            </Card>
          ) : viewMode === 'list' ? (
            <div className="space-y-2">
              {displayedStudents.map(s => (
                <StudentCard key={s.id} student={s} isRTL={isRTL} viewMode="list"
                  onView={handleView} onEdit={handleEdit} onDelete={handleDelete}
                  onAction={handleAccountAction} />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-3">
              {displayedStudents.map(s => (
                <StudentCard key={s.id} student={s} isRTL={isRTL}
                  onView={handleView} onEdit={handleEdit} onDelete={handleDelete}
                  onAction={handleAccountAction} />
              ))}
            </div>
          )}
        </main>

        <AddStudentWizard
          open={showStudentWizard}
          onOpenChange={setShowStudentWizard}
          onSuccess={() => { setShowStudentWizard(false); fetchData(); toast.success(t('studentAdded')); }}
          api={api}
          isRTL={isRTL}
          grades={grades}
          classes={classes}
          preselectedClassId={classId}
          preselectedGradeId={classData?.grade_id || classData?.grade_level || ''}
          preselectedEducationLevel={(() => {
            const g = Number(classData?.grade);
            if (!g || Number.isNaN(g)) return '';
            if (g <= 6) return 'primary';
            if (g <= 9) return 'middle';
            return 'high';
          })()}
        />
      </div>
    </Sidebar>
  );
}
