/**
 * Student Portal - Schedule Page
 * صفحة الجدول الدراسي للطالب
 */

import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Skeleton } from '../../components/ui/skeleton';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  Calendar,
  Clock,
  BookOpen,
  User,
  MapPin,
} from 'lucide-react';


const DAYS = ['الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس'];

const StudentSchedulePage = () => {
  const { token, api } = useAuth();
  const { isRTL } = useTheme();
  const [loading, setLoading] = useState(true);
  const [schedule, setSchedule] = useState({});
  const [studentInfo, setStudentInfo] = useState(null);
  const [selectedDay, setSelectedDay] = useState(getCurrentDay());

  const { nassaqError, nassaqWarning } = useNassaqAlert();
  function getCurrentDay() {
    const dayMap = {
      0: 'الأحد',
      1: 'الاثنين',
      2: 'الثلاثاء',
      3: 'الأربعاء',
      4: 'الخميس',
      5: 'الجمعة',
      6: 'السبت'
    };
    return dayMap[new Date().getDay()] || 'الأحد';
  }

  useEffect(() => {
    fetchSchedule();
  }, [token]);

  const fetchSchedule = async () => {
    try {
      const response = await api.get('/student-portal/schedule');
      setSchedule(response.data.schedule || {});
      setStudentInfo(response.data.student_info);
    } catch (error) {
      console.error('Error fetching schedule:', error);
      nassaqError(isRTL ? 'حدث خطأ في جلب الجدول' : 'Error fetching schedule');
    } finally {
      setLoading(false);
    }
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

  return (
    <PortalLayout portalType="student">
      <div className="p-4 space-y-4" data-testid="student-schedule-page">
        {/* Header */}
        <Card className="rounded-2xl border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-emerald-100 flex items-center justify-center">
                  <Calendar className="h-6 w-6 text-emerald-600" />
                </div>
                <div>
                  <h1 className="font-bold text-lg">{isRTL ? 'الجدول الدراسي' : 'Class Schedule'}</h1>
                  {studentInfo && (
                    <p className="text-sm text-muted-foreground">
                      {studentInfo.grade} - {studentInfo.class_name}
                    </p>
                  )}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Days Tabs */}
        <Tabs value={selectedDay} onValueChange={setSelectedDay} className="w-full">
          <TabsList className="grid grid-cols-5 bg-gray-100 rounded-xl p-1 h-auto">
            {DAYS.map((day) => (
              <TabsTrigger
                key={day}
                value={day}
                className={`rounded-lg py-2 text-xs font-medium ${
                  day === getCurrentDay() ? 'data-[state=active]:bg-emerald-500 data-[state=active]:text-white' : ''
                }`}
              >
                {day}
              </TabsTrigger>
            ))}
          </TabsList>

          {DAYS.map((day) => (
            <TabsContent key={day} value={day} className="mt-4">
              <Card className="rounded-2xl border-0 shadow-sm">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Clock className="h-5 w-5 text-emerald-600" />
                    {isRTL ? `حصص يوم ${day}` : `${day} Classes`}
                    <Badge variant="secondary" className="ms-auto">
                      {schedule[day]?.length || 0} {isRTL ? 'حصص' : 'classes'}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {schedule[day]?.length > 0 ? (
                    <div className="space-y-3">
                      {schedule[day].map((entry, idx) => (
                        <div
                          key={idx}
                          className="flex items-center gap-4 p-4 bg-gray-50 rounded-xl hover:bg-gray-100 transition-all"
                        >
                          <div className="w-16 h-14 rounded-lg bg-emerald-100 flex flex-col items-center justify-center">
                            <span className="font-bold text-sm text-emerald-700">{entry.start_time}</span>
                            <span className="text-xs text-emerald-600">{entry.end_time}</span>
                          </div>
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <BookOpen className="h-4 w-4 text-emerald-600" />
                              <span className="font-medium">{entry.subject}</span>
                            </div>
                            <div className="flex items-center gap-4 text-xs text-muted-foreground">
                              <span className="flex items-center gap-1">
                                <User className="h-3 w-3" />
                                {entry.teacher}
                              </span>
                              {entry.room && (
                                <span className="flex items-center gap-1">
                                  <MapPin className="h-3 w-3" />
                                  {entry.room}
                                </span>
                              )}
                            </div>
                          </div>
                          <Badge variant="outline" className="text-emerald-600 border-emerald-200">
                            {isRTL ? `الحصة ${entry.period}` : `Period ${entry.period}`}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                      <Calendar className="h-12 w-12 mb-3 opacity-30" />
                      <p>{isRTL ? 'لا توجد حصص في هذا اليوم' : 'No classes on this day'}</p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          ))}
        </Tabs>
      </div>
    </PortalLayout>
  );
};

export default StudentSchedulePage;
