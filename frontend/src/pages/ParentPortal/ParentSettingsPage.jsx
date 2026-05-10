import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTranslation } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Skeleton } from '../../components/ui/skeleton';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  Settings, Bell, Globe, Mail, MessageCircle, Shield,
} from 'lucide-react';

// Brand-aware toggle that reads correctly in both themes.
// On  → brand-navy (light) / brand-turquoise (dark, for contrast on dark surfaces).
// Off → neutral semantic surface that does not blend with rows in dark mode.
const Toggle = ({ checked, onChange, ariaLabel }) => (
  <button
    type="button"
    role="switch"
    aria-checked={checked}
    aria-label={ariaLabel}
    onClick={() => onChange(!checked)}
    className={`w-11 h-6 rounded-full transition-colors relative shrink-0 ${
      checked
        ? 'bg-brand-navy dark:bg-brand-turquoise'
        : 'bg-muted-foreground/30 dark:bg-muted-foreground/40'
    }`}
  >
    <div
      className={`w-5 h-5 bg-white dark:bg-card rounded-full absolute top-0.5 shadow transition-all ${
        checked ? 'right-0.5' : 'left-0.5'
      }`}
    />
  </button>
);

const ParentSettingsPage = () => {
  const { t } = useTranslation();
  const { token, api } = useAuth();
  const [loading, setLoading] = useState(true);
  const [settings, setSettings] = useState(null);
  const [saving, setSaving] = useState(false);

  const { nassaqError } = useNassaqAlert();

  useEffect(() => {
    let cancelled = false;
    const fetchSettings = async () => {
      try {
        const res = await api.get('/parent-portal/settings');
        if (!cancelled) setSettings(res.data);
      } catch {
        if (!cancelled) {
          setSettings({
            notification_preferences: {
              email: true, sms: true, push: true,
              attendance_alerts: true, grade_alerts: true, behaviour_alerts: true,
            },
            language: 'ar',
          });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchSettings();
    return () => { cancelled = true; };
  }, [token, api]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put('/parent-portal/settings', settings);
      toast.success(t('settingsSaved'));
    } catch {
      nassaqError(t('errorSaving'));
    } finally {
      setSaving(false);
    }
  };

  const updatePref = (key, value) => {
    setSettings(prev => ({
      ...prev,
      notification_preferences: {
        ...prev.notification_preferences,
        [key]: value,
      },
    }));
  };

  if (loading) {
    return (
      <PortalLayout portalType="parent">
        <div className="p-4 space-y-4">
          <Skeleton className="h-48 rounded-2xl" />
          <Skeleton className="h-48 rounded-2xl" />
        </div>
      </PortalLayout>
    );
  }

  const prefs = settings?.notification_preferences || {};
  const rows = [
    { key: 'email', label: t('emailNotifications'), icon: Mail },
    { key: 'sms', label: t('smsNotifications2'), icon: MessageCircle },
    { key: 'attendance_alerts', label: t('attendanceAlerts2'), icon: Shield },
    { key: 'grade_alerts', label: t('gradeAlerts'), icon: Bell },
    { key: 'behaviour_alerts', label: t('behaviorAlerts'), icon: Bell },
  ];

  return (
    <PortalLayout portalType="parent">
      <div className="p-4 space-y-4" data-testid="parent-settings-page">
        <div className="flex items-center gap-2 mb-2">
          <Settings className="h-6 w-6 text-brand-navy dark:text-brand-turquoise" />
          <h1 className="text-xl font-bold font-cairo text-foreground">{t('settings')}</h1>
        </div>

        <Card className="rounded-2xl border-0 shadow-sm bg-card">
          <CardContent className="p-4 space-y-3">
            <h2 className="font-cairo font-bold text-base flex items-center gap-2 text-foreground">
              <Bell className="h-5 w-5 text-brand-navy dark:text-brand-turquoise" />
              {t('notificationPreferences')}
            </h2>

            {rows.map(({ key, label, icon: Icon }) => (
              <div
                key={key}
                className="flex items-center justify-between p-3 rounded-xl bg-muted/40 dark:bg-muted/30 border border-border hover:bg-muted/60 dark:hover:bg-muted/50 transition-colors"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className="w-8 h-8 rounded-lg bg-brand-navy/5 dark:bg-brand-turquoise/15 text-brand-navy dark:text-brand-turquoise flex items-center justify-center shrink-0">
                    <Icon className="h-4 w-4" />
                  </span>
                  <span className="text-sm text-foreground font-tajawal truncate">{label}</span>
                </div>
                <Toggle
                  checked={prefs[key] ?? true}
                  onChange={(v) => updatePref(key, v)}
                  ariaLabel={label}
                />
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="rounded-2xl border-0 shadow-sm bg-card">
          <CardContent className="p-4 space-y-4">
            <h2 className="font-cairo font-bold text-base flex items-center gap-2 text-foreground">
              <Globe className="h-5 w-5 text-brand-navy dark:text-brand-turquoise" />
              {t('language')}
            </h2>
            <div className="flex gap-3">
              {[
                { value: 'ar', label: 'العربية' },
                { value: 'en', label: 'English' },
              ].map(lang => {
                const active = settings?.language === lang.value;
                return (
                  <button
                    key={lang.value}
                    onClick={() => setSettings(prev => ({ ...prev, language: lang.value }))}
                    className={`flex-1 p-3 rounded-xl text-sm font-medium font-cairo transition-all ${
                      active
                        ? 'bg-brand-navy dark:bg-brand-turquoise text-white dark:text-brand-navy shadow-sm'
                        : 'bg-muted/40 dark:bg-muted/30 text-foreground border border-border hover:bg-muted/60 dark:hover:bg-muted/50'
                    }`}
                  >
                    {lang.label}
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>

        <Button
          onClick={handleSave}
          disabled={saving}
          className="w-full bg-brand-navy hover:bg-brand-navy-dark dark:bg-brand-turquoise dark:hover:bg-brand-turquoise/90 text-white dark:text-brand-navy rounded-xl h-12 font-cairo"
        >
          {saving ? t('saving') : t('saveSettings')}
        </Button>
      </div>
    </PortalLayout>
  );
};

export default ParentSettingsPage;
