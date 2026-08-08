import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useNassaqAlert } from '@/shared/components/ui/NassaqAlertDialog';
import { useTranslation } from '@/shared/contexts/ThemeContext';
import {
  registerPerimeterGateHandler,
  resetBootstrapDialogGuard,
} from '@/shared/services/perimeterGateBridge';
import { PERIMETER_FINISH_SETUP_ROUTE } from '@/shared/models/constants/auth';

// Routes that are public-by-design (landing, login, register, password
// reset, public invitation accept). The perimeter "finish setup" dialog
// must NEVER fire on these surfaces — even with a stale IT bearer in
// localStorage — otherwise a guest CTA click looks like an onboarding
// recovery prompt. Authoritative onboarding redirect happens AFTER login.
const PUBLIC_ROUTE_PREFIXES = [
  '/login',
  '/register',
  '/forgot-password',
  '/reset-password',
  '/registration-confirmation',
  '/parent-invitations/accept',
  '/teacher/collab-accept',
  '/workspace-collaborators/accept',
];

const isPublicPath = (pathname) => {
  if (!pathname || pathname === '/') return true;
  return PUBLIC_ROUTE_PREFIXES.some((p) => pathname === p || pathname.startsWith(p + '/'));
};

export default function PerimeterGateBridge() {
  const navigate = useNavigate();
  const { nassaqInfo } = useNassaqAlert();
  const { t } = useTranslation();

  useEffect(() => {
    const unregister = registerPerimeterGateHandler(() => {
      // Defense in depth: even if a stray 409 leaks through (e.g. a stale
      // IT bearer hits a not-yet-allowlisted route), do NOT pop the
      // onboarding dialog while the user is on a public surface.
      if (isPublicPath(window.location.pathname)) {
        return;
      }
      nassaqInfo(t('itPerimeterFinishSetupBody'), {
        title: t('itPerimeterFinishSetupTitle'),
        confirmText: t('itPerimeterFinishSetupCta'),
        onConfirm: () => {
          resetBootstrapDialogGuard();
          navigate(PERIMETER_FINISH_SETUP_ROUTE);
        },
      });
      try {
        navigate(PERIMETER_FINISH_SETUP_ROUTE);
      } catch {
        // navigation is best-effort; the dialog Confirm handler retries
      }
    });
    return unregister;
  }, [navigate, nassaqInfo, t]);

  return null;
}
