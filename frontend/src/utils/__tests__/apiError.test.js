import { getApiErrorMessage } from '../apiError';

describe('getApiErrorMessage', () => {
  it('reads the canonical envelope (data.error.message)', () => {
    const error = {
      response: {
        data: { success: false, error: { code: 'X', message: 'لا يمكن الحفظ' } },
      },
    };
    expect(getApiErrorMessage(error, 'fallback')).toBe('لا يمكن الحفظ');
  });

  it('reads a legacy string detail', () => {
    const error = { response: { data: { detail: 'Legacy detail message' } } };
    expect(getApiErrorMessage(error, 'fallback')).toBe('Legacy detail message');
  });

  it('joins a validation-array detail', () => {
    const error = {
      response: {
        data: {
          detail: [
            { msg: 'field a required' },
            { message: 'field b invalid' },
            'plain string entry',
          ],
        },
      },
    };
    expect(getApiErrorMessage(error, 'fallback')).toBe(
      'field a required, field b invalid, plain string entry'
    );
  });

  it('reads an object detail.message', () => {
    const error = { response: { data: { detail: { message: 'nested object message' } } } };
    expect(getApiErrorMessage(error, 'fallback')).toBe('nested object message');
  });

  it('accepts a raw envelope passed directly', () => {
    const envelope = { success: false, error: { message: 'direct envelope message' } };
    expect(getApiErrorMessage(envelope, 'fallback')).toBe('direct envelope message');
  });

  it('reads an axios response / resolved body (res.data)', () => {
    const response = { data: { error: { message: 'from res.data' } } };
    expect(getApiErrorMessage(response, 'fallback')).toBe('from res.data');
  });

  it('does NOT leak a plain Error message (e.g. "Network Error")', () => {
    const error = new Error('Network Error');
    expect(getApiErrorMessage(error, 'fallback')).toBe('fallback');
  });

  it('returns the fallback when the value is empty or missing', () => {
    expect(getApiErrorMessage(undefined, 'fallback')).toBe('fallback');
    expect(getApiErrorMessage(null, 'fallback')).toBe('fallback');
    expect(getApiErrorMessage({}, 'fallback')).toBe('fallback');
    expect(getApiErrorMessage({ response: { data: {} } }, 'fallback')).toBe('fallback');
  });

  it('defaults the fallback to undefined when not supplied', () => {
    expect(getApiErrorMessage(new Error('boom'))).toBeUndefined();
  });

  it('prefers the canonical envelope over legacy detail', () => {
    const error = {
      response: {
        data: { error: { message: 'canonical wins' }, detail: 'legacy loses' },
      },
    };
    expect(getApiErrorMessage(error, 'fallback')).toBe('canonical wins');
  });

  it('falls back to a top-level message when no error/detail present', () => {
    const error = { response: { data: { success: false, message: 'top level message' } } };
    expect(getApiErrorMessage(error, 'fallback')).toBe('top level message');
  });
});
