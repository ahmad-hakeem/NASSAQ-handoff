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
 * @param {object} api  - axios instance من useAuth
 * @param {object|null} slot - { timetable_id, class_id, day_of_week, period_number, subject_id? }
 * @param {object} filters   - { specialty, only_available }
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
      if (filters?.only_available) params.only_available = true;

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
      filters?.specialty, filters?.only_available]);

  useEffect(() => { fetchCandidates(); }, [fetchCandidates]);

  return { candidates, loading, error, refetch: fetchCandidates };
}
