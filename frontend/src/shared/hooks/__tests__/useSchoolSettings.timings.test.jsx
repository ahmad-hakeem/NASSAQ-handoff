import { act, renderHook, waitFor } from '@testing-library/react';
import { useSchoolSettings } from '../useSchoolSettings';

const mockNavigate = jest.fn();
const mockApiGet = jest.fn();
const mockApiPut = jest.fn();
const mockToastSuccess = jest.fn();
const mockNassaqError = jest.fn();
const mockApi = {
  get: (...args) => mockApiGet(...args),
  put: (...args) => mockApiPut(...args),
  post: jest.fn(async () => ({ data: {} })),
  delete: jest.fn(),
};
const mockUser = { id: 'principal-1', tenant_id: 'school-1' };
const mockAuth = { api: mockApi, user: mockUser };

jest.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
  useLocation: () => ({ pathname: '/principal/schedule', search: '?tab=settings&sub=timings' }),
}), { virtual: true });

jest.mock('@/shared/contexts/AuthContext', () => ({
  useAuth: () => mockAuth,
}));

jest.mock('@/shared/contexts/ThemeContext', () => ({
  useTranslation: () => ({
    t: (key, values = {}) => ({
      timingValidationSchoolDayTooShort: `اليوم الدراسي أقصر من المطلوب بـ ${values.shortage} دقيقة.`,
      timingValidationTimeOrder: 'يجب أن يكون وقت نهاية اليوم بعد وقت بدايته.',
      timingValidationDaySpecificBreaks: 'يلزم تطبيق فترات الاستراحة على جميع الأيام.',
      timingSettingsVersionConflict: 'عُدّلت الإعدادات في جلسة أخرى',
      timingFieldDayEnd: 'وقت نهاية اليوم',
      timingFieldSettings: 'إعدادات التوقيت',
    }[key] || key),
  }),
}));

jest.mock('@/shared/components/ui/NassaqAlertDialog', () => ({
  useNassaqAlert: () => ({
    nassaqWarning: jest.fn(),
    nassaqConfirm: jest.fn(),
    nassaqError: (...args) => mockNassaqError(...args),
  }),
}));

jest.mock('@dnd-kit/core', () => ({
  PointerSensor: function PointerSensor() {},
  useSensor: () => ({}),
  useSensors: () => [],
}));

jest.mock('sonner', () => ({
  toast: { success: (...args) => mockToastSuccess(...args) },
}));

const canonicalSettings = (overrides = {}) => ({
  academic_year: '1447',
  current_semester: '2',
  day_start: '07:10',
  day_end: '13:30',
  periods_per_day: 7,
  period_duration: 45,
  break_duration: 20,
  break_after_period: 3,
  attendance_pattern: 'winter',
  max_standby_per_week: 5,
  working_days: ['الأحد', 'الإثنين'],
  weekend_days: ['الجمعة', 'السبت'],
  breaks: [],
  settings_version: 8,
  ...overrides,
});

function ancillaryResponse(url) {
  if (url.includes('/hard-constraints')) return { data: { hard_constraints: [] } };
  if (url.includes('/soft-constraints')) return { data: { soft_constraints: [] } };
  if (url.includes('/unavailability')) return { data: { items: [] } };
  if (url.includes('/custom-soft-constraints')) return { data: { constraints: [] } };
  if (url.includes('/constraint-patterns')) return { data: { builtin_patterns: [], custom_patterns: [] } };
  if (url.includes('/other-duties')) return { data: { duties: [] } };
  if (url === '/timetable-readiness/check') return { data: {} };
  return { data: [] };
}

describe('useSchoolSettings timetable settings persistence', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockApiGet.mockImplementation(async (url) => (
      url === '/school/settings'
        ? { data: canonicalSettings() }
        : ancillaryResponse(url)
    ));
  });

  it('hydrates snake-case GET values and saves a full camel-case payload with the version', async () => {
    mockApiPut.mockResolvedValue({
      data: {
        success: true,
        message: 'تم الحفظ',
        settings: canonicalSettings({ break_duration: 25, settings_version: 9 }),
      },
    });
    const { result } = renderHook(() => useSchoolSettings());
    await waitFor(() => expect(result.current.timingSettings.breakDuration).toBe(20));

    act(() => result.current.handleSettingChange('breakDuration', 25));
    await act(async () => result.current.saveAllSettings());

    expect(mockApiPut).toHaveBeenCalledWith('/school/settings', expect.objectContaining({
      academicYear: '1447',
      currentSemester: '2',
      dayStart: '07:10',
      dayEnd: '13:30',
      periodsPerDay: 7,
      periodDuration: 45,
      breakDuration: 25,
      breakAfterPeriod: 3,
      attendancePattern: 'winter',
      maxStandbyPerWeek: 5,
      workingDays: ['الأحد', 'الإثنين'],
      weekendDays: expect.arrayContaining(['الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت']),
      breaks: [],
      expected_version: 8,
    }));
    expect(result.current.timingSettings.breakDuration).toBe(25);
    expect(result.current.settingsVersion).toBe(9);
    expect(result.current.hasChanges).toBe(false);

    mockApiGet.mockImplementation(async (url) => (
      url === '/school/settings'
        ? { data: canonicalSettings({ break_duration: 25, settings_version: 9 }) }
        : ancillaryResponse(url)
    ));
    await act(async () => result.current.fetchData());
    expect(result.current.timingSettings.breakDuration).toBe(25);
  });

  it('preserves valid zero values across all canonical aliases', async () => {
    mockApiGet.mockImplementation(async (url) => (
      url === '/school/settings'
        ? {
            data: canonicalSettings({
              periods_per_day: 0,
              period_duration: 0,
              break_duration: 0,
              break_after_period: 0,
              breaks: [{ id: 1, name: '', after_period: 0, duration: 0, type: 'break' }],
            }),
          }
        : ancillaryResponse(url)
    ));
    const { result } = renderHook(() => useSchoolSettings());

    await waitFor(() => expect(result.current.timingSettings.breakDuration).toBe(0));
    expect(result.current.timingSettings.periodsPerDay).toBe(0);
    expect(result.current.timingSettings.periodDuration).toBe(0);
    expect(result.current.timingSettings.breakAfterPeriod).toBe(0);
    expect(result.current.breakTimes[0]).toEqual(expect.objectContaining({
      afterPeriod: 0,
      duration: 0,
    }));
  });

  it('preserves a null break duration as inherited instead of replacing it with 15', async () => {
    mockApiGet.mockImplementation(async (url) => (
      url === '/school/settings'
        ? { data: canonicalSettings({ breaks: [{ id: 1, name: 'Inherited', after_period: 2, duration: null, type: 'break' }] }) }
        : ancillaryResponse(url)
    ));
    const { result } = renderHook(() => useSchoolSettings());
    await waitFor(() => expect(result.current.breakTimes).toHaveLength(1));
    expect(result.current.breakTimes[0].duration).toBeNull();
  });

  it('keeps the draft and surfaces the backend message when saving fails', async () => {
    mockApiPut.mockRejectedValue({
      response: {
        status: 409,
        data: { success: false, error: { message: 'ألغِ نشر الجدول قبل تعديل التوقيت' } },
      },
    });
    const { result } = renderHook(() => useSchoolSettings());
    await waitFor(() => expect(result.current.settingsVersion).toBe(8));
    act(() => result.current.handleSettingChange('breakDuration', 25));

    await act(async () => result.current.saveAllSettings());

    expect(result.current.timingSettings.breakDuration).toBe(25);
    expect(result.current.hasChanges).toBe(true);
    expect(mockNassaqError).toHaveBeenCalledWith('ألغِ نشر الجدول قبل تعديل التوقيت');
    expect(mockToastSuccess).not.toHaveBeenCalled();
  });

  it('blocks a locally invalid save and preserves the entered timing draft', async () => {
    const { result } = renderHook(() => useSchoolSettings());
    await waitFor(() => expect(result.current.settingsVersion).toBe(8));
    act(() => result.current.handleSettingChange('dayEnd', '07:00'));
    mockApiPut.mockClear();

    await act(async () => result.current.saveAllSettings());

    expect(mockApiPut).not.toHaveBeenCalled();
    expect(result.current.timingSettings.dayEnd).toBe('07:00');
    expect(result.current.hasChanges).toBe(true);
    expect(mockNassaqError).toHaveBeenCalledWith('يجب أن يكون وقت نهاية اليوم بعد وقت بدايته؛ لا يمكن أن يمتد اليوم إلى اليوم التالي.');
  });

  it('localizes structured timing validation errors instead of showing backend English', async () => {
    mockApiPut.mockRejectedValue({
      response: {
        status: 422,
        data: {
          detail: {
            code: 'TIMING_VALIDATION_ERROR',
            reason: 'school_day_too_short',
            field: 'day_end',
            shortage_minutes: 25,
            message: 'School day is too short',
          },
        },
      },
    });
    const { result } = renderHook(() => useSchoolSettings());
    await waitFor(() => expect(result.current.settingsVersion).toBe(8));

    await act(async () => result.current.saveAllSettings());

    expect(mockNassaqError).toHaveBeenCalledWith('اليوم الدراسي أقصر من مجموع الحصص والاستراحات بـ 25 دقيقة.');
    expect(result.current.hasChanges).toBe(false);
  });

  it('reports a settings GET failure instead of replacing it with defaults', async () => {
    mockApiGet.mockImplementation(async (url) => {
      if (url === '/school/settings') {
        throw {
          response: {
            status: 503,
            data: { success: false, error: { message: 'خدمة الإعدادات غير متاحة' } },
          },
        };
      }
      return ancillaryResponse(url);
    });
    const { result } = renderHook(() => useSchoolSettings());

    await waitFor(() => expect(result.current.settingsLoadError).toBe('خدمة الإعدادات غير متاحة'));
    expect(mockNassaqError).toHaveBeenCalledWith('خدمة الإعدادات غير متاحة');
    expect(mockApiPut).not.toHaveBeenCalled();
  });

  it('keeps a conflicting draft until the user explicitly reloads server settings', async () => {
    mockApiPut.mockRejectedValue({
      response: {
        status: 409,
        data: {
          success: false,
          error: {
            code: 'settings_version_conflict',
            message: 'عُدّلت الإعدادات في جلسة أخرى',
          },
        },
      },
    });
    const { result } = renderHook(() => useSchoolSettings());
    await waitFor(() => expect(result.current.settingsVersion).toBe(8));
    act(() => result.current.handleSettingChange('breakDuration', 25));

    await act(async () => result.current.saveAllSettings());
    expect(result.current.timingSettings.breakDuration).toBe(25);
    expect(result.current.hasChanges).toBe(true);
    expect(result.current.timingSaveError).toEqual({
      message: 'عُدّلت إعدادات التوقيت في جلسة أخرى. احتفظنا بمسودتك؛ حمّل أحدث نسخة لمراجعتها.',
      isConflict: true,
    });

    await act(async () => result.current.reloadTimingSettings());
    expect(result.current.timingSettings.breakDuration).toBe(20);
    expect(result.current.hasChanges).toBe(false);
    expect(result.current.timingSaveError).toBeNull();
  });

  it('does not let a stale load or save response overwrite a newer local draft', async () => {
    let resolveSettings;
    const delayedSettings = new Promise(resolve => { resolveSettings = resolve; });
    mockApiGet.mockImplementation((url) => (
      url === '/school/settings' ? delayedSettings : Promise.resolve(ancillaryResponse(url))
    ));
    const first = renderHook(() => useSchoolSettings());
    act(() => first.result.current.handleSettingChange('breakDuration', 25));
    await act(async () => {
      resolveSettings({ data: canonicalSettings({ break_duration: 20 }) });
      await delayedSettings;
    });
    expect(first.result.current.timingSettings.breakDuration).toBe(25);
    expect(first.result.current.hasChanges).toBe(true);
    first.unmount();

    mockApiGet.mockImplementation(async (url) => (
      url === '/school/settings' ? { data: canonicalSettings() } : ancillaryResponse(url)
    ));
    let resolveSave;
    mockApiPut.mockReturnValue(new Promise(resolve => { resolveSave = resolve; }));
    const second = renderHook(() => useSchoolSettings());
    await waitFor(() => expect(second.result.current.settingsVersion).toBe(8));
    act(() => second.result.current.handleSettingChange('breakDuration', 25));
    let savePromise;
    act(() => { savePromise = second.result.current.saveAllSettings(); });
    act(() => second.result.current.handleSettingChange('periodDuration', 50));
    await act(async () => {
      resolveSave({
        data: {
          success: true,
          settings: canonicalSettings({ break_duration: 25, period_duration: 45, settings_version: 9 }),
        },
      });
      await savePromise;
    });

    expect(second.result.current.timingSettings.periodDuration).toBe(50);
    expect(second.result.current.hasChanges).toBe(true);
    expect(second.result.current.settingsVersion).toBe(9);
  });
});