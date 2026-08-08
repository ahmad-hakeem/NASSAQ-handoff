import { useState, useEffect, useRef, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { LoadingState } from '@/shared/components/ui/LoadingState';
import {
  PriorityBadge, EmptyState,
  PRIORITY_CONFIG,
} from './index';
import {
  Brain, BarChart3, Users, Target, Sparkles,
  AlertOctagon, CheckCircle2, TrendingUp, Eye, Timer,
  AlertTriangle, Activity, Award, Building2, ArrowUpRight,
  ShieldCheck, CircleDot, XCircle, ThumbsDown, Layers,
} from 'lucide-react';

function useCountUp(end, duration = 1200) {
  const [value, setValue] = useState(0);
  const prevEnd = useRef(0);
  const rafRef = useRef(null);
  const prefersReducedMotion = useRef(
    typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  );

  useEffect(() => {
    if (prefersReducedMotion.current || end === 0) {
      setValue(end);
      return;
    }
    const startVal = prevEnd.current;
    prevEnd.current = end;
    const diff = end - startVal;
    if (diff === 0) return;

    const startTime = performance.now();
    const dur = Math.min(Math.max(duration, 600), 1800);

    const step = (now) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / dur, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(startVal + diff * eased));
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(step);
      }
    };
    rafRef.current = requestAnimationFrame(step);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [end, duration]);

  return value;
}

export default function DashboardView({ data, loading, isAdmin, navigate }) {
  const total = data?.total_issues || 0;
  const resolved = data?.total_resolved || 0;
  const open = data?.total_open || 0;
  const rejected = data?.total_rejected || 0;
  const resRate = data?.resolution_rate || 0;
  const unresolvedPct = total > 0 ? Math.round((open / total) * 100) : 0;
  const resolvedPct = total > 0 ? Math.round((resolved / total) * 100) : 0;
  const rejectedPct = total > 0 ? Math.round((rejected / total) * 100) : 0;

  const animTotal = useCountUp(total, 1400);
  const animResolved = useCountUp(resolved, 1200);
  const animOpen = useCountUp(open, 1000);
  const animCritical = useCountUp(data?.critical_open || 0, 800);

  if (loading || !data) {
    return (
      <LoadingState variant="section" label="جاري تحميل التحليلات..." />
    );
  }

  const statusFlow = [
    { label: 'جديدة', value: data.new_count || 0, color: 'bg-sky-500', icon: CircleDot },
    { label: 'قيد المراجعة', value: data.under_review || 0, color: 'bg-amber-500', icon: Eye },
    { label: 'قيد التنفيذ', value: data.in_progress || 0, color: 'bg-violet-500', icon: Activity },
    { label: 'فحص الجودة', value: data.qa_validation || 0, color: 'bg-blue-500', icon: ShieldCheck },
    { label: 'تم الحل', value: resolved, color: 'bg-emerald-500', icon: CheckCircle2 },
    { label: 'مرفوضة', value: rejected, color: 'bg-red-500', icon: XCircle },
  ];

  const hakimStats = data.hakim_stats;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="relative overflow-hidden rounded-2xl border-0 bg-gradient-to-br from-brand-navy via-brand-navy/95 to-brand-turquoise/80 p-5 shadow-xl shadow-brand-navy/20 text-white hub-card">
          <div className="absolute inset-0 opacity-[0.04]" style={{ backgroundImage: 'radial-gradient(circle at 1px 1px, rgba(255,255,255,0.5) 1px, transparent 0)', backgroundSize: '16px 16px' }} />
          <div className="flex items-start justify-between">
            <div className="p-2.5 rounded-xl bg-white/10 backdrop-blur-sm">
              <Layers className="h-5 w-5 text-white" />
            </div>
            {data.new_this_week > 0 && (
              <span className="text-[10px] font-semibold px-2.5 py-1 rounded-full bg-white/15 backdrop-blur-sm flex items-center gap-1 border border-white/10">
                <ArrowUpRight className="h-3 w-3" />
                +{data.new_this_week} هذا الأسبوع
              </span>
            )}
          </div>
          <div className="mt-4 mb-1">
            <p className="text-6xl font-extrabold tracking-tighter leading-none tabular-nums hub-countup-number">
              {animTotal}
            </p>
            <p className="text-sm text-white/60 mt-2 font-medium">إجمالي التحديات</p>
          </div>
          {resolved > 0 && (
            <div className="mt-3 flex items-center gap-2">
              <div className="flex-1 bg-white/10 rounded-full h-1.5 overflow-hidden">
                <div className="bg-brand-turquoise h-1.5 rounded-full hub-progress-fill" style={{ width: `${resolvedPct}%` }} />
              </div>
              <span className="text-[10px] text-white/50 font-semibold tabular-nums">{resolvedPct}% مكتمل</span>
            </div>
          )}
          <div className="absolute -bottom-8 -left-8 h-28 w-28 rounded-full bg-brand-turquoise/10" />
          <div className="absolute -top-4 -right-4 h-16 w-16 rounded-full bg-white/5" />
        </div>

        <div className="relative overflow-hidden rounded-2xl border bg-white p-5 shadow-sm group hover:shadow-md transition-all hub-card">
          <div className="flex items-start justify-between">
            <div className="p-2.5 rounded-xl bg-emerald-50 transition-transform group-hover:scale-110">
              <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            </div>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700">
              {resolvedPct}%
            </span>
          </div>
          <div className="mt-3">
            <p className="text-4xl font-extrabold text-brand-navy tracking-tighter tabular-nums">{animResolved}</p>
            <p className="text-sm text-muted-foreground mt-0.5">تم حلها</p>
          </div>
          <div className="mt-2 w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
            <div className="bg-emerald-500 h-1.5 rounded-full hub-progress-fill" style={{ width: `${resolvedPct}%` }} />
          </div>
          <div className="absolute -bottom-4 -left-4 h-20 w-20 rounded-full bg-emerald-50 opacity-50" />
        </div>

        <div className="relative overflow-hidden rounded-2xl border bg-white p-5 shadow-sm group hover:shadow-md transition-all hub-card">
          <div className="flex items-start justify-between">
            <div className="p-2.5 rounded-xl bg-amber-50 transition-transform group-hover:scale-110">
              <AlertTriangle className="h-5 w-5 text-amber-600" />
            </div>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-50 text-amber-700">
              {unresolvedPct}%
            </span>
          </div>
          <div className="mt-3">
            <p className="text-4xl font-extrabold text-brand-navy tracking-tighter tabular-nums">{animOpen}</p>
            <p className="text-sm text-muted-foreground mt-0.5">لم تُحل بعد</p>
          </div>
          <div className="mt-2 w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
            <div className="bg-amber-500 h-1.5 rounded-full hub-progress-fill" style={{ width: `${unresolvedPct}%` }} />
          </div>
          <div className="absolute -bottom-4 -left-4 h-20 w-20 rounded-full bg-amber-50 opacity-50" />
        </div>

        <div className="relative overflow-hidden rounded-2xl border bg-white p-5 shadow-sm group hover:shadow-md transition-all hub-card">
          <div className="flex items-start justify-between">
            <div className="p-2.5 rounded-xl bg-red-50 transition-transform group-hover:scale-110">
              <AlertOctagon className="h-5 w-5 text-red-600" />
            </div>
            {data.sla_exceeded > 0 && (
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-50 text-red-700">
                {data.sla_exceeded} تجاوز SLA
              </span>
            )}
          </div>
          <div className="mt-3">
            <p className="text-4xl font-extrabold text-brand-navy tracking-tighter tabular-nums">{animCritical}</p>
            <p className="text-sm text-muted-foreground mt-0.5">حرجة مفتوحة</p>
          </div>
          <div className="mt-2 w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
            <div className="bg-red-500 h-1.5 rounded-full hub-progress-fill" style={{ width: `${total > 0 ? Math.round(((data.critical_open || 0) / total) * 100) : 0}%` }} />
          </div>
          <div className="absolute -bottom-4 -left-4 h-20 w-20 rounded-full bg-red-50 opacity-50" />
        </div>
      </div>

      <Card className="border rounded-2xl shadow-sm overflow-hidden">
        <CardHeader className="pb-2 bg-gradient-to-l from-slate-50 to-white">
          <CardTitle className="text-sm font-semibold flex items-center gap-2 text-brand-navy">
            <div className="p-1.5 rounded-lg bg-brand-turquoise/10">
              <Activity className="h-4 w-4 text-brand-turquoise" />
            </div>
            تدفق حالة التحديات
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-3 pb-5">
          <div className="flex items-center gap-1 mb-4 w-full h-3 rounded-full overflow-hidden bg-slate-100">
            {statusFlow.map((s, i) => {
              const pct = total > 0 ? (s.value / total) * 100 : 0;
              return pct > 0 ? (
                <div key={i} className={`${s.color} h-3 transition-all duration-700`} style={{ width: `${pct}%` }} title={`${s.label}: ${s.value}`} />
              ) : null;
            })}
          </div>
          <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
            {statusFlow.map((s, i) => {
              const Ic = s.icon;
              return (
                <div key={i} className="text-center p-3 rounded-xl bg-slate-50/80 border border-slate-100 hover:border-slate-200 transition-colors">
                  <div className="flex items-center justify-center mb-1.5">
                    <div className={`w-2 h-2 rounded-full ${s.color} ml-1.5`} />
                    <Ic className="h-3.5 w-3.5 text-slate-500" />
                  </div>
                  <p className="text-xl font-bold text-brand-navy">{s.value}</p>
                  <p className="text-[10px] text-muted-foreground mt-0.5 leading-tight">{s.label}</p>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="rounded-2xl border bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <Timer className="h-4 w-4 text-emerald-600" />
            <span className="text-xs text-muted-foreground">متوسط وقت الحل</span>
          </div>
          <p className="text-2xl font-bold text-brand-navy">{data.avg_resolution_hours || 0}<span className="text-sm font-normal text-muted-foreground mr-1">ساعة</span></p>
        </div>
        <div className="rounded-2xl border bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <Target className="h-4 w-4 text-amber-600" />
            <span className="text-xs text-muted-foreground">مكررات مكتشفة</span>
          </div>
          <p className="text-2xl font-bold text-brand-navy">{data.duplicates_detected || 0}</p>
        </div>
        <div className="rounded-2xl border bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <ThumbsDown className="h-4 w-4 text-red-500" />
            <span className="text-xs text-muted-foreground">مرفوضة</span>
          </div>
          <p className="text-2xl font-bold text-brand-navy">{rejected}<span className="text-sm font-normal text-muted-foreground mr-1">({rejectedPct}%)</span></p>
        </div>
        <div className="rounded-2xl border bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="h-4 w-4 text-brand-turquoise" />
            <span className="text-xs text-muted-foreground">معدل الحل</span>
          </div>
          <p className="text-2xl font-bold text-brand-navy">{resRate}<span className="text-sm font-normal text-muted-foreground mr-1">%</span></p>
        </div>
      </div>

      {hakimStats && (
        <Card className="border rounded-2xl shadow-sm bg-gradient-to-br from-brand-turquoise/5 via-white to-brand-turquoise/3 border-brand-turquoise/20">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold flex items-center gap-2 text-brand-navy">
              <div className="p-2 rounded-xl bg-brand-turquoise/10">
                <Brain className="h-5 w-5 text-brand-turquoise" />
              </div>
              <span>تحليلات حكيم</span>
              <Sparkles className="h-3.5 w-3.5 text-brand-turquoise/60" />
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid grid-cols-3 gap-3">
              <div className="text-center p-3.5 bg-white rounded-xl border border-slate-100 shadow-sm">
                <p className="text-2xl font-bold text-brand-navy">{hakimStats.total_analyzed}</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">تحدي تم تحليله</p>
              </div>
              <div className="text-center p-3.5 bg-white rounded-xl border border-slate-100 shadow-sm">
                <p className="text-2xl font-bold text-amber-600">{hakimStats.duplicates_detected}</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">مكرر مكتشف</p>
              </div>
              <div className="text-center p-3.5 bg-white rounded-xl border border-slate-100 shadow-sm">
                <p className="text-2xl font-bold text-violet-600">{hakimStats.priority_overridden}</p>
                <p className="text-[10px] text-muted-foreground mt-0.5">أولوية مُعدّلة</p>
              </div>
            </div>

            {hakimStats.top_teams?.length > 0 && (
              <div>
                <p className="text-[11px] font-semibold text-muted-foreground mb-2 flex items-center gap-1.5">
                  <Users className="h-3 w-3" />
                  الفرق المقترحة من حكيم
                </p>
                <div className="flex flex-wrap gap-2">
                  {hakimStats.top_teams.map((t, i) => (
                    <Badge key={i} variant="outline" className="text-[11px] border-brand-turquoise/30 text-brand-turquoise bg-brand-turquoise/5 px-3 py-1">
                      {t.team} ({t.count})
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {hakimStats.recent_insights?.length > 0 && (
              <div>
                <p className="text-[11px] font-semibold text-muted-foreground mb-2 flex items-center gap-1.5">
                  <Eye className="h-3 w-3" />
                  آخر تحليلات حكيم
                </p>
                <div className="space-y-2">
                  {hakimStats.recent_insights.map((insight, i) => (
                    <div
                      key={i}
                      onClick={() => navigate(`/admin/product-hub/issues/${insight.id}`)}
                      className="p-3 bg-white rounded-xl border border-slate-100 hover:border-brand-turquoise/30 cursor-pointer transition-all group shadow-sm"
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[10px] font-mono text-muted-foreground bg-slate-100 px-1.5 py-0.5 rounded">
                          #{insight.issue_number}
                        </span>
                        <PriorityBadge priority={insight.priority} size="sm" />
                        {insight.suggested_team && (
                          <Badge variant="outline" className="text-[9px] border-brand-turquoise/20 text-brand-turquoise">
                            {insight.suggested_team}
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs font-medium text-brand-navy group-hover:text-brand-turquoise transition-colors truncate">
                        {insight.title}
                      </p>
                      {insight.impact && (
                        <p className="text-[10px] text-muted-foreground mt-1 line-clamp-1">{insight.impact}</p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border rounded-2xl shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold flex items-center gap-2 text-brand-navy">
              <div className="p-1.5 rounded-lg bg-brand-turquoise/10">
                <BarChart3 className="h-4 w-4 text-brand-turquoise" />
              </div>
              حسب النوع
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {data.by_type?.map((t, i) => {
                const pct = Math.min(100, (t.count / Math.max(1, total)) * 100);
                return (
                  <div key={i} className="group">
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="text-slate-600">{t.label}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-muted-foreground">{Math.round(pct)}%</span>
                        <span className="font-semibold text-brand-navy">{t.count}</span>
                      </div>
                    </div>
                    <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                      <div className="bg-gradient-to-r from-brand-turquoise to-brand-turquoise/70 h-2 rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
              {(!data.by_type || data.by_type.length === 0) && (
                <EmptyState title="لا توجد بيانات" className="py-8" />
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="border rounded-2xl shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold flex items-center gap-2 text-brand-navy">
              <div className="p-1.5 rounded-lg bg-brand-turquoise/10">
                <Target className="h-4 w-4 text-brand-turquoise" />
              </div>
              حسب الأولوية
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {data.by_priority?.map((p, i) => {
                const cfg = PRIORITY_CONFIG[p.priority] || {};
                const pct = Math.min(100, (p.count / Math.max(1, total)) * 100);
                return (
                  <div key={i}>
                    <div className="flex items-center justify-between text-sm mb-1">
                      <div className="flex items-center gap-2">
                        <div className={`w-2.5 h-2.5 rounded-full ${cfg.dotColor || 'bg-slate-400'}`} />
                        <span className="text-slate-600">{p.label || p.priority}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-muted-foreground">{Math.round(pct)}%</span>
                        <span className="font-semibold text-brand-navy">{p.count}</span>
                      </div>
                    </div>
                    <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                      <div className={`h-2 rounded-full transition-all duration-500 ${cfg.color || 'bg-slate-400'}`} style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
              {(!data.by_priority || data.by_priority.length === 0) && (
                <EmptyState title="لا توجد بيانات" className="py-8" />
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="border rounded-2xl shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold flex items-center gap-2 text-brand-navy">
              <div className="p-1.5 rounded-lg bg-brand-turquoise/10">
                <Users className="h-4 w-4 text-brand-turquoise" />
              </div>
              حسب الفريق
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {data.by_team?.map((t, i) => {
                const pct = Math.min(100, (t.count / Math.max(1, total)) * 100);
                return (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <span className="text-slate-600">{t.team || 'غير معيّن'}</span>
                    <div className="flex items-center gap-3">
                      <div className="w-20 bg-slate-100 rounded-full h-2 overflow-hidden">
                        <div className="bg-brand-navy/60 h-2 rounded-full" style={{ width: `${pct}%` }} />
                      </div>
                      <span className="font-semibold text-brand-navy w-6 text-left">{t.count}</span>
                    </div>
                  </div>
                );
              })}
              {(!data.by_team || data.by_team.length === 0) && (
                <EmptyState title="لا توجد بيانات" className="py-8" />
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="border rounded-2xl shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold flex items-center gap-2 text-brand-navy">
              <div className="p-1.5 rounded-lg bg-brand-turquoise/10">
                <Award className="h-4 w-4 text-brand-turquoise" />
              </div>
              أكثر المساهمين
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2.5">
              {data.top_contributors?.map((c, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2.5">
                    <span className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold text-white ${
                      i === 0 ? 'bg-amber-500' : i === 1 ? 'bg-slate-400' : 'bg-orange-400'
                    }`}>
                      {i + 1}
                    </span>
                    <span className="text-slate-600">{c.name}</span>
                  </div>
                  <Badge variant="secondary" className="text-[11px]">{c.count}</Badge>
                </div>
              ))}
              {(!data.top_contributors || data.top_contributors.length === 0) && (
                <EmptyState title="لا توجد بيانات" className="py-8" />
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="border rounded-2xl shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold flex items-center gap-2 text-brand-navy">
              <div className="p-1.5 rounded-lg bg-brand-turquoise/10">
                <CheckCircle2 className="h-4 w-4 text-brand-turquoise" />
              </div>
              أدق المبلّغين
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2.5">
              {data.most_accurate_reporters?.map((r, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <span className="text-slate-600">{r.name}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">{r.valid}/{r.total}</span>
                    <Badge className={`text-[10px] ${r.accuracy >= 80 ? 'bg-emerald-500 text-white' : 'bg-slate-200 text-slate-600'}`}>
                      {r.accuracy}%
                    </Badge>
                  </div>
                </div>
              ))}
              {(!data.most_accurate_reporters || data.most_accurate_reporters.length === 0) && (
                <EmptyState title="لا توجد بيانات كافية" className="py-8" />
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="border rounded-2xl shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold flex items-center gap-2 text-brand-navy">
              <div className="p-1.5 rounded-lg bg-brand-turquoise/10">
                <Building2 className="h-4 w-4 text-brand-turquoise" />
              </div>
              أكثر الأقسام تحديات
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2.5">
              {data.by_section?.map((s, i) => {
                const pct = Math.min(100, (s.count / Math.max(1, total)) * 100);
                return (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <span className="text-slate-600">{s.section || 'غير محدد'}</span>
                    <div className="flex items-center gap-3">
                      <div className="w-20 bg-slate-100 rounded-full h-2 overflow-hidden">
                        <div className="bg-brand-turquoise/60 h-2 rounded-full" style={{ width: `${pct}%` }} />
                      </div>
                      <span className="font-semibold text-brand-navy w-6 text-left">{s.count}</span>
                    </div>
                  </div>
                );
              })}
              {(!data.by_section || data.by_section.length === 0) && (
                <EmptyState title="لا توجد بيانات" className="py-8" />
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
