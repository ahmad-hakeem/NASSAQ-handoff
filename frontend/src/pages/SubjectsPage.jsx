import { useTheme, useTranslation } from '../contexts/ThemeContext';
import { Sidebar } from '../components/layout/Sidebar';
import { Button } from '../components/ui/button';
import { SubjectsManager } from '../components/subjects/SubjectsManager';
import { Sun, Moon, Globe, ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';

export const SubjectsPage = () => {
  const { toggleTheme, toggleLanguage, isDark } = useTheme();
  const { t } = useTranslation();

  return (
    <Sidebar>
      <div className="min-h-screen bg-background" data-testid="subjects-page">
        {/* Header */}
        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Button variant="ghost" size="icon" asChild className="rounded-xl">
                <Link to="/admin">
                  <ArrowLeft className="h-5 w-5" />
                </Link>
              </Button>
              <div>
                <h1 className="font-cairo text-2xl font-bold text-foreground">
                  {t('subjectsManagement')}
                </h1>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <Button variant="ghost" size="icon" onClick={toggleLanguage} className="rounded-xl" data-testid="toggle-language-btn">
                <Globe className="h-5 w-5" />
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme} className="rounded-xl" data-testid="toggle-theme-btn">
                {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </Button>
            </div>
          </div>
        </header>

        <div className="p-6">
          <SubjectsManager />
        </div>
      </div>
    </Sidebar>
  );
};
