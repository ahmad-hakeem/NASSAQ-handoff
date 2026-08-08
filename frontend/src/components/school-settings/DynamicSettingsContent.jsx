import React from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Badge } from '../ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { Switch } from '../ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Separator } from '../ui/separator';
import { ScrollArea } from '../ui/scroll-area';
import {
  CalendarDays, Clock, School, Users, BookOpen,
  Sliders, Plus, Edit2, Trash2, Save, CheckCircle2,
  Info, X, GraduationCap, Shield, Building2, MapPin, Phone, Mail,
  Layers, Zap, Lock, Calendar, Timer, Coffee, Moon, UserX, DoorClosed,
  RefreshCw, Wand2, Database, FileSpreadsheet, Upload, AlertTriangle,
  CheckCheck
} from 'lucide-react';
import { DndContext, DragOverlay, closestCenter } from '@dnd-kit/core';
import {
  DraggableClassItem,
  DroppableTeacherBox,
  DraggableSubjectItem,
  DroppableTeacherSubjectBox,
} from './DndComponents';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';
import { getApiErrorMessage } from '../../utils/apiError';
import { SubjectsManager } from '../subjects/SubjectsManager';

export function DynamicSettingsContent({ hook, dynamicTabs }) {
  const { t } = useTranslation();
  const { isRTL, direction } = useTheme();
  const {
    activeTab, setActiveTab, saving, sensors,
    schoolInfo, teachers, classes, assignments,
    subjects, draggingSubject, setDraggingSubject,
    assignmentSubTab, setAssignmentSubTab,
    classAssignments, classAssignmentsLoading, classAssignmentsLoaded, classAssignmentsError, loadClassAssignments, draggingClass, setDraggingClass,
    editedSchoolInfo, setEditedSchoolInfo,
    workDays, timingSettings, timeSlotsCount, generatingSlots,
    breakTimes, teacherUnavailability, classUnavailability,
    hardConstraints, softConstraints, activeHardTab, setActiveHardTab, activeSoftTab, setActiveSoftTab,
    customSoftConstraints, constraintPatterns, otherDuties, workloadSummary, workloadLoading,
    showAddConstraintModal, setShowAddConstraintModal, showAddDutyModal, setShowAddDutyModal,
    saveAllSettings, saveSchoolInfo, generateTimeSlots,
    getTeacherAssignments, removeAssignment, deleteClass,
    handleSettingChange, handleWorkDayChange,
    handleHardConstraintToggle,
    handleSoftConstraintToggle, handleSoftConstraintWeight, toggleAllConstraints,
    handleSoftConstraintTargetSubjects,
    handleAddCustomConstraint, handleUpdateCustomConstraint, handleDeleteCustomConstraint, handleToggleCustomConstraint,
    handleAddConstraintPattern,
    handleAddOtherDuty, handleUpdateOtherDuty, handleDeleteOtherDuty,
    fetchWorkloadSummary, handleWorkloadOverride,
    handleAddBreak, handleEditBreak, handleDeleteBreak,
    handleAddUnavailability, handleDeleteUnavailability,
    handleCreateClassAssignment, handleDeleteClassAssignment,
    subjectPickerRequest, subjectPickerSaving, cancelSubjectPicker, confirmSubjectPicker,
    nassaqWarning, nassaqError, user, api, setAssignments, handleOpenNoorImport,
  } = hook;

  return (
    <div className="space-y-6">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        {/* لا نُظهر شريط التبويبات الفرعي إذا كان هناك تبويب واحد فقط
            (مثل صفحة "بيانات المدرسة")؛ يبقى الـ TabsList كما هو في
            صفحات إعدادات الجدول التي تستخدم نفس المكوّن مع تبويبات متعدّدة. */}
        {dynamicTabs.length > 1 && (
          <TabsList className="w-full h-auto bg-white rounded-2xl p-1.5 shadow-sm border border-slate-200 mb-6 flex flex-row gap-0.5">
            {dynamicTabs.map((tab) => (
              <TabsTrigger
                key={tab.id}
                value={tab.id}
                className="flex-1 min-w-0 rounded-xl text-[9px] sm:text-[10px] py-2.5 px-0.5 data-[state=active]:bg-[#1C3D74] data-[state=active]:text-white data-[state=active]:shadow-md transition-all flex flex-col items-center gap-1 text-slate-500 hover:text-slate-700"
                data-testid={`tab-${tab.id}`}
              >
                <tab.icon className="h-3.5 w-3.5 sm:h-4 sm:w-4 flex-shrink-0" />
                <span className="truncate w-full text-center leading-tight">{tab.label}</span>
              </TabsTrigger>
            ))}
          </TabsList>
        )}

        <TabsContent value="school-info" className="space-y-6">
          <Card className="bg-white shadow-sm border-[#1C3D74]/20">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-[#1C3D74] flex items-center justify-center">
                    <Building2 className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <CardTitle className="text-lg text-[#1C3D74]">{t('schoolBasicData')}</CardTitle>
                    <CardDescription>{t('schoolBasicDataDesc')}</CardDescription>
                  </div>
                </div>
                {schoolInfo.license_number && (
                  <Badge className="bg-slate-100 text-slate-600 border border-slate-300 gap-1 text-sm px-3 py-1">
                    <Shield className="h-3 w-3" />
                    {t('schoolCode')}: {schoolInfo.license_number}
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="font-semibold text-slate-700 flex items-center gap-1">
                    <Building2 className="h-3.5 w-3.5 text-[#1C3D74]" />
                    {t('schoolNameAr')} <span className="text-red-500">*</span>
                  </Label>
                  <Input
                    dir={direction}
                    className="h-11 border-slate-200 focus:border-[#1C3D74] text-right"
                    value={editedSchoolInfo.name_ar || ''}
                    onChange={e => setEditedSchoolInfo(p => ({ ...p, name_ar: e.target.value }))}
                    placeholder={t('schoolNameArPlaceholder')}
                    data-testid="school-name-ar-input"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="font-semibold text-slate-700">{t('schoolTypeLabel')}</Label>
                  <Select
                    value={(() => {
                      // Defensive hydration: the deprecated "خاصة" option
                      // (stored as "special" or "special_needs") was
                      // consolidated into the canonical "أهلية" option.
                      // Map any legacy stored value to the canonical
                      // option so the select doesn't render blank for a
                      // historical school during the rollout window.
                      const v = editedSchoolInfo.type || '';
                      if (v === 'special' || v === 'special_needs') return 'private';
                      return v;
                    })()}
                    onValueChange={v => setEditedSchoolInfo(p => ({ ...p, type: v }))}
                  >
                    <SelectTrigger className="h-11 border-slate-200" data-testid="school-type-select"><SelectValue placeholder={t('schoolTypePlaceholder')} /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="government">{t('schoolTypeGovernment')}</SelectItem>
                      <SelectItem value="private">{t('schoolTypePrivate')}</SelectItem>
                      <SelectItem value="international">{t('schoolTypeInternational')}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label className="font-semibold text-slate-700">{t('schoolStageLabel')}</Label>
                  <Select value={editedSchoolInfo.stage || ''} onValueChange={v => setEditedSchoolInfo(p => ({ ...p, stage: v, educational_pathway: v === 'secondary_pathways' ? p.educational_pathway : '' }))}>
                    <SelectTrigger className="h-11 border-slate-200" data-testid="school-stage-select"><SelectValue placeholder={t('schoolStagePlaceholder')} /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="primary">{t('stagePrimary')}</SelectItem>
                      <SelectItem value="intermediate">{t('stageIntermediate')}</SelectItem>
                      <SelectItem value="secondary_general">{t('stageSecondaryGeneral')}</SelectItem>
                      <SelectItem value="secondary_pathways">{t('stageSecondaryPathways')}</SelectItem>
                      <SelectItem value="school_complex">{t('stageSchoolComplex')}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {editedSchoolInfo.stage === 'secondary_pathways' && (
                <div className="space-y-2">
                  <Label className="font-semibold text-slate-700 flex items-center gap-1"><GraduationCap className="h-3.5 w-3.5 text-[#1C3D74]" />{t('educationalPathway')}</Label>
                  <Select value={editedSchoolInfo.educational_pathway || ''} onValueChange={v => setEditedSchoolInfo(p => ({ ...p, educational_pathway: v }))}>
                    <SelectTrigger className="h-11 border-slate-200" data-testid="school-pathway-select"><SelectValue placeholder={t('educationalPathwayPlaceholder')} /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="general">{t('pathwayGeneral')}</SelectItem>
                      <SelectItem value="cs_engineering">{t('pathwayCsEngineering')}</SelectItem>
                      <SelectItem value="health_life">{t('pathwayHealthLife')}</SelectItem>
                      <SelectItem value="business">{t('pathwayBusiness')}</SelectItem>
                      <SelectItem value="sharia">{t('pathwaySharia')}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="font-semibold text-slate-700 flex items-center gap-1"><MapPin className="h-3.5 w-3.5 text-[#1C3D74]" />{t('cityLabel')}</Label>
                  <Input dir={direction} className="h-11 border-slate-200 focus:border-[#1C3D74] text-right" value={editedSchoolInfo.city || ''} onChange={e => setEditedSchoolInfo(p => ({ ...p, city: e.target.value }))} placeholder={t('cityLabel')} data-testid="school-city-input" />
                </div>
                <div className="space-y-2">
                  <Label className="font-semibold text-slate-700 flex items-center gap-1"><MapPin className="h-3.5 w-3.5 text-[#1C3D74]" />{t('regionGovernorate')}</Label>
                  <Input dir={direction} className="h-11 border-slate-200 focus:border-[#1C3D74] text-right" value={editedSchoolInfo.region || ''} onChange={e => setEditedSchoolInfo(p => ({ ...p, region: e.target.value }))} placeholder={t('regionPlaceholder')} data-testid="school-region-input" />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="font-semibold text-slate-700 flex items-center gap-1"><Phone className="h-3.5 w-3.5 text-[#1C3D74]" />{t('principalMobileLabel')} <span className="text-red-500">*</span></Label>
                  <Input dir="ltr" type="tel" className="h-11 border-slate-200 focus:border-[#1C3D74]" value={editedSchoolInfo.principal_mobile || ''} onChange={e => setEditedSchoolInfo(p => ({ ...p, principal_mobile: e.target.value }))} placeholder="05XXXXXXXX" data-testid="school-principal-mobile-input" />
                </div>
                <div className="space-y-2">
                  <Label className="font-semibold text-slate-700 flex items-center gap-1"><Mail className="h-3.5 w-3.5 text-[#1C3D74]" />{t('emailLabel')}</Label>
                  <Input dir="ltr" type="email" className="h-11 border-slate-200 focus:border-[#1C3D74]" value={editedSchoolInfo.email || ''} onChange={e => setEditedSchoolInfo(p => ({ ...p, email: e.target.value }))} placeholder="school@example.edu.sa" data-testid="school-email-input" />
                </div>
              </div>

              <div className="space-y-2">
                <Label className="font-semibold text-slate-700 flex items-center gap-1"><Users className="h-3.5 w-3.5 text-[#1C3D74]" />{t('principalNameLabel')}</Label>
                <Input dir={direction} className="h-11 border-slate-200 focus:border-[#1C3D74] text-right" value={editedSchoolInfo.principal_name || ''} onChange={e => setEditedSchoolInfo(p => ({ ...p, principal_name: e.target.value }))} placeholder={t('fullNamePlaceholder')} data-testid="school-principal-input" />
              </div>

              <div className="flex flex-wrap gap-3 pt-2 border-t border-slate-100">
                <div className="flex items-center gap-2 text-sm text-slate-500">
                  <Shield className="h-3.5 w-3.5" />
                  <span>{t('licenseCode')}</span>
                  <span className="font-mono font-semibold text-slate-700">{schoolInfo.license_number || '—'}</span>
                </div>
                <div className="flex items-center gap-2 text-sm text-slate-500">
                  <CheckCircle2 className={`h-3.5 w-3.5 ${schoolInfo.is_active ? 'text-emerald-500' : 'text-red-400'}`} />
                  <span>{t('statusColon')}</span>
                  <span className={`font-semibold ${schoolInfo.is_active ? 'text-emerald-600' : 'text-red-500'}`}>
                    {schoolInfo.is_active ? t('activeFem') : t('inactiveFem')}
                  </span>
                </div>
                {schoolInfo.updated_at && (
                  <div className="flex items-center gap-2 text-sm text-slate-500">
                    <RefreshCw className="h-3.5 w-3.5" />
                    <span>{t('lastUpdate')}</span>
                    <span className="text-slate-600">{new Date(schoolInfo.updated_at).toLocaleDateString(isRTL ? 'ar-SA' : 'en-US')}</span>
                  </div>
                )}
              </div>

              <div className="flex justify-end pt-2">
                <Button onClick={saveSchoolInfo} disabled={saving} className="bg-[#1C3D74] hover:bg-[#152d57] text-white px-8 h-11" data-testid="save-school-info-btn">
                  {saving ? <RefreshCw className="h-4 w-4 animate-spin me-2" /> : <Save className="h-4 w-4 me-2" />}
                  {t('saveSchoolInfoBtn')}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="timings" className="space-y-6">
          <Card className="bg-white shadow-sm">
            <CardHeader>
              <CardTitle className="text-xl flex items-center gap-2"><Clock className="h-5 w-5 text-[#1C3D74]" />إعدادات التوقيت والحصص</CardTitle>
              <CardDescription>حدد هيكل اليوم الدراسي وعدد الحصص</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <div>
                    <Label className="text-sm text-slate-600 mb-2 block flex items-center gap-1.5"><Clock className="h-3.5 w-3.5 text-[#1C3D74]" />وقت بداية اليوم الدراسي</Label>
                    <div className="flex items-center gap-2" data-testid="day-start-input">
                      <Select value={timingSettings.dayStart?.split(':')[0] || '07'} onValueChange={(h) => { const m = timingSettings.dayStart?.split(':')[1] || '00'; handleSettingChange('dayStart', `${h}:${m}`); }}>
                        <SelectTrigger className="h-12 w-24 text-lg font-bold text-center border-[#1C3D74]/30 focus:border-[#1C3D74]"><SelectValue /></SelectTrigger>
                        <SelectContent>{['05','06','07','08','09','10','11','12'].map(h => <SelectItem key={h} value={h} className="text-lg font-bold text-center">{h}</SelectItem>)}</SelectContent>
                      </Select>
                      <span className="text-2xl font-bold text-slate-400 select-none">:</span>
                      <Select value={timingSettings.dayStart?.split(':')[1] || '00'} onValueChange={(m) => { const h = timingSettings.dayStart?.split(':')[0] || '07'; handleSettingChange('dayStart', `${h}:${m}`); }}>
                        <SelectTrigger className="h-12 w-24 text-lg font-bold text-center border-[#1C3D74]/30 focus:border-[#1C3D74]"><SelectValue /></SelectTrigger>
                        <SelectContent>{['00','05','10','15','20','25','30','35','40','45','50','55'].map(m => <SelectItem key={m} value={m} className="text-lg font-bold text-center">{m}</SelectItem>)}</SelectContent>
                      </Select>
                      <span className="text-sm text-slate-500 mr-1">صباحاً</span>
                    </div>
                  </div>
                  <div>
                    <Label className="text-sm text-slate-600 mb-2 block">عدد الحصص في اليوم</Label>
                    <Select value={String(timingSettings.periodsPerDay)} onValueChange={(v) => handleSettingChange('periodsPerDay', parseInt(v))}>
                      <SelectTrigger className="h-12" data-testid="periods-per-day-select"><SelectValue /></SelectTrigger>
                      <SelectContent>{[5, 6, 7, 8, 9, 10].map(n => <SelectItem key={n} value={String(n)}>{n} حصص</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="space-y-4">
                  <div>
                    <Label className="text-sm text-slate-600 mb-2 block">مدة الحصة (بالدقائق)</Label>
                    <Select value={String(timingSettings.periodDuration)} onValueChange={(v) => handleSettingChange('periodDuration', parseInt(v))}>
                      <SelectTrigger className="h-12" data-testid="period-duration-select"><SelectValue /></SelectTrigger>
                      <SelectContent>{[30, 35, 40, 45, 50, 55, 60].map(n => <SelectItem key={n} value={String(n)}>{n} دقيقة</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-sm text-slate-600 mb-2 block">مدة الاستراحة الأساسية (بالدقائق)</Label>
                    <Select value={String(timingSettings.breakDuration)} onValueChange={(v) => handleSettingChange('breakDuration', parseInt(v))}>
                      <SelectTrigger className="h-12" data-testid="break-duration-select"><SelectValue /></SelectTrigger>
                      <SelectContent>{[10, 15, 20, 25, 30].map(n => <SelectItem key={n} value={String(n)}>{n} دقيقة</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-sm text-slate-600 mb-2 block">الحد الأقصى لحصص الانتظار للمعلم أسبوعياً</Label>
                    <input
                      type="number"
                      min={1}
                      max={20}
                      step={1}
                      value={timingSettings.maxStandbyPerWeek ?? 5}
                      onChange={(e) => {
                        const raw = parseInt(e.target.value, 10);
                        const clamped = Number.isFinite(raw)
                          ? Math.max(1, Math.min(20, raw))
                          : 5;
                        handleSettingChange('maxStandbyPerWeek', clamped);
                      }}
                      className="h-12 w-full rounded-md border border-slate-200 px-3 text-base focus:border-[#1C3D74] focus:outline-none"
                      data-testid="max-standby-per-week-input"
                    />
                    <p className="text-xs text-slate-500 mt-1">
                      الافتراضي: 5 — يطبّق كحد أعلى مع السعة المتبقية لكل معلم
                    </p>
                  </div>
                </div>
              </div>
              <div className="mt-6 p-4 bg-slate-50 rounded-xl">
                <h4 className="font-medium text-slate-700 mb-3">ملخص اليوم الدراسي</h4>
                <div className="grid grid-cols-4 gap-4">
                  <div className="text-center p-3 bg-white rounded-lg"><p className="text-sm text-slate-500">بداية اليوم</p><p className="text-xl font-bold text-[#1C3D74]">{timingSettings.dayStart}</p></div>
                  <div className="text-center p-3 bg-white rounded-lg"><p className="text-sm text-slate-500">عدد الحصص</p><p className="text-xl font-bold text-[#1C3D74]">{timingSettings.periodsPerDay}</p></div>
                  <div className="text-center p-3 bg-white rounded-lg"><p className="text-sm text-slate-500">مدة الحصة</p><p className="text-xl font-bold text-[#1C3D74]">{timingSettings.periodDuration} د</p></div>
                  <div className="text-center p-3 bg-white rounded-lg"><p className="text-sm text-slate-500">الاستراحة</p><p className="text-xl font-bold text-[#1C3D74]">{timingSettings.breakDuration} د</p></div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-white shadow-sm">
            <CardHeader>
              <CardTitle className="text-xl flex items-center gap-2"><Calendar className="h-5 w-5 text-[#1C3D74]" />أيام الدراسة</CardTitle>
              <CardDescription>حدد أيام الدوام الرسمية للمدرسة</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-7 gap-3">
                {[
                  { key: 'sunday', label: 'الأحد' },
                  { key: 'monday', label: 'الإثنين' },
                  { key: 'tuesday', label: 'الثلاثاء' },
                  { key: 'wednesday', label: 'الأربعاء' },
                  { key: 'thursday', label: 'الخميس' },
                  { key: 'friday', label: 'الجمعة' },
                  { key: 'saturday', label: 'السبت' },
                ].map(day => (
                  <div
                    key={day.key}
                    onClick={() => handleWorkDayChange(day.key)}
                    className={`cursor-pointer rounded-xl p-4 text-center transition-all duration-200 border-2 ${
                      workDays[day.key]
                        ? 'border-[#1C3D74] bg-[#1C3D74]/5 shadow-md'
                        : 'border-slate-200 hover:border-slate-300 bg-white'
                    }`}
                    data-testid={`work-day-${day.key}`}
                  >
                    <p className={`font-bold text-sm ${workDays[day.key] ? 'text-[#1C3D74]' : 'text-slate-500'}`}>{day.label}</p>
                    {workDays[day.key] && <CheckCircle2 className="h-4 w-4 mx-auto mt-2 text-[#1C3D74]" />}
                  </div>
                ))}
              </div>
              <p className="text-sm text-slate-500 mt-3">
                {Object.values(workDays).filter(Boolean).length > 0
                  ? `${Object.values(workDays).filter(Boolean).length} أيام دراسة محددة`
                  : 'لم يتم تحديد أيام الدراسة بعد'}
              </p>
            </CardContent>
          </Card>

          <Card className="bg-white shadow-sm">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-xl flex items-center gap-2"><Calendar className="h-5 w-5 text-[#1C3D74]" />نمط الدوام</CardTitle>
                  <CardDescription>اختر نمط الدوام المناسب للمدرسة</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4">
                {[
                  { value: 'summer', label: 'دوام صيفي', icon: '☀️' },
                  { value: 'winter', label: 'دوام شتوي', icon: '❄️' },
                  { value: 'ramadan', label: 'دوام رمضان', icon: '🌙' }
                ].map((pattern) => (
                  <div
                    key={pattern.value}
                    onClick={() => handleSettingChange('attendancePattern', pattern.value)}
                    className={`cursor-pointer rounded-xl p-4 text-center transition-all duration-200 border-2 ${
                      timingSettings.attendancePattern === pattern.value
                        ? 'border-[#1C3D74] bg-[#1C3D74]/5 shadow-md'
                        : 'border-slate-200 hover:border-slate-300 bg-white'
                    }`}
                    data-testid={`pattern-${pattern.value}`}
                  >
                    <span className="text-3xl mb-2 block">{pattern.icon}</span>
                    <p className={`font-bold text-sm ${timingSettings.attendancePattern === pattern.value ? 'text-[#1C3D74]' : 'text-slate-700'}`}>{pattern.label}</p>
                    {timingSettings.attendancePattern === pattern.value && <CheckCircle2 className="h-4 w-4 mx-auto mt-2 text-[#1C3D74]" />}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card className="bg-white shadow-sm">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-xl flex items-center gap-2"><Coffee className="h-5 w-5 text-[#1C3D74]" />فترات الاستراحة والصلاة</CardTitle>
                  <CardDescription>حدد أوقات الاستراحات وفترات الصلاة</CardDescription>
                </div>
                <Button variant="outline" className="gap-2" onClick={handleAddBreak} data-testid="add-break-btn"><Plus className="h-4 w-4" />إضافة فترة</Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {breakTimes.map((breakTime) => (
                  <div key={breakTime.id} className={`flex items-center justify-between p-4 rounded-xl border ${breakTime.type === 'prayer' ? 'bg-emerald-50 border-emerald-200' : breakTime.type === 'other' ? 'bg-blue-50 border-blue-200' : 'bg-amber-50 border-amber-200'}`}>
                    <div className="flex items-center gap-4">
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${breakTime.type === 'prayer' ? 'bg-emerald-500 text-white' : breakTime.type === 'other' ? 'bg-blue-500 text-white' : 'bg-amber-500 text-white'}`}>
                        {breakTime.type === 'prayer' ? <Moon className="h-5 w-5" /> : <Coffee className="h-5 w-5" />}
                      </div>
                      <div>
                        <p className="font-medium">{breakTime.name}</p>
                        <p className="text-sm text-slate-500">
                          بعد الحصة {breakTime.afterPeriod} • {breakTime.duration} دقيقة
                          {breakTime.day && breakTime.day !== 'all' && ` • ${breakTime.day}`}
                          {breakTime.day === 'all' && ' • جميع الأيام'}
                          {breakTime.type === 'other' && breakTime.customType && ` • ${breakTime.customType}`}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button variant="ghost" size="sm" onClick={() => handleEditBreak(breakTime)} data-testid={`edit-break-${breakTime.id}`}><Edit2 className="h-4 w-4" /></Button>
                      <Button variant="ghost" size="sm" className="text-red-500" onClick={() => handleDeleteBreak(breakTime.id)} data-testid={`delete-break-${breakTime.id}`}><Trash2 className="h-4 w-4" /></Button>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <div className="flex justify-end">
            <Button onClick={saveAllSettings} disabled={saving} className="bg-[#1C3D74] hover:bg-[#152d57] px-8" data-testid="save-timings-btn">
              <Save className="h-4 w-4 ml-2" />{saving ? 'جاري الحفظ...' : 'حفظ التغييرات'}
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="classes" className="space-y-6">
          <Card className="bg-white shadow-sm border-brand-navy/10">
            <CardHeader className="bg-gradient-to-l from-brand-navy/5 to-transparent">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-xl bg-brand-navy flex items-center justify-center"><School className="h-6 w-6 text-white" /></div>
                  <div>
                    <CardTitle className="text-xl text-brand-navy">الفصول الدراسية والشعب</CardTitle>
                    <CardDescription className="text-brand-navy/60">{classes.length} فصل مسجل في قاعدة البيانات</CardDescription>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    onClick={() => handleOpenNoorImport('noor_classes')}
                    className="bg-green-600 hover:bg-green-700 text-white gap-2 shadow-md"
                    size="sm"
                    data-testid="noor-import-classes-btn"
                  >
                    <FileSpreadsheet className="h-4 w-4" />
                    استيراد من نظام نور
                  </Button>
                  <Badge variant="outline" className="bg-brand-turquoise/10 text-brand-turquoise border-brand-turquoise/30"><Database className="h-3 w-3 ml-1" />بيانات من قاعدة البيانات</Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {classes.length === 0 ? (
                <div className="text-center py-12">
                  <School className="h-16 w-16 text-slate-200 mx-auto mb-4" />
                  <p className="text-lg text-slate-500 mb-2">لا يوجد فصول مسجلة</p>
                  <p className="text-sm text-slate-400">يمكنك إضافة الفصول من صفحة إدارة المستخدمين والفصول</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-slate-50">
                      <tr>
                        <th className="text-right py-3 px-4 text-sm font-semibold text-brand-navy">#</th>
                        <th className="text-right py-3 px-4 text-sm font-semibold text-brand-navy">اسم الفصل</th>
                        <th className="text-right py-3 px-4 text-sm font-semibold text-brand-navy">الصف</th>
                        <th className="text-right py-3 px-4 text-sm font-semibold text-brand-navy">الشعبة</th>
                        <th className="text-center py-3 px-4 text-sm font-semibold text-brand-navy">السعة</th>
                        <th className="text-center py-3 px-4 text-sm font-semibold text-brand-navy">الحالة</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {classes.map((cls, idx) => (
                        <tr key={cls.id || idx} className="hover:bg-brand-navy/5 transition-colors">
                          <td className="py-3 px-4 text-slate-500 text-sm">{idx + 1}</td>
                          <td className="py-3 px-4"><span className="font-medium text-slate-800">{cls.name || cls.name_ar || '-'}</span></td>
                          <td className="py-3 px-4 text-slate-600">{cls.grade_level || cls.grade || cls.grade_name || '-'}</td>
                          <td className="py-3 px-4 text-slate-600">{cls.section || '-'}</td>
                          <td className="py-3 px-4 text-center"><Badge variant="outline" className="bg-brand-navy/5 text-brand-navy border-brand-navy/20">{cls.capacity || 30} طالب</Badge></td>
                          <td className="py-3 px-4 text-center"><Badge className={cls.is_active !== false ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}>{cls.is_active !== false ? 'نشط' : 'غير نشط'}</Badge></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <div className="p-4 bg-amber-50 border-t border-amber-200">
                <div className="flex items-start gap-3">
                  <Info className="h-5 w-5 text-amber-600 mt-0.5 flex-shrink-0" />
                  <div><p className="text-sm text-amber-700">لإضافة أو تعديل الفصول، استخدم صفحة <span className="font-medium">إدارة المستخدمين والفصول</span> من القائمة الجانبية.</p></div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="subjects" className="space-y-6">
          <SubjectsManager embedded />
        </TabsContent>

        <TabsContent value="teacher-assignments" className="space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <button onClick={() => setAssignmentSubTab('subjects')} className={`p-4 rounded-xl border-2 transition-all ${assignmentSubTab === 'subjects' ? 'border-brand-purple bg-brand-purple/5 shadow-md' : 'border-slate-200 bg-white hover:border-slate-300'}`}>
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${assignmentSubTab === 'subjects' ? 'bg-brand-purple text-white' : 'bg-slate-100 text-slate-500'}`}><BookOpen className="h-5 w-5" /></div>
                <div className="text-right">
                  <h4 className={`font-bold ${assignmentSubTab === 'subjects' ? 'text-brand-purple' : 'text-slate-700'}`}>إسناد المواد</h4>
                  <p className="text-xs text-slate-500">{assignments.length} إسناد</p>
                </div>
              </div>
            </button>
            <button onClick={() => setAssignmentSubTab('classes')} className={`p-4 rounded-xl border-2 transition-all ${assignmentSubTab === 'classes' ? 'border-brand-turquoise bg-brand-turquoise/5 shadow-md' : 'border-slate-200 bg-white hover:border-slate-300'}`}>
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${assignmentSubTab === 'classes' ? 'bg-brand-turquoise text-white' : 'bg-slate-100 text-slate-500'}`}><GraduationCap className="h-5 w-5" /></div>
                <div className="text-right">
                  <h4 className={`font-bold ${assignmentSubTab === 'classes' ? 'text-brand-turquoise-dark' : 'text-slate-700'}`}>إسناد الفصول</h4>
                  {classAssignmentsError && !classAssignmentsLoaded ? (
                    <p className="text-xs text-red-500">تعذّر التحميل — أعد المحاولة</p>
                  ) : !classAssignmentsLoaded ? (
                    <p className="text-xs text-slate-500 flex items-center gap-1.5">
                      <span className="inline-block w-3 h-3 rounded-full border-2 border-slate-300 border-t-brand-turquoise animate-spin" />
                      جارٍ التحميل…
                    </p>
                  ) : (
                    <p className="text-xs text-slate-500">{classAssignments.length} إسناد</p>
                  )}
                </div>
              </div>
            </button>
          </div>

          {assignmentSubTab === 'subjects' && (
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragStart={(e) => setDraggingSubject(e.active?.data?.current?.subject || null)}
              onDragEnd={(e) => {
                setDraggingSubject(null);
                const subject = e.active?.data?.current?.subject;
                const teacher = e.over?.data?.current?.teacher;
                if (subject && teacher) {
                  const existingAssignment = assignments.find(a => a.teacher_id === teacher.id && a.subject_id === subject.id);
                  if (existingAssignment) {
                    nassaqWarning('هذه المادة مسندة بالفعل لهذا المعلم');
                  } else {
                    const tempId = `temp-${Date.now()}`;
                    const optimistic = { id: tempId, teacher_id: teacher.id, subject_id: subject.id, subject_name: subject.name_ar, school_id: user?.tenant_id || '', _optimistic: true };
                    setAssignments(prev => [...prev, optimistic]);
                    const schoolId = user?.tenant_id || user?.school_id || 'SCH-001';
                    api.post('/teacher-assignments', { teacher_id: teacher.id, subject_id: subject.id, school_id: schoolId })
                      .then(res => { const realId = res.data?.assignment?.id || res.data?.id || res.data?.assignment_id || tempId; setAssignments(prev => prev.map(a => a.id === tempId ? { ...a, id: realId, _optimistic: false } : a)); })
                      .catch(err => {
                        setAssignments(prev => prev.filter(a => a.id !== tempId));
                        const msg = getApiErrorMessage(err) || err?.response?.data?.error?.message || err?.message || 'تعذّر إسناد المادة للمعلم';
                        nassaqError(msg);
                      });
                  }
                }
              }}
            >
              <Card className="bg-gradient-to-l from-brand-purple/10 to-brand-purple/5 border-brand-purple/20">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-brand-purple flex items-center justify-center"><BookOpen className="h-5 w-5 text-white" /></div>
                      <div>
                        <h3 className="text-lg font-bold text-brand-purple">ربط المعلمين بالمواد</h3>
                        <p className="text-xs text-brand-purple/60">{teachers.length} معلم • {subjects.length} مادة • {assignments.length} إسناد</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        onClick={() => handleOpenNoorImport('noor_assignments')}
                        className="bg-green-600 hover:bg-green-700 text-white gap-2 shadow-md"
                        size="sm"
                        data-testid="noor-import-assignments-btn"
                      >
                        <FileSpreadsheet className="h-3.5 w-3.5" />
                        استيراد من نظام نور
                      </Button>
                      <Badge variant="outline" className="bg-brand-purple/10 text-brand-purple border-brand-purple/30 text-xs"><Zap className="h-3 w-3 ml-1" />سحب وإفلات</Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <div className="p-3 bg-blue-50 rounded-xl border border-blue-200">
                <div className="flex items-start gap-2">
                  <Info className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
                  <p className="text-xs text-blue-700">اسحب أي مادة من قائمة المواد على اليسار وأفلتها داخل صندوق المعلم المطلوب لإسنادها له. يمكنك إسناد نفس المادة لأكثر من معلم. يتم الحفظ تلقائياً.</p>
                </div>
              </div>

              <div className="grid lg:grid-cols-5 gap-4">
                <div className="lg:col-span-2">
                  <Card className="bg-white shadow-sm h-full">
                    <CardHeader className="pb-2"><CardTitle className="text-base flex items-center gap-2 text-brand-purple"><BookOpen className="h-4 w-4" />المواد الدراسية<Badge variant="outline" className="text-xs">{subjects.length}</Badge></CardTitle></CardHeader>
                    <CardContent>
                      <ScrollArea className="h-[420px] pr-2">
                        <div className="space-y-2">
                          {subjects.map((subject) => {
                            const assignedCount = assignments.filter(a => a.subject_id === subject.id).length;
                            return <DraggableSubjectItem key={subject.id} subject={subject} assignedCount={assignedCount} />;
                          })}
                        </div>
                      </ScrollArea>
                    </CardContent>
                  </Card>
                </div>
                <div className="lg:col-span-3">
                  <Card className="bg-white shadow-sm h-full">
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-base flex items-center gap-2 text-brand-navy"><Users className="h-4 w-4" />المعلمون<Badge variant="outline" className="text-xs">{teachers.length}</Badge></CardTitle>
                        {assignments.length > 0 && <Badge variant="outline" className="text-brand-purple border-brand-purple/30">{assignments.length} إسناد</Badge>}
                      </div>
                    </CardHeader>
                    <CardContent>
                      <ScrollArea className="h-[420px] pr-2">
                        {teachers.length === 0 ? (
                          <div className="text-center py-12"><Users className="h-16 w-16 text-slate-200 mx-auto mb-4" /><p className="text-slate-500">لا يوجد معلمين مسجلين</p></div>
                        ) : (
                          <div className="grid grid-cols-2 gap-3">
                            {teachers.map((teacher) => {
                              const teacherAssignments = getTeacherAssignments(teacher.id);
                              return <DroppableTeacherSubjectBox key={teacher.id} teacher={teacher} assignments={teacherAssignments} onRemoveAssignment={removeAssignment} />;
                            })}
                          </div>
                        )}
                      </ScrollArea>
                    </CardContent>
                  </Card>
                </div>
              </div>
              <DragOverlay>
                {draggingSubject ? (
                  <div className="p-3 rounded-xl border-2 border-brand-purple bg-brand-purple text-white shadow-2xl opacity-95 min-w-[140px]">
                    <div className="flex items-center gap-2"><BookOpen className="h-4 w-4 text-white shrink-0" /><span className="text-sm font-bold truncate">{draggingSubject.name_ar}</span></div>
                  </div>
                ) : null}
              </DragOverlay>
            </DndContext>
          )}

          {assignmentSubTab === 'classes' && (
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragStart={(e) => setDraggingClass(e.active?.data?.current?.classItem || null)}
              onDragEnd={(e) => {
                setDraggingClass(null);
                const classItem = e.active?.data?.current?.classItem;
                const teacher = e.over?.data?.current?.teacher;
                if (classItem && teacher) {
                  const exists = classAssignments.some(a => a.class_id === classItem.id && a.teacher_id === teacher.id);
                  if (!exists) { handleCreateClassAssignment(teacher.id, classItem.id); }
                  else { nassaqWarning('هذا الفصل مسند بالفعل لهذا المعلم'); }
                }
              }}
            >
              <Card className="bg-gradient-to-l from-brand-turquoise/10 to-brand-turquoise/5 border-brand-turquoise/20">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-brand-turquoise flex items-center justify-center"><GraduationCap className="h-5 w-5 text-white" /></div>
                      <div>
                        <h3 className="text-lg font-bold text-brand-turquoise-dark">ربط المعلمين بالفصول</h3>
                        {classAssignmentsError && !classAssignmentsLoaded ? (
                          <p className="text-xs text-red-600 flex items-center gap-2">
                            <span>{teachers.length} معلم • {classes.length} فصل • تعذّر تحميل الإسنادات</span>
                            <button
                              type="button"
                              onClick={() => loadClassAssignments()}
                              className="underline text-red-700 hover:text-red-800"
                            >
                              إعادة المحاولة
                            </button>
                          </p>
                        ) : !classAssignmentsLoaded ? (
                          <p className="text-xs text-slate-600 flex items-center gap-1.5">
                            <span>{teachers.length} معلم • {classes.length} فصل •</span>
                            <span className="inline-block w-3 h-3 rounded-full border-2 border-slate-300 border-t-brand-turquoise animate-spin" />
                            <span>جارٍ تحميل الإسنادات…</span>
                          </p>
                        ) : (
                          <p className="text-xs text-slate-600">{teachers.length} معلم • {classes.length} فصل • {classAssignments.length} إسناد</p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        onClick={() => handleOpenNoorImport('noor_assignments')}
                        className="bg-green-600 hover:bg-green-700 text-white gap-2 shadow-md"
                        size="sm"
                      >
                        <FileSpreadsheet className="h-3.5 w-3.5" />
                        استيراد من نظام نور
                      </Button>
                      <Badge variant="outline" className="bg-brand-turquoise/10 text-brand-turquoise-dark border-brand-turquoise/30 text-xs"><Zap className="h-3 w-3 ml-1" />سحب وإفلات</Badge>
                    </div>
                  </div>
                  <div className="mt-3 bg-blue-50 border border-blue-200 rounded-lg px-3 py-2 text-xs text-blue-700">
                    <span className="font-bold">الإعداد الافتراضي:</span> جميع المعلمين مرتبطون بجميع الفصول تلقائيًا. يمكنك إزالة فصل من كارت المعلم لإلغاء الربط.
                  </div>
                </CardContent>
              </Card>

              <div className="p-3 bg-blue-50 rounded-xl border border-blue-200">
                <div className="flex items-start gap-2">
                  <Info className="h-4 w-4 text-blue-600 mt-0.5 flex-shrink-0" />
                  <p className="text-xs text-blue-700">اسحب أي فصل من قائمة الفصول على اليسار وأفلته داخل صندوق المعلم المطلوب لإسناده له. يتم الحفظ تلقائياً في قاعدة البيانات ويُستخدم في توليد الجدول.</p>
                </div>
              </div>

              <div className="grid lg:grid-cols-5 gap-4">
                <div className="lg:col-span-2">
                  <Card className="bg-white shadow-sm h-full">
                    <CardHeader className="pb-2"><CardTitle className="text-base flex items-center gap-2"><GraduationCap className="h-4 w-4 text-brand-turquoise" />الفصول الدراسية<Badge variant="outline" className="text-xs">{classes.length}</Badge></CardTitle></CardHeader>
                    <CardContent>
                      <ScrollArea className="h-[400px] pr-2">
                        <div className="space-y-2">
                          {classes.map((classItem) => {
                            const hasAssignment = classAssignments.some(a => a.class_id === classItem.id);
                            return <DraggableClassItem key={classItem.id} classItem={classItem} isAssigned={hasAssignment} assignedTeacher={classAssignments.find(a => a.class_id === classItem.id)?.teacher_name} />;
                          })}
                        </div>
                      </ScrollArea>
                    </CardContent>
                  </Card>
                </div>
                <div className="lg:col-span-3">
                  <Card className="bg-white shadow-sm h-full">
                    <CardHeader className="pb-2"><CardTitle className="text-base flex items-center gap-2"><Users className="h-4 w-4 text-brand-navy" />المعلمون<Badge variant="outline" className="text-xs">{teachers.length}</Badge></CardTitle></CardHeader>
                    <CardContent>
                      <ScrollArea className="h-[400px] pr-2">
                        <div className="grid grid-cols-2 gap-3">
                          {teachers.map((teacher) => {
                            const teacherClassAssignments = classAssignments.filter(a => a.teacher_id === teacher.id);
                            return <DroppableTeacherBox key={teacher.id} teacher={teacher} assignments={teacherClassAssignments} onRemoveAssignment={handleDeleteClassAssignment} />;
                          })}
                        </div>
                      </ScrollArea>
                    </CardContent>
                  </Card>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div className="p-3 bg-green-50 rounded-xl border border-green-200 text-center"><p className="text-2xl font-bold text-green-700">{new Set(classAssignments.map(a => a.class_id)).size}</p><p className="text-xs text-green-600">فصول مسندة</p></div>
                <div className="p-3 bg-amber-50 rounded-xl border border-amber-200 text-center"><p className="text-2xl font-bold text-amber-700">{classes.length - new Set(classAssignments.map(a => a.class_id)).size}</p><p className="text-xs text-amber-600">بدون إسناد</p></div>
                <div className="p-3 bg-blue-50 rounded-xl border border-blue-200 text-center"><p className="text-2xl font-bold text-blue-700">{classAssignments.length}</p><p className="text-xs text-blue-600">إجمالي الإسنادات</p></div>
              </div>

              <DragOverlay>
                {draggingClass && (
                  <div className="p-3 rounded-lg border-2 border-brand-turquoise bg-white shadow-xl">
                    <div className="flex items-center gap-2"><GraduationCap className="h-5 w-5 text-brand-turquoise" /><div><p className="font-medium text-sm">{draggingClass.name}</p><p className="text-xs text-muted-foreground">{draggingClass.section}</p></div></div>
                  </div>
                )}
              </DragOverlay>
            </DndContext>
          )}
        </TabsContent>

        <TabsContent value="unavailability" className="space-y-6">
          <div className="grid md:grid-cols-2 gap-6">
            <Card className="bg-white shadow-sm">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-lg flex items-center gap-2"><UserX className="h-5 w-5 text-amber-600" />عدم توفر المعلمين</CardTitle>
                    <CardDescription>حدد أوقات عدم توفر المعلمين</CardDescription>
                  </div>
                  <Button variant="outline" size="sm" className="gap-1" onClick={() => handleAddUnavailability('teacher')} data-testid="add-teacher-unavailability-btn"><Plus className="h-4 w-4" />إضافة</Button>
                </div>
              </CardHeader>
              <CardContent>
                {teacherUnavailability.length === 0 ? (
                  <div className="text-center py-8 text-slate-400"><UserX className="h-10 w-10 mx-auto mb-2 opacity-50" /><p className="text-sm">لا يوجد قيود على توفر المعلمين</p></div>
                ) : (
                  <div className="space-y-2">
                    {teacherUnavailability.map((item) => (
                      <div key={item.id} className={`flex items-center justify-between p-3 rounded-lg border ${item.unavailability_type === 'long_term' ? 'bg-orange-50 border-orange-200' : 'bg-amber-50 border-amber-200'}`}>
                        <div className="flex items-center gap-2">
                          {item.unavailability_type === 'long_term' ? (
                            <Calendar className="h-4 w-4 text-orange-500 flex-shrink-0" />
                          ) : (
                            <Clock className="h-4 w-4 text-amber-500 flex-shrink-0" />
                          )}
                          <div>
                            <span className="text-sm font-medium">{item.teacher_name || item.entity_name}</span>
                            {item.unavailability_type === 'long_term' ? (
                              <p className="text-xs text-orange-600">فترة طويلة: {item.start_date} إلى {item.end_date}{item.reason ? ` (${item.reason})` : ''}</p>
                            ) : (
                              <p className="text-xs text-amber-600">متكرر: {item.day} - الحصة {item.period}</p>
                            )}
                          </div>
                        </div>
                        <Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-red-500" onClick={() => handleDeleteUnavailability(item.id, 'teacher')}><X className="h-3 w-3" /></Button>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
            <Card className="bg-white shadow-sm">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-lg flex items-center gap-2"><DoorClosed className="h-5 w-5 text-red-600" />عدم توفر الفصول</CardTitle>
                    <CardDescription>حدد أوقات عدم توفر الفصول</CardDescription>
                  </div>
                  <Button variant="outline" size="sm" className="gap-1" onClick={() => handleAddUnavailability('class')} data-testid="add-class-unavailability-btn"><Plus className="h-4 w-4" />إضافة</Button>
                </div>
              </CardHeader>
              <CardContent>
                {classUnavailability.length === 0 ? (
                  <div className="text-center py-8 text-slate-400"><DoorClosed className="h-10 w-10 mx-auto mb-2 opacity-50" /><p className="text-sm">لا يوجد قيود على توفر الفصول</p></div>
                ) : (
                  <div className="space-y-2">
                    {classUnavailability.map((item) => (
                      <div key={item.id} className={`flex items-center justify-between p-3 rounded-lg border ${item.unavailability_type === 'long_term' ? 'bg-rose-50 border-rose-300' : 'bg-red-50 border-red-200'}`}>
                        <div className="flex items-center gap-2">
                          {item.unavailability_type === 'long_term' ? (
                            <AlertTriangle className="h-4 w-4 text-rose-500 flex-shrink-0" />
                          ) : (
                            <DoorClosed className="h-4 w-4 text-red-500 flex-shrink-0" />
                          )}
                          <div>
                            <span className="text-sm font-medium">{item.class_name || item.entity_name}</span>
                            {item.unavailability_type === 'long_term' ? (
                              <p className="text-xs text-rose-600">فترة طويلة: {item.start_date} إلى {item.end_date}{item.reason ? ` (${item.reason})` : ''}</p>
                            ) : (
                              <p className="text-xs text-red-600">متكرر: {item.day} - الحصة {item.period}</p>
                            )}
                            {item.alternative_location && (
                              <p className="text-xs text-orange-700 font-semibold">نُقل إلى: {item.alternative_location}</p>
                            )}
                            {item.alternative_location && (item.recipient_count ?? 0) > 0 && (
                              // لوحة تدقيق سريعة: تُظهر للمدير كم معلماً
                              // سجّل اطلاعه على نقل الفصل من أصل عدد
                              // المستلمين. تختفي للسجلات بدون موقع بديل
                              // لأن لا يلزم تأكيد استلام لها.
                              <div className="mt-1 flex items-center gap-1.5">
                                <Badge
                                  variant="outline"
                                  className={`gap-1 text-[10px] border ${
                                    item.acknowledged_count >= item.recipient_count
                                      ? 'bg-emerald-50 text-emerald-700 border-emerald-300'
                                      : 'bg-amber-50 text-amber-700 border-amber-300'
                                  }`}
                                  data-testid={`unavail-ack-badge-${item.id}`}
                                >
                                  <CheckCheck className="h-3 w-3" />
                                  تم الاطلاع: {item.acknowledged_count || 0} / {item.recipient_count}
                                </Badge>
                              </div>
                            )}
                          </div>
                        </div>
                        <Button variant="ghost" size="sm" className="h-6 w-6 p-0 text-red-500" onClick={() => handleDeleteUnavailability(item.id, 'class')}><X className="h-3 w-3" /></Button>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="constraints" className="space-y-0">
          <ConstraintsPanel
            hardConstraints={hardConstraints}
            softConstraints={softConstraints}
            customSoftConstraints={customSoftConstraints}
            constraintPatterns={constraintPatterns}
            subjects={subjects}
            teachers={teachers}
            otherDuties={otherDuties}
            workloadSummary={workloadSummary}
            workloadLoading={workloadLoading}
            activeHardTab={activeHardTab}
            setActiveHardTab={setActiveHardTab}
            activeSoftTab={activeSoftTab}
            setActiveSoftTab={setActiveSoftTab}
            showAddConstraintModal={showAddConstraintModal}
            setShowAddConstraintModal={setShowAddConstraintModal}
            showAddDutyModal={showAddDutyModal}
            setShowAddDutyModal={setShowAddDutyModal}
            handleHardConstraintToggle={handleHardConstraintToggle}
            handleSoftConstraintToggle={handleSoftConstraintToggle}
            handleSoftConstraintWeight={handleSoftConstraintWeight}
            toggleAllConstraints={toggleAllConstraints}
            handleSoftConstraintTargetSubjects={handleSoftConstraintTargetSubjects}
            handleAddCustomConstraint={handleAddCustomConstraint}
            handleDeleteCustomConstraint={handleDeleteCustomConstraint}
            handleToggleCustomConstraint={handleToggleCustomConstraint}
            handleUpdateCustomConstraint={handleUpdateCustomConstraint}
            handleAddConstraintPattern={handleAddConstraintPattern}
            handleAddOtherDuty={handleAddOtherDuty}
            handleUpdateOtherDuty={handleUpdateOtherDuty}
            handleDeleteOtherDuty={handleDeleteOtherDuty}
            fetchWorkloadSummary={fetchWorkloadSummary}
            handleWorkloadOverride={handleWorkloadOverride}
          />
        </TabsContent>
      </Tabs>

      <ClassAssignmentSubjectPicker
        request={subjectPickerRequest}
        saving={subjectPickerSaving}
        onCancel={cancelSubjectPicker}
        onConfirm={confirmSubjectPicker}
      />
    </div>
  );
}

/**
 * حوار اختيار المادة عند تعذّر تحديدها تلقائيًا لزوج (معلم، فصل).
 * يظهر فقط عندما يرجع الخادم 409 subject_required ومعه قائمة مواد مرشّحة،
 * فيكمل المدير الإسناد من مكانه بدل الانتقال إلى تبويب آخر.
 */
function ClassAssignmentSubjectPicker({ request, saving, onCancel, onConfirm }) {
  const [selected, setSelected] = React.useState('');

  React.useEffect(() => {
    setSelected(request?.candidates?.length === 1 ? request.candidates[0].id : '');
  }, [request]);

  if (!request) return null;

  return (
    <div className="fixed inset-0 z-[60] bg-black/50 flex items-center justify-center p-4" dir="rtl">
      <div className="bg-white rounded-2xl w-full max-w-md shadow-2xl overflow-hidden" data-testid="subject-picker-dialog">
        <div className="p-5 border-b">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center shrink-0">
              <BookOpen className="h-5 w-5 text-amber-600" />
            </div>
            <div>
              <h3 className="font-bold text-brand-navy">اختر المادة لهذا الإسناد</h3>
              <p className="text-xs text-slate-500 mt-1">
                {request.teacherName || 'المعلم'} • {request.className || 'الفصل'}
              </p>
            </div>
          </div>
          {request.message && <p className="text-xs text-slate-600 mt-3">{request.message}</p>}
        </div>
        <div className="p-5 max-h-[320px] overflow-y-auto space-y-2">
          {request.candidates.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => setSelected(c.id)}
              data-testid={`subject-candidate-${c.id}`}
              className={`w-full text-right px-4 py-3 rounded-xl border-2 transition-all ${selected === c.id ? 'border-brand-turquoise bg-brand-turquoise/5 font-bold text-brand-turquoise-dark' : 'border-slate-200 hover:border-slate-300 text-slate-700'}`}
            >
              {c.name}
            </button>
          ))}
        </div>
        <div className="p-5 border-t flex justify-end gap-3">
          <button onClick={onCancel} disabled={saving} className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-all disabled:opacity-50">إلغاء</button>
          <button
            onClick={() => onConfirm(selected)}
            disabled={!selected || saving}
            data-testid="subject-picker-confirm"
            className="px-5 py-2 text-sm bg-brand-turquoise text-white rounded-lg hover:bg-brand-turquoise-dark transition-all disabled:opacity-50"
          >
            {saving ? 'جاري الإسناد...' : 'إسناد الفصل'}
          </button>
        </div>
      </div>
    </div>
  );
}

function SubjectMultiSelect({ subjects, selectedIds, onChange }) {
  const [open, setOpen] = React.useState(false);
  const selected = selectedIds || [];

  const toggle = (id) => {
    const newSelected = selected.includes(id) ? selected.filter(x => x !== id) : [...selected, id];
    onChange(newSelected);
  };

  const label = selected.length === 0
    ? 'جميع المواد (افتراضي)'
    : selected.length === 1
      ? (subjects.find(s => s.id === selected[0])?.name_ar || selected[0])
      : `${selected.length} مواد مختارة`;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-[10px] px-2 py-1 rounded-md border border-slate-200 bg-white text-slate-600 hover:border-amber-300 hover:text-amber-700 transition-all max-w-[180px] truncate"
      >
        <BookOpen className="h-3 w-3 flex-shrink-0" />
        <span className="truncate">{label}</span>
      </button>
      {open && (
        <div className="absolute top-full mt-1 right-0 z-50 bg-white border border-slate-200 rounded-xl shadow-lg w-52 max-h-48 overflow-y-auto p-1.5">
          <div
            className={`flex items-center gap-2 px-2 py-1.5 rounded-lg cursor-pointer text-[11px] transition-all ${selected.length === 0 ? 'bg-amber-50 text-amber-700 font-medium' : 'hover:bg-slate-50 text-slate-600'}`}
            onClick={() => { onChange([]); setOpen(false); }}
          >
            <CheckCircle2 className={`h-3 w-3 ${selected.length === 0 ? 'text-amber-500' : 'text-transparent'}`} />
            جميع المواد (بدون تحديد)
          </div>
          {subjects.map(s => (
            <div
              key={s.id}
              className={`flex items-center gap-2 px-2 py-1.5 rounded-lg cursor-pointer text-[11px] transition-all ${selected.includes(s.id) ? 'bg-amber-50 text-amber-700 font-medium' : 'hover:bg-slate-50 text-slate-600'}`}
              onClick={() => toggle(s.id)}
            >
              <CheckCircle2 className={`h-3 w-3 flex-shrink-0 ${selected.includes(s.id) ? 'text-amber-500' : 'text-transparent'}`} />
              <span className="truncate">{s.name_ar || s.name}</span>
            </div>
          ))}
        </div>
      )}
      {open && <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />}
    </div>
  );
}

function ConstraintsPanel({
  hardConstraints, softConstraints, customSoftConstraints = [], constraintPatterns = {}, subjects = [],
  teachers = [], otherDuties = [], workloadSummary = [], workloadLoading = false,
  activeHardTab, setActiveHardTab, activeSoftTab, setActiveSoftTab,
  showAddConstraintModal, setShowAddConstraintModal, showAddDutyModal, setShowAddDutyModal,
  handleHardConstraintToggle,
  handleSoftConstraintToggle, handleSoftConstraintWeight, toggleAllConstraints,
  handleSoftConstraintTargetSubjects, handleAddCustomConstraint, handleUpdateCustomConstraint,
  handleDeleteCustomConstraint, handleToggleCustomConstraint, handleAddConstraintPattern,
  handleAddOtherDuty, handleUpdateOtherDuty, handleDeleteOtherDuty, fetchWorkloadSummary, handleWorkloadOverride,
}) {
  const [activePanel, setActivePanel] = React.useState('soft');
  const [workloadLoaded, setWorkloadLoaded] = React.useState(false);
  const [editingConstraint, setEditingConstraint] = React.useState(null);
  const [editingDuty, setEditingDuty] = React.useState(null);

  React.useEffect(() => {
    if (activePanel === 'workload' && !workloadLoaded) {
      setWorkloadLoaded(true);
      fetchWorkloadSummary();
    }
  }, [activePanel]); // eslint-disable-line react-hooks/exhaustive-deps

  const hardCategoryLabels = {
    all: { label: 'الكل', color: 'red' }, resource_conflict: { label: 'تعارض الموارد', color: 'red' },
    time_boundary: { label: 'حدود الوقت', color: 'orange' }, capacity: { label: 'السعة', color: 'blue' },
    workload: { label: 'نصاب العمل', color: 'purple' }, curriculum: { label: 'المنهج', color: 'green' },
    distribution: { label: 'التوزيع', color: 'teal' }, assignment: { label: 'الإسناد', color: 'indigo' },
    completeness: { label: 'الاكتمال', color: 'emerald' }, data_integrity: { label: 'صحة البيانات', color: 'slate' },
    publishing: { label: 'النشر', color: 'amber' }
  };
  const hardGrouped = {};
  hardConstraints.forEach(c => { const cat = c.category || 'other'; if (!hardGrouped[cat]) hardGrouped[cat] = []; hardGrouped[cat].push(c); });
  const hardCats = Object.keys(hardGrouped);
  const filteredHard = activeHardTab === 'all' ? hardConstraints : (hardGrouped[activeHardTab] || []);

  const softCategoryLabels = {
    all: { label: 'الكل', color: 'amber' }, distribution: { label: 'توزيع الحصص', color: 'teal' },
    teacher_comfort: { label: 'راحة المعلم', color: 'blue' }, pedagogy: { label: 'الجانب التربوي', color: 'purple' },
    fairness: { label: 'العدالة', color: 'green' }
  };
  const softGrouped = {};
  softConstraints.forEach(c => { const cat = c.category || 'other'; if (!softGrouped[cat]) softGrouped[cat] = []; softGrouped[cat].push(c); });
  const softCats = Object.keys(softGrouped);
  const filteredSoft = activeSoftTab === 'all' ? softConstraints : (softGrouped[activeSoftTab] || []);

  const bgColors = {
    red: 'bg-red-50/80 border-red-200', orange: 'bg-orange-50/80 border-orange-200',
    blue: 'bg-blue-50/80 border-blue-200', purple: 'bg-purple-50/80 border-purple-200',
    green: 'bg-green-50/80 border-green-200', teal: 'bg-teal-50/80 border-teal-200',
    indigo: 'bg-indigo-50/80 border-indigo-200', emerald: 'bg-emerald-50/80 border-emerald-200',
    slate: 'bg-slate-50/80 border-slate-200', amber: 'bg-amber-50/80 border-amber-200'
  };

  const panels = [
    { id: 'hard', label: 'القيود الإلزامية', icon: Shield, count: hardConstraints.length, color: 'red' },
    { id: 'soft', label: 'القيود التفضيلية', icon: Sliders, count: softConstraints.length + customSoftConstraints.length, color: 'amber' },
    { id: 'workload', label: 'النصاب والتكليفات', icon: Users, count: workloadSummary.length || teachers.length, color: 'blue' },
  ];

  return (
    <div className="space-y-4">
      <div className="flex gap-2 p-1 bg-slate-100 rounded-xl">
        {panels.map(p => (
          <button
            key={p.id}
            onClick={() => setActivePanel(p.id)}
            className={`flex-1 flex items-center justify-center gap-2 py-2.5 px-3 rounded-lg text-sm font-medium transition-all ${activePanel === p.id ? 'bg-white shadow text-slate-800' : 'text-slate-500 hover:text-slate-700'}`}
          >
            <p.icon className="h-4 w-4" />
            <span className="hidden sm:inline">{p.label}</span>
            <Badge className="text-[10px] bg-slate-100 text-slate-600 border-0">{p.count}</Badge>
          </button>
        ))}
      </div>

      {activePanel === 'hard' && (
        <div className="bg-gradient-to-br from-red-50 to-rose-50 border-2 border-red-200 rounded-2xl overflow-hidden">
          <div className="p-4 border-b border-red-200 bg-white/60">
            <div className="flex items-center gap-2.5 mb-1.5">
              <div className="w-9 h-9 rounded-xl bg-red-500 flex items-center justify-center shadow-sm"><Shield className="h-4.5 w-4.5 text-white" /></div>
              <div className="flex-1"><h3 className="text-base font-bold text-red-800">القيود الإلزامية</h3><p className="text-[11px] text-red-500 mt-0.5">Hard Constraints</p></div>
              <Badge className="bg-red-100 text-red-700 border border-red-200 text-xs">{hardConstraints.length} قيد</Badge>
            </div>
            <p className="text-xs text-red-600/80 flex items-center gap-1.5 mt-2"><Lock className="h-3.5 w-3.5" />قيود نظامية ثابتة لا يمكن خرقها — مطبقة تلقائياً</p>
          </div>
          <div className="flex flex-wrap gap-1.5 p-3 border-b border-red-100 bg-white/40">
            {['all', ...hardCats].map(cat => {
              const info = hardCategoryLabels[cat] || { label: cat, color: 'slate' };
              const count = cat === 'all' ? hardConstraints.length : (hardGrouped[cat]?.length || 0);
              return (
                <button key={cat} onClick={() => setActiveHardTab(cat)} className={`text-[11px] px-2.5 py-1 rounded-lg border transition-all font-medium ${activeHardTab === cat ? 'bg-red-500 text-white border-red-500 shadow-sm' : 'bg-white text-slate-600 border-slate-200 hover:border-red-300 hover:text-red-600'}`}>
                  {info.label} ({count})
                </button>
              );
            })}
          </div>
          <div className="overflow-y-auto p-3 space-y-2" style={{ maxHeight: '520px' }}>
            {filteredHard.length === 0 ? (
              <div className="text-center py-8 text-slate-400"><Shield className="h-10 w-10 mx-auto mb-2 opacity-40" /><p className="text-sm">{hardConstraints.length === 0 ? 'لا توجد قيود إلزامية' : 'لا توجد قيود في هذا التصنيف'}</p></div>
            ) : (
              filteredHard.map(c => {
                const catInfo = hardCategoryLabels[c.category] || { label: c.category, color: 'slate' };
                return (
                  <div key={c.code} className={`flex items-start gap-2.5 p-3 rounded-xl border transition-all ${bgColors[catInfo.color] || bgColors.slate} ${c.is_active === false ? 'opacity-60' : ''}`}>
                    <div className="w-7 h-7 rounded-lg bg-white border flex items-center justify-center shadow-sm flex-shrink-0 mt-0.5"><Lock className="h-3.5 w-3.5 text-red-500" /></div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-[10px] font-mono bg-white/60 px-1.5 py-0.5 rounded border text-slate-500">{c.code}</span>
                        <span className={`text-sm font-semibold ${c.is_active === false ? 'text-slate-400' : 'text-slate-800'}`}>{c.name_ar}</span>
                      </div>
                      <p className="text-xs text-slate-500 leading-relaxed">{c.description_ar}</p>
                      {c.can_disable
                        ? <Badge className="mt-1.5 bg-yellow-100 text-yellow-700 border border-yellow-300 text-[10px]">قابل للتعطيل</Badge>
                        : <Badge className="mt-1.5 bg-red-100 text-red-700 border border-red-300 text-[10px]">إلزامي دائماً</Badge>}
                    </div>
                    {c.can_disable ? (
                      <Switch
                        checked={c.is_active !== false}
                        onCheckedChange={() => handleHardConstraintToggle(c.code)}
                        className="flex-shrink-0 mt-0.5"
                      />
                    ) : (
                      <div className="flex items-center gap-1 flex-shrink-0 mt-1" title="قيد إلزامي لا يمكن تعطيله">
                        <Lock className="h-3.5 w-3.5 text-red-400" />
                        <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {activePanel === 'soft' && (
        <div className="space-y-4">
          <div className="bg-gradient-to-br from-amber-50 to-orange-50 border-2 border-amber-200 rounded-2xl overflow-hidden">
            <div className="p-4 border-b border-amber-200 bg-white/60">
              <div className="flex items-center gap-2.5 mb-1.5">
                <div className="w-9 h-9 rounded-xl bg-amber-500 flex items-center justify-center shadow-sm"><Sliders className="h-4.5 w-4.5 text-white" /></div>
                <div className="flex-1"><h3 className="text-base font-bold text-amber-800">القيود التفضيلية</h3><p className="text-[11px] text-amber-500 mt-0.5">Soft Constraints</p></div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-emerald-600 font-semibold">{softConstraints.filter(c => c.is_active).length} مفعّل</span>
                  <span className="text-xs text-slate-300">|</span>
                  <span className="text-xs text-slate-400">{softConstraints.filter(c => !c.is_active).length} معطّل</span>
                </div>
              </div>
              <div className="flex items-center justify-between mt-2">
                <p className="text-xs text-amber-600/80">تؤثر على جودة الجدول — يمكن تفعيلها وضبط أولويتها والمواد المستهدفة</p>
                <div className="flex gap-1.5">
                  <button onClick={() => toggleAllConstraints(true)} className="text-[10px] px-2 py-1 rounded-md border border-emerald-300 text-emerald-700 bg-emerald-50 hover:bg-emerald-100 transition-all">تفعيل الكل</button>
                  <button onClick={() => toggleAllConstraints(false)} className="text-[10px] px-2 py-1 rounded-md border border-slate-300 text-slate-500 bg-white hover:bg-slate-50 transition-all">تعطيل الكل</button>
                </div>
              </div>
            </div>
            <div className="flex flex-wrap gap-1.5 p-3 border-b border-amber-100 bg-white/40">
              {['all', ...softCats].map(cat => {
                const info = softCategoryLabels[cat] || { label: cat, color: 'slate' };
                const count = cat === 'all' ? softConstraints.length : (softGrouped[cat]?.length || 0);
                return (
                  <button key={cat} onClick={() => setActiveSoftTab(cat)} className={`text-[11px] px-2.5 py-1 rounded-lg border transition-all font-medium ${activeSoftTab === cat ? 'bg-amber-500 text-white border-amber-500 shadow-sm' : 'bg-white text-slate-600 border-slate-200 hover:border-amber-300 hover:text-amber-600'}`}>
                    {info.label} ({count})
                  </button>
                );
              })}
            </div>
            <div className="overflow-y-auto p-3 space-y-2.5" style={{ maxHeight: '480px' }}>
              {filteredSoft.length === 0 ? (
                <div className="text-center py-8 text-slate-400"><Sliders className="h-10 w-10 mx-auto mb-2 opacity-40" /><p className="text-sm">{softConstraints.length === 0 ? 'لا توجد قيود تفضيلية' : 'لا توجد قيود في هذا التصنيف'}</p></div>
              ) : (
                filteredSoft.map(c => {
                  const priorityLabel = c.weight >= 8 ? 'عالية' : c.weight >= 5 ? 'متوسطة' : 'منخفضة';
                  const priorityStyles = c.weight >= 8 ? 'bg-emerald-100 text-emerald-700 border-emerald-200' : c.weight >= 5 ? 'bg-amber-100 text-amber-700 border-amber-200' : 'bg-slate-100 text-slate-600 border-slate-200';
                  return (
                    <div key={c.code} className={`rounded-xl border-2 transition-all duration-200 overflow-hidden ${c.is_active ? 'border-amber-200 bg-white' : 'border-slate-100 bg-slate-50/60 opacity-60'}`}>
                      <div className="flex items-center justify-between p-3 pb-1.5">
                        <div className="flex items-center gap-2.5">
                          <Switch checked={c.is_active} onCheckedChange={() => handleSoftConstraintToggle(c.code)} />
                          <div>
                            <div className="flex items-center gap-1.5">
                              <span className="text-[10px] font-mono text-slate-400 bg-slate-100 px-1 py-0.5 rounded">{c.code}</span>
                              <span className={`text-sm font-medium ${c.is_active ? 'text-slate-800' : 'text-slate-400'}`}>{c.name_ar}</span>
                            </div>
                            {c.description_ar && <p className="text-[11px] text-slate-400 mt-0.5 line-clamp-1">{c.description_ar}</p>}
                          </div>
                        </div>
                        {c.is_active && <Badge className={`text-[10px] border ${priorityStyles}`}>{priorityLabel}</Badge>}
                      </div>
                      {c.is_active && (
                        <div className="px-3 pb-3 pt-1">
                          <div className="flex items-center gap-2.5">
                            <span className="text-[11px] text-slate-500 w-12 shrink-0">الأولوية</span>
                            <input type="range" min="1" max="10" step="1" value={c.weight} onChange={(e) => handleSoftConstraintWeight(c.code, parseInt(e.target.value))} className="flex-1 h-1.5 rounded-full accent-amber-500 cursor-pointer" />
                            <span className="text-xs font-bold w-8 text-start text-amber-600">{c.weight}/10</span>
                          </div>
                          <div className="flex items-center justify-between mt-1.5">
                            <div className="flex gap-1.5">
                              {[{label:'منخفض', val:3},{label:'متوسط', val:6},{label:'عالي', val:9}].map(p => (
                                <button key={p.val} onClick={() => handleSoftConstraintWeight(c.code, p.val)} className={`text-[10px] px-2 py-0.5 rounded-md border transition-all ${c.weight === p.val ? 'bg-amber-500 text-white border-amber-500' : 'bg-white text-slate-500 border-slate-200 hover:border-amber-300'}`}>{p.label}</button>
                              ))}
                            </div>
                            {subjects.length > 0 && (
                              <SubjectMultiSelect
                                subjects={subjects}
                                selectedIds={c.target_subject_ids || []}
                                onChange={(ids) => handleSoftConstraintTargetSubjects(c.code, ids)}
                              />
                            )}
                          </div>
                          {(c.target_subject_ids?.length > 0) && (
                            <p className="text-[10px] text-amber-600 mt-1 flex items-center gap-1">
                              <BookOpen className="h-3 w-3" />
                              مطبّق على {c.target_subject_ids.length} مادة محددة فقط
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
            <div className="p-3 border-t border-amber-100 bg-white/40">
              <p className="text-[11px] text-slate-400 text-center">التغييرات تُحفظ تلقائياً — تُطبَّق على الجداول الجديدة فقط</p>
            </div>
          </div>

          <div className="bg-gradient-to-br from-violet-50 to-purple-50 border-2 border-violet-200 rounded-2xl overflow-hidden">
            <div className="p-4 border-b border-violet-200 bg-white/60">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-9 h-9 rounded-xl bg-violet-500 flex items-center justify-center shadow-sm"><Plus className="h-4.5 w-4.5 text-white" /></div>
                  <div>
                    <h3 className="text-base font-bold text-violet-800">القيود التفضيلية المخصصة</h3>
                    <p className="text-[11px] text-violet-500 mt-0.5">Custom Soft Constraints</p>
                  </div>
                </div>
                <button
                  onClick={() => setShowAddConstraintModal(true)}
                  className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-violet-500 text-white hover:bg-violet-600 transition-all shadow-sm"
                >
                  <Plus className="h-3.5 w-3.5" />
                  إضافة قيد جديد
                </button>
              </div>
            </div>
            <div className="p-3 space-y-2" style={{ maxHeight: '320px', overflowY: 'auto' }}>
              {customSoftConstraints.length === 0 ? (
                <div className="text-center py-8 text-slate-400">
                  <Plus className="h-10 w-10 mx-auto mb-2 opacity-40" />
                  <p className="text-sm">لم تُضَف قيود مخصصة بعد</p>
                  <button onClick={() => setShowAddConstraintModal(true)} className="mt-3 text-xs text-violet-600 hover:text-violet-700 underline">إضافة أول قيد مخصص</button>
                </div>
              ) : (
                customSoftConstraints.map(c => (
                  <div key={c.id} className={`rounded-xl border-2 overflow-hidden transition-all ${c.is_active ? 'border-violet-200 bg-white' : 'border-slate-100 bg-slate-50/60 opacity-60'}`}>
                    <div className="flex items-center justify-between p-3">
                      <div className="flex items-center gap-2.5">
                        <Switch checked={c.is_active} onCheckedChange={() => handleToggleCustomConstraint(c.id)} />
                        <div>
                          <div className="flex items-center gap-1.5">
                            <Badge className="text-[9px] bg-violet-100 text-violet-700 border-violet-200">مخصص</Badge>
                            <span className={`text-sm font-medium ${c.is_active ? 'text-slate-800' : 'text-slate-400'}`}>{c.name_ar}</span>
                          </div>
                          {c.description_ar && <p className="text-[11px] text-slate-400 mt-0.5">{c.description_ar}</p>}
                          <div className="flex items-center gap-2 mt-1">
                            <span className="text-[10px] text-slate-500">الوزن: {c.weight}/10</span>
                            {c.pattern_code && c.pattern_code !== 'custom' && (
                              <span className="text-[10px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded">{c.pattern_code}</span>
                            )}
                            {(c.target_subject_ids?.length > 0) && (
                              <span className="text-[10px] text-amber-600">{c.target_subject_ids.length} مادة محددة</span>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        <button onClick={() => setEditingConstraint(c)} className="p-1.5 text-violet-400 hover:text-violet-600 hover:bg-violet-50 rounded-lg transition-all" title="تعديل القيد">
                          <Edit2 className="h-3.5 w-3.5" />
                        </button>
                        <button onClick={() => handleDeleteCustomConstraint(c.id)} className="p-1.5 text-red-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all" title="حذف القيد">
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {showAddConstraintModal && (
            <AddConstraintModal
              subjects={subjects}
              constraintPatterns={constraintPatterns}
              handleAddConstraintPattern={handleAddConstraintPattern}
              onSave={handleAddCustomConstraint}
              onClose={() => setShowAddConstraintModal(false)}
            />
          )}
          {editingConstraint && (
            <AddConstraintModal
              subjects={subjects}
              constraintPatterns={constraintPatterns}
              handleAddConstraintPattern={handleAddConstraintPattern}
              initialData={editingConstraint}
              onSave={async (data) => {
                await handleUpdateCustomConstraint(editingConstraint.id, data);
                setEditingConstraint(null);
              }}
              onClose={() => setEditingConstraint(null)}
            />
          )}
        </div>
      )}

      {activePanel === 'workload' && (
        <div className="space-y-4">
          <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border-2 border-blue-200 rounded-2xl overflow-hidden">
            <div className="p-4 border-b border-blue-200 bg-white/60">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-9 h-9 rounded-xl bg-blue-500 flex items-center justify-center shadow-sm"><Users className="h-4.5 w-4.5 text-white" /></div>
                  <div>
                    <h3 className="text-base font-bold text-blue-800">ملخص النصاب</h3>
                    <p className="text-[11px] text-blue-500 mt-0.5">حصص دراسية + تكليفات = مستخدم / النصاب الكلي</p>
                  </div>
                </div>
                <button onClick={fetchWorkloadSummary} className="text-[10px] px-2 py-1 rounded-md border border-blue-200 text-blue-600 hover:bg-blue-50 flex items-center gap-1">
                  <RefreshCw className="h-3 w-3" />تحديث
                </button>
              </div>
            </div>
            <div className="overflow-y-auto" style={{ maxHeight: '480px' }}>
              {workloadLoading ? (
                <div className="text-center py-12 text-slate-400"><RefreshCw className="h-8 w-8 mx-auto mb-2 animate-spin opacity-40" /><p className="text-sm">جاري حساب النصاب...</p></div>
              ) : workloadSummary.length === 0 ? (
                <div className="text-center py-12 text-slate-400"><Users className="h-10 w-10 mx-auto mb-2 opacity-40" /><p className="text-sm">لا يوجد معلمون أو لم يتم تحميل بيانات النصاب</p></div>
              ) : (
                <div className="divide-y divide-blue-50">
                  {workloadSummary.map(w => (
                    <WorkloadRow key={w.teacher_id} w={w} handleWorkloadOverride={handleWorkloadOverride} />
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="bg-gradient-to-br from-teal-50 to-emerald-50 border-2 border-teal-200 rounded-2xl overflow-hidden">
            <div className="p-4 border-b border-teal-200 bg-white/60">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-9 h-9 rounded-xl bg-teal-500 flex items-center justify-center shadow-sm"><Zap className="h-4.5 w-4.5 text-white" /></div>
                  <div>
                    <h3 className="text-base font-bold text-teal-800">التكليفات الأخرى</h3>
                    <p className="text-[11px] text-teal-500 mt-0.5">مهام غير تدريسية لها حصص معادلة (إذاعة، مكتبة، إرشاد...)</p>
                  </div>
                </div>
                <button
                  onClick={() => setShowAddDutyModal(true)}
                  className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-teal-500 text-white hover:bg-teal-600 transition-all shadow-sm"
                >
                  <Plus className="h-3.5 w-3.5" />
                  إضافة تكليف
                </button>
              </div>
            </div>
            <div className="p-3 space-y-2" style={{ maxHeight: '320px', overflowY: 'auto' }}>
              {otherDuties.length === 0 ? (
                <div className="text-center py-8 text-slate-400">
                  <Zap className="h-10 w-10 mx-auto mb-2 opacity-40" />
                  <p className="text-sm">لا توجد تكليفات أخرى مضافة</p>
                  <p className="text-xs mt-1">مثال: إذاعة (2 حصة)، مكتبة (1 حصة)، إرشاد (3 حصص)</p>
                </div>
              ) : (
                otherDuties.map(d => (
                  <div key={d.id} className="flex items-center justify-between p-3 rounded-xl border border-teal-100 bg-white">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-slate-800">{d.teacher_name}</span>
                        <Badge className="text-[10px] bg-teal-100 text-teal-700 border-teal-200">{d.duty_name}</Badge>
                        <Badge className="text-[10px] bg-blue-100 text-blue-700 border-blue-200">{d.equivalent_periods} حصة</Badge>
                      </div>
                      {d.notes && <p className="text-[11px] text-slate-400 mt-0.5">{d.notes}</p>}
                    </div>
                    <div className="flex items-center gap-1">
                      <button onClick={() => setEditingDuty(d)} className="p-1.5 text-teal-400 hover:text-teal-600 hover:bg-teal-50 rounded-lg transition-all" title="تعديل التكليف">
                        <Edit2 className="h-3.5 w-3.5" />
                      </button>
                      <button onClick={() => handleDeleteOtherDuty(d.id)} className="p-1.5 text-red-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all" title="حذف التكليف">
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {showAddDutyModal && (
            <AddDutyModal
              teachers={teachers}
              onSave={handleAddOtherDuty}
              onClose={() => setShowAddDutyModal(false)}
            />
          )}
          {editingDuty && (
            <AddDutyModal
              teachers={teachers}
              initialData={editingDuty}
              onSave={async (data) => {
                await handleUpdateOtherDuty(editingDuty.id, data);
                setEditingDuty(null);
              }}
              onClose={() => setEditingDuty(null)}
            />
          )}
        </div>
      )}
    </div>
  );
}

function WorkloadRow({ w, handleWorkloadOverride }) {
  const [localStandby, setLocalStandby] = React.useState(String(w.standby_periods));
  React.useEffect(() => { setLocalStandby(String(w.standby_periods)); }, [w.standby_periods]);

  const commit = () => {
    const val = parseInt(localStandby, 10);
    if (isNaN(val) || val < 0 || val > w.total_periods) {
      setLocalStandby(String(w.standby_periods));
      return;
    }
    if (val !== w.standby_periods) {
      handleWorkloadOverride(w.teacher_id, val);
    }
  };

  const usedPct = Math.min(100, Math.round((w.used_periods / (w.total_periods || 1)) * 100));
  const isOverload = w.overload;

  return (
    <div className={`p-4 ${isOverload ? 'bg-red-50/50' : 'bg-white/40'}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-slate-800">{w.teacher_name}</span>
          {w.rank && <Badge className="text-[9px] bg-slate-100 text-slate-600 border-0">{w.rank}</Badge>}
          {isOverload && <Badge className="text-[9px] bg-red-100 text-red-700 border-red-200">تجاوز النصاب</Badge>}
          {w.manual_override && <Badge className="text-[9px] bg-blue-100 text-blue-700 border-blue-200">تعديل يدوي</Badge>}
        </div>
        <div className="text-xs text-slate-600 font-medium">
          <span className={isOverload ? 'text-red-600 font-bold' : ''}>{w.used_periods}</span>/{w.total_periods} حصة
        </div>
      </div>
      <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden mb-2">
        <div
          className={`h-full rounded-full transition-all ${isOverload ? 'bg-red-500' : usedPct > 80 ? 'bg-amber-500' : 'bg-blue-500'}`}
          style={{ width: `${usedPct}%` }}
        />
      </div>
      <div className="flex items-center justify-between text-[10px] text-slate-500">
        <div className="flex items-center gap-3">
          <span>📚 تدريس: <strong>{w.teaching_periods}</strong></span>
          <span>➕ تكليفات: <strong>{w.other_duty_periods}</strong></span>
          <span className={w.standby_periods < 0 ? 'text-red-600' : 'text-slate-500'}>⏳ انتظار: <strong>{w.standby_periods}</strong></span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-slate-400">حصص الانتظار:</span>
          <input
            type="number"
            min="0"
            max={w.total_periods}
            value={localStandby}
            onChange={(e) => setLocalStandby(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.target.blur(); } }}
            className="w-12 text-center text-xs border border-slate-200 rounded px-1 py-0.5 focus:outline-none focus:border-blue-400"
            title={`تعديل يدوي لحصص الانتظار (0 - ${w.total_periods})`}
          />
          {w.manual_override && (
            <button onClick={() => handleWorkloadOverride(w.teacher_id, null)} className="text-slate-400 hover:text-red-500 transition-all" title="إزالة التعديل اليدوي">
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function AddConstraintModal({ subjects, constraintPatterns, handleAddConstraintPattern, onSave, onClose, initialData = null }) {
  const { direction } = useTheme();
  const isEdit = !!initialData;
  const [nameAr, setNameAr] = React.useState(initialData?.name_ar || '');
  const [descAr, setDescAr] = React.useState(initialData?.description_ar || '');
  const [patternCode, setPatternCode] = React.useState(initialData?.pattern_code || 'custom');
  const [weight, setWeight] = React.useState(initialData?.weight ?? 5);
  const [targetSubjectIds, setTargetSubjectIds] = React.useState(initialData?.target_subject_ids || []);
  const [appliesTo, setAppliesTo] = React.useState(initialData?.applies_to || 'school');
  const [showNewPattern, setShowNewPattern] = React.useState(false);
  const [newPatternName, setNewPatternName] = React.useState('');
  const [saving, setSaving] = React.useState(false);

  const allPatterns = [
    ...(constraintPatterns?.builtin || []),
    ...(constraintPatterns?.custom || []),
  ];

  const handleSave = async () => {
    if (!nameAr.trim()) return;
    setSaving(true);
    try {
      await onSave({ name_ar: nameAr, description_ar: descAr, pattern_code: patternCode, weight, target_subject_ids: targetSubjectIds, applies_to: appliesTo });
    } finally {
      setSaving(false);
    }
  };

  const handleAddPattern = async () => {
    if (!newPatternName.trim()) return;
    const p = await handleAddConstraintPattern({ name_ar: newPatternName });
    if (p) {
      setPatternCode(p.code);
      setShowNewPattern(false);
      setNewPatternName('');
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" dir={direction}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
        <div className="p-5 border-b flex items-center justify-between">
          <h3 className="text-lg font-bold flex items-center gap-2"><Plus className="h-5 w-5 text-violet-600" />{isEdit ? 'تعديل القيد التفضيلي' : 'إضافة قيد تفضيلي مخصص'}</h3>
          <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-lg transition-all"><X className="h-4 w-4" /></button>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <Label className="text-sm font-medium text-slate-700">اسم القيد <span className="text-red-500">*</span></Label>
            <Input value={nameAr} onChange={e => setNameAr(e.target.value)} placeholder="مثال: المعلم أحمد لا يُجدول في الحصة الأولى" className="mt-1.5" />
          </div>
          <div>
            <Label className="text-sm font-medium text-slate-700">الوصف</Label>
            <Input value={descAr} onChange={e => setDescAr(e.target.value)} placeholder="وصف تفصيلي للقيد..." className="mt-1.5" />
          </div>
          <div>
            <Label className="text-sm font-medium text-slate-700">نمط القيد</Label>
            <div className="flex gap-2 mt-1.5">
              <Select value={patternCode} onValueChange={setPatternCode}>
                <SelectTrigger className="flex-1"><SelectValue placeholder="اختر النمط" /></SelectTrigger>
                <SelectContent>
                  {allPatterns.map(p => (
                    <SelectItem key={p.code} value={p.code}>{p.name_ar}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <button onClick={() => setShowNewPattern(!showNewPattern)} className="text-xs px-3 py-1.5 rounded-lg border border-violet-200 text-violet-700 hover:bg-violet-50 transition-all whitespace-nowrap">+ نمط جديد</button>
            </div>
            {showNewPattern && (
              <div className="flex gap-2 mt-2">
                <Input value={newPatternName} onChange={e => setNewPatternName(e.target.value)} placeholder="اسم النمط الجديد..." className="flex-1 text-sm" />
                <button onClick={handleAddPattern} className="text-xs px-3 py-1.5 rounded-lg bg-violet-500 text-white hover:bg-violet-600 transition-all">إضافة</button>
              </div>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label className="text-sm font-medium text-slate-700">الوزن / الأولوية</Label>
              <div className="flex items-center gap-2 mt-1.5">
                <input type="range" min="1" max="10" value={weight} onChange={e => setWeight(parseInt(e.target.value))} className="flex-1 accent-violet-500" />
                <span className="text-sm font-bold text-violet-600 w-8">{weight}/10</span>
              </div>
            </div>
            <div>
              <Label className="text-sm font-medium text-slate-700">نطاق التطبيق</Label>
              <Select value={appliesTo} onValueChange={setAppliesTo}>
                <SelectTrigger className="mt-1.5"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="school">المدرسة كاملة</SelectItem>
                  <SelectItem value="teacher">معلم</SelectItem>
                  <SelectItem value="class">فصل</SelectItem>
                  <SelectItem value="subject">مادة</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          {subjects.length > 0 && (
            <div>
              <Label className="text-sm font-medium text-slate-700">المواد المستهدفة (اختياري)</Label>
              <p className="text-xs text-slate-400 mb-1.5">إذا تُركت فارغة يُطبَّق على جميع المواد</p>
              <div className="flex flex-wrap gap-1.5 p-2 border rounded-xl bg-slate-50 min-h-[40px]">
                {subjects.map(s => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => setTargetSubjectIds(prev => prev.includes(s.id) ? prev.filter(x => x !== s.id) : [...prev, s.id])}
                    className={`text-[11px] px-2 py-0.5 rounded-md border transition-all ${targetSubjectIds.includes(s.id) ? 'bg-violet-500 text-white border-violet-500' : 'bg-white text-slate-600 border-slate-200 hover:border-violet-300'}`}
                  >
                    {s.name_ar || s.name}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
        <div className="p-5 border-t flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-all">إلغاء</button>
          <button onClick={handleSave} disabled={!nameAr.trim() || saving} className="px-5 py-2 text-sm bg-violet-500 text-white rounded-lg hover:bg-violet-600 transition-all disabled:opacity-50">
            {saving ? 'جاري الحفظ...' : 'حفظ القيد'}
          </button>
        </div>
      </div>
    </div>
  );
}

function AddDutyModal({ teachers, onSave, onClose, initialData = null }) {
  const { direction } = useTheme();
  const isEdit = !!initialData;
  const [teacherId, setTeacherId] = React.useState(initialData?.teacher_id || '');
  const [dutyName, setDutyName] = React.useState(initialData?.duty_name || '');
  const [equivalentPeriods, setEquivalentPeriods] = React.useState(initialData?.equivalent_periods ?? 1);
  const [notes, setNotes] = React.useState(initialData?.notes || '');
  const [saving, setSaving] = React.useState(false);

  const DUTY_PRESETS = ['إذاعة المدرسة', 'مكتبة', 'إرشاد طلابي', 'ريادة فصل', 'نشاط مدرسي', 'لجنة امتحانات', 'إشراف فترة الانتظار'];

  const handleSave = async () => {
    if (!teacherId || !dutyName.trim()) return;
    setSaving(true);
    const teacher = teachers.find(t => t.id === teacherId);
    try {
      await onSave({
        teacher_id: teacherId,
        teacher_name: teacher?.full_name || '',
        duty_name: dutyName,
        equivalent_periods: equivalentPeriods,
        notes,
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" dir={direction}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="p-5 border-b flex items-center justify-between">
          <h3 className="text-lg font-bold flex items-center gap-2"><Zap className="h-5 w-5 text-teal-600" />{isEdit ? 'تعديل التكليف' : 'إضافة تكليف آخر'}</h3>
          <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-lg transition-all"><X className="h-4 w-4" /></button>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <Label className="text-sm font-medium text-slate-700">المعلم {!isEdit && <span className="text-red-500">*</span>}</Label>
            {isEdit ? (
              <div className="mt-1.5 px-3 py-2 rounded-lg bg-slate-50 border border-slate-200 text-sm text-slate-700">
                {initialData?.teacher_name || 'المعلم'}
                <span className="text-[10px] text-slate-400 mr-2">(لا يمكن تغيير المعلم)</span>
              </div>
            ) : (
              <Select value={teacherId} onValueChange={setTeacherId}>
                <SelectTrigger className="mt-1.5"><SelectValue placeholder="اختر المعلم" /></SelectTrigger>
                <SelectContent>
                  {teachers.map(t => <SelectItem key={t.id} value={t.id}>{t.full_name}</SelectItem>)}
                </SelectContent>
              </Select>
            )}
          </div>
          <div>
            <Label className="text-sm font-medium text-slate-700">نوع التكليف <span className="text-red-500">*</span></Label>
            <div className="flex flex-wrap gap-1.5 mt-1.5 mb-2">
              {DUTY_PRESETS.map(p => (
                <button key={p} type="button" onClick={() => setDutyName(p)} className={`text-[11px] px-2 py-0.5 rounded-md border transition-all ${dutyName === p ? 'bg-teal-500 text-white border-teal-500' : 'bg-white text-slate-600 border-slate-200 hover:border-teal-300'}`}>{p}</button>
              ))}
            </div>
            <Input value={dutyName} onChange={e => setDutyName(e.target.value)} placeholder="أو اكتب نوع التكليف..." className="mt-1" />
          </div>
          <div>
            <Label className="text-sm font-medium text-slate-700">عدد الحصص المعادلة</Label>
            <div className="flex items-center gap-3 mt-1.5">
              {[1, 2, 3, 4, 5].map(n => (
                <button key={n} type="button" onClick={() => setEquivalentPeriods(n)} className={`w-10 h-10 rounded-xl text-sm font-bold border transition-all ${equivalentPeriods === n ? 'bg-teal-500 text-white border-teal-500' : 'bg-white text-slate-600 border-slate-200 hover:border-teal-300'}`}>{n}</button>
              ))}
              <input type="number" min="0" max="20" value={equivalentPeriods} onChange={e => setEquivalentPeriods(parseInt(e.target.value) || 0)} className="w-16 text-center border border-slate-200 rounded-xl px-2 py-2 text-sm focus:outline-none focus:border-teal-400" />
            </div>
          </div>
          <div>
            <Label className="text-sm font-medium text-slate-700">ملاحظات</Label>
            <Input value={notes} onChange={e => setNotes(e.target.value)} placeholder="ملاحظات اختيارية..." className="mt-1.5" />
          </div>
        </div>
        <div className="p-5 border-t flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-all">إلغاء</button>
          <button onClick={handleSave} disabled={!teacherId || !dutyName.trim() || saving} className="px-5 py-2 text-sm bg-teal-500 text-white rounded-lg hover:bg-teal-600 transition-all disabled:opacity-50">
            {saving ? 'جاري الحفظ...' : 'إضافة التكليف'}
          </button>
        </div>
      </div>
    </div>
  );
}
