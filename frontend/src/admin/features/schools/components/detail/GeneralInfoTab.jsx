import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Badge } from '@/shared/components/ui/badge';
import {
  Building2, Hash, Shield, Calendar, Mail, Phone, MapPin,
  Edit3, Save, X, Loader2, AlertTriangle, CheckCircle2, Globe
} from 'lucide-react';
import { SCHOOL_STATUS } from '../../constants/schoolConstants';
import SchoolCredentialsCard from './SchoolCredentialsCard';

function InfoTile({ label, value, icon, mono = false, isRTL = true }) {
  return (
    <div className="p-3.5 rounded-xl bg-slate-50/80 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-800 transition-all hover:bg-slate-100/60 dark:hover:bg-slate-800/70">
      <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1">
        {icon}
        <span>{label}</span>
      </div>
      <div className={`text-xs sm:text-sm font-bold text-slate-900 dark:text-slate-100 ${mono ? 'font-mono' : ''} truncate`} dir={mono ? 'ltr' : undefined}>
        {value || <span className="text-slate-400 font-normal">—</span>}
      </div>
    </div>
  );
}

function EditableField({ label, value, displayValue, editMode, onChange, icon, dir, placeholder, type = 'text' }) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-bold text-slate-600 dark:text-slate-300 flex items-center gap-1.5">
        {icon}
        <span>{label}</span>
      </label>
      {editMode ? (
        <Input
          type={type}
          dir={dir}
          placeholder={placeholder}
          value={value || ''}
          onChange={(e) => onChange(e.target.value)}
          className="h-10 rounded-xl text-xs font-medium bg-white dark:bg-slate-950 border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-[#46C1BE]/20 focus:border-[#46C1BE] shadow-2xs"
        />
      ) : (
        <div className="p-3 rounded-xl bg-slate-50/80 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-800 text-xs font-bold text-slate-900 dark:text-white min-h-[42px] flex items-center">
          <span className="truncate" dir={dir}>{displayValue || <span className="text-slate-400 font-normal">—</span>}</span>
        </div>
      )}
    </div>
  );
}

export default function GeneralInfoTab({
  school,
  editMode,
  setEditMode,
  editData,
  setEditData,
  onSave,
  saving,
  principalAccount,
  hasCredentials,
  onOpenCredForm,
  credResult,
  onCopy,
  isRTL,
  t,
}) {
  const statusCfg = SCHOOL_STATUS[school?.status] || SCHOOL_STATUS.active;

  return (
    <div dir={isRTL ? 'rtl' : 'ltr'} className="space-y-6">
      {/* Suspension Alert if applicable */}
      {school?.suspension_reason && (
        <div className="p-4 bg-rose-50/90 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/80 rounded-2xl space-y-1.5 shadow-2xs animate-in fade-in-50 duration-300">
          <div className="flex items-center gap-2.5 text-rose-700 dark:text-rose-300 font-bold text-xs sm:text-sm">
            <div className="w-7 h-7 rounded-lg bg-rose-100 dark:bg-rose-900/60 flex items-center justify-center text-rose-600 dark:text-rose-400 shrink-0">
              <AlertTriangle className="h-4 w-4" />
            </div>
            <span>{t('suspensionReason') || (isRTL ? 'حساب المدرسة موقوف مؤقتاً' : 'School Account is Suspended')}</span>
          </div>
          <p className="text-xs text-rose-700/90 dark:text-rose-300/90 font-medium ps-9">
            {school.suspension_reason}
          </p>
          {school.suspended_at && (
            <p className="text-[11px] text-rose-500 font-mono ps-9">
              {new Date(school.suspended_at).toLocaleString(isRTL ? 'ar-SA' : 'en-GB')}
            </p>
          )}
        </div>
      )}

      {/* Bento Grid: 2 Main Columns */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Column 1 (Left 2 spans): Editable School Details */}
        <Card className="lg:col-span-2 rounded-2xl border-slate-200/90 dark:border-slate-800 shadow-sm bg-white dark:bg-slate-900 overflow-hidden">
          <CardHeader className="flex flex-row items-center justify-between border-b border-slate-100 dark:border-slate-800/80 pb-4">
            <CardTitle className="font-cairo text-sm sm:text-base font-extrabold text-slate-900 dark:text-white flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-blue-50 dark:bg-blue-950/60 text-[#1C3D74] dark:text-[#46C1BE] flex items-center justify-center shrink-0 border border-blue-100 dark:border-blue-900/60">
                <Building2 className="h-4 w-4" />
              </div>
              <span>{isRTL ? 'البيانات الأساسية ومعلومات الاتصال' : 'Basic Details & Contact'}</span>
            </CardTitle>

            {!editMode ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() => setEditMode(true)}
                className="rounded-xl h-9 px-4 font-bold text-xs border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-all gap-2"
              >
                <Edit3 className="h-3.5 w-3.5 text-[#1C3D74] dark:text-[#46C1BE]" />
                <span>{t('edit') || (isRTL ? 'تعديل البيانات' : 'Edit')}</span>
              </Button>
            ) : (
              <div className="flex items-center gap-2.5">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setEditMode(false)}
                  disabled={saving}
                  className="rounded-xl h-9 px-4 text-xs font-bold border-slate-200 dark:border-slate-700 gap-1.5"
                >
                  <X className="h-3.5 w-3.5" />
                  <span>{t('cancel') || (isRTL ? 'إلغاء' : 'Cancel')}</span>
                </Button>
                <Button
                  size="sm"
                  className="rounded-xl h-9 px-4 bg-[#1C3D74] hover:bg-[#152e57] text-white font-bold text-xs shadow-xs gap-2"
                  onClick={onSave}
                  disabled={saving}
                >
                  {saving ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Save className="h-3.5 w-3.5" />
                  )}
                  <span>{t('save') || (isRTL ? 'حفظ' : 'Save')}</span>
                </Button>
              </div>
            )}
          </CardHeader>

          <CardContent className="pt-6 pb-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              {/* Arabic Name */}
              <EditableField
                label={t('schoolNameArabic') || (isRTL ? 'اسم المدرسة (بالعربية)' : 'School Name (Arabic)')}
                value={editData.name}
                displayValue={school?.name}
                editMode={editMode}
                onChange={(v) => setEditData(d => ({ ...d, name: v }))}
                icon={<Building2 className="h-3.5 w-3.5 text-slate-400" />}
                placeholder="مثال: مدرسة الأفق الأهلية"
              />

              {/* English Name */}
              <EditableField
                label={t('schoolNameEnglish2') || (isRTL ? 'اسم المدرسة (بالإنجليزية)' : 'School Name (English)')}
                value={editData.name_en}
                displayValue={school?.name_en}
                editMode={editMode}
                onChange={(v) => setEditData(d => ({ ...d, name_en: v }))}
                icon={<Globe className="h-3.5 w-3.5 text-slate-400" />}
                dir="ltr"
                placeholder="e.g. Al-Ofoq Private School"
              />

              {/* Official Email */}
              <EditableField
                label={t('email2') || (isRTL ? 'البريد الرسمي للمدرسة' : 'Official Email')}
                value={editData.email}
                displayValue={school?.email}
                editMode={editMode}
                onChange={(v) => setEditData(d => ({ ...d, email: v }))}
                icon={<Mail className="h-3.5 w-3.5 text-slate-400" />}
                dir="ltr"
                type="email"
                placeholder="info@school.edu.sa"
              />

              {/* Contact Phone */}
              <EditableField
                label={t('phone2') || (isRTL ? 'رقم هاتف التواصل' : 'Contact Phone')}
                value={editData.phone}
                displayValue={school?.phone}
                editMode={editMode}
                onChange={(v) => setEditData(d => ({ ...d, phone: v }))}
                icon={<Phone className="h-3.5 w-3.5 text-slate-400" />}
                dir="ltr"
                placeholder="05xxxxxxxx / 011xxxxxxx"
              />

              {/* City */}
              <EditableField
                label={t('city') || (isRTL ? 'المدينة' : 'City')}
                value={editData.city}
                displayValue={school?.city}
                editMode={editMode}
                onChange={(v) => setEditData(d => ({ ...d, city: v }))}
                icon={<MapPin className="h-3.5 w-3.5 text-slate-400" />}
                placeholder="مثال: الرياض"
              />

              {/* Region */}
              <EditableField
                label={t('region2') || (isRTL ? 'المنطقة الإدارية' : 'Administrative Region')}
                value={editData.region}
                displayValue={school?.region}
                editMode={editMode}
                onChange={(v) => setEditData(d => ({ ...d, region: v }))}
                icon={<MapPin className="h-3.5 w-3.5 text-slate-400" />}
                placeholder="مثال: منطقة الرياض"
              />
            </div>
          </CardContent>
        </Card>

        {/* Column 2 (Right 1 span): System & Tenant Metadata */}
        <Card className="rounded-2xl border-slate-200/90 dark:border-slate-800 shadow-sm bg-white dark:bg-slate-900 overflow-hidden flex flex-col justify-between">
          <div>
            <CardHeader className="border-b border-slate-100 dark:border-slate-800/80 pb-4">
              <CardTitle className="font-cairo text-sm sm:text-base font-extrabold text-slate-900 dark:text-white flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-purple-50 dark:bg-purple-950/60 text-[#615090] dark:text-purple-300 flex items-center justify-center shrink-0 border border-purple-100 dark:border-purple-900/60">
                  <Shield className="h-4 w-4" />
                </div>
                <span>{isRTL ? 'بيانات النظام والترخيص' : 'System & License Info'}</span>
              </CardTitle>
            </CardHeader>

            <CardContent className="pt-5 space-y-3.5">
              {/* Tenant Code */}
              <InfoTile
                label={t('schoolCode') || (isRTL ? 'رمز المستأجر (Code)' : 'Tenant Code')}
                value={school?.code}
                icon={<Hash className="h-3.5 w-3.5 text-[#46C1BE]" />}
                mono
                isRTL={isRTL}
              />

              {/* Status Badge */}
              <div className="p-3 rounded-xl bg-slate-50/80 dark:bg-slate-800/40 border border-slate-200/70 dark:border-slate-800">
                <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 dark:text-slate-400 mb-1.5">
                  <CheckCircle2 className="h-3.5 w-3.5 text-slate-400" />
                  <span>{t('status2') || (isRTL ? 'حالة المدرسة' : 'Status')}</span>
                </div>
                <Badge className={`text-xs font-bold px-2.5 py-0.5 rounded-full ${statusCfg.badge}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${statusCfg.dot} me-1.5`} />
                  <span>{isRTL ? statusCfg.label : statusCfg.label_en}</span>
                </Badge>
              </div>

              {/* Creation Date */}
              <InfoTile
                label={t('createdAt') || (isRTL ? 'تاريخ التأسيس' : 'Created Date')}
                value={school?.created_at ? new Date(school.created_at).toLocaleDateString(isRTL ? 'ar-SA' : 'en-GB') : '—'}
                icon={<Calendar className="h-3.5 w-3.5 text-slate-400" />}
                isRTL={isRTL}
              />

              {/* Internal System ID */}
              <InfoTile
                label={t('schoolId') || (isRTL ? 'المعرّف الفريد للنظام' : 'System UUID')}
                value={school?.id}
                icon={<Shield className="h-3.5 w-3.5 text-slate-400" />}
                mono
                isRTL={isRTL}
              />
            </CardContent>
          </div>
        </Card>
      </div>

      {/* Principal Login Credentials Section */}
      <SchoolCredentialsCard
        principal={principalAccount}
        hasCreds={hasCredentials}
        onOpenCredForm={onOpenCredForm}
        credResult={credResult}
        onCopy={onCopy}
        isRTL={isRTL}
        t={t}
      />
    </div>
  );
}
