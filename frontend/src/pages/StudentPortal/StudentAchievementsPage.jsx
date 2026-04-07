import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme , useTranslation } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Skeleton } from '../../components/ui/skeleton';
import {
  Trophy, Star, TrendingUp, CheckCircle, ClipboardCheck,
  Award, Heart, Lock, AlertCircle
} from 'lucide-react';


const ICON_MAP = {
  'star': Star,
  'trending-up': TrendingUp,
  'check-circle': CheckCircle,
  'clipboard-check': ClipboardCheck,
  'award': Award,
  'heart': Heart,
};

const COLOR_MAP = {
  'gold': { bg: 'bg-amber-100', text: 'text-amber-600', border: 'border-amber-200', gradient: 'from-amber-400 to-yellow-500' },
  'green': { bg: 'bg-green-100', text: 'text-green-600', border: 'border-green-200', gradient: 'from-green-400 to-emerald-500' },
  'blue': { bg: 'bg-blue-100', text: 'text-blue-600', border: 'border-blue-200', gradient: 'from-blue-400 to-indigo-500' },
  'purple': { bg: 'bg-purple-100', text: 'text-purple-600', border: 'border-purple-200', gradient: 'from-purple-400 to-violet-500' },
  'red': { bg: 'bg-red-100', text: 'text-red-600', border: 'border-red-200', gradient: 'from-red-400 to-rose-500' },
};

const AchievementCard = ({ achievement, isRTL, earned = true }) => {
  const { t } = useTranslation();
  const IconComponent = ICON_MAP[achievement.icon] || Star;
  const colors = COLOR_MAP[achievement.color] || COLOR_MAP.gold;

  return (
    <Card className={`rounded-2xl border-0 shadow-sm overflow-hidden transition-all ${
      earned ? 'hover:shadow-md' : 'opacity-50'
    }`}>
      <CardContent className="p-4">
        <div className="flex items-center gap-4">
          <div className={`w-14 h-14 rounded-xl flex items-center justify-center ${
            earned ? `bg-gradient-to-br ${colors.gradient}` : 'bg-gray-200'
          }`}>
            {earned ? (
              <IconComponent className="h-7 w-7 text-white" />
            ) : (
              <Lock className="h-6 w-6 text-gray-400" />
            )}
          </div>
          <div className="flex-1">
            <h3 className="font-bold text-sm">
              {isRTL ? achievement.title_ar : achievement.title_en}
            </h3>
            <p className="text-xs text-muted-foreground mt-1">
              {isRTL ? achievement.description_ar : achievement.description_en}
            </p>
          </div>
          {earned && (
            <Badge className={`${colors.bg} ${colors.text} ${colors.border} border text-xs`}>
              {t('earned')}
            </Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

const StudentAchievementsPage = () => {
  const { token, api } = useAuth();
  const { isRTL } = useTheme();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);

  useEffect(() => {
    const fetchAchievements = async () => {
      try {
        const res = await api.get('/student-portal/achievements');
        setData(res.data);
      } catch (err) {
        console.error('Error fetching achievements:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchAchievements();
  }, [token]);

  if (loading) {
    return (
      <PortalLayout portalType="student">
        <div className="p-4 space-y-4">
          <Skeleton className="h-24 rounded-2xl" />
          {[1, 2, 3].map(i => <Skeleton key={i} className="h-20 rounded-2xl" />)}
        </div>
      </PortalLayout>
    );
  }

  if (!data) {
    return (
      <PortalLayout portalType="student">
        <div className="p-4">
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardContent className="py-16 text-center">
              <AlertCircle className="h-16 w-16 mx-auto mb-4 text-gray-300" />
              <p className="text-muted-foreground">{t('couldNotLoadData')}</p>
            </CardContent>
          </Card>
        </div>
      </PortalLayout>
    );
  }

  return (
    <PortalLayout portalType="student">
      <div className="p-4 space-y-4" data-testid="student-achievements-page">
        <Card className="bg-gradient-to-br from-amber-400 to-yellow-500 text-white border-0 rounded-2xl">
          <CardContent className="p-6 text-center">
            <Trophy className="h-12 w-12 mx-auto mb-3" />
            <h1 className="text-2xl font-bold font-cairo">
              {t('myAchievements')}
            </h1>
            <p className="text-amber-100 mt-2">
              {data.total_earned} / {data.total_possible} {t('achievementsEarned')}
            </p>
            <div className="flex justify-center gap-1 mt-3">
              {Array.from({ length: data.total_possible }).map((_, i) => (
                <div
                  key={i}
                  className={`w-8 h-2 rounded-full ${
                    i < data.total_earned ? 'bg-white' : 'bg-white/30'
                  }`}
                />
              ))}
            </div>
          </CardContent>
        </Card>

        {data.earned?.length > 0 && (
          <>
            <h2 className="font-bold text-lg font-cairo flex items-center gap-2 px-1">
              <Award className="h-5 w-5 text-amber-500" />
              {t('earnedAchievements')}
            </h2>
            <div className="space-y-3">
              {data.earned.map(a => (
                <AchievementCard key={a.id} achievement={a} isRTL={isRTL} earned={true} />
              ))}
            </div>
          </>
        )}

        {data.locked?.length > 0 && (
          <>
            <h2 className="font-bold text-lg font-cairo flex items-center gap-2 px-1 mt-4">
              <Lock className="h-5 w-5 text-gray-400" />
              {t('lockedAchievements')}
            </h2>
            <div className="space-y-3">
              {data.locked.map(a => (
                <AchievementCard key={a.id} achievement={a} isRTL={isRTL} earned={false} />
              ))}
            </div>
          </>
        )}
      </div>
    </PortalLayout>
  );
};

export default StudentAchievementsPage;
