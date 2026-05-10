import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useParentActiveStudent } from '../contexts/ParentActiveStudentContext';

/**
 * Task #146 — children + active selection now come from the global
 * ParentActiveStudentContext (single source of truth, mounted at App root).
 * This hook keeps the per-child live/weekly/notification fetch loops it
 * always owned, but no longer fetches the children list itself and no
 * longer holds a local `selectedChildIndex`.
 */
export default function useParentDashboard() {
  const { api } = useAuth();
  const {
    linkedChildren: children,
    activeChild: selectedChild,
    activeChildId: selectedChildId,
    setActiveChildId,
    isLoading: childrenLoading,
    error: childrenErrorObj,
    refetch: refreshChildren,
  } = useParentActiveStudent();

  const [liveData, setLiveData] = useState(null);
  const [weeklyStory, setWeeklyStory] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [notificationsLoading, setNotificationsLoading] = useState(true);
  const [liveLoading, setLiveLoading] = useState(false);
  const [weeklyLoading, setWeeklyLoading] = useState(false);
  const [liveError, setLiveError] = useState(false);
  const [weeklyError, setWeeklyError] = useState(false);
  const timerRef = useRef(null);
  // Stale-response guard: each per-child fetch captures the *active* child
  // id at request time and discards its result if the active child has
  // since changed. Prevents older responses (rapid switches / out-of-order
  // network) from overwriting state for a different child.
  const activeChildRef = useRef(null);
  activeChildRef.current = selectedChildId;

  const fetchLiveData = useCallback(async (childId) => {
    if (!childId) return;
    setLiveLoading(true);
    setLiveError(false);
    try {
      const res = await api.get(`/parent-portal/child/${childId}/today-live`);
      if (String(activeChildRef.current) !== String(childId)) return;
      setLiveData(res.data);
    } catch {
      if (String(activeChildRef.current) !== String(childId)) return;
      setLiveData(null);
      setLiveError(true);
    } finally {
      if (String(activeChildRef.current) === String(childId)) setLiveLoading(false);
    }
  }, [api]);

  const fetchWeeklyStory = useCallback(async (childId) => {
    if (!childId) return;
    setWeeklyLoading(true);
    setWeeklyError(false);
    try {
      const res = await api.get(`/parent-portal/child/${childId}/weekly-story`);
      if (String(activeChildRef.current) !== String(childId)) return;
      setWeeklyStory(res.data);
    } catch {
      if (String(activeChildRef.current) !== String(childId)) return;
      setWeeklyStory(null);
      setWeeklyError(true);
    } finally {
      if (String(activeChildRef.current) === String(childId)) setWeeklyLoading(false);
    }
  }, [api]);

  const fetchNotifications = useCallback(async () => {
    try {
      const res = await api.get('/parent-portal/notifications');
      setNotifications(res.data?.notifications || []);
    } catch {
      setNotifications([]);
    } finally {
      setNotificationsLoading(false);
    }
  }, [api]);

  useEffect(() => {
    fetchNotifications();
  }, [fetchNotifications]);

  // Reset per-child state whenever the active student changes so we never
  // flash a previous child's live data on the new one's hero. We flip the
  // section loading flags ON synchronously so the dashboard renders local
  // skeletons (instead of a brief blank gap) for the duration of the swap.
  useEffect(() => {
    setLiveData(null);
    setWeeklyStory(null);
    if (selectedChildId) {
      setLiveLoading(true);
      setWeeklyLoading(true);
      fetchLiveData(selectedChildId);
      fetchWeeklyStory(selectedChildId);
    } else {
      setLiveLoading(false);
      setWeeklyLoading(false);
    }
  }, [selectedChildId, fetchLiveData, fetchWeeklyStory]);

  useEffect(() => {
    if (!selectedChildId) return;
    timerRef.current = setInterval(() => {
      fetchLiveData(selectedChildId);
    }, 60000);
    return () => clearInterval(timerRef.current);
  }, [selectedChildId, fetchLiveData]);

  // Back-compat shim: legacy callers used `selectChild(index)`. Translate
  // an index into the corresponding child id and push it through the
  // global context so every other parent page reflects the change.
  const selectChild = useCallback((index) => {
    const c = children?.[index];
    if (c?.id != null) setActiveChildId(c.id);
  }, [children, setActiveChildId]);

  const selectedChildIndex = selectedChildId
    ? Math.max(0, children.findIndex(c => String(c.id) === String(selectedChildId)))
    : 0;

  return {
    children,
    selectedChildIndex,
    selectedChild,
    selectedChildId,
    liveData,
    weeklyStory,
    notifications,
    loading: childrenLoading || notificationsLoading,
    liveLoading,
    weeklyLoading,
    liveError,
    weeklyError,
    childrenError: !!childrenErrorObj,
    selectChild,
    refreshLiveData: () => fetchLiveData(selectedChildId),
    refreshWeeklyStory: () => fetchWeeklyStory(selectedChildId),
    refreshChildren,
  };
}
