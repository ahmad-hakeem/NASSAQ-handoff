import { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../../../contexts/AuthContext';
import { useTranslation } from '../../../contexts/ThemeContext';
import { Button } from '../../ui/button';
import { Sparkles, X } from 'lucide-react';
import OnboardingTour from './OnboardingTour';

export default function OnboardingTrigger() {
  const { user, api } = useAuth();
  const { t } = useTranslation();
  const isIT = (user?.role || '').toLowerCase() === 'independent_teacher';
  const [shouldShow, setShouldShow] = useState(false);
  const [welcomeOpen, setWelcomeOpen] = useState(false);
  const [tourOpen, setTourOpen] = useState(false);
  const [completing, setCompleting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (!isIT || !api) return undefined;
    (async () => {
      try {
        const { data } = await api.get('/independent-teacher/onboarding/state');
        if (cancelled) return;
        if (data?.should_show) {
          setShouldShow(true);
          setWelcomeOpen(true);
        }
      } catch (e) { /* silent — never block dashboard on tour state */ }
    })();
    return () => { cancelled = true; };
  }, [isIT, api]);

  const stamp = useCallback(async () => {
    if (completing) return;
    setCompleting(true);
    try {
      await api.post('/independent-teacher/onboarding/complete');
    } catch (e) { /* silent — UI dismisses regardless */ }
    finally {
      setCompleting(false);
      setShouldShow(false);
    }
  }, [api, completing]);

  const handleStart = () => { setWelcomeOpen(false); setTourOpen(true); };
  const handleSkip = async () => { setWelcomeOpen(false); setTourOpen(false); await stamp(); };
  const handleFinish = async () => { setTourOpen(false); await stamp(); };

  if (!isIT || !shouldShow) return null;

  return (
    <>
      {welcomeOpen && (
        <div
          className="fixed inset-0 z-[9998] bg-slate-950/55 flex items-center justify-center p-4"
          data-testid="it-onboarding-welcome"
        >
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl border border-border max-w-md w-full p-6 relative">
            <button
              type="button"
              className="absolute top-3 end-3 text-muted-foreground hover:text-foreground p-1 rounded"
              onClick={handleSkip}
              aria-label={t('itTourSkip')}
            >
              <X className="h-4 w-4" />
            </button>
            <div className="w-12 h-12 rounded-2xl bg-brand-turquoise/15 flex items-center justify-center mb-3">
              <Sparkles className="h-6 w-6 text-brand-turquoise" />
            </div>
            <h2 className="font-cairo font-bold text-xl text-foreground mb-1">
              {t('itTourWelcomeTitle')}
            </h2>
            <p className="text-sm text-muted-foreground font-tajawal leading-relaxed mb-5">
              {t('itTourWelcomeBody')}
            </p>
            <div className="flex items-center justify-end gap-2">
              <Button
                variant="ghost"
                onClick={handleSkip}
                className="rounded-xl font-tajawal"
                data-testid="it-onboarding-welcome-skip"
              >
                {t('itTourSkip')}
              </Button>
              <Button
                onClick={handleStart}
                className="rounded-xl bg-brand-turquoise hover:bg-brand-turquoise/90 text-white font-tajawal gap-2"
                data-testid="it-onboarding-welcome-start"
              >
                <Sparkles className="h-4 w-4" />
                {t('itTourStart')}
              </Button>
            </div>
          </div>
        </div>
      )}

      <OnboardingTour open={tourOpen} onFinish={handleFinish} onSkip={handleSkip} />
    </>
  );
}
