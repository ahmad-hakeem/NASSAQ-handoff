/**
 * TeacherStandbyPage — جدول حصص الانتظار للمعلم.
 * نَسَّق | NASSAQ — Task #157
 *
 * Read-only weekly view of the standby slots assigned to the
 * authenticated teacher by the principal/admin (auto + manual). Pulls
 * from `GET /api/standby/roster/me`. Mirrors the Saudi MoE day-centric
 * format but scoped to the current teacher only.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Sidebar } from '../../components/layout/Sidebar';
import { useAuth } from '../../contexts/AuthContext';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Hourglass, Loader2, RefreshCw, CheckCircle2, Calendar } from 'lucide-react';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';

const DAY_AR = {
  sunday: 'الأحد', monday: 'الإثنين', tuesday: 'الثلاثاء',
  wednesday: 'الأربعاء', thursday: 'الخميس',
};

function periodLabel(p) {
  const ar = ['', 'الأولى', 'الثانية', 'الثالثة', 'الرابعة', 'الخامسة',
              'السادسة', 'السابعة', 'الثامنة', 'التاسعة', 'العاشرة'];
  return ar[p] ? `الحصة ${ar[p]}` : `الحصة ${p}`;
}

export default function TeacherStandbyPage() {
  const { api } = useAuth();
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

  // Refresh when the principal regenerates (notification arrives, but we
  // also poll lightly to stay current without a hard reload).
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
    <Sidebar>
      <div
        dir="rtl"
        className="min-h-screen bg-slate-50 text-slate-900 p-3 md:p-5 space-y-3"
      >
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <h1 className="text-xl md:text-2xl font-bold text-[#1C3D74] flex items-center gap-2">
              <Hourglass className="h-5 w-5 text-amber-500" />
              حصص الانتظار الخاصة بي
            </h1>
            <p className="text-[12px] text-slate-500 mt-0.5">
              الحصص التي أسندتها إدارة المدرسة لك كمعلم انتظار خلال الأسبوع الحالي.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="outline" className="border-amber-300 bg-amber-50 text-amber-800">
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
              <div className="flex items-center justify-center py-16 text-slate-500">
                <Loader2 className="h-6 w-6 animate-spin ml-2" />
                جارٍ التحميل…
              </div>
            ) : total === 0 ? (
              <div className="py-16 text-center text-slate-500 text-sm flex flex-col items-center gap-2">
                <Calendar className="h-8 w-8 text-slate-300" />
                لا توجد لديك خانات انتظار هذا الأسبوع.
              </div>
            ) : (
              <div className="overflow-auto">
                <table dir="rtl" className="w-full border-collapse text-[12px] text-slate-800">
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
                      <tr key={dKey} className="hover:bg-slate-50">
                        <td className="border border-slate-300 bg-[#F4F7FB] text-center font-bold text-[#1C3D74]">
                          {DAY_AR[dKey]}
                        </td>
                        {periods.map((p) => {
                          const has = slotsSet.has(`${dKey}:${p}`);
                          return (
                            <td
                              key={`${dKey}-${p}`}
                              className={`border border-slate-300 text-center align-middle h-12 ${has ? 'bg-emerald-50' : 'bg-white'}`}
                            >
                              {has ? (
                                <span className="inline-flex items-center gap-1 text-emerald-700 font-semibold text-[11px]">
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
    </Sidebar>
  );
}
