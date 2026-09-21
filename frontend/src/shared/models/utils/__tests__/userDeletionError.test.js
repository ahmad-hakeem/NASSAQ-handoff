import { formatUserDeletionError, getUserDeletionError } from '../userDeletionError';
import ar from '@/locales/ar.json';
import en from '@/locales/en.json';

describe('getUserDeletionError', () => {
  it('normalizes the structured 409 envelope and only retains safe dependency fields', () => {
    const result = getUserDeletionError({
      response: {
        status: 409,
        data: {
          success: false,
          error: {
            code: 'DELETE_DEPENDENCY_BLOCKED',
            message: 'تعذر الحذف',
            detail: {
              dependencies: [{
                reason: 'account_ownership_mismatch',
                category: 'dependency',
                table: 'users',
                count: 2,
                resolution: 'راجع ملكية الحساب.',
                full_name: 'Must not be exposed',
              }],
            },
          },
        },
      },
    }, 'teacher');

    expect(result).toEqual({
      status: 409,
      code: 'DELETE_DEPENDENCY_BLOCKED',
      message: 'تعذر الحذف',
      dependencies: [{
        reason: 'account_ownership_mismatch',
        category: 'dependency',
        table: 'users',
        count: 2,
        resolution: 'راجع ملكية الحساب.',
      }],
    });
  });

  it('uses a permission-specific safe message for an unstructured 403', () => {
    expect(getUserDeletionError({ response: { status: 403, data: {} } }, 'teacher')).toEqual({
      status: 403,
      code: undefined,
      message: 'لا تملك صلاحية حذف هذا الحساب.',
      dependencies: [],
    });
  });

  it('uses a retryable generic message for an unstructured 500', () => {
    expect(getUserDeletionError({ response: { status: 500, data: {} } }, 'teacher')).toEqual({
      status: 500,
      code: undefined,
      message: 'تعذر إكمال حذف الحساب. لم يُحذف أي شيء؛ حاول مرة أخرى.',
      dependencies: [],
    });
  });

  it('prefers localized copy for a known dependency blocker', () => {
    const t = jest.fn((key) => ({
      teacherDeleteConflict: 'This teacher cannot be deleted while blocking links remain.',
    }[key] || key));

    expect(getUserDeletionError({
      response: {
        status: 409,
        data: {
          error: {
            code: 'DELETE_DEPENDENCY_BLOCKED',
            message: 'رسالة الخادم',
          },
        },
      },
    }, 'teacher', t).message).toBe(
      'This teacher cannot be deleted while blocking links remain.'
    );
    expect(t).toHaveBeenCalledWith('teacherDeleteConflict');
  });

  it('localizes distinct actionable ownership blockers in Arabic and English while retaining raw reason codes', () => {
    const error = {
      response: {
        status: 409,
        data: {
          error: {
            code: 'DELETE_DEPENDENCY_BLOCKED',
            detail: {
              dependencies: [
                { reason: 'account_tenant_mismatch', table: 'users', count: 1 },
                { reason: 'additional_linked_roles', table: 'users', count: 2 },
              ],
            },
          },
        },
      },
    };
    const translator = messages => key => messages[key] || key;

    const arabic = getUserDeletionError(error, 'teacher', translator(ar));
    const english = getUserDeletionError(error, 'teacher', translator(en));

    expect(arabic.dependencies[0]).toMatchObject({
      reason: 'account_tenant_mismatch',
      reasonLabel: 'حساب تسجيل الدخول تابع لمدرسة أخرى.',
      resolutionLabel: expect.stringContaining('تصحيح ملكية الحساب'),
    });
    expect(arabic.dependencies[1].reasonLabel).toContain('أدوار نشطة إضافية');
    expect(english.dependencies[0]).toMatchObject({
      reason: 'account_tenant_mismatch',
      reasonLabel: 'The login account belongs to a different school.',
      resolutionLabel: expect.stringContaining('school ownership'),
    });
    expect(english.dependencies[1].reasonLabel).toContain('additional active roles');
    expect(english.dependencies[0].reasonLabel).not.toBe(arabic.dependencies[0].reasonLabel);
    expect(formatUserDeletionError(english)).toContain(
      '• The login account belongs to a different school.\n  Ask a platform administrator'
    );
  });
});
