/**
 * ParentActiveStudentContext — Task #146
 *
 * Single global source of truth for the Parent Portal's "active student".
 *
 * Owns:
 *   - linkedChildren    : list returned by GET /parent-portal/children
 *   - activeChildId     : string id of the currently selected child
 *   - activeChild       : the resolved object from linkedChildren
 *   - setActiveChildId  : in-memory switcher (no localStorage)
 *
 * Initialization order:
 *   route/?child= →  first linked child  →  empty state
 *
 * Mounted once at the App root so any parent page/component can read it
 * via `useParentActiveStudent()`. The provider is a no-op for non-parent
 * users (no fetch, empty state).
 *
 * Backend IDOR is enforced by `_verify_parent_access` on every
 * /parent-portal/child/{child_id}/... endpoint — this context never
 * trusts the client for authorization.
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useAuth } from './AuthContext';

const ParentActiveStudentCtx = createContext(null);

const EMPTY_VALUE = {
  linkedChildren: [],
  activeChildId: null,
  activeChild: null,
  setActiveChildId: () => {},
  isLoading: false,
  error: null,
  refetch: () => {},
};

export const ParentActiveStudentProvider = ({ children }) => {
  const { api, user } = useAuth();
  const isParent = user?.role === 'parent';

  const [linkedChildren, setLinkedChildren] = useState([]);
  const [activeChildId, setActiveChildIdState] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const fetchedForUserRef = useRef(null);

  const fetchChildren = useCallback(async () => {
    if (!isParent) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.get('/parent-portal/children');
      const list = Array.isArray(res.data?.children) ? res.data.children : [];
      setLinkedChildren(list);
      // Initialization order: keep current selection if still valid,
      // otherwise fall back to the first linked child, otherwise null.
      setActiveChildIdState((prev) => {
        if (prev && list.some((c) => String(c.id) === String(prev))) return prev;
        return list[0]?.id != null ? String(list[0].id) : null;
      });
    } catch (e) {
      setLinkedChildren([]);
      setActiveChildIdState(null);
      setError(e);
    } finally {
      setIsLoading(false);
    }
  }, [api, isParent]);

  // Fetch once per logged-in parent. Reset when user changes/logs out.
  useEffect(() => {
    if (!isParent) {
      fetchedForUserRef.current = null;
      setLinkedChildren([]);
      setActiveChildIdState(null);
      setError(null);
      return;
    }
    if (fetchedForUserRef.current === user?.id) return;
    fetchedForUserRef.current = user?.id;
    fetchChildren();
  }, [isParent, user?.id, fetchChildren]);

  const setActiveChildId = useCallback((id) => {
    if (id == null) return;
    const sid = String(id);
    setActiveChildIdState((prev) => (prev === sid ? prev : sid));
  }, []);

  const activeChild = useMemo(
    () => linkedChildren.find((c) => String(c.id) === String(activeChildId)) || null,
    [linkedChildren, activeChildId],
  );

  const value = useMemo(
    () => ({
      linkedChildren,
      activeChildId: activeChildId ? String(activeChildId) : null,
      activeChild,
      setActiveChildId,
      isLoading,
      error,
      refetch: fetchChildren,
    }),
    [linkedChildren, activeChildId, activeChild, setActiveChildId, isLoading, error, fetchChildren],
  );

  return (
    <ParentActiveStudentCtx.Provider value={value}>
      {children}
    </ParentActiveStudentCtx.Provider>
  );
};

export const useParentActiveStudent = () => {
  const ctx = useContext(ParentActiveStudentCtx);
  return ctx || EMPTY_VALUE;
};

/**
 * One-way sync: push a `:childId` route param into the global active-student
 * context. Used by legacy detail routes (`/parent/child/:childId/...`) so that
 * landing on a deep link selects the matching child globally without ever
 * writing back to the URL.
 */
export const useSyncRouteChildToActive = (childIdFromRoute) => {
  const { setActiveChildId } = useParentActiveStudent();
  useEffect(() => {
    if (childIdFromRoute) setActiveChildId(childIdFromRoute);
  }, [childIdFromRoute, setActiveChildId]);
};

export default ParentActiveStudentCtx;
