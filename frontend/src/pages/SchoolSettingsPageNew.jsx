/**
 * صفحة إعدادات المدرسة - التصميم الجديد الاحترافي
 * تعرض جميع البيانات من قاعدة البيانات مع إمكانية التعديل
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from '../components/layout/Sidebar';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { useLanguage } from '../contexts/LanguageContext';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';

// Shadcn UI Components
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { ScrollArea } from '../components/ui/scroll-area';
import { Separator } from '../components/ui/separator';

// Icons
import {
  Settings, Globe, Sun, Moon, RefreshCw, Save, Edit2, Plus, Trash2,
  Calendar, Clock, Users, BookOpen, GraduationCap, Shield, Target,
  ChevronRight, ChevronDown, Building2, MapPin, Phone, Mail,
  Grid3X3, Coffee, Play, CheckCircle2, AlertTriangle, Info,
  CalendarDays, Timer, Loader2, FileText, X
} from 'lucide-react';
import NotificationBell from '../components/NotificationBell';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// ============================================
// مكون كارت قابل للتوسيع
// ============================================
const ExpandableCard = ({ title, icon: Icon, iconColor, count, children, defaultExpanded = false, badge }) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  return (
    <Card className="border-2 hover:shadow-lg transition-all duration-300" data-testid={`card-${title}`}>
      <CardHeader 
        className="cursor-pointer select-none py-4"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl ${iconColor} flex items-center justify-center`}>
              <Icon className="h-5 w-5 text-white" />
            </div>
            <div>
              <CardTitle className="font-cairo text-base">{title}</CardTitle>
              {count !== undefined && (
                <CardDescription className="text-xs">{count} عنصر</CardDescription>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {badge && (
              <Badge variant="secondary" className="text-xs">{badge}</Badge>
            )}
            {isExpanded ? <ChevronDown className="h-5 w-5" /> : <ChevronRight className="h-5 w-5" />}
          </div>
        </div>
      </CardHeader>
      {isExpanded && (
        <CardContent className="pt-0 border-t">
          {children}
        </CardContent>
      )}
    </Card>
  );
};

// ============================================
// مكون عرض الأيام
// ============================================
const DaysDisplay = ({ days, type = "work" }) => {
  const dayColors = type === "work" 
    ? "bg-green-100 text-green-700 border-green-300" 
    : "bg-red-100 text-red-700 border-red-300";
    
  return (
    <div className="flex flex-wrap gap-2">
      {days.map((day, idx) => (
        <Badge key={idx} variant="outline" className={`${dayColors} px-3 py-1.5`}>
          {day}
        </Badge>
      ))}
    </div>
  );
};

// ============================================
// مكون عرض الفترات الزمنية
// ============================================
const TimeSlotCard = ({ slot, index }) => {
  const getSlotStyle = (type) => {
    switch(type) {
      case 'break': return 'bg-amber-50 border-amber-300 text-amber-800';
      case 'prayer': return 'bg-green-50 border-green-300 text-green-800';
      default: return 'bg-blue-50 border-blue-300 text-blue-800';
    }
  };
  
  const getSlotIcon = (type) => {
    switch(type) {
      case 'break': return <Coffee className="h-4 w-4" />;
      case 'prayer': return <Moon className="h-4 w-4" />;
      default: return <BookOpen className="h-4 w-4" />;
    }
  };
  
  return (
    <div className={`flex items-center justify-between p-3 rounded-lg border-2 ${getSlotStyle(slot.type || 'period')}`}>
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center border">
          {getSlotIcon(slot.type || 'period')}
        </div>
        <div>
          <p className="font-medium text-sm">{slot.name_ar || slot.name}</p>
          <p className="text-xs opacity-70">{slot.duration || slot.duration_minutes} دقيقة</p>
        </div>
      </div>
      <div className="text-left font-mono text-sm">
        <span className="font-bold">{slot.start_time}</span>
        <span className="mx-1">-</span>
        <span className="font-bold">{slot.end_time}</span>
      </div>
    </div>
  );
};

// ============================================
// مكون عرض المعلم
// ============================================
const TeacherCard = ({ teacher }) => (
  <div className="flex items-center justify-between p-3 rounded-lg bg-gradient-to-r from-violet-50 to-purple-50 border border-violet-200 hover:shadow-md transition-all">
    <div className="flex items-center gap-3">
      <div className="w-10 h-10 rounded-full bg-violet-100 flex items-center justify-center">
        <span className="text-violet-700 font-bold">{teacher.full_name?.charAt(0) || teacher.full_name_ar?.charAt(0) || 'م'}</span>
      </div>
      <div>
        <p className="font-medium text-sm text-violet-900">{teacher.full_name || teacher.full_name_ar}</p>
        <p className="text-xs text-violet-600">{teacher.subject_name || teacher.specialization}</p>
      </div>
    </div>
    <div className="text-left">
      <Badge variant="outline" className="bg-violet-100 text-violet-700 border-violet-300">
        {teacher.weekly_periods || 24} حصة
      </Badge>
      <p className="text-xs text-muted-foreground mt-1">{teacher.rank_name_ar || teacher.rank_name}</p>
    </div>
  </div>
);

// ============================================
// مكون عرض الفصل
// ============================================
const ClassCard = ({ classItem }) => (
  <div className="flex items-center justify-between p-3 rounded-lg bg-gradient-to-r from-cyan-50 to-teal-50 border border-cyan-200 hover:shadow-md transition-all">
    <div className="flex items-center gap-3">
      <div className="w-10 h-10 rounded-full bg-cyan-100 flex items-center justify-center">
        <GraduationCap className="h-5 w-5 text-cyan-700" />
      </div>
      <div>
        <p className="font-medium text-sm text-cyan-900">{classItem.name || classItem.name_ar}</p>
        <p className="text-xs text-cyan-600">{classItem.grade_name_ar || 'غير محدد'}</p>
      </div>
    </div>
    <Badge variant="outline" className="bg-cyan-100 text-cyan-700 border-cyan-300">
      {classItem.current_students || 0} طالب
    </Badge>
  </div>
);

// ============================================
// مكون عرض المادة
// ============================================
const SubjectCard = ({ subject }) => {
  const getCategoryColor = (category) => {
    switch(category) {
      case 'language': return 'bg-blue-100 text-blue-700 border-blue-300';
      case 'science': return 'bg-green-100 text-green-700 border-green-300';
      case 'islamic': return 'bg-emerald-100 text-emerald-700 border-emerald-300';
      case 'activity': return 'bg-orange-100 text-orange-700 border-orange-300';
      case 'social': return 'bg-purple-100 text-purple-700 border-purple-300';
      default: return 'bg-gray-100 text-gray-700 border-gray-300';
    }
  };
  
  return (
    <div className={`p-3 rounded-lg border ${getCategoryColor(subject.category)}`}>
      <div className="flex items-center justify-between">
        <span className="font-medium text-sm">{subject.name_ar}</span>
        <Badge variant="secondary" className="text-xs">{subject.weekly_periods} ح/أسبوع</Badge>
      </div>
    </div>
  );
};

// ============================================
// مكون عرض القيد الإداري
// ============================================
const ConstraintCard = ({ constraint, index }) => (
  <div className="flex items-start gap-3 p-3 rounded-lg bg-rose-50 border border-rose-200">
    <div className="w-6 h-6 rounded-full bg-rose-200 flex items-center justify-center flex-shrink-0 mt-0.5">
      <span className="text-xs font-bold text-rose-700">{index + 1}</span>
    </div>
    <div className="flex-1">
      <p className="font-medium text-sm text-rose-800">{constraint.name_ar}</p>
      <p className="text-xs text-rose-600 mt-1">{constraint.description_ar}</p>
      <div className="flex items-center gap-2 mt-2">
        <Badge 
          variant="outline" 
          className={`text-xs ${
            constraint.priority === 'critical' ? 'bg-red-100 text-red-700' :
            constraint.priority === 'high' ? 'bg-orange-100 text-orange-700' :
            'bg-yellow-100 text-yellow-700'
          }`}
        >
          {constraint.priority === 'critical' ? 'حرج' : constraint.priority === 'high' ? 'عالي' : 'متوسط'}
        </Badge>
        {constraint.is_active && (
          <Badge variant="outline" className="text-xs bg-green-100 text-green-700">
            <CheckCircle2 className="h-3 w-3 mr-1" /> مفعّل
          </Badge>
        )}
      </div>
    </div>
  </div>
);

// ============================================
// مكون رتبة المعلم
// ============================================
const RankCard = ({ rank }) => (
  <div className="flex items-center justify-between p-3 rounded-lg bg-teal-50 border border-teal-200">
    <div className="flex items-center gap-3">
      <Target className="h-5 w-5 text-teal-600" />
      <span className="font-medium text-sm text-teal-800">{rank.name_ar}</span>
    </div>
    <div className="flex items-center gap-2">
      <Badge className="bg-teal-600 text-white">{rank.weekly_periods} حصة/أسبوع</Badge>
      <Badge variant="outline" className="text-xs">{rank.daily_max} حد يومي</Badge>
    </div>
  </div>
);

// ============================================
// الصفحة الرئيسية
// ============================================
export default function SchoolSettingsPageNew() {
  const navigate = useNavigate();
  const { user, api } = useAuth();
  const { isDark, toggleTheme } = useTheme();
  const { isRTL, toggleLanguage } = useLanguage();
  
  // States
  const [loading, setLoading] = useState(true);
  const [schoolInfo, setSchoolInfo] = useState({});
  const [settings, setSettings] = useState({});
  const [teachers, setTeachers] = useState([]);
  const [classes, setClasses] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [teacherRanks, setTeacherRanks] = useState([]);
  const [constraints, setConstraints] = useState([]);
  const [academicStructure, setAcademicStructure] = useState({ stages: [], grades: [], tracks: [] });
  const [activeTab, setActiveTab] = useState('overview');
  
  // Fetch data
  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [
        settingsRes,
        teachersRes,
        classesRes,
        ranksRes,
        constraintsRes,
        stagesRes,
        gradesRes,
        tracksRes,
        subjectsRes
      ] = await Promise.all([
        api.get('/school/settings').catch(() => ({ data: {} })),
        api.get('/teachers').catch(() => ({ data: [] })),
        api.get('/classes').catch(() => ({ data: [] })),
        api.get('/reference/teacher-ranks').catch(() => ({ data: [] })),
        api.get('/reference/admin-constraints').catch(() => ({ data: [] })),
        api.get('/reference/stages').catch(() => ({ data: [] })),
        api.get('/reference/grades').catch(() => ({ data: [] })),
        api.get('/reference/tracks').catch(() => ({ data: [] })),
        api.get('/reference/subjects').catch(() => ({ data: [] })),
      ]);
      
      const settingsData = settingsRes.data;
      
      setSchoolInfo(settingsData.school_info || {});
      setSettings({
        workingDays: settingsData.settings?.working_days_ar || ['الأحد', 'الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس'],
        weekendDays: settingsData.settings?.weekend_days_ar || ['الجمعة', 'السبت'],
        periodsPerDay: settingsData.periods_per_day || 7,
        periodDuration: settingsData.settings?.period_duration_minutes || 45,
        breakDuration: settingsData.settings?.break_duration_minutes || 20,
        prayerDuration: settingsData.settings?.prayer_duration_minutes || 20,
        dayStart: settingsData.school_day_start || '07:00',
        dayEnd: settingsData.school_day_end || '13:15',
        timeSlots: settingsData.time_slots || [],
      });
      setTeachers(teachersRes.data || []);
      setClasses(classesRes.data || []);
      setTeacherRanks(ranksRes.data || []);
      setConstraints(constraintsRes.data || []);
      setAcademicStructure({
        stages: stagesRes.data || [],
        grades: gradesRes.data || [],
        tracks: tracksRes.data || [],
      });
      
      // Get unique subjects for this school's grades
      const schoolGrades = (classesRes.data || []).map(c => c.grade_id);
      const filteredSubjects = (subjectsRes.data || []).filter(s => 
        schoolGrades.includes(s.grade_id) || !s.grade_id
      );
      // Remove duplicates by name
      const uniqueSubjects = filteredSubjects.reduce((acc, curr) => {
        if (!acc.find(s => s.name_ar === curr.name_ar)) {
          acc.push(curr);
        }
        return acc;
      }, []);
      setSubjects(uniqueSubjects.slice(0, 15)); // Show first 15 unique subjects
      
    } catch (error) {
      console.error('Error fetching data:', error);
      nassaqError('خطأ في تحميل البيانات');
    } finally {
      setLoading(false);
    }
  }, [api]);
  
  useEffect(() => {
    fetchData();
  }, [fetchData]);
  
  if (loading) {
    return (
      <Sidebar>
        <div className="min-h-screen flex items-center justify-center">
          <div className="text-center">
            <Loader2 className="h-12 w-12 animate-spin mx-auto text-brand-navy" />
            <p className="mt-4 text-muted-foreground">جاري تحميل الإعدادات...</p>
          </div>
        </div>
      </Sidebar>
    );
  }
  
  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-br from-background via-muted/20 to-background" data-testid="school-settings-page">
        {/* Header */}
        <header className="sticky top-0 z-30 bg-background/80 backdrop-blur-lg border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-brand-navy to-brand-turquoise flex items-center justify-center shadow-lg">
                <Settings className="h-6 w-6 text-white" />
              </div>
              <div>
                <h1 className="font-cairo text-2xl font-bold text-foreground">
                  مرحباً، {user?.full_name || 'المستخدم'}
                </h1>
                <p className="text-base text-muted-foreground">إعدادات المدرسة</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="ghost" size="icon" onClick={toggleLanguage}>
                <Globe className="h-5 w-5" />
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme}>
                {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </Button>
              <Button variant="outline" onClick={fetchData} className="gap-2">
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                تحديث
              </Button>
              <NotificationBell />
            </div>
          </div>
        </header>
        
        {/* Main Content */}
        <main className="p-6 space-y-6 max-w-7xl mx-auto">
          
          {/* معلومات المدرسة */}
          <Card className="border-2 border-brand-navy/20 bg-gradient-to-r from-brand-navy/5 to-brand-turquoise/5">
            <CardContent className="p-6">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                  <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-navy to-brand-turquoise flex items-center justify-center shadow-lg">
                    <Building2 className="h-8 w-8 text-white" />
                  </div>
                  <div>
                    <h2 className="font-cairo text-xl font-bold">{schoolInfo.name || 'اسم المدرسة'}</h2>
                    <p className="text-sm text-muted-foreground">{schoolInfo.name_en || 'School Name'}</p>
                    <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <MapPin className="h-3 w-3" /> {schoolInfo.city || 'المدينة'}
                      </span>
                      <span className="flex items-center gap-1">
                        <Phone className="h-3 w-3" /> {schoolInfo.phone || '---'}
                      </span>
                      <span className="flex items-center gap-1">
                        <Mail className="h-3 w-3" /> {schoolInfo.email || '---'}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="flex gap-3">
                  <div className="text-center px-4 py-2 bg-violet-100 rounded-xl">
                    <p className="text-2xl font-bold text-violet-700">{teachers.length}</p>
                    <p className="text-xs text-violet-600">معلم</p>
                  </div>
                  <div className="text-center px-4 py-2 bg-cyan-100 rounded-xl">
                    <p className="text-2xl font-bold text-cyan-700">{classes.length}</p>
                    <p className="text-xs text-cyan-600">فصل</p>
                  </div>
                  <div className="text-center px-4 py-2 bg-emerald-100 rounded-xl">
                    <p className="text-2xl font-bold text-emerald-700">{subjects.length}</p>
                    <p className="text-xs text-emerald-600">مادة</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
          
          {/* Tabs Navigation */}
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full" dir="rtl">
            <TabsList className="grid w-full grid-cols-4 lg:grid-cols-8 mb-6">
              <TabsTrigger value="overview" className="text-xs">نظرة عامة</TabsTrigger>
              <TabsTrigger value="time" className="text-xs">التوقيت</TabsTrigger>
              <TabsTrigger value="teachers" className="text-xs">المعلمون</TabsTrigger>
              <TabsTrigger value="classes" className="text-xs">الفصول</TabsTrigger>
              <TabsTrigger value="subjects" className="text-xs">المواد</TabsTrigger>
              <TabsTrigger value="ranks" className="text-xs">الرتب</TabsTrigger>
              <TabsTrigger value="constraints" className="text-xs">القيود</TabsTrigger>
              <TabsTrigger value="structure" className="text-xs">الهيكل</TabsTrigger>
            </TabsList>
            
            {/* نظرة عامة */}
            <TabsContent value="overview" className="space-y-6">
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                {/* أيام العمل */}
                <Card className="border-green-200 bg-green-50/50">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Calendar className="h-4 w-4 text-green-600" />
                      أيام العمل
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <DaysDisplay days={settings.workingDays} type="work" />
                  </CardContent>
                </Card>
                
                {/* أيام العطلة */}
                <Card className="border-red-200 bg-red-50/50">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <CalendarDays className="h-4 w-4 text-red-600" />
                      أيام العطلة
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <DaysDisplay days={settings.weekendDays} type="weekend" />
                  </CardContent>
                </Card>
                
                {/* اليوم الدراسي */}
                <Card className="border-blue-200 bg-blue-50/50">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Clock className="h-4 w-4 text-blue-600" />
                      اليوم الدراسي
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <div className="text-center">
                        <p className="text-xs text-muted-foreground">بداية</p>
                        <p className="text-lg font-bold text-green-600">{settings.dayStart}</p>
                      </div>
                      <ChevronRight className="h-5 w-5 text-muted-foreground" />
                      <div className="text-center">
                        <p className="text-xs text-muted-foreground">نهاية</p>
                        <p className="text-lg font-bold text-orange-600">{settings.dayEnd}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
                
                {/* عدد الحصص */}
                <Card className="border-purple-200 bg-purple-50/50">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Grid3X3 className="h-4 w-4 text-purple-600" />
                      الحصص اليومية
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-3xl font-bold text-purple-700">{settings.periodsPerDay}</p>
                        <p className="text-xs text-muted-foreground">حصة يومياً</p>
                      </div>
                      <div className="text-left">
                        <p className="text-lg font-semibold text-purple-600">{settings.periodDuration} دقيقة</p>
                        <p className="text-xs text-muted-foreground">مدة الحصة</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
                
                {/* الاستراحة */}
                <Card className="border-amber-200 bg-amber-50/50">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Coffee className="h-4 w-4 text-amber-600" />
                      الاستراحة
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-3xl font-bold text-amber-700">{settings.breakDuration}</p>
                    <p className="text-xs text-muted-foreground">دقيقة</p>
                  </CardContent>
                </Card>
                
                {/* فترة الصلاة */}
                <Card className="border-emerald-200 bg-emerald-50/50">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Moon className="h-4 w-4 text-emerald-600" />
                      فترة الصلاة
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-3xl font-bold text-emerald-700">{settings.prayerDuration}</p>
                    <p className="text-xs text-muted-foreground">دقيقة</p>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>
            
            {/* التوقيت والفترات */}
            <TabsContent value="time" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Timer className="h-5 w-5 text-blue-600" />
                    التوزيع الزمني الكامل
                  </CardTitle>
                  <CardDescription>
                    {settings.timeSlots?.length || 0} فترة زمنية ({settings.periodsPerDay} حصة + استراحة + صلاة)
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {settings.timeSlots?.map((slot, index) => (
                      <TimeSlotCard key={index} slot={slot} index={index} />
                    ))}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
            
            {/* المعلمون */}
            <TabsContent value="teachers" className="space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        <Users className="h-5 w-5 text-violet-600" />
                        بيانات المعلمين
                      </CardTitle>
                      <CardDescription>{teachers.length} معلم في المدرسة</CardDescription>
                    </div>
                    <Button className="bg-violet-600 hover:bg-violet-700">
                      <Plus className="h-4 w-4 me-2" /> إضافة معلم
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  {teachers.length > 0 ? (
                    <div className="grid md:grid-cols-2 gap-3">
                      {teachers.map((teacher) => (
                        <TeacherCard key={teacher.id} teacher={teacher} />
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      <Users className="h-12 w-12 mx-auto mb-3 opacity-30" />
                      <p>لا يوجد معلمون مسجلون</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
            
            {/* الفصول */}
            <TabsContent value="classes" className="space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        <GraduationCap className="h-5 w-5 text-cyan-600" />
                        بيانات الفصول
                      </CardTitle>
                      <CardDescription>{classes.length} فصل في المدرسة</CardDescription>
                    </div>
                    <Button className="bg-cyan-600 hover:bg-cyan-700">
                      <Plus className="h-4 w-4 me-2" /> إضافة فصل
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  {classes.length > 0 ? (
                    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
                      {classes.map((classItem) => (
                        <ClassCard key={classItem.id} classItem={classItem} />
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      <GraduationCap className="h-12 w-12 mx-auto mb-3 opacity-30" />
                      <p>لا يوجد فصول مسجلة</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
            
            {/* المواد الدراسية */}
            <TabsContent value="subjects" className="space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        <BookOpen className="h-5 w-5 text-emerald-600" />
                        المواد الدراسية
                      </CardTitle>
                      <CardDescription>{subjects.length} مادة دراسية</CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  {subjects.length > 0 ? (
                    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
                      {subjects.map((subject, index) => (
                        <SubjectCard key={index} subject={subject} />
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      <BookOpen className="h-12 w-12 mx-auto mb-3 opacity-30" />
                      <p>لا يوجد مواد مسجلة</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
            
            {/* رتب المعلمين والنصاب */}
            <TabsContent value="ranks" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Target className="h-5 w-5 text-teal-600" />
                    رتب المعلمين والنصاب التدريسي
                  </CardTitle>
                  <CardDescription>{teacherRanks.length} رتبة معلم</CardDescription>
                </CardHeader>
                <CardContent>
                  {teacherRanks.length > 0 ? (
                    <div className="space-y-3">
                      {teacherRanks.map((rank) => (
                        <RankCard key={rank.id} rank={rank} />
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      <Target className="h-12 w-12 mx-auto mb-3 opacity-30" />
                      <p>لا يوجد رتب محددة</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
            
            {/* القيود الإدارية */}
            <TabsContent value="constraints" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Shield className="h-5 w-5 text-rose-600" />
                    القيود الإدارية
                  </CardTitle>
                  <CardDescription>{constraints.length} قيد إداري مفعّل</CardDescription>
                </CardHeader>
                <CardContent>
                  {constraints.length > 0 ? (
                    <div className="space-y-3">
                      {constraints.map((constraint, index) => (
                        <ConstraintCard key={constraint.id} constraint={constraint} index={index} />
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-8 text-muted-foreground">
                      <Shield className="h-12 w-12 mx-auto mb-3 opacity-30" />
                      <p>لا يوجد قيود إدارية</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
            
            {/* الهيكل الأكاديمي */}
            <TabsContent value="structure" className="space-y-4">
              <div className="grid md:grid-cols-3 gap-4">
                {/* المراحل */}
                <Card className="border-blue-200">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Building2 className="h-4 w-4 text-blue-600" />
                      المراحل الدراسية
                    </CardTitle>
                    <CardDescription>{academicStructure.stages?.length || 0} مرحلة</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {academicStructure.stages?.map((stage, index) => (
                        <div key={index} className="flex items-center justify-between p-2 rounded-lg bg-blue-50 border border-blue-200">
                          <span className="text-sm font-medium">{stage.name_ar}</span>
                          <Badge variant="outline" className="text-xs">{stage.grades_count} صف</Badge>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
                
                {/* الصفوف */}
                <Card className="border-green-200">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <GraduationCap className="h-4 w-4 text-green-600" />
                      الصفوف الدراسية
                    </CardTitle>
                    <CardDescription>{academicStructure.grades?.length || 0} صف</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ScrollArea className="h-60">
                      <div className="space-y-2">
                        {academicStructure.grades?.map((grade, index) => (
                          <div key={index} className="flex items-center justify-between p-2 rounded-lg bg-green-50 border border-green-200">
                            <span className="text-sm font-medium">{grade.name_ar}</span>
                            <Badge variant="outline" className="text-xs">{grade.order}</Badge>
                          </div>
                        ))}
                      </div>
                    </ScrollArea>
                  </CardContent>
                </Card>
                
                {/* المسارات */}
                <Card className="border-purple-200">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <FileText className="h-4 w-4 text-purple-600" />
                      المسارات التعليمية
                    </CardTitle>
                    <CardDescription>{academicStructure.tracks?.length || 0} مسار</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {academicStructure.tracks?.map((track, index) => (
                        <div key={index} className="flex items-center justify-between p-2 rounded-lg bg-purple-50 border border-purple-200">
                          <span className="text-sm font-medium">{track.name_ar}</span>
                          {track.is_quran_track && (
                            <Badge className="bg-emerald-600 text-xs">تحفيظ</Badge>
                          )}
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>
          </Tabs>
        </main>
      </div>
    </Sidebar>
  );
}

export { SchoolSettingsPageNew };
