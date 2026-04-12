import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme , useTranslation } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Skeleton } from '../../components/ui/skeleton';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import {
  Settings, Bell, Globe, Mail, MessageCircle, Shield
} from 'lucide-react';


const Toggle = ({ checked, onChange }) => (
  <button
    onClick={() => onChange(!checked)}
    className={`w-11 h-6 rounded-full transition-all relative ${checked ? 'bg-brand-navy' : 'bg-gray-300'}`}
  >
    <div className={`w-5 h-5 bg-white rounded-full absolute top-0.5 transition-all ${
      checked ? 'right-0.5' : 'left-0.5'
    }`} />
  </button>
);

const ParentSettingsPage = () => {
  const { t } = useTranslation();
  const { token, user, api } = useAuth();
  const { isRTL } = useTheme();
  const [loading, setLoading] = useState(true);
  const [settings, setSettings] = useState(null);
  const [saving, setSaving] = useState(false);

  const { nassaqError, nassaqWarning } = useNassaqAlert();
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const res = await api.get('/parent-portal/settings');
        setSettings(res.data);
      } catch (err) {
        console.error('Error:', err);
        setSettings({
          notification_preferences: {
            email: true, sms: true, push: true,
            attendance_alerts: true, grade_alerts: true, behaviour_alerts: true
          },
          language: 'ar'
        });
      } finally {
        setLoading(false);
      }
    };
    fetchSettings();
  }, [token]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put('/parent-portal/settings', settings);
      toast.success(t('settingsSaved'));
    } catch (err) {
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
        [key]: value
      }
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

  return (
    <PortalLayout portalType="parent">
      <div className="p-4 space-y-4" data-testid="parent-settings-page">
        <div className="flex items-center gap-2 mb-2">
          <Settings className="h-6 w-6 text-brand-navy" />
          <h1 className="text-xl font-bold font-cairo">{t('settings')}</h1>
        </div>

        <Card className="rounded-2xl border-0 shadow-sm">
          <CardContent className="p-4 space-y-4">
            <h2 className="font-cairo font-bold text-base flex items-center gap-2">
              <Bell className="h-5 w-5 text-brand-navy" />
              {t('notificationPreferences')}
            </h2>

            {[
              { key: 'email', label: t('emailNotifications'), icon: Mail },
              { key: 'sms', label: t('smsNotifications2'), icon: MessageCircle },
              { key: 'attendance_alerts', label: t('attendanceAlerts2'), icon: Shield },
              { key: 'grade_alerts', label: t('gradeAlerts'), icon: Bell },
              { key: 'behaviour_alerts', label: t('behaviorAlerts'), icon: Bell },
            ].map(({ key, label, icon: Icon }) => (
              <div key={key} className="flex items-center justify-between p-3 bg-gray-50 rounded-xl">
                <div className="flex items-center gap-3">
                  <Icon className="h-4 w-4 text-gray-500" />
                  <span className="text-sm">{label}</span>
                </div>
                <Toggle checked={prefs[key] ?? true} onChange={(v) => updatePref(key, v)} />
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="rounded-2xl border-0 shadow-sm">
          <CardContent className="p-4 space-y-4">
            <h2 className="font-cairo font-bold text-base flex items-center gap-2">
              <Globe className="h-5 w-5 text-brand-navy" />
              {t('language')}
            </h2>
            <div className="flex gap-3">
              {[
                { value: 'ar', label: 'العربية' },
                { value: 'en', label: 'English' },
              ].map(lang => (
                <button
                  key={lang.value}
                  onClick={() => setSettings(prev => ({ ...prev, language: lang.value }))}
                  className={`flex-1 p-3 rounded-xl text-sm font-medium transition-all ${
                    settings?.language === lang.value
                      ? 'bg-brand-navy text-white'
                      : 'bg-gray-50 text-gray-700 border'
                  }`}
                >
                  {lang.label}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        <Button
          onClick={handleSave}
          disabled={saving}
          className="w-full bg-brand-navy hover:bg-brand-navy-dark text-white rounded-xl h-12"
        >
          {saving
            ? (t('saving'))
            : (t('saveSettings'))}
        </Button>
      </div>
    </PortalLayout>
  );
};

export default ParentSettingsPage;
