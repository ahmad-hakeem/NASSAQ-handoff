import React from 'react';
import { Inbox } from 'lucide-react';

export function EmptyState({ icon: Icon = Inbox, title = 'لا توجد بيانات', description = '', action, className = '' }) {
  return (
    <div className={`flex flex-col items-center justify-center py-16 px-6 text-center ${className}`}>
      <div className="rounded-2xl bg-slate-50 p-5 mb-4">
        <Icon className="h-10 w-10 text-slate-300" />
      </div>
      <h3 className="text-base font-semibold text-slate-500">{title}</h3>
      {description && <p className="text-sm text-slate-400 mt-1 max-w-sm">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
