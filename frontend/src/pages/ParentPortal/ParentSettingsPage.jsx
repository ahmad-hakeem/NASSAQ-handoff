import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTranslation, useTheme } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent } from '../../components/ui/card';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  Settings as SettingsIcon, FileText, Shield, Globe, MessageCircle,
  GraduationCap, LogOut, ChevronLeft, ChevronRight,
} from 'lucide-react';

const Row = ({ icon: Icon, iconBg, iconColor, label, onClick, trailing, danger, isRTL, testId }) => {
  const Chevron = isRTL ? ChevronLeft : ChevronRight;
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testId}
      className={`w-full flex items-center gap-3 px-4 py-3 transition-colors text-start
        ${danger
          ? 'hover:bg-red-50/70 dark:hover:bg-red-950/30'
          : 'hover:bg-muted/50 dark:hover:bg-muted/30'}`}
    >
      <span
        className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${iconBg}`}
      >
        <Icon className={`h-4 w-4 ${iconColor}`} />
      </span>
      <span className={`flex-1 text-sm font-cairo truncate ${danger ? 'text-red-600 dark:text-red-400 font-bold' : 'text-foreground'}`}>
        {label}
      </span>
      {trailing}
      <Chevron className={`h-4 w-4 shrink-0 ${danger ? 'text-red-400 dark:text-red-500/70' : 'text-muted-foreground/60'}`} />
    </button>
  );
};

const SectionLabel = ({ children }) => (
  <p className="text-xs font-cairo text-muted-foreground/80 px-2 mb-2 mt-1">{children}</p>
);

const ParentSettingsPage = () => {
  const { t } = useTranslation();
  const { isRTL, language, setLanguage } = useTheme();
  const { logout, api } = useAuth();
  const navigate = useNavigate();
  const { nassaqConfirm } = useNassaqAlert();

  // Persist language choice to backend silently when possible; never block UI.
  const persistLanguage = (lang) => {
    api.put('/users/me/preferences', { language: lang }).catch(() => {});
  };

  const switchLanguage = (lang) => {
    if (lang === language) return;
    setLanguage?.(lang);
    persistLanguage(lang);
  };

  // Safe account-switch entry point: full logout then return to fresh login.
  const handleLoginAsTeacher = () => {
    nassaqConfirm(
      t('loginAsTeacherConfirm')
        || 'Sign out of the parent account and go to the login page to sign in as a teacher?',
      () => {
        logout();
        navigate('/login?role=teacher', { replace: true });
      },
      {
        title: t('loginAsTeacher') || 'Login as Teacher',
        confirmText: t('continue') || t('confirm') || 'Continue',
        cancelText: t('cancel') || 'Cancel',
      }
    );
  };

  const handleLogout = () => {
    nassaqConfirm(
      t('logoutConfirm') || t('areYouSureLogout') || 'Are you sure you want to log out?',
      () => {
        logout();
        navigate('/login', { replace: true });
      },
      {
        title: t('logout'),
        type: 'warning',
        confirmText: t('logout'),
        cancelText: t('cancel') || 'Cancel',
      }
    );
  };

  const langPill = (
    <div className="flex items-center gap-1 rounded-lg bg-muted/40 dark:bg-muted/30 p-0.5">
      {[
        { value: 'ar', label: 'ع' },
        { value: 'en', label: 'EN' },
      ].map((opt) => {
        const active = language === opt.value;
        return (
          <span
            key={opt.value}
            onClick={(e) => { e.stopPropagation(); switchLanguage(opt.value); }}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                e.stopPropagation();
                switchLanguage(opt.value);
              }
            }}
            className={`px-2 py-0.5 text-[11px] font-bold rounded-md transition-colors cursor-pointer ${
              active
                ? 'bg-brand-navy text-white dark:bg-brand-turquoise dark:text-brand-navy shadow-sm'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {opt.label}
          </span>
        );
      })}
    </div>
  );

  return (
    <PortalLayout portalType="parent">
      <div className="p-4 space-y-5 max-w-2xl mx-auto" data-testid="parent-settings-page">
        <div className="flex items-center gap-2 mb-1">
          <SettingsIcon className="h-6 w-6 text-brand-navy dark:text-brand-turquoise" />
          <h1 className="text-xl font-bold font-cairo text-foreground">{t('settings')}</h1>
        </div>

        {/* General group */}
        <div>
          <SectionLabel>{t('general') || 'General'}</SectionLabel>
          <Card className="rounded-2xl border-0 shadow-sm bg-card overflow-hidden">
            <CardContent className="p-0 divide-y divide-border/60">
              <Row
                icon={FileText}
                iconBg="bg-amber-50 dark:bg-amber-900/30"
                iconColor="text-amber-600 dark:text-amber-400"
                label={t('termsAndConditions') || t('termsConditions') || 'Terms & Conditions'}
                onClick={() => navigate('/parent/legal/terms')}
                isRTL={isRTL}
                testId="settings-row-terms"
              />
              <Row
                icon={Shield}
                iconBg="bg-blue-50 dark:bg-blue-900/30"
                iconColor="text-blue-600 dark:text-blue-400"
                label={t('privacyPolicy') || 'Privacy Policy'}
                onClick={() => navigate('/parent/legal/privacy')}
                isRTL={isRTL}
                testId="settings-row-privacy"
              />
              <Row
                icon={Globe}
                iconBg="bg-emerald-50 dark:bg-emerald-900/30"
                iconColor="text-emerald-600 dark:text-emerald-400"
                label={t('language') || 'Language'}
                onClick={() => switchLanguage(language === 'ar' ? 'en' : 'ar')}
                trailing={langPill}
                isRTL={isRTL}
                testId="settings-row-language"
              />
              <Row
                icon={MessageCircle}
                iconBg="bg-violet-50 dark:bg-violet-900/30"
                iconColor="text-violet-600 dark:text-violet-400"
                label={t('contactUs') || 'Contact Us'}
                onClick={() => navigate('/parent/communication')}
                isRTL={isRTL}
                testId="settings-row-contact"
              />
            </CardContent>
          </Card>
        </div>

        {/* Account switching group */}
        <div>
          <SectionLabel>{t('accountSwitching') || t('account') || 'Account'}</SectionLabel>
          <Card className="rounded-2xl border-0 shadow-sm bg-card overflow-hidden">
            <CardContent className="p-0 divide-y divide-border/60">
              <Row
                icon={GraduationCap}
                iconBg="bg-emerald-50 dark:bg-emerald-900/30"
                iconColor="text-emerald-600 dark:text-emerald-400"
                label={t('loginAsTeacher') || 'Login as Teacher'}
                onClick={handleLoginAsTeacher}
                isRTL={isRTL}
                testId="settings-row-login-teacher"
              />
              <Row
                icon={LogOut}
                iconBg="bg-red-50 dark:bg-red-900/30"
                iconColor="text-red-600 dark:text-red-400"
                label={t('logout')}
                onClick={handleLogout}
                isRTL={isRTL}
                danger
                testId="settings-row-logout"
              />
            </CardContent>
          </Card>
        </div>
      </div>
    </PortalLayout>
  );
};

export default ParentSettingsPage;
