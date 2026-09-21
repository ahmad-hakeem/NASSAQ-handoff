/**
 * محتوى تبويب "إعدادات الجدول المدرسي" داخل صفحة الجدول الذكي
 * نَسَّق | NASSAQ — Task #114 (+ ومضة التحميل المُصلَّحة)
 *
 * يُعيد استخدام نفس مكوّن DynamicSettingsContent ونفس مودالات
 * SettingsModals وخطّاف useSchoolSettings المستعملة في صفحة "إعدادات
 * المدرسة"، لكن بقائمة تبويبات فرعية مقتصرة على إعدادات الجدول الخمس:
 *   - التوقيت والحصص
 *   - الفصول والشعب
 *   - إسناد المعلمين
 *   - أوقات عدم التوفر
 *   - قيود الجدول
 *
 * مزامنة ثنائية الاتجاه بين معطى الرابط `?sub=` وحالة التبويب الفرعي
 * النشط، حتى تكون كل تبويبة قابلة للحفظ والمشاركة عبر الـ URL.
 *
 * أهمّ تفصيل سلوكي: useSchoolSettings يقرأ معطى ?tab= عند الإقلاع لاختيار
 * التبويب الافتراضي ضمن سياق "إعدادات المدرسة" (school-info, timings, ...).
 * في صفحتنا يأخذ ?tab= القيمة "settings" التي ليست ضمن تبويبات الخطّاف
 * الديناميكية، فيقع الاختيار الافتراضي على "school-info". لتفادي ومضة
 * عرض بطاقة "البيانات الأساسية للمدرسة" قبل أن يضبط useLayoutEffect
 * التبويب على "timings" أو على ?sub= الموجود، نعرض مُحمِّل بسيط حتى
 * يصبح activeTab ضمن التبويبات الخمس المسموح بها هنا. وهذا أيضاً يضمن
 * أنّ التنقّل بين التبويبات الفرعية لا يتسبّب بإعادة تركيب أي عنصر —
 * تتغيّر فقط حالة activeTab داخل DynamicSettingsContent.
 *
 * لا تعديلات داخلية على المكوّنات أو الخطّاف — مجرد تمرير قائمة
 * تبويبات مُصفّاة عبر prop وتنسيق المزامنة من الخارج.
 */

import React, { useEffect, useLayoutEffect, useMemo, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Loader2, Clock, School, Link2, UserX, Shield, CheckCircle2, AlertTriangle, X, Check, BookOpen } from 'lucide-react';
import { useSchoolSettings } from '@/shared/hooks/useSchoolSettings';
import { DynamicSettingsContent } from '@/features/settings/components/school-settings/DynamicSettingsContent';
import { SettingsModals } from '@/features/settings/components/school-settings/SettingsModals';
import { useTranslation, useTheme } from '@/shared/contexts/ThemeContext';

const SCHEDULE_TAB_IDS = ['timings', 'classes', 'subjects', 'teacher-assignments', 'unavailability', 'constraints'];
const DEFAULT_SUB_TAB = 'timings';

export default function ScheduleSettingsTabContent({
  onUnpublishPublished,
  unpublishingPublished = false,
  onTimingSettingsSaved,
}) {
  const { t } = useTranslation();
  const { direction } = useTheme();
  const scheduleSubTabs = useMemo(() => ([
    { id: 'timings', label: t('settingsTabTimings'), icon: Clock },
    { id: 'classes', label: t('settingsTabClasses'), icon: School },
    { id: 'subjects', label: t('settingsTabSubjects'), icon: BookOpen },
    { id: 'teacher-assignments', label: t('settingsTabTeacherAssignments'), icon: Link2 },
    { id: 'unavailability', label: t('settingsTabUnavailability'), icon: UserX },
    { id: 'constraints', label: t('settingsTabConstraints'), icon: Shield },
  ]), [t]);
  const settingsHook = useSchoolSettings({ onTimingSettingsSaved });
  const hook = {
    ...settingsHook,
    onUnpublishPublished,
    unpublishingPublished,
  };
  const { loading, activeTab, setActiveTab, settingsLoadError, fetchData } = hook;
  const location = useLocation();
  const navigate = useNavigate();

  // ── 1) URL → state (متزامن قبل الرسم، يعتمد على الرابط فقط) ────
  // useLayoutEffect يضمن إجراء التصحيح قبل أوّل رسمة فعلية للمتصفح،
  // فيُلغي ومضة "school-info" التي قد تظهر في الجزء بين أوّل تركيب
  // وتشغيل useEffect العادي. عند تغيّر معطى ?sub= لاحقاً (مثلاً عبر
  // زر "إصلاح" في بطاقة الجاهزية أو رابط INF أو زر الرجوع في المتصفح)
  // نُزامن التبويب النشط ليطابقه.
  //
  // مهم: لا نُدرج activeTab ضمن الاعتماديات. لو فعلنا فعند ضغط المستخدم
  // على تبويب فرعي جديد ("classes" مثلاً) سيُعاد تشغيل هذا التأثير قبل
  // أن ينجح التأثير (2) state→URL في كتابة ?sub=classes، فيقرأ ?sub=
  // القديم من الرابط (timings) ويُعيد ضبط activeTab إلى timings —
  // وهذا يُلغي ضغطة المستخدم. نقرأ activeTab الحالي عبر ref حتى نتفادى
  // التحذير من exhaustive-deps دون التضحية بصحّة المنطق.
  const activeTabRef = useRef(activeTab);
  useLayoutEffect(() => { activeTabRef.current = activeTab; }, [activeTab]);
  useLayoutEffect(() => {
    const sub = new URLSearchParams(location.search).get('sub');
    const current = activeTabRef.current;
    if (sub && SCHEDULE_TAB_IDS.includes(sub)) {
      if (sub !== current) setActiveTab(sub);
      return;
    }
    if (!SCHEDULE_TAB_IDS.includes(current)) {
      setActiveTab(DEFAULT_SUB_TAB);
    }
  }, [location.search, setActiveTab]);

  // ── 2) state → URL ─────────────────────────────────────────────
  // عندما يضغط المستخدم على تبويب فرعي داخل DynamicSettingsContent
  // (الذي يستدعي setActiveTab مباشرة) نكتب القيمة الجديدة في معطى
  // ?sub= حتى يكون الرابط دائماً معبِّراً عن الحالة المعروضة. نستخدم
  // navigate(replace) حتى لا تتراكم نُسَخ في تاريخ المتصفح عند تنقّل
  // المستخدم بين التبويبات الفرعية. كما نُحافظ على tab=settings حتى
  // لا يخرج المستخدم من تبويب الإعدادات الرئيسي بطريق الخطأ.
  useEffect(() => {
    if (!SCHEDULE_TAB_IDS.includes(activeTab)) return;
    const params = new URLSearchParams(location.search);
    if (params.get('sub') === activeTab && params.get('tab') === 'settings') return;
    params.set('tab', 'settings');
    params.set('sub', activeTab);
    navigate(`${location.pathname}?${params.toString()}`, { replace: true });
  }, [activeTab, navigate, location.pathname, location.search]);

  // مُحمِّل واحد لكلا الحالتين: تحميل البيانات الأوّلي من useSchoolSettings،
  // أو الإطار الانتقالي القصير الذي يكون فيه activeTab خارج تبويبات الجدول
  // (قبل أن يضبطه useLayoutEffect أعلاه). بدون هذه البوّابة سيُرنْدِر
  // DynamicSettingsContent بطاقة "البيانات الأساسية للمدرسة" لإطار واحد —
  // وهي ومضة بصرية مربكة لمستخدم وصل لتبويب إعدادات الجدول.
  if (loading || !SCHEDULE_TAB_IDS.includes(activeTab)) {
    return (
      <div
        dir={direction}
        className="flex items-center justify-center py-20 min-h-[60vh] text-slate-500"
        data-testid="schedule-settings-loader"
      >
        <Loader2 className="h-6 w-6 animate-spin me-2" />
        {t('loadingScheduleSettings')}
      </div>
    );
  }

  if (activeTab === 'timings' && settingsLoadError) {
    return (
      <div
        role="alert"
        className="rounded-xl border border-red-300 bg-red-50 p-5 text-red-900"
        data-testid="schedule-settings-load-error"
      >
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-red-600" />
          <div className="flex-1">
            <p className="font-bold">تعذّر تحميل إعدادات التوقيت</p>
            <p className="mt-1 text-sm leading-6">{settingsLoadError}</p>
            <p className="mt-1 text-sm">لم نعرض قيماً افتراضية بديلة حتى لا تُحفظ فوق إعدادات المدرسة الحالية.</p>
            <button
              type="button"
              onClick={fetchData}
              className="mt-4 rounded-lg bg-red-700 px-4 py-2 text-sm font-semibold text-white hover:bg-red-800"
              data-testid="retry-schedule-settings"
            >
              إعادة المحاولة
            </button>
          </div>
        </div>
      </div>
    );
  }

  const { inlineAlert, dismissInlineAlert, successModal, dismissSuccessModal } = hook;

  return (
    <div data-testid="schedule-settings-tab-content">
      <InlineAlert alert={inlineAlert} onDismiss={dismissInlineAlert} />
      <DynamicSettingsContent hook={hook} dynamicTabs={scheduleSubTabs} />
      <SettingsModals hook={hook} />
      <SuccessModal modal={successModal} onClose={dismissSuccessModal} />
    </div>
  );
}

/**
 * مودال نجاح مركزي للحركات الحسّاسة (مثل إرسال إشعارات فعلية للمعلمين
 * بعد إضافة عدم توفر فصل). يوقف التفاعل مع الخلفية حتى يضغط المسؤول
 * "حسناً" — تأكيد صريح يضمن قراءة الرسالة قبل المتابعة.
 */
function SuccessModal({ modal, onClose }) {
  if (!modal?.show) return null;

  const variants = {
    success: {
      iconBg: 'bg-emerald-100',
      iconColor: 'text-emerald-600',
      Icon: Check,
      iconStroke: 3,
      button: 'bg-emerald-600 hover:bg-emerald-700',
      defaultTitle: 'تمت الإضافة بنجاح',
    },
    warning: {
      iconBg: 'bg-amber-100',
      iconColor: 'text-amber-600',
      Icon: AlertTriangle,
      iconStroke: 2,
      button: 'bg-amber-600 hover:bg-amber-700',
      defaultTitle: 'تنبيه',
    },
    error: {
      iconBg: 'bg-red-100',
      iconColor: 'text-red-600',
      Icon: AlertTriangle,
      iconStroke: 2,
      button: 'bg-red-600 hover:bg-red-700',
      defaultTitle: 'تعذّر الحفظ',
    },
  };
  const v = variants[modal.type] || variants.success;
  const { Icon } = v;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
      role="dialog"
      aria-modal="true"
      data-testid={`schedule-success-modal-${modal.type || 'success'}`}
      onClick={onClose}
    >
      <div
        className="bg-white rounded-xl shadow-2xl p-6 w-full max-w-md transform transition-all text-center"
        onClick={(e) => e.stopPropagation()}
      >
        <div className={`mx-auto flex h-16 w-16 items-center justify-center rounded-full ${v.iconBg} mb-4`}>
          <Icon className={`h-10 w-10 ${v.iconColor}`} strokeWidth={v.iconStroke} />
        </div>
        <h3 className="text-xl font-bold text-slate-800 mb-2 font-cairo">
          {modal.title || v.defaultTitle}
        </h3>
        <p className="text-slate-600 mb-6 font-tajawal leading-7">{modal.message}</p>
        <button
          type="button"
          onClick={onClose}
          className={`w-full text-white rounded-lg py-3 font-semibold transition-colors font-cairo ${v.button}`}
          data-testid="schedule-success-modal-confirm"
        >
          حسناً
        </button>
      </div>
    </div>
  );
}

/**
 * تنبيه ثابت داخل الصفحة (Inline Alert) — يُعرض أسفل التبويبات وأعلى
 * المحتوى. يحمل ألواناً دلالية ناعمة وحدوداً RTL، ويتطلّب من المسؤول
 * إغلاقاً صريحاً حتى لا يفوته الأمر.
 */
function InlineAlert({ alert, onDismiss }) {
  if (!alert?.show) return null;

  const variants = {
    success: {
      container: 'bg-emerald-50 border-emerald-500 text-emerald-800',
      Icon: CheckCircle2,
      iconClass: 'text-emerald-600',
    },
    warning: {
      container: 'bg-amber-50 border-amber-500 text-amber-800',
      Icon: AlertTriangle,
      iconClass: 'text-amber-600',
    },
    error: {
      container: 'bg-red-50 border-red-500 text-red-800',
      Icon: AlertTriangle,
      iconClass: 'text-red-600',
    },
  };
  const { container, Icon, iconClass } = variants[alert.type] || variants.success;

  return (
    <div
      role="alert"
      data-testid={`schedule-inline-alert-${alert.type}`}
      className={`flex justify-between items-start p-4 mb-6 rounded-lg border-r-4 shadow-sm transition-all duration-300 ${container}`}
    >
      <div className="flex items-start gap-3 flex-1 min-w-0">
        <Icon className={`h-5 w-5 mt-0.5 shrink-0 ${iconClass}`} />
        <p className="font-tajawal text-sm leading-6 break-words">{alert.message}</p>
      </div>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="إغلاق التنبيه"
        className="hover:bg-black/5 rounded-md p-1 transition-colors shrink-0 ms-3"
        data-testid="schedule-inline-alert-dismiss"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
