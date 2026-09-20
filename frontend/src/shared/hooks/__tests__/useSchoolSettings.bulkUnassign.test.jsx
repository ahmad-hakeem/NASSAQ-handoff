import { act, renderHook, waitFor } from '@testing-library/react';
import { useSchoolSettings } from '../useSchoolSettings';

const mockNavigate = jest.fn();
const mockApi = { get: jest.fn(), post: jest.fn(), put: jest.fn(), delete: jest.fn() };
const mockAuth = { api: mockApi, user: { id: 'principal-1' } };
const mockError = jest.fn();
const mockWarning = jest.fn();
const mockToastSuccess = jest.fn();
let mockSearch = '?tab=settings&sub=teacher-assignments';

jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
  useLocation: () => ({ pathname: '/principal/schedule', search: mockSearch }),
}), { virtual: true });
jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => mockAuth,
}));
jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqWarning: mockWarning,
    nassaqConfirm: jest.fn(),
    nassaqError: mockError,
  }),
}));
jest.mock('sonner', () => ({ toast: { success: (...args) => mockToastSuccess(...args) } }));
jest.mock('@dnd-kit/core', () => ({
  PointerSensor: function PointerSensor() {},
  useSensor: () => ({}),
  useSensors: () => [],
}));

const assignments = [
  { id: 'a1', teacher_id: 't1', class_id: 'c1' },
  { id: 'a2', teacher_id: 't1', class_id: 'c2' },
];

function responseFor(url) {
  if (url.startsWith('/teacher-class-assignments')) return { data: { data: assignments } };
  if (url === '/school/info') return { data: { id: 'school-1' } };
  if (url.includes('/hard-constraints')) return { data: { hard_constraints: [] } };
  if (url.includes('/soft-constraints')) return { data: { soft_constraints: [] } };
  if (url.includes('/unavailability')) return { data: { items: [] } };
  if (url.includes('/custom-soft-constraints')) return { data: { constraints: [] } };
  if (url.includes('/constraint-patterns')) return { data: { builtin_patterns: [], custom_patterns: [] } };
  if (url.includes('/other-duties')) return { data: { duties: [] } };
  return { data: [] };
}

describe('useSchoolSettings bulk class unassignment', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSearch = '?tab=settings&sub=teacher-assignments';
    mockApi.get.mockImplementation(async url => responseFor(url));
    mockApi.post.mockResolvedValue({ data: { removed_count: 2 } });
  });

  it('uses the teacher bulk endpoint, reloads assignments, and reports success', async () => {
    const { result } = renderHook(() => useSchoolSettings());
    await act(async () => {
      await result.current.unassignAllClassesForTeacher('t1');
    });

    expect(mockApi.post).toHaveBeenCalledWith(
      '/teacher-class-assignments/unassign-teacher',
      { teacher_id: 't1' },
    );
    expect(mockApi.get).toHaveBeenCalledWith('/teacher-class-assignments?page_size=20000');
    expect(mockToastSuccess).toHaveBeenCalledWith('تم إلغاء إسناد جميع الفصول عن المعلم بنجاح.');
  });

  it('keeps assignments and exposes an error if global reset fails', async () => {
    const { result } = renderHook(() => useSchoolSettings());
    await act(async () => {
      await result.current.loadClassAssignments();
    });
    mockApi.post.mockRejectedValueOnce(new Error('network'));
    await act(async () => {
      await result.current.unassignAllClassAssignments();
    });

    expect(mockApi.post).toHaveBeenCalledWith('/teacher-class-assignments/unassign-all', {});
    expect(result.current.classAssignments).toEqual(assignments);
    expect(mockError).toHaveBeenCalled();
  });

  it('blocks duplicate bulk requests while one is pending', async () => {
    let resolveRequest;
    mockApi.post.mockImplementationOnce(() => new Promise(resolve => { resolveRequest = resolve; }));
    const { result } = renderHook(() => useSchoolSettings());

    let first;
    act(() => {
      first = result.current.unassignAllClassAssignments();
      result.current.unassignAllClassAssignments();
    });
    expect(mockApi.post).toHaveBeenCalledTimes(1);
    expect(result.current.classAssignmentsBulkLoading).toBe(true);

    await act(async () => {
      resolveRequest({ data: { removed_count: 2 } });
      await first;
    });
    await waitFor(() => expect(result.current.classAssignmentsBulkLoading).toBe(false));
  });

  it('clears both panels and warns when mutation succeeds but canonical reload fails', async () => {
    const { result } = renderHook(() => useSchoolSettings());
    await act(async () => {
      await result.current.loadClassAssignments();
    });
    await waitFor(() => expect(result.current.classAssignments).toEqual(assignments));

    mockApi.get.mockImplementation(async url => {
      if (url.startsWith('/teacher-class-assignments')) throw new Error('refresh failed');
      return responseFor(url);
    });
    await act(async () => {
      await result.current.unassignAllClassesForTeacher('t1');
    });

    await waitFor(() => expect(result.current.classAssignments).toEqual([]));
    expect(mockToastSuccess).toHaveBeenCalledWith('تم إلغاء إسناد جميع الفصول عن المعلم بنجاح.');
    expect(mockWarning).toHaveBeenCalledWith(expect.stringContaining('تم إلغاء الإسنادات'));
    expect(mockError).not.toHaveBeenCalled();
    expect(mockApi.post).toHaveBeenCalledTimes(1);
  });

  it('does not repeatedly refetch when the canonical assignment set is empty', async () => {
    mockSearch = '?tab=teacher-assignments';
    mockApi.get.mockImplementation(async url => {
      if (url.startsWith('/teacher-class-assignments')) return { data: { data: [] } };
      return responseFor(url);
    });

    const { result } = renderHook(() => useSchoolSettings());
    await waitFor(() => expect(result.current.classAssignmentsLoaded).toBe(true));
    await act(async () => {
      await Promise.resolve();
    });

    expect(mockApi.get.mock.calls.filter(([url]) => url.startsWith('/teacher-class-assignments'))).toHaveLength(1);
  });
});