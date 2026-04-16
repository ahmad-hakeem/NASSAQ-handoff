import { useTranslation } from '../../contexts/ThemeContext';
import {
  ScatterChart, Scatter, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts';

const COLORS = {
  stable: '#22c55e',
  needs_followup: '#eab308',
  at_risk: '#ef4444',
  excelling: '#615090',
};

function Dot(props) {
  const { cx, cy, payload } = props;
  return <circle cx={cx} cy={cy} r={6} fill={COLORS[payload.category] || '#888'} />;
}

function TipBox({ active, payload }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-lg bg-white p-3 shadow text-sm" dir="rtl">
      <div className="font-bold text-[#1C3D74]">{p.name}</div>
      <div className="text-neutral-600">{p.class_name}</div>
      <div className="mt-1">Risk: {p.risk_score}</div>
      <div className="text-xs text-neutral-500">{(p.factors || []).join('، ')}</div>
    </div>
  );
}

export default function StudentRiskMap({ points }) {
  const { t } = useTranslation();
  return (
    <div className="rounded-xl bg-white p-5 shadow-[0_4px_20px_-4px_rgba(15,44,89,0.1)]">
      <h3 className="text-lg font-cairo text-[#1C3D74] mb-3">{t('riskMap')}</h3>
      <ResponsiveContainer width="100%" height={340}>
        <ScatterChart margin={{ top: 10, right: 10, bottom: 20, left: 10 }}>
          <CartesianGrid stroke="#EAECED" />
          <XAxis
            type="number" dataKey="x_academic" domain={[0, 100]}
            label={{ value: t('academicAxis'), position: 'insideBottom', offset: -5 }}
          />
          <YAxis
            type="number" dataKey="y_engagement" domain={[0, 100]}
            label={{ value: t('engagementAxis'), angle: -90, position: 'insideLeft' }}
          />
          <Tooltip content={<TipBox />} />
          <Scatter data={points || []} shape={<Dot />} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
