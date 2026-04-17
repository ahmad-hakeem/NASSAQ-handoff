import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

// Suppress benign "ResizeObserver loop completed with undelivered notifications"
// warnings. This is a well-known browser quirk (not a real error) that triggers
// the CRA dev overlay and obscures the UI. It does not affect runtime behavior.
// IMPORTANT: capture-phase listeners run before CRA's dev overlay handler, so we
// can stop propagation before it shows the red overlay.
const RESIZE_OBSERVER_MSG = "ResizeObserver loop";
const isResizeObserverErr = (m) => typeof m === "string" && m.includes(RESIZE_OBSERVER_MSG);

window.addEventListener(
  "error",
  (e) => {
    if (isResizeObserverErr(e.message)) {
      e.stopImmediatePropagation();
      e.preventDefault();
      return false;
    }
  },
  true, // capture phase – beat the dev overlay
);
window.addEventListener(
  "unhandledrejection",
  (e) => {
    const msg = e.reason && (e.reason.message || String(e.reason));
    if (isResizeObserverErr(msg)) {
      e.stopImmediatePropagation();
      e.preventDefault();
      return false;
    }
  },
  true,
);

// Hide the CRA/webpack-dev-server overlay iframe if it slips through (defense
// in depth: a MutationObserver removes any overlay caused by the RO warning).
if (process.env.NODE_ENV !== "production") {
  const dropOverlay = () => {
    const iframe = document.body.querySelector(
      'iframe[style*="z-index: 2147483647"], iframe#webpack-dev-server-client-overlay',
    );
    if (iframe) {
      try {
        const text = iframe.contentDocument?.body?.innerText || "";
        if (isResizeObserverErr(text)) iframe.remove();
      } catch {
        /* cross-origin: ignore */
      }
    }
  };
  const mo = new MutationObserver(dropOverlay);
  mo.observe(document.documentElement, { childList: true, subtree: true });
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

requestAnimationFrame(() => {
  const splash = document.getElementById("initial-splash");
  if (splash) {
    splash.style.transition = "opacity 200ms ease-out";
    splash.style.opacity = "0";
    setTimeout(() => splash.remove(), 220);
  }
});
