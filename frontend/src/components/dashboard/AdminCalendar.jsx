import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useTranslation, useTheme } from '../../contexts/ThemeContext';
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

const SEED_EVENTS = [
  { id: 'evt-1', title_ar: 'جولة تفقدية – مبنى ب', title_en: 'Inspection Tour – Building B', type: 'trip',    date: '2026-03-28', details_ar: 'جولة تفقدية على فصول مبنى ب يرافقها قائد المدرسة.', details_en: 'Inspection of Building B classrooms led by the principal.' },
  { id: 'evt-2', title_ar: 'يوم مفتوح لأولياء الأمور', title_en: 'Open Day for Parents', type: 'parents',  date: '2026-03-29', details_ar: 'استقبال أولياء الأمور لمناقشة أداء الطلاب الفصلي.', details_en: 'Welcoming parents to discuss term performance.' },
  { id: 'evt-3', title_ar: 'تقرير نهاية الفصل', title_en: 'End-of-Term Report', type: 'report',   date: '2026-03-30', details_ar: 'تسليم التقارير النهائية للفصل الدراسي.', details_en: 'Submission of final term reports.' },
  { id: 'evt-4', title_ar: 'اختبارات نَفِس الأسبوعية', title_en: 'Weekly Nafis Tests', type: 'exam',     date: '2026-04-02', details_ar: 'انعقاد الاختبارات الأسبوعية لطلاب الصف.', details_en: 'Weekly assessments for grade students.' },
  { id: 'evt-5', title_ar: 'بداية إجازة منتصف الفصل', title_en: 'Mid-term Break Begins', type: 'holiday',  date: '2026-04-05', details_ar: 'بداية عطلة منتصف الفصل الدراسي للطلاب.', details_en: 'Start of mid-term break for students.' },
];

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

export const AdminCalendar = () => {
  const { t } = useTranslation();
  const { isRTL } = useTheme();
  const lang = isRTL ? 'ar' : 'en';

  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ title_ar: '', title_en: '', type: 'meeting', date: '' });
  const [busy, setBusy] = useState(false);
  const [addMenuOpen, setAddMenuOpen] = useState(false);
  const [importedFile, setImportedFile] = useState(null);
  const fileInputRef = useRef(null);

  const fetchEvents = useCallback(async () => {
    await new Promise((r) => setTimeout(r, 250));
    setEvents([...SEED_EVENTS].sort((a, b) => a.date.localeCompare(b.date)));
    setLoading(false);
  }, []);

  useEffect(() => { fetchEvents(); }, [fetchEvents]);

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
    await new Promise((r) => setTimeout(r, 200));
    setEvents((prev) => {
      if (editing) {
        return prev.map((e) => (e.id === editing.id ? { ...e, ...form } : e));
      }
      const id = `evt-${Date.now()}`;
      return [...prev, { id, ...form }];
    });
    setBusy(false);
    setShowForm(false);
    setEditing(null);
  };

  const triggerImport = () => {
    setAddMenuOpen(false);
    setTimeout(() => {
      fileInputRef.current?.click();
    }, 0);
  };

  const handleFileSelect = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImportedFile(file);
    setBusy(true);
    // Placeholder for backend processing — captured for future API call.
    // eslint-disable-next-line no-console
    console.log('[AdminCalendar] file selected for import:', {
      name: file.name,
      size: file.size,
      type: file.type,
    });
    await new Promise((r) => setTimeout(r, 200));
    setBusy(false);
    // Reset input so selecting the same file again still triggers onChange.
    e.target.value = '';
  };

  const deleteEvent = async (id) => {
    setEvents((prev) => prev.filter((e) => e.id !== id));
    await new Promise((r) => setTimeout(r, 150));
  };

  return (
    <Card className="card-nassaq h-full" data-testid="admin-calendar">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <CardTitle className="flex items-center gap-2 font-cairo text-lg">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-purple to-brand-navy flex items-center justify-center shadow-sm shadow-brand-purple/30">
              <CalendarDays className="h-4.5 w-4.5 text-white" />
            </div>
            {isRTL ? 'الروزنامة الإدارية' : 'Administrative Calendar'}
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
                <Button size="sm" variant="outline" className="h-8 rounded-xl text-xs px-2.5 gap-1 border-brand-turquoise/40 text-brand-turquoise hover:bg-brand-turquoise/10">
                  <Plus className="h-3.5 w-3.5" />
                  {isRTL ? 'إضافة' : 'Add'}
                  <ChevronDown className="h-3 w-3 opacity-70" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="font-tajawal">
                <DropdownMenuItem onClick={() => { setAddMenuOpen(false); openAddForm(); }} className="gap-2">
                  <Plus className="h-3.5 w-3.5 text-brand-turquoise" />
                  {isRTL ? 'إضافة يدوية' : 'Manual Add'}
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={triggerImport}
                  className="gap-2"
                  disabled={busy}
                  data-testid="admin-calendar-import"
                >
                  <Upload className="h-3.5 w-3.5 text-brand-purple" />
                  {isRTL ? 'استيراد' : 'Import'}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <input
              type="file"
              ref={fileInputRef}
              className="hidden"
              accept=".csv,.xlsx,.json"
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
          <div className="text-center py-8">
            <Sparkles className="h-7 w-7 text-brand-turquoise/60 mx-auto mb-2" />
            <p className="text-sm font-tajawal text-muted-foreground">
              {isRTL ? 'لا توجد أحداث قادمة' : 'No upcoming events'}
            </p>
          </div>
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
                      onClick={(e) => { e.stopPropagation(); deleteEvent(event.id); }}
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
                {isRTL ? 'العنوان (عربي)' : 'Title (AR)'}
              </label>
              <input
                value={form.title_ar}
                onChange={(e) => setForm({ ...form, title_ar: e.target.value })}
                className="w-full h-9 rounded-lg border border-input bg-background px-3 text-sm"
              />
            </div>
            <div>
              <label className="text-xs font-cairo text-muted-foreground mb-1 block">
                {isRTL ? 'العنوان (إنجليزي)' : 'Title (EN)'}
              </label>
              <input
                value={form.title_en}
                onChange={(e) => setForm({ ...form, title_en: e.target.value })}
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
              disabled={busy || !form.date || (!form.title_ar && !form.title_en)}
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
