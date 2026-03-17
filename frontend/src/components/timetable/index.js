/**
 * Timetable Components Index
 * فهرس مكونات الجدول المدرسي
 */

// Main Page Component
export { default as PrincipalTimetablePage } from './PrincipalTimetablePage';

// Section Components
export { default as TimetablePageHeader } from './TimetablePageHeader';
export { default as TimetableStatusBanner } from './TimetableStatusBanner';
export { default as TimetableActionBar } from './TimetableActionBar';
export { default as TimetableReadinessPanel } from './TimetableReadinessPanel';
export { default as TimetableViewControls, TimetableViewModeTabs, TimetableSearchInput, TimetableToggleControls } from './TimetableViewControls';
export { default as TimetableGridSection, TimetableCell, TimetableEmptyGridState, TimetableGridSkeleton } from './TimetableGridSection';
export { default as TimetableInsightsPanel, StatItem, AIInsightNotice } from './TimetableInsightsPanel';
export { default as TimetableVersionManager, VersionItem } from './TimetableVersionManager';
export { default as TimetableIssuesSection, IssueAccordionItem, IssueSeverityBadge } from './TimetableIssuesSection';

// Modal Components
export {
  AITimetableGenerationModal,
  PartialRegenerationModal,
  PublishTimetableVersionModal,
  ArchiveTimetableVersionModal,
  TimetableDiagnosticsModal,
  TimetableSessionDetailsDrawer
} from './TimetableModals';

// Types and Constants
export * from './types';
