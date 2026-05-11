/**
 * MasterMatrixDnd — drag-and-drop wrappers for the draft Master Grid.
 *
 * Responsibilities:
 *   • DraggableSession  — wraps a filled cell so the principal can pick
 *                         it up with the pointer. Uses a small activation
 *                         distance so a plain click still opens the
 *                         existing SessionDetailModal (drag-and-drop is an
 *                         acceleration layer, never the only path).
 *   • DroppableSlot     — wraps every (teacher × day × period) cell so
 *                         the engine can land a drag there. Renders an
 *                         emerald "valid drop" ring while a drag is over
 *                         the cell — the visual is intentionally quiet at
 *                         100-teacher density.
 *   • useDragSensors    — PointerSensor with `distance: 6` so click and
 *                         keyboard fallback paths keep working.
 *
 * Backend endpoints used by the page-level drop handler (not by this
 * file): POST /smart-scheduling/sessions/move (empty target) and
 * POST /smart-scheduling/sessions/swap (filled target). Both endpoints
 * already enforce tenant isolation, draft-only mutability and full
 * conflict detection — drag-and-drop never bypasses backend validation.
 */
import React from 'react';
import { useDraggable, useDroppable } from '@dnd-kit/core';
import { useSensor, useSensors, PointerSensor, KeyboardSensor } from '@dnd-kit/core';

export function useDragSensors() {
  // distance: 6px — keeps click-to-open as the dominant interaction.
  // Without this, every mousedown-up on a session cell would be treated
  // as a drag and the SessionDetailModal would never open.
  return useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor),
  );
}

/**
 * DraggableSession — pick-up wrapper for a filled, mutable cell.
 *
 * `payload` is forwarded verbatim to DragEndEvent.active.data.current so
 * the page-level onDragEnd handler has every field it needs to call the
 * backend without re-deriving identity from the DOM.
 */
export function DraggableSession({ id, payload, disabled = false, children }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id,
    data: payload,
    disabled,
  });
  // We deliberately do NOT apply CSS.Translate transforms — the matrix
  // grid layout would tear visually if a single cell shifted out of its
  // track. The pointer cursor + opacity are enough drag feedback; the
  // real reconciliation comes from the backend response.
  const style = {
    opacity: isDragging ? 0.4 : 1,
    cursor: disabled ? undefined : 'grab',
    touchAction: 'none',
  };
  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      data-dragging={isDragging ? 'true' : undefined}
      className="h-full"
    >
      {children}
    </div>
  );
}

/**
 * DroppableSlot — landing wrapper for every grid cell.
 *
 * Renders a thin emerald ring when a drag is over the slot. The wrapper
 * itself stays transparent so the underlying FilledCell / EmptyCell
 * keeps its existing visual.
 */
export function DroppableSlot({ id, payload, disabled = false, children }) {
  const { setNodeRef, isOver, active } = useDroppable({ id, data: payload, disabled });
  // Don't ring the source cell as a valid target — the backend would
  // reject the no-op move anyway, and the visual would mislead the user.
  const isSource = !!(active && String(active.id) === String(id));
  const ring = isOver && !isSource
    ? 'ring-2 ring-inset ring-emerald-400 bg-emerald-50/40'
    : '';
  return (
    <div
      ref={setNodeRef}
      className={`h-full w-full transition-colors ${ring}`}
      data-droppable-active={isOver && !isSource ? 'true' : undefined}
    >
      {children}
    </div>
  );
}
