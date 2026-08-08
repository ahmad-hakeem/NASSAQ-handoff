import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import {
  Calendar, CalendarDays, Clock, Save, Loader2, Settings,
} from 'lucide-react';

import { useAuth } from '@/shared/contexts/AuthContext';
import { useTranslation } from '@/shared/contexts/ThemeContext';
import { Sidebar } from '@/shared/components/layout/Sidebar';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Checkbox } from '@/shared/components/ui/checkbox';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/shared/components/ui/select';
import { useNassaqAlert } from '@/shared/components/ui/NassaqAlertDialog';

import { WorkspaceSchedulePanel } from './WorkspaceSchedulePage';
import { TeacherPersonalCalendarPanel } from './TeacherPersonalCalendarPage';
import { getApiErrorMessage } from '@/shared/models/utils/apiError';

const IT_SETTINGS_WEEKDAYS = [
  { key: 'sun', i18n: 'sunday' },
  { key: 'mon', i18n: 'monday' },
  { key: 'tue', i18n: 'tuesday' },
  { key: 'wed', i18n: 'wednesday' },
  { key: 'thu', i18n: 'thursday' },
  { key: 'fri', i18n: 'friday' },
  { key: 'sat', i18n: 'saturday' },
];

const IT_SETTINGS_TIMEZONES = [
  'Asia/Riyadh', 'Asia/Dubai', 'Asia/Kuwait', 'Asia/Baghdad',
  'Asia/Amman', 'Africa/Cairo', 'UTC',
];

// Canonical Saudi academic terms. `value` is the stored label (kept in
// Arabic to match backend defaults); `labelKey` localizes the display.
const IT_TERM_OPTIONS = [
  { value: 'الفصل الأول', labelKey: 'termNameFirst' },
  { value: 'الفصل الثاني', labelKey: 'termNameSecond' },
  { value: 'الفصل الثالث', labelKey: 'termNameThird' },
];

const VALID_TABS = new Set(['schedule', 'calendar', 'settings']);

/**
 * 2026-05-19 — IA refactor: dedicated "الجدول والتقويم" hub for
 * Independent-Teacher accounts. Extracts the three time-management
 * tabs (schedule / personal calendar / schedule settings) out of the
 * bloated "فصولي" page so they live in their own focused surface
 * reachable from the main sidebar.
 *
 * Backend contracts, RBAC slices and MFA step-up envelopes are
 * unchanged — this is a frontend-only relocation. The three sub-
 * tabs reuse the existing headless panels (`WorkspaceSchedulePanel`,
 * `TeacherPersonalCalendarPanel`) and the same partial PUT against
 * `/independent-teacher/workspace/settings` that the schedule
 * settings card used in its previous home.
 */
export default function TimeManagementHubPage() {
  const navigate = useNavigate();
  const { user, api, isRTL } = useAuth();
  const { t } = useTranslation();
  const { nassaqError } = useNassaqAlert();

  const isIndependentTeacher = user?.role === 'independent_teacher';

  // Personal-calendar tab gates on ROLE, not the lazy /auth/me/permissions
  // fetch. The backend base set for independent_teacher always includes
  // `events.author_own` (rbac.py — Phase 2 §6.3), so the fetch could only
  // ever false-negative: fetchPermissions() returns null both on error AND
  // when another mounted caller (Sidebar) already has a fetch in flight,
  // which this page used to coerce into an empty permission set — hiding
  // the tab permanently (the "تقويمي الشخصي disappeared" regression).
  // Server-side authorization is enforced on every calendar route anyway.
  const canUsePersonalCalendar = isIndependentTeacher;

  const [searchParams, setSearchParams] = useSearchParams();
  const _rawTab = searchParams.get('tab');
  const activeTab = (() => {
    if (_rawTab === 'calendar' && canUsePersonalCalendar) return 'calendar';
    if (_rawTab === 'settings') return 'settings';
    if (_rawTab === 'schedule') return 'schedule';
    return 'schedule';
  })();

  const handleTabChange = (tab) => {
    const safe = (tab === 'calendar' && !canUsePersonalCalendar) ? 'schedule'
      : VALID_TABS.has(tab) ? tab : 'schedule';
    setSearchParams(safe === 'schedule' ? {} : { tab: safe });
  };

  // Non-IT users have no workspace schedule/calendar/settings surface;
  // bounce to the dashboard rather than rendering an empty hub.
  useEffect(() => {
    if (user && !isIndependentTeacher) navigate('/teacher', { replace: true });
  }, [user, isIndependentTeacher, navigate]);

  // ---- إعدادات الجدول: state + load/save (relocated from فصولي) ----
  const [itSettingsLoaded, setItSettingsLoaded] = useState(false);
  const [itSettingsLoadError, setItSettingsLoadError] = useState(false);
  const [itSettingsSaving, setItSettingsSaving] = useState(false);
  const [itWorkingDays, setItWorkingDays] = useState([]);
  const [itPeriodsPerDay, setItPeriodsPerDay] = useState(7);
  const [itPeriodMinutes, setItPeriodMinutes] = useState(45);
  const [itDayStart, setItDayStart] = useState('07:00');
  const [itTimezone, setItTimezone] = useState('Asia/Riyadh');
  const [itYearLabel, setItYearLabel] = useState('');
  const [itTermLabel, setItTermLabel] = useState('');

  const loadItScheduleSettings = useCallback(async () => {
    if (!isIndependentTeacher || !api) return;
    setItSettingsLoadError(false);
    try {
      const { data } = await api.get('/independent-teacher/workspace/settings');
      if (!data) return;
      setItWorkingDays(Array.isArray(data.working_days) ? data.working_days : []);
      setItPeriodsPerDay(Number(data.periods_per_day) || 7);
      setItPeriodMinutes(Number(data.period_minutes) || 45);
      setItDayStart(data.school_day_start || '07:00');
      setItTimezone(data.timezone || 'Asia/Riyadh');
      setItYearLabel(data.academic_year_label || '');
      setItTermLabel(data.academic_term_label || '');
      setItSettingsLoaded(true);
    } catch (err) {
      const msg = getApiErrorMessage(err) || t('failedToLoadWorkspaceSettings');
      nassaqError(msg);
      setItSettingsLoadError(true);
    }
  }, [isIndependentTeacher, api, nassaqError, t]);

  useEffect(() => {
    if (isIndependentTeacher && api) loadItScheduleSettings();
  }, [isIndependentTeacher, api, loadItScheduleSettings]);

  const toggleItWorkingDay = (key) => {
    setItWorkingDays(prev => prev.includes(key) ? prev.filter(d => d !== key) : [...prev, key]);
  };

  const handleSaveItScheduleSettings = async () => {
    if (!itWorkingDays.length) { nassaqError(t('workingDaysRequired')); return; }
    if (itPeriodsPerDay < 1 || itPeriodsPerDay > 12) { nassaqError(t('periodsPerDayRange')); return; }
    if (itPeriodMinutes < 10 || itPeriodMinutes > 120) { nassaqError(t('periodMinutesRange')); return; }
    if (!/^([01]?\d|2[0-3]):[0-5]\d$/.test(String(itDayStart || ''))) {
      nassaqError(t('dayStartInvalid'));
      return;
    }
    setItSettingsSaving(true);
    try {
      const payload = {
        working_days: itWorkingDays,
        periods_per_day: Number(itPeriodsPerDay),
        period_minutes: Number(itPeriodMinutes),
        school_day_start: itDayStart,
        timezone: itTimezone,
      };
      if (itYearLabel?.trim()) payload.academic_year_label = itYearLabel.trim();
      if (itTermLabel?.trim()) payload.academic_term_label = itTermLabel.trim();
      await api.put('/independent-teacher/workspace/settings', payload);
      toast.success(t('workspaceSettingsSaved'));
    } catch (err) {
      const msg = getApiErrorMessage(err) || t('failedToSaveWorkspaceSettings');
      nassaqError(msg);
    } finally {
      setItSettingsSaving(false);
    }
  };

  if (!isIndependentTeacher) return null;

  // Localized options, plus any previously-saved custom term so the closed
  // state always reflects the persisted value.
  const itTermOptions = [
    ...IT_TERM_OPTIONS.map(o => ({ value: o.value, label: t(o.labelKey) })),
    ...(itTermLabel && !IT_TERM_OPTIONS.some(o => o.value === itTermLabel)
      ? [{ value: itTermLabel, label: itTermLabel }]
      : []),
  ];

  const tabBtnCls = (tab) => `px-5 py-2.5 text-sm font-medium font-cairo transition-colors relative whitespace-nowrap ${
    activeTab === tab
      ? 'text-brand-navy dark:text-brand-turquoise'
      : 'text-muted-foreground hover:text-foreground'
  }`;
  const tabUnderline = (tab) => (activeTab === tab
    ? <span className="absolute bottom-0 inset-x-0 h-0.5 bg-brand-turquoise rounded-full" />
    : null);

  return (
    <Sidebar>
      <div className="min-h-screen bg-background" dir={isRTL ? 'rtl' : 'ltr'}>
        <div className="sticky top-0 z-30 bg-background/95 backdrop-blur border-b border-border/40">
          <div className="px-4 sm:px-6 py-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h1 className="text-2xl font-bold font-cairo flex items-center gap-2 text-foreground">
                  <CalendarDays className="h-7 w-7 text-brand-turquoise" />
                  {t('timeManagementHub')}
                </h1>
                <p className="text-sm text-muted-foreground mt-0.5 font-tajawal">
                  {t('timeManagementHubSubtitle')}
                </p>
              </div>
            </div>
          </div>
          <div className="px-4 sm:px-6 flex gap-0 border-t border-border/30 overflow-x-auto flex-nowrap scrollbar-thin">
            <button
              onClick={() => handleTabChange('schedule')}
              className={tabBtnCls('schedule')}
              data-testid="time-hub-schedule-tab"
            >
              <span className="flex items-center gap-1.5">
                <Calendar className="h-4 w-4" />
                جدولي
              </span>
              {tabUnderline('schedule')}
            </button>
            {canUsePersonalCalendar && (
              <button
                onClick={() => handleTabChange('calendar')}
                className={tabBtnCls('calendar')}
                data-testid="time-hub-calendar-tab"
              >
                <span className="flex items-center gap-1.5">
                  <Calendar className="h-4 w-4" />
                  {t('itPersonalCalendarTab')}
                </span>
                {tabUnderline('calendar')}
              </button>
            )}
            <button
              onClick={() => handleTabChange('settings')}
              className={tabBtnCls('settings')}
              data-testid="time-hub-settings-tab"
            >
              <span className="flex items-center gap-1.5">
                <Settings className="h-4 w-4" />
                {t('itScheduleTabLabel')}
              </span>
              {tabUnderline('settings')}
            </button>
          </div>
        </div>

        <div className="px-4 sm:px-6 py-4 space-y-4">
          {activeTab === 'schedule' && (
            <WorkspaceSchedulePanel
              embedded
              onNavigateToClasses={() => navigate('/teacher/classes')}
            />
          )}

          {activeTab === 'calendar' && canUsePersonalCalendar && (
            <TeacherPersonalCalendarPanel />
          )}

          {activeTab === 'settings' && (
            <div className="max-w-4xl mx-auto space-y-6" data-testid="it-schedule-settings-panel">
              {itSettingsLoadError && !itSettingsLoaded && (
                <Card className="card-nassaq border-red-200 bg-red-50/40">
                  <CardContent className="pt-5 pb-5 flex items-center justify-between gap-3">
                    <span className="text-sm font-cairo text-red-700">
                      {t('failedToLoadWorkspaceSettings')}
                    </span>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={loadItScheduleSettings}
                      className="rounded-xl gap-2"
                      data-testid="retry-it-schedule-settings"
                    >
                      <Loader2 className="h-4 w-4" />
                      {t('retry')}
                    </Button>
                  </CardContent>
                </Card>
              )}

              <Card className="card-nassaq border-workspace-accent-border">
                <CardHeader className="pb-4 border-b border-workspace-accent-border bg-workspace-accent-light/40">
                  <CardTitle className="font-cairo flex items-center gap-2 text-lg text-workspace-accent-fg">
                    <Clock className="h-5 w-5 text-workspace-accent" />
                    {t('itScheduleSettingsTitle')}
                  </CardTitle>
                  <p className="text-xs text-workspace-accent-fg/70 font-tajawal mt-1">
                    {t('itScheduleSettingsDesc')}
                  </p>
                </CardHeader>
                <CardContent className="space-y-5 pt-5">
                  <div>
                    <Label className="mb-3 block font-cairo text-sm">{t('workingDaysLabel')}</Label>
                    <div className="flex flex-wrap gap-2">
                      {IT_SETTINGS_WEEKDAYS.map(d => {
                        const on = itWorkingDays.includes(d.key);
                        return (
                          <label
                            key={d.key}
                            className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition ${on
                              ? 'bg-workspace-accent-light border-workspace-accent text-workspace-accent-fg'
                              : 'bg-white border-slate-200 text-slate-600 hover:border-workspace-accent/50'
                            }`}
                            data-testid={`it-workspace-day-${d.key}`}
                          >
                            <Checkbox
                              checked={on}
                              onCheckedChange={() => toggleItWorkingDay(d.key)}
                              disabled={!itSettingsLoaded}
                            />
                            <span className="text-sm font-medium font-cairo">{t(d.i18n)}</span>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <Label className="mb-2 block font-cairo text-sm">{t('periodsPerDayLabel')}</Label>
                      <Input
                        type="number"
                        min={1}
                        max={12}
                        value={itPeriodsPerDay}
                        onChange={e => setItPeriodsPerDay(parseInt(e.target.value || '0', 10))}
                        className="h-11 rounded-xl"
                        data-testid="it-workspace-periods-input"
                        disabled={!itSettingsLoaded}
                      />
                    </div>
                    <div>
                      <Label className="mb-2 block font-cairo text-sm">{t('periodMinutesLabel')}</Label>
                      <Input
                        type="number"
                        min={10}
                        max={120}
                        value={itPeriodMinutes}
                        onChange={e => setItPeriodMinutes(parseInt(e.target.value || '0', 10))}
                        className="h-11 rounded-xl"
                        data-testid="it-workspace-period-minutes-input"
                        disabled={!itSettingsLoaded}
                      />
                    </div>
                    <div>
                      <Label className="mb-2 block font-cairo text-sm">{t('schoolDayStartLabel')}</Label>
                      <Input
                        type="time"
                        value={itDayStart}
                        onChange={e => setItDayStart(e.target.value)}
                        className="h-11 rounded-xl"
                        data-testid="it-workspace-day-start-input"
                        disabled={!itSettingsLoaded}
                      />
                      <p className="text-xs text-muted-foreground font-tajawal mt-1">
                        {t('schoolDayStartHelp')}
                      </p>
                    </div>
                    <div>
                      <Label className="mb-2 block font-cairo text-sm">{t('timezone')}</Label>
                      <Select
                        value={itTimezone}
                        onValueChange={setItTimezone}
                        disabled={!itSettingsLoaded}
                      >
                        <SelectTrigger
                          className="h-11 rounded-xl"
                          data-testid="it-workspace-timezone-select"
                        >
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {IT_SETTINGS_TIMEZONES.map(z => (
                            <SelectItem key={z} value={z}>{z}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card className="card-nassaq border-workspace-accent-border">
                <CardHeader className="pb-4 border-b border-workspace-accent-border bg-workspace-accent-light/40">
                  <CardTitle className="font-cairo flex items-center gap-2 text-lg text-workspace-accent-fg">
                    <Calendar className="h-5 w-5 text-workspace-accent" />
                    {t('academicYearSectionTitle')}
                  </CardTitle>
                  <p className="text-xs text-workspace-accent-fg/70 font-tajawal mt-1">
                    {t('academicYearSectionDesc')}
                  </p>
                </CardHeader>
                <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-5">
                  <div>
                    <Label className="mb-2 block font-cairo text-sm">{t('academicYearNameLabel')}</Label>
                    <Input
                      dir={isRTL ? 'rtl' : 'ltr'}
                      value={itYearLabel}
                      onChange={e => setItYearLabel(e.target.value)}
                      className="h-11 rounded-xl"
                      placeholder={t('academicYearNamePlaceholder')}
                      data-testid="it-workspace-year-label-input"
                      disabled={!itSettingsLoaded}
                    />
                  </div>
                  <div>
                    <Label className="mb-2 block font-cairo text-sm">{t('academicTermNameLabel')}</Label>
                    <Select
                      value={itTermLabel || undefined}
                      onValueChange={setItTermLabel}
                      disabled={!itSettingsLoaded}
                    >
                      <SelectTrigger
                        className="h-11 rounded-xl"
                        data-testid="it-workspace-term-label-select"
                      >
                        <SelectValue placeholder={t('academicTermNamePlaceholder')} />
                      </SelectTrigger>
                      <SelectContent>
                        {itTermOptions.map(opt => (
                          <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </CardContent>
              </Card>

              <div className="flex justify-end">
                <Button
                  onClick={handleSaveItScheduleSettings}
                  disabled={itSettingsSaving || !itSettingsLoaded}
                  className="bg-workspace-accent hover:bg-workspace-accent-fg text-white rounded-xl gap-2 min-w-[160px] h-11"
                  data-testid="save-it-schedule-settings"
                >
                  {itSettingsSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  {t('saveChanges2')}
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </Sidebar>
  );
}
