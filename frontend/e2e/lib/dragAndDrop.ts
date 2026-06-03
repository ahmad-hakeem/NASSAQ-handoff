import { Locator, Page } from '@playwright/test';

/**
 * Real-browser HTML5 drag-and-drop helper.
 *
 * Playwright's mouse-based `locator.dragTo()` dispatches mousedown /
 * mousemove / mouseup — it does NOT fire the native HTML5 drag events
 * (`dragstart`, `dragover`, `drop`, `dragend`) that a `draggable`
 * element relies on, and it cannot carry a `DataTransfer` payload. The
 * student class-transfer chips use the native HTML5 DnD API
 * (`StudentClassGrid.jsx`), so a faithful test has to fire the real
 * drag events with a shared `DataTransfer`.
 *
 * This runs entirely inside the live Chromium page: it constructs a
 * real `DataTransfer`, then dispatches real bubbling `DragEvent`s on the
 * real DOM nodes so React's delegated `onDragStart` / `onDragOver` /
 * `onDrop` handlers run exactly as they do for a human's mouse drag.
 * The same `DataTransfer` instance is threaded through every event so
 * the payload written on `dragstart` is the one the drop handler reads
 * back — which is the whole point jsdom cannot exercise.
 */
export async function html5DragAndDrop(page: Page, source: Locator, target: Locator) {
  const sourceHandle = await source.elementHandle();
  const targetHandle = await target.elementHandle();
  if (!sourceHandle || !targetHandle) {
    throw new Error('html5DragAndDrop: source or target element not found');
  }

  await page.evaluate(
    ({ src, tgt }) => {
      const dataTransfer = new DataTransfer();
      const fire = (el: Element, type: string) => {
        const event = new DragEvent(type, {
          bubbles: true,
          cancelable: true,
          composed: true,
          dataTransfer,
        });
        el.dispatchEvent(event);
      };
      fire(src as Element, 'dragstart');
      fire(tgt as Element, 'dragenter');
      fire(tgt as Element, 'dragover');
      fire(tgt as Element, 'drop');
      fire(src as Element, 'dragend');
    },
    { src: sourceHandle, tgt: targetHandle },
  );

  await sourceHandle.dispose();
  await targetHandle.dispose();
}
