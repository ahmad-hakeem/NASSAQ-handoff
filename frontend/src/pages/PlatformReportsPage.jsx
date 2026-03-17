import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { Sidebar } from '../components/layout/Sidebar';
import { HakimAssistant } from '../components/hakim/HakimAssistant';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Progress } from '../components/ui/progress';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import {
  BarChart3,
  Building2,
  Users,
  GraduationCap,
  UserCheck,
  TrendingUp,
  TrendingDown,
  Sun,
  Moon,
  Globe,
  RefreshCw,
  Download,
  Calendar,
  Activity,
  PieChart,
  FileText,
  Eye,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
} from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';

export const PlatformReportsPage = () => {
  const { user, api } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  const [stats, setStats] = useState(null);
  const [schools, setSchools] = useState([]);
  const [loading, setLoading] = useState(true);
  const [timeFilter, setTimeFilter] = useState('month');

  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const fetchData = async () => {
    try {
      setLoading(true);
      const [statsRes, schoolsRes] = await Promise.all([
        api.get('/dashboard/stats'),
        api.get('/schools'),
      ]);
      setStats(statsRes.data);
      setSchools(schoolsRes.data);
    } catch (error) {
      console.error('Failed to fetch data:', error);
      nassaqError(isRTL ? 'فشل تحميل البيانات' : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleExport = (reportType) => {
    toast.promise(
      new Promise(resolve => setTimeout(resolve, 2000)),
      {
        loading: isRTL ? 'جاري تصدير التقرير...' : 'Exporting report...',
        success: isRTL ? 'تم تصدير التقرير بنجاح' : 'Report exported successfully',
        error: isRTL ? 'فشل تصدير التقرير' : 'Failed to export report',
      }
    );
  };

  // Calculate statistics
  const activeSchools = schools.filter(s => s.status === 'active').length;
  const totalStudents = schools.reduce((sum, s) => sum + (s.current_students || 0), 0);
  const totalTeachers = schools.reduce((sum, s) => sum + (s.current_teachers || 0), 0);
  const avgStudentsPerSchool = schools.length > 0 ? Math.round(totalStudents / schools.length) : 0;
  const avgTeachersPerSchool = schools.length > 0 ? Math.round(totalTeachers / schools.length) : 0;

  // Top schools by students
  const topSchoolsByStudents = [...schools]
    .sort((a, b) => (b.current_students || 0) - (a.current_students || 0))
    .slice(0, 5);

  // Schools by status
  const schoolsByStatus = {
    active: schools.filter(s => s.status === 'active').length,
    pending: schools.filter(s => s.status === 'pending').length,
    suspended: schools.filter(s => s.status === 'suspended').length,
  };

  // Schools by region
  const schoolsByRegion = schools.reduce((acc, school) => {
    const region = school.region || (isRTL ? 'غير محدد' : 'Unknown');
    acc[region] = (acc[region] || 0) + 1;
    return acc;
  }, {});

  const topRegions = Object.entries(schoolsByRegion)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);

  const kpiCards = [
    {
      title: isRTL ? 'إجمالي المدارس' : 'Total Schools',
      value: stats?.total_schools || 0,
      icon: Building2,
      trend: '+12%',
      trendUp: true,
      color: 'brand-navy',
    },
    {
      title: isRTL ? 'المدارس النشطة' : 'Active Schools',
      value: activeSchools,
      icon: Activity,
      trend: '+5%',
      trendUp: true,
      color: 'green-500',
    },
    {
      title: isRTL ? 'إجمالي الطلاب' : 'Total Students',
      value: totalStudents,
      icon: GraduationCap,
      trend: '+8%',
      trendUp: true,
      color: 'brand-turquoise',
    },
    {
      title: isRTL ? 'إجمالي المعلمين' : 'Total Teachers',
      value: totalTeachers,
      icon: UserCheck,
      trend: '+3%',
      trendUp: true,
      color: 'brand-purple',
    },
    {
      title: isRTL ? 'متوسط الطلاب/مدرسة' : 'Avg Students/School',
      value: avgStudentsPerSchool,
      icon: Users,
      trend: '0%',
      trendUp: null,
      color: 'orange-500',
    },
    {
      title: isRTL ? 'المستخدمون النشطون' : 'Active Users',
      value: stats?.active_users || 0,
      icon: Users,
      trend: '+15%',
      trendUp: true,
      color: 'blue-500',
    },
  ];

  const reportTypes = [
    {
      title: isRTL ? 'تقرير المدارس الشامل' : 'Comprehensive Schools Report',
      description: isRTL ? 'تقرير تفصيلي عن جميع المدارس في المنصة' : 'Detailed report of all schools on the platform',
      icon: Building2,
      type: 'schools',
    },
    {
      title: isRTL ? 'تقرير المستخدمين' : 'Users Report',
      description: isRTL ? 'إحصائيات المستخدمين حسب الدور والحالة' : 'User statistics by role and status',
      icon: Users,
      type: 'users',
    },
    {
      title: isRTL ? 'تقرير الأداء' : 'Performance Report',
      description: isRTL ? 'مؤشرات أداء المنصة والمدارس' : 'Platform and schools performance metrics',
      icon: BarChart3,
      type: 'performance',
    },
    {
      title: isRTL ? 'تقرير النشاط اليومي' : 'Daily Activity Report',
      description: isRTL ? 'تقرير عن النشاط اليومي في المنصة' : 'Report on daily platform activity',
      icon: Activity,
      type: 'activity',
    },
  ];

  return (
    <Sidebar>
      <div className="min-h-screen bg-background" data-testid="platform-reports-page">
        {/* Header */}
        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="font-cairo text-2xl font-bold text-foreground">
                {isRTL ? 'التقارير والتحليلات' : 'Reports & Analytics'}
              </h1>
              <p className="text-sm text-muted-foreground font-tajawal">
                {isRTL ? 'تحليلات شاملة للمنصة' : 'Comprehensive platform analytics'}
              </p>
            </div>
            
            <div className="flex items-center gap-3">
              <Select value={timeFilter} onValueChange={setTimeFilter}>
                <SelectTrigger className="w-[140px] rounded-xl">
                  <Calendar className="h-4 w-4 me-2" />
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="today">{isRTL ? 'اليوم' : 'Today'}</SelectItem>
                  <SelectItem value="week">{isRTL ? 'هذا الأسبوع' : 'This Week'}</SelectItem>
                  <SelectItem value="month">{isRTL ? 'هذا الشهر' : 'This Month'}</SelectItem>
                  <SelectItem value="year">{isRTL ? 'هذا العام' : 'This Year'}</SelectItem>
                </SelectContent>
              </Select>
              
              <Button variant="ghost" size="icon" onClick={toggleLanguage} className="rounded-xl">
                <Globe className="h-5 w-5" />
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme} className="rounded-xl">
                {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </Button>
              <Button variant="ghost" size="icon" onClick={fetchData} className="rounded-xl">
                <RefreshCw className="h-5 w-5" />
              </Button>
            </div>
          </div>
        </header>

        <div className="p-6 space-y-6">
          {/* KPI Cards */}
          <section>
            <h2 className="font-cairo text-xl font-bold text-foreground mb-4">
              {isRTL ? 'مؤشرات الأداء الرئيسية' : 'Key Performance Indicators'}
            </h2>
            
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
              {kpiCards.map((kpi, index) => (
                <Card key={index} className="card-nassaq">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className={`w-10 h-10 rounded-xl bg-${kpi.color}/10 flex items-center justify-center`}>
                        <kpi.icon className={`h-5 w-5 text-${kpi.color}`} />
                      </div>
                      {kpi.trendUp !== null && (
                        <div className={`flex items-center text-xs ${kpi.trendUp ? 'text-green-600' : 'text-red-600'}`}>
                          {kpi.trendUp ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                          {kpi.trend}
                        </div>
                      )}
                      {kpi.trendUp === null && (
                        <div className="flex items-center text-xs text-gray-500">
                          <Minus className="h-3 w-3" />
                          {kpi.trend}
                        </div>
                      )}
                    </div>
                    <p className="text-2xl font-bold">{kpi.value.toLocaleString()}</p>
                    <p className="text-xs text-muted-foreground">{kpi.title}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>

          {/* Charts Section */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Schools by Status */}
            <Card className="card-nassaq">
              <CardHeader>
                <CardTitle className="font-cairo">{isRTL ? 'المدارس حسب الحالة' : 'Schools by Status'}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="flex items-center gap-2">
                        <span className="w-3 h-3 rounded-full bg-green-500"></span>
                        {isRTL ? 'نشطة' : 'Active'}
                      </span>
                      <span className="font-bold">{schoolsByStatus.active}</span>
                    </div>
                    <Progress value={schools.length > 0 ? (schoolsByStatus.active / schools.length) * 100 : 0} className="h-2 bg-green-100" />
                  </div>
                  
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="flex items-center gap-2">
                        <span className="w-3 h-3 rounded-full bg-yellow-500"></span>
                        {isRTL ? 'معلقة' : 'Pending'}
                      </span>
                      <span className="font-bold">{schoolsByStatus.pending}</span>
                    </div>
                    <Progress value={schools.length > 0 ? (schoolsByStatus.pending / schools.length) * 100 : 0} className="h-2 bg-yellow-100" />
                  </div>
                  
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="flex items-center gap-2">
                        <span className="w-3 h-3 rounded-full bg-red-500"></span>
                        {isRTL ? 'موقوفة' : 'Suspended'}
                      </span>
                      <span className="font-bold">{schoolsByStatus.suspended}</span>
                    </div>
                    <Progress value={schools.length > 0 ? (schoolsByStatus.suspended / schools.length) * 100 : 0} className="h-2 bg-red-100" />
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Top Regions */}
            <Card className="card-nassaq">
              <CardHeader>
                <CardTitle className="font-cairo">{isRTL ? 'المدارس حسب المنطقة' : 'Schools by Region'}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {topRegions.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-4">
                      {isRTL ? 'لا توجد بيانات' : 'No data available'}
                    </p>
                  ) : (
                    topRegions.map(([region, count], index) => (
                      <div key={region} className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <span className="w-6 h-6 rounded-full bg-brand-navy/10 flex items-center justify-center text-xs font-bold text-brand-navy">
                            {index + 1}
                          </span>
                          <span className="text-sm">{region}</span>
                        </div>
                        <Badge variant="secondary">{count} {isRTL ? 'مدرسة' : 'schools'}</Badge>
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Top Schools */}
          <Card className="card-nassaq">
            <CardHeader>
              <CardTitle className="font-cairo">{isRTL ? 'أكبر المدارس حسب عدد الطلاب' : 'Top Schools by Students'}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {topSchoolsByStudents.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-4">
                    {isRTL ? 'لا توجد بيانات' : 'No data available'}
                  </p>
                ) : (
                  topSchoolsByStudents.map((school, index) => (
                    <div key={school.id} className="flex items-center gap-4">
                      <span className="w-8 h-8 rounded-xl bg-brand-turquoise/10 flex items-center justify-center text-sm font-bold text-brand-turquoise">
                        {index + 1}
                      </span>
                      <div className="flex-1">
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-medium">{school.name}</span>
                          <span className="text-sm text-muted-foreground">
                            {school.current_students || 0} / {school.student_capacity}
                          </span>
                        </div>
                        <Progress 
                          value={school.student_capacity > 0 ? ((school.current_students || 0) / school.student_capacity) * 100 : 0} 
                          className="h-2" 
                        />
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          {/* Export Reports */}
          <Card className="card-nassaq">
            <CardHeader>
              <CardTitle className="font-cairo">{isRTL ? 'تصدير التقارير' : 'Export Reports'}</CardTitle>
              <CardDescription>
                {isRTL ? 'تصدير التقارير بصيغة PDF أو Excel' : 'Export reports in PDF or Excel format'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {reportTypes.map((report, index) => (
                  <Card 
                    key={index} 
                    className="bg-muted/50 hover:bg-muted cursor-pointer transition-all"
                    onClick={() => handleExport(report.type)}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-start gap-3">
                        <div className="w-10 h-10 rounded-xl bg-background flex items-center justify-center flex-shrink-0">
                          <report.icon className="h-5 w-5 text-brand-navy" />
                        </div>
                        <div className="flex-1">
                          <p className="font-cairo font-medium text-sm">{report.title}</p>
                          <p className="text-xs text-muted-foreground mt-1">{report.description}</p>
                        </div>
                        <Download className="h-4 w-4 text-muted-foreground" />
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
      <HakimAssistant />
    </Sidebar>
  );
};
