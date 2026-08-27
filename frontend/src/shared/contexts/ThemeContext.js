import { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import { API_BASE_URL } from '@/shared/config/apiConfig';
import arLocale from '@/locales/ar.json';
import enLocale from '@/locales/en.json';

export const ThemeContext = createContext(null);

const locales = { ar: arLocale, en: enLocale };

const applyLanguageDirection = (lang) => {
  const root = window.document.documentElement;
  const body = window.document.body;
  const dir = lang === 'ar' ? 'rtl' : 'ltr';

  root.dir = dir;
  root.lang = lang;
  root.setAttribute('data-language', lang);
  root.setAttribute('data-direction', dir);

  body.dir = dir;
  body.setAttribute('data-language', lang);
  body.setAttribute('data-direction', dir);

  root.style.setProperty('--direction', dir);
  root.style.setProperty('--text-align', lang === 'ar' ? 'right' : 'left');
  root.style.setProperty('--text-align-opposite', lang === 'ar' ? 'left' : 'right');

  localStorage.setItem('nassaq_language', lang);

  document.title = 'NASSAQ | نَسَّق';

  // The skip-to-content link lives in the static index.html shell (rendered
  // before React boots), so it must be re-localized here on every language
  // change. See parent-dropdowns audit Finding 5.
  const skipLink = window.document.querySelector('.skip-link');
  if (skipLink) {
    const skipText = (locales[lang] && locales[lang].skipToContent)
      || locales.ar.skipToContent;
    if (skipText) skipLink.textContent = skipText;
  }

  return dir;
};

const applyTheme = (theme) => {
  const root = window.document.documentElement;
  root.classList.remove('light', 'dark');
  root.classList.add(theme);
  root.setAttribute('data-theme', theme);
  localStorage.setItem('nassaq_theme', theme);
};

export const ThemeProvider = ({ children }) => {
  const [theme, setTheme] = useState(() => {
    const stored = localStorage.getItem('nassaq_theme');
    return stored || 'light';
  });

  const [language, setLanguage] = useState(() => {
    const stored = localStorage.getItem('nassaq_language');
    return stored || 'ar';
  });

  const [, setForceUpdate] = useState(0);

  useEffect(() => {
    applyTheme(theme);
    applyLanguageDirection(language);
  }, [theme, language]);

  useEffect(() => {
    const storedLang = localStorage.getItem('nassaq_language') || 'ar';
    const storedTheme = localStorage.getItem('nassaq_theme') || 'light';

    applyTheme(storedTheme);
    applyLanguageDirection(storedLang);

    setTheme(storedTheme);
    setLanguage(storedLang);
  }, []);

  useEffect(() => {
    const handleThemeSync = (e) => {
      if (e.detail?.theme) {
        setTheme(e.detail.theme);
        applyTheme(e.detail.theme);
      }
    };
    window.addEventListener('nassaq-theme-sync', handleThemeSync);
    return () => window.removeEventListener('nassaq-theme-sync', handleThemeSync);
  }, []);

  useEffect(() => {
    const handleLangSync = (e) => {
      const newLang = e.detail?.language;
      if (newLang && (newLang === 'ar' || newLang === 'en')) {
        setLanguage((current) => {
          if (current !== newLang) {
            applyLanguageDirection(newLang);
            setForceUpdate((n) => n + 1);
            return newLang;
          }
          return current;
        });
      }
    };
    window.addEventListener('nassaq-language-sync', handleLangSync);
    return () => window.removeEventListener('nassaq-language-sync', handleLangSync);
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => {
      const newTheme = prev === 'light' ? 'dark' : 'light';
      applyTheme(newTheme);
      const token = localStorage.getItem('nassaq_token');
      if (token) {
        fetch(`${API_BASE_URL}/auth/preferences?preferred_theme=${newTheme}`, {
          method: 'PUT',
          headers: { 'Authorization': `Bearer ${token}` },
        }).catch(() => {});
      }
      return newTheme;
    });
  }, []);

  const setLanguageAndApply = useCallback((newLang) => {
    if (newLang !== 'ar' && newLang !== 'en') return;
    setLanguage(newLang);
    applyLanguageDirection(newLang);
    setForceUpdate((n) => n + 1);
    window.dispatchEvent(new CustomEvent('nassaq-language-sync', { detail: { language: newLang } }));
    const token = localStorage.getItem('nassaq_token');
    if (token) {
      fetch(`${API_BASE_URL}/auth/preferences?preferred_language=${newLang}`, {
        method: 'PUT',
        headers: { 'Authorization': `Bearer ${token}` },
      }).catch(() => {});
    }
  }, []);

  const toggleLanguage = useCallback(() => {
    setLanguage((prev) => {
      const newLang = prev === 'ar' ? 'en' : 'ar';
      applyLanguageDirection(newLang);
      setForceUpdate((n) => n + 1);
      window.dispatchEvent(new CustomEvent('nassaq-language-sync', { detail: { language: newLang } }));
      const token = localStorage.getItem('nassaq_token');
      if (token) {
        fetch(`${API_BASE_URL}/auth/preferences?preferred_language=${newLang}`, {
          method: 'PUT',
          headers: { 'Authorization': `Bearer ${token}` },
        }).catch(() => {});
      }
      return newLang;
    });
  }, []);

  const value = useMemo(() => ({
    theme,
    setTheme,
    toggleTheme,
    language,
    setLanguage: setLanguageAndApply,
    toggleLanguage,
    isRTL: language === 'ar',
    isDark: theme === 'dark',
    dir: language === 'ar' ? 'rtl' : 'ltr',
    direction: language === 'ar' ? 'rtl' : 'ltr',
  }), [theme, language, toggleTheme, toggleLanguage, setLanguageAndApply]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
};

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};

export const useTranslation = () => {
  const { language, isRTL, dir, direction } = useTheme();

  const t = useCallback((key, params) => {
    let text = locales[language]?.[key] || locales.ar[key] || key;
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        text = text.replace(new RegExp(`\\{\\{${k}\\}\\}`, 'g'), v);
        text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
      });
    }
    return text;
  }, [language]);

  const localizedValue = useCallback((item, field) => {
    if (!item) return '';
    if (language === 'en') {
      return item[`${field}_en`] || item[`${field}_ar`] || item[field] || '';
    }
    return item[`${field}_ar`] || item[field] || item[`${field}_en`] || '';
  }, [language]);

  return {
    t,
    language,
    isRTL: isRTL !== undefined ? isRTL : language === 'ar',
    dir: dir || (language === 'ar' ? 'rtl' : 'ltr'),
    direction: direction || (language === 'ar' ? 'rtl' : 'ltr'),
    localizedValue,
  };
};

export const translations = locales;

