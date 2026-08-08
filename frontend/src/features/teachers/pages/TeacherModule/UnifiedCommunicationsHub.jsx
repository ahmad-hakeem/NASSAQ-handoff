import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Inbox, Send, Bell } from 'lucide-react';
import { Sidebar } from '@/shared/components/layout/Sidebar';
import { Badge } from '@/shared/components/ui/badge';
import { useAuth } from '@/shared/contexts/AuthContext';
import { useTheme, useTranslation } from '@/shared/contexts/ThemeContext';
import { TeacherNotificationsPanel } from './TeacherNotificationsPage';
import { IndependentTeacherCommunicationPanel } from './IndependentTeacherCommunicationPage';

// 2026-05-18 — Unified "التواصل والإشعارات" hub for Independent
// Teachers. Merges the old standalone Notifications Inbox
// (/teacher/notifications) and the IT Communication Composer
// (/teacher/communication) under one route + sidebar entry.
//
// State preservation: BOTH panels are mounted simultaneously and
// hidden via CSS (`display: none`) instead of being unmounted on
// tab change, so the composer's draft (subject + body + selected
// recipients) and the inbox's pagination cursor / filter state
// survive cross-tab navigation. The inactive panel is also marked
// `aria-hidden` and pulled out of the tab order so SR users don't
// see ghost content.
//
// Permission gating: the IT composer + inbox routes are already
// IT-only via ProtectedRoute in appRoutes.js, so we don't repeat
// the permission check here. Non-IT users render the legacy
// TeacherCommunicationPageInner upstream (the IT branch in
// TeacherCommunicationPage.jsx is what now returns this hub).

const TAB_INBOX = 'inbox';
const TAB_COMPOSE = 'compose';
const VALID_TABS = new Set([TAB_INBOX, TAB_COMPOSE]);

export default function UnifiedCommunicationsHub() {
  const { api, user } = useAuth();
  const { isRTL } = useTheme();
  const { t } = useTranslation();
  const isAr = (user?.preferred_language || 'ar') === 'ar';

  const [searchParams, setSearchParams] = useSearchParams();
  const rawTab = (searchParams.get('tab') || '').toLowerCase();
  const activeTab = VALID_TABS.has(rawTab) ? rawTab : TAB_INBOX;

  // Live unread counter for the Inbox tab badge. We poll the same
  // IT-scoped endpoint NotificationBell uses so the two numbers
  // never disagree, and listen for the global `notifications:refresh`
  // event so bulk mark-as-read in either surface updates the badge
  // immediately without waiting for the next poll.
  const [unread, setUnread] = useState(0);
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await api.get('/independent-teacher/notifications/unread-count');
        if (!cancelled) setUnread(Number(res?.data?.unread_count) || 0);
      } catch {
        if (!cancelled) setUnread(0);
      }
    };
    load();
    const onRefresh = () => load();
    window.addEventListener('notifications:refresh', onRefresh);
    return () => {
      cancelled = true;
      window.removeEventListener('notifications:refresh', onRefresh);
    };
  }, [api]);

  const setTab = (tab) => {
    const next = VALID_TABS.has(tab) ? tab : TAB_INBOX;
    const params = new URLSearchParams(searchParams);
    if (next === TAB_INBOX) params.delete('tab');
    else params.set('tab', next);
    setSearchParams(params, { replace: true });
  };

  const headerTitle = useMemo(
    () => t('unifiedCommHubTitle') || (isAr ? 'التواصل والإشعارات' : 'Communications & Notifications'),
    [t, isAr],
  );
  const headerSubtitle = useMemo(
    () => t('unifiedCommHubSubtitle')
      || (isAr
        ? 'إشعاراتك ورسائلك إلى طلابك وأولياء أمورهم في مكان واحد.'
        : 'Notifications and outbound messages to your students and parents in one place.'),
    [t, isAr],
  );

  return (
    <div className="flex h-screen bg-gray-50" dir={isRTL ? 'rtl' : 'ltr'}>
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-4 sm:p-6">
        <div className="max-w-5xl mx-auto space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <Bell className="h-6 w-6 text-brand-turquoise shrink-0" />
              <div className="min-w-0">
                <h1 className="text-xl sm:text-2xl font-bold text-gray-900 font-cairo">
                  {headerTitle}
                </h1>
                <p className="text-xs sm:text-sm text-gray-500 font-tajawal">
                  {headerSubtitle}
                </p>
              </div>
            </div>
          </div>

          {/* Tab bar — mirrors the visual language used by the
              TeacherClassesPage tabs (underline + brand-turquoise
              active color) so the IT navigation feels consistent
              across the two unified hubs we shipped today. */}
          <div
            role="tablist"
            aria-label={headerTitle}
            className="flex flex-wrap gap-0 border-b border-border/40 bg-white rounded-t-lg shadow-sm"
            data-testid="unified-comm-tabbar"
          >
            <button
              type="button"
              role="tab"
              id="unified-comm-tab-inbox"
              aria-selected={activeTab === TAB_INBOX}
              aria-controls="unified-comm-panel-inbox"
              onClick={() => setTab(TAB_INBOX)}
              className={`px-5 py-2.5 text-sm font-medium font-cairo transition-colors relative flex items-center gap-2 ${
                activeTab === TAB_INBOX
                  ? 'text-brand-navy dark:text-brand-turquoise'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
              data-testid="unified-comm-tab-inbox"
            >
              <Inbox className="h-4 w-4" />
              <span>{t('unifiedCommTabInbox') || (isAr ? 'البريد الوارد' : 'Inbox')}</span>
              {unread > 0 && (
                <Badge
                  variant="destructive"
                  className="ms-1 h-5 min-w-[1.25rem] px-1.5 text-[10px] font-semibold flex items-center justify-center rounded-full"
                  data-testid="unified-comm-inbox-unread-badge"
                >
                  {unread > 99 ? '99+' : unread}
                </Badge>
              )}
              {activeTab === TAB_INBOX && (
                <span className="absolute bottom-0 inset-x-0 h-0.5 bg-brand-turquoise rounded-full" />
              )}
            </button>
            <button
              type="button"
              role="tab"
              id="unified-comm-tab-compose"
              aria-selected={activeTab === TAB_COMPOSE}
              aria-controls="unified-comm-panel-compose"
              onClick={() => setTab(TAB_COMPOSE)}
              className={`px-5 py-2.5 text-sm font-medium font-cairo transition-colors relative flex items-center gap-2 ${
                activeTab === TAB_COMPOSE
                  ? 'text-brand-navy dark:text-brand-turquoise'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
              data-testid="unified-comm-tab-compose"
            >
              <Send className="h-4 w-4" />
              <span>{t('unifiedCommTabCompose') || (isAr ? 'إرسال رسالة' : 'Compose Message')}</span>
              {activeTab === TAB_COMPOSE && (
                <span className="absolute bottom-0 inset-x-0 h-0.5 bg-brand-turquoise rounded-full" />
              )}
            </button>
          </div>

          {/* Both panels stay mounted; we toggle visibility with
              `hidden` so React preserves form/draft + pagination
              state across tab switches per the spec's "State
              Preservation" guardrail. The inactive panel is also
              `aria-hidden` and removed from the tab order. */}
          <div className="bg-white rounded-b-lg shadow-sm">
            <section
              role="tabpanel"
              id="unified-comm-panel-inbox"
              aria-labelledby="unified-comm-tab-inbox"
              aria-hidden={activeTab !== TAB_INBOX}
              hidden={activeTab !== TAB_INBOX}
              className="p-4 sm:p-6"
            >
              <TeacherNotificationsPanel embedded />
            </section>
            <section
              role="tabpanel"
              id="unified-comm-panel-compose"
              aria-labelledby="unified-comm-tab-compose"
              aria-hidden={activeTab !== TAB_COMPOSE}
              hidden={activeTab !== TAB_COMPOSE}
              className="p-4 sm:p-6"
            >
              <IndependentTeacherCommunicationPanel embedded />
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}
