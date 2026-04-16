import { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { createApiService } from '../services/apiClient';

const AuthContext = createContext(null);

const API_URL = process.env.REACT_APP_BACKEND_URL;

const RETRY_STATUS_CODES = new Set([502, 503]);
const MAX_RETRIES = 2;
const BASE_DELAY_MS = 500;

let refreshPromise = null;

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
      const config = error.config || {};
      const retryCount = config._retryCount || 0;
      const status = error.response?.status;
      const isGet = (config.method || '').toUpperCase() === 'GET';
      const isTransient = !error.response || RETRY_STATUS_CODES.has(status);

      if (isGet && isTransient && retryCount < MAX_RETRIES) {
        return retryRequest(api, config, retryCount);
      }

      if (status === 401 && !config.url?.includes('/auth/me') && !config.url?.includes('/auth/login') && !config.url?.includes('/auth/refresh')) {
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
        const retryAfter = error.response?.headers?.['retry-after'];
        const parsed = retryAfter ? parseInt(retryAfter, 10) : NaN;
        const secs = Number.isFinite(parsed) && parsed > 0 ? parsed : 30;
        toast.error(`طلبات كثيرة — يرجى الانتظار ${secs} ثانية`);
        return Promise.reject(error);
      }

      if (status >= 500 || !error.response) {
        const msg = !error.response
          ? 'تعذر الاتصال بالخادم — تحقق من الاتصال بالإنترنت'
          : `خطأ في الخادم (${status}) — يرجى المحاولة لاحقاً`;
        toast.error(msg);
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
        toast.error('تعذر تحميل بيانات المستخدم');
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
      const { access_token, refresh_token: refreshToken, user: userData } = response.data;
      
      localStorage.setItem('nassaq_token', access_token);
      setToken(access_token);
      setUser(userData);

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
      let message = 'فشل تسجيل الدخول';
      if (error.response?.data?.detail) {
        message = error.response.data.detail;
      } else if (error.response?.status === 401) {
        message = 'بيانات الدخول غير صحيحة';
      } else if (error.response?.status === 404) {
        message = 'الحساب غير موجود';
      } else if (!error.response) {
        message = 'خطأ في الاتصال بالخادم';
      }
      return { success: false, error: message };
    }
  };

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

  const logout = useCallback(() => {
    try {
      const currentToken = localStorage.getItem('nassaq_token');
      if (currentToken) {
        axios.post(`${API_URL}/api/auth/logout`, null, {
          headers: { Authorization: `Bearer ${currentToken}` }
        }).catch(() => {});
      }
    } catch {}
    clearAllAuthTokens();
    sessionStorage.removeItem('nassaq_school_context');
    sessionStorage.removeItem('nassaq_impersonating');
    setToken(null);
    setUser(null);
    setSchoolContext(null);
    setIsImpersonating(false);
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
  
  // Enter School Context (Platform Admin simulation of School Manager)
  const enterSchoolContext = (school) => {
    const ctx = {
      school_id: school.id,
      school_name: school.name,
      school_name_en: school.name_en,
      school_code: school.code,
      original_role: user?.role,
      entered_at: new Date().toISOString()
    };
    sessionStorage.setItem('nassaq_school_context', JSON.stringify(ctx));
    sessionStorage.setItem('nassaq_impersonating', 'true');
    setSchoolContext(ctx);
    setIsImpersonating(true);
    return ctx;
  };
  
  // Exit School Context (Return to Platform Admin)
  const exitSchoolContext = () => {
    sessionStorage.removeItem('nassaq_school_context');
    sessionStorage.removeItem('nassaq_impersonating');
    setSchoolContext(null);
    setIsImpersonating(false);
  };
  
  // Get effective role (simulated or actual)
  const getEffectiveRole = () => {
    if (isImpersonating && schoolContext) {
      return 'school_principal'; // Simulate School Manager role
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

  // Refresh user data from server
  const refreshUser = async () => {
    if (!token) return;
    try {
      const response = await api.get('/auth/me');
      setUser(response.data);
      return response.data;
    } catch (error) {
      console.error('Failed to refresh user:', error);
      return null;
    }
  };

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
    register,
    logout,
    updateToken,
    updatePreferences,
    updateUser,
    refreshUser,
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
    getEffectiveRole,
    getEffectiveTenantId,
    preferredLanguage,
    isRTL,
    apiServices: createApiService(api),
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
