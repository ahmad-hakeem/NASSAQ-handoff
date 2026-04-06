/**
 * Student Portal - Homework Page
 * صفحة الواجبات للطالب - محدثة لاستخدام البيانات الحقيقية
 */

import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Skeleton } from '../../components/ui/skeleton';
import { ScrollArea } from '../../components/ui/scroll-area';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  ClipboardList,
  BookOpen,
  Clock,
  CheckCircle,
  AlertCircle,
  Calendar,
  FileText,
  RefreshCw,
  Upload,
  Loader2
} from 'lucide-react';


const StudentHomeworkPage = () => {
  const { token, api } = useAuth();
  const { isRTL } = useTheme();
  const [loading, setLoading] = useState(true);
  const [homework, setHomework] = useState({ pending: [], completed: [], overdue: [] });
  const [statistics, setStatistics] = useState({ pending: 0, submitted: 0, graded: 0, late: 0 });

  const { nassaqError, nassaqWarning } = useNassaqAlert();
  useEffect(() => {
    fetchHomework();
  }, [token]);

  const fetchHomework = async () => {
    setLoading(true);
    try {
      // Fetch from real API
      const response = await api.get('/student-portal/assignments');
      
      if (response.data && response.data.assignments) {
        const assignments = response.data.assignments;
        
        // Categorize assignments
        const pending = assignments.filter(a => a.status === 'pending');
        const completed = assignments.filter(a => a.status === 'submitted' || a.status === 'graded');
        const overdue = assignments.filter(a => a.status === 'late');
        
        setHomework({ pending, completed, overdue });
        setStatistics(response.data.statistics || {
          pending: pending.length,
          submitted: completed.filter(a => a.status === 'submitted').length,
          graded: completed.filter(a => a.status === 'graded').length,
          late: overdue.length
        });
      }
    } catch (error) {
      console.error('Error fetching homework:', error);
      
      // Show appropriate error message
      if (error.response?.status === 403) {
        nassaqError(isRTL ? 'لا يمكنك الوصول إلى هذه الصفحة. يجب تسجيل الدخول كطالب.' : 'Access denied. Please login as a student.');
      } else {
        nassaqError(isRTL ? 'حدث خطأ في جلب الواجبات' : 'Error fetching homework');
      }
      
      // Set empty data
      setHomework({ pending: [], completed: [], overdue: [] });
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-700 border-green-200';
      case 'overdue':
        return 'bg-red-100 text-red-700 border-red-200';
      default:
        return 'bg-amber-100 text-amber-700 border-amber-200';
    }
  };

  const getStatusLabel = (status) => {
    const labels = {
      pending: isRTL ? 'قيد الانتظار' : 'Pending',
      completed: isRTL ? 'مكتمل' : 'Completed',
      overdue: isRTL ? 'متأخر' : 'Overdue'
    };
    return labels[status] || status;
  };

  const formatDate = (dateStr) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('ar-SA', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
    } catch (e) {
      console.error('Error formatting date:', e);
      return dateStr;
    }
  };

  const getDaysRemaining = (dueDate) => {
    const today = new Date();
    const due = new Date(dueDate);
    const diff = Math.ceil((due - today) / (1000 * 60 * 60 * 24));
    
    if (diff < 0) return isRTL ? `متأخر ${Math.abs(diff)} يوم` : `${Math.abs(diff)} days overdue`;
    if (diff === 0) return isRTL ? 'اليوم' : 'Today';
    if (diff === 1) return isRTL ? 'غداً' : 'Tomorrow';
    return isRTL ? `${diff} أيام متبقية` : `${diff} days left`;
  };

  if (loading) {
    return (
      <PortalLayout portalType="student">
        <div className="p-4 space-y-4">
          <Skeleton className="h-12 w-full rounded-xl" />
          <Skeleton className="h-64 w-full rounded-2xl" />
        </div>
      </PortalLayout>
    );
  }

  const totalPending = homework.pending.length;
  const totalCompleted = homework.completed.length;
  const totalOverdue = homework.overdue.length;

  return (
    <PortalLayout portalType="student">
      <div className="p-4 space-y-4" data-testid="student-homework-page">
        {/* Header */}
        <Card className="rounded-2xl border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-purple-100 flex items-center justify-center">
                  <ClipboardList className="h-6 w-6 text-purple-600" />
                </div>
                <div>
                  <h1 className="font-bold text-lg">{isRTL ? 'الواجبات المنزلية' : 'Homework'}</h1>
                  <p className="text-sm text-muted-foreground">
                    {totalPending} {isRTL ? 'واجب قيد الانتظار' : 'pending assignments'}
                  </p>
                </div>
              </div>
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={fetchHomework}
                disabled={loading}
                data-testid="refresh-homework-btn"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-3">
          <Card className="rounded-xl border-0 shadow-sm">
            <CardContent className="p-3 text-center">
              <div className="w-8 h-8 mx-auto mb-1 rounded-lg bg-amber-100 flex items-center justify-center">
                <Clock className="h-4 w-4 text-amber-600" />
              </div>
              <p className="text-lg font-bold text-amber-600">{totalPending}</p>
              <p className="text-[10px] text-muted-foreground">{isRTL ? 'قيد الانتظار' : 'Pending'}</p>
            </CardContent>
          </Card>

          <Card className="rounded-xl border-0 shadow-sm">
            <CardContent className="p-3 text-center">
              <div className="w-8 h-8 mx-auto mb-1 rounded-lg bg-green-100 flex items-center justify-center">
                <CheckCircle className="h-4 w-4 text-green-600" />
              </div>
              <p className="text-lg font-bold text-green-600">{totalCompleted}</p>
              <p className="text-[10px] text-muted-foreground">{isRTL ? 'مكتمل' : 'Completed'}</p>
            </CardContent>
          </Card>

          <Card className="rounded-xl border-0 shadow-sm">
            <CardContent className="p-3 text-center">
              <div className="w-8 h-8 mx-auto mb-1 rounded-lg bg-red-100 flex items-center justify-center">
                <AlertCircle className="h-4 w-4 text-red-600" />
              </div>
              <p className="text-lg font-bold text-red-600">{totalOverdue}</p>
              <p className="text-[10px] text-muted-foreground">{isRTL ? 'متأخر' : 'Overdue'}</p>
            </CardContent>
          </Card>
        </div>

        {/* Tabs */}
        <Tabs defaultValue="pending" className="w-full">
          <TabsList className="grid w-full grid-cols-3 bg-gray-100 rounded-xl p-1">
            <TabsTrigger value="pending" className="rounded-lg text-xs">
              {isRTL ? 'قيد الانتظار' : 'Pending'} ({totalPending})
            </TabsTrigger>
            <TabsTrigger value="completed" className="rounded-lg text-xs">
              {isRTL ? 'مكتمل' : 'Completed'} ({totalCompleted})
            </TabsTrigger>
            <TabsTrigger value="overdue" className="rounded-lg text-xs">
              {isRTL ? 'متأخر' : 'Overdue'} ({totalOverdue})
            </TabsTrigger>
          </TabsList>

          {['pending', 'completed', 'overdue'].map((status) => (
            <TabsContent key={status} value={status} className="mt-4">
              <Card className="rounded-2xl border-0 shadow-sm">
                <CardContent className="p-4">
                  <ScrollArea className="h-[400px]">
                    {homework[status]?.length > 0 ? (
                      <div className="space-y-3">
                        {homework[status].map((item) => (
                          <div
                            key={item.id}
                            className="p-4 bg-gray-50 rounded-xl hover:bg-gray-100 transition-all"
                            data-testid={`homework-item-${item.id}`}
                          >
                            <div className="flex items-start justify-between mb-2">
                              <div className="flex items-center gap-2">
                                <BookOpen className="h-4 w-4 text-purple-600" />
                                <span className="font-medium text-sm">{item.subject_name || item.subject}</span>
                              </div>
                              <Badge variant="outline" className={getStatusColor(item.status)}>
                                {getStatusLabel(item.status)}
                              </Badge>
                            </div>
                            
                            <h3 className="font-bold mb-1">{item.title}</h3>
                            <p className="text-sm text-muted-foreground mb-3">{item.description}</p>
                            
                            {/* Teacher name */}
                            {item.teacher_name && (
                              <p className="text-xs text-muted-foreground mb-2">
                                {isRTL ? 'المعلم:' : 'Teacher:'} {item.teacher_name}
                              </p>
                            )}
                            
                            <div className="flex items-center justify-between text-xs text-muted-foreground">
                              <span className="flex items-center gap-1">
                                <Calendar className="h-3 w-3" />
                                {formatDate(item.due_date)}
                              </span>
                              {status === 'pending' && (
                                <span className={`font-medium ${
                                  getDaysRemaining(item.due_date).includes('متأخر') || getDaysRemaining(item.due_date).includes('overdue')
                                    ? 'text-red-600'
                                    : 'text-amber-600'
                                }`}>
                                  {getDaysRemaining(item.due_date)}
                                </span>
                              )}
                              {(status === 'completed' || item.status === 'graded') && item.grade !== null && item.grade !== undefined && (
                                <Badge className="bg-green-100 text-green-700 border-0">
                                  {isRTL ? 'الدرجة:' : 'Grade:'} {item.grade}{item.max_grade ? `/${item.max_grade}` : '%'}
                                </Badge>
                              )}
                            </div>
                            
                            {/* Feedback if available */}
                            {item.feedback && (
                              <div className="mt-2 p-2 bg-blue-50 rounded-lg">
                                <p className="text-xs text-blue-700">
                                  <strong>{isRTL ? 'ملاحظات المعلم:' : 'Teacher feedback:'}</strong> {item.feedback}
                                </p>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                        <FileText className="h-12 w-12 mb-3 opacity-30" />
                        <p>
                          {status === 'pending' && (isRTL ? 'لا توجد واجبات قيد الانتظار' : 'No pending homework')}
                          {status === 'completed' && (isRTL ? 'لا توجد واجبات مكتملة' : 'No completed homework')}
                          {status === 'overdue' && (isRTL ? 'لا توجد واجبات متأخرة' : 'No overdue homework')}
                        </p>
                      </div>
                    )}
                  </ScrollArea>
                </CardContent>
              </Card>
            </TabsContent>
          ))}
        </Tabs>
      </div>
    </PortalLayout>
  );
};

export default StudentHomeworkPage;
