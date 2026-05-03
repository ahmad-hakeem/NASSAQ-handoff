/**
 * Task #133 — TeacherScheduleGrid loading state regression guard.
 *
 * بعد المهمة #132 صار `TeacherScheduleGrid` يعتمد كليًا على `timeSlots`
 * القادمة من إعدادات المدرسة في الباك‑إند، فإن وصلت متأخرة كانت الشبكة
 * تظهر بأعمدة صفر للحظة قبل تحميل الإعدادات.
 *
 * هنا نتحقق من سلوك خاصية `isLoading` الجديدة:
 *
 *   1. عندما `isLoading=true` و`timeSlots` فارغة، يُعرض هيكل تحميل
 *      (skeleton) مع `data-testid="teacher-schedule-grid-loading"`،
 *      ولا تُعرض الشبكة الحقيقية ولا حالة "اضبط الإعدادات".
 *   2. عندما `isLoading=false` و`timeSlots` فارغة، يبقى السلوك القديم
 *      (حالة فارغة موجِّهة لإعدادات الجدول) — لا وميض لشبكة بلا أعمدة.
 *   3. بمجرد وصول `timeSlots`، تختفي طبقة التحميل وتُرسم الشبكة الفعلية،
 *      حتى لو بقيت `isLoading=true` (لا نُخفي بيانات صحيحة).
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { ThemeProvider } from '../../../contexts/ThemeContext';
import { TeacherScheduleGrid } from '../TeacherScheduleGrid';

jest.mock('../../ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqWarning: jest.fn(),
    nassaqError: jest.fn(),
    nassaqInfo: jest.fn(),
    nassaqSuccess: jest.fn(),
  }),
}));

const renderGrid = (props = {}) =>
  render(
    <ThemeProvider>
      <TeacherScheduleGrid teachers={[]} sessions={[]} timeSlots={[]} {...props} />
    </ThemeProvider>,
  );

describe('TeacherScheduleGrid — loading state (Task #133)', () => {
  test('isLoading=true with empty timeSlots renders the skeleton, not the empty hint', () => {
    renderGrid({ isLoading: true });
    expect(screen.getByTestId('teacher-schedule-grid-loading')).toBeInTheDocument();
    expect(screen.queryByTestId('teacher-schedule-grid-empty')).not.toBeInTheDocument();
    expect(screen.queryByTestId('teacher-schedule-grid')).not.toBeInTheDocument();
  });

  test('isLoading=false with empty timeSlots keeps the legacy empty/configure state', () => {
    renderGrid({ isLoading: false });
    expect(screen.getByTestId('teacher-schedule-grid-empty')).toBeInTheDocument();
    expect(screen.queryByTestId('teacher-schedule-grid-loading')).not.toBeInTheDocument();
  });

  test('once timeSlots arrive the skeleton disappears and the real grid renders (no flicker)', () => {
    const slots = [
      { slot_number: 1, start_time: '08:00', end_time: '08:45', is_break: false },
      { slot_number: 2, start_time: '08:45', end_time: '09:30', is_break: false },
    ];
    renderGrid({ isLoading: true, timeSlots: slots });
    expect(screen.queryByTestId('teacher-schedule-grid-loading')).not.toBeInTheDocument();
    expect(screen.queryByTestId('teacher-schedule-grid-empty')).not.toBeInTheDocument();
    expect(screen.getByTestId('teacher-schedule-grid')).toBeInTheDocument();
  });
});
