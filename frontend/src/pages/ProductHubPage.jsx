import React, { useState, useEffect, useCallback, useMemo, useRef, useLayoutEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Sidebar } from '../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import {
  StatusChip, PriorityBadge, SLAIndicator, StatCard, EmptyState,
  HakimInsightCard, CommentInput, CommentBubble,
  STATUS_CONFIG, PRIORITY_CONFIG, TYPE_CONFIG, STATUS_PROGRESS, COMMENT_TYPE_CONFIG,
  formatDualDateCompact, getInitials, getUserColor,
} from '../components/product-hub';
import {
  Brain, Plus, Search, BarChart3, Users, Target, Zap, Sparkles,
  ChevronLeft, ChevronRight, Award, Building2, Timer, AlertOctagon, Clock,
  AlertTriangle, CheckCircle2, Bug, TrendingUp, Eye,
  RefreshCw, XCircle, ArrowUpRight, ArrowDownRight, ShieldCheck, CircleDot,
  Activity, Layers, ThumbsUp, ThumbsDown, Copy, MessageSquare, FileText, Paperclip, ExternalLink,
  ChevronDown, ChevronUp, Minimize2, Send, Loader2, Wand2, ListChecks,
} from 'lucide-react';

const authHeaders = () => {
  const t = localStorage.getItem('nassaq_token');
  return t ? { Authorization: `Bearer ${t}` } : {};
};

const SLA_HOURS = { critical: 24, high: 72, medium: 120, low: 240 };

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

function computePredictions(issue, _nowBucket) {
  const progress = STATUS_PROGRESS[issue.status] || 0;
  const isDone = issue.status === 'done' || issue.status === 'user_feedback_confirmed' || issue.status === 'rejected';
  if (isDone) return { risk: 'low', delay: 'on_track', escalation: 'stable' };

  const created = new Date(issue.created_at);
  if (isNaN(created.getTime())) return { risk: 'medium', delay: 'on_track', escalation: 'stable' };

  const now = new Date();
  const hoursElapsed = (now - created) / (1000 * 60 * 60);
  const daysElapsed = hoursElapsed / 24;
  const slaHours = SLA_HOURS[issue.priority] || 120;
  const slaRatio = hoursElapsed / slaHours;
  const progressRatio = progress / 100;

  let riskScore = 0;
  if (issue.priority === 'critical') riskScore += 3;
  else if (issue.priority === 'high') riskScore += 2;
  else if (issue.priority === 'medium') riskScore += 1;

  if (issue.sla_status === 'exceeded') riskScore += 3;
  else if (typeof issue.sla_remaining_hours === 'number' && issue.sla_remaining_hours <= 12) riskScore += 2;

  if (slaRatio > 0.8 && progressRatio < 0.5) riskScore += 2;
  if (slaRatio > 0.5 && progressRatio < 0.25) riskScore += 1;
  if (issue.hakim_analysis?.duplicate_ids?.length > 0) riskScore += 1;

  const risk = riskScore >= 5 ? 'high' : riskScore >= 3 ? 'medium' : 'low';

  let delay = 'on_track';
  const velocityGap = slaRatio - progressRatio;
  if (issue.sla_status === 'exceeded') delay = 'likely_delayed';
  else if (velocityGap > 0.5) delay = 'likely_delayed';
  else if (velocityGap > 0.2 && daysElapsed > 2) delay = 'at_risk';

  let escalation = 'stable';
  if (riskScore >= 5 && progressRatio < 0.3) escalation = 'escalating';
  else if (riskScore >= 3 && slaRatio > 0.7 && progressRatio < 0.5) escalation = 'escalating';
  else if (isDone || progressRatio > 0.7) escalation = 'decreasing';

  return { risk, delay, escalation, riskScore };
}

const PREDICTION_CFG = {
  delay: {
    on_track: { label: 'في الموعد', labelEn: 'On Track', icon: '✅', color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200' },
    at_risk: { label: 'معرض للتأخير', labelEn: 'At Risk', icon: '⚠️', color: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-200' },
    likely_delayed: { label: 'متأخر محتمل', labelEn: 'Likely Delayed', icon: '🔴', color: 'text-red-700', bg: 'bg-red-50', border: 'border-red-200' },
  },
  escalation: {
    stable: { label: 'مستقر', labelEn: 'Stable', icon: '➡️', color: 'text-slate-600', bg: 'bg-slate-50', border: 'border-slate-200' },
    escalating: { label: 'خطر متصاعد', labelEn: 'Escalating', icon: '📈', color: 'text-red-700', bg: 'bg-red-50', border: 'border-red-200' },
    decreasing: { label: 'خطر متناقص', labelEn: 'Decreasing', icon: '📉', color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200' },
  },
  risk: {
    high: { label: 'خطر عالي', labelEn: 'High Risk', dot: 'bg-red-500', color: 'text-red-700', bg: 'bg-red-50', border: 'border-red-200', tooltip: 'هذا التحدي يؤثر على وظائف أساسية أو يمنع المستخدمين' },
    medium: { label: 'خطر متوسط', labelEn: 'Medium Risk', dot: 'bg-amber-500', color: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-200', tooltip: 'هذا التحدي يحتاج متابعة ومعالجة في الوقت المناسب' },
    low: { label: 'خطر منخفض', labelEn: 'Low Risk', dot: 'bg-emerald-500', color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200', tooltip: 'هذا التحدي تحت السيطرة ولا يشكل خطراً حالياً' },
  },
};

const HEATMAP_CFG = {
  critical: { bg: 'bg-red-50/50', hoverBg: 'hover:bg-red-50/70', borderAccent: 'border-r-red-500', glow: 'shadow-red-100/50' },
  high: { bg: 'bg-orange-50/40', hoverBg: 'hover:bg-orange-50/60', borderAccent: 'border-r-orange-400', glow: 'shadow-orange-100/50' },
  medium: { bg: 'bg-amber-50/25', hoverBg: 'hover:bg-amber-50/40', borderAccent: 'border-r-amber-400', glow: '' },
  low: { bg: 'bg-slate-50/30', hoverBg: 'hover:bg-slate-50/50', borderAccent: 'border-r-slate-300', glow: '' },
};

const PROGRESS_STATUS_COLOR = {
  new: 'from-blue-400 to-blue-500',
  under_review: 'from-amber-400 to-amber-500',
  in_progress: 'from-violet-400 to-violet-500',
  qa_validation: 'from-cyan-400 to-cyan-500',
  done: 'from-emerald-400 to-emerald-500',
  user_feedback_confirmed: 'from-emerald-500 to-emerald-600',
  rejected: 'from-red-400 to-red-500',
};

export function ProductHubPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'issues');
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
    created_by: '',
  });

  const isAdmin = user?.role === 'platform_admin';
  const isMainAdmin = config?.is_main_admin || false;
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
    setFilters({ status: '', issue_type: '', priority: '', section: '', assigned_team: '', search: '', date_from: '', date_to: '', created_by: '' });
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
          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-brand-navy via-brand-navy/95 to-brand-purple p-6 sm:p-8 text-white shadow-2xl">
            <div className="absolute inset-0 nassaq-pattern opacity-[0.06]" style={{ backgroundImage: "url('/nassaq-pattern.png')" }} />
            <div className="relative flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="space-y-2">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-white/10 rounded-xl backdrop-blur-sm">
                    <Brain className="h-6 w-6" />
                  </div>
                  <div>
                    <h1 className="text-2xl sm:text-3xl font-bold font-cairo">
                      مركز ذكاء المنتج
                    </h1>
                    <p className="text-white/70 text-sm font-tajawal">
                      نظام الحوكمة والتتبع الذكي الداخلي
                    </p>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {isMainAdmin && (
                  <Button
                    variant="outline"
                    size="sm"
                    className={`border-white/20 hover:bg-white/10 ${activeTab === 'dashboard' ? 'bg-white/20 text-white' : 'text-white'}`}
                    onClick={() => handleTabChange(activeTab === 'dashboard' ? 'issues' : 'dashboard')}
                  >
                    <BarChart3 className="h-4 w-4 me-1.5" />
                    لوحة القيادة
                  </Button>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  className="border-white/20 text-white hover:bg-white/10"
                  onClick={() => { fetchIssues(); fetchDashboard(); }}
                >
                  <RefreshCw className="h-4 w-4" />
                </Button>
                <Button
                  size="sm"
                  onClick={() => navigate('/admin/product-hub/submit')}
                  className="bg-brand-turquoise hover:bg-brand-turquoise/90 text-white shadow-lg shadow-brand-turquoise/20"
                >
                  <Plus className="h-4 w-4 me-1.5" />
                  إضافة تحدي جديد
                </Button>
              </div>
            </div>
          </div>

          {activeTab === 'dashboard' && isMainAdmin && (
            <DashboardView data={dashboard} loading={dashLoading} isAdmin={isMainAdmin} navigate={navigate} />
          )}

          {activeTab !== 'dashboard' && (
            <div className="space-y-5">
              <FilterToolbar
                filters={filters}
                config={config}
                onFilterChange={updateFilter}
                onClear={clearFilters}
                hasActiveFilters={hasActiveFilters}
              />

              <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
                <div className="lg:col-span-3">
                  <IssuesStatusFlow issues={issues} onStatusFilter={updateFilter} activeStatus={filters.status} />
                </div>
                <div className="relative overflow-hidden flex flex-col items-center justify-center text-center p-5 rounded-2xl bg-gradient-to-br from-brand-navy via-brand-navy/95 to-brand-turquoise/80 text-white shadow-lg">
                  <div className="absolute -bottom-6 -left-6 h-20 w-20 rounded-full bg-brand-turquoise/15" />
                  <div className="absolute -top-4 -right-4 h-14 w-14 rounded-full bg-white/5" />
                  <div className="relative z-10 flex flex-col items-center gap-1">
                    <div className="p-2 rounded-xl bg-white/10 backdrop-blur-sm mb-1">
                      <Layers className="h-5 w-5 text-white" />
                    </div>
                    <p className="text-5xl font-extrabold tracking-tighter leading-none tabular-nums hub-countup-number">
                      {total.toLocaleString('ar-SA')}
                    </p>
                    <p className="text-[11px] text-white/65 font-medium mt-1">إجمالي التحديات</p>
                    {hasActiveFilters && (
                      <p className="text-[10px] text-brand-turquoise font-medium mt-1 bg-white/10 px-2 py-0.5 rounded-full">
                        عرض {sortedIssues.length} من {total} نتيجة
                      </p>
                    )}
                  </div>
                </div>
              </div>

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
                isMainAdmin={isMainAdmin}
                onRefresh={fetchIssues}
              />
            </div>
          )}
        </div>
      </div>
    </Sidebar>
  );
}

function FilterToolbar({ filters, config, onFilterChange, onClear, hasActiveFilters }) {
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

function getProgressGradient(progress, status) {
  if (status === 'rejected') return 'from-red-300 to-red-500';
  if (progress >= 100) return 'from-emerald-400 to-emerald-600';
  if (progress >= 75) return 'from-emerald-300 to-emerald-500';
  if (progress >= 50) return 'from-brand-turquoise/80 to-brand-turquoise';
  if (progress >= 25) return 'from-amber-300 to-amber-500';
  return 'from-red-300 to-red-500';
}

function IssuesStatusFlow({ issues, onStatusFilter, activeStatus }) {
  const counts = useMemo(() => {
    const c = { new: 0, under_review: 0, in_progress: 0, qa_validation: 0, done: 0, user_feedback_confirmed: 0, rejected: 0 };
    (issues || []).forEach(issue => {
      if (c[issue.status] !== undefined) c[issue.status]++;
    });
    return c;
  }, [issues]);

  const total = issues?.length || 0;

  const flow = [
    { key: 'new', label: 'جديدة', value: counts.new, color: 'bg-sky-500', icon: CircleDot },
    { key: 'under_review', label: 'قيد المراجعة', value: counts.under_review, color: 'bg-amber-500', icon: Eye },
    { key: 'in_progress', label: 'قيد التنفيذ', value: counts.in_progress, color: 'bg-violet-500', icon: Activity },
    { key: 'qa_validation', label: 'فحص الجودة', value: counts.qa_validation, color: 'bg-blue-500', icon: ShieldCheck },
    { key: 'done,user_feedback_confirmed', label: 'تم الحل', value: counts.done + counts.user_feedback_confirmed, color: 'bg-emerald-500', icon: CheckCircle2 },
    { key: 'rejected', label: 'مرفوضة', value: counts.rejected, color: 'bg-red-500', icon: XCircle },
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
              <div key={i} className={`${s.color} h-3 transition-all duration-700 first:rounded-r-full last:rounded-l-full`} style={{ width: `${pct}%` }} title={`${s.label}: ${s.value}`} />
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
                className={`text-center p-2.5 rounded-xl border transition-all duration-200 cursor-pointer ${isActive ? 'bg-brand-navy/5 border-brand-navy/30 ring-1 ring-brand-navy/20 shadow-sm' : 'bg-slate-50/60 border-slate-100 hover:border-slate-200 hover:bg-white hover:shadow-sm'}`}
              >
                <div className="flex items-center justify-center mb-1">
                  <div className={`w-2 h-2 rounded-full ${s.color} ml-1`} />
                  <Ic className="h-3 w-3 text-slate-500" />
                </div>
                <p className="text-lg font-bold text-brand-navy">{s.value}</p>
                <p className="text-[9px] text-muted-foreground leading-tight">{s.label}</p>
              </button>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

function IssuePanel({ issue, navigate, isHighlighted, isMainAdmin, isAdmin, userId, onRefresh, isExpanded, onToggleExpand }) {
  const typeCfg = TYPE_CONFIG[issue.issue_type] || TYPE_CONFIG.other;
  const TypeIcon = typeCfg.icon;
  const progress = STATUS_PROGRESS[issue.status] || 0;
  const isDone = issue.status === 'done' || issue.status === 'user_feedback_confirmed';
  const isRejected = issue.status === 'rejected';
  const cardRef = useRef(null);
  const [generating, setGenerating] = useState(false);
  const [copied, setCopied] = useState(false);
  const [detailData, setDetailData] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(false);
  const [commentType, setCommentType] = useState('general');
  const [submittingComment, setSubmittingComment] = useState(false);
  const [reanalyzing, setReanalyzing] = useState(false);
  const commentCount = issue.comment_count || 0;
  const attachmentCount = issue.attachments?.length || 0;
  const hasDuplicates = issue.hakim_analysis?.duplicate_ids?.length > 0;
  const recentComments = issue.recent_comments || [];

  useEffect(() => {
    if (isHighlighted && cardRef.current) {
      cardRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [isHighlighted]);

  useEffect(() => {
    if (isExpanded && !detailData && !detailLoading && !detailError) {
      setDetailLoading(true);
      axios.get(`/api/product-hub/issues/${issue.id}`, { headers: authHeaders() })
        .then(res => { setDetailData(res.data); setDetailError(false); })
        .catch(() => { toast.error('فشل في تحميل التفاصيل'); setDetailError(true); })
        .finally(() => setDetailLoading(false));
    }
  }, [isExpanded, issue.id, detailData, detailLoading, detailError]);

  const refetchDetail = useCallback(async () => {
    try {
      const res = await axios.get(`/api/product-hub/issues/${issue.id}`, { headers: authHeaders() });
      setDetailData(res.data);
    } catch {}
    if (onRefresh) onRefresh();
  }, [issue.id, onRefresh]);

  const handleGenerate = async (e) => {
    if (e) e.stopPropagation();
    setGenerating(true);
    try {
      await axios.post(`/api/product-hub/issues/${issue.id}/generate-prompt`, {}, { headers: authHeaders() });
      toast.success('تم إنشاء البرومبت');
      await refetchDetail();
    } catch {
      toast.error('فشل في إنشاء البرومبت');
    } finally {
      setGenerating(false);
    }
  };

  const handleCopy = async (e) => {
    if (e) e.stopPropagation();
    const prompt = detailData?.generated_prompt || issue.generated_prompt;
    if (prompt) {
      try {
        await navigator.clipboard.writeText(prompt);
        setCopied(true);
        toast.success('تم نسخ البرومبت');
        setTimeout(() => setCopied(false), 2000);
      } catch {
        toast.error('فشل في النسخ');
      }
    }
  };

  const handleComment = async (content, mentions = []) => {
    if (!content.trim()) return;
    setSubmittingComment(true);
    try {
      await axios.post(`/api/product-hub/issues/${issue.id}/comments`, {
        content, comment_type: isMainAdmin ? commentType : 'general', mentions
      }, { headers: authHeaders() });
      toast.success('تم إضافة التعليق');
      setCommentType('general');
      await refetchDetail();
    } catch (err) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'object' ? detail.message : (detail || 'فشل في إضافة التعليق'));
    } finally {
      setSubmittingComment(false);
    }
  };

  const handleEditComment = async (commentId, content, mentions = []) => {
    try {
      await axios.put(`/api/product-hub/issues/${issue.id}/comments/${commentId}`, { content, mentions }, { headers: authHeaders() });
      toast.success('تم تعديل التعليق');
      await refetchDetail();
    } catch (err) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'object' ? detail.message : (detail || 'فشل في تعديل التعليق'));
    }
  };

  const handleDeleteComment = async (commentId) => {
    try {
      await axios.delete(`/api/product-hub/issues/${issue.id}/comments/${commentId}`, { headers: authHeaders() });
      toast.success('تم حذف التعليق');
      await refetchDetail();
    } catch {
      toast.error('فشل في حذف التعليق');
    }
  };

  const handleReanalyze = async (e) => {
    if (e) e.stopPropagation();
    setReanalyzing(true);
    try {
      const res = await axios.post(`/api/product-hub/issues/${issue.id}/reanalyze`, {}, { headers: authHeaders() });
      if (res.data?.hakim_analysis) {
        setDetailData(prev => prev ? { ...prev, hakim_analysis: res.data.hakim_analysis } : prev);
      }
      toast.success('تم إعادة تحليل حكيم بنجاح');
      if (onRefresh) onRefresh();
    } catch {
      toast.error('فشل في إعادة التحليل');
    } finally {
      setReanalyzing(false);
    }
  };

  const heatmap = HEATMAP_CFG[issue.priority] || HEATMAP_CFG.medium;
  const nowBucket = useMemo(() => Math.floor(Date.now() / (5 * 60 * 1000)), []);
  const predictions = useMemo(() => computePredictions(issue, nowBucket), [issue, nowBucket]);
  const riskCfg = PREDICTION_CFG.risk[predictions.risk];
  const delayCfg = PREDICTION_CFG.delay[predictions.delay];
  const escalationCfg = PREDICTION_CFG.escalation[predictions.escalation];
  const progressColor = PROGRESS_STATUS_COLOR[issue.status] || 'from-slate-300 to-slate-500';
  const isHighRiskLowProgress = (predictions.risk === 'high' && progress < 50);

  const comments = detailData?.comments || [];
  const hakimAnalysis = detailData?.hakim_analysis || issue.hakim_analysis;
  const promptText = detailData?.generated_prompt || issue.generated_prompt;

  const statusLabel = STATUS_CONFIG[issue.status]?.label || issue.status;

  return (
    <div
      ref={cardRef}
      className={`w-full rounded-2xl border overflow-hidden group hub-card ${
        isDone
          ? 'bg-gradient-to-l from-emerald-50/80 via-emerald-50/40 to-white border-emerald-200/60 hub-card-done'
          : isRejected
          ? 'bg-gradient-to-l from-red-50/50 via-red-50/20 to-white border-red-200/50'
          : 'bg-white border-slate-200'
      } ${isExpanded ? 'md:col-span-2 hub-card-expanded border-brand-turquoise/40 shadow-[0_8px_32px_rgba(70,193,190,0.12)] ring-1 ring-brand-turquoise/15' : `hover:shadow-[0_4px_16px_rgba(0,0,0,0.06)] ${!isDone && !isRejected ? 'hover:border-slate-300' : ''}`} ${isHighlighted ? 'ring-2 ring-brand-turquoise ring-offset-2' : ''}`}
    >
      {/* ═══════════════ COLLAPSED STATE ═══════════════ */}
      <div
        onClick={() => onToggleExpand(issue.id)}
        className="cursor-pointer"
      >
        {/* ─── ROW 1: Title + Issue Number + Expand ─── */}
        <div className="px-5 pt-5 pb-2.5">
          <div className="flex items-start gap-3" dir="rtl">
            <div className="flex-1 min-w-0 text-right">
              <h3 className={`text-base font-bold leading-relaxed ${isDone ? 'text-emerald-800' : isRejected ? 'text-red-400' : 'text-brand-navy'}`}>
                {isDone && <CheckCircle2 className="h-4 w-4 text-emerald-500 inline-block ml-1.5 -mt-0.5" />}
                {issue.title}
              </h3>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0 pt-0.5">
              {hasDuplicates && (
                <div className="flex items-center gap-1 px-1.5 py-0.5 bg-amber-50 rounded-md border border-amber-100">
                  <Copy className="h-2.5 w-2.5 text-amber-500" />
                  <span className="text-[9px] text-amber-600 font-semibold">مكرر</span>
                </div>
              )}
              <span className="text-[10px] font-mono text-slate-400 bg-slate-50 px-2 py-1 rounded-md font-semibold border border-slate-100">
                #{issue.issue_number}
              </span>
              <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${isExpanded ? 'bg-brand-turquoise/10 text-brand-turquoise' : 'bg-slate-50 text-slate-400 group-hover:bg-slate-100'}`}>
                <ChevronDown className={`h-4 w-4 hub-chevron ${isExpanded ? 'hub-chevron-open' : ''}`} />
              </div>
            </div>
          </div>
        </div>

        {/* ─── ROW 2: Reporter + Badges ─── */}
        <div className="px-5 pb-3" dir="rtl">
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-2">
              <div
                className="w-6 h-6 rounded-full flex items-center justify-center text-[8px] font-bold text-white flex-shrink-0 shadow-sm"
                style={{ background: isDone ? 'linear-gradient(135deg, #10b981, #059669)' : isRejected ? 'linear-gradient(135deg, #ef4444, #dc2626)' : 'linear-gradient(135deg, #1C3D74, #46C1BE)' }}
              >
                {getInitials(issue.employee_name)}
              </div>
              <span className="text-[11px] font-semibold text-brand-navy truncate max-w-[130px]">{issue.employee_name}</span>
            </div>
            <div className="w-px h-4 bg-slate-200" />
            <StatusChip status={issue.status} size="default" showIcon />
            <PriorityBadge priority={issue.priority} size="sm" showIcon />
            <SLAIndicator issue={issue} size="sm" />
            {issue.assigned_team && (
              <Badge variant="outline" className="text-[9px] border-brand-turquoise/20 text-brand-turquoise px-2 py-0.5 h-5 font-medium max-md:hidden rounded-md">
                {issue.assigned_team}
              </Badge>
            )}
          </div>
        </div>

        {/* ─── ROW 3: Progress Bar ─── */}
        <div className="px-5 pb-3" dir="rtl">
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-slate-500 font-medium">التقدم</span>
              <span className="text-[10px] text-slate-400">({statusLabel})</span>
            </div>
            <span className={`text-xs font-bold tabular-nums ${progress >= 75 ? 'text-emerald-600' : progress >= 50 ? 'text-brand-turquoise' : progress >= 25 ? 'text-amber-500' : 'text-red-500'}`}>
              {progress}%
            </span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
            <div
              className={`h-full rounded-full bg-gradient-to-l ${progressColor} hub-progress-fill`}
              style={{ width: `${Math.max(progress, 2)}%` }}
            />
          </div>
        </div>


        {/* ─── ROW 4: Footer — Date + Metadata ─── */}
        <div className="px-5 pb-4 pt-1" dir="rtl">
          <div className="flex items-center justify-between border-t border-slate-100 pt-2.5">
            <div className="flex items-center gap-2">
              <Clock className="h-3 w-3 text-slate-300" />
              <span className="text-[10px] text-slate-400">{formatDualDateCompact(issue.created_at)}</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1 text-[10px] text-slate-400">
                <MessageSquare className="h-3 w-3" />
                <span className="font-semibold">{commentCount}</span>
              </div>
              {attachmentCount > 0 && (
                <div className="flex items-center gap-1 text-[10px] text-slate-400">
                  <Paperclip className="h-3 w-3" />
                  <span className="font-semibold">{attachmentCount}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ═══════════════ EXPANDED STATE ═══════════════ */}
      <div
        className="overflow-hidden hub-expand-content"
        style={{
          maxHeight: isExpanded ? '2000px' : '0px',
          opacity: isExpanded ? 1 : 0,
        }}
      >
        <div className="border-t border-slate-100">
          {detailLoading ? (
            <div className="p-5 space-y-4">
              <div className="flex items-center gap-3">
                <div className="hub-skeleton w-10 h-10 rounded-full" />
                <div className="flex-1 space-y-2">
                  <div className="hub-skeleton h-4 w-3/4 rounded-md" />
                  <div className="hub-skeleton h-3 w-1/2 rounded-md" />
                </div>
              </div>
              <div className="hub-skeleton h-20 w-full rounded-xl" />
              <div className="hub-skeleton h-16 w-full rounded-xl" />
              <div className="flex gap-2">
                <div className="hub-skeleton h-9 flex-1 rounded-lg" />
              </div>
            </div>
          ) : detailError ? (
            <div className="flex justify-center items-center py-16">
              <div className="flex flex-col items-center gap-3">
                <AlertTriangle className="h-8 w-8 text-amber-400" />
                <p className="text-sm text-muted-foreground">فشل في تحميل التفاصيل</p>
                <Button variant="outline" size="sm" onClick={() => { setDetailError(false); }} className="gap-1.5">
                  <RefreshCw className="h-3.5 w-3.5" /> إعادة المحاولة
                </Button>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-0">
              {/* ═══ ZONE A: DETAILS ═══ */}
              <div className="lg:col-span-5 p-5 lg:border-l border-slate-100 hub-zone-stagger hub-zone-stagger-1">
                <div className="space-y-4">
                  <div className="flex items-center gap-3 mb-4 flex-wrap">
                    <div className="flex items-center gap-2 bg-gradient-to-l from-brand-navy/5 to-brand-turquoise/5 rounded-lg px-3 py-2 border border-brand-turquoise/15">
                      <div
                        className="w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0"
                        style={{ background: isDone ? 'linear-gradient(135deg, #10b981, #059669)' : isRejected ? 'linear-gradient(135deg, #ef4444, #dc2626)' : 'linear-gradient(135deg, #1C3D74, #46C1BE)' }}
                      >
                        {getInitials(issue.employee_name)}
                      </div>
                      <div className="min-w-0">
                        <span className="text-[9px] text-brand-turquoise font-semibold block leading-none">المُبلّغ</span>
                        <span className="text-xs font-bold text-brand-navy truncate block">{issue.employee_name}</span>
                      </div>
                    </div>
                    {issue.section && <span className="text-[10px] px-2 py-1 rounded-lg bg-slate-50 text-slate-600 border border-slate-100">{issue.section}</span>}
                    {issue.page && <span className="text-[10px] px-2 py-1 rounded-lg bg-slate-50 text-slate-500 border border-slate-100">{issue.page}</span>}
                    {issue.assigned_team && (
                      <Badge variant="outline" className="text-[10px] border-brand-turquoise/30 text-brand-turquoise px-2 py-0.5 font-medium">{issue.assigned_team}</Badge>
                    )}
                    {issue.platform && <span className="text-[10px] px-2 py-1 rounded-lg bg-violet-50 text-violet-600 border border-violet-100">{issue.platform}</span>}
                  </div>

                  {(issue.current_behavior || issue.expected_behavior) && (
                    <div className="grid grid-cols-1 gap-3">
                      {issue.current_behavior && (
                        <div className="p-3 rounded-xl bg-red-50/60 border border-red-100">
                          <span className="text-[10px] font-semibold text-red-500 block mb-1.5">السلوك الحالي</span>
                          <p className="text-xs text-slate-700 leading-relaxed">{issue.current_behavior}</p>
                        </div>
                      )}
                      {issue.expected_behavior && (
                        <div className="p-3 rounded-xl bg-emerald-50/60 border border-emerald-100">
                          <span className="text-[10px] font-semibold text-emerald-600 block mb-1.5">السلوك المتوقع</span>
                          <p className="text-xs text-slate-700 leading-relaxed">{issue.expected_behavior}</p>
                        </div>
                      )}
                    </div>
                  )}

                  {issue.impact && issue.impact.length > 0 && (
                    <div className="p-3 rounded-xl bg-amber-50/50 border border-amber-100">
                      <span className="text-[10px] font-semibold text-amber-600 block mb-2 flex items-center gap-1.5">
                        <AlertTriangle className="h-3 w-3" /> التأثير
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {issue.impact.map((imp, i) => (
                          <span key={i} className="text-[10px] px-2 py-0.5 rounded-lg bg-white text-amber-700 border border-amber-200 font-medium">{imp}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  {detailData?.steps_to_reproduce && (
                    <div className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                      <span className="text-[10px] font-semibold text-slate-600 block mb-1.5">خطوات إعادة الإنتاج</span>
                      <p className="text-xs text-slate-700 leading-relaxed whitespace-pre-line">{detailData.steps_to_reproduce}</p>
                    </div>
                  )}

                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[10px] text-muted-foreground font-medium">التقدم</span>
                      <span className={`text-xs font-bold ${progress >= 75 ? 'text-emerald-600' : progress >= 50 ? 'text-brand-turquoise' : progress >= 25 ? 'text-amber-500' : 'text-red-500'}`}>{progress}%</span>
                    </div>
                    <div className="w-full bg-slate-200/60 rounded-full h-2.5 overflow-hidden">
                      <div className={`h-full rounded-full bg-gradient-to-l ${getProgressGradient(progress, issue.status)} transition-all duration-500`} style={{ width: `${progress}%` }} />
                    </div>
                  </div>

                  <div className="flex gap-2 pt-1">
                    <Button
                      onClick={() => navigate(`/admin/product-hub/issues/${issue.id}`)}
                      size="sm"
                      className="flex-1 h-9 text-xs font-semibold rounded-lg gap-1.5 bg-brand-navy hover:bg-brand-navy/90 text-white hub-btn"
                    >
                      <ExternalLink className="h-3.5 w-3.5" /> فتح الصفحة الكاملة
                    </Button>
                  </div>
                </div>
              </div>

              {/* ═══ ZONE B: COMMENTS ═══ */}
              <div className="lg:col-span-4 p-5 lg:border-l border-slate-100 border-t lg:border-t-0 flex flex-col hub-zone-stagger hub-zone-stagger-2">
                <div className="flex items-center gap-2 mb-3">
                  <MessageSquare className="h-4 w-4 text-brand-navy" />
                  <span className="text-sm font-semibold text-brand-navy">المناقشة</span>
                  <span className="text-[10px] text-muted-foreground">({comments.length})</span>
                </div>

                <div className="flex-1 overflow-y-auto max-h-[400px] space-y-3 mb-3 scrollbar-thin">
                  {comments.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-8 text-center hub-empty-state">
                      <MessageSquare className="h-8 w-8 text-slate-200 mb-2" />
                      <p className="text-xs text-muted-foreground">لا توجد تعليقات بعد</p>
                      <p className="text-[10px] text-muted-foreground mt-0.5">كن أول من يعلّق</p>
                    </div>
                  ) : (
                    comments.map((comment, idx) => {
                      const uColor = getUserColor(comment.created_by || comment.user_id);
                      return (
                        <div key={comment.id} className="hub-comment-enter flex gap-2.5" style={{ animationDelay: `${Math.min(idx * 40, 200)}ms` }}>
                          <div
                            className="w-7 h-7 rounded-full flex items-center justify-center text-[9px] font-bold text-white flex-shrink-0 mt-0.5 shadow-sm"
                            style={{ backgroundColor: uColor.avatar }}
                          >
                            {getInitials(comment.user_name)}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-1.5 mb-0.5">
                              <span className={`text-[11px] font-semibold ${uColor.text}`}>{comment.user_name}</span>
                              <span className="text-[9px] text-slate-400">{formatDualDateCompact(comment.timestamp)}</span>
                            </div>
                            <CommentBubble
                              comment={comment}
                              currentUserId={userId}
                              isMainAdmin={isMainAdmin}
                              isAdmin={isAdmin}
                              onEdit={handleEditComment}
                              onDelete={handleDeleteComment}
                            />
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>

                <div className="border-t border-slate-100 pt-3">
                  <CommentInput
                    onSubmit={handleComment}
                    submitting={submittingComment}
                    isMainAdmin={isMainAdmin}
                    isAdmin={isAdmin}
                    commentType={commentType}
                    setCommentType={setCommentType}
                    COMMENT_TYPE_CONFIG={COMMENT_TYPE_CONFIG}
                  />
                </div>
              </div>

              {/* ═══ ZONE C: HAKIM AI (Main Admins Only) ═══ */}
              {isMainAdmin ? <div className="lg:col-span-3 p-5 border-t lg:border-t-0 bg-gradient-to-b from-brand-turquoise/[0.04] via-transparent to-brand-navy/[0.02] hub-zone-stagger hub-zone-stagger-3 hub-hakim-enter">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-turquoise to-brand-navy flex items-center justify-center shadow-md shadow-brand-turquoise/20">
                    <Brain className="h-4.5 w-4.5 text-white" />
                  </div>
                  <div className="flex-1">
                    <span className="text-sm font-bold text-brand-navy block leading-tight">حكيم</span>
                    <span className="text-[10px] text-brand-turquoise font-medium">مساعد ذكي للتحليل</span>
                  </div>
                </div>

                {isMainAdmin && (
                  <Button
                    onClick={handleReanalyze}
                    disabled={reanalyzing}
                    className={`w-full h-10 text-xs font-bold rounded-xl gap-2 mb-4 shadow-sm hub-btn ${
                      hakimAnalysis && Object.keys(hakimAnalysis).length > 0
                        ? 'bg-white border-2 border-brand-turquoise/30 text-brand-turquoise hover:bg-brand-turquoise/5 hover:border-brand-turquoise/50 hover:shadow-md'
                        : 'bg-gradient-to-l from-brand-turquoise to-brand-turquoise/90 text-white hover:from-brand-turquoise/90 hover:to-brand-turquoise/80 shadow-brand-turquoise/25'
                    }`}
                    variant={hakimAnalysis && Object.keys(hakimAnalysis).length > 0 ? 'outline' : 'default'}
                  >
                    {reanalyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Brain className="h-4 w-4" />}
                    <span className={reanalyzing ? 'hub-analyzing' : ''}>{reanalyzing ? 'حكيم يحلّل...' : hakimAnalysis && Object.keys(hakimAnalysis).length > 0 ? 'إعادة التحليل بحكيم' : 'تحليل بواسطة حكيم'}</span>
                  </Button>
                )}

                {hakimAnalysis && Object.keys(hakimAnalysis).length > 0 ? (
                  <div className="space-y-2.5">
                    {hakimAnalysis.suggested_priority && (
                      <div className="hub-insight-item">
                        <HakimMicroInsight
                          label="الأولوية المقترحة"
                          value={PRIORITY_CONFIG[hakimAnalysis.suggested_priority]?.label || hakimAnalysis.suggested_priority}
                          detail={hakimAnalysis.priority_reasoning}
                          icon={Target}
                          valueColor={PRIORITY_CONFIG[hakimAnalysis.suggested_priority]?.textColor}
                        />
                      </div>
                    )}
                    {hakimAnalysis.suggested_team && (
                      <div className="hub-insight-item">
                        <HakimMicroInsight
                          label="الفريق المقترح"
                          value={hakimAnalysis.suggested_team}
                          detail={hakimAnalysis.team_reasoning}
                          icon={Users}
                          valueColor="text-brand-turquoise"
                        />
                      </div>
                    )}
                    {hakimAnalysis.impact_assessment && (
                      <div className="hub-insight-item">
                        <HakimMicroInsight label="تقييم الأثر" detail={hakimAnalysis.impact_assessment} icon={AlertTriangle} />
                      </div>
                    )}
                    {hakimAnalysis.technical_notes && (
                      <div className="hub-insight-item">
                        <HakimMicroInsight label="ملاحظات فنية" detail={hakimAnalysis.technical_notes} icon={FileText} />
                      </div>
                    )}
                    {hakimAnalysis.duplicate_ids?.length > 0 && (
                      <div className="hub-insight-item p-2.5 bg-amber-50/80 rounded-xl border border-amber-200/80">
                        <div className="flex items-center gap-1.5 text-amber-700 text-[10px] font-semibold mb-1">
                          <Copy className="h-3 w-3" />
                          {hakimAnalysis.duplicate_ids.length} تحدي مشابه
                        </div>
                        {hakimAnalysis.duplicate_note && (
                          <p className="text-[10px] text-amber-600 leading-relaxed">{hakimAnalysis.duplicate_note}</p>
                        )}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-5 px-3 bg-slate-50/50 rounded-xl border border-dashed border-slate-200 hub-empty-state">
                    <Sparkles className="h-8 w-8 text-slate-200 mx-auto mb-2" />
                    <p className="text-xs text-slate-400 font-medium">لم يتم التحليل بعد</p>
                    <p className="text-[10px] text-slate-300 mt-0.5">اضغط الزر أعلاه لبدء تحليل حكيم</p>
                  </div>
                )}

                {isMainAdmin && (
                  <div className="mt-4 pt-4 border-t border-slate-100 space-y-2">
                    <div className="text-[10px] text-slate-400 font-semibold mb-2 flex items-center gap-1.5">
                      <Wand2 className="h-3 w-3 text-brand-purple/70" /> أدوات إضافية
                    </div>
                    <div className="grid grid-cols-2 gap-1.5">
                      <Button
                        variant="outline" size="sm"
                        onClick={handleGenerate}
                        disabled={generating}
                        className="h-8 text-[9px] font-semibold rounded-lg gap-1 border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-brand-purple hover:border-brand-purple/20 hub-btn"
                      >
                        {generating ? <Loader2 className="h-3 w-3 animate-spin" /> : <Wand2 className="h-3 w-3" />}
                        {promptText ? 'إعادة البرومبت' : 'إنشاء برومبت'}
                      </Button>
                      <Button
                        variant={copied ? "default" : "outline"} size="sm"
                        onClick={handleCopy}
                        disabled={!promptText}
                        className={`h-8 text-[9px] font-semibold rounded-lg gap-1 hub-btn ${copied ? 'bg-emerald-500 text-white hub-success-pulse' : 'border-slate-200 text-slate-600 hover:bg-slate-50'} ${!promptText ? 'opacity-30' : ''}`}
                      >
                        {copied ? <CheckCircle2 className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                        {copied ? 'تم النسخ' : 'نسخ البرومبت'}
                      </Button>
                    </div>

                    {promptText && (
                      <div className="mt-2 p-2.5 bg-slate-900 rounded-xl max-h-[150px] overflow-y-auto scrollbar-thin">
                        <pre className="text-[9px] text-emerald-300 whitespace-pre-wrap leading-relaxed font-mono" dir="ltr">{promptText.slice(0, 600)}{promptText.length > 600 ? '...' : ''}</pre>
                      </div>
                    )}
                  </div>
                )}
              </div> : null}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function HakimMicroInsight({ label, value, detail, icon: Icon, valueColor = 'text-brand-navy' }) {
  return (
    <div className="p-3 bg-white rounded-xl border border-slate-100 hover:border-brand-turquoise/25 transition-all hover:shadow-sm">
      <div className="flex items-center gap-2 mb-1">
        <div className="w-5 h-5 rounded-md bg-brand-turquoise/8 flex items-center justify-center flex-shrink-0">
          <Icon className="h-3 w-3 text-brand-turquoise" />
        </div>
        <span className="text-[10px] text-slate-400 font-semibold uppercase tracking-wide">{label}</span>
      </div>
      {value && <p className={`text-xs font-bold ${valueColor} mt-1`}>{value}</p>}
      {detail && <p className="text-[10px] text-slate-500 mt-1 leading-relaxed line-clamp-3">{detail}</p>}
    </div>
  );
}

function IssuesTableView({ issues, loading, total, page, totalPages, onPageChange, navigate, highlightId, isMainAdmin, onRefresh }) {
  const { user } = useAuth();
  const isAdmin = user?.role === 'platform_admin';
  const [expandedId, setExpandedId] = useState(null);

  const handleToggleExpand = useCallback((issueId) => {
    setExpandedId(prev => prev === issueId ? null : issueId);
  }, []);

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
      {expandedId && (
        <div className="flex justify-end">
          <Button
            variant="ghost" size="sm"
            onClick={() => setExpandedId(null)}
            className="text-xs text-slate-400 hover:text-brand-navy gap-1.5 h-7 rounded-lg"
          >
            <Minimize2 className="h-3 w-3" /> طي الكل
          </Button>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {issues.map(issue => (
          <IssuePanel
            key={issue.id}
            issue={issue}
            navigate={navigate}
            isHighlighted={highlightId === issue.id}
            isMainAdmin={isMainAdmin}
            isAdmin={isAdmin}
            userId={user?.id}
            onRefresh={onRefresh}
            isExpanded={expandedId === issue.id}
            onToggleExpand={handleToggleExpand}
          />
        ))}
      </div>

      {totalPages > 1 && (
        <div className="flex justify-center items-center gap-3 pt-4 pb-2">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPageChange(p => p - 1)} className="rounded-xl h-9 w-9 p-0 border-slate-200">
            <ChevronRight className="h-4 w-4" />
          </Button>
          <div className="flex items-center gap-2 px-4 py-1.5 bg-slate-50 rounded-xl border border-slate-200">
            <span className="text-xs text-slate-500 font-medium">
              صفحة <span className="font-bold text-brand-navy">{page}</span> من <span className="font-bold text-brand-navy">{totalPages}</span>
            </span>
            <span className="text-[10px] text-slate-400">({total} تحدي)</span>
          </div>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => onPageChange(p => p + 1)} className="rounded-xl h-9 w-9 p-0 border-slate-200">
            <ChevronLeft className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}


function DashboardView({ data, loading, isAdmin, navigate }) {
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
      <div className="flex justify-center items-center py-20">
        <div className="flex flex-col items-center gap-3">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-brand-turquoise border-t-transparent" />
          <p className="text-sm text-muted-foreground">جاري تحميل التحليلات...</p>
        </div>
      </div>
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
              {animTotal.toLocaleString('ar-SA')}
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
            <p className="text-4xl font-extrabold text-brand-navy tracking-tighter tabular-nums">{animResolved.toLocaleString('ar-SA')}</p>
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
            <p className="text-4xl font-extrabold text-brand-navy tracking-tighter tabular-nums">{animOpen.toLocaleString('ar-SA')}</p>
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
            <p className="text-4xl font-extrabold text-brand-navy tracking-tighter tabular-nums">{animCritical.toLocaleString('ar-SA')}</p>
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
