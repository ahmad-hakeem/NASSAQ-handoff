import React from 'react';
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  PieChart, Pie, Cell,
  ResponsiveContainer
} from 'recharts';

export const GaugeChart = ({ value, level }) => {
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
              <Cell fill="#f3f4f6" />
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 text-center">
          <p className="text-2xl font-bold text-gray-800">{value}%</p>
          <p className="text-xs text-gray-500">{level}</p>
        </div>
      </div>
    </div>
  );
};

export const PerformanceLine = ({ data }) => {
  if (!data?.length) return null;

  return (
    <div className="w-full h-52" dir="ltr">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="month" tick={{ fontSize: 10 }} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} width={30} />
          <Tooltip contentStyle={{ fontSize: 12, direction: 'rtl' }} />
          <Line
            type="monotone"
            dataKey="average"
            name="المتوسط"
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
  if (!data?.length) return null;

  return (
    <div className="w-full h-64" dir="ltr">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} cx="50%" cy="50%" outerRadius="70%">
          <PolarGrid stroke="#e5e7eb" />
          <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11, fill: '#374151' }} />
          <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 9 }} />
          <Radar
            name="الدرجات"
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
