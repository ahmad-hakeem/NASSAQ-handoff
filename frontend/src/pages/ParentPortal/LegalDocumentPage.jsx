import React, { useEffect, useState } from 'react';
import { useNavigate, useParams, Navigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useTranslation, useTheme } from '../../contexts/ThemeContext';
import PortalLayout from '../../components/portal/PortalLayout';
import { Card, CardContent } from '../../components/ui/card';
import { Skeleton } from '../../components/ui/skeleton';
import { Button } from '../../components/ui/button';
import { ChevronLeft, ChevronRight, FileText } from 'lucide-react';

const ParentLegalDocumentPage = ({ docType: docTypeProp }) => {
  const { docType: docTypeParam } = useParams();
  const requested = (docTypeProp || docTypeParam || 'terms').toLowerCase();
  // Both Privacy and Terms are now served by the unified public pages
  // (/privacy and /terms) across the whole platform — redirect any legacy
  // parent-portal legal URLs there.
  const isPrivacyRedirect = requested === 'privacy';
  const isTermsRedirect = requested === 'terms';
  const docType = null;
  const navigate = useNavigate();
  const { api } = useAuth();
  const { t } = useTranslation();
  const { isRTL, language } = useTheme();

  const [loading, setLoading] = useState(true);
  const [doc, setDoc] = useState(null);

  useEffect(() => {
    if (!docType) { setLoading(false); return; }
    let cancelled = false;
    setLoading(true);
    setDoc(null);
    // Only Terms & Conditions is served here. Privacy is unified at /privacy.
    api.get('/settings/terms/published')
      .then((res) => { if (!cancelled) setDoc(res.data || null); })
      .catch(() => { if (!cancelled) setDoc(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [api, docType]);

  // Hooks have all run — safe to redirect legacy /parent/legal/*
  // routes to the unified public pages.
  if (isPrivacyRedirect) {
    return <Navigate to="/privacy" replace />;
  }
  if (isTermsRedirect) {
    return <Navigate to="/terms" replace />;
  }

  const Icon = FileText;
  const title = !docType
    ? (t('notFound') || 'Not Found')
    : t('termsAndConditions');
  const Back = isRTL ? ChevronRight : ChevronLeft;

  const hasPublished = !!(doc && doc.version_number);
  const content = hasPublished
    ? ((language === 'en' ? doc?.content_en : doc?.content_ar)
        || doc?.content_ar || doc?.content_en || '')
    : '';

  return (
    <PortalLayout portalType="parent">
      <div className="p-4 space-y-4" data-testid="parent-legal-page">
        <div className="flex items-center gap-2 mb-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate('/parent/settings')}
            aria-label={t('back') || 'Back'}
            className="h-9 w-9"
          >
            <Back className="h-5 w-5" />
          </Button>
          <Icon className="h-6 w-6 text-brand-navy dark:text-brand-turquoise" />
          <h1 className="text-xl font-bold font-cairo text-foreground">{title}</h1>
        </div>

        <Card className="rounded-2xl border-0 shadow-sm bg-card">
          <CardContent className="p-5">
            {loading ? (
              <div className="space-y-3">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-5/6" />
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-4 w-full" />
              </div>
            ) : content ? (
              <article
                className="prose prose-sm max-w-none whitespace-pre-wrap font-tajawal text-foreground leading-7"
                dir={isRTL ? 'rtl' : 'ltr'}
              >
                {content}
                {doc?.version_number ? (
                  <p className="mt-6 text-xs text-muted-foreground">
                    {t('version')}: {doc.version_number}
                  </p>
                ) : null}
              </article>
            ) : (
              <div className="py-12 text-center">
                <Icon className="h-12 w-12 mx-auto mb-3 text-muted-foreground/50" />
                <p className="text-muted-foreground">{t('noData')}</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </PortalLayout>
  );
};

export default ParentLegalDocumentPage;
