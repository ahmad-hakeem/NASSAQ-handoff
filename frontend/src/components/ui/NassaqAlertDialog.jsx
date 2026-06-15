import React, { createContext, useContext, useState, useCallback, useRef } from 'react';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
} from './alert-dialog';
import { Button } from './button';
import { AlertTriangle, AlertCircle, CheckCircle, Info, XCircle, ShieldAlert } from 'lucide-react';

const ALERT_TYPES = {
  warning: {
    icon: AlertTriangle,
    iconColor: 'text-amber-500',
    bgColor: 'bg-amber-50',
    borderColor: 'border-amber-200',
    buttonClass: 'bg-amber-600 hover:bg-amber-700 text-white',
  },
  error: {
    icon: XCircle,
    iconColor: 'text-red-500',
    bgColor: 'bg-red-50',
    borderColor: 'border-red-200',
    buttonClass: 'bg-red-600 hover:bg-red-700 text-white',
  },
  success: {
    icon: CheckCircle,
    iconColor: 'text-emerald-500',
    bgColor: 'bg-emerald-50',
    borderColor: 'border-emerald-200',
    buttonClass: 'bg-emerald-600 hover:bg-emerald-700 text-white',
  },
  info: {
    icon: Info,
    iconColor: 'text-blue-500',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
    buttonClass: 'bg-blue-600 hover:bg-blue-700 text-white',
  },
  confirm: {
    icon: ShieldAlert,
    iconColor: 'text-indigo-500',
    bgColor: 'bg-indigo-50',
    borderColor: 'border-indigo-200',
    buttonClass: 'bg-indigo-600 hover:bg-indigo-700 text-white',
  },
};

const NassaqAlertContext = createContext(null);

export const useNassaqAlert = () => {
  const context = useContext(NassaqAlertContext);
  if (!context) {
    throw new Error('useNassaqAlert must be used within NassaqAlertProvider');
  }
  return context;
};

export const NassaqAlertProvider = ({ children }) => {
  const [alertState, setAlertState] = useState({
    open: false,
    type: 'warning',
    title: '',
    message: '',
    confirmText: '',
    cancelText: '',
    onConfirm: null,
    onCancel: null,
    showCancel: false,
    secondaryActionText: '',
    onSecondaryAction: null,
    extraContent: null,
  });

  // Refs hold the latest callbacks so handleConfirm/handleCancel/handleSecondaryAction
  // never suffer stale-closure misses regardless of React batching or render order.
  const onConfirmRef = useRef(null);
  const onCancelRef = useRef(null);
  const onSecondaryActionRef = useRef(null);

  const showAlert = useCallback(({
    type = 'warning',
    title,
    message,
    confirmText,
    cancelText,
    onConfirm,
    onCancel,
    showCancel = false,
    secondaryActionText,
    onSecondaryAction,
    extraContent = null,
  }) => {
    // Keep refs in sync BEFORE the state update so any in-flight handler
    // immediately sees the correct callbacks even before a re-render.
    onConfirmRef.current = onConfirm || null;
    onCancelRef.current = onCancel || null;
    onSecondaryActionRef.current = onSecondaryAction || null;

    setAlertState({
      open: true,
      type,
      title: title || (type === 'warning' ? 'تنبيه' : type === 'error' ? 'خطأ' : type === 'success' ? 'تم بنجاح' : type === 'info' ? 'معلومة' : 'تأكيد'),
      message,
      confirmText: confirmText || 'حسناً',
      cancelText: cancelText || 'إلغاء',
      onConfirm: onConfirm || null,
      onCancel: onCancel || null,
      showCancel,
      secondaryActionText: secondaryActionText || '',
      onSecondaryAction: onSecondaryAction || null,
      extraContent: extraContent || null,
    });
  }, []);

  const nassaqWarning = useCallback((message, options = {}) => {
    showAlert({ type: 'warning', message, ...options });
  }, [showAlert]);

  const nassaqError = useCallback((message, options = {}) => {
    showAlert({ type: 'error', message, ...options });
  }, [showAlert]);

  const nassaqSuccess = useCallback((message, options = {}) => {
    showAlert({ type: 'success', message, ...options });
  }, [showAlert]);

  const nassaqInfo = useCallback((message, options = {}) => {
    showAlert({ type: 'info', message, ...options });
  }, [showAlert]);

  const nassaqConfirm = useCallback((message, onConfirm, options = {}) => {
    showAlert({
      type: 'confirm',
      message,
      showCancel: true,
      onConfirm,
      ...options,
    });
  }, [showAlert]);

  const closeAlert = useCallback(() => {
    // Clear refs when the dialog closes so stale callbacks are never invoked
    // on a subsequent open of an unrelated dialog type.
    onConfirmRef.current = null;
    onCancelRef.current = null;
    onSecondaryActionRef.current = null;
    setAlertState(prev => ({ ...prev, open: false, onConfirm: null, onCancel: null, onSecondaryAction: null }));
  }, []);

  const handleConfirm = useCallback(async () => {
    // Read the callback from the ref — always current, no stale-closure risk.
    const fn = onConfirmRef.current;
    if (process.env.NODE_ENV === 'development') {
      console.debug('[NassaqAlertDialog] handleConfirm fired', {
        hasFn: typeof fn === 'function',
        fnName: fn?.name || '(anonymous)',
      });
    }
    closeAlert();
    if (fn) {
      await fn();
    }
  }, [closeAlert]);

  const handleCancel = useCallback(() => {
    const fn = onCancelRef.current;
    closeAlert();
    if (fn) fn();
  }, [closeAlert]);

  const handleSecondaryAction = useCallback(async () => {
    const fn = onSecondaryActionRef.current;
    closeAlert();
    if (fn) {
      await fn();
    }
  }, [closeAlert]);

  const config = ALERT_TYPES[alertState.type] || ALERT_TYPES.warning;
  const IconComponent = config.icon;

  return (
    <NassaqAlertContext.Provider value={{ showAlert, nassaqWarning, nassaqError, nassaqSuccess, nassaqInfo, nassaqConfirm }}>
      {children}
      <AlertDialog open={alertState.open} onOpenChange={(open) => { if (!open) closeAlert(); }}>
        <AlertDialogContent
          className="max-w-md max-h-[85vh] flex flex-col rounded-2xl p-0 gap-0 overflow-hidden border-0 shadow-2xl"
          dir="rtl"
          data-nassaq-alert={alertState.type}
          data-testid="nassaq-alert-dialog"
        >
          <div className={`flex-shrink-0 ${config.bgColor} ${config.borderColor} border-b px-6 pt-6 pb-4`}>
            <AlertDialogHeader className="flex flex-row items-center gap-3 space-y-0">
              <div className={`flex-shrink-0 w-12 h-12 rounded-full ${config.bgColor} border-2 ${config.borderColor} flex items-center justify-center`}>
                <IconComponent className={`h-6 w-6 ${config.iconColor}`} />
              </div>
              <div className="flex-1 text-right">
                <AlertDialogTitle className="text-lg font-bold font-cairo text-gray-900">
                  {alertState.title}
                </AlertDialogTitle>
              </div>
            </AlertDialogHeader>
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto px-6 py-5">
            <AlertDialogDescription className="text-sm text-gray-700 leading-relaxed font-cairo text-right whitespace-pre-wrap break-words">
              {alertState.message}
            </AlertDialogDescription>
            {alertState.extraContent && (
              <div className="mt-4 text-right">
                {alertState.extraContent}
              </div>
            )}
          </div>

          <AlertDialogFooter className="flex-shrink-0 px-6 pb-5 pt-3 gap-2 flex-row-reverse sm:flex-row-reverse">
            <Button
              onClick={handleConfirm}
              className={`${config.buttonClass} rounded-xl px-6 py-2.5 text-sm font-bold font-cairo shadow-md hover:shadow-lg transition-all`}
            >
              {alertState.confirmText}
            </Button>
            {alertState.secondaryActionText && alertState.onSecondaryAction && (
              <Button
                variant="outline"
                onClick={handleSecondaryAction}
                data-testid="nassaq-alert-secondary-action"
                className="rounded-xl px-6 py-2.5 text-sm font-bold font-cairo border-indigo-300 text-indigo-700 hover:bg-indigo-50 mt-0"
              >
                {alertState.secondaryActionText}
              </Button>
            )}
            {alertState.showCancel && (
              <Button
                variant="outline"
                onClick={handleCancel}
                className="rounded-xl px-6 py-2.5 text-sm font-medium font-cairo border-gray-200 hover:bg-gray-50 mt-0"
              >
                {alertState.cancelText}
              </Button>
            )}
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </NassaqAlertContext.Provider>
  );
};

export default NassaqAlertProvider;
