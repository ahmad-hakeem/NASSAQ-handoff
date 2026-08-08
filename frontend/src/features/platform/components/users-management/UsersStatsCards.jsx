import React from 'react';
import { Card, CardContent } from '@/shared/components/ui/card';
import {
  Users, UserCheck, UserX, Shield, Building2,
  GraduationCap, BookOpen, Clock, UserCog
} from 'lucide-react';

export default function UsersStatsCards({ stats }) {
  const cards = [
    { label: 'إجمالي المستخدمين', value: stats.totalUsers, icon: Users, border: 'border-slate-200', bg: 'bg-slate-50', textColor: 'text-slate-600', valueColor: 'text-slate-700', iconColor: 'text-slate-300' },
    { label: 'حسابات نشطة', value: stats.activeUsers, icon: UserCheck, border: 'border-green-200', bg: 'bg-green-50', textColor: 'text-green-600', valueColor: 'text-green-700', iconColor: 'text-green-300' },
    { label: 'حسابات موقوفة', value: stats.suspendedUsers, icon: UserX, border: 'border-red-200', bg: 'bg-red-50', textColor: 'text-red-600', valueColor: 'text-red-700', iconColor: 'text-red-300' },
    { label: 'مدراء المنصة', value: stats.platformAdmins, icon: Shield, border: 'border-purple-200', bg: 'bg-purple-50', textColor: 'text-purple-600', valueColor: 'text-purple-700', iconColor: 'text-purple-300' },
    { label: 'مدراء المدارس', value: stats.schoolAdmins, icon: Building2, border: 'border-teal-200', bg: 'bg-teal-50', textColor: 'text-teal-600', valueColor: 'text-teal-700', iconColor: 'text-teal-300' },
    { label: 'المعلمين', value: stats.teachers, icon: BookOpen, border: 'border-blue-200', bg: 'bg-blue-50', textColor: 'text-blue-600', valueColor: 'text-blue-700', iconColor: 'text-blue-300' },
    { label: 'الطلاب', value: stats.students, icon: GraduationCap, border: 'border-cyan-200', bg: 'bg-cyan-50', textColor: 'text-cyan-600', valueColor: 'text-cyan-700', iconColor: 'text-cyan-300' },
    { label: 'أولياء الأمور', value: stats.parents, icon: UserCog, border: 'border-violet-200', bg: 'bg-violet-50', textColor: 'text-violet-600', valueColor: 'text-violet-700', iconColor: 'text-violet-300' },
    { label: 'طلبات معلقة', value: stats.pendingRequests, icon: Clock, border: 'border-yellow-200', bg: 'bg-yellow-50', textColor: 'text-yellow-600', valueColor: 'text-yellow-700', iconColor: 'text-yellow-300' },
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
                  <p className={`text-xl font-bold ${card.valueColor}`}>
                    {card.value != null ? card.value : '—'}
                  </p>
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
