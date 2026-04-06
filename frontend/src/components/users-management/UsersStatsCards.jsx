import React from 'react';
import { Card, CardContent } from '../ui/card';
import {
  Building2, GraduationCap, UserCheck, Clock, Shield, Brain,
  Activity, TrendingUp, Sparkles
} from 'lucide-react';

export default function UsersStatsCards({ stats, totalPendingRequests }) {
  const cards = [
    { label: 'المدارس المسجلة', value: stats.totalSchools, icon: Building2, border: 'border-teal-200', bg: 'bg-teal-50', textColor: 'text-teal-600', valueColor: 'text-teal-700', iconColor: 'text-teal-200' },
    { label: 'الطلاب المسجلين', value: stats.totalStudents, icon: GraduationCap, border: 'border-cyan-200', bg: 'bg-cyan-50', textColor: 'text-cyan-600', valueColor: 'text-cyan-700', iconColor: 'text-cyan-200' },
    { label: 'معلمين المدارس', value: stats.teachersInSchools, icon: UserCheck, border: 'border-blue-200', bg: 'bg-blue-50', textColor: 'text-blue-600', valueColor: 'text-blue-700', iconColor: 'text-blue-200' },
    { label: 'معلمين مستقلين', value: stats.independentTeachers, icon: Sparkles, border: 'border-violet-200', bg: 'bg-violet-50', textColor: 'text-violet-600', valueColor: 'text-violet-700', iconColor: 'text-violet-200' },
    { label: 'حضور الطلاب', value: stats.studentAttendanceRate !== null ? `${stats.studentAttendanceRate}%` : '—', icon: TrendingUp, border: 'border-green-200', bg: 'bg-green-50', textColor: 'text-green-600', valueColor: 'text-green-700', iconColor: 'text-green-200' },
    { label: 'حضور المعلمين', value: stats.teacherAttendanceRate !== null ? `${stats.teacherAttendanceRate}%` : '—', icon: Activity, border: 'border-emerald-200', bg: 'bg-emerald-50', textColor: 'text-emerald-600', valueColor: 'text-emerald-700', iconColor: 'text-emerald-200' },
    { label: 'حسابات المنصة', value: stats.platformAdmins, icon: Shield, border: 'border-purple-200', bg: 'bg-purple-50', textColor: 'text-purple-600', valueColor: 'text-purple-700', iconColor: 'text-purple-200' },
    { label: 'طلبات معلقة', value: totalPendingRequests, icon: Clock, border: 'border-yellow-200', bg: 'bg-yellow-50', textColor: 'text-yellow-600', valueColor: 'text-yellow-700', iconColor: 'text-yellow-200' },
    { label: 'مدارس AI', value: stats.aiEnabledSchools, icon: Brain, border: 'border-indigo-200', bg: 'bg-indigo-50', textColor: 'text-indigo-600', valueColor: 'text-indigo-700', iconColor: 'text-indigo-200' },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 xl:grid-cols-9 gap-3 mb-6">
      {cards.map((card, idx) => {
        const Icon = card.icon;
        return (
          <Card key={idx} className={`${card.border} ${card.bg} cursor-default`}>
            <CardContent className="p-3">
              <div className="flex items-center justify-between flex-row-reverse">
                <div className="text-right">
                  <p className={`${card.textColor} text-xs`}>{card.label}</p>
                  <p className={`text-xl font-bold ${card.valueColor}`}>{card.value}</p>
                </div>
                <Icon className={`h-6 w-6 ${card.iconColor}`} />
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
