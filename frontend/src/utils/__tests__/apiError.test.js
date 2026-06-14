import {
  getApiErrorMessage,
  getApiErrorCode,
  getLocalizedApiError,
  getValidationErrors,
  formatValidationErrors,
  getFormErrorMessage,
  classifyWriteError,
} from '../apiError';

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

// Minimal translator that mimics ThemeContext's `t`: returns a localized string
// for known keys and echoes the key otherwise.
const dict = {
  name: 'الاسم',
  email: 'البريد',
  password: 'كلمة المرور',
  validationRequired: 'مطلوب',
  validationInvalidEmail: 'بريد إلكتروني غير صالح',
  validationTooShort: 'قصير جداً',
};
const t = (key) => dict[key] || key;

const makeValidationError = (errors) => ({
  response: {
    status: 422,
    data: {
      success: false,
      error: { code: 'VALIDATION_ERROR', message: 'Request validation failed' },
      meta: { validation_errors: errors },
    },
  },
});

describe('apiError validation helpers', () => {
  describe('getValidationErrors', () => {
    it('extracts the per-field breakdown from meta.validation_errors', () => {
      const err = makeValidationError([
        { field: 'body.basic_info.name', message: 'Field required' },
        { field: 'body.basic_info.email', message: 'value is not a valid email' },
      ]);
      expect(getValidationErrors(err)).toEqual([
        { field: 'body.basic_info.name', message: 'Field required' },
        { field: 'body.basic_info.email', message: 'value is not a valid email' },
      ]);
    });

    it('returns [] when there is no per-field detail', () => {
      expect(getValidationErrors({ response: { data: { error: { message: 'boom' } } } })).toEqual([]);
      expect(getValidationErrors(new Error('Network Error'))).toEqual([]);
      expect(getValidationErrors(null)).toEqual([]);
    });

    it('reads a raw envelope body and an axios resolved body', () => {
      const raw = { success: false, meta: { validation_errors: [{ field: 'name', message: 'Field required' }] } };
      expect(getValidationErrors(raw)).toEqual([{ field: 'name', message: 'Field required' }]);
      expect(getValidationErrors({ data: raw })).toEqual([{ field: 'name', message: 'Field required' }]);
    });
  });

  describe('formatValidationErrors', () => {
    it('localizes field labels and messages when a translator is supplied', () => {
      const err = makeValidationError([
        { field: 'body.basic_info.name', message: 'Field required' },
        { field: 'body.basic_info.email', message: 'value is not a valid email address' },
      ]);
      expect(formatValidationErrors(err, t)).toEqual([
        'الاسم: مطلوب',
        'البريد: بريد إلكتروني غير صالح',
      ]);
    });

    it('humanizes unknown fields and keeps unmatched raw messages without a translator', () => {
      const err = makeValidationError([
        { field: 'body.some_custom_field', message: 'Value is not a recognized option' },
      ]);
      expect(formatValidationErrors(err)).toEqual([
        'Some Custom Field: Value is not a recognized option',
      ]);
    });

    it('maps a "too short" message to the localized key', () => {
      const err = makeValidationError([
        { field: 'password', message: 'String should have at least 8 characters' },
      ]);
      expect(formatValidationErrors(err, t)).toEqual(['كلمة المرور: قصير جداً']);
    });

    it('returns [] when there is no validation detail', () => {
      expect(formatValidationErrors({ response: { data: {} } }, t)).toEqual([]);
    });
  });

  describe('getFormErrorMessage', () => {
    it('surfaces a bulleted, localized list when per-field detail exists', () => {
      const err = makeValidationError([
        { field: 'name', message: 'Field required' },
        { field: 'email', message: 'value is not a valid email' },
      ]);
      expect(getFormErrorMessage(err, { t })).toBe('• الاسم: مطلوب\n• البريد: بريد إلكتروني غير صالح');
    });

    it('degrades to the generic top-level message when no per-field detail exists', () => {
      const err = { response: { data: { error: { message: 'Something broke' } } } };
      expect(getFormErrorMessage(err, { t, fallback: 'fallback' })).toBe('Something broke');
    });

    it('returns the fallback when nothing usable is found', () => {
      expect(getFormErrorMessage(new Error('Network Error'), { t, fallback: 'fallback' })).toBe('fallback');
    });
  });

  describe('getApiErrorMessage is unchanged for non-validation envelopes', () => {
    it('still reads data.error.message', () => {
      expect(getApiErrorMessage({ response: { data: { error: { message: 'boom' } } } })).toBe('boom');
    });
  });

  describe('getApiErrorCode', () => {
    it('reads the canonical envelope error.code', () => {
      const error = {
        response: { data: { success: false, error: { code: 'CLASS_CAPACITY_REACHED', message: 'م' } } },
      };
      expect(getApiErrorCode(error)).toBe('CLASS_CAPACITY_REACHED');
    });

    it('falls back to a structured detail.code', () => {
      const error = { response: { data: { error: { detail: { code: 'CLASS_CAPACITY_REACHED' } } } } };
      expect(getApiErrorCode(error)).toBe('CLASS_CAPACITY_REACHED');
    });

    it('returns undefined when no usable code is present', () => {
      expect(getApiErrorCode({ response: { data: { error: { message: 'x' } } } })).toBeUndefined();
      expect(getApiErrorCode(new Error('boom'))).toBeUndefined();
      expect(getApiErrorCode(null)).toBeUndefined();
    });
  });

  describe('getLocalizedApiError', () => {
    const capDict = { classCapacityReached: 'وصل هذا الفصل إلى الحد الأقصى المسموح به. الرجاء اختيار فصل آخر.' };
    const capT = (key) => capDict[key] || key;

    const fullEnvelope = {
      response: {
        data: {
          success: false,
          error: {
            code: 'CLASS_CAPACITY_REACHED',
            // The backend already sends a safe Arabic message, but the UI owns
            // the copy and should localize off the code.
            message: 'رسالة الخادم العربية',
          },
        },
      },
    };

    it('prefers the localized translation keyed off the error code', () => {
      expect(getLocalizedApiError(fullEnvelope, { t: capT })).toBe(capDict.classCapacityReached);
    });

    it('falls back to the backend message when no translator is supplied', () => {
      expect(getLocalizedApiError(fullEnvelope, {})).toBe('رسالة الخادم العربية');
    });

    it('falls back to the backend message for an unmapped code', () => {
      const error = { response: { data: { error: { code: 'SOME_OTHER_CODE', message: 'خطأ آخر' } } } };
      expect(getLocalizedApiError(error, { t: capT })).toBe('خطأ آخر');
    });

    it('never renders a bare i18n key when the translator has no entry', () => {
      const echoT = (key) => key; // translator with no matching entry
      expect(getLocalizedApiError(fullEnvelope, { t: echoT })).toBe('رسالة الخادم العربية');
    });

    it('uses the fallback when neither code nor message resolve anything', () => {
      expect(getLocalizedApiError(new Error('Network Error'), { t: capT, fallback: 'fb' })).toBe('fb');
    });
  });

  describe('classifyWriteError', () => {
    it('classifies a canceled request as canceled (UI stays silent)', () => {
      expect(classifyWriteError({ code: 'ERR_CANCELED', message: 'canceled' })).toEqual({ kind: 'canceled' });
      expect(classifyWriteError({ name: 'CanceledError' })).toEqual({ kind: 'canceled' });
      expect(classifyWriteError({ message: 'canceled' })).toEqual({ kind: 'canceled' });
    });

    it('classifies a backend response and surfaces its canonical message', () => {
      const error = { response: { status: 409, data: { success: false, error: { message: 'الفصل ممتلئ' } } } };
      expect(classifyWriteError(error)).toEqual({ kind: 'backend', message: 'الفصل ممتلئ' });
    });

    it('classifies a backend response with no usable message as backend + null', () => {
      expect(classifyWriteError({ response: { status: 500, data: {} } })).toEqual({ kind: 'backend', message: null });
    });

    it('classifies a no-response/network failure as network', () => {
      expect(classifyWriteError({ request: {}, message: 'Network Error' })).toEqual({ kind: 'network' });
    });

    it('classifies a timeout with no response as network', () => {
      expect(classifyWriteError({ code: 'ECONNABORTED', message: 'timeout of 0ms exceeded' })).toEqual({ kind: 'network' });
    });
  });
});
