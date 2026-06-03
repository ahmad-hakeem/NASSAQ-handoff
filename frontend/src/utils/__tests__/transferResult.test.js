import { interpretTransferSuccess, classifyTransferError } from '../transferResult';

describe('interpretTransferSuccess', () => {
  test('recognises a genuine success envelope and extracts both counts', () => {
    const res = {
      data: {
        success: true,
        old_class_id: 'class-a',
        old_class_current_students: 3,
        target_class_current_students: 15,
      },
    };
    expect(interpretTransferSuccess(res)).toEqual({
      ok: true,
      oldClassId: 'class-a',
      oldCount: 3,
      targetCount: 15,
    });
  });

  test('a same-class no-op success (no counts) is still a success', () => {
    const res = { data: { success: true, message: 'الطالب موجود بالفعل في هذا الفصل' } };
    const out = interpretTransferSuccess(res);
    expect(out.ok).toBe(true);
    expect(out.oldCount).toBeNull();
    expect(out.targetCount).toBeNull();
  });

  test('a 2xx with success:false surfaces the backend message, not a generic fallback', () => {
    const res = { data: { success: false, error: { message: 'الفصل ممتلئ' } } };
    expect(interpretTransferSuccess(res)).toEqual({ ok: false, backendMessage: 'الفصل ممتلئ' });
  });

  test('a 2xx that returns an HTML SPA/gateway page is a failure with no message', () => {
    const res = { data: '<!doctype html><html><body>app</body></html>' };
    expect(interpretTransferSuccess(res)).toEqual({ ok: false, backendMessage: null });
  });
});

describe('classifyTransferError', () => {
  test('a real backend error response surfaces the canonical envelope message', () => {
    const error = { response: { status: 404, data: { success: false, error: { message: 'الفصل غير موجود' } } } };
    expect(classifyTransferError(error)).toEqual({ kind: 'backend', message: 'الفصل غير موجود' });
  });

  test('a backend error without a usable message returns null so the caller can apply a specific transfer server-error message (never the generic fallback)', () => {
    const error = { response: { status: 500, data: {} } };
    expect(classifyTransferError(error)).toEqual({ kind: 'backend', message: null });
  });

  test('a no-response/network failure is classified as network (not a backend error)', () => {
    const error = { request: {}, message: 'Network Error' };
    expect(classifyTransferError(error)).toEqual({ kind: 'network' });
  });

  test('a timeout with no response is classified as network', () => {
    const error = { code: 'ECONNABORTED', message: 'timeout of 0ms exceeded' };
    expect(classifyTransferError(error)).toEqual({ kind: 'network' });
  });

  test('a canceled request is classified as canceled so the UI stays silent', () => {
    expect(classifyTransferError({ code: 'ERR_CANCELED', message: 'canceled' })).toEqual({ kind: 'canceled' });
    expect(classifyTransferError({ name: 'CanceledError' })).toEqual({ kind: 'canceled' });
  });
});
