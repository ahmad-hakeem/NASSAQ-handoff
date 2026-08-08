import React, { useEffect, useState } from 'react';
import { useAuth } from '@/shared/contexts/AuthContext';
import { useTheme, useTranslation } from '@/shared/contexts/ThemeContext';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/shared/components/ui/dialog';
import { Button } from '@/shared/components/ui/button';
import { LoadingState } from '@/shared/components/ui/LoadingState';
import { Mail, Phone, MapPin, Globe, MessageCircle, AlertCircle, RefreshCw } from 'lucide-react';

let _cache = null;
let _cacheAt = 0;
const TTL_MS = 2 * 60 * 1000;

const Item = ({ icon: Icon, label, value, href, dir }) => {
  if (!value) return null;
  const inner = (
    <div className="flex items-center gap-3 p-3 rounded-xl border border-border/60 hover:bg-muted/40 transition-colors">
      <span className="w-9 h-9 rounded-xl bg-brand-turquoise/10 flex items-center justify-center shrink-0">
        <Icon className="h-4 w-4 text-brand-turquoise" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[11px] text-muted-foreground font-cairo">{label}</p>
        <p
          className="text-sm font-medium text-foreground truncate font-cairo"
          dir={dir || undefined}
        >
          {value}
        </p>
      </div>
    </div>
  );
  return href ? (
    <a href={href} target="_blank" rel="noopener noreferrer" className="block">
      {inner}
    </a>
  ) : (
    inner
  );
};

const ContactInfoDialog = ({ open, onOpenChange }) => {
  const { api } = useAuth();
  const { t } = useTranslation();
  const { isRTL } = useTheme();
  const [info, setInfo] = useState(_cache);
  const [loading, setLoading] = useState(!_cache);
  const [error, setError] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!open) return;
    const fresh = _cache && Date.now() - _cacheAt < TTL_MS;
    if (fresh && reloadKey === 0) {
      setInfo(_cache);
      setError(false);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(false);
    api.get('/public/contact-info')
      .then((res) => {
        if (cancelled) return;
        const data = res?.data || null;
        if (data && (data.primary_email || data.primary_phone || data.address || data.website || data.support_email)) {
          _cache = data;
          _cacheAt = Date.now();
          setInfo(data);
        } else {
          setInfo(null);
          setError(true);
        }
      })
      .catch(() => {
        if (cancelled) return;
        setInfo(null);
        setError(true);
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [open, api, reloadKey]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" dir={isRTL ? 'rtl' : 'ltr'} data-testid="contact-info-dialog">
        <DialogHeader>
          <DialogTitle className="font-cairo flex items-center gap-2">
            <MessageCircle className="h-5 w-5 text-brand-turquoise" />
            {t('contactUs') || 'Contact Us'}
          </DialogTitle>
        </DialogHeader>

        {loading ? (
          <LoadingState variant="section" />
        ) : error || !info ? (
          <div className="py-8 text-center space-y-3" data-testid="contact-info-error">
            <AlertCircle className="h-10 w-10 mx-auto text-muted-foreground/50" />
            <p className="text-sm text-muted-foreground font-cairo">
              {t('contactInfoUnavailable')
                || (isRTL ? 'تعذر تحميل معلومات التواصل حالياً' : 'Contact information is unavailable right now')}
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setReloadKey((k) => k + 1)}
              data-testid="contact-info-retry"
            >
              <RefreshCw className="h-3.5 w-3.5 me-1.5" />
              {t('retry') || (isRTL ? 'إعادة المحاولة' : 'Retry')}
            </Button>
          </div>
        ) : (
          <div className="space-y-2 py-2">
            <Item
              icon={Mail}
              label={t('primaryEmail') || 'Email'}
              value={info?.primary_email}
              href={info?.primary_email ? `mailto:${info.primary_email}` : undefined}
              dir="ltr"
            />
            {info?.support_email && info.support_email !== info.primary_email && (
              <Item
                icon={Mail}
                label={t('supportEmail') || 'Support Email'}
                value={info.support_email}
                href={`mailto:${info.support_email}`}
                dir="ltr"
              />
            )}
            <Item
              icon={Phone}
              label={t('primaryPhone') || 'Phone'}
              value={info?.primary_phone}
              href={info?.primary_phone ? `tel:${String(info.primary_phone).replace(/\s+/g, '')}` : undefined}
              dir="ltr"
            />
            <Item
              icon={MapPin}
              label={t('address') || 'Address'}
              value={info?.address}
            />
            {info?.website && (
              <Item
                icon={Globe}
                label={t('website') || 'Website'}
                value={String(info.website).replace(/^https?:\/\//, '')}
                href={info.website.startsWith('http') ? info.website : `https://${info.website}`}
                dir="ltr"
              />
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default ContactInfoDialog;
