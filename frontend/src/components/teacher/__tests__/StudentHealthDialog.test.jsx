/**
 * In-session student health visibility (2026-07-20 spec).
 *
 * Pins the StudentHealthDialog contract:
 *  1. Fetches GET /session/{sid}/students/{stid}/health FRESH on every open
 *     (no caching — parent edits must be visible immediately).
 *  2. Renders gated health + behavior sections from the detail payload.
 *  3. Never renders family-situation data (server excludes it; the dialog
 *     has no code path for it — this test asserts the payload keys used).
 *  4. Shows a safe Arabic error state when the fetch fails.
 *  5. Shows the "no notes" empty state when has_any is false.
 */
import React from 'react';
import { render, screen, act, waitFor } from '@testing-library/react';

jest.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({ language: 'ar', isRTL: true }),
  useTranslation: () => ({ t: (k) => k }),
}));

// Stable module-level refs — a fresh user/api object per useAuth() call would
// re-trigger the dialog's [api]-dep fetch effect forever (act timeout).
const mockApiGet = jest.fn();
const stableUser = { id: 'u1', role: 'teacher' };
const stableApi = { get: (...args) => mockApiGet(...args) };
jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({ user: stableUser, api: stableApi }),
}));

import StudentHealthDialog from '../StudentHealthDialog';

const STUDENT = { id: 'stu-1', full_name: 'سارة أحمد' };

const FULL_DETAIL = {
  student_id: 'stu-1',
  full_name: 'سارة أحمد',
  health: {
    conditions: ['asthma', 'nut_allergy'],
    other_details: 'تحتاج بخاخ الربو عند المجهود',
    blood_type: 'O+',
    chronic_conditions: 'ربو مزمن',
    allergies: 'مكسرات',
    disabilities: null,
    current_medications: 'فنتولين',
    special_care_notes: null,
    emergency_medical_notes: 'الاتصال بولي الأمر فوراً',
  },
  behavior: {
    aspects: ['adhd'],
    other_details: 'يحتاج جلوساً في المقاعد الأمامية',
  },
  has_health_alert: true,
  has_behavior_alert: true,
  has_any: true,
};

beforeEach(() => {
  mockApiGet.mockReset();
});

test('fetches fresh on open and renders health + behavior sections', async () => {
  mockApiGet.mockResolvedValue({ data: FULL_DETAIL });

  await act(async () => {
    render(
      <StudentHealthDialog open sessionId="sess-9" student={STUDENT} onClose={() => {}} />
    );
  });

  await waitFor(() => {
    expect(mockApiGet).toHaveBeenCalledWith('/session/sess-9/students/stu-1/health');
  });

  // Header carries the student name
  expect(screen.getByText(/سارة أحمد/)).toBeInTheDocument();

  // Health section: condition chips use the shared vocabulary labels
  expect(screen.getByText('ربو')).toBeInTheDocument();
  expect(screen.getByText('حساسية من المكسرات')).toBeInTheDocument();
  // Free-text + medical rows
  expect(screen.getByText('تحتاج بخاخ الربو عند المجهود')).toBeInTheDocument();
  expect(screen.getByText('O+')).toBeInTheDocument();
  expect(screen.getByText('فنتولين')).toBeInTheDocument();
  expect(screen.getByText('الاتصال بولي الأمر فوراً')).toBeInTheDocument();
  // Null rows are not rendered
  expect(screen.queryByText('إعاقات')).not.toBeInTheDocument();

  // Behavior section
  expect(screen.getByText('الجوانب السلوكية والتعلم')).toBeInTheDocument();
  expect(screen.getByText('يحتاج جلوساً في المقاعد الأمامية')).toBeInTheDocument();
});

test('re-fetches on every open (no stale cache)', async () => {
  mockApiGet.mockResolvedValue({ data: FULL_DETAIL });

  let rerender;
  await act(async () => {
    ({ rerender } = render(
      <StudentHealthDialog open sessionId="sess-9" student={STUDENT} onClose={() => {}} />
    ));
  });
  await waitFor(() => expect(mockApiGet).toHaveBeenCalledTimes(1));

  await act(async () => {
    rerender(
      <StudentHealthDialog open={false} sessionId="sess-9" student={STUDENT} onClose={() => {}} />
    );
  });
  await act(async () => {
    rerender(
      <StudentHealthDialog open sessionId="sess-9" student={STUDENT} onClose={() => {}} />
    );
  });

  await waitFor(() => expect(mockApiGet).toHaveBeenCalledTimes(2));
});

test('failed fetch shows safe Arabic error, no raw error text', async () => {
  mockApiGet.mockRejectedValue(new Error('Internal boom with secrets'));

  await act(async () => {
    render(
      <StudentHealthDialog open sessionId="sess-9" student={STUDENT} onClose={() => {}} />
    );
  });

  await waitFor(() => {
    expect(screen.getByText('تعذر تحميل البيانات الصحية، حاول مرة أخرى')).toBeInTheDocument();
  });
  expect(screen.queryByText(/Internal boom/)).not.toBeInTheDocument();
});

test('has_any=false renders the empty state', async () => {
  mockApiGet.mockResolvedValue({
    data: {
      student_id: 'stu-1',
      full_name: 'سارة أحمد',
      health: { conditions: [] },
      behavior: { aspects: [] },
      has_health_alert: false,
      has_behavior_alert: false,
      has_any: false,
    },
  });

  await act(async () => {
    render(
      <StudentHealthDialog open sessionId="sess-9" student={STUDENT} onClose={() => {}} />
    );
  });

  await waitFor(() => {
    expect(
      screen.getByText('لا توجد ملاحظات صحية أو سلوكية مسجلة لهذا الطالب')
    ).toBeInTheDocument();
  });
});

test('closed dialog does not fetch', () => {
  render(
    <StudentHealthDialog open={false} sessionId="sess-9" student={STUDENT} onClose={() => {}} />
  );
  expect(mockApiGet).not.toHaveBeenCalled();
});
