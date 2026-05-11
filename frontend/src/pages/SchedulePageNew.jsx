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
import { Sidebar } from '../components/layout/Sidebar';
import { useAuth } from '../contexts/AuthContext';
import { useTheme, useTranslation } from '../contexts/ThemeContext';
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
  Scale, Hourglass, UserMinus, AlertOctagon, AlertTriangle,
  ShieldAlert, Settings, ArrowLeft,
  Undo2, Layers, Lightbulb, X, ExternalLink, CheckCircle2,
} from 'lucide-react';
import CandidatesSidePanel from '../components/schedule/CandidatesSidePanel';
import BulkSubstitutionPanel from '../components/schedule/BulkSubstitutionPanel';
import ScheduleTabNav from '../components/schedule/ScheduleTabNav';
import ScheduleSettingsTabContent from '../components/schedule/ScheduleSettingsTabContent';
import FilledCell from '../components/schedule/FilledCell';
import SessionEditDrawer from '../components/schedule/SessionEditDrawer';
import { SessionDetailModal, getDayBandClass, getDayTintClass, getDayTextOnBand } from '../components/schedule/grid-theme';
import { computeDisplayDays } from '../components/schedule/grid-helpers';
import { StandbyRosterContent } from './StandbyRosterPage';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import { getPose } from '../components/hakim/hakimPoses';
import { MASTER_GRID_TEACHER_WINDOW } from '../config/scheduleConfig';

// ─── Infeasibility issue → contextual next step ────────────────────────────
// كل كود INF يحدد الصفحة الأنسب التي تحل المشكلة. عند غياب الكود نوجِّه إلى
// إعدادات المدرسة العامة كملاذ افتراضي.
const ISSUE_NEXT_STEP = {
  'INF-01': { labelKey: 'openAcademicSettings', path: '/school/settings?section=academic' },
  'INF-02': { labelKey: 'openAcademicSettings', path: '/school/settings?section=academic' },
  'INF-03': { labelKey: 'openTeachersAssignments',  path: '/school/teachers' },
  'INF-04': { labelKey: 'openRoomsSettings',           path: '/school/schedule?tab=settings&sub=timings' },
  'INF-05': { labelKey: 'openSchoolDaySettings',     path: '/school/schedule?tab=settings&sub=timings' },
};
const DEFAULT_NEXT_STEP = { labelKey: 'openScheduleSettings', path: '/school/schedule?tab=settings' };

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
    <div className={`bg-white shadow-sm rounded-lg border border-slate-200 border-s-4 ${accent.topBorder.replace('border-t-', 'border-s-')} flex items-center gap-2.5 px-3 py-2 min-w-0`}>
      <div className={`h-8 w-8 rounded-md flex items-center justify-center shrink-0 ${accent.iconBg}`}>
        <Icon className={`h-4 w-4 ${accent.iconText}`} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[10px] font-medium text-slate-500 leading-tight truncate">{label}</p>
        <div className="flex items-baseline gap-1 leading-tight">
          <span className={`text-lg font-bold ${accent.valueText}`}>{value}</span>
          {suffix && <span className="text-[10px] text-slate-400">{suffix}</span>}
        </div>
      </div>
    </div>
  );
}

// ─── Master matrix structural skeleton (Task #142) ─────────────────────────
// يحلّ محل المنبثق المركزي القديم (Loader2) داخل حاوية المصفوفة. يرسم
// شبكة هيكلية بنفس عدد صفوف الصفحة (`pageSize`) وعدد الأعمدة المطابق
// لوضع العرض الحالي، فيبقى المستخدم على نفس الخريطة البصرية أثناء
// التحميل بدلاً من أن يرى دوّاراً وسط منطقة فارغة.
function MasterMatrixSkeleton({ rows = 10, days = 5, periods = 7, isDaily = false }) {
  const { t } = useTranslation();
  const totalDataCols = Math.max(1, days * periods);
  const teacherCol = isDaily
    ? 'clamp(220px, 22vw, 280px)'
    : 'clamp(160px, 14vw, 200px)';
  const dataCol = isDaily ? 'minmax(0, 1fr)' : 'minmax(76px, 1fr)';
  const gridTemplate = `${teacherCol} repeat(${totalDataCols}, ${dataCol})`;
  const rowH = isDaily ? 96 : 88;
  const dayBandH = 36;
  const periodHeadH = isDaily ? 44 : 38;

  return (
    <div
      data-testid="master-matrix-skeleton"
      role="status"
      aria-label={t('preparingMatrixAria')}
      className="grid w-full text-[11px] animate-in fade-in-0 duration-200"
      style={{ gridTemplateColumns: gridTemplate }}
    >
      {/* Day-band header row */}
      <div
        className="sticky bg-slate-100 border-b border-slate-200 z-30"
        style={{ top: 'var(--sticky-band-h, 88px)', insetInlineStart: 0, height: dayBandH }}
      />
      {Array.from({ length: days }).map((_, d) => (
        <div
          key={`sk-day-${d}`}
          className={`bg-slate-200/70 border-b border-white/40 animate-pulse ${d > 0 ? 'border-s-2 border-s-slate-300/70' : ''}`}
          style={{ gridColumn: `span ${periods}`, height: dayBandH }}
        />
      ))}
      {/* Period sub-header row */}
      <div
        className="bg-slate-50 border-b border-slate-200"
        style={{ height: periodHeadH }}
      />
      {Array.from({ length: totalDataCols }).map((_, i) => {
        const isDayStart = !isDaily && i % periods === 0 && i > 0;
        return (
          <div
            key={`sk-ph-${i}`}
            className={`bg-slate-100/80 border-b border-l border-slate-100 animate-pulse ${isDayStart ? 'border-s-2 border-s-slate-300/70' : ''}`}
            style={{ height: periodHeadH }}
          />
        );
      })}
      {/* Body rows */}
      {Array.from({ length: rows }).map((_, r) => (
        <React.Fragment key={`sk-row-${r}`}>
          <div
            className="px-3 py-2 border-b border-l border-slate-200 bg-white flex flex-col justify-center gap-1.5"
            style={{ minHeight: rowH }}
          >
            <div className="h-3 w-28 bg-slate-200 rounded animate-pulse" />
            <div className="h-2 w-20 bg-slate-100 rounded animate-pulse" />
          </div>
          {Array.from({ length: totalDataCols }).map((_, c) => {
            const isDayStart = !isDaily && c % periods === 0 && c > 0;
            return (
              <div
                key={`sk-cell-${r}-${c}`}
                className={`border-b border-l border-slate-100 p-1 ${isDayStart ? 'border-s-2 border-s-slate-300/70' : ''}`}
                style={{ height: rowH }}
              >
                <div
                  className="h-full w-full rounded-md bg-slate-100/80 animate-pulse"
                  style={{ animationDelay: `${(r * 31 + c * 17) % 600}ms` }}
                />
              </div>
            );
          })}
        </React.Fragment>
      ))}
    </div>
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
        className="w-full h-full bg-slate-50/40 border-b border-dashed border-slate-200/60 hover:bg-emerald-50/60 hover:border-emerald-300 transition-colors flex items-center justify-center text-slate-300 hover:text-emerald-600 group"
        data-testid="master-matrix-empty-cell-add"
      >
        <span className="opacity-0 group-hover:opacity-100 text-lg leading-none transition-opacity">+</span>
      </button>
    );
  }
  return (
    <div className="w-full h-full bg-slate-50/40 border-b border-dashed border-slate-200/60" />
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
function HakimGeneratingOverlay() {
  const { t } = useTranslation();
  const [stageIdx, setStageIdx] = useState(0);

  useEffect(() => {
    if (stageIdx >= HAKIM_STAGES.length - 1) return;
    const ms = HAKIM_STAGES[stageIdx].minMs;
    const id = setTimeout(() => setStageIdx((i) => Math.min(i + 1, HAKIM_STAGES.length - 1)), ms);
    return () => clearTimeout(id);
  }, [stageIdx]);

  const stage = HAKIM_STAGES[stageIdx];
  const poseSrc = getPose(stage.poseKey);
  const total = HAKIM_STAGES.length;
  const progressPct = Math.round(((stageIdx + 1) / total) * 100);

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
// `/school/schedule?tab=settings&sub=<tab>` الذي تُحسن الصفحة قراءته.

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
        className="shrink-0 border-orange-300 text-orange-800 hover:bg-orange-100 bg-white/70"
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
  const schoolId = user?.tenant_id;
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

  const loadGrid = useCallback(async (viewOverride, paginationOverride) => {
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
    // Task #142 — every refetch swaps the matrix region to the
    // structural skeleton while keeping page chrome (header, KPI strip,
    // view-mode toggle, day-tabs row) mounted. The skeleton matches
    // the current view-mode/day-count via grid?.days?.length and the
    // active pageSize, so the operator never sees the chrome flash or
    // the matrix collapse to a centered spinner.
    setLoading(true);
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
      const response = await api.get('/schedule/master-grid', {
        params,
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

  const handleAutoGenerate = useCallback(async () => {
    if (!schoolId) {
      nassaqError(t('cannotDetermineSchool'));
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
    }
  }, [api, schoolId, generating, loadGrid, nassaqError, nassaqWarning, t]);

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
            const lines = violations.slice(0, 8).map((v) => {
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

  const [selectedDay, setSelectedDay] = useState(null);

  // Sync selectedDay with available days when grid loads / changes.
  // Falls back to today, then to the first available day.
  useEffect(() => {
    if (!days?.length) return;
    setSelectedDay((cur) => {
      if (cur && days.includes(cur)) return cur;
      if (todayKey && days.includes(todayKey)) return todayKey;
      return days[0];
    });
  }, [days, todayKey]);

  // Mirror current view/day into a ref so loadGrid's stable callback
  // can read it without re-creating on every render. The single window
  // size is constant across the session.
  const paginationStateRef = useRef({
    pageIndex: 0,
    pageSize: MASTER_GRID_TEACHER_WINDOW,
    day: null,
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
    return (
      <Sidebar>
        <div
          dir={direction}
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
          dir={direction}
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
                  {t('settingsScheduleTitle')}
                </h1>
                <p className="text-sm text-slate-500 mt-1">
                  {t('settingsScheduleSubtitle')}
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
        dir={direction}
        data-master-schedule-root
        className="flex flex-col min-h-[100dvh] bg-slate-50 text-slate-900"
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
            // Pull the fresh draft so the matrix mirrors the mutation.
            // No need to clear conflicts here — the drawer already did.
            loadGrid('draft');
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
          className="sticky top-0 z-40 bg-white/95 backdrop-blur border-b border-slate-200"
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
                      ? 'bg-[#1C3D74] text-white shadow-sm'
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
                      ? 'bg-[#1C3D74] text-white shadow-sm'
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
                className="border-slate-300 text-slate-700 hover:bg-slate-100 h-8 px-2.5"
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
              className="flex flex-wrap items-center gap-2 px-4 md:px-6 pb-2"
            >
              <div
                role="tablist"
                aria-label={t('selectDayLabel')}
                className={`inline-flex flex-wrap gap-1 rounded-lg border border-slate-200 bg-white p-0.5 shadow-sm ${loading ? 'opacity-70' : ''}`}
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
                          ? 'bg-[#2BB5A0] text-white shadow-sm'
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
        <div className="relative" data-testid="master-matrix-region">
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
          className={`relative bg-white border-t border-slate-200 ${
            viewMode === 'weekly' ? 'overflow-x-auto overflow-y-visible' : 'overflow-visible'
          }`}
        >
          {loading ? (
            <MasterMatrixSkeleton
              rows={Math.min(MASTER_GRID_TEACHER_WINDOW, totalTeachersAll || 12)}
              days={viewMode === 'daily' ? 1 : ((grid?.days?.length) || days.length || 5)}
              periods={(grid?.periods?.length) || 7}
              isDaily={viewMode === 'daily'}
            />
          ) : error ? (
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
                {scheduleView === 'published' && (
                  <Button
                    onClick={() => setScheduleView('draft')}
                    variant="outline"
                    className="border-amber-300 text-amber-700 hover:bg-amber-50"
                    data-testid="empty-state-switch-draft-btn"
                  >
                    {t('switchToDraftView')}
                  </Button>
                )}
                {scheduleView === 'draft' && (
                  <Button
                    onClick={() => setScheduleView('published')}
                    variant="outline"
                    className="border-emerald-300 text-emerald-700 hover:bg-emerald-50"
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
            />
          )}

          {/* ── Hakeem-branded loading overlay ────────────────────────
              يظهر فقط أثناء التوليد التلقائي. يستخدم تعبير "ai-thinking"
              من معرض حكيم مع نبضة ضوئية بنفسجية لتأكيد أن المحرك يقرأ
              القيود ويبني الجدول الذكي. */}
          {generating && <HakimGeneratingOverlay />}
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
                            className="border-red-300 text-red-700 hover:bg-red-100 shrink-0"
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
function MasterMatrix({ teachers, cells, days, periods, dayLabelMap, onVacantClick, onUndoAbsence, onBulkCoverClick, onAcknowledgeRelocation, today, periodTimes = {}, unresolvedConflicts = [], viewMode = 'weekly', selectedDay = null, totalTeachers = null, canEdit = false, onEditSession, onCreateSession }) {
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

  return (
    <div
      data-testid={`master-matrix-${isDaily ? 'daily' : 'weekly'}`}
      className="grid text-[11px] w-full"
      style={{ gridTemplateColumns: gridTemplate }}
    >
      {/* ── Sticky header row 1: day spans ─────────────────────── */}
      {/* الزاوية العلوية الجانبية (تقاطع رأس + عمود المعلم) — أعلى z-index */}
      <div
        data-testid="master-matrix-corner"
        className={`sticky bg-slate-50 text-slate-700 text-xs font-semibold flex items-center justify-center border-b border-l border-slate-200 ${teacherStickyShadow}`}
        style={{ top: 'var(--sticky-band-h, 88px)', insetInlineStart: 0, zIndex: 30, height: DAY_HEADER_HEIGHT }}
      >
        {t('teacherColHeader')}
      </div>
      {displayDays.map((dayKey, dayIdx) => (
        <div
          key={`day-h-${dayKey}`}
          data-testid={`master-matrix-day-band-${dayKey}`}
          className={`sticky z-20 ${getDayBandClass(dayKey)} ${getDayTextOnBand(dayKey)} text-sm font-cairo font-bold text-center flex items-center justify-center tracking-wide ${dayIdx > 0 ? 'border-s-2 border-s-white/70' : ''} shadow-[inset_0_-1px_0_rgba(255,255,255,0.25)]`}
          style={{ top: 'var(--sticky-band-h, 88px)', gridColumn: `span ${periods.length}`, height: DAY_HEADER_HEIGHT }}
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
        style={{ top: `calc(var(--sticky-band-h, 88px) + ${DAY_HEADER_HEIGHT}px)`, insetInlineStart: 0, zIndex: 30, height: PERIOD_HEADER_HEIGHT }}
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
              className={`sticky z-20 ${getDayTintClass(dayKey)} text-brand-navy/85 text-center flex flex-col items-center justify-center leading-tight border-b border-white/40 border-l border-l-white/40 ${isDayStart ? 'border-s-2 border-s-slate-300/70' : ''}`}
              style={{ top: `calc(var(--sticky-band-h, 88px) + ${DAY_HEADER_HEIGHT}px)`, height: PERIOD_HEADER_HEIGHT }}
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
              className={`sticky z-10 ${isDaily ? 'px-4 py-3' : 'px-3 py-2'} border-b border-l border-slate-200 ${rowBg} ${teacherStickyShadow}`}
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
                      className="w-full h-6 text-[10px] font-bold bg-gradient-to-r from-[#1C3D74] to-[#2BB5A0] hover:from-[#152d57] text-white shadow-sm px-2"
                      title={t('openBulkCoverPanelTooltip')}
                    >
                      <Layers className="h-3 w-3 me-1" />
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
                    day_of_week: dayKey,
                    slot_number: p,
                    teacher_name: teacher.full_name,
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
                return (
                  <div
                    key={`${teacher.id}-${dayKey}-${p}`}
                    className={`min-w-0 border-b border-l border-slate-100 p-0.5 ${conflictBg} ${isDayStart ? 'border-s-2 border-s-slate-300/70' : ''}`}
                    style={{
                      height: ROW_HEIGHT,
                      ...(subjectBarColor ? {
                        borderInlineStartWidth: '3px',
                        borderInlineStartStyle: 'solid',
                        borderInlineStartColor: subjectBarColor,
                      } : {}),
                    }}
                    title={conflictTip || undefined}
                  >
                    {cell ? (
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
                    )}
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
}
