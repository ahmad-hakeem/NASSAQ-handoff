import React from 'react';

export function FormSection({ title, subtitle, icon: Icon, children, className = '' }) {
  return (
    <div className={`space-y-3 ${className}`}>
      {(title || subtitle) && (
        <div className="flex items-center gap-2">
          {Icon && <Icon className="h-5 w-5 text-brand-turquoise" />}
          <div>
            {title && <h3 className="text-sm font-bold font-cairo">{title}</h3>}
            {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
          </div>
        </div>
      )}
      {children}
    </div>
  );
}
