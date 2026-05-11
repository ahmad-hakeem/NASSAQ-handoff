import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';
import { useNassaqAlert } from '../ui/NassaqAlertDialog';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import {
  ShieldCheck,
  Smartphone,
  Mail,
  KeyRound,
  LifeBuoy,
  Loader2,
  CheckCircle,
  AlertTriangle,
  Copy,
  Download,
  RefreshCw,
  Plus,
} from 'lucide-react';

const TIER_META = {
  A: { ar: 'المستوى أ — تحقق إلزامي قوي', en: 'Tier A — strong MFA required', tone: 'bg-purple-100 text-purple-700' },
  B: { ar: 'المستوى ب — تحقق ببريد إلكتروني', en: 'Tier B — email-based MFA', tone: 'bg-indigo-100 text-indigo-700' },
  C: { ar: 'المستوى ج — تحقق ببريد إلكتروني', en: 'Tier C — email-based MFA', tone: 'bg-cyan-100 text-cyan-700' },
};

const FACTOR_LABEL = {
  webauthn: { ar: 'مفتاح أمان (Passkey)', en: 'Security key / Passkey', icon: KeyRound },
  totp: { ar: 'تطبيق المصادقة', en: 'Authenticator app', icon: Smartphone },
  email_otp: { ar: 'رمز عبر البريد الإلكتروني', en: 'Email code', icon: Mail },
  recovery_code: { ar: 'رموز الاسترداد', en: 'Recovery codes', icon: LifeBuoy },
};

function formatDate(value, lang) {
  if (!value) return null;
  try {
    return new Date(value).toLocaleString(lang === 'ar' ? 'ar-SA' : 'en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return null;
  }
}

export default function MfaSecuritySection() {
  const { api } = useAuth();
  const { isRTL } = useTheme();
  const { t } = useTranslation();
  const { nassaqError, nassaqSuccess, nassaqWarning } = useNassaqAlert();
  const lang = isRTL ? 'ar' : 'en';

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null); // MfaFactorsResponse
  const [refreshKey, setRefreshKey] = useState(0);

  const [totpDialogOpen, setTotpDialogOpen] = useState(false);
  const [totpEnroll, setTotpEnroll] = useState(null); // { factor_id, qr_svg, otpauth_uri, account_label }
  const [totpCode, setTotpCode] = useState('');
  const [totpBusy, setTotpBusy] = useState(false);
  const [totpError, setTotpError] = useState('');

  const [recoveryDialogOpen, setRecoveryDialogOpen] = useState(false);
  const [recoveryPwd, setRecoveryPwd] = useState('');
  const [recoveryBusy, setRecoveryBusy] = useState(false);
  const [recoveryError, setRecoveryError] = useState('');
  const [recoveryNewCodes, setRecoveryNewCodes] = useState(null);

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  useEffect(() => {
    let cancel = false;
    (async () => {
      setLoading(true);
      try {
        const res = await api.get('/auth/mfa/factors');
        if (!cancel) setData(res.data);
      } catch (err) {
        if (!cancel) setData(null);
      } finally {
        if (!cancel) setLoading(false);
      }
    })();
    return () => { cancel = true; };
  }, [api, refreshKey]);

  const allowed = useMemo(() => new Set(data?.allowed_kinds || []), [data]);
  const factorsByKind = useMemo(() => {
    const m = {};
    for (const f of data?.factors || []) {
      if (!m[f.kind]) m[f.kind] = [];
      m[f.kind].push(f);
    }
    return m;
  }, [data]);

  const tierBadge = data?.tier ? TIER_META[data.tier] : null;
  const remaining = data?.unused_recovery_codes ?? 0;
  const acknowledged = !!data?.mfa_recovery_codes_acknowledged;

  // ---- TOTP enrolment ----
  const beginTotp = async () => {
    setTotpBusy(true);
    setTotpError('');
    setTotpCode('');
    try {
      const r = await api.post('/auth/mfa/totp/enroll/begin');
      setTotpEnroll(r.data);
      setTotpDialogOpen(true);
    } catch (err) {
      const msg = err?.response?.data?.error?.message || err?.response?.data?.detail || (lang === 'ar' ? 'تعذر بدء التسجيل' : 'Could not start enrolment');
      nassaqError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setTotpBusy(false);
    }
  };

  const confirmTotp = async () => {
    if (!totpEnroll?.factor_id || !totpCode.trim()) {
      setTotpError(lang === 'ar' ? 'يرجى إدخال رمز التطبيق.' : 'Please enter the app code.');
      return;
    }
    setTotpBusy(true);
    setTotpError('');
    try {
      await api.post('/auth/mfa/totp/enroll/confirm', { factor_id: totpEnroll.factor_id, code: totpCode.trim() });
      setTotpDialogOpen(false);
      setTotpEnroll(null);
      setTotpCode('');
      nassaqSuccess(lang === 'ar' ? 'تم تفعيل تطبيق المصادقة بنجاح.' : 'Authenticator app activated.');
      refresh();
    } catch (err) {
      const msg = err?.response?.data?.error?.message || err?.response?.data?.detail || (lang === 'ar' ? 'الرمز غير صحيح.' : 'Invalid code.');
      setTotpError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setTotpBusy(false);
    }
  };

  // ---- Recovery codes ----
  const submitRegenerate = async () => {
    if (!recoveryPwd) {
      setRecoveryError(lang === 'ar' ? 'يرجى إدخال كلمة المرور.' : 'Please enter your password.');
      return;
    }
    setRecoveryBusy(true);
    setRecoveryError('');
    try {
      const r = await api.post('/auth/mfa/recovery-codes/regenerate', { password: recoveryPwd });
      setRecoveryNewCodes(r.data?.codes || []);
      setRecoveryPwd('');
      refresh();
    } catch (err) {
      const msg = err?.response?.data?.error?.message || err?.response?.data?.detail || (lang === 'ar' ? 'تعذر إنشاء الرموز.' : 'Could not generate codes.');
      setRecoveryError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setRecoveryBusy(false);
    }
  };

  const closeRecoveryDialog = () => {
    setRecoveryDialogOpen(false);
    setRecoveryPwd('');
    setRecoveryError('');
    setRecoveryNewCodes(null);
  };

  const copyCodes = async () => {
    if (!recoveryNewCodes?.length) return;
    try {
      await navigator.clipboard.writeText(recoveryNewCodes.join('\n'));
      nassaqSuccess(lang === 'ar' ? 'تم نسخ الرموز.' : 'Codes copied.');
    } catch {
      nassaqError(lang === 'ar' ? 'تعذّر النسخ.' : 'Copy failed.');
    }
  };

  const downloadCodes = () => {
    if (!recoveryNewCodes?.length) return;
    const header = lang === 'ar'
      ? 'رموز استرداد NASSAQ — احفظها في مكان آمن. كل رمز يُستخدم مرة واحدة فقط.\n\n'
      : 'NASSAQ recovery codes — keep these safe. Each code can be used once.\n\n';
    const blob = new Blob([header + recoveryNewCodes.join('\n') + '\n'], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `nassaq-recovery-codes-${Date.now()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const acknowledgeRecovery = async () => {
    try {
      await api.post('/auth/mfa/recovery-codes/acknowledge');
      nassaqSuccess(lang === 'ar' ? 'تم تأكيد حفظ الرموز.' : 'Acknowledged.');
      refresh();
    } catch {
      nassaqError(lang === 'ar' ? 'تعذّر الحفظ.' : 'Acknowledgement failed.');
    }
  };

  // ---- factor row renderer ----
  const renderFactorRow = (kind, { actionsRight }) => {
    const meta = FACTOR_LABEL[kind];
    if (!meta) return null;
    const Icon = meta.icon;
    const isAllowed = allowed.has(kind);
    const enrolled = (factorsByKind[kind] || []).length > 0;
    const lastUsed = enrolled ? formatDate((factorsByKind[kind] || [])[0]?.last_used_at, lang) : null;

    return (
      <div
        key={kind}
        className={`flex items-center justify-between gap-3 p-4 rounded-xl border ${enrolled ? 'border-emerald-200 bg-emerald-50/40 dark:border-emerald-900/40 dark:bg-emerald-950/20' : isAllowed ? 'border-border/60 bg-muted/20' : 'border-border/40 bg-muted/10 opacity-70'}`}
      >
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 ${enrolled ? 'bg-emerald-500/15 text-emerald-600' : 'bg-brand-turquoise/15 text-brand-turquoise'}`}>
            <Icon className="h-5 w-5" />
          </div>
          <div className={`flex-1 min-w-0 ${isRTL ? 'text-right' : 'text-left'}`}>
            <div className="flex items-center gap-2 flex-wrap">
              <p className="font-cairo font-semibold text-sm text-foreground">
                {lang === 'ar' ? meta.ar : meta.en}
              </p>
              {enrolled && (
                <Badge className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400 border-0 text-[10px]">
                  <CheckCircle className="h-3 w-3 me-1" />
                  {lang === 'ar' ? 'مفعّل' : 'Active'}
                </Badge>
              )}
              {!isAllowed && (
                <Badge variant="outline" className="text-[10px] text-muted-foreground">
                  {lang === 'ar' ? 'غير متاح للدور' : 'Not available for role'}
                </Badge>
              )}
            </div>
            {lastUsed && (
              <p className="text-[11px] text-muted-foreground font-tajawal mt-0.5">
                {lang === 'ar' ? `آخر استخدام: ${lastUsed}` : `Last used: ${lastUsed}`}
              </p>
            )}
          </div>
        </div>
        <div className="flex-shrink-0">{actionsRight}</div>
      </div>
    );
  };

  return (
    <Card className="card-nassaq" data-testid="mfa-security-section">
      <CardHeader className="pb-4">
        <CardTitle className="font-cairo flex items-center gap-2 text-lg">
          <ShieldCheck className="h-5 w-5 text-brand-turquoise" />
          {lang === 'ar' ? 'التحقق بخطوتين (MFA)' : 'Two-step verification (MFA)'}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading && (
          <div className="flex items-center justify-center py-8 text-muted-foreground gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span className="font-tajawal text-sm">{lang === 'ar' ? 'جارٍ التحميل…' : 'Loading…'}</span>
          </div>
        )}

        {!loading && data && (
          <>
            {tierBadge && (
              <div className={`flex items-center gap-2 px-3 py-2 rounded-xl ${tierBadge.tone}`}>
                <ShieldCheck className="h-4 w-4 flex-shrink-0" />
                <span className="font-cairo text-sm font-semibold">
                  {lang === 'ar' ? tierBadge.ar : tierBadge.en}
                </span>
              </div>
            )}
            {!tierBadge && (
              <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-muted/30 text-muted-foreground">
                <ShieldCheck className="h-4 w-4 flex-shrink-0" />
                <span className="font-cairo text-sm">
                  {lang === 'ar' ? 'الحساب لا يتطلب تحققاً بخطوتين.' : 'Your account does not require MFA.'}
                </span>
              </div>
            )}

            {data.mfa_must_restore_factor && (
              <div className="flex items-start gap-2 p-3 rounded-xl bg-amber-50 dark:bg-amber-950/20 border border-amber-200/60 dark:border-amber-800/40 text-amber-800 dark:text-amber-300">
                <AlertTriangle className="h-4 w-4 flex-shrink-0 mt-0.5" />
                <span className="font-tajawal text-xs">
                  {lang === 'ar'
                    ? 'يجب إعادة تفعيل عامل تحقق قوي (مفتاح أمان أو تطبيق مصادقة) لاستئناف الإجراءات الحساسة.'
                    : 'You must re-enroll a strong factor (security key or authenticator app) before sensitive actions resume.'}
                </span>
              </div>
            )}

            <div className="space-y-2">
              {/* Authenticator app (TOTP) */}
              {(allowed.has('totp') || (factorsByKind.totp || []).length > 0) && renderFactorRow('totp', {
                actionsRight: (factorsByKind.totp || []).length > 0
                  ? <Badge variant="outline" className="text-[10px]">{lang === 'ar' ? 'مفعّل' : 'Active'}</Badge>
                  : (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={beginTotp}
                      disabled={totpBusy}
                      className="rounded-lg gap-1.5"
                      data-testid="mfa-totp-enroll-btn"
                    >
                      {totpBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
                      {lang === 'ar' ? 'تفعيل' : 'Enable'}
                    </Button>
                  ),
              })}

              {/* Email OTP — server-managed, always on when allowed */}
              {allowed.has('email_otp') && renderFactorRow('email_otp', {
                actionsRight: (
                  <Badge className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400 border-0 text-[10px]">
                    {lang === 'ar' ? 'متاح دائماً' : 'Always on'}
                  </Badge>
                ),
              })}

              {/* WebAuthn / Passkey — already-enrolled passkeys surface as
                  Active; new enrolment UI ships in the follow-up Step.
                  See Task #169 Step 11 scope. */}
              {(allowed.has('webauthn') || (factorsByKind.webauthn || []).length > 0) && renderFactorRow('webauthn', {
                actionsRight: (factorsByKind.webauthn || []).length > 0
                  ? (
                    <Badge className="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400 border-0 text-[10px]">
                      {lang === 'ar' ? 'مفعّل' : 'Active'}
                    </Badge>
                  )
                  : (
                    <Badge variant="outline" className="text-[10px] text-muted-foreground">
                      {lang === 'ar' ? 'قريباً' : 'Coming soon'}
                    </Badge>
                  ),
              })}
            </div>

            {/* Recovery codes panel */}
            {allowed.has('recovery_code') && (
              <div className={`p-4 rounded-xl border ${remaining === 0 ? 'border-amber-200 bg-amber-50/50 dark:border-amber-900/40 dark:bg-amber-950/20' : remaining <= 3 ? 'border-amber-200 bg-amber-50/30 dark:border-amber-900/40' : 'border-border/60 bg-muted/20'}`} data-testid="mfa-recovery-panel">
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    <div className="w-10 h-10 rounded-xl bg-brand-turquoise/15 text-brand-turquoise flex items-center justify-center flex-shrink-0">
                      <LifeBuoy className="h-5 w-5" />
                    </div>
                    <div className={`flex-1 min-w-0 ${isRTL ? 'text-right' : 'text-left'}`}>
                      <p className="font-cairo font-semibold text-sm text-foreground">
                        {lang === 'ar' ? 'رموز الاسترداد' : 'Recovery codes'}
                      </p>
                      <p className="text-[11px] text-muted-foreground font-tajawal mt-0.5">
                        {lang === 'ar'
                          ? 'استخدم هذه الرموز إذا فقدت الوصول إلى وسيلة التحقق الأساسية. كل رمز يُستخدم مرة واحدة فقط.'
                          : 'Use these if you lose access to your main factor. Each code can be used once.'}
                      </p>
                      <div className="flex items-center gap-2 mt-2 flex-wrap">
                        <Badge className={`${remaining === 0 ? 'bg-red-100 text-red-700' : remaining <= 3 ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'} border-0 text-[10px]`}>
                          {lang === 'ar' ? `${remaining} رمز متبقٍ` : `${remaining} remaining`}
                        </Badge>
                        {data.mfa_recovery_codes_generated_at == null && (
                          <Badge variant="outline" className="text-[10px] text-muted-foreground">
                            {lang === 'ar' ? 'لم يتم الإنشاء بعد' : 'Not generated yet'}
                          </Badge>
                        )}
                        {!acknowledged && remaining > 0 && (
                          <Badge className="bg-amber-100 text-amber-700 border-0 text-[10px]">
                            <AlertTriangle className="h-3 w-3 me-1" />
                            {lang === 'ar' ? 'لم يتم الإقرار بحفظها' : 'Not acknowledged'}
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex flex-col gap-2 flex-shrink-0">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setRecoveryDialogOpen(true)}
                      className="rounded-lg gap-1.5"
                      data-testid="mfa-recovery-regen-btn"
                    >
                      <RefreshCw className="h-3.5 w-3.5" />
                      {remaining === 0
                        ? (lang === 'ar' ? 'إنشاء رموز' : 'Generate')
                        : (lang === 'ar' ? 'إعادة الإنشاء' : 'Regenerate')}
                    </Button>
                    {!acknowledged && remaining > 0 && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={acknowledgeRecovery}
                        className="rounded-lg text-[11px] text-muted-foreground"
                        data-testid="mfa-recovery-ack-btn"
                      >
                        <CheckCircle className="h-3.5 w-3.5 me-1" />
                        {lang === 'ar' ? 'لقد حفظتها' : 'I saved them'}
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {!loading && !data && (
          <div className="text-center py-6 text-sm text-muted-foreground font-tajawal">
            {lang === 'ar' ? 'تعذر تحميل إعدادات التحقق.' : 'Could not load MFA settings.'}
          </div>
        )}
      </CardContent>

      {/* ===== TOTP enrolment dialog ===== */}
      <Dialog open={totpDialogOpen} onOpenChange={(o) => { if (!o && !totpBusy) { setTotpDialogOpen(false); setTotpEnroll(null); setTotpCode(''); setTotpError(''); } }}>
        <DialogContent className="max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader>
            <DialogTitle className="font-cairo flex items-center gap-2">
              <Smartphone className="h-5 w-5 text-brand-turquoise" />
              {lang === 'ar' ? 'تفعيل تطبيق المصادقة' : 'Set up authenticator app'}
            </DialogTitle>
            <DialogDescription className="font-tajawal text-xs">
              {lang === 'ar'
                ? 'افتح تطبيق المصادقة (Google Authenticator، Microsoft Authenticator، 1Password…) وامسح الرمز التالي ثم أدخل الرمز المعروض لإكمال التفعيل.'
                : 'Open your authenticator app (Google Authenticator, Microsoft Authenticator, 1Password…), scan the QR code below, then enter the 6-digit code to finish.'}
            </DialogDescription>
          </DialogHeader>
          {totpEnroll?.qr_svg && (
            <div className="flex justify-center bg-white p-4 rounded-xl border border-border/40">
              {/* qr_svg is a server-built SVG string */}
              <div
                className="[&>svg]:w-44 [&>svg]:h-44"
                dangerouslySetInnerHTML={{ __html: totpEnroll.qr_svg }}
              />
            </div>
          )}
          {totpEnroll?.account_label && (
            <p className="text-[11px] text-center text-muted-foreground font-tajawal" dir="ltr">
              {totpEnroll.account_label}
            </p>
          )}
          <div className="space-y-2">
            <Label htmlFor="totp-confirm-code" className="font-tajawal text-sm">
              {lang === 'ar' ? 'الرمز من التطبيق' : 'Code from the app'}
            </Label>
            <Input
              id="totp-confirm-code"
              value={totpCode}
              onChange={(e) => setTotpCode(e.target.value)}
              placeholder="000000"
              maxLength={6}
              inputMode="numeric"
              autoComplete="one-time-code"
              className="text-center font-mono text-lg tracking-[0.4em] py-3 h-12 rounded-xl"
              dir="ltr"
              autoFocus
              data-testid="totp-confirm-code-input"
              onKeyDown={(e) => { if (e.key === 'Enter' && !totpBusy) confirmTotp(); }}
            />
            {totpError && (
              <p className="text-xs text-red-600 font-tajawal">{totpError}</p>
            )}
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setTotpDialogOpen(false)} disabled={totpBusy}>
              {lang === 'ar' ? 'إلغاء' : 'Cancel'}
            </Button>
            <Button onClick={confirmTotp} disabled={totpBusy} className="bg-brand-navy hover:bg-brand-navy-light gap-2" data-testid="totp-confirm-btn">
              {totpBusy && <Loader2 className="h-4 w-4 animate-spin" />}
              {lang === 'ar' ? 'تأكيد التفعيل' : 'Confirm'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ===== Recovery codes dialog ===== */}
      <Dialog open={recoveryDialogOpen} onOpenChange={(o) => { if (!o && !recoveryBusy) closeRecoveryDialog(); }}>
        <DialogContent className="max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader>
            <DialogTitle className="font-cairo flex items-center gap-2">
              <LifeBuoy className="h-5 w-5 text-brand-turquoise" />
              {recoveryNewCodes
                ? (lang === 'ar' ? 'احفظ رموز الاسترداد' : 'Save your recovery codes')
                : (lang === 'ar' ? 'إنشاء رموز استرداد جديدة' : 'Generate recovery codes')}
            </DialogTitle>
            <DialogDescription className="font-tajawal text-xs">
              {recoveryNewCodes
                ? (lang === 'ar'
                    ? 'احفظ هذه الرموز في مكان آمن. لن نعرضها مرة أخرى. كل رمز يُستخدم مرة واحدة فقط.'
                    : 'Store these somewhere safe. We will not show them again. Each code can be used once.')
                : (lang === 'ar'
                    ? 'إنشاء مجموعة رموز جديدة سيُلغي صلاحية الرموز القديمة فوراً. أدخل كلمة المرور الحالية للتأكيد.'
                    : 'Creating a new set immediately invalidates your old codes. Enter your current password to confirm.')}
            </DialogDescription>
          </DialogHeader>

          {!recoveryNewCodes && (
            <div className="space-y-2">
              <Label htmlFor="recovery-pwd" className="font-tajawal text-sm">
                {lang === 'ar' ? 'كلمة المرور الحالية' : 'Current password'}
              </Label>
              <Input
                id="recovery-pwd"
                type="password"
                value={recoveryPwd}
                onChange={(e) => setRecoveryPwd(e.target.value)}
                className="rounded-xl"
                dir="ltr"
                autoFocus
                data-testid="recovery-pwd-input"
                onKeyDown={(e) => { if (e.key === 'Enter' && !recoveryBusy) submitRegenerate(); }}
              />
              {recoveryError && <p className="text-xs text-red-600 font-tajawal">{recoveryError}</p>}
            </div>
          )}

          {recoveryNewCodes && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-2 p-4 rounded-xl bg-muted/40 border border-border/40">
                {recoveryNewCodes.map((c) => (
                  <code key={c} className="font-mono text-sm text-center py-1.5 px-2 rounded bg-background border border-border/40" dir="ltr">
                    {c}
                  </code>
                ))}
              </div>
              <div className="flex gap-2 flex-wrap">
                <Button size="sm" variant="outline" onClick={copyCodes} className="gap-1.5" data-testid="recovery-copy-btn">
                  <Copy className="h-3.5 w-3.5" />
                  {lang === 'ar' ? 'نسخ' : 'Copy'}
                </Button>
                <Button size="sm" variant="outline" onClick={downloadCodes} className="gap-1.5" data-testid="recovery-download-btn">
                  <Download className="h-3.5 w-3.5" />
                  {lang === 'ar' ? 'تنزيل' : 'Download'}
                </Button>
              </div>
            </div>
          )}

          <DialogFooter className="gap-2">
            {!recoveryNewCodes ? (
              <>
                <Button variant="outline" onClick={closeRecoveryDialog} disabled={recoveryBusy}>
                  {lang === 'ar' ? 'إلغاء' : 'Cancel'}
                </Button>
                <Button onClick={submitRegenerate} disabled={recoveryBusy} className="bg-brand-navy hover:bg-brand-navy-light gap-2" data-testid="recovery-submit-btn">
                  {recoveryBusy && <Loader2 className="h-4 w-4 animate-spin" />}
                  {lang === 'ar' ? 'إنشاء الرموز' : 'Generate'}
                </Button>
              </>
            ) : (
              <Button
                onClick={async () => { await acknowledgeRecovery(); closeRecoveryDialog(); }}
                className="bg-brand-navy hover:bg-brand-navy-light gap-2"
                data-testid="recovery-saved-btn"
              >
                <CheckCircle className="h-4 w-4" />
                {lang === 'ar' ? 'حفظت الرموز' : 'I saved them'}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
