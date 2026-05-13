/**
 * Task #277 — ChildDetailsPage hides school-only surfaces for IT-invited
 * parents.
 *
 * Pins:
 *   - The hero replaces the school chip with the inviting teacher's
 *     workspace label when `is_independent_teacher_workspace=true`.
 *   - The "Contact Teachers" card (which deep-links into the school-only
 *     teacher roster page) is NOT rendered for IT students.
 *   - The same card IS rendered for ordinary school-tenant students,
 *     so the existing flow is unaffected.
 */
import React from 'react';
import { render, screen, act } from '@testing-library/react';

jest.mock('react-router-dom', () => ({
  Link: ({ children, to, ...rest }) => (
    <a href={typeof to === 'string' ? to : '#'} {...rest}>{children}</a>
  ),
  useParams: () => ({ childId: 'stu-1' }),
}), { virtual: true });

jest.mock('../../../contexts/AuthContext', () => ({
  useAuth: () => ({ token: 't', api: { get: () => Promise.resolve({ data: {} }) } }),
}));

jest.mock('../../../contexts/ThemeContext', () => ({
  useTheme: () => ({ isRTL: true, isDark: false }),
  useTranslation: () => ({ t: () => undefined, isRTL: true }),
}));

let mockActiveChild = null;
jest.mock('../../../contexts/ParentActiveStudentContext', () => ({
  useSyncRouteChildToActive: () => {},
  useParentActiveStudent: () => ({
    activeChildId: 'stu-1',
    activeChild: mockActiveChild,
    hasLoadedChildren: true,
    getCachedEndpoint: () => null,
    setCachedEndpoint: () => {},
  }),
}));

jest.mock('../../../components/portal/PortalLayout', () => ({
  __esModule: true,
  default: ({ children }) => <div data-testid="portal-layout">{children}</div>,
}));
jest.mock('../../../components/parent/CumulativeAnalytics', () => ({
  __esModule: true, default: () => <div />,
}));
jest.mock('../../../components/parent/BackgroundRefreshChip', () => ({
  __esModule: true, default: () => <div />,
}));
jest.mock('../../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ nassaqError: jest.fn(), nassaqWarning: jest.fn() }),
}));
jest.mock('sonner', () => ({ toast: { error: jest.fn(), success: jest.fn() } }));

const ChildDetailsPage = require('../ChildDetailsPage').default;

describe('ChildDetailsPage — IT polish (#277)', () => {
  it('hides the Contact Teachers card and shows the IT label for IT students', async () => {
    mockActiveChild = {
      id: 'stu-1',
      name: 'طالب الترحيب',
      grade: 'ابتدائي',
      class_name: 'الصف الأول',
      school_id: 'itw_owner-1',
      school_name: 'IT-Workspace-owner1',
      is_independent_teacher_workspace: true,
      teacher_display_name: 'الأستاذة سارة',
    };

    await act(async () => {
      render(<ChildDetailsPage />);
    });

    expect(screen.getByTestId('child-details-page')).toBeTruthy();
    expect(screen.queryByTestId('contact-teachers-card')).toBeNull();
    // Teacher workspace label rendered in place of the school name.
    expect(screen.getByText(/الأستاذة سارة/)).toBeTruthy();
  });

  it('still renders the Contact Teachers card for ordinary school students', async () => {
    mockActiveChild = {
      id: 'stu-2',
      name: 'طالب مدرسة',
      grade: 'ابتدائي',
      class_name: 'الصف الأول',
      school_id: 'school-1',
      school_name: 'مدرسة النور',
      is_independent_teacher_workspace: false,
      teacher_display_name: null,
    };

    await act(async () => {
      render(<ChildDetailsPage />);
    });

    expect(screen.getByTestId('contact-teachers-card')).toBeTruthy();
  });
});
