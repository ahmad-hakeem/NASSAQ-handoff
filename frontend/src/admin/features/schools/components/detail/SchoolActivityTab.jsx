import React, { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { Button } from '@/shared/components/ui/button';
import { Activity, Clock, Search, X, User, MessageSquare } from 'lucide-react';
import { resolveActivity } from '../../constants/schoolConstants';

export default function SchoolActivityTab({
  auditLogs = [],
  isRTL,
  t,
}) {
  const [searchQuery, setSearchQuery] = useState('');

  const filteredLogs = useMemo(() => {
    if (!searchQuery.trim()) return auditLogs;
    const q = searchQuery.toLowerCase().trim();
    return auditLogs.filter(log =>
      log.action?.toLowerCase().includes(q) ||
      log.actor_email?.toLowerCase().includes(q) ||
      log.new_values?.reason?.toLowerCase().includes(q)
    );
  }, [auditLogs, searchQuery]);

  return (
    <Card dir={isRTL ? 'rtl' : 'ltr'} className="rounded-2xl border-slate-200/90 dark:border-slate-800 shadow-sm bg-white dark:bg-slate-900 overflow-hidden font-tajawal">
      <CardHeader className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-100 dark:border-slate-800/80 pb-3.5">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-blue-50 dark:bg-blue-950/60 text-[#1C3D74] dark:text-[#46C1BE] flex items-center justify-center shrink-0 border border-blue-100 dark:border-blue-900/60">
            <Activity className="h-4 w-4" />
          </div>
          <div>
            <CardTitle className="font-cairo text-sm sm:text-base font-extrabold text-slate-900 dark:text-white">
              {isRTL ? 'سجل العمليات والأنشطة' : 'Activity & Audit Log'}
            </CardTitle>
            <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">
              {isRTL ? `إجمالي العمليات: ${auditLogs.length} عملية` : `Total events: ${auditLogs.length}`}
            </p>
          </div>
        </div>

        {auditLogs.length > 0 && (
          <div className="relative w-full sm:w-56">
            <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={isRTL ? 'بحث في السجل...' : 'Search logs...'}
              className="ps-9 pe-7 h-9 rounded-xl text-xs bg-slate-50/80 dark:bg-slate-950 border-slate-200/90 dark:border-slate-800 focus:ring-2 focus:ring-[#46C1BE]/20 focus:border-[#46C1BE]"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute end-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                <X className="h-3 w-3" />
              </button>
            )}
          </div>
        )}
      </CardHeader>

      <CardContent className="p-5">
        {auditLogs.length === 0 ? (
          <div className="text-center py-12 px-4">
            <div className="w-12 h-12 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center mx-auto mb-2.5 text-slate-400">
              <Activity className="h-6 w-6" />
            </div>
            <p className="font-bold text-xs text-slate-700 dark:text-slate-300 font-cairo">
              {isRTL ? 'لا توجد أنشطة مسجلة لهذه المدرسة حتى الآن' : 'No activity logs found for this school'}
            </p>
            <p className="text-[11px] text-slate-400 mt-0.5">
              {isRTL ? 'يتم توثيق كافة التعديلات والتغييرات الإدارية تلقائياً في هذا السجل.' : 'All administrative actions are automatically recorded here.'}
            </p>
          </div>
        ) : filteredLogs.length === 0 ? (
          <div className="text-center py-8 px-4 space-y-2.5">
            <p className="text-xs font-bold text-slate-600 dark:text-slate-300 font-cairo">
              {isRTL ? 'لم يتم العثور على سجلات مطابقة للبحث' : 'No logs matched your search'}
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSearchQuery('')}
              className="rounded-xl text-xs font-bold h-8 px-3"
            >
              {isRTL ? 'إلغاء التصفية' : 'Clear Filter'}
            </Button>
          </div>
        ) : (
          <div className="relative ps-4 sm:ps-5 space-y-3 before:absolute before:top-2 before:bottom-2 before:start-2 sm:before:start-2.5 before:w-0.5 before:bg-slate-200 dark:before:bg-slate-800">
            {filteredLogs.map((log, idx) => {
              const actionCfg = resolveActivity(log.action, isRTL);
              const ActionIcon = actionCfg.icon;

              return (
                <div
                  key={idx}
                  className="relative flex items-start gap-3.5 p-3.5 rounded-xl border border-slate-200/70 dark:border-slate-800/80 bg-slate-50/40 dark:bg-slate-800/20 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-all shadow-2xs group"
                >
                  {/* Action Icon Badge */}
                  <div className={`p-2 rounded-lg shrink-0 ${actionCfg.color} shadow-2xs`}>
                    <ActionIcon className="h-3.5 w-3.5" strokeWidth={2} />
                  </div>

                  <div className="flex-1 min-w-0 space-y-1">
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <p className="text-xs font-bold text-slate-900 dark:text-white font-cairo">
                        {actionCfg.label}
                      </p>
                      <div className="flex items-center gap-1 text-[11px] font-mono text-slate-400 shrink-0">
                        <Clock className="h-3 w-3" />
                        <span>
                          {log.timestamp ? new Date(log.timestamp).toLocaleString(isRTL ? 'ar-SA' : 'en-GB') : ''}
                        </span>
                      </div>
                    </div>

                    {log.actor_email && (
                      <div className="flex items-center gap-1 text-[11px] text-slate-500 dark:text-slate-400">
                        <User className="h-3 w-3" />
                        <span>{t('by') || (isRTL ? 'بواسطة:' : 'By:')}</span>
                        <span className="font-mono text-slate-700 dark:text-slate-300 font-medium truncate max-w-[200px]" dir="ltr">
                          {log.actor_email}
                        </span>
                      </div>
                    )}

                    {log.new_values?.reason && (
                      <div className="flex items-start gap-1.5 p-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-200/60 dark:border-slate-800 text-[11px] text-slate-700 dark:text-slate-300">
                        <MessageSquare className="h-3 w-3 text-slate-400 shrink-0 mt-0.5" />
                        <span className="font-medium">
                          {t('reason') || (isRTL ? 'ملاحظة:' : 'Note:')} {log.new_values.reason}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
