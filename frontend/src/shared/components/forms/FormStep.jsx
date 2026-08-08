import React from 'react';
import { FormField } from './FormField';
import { FormGrid } from './FormGrid';
import { FormSection } from './FormSection';

export function FormStep({
  fields = [],
  sections = [],
  formData,
  errors,
  updateField,
  columns = 2,
  title,
  subtitle,
  icon,
}) {
  if (sections.length > 0) {
    return (
      <div className="space-y-6">
        {sections.map((section, sIdx) => (
          <FormSection key={sIdx} title={section.title} subtitle={section.subtitle} icon={section.icon}>
            <FormGrid columns={section.columns || columns}>
              {section.fields.map((field) => (
                <FormField
                  key={field.name}
                  {...field}
                  value={formData[field.name]}
                  error={errors[field.name]}
                  onChange={updateField}
                />
              ))}
            </FormGrid>
          </FormSection>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {(title || subtitle) && (
        <FormSection title={title} subtitle={subtitle} icon={icon} />
      )}
      <FormGrid columns={columns}>
        {fields.map((field) => (
          <FormField
            key={field.name}
            {...field}
            value={formData[field.name]}
            error={errors[field.name]}
            onChange={updateField}
          />
        ))}
      </FormGrid>
    </div>
  );
}
