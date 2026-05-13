/**
 * Task #252 — Aggregator hook for the Independent-Teacher
 * "إعدادات المساحة" (Workspace settings hub) on AccountSettingsPage.
 *
 * Fans out to existing IT endpoints — no new backend routes:
 *   - GET /independent-teacher/workspace/lifecycle  (now embeds quota)
 *   - GET /classes
 *   - GET /independent-teacher/workspace-collaborators?class_id=...  (per class)
 *
 * Returns a unified snapshot the hub renders: lifecycle row, quota
 * progress, and a flattened collaborators list (with class label) so the
 * card can render active + pending in one block. Per-class collaborator
 * fetches are isolated via Promise.allSettled so one failing class never
 * wedges the whole hub. Refresh is exposed for post-action re-fetch.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';

const _safe = async (promise) => {
  try {
    return await promise;
  } catch (err) {
    return { __error: err };
  }
};

export function useWorkspaceHubData(api, enabled) {
  const [lifecycle, setLifecycle] = useState(null);
  const [quota, setQuota] = useState(null);
  const [classes, setClasses] = useState([]);
  const [collaborators, setCollaborators] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [partialErrors, setPartialErrors] = useState([]);

  const fetchAll = useCallback(async () => {
    if (!api || !enabled) return;
    setLoading(true);
    setError(null);
    setPartialErrors([]);
    const [lcRes, clsRes] = await Promise.all([
      _safe(api.get('/independent-teacher/workspace/lifecycle')),
      _safe(api.get('/classes')),
    ]);

    const partial = [];
    let nextLifecycle = null;
    let nextQuota = null;
    if (lcRes && !lcRes.__error) {
      nextLifecycle = lcRes.data || null;
      nextQuota = (lcRes.data && lcRes.data.quota) || null;
    } else {
      partial.push('lifecycle');
    }

    let classList = [];
    if (clsRes && !clsRes.__error) {
      const data = clsRes.data;
      classList = Array.isArray(data) ? data : (data?.items || data?.classes || []);
    } else {
      partial.push('classes');
    }

    // Per-class collaborator fan-out. One failing class is recorded under
    // partialErrors but never throws — the hub stays usable.
    const collabFetches = classList.map((cls) =>
      _safe(
        api.get('/independent-teacher/workspace-collaborators', {
          params: { class_id: cls.id },
        }),
      ).then((res) => ({ cls, res })),
    );
    const collabResults = await Promise.all(collabFetches);
    const flat = [];
    for (const { cls, res } of collabResults) {
      if (res.__error) {
        partial.push(`collab:${cls.id}`);
        continue;
      }
      const items = res.data?.items || [];
      for (const it of items) {
        flat.push({
          ...it,
          class_id: cls.id,
          class_name: cls.name_ar || cls.name || cls.name_en || cls.id,
        });
      }
    }

    setLifecycle(nextLifecycle);
    setQuota(nextQuota);
    setClasses(classList);
    setCollaborators(flat);
    setPartialErrors(partial);
    if (!nextLifecycle && partial.includes('lifecycle')) {
      setError('lifecycle');
    }
    setLoading(false);
  }, [api, enabled]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const counts = useMemo(() => {
    const active = collaborators.filter(
      (c) => (c.status || '').toLowerCase() === 'accepted',
    ).length;
    const pending = collaborators.filter(
      (c) => (c.status || '').toLowerCase() === 'pending',
    ).length;
    return { active, pending, total: collaborators.length };
  }, [collaborators]);

  return {
    lifecycle,
    quota,
    classes,
    collaborators,
    counts,
    loading,
    error,
    partialErrors,
    refresh: fetchAll,
  };
}

export default useWorkspaceHubData;
