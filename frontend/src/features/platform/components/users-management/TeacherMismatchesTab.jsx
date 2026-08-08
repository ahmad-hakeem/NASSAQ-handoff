import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Avatar, AvatarFallback } from '@/shared/components/ui/avatar';
import { Button } from '@/shared/components/ui/button';
import {
  AlertTriangle, ArrowLeft, Building2, Eye, RefreshCw, UserCheck, Wand2,
} from 'lucide-react';

export default function TeacherMismatchesTab({
  mismatches = [],
  total = null,
  loading = false,
  onRefresh,
  onResolve,
  onResolveAll,
  resolvingId = null,
  resolvingAll = false,
}) {
  const navigate = useNavigate();
  const totalCount = total ?? mismatches.length;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between flex-row-reverse">
          <CardTitle className="font-cairo flex items-center gap-2 flex-row-reverse">
            <AlertTriangle className="h-5 w-5 text-amber-600" strokeWidth={1.5} aria-hidden="true" />
            معلمون لم يتم نقلهم
          </CardTitle>
          <div className="flex items-center gap-2 flex-row-reverse">
            <Badge variant="outline" className="text-sm bg-amber-50 text-amber-700 border-amber-200">
              {totalCount} حالة
            </Badge>
            {totalCount > 0 && (
              <Button
                size="sm" className="text-xs bg-brand-turquoise hover:bg-brand-turquoise/90 text-white"
                onClick={onResolveAll}
                disabled={resolvingAll || loading || resolvingId != null}
                data-testid="resolve-all-mismatches"
              >
                {resolvingAll ? (
                  <RefreshCw className="h-3.5 w-3.5 ms-1 animate-spin" strokeWidth={1.5} aria-hidden="true" />
                ) : (
                  <Wand2 className="h-3.5 w-3.5 ms-1" strokeWidth={1.5} aria-hidden="true" />
                )}
                حل كل التعارضات
              </Button>
            )}
            <Button
              variant="ghost" size="icon" className="rounded-xl"
              onClick={onRefresh} disabled={loading || resolvingAll}
              data-testid="refresh-mismatches"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} strokeWidth={1.5} aria-hidden="true" />
            </Button>
          </div>
        </div>
        <p className="text-sm text-muted-foreground text-start">
          هؤلاء المعلمون مرتبطون بمدرسة، لكن سجلهم الأكاديمي ما زال في مدرسة أخرى، لذلك
          لا يظهرون في قائمة معلمي المدرسة المطلوبة. لحل التعارض، قم بإلغاء تفعيل السجل
          القديم في المدرسة الأخرى ثم أعد ربط المعلم بالمدرسة المطلوبة.
        </p>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <RefreshCw className="h-8 w-8 animate-spin text-brand-turquoise" strokeWidth={1.5} aria-hidden="true" />
          </div>
        ) : mismatches.length === 0 ? (
          <div className="py-12 text-center">
            <UserCheck className="h-16 w-16 mx-auto text-emerald-300 mb-4" strokeWidth={1.5} aria-hidden="true" />
            <h3 className="font-bold text-lg mb-2">لا توجد تعارضات</h3>
            <p className="text-muted-foreground">جميع المعلمين مرتبطون بمدارسهم بشكل صحيح</p>
          </div>
        ) : (
          <div className="space-y-3">
            {mismatches.map((m) => (
              <div
                key={m.user_id}
                className="rounded-xl border-2 border-amber-200 bg-amber-50/40 p-4"
                data-testid={`mismatch-${m.user_id}`}
              >
                <div className="flex items-start justify-between gap-3 flex-row-reverse">
                  <div className="flex items-center gap-3 flex-row-reverse">
                    <Avatar className="h-11 w-11">
                      <AvatarFallback className="bg-amber-500 text-white">
                        {(m.full_name || '?').charAt(0)}
                      </AvatarFallback>
                    </Avatar>
                    <div className="text-start">
                      <p className="font-bold">{m.full_name}</p>
                      <p className="text-xs text-muted-foreground">{m.email}</p>
                      {m.is_active === false && (
                        <Badge variant="outline" className="text-[10px] mt-1 bg-red-100 text-red-700 border-red-200">
                          حساب معلّق
                        </Badge>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-row-reverse">
                    <Button
                      size="sm" className="text-xs bg-brand-turquoise hover:bg-brand-turquoise/90 text-white"
                      onClick={() => onResolve?.(m)}
                      disabled={resolvingId === m.user_id}
                      data-testid={`resolve-mismatch-${m.user_id}`}
                    >
                      {resolvingId === m.user_id ? (
                        <RefreshCw className="h-3.5 w-3.5 ms-1 animate-spin" strokeWidth={1.5} aria-hidden="true" />
                      ) : (
                        <Wand2 className="h-3.5 w-3.5 ms-1" strokeWidth={1.5} aria-hidden="true" />
                      )}
                      حل التعارض
                    </Button>
                    <Button
                      variant="outline" size="sm" className="text-xs"
                      onClick={() => navigate(`/admin/users/${m.user_id}`)}
                      data-testid={`view-mismatch-${m.user_id}`}
                    >
                      <Eye className="h-3.5 w-3.5 ms-1" strokeWidth={1.5} aria-hidden="true" />
                      عرض المستخدم
                    </Button>
                  </div>
                </div>

                <div className="mt-4 flex items-center gap-3 flex-wrap text-sm">
                  <div className="flex items-center gap-2 rounded-lg bg-white border px-3 py-2">
                    <Building2 className="h-4 w-4 text-brand-navy" strokeWidth={1.5} aria-hidden="true" />
                    <div className="text-start">
                      <span className="block text-[10px] text-muted-foreground">المدرسة المطلوبة</span>
                      <span className="font-medium">{m.intended_school?.name}</span>
                    </div>
                  </div>
                  <ArrowLeft className="h-4 w-4 text-amber-500" strokeWidth={1.5} aria-hidden="true" />
                  <div className="flex items-center gap-2 rounded-lg bg-white border px-3 py-2">
                    <Building2 className="h-4 w-4 text-amber-600" strokeWidth={1.5} aria-hidden="true" />
                    <div className="text-start">
                      <span className="block text-[10px] text-muted-foreground">السجل الأكاديمي الحالي</span>
                      <span className="font-medium">
                        {(m.record_schools || []).map((s) => s.name).join('، ')}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
