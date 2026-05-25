import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Eye, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';
import { useNassaqAlert } from '../ui/NassaqAlertDialog';
import { Button } from '../ui/button';

/**
 * Task #528 — Persistent preview-mode banner.
 * Task #576 — Consolidated: this is now the ONLY preview-mode banner
 * (the duplicate orange/amber banner on PrincipalDashboard was removed).
 *
 * Visible across navigation whenever the Platform Admin is impersonating
 * a school (Preview Mode). The exit button calls the same hardened
 * `/user-roles/return-to-original` flow used by the dialog button —
 * both go through `returnToOriginalRole()` on AuthContext so there is a
 * single source of truth for the restore network call and token swap.
 */
export default function PreviewModeBanner() {
  const { isImpersonating, schoolContext, returnToOriginalRole } = useAuth();
  const { isRTL, language } = useTheme();
  const { t } = useTranslation();
  const { nassaqError } = useNassaqAlert();
  const navigate = useNavigate();
  const [exiting, setExiting] = useState(false);

  const handleExit = useCallback(async () => {
    if (exiting) return;
    setExiting(true);
    try {
      const result = await returnToOriginalRole();
      if (result?.success) {
        toast.success(result.message || t('returnedToOriginalRole'));
        navigate(result.redirectTo);
      }
    } catch (error) {
      console.error('Error exiting preview mode:', error);
      nassaqError(t('errorReturningToOriginalRole'));
    } finally {
      setExiting(false);
    }
  }, [exiting, navigate, nassaqError, returnToOriginalRole, t]);

  if (!isImpersonating) return null;

  const schoolName = schoolContext
    ? (language === 'en'
        ? (schoolContext.school_name_en || schoolContext.school_name)
        : (schoolContext.school_name || schoolContext.school_name_en))
    : null;

  return (
    <div
      dir={isRTL ? 'rtl' : 'ltr'}
      data-testid="preview-mode-banner"
      className="sticky top-0 z-[120] w-full bg-brand-navy text-white border-b border-brand-turquoise/40 shadow-md"
    >
      <div className="max-w-7xl mx-auto px-3 sm:px-4 py-2 sm:py-2.5 flex items-center gap-2 sm:gap-3 justify-between">
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          <span
            className="flex items-center justify-center h-8 w-8 sm:h-9 sm:w-9 rounded-lg bg-brand-turquoise/20 text-brand-turquoise shrink-0"
            aria-hidden="true"
          >
            <Eye className="h-4 w-4 sm:h-5 sm:w-5" strokeWidth={1.5} />
          </span>
          <div className="flex flex-col sm:flex-row sm:items-baseline sm:gap-3 min-w-0 text-start">
            <span className="inline-flex items-center rounded-md bg-brand-turquoise/20 text-brand-turquoise px-2 py-0.5 text-[11px] sm:text-xs font-bold uppercase tracking-wide w-fit">
              {t('previewMode')}
            </span>
            {schoolName ? (
              <span className="font-cairo text-sm sm:text-base font-bold text-white truncate">
                {schoolName}
              </span>
            ) : (
              <span className="text-xs sm:text-sm text-white/80 truncate">
                {t('previewModeBannerHelper')}
              </span>
            )}
          </div>
        </div>
        <Button
          onClick={handleExit}
          disabled={exiting}
          size="sm"
          data-testid="preview-mode-banner-exit-btn"
          className="bg-brand-turquoise hover:bg-brand-turquoise-light text-white rounded-lg font-bold shadow-md shrink-0 min-h-[36px] px-3 sm:px-4"
        >
          {exiting ? (
            <RefreshCw className="h-4 w-4 me-1.5 sm:me-2 animate-spin" strokeWidth={1.5} aria-hidden="true" />
          ) : (
            <ArrowLeft
              className={`h-4 w-4 me-1.5 sm:me-2 ${isRTL ? 'rotate-180' : ''}`}
              strokeWidth={1.5}
              aria-hidden="true"
            />
          )}
          <span className="hidden sm:inline">{t('backToPlatform')}</span>
          <span className="sm:hidden">{t('back3')}</span>
        </Button>
      </div>
    </div>
  );
}
