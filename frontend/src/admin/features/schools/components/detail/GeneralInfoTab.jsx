import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Badge } from '@/shared/components/ui/badge';
import {
  Building2, Hash, Shield, Calendar, Mail, Phone, MapPin,
  Edit, Save, X, Loader2, AlertTriangle
} from 'lucide-react';
import { SCHOOL_STATUS } from '../../constants/schoolConstants';
import SchoolCredentialsCard from './SchoolCredentialsCard';

function InfoField({ label, value, icon, mono }) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-bold text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
        {icon}
        <span>{label}</span>
      </label>
      <div className={`p-3 rounded-2xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-800 text-xs font-medium text-slate-900 dark:text-white ${mono ? 'font-mono' : ''}`}>
        {value || <span className="text-slate-400">—</span>}
      </div>
    </div>
  );
}

function EditableField({ label, value, displayValue, editMode, onChange, icon }) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-bold text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
        {icon}
        <span>{label}</span>
      </label>
      {editMode ? (
        <Input
          value={value || ''}
          onChange={(e) => onChange(e.target.value)}
          className="h-11 rounded-xl text-xs font-medium bg-white dark:bg-slate-950 border-slate-300 dark:border-slate-700 text-slate-900 dark:text-white focus:ring-2 focus:ring-[#46C1BE]/20 focus:border-[#46C1BE]"
        />
      ) : (
        <div className="p-3 rounded-2xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-800 text-xs font-medium text-slate-900 dark:text-white">
          {displayValue || <span className="text-slate-400">—</span>}
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
    <div className="space-y-6">
      {/* General Information Card */}
      <Card className="rounded-3xl border-slate-200 dark:border-slate-800 shadow-sm bg-white dark:bg-slate-900 overflow-hidden">
        <CardHeader className="flex flex-row items-center justify-between border-b border-slate-100 dark:border-slate-800/80 pb-4">
          <CardTitle className="font-cairo text-base font-extrabold text-slate-900 dark:text-white flex items-center gap-2">
            <Building2 className="h-5 w-5 text-[#1C3D74] dark:text-[#46C1BE]" />
            <span>{isRTL ? 'المعلومات العامة للمدرسة' : 'General School Information'}</span>
          </CardTitle>
          {!editMode ? (
            <Button
              size="sm"
              variant="outline"
              onClick={() => setEditMode(true)}
              className="rounded-xl h-9 px-3.5 font-bold text-xs border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-200"
            >
              <Edit className={`h-3.5 w-3.5 ${isRTL ? 'ms-1.5' : 'me-1.5'}`} />
              <span>{t('edit') || (isRTL ? 'تعديل البيانات' : 'Edit')}</span>
            </Button>
          ) : (
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => setEditMode(false)}
                className="rounded-xl h-9 px-3 text-xs font-bold border-slate-300 dark:border-slate-700"
              >
                <X className={`h-3.5 w-3.5 ${isRTL ? 'ms-1.5' : 'me-1.5'}`} />
                <span>{t('cancel') || (isRTL ? 'إلغاء' : 'Cancel')}</span>
              </Button>
              <Button
                size="sm"
                className="rounded-xl h-9 px-4 bg-[#1C3D74] hover:bg-[#152e57] text-white font-extrabold text-xs shadow-md shadow-[#1C3D74]/20"
                onClick={onSave}
                disabled={saving}
              >
                {saving ? (
                  <Loader2 className={`h-3.5 w-3.5 animate-spin ${isRTL ? 'ms-1.5' : 'me-1.5'}`} />
                ) : (
                  <Save className={`h-3.5 w-3.5 ${isRTL ? 'ms-1.5' : 'me-1.5'}`} />
                )}
                <span>{t('save') || (isRTL ? 'حفظ التعديلات' : 'Save Changes')}</span>
              </Button>
            </div>
          )}
        </CardHeader>

        <CardContent className="pt-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* School Code */}
            <InfoField
              label={t('schoolCode') || (isRTL ? 'كود المستأجر' : 'Tenant Code')}
              value={school?.code}
              icon={<Hash className="h-4 w-4 text-[#46C1BE]" />}
              mono
            />

            {/* School System ID */}
            <InfoField
              label={t('schoolId') || (isRTL ? 'المعرّف الداخلي' : 'School ID')}
              value={school?.id}
              icon={<Shield className="h-4 w-4 text-[#1C3D74] dark:text-[#46C1BE]" />}
              mono
            />

            {/* Creation Date */}
            <InfoField
              label={t('createdAt') || (isRTL ? 'تاريخ الإنشاء' : 'Created At')}
              value={school?.created_at ? new Date(school.created_at).toLocaleDateString(isRTL ? 'ar-SA' : 'en-GB') : '—'}
              icon={<Calendar className="h-4 w-4 text-slate-400" />}
            />

            {/* Current Status */}
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-slate-600 dark:text-slate-400 flex items-center gap-1.5">
                <Shield className="h-4 w-4 text-slate-400" />
                <span>{t('status2') || (isRTL ? 'الحالة الحالية' : 'Current Status')}</span>
              </label>
              <div className="p-3 rounded-2xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-800">
                <Badge className={`text-xs font-bold ${statusCfg.badge}`}>
                  <div className={`w-1.5 h-1.5 rounded-full ${statusCfg.dot} ${isRTL ? 'ms-1.5' : 'me-1.5'}`} />
                  <span>{isRTL ? statusCfg.label : statusCfg.label_en}</span>
                </Badge>
              </div>
            </div>

            {/* Arabic Name */}
            <EditableField
              label={t('schoolNameArabic') || (isRTL ? 'اسم المدرسة (بالعربية)' : 'School Name (Arabic)')}
              value={editData.name}
              displayValue={school?.name}
              editMode={editMode}
              onChange={(v) => setEditData(d => ({ ...d, name: v }))}
              icon={<Building2 className="h-4 w-4 text-slate-400" />}
            />

            {/* English Name */}
            <EditableField
              label={t('schoolNameEnglish2') || (isRTL ? 'اسم المدرسة (بالإنجليزية)' : 'School Name (English)')}
              value={editData.name_en}
              displayValue={school?.name_en}
              editMode={editMode}
              onChange={(v) => setEditData(d => ({ ...d, name_en: v }))}
              icon={<Building2 className="h-4 w-4 text-slate-400" />}
            />

            {/* Official Email */}
            <EditableField
              label={t('email2') || (isRTL ? 'البريد الرسمي للمدرسة' : 'Official Email')}
              value={editData.email}
              displayValue={school?.email}
              editMode={editMode}
              onChange={(v) => setEditData(d => ({ ...d, email: v }))}
              icon={<Mail className="h-4 w-4 text-slate-400" />}
            />

            {/* Contact Phone */}
            <EditableField
              label={t('phone2') || (isRTL ? 'رقم هاتف التواصل' : 'Contact Phone')}
              value={editData.phone}
              displayValue={school?.phone}
              editMode={editMode}
              onChange={(v) => setEditData(d => ({ ...d, phone: v }))}
              icon={<Phone className="h-4 w-4 text-slate-400" />}
            />

            {/* City */}
            <EditableField
              label={t('city') || (isRTL ? 'المدينة' : 'City')}
              value={editData.city}
              displayValue={school?.city}
              editMode={editMode}
              onChange={(v) => setEditData(d => ({ ...d, city: v }))}
              icon={<MapPin className="h-4 w-4 text-slate-400" />}
            />

            {/* Region */}
            <EditableField
              label={t('region2') || (isRTL ? 'المنطقة الإدارية' : 'Administrative Region')}
              value={editData.region}
              displayValue={school?.region}
              editMode={editMode}
              onChange={(v) => setEditData(d => ({ ...d, region: v }))}
              icon={<MapPin className="h-4 w-4 text-slate-400" />}
            />

            {/* Suspension Reason Info Alert */}
            {school?.suspension_reason && (
              <div className="col-span-full p-4 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/80 rounded-2xl space-y-1 shadow-xs">
                <p className="text-xs font-bold text-rose-700 dark:text-rose-300 flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-rose-600" />
                  <span>{t('suspensionReason') || (isRTL ? 'سبب تعليق الحساب' : 'Suspension Reason')}</span>
                </p>
                <p className="text-xs text-rose-600 dark:text-rose-400 font-medium">{school.suspension_reason}</p>
                {school.suspended_at && (
                  <p className="text-[11px] text-rose-500 font-mono">
                    {new Date(school.suspended_at).toLocaleString(isRTL ? 'ar-SA' : 'en-GB')}
                  </p>
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Login Credentials Card */}
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
