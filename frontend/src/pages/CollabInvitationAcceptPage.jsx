/**
 * Workspace-collaborator accept landing — Task #210 (IT §6.7).
 *
 * Authenticated route. The page reads `?token=…` from the URL, posts it
 * to `/independent-teacher/workspace-collaborators/accept` (which
 * requires fresh MFA + IT role), and on success navigates back to the
 * teacher's classes overview where the newly-shared class will appear
 * tagged "متعاون مع <host>".
 *
 * All failure modes surface through NassaqAlertDialog.
 */
import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Loader2, CheckCircle2, AlertCircle } from 'lucide-react';

import { useAuth } from '../contexts/AuthContext';
import { useTranslation } from '../contexts/ThemeContext';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import { Button } from '../components/ui/button';
import { getApiErrorMessage } from '../utils/apiError';

export default function CollabInvitationAcceptPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { api, user, isAuthenticated } = useAuth();
  const { t, isRTL } = useTranslation();
  const { warn, error } = useNassaqAlert();

  const [phase, setPhase] = useState('working'); // working | done | failed
  const onceRef = useRef(false);

  useEffect(() => {
    if (onceRef.current) return;
    const token = (params.get('token') || '').trim();
    if (!token) {
      setPhase('failed');
      warn({ title: t('collabAcceptError'), description: t('collabAcceptInvalid') });
      return;
    }
    if (!isAuthenticated || !user) {
      // Defer: send to sign-in with a return URL. AuthContext will replay.
      const returnTo = encodeURIComponent(`/teacher/collab-accept?token=${encodeURIComponent(token)}`);
      navigate(`/login?redirect=${returnTo}`, { replace: true });
      return;
    }
    onceRef.current = true;
    (async () => {
      try {
        await api.post('/independent-teacher/workspace-collaborators/accept', { token });
        setPhase('done');
      } catch (err) {
        const status = err?.response?.status;
        const detail = err?.response?.data?.detail ?? getApiErrorMessage(err);
        setPhase('failed');
        if (status === 403) {
          // Either MFA step-up envelope (axios interceptor will replay) or
          // an authorization mismatch we surface verbatim.
          const code = detail && typeof detail === 'object' ? detail.code : null;
          if (code && (code === 'MFA_STEPUP_REQUIRED' || code === 'MFA_PASSKEY_REQUIRED' || code === 'MFA_RESTORE_REQUIRED')) {
            // The interceptor handles step-up; the user will be redirected
            // back here after the passkey assertion completes.
            return;
          }
          error({ title: t('collabAcceptError'), description: detail || t('collabAcceptForbidden') });
          return;
        }
        const fallback = status === 400 ? t('collabAcceptInvalid') : t('collabAcceptGeneric');
        error({ title: t('collabAcceptError'), description: typeof detail === 'string' ? detail : fallback });
      }
    })();
  }, [api, error, isAuthenticated, navigate, params, t, user, warn]);

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-gray-50 dark:bg-gray-900" dir={isRTL ? 'rtl' : 'ltr'}>
      <div className="max-w-md w-full text-center space-y-4 bg-white dark:bg-gray-800 rounded-2xl p-8 shadow-lg border border-border">
        {phase === 'working' && (
          <>
            <Loader2 className="h-10 w-10 animate-spin text-brand-turquoise mx-auto" />
            <h1 className="text-xl font-bold font-cairo">{t('collabAcceptWorkingTitle')}</h1>
            <p className="text-sm text-muted-foreground">{t('collabAcceptWorkingBody')}</p>
          </>
        )}
        {phase === 'done' && (
          <>
            <CheckCircle2 className="h-12 w-12 text-emerald-500 mx-auto" />
            <h1 className="text-xl font-bold font-cairo">{t('collabAcceptDoneTitle')}</h1>
            <p className="text-sm text-muted-foreground">{t('collabAcceptDoneBody')}</p>
            <Button onClick={() => navigate('/teacher/classes', { replace: true })}>
              {t('collabGoToClasses')}
            </Button>
          </>
        )}
        {phase === 'failed' && (
          <>
            <AlertCircle className="h-12 w-12 text-rose-500 mx-auto" />
            <h1 className="text-xl font-bold font-cairo">{t('collabAcceptError')}</h1>
            <p className="text-sm text-muted-foreground">{t('collabAcceptGeneric')}</p>
            <Button variant="outline" onClick={() => navigate('/teacher/classes', { replace: true })}>
              {t('collabGoToClasses')}
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
