import { toHijri } from 'hijri-converter';

const HIJRI_MONTHS_AR = [
  'محرم', 'صفر', 'ربيع الأول', 'ربيع الآخر',
  'جمادى الأولى', 'جمادى الآخرة', 'رجب', 'شعبان',
  'رمضان', 'شوال', 'ذو القعدة', 'ذو الحجة'
];

const HIJRI_MONTHS_EN = [
  'Muharram', 'Safar', 'Rabi al-Awwal', 'Rabi al-Thani',
  'Jumada al-Ula', 'Jumada al-Thani', 'Rajab', 'Shaaban',
  'Ramadan', 'Shawwal', 'Dhul Qadah', 'Dhul Hijjah'
];

const GREGORIAN_MONTHS_AR = [
  'يناير', 'فبراير', 'مارس', 'أبريل',
  'مايو', 'يونيو', 'يوليو', 'أغسطس',
  'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'
];

const WEEKDAYS_AR = [
  'الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء',
  'الخميس', 'الجمعة', 'السبت'
];

const WEEKDAYS_EN = [
  'Sunday', 'Monday', 'Tuesday', 'Wednesday',
  'Thursday', 'Friday', 'Saturday'
];

const EASTERN_DIGITS = ['٠','١','٢','٣','٤','٥','٦','٧','٨','٩'];

function toEasternArabic(num) {
  return String(num).replace(/[0-9]/g, d => EASTERN_DIGITS[parseInt(d)]);
}

export function getHijriDate(date = new Date()) {
  const y = date.getFullYear();
  const m = date.getMonth() + 1;
  const d = date.getDate();
  const { hy, hm, hd } = toHijri(y, m, d);
  const weekdayIndex = date.getDay();

  return {
    hijriDay: hd,
    hijriMonth: hm,
    hijriYear: hy,
    hijriMonthAr: HIJRI_MONTHS_AR[hm - 1],
    hijriMonthEn: HIJRI_MONTHS_EN[hm - 1],
    gregorianDay: d,
    gregorianMonth: m,
    gregorianYear: y,
    gregorianMonthAr: GREGORIAN_MONTHS_AR[m - 1],
    weekdayAr: WEEKDAYS_AR[weekdayIndex],
    weekdayEn: WEEKDAYS_EN[weekdayIndex],
  };
}

export function formatHijriDate(date = new Date(), options = {}) {
  const { locale = 'ar', includeWeekday = true, includeGregorian = true } = options;
  const h = getHijriDate(date);

  if (locale === 'ar') {
    const weekday = includeWeekday ? `${h.weekdayAr} ` : '';
    const hijriPart = `${weekday}${toEasternArabic(h.hijriDay)} ${h.hijriMonthAr} ${toEasternArabic(h.hijriYear)} هـ`;
    if (!includeGregorian) return hijriPart;
    const gregPart = `${toEasternArabic(h.gregorianDay)} ${h.gregorianMonthAr} ${toEasternArabic(h.gregorianYear)}`;
    return `${hijriPart}  —  ${gregPart}`;
  }

  const weekday = includeWeekday ? `${h.weekdayEn} ` : '';
  const hijriPart = `${weekday}${h.hijriDay} ${h.hijriMonthEn} ${h.hijriYear} AH`;
  if (!includeGregorian) return hijriPart;
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const gregPart = `${h.gregorianDay} ${months[h.gregorianMonth - 1]} ${h.gregorianYear}`;
  return `${hijriPart}  —  ${gregPart}`;
}

export function formatHijriOnly(date = new Date(), locale = 'ar') {
  const h = getHijriDate(date);
  if (locale === 'ar') {
    return `${toEasternArabic(h.hijriDay)} ${h.hijriMonthAr} ${toEasternArabic(h.hijriYear)} هـ`;
  }
  return `${h.hijriDay} ${h.hijriMonthEn} ${h.hijriYear} AH`;
}

export function formatGregorianArabic(date = new Date()) {
  const h = getHijriDate(date);
  return `${toEasternArabic(h.gregorianDay)} ${h.gregorianMonthAr} ${toEasternArabic(h.gregorianYear)}`;
}

const GREGORIAN_MONTHS_SHORT_EN = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

export function formatGregorianShort(date = new Date(), locale = 'ar') {
  const d = date instanceof Date ? date : new Date(date);
  if (!d || Number.isNaN(d.getTime())) return '—';
  const day = d.getDate();
  const monthIdx = d.getMonth();
  if (locale === 'ar') {
    return `${toEasternArabic(day)} ${GREGORIAN_MONTHS_AR[monthIdx]}`;
  }
  return `${day} ${GREGORIAN_MONTHS_SHORT_EN[monthIdx]}`;
}

export function formatGregorianFull(date = new Date(), locale = 'ar') {
  const d = date instanceof Date ? date : new Date(date);
  if (!d || Number.isNaN(d.getTime())) return '—';
  const weekdayIdx = d.getDay();
  const day = d.getDate();
  const monthIdx = d.getMonth();
  const year = d.getFullYear();
  if (locale === 'ar') {
    return `${WEEKDAYS_AR[weekdayIdx]} ${toEasternArabic(day)} ${GREGORIAN_MONTHS_AR[monthIdx]} ${toEasternArabic(year)}`;
  }
  return `${WEEKDAYS_EN[weekdayIdx]} ${day} ${GREGORIAN_MONTHS_SHORT_EN[monthIdx]} ${year}`;
}

export function getWeekdayName(date = new Date(), locale = 'ar') {
  const idx = date.getDay();
  return locale === 'ar' ? WEEKDAYS_AR[idx] : WEEKDAYS_EN[idx];
}

export function formatFullDate(date = new Date(), locale = 'ar') {
  const h = getHijriDate(date);
  if (locale === 'ar') {
    const hijri = `${toEasternArabic(h.hijriDay)} ${h.hijriMonthAr} ${toEasternArabic(h.hijriYear)} هـ`;
    const greg = `${toEasternArabic(h.gregorianDay)} ${h.gregorianMonthAr} ${toEasternArabic(h.gregorianYear)}`;
    return { weekday: h.weekdayAr, hijri, gregorian: greg, full: `${hijri}  —  ${greg}` };
  }
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const hijri = `${h.hijriDay} ${h.hijriMonthEn} ${h.hijriYear} AH`;
  const greg = `${h.gregorianDay} ${months[h.gregorianMonth - 1]} ${h.gregorianYear}`;
  return { weekday: h.weekdayEn, hijri, gregorian: greg, full: `${hijri}  —  ${greg}` };
}
