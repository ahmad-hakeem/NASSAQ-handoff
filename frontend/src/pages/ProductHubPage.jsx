import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Sidebar } from '../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Progress } from '../components/ui/progress';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Bug, AlertTriangle, Clock, CheckCircle2, XCircle, Search, Plus,
  BarChart3, TrendingUp, Users, Target, Shield, Zap, Filter,
  ChevronLeft, ChevronRight, Brain, Lightbulb, Award, Building2,
  ArrowUpRight, Timer, AlertOctagon, Eye
} from 'lucide-react';

const STATUS_CONFIG = {
  new: { label: 'جديد', color: 'bg-blue-500', textColor: 'text-blue-700', bgLight: 'bg-blue-50', icon: Zap },
  under_review: { label: 'تحت المراجعة', color: 'bg-orange-500', textColor: 'text-orange-700', bgLight: 'bg-orange-50', icon: Eye },
  in_progress: { label: 'قيد التنفيذ', color: 'bg-purple-500', textColor: 'text-purple-700', bgLight: 'bg-purple-50', icon: Clock },
  qa_validation: { label: 'تحقق الجودة', color: 'bg-cyan-500', textColor: 'text-cyan-700', bgLight: 'bg-cyan-50', icon: Shield },
  done: { label: 'مكتمل', color: 'bg-green-500', textColor: 'text-green-700', bgLight: 'bg-green-50', icon: CheckCircle2 },
  rejected: { label: 'مرفوض', color: 'bg-red-500', textColor: 'text-red-700', bgLight: 'bg-red-50', icon: XCircle },
  user_feedback_confirmed: { label: 'أكده المستخدم', color: 'bg-emerald-600', textColor: 'text-emerald-700', bgLight: 'bg-emerald-50', icon: CheckCircle2 },
};

const PRIORITY_CONFIG = {
  critical: { label: 'حرج', color: 'bg-red-600', textColor: 'text-red-700', icon: AlertOctagon },
  high: { label: 'عالي', color: 'bg-orange-500', textColor: 'text-orange-700', icon: AlertTriangle },
  medium: { label: 'متوسط', color: 'bg-yellow-500', textColor: 'text-yellow-700', icon: Target },
  low: { label: 'منخفض', color: 'bg-gray-400', textColor: 'text-gray-600', icon: ArrowUpRight },
};

const TYPE_ICONS = {
  bug: Bug, error: AlertTriangle, ui_issue: Eye, ux_issue: Lightbulb,
  performance: Zap, feature_request: Lightbulb, improvement: TrendingUp,
};

const STATUS_PROGRESS = {
  new: 10, under_review: 25, in_progress: 55, qa_validation: 80,
  done: 100, rejected: 100, user_feedback_confirmed: 100,
};

export function ProductHubPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'issues');
  const [issues, setIssues] = useState([]);
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [config, setConfig] = useState(null);

  const [filters, setFilters] = useState({
    status: searchParams.get('status') || '',
    issue_type: '',
    priority: '',
    section: '',
    assigned_team: '',
    search: '',
  });

  const isAdmin = user?.role === 'platform_admin';

  const fetchConfig = useCallback(async () => {
    try {
      const res = await axios.get('/api/product-hub/config');
      setConfig(res.data);
    } catch (e) { console.error(e); }
  }, []);

  const fetchIssues = useCallback(async () => {
    try {
      const params = { page, limit: 20 };
      if (filters.status) params.status = filters.status;
      if (filters.issue_type) params.issue_type = filters.issue_type;
      if (filters.priority) params.priority = filters.priority;
      if (filters.section) params.section = filters.section;
      if (filters.assigned_team) params.assigned_team = filters.assigned_team;
      if (filters.search) params.search = filters.search;
      const res = await axios.get('/api/product-hub/issues', { params });
      setIssues(res.data.issues);
      setTotal(res.data.total);
    } catch (e) {
      toast.error('فشل في تحميل المشاكل');
    } finally {
      setLoading(false);
    }
  }, [page, filters]);

  const fetchDashboard = useCallback(async () => {
    try {
      const res = await axios.get('/api/product-hub/dashboard');
      setDashboard(res.data);
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => { fetchConfig(); }, [fetchConfig]);
  useEffect(() => { fetchIssues(); }, [fetchIssues]);
  useEffect(() => { if (activeTab === 'dashboard') fetchDashboard(); }, [activeTab, fetchDashboard]);

  useEffect(() => {
    const tab = searchParams.get('tab');
    if (tab && tab !== activeTab) setActiveTab(tab);
  }, [searchParams]);

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setSearchParams({ tab });
  };

  const totalPages = Math.ceil(total / 20);

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50/30" dir="rtl">
        <div className="p-4 lg:p-6 space-y-6">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl lg:text-3xl font-bold text-brand-navy flex items-center gap-3">
                <Brain className="h-8 w-8 text-brand-turquoise" />
                مركز ذكاء المنتج
              </h1>
              <p className="text-muted-foreground mt-1">نظام الحوكمة والتتبع الذكي الداخلي</p>
            </div>
            <Button
              onClick={() => navigate('/admin/product-hub/submit')}
              className="bg-brand-turquoise hover:bg-brand-turquoise/90 text-white"
            >
              <Plus className="h-4 w-4 ml-2" />
              إرسال مشكلة جديدة
            </Button>
          </div>

          <Tabs value={activeTab} onValueChange={handleTabChange}>
            <TabsList className="bg-white border shadow-sm">
              <TabsTrigger value="issues" className="data-[state=active]:bg-brand-navy data-[state=active]:text-white">
                المشاكل
              </TabsTrigger>
              <TabsTrigger value="dashboard" className="data-[state=active]:bg-brand-navy data-[state=active]:text-white">
                لوحة التحليلات
              </TabsTrigger>
            </TabsList>

            <TabsContent value="issues" className="space-y-4 mt-4">
              <Card className="border shadow-sm">
                <CardContent className="p-4">
                  <div className="flex flex-wrap gap-3 items-center">
                    <div className="relative flex-1 min-w-[200px]">
                      <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                      <Input
                        placeholder="بحث..."
                        value={filters.search}
                        onChange={(e) => { setFilters(f => ({...f, search: e.target.value})); setPage(1); }}
                        className="pr-10 text-right"
                      />
                    </div>
                    <Select value={filters.status} onValueChange={(v) => { setFilters(f => ({...f, status: v === 'all' ? '' : v})); setPage(1); }}>
                      <SelectTrigger className="w-[150px]"><SelectValue placeholder="الحالة" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">الكل</SelectItem>
                        {Object.entries(STATUS_CONFIG).map(([k, v]) => (
                          <SelectItem key={k} value={k}>{v.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Select value={filters.priority} onValueChange={(v) => { setFilters(f => ({...f, priority: v === 'all' ? '' : v})); setPage(1); }}>
                      <SelectTrigger className="w-[140px]"><SelectValue placeholder="الأولوية" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">الكل</SelectItem>
                        {Object.entries(PRIORITY_CONFIG).map(([k, v]) => (
                          <SelectItem key={k} value={k}>{v.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {config && (
                      <>
                        <Select value={filters.issue_type} onValueChange={(v) => { setFilters(f => ({...f, issue_type: v === 'all' ? '' : v})); setPage(1); }}>
                          <SelectTrigger className="w-[150px]"><SelectValue placeholder="النوع" /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="all">الكل</SelectItem>
                            {config.issue_types?.map(t => (
                              <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Select value={filters.assigned_team} onValueChange={(v) => { setFilters(f => ({...f, assigned_team: v === 'all' ? '' : v})); setPage(1); }}>
                          <SelectTrigger className="w-[140px]"><SelectValue placeholder="الفريق" /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="all">الكل</SelectItem>
                            {config.teams?.map(t => (
                              <SelectItem key={t} value={t}>{t}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </>
                    )}
                  </div>
                </CardContent>
              </Card>

              {loading ? (
                <div className="flex justify-center py-20">
                  <div className="animate-pulse text-brand-navy text-lg">جاري التحميل...</div>
                </div>
              ) : issues.length === 0 ? (
                <Card className="border">
                  <CardContent className="p-12 text-center">
                    <Bug className="h-16 w-16 mx-auto text-muted-foreground/40 mb-4" />
                    <h3 className="text-lg font-semibold text-muted-foreground">لا توجد مشاكل</h3>
                    <p className="text-sm text-muted-foreground mt-1">قم بإرسال أول مشكلة للبدء</p>
                  </CardContent>
                </Card>
              ) : (
                <div className="space-y-3">
                  {issues.map(issue => {
                    const statusCfg = STATUS_CONFIG[issue.status] || STATUS_CONFIG.new;
                    const priorityCfg = PRIORITY_CONFIG[issue.priority] || PRIORITY_CONFIG.medium;
                    const TypeIcon = TYPE_ICONS[issue.issue_type] || Bug;
                    const progress = STATUS_PROGRESS[issue.status] || 0;
                    return (
                      <Card
                        key={issue.id}
                        className="border hover:border-brand-turquoise/50 hover:shadow-md transition-all cursor-pointer"
                        onClick={() => navigate(`/admin/product-hub/issues/${issue.id}`)}
                      >
                        <CardContent className="p-4">
                          <div className="flex flex-col lg:flex-row lg:items-center gap-4">
                            <div className="flex items-start gap-3 flex-1">
                              <div className={`p-2 rounded-lg ${statusCfg.bgLight}`}>
                                <TypeIcon className={`h-5 w-5 ${statusCfg.textColor}`} />
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="text-xs text-muted-foreground font-mono">#{issue.issue_number}</span>
                                  <h3 className="font-semibold text-sm lg:text-base truncate">{issue.title}</h3>
                                </div>
                                <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground flex-wrap">
                                  <span>{issue.employee_name}</span>
                                  <span>•</span>
                                  <span>{issue.section}</span>
                                  <span>•</span>
                                  <span>{issue.page}</span>
                                  {issue.assigned_team && (
                                    <>
                                      <span>•</span>
                                      <span className="text-brand-turquoise">{issue.assigned_team}</span>
                                    </>
                                  )}
                                </div>
                                <div className="mt-2">
                                  <Progress value={progress} className="h-1.5" />
                                </div>
                              </div>
                            </div>
                            <div className="flex items-center gap-2 flex-shrink-0">
                              <Badge className={`${priorityCfg.color} text-white text-[10px]`}>{priorityCfg.label}</Badge>
                              <Badge className={`${statusCfg.color} text-white text-[10px]`}>{statusCfg.label}</Badge>
                              {issue.sla_status === 'exceeded' && (
                                <Badge className="bg-red-600 text-white text-[10px] animate-pulse">
                                  <Timer className="h-3 w-3 ml-1" />
                                  تجاوز SLA
                                </Badge>
                              )}
                              {issue.hakim_analysis?.duplicate_ids?.length > 0 && (
                                <Badge variant="outline" className="text-[10px] border-amber-300 text-amber-600">
                                  مكرر محتمل
                                </Badge>
                              )}
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}

                  {totalPages > 1 && (
                    <div className="flex justify-center items-center gap-4 pt-4">
                      <Button
                        variant="outline" size="sm"
                        disabled={page <= 1}
                        onClick={() => setPage(p => p - 1)}
                      >
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                      <span className="text-sm text-muted-foreground">
                        صفحة {page} من {totalPages} ({total} مشكلة)
                      </span>
                      <Button
                        variant="outline" size="sm"
                        disabled={page >= totalPages}
                        onClick={() => setPage(p => p + 1)}
                      >
                        <ChevronLeft className="h-4 w-4" />
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </TabsContent>

            <TabsContent value="dashboard" className="space-y-6 mt-4">
              {!dashboard ? (
                <div className="flex justify-center py-20">
                  <div className="animate-pulse text-brand-navy">جاري تحميل التحليلات...</div>
                </div>
              ) : (
                <DashboardView data={dashboard} />
              )}
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </Sidebar>
  );
}

function DashboardView({ data }) {
  const kpiCards = [
    { label: 'إجمالي المشاكل', value: data.total_issues, icon: BarChart3, color: 'text-brand-navy', bg: 'bg-blue-50' },
    { label: 'مشاكل مفتوحة', value: data.total_open, icon: AlertTriangle, color: 'text-orange-600', bg: 'bg-orange-50' },
    { label: 'مشاكل حرجة', value: data.critical_open, icon: AlertOctagon, color: 'text-red-600', bg: 'bg-red-50' },
    { label: 'جديدة هذا الأسبوع', value: data.new_this_week, icon: Zap, color: 'text-blue-600', bg: 'bg-blue-50' },
    { label: 'قيد التنفيذ', value: data.in_progress, icon: Clock, color: 'text-purple-600', bg: 'bg-purple-50' },
    { label: 'متوسط الحل (ساعة)', value: data.avg_resolution_hours, icon: Timer, color: 'text-green-600', bg: 'bg-green-50' },
    { label: 'تجاوز SLA', value: data.sla_exceeded, icon: AlertTriangle, color: 'text-red-600', bg: 'bg-red-50' },
    { label: 'مكررات تم اكتشافها', value: data.duplicates_detected, icon: Target, color: 'text-amber-600', bg: 'bg-amber-50' },
  ];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {kpiCards.map((kpi, i) => (
          <Card key={i} className="border shadow-sm">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div className={`p-2 rounded-lg ${kpi.bg}`}>
                  <kpi.icon className={`h-5 w-5 ${kpi.color}`} />
                </div>
                <div className="text-left">
                  <p className="text-2xl font-bold text-brand-navy">{kpi.value ?? 0}</p>
                  <p className="text-xs text-muted-foreground">{kpi.label}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-brand-turquoise" />
              حسب النوع
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {data.by_type?.map((t, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <span>{t.label}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-32 bg-gray-100 rounded-full h-2">
                      <div className="bg-brand-turquoise h-2 rounded-full" style={{width: `${Math.min(100, (t.count / Math.max(1, data.total_issues)) * 100)}%`}} />
                    </div>
                    <span className="font-semibold w-8 text-left">{t.count}</span>
                  </div>
                </div>
              ))}
              {(!data.by_type || data.by_type.length === 0) && (
                <p className="text-sm text-muted-foreground text-center py-4">لا توجد بيانات</p>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="border shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Target className="h-4 w-4 text-brand-turquoise" />
              حسب الأولوية
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {data.by_priority?.map((p, i) => {
                const cfg = PRIORITY_CONFIG[p.priority] || {};
                return (
                  <div key={i} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <div className={`w-3 h-3 rounded-full ${cfg.color || 'bg-gray-400'}`} />
                      <span>{p.label || p.priority}</span>
                    </div>
                    <span className="font-semibold">{p.count}</span>
                  </div>
                );
              })}
              {(!data.by_priority || data.by_priority.length === 0) && (
                <p className="text-sm text-muted-foreground text-center py-4">لا توجد بيانات</p>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="border shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Award className="h-4 w-4 text-brand-turquoise" />
              أكثر المساهمين
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {data.top_contributors?.map((c, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <span className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold text-white ${i === 0 ? 'bg-amber-500' : i === 1 ? 'bg-gray-400' : 'bg-orange-400'}`}>
                      {i + 1}
                    </span>
                    <span>{c.name}</span>
                  </div>
                  <Badge variant="secondary">{c.count} مشكلة</Badge>
                </div>
              ))}
              {(!data.top_contributors || data.top_contributors.length === 0) && (
                <p className="text-sm text-muted-foreground text-center py-4">لا توجد بيانات</p>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="border shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-brand-turquoise" />
              أدق المبلّغين
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {data.most_accurate_reporters?.map((r, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <span>{r.name}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">{r.valid}/{r.total}</span>
                    <Badge variant={r.accuracy >= 80 ? 'default' : 'secondary'} className={r.accuracy >= 80 ? 'bg-green-500' : ''}>
                      {r.accuracy}%
                    </Badge>
                  </div>
                </div>
              ))}
              {(!data.most_accurate_reporters || data.most_accurate_reporters.length === 0) && (
                <p className="text-sm text-muted-foreground text-center py-4">لا توجد بيانات كافية</p>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="border shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Building2 className="h-4 w-4 text-brand-turquoise" />
              أكثر الأقسام مشاكلاً
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {data.top_sections?.map((s, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <span>{s.section}</span>
                  <Badge variant="secondary">{s.count}</Badge>
                </div>
              ))}
              {(!data.top_sections || data.top_sections.length === 0) && (
                <p className="text-sm text-muted-foreground text-center py-4">لا توجد بيانات</p>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="border shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Users className="h-4 w-4 text-brand-turquoise" />
              حسب الفريق
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {data.by_team?.map((t, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <span>{t.team}</span>
                  <Badge variant="secondary">{t.count}</Badge>
                </div>
              ))}
              {(!data.by_team || data.by_team.length === 0) && (
                <p className="text-sm text-muted-foreground text-center py-4">لا توجد بيانات</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default ProductHubPage;
