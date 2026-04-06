import { useState } from 'react';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';
import { Skeleton } from '../ui/skeleton';
import {
  Clock, Download, Sparkles, Loader2, Target, User,
  ChevronUp, ChevronDown, Plus, Stethoscope, Rocket
} from 'lucide-react';

export const TALENT_OPTIONS = [
  { value: 'academically_gifted', ar: 'متفوق أكاديمياً', en: 'Academically Gifted', color: 'bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-700' },
  { value: 'artistic', ar: 'فنان', en: 'Artistic', color: 'bg-purple-100 text-purple-700 border-purple-200 dark:bg-purple-900/30 dark:text-purple-300 dark:border-purple-700' },
  { value: 'athletic', ar: 'رياضي', en: 'Athletic', color: 'bg-green-100 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-300 dark:border-green-700' },
  { value: 'scientific', ar: 'علمي', en: 'Scientific', color: 'bg-cyan-100 text-cyan-700 border-cyan-200 dark:bg-cyan-900/30 dark:text-cyan-300 dark:border-cyan-700' },
  { value: 'leadership', ar: 'قيادي', en: 'Leadership', color: 'bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-900/30 dark:text-amber-300 dark:border-amber-700' },
  { value: 'literary', ar: 'أدبي', en: 'Literary', color: 'bg-rose-100 text-rose-700 border-rose-200 dark:bg-rose-900/30 dark:text-rose-300 dark:border-rose-700' },
  { value: 'musical', ar: 'موسيقي', en: 'Musical', color: 'bg-indigo-100 text-indigo-700 border-indigo-200 dark:bg-indigo-900/30 dark:text-indigo-300 dark:border-indigo-700' },
  { value: 'technological', ar: 'تقني', en: 'Technological', color: 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-900/30 dark:text-slate-300 dark:border-slate-700' },
];

export const HAKIM_POSES = {
  remedial: '/hakim-poses/support.png',
  enrichment: '/hakim-poses/motivating.png',
  thinking: '/hakim-poses/ai-thinking.png',
};

export const PLAN_CONFIG = {
  remedial: {
    title_ar: 'الخطة العلاجية', title_en: 'Remedial Plan',
    desc_ar: 'خطة لمعالجة نقاط الضعف وتحسين الأداء الأكاديمي',
    desc_en: 'A plan to address weaknesses and improve academic performance',
    btn_ar: 'أنشئ الخطة العلاجية', btn_en: 'Generate Remedial Plan',
    icon: Stethoscope, gradient: 'from-rose-500 to-orange-500',
    bg: 'bg-gradient-to-br from-rose-50 to-orange-50/50 dark:from-rose-950/20 dark:to-orange-950/10',
    border: 'border-rose-200/70 dark:border-rose-800/30',
    iconBg: 'bg-rose-100 dark:bg-rose-900/40 text-rose-600 dark:text-rose-400',
    stepBg: 'bg-rose-50/80 dark:bg-rose-950/10 border-rose-100 dark:border-rose-800/20',
    btnClass: 'from-rose-500 to-orange-500',
  },
  enrichment: {
    title_ar: 'الخطة الإثرائية', title_en: 'Enrichment Plan',
    desc_ar: 'خطة لتعزيز نقاط القوة وتطوير المهارات المتميزة',
    desc_en: 'A plan to strengthen talents and develop advanced skills',
    btn_ar: 'أنشئ الخطة الإثرائية', btn_en: 'Generate Enrichment Plan',
    icon: Rocket, gradient: 'from-emerald-500 to-teal-500',
    bg: 'bg-gradient-to-br from-emerald-50 to-teal-50/50 dark:from-emerald-950/20 dark:to-teal-950/10',
    border: 'border-emerald-200/70 dark:border-emerald-800/30',
    iconBg: 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-600 dark:text-emerald-400',
    stepBg: 'bg-emerald-50/80 dark:bg-emerald-950/10 border-emerald-100 dark:border-emerald-800/20',
    btnClass: 'from-emerald-500 to-teal-500',
  },
};

export const getTalentConfig = (value) => TALENT_OPTIONS.find(t => t.value === value) || { value, ar: value, en: value, color: 'bg-gray-100 text-gray-700 border-gray-200' };

export const HakimPlanCard = ({ type, plan, isRTL, loading, onGenerate, onExport }) => {
  const [stepsOpen, setStepsOpen] = useState(true);
  const cfg = PLAN_CONFIG[type];
  const Icon = cfg.icon;
  const hakimPose = loading ? HAKIM_POSES.thinking : HAKIM_POSES[type];
  const hasPlan = !!plan;

  return (
    <Card className={`border ${cfg.border} overflow-hidden`}>
      <div className={`relative ${cfg.bg}`}>
        <div className={`absolute top-0 left-0 right-0 h-1 bg-gradient-to-l ${cfg.gradient}`} />
        <div className="p-4 pt-5">
          <div className="flex items-start gap-3">
            <div className="w-14 h-14 rounded-2xl bg-white/80 dark:bg-gray-800/60 border border-white/50 dark:border-gray-700/50 shadow-sm flex items-center justify-center overflow-hidden flex-shrink-0">
              <img src={hakimPose} alt="حكيم" className={`w-12 h-12 object-contain ${loading ? 'animate-pulse' : ''}`}
                onError={(e) => { e.target.style.display = 'none'; }} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <div className={`w-7 h-7 rounded-lg ${cfg.iconBg} flex items-center justify-center flex-shrink-0`}>
                  <Icon className="h-4 w-4" />
                </div>
                <h4 className="font-bold text-sm font-cairo">{isRTL ? cfg.title_ar : cfg.title_en}</h4>
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">{isRTL ? cfg.desc_ar : cfg.desc_en}</p>
              {!hasPlan && !loading && (
                <Button onClick={onGenerate} size="sm"
                  className={`mt-3 bg-gradient-to-r ${cfg.btnClass} hover:opacity-90 text-white gap-1.5 text-xs h-8 shadow-sm`}>
                  <Sparkles className="h-3.5 w-3.5" />
                  {isRTL ? cfg.btn_ar : cfg.btn_en}
                </Button>
              )}
              {loading && (
                <div className="flex items-center gap-2 mt-3">
                  <Loader2 className="h-4 w-4 animate-spin text-brand-purple" />
                  <span className="text-xs text-muted-foreground font-tajawal">{isRTL ? 'حكيم يحلل ويُعد الخطة...' : 'Hakim is preparing the plan...'}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
      {hasPlan && (
        <>
          <button onClick={() => setStepsOpen(!stepsOpen)}
            className="w-full flex items-center justify-between px-4 py-2.5 border-t border-b border-border/30 bg-muted/20 hover:bg-muted/40 transition-colors">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium font-cairo">{plan.title || (isRTL ? cfg.title_ar : cfg.title_en)}</span>
              {plan.steps && <span className="text-[10px] text-muted-foreground">({plan.steps.length} {isRTL ? 'خطوات' : 'steps'})</span>}
            </div>
            <div className="flex items-center gap-1">
              {onExport && (
                <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); onExport(type); }}
                  className="h-6 px-2 text-[10px] gap-1 text-brand-turquoise hover:text-brand-turquoise">
                  <Download className="h-3 w-3" /> {isRTL ? 'تصدير' : 'Export'}
                </Button>
              )}
              <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); onGenerate(); }}
                className="h-6 px-2 text-[10px] gap-1 text-brand-purple hover:text-brand-purple">
                <Sparkles className="h-3 w-3" /> {isRTL ? 'إعادة' : 'Redo'}
              </Button>
              {stepsOpen ? <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
            </div>
          </button>
          {stepsOpen && (
            <CardContent className="p-4 space-y-2.5">
              {plan.summary && <p className="text-xs text-muted-foreground bg-muted/30 p-2.5 rounded-lg leading-relaxed font-tajawal">{plan.summary}</p>}
              {plan.steps?.map((step, i) => (
                <div key={i} className={`p-3 rounded-xl border ${cfg.stepBg}`}>
                  <div className="flex items-start gap-3">
                    <div className={`w-6 h-6 rounded-full ${cfg.iconBg} flex items-center justify-center flex-shrink-0 text-xs font-bold mt-0.5`}>{i + 1}</div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-sm font-cairo">{step.title}</p>
                      <p className="text-xs text-muted-foreground mt-1 leading-relaxed">{step.description}</p>
                      <div className="flex flex-wrap items-center gap-3 mt-2">
                        {step.duration && <span className="flex items-center gap-1 text-[11px] text-muted-foreground"><Clock className="h-3 w-3" /> {step.duration}</span>}
                        {step.responsible && <span className="flex items-center gap-1 text-[11px] text-muted-foreground"><User className="h-3 w-3" /> {step.responsible}</span>}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
              {plan.expected_outcome && (
                <div className="flex items-start gap-2 p-3 bg-blue-50/50 dark:bg-blue-950/10 rounded-xl border border-blue-100 dark:border-blue-800/20">
                  <Target className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-xs font-medium text-blue-700 dark:text-blue-300 font-cairo">{isRTL ? 'النتيجة المتوقعة' : 'Expected Outcome'}</p>
                    <p className="text-xs text-blue-600/80 dark:text-blue-400/80 mt-0.5">{plan.expected_outcome}</p>
                  </div>
                </div>
              )}
            </CardContent>
          )}
        </>
      )}
    </Card>
  );
};

export const StatCard = ({ icon: Icon, value, label, color, bg, loading }) => (
  <div className={`flex flex-col items-center justify-center p-3 rounded-xl ${bg} min-w-[100px]`}>
    {loading ? (
      <>
        <Skeleton className="h-4 w-4 mb-1.5 rounded-full" />
        <Skeleton className="h-6 w-10 mb-1" />
        <Skeleton className="h-3 w-16" />
      </>
    ) : (
      <>
        <Icon className={`h-4 w-4 mb-1 ${color}`} />
        <p className={`text-lg font-bold font-cairo tabular-nums ${color}`}>{value ?? '-'}</p>
        <p className="text-[10px] text-muted-foreground font-cairo leading-tight text-center">{label}</p>
      </>
    )}
  </div>
);

export const EmptyState = ({ icon: Icon, message, actionLabel, onAction }) => (
  <div className="text-center py-8">
    <div className="w-16 h-16 mx-auto mb-3 rounded-full bg-muted/40 flex items-center justify-center">
      <Icon className="h-8 w-8 text-muted-foreground/30" />
    </div>
    <p className="text-sm text-muted-foreground font-cairo">{message}</p>
    {actionLabel && onAction && (
      <Button variant="outline" size="sm" className="mt-3 font-cairo" onClick={onAction}>
        <Plus className="h-3.5 w-3.5 me-1" /> {actionLabel}
      </Button>
    )}
  </div>
);

export const DataField = ({ label, value, icon: Icon, empty }) => (
  <div className="space-y-1">
    <p className="text-[11px] text-muted-foreground font-cairo">{label}</p>
    {value ? (
      <p className="text-sm font-medium flex items-center gap-1.5">
        {Icon && <Icon className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />}
        {value}
      </p>
    ) : (
      <p className="text-sm text-muted-foreground/60 italic font-cairo">{empty || '—'}</p>
    )}
  </div>
);
