import { useState, useEffect, useCallback, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '@/shared/contexts/AuthContext';
import hakimEngine, { SYSTEM_EVENTS, ANIMATION_LEVELS } from './HakimContextEngine';

const AI_ENABLED_PAGES = [
  '/teacher/home', '/teacher/classes', '/teacher/achievements',
  '/principal/ai-insights', '/teacher/communication', '/teacher/schedule',
  '/teacher/assessments', '/teacher/attendance', '/teacher/behavior',
  '/teacher/session/start', '/teacher/session/teach',
  '/school/dashboard', '/school/schedule', '/school/ai-insights',
  '/principal/schedule',
  '/student', '/parent', '/notifications',
];

function useHakimContext(options = {}) {
  const { autoDetect = true } = options;
  const location = useLocation();
  const { user, api } = useAuth();
  const [state, setState] = useState(hakimEngine.getState());
  const prevPathRef = useRef(null);
  const prevRoleRef = useRef(null);
  const aiFetchingRef = useRef(false);
  const aiCacheRef = useRef({});

  useEffect(() => {
    const unsub = hakimEngine.subscribe((newState) => {
      setState(newState);
    });
    return unsub;
  }, []);

  useEffect(() => {
    if (!autoDetect) return;
    const path = location.pathname;
    const userRole = user?.role || user?.user_role || 'school_principal';
    if (path === prevPathRef.current && userRole === prevRoleRef.current) return;
    prevPathRef.current = path;
    prevRoleRef.current = userRole;

    hakimEngine.detectContext(path, userRole);

    const shouldFetchAI = AI_ENABLED_PAGES.some(p => path.startsWith(p));
    if (shouldFetchAI && api && !aiFetchingRef.current) {
      const cacheKey = `${path}:${userRole}`;
      const cached = aiCacheRef.current[cacheKey];
      if (cached && Date.now() - cached.ts < 120000) {
        hakimEngine.fireEvent('ai_analysis_ready', cached.message);
        return;
      }

      aiFetchingRef.current = true;
      api.post('/hakim/contextual-message', {
        page: path,
        role: userRole,
        language: document.documentElement.lang === 'en' ? 'en' : 'ar',
      }).then(res => {
        const msg = res.data?.message;
        if (msg) {
          aiCacheRef.current[cacheKey] = { message: msg, ts: Date.now() };
          hakimEngine.fireEvent('ai_analysis_ready', msg);
        }
      }).catch(err => { if (process.env.NODE_ENV === 'development') console.warn('Hakim AI analysis failed:', err.message); }).finally(() => { aiFetchingRef.current = false; });
    }
  }, [location.pathname, user, autoDetect, api]);

  const fireEvent = useCallback((eventName, customMessage) => {
    hakimEngine.fireEvent(eventName, customMessage);
  }, []);

  const setVisible = useCallback((visible) => {
    hakimEngine.setVisibility(visible);
  }, []);

  const getIdleMessage = useCallback(() => {
    const userRole = user?.role || user?.user_role || 'school_principal';
    return hakimEngine.getIdleMessage(userRole);
  }, [user]);

  const fetchContextualMessage = useCallback(async (contextData = {}) => {
    if (!api) return null;
    try {
      const path = location.pathname;
      const userRole = user?.role || user?.user_role || 'school_principal';
      const res = await api.post('/hakim/contextual-message', {
        page: path,
        role: userRole,
        context_data: contextData,
        language: document.documentElement.lang === 'en' ? 'en' : 'ar',
      });
      const msg = res.data?.message;
      if (msg) hakimEngine.fireEvent('ai_analysis_ready', msg);
      return msg;
    } catch (e) { console.error('Error analyzing with Hakim:', e); return null; }
  }, [api, location.pathname, user]);

  return {
    ...state,
    fireEvent,
    setVisible,
    getIdleMessage,
    fetchContextualMessage,
    EVENTS: SYSTEM_EVENTS,
    ANIM: ANIMATION_LEVELS,
  };
}

export { SYSTEM_EVENTS, ANIMATION_LEVELS };
export default useHakimContext;
