import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { Sidebar } from '../components/layout/Sidebar';
import { HakimAssistant } from '../components/hakim/HakimAssistant';
import { NotificationBell } from '../components/notifications/NotificationBell';
import { SchoolDashboardContent } from '../components/dashboard/SchoolDashboardContent';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  Sun,
  Moon,
  Globe,
  ArrowLeft,
  Shield,
  Building2,
  X,
  Command,
} from 'lucide-react';

export default function PrincipalDashboard() {
  const navigate = useNavigate();
  const { user, schoolContext, isImpersonating, exitSchoolContext } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  const exitTimeoutRef = useRef(null);

  useEffect(() => {
    return () => {
      if (exitTimeoutRef.current) clearTimeout(exitTimeoutRef.current);
    };
  }, []);
  
  const handleExitImpersonation = () => {
  const { t } = useTranslation();
    exitSchoolContext();
    if (exitTimeoutRef.current) clearTimeout(exitTimeoutRef.current);
    exitTimeoutRef.current = setTimeout(() => {
      window.location.href = '/admin/tenants';
    }, 100);
  };

  return (
    <Sidebar>
      <div className="min-h-screen" data-testid="principal-dashboard">
        {isImpersonating && schoolContext && (
          <div 
            className="sticky top-0 z-50 bg-gradient-to-r from-amber-500 via-orange-500 to-amber-500 text-white px-3 sm:px-4 py-2 sm:py-3 flex items-center justify-between shadow-lg gap-2" 
            data-testid="impersonation-banner"
          >
            <div className="flex items-center gap-2 sm:gap-3 min-w-0">
              <div className="w-8 h-8 sm:w-10 sm:h-10 bg-white/20 rounded-xl flex items-center justify-center flex-shrink-0">
                <Shield className="h-4 w-4 sm:h-5 sm:w-5" />
              </div>
              <div className="flex flex-col min-w-0">
                <span className="font-bold text-xs sm:text-sm">
                  {t('youAreNowPreviewing')}
                </span>
                <span className="text-white/90 font-cairo text-sm sm:text-lg truncate">
                  {schoolContext.school_name}
                </span>
              </div>
            </div>
            <Button 
              size="sm" 
              className="bg-white text-amber-600 hover:bg-white/90 rounded-xl font-bold shadow-md flex-shrink-0 text-xs sm:text-sm"
              onClick={handleExitImpersonation}
              data-testid="exit-impersonation-btn"
            >
              <ArrowLeft className={`h-3.5 w-3.5 sm:h-4 sm:w-4 me-1 sm:me-2 ${isRTL ? 'rotate-180' : ''}`} />
              <span className="hidden sm:inline">{t('backToPlatform')}</span>
              <span className="sm:hidden">{t('back3')}</span>
            </Button>
          </div>
        )}
        
        <header className={`sticky ${isImpersonating ? 'top-[48px] sm:top-[60px]' : 'top-0'} z-30 bg-background/80 backdrop-blur-xl border-b border-border/40 px-4 sm:px-6 py-3 sm:py-4`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3 sm:gap-4 min-w-0">
              <div className="w-9 h-9 sm:w-11 sm:h-11 rounded-xl bg-gradient-to-br from-brand-navy to-brand-turquoise flex items-center justify-center shadow-lg shadow-brand-navy/20 flex-shrink-0">
                <Command className="h-4 w-4 sm:h-5 sm:w-5 text-white" />
              </div>
              <div className="min-w-0">
                <h1 className="font-cairo text-lg sm:text-xl font-bold text-foreground truncate">
                  {isRTL ? 'مركز القيادة' : 'Command Center'}
                </h1>
                <p className="text-xs sm:text-sm text-muted-foreground font-tajawal truncate">
                  {isImpersonating && schoolContext 
                    ? (isRTL ? `معاينة: ${schoolContext.school_name}` : `Previewing: ${schoolContext.school_name}`)
                    : (isRTL 
                        ? `مرحباً${user?.title && user?.title !== 'none' ? ` ${user.title}` : ''}، ${user?.full_name}` 
                        : `Welcome${user?.title && user?.title !== 'none' ? ` ${user.title}` : ''}, ${user?.full_name}`)
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
      <HakimAssistant />
    </Sidebar>
  );
}
