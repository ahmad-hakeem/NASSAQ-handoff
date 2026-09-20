import { Calendar } from 'lucide-react';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import {
  convertGregorianToHijri,
  getSaudiDateOnly,
  parseGregorianDateOnly,
  validateTeacherBirthDate,
} from '@/shared/models/utils/teacherBirthDate';

const localizeNumber = (value, locale) => {
  if (locale !== 'ar') return String(value);
  const arabicDigits = '٠١٢٣٤٥٦٧٨٩';
  return String(value).replace(/\d/g, (digit) => arabicDigits[Number(digit)]);
};

const formatHijri = (conversion, locale) => {
  if (conversion.status !== 'converted') return null;
  const { year, month, day } = conversion.hijri;
  const iso = [year, month, day]
    .map((part, index) => localizeNumber(String(part).padStart(index ? 2 : 4, '0'), locale))
    .join('-');
  return `${iso} ${locale === 'ar' ? 'هـ' : 'AH'}`;
};

export const TeacherBirthDateField = ({
  id = 'teacher-date-of-birth',
  value = '',
  onChange,
  t,
  locale = 'en',
  today = getSaudiDateOnly(),
  error,
  legacyUnchanged = false,
  className = '',
  testId = 'teacher-dob',
}) => {
  const validation = validateTeacherBirthDate(value, today);
  const hasNoncanonicalStoredValue = legacyUnchanged && Boolean(value) && !parseGregorianDateOnly(value);
  const conversion = validation.status === 'valid'
    ? validation.conversion
    : { status: validation.status === 'blank' ? 'blank' : 'invalid' };
  const validationMessage = error || (!hasNoncanonicalStoredValue && (
    validation.status === 'invalid'
      ? t('invalidGregorianDate')
      : validation.status === 'future'
        ? t('futureBirthDate')
        : ''
  ));
  const descriptionId = `${id}-description`;
  const errorId = `${id}-error`;

  return (
    <div className={`space-y-2 ${className}`}>
      <div className="space-y-1">
        <Label htmlFor={id} className="text-sm font-medium">
          {t('gregorianBirthDate')}
        </Label>
        <Input
          id={id}
          type="date"
          value={hasNoncanonicalStoredValue ? '' : (value || '')}
          max={today}
          onChange={(event) => onChange(event.target.value)}
          aria-invalid={Boolean(validationMessage)}
          aria-describedby={`${descriptionId}${validationMessage ? ` ${errorId}` : ''}`}
          className={`h-10 rounded-lg ${validationMessage ? 'border-red-500' : ''}`}
          data-testid={testId}
        />
        <p id={descriptionId} className="text-xs text-muted-foreground">
          {t('gregorianDateFormat')}
        </p>
        {validationMessage ? (
          <p id={errorId} role="alert" className="text-xs text-red-600">
            {validationMessage}
          </p>
        ) : null}
        {hasNoncanonicalStoredValue ? (
          <div className="flex items-center justify-between gap-2">
            <p role="status" aria-live="polite" className="text-xs text-amber-700 dark:text-amber-400">
              {t('invalidStoredGregorianDate')}: <span dir="ltr">{value}</span>
            </p>
            <button
              type="button"
              className="text-xs font-medium text-red-600 underline-offset-2 hover:underline"
              onClick={() => onChange('')}
              data-testid={`${testId}-clear-legacy`}
            >
              {t('clearTeacherBirthDate')}
            </button>
          </div>
        ) : null}
      </div>

      <div className="rounded-lg border bg-muted/30 px-3 py-2" role="status" aria-live="polite">
        <p className="text-xs text-muted-foreground">{t('hijriBirthDate')}</p>
        {conversion.status === 'converted' ? (
          <>
            <p className="font-medium" dir="ltr">{formatHijri(conversion, locale)}</p>
            <p className="text-xs text-muted-foreground">{t('hijriDateFormat')}</p>
          </>
        ) : conversion.status === 'unsupported' ? (
          <p className="text-xs text-amber-700 dark:text-amber-400">
            {t('hijriConversionUnavailable')}
          </p>
        ) : (
          <p className="font-medium text-muted-foreground">—</p>
        )}
      </div>
    </div>
  );
};

export const TeacherBirthDateDisplay = ({
  value,
  t,
  locale = 'en',
  className = '',
}) => {
  const conversion = value ? convertGregorianToHijri(value) : { status: 'blank' };
  const empty = t('notProvided');

  return (
    <div className={`grid grid-cols-1 gap-3 sm:grid-cols-2 ${className}`}>
      <div className="flex items-start gap-2">
        <Calendar className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div>
          <span className="text-xs text-muted-foreground">{t('gregorianBirthDate')}</span>
          <p className="font-medium text-sm" dir="ltr">{value || empty}</p>
        </div>
      </div>
      <div className="flex items-start gap-2">
        <Calendar className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div>
          <span className="text-xs text-muted-foreground">{t('hijriBirthDate')}</span>
          {conversion.status === 'converted' ? (
            <p className="font-medium text-sm" dir="ltr">{formatHijri(conversion, locale)}</p>
          ) : conversion.status === 'unsupported' ? (
            <p className="text-xs text-amber-700 dark:text-amber-400">{t('hijriConversionUnavailable')}</p>
          ) : conversion.status === 'invalid' ? (
            <p className="text-xs text-amber-700 dark:text-amber-400">{t('invalidStoredGregorianDate')}</p>
          ) : (
            <p className="font-medium text-sm">{empty}</p>
          )}
        </div>
      </div>
    </div>
  );
};