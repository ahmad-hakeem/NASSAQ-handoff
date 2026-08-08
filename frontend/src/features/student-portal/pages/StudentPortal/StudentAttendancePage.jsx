/**
 * Student Portal - Attendance Page
 * صفحة الحضور والغياب للطالب
 */

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/shared/contexts/AuthContext';
import { useTheme , useTranslation } from '@/shared/contexts/ThemeContext';
import PortalLayout from '@/features/student-portal/components/portal/PortalLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Progress } from '@/shared/components/ui/progress';
import { LoadingState } from '@/shared/components/ui/LoadingState';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { Button } from '@/shared/components/ui/button';
import { toast } from 'sonner';
import { useNassaqAlert } from '@/shared/components/ui/NassaqAlertDialog';
import {
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
  Calendar,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';


const MONTHS = [
  'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
  'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'
];

const StudentAttendancePage = () => {
  const { t } = useTranslation();
  const { token, api } = useAuth();
  const { isRTL } = useTheme();
  const [loading, setLoading] = useState(true);
  const [attendanceData, setAttendanceData] = useState(null);
  const [currentMonth, setCurrentMonth] = useState(new Date().getMonth() + 1);
  const [currentYear, setCurrentYear] = useState(new Date().getFullYear());

  const { nassaqError, nassaqWarning } = useNassaqAlert();
  useEffect(() => {
    fetchAttendance();
  }, [token, currentMonth, currentYear]);

  const fetchAttendance = async () => {
    setLoading(true);
    try {
      const response = await api.get('/student-portal/attendance', {
        headers: { Authorization: `Bearer ${token}` },
        params: { month: currentMonth, year: currentYear }
      });
      setAttendanceData(response.data);
    } catch (error) {
      console.error('Error fetching attendance:', error);
      nassaqError(t('errorFetchingAttendance'));
    } finally {
      setLoading(false);
    }
  };

  const goToPreviousMonth = () => {
    if (currentMonth === 1) {
      setCurrentMonth(12);
      setCurrentYear(currentYear - 1);
    } else {
      setCurrentMonth(currentMonth - 1);
    }
  };

  const goToNextMonth = () => {
    if (currentMonth === 12) {
      setCurrentMonth(1);
      setCurrentYear(currentYear + 1);
    } else {
      setCurrentMonth(currentMonth + 1);
    }
  };

  // Note: 'late' is intentionally hidden from the student-facing UI; legacy late records render as present
  const getStatusIcon = (status) => {
    switch (status) {
      case 'present':
      case 'late':
        return <CheckCircle className="h-5 w-5 text-green-600" />;
      case 'absent':
        return <XCircle className="h-5 w-5 text-red-600" />;
      case 'excused':
        return <AlertCircle className="h-5 w-5 text-blue-600" />;
      default:
        return <Calendar className="h-5 w-5 text-gray-400" />;
    }
  };

  const getStatusLabel = (status) => {
    const labels = {
      present: t('present'),
      absent: t('absent'),
      late: t('present'),
      excused: t('excused2')
    };
    return labels[status] || status;
  };

  const getStatusBg = (status) => {
    const bgs = {
      present: 'bg-green-50 border-green-200',
      absent: 'bg-red-50 border-red-200',
      late: 'bg-green-50 border-green-200',
      excused: 'bg-blue-50 border-blue-200'
    };
    return bgs[status] || 'bg-gray-50 border-gray-200';
  };

  if (loading) {
    return (
      <PortalLayout portalType="student">
        <LoadingState variant="fullpage" />
      </PortalLayout>
    );
  }

  const stats = attendanceData?.statistics || {};

  return (
    <PortalLayout portalType="student">
      <div className="p-4 space-y-4" data-testid="student-attendance-page">
        {/* Summary Card */}
        <Card className="rounded-2xl border-0 shadow-sm bg-gradient-to-br from-green-500 to-emerald-600 text-white">
          <CardContent className="p-4 md:p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 rounded-2xl bg-white/20 flex items-center justify-center">
                  <CheckCircle className="h-8 w-8 text-white" />
                </div>
                <div>
                  <p className="text-green-100 text-sm">{t('attendanceRate')}</p>
                  <h1 className="text-3xl font-bold">{stats.attendance_rate || 0}%</h1>
                  <p className="text-sm text-green-100 mt-1">
                    {stats.present || 0} {isRTL ? 'من' : 'of'} {stats.total_days || 0} {t('days')}
                  </p>
                </div>
              </div>
              <div className="hidden md:block">
                <Progress value={stats.attendance_rate || 0} className="w-32 h-3 bg-white/20" />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Stats Grid */}
        <div className="grid grid-cols-3 gap-3">
          <Card className="rounded-xl border-0 shadow-sm">
            <CardContent className="p-4 text-center">
              <div className="w-10 h-10 mx-auto mb-2 rounded-lg bg-green-100 flex items-center justify-center">
                <CheckCircle className="h-5 w-5 text-green-600" />
              </div>
              <p className="text-xl font-bold text-green-600">{stats.present || 0}</p>
              <p className="text-xs text-muted-foreground">{t('present')}</p>
            </CardContent>
          </Card>

          <Card className="rounded-xl border-0 shadow-sm">
            <CardContent className="p-4 text-center">
              <div className="w-10 h-10 mx-auto mb-2 rounded-lg bg-red-100 flex items-center justify-center">
                <XCircle className="h-5 w-5 text-red-600" />
              </div>
              <p className="text-xl font-bold text-red-600">{stats.absent || 0}</p>
              <p className="text-xs text-muted-foreground">{t('absent')}</p>
            </CardContent>
          </Card>

          <Card className="rounded-xl border-0 shadow-sm">
            <CardContent className="p-4 text-center">
              <div className="w-10 h-10 mx-auto mb-2 rounded-lg bg-blue-100 flex items-center justify-center">
                <AlertCircle className="h-5 w-5 text-blue-600" />
              </div>
              <p className="text-xl font-bold text-blue-600">{stats.excused || 0}</p>
              <p className="text-xs text-muted-foreground">{t('excused2')}</p>
            </CardContent>
          </Card>
        </div>

        {/* Monthly Records */}
        <Card className="rounded-2xl border-0 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center justify-between text-base">
              <div className="flex items-center gap-2">
                <Calendar className="h-5 w-5 text-green-600" />
                {t('attendanceRecords')}
              </div>
              
              {/* Month Navigation */}
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={goToPreviousMonth}
                  className="h-8 w-8"
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
                <span className="text-sm font-medium min-w-[100px] text-center">
                  {MONTHS[currentMonth - 1]} {currentYear}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={goToNextMonth}
                  className="h-8 w-8"
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[400px]">
              {attendanceData?.records?.length > 0 ? (
                <div className="space-y-2">
                  {attendanceData.records.map((record, idx) => (
                    <div
                      key={idx}
                      className={`flex items-center justify-between p-3 rounded-xl border ${getStatusBg(record.status)}`}
                    >
                      <div className="flex items-center gap-3">
                        {getStatusIcon(record.status)}
                        <div>
                          <p className="font-medium text-sm">{record.date}</p>
                          {record.notes && (
                            <p className="text-xs text-muted-foreground">{record.notes}</p>
                          )}
                        </div>
                      </div>
                      <div className="text-end">
                        <Badge variant="outline" className="text-xs">
                          {getStatusLabel(record.status)}
                        </Badge>
                        {record.check_in_time && (
                          <p className="text-xs text-muted-foreground mt-1">
                            {t('in')} {record.check_in_time}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                  <Calendar className="h-12 w-12 mb-3 opacity-30" />
                  <p>{t('noRecordsForThisMonth')}</p>
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    </PortalLayout>
  );
};

export default StudentAttendancePage;
