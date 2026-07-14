import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme , useTranslation } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Progress } from '../../components/ui/progress';
import { LoadingState } from '../../components/ui/LoadingState';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/avatar';
import CumulativeAnalytics from '../../components/parent/CumulativeAnalytics';
import {
  User, GraduationCap, MapPin, Calendar, CheckCircle,
  TrendingUp, Star, Award, Mail, Phone, Hash, Activity, AlertCircle, RefreshCw
} from 'lucide-react';


const StudentProfilePage = () => {
  const { t } = useTranslation();
  const { token, api } = useAuth();
  const { isRTL } = useTheme();
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState(null);
  const [activities, setActivities] = useState([]);
  const [error, setError] = useState(false);

  useEffect(() => {
    const fetchData = async () => {
      setError(false);
      try {
        const headers = { Authorization: `Bearer ${token}` };
        const [profileRes, actRes] = await Promise.all([
          api.get('/student-portal/profile'),
          api.get('/student-portal/activities').catch(() => ({ data: { activities: [] } })),
        ]);
        setProfile(profileRes.data);
        setActivities(actRes.data?.activities || []);
      } catch (err) {
        console.error('Error fetching profile:', err);
        setError(true);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [token]);

  if (loading) {
    return (
      <PortalLayout portalType="student">
        <LoadingState variant="fullpage" />
      </PortalLayout>
    );
  }

  if (error || !profile) {
    return (
      <PortalLayout portalType="student">
        <div className="p-4">
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardContent className="py-16 text-center">
              <AlertCircle className="h-16 w-16 mx-auto mb-4 text-muted-foreground/50" strokeWidth={1.5} aria-hidden="true" />
              <h3 className="font-bold font-cairo text-lg text-foreground mb-4">
                {t('couldNotLoadData')}
              </h3>
              <Button onClick={() => window.location.reload()} className="bg-emerald-600 hover:bg-emerald-700 text-white gap-2">
                <RefreshCw className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />
                {t('retry')}
              </Button>
            </CardContent>
          </Card>
        </div>
      </PortalLayout>
    );
  }

  const student = profile?.student || {};
  const stats = profile?.stats || {};

  return (
    <PortalLayout portalType="student">
      <div className="p-4 space-y-4" data-testid="student-profile-page">
        <Card className="bg-gradient-to-br from-emerald-500 to-teal-600 text-white border-0 rounded-2xl overflow-hidden">
          <CardContent className="p-6">
            <div className="flex flex-col items-center text-center">
              <Avatar className="h-24 w-24 border-4 border-white/30 mb-4">
                <AvatarImage src={student.profile_picture} />
                <AvatarFallback className="bg-white/20 text-white text-3xl font-bold">
                  {student.name?.charAt(0) || 'ط'}
                </AvatarFallback>
              </Avatar>
              <h1 className="text-2xl font-bold font-cairo">{student.name}</h1>
              {student.name_en && <p className="text-emerald-100 text-sm mt-1">{student.name_en}</p>}
              <div className="flex items-center gap-2 mt-2 text-emerald-100">
                <MapPin className="h-4 w-4" />
                <span className="text-sm">{student.school_name}</span>
              </div>
              <div className="flex gap-3 mt-3">
                <Badge className="bg-white/20 text-white border-0 text-sm px-3 py-1">
                  <GraduationCap className="h-3 w-3 me-1" />
                  {student.grade}
                </Badge>
                <Badge className="bg-white/20 text-white border-0 text-sm px-3 py-1">
                  {student.class_name}
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card className="rounded-xl border-0 shadow-sm">
            <CardContent className="p-4 text-center">
              <div className="w-10 h-10 mx-auto mb-2 rounded-lg bg-amber-100 flex items-center justify-center">
                <Star className="h-5 w-5 text-amber-600" />
              </div>
              <p className="text-xl font-bold text-amber-600">{stats.total_points || 0}</p>
              <p className="text-xs text-muted-foreground">{t('totalPoints')}</p>
            </CardContent>
          </Card>

          <Card className="rounded-xl border-0 shadow-sm">
            <CardContent className="p-4 text-center">
              <div className="w-10 h-10 mx-auto mb-2 rounded-lg bg-green-100 flex items-center justify-center">
                <CheckCircle className="h-5 w-5 text-green-600" />
              </div>
              <p className="text-xl font-bold text-green-600">{stats.attendance_rate}%</p>
              <p className="text-xs text-muted-foreground">{isRTL ? 'نسبة الحضور' : 'Attendance'}</p>
            </CardContent>
          </Card>

          <Card className="rounded-xl border-0 shadow-sm">
            <CardContent className="p-4 text-center">
              <div className="w-10 h-10 mx-auto mb-2 rounded-lg bg-blue-100 flex items-center justify-center">
                <TrendingUp className="h-5 w-5 text-blue-600" />
              </div>
              <p className="text-xl font-bold text-blue-600">{stats.average_score}%</p>
              <p className="text-xs text-muted-foreground">{t('average2')}</p>
            </CardContent>
          </Card>

          <Card className="rounded-xl border-0 shadow-sm">
            <CardContent className="p-4 text-center">
              <div className="w-10 h-10 mx-auto mb-2 rounded-lg bg-purple-100 flex items-center justify-center">
                <Award className="h-5 w-5 text-purple-600" />
              </div>
              <p className="text-xl font-bold text-purple-600">{stats.total_grades}</p>
              <p className="text-xs text-muted-foreground">{t('assessments')}</p>
            </CardContent>
          </Card>
        </div>

        <CumulativeAnalytics childId={student.id} viewerRole="student" />

        <Card className="rounded-2xl border-0 shadow-sm">
          <CardContent className="p-4 space-y-4">
            <h2 className="font-bold text-lg font-cairo flex items-center gap-2">
              <User className="h-5 w-5 text-emerald-600" />
              {t('personalInformation2')}
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {student.national_id && (
                <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl">
                  <Hash className="h-5 w-5 text-gray-400" />
                  <div>
                    <p className="text-xs text-muted-foreground">{t('nationalId')}</p>
                    <p className="font-medium text-sm">{student.national_id}</p>
                  </div>
                </div>
              )}

              {student.email && (
                <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl">
                  <Mail className="h-5 w-5 text-gray-400" />
                  <div>
                    <p className="text-xs text-muted-foreground">{t('email2')}</p>
                    <p className="font-medium text-sm">{student.email}</p>
                  </div>
                </div>
              )}

              {student.phone && (
                <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl">
                  <Phone className="h-5 w-5 text-gray-400" />
                  <div>
                    <p className="text-xs text-muted-foreground">{t('phone')}</p>
                    <p className="font-medium text-sm">{student.phone}</p>
                  </div>
                </div>
              )}

              {student.birth_date && (
                <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl">
                  <Calendar className="h-5 w-5 text-gray-400" />
                  <div>
                    <p className="text-xs text-muted-foreground">{t('dateOfBirth')}</p>
                    <p className="font-medium text-sm">{student.birth_date}</p>
                  </div>
                </div>
              )}

              {student.gender && (
                <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl">
                  <User className="h-5 w-5 text-gray-400" />
                  <div>
                    <p className="text-xs text-muted-foreground">{t('gender')}</p>
                    <p className="font-medium text-sm">
                      {student.gender === 'male' ? (t('male')) : (t('female'))}
                    </p>
                  </div>
                </div>
              )}

              {student.enrollment_date && (
                <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl">
                  <Calendar className="h-5 w-5 text-gray-400" />
                  <div>
                    <p className="text-xs text-muted-foreground">{t('enrollmentDate')}</p>
                    <p className="font-medium text-sm">{student.enrollment_date}</p>
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-2xl border-0 shadow-sm">
          <CardContent className="p-4 space-y-3">
            <h2 className="font-bold text-lg font-cairo flex items-center gap-2">
              <Activity className="h-5 w-5 text-purple-600" />
              {isRTL ? 'الأنشطة المشارك بها' : 'Activities Participated In'}
            </h2>

            {activities.length > 0 ? (
              <div className="space-y-2">
                {activities.map((activity, idx) => (
                  <div key={idx} className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl">
                    <div className="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center flex-shrink-0">
                      <Activity className="h-5 w-5 text-purple-600" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm truncate">{activity.name}</p>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground mt-0.5">
                        <span className="flex items-center gap-1">
                          <Calendar className="h-3 w-3" />
                          {activity.date?.slice(0, 10)}
                        </span>
                        <Badge className={`border-0 text-[10px] px-1.5 py-0 ${
                          activity.type === 'sports' ? 'bg-green-100 text-green-700' :
                          activity.type === 'cultural' ? 'bg-blue-100 text-blue-700' :
                          activity.type === 'scientific' ? 'bg-purple-100 text-purple-700' :
                          activity.type === 'social' ? 'bg-amber-100 text-amber-700' :
                          activity.type === 'artistic' ? 'bg-pink-100 text-pink-700' :
                          activity.type === 'volunteer' ? 'bg-teal-100 text-teal-700' :
                          'bg-gray-100 text-gray-700'
                        }`}>
                          {activity.type === 'sports' ? (t('sports')) :
                           activity.type === 'cultural' ? (t('cultural')) :
                           activity.type === 'scientific' ? (t('scientific')) :
                           activity.type === 'social' ? (t('social')) :
                           activity.type === 'artistic' ? (t('artistic')) :
                           activity.type === 'volunteer' ? (t('volunteer')) :
                           (t('other'))}
                        </Badge>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-6 text-muted-foreground">
                <Activity className="h-10 w-10 mx-auto mb-2 opacity-30" />
                <p className="text-sm">{t('noActivitiesRecorded')}</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="rounded-2xl border-0 shadow-sm">
          <CardContent className="p-4 space-y-3">
            <h2 className="font-bold text-lg font-cairo flex items-center gap-2">
              <GraduationCap className="h-5 w-5 text-emerald-600" />
              {t('academicInformation2')}
            </h2>

            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 bg-green-50 rounded-xl">
                <span className="text-sm font-medium">{t('attendanceRate')}</span>
                <span className="font-bold text-green-600">{stats.attendance_rate}%</span>
              </div>
              <Progress value={stats.attendance_rate} className="h-2" />

              <div className="flex items-center justify-between p-3 bg-blue-50 rounded-xl">
                <span className="text-sm font-medium">{isRTL ? 'المعدل العام' : 'Overall Average'}</span>
                <span className="font-bold text-blue-600">{stats.average_score}%</span>
              </div>
              <Progress value={stats.average_score} className="h-2" />

              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-xl">
                <span className="text-sm font-medium">{t('classSize')}</span>
                <span className="font-bold">{stats.class_size}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </PortalLayout>
  );
};

export default StudentProfilePage;
