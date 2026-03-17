import { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { Sidebar } from '../components/layout/Sidebar';
import { HakimAssistant } from '../components/hakim/HakimAssistant';
import HakimPresence from '../components/hakim/HakimPresence';
import { NotificationBell } from '../components/notifications/NotificationBell';
import { SchoolDashboardContent } from '../components/dashboard/SchoolDashboardContent';
import { Button } from '../components/ui/button';
import {
  Sun,
  Moon,
  Globe,
} from 'lucide-react';

export const SchoolDashboard = () => {
  const { user } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();

  return (
    <Sidebar>
      <div className="min-h-screen" data-testid="school-dashboard">
        {/* Header */}
        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="font-cairo text-2xl font-bold">
                {isRTL ? 'مركز القيادة' : 'Command Center'}
              </h1>
              <p className="text-sm text-muted-foreground font-tajawal">
                {isRTL ? `مرحباً، ${user?.full_name}` : `Welcome, ${user?.full_name}`}
              </p>
            </div>
            
            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" onClick={toggleLanguage} data-testid="language-toggle">
                <Globe className="h-5 w-5" />
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme} data-testid="theme-toggle">
                {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </Button>
              <NotificationBell />
            </div>
          </div>
        </header>

        <div className="px-6 pt-4">
          <div className="flex items-center gap-3 p-3 rounded-2xl bg-gradient-to-r from-violet-50/80 via-cyan-50/50 to-transparent dark:from-violet-950/30 dark:via-cyan-950/20 dark:to-transparent border border-violet-100/50 dark:border-violet-800/30">
            <HakimPresence size="sm" showMessage={true} messagePosition="bottom" />
          </div>
        </div>

        <div className="p-6">
          <SchoolDashboardContent />
        </div>
      </div>
      <HakimAssistant />
    </Sidebar>
  );
};

export default SchoolDashboard;
