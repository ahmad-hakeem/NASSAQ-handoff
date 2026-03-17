// =============================================================
// صفحة إعدادات المدرسة - School Settings Page
// الصفحة المرجعية الأساسية داخل حساب مدير المدرسة
// مصدر جميع البيانات المستخدمة في صفحة الجدول المدرسي
// =============================================================

import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { Sidebar } from '../components/layout/Sidebar';
import { HakimAssistant } from '../components/hakim/HakimAssistant';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { ScrollArea } from '../components/ui/scroll-area';
import { Separator } from '../components/ui/separator';
import { Switch } from '../components/ui/switch';
import { Textarea } from '../components/ui/textarea';
import { Avatar, AvatarFallback } from '../components/ui/avatar';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '../components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../components/ui/alert-dialog';
import {
  Settings,
  Users,
  GraduationCap,
  BookOpen,
  Calendar,
  Clock,
  Coffee,
  Activity,
  Target,
  CheckCircle2,
  AlertTriangle,
  Plus,
  Minus,
  Edit2,
  Trash2,
  Save,
  RefreshCw,
  ChevronRight,
  CalendarDays,
  School,
  UserPlus,
  Layers,
  Grid3X3,
  Building2,
  FileText,
  Loader2,
  X,
  Phone,
  Mail,
  MapPin,
  Globe,
  Sun,
  Moon,
  Eye,
  Shield,
  CalendarClock,
  ListChecks,
  Briefcase,
  Timer,
  XCircle,
} from 'lucide-react';

// Wizards
import { AddTeacherWizard } from '../components/wizards/AddTeacherWizard';
import AddStudentWizard from '../components/wizards/AddStudentWizard';
import { CreateClassWizard } from '../components/wizards/CreateClassWizard';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// =============================================================
// قسم معلومات المدرسة الأساسية
// =============================================================
const SchoolInfoSection = ({ schoolInfo, onSave, loading, isRTL }) => {
  const [info, setInfo] = useState(schoolInfo || {});
  const [saving, setSaving] = useState(false);

  const { nassaqError, nassaqWarning } = useNassaqAlert();
  useEffect(() => {
    if (schoolInfo) setInfo(schoolInfo);
  }, [schoolInfo]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(info);
      toast.success(isRTL ? 'تم حفظ معلومات المدرسة بنجاح' : 'School info saved successfully');
    } catch (error) {
      nassaqError(isRTL ? 'خطأ في حفظ المعلومات' : 'Error saving info');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="border-2 border-brand-navy/20 bg-gradient-to-br from-brand-navy/5 to-white" data-testid="school-info-section">
      <CardHeader>
        <div className="flex items-center gap-3 flex-row-reverse">
          <div className="w-14 h-14 rounded-2xl bg-brand-navy flex items-center justify-center">
            <Building2 className="h-7 w-7 text-white" />
          </div>
          <div className="text-right flex-1">
            <CardTitle className="font-cairo text-xl">{isRTL ? 'معلومات المدرسة' : 'School Information'}</CardTitle>
            <CardDescription>
              {isRTL ? 'البيانات الأساسية للمدرسة - أي تعديل هنا ينعكس على النظام بالكامل' : 'Basic school data - changes reflect system-wide'}
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {loading ? (
          <div className="py-8 text-center">
            <Loader2 className="h-8 w-8 animate-spin mx-auto text-brand-navy" />
          </div>
        ) : (
          <>
            <div className="grid md:grid-cols-2 gap-6">
              {/* School Name Arabic */}
              <div className="space-y-2">
                <Label className="flex items-center gap-2 flex-row-reverse justify-end">
                  <span>{isRTL ? 'اسم المدرسة بالعربية' : 'School Name (Arabic)'}</span>
                  <span className="text-red-500">*</span>
                </Label>
                <Input
                  value={info.name || ''}
                  onChange={(e) => setInfo({ ...info, name: e.target.value })}
                  placeholder={isRTL ? 'مثال: مدرسة النور' : 'e.g., Al-Noor School'}
                  className="text-right"
                  dir="rtl"
                />
              </div>
              
              {/* School Name English */}
              <div className="space-y-2">
                <Label className="flex items-center gap-2 flex-row-reverse justify-end">
                  <span>{isRTL ? 'اسم المدرسة بالإنجليزية' : 'School Name (English)'}</span>
                </Label>
                <Input
                  value={info.name_en || ''}
                  onChange={(e) => setInfo({ ...info, name_en: e.target.value })}
                  placeholder="e.g., Al-Noor School"
                  dir="ltr"
                />
              </div>
              
              {/* Email */}
              <div className="space-y-2">
                <Label className="flex items-center gap-2 flex-row-reverse justify-end">
                  <Mail className="h-4 w-4 text-muted-foreground" />
                  <span>{isRTL ? 'البريد الإلكتروني' : 'Email'}</span>
                </Label>
                <Input
                  type="email"
                  value={info.email || ''}
                  onChange={(e) => setInfo({ ...info, email: e.target.value })}
                  placeholder="school@example.com"
                  dir="ltr"
                />
              </div>
              
              {/* Phone */}
              <div className="space-y-2">
                <Label className="flex items-center gap-2 flex-row-reverse justify-end">
                  <Phone className="h-4 w-4 text-muted-foreground" />
                  <span>{isRTL ? 'رقم الهاتف' : 'Phone'}</span>
                </Label>
                <Input
                  value={info.phone || ''}
                  onChange={(e) => setInfo({ ...info, phone: e.target.value })}
                  placeholder="+966 XX XXX XXXX"
                  dir="ltr"
                />
              </div>
              
              {/* City */}
              <div className="space-y-2">
                <Label className="flex items-center gap-2 flex-row-reverse justify-end">
                  <MapPin className="h-4 w-4 text-muted-foreground" />
                  <span>{isRTL ? 'المدينة' : 'City'}</span>
                </Label>
                <Input
                  value={info.city || ''}
                  onChange={(e) => setInfo({ ...info, city: e.target.value })}
                  placeholder={isRTL ? 'الرياض' : 'Riyadh'}
                  className="text-right"
                  dir="rtl"
                />
              </div>
              
              {/* Region */}
              <div className="space-y-2">
                <Label className="flex items-center gap-2 flex-row-reverse justify-end">
                  <span>{isRTL ? 'المنطقة' : 'Region'}</span>
                </Label>
                <Input
                  value={info.region || ''}
                  onChange={(e) => setInfo({ ...info, region: e.target.value })}
                  placeholder={isRTL ? 'منطقة الرياض' : 'Riyadh Region'}
                  className="text-right"
                  dir="rtl"
                />
              </div>
              
              {/* Address */}
              <div className="space-y-2 md:col-span-2">
                <Label className="flex items-center gap-2 flex-row-reverse justify-end">
                  <span>{isRTL ? 'العنوان' : 'Address'}</span>
                </Label>
                <Textarea
                  value={info.address || ''}
                  onChange={(e) => setInfo({ ...info, address: e.target.value })}
                  placeholder={isRTL ? 'العنوان الكامل للمدرسة' : 'Full school address'}
                  className="text-right"
                  dir="rtl"
                  rows={2}
                />
              </div>
            </div>
            
            <Separator />
            
            <Button 
              onClick={handleSave} 
              disabled={saving}
              className="bg-brand-navy hover:bg-brand-navy/90"
            >
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin me-2" />
              ) : (
                <Save className="h-4 w-4 me-2" />
              )}
              {isRTL ? 'حفظ المعلومات' : 'Save Information'}
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
};

// =============================================================
// قسم بيانات المعلمين
// =============================================================
const TeachersSection = ({ teachers, loading, onRefresh, onAddTeacher, onEditTeacher, isRTL }) => {
  return (
    <Card className="border-2 border-blue-200 bg-gradient-to-br from-blue-50/50 to-white" data-testid="teachers-section">
      <CardHeader>
        <div className="flex items-center justify-between flex-row-reverse">
          <div className="flex items-center gap-3 flex-row-reverse">
            <div className="w-12 h-12 rounded-xl bg-blue-100 flex items-center justify-center">
              <GraduationCap className="h-6 w-6 text-blue-600" />
            </div>
            <div className="text-right">
              <CardTitle className="font-cairo">{isRTL ? 'بيانات المعلمين' : 'Teachers Data'}</CardTitle>
              <CardDescription>
                {isRTL ? 'المعلمين المسجلين - متاحين لمحرك الجدولة' : 'Registered teachers - Available for scheduling'}
              </CardDescription>
            </div>
          </div>
          <Badge variant="outline" className="text-lg px-4 py-2 bg-blue-100 text-blue-700">
            {teachers.length} {isRTL ? 'معلم' : 'Teachers'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex gap-3 mb-4 flex-wrap">
          <Button 
            onClick={onAddTeacher}
            className="bg-blue-600 hover:bg-blue-700"
            data-testid="add-teacher-settings-btn"
          >
            <UserPlus className="h-4 w-4 me-2" />
            {isRTL ? 'معلم / معلمين' : 'Teacher(s)'}
          </Button>
          <Button variant="outline" onClick={onRefresh} size="icon">
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
        
        {loading ? (
          <div className="py-8 text-center">
            <Loader2 className="h-8 w-8 animate-spin mx-auto text-blue-600" />
          </div>
        ) : teachers.length === 0 ? (
          <div className="py-12 text-center border-2 border-dashed border-blue-200 rounded-xl">
            <GraduationCap className="h-16 w-16 mx-auto mb-4 text-blue-200" />
            <h3 className="font-bold text-lg mb-2">{isRTL ? 'لا يوجد معلمين' : 'No Teachers'}</h3>
            <p className="text-muted-foreground mb-4">{isRTL ? 'قم بإضافة المعلمين ليصبحوا متاحين للجدولة' : 'Add teachers to make them available for scheduling'}</p>
            <Button onClick={onAddTeacher} variant="outline" className="border-blue-300 text-blue-600 hover:bg-blue-50">
              <Plus className="h-4 w-4 me-2" />
              {isRTL ? 'معلم / معلمين' : 'Teacher(s)'}
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 max-h-[400px] overflow-y-auto">
            {teachers.map((teacher) => (
              <div 
                key={teacher.id} 
                className="p-3 rounded-xl border bg-white hover:border-blue-300 hover:shadow-md transition-all cursor-pointer group"
                onClick={() => onEditTeacher(teacher)}
              >
                <div className="flex items-center gap-3 flex-row-reverse">
                  <Avatar className="h-10 w-10">
                    <AvatarFallback className="bg-blue-100 text-blue-700 font-bold">
                      {teacher.full_name?.charAt(0)}
                    </AvatarFallback>
                  </Avatar>
                  <div className="flex-1 text-right">
                    <p className="font-medium text-sm">{teacher.full_name}</p>
                    <p className="text-xs text-muted-foreground">{teacher.subject || teacher.specialization || (isRTL ? 'غير محدد' : 'Not specified')}</p>
                  </div>
                  <Button variant="ghost" size="icon" className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Edit2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// =============================================================
// قسم بيانات الفصول
// =============================================================
const ClassesSection = ({ classes, loading, onRefresh, onAddClass, onEditClass, isRTL }) => {
  return (
    <Card className="border-2 border-purple-200 bg-gradient-to-br from-purple-50/50 to-white" data-testid="classes-section">
      <CardHeader>
        <div className="flex items-center justify-between flex-row-reverse">
          <div className="flex items-center gap-3 flex-row-reverse">
            <div className="w-12 h-12 rounded-xl bg-purple-100 flex items-center justify-center">
              <School className="h-6 w-6 text-purple-600" />
            </div>
            <div className="text-right">
              <CardTitle className="font-cairo">{isRTL ? 'بيانات الفصول' : 'Classes Data'}</CardTitle>
              <CardDescription>
                {isRTL ? 'الفصول المسجلة - متاحة لمحرك الجدولة' : 'Registered classes - Available for scheduling'}
              </CardDescription>
            </div>
          </div>
          <Badge variant="outline" className="text-lg px-4 py-2 bg-purple-100 text-purple-700">
            {classes.length} {isRTL ? 'فصل' : 'Classes'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex gap-3 mb-4 flex-wrap">
          <Button 
            onClick={onAddClass}
            className="bg-purple-600 hover:bg-purple-700"
            data-testid="add-class-settings-btn"
          >
            <Plus className="h-4 w-4 me-2" />
            {isRTL ? 'فصل / فصول' : 'Class(es)'}
          </Button>
          <Button variant="outline" onClick={onRefresh} size="icon">
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
        
        {loading ? (
          <div className="py-8 text-center">
            <Loader2 className="h-8 w-8 animate-spin mx-auto text-purple-600" />
          </div>
        ) : classes.length === 0 ? (
          <div className="py-12 text-center border-2 border-dashed border-purple-200 rounded-xl">
            <School className="h-16 w-16 mx-auto mb-4 text-purple-200" />
            <h3 className="font-bold text-lg mb-2">{isRTL ? 'لا يوجد فصول' : 'No Classes'}</h3>
            <p className="text-muted-foreground mb-4">{isRTL ? 'قم بإضافة الفصول ليتم ربطها بالجدول' : 'Add classes to link them to the schedule'}</p>
            <Button onClick={onAddClass} variant="outline" className="border-purple-300 text-purple-600 hover:bg-purple-50">
              <Plus className="h-4 w-4 me-2" />
              {isRTL ? 'فصل / فصول' : 'Class(es)'}
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 max-h-[300px] overflow-y-auto">
            {classes.map((cls) => (
              <div 
                key={cls.id} 
                className="p-3 rounded-xl border bg-white hover:border-purple-300 hover:shadow-md transition-all cursor-pointer text-center group"
                onClick={() => onEditClass(cls)}
              >
                <div className="w-12 h-12 rounded-full bg-purple-100 flex items-center justify-center mx-auto mb-2">
                  <span className="text-purple-700 font-bold text-sm">{cls.grade}{cls.section}</span>
                </div>
                <p className="font-medium text-sm">{cls.name}</p>
                <p className="text-xs text-muted-foreground">{cls.student_count || 0} {isRTL ? 'طالب' : 'students'}</p>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// =============================================================
// قسم المواد الدراسية
// =============================================================
const SubjectsSection = ({ subjects, grades, loading, onAddSubject, onDeleteSubject, isRTL }) => {
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(null);
  const [selectedGrade, setSelectedGrade] = useState('');
  const [newSubjectName, setNewSubjectName] = useState('');
  const [newSubjectNameEn, setNewSubjectNameEn] = useState('');
  const [weeklyPeriods, setWeeklyPeriods] = useState(4);

  const handleAddSubject = () => {
    if (!newSubjectName) {
      nassaqError(isRTL ? 'يرجى إدخال اسم المادة' : 'Please enter subject name');
      return;
    }
    onAddSubject({
      grade_id: selectedGrade,
      name: newSubjectName,
      name_en: newSubjectNameEn,
      weekly_periods: weeklyPeriods,
    });
    setShowAddDialog(false);
    setNewSubjectName('');
    setNewSubjectNameEn('');
    setWeeklyPeriods(4);
    setSelectedGrade('');
  };

  const handleConfirmDelete = (subject) => {
    setShowDeleteConfirm(subject);
  };

  const handleDelete = () => {
    if (showDeleteConfirm) {
      onDeleteSubject(showDeleteConfirm);
      setShowDeleteConfirm(null);
    }
  };

  return (
    <Card className="border-2 border-emerald-200 bg-gradient-to-br from-emerald-50/50 to-white" data-testid="subjects-section">
      <CardHeader>
        <div className="flex items-center justify-between flex-row-reverse">
          <div className="flex items-center gap-3 flex-row-reverse">
            <div className="w-12 h-12 rounded-xl bg-emerald-100 flex items-center justify-center">
              <BookOpen className="h-6 w-6 text-emerald-600" />
            </div>
            <div className="text-right">
              <CardTitle className="font-cairo">{isRTL ? 'المواد الدراسية' : 'Subjects'}</CardTitle>
              <CardDescription>
                {isRTL ? 'المواد المعتمدة - مدخلات محرك الجدولة' : 'Approved subjects - Scheduling inputs'}
              </CardDescription>
            </div>
          </div>
          <Badge variant="outline" className="text-lg px-4 py-2 bg-emerald-100 text-emerald-700">
            {subjects.length} {isRTL ? 'مادة' : 'Subjects'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <Button 
          onClick={() => setShowAddDialog(true)}
          className="bg-emerald-600 hover:bg-emerald-700 mb-4"
          data-testid="add-subject-btn"
        >
          <Plus className="h-4 w-4 me-2" />
          {isRTL ? 'إضافة مادة دراسية' : 'Add Subject'}
        </Button>

        {loading ? (
          <div className="py-8 text-center">
            <Loader2 className="h-8 w-8 animate-spin mx-auto text-emerald-600" />
          </div>
        ) : subjects.length === 0 ? (
          <div className="py-12 text-center border-2 border-dashed border-emerald-200 rounded-xl">
            <BookOpen className="h-16 w-16 mx-auto mb-4 text-emerald-200" />
            <h3 className="font-bold text-lg mb-2">{isRTL ? 'لا توجد مواد' : 'No Subjects'}</h3>
            <p className="text-muted-foreground">{isRTL ? 'قم بإضافة المواد الدراسية' : 'Add subjects'}</p>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2 max-h-[300px] overflow-y-auto">
            {subjects.map((subject) => (
              <Badge 
                key={subject.id} 
                variant="outline"
                className="px-3 py-2 text-sm bg-white hover:bg-emerald-50 cursor-pointer group flex items-center gap-2"
              >
                <span>{subject.name}</span>
                <span className="text-xs text-muted-foreground">({subject.weekly_periods || 4} {isRTL ? 'حصص' : 'periods'})</span>
                <button 
                  onClick={(e) => { e.stopPropagation(); handleConfirmDelete(subject); }}
                  className="opacity-0 group-hover:opacity-100 text-red-500 hover:text-red-700 transition-opacity"
                >
                  <XCircle className="h-4 w-4" />
                </button>
              </Badge>
            ))}
          </div>
        )}

        {/* Add Subject Dialog */}
        <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="text-right font-cairo">{isRTL ? 'إضافة مادة دراسية' : 'Add Subject'}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              {grades.length > 0 && (
                <div className="space-y-2">
                  <Label className="text-right block">{isRTL ? 'الصف (اختياري)' : 'Grade (Optional)'}</Label>
                  <Select value={selectedGrade} onValueChange={setSelectedGrade}>
                    <SelectTrigger>
                      <SelectValue placeholder={isRTL ? 'اختر الصف' : 'Select grade'} />
                    </SelectTrigger>
                    <SelectContent>
                      {grades.map((grade) => (
                        <SelectItem key={grade.id} value={grade.id}>{grade.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
              <div className="space-y-2">
                <Label className="text-right block">{isRTL ? 'اسم المادة بالعربية' : 'Subject Name (Arabic)'} <span className="text-red-500">*</span></Label>
                <Input 
                  value={newSubjectName}
                  onChange={(e) => setNewSubjectName(e.target.value)}
                  placeholder={isRTL ? 'مثال: الرياضيات' : 'e.g., Mathematics'}
                  className="text-right"
                  dir="rtl"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-right block">{isRTL ? 'اسم المادة بالإنجليزية' : 'Subject Name (English)'}</Label>
                <Input 
                  value={newSubjectNameEn}
                  onChange={(e) => setNewSubjectNameEn(e.target.value)}
                  placeholder="e.g., Mathematics"
                  dir="ltr"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-right block">{isRTL ? 'النصاب الأسبوعي' : 'Weekly Periods'}</Label>
                <Input 
                  type="number"
                  min="1"
                  max="10"
                  value={weeklyPeriods}
                  onChange={(e) => setWeeklyPeriods(parseInt(e.target.value) || 4)}
                />
              </div>
            </div>
            <DialogFooter className="flex gap-2 flex-row-reverse">
              <Button variant="outline" onClick={() => setShowAddDialog(false)}>
                {isRTL ? 'إلغاء' : 'Cancel'}
              </Button>
              <Button onClick={handleAddSubject} className="bg-emerald-600 hover:bg-emerald-700">
                <Plus className="h-4 w-4 me-2" />
                {isRTL ? 'إضافة' : 'Add'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Delete Confirmation Dialog */}
        <AlertDialog open={!!showDeleteConfirm} onOpenChange={() => setShowDeleteConfirm(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle className="text-right font-cairo">
                {isRTL ? 'هل تريد حذف هذه المادة؟' : 'Delete this subject?'}
              </AlertDialogTitle>
              <AlertDialogDescription className="text-right">
                {isRTL 
                  ? `سيتم حذف المادة "${showDeleteConfirm?.name}" نهائياً. هذا الإجراء لا يمكن التراجع عنه.`
                  : `The subject "${showDeleteConfirm?.name}" will be permanently deleted. This action cannot be undone.`
                }
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter className="flex gap-2 flex-row-reverse">
              <AlertDialogCancel>{isRTL ? 'لا' : 'No'}</AlertDialogCancel>
              <AlertDialogAction onClick={handleDelete} className="bg-red-600 hover:bg-red-700">
                {isRTL ? 'نعم، احذف' : 'Yes, Delete'}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </CardContent>
    </Card>
  );
};

// =============================================================
// قسم أيام العمل
// =============================================================
const WorkDaysSection = ({ workDays, officialHolidays, onSaveWorkDays, onAddHoliday, isRTL }) => {
  const [days, setDays] = useState(workDays || {
    sunday: true,
    monday: true,
    tuesday: true,
    wednesday: true,
    thursday: true,
    friday: false,
    saturday: false,
  });
  const [saving, setSaving] = useState(false);
  const [showHolidayDialog, setShowHolidayDialog] = useState(false);
  const [newHoliday, setNewHoliday] = useState({ name: '', start_date: '', end_date: '' });

  const dayNames = {
    sunday: isRTL ? 'الأحد' : 'Sunday',
    monday: isRTL ? 'الاثنين' : 'Monday',
    tuesday: isRTL ? 'الثلاثاء' : 'Tuesday',
    wednesday: isRTL ? 'الأربعاء' : 'Wednesday',
    thursday: isRTL ? 'الخميس' : 'Thursday',
    friday: isRTL ? 'الجمعة' : 'Friday',
    saturday: isRTL ? 'السبت' : 'Saturday',
  };

  const toggleDay = (day) => {
    setDays(prev => ({ ...prev, [day]: !prev[day] }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSaveWorkDays(days);
      toast.success(isRTL ? 'تم حفظ أيام العمل' : 'Work days saved');
    } catch (error) {
      nassaqError(isRTL ? 'خطأ في الحفظ' : 'Save error');
    } finally {
      setSaving(false);
    }
  };

  const handleAddHoliday = () => {
    if (!newHoliday.name || !newHoliday.start_date) {
      nassaqError(isRTL ? 'يرجى ملء جميع الحقول المطلوبة' : 'Please fill required fields');
      return;
    }
    onAddHoliday(newHoliday);
    setShowHolidayDialog(false);
    setNewHoliday({ name: '', start_date: '', end_date: '' });
  };

  const workingDaysCount = Object.values(days).filter(Boolean).length;

  return (
    <Card className="border-2 border-amber-200 bg-gradient-to-br from-amber-50/50 to-white" data-testid="workdays-section">
      <CardHeader>
        <div className="flex items-center justify-between flex-row-reverse">
          <div className="flex items-center gap-3 flex-row-reverse">
            <div className="w-12 h-12 rounded-xl bg-amber-100 flex items-center justify-center">
              <CalendarDays className="h-6 w-6 text-amber-600" />
            </div>
            <div className="text-right">
              <CardTitle className="font-cairo">{isRTL ? 'أيام العمل' : 'Work Days'}</CardTitle>
              <CardDescription>
                {isRTL ? 'تحديد أيام الدراسة والإجازات' : 'Define school days and holidays'}
              </CardDescription>
            </div>
          </div>
          <Badge variant="outline" className="px-4 py-2 bg-amber-100 text-amber-700">
            {workingDaysCount} {isRTL ? 'أيام دراسة' : 'School Days'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Week Days Grid */}
        <div>
          <Label className="mb-3 block text-right font-medium">{isRTL ? 'أيام الأسبوع الدراسية' : 'Weekly School Days'}</Label>
          <div className="grid grid-cols-7 gap-2">
            {Object.entries(dayNames).map(([key, name]) => (
              <div
                key={key}
                onClick={() => toggleDay(key)}
                className={`
                  p-4 rounded-xl text-center cursor-pointer transition-all border-2
                  ${days[key] 
                    ? 'bg-green-100 border-green-500 text-green-700 shadow-sm' 
                    : 'bg-gray-100 border-gray-300 text-gray-500 hover:border-gray-400'
                  }
                `}
              >
                <p className="font-bold text-sm">{name}</p>
                <p className="text-[10px] mt-1">
                  {days[key] ? (isRTL ? 'دراسة' : 'School') : (isRTL ? 'إجازة' : 'Off')}
                </p>
              </div>
            ))}
          </div>
        </div>

        <Separator />

        {/* Official Holidays */}
        <div>
          <div className="flex items-center justify-between mb-3 flex-row-reverse">
            <Label className="font-medium">{isRTL ? 'الإجازات الرسمية السنوية' : 'Official Annual Holidays'}</Label>
            <Button variant="outline" size="sm" onClick={() => setShowHolidayDialog(true)}>
              <Plus className="h-4 w-4 me-1" />
              {isRTL ? 'إضافة إجازة' : 'Add Holiday'}
            </Button>
          </div>
          
          {(!officialHolidays || officialHolidays.length === 0) ? (
            <div className="py-4 text-center text-muted-foreground border-2 border-dashed border-amber-200 rounded-xl">
              <Calendar className="h-8 w-8 mx-auto mb-2 text-amber-200" />
              <p className="text-sm">{isRTL ? 'لم يتم تحديد إجازات رسمية' : 'No official holidays defined'}</p>
            </div>
          ) : (
            <div className="space-y-2">
              {officialHolidays.map((holiday, index) => (
                <div key={index} className="p-3 bg-white rounded-lg border flex items-center justify-between flex-row-reverse">
                  <span className="font-medium">{holiday.name}</span>
                  <span className="text-sm text-muted-foreground">{holiday.start_date} - {holiday.end_date || holiday.start_date}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <Button onClick={handleSave} disabled={saving} className="bg-amber-600 hover:bg-amber-700">
          {saving ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Save className="h-4 w-4 me-2" />}
          {isRTL ? 'حفظ التغييرات' : 'Save Changes'}
        </Button>

        {/* Add Holiday Dialog */}
        <Dialog open={showHolidayDialog} onOpenChange={setShowHolidayDialog}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="text-right font-cairo">{isRTL ? 'إضافة إجازة رسمية' : 'Add Official Holiday'}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label className="text-right block">{isRTL ? 'اسم الإجازة' : 'Holiday Name'} <span className="text-red-500">*</span></Label>
                <Input
                  value={newHoliday.name}
                  onChange={(e) => setNewHoliday({ ...newHoliday, name: e.target.value })}
                  placeholder={isRTL ? 'مثال: عيد الفطر' : 'e.g., Eid Al-Fitr'}
                  className="text-right"
                  dir="rtl"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-right block">{isRTL ? 'تاريخ البداية' : 'Start Date'} <span className="text-red-500">*</span></Label>
                  <Input
                    type="date"
                    value={newHoliday.start_date}
                    onChange={(e) => setNewHoliday({ ...newHoliday, start_date: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-right block">{isRTL ? 'تاريخ النهاية' : 'End Date'}</Label>
                  <Input
                    type="date"
                    value={newHoliday.end_date}
                    onChange={(e) => setNewHoliday({ ...newHoliday, end_date: e.target.value })}
                  />
                </div>
              </div>
            </div>
            <DialogFooter className="flex gap-2 flex-row-reverse">
              <Button variant="outline" onClick={() => setShowHolidayDialog(false)}>
                {isRTL ? 'إلغاء' : 'Cancel'}
              </Button>
              <Button onClick={handleAddHoliday} className="bg-amber-600 hover:bg-amber-700">
                <Plus className="h-4 w-4 me-2" />
                {isRTL ? 'إضافة' : 'Add'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
};

// =============================================================
// قسم عدد الحصص في اليوم
// =============================================================
const PeriodsPerDaySection = ({ periodsPerDay, periodDuration, isRTL }) => {
  return (
    <Card className="border-2 border-cyan-200 bg-gradient-to-br from-cyan-50/50 to-white" data-testid="periods-section">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-3 flex-row-reverse">
          <div className="w-10 h-10 rounded-xl bg-cyan-100 flex items-center justify-center">
            <Grid3X3 className="h-5 w-5 text-cyan-600" />
          </div>
          <div className="text-right flex-1">
            <CardTitle className="font-cairo text-base">{isRTL ? 'عدد الحصص في اليوم' : 'Periods Per Day'}</CardTitle>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="flex items-center justify-between flex-row-reverse p-4 bg-cyan-50 rounded-xl">
          <div className="text-right">
            <div className="text-4xl font-bold text-cyan-700">{periodsPerDay || 7}</div>
            <div className="text-sm text-cyan-600 mt-1">{isRTL ? 'حصة يومياً' : 'periods/day'}</div>
          </div>
          <div className="text-right">
            <div className="text-lg font-semibold text-cyan-600">{periodDuration || 45} {isRTL ? 'دقيقة' : 'min'}</div>
            <div className="text-xs text-muted-foreground">{isRTL ? 'مدة الحصة' : 'per period'}</div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// =============================================================
// قسم بداية ونهاية اليوم الدراسي
// =============================================================
const SchoolTimingSection = ({ timing, isRTL }) => {
  return (
    <Card className="border-2 border-indigo-200 bg-gradient-to-br from-indigo-50/50 to-white" data-testid="timing-section">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-3 flex-row-reverse">
          <div className="w-10 h-10 rounded-xl bg-indigo-100 flex items-center justify-center">
            <Clock className="h-5 w-5 text-indigo-600" />
          </div>
          <div className="text-right flex-1">
            <CardTitle className="font-cairo text-base">{isRTL ? 'اليوم الدراسي' : 'School Day'}</CardTitle>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="flex items-center gap-4 p-4 bg-indigo-50 rounded-xl">
          <div className="flex-1 text-center p-3 bg-white rounded-lg border border-green-200">
            <Sun className="h-5 w-5 mx-auto mb-1 text-green-600" />
            <div className="text-xl font-bold text-green-700">{timing?.start || '07:00'}</div>
            <div className="text-xs text-muted-foreground">{isRTL ? 'بداية' : 'Start'}</div>
          </div>
          <ChevronRight className="h-5 w-5 text-indigo-400" />
          <div className="flex-1 text-center p-3 bg-white rounded-lg border border-orange-200">
            <Moon className="h-5 w-5 mx-auto mb-1 text-orange-600" />
            <div className="text-xl font-bold text-orange-700">{timing?.end || '13:15'}</div>
            <div className="text-xs text-muted-foreground">{isRTL ? 'نهاية' : 'End'}</div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// =============================================================
// قسم فترات الاستراحة
// =============================================================
const BreaksSection = ({ breaks, onSave, isRTL }) => {
  const [breaksList, setBreaksList] = useState(breaks || []);
  const [showDialog, setShowDialog] = useState(false);
  const [newBreak, setNewBreak] = useState({ start: '', end: '', name: '' });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (breaks) setBreaksList(breaks);
  }, [breaks]);

  const handleAddBreak = () => {
    if (!newBreak.start || !newBreak.end) {
      nassaqError(isRTL ? 'يرجى تحديد وقت البداية والنهاية' : 'Please set start and end times');
      return;
    }
    const updated = [...breaksList, { ...newBreak, id: Date.now().toString() }];
    setBreaksList(updated);
    setNewBreak({ start: '', end: '', name: '' });
    setShowDialog(false);
  };

  const handleRemoveBreak = (id) => {
    setBreaksList(breaksList.filter(b => b.id !== id));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(breaksList);
      toast.success(isRTL ? 'تم حفظ فترات الاستراحة' : 'Breaks saved');
    } catch (error) {
      nassaqError(isRTL ? 'خطأ في الحفظ' : 'Save error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="border-2 border-orange-200 bg-gradient-to-br from-orange-50/50 to-white" data-testid="breaks-section">
      <CardHeader>
        <div className="flex items-center justify-between flex-row-reverse">
          <div className="flex items-center gap-3 flex-row-reverse">
            <div className="w-12 h-12 rounded-xl bg-orange-100 flex items-center justify-center">
              <Coffee className="h-6 w-6 text-orange-600" />
            </div>
            <div className="text-right">
              <CardTitle className="font-cairo">{isRTL ? 'فترات الاستراحة' : 'Break Periods'}</CardTitle>
              <CardDescription>{isRTL ? 'تحديد أوقات الاستراحة خلال اليوم - تستثنى من الجدولة' : 'Define break times - excluded from scheduling'}</CardDescription>
            </div>
          </div>
          <Badge variant="outline" className="text-lg px-4 py-2 bg-orange-100 text-orange-700">
            {breaksList.length} {isRTL ? 'استراحة' : 'Breaks'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex gap-3 mb-4 flex-wrap">
          <Button onClick={() => setShowDialog(true)} className="bg-orange-600 hover:bg-orange-700">
            <Plus className="h-4 w-4 me-2" />
            {isRTL ? 'إضافة استراحة' : 'Add Break'}
          </Button>
          {breaksList.length > 0 && (
            <Button variant="outline" onClick={handleSave} disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Save className="h-4 w-4 me-2" />}
              {isRTL ? 'حفظ' : 'Save'}
            </Button>
          )}
        </div>

        {breaksList.length === 0 ? (
          <div className="py-8 text-center border-2 border-dashed border-orange-200 rounded-xl">
            <Coffee className="h-12 w-12 mx-auto mb-3 text-orange-200" />
            <p className="text-muted-foreground">{isRTL ? 'لا توجد فترات استراحة محددة (القيمة الافتراضية: صفر)' : 'No breaks defined (default: zero)'}</p>
          </div>
        ) : (
          <div className="space-y-2">
            {breaksList.map((breakItem) => (
              <div key={breakItem.id} className="flex items-center justify-between p-3 rounded-lg bg-white border hover:border-orange-300 transition-colors">
                <div className="flex items-center gap-3 flex-row-reverse">
                  <Badge variant="outline" className="font-mono">{breakItem.start} - {breakItem.end}</Badge>
                  {breakItem.name && <span className="text-sm font-medium">{breakItem.name}</span>}
                </div>
                <Button variant="ghost" size="icon" onClick={() => handleRemoveBreak(breakItem.id)} className="text-red-500 hover:text-red-700 hover:bg-red-50">
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>
        )}

        <Dialog open={showDialog} onOpenChange={setShowDialog}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="text-right font-cairo">{isRTL ? 'إضافة فترة استراحة' : 'Add Break'}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label className="text-right block">{isRTL ? 'اسم الاستراحة (اختياري)' : 'Break Name (Optional)'}</Label>
                <Input value={newBreak.name} onChange={(e) => setNewBreak({ ...newBreak, name: e.target.value })} placeholder={isRTL ? 'مثال: استراحة الفطور' : 'e.g., Breakfast break'} className="text-right" dir="rtl" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-right block">{isRTL ? 'البداية' : 'Start'} <span className="text-red-500">*</span></Label>
                  <Input type="time" value={newBreak.start} onChange={(e) => setNewBreak({ ...newBreak, start: e.target.value })} />
                </div>
                <div className="space-y-2">
                  <Label className="text-right block">{isRTL ? 'النهاية' : 'End'} <span className="text-red-500">*</span></Label>
                  <Input type="time" value={newBreak.end} onChange={(e) => setNewBreak({ ...newBreak, end: e.target.value })} />
                </div>
              </div>
            </div>
            <DialogFooter className="flex gap-2 flex-row-reverse">
              <Button variant="outline" onClick={() => setShowDialog(false)}>{isRTL ? 'إلغاء' : 'Cancel'}</Button>
              <Button onClick={handleAddBreak} className="bg-orange-600 hover:bg-orange-700">
                <Plus className="h-4 w-4 me-2" />
                {isRTL ? 'إضافة' : 'Add'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
};

// =============================================================
// قسم التوزيع الزمني الكامل لليوم الدراسي
// =============================================================
const TimeSlotsSection = ({ timeSlots, periodsPerDay, isRTL }) => {
  const slotTypeColors = {
    period: 'bg-blue-100 border-blue-300 text-blue-700',
    break: 'bg-orange-100 border-orange-300 text-orange-700',
    prayer: 'bg-green-100 border-green-300 text-green-700',
  };

  const slotTypeLabels = {
    period: isRTL ? 'حصة' : 'Period',
    break: isRTL ? 'استراحة' : 'Break',
    prayer: isRTL ? 'صلاة' : 'Prayer',
  };

  return (
    <Card className="border-2 border-purple-200 bg-gradient-to-br from-purple-50/50 to-white" data-testid="timeslots-section">
      <CardHeader>
        <div className="flex items-center justify-between flex-row-reverse">
          <div className="flex items-center gap-3 flex-row-reverse">
            <div className="w-12 h-12 rounded-xl bg-purple-100 flex items-center justify-center">
              <Timer className="h-6 w-6 text-purple-600" />
            </div>
            <div className="text-right">
              <CardTitle className="font-cairo">{isRTL ? 'التوزيع الزمني الكامل' : 'Complete Time Distribution'}</CardTitle>
              <CardDescription>
                {isRTL ? 'جدول الحصص والاستراحات وفترات الصلاة' : 'Schedule of periods, breaks, and prayer times'}
              </CardDescription>
            </div>
          </div>
          <Badge variant="outline" className="px-4 py-2 bg-purple-100 text-purple-700">
            {timeSlots?.length || 0} {isRTL ? 'فترة' : 'Slots'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        {timeSlots && timeSlots.length > 0 ? (
          <div className="space-y-2">
            {timeSlots.map((slot, index) => (
              <div 
                key={index}
                className={`flex items-center justify-between p-3 rounded-lg border-2 ${slotTypeColors[slot.type] || 'bg-gray-100 border-gray-300'}`}
              >
                <div className="flex items-center gap-3 flex-row-reverse">
                  <Badge variant="secondary" className="font-mono">
                    {slot.start_time} - {slot.end_time}
                  </Badge>
                  <span className="font-medium">{slot.name_ar || slot.name_en || slot.name}</span>
                </div>
                <Badge variant="outline" className="text-xs">
                  {slotTypeLabels[slot.type] || slot.type}
                </Badge>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            <Timer className="h-12 w-12 mx-auto mb-3 opacity-50" />
            <p>{isRTL ? 'لا يوجد توزيع زمني محدد' : 'No time slots defined'}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// =============================================================
// قسم النصاب التدريسي للمعلمين - من البيانات المرجعية
// =============================================================
const TeachingLoadSection = ({ teachers, teacherRanks, isRTL }) => {
  return (
    <Card className="border-2 border-teal-200 bg-gradient-to-br from-teal-50/50 to-white" data-testid="teaching-load-section">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-3 flex-row-reverse">
          <div className="w-10 h-10 rounded-xl bg-teal-100 flex items-center justify-center">
            <Target className="h-5 w-5 text-teal-600" />
          </div>
          <div className="text-right flex-1">
            <CardTitle className="font-cairo text-base">{isRTL ? 'النصاب التدريسي حسب الرتبة' : 'Teaching Load by Rank'}</CardTitle>
          </div>
          <Badge variant="outline" className="bg-teal-100 text-teal-700">
            {teacherRanks?.length || 0} {isRTL ? 'رتبة' : 'ranks'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        {teacherRanks && teacherRanks.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {teacherRanks.map((rank, index) => (
              <div key={index} className="flex items-center justify-between p-3 rounded-lg bg-teal-50 border border-teal-200">
                <span className="text-sm font-medium text-teal-800">{rank.name_ar || rank.name}</span>
                <Badge className="bg-teal-600 text-white">{rank.weekly_periods} {isRTL ? 'حصة' : 'periods'}</Badge>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-6 text-center border-2 border-dashed border-teal-200 rounded-xl">
            <Target className="h-10 w-10 mx-auto mb-2 text-teal-200" />
            <p className="text-sm text-muted-foreground">{isRTL ? 'لم يتم تحديد رتب المعلمين' : 'No teacher ranks defined'}</p>
          </div>
        )}
        
        {/* عرض المعلمين مع نصابهم الفعلي */}
        {teachers && teachers.length > 0 && (
          <div className="mt-4">
            <h4 className="text-sm font-semibold text-teal-700 mb-2">{isRTL ? 'المعلمون ونصابهم:' : 'Teachers & Load:'}</h4>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {teachers.map((teacher) => (
                <div key={teacher.id} className="p-2 rounded-lg bg-white border flex items-center justify-between flex-row-reverse">
                  <span className="text-xs font-medium truncate">{teacher.full_name}</span>
                  <Badge variant="outline" className="text-xs bg-teal-50">{teacher.weekly_periods || 24}</Badge>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// =============================================================
// قسم القيود الإدارية - من البيانات المرجعية
// =============================================================
const ConstraintsSection = ({ constraints, isRTL }) => {
  return (
    <Card className="border-2 border-rose-200 bg-gradient-to-br from-rose-50/50 to-white" data-testid="constraints-section">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-3 flex-row-reverse">
          <div className="w-10 h-10 rounded-xl bg-rose-100 flex items-center justify-center">
            <Shield className="h-5 w-5 text-rose-600" />
          </div>
          <div className="text-right flex-1">
            <CardTitle className="font-cairo text-base">{isRTL ? 'القيود الإدارية' : 'Administrative Constraints'}</CardTitle>
          </div>
          <Badge variant="outline" className="bg-rose-100 text-rose-700">
            {constraints?.length || 0} {isRTL ? 'قيد' : 'rules'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        {constraints && constraints.length > 0 ? (
          <div className="space-y-2">
            {constraints.map((constraint, index) => (
              <div key={index} className="flex items-start gap-3 p-3 rounded-lg bg-rose-50 border border-rose-200">
                <div className="w-6 h-6 rounded-full bg-rose-200 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-xs font-bold text-rose-700">{index + 1}</span>
                </div>
                <div className="flex-1 text-right">
                  <p className="text-sm font-medium text-rose-800">{constraint.name_ar || constraint.name}</p>
                  {constraint.description_ar && (
                    <p className="text-xs text-rose-600 mt-1">{constraint.description_ar}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-6 text-center border-2 border-dashed border-rose-200 rounded-xl">
            <Shield className="h-10 w-10 mx-auto mb-2 text-rose-200" />
            <p className="text-sm text-muted-foreground">{isRTL ? 'لا توجد قيود إدارية محددة' : 'No constraints defined'}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// =============================================================
// قسم أيام الأنشطة - مبسط
// =============================================================
const ActivityDaysSection = ({ activityDays, isRTL }) => {
  return (
    <Card className="border-2 border-pink-200 bg-gradient-to-br from-pink-50/50 to-white" data-testid="activity-days-section">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-3 flex-row-reverse">
          <div className="w-10 h-10 rounded-xl bg-pink-100 flex items-center justify-center">
            <Activity className="h-5 w-5 text-pink-600" />
          </div>
          <div className="text-right flex-1">
            <CardTitle className="font-cairo text-base">{isRTL ? 'أيام الأنشطة' : 'Activity Days'}</CardTitle>
          </div>
          <Badge variant="outline" className="bg-pink-100 text-pink-700">
            {activityDays?.length || 0} {isRTL ? 'يوم' : 'days'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        {activityDays && activityDays.length > 0 ? (
          <div className="space-y-2">
            {activityDays.map((activity, index) => (
              <div key={index} className="flex items-center justify-between p-3 rounded-lg bg-pink-50 border border-pink-200">
                <Badge variant="outline" className="font-mono">{activity.date}</Badge>
                <span className="text-sm font-medium text-pink-800">{activity.name}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-6 text-center bg-pink-50/50 rounded-xl">
            <Activity className="h-8 w-8 mx-auto mb-2 text-pink-300" />
            <p className="text-sm text-muted-foreground">{isRTL ? 'لا توجد أيام أنشطة محددة' : 'No activity days defined'}</p>
            <p className="text-xs text-pink-500 mt-1">{isRTL ? '(الأيام العادية فقط)' : '(Regular days only)'}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// =============================================================
// قسم التوافر - يعرض توافر المعلمين
// =============================================================
const AvailabilitySection = ({ teachers, isRTL }) => {
  const dayNames = {
    sunday: isRTL ? 'الأحد' : 'Sun',
    monday: isRTL ? 'الإثنين' : 'Mon',
    tuesday: isRTL ? 'الثلاثاء' : 'Tue',
    wednesday: isRTL ? 'الأربعاء' : 'Wed',
    thursday: isRTL ? 'الخميس' : 'Thu',
  };

  // Find teachers with availability exceptions
  const teachersWithExceptions = teachers?.filter(t => {
    const av = t.availability || {};
    return Object.values(av).some(periods => periods && periods.length < 7);
  }) || [];

  return (
    <Card className="border-2 border-amber-200 bg-gradient-to-br from-amber-50/50 to-white" data-testid="availability-section">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-3 flex-row-reverse">
          <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center">
            <CalendarClock className="h-5 w-5 text-amber-600" />
          </div>
          <div className="text-right flex-1">
            <CardTitle className="font-cairo text-base">{isRTL ? 'توافر المعلمين' : 'Teacher Availability'}</CardTitle>
          </div>
          <Badge variant="outline" className="bg-amber-100 text-amber-700">
            {teachersWithExceptions.length} {isRTL ? 'استثناء' : 'exceptions'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        {teachersWithExceptions.length > 0 ? (
          <div className="space-y-2">
            {teachersWithExceptions.map((teacher) => {
              const av = teacher.availability || {};
              const exceptions = Object.entries(av).filter(([day, periods]) => periods && periods.length < 7);
              return (
                <div key={teacher.id} className="p-3 rounded-lg bg-amber-50 border border-amber-200">
                  <div className="flex items-center justify-between flex-row-reverse mb-2">
                    <span className="text-sm font-medium text-amber-800">{teacher.full_name}</span>
                    <Badge variant="secondary" className="text-xs">{teacher.subject_name || teacher.specialization}</Badge>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {exceptions.map(([day, periods]) => {
                      const missingPeriods = [1,2,3,4,5,6,7].filter(p => !periods.includes(p));
                      return missingPeriods.map(p => (
                        <Badge key={`${day}-${p}`} variant="outline" className="text-xs bg-red-50 text-red-600 border-red-200">
                          {dayNames[day]} - {isRTL ? `ح${p}` : `P${p}`}
                        </Badge>
                      ));
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="py-6 text-center bg-amber-50/50 rounded-xl">
            <CheckCircle2 className="h-8 w-8 mx-auto mb-2 text-green-400" />
            <p className="text-sm text-muted-foreground">{isRTL ? 'جميع المعلمين متاحون في كل الأوقات' : 'All teachers available at all times'}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// =============================================================
// قسم الهيكل الأكاديمي - من البيانات المرجعية
// =============================================================
const AcademicStructureSection = ({ academicStructure, isRTL }) => {
  const [activeTab, setActiveTab] = useState('stages');
  
  const stages = academicStructure?.stages || [];
  const grades = academicStructure?.grades || [];
  const tracks = academicStructure?.tracks || [];

  return (
    <Card className="border-2 border-blue-200 bg-gradient-to-br from-blue-50/50 to-white" data-testid="academic-structure-section">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-3 flex-row-reverse">
          <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center">
            <GraduationCap className="h-5 w-5 text-blue-600" />
          </div>
          <div className="text-right flex-1">
            <CardTitle className="font-cairo text-base">{isRTL ? 'الهيكل الأكاديمي' : 'Academic Structure'}</CardTitle>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full" dir="rtl">
          <TabsList className="grid w-full grid-cols-3 mb-4">
            <TabsTrigger value="stages" className="text-xs">
              {isRTL ? 'المراحل' : 'Stages'} ({stages.length})
            </TabsTrigger>
            <TabsTrigger value="grades" className="text-xs">
              {isRTL ? 'الصفوف' : 'Grades'} ({grades.length})
            </TabsTrigger>
            <TabsTrigger value="tracks" className="text-xs">
              {isRTL ? 'المسارات' : 'Tracks'} ({tracks.length})
            </TabsTrigger>
          </TabsList>

          {/* المراحل */}
          <TabsContent value="stages">
            {stages.length > 0 ? (
              <div className="space-y-2">
                {stages.map((stage, index) => (
                  <div key={index} className="flex items-center justify-between p-3 rounded-lg bg-blue-50 border border-blue-200">
                    <div className="flex items-center gap-2">
                      <Badge className="bg-blue-600">{stage.order || index + 1}</Badge>
                      <span className="text-sm font-medium text-blue-800">{stage.name_ar || stage.name}</span>
                    </div>
                    <span className="text-xs text-muted-foreground">{stage.name_en}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-4 text-center text-muted-foreground text-sm">
                {isRTL ? 'لا توجد مراحل محددة' : 'No stages defined'}
              </div>
            )}
          </TabsContent>

          {/* الصفوف */}
          <TabsContent value="grades">
            {grades.length > 0 ? (
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {grades.map((grade, index) => (
                  <div key={index} className="flex items-center justify-between p-2 rounded-lg bg-green-50 border border-green-200">
                    <span className="text-sm font-medium text-green-800">{grade.name_ar || grade.name}</span>
                    <Badge variant="outline" className="text-xs">{grade.stage_name_ar || grade.stage_id}</Badge>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-4 text-center text-muted-foreground text-sm">
                {isRTL ? 'لا توجد صفوف محددة' : 'No grades defined'}
              </div>
            )}
          </TabsContent>

          {/* المسارات */}
          <TabsContent value="tracks">
            {tracks.length > 0 ? (
              <div className="space-y-2">
                {tracks.map((track, index) => (
                  <div key={index} className="flex items-center justify-between p-3 rounded-lg bg-purple-50 border border-purple-200">
                    <span className="text-sm font-medium text-purple-800">{track.name_ar || track.name}</span>
                    <span className="text-xs text-muted-foreground">{track.name_en}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-4 text-center text-muted-foreground text-sm">
                {isRTL ? 'لا توجد مسارات محددة' : 'No tracks defined'}
              </div>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
};
// =============================================================
// الصفحة الرئيسية
// =============================================================
export default function SchoolSettingsPage() {
  const navigate = useNavigate();
  const { user, token, api } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  
  // State
  const [loading, setLoading] = useState(true);
  const [schoolInfo, setSchoolInfo] = useState(null);
  const [teachers, setTeachers] = useState([]);
  const [classes, setClasses] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [grades, setGrades] = useState([]);
  const [settings, setSettings] = useState({
    workDays: { sunday: true, monday: true, tuesday: true, wednesday: true, thursday: true, friday: false, saturday: false },
    officialHolidays: [],
    periodsPerDay: 7,
    timing: { start: '07:00', end: '14:00' },
    breaks: [],
    teachingLoads: {},
    constraints: [],
  });
  
  // Wizard States
  const [showAddTeacherWizard, setShowAddTeacherWizard] = useState(false);
  const [showAddStudentWizard, setShowAddStudentWizard] = useState(false);
  const [showCreateClassWizard, setShowCreateClassWizard] = useState(false);

  // Fetch all data
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      // Fetch from the new comprehensive school settings API
      // Note: api already has baseURL with /api prefix
      const [teachersRes, classesRes, settingsRes] = await Promise.all([
        api.get('/teachers').catch(() => ({ data: [] })),
        api.get('/classes').catch(() => ({ data: [] })),
        api.get('/school/settings').catch(() => ({ data: {} })),
      ]);
      
      setTeachers(teachersRes.data || []);
      setClasses(classesRes.data || []);
      
      // Set data from school settings API
      const settingsData = settingsRes.data || {};
      setSchoolInfo(settingsData.school_info || null);
      
      // Get reference data
      const refData = settingsData.reference_data || {};
      const academicData = settingsData.academic_structure || {};
      
      setSubjects(refData.subjects || settingsData.subjects || []);
      setGrades(academicData.grades || settingsData.grades || []);
      
      // Get working days from settings
      const workingDays = settingsData.settings?.working_days || settingsData.working_days || { 
        sunday: true, monday: true, tuesday: true, wednesday: true, thursday: true, friday: false, saturday: false 
      };
      
      setSettings({
        workDays: workingDays,
        workDaysAr: settingsData.settings?.working_days_ar || [],
        workDaysEn: settingsData.settings?.working_days_en || [],
        weekendDaysAr: settingsData.settings?.weekend_days_ar || [],
        weekendDaysEn: settingsData.settings?.weekend_days_en || [],
        officialHolidays: settingsData.official_holidays || [],
        exceptionDays: settingsData.exception_days || [],
        periodsPerDay: settingsData.periods_per_day || 7,
        periodDuration: settingsData.settings?.period_duration_minutes || 45,
        breakDuration: settingsData.settings?.break_duration_minutes || 20,
        prayerDuration: settingsData.settings?.prayer_duration_minutes || 20,
        timing: { 
          start: settingsData.school_day_start || '07:00', 
          end: settingsData.school_day_end || '13:15' 
        },
        timeSlots: settingsData.time_slots || [],
        breaks: settingsData.breaks || [],
        activityDays: settingsData.activity_days || [],
        teachingLoads: settingsData.teaching_loads || {},
        teacherAvailability: settingsData.teacher_availability || {},
        constraints: refData.admin_constraints || settingsData.constraints || [],
        educationalStages: academicData.stages || settingsData.educational_stages || [],
        educationTracks: academicData.tracks || [],
        teacherRanks: refData.teacher_ranks || [],
        adminConstraints: refData.admin_constraints || [],
        academicStructure: academicData,
        sections: settingsData.school_classes || settingsData.sections || [],
        academicTerms: settingsData.academic_terms || [],
      });
    } catch (error) {
      console.error('Error fetching data:', error);
      nassaqError(isRTL ? 'خطأ في تحميل البيانات' : 'Error loading data');
    } finally {
      setLoading(false);
    }
  }, [api, user, isRTL]);

  useEffect(() => {
    fetchData();
  }, []);

  // Save handlers
  const handleSaveSchoolInfo = async (info) => {
    await api.put('/school/settings/info', info);
    setSchoolInfo(prev => ({ ...prev, ...info }));
  };

  const handleSaveWorkDays = async (workDays) => {
    await api.put('/school/settings/work-days', workDays);
    setSettings(prev => ({ ...prev, workDays }));
  };

  const handleSavePeriodsPerDay = async (periods) => {
    await api.put(`/school/settings/periods-per-day?periods=${periods}`);
    setSettings(prev => ({ ...prev, periodsPerDay: periods }));
  };

  const handleSaveTiming = async (timing) => {
    await api.put('/school/settings/timing', timing);
    setSettings(prev => ({ ...prev, timing }));
  };

  const handleSaveBreaks = async (breaks) => {
    await api.put('/school/settings/breaks', breaks);
    setSettings(prev => ({ ...prev, breaks }));
  };

  const handleSaveTeachingLoads = async (loads) => {
    await api.put('/school/settings/teaching-loads', loads);
    setSettings(prev => ({ ...prev, teachingLoads: loads }));
  };

  const handleSaveConstraints = async (constraints) => {
    await api.put('/school/settings/constraints', constraints);
    setSettings(prev => ({ ...prev, constraints }));
  };

  const handleAddSubject = async (subjectData) => {
    try {
      const response = await api.post('/school/settings/subjects', subjectData);
      const newSubject = response.data?.subject || subjectData;
      setSubjects(prev => [...prev, newSubject]);
      toast.success(isRTL ? 'تمت إضافة المادة بنجاح' : 'Subject added successfully');
    } catch (error) {
      nassaqError(isRTL ? 'خطأ في إضافة المادة' : 'Error adding subject');
      throw error;
    }
  };

  const handleDeleteSubject = async (subject) => {
    try {
      await api.delete(`/school/settings/subjects/${subject.id}`);
      setSubjects(prev => prev.filter(s => s.id !== subject.id));
      toast.success(isRTL ? 'تم حذف المادة' : 'Subject deleted');
    } catch (error) {
      nassaqError(isRTL ? 'خطأ في حذف المادة' : 'Error deleting subject');
      throw error;
    }
  };

  const handleAddHoliday = async (holiday) => {
    try {
      const response = await api.post('/school/settings/holidays', holiday);
      const newHoliday = response.data?.holiday || holiday;
      setSettings(prev => ({ 
        ...prev, 
        officialHolidays: [...(prev.officialHolidays || []), newHoliday] 
      }));
      toast.success(isRTL ? 'تمت إضافة الإجازة' : 'Holiday added');
    } catch (error) {
      nassaqError(isRTL ? 'خطأ في إضافة الإجازة' : 'Error adding holiday');
      throw error;
    }
  };

  const handleDeleteHoliday = async (holidayId) => {
    try {
      await api.delete(`/school/settings/holidays/${holidayId}`);
      setSettings(prev => ({
        ...prev,
        officialHolidays: prev.officialHolidays.filter(h => h.id !== holidayId)
      }));
      toast.success(isRTL ? 'تم حذف الإجازة' : 'Holiday deleted');
    } catch (error) {
      nassaqError(isRTL ? 'خطأ في حذف الإجازة' : 'Error deleting holiday');
    }
  };

  const handleAddExceptionDay = async (exceptionDay) => {
    try {
      const response = await api.post('/school/settings/exception-days', exceptionDay);
      const newException = response.data?.exception || exceptionDay;
      setSettings(prev => ({
        ...prev,
        exceptionDays: [...(prev.exceptionDays || []), newException]
      }));
      toast.success(isRTL ? 'تم إضافة يوم الاستثناء' : 'Exception day added');
    } catch (error) {
      nassaqError(isRTL ? 'خطأ في إضافة يوم الاستثناء' : 'Error adding exception day');
    }
  };

  const handleAddActivityDay = async (activityDay) => {
    try {
      const response = await api.post('/school/settings/activity-days', activityDay);
      const newActivity = response.data?.activity || activityDay;
      setSettings(prev => ({
        ...prev,
        activityDays: [...(prev.activityDays || []), newActivity]
      }));
      toast.success(isRTL ? 'تم إضافة يوم النشاط' : 'Activity day added');
    } catch (error) {
      nassaqError(isRTL ? 'خطأ في إضافة يوم النشاط' : 'Error adding activity day');
    }
  };

  const handleDeleteActivityDay = async (activityId) => {
    try {
      await api.delete(`/school/settings/activity-days/${activityId}`);
      setSettings(prev => ({
        ...prev,
        activityDays: prev.activityDays.filter(a => a.id !== activityId)
      }));
      toast.success(isRTL ? 'تم حذف يوم النشاط' : 'Activity day deleted');
    } catch (error) {
      nassaqError(isRTL ? 'خطأ في حذف يوم النشاط' : 'Error deleting activity day');
    }
  };

  // Academic structure handlers
  const handleAddStage = async (stage) => {
    try {
      const response = await api.post('/school/settings/stages', stage);
      const newStage = response.data?.stage || stage;
      setSettings(prev => ({
        ...prev,
        educationalStages: [...(prev.educationalStages || []), newStage]
      }));
      toast.success(isRTL ? 'تم إضافة المرحلة التعليمية' : 'Stage added');
    } catch (error) {
      nassaqError(isRTL ? 'خطأ في إضافة المرحلة' : 'Error adding stage');
    }
  };

  const handleDeleteStage = async (stageId) => {
    try {
      await api.delete(`/school/settings/stages/${stageId}`);
      setSettings(prev => ({
        ...prev,
        educationalStages: prev.educationalStages.filter(s => s.id !== stageId)
      }));
      toast.success(isRTL ? 'تم حذف المرحلة' : 'Stage deleted');
    } catch (error) {
      nassaqError(isRTL ? 'خطأ في حذف المرحلة' : 'Error deleting stage');
    }
  };

  const handleAddGrade = async (grade) => {
    try {
      const response = await api.post('/school/settings/grades', grade);
      const newGrade = response.data?.grade || grade;
      setGrades(prev => [...prev, newGrade]);
      toast.success(isRTL ? 'تم إضافة الصف' : 'Grade added');
    } catch (error) {
      nassaqError(isRTL ? 'خطأ في إضافة الصف' : 'Error adding grade');
    }
  };

  const handleDeleteGrade = async (gradeId) => {
    try {
      await api.delete(`/school/settings/grades/${gradeId}`);
      setGrades(prev => prev.filter(g => g.id !== gradeId));
      toast.success(isRTL ? 'تم حذف الصف' : 'Grade deleted');
    } catch (error) {
      nassaqError(isRTL ? 'خطأ في حذف الصف' : 'Error deleting grade');
    }
  };

  const handleAddSection = async (section) => {
    try {
      const response = await api.post('/school/settings/sections', section);
      const newSection = response.data?.section || section;
      setSettings(prev => ({
        ...prev,
        sections: [...(prev.sections || []), newSection]
      }));
      toast.success(isRTL ? 'تم إضافة الشعبة' : 'Section added');
    } catch (error) {
      nassaqError(isRTL ? 'خطأ في إضافة الشعبة' : 'Error adding section');
    }
  };

  const handleDeleteSection = async (sectionId) => {
    try {
      await api.delete(`/school/settings/sections/${sectionId}`);
      setSettings(prev => ({
        ...prev,
        sections: prev.sections.filter(s => s.id !== sectionId)
      }));
      toast.success(isRTL ? 'تم حذف الشعبة' : 'Section deleted');
    } catch (error) {
      nassaqError(isRTL ? 'خطأ في حذف الشعبة' : 'Error deleting section');
    }
  };

  const handleAddTerm = async (term) => {
    try {
      const response = await api.post('/school/settings/academic-terms', term);
      const newTerm = response.data?.term || term;
      setSettings(prev => ({
        ...prev,
        academicTerms: [...(prev.academicTerms || []), newTerm]
      }));
      toast.success(isRTL ? 'تم إضافة الفصل الدراسي' : 'Term added');
    } catch (error) {
      nassaqError(isRTL ? 'خطأ في إضافة الفصل' : 'Error adding term');
    }
  };

  const handleDeleteTerm = async (termId) => {
    try {
      await api.delete(`/school/settings/academic-terms/${termId}`);
      setSettings(prev => ({
        ...prev,
        academicTerms: prev.academicTerms.filter(t => t.id !== termId)
      }));
      toast.success(isRTL ? 'تم حذف الفصل الدراسي' : 'Term deleted');
    } catch (error) {
      nassaqError(isRTL ? 'خطأ في حذف الفصل' : 'Error deleting term');
    }
  };

  const handleSaveAvailability = async (data) => {
    try {
      await api.put('/school/settings/teacher-availability', data);
      setSettings(prev => ({
        ...prev,
        teacherAvailability: {
          ...(prev.teacherAvailability || {}),
          [data.teacher_id]: { available_days: data.available_days, available_periods: data.available_periods }
        }
      }));
      toast.success(isRTL ? 'تم حفظ توفر المعلم' : 'Availability saved');
    } catch (error) {
      nassaqError(isRTL ? 'خطأ في حفظ التوفر' : 'Error saving availability');
    }
  };

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-br from-background to-muted/20" data-testid="school-settings-page">
        {/* Header */}
        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-brand-navy flex items-center justify-center">
                <Settings className="h-6 w-6 text-white" />
              </div>
              <div>
                <h1 className="font-cairo text-2xl font-bold">
                  {isRTL ? `مرحباً، ${user?.full_name || 'المستخدم'}` : `Welcome, ${user?.full_name || 'User'}`}
                </h1>
                <p className="text-base text-muted-foreground font-tajawal">{isRTL ? 'إعدادات المدرسة' : 'School Settings'}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="icon" onClick={toggleLanguage}><Globe className="h-5 w-5" /></Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme}>{isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}</Button>
              <Button variant="outline" onClick={fetchData}><RefreshCw className={`h-4 w-4 me-2 ${loading ? 'animate-spin' : ''}`} />{isRTL ? 'تحديث' : 'Refresh'}</Button>
            </div>
          </div>
        </header>

        {/* Quick Actions */}
        <div className="px-6 py-4 border-b border-border/50 bg-gradient-to-r from-brand-navy/5 to-brand-turquoise/5">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-sm font-medium text-muted-foreground">{isRTL ? 'إجراءات سريعة:' : 'Quick Actions:'}</span>
            <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700" onClick={() => setShowAddStudentWizard(true)}><UserPlus className="h-4 w-4 me-2" />{isRTL ? 'طالب / طلاب' : 'Student(s)'}</Button>
            <Button size="sm" className="bg-blue-600 hover:bg-blue-700" onClick={() => setShowAddTeacherWizard(true)}><GraduationCap className="h-4 w-4 me-2" />{isRTL ? 'معلم / معلمين' : 'Teacher(s)'}</Button>
            <Button size="sm" className="bg-purple-600 hover:bg-purple-700" onClick={() => setShowCreateClassWizard(true)}><School className="h-4 w-4 me-2" />{isRTL ? 'فصل / فصول' : 'Class(es)'}</Button>
          </div>
        </div>

        {/* Main Content */}
        <main className="p-6 space-y-6">
          {/* Section 0: School Info - معلومات المدرسة */}
          <SchoolInfoSection schoolInfo={schoolInfo} onSave={handleSaveSchoolInfo} loading={loading} isRTL={isRTL} />

          {/* Section 1 & 2: Teachers and Classes - المعلمين والفصول */}
          <div className="grid lg:grid-cols-2 gap-6">
            <TeachersSection teachers={teachers} loading={loading} onRefresh={fetchData} onAddTeacher={() => setShowAddTeacherWizard(true)} onEditTeacher={() => {}} isRTL={isRTL} />
            <ClassesSection classes={classes} loading={loading} onRefresh={fetchData} onAddClass={() => setShowCreateClassWizard(true)} onEditClass={() => {}} isRTL={isRTL} />
          </div>

          {/* Section 3: Subjects - المواد الدراسية */}
          <SubjectsSection subjects={subjects} grades={grades} loading={loading} onAddSubject={handleAddSubject} onDeleteSubject={handleDeleteSubject} isRTL={isRTL} />

          {/* Section 4: Work Days - أيام العمل */}
          <WorkDaysSection 
            workDays={settings.workDays} 
            officialHolidays={settings.officialHolidays} 
            onSaveWorkDays={handleSaveWorkDays} 
            onAddHoliday={handleAddHoliday}
            onDeleteHoliday={handleDeleteHoliday}
            onAddExceptionDay={handleAddExceptionDay}
            isRTL={isRTL} 
          />

          {/* Section 5 & 6: Periods and Timing - الحصص وأوقات الدوام */}
          <div className="grid lg:grid-cols-2 gap-6">
            <PeriodsPerDaySection periodsPerDay={settings.periodsPerDay} periodDuration={settings.periodDuration} isRTL={isRTL} />
            <SchoolTimingSection timing={settings.timing} isRTL={isRTL} />
          </div>

          {/* Section 7: Breaks - فترات الاستراحة */}
          <BreaksSection breaks={settings.breaks} onSave={handleSaveBreaks} isRTL={isRTL} />

          {/* Section 7.5: Time Slots - التوزيع الزمني الكامل */}
          <TimeSlotsSection 
            timeSlots={settings.timeSlots} 
            periodsPerDay={settings.periodsPerDay}
            isRTL={isRTL} 
          />

          {/* Section 8: Activity Days - أيام الأنشطة */}
          <ActivityDaysSection 
            activityDays={settings.activityDays || []} 
            isRTL={isRTL} 
          />

          {/* Section 9: Teaching Load - النصاب التدريسي */}
          <TeachingLoadSection teachers={teachers} teacherRanks={settings.teacherRanks} isRTL={isRTL} />

          {/* Section 10: Availability - التوافر */}
          <AvailabilitySection 
            teachers={teachers} 
            isRTL={isRTL} 
          />

          {/* Section 11: Constraints - القيود الإدارية */}
          <ConstraintsSection constraints={settings.adminConstraints || []} isRTL={isRTL} />

          {/* Section 12-15: Academic Structure - الهيكل الأكاديمي */}
          <AcademicStructureSection 
            academicStructure={settings.academicStructure}
            isRTL={isRTL}
          />
        </main>

        {/* Wizards */}
        <AddTeacherWizard open={showAddTeacherWizard} onOpenChange={setShowAddTeacherWizard} onSuccess={fetchData} />
        <AddStudentWizard open={showAddStudentWizard} onOpenChange={setShowAddStudentWizard} isRTL={isRTL} api={api} grades={grades} classes={classes} onSuccess={fetchData} />
        <CreateClassWizard open={showCreateClassWizard} onOpenChange={setShowCreateClassWizard} onSuccess={fetchData} />
        
        {/* Hakim Assistant */}
        <HakimAssistant />
      </div>
    </Sidebar>
  );
}

// Export for backwards compatibility
export { SchoolSettingsPage };
