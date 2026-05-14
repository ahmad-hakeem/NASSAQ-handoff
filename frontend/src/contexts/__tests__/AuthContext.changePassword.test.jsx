/**
 * Task #338 — real interceptor + AccountSettings behaviour for the
 * change-password MFA step-up envelope.
 *
 * These tests mount the actual <AuthProvider/> so the production axios
 * response interceptor is wired up, then drive the wrapped axios
 * instance via a mock adapter. They pin three contracts the bug
 * reported:
 *
 *   1. A 403 + canonical step-up envelope on /auth/change-password
 *      invokes the registered MFA step-up handler and replays the
 *      request with the new access token — and never redirects to
 *      /login.
 *   2. If the user cancels / fails the step-up modal AND the replayed
 *      request still returns the canonical envelope (401 or 403), the
 *      defense-in-depth branch rejects to the caller. The legacy
 *      bare-401 fallback (attemptTokenRefresh + window.location='/login')
 *      MUST NOT fire.
 *   3. A 200 success on /auth/change-password resolves to the caller
 *      without invoking the step-up handler and without navigating.
 *   4. A 400 + Arabic detail flows through to the caller's catch
 *      without invoking the step-up handler and without navigating.
 */
import React, { useEffect } from 'react';
import { act, render, waitFor } from '@testing-library/react';

// --- module mocks ---------------------------------------------------------

jest.mock('sonner', () => ({
  toast: {
    error: jest.fn(),
    success: jest.fn(),
  },
}));

// Stub locale dictionaries to avoid pulling the full JSON tree into the
// jest module graph.
jest.mock('../../locales/ar.json', () => ({}), { virtual: true });
jest.mock('../../locales/en.json', () => ({}), { virtual: true });

// The createApiService helper is invoked by AuthProvider but its return
// value is unused for these tests — stub to keep imports light.
jest.mock('../../services/apiClient', () => ({
  createApiService: () => ({}),
}));

// --- imports under test ---------------------------------------------------

import { AuthProvider, useAuth } from '../AuthContext';
import { registerMfaStepUpHandler } from '../../services/mfaStepUpBridge';

// --- helpers --------------------------------------------------------------

function mockResponse({ status, data }) {
  return {
    data,
    status,
    statusText: '',
    headers: {},
    config: {},
    request: {},
  };
}

/**
 * Mount AuthProvider and capture its wrapped axios instance via a child
 * that calls useAuth(). We replace the instance's adapter so requests
 * never hit the network and we can drive arbitrary status codes through
 * the production response interceptor.
 */
function mountAndCaptureApi() {
  const captured = { api: null };

  function Capture() {
    const { api } = useAuth();
    useEffect(() => {
      captured.api = api;
    }, [api]);
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

describe('Task #338 — /auth/change-password MFA step-up interceptor', () => {
  let originalLocation;

  beforeEach(() => {
    // Seed a token so the request interceptor attaches Authorization
    // and the bare-401 branch (which checks `hasStoredToken`) would be
    // a candidate for the 401 fallback if our short-circuit is missing.
    localStorage.setItem('nassaq_token', 'principal-access-token');
    // Stub window.location so we can detect any /login redirect.
    originalLocation = window.location;
    delete window.location;
    window.location = {
      ...originalLocation,
      href: 'http://localhost/account-settings',
      pathname: '/account-settings',
      assign: jest.fn(),
    };
  });

  afterEach(() => {
    window.location = originalLocation;
    localStorage.clear();
    sessionStorage.clear();
    jest.clearAllMocks();
  });

  test('403 + step-up envelope opens the step-up handler and replays with the new token (no /login)', async () => {
    const { captured, unmount } = mountAndCaptureApi();
    await waitFor(() => expect(captured.api).not.toBeNull());

    // Mock step-up handler returns a fresh access token. The real
    // MfaStepUpDialog persists the new token to localStorage on success
    // (so the request interceptor picks it up on subsequent requests);
    // mirror that side-effect here.
    const handler = jest.fn().mockImplementation(async () => {
      localStorage.setItem('nassaq_token', 'fresh-access-token');
      return 'fresh-access-token';
    });
    const unregister = registerMfaStepUpHandler(handler);

    // First call: 403 step-up envelope. Replay: 200 success.
    let callCount = 0;
    captured.api.defaults.adapter = (config) => {
      callCount += 1;
      if (callCount === 1) {
        return Promise.reject({
          config,
          response: mockResponse({
            status: 403,
            data: {
              detail: {
                code: 'MFA_STEPUP_REQUIRED',
                message: 'يلزم التحقق المسبق',
                challenge_endpoint: '/api/auth/mfa/stepup/start',
                max_age_seconds: 300,
              },
            },
          }),
          message: 'Request failed with status code 403',
          isAxiosError: true,
        });
      }
      // Replay must carry the new bearer.
      expect(config.headers.Authorization).toBe('Bearer fresh-access-token');
      return Promise.resolve(
        mockResponse({ status: 200, data: { message: 'تم تغيير كلمة المرور بنجاح' } }),
      );
    };

    const result = await captured.api.post('/auth/change-password', {
      current_password: 'Old@1234!',
      new_password: 'New@12345!',
    });

    expect(handler).toHaveBeenCalledTimes(1);
    expect(callCount).toBe(2);
    expect(result.status).toBe(200);
    expect(window.location.href).toBe('http://localhost/account-settings');

    unregister();
    unmount();
  });

  test('cancelled step-up rejects to the caller and does NOT redirect to /login', async () => {
    const { captured, unmount } = mountAndCaptureApi();
    await waitFor(() => expect(captured.api).not.toBeNull());

    // Step-up handler simulates the user cancelling the modal.
    const handler = jest.fn().mockRejectedValue(new Error('MFA_STEPUP_CANCELLED'));
    const unregister = registerMfaStepUpHandler(handler);

    captured.api.defaults.adapter = (config) =>
      Promise.reject({
        config,
        response: mockResponse({
          status: 403,
          data: {
            detail: {
              code: 'MFA_STEPUP_REQUIRED',
              message: 'يلزم التحقق المسبق',
            },
          },
        }),
        message: 'Request failed with status code 403',
        isAxiosError: true,
      });

    let caught = null;
    try {
      await captured.api.post('/auth/change-password', {
        current_password: 'Old@1234!',
        new_password: 'New@12345!',
      });
    } catch (e) {
      caught = e;
    }

    expect(handler).toHaveBeenCalledTimes(1);
    expect(caught).not.toBeNull();
    expect(caught.response.status).toBe(403);
    // No redirect.
    expect(window.location.href).toBe('http://localhost/account-settings');

    unregister();
    unmount();
  });

  test('401 + canonical envelope on a replayed request short-circuits the bare-401 logout branch', async () => {
    // Defense in depth: even if a future route emits the envelope as 401
    // and reaches the response interceptor on a replayed request
    // (`_mfaStepUpRetried` true), the interceptor must reject the error
    // instead of calling attemptTokenRefresh + window.location='/login'.
    const { captured, unmount } = mountAndCaptureApi();
    await waitFor(() => expect(captured.api).not.toBeNull());

    const handler = jest.fn();
    const unregister = registerMfaStepUpHandler(handler);

    captured.api.defaults.adapter = (config) =>
      Promise.reject({
        config,
        response: mockResponse({
          status: 401,
          data: {
            detail: {
              code: 'MFA_PASSKEY_REQUIRED',
              message: 'هذا الإجراء يتطلب تسجيل مفتاح أمان',
            },
          },
        }),
        message: 'Request failed with status code 401',
        isAxiosError: true,
      });

    let caught = null;
    try {
      // _mfaStepUpRetried marks this as already-replayed so the step-up
      // branch is skipped; the defense-in-depth branch must catch it.
      await captured.api.request({
        url: '/auth/change-password',
        method: 'POST',
        data: { current_password: 'x', new_password: 'y' },
        _mfaStepUpRetried: true,
      });
    } catch (e) {
      caught = e;
    }

    expect(caught).not.toBeNull();
    expect(caught.response.status).toBe(401);
    expect(handler).not.toHaveBeenCalled();
    // The legacy bare-401 fallback must NOT have redirected.
    expect(window.location.href).toBe('http://localhost/account-settings');

    unregister();
    unmount();
  });

  test('200 success resolves to the caller without invoking the step-up handler or navigating', async () => {
    const { captured, unmount } = mountAndCaptureApi();
    await waitFor(() => expect(captured.api).not.toBeNull());

    const handler = jest.fn();
    const unregister = registerMfaStepUpHandler(handler);

    captured.api.defaults.adapter = () =>
      Promise.resolve(
        mockResponse({ status: 200, data: { message: 'تم تغيير كلمة المرور بنجاح' } }),
      );

    const result = await captured.api.post('/auth/change-password', {
      current_password: 'Old@1234!',
      new_password: 'New@12345!',
    });

    expect(result.status).toBe(200);
    expect(result.data.message).toBe('تم تغيير كلمة المرور بنجاح');
    expect(handler).not.toHaveBeenCalled();
    expect(window.location.href).toBe('http://localhost/account-settings');

    unregister();
    unmount();
  });

  test('Task #351: 403 + MFA_RESTORE_REQUIRED rejects to caller WITHOUT opening step-up handler or navigating', async () => {
    // The recovery-code session state cannot be satisfied by the step-up
    // modal — only re-enrolling a primary factor can. The interceptor
    // must NOT call the registered handler for this code; it must reject
    // with the original error so AccountSettingsPage can route the user
    // to the MFA Security section. The defense-in-depth branch still
    // protects against the bare-401 logout fallback.
    const { captured, unmount } = mountAndCaptureApi();
    await waitFor(() => expect(captured.api).not.toBeNull());

    const handler = jest.fn();
    const unregister = registerMfaStepUpHandler(handler);

    captured.api.defaults.adapter = (config) =>
      Promise.reject({
        config,
        response: mockResponse({
          status: 403,
          data: {
            detail: {
              code: 'MFA_RESTORE_REQUIRED',
              message:
                'تم استخدام رمز استرداد. يجب إعادة تسجيل عامل تحقق (مفتاح أمان أو تطبيق مصادقة) قبل المتابعة',
            },
          },
        }),
        message: 'Request failed with status code 403',
        isAxiosError: true,
      });

    let caught = null;
    try {
      await captured.api.post('/auth/change-password', {
        current_password: 'Old@1234!',
        new_password: 'New@12345!',
      });
    } catch (e) {
      caught = e;
    }

    expect(caught).not.toBeNull();
    expect(caught.response.status).toBe(403);
    expect(caught.response.data.detail.code).toBe('MFA_RESTORE_REQUIRED');
    // Critical: the step-up handler MUST NOT be invoked for this code.
    expect(handler).not.toHaveBeenCalled();
    // No /login redirect either.
    expect(window.location.href).toBe('http://localhost/account-settings');

    unregister();
    unmount();
  });

  test('400 + Arabic detail rejects to the caller without step-up and without navigation', async () => {
    const { captured, unmount } = mountAndCaptureApi();
    await waitFor(() => expect(captured.api).not.toBeNull());

    const handler = jest.fn();
    const unregister = registerMfaStepUpHandler(handler);

    const arabicDetail = 'كلمة المرور الحالية غير صحيحة';
    captured.api.defaults.adapter = (config) =>
      Promise.reject({
        config,
        response: mockResponse({ status: 400, data: { detail: arabicDetail } }),
        message: 'Request failed with status code 400',
        isAxiosError: true,
      });

    let caught = null;
    try {
      await captured.api.post('/auth/change-password', {
        current_password: 'wrong',
        new_password: 'New@12345!',
      });
    } catch (e) {
      caught = e;
    }

    expect(caught).not.toBeNull();
    expect(caught.response.status).toBe(400);
    expect(caught.response.data.detail).toBe(arabicDetail);
    expect(handler).not.toHaveBeenCalled();
    expect(window.location.href).toBe('http://localhost/account-settings');

    unregister();
    unmount();
  });
});
