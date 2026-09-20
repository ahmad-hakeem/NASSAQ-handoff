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
});