/**
 * CoverageNotifyControl — تكليف معلم متاح بتغطية حصة من جدول الانتظار.
 *
 * يُعرض داخل SessionDetailModal لقيادة المدرسة (مدير/مدير مساعد/مشرف منصة)
 * عند فتح حصة معبّأة في الجدول المدرسي. يجلب المعلمين المتاحين في نفس
 * اليوم/الحصة من /standby/candidates، ويتيح اختيار أحدهم وإرسال إشعار
 * تكليف عبر /standby/notify-coverage. الإشعار يتضمّن (اليوم، رقم الحصة،
 * توقيت الحصة، اسم الفصل، المادة) ويُبنى على الخادم.
 *
 * مكوّن مكتفٍ ذاتياً: يدير حالته بنفسه ويستخدم عميل الـ API من AuthContext
 * كي لا نمرّر سلسلة طويلة من الـ props عبر MasterMatrix.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Loader2, Send, UserCheck } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/shared/components/ui/button';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '@/shared/components/ui/select';
import { useAuth } from '@/shared/contexts/AuthContext';
import { useTranslation } from '@/shared/contexts/ThemeContext';
import { useNassaqAlert } from '@/shared/components/ui/NassaqAlertDialog';

export default function CoverageNotifyControl({ session, schoolId }) {
  const { api } = useAuth();
  const { t } = useTranslation();
  const { nassaqError } = useNassaqAlert();

  const day = session?.day_of_week || null;
  const period = session?.slot_number ?? session?.period_number ?? null;
  const originalSessionId = session?.session_id || session?.id || null;

  const [loading, setLoading] = useState(false);
  const [candidates, setCandidates] = useState([]);
  const [selected, setSelected] = useState('');
  const [sending, setSending] = useState(false);
  const [sentTo, setSentTo] = useState(null);

  useEffect(() => {
    let cancelled = false;
    if (!day || !period || !schoolId) {
      setCandidates([]);
      return undefined;
    }
    setLoading(true);
    setSelected('');
    setSentTo(null);
    (async () => {
      try {
        const res = await api.get('/standby/candidates', {
          params: {
            day,
            period,
            original_session_id: originalSessionId,
            school_id: schoolId,
            limit: 10,
          },
          headers: { 'X-School-Context': schoolId },
        });
        if (!cancelled) setCandidates(res?.data?.candidates || []);
      } catch (err) {
        if (!cancelled) setCandidates([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [api, day, period, originalSessionId, schoolId]);

  const handleSend = useCallback(async () => {
    if (!selected || !originalSessionId || sending) return;
    setSending(true);
    try {
      await api.post(
        '/standby/notify-coverage',
        { original_session_id: originalSessionId, substitute_teacher_id: selected },
        { params: { school_id: schoolId }, headers: { 'X-School-Context': schoolId } },
      );
      const cand = candidates.find((c) => c.teacher_id === selected);
      setSentTo(selected);
      toast.success(t('coverageNotifySuccess'), {
        description: t('substituteWithName', { name: cand?.teacher_name || '' }),
      });
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const msg = (typeof detail === 'string' && /[\u0600-\u06FF]/.test(detail))
        ? detail
        : t('coverageNotifyFailed');
      nassaqError(msg);
    } finally {
      setSending(false);
    }
  }, [api, selected, originalSessionId, schoolId, sending, candidates, t, nassaqError]);

  if (!day || !period || !originalSessionId) return null;

  return (
    <div className="border-t border-brand-navy/10 pt-3 space-y-2" data-testid="coverage-control">
      <div className="flex items-center gap-1.5 text-xs font-cairo font-bold text-brand-navy/80">
        <UserCheck className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden="true" />
        {t('assignCoverageTitle')}
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-xs font-tajawal text-brand-navy/60 py-2">
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
          {t('loadingAvailableTeachers')}
        </div>
      ) : candidates.length === 0 ? (
        <p
          className="text-xs font-tajawal text-brand-navy/60 bg-brand-navy/5 rounded-lg px-3 py-2 text-center"
          data-testid="coverage-empty"
        >
          {t('noAvailableTeachersThisPeriod')}
        </p>
      ) : (
        <div className="flex flex-col gap-2">
          <Select value={selected} onValueChange={setSelected} disabled={sending}>
            <SelectTrigger data-testid="coverage-teacher-select" className="w-full bg-white/70">
              <SelectValue placeholder={t('selectAvailableTeacher')} />
            </SelectTrigger>
            <SelectContent>
              {candidates.map((c) => {
                const showSpecialty = c.specialty && c.specialty !== 'غير محدد';
                return (
                  <SelectItem key={c.teacher_id} value={c.teacher_id}>
                    {c.teacher_name}{showSpecialty ? ` — ${c.specialty}` : ''}
                  </SelectItem>
                );
              })}
            </SelectContent>
          </Select>
          <Button
            data-testid="coverage-send-btn"
            onClick={handleSend}
            disabled={!selected || sending || sentTo === selected}
            className="w-full bg-brand-turquoise hover:bg-brand-turquoise-dark text-white gap-1.5"
          >
            {sending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <Send className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden="true" />
            )}
            {sentTo === selected ? t('coverageNotifySent') : t('assignAndNotify')}
          </Button>
        </div>
      )}
    </div>
  );
}
