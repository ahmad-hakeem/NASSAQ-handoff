import { Settings, Palette, Shield, Mail, Lock } from 'lucide-react';

// Platform-admin sidebar tabs for `PlatformSettingsPage`.
//
// Extracted into its own pure module so the regression test in
// `frontend/src/pages/__tests__/PlatformSettingsPage.tabs.test.js` can import
// it without pulling the full page (which depends on react-router, axios,
// auth context, etc.) through Jest.
//
// Unification note: T&C is centrally maintained in `TermsAndConditionsPage.jsx`
// and served at the public `/terms` route. The previously-present `terms` tab
// (and its `/settings/terms/*` per-tenant editor) is intentionally absent so
// platform admins do not author content that is not surfaced to end users.
export const SETTINGS_TABS = [
  { id: 'general', icon: Settings, label_ar: 'الإعدادات العامة', label_en: 'General' },
  { id: 'brand', icon: Palette, label_ar: 'الهوية البصرية', label_en: 'Branding' },
  { id: 'privacy', icon: Shield, label_ar: 'سياسة الخصوصية', label_en: 'Privacy' },
  { id: 'contact', icon: Mail, label_ar: 'بيانات التواصل', label_en: 'Contact' },
  { id: 'security', icon: Lock, label_ar: 'سياسات الأمان والجلسات', label_en: 'Security & Sessions Policy' },
];
