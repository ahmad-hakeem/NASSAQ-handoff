import { SETTINGS_TABS } from '@/features/platform/pages/platformSettingsTabs';

describe('PlatformSettingsPage SETTINGS_TABS (T&C unification regression)', () => {
  it('does not expose a "terms" tab — T&C is unified at the public /terms route', () => {
    const ids = SETTINGS_TABS.map((tab) => tab.id);
    expect(ids).not.toContain('terms');
  });

  it('keeps the expected platform-admin tabs in order', () => {
    const ids = SETTINGS_TABS.map((tab) => tab.id);
    expect(ids).toEqual(['general', 'brand', 'privacy', 'contact', 'security']);
  });

  it('every tab carries an id, icon, and bilingual labels', () => {
    SETTINGS_TABS.forEach((tab) => {
      expect(typeof tab.id).toBe('string');
      expect(tab.id.length).toBeGreaterThan(0);
      expect(tab.icon).toBeDefined();
      expect(typeof tab.label_ar).toBe('string');
      expect(typeof tab.label_en).toBe('string');
    });
  });
});
