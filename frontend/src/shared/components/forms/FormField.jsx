import React from 'react';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Textarea } from '@/shared/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';

export function FormField({
  name,
  label,
  type = 'text',
  value,
  onChange,
  error,
  required = false,
  placeholder,
  options = [],
  disabled = false,
  dir,
  className = '',
  icon: Icon,
  hint,
  rows = 3,
  min,
  max,
}) {
  const fieldId = `form-field-${name}`;
  const hasError = !!error;

  const renderInput = () => {
    switch (type) {
      case 'select':
        return (
          <Select
            value={value || ''}
            onValueChange={(val) => onChange(name, val)}
            disabled={disabled}
          >
            <SelectTrigger
              id={fieldId}
              className={`rounded-xl ${hasError ? 'border-red-500 ring-1 ring-red-500' : ''} ${className}`}
              dir={dir}
            >
              <SelectValue placeholder={placeholder || `اختر ${label}`} />
            </SelectTrigger>
            <SelectContent>
              {options.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );

      case 'textarea':
        return (
          <Textarea
            id={fieldId}
            value={value || ''}
            onChange={(e) => onChange(name, e.target.value)}
            placeholder={placeholder}
            disabled={disabled}
            dir={dir}
            rows={rows}
            className={`rounded-xl resize-none ${hasError ? 'border-red-500 ring-1 ring-red-500' : ''} ${className}`}
          />
        );

      case 'number':
        return (
          <Input
            id={fieldId}
            type="number"
            value={value || ''}
            onChange={(e) => onChange(name, e.target.value)}
            placeholder={placeholder}
            disabled={disabled}
            dir={dir || 'ltr'}
            min={min}
            max={max}
            className={`rounded-xl ${hasError ? 'border-red-500 ring-1 ring-red-500' : ''} ${className}`}
          />
        );

      case 'email':
        return (
          <div className="relative">
            <Input
              id={fieldId}
              type="email"
              value={value || ''}
              onChange={(e) => onChange(name, e.target.value)}
              placeholder={placeholder}
              disabled={disabled}
              dir="ltr"
              className={`rounded-xl ${Icon ? 'pe-10' : ''} ${hasError ? 'border-red-500 ring-1 ring-red-500' : ''} ${className}`}
            />
            {Icon && (
              <Icon className="absolute top-1/2 -translate-y-1/2 end-3 h-4 w-4 text-muted-foreground" />
            )}
          </div>
        );

      case 'tel':
        return (
          <Input
            id={fieldId}
            type="tel"
            value={value || ''}
            onChange={(e) => onChange(name, e.target.value)}
            placeholder={placeholder}
            disabled={disabled}
            dir="ltr"
            className={`rounded-xl ${hasError ? 'border-red-500 ring-1 ring-red-500' : ''} ${className}`}
          />
        );

      default:
        return (
          <div className="relative">
            <Input
              id={fieldId}
              type={type}
              value={value || ''}
              onChange={(e) => onChange(name, e.target.value)}
              placeholder={placeholder}
              disabled={disabled}
              dir={dir}
              className={`rounded-xl ${Icon ? 'pe-10' : ''} ${hasError ? 'border-red-500 ring-1 ring-red-500' : ''} ${className}`}
            />
            {Icon && (
              <Icon className="absolute top-1/2 -translate-y-1/2 end-3 h-4 w-4 text-muted-foreground" />
            )}
          </div>
        );
    }
  };

  return (
    <div className="space-y-1.5">
      <Label htmlFor={fieldId} className="text-sm font-medium flex items-center gap-1">
        {label}
        {required && <span className="text-red-500">*</span>}
      </Label>
      {renderInput()}
      {hasError && (
        <p className="text-xs text-red-500 mt-0.5">{error}</p>
      )}
      {hint && !hasError && (
        <p className="text-xs text-muted-foreground mt-0.5">{hint}</p>
      )}
    </div>
  );
}
