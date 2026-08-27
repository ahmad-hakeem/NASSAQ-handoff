import React from 'react';
import { render, screen, act } from '@testing-library/react';
import { ThemeProvider, useTheme, useTranslation } from '@/shared/contexts/ThemeContext';
import { AuthProvider, useAuth } from '@/shared/contexts/AuthContext';

const TestComponent = () => {
  const { language, isRTL, dir, toggleLanguage, setLanguage } = useTheme();
  const { t } = useTranslation();
  const { isRTL: authIsRTL, preferredLanguage } = useAuth();

  return (
    <div>
      <span data-testid="lang">{language}</span>
      <span data-testid="isRTL">{String(isRTL)}</span>
      <span data-testid="dir">{dir}</span>
      <span data-testid="authIsRTL">{String(authIsRTL)}</span>
      <span data-testid="preferredLang">{preferredLanguage}</span>
      <span data-testid="welcome">{t('welcomeTeacher', { 0: 'Ahmad' })}</span>
      <button data-testid="toggle-btn" onClick={toggleLanguage}>Toggle</button>
      <button data-testid="set-en-btn" onClick={() => setLanguage('en')}>Set EN</button>
      <button data-testid="set-ar-btn" onClick={() => setLanguage('ar')}>Set AR</button>
    </div>
  );
};

describe('Language and Direction Synchronization', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  test('defaults to Arabic RTL and syncs both ThemeContext and AuthContext', () => {
    render(
      <ThemeProvider>
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      </ThemeProvider>
    );

    expect(screen.getByTestId('lang').textContent).toBe('ar');
    expect(screen.getByTestId('isRTL').textContent).toBe('true');
    expect(screen.getByTestId('dir').textContent).toBe('rtl');
    expect(screen.getByTestId('authIsRTL').textContent).toBe('true');
    expect(screen.getByTestId('preferredLang').textContent).toBe('ar');
    expect(document.documentElement.dir).toBe('rtl');
  });

  test('toggling language switches to English LTR across ThemeContext and AuthContext', () => {
    render(
      <ThemeProvider>
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      </ThemeProvider>
    );

    act(() => {
      screen.getByTestId('toggle-btn').click();
    });

    expect(screen.getByTestId('lang').textContent).toBe('en');
    expect(screen.getByTestId('isRTL').textContent).toBe('false');
    expect(screen.getByTestId('dir').textContent).toBe('ltr');
    expect(screen.getByTestId('authIsRTL').textContent).toBe('false');
    expect(screen.getByTestId('preferredLang').textContent).toBe('en');
    expect(document.documentElement.dir).toBe('ltr');
    expect(screen.getByTestId('welcome').textContent).toContain('Welcome, Ahmad');
  });

  test('setting language via custom event syncs state immediately', () => {
    render(
      <ThemeProvider>
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      </ThemeProvider>
    );

    act(() => {
      window.dispatchEvent(new CustomEvent('nassaq-language-sync', { detail: { language: 'en' } }));
    });

    expect(screen.getByTestId('lang').textContent).toBe('en');
    expect(screen.getByTestId('isRTL').textContent).toBe('false');
    expect(screen.getByTestId('dir').textContent).toBe('ltr');
    expect(screen.getByTestId('authIsRTL').textContent).toBe('false');
    expect(document.documentElement.dir).toBe('ltr');
  });
});
