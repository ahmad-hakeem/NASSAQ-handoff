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
    render(<SessionCell session={baseSession} dayKey="monday" onClick={() => {}} />);
    const cell = screen.getByRole('button');
    expect(cell.className).toMatch(/--day-mon-tint/);
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
    expect(subject.className).toMatch(/text-\[10px\]/);
  });

  it('uses roomier typography when compact is false (daily view)', () => {
    render(
      <SessionCell session={baseSession} dayKey="monday" onClick={() => {}} compact={false} />,
    );
    const subject = screen.getByText('رياضيات');
    expect(subject.className).toMatch(/line-clamp-2/);
    expect(subject.className).toMatch(/text-xs/);
    const klass = screen.getByText('٣ علوم');
    expect(klass.className).toMatch(/line-clamp-2/);
  });
});
