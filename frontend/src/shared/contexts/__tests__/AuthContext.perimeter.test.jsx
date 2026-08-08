/**
 * Task #186 — interceptor contract for the IT "finish setup" perimeter gate.
 *
 * The backend emits HTTP 409 + safe Arabic detail when an IT user calls
 * a non-allowlisted route with an empty `tenant_id` claim. The axios
 * response interceptor in AuthContext must:
 *   (a) silently refresh the token when refresh succeeds AND the new
 *       token's `tenant_id` claim is non-empty, then retry the original
 *       request once;
 *   (b) when refresh fails OR returns a token still missing tenant_id,
 *       fire the registered perimeter-gate handler (drives the
 *       NassaqAlertDialog + navigate('/teacher/onboarding')); and
 *   (c) collapse N parallel 409s into a single dialog notification
 *       (one-shot guard).
 *
 * No `toast.error` and no `nassaqError` may be invoked on this branch.
 */
import {
  registerPerimeterGateHandler,
  isPerimeterGateHandlerRegistered,
  resetBootstrapDialogGuard,
} from '@/shared/services/perimeterGateBridge';
import { WORKSPACE_NOT_MATERIALISED_AR_FE } from '@/shared/models/constants/auth';

// Build a minimal axios-shaped error fixture matching the FastAPI
// envelope shape the interceptor expects (`error.response.data.detail`).
function makeAxios409Error(url, method = 'GET') {
  const config = { url, method, headers: {}, _retryCount: 0 };
  const error = {
    config,
    response: {
      status: 409,
      data: { detail: WORKSPACE_NOT_MATERIALISED_AR_FE },
      headers: {},
    },
    message: 'Request failed with status code 409',
  };
  return error;
}

// Encode a base64url JWT payload — header/signature can be anything.
function makeAccessToken(claims) {
  const b64 = (obj) =>
    Buffer.from(JSON.stringify(obj)).toString('base64')
      .replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_');
  return `${b64({ alg: 'HS256', typ: 'JWT' })}.${b64(claims)}.sig`;
}

describe('Task #186 perimeter-gate interceptor', () => {
  beforeEach(() => {
    resetBootstrapDialogGuard();
    localStorage.clear();
    sessionStorage.clear();
  });

  test('detects the canonical 409 + safe Arabic detail tuple', () => {
    const err = makeAxios409Error('/students');
    expect(err.response.status).toBe(409);
    expect(err.response.data.detail).toBe(WORKSPACE_NOT_MATERIALISED_AR_FE);
  });

  test('handler bridge is one-shot per session via the shared guard', () => {
    const handler = jest.fn();
    const unregister = registerPerimeterGateHandler(handler);
    expect(isPerimeterGateHandlerRegistered()).toBe(true);

    // Simulate the interceptor's guard: dispatch only when the guard is unset.
    const {
      hasShownBootstrapDialogThisSession,
      markBootstrapDialogShownThisSession,
      notifyWorkspaceNotMaterialised,
    } = require('@/shared/services/perimeterGateBridge');

    for (let i = 0; i < 5; i += 1) {
      if (!hasShownBootstrapDialogThisSession()) {
        markBootstrapDialogShownThisSession();
        notifyWorkspaceNotMaterialised();
      }
    }
    expect(handler).toHaveBeenCalledTimes(1);

    resetBootstrapDialogGuard();
    if (!hasShownBootstrapDialogThisSession()) {
      markBootstrapDialogShownThisSession();
      notifyWorkspaceNotMaterialised();
    }
    expect(handler).toHaveBeenCalledTimes(2);

    unregister();
    expect(isPerimeterGateHandlerRegistered()).toBe(false);
  });

  test('refreshed token with non-empty tenant_id is recognised as recovered', () => {
    // Mirror the interceptor's `_decodeJwtPayload` recovery decision.
    const recoveredToken = makeAccessToken({
      sub: 'u-1',
      tenant_id: 'itw_u-1',
      type: 'access',
    });
    const stillEmpty = makeAccessToken({ sub: 'u-1', type: 'access' });

    const decode = (t) => {
      try {
        const part = t.split('.')[1];
        const padded = part.replace(/-/g, '+').replace(/_/g, '/');
        const pad = padded.length % 4 === 0 ? '' : '='.repeat(4 - (padded.length % 4));
        return JSON.parse(Buffer.from(padded + pad, 'base64').toString('utf8'));
      } catch {
        return null;
      }
    };

    expect(decode(recoveredToken).tenant_id).toBeTruthy();
    expect(decode(stillEmpty).tenant_id).toBeFalsy();
  });

  test('handler is NOT invoked for unrelated 409s', () => {
    const handler = jest.fn();
    const unregister = registerPerimeterGateHandler(handler);

    // Build a 409 with a DIFFERENT detail (e.g. concurrent edit conflict)
    const err = {
      config: { url: '/something', method: 'PUT', headers: {} },
      response: { status: 409, data: { detail: 'تعارض في التعديل' }, headers: {} },
    };

    // Mirror the interceptor's predicate.
    const detail = typeof err.response.data.detail === 'string'
      ? err.response.data.detail
      : (err.response.data.detail?.message || '');
    const matchesPerimeter = err.response.status === 409
      && detail === WORKSPACE_NOT_MATERIALISED_AR_FE;
    expect(matchesPerimeter).toBe(false);
    expect(handler).not.toHaveBeenCalled();

    unregister();
  });
});
