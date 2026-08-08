import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '@/shared/contexts/AuthContext';
import { useTheme, useTranslation } from '@/shared/contexts/ThemeContext';
import { useNassaqAlert } from '@/shared/components/ui/NassaqAlertDialog';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { LoadingState } from '@/shared/components/ui/LoadingState';
import { ScrollArea } from '@/shared/components/ui/scroll-area';
import { Calendar, BookOpen, User, Printer } from 'lucide-react';
import { buildScheduleGrid, getScheduleCell } from '@/shared/models/utils/parentScheduleGrid';

const DAY_NAMES = {
  sunday: { ar: 'الأحد', color: 'from-blue-500 to-blue-600' },
  monday: { ar: 'الإثنين', color: 'from-brand-purple to-brand-purple-dark' },
  tuesday: { ar: 'الثلاثاء', color: 'from-green-500 to-green-600' },
  wednesday: { ar: 'الأربعاء', color: 'from-amber-500 to-amber-600' },
  thursday: { ar: 'الخميس', color: 'from-rose-500 to-rose-600' },
  friday: { ar: 'الجمعة', color: 'from-emerald-500 to-emerald-600' },
  saturday: { ar: 'السبت', color: 'from-slate-500 to-slate-600' },
};

const SchedulePanel = ({ childId }) => {
  const { t } = useTranslation();
  const { nassaqError } = useNassaqAlert();
  const { token, api } = useAuth();
  const { isRTL } = useTheme();
  const [loading, setLoading] = useState(true);
  const [schedule, setSchedule] = useState(null);
  const [viewMode, setViewMode] = useState('list');

  const loadSchedule = useCallback(async ({ silent = false } = {}) => {
    try {
      const res = await api.get(`/parent-portal/child/${childId}/schedule`);
      setSchedule(res.data);
    } catch {
      if (!silent) nassaqError(t('errorFetchingSchedule'));
    } finally {
      if (!silent) setLoading(false);
    }
  }, [childId, api, nassaqError, t]);

  useEffect(() => {
    setLoading(true);
    loadSchedule();
  }, [token, loadSchedule]);

  // Task #145 — silently refetch when the school admin publishes a new
  // timetable so the embedded parent schedule panel updates in place.
  useEffect(() => {
    const onPublished = () => { loadSchedule({ silent: true }); };
    window.addEventListener('nassaq:schedule_published', onPublished);
    return () => window.removeEventListener('nassaq:schedule_published', onPublished);
  }, [loadSchedule]);

  if (loading) {
    return (
      <LoadingState variant="section" />
    );
  }

  const days = schedule?.days || [];
  const scheduleData = schedule?.schedule || {};
  const { periods: gridPeriods, lookup: gridLookup } = buildScheduleGrid(schedule);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-end gap-2">
        <Button variant="outline" size="sm" onClick={() => window.print()} className="gap-2 print:hidden">
          <Printer className="h-4 w-4" />
          {t('print')}
        </Button>
        <div className="flex bg-muted/40 rounded-lg p-0.5 print:hidden">
          <button
            onClick={() => setViewMode('list')}
            className={`px-3 py-1 text-xs rounded-md transition ${viewMode === 'list' ? 'bg-card shadow-sm font-medium' : 'text-muted-foreground'}`}
          >
            {t('list')}
          </button>
          <button
            onClick={() => setViewMode('grid')}
            className={`px-3 py-1 text-xs rounded-md transition ${viewMode === 'grid' ? 'bg-card shadow-sm font-medium' : 'text-muted-foreground'}`}
          >
            {t('grid')}
          </button>
        </div>
      </div>

      {days.length === 0 ? (
        <Card className="rounded-2xl border-0 shadow-sm">
          <CardContent className="py-16 text-center">
            <Calendar className="h-16 w-16 mx-auto mb-4 text-muted-foreground/50" />
            <h3 className="font-bold font-cairo text-lg text-foreground mb-2">
              {t('noScheduleAvailable')}
            </h3>
            <p className="text-sm text-muted-foreground">
              {t('scheduleWillAppearAfterItIsPublishedBySchoolAdmin')}
            </p>
          </CardContent>
        </Card>
      ) : viewMode === 'list' ? (
        <div className="space-y-4">
          {days.map((day) => {
            const dayInfo = DAY_NAMES[day] || { ar: day, color: 'from-gray-500 to-gray-600' };
            const entries = scheduleData[day] || [];
            return (
              <Card key={day} className="rounded-2xl border-0 shadow-sm overflow-hidden">
                <div className={`bg-gradient-to-r ${dayInfo.color} px-4 py-2.5`}>
                  <h3 className="font-bold font-cairo text-white text-sm flex items-center gap-2">
                    <Calendar className="h-4 w-4" />
                    {isRTL ? dayInfo.ar : day}
                    <Badge className="bg-white/20 text-white border-0 text-[10px]">
                      {entries.length} {isRTL ? 'حصص' : 'classes'}
                    </Badge>
                  </h3>
                </div>
                <CardContent className="p-3">
                  {entries.length > 0 ? (
                    <div className="space-y-2">
                      {entries.map((entry, idx) => (
                        <div key={idx} className="flex items-center gap-3 p-3 bg-muted/40 rounded-xl transition">
                          <div className="flex flex-col items-center justify-center min-w-[56px] h-12 rounded-lg bg-brand-navy/15">
                            <span className="text-[10px] font-bold text-brand-navy">{entry.start_time}</span>
                            <span className="text-[9px] text-brand-navy/60">{entry.end_time}</span>
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <BookOpen className="h-3.5 w-3.5 text-brand-navy flex-shrink-0" />
                              <p className="font-semibold text-sm truncate">{entry.subject}</p>
                            </div>
                            <div className="flex items-center gap-2 mt-0.5">
                              <User className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                              <p className="text-xs text-muted-foreground truncate">{entry.teacher}</p>
                            </div>
                          </div>
                          {entry.period && (
                            <Badge variant="outline" className="text-[10px] shrink-0">
                              {isRTL ? `ح${entry.period}` : `P${entry.period}`}
                            </Badge>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-center text-sm text-muted-foreground py-4">
                      {isRTL ? 'لا توجد حصص' : 'No classes'}
                    </p>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      ) : (
        <Card className="rounded-2xl border-0 shadow-sm">
          <CardContent className="p-3">
            <ScrollArea className="w-full">
              <div className="overflow-x-auto">
                <table className="w-full text-xs border-collapse" dir={isRTL ? 'rtl' : 'ltr'}>
                  <thead>
                    <tr>
                      <th className="p-2 text-muted-foreground font-medium border-b w-16">
                        {t('period')}
                      </th>
                      {days.map(day => {
                        const dayInfo = DAY_NAMES[day] || { ar: day, color: 'from-gray-500 to-gray-600' };
                        return (
                          <th key={day} className="p-2 border-b">
                            <span className={`inline-block px-2 py-0.5 rounded-full text-white text-[10px] font-bold bg-gradient-to-r ${dayInfo.color}`}>
                              {isRTL ? dayInfo.ar : day}
                            </span>
                          </th>
                        );
                      })}
                    </tr>
                  </thead>
                  <tbody>
                    {gridPeriods.map(({ period, label }) => (
                      <tr key={period}>
                        <td className="p-1.5 text-center font-medium text-muted-foreground border-b">
                          {label}
                        </td>
                        {days.map(day => {
                          const entry = getScheduleCell(gridLookup, day, period);
                          if (!entry) {
                            return (
                              <td key={day} className="p-1 border-b">
                                <div className="h-12 rounded-lg bg-muted/40 border border-dashed border-border" />
                              </td>
                            );
                          }
                          return (
                            <td key={day} className="p-1 border-b" data-testid="parent-grid-cell">
                              <div
                                className="h-12 rounded-lg bg-brand-navy/5 border border-brand-navy/10 flex items-center justify-center px-1.5 text-center"
                                title={entry.subject}
                              >
                                <span className="text-[11px] font-semibold text-brand-navy leading-tight line-clamp-2 max-w-full">
                                  {entry.subject}
                                </span>
                              </div>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default SchedulePanel;
