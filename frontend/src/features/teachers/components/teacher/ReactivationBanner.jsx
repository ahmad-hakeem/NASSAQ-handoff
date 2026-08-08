import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/shared/contexts/AuthContext';
import { useTranslation } from '@/shared/contexts/ThemeContext';
import { formatHijriDate } from '@/shared/models/utils/hijriDate';
import { Button } from '@/shared/components/ui/button';
import { CheckCircle2, X, ArrowRight } from 'lucide-react';

/**
 * Task #222 — IT post-login reactivation banner.
 *
 * Renders ONLY for `independent_teacher` users whose lifecycle row
 * carries a `reactivation_banner` block (server gate: caller has
 * reactivated since their last dismissal). Dismiss POSTs to the
 * dedicated dismiss endpoint and removes the banner locally so the
 * card disappears without a refresh.
 *
 * Safe to mount on every dashboard: when the gate is closed the
 * single GET resolves to `reactivation_banner === null` and the
 * component renders nothing.
 */
export default function ReactivationBanner() {
  const { t } = useTranslation();
  const { user, api, consumeInitialWorkspaceLifecycle } = useAuth();
  const navigate = useNavigate();
  const isIndependentTeacher = (user?.role || '').toLowerCase() === 'independent_teacher';

  // Task #231 — seed initial state from the post-login lifecycle snapshot
  // embedded in the /auth/login (and /auth/mfa/verify) response. The
  // dashboard renders the banner in the same paint as the rest of the
  // page; the follow-up GET below is only needed when the banner mounts
  // outside the post-login flow (e.g. a hard refresh).
  const [initial] = useState(() => {
    if (!isIndependentTeacher || typeof consumeInitialWorkspaceLifecycle !== 'function') {
      return { banner: null, consumed: false };
    }
    const { snapshot, consumed } = consumeInitialWorkspaceLifecycle();
    return { banner: snapshot?.reactivation_banner || null, consumed };
  });
  const [banner, setBanner] = useState(initial.banner);
  const [dismissing, setDismissing] = useState(false);

  useEffect(() => {
    // If the post-login flow already delivered a snapshot, skip the
    // follow-up GET — the embedded payload is the freshest data we
    // can possibly have. This includes the "snapshot present but
    // reactivation_banner === null" case, where re-fetching would
    // only generate a redundant request.
    if (!api || !isIndependentTeacher || initial.consumed) return;
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get('/independent-teacher/workspace/lifecycle');
        if (!cancelled && data?.reactivation_banner) {
          setBanner(data.reactivation_banner);
        }
      } catch (_e) {
        /* non-fatal — silently skip the banner */
      }
    })();
    return () => { cancelled = true; };
  }, [api, isIndependentTeacher, initial.consumed]);

  const handleDismiss = useCallback(async () => {
    if (dismissing) return;
    setDismissing(true);
    setBanner(null);
    try {
      await api.post('/independent-teacher/workspace/lifecycle/reactivation-banner/dismiss');
    } catch (_e) {
      /* server-side will re-arm if persistence failed; UI already hidden */
    } finally {
      setDismissing(false);
    }
  }, [api, dismissing]);

  if (!isIndependentTeacher || !banner) return null;

  const archivedDate = banner.archived_at ? new Date(banner.archived_at) : null;
  const wouldDeleteDate = banner.would_have_been_deleted_at
    ? new Date(banner.would_have_been_deleted_at)
    : null;
  const archivedFmt = archivedDate ? formatHijriDate(archivedDate) : null;
  const wouldDeleteFmt = wouldDeleteDate ? formatHijriDate(wouldDeleteDate) : null;
  const daysLeft = banner.days_remaining_at_reactivation;

  return (
    <div
      role="status"
      data-testid="it-reactivation-banner"
      className="relative rounded-2xl border border-emerald-500/30 bg-gradient-to-r from-emerald-500/10 via-emerald-400/5 to-brand-turquoise/10 p-4 mb-4 shadow-sm"
    >
      <button
        type="button"
        aria-label={t('itReactivationBannerDismiss')}
        onClick={handleDismiss}
        className="absolute top-3 end-3 p-1 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/40 transition-colors"
      >
        <X className="h-4 w-4" />
      </button>
      <div className="flex items-start gap-3 pe-8">
        <div className="h-10 w-10 rounded-xl bg-emerald-500/15 flex items-center justify-center flex-shrink-0">
          <CheckCircle2 className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-cairo font-bold text-sm text-foreground">
            {t('itReactivationBannerTitle')}
          </h3>
          <div className="mt-1 space-y-1 text-xs font-tajawal text-muted-foreground">
            {archivedFmt ? (
              <p>
                {t('itReactivationBannerArchivedOn').replace('{{date}}', archivedFmt)}
              </p>
            ) : (
              <p>{t('itReactivationBannerNoCycle')}</p>
            )}
            {wouldDeleteFmt && daysLeft != null && (
              <p>
                {t('itReactivationBannerWindow')
                  .replace('{{date}}', wouldDeleteFmt)
                  .replace('{{days}}', String(daysLeft))}
              </p>
            )}
          </div>
          <div className="mt-3">
            <Button
              size="sm"
              variant="outline"
              onClick={() => navigate('/account/settings#workspace')}
              className="rounded-xl gap-1.5 text-xs"
            >
              {t('itReactivationBannerCta')}
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
