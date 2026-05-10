import React, { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { useNassaqAlert } from '../ui/NassaqAlertDialog';
import { toast } from 'sonner';
import { Loader2, Lock, Eye, EyeOff, Check, X } from 'lucide-react';

const PasswordStrength = ({ password, isRTL, t }) => {
  const checks = [
    { test: password.length >= 8, label: t('atLeast8Characters') || 'At least 8 characters' },
    { test: /[A-Z]/.test(password), label: t('uppercaseLetter') || 'Uppercase letter' },
    { test: /[a-z]/.test(password), label: t('lowercaseLetter') || 'Lowercase letter' },
    { test: /[0-9]/.test(password), label: t('number') || 'Number' },
    { test: /[^A-Za-z0-9]/.test(password), label: t('specialCharacter') || 'Special character' },
  ];
  const passed = checks.filter((c) => c.test).length;
  const strength = passed === 0 ? 0 : passed <= 2 ? 1 : passed <= 3 ? 2 : passed <= 4 ? 3 : 4;
  const labels = isRTL
    ? ['', 'ضعيفة', 'مقبولة', 'جيدة', 'قوية جداً']
    : ['', 'Weak', 'Fair', 'Good', 'Very Strong'];
  const colors = ['', 'bg-red-500', 'bg-amber-500', 'bg-blue-500', 'bg-emerald-500'];
  if (!password) return null;
  return (
    <div className="space-y-2 mt-2">
      <div className="flex gap-1.5">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className={`h-1.5 flex-1 rounded-full transition-all ${i <= strength ? colors[strength] : 'bg-muted/30'}`}
          />
        ))}
      </div>
      <span className={`text-xs font-cairo ${strength >= 3 ? 'text-emerald-600' : strength >= 2 ? 'text-amber-600' : 'text-red-600'}`}>
        {labels[strength]}
      </span>
      <div className="grid grid-cols-2 gap-1">
        {checks.map((c, i) => (
          <div key={i} className="flex items-center gap-1.5">
            {c.test ? <Check className="h-3 w-3 text-emerald-500" /> : <X className="h-3 w-3 text-muted-foreground/40" />}
            <span className={`text-[10px] ${c.test ? 'text-emerald-600' : 'text-muted-foreground/50'}`}>{c.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

const PasswordChangeDialog = ({ open, onOpenChange }) => {
  const { user, api } = useAuth();
  const { isRTL } = useTheme();
  const { t } = useTranslation();
  const { nassaqError } = useNassaqAlert();

  const [form, setForm] = useState({ current_password: '', new_password: '', confirm_password: '' });
  const [show, setShow] = useState({ current: false, new: false, confirm: false });
  const [saving, setSaving] = useState(false);

  const reset = () => {
    setForm({ current_password: '', new_password: '', confirm_password: '' });
    setShow({ current: false, new: false, confirm: false });
  };

  const handleClose = () => { reset(); onOpenChange?.(false); };

  const submit = async () => {
    if (form.new_password !== form.confirm_password) {
      nassaqError(t('passwordsDoNotMatch') || 'Passwords do not match');
      return;
    }
    if (form.new_password.length < 8) {
      nassaqError(t('passwordMustBeAtLeast8Characters2') || t('passwordMustBeAtLeast8Characters') || 'Password must be at least 8 characters');
      return;
    }
    setSaving(true);
    try {
      await api.put(`/users/${user?.id}/password`, {
        current_password: form.current_password,
        new_password: form.new_password,
      });
      toast.success(t('passwordChangedSuccessfully') || 'Password changed');
      handleClose();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      nassaqError(typeof detail === 'string' ? detail : (t('errorChangingPassword') || 'Error changing password'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) reset(); onOpenChange?.(v); }}>
      <DialogContent className="sm:max-w-md" dir={isRTL ? 'rtl' : 'ltr'} data-testid="parent-password-dialog">
        <DialogHeader>
          <DialogTitle className="font-cairo flex items-center gap-2">
            <Lock className="h-5 w-5 text-brand-turquoise" />
            {t('changePassword') || 'Change password'}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label className="font-cairo">{t('currentPassword') || 'Current password'}</Label>
            <div className="relative">
              <Input
                type={show.current ? 'text' : 'password'}
                value={form.current_password}
                onChange={(e) => setForm({ ...form, current_password: e.target.value })}
                dir="ltr"
                className="pe-10"
                data-testid="parent-password-current-input"
              />
              <button
                type="button"
                onClick={() => setShow({ ...show, current: !show.current })}
                className="absolute end-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {show.current ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <div className="space-y-2">
            <Label className="font-cairo">{t('newPassword') || 'New password'}</Label>
            <div className="relative">
              <Input
                type={show.new ? 'text' : 'password'}
                value={form.new_password}
                onChange={(e) => setForm({ ...form, new_password: e.target.value })}
                dir="ltr"
                className="pe-10"
                data-testid="parent-password-new-input"
              />
              <button
                type="button"
                onClick={() => setShow({ ...show, new: !show.new })}
                className="absolute end-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {show.new ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <PasswordStrength password={form.new_password} isRTL={isRTL} t={t} />
          </div>

          <div className="space-y-2">
            <Label className="font-cairo">{t('confirmNewPassword') || 'Confirm new password'}</Label>
            <div className="relative">
              <Input
                type={show.confirm ? 'text' : 'password'}
                value={form.confirm_password}
                onChange={(e) => setForm({ ...form, confirm_password: e.target.value })}
                dir="ltr"
                className="pe-10"
                data-testid="parent-password-confirm-input"
              />
              <button
                type="button"
                onClick={() => setShow({ ...show, confirm: !show.confirm })}
                className="absolute end-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {show.confirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            {form.confirm_password && form.new_password !== form.confirm_password && (
              <p className="text-xs text-red-500 font-cairo flex items-center gap-1">
                <X className="h-3 w-3" />{t('passwordsDoNotMatch') || 'Passwords do not match'}
              </p>
            )}
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={handleClose} disabled={saving}>
            {t('cancel') || 'Cancel'}
          </Button>
          <Button
            onClick={submit}
            disabled={
              saving ||
              !form.current_password ||
              !form.new_password ||
              form.new_password !== form.confirm_password
            }
            className="bg-brand-turquoise hover:bg-brand-turquoise/90"
            data-testid="parent-password-submit-btn"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Lock className="h-4 w-4 me-2" />}
            {t('changePassword') || 'Change password'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default PasswordChangeDialog;
