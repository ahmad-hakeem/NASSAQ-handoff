import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTheme } from '../contexts/ThemeContext';
import { Footer } from '../components/layout/Footer';
import { HakimAssistant } from '../components/hakim/HakimAssistant';
import { Button } from '../components/ui/button';
import {
  ArrowLeft, ArrowRight, Zap, Sparkles, CheckCircle2, Check,
  ClipboardList, Activity, Brain, Send, Award, Star,
  Calendar, BookOpen, Users, TrendingUp, Bell, Download,
  FileText, MessageCircle,
  GraduationCap, AlertTriangle, Target, Lightbulb,
} from 'lucide-react';

const BG_PATTERN = '/nassaq-pattern.png';

const WORKFLOW_STEPS = [
  {
    num: '01',
    icon: ClipboardList,
    ar: 'تسجيل الحضور',
    arDesc: 'يتم توثيقه بشكل رقمي أثناء الحصة — لا وقت مهدر، لا أوراق.',
    en: 'Attendance Recording',
    enDesc: 'Digitally logged during class — no wasted time, no paper.',
  },
  {
    num: '02',
    icon: Activity,
    ar: 'رصد التفاعل والسلوك',
    arDesc: 'المشاركة والأداء موثّقة تلقائياً كل يوم.',
    en: 'Interaction & Behaviour',
    enDesc: 'Participation and performance auto-documented every day.',
  },
  {
    num: '03',
    icon: Brain,
    ar: 'توصيات حكيم',
    arDesc: 'اعرف من يحتاج تدخلك قبل نهاية اليوم — مرتبة بالأولوية.',
    en: 'Hakim Recommendations',
    enDesc: 'Know who needs your attention before the day ends — ranked by priority.',
  },
  {
    num: '04',
    icon: MessageCircle,
    ar: 'تواصل مع أولياء الأمور',
    arDesc: 'أرسل تنبيهات فورية لأولياء الأمور بضغطة واحدة — أكاديمي أو سلوكي.',
    en: 'Parent Communication',
    enDesc: 'Send instant alerts to parents in one tap — academic or behavioural.',
  },
  {
    num: '05',
    icon: Award,
    ar: 'ملف إنجاز يبنى تلقائياً',
    arDesc: 'كل حصة تُضيف سجلاً — الملف جاهز للتصدير في أي وقت.',
    en: 'Auto-Built Achievement File',
    enDesc: 'Every lesson adds a record — the file is always ready to export.',
  },
];

const ACHIEVEMENT_RECORDS = [
  {
    date: '١٢ مايو', dateEn: '12 May',
    subject: 'خطة توزيع المنهج الدراسي', subjectEn: 'Curriculum distribution plan',
    note: 'تم إرفاق الخطة الزمنية للفصل الدراسي الأول', noteEn: 'Term-one timeline attached',
    tag: 'تحضير', tagEn: 'Planning', tagColor: 'bg-brand-turquoise/10 text-teal-700',
    icon: FileText,
  },
  {
    date: '١١ مايو', dateEn: '11 May',
    subject: 'تحليل نتائج الاختبارات', subjectEn: 'Assessment results analysis',
    note: 'تقرير مفصل عن نقاط القوة والضعف للطلاب', noteEn: 'Detailed report on student strengths & gaps',
    tag: 'تقييم', tagEn: 'Assessment', tagColor: 'bg-brand-purple/10 text-brand-purple',
    icon: TrendingUp,
  },
  {
    date: '١٠ مايو', dateEn: '10 May',
    subject: 'تقييم شفهي', subjectEn: 'Oral assessment',
    note: 'استراتيجيات تدريس تفاعلية موثقة', noteEn: 'Documented interactive teaching strategies',
    tag: 'شاهد', tagEn: 'Evidence', tagColor: 'bg-emerald-500/10 text-emerald-600',
    icon: MessageCircle,
  },
  {
    date: '٩ مايو', dateEn: '9 May',
    subject: 'شهادة حضور دورة تدريبية', subjectEn: 'Training course certificate',
    note: 'التطوير المهني المستمر', noteEn: 'Continuous professional development',
    tag: 'تطوير', tagEn: 'Development', tagColor: 'bg-amber-500/10 text-amber-700',
    icon: Award,
  },
];

const ALERT_TYPES = [
  { ar: 'أكاديمي', en: 'Academic', icon: BookOpen, color: 'bg-brand-navy/10 text-brand-navy border-brand-navy/20' },
  { ar: 'سلوكي', en: 'Behavioural', icon: AlertTriangle, color: 'bg-amber-500/10 text-amber-600 border-amber-200' },
  { ar: 'إنجاز', en: 'Achievement', icon: Star, color: 'bg-brand-turquoise/10 text-brand-turquoise border-brand-turquoise/20' },
  { ar: 'خطة تحسين', en: 'Improvement Plan', icon: Target, color: 'bg-brand-purple/10 text-brand-purple border-brand-purple/20' },
];

const MONTHLY_FEATURES = [
  { ar: 'توصيات حكيم اليومية', en: 'Daily Hakim recommendations' },
  { ar: 'التنبيهات الفورية لأولياء الأمور', en: 'Instant parent alerts' },
  { ar: 'متابعة الطلاب', en: 'Student tracking' },
  { ar: 'ملف الإنجاز التلقائي', en: 'Auto achievement file' },
  { ar: 'كشف متابعة رقمي قابل للتصدير', en: 'Exportable digital roster' },
  { ar: 'تنظيم العمل اليومي', en: 'Daily work organisation' },
  { ar: 'رصد التفاعل والسلوك', en: 'Interaction & behaviour tracking' },
  { ar: 'التدخلات المقترحة', en: 'Suggested interventions' },
];

export const TeacherExperiencePage = () => {
  const { isRTL } = useTheme();
  const [activeAlertType, setActiveAlertType] = useState(0);
  const showTeacherPricing = false;

  const ar = (a, e) => isRTL ? a : e;

  return (
    <div className="min-h-screen" dir={isRTL ? 'rtl' : 'ltr'} data-testid="teacher-experience-page">
      {/* Header lives in the shared <PublicShell>; the old breadcrumb
          bar was removed as part of the unified two-tab navigation. */}

      {/* ── HERO — navy + nassaq texture ──────────────────────── */}
      <section className="relative bg-brand-navy overflow-hidden py-20 lg:py-28">
        <div
          className="absolute inset-0 bg-cover bg-center opacity-[0.07]"
          style={{ backgroundImage: `url('/nassaq-background.png')` }}
          aria-hidden="true"
        />
        <div className="absolute inset-0 bg-brand-navy/60" aria-hidden="true" />
        <div className="absolute top-0 left-0 w-[500px] h-[500px] rounded-full bg-brand-turquoise/8 blur-[120px]" aria-hidden="true" />
        <div className="absolute bottom-0 right-0 w-[400px] h-[400px] rounded-full bg-brand-purple/8 blur-[100px]" aria-hidden="true" />

        <div className="relative max-w-7xl mx-auto px-6 grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          {/* Copy */}
          <div className={`space-y-6 ${isRTL ? '' : 'order-2'}`}>
            {/* eyebrow */}
            <div className="inline-flex items-center gap-2.5 bg-brand-turquoise/15 border border-brand-turquoise/30 rounded-full px-5 py-2.5 backdrop-blur-sm">
              <Zap className="h-4 w-4 text-brand-turquoise animate-pulse" strokeWidth={1.5} aria-hidden="true" />
              <span className="font-tajawal text-sm text-brand-turquoise font-medium">
                {ar('للمعلم المستقل · Teacher Experience', 'Independent Teacher · Teacher Experience')}
              </span>
            </div>

            <h1 className="font-cairo font-bold text-white text-5xl md:text-6xl lg:text-7xl leading-none tracking-tight">
              نَسَّق
            </h1>

            <p className="font-tajawal text-lg text-white/75 leading-relaxed max-w-xl">
              {ar(
                'نسّق يتولى المتابعة والتنظيم — حتى تركّز على ما يهم فعلاً: علاقتك بطلابك.',
                'NASSAQ handles the tracking and organisation — so you focus on what truly matters: your relationship with your students.'
              )}
            </p>

            {/* CTAs */}
            <div className="flex flex-wrap items-center gap-3 pt-2">
              <Link
                to="/teacher-register"
                className="inline-flex items-center gap-2 font-cairo font-bold text-base px-8 py-3 rounded-lg bg-brand-turquoise hover:bg-brand-turquoise-light text-white shadow-lg hover:shadow-xl hover:-translate-y-0.5 active:scale-95 transition-all"
              >
                {ar('ابدأ تجربتك كمعلم', 'Start as a teacher')}
                {isRTL ? <ArrowLeft className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" /> : <ArrowRight className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />}
              </Link>
              <a
                href="#workflow"
                className="inline-flex items-center gap-2 font-tajawal text-sm font-medium px-6 py-3 rounded-lg border-2 border-white/25 text-white hover:bg-white/10 hover:border-white/40 transition-all"
              >
                {ar('شاهد كيف يعمل', 'See how it works')}
              </a>
            </div>

            {/* Trust badges */}
            <div className="flex flex-wrap items-center gap-4 pt-2">
              {[
                { icon: CheckCircle2, ar: 'بدون إعداد معقد', en: 'Zero setup' },
                { icon: CheckCircle2, ar: 'يعمل من اليوم الأول', en: 'Works day one' },
                { icon: CheckCircle2, ar: 'شهر مجاني كامل', en: 'Full month free' },
              ].map(({ icon: I, ar: a, en: e }, i) => (
                <span key={i} className="flex items-center gap-1.5 text-white/60 font-tajawal text-xs">
                  <I className="h-3.5 w-3.5 text-brand-turquoise" strokeWidth={2} aria-hidden="true" />
                  {ar(a, e)}
                </span>
              ))}
            </div>
          </div>

          {/* Real teacher dashboard preview */}
          <div className={`${isRTL ? '' : 'order-1'}`}>
            <img
              src="/teacher-dashboard-preview.png"
              alt={ar('معاينة لوحة المعلم في نَسَّق', 'Preview of the NASSAQ teacher dashboard')}
              className="w-full h-auto rounded-2xl border border-white/10 shadow-2xl bg-white/5 backdrop-blur-sm"
              loading="lazy"
            />
          </div>
        </div>
      </section>

      {/* ── WORKFLOW — light bg ────────────────────────────────── */}
      <section
        id="workflow"
        className="py-24 lg:py-32 bg-gradient-to-b from-background via-background to-background relative overflow-hidden scroll-mt-24"
      >
        <div className="absolute inset-0 opacity-[0.02]" style={{ backgroundImage: `url(${BG_PATTERN})`, backgroundSize: '200% auto' }} aria-hidden="true" />
        <div className="absolute top-0 left-0 w-[500px] h-[500px] rounded-full bg-brand-turquoise/5 blur-[120px] animate-pulse" style={{ animationDuration: '8s' }} aria-hidden="true" />
        <div className="absolute bottom-0 right-0 w-[400px] h-[400px] rounded-full bg-brand-purple/5 blur-[100px] animate-pulse" style={{ animationDelay: '2s', animationDuration: '8s' }} aria-hidden="true" />

        <div className="relative max-w-5xl mx-auto px-6">
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2.5 bg-gradient-to-r from-brand-turquoise/15 to-brand-turquoise/5 border border-brand-turquoise/25 rounded-full px-5 py-2.5 mb-6 backdrop-blur-sm">
              <Zap className="h-4 w-4 text-brand-turquoise animate-pulse" strokeWidth={1.5} aria-hidden="true" />
              <span className="text-brand-turquoise text-sm font-tajawal font-medium">{ar('سير العمل اليومي', 'Daily workflow')}</span>
            </div>
            <h2 className="font-cairo font-black text-foreground text-3xl md:text-5xl lg:text-[3.5rem] leading-tight mb-5">
              {ar(
                <>كيف يعمل <span className="text-brand-turquoise">معلّم نسّق</span> خلال يومك؟</>,
                <>How does <span className="text-brand-turquoise">NASSAQ Teacher</span> work through your day?</>
              )}
            </h2>
            <p className="text-lg text-muted-foreground font-tajawal max-w-2xl mx-auto leading-relaxed">
              {ar('خمس خطوات تغطي يومك الدراسي كاملاً.', 'Five steps that cover your entire school day.')}
            </p>
          </div>

          <div className="grid md:grid-cols-5 gap-4">
            {WORKFLOW_STEPS.map((step, i) => {
              const Icon = step.icon;
              return (
                <div
                  key={i}
                  className="relative flex flex-col items-center text-center p-6 bg-card/80 border border-border/50 rounded-2xl hover:border-brand-turquoise/40 hover:shadow-lg hover:-translate-y-0.5 transition-all group"
                >
                  {/* connector line (desktop) */}
                  {i < WORKFLOW_STEPS.length - 1 && (
                    <div className={`hidden md:block absolute top-10 ${isRTL ? '-left-2' : '-right-2'} w-4 h-0.5 bg-border/60 z-10`} aria-hidden="true" />
                  )}
                  <div className="w-12 h-12 rounded-xl bg-brand-turquoise/10 flex items-center justify-center mb-3 group-hover:bg-brand-turquoise/15 transition-colors">
                    <Icon className="h-6 w-6 text-brand-turquoise" strokeWidth={1.5} aria-hidden="true" />
                  </div>
                  <span className="font-cairo text-xs font-bold text-brand-turquoise/60 mb-1">{step.num}</span>
                  <h3 className="font-cairo text-sm font-bold text-foreground mb-2">{ar(step.ar, step.en)}</h3>
                  <p className="font-tajawal text-xs text-muted-foreground leading-relaxed">{ar(step.arDesc, step.enDesc)}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ── ACHIEVEMENT FILE — navy ────────────────────────────── */}
      <section className="relative bg-brand-navy py-24 lg:py-32 overflow-hidden">
        <div
          className="absolute inset-0 bg-cover bg-center opacity-[0.05]"
          style={{ backgroundImage: `url('/nassaq-background.png')` }}
          aria-hidden="true"
        />
        <div className="absolute inset-0 bg-brand-navy/70" aria-hidden="true" />
        <div className="absolute top-0 left-0 w-[500px] h-[500px] rounded-full bg-brand-turquoise/6 blur-[120px] animate-pulse" style={{ animationDuration: '10s' }} aria-hidden="true" />
        <div className="absolute bottom-0 right-0 w-[400px] h-[400px] rounded-full bg-brand-purple/6 blur-[100px] animate-pulse" style={{ animationDelay: '2s', animationDuration: '8s' }} aria-hidden="true" />

        <div className="relative max-w-6xl mx-auto px-6 grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          {/* copy */}
          <div className="space-y-6">
            <div className="inline-flex items-center gap-2.5 bg-white/10 border border-white/20 rounded-full px-5 py-2.5">
              <FileText className="h-4 w-4 text-white" strokeWidth={1.5} aria-hidden="true" />
              <span className="text-white text-sm font-tajawal font-medium">{ar('ملف الإنجاز التلقائي', 'Auto Achievement File')}</span>
            </div>
            <div className="space-y-3">
              <h2 className="font-cairo font-black text-white text-4xl md:text-5xl lg:text-[3.75rem] leading-[1.05] tracking-tight">
                {ar('ملف إنجاز مهني', 'A professional portfolio')}
              </h2>
              <p className="font-cairo font-bold text-brand-turquoise text-2xl md:text-3xl lg:text-[2rem] leading-tight">
                {ar('يُبنى تلقائياً من اليوم الأول.', 'Built automatically from day one.')}
              </p>
            </div>
            <p className="font-tajawal text-white/65 text-base md:text-[1.0625rem] leading-relaxed max-w-lg pt-1">
              {ar(
                'وداعاً للورق والمجلدات. نَسَّق يقوم بجمع وتوثيق شواهدك اليومية، تحضيرك، وتقييماتك تلقائياً في ملف إنجاز احترافي جاهز للمشاركة مع الإدارة أو المشرفين في أي وقت.',
                'Goodbye to paper and folders. NASSAQ automatically gathers and documents your daily evidence, lesson plans, and assessments into a professional portfolio ready to share with administration or supervisors anytime.'
              )}
            </p>
            <ul className="space-y-3">
              {[
                { ar: 'توثيق آلي للشواهد — يُبنى تلقائياً من أنشطتك اليومية دون جهد إضافي.', en: 'Automatic evidence documentation — built from your daily activities with zero extra effort.' },
                { ar: 'تنظيم احترافي — تصنيف ذكي للخطط، التقييمات، والأنشطة اللامنهجية.', en: 'Professional organisation — smart classification of plans, assessments, and extracurriculars.' },
                { ar: 'استعراض شامل للأداء — يعكس تطورك المهني وتأثيرك الفعلي في الفصول.', en: 'Comprehensive performance overview — reflects your professional growth and real classroom impact.' },
                { ar: 'جاهز للطباعة والمشاركة — بضغطة واحدة، ملفك جاهز للتقييم أو الترقية.', en: 'Print- and share-ready — one tap and your file is ready for review or promotion.' },
              ].map((item, i) => (
                <li key={i} className="flex items-start gap-3 font-tajawal text-sm text-white/70">
                  <CheckCircle2 className="h-4 w-4 text-brand-turquoise shrink-0 mt-0.5" strokeWidth={2} aria-hidden="true" />
                  {ar(item.ar, item.en)}
                </li>
              ))}
            </ul>
          </div>

          {/* achievement file card */}
          <div aria-label={ar('ملف الإنجاز المهني — الأستاذ إبراهيم', 'Professional Portfolio — Mr Ibrahim')}>
            <div className="bg-white border border-slate-200/70 rounded-2xl overflow-hidden shadow-[0_20px_60px_-20px_rgba(2,12,46,0.45)] ring-1 ring-black/5">
              {/* card header */}
              <div className="px-5 py-4 border-b border-slate-200/80 flex items-center justify-between bg-gradient-to-b from-slate-50/60 to-white">
                <div>
                  <p className="font-cairo text-brand-navy font-bold text-base">{ar('ملف الإنجاز المهني — الأستاذ إبراهيم', 'Professional Portfolio — Mr Ibrahim')}</p>
                  <p className="font-tajawal text-slate-500 text-xs mt-0.5">{ar('الفصل الثاني · ١٤٤٦', 'Term 2 · 2024')}</p>
                </div>
                <button className="flex items-center gap-1.5 font-tajawal text-xs font-medium text-brand-navy border border-slate-200 rounded-lg px-3 py-1.5 hover:bg-slate-50 hover:border-slate-300 transition-colors">
                  <Download className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden="true" />
                  {ar('تصدير', 'Export')}
                </button>
              </div>

              {/* stats */}
              <div className="grid grid-cols-3 divide-x divide-slate-200/70 rtl:divide-x-reverse border-b border-slate-200/80 bg-white">
                {[
                  { value: '٤٥', label: ar('الشواهد المكتملة', 'Evidence completed'), accent: 'text-teal-700' },
                  { value: '١٢', label: ar('الأنشطة الموثقة', 'Documented activities'), accent: 'text-brand-navy' },
                  { value: ar('متميز', 'Excellent'), label: ar('التقييم العام', 'Overall rating'), accent: 'text-teal-700' },
                ].map((s, i) => (
                  <div key={i} className="py-4 px-3 text-center">
                    <p className={`font-cairo font-black text-xl ${s.accent}`}>{s.value}</p>
                    <p className="font-tajawal text-slate-600 text-xs mt-1">{s.label}</p>
                  </div>
                ))}
              </div>

              {/* records */}
              <div className="px-5 py-4 bg-white">
                <p className="font-tajawal text-slate-500 text-xs mb-3">{ar('آخر السجلات — تُبنى تلقائياً', 'Latest records — auto-built')}</p>
                <div className="space-y-1">
                  {ACHIEVEMENT_RECORDS.map((rec, i) => {
                    const Icon = rec.icon;
                    return (
                      <div key={i} className="flex items-center gap-3 py-2 border-b border-slate-100 last:border-0">
                        <div className="w-8 h-8 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-center shrink-0">
                          <Icon className="h-4 w-4 text-slate-500" strokeWidth={1.5} aria-hidden="true" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="font-cairo text-xs font-semibold text-brand-navy truncate">{ar(rec.subject, rec.subjectEn)}</p>
                          <p className="font-tajawal text-[11px] text-slate-600 truncate">{ar(rec.note, rec.noteEn)}</p>
                        </div>
                        <span className={`shrink-0 font-tajawal text-[10px] font-medium px-2 py-0.5 rounded-full ${rec.tagColor}`}>{ar(rec.tag, rec.tagEn)}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── PARENT COMMUNICATION — light ──────────────────────── */}
      <section className="py-24 lg:py-32 bg-gradient-to-b from-background via-background to-background relative overflow-hidden">
        <div className="absolute inset-0 opacity-[0.02]" style={{ backgroundImage: `url(${BG_PATTERN})`, backgroundSize: '200% auto' }} aria-hidden="true" />
        <div className="absolute top-0 right-0 w-[500px] h-[500px] rounded-full bg-brand-turquoise/5 blur-[120px] animate-pulse" style={{ animationDuration: '10s' }} aria-hidden="true" />
        <div className="absolute bottom-0 left-0 w-[400px] h-[400px] rounded-full bg-brand-purple/5 blur-[100px] animate-pulse" style={{ animationDelay: '2s', animationDuration: '8s' }} aria-hidden="true" />

        <div className="relative max-w-6xl mx-auto px-6 grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          {/* send form mockup */}
          <div>
            <div className="bg-card/80 border border-border/50 rounded-2xl overflow-hidden shadow-sm">
              {/* header */}
              <div className="px-5 py-4 border-b border-border/50 flex items-center justify-between">
                <div>
                  <p className="font-cairo font-bold text-foreground text-sm">{ar('إرسال تنبيه — نورة عبدالله', 'Send Alert — Nora Abdullah')}</p>
                  <p className="font-tajawal text-muted-foreground text-xs mt-0.5">{ar('مباشر', 'Live')}</p>
                </div>
                <Bell className="h-5 w-5 text-brand-turquoise" strokeWidth={1.5} aria-hidden="true" />
              </div>

              {/* alert type selector */}
              <div className="px-5 py-4 border-b border-border/50">
                <p className="font-tajawal text-xs text-muted-foreground mb-3">{ar('نوع التنبيه', 'Alert type')}</p>
                <div className="flex flex-wrap gap-2">
                  {ALERT_TYPES.map((t, i) => {
                    const Icon = t.icon;
                    return (
                      <button
                        key={i}
                        onClick={() => setActiveAlertType(i)}
                        className={`flex items-center gap-1.5 font-tajawal text-xs px-3 py-1.5 rounded-lg border transition-all ${
                          activeAlertType === i
                            ? `${t.color} shadow-sm`
                            : 'bg-muted/50 text-muted-foreground border-border/50 hover:bg-muted'
                        }`}
                      >
                        <Icon className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden="true" />
                        {ar(t.ar, t.en)}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* message preview */}
              <div className="px-5 py-4 border-b border-border/50">
                <p className="font-tajawal text-xs text-muted-foreground mb-2">{ar('معاينة الرسالة', 'Message preview')}</p>
                <div className="bg-slate-50 rounded-xl p-3 font-tajawal text-sm text-foreground/80 leading-relaxed border border-border/30">
                  {ar(
                    'عزيزي ولي أمر نورة، لاحظنا تراجعاً في تفاعل نورة خلال الأسابيع الثلاثة الماضية. نقترح جلسة متابعة.',
                    "Dear Nora's guardian, we've noticed a decline in Nora's engagement over the past three weeks. We suggest a follow-up session."
                  )}
                </div>
              </div>

              {/* hakim suggestion */}
              <div className="px-5 py-3 border-b border-border/50 flex items-start gap-2.5">
                <div className="w-6 h-6 rounded-full bg-brand-purple flex items-center justify-center font-cairo font-bold text-[10px] text-white shrink-0 mt-0.5">ح</div>
                <p className="font-tajawal text-xs text-muted-foreground leading-relaxed">
                  <span className="text-brand-purple font-bold font-cairo">{ar('حكيم: ', 'Hakim: ')}</span>
                  {ar('أضف اقتراح خطة تحسين لتقليص الفجوة في الأسبوعين القادمين.', 'Add an improvement plan suggestion to close the gap over the next two weeks.')}
                </p>
              </div>

              {/* send button */}
              <div className="px-5 py-4">
                <button className="w-full flex items-center justify-center gap-2 bg-brand-navy text-white font-cairo font-bold text-sm py-3 rounded-lg hover:bg-brand-navy-light shadow-sm hover:shadow-md transition-all active:scale-[0.98]">
                  <Send className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />
                  {ar('إرسال التنبيه الآن', 'Send alert now')}
                </button>
                <p className="text-center font-tajawal text-xs text-muted-foreground mt-2">
                  {ar('تجربة مجانية لمدة شهر كامل — بدون بطاقة ائتمان', 'Free trial for a full month — no credit card')}
                </p>
              </div>
            </div>
          </div>

          {/* copy */}
          <div className="space-y-6">
            <div className="inline-flex items-center gap-2.5 bg-gradient-to-r from-brand-turquoise/15 to-brand-turquoise/5 border border-brand-turquoise/25 rounded-full px-5 py-2.5">
              <MessageCircle className="h-4 w-4 text-brand-turquoise" strokeWidth={1.5} aria-hidden="true" />
              <span className="text-brand-turquoise text-sm font-tajawal font-medium">{ar('التواصل مع أولياء الأمور', 'Parent communication')}</span>
            </div>
            <h2 className="font-cairo font-black text-foreground text-3xl md:text-5xl lg:text-[3.5rem] leading-tight">
              {ar(
                <>تنبيهات فورية<br /><span className="text-brand-turquoise">بضغطة واحدة.</span></>,
                <>Instant alerts<br /><span className="text-brand-turquoise">in one tap.</span></>
              )}
            </h2>
            <p className="font-tajawal text-muted-foreground text-lg leading-relaxed max-w-lg">
              {ar(
                'أرسل تنبيهات أكاديمية وسلوكية مباشرة لأولياء الأمور — مشاركة التقدم، الملاحظات السريعة، وخطط التحسين المقترحة.',
                'Send academic and behavioural alerts directly to parents — share progress, quick notes, and suggested improvement plans.'
              )}
            </p>
            <div className="grid grid-cols-2 gap-3">
              {[
                { icon: BookOpen, ar: 'تنبيه أكاديمي', en: 'Academic alert', desc: ar('تراجع في أداء نورة', 'Decline in Nora\'s performance') },
                { icon: Star, ar: 'ملاحظة سريعة', en: 'Quick note', desc: ar('مشاركة ممتازة لأحمد', 'Ahmed\'s excellent participation') },
                { icon: GraduationCap, ar: 'إنجاز الطالب', en: 'Student achievement', desc: ar('خالد أكمل المشروع امتياز', 'Khalid completed project with distinction') },
                { icon: Lightbulb, ar: 'خطة تحسين', en: 'Improvement plan', desc: ar('مقترح حكيم: جلسة دعم', 'Hakim suggestion: support session') },
              ].map((item, i) => {
                const Icon = item.icon;
                return (
                  <div key={i} className="bg-card/80 border border-border/50 rounded-xl p-3 hover:border-brand-turquoise/30 hover:shadow-sm transition-all">
                    <div className="w-8 h-8 rounded-lg bg-brand-turquoise/10 flex items-center justify-center mb-2">
                      <Icon className="h-4 w-4 text-brand-turquoise" strokeWidth={1.5} aria-hidden="true" />
                    </div>
                    <p className="font-cairo text-xs font-bold text-foreground mb-1">{ar(item.ar, item.en)}</p>
                    <p className="font-tajawal text-[11px] text-muted-foreground">{item.desc}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      {/* ── PRICING — navy ────────────────────────────────────── */}
      {showTeacherPricing && (
      <section className="relative bg-brand-navy py-24 lg:py-32 overflow-hidden">
        <div
          className="absolute inset-0 bg-cover bg-center opacity-[0.05]"
          style={{ backgroundImage: `url('/nassaq-background.png')` }}
          aria-hidden="true"
        />
        <div className="absolute inset-0 bg-brand-navy/70" aria-hidden="true" />
        <div className="absolute top-0 left-0 w-[500px] h-[500px] rounded-full bg-brand-turquoise/5 blur-3xl animate-pulse" style={{ animationDuration: '10s' }} aria-hidden="true" />
        <div className="absolute bottom-0 right-0 w-[400px] h-[400px] rounded-full bg-brand-purple/5 blur-3xl animate-pulse" style={{ animationDelay: '2s', animationDuration: '8s' }} aria-hidden="true" />

        <div className="relative max-w-4xl mx-auto px-6">
          <div className="text-center mb-14">
            <div className="inline-flex items-center gap-2 bg-white/10 border border-white/25 rounded-full px-5 py-2 mb-6">
              <Award className="h-4 w-4 text-white" strokeWidth={1.5} aria-hidden="true" />
              <span className="font-tajawal text-sm font-medium text-white">{ar('خطتك كمعلم', 'Your teacher plan')}</span>
            </div>
            <h2 className="font-cairo font-black text-white text-3xl md:text-5xl leading-tight mb-4">
              {ar('بسيطة، واضحة، بدون تعقيد.', 'Simple, clear, no complexity.')}
            </h2>
          </div>

          <div className="grid md:grid-cols-2 gap-6 max-w-2xl mx-auto">
            {/* Monthly */}
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-7 flex flex-col hover:border-white/20 hover:bg-white/8 transition-all">
              <p className="font-cairo font-bold text-white/70 text-sm mb-4">{ar('الخطة الشهرية', 'Monthly plan')}</p>
              <div className="flex items-end gap-1 mb-1">
                <span className="font-cairo font-black text-white text-5xl">٢٩</span>
                <span className="font-tajawal text-white/50 text-sm mb-2">{ar('ريال / شهر', 'SAR / month')}</span>
              </div>
              <p className="font-tajawal text-white/40 text-xs mb-6">{ar('بعد شهر التجربة المجاني', 'After the free trial month')}</p>
              <ul className="space-y-2.5 mb-8 flex-1">
                {MONTHLY_FEATURES.map((f, i) => (
                  <li key={i} className="flex items-center gap-2.5 font-tajawal text-sm text-white/70">
                    <Check className="h-4 w-4 text-brand-turquoise shrink-0" strokeWidth={2} aria-hidden="true" />
                    {ar(f.ar, f.en)}
                  </li>
                ))}
              </ul>
              <Link
                to="/teacher-register"
                className="block text-center font-cairo font-bold text-sm py-3 rounded-lg border-2 border-white/20 text-white hover:bg-white/10 hover:border-white/30 transition-all active:scale-[0.98]"
              >
                {ar('ابدأ تجربتك المجانية', 'Start your free trial')}
              </Link>
            </div>

            {/* Annual — highlighted */}
            <div className="relative bg-white/10 backdrop-blur-sm border border-brand-turquoise/40 rounded-2xl p-7 flex flex-col shadow-2xl shadow-brand-turquoise/10 scale-[1.02]">
              {/* recommended badge */}
              <div className="absolute -top-3 inset-x-0 flex justify-center">
                <span className="bg-gradient-to-r from-brand-turquoise to-cyan-500 text-white font-cairo text-xs font-bold px-4 py-1 rounded-full shadow-lg shadow-brand-turquoise/30">
                  {ar('الأوفر', 'Best value')}
                </span>
              </div>
              <p className="font-cairo font-bold text-white text-sm mb-4">{ar('الخطة السنوية', 'Annual plan')}</p>
              <div className="flex items-end gap-1 mb-1">
                <span className="font-cairo font-black text-brand-turquoise text-5xl">١٩٩</span>
                <span className="font-tajawal text-white/50 text-sm mb-2">{ar('ريال / سنة', 'SAR / year')}</span>
              </div>
              <p className="font-tajawal text-white/40 text-xs mb-6">{ar('أي ١٦.٦ ريال شهرياً — بعد شهر التجربة', 'Just 16.6 SAR/month — after the free trial')}</p>
              <ul className="space-y-2.5 mb-8 flex-1">
                {MONTHLY_FEATURES.map((f, i) => (
                  <li key={i} className="flex items-center gap-2.5 font-tajawal text-sm text-white/80">
                    <Check className="h-4 w-4 text-brand-turquoise shrink-0" strokeWidth={2} aria-hidden="true" />
                    {ar(f.ar, f.en)}
                  </li>
                ))}
              </ul>
              <Link
                to="/teacher-register"
                className="block text-center font-cairo font-bold text-sm py-3 rounded-lg bg-gradient-to-r from-brand-turquoise to-cyan-500 hover:from-brand-turquoise-light hover:to-cyan-400 text-white shadow-lg shadow-brand-turquoise/25 hover:shadow-xl transition-all active:scale-[0.98]"
              >
                {ar('ابدأ تجربتك المجانية', 'Start your free trial')}
              </Link>
            </div>
          </div>

          <p className="text-center font-tajawal text-sm text-white/40 mt-8">
            {ar('لا حاجة لبطاقة ائتمان · إلغاء في أي وقت · شهر مجاني كامل بجميع الميزات', 'No credit card · Cancel anytime · Full month free with all features')}
          </p>
        </div>
      </section>
      )}

      {/* ── FINAL CTA — light ─────────────────────────────────── */}
      <section className="py-24 lg:py-32 bg-gradient-to-b from-background via-background to-background relative overflow-hidden">
        <div className="absolute inset-0 opacity-[0.02]" style={{ backgroundImage: `url(${BG_PATTERN})`, backgroundSize: '200% auto' }} aria-hidden="true" />
        <div className="absolute top-0 left-0 w-[500px] h-[500px] rounded-full bg-brand-turquoise/5 blur-[120px] animate-pulse" style={{ animationDuration: '8s' }} aria-hidden="true" />
        <div className="absolute bottom-0 right-0 w-[400px] h-[400px] rounded-full bg-brand-purple/5 blur-[100px] animate-pulse" style={{ animationDelay: '2s', animationDuration: '8s' }} aria-hidden="true" />

        <div className="relative max-w-3xl mx-auto px-6 text-center">
          {/* hakim avatar */}
          <div className="flex justify-center mb-8">
            <div className="relative">
              <div className="absolute -inset-2 rounded-full bg-brand-turquoise/15 blur-xl animate-pulse" aria-hidden="true" />
              <img
                src="/hakim-poses/motivating.png"
                alt={ar('حكيم', 'Hakim')}
                className="hakim-img relative w-24 h-24 rounded-2xl object-contain border-2 border-brand-turquoise shadow-xl bg-gradient-to-br from-cyan-50 to-violet-50 p-1"
              />
            </div>
          </div>

          <div className="inline-flex items-center gap-2.5 bg-gradient-to-r from-brand-turquoise/15 to-brand-turquoise/5 border border-brand-turquoise/25 rounded-full px-5 py-2.5 mb-6 backdrop-blur-sm">
            <Sparkles className="h-4 w-4 text-brand-turquoise" strokeWidth={1.5} aria-hidden="true" />
            <span className="text-brand-turquoise text-sm font-tajawal font-medium">{ar('معلّم نسّق · للمعلم المستقل', 'NASSAQ Teacher · For independent teachers')}</span>
          </div>

          <h2 className="font-cairo font-black text-foreground text-3xl md:text-5xl lg:text-[3.5rem] leading-tight mb-5">
            {ar(
              <>وفّر ساعات المتابعة الإدارية<br /><span className="text-brand-turquoise">وركّز على ما يهم.</span></>,
              <>Save admin tracking hours<br /><span className="text-brand-turquoise">and focus on what matters.</span></>
            )}
          </h2>

          <p className="font-tajawal text-muted-foreground text-lg max-w-xl mx-auto leading-relaxed mb-10">
            {ar(
              'شهر مجاني كامل بجميع الميزات — بدون تعقيد تقني.',
              'A full free month with all features — no technical complexity.'
            )}
          </p>

          <div className="flex flex-wrap items-center justify-center gap-4">
            <Link
              to="/teacher-register"
              className="inline-flex items-center gap-2 font-cairo font-bold text-lg px-10 py-4 rounded-2xl bg-gradient-to-r from-brand-turquoise to-cyan-500 hover:from-brand-turquoise-light hover:to-cyan-400 text-white shadow-2xl shadow-brand-turquoise/30 hover:shadow-brand-turquoise/40 transition-all hover:scale-[1.03] active:scale-[0.98]"
              data-testid="teacher-final-cta"
            >
              {ar('ابدأ تجربتك كمعلم', 'Start as a teacher')}
              {isRTL ? <ArrowLeft className="h-5 w-5" strokeWidth={1.5} aria-hidden="true" /> : <ArrowRight className="h-5 w-5" strokeWidth={1.5} aria-hidden="true" />}
            </Link>
            <Link
              to="/"
              className="inline-flex items-center gap-2 font-tajawal text-sm font-medium px-6 py-3 rounded-lg border border-border text-foreground hover:bg-muted hover:text-foreground transition-all"
            >
              {ar('استكشف نسّق للمؤسسات', 'Explore NASSAQ for institutions')}
            </Link>
          </div>
        </div>
      </section>

      <Footer />
      <HakimAssistant />
    </div>
  );
};

export default TeacherExperiencePage;
