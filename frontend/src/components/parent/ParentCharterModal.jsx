import { useEffect, useRef, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { toast } from 'sonner';

/**
 * Mandatory parent charter blocking screen ("ميثاق ولي الأمر").
 *
 * Rendered by RouteGuards whenever an authenticated parent has
 * ``charter_accepted_at == null``. Intentionally NOT a Radix Dialog:
 * we render a full-viewport fixed overlay so there is no built-in
 * close affordance (no Escape, no overlay click, no X button). The
 * only ways out are (a) accepting the charter or (b) logging out via
 * the global header which remains accessible above the overlay's
 * z-index by design choice — however the overlay itself blocks all
 * underlying interaction with the dashboard.
 */
const ParentCharterModal = () => {
  const { user, api, updateUser, logout } = useAuth();
  const [isChecked, setIsChecked] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const dialogRef = useRef(null);
  const checkboxRef = useRef(null);

  // Initial focus on the checkbox so a keyboard user lands inside the
  // dialog, and trap Tab/Shift+Tab so focus cannot escape behind the
  // overlay. Escape is intentionally swallowed (modal is non-dismissible).
  useEffect(() => {
    checkboxRef.current?.focus();
    const onKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        return;
      }
      if (e.key !== 'Tab' || !dialogRef.current) return;
      const focusable = dialogRef.current.querySelectorAll(
        'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKeyDown, true);
    return () => document.removeEventListener('keydown', onKeyDown, true);
  }, []);

  const handleAccept = async () => {
    if (!isChecked || submitting) return;
    setSubmitting(true);
    try {
      const res = await api.post('/parent-portal/accept-charter');
      const acceptedAt =
        res?.data?.charter_accepted_at || new Date().toISOString();
      updateUser({ charter_accepted_at: acceptedAt });
    } catch (err) {
      toast.error('تعذر حفظ الموافقة، يرجى المحاولة مرة أخرى');
      setSubmitting(false);
    }
  };

  const handleLogout = async () => {
    try {
      await logout?.();
    } catch {
      window.location.assign('/login');
    }
  };

  const displayName = user?.full_name || '';

  return (
    <div
      ref={dialogRef}
      className="fixed inset-0 z-[9999] bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="parent-charter-title"
      dir="rtl"
      data-testid="parent-charter-modal"
    >
      <div className="w-full max-w-3xl max-h-[90vh] bg-white rounded-2xl shadow-2xl border border-border/40 flex flex-col">
        <div className="px-6 pt-6 pb-3 text-center border-b border-border/40 shrink-0">
          <h2
            id="parent-charter-title"
            className="text-xl font-bold text-brand-navy font-cairo"
          >
            ميثاق ولي الأمر
          </h2>
          {displayName && (
            <p className="mt-1 text-xs text-muted-foreground font-tajawal">
              مرحباً {displayName}
            </p>
          )}
        </div>

        <div className="px-6 py-5 space-y-4 text-foreground/90 leading-relaxed text-sm md:text-[15px] font-tajawal overflow-y-auto flex-1 min-h-0">
          <h3 className="text-base md:text-lg font-bold text-foreground font-cairo">
            ميثاق الشفافية والتعاون مع ولي الأمر
          </h3>

          <p>
            نرحب بكم في{' '}
            <span className="font-semibold text-brand-turquoise">منصة نسّق</span>،
            ونسعد بوجودكم كشريك أساسي في دعم رحلة الطالب التعليمية، حيث نؤمن
            بأن التعاون بين المدرسة وولي الأمر هو أساس نجاح الطالب.
          </p>

          <p>
            باستخدامكم للمنصة،{' '}
            <span className="font-semibold text-rose-600">فإنكم تتعهدون بما يلي:</span>
          </p>
          <ul className="list-disc pr-6 space-y-1.5 marker:text-brand-navy">
            <li>إدخال بيانات الطالب بشكل صحيح ودقيق، بما في ذلك أي معلومات صحية أو تعليمية مهمة.</li>
            <li>إبلاغ المدرسة بأي مستجدات أو تغييرات قد تؤثر على الطالب خلال اليوم الدراسي.</li>
            <li>الحرص على تحديث البيانات عند حدوث أي تغيير لضمان متابعة أفضل للطالب.</li>
          </ul>

          <p>ونود التنويه إلى أن:</p>
          <ul className="list-disc pr-6 space-y-1.5 marker:text-brand-navy">
            <li>المدرسة غير مسؤولة عن أي تبعات أو أضرار قد تنتج عن عدم الإفصاح أو تقديم معلومات غير دقيقة من قبل ولي الأمر.</li>
            <li>مشاركة المعلومات الدقيقة تساعد المدرسة في تقديم الرعاية والدعم المناسب للطالب.</li>
            <li>يتم التعامل مع جميع البيانات بسرية تامة وتُستخدم فقط لأغراض تعليمية وتنظيمية داخل المنصة.</li>
          </ul>

          <p>نشكركم على تعاونكم، ونسعد بشراكتكم في دعم رحلة أبنائنا التعليمية.</p>
        </div>

        <div className="px-6 pb-6 pt-3 border-t border-border/40 shrink-0">
          <label className="flex items-start gap-3 cursor-pointer select-none">
            <input
              ref={checkboxRef}
              type="checkbox"
              checked={isChecked}
              onChange={(e) => setIsChecked(e.target.checked)}
              disabled={submitting}
              className="mt-1 w-4 h-4 accent-brand-navy cursor-pointer"
              data-testid="checkbox-accept-charter"
            />
            <span className="text-sm text-foreground/90 font-tajawal">
              أقر بأني اطلعت على الميثاق والتعليمات المذكورة فيه
            </span>
          </label>

          <div className="mt-5 flex items-center justify-between gap-3">
            <button
              type="button"
              onClick={handleLogout}
              disabled={submitting}
              className="text-xs text-muted-foreground hover:text-foreground underline underline-offset-4 disabled:opacity-50"
              data-testid="button-charter-logout"
            >
              تسجيل الخروج
            </button>
            <button
              type="button"
              onClick={handleAccept}
              disabled={!isChecked || submitting}
              className={`min-w-[140px] inline-flex items-center justify-center gap-2 px-6 py-2.5 rounded-xl text-sm font-semibold font-cairo transition-all ${
                isChecked && !submitting
                  ? 'bg-brand-navy text-white hover:bg-brand-navy-dark shadow-md'
                  : 'bg-muted text-muted-foreground cursor-not-allowed'
              }`}
              data-testid="button-accept-charter"
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  جارٍ الحفظ...
                </>
              ) : (
                'موافق'
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ParentCharterModal;
