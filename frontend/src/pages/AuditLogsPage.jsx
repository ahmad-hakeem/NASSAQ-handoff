/**
 * AuditLogsPage - صفحة سجلات التدقيق
 * عرض شامل لجميع أحداث النظام مع بيانات المستخدم والجهاز
 */

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import {
  Shield, Search, Download, Clock, User, AlertTriangle,
  CheckCircle, XCircle, Activity, FileText, RefreshCw,
  Calendar, Monitor, Smartphone, Tablet, Globe, Cpu,
  LogIn, LogOut, Settings, Trash2, Edit, Plus, ChevronDown,
  ChevronRight, Eye, Lock, Unlock, Database,
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Sidebar } from '../components/layout/Sidebar';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';

/* ─── helpers ─────────────────────────────────────────── */

const SEVERITY_CFG = {
  critical: { label: 'حرج',       bg: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',    dot: 'bg-red-500' },
  high:     { label: 'عالي',      bg: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400', dot: 'bg-orange-500' },
  medium:   { label: 'متوسط',     bg: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400', dot: 'bg-yellow-500' },
  low:      { label: 'منخفض',     bg: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400', dot: 'bg-green-500' },
  info:     { label: 'معلومات',   bg: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400', dot: 'bg-blue-400' },
};

const ROLE_AR = {
  platform_admin: 'مدير المنصة',
  admin: 'مدير المدرسة',
  principal: 'مدير',
  vice_principal: 'وكيل',
  teacher: 'معلم',
  student: 'طالب',
  parent: 'ولي أمر',
  supervisor: 'مشرف',
  coordinator: 'منسق',
  counselor: 'مرشد',
  data_entry: 'إدخال بيانات',
};

function DeviceIcon({ deviceType, size = 4 }) {
  const cls = `h-${size} w-${size}`;
  if (!deviceType) return <Monitor className={cls} />;
  if (deviceType.includes('هاتف') || deviceType === 'mobile')    return <Smartphone className={cls} />;
  if (deviceType.includes('لوحي') || deviceType === 'tablet')    return <Tablet className={cls} />;
  if (deviceType === 'API')                                        return <Cpu className={cls} />;
  return <Monitor className={cls} />;
}

function ActionIcon({ action }) {
  if (!action) return <FileText className="h-4 w-4 text-muted-foreground" />;
  if (action.includes('login'))    return <LogIn className="h-4 w-4 text-blue-500" />;
  if (action.includes('logout'))   return <LogOut className="h-4 w-4 text-slate-500" />;
  if (action.includes('delete') || action.includes('deleted'))
                                   return <Trash2 className="h-4 w-4 text-red-500" />;
  if (action.includes('creat') || action.includes('add') || action.includes('register'))
                                   return <Plus className="h-4 w-4 text-green-500" />;
  if (action.includes('updat') || action.includes('edit') || action.includes('modif'))
                                   return <Edit className="h-4 w-4 text-blue-500" />;
  if (action.includes('export'))   return <Download className="h-4 w-4 text-purple-500" />;
  if (action.includes('import'))   return <Database className="h-4 w-4 text-indigo-500" />;
  if (action.includes('suspend'))  return <Lock className="h-4 w-4 text-orange-500" />;
  if (action.includes('activat'))  return <Unlock className="h-4 w-4 text-green-500" />;
  if (action.includes('setting'))  return <Settings className="h-4 w-4 text-slate-500" />;
  if (action.includes('password')) return <Lock className="h-4 w-4 text-amber-500" />;
  if (action.includes('view') || action.includes('access') || action.includes('report'))
                                   return <Eye className="h-4 w-4 text-slate-400" />;
  return <Activity className="h-4 w-4 text-muted-foreground" />;
}

const formatTs = (ts, isRTL) => {
  if (!ts) return '-';
  try {
    return new Date(ts).toLocaleString(isRTL ? 'ar-SA' : 'en-US', {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  } catch (e) { console.error('Error formatting timestamp:', e); return ts; }
};

/* ─── component ───────────────────────────────────────── */

const AuditLogsPage = () => {
  const { api } = useAuth();
  const { isRTL } = useTheme();
  const { nassaqError } = useNassaqAlert();

  const [logs,  setLogs]  = useState([]);
  const [stats, setStats] = useState(null);
  const [loading,      setLoading]      = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  const [expandedRow,  setExpandedRow]  = useState(null);

  // Filters
  const [searchTerm,       setSearchTerm]       = useState('');
  const [severityFilter,   setSeverityFilter]   = useState('all');
  const [entityTypeFilter, setEntityTypeFilter] = useState('all');
  const [daysFilter,       setDaysFilter]       = useState('30');

  // Pagination
  const [page,  setPage]  = useState(1);
  const [total, setTotal] = useState(0);
  const LIMIT = 25;

  /* ── fetch ─────────────────────────────────────────── */

  const fetchLogs = useCallback(async () => {
    try {
      setLoading(true);
      const p = new URLSearchParams({ page: String(page), limit: String(LIMIT), days: daysFilter });
      if (severityFilter   !== 'all') p.append('severity',    severityFilter);
      if (entityTypeFilter !== 'all') p.append('entity_type', entityTypeFilter);
      if (searchTerm)                 p.append('search',      searchTerm);
      const res = await api.get(`/audit/logs?${p}`);
      setLogs(res.data?.logs  || []);
      setTotal(res.data?.total || 0);
    } catch (err) {
      console.error(err);
      nassaqError('خطأ في تحميل السجلات');
    } finally {
      setLoading(false);
    }
  }, [api, page, LIMIT, daysFilter, severityFilter, entityTypeFilter, searchTerm]);

  const fetchStats = useCallback(async () => {
    try {
      setStatsLoading(true);
      const res = await api.get(`/audit/stats?days=${daysFilter}`);
      setStats(res.data);
    } catch (e) { console.error('Error fetching audit stats:', e); } finally {
      setStatsLoading(false);
    }
  }, [api, daysFilter]);

  useEffect(() => { fetchLogs(); fetchStats(); }, [fetchLogs, fetchStats]);

  // Reset to page 1 when filters change
  useEffect(() => { setPage(1); }, [searchTerm, severityFilter, entityTypeFilter, daysFilter]);

  /* ── export ─────────────────────────────────────────── */

  const handleExport = async () => {
    try {
      const p = new URLSearchParams({ days: daysFilter, format: 'json', limit: '1000' });
      if (severityFilter !== 'all') p.append('severity', severityFilter);
      const res = await api.get(`/audit/export?${p}`);
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' });
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = `audit-${new Date().toISOString().split('T')[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('تم تصدير السجلات بنجاح');
    } catch (e) { console.error('Error exporting audit logs:', e); nassaqError('خطأ في التصدير'); }
  };

  /* ── stat cards ─────────────────────────────────────── */

  const statCards = [
    { label: 'إجمالي الأحداث',   value: stats?.total_events ?? 0, icon: <Activity className="h-7 w-7 text-blue-500" />,    color: 'text-blue-600' },
    { label: 'اليوم',             value: stats?.today_events  ?? 0, icon: <Clock className="h-7 w-7 text-green-500" />,     color: 'text-green-600' },
    { label: 'أحداث حرجة',       value: stats?.critical_count ?? 0, icon: <AlertTriangle className="h-7 w-7 text-red-500" />, color: 'text-red-600' },
    { label: 'محاولات دخول فاشلة', value: stats?.failed_logins ?? 0, icon: <Shield className="h-7 w-7 text-orange-500" />, color: 'text-orange-600' },
    { label: 'مستخدمون نشطون',   value: stats?.unique_users  ?? 0, icon: <User className="h-7 w-7 text-purple-500" />,     color: 'text-purple-600' },
  ];

  /* ── render ─────────────────────────────────────────── */

  return (
    <Sidebar>
      <div className={`p-4 sm:p-6 ${isRTL ? 'font-tajawal' : ''}`}>

        {/* Header */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-xl">
              <Shield className="h-6 w-6 text-purple-600 dark:text-purple-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-foreground font-cairo">سجلات التدقيق</h1>
              <p className="text-sm text-muted-foreground">تتبع شامل لجميع أحداث النظام مع بيانات المستخدم والجهاز</p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => { fetchLogs(); fetchStats(); }}>
              <RefreshCw className="h-4 w-4 me-2" />
              تحديث
            </Button>
            <Button className="bg-brand-turquoise hover:bg-brand-turquoise/90" onClick={handleExport}>
              <Download className="h-4 w-4 me-2" />
              تصدير
            </Button>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
          {statCards.map((s, i) => (
            <Card key={i} className="border-0 shadow-sm">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">{s.label}</p>
                    <p className={`text-2xl font-bold ${s.color}`}>
                      {statsLoading ? '—' : s.value.toLocaleString('ar-SA')}
                    </p>
                  </div>
                  {s.icon}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Filters */}
        <Card className="border-0 shadow-sm mb-5">
          <CardContent className="p-4">
            <div className="flex flex-wrap gap-3 items-center">
              {/* Search */}
              <div className="flex-1 min-w-[200px] relative">
                <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="بحث بالاسم، البريد، IP، المسار..."
                  value={searchTerm}
                  onChange={e => setSearchTerm(e.target.value)}
                  className="ps-10"
                />
              </div>

              {/* Severity */}
              <Select value={severityFilter} onValueChange={setSeverityFilter}>
                <SelectTrigger className="w-[140px]">
                  <SelectValue placeholder="الخطورة" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">جميع المستويات</SelectItem>
                  <SelectItem value="critical">حرج</SelectItem>
                  <SelectItem value="high">عالي</SelectItem>
                  <SelectItem value="medium">متوسط</SelectItem>
                  <SelectItem value="low">منخفض</SelectItem>
                  <SelectItem value="info">معلومات</SelectItem>
                </SelectContent>
              </Select>

              {/* Entity type */}
              <Select value={entityTypeFilter} onValueChange={setEntityTypeFilter}>
                <SelectTrigger className="w-[150px]">
                  <SelectValue placeholder="نوع الحدث" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">جميع الأنواع</SelectItem>
                  <SelectItem value="auth">المصادقة</SelectItem>
                  <SelectItem value="user">المستخدمون</SelectItem>
                  <SelectItem value="tenant">المؤسسات</SelectItem>
                  <SelectItem value="school">المدارس</SelectItem>
                  <SelectItem value="student">الطلاب</SelectItem>
                  <SelectItem value="teacher">المعلمون</SelectItem>
                  <SelectItem value="attendance">الحضور</SelectItem>
                  <SelectItem value="grade">الدرجات</SelectItem>
                  <SelectItem value="schedule">الجداول</SelectItem>
                  <SelectItem value="settings">الإعدادات</SelectItem>
                  <SelectItem value="data">البيانات</SelectItem>
                  <SelectItem value="security">الأمان</SelectItem>
                  <SelectItem value="system">النظام</SelectItem>
                </SelectContent>
              </Select>

              {/* Days */}
              <Select value={daysFilter} onValueChange={setDaysFilter}>
                <SelectTrigger className="w-[130px]">
                  <SelectValue placeholder="الفترة" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1">اليوم</SelectItem>
                  <SelectItem value="7">7 أيام</SelectItem>
                  <SelectItem value="30">30 يوم</SelectItem>
                  <SelectItem value="90">90 يوم</SelectItem>
                  <SelectItem value="365">سنة كاملة</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* Event Log Table */}
        <Card className="border-0 shadow-sm">
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-base font-cairo">
              سجل الأحداث
              {!loading && (
                <span className="ms-2 text-sm font-normal text-muted-foreground">
                  ({total.toLocaleString('ar-SA')} حدث)
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {loading ? (
              <div className="flex flex-col items-center justify-center py-16 gap-3">
                <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
                <p className="text-sm text-muted-foreground">جارٍ تحميل السجلات...</p>
              </div>
            ) : logs.length === 0 ? (
              <div className="text-center py-16 text-muted-foreground">
                <Shield className="h-12 w-12 mx-auto mb-3 opacity-30" />
                <p className="font-medium">لا توجد سجلات لهذه الفترة</p>
                <p className="text-sm mt-1">جرّب تغيير الفلاتر أو تمديد الفترة الزمنية</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/30 text-xs text-muted-foreground uppercase tracking-wide">
                      <th className="text-start px-4 py-3 w-8"></th>
                      <th className="text-start px-4 py-3">الوقت</th>
                      <th className="text-start px-4 py-3">الحدث</th>
                      <th className="text-start px-4 py-3">الخطورة</th>
                      <th className="text-start px-4 py-3">المستخدم</th>
                      <th className="text-start px-4 py-3">الجهاز</th>
                      <th className="text-start px-4 py-3">عنوان IP</th>
                      <th className="text-start px-4 py-3">الحالة</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map((log, idx) => {
                      const sev  = SEVERITY_CFG[log.severity] || SEVERITY_CFG.low;
                      const isExpanded = expandedRow === (log.id || idx);
                      const success = log.details?.success !== false
                                   && (log.details?.status_code == null || log.details.status_code < 400);

                      return [
                        /* ── main row ── */
                        <tr
                          key={`row-${log.id || idx}`}
                          className={`border-b hover:bg-muted/30 cursor-pointer transition-colors ${isExpanded ? 'bg-muted/20' : ''}`}
                          onClick={() => setExpandedRow(isExpanded ? null : (log.id || idx))}
                        >
                          {/* expand toggle */}
                          <td className="px-4 py-3 text-muted-foreground">
                            {isExpanded
                              ? <ChevronDown className="h-4 w-4" />
                              : <ChevronRight className="h-4 w-4" />}
                          </td>

                          {/* time */}
                          <td className="px-4 py-3 whitespace-nowrap">
                            <div className="flex items-center gap-1.5 text-muted-foreground">
                              <Clock className="h-3.5 w-3.5 shrink-0" />
                              <span className="text-xs">{formatTs(log.timestamp, isRTL)}</span>
                            </div>
                          </td>

                          {/* action */}
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <ActionIcon action={log.action} />
                              <div>
                                <p className="font-medium text-foreground leading-tight">
                                  {log.action_ar || log.action}
                                </p>
                                <p className="text-xs text-muted-foreground font-mono">{log.action}</p>
                              </div>
                            </div>
                          </td>

                          {/* severity */}
                          <td className="px-4 py-3">
                            <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${sev.bg}`}>
                              <span className={`h-1.5 w-1.5 rounded-full ${sev.dot}`} />
                              {sev.label}
                            </span>
                          </td>

                          {/* user */}
                          <td className="px-4 py-3">
                            {log.actor_name || log.actor_email || log.performed_by ? (
                              <div>
                                <p className="font-medium text-foreground leading-tight">
                                  {log.actor_name || 'غير معروف'}
                                </p>
                                <p className="text-xs text-muted-foreground">
                                  {ROLE_AR[log.actor_role] || log.actor_role || ''}
                                  {log.actor_email && ` · ${log.actor_email}`}
                                </p>
                              </div>
                            ) : (
                              <span className="text-muted-foreground text-xs">نظام / مجهول</span>
                            )}
                          </td>

                          {/* device */}
                          <td className="px-4 py-3">
                            {log.device_info ? (
                              <div className="flex items-center gap-1.5">
                                <DeviceIcon deviceType={log.device_info.device_type} size={3} />
                                <div>
                                  <p className="leading-tight text-xs font-medium">{log.device_info.browser}</p>
                                  <p className="text-xs text-muted-foreground">{log.device_info.os}</p>
                                </div>
                              </div>
                            ) : (
                              <span className="text-muted-foreground text-xs">—</span>
                            )}
                          </td>

                          {/* IP */}
                          <td className="px-4 py-3">
                            {log.ip_address ? (
                              <div className="flex items-center gap-1 text-xs font-mono">
                                <Globe className="h-3 w-3 text-muted-foreground" />
                                {log.ip_address}
                              </div>
                            ) : <span className="text-muted-foreground text-xs">—</span>}
                          </td>

                          {/* status */}
                          <td className="px-4 py-3">
                            {success
                              ? <CheckCircle className="h-4 w-4 text-green-500" />
                              : <XCircle className="h-4 w-4 text-red-500" />
                            }
                          </td>
                        </tr>,

                        /* ── expanded detail row ── */
                        isExpanded && (
                          <tr key={`detail-${log.id || idx}`} className="bg-muted/10 border-b">
                            <td colSpan={8} className="px-6 py-4">
                              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">

                                {/* User details */}
                                <div className="space-y-1.5">
                                  <p className="font-semibold text-foreground mb-2 flex items-center gap-1">
                                    <User className="h-3.5 w-3.5" /> بيانات المستخدم
                                  </p>
                                  <DetailRow label="الاسم"     value={log.actor_name} />
                                  <DetailRow label="البريد"    value={log.actor_email} />
                                  <DetailRow label="الدور"     value={ROLE_AR[log.actor_role] || log.actor_role} />
                                  <DetailRow label="المعرّف"   value={log.performed_by} mono />
                                  {log.tenant_id && <DetailRow label="المدرسة" value={log.tenant_id} mono />}
                                </div>

                                {/* Device details */}
                                <div className="space-y-1.5">
                                  <p className="font-semibold text-foreground mb-2 flex items-center gap-1">
                                    <Monitor className="h-3.5 w-3.5" /> بيانات الجهاز
                                  </p>
                                  <DetailRow label="المتصفح"    value={log.device_info?.browser} />
                                  <DetailRow label="نظام التشغيل" value={log.device_info?.os} />
                                  <DetailRow label="نوع الجهاز"  value={log.device_info?.device_type} />
                                  <DetailRow label="عنوان IP"    value={log.ip_address} mono />
                                  {log.device_info?.raw && (
                                    <div>
                                      <span className="text-muted-foreground">User-Agent: </span>
                                      <span className="font-mono text-[10px] break-all opacity-60">{log.device_info.raw.substring(0, 120)}…</span>
                                    </div>
                                  )}
                                </div>

                                {/* Event details */}
                                <div className="space-y-1.5">
                                  <p className="font-semibold text-foreground mb-2 flex items-center gap-1">
                                    <FileText className="h-3.5 w-3.5" /> تفاصيل الحدث
                                  </p>
                                  <DetailRow label="الإجراء"  value={log.action} mono />
                                  {log.details?.method && <DetailRow label="الطريقة" value={log.details.method} mono />}
                                  {log.details?.path   && <DetailRow label="المسار"  value={log.details.path}   mono />}
                                  {log.details?.status_code && (
                                    <DetailRow label="الحالة" value={String(log.details.status_code)} />
                                  )}
                                  {log.details?.duration_ms && (
                                    <DetailRow label="المدة" value={`${log.details.duration_ms} مللي ثانية`} />
                                  )}
                                  {log.details?.reason && <DetailRow label="السبب" value={log.details.reason} />}
                                  {log.details?.email  && <DetailRow label="البريد" value={log.details.email} />}
                                  {log.entity_id && <DetailRow label="معرّف الكيان" value={log.entity_id} mono />}
                                </div>
                              </div>
                            </td>
                          </tr>
                        ),
                      ];
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination */}
            {!loading && total > 0 && (
              <div className="flex justify-between items-center px-4 py-3 border-t text-sm">
                <p className="text-muted-foreground">
                  عرض {Math.min((page - 1) * LIMIT + 1, total)}–{Math.min(page * LIMIT, total)} من {total.toLocaleString('ar-SA')}
                </p>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}>
                    السابق
                  </Button>
                  <span className="flex items-center px-3 text-muted-foreground text-xs">
                    صفحة {page} / {Math.ceil(total / LIMIT)}
                  </span>
                  <Button variant="outline" size="sm" disabled={page * LIMIT >= total} onClick={() => setPage(p => p + 1)}>
                    التالي
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </Sidebar>
  );
};

/* small helper */
function DetailRow({ label, value, mono = false }) {
  if (!value) return null;
  return (
    <div className="flex gap-1.5 flex-wrap">
      <span className="text-muted-foreground shrink-0">{label}:</span>
      <span className={mono ? 'font-mono break-all' : ''}>{value}</span>
    </div>
  );
}

export default AuditLogsPage;
