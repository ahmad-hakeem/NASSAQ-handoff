import { useAuth } from '../contexts/AuthContext';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { Sidebar } from '../components/layout/Sidebar';
import { NotificationBell } from '../components/notifications/NotificationBell';
import { SchoolDashboardContent } from '../components/dashboard/SchoolDashboardContent';
import { Button } from '../components/ui/button';
import {
  Sun,
  Moon,
  Globe,
  Command,
} from 'lucide-react';

export default function PrincipalDashboard() {
  const { user, schoolContext, isImpersonating } = useAuth();
  const { t } = useTranslation();
  const { toggleTheme, toggleLanguage, isDark } = useTheme();

  return (
    <Sidebar>
      <div className="min-h-screen" data-testid="principal-dashboard">
        <header className="sticky top-0 z-30 bg-background/80 backdrop-blur-xl border-b border-border/40 px-4 sm:px-6 py-3 sm:py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3 sm:gap-4 min-w-0">
              <div className="w-9 h-9 sm:w-11 sm:h-11 rounded-xl bg-gradient-to-br from-brand-navy to-brand-turquoise flex items-center justify-center shadow-lg shadow-brand-navy/20 flex-shrink-0">
                <Command className="h-4 w-4 sm:h-5 sm:w-5 text-white" />
              </div>
              <div className="min-w-0">
                <h1 className="font-cairo text-lg sm:text-xl font-bold text-foreground truncate">
                  {t('commandCenter')}
                </h1>
                <p className="text-xs sm:text-sm text-muted-foreground font-tajawal truncate">
                  {isImpersonating && schoolContext
                    ? t('previewingSchool', { name: schoolContext.school_name })
                    : (user?.title && user?.title !== 'none'
                        ? t('welcomeUserWithTitle', { title: user.title, name: user?.full_name || '' })
                        : t('welcomeUser', { name: user?.full_name || '' }))
                  }
                </p>
              </div>
            </div>
            
            <div className="flex items-center gap-1 sm:gap-2 flex-shrink-0">
              <Button variant="ghost" size="icon" onClick={toggleLanguage} className="rounded-xl h-9 w-9" data-testid="language-toggle">
                <Globe className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme} className="rounded-xl h-9 w-9" data-testid="theme-toggle">
                {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </Button>
              <NotificationBell />
            </div>
          </div>
        </header>

        <div className="p-4 sm:p-6">
          <SchoolDashboardContent />
        </div>
      </div>
    </Sidebar>
  );
}
