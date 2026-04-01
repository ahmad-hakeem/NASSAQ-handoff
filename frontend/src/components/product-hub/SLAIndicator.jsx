import React from 'react';
import { Timer, CheckCircle2, AlertTriangle } from 'lucide-react';

export function SLAIndicator({ issue, size = 'default' }) {
  const slaStatus = issue.sla_status;
  const remaining = issue.sla_remaining_hours;

  if (!slaStatus || slaStatus === 'no_sla') return null;

  const isExceeded = slaStatus === 'exceeded';
  const isWarning = remaining !== undefined && remaining > 0 && remaining <= 12;

  const sizeClasses = {
    sm: 'text-[10px] px-2 py-0.5',
    default: 'text-xs px-2.5 py-1',
    lg: 'text-sm px-3 py-1.5',
  };

  if (isExceeded) {
    return (
      <span className={`inline-flex items-center gap-1 rounded-full font-medium bg-red-100 text-red-700 border border-red-200 animate-pulse ${sizeClasses[size]}`}>
        <AlertTriangle className={size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5'} />
        تجاوز SLA
      </span>
    );
  }

  if (isWarning) {
    return (
      <span className={`inline-flex items-center gap-1 rounded-full font-medium bg-amber-100 text-amber-700 border border-amber-200 ${sizeClasses[size]}`}>
        <Timer className={size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5'} />
        {Math.round(remaining)}h
      </span>
    );
  }

  if (remaining !== undefined && remaining > 0) {
    return (
      <span className={`inline-flex items-center gap-1 rounded-full font-medium bg-emerald-100 text-emerald-700 border border-emerald-200 ${sizeClasses[size]}`}>
        <CheckCircle2 className={size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5'} />
        ضمن SLA
      </span>
    );
  }

  return null;
}
