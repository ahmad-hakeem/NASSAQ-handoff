/**
 * CI plan Task 11 — component coverage for the teacher→class drag-assignment
 * page (TeacherClassAssignmentPage.jsx). No prior test exercised this flow.
 *
 * @dnd-kit drag gestures can't be simulated reliably in jsdom, so DndContext
 * is mocked to CAPTURE the page's onDragEnd handler; tests invoke it with the
 * same event shape dnd-kit produces ({active.data.current.teacher,
 * over.data.current.classItem}) — the exact contract handleDragEnd reads.
 * Covered: initial load render, drop → POST + optimistic UI, duplicate-drop
 * guard (warning dialog, no POST), and assignment removal → DELETE.
 */
import React from 'react';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import TeacherClassAssignmentPage from '@/features/teachers/pages/TeacherClassAssignmentPage';

// ── captured dnd-kit handlers ────────────────────────────────────────
let capturedOnDragEnd = null;
let capturedOnDragStart = null;

jest.mock('@dnd-kit/core', () => ({
  DndContext: ({ children, onDragEnd, onDragStart }) => {
    capturedOnDragEnd = onDragEnd;
    capturedOnDragStart = onDragStart;
    return <div data-testid="dnd-context">{children}</div>;
  },
  DragOverlay: ({ children }) => <div>{children}</div>,
  useDraggable: () => ({ attributes: {}, listeners: {}, setNodeRef: () => {}, transform: null }),
  useDroppable: () => ({ setNodeRef: () => {}, isOver: false }),
  closestCenter: jest.fn(),
}));

jest.mock('@/shared/components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div>{children}</div>,
}));

const mockNavigate = jest.fn();
jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}), { virtual: true });

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() },
}));

const mockNassaqWarning = jest.fn();
const mockNassaqError = jest.fn();
jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ nassaqWarning: mockNassaqWarning, nassaqError: mockNassaqError }),
}));

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({
    isRTL: true,
    isDark: false,
    language: 'ar',
    theme: 'light',
    toggleTheme: () => {},
    toggleLanguage: () => {},
    setLanguage: () => {},
    setTheme: () => {},
  }),
  useTranslation: () => ({ t: (k) => k }),
}));

jest.mock('@/shared/hooks/useCanViewInternalIds', () => ({
  useCanViewInternalIds: () => false,
}));

// Stable module-level api object (CRA resetMocks wipes impls — reinstall in
// beforeEach; the OBJECT identity must stay stable for useCallback deps).
const mockApi = { get: jest.fn(), post: jest.fn(), delete: jest.fn() };
jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({ api: mockApi }),
}));

const { toast } = require('sonner');

const TEACHERS = [
  { id: 't1', full_name: 'أحمد المعلم', specialization: 'math' },
  { id: 't2', full_name: 'سالم المعلم', specialization: 'science' },
];
const CLASSES = [
  { id: 'c1', name: 'الأول أ', section: 'أ' },
  { id: 'c2', name: 'الثاني ب', section: 'ب' },
];
const EXISTING_ASSIGNMENT = { id: 'a1', teacher_id: 't2', class_id: 'c2', teacher_name: 'سالم المعلم' };

function installApiMocks({ assignments = [EXISTING_ASSIGNMENT] } = {}) {
  mockApi.get.mockImplementation((url) => {
    if (url === '/teachers') return Promise.resolve({ data: TEACHERS });
    if (url === '/classes') return Promise.resolve({ data: CLASSES });
    if (url.startsWith('/teacher-class-assignments')) return Promise.resolve({ data: { data: assignments } });
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
  mockApi.post.mockResolvedValue({
    data: { assignment: { id: 'a-new', teacher_id: 't1', class_id: 'c1', teacher_name: 'أحمد المعلم' } },
  });
  mockApi.delete.mockResolvedValue({ data: { ok: true } });
}

async function renderPage(opts) {
  installApiMocks(opts);
  render(<TeacherClassAssignmentPage />);
  await waitFor(() => expect(screen.getByTestId('teacher-class-assignment-page')).toBeInTheDocument());
}

const dragEvent = (teacherId, classId) => ({
  active: { data: { current: { teacher: TEACHERS.find((t) => t.id === teacherId) } } },
  over: { data: { current: { classItem: CLASSES.find((c) => c.id === classId) } } },
});

describe('TeacherClassAssignmentPage drag-assignment (CI Task 11)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    capturedOnDragEnd = null;
    capturedOnDragStart = null;
  });

  test('loads and renders teachers, classes, and existing assignments', async () => {
    await renderPage();
    expect(screen.getByTestId('teacher-card-t1')).toBeInTheDocument();
    expect(screen.getByTestId('teacher-card-t2')).toBeInTheDocument();
    expect(screen.getByTestId('class-box-c1')).toBeInTheDocument();
    // Existing assignment rendered inside its class box with a remove button.
    expect(screen.getByTestId('remove-assignment-a1')).toBeInTheDocument();
    expect(typeof capturedOnDragEnd).toBe('function');
    expect(typeof capturedOnDragStart).toBe('function');
  });

  test('dropping a teacher on a class POSTs the assignment and updates the UI', async () => {
    await renderPage();
    await act(async () => {
      await capturedOnDragEnd(dragEvent('t1', 'c1'));
    });
    expect(mockApi.post).toHaveBeenCalledTimes(1);
    expect(mockApi.post).toHaveBeenCalledWith('/teacher-class-assignments', {
      teacher_id: 't1',
      class_id: 'c1',
    });
    // Optimistic UI: the new assignment's remove button appears in class c1.
    expect(screen.getByTestId('remove-assignment-a-new')).toBeInTheDocument();
    expect(toast.success).toHaveBeenCalled();
  });

  test('dropping an already-assigned teacher warns and does NOT POST', async () => {
    await renderPage();
    await act(async () => {
      await capturedOnDragEnd(dragEvent('t2', 'c2'));
    });
    expect(mockApi.post).not.toHaveBeenCalled();
    expect(mockNassaqWarning).toHaveBeenCalledWith('هذا المعلم مسند بالفعل لهذا الفصل');
  });

  test('drop with no target (over=null) is a no-op', async () => {
    await renderPage();
    await act(async () => {
      await capturedOnDragEnd({ active: { data: { current: {} } }, over: null });
    });
    expect(mockApi.post).not.toHaveBeenCalled();
    expect(mockNassaqWarning).not.toHaveBeenCalled();
  });

  test('removing an assignment DELETEs it and drops it from the UI', async () => {
    await renderPage();
    await act(async () => {
      fireEvent.click(screen.getByTestId('remove-assignment-a1'));
    });
    await waitFor(() => expect(mockApi.delete).toHaveBeenCalledWith('/teacher-class-assignments/a1'));
    await waitFor(() => expect(screen.queryByTestId('remove-assignment-a1')).not.toBeInTheDocument());
    expect(toast.success).toHaveBeenCalled();
  });
});
