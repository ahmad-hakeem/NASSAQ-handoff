/**
 * ملف الإنجاز → مكتبة الملفات: the evidence-type filter must be able to match
 * every document the library actually shows.
 *
 * Regression: the portfolio moved to the v2 evidence vocabulary (49 types,
 * e.g. curriculum_distribution_plan / oral_assessment) but the library filter
 * kept offering the legacy 25-type list with its own label map. Result:
 *  - documents whose type is v2-only had NO option that could match them, and
 *  - the same key was labelled differently in the dropdown ("نتائج الاختبارات")
 *    and on the card ("الاختبارات"), so teachers picked the option that looked
 *    like the card and got an empty list.
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

jest.mock('../../../components/layout/Sidebar', () => ({
  Sidebar: ({ children }) => <div data-testid="sidebar">{children}</div>,
}));

jest.mock('../../../components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({ showAlert: jest.fn(), nassaqError: jest.fn() }),
}));

jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

jest.mock('@/shared/hooks/useCanViewInternalIds', () => ({
  useCanViewInternalIds: () => false,
}));

// Closed dialogs must stay out of the DOM so their type <SelectItem>s don't
// duplicate the library filter's options.
jest.mock('../../../components/ui/dialog', () => ({
  Dialog: ({ open, children }) => (open ? <div>{children}</div> : null),
  DialogContent: ({ children }) => <div>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <div>{children}</div>,
  DialogFooter: ({ children }) => <div>{children}</div>,
}));

jest.mock('../../../components/ui/dropdown-menu', () => ({
  DropdownMenu: ({ children }) => <div>{children}</div>,
  DropdownMenuTrigger: ({ children }) => <div>{children}</div>,
  DropdownMenuContent: ({ children }) => <div>{children}</div>,
  DropdownMenuItem: ({ children }) => <div>{children}</div>,
  DropdownMenuLabel: ({ children }) => <div>{children}</div>,
  DropdownMenuSeparator: () => <hr />,
}));

// Radix Select never opens in jsdom; render every option inline and wire
// clicks back to the owning Select's onValueChange.
jest.mock('../../../components/ui/select', () => {
  const R = require('react');
  const Ctx = R.createContext({ onValueChange: () => {} });
  return {
    __esModule: true,
    Select: ({ children, value, onValueChange }) => (
      <Ctx.Provider value={{ value, onValueChange: onValueChange || (() => {}) }}>
        <div>{children}</div>
      </Ctx.Provider>
    ),
    SelectTrigger: ({ children }) => <div>{children}</div>,
    SelectContent: ({ children }) => <div>{children}</div>,
    SelectValue: ({ placeholder }) => <span>{placeholder}</span>,
    SelectGroup: ({ children }) => <div>{children}</div>,
    SelectLabel: ({ children }) => <div>{children}</div>,
    SelectItem: ({ children, value }) => {
      const ctx = R.useContext(Ctx);
      return (
        <button type="button" role="option" aria-selected={ctx.value === value}
                data-value={value} onClick={() => ctx.onValueChange(value)}>
          {children}
        </button>
      );
    },
  };
});

const mockStableTheme = { isRTL: true };
const mockStableTranslation = { t: (k) => k, isRTL: true };
jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTheme: () => mockStableTheme,
  useTranslation: () => mockStableTranslation,
}));

const mockApiGet = jest.fn();
const mockApi = { get: mockApiGet, post: jest.fn(), put: jest.fn(), delete: jest.fn() };
const mockAuth = {
  api: mockApi,
  isRTL: true,
  user: { id: 't1', role: 'teacher', full_name: 'معلم', tenant_id: 'school1' },
};
jest.mock('@/shared/contexts/AuthContext', () => ({ useAuth: () => mockAuth }));

// The three attachments a real teacher portfolio holds today — two of them
// carry v2-only evidence types.
const DOC_ORAL = {
  id: 'e1', evidence_type: 'oral_assessment', title_ar: 'مرحبا تجربة',
  file_id: 'f1', source: 'manual', date: '2026-04-21', created_at: '2026-04-21T10:00:00',
};
const DOC_CURRICULUM = {
  id: 'e2', evidence_type: 'curriculum_distribution_plan', title_ar: 'خطة توزيع المنهج الدراسي للمعلم',
  file_id: 'f2', source: 'manual', date: '2026-04-21', created_at: '2026-04-21T09:00:00',
};
const DOC_EXAM_ANALYSIS = {
  id: 'e3', evidence_type: 'exam_results_analysis', title_ar: 'تحليل نتائج امتحانات الطلاب',
  file_id: 'f3', source: 'manual', date: '2026-04-21', created_at: '2026-04-21T08:00:00',
};
// Auto-captured evidence carries NO file attachment — exactly what an
// independent teacher's portfolio is made of.
const DOC_AUTO_ATTENDANCE = {
  id: 'e4', evidence_type: 'attendance_record', title_ar: 'سجل حضور الطلاب',
  source: 'auto', date: '2026-04-16', created_at: '2026-04-16T08:00:00',
};
const DOC_AUTO_LESSON = {
  id: 'e5', evidence_type: 'applied_lesson_report', title_ar: 'تقرير درس مطبق: 2026-07-31',
  source: 'auto', date: '2026-07-31', created_at: '2026-07-31T07:00:00',
};

const DEFAULT_SECTIONS = {
  assessment_grading: { count: 1, items: [DOC_EXAM_ANALYSIS], types_covered: [] },
  administrative: { count: 2, items: [DOC_ORAL, DOC_CURRICULUM], types_covered: [] },
  attendance: { count: 1, items: [DOC_AUTO_ATTENDANCE], types_covered: [] },
  classroom_management: { count: 1, items: [DOC_AUTO_LESSON], types_covered: [] },
};

function setupMocks(sections = DEFAULT_SECTIONS) {
  const items = Object.values(sections).flatMap(s => s.items || []);
  mockApiGet.mockImplementation((url) => {
    if (url.includes('/teacher/portfolio/progress')) {
      return Promise.resolve({ data: { overall_percent: 6, overall_covered: 3, overall_total: 49, sections: [] } });
    }
    if (url.includes('/teacher/portfolio/sections')) {
      return Promise.resolve({ data: { intro: { text: '' }, vmv: {}, cv: { profile: {} }, evidence_subsections: {} } });
    }
    if (url.includes('/teacher/portfolio')) {
      return Promise.resolve({
        data: {
          total_evidence: items.length,
          auto_count: items.filter(i => i.source === 'auto').length,
          manual_count: items.filter(i => i.source !== 'auto').length,
          coverage_percent: 6,
          types_covered: [...new Set(items.map(i => i.evidence_type))],
          sections,
        },
      });
    }
    return Promise.resolve({ data: {} });
  });
}

// eslint-disable-next-line import/first
import TeacherAchievementsPage from '../TeacherAchievementsPage';

async function renderLibraryTab(waitText = 'مرحبا تجربة') {
  render(<TeacherAchievementsPage />);
  await waitFor(() => expect(screen.getByText('portfolioTitle')).toBeInTheDocument());
  fireEvent.click(screen.getByText('portfolioFileLibrary'));
  await screen.findByText(waitText);
}

const option = (label) => screen.getByRole('option', { name: label });

beforeEach(() => {
  jest.clearAllMocks();
  setupMocks();
  mockAuth.user = { id: 't1', role: 'teacher', full_name: 'معلم', tenant_id: 'school1' };
});

describe('portfolio file library — evidence type filter', () => {
  test('every document in the library has a filter option carrying its own label', async () => {
    await renderLibraryTab();

    // The label printed on each card must exist as a selectable option.
    ['التقويم الشفهي', 'خطة توزيع المنهج', 'تحليل نتائج الاختبارات'].forEach(label => {
      expect(option(label)).toBeInTheDocument();
    });
  });

  test('picking the label shown on a card returns that card', async () => {
    await renderLibraryTab();

    fireEvent.click(option('تحليل نتائج الاختبارات'));
    await waitFor(() => expect(screen.queryByText('مرحبا تجربة')).not.toBeInTheDocument());
    expect(screen.getByText('تحليل نتائج امتحانات الطلاب')).toBeInTheDocument();

    fireEvent.click(option('التقويم الشفهي'));
    await waitFor(() => expect(screen.getByText('مرحبا تجربة')).toBeInTheDocument());
    expect(screen.queryByText('تحليل نتائج امتحانات الطلاب')).not.toBeInTheDocument();
  });

  test('an independent teacher gets the same options for the same documents', async () => {
    mockAuth.user = { id: 'it1', role: 'independent_teacher', full_name: 'معلم مستقل', tenant_id: 'itw_it1' };
    await renderLibraryTab();

    expect(option('خطة توزيع المنهج')).toBeInTheDocument();
    fireEvent.click(option('خطة توزيع المنهج'));
    await waitFor(() => expect(screen.queryByText('مرحبا تجربة')).not.toBeInTheDocument());
    expect(screen.getByText('خطة توزيع المنهج الدراسي للمعلم')).toBeInTheDocument();
  });

  test('a type with no documents says "no matches" instead of "portfolio is empty"', async () => {
    await renderLibraryTab();

    fireEvent.click(option('الاختبارات القصيرة')); // quiz_results — nothing stored
    await waitFor(() => expect(screen.getByTestId('file-library-no-matches')).toBeInTheDocument());
    expect(screen.queryByText('portfolioEmptyState')).not.toBeInTheDocument();
  });
});

describe('portfolio file library — evidence records without attached files', () => {
  test('«جميع الشواهد» lists every evidence record, not only file-bearing ones', async () => {
    await renderLibraryTab();

    // Auto-captured records (no file_id / file_url) must appear too.
    expect(screen.getByText('سجل حضور الطلاب')).toBeInTheDocument();
    expect(screen.getByText('تقرير درس مطبق: 2026-07-31')).toBeInTheDocument();
    // Alongside the uploaded documents.
    expect(screen.getByText('تحليل نتائج امتحانات الطلاب')).toBeInTheDocument();
  });

  test('an independent teacher whose portfolio is all auto-captured (zero files) still sees and filters records', async () => {
    mockAuth.user = { id: 'it1', role: 'independent_teacher', full_name: 'معلم مستقل', tenant_id: 'itw_it1' };
    setupMocks({
      attendance: { count: 1, items: [DOC_AUTO_ATTENDANCE], types_covered: [] },
      classroom_management: { count: 1, items: [DOC_AUTO_LESSON], types_covered: [] },
    });
    await renderLibraryTab('تقرير درس مطبق: 2026-07-31');

    expect(screen.getByText('سجل حضور الطلاب')).toBeInTheDocument();
    expect(screen.queryByTestId('file-library-empty')).not.toBeInTheDocument();

    // Filtering by the record's own type keeps it and drops the rest.
    fireEvent.click(option('تقرير درس تطبيقي'));
    await waitFor(() => expect(screen.queryByText('سجل حضور الطلاب')).not.toBeInTheDocument());
    expect(screen.getByText('تقرير درس مطبق: 2026-07-31')).toBeInTheDocument();
  });
});
