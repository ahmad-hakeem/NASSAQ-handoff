import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import SessionCell from '../grid-theme/SessionCell';

const baseSession = {
  id: 's-1',
  subject_name: 'رياضيات',
  class_name: '٣ علوم',
  day_of_week: 'monday',
  slot_number: 3,
  start_time: '11:35',
  end_time: '12:15',
};

describe('SessionCell', () => {
  it('renders subject and class', () => {
    render(<SessionCell session={baseSession} dayKey="monday" onClick={() => {}} />);
    expect(screen.getByText('رياضيات')).toBeInTheDocument();
    expect(screen.getByText('٣ علوم')).toBeInTheDocument();
  });

  it('applies the monday tint class', () => {
    // Workspace redesign: the cell body is a white tile — the day tint
    // now lives on the top band + faint bottom "echo" strip inside it.
    render(<SessionCell session={baseSession} dayKey="monday" onClick={() => {}} />);
    const cell = screen.getByRole('button');
    expect(cell.querySelector('[class*="--day-mon-tint"]')).not.toBeNull();
    expect(cell.querySelector('[class*="--day-mon-band"]')).not.toBeNull();
  });

  it('calls onClick with the session when activated', () => {
    const onClick = jest.fn();
    render(<SessionCell session={baseSession} dayKey="monday" onClick={onClick} />);
    fireEvent.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledWith(baseSession);
  });

  it('opens on Enter key press', () => {
    const onClick = jest.fn();
    render(<SessionCell session={baseSession} dayKey="monday" onClick={onClick} />);
    fireEvent.keyDown(screen.getByRole('button'), { key: 'Enter' });
    expect(onClick).toHaveBeenCalled();
  });

  it('renders an accessible label including subject, class, day and period', () => {
    render(<SessionCell session={baseSession} dayKey="monday" onClick={() => {}} />);
    const cell = screen.getByRole('button');
    expect(cell.getAttribute('aria-label')).toMatch(/رياضيات/);
    expect(cell.getAttribute('aria-label')).toMatch(/٣ علوم/);
  });

  it('shows lock icon when isLocked is true', () => {
    render(<SessionCell session={baseSession} dayKey="monday" onClick={() => {}} isLocked />);
    expect(screen.getByTestId('session-cell-lock-icon')).toBeInTheDocument();
  });

  // ── Compact prop (Task #138) ─────────────────────────────────────────
  // الوضع الأسبوعي يبقى على السلوك السابق (compact = true): سطر واحد فقط
  // وحجم خط صغير. الوضع اليومي (compact = false) يستخدم سطرين بحجم أكبر
  // ليتنفّس النص في الأعمدة العريضة.
  it('uses compact (single-line) typography by default', () => {
    render(<SessionCell session={baseSession} dayKey="monday" onClick={() => {}} />);
    const subject = screen.getByText('رياضيات');
    expect(subject.className).toMatch(/line-clamp-1/);
    // Task #142 — weekly mode primary text must be >= 11px so operators
    // can read it at a glance without hovering.
    expect(subject.className).toMatch(/text-\[11px\]/);
    expect(subject.className).toMatch(/font-bold/);
  });

  it('uses roomier typography when compact is false (daily view)', () => {
    render(
      <SessionCell session={baseSession} dayKey="monday" onClick={() => {}} compact={false} />,
    );
    const subject = screen.getByText('رياضيات');
    expect(subject.className).toMatch(/line-clamp-2/);
    expect(subject.className).toMatch(/text-sm/);
    const klass = screen.getByText('٣ علوم');
    expect(klass.className).toMatch(/line-clamp-2/);
  });

  // ── Task #142 — visual hierarchy contract ────────────────────────────
  // Filled cells must surface three anchors in priority order:
  //   1. subject (boldest, biggest)
  //   2. class   (regular weight, ≥11px in weekly)
  //   3. meta    (period time / slot, smallest, dimmed)
  // These tests freeze that contract so future tweaks can't silently
  // collapse the hierarchy.
  it('renders the three-tier hierarchy: subject → class → meta', () => {
    render(<SessionCell session={baseSession} dayKey="monday" onClick={() => {}} />);
    const subject = screen.getByTestId('session-cell-subject');
    const klass = screen.getByTestId('session-cell-class');
    const meta = screen.getByTestId('session-cell-meta');
    expect(subject).toHaveTextContent('رياضيات');
    expect(klass).toHaveTextContent('٣ علوم');
    expect(meta).toHaveTextContent('11:35'); // start_time fallback
  });

  it('weekly typography is >= 11px for both subject and class lines', () => {
    render(<SessionCell session={baseSession} dayKey="monday" onClick={() => {}} />);
    const subject = screen.getByTestId('session-cell-subject');
    const klass = screen.getByTestId('session-cell-class');
    // Both primary anchors must be >= 11px in the dense weekly view.
    expect(subject.className).toMatch(/text-\[11px\]/);
    expect(klass.className).toMatch(/text-\[11px\]/);
    // Subject is heavier than class to enforce visual hierarchy.
    expect(subject.className).toMatch(/font-bold/);
    expect(klass.className).toMatch(/font-medium/);
  });

  it('falls back to slot number when start_time is missing', () => {
    const noTime = { ...baseSession, start_time: undefined };
    render(<SessionCell session={noTime} dayKey="monday" onClick={() => {}} />);
    expect(screen.getByTestId('session-cell-meta')).toHaveTextContent('#3');
  });
});
