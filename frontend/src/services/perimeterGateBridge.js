let handler = null;

export function registerPerimeterGateHandler(fn) {
  handler = fn;
  return () => {
    if (handler === fn) handler = null;
  };
}

export function isPerimeterGateHandlerRegistered() {
  return typeof handler === 'function';
}

export function notifyWorkspaceNotMaterialised() {
  if (typeof handler !== 'function') return;
  try {
    handler();
  } catch {
    // handler is best-effort UI; never break the rejection chain
  }
}

let dialogShownThisSession = false;

export function hasShownBootstrapDialogThisSession() {
  return dialogShownThisSession;
}

export function markBootstrapDialogShownThisSession() {
  dialogShownThisSession = true;
}

export function resetBootstrapDialogGuard() {
  dialogShownThisSession = false;
}
