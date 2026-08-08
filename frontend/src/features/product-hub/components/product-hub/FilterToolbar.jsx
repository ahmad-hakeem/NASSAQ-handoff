import React, { useState, useMemo } from 'react';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import {
  STATUS_CONFIG, PRIORITY_CONFIG, STATUS_PROGRESS,
} from './index';
import {
  Search, CheckCircle2, Eye,
  XCircle, ShieldCheck, CircleDot,
  Activity, Layers,
  ChevronDown,
} from 'lucide-react';

export function FilterToolbar({ filters, config, onFilterChange, onClear, hasActiveFilters }) {
  const activeCount = Object.values(filters).filter(v => v).length;
  const [showAdvanced, setShowAdvanced] = useState(false);
  const hasAdvancedFilters = !!(filters.issue_type || filters.created_by || filters.date_from || filters.date_to);

  return (
    <Card className="border shadow-sm rounded-2xl bg-white/80 backdrop-blur-sm">
      <CardContent className="p-0">
        <div className="p-4 pb-3">
          <div className="flex items-center gap-3">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
              <Input
                placeholder="بحث في العنوان، المحتوى، الاسم..."
                value={filters.search}
                onChange={(e) => onFilterChange('search', e.target.value)}
                className="pr-10 text-right rounded-xl h-10 bg-slate-50/80 border-slate-200 focus:bg-white transition-colors"
              />
            </div>

            <Select value={filters.status || '_all'} onValueChange={(v) => onFilterChange('status', v === '_all' ? '' : v)}>
              <SelectTrigger className="w-[140px] rounded-xl h-10 text-xs bg-slate-50/80 border-slate-200">
                <SelectValue placeholder="الحالة" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="_all">كل الحالات</SelectItem>
                {Object.entries(STATUS_CONFIG).map(([k, v]) => (
                  <SelectItem key={k} value={k}>
                    <span className="flex items-center gap-1.5">
                      <span className={`w-2 h-2 rounded-full ${v.color}`} />
                      {v.label}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={filters.priority || '_all'} onValueChange={(v) => onFilterChange('priority', v === '_all' ? '' : v)}>
              <SelectTrigger className="w-[130px] rounded-xl h-10 text-xs bg-slate-50/80 border-slate-200">
                <SelectValue placeholder="الأولوية" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="_all">كل الأولويات</SelectItem>
                {Object.entries(PRIORITY_CONFIG).map(([k, v]) => (
                  <SelectItem key={k} value={k}>
                    <span className="flex items-center gap-1.5">
                      <span className={`w-2 h-2 rounded-full ${v.dotColor || 'bg-slate-400'}`} />
                      {v.label}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Button
              variant="ghost" size="sm"
              onClick={() => setShowAdvanced(prev => !prev)}
              className={`rounded-xl h-10 px-3 text-xs gap-1.5 transition-all ${showAdvanced || hasAdvancedFilters ? 'bg-brand-navy/5 text-brand-navy border border-brand-navy/15' : 'text-muted-foreground hover:text-brand-navy'}`}
            >
              <Layers className="h-3.5 w-3.5" />
              فلاتر متقدمة
              {hasAdvancedFilters && <span className="w-2 h-2 rounded-full bg-brand-turquoise animate-pulse" />}
              <ChevronDown className={`h-3 w-3 transition-transform duration-200 ${showAdvanced ? 'rotate-180' : ''}`} />
            </Button>

            {hasActiveFilters && (
              <Button variant="ghost" size="sm" onClick={onClear} className="text-red-500 hover:text-red-700 hover:bg-red-50 rounded-xl h-10 px-3 text-xs gap-1.5">
                <XCircle className="h-3.5 w-3.5" />
                مسح ({activeCount})
              </Button>
            )}
          </div>
        </div>

        <div
          className="overflow-hidden transition-all duration-300 ease-in-out"
          style={{ maxHeight: showAdvanced ? '200px' : '0px', opacity: showAdvanced ? 1 : 0 }}
        >
          <div className="px-4 pb-4 pt-1 border-t border-slate-100">
            <div className="flex flex-wrap items-end gap-3 mt-3">
              {config && (
                <>
                  <Select value={filters.issue_type || '_all'} onValueChange={(v) => onFilterChange('issue_type', v === '_all' ? '' : v)}>
                    <SelectTrigger className="w-[140px] rounded-xl h-9 text-xs bg-slate-50/80 border-slate-200">
                      <SelectValue placeholder="النوع" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="_all">كل الأنواع</SelectItem>
                      {(config.issue_types || []).map(t => (
                        <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  {(config.reporters || []).length > 0 && (
                    <Select value={filters.created_by || '_all'} onValueChange={(v) => onFilterChange('created_by', v === '_all' ? '' : v)}>
                      <SelectTrigger className="w-[150px] rounded-xl h-9 text-xs bg-slate-50/80 border-slate-200">
                        <SelectValue placeholder="المُبلِّغ" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="_all">كل المُبلِّغين</SelectItem>
                        {(config.reporters || []).map(r => (
                          <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                </>
              )}

              <div className="flex items-center gap-2">
                <div className="flex flex-col">
                  <label className="text-[10px] text-muted-foreground mb-0.5 font-medium">من تاريخ</label>
                  <Input
                    type="date"
                    value={filters.date_from}
                    onChange={(e) => onFilterChange('date_from', e.target.value)}
                    className="w-[140px] rounded-xl h-9 text-xs bg-slate-50/80 border-slate-200"
                  />
                </div>
                <div className="flex flex-col">
                  <label className="text-[10px] text-muted-foreground mb-0.5 font-medium">إلى تاريخ</label>
                  <Input
                    type="date"
                    value={filters.date_to}
                    onChange={(e) => onFilterChange('date_to', e.target.value)}
                    className="w-[140px] rounded-xl h-9 text-xs bg-slate-50/80 border-slate-200"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function IssuesStatusFlow({ issues, onStatusFilter, activeStatus }) {
  const counts = useMemo(() => {
    const c = { new: 0, under_review: 0, in_progress: 0, qa_validation: 0, done: 0, user_feedback_confirmed: 0, rejected: 0 };
    (issues || []).forEach(issue => {
      if (c[issue.status] !== undefined) c[issue.status]++;
    });
    return c;
  }, [issues]);

  const total = issues?.length || 0;

  const flow = [
    { key: 'new', label: 'جديدة', value: counts.new, bg: 'bg-sky-500', bgLight: 'bg-sky-50', bgHover: 'hover:bg-sky-100', borderActive: 'border-sky-400 ring-sky-300', textColor: 'text-sky-700', iconColor: 'text-sky-500', icon: CircleDot },
    { key: 'under_review', label: 'قيد المراجعة', value: counts.under_review, bg: 'bg-amber-500', bgLight: 'bg-amber-50', bgHover: 'hover:bg-amber-100', borderActive: 'border-amber-400 ring-amber-300', textColor: 'text-amber-700', iconColor: 'text-amber-500', icon: Eye },
    { key: 'in_progress', label: 'قيد التنفيذ', value: counts.in_progress, bg: 'bg-violet-500', bgLight: 'bg-violet-50', bgHover: 'hover:bg-violet-100', borderActive: 'border-violet-400 ring-violet-300', textColor: 'text-violet-700', iconColor: 'text-violet-500', icon: Activity },
    { key: 'qa_validation', label: 'فحص الجودة', value: counts.qa_validation, bg: 'bg-blue-500', bgLight: 'bg-blue-50', bgHover: 'hover:bg-blue-100', borderActive: 'border-blue-400 ring-blue-300', textColor: 'text-blue-700', iconColor: 'text-blue-500', icon: ShieldCheck },
    { key: 'done,user_feedback_confirmed', label: 'تم الحل', value: counts.done + counts.user_feedback_confirmed, bg: 'bg-emerald-500', bgLight: 'bg-emerald-50', bgHover: 'hover:bg-emerald-100', borderActive: 'border-emerald-400 ring-emerald-300', textColor: 'text-emerald-700', iconColor: 'text-emerald-500', icon: CheckCircle2 },
    { key: 'rejected', label: 'مرفوضة', value: counts.rejected, bg: 'bg-red-500', bgLight: 'bg-red-50', bgHover: 'hover:bg-red-100', borderActive: 'border-red-400 ring-red-300', textColor: 'text-red-700', iconColor: 'text-red-500', icon: XCircle },
  ];

  return (
    <Card className="border rounded-2xl shadow-sm overflow-hidden bg-white/80 backdrop-blur-sm">
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <div className="p-1.5 rounded-lg bg-brand-turquoise/10">
            <Activity className="h-4 w-4 text-brand-turquoise" />
          </div>
          <span className="text-sm font-semibold text-brand-navy">تدفق حالة التحديات</span>
        </div>

        <div className="flex items-center gap-0.5 mb-3 w-full h-3 rounded-full overflow-hidden bg-slate-100/80">
          {flow.map((s, i) => {
            const pct = total > 0 ? (s.value / total) * 100 : 0;
            return pct > 0 ? (
              <div key={i} className={`${s.bg} h-3 transition-all duration-700 first:rounded-r-full last:rounded-l-full`} style={{ width: `${pct}%` }} title={`${s.label}: ${s.value}`} />
            ) : null;
          })}
        </div>

        <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
          {flow.map((s, i) => {
            const Ic = s.icon;
            const isActive = activeStatus === s.key;
            return (
              <button
                key={i}
                onClick={() => onStatusFilter('status', isActive ? '' : s.key)}
                className={`group/card text-center p-3 rounded-xl border-2 transition-all duration-200 cursor-pointer active:scale-95 ${isActive ? `${s.bgLight} ${s.borderActive} ring-2 shadow-md` : `${s.bgLight} border-transparent ${s.bgHover} hover:shadow-md hover:border-current/10 hover:-translate-y-0.5`}`}
              >
                <div className="flex items-center justify-center mb-1.5">
                  <Ic className={`h-4 w-4 ${s.iconColor}`} />
                </div>
                <p className={`text-xl font-bold ${s.textColor}`}>{s.value}</p>
                <p className={`text-[9px] ${s.textColor} opacity-70 leading-tight font-medium mt-0.5`}>{s.label}</p>
              </button>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
