import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme , useTranslation } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Progress } from '../../components/ui/progress';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/avatar';
import { Button } from '../../components/ui/button';
import { Skeleton } from '../../components/ui/skeleton';
import {
  Users, GraduationCap, CheckCircle, TrendingUp, Calendar,
  ChevronLeft, BookOpen, ClipboardList, Heart, MessageSquare, AlertCircle
} from 'lucide-react';


const ParentChildrenPage = () => {
  const { t } = useTranslation();
  const { token, user, api } = useAuth();
  const { isRTL } = useTheme();
  const [loading, setLoading] = useState(true);
  const [children, setChildren] = useState([]);

  useEffect(() => {
    const fetchChildren = async () => {
      try {
        const res = await api.get('/parent-portal/children');
        setChildren(res.data.children || []);
      } catch (err) {
        console.error('Error:', err);
        try {
          const res2 = await api.get('/parent-portal/dashboard');
          setChildren(res2.data.children || []);
        } catch (e2) { console.error('Error fetching children fallback:', e2); setChildren([]); }
      } finally {
        setLoading(false);
      }
    };
    fetchChildren();
  }, [token]);

  if (loading) {
    return (
      <PortalLayout portalType="parent">
        <div className="p-4 space-y-4">
          {[1, 2].map(i => <Skeleton key={i} className="h-48 rounded-2xl" />)}
        </div>
      </PortalLayout>
    );
  }

  return (
    <PortalLayout portalType="parent">
      <div className="p-4 space-y-4" data-testid="parent-children-page">
        <div className="flex items-center gap-2 mb-2">
          <Users className="h-6 w-6 text-indigo-600" />
          <h1 className="text-xl font-bold font-cairo">{t('myChildren')}</h1>
          <Badge className="bg-indigo-100 text-indigo-700 border-0 ms-auto">
            {children.length} {t('children')}
          </Badge>
        </div>

        {children.length === 0 ? (
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardContent className="py-16 text-center">
              <Users className="h-16 w-16 mx-auto mb-4 text-gray-300" />
              <h3 className="font-bold text-lg text-gray-700 mb-2">
                {t('noChildrenEnrolled')}
              </h3>
              <p className="text-muted-foreground text-sm">
                {t('contactSchoolAdministrationToLinkYourAccount')}
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            {children.map((child) => (
              <Card key={child.id} className="rounded-2xl border-0 shadow-sm overflow-hidden">
                <div className="bg-gradient-to-l from-indigo-50 to-purple-50 p-4">
                  <div className="flex items-center gap-4">
                    <Avatar className="h-16 w-16 border-2 border-indigo-200">
                      <AvatarImage src={child.photo_url || child.profile_picture} />
                      <AvatarFallback className="bg-indigo-100 text-indigo-600 font-bold text-xl">
                        {child.name?.charAt(0)}
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex-1">
                      <h2 className="font-cairo font-bold text-lg">{child.name}</h2>
                      <p className="text-sm text-muted-foreground">
                        {child.grade} - {child.class_name}
                      </p>
                      <p className="text-xs text-muted-foreground">{child.school_name}</p>
                    </div>
                  </div>
                </div>

                <CardContent className="p-4 space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="flex items-center gap-2 p-3 bg-green-50 rounded-xl">
                      <CheckCircle className="h-5 w-5 text-green-600" />
                      <div>
                        <p className="text-sm font-bold text-green-600">{child.attendance_rate}%</p>
                        <p className="text-[10px] text-muted-foreground">{t('attendance2')}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 p-3 bg-blue-50 rounded-xl">
                      <TrendingUp className="h-5 w-5 text-blue-600" />
                      <div>
                        <p className="text-sm font-bold text-blue-600">{child.average_score || 0}%</p>
                        <p className="text-[10px] text-muted-foreground">{t('average')}</p>
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                    <Link to={`/parent/child/${child.id}`}>
                      <Button variant="outline" size="sm" className="w-full text-xs h-9">
                        <GraduationCap className="h-3 w-3 me-1" />
                        {t('details')}
                      </Button>
                    </Link>
                    <Link to={`/parent/child/${child.id}/schedule`}>
                      <Button variant="outline" size="sm" className="w-full text-xs h-9">
                        <Calendar className="h-3 w-3 me-1" />
                        {t('schedule')}
                      </Button>
                    </Link>
                    <Link to={`/parent/child/${child.id}/homework`}>
                      <Button variant="outline" size="sm" className="w-full text-xs h-9">
                        <ClipboardList className="h-3 w-3 me-1" />
                        {t('homework')}
                      </Button>
                    </Link>
                    <Link to={`/parent/child/${child.id}/behaviour`}>
                      <Button variant="outline" size="sm" className="w-full text-xs h-9">
                        <Heart className="h-3 w-3 me-1" />
                        {t('behavior')}
                      </Button>
                    </Link>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </PortalLayout>
  );
};

export default ParentChildrenPage;
