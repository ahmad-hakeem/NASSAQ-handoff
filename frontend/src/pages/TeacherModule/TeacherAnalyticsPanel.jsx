// 2026-05-19 — UX merge: the standalone IT analytics page has been
// folded into AIInsightsPage as the "التحليلات الرقمية" tab. This
// module is the embeddable panel form (no Sidebar wrapper, no page
// shell) so AIInsightsPage can render it inside a TabsContent. The
// data-fetching, date filters, class filter, export buttons and
// charts are unchanged — only the outer chrome was removed. The
// panel uses its own state and `useEffect` so the AI Insights tab
// never blocks the analytics tab's API calls and vice versa.
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { BarChart3, FileText, FileSpreadsheet, Loader2, RefreshCw } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import { useAuth } from '../../contexts/AuthContext';
import { useTranslation } from '../../contexts/ThemeContext';
import { formatHijriDate, getHijriDate } from '../../utils/hijriDate';

const DEFAULT_RANGE_DAYS = 30;

function isoDay(d) {
  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(d.getUTCDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

function dayBoundaryIso(value, { endOfDay = false } = {}) {
  if (!value) return null;
  const [y, m, d] = value.split('-').map((n) => parseInt(n, 10));
  if (!y || !m || !d) return null;
  const dt = new Date(Date.UTC(y, m - 1, d, endOfDay ? 23 : 0, endOfDay ? 59 : 0, endOfDay ? 59 : 0));
  return dt.toISOString();
}

function formatHijriOrIso(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return formatHijriDate(d);
  } catch {
    return iso;
  }
}

export default function TeacherAnalyticsPanel() {
  const { t } = useTranslation();
  const { nassaqError } = useNassaqAlert();
  const { api } = useAuth();

  const today = useMemo(() => new Date(), []);
  const defaultStart = useMemo(() => {
    const d = new Date(today.getTime());
    d.setUTCDate(d.getUTCDate() - DEFAULT_RANGE_DAYS);
    return d;
  }, [today]);

  const [fromDate, setFromDate] = useState(isoDay(defaultStart));
  const [toDate, setToDate] = useState(isoDay(today));
  const [classId, setClassId] = useState('all');
  const [classes, setClasses] = useState([]);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [exporting, setExporting] = useState(null); // 'pdf' | 'xlsx' | null

  const loadClasses = useCallback(async () => {
    try {
      const resp = await api.get('/classes');
      const list = Array.isArray(resp?.data)
        ? resp.data
        : (resp?.data?.classes || []);
      setClasses(list);
    } catch {
      setClasses([]);
    }
  }, [api]);

  const loadAnalytics = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        from: dayBoundaryIso(fromDate),
        to: dayBoundaryIso(toDate, { endOfDay: true }),
      };
      if (classId && classId !== 'all') params.class_id = classId;
      const resp = await api.get('/independent-teacher/analytics', { params });
      setData(resp?.data || null);
    } catch (err) {
      const msg = err?.response?.data?.error?.message
        || err?.response?.data?.detail
        || t('teacherAnalyticsLoadFailed');
      nassaqError(msg);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [api, fromDate, toDate, classId, t, nassaqError]);

  useEffect(() => { loadClasses(); }, [loadClasses]);
  useEffect(() => { loadAnalytics(); }, [loadAnalytics]);

  const handleExport = useCallback(async (fmt) => {
    if (exporting) return;
    setExporting(fmt);
    try {
      const params = {
        from: dayBoundaryIso(fromDate),
        to: dayBoundaryIso(toDate, { endOfDay: true }),
      };
      if (classId && classId !== 'all') params.class_id = classId;
      const path = fmt === 'pdf'
        ? '/independent-teacher/analytics/export.pdf'
        : '/independent-teacher/analytics/export.xlsx';
      const res = await api.get(path, { params, responseType: 'blob' });
      const mime = fmt === 'pdf'
        ? 'application/pdf'
        : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
      const blob = res?.data instanceof Blob
        ? res.data
        : new Blob([res?.data ?? ''], { type: mime });
      const h = getHijriDate(new Date());
      const stamp = `${String(h.hijriYear).padStart(4, '0')}-${String(h.hijriMonth).padStart(2, '0')}-${String(h.hijriDay).padStart(2, '0')}H`;
      const filename = `nassaq-analytics-${stamp}.${fmt}`;
      const href = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = href;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(href), 0);
    } catch (err) {
      const msg = err?.response?.data?.error?.message
        || err?.response?.data?.detail
        || t('teacherAnalyticsExportFailed');
      nassaqError(msg);
    } finally {
      setExporting(null);
    }
  }, [api, fromDate, toDate, classId, exporting, t, nassaqError]);

  const behaviorRows = useMemo(() => data?.behavior || [], [data]);

  return (
    <div className="space-y-4" dir="rtl" data-testid="teacher-analytics-panel">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        <div className="flex items-center gap-2">
          <BarChart3 className="h-6 w-6 text-blue-600" />
          <div>
            <h2 className="text-lg font-bold font-cairo">{t('teacherAnalyticsTitle')}</h2>
            <p className="text-sm text-gray-500 font-tajawal">{t('teacherAnalyticsIntro')}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => handleExport('pdf')}
            disabled={loading || !!exporting}
            data-testid="analytics-export-pdf"
          >
            {exporting === 'pdf'
              ? <Loader2 className="h-4 w-4 animate-spin" />
              : <FileText className="h-4 w-4" />}
            <span className="mx-1">{t('teacherAnalyticsExportPdf')}</span>
          </Button>
          <Button
            variant="outline"
            onClick={() => handleExport('xlsx')}
            disabled={loading || !!exporting}
            data-testid="analytics-export-xlsx"
          >
            {exporting === 'xlsx'
              ? <Loader2 className="h-4 w-4 animate-spin" />
              : <FileSpreadsheet className="h-4 w-4" />}
            <span className="mx-1">{t('teacherAnalyticsExportExcel')}</span>
          </Button>
          <Button
            variant="outline"
            onClick={loadAnalytics}
            disabled={loading}
            data-testid="analytics-refresh"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            <span className="mx-1">{t('teacherAnalyticsRefresh')}</span>
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="p-4 grid grid-cols-1 md:grid-cols-4 gap-3">
          <div>
            <label className="block text-xs text-gray-600 mb-1">{t('teacherAnalyticsFrom')}</label>
            <Input
              type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              data-testid="analytics-from"
            />
            <p className="text-[11px] text-gray-500 mt-1">{formatHijriOrIso(dayBoundaryIso(fromDate))}</p>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">{t('teacherAnalyticsTo')}</label>
            <Input
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              data-testid="analytics-to"
            />
            <p className="text-[11px] text-gray-500 mt-1">{formatHijriOrIso(dayBoundaryIso(toDate, { endOfDay: true }))}</p>
          </div>
          <div>
            <label className="block text-xs text-gray-600 mb-1">{t('teacherAnalyticsClass')}</label>
            <Select value={classId} onValueChange={setClassId}>
              <SelectTrigger data-testid="analytics-class"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('teacherAnalyticsAllClasses')}</SelectItem>
                {classes.map((c) => (
                  <SelectItem key={c.id} value={c.id}>{c.name || c.id}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle className="text-base">{t('teacherAnalyticsAttendanceTitle')}</CardTitle></CardHeader>
          <CardContent style={{ height: 300 }}>
            {!loading && (data?.attendance?.length || 0) === 0 ? (
              <div className="h-full flex items-center justify-center text-sm text-gray-500" data-testid="analytics-attendance-empty">
                {t('teacherAnalyticsEmpty')}
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data?.attendance || []}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                  <Tooltip />
                  <Legend />
                  <Area type="monotone" dataKey="present" stackId="1" stroke="#10b981" fill="#10b981" name={t('teacherAnalyticsPresent')} />
                  <Area type="monotone" dataKey="absent" stackId="1" stroke="#dc2626" fill="#dc2626" name={t('teacherAnalyticsAbsent')} />
                  <Area type="monotone" dataKey="late" stackId="1" stroke="#f59e0b" fill="#f59e0b" name={t('teacherAnalyticsLate')} />
                  <Area type="monotone" dataKey="excused" stackId="1" stroke="#6b7280" fill="#6b7280" name={t('teacherAnalyticsExcused')} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">{t('teacherAnalyticsBehaviorTitle')}</CardTitle></CardHeader>
          <CardContent style={{ height: 300 }}>
            {!loading && behaviorRows.length === 0 ? (
              <div className="h-full flex items-center justify-center text-sm text-gray-500" data-testid="analytics-behavior-empty">
                {t('teacherAnalyticsEmpty')}
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={behaviorRows}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="week" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="positive" fill="#10b981" name={t('teacherAnalyticsBehaviorPositive')} />
                  <Bar dataKey="negative" fill="#dc2626" name={t('teacherAnalyticsBehaviorNegative')} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">{t('teacherAnalyticsLessonPlansTitle')}</CardTitle></CardHeader>
          <CardContent style={{ height: 300 }}>
            {!loading && (data?.lesson_plans?.length || 0) === 0 ? (
              <div className="h-full flex items-center justify-center text-sm text-gray-500" data-testid="analytics-lp-empty">
                {t('teacherAnalyticsEmpty')}
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data?.lesson_plans || []}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="generated" stroke="#2563eb" strokeWidth={2} dot name={t('teacherAnalyticsLessonPlansGenerated')} />
                  <Line type="monotone" dataKey="saved" stroke="#10b981" strokeWidth={2} dot name={t('teacherAnalyticsLessonPlansSaved')} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">{t('teacherAnalyticsTopTitle')}</CardTitle></CardHeader>
          <CardContent className="space-y-4">
            <TopTable
              title={t('teacherAnalyticsTopAbsence')}
              rows={(data?.top_students_absence || []).map((r) => ({
                ...r,
                rate_pct: `${Math.round((r.absence_rate || 0) * 100)}% (${r.absent_count || 0}/${r.total_count || 0})`,
              }))}
              cols={[
                { key: 'name', label: t('teacherAnalyticsName') },
                { key: 'rate_pct', label: t('teacherAnalyticsAbsenceRate'), align: 'end' },
              ]}
              emptyLabel={t('teacherAnalyticsEmpty')}
              testId="analytics-top-absence"
            />
            <TopTable
              title={t('teacherAnalyticsTopBehavior')}
              rows={data?.top_students_behavior || []}
              cols={[
                { key: 'name', label: t('teacherAnalyticsName') },
                { key: 'negative_count', label: t('teacherAnalyticsNegativeCount'), align: 'end' },
              ]}
              emptyLabel={t('teacherAnalyticsEmpty')}
              testId="analytics-top-behavior"
            />
            <TopTable
              title={t('teacherAnalyticsTopClasses')}
              rows={(data?.top_classes_attendance || []).map((r) => ({
                ...r,
                rate_pct: `${Math.round((r.attendance_rate || 0) * 100)}%`,
              }))}
              cols={[
                { key: 'name', label: t('teacherAnalyticsClassName') },
                { key: 'rate_pct', label: t('teacherAnalyticsRate'), align: 'end' },
              ]}
              emptyLabel={t('teacherAnalyticsEmpty')}
              testId="analytics-top-classes"
            />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function TopTable({ title, rows, cols, emptyLabel, testId }) {
  return (
    <div data-testid={testId}>
      <h4 className="text-sm font-semibold mb-2">{title}</h4>
      {rows.length === 0 ? (
        <div className="text-xs text-gray-500 py-4 text-center border rounded">{emptyLabel}</div>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-gray-600 border-b">
              {cols.map((c) => (
                <th key={c.key} className={`py-1 ${c.align === 'end' ? 'text-end' : 'text-start'}`}>{c.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.student_id || r.class_id || i} className="border-b last:border-0">
                {cols.map((c) => (
                  <td key={c.key} className={`py-1 ${c.align === 'end' ? 'text-end' : 'text-start'}`}>{r[c.key]}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
