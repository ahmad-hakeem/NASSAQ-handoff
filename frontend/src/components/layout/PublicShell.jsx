import { useEffect, useRef } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Globe, Sun, Moon } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';

const TABS = [
  { id: 'home', path: '/', ar: 'الرئيسية', en: 'Home' },
  { id: 'teacher', path: '/for-teachers', ar: 'معلم نسق', en: 'NASSAQ Teacher' },
];

export const PublicShell = ({ children }) => {
  const { isRTL, toggleLanguage, toggleTheme, isDark } = useTheme();
  const location = useLocation();
  const navigate = useNavigate();

  const activeId = location.pathname === '/for-teachers' ? 'teacher' : 'home';
  const tabRefs = useRef({});
  const isFirstRender = useRef(true);

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    if (typeof window !== 'undefined') {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }, [location.pathname]);

  const goToTab = (path) => {
    if (location.pathname !== path) navigate(path);
  };

  const handleKeyDown = (e, idx) => {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    e.preventDefault();
    const forward = isRTL ? e.key === 'ArrowLeft' : e.key === 'ArrowRight';
    const nextIdx = forward
      ? (idx + 1) % TABS.length
      : (idx - 1 + TABS.length) % TABS.length;
    const nextTab = TABS[nextIdx];
    tabRefs.current[nextTab.id]?.focus();
    goToTab(nextTab.path);
  };

  const registerHref = activeId === 'teacher' ? '/teacher-register' : '/register';

  return (
    <div
      className="min-h-screen flex flex-col"
      dir={isRTL ? 'rtl' : 'ltr'}
      data-testid="public-shell"
    >
      <header
        className="sticky top-0 z-50 bg-white/90 backdrop-blur-md border-b border-slate-200"
        data-testid="public-shell-header"
      >
        <nav className="max-w-7xl mx-auto px-4 sm:px-6 py-3 sm:py-4 flex items-center justify-between gap-3">
          {/* Logo */}
          <Link
            to="/"
            className="flex items-center gap-2 shrink-0"
            data-testid="navbar-logo"
            aria-label={isRTL ? 'نَسَّق الرئيسية' : 'NASSAQ Home'}
          >
            <img
              src="/nassaq-logo.png"
              alt={isRTL ? 'شعار نَسَّق' : 'NASSAQ logo'}
              className="w-10 h-10 rounded-xl object-cover shadow-md ring-1 ring-brand-navy/10"
            />
            <div className="hidden sm:flex flex-col leading-tight">
              <span className="font-cairo font-bold text-brand-navy text-lg">
                {isRTL ? 'نَسَّق' : 'NASSAQ'}
              </span>
              <span className="font-tajawal text-[10px] text-slate-500">
                {isRTL ? 'من البيانات للقرار' : 'From data to decisions'}
              </span>
            </div>
          </Link>

          {/* Two-tab segmented switcher */}
          <div
            role="tablist"
            aria-label={isRTL ? 'تبويبات نَسَّق' : 'NASSAQ sections'}
            className="relative inline-flex items-center rounded-full border border-slate-200/70 bg-white/85 backdrop-blur-md shadow-sm p-1"
            data-testid="public-tab-switcher"
          >
            {TABS.map((tab, idx) => {
              const isActive = tab.id === activeId;
              return (
                <button
                  key={tab.id}
                  id={`public-tab-${tab.id}`}
                  ref={(el) => { tabRefs.current[tab.id] = el; }}
                  role="tab"
                  type="button"
                  tabIndex={isActive ? 0 : -1}
                  aria-selected={isActive}
                  onClick={() => goToTab(tab.path)}
                  onKeyDown={(e) => handleKeyDown(e, idx)}
                  aria-controls="public-shell-panel"
                  className="relative isolate font-cairo text-xs sm:text-sm font-semibold px-3 sm:px-6 py-1.5 sm:py-2 rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-turquoise focus-visible:ring-offset-2"
                  data-testid={`public-tab-${tab.id}`}
                >
                  {isActive && (
                    <motion.span
                      layoutId="public-tab-active-pill"
                      className="absolute inset-0 -z-10 rounded-full bg-brand-navy shadow"
                      transition={{ type: 'spring', stiffness: 350, damping: 30 }}
                      aria-hidden="true"
                    />
                  )}
                  <span className={isActive ? 'text-white' : 'text-slate-600 hover:text-brand-navy transition-colors'}>
                    {isRTL ? tab.ar : tab.en}
                  </span>
                </button>
              );
            })}
          </div>

          {/* End actions */}
          <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
            <button
              type="button"
              onClick={toggleLanguage}
              className="hidden sm:inline-flex items-center justify-center h-9 w-9 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
              data-testid="language-toggle"
              aria-label={isRTL ? 'تغيير اللغة' : 'Toggle language'}
            >
              <Globe className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={toggleTheme}
              className="hidden sm:inline-flex items-center justify-center h-9 w-9 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
              data-testid="theme-toggle"
              aria-label={isDark ? (isRTL ? 'الوضع الفاتح' : 'Light mode') : (isRTL ? 'الوضع الداكن' : 'Dark mode')}
            >
              {isDark
                ? <Sun className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />
                : <Moon className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />}
            </button>
            <Link
              to="/login"
              className="inline-flex font-tajawal text-xs sm:text-sm font-medium px-2.5 sm:px-4 py-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
              data-testid="login-link"
            >
              {isRTL ? 'دخول' : 'Log in'}
            </Link>
            <Link
              to={registerHref}
              className="font-tajawal text-xs sm:text-sm font-medium px-3 sm:px-6 py-2 sm:py-2.5 rounded-lg bg-brand-navy text-white hover:bg-brand-navy-light hover:text-white shadow-sm hover:shadow-md active:scale-95 transition-all"
              data-testid="register-link"
            >
              {isRTL ? 'ابدأ مجاناً' : 'Start free'}
            </Link>
          </div>
        </nav>
      </header>

      <AnimatePresence mode="wait" initial={false}>
        <motion.main
          key={location.pathname}
          id="public-shell-panel"
          role="tabpanel"
          aria-labelledby={`public-tab-${activeId}`}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.28, ease: 'easeOut' }}
          className="flex-1"
        >
          {children}
        </motion.main>
      </AnimatePresence>
    </div>
  );
};

export default PublicShell;
