import { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { createApiService } from '../services/apiClient';
import { isMfaStepUpHandlerRegistered, requestMfaStepUp } from '../services/mfaStepUpBridge';
import {
  isPerimeterGateHandlerRegistered,
  notifyWorkspaceNotMaterialised,
  hasShownBootstrapDialogThisSession,
  markBootstrapDialogShownThisSession,
  resetBootstrapDialogGuard,
} from '../services/perimeterGateBridge';
import { WORKSPACE_NOT_MATERIALISED_AR_FE } from '../constants/auth';
import { isIdempotentWriteRetry } from '../utils/retryableWrite';
import arLocale from '../locales/ar.json';
import enLocale from '../locales/en.json';

// Lightweight base64url JWT payload decoder (no signature check — the
// backend re-validates every request). Used by the perimeter-gate
// interceptor branch to decide whether a freshly-refreshed access token
// has had its `tenant_id` claim populated by another tab's bootstrap.
function _decodeJwtPayload(token) {
  try {
    const part = token.split('.')[1];
    if (!part) return null;
    const padded = part.replace(/-/g, '+').replace(/_/g, '/');
    const pad = padded.length % 4 === 0 ? '' : '='.repeat(4 - (padded.length % 4));
    const json = atob(padded + pad);
    return JSON.parse(decodeURIComponent(escape(json)));
  } catch {
    return null;
  }
}

// Lightweight translator that does not depend on a React hook — used by the
// axios interceptor which lives outside React's render tree. Falls back to
// Arabic (default app language) when a key is missing.
const translateToast = (key, params) => {
  const lang = (typeof window !== 'undefined' && localStorage.getItem('nassaq_language')) || 'ar';
  const dict = lang === 'en' ? enLocale : arLocale;
  let text = dict[key] || arLocale[key] || key;
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
    });
  }
  return text;
};

export const AuthContext = createContext(null);

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const RETRY_STATUS_CODES = new Set([502, 503]);
const MAX_RETRIES = 2;
const BASE_DELAY_MS = 500;

let refreshPromise = null;

// Task #790 — single-flight guard so the many parallel 403s a school
// preview page fires (notifications, analytics, stats, ...) only trigger
// ONE clean preview teardown instead of N stacked toasts / state churn.
let previewSessionLostInFlight = false;

// Task #790 — does the live access token still carry an active
// impersonation session? The 15-min token minted by /role-switch/switch
// is NOT part of the refresh-token family, so a background refresh can
// quietly swap it for a plain platform-admin token (no `is_impersonating`,
// no `tenant_id`) while the preview UI flags are still set. We decode the
// stored token (no signature check — the backend re-validates) to tell
// "still previewing" apart from "preview session was lost".
function _tokenStillImpersonating() {
  const stored = typeof window !== 'undefined' ? localStorage.getItem('nassaq_token') : null;
  if (!stored) return false;
  const claims = _decodeJwtPayload(stored);
  if (!claims) return false;
  const tenant = claims.tenant_id || claims.school_id;
  return !!(claims.is_impersonating && tenant);
}

async function attemptTokenRefresh() {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    const refreshToken = localStorage.getItem('nassaq_refresh_token') || sessionStorage.getItem('nassaq_refresh_token');
    if (!refreshToken) return null;

    try {
      const response = await axios.post(`${API_URL}/api/auth/refresh`, { refresh_token: refreshToken });
      const { access_token: newAccess, refresh_token: newRefresh } = response.data;

      localStorage.setItem('nassaq_token', newAccess);

      if (newRefresh) {
        if (localStorage.getItem('nassaq_refresh_token')) {
          localStorage.setItem('nassaq_refresh_token', newRefresh);
        } else {
          sessionStorage.setItem('nassaq_refresh_token', newRefresh);
        }
      }

      return newAccess;
    } catch {
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

function clearAllAuthTokens() {
  localStorage.removeItem('nassaq_token');
  localStorage.removeItem('nassaq_refresh_token');
  localStorage.removeItem('rememberMe');
  sessionStorage.removeItem('nassaq_refresh_token');
}

async function retryRequest(axiosInstance, config, retryCount) {
  const delay = BASE_DELAY_MS * Math.pow(2, retryCount);
  await new Promise((r) => setTimeout(r, delay));
  const { Authorization, 'X-School-Context': _sc, ...customHeaders } = config.headers || {};
  const retryCfg = { ...config, _retryCount: retryCount + 1, headers: customHeaders };
  return axiosInstance.request(retryCfg);
}

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('nassaq_token'));
  const [loading, setLoading] = useState(true);
  // Task #231 — initial workspace lifecycle snapshot embedded in the
  // login / MFA verify response. Held in a ref (not state) so the
  // one-shot consumer in <ReactivationBanner> can read it inside a
  // useState initializer without triggering an "update during render"
  // warning. Cleared on consume + on logout/clearAuthState.
  const initialWorkspaceLifecycleRef = useRef(null);
  
  // School Context Switching (Platform Admin -> School Manager simulation)
  const [schoolContext, setSchoolContext] = useState(() => {
    try {
      const saved = sessionStorage.getItem('nassaq_school_context');
      return saved ? JSON.parse(saved) : null;
    } catch { return null; }
  });
  const [isImpersonating, setIsImpersonating] = useState(() => {
    return sessionStorage.getItem('nassaq_impersonating') === 'true';
  });

  const api = useMemo(() => axios.create({
    baseURL: `${API_URL}/api`,
    headers: {
      'Content-Type': 'application/json',
    },
  }), []);

  useEffect(() => {
  const reqInterceptor = api.interceptors.request.use((config) => {
    const storedToken = localStorage.getItem('nassaq_token');
    if (storedToken) {
      config.headers.Authorization = `Bearer ${storedToken}`;
    }

    // Let axios set the proper multipart boundary itself for FormData uploads
    if (typeof FormData !== 'undefined' && config.data instanceof FormData) {
      if (config.headers) {
        delete config.headers['Content-Type'];
        delete config.headers['content-type'];
      }
    }

    const savedContext = sessionStorage.getItem('nassaq_school_context');
    if (savedContext) {
      let ctx = null;
      try { ctx = JSON.parse(savedContext); } catch {}
      if (ctx?.school_id) {
        config.headers['X-School-Context'] = ctx.school_id;
      }
    }
    return config;
  });

  const resInterceptor = api.interceptors.response.use(
    (response) => response,
    async (error) => {
      // Silently ignore canceled/aborted requests (StrictMode double-mount,
      // route changes, AbortController cleanups). These are not real failures
      // and must NOT trigger global error toasts.
      if (
        axios.isCancel?.(error) ||
        error?.name === 'CanceledError' ||
        error?.code === 'ERR_CANCELED' ||
        error?.message === 'canceled'
      ) {
        return Promise.reject(error);
      }

      const config = error.config || {};
      const retryCount = config._retryCount || 0;
      const status = error.response?.status;

      // Normalize wrapped error envelope { success:false, error:{code,message} }
      // back into FastAPI-style { detail } so existing handlers keep working.
      if (error.response?.data && typeof error.response.data === 'object') {
        const data = error.response.data;
        if (!data.detail && data.error && typeof data.error === 'object') {
          const msg = data.error.message || data.error.detail || data.error.code;
          if (msg) data.detail = msg;
        }
      }
      const isGet = (config.method || '').toUpperCase() === 'GET';
      const isTransient = !error.response || RETRY_STATUS_CODES.has(status);

      // Task #785 — GETs already auto-retry a transient blip (no response /
      // 502 / 503). Writes did not, so a brief network drop on a "save"
      // silently became a generic error the user had to retry by hand (the
      // same asymmetry behind the #784 transfer bug). We extend the SAME retry
      // to a small, explicit allow-list of idempotent write endpoints only —
      // re-sending them is a safe no-op, so we never double-submit a create.
      if ((isGet || isIdempotentWriteRetry(config)) && isTransient && retryCount < MAX_RETRIES) {
        return retryRequest(api, config, retryCount);
      }

      // Task #186 — IT perimeter "finish setup" handler.
      // The backend's `require_workspace_materialised` gate emits a
      // canonical 409 + safe Arabic detail when an IT user calls a
      // non-allowlisted route with `tenant_id` claim still empty (signed
      // up but never bootstrapped, OR opened a stale tab after another
      // tab finished bootstrap). We do NOT widen this branch — it must
      // match on BOTH status 409 AND the exact constant detail string,
      // so unrelated 409s (concurrent edits, version mismatches, etc.)
      // keep their existing handling.
      const detailField = error.response?.data?.detail;
      const detailMessage = typeof detailField === 'string'
        ? detailField
        : (detailField?.message || error.response?.data?.error?.message || '');
      if (
        status === 409
        && detailMessage === WORKSPACE_NOT_MATERIALISED_AR_FE
        && !config._perimeterGateRetried
      ) {
        // First, try a single-flight refresh — covers the common
        // "bootstrapped in another tab" race transparently. Reuse the
        // shared `attemptTokenRefresh` so parallel 409s coalesce.
        const refreshed = await attemptTokenRefresh();
        if (refreshed) {
          const claims = _decodeJwtPayload(refreshed);
          if (claims && claims.tenant_id) {
            setToken(refreshed);
            const retryCfg = {
              ...config,
              _perimeterGateRetried: true,
              headers: { ...config.headers, Authorization: `Bearer ${refreshed}` },
            };
            return api.request(retryCfg);
          }
        }
        // Real "not bootstrapped yet" — show the one-shot guidance
        // dialog (idempotent across parallel 409s) and route to the
        // wizard. Suppress the default error UI for this rejection.
        if (!hasShownBootstrapDialogThisSession() && isPerimeterGateHandlerRegistered()) {
          markBootstrapDialogShownThisSession();
          notifyWorkspaceNotMaterialised();
        }
        return Promise.reject(error);
      }

      // Task #169 Step 9 — MFA step-up interceptor.
      // Backend signals "fresh MFA proof required" with HTTP 401 + a
      // structured detail dict {code: "MFA_STEPUP_REQUIRED", ...}. We
      // intercept here, hand off to the React-mounted MfaStepUpProvider
      // (via a tiny module-level bridge so a non-React interceptor can
      // wake a React modal), and on a successful step-up replay the
      // original request with the freshly-stamped access token. The
      // dialog itself never unmounts the active route.
      const mfaCode =
        error.response?.data?.error?.code ||
        (typeof error.response?.data?.detail === 'object' ? error.response.data.detail.code : null);
      // Task #199: sensitive-action surfaces (e.g. IT Invite Parent)
      // return 403 + canonical step-up payload instead of 401, so the
      // step-up modal can drive a Tier-A re-auth from a non-auth
      // context. Both status codes funnel through the same replay.
      //
      // Task #351: MFA_RESTORE_REQUIRED is intentionally NOT in this
      // auto-replay set. That code is only emitted when a Tier-A user
      // signed in with a recovery code and `mfa_must_restore_factor`
      // is true on the user row. The step-up dialog cannot satisfy it
      // — only enrolling a fresh primary factor (passkey / TOTP) can
      // — so opening the modal would either fail outright or loop. We
      // reject with the original error and let the calling component
      // (e.g. AccountSettingsPage handleChangePassword) detect the code
      // and route the user to the MFA Security section instead. The
      // canonical envelope is still recognised by the defense-in-depth
      // re-rejection block below, so we never fall through to the
      // bare-401 hard-logout path.
      const mfaStepUpCodes = new Set([
        'MFA_STEPUP_REQUIRED',
        'MFA_PASSKEY_REQUIRED',
      ]);
      const mfaCanonicalCodes = new Set([
        'MFA_STEPUP_REQUIRED',
        'MFA_PASSKEY_REQUIRED',
        'MFA_RESTORE_REQUIRED',
      ]);
      if ((status === 401 || status === 403) && mfaStepUpCodes.has(mfaCode) && !config._mfaStepUpRetried) {
        if (!isMfaStepUpHandlerRegistered()) {
          return Promise.reject(error);
        }
        try {
          const newAccess = await requestMfaStepUp({
            requestUrl: config.url,
            requestMethod: config.method,
          });
          if (!newAccess) return Promise.reject(error);
          setToken(newAccess);
          const retryCfg = {
            ...config,
            _mfaStepUpRetried: true,
            headers: { ...config.headers, Authorization: `Bearer ${newAccess}` },
          };
          return api.request(retryCfg);
        } catch {
          return Promise.reject(error);
        }
      }

      // Task #338 — defense in depth for the canonical step-up envelope.
      // The block above already opens the step-up modal when the response
      // carries a step-up code on a fresh attempt. If the same envelope
      // arrives on a replayed request (`_mfaStepUpRetried` is set, e.g.
      // user cancelled / failed step-up, or the replay still wasn't
      // accepted) we MUST NOT fall through to the legacy bare-401
      // handler — that would call attemptTokenRefresh() and, on failure,
      // hard-redirect the user to /login. Instead, reject the original
      // error so the calling component's `catch` surfaces its own Arabic
      // form-level message. This keeps any future route that emits the
      // canonical envelope safe even if it does so as a 401.
      if (mfaCanonicalCodes.has(mfaCode)) {
        return Promise.reject(error);
      }

      // Task #790 — gracefully tear down a school preview whose
      // impersonation session was silently lost. The short-lived (15-min)
      // impersonation token minted by /role-switch/switch is NOT part of
      // the refresh-token family, so a background token refresh can replace
      // it with a plain platform-admin token while the preview flags
      // (nassaq_school_context / nassaq_impersonating) are still active.
      // Task #788 made the backend fail closed (403) in that state. Rather
      // than letting the preview UI render those 403s as empty/error data,
      // we detect the exact condition — a 403 on a request that carried the
      // X-School-Context header, while the impersonation flag is still set
      // but the LIVE token no longer carries the impersonated tenant — and
      // cleanly drop back to the platform-admin context. The route guards
      // then redirect the (now non-impersonating) platform admin off any
      // school-only route to /admin. We deliberately scope this to the
      // "session lost" signal so a 403 on a still-valid preview token
      // (e.g. a genuine permission/MFA failure) keeps its own handling.
      const sentSchoolContext = !!(config.headers &&
        (config.headers['X-School-Context'] || config.headers['x-school-context']));
      let impersonationFlag = false;
      try {
        impersonationFlag =
          typeof sessionStorage !== 'undefined' &&
          sessionStorage.getItem('nassaq_impersonating') === 'true';
      } catch {
        impersonationFlag = false;
      }
      if (
        status === 403 &&
        sentSchoolContext &&
        impersonationFlag &&
        !_tokenStillImpersonating()
      ) {
        if (!previewSessionLostInFlight) {
          previewSessionLostInFlight = true;
          try {
            sessionStorage.removeItem('nassaq_school_context');
            sessionStorage.removeItem('nassaq_impersonating');
            sessionStorage.removeItem('nassaq_original_token');
          } catch {
            // best-effort cleanup; React state reset below is authoritative
          }
          setSchoolContext(null);
          setIsImpersonating(false);
          toast.error(translateToast('previewSessionExpired'), {
            id: 'preview-session-expired',
          });
          // Release the single-flight guard once the React state has
          // settled so a genuinely new preview session later can re-trigger
          // this path.
          setTimeout(() => { previewSessionLostInFlight = false; }, 1500);
        }
        return Promise.reject(error);
      }

      if (status === 401 && !config.url?.includes('/auth/me') && !config.url?.includes('/auth/login') && !config.url?.includes('/auth/refresh')) {
        // A 401 for a request that had NO Authorization header to begin
        // with is not an expired session — it's an endpoint the caller
        // (a guest) isn't allowed to hit (e.g. /public/stats is locked
        // to platform_admin per the C-4 audit). Bouncing the browser to
        // /login here would trap guests on the public landing page in a
        // /login → / → /login redirect loop the moment any background
        // poll 401s. Reject silently and let the caller surface the
        // error (LandingPage already swallows /public/stats failures).
        const hadAuthHeader = !!(config.headers && (config.headers.Authorization || config.headers.authorization));
        const hasStoredToken = !!localStorage.getItem('nassaq_token');
        if (!hadAuthHeader && !hasStoredToken) {
          return Promise.reject(error);
        }

        if (config._isRetryAfterRefresh) {
          clearAllAuthTokens();
          setToken(null);
          setUser(null);
          window.location.href = '/login';
          return Promise.reject(error);
        }

        const newAccess = await attemptTokenRefresh();
        if (newAccess) {
          setToken(newAccess);
          const retryCfg = { ...config, _isRetryAfterRefresh: true, headers: { ...config.headers, Authorization: `Bearer ${newAccess}` } };
          return api.request(retryCfg);
        } else {
          clearAllAuthTokens();
          setToken(null);
          setUser(null);
          window.location.href = '/login';
          return Promise.reject(error);
        }
      }

      if (status === 429) {
        // Task #195 — the login page owns its own error surface for
        // rate-limit failures; suppress the global 429 toast for
        // /auth/login (and the immediately-following /auth/me) so it
        // can't double-fire alongside the inline banner.
        const url429 = config.url || '';
        const isLoginRateLimit =
          url429.includes('/auth/login') ||
          url429.includes('/auth/me');
        if (!isLoginRateLimit) {
          const retryAfter = error.response?.headers?.['retry-after'];
          const parsed = retryAfter ? parseInt(retryAfter, 10) : NaN;
          const secs = Number.isFinite(parsed) && parsed > 0 ? parsed : 30;
          toast.error(translateToast('tooManyRequestsWaitSeconds', { seconds: secs }));
        }
        return Promise.reject(error);
      }

      // Only surface a global toast for catastrophic failures, and only on
      // mutations. GET failures (single widget data, dashboards, etc.) must
      // be handled by the calling component so a partial failure does not
      // crash the whole page or display a misleading "offline" message.
      const isMutation = !isGet && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(
        (config.method || '').toUpperCase()
      );
      const isRealNetworkError =
        !error.response &&
        (error.message === 'Network Error' || error.code === 'ERR_NETWORK');

      if (isMutation && (status >= 500 || isRealNetworkError)) {
        const PUBLIC_PATHS = ['/', '/login', '/register', '/about', '/contact', '/pricing', '/forgot-password'];
        const isPublicPath = PUBLIC_PATHS.includes(window.location.pathname);
        const url = config.url || '';
        const isAuthMe = url.includes('/auth/me');
        // Task #195 — the login page owns its own error surface for the
        // /auth/login call and the immediately-following /auth/me bootstrap.
        // Suppress the global server-error toast for those two endpoints so
        // it cannot double-fire alongside the login card's banner / dialog.
        const isAuthLogin = url.includes('/auth/login');
        // Task #470 — /auth/change-password owns its own error surface
        // (in-form `nassaqError` from AccountSettingsPage, the parent
        // PasswordChangeDialog, and TeacherSettingsPage). Suppress the
        // generic server-error toast for this route so a backend 5xx
        // cannot double-fire alongside the in-form Arabic error.
        const isChangePassword = url.includes('/auth/change-password');
        const isLoginOrPostLoginAuthMe = isAuthLogin || (isPublicPath && isAuthMe);
        if (!isLoginOrPostLoginAuthMe && !isChangePassword) {
          const msg = isRealNetworkError
            ? translateToast('serverConnectionFailed')
            : translateToast('serverErrorWithCode', { code: status });
          toast.error(msg, { id: 'server-conn-error' });
        }
      }

      return Promise.reject(error);
    }
  );

  return () => {
    api.interceptors.request.eject(reqInterceptor);
    api.interceptors.response.eject(resInterceptor);
  };
  }, [api]);

  const fetchUser = useCallback(async () => {
    if (!token) {
      setLoading(false);
      return;
    }
    if (user) {
      setLoading(false);
      return;
    }

    const PUBLIC_PATHS = ['/', '/login', '/register', '/about', '/contact', '/pricing', '/forgot-password'];
    const isPublicPath = PUBLIC_PATHS.includes(window.location.pathname);

    const fetchWithTimeout = async (timeoutMs) => {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
      try {
        return await api.get('/auth/me', { signal: controller.signal });
      } finally {
        clearTimeout(timeoutId);
      }
    };

    try {
      let response;
      try {
        response = await fetchWithTimeout(20000);
      } catch (firstErr) {
        const isTimeout = firstErr.name === 'CanceledError' || firstErr.code === 'ERR_CANCELED';
        if (isTimeout) {
          console.warn('fetchUser timed out after 20s, retrying once...');
          response = await fetchWithTimeout(20000);
        } else {
          throw firstErr;
        }
      }
      setUser(response.data);
    } catch (error) {
      if (error.name === 'CanceledError' || error.code === 'ERR_CANCELED') {
        console.error('fetchUser timed out after retry');
        if (!isPublicPath) {
          toast.error('انتهت مهلة الاتصال — يرجى تحديث الصفحة');
        }
      } else if (error.response?.status === 401) {
        const newAccess = await attemptTokenRefresh();
        if (newAccess) {
          setToken(newAccess);
          try {
            const retryResponse = await api.get('/auth/me');
            setUser(retryResponse.data);
            return;
          } catch {}
        }
        clearAllAuthTokens();
        setToken(null);
        setUser(null);
      } else {
        console.error('Failed to fetch user:', error);
        // Task #196 — suppress the bootstrap toast on public/auth surfaces
        // (login, forgot-password, etc.) so it cannot double-fire alongside
        // the LoginPage's own inline error banner during the login → /auth/me
        // race, and so a user who navigates away from /login mid-bootstrap
        // doesn't see a stale "failed to load profile" message. Protected
        // routes still surface a single Arabic message here.
        if (!isPublicPath) {
          toast.error('تعذر تحميل بيانات المستخدم');
        }
      }
    } finally {
      setLoading(false);
    }
  }, [token, api]);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  const login = async (email, password, rememberMe = false) => {
    try {
      const response = await api.post('/auth/login', { email, password, remember_me: rememberMe });
      const data = response.data || {};

      // Task #169 Step 10 — MFA-required login response.
      // The backend returns { mfa_required: true, mfa_tier, challenge_token,
      // challenge_expires_at, available_factor_kinds } and intentionally
      // withholds access_token / refresh_token until the second factor is
      // verified via /auth/mfa/verify. The login page surfaces this as an
      // inline factor picker.
      if (data.mfa_required) {
        return {
          success: false,
          mfaChallenge: {
            challenge_token: data.challenge_token,
            challenge_expires_at: data.challenge_expires_at,
            available_factor_kinds: data.available_factor_kinds || [],
            mfa_tier: data.mfa_tier,
            mfa_enrollment_required: !!data.mfa_enrollment_required,
            remember_me: rememberMe,
          },
        };
      }

      const { access_token, refresh_token: refreshToken, user: userData } = data;

      localStorage.setItem('nassaq_token', access_token);
      setToken(access_token);
      setUser(userData);
      // Task #186 — fresh login resets the one-shot perimeter-gate
      // dialog guard so a future stale-token recurrence in this tab
      // can re-prompt.
      resetBootstrapDialogGuard();
      // Task #231 — stash the IT workspace lifecycle snapshot embedded
      // in the login response so the post-login dashboard can render
      // the reactivation banner without waiting on a follow-up GET.
      initialWorkspaceLifecycleRef.current = data.workspace_lifecycle ?? null;

      if (refreshToken) {
        if (rememberMe) {
          localStorage.setItem('nassaq_refresh_token', refreshToken);
          sessionStorage.removeItem('nassaq_refresh_token');
        } else {
          sessionStorage.setItem('nassaq_refresh_token', refreshToken);
          localStorage.removeItem('nassaq_refresh_token');
        }
      }
      
      if (userData?.preferred_theme) {
        localStorage.setItem('nassaq_theme', userData.preferred_theme);
        const root = window.document.documentElement;
        root.classList.remove('light', 'dark');
        root.classList.add(userData.preferred_theme);
        root.setAttribute('data-theme', userData.preferred_theme);
        window.dispatchEvent(new CustomEvent('nassaq-theme-sync', { detail: { theme: userData.preferred_theme } }));
      }
      if (userData?.preferred_language) {
        localStorage.setItem('nassaq_language', userData.preferred_language);
      }
      
      return { success: true, user: userData };
    } catch (error) {
      console.error('Login error:', error);
      const httpStatus = error.response?.status;
      // Task #195 — never forward raw backend strings (`error.response.data.detail`,
      // `str(e)`, etc.) to the user. Map every login failure to a safe,
      // pre-translated Arabic message. `kind` tells the login page which
      // surface to use (inline banner vs alert dialog).
      let message = 'فشل تسجيل الدخول';
      let kind = 'system';
      // Temporary platform-wide student-login block. The backend returns a
      // structured 403 envelope with code STUDENT_LOGIN_DISABLED and a
      // pre-translated Arabic message; surface it verbatim through the
      // NassaqAlertDialog instead of the generic 4xx "invalid credentials"
      // mapping below.
      const rawDetail = error.response?.data?.detail;
      const detailCode = (rawDetail && typeof rawDetail === 'object') ? rawDetail.code : null;
      if (httpStatus === 403 && detailCode === 'STUDENT_LOGIN_DISABLED') {
        return {
          success: false,
          error: rawDetail.message_ar || 'تسجيل دخول الطالب غير متاح حالياً',
          httpStatus,
          kind: 'credentials',
          code: 'STUDENT_LOGIN_DISABLED',
        };
      }
      if (httpStatus === 401) {
        message = 'بيانات الدخول غير صحيحة';
        kind = 'credentials';
      } else if (httpStatus === 404) {
        message = 'الحساب غير موجود';
        kind = 'credentials';
      } else if (httpStatus === 429) {
        message = 'محاولات كثيرة جداً، يرجى المحاولة لاحقاً';
        kind = 'credentials';
      } else if (httpStatus && httpStatus >= 400 && httpStatus < 500) {
        message = 'بيانات الدخول غير صحيحة';
        kind = 'credentials';
      } else if (httpStatus && httpStatus >= 500) {
        message = 'خطأ في الاتصال بالخادم';
        kind = 'system';
      } else if (!error.response) {
        message = 'خطأ في الاتصال بالخادم';
        kind = 'system';
      }
      return { success: false, error: message, httpStatus, kind };
    }
  };

  // Task #195 — local-only auth state reset used when /auth/login succeeded
  // (so tokens were just persisted) but a downstream bootstrap step
  // (/auth/me, role resolution, redirect target) failed. We must NOT call
  // the server-side /auth/logout here — the issued session is fine; we
  // simply abandon it on the client so the user is left in a clean
  // signed-out state on /login.
  const clearAuthState = useCallback(() => {
    clearAllAuthTokens();
    sessionStorage.removeItem('nassaq_school_context');
    sessionStorage.removeItem('nassaq_impersonating');
    sessionStorage.removeItem('nassaq_original_token');
    setToken(null);
    setUser(null);
    setSchoolContext(null);
    setIsImpersonating(false);
    // Task #231 — drop any pending one-shot lifecycle snapshot so it
    // cannot leak across sessions (e.g. user A logs out, user B logs
    // in — B must not see A's snapshot if the new login somehow
    // skipped the assignment).
    initialWorkspaceLifecycleRef.current = null;
  }, []);

  const register = async (userData) => {
    try {
      const response = await api.post('/auth/register', userData);
      const { access_token, user: newUser } = response.data;
      
      localStorage.setItem('nassaq_token', access_token);
      setToken(access_token);
      setUser(newUser);
      
      return { success: true, user: newUser };
    } catch (error) {
      const message = error.response?.data?.detail || 'فشل إنشاء الحساب';
      return { success: false, error: message };
    }
  };

  // Task #169 Step 10 — Verify an MFA login challenge and apply the resulting
  // session. Mirrors `login()` post-success: stores tokens (respecting
  // remember_me), sets user, and applies preferences. The challenge_token
  // is the bearer for /auth/mfa/verify; the response is a normal
  // TokenResponse with access_token + refresh_token + user.
  const verifyMfaLogin = useCallback(async ({
    challenge_token,
    factor_kind,
    code,
    webauthn_response,
    webauthn_challenge_id,
    remember_me,
  }) => {
    try {
      const body = { factor_kind };
      if (code) body.code = code;
      if (webauthn_response) body.webauthn_response = webauthn_response;
      if (webauthn_challenge_id) body.webauthn_challenge_id = webauthn_challenge_id;

      const res = await axios.post(`${API_URL}/api/auth/mfa/verify`, body, {
        headers: { Authorization: `Bearer ${challenge_token}` },
      });
      const { access_token, refresh_token: refreshToken, user: userData } = res.data || {};
      if (!access_token || !userData) {
        return { success: false, error: 'فشل التحقق' };
      }

      localStorage.setItem('nassaq_token', access_token);
      setToken(access_token);
      setUser(userData);
      // Task #186 — fresh MFA-verified login also resets the one-shot
      // perimeter-gate dialog guard.
      resetBootstrapDialogGuard();
      // Task #231 — same as login(): stash the IT workspace lifecycle
      // snapshot so the post-login dashboard banner paints in the same
      // frame.
      initialWorkspaceLifecycleRef.current = res.data?.workspace_lifecycle ?? null;

      if (refreshToken) {
        if (remember_me) {
          localStorage.setItem('nassaq_refresh_token', refreshToken);
          sessionStorage.removeItem('nassaq_refresh_token');
        } else {
          sessionStorage.setItem('nassaq_refresh_token', refreshToken);
          localStorage.removeItem('nassaq_refresh_token');
        }
      }

      if (userData?.preferred_theme) {
        localStorage.setItem('nassaq_theme', userData.preferred_theme);
        const root = window.document.documentElement;
        root.classList.remove('light', 'dark');
        root.classList.add(userData.preferred_theme);
        root.setAttribute('data-theme', userData.preferred_theme);
        window.dispatchEvent(new CustomEvent('nassaq-theme-sync', { detail: { theme: userData.preferred_theme } }));
      }
      if (userData?.preferred_language) {
        localStorage.setItem('nassaq_language', userData.preferred_language);
      }

      return { success: true, user: userData, raw: res.data };
    } catch (error) {
      const detail =
        error?.response?.data?.error?.message ||
        error?.response?.data?.detail ||
        'فشل التحقق';
      return {
        success: false,
        error: typeof detail === 'string' ? detail : JSON.stringify(detail),
        status: error?.response?.status,
      };
    }
  }, []);

  // Task #169 Step 10 — Trigger an email OTP for the active login challenge.
  const sendMfaLoginEmailOtp = useCallback(async ({ challenge_token }) => {
    try {
      const res = await axios.post(`${API_URL}/api/auth/mfa/email-otp/send`, {}, {
        headers: { Authorization: `Bearer ${challenge_token}` },
      });
      return { success: true, ...(res.data || {}) };
    } catch (error) {
      const detail =
        error?.response?.data?.error?.message ||
        error?.response?.data?.detail ||
        'تعذر إرسال رمز البريد';
      return {
        success: false,
        error: typeof detail === 'string' ? detail : JSON.stringify(detail),
        status: error?.response?.status,
        retryAfter: error?.response?.headers?.['retry-after'],
      };
    }
  }, []);

  const applyAuthSession = useCallback(({ access_token, refresh_token: refreshToken, user: userData }) => {
    if (!access_token || !userData) return;
    localStorage.setItem('nassaq_token', access_token);
    setToken(access_token);
    setUser(userData);

    if (refreshToken) {
      sessionStorage.setItem('nassaq_refresh_token', refreshToken);
      localStorage.removeItem('nassaq_refresh_token');
    }

    if (userData?.preferred_theme) {
      localStorage.setItem('nassaq_theme', userData.preferred_theme);
      const root = window.document.documentElement;
      root.classList.remove('light', 'dark');
      root.classList.add(userData.preferred_theme);
      root.setAttribute('data-theme', userData.preferred_theme);
      window.dispatchEvent(new CustomEvent('nassaq-theme-sync', { detail: { theme: userData.preferred_theme } }));
    }
    if (userData?.preferred_language) {
      localStorage.setItem('nassaq_language', userData.preferred_language);
    }
  }, []);

  const logout = useCallback(() => {
    try {
      const currentToken = localStorage.getItem('nassaq_token');
      if (currentToken) {
        const refreshToken =
          localStorage.getItem('nassaq_refresh_token') ||
          sessionStorage.getItem('nassaq_refresh_token') ||
          null;
        axios.post(
          `${API_URL}/api/auth/logout`,
          { refresh_token: refreshToken },
          { headers: { Authorization: `Bearer ${currentToken}` } }
        ).catch(() => {});
      }
    } catch {}
    clearAllAuthTokens();
    sessionStorage.removeItem('nassaq_school_context');
    sessionStorage.removeItem('nassaq_impersonating');
    sessionStorage.removeItem('nassaq_original_token');
    setToken(null);
    setUser(null);
    setSchoolContext(null);
    setIsImpersonating(false);
    // Task #231 — drop any pending one-shot lifecycle snapshot so it
    // cannot leak across sessions (e.g. user A logs out, user B logs
    // in — B must not see A's snapshot if the new login somehow
    // skipped the assignment).
    initialWorkspaceLifecycleRef.current = null;
  }, []);

  useEffect(() => {
    const handleStorageChange = (e) => {
      if (e.key === 'nassaq_token' && !e.newValue) {
        clearAllAuthTokens();
        logout();
        window.location.replace('/login');
      }
    };
    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, [logout]);

  // Update token (for role switching)
  const updateToken = async (newToken) => {
    localStorage.setItem('nassaq_token', newToken);
    setToken(newToken);
    // Re-fetch user with new token
    try {
      const response = await axios.get(`${API_URL}/api/auth/me`, {
        headers: { Authorization: `Bearer ${newToken}` }
      });
      setUser(response.data);
    } catch (error) {
      console.error('Failed to fetch user after token update:', error);
    }
  };

  // Task #528 — Single source of truth for the "exit preview / return
  // to original role" flow used by both RoleSwitcherDialog and the
  // persistent PreviewModeBanner in the app shell. Wraps the hardened
  // `/user-roles/return-to-original` endpoint, swaps the bearer token,
  // and clears any school-context impersonation flags. Callers handle
  // navigation and user-facing toasts so this stays UI-agnostic.
  const returnToOriginalRole = useCallback(async () => {
    const response = await api.post('/user-roles/return-to-original', {});
    if (response?.data?.success) {
      sessionStorage.removeItem('nassaq_school_context');
      sessionStorage.removeItem('nassaq_impersonating');
      sessionStorage.removeItem('nassaq_original_token');
      setSchoolContext(null);
      setIsImpersonating(false);
      await updateToken(response.data.access_token);
      return {
        success: true,
        redirectTo: response.data.redirect_to || '/admin',
        message: response.data.message,
      };
    }
    return { success: false };
  }, [api]);
  
  // Enter School Context (Platform Admin previewing a school as its
  // School Principal).
  //
  // Task #511: Previously this only flipped sessionStorage flags and
  // React state — the bearer token stayed a plain platform-admin token
  // with `is_impersonating=False` and no `tenant_id` claim, so the
  // backend's `resolve_school_id()` could not honor the
  // `X-School-Context` header and the four directory endpoints
  // (/students, /teachers, /parents, /classes) silently degraded into
  // unscoped cross-tenant dumps.
  //
  // We now route Command-Center preview through the same hardened
  // /role-switch/switch endpoint the Sidebar role-switcher uses. The
  // axios interceptor handles MFA step-up transparently (HTTP 403 +
  // canonical envelope → passkey assertion → replay), so this call
  // resolves with `{ token, role, school_id, is_impersonating: true,
  // original_role }` once the user has completed any required MFA. The
  // original PA bearer is parked in sessionStorage so exitSchoolContext
  // can restore it without forcing another /auth/me round-trip.
  const enterSchoolContext = async (school, opts = {}) => {
    if (!school?.id) {
      throw new Error('school.id is required');
    }
    const reason = (opts.reason || 'معاينة المدرسة من مركز تحكم المنصة').trim();
    const targetRole = opts.targetRole || 'school_principal';

    const originalToken = localStorage.getItem('nassaq_token');

    const response = await api.post('/role-switch/switch', {
      target_role: targetRole,
      school_id: school.id,
      reason,
    });

    const newToken = response?.data?.token;
    if (!newToken) {
      throw new Error('role-switch/switch returned no token');
    }

    if (originalToken) {
      sessionStorage.setItem('nassaq_original_token', originalToken);
    }

    const ctx = {
      school_id: school.id,
      school_name: school.name,
      school_name_en: school.name_en,
      school_code: school.code,
      original_role: user?.role,
      preview_role: targetRole,
      entered_at: new Date().toISOString(),
    };
    sessionStorage.setItem('nassaq_school_context', JSON.stringify(ctx));
    sessionStorage.setItem('nassaq_impersonating', 'true');
    setSchoolContext(ctx);
    setIsImpersonating(true);

    await updateToken(newToken);
    return ctx;
  };

  // Exit School Context (Return to Platform Admin).
  //
  // Audit 2026-05-25 (H2): previously this was a pure client-side cleanup —
  // sessionStorage was dropped and the parked PA token was reinstated, but
  // the impersonation JWT (issued by /role-switch/switch) was NEVER revoked
  // on the backend and kept passing get_current_user for its full 15-min
  // TTL. We now call the hardened /role-switch/restore endpoint FIRST so
  // the impersonation JTI is server-side revoked. The parked-token client
  // restore remains only as a fallback for the network-failure /
  // no-parked-token branch (e.g. mid-preview reload).
  const exitSchoolContext = async () => {
    const originalToken = sessionStorage.getItem('nassaq_original_token');
    let serverRestoredToken = null;
    try {
      const response = await api.post('/role-switch/restore', {});
      // The hardened restore returns { token: "<new PA access>", ... }.
      // Accept either field name for forward-compat.
      serverRestoredToken =
        response?.data?.token || response?.data?.access_token || null;
    } catch (_serverErr) {
      // Fall through to the parked-token fallback below. Do NOT block
      // the preview-exit UX on a transient network/server error.
    }
    sessionStorage.removeItem('nassaq_school_context');
    sessionStorage.removeItem('nassaq_impersonating');
    sessionStorage.removeItem('nassaq_original_token');
    setSchoolContext(null);
    setIsImpersonating(false);
    const tokenToUse = serverRestoredToken || originalToken;
    if (tokenToUse) {
      try {
        await updateToken(tokenToUse);
      } catch (_e) {
        // updateToken already swallows /auth/me failures and logs them;
        // we must not block the preview-exit UX on a transient network
        // error here.
      }
    } else {
      // Audit 2026-05-25 (H2 hardening): both the server restore failed
      // AND no parked Platform-Admin token is available (e.g. mid-preview
      // reload after session storage was cleared). Do NOT silently keep
      // the impersonation bearer in localStorage — that would diverge UI
      // (exited preview) from token state (still impersonating). Clear
      // the bearer so the route guard sends the user back through login.
      try {
        localStorage.removeItem('nassaq_token');
      } catch (_storageErr) {
        // ignore — already in the worst-case branch
      }
      setToken(null);
      setUser(null);
    }
  };
  
  // Get effective role (simulated or actual)
  const getEffectiveRole = () => {
    if (isImpersonating && schoolContext) {
      return schoolContext.preview_role || 'school_principal'; // Simulate school preview role
    }
    return user?.role;
  };
  
  // Get effective tenant_id (school_id)
  const getEffectiveTenantId = () => {
    if (isImpersonating && schoolContext) {
      return schoolContext.school_id;
    }
    return user?.tenant_id;
  };
  
  // Language preference - Default to Arabic for teachers, use user preference if set
  const preferredLanguage = user?.preferred_language || (user?.role === 'teacher' ? 'ar' : 'ar');
  const isRTL = preferredLanguage === 'ar';

  const updatePreferences = async (preferences) => {
    try {
      await api.put('/auth/preferences', null, { params: preferences });
      setUser((prev) => ({ ...prev, ...preferences }));
      return { success: true };
    } catch (error) {
      return { success: false, error: 'فشل تحديث الإعدادات' };
    }
  };

  // Update user data (for profile updates)
  const updateUser = (updatedData) => {
    setUser((prev) => ({ ...prev, ...updatedData }));
  };

  // Refresh user data from server.
  // Task #195 — also accept the token from localStorage as a fallback so
  // a refresh issued immediately after login() (before the React state
  // has flushed) doesn't return a false-negative null. The login page
  // relies on a null return value to mean "/auth/me genuinely failed".
  const refreshUser = async () => {
    const effectiveToken = token || (typeof window !== 'undefined' ? localStorage.getItem('nassaq_token') : null);
    if (!effectiveToken) return null;
    try {
      const response = await api.get('/auth/me');
      setUser(response.data);
      return response.data;
    } catch (error) {
      console.error('Failed to refresh user:', error);
      return null;
    }
  };

  // Phase 0 §4.B-6 — backend-sourced permission set, lazily fetched and
  // cached for the lifetime of this context. The wizard and any other
  // role-aware UI should read from here instead of hardcoding role →
  // permission mappings.
  const [permissions, setPermissions] = useState(null);
  // In-flight promise shared across concurrent callers. Sidebar, route
  // guards, and pages all call fetchPermissions from mount effects in the
  // same render pass — a React-state "loading" flag can't guard that race
  // (every closure still sees the pre-update value), which is exactly how
  // production traces ended up with /auth/me/permissions fetched twice
  // back-to-back, and the losing caller handed `null` instead of data.
  const permissionsInFlightRef = useRef(null);
  // Generation counter: bumped on force refresh and on any authenticated-
  // identity change. A completion from an older generation must neither
  // populate the cache nor clear the newer generation's in-flight promise —
  // otherwise a slow response fetched under a previous token/tenant/role
  // could overwrite the fresh permission set (stale-authz UI risk).
  const permissionsGenRef = useRef(0);
  // Bearer token the cache / in-flight request was established under.
  // Every token transition in the app (login, refresh, MFA step-up, role
  // switch via updateToken, invite acceptance) writes localStorage
  // 'nassaq_token' synchronously BEFORE the React state/user catch up, so
  // comparing against it at read time closes the window where a caller
  // under a new bearer could be served permissions cached under the old
  // one. The identity effect below stays as defense in depth for
  // user-object-only changes.
  const permissionsTokenRef = useRef(null);
  const invalidatePermissions = useCallback(() => {
    permissionsGenRef.current += 1;
    permissionsInFlightRef.current = null;
    permissionsTokenRef.current = null;
    setPermissions(null);
  }, []);

  // Invalidate the cached permission set whenever the authenticated
  // identity changes (logout, login as someone else, role switch, tenant
  // change). The first anon → user transition is deliberately exempt:
  // the bootstrap permissions fetch runs under this same token, and
  // clearing it here would force every consumer to refetch — recreating
  // the double-fetch this cache exists to prevent.
  const lastPermissionsIdentityRef = useRef(null);
  useEffect(() => {
    const key = user
      ? `${user.id}|${user.tenant_id || ''}|${user.role || ''}|${user.is_switched ? '1' : '0'}`
      : null;
    const prev = lastPermissionsIdentityRef.current;
    lastPermissionsIdentityRef.current = key;
    if (prev !== null && prev !== key) {
      invalidatePermissions();
    }
  }, [user, invalidatePermissions]);

  const fetchPermissions = useCallback(async ({ force = false } = {}) => {
    if (!token) return null;
    // Authoritative bearer for this call: localStorage is written
    // synchronously by every token-transition path, whereas the `token`
    // state and `user` object lag a render / an /auth/me round-trip.
    const bearer = localStorage.getItem('nassaq_token') || token;
    // Pass `force: true` after a tenant_id change (e.g. IT bootstrap)
    // so the cached permission set is discarded and rebuilt against the
    // freshly-set tenant. Without `force`, we keep the cached value to
    // avoid hammering /auth/me/permissions on every UI gate read.
    if (force) {
      invalidatePermissions();
    } else if (permissionsTokenRef.current !== bearer) {
      // Bearer/session transition (role switch, re-login, step-up) that
      // the passive identity effect hasn't observed yet — the cache and
      // any in-flight request belong to the previous auth context.
      invalidatePermissions();
    } else if (permissions) {
      return permissions;
    }
    if (permissionsInFlightRef.current) {
      return permissionsInFlightRef.current;
    }
    const gen = permissionsGenRef.current;
    permissionsTokenRef.current = bearer;
    const request = (async () => {
      try {
        const response = await api.get('/auth/me/permissions');
        if (
          permissionsGenRef.current !== gen ||
          (localStorage.getItem('nassaq_token') || token) !== bearer
        ) {
          // Superseded by a force refresh, identity change, or bearer
          // transition while in flight — the payload belongs to a
          // previous auth context.
          return null;
        }
        setPermissions(response.data);
        return response.data;
      } catch (error) {
        // Failures are not cached: clear the shared promise so the next
        // caller can retry.
        return null;
      } finally {
        // Only clear our own registration — a newer generation may have
        // already replaced it.
        if (permissionsInFlightRef.current === request) {
          permissionsInFlightRef.current = null;
        }
      }
    })();
    permissionsInFlightRef.current = request;
    return request;
  }, [token, api, permissions, invalidatePermissions]);

  // Listen for user-updated events
  useEffect(() => {
    const handleUserUpdate = (event) => {
      if (event.detail) {
        setUser((prev) => ({ ...prev, ...event.detail }));
      }
    };
    
    window.addEventListener('user-updated', handleUserUpdate);
    return () => window.removeEventListener('user-updated', handleUserUpdate);
  }, []);

  const isSwitchedRole = user?.is_switched === true;
  const originalRole = user?.original_role || null;

  const value = {
    user,
    token,
    loading,
    login,
    verifyMfaLogin,
    sendMfaLoginEmailOtp,
    register,
    applyAuthSession,
    logout,
    updateToken,
    updatePreferences,
    updateUser,
    refreshUser,
    clearAuthState,
    permissions,
    fetchPermissions,
    api,
    isAuthenticated: !!user,
    isPlatformAdmin: user?.role === 'platform_admin',
    isSchoolPrincipal: user?.role === 'school_principal' || user?.role === 'school_admin' || (isImpersonating && user?.role === 'platform_admin'),
    isTeacher: user?.role === 'teacher',
    isStudent: user?.role === 'student',
    isParent: user?.role === 'parent',
    isSwitchedRole,
    originalRole,
    schoolContext,
    isImpersonating,
    enterSchoolContext,
    exitSchoolContext,
    returnToOriginalRole,
    getEffectiveRole,
    getEffectiveTenantId,
    preferredLanguage,
    isRTL,
    apiServices: createApiService(api),
    // Task #231 — one-shot post-login workspace lifecycle snapshot.
    // Returns `{ snapshot, consumed }`: `consumed` is `true` whenever
    // the post-login flow actually delivered a snapshot (even when the
    // server resolved `reactivation_banner` to `null`), so callers can
    // skip the redundant follow-up GET in that case. Reads + clears the
    // ref synchronously without touching React state, which makes it
    // safe to call from a `useState` initializer.
    consumeInitialWorkspaceLifecycle: () => {
      const snapshot = initialWorkspaceLifecycleRef.current;
      const consumed = snapshot !== null;
      if (consumed) initialWorkspaceLifecycleRef.current = null;
      return { snapshot, consumed };
    },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
