/**
 * StandbyTab — content panel for the "حصص الانتظار" tab inside
 * `TeacherClassesPage`. Mounted in-place (no route change), so tab
 * switches don't unmount the surrounding shell. Pulls the same
 * teacher-scoped payload from `GET /api/standby/roster/me` that the
 * legacy standalone page used; the backend remains the security
 * boundary (`role == teacher`, school-scoped).
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  Hourglass, RefreshCw, CheckCircle2, Calendar,
} from 'lucide-react';

const DAY_AR = {
  sunday: 'الأحد', monday: 'الإثنين', tuesday: 'الثلاثاء',
  wednesday: 'الأربعاء', thursday: 'الخميس',
};

function periodLabel(p) {
  const ar = ['', 'الأولى', 'الثانية', 'الثالثة', 'الرابعة', 'الخامسة',
              'السادسة', 'السابعة', 'الثامنة', 'التاسعة', 'العاشرة'];
  return ar[p] ? `الحصة ${ar[p]}` : `الحصة ${p}`;
}

function GridSkeleton({ cols = 7 }) {
  // Lightweight skeleton in lieu of a page-level spinner so the tab
  // shell stays mounted and feels instant on switch.
  return (
    <div className="animate-pulse space-y-2">
      <div className="h-9 bg-slate-100 dark:bg-slate-800 rounded" />
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="grid gap-1" style={{ gridTemplateColumns: `120px repeat(${cols}, 1fr)` }}>
          {Array.from({ length: cols + 1 }).map((__, j) => (
            <div key={j} className="h-10 bg-slate-100 dark:bg-slate-800 rounded" />
          ))}
        </div>
      ))}
    </div>
  );
}

export default function StandbyTab() {
  const { api, isRTL } = useAuth();
  const { nassaqError } = useNassaqAlert();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [data, setData] = useState(null);

  const load = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true);
    try {
      const res = await api.get('/standby/roster/me');
      setData(res.data || null);
    } catch (e) {
      const msg = e?.response?.data?.detail || 'تعذّر تحميل جدول الانتظار';
      nassaqError(typeof msg === 'string' ? msg : 'تعذّر تحميل جدول الانتظار');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [api, nassaqError]);

  useEffect(() => { load(); }, [load]);

  // Light background poll so a principal-side regenerate is reflected
  // without forcing the teacher to reload. The notification action_url
  // also deep-links here.
  useEffect(() => {
    const id = setInterval(() => load({ silent: true }), 120000);
    return () => clearInterval(id);
  }, [load]);

  const periods = useMemo(() => data?.periods || [1, 2, 3, 4, 5, 6, 7], [data]);
  const days = useMemo(() => data?.days || [], [data]);
  const total = data?.total_slots || 0;

  const slotsSet = useMemo(() => {
    const s = new Set();
    for (const d of days) {
      for (const p of (d.periods || [])) s.add(`${d.day}:${p}`);
    }
    return s;
  }, [days]);

  return (
    <div dir={isRTL ? 'rtl' : 'ltr'} className="space-y-3">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 text-slate-600 dark:text-slate-300">
          <Hourglass className="h-4 w-4 text-amber-500" />
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
            <RefreshCw className={`h-4 w-4 ml-1 ${refreshing ? 'animate-spin' : ''}`} />
            تحديث
          </Button>
        </div>
      </div>

      <Card className="overflow-hidden">
        <CardContent className="p-0">
          {loading ? (
            <div className="p-3"><GridSkeleton cols={periods.length || 7} /></div>
          ) : total === 0 ? (
            <div className="py-16 text-center text-slate-500 text-sm flex flex-col items-center gap-2">
              <Calendar className="h-8 w-8 text-slate-300" />
              لا توجد لديك خانات انتظار هذا الأسبوع.
            </div>
          ) : (
            <div className="overflow-auto">
              <table dir="rtl" className="w-full border-collapse text-[12px] text-slate-800 dark:text-slate-100">
                <thead>
                  <tr className="bg-[#1C3D74] text-white">
                    <th className="border border-[#1C3D74] px-2 py-2 font-bold w-[120px]">اليوم</th>
                    {periods.map((p) => (
                      <th key={`ph-${p}`} className="border border-[#1C3D74] px-2 py-2 font-bold whitespace-nowrap">
                        {periodLabel(p)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Object.keys(DAY_AR).map((dKey) => (
                    <tr key={dKey} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                      <td className="border border-slate-300 bg-[#F4F7FB] dark:bg-slate-800 text-center font-bold text-[#1C3D74] dark:text-slate-100">
                        {DAY_AR[dKey]}
                      </td>
                      {periods.map((p) => {
                        const has = slotsSet.has(`${dKey}:${p}`);
                        return (
                          <td
                            key={`${dKey}-${p}`}
                            className={`border border-slate-300 text-center align-middle h-12 ${has ? 'bg-emerald-50 dark:bg-emerald-950/30' : 'bg-white dark:bg-slate-900'}`}
                          >
                            {has ? (
                              <span className="inline-flex items-center gap-1 text-emerald-700 dark:text-emerald-300 font-semibold text-[11px]">
                                <CheckCircle2 className="h-3.5 w-3.5" />
                                انتظار
                              </span>
                            ) : (
                              <span className="text-slate-300">—</span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
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
