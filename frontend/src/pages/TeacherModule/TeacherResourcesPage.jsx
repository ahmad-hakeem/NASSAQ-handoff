import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Label } from '../../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Progress } from '../../components/ui/progress';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  BookOpen, FileText, Plus, Upload, Download, Loader2, RefreshCw,
  Video, File, Image, Link2, Trash2, Edit2, Eye, FolderOpen, Search
} from 'lucide-react';
import { HakimAssistant } from '../../components/hakim/HakimAssistant';

import { useTranslation } from '../../contexts/ThemeContext';
const RESOURCE_TYPES = [
  { value: 'document', label: 'مستند', labelEn: 'Document', icon: FileText },
  { value: 'video', label: 'فيديو', labelEn: 'Video', icon: Video },
  { value: 'image', label: 'صورة', labelEn: 'Image', icon: Image },
  { value: 'link', label: 'رابط', labelEn: 'Link', icon: Link2 },
  { value: 'other', label: 'أخرى', labelEn: 'Other', icon: File },
];

export default function TeacherResourcesPage() {
  const { t } = useTranslation();
  const { user, api, isRTL } = useAuth();
  const [loading, setLoading] = useState(true);
  const [classes, setClasses] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [resources, setResources] = useState([]);
  const [selectedClass, setSelectedClass] = useState('');
  const [selectedSubject, setSelectedSubject] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('all');
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [saving, setSaving] = useState(false);

  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const [newResource, setNewResource] = useState({
    title: '',
    description: '',
    type: 'document',
    url: '',
    class_ids: [],
    subject_id: ''
  });

  const teacherId = user?.teacher_id || user?.id;

  const fetchData = useCallback(async () => {
    if (!teacherId) return;
    
    setLoading(true);
    try {
      const [classesRes, resourcesRes] = await Promise.all([
        api.get(`/teacher/classes/${teacherId}`).catch(() => ({ data: [] })),
        api.get(`/resources?teacher_id=${teacherId}`).catch(() => ({ data: [] }))
      ]);
      
      setClasses(classesRes.data || []);
      setResources(resourcesRes.data || []);
      
      // Extract unique subjects from classes
      const allSubjects = [...new Set(classesRes.data?.flatMap(c => c.subjects || []))];
      setSubjects(allSubjects.map((s, i) => ({ id: `sub-${i}`, name: s })));
      
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  }, [api, teacherId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleAddResource = async () => {
    if (!newResource.title) {
      nassaqError(t('pleaseEnterResourceTitle'));
      return;
    }

    setSaving(true);
    try {
      await api.post('/resources', {
        ...newResource,
        teacher_id: teacherId,
        created_at: new Date().toISOString()
      });

      toast.success(t('resourceAddedSuccessfully'));
      setShowAddDialog(false);
      setNewResource({
        title: '',
        description: '',
        type: 'document',
        url: '',
        class_ids: [],
        subject_id: ''
      });
      fetchData();
    } catch (error) {
      nassaqError(t('errorAddingResource'));
    } finally {
      setSaving(false);
    }
  };

  const deleteResource = async (resourceId) => {
    if (!confirm(t('areYouSureYouWantToDeleteThisResource'))) {
      return;
    }

    try {
      await api.delete(`/resources/${resourceId}`);
      toast.success(t('resourceDeleted'));
      fetchData();
    } catch (error) {
      nassaqError(t('errorDeleting'));
    }
  };

  const filteredResources = resources.filter(r => {
    const matchesSearch = r.title?.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         r.description?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesType = activeTab === 'all' || r.type === activeTab;
    const matchesClass = !selectedClass || r.class_ids?.includes(selectedClass);
    const matchesSubject = !selectedSubject || r.subject_id === selectedSubject;
    
    return matchesSearch && matchesType && matchesClass && matchesSubject;
  });

  const getResourceIcon = (type) => {
    const resourceType = RESOURCE_TYPES.find(rt => rt.value === type);
    return resourceType?.icon || File;
  };

  const getResourceColor = (type) => {
    switch (type) {
      case 'document': return 'bg-blue-100 text-blue-600';
      case 'video': return 'bg-red-100 text-red-600';
      case 'image': return 'bg-green-100 text-green-600';
      case 'link': return 'bg-purple-100 text-purple-600';
      default: return 'bg-gray-100 text-gray-600';
    }
  };

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800" dir={isRTL ? 'rtl' : 'ltr'}>
        {/* Header */}
        <div className="sticky top-0 z-20 bg-white/90 dark:bg-gray-900/90 backdrop-blur-sm border-b p-4">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-2xl font-bold text-brand-navy dark:text-brand-turquoise font-cairo">
                {t('educationalResources')}
              </h1>
              <p className="text-sm text-muted-foreground">
                {t('manageAndShareEducationalResources')}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={fetchData} disabled={loading}>
                <RefreshCw className={`h-4 w-4 me-1 ${loading ? 'animate-spin' : ''}`} />
              </Button>
              <Button 
                className="bg-brand-turquoise hover:bg-brand-turquoise/90"
                onClick={() => setShowAddDialog(true)}
              >
                <Plus className="h-4 w-4 me-1" />
                {t('addResource')}
              </Button>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="p-4 border-b bg-muted/30">
          <div className="flex flex-wrap gap-4">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder={t('searchResources')}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="ps-9"
              />
            </div>
            <Select value={selectedClass} onValueChange={setSelectedClass}>
              <SelectTrigger className="w-full sm:w-[150px]">
                <SelectValue placeholder={t('allClasses')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">{t('allClasses')}</SelectItem>
                {classes.map(cls => (
                  <SelectItem key={cls.id} value={cls.id}>{cls.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={selectedSubject} onValueChange={setSelectedSubject}>
              <SelectTrigger className="w-full sm:w-[150px]">
                <SelectValue placeholder={t('allSubjects')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="">{t('allSubjects')}</SelectItem>
                {subjects.map(sub => (
                  <SelectItem key={sub.id} value={sub.id}>{sub.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Content */}
        <div className="p-4">
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="mb-4">
              <TabsTrigger value="all">{t('all')}</TabsTrigger>
              {RESOURCE_TYPES.map(type => (
                <TabsTrigger key={type.value} value={type.value}>
                  <type.icon className="h-4 w-4 me-1" />
                  {isRTL ? type.label : type.labelEn}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
            </div>
          ) : filteredResources.length === 0 ? (
            <Card>
              <CardContent className="text-center py-16">
                <FolderOpen className="h-16 w-16 mx-auto mb-4 text-muted-foreground/30" />
                <h3 className="font-bold mb-2">{t('noResources')}</h3>
                <p className="text-muted-foreground mb-4">
                  {t('startByAddingEducationalResources')}
                </p>
                <Button onClick={() => setShowAddDialog(true)}>
                  <Plus className="h-4 w-4 me-1" />
                  {t('addResource')}
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredResources.map((resource) => {
                const Icon = getResourceIcon(resource.type);
                return (
                  <Card key={resource.id} className="hover:shadow-md transition-all" data-testid={`resource-${resource.id}`}>
                    <CardContent className="p-4">
                      <div className="flex items-start gap-3 mb-3">
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${getResourceColor(resource.type)}`}>
                          <Icon className="h-5 w-5" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <h3 className="font-medium truncate">{resource.title}</h3>
                          <p className="text-xs text-muted-foreground">
                            {RESOURCE_TYPES.find(rt => rt.value === resource.type)?.[isRTL ? 'label' : 'labelEn']}
                          </p>
                        </div>
                      </div>
                      
                      {resource.description && (
                        <p className="text-sm text-muted-foreground mb-3 line-clamp-2">
                          {resource.description}
                        </p>
                      )}

                      <div className="flex items-center gap-2 mb-3">
                        {resource.class_ids?.length > 0 && (
                          <Badge variant="outline" className="text-xs">
                            {resource.class_ids.length} {isRTL ? 'فصل' : 'classes'}
                          </Badge>
                        )}
                        {resource.subject_id && (
                          <Badge variant="secondary" className="text-xs">
                            {subjects.find(s => s.id === resource.subject_id)?.name || resource.subject_id}
                          </Badge>
                        )}
                      </div>

                      <div className="flex gap-2 pt-2 border-t">
                        {resource.url && (
                          <Button 
                            variant="outline" 
                            size="sm" 
                            className="flex-1"
                            onClick={() => window.open(resource.url, '_blank')}
                          >
                            <Eye className="h-3.5 w-3.5 me-1" />
                            {t('view2')}
                          </Button>
                        )}
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={() => deleteResource(resource.id)}
                        >
                          <Trash2 className="h-3.5 w-3.5 text-red-500" />
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}

          {/* Stats */}
          {!loading && resources.length > 0 && (
            <div className="grid grid-cols-3 sm:grid-cols-5 gap-3 sm:gap-4 mt-6">
              <Card>
                <CardContent className="p-4 text-center">
                  <FolderOpen className="h-6 w-6 mx-auto mb-1 text-brand-navy" />
                  <div className="text-xl font-bold">{resources.length}</div>
                  <div className="text-xs text-muted-foreground">{t('total5')}</div>
                </CardContent>
              </Card>
              {RESOURCE_TYPES.slice(0, 4).map(type => (
                <Card key={type.value}>
                  <CardContent className="p-4 text-center">
                    <type.icon className="h-6 w-6 mx-auto mb-1 text-muted-foreground" />
                    <div className="text-xl font-bold">
                      {resources.filter(r => r.type === type.value).length}
                    </div>
                    <div className="text-xs text-muted-foreground">{isRTL ? type.label : type.labelEn}</div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>

        {/* Add Resource Dialog */}
        <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
          <DialogContent className="w-[95vw] max-w-lg">
            <DialogHeader>
              <DialogTitle className="font-cairo">{t('addNewResource')}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>{t('resourceTitle')} *</Label>
                <Input
                  value={newResource.title}
                  onChange={(e) => setNewResource({...newResource, title: e.target.value})}
                  placeholder={t('egChapter1Summary')}
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>{t('resourceType')}</Label>
                  <Select 
                    value={newResource.type} 
                    onValueChange={(v) => setNewResource({...newResource, type: v})}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {RESOURCE_TYPES.map(type => (
                        <SelectItem key={type.value} value={type.value}>
                          {isRTL ? type.label : type.labelEn}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>{t('subject')}</Label>
                  <Select 
                    value={newResource.subject_id} 
                    onValueChange={(v) => setNewResource({...newResource, subject_id: v})}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={t('select2')} />
                    </SelectTrigger>
                    <SelectContent>
                      {subjects.map(sub => (
                        <SelectItem key={sub.id} value={sub.id}>{sub.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label>{t('linkUrl')}</Label>
                <Input
                  value={newResource.url}
                  onChange={(e) => setNewResource({...newResource, url: e.target.value})}
                  placeholder="https://..."
                  dir="ltr"
                />
              </div>

              <div className="space-y-2">
                <Label>{t('description')}</Label>
                <Textarea
                  value={newResource.description}
                  onChange={(e) => setNewResource({...newResource, description: e.target.value})}
                  placeholder={t('resourceDescription')}
                  rows={3}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowAddDialog(false)}>
                {t('cancel')}
              </Button>
              <Button onClick={handleAddResource} disabled={saving}>
                {saving && <Loader2 className="h-4 w-4 animate-spin me-2" />}
                {t('add')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
      <HakimAssistant />
    </Sidebar>
  );
}
