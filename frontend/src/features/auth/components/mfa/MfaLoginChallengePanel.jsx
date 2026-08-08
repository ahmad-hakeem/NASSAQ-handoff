import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from '@/shared/contexts/AuthContext';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import {
  ShieldCheck,
  Mail,
  KeyRound,
  Smartphone,
  LifeBuoy,
  Loader2,
  AlertCircle,
  ArrowRight,
  ArrowLeft,
  Clock,
} from 'lucide-react';

const FACTOR_META = {
  webauthn: {
    icon: KeyRound,
    label_ar: 'مفتاح الأمان (Passkey)',
    label_en: 'Security key / Passkey',
    desc_ar: 'استخدم بصمة الإصبع أو الوجه أو مفتاح الأمان.',
    desc_en: 'Use your fingerprint, face, or hardware security key.',
  },
  totp: {
    icon: Smartphone,
    label_ar: 'تطبيق المصادقة',
    label_en: 'Authenticator app',
    desc_ar: 'أدخل الرمز المعروض في تطبيق المصادقة.',
    desc_en: 'Enter the code shown in your authenticator app.',
  },
  email_otp: {
    icon: Mail,
    label_ar: 'رمز عبر البريد الإلكتروني',
    label_en: 'Email code',
    desc_ar: 'سنرسل رمزاً مكوناً من 6 أرقام إلى بريدك.',
    desc_en: 'We will email you a 6-digit code.',
  },
  recovery_code: {
    icon: LifeBuoy,
    label_ar: 'رمز الاسترداد',
    label_en: 'Recovery code',
    desc_ar: 'استخدم أحد رموز الاسترداد التي حفظتها.',
    desc_en: 'Use one of your saved recovery codes.',
  },
};

function formatRemaining(ms) {
  if (ms <= 0) return '00:00';
  const total = Math.floor(ms / 1000);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

export default function MfaLoginChallengePanel({ challenge, isRTL, onSuccess, onCancel }) {
  const { verifyMfaLogin, sendMfaLoginEmailOtp } = useAuth();
  const lang = isRTL ? 'ar' : 'en';

  const initialKinds = challenge.available_factor_kinds || [];
  const [picked, setPicked] = useState(initialKinds.length === 1 ? initialKinds[0] : null);
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [otpInfo, setOtpInfo] = useState(null); // { masked_email, expires_at, ... }
  const [otpSendingState, setOtpSendingState] = useState('idle'); // 'idle' | 'sending' | 'sent' | 'error'
  const [now, setNow] = useState(Date.now());
  const [resendCooldownUntil, setResendCooldownUntil] = useState(0);
  const autoSentRef = useRef(false);

  // 1Hz tick for countdown timers.
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const sendEmailOtp = useCallback(async () => {
    if (!challenge?.challenge_token) return;
    setOtpSendingState('sending');
    setError('');
    const r = await sendMfaLoginEmailOtp({ challenge_token: challenge.challenge_token });
    if (r.success) {
      setOtpInfo(r);
      setOtpSendingState('sent');
      setResendCooldownUntil(Date.now() + 30_000);
    } else {
      setOtpSendingState('error');
      setError(r.error || (lang === 'ar' ? 'تعذر إرسال الرمز.' : 'Could not send the code.'));
    }
  }, [challenge, sendMfaLoginEmailOtp, lang]);

  // Auto-send the email OTP once per session as soon as the user lands on it.
  useEffect(() => {
    if (picked !== 'email_otp') return;
    if (autoSentRef.current) return;
    autoSentRef.current = true;
    sendEmailOtp();
  }, [picked, sendEmailOtp]);

  const handleVerify = async () => {
    if (!picked) return;
    if (picked === 'webauthn') {
      setError(
        lang === 'ar'
          ? 'التحقق عبر Passkey سيتوفر في التحديث القادم — يرجى استخدام وسيلة أخرى.'
          : 'Passkey verification will be available in the next update — please use another method.',
      );
      return;
    }
    if (!code.trim()) {
      setError(lang === 'ar' ? 'يرجى إدخال الرمز.' : 'Please enter the code.');
      return;
    }
    setSubmitting(true);
    setError('');
    const r = await verifyMfaLogin({
      challenge_token: challenge.challenge_token,
      factor_kind: picked,
      code: code.trim(),
      remember_me: challenge.remember_me,
    });
    setSubmitting(false);
    if (r.success) {
      onSuccess?.(r.user);
    } else {
      setError(r.error || (lang === 'ar' ? 'فشل التحقق.' : 'Verification failed.'));
    }
  };

  const challengeRemainingMs = useMemo(() => {
    if (!challenge?.challenge_expires_at) return null;
    const exp = new Date(challenge.challenge_expires_at).getTime();
    return Math.max(0, exp - now);
  }, [challenge, now]);

  const otpRemainingMs = useMemo(() => {
    if (!otpInfo?.expires_at) return null;
    const exp = new Date(otpInfo.expires_at).getTime();
    return Math.max(0, exp - now);
  }, [otpInfo, now]);

  const resendDisabled = submitting || resendCooldownUntil > now || otpSendingState === 'sending';
  const resendSecondsLeft = Math.max(0, Math.ceil((resendCooldownUntil - now) / 1000));

  const challengeExpired = challengeRemainingMs === 0;

  // Single-factor branch — render directly. Multi-factor — show picker first.
  const showPicker = !picked;

  return (
    <div className="space-y-4 animate-fade-in" data-testid="mfa-challenge-panel">
      {/* Header */}
      <div className="flex items-start gap-3 p-3 rounded-xl bg-indigo-50 border border-indigo-200">
        <ShieldCheck className="h-5 w-5 text-indigo-600 flex-shrink-0 mt-0.5" />
        <div className={`flex-1 ${isRTL ? 'text-right' : 'text-left'}`}>
          <div className="font-cairo text-sm font-bold text-indigo-900">
            {lang === 'ar' ? 'مطلوب التحقق بخطوتين' : 'Two-step verification required'}
          </div>
          <div className="font-tajawal text-xs text-indigo-800 mt-0.5">
            {lang === 'ar'
              ? 'لحماية حسابك، يرجى تأكيد العامل الثاني قبل الدخول.'
              : 'To protect your account, please confirm a second factor before continuing.'}
          </div>
          {challengeRemainingMs !== null && !challengeExpired && (
            <div className="flex items-center gap-1.5 mt-1.5 text-xs text-indigo-700 font-tajawal">
              <Clock className="h-3 w-3" />
              {lang === 'ar'
                ? `تنتهي صلاحية الجلسة خلال ${formatRemaining(challengeRemainingMs)}`
                : `Session expires in ${formatRemaining(challengeRemainingMs)}`}
            </div>
          )}
        </div>
      </div>

      {challengeExpired && (
        <div className="flex items-start gap-2 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700">
          <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
          <div className={`font-cairo text-sm flex-1 ${isRTL ? 'text-right' : 'text-left'}`}>
            {lang === 'ar'
              ? 'انتهت صلاحية جلسة التحقق. يرجى إعادة تسجيل الدخول.'
              : 'This verification session has expired. Please sign in again.'}
          </div>
        </div>
      )}

      {!challengeExpired && showPicker && (
        <div className="space-y-2">
          <div className={`font-tajawal text-xs text-muted-foreground ${isRTL ? 'text-right' : 'text-left'}`}>
            {lang === 'ar' ? 'اختر طريقة التحقق:' : 'Choose a verification method:'}
          </div>
          {initialKinds.map((kind) => {
            const meta = FACTOR_META[kind];
            if (!meta) return null;
            const Icon = meta.icon;
            return (
              <button
                key={kind}
                type="button"
                onClick={() => {
                  setPicked(kind);
                  setCode('');
                  setError('');
                }}
                className={`w-full flex items-center gap-3 p-3 rounded-xl border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50/50 transition-all ${isRTL ? 'text-right' : 'text-left'}`}
                data-testid={`mfa-pick-${kind}`}
              >
                <Icon className="h-5 w-5 text-indigo-600 flex-shrink-0" />
                <div className="flex-1">
                  <div className="font-cairo text-sm font-semibold text-foreground">
                    {lang === 'ar' ? meta.label_ar : meta.label_en}
                  </div>
                  <div className="font-tajawal text-xs text-muted-foreground mt-0.5">
                    {lang === 'ar' ? meta.desc_ar : meta.desc_en}
                  </div>
                </div>
                {isRTL ? <ArrowLeft className="h-4 w-4 text-muted-foreground" /> : <ArrowRight className="h-4 w-4 text-muted-foreground" />}
              </button>
            );
          })}
          <button
            type="button"
            onClick={onCancel}
            className="w-full text-xs font-tajawal text-muted-foreground hover:text-foreground py-2"
            data-testid="mfa-cancel-link"
          >
            {lang === 'ar' ? 'العودة لتسجيل الدخول' : 'Back to sign in'}
          </button>
        </div>
      )}

      {!challengeExpired && !showPicker && (
        <div className="space-y-3">
          <div className={`flex items-center gap-2 p-2.5 rounded-xl bg-muted/50 ${isRTL ? 'flex-row-reverse text-right' : 'text-left'}`}>
            {(() => {
              const Icon = FACTOR_META[picked]?.icon || ShieldCheck;
              return <Icon className="h-5 w-5 text-indigo-600 flex-shrink-0" />;
            })()}
            <div className="flex-1">
              <div className="font-cairo text-sm font-semibold text-foreground">
                {lang === 'ar' ? FACTOR_META[picked]?.label_ar : FACTOR_META[picked]?.label_en}
              </div>
              {picked === 'email_otp' && otpInfo?.masked_email && (
                <div className="font-tajawal text-xs text-muted-foreground mt-0.5" dir="ltr">
                  {lang === 'ar' ? `أُرسل إلى ${otpInfo.masked_email}` : `Sent to ${otpInfo.masked_email}`}
                </div>
              )}
              {picked === 'email_otp' && otpSendingState === 'sending' && (
                <div className="font-tajawal text-xs text-muted-foreground mt-0.5">
                  {lang === 'ar' ? 'جارٍ الإرسال…' : 'Sending…'}
                </div>
              )}
            </div>
          </div>

          {picked !== 'webauthn' && (
            <Input
              autoFocus
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder={picked === 'recovery_code' ? 'XXXX-XXXX-XXXX' : '000000'}
              maxLength={picked === 'recovery_code' ? 14 : 6}
              inputMode={picked === 'recovery_code' ? 'text' : 'numeric'}
              autoComplete="one-time-code"
              disabled={submitting}
              className="text-center font-mono text-lg tracking-[0.4em] py-3 h-12 rounded-xl"
              dir="ltr"
              data-testid="mfa-code-input"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !submitting) handleVerify();
              }}
            />
          )}

          {picked === 'email_otp' && otpRemainingMs !== null && otpInfo?.expires_at && (
            <div className={`flex items-center gap-1.5 text-xs font-tajawal ${otpRemainingMs <= 30_000 ? 'text-red-600' : 'text-muted-foreground'} ${isRTL ? 'flex-row-reverse' : ''}`}>
              <Clock className="h-3 w-3" />
              {lang === 'ar'
                ? `صلاحية الرمز: ${formatRemaining(otpRemainingMs)}`
                : `Code expires in ${formatRemaining(otpRemainingMs)}`}
            </div>
          )}

          {error && (
            <div className="flex items-start gap-2 p-2.5 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive">
              <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
              <div className={`font-tajawal text-xs flex-1 ${isRTL ? 'text-right' : 'text-left'}`}>
                {error}
              </div>
            </div>
          )}

          <Button
            type="button"
            onClick={handleVerify}
            disabled={submitting || picked === 'webauthn'}
            className="w-full h-12 rounded-xl bg-brand-navy hover:bg-brand-navy-light font-cairo text-base shadow-lg hover:shadow-xl transition-all"
            data-testid="mfa-verify-btn"
          >
            {submitting ? (
              <span className="flex items-center gap-2">
                <Loader2 className="h-5 w-5 animate-spin" />
                {lang === 'ar' ? 'جارٍ التحقق…' : 'Verifying…'}
              </span>
            ) : (
              <span className="flex items-center gap-2">
                {lang === 'ar' ? 'تحقق ومتابعة' : 'Verify & continue'}
                {isRTL ? <ArrowLeft className="h-5 w-5" /> : <ArrowRight className="h-5 w-5" />}
              </span>
            )}
          </Button>

          <div className={`flex items-center justify-between gap-2 ${isRTL ? 'flex-row-reverse' : ''}`}>
            {picked === 'email_otp' ? (
              <button
                type="button"
                onClick={sendEmailOtp}
                disabled={resendDisabled}
                className="text-xs font-tajawal text-indigo-600 hover:text-indigo-700 disabled:text-muted-foreground disabled:cursor-not-allowed"
                data-testid="mfa-resend-btn"
              >
                {resendCooldownUntil > now
                  ? (lang === 'ar' ? `إعادة الإرسال خلال ${resendSecondsLeft}ث` : `Resend in ${resendSecondsLeft}s`)
                  : (lang === 'ar' ? 'إعادة إرسال الرمز' : 'Resend code')}
              </button>
            ) : <span />}

            {initialKinds.length > 1 && (
              <button
                type="button"
                onClick={() => {
                  setPicked(null);
                  setCode('');
                  setError('');
                  setOtpInfo(null);
                  setOtpSendingState('idle');
                  autoSentRef.current = false;
                }}
                disabled={submitting}
                className="text-xs font-tajawal text-muted-foreground hover:text-foreground disabled:opacity-50"
                data-testid="mfa-change-method-btn"
              >
                {lang === 'ar' ? 'اختيار وسيلة أخرى' : 'Choose another method'}
              </button>
            )}
          </div>

          <button
            type="button"
            onClick={onCancel}
            disabled={submitting}
            className="w-full text-xs font-tajawal text-muted-foreground hover:text-foreground py-2 disabled:opacity-50"
            data-testid="mfa-cancel-link-2"
          >
            {lang === 'ar' ? 'العودة لتسجيل الدخول' : 'Back to sign in'}
          </button>
        </div>
      )}

      {challengeExpired && (
        <Button
          type="button"
          onClick={onCancel}
          className="w-full h-11 rounded-xl bg-brand-navy hover:bg-brand-navy-light font-cairo"
        >
          {lang === 'ar' ? 'إعادة تسجيل الدخول' : 'Sign in again'}
        </Button>
      )}
    </div>
  );
}
