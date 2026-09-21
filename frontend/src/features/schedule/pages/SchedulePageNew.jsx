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

import React, { useEffect, useMemo, useState, useCallback, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Sidebar } from '@/shared/components/layout/Sidebar';
import { useAuth } from '@/shared/contexts/AuthContext';
import { useTheme, useTranslation } from '@/shared/contexts/ThemeContext';
import { toast } from 'sonner';

import { Card, CardContent } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { LoadingState } from '@/shared/components/ui/LoadingState';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '@/shared/components/ui/select';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from '@/shared/components/ui/tooltip';
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from '@/shared/components/ui/sheet';
import { Badge } from '@/shared/components/ui/badge';
import {
  Wand2, UserX, Sparkles, Loader2, RefreshCw,
  Scale, Hourglass, UserMinus, AlertOctagon, AlertTriangle,
  ShieldAlert, Settings, ArrowLeft,
  Undo2, Layers, Lightbulb, X, ExternalLink, CheckCircle2,
  PenLine, History, Unlock,
} from 'lucide-react';
import CandidatesSidePanel from '@/features/schedule/components/schedule/CandidatesSidePanel';
import BulkSubstitutionPanel from '@/features/schedule/components/schedule/BulkSubstitutionPanel';
import ScheduleTabNav from '@/features/schedule/components/schedule/ScheduleTabNav';
import ScheduleSettingsTabContent from '@/features/schedule/components/schedule/ScheduleSettingsTabContent';
import FilledCell from '@/features/schedule/components/schedule/FilledCell';
import MobileScheduleAgenda from '@/features/schedule/components/schedule/MobileScheduleAgenda';
import SessionEditDrawer from '@/features/schedule/components/schedule/SessionEditDrawer';
import { DndContext } from '@dnd-kit/core';
import { DraggableSession, DroppableSlot, useDragSensors } from '@/features/schedule/components/schedule/MasterMatrixDnd';
import { SessionDetailModal, getDayBandClass, getDayTintClass, getDayTextOnBand } from '@/features/schedule/components/schedule/grid-theme';
import { computeDisplayDays } from '@/features/schedule/components/schedule/grid-helpers';
import { StandbyRosterContent } from './StandbyRosterPage';
import { useNassaqAlert } from '@/shared/components/ui/NassaqAlertDialog';
import { getPose } from '@/features/hakim/components/hakim/hakimPoses';
import { MASTER_GRID_TEACHER_WINDOW } from '@/shared/models/config/scheduleConfig';

// Placeholder column count for the loading skeleton only — the real grid
// always derives its columns from the API payload (grid.periods).
const SKELETON_GRID_COLS = 7;

// ─── Infeasibility issue → contextual next step ────────────────────────────
// كل كود INF يحدد الصفحة الأنسب التي تحل المشكلة. عند غياب الكود نوجِّه إلى
// إعدادات المدرسة العامة كملاذ افتراضي.
const ISSUE_NEXT_STEP = {
  'INF-01': { labelKey: 'openAcademicSettings', path: '/principal/settings?section=academic' },
  'INF-02': { labelKey: 'openAcademicSettings', path: '/principal/settings?section=academic' },
  'INF-03': { labelKey: 'openTeachersAssignments',  path: '/principal/users-management?filter=teachers' },
  'INF-04': { labelKey: 'openRoomsSettings',           path: '/principal/schedule?tab=settings&sub=timings' },
  'INF-05': { labelKey: 'openSchoolDaySettings',     path: '/principal/schedule?tab=settings&sub=timings' },
};
const DEFAULT_NEXT_STEP = { labelKey: 'openScheduleSettings', path: '/principal/schedule?tab=settings' };

const DAYS = [
  { key: 'sunday' },
  { key: 'monday' },
  { key: 'tuesday' },
  { key: 'wednesday' },
  { key: 'thursday' },
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

// Tiny relative-time formatter localized via the t() helper (mirrors
// TeacherAttendancePage). Used by the absence tooltip so principals can see
// when a row was flipped.
function formatRelativeTime(iso, t, locale) {
  if (!iso) return '';
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return '';
  const diffSec = Math.round((Date.now() - then.getTime()) / 1000);
  if (diffSec < 5) return t('justNow');
  if (diffSec < 60) return t('secondsAgo', { count: diffSec });
  const mins = Math.round(diffSec / 60);
  if (mins < 60) return t('minutesAgo', { count: mins });
  const hours = Math.round(mins / 60);
  if (hours < 24) return t('hoursAgo', { count: hours });
  const days = Math.round(hours / 24);
  if (days < 7) return t('daysAgo', { count: days });
  return then.toLocaleDateString(locale === 'ar' ? 'ar-EG' : 'en-US');
}

// ─── Absence pill with recorder tooltip ───────────────────────────────────
// The pill itself is unchanged visually; hovering reveals "سجَّله: <name>"
// and the relative time. Falls back gracefully when the audit fields are
// absent (older absence rows that predate the recorder feature).
function AbsencePill({ recorderName, recordedAt }) {
  const { t, language } = useTranslation();
  const { direction } = useTheme();
  const pill = (
    <span
      tabIndex={0}
      className="text-[10px] font-semibold rounded border border-red-400 text-red-700 bg-red-100 px-1.5 py-0.5 cursor-help focus:outline-none focus:ring-1 focus:ring-red-400"
    >
      {t('absent')}
    </span>
  );

  const hasAudit = Boolean(recorderName) || Boolean(recordedAt);
  if (!hasAudit) return pill;

  const relTime = formatRelativeTime(recordedAt, t, language);
  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>{pill}</TooltipTrigger>
        <TooltipContent
          side="top"
          align="start"
          className="bg-slate-900 text-white text-[11px] leading-tight max-w-[220px]"
        >
          <div dir={direction} className="space-y-0.5">
            <div>
              <span className="font-semibold">{t('recordedByColon')}</span>{' '}
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
  // Condensed "pill" KPI (Task #142). The matrix is the dominant surface
  // of this page; KPIs sit in a thin horizontal strip rather than tall
  // dashboard cards. Keeps the colored accent so the operator can still
  // spot critical metrics at a glance, but reclaims ~60px of vertical
  // space for the grid below.
  return (
    <div className={`group relative overflow-hidden bg-white rounded-xl border border-slate-200/80 shadow-[0_1px_2px_rgba(15,42,75,0.04),0_1px_3px_rgba(15,42,75,0.05)] hover:shadow-[0_6px_16px_rgba(15,42,75,0.1)] hover:-translate-y-0.5 transition-all duration-200 flex items-center gap-3 px-4 py-3 min-w-0`}>
      <span aria-hidden="true" className={`absolute inset-y-0 start-0 w-1 ${accent.topBorder.replace('border-t-', 'bg-').replace('-400', '-500').replace('-500', '-500')}`} />
      <div className={`h-10 w-10 rounded-xl flex items-center justify-center shrink-0 ${accent.iconBg} ring-1 ring-inset ring-white/70`}>
        <Icon className={`h-5 w-5 ${accent.iconText}`} strokeWidth={1.5} aria-hidden="true" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500 leading-tight truncate">{label}</p>
        <div className="flex items-baseline gap-1 leading-none mt-1">
          <span className={`text-2xl font-bold tabular-nums tracking-tight ${accent.valueText}`}>{value}</span>
          {suffix && <span className="text-xs font-semibold text-slate-400 tabular-nums">{suffix}</span>}
        </div>
      </div>
    </div>
  );
}

// ─── Master matrix loading state ────────────────────────────────────────────
// المؤشر الموحّد للتحميل قبل وصول البيانات (LoadingState). يحافظ على ارتفاع
// يقارب ارتفاع المصفوفة الفعلية (بحسب عدد صفوف الصفحة ووضع العرض) حتى لا
// تقفز الواجهة عند وصول البيانات. يحتفظ بنفس معرف الاختبار ودور الحالة.
function MasterMatrixSkeleton({ rows = 10, isDaily = false }) {
  const { t } = useTranslation();
  const rowH = isDaily ? 96 : 88;
  const headerH = 36 + (isDaily ? 44 : 38);
  const minHeight = Math.min(headerH + rows * rowH, 640);

  return (
    <LoadingState
      variant="section"
      data-testid="master-matrix-skeleton"
      label={t('preparingMatrixAria')}
      className="animate-in fade-in-0 duration-200"
      style={{ minHeight }}
    />
  );
}

// ─── Cell renderers ────────────────────────────────────────────────────────
// Compact, "data-dense" cells: tiny text, subtle borders, no boxy borders
// inside cells — the matrix relies on the parent grid lines for separation.
// FilledCell نفسه استُخرج إلى ../components/schedule/FilledCell.jsx ليُختبر
// بمعزل عن بقية الصفحة (انظر __tests__/FilledCell.test.jsx). المنطق المضاف
// لاحقاً (Popover + زر "تم الاطلاع" مع onAcknowledgeRelocation) صار جزءاً
// من المكوّن المُستخرَج، وتمرّر الصفحة الـcallback إليه عبر MasterMatrix.

function EmptyCell({ onClick, addLabel }) {
  // فراغ في صف المعلم — لا تنبيه. حتى لو كان المعلم غائباً، الخلية الفارغة
  // تبقى فارغة وتكتفي بصبغة الصف الحمراء الخفيفة. الخانات التي يجب وسمها
  // "شاغرة" تُرَنْدَر عبر FilledCell.is_vacant = true.
  // Workspace-redesign visual: faint background tint + dotted hairline
  // at the bottom edge so the surface reads as structured, not as a
  // dead spreadsheet box. Stays quiet at 100-teacher density.
  // Manual-edit (draft only): if `onClick` is supplied, render the cell
  // as a button that opens the SessionEditDrawer in create mode. The
  // hover affordance is intentionally subtle so the empty grid still
  // reads as quiet at 100-teacher density.
  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        title={addLabel}
        aria-label={addLabel}
        className="w-full h-full bg-gradient-to-b from-slate-50/40 to-slate-100/30 hover:from-brand-turquoise/10 hover:to-brand-turquoise/5 hover:ring-1 hover:ring-inset hover:ring-brand-turquoise/40 transition-all duration-200 flex items-center justify-center text-slate-300 hover:text-brand-turquoise group rounded-md focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-turquoise focus-visible:ring-offset-1"
        data-testid="master-matrix-empty-cell-add"
      >
        <span className="opacity-0 group-hover:opacity-100 scale-75 group-hover:scale-100 text-lg leading-none transition-all duration-200 font-light">+</span>
      </button>
    );
  }
  return (
    <div className="w-full h-full bg-gradient-to-b from-slate-50/40 to-slate-100/30" />
  );
}

// ─── Hakeem-branded loading overlay ─────────────────────────────────────────
// يُعرض فوق المصفوفة أثناء توليد الجدول التلقائي. يستخدم تعبير "ai-thinking"
// من معرض حكيم مع ضباب أبيض شفّاف ونبضة بنفسجية لتأكيد أن المحرك يعمل.
// Five real engine phases the smart-scheduling pipeline goes through, in
// order. Each phase carries its own Hakim pose so the operator gets a
// continuously-updating signal that the engine is actually working
// instead of one boolean spinner that hides whether anything is happening.
// `minMs` is a soft lower bound — the UI advances on whichever comes
// first: minMs elapsed OR the request finishing. The final stage holds
// until the request returns so the overlay never lies about "done".
const HAKIM_STAGES = [
  { key: 'queued',          poseKey: 'ai-thinking',         labelKey: 'hakimStageQueued',          minMs: 600 },
  { key: 'reading',         poseKey: 'analyzing-data',      labelKey: 'hakimStageReadingSettings', minMs: 1500 },
  { key: 'analyzing',       poseKey: 'detecting-patterns',  labelKey: 'hakimStageAnalyzing',       minMs: 2200 },
  { key: 'building',        poseKey: 'ai-thinking-2',       labelKey: 'hakimStageBuilding',        minMs: 3000 },
  { key: 'validating',      poseKey: 'looking-at-charts',   labelKey: 'hakimStageValidating',      minMs: 2200 },
  { key: 'finalizing',      poseKey: 'positive-feedback',   labelKey: 'hakimStageFinalizing',      minMs: 0 },
];

// ─── Hakeem-branded loading overlay (multi-stage) ──────────────────────────
// Replaces the previous single-message overlay. Cycles through the five
// engine phases above with a smooth progress bar so the operator can
// see exactly what the pipeline is doing. Stays on the final stage if
// the request is still in-flight when the timer reaches the end. No
// full-page spinner — the overlay is positioned absolutely inside the
// matrix container so the rest of the page (KPIs, sticky band) stays
// interactive and visible.
// Generation now runs as a background job on the server, so the overlay no
// longer has to guess: `serverProgress` is the real completion_percentage the
// engine writes to its run row, delivered by polling. The timer below is kept
// only as a floor for the window before the first poll comes back, and the bar
// never moves backwards.
function serverPctToStageIdx(pct) {
  if (pct == null) return null;
  if (pct < 10) return 0;   // queued / validating
  if (pct < 55) return 2;   // loading + analyzing demand
  if (pct < 70) return 3;   // building the draft (the long phase)
  if (pct < 90) return 4;   // conflict detection
  return 5;                 // optimizing / writing
}

function HakimGeneratingOverlay({ serverProgress = null }) {
  const { t } = useTranslation();
  const [stageIdx, setStageIdx] = useState(0);

  useEffect(() => {
    if (stageIdx >= HAKIM_STAGES.length - 1) return;
    const ms = HAKIM_STAGES[stageIdx].minMs;
    const id = setTimeout(() => setStageIdx((i) => Math.min(i + 1, HAKIM_STAGES.length - 1)), ms);
    return () => clearTimeout(id);
  }, [stageIdx]);

  const serverStageIdx = serverPctToStageIdx(serverProgress);
  // Take whichever signal is further along: the server is authoritative once
  // it reports, but before the first poll the timer is all we have.
  const effectiveIdx = serverStageIdx == null
    ? stageIdx
    : Math.max(stageIdx, serverStageIdx);

  const stage = HAKIM_STAGES[Math.min(effectiveIdx, HAKIM_STAGES.length - 1)];
  const poseSrc = getPose(stage.poseKey);
  const total = HAKIM_STAGES.length;
  const timerPct = Math.round(((stageIdx + 1) / total) * 100);
  const progressPct = serverProgress == null
    ? timerPct
    : Math.max(timerPct, Math.min(100, Math.round(serverProgress)));

  return (
    <div
      className="absolute inset-0 z-40 flex items-center justify-center bg-white/85 backdrop-blur-[2px]"
      data-testid="hakim-generating-overlay"
      role="status"
      aria-live="polite"
    >
      <div className="flex flex-col items-center gap-3 px-6 py-5 rounded-xl bg-white border border-violet-200 shadow-lg w-[320px] max-w-[90vw]">
        <div className="relative">
          <div className="absolute inset-0 rounded-full bg-violet-300/40 animate-ping" />
          <img
            key={stage.key}
            src={poseSrc}
            alt={t('hakimAI')}
            className="relative h-20 w-20 object-contain"
            draggable={false}
          />
        </div>

        <div className="flex items-center gap-2 text-violet-700 min-h-[20px]">
          <Loader2 className="h-4 w-4 animate-spin shrink-0" />
          <span
            className="text-sm font-semibold text-center"
            data-testid={`hakim-stage-${stage.key}`}
          >
            {t(stage.labelKey)}
          </span>
        </div>

        {/* Progress bar — shows discrete stage advancement, not a fake
            percent counter, so the operator can see the engine moving
            forward and roughly how far we are. */}
        <div className="w-full">
          <div className="h-1.5 w-full bg-violet-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-violet-400 to-violet-600 transition-all duration-500 ease-out"
              style={{ width: `${progressPct}%` }}
            />
          </div>
          <p className="mt-1 text-[10px] text-slate-500 text-center">
            {t('hakimStagesProgressLabel', { current: stageIdx + 1, total })}
          </p>
        </div>

        <p className="text-[11px] text-slate-500 max-w-[260px] text-center leading-relaxed">
          {t('hakimGenerationDuration')}
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
// `/principal/schedule?tab=settings&sub=<tab>` الذي تُحسن الصفحة قراءته.

const SETTINGS_TAB_LABEL_KEY = {
  'timings': 'settingsTabTimings',
  'classes': 'settingsTabClasses',
  'teacher-assignments': 'settingsTabTeacherAssignments',
  'unavailability': 'settingsTabUnavailability',
  'constraints': 'settingsTabConstraints',
};
const VALID_SETTINGS_TABS = Object.keys(SETTINGS_TAB_LABEL_KEY);
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

function HakimInsightsBanner({ conflicts, dismissed, onDismiss, onOpenDrawer }) {
  const { t } = useTranslation();
  if (!conflicts || conflicts.length === 0 || dismissed) return null;
  const total = conflicts.length;
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg border border-orange-200 bg-orange-50 text-orange-900 shrink-0">
      <Lightbulb className="h-5 w-5 shrink-0 text-orange-500" />
      <p className="flex-1 min-w-0 text-sm font-bold truncate text-start">
        {t('hakimInsightsBannerTitle', { count: total })}
      </p>
      <Button
        type="button"
        size="sm"
        variant="outline"
        onClick={onOpenDrawer}
        className="shrink-0 border-orange-300 text-orange-800 hover:bg-orange-100 hover:text-orange-800 focus-visible:text-orange-800 bg-white/70"
        data-testid="open-hakim-insights-drawer"
      >
        <Lightbulb className="h-3.5 w-3.5 me-1" />
        {t('viewDetails')}
      </Button>
      <button
        type="button"
        onClick={onDismiss}
        title={t('hideBanner')}
        aria-label={t('hideHakimInsightsBanner')}
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
  const { t, language } = useTranslation();
  const { direction } = useTheme();
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
    const day = t(item.day_of_week);
    return `${day} • ${t('periodN', { n: item.period_number })}`;
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side={direction === 'rtl' ? 'left' : 'right'}
        dir={direction}
        className="w-full sm:max-w-lg p-0 flex flex-col gap-0"
        data-testid="hakim-insights-drawer"
      >
        <SheetHeader className="p-5 bg-gradient-to-l from-orange-100 to-amber-50 border-b border-orange-200 text-start">
          <SheetTitle className="flex items-center gap-2 text-orange-900">
            <Lightbulb className="h-5 w-5 text-orange-500" />
            {t('hakimInsightsDrawerTitle')}
          </SheetTitle>
          <SheetDescription className="text-orange-800/90 text-xs leading-relaxed">
            {total > 0
              ? t('hakimInsightsDrawerDesc', { count: total })
              : t('noUnscheduledItems')}
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
                ? <Loader2 className="h-3.5 w-3.5 me-1 animate-spin" />
                : <RefreshCw className="h-3.5 w-3.5 me-1" />}
              {retrying ? t('regenerating') : t('retry')}
            </Button>
          </div>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-50">
          {total === 0 ? (
            <p className="text-sm text-slate-500 text-center py-10">
              {t('noDataToShow')}
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
                          {t('countItems', { count: rows.length })}
                        </Badge>
                      </div>
                      <ul className="space-y-2">
                        {rows.map((c, i) => {
                          const tab = resolveSettingsTab(c);
                          const tabLabel = t(SETTINGS_TAB_LABEL_KEY[tab] || 'settings');
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
                                    {(language === 'en' ? (c.reason_en || c.reason_ar) : c.reason_ar) || t('failedToScheduleDefault')}
                                  </p>
                                </div>
                                <Button
                                  type="button"
                                  size="sm"
                                  variant="outline"
                                  onClick={() => onNavigate(tab)}
                                  className="shrink-0 border-[#1C3D74]/30 text-[#1C3D74] hover:bg-[#1C3D74]/5 text-[11px] h-7"
                                  data-testid={`hakim-insights-open-${tab}`}
                                >
                                  <ExternalLink className="h-3 w-3 me-1" />
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

// Named exports for test harnesses (Task #142). Keeps the page's default
// export untouched while letting the new MasterMatrix/skeleton tests
// exercise the components in isolation without rendering the whole page.
export { MasterMatrix, MasterMatrixSkeleton };

export default function SchedulePageNew() {
  const { user, api } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const schoolId = user?.tenant_id;
  // تكليف التغطية متاح لقيادة المدرسة ومشرف المنصة فقط؛ الخادم يفرض الدور
  // أيضاً عبر require_standby_roster_role.
  const coverageEnabled = ['school_principal', 'school_admin', 'platform_admin']
    .includes(user?.role);
  const tab = useScheduleTab();
  const { nassaqError, nassaqWarning, nassaqConfirm } = useNassaqAlert();
  const { t } = useTranslation();
  const { direction } = useTheme();

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
  // نسبة الإنجاز الحقيقية القادمة من الخادم (0-100) أثناء تنفيذ مهمة التوليد،
  // أو null قبل وصول أول استعلام.
  const [generationProgress, setGenerationProgress] = useState(null);
  // يُستخدم لإيقاف الاستعلام الدوري عند مغادرة الصفحة، حتى لا يستمر بعد
  // إلغاء تركيب المكوّن (تحديث حالة على مكوّن مفكوك + طلبات بلا فائدة).
  const pollCancelledRef = useRef(false);
  useEffect(() => () => { pollCancelledRef.current = true; }, []);

  // ── Manual edit drawer (master grid) ──────────────────────────────
  // The drawer covers three flows:
  //   • clicking a filled cell → "Edit" / "Move" (mode = 'edit')
  //   • clicking an empty cell while in draft view → "Add" (mode = 'create')
  //   • the inline Delete button on the edit drawer (DELETE endpoint)
  // Editing is gated to draft view only — the affordance disappears
  // entirely on the published view (and the backend additionally
  // refuses mutations on a published timetable).
  const [editDrawerOpen, setEditDrawerOpen] = useState(false);
  const [editDrawerMode, setEditDrawerMode] = useState('edit');
  const [editDrawerContext, setEditDrawerContext] = useState(null);

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

  // Task #141 — draft/published view toggle. Persisted to
  // localStorage so the school admin lands on the same view between
  // visits. Default is 'published' so non-admins (and admins on a
  // freshly-loaded page) see what teachers/students are actually
  // looking at right now. After a successful auto-generate we flip
  // automatically to 'draft' so the freshly-generated variant is
  // visible immediately for review.
  const [scheduleView, setScheduleView] = useState(() => {
    try {
      const v = localStorage.getItem('nassaq.schedule.view');
      return v === 'draft' ? 'draft' : 'published';
    } catch { return 'published'; }
  });
  useEffect(() => {
    try { localStorage.setItem('nassaq.schedule.view', scheduleView); } catch {}
  }, [scheduleView]);
  const [publishing, setPublishing] = useState(false);

  // ── Manual timetable create dialog ────────────────────────────────
  const [manualCreateOpen, setManualCreateOpen] = useState(false);
  const [manualCreateName, setManualCreateName] = useState('');
  const [manualCreating, setManualCreating] = useState(false);

  // ── Timetable versions panel ───────────────────────────────────────
  const [versionsOpen, setVersionsOpen] = useState(false);
  const [versionsData, setVersionsData] = useState([]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [unpublishing, setUnpublishing] = useState(false);

  // ── Sticky band density + height tracking (workspace redesign) ────
  // The sticky action band exposes its measured height to the matrix
  // header offsets via the `--sticky-band-h` CSS custom property on
  // the page root. A second ResizeObserver on the band's own width
  // toggles `data-density` to prevent wrapping at 1024–1279 px.
  const stickyBandRef = useRef(null);
  useEffect(() => {
    const band = stickyBandRef.current;
    if (!band) return;
    const root = band.closest('[data-master-schedule-root]');
    if (!root) return;
    const updateHeight = () => {
      const h = band.getBoundingClientRect().height || 72;
      root.style.setProperty('--sticky-band-h', `${Math.round(h)}px`);
    };
    const updateDensity = () => {
      const w = band.getBoundingClientRect().width || 1280;
      let density = 'default';
      if (w < 1024) density = 'dense';
      else if (w < 1280) density = 'compact';
      band.setAttribute('data-density', density);
    };
    const ro = new ResizeObserver(() => {
      updateHeight();
      updateDensity();
    });
    ro.observe(band);
    updateHeight();
    updateDensity();
    return () => ro.disconnect();
    // ``tab`` is in deps so when the user lands on a non-master tab
    // first (e.g. `?tab=standby`) and switches to master, the effect
    // re-runs and finds the freshly-mounted band element. Without
    // this, the band stays unmeasured and sticky offsets fall back
    // to the 88px hint, which can overlap the matrix headers when
    // the band wraps at narrower widths.
  }, [tab]);

  // ── Weekly matrix horizontal-overflow discoverability ──────────────
  // Toggles `data-can-scroll-end` and `data-can-scroll-start` on the
  // matrix container so the inline-end / inline-start edge fades
  // (defined in the JSX below) appear only when overflow exists in
  // that direction. RTL-correct: in RTL, scrollLeft is negative or
  // mirrored depending on browser; using Math.abs(scrollLeft) and
  // comparing against scrollWidth - clientWidth covers both.
  const matrixContainerRef = useRef(null);
  useEffect(() => {
    const el = matrixContainerRef.current;
    if (!el) return;
    const update = () => {
      const max = el.scrollWidth - el.clientWidth;
      const pos = Math.abs(el.scrollLeft);
      const region = el.parentElement;
      if (!region) return;
      const canStart = pos > 1;
      const canEnd = pos < max - 1;
      el.setAttribute('data-can-scroll-start', canStart ? 'true' : 'false');
      el.setAttribute('data-can-scroll-end', canEnd ? 'true' : 'false');
      region.style.setProperty('--scroll-fade-start-opacity', canStart ? '1' : '0');
      region.style.setProperty('--scroll-fade-end-opacity', canEnd ? '1' : '0');
      const dir = document.documentElement.dir === 'rtl' ? 'rtl' : 'ltr';
      region.style.setProperty('--scroll-fade-end-dir', dir === 'rtl' ? 'right' : 'left');
      region.style.setProperty('--scroll-fade-start-dir', dir === 'rtl' ? 'left' : 'right');
    };
    update();
    el.addEventListener('scroll', update, { passive: true });
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => {
      el.removeEventListener('scroll', update);
      ro.disconnect();
    };
    // NOTE: viewMode/grid are intentionally excluded from deps to avoid
    // a temporal-dead-zone ReferenceError (those identifiers are declared
    // further down the component body). The ResizeObserver above already
    // re-fires `update()` whenever the container's box changes due to a
    // viewMode switch or grid reload, so we don't need explicit deps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadGrid = useCallback(async (viewOverride, paginationOverride, options = {}) => {
    // Returns the payload itself on success (not just a boolean) so callers
    // can compare against an expected timetable id after generation without
    // depending on React state inside the same closure. ``viewOverride``
    // lets handleAutoGenerate force-fetch the draft right after generation.
    // ``paginationOverride`` lets callers bypass the closure's stale
    // state and request the right window in a single round-trip — Task
    // #142 backend payload scoping (teacher window + day in daily mode).
    if (!schoolId) return null;
    const effectiveView = viewOverride || scheduleView;
    const effectivePage = paginationOverride?.page ?? (paginationStateRef.current.pageIndex + 1);
    const effectivePageSize = paginationOverride?.pageSize ?? paginationStateRef.current.pageSize;
    const isSilent = options?.silent ?? false;

    // Capture current scroll positions so mutations / silent refetches maintain exact scroll offset
    const prevScrollTop = matrixContainerRef.current?.scrollTop;
    const prevScrollLeft = matrixContainerRef.current?.scrollLeft;

    if (!isSilent) {
      setLoading(true);
    } else {
      setRefreshing(true);
    }
    try {
      // ``_t`` busts any stale browser/proxy cache (the backend already
      // sets Cache-Control: no-store but some intermediaries ignore it).
      // teacher_page / teacher_page_size + day opt into the visible-
      // window contract — the backend slices teachers, sessions, and
      // (in daily mode) day so the wire payload scales with what's
      // actually rendered.
      const params = {
        school_id: schoolId,
        view: effectiveView,
        teacher_page: effectivePage,
        teacher_page_size: effectivePageSize,
        _t: Date.now(),
      };
      const dayParam = paginationOverride?.day ?? paginationStateRef.current.day;
      if (dayParam) params.day = dayParam;
      const doGet = () => api.get('/schedule/master-grid', {
        params,
        headers: {
          'X-School-Context': schoolId,
          'Cache-Control': 'no-cache',
          'Pragma': 'no-cache',
        },
      });
      let response = await doGet();
      // قاعدة المنتج: «المسودة» نسخةُ عملٍ قابلة للتعديل من آخر جدول منشور.
      // بعد النشر لا يبقى صفُّ مسودة فتعود شبكة المسودة فارغة — نطلب من
      // الخادم تهيئة مسودة (بنسخ الجدول المنشور) مرّة واحدة ثم نعيد الجلب.
      // ننفّذ ذلك لعرض المسودة فقط وعندما تكون الشبكة فارغة فعلاً، فلا
      // يتكرر بعد إنشاء المسودة (تصبح غير فارغة) ولا يحدث تكرار لا نهائي.
      // يغطّي هذا العرضين اليومي والأسبوعي وإعادة التحميل لأنهما يمرّان
      // عبر ``loadGrid`` نفسها.
      if (effectiveView === 'draft' && response?.data?.is_empty === true) {
        try {
          const ensured = await api.post(
            '/schedule/draft/ensure',
            { school_id: schoolId },
            { headers: { 'X-School-Context': schoolId } },
          );
          if (ensured?.data?.timetable_id) {
            response = await doGet();
          }
        } catch (ensureErr) {
          // غير حرج: نُبقي حالة الشبكة الفارغة إن تعذّرت التهيئة.
        }
      }
      setGrid(response.data);
      setError('');

      if (prevScrollTop != null || prevScrollLeft != null) {
        requestAnimationFrame(() => {
          if (matrixContainerRef.current) {
            if (prevScrollTop != null && prevScrollTop > 0) {
              matrixContainerRef.current.scrollTop = prevScrollTop;
            }
            if (prevScrollLeft != null && prevScrollLeft > 0) {
              matrixContainerRef.current.scrollLeft = prevScrollLeft;
            }
          }
        });
      }

      return response.data;
    } catch (e) {
      const msg = e?.response?.data?.error?.message || e?.message || t('failedToLoadGrid');
      setError(msg);
      return null;
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [api, schoolId, scheduleView, t]);
  // ``loadGrid`` deliberately depends on ``scheduleView`` so that
  // toggling the view via the header tabs triggers an automatic
  // refetch through the existing useEffect → loadGrid wiring.

  useEffect(() => {
    // نُحمِّل مصفوفة الجدول الرئيسي فقط عندما يكون التبويب النشط هو
    // "الجدول الرئيسي" — تبويبا الانتظار والإعدادات لهما تحميل بياناتهما
    // الخاص داخل مكوّناتهما.
    if (tab !== 'master') return;
    loadGrid();
  }, [loadGrid, tab]);

  // استعلام دوري عن حالة مهمة التوليد حتى تنتهي.
  //
  // الفاصل ثانيتان: أسرع من ذلك يُغرق الخادم بلا فائدة (المرحلة الطويلة هي
  // بناء المسودة وتستغرق ثوانيَ عدّة)، وأبطأ منه يجعل شريط التقدّم يبدو
  // متجمّداً. السقف عشر دقائق يطابق مهلة اعتبار المهمة متوقّفة في الخادم،
  // فلا ننتظر إلى الأبد لو اختفى العامل المنفّذ.
  const pollGenerationJob = useCallback(async (jobId) => {
    const INTERVAL_MS = 2000;
    const MAX_WAIT_MS = 10 * 60 * 1000;
    const deadline = Date.now() + MAX_WAIT_MS;
    pollCancelledRef.current = false;

    // أخطاء الشبكة العابرة أثناء الاستعلام لا تعني فشل التوليد — المهمة
    // تعمل على الخادم. نتسامح مع عدّة إخفاقات متتالية قبل الاستسلام.
    let consecutiveErrors = 0;
    const MAX_CONSECUTIVE_ERRORS = 5;

    while (Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, INTERVAL_MS));
      if (pollCancelledRef.current) return { cancelled: true };

      let status;
      try {
        const res = await api.get(`/smart-scheduling/job/${jobId}`, {
          headers: { 'X-School-Context': schoolId },
        });
        status = res.data || {};
        consecutiveErrors = 0;
      } catch (e) {
        // 404/403 نهائيان — لا فائدة من إعادة المحاولة.
        const code = e?.response?.status;
        if (code === 404 || code === 403 || code === 401) throw e;
        consecutiveErrors += 1;
        if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) throw e;
        continue;
      }

      if (typeof status.progress === 'number') setGenerationProgress(status.progress);
      if (status.is_done) return status;
    }
    return { is_done: false, timed_out: true, message_ar: t('generationFailedDefault') };
  }, [api, schoolId, t]);

  const handleAutoGenerate = useCallback(async () => {
    if (!schoolId) {
      nassaqError(t('cannotDetermineSchool'));
      return;
    }
    if (generating) return;

    setGenerating(true);
    setGenerationProgress(null);
    setInsightsDismissed(false);
    setUnresolvedConflicts([]);

    try {
      // ──────────────────────────────────────────────────────────────────
      // التوليد يعمل الآن كمهمة خلفية على الخادم: نطلب بدء المهمة فنستلم
      // معرّفها فوراً، ثم نستعلم عن حالتها دورياً. السبب: التوليد يستغرق
      // من ثانية إلى ~27 ثانية حسب حجم المدرسة، وهي مدّة تكفي لأن يقطعها
      // الوسيط أو المتصفّح فيبدو الأمر فشلاً بينما الجدول قد أُنشئ فعلاً.
      // كما أن هذا يحرّر المدير من انتظار الصفحة.
      // ──────────────────────────────────────────────────────────────────
      const startRes = await api.post(
        `/smart-scheduling/generate/${schoolId}/job`,
        {},
        { headers: { 'X-School-Context': schoolId } },
      );
      const jobId = startRes.data?.job_id;
      if (!jobId) throw new Error('missing job id');

      const job = await pollGenerationJob(jobId);
      if (job.cancelled) return;
      if (!job.result) {
        // انتهت المهمة دون نتيجة قابلة للعرض (فشل أو توقّف).
        nassaqError(
          job.message_ar || t('generationFailedDefault'),
          { title: t('failedToGenerateScheduleTitle') },
        );
        return;
      }

      const data = job.result;
      const scheduled = data.scheduled_sessions ?? 0;
      const total = data.total_sessions ?? 0;
      const conflicts = data.conflicts_count ?? 0;
      const unscheduled = data.unscheduled_count ?? 0;
      const pct = Math.round(data.completion_percentage ?? 0);
      const summary =
        t('generationSummaryToast', { scheduled, total, pct }) +
        (conflicts ? t('generationConflictsSuffix', { n: conflicts }) : '') +
        (unscheduled ? t('generationUnscheduledSuffix', { n: unscheduled }) : '');

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
      // Task #141 — generation only writes DRAFT. Force-switch the
      // view to 'draft' so the new variant is visible immediately for
      // review/publish, regardless of what the admin had selected
      // before. We pass the explicit view to ``loadGrid`` because
      // ``setScheduleView`` is async and the very next render hasn't
      // happened yet — relying on the closure here would refetch the
      // stale (published) view and then race the eventual draft load.
      setScheduleView('draft');
      const expectedId = data.timetable_id || null;
      let fetched = await loadGrid('draft');
      // الجلب يُعتبر "بائتاً" لو وُجد expectedId ولم يطابق ما رجع من
      // الخادم — بما في ذلك حالة فشل المحاولة الثانية بعد عدم التطابق
      // الأول (نحتفظ بإشارة "بائت" بدلاً من الخلط بينها وبين فشل الشبكة).
      let staleAfterRetry = false;
      if (fetched && expectedId && fetched.timetable_id !== expectedId) {
        await new Promise((r) => setTimeout(r, 400));
        const retry = await loadGrid('draft');
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
        toast.success(data.message_ar || t('generatedSuccess'), {
          description: summary,
        });
      } else {
        // اكتمل التشغيل مع ملاحظات — نرفعها كحوار رؤى حكيم بدلاً من تنبيه toast
        // عابر، حتى لا تضيع المعلومة المهمّة على المدير. هذه المعلومات
        // مستقلّة عن نجاح/فشل إعادة الجلب.
        nassaqWarning(
          (data.message_ar || t('generatedPartialNotice')) + '\n\n' + summary,
          { title: t('hakimPartialTitle') },
        );
      }
      if (!fetched || staleAfterRetry) {
        // توليد (كامل أو جزئي) نجح في الكتابة لقاعدة البيانات لكن العرض
        // قديم — إمّا لأن جلب المصفوفة فشل شبكياً، وإمّا لأن المحاولة
        // الثانية بعد عدم تطابق المعرّف لم تُرجع الجدول الجديد. في كلتا
        // الحالتين نعرض خطأ صريح بالعبارة المحدَّدة في خطّة المهمة كي لا
        // يُترك المدير أمام شاشة قديمة دون تنبيه.
        nassaqError(
          t('failedToLoadUpdatedGrid'),
          { title: t('failedToRefreshMatrix') },
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

      let msg = t('generationFailedDefault');
      if (typeof detail === 'string' && /[\u0600-\u06FF]/.test(detail)) {
        msg = detail;
      } else if (detail?.code === 'GENERATION_BLOCKED') {
        // Fallback: server returned the code but no report payload.
        msg = t('dataNotReadyForEngine');
      } else if (e?.response?.data?.message_ar) {
        msg = e.response.data.message_ar;
      } else if (status === 401 || status === 403) {
        msg = t('noPermissionAutoGenerate');
      } else if (status === 404) {
        msg = t('schoolDataNotFound');
      } else if (e?.code === 'ERR_NETWORK' || !e?.response) {
        msg = t('networkErrorRetry');
      }
      nassaqError(msg, { title: t('failedToGenerateScheduleTitle') });
    } finally {
      setGenerating(false);
      setGenerationProgress(null);
    }
  }, [api, schoolId, generating, loadGrid, nassaqError, nassaqWarning, t, pollGenerationJob]);

  const handleLogAbsence = useCallback(() => {
    setAbsenceTeacherId('');
    setAbsenceNotes('');
    setAbsenceOpen(true);
  }, []);

  const handleSubmitAbsence = useCallback(async () => {
    if (!absenceTeacherId) {
      toast.error(t('pleaseSelectTeacher'));
      return;
    }
    if (!schoolId) {
      toast.error(t('cannotDetermineSchool'));
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
      toast.success(t('absenceLogged'));
      setAbsenceOpen(false);
      setAbsenceTeacherId('');
      setAbsenceNotes('');
      setRefreshing(true);
      await loadGrid();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const status = e?.response?.status;
      let msg = t('absenceLogFailed');
      if (typeof detail === 'string' && /[\u0600-\u06FF]/.test(detail)) {
        msg = detail;
      } else if (e?.response?.data?.message_ar) {
        msg = e.response.data.message_ar;
      } else if (status === 401 || status === 403) {
        msg = t('noPermissionLogAbsence');
      } else if (e?.code === 'ERR_NETWORK' || !e?.response) {
        msg = t('networkErrorRetry');
      }
      toast.error(msg);
    } finally {
      setSavingAbsence(false);
    }
  }, [api, schoolId, absenceTeacherId, absenceNotes, loadGrid, t]);

  const handleRequestUndoAbsence = useCallback((teacher) => {
    if (!teacher?.id) return;
    setUndoTeacher({ id: teacher.id, full_name: teacher.full_name || '' });
  }, []);

  // Acknowledge a relocation overlay straight from a master-grid cell. We
  // hit the same school-settings ack endpoint the notifications page uses,
  // then refresh the grid so the cell flips to "تم الاطلاع" without forcing
  // the teacher to navigate to /notifications. The unread badge in the
  // sidebar listens to a window event so we nudge it here too.
  const handleAcknowledgeRelocation = useCallback(async (cell) => {
    if (!cell?.unavailability_id) return;
    if (!schoolId) {
      toast.error(t('cannotDetermineSchool'));
      return;
    }
    try {
      await api.post(
        `/school/settings/unavailability/${cell.unavailability_id}/acknowledge`,
        {},
        { headers: { 'X-School-Context': schoolId } },
      );
      toast.success(t('relocationAckSuccess'));
      // Bump the bell so its unread badge re-syncs.
      window.dispatchEvent(new CustomEvent('notifications:refresh'));
      await loadGrid();
    } catch (e) {
      const status = e?.response?.status;
      const detail = e?.response?.data?.detail;
      if (status === 403) {
        nassaqError(detail || t('notForYouNote'));
      } else {
        nassaqError(detail || t('relocationAckFailed'));
      }
    }
  }, [api, schoolId, loadGrid, nassaqError, t]);

  // ── Drag-and-drop handler (draft master grid) ─────────────────────
  // The page is the source of truth for grid mutations: it picks the
  // correct backend endpoint based on whether the drop target is empty
  // (move) or filled (swap), then refreshes the draft so the matrix
  // reflects the authoritative server state. The backend remains the
  // primary security boundary — it enforces tenant isolation, draft-only
  // mutability, and full conflict detection. We never apply optimistic
  // mutations here because rollback would have to undo a swap across two
  // cells, which is brittle; pessimistic + fast reconcile is the cleaner
  // contract.
  const handleSessionDragMove = useCallback(async ({
    sessionId,
    targetDay,
    targetPeriod,
    targetSessionId,
  }) => {
    if (!sessionId || !schoolId || !targetDay || !targetPeriod) return;
    try {
      if (targetSessionId) {
        // Filled target → swap the two sessions atomically.
        await api.post(
          '/smart-scheduling/sessions/swap',
          { session_id_1: sessionId, session_id_2: targetSessionId },
          { headers: { 'X-School-Context': schoolId } },
        );
        toast.success(t('sessionSwapSuccess'));
      } else {
        // Empty target → move the source session into it.
        await api.post(
          '/smart-scheduling/sessions/move',
          { session_id: sessionId, new_day: targetDay, new_period: targetPeriod },
          { headers: { 'X-School-Context': schoolId } },
        );
        toast.success(t('sessionMoveSuccess'));
      }
      await loadGrid('draft');
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const msg = (typeof detail === 'string' && detail)
        || detail?.message_ar
        || e?.response?.data?.message_ar
        || t('sessionMoveFailed');
      // Conflict / authorization errors get the branded NassaqAlertDialog
      // — never a native browser alert or a bare toast.error per the
      // platform UI contract in replit.md.
      nassaqError(msg, { title: t('sessionMoveFailedTitle') });
      // The grid is the source of truth — re-fetch so the dragged tile
      // visually reverts to its original cell on the next render.
      await loadGrid('draft');
    }
  }, [api, schoolId, loadGrid, nassaqError, t]);

  const handleConfirmUndoAbsence = useCallback(async () => {
    if (!undoTeacher?.id) return;
    if (!schoolId) {
      toast.error(t('cannotDetermineSchool'));
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
      toast.success(t('absenceUndone'));
      setUndoTeacher(null);
      setRefreshing(true);
      await loadGrid();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const status = e?.response?.status;
      let msg = t('undoAbsenceFailed');
      if (typeof detail === 'string' && /[\u0600-\u06FF]/.test(detail)) {
        msg = detail;
      } else if (e?.response?.data?.message_ar) {
        msg = e.response.data.message_ar;
      } else if (status === 401 || status === 403) {
        msg = t('noPermissionUndoAbsence');
      } else if (e?.code === 'ERR_NETWORK' || !e?.response) {
        msg = t('networkErrorRetry');
      }
      toast.error(msg);
    } finally {
      setUndoingAbsence(false);
    }
  }, [api, schoolId, undoTeacher, loadGrid, t]);

  const handleVacantClick = useCallback((cellData) => {
    if (!cellData?.session?.session_id) {
      toast.error(t('vacantSlotNotLinked'));
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
      // معرف المعلم الغائب (إلى جانب الاسم) ليتمكّن درج الانتظار من
      // استبعاده من قائمة المرشحين وربط الإسناد بسجل الغياب الصحيح.
      absent_teacher_id: cellData.teacher_id,
      absent_teacher_name: cellData.teacher_name,
      absence_date: cellData.day_of_week === today ? todayDate : todayDate,
      school_id: schoolId,
    });
    setDrawerOpen(true);
  }, [grid?.today, schoolId, t]);

  const handleUndoSubstitution = useCallback(async (substitutionId) => {
    try {
      await api.delete(`/substitutions/${substitutionId}`, {
        params: { school_id: schoolId },
        headers: { 'X-School-Context': schoolId },
      });
      await loadGrid();
      toast.success(t('substitutionUndone'));
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || t('undoFailed');
      toast.error(msg);
    }
  }, [api, schoolId, loadGrid, t]);

  const handleAssigned = useCallback((substitution, cand) => {
    // Optimistic refresh + undo toast
    loadGrid();
    const subId = substitution?.id;
    toast.success(t('substitutionAssignedNotified'), {
      description: t('substituteWithName', { name: cand?.teacher_name || '—' }),
      duration: 10000,
      action: subId
        ? { label: t('undoBtn'), onClick: () => handleUndoSubstitution(subId) }
        : undefined,
    });
  }, [loadGrid, handleUndoSubstitution, t]);

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
      toast.success(t('batchUndone'));
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || t('batchUndoFailed');
      toast.error(msg);
    }
  }, [api, schoolId, loadGrid, t]);

  const handleAssignedBatch = useCallback((batchResult) => {
    loadGrid();
    const succeeded = batchResult?.succeeded || 0;
    const failed = batchResult?.failed || 0;
    const batchId = batchResult?.batch_id;
    if (succeeded === 0) return;

    const description = failed > 0
      ? t('batchPartialDescription', { ok: succeeded, fail: failed })
      : t('batchAllSuccessDescription', { n: succeeded });

    toast.success(t('batchAssignedNTitle', { n: succeeded }), {
      description,
      duration: 12000,
      action: batchId
        ? { label: t('undoBatchAction'), onClick: () => handleUndoBulkBatch(batchId) }
        : undefined,
    });
  }, [loadGrid, handleUndoBulkBatch, t]);

  const handleRefresh = useCallback(() => {
    setRefreshing(true);
    loadGrid();
  }, [loadGrid]);

  // ── Manual timetable create handler ───────────────────────────────
  const handleManualCreate = useCallback(async () => {
    const name = manualCreateName.trim();
    if (!name) {
      nassaqError(t('manualCreateScheduleNameRequired'), { title: t('manualCreateScheduleFailedTitle') });
      return;
    }
    setManualCreating(true);
    try {
      await api.post(
        '/smart-scheduling/timetables/manual',
        { name },
        { headers: { 'X-School-Context': schoolId } },
      );
      setManualCreateOpen(false);
      setManualCreateName('');
      setScheduleView('draft');
      setRefreshing(true);
      await loadGrid('draft');
      toast.success(t('manualCreateScheduleSuccess'));
    } catch (e) {
      const detail = e?.response?.data?.detail;
      const msg = (typeof detail === 'string' && detail) || detail?.message_ar
        || e?.response?.data?.message_ar || t('manualCreateScheduleFailed');
      nassaqError(msg, { title: t('manualCreateScheduleFailedTitle') });
    } finally {
      setManualCreating(false);
    }
  }, [api, manualCreateName, schoolId, loadGrid, setScheduleView, nassaqError, t]);

  // ── Versions panel handlers ────────────────────────────────────────
  const handleOpenVersions = useCallback(async () => {
    setVersionsOpen(true);
    setVersionsLoading(true);
    try {
      const resp = await api.get('/smart-scheduling/timetable/versions', {
        headers: { 'X-School-Context': schoolId },
      });
      setVersionsData(Array.isArray(resp?.data?.versions) ? resp.data.versions : []);
    } catch {
      toast.error(t('timetableVersionLoadFailed'));
    } finally {
      setVersionsLoading(false);
    }
  }, [api, schoolId, t]);

  const handleTimingSettingsSaved = useCallback(async ({ draftReconciliation } = {}) => {
    // Structural settings can replace the editable draft, so no cell/session
    // identifier captured before the save is safe to keep selected.
    setDrawerOpen(false);
    setDrawerSlot(null);
    setBulkOpen(false);
    setBulkTarget(null);
    setEditDrawerOpen(false);
    setEditDrawerContext(null);
    setUnresolvedConflicts([]);

    // A non-null editable draft id is the backend's canonical signal that
    // reconciliation produced/reused a draft. Show that draft immediately.
    // When it is null (for example a non-structural save), preserve the
    // operator's active published/draft view rather than forcing a switch.
    const nextView = draftReconciliation?.editable_draft_id ? 'draft' : scheduleView;
    if (nextView !== scheduleView) setScheduleView(nextView);

    const versionsRequest = api.get('/smart-scheduling/timetable/versions', {
      headers: { 'X-School-Context': schoolId },
    }).then((resp) => {
      setVersionsData(Array.isArray(resp?.data?.versions) ? resp.data.versions : []);
    }).catch(() => {
      // The save itself is already committed; a transient history refresh
      // must not turn that successful operation into a false save failure.
    });

    await Promise.all([
      loadGrid(nextView, undefined, { silent: true }),
      versionsRequest,
    ]);
  }, [api, loadGrid, scheduleView, schoolId, setScheduleView]);

  const handleUnpublish = useCallback((timetableId, { keepExistingDraft = false } = {}) => {
    nassaqConfirm(
      keepExistingDraft
        ? 'سيتم إلغاء نشر الجدول مع الإبقاء على المسودة الحالية لتعديلها أو إعادة توليدها. لن يتغير الجدول المنشور بصمت؛ ستحتاج إلى مراجعة المسودة ونشرها من جديد. هل تريد المتابعة؟'
        : t('timetableUnpublishConfirmMessage'),
      async () => {
        setUnpublishing(true);
        try {
          await api.post(
            `/smart-scheduling/timetable/${timetableId}/unpublish`,
            keepExistingDraft ? { keep_existing_draft: true } : {},
            { headers: { 'X-School-Context': schoolId } },
          );
          toast.success(
            keepExistingDraft
              ? 'تم إلغاء النشر والإبقاء على المسودة الحالية. احفظ التوقيت ثم راجع المسودة وانشرها من جديد.'
              : t('timetableUnpublishSuccess'),
          );
          setScheduleView('draft');
          setVersionsOpen(false);
          setRefreshing(true);
          await loadGrid('draft');
        } catch (e) {
          const detail = e?.response?.data?.detail;
          const msg = (typeof detail === 'string' && detail) || detail?.message_ar
            || e?.response?.data?.message_ar || t('timetableUnpublishFailed');
          nassaqError(msg, { title: t('timetableUnpublishFailedTitle') });
        } finally {
          setUnpublishing(false);
        }
      },
      { title: t('timetableUnpublishConfirmTitle'), confirmText: t('timetableUnpublish') },
    );
  }, [api, schoolId, loadGrid, setScheduleView, nassaqError, nassaqConfirm, t]);

  const handleUnpublishForTimingSettings = useCallback(async () => {
    try {
      const resp = await api.get('/smart-scheduling/timetable/versions', {
        headers: { 'X-School-Context': schoolId },
      });
      const versions = Array.isArray(resp?.data?.versions) ? resp.data.versions : [];
      const published = versions.find(version => (
        version.status === 'published' || version.is_published === true
      ));
      if (!published) {
        nassaqWarning('لا يوجد جدول منشور حالياً. يمكنك حفظ إعدادات التوقيت مباشرة.');
        return;
      }
      handleUnpublish(published.id, { keepExistingDraft: true });
    } catch (error) {
      const detail = error?.response?.data?.detail;
      const message = (typeof detail === 'string' && detail)
        || detail?.message_ar
        || error?.response?.data?.error?.message
        || 'تعذّر التحقق من الجدول المنشور. حاول مرة أخرى.';
      nassaqError(message);
    }
  }, [api, schoolId, handleUnpublish, nassaqError, nassaqWarning]);

  // Task #141 — Publish flow. Confirms via NassaqAlertDialog (per
  // replit.md: never use native confirm/toast.error for important
  // warnings), POSTs /api/schedule/publish, switches the view to
  // 'published', and refreshes the grid so the admin instantly sees
  // the published version that teachers will see.
  const handlePublish = useCallback(() => {
    if (!schoolId) {
      nassaqError(t('cannotDetermineSchool'));
      return;
    }
    if (publishing) return;
    nassaqConfirm(
      t('publishScheduleConfirmMessage'),
      async () => {
        setPublishing(true);
        try {
          const resp = await api.post(
            '/schedule/publish',
            { school_id: schoolId, timetable_id: grid?.timetable_id || null },
            { headers: { 'X-School-Context': schoolId } },
          );
          const data = resp?.data || {};
          setScheduleView('published');
          setRefreshing(true);
          await loadGrid('published');
          const notified = Number(data.notified_count || 0);
          toast.success(
            notified > 0
              ? t('publishScheduleSuccessWithCount', { n: notified })
              : t('publishScheduleSuccess'),
          );
        } catch (e) {
          const detail = e?.response?.data?.detail;
          // Task #141 — surface PUBLISH_BLOCKED violations in a
          // dedicated NassaqAlertDialog so the admin can see *why*
          // the publish was rejected (HC violation list) instead of
          // the generic toast.
          if (detail?.code === 'PUBLISH_BLOCKED') {
            const violations = Array.isArray(detail.violations) ? detail.violations : [];
            const lines = violations.map((v) => {
              if (typeof v === 'string') return `• ${v}`;
              return `• ${v.message_ar || v.message || v.code || ''}`.trim();
            }).filter(Boolean);
            const body = (detail.message_ar || t('publishBlockedDefault'))
              + (lines.length ? '\n\n' + lines.join('\n') : '');
            nassaqError(body, { title: t('publishBlockedTitle') });
            return;
          }
          let msg = t('publishScheduleFailed');
          if (typeof detail === 'string' && /[\u0600-\u06FF]/.test(detail)) {
            msg = detail;
          } else if (detail?.message_ar) {
            msg = detail.message_ar;
          } else if (e?.response?.data?.message_ar) {
            msg = e.response.data.message_ar;
          }
          nassaqError(msg, { title: t('publishScheduleFailedTitle') });
        } finally {
          setPublishing(false);
        }
      },
      { title: t('publishScheduleConfirmTitle'), confirmText: t('publishScheduleConfirmAction') },
    );
  }, [api, schoolId, grid?.timetable_id, publishing, loadGrid, nassaqConfirm, nassaqError, t]);

  // ── Derived grid view model ───────────────────────────────────────────
  const teacherRows = grid?.teachers || [];
  const cellsByTeacher = grid?.cells || {};
  const days = grid?.days || DAYS.map(d => d.key);
  const periods = grid?.periods || FALLBACK_PERIODS;
  const kpis = grid?.kpis || { fairness_pct: 0, assigned_waiting: 0, absent_teachers_today: 0, vacant_sessions_today: 0 };
  const alertText = grid?.alert;

  // ── KPI: حصة شاغرة (محسوبة من الشبكة) ──────────────────────────────
  // نُعيد حساب عدد الحصص الشاغرة على الواجهة من نفس مصدر العرض حتى
  // يبقى العدد متوافقاً مع ما يراه المستخدم بعد cascade الغياب
  // (يشمل الخانات التي رفعت الواجهة عليها is_vacant عند الغياب لو
  // لم يكن الـbackend قد رفعها بعد). يعتمد فقط على يوم اليوم لأن
  // KPI يقيس "اليوم" بالتعريف.
  const todayKey = grid?.today;
  const vacantSessionsToday = useMemo(() => {
    if (!todayKey) return kpis.vacant_sessions_today || 0;
    let n = 0;
    for (const teacher of teacherRows) {
      const dayCells = cellsByTeacher[teacher.id]?.[todayKey];
      if (!dayCells) continue;
      for (const c of Object.values(dayCells)) {
        if (!c) continue;
        if (c.is_vacant) { n += 1; continue; }
        // Cascade الواجهة: غائب + خانة معبَّأة بدون بديل ⇒ شاغرة فعلياً.
        if (teacher.is_absent_today && !c.is_substituted && !c.is_substitute) n += 1;
      }
    }
    return n;
  }, [teacherRows, cellsByTeacher, todayKey, kpis.vacant_sessions_today]);

  const dayLabelMap = useMemo(
    () => Object.fromEntries(DAYS.map((d) => [d.key, t(d.key)])),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t],
  );

  // ── View mode (Task #142) — pager removed (workspace redesign) ────
  // The master grid no longer exposes a pager UI. Instead it requests
  // a single large window sized by MASTER_GRID_TEACHER_WINDOW (see
  // config/scheduleConfig.js). The backend `teacher_page` /
  // `teacher_page_size` contract from Task #142 is preserved verbatim;
  // only the UI affordance is removed. If the server reports
  // `pagination.total > MASTER_GRID_TEACHER_WINDOW`, the
  // no-silent-truncation handler in Task 9 surfaces a NassaqAlertDialog.

  const [viewMode, setViewMode] = useState(() => {
    try {
      const v = localStorage.getItem('nassaq_master_grid_view_mode');
      return v === 'daily' ? 'daily' : 'weekly';
    } catch { return 'weekly'; }
  });
  useEffect(() => {
    try { localStorage.setItem('nassaq_master_grid_view_mode', viewMode); } catch {}
  }, [viewMode]);

  const [selectedDay, setSelectedDay] = useState(() => {
    try {
      const params = new URLSearchParams(location.search);
      const dayParam = params.get('day')?.toLowerCase();
      if (dayParam && DAYS.some((d) => d.key === dayParam)) return dayParam;
      const saved = localStorage.getItem('nassaq_master_grid_selected_day');
      if (saved && DAYS.some((d) => d.key === saved)) return saved;
    } catch {}
    return null;
  });

  useEffect(() => {
    if (selectedDay) {
      try {
        localStorage.setItem('nassaq_master_grid_selected_day', selectedDay);
      } catch {}
    }
  }, [selectedDay]);

  // Sync selected day to URL in daily mode so refreshing or sharing URL preserves the day
  useEffect(() => {
    if (tab !== 'master') return;
    const params = new URLSearchParams(location.search);
    let changed = false;
    if (viewMode === 'daily') {
      if (selectedDay && params.get('day') !== selectedDay) {
        params.set('day', selectedDay);
        changed = true;
      }
    } else {
      if (params.has('day')) {
        params.delete('day');
        changed = true;
      }
    }
    if (changed) {
      navigate(`${location.pathname}?${params.toString()}`, { replace: true });
    }
  }, [tab, viewMode, selectedDay, location.pathname, location.search, navigate]);

  // Sync selectedDay with available days when grid loads / changes.
  // Preserves existing valid selection or saved day, then falls back to today or the first available day.
  useEffect(() => {
    if (!days?.length) return;
    setSelectedDay((cur) => {
      if (cur && days.includes(cur)) return cur;
      try {
        const params = new URLSearchParams(location.search);
        const dayParam = params.get('day')?.toLowerCase();
        if (dayParam && days.includes(dayParam)) return dayParam;
        const saved = localStorage.getItem('nassaq_master_grid_selected_day');
        if (saved && days.includes(saved)) return saved;
      } catch {}
      if (todayKey && days.includes(todayKey)) return todayKey;
      return days[0];
    });
  }, [days, todayKey, location.search]);

  // Mirror current view/day into a ref so loadGrid's stable callback
  // can read it without re-creating on every render. The single window
  // size is constant across the session.
  const paginationStateRef = useRef({
    pageIndex: 0,
    pageSize: MASTER_GRID_TEACHER_WINDOW,
    day: viewMode === 'daily' ? selectedDay : null,
  });

  // Task #142 — totals come from the backend pagination block.
  const totalTeachersAll = grid?.pagination?.total ?? teacherRows.length;
  const pagedTeachers = teacherRows;

  // No-silent-truncation guard: if the server reports more teachers
  // than MASTER_GRID_TEACHER_WINDOW, surface a one-time NassaqAlertDialog
  // notice per session. The window itself is configurable (see
  // config/scheduleConfig.js); the long-term fix when this fires
  // repeatedly in a deployment is to bump the constant, not to
  // restore the pager UI. Tracked by `truncationNoticeShown` so the
  // notice only appears once per page mount.
  const [truncationNoticeShown, setTruncationNoticeShown] = useState(false);
  useEffect(() => {
    if (truncationNoticeShown) return;
    const total = grid?.pagination?.total;
    if (typeof total !== 'number') return;
    if (total <= MASTER_GRID_TEACHER_WINDOW) return;
    setTruncationNoticeShown(true);
    if (typeof nassaqWarning === 'function') {
      nassaqWarning(
        t('masterGridTruncationBody', {
          shown: MASTER_GRID_TEACHER_WINDOW,
          total,
        }),
        { title: t('masterGridTruncationTitle') },
      );
    }
  }, [grid?.pagination?.total, truncationNoticeShown, nassaqWarning, t]);

  const dayParam = viewMode === 'daily' ? selectedDay : null;

  // Re-fetch when the view-mode or selected day changes. The window
  // size never changes, so we drop the old pageSize-driven effect.
  const lastFetchedRef = useRef({ day: null, mode: null });
  useEffect(() => {
    if (tab !== 'master') return;
    paginationStateRef.current = {
      pageIndex: 0,
      pageSize: MASTER_GRID_TEACHER_WINDOW,
      day: dayParam,
    };
    const last = lastFetchedRef.current;
    if (last.day === dayParam && last.mode === viewMode) return;
    lastFetchedRef.current = { day: dayParam, mode: viewMode };
    loadGrid(undefined, {
      page: 1,
      pageSize: MASTER_GRID_TEACHER_WINDOW,
      day: dayParam,
    });
  }, [viewMode, dayParam, tab, loadGrid]);

  if (tab === 'standby') {
    // تبويب جدول حصص الانتظار — يُضمَّن المحتوى نفسه المستخدم في الصفحة
    // المستقلة `/school/standby` بدون لمس مصدر بياناته.
    //
    // ملاحظة تخطيطية: الغلاف الخارجي مطابق تماماً للغلاف المستخدم في تبويب
    // «الجدول الرئيسي» أدناه (نفس الارتفاع، بدون حشو علوي، بدون gap)، حتى
    // يبدأ محتوى التبويبَين من نفس النقطة الرأسية ولا يحدث أيّ انزياح بصري
    // عند التبديل بينهما. الحشو الأفقي والمسافة العلوية الموحَّدة (pt-3) تُطبَّق
    // على غلاف داخلي يلفّ StandbyRosterContent، تماماً كما تفعل شريحة KPI في
    // تبويب الجدول الرئيسي. هذا يُبقي StandbyRosterContent نفسه دون تعديل،
    // فلا تتأثَّر صفحة `/school/standby` المستقلة.
    return (
      <Sidebar>
        <div
          dir={direction}
          className="flex flex-col h-[100dvh] bg-slate-50 text-slate-900 overflow-hidden"
        >
          <ScheduleTabNav active="standby" />
          <div className="flex-1 min-h-0 flex flex-col gap-5 px-4 md:px-6 pt-3 pb-4 md:pb-6 [&>*:first-child]:mt-0">
            <StandbyRosterContent />
          </div>
        </div>
      </Sidebar>
    );
  }

  if (tab === 'settings') {
    // الغلاف الخارجي مطابق تماماً لتبويبَي «الجدول الرئيسي» و«جدول حصص
    // الانتظار» حتى يبدأ المحتوى من نفس النقطة الرأسية بلا انزياح بصري عند
    // التبديل بين التبويبات الثلاثة. الحشو الأفقي والمسافة العلوية الموحَّدة
    // (pt-3) تُطبَّق على غلاف داخلي يلفّ الترويسة ومحتوى الإعدادات.
    return (
      <Sidebar>
        <div
          dir={direction}
          className="flex flex-col h-[100dvh] bg-slate-50 text-slate-900 overflow-hidden"
        >
          {/* ── Primary tab nav (Master / Standby / Settings) ─────────── */}
          <ScheduleTabNav active="settings" />

          <div className="flex-1 min-h-0 overflow-auto">
            <div className="flex flex-col gap-5 px-4 md:px-6 pt-3 pb-4 md:pb-6 [&>*:first-child]:mt-0">
              {/* ── Header ───────────────────────────────────────────── */}
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                <div>
                  <h1 className="text-2xl md:text-3xl font-bold text-[#1C3D74] flex items-center gap-2">
                    <Settings className="h-7 w-7 text-[#1C3D74]" />
                    {t('settingsScheduleTitle')}
                  </h1>
                  <p className="text-sm text-slate-500 mt-1">
                    {t('settingsScheduleSubtitle')}
                  </p>
                </div>
              </div>

              <ScheduleSettingsTabContent
                onUnpublishPublished={handleUnpublishForTimingSettings}
                unpublishingPublished={unpublishing}
                onTimingSettingsSaved={handleTimingSettingsSaved}
              />
            </div>
          </div>
        </div>
      </Sidebar>
    );
  }

  return (
    <Sidebar>
      <div
        dir={direction}
        data-master-schedule-root
        className="flex flex-col h-[100dvh] bg-slate-50 text-slate-900"
        style={{
          // Mode-specific pre-measurement fallback per spec §4.2
          // (daily ≤ 88 px, weekly ≤ 52 px). The ResizeObserver in
          // Task 4 overwrites this with the real measured height on
          // first paint; the fallback only matters for the first
          // synchronous render before the observer fires.
          '--sticky-band-h': viewMode === 'daily' ? '88px' : '52px',
        }}
      >
        {/* ── Primary tab nav (Master / Standby / Settings) ─────────── */}
        <ScheduleTabNav active="master" />

        {/* ── KPI strip (Task #142) ────────────────────────────────────
            Compact horizontal pill row instead of tall dashboard cards.
            On wider screens the four KPIs sit side-by-side on a single
            line, reclaiming vertical space for the timetable below. On
            mobile they fall back to a 2×2 grid so the operator can
            still scan them without horizontal scroll. */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 px-4 md:px-6 pt-3">
          <KpiCard
            icon={Scale}
            label={t('distributionFairness')}
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
            label={t('assignedStandby')}
            value={kpis.assigned_waiting}
            accent={{
              topBorder: 'border-t-blue-400',
              iconBg: 'bg-blue-50', iconText: 'text-blue-600',
              valueText: 'text-slate-900',
            }}
          />
          <KpiCard
            icon={UserMinus}
            label={t('absentTeacherLabel')}
            value={kpis.absent_teachers_today}
            accent={{
              topBorder: 'border-t-yellow-400',
              iconBg: 'bg-yellow-50', iconText: 'text-yellow-600',
              valueText: 'text-slate-900',
            }}
          />
          <KpiCard
            icon={AlertOctagon}
            label={t('vacantPeriodLabel')}
            value={vacantSessionsToday}
            accent={{
              topBorder: 'border-t-red-500',
              iconBg: 'bg-red-50', iconText: 'text-red-600',
              valueText: 'text-red-700',
            }}
          />
        </div>

        {/* Draft / smart-alert / Hakim-insights banners removed — all
            three collapsed into chips inside the sticky band (Task 4)
            to free first-paint vertical space above the matrix per
            workspace redesign spec §4.2. The HakimInsightsDrawer
            invocation immediately below stays — it's the drawer the
            chip opens on click. */}

        <HakimInsightsDrawer
          open={insightsDrawerOpen}
          onOpenChange={setInsightsDrawerOpen}
          conflicts={unresolvedConflicts}
          retrying={generating}
          onNavigate={(tab) => {
            // نغلق الدرج أولاً ثم ننتقل إلى تبويب الإعدادات المناسب
            // داخل التبويب نفسه (SPA navigation) لتفادي الفتح المزدوج.
            setInsightsDrawerOpen(false);
            navigate(`/principal/schedule?tab=settings&sub=${encodeURIComponent(tab)}`);
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

        {/* ── Manual edit drawer (master grid, draft only) ───────────
            Hosts the edit / move / delete / add flows for individual
            grid cells. Wires to the existing smart-scheduling session
            endpoints (no duplication) and reloads the grid on success
            so the matrix reflects the change immediately. */}
        <SessionEditDrawer
          open={editDrawerOpen}
          mode={editDrawerMode}
          context={editDrawerContext}
          schoolId={schoolId}
          timetableId={grid?.timetable_id}
          teachers={teacherRows}
          periods={periods}
          api={api}
          onClose={() => setEditDrawerOpen(false)}
          onSaved={() => {
            // Pull the fresh draft silently so the matrix mirrors the mutation
            // without unmounting or resetting scroll position.
            loadGrid('draft', undefined, { silent: true });
          }}
        />

        <style>{`
          [data-master-schedule-root] [data-testid="master-schedule-sticky-band"][data-density="compact"] [data-band-action-label] { display: none; }
          [data-master-schedule-root] [data-testid="master-schedule-sticky-band"][data-density="compact"] [data-band-action-label-short] { display: inline; }
          [data-master-schedule-root] [data-testid="master-schedule-sticky-band"][data-density="dense"] [data-band-action-label],
          [data-master-schedule-root] [data-testid="master-schedule-sticky-band"][data-density="dense"] [data-band-action-label-short],
          [data-master-schedule-root] [data-testid="master-schedule-sticky-band"][data-density="dense"] [data-band-title],
          [data-master-schedule-root] [data-testid="master-schedule-sticky-band"][data-density="dense"] [data-band-chip-label] { display: none; }
        `}</style>

        {/* ── Sticky action band (workspace redesign) ─────────────────
            Top: 0; height exposed to matrix header offsets via
            --sticky-band-h. Density attribute degrades title +
            button labels at narrow band widths to prevent wrapping. */}
        <div
          ref={stickyBandRef}
          data-testid="master-schedule-sticky-band"
          data-density="default"
          className="sticky top-0 z-20 bg-white/95 backdrop-blur border-b border-slate-200"
        >
          {/* Row 1: status chips (start) + actions (end). The h1 page
              title and the decorative Sparkles icon are intentionally
              omitted from the sticky band — the page is already
              labeled by ScheduleTabNav above and a redundant title
              consumes the matrix's first-glance budget. The smart-alert
              and Hakim-insights blocks (previously rendered as full
              banners above the matrix) collapse into the chip cluster
              here as icon-with-tooltip indicators that open the
              existing dialogs/drawers on click — they no longer
              consume any first-paint vertical space above the matrix. */}
          <div className="flex items-center justify-between gap-3 px-4 md:px-6 py-1.5 min-w-0">
            <div className="flex items-center gap-1.5 min-w-0">
              {grid?.timetable_status === 'draft' && (
                <span
                  data-testid="draft-status-chip"
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-300 shrink-0"
                  title={t('draftScheduleBanner')}
                >
                  <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                  <span data-band-chip-label>{t('scheduleViewDraft')}</span>
                </span>
              )}
              {alertText && (
                <button
                  type="button"
                  data-testid="smart-alert-chip"
                  onClick={() => {
                    // replit.md guardrail: NassaqAlertDialog only —
                    // no native alert(). Reuse the same imperative
                    // helper used elsewhere on the page.
                    if (typeof nassaqError === 'function') {
                      nassaqError(alertText);
                    }
                  }}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-100 text-red-800 border border-red-300 shrink-0 hover:bg-red-200 transition-colors"
                  title={alertText}
                  aria-label={alertText}
                >
                  <AlertTriangle className="h-3 w-3" aria-hidden="true" />
                  <span data-band-chip-label>{t('smartAlertChipLabel')}</span>
                </button>
              )}
              {!insightsDismissed && unresolvedConflicts && unresolvedConflicts.length > 0 && (
                <button
                  type="button"
                  data-testid="hakim-insights-chip"
                  onClick={() => setInsightsDrawerOpen(true)}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-orange-100 text-orange-800 border border-orange-300 shrink-0 hover:bg-orange-200 transition-colors"
                  title={t('hakimInsightsBannerTitle', { count: unresolvedConflicts.length })}
                  aria-label={t('hakimInsightsBannerTitle', { count: unresolvedConflicts.length })}
                >
                  <Lightbulb className="h-3 w-3" aria-hidden="true" />
                  <span data-band-chip-label>{unresolvedConflicts.length}</span>
                </button>
              )}
            </div>

            <div className="flex items-center gap-1.5 shrink-0">
              {/* View toggle (draft/published) */}
              <div
                role="tablist"
                aria-label={t('scheduleViewToggleLabel')}
                className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5 shadow-sm"
              >
                <button
                  type="button"
                  role="tab"
                  aria-selected={scheduleView === 'published'}
                  onClick={() => setScheduleView('published')}
                  className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
                    scheduleView === 'published'
                      ? 'bg-emerald-600 text-white shadow-sm'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                  data-testid="schedule-view-published"
                >
                  {t('scheduleViewPublished')}
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={scheduleView === 'draft'}
                  onClick={() => setScheduleView('draft')}
                  className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
                    scheduleView === 'draft'
                      ? 'bg-amber-500 text-white shadow-sm'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                  data-testid="schedule-view-draft"
                >
                  {t('scheduleViewDraft')}
                </button>
              </div>

              {/* View mode toggle (daily/weekly) */}
              <div
                role="tablist"
                aria-label={t('masterGridViewModeLabel')}
                className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5 shadow-sm"
              >
                <button
                  type="button"
                  role="tab"
                  aria-selected={viewMode === 'daily'}
                  onClick={() => setViewMode('daily')}
                  className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
                    viewMode === 'daily'
                      ? 'bg-brand-navy text-white shadow-sm'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                  data-testid="view-mode-daily"
                >
                  {t('dailyViewLabel')}
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={viewMode === 'weekly'}
                  onClick={() => setViewMode('weekly')}
                  className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors ${
                    viewMode === 'weekly'
                      ? 'bg-brand-navy text-white shadow-sm'
                      : 'text-slate-600 hover:bg-slate-100'
                  }`}
                  data-testid="view-mode-weekly"
                >
                  {t('weeklyViewLabel')}
                </button>
              </div>

              {/* Generate */}
              <Button
                onClick={handleAutoGenerate}
                disabled={generating}
                className="bg-violet-600 hover:bg-violet-700 text-white shadow-sm h-8 px-2.5"
                data-band-action="generate"
                title={t('autoGenerateSchedule')}
                aria-label={t('autoGenerateSchedule')}
              >
                {generating ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Wand2 className="h-4 w-4" />
                )}
                <span data-band-action-label className="ms-1.5">
                  {generating ? t('generatingSchedule') : t('autoGenerateSchedule')}
                </span>
                <span data-band-action-label-short className="ms-1.5 hidden">
                  {t('autoGenerateScheduleShort')}
                </span>
              </Button>

              {/* Create manually */}
              <Button
                onClick={() => { setManualCreateName(''); setManualCreateOpen(true); }}
                disabled={generating}
                variant="outline"
                className="border-slate-300 text-slate-700 hover:bg-slate-100 hover:text-slate-700 focus-visible:text-slate-700 shadow-sm h-8 px-2.5"
                data-band-action="manual-create"
                title={t('manualCreateSchedule')}
                aria-label={t('manualCreateSchedule')}
                data-testid="manual-create-schedule-btn"
              >
                <PenLine className="h-4 w-4" />
                <span data-band-action-label className="ms-1.5">
                  {t('manualCreateSchedule')}
                </span>
                <span data-band-action-label-short className="ms-1.5 hidden">
                  {t('manualCreateScheduleShort')}
                </span>
              </Button>

              {/* Versions */}
              <Button
                onClick={handleOpenVersions}
                variant="outline"
                className="border-slate-300 text-slate-700 hover:bg-slate-100 hover:text-slate-700 focus-visible:text-slate-700 shadow-sm h-8 px-2.5"
                data-band-action="versions"
                title={t('timetableVersionsOpen')}
                aria-label={t('timetableVersionsOpen')}
                data-testid="open-timetable-versions-btn"
              >
                <History className="h-4 w-4" />
                <span data-band-action-label className="ms-1.5">
                  {t('timetableVersionsOpen')}
                </span>
              </Button>

              {/* Publish */}
              {(() => {
                const noDraft = !(grid?.timetable_status === 'draft');
                const disabled = publishing || noDraft;
                const tooltip = noDraft
                  ? t('publishScheduleNoDraftTooltip')
                  : t('publishScheduleAction');
                return (
                  <Button
                    onClick={handlePublish}
                    disabled={disabled}
                    title={tooltip}
                    aria-label={tooltip}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm disabled:opacity-50 disabled:cursor-not-allowed h-8 px-2.5"
                    data-testid="publish-schedule-btn"
                    data-band-action="publish"
                  >
                    {publishing ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <CheckCircle2 className="h-4 w-4" />
                    )}
                    <span data-band-action-label className="ms-1.5">
                      {publishing ? t('publishingSchedule') : t('publishScheduleAction')}
                    </span>
                    <span data-band-action-label-short className="ms-1.5 hidden">
                      {t('publishScheduleActionShort')}
                    </span>
                  </Button>
                );
              })()}

              {/* Record absence */}
              <Button
                onClick={handleLogAbsence}
                variant="outline"
                className="border-slate-300 text-slate-700 hover:bg-slate-100 hover:text-slate-700 focus-visible:text-slate-700 h-8 px-2.5"
                data-band-action="absence"
                title={t('recordAbsence')}
                aria-label={t('recordAbsence')}
              >
                <UserX className="h-4 w-4" />
                <span data-band-action-label className="ms-1.5">
                  {t('recordAbsence')}
                </span>
                <span data-band-action-label-short className="ms-1.5 hidden">
                  {t('recordAbsenceShort')}
                </span>
              </Button>

              {/* Refresh */}
              <Button
                onClick={handleRefresh}
                variant="ghost"
                size="icon"
                disabled={refreshing}
                title={t('refreshTooltip')}
                aria-label={t('refreshTooltip')}
                className="h-8 w-8"
              >
                <RefreshCw className={`h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>

          {/* Row 2: day tabs (daily mode only) */}
          {viewMode === 'daily' && days.length > 0 && (
            <div
              data-testid="day-tabs-row"
              className="flex items-center gap-2 px-4 md:px-6 pb-2 overflow-x-auto md:overflow-visible md:flex-wrap [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
            >
              <div
                role="tablist"
                aria-label={t('selectDayLabel')}
                className={`inline-flex flex-nowrap md:flex-wrap gap-1 rounded-lg border border-slate-200 bg-white p-0.5 shadow-sm ${loading ? 'opacity-70' : ''}`}
              >
                {days.map((dayKey) => {
                  const isActive = selectedDay === dayKey;
                  const isToday = todayKey === dayKey;
                  return (
                    <button
                      key={`day-tab-${dayKey}`}
                      type="button"
                      role="tab"
                      aria-selected={isActive}
                      disabled={loading}
                      onClick={() => setSelectedDay(dayKey)}
                      className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors flex items-center gap-1 disabled:cursor-wait ${
                        isActive
                          ? 'bg-brand-turquoise text-white shadow-[0_1px_2px_rgba(43,181,160,0.35)]'
                          : 'text-slate-600 hover:bg-slate-100'
                      }`}
                      data-testid={`day-tab-${dayKey}`}
                    >
                      {dayLabelMap[dayKey] || dayKey}
                      {isToday && (
                        <span className={`text-[9px] px-1 rounded ${isActive ? 'bg-white/25 text-white' : 'bg-emerald-100 text-emerald-700'}`}>
                          {t('todayBadge')}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* ── Master matrix grid (Task #142) ─────────────────────────
            The matrix is the dominant workspace surface of the page.
            Thin rounded border + soft shadow integrate it into the
            page surface; daily mode never scrolls horizontally,
            weekly mode scrolls horizontally inside the container
            while the teacher column and headers stay sticky. */}
        {/* Mobile-only agenda (period-first vertical list). The
            desktop `MasterMatrix` below is unchanged and hidden on
            phones via `hidden md:flex` — see Task #526. */}
        <div className="md:hidden flex-grow min-h-0 overflow-auto" data-testid="master-matrix-mobile">
          <MobileScheduleAgenda
            teachers={teacherRows}
            cells={cellsByTeacher}
            days={days}
            periods={periods}
            dayLabelMap={dayLabelMap}
            viewMode={viewMode}
            selectedDay={selectedDay}
            today={grid?.today}
            periodTimes={grid?.period_times || {}}
            unresolvedConflicts={unresolvedConflicts}
            canEdit={scheduleView === 'draft' && !!grid?.timetable_id}
            onEditSession={({ session }) => {
              setEditDrawerMode('edit');
              setEditDrawerContext({ session });
              setEditDrawerOpen(true);
            }}
            onVacantClick={handleVacantClick}
            loading={loading}
            error={error}
            onRetry={() => loadGrid()}
            enableCoverage={coverageEnabled}
            schoolId={schoolId}
          />
        </div>
        <div className="relative hidden md:flex flex-col flex-grow min-h-0" data-testid="master-matrix-region">
          {viewMode === 'weekly' && (
            <>
              <div
                aria-hidden="true"
                data-testid="matrix-edge-fade-end"
                className="pointer-events-none absolute top-0 bottom-0 w-6 z-[5] transition-opacity duration-150"
                style={{
                  insetInlineEnd: 0,
                  background: 'linear-gradient(to var(--scroll-fade-end-dir, left), rgba(255,255,255,1), rgba(255,255,255,0))',
                  opacity: 'var(--scroll-fade-end-opacity, 0)',
                }}
              />
              <div
                aria-hidden="true"
                data-testid="matrix-edge-fade-start"
                className="pointer-events-none absolute top-0 bottom-0 w-6 z-[5] transition-opacity duration-150"
                style={{
                  insetInlineStart: 0,
                  background: 'linear-gradient(to var(--scroll-fade-start-dir, right), rgba(255,255,255,1), rgba(255,255,255,0))',
                  opacity: 'var(--scroll-fade-start-opacity, 0)',
                }}
              />
            </>
          )}
        <div
          ref={matrixContainerRef}
          data-testid="master-matrix-container"
          data-matrix-overflow={viewMode === 'weekly' ? 'horizontal' : 'none'}
          // Both view modes share a single constrained two-axis internal
          // scroll container — the matrix scrolls INSIDE this box, never at
          // the page level. overflow-x:auto handles horizontal scroll (wide
          // weekly day columns; daily uses minmax(0,1fr) so it normally fits
          // and no horizontal scrollbar appears). overflow-y:auto + flex-grow
          // + min-h-0 give the container a real constrained height, so it
          // becomes a vertical scroll box bounded by the page shell. Because
          // the container — not the document — is the scroll parent,
          // position:sticky headers inside stick relative to it (corner /
          // day-band at top:0, period row at top:DAY_HEADER_HEIGHT) without
          // any page-level --sticky-band-h offset. (CSS overflow coercion
          // forces a non-visible overflow on one axis to coerce the other
          // visible → auto anyway, so embracing it with an explicit
          // constrained height is the correct architectural pattern.)
          className="relative bg-white border border-slate-200/70 rounded-2xl shadow-[0_1px_2px_rgba(15,42,75,0.04),0_8px_24px_-12px_rgba(15,42,75,0.12)] overflow-x-auto overflow-y-auto flex-grow min-h-0"
        >
          {loading && !grid ? (
            <MasterMatrixSkeleton
              rows={Math.min(MASTER_GRID_TEACHER_WINDOW, totalTeachersAll || 12)}
              days={viewMode === 'daily' ? 1 : ((grid?.days?.length) || days.length || 5)}
              periods={(grid?.periods?.length) || SKELETON_GRID_COLS}
              isDaily={viewMode === 'daily'}
            />
          ) : error && !grid ? (
            <div className="p-6 text-center text-red-600">{error}</div>
          ) : teacherRows.length === 0 ? (
            <div className="p-6 text-center text-slate-500">
              {t('noTeachersRegistered')}
            </div>
          ) : grid?.is_empty ? (
            // Task #141 — explicit empty-state when the requested
            // view (draft/published) has no matching timetable. The
            // legacy fallback only checked ``teacherRows.length``
            // which masks "no published yet" vs "no teachers" — two
            // very different problems. Includes action buttons so
            // the admin can move forward without hunting for them.
            <div className="p-10 text-center text-slate-600 flex flex-col items-center gap-4" data-testid="schedule-empty-state">
              <div>
                <p className="text-base font-semibold mb-2 text-slate-800">
                  {scheduleView === 'published'
                    ? t('noPublishedScheduleYet')
                    : t('noDraftScheduleYet')}
                </p>
                <p className="text-sm text-slate-500 max-w-md mx-auto">
                  {scheduleView === 'published'
                    ? t('noPublishedScheduleHint')
                    : t('noDraftScheduleHint')}
                </p>
              </div>
              <div className="flex flex-wrap items-center justify-center gap-2">
                <Button
                  onClick={handleAutoGenerate}
                  disabled={generating}
                  className="bg-violet-600 hover:bg-violet-700 text-white"
                  data-testid="empty-state-generate-btn"
                >
                  {generating ? (
                    <Loader2 className="h-4 w-4 me-2 animate-spin" />
                  ) : (
                    <Wand2 className="h-4 w-4 me-2" />
                  )}
                  {generating ? t('generatingSchedule') : t('autoGenerateSchedule')}
                </Button>
                <Button
                  onClick={() => { setManualCreateName(''); setManualCreateOpen(true); }}
                  disabled={generating}
                  variant="outline"
                  className="border-slate-300 text-slate-700 hover:bg-slate-100 hover:text-slate-700 focus-visible:text-slate-700"
                  data-testid="empty-state-manual-create-btn"
                >
                  <PenLine className="h-4 w-4 me-2" />
                  {t('manualCreateSchedule')}
                </Button>
                {scheduleView === 'published' && (
                  <Button
                    onClick={() => setScheduleView('draft')}
                    variant="outline"
                    className="border-amber-300 text-amber-700 hover:bg-amber-50 hover:text-amber-700 focus-visible:text-amber-700"
                    data-testid="empty-state-switch-draft-btn"
                  >
                    {t('switchToDraftView')}
                  </Button>
                )}
                {scheduleView === 'draft' && (
                  <Button
                    onClick={() => setScheduleView('published')}
                    variant="outline"
                    className="border-emerald-300 text-emerald-700 hover:bg-emerald-50 hover:text-emerald-700 focus-visible:text-emerald-700"
                    data-testid="empty-state-switch-published-btn"
                  >
                    {t('switchToPublishedView')}
                  </Button>
                )}
              </div>
            </div>
          ) : (
            <MasterMatrix
              teachers={pagedTeachers}
              totalTeachers={totalTeachersAll}
              cells={cellsByTeacher}
              days={days}
              periods={periods}
              dayLabelMap={dayLabelMap}
              viewMode={viewMode}
              selectedDay={selectedDay}
              onVacantClick={handleVacantClick}
              onUndoAbsence={handleRequestUndoAbsence}
              onBulkCoverClick={handleOpenBulkPanel}
              onAcknowledgeRelocation={handleAcknowledgeRelocation}
              today={grid?.today}
              periodTimes={grid?.period_times || {}}
              unresolvedConflicts={unresolvedConflicts}
              canEdit={scheduleView === 'draft' && !!grid?.timetable_id}
              onEditSession={({ session }) => {
                setEditDrawerMode('edit');
                setEditDrawerContext({ session });
                setEditDrawerOpen(true);
              }}
              onCreateSession={(ctx) => {
                setEditDrawerMode('create');
                setEditDrawerContext(ctx);
                setEditDrawerOpen(true);
              }}
              onDragMove={handleSessionDragMove}
              enableCoverage={coverageEnabled}
              schoolId={schoolId}
            />
          )}

          {/* ── Hakeem-branded loading overlay ────────────────────────
              يظهر فقط أثناء التوليد التلقائي. يستخدم تعبير "ai-thinking"
              من معرض حكيم مع نبضة ضوئية بنفسجية لتأكيد أن المحرك يقرأ
              القيود ويبني الجدول الذكي. */}
          {generating && <HakimGeneratingOverlay serverProgress={generationProgress} />}
        </div>
        </div>

        {/* ── Absence dialog ─────────────────────────────────────── */}
        <Dialog open={absenceOpen} onOpenChange={setAbsenceOpen}>
          <DialogContent dir={direction} className="max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-[#1C3D74]">
                <UserX className="h-5 w-5 text-red-600" />
                {t('recordTeacherAbsence')}
              </DialogTitle>
              <DialogDescription>
                {t('recordTeacherAbsenceDescription')}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-2">
              <div className="space-y-2">
                <Label htmlFor="absence-teacher">{t('teacher')}</Label>
                <Select value={absenceTeacherId} onValueChange={setAbsenceTeacherId}>
                  <SelectTrigger id="absence-teacher" className="w-full">
                    <SelectValue placeholder={t('selectTeacherPlaceholder')} />
                  </SelectTrigger>
                  <SelectContent>
                    {teacherRows.length === 0 ? (
                      <div className="px-3 py-2 text-sm text-slate-500">
                        {t('noTeachersAvailable')}
                      </div>
                    ) : (
                      teacherRows.map((row) => (
                        <SelectItem key={row.id} value={row.id} disabled={row.is_absent_today}>
                          {row.full_name}
                          {row.is_absent_today ? ` ${t('absentTodayTag')}` : ''}
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="absence-notes">{t('notesOptional')}</Label>
                <Textarea
                  id="absence-notes"
                  value={absenceNotes}
                  onChange={(e) => setAbsenceNotes(e.target.value)}
                  placeholder={t('absenceNotesPlaceholder')}
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
                {t('cancel')}
              </Button>
              <Button
                onClick={handleSubmitAbsence}
                disabled={savingAbsence || !absenceTeacherId}
                className="bg-red-600 hover:bg-red-700 text-white"
              >
                {savingAbsence ? (
                  <Loader2 className="h-4 w-4 me-2 animate-spin" />
                ) : (
                  <UserX className="h-4 w-4 me-2" />
                )}
                {savingAbsence ? t('savingAbsenceLabel') : t('recordAbsenceConfirm')}
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
          <DialogContent dir={direction} className="max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-[#1C3D74]">
                <Undo2 className="h-5 w-5 text-emerald-600" />
                {t('undoAbsenceTitle')}
              </DialogTitle>
              <DialogDescription>
                {t('undoAbsenceDesc')}
              </DialogDescription>
            </DialogHeader>

            <div className="py-2 text-sm text-slate-700">
              {t('undoAbsenceConfirmQuestion')}{' '}
              <span className="font-semibold text-slate-900">
                {undoTeacher?.full_name || '—'}
              </span>{' '}
              {t('forThisDayQuestion')}
            </div>

            <DialogFooter className="gap-2 sm:gap-2">
              <Button
                variant="outline"
                onClick={() => setUndoTeacher(null)}
                disabled={undoingAbsence}
              >
                {t('cancel')}
              </Button>
              <Button
                onClick={handleConfirmUndoAbsence}
                disabled={undoingAbsence}
                className="bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                {undoingAbsence ? (
                  <Loader2 className="h-4 w-4 me-2 animate-spin" />
                ) : (
                  <Undo2 className="h-4 w-4 me-2" />
                )}
                {undoingAbsence ? t('undoingAbsence') : t('confirmUndoAbsence')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      {/* ── Manual timetable create dialog ─────────────────────────
          Dialog with a single text input for naming the blank draft.
          On submit: POST /smart-scheduling/timetables/manual → switches
          to draft view and reloads the grid. */}
      <Dialog open={manualCreateOpen} onOpenChange={(v) => { if (!v) setManualCreateOpen(false); }}>
        <DialogContent dir={direction} className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-brand-navy">
              <PenLine className="h-5 w-5 text-brand-turquoise" aria-hidden="true" />
              {t('manualCreateScheduleTitle')}
            </DialogTitle>
            <DialogDescription>
              {t('manualCreateScheduleDescription')}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2 py-2">
            <Label htmlFor="manual-timetable-name" className="text-xs font-semibold">
              {t('manualCreateScheduleNameLabel')}
            </Label>
            <Input
              id="manual-timetable-name"
              dir={direction}
              value={manualCreateName}
              onChange={(e) => setManualCreateName(e.target.value)}
              placeholder={t('manualCreateScheduleNamePlaceholder')}
              disabled={manualCreating}
              onKeyDown={(e) => { if (e.key === 'Enter' && !manualCreating) handleManualCreate(); }}
              data-testid="manual-create-name-input"
            />
          </div>

          <DialogFooter className="gap-2 sm:gap-2">
            <Button variant="outline" onClick={() => setManualCreateOpen(false)} disabled={manualCreating}>
              {t('cancelAction')}
            </Button>
            <Button
              onClick={handleManualCreate}
              disabled={manualCreating || !manualCreateName.trim()}
              className="bg-brand-turquoise hover:bg-brand-turquoise-dark text-white"
              data-testid="manual-create-confirm-btn"
            >
              {manualCreating ? (
                <Loader2 className="h-4 w-4 animate-spin me-1" />
              ) : (
                <PenLine className="h-4 w-4 me-1" />
              )}
              {manualCreating ? t('manualCreateScheduleCreating') : t('manualCreateScheduleSubmit')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Timetable versions panel ────────────────────────────────
          Side Sheet listing all draft+published timetables for the school.
          Published items show a "منشور" badge and an "إلغاء النشر" button.
          Clicking a draft item switches the grid to draft view. */}
      <Sheet open={versionsOpen} onOpenChange={setVersionsOpen}>
        <SheetContent
          side={direction === 'rtl' ? 'left' : 'right'}
          dir={direction}
          className="w-full sm:max-w-md p-0 flex flex-col gap-0"
          data-testid="timetable-versions-panel"
        >
          <SheetHeader className="p-5 bg-gradient-to-l from-brand-turquoise/15 to-brand-turquoise/5 border-b border-brand-turquoise/30 text-start">
            <SheetTitle className="flex items-center gap-2 text-brand-navy">
              <History className="h-5 w-5 text-brand-turquoise" aria-hidden="true" />
              {t('timetableVersionsTitle')}
            </SheetTitle>
            <SheetDescription className="text-brand-navy/70 text-xs">
              {t('timetableVersionsOpen')}
            </SheetDescription>
          </SheetHeader>

          <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-slate-50">
            {versionsLoading ? (
              <div className="flex items-center justify-center py-10">
                <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
              </div>
            ) : versionsData.length === 0 ? (
              <p className="text-center text-slate-500 text-sm py-10">
                {t('timetableVersionsEmpty')}
              </p>
            ) : (
              versionsData.map((v) => {
                const isPublished = v.status === 'published';
                const isDraft = v.status === 'draft';
                const isManual = v.generation_mode === 'manual';
                return (
                  <div
                    key={v.id}
                    className={`rounded-lg border bg-white p-3 flex flex-col gap-2 ${isPublished ? 'border-emerald-200' : 'border-slate-200'}`}
                    data-testid={`version-row-${v.status}`}
                  >
                    <div className="flex items-start justify-between gap-2 min-w-0">
                      <div className="min-w-0 flex-1">
                        <p className="font-semibold text-sm text-brand-navy truncate">
                          {v.versionName}
                        </p>
                        {v.created_at && (
                          <p className="text-[11px] text-slate-400 mt-0.5">
                            {t('timetableCreatedAtLabel')}{' '}
                            {new Date(v.created_at).toLocaleDateString(direction === 'rtl' ? 'ar-EG' : 'en-US')}
                          </p>
                        )}
                        {isPublished && v.published_at && (
                          <p className="text-[11px] text-emerald-600 mt-0.5">
                            {t('timetablePublishedAtLabel')}{' '}
                            {new Date(v.published_at).toLocaleDateString(direction === 'rtl' ? 'ar-EG' : 'en-US')}
                          </p>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-1 shrink-0">
                        {isPublished && (
                          <Badge className="bg-emerald-600 hover:bg-emerald-600 text-white text-[10px]" data-testid="published-badge">
                            {t('timetablePublishedBadge')}
                          </Badge>
                        )}
                        {isDraft && (
                          <Badge variant="outline" className="border-amber-400 text-amber-700 bg-amber-50 text-[10px]">
                            {t('timetableDraftBadge')}
                          </Badge>
                        )}
                        {isManual && (
                          <Badge variant="outline" className="border-slate-300 text-slate-600 bg-slate-50 text-[10px]">
                            {t('timetableManualBadge')}
                          </Badge>
                        )}
                      </div>
                    </div>
                    {isPublished && (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => handleUnpublish(v.id)}
                        disabled={unpublishing}
                        className="self-start border-amber-300 text-amber-700 hover:bg-amber-50 hover:text-amber-700 focus-visible:text-amber-700 h-7 text-xs gap-1"
                        data-testid="unpublish-timetable-btn"
                      >
                        {unpublishing ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <Unlock className="h-3 w-3" />
                        )}
                        {t('timetableUnpublish')}
                      </Button>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </SheetContent>
      </Sheet>

      </div>
    </Sidebar>
  );
}

// ─── Generation-blocked dialog ─────────────────────────────────────────────
// عند رفض المحرك للتوليد (HTTP 422 / GENERATION_BLOCKED) نعرض هنا قائمة
// المشاكل بالعربية مع زر يفتح الصفحة الأنسب لمعالجة كل مشكلة.
function BlockedGenerationDialog({ open, onOpenChange, report, onNavigate }) {
  const { t, language } = useTranslation();
  const { direction } = useTheme();
  const issues = Array.isArray(report?.issues) ? report.issues : [];
  const blockers  = issues.filter((i) => i.severity === 'blocker');
  const advisories = issues.filter((i) => i.severity === 'advisory');

  // اختر الإجراء الأساسي بناءً على أول blocker (أكثر إلحاحاً) أو الافتراضي.
  const primaryStep = (blockers[0] && ISSUE_NEXT_STEP[blockers[0].code]) || DEFAULT_NEXT_STEP;
  const messageOf = (iss) => (language === 'ar' ? (iss.message_ar || iss.message_en) : (iss.message_en || iss.message_ar));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent dir={direction} className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-red-700">
            <ShieldAlert className="h-5 w-5" />
            {t('generationBlockedTitle')}
          </DialogTitle>
          <DialogDescription>
            {t('generationBlockedDesc')}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 py-2 max-h-[55vh] overflow-y-auto pe-1">
          {issues.length === 0 ? (
            <p className="text-sm text-slate-500 text-center py-6">
              {t('noEngineDetailsAvailable')}
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
                                {t('blockerBadge')}
                              </Badge>
                              <span className="text-[11px] font-mono text-slate-500">
                                {iss.code}
                              </span>
                            </div>
                            <p className="text-sm text-red-900 leading-relaxed">
                              {messageOf(iss)}
                            </p>
                          </div>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            className="border-red-300 text-red-700 hover:bg-red-100 hover:text-red-700 focus-visible:text-red-700 shrink-0"
                            onClick={() => onNavigate(step.path)}
                          >
                            <Settings className="h-3.5 w-3.5 me-1" />
                            <span className="text-xs">{t(step.labelKey)}</span>
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
                    {t('additionalNotesNonBlocking')}
                  </p>
                  <ul className="space-y-2">
                    {advisories.map((iss, idx) => (
                      <li
                        key={`a-${iss.code}-${idx}`}
                        className="rounded-lg border border-amber-200 bg-amber-50 p-3"
                      >
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant="outline" className="border-amber-400 text-amber-800 bg-amber-100 text-[10px]">
                            {t('advisoryBadge')}
                          </Badge>
                          <span className="text-[11px] font-mono text-slate-500">
                            {iss.code}
                          </span>
                        </div>
                        <p className="text-sm text-amber-900 leading-relaxed">
                          {messageOf(iss)}
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
            {t('close')}
          </Button>
          <Button
            onClick={() => onNavigate(primaryStep.path)}
            className="bg-[#1C3D74] hover:bg-[#162f5a] text-white"
          >
            <ArrowLeft className="h-4 w-4 me-2" />
            {t(primaryStep.labelKey)}
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
function MasterMatrix({ teachers, cells, days, periods, dayLabelMap, onVacantClick, onUndoAbsence, onBulkCoverClick, onAcknowledgeRelocation, today, periodTimes = {}, unresolvedConflicts = [], viewMode = 'weekly', selectedDay = null, totalTeachers = null, canEdit = false, onEditSession, onCreateSession, onDragMove, enableCoverage = false, schoolId = null }) {
  const { t, language } = useTranslation();
  const [selectedSession, setSelectedSession] = useState(null);
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
      const localizedReason = language === 'en' ? (c.reason_en || c.reason_ar) : c.reason_ar;
      const tip = reason ? `${reason}: ${localizedReason || ''}` : (localizedReason || '');
      if (prev) m.set(k, prev + '\n' + tip);
      else m.set(k, tip);
    }
    return m;
  }, [unresolvedConflicts, language]);

  // وضع العرض: «يومي» يُقصر الأعمدة على اليوم المحدَّد فقط (أعمدة عريضة
  // قابلة للقراءة)، و«أسبوعي» يعرض كامل الأيام بأعمدة كثيفة وفقاً للسلوك
  // السابق. عند Daily بدون يوم محدَّد نسقط على أول يوم متاح ضماناً.
  const isDaily = viewMode === 'daily';
  const displayDays = computeDisplayDays(viewMode, selectedDay, days);

  // ترتيب الأعمدة: لكل يوم تُضاف أعمدة الحصص (1..7) متتالية.
  const totalDataCols = displayDays.length * periods.length;
  // Task #142 — daily mode is intentionally roomy: tall rows, wider
  // teacher column, prominent period sub-headers. Weekly mode keeps a
  // calmer rhythm with a real per-period minimum width so the grid
  // overflows horizontally (sticky teacher column + headers) instead of
  // squeezing every cell into illegible micro-text.
  const DAY_HEADER_HEIGHT = isDaily ? 40 : 36;
  const PERIOD_HEADER_HEIGHT = isDaily ? 44 : 38;
  const ROW_HEIGHT = isDaily ? 96 : 88;

  // Daily: ≤7 columns, `minmax(0, 1fr)` keeps the whole grid inside the
  //        container (no internal horizontal scroll) with a generously
  //        wide teacher column on the inline-start.
  // Weekly: 5 days × N periods often overflows on common laptop widths;
  //         we anchor each period at ≥76px so cells stay legible (≥11px
  //         text never collapses) and the grid scrolls horizontally
  //         inside its container.
  const gridTemplate = isDaily
    ? `clamp(220px, 22vw, 280px) repeat(${totalDataCols}, minmax(0, 1fr))`
    : `clamp(220px, 22vw, 280px) repeat(${totalDataCols}, minmax(84px, 1fr))`;
  const summaryCount = totalTeachers ?? teachers.length;

  // ظل أيسر خفيف لعمود المعلم المثبَّت (في RTL يقع على اليمين، فالظل يمتدّ
  // نحو اليسار داخل منطقة التمرير).
  const teacherStickyShadow = 'shadow-[-2px_0_5px_rgba(0,0,0,0.02)]';

  // ── Drag-and-drop wiring (draft only) ─────────────────────────────
  // Sensors live here so click-to-edit (PointerSensor.distance = 6) and
  // keyboard fallback both keep working. The DndContext is only mounted
  // when the page passed both `canEdit` and `onDragMove`; on the
  // published view the matrix renders without any DnD scaffolding.
  const dndEnabled = !!(canEdit && onDragMove);
  const dragSensors = useDragSensors();
  const handleDragEnd = (event) => {
    const src = event?.active?.data?.current;
    const dst = event?.over?.data?.current;
    if (!src || !dst || src.kind !== 'session' || dst.kind !== 'slot') return;
    if (!src.session_id) return;
    // Same (day, period) drop is a no-op for the backend `move` API
    // (which only keys on day + period, not teacher row). Dropping the
    // session onto a different teacher row at the same day/period would
    // therefore round-trip to the server with no real change, so we
    // silently ignore it here. Reassigning a teacher is a separate flow
    // handled by the edit drawer, not by drag-and-drop.
    if (src.day_of_week === dst.day_of_week
        && src.period_number === dst.period_number) return;
    onDragMove?.({
      sessionId: src.session_id,
      sourceTeacherId: src.teacher_id,
      sourceDay: src.day_of_week,
      sourcePeriod: src.period_number,
      targetTeacherId: dst.teacher_id,
      targetDay: dst.day_of_week,
      targetPeriod: dst.period_number,
      targetSessionId: dst.session_id || null,
    });
  };

  const matrix = (
    <div
      data-testid={`master-matrix-${isDaily ? 'daily' : 'weekly'}`}
      className="grid text-[11px] w-full"
      style={{
        gridTemplateColumns: gridTemplate,
        // Explicit header tracks + body row floor. Without this, the
        // first body row's CSS-grid auto track could collapse below
        // ROW_HEIGHT (clipping the first teacher row under the sticky
        // period header) when its lesson cells had no sessions and the
        // per-item `minHeight: ROW_HEIGHT` contract was not enough to
        // grow the implicit track. `grid-auto-rows: minmax(ROW_HEIGHT,
        // auto)` enforces the floor at the container level so row 1
        // cannot structurally diverge from row N. The two explicit
        // header rows keep using their existing fixed heights.
        gridTemplateRows: `${DAY_HEADER_HEIGHT}px ${PERIOD_HEADER_HEIGHT}px`,
        gridAutoRows: `minmax(${ROW_HEIGHT}px, auto)`,
      }}
    >
      {/* ── Sticky header row 1: day spans ─────────────────────── */}
      {/* الزاوية العلوية الجانبية (تقاطع رأس + عمود المعلم) — أعلى z-index */}
      <div
        data-testid="master-matrix-corner"
        className={`sticky bg-slate-50 text-slate-700 text-xs font-semibold flex items-center justify-center border-b border-l border-slate-200 rounded-ts-2xl ${teacherStickyShadow}`}
        style={{
          // Both view modes use the matrix container as their scroll parent
          // (not the page), so the corner header sticks at top:0 of the
          // container in daily and weekly alike.
          top: 0,
          insetInlineStart: 0, zIndex: 30, height: DAY_HEADER_HEIGHT,
        }}
      >
        {t('teacherColHeader')}
      </div>
      {displayDays.map((dayKey, dayIdx) => (
        <div
          key={`day-h-${dayKey}`}
          data-testid={`master-matrix-day-band-${dayKey}`}
          className={`sticky z-20 ${getDayBandClass(dayKey)} ${getDayTextOnBand(dayKey)} text-sm font-cairo font-bold text-center flex items-center justify-center tracking-wide ${dayIdx > 0 ? 'border-s-2 border-s-white/70' : ''} ${dayIdx === displayDays.length - 1 ? 'rounded-te-2xl' : ''} shadow-[inset_0_1px_0_rgba(255,255,255,0.35),inset_0_-2px_0_rgba(0,0,0,0.12),0_1px_2px_rgba(15,42,75,0.08)]`}
          style={{ top: 0, gridColumn: `span ${periods.length}`, height: DAY_HEADER_HEIGHT }}
        >
          {dayLabelMap[dayKey] || dayKey}
          {dayKey === today && (
            <span className="ms-2 inline-block px-1.5 py-0 text-[10px] rounded bg-white/30 text-white">
              {t('todayBadge')}
            </span>
          )}
        </div>
      ))}

      {/* ── Sticky header row 2: period numbers ────────────────── */}
      <div
        className={`sticky bg-slate-50 text-slate-500 text-[10px] font-medium px-2 flex items-center justify-end border-b border-l border-slate-200 ${teacherStickyShadow}`}
        style={{
          top: `${DAY_HEADER_HEIGHT}px`,
          insetInlineStart: 0, zIndex: 30, height: PERIOD_HEADER_HEIGHT,
        }}
      >
        {t('teachersCountSummary', { count: summaryCount, periods: periods.length, days: days.length })}
      </div>
      {displayDays.map((dayKey, dayIdx) => (
        periods.map((p, pIdx) => {
          const slot = periodTimes?.[String(p)];
          const timeLabel = slot && (slot.start || slot.end)
            ? `${slot.start || ''}${slot.start && slot.end ? ' – ' : ''}${slot.end || ''}`
            : '';
          const isDayStart = !isDaily && dayIdx > 0 && pIdx === 0;
          return (
            <div
              key={`ph-${dayKey}-${p}`}
              data-testid={`master-matrix-period-head-${dayKey}-${p}`}
              className={`sticky z-20 ${getDayTintClass(dayKey)} text-brand-navy/90 text-center flex flex-col items-center justify-center leading-tight border-b border-white/70 border-l border-l-white/60 shadow-[inset_0_1px_0_rgba(255,255,255,0.6),inset_0_-1px_0_rgba(15,42,75,0.05)] ${isDayStart ? 'border-s-2 border-s-slate-300/70' : ''}`}
              style={{
                top: `${DAY_HEADER_HEIGHT}px`,
                height: PERIOD_HEADER_HEIGHT,
              }}
              title={timeLabel ? t('periodLabelWithTime', { num: p, time: timeLabel }) : t('periodLabelShort', { num: p })}
            >
              <span className={`${isDaily ? 'text-sm' : 'text-[12px]'} font-bold tabular-nums`}>{p}</span>
              {timeLabel && (
                <span className={`${isDaily ? 'text-[10px]' : 'text-[9px]'} text-brand-navy/60 tabular-nums`}>{timeLabel}</span>
              )}
            </div>
          );
        })
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
              data-testid={`master-matrix-teacher-${teacher.id}`}
              className={`sticky z-10 ${isDaily ? 'px-4 py-3' : 'px-3 py-2'} border-b border-l border-slate-200 ${rowBg} ${teacherStickyShadow} transition-colors hover:bg-slate-50/60`}
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
                    title={t('restorePresenceTooltip')}
                    aria-label={t('cancelAbsenceForName', { name: teacher.full_name })}
                    className="inline-flex items-center gap-1 text-[10px] font-semibold rounded border border-emerald-400 text-emerald-700 bg-emerald-50 hover:bg-emerald-100 transition-colors px-1.5 py-0.5 cursor-pointer self-start"
                  >
                    <Undo2 className="h-3 w-3" aria-hidden="true" />
                    <span>{t('cancelAbsenceShortLabel')}</span>
                  </button>
                  {vacantTodayCount > 0 && onBulkCoverClick && (
                    <Button
                      type="button"
                      size="sm"
                      onClick={() => onBulkCoverClick(teacher)}
                      className="w-full h-6 text-[10px] font-bold bg-gradient-to-r from-brand-navy to-brand-turquoise hover:brightness-110 text-white shadow-sm px-2"
                      title={t('openBulkCoverPanelTooltip')}
                    >
                      <Layers className="h-3 w-3 me-1" strokeWidth={1.5} aria-hidden="true" />
                      {t('coverWithCount', { count: vacantTodayCount })}
                    </Button>
                  )}
                </div>
              )}
            </div>

            {/* Cells: per day, per period */}
            {displayDays.map((dayKey, dayIdx) => (
              periods.map((p, pIdx) => {
                const rawCell = teacherCells[dayKey]?.[String(p)] || null;
                // ── Cascade الغياب → شاغرة ───────────────────────────────
                // الـbackend عادةً يرفع is_vacant عند تسجيل الغياب، لكن
                // نضيف هنا شبكة أمان: إذا كان المعلم غائباً اليوم وله حصة
                // معبَّأة في يوم الـtoday بدون علم is_vacant ولا بديل
                // مُسنَد، فإنّ الخانة فعلياً شاغرة وننبّه عليها بصرياً
                // ونفعِّل النقر عليها لفتح درج المرشحين.
                const cell = (
                  rawCell &&
                  teacher.is_absent_today &&
                  dayKey === today &&
                  !rawCell.is_vacant &&
                  !rawCell.is_substituted &&
                  !rawCell.is_substitute
                ) ? { ...rawCell, is_vacant: true } : rawCell;
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
                const handleNormalClick = (sessionData) => {
                  setSelectedSession({
                    ...sessionData,
                    teacher_id: sessionData?.teacher_id || teacher.id,
                    teacher_name: sessionData?.teacher_name || teacher.full_name,
                    day_of_week: sessionData?.day_of_week || dayKey,
                    slot_number: p,
                    period_number: sessionData?.period_number || p,
                    teacher_specialty: teacher.subject || '',
                    teacher_avatar_url: teacher.avatar_url,
                    start_time: periodTimes?.[String(p)]?.start,
                    end_time: periodTimes?.[String(p)]?.end,
                  });
                };
                const isDayStart = !isDaily && dayIdx > 0 && pIdx === 0;
                const subjectBarColor = cell && !cell.is_vacant
                  ? (cell.subject_color || '#1C3D74')
                  : null;
                // Drag-and-drop only on draft cells. A "normal" filled cell
                // (not vacant, not substituted, not relocated, not locked,
                // and carrying a real session id) is the draggable surface.
                // Every cell — filled or empty — is a droppable target so the
                // engine can land a swap or a move respectively.
                const isNormalFilled = !!cell && !cell.is_vacant && !cell.is_substituted
                  && !cell.is_substitute && !cell.is_relocated && !cell.is_locked;
                const cellSessionId = cell?.session_id || cell?.id || null;
                const dndEnabled = !!(canEdit && onDragMove);
                const slotId = `slot:${teacher.id}:${dayKey}:${p}`;
                const slotPayload = {
                  kind: 'slot',
                  teacher_id: teacher.id,
                  day_of_week: dayKey,
                  period_number: p,
                  session_id: cellSessionId,
                  is_normal_filled: isNormalFilled,
                };
                const inner = cell ? (
                  <FilledCell
                    cell={cell}
                    dayKey={dayKey}
                    compact={!isDaily}
                    onClick={cell.is_vacant ? () => onVacantClick(cellData) : handleNormalClick}
                    onAcknowledgeRelocation={onAcknowledgeRelocation}
                  />
                ) : (
                  <EmptyCell
                    onClick={canEdit && onCreateSession
                      ? () => onCreateSession({
                          teacher_id: teacher.id,
                          day_of_week: dayKey,
                          period_number: p,
                        })
                      : null}
                    addLabel={t('addLessonHere')}
                  />
                );
                const innerWithDrag = (dndEnabled && isNormalFilled && cellSessionId) ? (
                  <DraggableSession
                    id={`session:${cellSessionId}`}
                    payload={{
                      kind: 'session',
                      session_id: cellSessionId,
                      teacher_id: teacher.id,
                      day_of_week: dayKey,
                      period_number: p,
                    }}
                  >
                    {inner}
                  </DraggableSession>
                ) : inner;
                return (
                  <div
                    key={`${teacher.id}-${dayKey}-${p}`}
                    data-testid={`master-matrix-cell-${teacher.id}-${dayKey}-${p}`}
                    // `flex` here is critical for the row-height contract:
                    // CSS-grid stretches this wrapper to the row track, but
                    // the inner SessionCell / FilledCell / EmptyCell uses
                    // `h-full` (height: 100%). A percentage height inside a
                    // grid item whose own `height` is `auto` (only
                    // `minHeight` set) resolves to `auto` in browsers, so
                    // the colored cell collapses to its content height
                    // (~60px) inside an 88px row — exactly the symptom in
                    // the bug screenshot. Switching the wrapper to a flex
                    // container makes the child stretch via flex's
                    // cross-axis (no percentage resolution required), so
                    // the day-tinted cell, the empty-cell button, and the
                    // DnD ring all fill the row faithfully.
                    // `[&>*]:flex-1 [&>*]:min-w-0` forces the immediate
                    // child (DroppableSlot when DnD is on, otherwise the
                    // FilledCell/SessionCell/EmptyCell itself) to grow on
                    // the flex main-axis (width). Cross-axis (height) is
                    // already handled by flex's default `align-items:
                    // stretch`. Together with the wrapper's `minHeight`
                    // this guarantees the colored cell fully fills its
                    // grid track regardless of whether SessionCell
                    // happens to set `w-full` itself.
                    className={`min-w-0 flex [&>*]:flex-1 [&>*]:min-w-0 border-b border-l border-slate-100 p-0.5 ${conflictBg} ${isDayStart ? 'border-s-2 border-s-slate-300/70' : ''}`}
                    style={{
                      // Single row-height contract: the teacher (first column)
                      // cell uses `minHeight: ROW_HEIGHT` so absence buttons /
                      // long subject text can grow the track. Lesson cells
                      // share the same minHeight and rely on CSS grid's
                      // default `align-items: stretch` to match the actual
                      // track height. Using a fixed `height` here would cap
                      // the lesson cell at 88px even when the teacher cell
                      // pushes the row taller, which manifests as the first
                      // visible row appearing shorter than the row below
                      // and the teacher name being vertically clipped.
                      minHeight: ROW_HEIGHT,
                      ...(subjectBarColor ? {
                        borderInlineStartWidth: '3px',
                        borderInlineStartStyle: 'solid',
                        borderInlineStartColor: subjectBarColor,
                      } : {}),
                    }}
                    title={conflictTip || undefined}
                  >
                    {dndEnabled ? (
                      <DroppableSlot id={slotId} payload={slotPayload}>
                        {innerWithDrag}
                      </DroppableSlot>
                    ) : innerWithDrag}
                  </div>
                );
              })
            ))}
          </React.Fragment>
        );
      })}
      <SessionDetailModal
        open={!!selectedSession}
        session={selectedSession}
        onClose={() => setSelectedSession(null)}
        hideActions={!canEdit}
        enableCoverage={enableCoverage}
        schoolId={schoolId}
        onEdit={canEdit ? (s) => {
          setSelectedSession(null);
          onEditSession?.({ session: s, mode: 'edit' });
        } : undefined}
        onMove={canEdit ? (s) => {
          // "Move" reuses the same drawer as Edit — the teacher/day/period
          // selectors are the move surface. Keeping the affordance as a
          // separate button matches the modal's existing UX vocabulary.
          setSelectedSession(null);
          onEditSession?.({ session: s, mode: 'edit' });
        } : undefined}
      />
    </div>
  );

  // Mount DndContext only on draft+editable matrices; the published view
  // renders identical markup without the DnD scaffolding so the existing
  // MasterMatrix layout tests keep passing untouched.
  return dndEnabled ? (
    <DndContext sensors={dragSensors} onDragEnd={handleDragEnd}>
      {matrix}
    </DndContext>
  ) : matrix;
}
