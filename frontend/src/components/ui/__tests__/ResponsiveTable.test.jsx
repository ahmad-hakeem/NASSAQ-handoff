/**
 * Task #274 — pin the table → cards adaptor contract.
 *
 * Below 640px: rows render as stacked cards (label → value pairs).
 * At 640px+: rows render inside a real `<table>` element.
 * Both modes share the same columns + rows props.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { ResponsiveTable } from '../ResponsiveTable';

const columns = [
  { key: 'name', header: 'Name', primary: true },
  { key: 'role', header: 'Role' },
  { key: 'when', header: 'When', render: (r) => `@${r.when}` },
];
const rows = [
  { id: 'r1', name: 'Nour', role: 'Parent', when: '2026-05-13' },
  { id: 'r2', name: 'Sami', role: 'Teacher', when: '2026-05-12' },
];

test('renders both table and mobile-card markup, sharing the same data', () => {
  render(<ResponsiveTable columns={columns} rows={rows} ariaLabel="people" />);
  // Real table is in the tree (Tailwind hides it visually below sm).
  expect(screen.getByRole('table', { name: 'people' })).toBeInTheDocument();
  // Mobile stacked-card list is also present so the responsive switch is
  // pure CSS (Tailwind sm: utilities) — no JS measurement needed.
  expect(screen.getByTestId('responsive-table-mobile')).toBeInTheDocument();
  // Each row appears in both modes.
  expect(screen.getAllByText('Nour').length).toBeGreaterThanOrEqual(2);
  expect(screen.getAllByText('@2026-05-13').length).toBeGreaterThanOrEqual(2);
});

test('mobile cards render label→value pairs for non-primary columns', () => {
  render(<ResponsiveTable columns={columns} rows={rows} />);
  const mobile = screen.getByTestId('responsive-table-mobile');
  // The "Role" header is rendered as the label inside each mobile card.
  const roleLabels = mobile.querySelectorAll('span');
  const labels = Array.from(roleLabels).map((s) => s.textContent);
  expect(labels).toContain('Role');
  expect(labels).toContain('When');
});

test('renders the empty-state node when no rows are provided', () => {
  render(
    <ResponsiveTable
      columns={columns}
      rows={[]}
      emptyState={<div data-testid="empty">none</div>}
    />,
  );
  expect(screen.getByTestId('empty')).toBeInTheDocument();
  expect(screen.queryByTestId('responsive-table')).toBeNull();
});

test('hideOnMobile columns are dropped from the mobile card view only', () => {
  const cols = [
    ...columns,
    { key: 'meta', header: 'Meta', hideOnMobile: true, render: () => 'META-VAL' },
  ];
  render(<ResponsiveTable columns={cols} rows={rows} />);
  // Meta still appears in the desktop table cells.
  const desktop = screen.getByRole('table');
  expect(desktop.textContent).toContain('META-VAL');
  // But not inside the mobile cards.
  const mobile = screen.getByTestId('responsive-table-mobile');
  expect(mobile.textContent).not.toContain('META-VAL');
});
