import { useTranslation } from '../../contexts/ThemeContext';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';

const SLICE_COLORS = {
  attendance: '#eab308',
  participation: '#22c55e',
  behaviour: '#ef4444',
  academic: '#615090',
};

export default function RootCauseChart({ causes }) {
  const { t } = useTranslation();
  const data = Object.entries(causes || {})
    .map(([k, v]) => ({ name: t(k), key: k, value: v.count, pct: v.percentage }))
    .filter((d) => d.value > 0)
    .sort((a, b) => b.value - a.value);

  const total = data.reduce((s, d) => s + d.value, 0);

  return (
    <div className="rounded-xl bg-white p-5 shadow-[0_4px_20px_-4px_rgba(15,44,89,0.1)]">
      <h3 className="text-lg font-cairo text-[#1C3D74] mb-3">{t('rootCauseAnalysis')}</h3>
      {data.length === 0 ? (
        <div className="text-center text-neutral-500 py-12">—</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-center">
          <div className="relative h-[240px]">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={62}
                  outerRadius={92}
                  paddingAngle={2}
                  stroke="none"
                  isAnimationActive={false}
                >
                  {data.map((d) => <Cell key={d.key} fill={SLICE_COLORS[d.key] || '#94a3b8'} />)}
                </Pie>
                <Tooltip
                  formatter={(v, n, p) => [`${v} (${p.payload.pct}%)`, n]}
                  contentStyle={{ borderRadius: 8, fontFamily: 'Cairo, sans-serif' }}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <span className="text-2xl font-bold font-cairo text-[#1C3D74]">{total}</span>
              <span className="text-[11px] text-neutral-500 font-tajawal mt-0.5">{t('total') || 'الإجمالي'}</span>
            </div>
          </div>
          <ul className="space-y-2">
            {data.map((d) => (
              <li
                key={d.key}
                className="flex items-center justify-between gap-3 rounded-lg border border-neutral-100 bg-neutral-50/60 px-3 py-2"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span
                    className="inline-block w-3 h-3 rounded-full shrink-0"
                    style={{ background: SLICE_COLORS[d.key] || '#94a3b8' }}
                  />
                  <span className="text-sm font-cairo text-[#312E2F] truncate">{d.name}</span>
                </div>
                <div className="flex items-baseline gap-2 shrink-0">
                  <span className="text-sm font-bold font-cairo text-[#1C3D74] tabular-nums">{d.value}</span>
                  <span className="text-xs text-neutral-500 tabular-nums">({d.pct}%)</span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
