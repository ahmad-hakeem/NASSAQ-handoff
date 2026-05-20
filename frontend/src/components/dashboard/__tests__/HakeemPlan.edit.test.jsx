import React from 'react';
import { render, act, waitFor, screen, fireEvent, within } from '@testing-library/react';

jest.mock('sonner', () => ({ toast: { error: jest.fn() } }));

jest.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: false }),
  useTranslation: () => ({ t: (k) => k }),
}));

jest.mock('../../../utils/hijriDate', () => ({
  formatFullDate: () => ({ full: 'Wednesday, 20 May 2026' }),
}));

// All mock* variables are hoisted by babel-jest alongside jest.mock(), so they
// can be referenced inside the factory function.
const mockApiGet = jest.fn();
const mockApiPatch = jest.fn();
const mockApiPost = jest.fn();
const mockApiDelete = jest.fn();

// Stable object so useCallback([api]) doesn't produce a new fetchTasks reference
// on every re-render (which would re-trigger the useEffect and overwrite state).
const mockStableApi = {
  get: (...args) => mockApiGet(...args),
  patch: (...args) => mockApiPatch(...args),
  post: (...args) => mockApiPost(...args),
  delete: (...args) => mockApiDelete(...args),
};

jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'u1', role: 'principal' },
    api: mockStableApi,
  }),
}));

import { HakeemPlan } from '../HakeemPlan';

const TASK_NORMAL = {
  id: 'task-1',
  title: 'Morning briefing',
  details: '',
  priority: 'normal',
  status: 'active',
  source: 'manual',
  task_date: '2026-05-20',
};

const TASK_URGENT = {
  id: 'task-2',
  title: 'Fire drill prep',
  details: '',
  priority: 'urgent',
  status: 'active',
  source: 'manual',
  task_date: '2026-05-20',
};

function tasksResponse(tasks) {
  return { data: { tasks } };
}

beforeEach(() => {
  mockApiGet.mockReset();
  mockApiPatch.mockReset();
  mockApiPost.mockReset();
  mockApiDelete.mockReset();
  mockApiGet.mockResolvedValue(tasksResponse([TASK_NORMAL, TASK_URGENT]));
  mockApiPatch.mockImplementation((_url, body) =>
    Promise.resolve({ data: { task: { ...TASK_NORMAL, ...body } } })
  );
});

async function renderAndWait() {
  let utils;
  await act(async () => {
    utils = render(<HakeemPlan />);
  });
  await waitFor(() => expect(screen.getByTestId('task-row-task-1')).toBeInTheDocument());
  return utils;
}

describe('HakeemPlan — inline edit with priority', () => {
  test('edit name only: priority stays unchanged, PATCH sends only title', async () => {
    await renderAndWait();

    // Open edit for task-1 (normal priority)
    await act(async () => {
      fireEvent.click(screen.getByTestId('edit-task-task-1'));
    });

    const titleInput = screen.getByTestId('edit-title-input-task-1');
    const prioritySelect = screen.getByTestId('edit-priority-select-task-1');

    // Priority pre-filled with task's current priority
    expect(prioritySelect.value).toBe('normal');

    // Change only the title
    fireEvent.change(titleInput, { target: { value: 'Updated briefing' } });
    expect(prioritySelect.value).toBe('normal'); // still normal

    await act(async () => {
      fireEvent.keyDown(titleInput, { key: 'Enter' });
    });

    await waitFor(() => {
      expect(mockApiPatch).toHaveBeenCalledTimes(1);
      const [, body] = mockApiPatch.mock.calls[0];
      expect(body).toEqual({ title: 'Updated briefing' });
      expect(body.priority).toBeUndefined();
    });
  });

  test('edit priority only: title stays unchanged, PATCH sends only priority', async () => {
    await renderAndWait();

    await act(async () => {
      fireEvent.click(screen.getByTestId('edit-task-task-1'));
    });

    const titleInput = screen.getByTestId('edit-title-input-task-1');
    const prioritySelect = screen.getByTestId('edit-priority-select-task-1');

    // Don't change title — only change priority
    fireEvent.change(prioritySelect, { target: { value: 'urgent' } });

    await act(async () => {
      fireEvent.keyDown(titleInput, { key: 'Enter' });
    });

    await waitFor(() => {
      expect(mockApiPatch).toHaveBeenCalledTimes(1);
      const [, body] = mockApiPatch.mock.calls[0];
      expect(body).toEqual({ priority: 'urgent' });
      expect(body.title).toBeUndefined();
    });
  });

  test('edit both title and priority: PATCH sends both fields', async () => {
    await renderAndWait();

    await act(async () => {
      fireEvent.click(screen.getByTestId('edit-task-task-1'));
    });

    const titleInput = screen.getByTestId('edit-title-input-task-1');
    const prioritySelect = screen.getByTestId('edit-priority-select-task-1');

    fireEvent.change(titleInput, { target: { value: 'New title' } });
    fireEvent.change(prioritySelect, { target: { value: 'medium' } });

    await act(async () => {
      fireEvent.keyDown(titleInput, { key: 'Enter' });
    });

    await waitFor(() => {
      expect(mockApiPatch).toHaveBeenCalledTimes(1);
      const [, body] = mockApiPatch.mock.calls[0];
      expect(body).toEqual({ title: 'New title', priority: 'medium' });
    });
  });

  test('cancel edit (Escape): no PATCH, task unchanged', async () => {
    await renderAndWait();

    await act(async () => {
      fireEvent.click(screen.getByTestId('edit-task-task-1'));
    });

    const titleInput = screen.getByTestId('edit-title-input-task-1');
    const prioritySelect = screen.getByTestId('edit-priority-select-task-1');

    // Make changes, then cancel
    fireEvent.change(titleInput, { target: { value: 'Should not save' } });
    fireEvent.change(prioritySelect, { target: { value: 'urgent' } });

    await act(async () => {
      fireEvent.keyDown(titleInput, { key: 'Escape' });
    });

    expect(mockApiPatch).not.toHaveBeenCalled();

    // Original title is still shown
    await waitFor(() => {
      expect(screen.queryByTestId('edit-title-input-task-1')).not.toBeInTheDocument();
      expect(screen.getByTestId('task-row-task-1')).toHaveTextContent('Morning briefing');
    });
  });

  test('no change: PATCH is skipped when title and priority both unchanged', async () => {
    await renderAndWait();

    await act(async () => {
      fireEvent.click(screen.getByTestId('edit-task-task-1'));
    });

    const titleInput = screen.getByTestId('edit-title-input-task-1');

    // Don't change anything
    await act(async () => {
      fireEvent.keyDown(titleInput, { key: 'Enter' });
    });

    expect(mockApiPatch).not.toHaveBeenCalled();
  });

  test('priority badge reflects updated priority after save', async () => {
    const updatedTask = { ...TASK_NORMAL, priority: 'urgent' };
    mockApiPatch.mockResolvedValue({ data: { task: updatedTask } });

    await renderAndWait();

    // Confirm normal badge is shown initially
    expect(screen.getByTestId('priority-badge-task-1')).toHaveTextContent('Normal');

    // Open edit, change priority, commit — all inside one act so async continuations are flushed
    await act(async () => {
      fireEvent.click(screen.getByTestId('edit-task-task-1'));
    });

    await act(async () => {
      fireEvent.change(screen.getByTestId('edit-priority-select-task-1'), { target: { value: 'urgent' } });
    });

    // Commit via Enter; act wraps the synchronous handler, but the async patch continuation
    // runs in the microtask queue — flush it with a zero-delay tick inside the same act.
    await act(async () => {
      fireEvent.keyDown(screen.getByTestId('edit-title-input-task-1'), { key: 'Enter' });
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    // Badge should show Urgent after optimistic update (patch resolves instantly in test)
    await waitFor(() => {
      expect(screen.getByTestId('priority-badge-task-1')).toHaveTextContent('Urgent');
    });
  });

  test('priority select is pre-filled with the task current priority when edit opens', async () => {
    // task-2 has urgent priority
    await renderAndWait();

    await act(async () => {
      fireEvent.click(screen.getByTestId('edit-task-task-2'));
    });

    const prioritySelect = screen.getByTestId('edit-priority-select-task-2');
    expect(prioritySelect.value).toBe('urgent');
  });
});
