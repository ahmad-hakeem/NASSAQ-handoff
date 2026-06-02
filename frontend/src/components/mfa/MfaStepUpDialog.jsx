import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { ShieldCheck, Mail, KeyRound, Smartphone, LifeBuoy, Loader2, AlertCircle } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const FACTOR_META = {
  webauthn: {
    icon: KeyRound,
    label_ar: 'مفتاح الأمان (Passkey)',
    label_en: 'Security key / Passkey',
    description_ar: 'استخدم بصمة الإصبع أو الوجه أو مفتاح الأمان',
  },
  totp: {
    icon: Smartphone,
    label_ar: 'تطبيق المصادقة',
    label_en: 'Authenticator app',
    description_ar: 'أدخل الرمز المعروض في تطبيق المصادقة',
  },
  email_otp: {
    icon: Mail,
    label_ar: 'رمز البريد الإلكتروني',
    label_en: 'Email code',
    description_ar: 'سنرسل رمزاً مكوناً من 6 أرقام إلى بريدك',
  },
  recovery_code: {
    icon: LifeBuoy,
    label_ar: 'رمز الاسترداد',
    label_en: 'Recovery code',
    description_ar: 'استخدم أحد رموز الاسترداد التي حفظتها',
  },
};

function getCurrentAccessToken() {
  return localStorage.getItem('nassaq_token') || null;
}

function getLang() {
  try {
    return (typeof window !== 'undefined' && localStorage.getItem('nassaq_language')) || 'ar';
  } catch {
    return 'ar';
  }
}

export default function MfaStepUpDialog({ open, errorContext, onSuccess, onCancel }) {
  const [phase, setPhase] = useState('starting'); // 'starting' | 'pick' | 'verify' | 'submitting' | 'error'
  const [challenge, setChallenge] = useState(null); // { challenge_token, expires_at, available_factor_kinds, mfa_tier }
  const [pickedFactor, setPickedFactor] = useState(null);
  const [code, setCode] = useState('');
  const [errorMsg, setErrorMsg] = useState('');
  const [otpSendInfo, setOtpSendInfo] = useState(null); // { masked_email, expires_at, remaining_sends }
  const startedForRef = useRef(null);
  const lang = getLang();

  const reset = useCallback(() => {
    setPhase('starting');
    setChallenge(null);
    setPickedFactor(null);
    setCode('');
    setErrorMsg('');
    setOtpSendInfo(null);
    startedForRef.current = null;
  }, []);

  // Whenever the dialog (re)opens, mint a fresh challenge.
  useEffect(() => {
    if (!open) {
      reset();
      return;
    }
    const accessToken = getCurrentAccessToken();
    if (!accessToken) {
      setErrorMsg(lang === 'en' ? 'Not signed in.' : 'لم يتم تسجيل الدخول.');
      setPhase('error');
      return;
    }
    // Avoid double-firing in React StrictMode dev double-mount.
    const key = `${accessToken.slice(-12)}:${errorContext?.requestUrl || ''}`;
    if (startedForRef.current === key) return;
    startedForRef.current = key;

    (async () => {
      try {
        setPhase('starting');
        setErrorMsg('');
        const res = await axios.post(
          `${API_URL}/api/auth/mfa/stepup/start`,
          {},
          { headers: { Authorization: `Bearer ${accessToken}` } },
        );
        const data = res.data || {};
        const kinds = data.available_factor_kinds || [];
        setChallenge({
          challenge_token: data.challenge_token,
          challenge_expires_at: data.challenge_expires_at,
          available_factor_kinds: kinds,
          mfa_tier: data.mfa_tier,
        });
        if (kinds.length === 1) {
          setPickedFactor(kinds[0]);
          setPhase('verify');
        } else if (kinds.length === 0) {
          setErrorMsg(
            lang === 'en'
              ? 'No second-factor methods are available on this account.'
              : 'لا توجد وسائل تحقق متاحة لهذا الحساب.',
          );
          setPhase('error');
        } else {
          setPhase('pick');
        }
      } catch (err) {
        const detail =
          err?.response?.data?.error?.message ||
          err?.response?.data?.detail ||
          (lang === 'en'
            ? 'Could not start step-up verification.'
            : 'تعذر بدء التحقق الإضافي.');
        setErrorMsg(typeof detail === 'string' ? detail : JSON.stringify(detail));
        setPhase('error');
      }
    })();
  }, [open, errorContext, lang, reset]);

  // Auto-send email OTP the moment that factor is picked.
  useEffect(() => {
    if (phase !== 'verify') return;
    if (pickedFactor !== 'email_otp') return;
    if (otpSendInfo) return;
    if (!challenge?.challenge_token) return;

    (async () => {
      try {
        const res = await axios.post(
          `${API_URL}/api/auth/mfa/email-otp/send`,
          {},
          { headers: { Authorization: `Bearer ${challenge.challenge_token}` } },
        );
        setOtpSendInfo(res.data || {});
      } catch (err) {
        const detail =
          err?.response?.data?.error?.message ||
          err?.response?.data?.detail ||
          (lang === 'en' ? 'Could not send the email code.' : 'تعذر إرسال رمز البريد.');
        setErrorMsg(typeof detail === 'string' ? detail : JSON.stringify(detail));
      }
    })();
  }, [phase, pickedFactor, challenge, otpSendInfo, lang]);

  const handlePick = (kind) => {
    setPickedFactor(kind);
    setCode('');
    setErrorMsg('');
    setPhase('verify');
  };

  const handleVerify = async () => {
    if (!challenge?.challenge_token) return;
    setErrorMsg('');

    if (
      (pickedFactor === 'totp' || pickedFactor === 'email_otp' || pickedFactor === 'recovery_code') &&
      !code.trim()
    ) {
      setErrorMsg(lang === 'en' ? 'Please enter the code.' : 'يرجى إدخال الرمز.');
      return;
    }

    if (pickedFactor === 'webauthn') {
      setErrorMsg(
        lang === 'en'
          ? 'Passkey verification will be available in the next update — please use another method.'
          : 'التحقق عبر Passkey سيتوفر في التحديث القادم — يرجى استخدام وسيلة أخرى.',
      );
      return;
    }

    try {
      setPhase('submitting');
      const body = {
        factor_kind: pickedFactor,
        code: code.trim() || null,
      };
      const res = await axios.post(
        `${API_URL}/api/auth/mfa/stepup/verify`,
        body,
        { headers: { Authorization: `Bearer ${challenge.challenge_token}` } },
      );
      const newAccess = res.data?.access_token;
      if (!newAccess) {
        throw new Error('NO_ACCESS_TOKEN');
      }
      // Persist the refreshed access token so subsequent requests include it.
      try {
        localStorage.setItem('nassaq_token', newAccess);
      } catch {}
      onSuccess?.(newAccess);
    } catch (err) {
      const detail =
        err?.response?.data?.error?.message ||
        err?.response?.data?.detail ||
        (lang === 'en' ? 'Verification failed.' : 'فشل التحقق.');
      setErrorMsg(typeof detail === 'string' ? detail : JSON.stringify(detail));
      setPhase('verify');
    }
  };

  const handleResendOtp = async () => {
    if (!challenge?.challenge_token) return;
    setErrorMsg('');
    try {
      const res = await axios.post(
        `${API_URL}/api/auth/mfa/email-otp/send`,
        {},
        { headers: { Authorization: `Bearer ${challenge.challenge_token}` } },
      );
      setOtpSendInfo(res.data || {});
    } catch (err) {
      const detail =
        err?.response?.data?.error?.message ||
        err?.response?.data?.detail ||
        (lang === 'en' ? 'Could not resend the code.' : 'تعذر إعادة إرسال الرمز.');
      setErrorMsg(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }
  };

  const title = useMemo(() => (lang === 'en' ? 'Verify it’s you' : 'يرجى التحقق من هويتك'), [lang]);
  const subtitle = useMemo(
    () =>
      lang === 'en'
        ? 'This action requires a fresh second-factor check.'
        : 'هذا الإجراء يتطلب تأكيد العامل الثاني من جديد.',
    [lang],
  );

  // Keep dialog mounted but conditionally visible — must NOT unmount routes.
  return (
    <Dialog
      open={open}
      onOpenChange={(isOpen) => {
        if (!isOpen && open) {
          // Block close-via-escape/overlay only while the request is in flight.
          if (phase === 'submitting') return;
          onCancel?.();
        }
      }}
    >
      <DialogContent
        className="max-w-md rounded-2xl p-0 overflow-hidden border-0 shadow-2xl"
        dir={lang === 'en' ? 'ltr' : 'rtl'}
        onInteractOutside={(e) => {
          if (phase === 'submitting') e.preventDefault();
        }}
        onEscapeKeyDown={(e) => {
          if (phase === 'submitting') e.preventDefault();
        }}
      >
        <div className="bg-indigo-50 border-b border-indigo-200 px-6 pt-6 pb-4">
          <DialogHeader className="flex flex-row items-center gap-3 space-y-0">
            <div className="flex-shrink-0 w-12 h-12 rounded-full bg-indigo-50 border-2 border-indigo-200 flex items-center justify-center">
              <ShieldCheck className="h-6 w-6 text-indigo-500" />
            </div>
            <div className={`flex-1 ${lang === 'en' ? 'text-left' : 'text-right'}`}>
              <DialogTitle className="text-lg font-bold font-cairo text-gray-900">
                {title}
              </DialogTitle>
              <DialogDescription className="text-xs text-gray-600 font-cairo mt-1">
                {subtitle}
              </DialogDescription>
            </div>
          </DialogHeader>
        </div>

        <div className="px-6 py-5 min-h-[140px]">
          {phase === 'starting' && (
            <div className="flex items-center justify-center py-6 text-gray-500 gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="font-cairo text-sm">
                {lang === 'en' ? 'Preparing verification…' : 'جارٍ تجهيز التحقق…'}
              </span>
            </div>
          )}

          {phase === 'pick' && (
            <div className="space-y-2">
              {(challenge?.available_factor_kinds || []).map((kind) => {
                const meta = FACTOR_META[kind];
                if (!meta) return null;
                const Icon = meta.icon;
                return (
                  <button
                    key={kind}
                    type="button"
                    onClick={() => handlePick(kind)}
                    className={`w-full flex items-center gap-3 p-3 rounded-xl border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50/50 transition-all ${lang === 'en' ? 'text-left' : 'text-right'}`}
                  >
                    <Icon className="h-5 w-5 text-indigo-500 flex-shrink-0" />
                    <div className="flex-1">
                      <div className="font-cairo text-sm font-semibold text-gray-900">
                        {lang === 'en' ? meta.label_en : meta.label_ar}
                      </div>
                      <div className="font-cairo text-xs text-gray-500 mt-0.5">
                        {meta.description_ar}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          {(phase === 'verify' || phase === 'submitting') && (
            <div className="space-y-3">
              <div className={`text-sm text-gray-700 font-cairo ${lang === 'en' ? 'text-left' : 'text-right'}`}>
                {pickedFactor === 'email_otp' && (
                  <>
                    {otpSendInfo?.masked_email
                      ? lang === 'en'
                        ? `Sent a 6-digit code to ${otpSendInfo.masked_email}`
                        : `أرسلنا رمزاً مكوناً من 6 أرقام إلى ${otpSendInfo.masked_email}`
                      : lang === 'en'
                        ? 'Sending the email code…'
                        : 'جارٍ إرسال رمز البريد…'}
                  </>
                )}
                {pickedFactor === 'totp' && (lang === 'en'
                  ? 'Open your authenticator app and enter the current 6-digit code.'
                  : 'افتح تطبيق المصادقة وأدخل الرمز الحالي المكون من 6 أرقام.')}
                {pickedFactor === 'recovery_code' && (lang === 'en'
                  ? 'Enter one of your saved recovery codes.'
                  : 'أدخل أحد رموز الاسترداد المحفوظة لديك.')}
              </div>

              <Input
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder={
                  pickedFactor === 'recovery_code'
                    ? 'XXXX-XXXX-XXXX'
                    : '000000'
                }
                autoFocus
                inputMode={pickedFactor === 'recovery_code' ? 'text' : 'numeric'}
                maxLength={pickedFactor === 'recovery_code' ? 14 : 6}
                disabled={phase === 'submitting'}
                className="text-center font-mono text-lg tracking-[0.4em] py-3 rounded-xl"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && phase !== 'submitting') {
                    handleVerify();
                  }
                }}
                dir="ltr"
              />

              {pickedFactor === 'email_otp' && (
                <button
                  type="button"
                  onClick={handleResendOtp}
                  disabled={phase === 'submitting'}
                  className="text-xs font-cairo text-indigo-600 hover:text-indigo-700 disabled:opacity-50"
                >
                  {lang === 'en' ? 'Resend code' : 'إعادة إرسال الرمز'}
                </button>
              )}
            </div>
          )}

          {phase === 'error' && (
            <div className="flex items-start gap-2 text-red-600">
              <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
              <div className="font-cairo text-sm text-right flex-1 whitespace-pre-wrap">
                {errorMsg}
              </div>
            </div>
          )}

          {errorMsg && phase !== 'error' && (
            <div className="mt-3 flex items-start gap-2 text-red-600">
              <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
              <div className="font-cairo text-xs flex-1 whitespace-pre-wrap text-right">
                {errorMsg}
              </div>
            </div>
          )}
        </div>

        <div className="px-6 pb-5 gap-2 flex flex-row-reverse">
          {(phase === 'verify' || phase === 'submitting') && (
            <Button
              onClick={handleVerify}
              disabled={phase === 'submitting'}
              className="bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl px-6 py-2.5 text-sm font-bold font-cairo shadow-md hover:shadow-lg transition-all"
            >
              {phase === 'submitting' && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
              {lang === 'en' ? 'Verify' : 'تحقق'}
            </Button>
          )}

          {phase === 'verify' && (challenge?.available_factor_kinds || []).length > 1 && (
            <Button
              variant="outline"
              onClick={() => {
                setPickedFactor(null);
                setCode('');
                setErrorMsg('');
                setOtpSendInfo(null);
                setPhase('pick');
              }}
              disabled={phase === 'submitting'}
              className="rounded-xl px-4 py-2.5 text-sm font-cairo border-gray-200"
            >
              {lang === 'en' ? 'Choose another' : 'اختيار وسيلة أخرى'}
            </Button>
          )}

          <Button
            variant="outline"
            onClick={() => onCancel?.()}
            disabled={phase === 'submitting'}
            className="rounded-xl px-4 py-2.5 text-sm font-cairo border-gray-200 hover:bg-gray-50"
          >
            {lang === 'en' ? 'Cancel' : 'إلغاء'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
