import { useTranslation } from '@/shared/contexts/ThemeContext';
import { CheckCircle2, AlertTriangle, TrendingDown, Star } from 'lucide-react';

const CARDS = [
  { key: 'stable',         color: '#22c55e', Icon: CheckCircle2,  labelKey: 'stable' },
  { key: 'needs_followup', color: '#eab308', Icon: AlertTriangle, labelKey: 'needsFollowup' },
  { key: 'at_risk',        color: '#ef4444', Icon: TrendingDown,  labelKey: 'educationalRisk' },
  { key: 'excelling',      color: '#615090', Icon: Star,          labelKey: 'excelling' },
];

export default function ExecutiveSummaryCards({ summary }) {
  const { t } = useTranslation();
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {CARDS.map(({ key, color, Icon, labelKey }) => {
        const v = summary?.[key] || { count: 0, percentage: 0 };
        return (
          <div
            key={key}
            className="rounded-xl bg-white p-5 shadow-[0_4px_20px_-4px_rgba(15,44,89,0.1)] border-e-4"
            style={{ borderInlineEndColor: color }}
          >
            <div className="flex items-start justify-between">
              <div>
                <div className="text-3xl font-cairo font-bold" style={{ color }}>
                  {v.percentage}%
                </div>
                <div className="text-sm text-[#312E2F] mt-1">{t(labelKey)}</div>
                <div className="text-xs text-neutral-500 mt-1">{v.count}</div>
              </div>
              <Icon className="h-6 w-6" style={{ color }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
