import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import useParentDashboard from '../../hooks/useParentDashboard';
import StudentSwitcher from '../../components/parent/StudentSwitcher';
import SchoolDayProgress from '../../components/parent/SchoolDayProgress';
import CurrentClassCard from '../../components/parent/CurrentClassCard';
import UpcomingClasses from '../../components/parent/UpcomingClasses';
import PerformanceIndicator from '../../components/parent/PerformanceIndicator';
import WeeklyStory from '../../components/parent/WeeklyStory';
import HakimChatWidget from '../../components/parent/HakimChatWidget';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Skeleton } from '../../components/ui/skeleton';
import {
  Users, GraduationCap, Bell, Calendar, MessageSquare,
  Building, UserCircle, RefreshCw, AlertCircle
} from 'lucide-react';
import { formatHijriDate } from '../../utils/hijriDate';

const ParentPortalDashboard = () => {
  const { t } = useTranslation();
  const { isRTL } = useTheme();
  const {
    children,
    selectedChildIndex,
    selectedChild,
    selectedChildId,
    liveData,
    weeklyStory,
    notifications,
    loading,
    liveLoading,
    liveError,
    weeklyLoading,
    weeklyError,
    childrenError,
    selectChild,
    refreshLiveData,
    refreshWeeklyStory,
    refreshChildren,
  } = useParentDashboard();

  const [showNotifications, setShowNotifications] = useState(false);
  const [notifTab, setNotifTab] = useState('admin');

  const teacherNotifs = notifications.filter(n => n.sender_role === 'teacher');
  const adminNotifs = notifications.filter(n => n.sender_role !== 'teacher');

  if (loading) {
    return (
      <PortalLayout portalType="parent">
        <div className="p-4 space-y-4 max-w-lg mx-auto">
          <Skeleton className="h-10 w-full rounded-xl" />
          <Skeleton className="h-32 w-full rounded-2xl" />
          <Skeleton className="h-20 w-full rounded-2xl" />
          <Skeleton className="h-16 w-full rounded-2xl" />
          <Skeleton className="h-44 w-full rounded-2xl" />
          <Skeleton className="h-32 w-full rounded-2xl" />
          <Skeleton className="h-64 w-full rounded-2xl" />
        </div>
      </PortalLayout>
    );
  }

  return (
    <PortalLayout portalType="parent">
      <div className="p-4 space-y-4 max-w-lg mx-auto" dir={isRTL ? 'rtl' : 'ltr'} data-testid="parent-portal-dashboard">
        <StudentSwitcher
          children={children}
          selectedIndex={selectedChildIndex}
          onSelect={selectChild}
        />

        {childrenError && (
          <Card className="rounded-2xl border-0 shadow-sm border-red-100">
            <CardContent className="py-8 text-center">
              <AlertCircle className="h-10 w-10 mx-auto mb-3 text-red-400" />
              <p className="text-gray-700 text-sm font-medium mb-1">{t('failedToLoadChildrenData')}</p>
              <p className="text-gray-400 text-xs mb-3">{t('checkConnectionAndRetry')}</p>
              <Button variant="outline" size="sm" onClick={refreshChildren}>
                <RefreshCw className="h-3.5 w-3.5 me-1.5" />
                {t('retry')}
              </Button>
            </CardContent>
          </Card>
        )}

        {!childrenError && (!children || children.length === 0) && !loading && (
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardContent className="py-12 text-center">
              <Users className="h-16 w-16 mx-auto mb-4 text-gray-300" />
              <h3 className="font-bold text-lg text-gray-700 mb-2">{t('noChildrenEnrolled')}</h3>
              <p className="text-muted-foreground text-sm mb-4">{t('contactSchoolAdministrationToLinkYourAccount')}</p>
              <Button variant="outline">
                <MessageSquare className="h-4 w-4 me-2" />
                {t('contactAdmin')}
              </Button>
            </CardContent>
          </Card>
        )}

        {selectedChild && liveData && (
          <>
            <Card className="bg-gradient-to-br from-indigo-600 to-purple-700 text-white border-0 rounded-2xl overflow-hidden shadow-lg shadow-indigo-200">
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-indigo-200 text-xs">{formatHijriDate()}</p>
                    <h1 className="text-lg font-bold mt-0.5 truncate">
                      {liveData.student?.name}
                    </h1>
                    <div className="flex items-center gap-3 mt-1 text-sm text-indigo-100">
                      <span className="flex items-center gap-1">
                        <GraduationCap className="w-3.5 h-3.5 shrink-0" />
                        <span className="truncate">{liveData.student?.class_name} — {liveData.student?.grade_level}</span>
                      </span>
                    </div>
                    <div className="flex items-center gap-1 mt-0.5 text-xs text-indigo-200">
                      <Building className="w-3 h-3 shrink-0" />
                      <span className="truncate">{liveData.student?.school_name}</span>
                    </div>
                  </div>

                  <div className="flex gap-2 shrink-0">
                    {selectedChildId && (
                      <Link to={`/parent/child/${selectedChildId}/schedule`}>
                        <button
                          className="p-2.5 rounded-xl bg-white/15 hover:bg-white/25 transition-colors"
                          title={t('weeklySchedule')}
                        >
                          <Calendar className="w-5 h-5" />
                        </button>
                      </Link>
                    )}
                    <button
                      onClick={() => setShowNotifications(!showNotifications)}
                      className="p-2.5 rounded-xl bg-white/15 hover:bg-white/25 transition-colors relative"
                      title={t('notifications')}
                    >
                      <Bell className="w-5 h-5" />
                      {notifications.length > 0 && (
                        <span className="absolute -top-1 -right-1 w-4.5 h-4.5 rounded-full bg-red-500 text-[10px] font-bold flex items-center justify-center ring-2 ring-indigo-600">
                          {notifications.length > 9 ? '9+' : notifications.length}
                        </span>
                      )}
                    </button>
                  </div>
                </div>
              </CardContent>
            </Card>

            {showNotifications && (
              <Card className="rounded-2xl border-0 shadow-md animate-in slide-in-from-top-2 duration-200">
                <CardContent className="p-4">
                  <div className="flex gap-2 mb-3">
                    <button
                      onClick={() => setNotifTab('admin')}
                      className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all ${
                        notifTab === 'admin'
                          ? 'bg-indigo-100 text-indigo-700 shadow-sm'
                          : 'bg-gray-50 text-gray-500 hover:bg-gray-100'
                      }`}
                    >
                      {t('adminAlerts')} ({adminNotifs.length})
                    </button>
                    <button
                      onClick={() => setNotifTab('teacher')}
                      className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all ${
                        notifTab === 'teacher'
                          ? 'bg-indigo-100 text-indigo-700 shadow-sm'
                          : 'bg-gray-50 text-gray-500 hover:bg-gray-100'
                      }`}
                    >
                      {t('teacherAlerts')} ({teacherNotifs.length})
                    </button>
                  </div>
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {(notifTab === 'admin' ? adminNotifs : teacherNotifs).length === 0 ? (
                      <p className="text-center text-sm text-gray-400 py-4">{t('noAlerts')}</p>
                    ) : (
                      (notifTab === 'admin' ? adminNotifs : teacherNotifs).map((n, i) => (
                        <div key={n.id || i} className="p-3 rounded-xl bg-gray-50 hover:bg-indigo-50 transition-colors">
                          <p className="text-gray-800 font-medium text-xs leading-relaxed">{n.title || n.message}</p>
                          <p className="text-gray-400 text-[10px] mt-1">
                            {n.created_at ? new Date(n.created_at).toLocaleDateString('ar-SA') : ''}
                          </p>
                        </div>
                      ))
                    )}
                  </div>
                </CardContent>
              </Card>
            )}

            <PerformanceIndicator performance={liveData.performance} />

            <SchoolDayProgress schoolDay={liveData.school_day} />

            <CurrentClassCard
              currentClass={liveData.current_class}
              studentName={liveData.student?.name?.split(' ')[0]}
            />

            <UpcomingClasses classes={liveData.upcoming_classes} />

            <WeeklyStory data={weeklyStory} loading={weeklyLoading} error={weeklyError} onRetry={refreshWeeklyStory} />

            <div className="grid grid-cols-2 gap-3 pb-4">
              <Link to="/parent/communication">
                <Card className="rounded-xl border-0 shadow-sm hover:shadow-md transition-all cursor-pointer group">
                  <CardContent className="p-4 text-center">
                    <div className="w-12 h-12 rounded-xl bg-indigo-50 group-hover:bg-indigo-100 transition-colors flex items-center justify-center mx-auto mb-2">
                      <MessageSquare className="h-6 w-6 text-indigo-600" />
                    </div>
                    <p className="text-xs font-medium text-gray-700">{t('communicationCenter')}</p>
                  </CardContent>
                </Card>
              </Link>
              {selectedChildId && (
                <Link to={`/parent/child/${selectedChildId}/profile`}>
                  <Card className="rounded-xl border-0 shadow-sm hover:shadow-md transition-all cursor-pointer group">
                    <CardContent className="p-4 text-center">
                      <div className="w-12 h-12 rounded-xl bg-purple-50 group-hover:bg-purple-100 transition-colors flex items-center justify-center mx-auto mb-2">
                        <UserCircle className="h-6 w-6 text-purple-600" />
                      </div>
                      <p className="text-xs font-medium text-gray-700">{t('studentProfile')}</p>
                    </CardContent>
                  </Card>
                </Link>
              )}
            </div>
          </>
        )}

        {selectedChild && !liveData && !liveLoading && liveError && (
          <Card className="rounded-2xl border-0 shadow-sm border-red-100">
            <CardContent className="py-8 text-center">
              <AlertCircle className="h-10 w-10 mx-auto mb-3 text-red-400" />
              <p className="text-gray-700 text-sm font-medium mb-1">{t('failedToLoadSchoolDayData')}</p>
              <p className="text-gray-400 text-xs mb-3">{t('checkConnectionAndRetry')}</p>
              <Button variant="outline" size="sm" onClick={refreshLiveData}>
                <RefreshCw className="h-3.5 w-3.5 me-1.5" />
                {t('retry')}
              </Button>
            </CardContent>
          </Card>
        )}

        {selectedChild && !liveData && !liveLoading && !liveError && (
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardContent className="py-8 text-center">
              <GraduationCap className="h-10 w-10 mx-auto mb-3 text-gray-300" />
              <p className="text-gray-500 text-sm">{t('noDataAvailable')}</p>
            </CardContent>
          </Card>
        )}

        {selectedChildId && (
          <HakimChatWidget
            childId={selectedChildId}
            childName={liveData?.student?.name?.split(' ')[0] || selectedChild?.name}
          />
        )}
      </div>
    </PortalLayout>
  );
};

export default ParentPortalDashboard;
