/**
 * AuditLogsPage - صفحة سجلات التدقيق
 * عرض وتصفية وتصدير سجلات التدقيق
 */

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { 
  Shield, 
  Search, 
  Download, 
  Filter,
  Clock,
  User,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Activity,
  FileText,
  ChevronDown,
  RefreshCw,
  Calendar
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Sidebar } from '../components/layout/Sidebar';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';

const AuditLogsPage = () => {
  const { api, user } = useAuth();
  const { isRTL } = useTheme();
  
  const [logs, setLogs] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  
  // Filters
  const [actionFilter, setActionFilter] = useState('');
  const [severityFilter, setSeverityFilter] = useState('all');
  const [entityTypeFilter, setEntityTypeFilter] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [daysFilter, setDaysFilter] = useState('30');
  
  // Pagination
  const [skip, setSkip] = useState(0);
  const [limit] = useState(20);
  const [total, setTotal] = useState(0);

  // Fetch audit logs
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const fetchLogs = useCallback(async () => {
    try {
      setLoading(true);
      const page = Math.floor(skip / limit) + 1;
      const params = new URLSearchParams({
        page: page.toString(),
        limit: limit.toString()
      });
      
      if (actionFilter) params.append('action', actionFilter);
      if (searchTerm) params.append('search', searchTerm);
      
      const response = await api.get(`/audit/logs?${params.toString()}`);
      // Handle new API response format
      if (response.data?.logs) {
        setLogs(response.data.logs);
        setTotal(response.data.total || 0);
      } else {
        setLogs(response.data || []);
        setTotal(response.data?.length || 0);
      }
    } catch (error) {
      console.error('Error fetching audit logs:', error);
      nassaqError(isRTL ? 'خطأ في تحميل السجلات' : 'Error loading logs');
    } finally {
      setLoading(false);
    }
  }, [api, skip, limit, actionFilter, searchTerm, isRTL]);

  // Fetch audit stats
  const fetchStats = useCallback(async () => {
    try {
      setStatsLoading(true);
      const response = await api.get(`/audit/stats?days=${daysFilter}`);
      setStats(response.data);
    } catch (error) {
      console.error('Error fetching audit stats:', error);
    } finally {
      setStatsLoading(false);
    }
  }, [api, daysFilter]);

  useEffect(() => {
    fetchLogs();
    fetchStats();
  }, [fetchLogs, fetchStats]);

  // Export audit report
  const handleExport = async () => {
    try {
      const response = await api.post('/audit/export', {
        days: parseInt(daysFilter)
      });
      
      // Create downloadable JSON
      const blob = new Blob([JSON.stringify(response.data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `audit-report-${new Date().toISOString().split('T')[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
      
      toast.success(isRTL ? 'تم تصدير التقرير بنجاح' : 'Report exported successfully');
    } catch (error) {
      console.error('Export error:', error);
      nassaqError(isRTL ? 'خطأ في تصدير التقرير' : 'Error exporting report');
    }
  };

  // Get severity badge color
  const getSeverityBadge = (severity) => {
    const colors = {
      low: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
      medium: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
      high: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400',
      critical: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
    };
    return colors[severity] || 'bg-gray-100 text-gray-800';
  };

  // Get action icon
  const getActionIcon = (action) => {
    if (action?.includes('login')) return <User className="h-4 w-4" />;
    if (action?.includes('create')) return <CheckCircle className="h-4 w-4 text-green-500" />;
    if (action?.includes('delete')) return <XCircle className="h-4 w-4 text-red-500" />;
    if (action?.includes('update')) return <Activity className="h-4 w-4 text-blue-500" />;
    return <FileText className="h-4 w-4" />;
  };

  // Format timestamp
  const formatTimestamp = (timestamp) => {
    if (!timestamp) return '-';
    const date = new Date(timestamp);
    return date.toLocaleString(isRTL ? 'ar-SA' : 'en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // Translate action names
  const translateAction = (action) => {
    const translations = {
      'auth.login': isRTL ? 'تسجيل دخول' : 'Login',
      'auth.logout': isRTL ? 'تسجيل خروج' : 'Logout',
      'auth.login_failed': isRTL ? 'فشل تسجيل الدخول' : 'Login Failed',
      'user.created': isRTL ? 'إنشاء مستخدم' : 'User Created',
      'user.updated': isRTL ? 'تحديث مستخدم' : 'User Updated',
      'user.deleted': isRTL ? 'حذف مستخدم' : 'User Deleted',
      'user.suspended': isRTL ? 'تعليق مستخدم' : 'User Suspended',
      'user_created': isRTL ? 'إنشاء مستخدم' : 'User Created',
      'user_updated': isRTL ? 'تحديث مستخدم' : 'User Updated',
      'user_deleted': isRTL ? 'حذف مستخدم' : 'User Deleted',
      'tenant.created': isRTL ? 'إنشاء مدرسة' : 'School Created',
      'tenant.updated': isRTL ? 'تحديث مدرسة' : 'School Updated',
      'settings.updated': isRTL ? 'تحديث الإعدادات' : 'Settings Updated',
      'data.exported': isRTL ? 'تصدير البيانات' : 'Data Exported',
      'data.imported': isRTL ? 'استيراد البيانات' : 'Data Imported',
    };
    return translations[action] || action;
  };

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
              <h1 className="text-2xl font-bold text-foreground font-cairo">
                {isRTL ? 'سجلات التدقيق' : 'Audit Logs'}
              </h1>
              <p className="text-sm text-muted-foreground">
                {isRTL ? 'تتبع جميع العمليات والأنشطة في النظام' : 'Track all system operations and activities'}
              </p>
            </div>
          </div>
          
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => { fetchLogs(); fetchStats(); }}
              data-testid="refresh-audit-btn"
            >
              <RefreshCw className="h-4 w-4 me-2" />
              {isRTL ? 'تحديث' : 'Refresh'}
            </Button>
            <Button
              className="bg-brand-turquoise hover:bg-brand-turquoise-light"
              onClick={handleExport}
              data-testid="export-audit-btn"
            >
              <Download className="h-4 w-4 me-2" />
              {isRTL ? 'تصدير التقرير' : 'Export Report'}
            </Button>
          </div>
        </div>

        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <Card className="border-0 shadow-sm">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">
                      {isRTL ? 'إجمالي الأحداث' : 'Total Events'}
                    </p>
                    <p className="text-2xl font-bold">{stats.total_events || 0}</p>
                  </div>
                  <Activity className="h-8 w-8 text-blue-500" />
                </div>
              </CardContent>
            </Card>
            
            <Card className="border-0 shadow-sm">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">
                      {isRTL ? 'أحداث حرجة' : 'Critical Events'}
                    </p>
                    <p className="text-2xl font-bold text-red-600">{stats.critical_count || 0}</p>
                  </div>
                  <AlertTriangle className="h-8 w-8 text-red-500" />
                </div>
              </CardContent>
            </Card>
            
            <Card className="border-0 shadow-sm">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">
                      {isRTL ? 'أحداث عالية الخطورة' : 'High Severity'}
                    </p>
                    <p className="text-2xl font-bold text-orange-600">{stats.high_count || 0}</p>
                  </div>
                  <Shield className="h-8 w-8 text-orange-500" />
                </div>
              </CardContent>
            </Card>
            
            <Card className="border-0 shadow-sm">
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">
                      {isRTL ? 'الفترة' : 'Period'}
                    </p>
                    <p className="text-2xl font-bold">{stats.period_days} {isRTL ? 'يوم' : 'days'}</p>
                  </div>
                  <Calendar className="h-8 w-8 text-purple-500" />
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Filters */}
        <Card className="border-0 shadow-sm mb-6">
          <CardContent className="p-4">
            <div className="flex flex-wrap gap-4 items-center">
              <div className="flex-1 min-w-[200px]">
                <div className="relative">
                  <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder={isRTL ? 'بحث في السجلات...' : 'Search logs...'}
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="ps-10"
                    data-testid="audit-search-input"
                  />
                </div>
              </div>
              
              <Select value={severityFilter} onValueChange={setSeverityFilter}>
                <SelectTrigger className="w-[150px]" data-testid="severity-filter">
                  <SelectValue placeholder={isRTL ? 'الخطورة' : 'Severity'} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{isRTL ? 'الكل' : 'All'}</SelectItem>
                  <SelectItem value="low">{isRTL ? 'منخفضة' : 'Low'}</SelectItem>
                  <SelectItem value="medium">{isRTL ? 'متوسطة' : 'Medium'}</SelectItem>
                  <SelectItem value="high">{isRTL ? 'عالية' : 'High'}</SelectItem>
                  <SelectItem value="critical">{isRTL ? 'حرجة' : 'Critical'}</SelectItem>
                </SelectContent>
              </Select>
              
              <Select value={daysFilter} onValueChange={setDaysFilter}>
                <SelectTrigger className="w-[150px]" data-testid="days-filter">
                  <SelectValue placeholder={isRTL ? 'الفترة' : 'Period'} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="7">{isRTL ? '7 أيام' : '7 days'}</SelectItem>
                  <SelectItem value="30">{isRTL ? '30 يوم' : '30 days'}</SelectItem>
                  <SelectItem value="90">{isRTL ? '90 يوم' : '90 days'}</SelectItem>
                  <SelectItem value="365">{isRTL ? 'سنة' : '1 year'}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* Logs Table */}
        <Card className="border-0 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg font-cairo">
              {isRTL ? 'سجل الأحداث' : 'Event Log'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex justify-center py-12">
                <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : logs.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <Shield className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>{isRTL ? 'لا توجد سجلات' : 'No logs found'}</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b text-sm text-muted-foreground">
                      <th className="text-start p-3">{isRTL ? 'الوقت' : 'Time'}</th>
                      <th className="text-start p-3">{isRTL ? 'العملية' : 'Action'}</th>
                      <th className="text-start p-3">{isRTL ? 'الخطورة' : 'Severity'}</th>
                      <th className="text-start p-3">{isRTL ? 'المستخدم' : 'User'}</th>
                      <th className="text-start p-3">{isRTL ? 'التفاصيل' : 'Details'}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map((log, index) => (
                      <tr key={log.id || index} className="border-b hover:bg-muted/50 transition-colors">
                        <td className="p-3">
                          <div className="flex items-center gap-2 text-sm">
                            <Clock className="h-4 w-4 text-muted-foreground" />
                            {formatTimestamp(log.timestamp)}
                          </div>
                        </td>
                        <td className="p-3">
                          <div className="flex items-center gap-2">
                            {getActionIcon(log.action)}
                            <span className="font-medium">{translateAction(log.action)}</span>
                          </div>
                        </td>
                        <td className="p-3">
                          <Badge className={getSeverityBadge(log.severity)}>
                            {log.severity || 'unknown'}
                          </Badge>
                        </td>
                        <td className="p-3 text-sm">
                          {log.performed_by?.substring(0, 8)}...
                        </td>
                        <td className="p-3 text-sm text-muted-foreground max-w-[200px] truncate">
                          {log.details?.email || log.details?.reason || '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            
            {/* Pagination */}
            {logs.length > 0 && (
              <div className="flex justify-between items-center mt-4 pt-4 border-t">
                <p className="text-sm text-muted-foreground">
                  {isRTL ? `عرض ${logs.length} سجل` : `Showing ${logs.length} logs`}
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={skip === 0}
                    onClick={() => setSkip(Math.max(0, skip - limit))}
                  >
                    {isRTL ? 'السابق' : 'Previous'}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={logs.length < limit}
                    onClick={() => setSkip(skip + limit)}
                  >
                    {isRTL ? 'التالي' : 'Next'}
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

export default AuditLogsPage;
