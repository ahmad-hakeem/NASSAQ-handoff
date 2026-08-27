import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { ThemeProvider, useTheme, useTranslation } from '@/shared/contexts/ThemeContext';
import { AuthProvider } from '@/shared/contexts/AuthContext';
import { Header } from '@/shared/components/layout/Header';

const DashboardTestView = () => {
  const { language, isRTL, dir, toggleLanguage } = useTheme();
  const { t } = useTranslation();

  return (
    <div>
      <Header title={t('dashboard')} subtitle={t('usersClassesMgmt')} />
      <div data-testid="current-lang">{language}</div>
      <div data-testid="current-rtl">{String(isRTL)}</div>
      <div data-testid="current-dir">{dir}</div>
      <div data-testid="translated-title">{t('dashboard')}</div>
      <button data-testid="custom-toggle" onClick={toggleLanguage}>
        Change Lang
      </button>
    </div>
  );
};

describe('Language Toggle Responsiveness and State Reactivity', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.dir = 'rtl';
    document.documentElement.lang = 'ar';
  });

  test('header language button and custom toggle switch language back and forth smoothly', () => {
    render(
      <ThemeProvider>
        <AuthProvider>
          <DashboardTestView />
        </AuthProvider>
      </ThemeProvider>
    );

    // Initial Arabic state
    expect(screen.getByTestId('current-lang').textContent).toBe('ar');
    expect(screen.getByTestId('current-rtl').textContent).toBe('true');
    expect(screen.getByTestId('current-dir').textContent).toBe('rtl');
    expect(document.documentElement.dir).toBe('rtl');

    // Click 1: Toggle to English via Header language button
    const headerToggleBtn = screen.getByTestId('language-toggle-btn');
    act(() => {
      fireEvent.click(headerToggleBtn);
    });

    expect(screen.getByTestId('current-lang').textContent).toBe('en');
    expect(screen.getByTestId('current-rtl').textContent).toBe('false');
    expect(screen.getByTestId('current-dir').textContent).toBe('ltr');
    expect(document.documentElement.dir).toBe('ltr');
    expect(document.documentElement.getAttribute('data-language')).toBe('en');

    // Click 2: Toggle back to Arabic
    act(() => {
      fireEvent.click(headerToggleBtn);
    });

    expect(screen.getByTestId('current-lang').textContent).toBe('ar');
    expect(screen.getByTestId('current-rtl').textContent).toBe('true');
    expect(screen.getByTestId('current-dir').textContent).toBe('rtl');
    expect(document.documentElement.dir).toBe('rtl');
    expect(document.documentElement.getAttribute('data-language')).toBe('ar');

    // Click 3: Toggle to English via secondary button
    const customToggleBtn = screen.getByTestId('custom-toggle');
    act(() => {
      fireEvent.click(customToggleBtn);
    });

    expect(screen.getByTestId('current-lang').textContent).toBe('en');
    expect(screen.getByTestId('current-rtl').textContent).toBe('false');
    expect(screen.getByTestId('current-dir').textContent).toBe('ltr');
    expect(document.documentElement.dir).toBe('ltr');
  });

  test('multiple sequential rapid clicks do not lock or desynchronize state', () => {
    render(
      <ThemeProvider>
        <AuthProvider>
          <DashboardTestView />
        </AuthProvider>
      </ThemeProvider>
    );

    const toggleBtn = screen.getByTestId('language-toggle-btn');

    // Rapid toggle 4 times
    act(() => {
      fireEvent.click(toggleBtn); // en
      fireEvent.click(toggleBtn); // ar
      fireEvent.click(toggleBtn); // en
      fireEvent.click(toggleBtn); // ar
    });

    expect(screen.getByTestId('current-lang').textContent).toBe('ar');
    expect(document.documentElement.dir).toBe('rtl');

    // One more click to en
    act(() => {
      fireEvent.click(toggleBtn);
    });

    expect(screen.getByTestId('current-lang').textContent).toBe('en');
    expect(document.documentElement.dir).toBe('ltr');
  });
});
