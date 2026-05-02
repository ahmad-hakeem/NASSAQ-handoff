/**
 * إدارة الجداول الذكية — Smart Master Grid
 * نَسَّق | NASSAQ School Management System
 *
 * مصفوفة موحَّدة تعرض كل المعلمين كصفوف وكل (يوم × حصة) كأعمدة في تصميم RTL
 * مع رؤوس مثبَّتة، لوحة مؤشرات أداء أعلى الشاشة، شريط تنبيه أحمر ديناميكي،
 * وأزرار إجراءات أساسية (إنشاء تلقائي + تسجيل غياب).
 *
 * تستهلك endpoint وحيد: GET /api/schedule/master-grid
 */

import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Sidebar } from '../components/layout/Sidebar';
import { useAuth } from '../contexts/AuthContext';
import { toast } from 'sonner';

import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '../components/ui/dialog';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../components/ui/select';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from '../components/ui/tooltip';
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from '../components/ui/sheet';
import { Badge } from '../components/ui/badge';
import {
  Wand2, UserX, Sparkles, Loader2, RefreshCw,
  Scale, Hourglass, UserMinus, AlertOctagon, AlertTriangle, Repeat,
  ShieldAlert, Settings, ArrowLeft,
  Undo2, Layers, Lightbulb, X, ExternalLink,
} from 'lucide-react';
import CandidatesSidePanel from '../components/schedule/CandidatesSidePanel';
import BulkSubstitutionPanel from '../components/schedule/BulkSubstitutionPanel';
import ScheduleTabNav from '../components/schedule/ScheduleTabNav';
import ScheduleSettingsTabContent from '../components/schedule/ScheduleSettingsTabContent';
import { StandbyRosterContent } from './StandbyRosterPage';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import { getPose } from '../components/hakim/hakimPoses';

// ─── Infeasibility issue → contextual next step ────────────────────────────
// كل كود INF يحدد الصفحة الأنسب التي تحل المشكلة. عند غياب الكود نوجِّه إلى
// إعدادات المدرسة العامة كملاذ افتراضي.
const ISSUE_NEXT_STEP = {
  'INF-01': { label: 'فتح إعدادات الهيكل الأكاديمي', path: '/school/settings?section=academic' },
  'INF-02': { label: 'فتح إعدادات الهيكل الأكاديمي', path: '/school/settings?section=academic' },
  'INF-03': { label: 'فتح صفحة المعلمين والإسنادات',  path: '/school/teachers' },
  'INF-04': { label: 'فتح إعدادات القاعات',           path: '/school/schedule?tab=settings&sub=timings' },
  'INF-05': { label: 'فتح إعدادات اليوم الدراسي',     path: '/school/schedule?tab=settings&sub=timings' },
};
const DEFAULT_NEXT_STEP = { label: 'فتح إعدادات الجدول المدرسي', path: '/school/schedule?tab=settings' };

const DAYS = [
  { key: 'sunday',    ar: 'الأحد' },
  { key: 'monday',    ar: 'الإثنين' },
  { key: 'tuesday',   ar: 'الثلاثاء' },
  { key: 'wednesday', ar: 'الأربعاء' },
  { key: 'thursday',  ar: 'الخميس' },
];
// لا فرض لعدد الحصص في الواجهة بعد الآن — قائمة الحصص تأتي ديناميكياً من
// الباك‑إند بناءً على إعدادات المدرسة (periods_per_day / time_slots).
// نُبقي مصفوفة فارغة كـ fallback نهائي لتفادي كسر العرض إن تأخر التحميل.
const FALLBACK_PERIODS = [];

const RANK_AR = {
  expert: 'خبير',
  advanced: 'متقدم',
  practitioner: 'ممارس',
  assistant: 'مساعد',
};

// Tiny Arabic relative-time formatter (mirrors TeacherAttendancePage).
// Used by the absence tooltip so principals can see when a row was flipped.
function formatAbsenceTimeAr(iso) {
  if (!iso) return '';
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return '';
  const diffSec = Math.round((Date.now() - then.getTime()) / 1000);
  if (diffSec < 5) return 'الآن';
  if (diffSec < 60) return `قبل ${diffSec} ثانية`;
  const mins = Math.round(diffSec / 60);
  if (mins < 60) return `قبل ${mins} دقيقة`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `قبل ${hours} ساعة`;
  const days = Math.round(hours / 24);
  if (days < 7) return `قبل ${days} يوم`;
  return then.toLocaleDateString('ar-EG');
}

// ─── Absence pill with recorder tooltip ───────────────────────────────────
// The pill itself is unchanged visually; hovering reveals "سجَّله: <name>"
// and the relative time. Falls back gracefully when the audit fields are
// absent (older absence rows that predate the recorder feature).
function AbsencePill({ recorderName, recordedAt }) {
  const pill = (
    <span
      tabIndex={0}
      className="text-[10px] font-semibold rounded border border-red-400 text-red-700 bg-red-100 px-1.5 py-0.5 cursor-help focus:outline-none focus:ring-1 focus:ring-red-400"
    >
      غائب
    </span>
  );

  const hasAudit = Boolean(recorderName) || Boolean(recordedAt);
  if (!hasAudit) return pill;

  const relTime = formatAbsenceTimeAr(recordedAt);
  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>{pill}</TooltipTrigger>
        <TooltipContent
          side="top"
          align="start"
          className="bg-slate-900 text-white text-[11px] leading-tight max-w-[220px]"
        >
          <div dir="rtl" className="space-y-0.5">
            <div>
              <span className="font-semibold">سجَّله:</span>{' '}
              {recorderName || '—'}
            </div>
            {relTime && (
              <div className="opacity-80">{relTime}</div>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

// ─── Top-level KPI card ────────────────────────────────────────────────────
// Light "data-dense" aesthetic: clean white surface, soft shadow, rounded
// corners, and a thick colored top border that signals the metric's category
// (operational, attention, critical, etc.).
function KpiCard({ icon: Icon, label, value, suffix, accent }) {
  // accent: { topBorder, iconBg, iconText, valueText }
  return (
    <Card className={`bg-white shadow-sm rounded-lg border border-slate-200 border-t-4 ${accent.topBorder}`}>
      <CardContent className="p-4 flex items-center gap-4">
        <div className={`h-11 w-11 rounded-lg flex items-center justify-center ${accent.iconBg}`}>
          <Icon className={`h-5 w-5 ${accent.iconText}`} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[11px] font-medium text-slate-500 mb-0.5 truncate">{label}</p>
          <div className="flex items-baseline gap-1">
            <span className={`text-2xl font-bold ${accent.valueText}`}>{value}</span>
            {suffix && <span className="text-xs text-slate-400">{suffix}</span>}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ─── Cell renderers ────────────────────────────────────────────────────────
// Compact, "data-dense" cells: tiny text, subtle borders, no boxy borders
// inside cells — the matrix relies on the parent grid lines for separation.
function FilledCell({ cell, onClick }) {
  // cell.is_vacant => حصة شاغرة (معلمها غائب) — تفتح نافذة المرشحين عند الضغط
  if (cell?.is_vacant) {
    return (
      <button
        type="button"
        onClick={onClick}
        title="اضغط لاختيار بديل من جدول الانتظار"
        className="w-full h-full flex flex-col items-center justify-center text-[10px] font-semibold leading-tight px-1
                   bg-red-50 hover:bg-red-100 text-red-600 transition-colors"
      >
        <span className="font-bold">شاغرة</span>
        <span className="text-[9px] opacity-75 truncate max-w-full">{cell.class_name}</span>
      </button>
    );
  }
  // cell.is_substituted => الخانة الأصلية للمعلم الغائب بعد إسناد بديل
  if (cell?.is_substituted) {
    return (
      <div
        className="w-full h-full flex flex-col items-center justify-center text-[10px] leading-tight px-1
                   bg-emerald-50/70 text-emerald-700"
        title={`بديل: ${cell.substitute_teacher_name || ''}`}
      >
        <span className="font-semibold">{cell.class_name || '—'}</span>
        <span className="text-[9px] truncate max-w-full opacity-80">
          بديل: {cell.substitute_teacher_name || '—'}
        </span>
      </div>
    );
  }
  // cell.is_substitute => الخانة المضافة لصف المعلم البديل
  if (cell?.is_substitute) {
    return (
      <div
        className="w-full h-full flex flex-col items-center justify-center text-[10px] leading-tight px-1
                   bg-violet-50/70 text-violet-700 relative"
        title={`بديل عن ${cell.original_teacher_name || ''}`}
      >
        <Repeat className="absolute top-0.5 right-0.5 h-2.5 w-2.5 opacity-60" />
        <span className="font-semibold">{cell.class_name || '—'}</span>
        <span className="text-[9px] truncate max-w-full opacity-80">
          {cell.subject_name || ''}
        </span>
      </div>
    );
  }
  return (
    <div
      className="w-full h-full flex flex-col items-center justify-center text-[10px] leading-tight px-1 text-blue-600/80"
      title={cell?.subject_name || ''}
    >
      <span className="font-semibold">{cell?.class_name || '—'}</span>
      {cell?.subject_name && (
        <span className="text-[9px] text-slate-400 truncate max-w-full">{cell.subject_name}</span>
      )}
    </div>
  );
}

function EmptyCell() {
  // فراغ في صف المعلم — لا تنبيه. حتى لو كان المعلم غائباً، الخلية الفارغة
  // تبقى فارغة وتكتفي بصبغة الصف الحمراء الخفيفة. الخانات التي يجب وسمها
  // "شاغرة" تُرَنْدَر عبر FilledCell.is_vacant = true.
  return <div className="w-full h-full" />;
}

// ─── Hakeem-branded loading overlay ─────────────────────────────────────────
// يُعرض فوق المصفوفة أثناء توليد الجدول التلقائي. يستخدم تعبير "ai-thinking"
// من معرض حكيم مع ضباب أبيض شفّاف ونبضة بنفسجية لتأكيد أن المحرك يعمل.
function HakimGeneratingOverlay() {
  const poseSrc = getPose('ai-thinking');
  return (
    <div className="absolute inset-0 z-40 flex items-center justify-center bg-white/85 backdrop-blur-[2px]">
      <div className="flex flex-col items-center gap-3 px-6 py-5 rounded-xl bg-white border border-violet-200 shadow-lg">
        <div className="relative">
          <div className="absolute inset-0 rounded-full bg-violet-300/40 animate-ping" />
          <img
            src={poseSrc}
            alt="حكيم يفكّر"
            className="relative h-20 w-20 object-contain"
            draggable={false}
          />
        </div>
        <div className="flex items-center gap-2 text-violet-700">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="text-sm font-semibold">
            حكيم يقوم بتحليل القيود وبناء الجدول الذكي…
          </span>
        </div>
        <p className="text-[11px] text-slate-500 max-w-[260px] text-center">
          قد تستغرق العملية بضع ثوانٍ بحسب عدد المعلمين والفصول وقيود الجدول.
        </p>
      </div>
    </div>
  );
}

// ─── رؤى حكيم — شريط ملخّص + درج تفصيلي ──────────────────────────────────
// الشريط يلخّص العدد فقط، ويفتح زر «عرض التفاصيل» درجاً جانبياً (Sheet)
// يسرد كلّ العناصر بدون اقتطاع، مجمَّعة حسب الفصل ثم المادة. كلّ صف يحمل
// زر «فتح الإعدادات» يأخذ المدير مباشرةً إلى التبويب الفرعي المناسب
// (timings / classes / teacher-assignments / unavailability / constraints)
// بناءً على `settings_tab` القادم من الباك‑إند (مع fallback عبر reason_code
// لو شغّل الواجهةَ خادمٌ قديمٌ لا يُرسل هذا الحقل). يحتوي رأس الدرج زرَّ
// «إعادة المحاولة» الذي يُعيد تشغيل التوليد بعد إصلاح القيد.
//
// التبويبات الخمسة في صفحة إعدادات الجدول مسجَّلة في
// `ScheduleSettingsTabContent.jsx`، ونوجِّه الزر إلى الرابط
// `/school/schedule?tab=settings&sub=<tab>` الذي تُحسن الصفحة قراءته.

const SETTINGS_TAB_LABEL = {
  'timings': 'التوقيت والحصص',
  'classes': 'الفصول والشعب',
  'teacher-assignments': 'إسناد المعلمين',
  'unavailability': 'أوقات عدم التوفر',
  'constraints': 'قيود الجدول',
};
const VALID_SETTINGS_TABS = Object.keys(SETTINGS_TAB_LABEL);
const REASON_TO_SETTINGS_TAB = {
  // Conflicts emitted by the constraint detector.
  teacher_overlap: 'teacher-assignments',
  class_overlap: 'classes',
  room_overlap: 'timings',
  subject_consecutive: 'constraints',
  teacher_overload: 'teacher-assignments',
  subject_quota_violation: 'teacher-assignments',
  daily_period_limit_exceeded: 'constraints',
  availability: 'unavailability',
  constraint_violation: 'constraints',
  // Classified unscheduled-demand codes (engine baseline loop).
  no_working_days: 'timings',
  no_suitable_teacher: 'teacher-assignments',
  class_busy: 'classes',
  teacher_unavailable: 'unavailability',
  teacher_busy: 'teacher-assignments',
  teacher_load_exceeded: 'teacher-assignments',
  max_consecutive_reached: 'constraints',
  constraint_rejected: 'constraints',
  // Generic fallbacks.
  unscheduled_unknown: 'teacher-assignments',
  UNSCHEDULED: 'teacher-assignments',
};
const DEFAULT_SETTINGS_TAB = 'teacher-assignments';

function resolveSettingsTab(item) {
  const fromBackend = item?.settings_tab;
  if (fromBackend && VALID_SETTINGS_TABS.includes(fromBackend)) return fromBackend;
  return REASON_TO_SETTINGS_TAB[item?.reason_code] || DEFAULT_SETTINGS_TAB;
}

const DAY_LABEL_AR = {
  sunday: 'الأحد',
  monday: 'الإثنين',
  tuesday: 'الثلاثاء',
  wednesday: 'الأربعاء',
  thursday: 'الخميس',
};

function HakimInsightsBanner({ conflicts, dismissed, onDismiss, onOpenDrawer }) {
  if (!conflicts || conflicts.length === 0 || dismissed) return null;
  const total = conflicts.length;
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg border border-orange-200 bg-orange-50 text-orange-900 shrink-0">
      <Lightbulb className="h-5 w-5 shrink-0 text-orange-500" />
      <p className="flex-1 min-w-0 text-sm font-bold truncate text-right">
        رؤى حكيم • تعذّر جدولة {total} حصة
      </p>
      <Button
        type="button"
        size="sm"
        variant="outline"
        onClick={onOpenDrawer}
        className="shrink-0 border-orange-300 text-orange-800 hover:bg-orange-100 bg-white/70"
        data-testid="open-hakim-insights-drawer"
      >
        <Lightbulb className="h-3.5 w-3.5 ml-1" />
        عرض التفاصيل
      </Button>
      <button
        type="button"
        onClick={onDismiss}
        title="إخفاء الشريط"
        aria-label="إخفاء شريط رؤى حكيم"
        className="shrink-0 rounded p-1 text-orange-700 hover:bg-orange-100 transition-colors"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

// درج «رؤى حكيم» — يعرض كل العناصر بلا اقتطاع، مع زر إعادة المحاولة
// وروابط مباشرة إلى التبويبات الفرعية الخمس لإعدادات الجدول.
function HakimInsightsDrawer({
  open,
  onOpenChange,
  conflicts,
  onNavigate,
  onRetry,
  retrying,
}) {
  const items = conflicts || [];
  const total = items.length;

  // تجميع: class_name → subject_name → [items]
  const grouped = useMemo(() => {
    const m = new Map();
    for (const c of items) {
      const cls = c.class_name || '—';
      const subj = c.subject_name || '—';
      if (!m.has(cls)) m.set(cls, new Map());
      const subMap = m.get(cls);
      if (!subMap.has(subj)) subMap.set(subj, []);
      subMap.get(subj).push(c);
    }
    return m;
  }, [items]);

  // تفصيل سريع لتوقيت الحصة عند توفُّره (للتعارضات بخلاف الطلبات
  // المتبقية بدون موعد).
  const slotLabel = (item) => {
    if (!item.day_of_week || !item.period_number) return '';
    const day = DAY_LABEL_AR[item.day_of_week] || item.day_of_week;
    return `${day} • الحصة ${item.period_number}`;
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="left"
        dir="rtl"
        className="w-full sm:max-w-lg p-0 flex flex-col gap-0"
        data-testid="hakim-insights-drawer"
      >
        <SheetHeader className="p-5 bg-gradient-to-l from-orange-100 to-amber-50 border-b border-orange-200 text-right">
          <SheetTitle className="flex items-center gap-2 text-orange-900">
            <Lightbulb className="h-5 w-5 text-orange-500" />
            رؤى حكيم — تفاصيل الحصص غير المُجدولة
          </SheetTitle>
          <SheetDescription className="text-orange-800/90 text-xs leading-relaxed">
            {total > 0
              ? `تعذّرت جدولة ${total} عنصر. لكل صف زر يفتح التبويب الذي يساعدك على إصلاح السبب.`
              : 'لا توجد عناصر غير مُجدولة حالياً.'}
          </SheetDescription>
          <div className="pt-2">
            <Button
              type="button"
              size="sm"
              onClick={onRetry}
              disabled={retrying}
              className="bg-violet-600 hover:bg-violet-700 text-white"
              data-testid="hakim-insights-retry"
            >
              {retrying
                ? <Loader2 className="h-3.5 w-3.5 ml-1 animate-spin" />
                : <RefreshCw className="h-3.5 w-3.5 ml-1" />}
              {retrying ? 'جارٍ إعادة التوليد…' : 'إعادة المحاولة'}
            </Button>
          </div>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-50">
          {total === 0 ? (
            <p className="text-sm text-slate-500 text-center py-10">
              لا توجد بيانات لعرضها.
            </p>
          ) : (
            Array.from(grouped.entries()).map(([cls, subMap]) => (
              <div
                key={cls}
                className="rounded-lg border border-orange-200 bg-white shadow-sm overflow-hidden"
              >
                <div className="px-3 py-2 bg-orange-50 border-b border-orange-200 font-bold text-orange-900 text-sm">
                  {cls}
                </div>
                <ul className="divide-y divide-slate-100">
                  {Array.from(subMap.entries()).map(([subj, rows]) => (
                    <li key={subj} className="p-3">
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <span className="font-semibold text-slate-800 text-sm truncate">
                          {subj}
                        </span>
                        <Badge
                          variant="outline"
                          className="border-orange-300 text-orange-700 bg-orange-50 text-[10px] shrink-0"
                        >
                          {rows.length} عنصر
                        </Badge>
                      </div>
                      <ul className="space-y-2">
                        {rows.map((c, i) => {
                          const tab = resolveSettingsTab(c);
                          const tabLabel = SETTINGS_TAB_LABEL[tab] || 'الإعدادات';
                          const slot = slotLabel(c);
                          return (
                            <li
                              key={i}
                              className="rounded border border-slate-200 bg-slate-50/60 p-2 text-[12px] leading-relaxed"
                            >
                              <div className="flex items-start justify-between gap-2">
                                <div className="min-w-0 flex-1">
                                  {slot && (
                                    <p className="text-[11px] font-semibold text-slate-500 mb-0.5">
                                      {slot}
                                    </p>
                                  )}
                                  <p className="text-slate-800">
                                    {c.reason_ar || 'تعذّر الجدولة'}
                                  </p>
                                  {c.reason_code && (
                                    <p className="mt-0.5 text-[10px] font-mono text-slate-400">
                                      {c.reason_code}
                                    </p>
                                  )}
                                </div>
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  onClick={() => onNavigate(tab)}
                                  className="shrink-0 border-[#1C3D74]/30 text-[#1C3D74] hover:bg-[#1C3D74]/5 text-[11px] h-7"
                                  data-testid={`hakim-insights-open-${tab}`}
                                >
                                  <ExternalLink className="h-3 w-3 ml-1" />
                                  {tabLabel}
                                </Button>
                              </div>
                            </li>
                          );
                        })}
                      </ul>
                    </li>
                  ))}
                </ul>
              </div>
            ))
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}

// ─── Main page ─────────────────────────────────────────────────────────────
// ─── Active primary tab from URL ────────────────────────────────────────────
// التبويب الرئيسي للصفحة يُقرأ من معطى ?tab= في الرابط. تُقبل ثلاث قيم
// فقط: master (افتراضي) و standby و settings، وأي قيمة أخرى تُعامَل
// كـ master لتفادي صفحة فارغة.
const VALID_TABS = ['master', 'standby', 'settings'];
function useScheduleTab() {
  const location = useLocation();
  const params = new URLSearchParams(location.search);
  const raw = params.get('tab');
  return VALID_TABS.includes(raw) ? raw : 'master';
}

export default function SchedulePageNew() {
  const { user, api } = useAuth();
  const navigate = useNavigate();
  const schoolId = user?.tenant_id;
  const tab = useScheduleTab();
  const { nassaqError, nassaqWarning } = useNassaqAlert();

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [grid, setGrid] = useState(null);

  // Substitution drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerSlot, setDrawerSlot] = useState(null);

  // Bulk substitution drawer state
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkTarget, setBulkTarget] = useState(null);

  // إنشاء الجدول تلقائياً
  const [generating, setGenerating] = useState(false);

  // رؤى حكيم — قائمة التعارضات/الخانات التي تعذّر جدولتها بعد آخر تشغيل،
  // مع خانة قابلة للإغلاق تخزن تفضيل المستخدم لإخفاء الشريط لجلسة العمل.
  const [unresolvedConflicts, setUnresolvedConflicts] = useState([]);
  const [insightsDismissed, setInsightsDismissed] = useState(false);
  // درج «رؤى حكيم» التفصيلي — يفتحه المدير عبر زر «عرض التفاصيل».
  const [insightsDrawerOpen, setInsightsDrawerOpen] = useState(false);

  // حوار "تعذّر التوليد" مع تفاصيل الـ infeasibility report
  const [blockedOpen, setBlockedOpen] = useState(false);
  const [blockedReport, setBlockedReport] = useState(null);

  // تسجيل الغياب
  const [absenceOpen, setAbsenceOpen] = useState(false);
  const [absenceTeacherId, setAbsenceTeacherId] = useState('');
  const [absenceNotes, setAbsenceNotes] = useState('');
  const [savingAbsence, setSavingAbsence] = useState(false);

  // إلغاء الغياب
  const [undoTeacher, setUndoTeacher] = useState(null);
  const [undoingAbsence, setUndoingAbsence] = useState(false);

  const loadGrid = useCallback(async () => {
    // ملاحظة على القيمة المُعادة: نُعيد الـ payload نفسه عند النجاح (لا
    // مجرد boolean) كي يستطيع المستدعي مقارنته بمعرّف الجدول المتوقَّع
    // بعد التوليد دون الاعتماد على state React الذي لا يتحدّث داخل
    // closure نفس الدالة. عند الفشل نُعيد null.
    if (!schoolId) return null;
    try {
      // إضافة بصمة زمنية (`_t`) لإجبار المتصفح/أي وسيط على تجاوز أي
      // نسخة مخزَّنة من الاستجابة. الباك إند يضع Cache-Control: no-store،
      // ولكن نُضيف هذه الحماية الإضافية لأن بعض الإضافات/البروكسيات
      // تتجاهل ترويسات منع التخزين. مهم بشكل خاص بعد التوليد التلقائي
      // كي تُعرض المسودة الجديدة بدلاً من البيانات القديمة.
      const response = await api.get('/schedule/master-grid', {
        params: { school_id: schoolId, _t: Date.now() },
        headers: {
          'X-School-Context': schoolId,
          'Cache-Control': 'no-cache',
          'Pragma': 'no-cache',
        },
      });
      setGrid(response.data);
      setError('');
      return response.data;
    } catch (e) {
      const msg = e?.response?.data?.error?.message || e?.message || 'تعذّر تحميل الجدول';
      setError(msg);
      return null;
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [api, schoolId]);

  useEffect(() => {
    // نُحمِّل مصفوفة الجدول الرئيسي فقط عندما يكون التبويب النشط هو
    // "الجدول الرئيسي" — تبويبا الانتظار والإعدادات لهما تحميل بياناتهما
    // الخاص داخل مكوّناتهما.
    if (tab !== 'master') return;
    loadGrid();
  }, [loadGrid, tab]);

  const handleAutoGenerate = useCallback(async () => {
    if (!schoolId) {
      nassaqError('تعذّر تحديد المدرسة الحالية');
      return;
    }
    if (generating) return;

    setGenerating(true);
    setInsightsDismissed(false);
    setUnresolvedConflicts([]);

    try {
      const response = await api.post(
        `/smart-scheduling/generate/${schoolId}`,
        {},
        { headers: { 'X-School-Context': schoolId } },
      );
      const data = response.data || {};
      const scheduled = data.scheduled_sessions ?? 0;
      const total = data.total_sessions ?? 0;
      const conflicts = data.conflicts_count ?? 0;
      const unscheduled = data.unscheduled_count ?? 0;
      const pct = Math.round(data.completion_percentage ?? 0);
      const summary =
        `تم جدولة ${scheduled} من ${total} حصة (${pct}%)` +
        (conflicts ? ` • ${conflicts} تعارض` : '') +
        (unscheduled ? ` • ${unscheduled} حصة لم تُجدول` : '');

      // رؤى حكيم: نلتقط قائمة التعارضات/الخانات غير المجدولة لتغذية شريط
      // الرؤى وتلوين الخلايا. عند الفشل التام تظل القائمة فارغة.
      const insights = Array.isArray(data.unresolved_conflicts) ? data.unresolved_conflicts : [];
      setUnresolvedConflicts(insights);

      // ──────────────────────────────────────────────────────────────────
      // ترتيب مهمّ: نُعيد تحميل المصفوفة *قبل* عرض إشعار النجاح، حتى لا
      // يرى المدير "تم توليد الجدول بنجاح" بينما الشاشة لا تزال تعرض
      // البيانات القديمة. هذا يحقّق متطلب "اللحظة التي يظهر فيها الإشعار
      // يكون الجدول قد تحدّث فعلاً".
      //
      // إعادة محاولة واحدة احترازية: لو رجع الـ GET الأول بمعرّف جدول
      // غير المعرّف الذي قال محرك التوليد إنه أنشأه (سباق نادر بين الـ
      // commit وقراءة المصفوفة)، ننتظر 400 ميلي ثانية ونُعيد المحاولة.
      // نعتمد على القيمة المُعادة من loadGrid مباشرةً لا على state React
      // (الذي لا يتحدّث داخل نفس الـ closure).
      // ──────────────────────────────────────────────────────────────────
      setRefreshing(true);
      const expectedId = data.timetable_id || null;
      let fetched = await loadGrid();
      // الجلب يُعتبر "بائتاً" لو وُجد expectedId ولم يطابق ما رجع من
      // الخادم — بما في ذلك حالة فشل المحاولة الثانية بعد عدم التطابق
      // الأول (نحتفظ بإشارة "بائت" بدلاً من الخلط بينها وبين فشل الشبكة).
      let staleAfterRetry = false;
      if (fetched && expectedId && fetched.timetable_id !== expectedId) {
        await new Promise((r) => setTimeout(r, 400));
        const retry = await loadGrid();
        if (retry && retry.timetable_id === expectedId) {
          fetched = retry;
        } else {
          // المحاولة الثانية إمّا فشلت شبكياً وإمّا رجعت بنفس الجدول
          // القديم. نعتبر العرض بائتاً لتشغيل تنبيه التحديث اليدوي.
          staleAfterRetry = true;
          if (retry) fetched = retry;
        }
      }

      // ننتظر إعادة الرسم (frame) قبل توقيت الإشعار، فيُرى الإشعار والشاشة
      // المُحدَّثة في نفس اللحظة بصرياً.
      await new Promise((resolve) => requestAnimationFrame(() => resolve()));

      // نتعامل مع نتيجة المحرك (نجاح كامل/جزئي) ونتيجة الجلب (نجح/فشل) بشكل
      // مستقل، حتى لا تُغطّي رسالة الجلب الفاشل ملاحظات حكيم على التوليد
      // الجزئي. الترتيب: أولاً إشعار حالة التوليد (نجاح/جزئي)، ثم — إن
      // فشل الجلب — إشعار خطأ صريح إضافي حول العرض القديم.
      if (data.success) {
        toast.success(data.message_ar || 'تم توليد الجدول بنجاح', {
          description: summary,
        });
      } else {
        // اكتمل التشغيل مع ملاحظات — نرفعها كحوار رؤى حكيم بدلاً من تنبيه toast
        // عابر، حتى لا تضيع المعلومة المهمّة على المدير. هذه المعلومات
        // مستقلّة عن نجاح/فشل إعادة الجلب.
        nassaqWarning(
          (data.message_ar || 'اكتمل التوليد مع ملاحظات') + '\n\n' + summary,
          { title: 'رؤى حكيم — اكتمل التوليد جزئياً' },
        );
      }
      if (!fetched || staleAfterRetry) {
        // توليد (كامل أو جزئي) نجح في الكتابة لقاعدة البيانات لكن العرض
        // قديم — إمّا لأن جلب المصفوفة فشل شبكياً، وإمّا لأن المحاولة
        // الثانية بعد عدم تطابق المعرّف لم تُرجع الجدول الجديد. في كلتا
        // الحالتين نعرض خطأ صريح بالعبارة المحدَّدة في خطّة المهمة كي لا
        // يُترك المدير أمام شاشة قديمة دون تنبيه.
        nassaqError(
          'تعذّر تحميل الجدول المُحدَّث — اضغط "تحديث" لعرض الجدول الجديد.',
          { title: 'تعذّر تحديث المصفوفة' },
        );
      }
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const status = e?.response?.status;

      // الحالة الخاصة: المحرك يرفض التشغيل بسبب بيانات ناقصة → نعرض حواراً
      // مفصَّلاً بالأسباب بدلاً من رسالة عامة، حتى يستطيع المدير معالجتها فوراً.
      if (status === 422 && detail?.code === 'GENERATION_BLOCKED' && detail?.report) {
        setBlockedReport(detail.report);
        setBlockedOpen(true);
        return;
      }

      let msg = 'فشل توليد الجدول، يرجى المحاولة مرة أخرى';
      if (typeof detail === 'string' && /[\u0600-\u06FF]/.test(detail)) {
        msg = detail;
      } else if (detail?.code === 'GENERATION_BLOCKED') {
        // Fallback: server returned the code but no report payload.
        msg = 'تعذّر التوليد: البيانات غير جاهزة بعد لتشغيل المحرك';
      } else if (e?.response?.data?.message_ar) {
        msg = e.response.data.message_ar;
      } else if (status === 401 || status === 403) {
        msg = 'لا تملك صلاحية تشغيل التوليد التلقائي';
      } else if (status === 404) {
        msg = 'لم يتم العثور على بيانات المدرسة المطلوبة';
      } else if (e?.code === 'ERR_NETWORK' || !e?.response) {
        msg = 'تعذّر الاتصال بالخادم، تحقق من الشبكة وحاول مجدداً';
      }
      nassaqError(msg, { title: 'تعذّر توليد الجدول' });
    } finally {
      setGenerating(false);
    }
  }, [api, schoolId, generating, loadGrid, nassaqError, nassaqWarning]);

  const handleLogAbsence = useCallback(() => {
    setAbsenceTeacherId('');
    setAbsenceNotes('');
    setAbsenceOpen(true);
  }, []);

  const handleSubmitAbsence = useCallback(async () => {
    if (!absenceTeacherId) {
      toast.error('يرجى اختيار معلم');
      return;
    }
    if (!schoolId) {
      toast.error('تعذّر تحديد المدرسة الحالية');
      return;
    }

    const today = new Date().toISOString().split('T')[0];
    setSavingAbsence(true);
    try {
      await api.post(
        '/teacher-attendance/bulk',
        {
          records: [
            {
              teacher_id: absenceTeacherId,
              date: today,
              status: 'absent',
              check_in_time: null,
              notes: absenceNotes || '',
            },
          ],
        },
        { headers: { 'X-School-Context': schoolId } },
      );
      toast.success('تم تسجيل الغياب');
      setAbsenceOpen(false);
      setAbsenceTeacherId('');
      setAbsenceNotes('');
      setRefreshing(true);
      await loadGrid();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const status = e?.response?.status;
      let msg = 'فشل تسجيل الغياب، يرجى المحاولة مرة أخرى';
      if (typeof detail === 'string' && /[\u0600-\u06FF]/.test(detail)) {
        msg = detail;
      } else if (e?.response?.data?.message_ar) {
        msg = e.response.data.message_ar;
      } else if (status === 401 || status === 403) {
        msg = 'لا تملك صلاحية تسجيل الغياب';
      } else if (e?.code === 'ERR_NETWORK' || !e?.response) {
        msg = 'تعذّر الاتصال بالخادم، تحقق من الشبكة وحاول مجدداً';
      }
      toast.error(msg);
    } finally {
      setSavingAbsence(false);
    }
  }, [api, schoolId, absenceTeacherId, absenceNotes, loadGrid]);

  const handleRequestUndoAbsence = useCallback((teacher) => {
    if (!teacher?.id) return;
    setUndoTeacher({ id: teacher.id, full_name: teacher.full_name || '' });
  }, []);

  const handleConfirmUndoAbsence = useCallback(async () => {
    if (!undoTeacher?.id) return;
    if (!schoolId) {
      toast.error('تعذّر تحديد المدرسة الحالية');
      return;
    }

    const today = new Date().toISOString().split('T')[0];
    setUndoingAbsence(true);
    try {
      await api.post(
        '/teacher-attendance/bulk',
        {
          records: [
            {
              teacher_id: undoTeacher.id,
              date: today,
              status: 'present',
              check_in_time: null,
              notes: '',
            },
          ],
        },
        { headers: { 'X-School-Context': schoolId } },
      );
      toast.success('تم إلغاء الغياب');
      setUndoTeacher(null);
      setRefreshing(true);
      await loadGrid();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const status = e?.response?.status;
      let msg = 'فشل إلغاء الغياب، يرجى المحاولة مرة أخرى';
      if (typeof detail === 'string' && /[\u0600-\u06FF]/.test(detail)) {
        msg = detail;
      } else if (e?.response?.data?.message_ar) {
        msg = e.response.data.message_ar;
      } else if (status === 401 || status === 403) {
        msg = 'لا تملك صلاحية تعديل سجل الحضور';
      } else if (e?.code === 'ERR_NETWORK' || !e?.response) {
        msg = 'تعذّر الاتصال بالخادم، تحقق من الشبكة وحاول مجدداً';
      }
      toast.error(msg);
    } finally {
      setUndoingAbsence(false);
    }
  }, [api, schoolId, undoTeacher, loadGrid]);

  const handleVacantClick = useCallback((cellData) => {
    if (!cellData?.session?.session_id) {
      toast.error('لا يمكن فتح المرشحين — الخانة لا ترتبط بحصة معروفة');
      return;
    }
    const today = grid?.today || cellData.day_of_week;
    const todayDate = new Date().toISOString().slice(0, 10);
    setDrawerSlot({
      original_session_id: cellData.session.session_id,
      day_of_week: cellData.day_of_week,
      period_number: cellData.period_number,
      class_id: cellData.session.class_id,
      class_name: cellData.session.class_name,
      subject_id: cellData.session.subject_id,
      subject_name: cellData.session.subject_name,
      absent_teacher_name: cellData.teacher_name,
      absence_date: cellData.day_of_week === today ? todayDate : todayDate,
      school_id: schoolId,
    });
    setDrawerOpen(true);
  }, [grid?.today, schoolId]);

  const handleUndoSubstitution = useCallback(async (substitutionId) => {
    try {
      await api.delete(`/substitutions/${substitutionId}`, {
        params: { school_id: schoolId },
        headers: { 'X-School-Context': schoolId },
      });
      await loadGrid();
      toast.success('تم التراجع عن الإسناد');
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'فشل التراجع';
      toast.error(msg);
    }
  }, [api, schoolId, loadGrid]);

  const handleAssigned = useCallback((substitution, cand) => {
    // Optimistic refresh + undo toast
    loadGrid();
    const subId = substitution?.id;
    toast.success('تم إسناد الحصة وإرسال إشعار', {
      description: `البديل: ${cand?.teacher_name || '—'}`,
      duration: 10000,
      action: subId
        ? { label: 'تراجع', onClick: () => handleUndoSubstitution(subId) }
        : undefined,
    });
  }, [loadGrid, handleUndoSubstitution]);

  // ── Bulk substitution handlers ─────────────────────────────────────
  const handleOpenBulkPanel = useCallback((teacher) => {
    if (!teacher?.id) return;
    const todayDate = new Date().toISOString().slice(0, 10);
    setBulkTarget({
      absent_teacher_id: teacher.id,
      absent_teacher_name: teacher.full_name,
      absence_date: todayDate,
      school_id: schoolId,
    });
    setBulkOpen(true);
  }, [schoolId]);

  const handleUndoBulkBatch = useCallback(async (batchId) => {
    if (!batchId) return;
    try {
      await api.delete(`/substitutions/batch/${batchId}`, {
        params: { school_id: schoolId },
        headers: { 'X-School-Context': schoolId },
      });
      await loadGrid();
      toast.success('تم التراجع عن الدفعة بالكامل');
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'فشل التراجع عن الدفعة';
      toast.error(msg);
    }
  }, [api, schoolId, loadGrid]);

  const handleAssignedBatch = useCallback((batchResult) => {
    loadGrid();
    const succeeded = batchResult?.succeeded || 0;
    const failed = batchResult?.failed || 0;
    const batchId = batchResult?.batch_id;
    if (succeeded === 0) return;

    const description = failed > 0
      ? `نجح ${succeeded} وفشل ${failed} — تم إرسال إشعار مجمَّع لكل بديل`
      : `تم إرسال إشعار مجمَّع لكل بديل — ${succeeded} حصة`;

    toast.success(`تم إسناد ${succeeded} حصة دفعة واحدة`, {
      description,
      duration: 12000,
      action: batchId
        ? { label: 'تراجع عن الدفعة', onClick: () => handleUndoBulkBatch(batchId) }
        : undefined,
    });
  }, [loadGrid, handleUndoBulkBatch]);

  const handleRefresh = useCallback(() => {
    setRefreshing(true);
    loadGrid();
  }, [loadGrid]);

  // ── Derived grid view model ───────────────────────────────────────────
  const teacherRows = grid?.teachers || [];
  const cellsByTeacher = grid?.cells || {};
  const days = grid?.days || DAYS.map(d => d.key);
  const periods = grid?.periods || FALLBACK_PERIODS;
  const kpis = grid?.kpis || { fairness_pct: 0, assigned_waiting: 0, absent_teachers_today: 0, vacant_sessions_today: 0 };
  const alertText = grid?.alert;

  const dayLabelMap = useMemo(() => Object.fromEntries(DAYS.map(d => [d.key, d.ar])), []);

  if (tab === 'standby') {
    // تبويب جدول حصص الانتظار — يُضمَّن المحتوى نفسه المستخدم في الصفحة
    // المستقلة `/school/standby` بدون لمس مصدر بياناته.
    return (
      <Sidebar>
        <div
          dir="rtl"
          className="flex flex-col h-[calc(100dvh-3.5rem)] lg:h-[100dvh] p-4 md:p-6 gap-5 bg-slate-50 text-slate-900 overflow-hidden"
        >
          <ScheduleTabNav active="standby" />
          <StandbyRosterContent />
        </div>
      </Sidebar>
    );
  }

  if (tab === 'settings') {
    return (
      <Sidebar>
        <div
          dir="rtl"
          className="min-h-[calc(100dvh-3.5rem)] lg:min-h-[100dvh] bg-slate-50 text-slate-900"
        >
          <div className="p-4 md:p-6 flex flex-col gap-5">
            {/* ── Primary tab nav (Master / Standby / Settings) ─────────── */}
            <ScheduleTabNav active="settings" />

            {/* ── Header ───────────────────────────────────────────────── */}
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
              <div>
                <h1 className="text-2xl md:text-3xl font-bold text-[#1C3D74] flex items-center gap-2">
                  <Settings className="h-7 w-7 text-[#1C3D74]" />
                  إعدادات الجدول المدرسي
                </h1>
                <p className="text-sm text-slate-500 mt-1">
                  أَعِدّ التوقيت والحصص والفصول والإسناد وأوقات عدم التوفر وقيود الجدول من مكان واحد.
                </p>
              </div>
            </div>

            <ScheduleSettingsTabContent />
          </div>
        </div>
      </Sidebar>
    );
  }

  return (
    <Sidebar>
      <div
        dir="rtl"
        className="flex flex-col h-[calc(100dvh-3.5rem)] lg:h-[100dvh] p-4 md:p-6 gap-5 bg-slate-50 text-slate-900 overflow-hidden"
      >
        {/* ── Primary tab nav (Master / Standby / Settings) ─────────── */}
        <ScheduleTabNav active="master" />

        {/* ── Header ───────────────────────────────────────────────── */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 shrink-0">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-[#1C3D74] flex items-center gap-2">
              <Sparkles className="h-7 w-7 text-violet-600" />
              إدارة الجداول الذكية
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              مصفوفة موحَّدة لكل المعلمين × أيام الأسبوع × الحصص — مع متابعة لحظية للحصص الشاغرة.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              onClick={handleAutoGenerate}
              disabled={generating}
              className="bg-violet-600 hover:bg-violet-700 text-white shadow-md"
            >
              {generating ? (
                <Loader2 className="h-4 w-4 ml-2 animate-spin" />
              ) : (
                <Wand2 className="h-4 w-4 ml-2" />
              )}
              {generating ? 'جارٍ التوليد…' : 'إنشاء الجدول تلقائياً'}
            </Button>
            <Button
              onClick={handleLogAbsence}
              variant="outline"
              className="border-slate-300 text-slate-700 hover:bg-slate-100"
            >
              <UserX className="h-4 w-4 ml-2" />
              تسجيل غياب
            </Button>
            <Button
              onClick={handleRefresh}
              variant="ghost"
              size="icon"
              disabled={refreshing}
              title="تحديث"
            >
              <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </div>

        {/* ── KPI cards ────────────────────────────────────────────── */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 shrink-0">
          <KpiCard
            icon={Scale}
            label="عدالة التوزيع"
            value={kpis.fairness_pct}
            suffix="%"
            accent={{
              topBorder: 'border-t-orange-400',
              iconBg: 'bg-orange-50', iconText: 'text-orange-600',
              valueText: 'text-slate-900',
            }}
          />
          <KpiCard
            icon={Hourglass}
            label="انتظار مُسند"
            value={kpis.assigned_waiting}
            accent={{
              topBorder: 'border-t-blue-400',
              iconBg: 'bg-blue-50', iconText: 'text-blue-600',
              valueText: 'text-slate-900',
            }}
          />
          <KpiCard
            icon={UserMinus}
            label="معلم غائب"
            value={kpis.absent_teachers_today}
            accent={{
              topBorder: 'border-t-yellow-400',
              iconBg: 'bg-yellow-50', iconText: 'text-yellow-600',
              valueText: 'text-slate-900',
            }}
          />
          <KpiCard
            icon={AlertOctagon}
            label="حصة شاغرة"
            value={kpis.vacant_sessions_today}
            accent={{
              topBorder: 'border-t-red-500',
              iconBg: 'bg-red-50', iconText: 'text-red-600',
              valueText: 'text-red-700',
            }}
          />
        </div>

        {/* ── Smart alert banner ───────────────────────────────────── */}
        {alertText && (
          <div className="flex items-center gap-3 p-3 rounded-lg border border-red-300 bg-red-50 text-red-800 shrink-0">
            <AlertTriangle className="h-5 w-5 shrink-0" />
            <p className="text-sm font-medium">{alertText}</p>
          </div>
        )}

        {/* ── رؤى حكيم — شريط ديناميكي يظهر بعد التوليد عندما توجد
            تعارضات/خانات لم تُجدول. قابل للإغلاق لجلسة العمل الحالية،
            وزر «عرض التفاصيل» يفتح درجاً يسرد كلّ العناصر مع روابط مباشرة
            إلى تبويبات إعدادات الجدول. ─────── */}
        <HakimInsightsBanner
          conflicts={unresolvedConflicts}
          dismissed={insightsDismissed}
          onDismiss={() => setInsightsDismissed(true)}
          onOpenDrawer={() => setInsightsDrawerOpen(true)}
        />

        <HakimInsightsDrawer
          open={insightsDrawerOpen}
          onOpenChange={setInsightsDrawerOpen}
          conflicts={unresolvedConflicts}
          retrying={generating}
          onNavigate={(tab) => {
            // فتح تبويب الإعدادات الفرعي المناسب في تبويب رئيسي جديد كي
            // تبقى نتائج التوليد ظاهرة. عند الفشل (مانع نوافذ منبثقة
            // مثلاً) نستخدم navigate كحلّ احتياطي داخل التبويب نفسه.
            const url = `/school/schedule?tab=settings&sub=${encodeURIComponent(tab)}`;
            const win = window.open(url, '_blank', 'noopener');
            if (!win) navigate(url);
          }}
          onRetry={() => {
            setInsightsDrawerOpen(false);
            handleAutoGenerate();
          }}
        />

        {/* ── Substitution drawer (single slot) ─────────────────────── */}
        <CandidatesSidePanel
          open={drawerOpen}
          onOpenChange={setDrawerOpen}
          slot={drawerSlot}
          api={api}
          onAssigned={handleAssigned}
        />

        {/* ── Bulk substitution drawer (full absent teacher) ─────────── */}
        <BulkSubstitutionPanel
          open={bulkOpen}
          onOpenChange={setBulkOpen}
          target={bulkTarget}
          api={api}
          onAssignedBatch={handleAssignedBatch}
        />

        {/* ── Master matrix grid ─────────────────────────────────────
            Light, breathable container: white surface, single subtle
            border, rounded corners, and a single scroll context that
            owns both axes (no nested boxy scrollbars). */}
        <div className="relative flex-1 min-h-0 overflow-auto bg-white border border-slate-200 rounded-lg">
          {loading ? (
            <div className="flex h-full items-center justify-center py-20 text-slate-500">
              <Loader2 className="h-6 w-6 animate-spin ml-2" />
              جارٍ تحميل المصفوفة…
            </div>
          ) : error ? (
            <div className="p-6 text-center text-red-600">{error}</div>
          ) : teacherRows.length === 0 ? (
            <div className="p-6 text-center text-slate-500">
              لا يوجد معلمون مسجَّلون في هذه المدرسة بعد.
            </div>
          ) : (
            <MasterMatrix
              teachers={teacherRows}
              cells={cellsByTeacher}
              days={days}
              periods={periods}
              dayLabelMap={dayLabelMap}
              onVacantClick={handleVacantClick}
              onUndoAbsence={handleRequestUndoAbsence}
              onBulkCoverClick={handleOpenBulkPanel}
              today={grid?.today}
              unresolvedConflicts={unresolvedConflicts}
            />
          )}

          {/* ── Hakeem-branded loading overlay ────────────────────────
              يظهر فقط أثناء التوليد التلقائي. يستخدم تعبير "ai-thinking"
              من معرض حكيم مع نبضة ضوئية بنفسجية لتأكيد أن المحرك يقرأ
              القيود ويبني الجدول الذكي. */}
          {generating && <HakimGeneratingOverlay />}
        </div>

        {/* ── Absence dialog ─────────────────────────────────────── */}
        <Dialog open={absenceOpen} onOpenChange={setAbsenceOpen}>
          <DialogContent dir="rtl" className="max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-[#1C3D74]">
                <UserX className="h-5 w-5 text-red-600" />
                تسجيل غياب معلم
              </DialogTitle>
              <DialogDescription>
                سيُسجَّل المعلم المختار كغائب اليوم وتُحدَّث الخلايا والمؤشرات فوراً.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-2">
              <div className="space-y-2">
                <Label htmlFor="absence-teacher">المعلم</Label>
                <Select value={absenceTeacherId} onValueChange={setAbsenceTeacherId}>
                  <SelectTrigger id="absence-teacher" className="w-full">
                    <SelectValue placeholder="اختر معلماً…" />
                  </SelectTrigger>
                  <SelectContent>
                    {teacherRows.length === 0 ? (
                      <div className="px-3 py-2 text-sm text-slate-500">
                        لا يوجد معلمون متاحون
                      </div>
                    ) : (
                      teacherRows.map((t) => (
                        <SelectItem key={t.id} value={t.id} disabled={t.is_absent_today}>
                          {t.full_name}
                          {t.is_absent_today ? ' (غائب اليوم)' : ''}
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="absence-notes">ملاحظات (اختياري)</Label>
                <Textarea
                  id="absence-notes"
                  value={absenceNotes}
                  onChange={(e) => setAbsenceNotes(e.target.value)}
                  placeholder="سبب الغياب أو أي ملاحظات…"
                  rows={3}
                />
              </div>
            </div>

            <DialogFooter className="gap-2 sm:gap-2">
              <Button
                variant="outline"
                onClick={() => setAbsenceOpen(false)}
                disabled={savingAbsence}
              >
                إلغاء
              </Button>
              <Button
                onClick={handleSubmitAbsence}
                disabled={savingAbsence || !absenceTeacherId}
                className="bg-red-600 hover:bg-red-700 text-white"
              >
                {savingAbsence ? (
                  <Loader2 className="h-4 w-4 ml-2 animate-spin" />
                ) : (
                  <UserX className="h-4 w-4 ml-2" />
                )}
                {savingAbsence ? 'جارٍ الحفظ…' : 'تسجيل الغياب'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* ── Generation-blocked dialog (HTTP 422 / GENERATION_BLOCKED) ──── */}
        <BlockedGenerationDialog
          open={blockedOpen}
          onOpenChange={setBlockedOpen}
          report={blockedReport}
          onNavigate={(path) => {
            setBlockedOpen(false);
            navigate(path);
          }}
        />

        {/* ── Undo absence confirmation dialog ─────────────────────── */}
        <Dialog
          open={!!undoTeacher}
          onOpenChange={(open) => {
            if (!open && !undoingAbsence) setUndoTeacher(null);
          }}
        >
          <DialogContent dir="rtl" className="max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-[#1C3D74]">
                <Undo2 className="h-5 w-5 text-emerald-600" />
                إلغاء الغياب
              </DialogTitle>
              <DialogDescription>
                سيُعاد تسجيل المعلم كحاضر اليوم وتُحدَّث الخلايا والمؤشرات فوراً.
              </DialogDescription>
            </DialogHeader>

            <div className="py-2 text-sm text-slate-700">
              هل تريد فعلاً إلغاء غياب{' '}
              <span className="font-semibold text-slate-900">
                {undoTeacher?.full_name || '—'}
              </span>{' '}
              لهذا اليوم؟
            </div>

            <DialogFooter className="gap-2 sm:gap-2">
              <Button
                variant="outline"
                onClick={() => setUndoTeacher(null)}
                disabled={undoingAbsence}
              >
                تراجع
              </Button>
              <Button
                onClick={handleConfirmUndoAbsence}
                disabled={undoingAbsence}
                className="bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                {undoingAbsence ? (
                  <Loader2 className="h-4 w-4 ml-2 animate-spin" />
                ) : (
                  <Undo2 className="h-4 w-4 ml-2" />
                )}
                {undoingAbsence ? 'جارٍ الإلغاء…' : 'تأكيد إلغاء الغياب'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Sidebar>
  );
}

// ─── Generation-blocked dialog ─────────────────────────────────────────────
// عند رفض المحرك للتوليد (HTTP 422 / GENERATION_BLOCKED) نعرض هنا قائمة
// المشاكل بالعربية مع زر يفتح الصفحة الأنسب لمعالجة كل مشكلة.
function BlockedGenerationDialog({ open, onOpenChange, report, onNavigate }) {
  const issues = Array.isArray(report?.issues) ? report.issues : [];
  const blockers  = issues.filter((i) => i.severity === 'blocker');
  const advisories = issues.filter((i) => i.severity === 'advisory');

  // اختر الإجراء الأساسي بناءً على أول blocker (أكثر إلحاحاً) أو الافتراضي.
  const primaryStep = (blockers[0] && ISSUE_NEXT_STEP[blockers[0].code]) || DEFAULT_NEXT_STEP;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent dir="rtl" className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-red-700">
            <ShieldAlert className="h-5 w-5" />
            تعذّر تشغيل التوليد التلقائي
          </DialogTitle>
          <DialogDescription>
            رفض المحرك بدء التوليد لأن البيانات الأساسية غير مكتملة. عالج
            النقاط التالية ثم أعد المحاولة:
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 py-2 max-h-[55vh] overflow-y-auto pr-1">
          {issues.length === 0 ? (
            <p className="text-sm text-slate-500 text-center py-6">
              لا توجد تفاصيل إضافية متاحة من المحرك.
            </p>
          ) : (
            <>
              {blockers.length > 0 && (
                <ul className="space-y-2">
                  {blockers.map((iss, idx) => {
                    const step = ISSUE_NEXT_STEP[iss.code] || DEFAULT_NEXT_STEP;
                    return (
                      <li
                        key={`b-${iss.code}-${idx}`}
                        className="rounded-lg border border-red-200 bg-red-50 p-3"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <Badge className="bg-red-600 hover:bg-red-600 text-white text-[10px]">
                                مانع
                              </Badge>
                              <span className="text-[11px] font-mono text-slate-500">
                                {iss.code}
                              </span>
                            </div>
                            <p className="text-sm text-red-900 leading-relaxed">
                              {iss.message_ar || iss.message_en}
                            </p>
                          </div>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            className="border-red-300 text-red-700 hover:bg-red-100 shrink-0"
                            onClick={() => onNavigate(step.path)}
                          >
                            <Settings className="h-3.5 w-3.5 ml-1" />
                            <span className="text-xs">{step.label}</span>
                          </Button>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}

              {advisories.length > 0 && (
                <div className="pt-2">
                  <p className="text-xs font-semibold text-slate-600 mb-2">
                    ملاحظات إضافية (لا تمنع التوليد):
                  </p>
                  <ul className="space-y-2">
                    {advisories.map((iss, idx) => (
                      <li
                        key={`a-${iss.code}-${idx}`}
                        className="rounded-lg border border-amber-200 bg-amber-50 p-3"
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant="outline" className="border-amber-400 text-amber-800 bg-amber-100 text-[10px]">
                            إرشاد
                          </Badge>
                          <span className="text-[11px] font-mono text-slate-500">
                            {iss.code}
                          </span>
                        </div>
                        <p className="text-sm text-amber-900 leading-relaxed">
                          {iss.message_ar || iss.message_en}
                        </p>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>

        <DialogFooter className="gap-2 sm:gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            إغلاق
          </Button>
          <Button
            onClick={() => onNavigate(primaryStep.path)}
            className="bg-[#1C3D74] hover:bg-[#162f5a] text-white"
          >
            <ArrowLeft className="h-4 w-4 ml-2" />
            {primaryStep.label}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ─── Master Matrix Grid Component ─────────────────────────────────────────
// ملاحظة: نستخدم CSS Grid مع `position: sticky` على عمود المعلم وصف الرأس
// للحصول على تثبيت بالاتجاهين في RTL مع تمرير سلس.
//
// التصميم البصري الجديد: خلفية بيضاء، رؤوس فاتحة (slate-50)، حدود رفيعة
// (slate-100)، وعمود المعلم على يمين الشاشة (RTL) مع ظل خفيف يفصل المنطقة
// المثبَّتة عن منطقة التمرير.
function MasterMatrix({ teachers, cells, days, periods, dayLabelMap, onVacantClick, onUndoAbsence, onBulkCoverClick, today, unresolvedConflicts = [] }) {
  // فهرس "رؤى حكيم" بمفتاح teacher_id|day|period → reason_ar. التحديد
  // بالمعلم ضروري لئلا يلوّن صفّ معلم تنبيه يخصّ معلماً آخر في نفس
  // الفترة. العناصر التي لا تحمل teacher_id (مثل طلبات لم تُسنَد لأحد)
  // لا تظهر هنا — تظهر فقط داخل شريط رؤى حكيم.
  const conflictsByCell = useMemo(() => {
    const m = new Map();
    for (const c of unresolvedConflicts) {
      if (!c?.day_of_week || !c?.period_number || !c?.teacher_id) continue;
      const k = `${c.teacher_id}|${c.day_of_week}|${c.period_number}`;
      const prev = m.get(k);
      const reason = [c.subject_name, c.class_name].filter(Boolean).join(' / ');
      const tip = reason ? `${reason}: ${c.reason_ar || ''}` : (c.reason_ar || '');
      if (prev) m.set(k, prev + '\n' + tip);
      else m.set(k, tip);
    }
    return m;
  }, [unresolvedConflicts]);

  // ترتيب الأعمدة: لكل يوم تُضاف أعمدة الحصص (1..7) متتالية.
  const totalDataCols = days.length * periods.length;
  // أبعاد مدمجة لإحساس "data-dense": أعمدة الحصص ضيقة، عمود المعلم
  // أوسع لاحتواء الاسم + المادة + الحصة المسندة/الحصة الكلية.
  const TEACHER_COL_WIDTH = 220;
  const PERIOD_COL_WIDTH = 56;     // ≥ 48px كما يطلبه التصميم
  const DAY_HEADER_HEIGHT = 28;    // صف رأس الأيام
  const PERIOD_HEADER_HEIGHT = 24; // صف رأس أرقام الحصص
  const ROW_HEIGHT = 56;           // h-14 لكل صف بيانات
  const DAY_COLS_TOTAL_PX = totalDataCols * PERIOD_COL_WIDTH;

  // gridTemplateColumns: عمود المعلم + (يوم × حصص).
  const gridTemplate = `${TEACHER_COL_WIDTH}px repeat(${totalDataCols}, ${PERIOD_COL_WIDTH}px)`;

  // ظل أيسر خفيف لعمود المعلم المثبَّت (في RTL يقع على اليمين، فالظل يمتدّ
  // نحو اليسار داخل منطقة التمرير).
  const teacherStickyShadow = 'shadow-[-2px_0_5px_rgba(0,0,0,0.02)]';

  return (
    <div
      className="grid text-[11px]"
      style={{ gridTemplateColumns: gridTemplate, minWidth: TEACHER_COL_WIDTH + DAY_COLS_TOTAL_PX }}
    >
      {/* ── Sticky header row 1: day spans ─────────────────────── */}
      {/* الزاوية العلوية الجانبية (تقاطع رأس + عمود المعلم) — أعلى z-index */}
      <div
        className={`sticky top-0 bg-slate-50 text-slate-700 text-xs font-semibold flex items-center justify-center border-b border-l border-slate-200 ${teacherStickyShadow}`}
        style={{ insetInlineStart: 0, zIndex: 30, height: DAY_HEADER_HEIGHT }}
      >
        المعلم
      </div>
      {days.map((dayKey) => (
        <div
          key={`day-h-${dayKey}`}
          className="sticky top-0 z-20 bg-slate-50 text-slate-700 text-xs font-semibold text-center flex items-center justify-center border-b border-l border-slate-200"
          style={{ gridColumn: `span ${periods.length}`, height: DAY_HEADER_HEIGHT }}
        >
          {dayLabelMap[dayKey] || dayKey}
          {dayKey === today && (
            <span className="mr-2 inline-block px-1.5 py-0 text-[10px] rounded bg-slate-200 text-slate-700">
              اليوم
            </span>
          )}
        </div>
      ))}

      {/* ── Sticky header row 2: period numbers ────────────────── */}
      <div
        className={`sticky bg-slate-50 text-slate-500 text-[10px] font-medium px-2 flex items-center justify-end border-b border-l border-slate-200 ${teacherStickyShadow}`}
        style={{ top: DAY_HEADER_HEIGHT, insetInlineStart: 0, zIndex: 30, height: PERIOD_HEADER_HEIGHT }}
      >
        {teachers.length} معلم • {periods.length}×{days.length}
      </div>
      {days.map((dayKey) => (
        periods.map((p) => (
          <div
            key={`ph-${dayKey}-${p}`}
            className="sticky z-20 bg-slate-50 text-slate-700 text-center text-[11px] flex items-center justify-center border-b border-l border-slate-200"
            style={{ top: DAY_HEADER_HEIGHT, height: PERIOD_HEADER_HEIGHT }}
          >
            {p}
          </div>
        ))
      ))}

      {/* ── Body rows: one per teacher ─────────────────────────── */}
      {teachers.map((teacher) => {
        const teacherCells = cells[teacher.id] || {};
        const rowAbsentTint = teacher.is_absent_today;
        // الصبغة: صبغة حمراء خفيفة جداً للصف عند غياب المعلم، وإلا أبيض نقي.
        const rowBg = rowAbsentTint ? 'bg-red-50/40' : 'bg-white';
        const todayCells = (today && teacherCells[today]) || {};
        const vacantTodayCount = teacher.is_absent_today
          ? Object.values(todayCells).filter((c) => c && c.is_vacant).length
          : 0;
        return (
          <React.Fragment key={teacher.id}>
            {/* Sticky teacher column (الجانب الأيمن في RTL) */}
            <div
              className={`sticky z-10 px-3 py-2 border-b border-l border-slate-200 ${rowBg} ${teacherStickyShadow}`}
              style={{ insetInlineStart: 0, minHeight: ROW_HEIGHT }}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-slate-900 truncate flex items-center gap-1">
                    {teacher.full_name}
                    {teacher.is_absent_today && (
                      <AbsencePill
                        recorderName={teacher.absence_recorded_by_name}
                        recordedAt={teacher.absence_recorded_at}
                      />
                    )}
                  </p>
                  <p className="text-[10px] text-slate-500 truncate">
                    {teacher.subject || '—'}
                    {teacher.rank ? ` • ${RANK_AR[teacher.rank] || teacher.rank}` : ''}
                    {' • '}
                    <span className="font-semibold text-slate-600">
                      {teacher.assigned_periods}
                      <span className="text-slate-400">/</span>
                      {teacher.weekly_quota || '—'}
                    </span>
                  </p>
                </div>
              </div>
              {teacher.is_absent_today && (
                <div className="mt-1.5 flex flex-col gap-1">
                  <button
                    type="button"
                    onClick={() => onUndoAbsence?.(teacher)}
                    title="إعادة المعلم إلى حالة الحضور لهذا اليوم"
                    aria-label={`إلغاء غياب ${teacher.full_name}`}
                    className="inline-flex items-center gap-1 text-[10px] font-semibold rounded border border-emerald-400 text-emerald-700 bg-emerald-50 hover:bg-emerald-100 transition-colors px-1.5 py-0.5 cursor-pointer self-start"
                  >
                    <Undo2 className="h-3 w-3" aria-hidden="true" />
                    <span>إلغاء الغياب</span>
                  </button>
                  {vacantTodayCount > 0 && onBulkCoverClick && (
                    <Button
                      type="button"
                      size="sm"
                      onClick={() => onBulkCoverClick(teacher)}
                      className="w-full h-6 text-[10px] font-bold bg-gradient-to-r from-[#1C3D74] to-[#2BB5A0] hover:from-[#152d57] text-white shadow-sm px-2"
                      title="فتح لوحة تغطية كل الحصص الشاغرة لهذا المعلم اليوم"
                    >
                      <Layers className="h-3 w-3 ml-1" />
                      تغطية ({vacantTodayCount})
                    </Button>
                  )}
                </div>
              )}
            </div>

            {/* Cells: per day, per period */}
            {days.map((dayKey) => (
              periods.map((p) => {
                const cell = teacherCells[dayKey]?.[String(p)] || null;
                const cellData = {
                  teacher_id: teacher.id,
                  teacher_name: teacher.full_name,
                  day_of_week: dayKey,
                  period_number: p,
                  is_today: dayKey === today,
                  teacher_absent: teacher.is_absent_today,
                  session: cell,
                };
                // وسم خلية "تعارض حكيم": تظهر فقط على الخانات الفارغة التي
                // وردت في unresolved_conflicts ومرتبطة بنفس المعلم (الجلسات
                // المعبَّأة لا تحتاج تنبيه بصري). المفتاح يضم teacher_id كي
                // يقتصر التظليل على صفّ المعلم المتضرّر.
                const conflictKey = `${teacher.id}|${dayKey}|${p}`;
                const conflictTip = !cell ? conflictsByCell.get(conflictKey) : null;
                const conflictBg = conflictTip ? 'bg-orange-50 ring-1 ring-inset ring-orange-200' : rowBg;
                return (
                  <div
                    key={`${teacher.id}-${dayKey}-${p}`}
                    className={`min-w-[48px] h-14 border-b border-l border-slate-100 ${conflictBg}`}
                    title={conflictTip || undefined}
                  >
                    {cell ? (
                      <FilledCell
                        cell={cell}
                        onClick={cell.is_vacant ? () => onVacantClick(cellData) : undefined}
                      />
                    ) : (
                      <EmptyCell />
                    )}
                  </div>
                );
              })
            ))}
          </React.Fragment>
        );
      })}
    </div>
  );
}
