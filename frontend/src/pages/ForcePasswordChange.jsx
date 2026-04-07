import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import { Eye, EyeOff, Lock, Shield, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';


import { useTranslation } from '../contexts/ThemeContext';
export default function ForcePasswordChange() {
  const navigate = useNavigate();
  const { user, logout, api } = useAuth();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  
  const { nassaqError, nassaqWarning } = useNassaqAlert();
  const [formData, setFormData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });
  
  const [errors, setErrors] = useState({});
  
  // Password validation rules
  const passwordRules = [
    { id: 'length', label: 'على الأقل 8 أحرف', labelEn: 'At least 8 characters', check: (p) => p.length >= 8 },
    { id: 'uppercase', label: 'حرف كبير واحد على الأقل', labelEn: 'At least one uppercase letter', check: (p) => /[A-Z]/.test(p) },
    { id: 'lowercase', label: 'حرف صغير واحد على الأقل', labelEn: 'At least one lowercase letter', check: (p) => /[a-z]/.test(p) },
    { id: 'number', label: 'رقم واحد على الأقل', labelEn: 'At least one number', check: (p) => /[0-9]/.test(p) },
    { id: 'special', label: 'رمز خاص واحد على الأقل (!@#$%)', labelEn: 'At least one special character', check: (p) => /[!@#$%^&*(),.?":{}|<>]/.test(p) },
  ];
  
  const isRTL = true; // Arabic interface
  
  const validatePassword = () => {
  const { t } = useTranslation();
    const newErrors = {};
    
    if (!formData.currentPassword) {
      newErrors.currentPassword = t('currentPasswordIsRequired');
    }
    
    if (!formData.newPassword) {
      newErrors.newPassword = t('newPasswordIsRequired');
    } else {
      const failedRules = passwordRules.filter(rule => !rule.check(formData.newPassword));
      if (failedRules.length > 0) {
        newErrors.newPassword = t('passwordDoesNotMeetAllRequirements');
      }
    }
    
    if (formData.newPassword === formData.currentPassword) {
      newErrors.newPassword = t('newPasswordMustBeDifferentFromCurrent');
    }
    
    if (formData.newPassword !== formData.confirmPassword) {
      newErrors.confirmPassword = t('passwordsDoNotMatch');
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validatePassword()) {
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      await api.post('/auth/change-password', {
        current_password: formData.currentPassword,
        new_password: formData.newPassword,
      });
      
      toast.success(t('passwordChangedSuccessfully2'));
      
      // Redirect based on user role
      setTimeout(() => {
        if (user?.role === 'platform_admin') {
          navigate('/admin');
        } else if (user?.role === 'teacher') {
          navigate('/teacher');
        } else {
          navigate('/');
        }
      }, 1500);
      
    } catch (error) {
      console.error('Password change error:', error);
      if (error.response?.status === 400) {
        nassaqError(t('currentPasswordIsIncorrect'));
        setErrors({ currentPassword: t('currentPasswordIsIncorrect') });
      } else {
        nassaqError(t('errorChangingPassword'));
      }
    } finally {
      setIsSubmitting(false);
    }
  };
  
  const handleLogout = () => {
    logout();
    navigate('/login');
  };
  
  return (
    <div className="relative min-h-screen bg-gradient-to-br from-brand-navy via-brand-navy/95 to-brand-turquoise/20 flex items-center justify-center p-4 overflow-hidden" dir="rtl">
      <div className="absolute inset-0 nassaq-pattern opacity-[0.04] pointer-events-none" style={{ backgroundImage: "url('/nassaq-pattern.png')" }} />
      <Card className="w-full max-w-md shadow-2xl">
        <CardHeader className="text-center pb-2">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-yellow-100 flex items-center justify-center">
            <AlertTriangle className="h-8 w-8 text-yellow-600" />
          </div>
          <CardTitle className="font-cairo text-2xl text-brand-navy">
            {t('passwordChangeRequired')}
          </CardTitle>
          <CardDescription className="text-base">
            {t('youMustChangeYourTemporaryPasswordBeforeContinuing')}
          </CardDescription>
        </CardHeader>
        
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Current Password */}
            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <Lock className="h-4 w-4" />
                {t('currentPassword')}
              </Label>
              <div className="relative">
                <Input
                  type={showCurrentPassword ? 'text' : 'password'}
                  value={formData.currentPassword}
                  onChange={(e) => setFormData({ ...formData, currentPassword: e.target.value })}
                  className={`rounded-xl pe-10 ${errors.currentPassword ? 'border-red-500' : ''}`}
                  placeholder={t('enterCurrentPassword')}
                  dir="ltr"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute end-1 top-1/2 -translate-y-1/2 h-8 w-8"
                  onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                >
                  {showCurrentPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
              {errors.currentPassword && (
                <p className="text-sm text-red-500 flex items-center gap-1">
                  <XCircle className="h-3 w-3" />
                  {errors.currentPassword}
                </p>
              )}
            </div>
            
            {/* New Password */}
            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <Shield className="h-4 w-4" />
                {t('newPassword')}
              </Label>
              <div className="relative">
                <Input
                  type={showNewPassword ? 'text' : 'password'}
                  value={formData.newPassword}
                  onChange={(e) => setFormData({ ...formData, newPassword: e.target.value })}
                  className={`rounded-xl pe-10 ${errors.newPassword ? 'border-red-500' : ''}`}
                  placeholder={t('enterNewPassword')}
                  dir="ltr"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute end-1 top-1/2 -translate-y-1/2 h-8 w-8"
                  onClick={() => setShowNewPassword(!showNewPassword)}
                >
                  {showNewPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
              {errors.newPassword && (
                <p className="text-sm text-red-500 flex items-center gap-1">
                  <XCircle className="h-3 w-3" />
                  {errors.newPassword}
                </p>
              )}
              
              {/* Password Rules */}
              <div className="p-3 bg-muted/50 rounded-xl space-y-1.5 mt-2">
                <p className="text-xs font-medium text-muted-foreground mb-2">
                  {t('passwordRequirements')}
                </p>
                {passwordRules.map((rule) => {
                  const passed = rule.check(formData.newPassword);
                  return (
                    <div key={rule.id} className={`flex items-center gap-2 text-xs ${passed ? 'text-green-600' : 'text-muted-foreground'}`}>
                      {passed ? (
                        <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
                      ) : (
                        <div className="w-3.5 h-3.5 rounded-full border border-muted-foreground/50" />
                      )}
                      {isRTL ? rule.label : rule.labelEn}
                    </div>
                  );
                })}
              </div>
            </div>
            
            {/* Confirm Password */}
            <div className="space-y-2">
              <Label className="flex items-center gap-2">
                <Lock className="h-4 w-4" />
                {t('confirmNewPassword')}
              </Label>
              <div className="relative">
                <Input
                  type={showConfirmPassword ? 'text' : 'password'}
                  value={formData.confirmPassword}
                  onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                  className={`rounded-xl pe-10 ${errors.confirmPassword ? 'border-red-500' : ''}`}
                  placeholder={t('reenterNewPassword')}
                  dir="ltr"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute end-1 top-1/2 -translate-y-1/2 h-8 w-8"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                >
                  {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
              {errors.confirmPassword && (
                <p className="text-sm text-red-500 flex items-center gap-1">
                  <XCircle className="h-3 w-3" />
                  {errors.confirmPassword}
                </p>
              )}
              {formData.confirmPassword && formData.newPassword === formData.confirmPassword && (
                <p className="text-sm text-green-600 flex items-center gap-1">
                  <CheckCircle2 className="h-3 w-3" />
                  {t('passwordsMatch')}
                </p>
              )}
            </div>
            
            {/* Submit Button */}
            <Button
              type="submit"
              disabled={isSubmitting}
              className="w-full bg-brand-navy hover:bg-brand-navy/90 rounded-xl py-6 text-lg font-bold"
            >
              {isSubmitting ? (
                <>
                  <div className="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full me-2" />
                  {t('changing')}
                </>
              ) : (
                <>
                  <Shield className="h-5 w-5 me-2" />
                  {t('changePassword')}
                </>
              )}
            </Button>
            
            {/* Logout Option */}
            <div className="text-center pt-2">
              <button
                type="button"
                onClick={handleLogout}
                className="text-sm text-muted-foreground hover:text-brand-navy underline"
              >
                {t('logout')}
              </button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
