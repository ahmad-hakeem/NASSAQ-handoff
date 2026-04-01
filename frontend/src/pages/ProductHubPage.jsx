import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Sidebar } from '../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import {
  StatusChip, PriorityBadge, SLAIndicator, StatCard, EmptyState, IssueKanbanCard,
  HakimInsightCard,
  STATUS_CONFIG, PRIORITY_CONFIG, TYPE_CONFIG, STATUS_PROGRESS, KANBAN_COLUMNS,
  formatDualDateCompact,
} from '../components/product-hub';
import {
  Brain, Plus, Search, BarChart3, Users, Target, Zap, Sparkles,
  ChevronLeft, ChevronRight, Award, Building2, Timer, AlertOctagon, Clock,
  Table2, Kanban, AlertTriangle, CheckCircle2, Bug, TrendingUp, Eye,
  RefreshCw, XCircle, ArrowUpRight, ArrowDownRight, ShieldCheck, CircleDot,
  Activity, Layers, ThumbsUp, ThumbsDown,
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
  const [highlightId, setHighlightId] = useState(searchParams.get('highlight') || '');

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
      setIssues(res.data.issues || []);
      setTotal(res.data.total || 0);
    } catch (e) {
      console.error('[ProductHub] fetchIssues failed:', e?.response?.status, e?.response?.data || e.message);
      if (e?.response?.status === 401) {
        toast.error('انتهت صلاحية الجلسة — يرجى تسجيل الدخول مرة أخرى');
      } else {
        toast.error('فشل في تحميل التحديات');
      }
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
    const hl = searchParams.get('highlight');
    if (hl) setHighlightId(hl);
  }, [searchParams]);

  useEffect(() => {
    if (!highlightId) return;
    const timer = setTimeout(() => {
      setHighlightId('');
      const fresh = new URLSearchParams(window.location.search);
      fresh.delete('highlight');
      setSearchParams(fresh, { replace: true });
    }, 5000);
    return () => clearTimeout(timer);
  }, [highlightId]);

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
                highlightId={highlightId}
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
              <KanbanView issues={kanbanIssues} loading={loading} total={total} highlightId={highlightId} />
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </Sidebar>
  );
}

function FilterToolbar({ filters, config, onFilterChange, onClear, hasActiveFilters }) {
  const activeCount = Object.values(filters).filter(v => v).length;

  return (
    <Card className="border shadow-sm rounded-xl">
      <CardContent className="p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="بحث في العنوان، المحتوى، الاسم..."
              value={filters.search}
              onChange={(e) => onFilterChange('search', e.target.value)}
              className="pr-10 text-right rounded-lg h-9"
            />
          </div>

          <Select value={filters.status || '_all'} onValueChange={(v) => onFilterChange('status', v === '_all' ? '' : v)}>
            <SelectTrigger className="w-[140px] rounded-lg h-9 text-xs">
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
            <SelectTrigger className="w-[130px] rounded-lg h-9 text-xs">
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

          {config && (
            <>
              <Select value={filters.issue_type || '_all'} onValueChange={(v) => onFilterChange('issue_type', v === '_all' ? '' : v)}>
                <SelectTrigger className="w-[130px] rounded-lg h-9 text-xs">
                  <SelectValue placeholder="النوع" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="_all">كل الأنواع</SelectItem>
                  {(config.issue_types || []).map(t => (
                    <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select value={filters.section || '_all'} onValueChange={(v) => onFilterChange('section', v === '_all' ? '' : v)}>
                <SelectTrigger className="w-[130px] rounded-lg h-9 text-xs">
                  <SelectValue placeholder="القسم" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="_all">كل الأقسام</SelectItem>
                  {(config.sections || []).map(s => (
                    <SelectItem key={s} value={s}>{s}</SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select value={filters.assigned_team || '_all'} onValueChange={(v) => onFilterChange('assigned_team', v === '_all' ? '' : v)}>
                <SelectTrigger className="w-[120px] rounded-lg h-9 text-xs">
                  <SelectValue placeholder="الفريق" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="_all">كل الفرق</SelectItem>
                  {(config.teams || []).map(t => (
                    <SelectItem key={t} value={t}>{t}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </>
          )}

          {hasActiveFilters && (
            <Button variant="ghost" size="sm" onClick={onClear} className="text-red-500 hover:text-red-700 hover:bg-red-50 rounded-lg h-9 px-3">
              <XCircle className="h-3.5 w-3.5 ml-1" />
              مسح ({activeCount})
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function getProgressColor(progress, status) {
  if (status === 'rejected') return 'bg-red-500';
  if (progress >= 100) return 'bg-emerald-500';
  if (progress >= 75) return 'bg-emerald-400';
  if (progress >= 50) return 'bg-brand-turquoise';
  if (progress >= 25) return 'bg-amber-400';
  return 'bg-red-400';
}

function getProgressGradient(progress, status) {
  if (status === 'rejected') return 'from-red-300 to-red-500';
  if (progress >= 100) return 'from-emerald-400 to-emerald-600';
  if (progress >= 75) return 'from-emerald-300 to-emerald-500';
  if (progress >= 50) return 'from-brand-turquoise/80 to-brand-turquoise';
  if (progress >= 25) return 'from-amber-300 to-amber-500';
  return 'from-red-300 to-red-500';
}

function getCardStyle(progress, status) {
  const isDone = status === 'done' || status === 'user_feedback_confirmed';
  const isRejected = status === 'rejected';
  if (isDone) return 'border-emerald-200 bg-emerald-50/30';
  if (isRejected) return 'border-red-200 bg-red-50/20';
  if (progress >= 50) return 'border-slate-200';
  return 'border-slate-200';
}

function IssueCard({ issue, navigate, isHighlighted }) {
  const typeCfg = TYPE_CONFIG[issue.issue_type] || TYPE_CONFIG.other;
  const TypeIcon = typeCfg.icon;
  const progress = STATUS_PROGRESS[issue.status] || 0;
  const isDone = issue.status === 'done' || issue.status === 'user_feedback_confirmed';
  const isRejected = issue.status === 'rejected';
  const cardBorder = getCardStyle(progress, issue.status);
  const cardRef = React.useRef(null);

  React.useEffect(() => {
    if (isHighlighted && cardRef.current) {
      cardRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [isHighlighted]);

  return (
    <Card
      ref={cardRef}
      onClick={() => navigate(`/admin/product-hub/issues/${issue.id}`)}
      className={`shadow-sm rounded-xl hover:shadow-lg cursor-pointer transition-all group overflow-hidden ${cardBorder} ${isHighlighted ? 'ring-2 ring-brand-turquoise ring-offset-2 animate-pulse' : ''}`}
    >
      <div className={`h-1 w-full bg-gradient-to-l ${getProgressGradient(progress, issue.status)}`} style={{ width: `${progress}%`, minWidth: progress > 0 ? '8px' : '0' }} />

      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-2 mb-2">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] font-mono text-muted-foreground bg-slate-100 px-1.5 py-0.5 rounded">
                #{issue.issue_number}
              </span>
              <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
                <TypeIcon className={`h-3 w-3 ${typeCfg.color}`} />
                <span>{typeCfg.label}</span>
              </div>
            </div>
            <h3 className={`text-sm font-bold leading-snug transition-colors ${isDone ? 'text-emerald-700 line-through decoration-emerald-300' : isRejected ? 'text-red-400 line-through decoration-red-200' : 'text-brand-navy group-hover:text-brand-turquoise'}`}>
              {issue.title}
            </h3>
          </div>
          <PriorityBadge priority={issue.priority} size="sm" showIcon />
        </div>

        {issue.current_behavior && (
          <p className="text-[11px] text-muted-foreground line-clamp-2 mb-2 leading-relaxed bg-slate-50/80 p-2 rounded-lg border border-slate-100">
            {issue.current_behavior}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-1.5 mb-2">
          <StatusChip status={issue.status} size="sm" showIcon />
          <SLAIndicator issue={issue} size="sm" />
          {issue.assigned_team && (
            <Badge variant="outline" className="text-[9px] border-brand-turquoise/30 text-brand-turquoise px-1.5 py-0">
              {issue.assigned_team}
            </Badge>
          )}
        </div>

        {issue.hakim_analysis && Object.keys(issue.hakim_analysis).length > 0 && (
          <div className="flex items-center gap-1.5 mb-2 px-2 py-1 bg-brand-turquoise/5 rounded-md border border-brand-turquoise/10">
            <Brain className="h-2.5 w-2.5 text-brand-turquoise flex-shrink-0" />
            <span className="text-[9px] text-brand-turquoise font-medium">حكيم</span>
            {issue.hakim_analysis.suggested_team && (
              <span className="text-[9px] text-muted-foreground truncate">
                {issue.hakim_analysis.suggested_team}
              </span>
            )}
            {issue.hakim_analysis.duplicate_ids?.length > 0 && (
              <span className="text-[9px] text-amber-600 flex items-center gap-0.5">
                <AlertTriangle className="h-2 w-2" />
                {issue.hakim_analysis.duplicate_ids.length}
              </span>
            )}
          </div>
        )}

        <div className="mb-2">
          <div className="flex items-center justify-between mb-1">
            <span className={`text-[10px] font-semibold ${getProgressColor(progress, issue.status).replace('bg-', 'text-')}`}>
              {progress}%
            </span>
            <span className="text-[9px] text-muted-foreground">
              {isDone ? 'مكتمل' : isRejected ? 'مرفوض' : 'التقدم'}
            </span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
            <div
              className={`h-2 rounded-full bg-gradient-to-l ${getProgressGradient(progress, issue.status)} transition-all duration-500`}
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        <div className="flex items-center justify-between text-[10px] text-muted-foreground">
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-0.5">
              <Users className="h-2.5 w-2.5" />
              {issue.employee_name}
            </span>
            <span>{issue.section}</span>
          </div>
          <span>{formatDualDateCompact(issue.created_at)}</span>
        </div>
      </CardContent>
    </Card>
  );
}

function IssuesTableView({ issues, loading, total, page, totalPages, onPageChange, navigate, highlightId }) {
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
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {issues.map(issue => (
          <IssueCard key={issue.id} issue={issue} navigate={navigate} isHighlighted={highlightId === issue.id} />
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

function KanbanView({ issues, loading, total, highlightId }) {
  if (loading) {
    return (
      <div className="flex justify-center items-center py-24">
        <div className="flex flex-col items-center gap-4">
          <div className="relative">
            <div className="animate-spin rounded-full h-10 w-10 border-[3px] border-brand-turquoise/20 border-t-brand-turquoise" />
            <Kanban className="absolute inset-0 m-auto h-4 w-4 text-brand-turquoise animate-pulse" />
          </div>
          <p className="text-sm text-slate-400 font-medium">جاري تحميل اللوحة...</p>
        </div>
      </div>
    );
  }

  if (total === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-turquoise/10 to-brand-navy/10 flex items-center justify-center">
          <Kanban className="h-8 w-8 text-brand-turquoise/50" />
        </div>
        <div className="text-center space-y-1">
          <h3 className="text-base font-bold text-slate-700">لا توجد تحديات</h3>
          <p className="text-sm text-slate-400">ستظهر التحديات هنا بمجرد إنشائها</p>
        </div>
      </div>
    );
  }

  const COLUMN_STYLES = {
    new: { gradient: 'from-blue-500 to-blue-600', glow: 'shadow-blue-500/10', bgPattern: 'bg-[radial-gradient(circle_at_50%_0%,rgba(59,130,246,0.04),transparent_70%)]' },
    under_review: { gradient: 'from-amber-500 to-amber-600', glow: 'shadow-amber-500/10', bgPattern: 'bg-[radial-gradient(circle_at_50%_0%,rgba(245,158,11,0.04),transparent_70%)]' },
    in_progress: { gradient: 'from-violet-500 to-violet-600', glow: 'shadow-violet-500/10', bgPattern: 'bg-[radial-gradient(circle_at_50%_0%,rgba(139,92,246,0.04),transparent_70%)]' },
    qa_validation: { gradient: 'from-cyan-500 to-cyan-600', glow: 'shadow-cyan-500/10', bgPattern: 'bg-[radial-gradient(circle_at_50%_0%,rgba(6,182,212,0.04),transparent_70%)]' },
    done: { gradient: 'from-emerald-500 to-emerald-600', glow: 'shadow-emerald-500/10', bgPattern: 'bg-[radial-gradient(circle_at_50%_0%,rgba(16,185,129,0.04),transparent_70%)]' },
    rejected: { gradient: 'from-red-500 to-red-600', glow: 'shadow-red-500/10', bgPattern: 'bg-[radial-gradient(circle_at_50%_0%,rgba(239,68,68,0.04),transparent_70%)]' },
    user_feedback_confirmed: { gradient: 'from-emerald-500 to-teal-600', glow: 'shadow-emerald-500/10', bgPattern: 'bg-[radial-gradient(circle_at_50%_0%,rgba(16,185,129,0.04),transparent_70%)]' },
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between bg-white/60 backdrop-blur-sm rounded-xl border border-slate-200/60 px-4 py-2.5">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <Kanban className="h-4 w-4 text-brand-turquoise" />
            <span className="text-sm font-bold text-brand-navy">لوحة كانبان</span>
          </div>
          <div className="h-4 w-px bg-slate-200" />
          <span className="text-xs text-slate-400">
            <span className="font-semibold text-brand-navy">{total}</span> تحدي
          </span>
        </div>
        <div className="flex items-center gap-2">
          {KANBAN_COLUMNS.slice(0, 5).map(status => {
            const cfg = STATUS_CONFIG[status];
            const count = (issues[status] || []).length;
            if (count === 0) return null;
            return (
              <div key={status} className="flex items-center gap-1">
                <div className={`w-2 h-2 rounded-full ${cfg.color}`} />
                <span className="text-[10px] text-slate-500 font-medium">{count}</span>
              </div>
            );
          })}
        </div>
      </div>

      <div className="overflow-x-auto pb-4 -mx-1 px-1 scrollbar-thin" style={{ scrollbarWidth: 'thin' }}>
        <div className="flex gap-3" style={{ minWidth: `${KANBAN_COLUMNS.length * 260}px` }}>
          {KANBAN_COLUMNS.map(status => {
            const cfg = STATUS_CONFIG[status];
            const colStyle = COLUMN_STYLES[status];
            const columnIssues = issues[status] || [];
            return (
              <div key={status} className={`flex-1 min-w-[240px] max-w-[300px] flex flex-col rounded-2xl border border-slate-200/60 bg-white/40 backdrop-blur-sm overflow-hidden shadow-sm ${colStyle.glow}`}>
                <div className="relative px-4 py-3">
                  <div className={`absolute inset-x-0 top-0 h-[3px] bg-gradient-to-l ${colStyle.gradient}`} />
                  <div className="flex items-center justify-between pt-1">
                    <div className="flex items-center gap-2.5">
                      <div className={`w-7 h-7 rounded-lg bg-gradient-to-br ${colStyle.gradient} flex items-center justify-center shadow-sm`}>
                        <cfg.icon className="h-3.5 w-3.5 text-white" />
                      </div>
                      <div className="flex flex-col">
                        <span className="text-[13px] font-bold text-slate-800 leading-none">{cfg.label}</span>
                        <span className="text-[10px] text-slate-400 mt-0.5">{cfg.labelEn}</span>
                      </div>
                    </div>
                    <div className={`min-w-[24px] h-6 px-2 rounded-lg bg-gradient-to-br ${colStyle.gradient} flex items-center justify-center`}>
                      <span className="text-[11px] font-bold text-white">{columnIssues.length}</span>
                    </div>
                  </div>
                </div>

                <div
                  className={`flex-1 px-2.5 pb-2.5 space-y-2.5 min-h-[180px] max-h-[560px] overflow-y-auto ${colStyle.bgPattern}`}
                  style={{ scrollbarWidth: 'thin' }}
                >
                  {columnIssues.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-36 text-slate-300 gap-3">
                      <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${colStyle.gradient} opacity-10 flex items-center justify-center`}>
                        <cfg.icon className="h-5 w-5 text-slate-500" />
                      </div>
                      <span className="text-[11px] text-slate-400">لا توجد تحديات</span>
                    </div>
                  ) : (
                    columnIssues.map(issue => (
                      <IssueKanbanCard key={issue.id} issue={issue} isHighlighted={highlightId === issue.id} />
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
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

  const total = data.total_issues || 0;
  const resolved = data.total_resolved || 0;
  const open = data.total_open || 0;
  const rejected = data.total_rejected || 0;
  const resRate = data.resolution_rate || 0;
  const unresolvedPct = total > 0 ? Math.round((open / total) * 100) : 0;
  const resolvedPct = total > 0 ? Math.round((resolved / total) * 100) : 0;
  const rejectedPct = total > 0 ? Math.round((rejected / total) * 100) : 0;

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
        <div className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-brand-navy to-brand-navy/90 p-5 shadow-lg text-white">
          <div className="flex items-start justify-between">
            <div className="p-2.5 rounded-xl bg-white/10">
              <Layers className="h-5 w-5 text-white" />
            </div>
            {data.new_this_week > 0 && (
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-white/15 flex items-center gap-0.5">
                <ArrowUpRight className="h-3 w-3" />
                +{data.new_this_week} هذا الأسبوع
              </span>
            )}
          </div>
          <div className="mt-3">
            <p className="text-4xl font-bold tracking-tight">{total}</p>
            <p className="text-sm text-white/70 mt-0.5">إجمالي التحديات</p>
          </div>
          <div className="absolute -bottom-6 -left-6 h-24 w-24 rounded-full bg-white/5" />
        </div>

        <div className="relative overflow-hidden rounded-2xl border bg-white p-5 shadow-sm group hover:shadow-md transition-all">
          <div className="flex items-start justify-between">
            <div className="p-2.5 rounded-xl bg-emerald-50 transition-transform group-hover:scale-110">
              <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            </div>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700">
              {resolvedPct}%
            </span>
          </div>
          <div className="mt-3">
            <p className="text-4xl font-bold text-brand-navy tracking-tight">{resolved}</p>
            <p className="text-sm text-muted-foreground mt-0.5">تم حلها</p>
          </div>
          <div className="mt-2 w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
            <div className="bg-emerald-500 h-1.5 rounded-full transition-all duration-700" style={{ width: `${resolvedPct}%` }} />
          </div>
          <div className="absolute -bottom-4 -left-4 h-20 w-20 rounded-full bg-emerald-50 opacity-50" />
        </div>

        <div className="relative overflow-hidden rounded-2xl border bg-white p-5 shadow-sm group hover:shadow-md transition-all">
          <div className="flex items-start justify-between">
            <div className="p-2.5 rounded-xl bg-amber-50 transition-transform group-hover:scale-110">
              <AlertTriangle className="h-5 w-5 text-amber-600" />
            </div>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-50 text-amber-700">
              {unresolvedPct}%
            </span>
          </div>
          <div className="mt-3">
            <p className="text-4xl font-bold text-brand-navy tracking-tight">{open}</p>
            <p className="text-sm text-muted-foreground mt-0.5">لم تُحل بعد</p>
          </div>
          <div className="mt-2 w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
            <div className="bg-amber-500 h-1.5 rounded-full transition-all duration-700" style={{ width: `${unresolvedPct}%` }} />
          </div>
          <div className="absolute -bottom-4 -left-4 h-20 w-20 rounded-full bg-amber-50 opacity-50" />
        </div>

        <div className="relative overflow-hidden rounded-2xl border bg-white p-5 shadow-sm group hover:shadow-md transition-all">
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
            <p className="text-4xl font-bold text-brand-navy tracking-tight">{data.critical_open || 0}</p>
            <p className="text-sm text-muted-foreground mt-0.5">حرجة مفتوحة</p>
          </div>
          <div className="mt-2 w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
            <div className="bg-red-500 h-1.5 rounded-full transition-all duration-700" style={{ width: `${total > 0 ? Math.round(((data.critical_open || 0) / total) * 100) : 0}%` }} />
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
