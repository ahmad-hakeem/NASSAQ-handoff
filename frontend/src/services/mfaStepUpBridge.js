let handler = null;

export function registerMfaStepUpHandler(fn) {
  handler = fn;
  return () => {
    if (handler === fn) handler = null;
  };
}

export function isMfaStepUpHandlerRegistered() {
  return typeof handler === 'function';
}

export function requestMfaStepUp(errorContext) {
  if (typeof handler !== 'function') {
    return Promise.reject(new Error('MFA_STEPUP_HANDLER_UNAVAILABLE'));
  }
  return handler(errorContext);
}
