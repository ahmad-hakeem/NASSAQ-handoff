import {
  ArrowLeftRight,
  RefreshCw,
  Shield,
  Building2,
  GraduationCap,
  BookOpen,
  Users,
  Eye,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../../ui/dialog';
import { Button } from '../../ui/button';
import { Badge } from '../../ui/badge';
import { useTheme, useTranslation } from '../../../contexts/ThemeContext';

export default function RoleSwitcherDialog({
  open,
  onOpenChange,
  loadingRoles,
  availableRoles,
  switchingRole,
  onSelectRole,
  isSwitchedRole,
  onReturnToOriginal,
}) {
  const { isRTL } = useTheme();
  const { t } = useTranslation();

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ArrowLeftRight className="h-5 w-5 text-brand-turquoise" aria-hidden="true" strokeWidth={1.5} />
            {t('switchRole2')}
          </DialogTitle>
        </DialogHeader>

        {loadingRoles ? (
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="h-8 w-8 animate-spin text-brand-turquoise" aria-hidden="true" strokeWidth={1.5} />
          </div>
        ) : (
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {availableRoles.map((role, index) => (
              <button
                key={`${role.role}-${role.tenant_id || index}`}
                onClick={() => onSelectRole(role)}
                disabled={role.is_current || switchingRole}
                className={`w-full p-3 rounded-lg border transition-all text-start ${
                  role.is_current
                    ? 'bg-brand-turquoise/10 border-brand-turquoise'
                    : 'bg-background border-border hover:border-brand-turquoise hover:bg-muted'
                } ${switchingRole ? 'opacity-50 cursor-not-allowed' : ''}`}
                data-testid={`switch-role-${role.role}`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                      role.is_current ? 'bg-brand-turquoise text-white' : 'bg-muted'
                    }`}>
                      {role.is_preview ? (
                        <Eye className="h-5 w-5" aria-hidden="true" strokeWidth={1.5} />
                      ) : role.role === 'platform_admin' ? (
                        <Shield className="h-5 w-5" aria-hidden="true" strokeWidth={1.5} />
                      ) : role.role === 'school_principal' || role.role === 'school_admin' || role.role === 'school_sub_admin' ? (
                        <Building2 className="h-5 w-5" aria-hidden="true" strokeWidth={1.5} />
                      ) : role.role === 'teacher' || role.role === 'independent_teacher' ? (
                        <GraduationCap className="h-5 w-5" aria-hidden="true" strokeWidth={1.5} />
                      ) : role.role === 'student' ? (
                        <BookOpen className="h-5 w-5" aria-hidden="true" strokeWidth={1.5} />
                      ) : (
                        <Users className="h-5 w-5" aria-hidden="true" strokeWidth={1.5} />
                      )}
                    </div>
                    <div>
                      <p className="font-medium text-sm">
                        {isRTL ? (role.descriptive_ar || role.role_name_ar) : (role.descriptive_en || role.role_name_en)}
                      </p>
                      {role.tenant_name && !role.descriptive_ar && (
                        <p className="text-xs text-muted-foreground">
                          {role.tenant_name}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {role.is_current && (
                      <Badge variant="secondary" className="bg-brand-turquoise/20 text-brand-turquoise">
                        {t('current2')}
                      </Badge>
                    )}
                    {role.is_preview && (
                      <Badge variant="outline" className="text-amber-500 border-amber-500">
                        {t('preview')}
                      </Badge>
                    )}
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}

        {/* Task #528 — When the viewer is already in preview/switched mode,
            render a clearly separated footer block (divider + label + helper)
            so the exit action reads as a dedicated control, not another
            list option. */}
        {isSwitchedRole && (
          <div
            className="mt-4 pt-4 border-t border-border"
            data-testid="role-switcher-exit-preview-block"
          >
            <div className="mb-3 flex items-center gap-2 text-brand-turquoise">
              <Eye className="h-4 w-4" aria-hidden="true" strokeWidth={1.5} />
              <p className="text-sm font-semibold">
                {t('previewModeBannerTitle')}
              </p>
            </div>
            <p className="text-xs text-muted-foreground mb-3">
              {t('exitPreviewHelper')}
            </p>
            <Button
              variant="outline"
              onClick={onReturnToOriginal}
              disabled={switchingRole}
              data-testid="role-switcher-return-to-original-btn"
              className="w-full border-brand-turquoise/50 text-brand-turquoise hover:bg-brand-turquoise/10 hover:text-brand-turquoise focus-visible:text-brand-turquoise"
            >
              <RefreshCw
                className={`h-4 w-4 me-2 ${switchingRole ? 'animate-spin' : ''}`}
                aria-hidden="true"
                strokeWidth={1.5}
              />
              {t('returnToOriginalRole')}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
