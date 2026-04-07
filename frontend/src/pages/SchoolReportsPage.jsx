import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { Sidebar } from '../components/layout/Sidebar';
import { HakimAssistant } from '../components/hakim/HakimAssistant';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import {
  BarChart3,
  LineChart,
  PieChart,
  TrendingUp,
  TrendingDown,
  Users,
  GraduationCap,
  BookOpen,
  Calendar,
  Clock,
  Sun,
  Moon,
  Globe,
  Download,
  FileText,
  Filter,
  RefreshCw,
  Loader2,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Award,
  Target,
  Percent,
  ArrowUpRight,
  ArrowDownRight,
  CalendarDays,
  Heart,
  Trophy,
} from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Progress } from '../components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/table';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from 'recharts';

export const SchoolReportsPage = () => {
  const { t } = useTranslation();
  const { user, api } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  
  // State
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedPeriod, setSelectedPeriod] = useState('current_term');
  const [selectedClass, setSelectedClass] = useState('all');
  
  // Data
  const [classes, setClasses] = useState([]);
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const [stats, setStats] = useState({
    total_students: 0,
    total_teachers: 0,
    total_classes: 0,
    attendance_rate: 0,
    avg_grade: 0,
  });
  
  // Mock data for reports
  const [attendanceData, setAttendanceData] = useState([]);
  const [gradeData, setGradeData] = useState([]);
  const [behaviorData, setBehaviorData] = useState([]);
  const [behaviorNotes, setBehaviorNotes] = useState([]);
  const [topClasses, setTopClasses] = useState([]);
  
  // Trend data from reporting engine
  const [attendanceTrend, setAttendanceTrend] = useState([]);
  const [participationTrend, setParticipationTrend] = useState([]);
  const [atRiskStudents, setAtRiskStudents] = useState([]);

  // Hakim AI state
  const [hakimAnalysis, setHakimAnalysis] = useState(null);
  const [hakimLoading, setHakimLoading] = useState(false);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        // Fetch data from APIs
        const [classesRes, overviewRes, attendanceRes, gradesRes, behaviorRes, topClassesRes] = await Promise.all([
          api.get(`/classes?school_id=${user?.tenant_id}`).catch(() => ({ data: [] })),
          api.get(`/reports/school/overview?period=${selectedPeriod}`).catch(() => ({ data: null })),
          api.get(`/reports/school/attendance?period=${selectedPeriod}`).catch(() => ({ data: [] })),
          api.get(`/reports/school/grades?period=${selectedPeriod}`).catch(() => ({ data: [] })),
          api.get(`/reports/school/behavior?period=${selectedPeriod}`).catch(() => ({ data: null })),
          api.get(`/reports/school/top-classes`).catch(() => ({ data: [] })),
        ]);
        
        setClasses(classesRes.data || []);
        
        // Set statistics from API - no fallback to mock data
        if (overviewRes.data) {
          setStats({
            total_students: overviewRes.data.total_students || 0,
            total_teachers: overviewRes.data.total_teachers || 0,
            total_classes: overviewRes.data.total_classes || 0,
            attendance_rate: overviewRes.data.attendance_rate || 0,
            avg_grade: overviewRes.data.avg_grade || 0,
            positive_behavior: overviewRes.data.positive_behavior || (behaviorRes.data?.stats?.positive || 0),
          });
        } else {
          // Empty state - no mock data
          setStats({
            total_students: 0,
            total_teachers: 0,
            total_classes: 0,
            attendance_rate: 0,
            avg_grade: 0,
            positive_behavior: 0,
          });
        }
        
        // Set attendance data from API - no fallback to mock data
        if (attendanceRes.data && attendanceRes.data.length > 0) {
          setAttendanceData(attendanceRes.data);
        } else {
          // Empty state
          setAttendanceData([]);
        }
        
        // Set grade data from API - no fallback to mock data
        if (gradesRes.data && gradesRes.data.length > 0) {
          setGradeData(gradesRes.data);
        } else {
          // Empty state
          setGradeData([]);
        }
        
        // Set behavior data from API
        if (behaviorRes.data) {
          const behaviorStats = behaviorRes.data.stats || {};
          setBehaviorData([
            { type: 'positive', count: behaviorStats.positive || 0, change: 0 },
            { type: 'negative', count: behaviorStats.negative || 0, change: 0 },
            { type: 'warning', count: behaviorStats.warning || 0, change: 0 },
            { type: 'appreciation', count: behaviorStats.appreciation || 0, change: 0 },
          ]);
          setBehaviorNotes(behaviorRes.data.recent_notes || []);
        } else {
          setBehaviorData([]);
          setBehaviorNotes([]);
        }
        
        // Set top classes
        setTopClasses(topClassesRes.data || []);
        
      } catch (error) {
        console.error('Failed to fetch data:', error);
      } finally {
        setLoading(false);
      }
    };
    
    loadData();
  }, [user, selectedPeriod, selectedClass, api]);

  useEffect(() => {
    const fetchTrendData = async () => {
      if (!user?.tenant_id) return;
      const endDate = new Date().toISOString().split('T')[0];
      const startDate = new Date(Date.now() - 90 * 86400000).toISOString().split('T')[0];
      try {
        const [attRes, partRes] = await Promise.all([
          api.get(`/reports/generate/school_attendance?start_date=${startDate}&end_date=${endDate}`).catch(() => null),
          api.get(`/reports/generate/school_participation?start_date=${startDate}&end_date=${endDate}`).catch(() => null),
        ]);
        if (attRes?.data?.data?.weekly) {
          setAttendanceTrend(attRes.data.data.weekly.map(w => ({
            week: w.week, rate: w.rate, present: w.present, absent: w.absent,
          })));
        }
        if (partRes?.data?.data?.trend) {
          setParticipationTrend(partRes.data.data.trend.map(item => ({
            week: item.week, interactions: item.interactions,
          })));
        }
      } catch (err) {
        console.error('Trend data fetch error:', err);
      }
    };
    fetchTrendData();
  }, [user, api]);

  useEffect(() => {
    const fetchHakimData = async () => {
      if (!user?.tenant_id) return;
      setHakimLoading(true);
      try {
        const resp = await api.post(`/hakim/analyze/${user.tenant_id}`, {});
        if (resp.data) {
          setHakimAnalysis(resp.data);
          if (resp.data.at_risk_students) {
            setAtRiskStudents(resp.data.at_risk_students.filter(s => 
              s.risk_category === 'critical' || s.risk_category === 'high'
            ).slice(0, 10));
          }
        }
      } catch (err) {
        try {
          const insightsResp = await api.get(`/hakim/insights?school_id=${user.tenant_id}&limit=20`);
          if (insightsResp.data?.length > 0) {
            const fullAnalysis = insightsResp.data.find(i => i.type === 'full_school_analysis');
            if (fullAnalysis?.data) {
              setHakimAnalysis({
                school_id: user.tenant_id,
                risk_counts: fullAnalysis.data.risk_counts || {},
                at_risk_students_count: fullAnalysis.data.at_risk_students?.length || 0,
                insights: fullAnalysis.data.insights || [],
                class_health_summary: fullAnalysis.data.class_healths || [],
                analyzed_at: fullAnalysis.created_at,
              });
              if (fullAnalysis.data.at_risk_students) {
                setAtRiskStudents(fullAnalysis.data.at_risk_students.filter(s =>
                  s.risk_category === 'critical' || s.risk_category === 'high'
                ).slice(0, 10));
              }
            }
          }
        } catch (fallbackErr) {
          console.error('Hakim insights fallback error:', fallbackErr);
        }
      } finally {
        setHakimLoading(false);
      }
    };
    fetchHakimData();
  }, [user, api]);

  const handleExport = async (format) => {
    try {
      toast.info(t('preparingReport'));
      const fmtMap = { PDF: 'pdf', CSV: 'csv', Excel: 'xlsx' };
      const fmt = fmtMap[format] || 'pdf';
      const reportTypeMap = {
        overview: 'school_attendance',
        attendance: 'school_attendance',
        grades: 'school_academic',
        behavior: 'school_behaviour',
      };
      const reportType = reportTypeMap[activeTab] || 'school_attendance';

      const resp = await api.get(`/export/report/${reportType}?format=${fmt}`, {
        responseType: 'blob',
      });
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report_${reportType}.${fmt}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      toast.success(t('reportExportedSuccessfully'));
    } catch (error) {
      console.error('Export error:', error);
      nassaqError(t('failedToExportReport'));
    }
  };

  const StatCard = ({ title, value, icon: Icon, change, changeType, color }) => {
    const { t } = useTranslation();
    return (
    <Card className="card-nassaq">
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{title}</p>
            <p className="text-3xl font-bold mt-1">{value}</p>
            {change !== undefined && (
              <div className={`flex items-center gap-1 mt-2 text-sm ${
                changeType === 'positive' ? 'text-green-600' : 'text-red-600'
              }`}>
                {changeType === 'positive' ? (
                  <ArrowUpRight className="h-4 w-4" />
                ) : (
                  <ArrowDownRight className="h-4 w-4" />
                )}
                <span>{change}%</span>
              </div>
            )}
          </div>
          <div className={`h-14 w-14 rounded-2xl ${color} flex items-center justify-center`}>
            <Icon className="h-7 w-7 text-white" />
          </div>
        </div>
      </CardContent>
    </Card>
    );
  };

  if (loading) {
    return (
      <Sidebar>
        <div className="flex items-center justify-center min-h-screen">
          <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
        </div>
      </Sidebar>
    );
  }

  return (
    <Sidebar>
      <div className="min-h-screen bg-background" data-testid="school-reports-page">
        {/* Header */}
        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="font-cairo text-2xl font-bold text-foreground">
                {isRTL ? 'التقارير والتحليلات' : 'Reports & Analytics'}
              </h1>
              <p className="text-sm text-muted-foreground font-tajawal">
                {t('comprehensiveSchoolPerformanceReports')}
              </p>
            </div>
            
            <div className="flex items-center gap-3">
              <Select value={selectedPeriod} onValueChange={setSelectedPeriod}>
                <SelectTrigger className="w-[180px] rounded-xl">
                  <Calendar className="h-4 w-4 me-2" />
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="current_term">{t('currentTerm')}</SelectItem>
                  <SelectItem value="last_term">{t('lastTerm')}</SelectItem>
                  <SelectItem value="current_year">{t('currentYear')}</SelectItem>
                  <SelectItem value="last_year">{t('lastYear2')}</SelectItem>
                </SelectContent>
              </Select>
              
              <div className="flex gap-1">
                <Button variant="outline" onClick={() => handleExport('PDF')} className="rounded-xl" size="sm">
                  <Download className="h-4 w-4 me-1" /> PDF
                </Button>
                <Button variant="outline" onClick={() => handleExport('CSV')} className="rounded-xl" size="sm">
                  CSV
                </Button>
                <Button variant="outline" onClick={() => handleExport('Excel')} className="rounded-xl" size="sm">
                  Excel
                </Button>
              </div>
              
              <Button variant="ghost" size="icon" onClick={toggleLanguage} className="rounded-xl">
                <Globe className="h-5 w-5" />
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme} className="rounded-xl">
                {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </Button>
            </div>
          </div>
        </header>

        <div className="p-6 space-y-6">
          {/* Stats Overview */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            <StatCard
              title={t('totalStudents')}
              value={stats.total_students}
              icon={GraduationCap}
              change={5.2}
              changeType="positive"
              color="bg-brand-turquoise"
            />
            <StatCard
              title={t('totalTeachers')}
              value={stats.total_teachers}
              icon={Users}
              change={2.1}
              changeType="positive"
              color="bg-brand-purple"
            />
            <StatCard
              title={t('classes2')}
              value={stats.total_classes}
              icon={BookOpen}
              color="bg-brand-navy"
            />
            <StatCard
              title={t('attendanceRate')}
              value={`${stats.attendance_rate}%`}
              icon={CheckCircle}
              change={1.5}
              changeType="positive"
              color="bg-green-500"
            />
            <StatCard
              title={t('positiveBehavior')}
              value={behaviorData.find(b => b.type === 'positive')?.count || 0}
              icon={Target}
              change={behaviorData.find(b => b.type === 'positive')?.change || 0}
              changeType="positive"
              color="bg-amber-500"
            />
          </div>

          {/* Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
            <TabsList className="grid grid-cols-4 gap-2 bg-muted/50 p-1 rounded-xl">
              <TabsTrigger value="overview" className="rounded-lg data-[state=active]:bg-background" data-testid="tab-overview">
                <BarChart3 className="h-4 w-4 me-2" />
                {t('overview')}
              </TabsTrigger>
              <TabsTrigger value="attendance" className="rounded-lg data-[state=active]:bg-background" data-testid="tab-attendance">
                <CheckCircle className="h-4 w-4 me-2" />
                {t('attendance2')}
              </TabsTrigger>
              <TabsTrigger value="grades" className="rounded-lg data-[state=active]:bg-background" data-testid="tab-grades">
                <Award className="h-4 w-4 me-2" />
                {t('grades')}
              </TabsTrigger>
              <TabsTrigger value="behavior" className="rounded-lg data-[state=active]:bg-background" data-testid="tab-behavior">
                <Target className="h-4 w-4 me-2" />
                {t('behavior')}
              </TabsTrigger>
            </TabsList>

            {/* Overview Tab */}
            <TabsContent value="overview" className="space-y-6">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Attendance Overview */}
                <Card className="card-nassaq">
                  <CardHeader>
                    <CardTitle className="font-cairo flex items-center gap-2">
                      <CheckCircle className="h-5 w-5 text-green-500" />
                      {t('attendanceSummary')}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {(() => {
                      // Calculate totals from attendanceData
                      const totalPresent = attendanceData.reduce((sum, row) => sum + (row.present || 0), 0);
                      const totalAbsent = attendanceData.reduce((sum, row) => sum + (row.absent || 0), 0);
                      const totalLate = attendanceData.reduce((sum, row) => sum + (row.late || 0), 0);
                      const totalRecords = totalPresent + totalAbsent + totalLate;
                      const attendanceRate = totalRecords > 0 ? ((totalPresent / totalRecords) * 100).toFixed(1) : 0;
                      
                      return (
                        <div className="space-y-4">
                          <div className="flex items-center justify-between">
                            <span className="text-sm">{t('overallAttendance2')}</span>
                            <span className="font-bold text-green-600">{attendanceRate}%</span>
                          </div>
                          <Progress value={parseFloat(attendanceRate)} className="h-3" />
                          
                          <div className="grid grid-cols-3 gap-4 mt-6">
                            <div className="text-center p-4 rounded-xl bg-green-50 dark:bg-green-900/20">
                              <CheckCircle className="h-8 w-8 mx-auto text-green-500 mb-2" />
                              <p className="text-2xl font-bold text-green-600">{totalPresent}</p>
                              <p className="text-xs text-muted-foreground">{t('present')}</p>
                            </div>
                            <div className="text-center p-4 rounded-xl bg-red-50 dark:bg-red-900/20">
                              <XCircle className="h-8 w-8 mx-auto text-red-500 mb-2" />
                              <p className="text-2xl font-bold text-red-600">{totalAbsent}</p>
                              <p className="text-xs text-muted-foreground">{t('absent')}</p>
                            </div>
                            <div className="text-center p-4 rounded-xl bg-yellow-50 dark:bg-yellow-900/20">
                              <Clock className="h-8 w-8 mx-auto text-yellow-500 mb-2" />
                              <p className="text-2xl font-bold text-yellow-600">{totalLate}</p>
                              <p className="text-xs text-muted-foreground">{t('late')}</p>
                            </div>
                          </div>
                        </div>
                      );
                    })()}
                  </CardContent>
                </Card>

                {/* Behavior Overview - Replacing Grades */}
                <Card className="card-nassaq">
                  <CardHeader>
                    <CardTitle className="font-cairo flex items-center gap-2">
                      <Heart className="h-5 w-5 text-green-500" />
                      {t('positiveBehavior')}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {(() => {
                      const positiveCount = behaviorData.find(b => b.type === 'positive')?.count || 0;
                      const negativeCount = behaviorData.find(b => b.type === 'negative')?.count || 0;
                      const warningCount = behaviorData.find(b => b.type === 'warning')?.count || 0;
                      const appreciationCount = behaviorData.find(b => b.type === 'appreciation')?.count || 0;
                      const totalBehavior = positiveCount + negativeCount + warningCount + appreciationCount;
                      const positiveRate = totalBehavior > 0 ? (((positiveCount + appreciationCount) / totalBehavior) * 100).toFixed(1) : 0;
                      
                      return (
                        <div className="space-y-4">
                          <div className="flex items-center justify-between">
                            <span className="text-sm">{t('positiveBehaviorRate')}</span>
                            <span className="font-bold text-green-600">{positiveRate}%</span>
                          </div>
                          <Progress value={parseFloat(positiveRate)} className="h-3" />
                          
                          <div className="grid grid-cols-4 gap-4 mt-6">
                            <div className="text-center p-3 rounded-xl bg-green-50 dark:bg-green-900/20">
                              <p className="text-xl font-bold text-green-600">{positiveCount}</p>
                              <p className="text-xs text-muted-foreground">{t('positive')}</p>
                            </div>
                            <div className="text-center p-3 rounded-xl bg-blue-50 dark:bg-blue-900/20">
                              <p className="text-xl font-bold text-blue-600">{appreciationCount}</p>
                              <p className="text-xs text-muted-foreground">{t('appreciation')}</p>
                            </div>
                            <div className="text-center p-3 rounded-xl bg-yellow-50 dark:bg-yellow-900/20">
                              <p className="text-xl font-bold text-yellow-600">{warningCount}</p>
                              <p className="text-xs text-muted-foreground">{t('warning')}</p>
                            </div>
                            <div className="text-center p-3 rounded-xl bg-red-50 dark:bg-red-900/20">
                              <p className="text-xl font-bold text-red-600">{negativeCount}</p>
                              <p className="text-xs text-muted-foreground">{t('negative')}</p>
                            </div>
                          </div>
                        </div>
                      );
                    })()}
                  </CardContent>
                </Card>
              </div>

              {/* Top Performers */}
              <Card className="card-nassaq">
                <CardHeader>
                  <CardTitle className="font-cairo flex items-center gap-2">
                    <TrendingUp className="h-5 w-5 text-brand-turquoise" />
                    {t('topPerformingClasses')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {topClasses.length === 0 ? (
                    <div className="text-center py-8">
                      <Trophy className="h-10 w-10 mx-auto text-muted-foreground/30 mb-3" />
                      <p className="text-muted-foreground">{t('notEnoughDataToDetermineTopClasses')}</p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      {topClasses.slice(0, 3).map((item, index) => (
                        <Card key={item.class_id} className="border-2 border-brand-gold/30">
                          <CardContent className="p-4">
                            <div className="flex items-center gap-4">
                              <div className={`h-12 w-12 rounded-full flex items-center justify-center ${
                                index === 0 ? 'bg-yellow-400' : index === 1 ? 'bg-gray-300' : 'bg-amber-600'
                              }`}>
                                <span className="text-xl font-bold text-white">{index + 1}</span>
                              </div>
                              <div className="flex-1">
                                <p className="font-medium">{item.class_name}</p>
                                <p className="text-2xl font-bold text-brand-turquoise">{item.score}%</p>
                                <p className="text-xs text-muted-foreground mt-1">{item.rank_reason}</p>
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Hakim AI Insights Section */}
              <Card className="card-nassaq border-2 border-purple-200 dark:border-purple-800">
                <CardHeader>
                  <CardTitle className="font-cairo flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                      <BarChart3 className="h-4 w-4 text-white" />
                    </div>
                    {t('hakimAiInsights')}
                  </CardTitle>
                  <CardDescription className="font-tajawal">
                    {t('aipoweredSchoolPerformanceAnalysis')}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {hakimLoading ? (
                    <div className="flex items-center justify-center py-8">
                      <div className="text-center">
                        <Loader2 className="h-8 w-8 animate-spin text-purple-500 mx-auto mb-3" />
                        <p className="text-sm text-muted-foreground">{t('analyzing')}</p>
                      </div>
                    </div>
                  ) : hakimAnalysis ? (
                    <div className="space-y-6">
                      {/* Risk Summary */}
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <div className="text-center p-3 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
                          <AlertTriangle className="h-6 w-6 mx-auto text-red-500 mb-1" />
                          <p className="text-2xl font-bold text-red-600">{hakimAnalysis.risk_counts?.critical || 0}</p>
                          <p className="text-xs text-muted-foreground">{t('critical')}</p>
                        </div>
                        <div className="text-center p-3 rounded-xl bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-800">
                          <AlertTriangle className="h-6 w-6 mx-auto text-orange-500 mb-1" />
                          <p className="text-2xl font-bold text-orange-600">{hakimAnalysis.risk_counts?.high || 0}</p>
                          <p className="text-xs text-muted-foreground">{t('high')}</p>
                        </div>
                        <div className="text-center p-3 rounded-xl bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800">
                          <Clock className="h-6 w-6 mx-auto text-yellow-500 mb-1" />
                          <p className="text-2xl font-bold text-yellow-600">{hakimAnalysis.risk_counts?.medium || 0}</p>
                          <p className="text-xs text-muted-foreground">{t('medium')}</p>
                        </div>
                        <div className="text-center p-3 rounded-xl bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800">
                          <CheckCircle className="h-6 w-6 mx-auto text-green-500 mb-1" />
                          <p className="text-2xl font-bold text-green-600">{hakimAnalysis.risk_counts?.low || 0}</p>
                          <p className="text-xs text-muted-foreground">{t('low')}</p>
                        </div>
                      </div>

                      {/* Class Health + Alerts */}
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        {/* Class Health Rankings */}
                        {hakimAnalysis.class_health_summary?.length > 0 && (
                          <div className="space-y-2">
                            <h4 className="text-sm font-bold text-muted-foreground">{isRTL ? 'صحة الفصول' : 'Class Health'}</h4>
                            {hakimAnalysis.class_health_summary.slice(0, 5).map((cls) => (
                              <div key={cls.class_id} className="flex items-center gap-3 p-2 rounded-lg bg-muted/30">
                                <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-sm font-bold ${
                                  cls.health_score >= 80 ? 'bg-green-100 text-green-700' :
                                  cls.health_score >= 65 ? 'bg-blue-100 text-blue-700' :
                                  cls.health_score >= 50 ? 'bg-yellow-100 text-yellow-700' :
                                  'bg-red-100 text-red-700'
                                }`}>
                                  {cls.health_score}%
                                </div>
                                <span className="text-sm font-medium flex-1">{cls.class_name || cls.class_id}</span>
                                <Badge variant="outline" className={`text-xs ${
                                  cls.health_score >= 80 ? 'border-green-300 text-green-600' :
                                  cls.health_score >= 65 ? 'border-blue-300 text-blue-600' :
                                  cls.health_score >= 50 ? 'border-yellow-300 text-yellow-600' :
                                  'border-red-300 text-red-600'
                                }`}>
                                  {cls.health_score >= 80 ? (t('excellent')) :
                                   cls.health_score >= 65 ? (t('good')) :
                                   cls.health_score >= 50 ? (isRTL ? 'متوسط' : 'Average') :
                                   (t('needsWork'))}
                                </Badge>
                              </div>
                            ))}
                          </div>
                        )}

                        {/* AI Alerts */}
                        {hakimAnalysis.insights?.length > 0 && (
                          <div className="space-y-2">
                            <h4 className="text-sm font-bold text-muted-foreground">{t('hakimAlerts')}</h4>
                            {hakimAnalysis.insights.map((insight, idx) => (
                              <div key={idx} className={`p-3 rounded-lg border ${
                                insight.severity === 'critical' ? 'border-red-300 bg-red-50 dark:bg-red-950/20' :
                                insight.severity === 'high' ? 'border-orange-300 bg-orange-50 dark:bg-orange-950/20' :
                                insight.severity === 'medium' ? 'border-yellow-300 bg-yellow-50 dark:bg-yellow-950/20' :
                                'border-green-300 bg-green-50 dark:bg-green-950/20'
                              }`}>
                                <div className="flex items-center gap-2">
                                  {insight.type === 'achievement' ? <Award className="h-4 w-4 text-green-500 flex-shrink-0" /> :
                                   <AlertTriangle className={`h-4 w-4 flex-shrink-0 ${
                                     insight.severity === 'critical' ? 'text-red-500' :
                                     insight.severity === 'high' ? 'text-orange-500' : 'text-yellow-500'
                                   }`} />}
                                  <p className="text-sm">{insight.title_ar}</p>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      {/* Analysis Timestamp */}
                      <p className="text-xs text-center text-muted-foreground">
                        {t('lastAnalyzed')}
                        {hakimAnalysis.analyzed_at ? new Date(hakimAnalysis.analyzed_at).toLocaleString(isRTL ? 'ar-SA' : 'en-US') : '-'}
                      </p>
                    </div>
                  ) : (
                    <div className="text-center py-8">
                      <BarChart3 className="h-10 w-10 mx-auto text-muted-foreground/30 mb-3" />
                      <p className="text-muted-foreground">{t('noHakimAnalysisDataAvailable')}</p>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Attendance Trend Chart */}
              {attendanceTrend.length > 0 && (
                <Card className="card-nassaq">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 font-cairo">
                      <TrendingUp className="h-5 w-5 text-green-600" />
                      {t('weeklyAttendanceTrend')}
                    </CardTitle>
                    <CardDescription>{t('attendanceRateOverTheLast90Days')}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="h-[280px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={attendanceTrend}>
                          <defs>
                            <linearGradient id="attGrad" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#16a34a" stopOpacity={0.3}/>
                              <stop offset="95%" stopColor="#16a34a" stopOpacity={0}/>
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                          <XAxis dataKey="week" tick={{ fontSize: 11 }} />
                          <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                          <Tooltip formatter={(v) => [`${v}%`, t('rate')]} />
                          <Area type="monotone" dataKey="rate" stroke="#16a34a" fill="url(#attGrad)"
                            name={t('attendanceRate')} />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Participation Trend Chart */}
              {participationTrend.length > 0 && (
                <Card className="card-nassaq">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 font-cairo">
                      <BarChart3 className="h-5 w-5 text-blue-600" />
                      {t('weeklyParticipationTrend')}
                    </CardTitle>
                    <CardDescription>{t('interactionsPerWeek')}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="h-[280px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={participationTrend}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                          <XAxis dataKey="week" tick={{ fontSize: 11 }} />
                          <YAxis tick={{ fontSize: 11 }} />
                          <Tooltip />
                          <Bar dataKey="interactions" fill="#2563eb" radius={[4, 4, 0, 0]}
                            name={t('interactions')} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* At-Risk Students */}
              {atRiskStudents.length > 0 && (
                <Card className="card-nassaq border-red-200">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 font-cairo text-red-700">
                      <AlertTriangle className="h-5 w-5" />
                      {t('atriskStudents2')}
                    </CardTitle>
                    <CardDescription>{t('studentsNeedingImmediateAttention')}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {atRiskStudents.map((student, idx) => (
                        <div key={idx} className="flex items-center justify-between p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-100">
                          <div>
                            <p className="font-medium text-sm">{student.student_name || student.student_id}</p>
                            <p className="text-xs text-muted-foreground">
                              {student.class_name || student.class_id || ''}
                            </p>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge className={student.risk_category === 'critical' ? 'bg-red-600 text-white' : 'bg-orange-500 text-white'}>
                              {student.risk_category === 'critical' ? (t('critical')) : (t('high3'))}
                            </Badge>
                            <span className="text-sm font-bold text-red-600">{student.risk_score}%</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            {/* Attendance Tab */}
            <TabsContent value="attendance" className="space-y-6">
              <Card className="card-nassaq">
                <CardHeader>
                  <CardTitle className="font-cairo">
                    {t('attendanceReportByClass')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {attendanceData.length === 0 ? (
                    <div className="text-center py-12">
                      <CalendarDays className="h-12 w-12 mx-auto text-muted-foreground/30 mb-4" />
                      <p className="text-muted-foreground">{t('noAttendanceDataAvailable2')}</p>
                      <p className="text-sm text-muted-foreground/70 mt-2">
                        {t('dataWillAppearWhenAttendanceIsRecorded')}
                      </p>
                    </div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>{t('class')}</TableHead>
                          <TableHead className="text-center">{t('present')}</TableHead>
                          <TableHead className="text-center">{t('absent')}</TableHead>
                          <TableHead className="text-center">{t('late')}</TableHead>
                          <TableHead className="text-center">{t('rate')}</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {attendanceData.map((row, index) => (
                          <TableRow key={index}>
                            <TableCell className="font-medium">
                              {isRTL ? row.class : row.class_en}
                            </TableCell>
                            <TableCell className="text-center">
                              <Badge className="bg-green-100 text-green-700">{row.present}</Badge>
                            </TableCell>
                            <TableCell className="text-center">
                              <Badge className="bg-red-100 text-red-700">{row.absent}</Badge>
                            </TableCell>
                            <TableCell className="text-center">
                              <Badge className="bg-yellow-100 text-yellow-700">{row.late}</Badge>
                            </TableCell>
                            <TableCell className="text-center">
                              <div className="flex items-center justify-center gap-2">
                                <Progress value={row.rate} className="w-20 h-2" />
                                <span className={`font-medium ${row.rate >= 90 ? 'text-green-600' : row.rate >= 80 ? 'text-yellow-600' : 'text-red-600'}`}>
                                  {row.rate}%
                                </span>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Grades Tab */}
            <TabsContent value="grades" className="space-y-6">
              <Card className="card-nassaq">
                <CardHeader>
                  <CardTitle className="font-cairo">
                    {t('gradesReportBySubject')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {gradeData.length === 0 ? (
                    <div className="text-center py-12">
                      <Award className="h-12 w-12 mx-auto text-muted-foreground/30 mb-4" />
                      <p className="text-muted-foreground">{t('noGradeDataAvailable')}</p>
                      <p className="text-sm text-muted-foreground/70 mt-2">
                        {t('dataWillAppearWhenGradesAreRecorded')}
                      </p>
                    </div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>{t('subject')}</TableHead>
                          <TableHead className="text-center">{t('average3')}</TableHead>
                          <TableHead className="text-center">{t('highest')}</TableHead>
                          <TableHead className="text-center">{t('lowest')}</TableHead>
                          <TableHead className="text-center">{t('passRate')}</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {gradeData.map((row, index) => (
                          <TableRow key={index}>
                            <TableCell className="font-medium">
                              {isRTL ? row.subject : row.subject_en}
                            </TableCell>
                            <TableCell className="text-center">
                              <span className={`font-bold ${row.avg >= 80 ? 'text-green-600' : row.avg >= 60 ? 'text-yellow-600' : 'text-red-600'}`}>
                                {row.avg}%
                              </span>
                            </TableCell>
                            <TableCell className="text-center text-green-600 font-medium">{row.highest}</TableCell>
                            <TableCell className="text-center text-red-600 font-medium">{row.lowest}</TableCell>
                            <TableCell className="text-center">
                              <div className="flex items-center justify-center gap-2">
                                <Progress value={row.pass_rate} className="w-20 h-2" />
                                <span className="font-medium">{row.pass_rate}%</span>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Behavior Tab */}
            <TabsContent value="behavior" className="space-y-6">
              {behaviorData.length === 0 ? (
                <div className="text-center py-12">
                  <Heart className="h-12 w-12 mx-auto text-muted-foreground/30 mb-4" />
                  <p className="text-muted-foreground">{t('noBehaviorDataAvailable')}</p>
                  <p className="text-sm text-muted-foreground/70 mt-2">
                    {t('dataWillAppearWhenBehaviorNotesAreRecorded')}
                  </p>
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    {[
                      { type: 'positive', type_ar: 'إيجابي', count: behaviorData.find(b => b.type === 'positive')?.count || 0 },
                      { type: 'negative', type_ar: 'سلبي', count: behaviorData.find(b => b.type === 'negative')?.count || 0 },
                      { type: 'warning', type_ar: 'تحذير', count: behaviorData.find(b => b.type === 'warning')?.count || 0 },
                      { type: 'appreciation', type_ar: 'تقدير', count: behaviorData.find(b => b.type === 'appreciation')?.count || 0 },
                    ].map((item, index) => (
                      <Card key={index} className="card-nassaq">
                        <CardContent className="p-6">
                          <div className="flex items-center justify-between">
                            <div>
                              <p className="text-sm text-muted-foreground">
                                {isRTL ? item.type_ar : item.type}
                              </p>
                              <p className="text-3xl font-bold mt-1">{item.count}</p>
                            </div>
                            <div className={`h-14 w-14 rounded-2xl flex items-center justify-center ${
                              item.type === 'positive' ? 'bg-green-500' :
                              item.type === 'negative' ? 'bg-red-500' :
                              item.type === 'warning' ? 'bg-yellow-500' : 'bg-blue-500'
                            }`}>
                              {item.type === 'positive' && <CheckCircle className="h-7 w-7 text-white" />}
                              {item.type === 'negative' && <XCircle className="h-7 w-7 text-white" />}
                              {item.type === 'warning' && <AlertTriangle className="h-7 w-7 text-white" />}
                              {item.type === 'appreciation' && <Award className="h-7 w-7 text-white" />}
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>

              <Card className="card-nassaq">
                <CardHeader>
                  <CardTitle className="font-cairo">
                    {t('recentBehaviorNotes')}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {behaviorNotes.length === 0 ? (
                    <div className="text-center py-8">
                      <FileText className="h-12 w-12 mx-auto text-muted-foreground/30 mb-4" />
                      <p className="text-muted-foreground">
                        {t('noBehaviorNotesRecorded')}
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {behaviorNotes.map((note) => (
                        <div key={note.id} className="flex items-start gap-3 p-3 rounded-xl bg-muted/30 hover:bg-muted/50 transition-colors">
                          <div className={`h-10 w-10 rounded-full flex items-center justify-center flex-shrink-0 ${
                            note.type === 'positive' || note.type === 'appreciation' ? 'bg-green-100 text-green-600' :
                            note.type === 'negative' ? 'bg-red-100 text-red-600' : 'bg-yellow-100 text-yellow-600'
                          }`}>
                            {note.type === 'positive' || note.type === 'appreciation' ? <CheckCircle className="h-5 w-5" /> :
                             note.type === 'negative' ? <XCircle className="h-5 w-5" /> : <AlertTriangle className="h-5 w-5" />}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-sm">{note.student_name}</p>
                            <p className="text-sm text-muted-foreground mt-0.5 line-clamp-2">{note.note}</p>
                            <p className="text-xs text-muted-foreground/60 mt-1">
                              {note.date ? new Date(note.date).toLocaleDateString('ar-SA') : ''}
                            </p>
                          </div>
                          <Badge variant="secondary" className={`text-xs ${
                            note.type === 'positive' || note.type === 'appreciation' ? 'bg-green-100 text-green-700' :
                            note.type === 'negative' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'
                          }`}>
                            {note.type === 'positive' ? 'إيجابي' : 
                             note.type === 'negative' ? 'سلبي' : 
                             note.type === 'warning' ? 'تحذير' : 'تقدير'}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
                </>
              )}
            </TabsContent>
          </Tabs>
        </div>
      </div>
      <HakimAssistant />
    </Sidebar>
  );
};

export default SchoolReportsPage;
