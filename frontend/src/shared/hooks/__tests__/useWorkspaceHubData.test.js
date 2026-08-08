/**
 * Task #252 — Unit tests for useWorkspaceHubData aggregator hook.
 *
 * Covers:
 *   1. Successful fan-out: lifecycle + classes + per-class collaborators
 *      flatten into one list with class context, counts split active/pending.
 *   2. Disabled state (e.g. non-IT user / wrong section) issues no requests.
 *   3. Per-class collaborator failures are recorded under partialErrors and
 *      do NOT wedge the rest of the snapshot.
 *   4. refresh() re-fetches everything.
 */
import { renderHook, act, waitFor } from '@testing-library/react';
import { useWorkspaceHubData } from '../useWorkspaceHubData';

const makeApi = (impl) => ({
  get: jest.fn(impl.get || (() => Promise.resolve({ data: null }))),
  post: jest.fn(impl.post || (() => Promise.resolve({ data: {} }))),
  delete: jest.fn(impl.delete || (() => Promise.resolve({ data: {} }))),
});

describe('useWorkspaceHubData', () => {
  test('disabled: makes no requests', async () => {
    const api = makeApi({});
    const { result } = renderHook(() => useWorkspaceHubData(api, false));
    // Microtask flush
    await Promise.resolve();
    expect(api.get).not.toHaveBeenCalled();
    expect(result.current.lifecycle).toBeNull();
    expect(result.current.collaborators).toEqual([]);
  });

  test('successful fan-out: aggregates lifecycle, quota, and per-class collaborators', async () => {
    const lifecyclePayload = {
      workspace_id: 'itw_1',
      last_export_at: '2026-05-12T10:00:00+00:00',
      archived_at: null,
      pending_hard_delete: false,
      reactivation_banner: null,
      quota: {
        max_students: 200,
        current_students: 12,
        max_classes: null,
        current_classes: 2,
        max_imports_per_day: 5,
        imports_today: 1,
        max_lesson_plans_per_day: 20,
        lesson_plans_today: 3,
      },
    };
    const classes = [
      { id: 'c1', name_ar: 'الفصل ١' },
      { id: 'c2', name_ar: 'الفصل ٢' },
    ];
    const api = makeApi({
      get: jest.fn((path, opts) => {
        if (path === '/independent-teacher/workspace/lifecycle') {
          return Promise.resolve({ data: lifecyclePayload });
        }
        if (path === '/classes') {
          return Promise.resolve({ data: classes });
        }
        if (path === '/independent-teacher/workspace-collaborators') {
          const cid = opts?.params?.class_id;
          if (cid === 'c1') {
            return Promise.resolve({
              data: {
                items: [
                  { id: 'co1', collaborator_email: 'a@x.com', status: 'accepted' },
                  { id: 'co2', collaborator_email: 'b@x.com', status: 'pending' },
                ],
              },
            });
          }
          if (cid === 'c2') {
            return Promise.resolve({
              data: { items: [{ id: 'co3', collaborator_email: 'c@x.com', status: 'pending' }] },
            });
          }
        }
        return Promise.resolve({ data: null });
      }),
    });

    const { result } = renderHook(() => useWorkspaceHubData(api, true));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.lifecycle).toEqual(lifecyclePayload);
    expect(result.current.quota).toEqual(lifecyclePayload.quota);
    expect(result.current.classes).toHaveLength(2);
    expect(result.current.collaborators).toHaveLength(3);
    // class context flattened onto each row
    expect(result.current.collaborators[0]).toMatchObject({
      id: 'co1',
      class_id: 'c1',
      class_name: 'الفصل ١',
    });
    expect(result.current.counts).toEqual({ active: 1, pending: 2, total: 3 });
    expect(result.current.partialErrors).toEqual([]);
    expect(result.current.error).toBeNull();
  });

  test('partial failure: one class collab fetch fails — others survive, partialErrors records it', async () => {
    const api = makeApi({
      get: jest.fn((path, opts) => {
        if (path === '/independent-teacher/workspace/lifecycle') {
          return Promise.resolve({ data: { workspace_id: 'itw_1', quota: null } });
        }
        if (path === '/classes') {
          return Promise.resolve({ data: [{ id: 'c1', name_ar: 'A' }, { id: 'c2', name_ar: 'B' }] });
        }
        if (path === '/independent-teacher/workspace-collaborators') {
          const cid = opts?.params?.class_id;
          if (cid === 'c1') return Promise.reject(new Error('boom'));
          return Promise.resolve({
            data: { items: [{ id: 'ok1', collaborator_email: 'ok@x.com', status: 'accepted' }] },
          });
        }
        return Promise.resolve({ data: null });
      }),
    });

    const { result } = renderHook(() => useWorkspaceHubData(api, true));
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.collaborators).toHaveLength(1);
    expect(result.current.collaborators[0].id).toBe('ok1');
    expect(result.current.partialErrors).toContain('collab:c1');
    // lifecycle still loaded → no top-level error
    expect(result.current.error).toBeNull();
  });

  test('refresh() re-fetches lifecycle + classes + collaborators', async () => {
    const api = makeApi({
      get: jest.fn(() => Promise.resolve({ data: { items: [], quota: null } })),
    });
    const { result } = renderHook(() => useWorkspaceHubData(api, true));
    await waitFor(() => expect(result.current.loading).toBe(false));
    const initialCalls = api.get.mock.calls.length;

    await act(async () => {
      await result.current.refresh();
    });
    expect(api.get.mock.calls.length).toBeGreaterThan(initialCalls);
  });

  test('lifecycle fetch failure surfaces error="lifecycle"', async () => {
    const api = makeApi({
      get: jest.fn((path) => {
        if (path === '/independent-teacher/workspace/lifecycle') {
          return Promise.reject(new Error('502'));
        }
        return Promise.resolve({ data: [] });
      }),
    });
    const { result } = renderHook(() => useWorkspaceHubData(api, true));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe('lifecycle');
    expect(result.current.partialErrors).toContain('lifecycle');
  });
});
