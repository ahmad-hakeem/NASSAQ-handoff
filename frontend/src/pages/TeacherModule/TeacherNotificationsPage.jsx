import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { Sidebar } from '../../components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { useNassaqAlert } from '../../components/ui/NassaqAlertDialog';
import { Loader2, Bell, CheckCheck, ExternalLink, Inbox, Users, GraduationCap, Building2, Gauge, Sparkles, Info } from 'lucide-react';
import { formatHijriDate } from '../../utils/hijriDate';

// Task #249 — IT Notifications Inbox.
// Backend pins user_id + tenant_id == itw_{user_id}; this page is
// IT-only via the protected route in appRoutes.js. The bell in the
// header polls /notifications/unread-count globally; this page calls
// the IT-scoped /independent-teacher/notifications/unread-count for
// the per-tab badges and the mark-all-read action.

const CATEGORY_META = {
  collab_invite:       { icon: Users,        labelAr: 'تعاون',         labelEn: 'Collaboration' },
  parent_accept:       { icon: GraduationCap,labelAr: 'أولياء الأمور', labelEn: 'Parents' },
  workspace_lifecycle: { icon: Building2,    labelAr: 'مساحة العمل',   labelEn: 'Workspace' },
  quota:               { icon: Gauge,        labelAr: 'الحصص',          labelEn: 'Quota' },
  lesson_plan:         { icon: Sparkles,     labelAr: 'خطط الدروس',    labelEn: 'Lesson plans' },
  general:             { icon: Info,         labelAr: 'عام',            labelEn: 'General' },
};

const READ_TABS = ['all', 'unread'];
const CATEGORY_FILTERS = ['all', 'collab_invite', 'parent_accept', 'workspace_lifecycle', 'quota', 'lesson_plan'];

function CategoryIcon({ category, className }) {
  const meta = CATEGORY_META[category] || CATEGORY_META.general;
  const Icon = meta.icon;
  return <Icon className={className} />;
}

function formatRowDate(value, isAr) {
  if (!value) return '';
  try {
    const d = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(d.getTime())) return '';
    if (isAr) return formatHijriDate(d, { withTime: true });
    return d.toLocaleString('en-GB', {
      year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit',
    });
  } catch (e) {
    return '';
  }
}

export default function TeacherNotificationsPage() {
  const { api, user } = useAuth();
  const navigate = useNavigate();
  const { nassaqError, nassaqInfo } = useNassaqAlert();

  const isAr = (user?.preferred_language || 'ar') === 'ar';
  const [readTab, setReadTab] = useState('all');         // all | unread
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [items, setItems] = useState([]);
  const [nextCursor, setNextCursor] = useState(null);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [unread, setUnread] = useState(0);
  const [marking, setMarking] = useState(false);

  const fetchList = useCallback(async ({ readMode, category, cursor } = {}) => {
    const append = Boolean(cursor);
    if (append) setLoadingMore(true); else setLoading(true);
    try {
      const params = { limit: 25 };
      if (category && category !== 'all') params.category = category;
      if (readMode === 'unread') params.unread_only = true;
      if (cursor) params.cursor = cursor;
      const res = await api.get('/independent-teacher/notifications', { params });
      const page = Array.isArray(res?.data?.items) ? res.data.items : [];
      setItems((prev) => append ? [...prev, ...page] : page);
      setNextCursor(res?.data?.next_cursor || null);
      setHasMore(Boolean(res?.data?.has_more));
    } catch (err) {
      const msg = err?.response?.data?.detail || (isAr ? 'تعذّر تحميل الإشعارات.' : 'Failed to load notifications.');
      nassaqError(msg);
      if (!append) setItems([]);
    } finally {
      if (append) setLoadingMore(false); else setLoading(false);
    }
  }, [api, isAr, nassaqError]);

  const fetchUnread = useCallback(async () => {
    try {
      const res = await api.get('/independent-teacher/notifications/unread-count');
      setUnread(Number(res?.data?.unread_count) || 0);
    } catch (e) {
      // Soft-fail — header bell polls separately.
    }
  }, [api]);

  useEffect(() => {
    fetchList({ readMode: readTab, category: categoryFilter });
  }, [readTab, categoryFilter, fetchList]);
  useEffect(() => { fetchUnread(); }, [fetchUnread, items.length]);

  const handleLoadMore = useCallback(() => {
    if (!nextCursor || loadingMore) return;
    fetchList({ readMode: readTab, category: categoryFilter, cursor: nextCursor });
  }, [nextCursor, loadingMore, fetchList, readTab, categoryFilter]);

  const handleMarkRead = useCallback(async (notif) => {
    if (notif.is_read) return;
    try {
      await api.post(`/independent-teacher/notifications/${notif.id}/read`);
      setItems((prev) => prev.map((n) => n.id === notif.id ? { ...n, is_read: true } : n));
    } catch (e) {
      // best-effort UX
    }
  }, [api]);

  const handleOpen = useCallback(async (notif) => {
    await handleMarkRead(notif);
    if (notif.cta_url) navigate(notif.cta_url);
  }, [handleMarkRead, navigate]);

  const handleMarkAll = useCallback(async () => {
    setMarking(true);
    try {
      const res = await api.post('/independent-teacher/notifications/read-all');
      const updated = Number(res?.data?.updated) || 0;
      setUnread(0);
      // Re-fetch the visible list so the active tab reflects the new
      // state — most importantly, the "unread" tab must become empty
      // instead of showing now-read rows. The bell badge is synced
      // via the global ``notifications:refresh`` event below.
      await fetchList({ readMode: readTab, category: categoryFilter });
      window.dispatchEvent(new CustomEvent('notifications:refresh'));
      nassaqInfo(isAr ? `تم تحديد ${updated} إشعارًا كمقروء.` : `Marked ${updated} notifications as read.`);
    } catch (err) {
      nassaqError(err?.response?.data?.detail || (isAr ? 'تعذّر تحديد الإشعارات.' : 'Failed to mark notifications.'));
    } finally {
      setMarking(false);
    }
  }, [api, isAr, nassaqError, nassaqInfo, fetchList, readTab, categoryFilter]);

  const filtered = useMemo(() => items, [items]);

  return (
    <div className="flex h-screen bg-gray-50" dir={isAr ? 'rtl' : 'ltr'}>
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-6">
        <div className="max-w-4xl mx-auto space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Bell className="h-6 w-6 text-blue-600" />
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  {isAr ? 'الإشعارات' : 'Notifications'}
                </h1>
                <p className="text-sm text-gray-500">
                  {isAr
                    ? 'دعوات التعاون وقبول أولياء الأمور وتنبيهات مساحة العمل والحصص.'
                    : 'Collaborator invites, parent accepts, workspace and quota events.'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {unread > 0 && (
                <Badge variant="destructive" className="px-2 py-1">
                  {unread} {isAr ? 'غير مقروء' : 'unread'}
                </Badge>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={handleMarkAll}
                disabled={marking || unread === 0}
              >
                {marking ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCheck className="h-4 w-4" />}
                <span className="mx-1">
                  {isAr ? 'تعليم الكل كمقروء' : 'Mark all as read'}
                </span>
              </Button>
            </div>
          </div>

          <Tabs value={readTab} onValueChange={setReadTab}>
            <TabsList className="flex gap-1">
              {READ_TABS.map((t) => (
                <TabsTrigger key={t} value={t} className="flex items-center gap-1">
                  <Inbox className="h-3.5 w-3.5" />
                  <span>
                    {t === 'all'
                      ? (isAr ? 'الكل' : 'All')
                      : (isAr ? 'غير المقروء' : 'Unread')}
                  </span>
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-gray-500">
              {isAr ? 'تصفية حسب النوع:' : 'Filter by category:'}
            </span>
            {CATEGORY_FILTERS.map((c) => {
              const meta = c === 'all'
                ? { labelAr: 'الكل', labelEn: 'All', icon: Inbox }
                : CATEGORY_META[c];
              const Icon = meta.icon;
              const active = categoryFilter === c;
              return (
                <Button
                  key={c}
                  type="button"
                  size="sm"
                  variant={active ? 'default' : 'outline'}
                  onClick={() => setCategoryFilter(c)}
                  className="h-7 px-2 text-xs"
                >
                  <Icon className="h-3 w-3" />
                  <span className="mx-1">{isAr ? meta.labelAr : meta.labelEn}</span>
                </Button>
              );
            })}
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                {isAr ? 'سجل الإشعارات' : 'Notifications'}
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {loading ? (
                <div className="p-10 flex justify-center"><Loader2 className="h-6 w-6 animate-spin text-blue-600" /></div>
              ) : filtered.length === 0 ? (
                <div className="p-10 text-center text-gray-500">
                  <Inbox className="h-10 w-10 mx-auto mb-2 text-gray-300" />
                  {isAr ? 'لا توجد إشعارات لعرضها.' : 'Nothing to show yet.'}
                </div>
              ) : (
                <ul className="divide-y">
                  {filtered.map((n) => {
                    const unreadRow = !n.is_read;
                    return (
                      <li
                        key={n.id}
                        className={`flex items-start gap-3 p-4 hover:bg-gray-50 cursor-pointer ${unreadRow ? 'bg-blue-50/40' : ''}`}
                        onClick={() => handleOpen(n)}
                      >
                        <div className="mt-0.5">
                          <CategoryIcon category={n.category} className={`h-5 w-5 ${unreadRow ? 'text-blue-600' : 'text-gray-400'}`} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className={`font-semibold ${unreadRow ? 'text-gray-900' : 'text-gray-700'}`}>
                              {(isAr ? n.title : n.title_en) || n.title || ''}
                            </span>
                            {unreadRow && <span className="h-2 w-2 rounded-full bg-blue-500" />}
                          </div>
                          {(n.message || n.message_en) && (
                            <div className="text-sm text-gray-600 mt-0.5 line-clamp-2">
                              {(isAr ? n.message : n.message_en) || n.message}
                            </div>
                          )}
                          <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
                            <span>{formatRowDate(n.created_at, isAr)}</span>
                            {n.cta_url && (
                              <span className="inline-flex items-center gap-1 text-blue-600">
                                <ExternalLink className="h-3 w-3" />
                                {isAr ? 'فتح' : 'Open'}
                              </span>
                            )}
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
              {hasMore && !loading && (
                <div className="p-3 border-t text-center">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handleLoadMore}
                    disabled={loadingMore}
                  >
                    {loadingMore
                      ? <Loader2 className="h-4 w-4 animate-spin" />
                      : (isAr ? 'تحميل المزيد' : 'Load more')}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
