/**
 * ParentActiveStudentContext — Task #146
 *
 * Single global source of truth for the Parent Portal's "active student".
 *
 * Owns:
 *   - linkedChildren    : list returned by GET /parent-portal/children
 *   - activeChildId     : string id of the currently selected child
 *   - activeChild       : the resolved object from linkedChildren
 *   - setActiveChildId  : in-memory switcher (no localStorage). Validates the
 *                         id against `linkedChildren` once loaded; rejects
 *                         unknown ids and surfaces a clean Arabic alert.
 *
 * Initialization order (guaranteed at first render after children load):
 *   URL deep link  →  first linked child  →  empty state
 *
 * The provider itself reads the current location so the deep link wins on
 * first load — page-level sync hooks can never race the default selection.
 *
 * Mounted once, inside <BrowserRouter>, at the App root.
 *
 * Backend IDOR is enforced by `_verify_parent_access` on every
 * /parent-portal/child/{child_id}/... endpoint — this context never trusts
 * the client for authorization.
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
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from './AuthContext';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';

const ParentActiveStudentCtx = createContext(null);

const EMPTY_VALUE = {
  linkedChildren: [],
  activeChildId: null,
  activeChild: null,
  setActiveChildId: () => {},
  isLoading: false,
  hasLoadedChildren: false,
  error: null,
  refetch: () => {},
};

const LEGACY_CHILD_RE = /^\/parent\/child\/([^/]+)(?:\/.*)?$/;

/**
 * Pull a candidate child id from the current URL:
 *   - `/parent/child/:childId/...`  → path param
 *   - `/parent/...?child=<id>`      → search param
 * Returns the raw string or null. Membership is validated separately
 * against the parent's linked-children list.
 */
const readChildIdFromLocation = (location) => {
  if (!location) return null;
  const m = location.pathname?.match(LEGACY_CHILD_RE);
  if (m && m[1]) return m[1];
  try {
    const params = new URLSearchParams(location.search || '');
    const c = params.get('child');
    if (c) return c;
  } catch {
    /* ignore malformed query strings */
  }
  return null;
};

export const ParentActiveStudentProvider = ({ children }) => {
  const { api, user } = useAuth();
  const location = useLocation();
  const { nassaqError } = useNassaqAlert();
  const isParent = user?.role === 'parent';

  const [linkedChildren, setLinkedChildren] = useState([]);
  const [activeChildId, setActiveChildIdState] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [hasLoadedChildren, setHasLoadedChildren] = useState(false);
  const [error, setError] = useState(null);
  const fetchedForUserRef = useRef(null);
  // Snapshot the URL child id at the moment the provider mounts / a parent
  // logs in, so we can use it as the seed once children resolve. We do NOT
  // re-read it on every navigation — page-level hooks handle subsequent
  // route changes.
  const initialDeepLinkRef = useRef(null);
  const warnedInvalidRef = useRef(new Set());

  const fetchChildren = useCallback(async () => {
    if (!isParent) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.get('/parent-portal/children');
      const list = Array.isArray(res.data?.children) ? res.data.children : [];
      setLinkedChildren(list);
      // Initialization order: keep current selection if still valid →
      // honour the URL deep link (if linked) → first linked child → null.
      setActiveChildIdState((prev) => {
        if (prev && list.some((c) => String(c.id) === String(prev))) return prev;
        const seed = initialDeepLinkRef.current;
        if (seed && list.some((c) => String(c.id) === String(seed))) {
          return String(seed);
        }
        return list[0]?.id != null ? String(list[0].id) : null;
      });
    } catch (e) {
      setLinkedChildren([]);
      setActiveChildIdState(null);
      setError(e);
    } finally {
      setHasLoadedChildren(true);
      setIsLoading(false);
    }
  }, [api, isParent]);

  // Capture the initial deep-link id once per logged-in parent, then fetch.
  useEffect(() => {
    if (!isParent) {
      fetchedForUserRef.current = null;
      initialDeepLinkRef.current = null;
      warnedInvalidRef.current = new Set();
      setLinkedChildren([]);
      setActiveChildIdState(null);
      setHasLoadedChildren(false);
      setError(null);
      return;
    }
    if (fetchedForUserRef.current === user?.id) return;
    fetchedForUserRef.current = user?.id;
    initialDeepLinkRef.current = readChildIdFromLocation(location);
    fetchChildren();
    // We intentionally only re-run when the parent changes; subsequent URL
    // changes are handled by page-level useSyncRouteChildToActive hooks.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isParent, user?.id, fetchChildren]);

  /**
   * setActiveChildId — only accepts ids belonging to the parent's linked
   * children. Once `linkedChildren` is loaded, an unknown id is ignored and
   * surfaces a single Arabic alert (no spam) so we never fetch student
   * endpoints with an id the parent isn't actually linked to.
   */
  const setActiveChildId = useCallback((id) => {
    if (id == null) return;
    const sid = String(id);
    setActiveChildIdState((prev) => {
      // Children list not yet loaded — accept tentatively; the post-fetch
      // initializer re-validates against the resolved list (so a deep link
      // to an unauthorized id never survives the fetch).
      if (!hasLoadedChildren) {
        return prev === sid ? prev : sid;
      }
      const exists = linkedChildren.some((c) => String(c.id) === sid);
      if (!exists) {
        // Loaded list does NOT contain this id — reject it cleanly.
        // We never silently auto-heal to "first linked child" here, so the
        // failed access attempt cannot masquerade as a successful switch.
        if (!warnedInvalidRef.current.has(sid)) {
          warnedInvalidRef.current.add(sid);
          try {
            nassaqError('لا يمكنك الوصول إلى هذا الطالب');
          } catch {
            /* alert provider missing — degrade silently */
          }
        }
        // Preserve any previously-valid selection so the rest of the portal
        // stays usable; otherwise stay null (no child-scoped fetch fires).
        if (prev && linkedChildren.some((c) => String(c.id) === String(prev))) {
          return prev;
        }
        return null;
      }
      return prev === sid ? prev : sid;
    });
  }, [linkedChildren, hasLoadedChildren, nassaqError]);

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
      hasLoadedChildren,
      error,
      refetch: fetchChildren,
    }),
    [linkedChildren, activeChildId, activeChild, setActiveChildId, isLoading, hasLoadedChildren, error, fetchChildren],
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
 * context. Used by legacy detail routes (`/parent/child/:childId/...`) for
 * client-side navigation between children. Provider ownership of the initial
 * deep link means this hook is a no-op on first paint and only matters for
 * subsequent in-app navigations. The provider itself rejects unknown ids.
 *
 * Additionally canonicalizes the URL on invalid deep links: once the linked
 * children list has loaded, if the route's `:childId` is not authorized for
 * this parent we replace the URL with `/parent/children` so the address bar
 * never lingers on an unauthorized id (URL and rendered child stay in sync).
 */
export const useSyncRouteChildToActive = (childIdFromRoute) => {
  const { setActiveChildId, linkedChildren, hasLoadedChildren } = useParentActiveStudent();
  const navigate = useNavigate();
  useEffect(() => {
    if (childIdFromRoute) setActiveChildId(childIdFromRoute);
  }, [childIdFromRoute, setActiveChildId]);
  useEffect(() => {
    if (!childIdFromRoute) return;
    if (!hasLoadedChildren) return;
    const ok = linkedChildren.some((c) => String(c.id) === String(childIdFromRoute));
    if (!ok) {
      // Replace (don't push) so back-button won't loop into the bad URL.
      navigate('/parent/children', { replace: true });
    }
  }, [childIdFromRoute, hasLoadedChildren, linkedChildren, navigate]);
};

export default ParentActiveStudentCtx;
