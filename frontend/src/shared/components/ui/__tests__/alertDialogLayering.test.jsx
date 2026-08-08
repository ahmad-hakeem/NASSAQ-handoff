import React from 'react';
import { render } from '@testing-library/react';
import { Dialog, DialogContent, DialogTitle } from '../dialog';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogTitle,
} from '../alert-dialog';

/**
 * Regression guard for the Add-Teacher (and every other in-Dialog) freeze.
 *
 * The global NassaqAlertDialog is a Radix AlertDialog mounted at the app root.
 * When an error/confirm alert is raised from inside an open Radix Dialog (e.g.
 * the Add-Teacher wizard), the AlertDialog stacks ON TOP as the active modal
 * layer and disables pointer events on everything beneath it. If the alert's
 * z-index is LOWER than the Dialog's, the alert renders *behind* the wizard:
 * the wizard is visible but non-interactive, and the only clickable element
 * (the alert button) is hidden — a total UI freeze.
 *
 * The alert MUST therefore always stack above the Dialog scale.
 */
const zIndexOf = (el) => {
  const bracket = el.className.match(/z-\[(\d+)\]/);
  if (bracket) return parseInt(bracket[1], 10);
  const plain = el.className.match(/z-(\d+)\b/);
  if (plain) return parseInt(plain[1], 10);
  return null;
};

describe('Dialog / AlertDialog z-index layering', () => {
  it('renders the AlertDialog content above the Dialog content', () => {
    render(
      <Dialog open onOpenChange={() => {}}>
        <DialogContent>
          <DialogTitle>dialog</DialogTitle>
          dialog body
        </DialogContent>
      </Dialog>
    );
    render(
      <AlertDialog open onOpenChange={() => {}}>
        <AlertDialogContent>
          <AlertDialogTitle>alert</AlertDialogTitle>
          alert body
        </AlertDialogContent>
      </AlertDialog>
    );

    const dialogContent = document.querySelector('[role="dialog"]');
    const alertContent = document.querySelector('[role="alertdialog"]');

    expect(dialogContent).not.toBeNull();
    expect(alertContent).not.toBeNull();

    const dialogZ = zIndexOf(dialogContent);
    const alertZ = zIndexOf(alertContent);

    expect(dialogZ).not.toBeNull();
    expect(alertZ).not.toBeNull();
    expect(alertZ).toBeGreaterThan(dialogZ);
  });
});
