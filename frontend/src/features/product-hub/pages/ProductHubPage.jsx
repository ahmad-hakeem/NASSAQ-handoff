import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Sidebar } from '@/shared/components/layout/Sidebar';
import { Button } from '@/shared/components/ui/button';
import { useAuth } from '@/shared/contexts/AuthContext';
import { toast } from 'sonner';
import DashboardView from '@/features/product-hub/components/product-hub/DashboardView';
import { FilterToolbar, IssuesStatusFlow } from '@/features/product-hub/components/product-hub/FilterToolbar';
import IssuesTableView from '@/features/product-hub/components/product-hub/IssuesTableView';
import ActionHistoryPanel from '@/features/product-hub/components/product-hub/ActionHistoryPanel';
import {
  Brain, Plus, BarChart3,
  CheckCircle2, Bug,
  RefreshCw, History,
} from 'lucide-react';

export function ProductHubPage() {
  const { user, api } = useAuth();
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
  const [showHistory, setShowHistory] = useState(false);

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
      const res = await api.get('/product-hub/config');
      setConfig(res.data);
    } catch (e) { console.error(e); }
  }, [api]);

  const fetchIssues = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, limit };
      Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v; });
      const res = await api.get('/product-hub/issues', { params });
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
  }, [api, page, filters]);

  const fetchDashboard = useCallback(async () => {
    setDashLoading(true);
    try {
      const res = await api.get('/product-hub/dashboard');
      setDashboard(res.data);
    } catch (e) { console.error(e); }
    finally { setDashLoading(false); }
  }, [api]);

  useEffect(() => { fetchConfig(); }, [fetchConfig]);
  useEffect(() => { fetchIssues(); }, [fetchIssues]);
  // The dashboard/analytics endpoint is main-admin-only; only fetch it when
  // the resolved config grants main-admin access. A plain platform_admin can
  // use the issues list but would otherwise get a silent 403 here.
  useEffect(() => { if (isMainAdmin) fetchDashboard(); }, [fetchDashboard, isMainAdmin]);

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
                  <div className="flex items-center bg-white/10 rounded-lg p-0.5 gap-0.5">
                    <button
                      onClick={() => handleTabChange('issues')}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
                        activeTab === 'issues'
                          ? 'bg-white text-brand-navy shadow-sm'
                          : 'text-white/70 hover:text-white hover:bg-white/10'
                      }`}
                    >
                      <Bug className="h-3.5 w-3.5" />
                      التحديات
                    </button>
                    <button
                      onClick={() => handleTabChange('dashboard')}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
                        activeTab === 'dashboard'
                          ? 'bg-white text-brand-navy shadow-sm'
                          : 'text-white/70 hover:text-white hover:bg-white/10'
                      }`}
                    >
                      <BarChart3 className="h-3.5 w-3.5" />
                      لوحة القيادة
                    </button>
                  </div>
                )}
                {isMainAdmin && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="border-white/20 text-white hover:bg-white/10"
                    onClick={() => setShowHistory(true)}
                  >
                    <History className="h-4 w-4 me-1.5" />
                    سجل العمليات
                  </Button>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  className="border-white/20 text-white hover:bg-white/10"
                  onClick={() => { fetchIssues(); if (isMainAdmin) fetchDashboard(); }}
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

          {(activeTab !== 'dashboard' || !isMainAdmin) && (
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
                <div className="relative overflow-hidden flex flex-col items-center justify-center text-center p-5 rounded-2xl bg-gradient-to-br from-brand-navy via-brand-navy/95 to-brand-purple text-white shadow-lg">
                  <div className="absolute inset-0 nassaq-pattern opacity-[0.06]" style={{ backgroundImage: "url('/nassaq-pattern.png')" }} />
                  <div className="absolute -bottom-6 -left-6 h-20 w-20 rounded-full bg-brand-turquoise/15" />
                  <div className="absolute -top-4 -right-4 h-14 w-14 rounded-full bg-white/5" />
                  <div className="relative z-10 flex flex-col items-center gap-1">
                    <div className="p-2 rounded-xl bg-white/10 backdrop-blur-sm mb-1">
                      <CheckCircle2 className="h-5 w-5 text-emerald-300" />
                    </div>
                    <p className="text-5xl font-extrabold tracking-tighter leading-none tabular-nums hub-countup-number text-white drop-shadow-sm">
                      {issues.filter(i => i.status === 'done' || i.status === 'user_feedback_confirmed').length}
                    </p>
                    <p className="text-[11px] text-white/70 font-semibold mt-1">التحديات المحلولة</p>
                    <p className="text-[10px] text-white/50 font-medium mt-0.5">
                      من أصل {total} تحدي
                    </p>
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
      {isMainAdmin && (
        <ActionHistoryPanel
          open={showHistory}
          onClose={() => setShowHistory(false)}
          onRefresh={fetchIssues}
          api={api}
        />
      )}
    </Sidebar>
  );
}

export default ProductHubPage;
