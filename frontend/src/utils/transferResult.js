/**
 * Pure helpers that decide the outcome of a POST /students/transfer-class call
 * and pick the right user-facing message — WITHOUT ever collapsing a real
 * failure into the bare generic fallback that hides the cause.
 *
 * Why this exists: in production a transfer could fail with no usable axios
 * response (network drop, proxy timeout, or a non-JSON gateway page returned
 * with a 2xx). The old handler funnelled every such case into the generic
 * `failedToTransferStudent` string, so the actual reason was invisible. These
 * helpers separate three distinct outcomes — genuine success, a real backend
 * error (surface the backend's own Arabic message), and a no-response/network
 * failure (surface an accurate connection message) — and are unit-tested.
 */
import { getApiErrorMessage } from './apiError';

/**
 * Interpret a (resolved) axios response from the transfer endpoint.
 *
 * A success is recognised ONLY when the body is a JSON object with
 * `success === true`. A 2xx whose body is anything else — an HTML SPA/gateway
 * page, a proxy body, or `{ success:false }` — is treated as a failure, and the
 * backend message (if any) is extracted instead of being silently dropped.
 *
 * @param {*} res Axios response.
 * @returns {{ok:true, oldClassId:(string|null), oldCount:(number|null), targetCount:(number|null)}
 *          | {ok:false, backendMessage:(string|null)}}
 */
export function interpretTransferSuccess(res) {
  const body = res?.data;
  if (body && typeof body === 'object' && body.success === true) {
    return {
      ok: true,
      oldClassId: typeof body.old_class_id === 'string' ? body.old_class_id : null,
      oldCount: typeof body.old_class_current_students === 'number' ? body.old_class_current_students : null,
      targetCount: typeof body.target_class_current_students === 'number' ? body.target_class_current_students : null,
    };
  }
  return { ok: false, backendMessage: getApiErrorMessage({ data: body }) || null };
}

/**
 * Classify a caught axios error from the transfer endpoint.
 *
 * - `canceled`: StrictMode double-mount / route change / AbortController — not a
 *   real failure, the caller should stay silent.
 * - `backend`: the server answered (has `error.response`); surface its real
 *   message via the canonical envelope reader.
 * - `network`: no response at all (network drop / timeout / proxy failure);
 *   the caller should show an accurate connection message and may retry.
 *
 * @param {*} error
 * @returns {{kind:'canceled'} | {kind:'backend', message:(string|null)} | {kind:'network'}}
 */
export function classifyTransferError(error) {
  if (
    error &&
    (error.code === 'ERR_CANCELED' ||
      error.name === 'CanceledError' ||
      error.message === 'canceled')
  ) {
    return { kind: 'canceled' };
  }
  if (error && error.response) {
    return { kind: 'backend', message: getApiErrorMessage(error) || null };
  }
  return { kind: 'network' };
}
