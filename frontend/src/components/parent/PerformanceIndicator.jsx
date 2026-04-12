import React from 'react';
import { TrendingUp, TrendingDown, Minus, BarChart3 } from 'lucide-react';
import { useTranslation } from '../../contexts/ThemeContext';

const PerformanceIndicator = ({ performance }) => {
  const { t } = useTranslation();

  if (!performance) return null;

  const { level, trend, trend_direction, phrase, overall_average } = performance;

  const trendConfig = {
    up: {
      icon: TrendingUp,
      color: 'text-emerald-600',
      bg: 'bg-emerald-50',
      border: 'border-emerald-100',
      label: `+${Math.abs(trend)}%`,
      desc: t('improvedFromLastWeek'),
    },
    down: {
      icon: TrendingDown,
      color: 'text-red-500',
      bg: 'bg-red-50',
      border: 'border-red-100',
      label: `-${Math.abs(trend)}%`,
      desc: t('declinedFromLastWeek'),
    },
    stable: {
      icon: Minus,
      color: 'text-amber-600',
      bg: 'bg-amber-50',
      border: 'border-amber-100',
      label: '0%',
      desc: t('stableComparedToLastWeek'),
    },
  };

  const config = trendConfig[trend_direction] || trendConfig.stable;
  const TrendIcon = config.icon;

  const levelColors = {
    'ممتاز': { gradient: 'from-emerald-500 to-emerald-600', ring: 'ring-emerald-200' },
    'جيد جداً': { gradient: 'from-blue-500 to-blue-600', ring: 'ring-blue-200' },
    'جيد ومستقر': { gradient: 'from-brand-navy to-brand-navy', ring: 'ring-brand-navy/20' },
    'مقبول': { gradient: 'from-amber-500 to-amber-600', ring: 'ring-amber-200' },
    'يحتاج تحسين': { gradient: 'from-red-500 to-red-600', ring: 'ring-red-200' },
  };

  const levelStyle = levelColors[level] || { gradient: 'from-brand-navy to-brand-navy', ring: 'ring-brand-navy/20' };

  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-lg bg-brand-navy/5 flex items-center justify-center">
          <BarChart3 className="w-4 h-4 text-brand-navy" />
        </div>
        <p className="text-sm font-semibold text-gray-800 font-cairo">{t('performanceIndicator')}</p>
      </div>

      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`px-4 py-1.5 rounded-full text-white text-sm font-bold bg-gradient-to-r ${levelStyle.gradient} ring-2 ${levelStyle.ring} ring-offset-1`}>
            {level}
          </div>
          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border ${config.color} ${config.bg} ${config.border}`}>
            <TrendIcon className="w-3.5 h-3.5" />
            <span>{config.label}</span>
          </div>
        </div>
        <span className="text-lg font-bold text-gray-700">{overall_average}%</span>
      </div>

      <div className="h-2 bg-gray-100 rounded-full overflow-hidden mb-2">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${levelStyle.gradient} transition-all duration-700 ease-out`}
          style={{ width: `${overall_average}%` }}
        />
      </div>

      <div className="flex items-center justify-between">
        <p className="text-xs text-gray-500 italic">{phrase}</p>
        <p className="text-[10px] text-gray-400">{config.desc}</p>
      </div>
    </div>
  );
};

export default PerformanceIndicator;
