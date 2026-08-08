/**
 * أنماط التقييم (Evaluation Patterns) — Session Settings column edits must
 * propagate to the class-level grade-columns API, the single source of truth
 * shared by كشف المتابعة and فصولي → سجل الطلاب.
 *
 * Regression under test: the pattern editor edited only local state and
 * persisted to the legacy session_settings.extra_columns blob, which nothing
 * else reads. Added columns never reached the backend, deleted columns came
 * back on the next followup open, and the class record table never changed.
 *
 * Shared page: applies identically to School Teacher and Independent Teacher.
 * Harness mirrors SessionTeachPage.streakColumnToggle.test.jsx.
 */
import React from 'react';
import { render, act } from '@testing-library/react';

jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
  useLocation: () => ({ state: { sessionId: 'sess-1' } }),
}), { virtual: true });

const mockApiGet = jest.fn();
const mockApiPost = jest.fn();
const mockApiPut = jest.fn();
const mockApiDelete = jest.fn();
const mockApi = {
  get: mockApiGet,
  post: mockApiPost,
  put: mockApiPut,
  patch: jest.fn().mockResolvedValue({ data: {} }),
  delete: mockApiDelete,
};
jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => ({
    api: mockApi,
    user: { id: 'teacher-1', teacher_id: 'teacher-1', role: 'teacher', tenant_id: 'school-1' },
    isRTL: true,
  }),
}));
jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true }),
  useTranslation: () => ({ t: (k) => k, isRTL: true }),
}));

const mockAlert = {
  nassaqError: jest.fn(),
  nassaqWarning: jest.fn(),
  nassaqConfirm: jest.fn(),
  nassaqInfo: jest.fn(),
};
jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => mockAlert,
  NassaqAlertDialog: () => null,
}));

jest.mock('@/shared/components/SectionErrorBoundary', () => ({
  __esModule: true,
  default: ({ children }) => <>{children}</>,
}));

// Capture double: exposes the live sessionConfig contract so tests can drive
// the أنماط التقييم editor exactly the way SidebarSettingsDialog does.
let capturedSC = null;
jest.mock('@/features/teachers/components/teacher/SidebarSettingsDialog', () => ({
  __esModule: true,
  default: (props) => {
    capturedSC = props.sessionConfig;
    return null;
  },
}));
jest.mock('@/features/teachers/components/teacher/InlineAttendanceTable', () => ({
  __esModule: true,
  default: () => <div />,
}));
jest.mock('@/features/teachers/components/teacher/FollowupGradesTable', () => ({
  __esModule: true,
  default: () => <div data-testid="followup-grades-table" />,
}));

jest.mock('@/shared/components/ui/card', () => ({
  Card: ({ children, ...p }) => <div {...p}>{children}</div>,
  CardContent: ({ children, ...p }) => <div {...p}>{children}</div>,
}));
jest.mock('@/shared/components/ui/button', () => ({
  Button: ({ children, onClick, ...p }) => <button onClick={onClick} {...p}>{children}</button>,
}));
jest.mock('@/shared/components/ui/badge', () => ({
  Badge: ({ children, ...p }) => <span {...p}>{children}</span>,
}));
jest.mock('@/shared/components/ui/avatar', () => ({
  Avatar: ({ children }) => <div>{children}</div>,
  AvatarFallback: ({ children }) => <div>{children}</div>,
  AvatarImage: () => <img alt="" />,
}));
jest.mock('@/shared/components/ui/dialog', () => ({
  Dialog: ({ open, children }) => (open ? <div>{children}</div> : null),
  DialogContent: ({ children }) => <div>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <div>{children}</div>,
}));
jest.mock('@/shared/components/ui/textarea', () => ({
  Textarea: (p) => <textarea {...p} />,
}));
jest.mock('canvas-confetti', () => jest.fn());
jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn(), info: jest.fn() } }));

import SessionTeachPage from '../SessionTeachPage';

const SESSION = {
  id: 'sess-1', status: 'in_progress', class_id: 'cls-1', school_id: 'school-1',
  teacher_id: 'teacher-1', subject_id: 'subj-1', start_time: new Date().toISOString(),
  stats: { questions_asked: 0, correct_answers: 0 }, interaction_mode: 'review',
};
const STUDENTS = [{ id: 'stu-1', full_name: 'أحمد محمد', interaction_count: 0, correct_answers: 0 }];
// Canonical backend columns (class-level grade_columns collection).
const COLUMNS = [
  { id: 'part', name: 'المشاركة', column_type: 'coursework', max_grade: 5, visible: true, order: 1 },
  { id: 'hw', name: 'الواجبات', column_type: 'coursework', max_grade: 5, visible: true, order: 2 },
];

let serverSettings;

function setupApi() {
  mockApiGet.mockImplementation((url) => {
    if (typeof url !== 'string') return Promise.resolve({ data: {} });
    if (url === '/session/sess-1') return Promise.resolve({ data: SESSION });
    if (url === '/session/sess-1/students') return Promise.resolve({ data: { students: STUDENTS } });
    if (url === '/session/sess-1/followup-record') return Promise.resolve({ data: { data: {}, absences: {} } });
    if (url === '/class/cls-1/grade-columns') return Promise.resolve({ data: COLUMNS });
    if (url === '/skills-types') return Promise.resolve({ data: [] });
    if (url === '/subjects') return Promise.resolve({ data: [] });
    if (url.endsWith('/groups')) return Promise.resolve({ data: [] });
    if (url.endsWith('/settings')) return Promise.resolve({ data: serverSettings });
    if (url.endsWith('/notes')) return Promise.resolve({ data: [] });
    if (url.endsWith('/undo/peek')) return Promise.resolve({ data: { can_undo: false } });
    if (url.endsWith('/activity')) return Promise.resolve({ data: [] });
    if (url.endsWith('/live-metrics')) return Promise.resolve({ data: {} });
    if (url.endsWith('/homework')) return Promise.resolve({ data: {} });
    return Promise.resolve({ data: {} });
  });
  mockApiPost.mockImplementation(() => Promise.resolve({ data: {} }));
  mockApiPut.mockImplementation(() => Promise.resolve({ data: {} }));
  mockApiDelete.mockImplementation(() => Promise.resolve({ data: {} }));
}

async function flushMicrotasks() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}

async function mountPage() {
  await act(async () => {
    render(<SessionTeachPage />);
  });
  await flushMicrotasks();
}

async function saveSettings() {
  await act(async () => {
    await capturedSC.onSave();
  });
  await flushMicrotasks();
}

describe('SessionTeachPage — أنماط التقييم propagate through class grade-columns', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    capturedSC = null;
    sessionStorage.clear();
    setupApi();
  });

  test('pattern editor hydrates from the class-level grade-columns API on mount', async () => {
    serverSettings = { subject_id: 'subj-1' };
    await mountPage();
    const ids = (capturedSC.followupColumns || []).map((c) => c.id);
    expect(ids).toEqual(expect.arrayContaining(['part', 'hw']));
  });

  test('stale legacy extra_columns in session settings do NOT override backend columns', async () => {
    serverSettings = {
      subject_id: 'subj-1',
      extra_columns: [{ id: 'stale-1', name: 'عمود قديم', maxGrade: 5, type: 'grade' }],
    };
    await mountPage();
    const ids = (capturedSC.followupColumns || []).map((c) => c.id);
    expect(ids).toEqual(expect.arrayContaining(['part', 'hw']));
    expect(ids).not.toContain('stale-1');
  });

  test('adding a column then حفظ النمط POSTs it to the class grade-columns API', async () => {
    serverSettings = { subject_id: 'subj-1' };
    await mountPage();
    await act(async () => {
      capturedSC.onFollowupColumnsChange([
        ...capturedSC.followupColumns,
        { id: 'col_1784404261457', name: 'نشاط 1', maxGrade: 10, type: 'grade', group: 'coursework' },
      ]);
    });
    await saveSettings();
    const createCall = mockApiPost.mock.calls.find(
      ([url]) => url === '/class/cls-1/grade-columns',
    );
    expect(createCall).toBeTruthy();
    expect(createCall[1]).toMatchObject({
      name: 'نشاط 1',
      column_type: 'coursework',
      max_grade: 10,
    });
    // The legacy extra_columns blob must no longer be the persistence path.
    const settingsCall = mockApiPost.mock.calls.find(
      ([url]) => url === '/session/sess-1/settings',
    );
    expect(settingsCall).toBeTruthy();
    expect(settingsCall[1].extra_columns).toBeUndefined();
  });

  test('deleting a column then حفظ النمط DELETEs it from the class grade-columns API', async () => {
    serverSettings = { subject_id: 'subj-1' };
    await mountPage();
    await act(async () => {
      capturedSC.onFollowupColumnsChange(
        capturedSC.followupColumns.filter((c) => c.id !== 'hw'),
      );
    });
    await saveSettings();
    expect(mockApiDelete).toHaveBeenCalledWith('/grade-column/hw');
    // The surviving column must not be deleted.
    expect(mockApiDelete).not.toHaveBeenCalledWith('/grade-column/part');
  });

  test('changing a column category (أعمال السنة → الاختبارات) then حفظ النمط PUTs column_type', async () => {
    serverSettings = { subject_id: 'subj-1' };
    await mountPage();
    await act(async () => {
      capturedSC.onFollowupColumnsChange(
        capturedSC.followupColumns.map((c) => (
          c.id === 'hw' ? { ...c, group: 'exams' } : c
        )),
      );
    });
    await saveSettings();
    const putCall = mockApiPut.mock.calls.find(([url]) => url === '/grade-column/hw');
    expect(putCall).toBeTruthy();
    expect(putCall[1]).toMatchObject({ column_type: 'exams' });
    // Untouched column must not generate a write.
    expect(mockApiPut.mock.calls.find(([url]) => url === '/grade-column/part')).toBeUndefined();
  });

  test('adding a column marked اختبارات then حفظ النمط POSTs column_type exams', async () => {
    serverSettings = { subject_id: 'subj-1' };
    await mountPage();
    await act(async () => {
      capturedSC.onFollowupColumnsChange([
        ...capturedSC.followupColumns,
        { id: 'col_1784404261458', name: 'اختبار شهري', maxGrade: 20, type: 'grade', group: 'exams' },
      ]);
    });
    await saveSettings();
    const createCall = mockApiPost.mock.calls.find(
      ([url]) => url === '/class/cls-1/grade-columns',
    );
    expect(createCall).toBeTruthy();
    expect(createCall[1]).toMatchObject({ name: 'اختبار شهري', column_type: 'exams', max_grade: 20 });
  });

  test('renaming and re-scoring a column then حفظ النمط PUTs the change', async () => {
    serverSettings = { subject_id: 'subj-1' };
    await mountPage();
    await act(async () => {
      capturedSC.onFollowupColumnsChange(
        capturedSC.followupColumns.map((c) => (
          c.id === 'part' ? { ...c, name: 'مشاركة صفية', maxGrade: 15 } : c
        )),
      );
    });
    await saveSettings();
    const putCall = mockApiPut.mock.calls.find(([url]) => url === '/grade-column/part');
    expect(putCall).toBeTruthy();
    expect(putCall[1]).toMatchObject({ name: 'مشاركة صفية', max_grade: 15 });
    // Unchanged column must not generate a write.
    expect(mockApiPut.mock.calls.find(([url]) => url === '/grade-column/hw')).toBeUndefined();
  });
});
