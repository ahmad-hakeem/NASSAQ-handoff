import { executeStudentTransfer } from '../studentTransfer';

const MESSAGES = {
  transferred: 'TRANSFERRED',
  serverError: 'SERVER_ERROR',
  network: 'NETWORK',
};

function makeHarness(apiPost) {
  const onSuccess = jest.fn();
  const onToast = jest.fn();
  const onError = jest.fn();
  const sleep = jest.fn().mockResolvedValue(undefined);
  const api = { post: apiPost };
  const run = () =>
    executeStudentTransfer({
      api,
      studentId: 's1',
      targetClassId: 'target',
      messages: MESSAGES,
      onSuccess,
      onToast,
      onError,
      sleep,
    });
  return { api, onSuccess, onToast, onError, sleep, run };
}

describe('executeStudentTransfer', () => {
  test('success: toasts, applies success outcome with both counts, no error shown', async () => {
    const post = jest.fn().mockResolvedValue({
      data: {
        success: true,
        old_class_id: 'src',
        old_class_current_students: 3,
        target_class_current_students: 15,
      },
    });
    const h = makeHarness(post);
    const result = await h.run();

    expect(result.status).toBe('success');
    expect(h.onToast).toHaveBeenCalledWith('TRANSFERRED');
    expect(h.onSuccess).toHaveBeenCalledWith({
      ok: true,
      oldClassId: 'src',
      oldCount: 3,
      targetCount: 15,
    });
    expect(h.onError).not.toHaveBeenCalled();
    expect(post).toHaveBeenCalledTimes(1);
  });

  test('real backend error WITH a message surfaces that message, leaves UI state untouched', async () => {
    const post = jest.fn().mockRejectedValue({
      response: { status: 409, data: { success: false, error: { message: 'الفصل ممتلئ' } } },
    });
    const h = makeHarness(post);
    const result = await h.run();

    expect(result.status).toBe('backend-error');
    expect(h.onError).toHaveBeenCalledWith('الفصل ممتلئ');
    expect(h.onSuccess).not.toHaveBeenCalled();
    expect(h.onToast).not.toHaveBeenCalled();
    expect(post).toHaveBeenCalledTimes(1);
  });

  test('backend error WITHOUT a usable message shows the specific server-error message, never a generic fallback', async () => {
    const post = jest.fn().mockRejectedValue({ response: { status: 500, data: {} } });
    const h = makeHarness(post);
    const result = await h.run();

    expect(result.status).toBe('backend-error');
    expect(h.onError).toHaveBeenCalledWith('SERVER_ERROR');
    expect(h.onError).not.toHaveBeenCalledWith('NETWORK');
    expect(h.onSuccess).not.toHaveBeenCalled();
  });

  test('a non-JSON 2xx (HTML SPA/gateway page) is treated as a server error, not a success', async () => {
    const post = jest.fn().mockResolvedValue({ data: '<!doctype html><html></html>' });
    const h = makeHarness(post);
    const result = await h.run();

    expect(result.status).toBe('soft-error');
    expect(h.onError).toHaveBeenCalledWith('SERVER_ERROR');
    expect(h.onSuccess).not.toHaveBeenCalled();
    expect(h.onToast).not.toHaveBeenCalled();
  });

  test('no-response/network failure retries the idempotent transfer, then shows the network message', async () => {
    const post = jest.fn().mockRejectedValue({ request: {}, message: 'Network Error' });
    const h = makeHarness(post);
    const result = await h.run();

    expect(result.status).toBe('network-error');
    expect(post).toHaveBeenCalledTimes(3); // default maxAttempts
    expect(h.sleep).toHaveBeenCalledTimes(2); // between the 3 attempts
    expect(h.onError).toHaveBeenCalledWith('NETWORK');
    expect(h.onSuccess).not.toHaveBeenCalled();
  });

  test('a transient network blip recovers on retry and completes the transfer', async () => {
    const post = jest
      .fn()
      .mockRejectedValueOnce({ request: {}, message: 'Network Error' })
      .mockResolvedValueOnce({ data: { success: true, target_class_current_students: 5 } });
    const h = makeHarness(post);
    const result = await h.run();

    expect(result.status).toBe('success');
    expect(post).toHaveBeenCalledTimes(2);
    expect(h.onSuccess).toHaveBeenCalledWith({ ok: true, oldClassId: null, oldCount: null, targetCount: 5 });
    expect(h.onToast).toHaveBeenCalledWith('TRANSFERRED');
    expect(h.onError).not.toHaveBeenCalled();
  });

  test('a canceled request stays silent (no error, no toast, no state change)', async () => {
    const post = jest.fn().mockRejectedValue({ code: 'ERR_CANCELED', message: 'canceled' });
    const h = makeHarness(post);
    const result = await h.run();

    expect(result.status).toBe('canceled');
    expect(h.onError).not.toHaveBeenCalled();
    expect(h.onToast).not.toHaveBeenCalled();
    expect(h.onSuccess).not.toHaveBeenCalled();
    expect(post).toHaveBeenCalledTimes(1);
  });
});
