import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTranslation, useTheme } from '../../contexts/ThemeContext';
import { toast } from 'sonner';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent } from '../../components/ui/card';
import { Avatar, AvatarFallback, AvatarImage } from '../../components/ui/avatar';
import { Button } from '../../components/ui/button';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import { ImageCropModal } from '../../components/ui/ImageCropModal';
import ContactInfoDialog from '../../components/parent/ContactInfoDialog';
import ProfileEditDialog from '../../components/parent/ProfileEditDialog';
import PasswordChangeDialog from '../../components/parent/PasswordChangeDialog';
import ActiveSessionsCard from '../../components/parent/ActiveSessionsCard';
import MfaSecuritySection from '../../components/mfa/MfaSecuritySection';
import {
  Settings as SettingsIcon, FileText, Shield, Globe, MessageCircle,
  GraduationCap, LogOut, ChevronLeft, ChevronRight, User, Camera,
  Mail, Phone, Lock, Trash2, Pencil,
} from 'lucide-react';

const Row = ({ icon: Icon, iconBg, iconColor, label, sublabel, onClick, trailing, danger, isRTL, testId }) => {
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
      <span className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${iconBg}`}>
        <Icon className={`h-4 w-4 ${iconColor}`} />
      </span>
      <span className="flex-1 min-w-0">
        <span className={`block text-sm font-cairo truncate ${danger ? 'text-red-600 dark:text-red-400 font-bold' : 'text-foreground'}`}>
          {label}
        </span>
        {sublabel && (
          <span className="block text-[11px] text-muted-foreground font-cairo truncate" dir={typeof sublabel === 'string' && /^[+\d]/.test(sublabel) ? 'ltr' : undefined}>
            {sublabel}
          </span>
        )}
      </span>
      {trailing}
      {onClick && (
        <Chevron className={`h-4 w-4 shrink-0 ${danger ? 'text-red-400 dark:text-red-500/70' : 'text-muted-foreground/60'}`} />
      )}
    </button>
  );
};

const SectionLabel = ({ children }) => (
  <p className="text-xs font-cairo text-muted-foreground/80 px-2 mb-2 mt-1">{children}</p>
);

const ParentSettingsPage = () => {
  const { t } = useTranslation();
  const { isRTL, language, setLanguage } = useTheme();
  const { user, logout, api, refreshUser } = useAuth();
  const navigate = useNavigate();
  const { nassaqConfirm, nassaqError } = useNassaqAlert();

  const [contactOpen, setContactOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [passwordOpen, setPasswordOpen] = useState(false);
  const [cropOpen, setCropOpen] = useState(false);
  const [avatarBusy, setAvatarBusy] = useState(false);

  const persistLanguage = (lang) => {
    api.put('/users/me/preferences', { language: lang }).catch(() => {});
  };

  const switchLanguage = (lang) => {
    if (lang === language) return;
    setLanguage?.(lang);
    persistLanguage(lang);
  };

  const handleAvatarSave = async (base64) => {
    setAvatarBusy(true);
    try {
      await api.post('/users/me/avatar', { image_data: base64 });
      window.dispatchEvent(new CustomEvent('user-updated', { detail: { avatar_url: base64 } }));
      await refreshUser?.();
      toast.success(t('profilePictureUpdated') || 'Profile picture updated');
    } catch (err) {
      nassaqError(err?.response?.data?.detail || (t('errorUploadingImage') || 'Error uploading image'));
      throw err;
    } finally {
      setAvatarBusy(false);
    }
  };

  const handleAvatarRemove = () => {
    if (!user?.avatar_url) return;
    nassaqConfirm(
      t('removeProfilePictureConfirm') || (isRTL ? 'هل تريد إزالة صورتك الشخصية؟' : 'Remove your profile picture?'),
      async () => {
        setAvatarBusy(true);
        try {
          await api.put('/users/me/profile', { avatar_url: '' });
          await refreshUser?.();
          toast.success(t('profilePictureRemoved') || 'Profile picture removed');
        } catch (err) {
          nassaqError(err?.response?.data?.detail || (t('errorRemovingImage') || 'Error removing image'));
        } finally {
          setAvatarBusy(false);
        }
      },
      {
        title: t('profilePicture') || 'Profile picture',
        type: 'warning',
        confirmText: t('remove') || 'Remove',
        cancelText: t('cancel') || 'Cancel',
      },
    );
  };

  const handleLoginAsTeacher = () => {
    nassaqConfirm(
      t('loginAsTeacherConfirm')
        || (isRTL ? 'تسجيل الخروج من حساب ولي الأمر والانتقال إلى صفحة تسجيل الدخول كمعلم؟'
                  : 'Sign out of the parent account and go to the login page to sign in as a teacher?'),
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
      t('logoutConfirm') || t('areYouSureLogout') || (isRTL ? 'هل أنت متأكد من تسجيل الخروج؟' : 'Are you sure you want to log out?'),
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

  const fullName = user?.full_name || (isRTL ? 'ولي أمر' : 'Parent');

  return (
    <PortalLayout portalType="parent">
      <div className="p-4 space-y-5 max-w-2xl mx-auto" data-testid="parent-settings-page">
        <div className="flex items-center gap-2 mb-1">
          <SettingsIcon className="h-6 w-6 text-brand-navy dark:text-brand-turquoise" />
          <h1 className="text-xl font-bold font-cairo text-foreground">{t('settings')}</h1>
        </div>

        {/* Profile header card */}
        <Card className="rounded-2xl border-0 shadow-sm bg-card overflow-hidden">
          <CardContent className="p-4">
            <div className="flex items-center gap-4">
              <div className="relative">
                <Avatar className="h-16 w-16 ring-2 ring-brand-turquoise/20">
                  <AvatarImage src={user?.avatar_url} />
                  <AvatarFallback className="bg-brand-turquoise/15 text-brand-turquoise text-xl font-bold font-cairo">
                    {fullName.charAt(0)}
                  </AvatarFallback>
                </Avatar>
                <button
                  type="button"
                  onClick={() => setCropOpen(true)}
                  disabled={avatarBusy}
                  aria-label={t('uploadPhoto') || 'Upload photo'}
                  className="absolute -bottom-1 -end-1 z-10 w-7 h-7 rounded-full bg-brand-turquoise text-white flex items-center justify-center shadow-md hover:scale-110 transition-transform disabled:opacity-60"
                  data-testid="parent-avatar-upload-btn"
                >
                  <Camera className="h-3.5 w-3.5" />
                </button>
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-base font-bold font-cairo text-foreground truncate">{fullName}</p>
                {user?.email && (
                  <p className="text-xs text-muted-foreground truncate" dir="ltr">{user.email}</p>
                )}
                {user?.phone && (
                  <p className="text-xs text-muted-foreground truncate" dir="ltr">{user.phone}</p>
                )}
              </div>
              <div className="flex flex-col gap-1.5 shrink-0">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setProfileOpen(true)}
                  className="h-8 text-xs"
                  data-testid="parent-edit-profile-btn"
                >
                  <Pencil className="h-3.5 w-3.5 me-1.5" />
                  {t('editProfile') || 'Edit'}
                </Button>
                {user?.avatar_url && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={handleAvatarRemove}
                    disabled={avatarBusy}
                    className="h-8 text-xs text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-950/30"
                    data-testid="parent-avatar-remove-btn"
                  >
                    <Trash2 className="h-3.5 w-3.5 me-1.5" />
                    {t('remove') || 'Remove'}
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Account / Profile group */}
        <div>
          <SectionLabel>{t('profile3') || t('profile') || 'Profile'}</SectionLabel>
          <Card className="rounded-2xl border-0 shadow-sm bg-card overflow-hidden">
            <CardContent className="p-0 divide-y divide-border/60">
              <Row
                icon={User}
                iconBg="bg-brand-turquoise/10"
                iconColor="text-brand-turquoise"
                label={t('personalInformation') || 'Personal information'}
                sublabel={fullName}
                onClick={() => setProfileOpen(true)}
                isRTL={isRTL}
                testId="settings-row-personal-info"
              />
              {user?.email && (
                <Row
                  icon={Mail}
                  iconBg="bg-blue-50 dark:bg-blue-900/30"
                  iconColor="text-blue-600 dark:text-blue-400"
                  label={t('email') || t('email2') || 'Email'}
                  sublabel={user.email}
                  onClick={() => setProfileOpen(true)}
                  isRTL={isRTL}
                  testId="settings-row-email"
                />
              )}
              {user?.phone && (
                <Row
                  icon={Phone}
                  iconBg="bg-emerald-50 dark:bg-emerald-900/30"
                  iconColor="text-emerald-600 dark:text-emerald-400"
                  label={t('phoneNumber') || 'Phone number'}
                  sublabel={user.phone}
                  onClick={() => setProfileOpen(true)}
                  isRTL={isRTL}
                  testId="settings-row-phone"
                />
              )}
            </CardContent>
          </Card>
        </div>

        {/* Security group */}
        <div>
          <SectionLabel>{t('security') || 'Security'}</SectionLabel>
          <Card className="rounded-2xl border-0 shadow-sm bg-card overflow-hidden mb-3">
            <CardContent className="p-0 divide-y divide-border/60">
              <Row
                icon={Lock}
                iconBg="bg-amber-50 dark:bg-amber-900/30"
                iconColor="text-amber-600 dark:text-amber-400"
                label={t('changePassword') || 'Change password'}
                sublabel={t('changeYourAccountPassword2') || (isRTL ? 'تحديث كلمة مرور الحساب' : 'Update your account password')}
                onClick={() => setPasswordOpen(true)}
                isRTL={isRTL}
                testId="settings-row-password"
              />
            </CardContent>
          </Card>
          <div className="mb-3">
            <MfaSecuritySection />
          </div>
          <ActiveSessionsCard />
        </div>

        {/* Preferences / Legal / Contact group */}
        <div>
          <SectionLabel>{t('general') || 'General'}</SectionLabel>
          <Card className="rounded-2xl border-0 shadow-sm bg-card overflow-hidden">
            <CardContent className="p-0 divide-y divide-border/60">
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
                icon={FileText}
                iconBg="bg-amber-50 dark:bg-amber-900/30"
                iconColor="text-amber-600 dark:text-amber-400"
                label={t('termsAndConditions') || t('termsConditions') || 'Terms & Conditions'}
                onClick={() => navigate('/terms')}
                isRTL={isRTL}
                testId="settings-row-terms"
              />
              <Row
                icon={Shield}
                iconBg="bg-blue-50 dark:bg-blue-900/30"
                iconColor="text-blue-600 dark:text-blue-400"
                label={t('privacyPolicy') || 'Privacy Policy'}
                onClick={() => navigate('/privacy')}
                isRTL={isRTL}
                testId="settings-row-privacy"
              />
              <Row
                icon={MessageCircle}
                iconBg="bg-violet-50 dark:bg-violet-900/30"
                iconColor="text-violet-600 dark:text-violet-400"
                label={t('contactUs') || 'Contact Us'}
                onClick={() => setContactOpen(true)}
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

      <ContactInfoDialog open={contactOpen} onOpenChange={setContactOpen} />
      <ProfileEditDialog open={profileOpen} onOpenChange={setProfileOpen} />
      <PasswordChangeDialog open={passwordOpen} onOpenChange={setPasswordOpen} />
      <ImageCropModal
        open={cropOpen}
        onOpenChange={setCropOpen}
        onSave={handleAvatarSave}
        isRTL={isRTL}
      />
    </PortalLayout>
  );
};

export default ParentSettingsPage;
