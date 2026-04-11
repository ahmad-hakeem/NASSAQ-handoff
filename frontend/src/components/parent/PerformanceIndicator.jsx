import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

const PerformanceIndicator = ({ performance }) => {
  if (!performance) return null;

  const { level, trend, trend_direction, phrase, overall_average } = performance;

  const trendConfig = {
    up: { icon: TrendingUp, color: 'text-emerald-600', bg: 'bg-emerald-50', label: `تحسن ${Math.abs(trend)}%` },
    down: { icon: TrendingDown, color: 'text-red-500', bg: 'bg-red-50', label: `تراجع ${Math.abs(trend)}%` },
    stable: { icon: Minus, color: 'text-amber-600', bg: 'bg-amber-50', label: 'مستقر' },
  };

  const config = trendConfig[trend_direction] || trendConfig.stable;
  const TrendIcon = config.icon;

  const levelColors = {
    'ممتاز': 'from-emerald-500 to-emerald-600',
    'جيد جداً': 'from-blue-500 to-blue-600',
    'جيد ومستقر': 'from-indigo-500 to-indigo-600',
    'مقبول': 'from-amber-500 to-amber-600',
    'يحتاج تحسين': 'from-red-500 to-red-600',
  };

  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-gray-500 mb-1">مؤشر الأداء</p>
          <div className={`inline-block px-3 py-1 rounded-full text-white text-sm font-bold bg-gradient-to-r ${levelColors[level] || 'from-gray-500 to-gray-600'}`}>
            {level}
          </div>
        </div>
        <div className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ${config.color} ${config.bg}`}>
          <TrendIcon className="w-3.5 h-3.5" />
          <span>{config.label}</span>
        </div>
      </div>
      <p className="text-xs text-gray-500 mt-3">{phrase}</p>
      <div className="mt-2 flex items-center gap-2">
        <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full bg-gradient-to-r ${levelColors[level] || 'from-gray-500 to-gray-600'}`}
            style={{ width: `${overall_average}%` }}
          />
        </div>
        <span className="text-xs font-bold text-gray-600">{overall_average}%</span>
      </div>
    </div>
  );
};

export default PerformanceIndicator;
