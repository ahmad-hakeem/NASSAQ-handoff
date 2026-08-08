/**
 * Task #142 — MasterMatrix layout regression guard.
 *
 * يحرس هذا الملف القرارات البصرية لإعادة تصميم مصفوفة "إدارة الجداول
 * الذكية" (الوضع اليومي/الأسبوعي + هيكل التحميل + فاصل الأيام في
 * الوضع الأسبوعي). الاختبارات لا تعتمد على الراوتر/AuthContext؛ نستورد
 * MasterMatrix و MasterMatrixSkeleton كصادرات مُسمّاة من SchedulePageNew
 * ونغلِّفهما بـThemeProvider فقط، فيظلّ كل اختبار سريعاً وموثوقاً.
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';

// SchedulePageNew transitively imports react-router-dom v7 (ESM-only) and
// AuthContext; we only need MasterMatrix/MasterMatrixSkeleton here, so we
// stub the providers/router so jest never resolves them.
jest.mock('react-router-dom', () => ({
  useNavigate: () => () => {},
  useLocation: () => ({ pathname: '/', search: '', hash: '', state: null }),
  Link: ({ children }) => children,
}), { virtual: true });
jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({ user: null, api: { get: jest.fn() } }),
}));

import { ThemeProvider } from '@/shared/contexts/ThemeContext';
import {
  MasterMatrix,
  MasterMatrixSkeleton,
} from '../../../pages/SchedulePageNew';

const DAYS = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday'];
const DAY_LABEL_MAP = {
  sunday: 'الأحد',
  monday: 'الإثنين',
  tuesday: 'الثلاثاء',
  wednesday: 'الأربعاء',
  thursday: 'الخميس',
};
const PERIODS = [1, 2, 3, 4, 5, 6, 7];

const TEACHERS = [
  {
    id: 't-1',
    full_name: 'أحمد المعلم',
    subject: 'رياضيات',
    rank: 'معلم',
    weekly_quota: 24,
    assigned_periods: 20,
    is_absent_today: false,
  },
  {
    id: 't-2',
    full_name: 'سارة الفاضل',
    subject: 'علوم',
    rank: 'معلم',
    weekly_quota: 22,
    assigned_periods: 18,
    is_absent_today: false,
  },
];

const CELLS = {
  't-1': {
    sunday: {
      1: {
        session_id: 's-1',
        class_id: 'c-1',
        class_name: '٣ علوم',
        subject_id: 'sb-1',
        subject_name: 'رياضيات',
        is_vacant: false,
      },
    },
  },
};

const renderMatrix = (props = {}) =>
  render(
    <ThemeProvider>
      <MasterMatrix
        teachers={TEACHERS}
        cells={CELLS}
        days={DAYS}
        periods={PERIODS}
        dayLabelMap={DAY_LABEL_MAP}
        today="sunday"
        periodTimes={{ 1: { start: '07:00', end: '07:45' } }}
        viewMode="weekly"
        selectedDay="sunday"
        onVacantClick={() => {}}
        {...props}
      />
    </ThemeProvider>,
  );

describe('MasterMatrix — daily vs weekly layout (Task #142)', () => {
  test('renders the weekly variant with 5 day-band headers and a sticky teacher column', () => {
    renderMatrix({ viewMode: 'weekly' });
    const root = screen.getByTestId('master-matrix-weekly');
    expect(root).toBeInTheDocument();
    DAYS.forEach((d) => {
      expect(screen.getByTestId(`master-matrix-day-band-${d}`)).toBeInTheDocument();
    });
    // The teacher column is rendered for every teacher row.
    expect(screen.getByTestId('master-matrix-teacher-t-1')).toBeInTheDocument();
    expect(screen.getByTestId('master-matrix-teacher-t-2')).toBeInTheDocument();
  });

  test('teacher column cells are sticky on the inline-start edge', () => {
    renderMatrix({ viewMode: 'weekly' });
    const teacherCell = screen.getByTestId('master-matrix-teacher-t-1');
    // Sticky class + inline-start anchor pin the teacher column while
    // the rest of the grid scrolls horizontally.
    expect(teacherCell.className).toMatch(/\bsticky\b/);
    expect(teacherCell.style.insetInlineStart).toMatch(/^0(px)?$/);
  });

  test('top-left corner header is sticky on both axes with the highest z-index', () => {
    renderMatrix({ viewMode: 'weekly' });
    const corner = screen.getByTestId('master-matrix-corner');
    // sticky + top:0 + insetInlineStart:0 means it stays in the corner
    // when the grid scrolls in either axis. z-index 30 is above day
    // bands (z-20) and teacher column (z-10). The container — not the
    // page — is the scroll parent, so the corner sticks at top:0 of the
    // container (inline style, not a Tailwind class).
    expect(corner.className).toMatch(/\bsticky\b/);
    expect(corner.style.top).toMatch(/^0(px)?$/);
    expect(corner.style.insetInlineStart).toMatch(/^0(px)?$/);
    expect(corner.style.zIndex).toBe('30');
  });

  test('day-band headers stick to the top with a layered z-index below the corner', () => {
    renderMatrix({ viewMode: 'weekly' });
    const sundayBand = screen.getByTestId('master-matrix-day-band-sunday');
    expect(sundayBand.className).toMatch(/\bsticky\b/);
    // Sticks at top:0 of the scroll container (inline style).
    expect(sundayBand.style.top).toMatch(/^0(px)?$/);
    // z-20: above body cells, below the corner cell (z-30).
    expect(sundayBand.className).toMatch(/\bz-20\b/);
  });

  test('weekly grid template uses a real per-period minimum so the grid can overflow', () => {
    renderMatrix({ viewMode: 'weekly' });
    const root = screen.getByTestId('master-matrix-weekly');
    const tpl = root.style.gridTemplateColumns;
    // 5 days × 7 periods = 35 data columns + the leading teacher column.
    expect(tpl).toMatch(/repeat\(35,\s*minmax\(84px,\s*1fr\)\)/);
    expect(tpl).toMatch(/clamp\(220px/);
  });

  test('weekly mode places a strong inline-start separator on every new day-group', () => {
    renderMatrix({ viewMode: 'weekly' });
    // Monday is the second day → its first-period header cell should
    // carry the day-group separator class. The first-day (Sunday)
    // first-period header must not.
    const mondayBand = screen.getByTestId('master-matrix-day-band-monday');
    expect(mondayBand.className).toMatch(/border-s-2/);
    const sundayBand = screen.getByTestId('master-matrix-day-band-sunday');
    expect(sundayBand.className).not.toMatch(/border-s-2/);
  });

  test('renders the daily variant with a single day band and a wider teacher column', () => {
    renderMatrix({ viewMode: 'daily', selectedDay: 'monday' });
    expect(screen.getByTestId('master-matrix-daily')).toBeInTheDocument();
    expect(screen.getByTestId('master-matrix-day-band-monday')).toBeInTheDocument();
    // The other days are NOT rendered in daily mode.
    expect(screen.queryByTestId('master-matrix-day-band-tuesday')).toBeNull();
    const root = screen.getByTestId('master-matrix-daily');
    const tpl = root.style.gridTemplateColumns;
    // Daily uses a wider teacher column and minmax(0, 1fr) so the grid
    // never overflows horizontally.
    expect(tpl).toMatch(/clamp\(220px/);
    expect(tpl).toMatch(/repeat\(7,\s*minmax\(0,\s*1fr\)\)/);
  });
});

describe('MasterMatrix — daily scroll-ownership (Task #904)', () => {
  // Regression: daily view used to let the whole page scroll because its
  // matrix container was `overflow-visible` and its sticky headers were
  // anchored to the page-level `--sticky-band-h` offset
  // (top: var(--sticky-band-h) / calc(var(--sticky-band-h) + DAY_H)).
  // The fix makes daily adopt weekly's constrained-internal-scroll model:
  // the container is the scroll owner and the corner/day-band/period-head
  // cells stick relative to THAT container (top:0 and top:DAY_HEADER_HEIGHT),
  // never to the page band. These guards assert daily headers anchor to the
  // container and never reintroduce the `--sticky-band-h` / calc offset.
  test('daily corner + day-band stick at top:0 of the container (no page band offset)', () => {
    renderMatrix({ viewMode: 'daily', selectedDay: 'monday' });
    const corner = screen.getByTestId('master-matrix-corner');
    const mondayBand = screen.getByTestId('master-matrix-day-band-monday');
    // top:0 (container-relative), not var(--sticky-band-h).
    expect(corner.style.top).toMatch(/^0(px)?$/);
    expect(mondayBand.style.top).toMatch(/^0(px)?$/);
    // Must never fall back to the page-level band offset.
    expect(corner.style.top).not.toMatch(/sticky-band-h/);
    expect(corner.style.top).not.toMatch(/calc/);
    expect(mondayBand.style.top).not.toMatch(/sticky-band-h/);
  });

  test('daily period-number header sticks at DAY_HEADER_HEIGHT (40px), not the band + calc offset', () => {
    renderMatrix({ viewMode: 'daily', selectedDay: 'monday' });
    // Daily DAY_HEADER_HEIGHT is 40px (weekly is 36px); the period row
    // stacks directly beneath the day band inside the container.
    const periodHead = screen.getByTestId('master-matrix-period-head-monday-1');
    expect(periodHead.style.top).toBe('40px');
    expect(periodHead.style.top).not.toMatch(/sticky-band-h/);
    expect(periodHead.style.top).not.toMatch(/calc/);
  });

  test('weekly period-number header still sticks at DAY_HEADER_HEIGHT (36px) — unchanged', () => {
    renderMatrix({ viewMode: 'weekly' });
    // Weekly behavior must be byte-for-byte identical: day band at top:0,
    // period row at the weekly day-header height (36px).
    const periodHead = screen.getByTestId('master-matrix-period-head-sunday-1');
    expect(periodHead.style.top).toBe('36px');
    expect(periodHead.style.top).not.toMatch(/sticky-band-h/);
  });
});

describe('MasterMatrix — row-height contract (first-row alignment regression)', () => {
  // Regression: the first visible teacher row used to render its lesson
  // cells with a fixed `height: 88px` while the sticky teacher cell used
  // `minHeight: 88px`. Whenever the teacher card grew (absence buttons,
  // long subject text), the grid track stretched but the lesson cells
  // stayed anchored to 88px at the top of the track — visually shorter
  // than the next teacher row and clipping the teacher name on the
  // sticky column. Both cells must now share `minHeight: ROW_HEIGHT`
  // and rely on CSS grid `align-items: stretch` to stay in lockstep.
  test('teacher cell and lesson cells in the same row share a single minHeight contract (no fixed height)', () => {
    renderMatrix({ viewMode: 'weekly' });
    const teacherCell = screen.getByTestId('master-matrix-teacher-t-1');
    const lessonCell = screen.getByTestId('master-matrix-cell-t-1-sunday-1');

    // Teacher column uses minHeight, never an explicit height.
    expect(teacherCell.style.minHeight).toBe('88px');
    expect(teacherCell.style.height).toBe('');

    // Lesson cells must mirror that contract — minHeight, no fixed
    // height. A fixed height would re-introduce the first-row drift
    // bug because the cell would refuse to stretch when the teacher
    // card grows the row track.
    expect(lessonCell.style.minHeight).toBe('88px');
    expect(lessonCell.style.height).toBe('');
  });

  test('every lesson cell across every teacher row uses the same row-height contract', () => {
    renderMatrix({ viewMode: 'weekly' });
    // Sweep all teacher rows so a future regression on row 1 only
    // (the original bug shape) can never reappear silently.
    for (const teacher of TEACHERS) {
      for (const day of DAYS) {
        for (const p of PERIODS) {
          const cell = screen.getByTestId(
            `master-matrix-cell-${teacher.id}-${day}-${p}`,
          );
          expect(cell.style.minHeight).toBe('88px');
          expect(cell.style.height).toBe('');
        }
      }
    }
  });
});

describe('MasterMatrix — cell interactions (Task #142)', () => {
  test('clicking a filled session cell opens the read-only SessionDetailModal', () => {
    renderMatrix({ viewMode: 'weekly' });
    // The filled cell exposed via SessionCell renders as a button.
    const filled = screen.getByRole('button', { name: /رياضيات/ });
    fireEvent.click(filled);
    // SessionDetailModal mounts a portal-less node with this testid.
    expect(screen.getByTestId('session-detail-modal')).toBeInTheDocument();
  });

  test('clicking a vacant cell invokes onVacantClick with the cell payload, not the modal', () => {
    const onVacantClick = jest.fn();
    const VACANT_CELLS = {
      't-1': {
        sunday: {
          1: {
            session_id: 's-vac',
            class_id: 'c-1',
            class_name: '٣ علوم',
            subject_id: 'sb-1',
            subject_name: 'رياضيات',
            is_vacant: true,
          },
        },
      },
    };
    renderMatrix({
      viewMode: 'weekly',
      cells: VACANT_CELLS,
      onVacantClick,
    });
    const vacant = screen.getByRole('button', { name: /شاغرة/ });
    fireEvent.click(vacant);
    expect(onVacantClick).toHaveBeenCalledTimes(1);
    expect(onVacantClick.mock.calls[0][0]).toMatchObject({
      teacher_id: 't-1',
      day_of_week: 'sunday',
      period_number: 1,
    });
    // The modal must NOT open for vacant clicks (it's a different flow:
    // the parent opens the substitute candidates drawer instead).
    expect(screen.queryByTestId('session-detail-modal')).toBeNull();
  });
});

describe('MasterMatrix — page-level skeleton swap during live refetches (Task #142)', () => {
  // The matrix region must swap to MasterMatrixSkeleton on EVERY
  // refetch (pagination, day change, refresh, post-mutation reload),
  // not only on first load. The page chrome (header, KPIs, tabs)
  // stays mounted around it. We simulate the page-level pattern
  // (chrome + matrix region) and assert the swap.
  const PageShell = ({ loading, grid }) => (
    <ThemeProvider>
      <div data-testid="page-chrome">chrome stays mounted</div>
      {loading ? (
        <MasterMatrixSkeleton
          rows={3}
          days={grid?.days?.length || 5}
          periods={grid?.periods?.length || 7}
          isDaily={false}
        />
      ) : (
        <MasterMatrix
          teachers={TEACHERS}
          cells={CELLS}
          days={DAYS}
          periods={PERIODS}
          dayLabelMap={DAY_LABEL_MAP}
          today="sunday"
          periodTimes={[]}
          viewMode="weekly"
          selectedDay="sunday"
          onVacantClick={() => {}}
          onUndoAbsence={() => {}}
          onBulkCoverClick={() => {}}
          onAcknowledgeRelocation={() => {}}
          totalTeachers={2}
          unresolvedConflicts={[]}
        />
      )}
    </ThemeProvider>
  );

  test('chrome stays mounted while the matrix region swaps to the skeleton', () => {
    const { rerender } = render(<PageShell loading={false} grid={{ days: DAYS, periods: PERIODS }} />);
    expect(screen.getByTestId('page-chrome')).toBeInTheDocument();
    expect(screen.getByTestId('master-matrix-weekly')).toBeInTheDocument();
    expect(screen.queryByTestId('master-matrix-skeleton')).toBeNull();

    // Live refetch (e.g. pagination change) — page flips loading=true.
    rerender(<PageShell loading={true} grid={{ days: DAYS, periods: PERIODS }} />);
    // Chrome MUST still be mounted.
    expect(screen.getByTestId('page-chrome')).toBeInTheDocument();
    // Matrix swapped out for the structural skeleton.
    expect(screen.queryByTestId('master-matrix-weekly')).toBeNull();
    expect(screen.getByTestId('master-matrix-skeleton')).toBeInTheDocument();
    // The skeleton announces itself as a status region for screen readers.
    expect(screen.getByRole('status')).toBeInTheDocument();
  });
});

describe('MasterMatrixSkeleton — standardized loading state', () => {
  test('exposes an accessible status role with a localized label', () => {
    render(
      <ThemeProvider>
        <MasterMatrixSkeleton rows={4} days={5} periods={7} isDaily={false} />
      </ThemeProvider>,
    );
    const root = screen.getByTestId('master-matrix-skeleton');
    expect(root).toBeInTheDocument();
    expect(root).toHaveAttribute('role', 'status');
    expect(root).toHaveAttribute('aria-label');
  });

  test('reserves matrix-sized vertical space so the layout does not jump', () => {
    render(
      <ThemeProvider>
        <MasterMatrixSkeleton rows={2} days={1} periods={7} isDaily={true} />
      </ThemeProvider>,
    );
    const root = screen.getByTestId('master-matrix-skeleton');
    expect(parseInt(root.style.minHeight, 10)).toBeGreaterThan(0);
  });
});
