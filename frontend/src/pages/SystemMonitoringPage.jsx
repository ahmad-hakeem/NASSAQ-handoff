import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Sidebar } from '../components/layout/Sidebar';
import { PageHeader } from '../components/layout/PageHeader';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '../components/ui/dialog';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '../components/ui/sheet';
import {
  Activity,
  Server,
  Cpu,
  HardDrive,
  Wifi,
  Database,
  Globe,
  Brain,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Zap,
  Play,
  Pause,
  RotateCcw,
  Download,
  Upload,
  FileText,
  Eye,
  Settings,
  Bell,
  Shield,
  TrendingUp,
  TrendingDown,
  Minus,
  ArrowUp,
  ArrowDown,
  Link2,
  CloudOff,
  Cloud,
  Timer,
  Hash,
  Layers,
  Terminal,
  AlertCircle,
  Info,
  ChevronRight,
  BarChart3,
  PieChart,
} from 'lucide-react';
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart as RechartPie, Pie, Cell } from 'recharts';

// Translations
// Empty initial states - data will be fetched from API
const INITIAL_ERRORS = [];
const INITIAL_JOBS = [];
const INITIAL_INTEGRATIONS = [];
const INITIAL_ALERTS = [];

export const SystemMonitoringPage = () => {
  const { t } = useTranslation();
  const { isRTL = true, isDark } = useTheme();
  const { api } = useAuth();
  const diagnosisTimeoutRef = useRef(null);
  
  // States
  const [activeTab, setActiveTab] = useState('overview');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(new Date());
  const [performanceData, setPerformanceData] = useState([]);
  const [showErrorLogs, setShowErrorLogs] = useState(false);
  const [showJobsSheet, setShowJobsSheet] = useState(false);
  const [showApiMonitor, setShowApiMonitor] = useState(false);
  const [showDiagnosticDialog, setShowDiagnosticDialog] = useState(false);
  const [isDiagnosing, setIsDiagnosing] = useState(false);
  const [diagnosisResults, setDiagnosisResults] = useState(null);
  
  // Dynamic data states
  const [errorLogs, setErrorLogs] = useState(INITIAL_ERRORS);
  const [jobs, setJobs] = useState(INITIAL_JOBS);
  const [integrations, setIntegrations] = useState(INITIAL_INTEGRATIONS);
  const [alerts, setAlerts] = useState(INITIAL_ALERTS);
  const [loadingData, setLoadingData] = useState(true);
  
  const [metrics, setMetrics] = useState({
    cpu: 0,
    memory: 0,
    disk: 0,
    network: 0,
    dbConnections: 0,
    dbQueryTime: 0,
    dbSlowQueries: 0,
    apiResponseTime: 0,
    apiRequestsPerMin: 0,
    apiSuccessRate: 0,
    apiFailedRequests: 0,
    totalOperations: 0,
    activeUsers: 0,
    errors: 0,
    jobsRunning: 0,
    jobsPending: 0,
    jobsCompleted: 0,
    jobsFailed: 0,
    aiOperations: 0,
    aiModelsActive: 0,
  });
  
  // Auto refresh
  useEffect(() => {
    if (!autoRefresh) return;
    
    const interval = setInterval(() => {
      fetchMonitoringData();
      setLastUpdate(new Date());
    }, 30000);
    
    return () => clearInterval(interval);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRefresh]);
  
  const fetchMonitoringData = useCallback(async () => {
    try {
      setLoadingData(true);
      const [errorsRes, jobsRes, integrationsRes, alertsRes, metricsRes, healthRes, historyRes] = await Promise.allSettled([
        api.get('/system/errors'),
        api.get('/system/jobs'),
        api.get('/integrations'),
        api.get('/system/alerts'),
        api.get('/system/metrics'),
        api.get('/admin/command-center/system-health'),
        api.get('/system/metrics/history'),
      ]);
      
      if (errorsRes.status === 'fulfilled') {
        const d = errorsRes.value.data;
        const mapped = (Array.isArray(d) ? d : []).map(e => ({
          id: e.id || e.timestamp || Math.random(),
          severity: e.level || e.severity || 'info',
          type: e.message ? e.message.split(':')[0] : (e.type || 'Error'),
          message: e.message || '',
          time: e.timestamp || e.time || '',
          service: e.source || e.service || 'system',
        }));
        setErrorLogs(mapped);
      }
      if (jobsRes.status === 'fulfilled') {
        const d = jobsRes.value.data;
        setJobs(Array.isArray(d) ? d : []);
      }
      if (integrationsRes.status === 'fulfilled') {
        const raw = integrationsRes.value.data;
        const intData = Array.isArray(raw) ? raw : (raw?.integrations || []);
        setIntegrations(intData.map(i => ({
          ...i,
          name: i.name_ar || i.name,
          name_en: i.name_en || i.name,
          lastSync: i.last_sync || i.updated_at,
          health: i.health || (i.status === 'connected' ? 100 : 0)
        })));
      }
      if (alertsRes.status === 'fulfilled') {
        const d = alertsRes.value.data;
        setAlerts(Array.isArray(d) ? d : []);
      }
      if (metricsRes.status === 'fulfilled') {
        const m = metricsRes.value.data;
        if (m) {
          const totalReqs = m.response_metrics?.total_requests || 0;
          const totalErrs = m.response_metrics?.total_errors || 0;
          const successRate = totalReqs > 0 ? Math.round(((totalReqs - totalErrs) / totalReqs) * 1000) / 10 : 100;
          const netSentKbps = m.network?.sent_kbps || 0;
          const netRecvKbps = m.network?.recv_kbps || 0;

          setMetrics({
            cpu: m.process?.cpu_percent || 0,
            memory: m.system_memory?.percent || 0,
            disk: m.disk?.percent || 0,
            network: Math.round(netSentKbps + netRecvKbps),
            netSentKbps: netSentKbps,
            netRecvKbps: netRecvKbps,
            dbConnections: m.pool_stats?.checked_out || 0,
            dbQueryTime: m.db_latency_ms || 0,
            dbSlowQueries: 0,
            apiResponseTime: m.response_metrics?.avg_response_ms || 0,
            apiRequestsPerMin: m.requests_per_min || 0,
            apiSuccessRate: successRate,
            apiFailedRequests: totalErrs,
            totalOperations: totalReqs,
            activeUsers: m.active_users_24h || 0,
            errors: totalErrs,
            jobsRunning: 0,
            jobsPending: 0,
            jobsCompleted: 0,
            jobsFailed: 0,
            aiOperations: 0,
            aiModelsActive: 0,
            poolSize: m.pool_stats?.pool_size || 0,
            poolCheckedIn: m.pool_stats?.checked_in || 0,
            cacheHits: m.cache_metrics?.hits || 0,
            cacheMisses: m.cache_metrics?.misses || 0,
            cacheHitRate: m.cache_metrics?.hit_rate_percent || 0,
            memoryRssMb: m.process?.memory_rss_mb || 0,
            diskUsedGb: m.disk?.used_gb || 0,
            diskTotalGb: m.disk?.total_gb || 0,
            netSentMb: m.network?.bytes_sent_mb || 0,
            netRecvMb: m.network?.bytes_recv_mb || 0,
            uptimeSeconds: m.uptime_seconds || 0,
            dbUsers: m.database_counts?.users || 0,
            dbSchools: m.database_counts?.schools || 0,
            dbTeachers: m.database_counts?.teachers || 0,
            dbStudents: m.database_counts?.students || 0,
            dbClasses: m.database_counts?.classes || 0,
            dbSessions: m.database_counts?.sessions || 0,
            dbAuditLogs: m.database_counts?.audit_logs || 0,
            p95ResponseMs: m.response_metrics?.p95_response_ms || 0,
            p99ResponseMs: m.response_metrics?.p99_response_ms || 0,
          });
        }
      }
      if (healthRes.status === 'fulfilled') {
        const h = healthRes.value.data;
        if (h) {
          setMetrics(prev => ({
            ...prev,
            aiOperations: h.engines?.ai_engine === 'active' ? 1 : 0,
            aiModelsActive: h.engines?.ai_engine === 'active' ? 1 : 0,
          }));
        }
      }
      if (historyRes.status === 'fulfilled') {
        const history = historyRes.value.data;
        if (Array.isArray(history) && history.length > 0) {
          setPerformanceData(history.map((snap, idx) => ({
            time: new Date(snap.timestamp).toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit' }),
            cpu: snap.cpu || 0,
            memory: snap.memory || 0,
            responseTime: snap.avg_response_ms || 0,
            requests: snap.requests_per_min || 0,
          })));
        }
      }
    } catch (error) {
      console.error('Error fetching monitoring data:', error);
    } finally {
      setLoadingData(false);
    }
  }, [api]);
  
  useEffect(() => {
    fetchMonitoringData();
  }, [fetchMonitoringData]);
  
  // Manual refresh
  const handleRefresh = () => {
    fetchMonitoringData();
    setLastUpdate(new Date());
    toast.success(t('dataRefreshed'));
  };
  
  // Get health status
  const getHealthStatus = () => {
    if (metrics.cpu > 90 || metrics.memory > 90) return 'critical';
    if (metrics.cpu > 75 || metrics.memory > 80 || metrics.errors > 10) return 'warning';
    return 'healthy';
  };
  
  // Get health color
  const getHealthColor = (status) => {
    switch (status) {
      case 'healthy': return 'text-green-500 bg-green-500';
      case 'warning': return 'text-yellow-500 bg-yellow-500';
      case 'critical': return 'text-red-500 bg-red-500';
      default: return 'text-gray-500 bg-gray-500';
    }
  };
  
  // Get metric color
  const getMetricColor = (value, thresholds = { warning: 70, critical: 90 }) => {
    if (value >= thresholds.critical) return 'text-red-500';
    if (value >= thresholds.warning) return 'text-yellow-500';
    return 'text-green-500';
  };
  
  // Get progress color
  const getProgressColor = (value, thresholds = { warning: 70, critical: 90 }) => {
    if (value >= thresholds.critical) return 'bg-red-500';
    if (value >= thresholds.warning) return 'bg-yellow-500';
    return 'bg-green-500';
  };
  
  // Format time
  const formatTime = (date) => {
    return date.toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };
  
  useEffect(() => {
    return () => {
      if (diagnosisTimeoutRef.current) clearTimeout(diagnosisTimeoutRef.current);
    };
  }, []);

  const runDiagnosis = async () => {
    setIsDiagnosing(true);
    setDiagnosisResults(null);
    try {
      const res = await api.post('/system/ai-diagnosis');
      setDiagnosisResults(res.data);
      if (res.data.status === 'healthy') {
        toast.success(t('diagnosisCompleteSystemHealthy'));
      } else if (res.data.status === 'warning') {
        toast.warning(t('diagnosisCompleteWithWarnings'));
      } else {
        toast.error(t('diagnosisCompleteCriticalIssues'));
      }
    } catch (err) {
      console.error('AI diagnosis failed:', err);
      toast.error(t('diagnosisFailed'));
    } finally {
      setIsDiagnosing(false);
    }
  };
  
  const healthStatus = getHealthStatus();
  const healthColor = getHealthColor(healthStatus);
  
  // Pie chart data
  const jobsPieData = [
    { name: t('running'), value: metrics.jobsRunning, color: '#3B82F6' },
    { name: t('pending'), value: metrics.jobsPending, color: '#F59E0B' },
    { name: t('completed'), value: metrics.jobsCompleted, color: '#10B981' },
    { name: t('failed'), value: metrics.jobsFailed, color: '#EF4444' },
  ];
  
  return (
    <Sidebar>
      <div className="min-h-screen bg-background" dir={isRTL ? 'rtl' : 'ltr'} data-testid="system-monitoring-page">
        {/* Header */}
        <header className="sticky top-0 z-40 bg-background/95 backdrop-blur border-b">
          <div className="container mx-auto px-4 lg:px-6 py-4">
            <div className="flex items-center justify-between mb-4">
              <PageHeader 
                title={t('monitoringPageTitle')} 
                subtitle={t('monitoringPageSubtitle')}
                icon={Activity}
                className="mb-0"
              />
              <div className="flex items-center gap-3">
                {/* System Health Badge */}
                <div className={`flex items-center gap-2 px-4 py-2 rounded-xl ${healthColor.split(' ')[1]}/10`}>
                  <div className={`w-3 h-3 rounded-full ${healthColor.split(' ')[1]} animate-pulse`}></div>
                  <span className={`font-bold ${healthColor.split(' ')[0]}`}>
                    {healthStatus === 'healthy' ? t('healthy') : healthStatus === 'warning' ? t('warning') : t('critical')}
                  </span>
                </div>
                
                {/* Auto Refresh Toggle */}
                <Button 
                  variant={autoRefresh ? 'default' : 'outline'} 
                  size="sm"
                  onClick={() => setAutoRefresh(!autoRefresh)}
                  className="rounded-xl"
                >
                  {autoRefresh ? <Pause className="h-4 w-4 me-2" /> : <Play className="h-4 w-4 me-2" />}
                  {t('autoRefresh')}
                </Button>
                
                <Button variant="outline" onClick={handleRefresh} className="rounded-xl">
                  <RefreshCw className="h-4 w-4 me-2" />
                  {t('refresh')}
                </Button>
              </div>
            </div>
            
            {/* Last Update */}
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Clock className="h-4 w-4" />
              {t('lastUpdate')}: {formatTime(lastUpdate)}
            </div>
          </div>
        </header>
        
        {/* Main Content */}
        <main className="container mx-auto px-4 lg:px-6 py-6">
          <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
            <TabsList>
              <TabsTrigger value="overview">{t('overview')}</TabsTrigger>
              <TabsTrigger value="details">{t('details')}</TabsTrigger>
              <TabsTrigger value="alerts" className="relative">
                {t('alerts')}
                {alerts.filter(a => !a.resolved).length > 0 && (
                  <span className="absolute -top-1 -end-1 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
                    {alerts.filter(a => !a.resolved).length}
                  </span>
                )}
              </TabsTrigger>
              <TabsTrigger value="tools">{t('tools')}</TabsTrigger>
            </TabsList>
            
            {/* Overview Tab */}
            <TabsContent value="overview" className="space-y-6">
              {/* Server Resources */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* CPU */}
                <Card className="card-nassaq">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <div className="p-2 bg-blue-100 rounded-lg">
                          <Cpu className="h-5 w-5 text-blue-600" />
                        </div>
                        <span className="font-medium">{t('cpuUsage')}</span>
                      </div>
                      <span className={`text-2xl font-bold ${getMetricColor(metrics.cpu)}`}>
                        {metrics.cpu.toFixed(0)}%
                      </span>
                    </div>
                    <Progress value={metrics.cpu} className={`h-2 ${getProgressColor(metrics.cpu)}`} />
                  </CardContent>
                </Card>
                
                {/* Memory */}
                <Card className="card-nassaq">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <div className="p-2 bg-purple-100 rounded-lg">
                          <HardDrive className="h-5 w-5 text-purple-600" />
                        </div>
                        <span className="font-medium">{t('memoryUsage')}</span>
                      </div>
                      <span className={`text-2xl font-bold ${getMetricColor(metrics.memory)}`}>
                        {metrics.memory.toFixed(0)}%
                      </span>
                    </div>
                    <Progress value={metrics.memory} className={`h-2 ${getProgressColor(metrics.memory)}`} />
                  </CardContent>
                </Card>
                
                {/* Disk */}
                <Card className="card-nassaq">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <div className="p-2 bg-green-100 rounded-lg">
                          <Database className="h-5 w-5 text-green-600" />
                        </div>
                        <span className="font-medium">{t('diskUsage')}</span>
                      </div>
                      <span className={`text-2xl font-bold ${getMetricColor(metrics.disk, { warning: 80, critical: 95 })}`}>
                        {metrics.disk}%
                      </span>
                    </div>
                    <Progress value={metrics.disk} className={`h-2 ${getProgressColor(metrics.disk, { warning: 80, critical: 95 })}`} />
                  </CardContent>
                </Card>
                
                {/* Network */}
                <Card className="card-nassaq">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <div className="p-2 bg-cyan-100 rounded-lg">
                          <Wifi className="h-5 w-5 text-cyan-600" />
                        </div>
                        <span className="font-medium">{t('networkUsage')}</span>
                      </div>
                      <span className="text-2xl font-bold text-cyan-600">
                        {metrics.network} KB/s
                      </span>
                    </div>
                    <div className="flex justify-between text-xs text-muted-foreground mt-1">
                      <span>↑ {metrics.netSentKbps || 0} KB/s</span>
                      <span>↓ {metrics.netRecvKbps || 0} KB/s</span>
                    </div>
                  </CardContent>
                </Card>
              </div>
              
              {/* Performance Chart */}
              <Card className="card-nassaq">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <TrendingUp className="h-5 w-5 text-brand-navy" />
                    {t('serverResources')} - {t('today')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-[300px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={performanceData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                        <XAxis dataKey="time" stroke="#9CA3AF" fontSize={12} />
                        <YAxis stroke="#9CA3AF" fontSize={12} />
                        <Tooltip 
                          contentStyle={{ 
                            backgroundColor: isDark ? '#1F2937' : '#FFFFFF',
                            border: '1px solid #E5E7EB',
                            borderRadius: '8px',
                          }}
                        />
                        <Area type="monotone" dataKey="cpu" stroke="#3B82F6" fill="#3B82F6" fillOpacity={0.2} name={t('cpuUsage')} />
                        <Area type="monotone" dataKey="memory" stroke="#8B5CF6" fill="#8B5CF6" fillOpacity={0.2} name={t('memoryUsage')} />
                        <Area type="monotone" dataKey="responseTime" stroke="#06B6D4" fill="#06B6D4" fillOpacity={0.2} name={t('avgResponseTime')} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
              
              {/* Stats Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* API Performance */}
                <Card className="card-nassaq bg-gradient-to-br from-blue-50 to-blue-100/50">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="p-2 bg-blue-500 rounded-lg">
                        <Globe className="h-5 w-5 text-white" />
                      </div>
                      <span className="font-medium">{t('apiPerformance')}</span>
                    </div>
                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <span className="text-sm text-muted-foreground">{t('avgResponseTime')}</span>
                        <span className="font-bold">{metrics.apiResponseTime} {t('ms')}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-muted-foreground">{t('requestsPerMin')}</span>
                        <span className="font-bold">{metrics.apiRequestsPerMin}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-muted-foreground">{t('successRate')}</span>
                        <span className="font-bold text-green-600">{metrics.apiSuccessRate}%</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
                
                {/* Database */}
                <Card className="card-nassaq bg-gradient-to-br from-green-50 to-green-100/50">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="p-2 bg-green-500 rounded-lg">
                        <Database className="h-5 w-5 text-white" />
                      </div>
                      <span className="font-medium">{t('databasePerformance')}</span>
                    </div>
                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <span className="text-sm text-muted-foreground">{t('activeConnections')}</span>
                        <span className="font-bold">{metrics.dbConnections}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-muted-foreground">{t('queryTime')}</span>
                        <span className="font-bold">{metrics.dbQueryTime} {t('ms')}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-muted-foreground">{t('slowQueries')}</span>
                        <span className={`font-bold ${metrics.dbSlowQueries > 5 ? 'text-yellow-600' : 'text-green-600'}`}>
                          {metrics.dbSlowQueries}
                        </span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
                
                {/* Operations */}
                <Card className="card-nassaq bg-gradient-to-br from-purple-50 to-purple-100/50">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="p-2 bg-purple-500 rounded-lg">
                        <Zap className="h-5 w-5 text-white" />
                      </div>
                      <span className="font-medium">{t('systemOperations')}</span>
                    </div>
                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <span className="text-sm text-muted-foreground">{t('totalOperations')}</span>
                        <span className="font-bold">{metrics.totalOperations.toLocaleString()}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-muted-foreground">{t('activeUsers')}</span>
                        <span className="font-bold">{metrics.activeUsers}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-muted-foreground">{t('errorCount')}</span>
                        <span className={`font-bold ${metrics.errors > 5 ? 'text-red-600' : 'text-green-600'}`}>
                          {metrics.errors}
                        </span>
                      </div>
                    </div>
                  </CardContent>
                </Card>
                
                {/* AI Status */}
                <Card className="card-nassaq bg-gradient-to-br from-pink-50 to-pink-100/50">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="p-2 bg-pink-500 rounded-lg">
                        <Brain className="h-5 w-5 text-white" />
                      </div>
                      <span className="font-medium">{t('aiStatus')}</span>
                    </div>
                    <div className="space-y-2">
                      <div className="flex justify-between">
                        <span className="text-sm text-muted-foreground">{t('aiOperations')}</span>
                        <span className="font-bold">{metrics.aiOperations}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-muted-foreground">{t('aiModels')}</span>
                        <span className="font-bold">{metrics.aiModelsActive} {t('active')}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-sm text-muted-foreground">{t('status')}</span>
                        <Badge className="bg-green-500">{t('healthy')}</Badge>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
              
              {/* Integrations & Jobs Row */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Integrations */}
                <Card className="card-nassaq">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Link2 className="h-5 w-5 text-brand-navy" />
                      {t('integrationsStatus')}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {integrations.map((integration) => (
                        <div 
                          key={integration.id}
                          className="flex items-center justify-between p-3 bg-muted/30 rounded-lg"
                        >
                          <div className="flex items-center gap-3">
                            {integration.status === 'connected' ? (
                              <Cloud className="h-5 w-5 text-green-500" />
                            ) : (
                              <CloudOff className="h-5 w-5 text-red-500" />
                            )}
                            <span className="font-medium">
                              {isRTL ? integration.name : integration.name_en}
                            </span>
                          </div>
                          <Badge className={integration.status === 'connected' ? 'bg-green-500' : 'bg-red-500'}>
                            {integration.status === 'connected' ? t('connected') : t('disconnected')}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
                
                {/* Background Jobs */}
                <Card className="card-nassaq">
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="flex items-center gap-2">
                        <Layers className="h-5 w-5 text-brand-navy" />
                        {t('backgroundJobs')}
                      </CardTitle>
                      <Button variant="outline" size="sm" onClick={() => setShowJobsSheet(true)}>
                        <Eye className="h-4 w-4 me-2" />
                        {t('details')}
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-4 gap-4 text-center">
                      <div className="p-3 bg-blue-50 rounded-xl">
                        <p className="text-2xl font-bold text-blue-600">{metrics.jobsRunning}</p>
                        <p className="text-xs text-muted-foreground">{t('running')}</p>
                      </div>
                      <div className="p-3 bg-yellow-50 rounded-xl">
                        <p className="text-2xl font-bold text-yellow-600">{metrics.jobsPending}</p>
                        <p className="text-xs text-muted-foreground">{t('pending')}</p>
                      </div>
                      <div className="p-3 bg-green-50 rounded-xl">
                        <p className="text-2xl font-bold text-green-600">{metrics.jobsCompleted}</p>
                        <p className="text-xs text-muted-foreground">{t('completed')}</p>
                      </div>
                      <div className="p-3 bg-red-50 rounded-xl">
                        <p className="text-2xl font-bold text-red-600">{metrics.jobsFailed}</p>
                        <p className="text-xs text-muted-foreground">{t('failed')}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>
            
            {/* Details Tab */}
            <TabsContent value="details" className="space-y-6">
              {/* Recent Errors */}
              <Card className="card-nassaq">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2">
                      <AlertTriangle className="h-5 w-5 text-yellow-500" />
                      {t('errors')}
                    </CardTitle>
                    <Button variant="outline" size="sm" onClick={() => setShowErrorLogs(true)}>
                      <FileText className="h-4 w-4 me-2" />
                      {t('viewErrorLogs')}
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {errorLogs.map((error) => (
                      <div 
                        key={error.id}
                        className={`flex items-center justify-between p-3 rounded-lg border ${
                          error.severity === 'critical' ? 'border-red-200 bg-red-50' :
                          error.severity === 'warning' ? 'border-yellow-200 bg-yellow-50' :
                          'border-gray-200 bg-gray-50'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          {error.severity === 'critical' ? (
                            <XCircle className="h-5 w-5 text-red-500" />
                          ) : error.severity === 'warning' ? (
                            <AlertTriangle className="h-5 w-5 text-yellow-500" />
                          ) : (
                            <Info className="h-5 w-5 text-blue-500" />
                          )}
                          <div>
                            <p className="font-medium">{error.type}</p>
                            <p className="text-sm text-muted-foreground">{error.message}</p>
                          </div>
                        </div>
                        <div className="text-left">
                          <p className="text-sm">{error.time}</p>
                          <p className="text-xs text-muted-foreground">{error.service}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
              
              {/* Jobs Details */}
              <Card className="card-nassaq">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Layers className="h-5 w-5 text-brand-navy" />
                    {t('jobsQueue')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {jobs.map((job) => (
                      <div key={job.id} className="space-y-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            {job.status === 'running' && <RefreshCw className="h-4 w-4 text-blue-500 animate-spin" />}
                            {job.status === 'pending' && <Clock className="h-4 w-4 text-yellow-500" />}
                            {job.status === 'completed' && <CheckCircle2 className="h-4 w-4 text-green-500" />}
                            {job.status === 'failed' && <XCircle className="h-4 w-4 text-red-500" />}
                            <span className="font-medium">{isRTL ? job.name : job.name_en}</span>
                          </div>
                          <Badge className={
                            job.status === 'running' ? 'bg-blue-500' :
                            job.status === 'pending' ? 'bg-yellow-500' :
                            job.status === 'completed' ? 'bg-green-500' :
                            'bg-red-500'
                          }>
                            {t(job.status)}
                          </Badge>
                        </div>
                        {job.status === 'running' && (
                          <Progress value={job.progress} className="h-2" />
                        )}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
            
            {/* Alerts Tab */}
            <TabsContent value="alerts" className="space-y-6">
              {alerts.filter(a => !a.resolved).length === 0 ? (
                <Card className="p-12 text-center">
                  <CheckCircle2 className="h-16 w-16 mx-auto text-green-500 mb-4" />
                  <h3 className="font-bold text-lg mb-2">{t('noAlerts')}</h3>
                  <p className="text-muted-foreground">{t('allSystemsOperational')}</p>
                </Card>
              ) : (
                <div className="space-y-4">
                  {alerts.map((alert) => (
                    <Card 
                      key={alert.id}
                      className={`card-nassaq ${
                        alert.severity === 'critical' ? 'border-red-500 bg-red-50' :
                        alert.severity === 'warning' ? 'border-yellow-500 bg-yellow-50' :
                        ''
                      } ${alert.resolved ? 'opacity-50' : ''}`}
                    >
                      <CardContent className="p-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            {alert.severity === 'critical' ? (
                              <XCircle className="h-6 w-6 text-red-500" />
                            ) : (
                              <AlertTriangle className="h-6 w-6 text-yellow-500" />
                            )}
                            <div>
                              <h4 className="font-bold">{isRTL ? alert.title : alert.title_en}</h4>
                              <p className="text-sm text-muted-foreground">{alert.time}</p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {alert.resolved ? (
                              <Badge className="bg-green-500">{t('resolved')}</Badge>
                            ) : (
                              <>
                                <Button 
                                  variant="outline" 
                                  size="sm"
                                  onClick={() => toast.success(t('alertEscalatedToTechTeam'))}
                                >
                                  <Bell className="h-4 w-4 me-2" />
                                  {t('escalateAlert')}
                                </Button>
                                <Button 
                                  size="sm" 
                                  className="bg-brand-navy"
                                  onClick={() => toast.success(t('alertProcessingStarted'))}
                                >
                                  {t('handle')}
                                </Button>
                              </>
                            )}
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </TabsContent>
            
            {/* Tools Tab */}
            <TabsContent value="tools" className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {/* View Error Logs */}
                <Card 
                  className="card-nassaq hover:shadow-lg transition-all cursor-pointer"
                  onClick={() => setShowErrorLogs(true)}
                >
                  <CardContent className="p-6 text-center">
                    <div className="w-14 h-14 mx-auto mb-4 rounded-xl bg-red-100 flex items-center justify-center">
                      <FileText className="h-7 w-7 text-red-600" />
                    </div>
                    <h3 className="font-bold mb-2">{t('viewLogs')}</h3>
                    <p className="text-sm text-muted-foreground">
                      {t('viewDetailedErrorLogs')}
                    </p>
                  </CardContent>
                </Card>
                
                {/* Monitor APIs */}
                <Card 
                  className="card-nassaq hover:shadow-lg transition-all cursor-pointer"
                  onClick={() => setShowApiMonitor(true)}
                >
                  <CardContent className="p-6 text-center">
                    <div className="w-14 h-14 mx-auto mb-4 rounded-xl bg-blue-100 flex items-center justify-center">
                      <Globe className="h-7 w-7 text-blue-600" />
                    </div>
                    <h3 className="font-bold mb-2">{t('monitorAPIs')}</h3>
                    <p className="text-sm text-muted-foreground">
                      {t('monitorApiEndpoints')}
                    </p>
                  </CardContent>
                </Card>
                
                {/* Monitor Jobs */}
                <Card 
                  className="card-nassaq hover:shadow-lg transition-all cursor-pointer"
                  onClick={() => setShowJobsSheet(true)}
                >
                  <CardContent className="p-6 text-center">
                    <div className="w-14 h-14 mx-auto mb-4 rounded-xl bg-purple-100 flex items-center justify-center">
                      <Layers className="h-7 w-7 text-purple-600" />
                    </div>
                    <h3 className="font-bold mb-2">{t('monitorJobs')}</h3>
                    <p className="text-sm text-muted-foreground">
                      {t('monitorBackgroundJobs')}
                    </p>
                  </CardContent>
                </Card>
                
                {/* Restart Service */}
                <Card 
                  className="card-nassaq hover:shadow-lg transition-all cursor-pointer"
                  onClick={() => {
                    toast.promise(
                      api.post('/system/restart-service').then(res => {
                        fetchMonitoringData();
                        return res;
                      }),
                      {
                        loading: t('restartingService'),
                        success: (res) => res.data?.status === 'healthy' ? t('serviceRestartedSuccessfully') : t('serviceHealthDegraded'),
                        error: t('restartFailed'),
                      }
                    );
                  }}
                >
                  <CardContent className="p-6 text-center">
                    <div className="w-14 h-14 mx-auto mb-4 rounded-xl bg-orange-100 flex items-center justify-center">
                      <RotateCcw className="h-7 w-7 text-orange-600" />
                    </div>
                    <h3 className="font-bold mb-2">{t('restartService')}</h3>
                    <p className="text-sm text-muted-foreground">
                      {t('restartASpecificService')}
                    </p>
                  </CardContent>
                </Card>
                
                {/* Re-Sync */}
                <Card 
                  className="card-nassaq hover:shadow-lg transition-all cursor-pointer"
                  onClick={() => {
                    toast.promise(
                      api.post('/system/resync').then(res => {
                        fetchMonitoringData();
                        return res;
                      }),
                      {
                        loading: t('resyncing'),
                        success: t('resyncCompletedSuccessfully'),
                        error: t('syncFailed'),
                      }
                    );
                  }}
                >
                  <CardContent className="p-6 text-center">
                    <div className="w-14 h-14 mx-auto mb-4 rounded-xl bg-cyan-100 flex items-center justify-center">
                      <RefreshCw className="h-7 w-7 text-cyan-600" />
                    </div>
                    <h3 className="font-bold mb-2">{t('reSync')}</h3>
                    <p className="text-sm text-muted-foreground">
                      {t('resyncIntegrations')}
                    </p>
                  </CardContent>
                </Card>
                
                {/* Escalate Alert */}
                <Card 
                  className="card-nassaq hover:shadow-lg transition-all cursor-pointer"
                  onClick={() => {
                    api.post('/system/escalate-alert')
                      .then(() => toast.success(t('alertEscalatedToTechTeam')))
                      .catch(() => toast.error(t('actionFailed')));
                  }}
                >
                  <CardContent className="p-6 text-center">
                    <div className="w-14 h-14 mx-auto mb-4 rounded-xl bg-yellow-100 flex items-center justify-center">
                      <Bell className="h-7 w-7 text-yellow-600" />
                    </div>
                    <h3 className="font-bold mb-2">{t('escalateAlert')}</h3>
                    <p className="text-sm text-muted-foreground">
                      {t('escalateAlertToTechTeam')}
                    </p>
                  </CardContent>
                </Card>
                
                {/* Download Report */}
                <Card 
                  className="card-nassaq hover:shadow-lg transition-all cursor-pointer"
                  onClick={() => {
                    const report = {
                      generated_at: new Date().toISOString(),
                      metrics: metrics,
                      errors: errorLogs,
                      jobs: jobs,
                      integrations: integrations,
                      alerts: alerts,
                    };
                    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
                    const link = document.createElement('a');
                    link.href = URL.createObjectURL(blob);
                    link.download = `system_diagnostic_${new Date().toISOString().split('T')[0]}.json`;
                    link.click();
                    toast.success(t('diagnosticReportDownloaded'));
                  }}
                >
                  <CardContent className="p-6 text-center">
                    <div className="w-14 h-14 mx-auto mb-4 rounded-xl bg-green-100 flex items-center justify-center">
                      <Download className="h-7 w-7 text-green-600" />
                    </div>
                    <h3 className="font-bold mb-2">{t('downloadReport')}</h3>
                    <p className="text-sm text-muted-foreground">
                      {t('downloadDiagnosticReport')}
                    </p>
                  </CardContent>
                </Card>
                
                {/* AI Diagnosis */}
                <Card 
                  className="card-nassaq hover:shadow-lg transition-all cursor-pointer bg-gradient-to-br from-pink-50 to-purple-50"
                  onClick={() => setShowDiagnosticDialog(true)}
                >
                  <CardContent className="p-6 text-center">
                    <div className="w-14 h-14 mx-auto mb-4 rounded-xl bg-gradient-to-br from-pink-500 to-purple-500 flex items-center justify-center">
                      <Brain className="h-7 w-7 text-white" />
                    </div>
                    <h3 className="font-bold mb-2">{t('aiDiagnosis')}</h3>
                    <p className="text-sm text-muted-foreground">
                      {t('runAiSystemDiagnosis')}
                    </p>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>
          </Tabs>
        </main>
        
        {/* Error Logs Sheet */}
        <Sheet open={showErrorLogs} onOpenChange={setShowErrorLogs}>
          <SheetContent side={isRTL ? 'left' : 'right'} className="w-[500px] sm:w-[700px]">
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-brand-navy" />
                {t('viewErrorLogs')}
              </SheetTitle>
            </SheetHeader>
            <ScrollArea className="h-[calc(100vh-120px)] mt-6">
              <div className="space-y-4 pe-4">
                {errorLogs.length === 0 ? (
                  <div className="text-center text-muted-foreground py-12">
                    <CheckCircle2 className="h-12 w-12 mx-auto mb-4 text-green-500" />
                    <p>{t('noErrorsRecorded')}</p>
                  </div>
                ) : (
                  errorLogs.map((error, index) => (
                  <div 
                    key={`${error.id}-${index}`}
                    className="p-4 border rounded-lg space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <Badge className={
                        error.severity === 'critical' ? 'bg-red-500' :
                        error.severity === 'warning' ? 'bg-yellow-500' :
                        'bg-blue-500'
                      }>
                        {error.severity}
                      </Badge>
                      <span className="text-sm text-muted-foreground">{error.time}</span>
                    </div>
                    <p className="font-medium">{error.type}</p>
                    <p className="text-sm text-muted-foreground">{error.message}</p>
                    <p className="text-xs text-muted-foreground font-mono bg-muted p-2 rounded">
                      Service: {error.service}
                    </p>
                  </div>
                ))
                )}
              </div>
            </ScrollArea>
          </SheetContent>
        </Sheet>
        
        {/* Jobs Sheet */}
        <Sheet open={showJobsSheet} onOpenChange={setShowJobsSheet}>
          <SheetContent side={isRTL ? 'left' : 'right'} className="w-[500px]">
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2">
                <Layers className="h-5 w-5 text-brand-navy" />
                {t('backgroundJobs')}
              </SheetTitle>
            </SheetHeader>
            <div className="mt-6 space-y-4">
              {jobs.length === 0 ? (
                <div className="text-center text-muted-foreground py-12">
                  <CheckCircle2 className="h-12 w-12 mx-auto mb-4 text-green-500" />
                  <p>{t('noActiveJobs')}</p>
                </div>
              ) : (
                jobs.map((job) => (
                <Card key={job.id}>
                  <CardContent className="p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{isRTL ? job.name : job.name_en}</span>
                      <Badge className={
                        job.status === 'running' ? 'bg-blue-500' :
                        job.status === 'pending' ? 'bg-yellow-500' :
                        job.status === 'completed' ? 'bg-green-500' :
                        'bg-red-500'
                      }>
                        {t(job.status)}
                      </Badge>
                    </div>
                    {job.status === 'running' && (
                      <>
                        <Progress value={job.progress} className="h-2" />
                        <p className="text-sm text-muted-foreground">{job.progress}%</p>
                      </>
                    )}
                    <div className="flex items-center justify-between text-sm text-muted-foreground">
                      <span>{t('started')} {job.started}</span>
                      {job.status === 'running' && (
                        <Button variant="ghost" size="sm">
                          <Pause className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))
              )}
            </div>
          </SheetContent>
        </Sheet>
        
        {/* API Monitor Sheet */}
        <Sheet open={showApiMonitor} onOpenChange={setShowApiMonitor}>
          <SheetContent side={isRTL ? 'left' : 'right'} className="w-[500px] sm:w-[600px]">
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2">
                <Globe className="h-5 w-5 text-brand-navy" />
                {t('monitorAPIs')}
              </SheetTitle>
            </SheetHeader>
            <div className="mt-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <Card>
                  <CardContent className="p-4 text-center">
                    <p className="text-3xl font-bold text-blue-600">{metrics.apiResponseTime}<span className="text-sm font-normal text-muted-foreground ms-1">{t('ms')}</span></p>
                    <p className="text-sm text-muted-foreground mt-1">{t('avgResponseTime')}</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-4 text-center">
                    <p className="text-3xl font-bold text-green-600">{metrics.apiSuccessRate}<span className="text-sm font-normal text-muted-foreground ms-1">%</span></p>
                    <p className="text-sm text-muted-foreground mt-1">{t('successRate')}</p>
                  </CardContent>
                </Card>
              </div>
              <div className="space-y-3">
                <div className="flex justify-between items-center p-3 bg-muted/30 rounded-lg">
                  <span className="text-sm font-medium">{t('totalRequests')}</span>
                  <span className="font-bold">{metrics.totalOperations.toLocaleString()}</span>
                </div>
                <div className="flex justify-between items-center p-3 bg-muted/30 rounded-lg">
                  <span className="text-sm font-medium">{t('requestsPerMin')}</span>
                  <span className="font-bold">{metrics.apiRequestsPerMin}</span>
                </div>
                <div className="flex justify-between items-center p-3 bg-muted/30 rounded-lg">
                  <span className="text-sm font-medium">{t('failedRequests')}</span>
                  <span className={`font-bold ${metrics.apiFailedRequests > 0 ? 'text-red-600' : 'text-green-600'}`}>{metrics.apiFailedRequests}</span>
                </div>
                <div className="flex justify-between items-center p-3 bg-muted/30 rounded-lg">
                  <span className="text-sm font-medium">P95 {t('responseTime')}</span>
                  <span className="font-bold">{metrics.p95ResponseMs || 0} {t('ms')}</span>
                </div>
                <div className="flex justify-between items-center p-3 bg-muted/30 rounded-lg">
                  <span className="text-sm font-medium">P99 {t('responseTime')}</span>
                  <span className="font-bold">{metrics.p99ResponseMs || 0} {t('ms')}</span>
                </div>
                <div className="flex justify-between items-center p-3 bg-muted/30 rounded-lg">
                  <span className="text-sm font-medium">{t('dbConnections')}</span>
                  <span className="font-bold">{metrics.dbConnections} / {metrics.poolSize || 0}</span>
                </div>
                <div className="flex justify-between items-center p-3 bg-muted/30 rounded-lg">
                  <span className="text-sm font-medium">{t('dbLatency')}</span>
                  <span className="font-bold">{metrics.dbQueryTime} {t('ms')}</span>
                </div>
                <div className="flex justify-between items-center p-3 bg-muted/30 rounded-lg">
                  <span className="text-sm font-medium">{t('cacheHitRate')}</span>
                  <span className="font-bold">{metrics.cacheHitRate || 0}%</span>
                </div>
              </div>
            </div>
          </SheetContent>
        </Sheet>

        {/* AI Diagnostic Dialog */}
        <Dialog open={showDiagnosticDialog} onOpenChange={(open) => { setShowDiagnosticDialog(open); if (!open) setDiagnosisResults(null); }}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Brain className="h-5 w-5 text-brand-navy" />
                {t('aiDiagnosis')}
              </DialogTitle>
              <DialogDescription>
                {t('theSystemWillPerformComprehensiveTechnicalAnalysis')}
              </DialogDescription>
            </DialogHeader>
            
            {isDiagnosing ? (
              <div className="py-8 text-center">
                <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-brand-navy/10 flex items-center justify-center">
                  <RefreshCw className="h-8 w-8 text-brand-navy animate-spin" />
                </div>
                <p className="font-medium">{t('runningDiagnosis')}</p>
                <p className="text-sm text-muted-foreground mt-2">{t('pleaseWait')}</p>
              </div>
            ) : diagnosisResults ? (
              <div className="py-4 space-y-4">
                <div className={`flex items-center gap-3 p-3 rounded-lg ${
                  diagnosisResults.status === 'healthy' ? 'bg-green-50 border border-green-200' :
                  diagnosisResults.status === 'warning' ? 'bg-yellow-50 border border-yellow-200' :
                  'bg-red-50 border border-red-200'
                }`}>
                  {diagnosisResults.status === 'healthy' ? (
                    <CheckCircle2 className="h-6 w-6 text-green-500" />
                  ) : diagnosisResults.status === 'warning' ? (
                    <AlertTriangle className="h-6 w-6 text-yellow-500" />
                  ) : (
                    <XCircle className="h-6 w-6 text-red-500" />
                  )}
                  <span className="font-bold">
                    {diagnosisResults.status === 'healthy' ? t('systemHealthy') :
                     diagnosisResults.status === 'warning' ? t('systemWarnings') :
                     t('systemCritical')}
                  </span>
                </div>
                <div className="space-y-2">
                  {diagnosisResults.findings?.map((finding, idx) => (
                    <div key={idx} className="flex items-center gap-3 p-3 bg-muted/30 rounded-lg">
                      {finding.status === 'healthy' ? (
                        <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0" />
                      ) : finding.status === 'warning' ? (
                        <AlertTriangle className="h-5 w-5 text-yellow-500 shrink-0" />
                      ) : finding.status === 'critical' ? (
                        <XCircle className="h-5 w-5 text-red-500 shrink-0" />
                      ) : (
                        <Info className="h-5 w-5 text-gray-400 shrink-0" />
                      )}
                      <span className="text-sm">{finding.message}</span>
                    </div>
                  ))}
                </div>
                {diagnosisResults.recommendations?.length > 0 && (
                  <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg space-y-1">
                    <p className="font-medium text-sm text-blue-800">{t('recommendations')}</p>
                    {diagnosisResults.recommendations.map((rec, idx) => (
                      <p key={idx} className="text-sm text-blue-700">{rec}</p>
                    ))}
                  </div>
                )}
                <DialogFooter className="flex-row-reverse gap-2">
                  <Button variant="outline" onClick={() => { setShowDiagnosticDialog(false); setDiagnosisResults(null); }}>
                    {t('close')}
                  </Button>
                  <Button onClick={runDiagnosis} className="bg-brand-navy">
                    <RefreshCw className="h-4 w-4 me-2" />
                    {t('rerun')}
                  </Button>
                </DialogFooter>
              </div>
            ) : (
              <>
                <div className="py-4 space-y-3">
                  <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-lg">
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                    <span>{t('performanceMetricsAnalysis')}</span>
                  </div>
                  <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-lg">
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                    <span>{t('resourceConsumptionReview')}</span>
                  </div>
                  <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-lg">
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                    <span>{t('integrationsCheck')}</span>
                  </div>
                  <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-lg">
                    <CheckCircle2 className="h-5 w-5 text-green-500" />
                    <span>{t('errorPatternAnalysis')}</span>
                  </div>
                </div>
                <DialogFooter className="flex-row-reverse gap-2">
                  <Button variant="outline" onClick={() => setShowDiagnosticDialog(false)}>
                    {t('cancel')}
                  </Button>
                  <Button onClick={runDiagnosis} className="bg-brand-navy">
                    <Brain className="h-4 w-4 me-2" />
                    {t('runDiagnostics')}
                  </Button>
                </DialogFooter>
              </>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </Sidebar>
  );
};

export default SystemMonitoringPage;
