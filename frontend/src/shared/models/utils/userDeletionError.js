import { getApiErrorCode, getApiErrorMessage } from './apiError';

const STATUS_MESSAGES = {
  403: 'لا تملك صلاحية حذف هذا الحساب.',
  409: 'تعذر حذف الحساب لوجود ارتباطات تحتاج إلى مراجعة. عالج التفاصيل أدناه ثم أعد المحاولة.',
  500: 'تعذر إكمال حذف الحساب. لم يُحذف أي شيء؛ حاول مرة أخرى.',
};

const STATUS_MESSAGE_KEYS = {
  403: 'teacherDeleteForbidden',
  409: 'teacherDeleteConflict',
  500: 'teacherDeleteServerError',
};

const ERROR_CODE_MESSAGE_KEYS = {
  DELETE_AUTHORIZATION_DENIED: 'teacherDeleteForbidden',
  DELETE_DEPENDENCY_BLOCKED: 'teacherDeleteConflict',
  DELETE_CONFIGURATION_ERROR: 'teacherDeleteConflict',
  DELETE_INTERNAL_ERROR: 'teacherDeleteServerError',
};

const DEPENDENCY_MESSAGE_KEYS = {
  profile_account_link_mismatch: {
    reason: 'teacherDeleteReasonProfileAccountLinkMismatch',
    resolution: 'teacherDeleteResolutionProfileAccountLinkMismatch',
  },
  account_tenant_mismatch: {
    reason: 'teacherDeleteReasonAccountTenantMismatch',
    resolution: 'teacherDeleteResolutionAccountTenantMismatch',
  },
  account_role_mismatch: {
    reason: 'teacherDeleteReasonAccountRoleMismatch',
    resolution: 'teacherDeleteResolutionAccountRoleMismatch',
  },
  additional_linked_roles: {
    reason: 'teacherDeleteReasonAdditionalLinkedRoles',
    resolution: 'teacherDeleteResolutionAdditionalLinkedRoles',
  },
  parent_profile_claim: {
    reason: 'teacherDeleteReasonParentProfileClaim',
    resolution: 'teacherDeleteResolutionParentProfileClaim',
  },
  student_profile_claim: {
    reason: 'teacherDeleteReasonStudentProfileClaim',
    resolution: 'teacherDeleteResolutionStudentProfileClaim',
  },
  primary_tenant_mismatch: {
    reason: 'teacherDeleteReasonPrimaryTenantMismatch',
    resolution: 'teacherDeleteResolutionPrimaryTenantMismatch',
  },
  // Older API responses used one aggregate reason for the ownership checks.
  // Keep it readable while retaining the raw code for support diagnostics.
  account_ownership_mismatch: {
    reason: 'teacherDeleteReasonAccountOwnershipMismatch',
    resolution: 'teacherDeleteResolutionAccountOwnershipMismatch',
  },
};

const asSafeText = (value) => (
  typeof value === 'string' && value.trim() ? value.trim().slice(0, 500) : undefined
);

const translate = (t, key) => {
  if (typeof t !== 'function' || !key) return undefined;
  const message = t(key);
  return typeof message === 'string' && message.trim() && message !== key
    ? message
    : undefined;
};

const normalizeDependency = (dependency, t) => {
  if (!dependency || typeof dependency !== 'object' || Array.isArray(dependency)) return null;
  const reason = asSafeText(dependency.reason);
  const messageKeys = DEPENDENCY_MESSAGE_KEYS[reason];

  const normalized = {
    reason,
    category: asSafeText(dependency.category),
    table: asSafeText(dependency.table),
    count: Number.isFinite(dependency.count) && dependency.count >= 0
      ? dependency.count
      : undefined,
    resolution: asSafeText(dependency.resolution),
  };
  const reasonLabel = translate(t, messageKeys?.reason);
  const resolutionLabel = translate(t, messageKeys?.resolution);
  if (reasonLabel) normalized.reasonLabel = reasonLabel;
  if (resolutionLabel) normalized.resolutionLabel = resolutionLabel;

  return Object.values(normalized).some((value) => value !== undefined) ? normalized : null;
};

/**
 * Normalizes deletion failures into the deliberately small, non-PII shape that
 * the confirmation dialog is allowed to render.
 */
export function getUserDeletionError(error, role, t) {
  const status = error?.response?.status;
  const body = error?.response?.data ?? error?.data;
  const detail = body?.error?.detail ?? body?.detail;
  const rawDependencies = (
    detail && typeof detail === 'object' ? detail.dependencies : undefined
  ) ?? body?.error?.dependencies;
  const dependencies = Array.isArray(rawDependencies)
    ? rawDependencies.map(dependency => normalizeDependency(dependency, t)).filter(Boolean)
    : [];
  const code = getApiErrorCode(error);

  const fallback = translate(t, STATUS_MESSAGE_KEYS[status])
    || STATUS_MESSAGES[status]
    || (role === 'teacher'
      ? translate(t, 'teacherDeleteFailed')
        || 'فشل في حذف حساب المعلم. لم يُحذف أي شيء؛ حاول مرة أخرى.'
      : 'فشل في أرشفة الحساب. لم يتغير الحساب؛ حاول مرة أخرى.');
  const localizedCodeMessage = translate(t, ERROR_CODE_MESSAGE_KEYS[code]);

  return {
    status,
    code,
    message: localizedCodeMessage || getApiErrorMessage(error, fallback),
    dependencies,
  };
}

export function formatUserDeletionError(deletionError) {
  if (!deletionError?.dependencies?.length) return deletionError?.message;
  const blockers = deletionError.dependencies.map((dependency) => {
    const reason = dependency.reasonLabel || dependency.reason;
    const resolution = dependency.resolutionLabel || dependency.resolution;
    if (!reason) return resolution ? `• ${resolution}` : '';
    return resolution ? `• ${reason}\n  ${resolution}` : `• ${reason}`;
  }).filter(Boolean);
  return blockers.length
    ? `${deletionError.message}\n\n${blockers.join('\n')}`
    : deletionError.message;
}

export default getUserDeletionError;