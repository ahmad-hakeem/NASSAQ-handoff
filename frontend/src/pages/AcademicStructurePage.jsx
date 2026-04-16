import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { Slider } from '../components/ui/slider';
import { Progress } from '../components/ui/progress';
import { ScrollArea } from '../components/ui/scroll-area';
import { Separator } from '../components/ui/separator';
import {
  GraduationCap, Calendar, BookOpen, ClipboardCheck, ArrowUpDown,
  Plus, Edit2, Trash2, Eye, ChevronLeft, Sparkles, AlertTriangle,
  Info, CheckCircle2, Loader2, Send, Archive, X, CalendarDays,
  Clock, School, FileText, Settings2, TrendingUp, Users, Upload
} from 'lucide-react';

const STATUS_CONFIG = {
  upcoming: { label: 'قادم', labelEn: 'Upcoming', color: 'bg-blue-100 text-blue-800', dot: 'bg-blue-500' },
  active: { label: 'نشط', labelEn: 'Active', color: 'bg-green-100 text-green-800', dot: 'bg-green-500' },
  draft: { label: 'مسودة', labelEn: 'Draft', color: 'bg-gray-100 text-gray-800', dot: 'bg-gray-500' },
  closed: { label: 'مغلق', labelEn: 'Closed', color: 'bg-amber-100 text-amber-800', dot: 'bg-amber-500' },
  archived: { label: 'مؤرشف', labelEn: 'Archived', color: 'bg-slate-100 text-slate-800', dot: 'bg-slate-500' },
};

const HOLIDAY_TYPES = [
  { value: 'public', label: 'إجازة رسمية' },
  { value: 'school', label: 'إجازة مدرسية' },
  { value: 'activity', label: 'يوم نشاط' },
  { value: 'weekend_extension', label: 'تمديد عطلة نهاية الأسبوع' },
  { value: 'other', label: 'أخرى' },
];

const EXAM_TYPES = [
  { value: 'midterm', label: 'اختبار نصفي' },
  { value: 'final', label: 'اختبار نهائي' },
  { value: 'practical', label: 'اختبار عملي' },
  { value: 'quiz', label: 'اختبار قصير' },
];


export function AcademicStructureContent() {
  const { api } = useAuth();
  const { nassaqError, nassaqConfirm } = useNassaqAlert();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('years');

  const [overview, setOverview] = useState(null);
  const [academicYears, setAcademicYears] = useState([]);
  const [selectedYear, setSelectedYear] = useState(null);
  const [terms, setTerms] = useState([]);
  const [holidays, setHolidays] = useState([]);
  const [examPeriods, setExamPeriods] = useState([]);
  const [calendarData, setCalendarData] = useState(null);
  const [aiInsights, setAiInsights] = useState(null);

  const [showYearDialog, setShowYearDialog] = useState(false);
  const [showTermDialog, setShowTermDialog] = useState(false);
  const [showHolidayDialog, setShowHolidayDialog] = useState(false);
  const [showExamDialog, setShowExamDialog] = useState(false);
  const [showCalendarImportDialog, setShowCalendarImportDialog] = useState(false);
  const [importFile, setImportFile] = useState(null);
  const [importProcessing, setImportProcessing] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [hakimImportChat, setHakimImportChat] = useState('');
  const [editingItem, setEditingItem] = useState(null);

  const [yearForm, setYearForm] = useState({ name: '', name_en: '', start_date: '', end_date: '', is_current: false });
  const [termForm, setTermForm] = useState({ name: '', name_en: '', start_date: '', end_date: '', is_current: false });
  const [holidayForm, setHolidayForm] = useState({ name: '', name_en: '', start_date: '', end_date: '', type: 'public', custom_type: '', term_id: '' });
  const [examForm, setExamForm] = useState({ name: '', name_en: '', start_date: '', end_date: '', exam_type: 'final', term_id: '', start_time: '', end_time: '', period_number: '' });
  const fetchOverview = useCallback(async () => {
    try {
      const res = await api.get('/academic-structure/overview');
      setOverview(res.data);
    } catch (e) { console.error('Overview error:', e); }
  }, [api]);

  const fetchYears = useCallback(async () => {
    try {
      const res = await api.get('/academic-years');
      setAcademicYears(res.data);
      if (res.data.length > 0 && !selectedYear) {
        const current = res.data.find(y => y.is_current) || res.data[0];
        setSelectedYear(current);
      }
    } catch (e) { console.error('Years error:', e); }
  }, [api, selectedYear]);

  const fetchYearData = useCallback(async (yearId) => {
    if (!yearId) return;
    try {
      const [termsRes, holidaysRes, examsRes, calRes] = await Promise.all([
        api.get(`/terms?academic_year_id=${yearId}`),
        api.get(`/holidays?academic_year_id=${yearId}`),
        api.get(`/exam-periods?academic_year_id=${yearId}`),
        api.get(`/academic-calendar/${yearId}`),
      ]);
      setTerms(termsRes.data);
      setHolidays(holidaysRes.data);
      setExamPeriods(examsRes.data);
      setCalendarData(calRes.data);
    } catch (e) { console.error('Year data error:', e); }
  }, [api]);

  const fetchAiInsights = useCallback(async (yearId) => {
    try {
      const res = await api.get(`/academic-structure/ai-analysis/${yearId}`);
      setAiInsights(res.data);
    } catch (e) { console.error('AI error:', e); }
  }, [api]);

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      await Promise.all([fetchOverview(), fetchYears()]);
      setLoading(false);
    };
    init();
  }, [fetchOverview, fetchYears]);

  useEffect(() => {
    if (selectedYear?.id) {
      fetchYearData(selectedYear.id);
      fetchAiInsights(selectedYear.id);
    }
  }, [selectedYear?.id, fetchYearData, fetchAiInsights]);

  const getSchoolId = () => {
    try {
      const u = JSON.parse(localStorage.getItem('nassaq_user') || '{}');
      return u.tenant_id || u.school_id || '';
    } catch (e) { console.error('Error parsing user from localStorage:', e); return ''; }
  };

  const handleSaveYear = async () => {
    setSaving(true);
    try {
      const payload = { ...yearForm, school_id: getSchoolId() };
      if (editingItem) {
        await api.put(`/academic-years/${editingItem.id}`, payload);
      } else {
        await api.post('/academic-years', payload);
      }
      setShowYearDialog(false);
      setEditingItem(null);
      setYearForm({ name: '', name_en: '', start_date: '', end_date: '', is_current: false });
      await fetchYears();
      await fetchOverview();
    } catch (e) {
      nassaqError(e.response?.data?.detail || 'حدث خطأ أثناء حفظ العام الدراسي');
    }
    setSaving(false);
  };

  const handleSaveTerm = async () => {
    setSaving(true);
    try {
      const payload = { ...termForm, academic_year_id: selectedYear.id, school_id: getSchoolId() };
      if (editingItem) {
        await api.put(`/terms/${editingItem.id}`, payload);
      } else {
        await api.post('/terms', payload);
      }
      setShowTermDialog(false);
      setEditingItem(null);
      setTermForm({ name: '', name_en: '', start_date: '', end_date: '', is_current: false });
      await fetchYearData(selectedYear.id);
    } catch (e) {
      nassaqError(e.response?.data?.detail || 'حدث خطأ أثناء حفظ الفصل الدراسي');
    }
    setSaving(false);
  };

  const handleSaveHoliday = async () => {
    setSaving(true);
    try {
      const payload = { ...holidayForm, academic_year_id: selectedYear.id };
      if (editingItem) {
        await api.put(`/holidays/${editingItem.id}`, payload);
      } else {
        await api.post('/holidays', payload);
      }
      setShowHolidayDialog(false);
      setEditingItem(null);
      setHolidayForm({ name: '', name_en: '', start_date: '', end_date: '', type: 'public', custom_type: '', term_id: '' });
      await fetchYearData(selectedYear.id);
    } catch (e) {
      nassaqError(e.response?.data?.detail || 'حدث خطأ أثناء حفظ الإجازة');
    }
    setSaving(false);
  };

  const handleSaveExam = async () => {
    setSaving(true);
    try {
      const payload = {
        ...examForm,
        academic_year_id: selectedYear.id,
        start_time: examForm.start_time || null,
        end_time: examForm.end_time || null,
        period_number: examForm.period_number !== '' && examForm.period_number !== null ? Number(examForm.period_number) : null,
      };
      if (editingItem) {
        await api.put(`/exam-periods/${editingItem.id}`, payload);
      } else {
        await api.post('/exam-periods', payload);
      }
      setShowExamDialog(false);
      setEditingItem(null);
      setExamForm({ name: '', name_en: '', start_date: '', end_date: '', exam_type: 'final', term_id: '', start_time: '', end_time: '', period_number: '' });
      await fetchYearData(selectedYear.id);
    } catch (e) {
      nassaqError(e.response?.data?.detail || 'حدث خطأ أثناء حفظ فترة الاختبارات');
    }
    setSaving(false);
  };

  const handleAutoTerms = async (numTerms) => {
    setSaving(true);
    try {
      await api.post(`/academic-years/${selectedYear.id}/auto-terms?num_terms=${numTerms}`);
      await fetchYearData(selectedYear.id);
    } catch (e) {
      nassaqError(e.response?.data?.detail || 'حدث خطأ أثناء إنشاء الفصول تلقائياً');
    }
    setSaving(false);
  };

  const handlePublish = () => {
    nassaqConfirm('هل أنت متأكد من نشر هذا العام الدراسي؟ سيتم تعيينه كعام نشط.', async () => {
      setSaving(true);
      try {
        await api.post(`/academic-years/${selectedYear.id}/publish`);
        await Promise.all([fetchYears(), fetchOverview()]);
        const updated = await api.get(`/academic-years/${selectedYear.id}`);
        setSelectedYear(updated.data);
      } catch (e) {
        nassaqError(e.response?.data?.detail || 'حدث خطأ أثناء نشر العام الدراسي');
      }
      setSaving(false);
    }, { title: 'تأكيد النشر', confirmText: 'نعم، انشر', cancelText: 'إلغاء' });
  };

  const handleClose = () => {
    nassaqConfirm('هل أنت متأكد من إغلاق هذا العام الدراسي؟', async () => {
      setSaving(true);
      try {
        await api.post(`/academic-years/${selectedYear.id}/close`);
        await Promise.all([fetchYears(), fetchOverview()]);
        const updated = await api.get(`/academic-years/${selectedYear.id}`);
        setSelectedYear(updated.data);
      } catch (e) {
        nassaqError(e.response?.data?.detail || 'حدث خطأ أثناء إغلاق العام الدراسي');
      }
      setSaving(false);
    }, { title: 'تأكيد الإغلاق', confirmText: 'نعم، أغلق', cancelText: 'إلغاء' });
  };

  const handleArchive = () => {
    nassaqConfirm('هل أنت متأكد من أرشفة هذا العام الدراسي؟', async () => {
      setSaving(true);
      try {
        await api.post(`/academic-years/${selectedYear.id}/archive`);
        await Promise.all([fetchYears(), fetchOverview()]);
      } catch (e) {
        nassaqError(e.response?.data?.detail || 'حدث خطأ أثناء الأرشفة');
      }
      setSaving(false);
    }, { title: 'تأكيد الأرشفة', confirmText: 'نعم، أرشف', cancelText: 'إلغاء' });
  };

  const handleDeleteYear = (yearId) => {
    nassaqConfirm('هل أنت متأكد من حذف هذا العام الدراسي؟', async () => {
      try {
        await api.delete(`/academic-years/${yearId}`);
        await fetchYears();
        if (selectedYear?.id === yearId) setSelectedYear(null);
      } catch (e) {
        nassaqError(e.response?.data?.detail || 'حدث خطأ أثناء الحذف');
      }
    }, { title: 'تأكيد الحذف', confirmText: 'نعم، احذف', cancelText: 'إلغاء' });
  };

  const handleDeleteHoliday = (id) => {
    nassaqConfirm('هل أنت متأكد من حذف هذه الإجازة؟', async () => {
      try {
        await api.delete(`/holidays/${id}`);
        await fetchYearData(selectedYear.id);
      } catch (e) { nassaqError(e.response?.data?.detail || 'حدث خطأ أثناء الحذف'); }
    }, { title: 'تأكيد الحذف', confirmText: 'نعم، احذف', cancelText: 'إلغاء' });
  };

  const handleDeleteExam = (id) => {
    nassaqConfirm('هل أنت متأكد من حذف فترة الاختبارات؟', async () => {
      try {
        await api.delete(`/exam-periods/${id}`);
        await fetchYearData(selectedYear.id);
      } catch (e) { nassaqError(e.response?.data?.detail || 'حدث خطأ أثناء الحذف'); }
    }, { title: 'تأكيد الحذف', confirmText: 'نعم، احذف', cancelText: 'إلغاء' });
  };

  const handleCalendarImport = async () => {
    if (!importFile || !selectedYear) return;
    setImportProcessing(true);
    try {
      const formData = new FormData();
      formData.append('file', importFile);
      if (hakimImportChat) formData.append('instructions', hakimImportChat);
      const res = await api.post(`/academic-calendar/${selectedYear.id}/import`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setImportResult(res.data);
    } catch (e) {
      nassaqError(e.response?.data?.detail || 'حدث خطأ أثناء استيراد التقويم');
    }
    setImportProcessing(false);
  };

  const handleApplyImportResult = async () => {
    if (!importResult || !selectedYear) return;
    setSaving(true);
    try {
      await api.post(`/academic-calendar/${selectedYear.id}/import/apply`, { import_data: importResult });
      setShowCalendarImportDialog(false);
      setImportFile(null);
      setImportResult(null);
      setHakimImportChat('');
      await fetchYearData(selectedYear.id);
    } catch (e) {
      nassaqError(e.response?.data?.detail || 'حدث خطأ أثناء تطبيق بيانات التقويم');
    }
    setSaving(false);
  };

  const openExamDialog = (presetTermId = null) => {
    setEditingItem(null);
    const currentTerm = terms.find(t => t.is_current);
    const defaultTermId = presetTermId || (currentTerm ? currentTerm.id : (terms.length > 0 ? terms[0].id : ''));
    setExamForm({ name: '', name_en: '', start_date: '', end_date: '', exam_type: 'final', term_id: defaultTermId, start_time: '', end_time: '', period_number: '' });
    setShowExamDialog(true);
  };

  const formatDate = (val) => {
    if (!val) return '';
    return String(val).slice(0, 10);
  };

  const getDaysBetween = (start, end) => {
    try {
      const s = new Date(formatDate(start));
      const e = new Date(formatDate(end));
      const diff = Math.ceil((e - s) / (1000 * 60 * 60 * 24)) + 1;
      return Math.abs(diff);
    } catch (e) { console.error('Error calculating days between dates:', e); return 0; }
  };

  const getWeeksBetween = (start, end) => {
    return Math.round(getDaysBetween(start, end) / 7);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96" dir="rtl">
        <Loader2 className="h-8 w-8 animate-spin text-[#1B3A5C]" />
        <span className="mr-3 text-lg text-gray-600">جاري التحميل...</span>
      </div>
    );
  }

  const statusCfg = (s) => STATUS_CONFIG[s] || STATUS_CONFIG.draft;

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50/30 p-4 md:p-6" dir="rtl">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2.5 rounded-xl bg-gradient-to-br from-[#1B3A5C] to-[#2d5a8c] text-white shadow-lg">
            <GraduationCap className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[#1B3A5C]">الهيكل الأكاديمي</h1>
            <p className="text-sm text-gray-500">إدارة السنة الدراسية والفصول والتقويم الأكاديمي</p>
          </div>
        </div>

        {overview && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
            <Card className="border-0 shadow-sm bg-white/80">
              <CardContent className="p-4 flex items-center gap-3">
                <div className="p-2 rounded-lg bg-[#1B3A5C]/10"><Calendar className="h-5 w-5 text-[#1B3A5C]" /></div>
                <div>
                  <p className="text-xs text-gray-500">العام الحالي</p>
                  <p className="font-semibold text-sm">{overview.current_year?.name || 'غير محدد'}</p>
                </div>
              </CardContent>
            </Card>
            <Card className="border-0 shadow-sm bg-white/80">
              <CardContent className="p-4 flex items-center gap-3">
                <div className="p-2 rounded-lg bg-emerald-50"><BookOpen className="h-5 w-5 text-emerald-600" /></div>
                <div>
                  <p className="text-xs text-gray-500">عدد الفصول</p>
                  <p className="font-semibold text-sm">{overview.terms_count}</p>
                </div>
              </CardContent>
            </Card>
            <Card className="border-0 shadow-sm bg-white/80">
              <CardContent className="p-4 flex items-center gap-3">
                <div className="p-2 rounded-lg bg-amber-50"><Clock className="h-5 w-5 text-amber-600" /></div>
                <div>
                  <p className="text-xs text-gray-500">الفصل الحالي</p>
                  <p className="font-semibold text-sm">{overview.current_term?.name || 'غير محدد'}</p>
                </div>
              </CardContent>
            </Card>
            <Card className="border-0 shadow-sm bg-white/80">
              <CardContent className="p-4 flex items-center gap-3">
                <div className="p-2 rounded-lg bg-purple-50"><TrendingUp className="h-5 w-5 text-purple-600" /></div>
                <div>
                  <p className="text-xs text-gray-500">الأيام المتبقية</p>
                  <p className="font-semibold text-sm">{overview.remaining_school_days} يوم</p>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>

      {/* Main Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="bg-white shadow-sm border rounded-xl p-1 mb-4 flex flex-wrap gap-1">
          <TabsTrigger value="years" className="rounded-lg text-sm gap-1.5 data-[state=active]:bg-[#1B3A5C] data-[state=active]:text-white">
            <GraduationCap className="h-4 w-4" /> السنة الدراسية
          </TabsTrigger>
          <TabsTrigger value="terms" className="rounded-lg text-sm gap-1.5 data-[state=active]:bg-[#1B3A5C] data-[state=active]:text-white">
            <BookOpen className="h-4 w-4" /> الفصول الدراسية
          </TabsTrigger>
          <TabsTrigger value="calendar" className="rounded-lg text-sm gap-1.5 data-[state=active]:bg-[#1B3A5C] data-[state=active]:text-white">
            <CalendarDays className="h-4 w-4" /> التقويم الأكاديمي
          </TabsTrigger>
          <TabsTrigger value="exams" className="rounded-lg text-sm gap-1.5 data-[state=active]:bg-[#1B3A5C] data-[state=active]:text-white">
            <ClipboardCheck className="h-4 w-4" /> فترات الاختبارات
          </TabsTrigger>
        </TabsList>

        {/* TAB 1: Academic Years */}
        <TabsContent value="years">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold text-[#1B3A5C]">السنوات الدراسية</h2>
            <Button onClick={() => { setEditingItem(null); setYearForm({ name: '', name_en: '', start_date: '', end_date: '', is_current: false }); setShowYearDialog(true); }}
              className="bg-[#1B3A5C] hover:bg-[#2d5a8c] text-white gap-2">
              <Plus className="h-4 w-4" /> إضافة سنة دراسية
            </Button>
          </div>

          {academicYears.length === 0 ? (
            <Card className="border-dashed border-2 border-gray-300">
              <CardContent className="p-12 text-center">
                <GraduationCap className="h-12 w-12 mx-auto text-gray-400 mb-3" />
                <h3 className="text-lg font-semibold text-gray-600 mb-1">لا توجد سنوات دراسية</h3>
                <p className="text-sm text-gray-400 mb-4">ابدأ بإنشاء السنة الدراسية الأولى</p>
                <Button onClick={() => setShowYearDialog(true)} className="bg-[#1B3A5C] text-white gap-2">
                  <Plus className="h-4 w-4" /> إنشاء سنة دراسية
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {academicYears.map((year) => {
                const sc = statusCfg(year.status);
                const isSelected = selectedYear?.id === year.id;
                return (
                  <Card key={year.id}
                    className={`cursor-pointer transition-all hover:shadow-md border-2 ${isSelected ? 'border-[#1B3A5C] shadow-lg ring-2 ring-[#1B3A5C]/20' : 'border-transparent'}`}
                    onClick={() => setSelectedYear(year)}>
                    <CardContent className="p-5">
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <h3 className="text-lg font-bold text-[#1B3A5C]">{year.name}</h3>
                          {year.name_en && <p className="text-xs text-gray-500">{year.name_en}</p>}
                        </div>
                        <Badge className={`${sc.color} text-xs`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${sc.dot} ml-1.5`} />
                          {sc.label}
                        </Badge>
                      </div>
                      <div className="space-y-2 text-sm text-gray-600">
                        <div className="flex justify-between">
                          <span>تاريخ البدء</span>
                          <span className="font-medium">{formatDate(year.start_date)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>تاريخ الانتهاء</span>
                          <span className="font-medium">{formatDate(year.end_date)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>المدة</span>
                          <span className="font-medium">{getDaysBetween(year.start_date, year.end_date)} يوم</span>
                        </div>
                      </div>
                      <Separator className="my-3" />
                      <div className="flex gap-2 flex-wrap">
                        <Button size="sm" variant="outline" className="text-xs gap-1" onClick={(e) => {
                          e.stopPropagation();
                          setEditingItem(year);
                          setYearForm({ name: year.name, name_en: year.name_en || '', start_date: formatDate(year.start_date), end_date: formatDate(year.end_date), is_current: year.is_current });
                          setShowYearDialog(true);
                        }}>
                          <Edit2 className="h-3 w-3" /> تعديل
                        </Button>
                        {year.status !== 'active' && (
                          <Button size="sm" variant="outline" className="text-xs gap-1 text-red-600 hover:bg-red-50"
                            onClick={(e) => { e.stopPropagation(); handleDeleteYear(year.id); }}>
                            <Trash2 className="h-3 w-3" /> حذف
                          </Button>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}

          {/* Actions Bar for selected year */}
          {selectedYear && (
            <Card className="mt-4 border-0 shadow-sm bg-white/80">
              <CardContent className="p-4">
                <div className="flex items-center justify-between flex-wrap gap-3">
                  <div className="text-sm text-gray-600">
                    العام المحدد: <span className="font-bold text-[#1B3A5C]">{selectedYear.name}</span>
                    <Badge className={`${statusCfg(selectedYear.status).color} text-xs mr-2`}>{statusCfg(selectedYear.status).label}</Badge>
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    {!selectedYear.is_current && selectedYear.status !== 'archived' && (
                      <Button size="sm" onClick={handlePublish} disabled={saving} className="bg-emerald-600 hover:bg-emerald-700 text-white gap-1.5">
                        <Send className="h-3.5 w-3.5" /> تعيين كعام حالي
                      </Button>
                    )}
                    {selectedYear.is_current && (
                      <Button size="sm" variant="outline" onClick={handleClose} disabled={saving} className="text-amber-700 border-amber-300 gap-1.5">
                        <X className="h-3.5 w-3.5" /> إغلاق العام
                      </Button>
                    )}
                    {selectedYear.status !== 'active' && selectedYear.status !== 'archived' && (
                      <Button size="sm" variant="outline" onClick={handleArchive} disabled={saving} className="text-slate-600 gap-1.5">
                        <Archive className="h-3.5 w-3.5" /> أرشفة
                      </Button>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* TAB 2: Term Structure */}
        <TabsContent value="terms">
          {!selectedYear ? (
            <Card className="border-dashed border-2 border-gray-300">
              <CardContent className="p-12 text-center">
                <BookOpen className="h-12 w-12 mx-auto text-gray-400 mb-3" />
                <h3 className="text-lg font-semibold text-gray-600">اختر سنة دراسية أولاً</h3>
                <p className="text-sm text-gray-400">يرجى تحديد سنة دراسية من تبويب السنوات الدراسية</p>
              </CardContent>
            </Card>
          ) : (
            <>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-bold text-[#1B3A5C]">الفصول الدراسية — {selectedYear.name}</h2>
                  <p className="text-sm text-gray-500">{terms.length} فصل دراسي</p>
                </div>
                <div className="flex gap-2">
                  {terms.length === 0 && (
                    <>
                      <Button size="sm" variant="outline" onClick={() => handleAutoTerms(2)} disabled={saving} className="gap-1.5">
                        <Sparkles className="h-3.5 w-3.5" /> إنشاء فصلين
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => handleAutoTerms(3)} disabled={saving} className="gap-1.5">
                        <Sparkles className="h-3.5 w-3.5" /> إنشاء 3 فصول
                      </Button>
                    </>
                  )}
                  <Button onClick={() => { setEditingItem(null); setTermForm({ name: '', name_en: '', start_date: '', end_date: '', is_current: false }); setShowTermDialog(true); }}
                    size="sm" className="bg-[#1B3A5C] hover:bg-[#2d5a8c] text-white gap-1.5">
                    <Plus className="h-4 w-4" /> إضافة فصل
                  </Button>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {terms.map((term) => {
                  const weeks = getWeeksBetween(term.start_date, term.end_date);
                  const days = getDaysBetween(term.start_date, term.end_date);
                  const termHolidays = holidays.filter(h => h.term_id === term.id);
                  const termExams = examPeriods.filter(e => e.term_id === term.id);
                  const hasInvertedDates = term.start_date && term.end_date && formatDate(term.start_date) > formatDate(term.end_date);
                  return (
                    <Card key={term.id} className={`transition-all hover:shadow-md ${term.is_current ? 'border-2 border-emerald-500 ring-2 ring-emerald-500/20' : ''} ${hasInvertedDates ? 'border-2 border-red-400' : ''}`}>
                      <CardContent className="p-5">
                        {hasInvertedDates && (
                          <div className="mb-2 text-xs text-red-600 bg-red-50 rounded px-2 py-1 flex items-center gap-1">
                            <span>⚠️</span> تاريخ البداية بعد تاريخ النهاية — يرجى تعديل الفصل
                          </div>
                        )}
                        <div className="flex items-start justify-between mb-3">
                          <div>
                            <h3 className="font-bold text-[#1B3A5C]">{term.name}</h3>
                            {term.name_en && <p className="text-xs text-gray-500">{term.name_en}</p>}
                          </div>
                          {term.is_current && <Badge className="bg-emerald-100 text-emerald-800 text-xs">الحالي</Badge>}
                        </div>

                        <div className="grid grid-cols-2 gap-2 mb-3">
                          <div className="bg-gray-50 rounded-lg p-2.5 text-center">
                            <p className="text-lg font-bold text-[#1B3A5C]">{weeks}</p>
                            <p className="text-xs text-gray-500">أسبوع</p>
                          </div>
                          <div className="bg-gray-50 rounded-lg p-2.5 text-center">
                            <p className="text-lg font-bold text-[#1B3A5C]">{days}</p>
                            <p className="text-xs text-gray-500">يوم</p>
                          </div>
                        </div>

                        <div className="space-y-1.5 text-sm text-gray-600 mb-3">
                          <div className="flex justify-between"><span>البداية</span><span className="font-medium">{formatDate(term.start_date)}</span></div>
                          <div className="flex justify-between"><span>النهاية</span><span className="font-medium">{formatDate(term.end_date)}</span></div>
                          <div className="flex justify-between"><span>الإجازات</span><span className="font-medium">{termHolidays.length}</span></div>
                          <div className="flex justify-between"><span>فترات الاختبار</span><span className="font-medium">{termExams.length}</span></div>
                        </div>

                        <div className="flex gap-2">
                          <Button size="sm" variant="outline" className="text-xs gap-1 flex-1" onClick={() => {
                            setEditingItem(term);
                            setTermForm({ name: term.name, name_en: term.name_en || '', start_date: formatDate(term.start_date), end_date: formatDate(term.end_date), is_current: term.is_current });
                            setShowTermDialog(true);
                          }}>
                            <Edit2 className="h-3 w-3" /> تعديل
                          </Button>
                          <Button size="sm" variant="outline" className="text-xs gap-1" onClick={() => {
                            setHolidayForm({ ...holidayForm, term_id: term.id });
                            setEditingItem(null);
                            setShowHolidayDialog(true);
                          }}>
                            <CalendarDays className="h-3 w-3" /> إجازة
                          </Button>
                          <Button size="sm" variant="outline" className="text-xs gap-1" onClick={() => openExamDialog(term.id)}>
                            <ClipboardCheck className="h-3 w-3" /> اختبار
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </>
          )}
        </TabsContent>

        {/* TAB 3: Academic Calendar */}
        <TabsContent value="calendar">
          {!selectedYear ? (
            <Card className="border-dashed border-2 border-gray-300">
              <CardContent className="p-12 text-center">
                <CalendarDays className="h-12 w-12 mx-auto text-gray-400 mb-3" />
                <h3 className="text-lg font-semibold text-gray-600">اختر سنة دراسية أولاً</h3>
              </CardContent>
            </Card>
          ) : (
            <>
              <div className="flex items-center justify-between mb-4 gap-2">
                <h2 className="text-lg font-bold text-[#1B3A5C]">التقويم الأكاديمي — {selectedYear.name}</h2>
                <div className="flex items-center gap-2">
                  <Button size="sm" variant="outline" onClick={() => { setImportFile(null); setImportResult(null); setHakimImportChat(''); setShowCalendarImportDialog(true); }}
                    className="gap-1.5 border-[#1B3A5C] text-[#1B3A5C] hover:bg-[#1B3A5C]/10">
                    <Upload className="h-4 w-4" /> استيراد التقويم بالذكاء الاصطناعي
                  </Button>
                  <Button size="sm" onClick={() => { setEditingItem(null); setHolidayForm({ name: '', name_en: '', start_date: '', end_date: '', type: 'public', custom_type: '', term_id: '' }); setShowHolidayDialog(true); }}
                    className="bg-[#1B3A5C] hover:bg-[#2d5a8c] text-white gap-1.5">
                    <Plus className="h-4 w-4" /> إضافة إجازة
                  </Button>
                </div>
              </div>

              {/* Calendar Summary */}
              {calendarData?.summary && (
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
                  {[
                    { label: 'إجمالي الأيام', value: calendarData.summary.total_days, icon: Calendar, color: 'blue' },
                    { label: 'أيام دراسية', value: calendarData.summary.school_days, icon: School, color: 'emerald' },
                    { label: 'أيام إجازة', value: calendarData.summary.holiday_days, icon: CalendarDays, color: 'amber' },
                    { label: 'أيام اختبارات', value: calendarData.summary.exam_days, icon: ClipboardCheck, color: 'purple' },
                    { label: 'عدد الفصول', value: calendarData.summary.terms_count, icon: BookOpen, color: 'indigo' },
                  ].map((item, i) => (
                    <Card key={i} className="border-0 shadow-sm">
                      <CardContent className="p-3 text-center">
                        <item.icon className={`h-5 w-5 mx-auto mb-1 text-${item.color}-600`} />
                        <p className="text-xl font-bold text-[#1B3A5C]">{item.value}</p>
                        <p className="text-xs text-gray-500">{item.label}</p>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}

              {/* Term Timeline */}
              <Card className="mb-4 border-0 shadow-sm">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">الجدول الزمني للفصول</CardTitle>
                </CardHeader>
                <CardContent>
                  {terms.length === 0 ? (
                    <p className="text-center text-gray-400 py-6">لا توجد فصول دراسية</p>
                  ) : (
                    <div className="space-y-3">
                      {terms.map((term, idx) => {
                        const days = getDaysBetween(term.start_date, term.end_date);
                        const totalDays = calendarData?.summary?.total_days || 1;
                        const pct = Math.round((days / totalDays) * 100);
                        const colors = ['bg-blue-500', 'bg-emerald-500', 'bg-purple-500'];
                        return (
                          <div key={term.id}>
                            <div className="flex items-center justify-between text-sm mb-1">
                              <span className="font-medium">{term.name}</span>
                              <span className="text-gray-500">{formatDate(term.start_date)} → {formatDate(term.end_date)} ({days} يوم)</span>
                            </div>
                            <div className="w-full bg-gray-100 rounded-full h-3">
                              <div className={`${colors[idx % 3]} h-3 rounded-full transition-all`} style={{ width: `${pct}%` }} />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Holidays List */}
              <Card className="mb-4 border-0 shadow-sm">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">الإجازات والعطل</CardTitle>
                </CardHeader>
                <CardContent>
                  {holidays.length === 0 ? (
                    <p className="text-center text-gray-400 py-6">لا توجد إجازات مسجلة</p>
                  ) : (
                    <div className="space-y-2">
                      {holidays.map((h) => (
                        <div key={h.id} className="flex items-center justify-between bg-amber-50/50 rounded-lg p-3">
                          <div className="flex items-center gap-3">
                            <CalendarDays className="h-4 w-4 text-amber-600" />
                            <div>
                              <p className="font-medium text-sm">{h.name}</p>
                              <p className="text-xs text-gray-500">{formatDate(h.start_date)} → {formatDate(h.end_date)} ({getDaysBetween(h.start_date, h.end_date)} يوم)</p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge variant="outline" className="text-xs">{HOLIDAY_TYPES.find(t => t.value === h.type)?.label || h.type}</Badge>
                            <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={() => {
                              setEditingItem(h);
                              setHolidayForm({ name: h.name, name_en: h.name_en || '', start_date: formatDate(h.start_date), end_date: formatDate(h.end_date), type: h.type, custom_type: h.custom_type || '', term_id: h.term_id || '' });
                              setShowHolidayDialog(true);
                            }}>
                              <Edit2 className="h-3.5 w-3.5" />
                            </Button>
                            <Button size="sm" variant="ghost" className="h-7 w-7 p-0 text-red-500" onClick={() => handleDeleteHoliday(h.id)}>
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* AI Insights */}
              {aiInsights && (
                <Card className="border-0 shadow-sm bg-gradient-to-br from-indigo-50/50 to-purple-50/50">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base flex items-center gap-2">
                      <Sparkles className="h-4 w-4 text-indigo-600" /> تحليل حكيم الذكي
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {aiInsights.insights?.map((insight, idx) => (
                        <div key={idx} className={`flex items-start gap-3 p-3 rounded-lg ${
                          insight.type === 'warning' ? 'bg-amber-50' : insight.type === 'suggestion' ? 'bg-blue-50' : 'bg-emerald-50'
                        }`}>
                          {insight.type === 'warning' ? <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" /> :
                           insight.type === 'suggestion' ? <Info className="h-4 w-4 text-blue-600 mt-0.5 shrink-0" /> :
                           <CheckCircle2 className="h-4 w-4 text-emerald-600 mt-0.5 shrink-0" />}
                          <div>
                            <p className="text-sm font-medium">{insight.message}</p>
                            {insight.message_en && <p className="text-xs text-gray-500 mt-0.5">{insight.message_en}</p>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </TabsContent>

        {/* TAB 4: Exam Periods */}
        <TabsContent value="exams">
          {!selectedYear ? (
            <Card className="border-dashed border-2 border-gray-300">
              <CardContent className="p-12 text-center">
                <ClipboardCheck className="h-12 w-12 mx-auto text-gray-400 mb-3" />
                <h3 className="text-lg font-semibold text-gray-600">اختر سنة دراسية أولاً</h3>
              </CardContent>
            </Card>
          ) : (
            <>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-bold text-[#1B3A5C]">فترات الاختبارات — {selectedYear.name}</h2>
                <Button size="sm" onClick={() => openExamDialog()}
                  className="bg-[#1B3A5C] hover:bg-[#2d5a8c] text-white gap-1.5">
                  <Plus className="h-4 w-4" /> إضافة فترة اختبار
                </Button>
              </div>

              {examPeriods.length === 0 ? (
                <Card className="border-dashed border-2 border-gray-300">
                  <CardContent className="p-12 text-center">
                    <ClipboardCheck className="h-12 w-12 mx-auto text-gray-400 mb-3" />
                    <h3 className="text-lg font-semibold text-gray-600">لا توجد فترات اختبارات</h3>
                    <p className="text-sm text-gray-400 mb-4">أضف فترات الاختبارات لكل فصل دراسي</p>
                  </CardContent>
                </Card>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {examPeriods.map((ep) => {
                    const term = terms.find(t => t.id === ep.term_id);
                    return (
                      <Card key={ep.id} className="hover:shadow-md transition-all">
                        <CardContent className="p-5">
                          <div className="flex items-start justify-between mb-3">
                            <div>
                              <h3 className="font-bold text-[#1B3A5C]">{ep.name}</h3>
                              {ep.name_en && <p className="text-xs text-gray-500">{ep.name_en}</p>}
                            </div>
                            <Badge className="bg-purple-100 text-purple-800 text-xs">
                              {EXAM_TYPES.find(t => t.value === ep.exam_type)?.label || ep.exam_type}
                            </Badge>
                          </div>
                          <div className="space-y-1.5 text-sm text-gray-600 mb-3">
                            <div className="flex justify-between"><span>الفصل</span><span className="font-medium">{term?.name || '—'}</span></div>
                            <div className="flex justify-between"><span>البداية</span><span className="font-medium">{ep.start_date}</span></div>
                            <div className="flex justify-between"><span>النهاية</span><span className="font-medium">{ep.end_date}</span></div>
                            <div className="flex justify-between"><span>المدة</span><span className="font-medium">{getDaysBetween(ep.start_date, ep.end_date)} يوم</span></div>
                          </div>
                          <div className="flex gap-2">
                            <Button size="sm" variant="outline" className="text-xs gap-1" onClick={() => {
                              setEditingItem(ep);
                              setExamForm({ name: ep.name, name_en: ep.name_en || '', start_date: ep.start_date, end_date: ep.end_date, exam_type: ep.exam_type, term_id: ep.term_id, start_time: ep.start_time || '', end_time: ep.end_time || '', period_number: ep.period_number || '' });
                              setShowExamDialog(true);
                            }}>
                              <Edit2 className="h-3 w-3" /> تعديل
                            </Button>
                            <Button size="sm" variant="outline" className="text-xs gap-1 text-red-600 hover:bg-red-50" onClick={() => handleDeleteExam(ep.id)}>
                              <Trash2 className="h-3 w-3" /> حذف
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </TabsContent>

      </Tabs>

      {/* ========== DIALOGS ========== */}

      {/* Academic Year Dialog */}
      <Dialog open={showYearDialog} onOpenChange={setShowYearDialog}>
        <DialogContent className="sm:max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>{editingItem ? 'تعديل السنة الدراسية' : 'إضافة سنة دراسية جديدة'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>اسم السنة الدراسية (عربي)</Label>
              <Input value={yearForm.name} onChange={(e) => setYearForm({ ...yearForm, name: e.target.value })} placeholder="مثال: 1446 / 1447 هـ" />
            </div>
            <div>
              <Label>اسم السنة الدراسية (إنجليزي)</Label>
              <Input value={yearForm.name_en} onChange={(e) => setYearForm({ ...yearForm, name_en: e.target.value })} placeholder="e.g. 2025 / 2026" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>تاريخ البدء</Label>
                <Input type="date" value={yearForm.start_date} onChange={(e) => setYearForm({ ...yearForm, start_date: e.target.value })} />
              </div>
              <div>
                <Label>تاريخ الانتهاء</Label>
                <Input type="date" value={yearForm.end_date} onChange={(e) => setYearForm({ ...yearForm, end_date: e.target.value })} />
              </div>
            </div>
          </div>
          <DialogFooter className="flex gap-2">
            <Button variant="outline" onClick={() => setShowYearDialog(false)}>إلغاء</Button>
            <Button onClick={handleSaveYear} disabled={saving || !yearForm.name || !yearForm.start_date || !yearForm.end_date}
              className="bg-[#1B3A5C] text-white">
              {saving ? <Loader2 className="h-4 w-4 animate-spin ml-2" /> : null}
              {editingItem ? 'تحديث' : 'إنشاء'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Term Dialog */}
      <Dialog open={showTermDialog} onOpenChange={setShowTermDialog}>
        <DialogContent className="sm:max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>{editingItem ? 'تعديل الفصل الدراسي' : 'إضافة فصل دراسي'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>اسم الفصل (عربي)</Label>
              <Input value={termForm.name} onChange={(e) => setTermForm({ ...termForm, name: e.target.value })} placeholder="مثال: الفصل الأول" />
            </div>
            <div>
              <Label>اسم الفصل (إنجليزي)</Label>
              <Input value={termForm.name_en} onChange={(e) => setTermForm({ ...termForm, name_en: e.target.value })} placeholder="e.g. Term 1" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>تاريخ البدء</Label>
                <Input type="date" value={termForm.start_date} onChange={(e) => setTermForm({ ...termForm, start_date: e.target.value })} />
              </div>
              <div>
                <Label>تاريخ الانتهاء</Label>
                <Input type="date" value={termForm.end_date} onChange={(e) => setTermForm({ ...termForm, end_date: e.target.value })} />
              </div>
            </div>
          </div>
          <DialogFooter className="flex gap-2">
            <Button variant="outline" onClick={() => setShowTermDialog(false)}>إلغاء</Button>
            <Button onClick={handleSaveTerm} disabled={saving || !termForm.name || !termForm.start_date || !termForm.end_date}
              className="bg-[#1B3A5C] text-white">
              {saving ? <Loader2 className="h-4 w-4 animate-spin ml-2" /> : null}
              {editingItem ? 'تحديث' : 'إنشاء'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Holiday Dialog */}
      <Dialog open={showHolidayDialog} onOpenChange={setShowHolidayDialog}>
        <DialogContent className="sm:max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>{editingItem ? 'تعديل الإجازة' : 'إضافة إجازة'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>اسم الإجازة (عربي)</Label>
              <Input value={holidayForm.name} onChange={(e) => setHolidayForm({ ...holidayForm, name: e.target.value })} placeholder="مثال: إجازة اليوم الوطني" />
            </div>
            <div>
              <Label>اسم الإجازة (إنجليزي)</Label>
              <Input value={holidayForm.name_en} onChange={(e) => setHolidayForm({ ...holidayForm, name_en: e.target.value })} placeholder="e.g. National Day" />
            </div>
            <div>
              <Label>نوع الإجازة</Label>
              <Select value={holidayForm.type} onValueChange={(v) => setHolidayForm({ ...holidayForm, type: v, custom_type: '' })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {HOLIDAY_TYPES.map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            {holidayForm.type === 'other' && (
              <div>
                <Label>تحديد نوع الإجازة (أخرى)</Label>
                <Input value={holidayForm.custom_type} onChange={(e) => setHolidayForm({ ...holidayForm, custom_type: e.target.value })} placeholder="مثال: إجازة استثنائية" />
              </div>
            )}
            <div>
              <Label>الفصل الدراسي (اختياري)</Label>
              <Select value={holidayForm.term_id || 'none'} onValueChange={(v) => setHolidayForm({ ...holidayForm, term_id: v === 'none' ? '' : v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">— بدون فصل محدد —</SelectItem>
                  {terms.map(t => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>تاريخ البدء</Label>
                <Input type="date" value={holidayForm.start_date} onChange={(e) => setHolidayForm({ ...holidayForm, start_date: e.target.value })} />
              </div>
              <div>
                <Label>تاريخ الانتهاء</Label>
                <Input type="date" value={holidayForm.end_date} onChange={(e) => setHolidayForm({ ...holidayForm, end_date: e.target.value })} />
              </div>
            </div>
          </div>
          <DialogFooter className="flex gap-2">
            <Button variant="outline" onClick={() => setShowHolidayDialog(false)}>إلغاء</Button>
            <Button onClick={handleSaveHoliday} disabled={saving || !holidayForm.name || !holidayForm.start_date || !holidayForm.end_date}
              className="bg-[#1B3A5C] text-white">
              {saving ? <Loader2 className="h-4 w-4 animate-spin ml-2" /> : null}
              {editingItem ? 'تحديث' : 'إضافة'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Exam Period Dialog */}
      <Dialog open={showExamDialog} onOpenChange={setShowExamDialog}>
        <DialogContent className="sm:max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>{editingItem ? 'تعديل فترة الاختبار' : 'إضافة فترة اختبار'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>اسم فترة الاختبار (عربي)</Label>
              <Input value={examForm.name} onChange={(e) => setExamForm({ ...examForm, name: e.target.value })} placeholder="مثال: اختبارات نهاية الفصل الأول" />
            </div>
            <div>
              <Label>اسم فترة الاختبار (إنجليزي)</Label>
              <Input value={examForm.name_en} onChange={(e) => setExamForm({ ...examForm, name_en: e.target.value })} placeholder="e.g. Term 1 Final Exams" />
            </div>
            <div>
              <Label>نوع الاختبار</Label>
              <Select value={examForm.exam_type} onValueChange={(v) => setExamForm({ ...examForm, exam_type: v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {EXAM_TYPES.map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>الفصل الدراسي</Label>
              <Select value={examForm.term_id || 'none'} onValueChange={(v) => setExamForm({ ...examForm, term_id: v === 'none' ? '' : v })}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">— اختر الفصل —</SelectItem>
                  {terms.map(t => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>تاريخ البدء</Label>
                <Input type="date" value={examForm.start_date} onChange={(e) => setExamForm({ ...examForm, start_date: e.target.value })} />
              </div>
              <div>
                <Label>تاريخ الانتهاء</Label>
                <Input type="date" value={examForm.end_date} onChange={(e) => setExamForm({ ...examForm, end_date: e.target.value })} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>وقت البدء (اختياري)</Label>
                <Input type="time" value={examForm.start_time} onChange={(e) => setExamForm({ ...examForm, start_time: e.target.value })} />
              </div>
              <div>
                <Label>وقت الانتهاء (اختياري)</Label>
                <Input type="time" value={examForm.end_time} onChange={(e) => setExamForm({ ...examForm, end_time: e.target.value })} />
              </div>
            </div>
            <div>
              <Label>رقم الفترة (اختياري)</Label>
              <Input type="number" min="1" value={examForm.period_number} onChange={(e) => setExamForm({ ...examForm, period_number: e.target.value })} placeholder="مثال: 1" />
            </div>
          </div>
          <DialogFooter className="flex gap-2">
            <Button variant="outline" onClick={() => setShowExamDialog(false)}>إلغاء</Button>
            <Button onClick={handleSaveExam} disabled={saving || !examForm.name || !examForm.start_date || !examForm.end_date}
              className="bg-[#1B3A5C] text-white">
              {saving ? <Loader2 className="h-4 w-4 animate-spin ml-2" /> : null}
              {editingItem ? 'تحديث' : 'إضافة'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {/* AI Calendar Import Dialog */}
      <Dialog open={showCalendarImportDialog} onOpenChange={setShowCalendarImportDialog}>
        <DialogContent className="sm:max-w-lg" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-[#1B3A5C]" /> استيراد التقويم الأكاديمي بالذكاء الاصطناعي
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label className="mb-2 block">ارفع ملف Excel أو CSV يحتوي على التقويم</Label>
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center cursor-pointer hover:border-[#1B3A5C]/50 transition-colors"
                onClick={() => document.getElementById('calendar-file-input').click()}>
                <Upload className="h-8 w-8 mx-auto text-gray-400 mb-2" />
                {importFile ? (
                  <p className="text-sm font-medium text-[#1B3A5C]">{importFile.name}</p>
                ) : (
                  <p className="text-sm text-gray-500">اضغط لاختيار الملف</p>
                )}
                <p className="text-xs text-gray-400 mt-1">.xlsx, .xls, .csv</p>
                <input id="calendar-file-input" type="file" className="hidden" accept=".xlsx,.xls,.csv"
                  onChange={(e) => { if (e.target.files[0]) setImportFile(e.target.files[0]); }} />
              </div>
            </div>
            <div>
              <Label className="mb-2 block">تعليمات إضافية لحكيم (اختياري)</Label>
              <Input value={hakimImportChat} onChange={(e) => setHakimImportChat(e.target.value)}
                placeholder="مثال: يمكن تجاهل عطل نهاية الأسبوع، واعتبر أن الدراسة من السبت إلى الأربعاء..." />
            </div>
            {importResult && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle2 className="h-5 w-5 text-green-600" />
                  <span className="font-medium text-green-800">تم تحليل التقويم بنجاح</span>
                </div>
                <div className="text-sm text-gray-700 space-y-1">
                  {importResult.holidays && <p>الإجازات المكتشفة: {importResult.holidays.length}</p>}
                  {importResult.exam_periods && <p>فترات الاختبارات: {importResult.exam_periods.length}</p>}
                  {importResult.message && <p>{importResult.message}</p>}
                </div>
              </div>
            )}
          </div>
          <DialogFooter className="flex gap-2">
            <Button variant="outline" onClick={() => setShowCalendarImportDialog(false)}>إلغاء</Button>
            {importResult ? (
              <Button onClick={handleApplyImportResult} disabled={saving} className="bg-green-600 hover:bg-green-700 text-white gap-1.5">
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
                تطبيق البيانات
              </Button>
            ) : (
              <Button onClick={handleCalendarImport} disabled={!importFile || importProcessing} className="bg-[#1B3A5C] hover:bg-[#2d5a8c] text-white gap-1.5">
                {importProcessing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                تحليل بالذكاء الاصطناعي
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default function AcademicStructurePage() {
  return <AcademicStructureContent />;
}
