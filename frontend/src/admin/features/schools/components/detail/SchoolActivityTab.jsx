import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Activity } from 'lucide-react';
import { resolveActivity } from '../../constants/schoolConstants';

export default function SchoolActivityTab({
  auditLogs = [],
  isRTL,
  t,
}) {
  return (
    <Card className="rounded-3xl border-slate-200 dark:border-slate-800 shadow-sm bg-white dark:bg-slate-900 overflow-hidden">
      <CardHeader className="border-b border-slate-100 dark:border-slate-800/80 pb-4">
        <CardTitle className="font-cairo text-base font-extrabold flex items-center gap-2 text-slate-900 dark:text-white">
          <Activity className="h-5 w-5 text-[#1C3D74] dark:text-[#46C1BE]" />
          <span>{isRTL ? `سجل النشاط والعمليات (${auditLogs.length})` : `Activity Logs (${auditLogs.length})`}</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 sm:p-6">
        {auditLogs.length === 0 ? (
          <div className="text-center py-12 px-4">
            <div className="w-14 h-14 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center mx-auto mb-3 text-slate-400">
              <Activity className="h-7 w-7" />
            </div>
            <p className="font-bold text-xs text-slate-600 dark:text-slate-400 font-cairo">
              {isRTL ? 'لا يوجد سجل أنشطة مسجل لهذه المدرسة' : 'No activity logs found'}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {auditLogs.map((log, idx) => {
              const actionCfg = resolveActivity(log.action, isRTL);
              const ActionIcon = actionCfg.icon;

              return (
                <div
                  key={idx}
                  className="flex items-start gap-3.5 p-3.5 rounded-2xl border border-slate-100 dark:border-slate-800/80 hover:bg-slate-50 dark:hover:bg-slate-800/30 transition-colors shadow-2xs"
                >
                  <div className={`p-2 rounded-xl shrink-0 ${actionCfg.color}`}>
                    <ActionIcon className="h-4 w-4" strokeWidth={2} />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <p className="text-xs font-bold text-slate-900 dark:text-white font-cairo">
                        {actionCfg.label}
                      </p>
                      <span className="text-[11px] font-mono text-slate-400 shrink-0">
                        {log.timestamp ? new Date(log.timestamp).toLocaleString(isRTL ? 'ar-SA' : 'en-GB') : ''}
                      </span>
                    </div>

                    {log.actor_email && (
                      <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5" dir="ltr">
                        {t('by') || (isRTL ? 'بواسطة:' : 'by')} {log.actor_email}
                      </p>
                    )}

                    {log.new_values?.reason && (
                      <p className="text-[11px] text-slate-600 dark:text-slate-300 mt-1.5 p-2 rounded-xl bg-slate-100 dark:bg-slate-800 font-medium">
                        {t('reason') || (isRTL ? 'السبب:' : 'Reason:')} {log.new_values.reason}
                      </p>
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
