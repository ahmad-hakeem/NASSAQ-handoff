import { useState, useEffect, useCallback, useRef } from 'react';
import { getApiErrorMessage } from '../utils/apiError';

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
      const msg = getApiErrorMessage(err) || err.message || 'فشل جلب المرشحين';
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
      const msg = getApiErrorMessage(err) || err.message || 'فشل جلب مرشحي الانتظار';
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

/**
 * يجلب كل الحصص الشاغرة لمعلم غائب في تاريخ محدد، مع المرشحين لكل خانة.
 *   GET /api/standby/candidates/bulk?absent_teacher_id=&absence_date=
 *
 * @param {object} api  - axios instance
 * @param {object|null} target - { absent_teacher_id, absence_date?, school_id? }
 * @param {object} opts - { limit_per_slot, enabled }
 */
export function useBulkStandbyCandidates(api, target, opts = {}) {
  const [data, setData] = useState({
    slots: [],
    formula: '',
    formula_legend_ar: '',
    absent_teacher_name: '',
    day_of_week: '',
    day_label_ar: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const reqIdRef = useRef(0);
  const limitPerSlot = opts.limit_per_slot || 3;
  const enabled = opts.enabled !== false;

  const fetchSlots = useCallback(async () => {
    if (!enabled || !target || !target.absent_teacher_id) {
      setData({
        slots: [],
        formula: '',
        formula_legend_ar: '',
        absent_teacher_name: '',
        day_of_week: '',
        day_label_ar: '',
      });
      return;
    }
    const reqId = ++reqIdRef.current;
    setLoading(true);
    setError(null);
    try {
      const params = {
        absent_teacher_id: target.absent_teacher_id,
        limit_per_slot: limitPerSlot,
      };
      if (target.absence_date) params.absence_date = target.absence_date;
      if (target.school_id) params.school_id = target.school_id;

      const res = await api.get('/standby/candidates/bulk', {
        params,
        headers: target.school_id ? { 'X-School-Context': target.school_id } : undefined,
      });
      if (reqIdRef.current !== reqId) return;
      setData({
        slots: res.data?.slots || [],
        formula: res.data?.formula || '',
        formula_legend_ar: res.data?.formula_legend_ar || '',
        absent_teacher_name: res.data?.absent_teacher_name || '',
        day_of_week: res.data?.day_of_week || '',
        day_label_ar: res.data?.day_label_ar || '',
      });
    } catch (err) {
      if (reqIdRef.current !== reqId) return;
      const msg = getApiErrorMessage(err) || err.message || 'فشل جلب الحصص الشاغرة';
      setError(msg);
      setData({
        slots: [],
        formula: '',
        formula_legend_ar: '',
        absent_teacher_name: '',
        day_of_week: '',
        day_label_ar: '',
      });
    } finally {
      if (reqIdRef.current === reqId) setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, target?.absent_teacher_id, target?.absence_date, target?.school_id,
      limitPerSlot, enabled]);

  useEffect(() => { fetchSlots(); }, [fetchSlots]);

  return { ...data, loading, error, refetch: fetchSlots };
}
