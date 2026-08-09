import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/shared/contexts/AuthContext';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { toast } from 'sonner';
import { Progress } from '@/shared/components/ui/progress';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/shared/components/ui/dialog';
import {
  Brain, Activity, Database, Upload, Bell, Play, RefreshCw, Eye,
  CheckCircle2, XCircle, Sparkles, History,
  Gauge, ExternalLink, AlertTriangle
} from 'lucide-react';

import { useTranslation } from '@/shared/contexts/ThemeContext';

const AI_STATUS = {
  ACTIVE: { label: 'نشط', label_en: 'Active', color: 'bg-green-500', textColor: 'text-green-500' },
  PARTIAL: { label: 'نشط جزئياً', label_en: 'Partially Active', color: 'bg-yellow-500', textColor: 'text-yellow-500' },
  STOPPED: { label: 'متوقف', label_en: 'Stopped', color: 'bg-red-500', textColor: 'text-red-500' },
};

// Maps frontend operation IDs to backend operation_type values
const AI_OPERATIONS = [
  {
    id: 'system_diagnosis',
    backendType: 'diagnosis',
    title: 'تشخيص النظام',
    title_en: 'System Diagnosis',
    desc: 'فحص شامل للنظام',
    desc_en: 'Full system scan',
    icon: Gauge,
    color: 'bg-blue-500',
  },
  {
    id: 'data_quality',
    backendType: 'data_quality',
    title: 'فحص جودة البيانات',
    title_en: 'Data Quality Scan',
    desc: 'اكتشاف النقص والتكرار',
    desc_en: 'Find gaps & duplicates',
    icon: Database,
    color: 'bg-green-500',
  },
  {
    id: 'import_analyzer',
    backendType: 'import_analysis',
    title: 'تحليل ملفات الاستيراد',
    title_en: 'Import Analyzer',
    desc: 'نتائج الملفات المستوردة',
    desc_en: 'Import files results',
    icon: Upload,
    color: 'bg-purple-500',
  },
  {
    id: 'alerts_review',
    backendType: 'alerts_review',
    title: 'مراجعة التنبيهات',
    title_en: 'Alerts Review',
    desc: 'التنبيهات غير المقروءة',
    desc_en: 'Unread alerts',
    icon: Bell,
    color: 'bg-red-500',
  },
];

const OPERATION_LABELS = {
  diagnosis: { ar: 'تشخيص النظام', en: 'System Diagnosis' },
  data_quality: { ar: 'فحص جودة البيانات', en: 'Data Quality Scan' },
  import_analysis: { ar: 'تحليل ملفات الاستيراد', en: 'Import Analyzer' },
  alerts_review: { ar: 'مراجعة التنبيهات', en: 'Alerts Review' },
};

function fmtTime(iso, isRTL) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleTimeString(isRTL ? 'ar-SA' : 'en-US', { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

export default function QuickAIOperationsPanel({ api: apiProp, isRTL = true, initialStats = null }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { api: apiCtx } = useAuth();
  const api = apiProp || apiCtx;

  // Live data states
  // initialStats: caller-provided stats snapshot (avoids a redundant GET when
  // the parent (AdminDashboard) already fetches /admin/command-center/stats).
  const [stats, setStats] = useState(initialStats);
  // Only the FIRST load reuses the caller's snapshot. Every later load —
  // manual refresh, post-operation refresh — must hit the endpoint, otherwise
  // the panel would render stats that can never change.
  const reuseInitialStatsRef = useRef(initialStats != null);
  const [notifStats, setNotifStats] = useState(null);
  const [suggestedActions, setSuggestedActions] = useState([]);
  const [recentOps, setRecentOps] = useState([]);
  const [opsToday, setOpsToday] = useState(0);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(new Date());

  // Dialog states
  const [activeDialog, setActiveDialog] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [operationResult, setOperationResult] = useState(null);

  const loadAllInFlightRef = useRef(null);

  const loadAll = useCallback(async (silent = false) => {
    if (!api) return;
    if (!silent && loadAllInFlightRef.current) return loadAllInFlightRef.current;
    if (!silent) setLoading(true);

    const task = (async () => {
      try {
        // Skip the stats fetch ONCE when the parent already provided them
        // (deduplication of the /admin page's duplicate GET). Any subsequent
        // load — manual refresh, post-operation refresh, poll — re-fetches.
        const reuseProvidedStats = reuseInitialStatsRef.current;
        reuseInitialStatsRef.current = false;
        const requests = [
          reuseProvidedStats ? Promise.resolve(null) : api.get('/admin/command-center/stats'),
          api.get('/admin/notifications/stats'),
          api.get('/admin/ai-suggested-actions'),
          api.get('/admin/ai-operations/history?limit=5'),
        ];
        const [statsRes, notifRes, suggRes, histRes] = await Promise.allSettled(requests);
        if (statsRes.status === 'fulfilled' && statsRes.value !== null) {
          setStats(statsRes.value.data || statsRes.value);
        }
        if (notifRes.status === 'fulfilled') setNotifStats(notifRes.value.data || notifRes.value);
        if (suggRes.status === 'fulfilled') {
          const data = suggRes.value.data || suggRes.value;
          setSuggestedActions(data.actions || []);
        }
        if (histRes.status === 'fulfilled') {
          const data = histRes.value.data || histRes.value;
          setRecentOps(data.history || []);
          setOpsToday(data.operations_today || 0);
        }
        setLastUpdate(new Date());
      } catch (e) {
        console.error('AI panel load failed', e);
      } finally {
        if (!silent) setLoading(false);
        loadAllInFlightRef.current = null;
      }
    })();

    loadAllInFlightRef.current = task;
    return task;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // Derived live status values
  const aiEnabledSchools = stats?.ai_enabled_schools ?? 0;
  const totalSchools = stats?.registered_schools ?? 0;
  const operationsToday = opsToday;
  const openAlerts = notifStats?.unread_notifications ?? 0;
  const pendingRecommendations = suggestedActions.length;
  const aiStatus = totalSchools === 0
    ? AI_STATUS.STOPPED
    : (aiEnabledSchools < totalSchools ? AI_STATUS.PARTIAL : AI_STATUS.ACTIVE);

  // Run a real AI operation
  const runOperation = async (operationId) => {
    const op = AI_OPERATIONS.find(o => o.id === operationId);
    if (!op || !api) return;
    setActiveDialog(operationId);
    setIsProcessing(true);
    setOperationResult(null);
    try {
      const res = await api.post(`/admin/ai-operation/${op.backendType}`);
      const data = res.data || res;
      setOperationResult({
        title: isRTL ? op.title : op.title_en,
        summary: data.message || (isRTL ? 'تمت العملية بنجاح' : 'Operation completed'),
        details: data.details || {},
        backendType: op.backendType,
      });
      // Refresh stats and history after running
      loadAll(true);
    } catch (e) {
      setOperationResult({
        title: isRTL ? op.title : op.title_en,
        summary: isRTL ? 'تعذر تنفيذ العملية' : 'Operation failed',
        details: {},
        error: true,
      });
      toast.error(isRTL ? 'تعذر تنفيذ العملية' : 'Operation failed');
    } finally {
      setIsProcessing(false);
    }
  };

  const refreshStatus = async () => {
    await loadAll(false);
    toast.success(t('aiStatusUpdated'));
  };

  const handleActionClick = (action) => {
    navigate(action.link);
  };

  const getOperation = (id) => AI_OPERATIONS.find(op => op.id === id || op.backendType === id);

  const unreadBadge = openAlerts > 0 ? openAlerts : null;

  return (
    <section data-testid="ai-operations-panel" className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-cairo text-xl font-bold flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-purple to-brand-turquoise flex items-center justify-center">
              <Brain className="h-6 w-6 text-white" />
            </div>
            {t('quickAiOperationsPanel')}
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            {t('executeAnalyzeAndMonitorAiOperationsAcrossTheEntir')}
          </p>
        </div>
      </div>

      {/* Status bar */}
      <Card className="card-nassaq bg-gradient-to-r from-brand-navy/5 to-brand-purple/5 border-brand-navy/20">
        <CardContent className="p-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4 flex-wrap">
              <div className="flex items-center gap-2">
                <div className={`w-3 h-3 rounded-full ${aiStatus.color} animate-pulse`} />
                <span className="font-bold">{isRTL ? aiStatus.label : aiStatus.label_en}</span>
              </div>
              <div className="h-6 w-px bg-border" />
              <div className="flex items-center gap-1 text-sm">
                <Activity className="h-4 w-4 text-brand-turquoise" />
                <span data-testid="ops-today">{operationsToday}</span>
                <span className="text-muted-foreground">{t('opsToday')}</span>
              </div>
              <div className="h-6 w-px bg-border" />
              <div className="flex items-center gap-1 text-sm">
                <Bell className="h-4 w-4 text-orange-500" />
                <span data-testid="unread-alerts">{openAlerts}</span>
                <span className="text-muted-foreground">{t('unreadAlerts2')}</span>
              </div>
              <div className="h-6 w-px bg-border" />
              <div className="flex items-center gap-1 text-sm">
                <Sparkles className="h-4 w-4 text-brand-purple" />
                <span data-testid="recommendations-count">{pendingRecommendations}</span>
                <span className="text-muted-foreground">{t('recommendations')}</span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={refreshStatus}
                disabled={loading}
                className="rounded-lg"
                data-testid="ai-refresh-status"
              >
                <RefreshCw className={`h-4 w-4 me-1 ${loading ? 'animate-spin' : ''}`} />
                {t('refresh')}
              </Button>
              <Button variant="outline" size="sm" onClick={() => runOperation('system_diagnosis')} className="rounded-lg">
                <Gauge className="h-4 w-4 me-1" />
                {t('diagnose')}
              </Button>
            </div>
          </div>

          <div className="flex items-center gap-4 mt-3 pt-3 border-t text-xs text-muted-foreground flex-wrap">
            <span>{t('lastUpdate')} {lastUpdate.toLocaleTimeString(isRTL ? 'ar-SA' : 'en-US')}</span>
            <span>•</span>
            <span>{t('aienabledSchools')} {aiEnabledSchools}/{totalSchools}</span>
            <span>•</span>
            <span className="text-green-500 flex items-center gap-1">
              <CheckCircle2 className="h-3 w-3" />
              {t('allEnginesRunning')}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* 4 operation cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {AI_OPERATIONS.map((op) => {
          const showBadge = op.id === 'alerts_review' && unreadBadge;
          return (
            <Card
              key={op.id}
              className="card-nassaq hover:shadow-lg hover:border-brand-purple/30 transition-all cursor-pointer group relative overflow-hidden"
              onClick={() => runOperation(op.id)}
              data-testid={`ai-op-${op.id}`}
            >
              <div className="absolute top-2 right-2 flex items-center gap-1">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                </span>
              </div>

              <CardContent className="p-4 flex flex-col items-center text-center gap-3">
                <div className="relative">
                  <div className={`w-14 h-14 rounded-2xl ${op.color} flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform`}>
                    <op.icon className="h-7 w-7 text-white" />
                  </div>
                  {showBadge && (
                    <Badge className="absolute -top-2 -end-2 bg-red-500 text-white text-xs px-2 animate-pulse">
                      {showBadge}
                    </Badge>
                  )}
                </div>
                <div>
                  <p className="font-cairo font-bold text-sm">{isRTL ? op.title : op.title_en}</p>
                  <p className="text-xs text-muted-foreground">{isRTL ? op.desc : op.desc_en}</p>
                </div>
                <div className="flex items-center gap-1 text-xs text-muted-foreground group-hover:text-brand-purple transition-colors">
                  <Play className="h-3 w-3" />
                  <span>{t('clickToRun')}</span>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Suggested actions + Recent operations */}
      <div className="grid md:grid-cols-2 gap-4">
        <Card className="card-nassaq">
          <CardHeader className="pb-2">
            <CardTitle className="font-cairo text-base flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-yellow-500" />
              {t('aiSuggestedActions')}
              <Badge className="bg-yellow-500 text-white">{suggestedActions.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {suggestedActions.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-6">
                {isRTL ? 'لا توجد إجراءات مقترحة حالياً' : 'No suggested actions right now'}
              </p>
            ) : (
              <div className="space-y-2">
                {suggestedActions.map((action) => (
                  <div
                    key={action.id}
                    className={`flex items-center gap-3 p-3 rounded-lg border transition-all hover:bg-muted/50 ${
                      action.priority === 'high' ? 'border-red-200 bg-red-50/50' :
                      action.priority === 'medium' ? 'border-yellow-200 bg-yellow-50/50' :
                      'border-blue-200 bg-blue-50/50'
                    }`}
                  >
                    <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                      action.priority === 'high' ? 'bg-red-500' :
                      action.priority === 'medium' ? 'bg-yellow-500' :
                      'bg-blue-500'
                    }`} />
                    <span className="flex-1 text-sm">{isRTL ? action.title : (action.title_en || action.title)}</span>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 px-3 text-xs gap-1"
                      onClick={() => handleActionClick(action)}
                    >
                      <ExternalLink className="h-3 w-3" />
                      {isRTL ? action.linkText : (action.linkText_en || action.linkText)}
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="card-nassaq">
          <CardHeader className="pb-2">
            <CardTitle className="font-cairo text-base flex items-center gap-2 justify-between">
              <span className="flex items-center gap-2">
                <History className="h-5 w-5 text-brand-turquoise" />
                {t('recentOperations')}
              </span>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 px-2"
                onClick={() => loadAll(true)}
                title={t('refresh')}
              >
                <RefreshCw className="h-3 w-3" />
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {recentOps.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-6">
                {isRTL ? 'لا توجد عمليات حديثة' : 'No recent operations'}
              </p>
            ) : (
              <div className="space-y-2">
                {recentOps.map((op) => {
                  const label = OPERATION_LABELS[op.operation_type] || { ar: op.operation_type, en: op.operation_type };
                  return (
                    <div
                      key={op.id}
                      className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-all"
                    >
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-green-100 text-green-600">
                        <CheckCircle2 className="h-4 w-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{isRTL ? label.ar : label.en}</p>
                        <p className="text-xs text-muted-foreground truncate">
                          {op.performed_by_name || (isRTL ? 'مستخدم' : 'User')} • {fmtTime(op.created_at, isRTL)}
                        </p>
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 px-2 cursor-pointer hover:bg-brand-turquoise/10"
                        onClick={() => {
                          setActiveDialog(op.operation_type);
                          setIsProcessing(false);
                          setOperationResult({
                            title: isRTL ? label.ar : label.en,
                            summary: op.message,
                            details: op.details || {},
                            backendType: op.operation_type,
                            historical: true,
                          });
                        }}
                      >
                        <Eye className="h-3 w-3" />
                      </Button>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Result dialog */}
      <Dialog open={!!activeDialog} onOpenChange={() => { setActiveDialog(null); setOperationResult(null); setIsProcessing(false); }}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="ai-result-dialog">
          <DialogHeader>
            <DialogTitle className="font-cairo flex items-center gap-2">
              {activeDialog && getOperation(activeDialog) && (
                <>
                  <div className={`w-8 h-8 rounded-lg ${getOperation(activeDialog).color} flex items-center justify-center`}>
                    {React.createElement(getOperation(activeDialog).icon, { className: "h-4 w-4 text-white" })}
                  </div>
                  {isRTL ? getOperation(activeDialog).title : getOperation(activeDialog).title_en}
                </>
              )}
              {activeDialog && !getOperation(activeDialog) && operationResult && (
                <span>{operationResult.title}</span>
              )}
            </DialogTitle>
            <DialogDescription>
              {isProcessing ? t('analyzing') : t('operationResults')}
            </DialogDescription>
          </DialogHeader>

          {isProcessing ? (
            <div className="py-12 flex flex-col items-center gap-4">
              <div className="w-16 h-16 rounded-full bg-brand-purple/10 flex items-center justify-center">
                <Brain className="h-8 w-8 text-brand-purple animate-pulse" />
              </div>
              <p className="text-sm text-muted-foreground">{t('analyzingData')}</p>
              <Progress value={66} className="w-48" />
            </div>
          ) : operationResult && (
            <OperationResultView result={operationResult} isRTL={isRTL} navigate={navigate} onClose={() => setActiveDialog(null)} t={t} />
          )}
        </DialogContent>
      </Dialog>
    </section>
  );
}

function OperationResultView({ result, isRTL, navigate, onClose, t }) {
  const d = result.details || {};
  const backendType = result.backendType;

  return (
    <div className="space-y-4">
      <div className="p-4 rounded-lg bg-muted/50">
        <h4 className="font-bold mb-2">{result.title}</h4>
        <p className="text-sm text-muted-foreground">{result.summary}</p>
      </div>

      {backendType === 'diagnosis' && (
        <div className="space-y-3">
          {typeof d.health_score === 'number' && (
            <div className="p-4 rounded-lg border">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">{isRTL ? 'مؤشر صحة النظام' : 'System Health Score'}</span>
                <span className={`font-bold ${d.health_score >= 80 ? 'text-green-500' : d.health_score >= 60 ? 'text-yellow-500' : 'text-red-500'}`}>
                  {d.health_score}%
                </span>
              </div>
              <Progress value={d.health_score} className="h-2" />
            </div>
          )}
          <div className="grid grid-cols-3 gap-3">
            <Stat label={isRTL ? 'إجمالي المدارس' : 'Total Schools'} value={d.total_schools ?? 0} />
            <Stat label={isRTL ? 'مدارس نشطة' : 'Active Schools'} value={d.active_schools ?? 0} color="text-green-600" bg="bg-green-50" border="border-green-200" />
            <Stat label={isRTL ? 'مشاكل' : 'Issues'} value={d.issues_found ?? 0} color="text-red-600" bg="bg-red-50" border="border-red-200" />
          </div>
        </div>
      )}

      {backendType === 'data_quality' && (
        <div className="space-y-3">
          {typeof d.quality_score === 'number' && (
            <div className="p-4 rounded-lg border">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium">{t('dataQualityScore')}</span>
                <span className={`font-bold ${d.quality_score >= 80 ? 'text-green-500' : d.quality_score >= 60 ? 'text-yellow-500' : 'text-red-500'}`}>
                  {d.quality_score}%
                </span>
              </div>
              <Progress value={d.quality_score} className="h-2" />
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <Stat label={isRTL ? 'طلاب ببيانات ناقصة' : 'Students with missing data'} value={d.students_missing_data ?? 0} color="text-yellow-600" bg="bg-yellow-50" border="border-yellow-200" />
            <Stat label={isRTL ? 'معلمون ببيانات ناقصة' : 'Teachers with missing data'} value={d.teachers_missing_data ?? 0} color="text-yellow-600" bg="bg-yellow-50" border="border-yellow-200" />
          </div>
        </div>
      )}

      {backendType === 'import_analysis' && (
        <div className="space-y-3">
          <div className="grid grid-cols-4 gap-3">
            <Stat label={isRTL ? 'ملفات اليوم' : 'Files'} value={d.files_analyzed ?? 0} />
            <Stat label={isRTL ? 'صفوف مستوردة' : 'Imported'} value={d.imported ?? 0} color="text-green-600" bg="bg-green-50" border="border-green-200" />
            <Stat label={isRTL ? 'صفوف فشلت' : 'Failed'} value={d.failed ?? 0} color="text-red-600" bg="bg-red-50" border="border-red-200" />
            <Stat label={isRTL ? 'تحتاج مراجعة' : 'Need Review'} value={d.files_with_failures ?? 0} color="text-yellow-600" bg="bg-yellow-50" border="border-yellow-200" />
          </div>
          {Array.isArray(d.recent) && d.recent.length > 0 && (
            <div className="space-y-2">
              {d.recent.map((r, i) => (
                <div key={i} className="flex items-center justify-between p-3 rounded-lg border bg-muted/30">
                  <div className="text-sm truncate">
                    <p className="font-medium truncate">{r.filename || r.action}</p>
                    <p className="text-xs text-muted-foreground">
                      {isRTL ? 'مستورد' : 'Imported'}: {r.imported ?? 0} • {isRTL ? 'فشل' : 'Failed'}: {r.failed ?? 0}
                    </p>
                  </div>
                  <Badge className={r.failed > 0 ? 'bg-red-500' : 'bg-green-500'}>
                    {r.failed > 0 ? (isRTL ? 'به أخطاء' : 'Errors') : (isRTL ? 'نجاح' : 'Success')}
                  </Badge>
                </div>
              ))}
            </div>
          )}
          {(!d.recent || d.recent.length === 0) && (d.files_analyzed ?? 0) === 0 && (
            <p className="text-sm text-muted-foreground text-center py-4">
              {t('noImportsToday')}
            </p>
          )}
        </div>
      )}

      {backendType === 'alerts_review' && (
        <div className="space-y-3">
          <div className="p-4 rounded-lg bg-red-50 border border-red-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Bell className="h-6 w-6 text-red-500" />
                <div>
                  <p className="font-bold text-red-700">{d.pending_alerts ?? 0} {t('unreadAlerts3')}</p>
                  <p className="text-sm text-red-600">{t('clickToViewAlertsPage')}</p>
                </div>
              </div>
              <Button
                className="bg-red-500 hover:bg-red-600"
                onClick={() => { onClose(); navigate('/admin/audit'); }}
              >
                <ExternalLink className="h-4 w-4 me-1" />
                {t('viewAlerts')}
              </Button>
            </div>
          </div>
          {Array.isArray(d.recent) && d.recent.length > 0 && (
            <div className="space-y-2">
              {d.recent.map((n) => (
                <div key={n.id} className="flex items-center gap-3 p-3 rounded-lg border bg-muted/30">
                  <AlertTriangle className="h-4 w-4 text-orange-500" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{n.title || n.type}</p>
                    <p className="text-xs text-muted-foreground">{fmtTime(n.created_at, isRTL)}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, color = '', bg = 'bg-muted/50', border = '' }) {
  return (
    <div className={`p-3 rounded-lg text-center ${bg} ${border ? `border ${border}` : ''}`}>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      <p className={`text-xs ${color || 'text-muted-foreground'}`}>{label}</p>
    </div>
  );
}
