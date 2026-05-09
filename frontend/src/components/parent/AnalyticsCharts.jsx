import React from 'react';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  PieChart, Pie, Cell,
  ResponsiveContainer,
} from 'recharts';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';

export const GaugeChart = ({ value, level }) => {
  const { isDark } = useTheme();
  const gaugeData = [
    { name: 'score', value: value },
    { name: 'remaining', value: 100 - value },
  ];

  const getColor = () => {
    if (value >= 90) return '#10b981';
    if (value >= 80) return '#3b82f6';
    if (value >= 70) return '#1C3D74';
    if (value >= 60) return '#f59e0b';
    return '#ef4444';
  };

  const trackFill = isDark ? '#1e293b' : '#f3f4f6';

  return (
    <div className="flex flex-col items-center">
      <div className="w-48 h-28 relative" dir="ltr">
        <ResponsiveContainer width="100%" height={140}>
          <PieChart>
            <Pie
              data={gaugeData}
              cx="50%"
              cy="100%"
              startAngle={180}
              endAngle={0}
              innerRadius={55}
              outerRadius={75}
              dataKey="value"
              stroke="none"
            >
              <Cell fill={getColor()} />
              <Cell fill={trackFill} />
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 text-center">
          <p className="text-2xl font-bold text-foreground">{value}%</p>
          <p className="text-xs text-muted-foreground">{level}</p>
        </div>
      </div>
    </div>
  );
};

export const PerformanceLine = ({ data }) => {
  const { t, language } = useTranslation();
  const { isDark } = useTheme();

  if (!data?.length) return null;

  const gridStroke = isDark ? '#1e293b' : '#f0f0f0';
  const tickFill = isDark ? '#94a3b8' : '#374151';
  const tooltipBg = isDark ? '#0f172a' : '#ffffff';
  const tooltipBorder = isDark ? '#1e293b' : '#e5e7eb';

  return (
    <div className="w-full h-52" dir="ltr">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
          <XAxis dataKey="month" tick={{ fontSize: 10, fill: tickFill }} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: tickFill }} width={30} />
          <Tooltip
            contentStyle={{
              fontSize: 12,
              direction: language === 'ar' ? 'rtl' : 'ltr',
              backgroundColor: tooltipBg,
              border: `1px solid ${tooltipBorder}`,
              color: tickFill,
            }}
          />
          <Line
            type="monotone"
            dataKey="average"
            name={t('chartAverageLabel')}
            stroke="#1C3D74"
            strokeWidth={2}
            dot={{ r: 3, fill: '#1C3D74' }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export const SubjectRadar = ({ data }) => {
  const { t } = useTranslation();
  const { isDark } = useTheme();

  if (!data?.length) return null;

  const gridStroke = isDark ? '#334155' : '#e5e7eb';
  const tickFill = isDark ? '#cbd5e1' : '#374151';

  return (
    <div className="w-full h-64" dir="ltr">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} cx="50%" cy="50%" outerRadius="70%">
          <PolarGrid stroke={gridStroke} />
          <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11, fill: tickFill }} />
          <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 9, fill: tickFill }} />
          <Radar
            name={t('chartScoresLabel')}
            dataKey="score"
            stroke="#1C3D74"
            fill="#1C3D74"
            fillOpacity={0.25}
            strokeWidth={2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
};
