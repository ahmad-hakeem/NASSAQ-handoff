import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Sidebar } from '../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Progress } from '../components/ui/progress';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import {
  StatusChip, PriorityBadge, SLAIndicator, StatCard, EmptyState, IssueKanbanCard,
  STATUS_CONFIG, PRIORITY_CONFIG, TYPE_CONFIG, STATUS_PROGRESS, KANBAN_COLUMNS,
} from '../components/product-hub';
import {
  Brain, Plus, Search, BarChart3, Users, Target, Zap,
  ChevronLeft, ChevronRight, Award, Building2, Timer, AlertOctagon, Clock,
  Table2, Kanban, AlertTriangle, CheckCircle2, Bug,
  RefreshCw, XCircle,
} from 'lucide-react';

const authHeaders = () => {
  const t = localStorage.getItem('nassaq_token');
  return t ? { Authorization: `Bearer ${t}` } : {};
};

export function ProductHubPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'dashboard');
  const [issues, setIssues] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dashLoading, setDashLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [config, setConfig] = useState(null);
  const [sortField, setSortField] = useState('created_at');
  const [sortDir, setSortDir] = useState('desc');

  const [filters, setFilters] = useState({
    status: searchParams.get('status') || '',
    issue_type: '',
    priority: '',
    section: '',
    assigned_team: '',
    search: '',
    date_from: '',
    date_to: '',
  });

  const isAdmin = user?.role === 'platform_admin';
  const limit = 20;

  const fetchConfig = useCallback(async () => {
    try {
      const res = await axios.get('/api/product-hub/config', { headers: authHeaders() });
      setConfig(res.data);
    } catch (e) { console.error(e); }
  }, []);

  const fetchIssues = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, limit };
      Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v; });
      const res = await axios.get('/api/product-hub/issues', { params, headers: authHeaders() });
      setIssues(res.data.issues);
      setTotal(res.data.total);
    } catch (e) {
      toast.error('فشل في تحميل التحديات');
    } finally {
      setLoading(false);
    }
  }, [page, filters]);

  const fetchDashboard = useCallback(async () => {
    setDashLoading(true);
    try {
      const res = await axios.get('/api/product-hub/dashboard', { headers: authHeaders() });
      setDashboard(res.data);
    } catch (e) { console.error(e); }
    finally { setDashLoading(false); }
  }, []);

  useEffect(() => { fetchConfig(); }, [fetchConfig]);
  useEffect(() => { fetchIssues(); }, [fetchIssues]);
  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  useEffect(() => {
    const tab = searchParams.get('tab');
    if (tab && tab !== activeTab) setActiveTab(tab);
  }, [searchParams]);

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setSearchParams({ tab });
  };

  const updateFilter = (key, value) => {
    setFilters(f => ({ ...f, [key]: value === 'all' ? '' : value }));
    setPage(1);
  };

  const clearFilters = () => {
    setFilters({ status: '', issue_type: '', priority: '', section: '', assigned_team: '', search: '', date_from: '', date_to: '' });
    setPage(1);
  };

  const hasActiveFilters = Object.values(filters).some(v => v);
  const totalPages = Math.ceil(total / limit);

  const sortedIssues = useMemo(() => {
    const sorted = [...issues];
    sorted.sort((a, b) => {
      const aVal = a[sortField] || '';
      const bVal = b[sortField] || '';
      if (sortDir === 'asc') return aVal > bVal ? 1 : -1;
      return aVal < bVal ? 1 : -1;
    });
    return sorted;
  }, [issues, sortField, sortDir]);

  const kanbanIssues = useMemo(() => {
    const grouped = {};
    KANBAN_COLUMNS.forEach(col => { grouped[col] = []; });
    issues.forEach(issue => {
      const col = grouped[issue.status] ? issue.status : 'new';
      grouped[col].push(issue);
    });
    return grouped;
  }, [issues]);

  const toggleSort = (field) => {
    if (sortField === field) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  };

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50/20" dir="rtl">
        <div className="p-4 lg:p-8 space-y-6 max-w-[1600px] mx-auto">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl lg:text-3xl font-bold text-brand-navy flex items-center gap-3">
                <div className="p-2 rounded-xl bg-brand-turquoise/10">
                  <Brain className="h-7 w-7 text-brand-turquoise" />
                </div>
                مركز ذكاء المنتج
              </h1>
              <p className="text-muted-foreground mt-1 text-sm">نظام الحوكمة والتتبع الذكي الداخلي</p>
            </div>
            <div className="flex items-center gap-3">
              <Button
                variant="outline" size="sm"
                onClick={() => { fetchIssues(); fetchDashboard(); }}
                className="text-muted-foreground"
              >
                <RefreshCw className="h-4 w-4" />
              </Button>
              <Button
                onClick={() => navigate('/admin/product-hub/submit')}
                className="bg-brand-turquoise hover:bg-brand-turquoise/90 text-white shadow-lg shadow-brand-turquoise/20"
              >
                <Plus className="h-4 w-4 ml-2" />
                إضافة تحدي جديد
              </Button>
            </div>
          </div>

          <Tabs value={activeTab} onValueChange={handleTabChange}>
            <TabsList className="bg-white border shadow-sm rounded-xl p-1">
              <TabsTrigger value="dashboard" className="rounded-lg data-[state=active]:bg-brand-navy data-[state=active]:text-white gap-2">
                <BarChart3 className="h-4 w-4" />
                لوحة القيادة
              </TabsTrigger>
              <TabsTrigger value="issues" className="rounded-lg data-[state=active]:bg-brand-navy data-[state=active]:text-white gap-2">
                <Table2 className="h-4 w-4" />
                التحديات
              </TabsTrigger>
              <TabsTrigger value="kanban" className="rounded-lg data-[state=active]:bg-brand-navy data-[state=active]:text-white gap-2">
                <Kanban className="h-4 w-4" />
                كانبان
              </TabsTrigger>
            </TabsList>

            <TabsContent value="dashboard" className="mt-6">
              <DashboardView data={dashboard} loading={dashLoading} isAdmin={isAdmin} navigate={navigate} />
            </TabsContent>

            <TabsContent value="issues" className="mt-6 space-y-4">
              <FilterToolbar
                filters={filters}
                config={config}
                onFilterChange={updateFilter}
                onClear={clearFilters}
                hasActiveFilters={hasActiveFilters}
              />
              <IssuesTableView
                issues={sortedIssues}
                loading={loading}
                total={total}
                page={page}
                totalPages={totalPages}
                onPageChange={setPage}
                onSort={toggleSort}
                sortField={sortField}
                sortDir={sortDir}
                navigate={navigate}
              />
            </TabsContent>

            <TabsContent value="kanban" className="mt-6">
              <FilterToolbar
                filters={filters}
                config={config}
                onFilterChange={updateFilter}
                onClear={clearFilters}
                hasActiveFilters={hasActiveFilters}
              />
              <KanbanView issues={kanbanIssues} loading={loading} total={total} />
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </Sidebar>
  );
}

function ChipFilter({ label, value, options, onChange }) {
  return (
    <div className="space-y-1.5">
      <p className="text-[11px] font-semibold text-muted-foreground">{label}</p>
      <div className="flex flex-wrap gap-1.5">
        <button
          onClick={() => onChange('')}
          className={`px-3 py-1 rounded-full text-[11px] font-medium border transition-all ${
            !value
              ? 'border-brand-turquoise bg-brand-turquoise/10 text-brand-navy'
              : 'border-slate-200 text-muted-foreground hover:border-slate-300 hover:bg-slate-50'
          }`}
        >
          الكل
        </button>
        {options.map(opt => (
          <button
            key={opt.value}
            onClick={() => onChange(value === opt.value ? '' : opt.value)}
            className={`px-3 py-1 rounded-full text-[11px] font-medium border transition-all ${
              value === opt.value
                ? 'border-brand-turquoise bg-brand-turquoise/10 text-brand-navy'
                : 'border-slate-200 text-muted-foreground hover:border-slate-300 hover:bg-slate-50'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function FilterToolbar({ filters, config, onFilterChange, onClear, hasActiveFilters }) {
  return (
    <Card className="border shadow-sm rounded-xl">
      <CardContent className="p-4 space-y-4">
        <div className="relative">
          <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="بحث في العنوان، المحتوى، الاسم..."
            value={filters.search}
            onChange={(e) => onFilterChange('search', e.target.value)}
            className="pr-10 text-right rounded-lg"
          />
        </div>

        <ChipFilter
          label="الحالة"
          value={filters.status}
          options={Object.entries(STATUS_CONFIG).map(([k, v]) => ({ value: k, label: v.label }))}
          onChange={(v) => onFilterChange('status', v)}
        />

        <ChipFilter
          label="الأولوية"
          value={filters.priority}
          options={Object.entries(PRIORITY_CONFIG).map(([k, v]) => ({ value: k, label: v.label }))}
          onChange={(v) => onFilterChange('priority', v)}
        />

        {config && (
          <>
            <ChipFilter
              label="النوع"
              value={filters.issue_type}
              options={(config.issue_types || []).map(t => ({ value: t.value, label: t.label }))}
              onChange={(v) => onFilterChange('issue_type', v)}
            />
            <ChipFilter
              label="القسم"
              value={filters.section}
              options={(config.sections || []).map(s => ({ value: s, label: s }))}
              onChange={(v) => onFilterChange('section', v)}
            />
            <ChipFilter
              label="الفريق"
              value={filters.assigned_team}
              options={(config.teams || []).map(t => ({ value: t, label: t }))}
              onChange={(v) => onFilterChange('assigned_team', v)}
            />
          </>
        )}

        {hasActiveFilters && (
          <div className="flex justify-end">
            <Button variant="ghost" size="sm" onClick={onClear} className="text-red-500 hover:text-red-700 hover:bg-red-50 rounded-full">
              <XCircle className="h-4 w-4 ml-1" />
              مسح الفلاتر
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function IssueCard({ issue, navigate }) {
  const typeCfg = TYPE_CONFIG[issue.issue_type] || TYPE_CONFIG.other;
  const TypeIcon = typeCfg.icon;
  const progress = STATUS_PROGRESS[issue.status] || 0;

  return (
    <Card
      onClick={() => navigate(`/admin/product-hub/issues/${issue.id}`)}
      className="border shadow-sm rounded-xl hover:shadow-md hover:border-brand-turquoise/40 cursor-pointer transition-all group"
    >
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1.5">
              <span className="text-[11px] font-mono text-muted-foreground bg-slate-100 px-1.5 py-0.5 rounded">
                #{issue.issue_number}
              </span>
              <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
                <TypeIcon className={`h-3.5 w-3.5 ${typeCfg.color}`} />
                <span>{typeCfg.label}</span>
              </div>
            </div>
            <h3 className="text-sm font-bold text-brand-navy group-hover:text-brand-turquoise transition-colors leading-relaxed">
              {issue.title}
            </h3>
          </div>
          <PriorityBadge priority={issue.priority} size="sm" showIcon />
        </div>

        {issue.current_behavior && (
          <p className="text-xs text-muted-foreground line-clamp-2 mb-3 leading-relaxed bg-slate-50 p-2.5 rounded-lg border border-slate-100">
            {issue.current_behavior}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-2 mb-3">
          <StatusChip status={issue.status} size="sm" showIcon />
          <SLAIndicator issue={issue} size="sm" />
          {issue.assigned_team && (
            <Badge variant="outline" className="text-[10px] border-brand-turquoise/30 text-brand-turquoise">
              {issue.assigned_team}
            </Badge>
          )}
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
            <span className="flex items-center gap-1">
              <Users className="h-3 w-3" />
              {issue.employee_name}
            </span>
            <span>{issue.section}</span>
            <span>{new Date(issue.created_at).toLocaleDateString('ar-SA')}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Progress value={progress} className="h-1.5 w-16" />
            <span className="text-[10px] text-muted-foreground font-medium">{progress}%</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function IssuesTableView({ issues, loading, total, page, totalPages, onPageChange, navigate }) {
  if (loading) {
    return (
      <div className="flex justify-center items-center py-20">
        <div className="flex flex-col items-center gap-3">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-brand-turquoise border-t-transparent" />
          <p className="text-sm text-muted-foreground">جاري التحميل...</p>
        </div>
      </div>
    );
  }

  if (issues.length === 0) {
    return (
      <Card className="border rounded-xl">
        <CardContent>
          <EmptyState icon={Bug} title="لا توجد تحديات" description="لم يتم العثور على تحديات تطابق معايير البحث" />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {issues.map(issue => (
          <IssueCard key={issue.id} issue={issue} navigate={navigate} />
        ))}
      </div>

      {totalPages > 1 && (
        <div className="flex justify-center items-center gap-4 pt-2">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPageChange(p => p - 1)} className="rounded-lg">
            <ChevronRight className="h-4 w-4" />
          </Button>
          <span className="text-sm text-muted-foreground">
            صفحة {page} من {totalPages} ({total} تحدي)
          </span>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => onPageChange(p => p + 1)} className="rounded-lg">
            <ChevronLeft className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}

function KanbanView({ issues, loading, total }) {
  if (loading) {
    return (
      <div className="flex justify-center items-center py-20">
        <div className="flex flex-col items-center gap-3">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-brand-turquoise border-t-transparent" />
          <p className="text-sm text-muted-foreground">جاري التحميل...</p>
        </div>
      </div>
    );
  }

  if (total === 0) {
    return (
      <Card className="border rounded-xl">
        <CardContent>
          <EmptyState icon={Kanban} title="لا توجد تحديات" description="ستظهر التحديات هنا بمجرد إنشائها" />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7 gap-3">
      {KANBAN_COLUMNS.map(status => {
        const cfg = STATUS_CONFIG[status];
        const columnIssues = issues[status] || [];
        return (
          <div key={status} className="min-w-0">
            <div className={`rounded-t-xl px-3 py-2 ${cfg.bgLight} border ${cfg.borderColor} border-b-0`}>
              <div className="flex items-center justify-between gap-1">
                <div className="flex items-center gap-1.5 min-w-0">
                  <cfg.icon className={`h-3.5 w-3.5 flex-shrink-0 ${cfg.textColor}`} />
                  <span className={`text-xs font-semibold truncate ${cfg.textColor}`}>{cfg.label}</span>
                </div>
                <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-5 flex-shrink-0">
                  {columnIssues.length}
                </Badge>
              </div>
            </div>
            <div className={`rounded-b-xl border ${cfg.borderColor} border-t-0 bg-slate-50/50 p-2 space-y-2 min-h-[160px] max-h-[400px] overflow-y-auto`}>
              {columnIssues.length === 0 ? (
                <div className="flex items-center justify-center h-24 text-xs text-muted-foreground">
                  لا توجد تحديات
                </div>
              ) : (
                columnIssues.map(issue => (
                  <IssueKanbanCard key={issue.id} issue={issue} />
                ))
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function DashboardView({ data, loading, isAdmin, navigate }) {
  if (loading || !data) {
    return (
      <div className="flex justify-center items-center py-20">
        <div className="flex flex-col items-center gap-3">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-brand-turquoise border-t-transparent" />
          <p className="text-sm text-muted-foreground">جاري تحميل التحليلات...</p>
        </div>
      </div>
    );
  }

  const kpiCards = [
    { label: 'إجمالي التحديات', value: data.total_issues, icon: BarChart3, color: 'text-brand-navy', bg: 'bg-blue-50' },
    { label: 'تحديات مفتوحة', value: data.total_open, icon: AlertTriangle, color: 'text-amber-600', bg: 'bg-amber-50' },
    { label: 'تحديات حرجة', value: data.critical_open, icon: AlertOctagon, color: 'text-red-600', bg: 'bg-red-50' },
    { label: 'جديدة هذا الأسبوع', value: data.new_this_week, icon: Zap, color: 'text-blue-600', bg: 'bg-blue-50' },
    { label: 'قيد التنفيذ', value: data.in_progress, icon: Clock, color: 'text-violet-600', bg: 'bg-violet-50' },
    { label: 'متوسط الحل (ساعة)', value: data.avg_resolution_hours, icon: Timer, color: 'text-emerald-600', bg: 'bg-emerald-50' },
    { label: 'تجاوز SLA', value: data.sla_exceeded, icon: AlertTriangle, color: 'text-red-600', bg: 'bg-red-50' },
    { label: 'مكررات مكتشفة', value: data.duplicates_detected, icon: Target, color: 'text-amber-600', bg: 'bg-amber-50' },
  ];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {kpiCards.map((kpi, i) => (
          <StatCard key={i} {...kpi} />
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border rounded-xl shadow-sm">
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
                const pct = Math.min(100, (t.count / Math.max(1, data.total_issues)) * 100);
                return (
                  <div key={i} className="group">
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="text-slate-600">{t.label}</span>
                      <span className="font-semibold text-brand-navy">{t.count}</span>
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

        <Card className="border rounded-xl shadow-sm">
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
                const pct = Math.min(100, (p.count / Math.max(1, data.total_issues)) * 100);
                return (
                  <div key={i}>
                    <div className="flex items-center justify-between text-sm mb-1">
                      <div className="flex items-center gap-2">
                        <div className={`w-2.5 h-2.5 rounded-full ${cfg.dotColor || 'bg-slate-400'}`} />
                        <span className="text-slate-600">{p.label || p.priority}</span>
                      </div>
                      <span className="font-semibold text-brand-navy">{p.count}</span>
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

        <Card className="border rounded-xl shadow-sm">
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
                const pct = Math.min(100, (t.count / Math.max(1, data.total_issues)) * 100);
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

        <Card className="border rounded-xl shadow-sm">
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

        <Card className="border rounded-xl shadow-sm">
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

        <Card className="border rounded-xl shadow-sm">
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
              {data.top_sections?.map((s, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <span className="text-slate-600">{s.section}</span>
                  <Badge variant="secondary" className="text-[11px]">{s.count}</Badge>
                </div>
              ))}
              {(!data.top_sections || data.top_sections.length === 0) && (
                <EmptyState title="لا توجد بيانات" className="py-8" />
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default ProductHubPage;
