import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Progress } from '../../components/ui/progress';
import { Skeleton } from '../../components/ui/skeleton';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/avatar';
import axios from 'axios';
import {
  User, GraduationCap, MapPin, Calendar, CheckCircle,
  TrendingUp, Star, Award, Mail, Phone, Hash
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const StudentProfilePage = () => {
  const { token } = useAuth();
  const { isRTL } = useTheme();
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState(null);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const res = await axios.get(`${API_URL}/api/student-portal/profile`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setProfile(res.data);
      } catch (err) {
        console.error('Error fetching profile:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchProfile();
  }, [token]);

  if (loading) {
    return (
      <PortalLayout portalType="student">
        <div className="p-4 space-y-4">
          <Skeleton className="h-48 w-full rounded-2xl" />
          <Skeleton className="h-32 w-full rounded-2xl" />
          <Skeleton className="h-32 w-full rounded-2xl" />
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
              <p className="text-xs text-muted-foreground">{isRTL ? 'مجموع النقاط' : 'Total Points'}</p>
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
              <p className="text-xs text-muted-foreground">{isRTL ? 'المعدل العام' : 'Average'}</p>
            </CardContent>
          </Card>

          <Card className="rounded-xl border-0 shadow-sm">
            <CardContent className="p-4 text-center">
              <div className="w-10 h-10 mx-auto mb-2 rounded-lg bg-purple-100 flex items-center justify-center">
                <Award className="h-5 w-5 text-purple-600" />
              </div>
              <p className="text-xl font-bold text-purple-600">{stats.total_grades}</p>
              <p className="text-xs text-muted-foreground">{isRTL ? 'التقييمات' : 'Assessments'}</p>
            </CardContent>
          </Card>
        </div>

        <Card className="rounded-2xl border-0 shadow-sm">
          <CardContent className="p-4 space-y-4">
            <h2 className="font-bold text-lg font-cairo flex items-center gap-2">
              <User className="h-5 w-5 text-emerald-600" />
              {isRTL ? 'المعلومات الشخصية' : 'Personal Information'}
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {student.national_id && (
                <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl">
                  <Hash className="h-5 w-5 text-gray-400" />
                  <div>
                    <p className="text-xs text-muted-foreground">{isRTL ? 'رقم الهوية' : 'National ID'}</p>
                    <p className="font-medium text-sm">{student.national_id}</p>
                  </div>
                </div>
              )}

              {student.email && (
                <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl">
                  <Mail className="h-5 w-5 text-gray-400" />
                  <div>
                    <p className="text-xs text-muted-foreground">{isRTL ? 'البريد الإلكتروني' : 'Email'}</p>
                    <p className="font-medium text-sm">{student.email}</p>
                  </div>
                </div>
              )}

              {student.phone && (
                <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl">
                  <Phone className="h-5 w-5 text-gray-400" />
                  <div>
                    <p className="text-xs text-muted-foreground">{isRTL ? 'الجوال' : 'Phone'}</p>
                    <p className="font-medium text-sm">{student.phone}</p>
                  </div>
                </div>
              )}

              {student.birth_date && (
                <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl">
                  <Calendar className="h-5 w-5 text-gray-400" />
                  <div>
                    <p className="text-xs text-muted-foreground">{isRTL ? 'تاريخ الميلاد' : 'Date of Birth'}</p>
                    <p className="font-medium text-sm">{student.birth_date}</p>
                  </div>
                </div>
              )}

              {student.gender && (
                <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl">
                  <User className="h-5 w-5 text-gray-400" />
                  <div>
                    <p className="text-xs text-muted-foreground">{isRTL ? 'الجنس' : 'Gender'}</p>
                    <p className="font-medium text-sm">
                      {student.gender === 'male' ? (isRTL ? 'ذكر' : 'Male') : (isRTL ? 'أنثى' : 'Female')}
                    </p>
                  </div>
                </div>
              )}

              {student.enrollment_date && (
                <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl">
                  <Calendar className="h-5 w-5 text-gray-400" />
                  <div>
                    <p className="text-xs text-muted-foreground">{isRTL ? 'تاريخ التسجيل' : 'Enrollment Date'}</p>
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
              <GraduationCap className="h-5 w-5 text-emerald-600" />
              {isRTL ? 'المعلومات الأكاديمية' : 'Academic Information'}
            </h2>

            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 bg-green-50 rounded-xl">
                <span className="text-sm font-medium">{isRTL ? 'نسبة الحضور' : 'Attendance Rate'}</span>
                <span className="font-bold text-green-600">{stats.attendance_rate}%</span>
              </div>
              <Progress value={stats.attendance_rate} className="h-2" />

              <div className="flex items-center justify-between p-3 bg-blue-50 rounded-xl">
                <span className="text-sm font-medium">{isRTL ? 'المعدل العام' : 'Overall Average'}</span>
                <span className="font-bold text-blue-600">{stats.average_score}%</span>
              </div>
              <Progress value={stats.average_score} className="h-2" />

              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-xl">
                <span className="text-sm font-medium">{isRTL ? 'عدد الطلاب في الفصل' : 'Class Size'}</span>
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
