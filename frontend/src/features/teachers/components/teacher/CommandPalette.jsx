import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  Users,
  School as SchoolIcon,
  BookOpen,
  Sparkles,
  CalendarDays,
  Clock,
  Compass,
  GraduationCap,
  X,
} from 'lucide-react';
import { useAuth } from '@/shared/contexts/AuthContext';
import { useTranslation } from '@/shared/contexts/ThemeContext';

const RECENTS_STORAGE_PREFIX = 'nassaq_cmdk_recents_';
const MAX_RECENTS = 10;
const MIN_QUERY_LEN = 2;
const DEBOUNCE_MS = 180;
const MAX_NAV_RESULTS = 8;

// Roles that hit the school-staff palette endpoint. Independent teachers
// keep their own workspace endpoint; every other role (parent,
// platform_admin, …) gets navigation-only search with no network calls.
const SCHOOL_STAFF_ROLES = [
  'teacher',
  'school_principal',
  'school_admin',
  'school_sub_admin',
];

const CATEGORY_META = {
  navigation: { icon: Compass, labelKey: 'cmdkCategoryNavigation' },
  students: { icon: Users, labelKey: 'cmdkCategoryStudents' },
  classes: { icon: SchoolIcon, labelKey: 'cmdkCategoryClasses' },
  teachers: { icon: GraduationCap, labelKey: 'cmdkCategoryTeachers' },
  subjects: { icon: BookOpen, labelKey: 'cmdkCategorySubjects' },
  lesson_plans: { icon: Sparkles, labelKey: 'cmdkCategoryLessonPlans' },
  calendar_events: { icon: CalendarDays, labelKey: 'cmdkCategoryCalendarEvents' },
};

const CATEGORY_ORDER = [
  'navigation',
  'students',
  'classes',
  'teachers',
  'subjects',
  'lesson_plans',
  'calendar_events',
];

const flattenResults = (payload) => {
  if (!payload) return [];
  const flat = [];
  for (const cat of CATEGORY_ORDER) {
    const arr = Array.isArray(payload[cat]) ? payload[cat] : [];
    for (const item of arr) flat.push(item);
  }
  return flat;
};

const readRecents = (userId) => {
  if (!userId || typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(RECENTS_STORAGE_PREFIX + userId);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.slice(0, MAX_RECENTS) : [];
  } catch (_e) {
    return [];
  }
};

const writeRecent = (userId, item) => {
  if (!userId || !item || typeof window === 'undefined') return;
  try {
    const current = readRecents(userId).filter((r) => r.id !== item.id);
    current.unshift(item);
    localStorage.setItem(
      RECENTS_STORAGE_PREFIX + userId,
      JSON.stringify(current.slice(0, MAX_RECENTS)),
    );
  } catch (_e) {
    /* localStorage full or unavailable — silently ignore */
  }
};

const CommandPalette = ({ effectiveRole, menuItems }) => {
  const { api, user } = useAuth();
  const { t, isRTL } = useTranslation();
  const navigate = useNavigate();

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [recents, setRecents] = useState([]);
  const inputRef = useRef(null);
  const reqIdRef = useRef(0);

  const role = effectiveRole || user?.role || '';
  const searchEndpoint = role === 'independent_teacher'
    ? '/independent-teacher/search'
    : SCHOOL_STAFF_ROLES.includes(role)
      ? '/search/palette'
      : null;

  // ---- global Cmd/Ctrl+K hotkey -----------------------------------------
  useEffect(() => {
    const handler = (e) => {
      const isK = e.key === 'k' || e.key === 'K';
      if (isK && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // ---- listen to a custom open event so the sidebar icon can trigger it -
  useEffect(() => {
    const opener = () => setOpen(true);
    window.addEventListener('nassaq:open-command-palette', opener);
    return () => window.removeEventListener('nassaq:open-command-palette', opener);
  }, []);

  // ---- when opened: focus input + load recents --------------------------
  useEffect(() => {
    if (!open) return;
    setRecents(readRecents(user?.id));
    setQuery('');
    setPayload(null);
    setActiveIndex(0);
    const id = window.setTimeout(() => {
      try { inputRef.current?.focus(); } catch (_e) { /* noop */ }
    }, 30);
    return () => window.clearTimeout(id);
  }, [open, user?.id]);

  // ---- debounced search (roles with a backend palette endpoint only) ----
  useEffect(() => {
    if (!open) return undefined;
    const trimmed = (query || '').trim();
    if (trimmed.length < MIN_QUERY_LEN || !searchEndpoint) {
      setPayload(null);
      setLoading(false);
      return undefined;
    }
    const myReq = ++reqIdRef.current;
    setLoading(true);
    const t1 = window.setTimeout(async () => {
      try {
        const res = await api.get(searchEndpoint, {
          params: { q: trimmed, limit: 8 },
        });
        if (reqIdRef.current === myReq) {
          setPayload(res?.data || null);
          setActiveIndex(0);
        }
      } catch (_e) {
        if (reqIdRef.current === myReq) setPayload(null);
      } finally {
        if (reqIdRef.current === myReq) setLoading(false);
      }
    }, DEBOUNCE_MS);
    return () => window.clearTimeout(t1);
  }, [query, open, api, searchEndpoint]);

  // ---- client-side navigation search over the caller's own sidebar menu -
  const navResults = useMemo(() => {
    const trimmed = (query || '').trim().toLowerCase();
    if (trimmed.length < MIN_QUERY_LEN) return [];
    const out = [];
    for (const item of menuItems || []) {
      if (Array.isArray(item.subItems)) {
        for (const sub of item.subItems) {
          if (sub.href && (sub.label || '').toLowerCase().includes(trimmed)) {
            out.push({
              id: `nav-${sub.href}`,
              category: 'navigation',
              primary: sub.label,
              secondary: item.label || '',
              href: sub.href,
            });
          }
        }
      }
      if (item.href && (item.label || '').toLowerCase().includes(trimmed)) {
        out.push({
          id: `nav-${item.href}`,
          category: 'navigation',
          primary: item.label,
          secondary: '',
          href: item.href,
        });
      }
    }
    return out.slice(0, MAX_NAV_RESULTS);
  }, [query, menuItems]);

  const merged = useMemo(() => {
    if (!navResults.length && !payload) return null;
    return { navigation: navResults, ...(payload || {}) };
  }, [navResults, payload]);

  const flat = useMemo(() => flattenResults(merged), [merged]);
  const showRecents = (query || '').trim().length < MIN_QUERY_LEN;
  const visible = showRecents ? recents : flat;

  const handleSelect = useCallback((item) => {
    if (!item || !item.href) return;
    writeRecent(user?.id, item);
    setOpen(false);
    navigate(item.href);
  }, [navigate, user?.id]);

  const onKeyDown = (e) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      setOpen(false);
      return;
    }
    if (!visible.length) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => (i + 1) % visible.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => (i - 1 + visible.length) % visible.length);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      handleSelect(visible[activeIndex]);
    }
  };

  if (!open) return null;

  // group results by category preserving order, but keep one flat index map
  const grouped = CATEGORY_ORDER
    .map((cat) => ({ cat, items: merged?.[cat] || [] }))
    .filter((g) => Array.isArray(g.items) && g.items.length > 0);

  let runningIndex = -1;
  const indexFor = () => {
    runningIndex += 1;
    return runningIndex;
  };

  const renderRow = (item, idx) => {
    const Icon = CATEGORY_META[item.category]?.icon || Search;
    const isActive = idx === activeIndex;
    return (
      <button
        key={`${item.category}-${item.id}`}
        type="button"
        data-testid={`cmdk-result-${item.id}`}
        onMouseEnter={() => setActiveIndex(idx)}
        onClick={() => handleSelect(item)}
        className={`w-full flex items-center gap-3 px-4 py-2.5 text-start transition-colors ${
          isActive ? 'bg-brand-navy/10' : 'hover:bg-brand-navy/5'
        }`}
      >
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-navy/10 text-brand-navy">
          <Icon className="h-4 w-4" />
        </span>
        <span className="flex-1 min-w-0">
          <span className="block truncate text-sm font-medium text-foreground">
            {item.primary}
          </span>
          {item.secondary && (
            <span className="block truncate text-xs text-muted-foreground">
              {item.secondary}
            </span>
          )}
        </span>
      </button>
    );
  };

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center bg-black/50 backdrop-blur-sm sm:pt-[10vh] sm:px-4"
      onClick={() => setOpen(false)}
      data-testid="cmdk-overlay"
      dir={isRTL ? 'rtl' : 'ltr'}
    >
      <div
        className="w-full h-full sm:h-auto sm:max-w-xl bg-white sm:rounded-2xl shadow-2xl overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
        data-testid="cmdk-panel"
      >
        <div className="flex items-center gap-2 border-b px-4 py-3">
          <Search className="h-5 w-5 text-muted-foreground shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={t('cmdkPlaceholder')}
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground min-w-0"
            data-testid="cmdk-input"
            aria-label={t('cmdkPlaceholder')}
          />
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="hidden sm:inline-flex text-muted-foreground hover:text-foreground"
            data-testid="cmdk-close"
            aria-label={t('close') || 'close'}
          >
            <X className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="sm:hidden inline-flex items-center px-3 py-1.5 rounded-lg bg-brand-navy/10 text-brand-navy text-sm font-medium"
            data-testid="cmdk-close-mobile"
            aria-label={t('close') || 'close'}
          >
            {t('done') || t('close') || 'Done'}
          </button>
        </div>

        <div className="flex-1 sm:flex-none sm:max-h-[50vh] overflow-y-auto">
          {showRecents ? (
            recents.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-muted-foreground" data-testid="cmdk-empty-hint">
                {t('cmdkEmptyHint')}
              </div>
            ) : (
              <div className="py-2">
                <div className="px-4 py-1.5 flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                  <Clock className="h-3.5 w-3.5" />
                  {t('cmdkRecents')}
                </div>
                {recents.map((item) => renderRow(item, indexFor()))}
              </div>
            )
          ) : loading && !merged ? (
            <div className="px-4 py-8 text-center text-sm text-muted-foreground" data-testid="cmdk-loading">
              {t('cmdkLoading')}
            </div>
          ) : flat.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-muted-foreground" data-testid="cmdk-no-results">
              {t('cmdkNoResults')}
            </div>
          ) : (
            <div className="py-2">
              {grouped.map((g) => (
                <div key={g.cat}>
                  <div className="px-4 py-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                    {t(CATEGORY_META[g.cat]?.labelKey)}
                  </div>
                  {g.items.map((item) => renderRow(item, indexFor()))}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between border-t px-4 py-2 text-[11px] text-muted-foreground">
          <span>{t('cmdkHintNav')}</span>
          <span>{t('cmdkHintHotkey')}</span>
        </div>
      </div>
    </div>
  );
};

export default CommandPalette;
