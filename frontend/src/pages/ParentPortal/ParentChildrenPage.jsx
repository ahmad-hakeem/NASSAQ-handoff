import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTranslation } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/avatar';
import { Button } from '../../components/ui/button';
import { Skeleton } from '../../components/ui/skeleton';
import {
  Users, GraduationCap, CheckCircle, TrendingUp, Calendar,
  ClipboardList, Heart,
} from 'lucide-react';

const ParentChildrenPage = () => {
  const { t } = useTranslation();
  const { token, api } = useAuth();
  const [loading, setLoading] = useState(true);
  const [children, setChildren] = useState([]);

  useEffect(() => {
    let cancelled = false;
    const fetchChildren = async () => {
      try {
        const res = await api.get('/parent-portal/children');
        if (!cancelled) setChildren(res.data.children || []);
      } catch {
        try {
          const res2 = await api.get('/parent-portal/dashboard');
          if (!cancelled) setChildren(res2.data.children || []);
        } catch {
          if (!cancelled) setChildren([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchChildren();
    return () => { cancelled = true; };
  }, [token, api]);

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
          <Users className="h-6 w-6 text-brand-navy dark:text-brand-turquoise" />
          <h1 className="text-xl font-bold font-cairo text-foreground">{t('myChildren')}</h1>
          <Badge className="bg-brand-navy/15 dark:bg-brand-turquoise/20 text-brand-navy dark:text-brand-turquoise border-0 ms-auto">
            {children.length} {t('children')}
          </Badge>
        </div>

        {children.length === 0 ? (
          <Card className="rounded-2xl border-0 shadow-sm bg-card">
            <CardContent className="py-16 text-center">
              <Users className="h-16 w-16 mx-auto mb-4 text-muted-foreground/50" />
              <h3 className="font-cairo font-bold text-lg text-foreground mb-2">
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
              <Card
                key={child.id}
                className="rounded-2xl border border-border shadow-sm overflow-hidden bg-card"
              >
                {/* Hero strip — brand-tinted in both themes, never fades to white */}
                <div className="bg-gradient-to-l from-brand-navy/5 to-brand-purple/5 dark:from-brand-turquoise/10 dark:to-brand-purple/15 p-4 border-b border-border">
                  <div className="flex items-center gap-4">
                    <Avatar className="h-16 w-16 border-2 border-brand-navy/20 dark:border-brand-turquoise/30">
                      <AvatarImage src={child.photo_url || child.profile_picture} />
                      <AvatarFallback className="bg-brand-navy/15 dark:bg-brand-turquoise/20 text-brand-navy dark:text-brand-turquoise font-bold text-xl">
                        {child.name?.charAt(0)}
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex-1 min-w-0">
                      <h2 className="font-cairo font-bold text-lg text-foreground truncate">
                        {child.name}
                      </h2>
                      <p className="text-sm text-muted-foreground truncate">
                        {child.grade} - {child.class_name}
                      </p>
                      <p className="text-xs text-muted-foreground truncate">{child.school_name}</p>
                    </div>
                  </div>
                </div>

                <CardContent className="p-4 space-y-3">
                  {/* KPI rows — tinted accent surfaces with explicit dark variants */}
                  <div className="grid grid-cols-2 gap-3">
                    <div className="flex items-center gap-3 p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-100 dark:border-emerald-900/40">
                      <span className="w-9 h-9 rounded-lg bg-emerald-100 dark:bg-emerald-900/50 text-emerald-700 dark:text-emerald-300 flex items-center justify-center shrink-0">
                        <CheckCircle className="h-5 w-5" />
                      </span>
                      <div className="min-w-0">
                        <p className="text-sm font-bold text-emerald-700 dark:text-emerald-300 tabular-nums">
                          {child.attendance_rate}%
                        </p>
                        <p className="text-[10px] text-muted-foreground font-tajawal">{t('attendance2')}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 p-3 rounded-xl bg-blue-50 dark:bg-blue-950/30 border border-blue-100 dark:border-blue-900/40">
                      <span className="w-9 h-9 rounded-lg bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 flex items-center justify-center shrink-0">
                        <TrendingUp className="h-5 w-5" />
                      </span>
                      <div className="min-w-0">
                        <p className="text-sm font-bold text-blue-700 dark:text-blue-300 tabular-nums">
                          {child.average_score || 0}%
                        </p>
                        <p className="text-[10px] text-muted-foreground font-tajawal">{t('average')}</p>
                      </div>
                    </div>
                  </div>

                  {/* Action buttons — outline variant already uses semantic tokens */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                    <Link to={`/parent/child/${child.id}`}>
                      <Button variant="outline" size="sm" className="w-full text-xs h-9 border-border bg-card hover:bg-muted/40 dark:hover:bg-muted/30 text-foreground">
                        <GraduationCap className="h-3 w-3 me-1" />
                        {t('details')}
                      </Button>
                    </Link>
                    <Link to={`/parent/child/${child.id}/schedule`}>
                      <Button variant="outline" size="sm" className="w-full text-xs h-9 border-border bg-card hover:bg-muted/40 dark:hover:bg-muted/30 text-foreground">
                        <Calendar className="h-3 w-3 me-1" />
                        {t('schedule')}
                      </Button>
                    </Link>
                    <Link to={`/parent/child/${child.id}/homework`}>
                      <Button variant="outline" size="sm" className="w-full text-xs h-9 border-border bg-card hover:bg-muted/40 dark:hover:bg-muted/30 text-foreground">
                        <ClipboardList className="h-3 w-3 me-1" />
                        {t('homework')}
                      </Button>
                    </Link>
                    <Link to={`/parent/child/${child.id}/behaviour`}>
                      <Button variant="outline" size="sm" className="w-full text-xs h-9 border-border bg-card hover:bg-muted/40 dark:hover:bg-muted/30 text-foreground">
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
