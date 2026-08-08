import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Globe, Sun, Moon, Menu, X, LogIn } from 'lucide-react';
import { useTheme } from '@/shared/contexts/ThemeContext';
import { LandingPage } from '@/features/landing/pages/LandingPage';
import { TeacherExperiencePage } from '@/features/teachers/pages/TeacherExperiencePage';

const TABS = [
  { id: 'home', path: '/', ar: 'الرئيسية', en: 'Home' },
  { id: 'teacher', path: '/for-teachers', ar: 'معلم نسق', en: 'NASSAQ Teacher' },
];

const TAB_COMPONENTS = {
  home: LandingPage,
  teacher: TeacherExperiencePage,
};

const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  typeof window.matchMedia === 'function' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export const PublicShell = () => {
  const { isRTL, toggleLanguage, toggleTheme, isDark } = useTheme();
  const location = useLocation();
  const navigate = useNavigate();

  const activeId = location.pathname === '/for-teachers' ? 'teacher' : 'home';
  const tabRefs = useRef({});
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const mobileMenuRef = useRef(null);
  const mobileTriggerRef = useRef(null);

  // Track which tabs have been visited so we lazy-mount the second one only
  // after the user first navigates to it (avoids paying for both pages on
  // the very first paint).
  const [visited, setVisited] = useState(() => ({
    home: activeId === 'home',
    teacher: activeId === 'teacher',
  }));
  useEffect(() => {
    setVisited((prev) => (prev[activeId] ? prev : { ...prev, [activeId]: true }));
  }, [activeId]);

  // Save per-tab window scroll position so switching back restores where the
  // user was instead of jumping to top. The previous behaviour (smooth
  // scroll-to-top on every pathname change) is preserved when entering a
  // tab for the first time, because the saved value defaults to 0.
  const scrollPositions = useRef({ home: 0, teacher: 0 });
  const prevActiveRef = useRef(activeId);
  useLayoutEffect(() => {
    const prev = prevActiveRef.current;
    if (prev === activeId) return;
    if (typeof window !== 'undefined') {
      scrollPositions.current[prev] = window.scrollY;
      const target = scrollPositions.current[activeId] ?? 0;
      window.scrollTo({ top: target, behavior: 'auto' });
    }
    prevActiveRef.current = activeId;
  }, [activeId]);

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!mobileMenuOpen) return undefined;
    const handleKey = (e) => {
      if (e.key === 'Escape') {
        setMobileMenuOpen(false);
        mobileTriggerRef.current?.focus();
      }
    };
    const handleClick = (e) => {
      if (
        mobileMenuRef.current &&
        !mobileMenuRef.current.contains(e.target) &&
        !mobileTriggerRef.current?.contains(e.target)
      ) {
        setMobileMenuOpen(false);
      }
    };
    document.addEventListener('keydown', handleKey);
    document.addEventListener('mousedown', handleClick);
    return () => {
      document.removeEventListener('keydown', handleKey);
      document.removeEventListener('mousedown', handleClick);
    };
  }, [mobileMenuOpen]);

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

  const crossfadeDuration = prefersReducedMotion() ? 0 : 0.2;

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
              className="hidden sm:inline-flex font-tajawal text-xs sm:text-sm font-medium px-2.5 sm:px-4 py-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
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

            {/* Mobile-only "more" menu trigger */}
            <div className="relative sm:hidden">
              <button
                ref={mobileTriggerRef}
                type="button"
                onClick={() => setMobileMenuOpen((open) => !open)}
                className="inline-flex items-center justify-center h-9 w-9 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-turquoise focus-visible:ring-offset-2"
                aria-label={isRTL ? 'القائمة' : 'Menu'}
                aria-expanded={mobileMenuOpen}
                aria-controls="public-shell-mobile-menu"
                aria-haspopup="true"
                data-testid="public-shell-mobile-menu-trigger"
              >
                {mobileMenuOpen
                  ? <X className="h-5 w-5" strokeWidth={1.5} aria-hidden="true" />
                  : <Menu className="h-5 w-5" strokeWidth={1.5} aria-hidden="true" />}
              </button>

              <AnimatePresence>
                {mobileMenuOpen && (
                  <motion.div
                    ref={mobileMenuRef}
                    id="public-shell-mobile-menu"
                    role="menu"
                    initial={{ opacity: 0, y: -6, scale: 0.98 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -6, scale: 0.98 }}
                    transition={{ duration: 0.16, ease: 'easeOut' }}
                    className={`absolute top-full mt-2 ${isRTL ? 'start-0' : 'end-0'} w-56 rounded-xl border border-slate-200 bg-white shadow-lg ring-1 ring-black/5 p-1.5 z-50`}
                    data-testid="public-shell-mobile-menu"
                  >
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => { toggleLanguage(); setMobileMenuOpen(false); }}
                      className="flex w-full items-center gap-3 px-3 py-2.5 rounded-lg text-start font-tajawal text-sm text-slate-700 hover:bg-slate-100 transition-colors"
                      data-testid="mobile-language-toggle"
                    >
                      <Globe className="h-4 w-4 text-slate-500" strokeWidth={1.5} aria-hidden="true" />
                      <span>{isRTL ? 'English' : 'العربية'}</span>
                    </button>
                    <button
                      type="button"
                      role="menuitem"
                      onClick={() => { toggleTheme(); setMobileMenuOpen(false); }}
                      className="flex w-full items-center gap-3 px-3 py-2.5 rounded-lg text-start font-tajawal text-sm text-slate-700 hover:bg-slate-100 transition-colors"
                      data-testid="mobile-theme-toggle"
                    >
                      {isDark
                        ? <Sun className="h-4 w-4 text-slate-500" strokeWidth={1.5} aria-hidden="true" />
                        : <Moon className="h-4 w-4 text-slate-500" strokeWidth={1.5} aria-hidden="true" />}
                      <span>
                        {isDark
                          ? (isRTL ? 'الوضع الفاتح' : 'Light mode')
                          : (isRTL ? 'الوضع الداكن' : 'Dark mode')}
                      </span>
                    </button>
                    <div className="my-1 h-px bg-slate-100" aria-hidden="true" />
                    <Link
                      to="/login"
                      role="menuitem"
                      onClick={() => setMobileMenuOpen(false)}
                      className="flex w-full items-center gap-3 px-3 py-2.5 rounded-lg font-tajawal text-sm text-slate-700 hover:bg-slate-100 transition-colors"
                      data-testid="mobile-login-link"
                    >
                      <LogIn className="h-4 w-4 text-slate-500" strokeWidth={1.5} aria-hidden="true" />
                      <span>{isRTL ? 'دخول' : 'Log in'}</span>
                    </Link>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </nav>
      </header>

      {/* Persistent tab panels.
          Both pages stay mounted after first visit so switching between
          /  and /for-teachers preserves scroll position, autoplaying
          carousels and the typed-text animation, and the crossfade is
          driven by opacity rather than a remount. The inactive panel is
          taken out of layout via position:absolute so window scrollHeight
          tracks the active panel and there's no double-scroll. */}
      <div
        id="public-shell-panel"
        role="tabpanel"
        aria-labelledby={`public-tab-${activeId}`}
        className="relative flex-1"
      >
        {TABS.map((tab) => {
          if (!visited[tab.id]) return null;
          const isActive = tab.id === activeId;
          const Component = TAB_COMPONENTS[tab.id];
          return (
            <div
              key={tab.id}
              data-testid={`public-tab-panel-${tab.id}`}
              data-active={isActive ? 'true' : 'false'}
              aria-hidden={!isActive}
              inert={!isActive}
              className={isActive ? 'relative' : 'absolute inset-0 overflow-hidden pointer-events-none'}
              style={{
                opacity: isActive ? 1 : 0,
                transition: `opacity ${crossfadeDuration}s ease-out`,
              }}
            >
              <Component />
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default PublicShell;
