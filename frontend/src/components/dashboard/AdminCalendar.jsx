import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { useTranslation, useTheme } from '../../contexts/ThemeContext';
import { useAuth } from '../../contexts/AuthContext';
import { useNassaqAlert } from '../ui/NassaqAlertDialog';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '../../components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../../components/ui/dropdown-menu';
import {
  CalendarDays,
  Plus,
  Upload,
  Pencil,
  Trash2,
  ChevronDown,
  Sparkles,
  Loader2,
  Download,
} from 'lucide-react';
import { formatFullDate } from '../../utils/hijriDate';

const EVENT_TYPES = {
  trip:        { label_ar: 'رحلة',           label_en: 'Trip',         dot: 'bg-violet-500',  ring: 'ring-violet-500/20'  },
  parents:     { label_ar: 'أولياء الأمور',   label_en: 'Parents',      dot: 'bg-pink-500',    ring: 'ring-pink-500/20'    },
  report:      { label_ar: 'تقرير',          label_en: 'Report',       dot: 'bg-amber-500',   ring: 'ring-amber-500/20'   },
  exam:        { label_ar: 'اختبار',         label_en: 'Exam',         dot: 'bg-emerald-500', ring: 'ring-emerald-500/20' },
  holiday:     { label_ar: 'إجازة',          label_en: 'Holiday',      dot: 'bg-sky-500',     ring: 'ring-sky-500/20'     },
  meeting:     { label_ar: 'اجتماع',         label_en: 'Meeting',      dot: 'bg-blue-500',    ring: 'ring-blue-500/20'    },
};

const SHORT_MONTHS_AR = ['يناير','فبراير','مارس','أبريل','مايو','يونيو','يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر'];
const SHORT_MONTHS_EN = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

const formatShortDate = (iso, isRTL) => {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const day = d.getDate();
    const m = isRTL ? SHORT_MONTHS_AR[d.getMonth()] : SHORT_MONTHS_EN[d.getMonth()];
    return `${day} ${m}`;
  } catch {
    return iso;
  }
};

const isToday = (iso) => {
  try {
    const d = new Date(iso);
    const t = new Date();
    return d.getFullYear() === t.getFullYear() && d.getMonth() === t.getMonth() && d.getDate() === t.getDate();
  } catch { return false; }
};

export const AdminCalendar = ({
  // Task #208 §6.3 — optional personal-mode reuse for the IT calendar.
  // Defaults preserve the legacy school-wide /v1/calendar surface so
  // the principal page is byte-identical to before.
  basePath = '/v1/calendar',
  importEnabled = true,
  titleAr = 'الروزنامة الإدارية',
  titleEn = 'Administrative Calendar',
  // Task #307 — opt-in styled empty state (workspace-accent dashed card
  // with a primary CTA that opens the add-event dialog). Default `null`
  // preserves the legacy school-wide neutral empty state byte-identically.
  emptyState = null,
} = {}) => {
  const { t } = useTranslation();
  const { isRTL } = useTheme();
  const { api } = useAuth();
  const { nassaqConfirm, nassaqError } = useNassaqAlert();
  const lang = isRTL ? 'ar' : 'en';

  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ title_ar: '', title_en: '', type: 'meeting', date: '' });
  const [busy, setBusy] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [addMenuOpen, setAddMenuOpen] = useState(false);
  const fileInputRef = useRef(null);

  const fetchEvents = useCallback(async () => {
    try {
      const res = await api.get(`${basePath}/events`);
      const data = Array.isArray(res?.data) ? res.data : (res?.data?.events || []);
      setEvents(data);
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('[AdminCalendar] fetch error:', err);
      toast.error(isRTL ? 'تعذر تحميل الأحداث' : 'Failed to load events');
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, [api, isRTL, basePath]);

  useEffect(() => { fetchEvents(); }, [fetchEvents]);

  // Task #251 — deep-link via ?event_id=… opened from the IT command
  // palette: auto-open the edit dialog for the matching event once the
  // events list has loaded, then strip the query param so a refresh
  // doesn't replay the dialog.
  const _location = useLocation();
  const _navigate = useNavigate();
  const _eventDeepLinkRef = useRef(null);
  useEffect(() => {
    if (!events || !events.length) return;
    const params = new URLSearchParams(_location.search);
    const eid = params.get('event_id');
    if (!eid || _eventDeepLinkRef.current === eid) return;
    const match = events.find((ev) => ev.id === eid);
    if (!match) return;
    _eventDeepLinkRef.current = eid;
    setEditing(match);
    setForm({
      title_ar: match.title_ar || '',
      title_en: match.title_en || '',
      type: match.type || 'meeting',
      date: match.date || '',
    });
    setShowForm(true);
    params.delete('event_id');
    _navigate(
      { pathname: _location.pathname, search: params.toString() ? `?${params.toString()}` : '' },
      { replace: true },
    );
  }, [events, _location.pathname, _location.search, _navigate]);

  const todayLabel = useMemo(() => {
    try { return formatFullDate(new Date(), lang)?.full || ''; } catch { return ''; }
  }, [lang]);

  const sortedEvents = useMemo(
    () => [...events].sort((a, b) => a.date.localeCompare(b.date)),
    [events]
  );

  const openAddForm = () => {
    setEditing(null);
    setForm({ title_ar: '', title_en: '', type: 'meeting', date: new Date().toISOString().slice(0, 10) });
    setShowForm(true);
  };

  const openEditForm = (event) => {
    setEditing(event);
    setForm({
      title_ar: event.title_ar || '',
      title_en: event.title_en || '',
      type: event.type || 'meeting',
      date: event.date || '',
    });
    setShowForm(true);
  };

  const saveEvent = async () => {
    setBusy(true);
    try {
      const payload = {
        title_ar: form.title_ar?.trim() || form.title_en?.trim() || '',
        title_en: form.title_en?.trim() || '',
        type: form.type,
        date: form.date,
      };
      if (editing?.id) {
        const res = await api.put(`${basePath}/events/${editing.id}`, payload);
        const updated = res?.data?.event;
        if (updated) {
          setEvents((prev) => prev.map((e) => (e.id === editing.id ? updated : e)));
        }
        toast.success(isRTL ? 'تم تحديث الحدث' : 'Event updated');
      } else {
        const res = await api.post(`${basePath}/events`, payload);
        const created = res?.data?.event;
        if (created) {
          setEvents((prev) => [...prev, created]);
        }
        toast.success(isRTL ? 'تمت إضافة الحدث' : 'Event added');
      }
      setShowForm(false);
      setEditing(null);
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('[AdminCalendar] save error:', err);
      const detail = err?.response?.data?.error?.message || err?.response?.data?.detail;
      toast.error(detail || (isRTL ? 'تعذر حفظ الحدث' : 'Failed to save event'));
    } finally {
      setBusy(false);
    }
  };

  const triggerImport = () => {
    setAddMenuOpen(false);
    setTimeout(() => {
      fileInputRef.current?.click();
    }, 0);
  };

  const handleDownloadTemplate = () => {
    setAddMenuOpen(false);
    const header = 'اسم المهمة,التاريخ (YYYY-MM-DD),نوع الحدث (رحلة، تقرير، إجازة، أخرى)';
    const example = 'جولة تفقدية – مبنى ب,2026-04-01,رحلة';
    const csvContent = `${header}\n${example}\n`;
    const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'nassaq_calendar_template.csv';
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleFileSelect = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsImporting(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await api.post(`${basePath}/import`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const data = Array.isArray(res?.data) ? res.data : (res?.data?.events || []);
      setEvents(data);
      const inserted = res?.data?.inserted ?? data.length;
      const skipped = res?.data?.skipped ?? 0;
      const summary = isRTL
        ? `تم استيراد ${inserted} حدث${skipped ? ` (تم تخطي ${skipped})` : ''}`
        : `Imported ${inserted} event${inserted === 1 ? '' : 's'}${skipped ? ` (skipped ${skipped})` : ''}`;
      toast.success(summary);
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('[AdminCalendar] import error:', err);
      toast.error(isRTL ? 'تعذر استيراد الملف' : 'Failed to import file');
    } finally {
      setIsImporting(false);
      // Reset so selecting the same file again still triggers onChange.
      if (e?.target) e.target.value = null;
    }
  };

  const performDelete = async (id) => {
    const snapshot = events;
    setEvents((prev) => prev.filter((e) => e.id !== id));
    try {
      await api.delete(`${basePath}/events/${id}`);
      toast.success(isRTL ? 'تم حذف الحدث' : 'Event deleted');
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('[AdminCalendar] delete error:', err);
      setEvents(snapshot);
      const detail = err?.response?.data?.error?.message || err?.response?.data?.detail;
      nassaqError(detail || (isRTL ? 'تعذر حذف الحدث' : 'Failed to delete event'));
    }
  };

  // Per `replit.md` user prefs + `NassaqAlertDialog` standard, all
  // destructive confirmations route through the branded modal — never
  // `window.confirm`, never a bare optimistic delete.
  const deleteEvent = (event) => {
    const id = event?.id || event;
    const title = event?.title_ar || event?.title_en || '';
    nassaqConfirm(
      isRTL
        ? (title ? `هل تريد حذف الحدث "${title}"؟` : 'هل تريد حذف هذا الحدث؟')
        : (title ? `Delete event "${title}"?` : 'Delete this event?'),
      () => performDelete(id),
      {
        title: isRTL ? 'تأكيد الحذف' : 'Confirm deletion',
        confirmText: isRTL ? 'حذف' : 'Delete',
        cancelText: isRTL ? 'إلغاء' : 'Cancel',
        type: 'warning',
      },
    );
  };

  return (
    <Card className="card-nassaq h-full" data-testid="admin-calendar">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <CardTitle className="flex items-center gap-2 font-cairo text-lg">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-purple to-brand-navy flex items-center justify-center shadow-sm shadow-brand-purple/30">
              <CalendarDays className="h-4.5 w-4.5 text-white" />
            </div>
            {isRTL ? titleAr : titleEn}
          </CardTitle>
          <div className="flex items-center gap-2 flex-wrap">
            <Badge className="bg-brand-turquoise text-white border-0 font-cairo text-[11px] px-2 py-0.5 shadow-sm shadow-brand-turquoise/30 animate-pulse" data-testid="admin-calendar-today-badge">
              {isRTL ? 'اليوم' : 'Today'}
            </Badge>
            <Badge className="bg-brand-turquoise/15 text-brand-turquoise border-0 font-cairo text-[11px] px-2 py-0.5">
              {todayLabel}
            </Badge>
            <DropdownMenu open={addMenuOpen} onOpenChange={setAddMenuOpen}>
              <DropdownMenuTrigger asChild>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={isImporting}
                  className="h-8 rounded-xl text-xs px-2.5 gap-1 border-brand-turquoise/40 text-brand-turquoise hover:bg-brand-turquoise/10 hover:text-brand-turquoise focus-visible:text-brand-turquoise disabled:opacity-60"
                >
                  {isImporting ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Plus className="h-3.5 w-3.5" />
                  )}
                  {isImporting ? (isRTL ? 'جارٍ الاستيراد' : 'Importing') : (isRTL ? 'إضافة' : 'Add')}
                  <ChevronDown className="h-3 w-3 opacity-70" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="font-tajawal">
                <DropdownMenuItem onClick={() => { setAddMenuOpen(false); openAddForm(); }} className="gap-2">
                  <Plus className="h-3.5 w-3.5 text-brand-turquoise" />
                  {isRTL ? 'إضافة يدوية' : 'Manual Add'}
                </DropdownMenuItem>
                {importEnabled && (
                  <>
                    <DropdownMenuItem
                      onClick={triggerImport}
                      className="gap-2"
                      disabled={busy || isImporting}
                      data-testid="admin-calendar-import"
                    >
                      {isImporting ? (
                        <Loader2 className="h-3.5 w-3.5 text-brand-purple animate-spin" />
                      ) : (
                        <Upload className="h-3.5 w-3.5 text-brand-purple" />
                      )}
                      {isRTL ? 'استيراد' : 'Import'}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      onClick={handleDownloadTemplate}
                      className="gap-2"
                      data-testid="admin-calendar-download-template"
                    >
                      <Download className="h-3.5 w-3.5 text-brand-navy" />
                      {isRTL ? 'تحميل القالب' : 'Download Template'}
                    </DropdownMenuItem>
                  </>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
            <input
              type="file"
              ref={fileInputRef}
              className="hidden"
              accept=".csv,text/csv"
              onChange={handleFileSelect}
              data-testid="admin-calendar-file-input"
            />
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {loading ? (
          <div className="flex items-center justify-center py-10">
            <Loader2 className="h-5 w-5 animate-spin text-brand-turquoise" />
          </div>
        ) : sortedEvents.length === 0 ? (
          emptyState ? (
            <div
              className="text-center py-12 px-4 rounded-xl border border-dashed border-workspace-accent-border bg-workspace-accent-light/30"
              data-testid="admin-calendar-empty-state-styled"
            >
              <Sparkles className="h-12 w-12 mx-auto mb-3 text-workspace-accent" />
              <h3 className="font-bold text-base mb-2 font-cairo text-workspace-accent-fg">
                {emptyState.title}
              </h3>
              <p className="text-muted-foreground text-sm font-tajawal mb-4 max-w-md mx-auto">
                {emptyState.description}
              </p>
              <Button
                onClick={openAddForm}
                className="bg-workspace-accent hover:bg-workspace-accent-fg text-white rounded-xl gap-2 px-5"
                data-testid="admin-calendar-empty-state-cta"
              >
                <Plus className="h-4 w-4" />
                {emptyState.ctaLabel}
              </Button>
            </div>
          ) : (
            <div className="text-center py-8">
              <Sparkles className="h-7 w-7 text-brand-turquoise/60 mx-auto mb-2" />
              <p className="text-sm font-tajawal text-muted-foreground">
                {isRTL ? 'لا توجد أحداث قادمة' : 'No upcoming events'}
              </p>
            </div>
          )
        ) : (
          <ul className="space-y-1.5" data-testid="admin-calendar-list">
            {sortedEvents.map((event) => {
              const meta = EVENT_TYPES[event.type] || EVENT_TYPES.meeting;
              const today = isToday(event.date);
              return (
                <li
                  key={event.id}
                  className={`group flex items-center gap-3 p-2.5 rounded-xl border transition-all duration-200 cursor-pointer ${
                    today
                      ? 'bg-brand-turquoise/5 border-brand-turquoise/30 ring-1 ring-brand-turquoise/20'
                      : 'bg-muted/30 border-border/40 hover:bg-muted/60'
                  }`}
                  onClick={() => setSelected(event)}
                  data-testid={`event-row-${event.id}`}
                >
                  <span className={`relative w-2.5 h-2.5 rounded-full ${meta.dot} shrink-0 ring-2 ${meta.ring}`}>
                    {today && <span className={`absolute inset-0 rounded-full ${meta.dot} animate-ping opacity-60`} />}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-tajawal font-semibold truncate">
                      {isRTL ? (event.title_ar || event.title_en) : (event.title_en || event.title_ar)}
                    </p>
                    <p className="text-[11px] text-muted-foreground font-tajawal truncate">
                      {isRTL ? meta.label_ar : meta.label_en}
                    </p>
                  </div>
                  <div className="text-end shrink-0">
                    <p className="text-[11px] font-cairo font-semibold text-brand-purple">
                      {formatShortDate(event.date, isRTL)}
                    </p>
                    {today && (
                      <Badge className="mt-0.5 h-4 px-1.5 text-[9px] bg-brand-turquoise text-white border-0 font-cairo">
                        {isRTL ? 'اليوم' : 'Today'}
                      </Badge>
                    )}
                  </div>
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); openEditForm(event); }}
                      className="w-7 h-7 rounded-lg hover:bg-brand-turquoise/10 text-brand-turquoise flex items-center justify-center"
                      aria-label={t('edit')}
                      data-testid={`edit-event-${event.id}`}
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); deleteEvent(event); }}
                      className="w-7 h-7 rounded-lg hover:bg-red-500/10 text-red-500 flex items-center justify-center"
                      aria-label={t('delete')}
                      data-testid={`delete-event-${event.id}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>

      {/* Details modal */}
      <Dialog open={!!selected} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent className="font-tajawal max-w-md">
          <DialogHeader>
            <DialogTitle className="font-cairo text-lg flex items-center gap-2">
              {selected && (
                <span className={`w-2.5 h-2.5 rounded-full ${(EVENT_TYPES[selected.type] || EVENT_TYPES.meeting).dot}`} />
              )}
              {selected && (isRTL ? selected.title_ar : selected.title_en)}
            </DialogTitle>
            <DialogDescription className="font-tajawal">
              {selected && formatShortDate(selected.date, isRTL)}
            </DialogDescription>
          </DialogHeader>
          {selected && (
            <div className="text-sm font-tajawal text-muted-foreground leading-relaxed">
              {isRTL ? (selected.details_ar || '—') : (selected.details_en || '—')}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Add / Edit form */}
      <Dialog open={showForm} onOpenChange={(open) => { if (!open) { setShowForm(false); setEditing(null); } }}>
        <DialogContent className="font-tajawal max-w-md">
          <DialogHeader>
            <DialogTitle className="font-cairo text-lg">
              {editing ? (isRTL ? 'تعديل حدث' : 'Edit Event') : (isRTL ? 'إضافة حدث' : 'Add Event')}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <label className="text-xs font-cairo text-muted-foreground mb-1 block">
                {isRTL ? 'العنوان' : 'Title'}
              </label>
              <input
                value={form.title_ar}
                onChange={(e) => setForm({ ...form, title_ar: e.target.value })}
                className="w-full h-9 rounded-lg border border-input bg-background px-3 text-sm"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-cairo text-muted-foreground mb-1 block">{isRTL ? 'التاريخ' : 'Date'}</label>
                <input
                  type="date"
                  value={form.date}
                  onChange={(e) => setForm({ ...form, date: e.target.value })}
                  className="w-full h-9 rounded-lg border border-input bg-background px-3 text-sm"
                />
              </div>
              <div>
                <label className="text-xs font-cairo text-muted-foreground mb-1 block">{isRTL ? 'النوع' : 'Type'}</label>
                <select
                  value={form.type}
                  onChange={(e) => setForm({ ...form, type: e.target.value })}
                  className="w-full h-9 rounded-lg border border-input bg-background px-3 text-sm"
                >
                  {Object.entries(EVENT_TYPES).map(([key, meta]) => (
                    <option key={key} value={key}>{isRTL ? meta.label_ar : meta.label_en}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => { setShowForm(false); setEditing(null); }}>
              {isRTL ? 'إلغاء' : 'Cancel'}
            </Button>
            <Button
              disabled={busy || !form.date || !form.title_ar}
              onClick={saveEvent}
              className="bg-brand-turquoise hover:bg-brand-turquoise/90 text-white"
            >
              {busy && <Loader2 className="h-3.5 w-3.5 me-1.5 animate-spin" />}
              {isRTL ? 'حفظ' : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
};

export default AdminCalendar;
