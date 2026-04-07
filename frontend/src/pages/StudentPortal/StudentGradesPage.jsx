/**
 * Student Portal - Grades Page
 * صفحة الدرجات للطالب
 */

import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme , useTranslation } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Progress } from '../../components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { Skeleton } from '../../components/ui/skeleton';
import { ScrollArea } from '../../components/ui/scroll-area';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  Award,
  BookOpen,
  TrendingUp,
  TrendingDown,
  BarChart3,
  FileText,
} from 'lucide-react';


const StudentGradesPage = () => {
  const { t } = useTranslation();
  const { token, api } = useAuth();
  const { isRTL } = useTheme();
  const [loading, setLoading] = useState(true);
  const [gradesData, setGradesData] = useState(null);
  const [selectedSubject, setSelectedSubject] = useState('all');

  const { nassaqError, nassaqWarning } = useNassaqAlert();
  useEffect(() => {
    fetchGrades();
  }, [token]);

  const fetchGrades = async () => {
    try {
      const response = await api.get('/student-portal/grades');
      setGradesData(response.data);
    } catch (error) {
      console.error('Error fetching grades:', error);
      nassaqError(t('errorFetchingGrades'));
    } finally {
      setLoading(false);
    }
  };

  const getGradeColor = (percentage) => {
    if (percentage >= 90) return 'text-green-600';
    if (percentage >= 75) return 'text-blue-600';
    if (percentage >= 60) return 'text-amber-600';
    return 'text-red-600';
  };

  const getGradeBg = (percentage) => {
    if (percentage >= 90) return 'bg-green-100';
    if (percentage >= 75) return 'bg-blue-100';
    if (percentage >= 60) return 'bg-amber-100';
    return 'bg-red-100';
  };

  const getGradeLabel = (percentage) => {
    if (percentage >= 90) return t('excellent');
    if (percentage >= 80) return t('veryGood');
    if (percentage >= 70) return t('good');
    if (percentage >= 60) return t('pass');
    return t('fail');
  };

  if (loading) {
    return (
      <PortalLayout portalType="student">
        <div className="p-4 space-y-4">
          <Skeleton className="h-32 w-full rounded-2xl" />
          <Skeleton className="h-64 w-full rounded-2xl" />
        </div>
      </PortalLayout>
    );
  }

  return (
    <PortalLayout portalType="student">
      <div className="p-4 space-y-4" data-testid="student-grades-page">
        {/* Summary Card */}
        <Card className="rounded-2xl border-0 shadow-sm bg-gradient-to-br from-blue-500 to-indigo-600 text-white">
          <CardContent className="p-4 md:p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 rounded-2xl bg-white/20 flex items-center justify-center">
                  <Award className="h-8 w-8 text-white" />
                </div>
                <div>
                  <p className="text-blue-100 text-sm">{isRTL ? 'المعدل العام' : 'Overall Average'}</p>
                  <h1 className="text-3xl font-bold">{gradesData?.overall_average || 0}%</h1>
                  <Badge className="bg-white/20 text-white border-0 mt-1">
                    {getGradeLabel(gradesData?.overall_average || 0)}
                  </Badge>
                </div>
              </div>
              <div className="hidden md:block text-center">
                <p className="text-4xl font-bold">{gradesData?.total_grades || 0}</p>
                <p className="text-sm text-blue-100">{t('gradesRecorded')}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Subjects Overview */}
        <Card className="rounded-2xl border-0 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-blue-600" />
              {t('subjectsOverview')}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {gradesData?.subjects?.length > 0 ? (
              <div className="space-y-4">
                {gradesData.subjects.map((subject, idx) => (
                  <div key={idx} className="space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <BookOpen className={`h-4 w-4 ${getGradeColor(subject.average)}`} />
                        <span className="font-medium text-sm">{subject.subject}</span>
                        <Badge variant="outline" className="text-xs">
                          {subject.grades?.length || 0} {t('grades3')}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`font-bold ${getGradeColor(subject.average)}`}>
                          {subject.average}%
                        </span>
                        {subject.average >= 70 ? (
                          <TrendingUp className="h-4 w-4 text-green-500" />
                        ) : (
                          <TrendingDown className="h-4 w-4 text-red-500" />
                        )}
                      </div>
                    </div>
                    <Progress value={subject.average} className="h-2" />
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <Award className="h-12 w-12 mb-3 opacity-30" />
                <p>{t('noGradesRecorded')}</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Detailed Grades by Subject */}
        {gradesData?.subjects?.length > 0 && (
          <Card className="rounded-2xl border-0 shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <FileText className="h-5 w-5 text-blue-600" />
                {t('gradesDetails')}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue={gradesData.subjects[0]?.subject || 'all'} className="w-full">
                <TabsList className="flex flex-wrap gap-1 bg-gray-100 rounded-xl p-1 h-auto">
                  {gradesData.subjects.map((subject) => (
                    <TabsTrigger
                      key={subject.subject}
                      value={subject.subject}
                      className="rounded-lg py-2 px-3 text-xs"
                    >
                      {subject.subject}
                    </TabsTrigger>
                  ))}
                </TabsList>

                {gradesData.subjects.map((subject) => (
                  <TabsContent key={subject.subject} value={subject.subject} className="mt-4">
                    <ScrollArea className="h-[300px]">
                      <div className="space-y-2">
                        {subject.grades?.map((grade, idx) => (
                          <div
                            key={idx}
                            className="flex items-center justify-between p-3 bg-gray-50 rounded-xl hover:bg-gray-100 transition-all"
                          >
                            <div className="flex items-center gap-3">
                              <div className={`w-10 h-10 rounded-lg ${getGradeBg(grade.percentage)} flex items-center justify-center`}>
                                <span className={`font-bold text-sm ${getGradeColor(grade.percentage)}`}>
                                  {grade.percentage}%
                                </span>
                              </div>
                              <div>
                                <p className="font-medium text-sm">{grade.assessment_type}</p>
                                <p className="text-xs text-muted-foreground">{grade.date}</p>
                              </div>
                            </div>
                            <div className="text-end">
                              <Badge variant="outline" className={getGradeColor(grade.percentage)}>
                                {grade.score}/{grade.max_score}
                              </Badge>
                            </div>
                          </div>
                        ))}
                      </div>
                    </ScrollArea>
                  </TabsContent>
                ))}
              </Tabs>
            </CardContent>
          </Card>
        )}
      </div>
    </PortalLayout>
  );
};

export default StudentGradesPage;
