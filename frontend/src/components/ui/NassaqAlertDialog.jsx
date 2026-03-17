import React, { createContext, useContext, useState, useCallback } from 'react';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogAction,
  AlertDialogCancel,
} from './alert-dialog';
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
  });

  const showAlert = useCallback(({
    type = 'warning',
    title,
    message,
    confirmText,
    cancelText,
    onConfirm,
    onCancel,
    showCancel = false,
  }) => {
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
    setAlertState(prev => ({ ...prev, open: false }));
  }, []);

  const handleConfirm = useCallback(async () => {
    if (alertState.onConfirm) await alertState.onConfirm();
    closeAlert();
  }, [alertState.onConfirm, closeAlert]);

  const handleCancel = useCallback(() => {
    if (alertState.onCancel) alertState.onCancel();
    closeAlert();
  }, [alertState.onCancel, closeAlert]);

  const config = ALERT_TYPES[alertState.type] || ALERT_TYPES.warning;
  const IconComponent = config.icon;

  return (
    <NassaqAlertContext.Provider value={{ showAlert, nassaqWarning, nassaqError, nassaqSuccess, nassaqInfo, nassaqConfirm }}>
      {children}
      <AlertDialog open={alertState.open} onOpenChange={(open) => { if (!open) handleCancel(); }}>
        <AlertDialogContent className="max-w-md rounded-2xl p-0 overflow-hidden border-0 shadow-2xl" dir="rtl">
          <div className={`${config.bgColor} ${config.borderColor} border-b px-6 pt-6 pb-4`}>
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

          <div className="px-6 py-5">
            <AlertDialogDescription className="text-sm text-gray-700 leading-relaxed font-cairo text-right whitespace-pre-wrap">
              {alertState.message}
            </AlertDialogDescription>
          </div>

          <AlertDialogFooter className="px-6 pb-5 gap-2 flex-row-reverse sm:flex-row-reverse">
            <AlertDialogAction
              onClick={handleConfirm}
              className={`${config.buttonClass} rounded-xl px-6 py-2.5 text-sm font-bold font-cairo shadow-md hover:shadow-lg transition-all`}
            >
              {alertState.confirmText}
            </AlertDialogAction>
            {alertState.showCancel && (
              <AlertDialogCancel
                onClick={handleCancel}
                className="rounded-xl px-6 py-2.5 text-sm font-medium font-cairo border-gray-200 hover:bg-gray-50 mt-0"
              >
                {alertState.cancelText}
              </AlertDialogCancel>
            )}
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </NassaqAlertContext.Provider>
  );
};

export default NassaqAlertProvider;
