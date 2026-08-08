/**
 * Regression guard for the shared modal close-button (X) positioning standard.
 *
 * Why this test exists
 * --------------------
 * The platform is Arabic-first (RTL). The shared Radix Dialog/Sheet close
 * buttons originally used PHYSICAL positioning (`absolute right-4 top-4`),
 * which kept the X at the top-right corner in RTL — directly on top of the
 * right-aligned Arabic title and header icons (e.g. the "إعدادات الحصة"
 * settings modal). The fix switched to LOGICAL positioning (`end-4`,
 * Tailwind `inset-inline-end`) so the X sits in the trailing corner:
 * top-right in LTR, top-left in RTL — clear of the title.
 *
 * This test locks in that standard so a future edit cannot silently revert
 * the close button back to physical `right-*` / `left-*` positioning, and so
 * the shared headers keep reserving safe space (`pe-*`) for the X.
 */
import React from 'react';
import { render, screen, within } from '@testing-library/react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/shared/components/ui/sheet';
import { AlertDialogHeader } from '@/shared/components/ui/alert-dialog';
import { DrawerHeader } from '@/shared/components/ui/drawer';

const getCloseButton = () =>
  screen.getByRole('button', { name: /close/i });

describe('shared modal close button positioning standard', () => {
  test('Dialog close button uses logical end positioning, not physical right/left', () => {
    render(
      <Dialog open>
        <DialogContent dir="rtl">
          <DialogHeader>
            <DialogTitle>إعدادات الحصة</DialogTitle>
          </DialogHeader>
        </DialogContent>
      </Dialog>
    );

    const close = getCloseButton();
    expect(close.className).toMatch(/\bend-4\b/);
    expect(close.className).not.toMatch(/\bright-4\b/);
    expect(close.className).not.toMatch(/\bleft-4\b/);
    // A real tap target + stacking so it never sits under header content.
    expect(close.className).toMatch(/\bz-10\b/);
  });

  test('Sheet close button uses logical end positioning, not physical right/left', () => {
    render(
      <Sheet open>
        <SheetContent dir="rtl">
          <SheetHeader>
            <SheetTitle>الإعدادات</SheetTitle>
          </SheetHeader>
        </SheetContent>
      </Sheet>
    );

    const close = getCloseButton();
    expect(close.className).toMatch(/\bend-4\b/);
    expect(close.className).not.toMatch(/\bright-4\b/);
    expect(close.className).not.toMatch(/\bleft-4\b/);
    expect(close.className).toMatch(/\bz-10\b/);
  });

  test('shared headers reserve trailing safe space for the close button', () => {
    const { rerender } = render(
      <Dialog open>
        <DialogContent dir="rtl">
          <DialogHeader data-testid="dialog-header">
            <DialogTitle>عنوان</DialogTitle>
          </DialogHeader>
        </DialogContent>
      </Dialog>
    );
    expect(screen.getByTestId('dialog-header').className).toMatch(/\bpe-10\b/);

    rerender(
      <Sheet open>
        <SheetContent dir="rtl">
          <SheetHeader data-testid="sheet-header">
            <SheetTitle>عنوان</SheetTitle>
          </SheetHeader>
        </SheetContent>
      </Sheet>
    );
    expect(screen.getByTestId('sheet-header').className).toMatch(/\bpe-10\b/);
  });
});

describe('shared modal headers use logical (direction-aware) title alignment', () => {
  /*
   * Arabic-first app: shared headers must align titles to the logical START
   * (right in RTL, left in LTR). They previously hardcoded physical
   * `sm:text-left`, which forced Arabic titles to the LEFT on desktop — the
   * same side as the trailing-corner close button — so the title collided with
   * the X (e.g. the "ملف الطالب" student-profile dialog). Logical `sm:text-start`
   * keeps the title opposite the close button in both directions.
   */
  test.each([
    ['DialogHeader', DialogHeader],
    ['SheetHeader', SheetHeader],
    ['AlertDialogHeader', AlertDialogHeader],
    ['DrawerHeader', DrawerHeader],
  ])('%s aligns to logical start on sm+, not physical left/right', (_name, Header) => {
    render(<Header data-testid="hdr" />);
    const cls = screen.getByTestId('hdr').className;
    expect(cls).toMatch(/\bsm:text-start\b/);
    expect(cls).not.toMatch(/\bsm:text-left\b/);
    expect(cls).not.toMatch(/\bsm:text-right\b/);
  });
});
