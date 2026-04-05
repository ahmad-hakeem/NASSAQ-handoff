import { useState, useEffect } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import { useAuth } from '../../contexts/AuthContext';
import { useNassaqAlert } from '../ui/NassaqAlertDialog';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import { toast } from 'sonner';
import {
  Loader2,
  CheckCircle2,
  Calendar,
  Clock,
  Plus,
  Trash2,
  GraduationCap,
  User,
  BookOpen,
} from 'lucide-react';


export const CreateScheduleWizard = ({ open, onClose, onOpenChange }) => {
  const { isRTL } = useTheme();
  const { token, api } = useAuth();
  const { nassaqWarning, nassaqError } = useNassaqAlert();
  
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [result, setResult] = useState(null);
  
  const [options, setOptions] = useState({
    periods: [],
    days: [],
    teachers: [],
    subjects: [],
    classes: [],
    grades: [],
  });
  
  const [data, setData] = useState({
    name_ar: '',
    class_id: '',
    grade_id: '',
    academic_year: '2025-2026',
    semester: 1,
  });
  
  const [schedule, setSchedule] = useState({
    sunday: [],
    monday: [],
    tuesday: [],
    wednesday: [],
    thursday: [],
  });

  useEffect(() => {
    if (open) fetchOptions();
  }, [open]);

  const fetchOptions = async () => {
    setLoading(true);
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    try {
      const [periodsRes, daysRes, teachersRes, subjectsRes, classesRes, gradesRes] = await Promise.all([
        api.get('/schedules/options/periods').catch(() => ({ data: { periods: [] } })),
        api.get('/schedules/options/days').catch(() => ({ data: { days: [] } })),
        api.get('/schedules/options/teachers').catch(() => ({ data: { teachers: [] } })),
        api.get('/schedules/options/subjects').catch(() => ({ data: { subjects: [] } })),
        api.get('/schedules/options/classes').catch(() => ({ data: { classes: [] } })),
        api.get('/classes/options/grades').catch(() => ({ data: { grades: [] } })),
      ]);

      setOptions({
        periods: periodsRes.data.periods || [],
        days: daysRes.data.days || [],
        teachers: teachersRes.data.teachers || [],
        subjects: subjectsRes.data.subjects || [],
        classes: classesRes.data.classes || [],
        grades: gradesRes.data.grades || [],
      });
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };

  const addPeriod = (day) => {
    const nextNumber = (schedule[day]?.length || 0) + 1;
    const defaultPeriod = options.periods.find(p => p.number === nextNumber);
    
    setSchedule(prev => ({
      ...prev,
      [day]: [...(prev[day] || []), {
        period_number: nextNumber,
        subject_id: '',
        teacher_id: '',
        start_time: defaultPeriod?.start || '',
        end_time: defaultPeriod?.end || '',
      }]
    }));
  };

  const removePeriod = (day, index) => {
    setSchedule(prev => ({
      ...prev,
      [day]: prev[day].filter((_, i) => i !== index)
    }));
  };

  const updatePeriod = (day, index, field, value) => {
    setSchedule(prev => ({
      ...prev,
      [day]: prev[day].map((p, i) => i === index ? { ...p, [field]: value } : p)
    }));
  };

  const handleSubmit = async () => {
    if (!data.name_ar || !data.class_id) {
      nassaqWarning(isRTL ? 'أدخل اسم الجدول واختر الفصل' : 'Enter schedule name and select class');
      return;
    }

    setSubmitting(true);
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    
    try {
      const days = Object.entries(schedule)
        .filter(([_, periods]) => periods.length > 0)
        .map(([day, periods]) => ({
          day,
          periods: periods.map(p => ({
            ...p,
            class_id: data.class_id,
          }))
        }));

      if (days.length === 0) {
        nassaqWarning(isRTL ? 'أضف حصة واحدة على الأقل' : 'Add at least one period');
        setSubmitting(false);
        return;
      }

      const payload = {
        ...data,
        days,
      };

      const response = await api.post('/schedules/create', payload);
      
      if (response.data.success) {
        setResult(response.data);
        setSuccess(true);
        toast.success(isRTL ? 'تم إنشاء الجدول' : 'Schedule created');
      }
    } catch (error) {
      nassaqError(error.response?.data?.detail || (isRTL ? 'حدث خطأ أثناء إنشاء الجدول' : 'Error creating schedule'));
    } finally {
      setSubmitting(false);
    }
  };

  const handleReset = () => {
    setData({ name_ar: '', class_id: '', grade_id: '', academic_year: '2025-2026', semester: 1 });
    setSchedule({ sunday: [], monday: [], tuesday: [], wednesday: [], thursday: [] });
    setSuccess(false);
    setResult(null);
  };

  const handleClose = () => { 
    handleReset(); 
    if (onOpenChange) onOpenChange(false);
    else if (onClose) onClose();
  };

  const getDayName = (day) => options.days.find(d => d.code === day)?.[isRTL ? 'name_ar' : 'name_en'] || day;

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto" data-testid="create-schedule-wizard">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3 font-cairo text-xl">
            <div className="w-10 h-10 bg-amber-100 rounded-xl flex items-center justify-center">
              <Calendar className="h-5 w-5 text-amber-600" />
            </div>
            {isRTL ? 'إنشاء جدول مدرسي' : 'Create Schedule'}
          </DialogTitle>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-amber-600" />
          </div>
        ) : success && result ? (
          <div className="text-center space-y-6 py-8">
            <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto">
              <CheckCircle2 className="h-10 w-10 text-green-600" />
            </div>
            <div>
              <h3 className="text-2xl font-bold font-cairo text-green-700">{isRTL ? 'تم إنشاء الجدول!' : 'Schedule Created!'}</h3>
              <p className="text-lg mt-2 font-mono">{result.schedule_id}</p>
            </div>
            <div className="flex justify-center gap-3">
              <Button variant="outline" onClick={handleClose}>{isRTL ? 'إغلاق' : 'Close'}</Button>
              <Button onClick={handleReset} className="bg-amber-600 hover:bg-amber-700">{isRTL ? 'إنشاء جدول آخر' : 'Create Another'}</Button>
            </div>
          </div>
        ) : (
          <div className="space-y-6 py-4">
            {/* Basic Info */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label>{isRTL ? 'اسم الجدول' : 'Schedule Name'} <span className="text-red-500">*</span></Label>
                <Input
                  value={data.name_ar}
                  onChange={(e) => setData(p => ({ ...p, name_ar: e.target.value }))}
                  placeholder={isRTL ? 'جدول الصف الأول أ' : 'Grade 1-A Schedule'}
                  data-testid="schedule-name"
                />
              </div>
              <div className="space-y-2">
                <Label>{isRTL ? 'الصف' : 'Grade'}</Label>
                <Select value={data.grade_id} onValueChange={(val) => setData(p => ({ ...p, grade_id: val }))}>
                  <SelectTrigger data-testid="schedule-grade">
                    <SelectValue placeholder={isRTL ? 'اختر' : 'Select'} />
                  </SelectTrigger>
                  <SelectContent>
                    {options.grades.map((g) => (
                      <SelectItem key={g.id} value={g.id}>{isRTL ? g.name_ar : g.name_en}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>{isRTL ? 'الفصل' : 'Class'} <span className="text-red-500">*</span></Label>
                <Select value={data.class_id} onValueChange={(val) => setData(p => ({ ...p, class_id: val }))}>
                  <SelectTrigger data-testid="schedule-class">
                    <SelectValue placeholder={isRTL ? 'اختر' : 'Select'} />
                  </SelectTrigger>
                  <SelectContent>
                    {options.classes.map((c) => (
                      <SelectItem key={c.class_id} value={c.class_id}>{c.name_ar}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Schedule Grid */}
            <div className="space-y-4">
              <h4 className="font-bold font-cairo">{isRTL ? 'جدول الحصص' : 'Schedule Grid'}</h4>
              
              {['sunday', 'monday', 'tuesday', 'wednesday', 'thursday'].map((day) => (
                <Card key={day} className="overflow-hidden">
                  <CardHeader className="py-3 bg-muted/30">
                    <CardTitle className="flex items-center justify-between text-base">
                      <span className="font-tajawal">{getDayName(day)}</span>
                      <Button size="sm" variant="outline" onClick={() => addPeriod(day)}>
                        <Plus className="h-4 w-4 me-1" />
                        {isRTL ? 'حصة' : 'Period'}
                      </Button>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="py-3">
                    {schedule[day]?.length === 0 ? (
                      <p className="text-center text-muted-foreground text-sm py-2">
                        {isRTL ? 'لا توجد حصص' : 'No periods'}
                      </p>
                    ) : (
                      <div className="space-y-2">
                        {schedule[day]?.map((period, idx) => (
                          <div key={idx} className="flex items-center gap-2 p-2 bg-muted/20 rounded-lg">
                            <Badge variant="outline" className="shrink-0">{period.period_number}</Badge>
                            
                            <Select value={period.subject_id} onValueChange={(val) => updatePeriod(day, idx, 'subject_id', val)}>
                              <SelectTrigger className="flex-1 h-8">
                                <SelectValue placeholder={isRTL ? 'المادة' : 'Subject'} />
                              </SelectTrigger>
                              <SelectContent>
                                {options.subjects.map((s) => (
                                  <SelectItem key={s.id} value={s.id}>{isRTL ? s.name_ar : s.name_en}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                            
                            <Select value={period.teacher_id} onValueChange={(val) => updatePeriod(day, idx, 'teacher_id', val)}>
                              <SelectTrigger className="flex-1 h-8">
                                <SelectValue placeholder={isRTL ? 'المعلم' : 'Teacher'} />
                              </SelectTrigger>
                              <SelectContent>
                                {options.teachers.map((t) => (
                                  <SelectItem key={t.teacher_id} value={t.teacher_id}>{t.full_name_ar}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                            
                            <Input
                              type="time"
                              value={period.start_time}
                              onChange={(e) => updatePeriod(day, idx, 'start_time', e.target.value)}
                              className="w-24 h-8"
                            />
                            <span className="text-muted-foreground">-</span>
                            <Input
                              type="time"
                              value={period.end_time}
                              onChange={(e) => updatePeriod(day, idx, 'end_time', e.target.value)}
                              className="w-24 h-8"
                            />
                            
                            <Button size="icon" variant="ghost" className="h-8 w-8 text-red-500" onClick={() => removePeriod(day, idx)}>
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}

        {!loading && !success && (
          <DialogFooter className="flex justify-between gap-3 mt-4">
            <Button variant="ghost" onClick={handleClose}>{isRTL ? 'إلغاء' : 'Cancel'}</Button>
            <Button onClick={handleSubmit} disabled={submitting} className="bg-amber-600 hover:bg-amber-700">
              {submitting ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <CheckCircle2 className="h-4 w-4 me-2" />}
              {isRTL ? 'إنشاء الجدول' : 'Create Schedule'}
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default CreateScheduleWizard;
