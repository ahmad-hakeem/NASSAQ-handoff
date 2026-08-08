import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/shared/contexts/AuthContext';
import { useTranslation } from '@/shared/contexts/ThemeContext';
import { useNassaqAlert } from '@/shared/components/ui/NassaqAlertDialog';
import { toast } from 'sonner';
import { Button } from '@/shared/components/ui/button';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/shared/components/ui/dialog';
import { Label } from '@/shared/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/shared/components/ui/radio-group';
import { LoadingState } from '@/shared/components/ui/LoadingState';
import { HakimPlanCard, EmptyState } from '@/features/students/components/student-profile/ProfileComponents';
import { getApiErrorMessage } from '@/shared/models/utils/apiError';
import {
  Clock, Download, FileText, Calendar, User, Loader2, Stethoscope, Rocket,
} from 'lucide-react';

/**
 * Hakim smart-plans section (الخطة العلاجية / الخطة الإثرائية) for the
 * Independent Teacher student profile surfaces. Feature parity with the
 * leadership `PlansTab` in `student-profile/StudentTabsContent.jsx`, but
 * self-contained (own state + fetches) so it can mount inside the two
 * teacher-scoped dialogs without dragging in the leadership profile hook.
 *
 * Backend contract (already IT-enabled — teacher-permissions audit 2026-07-19):
 *   POST /hakim/student/{id}/ai-plans          — generate + persist history
 *   GET  /hakim/student/{id}/plan-history       — history log
 *   POST /export/student-plans/{id}[,/pdf]      — stamped DOCX / PDF export
 * All four enforce role gate + per-student `can_view_student`, so this
 * component adds zero new access — the API refuses students outside the
 * caller's workspace regardless of what the UI requests.
 *
 * `enrichmentOnly` (school teacher, 2026-07-21): renders only the enrichment
 * plan surface — no remedial card, no remedial/both export options, and the
 * generate call requests plan_type "enrichment". The backend independently
 * forces the same restriction for the teacher role, so this prop is UX
 * consistency, not the enforcement point.
 */
export default function StudentPlansSection({ studentId, studentName, enrichmentOnly = false }) {
  const { api, isRTL } = useAuth();
  const { t } = useTranslation();
  const { nassaqError } = useNassaqAlert();

  const [remedialPlan, setRemedialPlan] = useState(null);
  const [enrichmentPlan, setEnrichmentPlan] = useState(null);
  const [loadingRemedial, setLoadingRemedial] = useState(false);
  const [loadingEnrichment, setLoadingEnrichment] = useState(false);
  const [planHistory, setPlanHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(true);

  const [exportOpen, setExportOpen] = useState(false);
  const [exportPlanType, setExportPlanType] = useState('both');
  const [exportFormat, setExportFormat] = useState('pdf');
  const [exporting, setExporting] = useState(false);

  const fetchHistory = useCallback(async ({ hydrate } = {}) => {
    if (!studentId) return;
    setLoadingHistory(true);
    try {
      const res = await api.get(`/hakim/student/${studentId}/plan-history`);
      const records = res.data || [];
      setPlanHistory(records);
      if (hydrate) {
        // Records arrive newest-first; surface the most recent plan of each
        // type so previously generated plans stay visible after reopening.
        const latestRemedial = enrichmentOnly ? null : records.find((r) => r.plans?.remedial_plan);
        const latestEnrichment = records.find((r) => r.plans?.enrichment_plan);
        if (latestRemedial) setRemedialPlan(latestRemedial.plans.remedial_plan);
        if (latestEnrichment) setEnrichmentPlan(latestEnrichment.plans.enrichment_plan);
      }
    } catch (_e) {
      setPlanHistory([]);
    } finally {
      setLoadingHistory(false);
    }
  }, [api, studentId]);

  useEffect(() => {
    setRemedialPlan(null);
    setEnrichmentPlan(null);
    fetchHistory({ hydrate: true });
  }, [fetchHistory]);

  const generatePlan = async (planType) => {
    if (!studentId) return;
    const setLoadFn = planType === 'remedial' ? setLoadingRemedial : setLoadingEnrichment;
    setLoadFn(true);
    try {
      const res = await api.post(`/hakim/student/${studentId}/ai-plans`,
        enrichmentOnly ? { plan_type: 'enrichment' } : {});
      const plans = res.data?.plans;
      if (plans) {
        // The endpoint generates both plans in one call; fill whichever the
        // user asked for and opportunistically hydrate the sibling card.
        // In enrichmentOnly mode the backend already omits the remedial plan.
        if (planType === 'remedial') {
          if (plans.remedial_plan) setRemedialPlan(plans.remedial_plan);
          if (plans.enrichment_plan) setEnrichmentPlan((prev) => prev || plans.enrichment_plan);
        } else {
          if (plans.enrichment_plan) setEnrichmentPlan(plans.enrichment_plan);
          if (!enrichmentOnly && plans.remedial_plan) setRemedialPlan((prev) => prev || plans.remedial_plan);
        }
      }
      toast.success(t('planGeneratedByHakim'));
      fetchHistory({});
    } catch (e) {
      nassaqError(getApiErrorMessage(e) || t('failedToGeneratePlan'));
    } finally {
      setLoadFn(false);
    }
  };

  const openExportModal = (planType) => {
    setExportPlanType(enrichmentOnly ? 'enrichment' : (planType || 'both'));
    setExportFormat('pdf');
    setExportOpen(true);
  };

  const handleExport = async () => {
    if (!studentId) return;
    const payload = { plan_type: exportPlanType };
    if (exportPlanType === 'remedial' || exportPlanType === 'both') payload.remedial_plan = remedialPlan;
    if (exportPlanType === 'enrichment' || exportPlanType === 'both') payload.enrichment_plan = enrichmentPlan;
    setExporting(true);
    try {
      const isPdf = exportFormat === 'pdf';
      const url = isPdf ? `/export/student-plans/${studentId}/pdf` : `/export/student-plans/${studentId}`;
      const mimeType = isPdf ? 'application/pdf' : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
      const ext = isPdf ? 'pdf' : 'docx';
      const res = await api.post(url, payload, { responseType: 'blob' });
      if (res.data.type === 'application/json') {
        const text = await res.data.text();
        const errData = JSON.parse(text);
        throw new Error(errData.detail || 'Export failed');
      }
      const blob = new Blob([res.data], { type: mimeType });
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      const safeName = (studentName || 'student').replace(/\s+/g, '_');
      const date = new Date().toISOString().split('T')[0];
      const suffix = exportPlanType === 'remedial' ? 'Remedial_Plan' : exportPlanType === 'enrichment' ? 'Enrichment_Plan' : 'Plans';
      a.href = blobUrl;
      a.download = `${safeName}_${suffix}_${date}.${ext}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(blobUrl);
      a.remove();
      toast.success(t('planExportedSuccessfully'));
      setExportOpen(false);
    } catch (err) {
      let detail = err?.message || '';
      if (err?.response?.data instanceof Blob) {
        try {
          const text = await err.response.data.text();
          const parsed = JSON.parse(text);
          detail = parsed.detail || detail;
        } catch (_) { /* keep generic detail */ }
      } else if (getApiErrorMessage(err)) {
        detail = getApiErrorMessage(err);
      }
      nassaqError(isRTL ? `فشل تصدير الخطة: ${detail || 'خطأ غير معروف'}` : `Failed to export plan: ${detail || 'Unknown error'}`);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="space-y-4" data-testid="it-student-plans-section">
      <div className="relative my-2">
        <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-dashed border-brand-purple/20" /></div>
        <div className="relative flex justify-center">
          <span className="bg-background px-3 text-xs text-brand-purple font-cairo font-medium">{t('hakimAiPlans')}</span>
        </div>
      </div>

      {!enrichmentOnly && (
        <HakimPlanCard type="remedial" plan={remedialPlan} isRTL={isRTL} loading={loadingRemedial}
          onGenerate={() => generatePlan('remedial')} onExport={remedialPlan ? openExportModal : null} />
      )}

      <HakimPlanCard type="enrichment" plan={enrichmentPlan} isRTL={isRTL} loading={loadingEnrichment}
        onGenerate={() => generatePlan('enrichment')} onExport={enrichmentPlan ? openExportModal : null} />

      {!enrichmentOnly && remedialPlan && enrichmentPlan && (
        <Button variant="outline"
          className="w-full gap-2 border-brand-navy/20 text-brand-navy hover:bg-brand-navy/5 hover:text-brand-navy focus-visible:text-brand-navy"
          onClick={() => openExportModal('both')} disabled={exporting}>
          {exporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
          {t('exportBothPlans')}
        </Button>
      )}

      <Card>
        <CardContent className="p-6 space-y-3">
          <h3 className="font-bold text-base font-cairo flex items-center gap-2">
            <Clock className="h-5 w-5 text-brand-purple" />
            {t('planHistoryLog')}
          </h3>
          {loadingHistory ? (
            <LoadingState variant="section" />
          ) : planHistory.length === 0 ? (
            <EmptyState icon={Clock} message={t('noPlanHistoryYet')} />
          ) : (
            <div className="space-y-2">
              {planHistory.map((entry, i) => {
                // enrichmentOnly (school teacher): never surface remedial
                // metadata — defense-in-depth; the API already sanitizes.
                const hasRemedial = !enrichmentOnly && !!entry.plans?.remedial_plan;
                const hasEnrichment = !!entry.plans?.enrichment_plan;
                return (
                  <div key={entry.id || i} className="flex items-center gap-3 p-3 rounded-xl border hover:bg-muted/20 transition-colors">
                    <div className="w-8 h-8 rounded-lg bg-brand-purple/10 flex items-center justify-center flex-shrink-0">
                      <FileText className="h-4 w-4 text-brand-purple" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        {hasRemedial && <Badge variant="outline" className="text-[10px] border-rose-200 text-rose-600 dark:border-rose-800 dark:text-rose-400">{t('remedial')}</Badge>}
                        {hasEnrichment && <Badge variant="outline" className="text-[10px] border-emerald-200 text-emerald-600 dark:border-emerald-800 dark:text-emerald-400">{t('enrichment')}</Badge>}
                        <Badge variant="outline" className="text-[10px]">{entry.plan_source === 'ai' ? 'AI' : t('fallback')}</Badge>
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1"><Calendar className="h-3 w-3" />{entry.generated_at?.split('T')[0]}</span>
                        {entry.generated_by_name && <span className="flex items-center gap-1"><User className="h-3 w-3" />{entry.generated_by_name}</span>}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={exportOpen} onOpenChange={setExportOpen}>
        <DialogContent className="sm:max-w-md" dir={isRTL ? 'rtl' : 'ltr'}>
          <DialogHeader>
            <DialogTitle className="font-cairo flex items-center gap-2">
              <Download className="h-5 w-5 text-brand-navy" />
              {t('exportPlan')}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-5 pt-2">
            <div className="space-y-2">
              <Label className="text-sm font-medium font-cairo">{t('planType')}</Label>
              <RadioGroup value={exportPlanType} onValueChange={setExportPlanType} className="space-y-2">
                {!enrichmentOnly && remedialPlan && (
                  <label className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${exportPlanType === 'remedial' ? 'border-rose-300 bg-rose-50/50 dark:border-rose-700 dark:bg-rose-950/20' : 'border-border hover:border-rose-200'}`}>
                    <RadioGroupItem value="remedial" />
                    <Stethoscope className="h-4 w-4 text-rose-500 flex-shrink-0" />
                    <span className="text-sm font-medium">{t('remedialPlan')}</span>
                  </label>
                )}
                {enrichmentPlan && (
                  <label className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${exportPlanType === 'enrichment' ? 'border-emerald-300 bg-emerald-50/50 dark:border-emerald-700 dark:bg-emerald-950/20' : 'border-border hover:border-emerald-200'}`}>
                    <RadioGroupItem value="enrichment" />
                    <Rocket className="h-4 w-4 text-emerald-500 flex-shrink-0" />
                    <span className="text-sm font-medium">{t('enrichmentPlan')}</span>
                  </label>
                )}
                {!enrichmentOnly && remedialPlan && enrichmentPlan && (
                  <label className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${exportPlanType === 'both' ? 'border-brand-navy/30 bg-brand-navy/5 dark:border-brand-navy/50 dark:bg-brand-navy/10' : 'border-border hover:border-brand-navy/20'}`}>
                    <RadioGroupItem value="both" />
                    <FileText className="h-4 w-4 text-brand-navy flex-shrink-0" />
                    <span className="text-sm font-medium">{t('bothPlans')}</span>
                  </label>
                )}
              </RadioGroup>
            </div>

            <div className="space-y-2">
              <Label className="text-sm font-medium font-cairo">{t('fileFormat')}</Label>
              <RadioGroup value={exportFormat} onValueChange={setExportFormat} className="grid grid-cols-2 gap-2">
                <label className={`flex flex-col items-center gap-1.5 p-3 rounded-xl border cursor-pointer transition-all ${exportFormat === 'pdf' ? 'border-red-300 bg-red-50/50 dark:border-red-700 dark:bg-red-950/20 ring-1 ring-red-200 dark:ring-red-800' : 'border-border hover:border-red-200'}`}>
                  <RadioGroupItem value="pdf" className="sr-only" />
                  <div className="w-10 h-10 rounded-lg bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
                    <span className="text-red-600 dark:text-red-400 font-bold text-xs">PDF</span>
                  </div>
                  <span className="text-xs font-medium">{t('pdfFile')}</span>
                </label>
                <label className={`flex flex-col items-center gap-1.5 p-3 rounded-xl border cursor-pointer transition-all ${exportFormat === 'docx' ? 'border-blue-300 bg-blue-50/50 dark:border-blue-700 dark:bg-blue-950/20 ring-1 ring-blue-200 dark:ring-blue-800' : 'border-border hover:border-blue-200'}`}>
                  <RadioGroupItem value="docx" className="sr-only" />
                  <div className="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                    <span className="text-blue-600 dark:text-blue-400 font-bold text-xs">DOCX</span>
                  </div>
                  <span className="text-xs font-medium">{t('wordFile')}</span>
                </label>
              </RadioGroup>
            </div>

            <Button className="w-full gap-2 bg-brand-navy hover:bg-brand-navy/90 text-white" onClick={handleExport} disabled={exporting}>
              {exporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
              {t('download')}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
