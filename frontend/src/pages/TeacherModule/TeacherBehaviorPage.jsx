import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Label } from '../../components/ui/label';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/avatar';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  Heart, ThumbsUp, ThumbsDown, AlertTriangle, Award, Plus,
  Search, Loader2, RefreshCw, Users, Star, TrendingUp, Filter
} from 'lucide-react';
import { HakimAssistant } from '../../components/hakim/HakimAssistant';

import { useTranslation } from '../../contexts/ThemeContext';
const BEHAVIOR_TYPES = {
  positive: { label: 'إيجابي', labelEn: 'Positive', color: 'bg-green-100 text-green-700 border-green-300', icon: ThumbsUp },
  negative: { label: 'سلبي', labelEn: 'Negative', color: 'bg-red-100 text-red-700 border-red-300', icon: ThumbsDown },
  warning: { label: 'تحذير', labelEn: 'Warning', color: 'bg-amber-100 text-amber-700 border-amber-300', icon: AlertTriangle },
  achievement: { label: 'إنجاز', labelEn: 'Achievement', color: 'bg-blue-100 text-blue-700 border-blue-300', icon: Award },
};

const PREDEFINED_BEHAVIORS = {
  positive: [
    { id: 'p1', label: 'مشاركة فعالة', points: 5 },
    { id: 'p2', label: 'مساعدة زملائه', points: 3 },
    { id: 'p3', label: 'التزام بالقواعد', points: 2 },
    { id: 'p4', label: 'إبداع وتميز', points: 10 },
    { id: 'p5', label: 'تحسن ملحوظ', points: 5 },
  ],
  negative: [
    { id: 'n1', label: 'عدم الانتباه', points: -2 },
    { id: 'n2', label: 'إزعاج الآخرين', points: -3 },
    { id: 'n3', label: 'عدم إحضار الأدوات', points: -1 },
    { id: 'n4', label: 'تأخر عن الحصة', points: -2 },
    { id: 'n5', label: 'عدم أداء الواجب', points: -5 },
  ],
};

export default function TeacherBehaviorPage() {
  const { t } = useTranslation();
  const { user, api, isRTL } = useAuth();
  const [loading, setLoading] = useState(true);
  const [classes, setClasses] = useState([]);
  const [students, setStudents] = useState([]);
  const [records, setRecords] = useState([]);
  const [selectedClass, setSelectedClass] = useState('');
  const [selectedStudent, setSelectedStudent] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('record');
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [saving, setSaving] = useState(false);

  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const [newRecord, setNewRecord] = useState({
    type: 'positive',
    predefined_id: '',
    custom_note: '',
    points: 0
  });

  const teacherId = user?.teacher_id || user?.id;

  const fetchData = useCallback(async () => {
    if (!teacherId) return;
    
    setLoading(true);
    try {
      const classesRes = await api.get(`/teacher/classes/${teacherId}`).catch(() => ({ data: [] }));
      setClasses(classesRes.data || []);
      
      if (classesRes.data?.length > 0 && !selectedClass) {
        setSelectedClass(classesRes.data[0].id);
      }
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  }, [api, teacherId, selectedClass]);

  const fetchStudents = useCallback(async () => {
    if (!selectedClass) return;
    
    try {
      const [studentsRes, recordsRes] = await Promise.all([
        api.get(`/classes/${selectedClass}/students`).catch(() => ({ data: [] })),
        api.get(`/behavior?class_id=${selectedClass}`).catch(() => ({ data: [] }))
      ]);
      
      setStudents(studentsRes.data || []);
      setRecords(recordsRes.data || []);
    } catch (error) {
      console.error('Error:', error);
    }
  }, [api, selectedClass]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    if (selectedClass) {
      fetchStudents();
    }
  }, [selectedClass, fetchStudents]);

  const handleAddRecord = async () => {
    if (!selectedStudent) {
      nassaqError(t('pleaseSelectAStudent'));
      return;
    }

    setSaving(true);
    try {
      const predefined = [...PREDEFINED_BEHAVIORS.positive, ...PREDEFINED_BEHAVIORS.negative]
        .find(b => b.id === newRecord.predefined_id);
      
      await api.post('/behavior', {
        student_id: selectedStudent.id,
        class_id: selectedClass,
        teacher_id: teacherId,
        type: newRecord.type,
        note: predefined?.label || newRecord.custom_note,
        points: predefined?.points || newRecord.points,
        date: new Date().toISOString().split('T')[0]
      });

      toast.success(t('behaviorRecorded'));
      setShowAddDialog(false);
      setNewRecord({ type: 'positive', predefined_id: '', custom_note: '', points: 0 });
      fetchStudents();
    } catch (error) {
      nassaqError(t('errorRecording'));
    } finally {
      setSaving(false);
    }
  };

  const quickAddBehavior = async (student, behavior) => {
    try {
      await api.post('/behavior', {
        student_id: student.id,
        class_id: selectedClass,
        teacher_id: teacherId,
        type: behavior.points > 0 ? 'positive' : 'negative',
        note: behavior.label,
        points: behavior.points,
        date: new Date().toISOString().split('T')[0]
      });
      toast.success(t('recorded'));
      fetchStudents();
    } catch (error) {
      nassaqError(t('error'));
    }
  };

  const getStudentPoints = (studentId) => {
    return records
      .filter(r => r.student_id === studentId)
      .reduce((sum, r) => sum + (r.points || 0), 0);
  };

  const filteredStudents = students.filter(s => 
    s.full_name?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800" dir={isRTL ? 'rtl' : 'ltr'}>
        {/* Header */}
        <div className="sticky top-0 z-20 bg-white/90 dark:bg-gray-900/90 backdrop-blur-sm border-b p-4">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-2xl font-bold text-brand-navy dark:text-brand-turquoise font-cairo">
                {t('behaviorTracking')}
              </h1>
              <p className="text-sm text-muted-foreground">
                {t('trackAndRecordStudentBehavior')}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Select value={selectedClass} onValueChange={setSelectedClass}>
                <SelectTrigger className="w-[180px]" data-testid="class-select">
                  <SelectValue placeholder={t('selectClass')} />
                </SelectTrigger>
                <SelectContent>
                  {classes.map(cls => (
                    <SelectItem key={cls.id} value={cls.id}>{cls.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button variant="outline" size="sm" onClick={fetchStudents} disabled={loading}>
                <RefreshCw className={`h-4 w-4 me-1 ${loading ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-4">
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="mb-4">
              <TabsTrigger value="record" data-testid="record-tab">
                {t('quickRecord')}
              </TabsTrigger>
              <TabsTrigger value="history" data-testid="history-tab">
                {t('history')}
              </TabsTrigger>
              <TabsTrigger value="stats" data-testid="stats-tab">
                {t('statistics2')}
              </TabsTrigger>
            </TabsList>

            {/* Quick Record Tab */}
            <TabsContent value="record">
              {/* Search */}
              <div className="mb-4">
                <div className="relative">
                  <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder={isRTL ? 'بحث عن طالب...' : 'Search student...'}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="ps-9"
                  />
                </div>
              </div>

              {loading ? (
                <div className="flex items-center justify-center py-20">
                  <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
                </div>
              ) : filteredStudents.length === 0 ? (
                <Card>
                  <CardContent className="text-center py-16">
                    <Users className="h-16 w-16 mx-auto mb-4 text-muted-foreground/30" />
                    <p className="text-muted-foreground">
                      {isRTL ? 'لا يوجد طلاب' : 'No students found'}
                    </p>
                  </CardContent>
                </Card>
              ) : (
                <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {filteredStudents.map((student, idx) => {
                    const points = getStudentPoints(student.id);
                    return (
                      <Card key={student.id} className="hover:shadow-md transition-all" data-testid={`student-${student.id}`}>
                        <CardContent className="p-4">
                          <div className="flex items-center gap-3 mb-3">
                            <Avatar>
                              <AvatarImage src={student.avatar_url} />
                              <AvatarFallback className="bg-brand-navy text-white">
                                {student.full_name?.charAt(0) || (idx + 1)}
                              </AvatarFallback>
                            </Avatar>
                            <div className="flex-1 min-w-0">
                              <p className="font-medium truncate">{student.full_name || `طالب ${idx + 1}`}</p>
                              <div className="flex items-center gap-2">
                                <Badge variant={points >= 0 ? 'default' : 'destructive'} className="text-xs">
                                  <Star className="h-3 w-3 me-1" />
                                  {points} {isRTL ? 'نقطة' : 'pts'}
                                </Badge>
                              </div>
                            </div>
                          </div>

                          {/* Quick Actions */}
                          <div className="space-y-2">
                            <div className="flex gap-1 flex-wrap">
                              {PREDEFINED_BEHAVIORS.positive.slice(0, 3).map(b => (
                                <Button
                                  key={b.id}
                                  variant="outline"
                                  size="sm"
                                  className="text-xs bg-green-50 hover:bg-green-100 hover:text-green-700 text-green-700 border-green-200"
                                  onClick={() => quickAddBehavior(student, b)}
                                >
                                  <ThumbsUp className="h-3 w-3 me-1" />
                                  {b.label}
                                </Button>
                              ))}
                            </div>
                            <div className="flex gap-1 flex-wrap">
                              {PREDEFINED_BEHAVIORS.negative.slice(0, 3).map(b => (
                                <Button
                                  key={b.id}
                                  variant="outline"
                                  size="sm"
                                  className="text-xs bg-red-50 hover:bg-red-100 hover:text-red-700 text-red-700 border-red-200"
                                  onClick={() => quickAddBehavior(student, b)}
                                >
                                  <ThumbsDown className="h-3 w-3 me-1" />
                                  {b.label}
                                </Button>
                              ))}
                            </div>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="w-full text-xs"
                              onClick={() => {
                                setSelectedStudent(student);
                                setShowAddDialog(true);
                              }}
                            >
                              <Plus className="h-3 w-3 me-1" />
                              {t('customNote')}
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              )}
            </TabsContent>

            {/* History Tab */}
            <TabsContent value="history">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg font-cairo">
                    {t('behaviorRecords')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {records.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                      {t('noRecords')}
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {records.slice(0, 20).map((record, idx) => {
                        const student = students.find(s => s.id === record.student_id);
                        const typeInfo = BEHAVIOR_TYPES[record.type] || BEHAVIOR_TYPES.positive;
                        return (
                          <div
                            key={record.id || idx}
                            className={`p-3 rounded-lg border-2 ${typeInfo.color}`}
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <typeInfo.icon className="h-4 w-4" />
                                <span className="font-medium">{student?.full_name || 'طالب'}</span>
                              </div>
                              <Badge variant="outline">
                                {record.points > 0 ? '+' : ''}{record.points}
                              </Badge>
                            </div>
                            <p className="text-sm mt-1">{record.note}</p>
                            <p className="text-xs text-muted-foreground mt-1">
                              {new Date(record.date).toLocaleDateString('ar-SA')}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Statistics Tab */}
            <TabsContent value="stats">
              <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                <Card className="bg-gradient-to-br from-green-50 to-white">
                  <CardContent className="p-4 text-center">
                    <ThumbsUp className="h-8 w-8 mx-auto mb-2 text-green-600" />
                    <div className="text-2xl font-bold text-green-700">
                      {records.filter(r => r.type === 'positive').length}
                    </div>
                    <div className="text-sm text-muted-foreground">{t('positive2')}</div>
                  </CardContent>
                </Card>
                <Card className="bg-gradient-to-br from-red-50 to-white">
                  <CardContent className="p-4 text-center">
                    <ThumbsDown className="h-8 w-8 mx-auto mb-2 text-red-600" />
                    <div className="text-2xl font-bold text-red-700">
                      {records.filter(r => r.type === 'negative').length}
                    </div>
                    <div className="text-sm text-muted-foreground">{t('negative2')}</div>
                  </CardContent>
                </Card>
                <Card className="bg-gradient-to-br from-amber-50 to-white">
                  <CardContent className="p-4 text-center">
                    <AlertTriangle className="h-8 w-8 mx-auto mb-2 text-amber-600" />
                    <div className="text-2xl font-bold text-amber-700">
                      {records.filter(r => r.type === 'warning').length}
                    </div>
                    <div className="text-sm text-muted-foreground">{t('warnings')}</div>
                  </CardContent>
                </Card>
                <Card className="bg-gradient-to-br from-blue-50 to-white">
                  <CardContent className="p-4 text-center">
                    <TrendingUp className="h-8 w-8 mx-auto mb-2 text-blue-600" />
                    <div className="text-2xl font-bold text-blue-700">
                      {records.reduce((sum, r) => sum + (r.points || 0), 0)}
                    </div>
                    <div className="text-sm text-muted-foreground">{t('totalPoints2')}</div>
                  </CardContent>
                </Card>
              </div>

              {/* Top Students */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg font-cairo flex items-center gap-2">
                    <Award className="h-5 w-5 text-amber-500" />
                    {t('topStudents')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {students
                      .map(s => ({ ...s, points: getStudentPoints(s.id) }))
                      .sort((a, b) => b.points - a.points)
                      .slice(0, 5)
                      .map((student, idx) => (
                        <div key={student.id} className="flex items-center gap-3 p-2 rounded-lg bg-muted/30">
                          <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold ${
                            idx === 0 ? 'bg-amber-400 text-white' :
                            idx === 1 ? 'bg-gray-300 text-gray-700' :
                            idx === 2 ? 'bg-amber-600 text-white' :
                            'bg-muted text-muted-foreground'
                          }`}>
                            {idx + 1}
                          </div>
                          <div className="flex-1">
                            <p className="font-medium">{student.full_name}</p>
                          </div>
                          <Badge variant={student.points >= 0 ? 'default' : 'destructive'}>
                            {student.points} {isRTL ? 'نقطة' : 'pts'}
                          </Badge>
                        </div>
                      ))}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>

        {/* Add Custom Record Dialog */}
        <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="font-cairo">
                {t('addBehaviorNote')}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              {selectedStudent && (
                <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/30">
                  <Avatar>
                    <AvatarFallback>{selectedStudent.full_name?.charAt(0)}</AvatarFallback>
                  </Avatar>
                  <div>
                    <p className="font-medium">{selectedStudent.full_name}</p>
                  </div>
                </div>
              )}
              
              <div className="space-y-2">
                <Label>{t('behaviorType')}</Label>
                <Select value={newRecord.type} onValueChange={(v) => setNewRecord({...newRecord, type: v})}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(BEHAVIOR_TYPES).map(([key, value]) => (
                      <SelectItem key={key} value={key}>
                        {isRTL ? value.label : value.labelEn}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>{t('note3')}</Label>
                <Textarea
                  value={newRecord.custom_note}
                  onChange={(e) => setNewRecord({...newRecord, custom_note: e.target.value})}
                  placeholder={t('writeNote')}
                  rows={3}
                />
              </div>

              <div className="space-y-2">
                <Label>{t('points2')}</Label>
                <Input
                  type="number"
                  value={newRecord.points}
                  onChange={(e) => setNewRecord({...newRecord, points: parseInt(e.target.value) || 0})}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowAddDialog(false)}>
                {t('cancel')}
              </Button>
              <Button onClick={handleAddRecord} disabled={saving}>
                {saving && <Loader2 className="h-4 w-4 animate-spin me-2" />}
                {t('save')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
      <HakimAssistant />
    </Sidebar>
  );
}
