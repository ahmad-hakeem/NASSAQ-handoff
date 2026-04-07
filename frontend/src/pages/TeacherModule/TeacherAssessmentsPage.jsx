import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  FileText, Plus, Edit2, Trash2, Eye, Loader2, RefreshCw,
  GraduationCap, ClipboardList, Save, CheckCircle2, Clock, BookOpen
} from 'lucide-react';
import { HakimAssistant } from '../../components/hakim/HakimAssistant';

import { useTranslation } from '../../contexts/ThemeContext';
const ASSESSMENT_TYPES = [
  { value: 'exam', label: 'اختبار', labelEn: 'Exam' },
  { value: 'quiz', label: 'اختبار قصير', labelEn: 'Quiz' },
  { value: 'homework', label: 'واجب', labelEn: 'Homework' },
  { value: 'project', label: 'مشروع', labelEn: 'Project' },
  { value: 'participation', label: 'مشاركة', labelEn: 'Participation' },
];

export default function TeacherAssessmentsPage() {
  const { t } = useTranslation();
  const { user, api, isRTL } = useAuth();
  const [loading, setLoading] = useState(true);
  const [assessments, setAssessments] = useState([]);
  const [classes, setClasses] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [activeTab, setActiveTab] = useState('all');
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showGradeDialog, setShowGradeDialog] = useState(false);
  const [selectedAssessment, setSelectedAssessment] = useState(null);
  const [students, setStudents] = useState([]);
  const [grades, setGrades] = useState({});
  const [saving, setSaving] = useState(false);

  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const teacherId = user?.teacher_id || user?.id;

  const [newAssessment, setNewAssessment] = useState({
    title: '',
    assessment_type: 'exam',
    class_id: '',
    subject_id: '',
    max_score: 100,
    weight: 1,
    date: '',
    description: ''
  });

  const fetchData = useCallback(async () => {
    if (!teacherId) return;
    
    setLoading(true);
    try {
      const [assessmentsRes, classesRes, subjectsRes] = await Promise.all([
        api.get(`/teacher/assessments/${teacherId}`).catch(() => ({ data: [] })),
        api.get(`/teacher/classes/${teacherId}`).catch(() => ({ data: [] })),
        api.get('/subjects').catch(() => ({ data: [] }))
      ]);
      
      setAssessments(assessmentsRes.data || []);
      setClasses(classesRes.data || []);
      
      const allSubjects = Array.isArray(subjectsRes.data) ? subjectsRes.data : [];
      const subjectNames = [...new Set(classesRes.data?.flatMap(c => c.subjects || []))];
      const matchedSubjects = allSubjects.filter(s => subjectNames.includes(s.name));
      setSubjects(matchedSubjects.length > 0 ? matchedSubjects : allSubjects);
      
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  }, [api, teacherId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const createAssessment = async () => {
    if (!newAssessment.title || !newAssessment.class_id || !newAssessment.subject_id) {
      nassaqError(t('pleaseFillAllRequiredFields'));
      return;
    }
    
    setSaving(true);
    try {
      await api.post('/assessments', {
        title: newAssessment.title,
        assessment_type: newAssessment.assessment_type,
        class_id: newAssessment.class_id,
        subject_id: newAssessment.subject_id,
        max_score: Number(newAssessment.max_score) || 100,
        weight: Number(newAssessment.weight) || 1,
        date: newAssessment.date || new Date().toISOString().split('T')[0],
        description: newAssessment.description || undefined,
        is_published: false
      });
      toast.success(t('assessmentCreated'));
      setShowCreateDialog(false);
      setNewAssessment({
        title: '', assessment_type: 'exam', class_id: '', subject_id: '',
        max_score: 100, weight: 1, date: '', description: ''
      });
      fetchData();
    } catch (error) {
      console.error('Error creating assessment:', error?.response?.data || error);
      nassaqError(t('errorCreatingAssessment'));
    } finally {
      setSaving(false);
    }
  };

  const openGradeEntry = async (assessment) => {
    setSelectedAssessment(assessment);
    try {
      const studentsRes = await api.get(`/classes/${assessment.class_id}/students`);
      setStudents(studentsRes.data || []);
      
      // Fetch existing grades
      const gradesRes = await api.get(`/assessments/${assessment.id}/grades`).catch(() => ({ data: [] }));
      const existingGrades = {};
      gradesRes.data?.forEach(g => {
        existingGrades[g.student_id] = { score: g.score, notes: g.notes };
      });
      setGrades(existingGrades);
      
      setShowGradeDialog(true);
    } catch (error) {
      nassaqError(t('errorLoadingStudents'));
    }
  };

  const saveGrades = async () => {
    setSaving(true);
    try {
      const gradeEntries = Object.entries(grades).map(([studentId, data]) => ({
        student_id: studentId,
        assessment_id: selectedAssessment.id,
        score: data.score,
        notes: data.notes
      }));
      
      await api.post(`/assessments/${selectedAssessment.id}/grades`, { grades: gradeEntries });
      toast.success(t('gradesSaved'));
      setShowGradeDialog(false);
      fetchData();
    } catch (error) {
      nassaqError(t('errorSavingGrades'));
    } finally {
      setSaving(false);
    }
  };

  const filteredAssessments = assessments.filter(a => {
    if (activeTab === 'all') return true;
    if (activeTab === 'draft') return a.status === 'draft';
    if (activeTab === 'published') return a.status === 'published';
    if (activeTab === 'graded') return a.status === 'graded';
    return true;
  });

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800" dir={isRTL ? 'rtl' : 'ltr'}>
        {/* Header */}
        <div className="sticky top-0 z-20 bg-white/90 dark:bg-gray-900/90 backdrop-blur-sm border-b p-4">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-2xl font-bold text-brand-navy dark:text-brand-turquoise font-cairo">
                {t('assessmentsGrades')}
              </h1>
              <p className="text-sm text-muted-foreground">
                {t('createAssessmentsAndEnterGrades')}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={fetchData} disabled={loading}>
                <RefreshCw className={`h-4 w-4 me-1 ${loading ? 'animate-spin' : ''}`} />
                {t('refresh')}
              </Button>
              <Button 
                className="bg-brand-turquoise hover:bg-brand-turquoise/90"
                onClick={() => setShowCreateDialog(true)}
              >
                <Plus className="h-4 w-4 me-1" />
                {t('newAssessment')}
              </Button>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="p-4">
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="mb-4">
              <TabsTrigger value="all">{t('all')}</TabsTrigger>
              <TabsTrigger value="draft">{t('draft')}</TabsTrigger>
              <TabsTrigger value="published">{t('published')}</TabsTrigger>
              <TabsTrigger value="graded">{t('graded4')}</TabsTrigger>
            </TabsList>
          </Tabs>

          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
            </div>
          ) : filteredAssessments.length === 0 ? (
            <Card>
              <CardContent className="text-center py-16">
                <FileText className="h-16 w-16 mx-auto mb-4 text-muted-foreground/30" />
                <h3 className="font-bold mb-2">{t('noAssessments')}</h3>
                <p className="text-muted-foreground mb-4">
                  {t('startByCreatingANewAssessment')}
                </p>
                <Button onClick={() => setShowCreateDialog(true)}>
                  <Plus className="h-4 w-4 me-1" />
                  {t('newAssessment')}
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredAssessments.map((assessment) => (
                <Card key={assessment.id} className="hover:shadow-md transition-all" data-testid={`assessment-${assessment.id}`}>
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-2">
                        <div className="w-10 h-10 rounded-lg bg-brand-navy/10 flex items-center justify-center">
                          <ClipboardList className="h-5 w-5 text-brand-navy" />
                        </div>
                        <div>
                          <CardTitle className="text-base">{assessment.title || assessment.name}</CardTitle>
                          <p className="text-xs text-muted-foreground">
                            {ASSESSMENT_TYPES.find(at => at.value === (assessment.assessment_type || assessment.type))?.[isRTL ? 'label' : 'labelEn']}
                          </p>
                        </div>
                      </div>
                      <Badge variant={
                        assessment.status === 'published' ? 'default' :
                        assessment.status === 'graded' ? 'success' : 'secondary'
                      }>
                        {assessment.status === 'draft' ? (t('draft')) :
                         assessment.status === 'published' ? (t('published')) :
                         (t('graded4'))}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">{t('class')}</span>
                      <span className="font-medium">{assessment.class_name || '-'}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">{isRTL ? 'الدرجة' : 'Max Score'}</span>
                      <span className="font-medium">{assessment.max_score}</span>
                    </div>
                    {(assessment.date || assessment.due_date) && (
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">{t('date')}</span>
                        <span className="font-medium">{new Date(assessment.date || assessment.due_date).toLocaleDateString('ar-SA')}</span>
                      </div>
                    )}
                    
                    <div className="flex gap-2 pt-2 border-t">
                      <Button 
                        variant="outline" 
                        size="sm" 
                        className="flex-1"
                        onClick={() => openGradeEntry(assessment)}
                      >
                        <Edit2 className="h-3.5 w-3.5 me-1" />
                        {t('grades')}
                      </Button>
                      <Button variant="outline" size="sm">
                        <Eye className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>

        {/* Create Assessment Dialog */}
        <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
          <DialogContent className="w-[95vw] max-w-lg">
            <DialogHeader>
              <DialogTitle className="font-cairo">{t('createNewAssessment')}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>{t('assessmentName')} *</Label>
                <Input 
                  value={newAssessment.title}
                  onChange={(e) => setNewAssessment({...newAssessment, title: e.target.value})}
                  placeholder={t('egMidtermExam')}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>{t('type4')}</Label>
                  <Select value={newAssessment.assessment_type} onValueChange={(v) => setNewAssessment({...newAssessment, assessment_type: v})}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {ASSESSMENT_TYPES.map(at => (
                        <SelectItem key={at.value} value={at.value}>{isRTL ? at.label : at.labelEn}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>{t('class')} *</Label>
                  <Select value={newAssessment.class_id} onValueChange={(v) => setNewAssessment({...newAssessment, class_id: v})}>
                    <SelectTrigger><SelectValue placeholder={t('select2')} /></SelectTrigger>
                    <SelectContent>
                      {classes.map(c => (
                        <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>{t('subject')} *</Label>
                  <Select value={newAssessment.subject_id} onValueChange={(v) => setNewAssessment({...newAssessment, subject_id: v})}>
                    <SelectTrigger><SelectValue placeholder={isRTL ? 'اختر المادة' : 'Select Subject'} /></SelectTrigger>
                    <SelectContent>
                      {subjects.map(s => (
                        <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>{t('maxScore')}</Label>
                  <Input 
                    type="number"
                    value={newAssessment.max_score}
                    onChange={(e) => setNewAssessment({...newAssessment, max_score: parseInt(e.target.value) || 0})}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>{t('date')}</Label>
                  <Input 
                    type="date"
                    value={newAssessment.date}
                    onChange={(e) => setNewAssessment({...newAssessment, date: e.target.value})}
                  />
                </div>
                <div className="space-y-2">
                  <Label>{t('description')}</Label>
                  <Textarea 
                    value={newAssessment.description}
                    onChange={(e) => setNewAssessment({...newAssessment, description: e.target.value})}
                    rows={2}
                  />
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
                {t('cancel')}
              </Button>
              <Button onClick={createAssessment} disabled={saving}>
                {saving && <Loader2 className="h-4 w-4 animate-spin me-2" />}
                {t('create')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Grade Entry Dialog */}
        <Dialog open={showGradeDialog} onOpenChange={setShowGradeDialog}>
          <DialogContent className="w-[95vw] max-w-2xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="font-cairo">
                {t('enterGrades')} - {selectedAssessment?.title || selectedAssessment?.name}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-3 py-4">
              <div className="text-sm text-muted-foreground mb-4">
                {isRTL ? `الدرجة الكلية: ${selectedAssessment?.max_score}` : `Max Score: ${selectedAssessment?.max_score}`}
              </div>
              {students.map((student, idx) => (
                <div key={student.id} className="flex items-center gap-4 p-3 rounded-lg bg-muted/30">
                  <span className="font-medium flex-1">{student.full_name || `طالب ${idx + 1}`}</span>
                  <Input
                    type="number"
                    className="w-24"
                    placeholder="0"
                    max={selectedAssessment?.max_score}
                    value={grades[student.id]?.score || ''}
                    onChange={(e) => setGrades({
                      ...grades,
                      [student.id]: { ...grades[student.id], score: parseInt(e.target.value) || 0 }
                    })}
                  />
                  <span className="text-sm text-muted-foreground">/ {selectedAssessment?.max_score}</span>
                </div>
              ))}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowGradeDialog(false)}>
                {t('cancel')}
              </Button>
              <Button onClick={saveGrades} disabled={saving}>
                {saving && <Loader2 className="h-4 w-4 animate-spin me-2" />}
                <Save className="h-4 w-4 me-1" />
                {t('saveGrades')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
      <HakimAssistant />
    </Sidebar>
  );
}
