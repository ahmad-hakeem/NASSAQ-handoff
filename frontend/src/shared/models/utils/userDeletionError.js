import { getApiErrorCode, getApiErrorMessage } from './apiError';

const STATUS_MESSAGES = {
  403: 'لا تملك صلاحية حذف هذا الحساب.',
  409: 'تعذر حذف الحساب لوجود ارتباطات تحتاج إلى مراجعة. عالج التفاصيل أدناه ثم أعد المحاولة.',
  500: 'تعذر إكمال حذف الحساب. لم يُحذف أي شيء؛ حاول مرة أخرى.',
};

const asSafeText = (value) => (
  typeof value === 'string' && value.trim() ? value.trim().slice(0, 500) : undefined
);

const normalizeDependency = (dependency) => {
  if (!dependency || typeof dependency !== 'object' || Array.isArray(dependency)) return null;

  const normalized = {
    reason: asSafeText(dependency.reason),
    category: asSafeText(dependency.category),
    table: asSafeText(dependency.table),
    count: Number.isFinite(dependency.count) && dependency.count >= 0
      ? dependency.count
      : undefined,
    resolution: asSafeText(dependency.resolution),
  };

  return Object.values(normalized).some((value) => value !== undefined) ? normalized : null;
};

/**
 * Normalizes deletion failures into the deliberately small, non-PII shape that
 * the confirmation dialog is allowed to render.
 */
export function getUserDeletionError(error, role) {
  const status = error?.response?.status;
  const body = error?.response?.data ?? error?.data;
  const detail = body?.error?.detail ?? body?.detail;
  const rawDependencies = (
    detail && typeof detail === 'object' ? detail.dependencies : undefined
  ) ?? body?.error?.dependencies;
  const dependencies = Array.isArray(rawDependencies)
    ? rawDependencies.map(normalizeDependency).filter(Boolean)
    : [];

  const fallback = STATUS_MESSAGES[status]
    || (role === 'teacher'
      ? 'فشل في حذف حساب المعلم. لم يُحذف أي شيء؛ حاول مرة أخرى.'
      : 'فشل في أرشفة الحساب. لم يتغير الحساب؛ حاول مرة أخرى.');

  return {
    status,
    code: getApiErrorCode(error),
    message: getApiErrorMessage(error, fallback),
    dependencies,
  };
}

export default getUserDeletionError;