/**
 * Task #389 — pin the Noor import preview UI contracts introduced by Task #387.
 *
 * The preview surface has three UI-only invariants that have no automated
 * coverage and could silently regress in a refactor:
 *   1. The four canonical buckets (insert / update / duplicate / unclassified)
 *      render the counts the backend returned.
 *   2. When `counts.unclassified > 0`, the sticky "بدون فصل" banner is shown.
 *   3. Clicking "تنفيذ الاستيراد" while `counts.unclassified > 0` must NOT
 *      hit `/noor-import/commit` directly — it must first surface a
 *      NassaqAlertDialog with "أكمل بدون فصل" / "إلغاء" actions so the
 *      principal explicitly accepts the partial-link semantics.
 *
 * A regression here would re-introduce a quiet partial import.
 */
import React from 'react';
import { render, screen, fireEvent, act, within, waitFor } from '@testing-library/react';
import { NassaqAlertProvider, useNassaqAlert } from '../../ui/NassaqAlertDialog';
import NoorImportPanel from '../NoorImportPanel';

const _previewWithUnclassified = (overrides = {}) => ({
  import_draft_id: 'draft-abc',
  detected_type: 'students',
  header_row: 2,
  sheet_name: 'Sheet1',
  counts: {
    total: 10,
    insert: 4,
    update: 3,
    duplicate_in_file: 1,
    unclassified: 2,
    ambiguous: 0,
    skip: 0,
  },
  rows: [],
  ...overrides,
});

function Harness({ api, onComplete }) {
  const { nassaqError, nassaqWarning, nassaqConfirm, nassaqInfo } = useNassaqAlert();
  return (
    <NoorImportPanel
      api={api}
      nassaqError={nassaqError}
      nassaqWarning={nassaqWarning}
      nassaqConfirm={nassaqConfirm}
      nassaqInfo={nassaqInfo}
      t={(k) => k}
      onComplete={onComplete}
    />
  );
}

function renderWithProviders(api, onComplete) {
  return render(
    <NassaqAlertProvider>
      <Harness api={api} onComplete={onComplete} />
    </NassaqAlertProvider>,
  );
}

// Helper: drive the panel from "no file" to "preview rendered" using a stubbed api.post.
async function seedPreview(api, preview) {
  api.post.mockResolvedValueOnce({ data: preview });
  const file = new File(['x'], 'noor.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
  const input = document.querySelector('input[type="file"]');
  await act(async () => {
    fireEvent.change(input, { target: { files: [file] } });
  });
  const previewBtn = screen.getByRole('button', { name: /معاينة/ });
  await act(async () => {
    fireEvent.click(previewBtn);
  });
}

describe('NoorImportPanel preview contracts (Task #387)', () => {
  test('renders the four canonical bucket counts from the parse response', async () => {
    const api = { post: jest.fn() };
    renderWithProviders(api);

    await seedPreview(api, _previewWithUnclassified({
      counts: { total: 20, insert: 7, update: 5, duplicate_in_file: 3, unclassified: 4, ambiguous: 1, skip: 0 },
    }));

    expect(within(screen.getByTestId('bucket-insert')).getByText('7')).toBeInTheDocument();
    expect(within(screen.getByTestId('bucket-update')).getByText('5')).toBeInTheDocument();
    expect(within(screen.getByTestId('bucket-duplicate')).getByText('3')).toBeInTheDocument();
    expect(within(screen.getByTestId('bucket-unclassified')).getByText('4')).toBeInTheDocument();
  });

  test('shows the sticky "بدون فصل" banner when unclassified > 0', async () => {
    const api = { post: jest.fn() };
    renderWithProviders(api);

    await seedPreview(api, _previewWithUnclassified());

    const banner = screen.getByTestId('unclassified-banner');
    expect(banner).toBeInTheDocument();
    expect(banner.className).toMatch(/sticky/);
    expect(banner.textContent).toMatch(/بدون ربطه بفصل دراسي/);
  });

  test('hides the banner when unclassified === 0', async () => {
    const api = { post: jest.fn() };
    renderWithProviders(api);

    await seedPreview(api, _previewWithUnclassified({
      counts: { total: 5, insert: 5, update: 0, duplicate_in_file: 0, unclassified: 0, ambiguous: 0, skip: 0 },
    }));

    expect(screen.queryByTestId('unclassified-banner')).toBeNull();
  });

  test('clicking تنفيذ الاستيراد with unclassified > 0 opens the NassaqAlertDialog gate and does not POST /commit', async () => {
    const api = { post: jest.fn() };
    renderWithProviders(api);

    await seedPreview(api, _previewWithUnclassified());
    expect(api.post).toHaveBeenCalledTimes(1); // parse only

    const commitBtn = screen.getByRole('button', { name: /تنفيذ الاستيراد/ });
    await act(async () => {
      fireEvent.click(commitBtn);
    });

    // Gate dialog is open with the two canonical actions, BEFORE the commit fires.
    const dialog = await screen.findByTestId('nassaq-alert-dialog');
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: 'أكمل بدون فصل' })).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: 'إلغاء' })).toBeInTheDocument();

    // /commit MUST NOT have been called yet — the principal hasn't accepted.
    const commitCalls = api.post.mock.calls.filter(c => String(c[0]).includes('/noor-import/commit'));
    expect(commitCalls).toHaveLength(0);

    // Cancel keeps the commit suppressed.
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'إلغاء' }));
    });
    const commitCallsAfterCancel = api.post.mock.calls.filter(c => String(c[0]).includes('/noor-import/commit'));
    expect(commitCallsAfterCancel).toHaveLength(0);
  });
});

// ---- Task #390 — inline class-detail editor in the unclassified banner ----
const _previewWithPair = () => ({
  import_draft_id: 'draft-xyz',
  detected_type: 'students',
  header_row: 2,
  sheet_name: 'Sheet1',
  counts: { total: 2, insert: 0, update: 0, duplicate_in_file: 0, unclassified: 2, ambiguous: 0, skip: 0 },
  rows: [
    { row_index: 1, dedupe: 'insert', class_unresolved: true, data: { grade_code: '7', section_code: 'A' } },
    { row_index: 2, dedupe: 'insert', class_unresolved: true, data: { grade_code: '7', section_code: 'A' } },
  ],
});

describe('NoorImportPanel inline class-detail editor (Task #390)', () => {
  test('populates the homeroom dropdown from /teachers (raw-array shape) and sends overrides on confirm', async () => {
    const api = {
      post: jest.fn(),
      // academics_teacher_routes.py raw-array shape
      get: jest.fn().mockResolvedValue({ data: [
        { id: 't1', full_name: 'الأستاذة سارة', is_active: true },
        { id: 't2', full_name: 'مغادر', is_active: false },
      ] }),
    };
    renderWithProviders(api);
    await seedPreview(api, _previewWithPair());

    const capInput = await screen.findByTestId('capacity-input-0');
    expect(capInput).toBeInTheDocument();
    // Wait for the lazy teachers fetch to resolve and populate options.
    await screen.findByText('الأستاذة سارة');
    const hrSelect = screen.getByTestId('homeroom-select-0');
    // Active teachers only — inactive option must NOT appear.
    expect(within(hrSelect).queryByText('مغادر')).toBeNull();
    expect(within(hrSelect).getByText('الأستاذة سارة')).toBeInTheDocument();

    await act(async () => {
      fireEvent.change(capInput, { target: { value: '25' } });
      fireEvent.change(hrSelect, { target: { value: 't1' } });
    });

    // Click the create-missing-classes button, then confirm the dialog.
    const createBtn = screen.getByRole('button', { name: /إنشاء الفصول الناقصة/ });
    api.post.mockResolvedValueOnce({ data: { created_classes: [{ id: 'c1', grade_code: '7', section_code: 'A', capacity: 25, homeroom_teacher_id: 't1', homeroom_teacher_name: 'الأستاذة سارة' }] } });
    api.post.mockResolvedValueOnce({ data: _previewWithPair() }); // re-annotation
    await act(async () => { fireEvent.click(createBtn); });
    const dialog = await screen.findByTestId('nassaq-alert-dialog');
    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'إنشاء وإعادة المطابقة' }));
    });

    await waitFor(() => {
      const createCalls = api.post.mock.calls.filter(c => String(c[0]).includes('/create-missing-classes'));
      expect(createCalls.length).toBeGreaterThanOrEqual(1);
    });
    const createCall = api.post.mock.calls.find(c => String(c[0]).includes('/create-missing-classes'));
    expect(createCall[1]).toEqual({ overrides: [
      { grade_code: '7', section_code: 'A', capacity: 25, homeroom_teacher_id: 't1' },
    ]});
  });

  test('also accepts the {teachers} envelope shape', async () => {
    const api = {
      post: jest.fn(),
      // teacher_management_routes.py envelope shape
      get: jest.fn().mockResolvedValue({ data: { teachers: [
        { id: 't9', full_name: 'الأستاذة منى', is_active: true },
      ], total: 1 } }),
    };
    renderWithProviders(api);
    await seedPreview(api, _previewWithPair());

    await screen.findByTestId('homeroom-select-0');
    await screen.findByText('الأستاذة منى');
    const hrSelect = screen.getByTestId('homeroom-select-0');
    expect(within(hrSelect).getByText('الأستاذة منى')).toBeInTheDocument();
  });

  test('editor table renders one row per unclassified pair with capacity input and homeroom select', async () => {
    const api = {
      post: jest.fn(),
      get: jest.fn().mockResolvedValue({ data: [
        { id: 'ta', full_name: 'أستاذ أحمد', is_active: true },
        { id: 'tb', full_name: 'أستاذة نور', is_active: true },
      ] }),
    };
    renderWithProviders(api);
    await seedPreview(api, _previewWithPair());

    const table = await screen.findByTestId('missing-class-pairs');
    expect(table).toBeInTheDocument();

    // Exactly one data row for the single grade/section pair.
    const rows = table.querySelectorAll('tbody tr');
    expect(rows).toHaveLength(1);

    // That row must contain a capacity input and a homeroom select.
    expect(screen.getByTestId('capacity-input-0')).toBeInTheDocument();
    expect(screen.getByTestId('homeroom-select-0')).toBeInTheDocument();

    // Teachers are lazily fetched and must populate the dropdown.
    await screen.findByText('أستاذ أحمد');
    await screen.findByText('أستاذة نور');
  });

  test('out-of-range capacity surfaces a NassaqAlertDialog warning and does not POST', async () => {
    const api = {
      post: jest.fn(),
      get: jest.fn().mockResolvedValue({ data: [] }),
    };
    renderWithProviders(api);
    await seedPreview(api, _previewWithPair());

    const capInput = await screen.findByTestId('capacity-input-0');
    await act(async () => {
      fireEvent.change(capInput, { target: { value: '9999' } });
    });
    const createBtn = screen.getByRole('button', { name: /إنشاء الفصول الناقصة/ });
    await act(async () => { fireEvent.click(createBtn); });

    // A NassaqAlertDialog warning must appear with the Arabic capacity message.
    const dialog = await screen.findByTestId('nassaq-alert-dialog');
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAttribute('data-nassaq-alert', 'warning');
    expect(dialog.textContent).toMatch(/السعة يجب أن تكون رقماً صحيحاً بين 1 و 500/);

    // The create-missing-classes endpoint must NOT have been called.
    const createCalls = api.post.mock.calls.filter(c => String(c[0]).includes('/create-missing-classes'));
    expect(createCalls).toHaveLength(0);
  });

  test('zero capacity is also rejected with a NassaqAlertDialog warning and does not POST', async () => {
    const api = {
      post: jest.fn(),
      get: jest.fn().mockResolvedValue({ data: [] }),
    };
    renderWithProviders(api);
    await seedPreview(api, _previewWithPair());

    const capInput = await screen.findByTestId('capacity-input-0');
    await act(async () => {
      fireEvent.change(capInput, { target: { value: '0' } });
    });
    const createBtn = screen.getByRole('button', { name: /إنشاء الفصول الناقصة/ });
    await act(async () => { fireEvent.click(createBtn); });

    const dialog = await screen.findByTestId('nassaq-alert-dialog');
    expect(dialog).toHaveAttribute('data-nassaq-alert', 'warning');
    expect(dialog.textContent).toMatch(/السعة يجب أن تكون رقماً صحيحاً بين 1 و 500/);

    const createCalls = api.post.mock.calls.filter(c => String(c[0]).includes('/create-missing-classes'));
    expect(createCalls).toHaveLength(0);
  });
});
