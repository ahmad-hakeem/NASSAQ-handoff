/**
 * Timetable Modals Components
 * مكونات النوافذ المنبثقة للجدول المدرسي
 */

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { Progress } from '../../components/ui/progress';
import { Textarea } from '../../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Switch } from '../../components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { ScrollArea } from '../../components/ui/scroll-area';
import { 
  Wand2, Loader2, CheckCircle2, XCircle, AlertTriangle,
  GraduationCap, Users, BookOpen, Clock, Send, Archive,
  Activity, RefreshCw, Eye, ArrowRight,
  User, School, ChevronDown, ChevronUp, ExternalLink, Wrench
} from 'lucide-react';
import { ReadinessStatus, GenerationMode, TimetableStatus, getStatusLabel } from './types';

// ============================================
// AI Timetable Generation Modal
// ============================================
export const AITimetableGenerationModal = ({
  open = false,
  readinessSummary = null,
  generationInputSummary = null,
  submitting = false,
  onConfirm,
  onClose
}) => {
  const [usePublishedAsBaseline, setUsePublishedAsBaseline] = useState(false);

  const canGenerate = readinessSummary?.status === ReadinessStatus.FULLY_READY || 
                      readinessSummary?.can_generate === true;

  const handleConfirm = () => {
    onConfirm && onConfirm({
      generationMode: GenerationMode.FULL,
      usePublishedAsBaseline
    });
  };

  return (
    <Dialog open={open} onOpenChange={(open) => !open && onClose && onClose()}>
      <DialogContent className="sm:max-w-[500px]" data-testid="ai-generation-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-4">
            <div className="w-20 h-20 rounded-2xl overflow-hidden shadow-lg border-2 border-violet-200 flex-shrink-0 bg-gradient-to-br from-violet-50 to-cyan-50 p-1">
              <img src="/hakim-poses/ai-thinking.png" alt="حكيم" className="hakim-img w-full h-full object-contain drop-shadow-md" style={{ animation: 'hakimRxFloat 4s ease-in-out infinite' }} />
            </div>
            <div>
              <span className="block text-lg">حكيم يساعدك في توليد الجدول</span>
              <span className="block text-xs font-normal text-muted-foreground mt-1">سيقوم بقراءة البيانات الحالية وتوليد جدول مدرسي محسّن</span>
            </div>
          </DialogTitle>
          <style>{`@keyframes hakimRxFloat { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-6px); } }`}</style>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Generation Input Summary */}
          {generationInputSummary && (
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 bg-muted/30 rounded-lg text-center">
                <GraduationCap className="h-5 w-5 mx-auto mb-1 text-brand-navy" />
                <p className="text-lg font-bold">{generationInputSummary.totalClasses}</p>
                <p className="text-xs text-muted-foreground">فصل</p>
              </div>
              <div className="p-3 bg-muted/30 rounded-lg text-center">
                <Users className="h-5 w-5 mx-auto mb-1 text-brand-navy" />
                <p className="text-lg font-bold">{generationInputSummary.totalTeachers}</p>
                <p className="text-xs text-muted-foreground">معلم</p>
              </div>
              <div className="p-3 bg-muted/30 rounded-lg text-center">
                <BookOpen className="h-5 w-5 mx-auto mb-1 text-brand-navy" />
                <p className="text-lg font-bold">{generationInputSummary.totalSubjects}</p>
                <p className="text-xs text-muted-foreground">مادة</p>
              </div>
              <div className="p-3 bg-muted/30 rounded-lg text-center">
                <Clock className="h-5 w-5 mx-auto mb-1 text-brand-navy" />
                <p className="text-lg font-bold">{generationInputSummary.totalTeachingSlots}</p>
                <p className="text-xs text-muted-foreground">حصة</p>
              </div>
            </div>
          )}

          {/* Readiness Summary */}
          {readinessSummary && (
            <div className={`p-3 rounded-lg border ${
              canGenerate 
                ? 'bg-green-50 border-green-200' 
                : 'bg-red-50 border-red-200'
            }`}>
              <div className="flex items-center gap-2">
                {canGenerate ? (
                  <CheckCircle2 className="h-5 w-5 text-green-600" />
                ) : (
                  <XCircle className="h-5 w-5 text-red-600" />
                )}
                <span className={`font-medium ${canGenerate ? 'text-green-700' : 'text-red-700'}`}>
                  {canGenerate 
                    ? 'البيانات جاهزة للمعالجة' 
                    : 'البيانات غير مكتملة'
                  }
                </span>
              </div>
              {!canGenerate && (readinessSummary.critical_issues || readinessSummary.items) && (
                <ul className="mt-2 space-y-1 text-xs text-red-600">
                  {(readinessSummary.critical_issues || (readinessSummary.items || []).filter(i => i.status === 'missing' || i.status === 'critical'))
                    .slice(0, 3)
                    .map((issue, idx) => (
                    <li key={idx}>• {issue.message_ar || issue.label || issue.message}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {/* Options */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Label htmlFor="use-baseline" className="cursor-pointer">
                استخدام النسخة المنشورة كأساس
              </Label>
              <Switch
                id="use-baseline"
                checked={usePublishedAsBaseline}
                onCheckedChange={setUsePublishedAsBaseline}
              />
            </div>
            {usePublishedAsBaseline && (
              <p className="text-xs text-muted-foreground">
                سيحاول النظام الحفاظ على التوزيع الحالي قدر الإمكان
              </p>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={submitting}>
            إلغاء
          </Button>
          <Button 
            onClick={handleConfirm}
            disabled={!canGenerate || submitting}
            className="bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-700 hover:to-purple-700"
            data-testid="confirm-generation-btn"
          >
            {submitting ? (
              <>
                <Loader2 className="h-4 w-4 ml-2 animate-spin" />
                جاري المعالجة...
              </>
            ) : (
              <>
                <Wand2 className="h-4 w-4 ml-2" />
                بدء المعالجة
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

// ============================================
// Partial Regeneration Modal
// ============================================
export const PartialRegenerationModal = ({
  open = false,
  classes = [],
  teachers = [],
  weekdays = [],
  subjects = [],
  grades = [],
  submitting = false,
  onConfirm,
  onClose
}) => {
  const [scope, setScope] = useState('class');
  const [classId, setClassId] = useState(null);
  const [teacherId, setTeacherId] = useState(null);
  const [weekdayNumber, setWeekdayNumber] = useState(null);
  const [subjectId, setSubjectId] = useState(null);

  const canSubmit = () => {
    switch (scope) {
      case 'class':
        return !!classId;
      case 'teacher':
        return !!teacherId;
      case 'day':
        return weekdayNumber !== null;
      case 'subject':
        return !!subjectId;
      default:
        return false;
    }
  };

  const handleConfirm = () => {
    onConfirm && onConfirm({
      scope,
      classId,
      teacherId,
      weekdayNumber,
      subjectId
    });
  };

  const resetSelections = () => {
    setClassId(null);
    setTeacherId(null);
    setWeekdayNumber(null);
    setSubjectId(null);
  };

  return (
    <Dialog open={open} onOpenChange={(open) => !open && onClose && onClose()}>
      <DialogContent className="sm:max-w-[450px]" data-testid="partial-regeneration-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <RefreshCw className="h-5 w-5 text-blue-600" />
            إعادة المعالجة الجزئية
          </DialogTitle>
          <DialogDescription>
            اختر الجزء المراد إعادة معالجته من الجدول
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Scope Selection */}
          <Tabs value={scope} onValueChange={(val) => { setScope(val); resetSelections(); }}>
            <TabsList className="grid grid-cols-4 w-full">
              <TabsTrigger value="class">فصل</TabsTrigger>
              <TabsTrigger value="teacher">معلم</TabsTrigger>
              <TabsTrigger value="day">يوم</TabsTrigger>
              <TabsTrigger value="subject">مادة</TabsTrigger>
            </TabsList>

            <TabsContent value="class" className="space-y-3 mt-4">
              <Label>اختر الفصل</Label>
              <Select value={classId || ''} onValueChange={setClassId}>
                <SelectTrigger>
                  <SelectValue placeholder="اختر الفصل" />
                </SelectTrigger>
                <SelectContent>
                  {classes.map(c => (
                    <SelectItem key={c.id || c.value} value={c.id || c.value}>
                      {c.name || c.name_ar || c.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </TabsContent>

            <TabsContent value="teacher" className="space-y-3 mt-4">
              <Label>اختر المعلم</Label>
              <Select value={teacherId || ''} onValueChange={setTeacherId}>
                <SelectTrigger>
                  <SelectValue placeholder="اختر المعلم" />
                </SelectTrigger>
                <SelectContent>
                  {teachers.map(t => (
                    <SelectItem key={t.id || t.value} value={t.id || t.value}>
                      {t.full_name || t.name || t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </TabsContent>

            <TabsContent value="day" className="space-y-3 mt-4">
              <Label>اختر اليوم</Label>
              <Select 
                value={weekdayNumber?.toString() || ''} 
                onValueChange={(val) => setWeekdayNumber(parseInt(val))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="اختر اليوم" />
                </SelectTrigger>
                <SelectContent>
                  {weekdays.map(d => (
                    <SelectItem key={d.number ?? d.value} value={(d.number ?? d.value)?.toString()}>
                      {d.ar || d.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </TabsContent>

            <TabsContent value="subject" className="space-y-3 mt-4">
              <Label>اختر المادة</Label>
              <Select value={subjectId || ''} onValueChange={setSubjectId}>
                <SelectTrigger>
                  <SelectValue placeholder="اختر المادة" />
                </SelectTrigger>
                <SelectContent>
                  {subjects.map(s => (
                    <SelectItem key={s.id || s.value} value={s.id || s.value}>
                      {s.name_ar || s.name || s.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </TabsContent>
          </Tabs>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={submitting}>
            إلغاء
          </Button>
          <Button 
            onClick={handleConfirm}
            disabled={!canSubmit() || submitting}
            className="bg-blue-600 hover:bg-blue-700"
            data-testid="confirm-partial-regen-btn"
          >
            {submitting ? (
              <>
                <Loader2 className="h-4 w-4 ml-2 animate-spin" />
                جاري المعالجة...
              </>
            ) : (
              <>
                <RefreshCw className="h-4 w-4 ml-2" />
                إعادة المعالجة
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

// ============================================
// Publish Version Modal
// ============================================
const ConflictDetailCard = ({ conflict, index, onNavigateToConflict }) => {
  const [expanded, setExpanded] = useState(false);
  const isTeacher = conflict.type === 'teacher';
  const severity = conflict.severity || (isTeacher ? 'high' : 'medium');
  const severityConfig = {
    critical: { bg: 'bg-red-600', text: 'text-white', label: 'حرج' },
    high: { bg: 'bg-red-500', text: 'text-white', label: 'مرتفع' },
    medium: { bg: 'bg-orange-500', text: 'text-white', label: 'متوسط' },
  };
  const sev = severityConfig[severity] || severityConfig.medium;

  const steps = [];
  if (isTeacher) {
    steps.push({ text: `افتح جدول المعلم: ${conflict.teacher_name}`, icon: '1️⃣' });
    steps.push({ text: `انتقل إلى يوم ${conflict.day_ar} — الحصة ${conflict.period}`, icon: '2️⃣' });
    steps.push({ text: 'أزل أحد التعيينات المتعارضة أو انقل الحصة لوقت آخر', icon: '3️⃣' });
  } else {
    steps.push({ text: `افتح جدول الفصل: ${conflict.class_name}`, icon: '1️⃣' });
    steps.push({ text: `انتقل إلى يوم ${conflict.day_ar} — الحصة ${conflict.period}`, icon: '2️⃣' });
    steps.push({ text: 'أزل التعيين المكرر أو غيّر المعلم', icon: '3️⃣' });
  }

  return (
    <div className={`bg-white dark:bg-gray-900 rounded-xl border-2 overflow-hidden transition-all duration-200 ${
      expanded ? 'border-red-300 dark:border-red-700/60 shadow-md shadow-red-100/50 dark:shadow-red-900/20' : 'border-red-200 dark:border-red-800/40'
    }`}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 p-3 text-start hover:bg-red-50/50 dark:hover:bg-red-950/20 transition-colors"
      >
        <div className="relative">
          <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${isTeacher ? 'bg-red-100 dark:bg-red-900/30' : 'bg-orange-100 dark:bg-orange-900/30'}`}>
            {isTeacher ? <User className="h-4 w-4 text-red-600" /> : <School className="h-4 w-4 text-orange-600" />}
          </div>
          <span className="absolute -top-1.5 -end-1.5 w-5 h-5 rounded-full bg-red-500 text-white text-[9px] font-bold flex items-center justify-center shadow-sm">{index + 1}</span>
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge className={`text-[10px] border-0 ${isTeacher ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400' : 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-400'}`}>
              {conflict.conflict_type_ar}
            </Badge>
            <Badge variant="secondary" className="text-[10px] border-0">
              {conflict.day_ar} — الحصة {conflict.period}
            </Badge>
            <Badge className={`text-[9px] border-0 ${sev.bg} ${sev.text} px-1.5`}>
              {sev.label}
            </Badge>
          </div>
          <p className="text-xs font-semibold text-foreground mt-1 truncate">
            {isTeacher ? conflict.teacher_name : conflict.class_name}
            {conflict.subjects?.length > 0 && (
              <span className="text-muted-foreground font-normal"> ({conflict.subjects.join('، ')})</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {expanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
        </div>
      </button>

      {expanded && (
        <div className="px-3 pb-3 space-y-2.5 border-t border-red-100 dark:border-red-900/30 pt-2.5">
          <div className="p-3 rounded-xl bg-red-50 dark:bg-red-950/20 border border-red-200/60 dark:border-red-900/30">
            <div className="flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
              <div>
                <p className="text-[11px] font-bold text-red-700 dark:text-red-400 mb-0.5">سبب التعارض:</p>
                <p className="text-[11px] text-red-600 dark:text-red-300 leading-relaxed">{conflict.reason_ar}</p>
              </div>
            </div>
          </div>

          {isTeacher && conflict.classes?.length > 0 && (
            <div className="flex flex-wrap gap-1.5 px-1">
              <span className="text-[11px] font-semibold text-muted-foreground">الفصول:</span>
              {conflict.classes.map((cls, ci) => (
                <Badge key={ci} variant="secondary" className="text-[10px]">{cls}</Badge>
              ))}
            </div>
          )}
          {!isTeacher && conflict.teachers?.length > 0 && (
            <div className="flex flex-wrap gap-1.5 px-1">
              <span className="text-[11px] font-semibold text-muted-foreground">المعلمون:</span>
              {conflict.teachers.map((t, ti) => (
                <Badge key={ti} variant="secondary" className="text-[10px]">{t}</Badge>
              ))}
            </div>
          )}

          <div className="p-3 rounded-xl bg-blue-50 dark:bg-blue-950/20 border border-blue-200/60 dark:border-blue-900/30">
            <div className="flex items-start gap-2 mb-2">
              <Wrench className="h-4 w-4 text-blue-500 shrink-0 mt-0.5" />
              <p className="text-[11px] font-bold text-blue-700 dark:text-blue-400">خطوات الإصلاح:</p>
            </div>
            <div className="space-y-1.5 ps-1">
              {steps.map((step, si) => (
                <div key={si} className="flex items-start gap-2">
                  <span className="text-[11px] shrink-0">{step.icon}</span>
                  <p className="text-[11px] text-blue-600 dark:text-blue-300 leading-relaxed">{step.text}</p>
                </div>
              ))}
            </div>
            {conflict.fix_ar && (
              <p className="text-[10px] text-blue-500 dark:text-blue-400 mt-2 ps-1 border-t border-blue-200/50 dark:border-blue-800/30 pt-1.5">{conflict.fix_ar}</p>
            )}
          </div>

          <Button
            size="sm"
            variant="outline"
            onClick={() => onNavigateToConflict?.(conflict)}
            className="w-full text-xs h-9 border-red-200 text-red-700 hover:bg-red-100 gap-2 rounded-xl font-semibold"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            انتقل إلى التعارض — يوم {conflict.day_ar} الحصة {conflict.period}
          </Button>
        </div>
      )}
    </div>
  );
};


export const PublishTimetableVersionModal = ({
  open = false,
  version = null,
  submitting = false,
  onConfirm,
  onClose,
  apiCall,
  onGapsFilled,
  onNavigateToConflict,
}) => {
  const [confirmed, setConfirmed] = useState(false);
  const [validation, setValidation] = useState(null);
  const [validating, setValidating] = useState(false);
  const [emptyDetails, setEmptyDetails] = useState(null);
  const [showEmptyDetails, setShowEmptyDetails] = useState(false);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [fillingGaps, setFillingGaps] = useState(false);
  const [fillResult, setFillResult] = useState(null);
  const [showConflicts, setShowConflicts] = useState(true);

  const runValidation = () => {
    if (!version?.id || !apiCall) return;
    setValidation(null);
    setConfirmed(false);
    setFillResult(null);
    setEmptyDetails(null);
    setShowEmptyDetails(false);
    setValidating(true);
    apiCall(`/api/principal/timetable/version/${version.id}/validate-publish`)
      .then(res => setValidation(res.data))
      .catch(() => setValidation({ can_publish: true, errors: [], warnings: [] }))
      .finally(() => setValidating(false));
  };

  useEffect(() => {
    if (open) runValidation();
  }, [open, version?.id]);

  const loadEmptyDetails = async () => {
    if (!version?.id || !apiCall) return;
    setLoadingDetails(true);
    try {
      const res = await apiCall(`/api/principal/timetable/version/${version.id}/empty-slots`);
      setEmptyDetails(res.data);
      setShowEmptyDetails(true);
    } catch {
      setEmptyDetails(null);
    } finally {
      setLoadingDetails(false);
    }
  };

  const handleFillGaps = async () => {
    if (!version?.id || !apiCall) return;
    setFillingGaps(true);
    try {
      const res = await apiCall(`/api/principal/timetable/version/${version.id}/fill-gaps`, { method: 'POST' });
      setFillResult(res);
      runValidation();
      if (onGapsFilled) onGapsFilled();
    } catch (err) {
      setFillResult({ success: false, message: err.message });
    } finally {
      setFillingGaps(false);
    }
  };

  const errors = validation?.errors || [];
  const warnings = validation?.warnings || [];
  const canPublish = validation?.can_publish !== false;
  const hasEmptySlots = validation?.empty_slots > 0;
  const emptyWarning = warnings.find(w => w.code === 'EMPTY_SLOTS');
  const otherWarnings = warnings.filter(w => w.code !== 'EMPTY_SLOTS');

  const conflictError = errors.find(e => e.code === 'CONFLICT');
  const conflictDetails = conflictError?.details || [];
  const otherErrors = errors.filter(e => e.code !== 'CONFLICT');

  return (
    <Dialog open={open} onOpenChange={(open) => !open && onClose && onClose()}>
      <DialogContent className="sm:max-w-[640px] max-h-[85vh] overflow-y-auto" data-testid="publish-version-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-4">
            <div className="w-24 h-24 rounded-2xl overflow-hidden shadow-xl border-2 border-emerald-200 flex-shrink-0 bg-gradient-to-br from-emerald-50 to-cyan-50 p-1">
              <img src="/hakim-poses/clapping-celebration.png" alt="حكيم" className="hakim-img w-full h-full object-contain drop-shadow-md" style={{ animation: 'hakimCelebrate 1.2s ease-in-out infinite' }} />
            </div>
            <div>
              <span className="block text-lg">نشر الجدول المدرسي</span>
              <span className="block text-sm font-normal text-muted-foreground mt-1">
                هل أنت متأكد من نشر هذا الجدول؟ بعد النشر سيصبح الجدول الرسمي المعتمد للمدرسة.
              </span>
            </div>
          </DialogTitle>
          <style>{`@keyframes hakimCelebrate { 0%, 100% { transform: scale(1) rotate(0deg); } 25% { transform: scale(1.08) rotate(-3deg); } 50% { transform: scale(1.05) rotate(3deg); } 75% { transform: scale(1.02) rotate(-1deg); } }`}</style>
        </DialogHeader>

        <div className="space-y-3 py-3">
          {validating ? (
            <div className="flex items-center justify-center gap-3 py-8">
              <Loader2 className="h-6 w-6 animate-spin text-emerald-600" />
              <span className="text-sm text-gray-600">جاري التحقق من صحة الجدول...</span>
            </div>
          ) : (
            <>
              {version && (
                <div className="p-3 bg-gradient-to-l from-emerald-50 to-teal-50 rounded-xl border border-emerald-200">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-semibold text-emerald-800">{version.versionName}</span>
                    <Badge className="bg-amber-100 text-amber-700 text-xs">مسودة</Badge>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs text-emerald-700">
                    <span>عدد الحصص: {validation?.sessions_count || '...'}</span>
                    <span>عدد الفصول: {validation?.classes_count || '...'}</span>
                    {validation?.total_slots > 0 && (
                      <span className="col-span-2">نسبة التغطية: {Math.round(((validation.total_slots - (validation.empty_slots || 0)) / validation.total_slots) * 100)}%</span>
                    )}
                  </div>
                </div>
              )}

              {conflictDetails.length > 0 && (() => {
                const teacherConflicts = conflictDetails.filter(c => c.type === 'teacher');
                const classConflicts = conflictDetails.filter(c => c.type !== 'teacher');
                const affectedDays = [...new Set(conflictDetails.map(c => c.day_ar))];
                return (
                <div className="p-3 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800/40 rounded-xl space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-red-700 dark:text-red-400 font-semibold text-sm">
                      <XCircle className="h-4 w-4" />
                      تعارضات تمنع النشر ({conflictDetails.length})
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setShowConflicts(!showConflicts)}
                      className="text-xs h-7 px-2 text-red-600 hover:bg-red-100"
                    >
                      {showConflicts ? 'إخفاء التفاصيل' : 'عرض التفاصيل'}
                      {showConflicts ? <ChevronUp className="h-3 w-3 mr-1" /> : <ChevronDown className="h-3 w-3 mr-1" />}
                    </Button>
                  </div>

                  <div className="grid grid-cols-3 gap-2">
                    {teacherConflicts.length > 0 && (
                      <div className="px-2.5 py-2 rounded-lg bg-red-100/80 dark:bg-red-900/30 text-center">
                        <p className="text-lg font-bold text-red-700 dark:text-red-400 font-cairo">{teacherConflicts.length}</p>
                        <p className="text-[10px] text-red-600 dark:text-red-300">تعارض معلم</p>
                      </div>
                    )}
                    {classConflicts.length > 0 && (
                      <div className="px-2.5 py-2 rounded-lg bg-orange-100/80 dark:bg-orange-900/30 text-center">
                        <p className="text-lg font-bold text-orange-700 dark:text-orange-400 font-cairo">{classConflicts.length}</p>
                        <p className="text-[10px] text-orange-600 dark:text-orange-300">تعارض فصل</p>
                      </div>
                    )}
                    <div className="px-2.5 py-2 rounded-lg bg-slate-100/80 dark:bg-slate-800/30 text-center">
                      <p className="text-lg font-bold text-slate-700 dark:text-slate-300 font-cairo">{affectedDays.length}</p>
                      <p className="text-[10px] text-slate-600 dark:text-slate-400">أيام متأثرة</p>
                    </div>
                  </div>

                  <p className="text-xs text-red-600 dark:text-red-300 leading-relaxed">
                    {conflictError.message} — يجب حل جميع التعارضات قبل النشر. اضغط على كل تعارض لعرض خطوات الإصلاح.
                  </p>

                  {showConflicts && (
                    <ScrollArea className="max-h-[280px]">
                      <div className="space-y-2">
                        {conflictDetails.map((conflict, i) => (
                          <ConflictDetailCard
                            key={i}
                            conflict={conflict}
                            index={i}
                            onNavigateToConflict={(c) => {
                              onClose?.();
                              onNavigateToConflict?.(c);
                            }}
                          />
                        ))}
                      </div>
                    </ScrollArea>
                  )}
                </div>
                );
              })()}

              {otherErrors.length > 0 && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-xl space-y-2">
                  <div className="flex items-center gap-2 text-red-700 font-semibold text-sm">
                    <XCircle className="h-4 w-4" />
                    مشاكل أخرى تمنع النشر ({otherErrors.length})
                  </div>
                  {otherErrors.map((e, i) => (
                    <p key={i} className="text-xs text-red-600 flex items-start gap-1.5 ps-5">
                      <span className="text-red-400 mt-0.5">•</span> {e.message}
                    </p>
                  ))}
                </div>
              )}

              {hasEmptySlots && emptyWarning && (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-amber-700 font-semibold text-sm">
                      <AlertTriangle className="h-4 w-4" />
                      {emptyWarning.message}
                    </div>
                  </div>

                  {fillResult && (
                    <div className={`p-2.5 rounded-lg text-xs ${fillResult.success ? 'bg-emerald-50 border border-emerald-200 text-emerald-700' : 'bg-red-50 border border-red-200 text-red-700'}`}>
                      {fillResult.message}
                    </div>
                  )}

                  <div className="flex items-center gap-2 flex-wrap">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={loadEmptyDetails}
                      disabled={loadingDetails || fillingGaps}
                      className="text-xs h-8 border-amber-300 text-amber-700 hover:bg-amber-100"
                    >
                      {loadingDetails ? (
                        <><Loader2 className="h-3 w-3 animate-spin ml-1" /> جاري التحميل</>
                      ) : (
                        <><Eye className="h-3 w-3 ml-1" /> عرض التفاصيل</>
                      )}
                    </Button>
                    <Button
                      size="sm"
                      onClick={handleFillGaps}
                      disabled={fillingGaps || loadingDetails}
                      className="text-xs h-8 bg-amber-600 hover:bg-amber-700 text-white"
                    >
                      {fillingGaps ? (
                        <><Loader2 className="h-3 w-3 animate-spin ml-1" /> جاري الملء...</>
                      ) : (
                        <><Wand2 className="h-3 w-3 ml-1" /> ملء الخانات تلقائياً</>
                      )}
                    </Button>
                  </div>

                  {showEmptyDetails && emptyDetails && (
                    <div className="mt-2 space-y-2">
                      <div className="text-xs text-amber-600 font-medium">
                        {emptyDetails.affected_classes} فصل من أصل {emptyDetails.total_classes} يحتوي على خانات فارغة
                      </div>
                      <ScrollArea className="max-h-40">
                        <div className="space-y-1.5">
                          {emptyDetails.classes?.map((cls, i) => (
                            <div key={i} className="flex items-start justify-between bg-white rounded-lg p-2 border border-amber-100 text-xs">
                              <div>
                                <span className="font-medium text-amber-800">{cls.class_name}</span>
                                <div className="text-amber-500 mt-0.5">
                                  {Object.entries(cls.days || {}).map(([day, periods]) => (
                                    <span key={day} className="inline-block ml-2">
                                      {day}: ح{periods.join('، ح')}
                                    </span>
                                  ))}
                                </div>
                              </div>
                              <Badge variant="outline" className="text-amber-600 border-amber-200 text-[10px] shrink-0">
                                {cls.empty_count} فارغة
                              </Badge>
                            </div>
                          ))}
                        </div>
                      </ScrollArea>
                    </div>
                  )}
                </div>
              )}

              {otherWarnings.length > 0 && (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl space-y-2">
                  <div className="flex items-center gap-2 text-amber-700 font-semibold text-sm">
                    <AlertTriangle className="h-4 w-4" />
                    تحذيرات أخرى ({otherWarnings.length})
                  </div>
                  {otherWarnings.map((w, i) => (
                    <p key={i} className="text-xs text-amber-600 flex items-start gap-1.5 ps-5">
                      <span className="text-amber-400 mt-0.5">•</span> {w.message}
                    </p>
                  ))}
                </div>
              )}

              {canPublish && errors.length === 0 && !hasEmptySlots && (
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl">
                  <div className="flex items-center gap-2 text-emerald-700 font-medium text-sm">
                    <CheckCircle2 className="h-4 w-4" />
                    الجدول جاهز للنشر بالكامل
                  </div>
                </div>
              )}

              <div className="p-3 bg-gray-50 border border-gray-200 rounded-xl text-xs text-gray-600 space-y-1">
                <p>• سيصبح هذا الجدول هو الجدول الرسمي المعتمد للمدرسة</p>
                <p>• سيتم أرشفة الجدول المنشور السابق تلقائياً</p>
                <p>• سيظهر الجدول لجميع المعلمين والطلاب</p>
              </div>

              {canPublish && (
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="confirm-publish"
                    checked={confirmed}
                    onChange={(e) => setConfirmed(e.target.checked)}
                    className="rounded border-gray-300 text-emerald-600"
                  />
                  <Label htmlFor="confirm-publish" className="cursor-pointer text-sm">
                    {hasEmptySlots ? 'أؤكد أنني راجعت الجدول وأريد نشره رغم وجود خانات فارغة' : 'أؤكد أنني راجعت الجدول وأريد نشره'}
                  </Label>
                </div>
              )}
            </>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={submitting || fillingGaps}>
            إلغاء
          </Button>
          <Button
            onClick={onConfirm}
            disabled={submitting || !canPublish || !confirmed || validating || fillingGaps}
            className="bg-gradient-to-l from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 gap-2"
            data-testid="confirm-publish-btn"
          >
            {submitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                جاري النشر...
              </>
            ) : (
              <>
                <Send className="h-4 w-4" />
                تأكيد النشر
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

// ============================================
// Archive Version Modal
// ============================================
export const ArchiveTimetableVersionModal = ({
  open = false,
  version = null,
  submitting = false,
  onConfirm,
  onClose
}) => {
  const [reason, setReason] = useState('');

  return (
    <Dialog open={open} onOpenChange={(open) => !open && onClose && onClose()}>
      <DialogContent className="sm:max-w-[400px]" data-testid="archive-version-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Archive className="h-5 w-5 text-gray-600" />
            أرشفة النسخة
          </DialogTitle>
          <DialogDescription>
            نقل النسخة إلى الأرشيف
          </DialogDescription>
        </DialogHeader>

        {version && (
          <div className="space-y-4 py-4">
            <div className="p-3 bg-muted/30 rounded-lg">
              <span className="font-medium">{version.versionName}</span>
              <Badge className="mr-2" variant="outline">
                {getStatusLabel(version.status).ar}
              </Badge>
            </div>

            <div className="space-y-2">
              <Label htmlFor="archive-reason">سبب الأرشفة (اختياري)</Label>
              <Textarea
                id="archive-reason"
                placeholder="اكتب سبب الأرشفة..."
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={3}
              />
            </div>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={submitting}>
            إلغاء
          </Button>
          <Button 
            onClick={() => onConfirm && onConfirm(reason)}
            disabled={submitting}
            variant="secondary"
            data-testid="confirm-archive-btn"
          >
            {submitting ? (
              <>
                <Loader2 className="h-4 w-4 ml-2 animate-spin" />
                جاري الأرشفة...
              </>
            ) : (
              <>
                <Archive className="h-4 w-4 ml-2" />
                أرشفة
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

// ============================================
// Diagnostics Details Modal
// ============================================
export const TimetableDiagnosticsModal = ({
  open = false,
  diagnostics = null,
  loading = false,
  onClose
}) => {
  const formatDate = (dateStr) => {
    if (!dateStr) return '-';
    try {
      return new Date(dateStr).toLocaleString('ar-SA');
    } catch {
      return dateStr;
    }
  };

  return (
    <Dialog open={open} onOpenChange={(open) => !open && onClose && onClose()}>
      <DialogContent className="sm:max-w-[600px] max-h-[80vh]" data-testid="diagnostics-modal">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-brand-navy" />
            تشخيص المحرك
          </DialogTitle>
        </DialogHeader>

        <ScrollArea className="max-h-[60vh] pr-4">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-brand-navy" />
            </div>
          ) : diagnostics ? (
            <div className="space-y-4">
              {/* Run Info */}
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-muted/30 rounded-lg">
                  <p className="text-xs text-muted-foreground">بدء التشغيل</p>
                  <p className="font-medium text-sm">{formatDate(diagnostics.startedAt)}</p>
                </div>
                <div className="p-3 bg-muted/30 rounded-lg">
                  <p className="text-xs text-muted-foreground">انتهاء التشغيل</p>
                  <p className="font-medium text-sm">{formatDate(diagnostics.finishedAt)}</p>
                </div>
              </div>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 bg-blue-50 rounded-lg text-center">
                  <p className="text-2xl font-bold text-blue-700">{diagnostics.totalUnits || 0}</p>
                  <p className="text-xs text-blue-600">إجمالي الوحدات</p>
                </div>
                <div className="p-3 bg-green-50 rounded-lg text-center">
                  <p className="text-2xl font-bold text-green-700">{diagnostics.assignedUnits || 0}</p>
                  <p className="text-xs text-green-600">تم توزيعها</p>
                </div>
                <div className="p-3 bg-red-50 rounded-lg text-center">
                  <p className="text-2xl font-bold text-red-700">{diagnostics.unassignedUnits || 0}</p>
                  <p className="text-xs text-red-600">لم يتم توزيعها</p>
                </div>
              </div>

              {/* Conflicts */}
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 border rounded-lg">
                  <p className="text-xs text-muted-foreground">تعارضات حرجة</p>
                  <p className="text-xl font-bold text-red-600">{diagnostics.hardConflicts || 0}</p>
                </div>
                <div className="p-3 border rounded-lg">
                  <p className="text-xs text-muted-foreground">تعارضات بسيطة</p>
                  <p className="text-xl font-bold text-amber-600">{diagnostics.softConflicts || 0}</p>
                </div>
              </div>

              {/* Logs */}
              {diagnostics.logs && diagnostics.logs.length > 0 && (
                <div className="space-y-2">
                  <h4 className="font-medium text-sm">سجلات التشغيل</h4>
                  <div className="space-y-2 max-h-[200px] overflow-y-auto">
                    {diagnostics.logs.map((log, idx) => (
                      <div key={idx} className="p-2 bg-muted/20 rounded text-xs font-mono">
                        {log.message || log}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              لا توجد بيانات تشخيص
            </div>
          )}
        </ScrollArea>

        <DialogFooter>
          <Button onClick={onClose}>
            إغلاق
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

// ============================================
// Session Details Drawer
// ============================================
export const TimetableSessionDetailsDrawer = ({
  open = false,
  session = null,
  loading = false,
  onClose,
  onViewDiagnostics
}) => {
  if (!open) return null;

  return (
    <Dialog open={open} onOpenChange={(open) => !open && onClose && onClose()}>
      <DialogContent className="sm:max-w-[450px]" data-testid="session-details-drawer">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Eye className="h-5 w-5 text-brand-navy" />
            تفاصيل الحصة
          </DialogTitle>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-brand-navy" />
          </div>
        ) : session ? (
          <div className="space-y-4 py-4">
            {/* Main Info */}
            <div className="space-y-3">
              <div className="p-3 bg-gradient-to-br from-brand-navy/5 to-brand-turquoise/5 rounded-lg">
                <p className="text-xs text-muted-foreground">المادة</p>
                <p className="font-bold text-lg">{session.subjectName || session.subject_name}</p>
              </div>
              
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-muted/30 rounded-lg">
                  <p className="text-xs text-muted-foreground">المعلم</p>
                  <p className="font-medium">{session.teacherName || session.teacher_name}</p>
                </div>
                <div className="p-3 bg-muted/30 rounded-lg">
                  <p className="text-xs text-muted-foreground">الفصل</p>
                  <p className="font-medium">{session.className || session.class_name}</p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-muted/30 rounded-lg">
                  <p className="text-xs text-muted-foreground">اليوم</p>
                  <p className="font-medium">{session.weekdayLabel || session.day_of_week}</p>
                </div>
                <div className="p-3 bg-muted/30 rounded-lg">
                  <p className="text-xs text-muted-foreground">التوقيت</p>
                  <p className="font-medium">
                    {session.startTime || session.start_time} - {session.endTime || session.end_time}
                  </p>
                </div>
              </div>

              {session.roomName && (
                <div className="p-3 bg-muted/30 rounded-lg">
                  <p className="text-xs text-muted-foreground">القاعة</p>
                  <p className="font-medium">{session.roomName}</p>
                </div>
              )}
            </div>

            {/* Status Badges */}
            <div className="flex flex-wrap items-center gap-2">
              {session.isAiGenerated && (
                <Badge variant="outline" className="gap-1 bg-violet-50 text-violet-700 border-violet-200">
                  <Wand2 className="h-3 w-3" />
                  AI Generated
                </Badge>
              )}
              {session.status && (
                <Badge variant="outline">
                  {session.status}
                </Badge>
              )}
            </div>

            {/* Warnings */}
            {session.warnings && session.warnings.length > 0 && (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg space-y-1">
                <p className="text-xs font-medium text-amber-700">تحذيرات:</p>
                {session.warnings.map((warning, idx) => (
                  <p key={idx} className="text-xs text-amber-600">• {warning}</p>
                ))}
              </div>
            )}

            {/* Notes */}
            {session.notes && (
              <div className="p-3 bg-muted/30 rounded-lg">
                <p className="text-xs text-muted-foreground">ملاحظات</p>
                <p className="text-sm">{session.notes}</p>
              </div>
            )}
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            لا توجد بيانات
          </div>
        )}

        <DialogFooter>
          <Button onClick={onClose}>
            إغلاق
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
