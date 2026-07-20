/**
 * Lesson-plan full view/edit (spec 2026-07-20) — opening a saved plan
 * from "الخطط المحفوظة" must expose the FULL stored plan (objectives,
 * warmup, activities, assessment, homework, materials) plus the linked
 * class, not just topic/title/subject/grade/duration.
 *
 * Contracts pinned here:
 *   1. The saved-plans table shows the linked class name (الفصل).
 *   2. "تعديل" opens the details dialog with every stored plan section
 *      editable; saving PUTs the full plan JSONB (unknown keys kept).
 *   3. Changing the class calls POST /{id}/save-to-class.
 *   4. "عرض" shows the full read-only plan content.
 */
import React from 'react';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';

jest.mock('react-router-dom', () => {
  const React2 = require('react');
  const params = new URLSearchParams('');
  return {
    useNavigate: () => jest.fn(),
    useLocation: () => ({ search: '', pathname: '/teacher/classes' }),
    useSearchParams: () => [params, jest.fn()],
    MemoryRouter: ({ children }) => React2.createElement(React2.Fragment, null, children),
  };
}, { virtual: true });

jest.mock('../../../components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar">{children}</div>,
}));

const mockAlert = {
  nassaqError: jest.fn(),
  nassaqWarning: jest.fn(),
  nassaqConfirm: jest.fn(),
  nassaqInfo: jest.fn(),
};
jest.mock('../../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => mockAlert,
}));

jest.mock('../../../utils/hijriDate', () => ({
  formatHijriDate: () => 'hijri',
}));

jest.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true }),
  useTranslation: () => ({ t: (k) => k, isRTL: true }),
}));

const mockApiGet = jest.fn();
const mockApiPut = jest.fn();
const mockApiPost = jest.fn();
const mockApi = {
  get: mockApiGet,
  post: mockApiPost,
  put: mockApiPut,
  delete: jest.fn(),
};
const mockUser = { id: 'u-teacher-1', role: 'teacher', preferred_language: 'ar' };
jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({ api: mockApi, user: mockUser, isRTL: true }),
}));

import LessonPlannerPage from '../LessonPlannerPage';

const SAVED_PLAN = {
  id: 'plan-1',
  topic: 'past simple',
  subject: 'English',
  grade_level: 'الرابع الابتدائي',
  duration_minutes: 45,
  language: 'ar',
  class_id: 'cls-1',
  is_saved: true,
  created_at: '2026-07-01T08:00:00Z',
  updated_at: '2026-07-02T08:00:00Z',
  plan: {
    title: 'مراجعة ومقارنة Past Simple',
    objectives: ['يميز الطالب الفعل الماضي', 'يكوّن جملًا صحيحة'],
    warmup: 'مراجعة سريعة للأفعال',
    activities: [
      { name: 'نشاط المجموعات', duration_minutes: 15, description: 'تقسيم الطلاب لمجموعات' },
      { name: 'تدريب فردي', duration_minutes: 10, description: 'ورقة عمل' },
    ],
    assessment: 'أسئلة شفهية قصيرة',
    homework: 'حل تمارين الكتاب ص 40',
    materials: ['السبورة', 'بطاقات الأفعال'],
    extra_notes: 'ملاحظة مخصصة يجب ألا تُفقد عند الحفظ',
  },
};

const CLASSES = [
  { id: 'cls-1', name: 'الرابع أ', name_ar: 'الرابع أ' },
  { id: 'cls-2', name: 'الرابع ب', name_ar: 'الرابع ب' },
];

beforeEach(() => {
  mockApiGet.mockReset();
  mockApiPut.mockReset();
  mockApiPost.mockReset();
  mockAlert.nassaqError.mockReset();
  mockAlert.nassaqInfo.mockReset();
  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = function () {};
  }
  mockApiGet.mockImplementation((url) => {
    if (url === '/independent-teacher/lesson-plans') {
      return Promise.resolve({
        data: {
          lesson_plans: [SAVED_PLAN],
          quota: { used_today: 1, max_per_day: 20 },
        },
      });
    }
    if (url === '/classes') {
      return Promise.resolve({ data: { classes: CLASSES } });
    }
    return Promise.resolve({ data: {} });
  });
  mockApiPut.mockResolvedValue({ data: { lesson_plan: SAVED_PLAN } });
  mockApiPost.mockResolvedValue({ data: { lesson_plan: SAVED_PLAN } });
});

test('saved-plans table shows the linked class name', async () => {
  render(<LessonPlannerPage />);
  const rows = await screen.findAllByTestId('saved-plan-row-plan-1');
  await waitFor(() => {
    expect(screen.getAllByText('الرابع أ').length).toBeGreaterThan(0);
  }, { timeout: 4000 });
  expect(rows.length).toBeGreaterThan(0);
});

test('عرض opens the full read-only plan details', async () => {
  render(<LessonPlannerPage />);
  await screen.findAllByTestId('saved-plan-row-plan-1');
  fireEvent.click(screen.getAllByRole('button', { name: /عرض/ })[0]);
  const dialog = await screen.findByTestId('lesson-plan-details-dialog');
  const q = within(dialog);
  // Full stored sections are visible
  expect(q.getByText('مراجعة ومقارنة Past Simple')).toBeInTheDocument();
  expect(q.getByText('يميز الطالب الفعل الماضي')).toBeInTheDocument();
  expect(q.getByText('مراجعة سريعة للأفعال')).toBeInTheDocument();
  expect(q.getByText(/نشاط المجموعات/)).toBeInTheDocument();
  expect(q.getByText('أسئلة شفهية قصيرة')).toBeInTheDocument();
  expect(q.getByText('حل تمارين الكتاب ص 40')).toBeInTheDocument();
  expect(q.getByText('بطاقات الأفعال')).toBeInTheDocument();
  // Linked class is part of the context
  expect(q.getAllByText(/الرابع أ/).length).toBeGreaterThan(0);
});

test('تعديل exposes all plan sections and PUTs the full plan (unknown keys preserved)', async () => {
  render(<LessonPlannerPage />);
  await screen.findAllByTestId('saved-plan-row-plan-1');
  fireEvent.click(screen.getAllByRole('button', { name: /تعديل/ })[0]);
  const dialog = await screen.findByTestId('lesson-plan-details-dialog');

  // Every stored section is editable
  const objectives = await screen.findByTestId('plan-detail-objectives-input');
  expect(objectives.value).toContain('يميز الطالب الفعل الماضي');
  expect(screen.getByTestId('plan-detail-warmup-input').value).toBe('مراجعة سريعة للأفعال');
  expect(screen.getByTestId('plan-detail-assessment-input').value).toBe('أسئلة شفهية قصيرة');
  expect(screen.getByTestId('plan-detail-homework-input').value).toBe('حل تمارين الكتاب ص 40');
  expect(screen.getByTestId('plan-detail-materials-input').value).toContain('السبورة');
  expect(screen.getByTestId('plan-detail-activity-name-0').value).toBe('نشاط المجموعات');
  expect(screen.getByTestId('plan-detail-activity-desc-1').value).toBe('ورقة عمل');

  // Edit a deep field then save
  fireEvent.change(screen.getByTestId('plan-detail-warmup-input'), {
    target: { value: 'تهيئة محدّثة' },
  });
  fireEvent.click(screen.getByTestId('plan-detail-save'));

  await waitFor(() => expect(mockApiPut).toHaveBeenCalledTimes(1), { timeout: 4000 });
  const [url, body] = mockApiPut.mock.calls[0];
  expect(url).toBe('/independent-teacher/lesson-plans/plan-1');
  expect(body.topic).toBe('past simple');
  expect(body.plan.warmup).toBe('تهيئة محدّثة');
  expect(body.plan.objectives).toEqual(['يميز الطالب الفعل الماضي', 'يكوّن جملًا صحيحة']);
  expect(body.plan.activities).toHaveLength(2);
  expect(body.plan.activities[0].name).toBe('نشاط المجموعات');
  expect(body.plan.homework).toBe('حل تمارين الكتاب ص 40');
  expect(body.plan.materials).toEqual(['السبورة', 'بطاقات الأفعال']);
  // Unknown stored keys must survive a round-trip untouched
  expect(body.plan.extra_notes).toBe('ملاحظة مخصصة يجب ألا تُفقد عند الحفظ');
  expect(dialog).toBeInTheDocument();
});

test('changing the linked class calls save-to-class', async () => {
  render(<LessonPlannerPage />);
  await screen.findAllByTestId('saved-plan-row-plan-1');
  fireEvent.click(screen.getAllByRole('button', { name: /تعديل/ })[0]);
  await screen.findByTestId('lesson-plan-details-dialog');

  fireEvent.change(screen.getByTestId('plan-detail-class-select'), {
    target: { value: 'cls-2' },
  });
  fireEvent.click(screen.getByTestId('plan-detail-save'));

  await waitFor(() => {
    expect(mockApiPost).toHaveBeenCalledWith(
      '/independent-teacher/lesson-plans/plan-1/save-to-class',
      { class_id: 'cls-2' },
    );
  }, { timeout: 4000 });
});
