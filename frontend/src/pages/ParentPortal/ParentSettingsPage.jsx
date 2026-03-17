import React, { useState, useEffect } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Skeleton } from '../../components/ui/skeleton';
import { toast } from 'sonner';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import axios from 'axios';
import {
  Settings, Bell, Globe, Mail, MessageCircle, Shield
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const Toggle = ({ checked, onChange }) => (
  <button
    onClick={() => onChange(!checked)}
    className={`w-11 h-6 rounded-full transition-all relative ${checked ? 'bg-indigo-600' : 'bg-gray-300'}`}
  >
    <div className={`w-5 h-5 bg-white rounded-full absolute top-0.5 transition-all ${
      checked ? 'right-0.5' : 'left-0.5'
    }`} />
  </button>
);

const ParentSettingsPage = () => {
  const { token, user } = useAuth();
  const { isRTL } = useTheme();
  const [loading, setLoading] = useState(true);
  const [settings, setSettings] = useState(null);
  const [saving, setSaving] = useState(false);

  const { nassaqError, nassaqWarning } = useNassaqAlert();
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const res = await axios.get(`${API_URL}/api/parent-portal/settings`, {
          headers: { Authorization: `Bearer ${token}` }
        });
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
      await axios.put(`${API_URL}/api/parent-portal/settings`, settings, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(isRTL ? 'تم حفظ الإعدادات' : 'Settings saved');
    } catch (err) {
      nassaqError(isRTL ? 'خطأ في الحفظ' : 'Error saving');
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
          <Settings className="h-6 w-6 text-indigo-600" />
          <h1 className="text-xl font-bold font-cairo">{isRTL ? 'الإعدادات' : 'Settings'}</h1>
        </div>

        <Card className="rounded-2xl border-0 shadow-sm">
          <CardContent className="p-4 space-y-4">
            <h2 className="font-bold text-base flex items-center gap-2">
              <Bell className="h-5 w-5 text-indigo-600" />
              {isRTL ? 'تفضيلات الإشعارات' : 'Notification Preferences'}
            </h2>

            {[
              { key: 'email', label: isRTL ? 'إشعارات البريد الإلكتروني' : 'Email Notifications', icon: Mail },
              { key: 'sms', label: isRTL ? 'إشعارات الرسائل القصيرة' : 'SMS Notifications', icon: MessageCircle },
              { key: 'attendance_alerts', label: isRTL ? 'تنبيهات الحضور والغياب' : 'Attendance Alerts', icon: Shield },
              { key: 'grade_alerts', label: isRTL ? 'تنبيهات الدرجات' : 'Grade Alerts', icon: Bell },
              { key: 'behaviour_alerts', label: isRTL ? 'تنبيهات السلوك' : 'Behavior Alerts', icon: Bell },
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
            <h2 className="font-bold text-base flex items-center gap-2">
              <Globe className="h-5 w-5 text-indigo-600" />
              {isRTL ? 'اللغة' : 'Language'}
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
                      ? 'bg-indigo-600 text-white'
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
          className="w-full bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl h-12"
        >
          {saving
            ? (isRTL ? 'جاري الحفظ...' : 'Saving...')
            : (isRTL ? 'حفظ الإعدادات' : 'Save Settings')}
        </Button>
      </div>
    </PortalLayout>
  );
};

export default ParentSettingsPage;
