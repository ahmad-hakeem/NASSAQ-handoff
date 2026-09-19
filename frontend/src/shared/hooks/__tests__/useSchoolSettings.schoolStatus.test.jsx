import { act, renderHook, waitFor } from '@testing-library/react';
import { useSchoolSettings } from '../useSchoolSettings';

const mockNavigate = jest.fn();
const mockApiGet = jest.fn();
const mockApi = {
  get: (...args) => mockApiGet(...args),
  put: jest.fn(),
  post: jest.fn(),
  delete: jest.fn(),
};
const mockUser = { id: 'principal-1', tenant_id: 'school-1' };
const mockAuth = { api: mockApi, user: mockUser };
const mockAlerts = {
  nassaqWarning: jest.fn(),
  nassaqConfirm: jest.fn(),
  nassaqError: jest.fn(),
  nassaqSuccess: jest.fn(),
};

jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
  useLocation: () => ({ pathname: '/principal/settings', search: '' }),
}), { virtual: true });

jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => mockAuth,
}));

jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => mockAlerts,
}));

jest.mock('@dnd-kit/core', () => ({
  PointerSensor: function PointerSensor() {},
  useSensor: () => ({}),
  useSensors: () => [],
}));

let currentSchoolStatus;

function responseFor(url) {
  if (url === '/school/info') {
    return { data: { id: 'school-1', name: 'مدرسة الاختبار', status: currentSchoolStatus } };
  }
  if (url.includes('/hard-constraints')) return { data: { hard_constraints: [] } };
  if (url.includes('/soft-constraints')) return { data: { soft_constraints: [] } };
  if (url.includes('/unavailability')) return { data: { items: [] } };
  if (url.includes('/custom-soft-constraints')) return { data: { constraints: [] } };
  if (url.includes('/constraint-patterns')) return { data: { builtin_patterns: [], custom_patterns: [] } };
  if (url.includes('/other-duties')) return { data: { duties: [] } };
  return { data: [] };
}

describe('useSchoolSettings school status refresh', () => {
  beforeEach(() => {
    currentSchoolStatus = 'active';
    mockApiGet.mockReset();
    mockApiGet.mockImplementation(async (url) => responseFor(url));
  });

  it('replaces the displayed school status when settings are refreshed', async () => {
    const { result } = renderHook(() => useSchoolSettings());
    await waitFor(() => expect(result.current.schoolInfo.status).toBe('active'));

    currentSchoolStatus = 'suspended';
    await act(async () => {
      await result.current.fetchData();
    });

    expect(result.current.schoolInfo.status).toBe('suspended');
  });

  it('loads the current status after the settings hook is remounted', async () => {
    const first = renderHook(() => useSchoolSettings());
    await waitFor(() => expect(first.result.current.schoolInfo.status).toBe('active'));
    first.unmount();

    currentSchoolStatus = 'archived';
    const second = renderHook(() => useSchoolSettings());
    await waitFor(() => expect(second.result.current.schoolInfo.status).toBe('archived'));

    expect(mockApiGet.mock.calls.filter(([url]) => url === '/school/info')).toHaveLength(2);
  });
});