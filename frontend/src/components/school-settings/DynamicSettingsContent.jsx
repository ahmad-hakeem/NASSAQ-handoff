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
  RefreshCw, Wand2, Database
} from 'lucide-react';
import { DndContext, DragOverlay, closestCenter } from '@dnd-kit/core';
import {
  DraggableClassItem,
  DroppableTeacherBox,
  DraggableSubjectItem,
  DroppableTeacherSubjectBox,
} from './DndComponents';

export function DynamicSettingsContent({ hook, dynamicTabs }) {
  const {
    activeTab, setActiveTab, saving, sensors,
    schoolInfo, teachers, classes, assignments,
    subjects, draggingSubject, setDraggingSubject,
    assignmentSubTab, setAssignmentSubTab,
    classAssignments, classAssignmentsLoading, draggingClass, setDraggingClass,
    editedSchoolInfo, setEditedSchoolInfo,
    workDays, timingSettings, timeSlotsCount, generatingSlots,
    breakTimes, teacherUnavailability, classUnavailability,
    hardConstraints, softConstraints, activeHardTab, setActiveHardTab, activeSoftTab, setActiveSoftTab,
    saveAllSettings, saveSchoolInfo, generateTimeSlots,
    getTeacherAssignments, removeAssignment, deleteClass,
    handleSettingChange, handleWorkDayChange,
    handleSoftConstraintToggle, handleSoftConstraintWeight, toggleAllConstraints,
    handleAddBreak, handleEditBreak, handleDeleteBreak,
    handleAddUnavailability, handleDeleteUnavailability,
    handleCreateClassAssignment, handleDeleteClassAssignment,
    nassaqWarning, user, api, setAssignments,
  } = hook;

  return (
    <div className="space-y-6">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
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

        <TabsContent value="school-info" className="space-y-6">
          <Card className="bg-white shadow-sm border-[#1C3D74]/20">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-[#1C3D74] flex items-center justify-center">
                    <Building2 className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <CardTitle className="text-lg text-[#1C3D74]">البيانات الأساسية للمدرسة</CardTitle>
                    <CardDescription>المعلومات الرسمية المعتمدة — تُحفظ في قاعدة البيانات فور الحفظ</CardDescription>
                  </div>
                </div>
                {schoolInfo.license_number && (
                  <Badge className="bg-slate-100 text-slate-600 border border-slate-300 gap-1 text-sm px-3 py-1">
                    <Shield className="h-3 w-3" />
                    رمز المدرسة: {schoolInfo.license_number}
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="font-semibold text-slate-700 flex items-center gap-1">
                    <Building2 className="h-3.5 w-3.5 text-[#1C3D74]" />
                    اسم المدرسة بالعربية <span className="text-red-500">*</span>
                  </Label>
                  <Input
                    dir="rtl"
                    className="h-11 border-slate-200 focus:border-[#1C3D74] text-right"
                    value={editedSchoolInfo.name_ar || ''}
                    onChange={e => setEditedSchoolInfo(p => ({ ...p, name_ar: e.target.value }))}
                    placeholder="اسم المدرسة بالعربية"
                    data-testid="school-name-ar-input"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="font-semibold text-slate-700">نوع المدرسة</Label>
                  <Select value={editedSchoolInfo.type || ''} onValueChange={v => setEditedSchoolInfo(p => ({ ...p, type: v }))}>
                    <SelectTrigger className="h-11 border-slate-200" data-testid="school-type-select"><SelectValue placeholder="اختر نوع المدرسة" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="government">حكومية</SelectItem>
                      <SelectItem value="private">أهلية</SelectItem>
                      <SelectItem value="international">دولية</SelectItem>
                      <SelectItem value="special">خاصة</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label className="font-semibold text-slate-700">المرحلة الدراسية</Label>
                  <Select value={editedSchoolInfo.stage || ''} onValueChange={v => setEditedSchoolInfo(p => ({ ...p, stage: v, educational_pathway: v === 'secondary_pathways' ? p.educational_pathway : '' }))}>
                    <SelectTrigger className="h-11 border-slate-200" data-testid="school-stage-select"><SelectValue placeholder="اختر المرحلة" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="primary">ابتدائية</SelectItem>
                      <SelectItem value="intermediate">متوسطة</SelectItem>
                      <SelectItem value="secondary_general">ثانوية عامة</SelectItem>
                      <SelectItem value="secondary_pathways">ثانوية مسارات</SelectItem>
                      <SelectItem value="school_complex">مجمع مدارس</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {editedSchoolInfo.stage === 'secondary_pathways' && (
                <div className="space-y-2">
                  <Label className="font-semibold text-slate-700 flex items-center gap-1"><GraduationCap className="h-3.5 w-3.5 text-[#1C3D74]" />المسار التعليمي</Label>
                  <Select value={editedSchoolInfo.educational_pathway || ''} onValueChange={v => setEditedSchoolInfo(p => ({ ...p, educational_pathway: v }))}>
                    <SelectTrigger className="h-11 border-slate-200" data-testid="school-pathway-select"><SelectValue placeholder="اختر المسار التعليمي" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="general">المسار العام</SelectItem>
                      <SelectItem value="cs_engineering">مسار علوم الحاسب والهندسة</SelectItem>
                      <SelectItem value="health_life">مسار الصحة والحياة</SelectItem>
                      <SelectItem value="business">مسار إدارة الأعمال</SelectItem>
                      <SelectItem value="sharia">المسار الشرعي</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="font-semibold text-slate-700 flex items-center gap-1"><MapPin className="h-3.5 w-3.5 text-[#1C3D74]" />المدينة</Label>
                  <Input dir="rtl" className="h-11 border-slate-200 focus:border-[#1C3D74] text-right" value={editedSchoolInfo.city || ''} onChange={e => setEditedSchoolInfo(p => ({ ...p, city: e.target.value }))} placeholder="المدينة" data-testid="school-city-input" />
                </div>
                <div className="space-y-2">
                  <Label className="font-semibold text-slate-700 flex items-center gap-1"><MapPin className="h-3.5 w-3.5 text-[#1C3D74]" />المنطقة / المحافظة</Label>
                  <Input dir="rtl" className="h-11 border-slate-200 focus:border-[#1C3D74] text-right" value={editedSchoolInfo.region || ''} onChange={e => setEditedSchoolInfo(p => ({ ...p, region: e.target.value }))} placeholder="المنطقة الإدارية" data-testid="school-region-input" />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="font-semibold text-slate-700 flex items-center gap-1"><Phone className="h-3.5 w-3.5 text-[#1C3D74]" />رقم جوال المدير <span className="text-red-500">*</span></Label>
                  <Input dir="ltr" type="tel" className="h-11 border-slate-200 focus:border-[#1C3D74]" value={editedSchoolInfo.principal_mobile || ''} onChange={e => setEditedSchoolInfo(p => ({ ...p, principal_mobile: e.target.value }))} placeholder="05XXXXXXXX" data-testid="school-principal-mobile-input" />
                </div>
                <div className="space-y-2">
                  <Label className="font-semibold text-slate-700 flex items-center gap-1"><Mail className="h-3.5 w-3.5 text-[#1C3D74]" />البريد الإلكتروني</Label>
                  <Input dir="ltr" type="email" className="h-11 border-slate-200 focus:border-[#1C3D74]" value={editedSchoolInfo.email || ''} onChange={e => setEditedSchoolInfo(p => ({ ...p, email: e.target.value }))} placeholder="school@example.edu.sa" data-testid="school-email-input" />
                </div>
              </div>

              <div className="space-y-2">
                <Label className="font-semibold text-slate-700 flex items-center gap-1"><Users className="h-3.5 w-3.5 text-[#1C3D74]" />اسم مدير/مديرة المدرسة</Label>
                <Input dir="rtl" className="h-11 border-slate-200 focus:border-[#1C3D74] text-right" value={editedSchoolInfo.principal_name || ''} onChange={e => setEditedSchoolInfo(p => ({ ...p, principal_name: e.target.value }))} placeholder="الاسم الكامل" data-testid="school-principal-input" />
              </div>

              <div className="flex flex-wrap gap-3 pt-2 border-t border-slate-100">
                <div className="flex items-center gap-2 text-sm text-slate-500">
                  <Shield className="h-3.5 w-3.5" />
                  <span>رمز الترخيص:</span>
                  <span className="font-mono font-semibold text-slate-700">{schoolInfo.license_number || '—'}</span>
                </div>
                <div className="flex items-center gap-2 text-sm text-slate-500">
                  <CheckCircle2 className={`h-3.5 w-3.5 ${schoolInfo.is_active ? 'text-emerald-500' : 'text-red-400'}`} />
                  <span>الحالة:</span>
                  <span className={`font-semibold ${schoolInfo.is_active ? 'text-emerald-600' : 'text-red-500'}`}>
                    {schoolInfo.is_active ? 'نشطة' : 'غير نشطة'}
                  </span>
                </div>
                {schoolInfo.updated_at && (
                  <div className="flex items-center gap-2 text-sm text-slate-500">
                    <RefreshCw className="h-3.5 w-3.5" />
                    <span>آخر تحديث:</span>
                    <span className="text-slate-600">{new Date(schoolInfo.updated_at).toLocaleDateString('ar-SA')}</span>
                  </div>
                )}
              </div>

              <div className="flex justify-end pt-2">
                <Button onClick={saveSchoolInfo} disabled={saving} className="bg-[#1C3D74] hover:bg-[#152d57] text-white px-8 h-11" data-testid="save-school-info-btn">
                  {saving ? <RefreshCw className="h-4 w-4 animate-spin ml-2" /> : <Save className="h-4 w-4 ml-2" />}
                  حفظ بيانات المدرسة
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="academic-year" className="space-y-6">
          <Card className="bg-white shadow-sm">
            <CardHeader>
              <CardTitle className="text-xl flex items-center gap-2"><Calendar className="h-5 w-5 text-[#1C3D74]" />العام والفصل الدراسي الحالي</CardTitle>
              <CardDescription>حدد العام والفصل الدراسي الذي سيتم بناء الجدول له</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-2 gap-6">
                <div>
                  <Label className="text-sm text-slate-600 mb-2 block">العام الدراسي</Label>
                  <Select value={timingSettings.academicYear} onValueChange={(v) => handleSettingChange('academicYear', v)}>
                    <SelectTrigger className="h-12 bg-white" data-testid="academic-year-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1447">1447 هـ</SelectItem>
                      <SelectItem value="1446">1446 هـ</SelectItem>
                      <SelectItem value="1445">1445 هـ</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-sm text-slate-600 mb-2 block">الفصل الدراسي</Label>
                  <Select value={timingSettings.currentSemester} onValueChange={(v) => handleSettingChange('currentSemester', v)}>
                    <SelectTrigger className="h-12 bg-white" data-testid="semester-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1">الفصل الأول</SelectItem>
                      <SelectItem value="2">الفصل الثاني</SelectItem>
                      <SelectItem value="3">الفصل الثالث</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="mt-6 flex justify-end">
                <Button onClick={saveAllSettings} disabled={saving} className="bg-[#1C3D74] hover:bg-[#152d57] px-8" data-testid="save-academic-btn">
                  <Save className="h-4 w-4 ml-2" />{saving ? 'جاري الحفظ...' : 'حفظ'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="workdays" className="space-y-6">
          <Card className="bg-white shadow-sm">
            <CardHeader>
              <CardTitle className="text-xl flex items-center gap-2"><CalendarDays className="h-5 w-5 text-[#1C3D74]" />أيام العمل والعطلة</CardTitle>
              <CardDescription>حدد أيام الدراسة الأسبوعية</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-7 gap-3 mb-6">
                {[
                  { key: 'sunday', ar: 'الأحد', en: 'Sun' },
                  { key: 'monday', ar: 'الإثنين', en: 'Mon' },
                  { key: 'tuesday', ar: 'الثلاثاء', en: 'Tue' },
                  { key: 'wednesday', ar: 'الأربعاء', en: 'Wed' },
                  { key: 'thursday', ar: 'الخميس', en: 'Thu' },
                  { key: 'friday', ar: 'الجمعة', en: 'Fri' },
                  { key: 'saturday', ar: 'السبت', en: 'Sat' }
                ].map((day) => (
                  <div
                    key={day.key}
                    onClick={() => handleWorkDayChange(day.key)}
                    className={`cursor-pointer rounded-xl p-4 text-center transition-all duration-200 ${
                      workDays[day.key]
                        ? 'bg-brand-navy text-white shadow-lg shadow-brand-navy/20'
                        : 'bg-slate-100 text-slate-400 hover:bg-slate-200'
                    }`}
                    data-testid={`day-${day.key}`}
                  >
                    <p className="text-xs mb-1 opacity-70">{day.en}</p>
                    <p className="text-sm font-bold">{day.ar}</p>
                    <div className="mt-2">
                      {workDays[day.key] ? <CheckCircle2 className="h-4 w-4 mx-auto" /> : <X className="h-4 w-4 mx-auto opacity-50" />}
                    </div>
                  </div>
                ))}
              </div>
              <Separator className="my-6" />
              <div className="flex items-center justify-between">
                <div className="flex gap-6">
                  <div className="flex items-center gap-2"><div className="w-4 h-4 rounded-full bg-brand-navy"></div><span className="text-sm text-slate-600">{Object.values(workDays).filter(Boolean).length} أيام دراسة</span></div>
                  <div className="flex items-center gap-2"><div className="w-4 h-4 rounded-full bg-slate-200"></div><span className="text-sm text-slate-600">{Object.values(workDays).filter(v => !v).length} أيام عطلة</span></div>
                </div>
                <Button onClick={saveAllSettings} disabled={saving} className="bg-[#1C3D74] hover:bg-[#152d57] px-8" data-testid="save-workdays-btn">
                  <Save className="h-4 w-4 ml-2" />{saving ? 'جاري الحفظ...' : 'حفظ التغييرات'}
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
              <div className="mt-6 flex justify-end">
                <Button onClick={saveAllSettings} disabled={saving} className="bg-[#1C3D74] hover:bg-[#152d57] px-8" data-testid="save-timings-btn">
                  <Save className="h-4 w-4 ml-2" />{saving ? 'جاري الحفظ...' : 'حفظ التغييرات'}
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-white shadow-sm">
            <CardContent className="p-5">
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                  <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${timeSlotsCount > 0 ? 'bg-emerald-100' : 'bg-amber-100'}`}>
                    <Timer className={`h-6 w-6 ${timeSlotsCount > 0 ? 'text-emerald-600' : 'text-amber-600'}`} />
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-800">الفترات الزمنية للجدول</h3>
                    <p className="text-sm text-slate-500 mt-0.5">
                      {timeSlotsCount === null ? 'جاري التحقق...' : timeSlotsCount === 0 ? 'لا توجد فترات زمنية — اضغط "توليد" لإنشائها تلقائياً من إعدادات التوقيت' : `${timeSlotsCount} فترة زمنية مُعرَّفة للجدول`}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {timeSlotsCount > 0 && <Badge className="bg-emerald-100 text-emerald-700 border-0"><CheckCircle2 className="h-3 w-3 ml-1" />جاهز</Badge>}
                  <Button onClick={generateTimeSlots} disabled={generatingSlots} variant={timeSlotsCount > 0 ? 'outline' : 'default'} className={timeSlotsCount > 0 ? '' : 'bg-[#1C3D74] hover:bg-[#152d57]'} data-testid="generate-time-slots-btn">
                    {generatingSlots ? <RefreshCw className="h-4 w-4 ml-2 animate-spin" /> : <Wand2 className="h-4 w-4 ml-2" />}
                    {timeSlotsCount > 0 ? 'إعادة توليد' : 'توليد الفترات'}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="breaks" className="space-y-6">
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
                  <div key={breakTime.id} className={`flex items-center justify-between p-4 rounded-xl border ${breakTime.type === 'prayer' ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'}`}>
                    <div className="flex items-center gap-4">
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${breakTime.type === 'prayer' ? 'bg-emerald-500 text-white' : 'bg-amber-500 text-white'}`}>
                        {breakTime.type === 'prayer' ? <Moon className="h-5 w-5" /> : <Coffee className="h-5 w-5" />}
                      </div>
                      <div>
                        <p className="font-medium">{breakTime.name}</p>
                        <p className="text-sm text-slate-500">بعد الحصة {breakTime.afterPeriod} • {breakTime.duration} دقيقة</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button variant="ghost" size="sm" onClick={() => handleEditBreak(breakTime)} data-testid={`edit-break-${breakTime.id}`}><Edit2 className="h-4 w-4" /></Button>
                      <Button variant="ghost" size="sm" className="text-red-500" onClick={() => handleDeleteBreak(breakTime.id)} data-testid={`delete-break-${breakTime.id}`}><Trash2 className="h-4 w-4" /></Button>
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-6 flex justify-end">
                <Button onClick={saveAllSettings} disabled={saving} className="bg-[#1C3D74] hover:bg-[#152d57] px-8" data-testid="save-breaks-btn">
                  <Save className="h-4 w-4 ml-2" />{saving ? 'جاري الحفظ...' : 'حفظ التغييرات'}
                </Button>
              </div>
            </CardContent>
          </Card>
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
                <Badge variant="outline" className="bg-brand-turquoise/10 text-brand-turquoise border-brand-turquoise/30"><Database className="h-3 w-3 ml-1" />بيانات من قاعدة البيانات</Badge>
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
                  <p className="text-xs text-slate-500">{classAssignments.length} إسناد</p>
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
                      .then(res => { const realId = res.data?.id || res.data?.assignment_id || tempId; setAssignments(prev => prev.map(a => a.id === tempId ? { ...a, id: realId, _optimistic: false } : a)); })
                      .catch(err => { setAssignments(prev => prev.filter(a => a.id !== tempId)); });
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
                    <Badge variant="outline" className="bg-brand-purple/10 text-brand-purple border-brand-purple/30 text-xs"><Zap className="h-3 w-3 ml-1" />سحب وإفلات</Badge>
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
                        <p className="text-xs text-slate-600">{teachers.length} معلم • {classes.length} فصل • {classAssignments.length} إسناد</p>
                      </div>
                    </div>
                    <Badge variant="outline" className="bg-brand-turquoise/10 text-brand-turquoise-dark border-brand-turquoise/30 text-xs"><Zap className="h-3 w-3 ml-1" />سحب وإفلات</Badge>
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
                      <div key={item.id} className="flex items-center justify-between p-3 bg-amber-50 rounded-lg border border-amber-200">
                        <span className="text-sm">{item.teacher_name} - {item.day} - الحصة {item.period}</span>
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
                      <div key={item.id} className="flex items-center justify-between p-3 bg-red-50 rounded-lg border border-red-200">
                        <span className="text-sm">{item.class_name} - {item.day} - الحصة {item.period}</span>
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
            activeHardTab={activeHardTab}
            setActiveHardTab={setActiveHardTab}
            activeSoftTab={activeSoftTab}
            setActiveSoftTab={setActiveSoftTab}
            handleSoftConstraintToggle={handleSoftConstraintToggle}
            handleSoftConstraintWeight={handleSoftConstraintWeight}
            toggleAllConstraints={toggleAllConstraints}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function ConstraintsPanel({ hardConstraints, softConstraints, activeHardTab, setActiveHardTab, activeSoftTab, setActiveSoftTab, handleSoftConstraintToggle, handleSoftConstraintWeight, toggleAllConstraints }) {
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

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <div className="flex flex-col">
        <div className="bg-gradient-to-br from-red-50 to-rose-50 border-2 border-red-200 rounded-2xl overflow-hidden flex flex-col h-full">
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
          <div className="flex-1 overflow-y-auto p-3 space-y-2" style={{ maxHeight: '520px' }}>
            {filteredHard.length === 0 ? (
              <div className="text-center py-8 text-slate-400"><Shield className="h-10 w-10 mx-auto mb-2 opacity-40" /><p className="text-sm">{hardConstraints.length === 0 ? 'لا توجد قيود إلزامية' : 'لا توجد قيود في هذا التصنيف'}</p></div>
            ) : (
              filteredHard.map(c => {
                const catInfo = hardCategoryLabels[c.category] || { label: c.category, color: 'slate' };
                return (
                  <div key={c.code} className={`flex items-start gap-2.5 p-3 rounded-xl border ${bgColors[catInfo.color] || bgColors.slate}`}>
                    <div className="w-7 h-7 rounded-lg bg-white border flex items-center justify-center shadow-sm flex-shrink-0 mt-0.5"><Lock className="h-3.5 w-3.5 text-red-500" /></div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-[10px] font-mono bg-white/60 px-1.5 py-0.5 rounded border text-slate-500">{c.code}</span>
                        <span className="text-sm font-semibold text-slate-800">{c.name_ar}</span>
                      </div>
                      <p className="text-xs text-slate-500 leading-relaxed">{c.description_ar}</p>
                      {c.can_disable && <Badge className="mt-1.5 bg-yellow-100 text-yellow-700 border border-yellow-300 text-[10px]">قابل للتعطيل</Badge>}
                    </div>
                    <CheckCircle2 className="h-4 w-4 text-emerald-500 flex-shrink-0 mt-1" />
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      <div className="flex flex-col">
        <div className="bg-gradient-to-br from-amber-50 to-orange-50 border-2 border-amber-200 rounded-2xl overflow-hidden flex flex-col h-full">
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
              <p className="text-xs text-amber-600/80">تؤثر على جودة الجدول — يمكن تفعيلها وضبط أولويتها</p>
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
          <div className="flex-1 overflow-y-auto p-3 space-y-2.5" style={{ maxHeight: '520px' }}>
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
                        <div className="flex gap-1.5 mt-1.5 me-12">
                          {[{label:'منخفض', val:3},{label:'متوسط', val:6},{label:'عالي', val:9}].map(p => (
                            <button key={p.val} onClick={() => handleSoftConstraintWeight(c.code, p.val)} className={`text-[10px] px-2 py-0.5 rounded-md border transition-all ${c.weight === p.val ? 'bg-amber-500 text-white border-amber-500' : 'bg-white text-slate-500 border-slate-200 hover:border-amber-300'}`}>{p.label}</button>
                          ))}
                        </div>
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
      </div>
    </div>
  );
}
