import React, { useState, useCallback, useMemo } from 'react';
import { Card, CardContent } from '@/shared/components/ui/card';
import { StepIndicator } from './StepIndicator';
import { StickyActionBar } from './StickyActionBar';

export function FormContainer({
  steps,
  initialData = {},
  onSubmit,
  onCancel,
  title,
  subtitle,
  submitLabel = 'إرسال',
  cancelLabel = 'إلغاء',
  nextLabel = 'التالي',
  prevLabel = 'السابق',
  isRTL = true,
  loading = false,
  className = '',
  renderHeader,
  validateStep,
}) {
  const [currentStep, setCurrentStep] = useState(0);
  const [formData, setFormData] = useState(initialData);
  const [errors, setErrors] = useState({});
  const [stepCompleted, setStepCompleted] = useState({});

  const totalSteps = steps.length;
  const isLastStep = currentStep === totalSteps - 1;
  const isFirstStep = currentStep === 0;
  const activeStep = steps[currentStep];

  const updateField = useCallback((field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    setErrors(prev => {
      const next = { ...prev };
      delete next[field];
      return next;
    });
  }, []);

  const updateFields = useCallback((fields) => {
    setFormData(prev => ({ ...prev, ...fields }));
    setErrors(prev => {
      const next = { ...prev };
      Object.keys(fields).forEach(k => delete next[k]);
      return next;
    });
  }, []);

  const runValidation = useCallback(() => {
    if (!activeStep?.fields) return true;

    const stepErrors = {};
    activeStep.fields.forEach(field => {
      if (field.required) {
        const value = formData[field.name];
        if (value === undefined || value === null || value === '' || (Array.isArray(value) && value.length === 0)) {
          stepErrors[field.name] = field.errorMessage || `${field.label} مطلوب`;
        }
      }
      if (field.validate && formData[field.name]) {
        const err = field.validate(formData[field.name], formData);
        if (err) stepErrors[field.name] = err;
      }
    });

    if (validateStep) {
      const customErrors = validateStep(currentStep, formData);
      if (customErrors) Object.assign(stepErrors, customErrors);
    }

    setErrors(stepErrors);
    return Object.keys(stepErrors).length === 0;
  }, [activeStep, formData, currentStep, validateStep]);

  const handleNext = useCallback(() => {
    if (!runValidation()) return;
    setStepCompleted(prev => ({ ...prev, [currentStep]: true }));
    if (isLastStep) {
      onSubmit?.(formData);
    } else {
      setCurrentStep(prev => prev + 1);
    }
  }, [runValidation, isLastStep, currentStep, onSubmit, formData]);

  const handlePrev = useCallback(() => {
    if (!isFirstStep) {
      setCurrentStep(prev => prev - 1);
    }
  }, [isFirstStep]);

  const handleGoToStep = useCallback((stepIndex) => {
    if (stepIndex < currentStep || stepCompleted[stepIndex - 1] || stepIndex === 0) {
      setCurrentStep(stepIndex);
    }
  }, [currentStep, stepCompleted]);

  const contextValue = useMemo(() => ({
    formData,
    errors,
    updateField,
    updateFields,
    currentStep,
    totalSteps,
    isRTL,
  }), [formData, errors, updateField, updateFields, currentStep, totalSteps, isRTL]);

  return (
    <div className={`flex flex-col h-full ${className}`} dir={isRTL ? 'rtl' : 'ltr'}>
      {renderHeader ? renderHeader({ title, subtitle, currentStep, totalSteps }) : (
        title && (
          <div className="text-center mb-4 shrink-0">
            <h2 className="text-xl font-bold font-cairo">{title}</h2>
            {subtitle && <p className="text-sm text-muted-foreground mt-1">{subtitle}</p>}
          </div>
        )
      )}

      <StepIndicator
        steps={steps}
        currentStep={currentStep}
        completedSteps={stepCompleted}
        onStepClick={handleGoToStep}
        isRTL={isRTL}
      />

      <div className="flex-1 min-h-0 flex flex-col justify-center py-4">
        <Card className="border-0 shadow-none">
          <CardContent className="p-0">
            {activeStep?.render ? (
              activeStep.render(contextValue)
            ) : activeStep?.component ? (
              <activeStep.component {...contextValue} />
            ) : null}
          </CardContent>
        </Card>
      </div>

      <StickyActionBar
        isFirstStep={isFirstStep}
        isLastStep={isLastStep}
        onNext={handleNext}
        onPrev={handlePrev}
        onCancel={onCancel}
        nextLabel={isLastStep ? submitLabel : nextLabel}
        prevLabel={prevLabel}
        cancelLabel={cancelLabel}
        loading={loading}
        isRTL={isRTL}
      />
    </div>
  );
}
