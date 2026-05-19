import * as React from 'react';
import { cn } from '@/lib/utils';

/**
 * Task #274 — small reusable table → cards adaptor.
 *
 * Renders a real `<table>` at sm+ (≥640px) and a stacked card list
 * (label → value pairs) below 640px. Both modes share the same
 * `columns` + `rows` props so callers stay DRY.
 *
 * `columns`: Array<{ key, header, render?(row), cellClassName?, hideOnMobile?, primary?, mobileFullWidth? }>
 *   - render: optional cell renderer (defaults to row[key])
 *   - hideOnMobile: skip the card row line for this column
 *   - primary: render this column as the card title (no label prefix)
 *   - mobileFullWidth: on phones, render this column as a full-width
 *     block at the bottom of the card with no label prefix — meant for
 *     action buttons / CTAs so they remain a comfortable tap target.
 * `rows`: Array<{ id?, ...rowFields }>
 * `getRowKey`: optional fn(row, idx) → key (defaults to row.id || idx)
 * `emptyState`: optional React node shown when rows.length === 0
 *
 * Expandable rows (2026-05-19):
 *   - `isRowExpanded(row)`  → boolean. When true, an extra <tr> is
 *      rendered immediately under the main row in desktop mode with a
 *      single <td colSpan={columns.length}> so the expanded content
 *      spans the full table width instead of being trapped in one
 *      narrow column.
 *   - `renderExpanded(row)` → React node rendered inside that cell.
 *      On mobile (card mode) the same node is appended at the bottom
 *      of the card (which is already full-width) so the UX matches.
 */
export function ResponsiveTable({
  columns,
  rows,
  getRowKey,
  emptyState = null,
  className,
  cardClassName,
  rowClassName,
  ariaLabel,
  onRowClick,
  desktopMode = 'table',
  desktopGridClassName,
  isRowExpanded,
  renderExpanded,
}) {
  const safeRows = Array.isArray(rows) ? rows : [];
  const keyFor = (row, idx) => {
    if (typeof getRowKey === 'function') return getRowKey(row, idx);
    if (row && row.id != null) return row.id;
    return idx;
  };

  if (!safeRows.length && emptyState) return emptyState;

  const primaryCol = columns.find((c) => c.primary) || columns[0];

  if (desktopMode === 'grid') {
    return (
      <div className={cn('w-full', className)} data-testid="responsive-table">
        <div
          className={cn(
            'hidden sm:grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4',
            desktopGridClassName,
          )}
          role="list"
          aria-label={ariaLabel}
          data-testid="responsive-table-grid"
        >
          {safeRows.map((row, idx) => (
            <div
              key={keyFor(row, idx)}
              role="listitem"
              className={cn(onRowClick && 'cursor-pointer', rowClassName)}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
            >
              {primaryCol && (primaryCol.render ? primaryCol.render(row, idx) : row[primaryCol.key])}
            </div>
          ))}
        </div>
        <ul
          className="sm:hidden flex flex-col gap-2"
          data-testid="responsive-table-mobile"
        >
          {safeRows.map((row, idx) => (
            <li
              key={keyFor(row, idx)}
              className={cn(
                'rounded-lg border border-border/60 bg-white dark:bg-slate-900 p-3',
                onRowClick && 'cursor-pointer hover:bg-muted/30',
                cardClassName,
              )}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
            >
              {primaryCol && (primaryCol.render ? primaryCol.render(row, idx) : row[primaryCol.key])}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <div className={cn('w-full', className)} data-testid="responsive-table">
      {/* Desktop / tablet — real table */}
      <div className="hidden sm:block w-full overflow-x-auto">
        <table className="w-full text-sm" aria-label={ariaLabel}>
          <thead>
            <tr className="border-b">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={cn(
                    'h-10 px-2 text-start align-middle font-medium text-muted-foreground',
                    col.headerClassName,
                  )}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {safeRows.map((row, idx) => {
              const rowKey = keyFor(row, idx);
              const expanded = typeof isRowExpanded === 'function'
                ? !!isRowExpanded(row)
                : false;
              return (
                <React.Fragment key={rowKey}>
                  <tr
                    className={cn(
                      // Drop the bottom border when this row is
                      // followed by its own expansion <tr> so the two
                      // read as a single block instead of two stripes.
                      expanded ? 'hover:bg-muted/30' : 'border-b last:border-0 hover:bg-muted/30',
                      onRowClick && 'cursor-pointer',
                      rowClassName,
                    )}
                    onClick={onRowClick ? () => onRowClick(row) : undefined}
                  >
                    {columns.map((col) => (
                      <td
                        key={col.key}
                        className={cn('p-2 align-middle', col.cellClassName)}
                      >
                        {col.render ? col.render(row) : row[col.key]}
                      </td>
                    ))}
                  </tr>
                  {expanded && typeof renderExpanded === 'function' && (
                    <tr className="border-b last:border-0 bg-muted/20">
                      {/* Full-width expansion cell — colSpan equals
                         the column count so the details block spans
                         the entire table and isn't squeezed into a
                         single narrow column. */}
                      <td colSpan={columns.length} className="p-3 align-top">
                        {renderExpanded(row)}
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Mobile — stacked card per row */}
      <ul
        className="sm:hidden flex flex-col gap-2"
        data-testid="responsive-table-mobile"
      >
        {safeRows.map((row, idx) => {
          const visibleCols = columns.filter((c) => !c.hideOnMobile);
          const primaryCol = visibleCols.find((c) => c.primary);
          const rest = visibleCols.filter((c) => !c.primary);
          const expanded = typeof isRowExpanded === 'function'
            ? !!isRowExpanded(row)
            : false;
          return (
            <li
              key={keyFor(row, idx)}
              className={cn(
                'rounded-lg border border-border/60 bg-white dark:bg-slate-900 p-3 space-y-1.5',
                onRowClick && 'cursor-pointer hover:bg-muted/30',
                cardClassName,
              )}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
            >
              {primaryCol && (
                <div className="font-semibold text-sm text-foreground break-words min-w-0">
                  {primaryCol.render ? primaryCol.render(row) : row[primaryCol.key]}
                </div>
              )}
              {rest
                .filter((c) => !c.mobileFullWidth)
                .map((col) => (
                  <div
                    key={col.key}
                    className="flex items-baseline justify-between gap-3 text-xs min-w-0"
                  >
                    <span className="text-muted-foreground shrink-0">{col.header}</span>
                    <span className="text-foreground text-end break-words min-w-0">
                      {col.render ? col.render(row) : row[col.key]}
                    </span>
                  </div>
                ))}
              {rest
                .filter((c) => c.mobileFullWidth)
                .map((col) => (
                  // Action / CTA columns get a full-width block at the
                  // bottom of the card so buttons stay comfortably
                  // tappable (≥44px wide) at 360px.
                  <div key={col.key} className="pt-1 [&>*]:w-full">
                    {col.render ? col.render(row) : row[col.key]}
                  </div>
                ))}
              {expanded && typeof renderExpanded === 'function' && (
                <div className="pt-2 w-full">
                  {renderExpanded(row)}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default ResponsiveTable;
