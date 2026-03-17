import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Progress } from '../../components/ui/progress';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/avatar';
import { Skeleton } from '../../components/ui/skeleton';
import { Button } from '../../components/ui/button';
import axios from 'axios';
import {
  FileText, CheckCircle, TrendingUp, Heart, Users, Star,
  AlertCircle, ChevronDown, ChevronUp
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const ParentReportsPage = () => {
  const { token } = useAuth();
  const { isRTL } = useTheme();
  const [loading, setLoading] = useState(true);
  const [dashboard, setDashboard] = useState(null);
  const [reports, setReports] = useState({});
  const [expandedChild, setExpandedChild] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const headers = { Authorization: `Bearer ${token}` };
        const dashRes = await axios.get(`${API_URL}/api/parent-portal/dashboard`, { headers });
        setDashboard(dashRes.data);

        const children = dashRes.data?.children || [];
        const reportsMap = {};
        for (const child of children) {
          try {
            const r = await axios.get(`${API_URL}/api/parent-portal/child/${child.id}/progress-report`, { headers });
            reportsMap[child.id] = r.data;
          } catch (e) {
            reportsMap[child.id] = null;
          }
        }
        setReports(reportsMap);
        if (children.length > 0) setExpandedChild(children[0].id);
      } catch (err) {
        console.error('Error:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [token]);

  if (loading) {
    return (
      <PortalLayout portalType="parent">
        <div className="p-4 space-y-4">
          <Skeleton className="h-20 rounded-2xl" />
          <Skeleton className="h-64 rounded-2xl" />
        </div>
      </PortalLayout>
    );
  }

  const children = dashboard?.children || [];

  return (
    <PortalLayout portalType="parent">
      <div className="p-4 space-y-4" data-testid="parent-reports-page">
        <div className="flex items-center gap-2 mb-2">
          <FileText className="h-6 w-6 text-indigo-600" />
          <h1 className="text-xl font-bold font-cairo">{isRTL ? 'التقارير' : 'Reports'}</h1>
        </div>

        {children.length === 0 ? (
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardContent className="py-12 text-center">
              <FileText className="h-12 w-12 mx-auto mb-3 text-gray-300" />
              <p className="text-muted-foreground">{isRTL ? 'لا يوجد تقارير' : 'No reports available'}</p>
            </CardContent>
          </Card>
        ) : (
          children.map((child) => {
            const report = reports[child.id];
            const isExpanded = expandedChild === child.id;

            return (
              <Card key={child.id} className="rounded-2xl border-0 shadow-sm overflow-hidden">
                <button
                  onClick={() => setExpandedChild(isExpanded ? null : child.id)}
                  className="w-full p-4 flex items-center justify-between bg-gradient-to-l from-indigo-50 to-purple-50 hover:from-indigo-100 transition-all"
                >
                  <div className="flex items-center gap-3">
                    <Avatar className="h-10 w-10 border-2 border-indigo-200">
                      <AvatarImage src={child.profile_picture} />
                      <AvatarFallback className="bg-indigo-100 text-indigo-600 font-bold">
                        {child.name?.charAt(0)}
                      </AvatarFallback>
                    </Avatar>
                    <div className="text-start">
                      <p className="font-bold text-sm">{child.name}</p>
                      <p className="text-xs text-muted-foreground">{child.grade} - {child.class_name}</p>
                    </div>
                  </div>
                  {isExpanded ? <ChevronUp className="h-5 w-5 text-gray-400" /> : <ChevronDown className="h-5 w-5 text-gray-400" />}
                </button>

                {isExpanded && report && (
                  <CardContent className="p-4 space-y-4">
                    <div className="grid grid-cols-2 gap-3">
                      <div className="p-3 bg-green-50 rounded-xl text-center">
                        <CheckCircle className="h-6 w-6 mx-auto mb-1 text-green-600" />
                        <p className="text-lg font-bold text-green-600">{report.attendance?.rate}%</p>
                        <p className="text-[10px] text-muted-foreground">{isRTL ? 'الحضور' : 'Attendance'}</p>
                      </div>
                      <div className="p-3 bg-blue-50 rounded-xl text-center">
                        <TrendingUp className="h-6 w-6 mx-auto mb-1 text-blue-600" />
                        <p className="text-lg font-bold text-blue-600">{report.academics?.overall_average}%</p>
                        <p className="text-[10px] text-muted-foreground">{isRTL ? 'المعدل' : 'Average'}</p>
                      </div>
                    </div>

                    <div className="space-y-3">
                      <h3 className="text-sm font-bold">{isRTL ? 'تفاصيل الحضور' : 'Attendance Details'}</h3>
                      <div className="grid grid-cols-3 gap-2 text-center text-xs">
                        <div className="p-2 bg-green-50 rounded-lg">
                          <p className="font-bold text-green-600">{report.attendance?.present}</p>
                          <p className="text-muted-foreground">{isRTL ? 'حاضر' : 'Present'}</p>
                        </div>
                        <div className="p-2 bg-red-50 rounded-lg">
                          <p className="font-bold text-red-600">{report.attendance?.absent}</p>
                          <p className="text-muted-foreground">{isRTL ? 'غائب' : 'Absent'}</p>
                        </div>
                        <div className="p-2 bg-amber-50 rounded-lg">
                          <p className="font-bold text-amber-600">{report.attendance?.late}</p>
                          <p className="text-muted-foreground">{isRTL ? 'متأخر' : 'Late'}</p>
                        </div>
                      </div>
                    </div>

                    {report.academics?.subject_averages && Object.keys(report.academics.subject_averages).length > 0 && (
                      <div className="space-y-3">
                        <h3 className="text-sm font-bold">{isRTL ? 'المعدل حسب المادة' : 'Subject Averages'}</h3>
                        {Object.entries(report.academics.subject_averages).map(([subj, avg]) => (
                          <div key={subj}>
                            <div className="flex justify-between text-sm mb-1">
                              <span>{subj}</span>
                              <span className={`font-bold ${
                                avg >= 90 ? 'text-green-600' : avg >= 75 ? 'text-blue-600' : avg >= 60 ? 'text-amber-600' : 'text-red-600'
                              }`}>{avg}%</span>
                            </div>
                            <Progress value={avg} className="h-2" />
                          </div>
                        ))}
                      </div>
                    )}

                    <div className="grid grid-cols-2 gap-3">
                      <div className="p-3 bg-purple-50 rounded-xl">
                        <Heart className="h-5 w-5 text-purple-600 mb-1" />
                        <p className="text-sm font-bold">{isRTL ? 'السلوك' : 'Behavior'}</p>
                        <p className="text-xs text-muted-foreground">
                          {isRTL ? 'إيجابي' : 'Positive'}: {report.behaviour?.positive} | {isRTL ? 'سلبي' : 'Negative'}: {report.behaviour?.negative}
                        </p>
                      </div>
                      <div className="p-3 bg-amber-50 rounded-xl">
                        <Star className="h-5 w-5 text-amber-600 mb-1" />
                        <p className="text-sm font-bold">{isRTL ? 'المشاركة' : 'Participation'}</p>
                        <p className="text-xs text-muted-foreground">
                          {report.participation?.total_points} {isRTL ? 'نقطة' : 'points'}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                )}
              </Card>
            );
          })
        )}
      </div>
    </PortalLayout>
  );
};

export default ParentReportsPage;
