import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import ProfileEditor from '../../components/parent/ProfileEditor';
import AchievementsArchive from '../../components/parent/AchievementsArchive';
import { Card, CardContent } from '../../components/ui/card';
import { Skeleton } from '../../components/ui/skeleton';
import { Edit3, Award, ChevronLeft, BarChart3, GraduationCap, Building, Heart, Eye, Wind, ShieldAlert } from 'lucide-react';

const HEALTH_LABELS = {
  asthma: { ar: 'الربو', en: 'Asthma', icon: Wind, color: 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-300' },
  weak_vision: { ar: 'ضعف النظر', en: 'Weak Vision', icon: Eye, color: 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300' },
  allergy: { ar: 'الحساسية', en: 'Allergies', icon: ShieldAlert, color: 'bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' },
  heart: { ar: 'مشاكل القلب', en: 'Heart Issues', icon: Heart, color: 'bg-pink-50 text-pink-700 dark:bg-pink-900/30 dark:text-pink-300' },
};

const BEHAVIOR_LABELS = {
  shyness: { ar: 'الخجل', en: 'Shyness', icon: '🙈' },
  hyperactivity: { ar: 'فرط الحركة', en: 'Hyperactivity', icon: '⚡' },
  concentration_difficulty: { ar: 'صعوبة التركيز', en: 'Difficulty Concentrating', icon: '🎯' },
};

const FAMILY_LABELS = {
  both_parents: { ar: 'مع الوالدين', en: 'Both Parents' },
  father_only: { ar: 'مع الأب فقط', en: 'Father Only' },
  mother_only: { ar: 'مع الأم فقط', en: 'Mother Only' },
  other: { ar: 'طرف آخر', en: 'Other' },
};

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
        <div className="p-4 text-center text-gray-500 mt-20" dir={isRTL ? 'rtl' : 'ltr'}>
          <p>{isRTL ? 'لا يمكن عرض ملف الطالب حالياً' : 'Unable to display student profile'}</p>
          <Link to="/parent" className="text-indigo-600 text-sm mt-2 inline-block">
            {isRTL ? 'العودة للرئيسية' : 'Back to Home'}
          </Link>
        </div>
      </PortalLayout>
    );
  }

  return (
    <PortalLayout portalType="parent">
      <div className="p-4 space-y-4 max-w-lg mx-auto" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="flex items-center gap-3 mb-2">
          <Link to="/parent">
            <button className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
              <ChevronLeft className={`w-5 h-5 text-gray-600 dark:text-gray-400 ${isRTL ? 'rotate-180' : ''}`} />
            </button>
          </Link>
          <h1 className="text-lg font-bold text-gray-800 dark:text-gray-200">
            {isRTL ? 'ملف الطالب' : 'Student Profile'}
          </h1>
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
                  onClick={() => { setShowAchievements(!showAchievements); if (!showAchievements) setEditing(false); }}
                  className={`p-2 rounded-lg transition-colors ${showAchievements ? 'bg-white/30' : 'bg-white/20 hover:bg-white/30'}`}
                  title={isRTL ? 'إنجازاتي' : 'My Achievements'}
                >
                  <Award className="w-4 h-4" />
                </button>
                <button
                  onClick={() => { setEditing(!editing); if (!editing) setShowAchievements(false); }}
                  className={`p-2 rounded-lg transition-colors ${editing ? 'bg-white/30' : 'bg-white/20 hover:bg-white/30'}`}
                  title={isRTL ? 'تعديل الملف' : 'Edit Profile'}
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
                    <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">
                      {isRTL ? 'المشاكل الصحية' : 'Health Conditions'}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {profile.health_conditions.map(c => {
                        const cfg = HEALTH_LABELS[c];
                        const Icon = cfg?.icon;
                        return (
                          <span key={c} className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ${cfg?.color || 'bg-gray-100 text-gray-700'}`}>
                            {Icon && <Icon className="w-3 h-3" />}
                            {cfg ? (isRTL ? cfg.ar : cfg.en) : c}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                )}

                {profile?.behavioral_aspects?.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">
                      {isRTL ? 'سلوك يحتاج تحسين' : 'Behavioral Aspects'}
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {profile.behavioral_aspects.map(b => {
                        const cfg = BEHAVIOR_LABELS[b];
                        return (
                          <span key={b} className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300 text-xs font-medium">
                            {cfg?.icon && <span>{cfg.icon}</span>}
                            {cfg ? (isRTL ? cfg.ar : cfg.en) : b}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                )}

                {profile?.family_situation && (
                  <div>
                    <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                      {isRTL ? 'الوضع العائلي' : 'Family Situation'}
                    </p>
                    <p className="text-sm text-gray-700 dark:text-gray-300">
                      {FAMILY_LABELS[profile.family_situation]
                        ? (isRTL ? FAMILY_LABELS[profile.family_situation].ar : FAMILY_LABELS[profile.family_situation].en)
                        : profile.family_situation}
                    </p>
                  </div>
                )}

                <Link
                  to={`/parent/child/${childId}/analytics`}
                  className="flex items-center gap-3 p-3 rounded-xl bg-indigo-50 hover:bg-indigo-100 dark:bg-indigo-900/20 dark:hover:bg-indigo-900/30 transition-colors"
                >
                  <div className="w-10 h-10 rounded-xl bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400 flex items-center justify-center">
                    <BarChart3 className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-indigo-800 dark:text-indigo-300">
                      {isRTL ? 'تحليل الأداء التراكمي' : 'Cumulative Performance Analysis'}
                    </p>
                    <p className="text-xs text-indigo-600 dark:text-indigo-400">
                      {isRTL ? 'عرض التحليل الشامل والرسوم البيانية' : 'View comprehensive analysis and charts'}
                    </p>
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
