import { useEffect, useState } from 'react';
import { Eye, RefreshCw } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import { Input } from '../../ui/input';
import { Button } from '../../ui/button';
import { useTheme, useTranslation } from '../../../contexts/ThemeContext';

export default function PreviewReasonDialog({ role, submitting, onConfirm, onCancel }) {
  const { isRTL } = useTheme();
  const { t } = useTranslation();
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (role) {
      setReason('');
      setError('');
    }
  }, [role]);

  const handleConfirm = () => {
    const trimmed = (reason || '').trim();
    if (trimmed.length < 4) {
      setError(t('previewReasonTooShort'));
      return;
    }
    if (trimmed.length > 500) {
      setError(t('previewReasonTooLong'));
      return;
    }
    onConfirm(trimmed);
  };

  return (
    <Dialog
      open={!!role}
      onOpenChange={(open) => { if (!open && !submitting) onCancel(); }}
    >
      <DialogContent className="max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Eye className="h-5 w-5 text-brand-turquoise" />
            {t('previewAsPrincipalTitle')}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            {role?.tenant_name
              ? t('previewAsPrincipalDescWithSchool').replace('{school}', role.tenant_name)
              : t('previewAsPrincipalDesc')}
          </p>
          <label className="text-sm font-medium block" htmlFor="preview-reason-input">
            {t('previewReasonLabel')}
          </label>
          <Input
            id="preview-reason-input"
            dir="rtl"
            value={reason}
            onChange={(e) => {
              setReason(e.target.value);
              if (error) setError('');
            }}
            placeholder={t('previewReasonPlaceholder')}
            maxLength={500}
            disabled={submitting}
            data-testid="preview-reason-input"
            autoFocus
            className="text-start ps-4 placeholder:text-slate-400 focus:placeholder:opacity-0 placeholder:transition-opacity placeholder:duration-200"
          />
          {error && (
            <p className="text-xs text-red-600" role="alert">
              {error}
            </p>
          )}
        </div>
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="outline" onClick={onCancel} disabled={submitting}>
            {t('cancel')}
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={submitting}
            className="bg-brand-turquoise hover:bg-brand-turquoise/90 text-white"
            data-testid="preview-reason-confirm"
          >
            {submitting && <RefreshCw className="h-4 w-4 me-2 animate-spin" />}
            {t('previewAsPrincipalConfirm')}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
