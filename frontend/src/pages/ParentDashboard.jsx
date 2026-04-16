import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '../components/ui/avatar';
import { Progress } from '../components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import {
  User, Calendar, Bell, GraduationCap, Clock, CheckCircle2,
  AlertCircle, TrendingUp, Award, FileText, BookOpen, Users,
  Phone, Mail, BarChart3, CalendarDays, MessageSquare, Home,
  Settings, ChevronLeft, ChevronRight, Loader2
} from 'lucide-react';
import { formatHijriDate } from '../utils/hijriDate';

export default function ParentDashboard() {
  const { user, api, isRTL = true } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [selectedChildIndex, setSelectedChildIndex] = useState(0);
  const [parentData, setParentData] = useState(null);
  const [children, setChildren] = useState([]);
  const [notifications, setNotifications] = useState([]);

  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const fetchParentData = useCallback(async () => {
    setLoading(true);
    try {
      const parentId = user?.parent_id || user?.id;
      
      if (!parentId) {
        setLoading(false);
        return;
      }
      
      const response = await api.get(`/parent/dashboard/${parentId}`);
      
      if (response?.data) {
        const data = response.data;
        
        setParentData({
          name: data.parent?.name || user?.full_name,
          phone: data.parent?.phone,
          email: data.parent?.email
        });
        
        setChildren(data.children?.map(child => ({
          id: child.id,
          name: child.name,
          className: child.class_name,
          avatar: child.avatar,
          stats: {
            attendanceRate: child.stats?.attendance_rate || 0,
            averageGrade: child.stats?.average_grade || 0,
            absences: child.stats?.absences || 0,
            lates: child.stats?.lates || 0
          },
          recentGrades: child.recent_grades || [],
          behaviourNotes: child.behaviour_notes || [],
          todaySchedule: child.today_schedule || []
        })) || []);
        
        setNotifications(data.notifications?.map(n => ({
          title: n.title || n.message,
          time: n.time ? new Date(n.time).toLocaleDateString('ar-SA') : 'مؤخراً',
          type: n.type || 'info'
        })) || []);
      }
    } catch (error) {
      console.error('Error fetching parent data:', error);
      nassaqError('خطأ في جلب البيانات');
    } finally {
      setLoading(false);
    }
  }, [api, user?.id, user?.parent_id, user?.full_name]);

  useEffect(() => {
    fetchParentData();
  }, [fetchParentData]);

  const selectedChild = children[selectedChildIndex];

  const getGradeColor = (grade) => {
    if (grade >= 90) return 'text-green-600';
    if (grade >= 80) return 'text-blue-600';
    if (grade >= 70) return 'text-yellow-600';
    return 'text-red-600';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center" dir="rtl">
        <div className="text-center">
          <Loader2 className="h-12 w-12 animate-spin text-indigo-600 mx-auto mb-4" />
          <p className="text-muted-foreground">جارٍ التحميل...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-24" dir="rtl" data-testid="parent-dashboard">
      {/* Header */}
      <div className="bg-gradient-to-br from-indigo-600 to-purple-500 text-white">
        <div className="px-4 py-6 space-y-4">
          {/* Date */}
          <p className="text-indigo-100 text-sm text-center">{formatHijriDate()}</p>
          
          {/* Parent Info */}
          <div className="flex items-center gap-4">
            <Avatar className="h-16 w-16 border-2 border-white/30 shadow-lg">
              <AvatarImage src={user?.avatar_url} alt={parentData?.name} />
              <AvatarFallback className="bg-white/20 text-white text-xl font-bold">
                {parentData?.name?.charAt(0) || 'و'}
              </AvatarFallback>
            </Avatar>
            <div>
              <h1 className="font-cairo text-xl font-bold">
                مرحباً {parentData?.name || 'ولي الأمر'}
              </h1>
              <p className="text-indigo-100 text-sm flex items-center gap-2">
                <Users className="h-4 w-4" />
                {children.length} {children.length === 1 ? 'ابن' : 'أبناء'} مسجلين
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="px-4 py-4 space-y-4 -mt-4">
        
        {/* Children Selector */}
        {children.length > 1 && (
          <div className="flex gap-2 overflow-x-auto pb-2 -mx-4 px-4">
            {children.map((child, index) => (
              <button
                key={child.id}
                onClick={() => setSelectedChildIndex(index)}
                className={`flex items-center gap-2 px-4 py-2 rounded-full whitespace-nowrap transition-all ${
                  selectedChildIndex === index 
                    ? 'bg-indigo-600 text-white shadow-lg' 
                    : 'bg-white text-gray-700 border'
                }`}
              >
                <Avatar className="h-6 w-6">
                  <AvatarFallback className={`text-xs ${
                    selectedChildIndex === index ? 'bg-white/20 text-white' : 'bg-indigo-100 text-indigo-600'
                  }`}>
                    {(child.name || '').charAt(0)}
                  </AvatarFallback>
                </Avatar>
                <span className="text-sm font-medium">{(child.name || '').split(' ')[0]}</span>
              </button>
            ))}
          </div>
        )}

        {/* No Children State */}
        {children.length === 0 ? (
          <Card className="rounded-2xl shadow-sm border-0">
            <CardContent className="py-12 text-center">
              <Users className="h-16 w-16 mx-auto mb-4 text-gray-300" />
              <h3 className="font-bold text-lg text-gray-700 mb-2">لا يوجد أبناء مسجلين</h3>
              <p className="text-muted-foreground text-sm mb-4">
                تواصل مع إدارة المدرسة لربط حسابك بأبنائك
              </p>
              <Button variant="outline">
                <Phone className="h-4 w-4 me-2" />
                تواصل مع الإدارة
              </Button>
            </CardContent>
          </Card>
        ) : selectedChild && (
          <>
            {/* Selected Child Card */}
            <Card className="rounded-2xl shadow-sm border-0 overflow-hidden">
              <div className="bg-gradient-to-l from-indigo-50 to-purple-50 p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Avatar className="h-12 w-12 border-2 border-indigo-200">
                      <AvatarFallback className="bg-indigo-100 text-indigo-600 font-bold">
                        {(selectedChild.name || '').charAt(0)}
                      </AvatarFallback>
                    </Avatar>
                    <div>
                      <h2 className="font-cairo font-bold">{selectedChild.name || ''}</h2>
                      <p className="text-sm text-muted-foreground">{selectedChild.className}</p>
                    </div>
                  </div>
                  <Button variant="outline" size="sm" className="text-indigo-600 border-indigo-200">
                    <MessageSquare className="h-4 w-4 me-1" />
                    تواصل
                  </Button>
                </div>
              </div>
            </Card>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 gap-3">
              <Card className="rounded-xl shadow-sm border-0">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="p-2 rounded-lg bg-green-100">
                      <CheckCircle2 className="h-5 w-5 text-green-600" />
                    </div>
                    <span className="text-2xl font-bold text-green-600">
                      {selectedChild.stats.attendanceRate}%
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">نسبة الحضور</p>
                  <Progress value={selectedChild.stats.attendanceRate} className="h-1.5 mt-2" />
                </CardContent>
              </Card>

              <Card className="rounded-xl shadow-sm border-0">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="p-2 rounded-lg bg-blue-100">
                      <Award className="h-5 w-5 text-blue-600" />
                    </div>
                    <span className="text-2xl font-bold text-blue-600">
                      {selectedChild.stats.averageGrade}%
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground">المعدل العام</p>
                  <Progress value={selectedChild.stats.averageGrade} className="h-1.5 mt-2" />
                </CardContent>
              </Card>

              <Card className="rounded-xl shadow-sm border-0">
                <CardContent className="p-4 text-center">
                  <div className="p-2 rounded-lg bg-orange-100 w-fit mx-auto mb-2">
                    <AlertCircle className="h-5 w-5 text-orange-600" />
                  </div>
                  <span className="text-2xl font-bold text-orange-600">
                    {selectedChild.stats.absences}
                  </span>
                  <p className="text-xs text-muted-foreground">أيام الغياب</p>
                </CardContent>
              </Card>

              <Card className="rounded-xl shadow-sm border-0">
                <CardContent className="p-4 text-center">
                  <div className="p-2 rounded-lg bg-yellow-100 w-fit mx-auto mb-2">
                    <Clock className="h-5 w-5 text-yellow-600" />
                  </div>
                  <span className="text-2xl font-bold text-yellow-600">
                    {selectedChild.stats.lates}
                  </span>
                  <p className="text-xs text-muted-foreground">مرات التأخير</p>
                </CardContent>
              </Card>
            </div>

            {/* Tabs */}
            <Tabs defaultValue="grades" className="w-full">
              <TabsList className="grid w-full grid-cols-3 bg-gray-100 rounded-xl p-1">
                <TabsTrigger value="grades" className="rounded-lg text-xs">الدرجات</TabsTrigger>
                <TabsTrigger value="schedule" className="rounded-lg text-xs">الجدول</TabsTrigger>
                <TabsTrigger value="behaviour" className="rounded-lg text-xs">السلوك</TabsTrigger>
              </TabsList>

              <TabsContent value="grades" className="mt-3">
                <Card className="rounded-xl shadow-sm border-0">
                  <CardContent className="p-4 space-y-2">
                    {selectedChild.recentGrades.length === 0 ? (
                      <div className="text-center py-6 text-muted-foreground">
                        <Award className="h-10 w-10 mx-auto mb-2 opacity-50" />
                        <p>لا توجد درجات</p>
                      </div>
                    ) : (
                      selectedChild.recentGrades.map((item, index) => (
                        <div key={index} className="flex items-center justify-between p-3 rounded-lg bg-gray-50">
                          <div className="flex items-center gap-3">
                            <BookOpen className="h-5 w-5 text-gray-400" />
                            <div>
                              <span className="font-medium text-sm">{item.subject}</span>
                              <p className="text-xs text-muted-foreground">{item.date}</p>
                            </div>
                          </div>
                          <span className={`font-bold text-lg ${getGradeColor(item.grade)}`}>
                            {item.grade}%
                          </span>
                        </div>
                      ))
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="schedule" className="mt-3">
                <Card className="rounded-xl shadow-sm border-0">
                  <CardContent className="p-4 space-y-2">
                    {selectedChild.todaySchedule.length === 0 ? (
                      <div className="text-center py-6 text-muted-foreground">
                        <CalendarDays className="h-10 w-10 mx-auto mb-2 opacity-50" />
                        <p>لا توجد حصص اليوم</p>
                      </div>
                    ) : (
                      selectedChild.todaySchedule.map((lesson, index) => (
                        <div key={index} className="flex items-center gap-3 p-3 rounded-lg bg-gray-50">
                          <div className="w-12 h-10 rounded-lg bg-purple-100 flex items-center justify-center">
                            <span className="font-bold text-xs text-purple-600">{lesson.time}</span>
                          </div>
                          <div>
                            <p className="font-medium text-sm">{lesson.subject}</p>
                            <p className="text-xs text-muted-foreground">{lesson.teacher}</p>
                          </div>
                        </div>
                      ))
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="behaviour" className="mt-3">
                <Card className="rounded-xl shadow-sm border-0">
                  <CardContent className="p-4 space-y-2">
                    {selectedChild.behaviourNotes.length === 0 ? (
                      <div className="text-center py-6 text-muted-foreground">
                        <CheckCircle2 className="h-10 w-10 mx-auto mb-2 opacity-50" />
                        <p>لا توجد ملاحظات</p>
                      </div>
                    ) : (
                      selectedChild.behaviourNotes.map((note, index) => (
                        <div key={index} className={`p-3 rounded-lg border ${
                          note.type === 'positive' ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'
                        }`}>
                          <div className="flex items-start gap-3">
                            <div className={`p-2 rounded-full ${
                              note.type === 'positive' ? 'bg-green-100' : 'bg-red-100'
                            }`}>
                              {note.type === 'positive' ? (
                                <CheckCircle2 className="h-4 w-4 text-green-600" />
                              ) : (
                                <AlertCircle className="h-4 w-4 text-red-600" />
                              )}
                            </div>
                            <div>
                              <p className="font-medium text-sm">{note.note}</p>
                              <p className="text-xs text-muted-foreground">{note.date}</p>
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>
          </>
        )}

        {/* Notifications */}
        {notifications.length > 0 && (
          <Card className="rounded-2xl shadow-sm border-0">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <Bell className="h-5 w-5 text-orange-500" />
                الإشعارات
                <Badge variant="destructive" className="ms-auto text-xs">
                  {notifications.length}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {notifications.slice(0, 3).map((notif, index) => (
                <div key={index} className="flex items-start gap-3 p-3 rounded-xl bg-gray-50">
                  <div className={`p-2 rounded-full ${
                    notif.type === 'exam' ? 'bg-red-100' :
                    notif.type === 'grade' ? 'bg-green-100' : 'bg-blue-100'
                  }`}>
                    {notif.type === 'exam' ? (
                      <AlertCircle className="h-4 w-4 text-red-600" />
                    ) : notif.type === 'grade' ? (
                      <Award className="h-4 w-4 text-green-600" />
                    ) : (
                      <Calendar className="h-4 w-4 text-blue-600" />
                    )}
                  </div>
                  <div className="flex-1">
                    <p className="font-medium text-sm">{notif.title}</p>
                    <p className="text-xs text-muted-foreground">{notif.time}</p>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>

      {/* Bottom Navigation */}
      <nav className="fixed bottom-0 left-0 right-0 bg-white border-t shadow-lg z-50">
        <div className="flex items-center justify-around py-2">
          <button className="flex flex-col items-center gap-1 p-2 text-indigo-600">
            <Home className="h-6 w-6" />
            <span className="text-xs font-medium">الرئيسية</span>
          </button>
          <button className="flex flex-col items-center gap-1 p-2 text-gray-400">
            <Users className="h-6 w-6" />
            <span className="text-xs">أبنائي</span>
          </button>
          <button className="flex flex-col items-center gap-1 p-2 text-gray-400">
            <Bell className="h-6 w-6" />
            <span className="text-xs">الإشعارات</span>
          </button>
          <button className="flex flex-col items-center gap-1 p-2 text-gray-400">
            <User className="h-6 w-6" />
            <span className="text-xs">حسابي</span>
          </button>
        </div>
      </nav>
    </div>
  );
}
