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
  RotateCcw,
  ShieldOff,
} from 'lucide-react';

const TIER_META = {
  A: { ar: 'المستوى أ — تحقق إلزامي قوي', en: 'Tier A — strong MFA required', tone: 'bg-purple-100 text-purple-700' },
  B: { ar: 'المستوى ب — تحقق عبر تطبيق المصادقة', en: 'Tier B — authenticator-app MFA', tone: 'bg-indigo-100 text-indigo-700' },
  C: { ar: 'المستوى ج — تحقق عبر تطبيق المصادقة', en: 'Tier C — authenticator-app MFA', tone: 'bg-cyan-100 text-cyan-700' },
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

export default function MfaSecuritySection({ onChange } = {}) {
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

  // Reset / Reconfigure (swap to a new authenticator app without
  // disabling MFA in between). Backend mints a pending TOTP factor on
  // /auth/mfa/reset/begin and atomically swaps + rotates recovery
  // codes on /auth/mfa/reset/finalize.
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [resetEnroll, setResetEnroll] = useState(null); // {factor_id, qr_svg, otpauth_uri, account_label}
  const [resetCode, setResetCode] = useState('');
  const [resetBusy, setResetBusy] = useState(false);
  const [resetError, setResetError] = useState('');
  const [resetNewCodes, setResetNewCodes] = useState(null);

  // Disable MFA (only when the user's role does not mandate MFA).
  const [disableDialogOpen, setDisableDialogOpen] = useState(false);
  const [disablePwd, setDisablePwd] = useState('');
  const [disableBusy, setDisableBusy] = useState(false);
  const [disableError, setDisableError] = useState('');

  const refresh = useCallback(() => {
    setRefreshKey((k) => k + 1);
    if (typeof onChange === 'function') {
      try { onChange(); } catch { /* parent handles its own errors */ }
    }
  }, [onChange]);

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
  const recoveryGeneratedAt = data?.mfa_recovery_codes_generated_at || null;
  // Canonical "do recovery codes exist?" predicate. Either a positive
  // unused count from the live recovery-codes table, or a generated-at
  // stamp on the user row, proves codes have been minted at least once.
  const hasRecoveryCodes = remaining > 0 || !!recoveryGeneratedAt;

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
    // Capture pre-enrollment restore-required state so we can nudge the
    // user back to Change Password (Task #351) once they've satisfied the
    // re-enrollment requirement triggered by a recovery-code login.
    const wasRestoreRequired = !!data?.mfa_must_restore_factor;
    try {
      await api.post('/auth/mfa/totp/enroll/confirm', { factor_id: totpEnroll.factor_id, code: totpCode.trim() });
      setTotpDialogOpen(false);
      setTotpEnroll(null);
      setTotpCode('');
      nassaqSuccess(lang === 'ar' ? 'تم تفعيل تطبيق المصادقة بنجاح.' : 'Authenticator app activated.');
      if (wasRestoreRequired) {
        nassaqWarning(
          lang === 'ar'
            ? 'تم استعادة عامل التحقق. يمكنك الآن إعادة محاولة تغيير كلمة المرور.'
            : 'Factor restored. You can now retry changing your password.'
        );
      }
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

  // ---- Reset / Reconfigure ----
  const beginReset = async () => {
    setResetBusy(true);
    setResetError('');
    setResetCode('');
    setResetNewCodes(null);
    setResetEnroll(null);
    try {
      const r = await api.post('/auth/mfa/reset/begin');
      setResetEnroll(r.data);
      setResetDialogOpen(true);
    } catch (err) {
      const msg = err?.response?.data?.error?.message || err?.response?.data?.detail || (lang === 'ar' ? 'تعذر بدء إعادة الضبط' : 'Could not start reset');
      nassaqError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setResetBusy(false);
    }
  };

  const finalizeReset = async () => {
    if (!resetEnroll?.factor_id || !resetCode.trim()) {
      setResetError(lang === 'ar' ? 'يرجى إدخال رمز التطبيق.' : 'Please enter the app code.');
      return;
    }
    setResetBusy(true);
    setResetError('');
    try {
      const r = await api.post('/auth/mfa/reset/finalize', {
        factor_id: resetEnroll.factor_id,
        code: resetCode.trim(),
      });
      // Server returns fresh recovery codes the user must save now;
      // keep dialog open in "saved" mode so they can copy/download.
      setResetNewCodes(Array.isArray(r.data?.recovery_codes) ? r.data.recovery_codes : []);
      setResetCode('');
      setResetEnroll(null);
      nassaqSuccess(lang === 'ar' ? 'تم استبدال تطبيق المصادقة بنجاح.' : 'Authenticator app replaced.');
      refresh();
    } catch (err) {
      const msg = err?.response?.data?.error?.message || err?.response?.data?.detail || (lang === 'ar' ? 'الرمز غير صحيح.' : 'Invalid code.');
      setResetError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setResetBusy(false);
    }
  };

  const closeResetDialog = () => {
    if (resetBusy) return;
    setResetDialogOpen(false);
    setResetEnroll(null);
    setResetCode('');
    setResetError('');
    setResetNewCodes(null);
  };

  const copyResetCodes = async () => {
    if (!resetNewCodes?.length) return;
    try {
      await navigator.clipboard.writeText(resetNewCodes.join('\n'));
      nassaqSuccess(lang === 'ar' ? 'تم نسخ الرموز.' : 'Codes copied.');
    } catch {
      nassaqError(lang === 'ar' ? 'تعذّر النسخ.' : 'Copy failed.');
    }
  };

  const downloadResetCodes = () => {
    if (!resetNewCodes?.length) return;
    const header = lang === 'ar'
      ? 'رموز استرداد NASSAQ — احفظها في مكان آمن. كل رمز يُستخدم مرة واحدة فقط.\n\n'
      : 'NASSAQ recovery codes — keep these safe. Each code can be used once.\n\n';
    const blob = new Blob([header + resetNewCodes.join('\n') + '\n'], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `nassaq-recovery-codes-${Date.now()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // ---- Disable MFA ----
  const submitDisable = async () => {
    if (!disablePwd) {
      setDisableError(lang === 'ar' ? 'يرجى إدخال كلمة المرور.' : 'Please enter your password.');
      return;
    }
    setDisableBusy(true);
    setDisableError('');
    try {
      await api.post('/auth/mfa/disable', { password: disablePwd });
      setDisableDialogOpen(false);
      setDisablePwd('');
      nassaqSuccess(lang === 'ar' ? 'تم إلغاء تفعيل التحقق بخطوتين.' : 'MFA disabled.');
      refresh();
    } catch (err) {
      const status = err?.response?.status;
      const msg = err?.response?.data?.error?.message || err?.response?.data?.detail;
      // 409 means the role mandates MFA → guide the user to Reset.
      if (status === 409) {
        setDisableError(typeof msg === 'string'
          ? msg
          : (lang === 'ar'
              ? 'هذا الحساب يتطلب تحققاً بخطوتين بحكم دوره — استخدم إعادة الضبط بدلاً من الإلغاء.'
              : 'This role requires MFA — use Reset instead of Disable.'));
      } else {
        setDisableError(typeof msg === 'string'
          ? msg
          : (lang === 'ar' ? 'تعذّر إلغاء التفعيل.' : 'Could not disable MFA.'));
      }
    } finally {
      setDisableBusy(false);
    }
  };

  const closeDisableDialog = () => {
    if (disableBusy) return;
    setDisableDialogOpen(false);
    setDisablePwd('');
    setDisableError('');
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
            {!tierBadge && (() => {
              // Opt-in MFA banner. When the user's role does not mandate MFA,
              // we replace the passive "not required" pill with an active CTA
              // that lets them voluntarily enrol an authenticator app. Once
              // at least one factor is active, we flip the banner to a green
              // confirmation state — the factor rows below still surface the
              // Reset / Disable actions for managing the enrolled factor(s).
              const anyActiveFactor = (data?.factors || []).some((f) => f.is_active !== false);
              if (anyActiveFactor) {
                return (
                  <div
                    className="flex items-center gap-2 px-3 py-2 rounded-xl bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200/60 dark:border-emerald-800/40 text-emerald-700 dark:text-emerald-300"
                    data-testid="mfa-optin-active-banner"
                  >
                    <CheckCircle className="h-4 w-4 flex-shrink-0" />
                    <span className="font-cairo text-sm font-semibold">
                      {lang === 'ar'
                        ? 'التحقق بخطوتين مفعّل لحسابك.'
                        : 'Two-step verification is active on your account.'}
                    </span>
                  </div>
                );
              }
              return (
                <div
                  className="flex flex-col sm:flex-row sm:items-center gap-3 p-4 rounded-xl bg-brand-turquoise/10 border border-brand-turquoise/30"
                  data-testid="mfa-optin-cta"
                >
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    <div className="w-10 h-10 rounded-xl bg-brand-turquoise/20 text-brand-turquoise flex items-center justify-center flex-shrink-0">
                      <ShieldCheck className="h-5 w-5" />
                    </div>
                    <div className={`flex-1 min-w-0 ${isRTL ? 'text-right' : 'text-left'}`}>
                      <p className="font-cairo font-semibold text-sm text-foreground">
                        {lang === 'ar'
                          ? 'أضف طبقة حماية إضافية لحسابك.'
                          : 'Add an extra layer of security to your account.'}
                      </p>
                      <p className="font-tajawal text-xs text-muted-foreground mt-1">
                        {lang === 'ar'
                          ? 'فعّل التحقق بخطوتين باستخدام تطبيق مصادقة لحماية حسابك حتى لو سُرقت كلمة المرور.'
                          : 'Turn on two-step verification with an authenticator app so your account stays safe even if your password is stolen.'}
                      </p>
                    </div>
                  </div>
                  <Button
                    onClick={beginTotp}
                    disabled={totpBusy}
                    className="bg-brand-turquoise hover:bg-brand-turquoise/90 text-white rounded-xl gap-1.5 flex-shrink-0"
                    data-testid="mfa-optin-enable-btn"
                  >
                    {totpBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
                    {lang === 'ar' ? 'تفعيل التحقق بخطوتين' : 'Enable two-step verification'}
                  </Button>
                </div>
              );
            })()}

            {data.mfa_must_restore_factor && (
              <div className="p-3 rounded-xl bg-amber-50 dark:bg-amber-950/20 border border-amber-300 dark:border-amber-800/60 text-amber-900 dark:text-amber-200" data-testid="mfa-restore-required-banner">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="h-5 w-5 flex-shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <p className="font-cairo font-semibold text-sm">
                      {lang === 'ar' ? 'يجب ربط تطبيق مصادقة جديد' : 'Re-link an authenticator app'}
                    </p>
                    <p className="font-tajawal text-xs mt-1">
                      {lang === 'ar'
                        ? 'تم تسجيل الدخول باستخدام رمز استرداد. يجب ربط تطبيق مصادقة جديد لاستئناف الإجراءات الحساسة.'
                        : 'You signed in using a recovery code. Link a new authenticator app before sensitive actions resume.'}
                    </p>
                    <Button
                      size="sm"
                      onClick={beginReset}
                      disabled={resetBusy}
                      className="mt-3 bg-amber-600 hover:bg-amber-700 text-white gap-1.5"
                      data-testid="mfa-restore-cta"
                    >
                      {resetBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
                      {lang === 'ar' ? 'ربط تطبيق جديد الآن' : 'Link a new app now'}
                    </Button>
                  </div>
                </div>
              </div>
            )}

            <div className="space-y-2">
              {/* Authenticator app (TOTP) */}
              {(allowed.has('totp') || (factorsByKind.totp || []).length > 0) && renderFactorRow('totp', {
                actionsRight: (factorsByKind.totp || []).length > 0
                  ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={beginReset}
                      disabled={resetBusy}
                      className="rounded-lg gap-1.5"
                      data-testid="mfa-totp-reset-btn"
                    >
                      {resetBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
                      {lang === 'ar' ? 'إعادة ضبط' : 'Reset'}
                    </Button>
                  )
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
                        {!hasRecoveryCodes && (
                          <Badge variant="outline" className="text-[10px] text-muted-foreground">
                            {lang === 'ar' ? 'لم يتم الإنشاء بعد' : 'Not generated yet'}
                          </Badge>
                        )}
                        {recoveryGeneratedAt && (
                          <span className="text-[10px] text-muted-foreground font-tajawal">
                            {lang === 'ar'
                              ? `أُنشئت في ${formatDate(recoveryGeneratedAt, lang)}`
                              : `Generated on ${formatDate(recoveryGeneratedAt, lang)}`}
                          </span>
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

            {/* ===== Disable MFA — only for roles whose tier does not
                mandate MFA, and only when at least one factor is
                currently enrolled. Mandatory-tier users must rotate
                via Reset instead. ===== */}
            {!data.tier && (data?.factors?.length || 0) > 0 && (
              <div className="p-4 rounded-xl border border-red-200 bg-red-50/40 dark:border-red-900/40 dark:bg-red-950/20" data-testid="mfa-disable-panel">
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    <div className="w-10 h-10 rounded-xl bg-red-500/15 text-red-600 flex items-center justify-center flex-shrink-0">
                      <ShieldOff className="h-5 w-5" />
                    </div>
                    <div className={`flex-1 min-w-0 ${isRTL ? 'text-right' : 'text-left'}`}>
                      <p className="font-cairo font-semibold text-sm text-foreground">
                        {lang === 'ar' ? 'إلغاء التحقق بخطوتين' : 'Disable two-step verification'}
                      </p>
                      <p className="text-[11px] text-muted-foreground font-tajawal mt-0.5">
                        {lang === 'ar'
                          ? 'سيتم إلغاء تفعيل جميع وسائل التحقق وحذف رموز الاسترداد. يمكن إعادة التفعيل لاحقاً من نفس الصفحة.'
                          : 'Deactivates all factors and burns your recovery codes. You can re-enable from this page later.'}
                      </p>
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setDisableDialogOpen(true)}
                    className="rounded-lg gap-1.5 border-red-300 text-red-700 hover:bg-red-50 hover:text-red-700 dark:hover:bg-red-950/40 dark:hover:text-red-400 focus-visible:text-red-700"
                    data-testid="mfa-disable-btn"
                  >
                    <ShieldOff className="h-3.5 w-3.5" />
                    {lang === 'ar' ? 'إلغاء التفعيل' : 'Disable'}
                  </Button>
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

      {/* ===== Reset / Reconfigure dialog ===== */}
      <Dialog open={resetDialogOpen} onOpenChange={(o) => { if (!o) closeResetDialog(); }}>
        <DialogContent className="max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader>
            <DialogTitle className="font-cairo flex items-center gap-2">
              <RotateCcw className="h-5 w-5 text-brand-turquoise" />
              {resetNewCodes
                ? (lang === 'ar' ? 'احفظ رموز الاسترداد الجديدة' : 'Save your new recovery codes')
                : (lang === 'ar' ? 'إعادة ضبط تطبيق المصادقة' : 'Reset authenticator app')}
            </DialogTitle>
            <DialogDescription className="font-tajawal text-xs">
              {resetNewCodes
                ? (lang === 'ar'
                    ? 'تم تفعيل التطبيق الجديد وإلغاء الرموز القديمة. احفظ هذه الرموز الآن — لن نعرضها مرة أخرى.'
                    : 'The new app is active and your old recovery codes were burned. Save these now — we will not show them again.')
                : (lang === 'ar'
                    ? 'امسح الرمز التالي بتطبيق المصادقة الجديد ثم أدخل الرمز المعروض. سيتم استبدال التطبيق القديم تلقائياً عند النجاح.'
                    : 'Scan the QR with your new authenticator app and enter the code below. The old app will be replaced automatically on success.')}
            </DialogDescription>
          </DialogHeader>

          {!resetNewCodes && resetEnroll?.qr_svg && (
            <div className="flex justify-center bg-white p-4 rounded-xl border border-border/40">
              <div
                className="[&>svg]:w-44 [&>svg]:h-44"
                dangerouslySetInnerHTML={{ __html: resetEnroll.qr_svg }}
              />
            </div>
          )}
          {!resetNewCodes && resetEnroll?.account_label && (
            <p className="text-[11px] text-center text-muted-foreground font-tajawal" dir="ltr">
              {resetEnroll.account_label}
            </p>
          )}

          {!resetNewCodes && (
            <div className="space-y-2">
              <Label htmlFor="reset-code" className="font-tajawal text-sm">
                {lang === 'ar' ? 'الرمز من التطبيق الجديد' : 'Code from the new app'}
              </Label>
              <Input
                id="reset-code"
                value={resetCode}
                onChange={(e) => setResetCode(e.target.value)}
                placeholder="000000"
                maxLength={6}
                inputMode="numeric"
                autoComplete="one-time-code"
                className="text-center font-mono text-lg tracking-[0.4em] py-3 h-12 rounded-xl"
                dir="ltr"
                autoFocus
                data-testid="mfa-reset-code-input"
                onKeyDown={(e) => { if (e.key === 'Enter' && !resetBusy) finalizeReset(); }}
              />
              {resetError && <p className="text-xs text-red-600 font-tajawal">{resetError}</p>}
            </div>
          )}

          {resetNewCodes && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-2 p-4 rounded-xl bg-muted/40 border border-border/40">
                {resetNewCodes.map((c) => (
                  <code key={c} className="font-mono text-sm text-center py-1.5 px-2 rounded bg-background border border-border/40" dir="ltr">
                    {c}
                  </code>
                ))}
              </div>
              <div className="flex gap-2 flex-wrap">
                <Button size="sm" variant="outline" onClick={copyResetCodes} className="gap-1.5" data-testid="mfa-reset-copy-btn">
                  <Copy className="h-3.5 w-3.5" />
                  {lang === 'ar' ? 'نسخ' : 'Copy'}
                </Button>
                <Button size="sm" variant="outline" onClick={downloadResetCodes} className="gap-1.5" data-testid="mfa-reset-download-btn">
                  <Download className="h-3.5 w-3.5" />
                  {lang === 'ar' ? 'تنزيل' : 'Download'}
                </Button>
              </div>
            </div>
          )}

          <DialogFooter className="gap-2">
            {!resetNewCodes ? (
              <>
                <Button variant="outline" onClick={closeResetDialog} disabled={resetBusy}>
                  {lang === 'ar' ? 'إلغاء' : 'Cancel'}
                </Button>
                <Button onClick={finalizeReset} disabled={resetBusy} className="bg-brand-navy hover:bg-brand-navy-light gap-2" data-testid="mfa-reset-finalize-btn">
                  {resetBusy && <Loader2 className="h-4 w-4 animate-spin" />}
                  {lang === 'ar' ? 'تأكيد الاستبدال' : 'Confirm replacement'}
                </Button>
              </>
            ) : (
              <Button onClick={closeResetDialog} className="bg-brand-navy hover:bg-brand-navy-light gap-2" data-testid="mfa-reset-done-btn">
                <CheckCircle className="h-4 w-4" />
                {lang === 'ar' ? 'حفظت الرموز' : 'I saved them'}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ===== Disable MFA dialog ===== */}
      <Dialog open={disableDialogOpen} onOpenChange={(o) => { if (!o) closeDisableDialog(); }}>
        <DialogContent className="max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader>
            <DialogTitle className="font-cairo flex items-center gap-2">
              <ShieldOff className="h-5 w-5 text-red-600" />
              {lang === 'ar' ? 'تأكيد إلغاء التحقق بخطوتين' : 'Confirm disabling MFA'}
            </DialogTitle>
            <DialogDescription className="font-tajawal text-xs">
              {lang === 'ar'
                ? 'سيتم إلغاء جميع عوامل التحقق وحذف رموز الاسترداد. أدخل كلمة المرور الحالية للتأكيد. قد يُطلب منك أيضاً إثبات تحقق إضافي.'
                : 'All MFA factors will be deactivated and your recovery codes burned. Enter your current password to confirm. You may also be asked for an MFA challenge.'}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <Label htmlFor="disable-pwd" className="font-tajawal text-sm">
              {lang === 'ar' ? 'كلمة المرور الحالية' : 'Current password'}
            </Label>
            <Input
              id="disable-pwd"
              type="password"
              value={disablePwd}
              onChange={(e) => setDisablePwd(e.target.value)}
              className="rounded-xl"
              dir="ltr"
              autoFocus
              data-testid="mfa-disable-pwd-input"
              onKeyDown={(e) => { if (e.key === 'Enter' && !disableBusy) submitDisable(); }}
            />
            {disableError && <p className="text-xs text-red-600 font-tajawal">{disableError}</p>}
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={closeDisableDialog} disabled={disableBusy}>
              {lang === 'ar' ? 'إلغاء' : 'Cancel'}
            </Button>
            <Button
              onClick={submitDisable}
              disabled={disableBusy}
              className="bg-red-600 hover:bg-red-700 text-white gap-2"
              data-testid="mfa-disable-confirm-btn"
            >
              {disableBusy && <Loader2 className="h-4 w-4 animate-spin" />}
              <ShieldOff className="h-4 w-4" />
              {lang === 'ar' ? 'إلغاء التفعيل' : 'Disable MFA'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
