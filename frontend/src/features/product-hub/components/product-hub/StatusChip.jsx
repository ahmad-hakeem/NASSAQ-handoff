import React from 'react';
import { STATUS_CONFIG } from './hubConstants';

export function StatusChip({ status, size = 'default', showIcon = false }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.new;
  const Icon = cfg.icon;

  const sizeClasses = {
    sm: 'text-[10px] px-2 py-0.5',
    default: 'text-xs px-2.5 py-1',
    lg: 'text-sm px-3 py-1.5',
  };

  return (
    <span className={`inline-flex items-center gap-1 rounded-full font-medium text-white ${cfg.color} ${sizeClasses[size]}`}>
      {showIcon && Icon && <Icon className={size === 'sm' ? 'h-3 w-3' : 'h-3.5 w-3.5'} />}
      {cfg.label}
    </span>
  );
}
