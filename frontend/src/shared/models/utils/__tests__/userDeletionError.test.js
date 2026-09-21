import { getUserDeletionError } from '../userDeletionError';

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
});