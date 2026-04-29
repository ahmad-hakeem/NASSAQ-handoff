import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * بناء معرف خانة مركّب يطابق عقد الـ API:
 *   "{timetable_id}__{class_id}__{day_of_week}__{period_number}"
 */
export function buildSlotId({ timetable_id, class_id, day_of_week, period_number }) {
  return `${timetable_id}__${class_id}__${day_of_week}__${period_number}`;
}

/**
 * يجلب مرشحي معلمين لخانة فارغة من
 *   GET /api/schedule/slots/{slot_id}/candidates
 *
 * ملاحظة: هذا hook قديم يخدم خانات الجدول-المسوّدة. للاستبدال على جدول
 * منشور (تغطية غياب) استخدم `useStandbyCandidates`.
 */
export function useScheduleCandidates(api, slot, filters) {
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const reqIdRef = useRef(0);

  const fetchCandidates = useCallback(async () => {
    if (!slot || !slot.timetable_id || !slot.class_id) {
      setCandidates([]);
      return;
    }
    const reqId = ++reqIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const slotId = buildSlotId(slot);
      const params = {};
      if (slot.subject_id) params.subject_id = slot.subject_id;
      if (filters?.specialty) params.specialty = filters.specialty;
      if (filters?.available_only) params.available_only = true;

      const res = await api.get(`/schedule/slots/${encodeURIComponent(slotId)}/candidates`, { params });
      if (reqIdRef.current !== reqId) return; // stale
      setCandidates(res.data?.candidates || []);
    } catch (err) {
      if (reqIdRef.current !== reqId) return;
      const msg = err.response?.data?.detail || err.message || 'فشل جلب المرشحين';
      setError(msg);
      setCandidates([]);
    } finally {
      if (reqIdRef.current === reqId) setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, slot?.timetable_id, slot?.class_id, slot?.day_of_week,
      slot?.period_number, slot?.subject_id,
      filters?.specialty, filters?.available_only]);

  useEffect(() => { fetchCandidates(); }, [fetchCandidates]);

  return { candidates, loading, error, refetch: fetchCandidates };
}

/**
 * يجلب مرشحي «جدول الانتظار» لتغطية غياب معلم في خانة محدّدة.
 *   GET /api/standby/candidates?day=&period=&original_session_id=&absence_date=
 *
 * @param {object} api  - axios instance
 * @param {object|null} slot - { day_of_week, period_number, original_session_id?, absence_date?, school_id? }
 * @param {object} opts - { limit }
 */
export function useStandbyCandidates(api, slot, opts = {}) {
  const [data, setData] = useState({ candidates: [], formula: '', formula_legend_ar: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const reqIdRef = useRef(0);
  const limit = opts.limit || 3;

  const fetchCandidates = useCallback(async () => {
    if (!slot || !slot.day_of_week || !slot.period_number) {
      setData({ candidates: [], formula: '', formula_legend_ar: '' });
      return;
    }
    const reqId = ++reqIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const params = {
        day: slot.day_of_week,
        period: slot.period_number,
        limit,
      };
      if (slot.original_session_id) params.original_session_id = slot.original_session_id;
      if (slot.absence_date) params.absence_date = slot.absence_date;
      if (slot.school_id) params.school_id = slot.school_id;

      const res = await api.get('/standby/candidates', {
        params,
        headers: slot.school_id ? { 'X-School-Context': slot.school_id } : undefined,
      });
      if (reqIdRef.current !== reqId) return;
      setData({
        candidates: res.data?.candidates || [],
        formula: res.data?.formula || '',
        formula_legend_ar: res.data?.formula_legend_ar || '',
        total_eligible: res.data?.total_eligible || 0,
        original_session: res.data?.original_session || null,
      });
    } catch (err) {
      if (reqIdRef.current !== reqId) return;
      const msg = err.response?.data?.detail || err.message || 'فشل جلب مرشحي الانتظار';
      setError(msg);
      setData({ candidates: [], formula: '', formula_legend_ar: '' });
    } finally {
      if (reqIdRef.current === reqId) setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, slot?.day_of_week, slot?.period_number,
      slot?.original_session_id, slot?.absence_date, slot?.school_id, limit]);

  useEffect(() => { fetchCandidates(); }, [fetchCandidates]);

  return { ...data, loading, error, refetch: fetchCandidates };
}
