import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';
import { AdminCalendar } from '../../components/dashboard/AdminCalendar';

/**
 * Task #208 §6.3 — Independent-Teacher personal calendar page.
 *
 * Reuses the existing `AdminCalendar` component in personal-mode by
 * pointing it at the IT-only `/independent-teacher/calendar` surface.
 * Imports/templates are disabled here because the IT route does not
 * (currently) accept bulk CSV uploads — every personal event is
 * authored manually inside the caller's own workspace.
 */
export default function TeacherPersonalCalendarPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { isRTL } = useTheme();
  const isIndependent = (user?.role || '').toLowerCase() === 'independent_teacher';

  useEffect(() => {
    if (!isIndependent) navigate('/teacher', { replace: true });
  }, [isIndependent, navigate]);

  if (!isIndependent) return null;

  return (
    <div dir={isRTL ? 'rtl' : 'ltr'} className="min-h-screen bg-slate-50 py-6 px-4">
      <div className="mx-auto max-w-4xl space-y-6">
        <div data-testid="teacher-personal-calendar-header">
          <p className="text-xs font-semibold text-workspace-accent uppercase tracking-wide">
            مساحتك التعليمية الخاصة
          </p>
          <h1 className="text-2xl font-bold text-workspace-accent-fg">
            تقويمي الشخصي
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            أحداث شخصية لمعلمك المستقل — لا تظهر لأي معلم آخر.
          </p>
        </div>
        <AdminCalendar
          basePath="/independent-teacher/calendar"
          importEnabled={false}
          titleAr="تقويمي الشخصي"
          titleEn="My Personal Calendar"
        />
      </div>
    </div>
  );
}
