import React, { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Input } from '@/shared/components/ui/input';
import {
  Users, CheckCircle2, XCircle, Search, X
} from 'lucide-react';
import { ROLE_LABELS } from '../../constants/schoolConstants';

export default function SchoolUsersTab({ users = [], isRTL, t }) {
  const [userSearch, setUserSearch] = useState('');

  const filteredUsers = useMemo(() => {
    if (!userSearch.trim()) return users;
    const q = userSearch.toLowerCase().trim();
    return users.filter(u =>
      u.full_name?.toLowerCase().includes(q) ||
      u.email?.toLowerCase().includes(q) ||
      u.role?.toLowerCase().includes(q)
    );
  }, [users, userSearch]);

  return (
    <Card className="rounded-3xl border-slate-200 dark:border-slate-800 shadow-sm bg-white dark:bg-slate-900 overflow-hidden">
      <CardHeader className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-slate-100 dark:border-slate-800/80 pb-4">
        <CardTitle className="font-cairo text-base font-extrabold flex items-center gap-2 text-slate-900 dark:text-white">
          <Users className="h-5 w-5 text-[#1C3D74] dark:text-[#46C1BE]" />
          <span>{isRTL ? `المستخدمون المسجلون بالمدرسة (${users.length})` : `School Users (${users.length})`}</span>
        </CardTitle>

        {/* Quick User Search */}
        {users.length > 0 && (
          <div className="relative w-full sm:w-64">
            <Search className={`absolute ${isRTL ? 'right-3' : 'left-3'} top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400`} />
            <Input
              value={userSearch}
              onChange={(e) => setUserSearch(e.target.value)}
              placeholder={isRTL ? 'بحث بالاسم أو البريد...' : 'Search user by name/email...'}
              className={`${isRTL ? 'pr-9 pl-7' : 'pl-9 pr-7'} h-9 rounded-xl text-xs bg-slate-50 dark:bg-slate-950 border-slate-200 dark:border-slate-800`}
            />
            {userSearch && (
              <button
                onClick={() => setUserSearch('')}
                className={`absolute ${isRTL ? 'left-2.5' : 'right-2.5'} top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600`}
              >
                <X className="h-3 w-3" />
              </button>
            )}
          </div>
        )}
      </CardHeader>

      <CardContent className="p-0">
        {users.length === 0 ? (
          <div className="text-center py-12 px-4">
            <div className="w-14 h-14 rounded-2xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center mx-auto mb-3 text-slate-400">
              <Users className="h-7 w-7" />
            </div>
            <p className="font-bold text-xs text-slate-600 dark:text-slate-400 font-cairo">
              {t('noUsersFound') || (isRTL ? 'لا يوجد مستخدمين مسجلين لهذه المدرسة حتى الآن' : 'No users registered for this school yet')}
            </p>
          </div>
        ) : filteredUsers.length === 0 ? (
          <div className="text-center py-8 text-xs text-slate-500 font-medium">
            {isRTL ? 'لا توجد نتائج مطابقة لبحث المستخدمين' : 'No users matched your search'}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-slate-50/80 dark:bg-slate-800/50 border-b border-slate-200/80 dark:border-slate-800 text-slate-600 dark:text-slate-300">
                  <th className={`p-3.5 font-bold ${isRTL ? 'text-right' : 'text-left'}`}>{t('name') || (isRTL ? 'الاسم' : 'Name')}</th>
                  <th className={`p-3.5 font-bold ${isRTL ? 'text-right' : 'text-left'}`}>{t('email') || (isRTL ? 'البريد الإلكتروني' : 'Email')}</th>
                  <th className="p-3.5 font-bold text-center">{t('role') || (isRTL ? 'الدور' : 'Role')}</th>
                  <th className="p-3.5 font-bold text-center">{t('status2') || (isRTL ? 'الحالة' : 'Status')}</th>
                  <th className="p-3.5 font-bold text-center">{isRTL ? 'تاريخ الإنشاء' : 'Created At'}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filteredUsers.map((user) => {
                  const roleCfg = ROLE_LABELS[user.role] || { ar: user.role, en: user.role, color: 'bg-slate-100 text-slate-700' };
                  return (
                    <tr key={user.id} className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition-colors">
                      <td className="p-3.5">
                        <div className="flex items-center gap-2.5">
                          <div className="w-8 h-8 rounded-xl bg-blue-50 dark:bg-blue-950/60 text-[#1C3D74] dark:text-[#46C1BE] border border-blue-200 dark:border-blue-800 flex items-center justify-center font-bold text-xs shrink-0">
                            {user.full_name?.charAt(0) || '?'}
                          </div>
                          <span className="font-bold text-slate-900 dark:text-white truncate max-w-[180px]">
                            {user.full_name || '—'}
                          </span>
                        </div>
                      </td>
                      <td className="p-3.5 font-mono text-slate-600 dark:text-slate-400" dir="ltr">
                        {user.email}
                      </td>
                      <td className="p-3.5 text-center">
                        <Badge className={`text-[10px] font-bold px-2.5 py-0.5 rounded-md ${roleCfg.color}`}>
                          {isRTL ? roleCfg.ar : roleCfg.en}
                        </Badge>
                      </td>
                      <td className="p-3.5 text-center">
                        {user.is_active ? (
                          <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-bold">
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            <span>{t('active') || (isRTL ? 'نشط' : 'Active')}</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-rose-500 font-bold">
                            <XCircle className="h-3.5 w-3.5" />
                            <span>{isRTL ? 'موقوف' : 'Inactive'}</span>
                          </span>
                        )}
                      </td>
                      <td className="p-3.5 text-center text-slate-400 font-mono">
                        {user.created_at ? new Date(user.created_at).toLocaleDateString(isRTL ? 'ar-SA' : 'en-GB') : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
