import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { toast } from 'sonner';
import { Progress } from '../ui/progress';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '../ui/dialog';
import {
  Brain, Activity, Database, Upload, Bell, Play, RefreshCw, Eye,
  CheckCircle2, XCircle, Clock, Zap, Sparkles, ChevronRight, History,
  Gauge, Check, X, ExternalLink, FileCheck, AlertTriangle
} from 'lucide-react';

// AI Status States
const AI_STATUS = {
  ACTIVE: { label: 'نشط', label_en: 'Active', color: 'bg-green-500', textColor: 'text-green-500' },
  PARTIAL: { label: 'نشط جزئياً', label_en: 'Partially Active', color: 'bg-yellow-500', textColor: 'text-yellow-500' },
  STOPPED: { label: 'متوقف', label_en: 'Stopped', color: 'bg-red-500', textColor: 'text-red-500' },
};

// AI Operations Configuration - Only 4 operations as requested
const AI_OPERATIONS = [
  {
    id: 'system_diagnosis',
    title: 'تشخيص النظام',
    title_en: 'System Diagnosis',
    desc: 'فحص شامل للنظام',
    desc_en: 'Full system scan',
    icon: Gauge,
    color: 'bg-blue-500',
    type: 'analysis',
  },
  {
    id: 'data_quality',
    title: 'فحص جودة البيانات',
    title_en: 'Data Quality Scan',
    desc: 'اكتشاف النقص والتكرار',
    desc_en: 'Find gaps & duplicates',
    icon: Database,
    color: 'bg-green-500',
    type: 'analysis',
  },
  {
    id: 'import_analyzer',
    title: 'تحليل ملفات الاستيراد',
    title_en: 'Import Analyzer',
    desc: 'نتائج الملفات المستوردة',
    desc_en: 'Import files results',
    icon: Upload,
    color: 'bg-purple-500',
    type: 'analysis',
  },
  {
    id: 'alerts_review',
    title: 'مراجعة التنبيهات',
    title_en: 'Alerts Review',
    desc: 'التنبيهات غير المقروءة',
    desc_en: 'Unread alerts',
    icon: Bell,
    color: 'bg-red-500',
    type: 'alert',
    badge: 7, // Unread count
  },
];

// Sample suggested actions with navigation links
const SUGGESTED_ACTIONS = [
  { 
    id: 1, 
    title: 'توجد 3 مدارس لم يتم استكمال بيانات مديرها', 
    priority: 'high', 
    type: 'data',
    link: '/admin/schools',
    linkText: 'إدارة المدارس'
  },
  { 
    id: 2, 
    title: '12 معلماً بدون رتبة محددة', 
    priority: 'medium', 
    type: 'data',
    link: '/admin/teachers',
    linkText: 'إدارة المعلمين'
  },
  { 
    id: 3, 
    title: '4 ملفات استيراد تحتاج مراجعة', 
    priority: 'high', 
    type: 'import',
    link: '/admin/users',
    linkText: 'ملفات الاستيراد'
  },
  { 
    id: 4, 
    title: 'يُفضل تفعيل AI Scheduling لمدرستين', 
    priority: 'low', 
    type: 'suggestion',
    link: '/admin/schools',
    linkText: 'إدارة المدارس'
  },
];

// Sample recent operations
const RECENT_OPERATIONS = [
  { id: 1, name: 'تشخيص النظام', type: 'diagnosis', time: '10:30', status: 'success', user: 'مدير النظام' },
  { id: 2, name: 'فحص جودة البيانات', type: 'quality', time: '09:15', status: 'success', user: 'مدير النظام' },
  { id: 3, name: 'تحليل ملف استيراد', type: 'import', time: '08:45', status: 'partial', user: 'مدير النظام' },
];

export default function QuickAIOperationsPanel({ api, isRTL = true }) {
  const navigate = useNavigate();
  
  // States
  const [aiStatus] = useState(AI_STATUS.ACTIVE);
  const [operationsToday, setOperationsToday] = useState(47);
  const [openAlerts] = useState(7);
  const [pendingRecommendations] = useState(8);
  const [lastUpdate, setLastUpdate] = useState(new Date().toLocaleTimeString('ar-SA'));
  const [aiEnabledSchools] = useState(184);
  const [totalSchools] = useState(200);
  
  // Dialog states
  const [activeDialog, setActiveDialog] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [operationResult, setOperationResult] = useState(null);
  
  // Run AI Operation
  const runOperation = async (operationId) => {
    setActiveDialog(operationId);
    setIsProcessing(true);
    setOperationResult(null);
    
    // Simulate AI operation
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // Generate results based on operation type
    const results = generateOperationResults(operationId);
    setOperationResult(results);
    setIsProcessing(false);
    setOperationsToday(prev => prev + 1);
  };
  
  // Generate operation results - Empty states when no data
  const generateOperationResults = (operationId) => {
    switch (operationId) {
      case 'system_diagnosis':
        return {
          title: isRTL ? 'نتائج تشخيص النظام' : 'System Diagnosis Results',
          summary: isRTL ? 'يتم تحليل البيانات...' : 'Analyzing data...',
          items: [], // Empty - will be populated from API
          recommendations: []
        };
      case 'data_quality':
        return {
          title: isRTL ? 'نتائج فحص جودة البيانات' : 'Data Quality Results',
          summary: isRTL ? 'جاري الفحص...' : 'Checking...',
          qualityScore: 0,
          items: [], // Empty - will be populated from API
        };
      case 'import_analyzer':
        return {
          title: isRTL ? 'نتائج ملفات الاستيراد اليوم' : 'Today\'s Import Files Results',
          summary: isRTL ? 'لا توجد عمليات استيراد اليوم' : 'No imports today',
          importStats: {
            total: 0,
            success: 0,
            failed: 0,
            pending: 0
          },
          items: [], // Empty - will be populated from API
        };
      case 'alerts_review':
        return {
          title: isRTL ? 'التنبيهات غير المقروءة' : 'Unread Alerts',
          summary: isRTL ? `لديك ${openAlerts} تنبيهات غير مقروءة` : `You have ${openAlerts} unread alerts`,
          unreadCount: openAlerts,
          alertsLink: '/admin/audit',
          items: [], // Empty - will be populated from API
        };
      default:
        return {
          title: isRTL ? 'نتائج العملية' : 'Operation Results',
          summary: isRTL ? 'تمت العملية بنجاح' : 'Operation completed successfully',
          items: [],
        };
    }
  };
  
  // Refresh AI Status
  const refreshStatus = () => {
    setLastUpdate(new Date().toLocaleTimeString('ar-SA'));
    toast.success(isRTL ? 'تم تحديث حالة الذكاء الاصطناعي' : 'AI status updated');
  };
  
  // Navigate to action link
  const handleActionClick = (action) => {
    toast.info(isRTL ? `جاري الانتقال إلى ${action.linkText}...` : `Navigating to ${action.linkText}...`);
    navigate(action.link);
  };
  
  // Get operation by ID
  const getOperation = (id) => AI_OPERATIONS.find(op => op.id === id);
  
  return (
    <section data-testid="ai-operations-panel" className="space-y-6">
      {/* العنوان والوصف */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-cairo text-xl font-bold flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-purple to-brand-turquoise flex items-center justify-center">
              <Brain className="h-6 w-6 text-white" />
            </div>
            {isRTL ? 'لوحة العمليات الذكية السريعة' : 'Quick AI Operations Panel'}
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            {isRTL 
              ? 'تنفيذ وتحليل ومراقبة العمليات الذكية على مستوى المنصة بالكامل'
              : 'Execute, analyze and monitor AI operations across the entire platform'
            }
          </p>
        </div>
      </div>
      
      {/* شريط الحالة الذكي - AI Status Bar */}
      <Card className="card-nassaq bg-gradient-to-r from-brand-navy/5 to-brand-purple/5 border-brand-navy/20">
        <CardContent className="p-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            {/* حالة المحرك */}
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <div className={`w-3 h-3 rounded-full ${aiStatus.color} animate-pulse`} />
                <span className="font-bold">{isRTL ? aiStatus.label : aiStatus.label_en}</span>
              </div>
              <div className="h-6 w-px bg-border" />
              <div className="flex items-center gap-1 text-sm">
                <Activity className="h-4 w-4 text-brand-turquoise" />
                <span>{operationsToday}</span>
                <span className="text-muted-foreground">{isRTL ? 'عملية اليوم' : 'ops today'}</span>
              </div>
              <div className="h-6 w-px bg-border" />
              <div className="flex items-center gap-1 text-sm">
                <Bell className="h-4 w-4 text-orange-500" />
                <span>{openAlerts}</span>
                <span className="text-muted-foreground">{isRTL ? 'تنبيه غير مقروء' : 'unread alerts'}</span>
              </div>
              <div className="h-6 w-px bg-border" />
              <div className="flex items-center gap-1 text-sm">
                <Sparkles className="h-4 w-4 text-brand-purple" />
                <span>{pendingRecommendations}</span>
                <span className="text-muted-foreground">{isRTL ? 'توصية' : 'recommendations'}</span>
              </div>
            </div>
            
            {/* أزرار التحكم */}
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={refreshStatus} className="rounded-lg">
                <RefreshCw className="h-4 w-4 me-1" />
                {isRTL ? 'تحديث' : 'Refresh'}
              </Button>
              <Button variant="outline" size="sm" onClick={() => runOperation('system_diagnosis')} className="rounded-lg">
                <Gauge className="h-4 w-4 me-1" />
                {isRTL ? 'تشخيص' : 'Diagnose'}
              </Button>
            </div>
          </div>
          
          {/* معلومات إضافية */}
          <div className="flex items-center gap-4 mt-3 pt-3 border-t text-xs text-muted-foreground">
            <span>{isRTL ? 'آخر تحديث:' : 'Last update:'} {lastUpdate}</span>
            <span>•</span>
            <span>{isRTL ? 'المدارس المفعّل لها AI:' : 'AI-enabled schools:'} {aiEnabledSchools}/{totalSchools}</span>
            <span>•</span>
            <span className="text-green-500 flex items-center gap-1">
              <CheckCircle2 className="h-3 w-3" />
              {isRTL ? 'جميع المحركات تعمل' : 'All engines running'}
            </span>
          </div>
        </CardContent>
      </Card>
      
      {/* بطاقات العمليات الذكية - 4 عمليات فقط - الكارت كله قابل للنقر */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {AI_OPERATIONS.map((op) => (
          <Card 
            key={op.id}
            className="card-nassaq hover:shadow-lg hover:border-brand-purple/30 transition-all cursor-pointer group relative overflow-hidden"
            onClick={() => runOperation(op.id)}
            data-testid={`ai-op-${op.id}`}
          >
            {/* Live indicator */}
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
                {/* Badge for unread alerts */}
                {op.badge && (
                  <Badge className="absolute -top-2 -end-2 bg-red-500 text-white text-xs px-2 animate-pulse">
                    {op.badge}
                  </Badge>
                )}
              </div>
              <div>
                <p className="font-cairo font-bold text-sm">{isRTL ? op.title : op.title_en}</p>
                <p className="text-xs text-muted-foreground">{isRTL ? op.desc : op.desc_en}</p>
              </div>
              {/* Click hint instead of button */}
              <div className="flex items-center gap-1 text-xs text-muted-foreground group-hover:text-brand-purple transition-colors">
                <Play className="h-3 w-3" />
                <span>{isRTL ? 'اضغط للتشغيل' : 'Click to run'}</span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
      
      {/* صف سفلي: المهام المقترحة + سجل العمليات */}
      <div className="grid md:grid-cols-2 gap-4">
        {/* المهام الذكية المقترحة */}
        <Card className="card-nassaq">
          <CardHeader className="pb-2">
            <CardTitle className="font-cairo text-base flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-yellow-500" />
              {isRTL ? 'المهام الذكية المقترحة' : 'AI Suggested Actions'}
              <Badge className="bg-yellow-500 text-white">{SUGGESTED_ACTIONS.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {SUGGESTED_ACTIONS.map((action) => (
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
                  <span className="flex-1 text-sm">{action.title}</span>
                  <Button 
                    size="sm" 
                    variant="outline" 
                    className="h-7 px-3 text-xs gap-1"
                    onClick={() => handleActionClick(action)}
                  >
                    <ExternalLink className="h-3 w-3" />
                    {action.linkText}
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
        
        {/* سجل العمليات الأخيرة */}
        <Card className="card-nassaq">
          <CardHeader className="pb-2">
            <CardTitle className="font-cairo text-base flex items-center gap-2">
              <History className="h-5 w-5 text-brand-turquoise" />
              {isRTL ? 'سجل العمليات الأخيرة' : 'Recent Operations'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {RECENT_OPERATIONS.map((op) => (
                <div 
                  key={op.id}
                  className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-all"
                >
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                    op.status === 'success' ? 'bg-green-100 text-green-600' :
                    op.status === 'partial' ? 'bg-yellow-100 text-yellow-600' :
                    'bg-red-100 text-red-600'
                  }`}>
                    {op.status === 'success' ? <CheckCircle2 className="h-4 w-4" /> :
                     op.status === 'partial' ? <AlertTriangle className="h-4 w-4" /> :
                     <XCircle className="h-4 w-4" />}
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-medium">{op.name}</p>
                    <p className="text-xs text-muted-foreground">{op.user} • {op.time}</p>
                  </div>
                  <div className="flex gap-1">
                    <Button 
                      size="sm" 
                      variant="ghost" 
                      className="h-7 px-2 cursor-pointer hover:bg-brand-turquoise/10"
                      onClick={() => toast.success(isRTL ? `عرض تفاصيل عملية: ${op.name}` : `Viewing operation: ${op.name}`)}
                    >
                      <Eye className="h-3 w-3" />
                    </Button>
                    <Button 
                      size="sm" 
                      variant="ghost" 
                      className="h-7 px-2 cursor-pointer hover:bg-brand-turquoise/10"
                      onClick={() => toast.success(isRTL ? 'تم تحديث السجل' : 'Log refreshed')}
                    >
                      <RefreshCw className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
      
      {/* Dialog للنتائج */}
      <Dialog open={!!activeDialog} onOpenChange={() => { setActiveDialog(null); setOperationResult(null); }}>
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
            </DialogTitle>
            <DialogDescription>
              {isProcessing 
                ? (isRTL ? 'جاري التحليل...' : 'Analyzing...')
                : (isRTL ? 'نتائج العملية' : 'Operation Results')
              }
            </DialogDescription>
          </DialogHeader>
          
          {isProcessing ? (
            <div className="py-12 flex flex-col items-center gap-4">
              <div className="w-16 h-16 rounded-full bg-brand-purple/10 flex items-center justify-center">
                <Brain className="h-8 w-8 text-brand-purple animate-pulse" />
              </div>
              <p className="text-sm text-muted-foreground">{isRTL ? 'يتم تحليل البيانات...' : 'Analyzing data...'}</p>
              <Progress value={66} className="w-48" />
            </div>
          ) : operationResult && (
            <div className="space-y-4">
              {/* الملخص */}
              <div className="p-4 rounded-lg bg-muted/50">
                <h4 className="font-bold mb-2">{operationResult.title}</h4>
                <p className="text-sm text-muted-foreground">{operationResult.summary}</p>
              </div>
              
              {/* شريط الجودة (إن وجد) */}
              {operationResult.qualityScore && (
                <div className="p-4 rounded-lg border">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium">{isRTL ? 'نسبة جودة البيانات' : 'Data Quality Score'}</span>
                    <span className={`font-bold ${operationResult.qualityScore >= 80 ? 'text-green-500' : operationResult.qualityScore >= 60 ? 'text-yellow-500' : 'text-red-500'}`}>
                      {operationResult.qualityScore}%
                    </span>
                  </div>
                  <Progress value={operationResult.qualityScore} className="h-2" />
                </div>
              )}
              
              {/* إحصائيات الاستيراد (إن وجدت) */}
              {operationResult.importStats && (
                <div className="grid grid-cols-4 gap-3">
                  <div className="p-3 rounded-lg bg-muted/50 text-center">
                    <p className="text-2xl font-bold">{operationResult.importStats.total}</p>
                    <p className="text-xs text-muted-foreground">{isRTL ? 'إجمالي الملفات' : 'Total Files'}</p>
                  </div>
                  <div className="p-3 rounded-lg bg-green-50 text-center border border-green-200">
                    <p className="text-2xl font-bold text-green-600">{operationResult.importStats.success}</p>
                    <p className="text-xs text-green-600">{isRTL ? 'ناجح' : 'Success'}</p>
                  </div>
                  <div className="p-3 rounded-lg bg-red-50 text-center border border-red-200">
                    <p className="text-2xl font-bold text-red-600">{operationResult.importStats.failed}</p>
                    <p className="text-xs text-red-600">{isRTL ? 'فشل' : 'Failed'}</p>
                  </div>
                  <div className="p-3 rounded-lg bg-yellow-50 text-center border border-yellow-200">
                    <p className="text-2xl font-bold text-yellow-600">{operationResult.importStats.pending}</p>
                    <p className="text-xs text-yellow-600">{isRTL ? 'معلق' : 'Pending'}</p>
                  </div>
                </div>
              )}
              
              {/* رابط التنبيهات (إن وجد) */}
              {operationResult.alertsLink && (
                <div className="p-4 rounded-lg bg-red-50 border border-red-200">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Bell className="h-6 w-6 text-red-500" />
                      <div>
                        <p className="font-bold text-red-700">{operationResult.unreadCount} {isRTL ? 'تنبيهات غير مقروءة' : 'Unread Alerts'}</p>
                        <p className="text-sm text-red-600">{isRTL ? 'اضغط للانتقال لصفحة التنبيهات' : 'Click to view alerts page'}</p>
                      </div>
                    </div>
                    <Button 
                      className="bg-red-500 hover:bg-red-600"
                      onClick={() => {
                        setActiveDialog(null);
                        navigate(operationResult.alertsLink);
                      }}
                    >
                      <ExternalLink className="h-4 w-4 me-1" />
                      {isRTL ? 'عرض التنبيهات' : 'View Alerts'}
                    </Button>
                  </div>
                </div>
              )}
              
              {/* النتائج */}
              {operationResult.items && operationResult.items.length > 0 && !operationResult.importStats && !operationResult.alertsLink && (
                <div className="space-y-2">
                  {operationResult.items.map((item, index) => (
                    <div 
                      key={index}
                      className={`flex items-center justify-between p-3 rounded-lg ${
                        item.type === 'critical' ? 'bg-red-50 border border-red-200' :
                        item.type === 'warning' ? 'bg-yellow-50 border border-yellow-200' :
                        item.type === 'success' ? 'bg-green-50 border border-green-200' :
                        'bg-blue-50 border border-blue-200'
                      }`}
                    >
                      <span className="text-sm">{item.label}</span>
                      <Badge className={
                        item.type === 'critical' ? 'bg-red-500' :
                        item.type === 'warning' ? 'bg-yellow-500' :
                        item.type === 'success' ? 'bg-green-500' :
                        'bg-blue-500'
                      }>
                        {item.value}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
              
              {/* ملفات الاستيراد */}
              {operationResult.importStats && operationResult.items && (
                <div className="space-y-2">
                  {operationResult.items.map((item, index) => (
                    <div 
                      key={index}
                      className={`flex items-center justify-between p-3 rounded-lg ${
                        item.type === 'critical' ? 'bg-red-50 border border-red-200' :
                        item.type === 'warning' ? 'bg-yellow-50 border border-yellow-200' :
                        'bg-green-50 border border-green-200'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <FileCheck className={`h-4 w-4 ${
                          item.type === 'critical' ? 'text-red-500' :
                          item.type === 'warning' ? 'text-yellow-500' :
                          'text-green-500'
                        }`} />
                        <span className="text-sm">{item.label}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        {item.records && <span className="text-xs text-muted-foreground">{item.records} {isRTL ? 'سجل' : 'records'}</span>}
                        {item.error && <span className="text-xs text-red-500">{item.error}</span>}
                        <Badge className={
                          item.type === 'critical' ? 'bg-red-500' :
                          item.type === 'warning' ? 'bg-yellow-500' :
                          'bg-green-500'
                        }>
                          {item.value}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              
              {/* عرض بعض التنبيهات */}
              {operationResult.alertsLink && operationResult.items && (
                <div className="space-y-2">
                  <p className="text-sm font-medium text-muted-foreground">{isRTL ? 'آخر التنبيهات:' : 'Recent alerts:'}</p>
                  {operationResult.items.map((item, index) => (
                    <div 
                      key={index}
                      className={`flex items-center justify-between p-3 rounded-lg ${
                        item.type === 'critical' ? 'bg-red-50 border border-red-200' :
                        item.type === 'warning' ? 'bg-yellow-50 border border-yellow-200' :
                        'bg-blue-50 border border-blue-200'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <Bell className={`h-4 w-4 ${
                          item.type === 'critical' ? 'text-red-500' :
                          item.type === 'warning' ? 'text-yellow-500' :
                          'text-blue-500'
                        }`} />
                        <span className="text-sm">{item.label}</span>
                      </div>
                      <span className="text-xs text-muted-foreground">{item.time}</span>
                    </div>
                  ))}
                </div>
              )}
              
              {/* التوصيات */}
              {operationResult.recommendations && (
                <div className="p-4 rounded-lg border border-brand-purple/20 bg-brand-purple/5">
                  <h4 className="font-bold mb-2 flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-brand-purple" />
                    {isRTL ? 'التوصيات' : 'Recommendations'}
                  </h4>
                  <ul className="space-y-1">
                    {operationResult.recommendations.map((rec, index) => (
                      <li key={index} className="text-sm text-muted-foreground flex items-center gap-2">
                        <Check className="h-3 w-3 text-brand-purple" />
                        {rec}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
          
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => { setActiveDialog(null); setOperationResult(null); }}>
              {isRTL ? 'إغلاق' : 'Close'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
