import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { registerMfaStepUpHandler } from '@/shared/services/mfaStepUpBridge';
import MfaStepUpDialog from '@/features/auth/components/mfa/MfaStepUpDialog';

const MfaStepUpContext = createContext(null);

export const useMfaStepUp = () => {
  const ctx = useContext(MfaStepUpContext);
  if (!ctx) {
    throw new Error('useMfaStepUp must be used within MfaStepUpProvider');
  }
  return ctx;
};

export const MfaStepUpProvider = ({ children }) => {
  const [open, setOpen] = useState(false);
  const [errorContext, setErrorContext] = useState(null);

  const pendingRef = useRef(null);

  const requestStepUp = useCallback((ctxArg) => {
    if (pendingRef.current) {
      pendingRef.current.reject(new Error('MFA_STEPUP_SUPERSEDED'));
      pendingRef.current = null;
    }
    return new Promise((resolve, reject) => {
      pendingRef.current = { resolve, reject };
      setErrorContext(ctxArg || null);
      setOpen(true);
    });
  }, []);

  useEffect(() => {
    return registerMfaStepUpHandler(requestStepUp);
  }, [requestStepUp]);

  const handleSuccess = useCallback((accessToken) => {
    setOpen(false);
    setErrorContext(null);
    if (pendingRef.current) {
      pendingRef.current.resolve(accessToken);
      pendingRef.current = null;
    }
  }, []);

  const handleCancel = useCallback(() => {
    setOpen(false);
    setErrorContext(null);
    if (pendingRef.current) {
      pendingRef.current.reject(new Error('MFA_STEPUP_CANCELLED'));
      pendingRef.current = null;
    }
  }, []);

  const value = useMemo(
    () => ({ requestStepUp, isStepUpOpen: open }),
    [requestStepUp, open],
  );

  return (
    <MfaStepUpContext.Provider value={value}>
      {children}
      <MfaStepUpDialog
        open={open}
        errorContext={errorContext}
        onSuccess={handleSuccess}
        onCancel={handleCancel}
      />
    </MfaStepUpContext.Provider>
  );
};

export default MfaStepUpProvider;
