export const TOUR_STEPS = [
  {
    id: 'add-students',
    target: '[data-tour="sidebar-import-students"]',
    titleKey: 'itTourStep1Title',
    bodyKey: 'itTourStep1Body',
  },
  {
    id: 'add-classes',
    target: '[data-tour="sidebar-my-classes"]',
    titleKey: 'itTourStep2Title',
    bodyKey: 'itTourStep2Body',
  },
  {
    id: 'build-schedule',
    target: '[data-tour="sidebar-workspace-schedule"]',
    titleKey: 'itTourStep3Title',
    bodyKey: 'itTourStep3Body',
  },
  {
    id: 'invite-parents',
    target: '[data-tour="sidebar-communication"]',
    titleKey: 'itTourStep4Title',
    bodyKey: 'itTourStep4Body',
  },
  {
    id: 'lesson-planner',
    target: '[data-tour="sidebar-lesson-planner"]',
    titleKey: 'itTourStep5Title',
    bodyKey: 'itTourStep5Body',
  },
  {
    id: 'personal-calendar',
    target: '[data-tour="sidebar-calendar"]',
    titleKey: 'itTourStep6Title',
    bodyKey: 'itTourStep6Body',
  },
  {
    id: 'export-workspace',
    // 2026-05-19 — `sidebar-workspace-settings` was retired when
    // the standalone IT workspace-settings page was split: identity
    // moved into Account Settings, schedule + year/term into the
    // فصولي page as a new tab. Both tour steps now point at the
    // Account Settings sidebar entry, which is the canonical home
    // for workspace identity + export + tour replay.
    target: '[data-tour="sidebar-account-settings"]',
    titleKey: 'itTourStep7Title',
    bodyKey: 'itTourStep7Body',
  },
  {
    id: 'account-settings',
    target: '[data-tour="sidebar-account-settings"]',
    titleKey: 'itTourStep8Title',
    bodyKey: 'itTourStep8Body',
  },
];
