/**
 * Centralized API & Environment Configuration
 *
 * Automatically resolves the correct Backend Base URL:
 * 1. Local Development (localhost / 127.0.0.1):
 *    - Returns '' so requests go to `/api` and are routed through setupProxy.js.
 *    - setupProxy.js securely proxies to `REACT_APP_BACKEND_URL` (UAT, Production, or localhost:8000)
 *      with `changeOrigin: true` to bypass browser CORS preflight restrictions.
 * 2. Deployed Environments (UAT / Production):
 *    - Dynamically detects the current origin (`https://uat.nassaqapp.com`, `https://app.nassaqapp.com`, etc.)
 *    - Uses same-origin `/api` endpoints without needing code modifications.
 */

export const isLocalhost = () => {
  if (typeof window === 'undefined' || !window.location) return true;
  const hostname = window.location.hostname;
  return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '0.0.0.0';
};

export const getBackendOrigin = () => {
  // If running locally in browser, use relative origin so requests pass through setupProxy.js (CORS-free)
  if (typeof window !== 'undefined' && isLocalhost()) {
    return '';
  }

  // If running in production/UAT browser, use the current origin
  if (typeof window !== 'undefined' && window.location?.origin) {
    return window.location.origin.replace(/\/+$/, '');
  }

  // Build-time / SSR / fallback
  if (process.env.REACT_APP_BACKEND_URL) {
    return process.env.REACT_APP_BACKEND_URL.replace(/\/+$/, '');
  }

  return '';
};

export const getApiBaseUrl = () => {
  const origin = getBackendOrigin();
  return origin ? `${origin}/api` : '/api';
};

export const API_URL = getBackendOrigin();
export const API_BASE_URL = getApiBaseUrl();

export default {
  isLocalhost,
  getBackendOrigin,
  getApiBaseUrl,
  API_URL,
  API_BASE_URL,
};
