import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/layout/Sidebar';
import { PageHeader } from '../components/layout/PageHeader';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Switch } from '../components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Progress } from '../components/ui/progress';
import { ScrollArea } from '../components/ui/scroll-area';
import { Separator } from '../components/ui/separator';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import { getApiErrorMessage } from '../utils/apiError';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
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
  SheetDescription,
} from '../components/ui/sheet';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import {
  Link2,
  Plus,
  Settings,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  RefreshCw,
  Trash2,
  Edit,
  Eye,
  Power,
  PowerOff,
  FileText,
  Key,
  Globe,
  Server,
  Database,
  Mail,
  MessageSquare,
  CreditCard,
  Cloud,
  Brain,
  Shield,
  Building2,
  Webhook,
  Activity,
  Search,
  Filter,
  ChevronRight,
  ExternalLink,
  Copy,
  Check,
  Zap,
  PlugZap,
  History,
  Loader2,
  Smartphone,
  Share2,
  Lock,
  Terminal,
  Hash,
  LayoutGrid,
  List,
  X,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// Translations
// Integration categories
const INTEGRATION_CATEGORIES = [
  { id: 'all', icon: Link2, color: 'from-gray-500 to-gray-600', label_ar: 'الكل', label_en: 'All' },
  { id: 'government', icon: Building2, color: 'from-blue-500 to-blue-600', label_ar: 'حكومية', label_en: 'Government' },
  { id: 'payment', icon: CreditCard, color: 'from-green-500 to-green-600', label_ar: 'مدفوعات', label_en: 'Payment' },
  { id: 'messaging', icon: Smartphone, color: 'from-emerald-500 to-emerald-600', label_ar: 'المراسلة', label_en: 'Messaging' },
  { id: 'sms', icon: MessageSquare, color: 'from-purple-500 to-purple-600', label_ar: 'رسائل SMS', label_en: 'SMS' },
  { id: 'email', icon: Mail, color: 'from-orange-500 to-orange-600', label_ar: 'بريد إلكتروني', label_en: 'Email' },
  { id: 'storage', icon: Cloud, color: 'from-cyan-500 to-cyan-600', label_ar: 'تخزين', label_en: 'Storage' },
  { id: 'ai', icon: Brain, color: 'from-pink-500 to-pink-600', label_ar: 'ذكاء اصطناعي', label_en: 'AI' },
  { id: 'other', icon: PlugZap, color: 'from-slate-500 to-slate-600', label_ar: 'أخرى', label_en: 'Other' },
];


// NASSAQ API Keys - Empty initial state, will be populated from API
const INITIAL_API_KEYS = [];

// NASSAQ API Endpoints
const NASSAQ_ENDPOINTS = [
  { path: '/api/students', method: 'GET', description_ar: 'قائمة الطلاب', description_en: 'List Students' },
  { path: '/api/students/{id}', method: 'GET', description_ar: 'تفاصيل طالب', description_en: 'Student Details' },
  { path: '/api/teachers', method: 'GET', description_ar: 'قائمة المعلمين', description_en: 'List Teachers' },
  { path: '/api/schools', method: 'GET', description_ar: 'قائمة المدارس', description_en: 'List Schools' },
  { path: '/api/attendance', method: 'POST', description_ar: 'تسجيل الحضور', description_en: 'Record Attendance' },
  { path: '/api/grades', method: 'POST', description_ar: 'إدخال الدرجات', description_en: 'Submit Grades' },
  { path: '/api/reports', method: 'GET', description_ar: 'التقارير', description_en: 'Reports' },
  { path: '/api/webhooks', method: 'POST', description_ar: 'Webhooks', description_en: 'Webhooks' },
];

// Empty initial state - logs will be fetched from API
const INITIAL_LOGS = [];

export default function IntegrationsPage() {
  const { isRTL = true, isDark } = useTheme();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { token, api } = useAuth();
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  
  // States - start with empty arrays, will be populated from API
  const [integrations, setIntegrations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [apiKeys, setApiKeys] = useState(INITIAL_API_KEYS);
  const [activeMainTab, setActiveMainTab] = useState('integrations');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedStatus, setSelectedStatus] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState('card'); // card or table
  const [selectedIntegration, setSelectedIntegration] = useState(null);
  const [showDetailsSheet, setShowDetailsSheet] = useState(false);
  const [showLogsSheet, setShowLogsSheet] = useState(false);
  const [showShareDialog, setShowShareDialog] = useState(false);
  const [showNewKeyDialog, setShowNewKeyDialog] = useState(false);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [testingConnection, setTestingConnection] = useState(null);
  const [syncing, setSyncing] = useState(null);
  const [copiedField, setCopiedField] = useState(null);
  
  // New key form
  const [newKeyForm, setNewKeyForm] = useState({
    name: '',
    permissions: 'read_only',
  });
  
  // Add integration form
  const [formData, setFormData] = useState({
    name: '',
    name_en: '',
    type: 'other',
    description: '',
    api_base_url: '',
    api_key: '',
    secret_key: '',
  });
  
  // Format date
  const formatDateTime = (dateStr) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString(isRTL ? 'ar-SA' : 'en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };
  
    
  // Fetch integrations from API
  useEffect(() => {
    const fetchIntegrations = async () => {
      setLoading(true);
      try {
        const response = await api.get('/integrations');
        // API returns {integrations: [...]} not direct array
        const data = response.data?.integrations || response.data || [];
        setIntegrations(Array.isArray(data) ? data : []);
      } catch (error) {
        console.error('Failed to fetch integrations:', error);
        setIntegrations([]);
      } finally {
        setLoading(false);
      }
    };
    
    const fetchApiKeys = async () => {
      try {
        const response = await api.get('/settings/api-keys');
        // Handle both array and object response formats
        const data = response.data?.keys || response.data || [];
        setApiKeys(Array.isArray(data) ? data : []);
      } catch (error) {
        console.error('Failed to fetch API keys:', error);
        setApiKeys([]);
      }
    };
    
    if (token) {
      fetchIntegrations();
      fetchApiKeys();
    }
  }, [token, api]);
  
  // Get status info
  const getStatusInfo = (status) => {
    switch (status) {
      case 'active':
        return { label: t('active'), color: 'bg-green-500', textColor: 'text-green-600', bgLight: 'bg-green-100', icon: CheckCircle2 };
      case 'inactive':
        return { label: t('inactive'), color: 'bg-gray-500', textColor: 'text-gray-600', bgLight: 'bg-gray-100', icon: PowerOff };
      case 'pending':
        return { label: t('pending'), color: 'bg-yellow-500', textColor: 'text-yellow-600', bgLight: 'bg-yellow-100', icon: Clock };
      case 'error':
        return { label: t('error'), color: 'bg-red-500', textColor: 'text-red-600', bgLight: 'bg-red-100', icon: XCircle };
      default:
        return { label: status, color: 'bg-gray-500', textColor: 'text-gray-600', bgLight: 'bg-gray-100', icon: AlertTriangle };
    }
  };
  
  // Get category info
  const getCategoryInfo = (type) => {
    return INTEGRATION_CATEGORIES.find(c => c.id === type) || INTEGRATION_CATEGORIES[INTEGRATION_CATEGORIES.length - 1];
  };
  
  // Filter integrations
  const filteredIntegrations = integrations.filter(integration => {
    const matchesCategory = selectedCategory === 'all' || integration.type === selectedCategory;
    const matchesStatus = selectedStatus === 'all' || integration.status === selectedStatus;
    const matchesSearch = !searchQuery || 
      integration.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      integration.name_en.toLowerCase().includes(searchQuery.toLowerCase()) ||
      integration.description.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesStatus && matchesSearch;
  });
  
  // Stats
  const stats = {
    total: integrations.length,
    active: integrations.filter(i => i.status === 'active').length,
    pending: integrations.filter(i => i.status === 'pending').length,
    error: integrations.filter(i => i.status === 'error').length,
  };
  
  // Active filters count
  const activeFiltersCount = (selectedCategory !== 'all' ? 1 : 0) + (selectedStatus !== 'all' ? 1 : 0);
  
  // Copy to clipboard
  const copyToClipboard = async (text, field) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedField(field);
      setTimeout(() => setCopiedField(null), 2000);
      toast.success(t('copied'));
    } catch (err) {
      nassaqError(t('copyFailed'));
    }
  };
  
  // Generate share template
  const generateShareTemplate = () => {
    const baseUrl = `${API_URL}/api`;
    return `تم إنشاء بيانات التكامل الخاصة بمنصة نَسَّق | NASSAQ.
يمكنكم استخدام البيانات التالية للاتصال بالنظام:

Base API URL:
${baseUrl}

API Key:
nsk_live_xxxxxxxxxxxxxxxxxxxxxxxx

Secret Key:
nss_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx

Documentation:
${API_URL}/docs

Webhook Endpoint:
${baseUrl}/webhooks

مع تحيات
إدارة منصة نَسَّق`;
  };
  
  // Test connection
  const handleTestConnection = async (integration) => {
    setTestingConnection(integration.id);
    try {
      await api.post(`/integrations/${integration.id}/test`);
      toast.success(t('connectionSuccessful'));
    } catch (error) {
      const detail = getApiErrorMessage(error) || t('connectionFailed');
      nassaqError(detail);
    } finally {
      setTestingConnection(null);
    }
  };
  
  // Sync
  const handleSync = async (integration) => {
    setSyncing(integration.id);
    try {
      await api.post(`/integrations/${integration.id}/sync`);
      toast.success(t('syncCompleted'));
      setIntegrations(prev => prev.map(i => 
        i.id === integration.id 
          ? { ...i, last_sync: new Date().toISOString() }
          : i
      ));
    } catch (error) {
      const detail = getApiErrorMessage(error) || t('syncFailed');
      nassaqError(detail);
    } finally {
      setSyncing(null);
    }
  };
  
  // Toggle integration
  const handleToggle = async (integration) => {
    try {
      const res = await api.post(`/integrations/${integration.id}/toggle`);
      const newActive = res.data?.is_active;
      setIntegrations(prev => prev.map(i =>
        i.id === integration.id
          ? { ...i, is_active: newActive, status: newActive ? 'active' : 'inactive' }
          : i
      ));
      toast.success(newActive ? t('integrationEnabled') : t('integrationDisabled'));
    } catch (error) {
      nassaqError(getApiErrorMessage(error) || t('actionFailed'));
    }
  };
  
  // Generate new API key
  const handleGenerateKey = async () => {
    if (!newKeyForm.name?.trim()) {
      nassaqError(t('nameRequired') || 'الاسم مطلوب');
      return;
    }
    try {
      const res = await api.post('/settings/api-keys', {
        name: newKeyForm.name,
        permissions: newKeyForm.permissions,
      });
      const created = res.data || {};
      setApiKeys(prev => [created, ...prev]);
      setShowNewKeyDialog(false);
      setNewKeyForm({ name: '', permissions: 'read_only' });
      toast.success(t('keyGeneratedSuccessfully'));
    } catch (error) {
      nassaqError(getApiErrorMessage(error) || t('actionFailed'));
    }
  };
  
  // Revoke API key
  const handleRevokeKey = async (keyId) => {
    try {
      await api.post(`/settings/api-keys/${keyId}/revoke`);
      setApiKeys(prev => prev.map(k =>
        k.id === keyId ? { ...k, is_active: false } : k
      ));
      toast.success(t('keyRevoked'));
    } catch (error) {
      nassaqError(getApiErrorMessage(error) || t('actionFailed'));
    }
  };

  // Add new integration
  const handleAddIntegration = async () => {
    if (!formData.name?.trim()) {
      nassaqError(t('nameRequired') || 'الاسم مطلوب');
      return;
    }
    try {
      const res = await api.post('/integrations', {
        name: formData.name,
        name_en: formData.name_en || formData.name,
        type: formData.type,
        description: formData.description,
        api_base_url: formData.api_base_url,
        api_key: formData.api_key,
        config: formData.secret_key ? { secret_key: formData.secret_key } : {},
      });
      const created = res.data || {};
      setIntegrations(prev => [created, ...prev]);
      setShowAddDialog(false);
      setFormData({ name: '', name_en: '', type: 'other', description: '', api_base_url: '', api_key: '', secret_key: '' });
      toast.success(t('integrationCreated') || t('saved') || 'تم الحفظ');
    } catch (error) {
      nassaqError(getApiErrorMessage(error) || t('actionFailed'));
    }
  };
  
  // Open details
  const openDetails = (integration) => {
    setSelectedIntegration(integration);
    setShowDetailsSheet(true);
  };
  
  // Open logs
  const openLogs = (integration) => {
    setSelectedIntegration(integration);
    setShowLogsSheet(true);
  };
  
  // Clear filters
  const clearFilters = () => {
    setSelectedCategory('all');
    setSelectedStatus('all');
    setSearchQuery('');
  };
  
  return (
    <Sidebar>
      <div className="min-h-screen bg-background" dir={isRTL ? 'rtl' : 'ltr'} data-testid="integrations-page">
        {/* Header */}
        <header className="sticky top-0 z-40 bg-background/95 backdrop-blur border-b">
          <div className="container mx-auto px-4 lg:px-6 py-4">
            <div className="flex items-center justify-between mb-4">
              <PageHeader 
                title={t('integrationsPageTitle')} 
                subtitle={t('integrationsPageSubtitle')}
                icon={Link2}
                className="mb-0"
              />
              <Button 
                className="rounded-xl bg-brand-navy hover:bg-brand-navy/90"
                onClick={() => setShowAddDialog(true)}
                data-testid="add-integration-btn"
              >
                <Plus className="h-4 w-4 me-2" />
                {t('addIntegration')}
              </Button>
            </div>
            
            {/* Main Tabs */}
            <Tabs value={activeMainTab} onValueChange={setActiveMainTab}>
              <TabsList className="grid w-full max-w-md grid-cols-2">
                <TabsTrigger value="integrations" className="flex items-center gap-2">
                  <PlugZap className="h-4 w-4" />
                  {t('integrations')}
                </TabsTrigger>
                <TabsTrigger value="api" className="flex items-center gap-2">
                  <Key className="h-4 w-4" />
                  {t('apiManagement')}
                </TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </header>
        
        {/* Main Content */}
        <main className="container mx-auto px-4 lg:px-6 py-6">
          {activeMainTab === 'integrations' ? (
            <>
              {/* Category Filter Tabs - Moved to top */}
              <div className="mb-6">
                <div className="flex flex-wrap gap-2">
                  {INTEGRATION_CATEGORIES.map(category => {
                    const CategoryIcon = category.icon;
                    const count = category.id === 'all' 
                      ? integrations.length 
                      : integrations.filter(i => i.type === category.id).length;
                    const isSelected = selectedCategory === category.id;
                    
                    return (
                      <Button
                        key={category.id}
                        variant={isSelected ? 'default' : 'outline'}
                        size="sm"
                        className={`rounded-xl ${isSelected ? 'bg-brand-navy' : ''}`}
                        onClick={() => setSelectedCategory(category.id)}
                      >
                        <CategoryIcon className="h-4 w-4 me-2" />
                        {isRTL ? category.label_ar : category.label_en}
                        <Badge variant="secondary" className="ms-2 bg-white/20">
                          {count}
                        </Badge>
                      </Button>
                    );
                  })}
                </div>
              </div>
              
              {/* Stats Cards - Below filters */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <Card 
                  className={`cursor-pointer transition-all hover:shadow-lg ${selectedStatus === 'all' ? 'ring-2 ring-brand-navy' : ''}`}
                  onClick={() => setSelectedStatus(selectedStatus === 'all' ? 'all' : 'all')}
                >
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between mb-3">
                      <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center">
                        <Link2 className="h-6 w-6 text-white" />
                      </div>
                      <span className="text-3xl font-bold">{stats.total}</span>
                    </div>
                    <p className="text-sm text-muted-foreground">{t('totalIntegrations')}</p>
                  </CardContent>
                </Card>
                
                <Card 
                  className={`cursor-pointer transition-all hover:shadow-lg ${selectedStatus === 'active' ? 'ring-2 ring-green-500' : ''}`}
                  onClick={() => setSelectedStatus(selectedStatus === 'active' ? 'all' : 'active')}
                >
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between mb-3">
                      <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-green-500 to-green-600 flex items-center justify-center">
                        <CheckCircle2 className="h-6 w-6 text-white" />
                      </div>
                      <span className="text-3xl font-bold text-green-600">{stats.active}</span>
                    </div>
                    <p className="text-sm text-muted-foreground">{t('activeIntegrations')}</p>
                  </CardContent>
                </Card>
                
                <Card 
                  className={`cursor-pointer transition-all hover:shadow-lg ${selectedStatus === 'pending' ? 'ring-2 ring-yellow-500' : ''}`}
                  onClick={() => setSelectedStatus(selectedStatus === 'pending' ? 'all' : 'pending')}
                >
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between mb-3">
                      <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-yellow-500 to-yellow-600 flex items-center justify-center">
                        <Clock className="h-6 w-6 text-white" />
                      </div>
                      <span className="text-3xl font-bold text-yellow-600">{stats.pending}</span>
                    </div>
                    <p className="text-sm text-muted-foreground">{t('pendingIntegrations')}</p>
                  </CardContent>
                </Card>
                
                <Card 
                  className={`cursor-pointer transition-all hover:shadow-lg ${selectedStatus === 'error' ? 'ring-2 ring-red-500' : ''}`}
                  onClick={() => setSelectedStatus(selectedStatus === 'error' ? 'all' : 'error')}
                >
                  <CardContent className="p-5">
                    <div className="flex items-center justify-between mb-3">
                      <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-red-500 to-red-600 flex items-center justify-center">
                        <XCircle className="h-6 w-6 text-white" />
                      </div>
                      <span className="text-3xl font-bold text-red-600">{stats.error}</span>
                    </div>
                    <p className="text-sm text-muted-foreground">{t('errorIntegrations')}</p>
                  </CardContent>
                </Card>
              </div>
              
              {/* Search and View Toggle - Separate line */}
              <div className="flex items-center gap-4 mb-6">
                <div className="relative flex-1 max-w-md">
                  <Search className="absolute start-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                  <Input
                    placeholder={t('searchPlaceholder')}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="ps-12 h-12 rounded-xl text-base"
                    data-testid="search-input"
                  />
                  {searchQuery && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="absolute end-2 top-1/2 -translate-y-1/2"
                      onClick={() => setSearchQuery('')}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  )}
                </div>
                
                {/* Active Filters Display */}
                {activeFiltersCount > 0 && (
                  <div className="flex items-center gap-2">
                    {selectedCategory !== 'all' && (
                      <Badge variant="secondary" className="flex items-center gap-1 px-3 py-1">
                        {isRTL 
                          ? INTEGRATION_CATEGORIES.find(c => c.id === selectedCategory)?.label_ar 
                          : INTEGRATION_CATEGORIES.find(c => c.id === selectedCategory)?.label_en}
                        <X className="h-3 w-3 cursor-pointer" onClick={() => setSelectedCategory('all')} />
                      </Badge>
                    )}
                    {selectedStatus !== 'all' && (
                      <Badge variant="secondary" className="flex items-center gap-1 px-3 py-1">
                        {getStatusInfo(selectedStatus).label}
                        <X className="h-3 w-3 cursor-pointer" onClick={() => setSelectedStatus('all')} />
                      </Badge>
                    )}
                    <Button variant="ghost" size="sm" onClick={clearFilters}>
                      {t('clearFilters')}
                    </Button>
                  </div>
                )}
                
                {/* View Toggle */}
                <div className="flex items-center border rounded-xl p-1">
                  <Button
                    variant={viewMode === 'card' ? 'default' : 'ghost'}
                    size="sm"
                    className={`rounded-lg ${viewMode === 'card' ? 'bg-brand-navy' : ''}`}
                    onClick={() => setViewMode('card')}
                  >
                    <LayoutGrid className="h-4 w-4" />
                  </Button>
                  <Button
                    variant={viewMode === 'table' ? 'default' : 'ghost'}
                    size="sm"
                    className={`rounded-lg ${viewMode === 'table' ? 'bg-brand-navy' : ''}`}
                    onClick={() => setViewMode('table')}
                  >
                    <List className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              
              {/* Integrations Display */}
              {filteredIntegrations.length === 0 ? (
                <Card className="p-12 text-center">
                  <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-muted flex items-center justify-center">
                    <Search className="h-8 w-8 text-muted-foreground" />
                  </div>
                  <h3 className="text-lg font-medium mb-2">{t('noResults')}</h3>
                  <p className="text-muted-foreground mb-4">
                    {t('tryChangingSearchCriteriaOrFilters')}
                  </p>
                  <Button variant="outline" onClick={clearFilters}>
                    {t('clearFilters')}
                  </Button>
                </Card>
              ) : viewMode === 'card' ? (
                /* Card View */
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                  {filteredIntegrations.map(integration => {
                    const categoryInfo = getCategoryInfo(integration.type);
                    const statusInfo = getStatusInfo(integration.status);
                    const CategoryIcon = categoryInfo.icon;
                    const StatusIcon = statusInfo.icon;
                    
                    return (
                      <Card 
                        key={integration.id} 
                        className="group relative overflow-hidden border-2 hover:border-brand-navy/30 transition-all hover:shadow-xl"
                        data-testid={`integration-card-${integration.id}`}
                      >
                        {/* Gradient Background */}
                        <div className={`absolute inset-0 bg-gradient-to-br ${categoryInfo.color} opacity-5 group-hover:opacity-10 transition-opacity`} />
                        
                        <CardContent className="p-6 relative">
                          {/* Header */}
                          <div className="flex items-start justify-between mb-4">
                            <div className="flex items-center gap-3">
                              <div className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${categoryInfo.color} flex items-center justify-center text-2xl shadow-lg`}>
                                {integration.logo}
                              </div>
                              <div>
                                <h3 className="font-bold text-lg">
                                  {isRTL ? integration.name : integration.name_en}
                                </h3>
                                <Badge variant="outline" className="text-xs mt-1">
                                  {isRTL ? categoryInfo.label_ar : categoryInfo.label_en}
                                </Badge>
                              </div>
                            </div>
                          </div>
                          
                          {/* Status Badge */}
                          <Badge className={`${statusInfo.color} text-white mb-3`}>
                            <StatusIcon className="h-3 w-3 me-1" />
                            {statusInfo.label}
                          </Badge>
                          
                          {/* Description */}
                          <p className="text-sm text-muted-foreground mb-4 line-clamp-2 min-h-[40px]">
                            {isRTL ? integration.description : integration.description_en}
                          </p>
                          
                          {/* Features Tags */}
                          {integration.features && (
                            <div className="flex flex-wrap gap-1 mb-4">
                              {(isRTL ? integration.features : integration.features_en).slice(0, 3).map((feature, idx) => (
                                <Badge key={idx} variant="secondary" className="text-xs">
                                  {feature}
                                </Badge>
                              ))}
                              {integration.features.length > 3 && (
                                <Badge variant="secondary" className="text-xs">
                                  +{integration.features.length - 3}
                                </Badge>
                              )}
                            </div>
                          )}
                          
                          {/* Last Sync */}
                          <div className="flex items-center gap-2 text-xs text-muted-foreground mb-4">
                            <Clock className="h-3 w-3" />
                            <span>{t('lastSync')}: {formatDateTime(integration.last_sync)}</span>
                          </div>
                          
                          {/* Toggle */}
                          <div className="flex items-center justify-between pb-4 border-b mb-4">
                            <span className="text-sm font-medium">
                              {integration.is_active ? t('active') : t('inactive')}
                            </span>
                            <Switch
                              checked={integration.is_active}
                              onCheckedChange={() => handleToggle(integration)}
                              data-testid={`toggle-${integration.id}`}
                            />
                          </div>
                          
                          {/* Action Buttons */}
                          <div className="grid grid-cols-2 gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              className="rounded-lg"
                              onClick={() => openDetails(integration)}
                            >
                              <Settings className="h-4 w-4 me-1" />
                              {t('setupIntegration')}
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              className="rounded-lg"
                              onClick={() => handleTestConnection(integration)}
                              disabled={testingConnection === integration.id}
                            >
                              {testingConnection === integration.id ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <>
                                  <Zap className="h-4 w-4 me-1" />
                                  {t('testConnection')}
                                </>
                              )}
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              className="rounded-lg"
                              onClick={() => openLogs(integration)}
                            >
                              <History className="h-4 w-4 me-1" />
                              {t('viewLogs')}
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              className="rounded-lg"
                              onClick={() => handleSync(integration)}
                              disabled={syncing === integration.id || !integration.is_active}
                            >
                              {syncing === integration.id ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <>
                                  <RefreshCw className="h-4 w-4 me-1" />
                                  {t('sync')}
                                </>
                              )}
                            </Button>
                          </div>
                          
                          {/* View Details */}
                          <Button
                            variant="ghost"
                            size="sm"
                            className="w-full mt-2 rounded-lg group-hover:bg-brand-navy/5"
                            onClick={() => openDetails(integration)}
                          >
                            <Eye className="h-4 w-4 me-2" />
                            {t('viewDetails')}
                            <ChevronRight className="h-4 w-4 ms-auto rtl:rotate-180" />
                          </Button>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              ) : (
                /* Table View */
                <Card>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('integration')}</TableHead>
                        <TableHead>{t('type4')}</TableHead>
                        <TableHead>{t('status2')}</TableHead>
                        <TableHead>{t('lastSync')}</TableHead>
                        <TableHead>{t('actions2')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredIntegrations.map(integration => {
                        const categoryInfo = getCategoryInfo(integration.type);
                        const statusInfo = getStatusInfo(integration.status);
                        const StatusIcon = statusInfo.icon;
                        
                        return (
                          <TableRow key={integration.id}>
                            <TableCell>
                              <div className="flex items-center gap-3">
                                <span className="text-2xl">{integration.logo}</span>
                                <div>
                                  <p className="font-medium">{isRTL ? integration.name : integration.name_en}</p>
                                  <p className="text-xs text-muted-foreground line-clamp-1">
                                    {isRTL ? integration.description : integration.description_en}
                                  </p>
                                </div>
                              </div>
                            </TableCell>
                            <TableCell>
                              <Badge variant="outline">
                                {isRTL ? categoryInfo.label_ar : categoryInfo.label_en}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              <Badge className={`${statusInfo.color} text-white`}>
                                <StatusIcon className="h-3 w-3 me-1" />
                                {statusInfo.label}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              {formatDateTime(integration.last_sync)}
                            </TableCell>
                            <TableCell>
                              <div className="flex items-center gap-2">
                                <Switch
                                  checked={integration.is_active}
                                  onCheckedChange={() => handleToggle(integration)}
                                />
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => openDetails(integration)}
                                >
                                  <Settings className="h-4 w-4" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleTestConnection(integration)}
                                  disabled={testingConnection === integration.id}
                                >
                                  {testingConnection === integration.id ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                  ) : (
                                    <Zap className="h-4 w-4" />
                                  )}
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleSync(integration)}
                                  disabled={syncing === integration.id}
                                >
                                  {syncing === integration.id ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                  ) : (
                                    <RefreshCw className="h-4 w-4" />
                                  )}
                                </Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </Card>
              )}
            </>
          ) : (
            /* API Management Tab */
            <div className="space-y-6">
              {/* API Overview Card */}
              <Card className="bg-gradient-to-br from-brand-navy to-brand-navy/80 text-white">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-2xl font-bold mb-2">{t('nassaqApi')}</h2>
                      <p className="text-white/70">
                        {t('manageNassaqPlatformApiKeysAndAccess')}
                      </p>
                    </div>
                    <div className="flex gap-3">
                      <Button 
                        variant="secondary" 
                        className="rounded-xl"
                        onClick={() => setShowShareDialog(true)}
                      >
                        <Share2 className="h-4 w-4 me-2" />
                        {t('shareTemplate')}
                      </Button>
                      <Button 
                        className="rounded-xl bg-white text-brand-navy hover:bg-white/90"
                        onClick={() => setShowNewKeyDialog(true)}
                      >
                        <Plus className="h-4 w-4 me-2" />
                        {t('generateNewKey')}
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
              
              {/* API Base Info */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* API Keys */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Key className="h-5 w-5 text-brand-navy" />
                      {t('apiKeys')}
                    </CardTitle>
                    <CardDescription>
                      {t('apiAccessKeys')}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {apiKeys.map(key => (
                      <div 
                        key={key.id}
                        className={`p-4 rounded-xl border ${key.is_active ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-200'}`}
                      >
                        <div className="flex items-start justify-between mb-3">
                          <div>
                            <h4 className="font-medium flex items-center gap-2">
                              {key.name}
                              {key.is_active ? (
                                <Badge className="bg-green-500">{t('active')}</Badge>
                              ) : (
                                <Badge variant="secondary">{t('inactive')}</Badge>
                              )}
                            </h4>
                            <p className="text-xs text-muted-foreground mt-1">
                              {t('createdAt')}: {formatDateTime(key.created_at)}
                            </p>
                          </div>
                          <Badge variant="outline">
                            {key.permissions === 'full_access' ? t('fullAccess') :
                             key.permissions === 'read_write' ? t('readWrite') : t('readOnly')}
                          </Badge>
                        </div>
                        
                        {/* API Key */}
                        <div className="space-y-2">
                          <div className="flex items-center gap-2">
                            <code className="flex-1 bg-black/5 px-3 py-1.5 rounded text-xs font-mono" dir="ltr">
                              {key.key}
                            </code>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => copyToClipboard(key.key, `key-${key.id}`)}
                            >
                              {copiedField === `key-${key.id}` ? (
                                <Check className="h-4 w-4 text-green-500" />
                              ) : (
                                <Copy className="h-4 w-4" />
                              )}
                            </Button>
                          </div>
                          
                          {/* Secret */}
                          <div className="flex items-center gap-2">
                            <code className="flex-1 bg-black/5 px-3 py-1.5 rounded text-xs font-mono" dir="ltr">
                              {key.secret.substring(0, 10)}{'•'.repeat(20)}
                            </code>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => copyToClipboard(key.secret, `secret-${key.id}`)}
                            >
                              {copiedField === `secret-${key.id}` ? (
                                <Check className="h-4 w-4 text-green-500" />
                              ) : (
                                <Copy className="h-4 w-4" />
                              )}
                            </Button>
                          </div>
                        </div>
                        
                        {key.is_active && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="mt-3 text-red-600 hover:text-red-700 hover:bg-red-50"
                            onClick={() => handleRevokeKey(key.id)}
                          >
                            <Lock className="h-4 w-4 me-1" />
                            {t('revokeKey')}
                          </Button>
                        )}
                      </div>
                    ))}
                  </CardContent>
                </Card>
                
                {/* API Endpoints */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Terminal className="h-5 w-5 text-brand-navy" />
                      {t('endpoints')}
                    </CardTitle>
                    <CardDescription>
                      {t('availableApiEndpoints')}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {/* Base URL */}
                    <div className="mb-4 p-3 bg-brand-navy/5 rounded-xl">
                      <Label className="text-xs text-muted-foreground">{t('baseUrl')}</Label>
                      <div className="flex items-center gap-2 mt-1">
                        <code className="flex-1 font-mono text-sm" dir="ltr">{API_URL}/api</code>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => copyToClipboard(`${API_URL}/api`, 'base-url')}
                        >
                          {copiedField === 'base-url' ? (
                            <Check className="h-4 w-4 text-green-500" />
                          ) : (
                            <Copy className="h-4 w-4" />
                          )}
                        </Button>
                      </div>
                    </div>
                    
                    <ScrollArea className="h-[300px]">
                      <div className="space-y-2">
                        {NASSAQ_ENDPOINTS.map((endpoint, idx) => (
                          <div key={idx} className="flex items-center gap-3 p-2 hover:bg-muted/50 rounded-lg">
                            <Badge variant={endpoint.method === 'GET' ? 'secondary' : 'default'} className="w-16 justify-center">
                              {endpoint.method}
                            </Badge>
                            <code className="flex-1 text-sm font-mono" dir="ltr">{endpoint.path}</code>
                            <span className="text-xs text-muted-foreground">
                              {isRTL ? endpoint.description_ar : endpoint.description_en}
                            </span>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => copyToClipboard(`${API_URL}${endpoint.path}`, `endpoint-${idx}`)}
                            >
                              {copiedField === `endpoint-${idx}` ? (
                                <Check className="h-4 w-4 text-green-500" />
                              ) : (
                                <Copy className="h-4 w-4" />
                              )}
                            </Button>
                          </div>
                        ))}
                      </div>
                    </ScrollArea>
                    
                    {/* Documentation Link */}
                    <Button variant="outline" className="w-full mt-4 rounded-xl">
                      <FileText className="h-4 w-4 me-2" />
                      {t('documentation')}
                      <ExternalLink className="h-4 w-4 ms-auto" />
                    </Button>
                  </CardContent>
                </Card>
              </div>
            </div>
          )}
        </main>
        
        {/* Integration Details Sheet */}
        <Sheet open={showDetailsSheet} onOpenChange={setShowDetailsSheet}>
          <SheetContent side={isRTL ? 'left' : 'right'} className="w-[500px] sm:w-[600px] overflow-y-auto">
            <SheetHeader>
              <SheetTitle className="flex items-center gap-3">
                {selectedIntegration && (
                  <>
                    <span className="text-3xl">{selectedIntegration.logo}</span>
                    {isRTL ? selectedIntegration.name : selectedIntegration.name_en}
                  </>
                )}
              </SheetTitle>
              <SheetDescription>
                {selectedIntegration && (isRTL ? selectedIntegration.description : selectedIntegration.description_en)}
              </SheetDescription>
            </SheetHeader>
            
            {selectedIntegration && (
              <div className="space-y-6 py-6">
                {/* Status */}
                <div className="flex items-center justify-between p-4 bg-muted/30 rounded-xl">
                  <span className="font-medium">{t('status2')}</span>
                  <div className="flex items-center gap-2">
                    <Badge className={getStatusInfo(selectedIntegration.status).color}>
                      {getStatusInfo(selectedIntegration.status).label}
                    </Badge>
                    <Switch
                      checked={selectedIntegration.is_active}
                      onCheckedChange={() => handleToggle(selectedIntegration)}
                    />
                  </div>
                </div>
                
                {/* Connection Settings */}
                <div className="space-y-4">
                  <h4 className="font-medium flex items-center gap-2">
                    <Settings className="h-4 w-4" />
                    {t('connectionSettings')}
                  </h4>
                  
                  <div className="space-y-3">
                    <div className="space-y-2">
                      <Label>{t('apiUrl')}</Label>
                      <div className="flex gap-2">
                        <Input value={selectedIntegration.api_base_url} readOnly dir="ltr" />
                        <Button
                          variant="outline"
                          size="icon"
                          onClick={() => copyToClipboard(selectedIntegration.api_base_url, 'detail-url')}
                        >
                          {copiedField === 'detail-url' ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
                        </Button>
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      <Label>{t('apiKey')}</Label>
                      <div className="flex gap-2">
                        <Input type="password" value="••••••••••••••••••••" readOnly dir="ltr" />
                        <Button variant="outline" size="icon">
                          <Eye className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      <Label>{t('webhookUrl')}</Label>
                      <div className="flex gap-2">
                        <Input value={`${API_URL}/api/webhooks/${selectedIntegration.id}`} readOnly dir="ltr" />
                        <Button
                          variant="outline"
                          size="icon"
                          onClick={() => copyToClipboard(`${API_URL}/api/webhooks/${selectedIntegration.id}`, 'webhook')}
                        >
                          {copiedField === 'webhook' ? <Check className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
                
                {/* Features */}
                {selectedIntegration.features && (
                  <div className="space-y-3">
                    <h4 className="font-medium">{t('availableFeatures')}</h4>
                    <div className="flex flex-wrap gap-2">
                      {(isRTL ? selectedIntegration.features : selectedIntegration.features_en).map((feature, idx) => (
                        <Badge key={idx} variant="secondary">{feature}</Badge>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* Actions */}
                <div className="flex gap-3 pt-4">
                  <Button 
                    className="flex-1 bg-brand-navy rounded-xl"
                    onClick={() => handleTestConnection(selectedIntegration)}
                    disabled={testingConnection === selectedIntegration.id}
                  >
                    {testingConnection === selectedIntegration.id ? (
                      <Loader2 className="h-4 w-4 animate-spin me-2" />
                    ) : (
                      <Zap className="h-4 w-4 me-2" />
                    )}
                    {t('testConnection')}
                  </Button>
                  <Button 
                    variant="outline" 
                    className="flex-1 rounded-xl"
                    onClick={() => handleSync(selectedIntegration)}
                    disabled={syncing === selectedIntegration.id}
                  >
                    {syncing === selectedIntegration.id ? (
                      <Loader2 className="h-4 w-4 animate-spin me-2" />
                    ) : (
                      <RefreshCw className="h-4 w-4 me-2" />
                    )}
                    {t('sync')}
                  </Button>
                </div>
              </div>
            )}
          </SheetContent>
        </Sheet>
        
        {/* Logs Sheet */}
        <Sheet open={showLogsSheet} onOpenChange={setShowLogsSheet}>
          <SheetContent side={isRTL ? 'left' : 'right'} className="w-[450px] sm:w-[600px] overflow-y-auto">
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2">
                <History className="h-5 w-5 text-brand-navy" />
                {t('logs')}
                {selectedIntegration && (
                  <Badge variant="outline">{isRTL ? selectedIntegration.name : selectedIntegration.name_en}</Badge>
                )}
              </SheetTitle>
            </SheetHeader>
            <div className="space-y-4 py-6">
              {INITIAL_LOGS.length === 0 ? (
                <div className="text-center text-muted-foreground py-12">
                  <FileText className="h-12 w-12 mx-auto mb-4 text-muted-foreground/30" />
                  <p>{t('noLogsYet')}</p>
                </div>
              ) : (
                INITIAL_LOGS.map(log => (
                <div 
                  key={log.id}
                  className={`p-4 rounded-xl border ${
                    log.status === 'success' ? 'bg-green-50 border-green-200' :
                    log.status === 'failed' ? 'bg-red-50 border-red-200' :
                    'bg-muted/30'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      {log.status === 'success' ? (
                        <CheckCircle2 className="h-4 w-4 text-green-600" />
                      ) : log.status === 'failed' ? (
                        <XCircle className="h-4 w-4 text-red-600" />
                      ) : (
                        <Clock className="h-4 w-4 text-yellow-600" />
                      )}
                      <span className="font-medium text-sm">
                        {log.action === 'sync' ? (t('sync')) :
                         log.action === 'test' ? (t('test')) :
                         log.action === 'webhook' ? 'Webhook' : log.action}
                      </span>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {formatDateTime(log.timestamp)}
                    </span>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {isRTL ? log.details_ar : log.details_en}
                  </p>
                </div>
              ))
              )}
            </div>
          </SheetContent>
        </Sheet>
        
        {/* Share Template Dialog */}
        <Dialog open={showShareDialog} onOpenChange={setShowShareDialog}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Share2 className="h-5 w-5 text-brand-navy" />
                {t('shareTemplate')}
              </DialogTitle>
              <DialogDescription>
                {t('readyTemplateForSharingIntegrationData')}
              </DialogDescription>
            </DialogHeader>
            <div className="py-4">
              <Textarea
                value={generateShareTemplate()}
                readOnly
                rows={15}
                className="font-mono text-sm"
                dir="rtl"
              />
            </div>
            <DialogFooter className="flex-row-reverse gap-2">
              <Button variant="outline" onClick={() => setShowShareDialog(false)}>
                {t('cancel')}
              </Button>
              <Button 
                onClick={() => {
                  copyToClipboard(generateShareTemplate(), 'share-template');
                  setShowShareDialog(false);
                }}
                className="bg-brand-navy"
              >
                <Copy className="h-4 w-4 me-2" />
                {t('copyAll')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* New API Key Dialog */}
        <Dialog open={showNewKeyDialog} onOpenChange={setShowNewKeyDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Key className="h-5 w-5 text-brand-navy" />
                {t('generateNewKey')}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>{t('keyName')}</Label>
                <Input
                  value={newKeyForm.name}
                  onChange={(e) => setNewKeyForm({ ...newKeyForm, name: e.target.value })}
                  placeholder={t('egProductionKey')}
                />
              </div>
              
              <div className="space-y-2">
                <Label>{t('permissions')}</Label>
                <Select 
                  value={newKeyForm.permissions} 
                  onValueChange={(v) => setNewKeyForm({ ...newKeyForm, permissions: v })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="read_only">{t('readOnly')}</SelectItem>
                    <SelectItem value="read_write">{t('readWrite')}</SelectItem>
                    <SelectItem value="full_access">{t('fullAccess')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter className="flex-row-reverse gap-2">
              <Button variant="outline" onClick={() => setShowNewKeyDialog(false)}>
                {t('cancel')}
              </Button>
              <Button onClick={handleGenerateKey} className="bg-brand-navy" disabled={!newKeyForm.name}>
                <Plus className="h-4 w-4 me-2" />
                {t('generateNewKey')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Add Integration Dialog */}
        <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Plus className="h-5 w-5 text-brand-navy" />
                {t('addIntegration')}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>{t('nameArabic')}</Label>
                  <Input
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label>{t('nameEnglish')}</Label>
                  <Input
                    value={formData.name_en}
                    onChange={(e) => setFormData({ ...formData, name_en: e.target.value })}
                    dir="ltr"
                  />
                </div>
              </div>
              
              <div className="space-y-2">
                <Label>{t('integrationType')}</Label>
                <Select value={formData.type} onValueChange={(v) => setFormData({ ...formData, type: v })}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {INTEGRATION_CATEGORIES.filter(c => c.id !== 'all').map(type => (
                      <SelectItem key={type.id} value={type.id}>
                        {isRTL ? type.label_ar : type.label_en}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div className="space-y-2">
                <Label>{t('description')}</Label>
                <Textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  rows={2}
                />
              </div>
              
              <div className="space-y-2">
                <Label>{t('apiUrl')}</Label>
                <Input
                  value={formData.api_base_url}
                  onChange={(e) => setFormData({ ...formData, api_base_url: e.target.value })}
                  dir="ltr"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>{t('apiKey')}</Label>
                  <Input
                    type="password"
                    value={formData.api_key}
                    onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
                    dir="ltr"
                  />
                </div>
                <div className="space-y-2">
                  <Label>{t('secretKey')}</Label>
                  <Input
                    type="password"
                    value={formData.secret_key}
                    onChange={(e) => setFormData({ ...formData, secret_key: e.target.value })}
                    dir="ltr"
                  />
                </div>
              </div>
            </div>
            <DialogFooter className="flex-row-reverse gap-2">
              <Button variant="outline" onClick={() => setShowAddDialog(false)}>
                {t('cancel')}
              </Button>
              <Button className="bg-brand-navy" onClick={handleAddIntegration}>
                {t('save')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Sidebar>
  );
}
