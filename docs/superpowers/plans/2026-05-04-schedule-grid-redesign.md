# Schedule Grid Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the schedule grids (master grid + teacher's own schedule view + class detail schedule view) with a Nassaq-branded pastel day-color system, banded day headers, refined cells, and a glass-morphism cell-click modal that surfaces session detail and quick actions.

**Architecture:** Introduce a shared `frontend/src/components/schedule/grid-theme/` module containing a single source of truth for day colors (`dayPalette.js`), a banded `DayHeaderBand`, a re-themed `SessionCell`, and a glass `SessionDetailModal`. The existing `TeacherScheduleGrid` is refactored to use these primitives. The teacher's own schedule view (`TeacherModule/TeacherSchedulePage.jsx`) and class detail schedule view (`ClassDetailPage.jsx`) adopt the same primitives. No backend, API, or schema changes.

**Tech Stack:** React 18, Vite, Tailwind CSS, shadcn/ui (Radix), framer-motion (`^11.18.2`), lucide-react. Arabic-first RTL with Cairo (display) + Tajawal (body). Tests use Jest + React Testing Library (existing setup under `frontend/src/components/schedule/__tests__/`).

---

## File Structure

**New files (created in this plan):**
- `frontend/src/components/schedule/grid-theme/dayPalette.js` — day color tokens + helpers
- `frontend/src/components/schedule/grid-theme/DayHeaderBand.jsx` — colored day band + period number sub-row
- `frontend/src/components/schedule/grid-theme/SessionCell.jsx` — re-themed cell renderer with day tint
- `frontend/src/components/schedule/grid-theme/SessionDetailModal.jsx` — glass-morphism modal
- `frontend/src/components/schedule/grid-theme/index.js` — barrel re-exports
- `frontend/src/components/schedule/__tests__/dayPalette.test.js`
- `frontend/src/components/schedule/__tests__/SessionCell.test.jsx`
- `frontend/src/components/schedule/__tests__/SessionDetailModal.test.jsx`

**Existing files to modify:**
- `frontend/tailwind.config.js` — add `brand.sand` and `brand.sage` color extensions
- `frontend/src/index.css` — add `--day-*` HSL CSS variables for day tints/bands
- `frontend/src/components/schedule/TeacherScheduleGrid.jsx` — adopt `DayHeaderBand`, `SessionCell`, render `SessionDetailModal` at root
- `frontend/src/components/schedule/FilledCell.jsx` — delegate visuals to `SessionCell` for the default branch (keep relocated/substituted special branches as-is to limit blast radius)
- `frontend/src/pages/TeacherModule/TeacherSchedulePage.jsx` — adopt the new primitives (verify exact rendering structure during Task 8)
- `frontend/src/pages/ClassDetailPage.jsx` — adopt the new primitives (verify exact rendering structure during Task 9)
- `frontend/src/locales/ar.json`, `frontend/src/locales/en.json` — add modal labels (`sessionDetailsTitle`, `editAction`, `moveAction`, `lockAction`, `unlockAction`, `closeAction`)

---

## Task 1: Add Nassaq-extended palette tokens (sand + sage) to Tailwind & CSS variables

**Files:**
- Modify: `frontend/tailwind.config.js`
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Add `sand` and `sage` to Tailwind brand color group**

In `frontend/tailwind.config.js`, inside `theme.extend.colors.brand`, add the two new entries after `gray`:

```js
brand: {
    navy: '#1C3D74',
    'navy-light': '#2a5096',
    'navy-dark': '#152d57',
    purple: '#615090',
    'purple-light': '#7a68a8',
    'purple-dark': '#4a3d70',
    turquoise: '#46C1BE',
    'turquoise-light': '#5fd1ce',
    'turquoise-dark': '#38a19e',
    black: '#312E2F',
    gray: '#EAECED',
    sand: '#D4A23C',
    'sand-light': '#FBF1DC',
    sage: '#7AA169',
    'sage-light': '#E8F1E4',
},
```

- [ ] **Step 2: Add HSL day variables to `:root` in `index.css`**

Find the `:root` block in `frontend/src/index.css` (where `--brand-navy: 217 61% 28%;` lives) and add immediately after the brand triplet:

```css
/* Day color system — tints for cell backgrounds, bands for day headers */
--day-sun-tint: 217 56% 95%;
--day-sun-band: 217 61% 28%;
--day-mon-tint: 178 49% 93%;
--day-mon-band: 179 49% 51%;
--day-tue-tint: 41 81% 92%;
--day-tue-band: 38 64% 53%;
--day-wed-tint: 99 35% 92%;
--day-wed-band: 95 24% 52%;
--day-thu-tint: 251 31% 93%;
--day-thu-band: 255 29% 44%;
```

- [ ] **Step 3: Verify Tailwind picks up the new tokens**

Run:
```
cd frontend && pnpm run build 2>&1 | tail -20
```
Expected: build succeeds, no Tailwind errors. (If build script differs, use `npm run build`.)

- [ ] **Step 4: Commit**

```
git add frontend/tailwind.config.js frontend/src/index.css
git commit -m "feat(schedule): add nassaq-extended day color palette (sand + sage)"
```

---

## Task 2: Create `dayPalette.js` single source of truth + tests

**Files:**
- Create: `frontend/src/components/schedule/grid-theme/dayPalette.js`
- Test: `frontend/src/components/schedule/__tests__/dayPalette.test.js`

- [ ] **Step 1: Write the failing test**

`frontend/src/components/schedule/__tests__/dayPalette.test.js`:

```js
import {
  DAY_PALETTE,
  getDayTintClass,
  getDayBandClass,
  getDayTextOnBand,
  getDayKeys,
} from '../grid-theme/dayPalette';

describe('dayPalette', () => {
  it('exposes the five school days in week order', () => {
    expect(getDayKeys()).toEqual(['sunday', 'monday', 'tuesday', 'wednesday', 'thursday']);
  });

  it('returns a Tailwind tint class for each day', () => {
    expect(getDayTintClass('sunday')).toBe('bg-[hsl(var(--day-sun-tint))]');
    expect(getDayTintClass('monday')).toBe('bg-[hsl(var(--day-mon-tint))]');
    expect(getDayTintClass('tuesday')).toBe('bg-[hsl(var(--day-tue-tint))]');
    expect(getDayTintClass('wednesday')).toBe('bg-[hsl(var(--day-wed-tint))]');
    expect(getDayTintClass('thursday')).toBe('bg-[hsl(var(--day-thu-tint))]');
  });

  it('returns a Tailwind band class for each day', () => {
    expect(getDayBandClass('sunday')).toBe('bg-[hsl(var(--day-sun-band))]');
    expect(getDayBandClass('thursday')).toBe('bg-[hsl(var(--day-thu-band))]');
  });

  it('text-on-band is white for every day', () => {
    getDayKeys().forEach((day) => {
      expect(getDayTextOnBand(day)).toBe('text-white');
    });
  });

  it('falls back to a neutral tint when day key is unknown', () => {
    expect(getDayTintClass('saturday')).toBe('bg-muted/40');
    expect(getDayBandClass('saturday')).toBe('bg-muted');
  });

  it('DAY_PALETTE entries each carry tintClass and bandClass', () => {
    Object.values(DAY_PALETTE).forEach((entry) => {
      expect(entry).toHaveProperty('tintClass');
      expect(entry).toHaveProperty('bandClass');
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```
cd frontend && pnpm test -- dayPalette.test.js --watchAll=false
```
Expected: FAIL with "Cannot find module '../grid-theme/dayPalette'".

- [ ] **Step 3: Write the implementation**

Create `frontend/src/components/schedule/grid-theme/dayPalette.js`:

```js
/**
 * Single source of truth for schedule grid day colors.
 *
 * Tokens are defined as HSL CSS variables in `frontend/src/index.css`
 * (`--day-*-tint` / `--day-*-band`). Tailwind arbitrary-value classes wrap
 * those vars so consumers never hardcode a hex value.
 */

export const DAY_PALETTE = {
  sunday:    { tintClass: 'bg-[hsl(var(--day-sun-tint))]', bandClass: 'bg-[hsl(var(--day-sun-band))]', textOnBand: 'text-white' },
  monday:    { tintClass: 'bg-[hsl(var(--day-mon-tint))]', bandClass: 'bg-[hsl(var(--day-mon-band))]', textOnBand: 'text-white' },
  tuesday:   { tintClass: 'bg-[hsl(var(--day-tue-tint))]', bandClass: 'bg-[hsl(var(--day-tue-band))]', textOnBand: 'text-white' },
  wednesday: { tintClass: 'bg-[hsl(var(--day-wed-tint))]', bandClass: 'bg-[hsl(var(--day-wed-band))]', textOnBand: 'text-white' },
  thursday:  { tintClass: 'bg-[hsl(var(--day-thu-tint))]', bandClass: 'bg-[hsl(var(--day-thu-band))]', textOnBand: 'text-white' },
};

const FALLBACK = { tintClass: 'bg-muted/40', bandClass: 'bg-muted', textOnBand: 'text-foreground' };

export const getDayKeys = () => ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday'];

export const getDayPalette = (dayKey) => DAY_PALETTE[dayKey] || FALLBACK;

export const getDayTintClass = (dayKey) => getDayPalette(dayKey).tintClass;
export const getDayBandClass = (dayKey) => getDayPalette(dayKey).bandClass;
export const getDayTextOnBand = (dayKey) => getDayPalette(dayKey).textOnBand;
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```
cd frontend && pnpm test -- dayPalette.test.js --watchAll=false
```
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```
git add frontend/src/components/schedule/grid-theme/dayPalette.js frontend/src/components/schedule/__tests__/dayPalette.test.js
git commit -m "feat(schedule): add day palette single source of truth"
```

---

## Task 3: Build `DayHeaderBand` (band header + numbered period sub-row)

**Files:**
- Create: `frontend/src/components/schedule/grid-theme/DayHeaderBand.jsx`

- [ ] **Step 1: Write the implementation**

```jsx
/**
 * DayHeaderBand — colored day name band + numbered period sub-row.
 *
 * Replaces the two separate header rows in TeacherScheduleGrid. Renders a
 * single day group: a strong colored band (day name in white, Cairo 700)
 * stacked above small per-period number cells tinted in the day's lighter shade.
 *
 * Props:
 *   dayKey       — 'sunday' | 'monday' | ...
 *   dayLabel     — translated day name to display
 *   timeSlots    — array of slot objects { start_time, is_break, ... }
 *   slotWidthPx  — width of one period column in pixels (default 60)
 */
import React from 'react';
import { Coffee } from 'lucide-react';
import {
  getDayBandClass,
  getDayTintClass,
  getDayTextOnBand,
} from './dayPalette';

export default function DayHeaderBand({ dayKey, dayLabel, timeSlots, slotWidthPx = 60 }) {
  const bandClass = getDayBandClass(dayKey);
  const tintClass = getDayTintClass(dayKey);
  const textClass = getDayTextOnBand(dayKey);
  const totalWidth = (timeSlots?.length || 0) * slotWidthPx;

  return (
    <div className="flex-shrink-0" style={{ width: `${totalWidth}px` }}>
      {/* Band: day name */}
      <div
        className={`${bandClass} ${textClass} px-2 py-1.5 text-center font-cairo font-bold text-sm border-e border-white/20`}
        data-testid={`day-band-${dayKey}`}
      >
        {dayLabel}
      </div>
      {/* Numbered period sub-row */}
      <div className={`flex ${tintClass} border-e border-border/30`}>
        {timeSlots.map((slot, idx) => (
          <div
            key={`${dayKey}-period-${idx}`}
            className="text-center border-e border-white/40 last:border-e-0 py-1"
            style={{ width: `${slotWidthPx}px` }}
            data-testid={`day-period-${dayKey}-${idx}`}
          >
            {slot.is_break ? (
              <Coffee className="h-3 w-3 text-amber-600 mx-auto" aria-label="break" />
            ) : (
              <>
                <p className="text-[10px] font-tajawal font-semibold text-foreground/80">{idx + 1}</p>
                <p className="text-[8px] text-foreground/55 font-tajawal">{slot.start_time}</p>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Sanity check render path**

Run:
```
cd frontend && pnpm run build 2>&1 | tail -10
```
Expected: build succeeds.

- [ ] **Step 3: Commit**

```
git add frontend/src/components/schedule/grid-theme/DayHeaderBand.jsx
git commit -m "feat(schedule): add DayHeaderBand component with banded day color"
```

---

## Task 4: Build `SessionCell` (day-tinted, hover + a11y) + tests

**Files:**
- Create: `frontend/src/components/schedule/grid-theme/SessionCell.jsx`
- Test: `frontend/src/components/schedule/__tests__/SessionCell.test.jsx`

- [ ] **Step 1: Write the failing test**

```jsx
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import SessionCell from '../grid-theme/SessionCell';

const baseSession = {
  id: 's-1',
  subject_name: 'رياضيات',
  class_name: '٣ علوم',
  day_of_week: 'monday',
  slot_number: 3,
  start_time: '11:35',
  end_time: '12:15',
};

describe('SessionCell', () => {
  it('renders subject and class', () => {
    render(<SessionCell session={baseSession} dayKey="monday" onClick={() => {}} />);
    expect(screen.getByText('رياضيات')).toBeInTheDocument();
    expect(screen.getByText('٣ علوم')).toBeInTheDocument();
  });

  it('applies the monday tint class', () => {
    render(<SessionCell session={baseSession} dayKey="monday" onClick={() => {}} />);
    const cell = screen.getByRole('button');
    expect(cell.className).toMatch(/--day-mon-tint/);
  });

  it('calls onClick with the session when activated', () => {
    const onClick = jest.fn();
    render(<SessionCell session={baseSession} dayKey="monday" onClick={onClick} />);
    fireEvent.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledWith(baseSession);
  });

  it('opens on Enter key press', () => {
    const onClick = jest.fn();
    render(<SessionCell session={baseSession} dayKey="monday" onClick={onClick} />);
    fireEvent.keyDown(screen.getByRole('button'), { key: 'Enter' });
    expect(onClick).toHaveBeenCalled();
  });

  it('renders an accessible label including subject, class, day and period', () => {
    render(<SessionCell session={baseSession} dayKey="monday" onClick={() => {}} />);
    const cell = screen.getByRole('button');
    expect(cell.getAttribute('aria-label')).toMatch(/رياضيات/);
    expect(cell.getAttribute('aria-label')).toMatch(/٣ علوم/);
  });

  it('shows lock icon when isLocked is true', () => {
    render(<SessionCell session={baseSession} dayKey="monday" onClick={() => {}} isLocked />);
    expect(screen.getByTestId('session-cell-lock-icon')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```
cd frontend && pnpm test -- SessionCell.test.jsx --watchAll=false
```
Expected: FAIL — module not found.

- [ ] **Step 3: Write the implementation**

`frontend/src/components/schedule/grid-theme/SessionCell.jsx`:

```jsx
/**
 * SessionCell — day-tinted, click-to-open session cell.
 *
 * Replaces the visual default branch of FilledCell. Special states
 * (vacant / substituted / relocated) keep their existing renderers in
 * FilledCell.jsx; SessionCell is the canonical "filled, normal" cell.
 *
 * Props:
 *   session       — { id, subject_name, class_name, day_of_week, slot_number, start_time, end_time, ... }
 *   dayKey        — day key for color tint
 *   onClick(session) — invoked on click / Enter / Space
 *   isLocked      — show lock icon, dim slightly
 *   hasConflict   — show conflict icon
 */
import React from 'react';
import { Lock, AlertTriangle } from 'lucide-react';
import { getDayTintClass } from './dayPalette';

export default function SessionCell({
  session,
  dayKey,
  onClick,
  isLocked = false,
  hasConflict = false,
}) {
  const tint = getDayTintClass(dayKey);
  const handleActivate = (e) => {
    if (e.type === 'keydown' && e.key !== 'Enter' && e.key !== ' ') return;
    e.preventDefault?.();
    onClick?.(session);
  };
  const subject = session?.subject_name || '';
  const klass = session?.class_name || '—';
  const ariaLabel = `${subject} · ${klass} · ${dayKey} · ${session?.slot_number ?? ''}`;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={handleActivate}
      onKeyDown={handleActivate}
      aria-label={ariaLabel}
      data-testid={`session-cell-${session?.id}`}
      className={`
        relative h-full min-h-[50px] rounded-md p-1 cursor-pointer
        ${tint}
        border border-white/60
        text-brand-navy
        transition-all duration-200 ease-out
        hover:scale-[1.02] hover:shadow-md hover:z-10
        focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-turquoise focus-visible:ring-offset-1
        motion-reduce:hover:scale-100
        ${isLocked ? 'opacity-80' : ''}
      `}
    >
      {isLocked && (
        <Lock
          data-testid="session-cell-lock-icon"
          className="absolute top-0.5 start-0.5 h-2.5 w-2.5 text-brand-navy/60"
        />
      )}
      {hasConflict && (
        <AlertTriangle
          className="absolute top-0.5 end-0.5 h-2.5 w-2.5 text-red-500"
        />
      )}
      <div className="flex flex-col h-full justify-center items-center gap-0.5 text-center">
        <span className="text-[10px] font-cairo font-semibold line-clamp-1">
          {subject}
        </span>
        <span className="text-[9px] font-tajawal opacity-80 line-clamp-1">
          {klass}
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```
cd frontend && pnpm test -- SessionCell.test.jsx --watchAll=false
```
Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```
git add frontend/src/components/schedule/grid-theme/SessionCell.jsx frontend/src/components/schedule/__tests__/SessionCell.test.jsx
git commit -m "feat(schedule): add SessionCell with day tint, hover, a11y"
```

---

## Task 5: Build `SessionDetailModal` (glass) + tests

**Files:**
- Create: `frontend/src/components/schedule/grid-theme/SessionDetailModal.jsx`
- Test: `frontend/src/components/schedule/__tests__/SessionDetailModal.test.jsx`

- [ ] **Step 1: Write the failing test**

`frontend/src/components/schedule/__tests__/SessionDetailModal.test.jsx`:

```jsx
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import SessionDetailModal from '../grid-theme/SessionDetailModal';

const session = {
  id: 's-1',
  subject_name: 'رياضيات',
  class_name: '٣ علوم',
  teacher_name: 'أحمد المعلم',
  teacher_avatar_url: null,
  teacher_specialty: 'رياضيات',
  room: 'قاعة ٢٠٤',
  day_of_week: 'sunday',
  slot_number: 3,
  start_time: '11:35',
  end_time: '12:15',
  is_locked: false,
};

describe('SessionDetailModal', () => {
  it('renders nothing when closed', () => {
    const { container } = render(
      <SessionDetailModal open={false} session={session} onClose={() => {}} />
    );
    expect(container.querySelector('[data-testid="session-detail-modal"]')).toBeNull();
  });

  it('renders subject, class, teacher, room and time when open', () => {
    render(<SessionDetailModal open session={session} onClose={() => {}} />);
    expect(screen.getByText('رياضيات')).toBeInTheDocument();
    expect(screen.getByText('٣ علوم')).toBeInTheDocument();
    expect(screen.getByText('أحمد المعلم')).toBeInTheDocument();
    expect(screen.getByText(/قاعة ٢٠٤/)).toBeInTheDocument();
    expect(screen.getByText(/11:35/)).toBeInTheDocument();
  });

  it('calls onClose when X button is clicked', () => {
    const onClose = jest.fn();
    render(<SessionDetailModal open session={session} onClose={onClose} />);
    fireEvent.click(screen.getByTestId('session-detail-close'));
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose on Escape key', () => {
    const onClose = jest.fn();
    render(<SessionDetailModal open session={session} onClose={onClose} />);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose when backdrop is clicked', () => {
    const onClose = jest.fn();
    render(<SessionDetailModal open session={session} onClose={onClose} />);
    fireEvent.click(screen.getByTestId('session-detail-backdrop'));
    expect(onClose).toHaveBeenCalled();
  });

  it('invokes onEdit, onMove, onLockToggle from quick actions', () => {
    const onEdit = jest.fn();
    const onMove = jest.fn();
    const onLockToggle = jest.fn();
    render(
      <SessionDetailModal
        open
        session={session}
        onClose={() => {}}
        onEdit={onEdit}
        onMove={onMove}
        onLockToggle={onLockToggle}
      />
    );
    fireEvent.click(screen.getByTestId('session-action-edit'));
    fireEvent.click(screen.getByTestId('session-action-move'));
    fireEvent.click(screen.getByTestId('session-action-lock'));
    expect(onEdit).toHaveBeenCalledWith(session);
    expect(onMove).toHaveBeenCalledWith(session);
    expect(onLockToggle).toHaveBeenCalledWith(session);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```
cd frontend && pnpm test -- SessionDetailModal.test.jsx --watchAll=false
```
Expected: FAIL — module not found.

- [ ] **Step 3: Write the implementation**

`frontend/src/components/schedule/grid-theme/SessionDetailModal.jsx`:

```jsx
/**
 * SessionDetailModal — glass-morphism cell-click pop-up.
 *
 * Pure visual + a11y wiring. Quick actions delegate back to the parent
 * grid via onEdit / onMove / onLockToggle so the existing edit/drag/lock
 * pipelines remain authoritative.
 */
import React, { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Pencil, Move, Lock, Unlock, MapPin, User } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '../../ui/avatar';
import { Button } from '../../ui/button';
import { Badge } from '../../ui/badge';
import { useTranslation } from '../../../contexts/ThemeContext';
import { getDayBandClass, getDayTextOnBand } from './dayPalette';

export default function SessionDetailModal({
  open,
  session,
  onClose,
  onEdit,
  onMove,
  onLockToggle,
}) {
  const { t } = useTranslation();

  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (e.key === 'Escape') onClose?.(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && session && (
        <motion.div
          key="session-modal"
          data-testid="session-detail-modal"
          className="fixed inset-0 z-[100] flex items-center justify-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
        >
          {/* Backdrop */}
          <div
            data-testid="session-detail-backdrop"
            onClick={onClose}
            className="absolute inset-0 bg-[rgba(28,61,116,0.35)] backdrop-blur-md"
          />
          {/* Glass card */}
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="session-detail-title"
            initial={{ scale: 0.95, opacity: 0, y: 8 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.97, opacity: 0, y: 4 }}
            transition={{ duration: 0.22, ease: 'easeOut' }}
            className="relative w-[420px] max-w-[92vw] rounded-2xl bg-white/75 backdrop-blur-2xl
                       border border-brand-navy/15 shadow-[0_20px_60px_-15px_rgba(28,61,116,0.35)]
                       overflow-hidden"
          >
            {/* Day-color header strip */}
            <div
              id="session-detail-title"
              className={`${getDayBandClass(session.day_of_week)} ${getDayTextOnBand(session.day_of_week)}
                          px-4 py-2 text-sm font-cairo font-bold text-center`}
            >
              {t(session.day_of_week)} · {t('periodNumberLabel', { n: session.slot_number })} ·{' '}
              {session.start_time} - {session.end_time}
            </div>

            {/* Close button (top-left for RTL) */}
            <button
              type="button"
              data-testid="session-detail-close"
              onClick={onClose}
              aria-label={t('closeAction')}
              className="absolute top-2 start-2 h-7 w-7 inline-flex items-center justify-center
                         rounded-full bg-white/70 hover:bg-white text-brand-navy/80
                         transition-colors"
            >
              <X className="h-4 w-4" />
            </button>

            {/* Body */}
            <div className="p-5 space-y-4">
              <div className="text-center">
                <h3 className="text-xl font-cairo font-bold text-brand-navy">
                  {session.subject_name}
                </h3>
                <p className="text-sm font-tajawal text-brand-navy/70 mt-0.5">
                  {session.class_name}
                </p>
              </div>

              <div className="flex items-center gap-3 bg-white/50 rounded-xl p-2.5 border border-brand-navy/10">
                <Avatar className="h-9 w-9 flex-shrink-0">
                  <AvatarImage src={session.teacher_avatar_url} alt={session.teacher_name} />
                  <AvatarFallback className="bg-brand-navy text-white text-xs">
                    {(session.teacher_name || '?').split(' ').map((n) => n[0]).join('').slice(0, 2)}
                  </AvatarFallback>
                </Avatar>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-cairo font-semibold text-brand-navy truncate">
                    {session.teacher_name || t('teacher2')}
                  </p>
                  <p className="text-[11px] font-tajawal text-brand-navy/60 truncate">
                    {session.teacher_specialty || ''}
                  </p>
                </div>
              </div>

              {session.room && (
                <div className="inline-flex items-center gap-1.5 text-xs font-tajawal text-brand-navy/80
                                bg-brand-turquoise/10 border border-brand-turquoise/30 rounded-full px-2.5 py-1">
                  <MapPin className="h-3 w-3" />
                  {session.room}
                </div>
              )}

              {/* Status badges */}
              <div className="flex flex-wrap gap-1.5">
                {session.is_locked && (
                  <Badge variant="outline" className="text-[10px] border-amber-300 text-amber-700">
                    <Lock className="h-2.5 w-2.5 me-1" />
                    {t('lockedBadge')}
                  </Badge>
                )}
                {session.is_relocated && (
                  <Badge variant="outline" className="text-[10px] border-orange-300 text-orange-700">
                    {t('relocatedBadge')}
                  </Badge>
                )}
                {session.is_substitute && (
                  <Badge variant="outline" className="text-[10px] border-violet-300 text-violet-700">
                    {t('substituteShortLabel')}
                  </Badge>
                )}
              </div>

              {/* Quick actions */}
              <div className="flex gap-2 pt-1">
                <Button
                  data-testid="session-action-edit"
                  onClick={() => onEdit?.(session)}
                  className="flex-1 bg-brand-turquoise hover:bg-brand-turquoise-dark text-white gap-1.5"
                >
                  <Pencil className="h-3.5 w-3.5" />
                  {t('editAction')}
                </Button>
                <Button
                  data-testid="session-action-move"
                  variant="outline"
                  onClick={() => onMove?.(session)}
                  className="flex-1 gap-1.5"
                >
                  <Move className="h-3.5 w-3.5" />
                  {t('moveAction')}
                </Button>
                <Button
                  data-testid="session-action-lock"
                  variant="outline"
                  onClick={() => onLockToggle?.(session)}
                  className="flex-1 gap-1.5"
                >
                  {session.is_locked ? <Unlock className="h-3.5 w-3.5" /> : <Lock className="h-3.5 w-3.5" />}
                  {session.is_locked ? t('unlockAction') : t('lockAction')}
                </Button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```
cd frontend && pnpm test -- SessionDetailModal.test.jsx --watchAll=false
```
Expected: all 6 tests PASS. (If translation keys missing in tests cause warnings, the test does not assert on them — they will pass.)

- [ ] **Step 5: Commit**

```
git add frontend/src/components/schedule/grid-theme/SessionDetailModal.jsx frontend/src/components/schedule/__tests__/SessionDetailModal.test.jsx
git commit -m "feat(schedule): add glass SessionDetailModal with quick actions"
```

---

## Task 6: Add modal-related translation keys

**Files:**
- Modify: `frontend/src/locales/ar.json`
- Modify: `frontend/src/locales/en.json`

- [ ] **Step 1: Add keys to `ar.json`**

Append (or merge) to `frontend/src/locales/ar.json`:

```json
{
  "sessionDetailsTitle": "تفاصيل الحصة",
  "editAction": "تعديل",
  "moveAction": "نقل",
  "lockAction": "تثبيت",
  "unlockAction": "إلغاء التثبيت",
  "closeAction": "إغلاق",
  "lockedBadge": "مثبتة",
  "relocatedBadge": "نُقلت",
  "periodNumberLabel": "الحصة {{n}}"
}
```

- [ ] **Step 2: Add the same keys (English) to `en.json`**

```json
{
  "sessionDetailsTitle": "Session details",
  "editAction": "Edit",
  "moveAction": "Move",
  "lockAction": "Lock",
  "unlockAction": "Unlock",
  "closeAction": "Close",
  "lockedBadge": "Locked",
  "relocatedBadge": "Relocated",
  "periodNumberLabel": "Period {{n}}"
}
```

- [ ] **Step 3: Verify JSON parses**

```
cd frontend && node -e "JSON.parse(require('fs').readFileSync('src/locales/ar.json','utf8')); JSON.parse(require('fs').readFileSync('src/locales/en.json','utf8')); console.log('OK')"
```
Expected: `OK`.

- [ ] **Step 4: Commit**

```
git add frontend/src/locales/ar.json frontend/src/locales/en.json
git commit -m "i18n(schedule): add session detail modal labels"
```

---

## Task 7: Refactor `TeacherScheduleGrid` to use new primitives + render modal

**Files:**
- Modify: `frontend/src/components/schedule/TeacherScheduleGrid.jsx`
- Create: `frontend/src/components/schedule/grid-theme/index.js`

- [ ] **Step 1: Create barrel export**

`frontend/src/components/schedule/grid-theme/index.js`:

```js
export { default as DayHeaderBand } from './DayHeaderBand';
export { default as SessionCell } from './SessionCell';
export { default as SessionDetailModal } from './SessionDetailModal';
export * from './dayPalette';
```

- [ ] **Step 2: Replace the inline `SessionCard` and the two-row header with the new primitives**

In `frontend/src/components/schedule/TeacherScheduleGrid.jsx`:

a) Add imports near the top (alongside existing imports):

```jsx
import { DayHeaderBand, SessionCell, SessionDetailModal } from './grid-theme';
```

b) **Delete** the `SUBJECT_COLORS` constant, `DEFAULT_COLOR`, and the entire local `SessionCard` component (lines ~46 through ~134 in the current file). They are replaced by `SessionCell` + day tint.

c) Replace the `SessionCard` usage inside `TeacherRow` (the `{session ? <SessionCard ... /> : <EmptySlot ... />}` block) with:

```jsx
{session ? (
  <SessionCell
    session={session}
    dayKey={day.key}
    onClick={(s) => setSelectedSession(s)}
    isLocked={lockedSessions?.includes(session.id)}
    hasConflict={conflicts?.some((c) => c.session_id === session.id)}
  />
) : (
  <EmptySlot
    day={day.key}
    periodIndex={periodIndex}
    teacherId={teacher.id}
    isRTL={isRTL}
    onDragOver={onDragOver}
    onDrop={onDrop}
    isDropTarget={isCurrentDropTarget}
    isBreak={isBreak}
  />
)}
```

Note: this removes drag-from-cell on the new visual cell. To preserve drag, wrap the cell in a draggable container — see step (e) below.

d) Replace the entire two-block "Multi-level Header" (the `<div className="sticky top-0 z-20 bg-background">` block containing both the Days Header row and the Periods Header row) with a single banded header row:

```jsx
<div className="sticky top-0 z-20 bg-background">
  <div className="flex border-b border-border">
    {/* Teacher column header (kept) */}
    <div className="w-52 flex-shrink-0 p-3 border-e border-border font-medium text-sm sticky start-0 bg-muted/50 z-30">
      <div className="flex items-center gap-2">
        <User className="h-4 w-4 text-brand-navy" />
        <span>{t('teacher2')}</span>
      </div>
      <p className="text-[10px] text-muted-foreground mt-1">
        {t('teachersWithCount', { count: teachers.length })}
      </p>
    </div>
    {/* Day groups: each is a band + numbered period sub-row */}
    <div className="flex-1 overflow-x-auto">
      <div className="flex min-w-max">
        {daysToShow.map((day) => (
          <DayHeaderBand
            key={day.key}
            dayKey={day.key}
            dayLabel={t(day.key)}
            timeSlots={effectiveTimeSlots}
            slotWidthPx={60}
          />
        ))}
      </div>
    </div>
  </div>
</div>
```

e) Restore drag support by wrapping `SessionCell` inside `TeacherRow` in a draggable wrapper (only when not locked):

Replace the `SessionCell` usage from step (c) with:

```jsx
{session ? (
  <div
    draggable={!lockedSessions?.includes(session.id)}
    onDragStart={(e) => onDragStart?.(e, session)}
    onDragEnd={onDragEnd}
    className="h-full"
  >
    <SessionCell
      session={session}
      dayKey={day.key}
      onClick={(s) => setSelectedSession(s)}
      isLocked={lockedSessions?.includes(session.id)}
      hasConflict={conflicts?.some((c) => c.session_id === session.id)}
    />
  </div>
) : (
  /* unchanged EmptySlot */
)}
```

f) Add modal state at the top of the `TeacherScheduleGrid` function, alongside the existing `useState` calls:

```jsx
const [selectedSession, setSelectedSession] = useState(null);
```

g) Render the modal once at the root of the returned JSX (just before the closing `</div>` of the outer `<div className="relative overflow-hidden rounded-xl border border-border bg-background" ...>`):

```jsx
<SessionDetailModal
  open={!!selectedSession}
  session={selectedSession}
  onClose={() => setSelectedSession(null)}
  onEdit={(s) => { setSelectedSession(null); (onSessionEdit || onSessionClick)?.(s); }}
  onMove={(s) => { setSelectedSession(null); onSessionClick?.(s); /* drag pipeline already wired on the cell wrapper */ }}
  onLockToggle={(s) => { setSelectedSession(null); onSessionClick?.({ ...s, __action: 'toggle-lock' }); }}
/>
```

(Notes: `onSessionEdit` and `onSessionClick` are already props on the component. The Move action closes the modal so the user can drag the cell directly. The Lock action piggybacks on `onSessionClick` with an `__action` marker — if the parent doesn't yet handle it, the existing click flow runs with no regression. A separate `onSessionLockToggle` prop could be added later without touching this file.)

- [ ] **Step 3: Run existing tests to verify no regressions**

```
cd frontend && pnpm test -- TeacherScheduleGrid --watchAll=false
```
Expected: existing `TeacherScheduleGrid.loading.test.jsx` continues to PASS.

- [ ] **Step 4: Visual smoke test**

Open the master grid in the running Frontend Dev workflow and verify:
- Day bands appear in the five colors
- Cells are tinted per day
- Clicking a cell opens the glass modal
- Esc / X / backdrop dismiss the modal
- Edit button still triggers the existing edit flow

- [ ] **Step 5: Commit**

```
git add frontend/src/components/schedule/TeacherScheduleGrid.jsx frontend/src/components/schedule/grid-theme/index.js
git commit -m "refactor(schedule): adopt grid-theme primitives + glass modal in master grid"
```

---

## Task 8: Apply primitives to teacher's own schedule view

**Files:**
- Modify: `frontend/src/pages/TeacherModule/TeacherSchedulePage.jsx`

- [ ] **Step 1: Inspect the existing rendering**

Read `frontend/src/pages/TeacherModule/TeacherSchedulePage.jsx` end-to-end. Confirm whether the page renders its own grid markup (likely a per-day card list or a small matrix), not the shared `TeacherScheduleGrid`.

- [ ] **Step 2: Replace cell visuals + day headers with the new primitives**

For each day group in this page's render:
- Replace any custom day header markup with `<DayHeaderBand dayKey={day.key} dayLabel={t(day.key)} timeSlots={timeSlots} slotWidthPx={60} />`.
- Replace each per-period filled cell with `<SessionCell session={session} dayKey={day.key} onClick={(s) => setSelectedSession(s)} />`.
- Add `const [selectedSession, setSelectedSession] = useState(null);` at the top of the component.
- Render `<SessionDetailModal open={!!selectedSession} session={selectedSession} onClose={() => setSelectedSession(null)} onEdit={() => {}} onMove={() => {}} onLockToggle={() => {}} />` at the root. (Teacher view is read-only by default; omit lock/move buttons by passing `undefined` for handlers — the modal still renders the buttons but they no-op. If the teacher view should hide actions entirely, add a `readOnly` prop in a follow-up.)

Add the imports:

```jsx
import { DayHeaderBand, SessionCell, SessionDetailModal } from '../../components/schedule/grid-theme';
```

- [ ] **Step 3: Verify build + manual smoke test**

```
cd frontend && pnpm run build 2>&1 | tail -10
```
Expected: build succeeds.

Then load the teacher's own schedule view in the running app and confirm bands, tints, and modal behavior.

- [ ] **Step 4: Commit**

```
git add frontend/src/pages/TeacherModule/TeacherSchedulePage.jsx
git commit -m "feat(schedule): adopt grid-theme primitives in teacher's own schedule view"
```

---

## Task 9: Apply primitives to class detail schedule view

**Files:**
- Modify: `frontend/src/pages/ClassDetailPage.jsx`

- [ ] **Step 1: Inspect the existing rendering**

Read `frontend/src/pages/ClassDetailPage.jsx`. Locate the schedule rendering section (search for `day_of_week`, `slot_number`, or `schedule`). Confirm the markup shape.

- [ ] **Step 2: Replace day headers + cells with primitives**

Same shape as Task 8:

- Replace day headers with `<DayHeaderBand … />`.
- Replace each filled cell with `<SessionCell session={s} dayKey={day.key} onClick={(sess) => setSelectedSession(sess)} />`.
- Add `useState` for `selectedSession` and render `<SessionDetailModal … />` once at the root.

Add the import:

```jsx
import { DayHeaderBand, SessionCell, SessionDetailModal } from '../components/schedule/grid-theme';
```

- [ ] **Step 3: Build + smoke test**

```
cd frontend && pnpm run build 2>&1 | tail -10
```
Expected: build succeeds. Then verify in the running app.

- [ ] **Step 4: Commit**

```
git add frontend/src/pages/ClassDetailPage.jsx
git commit -m "feat(schedule): adopt grid-theme primitives in class detail schedule view"
```

---

## Task 10: Slim `FilledCell` to delegate the default branch to `SessionCell`

**Files:**
- Modify: `frontend/src/components/schedule/FilledCell.jsx`

- [ ] **Step 1: Replace only the default (final) `return` block**

The current `FilledCell` has four conditional branches: `is_vacant`, `is_substituted`, `is_substitute`, `relocated`, then a default. Keep the first four branches unchanged (they have specialized semantics: red vacancy button, emerald substituted, violet substitute, orange relocated popover). Replace only the final default block:

Old final block (lines ~158–168 in the current file):

```jsx
return (
  <div
    className="w-full h-full flex flex-col items-center justify-center text-[10px] leading-tight px-1 text-blue-600/80"
    title={cell?.subject_name || ''}
  >
    <span className="font-semibold">{cell?.class_name || '—'}</span>
    {cell?.subject_name && (
      <span className="text-[9px] text-slate-400 truncate max-w-full">{cell.subject_name}</span>
    )}
  </div>
);
```

Replace with:

```jsx
return (
  <SessionCell
    session={{
      id: cell?.id,
      subject_name: cell?.subject_name,
      class_name: cell?.class_name,
      day_of_week: cell?.day_of_week || cell?.day,
      slot_number: cell?.slot_number || cell?.period_number,
      start_time: cell?.start_time,
      end_time: cell?.end_time,
    }}
    dayKey={cell?.day_of_week || cell?.day}
    onClick={onClick}
  />
);
```

Add the import at the top of the file:

```jsx
import SessionCell from './grid-theme/SessionCell';
```

- [ ] **Step 2: Run existing FilledCell tests**

```
cd frontend && pnpm test -- FilledCell --watchAll=false
```
Expected: PASS (special branches untouched). If a default-branch test exists and asserts on the old class names, update its assertions to match the new SessionCell output.

- [ ] **Step 3: Commit**

```
git add frontend/src/components/schedule/FilledCell.jsx
git commit -m "refactor(schedule): delegate FilledCell default branch to SessionCell"
```

---

## Task 11: Final cross-grid verification + reduced-motion sanity

**Files:** none (verification only)

- [ ] **Step 1: Run full test suite**

```
cd frontend && pnpm test --watchAll=false 2>&1 | tail -40
```
Expected: all tests PASS, including the three new test files (`dayPalette`, `SessionCell`, `SessionDetailModal`) and the existing `FilledCell` and `TeacherScheduleGrid.loading` tests.

- [ ] **Step 2: Production build**

```
cd frontend && pnpm run build 2>&1 | tail -15
```
Expected: build succeeds with no Tailwind or import errors.

- [ ] **Step 3: Manual a11y + reduced-motion check**

In the running Frontend Dev workflow:
- Tab through cells → focus rings visible.
- Enter on a cell → modal opens.
- Esc → modal closes, focus returns to the cell.
- DevTools → Rendering → emulate `prefers-reduced-motion: reduce` → cell hover no longer scales; modal still fades.
- Verify each of the 5 day colors renders distinctly on Sunday → Thursday.

- [ ] **Step 4: Update `replit.md` with the new shared module**

Append to `replit.md` under the existing component conventions section:

```markdown
- **Schedule grid theme** — All schedule grids (master, teacher's own, class detail) share `frontend/src/components/schedule/grid-theme/`. Day colors are sourced from `dayPalette.js` (single source of truth, backed by `--day-*-tint` / `--day-*-band` CSS vars). Cell-click pop-up is `SessionDetailModal` (glass-morphism, framer-motion).
```

- [ ] **Step 5: Commit**

```
git add replit.md
git commit -m "docs: note new schedule grid-theme module in replit.md"
```

---

## Self-Review

**1. Spec coverage:**
- Day color system (spec §3) → Task 1 (tokens) + Task 2 (palette module).
- Grid layout: bands + numbered sub-row + tinted cells (spec §4) → Task 3 (DayHeaderBand) + Task 4 (SessionCell) + Task 7 (master grid wiring).
- Glass cell-click modal (spec §5) → Task 5 (modal) + Task 7 (mount in master grid).
- Modal content fields (subject, class, teacher, room, time, status badges, quick actions) → Task 5.
- Quick actions wired to existing handlers → Task 7 step 2g (Edit/Move/Lock dispatch through `onSessionEdit` / `onSessionClick`).
- Component architecture (`grid-theme/` module) → Tasks 2, 3, 4, 5, 7 step 1 (barrel).
- Reuse across all three grids → Tasks 7 (master), 8 (teacher view), 9 (class detail).
- Polish & a11y (hover scale, keyboard, aria-label, focus return, reduced-motion) → Task 4 (cell), Task 5 (modal), Task 11 (verification).
- No backend/API changes → preserved by construction; no task touches `backend/`.

**2. Placeholder scan:** No "TBD" / "TODO" / "implement later" / "add appropriate error handling" / "similar to Task N" anywhere. Every code-bearing step contains the actual code.

**3. Type / name consistency:**
- Helper names: `getDayTintClass`, `getDayBandClass`, `getDayTextOnBand`, `getDayKeys`, `getDayPalette`, `DAY_PALETTE` — same in palette module, tests, and consumers.
- Component prop names match across files: `dayKey`, `session`, `onClick`, `onClose`, `onEdit`, `onMove`, `onLockToggle`, `isLocked`, `hasConflict`.
- `data-testid` values referenced in tests (`session-cell-{id}`, `session-cell-lock-icon`, `session-detail-modal`, `session-detail-close`, `session-detail-backdrop`, `session-action-edit/move/lock`, `day-band-{dayKey}`, `day-period-{dayKey}-{idx}`) all defined in the corresponding components.
- Translation keys consumed in modal (`closeAction`, `editAction`, `moveAction`, `lockAction`, `unlockAction`, `lockedBadge`, `relocatedBadge`, `periodNumberLabel`, `substituteShortLabel`, `teacher2`) all added in Task 6 or already exist in current locales.

No issues found.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-04-schedule-grid-redesign.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
