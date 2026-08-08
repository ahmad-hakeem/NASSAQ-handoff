/**
 * Task #790 — interceptor contract for a school preview whose
 * impersonation session was silently lost.
 *
 * The short-lived (15-min) impersonation token minted by
 * /role-switch/switch is NOT part of the refresh-token family, so a
 * background token refresh can replace it with a plain platform-admin
 * token while the preview flags (nassaq_school_context /
 * nassaq_impersonating) are still active. Task #788 made the backend
 * fail closed (403) in that state. The axios response interceptor must
 * detect the exact "session lost" tuple and cleanly tear the preview
 * down instead of letting the preview UI render 403s:
 *   (a) a 403 whose request carried the X-School-Context header, AND
 *   (b) the nassaq_impersonating flag is still 'true', AND
 *   (c) the LIVE access token no longer carries an impersonation claim.
 *
 * A 403 on a still-valid preview token (genuine permission/MFA failure)
 * or a 403 with no X-School-Context header must NOT trigger teardown.
 */

// Encode a base64url JWT payload — header/signature can be anything.
function makeAccessToken(claims) {
  const b64 = (obj) =>
    Buffer.from(JSON.stringify(obj)).toString('base64')
      .replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_');
  return `${b64({ alg: 'HS256', typ: 'JWT' })}.${b64(claims)}.sig`;
}

// Mirror the interceptor's `_decodeJwtPayload` + `_tokenStillImpersonating`.
function decode(t) {
  try {
    const part = t.split('.')[1];
    if (!part) return null;
    const padded = part.replace(/-/g, '+').replace(/_/g, '/');
    const pad = padded.length % 4 === 0 ? '' : '='.repeat(4 - (padded.length % 4));
    return JSON.parse(Buffer.from(padded + pad, 'base64').toString('utf8'));
  } catch {
    return null;
  }
}

function tokenStillImpersonating(stored) {
  if (!stored) return false;
  const claims = decode(stored);
  if (!claims) return false;
  const tenant = claims.tenant_id || claims.school_id;
  return !!(claims.is_impersonating && tenant);
}

// Mirror the interceptor's preview-session-lost predicate.
function isPreviewSessionLost({ status, headers, impersonatingFlag, storedToken }) {
  const sentSchoolContext = !!(headers &&
    (headers['X-School-Context'] || headers['x-school-context']));
  return (
    status === 403 &&
    sentSchoolContext &&
    impersonatingFlag === true &&
    !tokenStillImpersonating(storedToken)
  );
}

const PA_TOKEN = makeAccessToken({ sub: 'pa-1', role: 'platform_admin', type: 'access' });
const IMPERSONATION_TOKEN = makeAccessToken({
  sub: 'pa-1', role: 'platform_admin', is_impersonating: true,
  tenant_id: 'sch_42', type: 'access',
});

describe('Task #790 preview-session-lost interceptor predicate', () => {
  test('a refreshed plain PA token no longer reads as impersonating', () => {
    expect(tokenStillImpersonating(IMPERSONATION_TOKEN)).toBe(true);
    expect(tokenStillImpersonating(PA_TOKEN)).toBe(false);
    expect(tokenStillImpersonating(null)).toBe(false);
  });

  test('403 + X-School-Context + flag set + non-impersonating token → teardown', () => {
    expect(isPreviewSessionLost({
      status: 403,
      headers: { 'X-School-Context': 'sch_42' },
      impersonatingFlag: true,
      storedToken: PA_TOKEN,
    })).toBe(true);
  });

  test('403 while the token is STILL a valid impersonation token → no teardown', () => {
    // Genuine permission/MFA failure inside an active preview must keep
    // its own handling rather than dropping the user out of preview.
    expect(isPreviewSessionLost({
      status: 403,
      headers: { 'X-School-Context': 'sch_42' },
      impersonatingFlag: true,
      storedToken: IMPERSONATION_TOKEN,
    })).toBe(false);
  });

  test('403 with no X-School-Context header → no teardown', () => {
    expect(isPreviewSessionLost({
      status: 403,
      headers: {},
      impersonatingFlag: true,
      storedToken: PA_TOKEN,
    })).toBe(false);
  });

  test('403 when not impersonating at all → no teardown', () => {
    expect(isPreviewSessionLost({
      status: 403,
      headers: { 'X-School-Context': 'sch_42' },
      impersonatingFlag: false,
      storedToken: PA_TOKEN,
    })).toBe(false);
  });

  test('non-403 status is ignored even with the lost-session shape', () => {
    expect(isPreviewSessionLost({
      status: 401,
      headers: { 'X-School-Context': 'sch_42' },
      impersonatingFlag: true,
      storedToken: PA_TOKEN,
    })).toBe(false);
  });
});
