/**
 * Student Grades Page
 * صفحة درجات الطالب
 */

import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { Sidebar } from '../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { ScrollArea } from '../components/ui/scroll-area';
import { Skeleton } from '../components/ui/skeleton';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import {
  TrendingUp,
  BookOpen,
  Award,
  Target,
  BarChart3,
} from 'lucide-react';


export const StudentGrades = () => {
  const { t } = useTranslation();
  const { token, api } = useAuth();
  const { isRTL } = useTheme();
  const [loading, setLoading] = useState(true);
  const [grades, setGrades] = useState(null);
  const [selectedSubject, setSelectedSubject] = useState('all');

  useEffect(() => {
    fetchGrades();
  }, [token]);

  const fetchGrades = async () => {
    try {
      const response = await api.get('/student-portal/grades');
      setGrades(response.data);
    } catch (error) {
      console.error('Error fetching grades:', error);
    } finally {
      setLoading(false);
    }
  };

  const getGradeColor = (percentage) => {
    if (percentage >= 90) return 'text-green-600 bg-green-500/10';
    if (percentage >= 75) return 'text-blue-600 bg-blue-500/10';
    if (percentage >= 60) return 'text-amber-600 bg-amber-500/10';
    return 'text-red-600 bg-red-500/10';
  };

  const getGradeLabel = (percentage) => {
    if (percentage >= 90) return t('excellent');
    if (percentage >= 75) return t('veryGood');
    if (percentage >= 60) return t('good');
    return isRTL ? 'يحتاج تحسين' : 'Needs Improvement';
  };

  const filteredSubjects = selectedSubject === 'all' 
    ? grades?.subjects 
    : grades?.subjects?.filter(s => s.subject === selectedSubject);

  if (loading) {
    return (
      <Sidebar>
        <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 p-4 md:p-6">
          <Skeleton className="h-10 w-48 mb-6" />
          <div className="grid gap-4">
            {[1, 2, 3].map(i => <Skeleton key={i} className="h-32 rounded-xl" />)}
          </div>
        </div>
      </Sidebar>
    );
  }

  return (
    <Sidebar>
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 p-4 md:p-6" dir={isRTL ? 'rtl' : 'ltr'}>
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold font-cairo text-brand-navy dark:text-white flex items-center gap-3">
              <TrendingUp className="h-8 w-8 text-brand-turquoise" />
              {t('myGrades')}
            </h1>
            <p className="text-muted-foreground mt-1">
              {t('viewAllGradesAndAssessments')}
            </p>
          </div>
          
          <Select value={selectedSubject} onValueChange={setSelectedSubject}>
            <SelectTrigger className="w-[200px] rounded-xl">
              <SelectValue placeholder={isRTL ? 'اختر المادة' : 'Select Subject'} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('allSubjects')}</SelectItem>
              {grades?.subjects?.map(s => (
                <SelectItem key={s.subject} value={s.subject}>{s.subject}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Overall Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <Card className="card-nassaq">
            <CardContent className="p-4 text-center">
              <Award className="h-8 w-8 mx-auto mb-2 text-brand-turquoise" />
              <p className="text-2xl font-bold">{grades?.overall_average}%</p>
              <p className="text-xs text-muted-foreground">{isRTL ? 'المعدل العام' : 'Overall Average'}</p>
            </CardContent>
          </Card>
          <Card className="card-nassaq">
            <CardContent className="p-4 text-center">
              <BookOpen className="h-8 w-8 mx-auto mb-2 text-brand-purple" />
              <p className="text-2xl font-bold">{grades?.subjects?.length || 0}</p>
              <p className="text-xs text-muted-foreground">{t('subjects')}</p>
            </CardContent>
          </Card>
          <Card className="card-nassaq">
            <CardContent className="p-4 text-center">
              <BarChart3 className="h-8 w-8 mx-auto mb-2 text-amber-500" />
              <p className="text-2xl font-bold">{grades?.total_grades || 0}</p>
              <p className="text-xs text-muted-foreground">{t('assessments')}</p>
            </CardContent>
          </Card>
          <Card className="card-nassaq">
            <CardContent className="p-4 text-center">
              <Target className="h-8 w-8 mx-auto mb-2 text-green-500" />
              <p className="text-2xl font-bold">{getGradeLabel(grades?.overall_average || 0)}</p>
              <p className="text-xs text-muted-foreground">{t('grade6')}</p>
            </CardContent>
          </Card>
        </div>

        {/* Subjects */}
        <div className="space-y-4">
          {filteredSubjects?.map((subject, idx) => (
            <Card key={idx} className="card-nassaq">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg flex items-center gap-2">
                    <BookOpen className="h-5 w-5 text-brand-navy" />
                    {subject.subject}
                  </CardTitle>
                  <Badge className={getGradeColor(subject.average)}>
                    {subject.average}% - {getGradeLabel(subject.average)}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <Progress value={subject.average} className="h-2 mb-4" />
                
                <ScrollArea className="max-h-[200px]">
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {subject.grades?.map((grade, gIdx) => (
                      <div key={gIdx} className="p-3 bg-muted/30 rounded-lg">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm font-medium">{grade.assessment_type}</span>
                          <Badge variant="outline" className={getGradeColor(grade.percentage)}>
                            {grade.score}/{grade.max_score}
                          </Badge>
                        </div>
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                          <span>{grade.percentage}%</span>
                          <span>{grade.date}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          ))}

          {(!filteredSubjects || filteredSubjects.length === 0) && (
            <Card className="card-nassaq">
              <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <TrendingUp className="h-16 w-16 mb-4 opacity-30" />
                <p className="text-lg">{t('noGradesYet')}</p>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </Sidebar>
  );
};

export default StudentGrades;
