import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { Coffee, UserX, DoorClosed, Upload, FileSpreadsheet, CheckCircle2, AlertCircle, X, Loader2, Download, Calendar } from 'lucide-react';
import { toast } from 'sonner';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';
import { useNassaqAlert } from '../ui/NassaqAlertDialog';
import { getApiErrorMessage } from '../../utils/apiError';

function BreakModal({ hook }) {
  const { t } = useTranslation();
  const { direction } = useTheme();
  const {
    showBreakModal, setShowBreakModal, editingBreak, handleSaveBreak,
  } = hook;

  const [breakType, setBreakType] = useState(editingBreak?.type || 'break');
  const [customType, setCustomType] = useState(editingBreak?.customType || '');
  const [durationMode, setDurationMode] = useState(() => {
    const dur = editingBreak?.duration;
    if (dur && ![5, 10, 15, 20, 25, 30].includes(dur)) return 'custom';
    return 'preset';
  });
  const [customDuration, setCustomDuration] = useState(editingBreak?.duration || 15);
  const [presetDuration, setPresetDuration] = useState(() => {
    const dur = editingBreak?.duration;
    if (dur && [5, 10, 15, 20, 25, 30].includes(dur)) return String(dur);
    return '15';
  });
  const [selectedDay, setSelectedDay] = useState(editingBreak?.day || 'all');

  useEffect(() => {
    setBreakType(editingBreak?.type || 'break');
    setCustomType(editingBreak?.customType || '');
    const dur = editingBreak?.duration;
    if (dur && ![5, 10, 15, 20, 25, 30].includes(dur)) {
      setDurationMode('custom');
      setCustomDuration(dur);
    } else {
      setDurationMode('preset');
      setPresetDuration(dur ? String(dur) : '15');
    }
    setSelectedDay(editingBreak?.day || 'all');
  }, [editingBreak, showBreakModal]);

  if (!showBreakModal) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" dir={direction}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
        <div className="p-6 border-b">
          <h3 className="text-lg font-bold flex items-center gap-2">
            <Coffee className="h-5 w-5 text-[#1C3D74]" />
            {editingBreak ? t('editPeriod') : t('addNewPeriod')}
          </h3>
        </div>
        <form onSubmit={(e) => {
          e.preventDefault();
          const formData = new FormData(e.target);
          const duration = durationMode === 'custom' ? parseInt(customDuration) : parseInt(presetDuration);
          handleSaveBreak({
            name: formData.get('name'),
            type: breakType,
            customType: breakType === 'other' ? customType : undefined,
            afterPeriod: parseInt(formData.get('afterPeriod')),
            duration: duration,
            day: selectedDay,
          });
        }} className="p-6 space-y-4">
          <div>
            <Label>{t('periodNameLabel')}</Label>
            <Input name="name" defaultValue={editingBreak?.name || ''} placeholder={t('periodNameExample')} required className="mt-1" />
          </div>
          <div>
            <Label>{t('periodTypeLabel')}</Label>
            <Select value={breakType} onValueChange={setBreakType}>
              <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="break">{t('breakType')}</SelectItem>
                <SelectItem value="prayer">{t('prayerType')}</SelectItem>
                <SelectItem value="other">{t('otherType')}</SelectItem>
              </SelectContent>
            </Select>
            {breakType === 'other' && (
              <Input
                value={customType}
                onChange={(e) => setCustomType(e.target.value)}
                placeholder={t('writePeriodType')}
                required
                className="mt-2"
              />
            )}
          </div>
          <div>
            <Label>{t('schoolDayLabel')}</Label>
            <Select value={selectedDay} onValueChange={setSelectedDay}>
              <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('allDays')}</SelectItem>
                <SelectItem value="الأحد">{t('sunday')}</SelectItem>
                <SelectItem value="الإثنين">{t('monday')}</SelectItem>
                <SelectItem value="الثلاثاء">{t('tuesday')}</SelectItem>
                <SelectItem value="الأربعاء">{t('wednesday')}</SelectItem>
                <SelectItem value="الخميس">{t('thursday')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>{t('afterPeriodNumber')}</Label>
              <Select name="afterPeriod" defaultValue={String(editingBreak?.afterPeriod || 2)}>
                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {[1,2,3,4,5,6,7,8].map(n => <SelectItem key={n} value={String(n)}>{n}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>{t('durationMinutes')}</Label>
              <Select value={durationMode === 'custom' ? 'custom' : presetDuration} onValueChange={(v) => {
                if (v === 'custom') {
                  setDurationMode('custom');
                } else {
                  setDurationMode('preset');
                  setPresetDuration(v);
                }
              }}>
                <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {[5, 10, 15, 20, 25, 30].map(n => <SelectItem key={n} value={String(n)}>{n} {t('minuteUnit')}</SelectItem>)}
                  <SelectItem value="custom">{t('customizeDuration')}</SelectItem>
                </SelectContent>
              </Select>
              {durationMode === 'custom' && (
                <Input
                  type="number"
                  min="1"
                  max="120"
                  value={customDuration}
                  onChange={(e) => setCustomDuration(e.target.value)}
                  placeholder={t('enterDurationMinutes')}
                  required
                  className="mt-2"
                />
              )}
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button type="button" variant="outline" onClick={() => setShowBreakModal(false)}>{t('cancel')}</Button>
            <Button type="submit" className="bg-[#1C3D74]">{editingBreak ? t('updateBtn') : t('addBtn')}</Button>
          </div>
        </form>
      </div>
    </div>
  );
}

function NoorImportModal({ show, onClose, importType, api, onSuccess }) {
  const { t } = useTranslation();
  const { direction } = useTheme();
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const fileInputRef = useRef(null);

  const importTypeMap = {
    noor_classes: { label: t('noorClassesLabel'), endpoint: 'noor_classes', color: 'brand-navy' },
    noor_assignments: { label: t('noorAssignmentsLabel'), endpoint: 'noor_assignments', color: 'brand-purple' },
  };

  const config = importTypeMap[importType] || importTypeMap.noor_classes;

  useEffect(() => {
    if (show) {
      setFile(null);
      setResult(null);
      setUploading(false);
    }
  }, [show]);

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    if (selected) {
      const validTypes = ['.xlsx', '.xls', '.csv'];
      const ext = selected.name.substring(selected.name.lastIndexOf('.')).toLowerCase();
      if (!validTypes.includes(ext)) {
        toast.error(t('selectExcelOrCsv'));
        return;
      }
      setFile(selected);
      setResult(null);
    }
  };

  const handleUpload = async () => {
    if (!file || !api) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await api.post(`/bulk/import/${config.endpoint}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setResult(res.data);
      if (res.data.imported > 0) {
        toast.success(t('imported_n_items', { n: res.data.imported }));
        if (onSuccess) onSuccess();
      }
    } catch (err) {
      const detail = getApiErrorMessage(err) || t('errorDuringImport');
      toast.error(detail);
      setResult({ success: false, total_rows: 0, imported: 0, failed: 0, errors: [{ message: detail }], warnings: [] });
    } finally {
      setUploading(false);
    }
  };

  const handleDownloadTemplate = async () => {
    if (!api) return;
    try {
      const res = await api.get(`/bulk/template/${config.endpoint}`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${t('noorTemplateFilePrefix')}_${config.label}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(t('templateDownloadError'));
    }
  };

  if (!show) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" dir={direction}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg">
        <div className="p-6 border-b flex items-center justify-between">
          <h3 className="text-lg font-bold flex items-center gap-2">
            <FileSpreadsheet className="h-5 w-5 text-green-600" />
            {t('noorImportTitle')} — {config.label}
          </h3>
          <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="p-6 space-y-4">
          <div className="p-3 bg-blue-50 rounded-xl border border-blue-200">
            <p className="text-xs text-blue-700">
              {t('noorImportInstructions', { label: config.label })}
            </p>
          </div>

          <Button variant="outline" size="sm" className="gap-2" onClick={handleDownloadTemplate}>
            <Download className="h-4 w-4" />
            {t('downloadImportTemplate')}
          </Button>

          <div
            className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer ${
              file ? 'border-green-300 bg-green-50' : 'border-slate-300 hover:border-blue-400 bg-slate-50'
            }`}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.xls,.csv"
              onChange={handleFileChange}
              className="hidden"
            />
            {file ? (
              <div className="flex flex-col items-center gap-2">
                <FileSpreadsheet className="h-10 w-10 text-green-600" />
                <p className="font-medium text-green-700">{file.name}</p>
                <p className="text-xs text-green-600">{(file.size / 1024).toFixed(1)} KB</p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <Upload className="h-10 w-10 text-slate-400" />
                <p className="text-sm text-slate-600">{t('clickOrDragFile')}</p>
                <p className="text-xs text-slate-400">{t('excelOrCsvFormats')}</p>
              </div>
            )}
          </div>

          {result && (
            <div className={`p-4 rounded-xl border ${result.imported > 0 ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
              <div className="flex items-center gap-2 mb-2">
                {result.imported > 0 ? (
                  <CheckCircle2 className="h-5 w-5 text-green-600" />
                ) : (
                  <AlertCircle className="h-5 w-5 text-red-600" />
                )}
                <span className="font-bold text-sm">{result.imported > 0 ? t('importSuccessLabel') : t('importFailedLabel')}</span>
              </div>
              <div className="grid grid-cols-3 gap-2 text-center text-xs">
                <div className="p-2 bg-white rounded-lg">
                  <p className="font-bold text-slate-700">{result.total_rows || 0}</p>
                  <p className="text-slate-500">{t('totalRows')}</p>
                </div>
                <div className="p-2 bg-white rounded-lg">
                  <p className="font-bold text-green-700">{result.imported || 0}</p>
                  <p className="text-green-600">{t('importedRows')}</p>
                </div>
                <div className="p-2 bg-white rounded-lg">
                  <p className="font-bold text-red-700">{result.failed || 0}</p>
                  <p className="text-red-600">{t('failedRows')}</p>
                </div>
              </div>
              {result.errors?.length > 0 && (
                <div className="mt-2 max-h-32 overflow-y-auto">
                  {result.errors.slice(0, 5).map((err, i) => (
                    <p key={i} className="text-xs text-red-600 mt-1">
                      {err.row ? `${t('rowPrefix')} ${err.row}: ` : ''}{err.field ? `${err.field} - ` : ''}{err.message}
                    </p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="p-6 border-t flex justify-end gap-3">
          <Button variant="outline" onClick={onClose}>{t('close')}</Button>
          <Button
            onClick={handleUpload}
            disabled={!file || uploading}
            className="bg-green-600 hover:bg-green-700 text-white gap-2"
          >
            {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            {uploading ? t('importingNow') : t('startImport')}
          </Button>
        </div>
      </div>
    </div>
  );
}

export function SettingsModals({ hook }) {
  const { t } = useTranslation();
  const { direction } = useTheme();
  const {
    showUnavailabilityModal, setShowUnavailabilityModal, unavailabilityType,
    handleSaveUnavailability, teachers, classes,
    showNoorImportModal, setShowNoorImportModal, noorImportType,
    api, fetchData,
  } = hook;

  const { nassaqError } = useNassaqAlert();
  const todayISO = useMemo(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }, []);
  const isRTL = direction === 'rtl';
  const [unavailMode, setUnavailMode] = useState('recurring');
  const [selectedEntityId, setSelectedEntityId] = useState('');

  useEffect(() => {
    if (showUnavailabilityModal) {
      setUnavailMode('recurring');
      setSelectedEntityId('');
    }
  }, [showUnavailabilityModal]);

  const getEntityName = () => {
    if (!selectedEntityId) return '';
    if (unavailabilityType === 'teacher') {
      const teach = teachers.find(t2 => t2.id === selectedEntityId);
      return teach?.full_name || '';
    } else {
      const c = classes.find(c2 => c2.id === selectedEntityId);
      return c ? `${c.name} - ${c.section || ''}` : '';
    }
  };

  return (
    <>
      <BreakModal hook={hook} />

      <NoorImportModal
        show={showNoorImportModal}
        onClose={() => setShowNoorImportModal(false)}
        importType={noorImportType}
        api={api}
        onSuccess={fetchData}
      />

      {showUnavailabilityModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" dir={direction}>
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
            <div className="p-6 border-b">
              <h3 className="text-lg font-bold flex items-center gap-2">
                {unavailabilityType === 'teacher' ? <UserX className="h-5 w-5 text-amber-600" /> : <DoorClosed className="h-5 w-5 text-red-600" />}
                {t('addUnavailabilityFor', { target: unavailabilityType === 'teacher' ? t('teacherWord') : t('classWord') })}
              </h3>
            </div>
            <form onSubmit={(e) => {
              e.preventDefault();
              const entityName = getEntityName();
              const formData = new FormData(e.target);
              const altLocation = unavailabilityType === 'class'
                ? (formData.get('alternative_location') || '').toString().trim()
                : '';
              if (unavailMode === 'recurring') {
                handleSaveUnavailability({
                  [unavailabilityType === 'teacher' ? 'teacher_id' : 'class_id']: selectedEntityId,
                  [unavailabilityType === 'teacher' ? 'teacher_name' : 'class_name']: entityName,
                  unavailability_type: 'recurring',
                  day: formData.get('day'),
                  period: formData.get('period'),
                  alternative_location: altLocation || null,
                });
              } else {
                const startDate = formData.get('start_date');
                const endDate = formData.get('end_date');
                if (startDate && startDate < todayISO) {
                  nassaqError(
                    isRTL ? 'تاريخ غير صالح' : 'Invalid Date',
                    isRTL ? 'لا يمكن تحديد بداية عدم التوفر في الماضي' : 'Unavailability cannot start in the past.',
                  );
                  return;
                }
                if (endDate && endDate < todayISO) {
                  nassaqError(
                    isRTL ? 'تاريخ غير صالح' : 'Invalid Date',
                    isRTL ? 'لا يمكن تحديد نهاية عدم التوفر في الماضي' : 'Unavailability cannot end in the past.',
                  );
                  return;
                }
                handleSaveUnavailability({
                  [unavailabilityType === 'teacher' ? 'teacher_id' : 'class_id']: selectedEntityId,
                  [unavailabilityType === 'teacher' ? 'teacher_name' : 'class_name']: entityName,
                  unavailability_type: 'long_term',
                  start_date: startDate,
                  end_date: endDate,
                  reason: formData.get('reason') || '',
                  alternative_location: altLocation || null,
                });
              }
            }} className="p-6 space-y-4">
              <div>
                <Label>{unavailabilityType === 'teacher' ? t('selectTeacher') : t('selectClass')}</Label>
                <Select value={selectedEntityId} onValueChange={setSelectedEntityId} required>
                  <SelectTrigger className="mt-1"><SelectValue placeholder={unavailabilityType === 'teacher' ? t('selectTeacherPlaceholder') : t('selectClassPlaceholder')} /></SelectTrigger>
                  <SelectContent>
                    {unavailabilityType === 'teacher'
                      ? teachers.map(tt => <SelectItem key={tt.id} value={tt.id}>{tt.full_name}</SelectItem>)
                      : classes.map(c => <SelectItem key={c.id} value={c.id}>{c.name} - {c.section}</SelectItem>)
                    }
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label className="mb-2 block">{t('unavailabilityType')}</Label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setUnavailMode('recurring')}
                    className={`p-3 rounded-lg border-2 text-center transition-all ${
                      unavailMode === 'recurring'
                        ? 'border-amber-500 bg-amber-50 text-amber-700'
                        : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                    }`}
                  >
                    <Calendar className="h-5 w-5 mx-auto mb-1" />
                    <p className="text-xs font-bold">{t('recurring')}</p>
                    <p className="text-[10px]">{t('recurringHint')}</p>
                  </button>
                  <button
                    type="button"
                    onClick={() => setUnavailMode('long_term')}
                    className={`p-3 rounded-lg border-2 text-center transition-all ${
                      unavailMode === 'long_term'
                        ? 'border-red-500 bg-red-50 text-red-700'
                        : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                    }`}
                  >
                    <Calendar className="h-5 w-5 mx-auto mb-1" />
                    <p className="text-xs font-bold">{t('longTerm')}</p>
                    <p className="text-[10px]">{t('longTermHint')}</p>
                  </button>
                </div>
              </div>

              {unavailMode === 'recurring' ? (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>{t('dayLabel')}</Label>
                    <Select name="day" required>
                      <SelectTrigger className="mt-1"><SelectValue placeholder={t('selectDayPlaceholder')} /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="الأحد">{t('sunday')}</SelectItem>
                        <SelectItem value="الإثنين">{t('monday')}</SelectItem>
                        <SelectItem value="الثلاثاء">{t('tuesday')}</SelectItem>
                        <SelectItem value="الأربعاء">{t('wednesday')}</SelectItem>
                        <SelectItem value="الخميس">{t('thursday')}</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>{t('periodLabel')}</Label>
                    <Select name="period" required>
                      <SelectTrigger className="mt-1"><SelectValue placeholder={t('selectPeriodPlaceholder')} /></SelectTrigger>
                      <SelectContent>
                        {[1,2,3,4,5,6,7].map(n => <SelectItem key={n} value={String(n)}>{t('periodPrefix')} {n}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>{t('startDateLabel')}</Label>
                      <Input type="date" name="start_date" min={todayISO} required className="mt-1" />
                    </div>
                    <div>
                      <Label>{t('endDateLabel')}</Label>
                      <Input type="date" name="end_date" min={todayISO} required className="mt-1" />
                    </div>
                  </div>
                  <div>
                    <Label>{t('reasonOptional')}</Label>
                    <Input name="reason" placeholder={t('reasonPlaceholder')} className="mt-1" />
                  </div>
                </div>
              )}

              {unavailabilityType === 'class' && (
                <div>
                  <Label>{t('alternativeLocationOptional')}</Label>
                  <Input
                    name="alternative_location"
                    placeholder={t('alternativeLocationPlaceholder')}
                    className="mt-1"
                    data-testid="input-alternative-location"
                  />
                  <p className="text-[11px] text-slate-500 mt-1">
                    {t('alternativeLocationHelp')}
                  </p>
                </div>
              )}

              <div className="flex justify-end gap-3 pt-4">
                <Button type="button" variant="outline" onClick={() => setShowUnavailabilityModal(false)}>{t('cancel')}</Button>
                <Button type="submit" disabled={!selectedEntityId} className={unavailabilityType === 'teacher' ? 'bg-amber-600' : 'bg-red-600'}>{t('addBtn')}</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
