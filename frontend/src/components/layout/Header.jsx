import { useTheme } from '../../contexts/ThemeContext';
import { Button } from '../ui/button';
import { NotificationBell } from '../notifications/NotificationBell';
import { Sun, Moon, Globe } from 'lucide-react';

export const Header = ({ title, subtitle, children }) => {
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();

  return (
    <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-cairo text-2xl font-bold text-foreground">
            {title}
          </h1>
          {subtitle && (
            <p className="text-sm text-muted-foreground font-tajawal">
              {subtitle}
            </p>
          )}
        </div>
        
        <div className="flex items-center gap-3">
          {/* Custom content */}
          {children}
          
          {/* Notification Bell */}
          <NotificationBell />
          
          {/* Language Toggle */}
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={toggleLanguage} 
            className="rounded-xl"
            data-testid="language-toggle-btn"
          >
            <Globe className="h-5 w-5" />
          </Button>
          
          {/* Theme Toggle */}
          <Button 
            variant="ghost" 
            size="icon" 
            onClick={toggleTheme} 
            className="rounded-xl"
            data-testid="theme-toggle-btn"
          >
            {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </Button>
        </div>
      </div>
    </header>
  );
};
