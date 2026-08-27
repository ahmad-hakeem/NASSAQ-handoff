import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { Switch } from '../switch';

describe('Switch Component — RTL & LTR Layout and Alignment', () => {
  test('renders in RTL mode with correct direction and classes', () => {
    render(
      <div dir="rtl">
        <Switch data-testid="test-switch-rtl" checked={true} onCheckedChange={() => {}} />
      </div>
    );

    const switchEl = screen.getByTestId('test-switch-rtl');
    expect(switchEl).toHaveAttribute('data-state', 'checked');

    const thumb = switchEl.querySelector('span');
    expect(thumb).toBeInTheDocument();
    expect(thumb.className).toContain('data-[state=checked]:translate-x-4');
    expect(thumb.className).toContain('data-[state=unchecked]:translate-x-0');
  });

  test('renders in LTR mode with correct direction and classes', () => {
    render(
      <div dir="ltr">
        <Switch data-testid="test-switch-ltr" checked={false} onCheckedChange={() => {}} />
      </div>
    );

    const switchEl = screen.getByTestId('test-switch-ltr');
    expect(switchEl).toHaveAttribute('data-state', 'unchecked');

    const thumb = switchEl.querySelector('span');
    expect(thumb).toBeInTheDocument();
    expect(thumb.className).toContain('data-[state=unchecked]:translate-x-0');
  });

  test('triggers onCheckedChange callback upon click', () => {
    const handleCheckedChange = jest.fn();
    render(
      <div dir="rtl">
        <Switch data-testid="interactive-switch" checked={false} onCheckedChange={handleCheckedChange} />
      </div>
    );

    const switchEl = screen.getByTestId('interactive-switch');
    fireEvent.click(switchEl);
    expect(handleCheckedChange).toHaveBeenCalledWith(true);
  });
});
