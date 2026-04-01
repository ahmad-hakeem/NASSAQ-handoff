import React from 'react';

export function StatCard({ label, value, icon: Icon, color = 'text-brand-navy', bg = 'bg-blue-50', trend, className = '' }) {
  return (
    <div className={`group relative overflow-hidden rounded-2xl border bg-white p-5 shadow-sm transition-all hover:shadow-md hover:-translate-y-0.5 ${className}`}>
      <div className="flex items-start justify-between">
        <div className={`rounded-xl p-2.5 ${bg} transition-transform group-hover:scale-110`}>
          {Icon && <Icon className={`h-5 w-5 ${color}`} />}
        </div>
        {trend !== undefined && (
          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${trend >= 0 ? 'bg-emerald-50 text-emerald-600' : 'bg-red-50 text-red-600'}`}>
            {trend >= 0 ? '+' : ''}{trend}%
          </span>
        )}
      </div>
      <div className="mt-3">
        <p className="text-3xl font-bold text-brand-navy tracking-tight">{value ?? 0}</p>
        <p className="text-sm text-muted-foreground mt-0.5">{label}</p>
      </div>
      <div className={`absolute -bottom-4 -left-4 h-20 w-20 rounded-full opacity-5 ${bg}`} />
    </div>
  );
}
