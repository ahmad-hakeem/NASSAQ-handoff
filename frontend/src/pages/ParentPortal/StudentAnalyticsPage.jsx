import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTranslation } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { GaugeChart, PerformanceLine, SubjectRadar } from '../../components/parent/AnalyticsCharts';
import { Card, CardContent } from '../../components/ui/card';
import { Skeleton } from '../../components/ui/skeleton';
import { ChevronLeft, TrendingUp, TrendingDown, Activity, CheckCircle, AlertTriangle, ShieldAlert } from 'lucide-react';

const StudentAnalyticsPage = () => {
  const { t } = useTranslation();
  const { childId } = useParams();
  const { api } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await api.get(`/parent-portal/child/${childId}/analytics`);
        setData(res.data);
      } catch {
        setData(null);
      } finally {
        setLoading(false);
      }
    };
    fetch();
  }, [childId]);

  if (loading) {
    return (
      <PortalLayout portalType="parent">
        <div className="p-4 space-y-4">
          <Skeleton className="h-10 w-48 rounded-xl" />
          <Skeleton className="h-40 w-full rounded-2xl" />
          <Skeleton className="h-60 w-full rounded-2xl" />
          <Skeleton className="h-64 w-full rounded-2xl" />
        </div>
      </PortalLayout>
    );
  }

  if (!data) {
    return (
      <PortalLayout portalType="parent">
        <div className="p-4 text-center text-gray-500 mt-20">
          <p>لا توجد بيانات تحليلية متاحة حالياً</p>
        </div>
      </PortalLayout>
    );
  }

  const followUpConfig = {
    'مستقر': { color: 'bg-emerald-50 text-emerald-700 border-emerald-200', icon: CheckCircle, barColor: 'bg-emerald-500' },
    'يحتاج متابعة': { color: 'bg-amber-50 text-amber-700 border-amber-200', icon: AlertTriangle, barColor: 'bg-amber-500' },
    'بحاجة دعم': { color: 'bg-red-50 text-red-700 border-red-200', icon: ShieldAlert, barColor: 'bg-red-500' },
  };

  const fuConf = followUpConfig[data.follow_up?.status] || followUpConfig['مستقر'];
  const FuIcon = fuConf.icon;

  return (
    <PortalLayout portalType="parent">
      <div className="p-4 space-y-4 max-w-lg mx-auto" dir="rtl">
        <div className="flex items-center gap-3 mb-2">
          <Link to={`/parent/child/${childId}/profile`}>
            <button className="p-2 rounded-lg hover:bg-gray-100 transition-colors">
              <ChevronLeft className="w-5 h-5 text-gray-600" />
            </button>
          </Link>
          <div>
            <h1 className="text-lg font-bold font-cairo text-gray-800">تحليل الأداء</h1>
            <p className="text-xs text-gray-500">{data.student_name}</p>
          </div>
        </div>

        <Card className="rounded-2xl border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="p-3 rounded-xl bg-brand-navy/5">
                <p className="text-2xl font-bold text-brand-navy">{data.summary?.overall_average}%</p>
                <p className="text-xs text-brand-navy mt-1">المتوسط العام</p>
              </div>
              <div className="p-3 rounded-xl bg-blue-50">
                <p className="text-2xl font-bold text-blue-700">{data.summary?.class_average}%</p>
                <p className="text-xs text-blue-600 mt-1">متوسط الفصل</p>
              </div>
              <div className="p-3 rounded-xl bg-brand-purple/5">
                <p className="text-2xl font-bold text-brand-purple">{data.summary?.total_assessments}</p>
                <p className="text-xs text-brand-purple mt-1">التقييمات</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="rounded-2xl border-0 shadow-sm">
          <CardContent className="p-4">
            <p className="text-sm font-semibold font-cairo text-gray-700 mb-3">مستوى الأداء الحالي</p>
            <GaugeChart value={data.gauge_data?.value || 0} level={data.gauge_data?.level || ''} />
          </CardContent>
        </Card>

        <Card className="rounded-2xl border-0 shadow-sm">
          <CardContent className="p-4">
            <p className="text-sm font-semibold font-cairo text-gray-700 mb-3">اتجاه الأداء</p>
            <PerformanceLine data={data.line_chart_data} />
          </CardContent>
        </Card>

        <Card className="rounded-2xl border-0 shadow-sm">
          <CardContent className="p-4">
            <p className="text-sm font-semibold font-cairo text-gray-700 mb-3">توزيع النتائج في المواد</p>
            <SubjectRadar data={data.radar_data} />
          </CardContent>
        </Card>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {data.strengths?.length > 0 && (
            <Card className="rounded-2xl border-0 shadow-sm">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-3">
                  <TrendingUp className="w-4 h-4 text-emerald-600" />
                  <p className="text-sm font-semibold font-cairo text-gray-700">نقاط القوة</p>
                </div>
                <div className="space-y-2">
                  {data.strengths.map((s, i) => (
                    <div key={i} className="p-2.5 rounded-lg bg-emerald-50 border border-emerald-100">
                      <p className="text-sm font-medium text-emerald-800">{s.area}</p>
                      <p className="text-xs text-emerald-600">{s.detail}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {data.weaknesses?.length > 0 && (
            <Card className="rounded-2xl border-0 shadow-sm">
              <CardContent className="p-4">
                <div className="flex items-center gap-2 mb-3">
                  <TrendingDown className="w-4 h-4 text-amber-600" />
                  <p className="text-sm font-semibold font-cairo text-gray-700">يحتاج تحسين</p>
                </div>
                <div className="space-y-2">
                  {data.weaknesses.map((w, i) => (
                    <div key={i} className="p-2.5 rounded-lg bg-amber-50 border border-amber-100">
                      <p className="text-sm font-medium text-amber-800">{w.area}</p>
                      <p className="text-xs text-amber-600">{w.detail}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        <Card className="rounded-2xl border-0 shadow-sm">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-gray-600" />
                <p className="text-sm font-semibold font-cairo text-gray-700">مؤشر المتابعة المنزلية</p>
              </div>
              <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${fuConf.color}`}>
                <FuIcon className="w-3.5 h-3.5" />
                {data.follow_up?.status}
              </span>
            </div>
            <div className="space-y-2.5">
              <BreakdownBar label="الحضور" value={data.follow_up?.breakdown?.attendance_rate} color={fuConf.barColor} />
              <BreakdownBar label="الواجبات" value={data.follow_up?.breakdown?.homework_rate} color={fuConf.barColor} />
              <BreakdownBar label="المشاركة" value={data.follow_up?.breakdown?.participation_score} color={fuConf.barColor} />
              <BreakdownBar label="الأكاديمي" value={data.follow_up?.breakdown?.academic_average} color={fuConf.barColor} />
            </div>
          </CardContent>
        </Card>
      </div>
    </PortalLayout>
  );
};

const BreakdownBar = ({ label, value, color }) => (
  <div className="flex items-center gap-3">
    <span className="text-xs text-gray-500 w-16 shrink-0">{label}</span>
    <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
      <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(value || 0, 100)}%` }} />
    </div>
    <span className="text-xs font-medium text-gray-600 w-10 text-left tabular-nums">{Math.round(value || 0)}%</span>
  </div>
);

export default StudentAnalyticsPage;
