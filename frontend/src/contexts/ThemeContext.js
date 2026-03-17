import { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';

const ThemeContext = createContext(null);

// Helper function to apply language direction to DOM
const applyLanguageDirection = (lang) => {
  const root = window.document.documentElement;
  const body = window.document.body;
  const dir = lang === 'ar' ? 'rtl' : 'ltr';
  
  // Apply to HTML element
  root.dir = dir;
  root.lang = lang;
  root.setAttribute('data-language', lang);
  root.setAttribute('data-direction', dir);
  
  // Apply to body element
  body.dir = dir;
  body.setAttribute('data-language', lang);
  body.setAttribute('data-direction', dir);
  
  // Update CSS custom properties
  root.style.setProperty('--direction', dir);
  root.style.setProperty('--text-align', lang === 'ar' ? 'right' : 'left');
  root.style.setProperty('--text-align-opposite', lang === 'ar' ? 'left' : 'right');
  
  // Store in localStorage
  localStorage.setItem('nassaq_language', lang);
  
  // Update document title
  document.title = 'NASSAQ | نَسَّق';
  
  return dir;
};

// Helper function to apply theme to DOM
const applyTheme = (theme) => {
  const root = window.document.documentElement;
  root.classList.remove('light', 'dark');
  root.classList.add(theme);
  root.setAttribute('data-theme', theme);
  localStorage.setItem('nassaq_theme', theme);
};

export const ThemeProvider = ({ children }) => {
  // Initialize state from localStorage
  const [theme, setTheme] = useState(() => {
    const stored = localStorage.getItem('nassaq_theme');
    return stored || 'light';
  });

  const [language, setLanguage] = useState(() => {
    const stored = localStorage.getItem('nassaq_language');
    return stored || 'ar';
  });

  // Force re-render counter to ensure all components update
  const [, setForceUpdate] = useState(0);

  // Apply theme and language on mount and changes
  useEffect(() => {
    applyTheme(theme);
    applyLanguageDirection(language);
  }, [theme, language]);

  // Apply on initial mount
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

  const toggleTheme = useCallback(() => {
    setTheme((prev) => {
      const newTheme = prev === 'light' ? 'dark' : 'light';
      applyTheme(newTheme);
      const token = localStorage.getItem('nassaq_token');
      if (token) {
        const baseUrl = (window.location.hostname === 'localhost' ? '' : '') + '/api';
        fetch(`${baseUrl}/auth/preferences?preferred_theme=${newTheme}`, {
          method: 'PUT',
          headers: { 'Authorization': `Bearer ${token}` },
        }).catch(() => {});
      }
      return newTheme;
    });
  }, []);

  const toggleLanguage = useCallback(() => {
    setLanguage((prev) => {
      const newLang = prev === 'ar' ? 'en' : 'ar';
      applyLanguageDirection(newLang);
      // Force re-render of all consuming components
      setForceUpdate(n => n + 1);
      return newLang;
    });
  }, []);

  // Memoize the context value to prevent unnecessary re-renders
  const value = useMemo(() => ({
    theme,
    setTheme,
    toggleTheme,
    language,
    setLanguage,
    toggleLanguage,
    isRTL: language === 'ar',
    isDark: theme === 'dark',
    direction: language === 'ar' ? 'rtl' : 'ltr',
  }), [theme, language, toggleTheme, toggleLanguage]);

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
};

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};

// Translation helper
export const translations = {
  ar: {
    // Navigation
    home: 'الرئيسية',
    features: 'المميزات',
    pricing: 'الأسعار',
    contact: 'تواصل معنا',
    login: 'تسجيل الدخول',
    register: 'إنشاء حساب',
    logout: 'تسجيل الخروج',
    dashboard: 'لوحة التحكم',
    
    // Landing Page
    heroTitle: 'نظام إدارة المدارس الذكي',
    heroSubtitle: 'منصة متكاملة مدعومة بالذكاء الاصطناعي لإدارة العملية التعليمية بكفاءة عالية',
    getStarted: 'ابدأ الآن',
    learnMore: 'اعرف المزيد',
    
    // Features
    aiAssistant: 'المساعد الذكي',
    aiAssistantDesc: 'حكيم - مساعدك الذكي لتحليل البيانات وتقديم التوصيات',
    schoolManagement: 'إدارة المدارس',
    schoolManagementDesc: 'إدارة شاملة للمدارس والفصول والمواد الدراسية',
    userManagement: 'إدارة المستخدمين',
    userManagementDesc: 'إدارة المعلمين والطلاب وأولياء الأمور بسهولة',
    analytics: 'التحليلات',
    analyticsDesc: 'تقارير وإحصائيات تفصيلية لمتابعة الأداء',
    
    // Auth
    email: 'البريد الإلكتروني',
    password: 'كلمة المرور',
    fullName: 'الاسم الكامل',
    forgotPassword: 'نسيت كلمة المرور؟',
    noAccount: 'ليس لديك حساب؟',
    hasAccount: 'لديك حساب بالفعل؟',
    
    // Dashboard
    overview: 'نظرة عامة',
    schools: 'المدارس',
    users: 'المستخدمين',
    settings: 'الإعدادات',
    totalSchools: 'إجمالي المدارس',
    totalStudents: 'إجمالي الطلاب',
    totalTeachers: 'إجمالي المعلمين',
    activeSchools: 'المدارس النشطة',
    
    // Common
    save: 'حفظ',
    cancel: 'إلغاء',
    edit: 'تعديل',
    delete: 'حذف',
    add: 'إضافة',
    search: 'بحث',
    loading: 'جاري التحميل...',
    error: 'حدث خطأ',
    success: 'تم بنجاح',
  },
  en: {
    // Navigation
    home: 'Home',
    features: 'Features',
    pricing: 'Pricing',
    contact: 'Contact',
    login: 'Login',
    register: 'Register',
    logout: 'Logout',
    dashboard: 'Dashboard',
    
    // Landing Page
    heroTitle: 'Smart School Management System',
    heroSubtitle: 'AI-powered integrated platform for efficient educational management',
    getStarted: 'Get Started',
    learnMore: 'Learn More',
    
    // Features
    aiAssistant: 'AI Assistant',
    aiAssistantDesc: 'Hakim - Your intelligent assistant for data analysis and recommendations',
    schoolManagement: 'School Management',
    schoolManagementDesc: 'Comprehensive management of schools, classes, and subjects',
    userManagement: 'User Management',
    userManagementDesc: 'Easily manage teachers, students, and parents',
    analytics: 'Analytics',
    analyticsDesc: 'Detailed reports and statistics to track performance',
    
    // Auth
    email: 'Email',
    password: 'Password',
    fullName: 'Full Name',
    forgotPassword: 'Forgot Password?',
    noAccount: "Don't have an account?",
    hasAccount: 'Already have an account?',
    
    // Dashboard
    overview: 'Overview',
    schools: 'Schools',
    users: 'Users',
    settings: 'Settings',
    totalSchools: 'Total Schools',
    totalStudents: 'Total Students',
    totalTeachers: 'Total Teachers',
    activeSchools: 'Active Schools',
    
    // Common
    save: 'Save',
    cancel: 'Cancel',
    edit: 'Edit',
    delete: 'Delete',
    add: 'Add',
    search: 'Search',
    loading: 'Loading...',
    error: 'An error occurred',
    success: 'Success',
  },
};

export const useTranslation = () => {
  const { language } = useTheme();
  
  const t = (key) => {
    return translations[language]?.[key] || translations.ar[key] || key;
  };
  
  return { t, language };
};
