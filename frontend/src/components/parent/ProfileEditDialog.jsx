import React, { useEffect, useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { useNassaqAlert } from '../ui/NassaqAlertDialog';
import { toast } from 'sonner';
import { Loader2, Save, User, Mail, Phone } from 'lucide-react';
import { getApiErrorMessage } from '../../utils/apiError';

const ProfileEditDialog = ({ open, onOpenChange, onSaved }) => {
  const { user, api, refreshUser } = useAuth();
  const { isRTL } = useTheme();
  const { t } = useTranslation();
  const { nassaqError } = useNassaqAlert();

  const [form, setForm] = useState({ full_name: '', email: '', phone: '' });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setForm({
        full_name: user?.full_name || '',
        email: user?.email || '',
        phone: user?.phone || '',
      });
    }
  }, [open, user]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = {};
      if (form.full_name && form.full_name !== user?.full_name) payload.full_name = form.full_name;
      if (form.email !== (user?.email || '')) payload.email = form.email || undefined;
      if (form.phone !== (user?.phone || '')) payload.phone = form.phone || undefined;

      if (Object.keys(payload).length === 0) {
        onOpenChange?.(false);
        return;
      }

      const res = await api.put('/users/me/profile', payload);
      await refreshUser?.();
      toast.success(t('profileSavedSuccessfully') || 'Profile saved');
      onSaved?.(res?.data?.user);
      onOpenChange?.(false);
    } catch (err) {
      const detail = getApiErrorMessage(err);
      nassaqError(typeof detail === 'string' ? detail : (t('errorSavingProfile') || 'Error saving profile'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" dir={isRTL ? 'rtl' : 'ltr'} data-testid="parent-profile-edit-dialog">
        <DialogHeader>
          <DialogTitle className="font-cairo flex items-center gap-2">
            <User className="h-5 w-5 text-brand-turquoise" />
            {t('editProfile') || 'Edit Profile'}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label className="font-cairo flex items-center gap-1.5 text-sm">
              <User className="h-3.5 w-3.5 text-muted-foreground" />
              {t('fullName') || 'Full name'}
            </Label>
            <Input
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              data-testid="parent-profile-fullname-input"
            />
          </div>
          <div className="space-y-2">
            <Label className="font-cairo flex items-center gap-1.5 text-sm">
              <Mail className="h-3.5 w-3.5 text-muted-foreground" />
              {t('email2') || t('email') || 'Email'}
            </Label>
            <Input
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              dir="ltr"
              data-testid="parent-profile-email-input"
            />
          </div>
          <div className="space-y-2">
            <Label className="font-cairo flex items-center gap-1.5 text-sm">
              <Phone className="h-3.5 w-3.5 text-muted-foreground" />
              {t('phoneNumber') || 'Phone number'}
            </Label>
            <Input
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              dir="ltr"
              placeholder="+966 5XX XXX XXXX"
              data-testid="parent-profile-phone-input"
            />
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onOpenChange?.(false)} disabled={saving}>
            {t('cancel') || 'Cancel'}
          </Button>
          <Button
            onClick={handleSave}
            disabled={saving || !form.full_name?.trim()}
            className="bg-brand-turquoise hover:bg-brand-turquoise/90"
            data-testid="parent-profile-save-btn"
          >
            {saving ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Save className="h-4 w-4 me-2" />}
            {t('saveChanges') || 'Save changes'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default ProfileEditDialog;
