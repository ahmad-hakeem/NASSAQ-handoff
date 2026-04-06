/**
 * Student Assignments Page
 * صفحة واجبات الطالب
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Progress } from '../../components/ui/progress';
import { ScrollArea } from '../../components/ui/scroll-area';
import { Skeleton } from '../../components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../../components/ui/dialog';
import { Textarea } from '../../components/ui/textarea';
import { Input } from '../../components/ui/input';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  BookOpen,
  Calendar,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  FileText,
  Upload,
  Send,
  Eye,
  Download,
  ChevronLeft,
  Filter,
  Search,
  Star,
  Award,
  Loader2,
} from 'lucide-react';


// Assignment status badge component
const StatusBadge = ({ status }) => {
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const statusConfig = {
    pending: { label: 'قيد الانتظار', color: 'bg-amber-100 text-amber-700', icon: Clock },
    submitted: { label: 'تم التسليم', color: 'bg-blue-100 text-blue-700', icon: Send },
    graded: { label: 'تم التقييم', color: 'bg-green-100 text-green-700', icon: CheckCircle },
    late: { label: 'متأخر', color: 'bg-red-100 text-red-700', icon: AlertCircle },
    missed: { label: 'فائت', color: 'bg-gray-100 text-gray-700', icon: XCircle },
  };
  
  const config = statusConfig[status] || statusConfig.pending;
  const Icon = config.icon;
  
  return (
    <Badge className={`${config.color} flex items-center gap-1`}>
      <Icon className="h-3 w-3" />
      {config.label}
    </Badge>
  );
};

// Assignment card component
const AssignmentCard = ({ assignment, onView, onSubmit }) => {
  const dueDate = new Date(assignment.due_date);
  const isOverdue = dueDate < new Date() && assignment.status === 'pending';
  const daysUntilDue = Math.ceil((dueDate - new Date()) / (1000 * 60 * 60 * 24));
  
  return (
    <Card className={`border-2 hover:shadow-md transition-all ${isOverdue ? 'border-red-200' : 'border-transparent'}`}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-brand-navy to-brand-turquoise flex items-center justify-center">
                <BookOpen className="h-5 w-5 text-white" />
              </div>
              <div>
                <h3 className="font-bold text-foreground">{assignment.title}</h3>
                <p className="text-sm text-muted-foreground">{assignment.subject_name}</p>
              </div>
            </div>
            
            <p className="text-sm text-muted-foreground line-clamp-2 mb-3">
              {assignment.description || 'لا يوجد وصف'}
            </p>
            
            <div className="flex items-center gap-4 text-xs text-muted-foreground">
              <div className="flex items-center gap-1">
                <Calendar className="h-3.5 w-3.5" />
                <span>التسليم: {dueDate.toLocaleDateString('ar-SA')}</span>
              </div>
              {assignment.grade !== undefined && assignment.grade !== null && (
                <div className="flex items-center gap-1">
                  <Star className="h-3.5 w-3.5 text-amber-500" />
                  <span>الدرجة: {assignment.grade}/{assignment.max_grade || 100}</span>
                </div>
              )}
            </div>
            
            {daysUntilDue <= 3 && daysUntilDue > 0 && assignment.status === 'pending' && (
              <div className="mt-2 p-2 bg-amber-50 rounded text-xs text-amber-700 flex items-center gap-1">
                <AlertCircle className="h-3 w-3" />
                <span>باقي {daysUntilDue} {daysUntilDue === 1 ? 'يوم' : 'أيام'} على موعد التسليم</span>
              </div>
            )}
            
            {isOverdue && (
              <div className="mt-2 p-2 bg-red-50 rounded text-xs text-red-700 flex items-center gap-1">
                <XCircle className="h-3 w-3" />
                <span>تجاوز موعد التسليم!</span>
              </div>
            )}
          </div>
          
          <div className="flex flex-col items-end gap-2">
            <StatusBadge status={assignment.status} />
            
            <div className="flex gap-1">
              <Button size="sm" variant="outline" onClick={() => onView(assignment)}>
                <Eye className="h-3 w-3 ml-1" />
                عرض
              </Button>
              {(assignment.status === 'pending' || assignment.status === 'late') && (
                <Button size="sm" onClick={() => onSubmit(assignment)}>
                  <Send className="h-3 w-3 ml-1" />
                  تسليم
                </Button>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export const StudentAssignments = () => {
  const { token, user, api } = useAuth();
  const { isRTL } = useTheme();
  const [loading, setLoading] = useState(true);
  const [assignments, setAssignments] = useState([]);
  const [stats, setStats] = useState({ total: 0, pending: 0, submitted: 0, graded: 0 });
  const [activeTab, setActiveTab] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  
  // Dialogs
  const [viewDialogOpen, setViewDialogOpen] = useState(false);
  const [submitDialogOpen, setSubmitDialogOpen] = useState(false);
  const [selectedAssignment, setSelectedAssignment] = useState(null);
  const [submissionText, setSubmissionText] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Fetch assignments
  const fetchAssignments = useCallback(async () => {
    setLoading(true);
    try {
      // Try student portal API first
      let response;
      try {
        response = await api.get('/student-portal/assignments');
      } catch (e) {
        console.error('Student portal API fallback:', e);
        response = await api.get(`/assignments/student/${user?.id}`);
      }
      
      const data = response.data?.assignments || response.data || [];
      setAssignments(data);
      
      // Calculate stats
      const pending = data.filter(a => a.status === 'pending' || a.status === 'late').length;
      const submitted = data.filter(a => a.status === 'submitted').length;
      const graded = data.filter(a => a.status === 'graded').length;
      setStats({ total: data.length, pending, submitted, graded });
    } catch (error) {
      console.error('Error fetching assignments:', error);
      setAssignments([]);
      setStats({ total: 0, pending: 0, submitted: 0, graded: 0 });
    } finally {
      setLoading(false);
    }
  }, [token, user?.id]);

  useEffect(() => {
    fetchAssignments();
  }, [fetchAssignments]);

  // Filter assignments
  const filteredAssignments = assignments.filter(a => {
    // Tab filter
    if (activeTab === 'pending' && a.status !== 'pending' && a.status !== 'late') return false;
    if (activeTab === 'submitted' && a.status !== 'submitted') return false;
    if (activeTab === 'graded' && a.status !== 'graded') return false;
    
    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      return (
        a.title?.toLowerCase().includes(query) ||
        a.subject_name?.toLowerCase().includes(query) ||
        a.description?.toLowerCase().includes(query)
      );
    }
    
    return true;
  });

  // Handle view assignment
  const handleView = (assignment) => {
    setSelectedAssignment(assignment);
    setViewDialogOpen(true);
  };

  // Handle submit assignment
  const handleSubmit = (assignment) => {
    setSelectedAssignment(assignment);
    setSubmissionText('');
    setSubmitDialogOpen(true);
  };

  // Submit assignment
  const submitAssignment = async () => {
    if (!selectedAssignment || !submissionText.trim()) {
      nassaqError('الرجاء إدخال محتوى الواجب');
      return;
    }
    
    setSubmitting(true);
    try {
      await api.post(`/assignments/${selectedAssignment.id}/submit`, {
        content: submissionText,
        student_id: user?.id
      });
      
      toast.success('تم تسليم الواجب بنجاح!');
      setSubmitDialogOpen(false);
      fetchAssignments();
    } catch (error) {
      console.error('Submit error:', error);
      nassaqError('حدث خطأ أثناء تسليم الواجب. الرجاء المحاولة مرة أخرى.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <Sidebar>
        <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 p-4 md:p-6">
          <div className="space-y-6">
            <Skeleton className="h-32 w-full rounded-xl" />
            <div className="grid gap-4">
              <Skeleton className="h-32 rounded-xl" />
              <Skeleton className="h-32 rounded-xl" />
              <Skeleton className="h-32 rounded-xl" />
            </div>
          </div>
        </div>
      </Sidebar>
    );
  }

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 p-4 md:p-6" data-testid="student-assignments-page">
        <div className="max-w-5xl mx-auto space-y-6">
          
          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-violet-600 to-purple-600 flex items-center justify-center shadow-lg">
                <FileText className="h-7 w-7 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-foreground">واجباتي</h1>
                <p className="text-muted-foreground">متابعة وتسليم الواجبات المدرسية</p>
              </div>
            </div>
            
            <Button onClick={fetchAssignments} variant="outline" className="gap-2">
              <Loader2 className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              تحديث
            </Button>
          </div>
          
          {/* Stats Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card className="border-2">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center">
                    <BookOpen className="h-5 w-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-blue-700">{stats.total}</p>
                    <p className="text-xs text-gray-500">إجمالي الواجبات</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="border-2 border-amber-200">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center">
                    <Clock className="h-5 w-5 text-amber-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-amber-700">{stats.pending}</p>
                    <p className="text-xs text-gray-500">قيد الانتظار</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="border-2">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center">
                    <Send className="h-5 w-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-blue-700">{stats.submitted}</p>
                    <p className="text-xs text-gray-500">تم التسليم</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card className="border-2 border-green-200">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-green-100 flex items-center justify-center">
                    <CheckCircle className="h-5 w-5 text-green-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold text-green-700">{stats.graded}</p>
                    <p className="text-xs text-gray-500">تم التقييم</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
          
          {/* Filters */}
          <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full md:w-auto">
              <TabsList>
                <TabsTrigger value="all">الكل</TabsTrigger>
                <TabsTrigger value="pending" className="gap-1">
                  <Clock className="h-3 w-3" />
                  قيد الانتظار
                  {stats.pending > 0 && (
                    <Badge className="bg-amber-500 h-5 px-1.5">{stats.pending}</Badge>
                  )}
                </TabsTrigger>
                <TabsTrigger value="submitted">تم التسليم</TabsTrigger>
                <TabsTrigger value="graded">تم التقييم</TabsTrigger>
              </TabsList>
            </Tabs>
            
            <div className="relative w-full md:w-64">
              <Search className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="بحث في الواجبات..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pr-10"
              />
            </div>
          </div>
          
          {/* Assignments List */}
          <div className="space-y-4">
            {filteredAssignments.length === 0 ? (
              <Card className="border-2 border-dashed">
                <CardContent className="p-12 text-center">
                  <div className="w-20 h-20 rounded-full bg-muted flex items-center justify-center mx-auto mb-4">
                    <FileText className="h-10 w-10 text-muted-foreground" />
                  </div>
                  <h3 className="text-lg font-bold mb-2">لا توجد واجبات</h3>
                  <p className="text-muted-foreground">
                    {activeTab === 'pending' ? 'لا توجد واجبات قيد الانتظار' :
                     activeTab === 'submitted' ? 'لم تقم بتسليم أي واجب بعد' :
                     activeTab === 'graded' ? 'لم يتم تقييم أي واجب بعد' :
                     'لا توجد واجبات مسجلة'}
                  </p>
                </CardContent>
              </Card>
            ) : (
              filteredAssignments.map(assignment => (
                <AssignmentCard
                  key={assignment.id}
                  assignment={assignment}
                  onView={handleView}
                  onSubmit={handleSubmit}
                />
              ))
            )}
          </div>
        </div>
        
        {/* View Assignment Dialog */}
        <Dialog open={viewDialogOpen} onOpenChange={setViewDialogOpen}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <BookOpen className="h-5 w-5 text-brand-navy" />
                {selectedAssignment?.title}
              </DialogTitle>
              <DialogDescription>
                {selectedAssignment?.subject_name}
              </DialogDescription>
            </DialogHeader>
            
            {selectedAssignment && (
              <div className="space-y-4 my-4">
                <div className="flex items-center justify-between">
                  <StatusBadge status={selectedAssignment.status} />
                  {selectedAssignment.grade !== undefined && selectedAssignment.grade !== null && (
                    <div className="flex items-center gap-1 text-lg font-bold">
                      <Star className="h-5 w-5 text-amber-500" />
                      <span className="text-green-600">{selectedAssignment.grade}</span>
                      <span className="text-gray-400">/{selectedAssignment.max_grade || 100}</span>
                    </div>
                  )}
                </div>
                
                <div className="p-4 bg-muted rounded-lg">
                  <h4 className="font-medium mb-2">الوصف:</h4>
                  <p className="text-sm text-muted-foreground">
                    {selectedAssignment.description || 'لا يوجد وصف'}
                  </p>
                </div>
                
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">تاريخ التسليم:</span>
                    <p className="font-medium">{new Date(selectedAssignment.due_date).toLocaleDateString('ar-SA')}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">المعلم:</span>
                    <p className="font-medium">{selectedAssignment.teacher_name || '-'}</p>
                  </div>
                </div>
                
                {selectedAssignment.feedback && (
                  <div className="p-4 bg-green-50 rounded-lg border border-green-200">
                    <h4 className="font-medium text-green-800 mb-2 flex items-center gap-1">
                      <Award className="h-4 w-4" />
                      ملاحظات المعلم:
                    </h4>
                    <p className="text-sm text-green-700">{selectedAssignment.feedback}</p>
                  </div>
                )}
              </div>
            )}
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setViewDialogOpen(false)}>
                إغلاق
              </Button>
              {selectedAssignment && (selectedAssignment.status === 'pending' || selectedAssignment.status === 'late') && (
                <Button onClick={() => { setViewDialogOpen(false); handleSubmit(selectedAssignment); }}>
                  <Send className="h-4 w-4 ml-2" />
                  تسليم الواجب
                </Button>
              )}
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Submit Assignment Dialog */}
        <Dialog open={submitDialogOpen} onOpenChange={setSubmitDialogOpen}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Send className="h-5 w-5 text-green-600" />
                تسليم الواجب
              </DialogTitle>
              <DialogDescription>
                {selectedAssignment?.title}
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-4 my-4">
              <div className="p-3 bg-muted rounded-lg text-sm">
                <p><span className="text-muted-foreground">المادة:</span> {selectedAssignment?.subject_name}</p>
                <p><span className="text-muted-foreground">موعد التسليم:</span> {selectedAssignment && new Date(selectedAssignment.due_date).toLocaleDateString('ar-SA')}</p>
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">محتوى الإجابة:</label>
                <Textarea
                  placeholder="اكتب إجابتك هنا..."
                  value={submissionText}
                  onChange={(e) => setSubmissionText(e.target.value)}
                  rows={6}
                  className="resize-none"
                />
              </div>
              
              <div className="p-3 bg-amber-50 rounded-lg text-sm text-amber-700 flex items-start gap-2">
                <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                <p>تأكد من مراجعة إجابتك قبل التسليم. لا يمكن التعديل بعد التسليم.</p>
              </div>
            </div>
            
            <DialogFooter>
              <Button variant="outline" onClick={() => setSubmitDialogOpen(false)} disabled={submitting}>
                إلغاء
              </Button>
              <Button onClick={submitAssignment} disabled={submitting || !submissionText.trim()} className="bg-green-600 hover:bg-green-700">
                {submitting ? <Loader2 className="h-4 w-4 animate-spin ml-2" /> : <Send className="h-4 w-4 ml-2" />}
                {submitting ? 'جاري التسليم...' : 'تسليم'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Sidebar>
  );
};

export default StudentAssignments;
