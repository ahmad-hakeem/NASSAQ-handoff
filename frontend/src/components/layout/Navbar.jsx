import { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTheme, useTranslation } from '../../contexts/ThemeContext';
import { Button } from '../ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu';
import { 
  Menu, 
  X, 
  Sun, 
  Moon, 
  Globe, 
  User, 
  LogOut, 
  LayoutDashboard,
  ChevronDown 
} from 'lucide-react';

const LOGO_LIGHT = 'https://customer-assets.emergentagent.com/job_f5ea20bb-5cf5-462f-a7f0-958201e27f89/artifacts/a2a1b0lv_Nassaq%20LinkedIn%20Logo.png';
const LOGO_DARK = 'https://customer-assets.emergentagent.com/job_f5ea20bb-5cf5-462f-a7f0-958201e27f89/artifacts/q04svb5j_Nassaq%20LinkedIn%20Logo%20White.png';

export const Navbar = ({ variant = 'default' }) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { user, logout, isAuthenticated } = useAuth();
  const { theme, toggleTheme, toggleLanguage, language, isDark } = useTheme();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();

  const isTransparent = variant === 'transparent';
  const isLanding = location.pathname === '/';

  const navLinks = [
    // روابط التنقل الرئيسية فقط - تم إزالة المميزات والأسعار
  ];

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  const getDashboardLink = () => {
    if (!user) return '/login';
    switch (user.role) {
      case 'platform_admin':
        return '/admin';
      case 'school_principal':
      case 'school_sub_admin':
        return '/school';
      case 'teacher':
        return '/teacher';
      case 'student':
        return '/student';
      case 'parent':
        return '/parent';
      default:
        return '/dashboard';
    }
  };

  return (
    <nav
      data-testid="navbar"
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        isTransparent
          ? 'bg-transparent'
          : 'glass border-b border-border/50'
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16 lg:h-20">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2" data-testid="navbar-logo">
            <img
              src={isTransparent || isDark ? LOGO_DARK : LOGO_LIGHT}
              alt="نَسَّق"
              className="h-10 lg:h-12 w-auto"
            />
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden lg:flex items-center gap-8">
            {isLanding && navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className={`text-sm font-medium transition-colors hover:text-brand-turquoise ${
                  isTransparent ? 'text-white' : 'text-foreground'
                }`}
              >
                {link.label}
              </a>
            ))}
          </div>

          {/* Desktop Actions */}
          <div className="hidden lg:flex items-center gap-3">
            {/* Language Toggle */}
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleLanguage}
              data-testid="language-toggle"
              className={isTransparent ? 'text-white hover:bg-white/10' : ''}
            >
              <Globe className="h-5 w-5" />
            </Button>

            {/* Theme Toggle */}
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleTheme}
              data-testid="theme-toggle"
              className={isTransparent ? 'text-white hover:bg-white/10' : ''}
            >
              {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </Button>

            {isAuthenticated ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    data-testid="user-menu-trigger"
                    className={`gap-2 ${isTransparent ? 'text-white hover:bg-white/10' : ''}`}
                  >
                    <div className="w-8 h-8 rounded-full bg-brand-turquoise flex items-center justify-center">
                      <User className="h-4 w-4 text-white" />
                    </div>
                    <span className="hidden md:inline">{user?.full_name}</span>
                    <ChevronDown className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  <div className="px-2 py-1.5">
                    <p className="text-sm font-medium">{user?.full_name}</p>
                    <p className="text-xs text-muted-foreground">{user?.email}</p>
                  </div>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem asChild>
                    <Link to={getDashboardLink()} className="flex items-center gap-2" data-testid="dashboard-link">
                      <LayoutDashboard className="h-4 w-4" />
                      {t('dashboard')}
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={handleLogout} className="text-destructive" data-testid="logout-btn">
                    <LogOut className="h-4 w-4 me-2" />
                    {t('logout')}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            ) : (
              <>
                <Button
                  variant="ghost"
                  asChild
                  className={isTransparent ? 'text-white hover:bg-white/10' : ''}
                  data-testid="login-link"
                >
                  <Link to="/login">{t('login')}</Link>
                </Button>
                <Button
                  asChild
                  className="bg-brand-turquoise hover:bg-brand-turquoise-light text-white rounded-xl"
                  data-testid="register-link"
                >
                  <Link to="/register">{t('register')}</Link>
                </Button>
              </>
            )}
          </div>

          {/* Mobile Menu Button */}
          <Button
            variant="ghost"
            size="icon"
            className={`lg:hidden ${isTransparent ? 'text-white' : ''}`}
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            data-testid="mobile-menu-toggle"
          >
            {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </Button>
        </div>
      </div>

      {/* Mobile Menu */}
      {mobileMenuOpen && (
        <div className="lg:hidden glass border-t border-border/50 animate-fade-in" data-testid="mobile-menu">
          <div className="px-4 py-4 space-y-3">
            {isLanding && navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="block py-2 text-foreground hover:text-brand-turquoise"
                onClick={() => setMobileMenuOpen(false)}
              >
                {link.label}
              </a>
            ))}
            
            <div className="flex items-center gap-2 py-2">
              <Button variant="ghost" size="icon" onClick={toggleLanguage}>
                <Globe className="h-5 w-5" />
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme}>
                {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </Button>
            </div>

            {isAuthenticated ? (
              <>
                <Link
                  to={getDashboardLink()}
                  className="block py-2 text-foreground hover:text-brand-turquoise"
                  onClick={() => setMobileMenuOpen(false)}
                >
                  {t('dashboard')}
                </Link>
                <Button
                  variant="ghost"
                  className="w-full justify-start text-destructive"
                  onClick={handleLogout}
                >
                  <LogOut className="h-4 w-4 me-2" />
                  {t('logout')}
                </Button>
              </>
            ) : (
              <div className="flex gap-2 pt-2">
                <Button variant="outline" asChild className="flex-1">
                  <Link to="/login" onClick={() => setMobileMenuOpen(false)}>
                    {t('login')}
                  </Link>
                </Button>
                <Button asChild className="flex-1 bg-brand-turquoise">
                  <Link to="/register" onClick={() => setMobileMenuOpen(false)}>
                    {t('register')}
                  </Link>
                </Button>
              </div>
            )}
          </div>
        </div>
      )}
    </nav>
  );
};
