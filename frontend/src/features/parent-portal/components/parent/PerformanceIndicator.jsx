import React from 'react';
import { TrendingUp, TrendingDown, Minus, BarChart3 } from 'lucide-react';
import { useTranslation } from '@/shared/contexts/ThemeContext';

const PerformanceIndicator = ({ performance }) => {
  const { t } = useTranslation();

  if (!performance) return null;

  const { level, trend, trend_direction, phrase, overall_average } = performance;

  const trendConfig = {
    up: {
      icon: TrendingUp,
      color: 'text-emerald-600 dark:text-emerald-400',
      bg: 'bg-emerald-50 dark:bg-emerald-950/30',
      border: 'border-emerald-100 dark:border-emerald-900/40',
      label: `+${Math.abs(trend)}%`,
      desc: t('improvedFromLastWeek'),
    },
    down: {
      icon: TrendingDown,
      color: 'text-red-500 dark:text-red-400',
      bg: 'bg-red-50 dark:bg-red-950/30',
      border: 'border-red-100 dark:border-red-900/40',
      label: `-${Math.abs(trend)}%`,
      desc: t('declinedFromLastWeek'),
    },
    stable: {
      icon: Minus,
      color: 'text-amber-600 dark:text-amber-400',
      bg: 'bg-amber-50 dark:bg-amber-950/30',
      border: 'border-amber-100 dark:border-amber-900/40',
      label: '0%',
      desc: t('stableComparedToLastWeek'),
    },
  };

  const config = trendConfig[trend_direction] || trendConfig.stable;
  const TrendIcon = config.icon;

  // Map both Arabic (current backend) and English level strings to a styling
  // bucket so the badge stays themed regardless of which language the API
  // returns. Backend should ideally send a stable enum — handled defensively
  // here for both legacy Arabic and forward-compatible English values.
  const levelBuckets = {
    excellent: ['ممتاز', 'Excellent', t('excellent')],
    veryGood:  ['جيد جداً', 'Very Good', t('veryGood')],
    good:      ['جيد ومستقر', 'Good & stable', t('goodAndStable')],
    acceptable:['مقبول', 'Acceptable', t('acceptable')],
    weak:      ['يحتاج تحسين', 'Needs Improvement', t('needsImprovement')],
  };

  const bucketStyles = {
    excellent: { gradient: 'from-emerald-500 to-emerald-600', ring: 'ring-emerald-200 dark:ring-emerald-700/40' },
    veryGood:  { gradient: 'from-blue-500 to-blue-600', ring: 'ring-blue-200 dark:ring-blue-700/40' },
    good:      { gradient: 'from-brand-navy to-brand-navy', ring: 'ring-brand-navy/20 dark:ring-brand-turquoise/40' },
    acceptable:{ gradient: 'from-amber-500 to-amber-600', ring: 'ring-amber-200 dark:ring-amber-700/40' },
    weak:      { gradient: 'from-red-500 to-red-600', ring: 'ring-red-200 dark:ring-red-700/40' },
  };

  const matchedBucket =
    Object.entries(levelBuckets).find(([, names]) => names.includes(level))?.[0] || 'good';
  const levelStyle = bucketStyles[matchedBucket];

  return (
    <div className="bg-card rounded-2xl p-4 shadow-sm border border-border">
      <div className="flex items-center gap-2 mb-3">
        <div className="w-8 h-8 rounded-lg bg-brand-navy/5 dark:bg-brand-turquoise/15 flex items-center justify-center">
          <BarChart3 className="w-4 h-4 text-brand-navy dark:text-brand-turquoise" />
        </div>
        <p className="text-sm font-semibold text-foreground font-cairo">{t('performanceIndicator')}</p>
      </div>

      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`px-4 py-1.5 rounded-full text-white text-sm font-bold bg-gradient-to-r ${levelStyle.gradient} ring-2 ${levelStyle.ring} ring-offset-1 ring-offset-card`}>
            {level}
          </div>
          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border ${config.color} ${config.bg} ${config.border}`}>
            <TrendIcon className="w-3.5 h-3.5" />
            <span>{config.label}</span>
          </div>
        </div>
        <span className="text-lg font-bold text-foreground">{overall_average}%</span>
      </div>

      <div className="h-2 bg-muted rounded-full overflow-hidden mb-2">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${levelStyle.gradient} transition-all duration-700 ease-out`}
          style={{ width: `${overall_average}%` }}
        />
      </div>

      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground italic">{phrase}</p>
        <p className="text-[10px] text-muted-foreground/70">{config.desc}</p>
      </div>
    </div>
  );
};

export default PerformanceIndicator;
