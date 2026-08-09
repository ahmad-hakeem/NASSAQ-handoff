/**
 * AuthContext — Global in-flight GET request deduplication test.
 *
 * Verifies that concurrent calls to any GET endpoint (such as /system/metrics/history,
 * /system/errors, /integrations, /schools, etc.) share a single network request over the wire.
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

function mockResponse({ status = 200, data }) {
  return { data, status, statusText: 'OK', headers: {}, config: {}, request: {} };
}

describe('AuthContext — Global in-flight GET request deduplication', () => {
  let originalAdapter;

  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    originalAdapter = axios.defaults.adapter;
  });

  afterEach(() => {
    axios.defaults.adapter = originalAdapter;
    jest.restoreAllMocks();
  });

  test('concurrent api.get calls to /system/metrics/history share ONE network request', async () => {
    let callCount = 0;

    const mockAdapter = jest.fn((config) => {
      if (config.url.endsWith('/system/metrics/history')) {
        callCount++;
        return new Promise((resolve) => {
          setTimeout(() => {
            resolve(mockResponse({ data: { metrics: [1, 2, 3] } }));
          }, 50);
        });
      }
      return Promise.resolve(mockResponse({ data: {} }));
    });

    axios.defaults.adapter = mockAdapter;

    let apiInstance;
    function TestComponent() {
      const { api } = useAuth();
      apiInstance = api;
      return null;
    }

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    await waitFor(() => expect(apiInstance).toBeTruthy());

    let res1, res2, res3;
    await act(async () => {
      // Dispatch 3 concurrent calls at the same time
      const p1 = apiInstance.get('/system/metrics/history');
      const p2 = apiInstance.get('/system/metrics/history');
      const p3 = apiInstance.get('/system/metrics/history');

      [res1, res2, res3] = await Promise.all([p1, p2, p3]);
    });

    // 1. All 3 callers receive the exact same response data
    expect(res1.data).toEqual({ metrics: [1, 2, 3] });
    expect(res2.data).toEqual({ metrics: [1, 2, 3] });
    expect(res3.data).toEqual({ metrics: [1, 2, 3] });

    // 2. Exactly 1 network call was made
    const metricsCalls = mockAdapter.mock.calls.filter(([c]) => c.url.endsWith('/system/metrics/history'));
    expect(metricsCalls).toHaveLength(1);
    expect(callCount).toBe(1);
  });

  test('concurrent calls to /system/errors and /integrations deduplicate independently', async () => {
    let errorsCallCount = 0;
    let integrationsCallCount = 0;

    const mockAdapter = jest.fn((config) => {
      if (config.url.endsWith('/system/errors')) {
        errorsCallCount++;
        return new Promise((resolve) => {
          setTimeout(() => resolve(mockResponse({ data: { errors: [] } })), 40);
        });
      }
      if (config.url.endsWith('/integrations')) {
        integrationsCallCount++;
        return new Promise((resolve) => {
          setTimeout(() => resolve(mockResponse({ data: { integrations: ['zoom', 'teams'] } })), 40);
        });
      }
      return Promise.resolve(mockResponse({ data: {} }));
    });

    axios.defaults.adapter = mockAdapter;

    let apiInstance;
    function TestComponent() {
      const { api } = useAuth();
      apiInstance = api;
      return null;
    }

    render(
      <AuthProvider>
        <TestComponent />
      </AuthProvider>
    );

    await waitFor(() => expect(apiInstance).toBeTruthy());

    await act(async () => {
      await Promise.all([
        apiInstance.get('/system/errors'),
        apiInstance.get('/system/errors'),
        apiInstance.get('/integrations'),
        apiInstance.get('/integrations'),
      ]);
    });

    expect(errorsCallCount).toBe(1);
    expect(integrationsCallCount).toBe(1);
  });
});
