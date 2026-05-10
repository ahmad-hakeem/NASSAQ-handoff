/**
 * ShellStudentSwitcher — Task #146
 *
 * Mounted once in the Parent Portal shell (PortalLayout / ParentShell)
 * so every parent page sees the same control. Drives the global
 * ParentActiveStudentContext.
 *
 * Behavior:
 *   - 0 children  → renders nothing (empty state handled inside pages)
 *   - 1 child     → compact non-interactive chip showing the child
 *   - 2+ children → popover dropdown with avatar + name + grade/class
 *
 * URL sync on switch:
 *   - On `/parent/child/:childId/...` legacy routes → rewrite the path
 *     so the current page re-fetches against the new child without a reload.
 *   - On `/parent/children`                         → write `?child=<id>`.
 *   - Anywhere else                                  → context-only update.
 *
 * No localStorage. RTL-safe. Handles missing avatars and long Arabic names.
 */

import React, { useState } from 'react';
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { Popover, PopoverContent, PopoverTrigger } from '../ui/popover';
import { Avatar, AvatarFallback, AvatarImage } from '../ui/avatar';
import { Check, ChevronDown, Users } from 'lucide-react';
import { useParentActiveStudent } from '../../contexts/ParentActiveStudentContext';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';

const LEGACY_CHILD_RE = /^\/parent\/child\/([^/]+)(\/.*)?$/;

const ShellStudentSwitcher = () => {
  const { t } = useTranslation();
  const { isRTL } = useTheme();
  const { linkedChildren, activeChildId, activeChild, setActiveChildId, isLoading } =
    useParentActiveStudent();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [open, setOpen] = useState(false);

  if (isLoading) return null;
  if (!linkedChildren || linkedChildren.length === 0) return null;

  const handlePick = (id) => {
    const sid = String(id);
    setActiveChildId(sid);
    setOpen(false);

    // One-way URL sync only on routes where the child id is part of the URL.
    const m = location.pathname.match(LEGACY_CHILD_RE);
    if (m) {
      const suffix = m[2] || '';
      navigate(`/parent/child/${sid}${suffix}${location.search || ''}`, { replace: true });
      return;
    }
    if (location.pathname === '/parent/children') {
      const next = new URLSearchParams(searchParams);
      next.set('child', sid);
      setSearchParams(next, { replace: true });
    }
  };

  const renderAvatar = (c, sizeClass = 'h-7 w-7') => (
    <Avatar className={`${sizeClass} shrink-0`}>
      <AvatarImage src={c.profile_picture || c.photo_url} alt={c.name || ''} />
      <AvatarFallback className="text-[10px] bg-brand-navy/15 text-brand-navy dark:bg-brand-turquoise/20 dark:text-brand-turquoise font-semibold">
        {c.name?.charAt(0) || '?'}
      </AvatarFallback>
    </Avatar>
  );

  // Single linked child — show a non-interactive identity chip.
  if (linkedChildren.length === 1) {
    const c = linkedChildren[0];
    return (
      <div
        className="flex items-center gap-2 rounded-xl bg-brand-navy/5 dark:bg-brand-turquoise/10 border border-brand-navy/10 dark:border-brand-turquoise/25 px-2.5 py-1.5 max-w-[220px]"
        data-testid="shell-student-chip"
        dir={isRTL ? 'rtl' : 'ltr'}
      >
        {renderAvatar(c, 'h-6 w-6')}
        <span className="text-xs font-cairo font-semibold truncate text-foreground">
          {c.name}
        </span>
      </div>
    );
  }

  const current = activeChild || linkedChildren[0];

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          data-testid="shell-student-switcher"
          className="flex items-center gap-2 rounded-xl bg-brand-navy/5 dark:bg-brand-turquoise/10 hover:bg-brand-navy/10 dark:hover:bg-brand-turquoise/20 border border-brand-navy/10 dark:border-brand-turquoise/25 px-2.5 py-1.5 transition-colors max-w-[260px]"
          dir={isRTL ? 'rtl' : 'ltr'}
        >
          {renderAvatar(current)}
          <div className="min-w-0 flex flex-col items-start">
            <span className="text-xs font-cairo font-semibold truncate text-foreground leading-tight max-w-[160px]">
              {current?.name}
            </span>
            {current?.grade && (
              <span className="text-[10px] text-muted-foreground font-tajawal truncate leading-tight max-w-[160px]">
                {current.grade}
              </span>
            )}
          </div>
          <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align={isRTL ? 'start' : 'end'}
        className="w-64 p-1.5"
        dir={isRTL ? 'rtl' : 'ltr'}
      >
        <div className="px-2 py-1.5 flex items-center gap-1.5 text-[11px] font-tajawal text-muted-foreground border-b border-border mb-1">
          <Users className="h-3.5 w-3.5" />
          <span>
            {t('linkedStudents') || (isRTL ? 'الطلاب المرتبطون' : 'Linked Students')}
          </span>
        </div>
        <div className="max-h-72 overflow-y-auto">
          {linkedChildren.map((c) => {
            const isActive = String(c.id) === String(activeChildId);
            return (
              <button
                key={c.id}
                type="button"
                onClick={() => handlePick(c.id)}
                data-testid={`shell-student-option-${c.id}`}
                className={`w-full flex items-center gap-2.5 px-2 py-2 rounded-lg text-start transition-colors ${
                  isActive
                    ? 'bg-brand-navy/10 dark:bg-brand-turquoise/15 text-brand-navy dark:text-brand-turquoise'
                    : 'hover:bg-muted/50 text-foreground'
                }`}
              >
                {renderAvatar(c, 'h-8 w-8')}
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-cairo font-semibold truncate">{c.name}</p>
                  {(c.grade || c.class_name) && (
                    <p className="text-[10px] text-muted-foreground truncate">
                      {[c.grade, c.class_name].filter(Boolean).join(' — ')}
                    </p>
                  )}
                </div>
                {isActive && (
                  <Check className="h-4 w-4 shrink-0 text-brand-turquoise" />
                )}
              </button>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
};

export default ShellStudentSwitcher;
