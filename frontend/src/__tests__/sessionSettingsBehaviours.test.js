/**
 * Lesson Settings (إعدادات الحصة) → Behaviors (السلوكيات) tab must display the
 * SAME behaviours the live-lesson sidebar shows — i.e. the built-in default
 * positive/negative behaviours PLUS any teacher-added custom ones — instead of
 * falsely rendering the "لا توجد سلوكيات بعد" empty state.
 *
 * Root cause locked in here: SessionTeachPage fed the dialog only the *custom*
 * behaviour arrays, while the sidebar renders `built-in defaults ∪ custom`. With
 * no custom entries the Settings tab showed empty even though the sidebar had
 * usable behaviours. Both School Teacher and Independent Teacher share
 * SessionTeachPage, so the fix must hold for both roles.
 *
 * Coverage:
 *   (dialog) built-in (non-removable) + custom (removable) both render; the
 *            empty state is gone; only removable items expose a delete button.
 *   (page)   opening Lesson Settings → Behaviors shows the built-in defaults
 *            (not the empty state) for both `teacher` and `independent_teacher`.
 *
 * Run: CI=true npx craco test --testPathPattern="sessionSettingsBehaviours" --watchAll=false --forceExit
 */

import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

// ---------------------------------------------------------------------------
// Shared mocks
// ---------------------------------------------------------------------------
const mockGet = jest.fn();
const mockPost = jest.fn();

// Mutable role so the same integration assertions run for both teacher types.
let mockRole = 'teacher';

jest.mock('canvas-confetti', () => ({ __esModule: true, default: jest.fn() }));

jest.mock('sonner', () => ({
  toast: { success: jest.fn(), error: jest.fn(), info: jest.fn(), warning: jest.fn() },
}));

const SESSION_ID = 'sess-behaviours-integ';
const SUBJECT_ID = 'subj-behaviours';

jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
  useLocation: () => ({
    state: {
      sessionId: SESSION_ID,
      sessionInfo: { class_name: 'Test Class', subject_name: 'Math', subject_id: SUBJECT_ID },
    },
    pathname: '/session/teach',
  }),
}), { virtual: true });

jest.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: { id: 'teacher-1', name: 'Ahmed Teacher', role: mockRole, school_id: 'school-1' },
    api: { get: mockGet, post: mockPost },
    isRTL: false,
  }),
}));

jest.mock('../contexts/ThemeContext', () => ({
  useTranslation: () => ({ t: (k) => k, isRTL: false, dir: 'ltr' }),
  useTheme: () => ({ isDark: false, toggleTheme: jest.fn() }),
}));

jest.mock('../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ nassaqError: jest.fn(), nassaqConfirm: jest.fn() }),
  NassaqAlertDialog: () => null,
}));

jest.mock('../components/SectionErrorBoundary', () => ({ children }) => <>{children}</>);
jest.mock('../components/teacher/FollowupGradesTable', () => () => null);
jest.mock('../components/teacher/InlineAttendanceTable', () => () => null);

// Render the dialog shell inline (open ⇒ children) so the REAL
// SidebarSettingsDialog content is exercised without Radix portal complexity.
jest.mock('../components/ui/dialog', () => {
  const Passthrough = ({ children }) => <div>{children}</div>;
  return {
    Dialog: ({ open, children }) => (open ? <div>{children}</div> : null),
    DialogPortal: Passthrough,
    DialogOverlay: Passthrough,
    DialogTrigger: Passthrough,
    DialogClose: Passthrough,
    DialogContent: Passthrough,
    DialogHeader: Passthrough,
    DialogFooter: Passthrough,
    DialogTitle: Passthrough,
    DialogDescription: Passthrough,
  };
});

// Components under test (imported AFTER mocks). SidebarSettingsDialog is NOT
// mocked — the whole point is to verify the real behaviours tab.
import SidebarSettingsDialog from '../components/teacher/SidebarSettingsDialog';
import SessionTeachPage from '../pages/TeacherModule/SessionTeachPage';

// ---------------------------------------------------------------------------
// Dialog-level contract
// ---------------------------------------------------------------------------
describe('SidebarSettingsDialog — behaviours tab rendering', () => {
  test('shows built-in (non-removable) + custom (removable) behaviours; only custom has a delete button', () => {
    const onRemovePositive = jest.fn();
    render(
      <SidebarSettingsDialog
        open
        onOpenChange={() => {}}
        t={(k) => k}
        positiveBehaviours={[
          { id: 'respect', name: 'احترام', points: 2, removable: false },
          { id: 'bhv_custom_1', name: 'تعاون', points: 3 },
        ]}
        negativeBehaviours={[
          { id: 'disruption', name: 'إزعاج', points: 2, removable: false },
        ]}
        onRemovePositiveBehaviour={onRemovePositive}
        onRemoveNegativeBehaviour={() => {}}
      />
    );

    // Move to the Behaviors tab.
    fireEvent.click(screen.getByRole('button', { name: 'behaviours' }));

    // Built-in and custom behaviours both render; the empty state is gone.
    expect(screen.getByText('احترام')).toBeInTheDocument();
    expect(screen.getByText('تعاون')).toBeInTheDocument();
    expect(screen.getByText('إزعاج')).toBeInTheDocument();
    expect(screen.queryByText('noBehavioursYet')).toBeNull();

    // Only the removable (custom) item exposes a delete button.
    const deleteButtons = screen.getAllByLabelText('delete');
    expect(deleteButtons).toHaveLength(1);

    fireEvent.click(deleteButtons[0]);
    expect(onRemovePositive).toHaveBeenCalledWith('bhv_custom_1');
  });
});

// ---------------------------------------------------------------------------
// Page-level integration (root-cause guard)
// ---------------------------------------------------------------------------
describe('SessionTeachPage — Lesson Settings behaviours reflect the sidebar', () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPost.mockReset();
    mockRole = 'teacher';

    mockGet.mockImplementation((url) => {
      if (url.endsWith('/settings'))
        return Promise.resolve({ data: { subject_id: SUBJECT_ID, participation_enabled: true } });
      if (url.endsWith('/students'))
        return Promise.resolve({ data: { students: [] } });
      if (url.endsWith('/groups')) return Promise.resolve({ data: { groups: [] } });
      if (url.endsWith('/notes')) return Promise.resolve({ data: { notes: [] } });
      if (url.endsWith('/undo/peek')) return Promise.resolve({ data: { has_reversible: false } });
      if (url.endsWith('/activity')) return Promise.resolve({ data: { activity: [] } });
      if (url.endsWith('/live-metrics')) return Promise.resolve({ data: {} });
      if (url.endsWith('/followup-record')) return Promise.resolve({ data: { data: {}, absences: {} } });
      if (url.endsWith('/grade-columns')) return Promise.resolve({ data: { columns: [] } });
      if (url.endsWith('/skills-types') || url === '/subjects') return Promise.resolve({ data: [] });
      return Promise.resolve({ data: { id: SESSION_ID, class_name: 'Test Class', status: 'active' } });
    });
    mockPost.mockResolvedValue({ data: {} });

    try { window.sessionStorage.clear(); } catch { /* ignore */ }
    try { window.localStorage.clear(); } catch { /* ignore */ }
  });

  test.each(['teacher', 'independent_teacher'])(
    'opening Lesson Settings shows built-in behaviours (not the empty state) for role=%s',
    async (role) => {
      mockRole = role;
      render(<SessionTeachPage />);

      // Wait for the session bootstrap to run so the toolbar is present.
      await waitFor(() => {
        expect(mockGet).toHaveBeenCalledWith(`/session/${SESSION_ID}/settings`);
      }, { timeout: 3000 });

      // Open Lesson Settings (إعدادات الحصة) via the gear button.
      fireEvent.click(screen.getAllByTitle('sessionSettings')[0]);

      // Switch to the Behaviors tab.
      const behavioursTab = await screen.findByRole('button', { name: 'behaviours' }, { timeout: 3000 });
      fireEvent.click(behavioursTab);

      // Built-in defaults must appear; the false "no behaviours yet" is gone.
      await waitFor(() => {
        expect(screen.getByText('behaviourRespect')).toBeInTheDocument();
        expect(screen.getByText('behaviourDisruption')).toBeInTheDocument();
      }, { timeout: 3000 });
      expect(screen.queryByText('noBehavioursYet')).toBeNull();
    }
  );
});
