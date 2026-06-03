/**
 * End-to-end orchestrator for a student class-transfer (POST
 * /students/transfer-class). Kept out of the page component so the full flow —
 * success, real backend error, no-response retry, and malformed 2xx — is unit
 * testable without rendering the heavy management page.
 *
 * Messaging contract (Task #784): a transfer failure must NEVER collapse into
 * the cause-hiding generic "فشل نقل الطالب" string. There are exactly three
 * failure messages:
 *   - the backend's own message, whenever the server returns one;
 *   - `messages.serverError`, when the server responded but gave no usable
 *     message (or returned a non-JSON 2xx body);
 *   - `messages.network`, only for a genuine no-response/network/timeout.
 */
import { interpretTransferSuccess, classifyTransferError } from './transferResult';

/**
 * @param {object} args
 * @param {object} args.api Axios instance.
 * @param {string} args.studentId
 * @param {string} args.targetClassId
 * @param {object} [args.headers]
 * @param {{transferred:string, serverError:string, network:string}} args.messages
 * @param {(outcome:object)=>void} args.onSuccess Apply success to UI state.
 * @param {(msg:string)=>void} args.onToast Show the success toast.
 * @param {(msg:string)=>void} args.onError Show an error dialog (NassaqAlertDialog).
 * @param {number} [args.maxAttempts=3]
 * @param {(ms:number)=>Promise<void>} [args.sleep] Injectable delay (tests stub it).
 * @returns {Promise<{status:string}>}
 */
export async function executeStudentTransfer({
  api,
  studentId,
  targetClassId,
  headers = {},
  messages,
  onSuccess,
  onToast,
  onError,
  maxAttempts = 3,
  sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
}) {
  const payload = { student_id: studentId, target_class_id: targetClassId };

  // The transfer is idempotent (moving to a class the student is already in is
  // a clean no-op success), so a no-response/network failure is retried a few
  // times — mirroring the GET auto-retry the axios interceptor already does for
  // transient blips. We never optimistically move the student first, so a
  // failure leaves no ghost row and no stale counts to roll back.
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      const res = await api.post('/students/transfer-class', payload, { headers });
      const outcome = interpretTransferSuccess(res);
      if (outcome.ok) {
        onToast(messages.transferred);
        onSuccess(outcome);
        return { status: 'success' };
      }
      // 2xx but not a genuine success envelope (HTML SPA/gateway page, proxy
      // body, or {success:false}): backend message if any, else server-error.
      onError(outcome.backendMessage || messages.serverError);
      return { status: 'soft-error' };
    } catch (error) {
      const classified = classifyTransferError(error);
      if (classified.kind === 'canceled') return { status: 'canceled' };
      if (classified.kind === 'backend') {
        // Server responded — surface its message, or a transfer-specific
        // server-error message. Never the generic cause-hiding fallback.
        onError(classified.message || messages.serverError);
        return { status: 'backend-error' };
      }
      // no-response / network / timeout: retry, then a clear connection message.
      if (attempt < maxAttempts - 1) {
        await sleep(400 * (attempt + 1));
        continue;
      }
      onError(messages.network);
      return { status: 'network-error' };
    }
  }
  return { status: 'network-error' };
}
