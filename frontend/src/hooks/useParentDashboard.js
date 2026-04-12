import { useState, useEffect, useCallback, useRef } from 'react';
import { useAuth } from '../contexts/AuthContext';

export default function useParentDashboard() {
  const { api, user } = useAuth();
  const [children, setChildren] = useState([]);
  const [selectedChildIndex, setSelectedChildIndex] = useState(0);
  const [liveData, setLiveData] = useState(null);
  const [weeklyStory, setWeeklyStory] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [liveLoading, setLiveLoading] = useState(false);
  const [weeklyLoading, setWeeklyLoading] = useState(false);
  const [liveError, setLiveError] = useState(false);
  const [weeklyError, setWeeklyError] = useState(false);
  const [childrenError, setChildrenError] = useState(false);
  const timerRef = useRef(null);

  const fetchChildren = useCallback(async () => {
    setChildrenError(false);
    try {
      const res = await api.get('/parent-portal/children');
      setChildren(res.data?.children || []);
    } catch (err) {
      setChildren([]);
      setChildrenError(true);
    }
  }, [api]);

  const fetchLiveData = useCallback(async (childId) => {
    if (!childId) return;
    setLiveLoading(true);
    setLiveError(false);
    try {
      const res = await api.get(`/parent-portal/child/${childId}/today-live`);
      setLiveData(res.data);
    } catch (err) {
      setLiveData(null);
      setLiveError(true);
    } finally {
      setLiveLoading(false);
    }
  }, [api]);

  const fetchWeeklyStory = useCallback(async (childId) => {
    if (!childId) return;
    setWeeklyLoading(true);
    setWeeklyError(false);
    try {
      const res = await api.get(`/parent-portal/child/${childId}/weekly-story`);
      setWeeklyStory(res.data);
    } catch (err) {
      setWeeklyStory(null);
      setWeeklyError(true);
    } finally {
      setWeeklyLoading(false);
    }
  }, [api]);

  const fetchNotifications = useCallback(async () => {
    try {
      const res = await api.get('/parent-portal/notifications');
      setNotifications(res.data?.notifications || []);
    } catch {
      setNotifications([]);
    }
  }, [api]);

  const selectChild = useCallback((index) => {
    setSelectedChildIndex(index);
  }, []);

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      await fetchChildren();
      await fetchNotifications();
      setLoading(false);
    };
    init();
  }, [fetchChildren, fetchNotifications]);

  const selectedChild = children[selectedChildIndex];
  const selectedChildId = selectedChild?.id;

  useEffect(() => {
    if (selectedChildId) {
      fetchLiveData(selectedChildId);
      fetchWeeklyStory(selectedChildId);
    }
  }, [selectedChildId, fetchLiveData, fetchWeeklyStory]);

  useEffect(() => {
    if (!selectedChildId) return;
    timerRef.current = setInterval(() => {
      fetchLiveData(selectedChildId);
    }, 60000);
    return () => clearInterval(timerRef.current);
  }, [selectedChildId, fetchLiveData]);

  return {
    children,
    selectedChildIndex,
    selectedChild,
    selectedChildId,
    liveData,
    weeklyStory,
    notifications,
    loading,
    liveLoading,
    weeklyLoading,
    liveError,
    weeklyError,
    childrenError,
    selectChild,
    refreshLiveData: () => fetchLiveData(selectedChildId),
    refreshWeeklyStory: () => fetchWeeklyStory(selectedChildId),
    refreshChildren: fetchChildren,
  };
}
