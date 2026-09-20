import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import ExternalImportReview, { downloadImportReview, hasImportBlockers } from '../components/ExternalImportReview';

const makeDraft = (overrides = {}) => ({
  draft_id: 'draft-1', fingerprint: 'exact-file-hash', preview_version: 1, import_type: 'students',
  can_confirm: true, errors: [], warnings: [], summary: { create: 1 },
  rows: [{ row: 2, name: 'Student one', national_id: '123', parent_name: 'Parent', grade: 'Grade 1', class_name: 'A', action: 'create', relationships: { parent: 'reuse', class: 'create' }, errors: [], warnings: [] }],
  ...overrides,
});
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
const upload = (name = 'students.csv') => fireEvent.change(screen.getByLabelText('Excel or CSV file'), { target: { files: [new File(['name\nStudent'], name)] } });
const preview = async () => {
  upload();
  fireEvent.click(screen.getByRole('button', { name: 'Preview file' }));
  await screen.findByText('Preview only — no data has been saved yet');
};

describe('mandatory external import review', () => {
  let api, complete, props;
  beforeEach(() => {
    api = { post: jest.fn().mockResolvedValue({ data: makeDraft() }) };
    complete = jest.fn();
    props = { api, headers: { 'X-School-Context': 'school-1' }, importType: 'students', isRTL: false, onSelectionChange: jest.fn(), onComplete: complete };
  });

  test('preview does not import; explicit acknowledgement commits only the server draft and delivers actual results', async () => {
    render(<ExternalImportReview {...props} />);
    await preview();
    expect(complete).not.toHaveBeenCalled();
    expect(api.post.mock.calls[0][0]).toBe('/bulk/preview/students');
    expect(api.post.mock.calls[0][1].get('file').name).toBe('students.csv');
    const button = screen.getByRole('button', { name: 'Confirm import' });
    expect(button).toBeDisabled();
    fireEvent.click(screen.getByLabelText(/I reviewed the preview/));
    const request = deferred();
    api.post.mockImplementation(url => url === '/bulk/confirm' ? request.promise : Promise.resolve({ data: {} }));
    fireEvent.click(button);
    fireEvent.click(button);
    expect(api.post.mock.calls.filter(([url]) => url === '/bulk/confirm')).toHaveLength(1);
    expect(api.post).toHaveBeenCalledWith('/bulk/confirm', {
      draft_id: 'draft-1', fingerprint: 'exact-file-hash', preview_version: 1, acknowledged: true,
    }, expect.objectContaining({ headers: props.headers }));
    await act(async () => request.resolve({ data: { imported: 1, assigned: 1 } }));
    expect(complete).toHaveBeenCalledWith({ imported: 1, assigned: 1 }, 'students');
  });

  test('blocks for a row error outside the visible page and for global errors regardless of can_confirm', async () => {
    const rows = Array.from({ length: 21 }, (_, i) => ({ row: i + 2, name: `Student ${i}`, action: 'create', errors: i === 20 ? ['bad identity'] : [] }));
    api.post.mockResolvedValue({ data: makeDraft({ rows }) });
    render(<ExternalImportReview {...props} />);
    await preview();
    expect(screen.queryByText('bad identity')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Confirm import' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.getByText('bad identity')).toBeInTheDocument();
    expect(hasImportBlockers(makeDraft({ errors: ['file issue'] }))).toBe(true);
    expect(hasImportBlockers(makeDraft({ can_confirm: false }))).toBe(true);
  });

  test('searches all rows, shows contacts and relationships, and requires warning acknowledgement', async () => {
    api.post.mockResolvedValue({ data: makeDraft({ warnings: ['Review reused parent'] }) });
    render(<ExternalImportReview {...props} />);
    await preview();
    expect(screen.getByText('123')).toBeInTheDocument();
    expect(screen.getByText('Parent: Reuse')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText(/I reviewed the preview/));
    expect(screen.getByRole('button', { name: 'Confirm import' })).toBeDisabled();
    fireEvent.click(screen.getByLabelText(/I reviewed all warnings/));
    expect(screen.getByRole('button', { name: 'Confirm import' })).toBeEnabled();
    fireEvent.change(screen.getByLabelText('Search preview rows'), { target: { value: 'missing' } });
    expect(screen.getByText('No matching rows.')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Search preview rows'), { target: { value: '123' } });
    expect(screen.getByText('123')).toBeInTheDocument();
  });

  test('guards duplicate previews and discards a late response after selecting another file', async () => {
    const request = deferred();
    api.post.mockImplementation(url => url.includes('/preview/') ? request.promise : Promise.resolve({ data: {} }));
    render(<ExternalImportReview {...props} />);
    upload();
    const button = screen.getByRole('button', { name: 'Preview file' });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(api.post.mock.calls.filter(([url]) => url.includes('/preview/'))).toHaveLength(1);
    upload('replacement.csv');
    await act(async () => request.resolve({ data: makeDraft() }));
    expect(screen.queryByText(/Preview only/)).not.toBeInTheDocument();
    expect(api.post).toHaveBeenCalledWith('/bulk/draft/draft-1/discard', {}, expect.anything());
    expect(complete).not.toHaveBeenCalled();
  });

  test('cancel discards a draft and never imports', async () => {
    render(<ExternalImportReview {...props} />);
    await preview();
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(api.post).toHaveBeenCalledWith('/bulk/draft/draft-1/discard', {}, expect.anything());
    expect(screen.queryByRole('button', { name: 'Confirm import' })).not.toBeInTheDocument();
    expect(complete).not.toHaveBeenCalled();
  });

  test('renders normalized backend student fields and localized relationship counts without internal keys', async () => {
    const row = {
      ...makeDraft().rows[0], grade: { grade: '1', label_ar: 'الصف الأول', label_en: 'First grade' },
      raw_class_name: 'First-A', class_name: undefined, optional_values: { email: 'student@example.test', phone: '0501234567' },
      relationships: { parent_account: { action: 'create', key: 'private-id' }, class: { action: 'reuse', key: 'class-id', restore: true, repair_grade_link: true } },
    };
    api.post.mockResolvedValue({ data: makeDraft({ rows: [row], summary: { parent_account_create: 1, assignments: 1 } }) });
    render(<ExternalImportReview {...props} />);
    await preview();
    expect(screen.getByText('First grade')).toBeInTheDocument();
    expect(screen.getByText('First-A')).toBeInTheDocument();
    expect(screen.getByText('student@example.test')).toBeInTheDocument();
    expect(screen.getByText('Parent account — Create: 1')).toBeInTheDocument();
    expect(screen.getByText(/Restore class/)).toHaveTextContent('Repair grade link');
    expect(screen.queryByText(/private-id/)).not.toBeInTheDocument();
  });

  test('teacher conflicts block the teacher review endpoint', async () => {
    api.post.mockResolvedValue({ data: makeDraft({ import_type: 'teachers', rows: [{ row: 2, name: 'Teacher', action: 'conflict', errors: ['Email exists'] }] }) });
    render(<ExternalImportReview {...props} importType="teachers" />);
    await preview();
    expect(api.post.mock.calls[0][0]).toBe('/bulk/preview/teachers');
    expect(screen.getByText('Email exists')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Confirm import' })).toBeDisabled();
  });

  test('scope change during confirmation suppresses the actual-results callback', async () => {
    const { rerender } = render(<ExternalImportReview key="old" {...props} />);
    await preview();
    const request = deferred();
    api.post.mockImplementation(url => url === '/bulk/confirm' ? request.promise : Promise.resolve({ data: {} }));
    fireEvent.click(screen.getByLabelText(/I reviewed the preview/));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm import' }));
    rerender(<ExternalImportReview key="new" {...props} />);
    await act(async () => request.resolve({ data: { imported: 1 } }));
    expect(complete).not.toHaveBeenCalled();
  });

  test.each(['type', 'actor', 'tenant'])('a %s remount suppresses stale requests and uses the original scope for discard', async (scope) => {
    const request = deferred();
    api.post.mockImplementation(url => url.includes('/preview/') ? request.promise : Promise.resolve({ data: {} }));
    const { rerender } = render(<ExternalImportReview key="original" {...props} />);
    upload();
    fireEvent.click(screen.getByRole('button', { name: 'Preview file' }));
    rerender(<ExternalImportReview key={scope} {...props} headers={{ 'X-School-Context': 'school-2' }} />);
    await act(async () => request.resolve({ data: makeDraft() }));
    expect(screen.queryByText(/Preview only/)).not.toBeInTheDocument();
    expect(api.post).toHaveBeenCalledWith('/bulk/draft/draft-1/discard', {}, { headers: props.headers });
  });

  test('stale confirmation requires a fresh preview and never reports success', async () => {
    render(<ExternalImportReview {...props} />);
    await preview();
    api.post.mockRejectedValue({ response: { status: 409, data: { detail: 'Draft stale' } } });
    fireEvent.click(screen.getByLabelText(/I reviewed the preview/));
    fireEvent.click(screen.getByRole('button', { name: 'Confirm import' }));
    await screen.findByRole('alert');
    expect(screen.getByRole('alert')).toHaveTextContent('create a new preview');
    expect(complete).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: 'Confirm import' })).not.toBeInTheDocument();
  });

  test('Arabic review is RTL with explicit Arabic confirmation', async () => {
    render(<ExternalImportReview {...props} isRTL />);
    fireEvent.change(screen.getByLabelText('ملف Excel أو CSV'), { target: { files: [new File(['data'], 'students.csv')] } });
    fireEvent.click(screen.getByRole('button', { name: 'معاينة الملف' }));
    expect(await screen.findByText('معاينة فقط — لم تُحفظ أي بيانات بعد')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'مراجعة الاستيراد الخارجي' })).toHaveAttribute('dir', 'rtl');
    expect(screen.getByRole('button', { name: 'تأكيد الاستيراد' })).toBeDisabled();
  });

  test('error download uses fixed JSON filename and revokes its URL', async () => {
    const create = URL.createObjectURL;
    const revoke = URL.revokeObjectURL;
    URL.createObjectURL = jest.fn(() => 'blob:safe');
    URL.revokeObjectURL = jest.fn();
    const click = jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () {
      expect(this.download).toBe('external-import-review.json');
    });
    downloadImportReview(makeDraft({ errors: ['=HYPERLINK("evil")'] }));
    expect(URL.createObjectURL.mock.calls[0][0].type).toBe('application/json;charset=utf-8');
    await waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:safe'));
    click.mockRestore();
    URL.createObjectURL = create;
    URL.revokeObjectURL = revoke;
  });
});