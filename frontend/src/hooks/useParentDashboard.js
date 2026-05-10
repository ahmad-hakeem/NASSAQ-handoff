import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useParentActiveStudent } from '../contexts/ParentActiveStudentContext';

/**
 * Task #146 — children + active selection now come from the global
 * ParentActiveStudentContext (single source of truth, mounted at App root).
 * This hook keeps the per-child live/weekly/notification fetch loops it
 * always owned, but no longer fetches the children list itself and no
 * longer holds a local `selectedChildIndex`.
 *
 * Task #150 — wires the per-child today-live + weekly-story responses into
 * the same per-(childId, endpoint) cache that powers the detail pages
 * (key: `dashboard`). Switching back to a previously-viewed child renders
 * the cached payload immediately and shows a subtle background refresh
 * chip while a fresh fetch runs. Cache is invalidated on logout/role
 * switch (handled by the context) and on `nassaq:schedule_published`
 * (added to SCHEDULE_DEPENDENT_KEYS in the context).
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
    getCachedEndpoint,
    setCachedEndpoint,
  } = useParentActiveStudent();

  const initialCached = selectedChildId
    ? getCachedEndpoint(selectedChildId, 'dashboard')
    : null;

  const [liveData, setLiveData] = useState(initialCached?.liveData ?? null);
  const [weeklyStory, setWeeklyStory] = useState(initialCached?.weeklyStory ?? null);
  const [notifications, setNotifications] = useState([]);
  const [notificationsLoading, setNotificationsLoading] = useState(true);
  const [liveLoading, setLiveLoading] = useState(false);
  const [weeklyLoading, setWeeklyLoading] = useState(false);
  const [liveError, setLiveError] = useState(false);
  const [weeklyError, setWeeklyError] = useState(false);
  // Background refresh indicator: true while we're re-fetching on top of
  // cached data (so the page can show a small chip instead of a skeleton).
  const [refreshing, setRefreshing] = useState(false);
  const timerRef = useRef(null);
  // Stale-response guard: each per-child fetch captures the *active* child
  // id at request time and discards its result if the active child has
  // since changed. Prevents older responses (rapid switches / out-of-order
  // network) from overwriting state for a different child.
  const activeChildRef = useRef(null);
  activeChildRef.current = selectedChildId;

  // Merge a partial payload into the dashboard cache for `childId` without
  // dropping whichever sibling slot (liveData / weeklyStory) was already
  // cached from a previous fetch.
  const mergeDashboardCache = useCallback((childId, patch) => {
    if (!childId) return;
    const prev = getCachedEndpoint(childId, 'dashboard') || {};
    setCachedEndpoint(childId, 'dashboard', { ...prev, ...patch });
  }, [getCachedEndpoint, setCachedEndpoint]);

  const fetchLiveData = useCallback(async (childId) => {
    if (!childId) return;
    try {
      const res = await api.get(`/parent-portal/child/${childId}/today-live`);
      if (String(activeChildRef.current) !== String(childId)) return;
      setLiveData(res.data);
      setLiveError(false);
      mergeDashboardCache(childId, { liveData: res.data });
    } catch {
      if (String(activeChildRef.current) !== String(childId)) return;
      // Only surface the error if we have nothing cached to fall back on;
      // otherwise keep showing the cached payload (background refresh
      // failed silently).
      const cached = getCachedEndpoint(childId, 'dashboard');
      if (!cached?.liveData) {
        setLiveData(null);
        setLiveError(true);
      }
    } finally {
      if (String(activeChildRef.current) === String(childId)) setLiveLoading(false);
    }
  }, [api, getCachedEndpoint, mergeDashboardCache]);

  const fetchWeeklyStory = useCallback(async (childId) => {
    if (!childId) return;
    try {
      const res = await api.get(`/parent-portal/child/${childId}/weekly-story`);
      if (String(activeChildRef.current) !== String(childId)) return;
      setWeeklyStory(res.data);
      setWeeklyError(false);
      mergeDashboardCache(childId, { weeklyStory: res.data });
    } catch {
      if (String(activeChildRef.current) !== String(childId)) return;
      const cached = getCachedEndpoint(childId, 'dashboard');
      if (!cached?.weeklyStory) {
        setWeeklyStory(null);
        setWeeklyError(true);
      }
    } finally {
      if (String(activeChildRef.current) === String(childId)) setWeeklyLoading(false);
    }
  }, [api, getCachedEndpoint, mergeDashboardCache]);

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

  // On every active-student change: hydrate from cache instantly when we
  // have it, otherwise show local skeletons. Either way kick off a fresh
  // background fetch so the cache stays warm.
  useEffect(() => {
    if (!selectedChildId) {
      setLiveData(null);
      setWeeklyStory(null);
      setLiveLoading(false);
      setWeeklyLoading(false);
      setRefreshing(false);
      return;
    }

    const cached = getCachedEndpoint(selectedChildId, 'dashboard');
    const hasLive = !!cached?.liveData;
    const hasWeekly = !!cached?.weeklyStory;

    setLiveData(cached?.liveData ?? null);
    setWeeklyStory(cached?.weeklyStory ?? null);
    setLiveError(false);
    setWeeklyError(false);
    // Show the section skeleton only on a true cold load for that slot;
    // otherwise the cached payload covers the visual gap and the chip
    // signals that fresh data is on its way.
    setLiveLoading(!hasLive);
    setWeeklyLoading(!hasWeekly);
    setRefreshing(hasLive || hasWeekly);

    let cancelled = false;
    const requestedFor = selectedChildId;
    Promise.allSettled([
      fetchLiveData(requestedFor),
      fetchWeeklyStory(requestedFor),
    ]).finally(() => {
      if (cancelled) return;
      if (String(activeChildRef.current) !== String(requestedFor)) return;
      setRefreshing(false);
    });
    return () => { cancelled = true; };
  }, [selectedChildId, getCachedEndpoint, fetchLiveData, fetchWeeklyStory]);

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
    refreshing,
    selectChild,
    refreshLiveData: () => fetchLiveData(selectedChildId),
    refreshWeeklyStory: () => fetchWeeklyStory(selectedChildId),
    refreshChildren,
  };
}
