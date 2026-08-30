import React from 'react';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '@/shared/components/ui/select';
import {
  Building2, Upload, Globe, MapPin, FileText, Mail, Phone,
} from 'lucide-react';
import { COUNTRIES, ALL_SAUDI_CITIES } from '../../constants/schoolConstants';

function RequiredBadge({ text = 'إجباري' }) {
  return (
    <span className="text-[11px] font-bold text-rose-700 bg-rose-50 dark:bg-rose-950/80 dark:text-rose-300 border border-rose-200 dark:border-rose-800 px-2 py-0.5 rounded-md leading-none shadow-2xs">
      {text}
    </span>
  );
}

function OptionalBadge({ text = 'اختياري' }) {
  return (
    <span className="text-[11px] font-semibold text-slate-600 bg-slate-100 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700 px-2 py-0.5 rounded-md leading-none">
      {text}
    </span>
  );
}

export default function StepSchoolProfile({
  schoolData,
  setSchoolData,
  errors,
  clearFieldError,
  onLogoUpload,
  isRTL,
}) {
  return (
    <div className="flex flex-col max-w-4xl mx-auto animate-in fade-in-50 duration-300 font-tajawal" data-testid="wizard-step-1">
      {/* Title */}
      <div className="mb-6 text-start">
        <h3 className="font-cairo text-xl font-black text-slate-900 dark:text-white flex items-center gap-2">
          <Building2 className="h-5 w-5 text-[#46C1BE]" />
          <span>{isRTL ? 'بيانات المدرسة الأساسية' : 'Basic School Information'}</span>
        </h3>
        <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mt-1">
          {isRTL ? 'أدخل المعلومات الأساسية والموقع الجغرافي للمدرسة' : 'Enter the basic school information and physical location'}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 mb-5">
        {/* Logo Upload Card */}
        <div className="md:col-span-4 flex flex-col items-center justify-center p-5 bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="relative group w-28 h-28 rounded-2xl border-2 border-dashed border-slate-300 dark:border-slate-700 hover:border-[#46C1BE] hover:bg-[#46C1BE]/5 flex items-center justify-center overflow-hidden transition-all duration-200 bg-slate-50 dark:bg-slate-800/80">
            {schoolData.logoPreview ? (
              <img src={schoolData.logoPreview} alt="School Logo" className="w-full h-full object-cover" />
            ) : (
              <div className="text-center p-3">
                <Upload className="h-7 w-7 mx-auto text-slate-400 group-hover:text-[#46C1BE] mb-1.5 transition-colors" />
                <span className="text-xs font-bold text-slate-700 dark:text-slate-200 block">
                  {isRTL ? 'رفع الشعار' : 'Upload Logo'}
                </span>
              </div>
            )}
            <input
              type="file"
              accept="image/*"
              onChange={onLogoUpload}
              className="absolute inset-0 opacity-0 cursor-pointer"
              data-testid="logo-upload"
            />
          </div>
          <div className="mt-3 flex items-center gap-1.5">
            <OptionalBadge text={isRTL ? 'اختياري' : 'Optional'} />
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">PNG, JPG (Max 2MB)</span>
          </div>
        </div>

        {/* School Name & Primary Details */}
        <div className="md:col-span-8 space-y-4 bg-white dark:bg-slate-900 p-5 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="space-y-1.5" data-field="name">
            <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center justify-between">
              <span className="flex items-center gap-1.5">
                <Building2 className="h-3.5 w-3.5 text-[#1C3D74] dark:text-[#46C1BE]" />
                <span>{isRTL ? 'اسم المدرسة' : 'School Name'}</span>
              </span>
              <RequiredBadge text={isRTL ? 'إجباري' : 'Required'} />
            </Label>
            <Input
              value={schoolData.name}
              onChange={(e) => {
                setSchoolData({ ...schoolData, name: e.target.value });
                clearFieldError('name');
              }}
              placeholder={isRTL ? 'مثال: مدرسة النور الأهلية' : 'e.g. Al-Noor Private School'}
              className={`h-11 rounded-xl text-xs font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white placeholder:text-slate-400 transition-all focus:ring-2 focus:ring-[#46C1BE]/20 focus:border-[#46C1BE] ${
                errors.name ? 'border-rose-500 bg-rose-50/20' : 'border-slate-200 dark:border-slate-800'
              }`}
              data-testid="school-name-input"
            />
            {errors.name && <p className="text-xs text-rose-600 font-bold">{errors.name}</p>}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5" data-field="country">
              <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <Globe className="h-3.5 w-3.5 text-[#46C1BE]" />
                  <span>{isRTL ? 'الدولة' : 'Country'}</span>
                </span>
                <RequiredBadge text={isRTL ? 'إجباري' : 'Required'} />
              </Label>
              <Select
                value={schoolData.country}
                onValueChange={(v) => {
                  setSchoolData({ ...schoolData, country: v, city: '' });
                  clearFieldError('country');
                }}
              >
                <SelectTrigger className="h-11 rounded-xl font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white border-slate-200 dark:border-slate-800" data-testid="country-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 font-cairo">
                  {COUNTRIES.map((country) => (
                    <SelectItem key={country.code} value={country.code} className="font-medium text-slate-900 dark:text-slate-100">
                      {isRTL ? country.name : country.name_en}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {errors.country && <p className="text-xs text-rose-600 font-bold">{errors.country}</p>}
            </div>

            <div className="space-y-1.5" data-field="city">
              <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center justify-between">
                <span className="flex items-center gap-1.5">
                  <MapPin className="h-3.5 w-3.5 text-[#46C1BE]" />
                  <span>{isRTL ? 'المدينة' : 'City'}</span>
                </span>
                <RequiredBadge text={isRTL ? 'إجباري' : 'Required'} />
              </Label>
              <Select
                value={schoolData.city}
                onValueChange={(v) => {
                  setSchoolData({ ...schoolData, city: v });
                  clearFieldError('city');
                }}
              >
                <SelectTrigger className="h-11 rounded-xl font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white border-slate-200 dark:border-slate-800" data-testid="city-select">
                  <SelectValue placeholder={isRTL ? 'اختر المدينة' : 'Select City'} />
                </SelectTrigger>
                <SelectContent className="bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 font-cairo">
                  {schoolData.country === 'SA' ? (
                    ALL_SAUDI_CITIES.map((city) => (
                      <SelectItem key={city} value={city} className="font-medium text-slate-900 dark:text-slate-100">
                        {city}
                      </SelectItem>
                    ))
                  ) : (
                    <SelectItem value="other" className="font-medium text-slate-900 dark:text-slate-100">{isRTL ? 'أخرى' : 'Other'}</SelectItem>
                  )}
                </SelectContent>
              </Select>
              {errors.city && <p className="text-xs text-rose-600 font-bold">{errors.city}</p>}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-5 bg-white dark:bg-slate-900 p-5 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-sm">
        {/* Detailed Address */}
        <div className="space-y-1.5" data-field="address">
          <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <FileText className="h-3.5 w-3.5 text-[#46C1BE]" />
              <span>{isRTL ? 'العنوان التفصيلي' : 'Address'}</span>
            </span>
            <RequiredBadge text={isRTL ? 'إجباري' : 'Required'} />
          </Label>
          <Input
            value={schoolData.address}
            onChange={(e) => {
              setSchoolData({ ...schoolData, address: e.target.value });
              clearFieldError('address');
            }}
            placeholder={isRTL ? 'الحي، الشارع، رقم المبنى...' : 'District, Street, Building No...'}
            className={`h-11 rounded-xl text-xs font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white placeholder:text-slate-400 ${
              errors.address ? 'border-rose-500 bg-rose-50/20' : 'border-slate-200 dark:border-slate-800'
            }`}
            data-testid="address-input"
          />
          {errors.address && <p className="text-xs text-rose-600 font-bold">{errors.address}</p>}
        </div>

        {/* Administrative Region */}
        <div className="space-y-1.5" data-field="region">
          <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <MapPin className="h-3.5 w-3.5 text-slate-400" />
              <span>{isRTL ? 'المنطقة الإدارية' : 'Administrative Region'}</span>
            </span>
            <OptionalBadge text={isRTL ? 'اختياري' : 'Optional'} />
          </Label>
          <Input
            value={schoolData.region}
            onChange={(e) => setSchoolData({ ...schoolData, region: e.target.value })}
            placeholder={isRTL ? 'مثال: منطقة الرياض' : 'e.g. Riyadh Region'}
            className="h-11 rounded-xl text-xs font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white placeholder:text-slate-400 border-slate-200 dark:border-slate-800"
            data-testid="region-input"
          />
        </div>

        {/* Official Email */}
        <div className="space-y-1.5" data-field="email">
          <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <Mail className="h-3.5 w-3.5 text-slate-400" />
              <span>{isRTL ? 'البريد الرسمي للمدرسة' : 'School Official Email'}</span>
            </span>
            <OptionalBadge text={isRTL ? 'اختياري' : 'Optional'} />
          </Label>
          <Input
            type="email"
            value={schoolData.email}
            onChange={(e) => setSchoolData({ ...schoolData, email: e.target.value })}
            placeholder="info@school.edu.sa"
            dir="ltr"
            className="h-11 rounded-xl text-xs font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white placeholder:text-slate-400 border-slate-200 dark:border-slate-800"
            data-testid="school-email-input"
          />
        </div>

        {/* Contact Mobile */}
        <div className="space-y-1.5" data-field="principal_mobile">
          <Label className="text-xs font-bold text-slate-800 dark:text-slate-100 flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <Phone className="h-3.5 w-3.5 text-[#46C1BE]" />
              <span>{isRTL ? 'رقم جوال التواصل المعتمد' : 'Primary Mobile'}</span>
            </span>
            <RequiredBadge text={isRTL ? 'إجباري' : 'Required'} />
          </Label>
          <Input
            value={schoolData.principal_mobile}
            onChange={(e) => {
              setSchoolData({ ...schoolData, principal_mobile: e.target.value });
              clearFieldError('principal_mobile');
            }}
            placeholder="05XXXXXXXX"
            dir="ltr"
            className={`h-11 rounded-xl text-xs font-medium bg-white dark:bg-slate-950 text-slate-900 dark:text-white placeholder:text-slate-400 ${
              errors.principal_mobile ? 'border-rose-500 bg-rose-50/20' : 'border-slate-200 dark:border-slate-800'
            }`}
            data-testid="school-principal-mobile-input"
          />
          {errors.principal_mobile && <p className="text-xs text-rose-600 font-bold">{errors.principal_mobile}</p>}
        </div>
      </div>
    </div>
  );
}
