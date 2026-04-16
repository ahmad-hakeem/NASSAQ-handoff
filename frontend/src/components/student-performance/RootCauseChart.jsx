import { useTranslation } from '../../contexts/ThemeContext';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';

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
    .filter((d) => d.value > 0);

  return (
    <div className="rounded-xl bg-white p-5 shadow-[0_4px_20px_-4px_rgba(15,44,89,0.1)]">
      <h3 className="text-lg font-cairo text-[#1C3D74] mb-3">{t('rootCauseAnalysis')}</h3>
      {data.length === 0 ? (
        <div className="text-center text-neutral-500 py-12">—</div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" outerRadius={100} label>
              {data.map((d) => <Cell key={d.key} fill={SLICE_COLORS[d.key]} />)}
            </Pie>
            <Tooltip formatter={(v, n, p) => [`${v} (${p.payload.pct}%)`, n]} />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
