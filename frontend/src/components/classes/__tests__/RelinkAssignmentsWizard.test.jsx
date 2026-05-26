/**
 * Task #648 — RelinkAssignmentsWizard test coverage.
 *
 * Pins the wizard contract used by ClassesPage after a soft-deleted class
 * is restored:
 *
 *   1. The wizard fetches `/classes/{id}/relink-candidates` exactly once
 *      when it opens and pre-selects every previewed row.
 *   2. "Clear all" per group empties that group's selection, the chosen
 *      counter updates, and the apply-selected button disables when 0.
 *   3. "Select all" puts the per-row selection back in full and the apply
 *      call POSTs the chosen ids to `/classes/{id}/relink/{table}`.
 *   4. Toggling a single checkbox flips just that row.
 *   5. "Reactivate all" POSTs `{all: true}` (not the ids array) for every
 *      non-empty group and skips empty groups entirely.
 *   6. When the candidates response is empty, the apply buttons are not
 *      rendered (the only path forward is "Skip").
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';

jest.mock('react-dom', () => {
  const actual = jest.requireActual('react-dom');
  return { ...actual, createPortal: (node) => node };
});

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

jest.mock('../../../contexts/ThemeContext', () => ({
  useTranslation: () => ({ t: (k) => k }),
}));

const mockNassaqError = jest.fn();
jest.mock('../../ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ nassaqError: mockNassaqError }),
}));

import RelinkAssignmentsWizard from '../RelinkAssignmentsWizard';
import { toast } from 'sonner';

const CLASS_ID = 'cls-1';

const _candidatesPayload = (overrides = {}) => ({
  data: {
    class_id: CLASS_ID,
    groups: {
      teacher_assignments: { count: 0, preview_limit: 200, items: [] },
      teacher_class_assignments: { count: 0, preview_limit: 200, items: [] },
      class_subjects: {
        count: 2,
        preview_limit: 200,
        items: [
          { id: 'cs-1', subject_id: 'math', subject_name: 'Math', weekly_periods: 4 },
          { id: 'cs-2', subject_id: 'sci', subject_name: 'Science', weekly_periods: 3 },
        ],
      },
      timetable_sessions: { count: 0, preview_limit: 200, items: [] },
      class_sessions: { count: 0, preview_limit: 200, items: [] },
      curriculum_lessons: {
        count: 1,
        preview_limit: 200,
        items: [{ id: 'cl-1', title: 'Intro', week: 1, subject_id: 'math' }],
      },
      ...overrides,
    },
  },
});

const _makeApi = ({ candidates } = {}) => ({
  get: jest.fn().mockResolvedValue(candidates ?? _candidatesPayload()),
  post: jest.fn().mockResolvedValue({ data: { success: true, reactivated: 1 } }),
});

const _flush = async () => {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
};

// `api.get` resolving is not enough — the wizard still has to re-render
// with the new groups and exit the loading branch. Tests wait for the
// "apply" footer button (which only renders once loading=false and
// totals.total > 0) before interacting with the accordion contents.
const _waitForLoaded = () =>
  waitFor(() => expect(screen.getByTestId('relink-apply-selected')).toBeInTheDocument());

beforeEach(() => {
  mockNassaqError.mockReset();
  toast.success.mockReset();
  toast.error.mockReset();
});

describe('RelinkAssignmentsWizard', () => {
  test('fetches candidates once on open and pre-selects every previewed row', async () => {
    const api = _makeApi();
    const onOpenChange = jest.fn();
    render(
      <RelinkAssignmentsWizard
        open
        onOpenChange={onOpenChange}
        classId={CLASS_ID}
        api={api}
      />,
    );

    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(1));
    expect(api.get).toHaveBeenCalledWith(`/classes/${CLASS_ID}/relink-candidates`);

    await _waitForLoaded();
    // All previewed rows start checked. There are 3 rows total (2 + 1).
    const checked = screen
      .getAllByRole('checkbox')
      .filter((c) => c.getAttribute('data-state') === 'checked');
    expect(checked).toHaveLength(3);

    // The apply-selected button shows the total chosen count (3).
    expect(screen.getByTestId('relink-apply-selected')).toHaveTextContent('(3)');
  });

  test('clear-all empties one group, toggling a row flips only that row', async () => {
    const api = _makeApi();
    render(
      <RelinkAssignmentsWizard
        open
        onOpenChange={jest.fn()}
        classId={CLASS_ID}
        api={api}
      />,
    );
    await _waitForLoaded();

    // Clear-all on class_subjects (the first "relinkClearAll" button is the
    // class_subjects accordion, which renders before curriculum_lessons in
    // GROUP_ORDER).
    const clearButtons = screen.getAllByRole('button', { name: /relinkClearAll/, hidden: true });
    fireEvent.click(clearButtons[0]);

    // 2 cleared + 1 still on (curriculum_lessons) → button shows (1)
    expect(screen.getByTestId('relink-apply-selected')).toHaveTextContent('(1)');

    // Per-row toggle: re-check exactly one class_subjects row by clicking
    // its checkbox directly (queried via its stable label-for id).
    const cs1 = document.getElementById('relink-class_subjects-cs-1');
    const row1Checkbox = cs1.parentElement.querySelector('button[role="checkbox"]');
    fireEvent.click(row1Checkbox);
    expect(screen.getByTestId('relink-apply-selected')).toHaveTextContent('(2)');

    // The other class_subjects row stays unchecked.
    const cs2 = document.getElementById('relink-class_subjects-cs-2');
    const row2Checkbox = cs2.parentElement.querySelector('button[role="checkbox"]');
    expect(row2Checkbox.getAttribute('data-state')).toBe('unchecked');
  });

  test('apply-selected POSTs the chosen ids and skips empty groups', async () => {
    const api = _makeApi();
    const onOpenChange = jest.fn();
    const onDone = jest.fn();
    render(
      <RelinkAssignmentsWizard
        open
        onOpenChange={onOpenChange}
        classId={CLASS_ID}
        api={api}
        onDone={onDone}
      />,
    );
    await _waitForLoaded();

    // Default pre-selection: 2 class_subjects + 1 curriculum_lessons.
    await act(async () => {
      fireEvent.click(screen.getByTestId('relink-apply-selected'));
      await _flush();
    });

    // Two POSTs: one per non-empty group. Empty groups skipped entirely.
    expect(api.post).toHaveBeenCalledTimes(2);
    expect(api.post).toHaveBeenCalledWith(
      `/classes/${CLASS_ID}/relink/class_subjects`,
      { ids: ['cs-1', 'cs-2'] },
    );
    expect(api.post).toHaveBeenCalledWith(
      `/classes/${CLASS_ID}/relink/curriculum_lessons`,
      { ids: ['cl-1'] },
    );
    // Empty groups must NEVER produce a POST.
    const paths = api.post.mock.calls.map(([p]) => p);
    expect(paths).not.toEqual(
      expect.arrayContaining([
        `/classes/${CLASS_ID}/relink/teacher_assignments`,
        `/classes/${CLASS_ID}/relink/timetable_sessions`,
      ]),
    );

    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(onDone).toHaveBeenCalled();
  });

  test('select-all restores the full per-row selection after a clear', async () => {
    const api = _makeApi();
    render(
      <RelinkAssignmentsWizard
        open
        onOpenChange={jest.fn()}
        classId={CLASS_ID}
        api={api}
      />,
    );
    await _waitForLoaded();

    const clearButtons = screen.getAllByRole('button', { name: /relinkClearAll/, hidden: true });
    fireEvent.click(clearButtons[0]); // clear class_subjects
    expect(screen.getByTestId('relink-apply-selected')).toHaveTextContent('(1)');

    const selectAllButtons = screen.getAllByRole('button', { name: /relinkSelectAll/, hidden: true });
    fireEvent.click(selectAllButtons[0]); // re-add class_subjects
    expect(screen.getByTestId('relink-apply-selected')).toHaveTextContent('(3)');
  });

  test('reactivate-all POSTs {all:true} per non-empty group, skipping empties', async () => {
    const api = _makeApi();
    render(
      <RelinkAssignmentsWizard
        open
        onOpenChange={jest.fn()}
        classId={CLASS_ID}
        api={api}
      />,
    );
    await _waitForLoaded();

    await act(async () => {
      fireEvent.click(screen.getByTestId('relink-apply-all'));
      await _flush();
    });

    expect(api.post).toHaveBeenCalledTimes(2);
    expect(api.post).toHaveBeenCalledWith(
      `/classes/${CLASS_ID}/relink/class_subjects`,
      { all: true },
    );
    expect(api.post).toHaveBeenCalledWith(
      `/classes/${CLASS_ID}/relink/curriculum_lessons`,
      { all: true },
    );
  });

  test('renders the empty-state message and no apply buttons when nothing to do', async () => {
    const empty = {
      data: {
        class_id: CLASS_ID,
        groups: {
          teacher_assignments: { count: 0, preview_limit: 200, items: [] },
          teacher_class_assignments: { count: 0, preview_limit: 200, items: [] },
          class_subjects: { count: 0, preview_limit: 200, items: [] },
          timetable_sessions: { count: 0, preview_limit: 200, items: [] },
          class_sessions: { count: 0, preview_limit: 200, items: [] },
          curriculum_lessons: { count: 0, preview_limit: 200, items: [] },
        },
      },
    };
    const api = _makeApi({ candidates: empty });
    render(
      <RelinkAssignmentsWizard
        open
        onOpenChange={jest.fn()}
        classId={CLASS_ID}
        api={api}
      />,
    );
    await waitFor(() => expect(screen.getByText('relinkNothingToDo')).toBeInTheDocument());

    expect(screen.queryByTestId('relink-apply-selected')).toBeNull();
    expect(screen.queryByTestId('relink-apply-all')).toBeNull();
    expect(screen.getByText('relinkSkip')).toBeInTheDocument();
  });
});
