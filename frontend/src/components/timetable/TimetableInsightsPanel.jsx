/**
 * TimetableInsightsPanel Component
 * لوحة الرؤى والتحليلات
 * 
 * يعرض ملخص ذكي وتحليلات النسخة الحالية
 */

import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Skeleton } from '../../components/ui/skeleton';
import { 
  BarChart3, CheckCircle2, AlertTriangle, XCircle, Users,
  GraduationCap, BookOpen, Lightbulb, Activity, TrendingUp,
  Percent, Clock
} from 'lucide-react';

// Simple Stat Item
const StatItem = ({ icon: Icon, label, value, color = 'blue' }) => {
  const colors = {
    blue: 'text-blue-600 bg-blue-50',
    green: 'text-green-600 bg-green-50',
    amber: 'text-amber-600 bg-amber-50',
    red: 'text-red-600 bg-red-50',
    violet: 'text-violet-600 bg-violet-50',
    gray: 'text-gray-600 bg-gray-50'
  };

  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-gray-50/50">
      <div className={`p-2 rounded-lg ${colors[color]}`}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-muted-foreground truncate">{label}</p>
        <p className="text-lg font-bold">{value}</p>
      </div>
    </div>
  );
};

// AI Insight Notice Component
const AIInsightNotice = ({ notes = [] }) => {
  if (!notes || notes.length === 0) return null;

  return (
    <div className="mt-4 p-3 bg-violet-50 border border-violet-200 rounded-lg">
      <h4 className="font-medium text-sm flex items-center gap-2 text-violet-700 mb-2">
        <Lightbulb className="h-4 w-4" />
        ملاحظات الذكاء الاصطناعي
      </h4>
      <ul className="space-y-1">
        {notes.map((note, idx) => (
          <li key={idx} className="text-sm text-violet-600 flex items-start gap-2">
            <span className="text-violet-400 mt-1">•</span>
            {note}
          </li>
        ))}
      </ul>
    </div>
  );
};

// Main Insights Panel Component
const TimetableInsightsPanel = ({
  insights = null,
  loading = false,
  onOpenDiagnostics
}) => {
  if (loading) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <Skeleton className="h-5 w-32" />
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-2">
            {[1, 2, 3, 4].map(i => (
              <Skeleton key={i} className="h-16 rounded-lg" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!insights) {
    return (
      <Card className="border-dashed">
        <CardContent className="py-8 text-center">
          <BarChart3 className="h-10 w-10 mx-auto text-muted-foreground/30 mb-3" />
          <p className="text-sm text-muted-foreground">لا توجد بيانات للتحليل</p>
          <p className="text-xs text-muted-foreground mt-1">قم بتوليد جدول أولاً</p>
        </CardContent>
      </Card>
    );
  }

  const qualityScore = Math.round(insights.qualityScore || 
    (insights.totalRequiredSessions > 0 
      ? (insights.totalAssignedSessions / insights.totalRequiredSessions) * 100
      : 0));

  return (
    <Card data-testid="timetable-insights-panel">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <Activity className="h-4 w-4 text-brand-navy" />
            ملخص وتحليلات
          </CardTitle>
          {onOpenDiagnostics && (
            <Button variant="ghost" size="sm" onClick={onOpenDiagnostics} className="h-7 text-xs">
              التشخيص
            </Button>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Quality Score - Featured */}
        <div className={`p-4 rounded-xl text-center ${
          qualityScore >= 90 ? 'bg-green-50 border border-green-200' :
          qualityScore >= 70 ? 'bg-amber-50 border border-amber-200' :
          'bg-red-50 border border-red-200'
        }`}>
          <div className="flex items-center justify-center gap-2 mb-1">
            <Percent className={`h-5 w-5 ${
              qualityScore >= 90 ? 'text-green-600' :
              qualityScore >= 70 ? 'text-amber-600' :
              'text-red-600'
            }`} />
            <span className="text-sm font-medium text-gray-600">جودة التوزيع</span>
          </div>
          <span className={`text-3xl font-bold ${
            qualityScore >= 90 ? 'text-green-700' :
            qualityScore >= 70 ? 'text-amber-700' :
            'text-red-700'
          }`}>{qualityScore}%</span>
        </div>

        {/* Stats Grid - 2 columns */}
        <div className="grid grid-cols-2 gap-2">
          <StatItem 
            icon={BookOpen} 
            label="الحصص المطلوبة" 
            value={insights.totalRequiredSessions || 0}
            color="blue"
          />
          <StatItem 
            icon={CheckCircle2} 
            label="الحصص الموزعة" 
            value={insights.totalAssignedSessions || 0}
            color="green"
          />
          <StatItem 
            icon={Clock} 
            label="غير موزعة" 
            value={insights.totalUnassignedSessions || 0}
            color={insights.totalUnassignedSessions === 0 ? 'green' : 'red'}
          />
          <StatItem 
            icon={AlertTriangle} 
            label="التحذيرات" 
            value={insights.warningsCount || 0}
            color={insights.warningsCount === 0 ? 'green' : 'amber'}
          />
        </div>

        {/* Secondary Stats */}
        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="p-2 rounded-lg bg-gray-50">
            <XCircle className={`h-4 w-4 mx-auto mb-1 ${
              (insights.hardConflictsCount || 0) === 0 ? 'text-green-500' : 'text-red-500'
            }`} />
            <p className="text-lg font-bold">{insights.hardConflictsCount || 0}</p>
            <p className="text-xs text-muted-foreground">تعارضات</p>
          </div>
          <div className="p-2 rounded-lg bg-gray-50">
            <Users className="h-4 w-4 mx-auto mb-1 text-blue-500" />
            <p className="text-lg font-bold">{insights.affectedTeachersCount || 0}</p>
            <p className="text-xs text-muted-foreground">معلمون</p>
          </div>
          <div className="p-2 rounded-lg bg-gray-50">
            <GraduationCap className="h-4 w-4 mx-auto mb-1 text-violet-500" />
            <p className="text-lg font-bold">{insights.affectedClassesCount || 0}</p>
            <p className="text-xs text-muted-foreground">فصول</p>
          </div>
        </div>

        {/* AI Notes */}
        {insights.aiNotes && insights.aiNotes.length > 0 && (
          <AIInsightNotice notes={insights.aiNotes} />
        )}
      </CardContent>
    </Card>
  );
};

export default TimetableInsightsPanel;
export { StatItem, AIInsightNotice };
