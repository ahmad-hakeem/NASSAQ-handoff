import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from '@/shared/contexts/ThemeContext';
import SessionDetailModal from '../grid-theme/SessionDetailModal';

const renderModal = (ui) => render(<ThemeProvider>{ui}</ThemeProvider>);

const session = {
  id: 's-1',
  subject_name: 'رياضيات',
  class_name: '٣ علوم',
  teacher_name: 'أحمد المعلم',
  teacher_avatar_url: null,
  teacher_specialty: 'تخصص الرياضيات',
  room: 'قاعة ٢٠٤',
  day_of_week: 'sunday',
  slot_number: 3,
  start_time: '11:35',
  end_time: '12:15',
  is_locked: false,
};

describe('SessionDetailModal', () => {
  it('renders nothing when closed', () => {
    const { container } = renderModal(
      <SessionDetailModal open={false} session={session} onClose={() => {}} />
    );
    expect(container.querySelector('[data-testid="session-detail-modal"]')).toBeNull();
  });

  it('renders subject, class, teacher, room and time when open', () => {
    renderModal(<SessionDetailModal open session={session} onClose={() => {}} />);
    expect(screen.getByText('رياضيات')).toBeInTheDocument();
    expect(screen.getByText('٣ علوم')).toBeInTheDocument();
    expect(screen.getByText('أحمد المعلم')).toBeInTheDocument();
    expect(screen.getByText(/قاعة ٢٠٤/)).toBeInTheDocument();
    expect(screen.getByText(/11:35/)).toBeInTheDocument();
  });

  it('calls onClose when X button is clicked', () => {
    const onClose = jest.fn();
    renderModal(<SessionDetailModal open session={session} onClose={onClose} />);
    fireEvent.click(screen.getByTestId('session-detail-close'));
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose on Escape key', () => {
    const onClose = jest.fn();
    renderModal(<SessionDetailModal open session={session} onClose={onClose} />);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('calls onClose when backdrop is clicked', () => {
    const onClose = jest.fn();
    renderModal(<SessionDetailModal open session={session} onClose={onClose} />);
    fireEvent.click(screen.getByTestId('session-detail-backdrop'));
    expect(onClose).toHaveBeenCalled();
  });

  it('invokes onEdit, onMove, onLockToggle from quick actions', () => {
    const onEdit = jest.fn();
    const onMove = jest.fn();
    const onLockToggle = jest.fn();
    renderModal(
      <SessionDetailModal
        open
        session={session}
        onClose={() => {}}
        onEdit={onEdit}
        onMove={onMove}
        onLockToggle={onLockToggle}
      />
    );
    fireEvent.click(screen.getByTestId('session-action-edit'));
    fireEvent.click(screen.getByTestId('session-action-move'));
    fireEvent.click(screen.getByTestId('session-action-lock'));
    expect(onEdit).toHaveBeenCalledWith(session);
    expect(onMove).toHaveBeenCalledWith(session);
    expect(onLockToggle).toHaveBeenCalledWith(session);
  });

  it('hides quick action footer when hideActions is true', () => {
    renderModal(<SessionDetailModal open session={session} onClose={() => {}} hideActions />);
    expect(screen.queryByTestId('session-action-edit')).toBeNull();
    expect(screen.queryByTestId('session-action-move')).toBeNull();
    expect(screen.queryByTestId('session-action-lock')).toBeNull();
  });
});
