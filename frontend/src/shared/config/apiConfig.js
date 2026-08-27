/**
 * Centralized API & Environment Configuration
 *
 * Automatically resolves the correct Backend Base URL:
 * 1. Environment Variable: `process.env.REACT_APP_BACKEND_URL` (if explicitly configured)
 * 2. Runtime Domain Detection (automatically adapts when deployed to UAT vs Production):
 *    - `uat.nassaqapp.com` -> 'https://uat.nassaqapp.com'
 *    - `app.nassaqapp.com` / `nassaqapp.com` -> 'https://app.nassaqapp.com' (or current origin)
 *    - `localhost` / `127.0.0.1` -> Uses `process.env.REACT_APP_BACKEND_URL` or defaults to 'http://localhost:8000'
 */

export const getBackendOrigin = () => {
  // If explicitly configured via environment variable, honor it
  if (process.env.REACT_APP_BACKEND_URL) {
    return process.env.REACT_APP_BACKEND_URL.replace(/\/+$/, '');
  }

  // Runtime domain auto-detection in browser
  if (typeof window !== 'undefined' && window.location) {
    const hostname = window.location.hostname;

    // UAT environment
    if (hostname.includes('uat.nassaqapp.com')) {
      return 'https://uat.nassaqapp.com';
    }

    // Production environment
    if (hostname.includes('nassaqapp.com')) {
      return window.location.origin;
    }
  }

  // Local development fallback
  return 'http://localhost:8000';
};

export const getApiBaseUrl = () => {
  const origin = getBackendOrigin();
  return `${origin}/api`;
};

export const API_URL = getBackendOrigin();
export const API_BASE_URL = getApiBaseUrl();

export default {
  getBackendOrigin,
  getApiBaseUrl,
  API_URL,
  API_BASE_URL,
};
