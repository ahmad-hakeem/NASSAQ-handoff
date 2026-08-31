import React, { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Input } from '@/shared/components/ui/input';
import { Button } from '@/shared/components/ui/button';
import {
  Users, CheckCircle2, XCircle, Search, X, Copy, Shield, Filter
} from 'lucide-react';
import { toast } from 'sonner';
import { ROLE_LABELS } from '../../constants/schoolConstants';

export default function SchoolUsersTab({ users = [], isRTL, t }) {
  const [userSearch, setUserSearch] = useState('');
  const [selectedRole, setSelectedRole] = useState('all');

  // Available roles present in the data
  const availableRoles = useMemo(() => {
    const set = new Set(users.map(u => u.role).filter(Boolean));
    return ['all', ...Array.from(set)];
  }, [users]);

  const filteredUsers = useMemo(() => {
    let list = users;
    if (selectedRole !== 'all') {
      list = list.filter(u => u.role === selectedRole);
    }
    if (userSearch.trim()) {
      const q = userSearch.toLowerCase().trim();
      list = list.filter(u =>
        u.full_name?.toLowerCase().includes(q) ||
        u.email?.toLowerCase().includes(q) ||
        u.phone?.includes(q)
      );
    }
    return list;
  }, [users, userSearch, selectedRole]);

  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text);
    toast.success(isRTL ? `تم نسخ ${label}` : `${label} copied`);
  };

  return (
    <Card className="rounded-2xl border-slate-200/90 dark:border-slate-800 shadow-sm bg-white dark:bg-slate-900 overflow-hidden font-tajawal">
      <CardHeader className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-slate-100 dark:border-slate-800/80 pb-3.5">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-blue-50 dark:bg-blue-950/60 text-[#1C3D74] dark:text-[#46C1BE] flex items-center justify-center shrink-0 border border-blue-100 dark:border-blue-900/60">
            <Users className="h-4 w-4" />
          </div>
          <div>
            <CardTitle className="font-cairo text-sm sm:text-base font-extrabold text-slate-900 dark:text-white">
              {isRTL ? 'دليل مستخدمي المدرسة' : 'School Users Directory'}
            </CardTitle>
            <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">
              {isRTL ? `إجمالي الحسابات: ${users.length} مستخدم` : `Total registered accounts: ${users.length}`}
            </p>
          </div>
        </div>

        {/* Filters & Search Row */}
        <div className="flex flex-wrap items-center gap-2.5 w-full md:w-auto">
          {/* Quick Search */}
          <div className="relative flex-1 md:w-56">
            <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
            <Input
              value={userSearch}
              onChange={(e) => setUserSearch(e.target.value)}
              placeholder={isRTL ? 'بحث بالاسم أو البريد...' : 'Search by name or email...'}
              className="ps-9 pe-7 h-8.5 rounded-xl text-xs bg-slate-50/80 dark:bg-slate-950 border-slate-200/90 dark:border-slate-800 focus:ring-2 focus:ring-[#46C1BE]/20 focus:border-[#46C1BE]"
            />
            {userSearch && (
              <button
                onClick={() => setUserSearch('')}
                className="absolute end-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
              >
                <X className="h-3 w-3" />
              </button>
            )}
          </div>
        </div>
      </CardHeader>

      {/* Role Filter Chips */}
      {availableRoles.length > 2 && (
        <div className="px-5 py-2 bg-slate-50/50 dark:bg-slate-800/30 border-b border-slate-100 dark:border-slate-800/80 flex items-center gap-1.5 overflow-x-auto text-xs">
          <Filter className="h-3 w-3 text-slate-400 me-1 shrink-0" />
          {availableRoles.map((role) => {
            const roleCfg = ROLE_LABELS[role] || { ar: role, en: role };
            const isActive = selectedRole === role;
            return (
              <button
                key={role}
                onClick={() => setSelectedRole(role)}
                className={`px-2.5 py-0.5 rounded-lg text-xs font-bold transition-all whitespace-nowrap ${
                  isActive
                    ? 'bg-[#1C3D74] text-white shadow-2xs dark:bg-[#46C1BE] dark:text-slate-950'
                    : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 border border-slate-200/80 dark:border-slate-700'
                }`}
              >
                {role === 'all' ? (isRTL ? 'الكل' : 'All') : (isRTL ? roleCfg.ar : roleCfg.en)}
              </button>
            );
          })}
        </div>
      )}

      <CardContent className="p-0">
        {users.length === 0 ? (
          <div className="text-center py-12 px-4">
            <div className="w-12 h-12 rounded-xl bg-slate-100 dark:bg-slate-800 flex items-center justify-center mx-auto mb-2.5 text-slate-400">
              <Users className="h-6 w-6" />
            </div>
            <p className="font-bold text-xs text-slate-700 dark:text-slate-300 font-cairo">
              {t('noUsersFound') || (isRTL ? 'لا يوجد مستخدمون مسجلون لهذه المدرسة حالياً' : 'No users registered for this school yet')}
            </p>
            <p className="text-[11px] text-slate-400 mt-0.5">
              {isRTL ? 'سيظهر المعلمون والمشرفون والطلاب هنا بمجرد إضافتهم.' : 'Teachers, admins, and students will appear here once added.'}
            </p>
          </div>
        ) : filteredUsers.length === 0 ? (
          <div className="text-center py-8 px-4 space-y-2">
            <p className="text-xs font-bold text-slate-600 dark:text-slate-300 font-cairo">
              {isRTL ? 'لم يتم العثور على نتائج مطابقة لبحثك' : 'No users matching your search filters'}
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => { setUserSearch(''); setSelectedRole('all'); }}
              className="rounded-xl text-xs font-bold h-8 px-3"
            >
              {isRTL ? 'إعادة ضبط البحث' : 'Reset Search'}
            </Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-slate-50/80 dark:bg-slate-800/50 border-b border-slate-200/80 dark:border-slate-800 text-slate-600 dark:text-slate-300 font-cairo">
                  <th className="p-3 font-bold text-start">{t('name') || (isRTL ? 'المستخدم' : 'User')}</th>
                  <th className="p-3 font-bold text-start">{t('email') || (isRTL ? 'البريد الإلكتروني' : 'Email')}</th>
                  <th className="p-3 font-bold text-center">{t('role') || (isRTL ? 'الدور' : 'Role')}</th>
                  <th className="p-3 font-bold text-center">{t('status2') || (isRTL ? 'الحالة' : 'Status')}</th>
                  <th className="p-3 font-bold text-center">{isRTL ? 'تاريخ الإضافة' : 'Joined Date'}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/80">
                {filteredUsers.map((user) => {
                  const roleCfg = ROLE_LABELS[user.role] || { ar: user.role, en: user.role, color: 'bg-slate-100 text-slate-700' };
                  return (
                    <tr key={user.id} className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40 transition-colors">
                      <td className="p-3">
                        <div className="flex items-center gap-2.5">
                          <div className="w-7.5 h-7.5 rounded-lg bg-blue-50 dark:bg-blue-950/60 text-[#1C3D74] dark:text-[#46C1BE] border border-blue-100 dark:border-blue-900/60 flex items-center justify-center font-bold text-xs shrink-0 select-none">
                            {user.full_name?.trim()?.charAt(0) || '?'}
                          </div>
                          <div className="min-w-0">
                            <span className="font-bold text-slate-900 dark:text-white block truncate max-w-[180px]">
                              {user.full_name || '—'}
                            </span>
                            {user.phone && (
                              <span className="text-[10px] font-mono text-slate-400 block" dir="ltr">{user.phone}</span>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="p-3 font-mono text-slate-600 dark:text-slate-300">
                        <div className="flex items-center gap-1" dir="ltr">
                          <span className="truncate max-w-[200px]">{user.email}</span>
                          <button
                            type="button"
                            onClick={() => copyToClipboard(user.email, isRTL ? 'البريد الإلكتروني' : 'Email')}
                            className="p-0.5 rounded text-slate-400 hover:text-[#1C3D74] dark:hover:text-[#46C1BE] hover:bg-slate-200/60 dark:hover:bg-slate-700 transition-colors"
                            title={isRTL ? 'نسخ البريد' : 'Copy email'}
                          >
                            <Copy className="h-3 w-3" />
                          </button>
                        </div>
                      </td>
                      <td className="p-3 text-center">
                        <Badge className={`text-[10px] font-bold px-2 py-0.5 rounded-md ${roleCfg.color}`}>
                          {isRTL ? roleCfg.ar : roleCfg.en}
                        </Badge>
                      </td>
                      <td className="p-3 text-center">
                        {user.is_active !== false ? (
                          <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-bold text-xs">
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            <span>{t('active') || (isRTL ? 'نشط' : 'Active')}</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-rose-500 font-bold text-xs">
                            <XCircle className="h-3.5 w-3.5" />
                            <span>{isRTL ? 'موقوف' : 'Inactive'}</span>
                          </span>
                        )}
                      </td>
                      <td className="p-3 text-center text-slate-400 font-mono text-[11px]">
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
