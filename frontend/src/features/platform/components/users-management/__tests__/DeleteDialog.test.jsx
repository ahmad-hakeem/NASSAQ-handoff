import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { DeleteDialog } from '../UsersDialogs';

jest.mock('lucide-react', () => new Proxy({}, { get: () => () => null }));

jest.mock('@/shared/components/ui/button', () => ({
  Button: ({ children, ...props }) => <button {...props}>{children}</button>,
}));

jest.mock('@/shared/components/ui/dialog', () => ({
  Dialog: ({ open, children }) => (open ? <div>{children}</div> : null),
  DialogContent: ({ children }) => <div>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <h2>{children}</h2>,
  DialogDescription: ({ children }) => <div>{children}</div>,
  DialogFooter: ({ children }) => <div>{children}</div>,
}));

describe('DeleteDialog', () => {
  it('explains permanent teacher removal, released identity, retained history, and shared-account review', () => {
    render(
      <DeleteDialog
        user={{ id: 'teacher-1', role: 'teacher', full_name: 'Teacher One' }}
        onClose={jest.fn()}
        onConfirm={jest.fn()}
      />
    );

    expect(screen.getByText('حذف حساب المعلم نهائياً')).toBeInTheDocument();
    expect(screen.getByText(/تحرير البريد الإلكتروني ورقم الهاتف والهوية/)).toBeInTheDocument();
    expect(screen.getByText(/السجلات التعليمية والتاريخية السابقة محفوظة/)).toBeInTheDocument();
    expect(screen.getByText(/ارتباطات مشتركة أو غير مؤكدة/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /حذف المعلم نهائياً/ })).toBeInTheDocument();
  });

  it('keeps archival wording for non-teacher roles', () => {
    render(
      <DeleteDialog
        user={{ id: 'admin-1', role: 'school_principal', full_name: 'Principal One' }}
        onClose={jest.fn()}
        onConfirm={jest.fn()}
      />
    );

    expect(screen.getByText(/سيتم نقل الحساب إلى الأرشيف ولن يتم حذفه نهائياً/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /أرشفة الحساب/ })).toBeInTheDocument();
    expect(screen.queryByText(/تحرير البريد الإلكتروني/)).not.toBeInTheDocument();
  });

  it('disables confirmation while deletion is pending', () => {
    const onConfirm = jest.fn();
    render(
      <DeleteDialog
        user={{ id: 'teacher-1', role: 'teacher', full_name: 'Teacher One' }}
        onClose={jest.fn()}
        onConfirm={onConfirm}
        isDeleting
      />
    );

    const confirm = screen.getByRole('button', { name: /جارٍ الحذف/ });
    expect(confirm).toBeDisabled();
    fireEvent.click(confirm);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it('renders structured dependency blockers without rendering unknown fields', () => {
    render(
      <DeleteDialog
        user={{ id: 'teacher-1', role: 'teacher', full_name: 'Teacher One' }}
        onClose={jest.fn()}
        onConfirm={jest.fn()}
        deletionError={{
          status: 409,
          code: 'DELETE_DEPENDENCY_BLOCKED',
          message: 'تعذر حذف الحساب لوجود ارتباطات تحتاج إلى مراجعة.',
          dependencies: [{
            reason: 'account_ownership_mismatch',
            reasonLabel: 'بيانات ملكية ملف المعلم والحساب غير متطابقة.',
            category: 'dependency',
            table: 'users',
            count: 2,
            resolution: 'راجع ملكية الحساب ثم أعد المحاولة.',
            resolutionLabel: 'اطلب من مسؤول المنصة مراجعة روابط ملكية الحساب وإصلاحها، ثم أعد المحاولة.',
            email: 'must-not-render@example.com',
          }],
        }}
      />
    );

    expect(screen.getByRole('alert')).toHaveTextContent('تعذر حذف الحساب');
    expect(screen.getByRole('alert')).toHaveTextContent('DELETE_DEPENDENCY_BLOCKED');
    expect(screen.getByText(/بيانات ملكية ملف المعلم والحساب غير متطابقة/)).toBeInTheDocument();
    expect(screen.getByText(/account_ownership_mismatch/)).toBeInTheDocument();
    expect(screen.getByText(/dependency/)).toBeInTheDocument();
    expect(screen.getByText(/users/)).toBeInTheDocument();
    expect(screen.getByText(/2/)).toBeInTheDocument();
    expect(screen.getByText(/مراجعة روابط ملكية الحساب وإصلاحها/)).toBeInTheDocument();
    expect(screen.queryByText(/must-not-render@example.com/)).not.toBeInTheDocument();
  });

  it('falls back to the raw reason and resolution for an unknown blocker', () => {
    render(
      <DeleteDialog
        user={{ id: 'teacher-1', role: 'teacher', full_name: 'Teacher One' }}
        onClose={jest.fn()}
        onConfirm={jest.fn()}
        deletionError={{
          status: 409,
          message: 'Blocked',
          dependencies: [{
            reason: 'future_unknown_guard',
            resolution: 'Follow the backend guidance.',
          }],
        }}
      />
    );

    expect(screen.getByText('future_unknown_guard')).toBeInTheDocument();
    expect(screen.getByText('Follow the backend guidance.')).toBeInTheDocument();
  });

  it.each([
    [403, 'لا تملك صلاحية حذف هذا الحساب'],
    [500, 'تعذر إكمال حذف الحساب'],
  ])('renders a persistent status-specific error for HTTP %s', (status, message) => {
    render(
      <DeleteDialog
        user={{ id: 'teacher-1', role: 'teacher', full_name: 'Teacher One' }}
        onClose={jest.fn()}
        onConfirm={jest.fn()}
        deletionError={{ status, message, dependencies: [] }}
      />
    );

    expect(screen.getByRole('alert')).toHaveTextContent(message);
  });
});