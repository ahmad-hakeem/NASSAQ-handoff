import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { useAuth } from '../contexts/AuthContext';
import { useTheme, useTranslation } from '../contexts/ThemeContext';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import {
  canOpenPrincipalDashboard,
  getPreviewBlockMessage,
} from '../utils/platformAdminPreview';

/**
 * Shared handler for Platform Admin "Open Dashboard" / principal preview.
 */
export function usePlatformAdminSchoolPreview() {
  const { enterSchoolContext } = useAuth();
  const navigate = useNavigate();
  const { isRTL } = useTheme();
  const { t } = useTranslation();
  const { nassaqError, nassaqWarning } = useNassaqAlert();

  const openPrincipalDashboard = useCallback(
    async (school, opts = {}) => {
      if (!school?.id) {
        nassaqError(t('errorInvalidSchoolData'));
        return false;
      }

      if (!canOpenPrincipalDashboard(school)) {
        const msg = getPreviewBlockMessage(school, { isRTL });
        nassaqWarning(msg);
        return false;
      }

      try {
        await enterSchoolContext(school, opts);
      } catch (err) {
        const detail = err?.response?.data?.detail;
        if (typeof detail === 'string' && detail.trim()) {
          nassaqError(detail);
        } else {
          nassaqError(t('errorSwitchingRole'));
        }
        return false;
      }

      if (opts.showSuccessToast !== false) {
        toast.success(
          isRTL
            ? `تم الدخول إلى ${school.name} كمدير مدرسة`
            : `Entered ${school.name_en || school.name} as School Manager`,
        );
      }

      if (opts.navigateToPrincipal !== false) {
        navigate(opts.redirectTo || '/principal');
      }
      return true;
    },
    [enterSchoolContext, isRTL, navigate, nassaqError, nassaqWarning, t],
  );

  return { openPrincipalDashboard, canOpenPrincipalDashboard };
}
