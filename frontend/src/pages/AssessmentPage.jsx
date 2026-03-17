import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { Sidebar } from '../components/layout/Sidebar';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import {
  ClipboardList, Plus, Calendar, Trash2, X, ChevronDown, ChevronUp,
  Sun, Moon, Globe, MapPin, Users, Copy, BarChart3, FileText,
  Upload, Printer, XCircle, CheckCircle, Settings2, Loader2,
  GripVertical, BookOpen, Clock, Eye, RefreshCw, Pencil
} from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '../components/ui/dialog';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '../components/ui/table';

const AVAILABLE_CLASSES = [
  'الرابع - أ', 'الرابع - ب', 'الرابع - ج',
  'الخامس - أ', 'الخامس - ب', 'الخامس - ج',
  'السادس - أ', 'السادس - ب', 'السادس - ج',
];

const AVAILABLE_TEACHERS = [
  'أ. عبدالله المحمدي', 'أ. سعد الشمري', 'أ. خالد العتيبي',
  'أ. فهد الدوسري', 'أ. محمد القحطاني', 'أ. أحمد الغامدي'
];

const ORDINALS = ['الأولى', 'الثانية', 'الثالثة', 'الرابعة', 'الخامسة'];

async function fetchStudentsByClasses(api, assignedClasses, maxCount) {
  try {
    const res = await api.get('/student-management/', { params: { limit: maxCount || 50 } });
    const allStudents = Array.isArray(res.data?.students) ? res.data.students : (Array.isArray(res.data) ? res.data : []);
    const mapped = allStudents.map((s, i) => ({
      id: s.id || s._id || `stu-${i}`,
      name: s.full_name || s.name || '',
      nationalId: s.national_id || s.nationalId || '',
      grade: s.grade_name || s.class_name || (assignedClasses.length > 0 ? assignedClasses[i % assignedClasses.length] : ''),
      seatNumber: i + 1,
    }));
    const filtered = assignedClasses.length > 0
      ? mapped.filter(s => assignedClasses.some(cls => s.grade.includes(cls) || cls.includes(s.grade)))
      : mapped;
    const result = (filtered.length > 0 ? filtered : mapped).slice(0, maxCount || 50);
    result.sort((a, b) => a.name.localeCompare(b.name, 'ar'));
    result.forEach((s, i) => { s.seatNumber = i + 1; });
    return result;
  } catch {
    return [];
  }
}

function formatArabicDate(dateStr) {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    const months = ['يناير','فبراير','مارس','أبريل','مايو','يونيو','يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر'];
    const days = ['الأحد','الإثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت'];
    return `${days[d.getDay()]} ${d.getDate()} ${months[d.getMonth()]}`;
  } catch { return dateStr; }
}

const uid = () => `id-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const DEFAULT_PERIODS = [
  {
    id: uid(),
    title: 'الفترة الأولى',
    subjects: [
      { id: uid(), name: 'الرياضيات', date: '2026-03-20', time: '08:00 - 10:00', classes: ['الرابع - أ', 'الرابع - ب', 'الخامس - أ'], observers: ['أ. عبدالله المحمدي', 'أ. سعد الشمري'] },
      { id: uid(), name: 'العلوم', date: '2026-03-21', time: '08:00 - 10:00', classes: ['الرابع - أ', 'الخامس - ب', 'السادس - أ'], observers: ['أ. خالد العتيبي'] },
      { id: uid(), name: 'اللغة العربية', date: '2026-03-22', time: '10:30 - 12:30', classes: ['الرابع - ج', 'الخامس - ج', 'السادس - ج'], observers: ['أ. فهد الدوسري', 'أ. محمد القحطاني'] },
    ],
  },
  { id: uid(), title: 'الفترة الثانية', subjects: [] },
];

const DEFAULT_COMMITTEES = [
  {
    id: uid(), name: 'لجنة 1', location: 'قاعة A', rows: 5, cols: 6,
    classes: ['الرابع - أ'],
    students: [],
    cancelledSeats: [],
  }
];

const DEFAULT_FIELDS = [
  { id: 'f1', label: 'اسم الطالب', key: 'name', width: 30, enabled: true, isDefault: true },
  { id: 'f2', label: 'رقم الهوية', key: 'nationalId', width: 25, enabled: true, isDefault: true },
  { id: 'f3', label: 'رقم الجلوس', key: 'seatNumber', width: 20, enabled: true, isDefault: true },
  { id: 'f4', label: 'الصف', key: 'grade', width: 25, enabled: true, isDefault: true },
];

function ExamScheduleTab({ periods, setPeriods, isRTL, apiClasses, apiTeachers }) {
  const { nassaqError } = useNassaqAlert();
  const [expanded, setExpanded] = useState({});
  const [addSubjectOpen, setAddSubjectOpen] = useState(false);
  const [targetPeriodId, setTargetPeriodId] = useState(null);
  const [subForm, setSubForm] = useState({ name: '', date: '', time: '', classes: [], observers: [] });
  const [editingPeriodId, setEditingPeriodId] = useState(null);
  const [editingPeriodTitle, setEditingPeriodTitle] = useState('');
  const [editSubjectId, setEditSubjectId] = useState(null);

  const classOptions = apiClasses.length > 0
    ? apiClasses.map(c => c.name || c.class_name || `${c.grade_name} - ${c.section}`)
    : AVAILABLE_CLASSES;
  const teacherOptions = apiTeachers.length > 0
    ? apiTeachers.map(t => t.full_name || `${t.full_name_en || ''}`)
    : AVAILABLE_TEACHERS;

  const toggleExpand = (id) => setExpanded(p => ({ ...p, [id]: !p[id] }));

  const addPeriod = () => {
    const idx = periods.length;
    const title = idx < 5 ? `الفترة ${ORDINALS[idx]}` : `الفترة ${idx + 1}`;
    setPeriods([...periods, { id: uid(), title, subjects: [] }]);
    toast.success(isRTL ? `تمت إضافة ${title}` : `Added ${title}`);
  };

  const deletePeriod = (pid) => {
    setPeriods(periods.filter(p => p.id !== pid));
    toast.success(isRTL ? 'تم حذف الفترة' : 'Period deleted');
  };

  const startEditPeriod = (e, period) => {
    e.stopPropagation();
    setEditingPeriodId(period.id);
    setEditingPeriodTitle(period.title);
  };

  const savePeriodTitle = () => {
    if (editingPeriodTitle.trim()) {
      setPeriods(periods.map(p => p.id === editingPeriodId ? { ...p, title: editingPeriodTitle.trim() } : p));
      toast.success(isRTL ? 'تم تحديث اسم الفترة' : 'Period name updated');
    }
    setEditingPeriodId(null);
  };

  const openAddSubject = (pid) => {
    setTargetPeriodId(pid);
    setEditSubjectId(null);
    setSubForm({ name: '', date: '', time: '', classes: [], observers: [] });
    setAddSubjectOpen(true);
  };

  const openEditSubject = (pid, sub) => {
    setTargetPeriodId(pid);
    setEditSubjectId(sub.id);
    setSubForm({ name: sub.name, date: sub.date, time: sub.time, classes: [...sub.classes], observers: [...sub.observers] });
    setAddSubjectOpen(true);
  };

  const toggleClass = (cls) => {
    setSubForm(f => ({
      ...f,
      classes: f.classes.includes(cls) ? f.classes.filter(c => c !== cls) : [...f.classes, cls]
    }));
  };

  const toggleObserver = (obs) => {
    setSubForm(f => ({
      ...f,
      observers: f.observers.includes(obs) ? f.observers.filter(o => o !== obs) : [...f.observers, obs]
    }));
  };

  const saveSubject = () => {
    if (!subForm.name.trim()) {
      nassaqError(isRTL ? 'يرجى إدخال اسم المادة' : 'Please enter subject name');
      return;
    }
    if (editSubjectId) {
      setPeriods(periods.map(p => {
        if (p.id !== targetPeriodId) return p;
        return { ...p, subjects: p.subjects.map(s => s.id === editSubjectId ? { ...s, ...subForm } : s) };
      }));
      toast.success(isRTL ? 'تم تحديث المادة' : 'Subject updated');
    } else {
      setPeriods(periods.map(p => {
        if (p.id !== targetPeriodId) return p;
        return { ...p, subjects: [...p.subjects, { id: uid(), ...subForm }] };
      }));
      toast.success(isRTL ? 'تمت إضافة المادة' : 'Subject added');
    }
    setAddSubjectOpen(false);
  };

  const deleteSubject = (pid, sid) => {
    setPeriods(periods.map(p => {
      if (p.id !== pid) return p;
      return { ...p, subjects: p.subjects.filter(s => s.id !== sid) };
    }));
    toast.success(isRTL ? 'تم حذف المادة' : 'Subject deleted');
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-bold text-gray-800 dark:text-gray-200 flex items-center gap-2">
          <Calendar className="h-5 w-5 text-indigo-500" />
          {isRTL ? 'جدول الاختبارات' : 'Exam Schedule'}
        </h3>
        <Button onClick={addPeriod} className="bg-indigo-600 hover:bg-indigo-700" data-testid="button-add-period">
          <Plus className="h-4 w-4 me-1" />{isRTL ? 'إضافة فترة' : 'Add Period'}
        </Button>
      </div>

      {periods.map(period => (
        <Card key={period.id} className="border border-gray-200 dark:border-gray-700 overflow-hidden" data-testid={`card-period-${period.id}`}>
          <div
            className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 text-white cursor-pointer"
            onClick={() => toggleExpand(period.id)}
          >
            <div className="flex items-center gap-3">
              {expanded[period.id] ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
              {editingPeriodId === period.id ? (
                <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                  <Input value={editingPeriodTitle} onChange={e => setEditingPeriodTitle(e.target.value)}
                    className="h-7 w-40 text-sm bg-white/20 border-white/30 text-white placeholder:text-white/50"
                    onKeyDown={e => { if (e.key === 'Enter') savePeriodTitle(); if (e.key === 'Escape') setEditingPeriodId(null); }}
                    autoFocus />
                  <Button variant="ghost" size="icon" className="h-6 w-6 text-white hover:bg-white/10" onClick={savePeriodTitle}>
                    <CheckCircle className="h-4 w-4" />
                  </Button>
                </div>
              ) : (
                <span className="font-bold">{period.title}</span>
              )}
              <Badge variant="secondary" className="bg-white/20 text-white text-[10px]">
                {period.subjects.length} {isRTL ? 'مادة' : 'subjects'}
              </Badge>
            </div>
            <div className="flex items-center gap-0.5">
              <Button variant="ghost" size="icon" className="h-7 w-7 text-white/80 hover:text-white hover:bg-white/10"
                onClick={(e) => startEditPeriod(e, period)} title={isRTL ? 'تعديل' : 'Edit'}>
                <Pencil className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="icon" className="h-7 w-7 text-white/80 hover:text-white hover:bg-white/10"
                onClick={(e) => { e.stopPropagation(); deletePeriod(period.id); }} data-testid={`button-delete-period-${period.id}`}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {expanded[period.id] && (
            <CardContent className="p-4">
              <div className="flex justify-end mb-3">
                <Button size="sm" variant="outline" onClick={() => openAddSubject(period.id)} data-testid={`button-add-subject-${period.id}`}>
                  <Plus className="h-3.5 w-3.5 me-1" />{isRTL ? 'إضافة مادة' : 'Add Subject'}
                </Button>
              </div>
              {period.subjects.length === 0 ? (
                <p className="text-center text-sm text-muted-foreground py-6">{isRTL ? 'لا توجد مواد مضافة بعد' : 'No subjects added yet'}</p>
              ) : (
                <div className="overflow-x-auto rounded-lg border">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-gray-50 dark:bg-gray-800">
                        <TableHead className="font-bold">{isRTL ? 'المادة' : 'Subject'}</TableHead>
                        <TableHead className="font-bold">{isRTL ? 'التاريخ' : 'Date'}</TableHead>
                        <TableHead className="font-bold">{isRTL ? 'الوقت' : 'Time'}</TableHead>
                        <TableHead className="font-bold">{isRTL ? 'الفصول' : 'Classes'}</TableHead>
                        <TableHead className="font-bold">{isRTL ? 'الملاحظون' : 'Observers'}</TableHead>
                        <TableHead className="w-10"></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {period.subjects.map(sub => (
                        <TableRow key={sub.id}>
                          <TableCell className="font-medium">{sub.name}</TableCell>
                          <TableCell className="text-sm">{formatArabicDate(sub.date)}</TableCell>
                          <TableCell><Badge variant="outline" className="text-xs">{sub.time}</Badge></TableCell>
                          <TableCell>
                            <div className="flex flex-wrap gap-1">
                              {sub.classes.map(c => <Badge key={c} variant="secondary" className="text-[10px]">{c}</Badge>)}
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="flex flex-wrap gap-1">
                              {sub.observers.map(o => <Badge key={o} className="bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 text-[10px]">{o}</Badge>)}
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="flex gap-0.5">
                              <Button variant="ghost" size="icon" className="h-7 w-7 text-blue-500 hover:text-blue-700"
                                onClick={() => openEditSubject(period.id, sub)} data-testid={`button-edit-subject-${sub.id}`}>
                                <Pencil className="h-3.5 w-3.5" />
                              </Button>
                              <Button variant="ghost" size="icon" className="h-7 w-7 text-red-500 hover:text-red-700"
                                onClick={() => deleteSubject(period.id, sub.id)} data-testid={`button-delete-subject-${sub.id}`}>
                                <Trash2 className="h-3.5 w-3.5" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          )}
        </Card>
      ))}

      <Dialog open={addSubjectOpen} onOpenChange={setAddSubjectOpen}>
        <DialogContent className="sm:max-w-[600px] max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editSubjectId ? (isRTL ? 'تعديل مادة اختبار' : 'Edit Exam Subject') : (isRTL ? 'إضافة مادة اختبار' : 'Add Exam Subject')}</DialogTitle>
            <DialogDescription>{isRTL ? 'أدخل تفاصيل المادة والتاريخ والفصول والملاحظين' : 'Enter subject details, date, classes and observers'}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>{isRTL ? 'اسم المادة' : 'Subject Name'}</Label>
              <Input value={subForm.name} onChange={e => setSubForm(f => ({ ...f, name: e.target.value }))}
                placeholder={isRTL ? 'مثال: الرياضيات' : 'e.g. Mathematics'} data-testid="input-subject-name" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>{isRTL ? 'التاريخ' : 'Date'}</Label>
                <Input type="date" value={subForm.date} onChange={e => setSubForm(f => ({ ...f, date: e.target.value }))} data-testid="input-subject-date" />
              </div>
              <div>
                <Label>{isRTL ? 'الوقت' : 'Time'}</Label>
                <Input value={subForm.time} onChange={e => setSubForm(f => ({ ...f, time: e.target.value }))}
                  placeholder="08:00 - 10:00" data-testid="input-subject-time" />
              </div>
            </div>
            <div>
              <Label className="mb-2 block font-bold">{isRTL ? 'الفصول المشاركة' : 'Participating Classes'}</Label>
              <div className="grid grid-cols-3 gap-2">
                {classOptions.map(cls => (
                  <label key={cls} className="flex items-center gap-2 p-2 rounded-lg border hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer text-sm">
                    <Checkbox checked={subForm.classes.includes(cls)} onCheckedChange={() => toggleClass(cls)} data-testid={`checkbox-class-${cls}`} />
                    {cls}
                  </label>
                ))}
              </div>
            </div>
            <div>
              <Label className="mb-2 block font-bold">{isRTL ? 'الملاحظون (المراقبون)' : 'Observers'}</Label>
              <div className="grid grid-cols-2 gap-2">
                {teacherOptions.map(t => (
                  <label key={t} className="flex items-center gap-2 p-2 rounded-lg border hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer text-sm">
                    <Checkbox checked={subForm.observers.includes(t)} onCheckedChange={() => toggleObserver(t)} data-testid={`checkbox-observer-${t}`} />
                    {t}
                  </label>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddSubjectOpen(false)}>{isRTL ? 'إلغاء' : 'Cancel'}</Button>
            <Button onClick={saveSubject} className="bg-indigo-600 hover:bg-indigo-700" data-testid="button-save-subject">
              {editSubjectId ? (isRTL ? 'حفظ التعديلات' : 'Save Changes') : (isRTL ? 'إضافة' : 'Add')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function CommitteesTab({ committees, setCommittees, isRTL, apiClasses, apiTeachers, api }) {
  const { nassaqError } = useNassaqAlert();
  const [selectedId, setSelectedId] = useState(null);
  const [addOpen, setAddOpen] = useState(false);
  const [addMode, setAddMode] = useState('single');
  const [comForm, setComForm] = useState({ name: '', location: '', rows: 5, cols: 6, classes: [] });
  const [statsOpen, setStatsOpen] = useState(false);
  const [statsCommittee, setStatsCommittee] = useState(null);
  const [reportOpen, setReportOpen] = useState(false);
  const [reportCommittee, setReportCommittee] = useState(null);
  const [copyOpen, setCopyOpen] = useState(false);
  const [copySource, setCopySource] = useState(null);
  const [copyClasses, setCopyClasses] = useState([]);
  const [importOpen, setImportOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (committees.length > 0 && (!selectedId || !committees.find(c => c.id === selectedId))) {
      setSelectedId(committees[0].id);
    }
  }, [committees, selectedId]);

  const classOptions = apiClasses.length > 0
    ? apiClasses.map(c => c.name || c.class_name || `${c.grade_name} - ${c.section}`)
    : AVAILABLE_CLASSES;

  const selected = committees.find(c => c.id === selectedId);

  const getActiveSeats = useCallback((com) => {
    if (!com) return [];
    const seats = [];
    for (let col = 0; col < com.cols; col++) {
      for (let row = 0; row < com.rows; row++) {
        const key = `${row}-${col}`;
        if (!com.cancelledSeats.includes(key)) {
          seats.push({ row, col, key });
        }
      }
    }
    return seats;
  }, []);

  const saveCommitteeToServer = async (committee) => {
    try {
      await api.put(`/exam-committees/${committee.id}`, {
        name: committee.name,
        location: committee.location,
        rows: committee.rows,
        cols: committee.cols,
        classes: committee.classes,
        students: committee.students,
        cancelledSeats: committee.cancelledSeats,
      });
    } catch (e) {
      nassaqError(e.response?.data?.detail || (isRTL ? 'فشل الحفظ' : 'Save failed'));
    }
  };

  const toggleSeat = async (key) => {
    if (!selected) return;
    const updated = committees.map(c => {
      if (c.id !== selected.id) return c;
      const cancelled = c.cancelledSeats.includes(key)
        ? c.cancelledSeats.filter(k => k !== key)
        : [...c.cancelledSeats, key];
      return { ...c, cancelledSeats: cancelled };
    });
    setCommittees(updated);
    const updatedCom = updated.find(c => c.id === selected.id);
    if (updatedCom) await saveCommitteeToServer(updatedCom);
  };

  const addCommittee = async () => {
    setSaving(true);
    try {
      if (addMode === 'single') {
        const name = comForm.name.trim() || `لجنة ${committees.length + 1}`;
        const loc = comForm.location.trim() || '';
        const capacity = comForm.rows * comForm.cols;
        const classes = comForm.classes.length > 0 ? comForm.classes : ['الرابع - أ'];
        const students = await fetchStudentsByClasses(api, classes, capacity);
        const res = await api.post('/exam-committees', {
          name, location: loc, rows: comForm.rows, cols: comForm.cols,
          classes, students, cancelledSeats: [],
        });
        const saved = res.data?.committee;
        if (saved) {
          setCommittees(prev => [...prev, saved]);
          setSelectedId(saved.id);
        }
        toast.success(isRTL ? `تمت إضافة ${name}` : `Added ${name}`);
      } else {
        if (comForm.classes.length === 0) {
          nassaqError(isRTL ? 'اختر فصلاً واحداً على الأقل' : 'Select at least one class');
          setSaving(false);
          return;
        }
        const bulkData = await Promise.all(comForm.classes.map(async (cls, i) => {
          const idx = committees.length + i + 1;
          const letterIdx = committees.length + i;
          const letter = String.fromCharCode(65 + (letterIdx % 26));
          const capacity = comForm.rows * comForm.cols;
          const students = await fetchStudentsByClasses(api, [cls], capacity);
          return {
            name: `لجنة ${idx}`, location: `قاعة ${letter}`,
            rows: comForm.rows, cols: comForm.cols, classes: [cls],
            students, cancelledSeats: [],
          };
        }));
        const res = await api.post('/exam-committees/bulk', bulkData);
        const saved = res.data?.committees || [];
        if (saved.length > 0) {
          setCommittees(prev => [...prev, ...saved]);
          setSelectedId(saved[0].id);
        }
        toast.success(isRTL ? `تم إنشاء ${saved.length} لجنة` : `Created ${saved.length} committees`);
      }
      setAddOpen(false);
    } catch (e) {
      nassaqError(e.response?.data?.detail || (isRTL ? 'فشل إنشاء اللجنة' : 'Failed to create committee'));
    } finally {
      setSaving(false);
    }
  };

  const deleteCommittee = async (cid) => {
    try {
      await api.delete(`/exam-committees/${cid}`);
      setCommittees(prev => prev.filter(c => c.id !== cid));
      if (selectedId === cid) setSelectedId(committees.find(c => c.id !== cid)?.id || null);
      toast.success(isRTL ? 'تم حذف اللجنة' : 'Committee deleted');
    } catch (e) {
      nassaqError(e.response?.data?.detail || (isRTL ? 'فشل الحذف' : 'Delete failed'));
    }
  };

  const openStats = (com) => { setStatsCommittee(com); setStatsOpen(true); };
  const openReport = (com) => { setReportCommittee(com); setReportOpen(true); };
  const openCopy = (com) => { setCopySource(com); setCopyClasses([]); setCopyOpen(true); };

  const doCopy = async () => {
    if (!copySource || copyClasses.length === 0) {
      nassaqError(isRTL ? 'اختر فصلاً واحداً على الأقل' : 'Select at least one class');
      return;
    }
    const capacity = copySource.rows * copySource.cols;
    const students = await fetchStudentsByClasses(api, copyClasses, capacity);
    try {
      const res = await api.post('/exam-committees', {
        name: `${copySource.name} (نسخة)`, location: copySource.location,
        rows: copySource.rows, cols: copySource.cols, classes: copyClasses,
        students, cancelledSeats: [],
      });
      const saved = res.data?.committee;
      if (saved) {
        setCommittees(prev => [...prev, saved]);
        setSelectedId(saved.id);
      }
      setCopyOpen(false);
      toast.success(isRTL ? 'تم نسخ اللجنة' : 'Committee copied');
    } catch (e) {
      nassaqError(e.response?.data?.detail || (isRTL ? 'فشل النسخ' : 'Copy failed'));
    }
  };

  const importStudents = async () => {
    if (!selected) return;
    const capacity = selected.rows * selected.cols;
    const students = await fetchStudentsByClasses(api, selected.classes, capacity);
    const updated = committees.map(c => c.id !== selected.id ? c : { ...c, students, cancelledSeats: [] });
    setCommittees(updated);
    const updatedCom = updated.find(c => c.id === selected.id);
    if (updatedCom) await saveCommitteeToServer(updatedCom);
    setImportOpen(false);
    toast.success(isRTL ? 'تم استيراد بيانات الطلاب' : 'Students imported');
  };

  const computeStats = (com) => {
    if (!com) return {};
    const total = com.rows * com.cols;
    const cancelled = com.cancelledSeats.length;
    const active = total - cancelled;
    const occupied = Math.min(com.students.length, active);
    const empty = active - occupied;
    const pct = active > 0 ? Math.round((occupied / active) * 100) : 0;
    const classDistribution = {};
    com.students.forEach(s => { classDistribution[s.grade] = (classDistribution[s.grade] || 0) + 1; });
    return { total, cancelled, active, occupied, empty, pct, classDistribution };
  };

  const renderGrid = () => {
    if (!selected) return <div className="flex items-center justify-center h-64 text-muted-foreground">{isRTL ? 'اختر لجنة لعرض مخطط الجلوس' : 'Select a committee to view seating layout'}</div>;
    const activeSeats = getActiveSeats(selected);
    const seatMap = {};
    activeSeats.forEach((seat, idx) => {
      if (idx < selected.students.length) {
        seatMap[seat.key] = selected.students[idx];
      }
    });

    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="font-bold text-sm">{selected.name} — {selected.location}</h4>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => setImportOpen(true)} data-testid="button-import">
              <Upload className="h-3.5 w-3.5 me-1" />{isRTL ? 'استيراد' : 'Import'}
            </Button>
            <Button size="sm" variant="outline" onClick={() => openReport(selected)} data-testid="button-report">
              <FileText className="h-3.5 w-3.5 me-1" />{isRTL ? 'تقرير' : 'Report'}
            </Button>
          </div>
        </div>
        <div className="bg-gray-800 text-white text-center py-1.5 rounded-t-lg text-sm font-bold">
          {isRTL ? 'السبورة' : 'Whiteboard'}
        </div>
        <div className="grid gap-1.5 p-3 bg-gray-50 dark:bg-gray-900 rounded-b-lg border" style={{ gridTemplateColumns: `repeat(${selected.cols}, 1fr)` }}>
          {Array.from({ length: selected.rows }).map((_, row) =>
            Array.from({ length: selected.cols }).map((_, col) => {
              const key = `${row}-${col}`;
              const isCancelled = selected.cancelledSeats.includes(key);
              const student = seatMap[key];
              const activeIdx = activeSeats.findIndex(s => s.key === key);
              const isEmpty = !isCancelled && !student;

              return (
                <div key={key} data-testid={`seat-${key}`}
                  onClick={() => toggleSeat(key)}
                  className={`relative p-2 rounded-lg border-2 text-center cursor-pointer transition-all min-h-[60px] flex flex-col items-center justify-center text-[11px] ${
                    isCancelled ? 'bg-red-50 dark:bg-red-950/30 border-red-300 dark:border-red-800 opacity-60' :
                    student ? 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-600 hover:border-indigo-400 hover:shadow-sm' :
                    'bg-gray-100 dark:bg-gray-800/50 border-dashed border-gray-300 dark:border-gray-600'
                  }`}>
                  {isCancelled ? (
                    <XCircle className="h-5 w-5 text-red-500" />
                  ) : student ? (
                    <>
                      <span className="font-medium leading-tight">{student.name.split(' ').slice(0, 2).join(' ')}</span>
                      <Badge className="mt-1 text-[9px] bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400">{student.seatNumber}</Badge>
                    </>
                  ) : (
                    <span className="text-muted-foreground">{isRTL ? 'فارغ' : 'Empty'}</span>
                  )}
                </div>
              );
            })
          )}
        </div>
        <p className="text-[11px] text-muted-foreground text-center">{isRTL ? 'اضغط على أي مقعد لإلغائه أو إعادة تفعيله' : 'Click any seat to cancel or restore it'}</p>
        <div className="flex justify-center gap-4 text-[11px]">
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded border bg-white dark:bg-gray-800"></span> {isRTL ? 'مشغول' : 'Occupied'}</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded border-2 border-dashed bg-gray-100"></span> {isRTL ? 'فارغ' : 'Empty'}</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-200"></span> {isRTL ? 'ملغى' : 'Cancelled'}</span>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-bold text-gray-800 dark:text-gray-200 flex items-center gap-2">
          <Users className="h-5 w-5 text-indigo-500" />
          {isRTL ? 'اللجان' : 'Committees'}
        </h3>
        <Button onClick={() => { setComForm({ name: '', location: '', rows: 5, cols: 6, classes: [] }); setAddMode('single'); setAddOpen(true); }}
          className="bg-indigo-600 hover:bg-indigo-700" data-testid="button-add-committee">
          <Plus className="h-4 w-4 me-1" />{isRTL ? 'إضافة لجنة' : 'Add Committee'}
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        <div className="lg:col-span-4 space-y-2 max-h-[600px] overflow-y-auto">
          {committees.map(com => (
            <Card key={com.id} data-testid={`card-committee-${com.id}`}
              className={`cursor-pointer transition-all hover:shadow-md ${selectedId === com.id ? 'ring-2 ring-indigo-500 border-indigo-400' : 'border-gray-200 dark:border-gray-700'}`}
              onClick={() => setSelectedId(com.id)}>
              <CardContent className="p-3">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <h4 className="font-bold text-sm">{com.name}</h4>
                    {com.location && (
                      <p className="text-xs text-muted-foreground flex items-center gap-1 mt-0.5">
                        <MapPin className="h-3 w-3" />{com.location}
                      </p>
                    )}
                    <div className="flex items-center gap-2 mt-1.5 text-[11px] text-muted-foreground">
                      <span className="flex items-center gap-1"><Users className="h-3 w-3" />{com.students.length}</span>
                      <span>{com.rows}×{com.cols}</span>
                    </div>
                    <div className="flex flex-wrap gap-1 mt-1.5">
                      {com.classes.map(c => <Badge key={c} variant="secondary" className="text-[9px]">{c}</Badge>)}
                    </div>
                  </div>
                  <div className="flex gap-0.5 shrink-0">
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={(e) => { e.stopPropagation(); openCopy(com); }} title={isRTL ? 'نسخ' : 'Copy'}>
                      <Copy className="h-3.5 w-3.5" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={(e) => { e.stopPropagation(); openStats(com); }} title={isRTL ? 'إحصائيات' : 'Statistics'}>
                      <BarChart3 className="h-3.5 w-3.5" />
                    </Button>
                    <Button variant="ghost" size="icon" className="h-7 w-7 text-red-500 hover:text-red-700" onClick={(e) => { e.stopPropagation(); deleteCommittee(com.id); }}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
          {committees.length === 0 && (
            <p className="text-center text-sm text-muted-foreground py-8">{isRTL ? 'لا توجد لجان بعد' : 'No committees yet'}</p>
          )}
        </div>
        <div className="lg:col-span-8">
          <Card className="border-gray-200 dark:border-gray-700">
            <CardContent className="p-4">{renderGrid()}</CardContent>
          </Card>
        </div>
      </div>

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent className="sm:max-w-[550px] max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{isRTL ? 'إضافة لجنة' : 'Add Committee'}</DialogTitle>
            <DialogDescription>{isRTL ? 'أنشئ لجنة واحدة أو عدة لجان من نمط' : 'Create a single committee or multiple from a template'}</DialogDescription>
          </DialogHeader>
          <div className="flex gap-2 mb-4">
            <Button variant={addMode === 'single' ? 'default' : 'outline'} size="sm" onClick={() => setAddMode('single')} className={addMode === 'single' ? 'bg-indigo-600' : ''}>
              {isRTL ? 'لجنة واحدة' : 'Single'}
            </Button>
            <Button variant={addMode === 'template' ? 'default' : 'outline'} size="sm" onClick={() => setAddMode('template')} className={addMode === 'template' ? 'bg-indigo-600' : ''}>
              {isRTL ? 'إنشاء من نمط' : 'From Template'}
            </Button>
          </div>
          <div className="space-y-4">
            {addMode === 'single' && (
              <>
                <div>
                  <Label>{isRTL ? 'اسم اللجنة' : 'Committee Name'}</Label>
                  <Input value={comForm.name} onChange={e => setComForm(f => ({ ...f, name: e.target.value }))} placeholder={`لجنة ${committees.length + 1}`} data-testid="input-committee-name" />
                </div>
                <div>
                  <Label>{isRTL ? 'الموقع' : 'Location'}</Label>
                  <Input value={comForm.location} onChange={e => setComForm(f => ({ ...f, location: e.target.value }))} placeholder={isRTL ? 'مثال: قاعة B' : 'e.g. Hall B'} data-testid="input-committee-location" />
                </div>
              </>
            )}
            {addMode === 'template' && (
              <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800 text-sm text-blue-700 dark:text-blue-400">
                {isRTL ? 'سيتم تسمية اللجان تلقائياً (لجنة 2، لجنة 3...) وتعيين مواقعها (قاعة B، قاعة C...)' : 'Committees will be auto-named and located'}
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>{isRTL ? 'عدد الصفوف' : 'Rows'}</Label>
                <Input type="number" min={1} max={20} value={comForm.rows} onChange={e => setComForm(f => ({ ...f, rows: Math.max(1, parseInt(e.target.value) || 1) }))} data-testid="input-rows" />
              </div>
              <div>
                <Label>{isRTL ? 'عدد الأعمدة' : 'Columns'}</Label>
                <Input type="number" min={1} max={20} value={comForm.cols} onChange={e => setComForm(f => ({ ...f, cols: Math.max(1, parseInt(e.target.value) || 1) }))} data-testid="input-cols" />
              </div>
            </div>
            <div className="text-center p-2 bg-indigo-50 dark:bg-indigo-950/20 rounded-lg text-sm font-medium text-indigo-700 dark:text-indigo-400">
              {isRTL ? 'السعة:' : 'Capacity:'} {comForm.rows * comForm.cols} {isRTL ? 'مقعد · الترتيب عمودي أبجدي تلقائي' : 'seats · column-first alphabetical order'}
            </div>
            <div>
              <Label className="mb-2 block font-bold">{isRTL ? 'الفصول' : 'Classes'}</Label>
              <div className="grid grid-cols-3 gap-2">
                {classOptions.map(cls => (
                  <label key={cls} className="flex items-center gap-2 p-2 rounded-lg border hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer text-sm">
                    <Checkbox checked={comForm.classes.includes(cls)} onCheckedChange={() => setComForm(f => ({
                      ...f, classes: f.classes.includes(cls) ? f.classes.filter(c => c !== cls) : [...f.classes, cls]
                    }))} />
                    {cls}
                  </label>
                ))}
              </div>
            </div>
            {addMode === 'template' && comForm.classes.length > 0 && (
              <div className="text-center text-sm font-medium text-indigo-600 dark:text-indigo-400">
                {isRTL ? `سيتم إنشاء ${comForm.classes.length} لجنة` : `Will create ${comForm.classes.length} committees`}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddOpen(false)}>{isRTL ? 'إلغاء' : 'Cancel'}</Button>
            <Button onClick={addCommittee} disabled={saving} className="bg-indigo-600 hover:bg-indigo-700" data-testid="button-create-committee">
              {saving ? <Loader2 className="h-4 w-4 animate-spin me-1" /> : null}
              {addMode === 'template' && comForm.classes.length > 0 ? (isRTL ? `إنشاء ${comForm.classes.length} لجنة` : `Create ${comForm.classes.length}`) : (isRTL ? 'إضافة' : 'Add')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={statsOpen} onOpenChange={setStatsOpen}>
        <DialogContent className="sm:max-w-[500px]">
          <DialogHeader>
            <DialogTitle>{isRTL ? 'إحصائيات اللجنة' : 'Committee Statistics'}</DialogTitle>
            {statsCommittee && <DialogDescription>{statsCommittee.name} — {statsCommittee.location}</DialogDescription>}
          </DialogHeader>
          {statsCommittee && (() => {
            const s = computeStats(statsCommittee);
            return (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div className="p-3 rounded-xl bg-blue-50 dark:bg-blue-950/20 border border-blue-200 text-center">
                    <p className="text-2xl font-bold text-blue-600">{s.total}</p>
                    <p className="text-xs text-blue-500">{isRTL ? 'إجمالي المقاعد' : 'Total Seats'}</p>
                  </div>
                  <div className="p-3 rounded-xl bg-green-50 dark:bg-green-950/20 border border-green-200 text-center">
                    <p className="text-2xl font-bold text-green-600">{s.occupied}</p>
                    <p className="text-xs text-green-500">{isRTL ? 'مقاعد مشغولة' : 'Occupied'}</p>
                  </div>
                  <div className="p-3 rounded-xl bg-gray-50 dark:bg-gray-800 border border-gray-200 text-center">
                    <p className="text-2xl font-bold text-gray-600">{s.empty}</p>
                    <p className="text-xs text-gray-500">{isRTL ? 'مقاعد فارغة' : 'Empty'}</p>
                  </div>
                  <div className="p-3 rounded-xl bg-red-50 dark:bg-red-950/20 border border-red-200 text-center">
                    <p className="text-2xl font-bold text-red-600">{s.cancelled}</p>
                    <p className="text-xs text-red-500">{isRTL ? 'مقاعد ملغاة' : 'Cancelled'}</p>
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-indigo-50 dark:bg-indigo-950/20 border border-indigo-200">
                  <div className="flex justify-between text-sm mb-1">
                    <span className="font-medium text-indigo-700">{isRTL ? 'نسبة الإشغال' : 'Occupancy'}</span>
                    <span className="font-bold text-indigo-700">{s.pct}%</span>
                  </div>
                  <div className="w-full bg-indigo-200 rounded-full h-2.5">
                    <div className="bg-indigo-600 h-2.5 rounded-full transition-all" style={{ width: `${s.pct}%` }}></div>
                  </div>
                </div>
                {Object.keys(s.classDistribution).length > 0 && (
                  <div>
                    <h5 className="font-bold text-sm mb-2">{isRTL ? 'توزيع الفصول' : 'Class Distribution'}</h5>
                    <div className="space-y-1.5">
                      {Object.entries(s.classDistribution).map(([cls, count]) => (
                        <div key={cls} className="flex items-center justify-between text-sm">
                          <span>{cls}</span>
                          <Badge variant="secondary">{count} {isRTL ? 'طالب' : 'students'}</Badge>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })()}
        </DialogContent>
      </Dialog>

      <Dialog open={reportOpen} onOpenChange={setReportOpen}>
        <DialogContent className="sm:max-w-[700px] max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{isRTL ? 'تقرير اللجنة' : 'Committee Report'}</DialogTitle>
          </DialogHeader>
          {reportCommittee && (
            <div className="space-y-4" id="committee-report-content">
              <div className="p-4 rounded-xl bg-indigo-50 dark:bg-indigo-950/20 border border-indigo-200">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div><span className="font-bold">{isRTL ? 'اسم اللجنة:' : 'Name:'}</span> {reportCommittee.name}</div>
                  <div><span className="font-bold">{isRTL ? 'الموقع:' : 'Location:'}</span> {reportCommittee.location}</div>
                  <div><span className="font-bold">{isRTL ? 'المخطط:' : 'Layout:'}</span> {reportCommittee.rows}×{reportCommittee.cols}</div>
                  <div><span className="font-bold">{isRTL ? 'عدد الطلاب:' : 'Students:'}</span> {reportCommittee.students.length}</div>
                  <div className="col-span-2"><span className="font-bold">{isRTL ? 'الفصول:' : 'Classes:'}</span> {reportCommittee.classes.join('، ')}</div>
                </div>
              </div>
              <div className="overflow-x-auto rounded-lg border">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-gray-50 dark:bg-gray-800">
                      <TableHead className="w-12 font-bold">#</TableHead>
                      <TableHead className="font-bold">{isRTL ? 'الاسم' : 'Name'}</TableHead>
                      <TableHead className="font-bold">{isRTL ? 'رقم الهوية' : 'National ID'}</TableHead>
                      <TableHead className="font-bold">{isRTL ? 'رقم الجلوس' : 'Seat #'}</TableHead>
                      <TableHead className="font-bold">{isRTL ? 'الصف' : 'Grade'}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {reportCommittee.students.map((stu, i) => (
                      <TableRow key={stu.id} data-testid={`row-report-${i}`}>
                        <TableCell className="text-sm">{i + 1}</TableCell>
                        <TableCell className="font-medium text-sm">{stu.name}</TableCell>
                        <TableCell className="text-sm font-mono">{stu.nationalId}</TableCell>
                        <TableCell><Badge variant="outline" className="text-xs">{stu.seatNumber}</Badge></TableCell>
                        <TableCell className="text-sm">{stu.grade}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              <div className="flex justify-end">
                <Button onClick={() => window.print()} className="bg-indigo-600 hover:bg-indigo-700">
                  <Printer className="h-4 w-4 me-1" />{isRTL ? 'طباعة التقرير' : 'Print Report'}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={copyOpen} onOpenChange={setCopyOpen}>
        <DialogContent className="sm:max-w-[450px]">
          <DialogHeader>
            <DialogTitle>{isRTL ? 'نسخ اللجنة' : 'Copy Committee'}</DialogTitle>
            {copySource && <DialogDescription>{isRTL ? `نسخ مخطط ${copySource.name} مع فصول جديدة` : `Copy layout of ${copySource.name} with new classes`}</DialogDescription>}
          </DialogHeader>
          <div>
            <Label className="mb-2 block font-bold">{isRTL ? 'اختر الفصول الجديدة' : 'Select New Classes'}</Label>
            <div className="grid grid-cols-3 gap-2">
              {classOptions.map(cls => (
                <label key={cls} className="flex items-center gap-2 p-2 rounded-lg border hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer text-sm">
                  <Checkbox checked={copyClasses.includes(cls)} onCheckedChange={() => setCopyClasses(p => p.includes(cls) ? p.filter(c => c !== cls) : [...p, cls])} />
                  {cls}
                </label>
              ))}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCopyOpen(false)}>{isRTL ? 'إلغاء' : 'Cancel'}</Button>
            <Button onClick={doCopy} className="bg-indigo-600 hover:bg-indigo-700">{isRTL ? 'نسخ' : 'Copy'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={importOpen} onOpenChange={setImportOpen}>
        <DialogContent className="sm:max-w-[450px]">
          <DialogHeader>
            <DialogTitle>{isRTL ? 'استيراد الطلاب' : 'Import Students'}</DialogTitle>
            <DialogDescription>{isRTL ? 'قم بتحميل ملف أو استخدم بيانات تجريبية' : 'Upload a file or use sample data'}</DialogDescription>
          </DialogHeader>
          <div className="border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-xl p-8 text-center">
            <Upload className="h-10 w-10 mx-auto text-muted-foreground mb-3" />
            <p className="text-sm text-muted-foreground mb-1">{isRTL ? 'اسحب وأفلت الملف هنا' : 'Drag and drop file here'}</p>
            <p className="text-xs text-muted-foreground">{isRTL ? 'يدعم: Excel, PDF, صور' : 'Supports: Excel, PDF, Images'}</p>
          </div>
          <Button variant="outline" onClick={importStudents} className="w-full" data-testid="button-import-sample">
            <RefreshCw className="h-4 w-4 me-1" />{isRTL ? 'استيراد طلاب من النظام' : 'Import Students from System'}
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SeatingCardsTab({ committees, isRTL, api }) {
  const [fields, setFields] = useState(DEFAULT_FIELDS);
  const [cardWidth, setCardWidth] = useState(300);
  const [cardHeight, setCardHeight] = useState(180);
  const [selectedComId, setSelectedComId] = useState('');
  const [addFieldOpen, setAddFieldOpen] = useState(false);
  const [newFieldLabel, setNewFieldLabel] = useState('');
  const [settingsLoaded, setSettingsLoaded] = useState(false);
  const saveTimerRef = useRef(null);

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const res = await api.get('/seating-card-settings');
        const s = res.data?.settings;
        if (s) {
          if (s.fields && s.fields.length > 0) setFields(s.fields);
          if (s.cardWidth) setCardWidth(s.cardWidth);
          if (s.cardHeight) setCardHeight(s.cardHeight);
        }
      } catch (e) {
        console.error('Failed to load seating card settings:', e);
      } finally {
        setSettingsLoaded(true);
      }
    };
    loadSettings();
  }, [api]);

  const saveSettings = useCallback((newFields, newWidth, newHeight) => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(async () => {
      try {
        await api.put('/seating-card-settings', {
          fields: newFields,
          cardWidth: newWidth,
          cardHeight: newHeight,
        });
      } catch (e) {
        console.error('Failed to save seating card settings:', e);
      }
    }, 600);
  }, [api]);

  useEffect(() => {
    return () => { if (saveTimerRef.current) clearTimeout(saveTimerRef.current); };
  }, []);

  const selectedCom = committees.find(c => c.id === selectedComId);
  const enabledFields = fields.filter(f => f.enabled);

  const toggleField = (fid) => {
    const updated = fields.map(f => f.id === fid ? { ...f, enabled: !f.enabled } : f);
    setFields(updated);
    saveSettings(updated, cardWidth, cardHeight);
  };

  const updateFieldWidth = (fid, w) => {
    const updated = fields.map(f => f.id === fid ? { ...f, width: Math.min(60, Math.max(10, parseInt(w) || 10)) } : f);
    setFields(updated);
    saveSettings(updated, cardWidth, cardHeight);
  };

  const deleteField = (fid) => {
    const updated = fields.filter(f => f.id !== fid);
    setFields(updated);
    saveSettings(updated, cardWidth, cardHeight);
  };

  const addField = () => {
    if (!newFieldLabel.trim()) return;
    const updated = [...fields, { id: uid(), label: newFieldLabel.trim(), key: 'custom', width: 20, enabled: true, isDefault: false }];
    setFields(updated);
    saveSettings(updated, cardWidth, cardHeight);
    setAddFieldOpen(false);
    setNewFieldLabel('');
    toast.success(isRTL ? 'تمت إضافة الخانة' : 'Field added');
  };

  const getStudentValue = (student, field) => {
    if (field.key === 'custom') return '—';
    return student[field.key] || '—';
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-bold text-gray-800 dark:text-gray-200 flex items-center gap-2">
          <FileText className="h-5 w-5 text-indigo-500" />
          {isRTL ? 'كروت الجلوس' : 'Seating Cards'}
        </h3>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => { setNewFieldLabel(''); setAddFieldOpen(true); }} data-testid="button-add-field">
            <Plus className="h-3.5 w-3.5 me-1" />{isRTL ? 'إضافة خانة' : 'Add Field'}
          </Button>
          <Button size="sm" onClick={() => window.print()} className="bg-indigo-600 hover:bg-indigo-700" data-testid="button-print-cards">
            <Printer className="h-3.5 w-3.5 me-1" />{isRTL ? 'طباعة الكروت' : 'Print Cards'}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="border-gray-200 dark:border-gray-700">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-bold">{isRTL ? 'الخانات' : 'Fields'}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {fields.map(field => (
              <div key={field.id} className="flex items-center justify-between p-2 rounded-lg border" data-testid={`field-config-${field.id}`}>
                <label className="flex items-center gap-2 cursor-pointer text-sm flex-1">
                  <Checkbox checked={field.enabled} onCheckedChange={() => toggleField(field.id)} />
                  {field.label}
                </label>
                {!field.isDefault && (
                  <Button variant="ghost" size="icon" className="h-6 w-6 text-red-500" onClick={() => deleteField(field.id)}>
                    <Trash2 className="h-3 w-3" />
                  </Button>
                )}
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="border-gray-200 dark:border-gray-700">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-bold">{isRTL ? 'المقاسات' : 'Dimensions'}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label className="text-xs">{isRTL ? 'عرض الكرت (px)' : 'Card Width (px)'}</Label>
                <Input type="number" min={200} max={500} value={cardWidth}
                  onChange={e => { const v = Math.min(500, Math.max(200, parseInt(e.target.value) || 200)); setCardWidth(v); saveSettings(fields, v, cardHeight); }} data-testid="input-card-width" />
              </div>
              <div>
                <Label className="text-xs">{isRTL ? 'ارتفاع الكرت (px)' : 'Card Height (px)'}</Label>
                <Input type="number" min={120} max={400} value={cardHeight}
                  onChange={e => { const v = Math.min(400, Math.max(120, parseInt(e.target.value) || 120)); setCardHeight(v); saveSettings(fields, cardWidth, v); }} data-testid="input-card-height" />
              </div>
            </div>
            <div className="space-y-2">
              {enabledFields.map(field => (
                <div key={field.id} className="flex items-center gap-2 text-sm">
                  <span className="flex-1">{field.label}</span>
                  <div className="flex items-center gap-1">
                    <Input type="number" min={10} max={60} value={field.width}
                      onChange={e => updateFieldWidth(field.id, e.target.value)}
                      className="w-16 h-7 text-xs" />
                    <span className="text-xs text-muted-foreground">%</span>
                  </div>
                </div>
              ))}
            </div>
            <p className="text-[11px] text-muted-foreground bg-blue-50 dark:bg-blue-950/20 p-2 rounded">
              {isRTL ? 'المقاسات تنطبق على جميع كروت الطباعة' : 'Dimensions apply to all print cards'}
            </p>
          </CardContent>
        </Card>
      </div>

      <div>
        <Label className="mb-2 block text-sm font-bold">{isRTL ? 'اختر اللجنة' : 'Select Committee'}</Label>
        <Select value={selectedComId} onValueChange={setSelectedComId} data-testid="select-committee">
          <SelectTrigger className="w-full md:w-80">
            <SelectValue placeholder={isRTL ? 'اختر لجنة لعرض الكروت' : 'Select a committee to view cards'} />
          </SelectTrigger>
          <SelectContent>
            {committees.map(com => (
              <SelectItem key={com.id} value={com.id}>{com.name} — {com.location}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {selectedCom && (
        <div className="flex flex-wrap gap-4 print:gap-2" id="seating-cards-container">
          {selectedCom.students.map(student => (
            <div key={student.id} data-testid={`card-seating-${student.id}`}
              className="border rounded-xl overflow-hidden shadow-sm bg-white dark:bg-gray-900 print:break-inside-avoid"
              style={{ width: cardWidth, minHeight: cardHeight }}>
              <div className="bg-gradient-to-r from-indigo-600 to-violet-600 text-white px-3 py-2">
                <p className="text-[10px] font-medium opacity-80">{isRTL ? 'بطاقة جلوس اختبارات' : 'Exam Seating Card'}</p>
                <p className="text-xs font-bold">{selectedCom.name} — {selectedCom.location}</p>
              </div>
              <div className="p-3 space-y-1.5">
                {enabledFields.map(field => (
                  <div key={field.id} className="flex text-sm border-b border-dashed border-gray-200 dark:border-gray-700 pb-1">
                    <span className="font-bold text-gray-600 dark:text-gray-400 shrink-0" style={{ minWidth: `${field.width}%` }}>{field.label}:</span>
                    <span className="flex-1 font-medium">{getStudentValue(student, field)}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={addFieldOpen} onOpenChange={setAddFieldOpen}>
        <DialogContent className="sm:max-w-[400px]">
          <DialogHeader>
            <DialogTitle>{isRTL ? 'إضافة خانة جديدة' : 'Add New Field'}</DialogTitle>
          </DialogHeader>
          <div>
            <Label>{isRTL ? 'اسم الخانة' : 'Field Label'}</Label>
            <Input value={newFieldLabel} onChange={e => setNewFieldLabel(e.target.value)}
              placeholder={isRTL ? 'مثال: القسم' : 'e.g. Section'} data-testid="input-field-label" />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddFieldOpen(false)}>{isRTL ? 'إلغاء' : 'Cancel'}</Button>
            <Button onClick={addField} className="bg-indigo-600 hover:bg-indigo-700">{isRTL ? 'إضافة' : 'Add'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

export const AssessmentPage = () => {
  const { user, api } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();

  const [activeTab, setActiveTab] = useState('schedule');
  const [periods, setPeriods] = useState(DEFAULT_PERIODS);
  const [committees, setCommittees] = useState([]);
  const [apiClasses, setApiClasses] = useState([]);
  const [apiTeachers, setApiTeachers] = useState([]);
  const [loading, setLoading] = useState(true);

  const { nassaqError, nassaqWarning } = useNassaqAlert();
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const [classesRes, teachersRes, committeesRes] = await Promise.all([
          api.get('/classes').catch(() => ({ data: [] })),
          api.get('/teachers').catch(() => ({ data: [] })),
          api.get('/exam-committees').catch(() => ({ data: { committees: [] } })),
        ]);
        setApiClasses(Array.isArray(classesRes.data) ? classesRes.data : []);
        setApiTeachers(Array.isArray(teachersRes.data) ? teachersRes.data : []);
        const loadedCommittees = committeesRes.data?.committees || [];
        setCommittees(loadedCommittees);
      } catch (e) {
        console.error('Error loading data:', e);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const totalSubjects = periods.reduce((sum, p) => sum + p.subjects.length, 0);
  const totalStudentsInCommittees = committees.reduce((sum, c) => sum + c.students.length, 0);

  return (
    <Sidebar>
      <div className="p-4 lg:p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 text-white shadow-lg">
                <ClipboardList className="h-6 w-6" />
              </div>
              {isRTL ? 'إدارة الاختبارات والتقييمات' : 'Exams & Assessments Management'}
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              {isRTL ? 'تنظيم الاختبارات والفترات واللجان وكروت الجلوس' : 'Organize exams, periods, committees and seating cards'}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" onClick={toggleTheme} className="h-9 w-9">
              {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            <Button variant="ghost" size="icon" onClick={toggleLanguage} className="h-9 w-9">
              <Globe className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <Card className="border-indigo-200 dark:border-indigo-800 bg-gradient-to-br from-indigo-50 to-indigo-100 dark:from-indigo-950/30 dark:to-indigo-900/20">
            <CardContent className="p-3 text-center">
              <p className="text-2xl font-bold text-indigo-600">{periods.length}</p>
              <p className="text-xs text-indigo-500">{isRTL ? 'فترات اختبار' : 'Exam Periods'}</p>
            </CardContent>
          </Card>
          <Card className="border-purple-200 dark:border-purple-800 bg-gradient-to-br from-purple-50 to-purple-100 dark:from-purple-950/30 dark:to-purple-900/20">
            <CardContent className="p-3 text-center">
              <p className="text-2xl font-bold text-purple-600">{totalSubjects}</p>
              <p className="text-xs text-purple-500">{isRTL ? 'مادة مجدولة' : 'Scheduled Subjects'}</p>
            </CardContent>
          </Card>
          <Card className="border-teal-200 dark:border-teal-800 bg-gradient-to-br from-teal-50 to-teal-100 dark:from-teal-950/30 dark:to-teal-900/20">
            <CardContent className="p-3 text-center">
              <p className="text-2xl font-bold text-teal-600">{committees.length}</p>
              <p className="text-xs text-teal-500">{isRTL ? 'لجان اختبار' : 'Exam Committees'}</p>
            </CardContent>
          </Card>
          <Card className="border-amber-200 dark:border-amber-800 bg-gradient-to-br from-amber-50 to-amber-100 dark:from-amber-950/30 dark:to-amber-900/20">
            <CardContent className="p-3 text-center">
              <p className="text-2xl font-bold text-amber-600">{totalStudentsInCommittees}</p>
              <p className="text-xs text-amber-500">{isRTL ? 'طالب في اللجان' : 'Students in Committees'}</p>
            </CardContent>
          </Card>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="w-full grid grid-cols-3 h-12 bg-white dark:bg-gray-900 border shadow-sm rounded-xl mb-4">
            <TabsTrigger value="schedule" className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white rounded-lg text-sm font-bold" data-testid="tab-schedule">
              <Calendar className="h-4 w-4 me-1.5" />
              {isRTL ? 'جدول الاختبارات' : 'Exam Schedule'}
            </TabsTrigger>
            <TabsTrigger value="committees" className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white rounded-lg text-sm font-bold" data-testid="tab-committees">
              <Users className="h-4 w-4 me-1.5" />
              {isRTL ? 'اللجان' : 'Committees'}
            </TabsTrigger>
            <TabsTrigger value="cards" className="data-[state=active]:bg-indigo-600 data-[state=active]:text-white rounded-lg text-sm font-bold" data-testid="tab-cards">
              <FileText className="h-4 w-4 me-1.5" />
              {isRTL ? 'كروت الجلوس' : 'Seating Cards'}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="schedule">
            <ExamScheduleTab periods={periods} setPeriods={setPeriods} isRTL={isRTL} apiClasses={apiClasses} apiTeachers={apiTeachers} />
          </TabsContent>
          <TabsContent value="committees">
            <CommitteesTab committees={committees} setCommittees={setCommittees} isRTL={isRTL} apiClasses={apiClasses} apiTeachers={apiTeachers} api={api} />
          </TabsContent>
          <TabsContent value="cards">
            <SeatingCardsTab committees={committees} isRTL={isRTL} api={api} />
          </TabsContent>
        </Tabs>
      </div>
    </Sidebar>
  );
};

export default AssessmentPage;
