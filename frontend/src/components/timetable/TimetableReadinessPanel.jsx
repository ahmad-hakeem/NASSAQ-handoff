import React, { useState } from 'react';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Progress } from '../../components/ui/progress';
import {
  CheckCircle2, AlertTriangle, XCircle, ChevronDown, ChevronUp,
  ArrowUpRight, RefreshCw, Loader2, Lock, Sparkles, Shield, Zap,
  ClipboardList
} from 'lucide-react';
import { ReadinessStatus } from './types';

const PHASE_META = {
  time_structure:         { num: 1, label: 'الهيكل الزمني' },
  academic_entities:      { num: 2, label: 'الكيانات' },
  teaching_staff:         { num: 3, label: 'المعلمون' },
  teaching_relationships: { num: 4, label: 'الربط' },
  constraints:            { num: 5, label: 'القيود' },
  generation_ready:       { num: 6, label: 'الإنشاء' },
};

const statusConfig = (status) => {
  switch (status) {
    case ReadinessStatus.FULLY_READY:
      return {
        accent: 'emerald',
        gradient: 'from-emerald-500 to-teal-500',
        bgLight: 'bg-emerald-50 dark:bg-emerald-950/20',
        borderColor: 'border-emerald-200 dark:border-emerald-800/40',
        textColor: 'text-emerald-700 dark:text-emerald-300',
        label: 'جاهز للإنشاء',
        icon: <Sparkles className="h-4 w-4" />,
        ringStroke: '#10b981',
      };
    case ReadinessStatus.PARTIALLY_READY:
      return {
        accent: 'amber',
        gradient: 'from-amber-500 to-orange-500',
        bgLight: 'bg-amber-50 dark:bg-amber-950/20',
        borderColor: 'border-amber-200 dark:border-amber-800/40',
        textColor: 'text-amber-700 dark:text-amber-300',
        label: 'جاهز جزئياً',
        icon: <Shield className="h-4 w-4" />,
        ringStroke: '#f59e0b',
      };
    default:
      return {
        accent: 'red',
        gradient: 'from-red-500 to-rose-500',
        bgLight: 'bg-red-50 dark:bg-red-950/20',
        borderColor: 'border-red-200 dark:border-red-800/40',
        textColor: 'text-red-700 dark:text-red-300',
        label: 'غير جاهز',
        icon: <Zap className="h-4 w-4" />,
        ringStroke: '#ef4444',
      };
  }
};

const phaseStatusStyle = (status) => {
  switch (status) {
    case 'complete': return { bg: 'bg-emerald-50 dark:bg-emerald-950/30', border: 'border-emerald-200/70 dark:border-emerald-800/40', badge: 'مكتمل', badgeCls: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300', barColor: 'bg-emerald-500' };
    case 'partial': return { bg: 'bg-amber-50 dark:bg-amber-950/30', border: 'border-amber-200/70 dark:border-amber-800/40', badge: 'جزئي', badgeCls: 'bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300', barColor: 'bg-amber-500' };
    case 'blocked': return { bg: 'bg-gray-50 dark:bg-gray-900/30', border: 'border-gray-200/70 dark:border-gray-700/40', badge: 'محظور', badgeCls: 'bg-gray-100 text-gray-600 dark:bg-gray-800/50 dark:text-gray-400', barColor: 'bg-gray-300' };
    case 'not_started': return { bg: 'bg-red-50/50 dark:bg-red-950/20', border: 'border-red-200/70 dark:border-red-800/40', badge: 'غير مكتمل', badgeCls: 'bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300', barColor: 'bg-red-400' };
    default: return { bg: 'bg-gray-50 dark:bg-gray-900/30', border: 'border-gray-200/70 dark:border-gray-700/40', badge: '—', badgeCls: 'bg-gray-100 text-gray-500', barColor: 'bg-gray-300' };
  }
};

const PhaseRow = ({ phaseKey, phase, onFix }) => {
  const [open, setOpen] = useState(false);
  const meta = PHASE_META[phaseKey] || { num: 0, label: phaseKey };
  const s = phaseStatusStyle(phase.status);
  const issues = phase.issues || [];
  const pct = phase.max_score > 0 ? Math.round((phase.score / phase.max_score) * 100) : 0;
  const isBlocked = phase.status === 'blocked';

  return (
    <div className={`rounded-xl border ${s.border} ${s.bg} transition-all ${isBlocked ? 'opacity-50' : ''}`}>
      <button
        onClick={() => !isBlocked && setOpen(!open)}
        className={`w-full flex items-center justify-between p-3.5 text-right gap-3 ${isBlocked ? 'cursor-not-allowed' : 'cursor-pointer'}`}
        disabled={isBlocked}
      >
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold flex-shrink-0 ${
            phase.status === 'complete' ? 'bg-emerald-500 text-white' :
            phase.status === 'partial' ? 'bg-amber-500 text-white' :
            phase.status === 'not_started' ? 'bg-red-100 text-red-600 dark:bg-red-900/40 dark:text-red-400' :
            'bg-gray-100 text-gray-400 dark:bg-gray-800 dark:text-gray-500'
          }`}>
            {phase.status === 'complete' ? <CheckCircle2 className="h-4 w-4" /> : meta.num}
          </div>
          <div className="min-w-0 flex-1">
            <p className="font-semibold text-[15px] font-cairo truncate">{phase.name_ar}</p>
          </div>
        </div>
        <div className="flex items-center gap-2.5 flex-shrink-0">
          <div className="flex items-center gap-2 min-w-[4.5rem] justify-end">
            <div className="w-14 h-2 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
              <div className={`h-full rounded-full transition-all duration-500 ${s.barColor}`} style={{ width: `${pct}%` }} />
            </div>
            <span className="text-sm font-bold tabular-nums text-foreground/70 w-8 text-end">{pct}%</span>
          </div>
          {!isBlocked && (
            open ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
          {isBlocked && <Lock className="h-4 w-4 text-gray-400" />}
        </div>
      </button>

      {open && (
        <div className="px-3 pb-3 space-y-1.5">
          {issues.length > 0 ? issues.map((issue, idx) => {
            const isCritical = issue.type === 'critical';
            const isWarn = issue.type === 'warning';
            return (
              <div key={issue.id || idx} className={`flex items-start gap-2.5 px-3.5 py-2.5 rounded-lg text-sm border ${
                isCritical ? 'bg-red-50/80 border-red-100 dark:bg-red-950/20 dark:border-red-900/30' :
                isWarn ? 'bg-amber-50/80 border-amber-100 dark:bg-amber-950/20 dark:border-amber-900/30' :
                'bg-blue-50/80 border-blue-100 dark:bg-blue-950/20 dark:border-blue-900/30'
              }`}>
                <div className="mt-0.5 flex-shrink-0">
                  {isCritical ? <XCircle className="h-4 w-4 text-red-500" /> :
                   isWarn ? <AlertTriangle className="h-4 w-4 text-amber-500" /> :
                   <CheckCircle2 className="h-4 w-4 text-blue-500" />}
                </div>
                <div className="flex-1 min-w-0 space-y-0.5">
                  {(issue.message_ar || '').split('\n').map((line, li) => (
                    <p key={li} className={`${li === 0 ? 'font-medium text-foreground/90' : 'text-muted-foreground'} break-words leading-relaxed`}>{line}</p>
                  ))}
                </div>
                {issue.fix_link && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 px-2.5 text-xs gap-1 shrink-0"
                    onClick={(e) => { e.stopPropagation(); onFix?.(issue.id, issue.fix_link); }}
                  >
                    {issue.fix_action || 'إصلاح'}
                    <ArrowUpRight className="h-3.5 w-3.5" />
                  </Button>
                )}
              </div>
            );
          }) : (
            <div className="flex items-center gap-2.5 text-emerald-600 dark:text-emerald-400 text-sm bg-emerald-50 dark:bg-emerald-950/20 p-3 rounded-lg border border-emerald-100 dark:border-emerald-800/30">
              <CheckCircle2 className="h-4 w-4" />
              <span className="font-tajawal">هذه المرحلة مكتملة</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const TimetableReadinessPanel = ({
  items = [],
  categories = {},
  phases = {},
  overallStatus = ReadinessStatus.NOT_READY,
  percentage = 0,
  currentPhase = 1,
  criticalIssuesCount = 0,
  warningsCount = 0,
  canGenerate = false,
  capacity = null,
  loading = false,
  onFixItem,
  onRefresh
}) => {
  const [expanded, setExpanded] = useState(false);

  const phaseData = Object.keys(phases).length > 0 ? phases : categories;
  const hasPhases = Object.keys(phaseData).length > 0;
  const phaseEntries = Object.entries(phaseData);
  const completedCount = phaseEntries.filter(([, p]) => p.status === 'complete').length;
  const totalPhases = phaseEntries.length || 6;
  const sc = statusConfig(overallStatus);
  const pctRounded = Math.round(percentage);

  if (loading) {
    return (
      <Card className="border border-border/60 overflow-hidden rounded-2xl">
        <CardContent className="p-8">
          <div className="flex flex-col items-center justify-center gap-3">
            <Loader2 className="h-7 w-7 animate-spin text-brand-navy" />
            <span className="text-sm text-muted-foreground font-tajawal">جاري فحص جاهزية البيانات...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden rounded-2xl border border-border/60 shadow-sm" data-testid="timetable-readiness-panel">
      <div className="p-5 sm:p-6">
        <div className="flex items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${sc.gradient} flex items-center justify-center shadow-sm`}>
              <ClipboardList className="h-5 w-5 text-white" />
            </div>
            <div>
              <h3 className="text-base font-bold font-cairo text-foreground">جاهزية بيانات الجدول</h3>
              <p className="text-sm text-muted-foreground font-tajawal">{completedCount} من {totalPhases} مراحل مكتملة</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {onRefresh && (
              <Button
                variant="ghost"
                size="icon"
                onClick={onRefresh}
                className="h-9 w-9 rounded-xl text-muted-foreground hover:text-foreground hover:bg-muted/60"
                data-testid="refresh-readiness-btn"
              >
                <RefreshCw className="h-4 w-4" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setExpanded(!expanded)}
              className="gap-1.5 h-9 text-sm rounded-xl text-muted-foreground hover:text-foreground hover:bg-muted/60 px-3"
              data-testid="toggle-readiness-btn"
            >
              <span className="font-tajawal">{expanded ? 'إخفاء' : 'تفاصيل'}</span>
              {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </Button>
          </div>
        </div>

        <div className="flex items-center gap-4 mb-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between mb-2">
              <Badge variant="outline" className={`text-xs px-2.5 py-1 border font-cairo gap-1.5 ${sc.bgLight} ${sc.textColor} ${sc.borderColor}`}>
                {sc.icon}
                {sc.label}
              </Badge>
              <span className="text-xl font-bold font-cairo tabular-nums text-foreground">{pctRounded}%</span>
            </div>
            <div className="w-full h-2.5 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
              <div
                className={`h-full rounded-full bg-gradient-to-l ${sc.gradient} transition-all duration-700 ease-out`}
                style={{ width: `${pctRounded}%` }}
              />
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {criticalIssuesCount > 0 && (
            <div className="flex items-center gap-2 text-sm bg-red-50 dark:bg-red-950/20 text-red-600 dark:text-red-400 px-3 py-1.5 rounded-lg border border-red-100 dark:border-red-900/30">
              <XCircle className="h-4 w-4" />
              <span className="font-tajawal font-medium">{criticalIssuesCount} مشكلة حرجة</span>
            </div>
          )}
          {warningsCount > 0 && (
            <div className="flex items-center gap-2 text-sm bg-amber-50 dark:bg-amber-950/20 text-amber-600 dark:text-amber-400 px-3 py-1.5 rounded-lg border border-amber-100 dark:border-amber-900/30">
              <AlertTriangle className="h-4 w-4" />
              <span className="font-tajawal font-medium">{warningsCount} تحذير</span>
            </div>
          )}
        </div>

        {hasPhases && (
          <div className="mt-5 grid gap-0" style={{ gridTemplateColumns: `repeat(${phaseEntries.length}, minmax(0, 1fr))` }}>
            {phaseEntries.map(([key, phase], idx) => {
              const meta = PHASE_META[key];
              const isDone = phase.status === 'complete';
              const isPartial = phase.status === 'partial';
              const isBlocked = phase.status === 'blocked';
              const isNotStarted = phase.status === 'not_started';

              return (
                <div key={key} className="flex flex-col items-center relative">
                  {idx > 0 && (
                    <div className={`absolute top-4 -z-10 h-[2px] w-full ${
                      isDone && phaseEntries[idx-1]?.[1]?.status === 'complete' ? 'bg-emerald-400' : 'bg-gray-200 dark:bg-gray-700'
                    }`} style={{ right: '50%' }} />
                  )}
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold z-10 border-2 transition-colors ${
                    isDone ? 'bg-emerald-500 border-emerald-500 text-white' :
                    isPartial ? 'bg-amber-500 border-amber-500 text-white' :
                    isNotStarted ? 'bg-white dark:bg-gray-900 border-red-300 dark:border-red-700 text-red-500 dark:text-red-400' :
                    isBlocked ? 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-700 text-gray-300 dark:text-gray-600' :
                    'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-700 text-gray-400'
                  }`}>
                    {isDone ? <CheckCircle2 className="h-4 w-4" /> : (meta?.num || idx + 1)}
                  </div>
                  <span className={`text-xs font-tajawal mt-2 text-center leading-tight ${
                    isDone ? 'text-emerald-600 dark:text-emerald-400 font-semibold' :
                    isPartial ? 'text-amber-600 dark:text-amber-400 font-semibold' :
                    isBlocked ? 'text-gray-300 dark:text-gray-600' :
                    isNotStarted ? 'text-red-500 dark:text-red-400 font-medium' :
                    'text-gray-400 dark:text-gray-500'
                  }`}>{meta?.label || ''}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {expanded && (
        <CardContent className="p-3 sm:p-4 space-y-2 bg-gray-50/50 dark:bg-gray-950/30 border-t border-border/40">
          {hasPhases ? (
            phaseEntries.map(([key, phase]) => (
              <PhaseRow key={key} phaseKey={key} phase={phase} onFix={onFixItem} />
            ))
          ) : (
            <div className="flex items-center justify-center gap-3 p-4 bg-emerald-50 dark:bg-emerald-950/20 rounded-xl border border-emerald-200 dark:border-emerald-800/30">
              <CheckCircle2 className="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
              <span className="font-medium text-emerald-700 dark:text-emerald-300 font-tajawal">
                بيانات الجدول مكتملة وجاهزة للمعالجة
              </span>
            </div>
          )}

          {capacity && capacity.total_available_slots > 0 && (
            <div className="mt-2.5 p-3.5 bg-white dark:bg-gray-900/40 rounded-xl border border-border/40">
              <div className="flex items-center justify-between text-sm text-muted-foreground mb-2 font-tajawal">
                <span>السعة: <strong className="text-foreground">{capacity.total_available_slots}</strong> فترة</span>
                <span>المطلوب: <strong className="text-foreground">{capacity.total_required_periods}</strong> حصة</span>
              </div>
              <Progress
                value={Math.min(capacity.utilization_pct, 100)}
                className={`h-2 rounded-full bg-gray-100 dark:bg-gray-800 ${capacity.utilization_pct > 100 ? '[&>div]:bg-red-500' : '[&>div]:bg-brand-navy'}`}
              />
              <p className="text-xs text-muted-foreground mt-1.5 text-center font-tajawal">
                نسبة الاستخدام: {capacity.utilization_pct}%
              </p>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
};

export default TimetableReadinessPanel;
