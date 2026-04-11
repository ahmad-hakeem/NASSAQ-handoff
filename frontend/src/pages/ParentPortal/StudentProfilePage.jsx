import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import ProfileEditor from '../../components/parent/ProfileEditor';
import AchievementsArchive from '../../components/parent/AchievementsArchive';
import { Card, CardContent } from '../../components/ui/card';
import { Skeleton } from '../../components/ui/skeleton';
import { Edit3, Award, ChevronLeft, BarChart3, GraduationCap, Building } from 'lucide-react';

const StudentProfilePage = () => {
  const { t } = useTranslation();
  const { childId } = useParams();
  const { api } = useAuth();
  const { isRTL } = useTheme();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [showAchievements, setShowAchievements] = useState(false);

  const fetchProfile = async () => {
    try {
      const res = await api.get(`/parent-portal/child/${childId}/profile`);
      setProfile(res.data);
    } catch {
      setProfile(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, [childId]);

  if (loading) {
    return (
      <PortalLayout portalType="parent">
        <div className="p-4 space-y-4">
          <Skeleton className="h-40 w-full rounded-2xl" />
          <Skeleton className="h-60 w-full rounded-2xl" />
        </div>
      </PortalLayout>
    );
  }

  if (!profile) {
    return (
      <PortalLayout portalType="parent">
        <div className="p-4 text-center text-gray-500 mt-20" dir="rtl">
          <p>لا يمكن عرض ملف الطالب حالياً</p>
          <Link to="/parent" className="text-indigo-600 text-sm mt-2 inline-block">العودة للرئيسية</Link>
        </div>
      </PortalLayout>
    );
  }

  return (
    <PortalLayout portalType="parent">
      <div className="p-4 space-y-4 max-w-lg mx-auto" dir="rtl">
        <div className="flex items-center gap-3 mb-2">
          <Link to="/parent">
            <button className="p-2 rounded-lg hover:bg-gray-100 transition-colors">
              <ChevronLeft className="w-5 h-5 text-gray-600" />
            </button>
          </Link>
          <h1 className="text-lg font-bold text-gray-800">ملف الطالب</h1>
        </div>

        <Card className="rounded-2xl border-0 shadow-sm overflow-hidden">
          <div className="bg-gradient-to-r from-indigo-600 to-purple-700 p-5 text-white">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 rounded-2xl bg-white/20 flex items-center justify-center text-3xl">
                  {profile?.emoji || '👦'}
                </div>
                <div>
                  <h2 className="text-lg font-bold">{profile?.name}</h2>
                  <div className="flex items-center gap-2 mt-1 text-sm opacity-80">
                    <GraduationCap className="w-3.5 h-3.5" />
                    <span>{profile?.class_name} - {profile?.grade_level}</span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5 text-sm opacity-80">
                    <Building className="w-3.5 h-3.5" />
                    <span>{profile?.school_name}</span>
                  </div>
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setShowAchievements(!showAchievements)}
                  className="p-2 rounded-lg bg-white/20 hover:bg-white/30 transition-colors"
                  title="إنجازاتي"
                >
                  <Award className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setEditing(!editing)}
                  className="p-2 rounded-lg bg-white/20 hover:bg-white/30 transition-colors"
                  title="تعديل الملف"
                >
                  <Edit3 className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          <CardContent className="p-4">
            {editing ? (
              <ProfileEditor
                profile={profile}
                childId={childId}
                onSave={() => {
                  setEditing(false);
                  fetchProfile();
                }}
                onCancel={() => setEditing(false)}
              />
            ) : (
              <div className="space-y-4">
                {profile?.health_conditions?.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-gray-500 mb-2">المشاكل الصحية</p>
                    <div className="flex flex-wrap gap-2">
                      {profile.health_conditions.map(c => (
                        <span key={c} className="px-3 py-1 rounded-full bg-red-50 text-red-700 text-xs font-medium">
                          {c === 'asthma' ? 'الربو' : c === 'weak_vision' ? 'ضعف النظر' : c === 'allergy' ? 'الحساسية' : c === 'heart' ? 'مشاكل القلب' : c}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {profile?.behavioral_aspects?.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-gray-500 mb-2">سلوك يحتاج تحسين</p>
                    <div className="flex flex-wrap gap-2">
                      {profile.behavioral_aspects.map(b => (
                        <span key={b} className="px-3 py-1 rounded-full bg-amber-50 text-amber-700 text-xs font-medium">
                          {b === 'shyness' ? 'الخجل' : b === 'hyperactivity' ? 'فرط الحركة' : b === 'concentration_difficulty' ? 'صعوبة التركيز' : b}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {profile?.family_situation && (
                  <div>
                    <p className="text-xs font-medium text-gray-500 mb-1">الوضع العائلي</p>
                    <p className="text-sm text-gray-700">
                      {profile.family_situation === 'both_parents' ? 'مع الوالدين' :
                       profile.family_situation === 'father_only' ? 'مع الأب فقط' :
                       profile.family_situation === 'mother_only' ? 'مع الأم فقط' : 'طرف آخر'}
                    </p>
                  </div>
                )}

                <Link
                  to={`/parent/child/${childId}/analytics`}
                  className="flex items-center gap-3 p-3 rounded-xl bg-indigo-50 hover:bg-indigo-100 transition-colors"
                >
                  <div className="w-10 h-10 rounded-xl bg-indigo-100 text-indigo-600 flex items-center justify-center">
                    <BarChart3 className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-indigo-800">تحليل الأداء التراكمي</p>
                    <p className="text-xs text-indigo-600">عرض التحليل الشامل والرسوم البيانية</p>
                  </div>
                </Link>
              </div>
            )}
          </CardContent>
        </Card>

        {showAchievements && (
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardContent className="p-4">
              <AchievementsArchive childId={childId} />
            </CardContent>
          </Card>
        )}
      </div>
    </PortalLayout>
  );
};

export default StudentProfilePage;
