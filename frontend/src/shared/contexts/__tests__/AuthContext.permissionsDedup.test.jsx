/**
 * Frontend network audit — /auth/me/permissions request deduplication.
 *
 * Production traces show /auth/me/permissions fired TWICE back-to-back on a
 * single page load: Sidebar's mount effect and a page/route-guard mount
 * effect both call AuthContext.fetchPermissions in the same render pass.
 * The old in-flight guard read `permissionsLoading` React state from a
 * stale closure, so both callers passed the check and both hit the
 * network — and the second caller was handed `null` instead of data
 * (the "permission-gated tabs vanish" failure mode).
 *
 * Contract pinned here:
 *   1. Concurrent fetchPermissions() callers produce ONE network request.
 *   2. Every concurrent caller receives the real permissions payload.
 *   3. After resolution, later callers get the cached value (no refetch).
 *   4. force:true still bypasses the cache and refetches.
 *   5. A force refresh DURING an in-flight fetch discards the stale
 *      completion — it must not overwrite the fresh cache nor clear the
 *      new request's in-flight slot.
 *   6. An authenticated-identity change (role switch / different user)
 *      invalidates the cache; a stale in-flight completion from the old
 *      identity cannot populate it.
 *   7. Failures are not cached — the next caller retries.
 *   8. A bearer-token transition (updateToken role switch) invalidates the
 *      cache SYNCHRONOUSLY — a caller running after the new token is
 *      published but BEFORE /auth/me resolves must dispatch a new request,
 *      never be served the old bearer's cache.
 */
import React from 'react';
import axios from 'axios';
import { act, render, waitFor } from '@testing-library/react';

jest.mock('sonner', () => ({
  toast: { error: jest.fn(), success: jest.fn() },
}));
jest.mock('@/locales/ar.json', () => ({}), { virtual: true });
jest.mock('@/locales/en.json', () => ({}), { virtual: true });
jest.mock('@/shared/services/apiClient', () => ({
  createApiService: () => ({}),
}));

import { AuthProvider, useAuth } from '../AuthContext';

function mockResponse({ status, data }) {
  return { data, status, statusText: '', headers: {}, config: {}, request: {} };
}

const PERMS = { permissions: ['can_view_students', 'can_manage_classes'] };

function mountAndCapture() {
  const captured = { api: null, fetchPermissions: null, refreshUser: null, updateToken: null };

  function Capture() {
    const { api, fetchPermissions, refreshUser, updateToken } = useAuth();
    // Assign during render so the test always holds the LATEST callback
    // identity (fetchPermissions is recreated when the cache state changes).
    captured.api = api;
    captured.fetchPermissions = fetchPermissions;
    captured.refreshUser = refreshUser;
    captured.updateToken = updateToken;
    return null;
  }

  let utils;
  act(() => {
    utils = render(
      <AuthProvider>
        <Capture />
      </AuthProvider>,
    );
  });
  return { ...utils, captured };
}

describe('fetchPermissions request deduplication', () => {
  beforeEach(() => {
    localStorage.setItem('nassaq_token', 'teacher-access-token');
  });

  afterEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    jest.clearAllMocks();
  });

  test('concurrent callers share ONE network request and BOTH receive the data', async () => {
    const { captured, unmount } = mountAndCapture();
    await waitFor(() => expect(captured.api).not.toBeNull());

    let permCalls = 0;
    captured.api.defaults.adapter = (config) => {
      if ((config.url || '').includes('/auth/me/permissions')) {
        permCalls += 1;
        // Resolve asynchronously so the two callers genuinely overlap.
        return new Promise((resolve) => {
          setTimeout(() => resolve(mockResponse({ status: 200, data: PERMS })), 30);
        });
      }
      return Promise.resolve(mockResponse({ status: 200, data: {} }));
    };
    // Let the auth bootstrap settle before measuring.
    await act(async () => {});

    let a;
    let b;
    await act(async () => {
      [a, b] = await Promise.all([
        captured.fetchPermissions(),
        captured.fetchPermissions(),
      ]);
    });

    expect(permCalls).toBe(1);
    expect(a).toEqual(PERMS);
    // The second caller must get real data, never null (null here is what
    // makes permission-gated tabs vanish on the losing consumer).
    expect(b).toEqual(PERMS);

    unmount();
  });

  test('later callers hit the cache; force:true refetches', async () => {
    const { captured, unmount } = mountAndCapture();
    await waitFor(() => expect(captured.api).not.toBeNull());

    let permCalls = 0;
    captured.api.defaults.adapter = (config) => {
      if ((config.url || '').includes('/auth/me/permissions')) {
        permCalls += 1;
        return Promise.resolve(mockResponse({ status: 200, data: PERMS }));
      }
      return Promise.resolve(mockResponse({ status: 200, data: {} }));
    };
    await act(async () => {});

    await act(async () => {
      await captured.fetchPermissions();
    });
    expect(permCalls).toBe(1);

    // Cached — no new network call.
    let cached;
    await act(async () => {
      cached = await captured.fetchPermissions();
    });
    expect(permCalls).toBe(1);
    expect(cached).toEqual(PERMS);

    // force bypasses the cache (tenant change after IT bootstrap).
    let forced;
    await act(async () => {
      forced = await captured.fetchPermissions({ force: true });
    });
    expect(permCalls).toBe(2);
    expect(forced).toEqual(PERMS);

    unmount();
  });

  test('force during an in-flight fetch discards the stale completion', async () => {
    const { captured, unmount } = mountAndCapture();
    await waitFor(() => expect(captured.api).not.toBeNull());

    // Deferred adapter: each permissions request parks until the test
    // resolves it explicitly, so completion ORDER is fully controlled.
    const pending = [];
    captured.api.defaults.adapter = (config) => {
      if ((config.url || '').includes('/auth/me/permissions')) {
        return new Promise((resolve) => {
          pending.push((data) => resolve(mockResponse({ status: 200, data })));
        });
      }
      return Promise.resolve(mockResponse({ status: 200, data: {} }));
    };
    await act(async () => {});

    let firstResult;
    let first;
    act(() => {
      first = captured.fetchPermissions();
      first.then((r) => { firstResult = r; });
    });
    await waitFor(() => expect(pending.length).toBe(1));

    // Force refresh while the first request is still in flight
    // (the IT-bootstrap tenant-change scenario).
    let second;
    act(() => {
      second = captured.fetchPermissions({ force: true });
    });
    await waitFor(() => expect(pending.length).toBe(2));

    // The OLD request completes LAST-WRITER style with stale data…
    await act(async () => {
      pending[0]({ permissions: ['STALE_OLD_TENANT'] });
      await first;
    });
    // …then the new one completes with fresh data.
    let fresh;
    await act(async () => {
      pending[1]({ permissions: ['FRESH'] });
      fresh = await second;
    });

    // Superseded completion is discarded, not handed to its caller.
    expect(firstResult).toBeNull();
    expect(fresh).toEqual({ permissions: ['FRESH'] });

    // Cache holds FRESH — no stale overwrite, and no third request.
    let cached;
    await act(async () => {
      cached = await captured.fetchPermissions();
    });
    expect(cached).toEqual({ permissions: ['FRESH'] });
    expect(pending.length).toBe(2);

    unmount();
  });

  test('identity change (role switch) invalidates the cache and discards stale in-flight data', async () => {
    const { captured, unmount } = mountAndCapture();
    await waitFor(() => expect(captured.api).not.toBeNull());

    const USER_A = { id: 'u-1', role: 'teacher', tenant_id: 't-1', email: 'a@x' };
    const USER_B = { id: 'u-1', role: 'school_admin', tenant_id: 't-1', email: 'a@x' };
    let me = USER_A;
    let permCalls = 0;
    const pending = [];
    captured.api.defaults.adapter = (config) => {
      const url = config.url || '';
      if (url.includes('/auth/me/permissions')) {
        permCalls += 1;
        return new Promise((resolve) => {
          pending.push((data) => resolve(mockResponse({ status: 200, data })));
        });
      }
      if (url.includes('/auth/me')) {
        return Promise.resolve(mockResponse({ status: 200, data: me }));
      }
      return Promise.resolve(mockResponse({ status: 200, data: {} }));
    };

    // Establish identity A (anon → A must NOT invalidate).
    await act(async () => {
      await captured.refreshUser();
    });

    // Start a permissions fetch under identity A and leave it in flight.
    let inFlight;
    act(() => {
      inFlight = captured.fetchPermissions();
    });
    await waitFor(() => expect(pending.length).toBe(1));

    // Role switch: identity A → B while the old fetch is still pending.
    me = USER_B;
    await act(async () => {
      await captured.refreshUser();
    });

    // Old-identity completion arrives late — must be discarded.
    let staleResult;
    await act(async () => {
      pending[0]({ permissions: ['TEACHER_ONLY'] });
      staleResult = await inFlight;
    });
    expect(staleResult).toBeNull();

    // Next caller triggers a NEW request for the new identity.
    let freshPromise;
    act(() => {
      freshPromise = captured.fetchPermissions();
    });
    await waitFor(() => expect(pending.length).toBe(2));
    let freshResult;
    await act(async () => {
      pending[1]({ permissions: ['ADMIN'] });
      freshResult = await freshPromise;
    });
    expect(freshResult).toEqual({ permissions: ['ADMIN'] });
    expect(permCalls).toBe(2);

    unmount();
  });

  test('token transition (updateToken) invalidates synchronously — no stale cache before /auth/me lands', async () => {
    // updateToken re-fetches /auth/me through the raw axios module (not the
    // context api instance); park it forever so the test exercises exactly
    // the race window: new bearer published, `user` still the old identity.
    const axiosGetSpy = jest
      .spyOn(axios, 'get')
      .mockImplementation(() => new Promise(() => {}));

    const { captured, unmount } = mountAndCapture();
    await waitFor(() => expect(captured.api).not.toBeNull());

    let permCalls = 0;
    const payloads = [
      { permissions: ['TEACHER_ONLY'] },
      { permissions: ['ADMIN'] },
    ];
    captured.api.defaults.adapter = (config) => {
      if ((config.url || '').includes('/auth/me/permissions')) {
        const data = payloads[Math.min(permCalls, payloads.length - 1)];
        permCalls += 1;
        return Promise.resolve(mockResponse({ status: 200, data }));
      }
      return Promise.resolve(mockResponse({ status: 200, data: {} }));
    };
    await act(async () => {});

    // Seed the cache under bearer A.
    let seeded;
    await act(async () => {
      seeded = await captured.fetchPermissions();
    });
    expect(seeded).toEqual({ permissions: ['TEACHER_ONLY'] });
    expect(permCalls).toBe(1);

    // Real token-change path: publishes the new bearer synchronously
    // (localStorage + setToken) while its /auth/me hangs — the user
    // identity effect has nothing to observe yet.
    act(() => {
      captured.updateToken('admin-access-token'); // deliberately not awaited
    });
    expect(localStorage.getItem('nassaq_token')).toBe('admin-access-token');

    // A caller in the race window must get a FRESH fetch, not A's cache.
    let raced;
    await act(async () => {
      raced = await captured.fetchPermissions();
    });
    expect(permCalls).toBe(2);
    expect(raced).toEqual({ permissions: ['ADMIN'] });

    axiosGetSpy.mockRestore();
    unmount();
  });

  test('a failed fetch is not cached — the next caller retries', async () => {
    const { captured, unmount } = mountAndCapture();
    await waitFor(() => expect(captured.api).not.toBeNull());

    let permCalls = 0;
    captured.api.defaults.adapter = (config) => {
      if ((config.url || '').includes('/auth/me/permissions')) {
        permCalls += 1;
        if (permCalls === 1) {
          return Promise.reject(Object.assign(new Error('boom'), {
            isAxiosError: true,
            config,
            response: mockResponse({ status: 500, data: {} }),
          }));
        }
        return Promise.resolve(mockResponse({ status: 200, data: PERMS }));
      }
      return Promise.resolve(mockResponse({ status: 200, data: {} }));
    };
    await act(async () => {});

    let r1;
    await act(async () => {
      r1 = await captured.fetchPermissions();
    });
    expect(r1).toBeNull();
    expect(permCalls).toBe(1);

    let r2;
    await act(async () => {
      r2 = await captured.fetchPermissions();
    });
    expect(r2).toEqual(PERMS);
    expect(permCalls).toBe(2);

    unmount();
  });
});
