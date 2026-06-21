/**
 * StandbyTab — content panel for the "حصص الانتظار" tab inside
 * `TeacherClassesPage`. Mounted in-place (no route change), so tab
 * switches don't unmount the surrounding shell. Pulls the enriched
 * payload from `GET /api/standby/roster/me`; each period entry now
 * includes class_name, subject_name, session_code, and status so
 * teachers see exactly what they are assigned to cover.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Input } from '../../components/ui/input';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import { getApiErrorMessage } from '../../utils/apiError';
import {
  Hourglass, RefreshCw, Calendar, Search, ChevronUp, ChevronDown, ChevronsUpDown,
} from 'lucide-react';

const DAY_AR = {
  sunday: 'الأحد', monday: 'الإثنين', tuesday: 'الثلاثاء',
  wednesday: 'الأربعاء', thursday: 'الخميس',
};

const DAY_ORDER = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday'];

function periodLabel(p) {
  const ar = ['', 'الأولى', 'الثانية', 'الثالثة', 'الرابعة', 'الخامسة',
    'السادسة', 'السابعة', 'الثامنة', 'التاسعة', 'العاشرة'];
  return ar[p] ? `الحصة ${ar[p]}` : `الحصة ${p}`;
}

function TableSkeleton() {
  return (
    <div className="animate-pulse space-y-2 p-3">
      <div className="h-9 bg-slate-100 dark:bg-slate-800 rounded" />
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="h-12 bg-slate-100 dark:bg-slate-800 rounded" />
      ))}
    </div>
  );
}

// 3-state sort: asc → desc → default (no sort)
function nextSortDir(currentKey, clickedKey, currentDir) {
  if (currentKey !== clickedKey) return 'asc';
  if (currentDir === 'asc') return 'desc';
  if (currentDir === 'desc') return null;  // null = default order
  return 'asc';
}

function SortIcon({ field, sortKey, sortDir }) {
  if (sortKey !== field || sortDir === null) {
    return <ChevronsUpDown className="h-3 w-3 opacity-40" aria-hidden="true" />;
  }
  if (sortDir === 'asc') return <ChevronUp className="h-3 w-3" aria-hidden="true" />;
  return <ChevronDown className="h-3 w-3" aria-hidden="true" />;
}

export default function StandbyTab() {
  const { api, isRTL } = useAuth();
  const { nassaqError } = useNassaqAlert();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [data, setData] = useState(null);
  const [search, setSearch] = useState('');
  // sortKey: 'day' | 'class_name' | 'subject_name'
  // sortDir: 'asc' | 'desc' | null (null = default order = day+period)
  const [sortKey, setSortKey] = useState('day');
  const [sortDir, setSortDir] = useState('asc');

  const load = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true);
    try {
      const res = await api.get('/standby/roster/me');
      setData(res.data || null);
    } catch (e) {
      const msg = getApiErrorMessage(e) || 'تعذّر تحميل جدول الانتظار';
      nassaqError(typeof msg === 'string' ? msg : 'تعذّر تحميل جدول الانتظار');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [api, nassaqError]);

  useEffect(() => { load(); }, [load]);

  // Light background poll so a principal-side regenerate is reflected
  // without forcing the teacher to reload.
  useEffect(() => {
    const id = setInterval(() => load({ silent: true }), 120000);
    return () => clearInterval(id);
  }, [load]);

  const total = data?.total_slots || 0;

  // Flatten days → periods into a single rows array for sort/filter.
  const rows = useMemo(() => {
    const result = [];
    for (const dayObj of (data?.days || [])) {
      const dayKey = dayObj.day;
      const dayAr = dayObj.day_ar || DAY_AR[dayKey] || dayKey;
      const dayOrder = DAY_ORDER.indexOf(dayKey);
      for (const entry of (dayObj.periods || [])) {
        // Support both old format (plain int) and new enriched object.
        const isEnriched = entry !== null && typeof entry === 'object';
        result.push({
          dayKey,
          dayAr,
          dayOrder,
          period: isEnriched ? entry.period : entry,
          session_code: isEnriched ? (entry.session_code || null) : null,
          class_name: isEnriched ? (entry.class_name || null) : null,
          subject_name: isEnriched ? (entry.subject_name || null) : null,
          assignment_id: isEnriched ? (entry.assignment_id || null) : null,
          original_session_id: isEnriched ? (entry.original_session_id || null) : null,
          absence_date: isEnriched ? (entry.absence_date || null) : null,
          status: isEnriched ? (entry.status || 'standby') : 'standby',
        });
      }
    }
    return result;
  }, [data]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    const base = q
      ? rows.filter(r =>
          (r.class_name || '').toLowerCase().includes(q) ||
          (r.subject_name || '').toLowerCase().includes(q) ||
          (r.session_code || '').toLowerCase().includes(q)
        )
      : rows;

    // sortDir === null means use default order (day + period), which is
    // already the natural order of rows from the backend.
    if (!sortKey || sortDir === null) return base;

    return [...base].sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'day') {
        cmp = a.dayOrder - b.dayOrder || a.period - b.period;
      } else if (sortKey === 'class_name') {
        cmp = (a.class_name || '').localeCompare(b.class_name || '', 'ar');
        if (cmp === 0) cmp = a.dayOrder - b.dayOrder || a.period - b.period;
      } else if (sortKey === 'subject_name') {
        cmp = (a.subject_name || '').localeCompare(b.subject_name || '', 'ar');
        if (cmp === 0) cmp = a.dayOrder - b.dayOrder || a.period - b.period;
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
  }, [rows, search, sortKey, sortDir]);

  const handleSort = (key) => {
    const newDir = nextSortDir(sortKey, key, sortDir);
    if (newDir === null) {
      // Reset: return to default order (day-asc)
      setSortKey('day');
      setSortDir('asc');
    } else {
      setSortKey(key);
      setSortDir(newDir);
    }
  };

  const handleSortable = (key) => {
    // For class_name and subject_name: 3-state cycle asc→desc→default.
    // For day: always toggle asc↔desc (it's always active as the tiebreaker).
    if (key === 'day') {
      setSortKey('day');
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
      return;
    }
    const newDir = nextSortDir(sortKey, key, sortDir);
    if (newDir === null) {
      setSortKey('day');
      setSortDir('asc');
    } else {
      setSortKey(key);
      setSortDir(newDir);
    }
  };

  return (
    <div dir={isRTL ? 'rtl' : 'ltr'} className="space-y-3">
      {/* Header bar */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 text-slate-600 dark:text-slate-300">
          <Hourglass className="h-4 w-4 text-amber-500" aria-hidden="true" strokeWidth={1.5} />
          <span className="text-[12px]">
            الحصص التي أسندتها إدارة المدرسة لك كمعلم انتظار خلال الأسبوع الحالي.
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="border-amber-300 bg-amber-50 text-amber-800 dark:bg-amber-950/30">
            {total} خانة هذا الأسبوع
          </Badge>
          <Button
            variant="outline"
            size="sm"
            onClick={() => { setRefreshing(true); load(); }}
            disabled={refreshing || loading}
          >
            <RefreshCw className={`h-4 w-4 ms-1 ${refreshing ? 'animate-spin' : ''}`} aria-hidden="true" strokeWidth={1.5} />
            تحديث
          </Button>
        </div>
      </div>

      {/* Search */}
      {!loading && total > 0 && (
        <div className="relative">
          <Search className="absolute top-1/2 -translate-y-1/2 end-3 h-4 w-4 text-slate-400 pointer-events-none" aria-hidden="true" strokeWidth={1.5} />
          <Input
            dir="rtl"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="ابحث بالفصل أو المادة أو رمز الحصة…"
            className="pe-9 text-sm"
            aria-label="بحث في جدول الانتظار"
          />
        </div>
      )}

      <Card className="overflow-hidden">
        <CardContent className="p-0">
          {loading ? (
            <TableSkeleton />
          ) : total === 0 ? (
            <div className="py-16 text-center text-slate-500 text-sm flex flex-col items-center gap-2">
              <Calendar className="h-8 w-8 text-slate-300" aria-hidden="true" strokeWidth={1.5} />
              لا توجد لديك خانات انتظار هذا الأسبوع.
            </div>
          ) : filtered.length === 0 ? (
            <div className="py-12 text-center text-slate-400 text-sm">
              لا توجد نتائج تطابق البحث.
            </div>
          ) : (
            <div className="overflow-auto">
              <table dir="rtl" className="w-full border-collapse text-[12px] text-slate-800 dark:text-slate-100">
                <thead>
                  <tr className="bg-[#1C3D74] text-white">
                    <th
                      className="border border-[#1C3D74] px-3 py-2 font-bold text-start whitespace-nowrap cursor-pointer select-none"
                      onClick={() => handleSortable('day')}
                      aria-sort={sortKey === 'day' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                    >
                      <span className="inline-flex items-center gap-1">
                        اليوم / الحصة
                        <SortIcon field="day" sortKey={sortKey} sortDir={sortDir} />
                      </span>
                    </th>
                    <th
                      className="border border-[#1C3D74] px-3 py-2 font-bold text-start whitespace-nowrap cursor-pointer select-none"
                      onClick={() => handleSortable('class_name')}
                      aria-sort={sortKey === 'class_name' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                    >
                      <span className="inline-flex items-center gap-1">
                        الفصل
                        <SortIcon field="class_name" sortKey={sortKey} sortDir={sortDir} />
                      </span>
                    </th>
                    <th
                      className="border border-[#1C3D74] px-3 py-2 font-bold text-start whitespace-nowrap cursor-pointer select-none"
                      onClick={() => handleSortable('subject_name')}
                      aria-sort={sortKey === 'subject_name' ? (sortDir === 'asc' ? 'ascending' : 'descending') : 'none'}
                    >
                      <span className="inline-flex items-center gap-1">
                        المادة
                        <SortIcon field="subject_name" sortKey={sortKey} sortDir={sortDir} />
                      </span>
                    </th>
                    <th className="border border-[#1C3D74] px-3 py-2 font-bold text-start whitespace-nowrap">
                      رمز الحصة
                    </th>
                    <th className="border border-[#1C3D74] px-3 py-2 font-bold text-start whitespace-nowrap">
                      الحالة
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((row, idx) => {
                    const isAssigned = row.status === 'assigned';
                    return (
                      <tr
                        key={`${row.dayKey}-${row.period}-${idx}`}
                        className="hover:bg-slate-50 dark:hover:bg-slate-800/40 border-b border-slate-200 dark:border-slate-700 last:border-0"
                      >
                        {/* Day + period */}
                        <td className="border border-slate-200 dark:border-slate-700 px-3 py-2.5 bg-[#F4F7FB] dark:bg-slate-800 font-bold text-[#1C3D74] dark:text-slate-100 whitespace-nowrap">
                          {row.dayAr}
                          <span className="block text-[11px] font-normal text-slate-500 dark:text-slate-400 mt-0.5">
                            {periodLabel(row.period)}
                          </span>
                        </td>

                        {/* Class name */}
                        <td className="border border-slate-200 dark:border-slate-700 px-3 py-2.5">
                          {row.class_name
                            ? <span className="font-semibold text-slate-800 dark:text-slate-100">{row.class_name}</span>
                            : <span className="text-slate-400 dark:text-slate-500">—</span>
                          }
                        </td>

                        {/* Subject name */}
                        <td className="border border-slate-200 dark:border-slate-700 px-3 py-2.5">
                          {row.subject_name
                            ? <span className="text-slate-700 dark:text-slate-200">{row.subject_name}</span>
                            : <span className="text-slate-400 dark:text-slate-500">—</span>
                          }
                        </td>

                        {/* Session code */}
                        <td className="border border-slate-200 dark:border-slate-700 px-3 py-2.5">
                          {row.session_code
                            ? <code className="text-[11px] bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 px-1.5 py-0.5 rounded font-mono">{row.session_code}</code>
                            : <span className="text-slate-400 dark:text-slate-500">—</span>
                          }
                        </td>

                        {/* Status badge */}
                        <td className="border border-slate-200 dark:border-slate-700 px-3 py-2.5">
                          {isAssigned ? (
                            <Badge className="bg-amber-100 text-amber-800 border border-amber-300 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-700 text-[11px] font-semibold">
                              مُسنَدة
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="text-slate-500 dark:text-slate-400 border-slate-300 dark:border-slate-600 text-[11px]">
                              انتظار
                            </Badge>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <p className="text-[11px] text-slate-400 text-center">
        عند تحديث الإدارة لجدول الانتظار سيصلك إشعار تلقائي ويُحدَّث هذا العرض.
      </p>
    </div>
  );
}
