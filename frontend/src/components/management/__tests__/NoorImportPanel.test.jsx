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
import { render, screen, fireEvent, act, within } from '@testing-library/react';
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
