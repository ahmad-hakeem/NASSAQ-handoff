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
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
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
  BookOpen,
  Plus,
  Search,
  Filter,
  Clock,
  CheckCircle,
  CheckCircle2,
  Settings,
  FileText,
  AlertCircle,
  RefreshCw,
  Calendar,
  Users,
  GraduationCap,
  Building2,
  Edit,
  Trash2,
  Copy,
  Eye,
  EyeOff,
  ChevronRight,
  XCircle,
  AlertTriangle,
  Shield,
  Percent,
  Hash,
  ToggleRight,
  List,
  Zap,
  Brain,
  Globe,
  Lock,
  Unlock,
  Save,
  X,
  Info,
  ArrowLeft,
  LayoutGrid,
  Table,
  Download,
  Upload,
  History,
  Play,
  Pause,
} from 'lucide-react';

// Translations
// Rule Categories
const RULE_CATEGORIES = {
  attendance: {
    id: 'attendance',
    title_ar: 'قواعد الحضور والغياب',
    title_en: 'Attendance Rules',
    description_ar: 'إدارة قواعد تسجيل الحضور والتأخر والغياب',
    description_en: 'Manage attendance, tardiness, and absence rules',
    icon: Clock,
    color: 'bg-blue-500',
  },
  grading: {
    id: 'grading',
    title_ar: 'قواعد التقييم والدرجات',
    title_en: 'Grading Rules',
    description_ar: 'نظام الدرجات والتقييمات والاختبارات',
    description_en: 'Grading system, assessments, and exams rules',
    icon: FileText,
    color: 'bg-green-500',
  },
  scheduling: {
    id: 'scheduling',
    title_ar: 'قواعد الجدولة',
    title_en: 'Scheduling Rules',
    description_ar: 'قواعد توزيع الحصص ونصاب المعلمين',
    description_en: 'Class distribution and teacher workload rules',
    icon: Calendar,
    color: 'bg-purple-500',
  },
  behavior: {
    id: 'behavior',
    title_ar: 'قواعد السلوك',
    title_en: 'Behavior Rules',
    description_ar: 'نظام نقاط السلوك والمكافآت والعقوبات',
    description_en: 'Behavior points, rewards, and penalties system',
    icon: Users,
    color: 'bg-orange-500',
  },
  academic: {
    id: 'academic',
    title_ar: 'القواعد الأكاديمية',
    title_en: 'Academic Rules',
    description_ar: 'متطلبات النجاح والانتقال بين المراحل',
    description_en: 'Pass requirements and grade progression rules',
    icon: GraduationCap,
    color: 'bg-teal-500',
  },
  tenant: {
    id: 'tenant',
    title_ar: 'قواعد المدارس',
    title_en: 'Tenant Rules',
    description_ar: 'قواعد إنشاء وإدارة المدارس',
    description_en: 'School creation and management rules',
    icon: Building2,
    color: 'bg-indigo-500',
  },
  security: {
    id: 'security',
    title_ar: 'قواعد الأمان',
    title_en: 'Security Rules',
    description_ar: 'قواعد كلمات المرور والوصول',
    description_en: 'Password and access control rules',
    icon: Shield,
    color: 'bg-red-500',
  },
  ai: {
    id: 'ai',
    title_ar: 'قواعد الذكاء الاصطناعي',
    title_en: 'AI Rules',
    description_ar: 'قواعد استخدام وتفعيل الذكاء الاصطناعي',
    description_en: 'AI usage and activation rules',
    icon: Brain,
    color: 'bg-pink-500',
  },
};

// Rule Types
const RULE_TYPES = {
  numeric: { label_ar: 'رقمي', label_en: 'Numeric', icon: Hash },
  percentage: { label_ar: 'نسبة مئوية', label_en: 'Percentage', icon: Percent },
  boolean: { label_ar: 'نعم/لا', label_en: 'Yes/No', icon: ToggleRight },
  list: { label_ar: 'قائمة', label_en: 'List', icon: List },
  text: { label_ar: 'نص', label_en: 'Text', icon: FileText },
};

// Empty initial state - rules will be fetched from API
const INITIAL_RULES = [];

export const RulesManagementPage = () => {
  const { t } = useTranslation();
  const { isRTL = true, isDark } = useTheme();
  const navigate = useNavigate();
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const { api } = useAuth();
  
  // States
  const [rules, setRules] = useState([]);
  const [filteredRules, setFilteredRules] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedStatus, setSelectedStatus] = useState('all');
  const [viewMode, setViewMode] = useState('grid');
  const [activeTab, setActiveTab] = useState('all');
  const [loading, setLoading] = useState(true);
  
  const fetchRules = async () => {
    setLoading(true);
    try {
      const response = await api.get('/system/rules');
      const data = response.data;
      setRules(data.rules || []);
      setFilteredRules(data.rules || []);
    } catch (error) {
      console.error('Error fetching rules:', error);
      nassaqError(t('failedToLoadRules'));
    } finally {
      setLoading(false);
    }
  };
  
  // Fetch on mount
  useEffect(() => {
    fetchRules();
  }, []);
  
  // Dialogs
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showEditSheet, setShowEditSheet] = useState(null);
  const [showDeleteDialog, setShowDeleteDialog] = useState(null);
  const [showViewSheet, setShowViewSheet] = useState(null);
  
  // Form state
  const [formData, setFormData] = useState({
    name_ar: '',
    name_en: '',
    description_ar: '',
    description_en: '',
    category: 'attendance',
    type: 'numeric',
    value: '',
    unit: '',
    status: 'draft',
    priority: 'medium',
    applies_to: 'all',
  });
  
  // Stats
  const stats = {
    total: rules.length,
    active: rules.filter(r => r.status === 'active').length,
    draft: rules.filter(r => r.status === 'draft').length,
    disabled: rules.filter(r => r.status === 'disabled').length,
  };
  
  // Category stats
  const categoryStats = Object.keys(RULE_CATEGORIES).map(catId => ({
    ...RULE_CATEGORIES[catId],
    count: rules.filter(r => r.category === catId).length,
  }));
  
  // Filter rules
  useEffect(() => {
    let result = [...rules];
    
    // Search
    if (searchTerm) {
      const query = searchTerm.toLowerCase();
      result = result.filter(rule => 
        rule.name_ar?.toLowerCase().includes(query) ||
        rule.name_en?.toLowerCase().includes(query) ||
        rule.description_ar?.toLowerCase().includes(query) ||
        rule.description_en?.toLowerCase().includes(query)
      );
    }
    
    // Category filter
    if (selectedCategory !== 'all') {
      result = result.filter(r => r.category === selectedCategory);
    }
    
    // Status filter
    if (selectedStatus !== 'all') {
      result = result.filter(r => r.status === selectedStatus);
    }
    
    setFilteredRules(result);
  }, [rules, searchTerm, selectedCategory, selectedStatus]);
  
  // Reset filters
  const resetFilters = () => {
    setSearchTerm('');
    setSelectedCategory('all');
    setSelectedStatus('all');
  };
  
  // Handle create rule - connected to API
  const handleCreateRule = async () => {
    try {
      await api.post('/system/rules', formData);
      toast.success(t('ruleCreated'));
      setShowCreateDialog(false);
      resetForm();
      fetchRules();
    } catch (error) {
      console.error('Error creating rule:', error);
      nassaqError(t('failedToCreateRule'));
    }
  };
  
  // Handle edit rule - connected to API
  const handleEditRule = async () => {
    try {
      await api.put(`/system/rules/${showEditSheet.id}`, formData);
      toast.success(t('ruleUpdated'));
      setShowEditSheet(null);
      resetForm();
      fetchRules();
    } catch (error) {
      console.error('Error updating rule:', error);
      nassaqError(t('failedToUpdateRule'));
    }
  };
  
  // Handle delete rule - connected to API
  const handleDeleteRule = async () => {
    try {
      await api.delete(`/system/rules/${showDeleteDialog.id}`);
      toast.success(t('ruleDeleted'));
      setShowDeleteDialog(null);
      fetchRules();
    } catch (error) {
      console.error('Error deleting rule:', error);
      nassaqError(t('failedToDeleteRule'));
    }
  };
  
  // Handle duplicate rule - connected to API
  const handleDuplicateRule = async (rule) => {
    const newRuleData = {
      name_ar: rule.name_ar + ' (نسخة)',
      name_en: rule.name_en + ' (Copy)',
      description_ar: rule.description_ar,
      description_en: rule.description_en,
      category: rule.category,
      type: rule.type,
      value: rule.value,
      unit: rule.unit,
      status: 'draft',
      priority: rule.priority,
      applies_to: rule.applies_to,
    };
    
    try {
      await api.post('/system/rules', newRuleData);
      toast.success(t('ruleDuplicated'));
      fetchRules();
    } catch (error) {
      console.error('Error duplicating rule:', error);
      nassaqError(t('failedToDuplicateRule'));
    }
  };
  
  // Handle toggle status
  const handleToggleStatus = (rule) => {
    const newStatus = rule.status === 'active' ? 'disabled' : 'active';
    setRules(prev => prev.map(r => 
      r.id === rule.id ? { ...r, status: newStatus, updated_at: new Date().toISOString().split('T')[0] } : r
    ));
    toast.success(newStatus === 'active' ? t('ruleEnabled') : t('ruleDisabled'));
  };
  
  // Reset form
  const resetForm = () => {
    setFormData({
      name_ar: '',
      name_en: '',
      description_ar: '',
      description_en: '',
      category: 'attendance',
      type: 'numeric',
      value: '',
      unit: '',
      status: 'draft',
      priority: 'medium',
      applies_to: 'all',
    });
  };
  
  // Open edit
  const openEdit = (rule) => {
    setFormData({
      name_ar: rule.name_ar,
      name_en: rule.name_en,
      description_ar: rule.description_ar,
      description_en: rule.description_en,
      category: rule.category,
      type: rule.type,
      value: rule.value,
      unit: rule.unit || '',
      status: rule.status,
      priority: rule.priority,
      applies_to: rule.applies_to,
    });
    setShowEditSheet(rule);
  };
  
  // Get category info
  const getCategoryInfo = (catId) => RULE_CATEGORIES[catId] || RULE_CATEGORIES.attendance;
  
  // Get status badge
  const getStatusBadge = (status) => {
    switch (status) {
      case 'active':
        return <Badge className="bg-green-500 text-white"><CheckCircle2 className="h-3 w-3 me-1" />{t('active')}</Badge>;
      case 'draft':
        return <Badge className="bg-yellow-500 text-white"><Clock className="h-3 w-3 me-1" />{t('draft')}</Badge>;
      case 'disabled':
        return <Badge className="bg-gray-500 text-white"><XCircle className="h-3 w-3 me-1" />{t('disabled')}</Badge>;
      default:
        return <Badge variant="outline">{status}</Badge>;
    }
  };
  
  // Get priority badge
  const getPriorityBadge = (priority) => {
    switch (priority) {
      case 'high':
        return <Badge variant="outline" className="border-red-500 text-red-600">{t('high')}</Badge>;
      case 'medium':
        return <Badge variant="outline" className="border-yellow-500 text-yellow-600">{t('medium')}</Badge>;
      case 'low':
        return <Badge variant="outline" className="border-green-500 text-green-600">{t('low')}</Badge>;
      default:
        return <Badge variant="outline">{priority}</Badge>;
    }
  };
  
  // Format value display
  const formatValue = (rule) => {
    if (rule.type === 'boolean') {
      return rule.value ? (t('yes')) : (t('no'));
    }
    if (rule.type === 'percentage') {
      return `${rule.value}%`;
    }
    return rule.unit ? `${rule.value} ${rule.unit}` : rule.value;
  };
  
  return (
    <Sidebar>
      <div className="min-h-screen bg-background" dir={isRTL ? 'rtl' : 'ltr'} data-testid="rules-management-page">
        {/* Header */}
        <header className="sticky top-0 z-40 bg-background/95 backdrop-blur border-b">
          <div className="container mx-auto px-4 lg:px-6 py-4">
            <div className="flex items-center justify-between mb-4">
              <PageHeader 
                title={t('pageTitle')} 
                subtitle={t('pageSubtitle')}
                icon={BookOpen}
                className="mb-0"
              />
              <div className="flex items-center gap-3">
                <Button 
                  variant="outline" 
                  className="rounded-xl"
                  onClick={() => {
                    // تصدير القواعد كملف JSON
                    const exportData = rules.map(r => ({
                      name_ar: r.name_ar,
                      name_en: r.name_en,
                      category: r.category,
                      type: r.type,
                      value: r.value,
                      status: r.status,
                      priority: r.priority,
                      description_ar: r.description_ar,
                      description_en: r.description_en,
                    }));
                    
                    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
                    const link = document.createElement('a');
                    link.href = URL.createObjectURL(blob);
                    link.download = `rules_export_${new Date().toISOString().split('T')[0]}.json`;
                    link.click();
                    toast.success(t('rulesExportedSuccessfully'));
                  }}
                >
                  <Download className="h-4 w-4 me-2" />
                  {t('export')}
                </Button>
                <Button 
                  className="rounded-xl bg-brand-navy hover:bg-brand-navy/90"
                  onClick={() => setShowCreateDialog(true)}
                  data-testid="create-rule-btn"
                >
                  <Plus className="h-4 w-4 me-2" />
                  {t('newRule')}
                </Button>
              </div>
            </div>
            
            {/* Stats Cards */}
            <div className="grid grid-cols-4 gap-4 mb-4">
              <Card className="bg-gradient-to-br from-brand-navy to-brand-navy/80 text-white">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-white/70 text-sm">{t('totalRules')}</p>
                      <p className="text-3xl font-bold">{stats.total}</p>
                    </div>
                    <BookOpen className="h-10 w-10 text-white/30" />
                  </div>
                </CardContent>
              </Card>
              <Card className="border-green-200 bg-green-50">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-green-600 text-sm">{t('activeRules')}</p>
                      <p className="text-3xl font-bold text-green-700">{stats.active}</p>
                    </div>
                    <CheckCircle className="h-10 w-10 text-green-200" />
                  </div>
                </CardContent>
              </Card>
              <Card className="border-yellow-200 bg-yellow-50">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-yellow-600 text-sm">{t('draftRules')}</p>
                      <p className="text-3xl font-bold text-yellow-700">{stats.draft}</p>
                    </div>
                    <Clock className="h-10 w-10 text-yellow-200" />
                  </div>
                </CardContent>
              </Card>
              <Card className="border-purple-200 bg-purple-50">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-purple-600 text-sm">{t('categories')}</p>
                      <p className="text-3xl font-bold text-purple-700">{Object.keys(RULE_CATEGORIES).length}</p>
                    </div>
                    <Settings className="h-10 w-10 text-purple-200" />
                  </div>
                </CardContent>
              </Card>
            </div>
            
            {/* Search and Filters */}
            <div className="flex flex-wrap items-center gap-4">
              <div className="relative flex-1 min-w-[300px]">
                <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder={t('search')}
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="ps-10 rounded-xl"
                />
              </div>
              
              <Select value={selectedCategory} onValueChange={setSelectedCategory}>
                <SelectTrigger className="w-40 rounded-xl">
                  <SelectValue placeholder={t('ruleCategory')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('allCategories')}</SelectItem>
                  {Object.entries(RULE_CATEGORIES).map(([key, cat]) => (
                    <SelectItem key={key} value={key}>
                      {isRTL ? cat.title_ar : cat.title_en}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              
              <Select value={selectedStatus} onValueChange={setSelectedStatus}>
                <SelectTrigger className="w-36 rounded-xl">
                  <SelectValue placeholder={t('ruleStatus')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('allStatus')}</SelectItem>
                  <SelectItem value="active">{t('active')}</SelectItem>
                  <SelectItem value="draft">{t('draft')}</SelectItem>
                  <SelectItem value="disabled">{t('disabled')}</SelectItem>
                </SelectContent>
              </Select>
              
              <Button variant="outline" onClick={resetFilters} className="rounded-xl">
                <RefreshCw className="h-4 w-4 me-2" />
                {t('reset')}
              </Button>
              
              <div className="flex items-center border rounded-xl overflow-hidden">
                <Button 
                  variant={viewMode === 'grid' ? 'default' : 'ghost'} 
                  size="icon" 
                  className="rounded-none"
                  onClick={() => setViewMode('grid')}
                >
                  <LayoutGrid className="h-4 w-4" />
                </Button>
                <Button 
                  variant={viewMode === 'list' ? 'default' : 'ghost'} 
                  size="icon" 
                  className="rounded-none"
                  onClick={() => setViewMode('list')}
                >
                  <List className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        </header>
        
        {/* Main Content */}
        <main className="container mx-auto px-4 lg:px-6 py-6">
          <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
            <TabsList>
              <TabsTrigger value="all">{t('allRules')}</TabsTrigger>
              <TabsTrigger value="category">{t('byCategory')}</TabsTrigger>
            </TabsList>
            
            {/* All Rules Tab */}
            <TabsContent value="all" className="space-y-4">
              {filteredRules.length === 0 ? (
                <Card className="p-12 text-center">
                  <BookOpen className="h-16 w-16 mx-auto text-muted-foreground/30 mb-4" />
                  <h3 className="font-bold text-lg mb-2">{t('noRules')}</h3>
                  <p className="text-muted-foreground mb-4">{t('noRulesDesc')}</p>
                  <Button onClick={() => setShowCreateDialog(true)}>
                    <Plus className="h-4 w-4 me-2" />
                    {t('newRule')}
                  </Button>
                </Card>
              ) : viewMode === 'grid' ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {filteredRules.map((rule) => {
                    const category = getCategoryInfo(rule.category);
                    const CategoryIcon = category.icon;
                    
                    return (
                      <Card 
                        key={rule.id}
                        className="card-nassaq hover:shadow-lg transition-all"
                        data-testid={`rule-card-${rule.id}`}
                      >
                        <CardHeader className="pb-2">
                          <div className="flex items-start justify-between">
                            <div className={`w-10 h-10 rounded-xl ${category.color} flex items-center justify-center`}>
                              <CategoryIcon className="h-5 w-5 text-white" />
                            </div>
                            <div className="flex items-center gap-2">
                              {getStatusBadge(rule.status)}
                            </div>
                          </div>
                          <CardTitle className="font-cairo text-lg mt-3">
                            {isRTL ? rule.name_ar : rule.name_en}
                          </CardTitle>
                          <CardDescription className="line-clamp-2">
                            {isRTL ? rule.description_ar : rule.description_en}
                          </CardDescription>
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-3">
                            {/* Value */}
                            <div className="flex items-center justify-between p-2 bg-muted/30 rounded-lg">
                              <span className="text-sm text-muted-foreground">{t('ruleValue')}:</span>
                              <span className="font-bold text-brand-navy">{formatValue(rule)}</span>
                            </div>
                            
                            {/* Priority */}
                            <div className="flex items-center justify-between">
                              <span className="text-sm text-muted-foreground">{t('priority')}:</span>
                              {getPriorityBadge(rule.priority)}
                            </div>
                            
                            {/* Actions */}
                            <div className="flex items-center gap-2 pt-3 border-t">
                              <Button 
                                variant="outline" 
                                size="sm" 
                                className="flex-1"
                                onClick={() => setShowViewSheet(rule)}
                              >
                                <Eye className="h-3 w-3 me-1" />
                                {t('view')}
                              </Button>
                              <Button 
                                variant="outline" 
                                size="sm" 
                                className="flex-1"
                                onClick={() => openEdit(rule)}
                              >
                                <Edit className="h-3 w-3 me-1" />
                                {t('edit')}
                              </Button>
                              <Button 
                                variant="outline" 
                                size="icon"
                                onClick={() => handleToggleStatus(rule)}
                              >
                                {rule.status === 'active' ? (
                                  <Pause className="h-3 w-3" />
                                ) : (
                                  <Play className="h-3 w-3" />
                                )}
                              </Button>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              ) : (
                <Card>
                  <div className="divide-y">
                    {filteredRules.map((rule) => {
                      const category = getCategoryInfo(rule.category);
                      const CategoryIcon = category.icon;
                      
                      return (
                        <div 
                          key={rule.id}
                          className="p-4 flex items-center justify-between hover:bg-muted/30 transition-colors"
                        >
                          <div className="flex items-center gap-4">
                            <div className={`w-10 h-10 rounded-xl ${category.color} flex items-center justify-center`}>
                              <CategoryIcon className="h-5 w-5 text-white" />
                            </div>
                            <div>
                              <h4 className="font-bold">{isRTL ? rule.name_ar : rule.name_en}</h4>
                              <p className="text-sm text-muted-foreground">
                                {isRTL ? category.title_ar : category.title_en}
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-4">
                            <span className="font-bold text-brand-navy">{formatValue(rule)}</span>
                            {getStatusBadge(rule.status)}
                            {getPriorityBadge(rule.priority)}
                            <div className="flex items-center gap-1">
                              <Button variant="ghost" size="icon" onClick={() => setShowViewSheet(rule)}>
                                <Eye className="h-4 w-4" />
                              </Button>
                              <Button variant="ghost" size="icon" onClick={() => openEdit(rule)}>
                                <Edit className="h-4 w-4" />
                              </Button>
                              <Button variant="ghost" size="icon" onClick={() => handleDuplicateRule(rule)}>
                                <Copy className="h-4 w-4" />
                              </Button>
                              <Button variant="ghost" size="icon" onClick={() => setShowDeleteDialog(rule)}>
                                <Trash2 className="h-4 w-4 text-red-500" />
                              </Button>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </Card>
              )}
            </TabsContent>
            
            {/* By Category Tab */}
            <TabsContent value="category" className="space-y-6">
              {categoryStats.map((category) => {
                const CategoryIcon = category.icon;
                const categoryRules = rules.filter(r => r.category === category.id);
                
                if (categoryRules.length === 0) return null;
                
                return (
                  <div key={category.id}>
                    <div className="flex items-center gap-3 mb-4">
                      <div className={`w-10 h-10 rounded-xl ${category.color} flex items-center justify-center`}>
                        <CategoryIcon className="h-5 w-5 text-white" />
                      </div>
                      <div>
                        <h3 className="font-bold text-lg">{isRTL ? category.title_ar : category.title_en}</h3>
                        <p className="text-sm text-muted-foreground">
                          {category.count} {t('rules')}
                        </p>
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {categoryRules.map((rule) => (
                        <Card 
                          key={rule.id}
                          className="card-nassaq"
                        >
                          <CardContent className="p-4">
                            <div className="flex items-start justify-between mb-2">
                              <h4 className="font-bold">{isRTL ? rule.name_ar : rule.name_en}</h4>
                              {getStatusBadge(rule.status)}
                            </div>
                            <p className="text-sm text-muted-foreground mb-3 line-clamp-2">
                              {isRTL ? rule.description_ar : rule.description_en}
                            </p>
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-brand-navy">{formatValue(rule)}</span>
                              <Button variant="ghost" size="sm" onClick={() => openEdit(rule)}>
                                <Edit className="h-4 w-4 me-1" />
                                {t('edit')}
                              </Button>
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </div>
                );
              })}
            </TabsContent>
          </Tabs>
        </main>
        
        {/* Create Rule Dialog */}
        <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Plus className="h-5 w-5 text-brand-navy" />
                {t('createRule')}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>{t('ruleName')} (عربي)</Label>
                  <Input 
                    value={formData.name_ar}
                    onChange={(e) => setFormData({ ...formData, name_ar: e.target.value })}
                    placeholder="اسم القاعدة بالعربية"
                  />
                </div>
                <div className="space-y-2">
                  <Label>{t('ruleName')} (English)</Label>
                  <Input 
                    value={formData.name_en}
                    onChange={(e) => setFormData({ ...formData, name_en: e.target.value })}
                    placeholder="Rule name in English"
                    dir="ltr"
                  />
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>{t('ruleCategory')}</Label>
                  <Select value={formData.category} onValueChange={(v) => setFormData({ ...formData, category: v })}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.entries(RULE_CATEGORIES).map(([key, cat]) => (
                        <SelectItem key={key} value={key}>
                          {isRTL ? cat.title_ar : cat.title_en}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>{t('ruleType')}</Label>
                  <Select value={formData.type} onValueChange={(v) => setFormData({ ...formData, type: v })}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Object.entries(RULE_TYPES).map(([key, type]) => (
                        <SelectItem key={key} value={key}>
                          {isRTL ? type.label_ar : type.label_en}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>{t('ruleValue')}</Label>
                  {formData.type === 'boolean' ? (
                    <Select 
                      value={formData.value?.toString()} 
                      onValueChange={(v) => setFormData({ ...formData, value: v === 'true' })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="true">{t('yes')}</SelectItem>
                        <SelectItem value="false">{t('no')}</SelectItem>
                      </SelectContent>
                    </Select>
                  ) : (
                    <Input 
                      type={formData.type === 'numeric' || formData.type === 'percentage' ? 'number' : 'text'}
                      value={formData.value}
                      onChange={(e) => setFormData({ ...formData, value: e.target.value })}
                    />
                  )}
                </div>
                <div className="space-y-2">
                  <Label>{t('priority')}</Label>
                  <Select value={formData.priority} onValueChange={(v) => setFormData({ ...formData, priority: v })}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="high">{t('high')}</SelectItem>
                      <SelectItem value="medium">{t('medium')}</SelectItem>
                      <SelectItem value="low">{t('low')}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              
              <div className="space-y-2">
                <Label>{t('ruleDescription')} (عربي)</Label>
                <Textarea 
                  value={formData.description_ar}
                  onChange={(e) => setFormData({ ...formData, description_ar: e.target.value })}
                  placeholder="وصف القاعدة بالعربية"
                  rows={2}
                />
              </div>
            </div>
            <DialogFooter className="flex-row-reverse gap-2">
              <Button variant="outline" onClick={() => { setShowCreateDialog(false); resetForm(); }}>
                {t('cancel')}
              </Button>
              <Button onClick={handleCreateRule} className="bg-brand-navy">
                <Plus className="h-4 w-4 me-2" />
                {t('create')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Edit Sheet */}
        <Sheet open={!!showEditSheet} onOpenChange={() => { setShowEditSheet(null); resetForm(); }}>
          <SheetContent side={isRTL ? 'left' : 'right'} className="w-[400px] sm:w-[540px] overflow-y-auto">
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2">
                <Edit className="h-5 w-5 text-brand-navy" />
                {t('editRule')}
              </SheetTitle>
            </SheetHeader>
            <div className="space-y-4 py-6">
              <div className="space-y-2">
                <Label>{t('ruleName')} (عربي)</Label>
                <Input 
                  value={formData.name_ar}
                  onChange={(e) => setFormData({ ...formData, name_ar: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <Label>{t('ruleName')} (English)</Label>
                <Input 
                  value={formData.name_en}
                  onChange={(e) => setFormData({ ...formData, name_en: e.target.value })}
                  dir="ltr"
                />
              </div>
              <div className="space-y-2">
                <Label>{t('ruleValue')}</Label>
                {formData.type === 'boolean' ? (
                  <Select 
                    value={formData.value?.toString()} 
                    onValueChange={(v) => setFormData({ ...formData, value: v === 'true' })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="true">{t('yes')}</SelectItem>
                      <SelectItem value="false">{t('no')}</SelectItem>
                    </SelectContent>
                  </Select>
                ) : (
                  <Input 
                    type={formData.type === 'numeric' || formData.type === 'percentage' ? 'number' : 'text'}
                    value={formData.value}
                    onChange={(e) => setFormData({ ...formData, value: e.target.value })}
                  />
                )}
              </div>
              <div className="space-y-2">
                <Label>{t('ruleStatus')}</Label>
                <Select value={formData.status} onValueChange={(v) => setFormData({ ...formData, status: v })}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">{t('active')}</SelectItem>
                    <SelectItem value="draft">{t('draft')}</SelectItem>
                    <SelectItem value="disabled">{t('disabled')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>{t('priority')}</Label>
                <Select value={formData.priority} onValueChange={(v) => setFormData({ ...formData, priority: v })}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="high">{t('high')}</SelectItem>
                    <SelectItem value="medium">{t('medium')}</SelectItem>
                    <SelectItem value="low">{t('low')}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>{t('ruleDescription')}</Label>
                <Textarea 
                  value={formData.description_ar}
                  onChange={(e) => setFormData({ ...formData, description_ar: e.target.value })}
                  rows={3}
                />
              </div>
              
              <div className="flex gap-2 pt-4">
                <Button onClick={handleEditRule} className="flex-1 bg-brand-navy">
                  <Save className="h-4 w-4 me-2" />
                  {t('save')}
                </Button>
                <Button 
                  variant="outline" 
                  className="text-red-600 hover:bg-red-50"
                  onClick={() => { setShowDeleteDialog(showEditSheet); setShowEditSheet(null); }}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </SheetContent>
        </Sheet>
        
        {/* View Sheet */}
        <Sheet open={!!showViewSheet} onOpenChange={() => setShowViewSheet(null)}>
          <SheetContent side={isRTL ? 'left' : 'right'} className="w-[400px] sm:w-[540px] overflow-y-auto">
            {showViewSheet && (
              <>
                <SheetHeader>
                  <SheetTitle>{isRTL ? showViewSheet.name_ar : showViewSheet.name_en}</SheetTitle>
                  <SheetDescription>
                    {isRTL ? showViewSheet.description_ar : showViewSheet.description_en}
                  </SheetDescription>
                </SheetHeader>
                <div className="space-y-6 py-6">
                  <div className="p-4 bg-brand-navy/5 rounded-xl text-center">
                    <p className="text-sm text-muted-foreground mb-1">{t('ruleValue')}</p>
                    <p className="text-4xl font-bold text-brand-navy">{formatValue(showViewSheet)}</p>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-3 bg-muted/30 rounded-lg">
                      <p className="text-sm text-muted-foreground">{t('ruleStatus')}</p>
                      <div className="mt-1">{getStatusBadge(showViewSheet.status)}</div>
                    </div>
                    <div className="p-3 bg-muted/30 rounded-lg">
                      <p className="text-sm text-muted-foreground">{t('priority')}</p>
                      <div className="mt-1">{getPriorityBadge(showViewSheet.priority)}</div>
                    </div>
                  </div>
                  
                  <div className="p-3 bg-muted/30 rounded-lg">
                    <p className="text-sm text-muted-foreground">{t('ruleCategory')}</p>
                    <p className="font-medium mt-1">
                      {isRTL 
                        ? getCategoryInfo(showViewSheet.category).title_ar 
                        : getCategoryInfo(showViewSheet.category).title_en}
                    </p>
                  </div>
                  
                  <div className="flex gap-2">
                    <Button onClick={() => { openEdit(showViewSheet); setShowViewSheet(null); }} className="flex-1">
                      <Edit className="h-4 w-4 me-2" />
                      {t('edit')}
                    </Button>
                    <Button variant="outline" onClick={() => handleDuplicateRule(showViewSheet)}>
                      <Copy className="h-4 w-4 me-2" />
                      {t('duplicate')}
                    </Button>
                  </div>
                </div>
              </>
            )}
          </SheetContent>
        </Sheet>
        
        {/* Delete Dialog */}
        <Dialog open={!!showDeleteDialog} onOpenChange={() => setShowDeleteDialog(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2 text-red-600">
                <Trash2 className="h-5 w-5" />
                {t('delete')}
              </DialogTitle>
              <DialogDescription>
                {t('deleteConfirm')}
                <br />
                <strong className="text-red-600">{t('deleteWarning')}</strong>
              </DialogDescription>
            </DialogHeader>
            <DialogFooter className="flex-row-reverse gap-2">
              <Button variant="outline" onClick={() => setShowDeleteDialog(null)}>{t('cancel')}</Button>
              <Button variant="destructive" onClick={handleDeleteRule}>
                <Trash2 className="h-4 w-4 me-2" />
                {t('delete')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Sidebar>
  );
};

export default RulesManagementPage;
