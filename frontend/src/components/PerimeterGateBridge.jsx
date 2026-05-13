import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useNassaqAlert } from './ui/NassaqAlertDialog';
import { useTranslation } from '../contexts/ThemeContext';
import {
  registerPerimeterGateHandler,
  resetBootstrapDialogGuard,
} from '../services/perimeterGateBridge';
import { PERIMETER_FINISH_SETUP_ROUTE } from '../constants/auth';

export default function PerimeterGateBridge() {
  const navigate = useNavigate();
  const { nassaqInfo } = useNassaqAlert();
  const { t } = useTranslation();

  useEffect(() => {
    const unregister = registerPerimeterGateHandler(() => {
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
