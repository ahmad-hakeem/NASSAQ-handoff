import React from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from '../contexts/ThemeContext';
import { Trash2, ArrowLeft } from 'lucide-react';

/**
 * Task #276 — IT account-erasure landing page.
 *
 * Public, unauthenticated route shown after the user confirms a
 * GDPR right-to-be-forgotten request. The session is force-logged-out
 * by the dialog handler before redirecting here, so this page never
 * needs auth context. Copy mirrors the dialog: workspace queued for
 * permanent deletion, final export emailed, no reactivation.
 */
const AccountErasedPage = () => {
  const { t } = useTranslation();
  return (
    <div
      dir="rtl"
      className="min-h-screen flex items-center justify-center bg-gradient-to-br from-red-50 via-white to-amber-50 px-4 py-12"
      data-testid="account-erased-page"
    >
      <div className="max-w-lg w-full bg-white rounded-3xl shadow-xl border border-red-100 p-8 text-center">
        <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-red-100 flex items-center justify-center">
          <Trash2 className="h-8 w-8 text-red-600" />
        </div>
        <h1 className="font-cairo text-2xl text-red-700 mb-2">
          {t('accountErasedTitle')}
        </h1>
        <p className="font-tajawal text-sm text-muted-foreground leading-relaxed whitespace-pre-line mb-6">
          {t('accountErasedBody')}
        </p>
        <div className="rounded-xl bg-red-50 border border-red-100 p-4 mb-6 text-right">
          <p className="font-cairo text-xs font-semibold text-red-700 mb-1">
            {t('accountErasedNoticeTitle')}
          </p>
          <p className="font-tajawal text-xs text-red-700/90 leading-relaxed">
            {t('accountErasedNoticeBody')}
          </p>
        </div>
        <Link
          to="/"
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-brand-navy text-white font-cairo text-sm hover:bg-brand-navy/90 transition"
          data-testid="account-erased-home-link"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('accountErasedHome')}
        </Link>
      </div>
    </div>
  );
};

export default AccountErasedPage;
