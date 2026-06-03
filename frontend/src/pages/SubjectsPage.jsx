import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme, useTranslation } from '../contexts/ThemeContext';
import { Sidebar } from '../components/layout/Sidebar';
import { HakimAssistant } from '../components/hakim/HakimAssistant';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Textarea } from '../components/ui/textarea';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import {
  Library,
  Plus,
  Search,
  MoreHorizontal,
  Sun,
  Moon,
  Globe,
  Trash2,
  Edit,
  Loader2,
  ArrowLeft,
  Clock,
  BookMarked,
  ChevronDown,
  ChevronUp,
  Undo2,
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import { Link } from 'react-router-dom';
import { getApiErrorMessage } from '../utils/apiError';

export const SubjectsPage = () => {
  const { user, api } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  const { nassaqError, nassaqWarning, nassaqConfirm, showAlert } = useNassaqAlert();
  const { t } = useTranslation();
  const [subjects, setSubjects] = useState([]);
  const [schools, setSchools] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingSubject, setEditingSubject] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSchool, setSelectedSchool] = useState('all');
  const [submitting, setSubmitting] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [deletedExpanded, setDeletedExpanded] = useState(false);
  const [restoringId, setRestoringId] = useState(null);
  const isSchoolLevel = user?.role && !user.role.startsWith('platform_');
  
  const [newSubject, setNewSubject] = useState({
    name: '',
    name_en: '',
    code: '',
    description: '',
    school_id: '',
    credits: 1,
    weekly_hours: 3,
    category: '',
  });

  const categoryOptions = [
    { value: 'core', label: t('categoryCore') },
    { value: 'elective', label: t('categoryElective') },
    { value: 'language', label: t('language2') },
    { value: 'science', label: t('science') },
    { value: 'math', label: t('mathematics') },
    { value: 'social', label: t('socialStudies') },
    { value: 'arts', label: t('arts') },
    { value: 'physical', label: t('physicalEducation') },
    { value: 'technology', label: t('technology') },
    { value: 'religion', label: t('religion') },
  ];

  const fetchData = async () => {
    try {
      // Task #645 — always request include_deleted=true so the
      // "Recently deleted" section is populated. The backend silently
      // ignores the flag for non-admin callers.
      const [subjectsRes, schoolsRes] = await Promise.all([
        api.get('/subjects', { params: { include_deleted: true } }),
        api.get('/schools').catch(() => ({ data: [] })),
      ]);
      setSubjects(subjectsRes.data);
      setSchools(schoolsRes.data || []);
    } catch (error) {
      console.error('Failed to fetch data:', error);
      nassaqError(t('failedToLoadData'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  const resetForm = () => {
    setNewSubject({
      name: '',
      name_en: '',
      code: '',
      description: '',
      school_id: '',
      credits: 1,
      weekly_hours: 3,
      category: '',
    });
  };

  const handleCreateSubject = async () => {
    if (!newSubject.name || !newSubject.school_id || !newSubject.code) {
      nassaqError(t('pleaseFillAllRequiredFields'));
      return;
    }

    setSubmitting(true);
    try {
      await api.post('/subjects', newSubject);
      toast.success(t('subjectAddedSuccessfully'));
      setCreateDialogOpen(false);
      resetForm();
      fetchData();
    } catch (error) {
      nassaqError(getApiErrorMessage(error) || (t('failedToAddSubject')));
    } finally {
      setSubmitting(false);
    }
  };

  const handleEditSubject = async () => {
    if (!editingSubject || !editingSubject.name || !editingSubject.school_id) {
      nassaqError(t('pleaseFillAllRequiredFields'));
      return;
    }

    setSubmitting(true);
    try {
      await api.put(`/subjects/${editingSubject.id}`, editingSubject);
      toast.success(t('subjectUpdatedSuccessfully'));
      setEditDialogOpen(false);
      setEditingSubject(null);
      fetchData();
    } catch (error) {
      nassaqError(getApiErrorMessage(error) || (t('failedToUpdateSubject')));
    } finally {
      setSubmitting(false);
    }
  };

  const performDelete = async (subjectId, { force = false } = {}) => {
    setDeletingId(subjectId);
    try {
      const res = await api.delete(`/subjects/${subjectId}`, force ? { params: { force: true } } : undefined);
      const data = res?.data;
      if (data && data.requires_confirmation) {
        const deps = data.dependencies || {};
        const classes = deps.classes || 0;
        const assignments = deps.teacher_assignments || 0;
        const sessions = deps.schedule_sessions || 0;
        const lines = [
          data.message || t('subjectDeleteHasDependencies') || 'هذه المادة لا تزال مستخدمة.',
          `• ${t('classes') || 'الفصول'}: ${classes}`,
          `• ${t('teacherAssignments') || 'إسنادات المعلمين'}: ${assignments}`,
          `• ${t('scheduleSessions') || 'الحصص في الجدول'}: ${sessions}`,
          t('subjectDeleteAnywayHint') || 'سيؤدي الحذف إلى إخفاء المادة دون حذف الفصول أو الحصص المرتبطة. هل تريد المتابعة؟',
        ];
        setDeletingId(null);
        nassaqConfirm(lines.join('\n'), async () => {
          await performDelete(subjectId, { force: true });
        }, {
          confirmText: t('deleteAnyway') || 'حذف على أي حال',
          cancelText: t('cancel') || 'إلغاء',
        });
        return;
      }
      fetchData();
    } catch (err) {
      const detail = getApiErrorMessage(err);
      nassaqError(typeof detail === 'string' ? detail : t('failedToDeleteSubject'));
    } finally {
      setDeletingId((current) => (current === subjectId ? null : current));
    }
  };

  const handleDeleteSubject = (subject) => {
    const label = subject.name || subject.name_en || '';
    const message = t('areYouSureYouWantToDeleteThisSubject') + (label ? `\n${label}` : '');
    nassaqConfirm(message, async () => {
      await performDelete(subject.id);
    });
  };

  const openEditDialog = (subject) => {
    setEditingSubject({ ...subject });
    setEditDialogOpen(true);
  };

  // Task #645 — restore a soft-deleted subject. Dependent rows
  // (classes/teacher_assignments/schedule_sessions) stay inactive on
  // purpose so the principal can re-link them deliberately.
  const handleRestoreSubject = async (subject) => {
    const sName = subject?.name || '';
    nassaqConfirm(
      isRTL
        ? `هل تريد استعادة المادة "${sName}"؟ ستظهر المادة مرة أخرى في القائمة، لكنك ستحتاج إلى إعادة ربط الفصول والإسنادات والجدول يدويًا.`
        : `Restore subject "${sName}"? It will reappear in the list, but you'll need to re-link its classes, assignments, and schedule manually.`,
      async () => {
        setRestoringId(subject.id);
        try {
          const res = await api.post(`/subjects/${subject.id}/restore`);
          const dependents = res?.data?.inactive_dependents || {};
          const labelMap = {
            classes: isRTL ? 'الفصول' : 'Classes',
            teacher_assignments: isRTL ? 'إسنادات المعلمين' : 'Teacher assignments',
            schedule_sessions: isRTL ? 'حصص الجدول' : 'Schedule sessions',
          };
          const lines = Object.entries(dependents)
            .filter(([, v]) => Number(v) > 0)
            .map(([k, v]) => `• ${labelMap[k] || k}: ${v}`);
          const header = isRTL
            ? `تمت استعادة المادة "${sName}" بنجاح.`
            : `Subject "${sName}" was restored successfully.`;
          const followUp = lines.length
            ? (isRTL
                ? `\n\nهذه العناصر المرتبطة لا تزال غير مُفعَّلة وتحتاج إلى إعادة ربط:\n${lines.join('\n')}`
                : `\n\nThe following linked items are still inactive and need to be re-linked:\n${lines.join('\n')}`)
            : (isRTL
                ? '\n\nلا توجد عناصر مرتبطة بحاجة إلى إعادة ربط.'
                : '\n\nNo linked items need re-linking.');
          showAlert({
            type: lines.length ? 'warning' : 'success',
            title: isRTL ? 'تمت استعادة المادة' : 'Subject restored',
            message: header + followUp,
            confirmText: isRTL ? 'حسناً' : 'OK',
          });
          await fetchData();
        } catch (error) {
          nassaqError(
            getApiErrorMessage(error)
              || (isRTL ? 'فشل استعادة المادة' : 'Failed to restore subject')
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

  // Task #645 — soft-deleted subjects (is_active=false AND deleted_at!=null)
  // live in their own "Recently deleted" section, not the main table.
  const isDeleted = (subject) => subject.is_active === false && !!subject.deleted_at;

  const filteredSubjects = subjects.filter(subject => {
    if (isDeleted(subject)) return false;
    const matchesSearch = subject.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         (subject.code && subject.code.toLowerCase().includes(searchTerm.toLowerCase()));
    const matchesSchool = selectedSchool === 'all' || subject.school_id === selectedSchool;
    return matchesSearch && matchesSchool;
  });

  const deletedSubjects = subjects
    .filter(subject => isDeleted(subject))
    .filter(subject => selectedSchool === 'all' || subject.school_id === selectedSchool)
    .sort((a, b) => {
      const ad = a.deleted_at || '';
      const bd = b.deleted_at || '';
      return bd.localeCompare(ad);
    });

  const getSchoolName = (schoolId) => {
    const school = schools.find(s => s.id === schoolId);
    return school?.name || '-';
  };

  const getCategoryLabel = (category) => {
    const cat = categoryOptions.find(c => c.value === category);
    return cat?.label || category || '-';
  };

  const getCategoryColor = (category) => {
    const colors = {
      core: 'bg-blue-100 text-blue-700',
      elective: 'bg-purple-100 text-purple-700',
      language: 'bg-green-100 text-green-700',
      science: 'bg-orange-100 text-orange-700',
      math: 'bg-red-100 text-red-700',
      social: 'bg-yellow-100 text-yellow-700',
      arts: 'bg-pink-100 text-pink-700',
      physical: 'bg-teal-100 text-teal-700',
      technology: 'bg-indigo-100 text-indigo-700',
      religion: 'bg-amber-100 text-amber-700',
    };
    return colors[category] || 'bg-gray-100 text-gray-700';
  };

  return (
    <Sidebar>
      <div className="min-h-screen bg-background" data-testid="subjects-page">
        {/* Header */}
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
                  {t('subjectsManagement')}
                </h1>
                <p className="text-sm text-muted-foreground font-tajawal">
                  {t('subjectsCount', { count: filteredSubjects.length })}
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" onClick={toggleLanguage} className="rounded-xl" data-testid="toggle-language-btn">
                <Globe className="h-5 w-5" />
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme} className="rounded-xl" data-testid="toggle-theme-btn">
                {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </Button>
            </div>
          </div>
        </header>

        <div className="p-6 space-y-6">
          {/* Actions Bar */}
          <div className="flex flex-col md:flex-row gap-4 justify-between">
            <div className="flex flex-1 gap-4 flex-wrap">
              <div className="relative flex-1 min-w-[200px] max-w-sm">
                <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                <Input
                  placeholder={t('searchSubjects')}
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="ps-10 rounded-xl"
                  data-testid="search-subjects-input"
                />
              </div>
              
              <Select value={selectedSchool} onValueChange={setSelectedSchool}>
                <SelectTrigger className="w-[200px] rounded-xl">
                  <SelectValue placeholder={t('allSchools')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('allSchools')}</SelectItem>
                  {schools.map(school => (
                    <SelectItem key={school.id} value={school.id}>{school.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
              <DialogTrigger asChild>
                <Button className="bg-brand-turquoise hover:bg-brand-turquoise-light rounded-xl" data-testid="add-subject-btn">
                  <Plus className="h-5 w-5 me-2" />
                  {t('addSubject')}
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-[550px]">
                <DialogHeader>
                  <DialogTitle className="font-cairo">
                    {t('addNewSubject')}
                  </DialogTitle>
                  <DialogDescription>
                    {t('enterTheNewSubjectDetails')}
                  </DialogDescription>
                </DialogHeader>
                
                <div className="grid gap-4 py-4 max-h-[60vh] overflow-y-auto">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>{t('subjectNameArabic')}</Label>
                      <Input
                        value={newSubject.name}
                        onChange={(e) => setNewSubject({ ...newSubject, name: e.target.value })}
                        placeholder={t('mathematics2')}
                        className="rounded-xl"
                        data-testid="subject-name-input"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>{t('subjectNameEnglish')}</Label>
                      <Input
                        value={newSubject.name_en}
                        onChange={(e) => setNewSubject({ ...newSubject, name_en: e.target.value })}
                        placeholder="Mathematics"
                        className="rounded-xl"
                      />
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>{t('subjectCode')}</Label>
                      <Input
                        value={newSubject.code}
                        onChange={(e) => setNewSubject({ ...newSubject, code: e.target.value.toUpperCase() })}
                        placeholder="MATH101"
                        className="rounded-xl font-mono"
                        data-testid="subject-code-input"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>{t('school2')}</Label>
                      <Select 
                        value={newSubject.school_id} 
                        onValueChange={(value) => setNewSubject({ ...newSubject, school_id: value })}
                      >
                        <SelectTrigger className="rounded-xl" data-testid="subject-school-select">
                          <SelectValue placeholder={t('selectSchool')} />
                        </SelectTrigger>
                        <SelectContent>
                          {schools.map(school => (
                            <SelectItem key={school.id} value={school.id}>{school.name}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-3 gap-4">
                    <div className="space-y-2">
                      <Label>{t('category')}</Label>
                      <Select 
                        value={newSubject.category} 
                        onValueChange={(value) => setNewSubject({ ...newSubject, category: value })}
                      >
                        <SelectTrigger className="rounded-xl">
                          <SelectValue placeholder={t('select2')} />
                        </SelectTrigger>
                        <SelectContent>
                          {categoryOptions.map(cat => (
                            <SelectItem key={cat.value} value={cat.value}>{cat.label}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label>{t('credits')}</Label>
                      <Input
                        type="number"
                        min={1}
                        max={10}
                        value={newSubject.credits}
                        onChange={(e) => setNewSubject({ ...newSubject, credits: parseInt(e.target.value) || 1 })}
                        className="rounded-xl"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>{t('weeklyHours')}</Label>
                      <Input
                        type="number"
                        min={1}
                        max={20}
                        value={newSubject.weekly_hours}
                        onChange={(e) => setNewSubject({ ...newSubject, weekly_hours: parseInt(e.target.value) || 3 })}
                        className="rounded-xl"
                      />
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    <Label>{t('description')}</Label>
                    <Textarea
                      value={newSubject.description}
                      onChange={(e) => setNewSubject({ ...newSubject, description: e.target.value })}
                      placeholder={t('subjectDescription')}
                      className="rounded-xl min-h-[80px]"
                    />
                  </div>
                </div>
                
                <DialogFooter>
                  <Button variant="outline" onClick={() => setCreateDialogOpen(false)} className="rounded-xl">
                    {t('cancel')}
                  </Button>
                  <Button 
                    onClick={handleCreateSubject} 
                    className="bg-brand-navy rounded-xl" 
                    disabled={submitting}
                    data-testid="create-subject-btn"
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

            {/* Edit Dialog */}
            <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
              <DialogContent className="sm:max-w-[550px]">
                <DialogHeader>
                  <DialogTitle className="font-cairo">
                    {t('editSubject')}
                  </DialogTitle>
                  <DialogDescription>
                    {t('updateSubjectDetails')}
                  </DialogDescription>
                </DialogHeader>
                
                {editingSubject && (
                  <div className="grid gap-4 py-4 max-h-[60vh] overflow-y-auto">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>{t('subjectNameArabic')}</Label>
                        <Input
                          value={editingSubject.name}
                          onChange={(e) => setEditingSubject({ ...editingSubject, name: e.target.value })}
                          className="rounded-xl"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>{t('subjectNameEnglish')}</Label>
                        <Input
                          value={editingSubject.name_en || ''}
                          onChange={(e) => setEditingSubject({ ...editingSubject, name_en: e.target.value })}
                          className="rounded-xl"
                        />
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>{t('subjectCode')}</Label>
                        <Input
                          value={editingSubject.code || ''}
                          onChange={(e) => setEditingSubject({ ...editingSubject, code: e.target.value.toUpperCase() })}
                          className="rounded-xl font-mono"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>{t('school2')}</Label>
                        <Select 
                          value={editingSubject.school_id} 
                          onValueChange={(value) => setEditingSubject({ ...editingSubject, school_id: value })}
                        >
                          <SelectTrigger className="rounded-xl">
                            <SelectValue placeholder={t('selectSchool')} />
                          </SelectTrigger>
                          <SelectContent>
                            {schools.map(school => (
                              <SelectItem key={school.id} value={school.id}>{school.name}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-3 gap-4">
                      <div className="space-y-2">
                        <Label>{t('category')}</Label>
                        <Select 
                          value={editingSubject.category || ''} 
                          onValueChange={(value) => setEditingSubject({ ...editingSubject, category: value })}
                        >
                          <SelectTrigger className="rounded-xl">
                            <SelectValue placeholder={t('select2')} />
                          </SelectTrigger>
                          <SelectContent>
                            {categoryOptions.map(cat => (
                              <SelectItem key={cat.value} value={cat.value}>{cat.label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label>{t('credits')}</Label>
                        <Input
                          type="number"
                          min={1}
                          max={10}
                          value={editingSubject.credits || 1}
                          onChange={(e) => setEditingSubject({ ...editingSubject, credits: parseInt(e.target.value) || 1 })}
                          className="rounded-xl"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>{t('weeklyHours')}</Label>
                        <Input
                          type="number"
                          min={1}
                          max={20}
                          value={editingSubject.weekly_hours || 3}
                          onChange={(e) => setEditingSubject({ ...editingSubject, weekly_hours: parseInt(e.target.value) || 3 })}
                          className="rounded-xl"
                        />
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      <Label>{t('description')}</Label>
                      <Textarea
                        value={editingSubject.description || ''}
                        onChange={(e) => setEditingSubject({ ...editingSubject, description: e.target.value })}
                        className="rounded-xl min-h-[80px]"
                      />
                    </div>
                  </div>
                )}
                
                <DialogFooter>
                  <Button variant="outline" onClick={() => setEditDialogOpen(false)} className="rounded-xl">
                    {t('cancel')}
                  </Button>
                  <Button 
                    onClick={handleEditSubject} 
                    className="bg-brand-navy rounded-xl" 
                    disabled={submitting}
                  >
                    {submitting ? (
                      <><Loader2 className="h-4 w-4 animate-spin me-2" />{t('updating')}</>
                    ) : (
                      t('saveChanges2')
                    )}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>

          {/* Subjects Table */}
          <Card className="card-nassaq">
            <CardContent className="p-0">
              {loading ? (
                <div className="flex items-center justify-center py-20">
                  <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
                </div>
              ) : (
                <div className="rounded-xl overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('subject')}</TableHead>
                        <TableHead>{t('code')}</TableHead>
                        <TableHead>{t('category')}</TableHead>
                        <TableHead>{t('school')}</TableHead>
                        <TableHead>{t('hours')}</TableHead>
                        <TableHead>{t('status2')}</TableHead>
                        <TableHead className="w-12"></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredSubjects.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={7} className="text-center py-12 text-muted-foreground">
                            <Library className="h-12 w-12 mx-auto mb-4 opacity-20" />
                            <p>{t('noSubjectsFound')}</p>
                          </TableCell>
                        </TableRow>
                      ) : (
                        filteredSubjects.map((subject) => (
                          <TableRow key={subject.id} data-testid={`subject-row-${subject.id}`}>
                            <TableCell>
                              <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-full bg-brand-purple/10 flex items-center justify-center">
                                  <BookMarked className="h-5 w-5 text-brand-purple" />
                                </div>
                                <div>
                                  <div className="font-medium">{subject.name}</div>
                                  {subject.name_en && (
                                    <div className="text-sm text-muted-foreground">{subject.name_en}</div>
                                  )}
                                </div>
                              </div>
                            </TableCell>
                            <TableCell>
                              <Badge variant="outline" className="rounded-lg font-mono">
                                {subject.code || '-'}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              <Badge className={`rounded-lg ${getCategoryColor(subject.category)}`}>
                                {getCategoryLabel(subject.category)}
                              </Badge>
                            </TableCell>
                            <TableCell>{getSchoolName(subject.school_id)}</TableCell>
                            <TableCell>
                              <div className="flex items-center gap-1 text-sm">
                                <Clock className="h-4 w-4 text-brand-turquoise" />
                                {subject.weekly_hours || 3} {t('hweek')}
                              </div>
                            </TableCell>
                            <TableCell>
                              <Badge className={subject.is_active !== false ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}>
                                {subject.is_active !== false ? (t('active')) : (t('inactive'))}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button variant="ghost" size="icon">
                                    <MoreHorizontal className="h-4 w-4" />
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end">
                                  <DropdownMenuItem onClick={() => openEditDialog(subject)}>
                                    <Edit className="h-4 w-4 me-2" />
                                    {t('edit')}
                                  </DropdownMenuItem>
                                  <DropdownMenuItem 
                                    className="text-red-600"
                                    disabled={deletingId === subject.id}
                                    onClick={() => handleDeleteSubject(subject)}
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

          {/* Task #645 — Recently deleted subjects (soft-deleted rows
              restorable via POST /subjects/{id}/restore). Only rendered
              when there is at least one such row. */}
          {deletedSubjects.length > 0 && (
            <Card className="card-nassaq border-red-200" data-testid="recently-deleted-subjects-card">
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
                        {isRTL ? 'المواد المحذوفة حديثاً' : 'Recently deleted subjects'}
                      </div>
                      <div className="text-sm text-muted-foreground font-tajawal">
                        {isRTL
                          ? `${deletedSubjects.length} مادة قابلة للاستعادة`
                          : `${deletedSubjects.length} subject${deletedSubjects.length === 1 ? '' : 's'} can be restored`}
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
                          <TableHead>{t('subject')}</TableHead>
                          <TableHead>{isRTL ? 'حُذف بواسطة' : 'Deleted by'}</TableHead>
                          <TableHead>{isRTL ? 'تاريخ الحذف' : 'Deleted at'}</TableHead>
                          {!isSchoolLevel && <TableHead>{t('school')}</TableHead>}
                          <TableHead className="w-32"></TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {deletedSubjects.map((subject) => (
                          <TableRow
                            key={subject.id}
                            data-testid={`deleted-subject-row-${subject.id}`}
                          >
                            <TableCell>
                              <div className="flex items-center gap-3">
                                <div className="w-9 h-9 rounded-full bg-red-50 flex items-center justify-center">
                                  <BookMarked className="h-4 w-4 text-red-600" aria-hidden="true" strokeWidth={1.5} />
                                </div>
                                <div>
                                  <div className="font-medium">{subject.name}</div>
                                  <div className="text-xs text-muted-foreground">{subject.code || subject.name_en || ''}</div>
                                </div>
                              </div>
                            </TableCell>
                            <TableCell className="text-sm">
                              {subject.deleted_by_name
                                || (subject.deleted_by ? (isRTL ? 'مستخدم محذوف' : 'Unknown user') : '-')}
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              {formatDeletedAt(subject.deleted_at)}
                            </TableCell>
                            {!isSchoolLevel && (
                              <TableCell>{getSchoolName(subject.school_id)}</TableCell>
                            )}
                            <TableCell>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleRestoreSubject(subject)}
                                disabled={restoringId === subject.id}
                                className="rounded-xl border-brand-turquoise text-brand-turquoise hover:bg-brand-turquoise/10"
                                data-testid={`restore-subject-${subject.id}`}
                              >
                                {restoringId === subject.id ? (
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
      <HakimAssistant />
    </Sidebar>
  );
};
