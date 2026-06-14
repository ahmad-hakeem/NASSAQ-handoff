import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useTheme, useTranslation } from '../contexts/ThemeContext';
import { Footer } from '../components/layout/Footer';
import { HakimAssistant } from '../components/hakim/HakimAssistant';
import {
  ArrowLeft, ArrowRight, Zap, Sparkles, CheckCircle2, Check,
  ClipboardList, Activity, Brain, Send, Award, Star,
  BookOpen, TrendingUp, Bell, Download,
  FileText, MessageCircle,
  GraduationCap, AlertTriangle, Target, Lightbulb,
  HelpCircle, ChevronDown,
} from 'lucide-react';

const BG_PATTERN = '/nassaq-pattern.png';

const WORKFLOW_STEPS = [
  { num: '01', icon: ClipboardList },
  { num: '02', icon: Activity },
  { num: '03', icon: Brain },
  { num: '04', icon: MessageCircle },
  { num: '05', icon: Award },
];

const ACHIEVEMENT_RECORDS = [
  { tagColor: 'bg-brand-turquoise/10 text-teal-700', icon: FileText },
  { tagColor: 'bg-brand-purple/10 text-brand-purple', icon: TrendingUp },
  { tagColor: 'bg-emerald-500/10 text-emerald-600', icon: MessageCircle },
  { tagColor: 'bg-amber-500/10 text-amber-700', icon: Award },
];

const ALERT_TYPES = [
  { icon: BookOpen, color: 'bg-brand-navy/10 text-brand-navy border-brand-navy/20' },
  { icon: AlertTriangle, color: 'bg-amber-500/10 text-amber-600 border-amber-200' },
  { icon: Star, color: 'bg-brand-turquoise/10 text-brand-turquoise border-brand-turquoise/20' },
  { icon: Target, color: 'bg-brand-purple/10 text-brand-purple border-brand-purple/20' },
];

const PLAN_FEATURE_COUNT = 8;

const PARENT_COMM_CARDS = [
  { icon: BookOpen },
  { icon: Star },
  { icon: GraduationCap },
  { icon: Lightbulb },
];

export const TeacherExperiencePage = () => {
  const { isRTL } = useTheme();
  const { t } = useTranslation();
  const [activeAlertType, setActiveAlertType] = useState(0);
  const [faqExpanded, setFaqExpanded] = useState(false);
  const showTeacherPricing = false;
  const FAQ_COLLAPSED_COUNT = 5;
  const FAQ_TOTAL = 15;

  return (
    <div className="min-h-screen" dir={isRTL ? 'rtl' : 'ltr'} data-testid="teacher-experience-page">
      {/* Header lives in the shared <PublicShell>; the old breadcrumb
          bar was removed as part of the unified two-tab navigation. */}

      {/* ── HERO — navy + nassaq texture ──────────────────────── */}
      <section className="relative bg-brand-navy overflow-hidden py-20 lg:py-28">
        {/* Brand background image */}
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: `url('/nassaq-background.png')` }}
          aria-hidden="true"
        />
        {/* Subtle pattern overlay */}
        <div
          className="absolute inset-0 opacity-[0.08]"
          style={{ backgroundImage: `url(${BG_PATTERN})`, backgroundSize: '200% auto', backgroundPosition: 'center top' }}
          aria-hidden="true"
        />
        {/* Navy tint to lock in contrast */}
        <div className="absolute inset-0 bg-brand-navy/70" aria-hidden="true" />
        <div className="absolute top-0 left-0 w-[500px] h-[500px] rounded-full bg-brand-turquoise/8 blur-[120px]" aria-hidden="true" />
        <div className="absolute bottom-0 right-0 w-[400px] h-[400px] rounded-full bg-brand-purple/8 blur-[100px]" aria-hidden="true" />

        <div className="relative max-w-7xl mx-auto px-6 grid lg:grid-cols-2 gap-12 lg:gap-16 lg:items-stretch">
          {/* Copy — distributed top → bottom so the column shares the same
              top/bottom boundary as the visual column (balanced 50/50). */}
          <div className={`flex flex-col justify-between gap-8 ${isRTL ? '' : 'order-2'}`}>
            {/* TOP GROUP: eyebrow + headline + subheading */}
            <div className="space-y-6">
              {/* eyebrow */}
              <div className="inline-flex items-center gap-2.5 bg-brand-turquoise/15 border border-brand-turquoise/30 rounded-full px-5 py-2.5 backdrop-blur-sm">
                <Zap className="h-4 w-4 text-brand-turquoise animate-pulse" strokeWidth={1.5} aria-hidden="true" />
                <span className="font-tajawal text-sm text-brand-turquoise font-medium">
                  {t('teacherExpHeroEyebrow')}
                </span>
              </div>

              <h1 className="font-cairo font-bold text-white text-5xl md:text-6xl lg:text-7xl leading-none tracking-tight">
                {t('teacherExpBrand')}
              </h1>

              <p className="font-tajawal text-lg text-white/75 leading-relaxed max-w-xl">
                {t('teacherExpHeroSubheading')}
              </p>
            </div>

            {/* MIDDLE GROUP: CTAs */}
            <div className="flex flex-wrap items-center gap-3">
              <Link
                to="/teacher-register"
                className="inline-flex items-center gap-2 font-cairo font-bold text-base px-8 py-3 rounded-lg bg-brand-turquoise hover:bg-brand-turquoise-light text-white shadow-lg hover:shadow-xl hover:-translate-y-0.5 active:scale-95 transition-all"
              >
                {t('teacherExpHeroCtaPrimary')}
                {isRTL ? <ArrowLeft className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" /> : <ArrowRight className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />}
              </Link>
              <a
                href="#workflow"
                className="inline-flex items-center gap-2 font-tajawal text-sm font-medium px-6 py-3 rounded-lg border-2 border-white/25 text-white hover:bg-white/10 hover:border-white/40 transition-all"
              >
                {t('teacherExpHeroCtaSecondary')}
              </a>
            </div>

            {/* BOTTOM GROUP: trust badges */}
            <div className="flex flex-wrap items-center gap-4">
              {[1, 2, 3].map((n) => (
                <span key={n} className="flex items-center gap-1.5 text-white/60 font-tajawal text-xs">
                  <CheckCircle2 className="h-3.5 w-3.5 text-brand-turquoise" strokeWidth={2} aria-hidden="true" />
                  {t(`teacherExpTrustBadge${n}`)}
                </span>
              ))}
            </div>
          </div>

          {/* Visual: two-layer scene — Hakeem transparent cutout peeking from
              BEHIND the teacher dashboard window — mirrors the principal hero. */}
          <div className={`flex flex-col justify-center ${isRTL ? '' : 'order-1'}`}>
            <div
              className="relative ![direction:ltr] w-full max-w-[640px] mx-auto lg:mx-0 lg:max-w-none
                         pt-8 lg:pt-10"
              dir="ltr"
              data-testid="teacher-hero-visual"
            >
              {/* Ambient glow halo behind the whole scene */}
              <div
                className="pointer-events-none absolute -inset-x-6 inset-y-2 rounded-[40px] bg-brand-turquoise/10 blur-3xl"
                aria-hidden="true"
              />

              {/* Hakeem — transparent cutout peeking out from BEHIND the dashboard */}
              <div
                className="pointer-events-none select-none absolute z-0 bottom-0 start-[-2%] sm:start-0
                           w-[36%] sm:w-[34%] lg:w-[36%] max-w-[280px]"
                aria-hidden="true"
              >
                <img
                  src="/images/hakeem-hide-seek.png"
                  alt=""
                  width={351}
                  height={472}
                  loading="lazy"
                  className="block w-full h-auto object-bottom drop-shadow-2xl"
                />
              </div>

              {/* Teacher dashboard — dominant foreground window, offset to the end side */}
              <div
                className="relative z-10 ms-auto w-[76%] sm:w-[78%] lg:w-[80%]
                           bg-white rounded-2xl shadow-2xl shadow-brand-navy/30 border border-slate-100 overflow-hidden
                           transform transition-transform duration-500 hover:scale-[1.01]"
              >
                <img
                  src="/teacher-dashboard-preview.png"
                  alt={t('teacherExpHeroImageAlt')}
                  width={1920}
                  height={827}
                  className="block w-full h-auto"
                  loading="lazy"
                />
              </div>
            </div>
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
              <span className="text-brand-turquoise text-sm font-tajawal font-medium">{t('teacherExpWorkflowEyebrow')}</span>
            </div>
            <h2 className="font-cairo font-black text-foreground text-3xl md:text-5xl lg:text-[3.5rem] leading-tight mb-5">
              {t('teacherExpWorkflowHeadingLead')}<span className="text-brand-turquoise">{t('teacherExpWorkflowHeadingAccent')}</span>{t('teacherExpWorkflowHeadingTail')}
            </h2>
            <p className="text-lg text-muted-foreground font-tajawal max-w-2xl mx-auto leading-relaxed">
              {t('teacherExpWorkflowSubheading')}
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
                  <h3 className="font-cairo text-sm font-bold text-foreground mb-2">{t(`teacherExpWorkflowStep${i + 1}Title`)}</h3>
                  <p className="font-tajawal text-xs text-muted-foreground leading-relaxed">{t(`teacherExpWorkflowStep${i + 1}Desc`)}</p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ── ACHIEVEMENT FILE — navy ────────────────────────────── */}
      <section className="relative bg-brand-navy py-24 lg:py-32 overflow-hidden">
        {/* Brand background image */}
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: `url('/nassaq-background.png')` }}
          aria-hidden="true"
        />
        {/* Subtle pattern overlay */}
        <div
          className="absolute inset-0 opacity-[0.06]"
          style={{ backgroundImage: `url(${BG_PATTERN})`, backgroundSize: '200% auto', backgroundPosition: 'center center' }}
          aria-hidden="true"
        />
        {/* Navy tint to lock in contrast */}
        <div className="absolute inset-0 bg-brand-navy/70" aria-hidden="true" />
        <div className="absolute top-0 left-0 w-[500px] h-[500px] rounded-full bg-brand-turquoise/6 blur-[120px] animate-pulse" style={{ animationDuration: '10s' }} aria-hidden="true" />
        <div className="absolute bottom-0 right-0 w-[400px] h-[400px] rounded-full bg-brand-purple/6 blur-[100px] animate-pulse" style={{ animationDelay: '2s', animationDuration: '8s' }} aria-hidden="true" />

        <div className="relative max-w-6xl mx-auto px-6 grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          {/* copy */}
          <div className="space-y-6">
            <div className="inline-flex items-center gap-2.5 bg-white/10 border border-white/20 rounded-full px-5 py-2.5">
              <FileText className="h-4 w-4 text-white" strokeWidth={1.5} aria-hidden="true" />
              <span className="text-white text-sm font-tajawal font-medium">{t('teacherExpAchEyebrow')}</span>
            </div>
            <div className="space-y-3">
              <h2 className="font-cairo font-black text-white text-4xl md:text-5xl lg:text-[3.75rem] leading-[1.05] tracking-tight">
                {t('teacherExpAchHeading')}
              </h2>
              <p className="font-cairo font-bold text-brand-turquoise text-2xl md:text-3xl lg:text-[2rem] leading-tight">
                {t('teacherExpAchSubheading')}
              </p>
            </div>
            <p className="font-tajawal text-white/65 text-base md:text-[1.0625rem] leading-relaxed max-w-lg pt-1">
              {t('teacherExpAchBody')}
            </p>
            <ul className="space-y-3">
              {[1, 2, 3, 4].map((n) => (
                <li key={n} className="flex items-start gap-3 font-tajawal text-sm text-white/70">
                  <CheckCircle2 className="h-4 w-4 text-brand-turquoise shrink-0 mt-0.5" strokeWidth={2} aria-hidden="true" />
                  {t(`teacherExpAchPoint${n}`)}
                </li>
              ))}
            </ul>
          </div>

          {/* achievement file card */}
          <div aria-label={t('teacherExpAchCardTitle')}>
            <div className="bg-white border border-slate-200/70 rounded-2xl overflow-hidden shadow-[0_20px_60px_-20px_rgba(2,12,46,0.45)] ring-1 ring-black/5">
              {/* card header */}
              <div className="px-5 py-4 border-b border-slate-200/80 flex items-center justify-between bg-gradient-to-b from-slate-50/60 to-white">
                <div>
                  <p className="font-cairo text-brand-navy font-bold text-base">{t('teacherExpAchCardTitle')}</p>
                  <p className="font-tajawal text-slate-500 text-xs mt-0.5">{t('teacherExpAchCardSubtitle')}</p>
                </div>
                <button className="flex items-center gap-1.5 font-tajawal text-xs font-medium text-brand-navy border border-slate-200 rounded-lg px-3 py-1.5 hover:bg-slate-50 hover:border-slate-300 transition-colors">
                  <Download className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden="true" />
                  {t('teacherExpAchExport')}
                </button>
              </div>

              {/* stats */}
              <div className="grid grid-cols-3 divide-x divide-slate-200/70 rtl:divide-x-reverse border-b border-slate-200/80 bg-white">
                {[
                  { value: '٤٥', label: t('teacherExpAchStat1Label'), accent: 'text-teal-700' },
                  { value: '١٢', label: t('teacherExpAchStat2Label'), accent: 'text-brand-navy' },
                  { value: t('teacherExpAchStat3Value'), label: t('teacherExpAchStat3Label'), accent: 'text-teal-700' },
                ].map((s, i) => (
                  <div key={i} className="py-4 px-3 text-center">
                    <p className={`font-cairo font-black text-xl ${s.accent}`}>{s.value}</p>
                    <p className="font-tajawal text-slate-600 text-xs mt-1">{s.label}</p>
                  </div>
                ))}
              </div>

              {/* records */}
              <div className="px-5 py-4 bg-white">
                <p className="font-tajawal text-slate-500 text-xs mb-3">{t('teacherExpAchRecordsTitle')}</p>
                <div className="space-y-1">
                  {ACHIEVEMENT_RECORDS.map((rec, i) => {
                    const Icon = rec.icon;
                    return (
                      <div key={i} className="flex items-center gap-3 py-2 border-b border-slate-100 last:border-0">
                        <div className="w-8 h-8 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-center shrink-0">
                          <Icon className="h-4 w-4 text-slate-500" strokeWidth={1.5} aria-hidden="true" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="font-cairo text-xs font-semibold text-brand-navy truncate">{t(`teacherExpAchRecord${i + 1}Subject`)}</p>
                          <p className="font-tajawal text-[11px] text-slate-600 truncate">{t(`teacherExpAchRecord${i + 1}Note`)}</p>
                        </div>
                        <span className={`shrink-0 font-tajawal text-[10px] font-medium px-2 py-0.5 rounded-full ${rec.tagColor}`}>{t(`teacherExpAchRecord${i + 1}Tag`)}</span>
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

        <div className="relative max-w-6xl mx-auto px-6 grid lg:grid-cols-2 gap-12 lg:gap-16 items-stretch">
          {/* send form mockup */}
          <div className="flex">
            <div className="bg-card/80 border border-border/50 rounded-2xl overflow-hidden shadow-sm w-full flex flex-col">
              {/* header */}
              <div className="px-5 py-4 border-b border-border/50 flex items-center justify-between">
                <div>
                  <p className="font-cairo font-bold text-foreground text-sm">{t('teacherExpPcFormTitle')}</p>
                  <p className="font-tajawal text-muted-foreground text-xs mt-0.5">{t('teacherExpPcLive')}</p>
                </div>
                <Bell className="h-5 w-5 text-brand-turquoise" strokeWidth={1.5} aria-hidden="true" />
              </div>

              {/* alert type selector */}
              <div className="px-5 py-4 border-b border-border/50">
                <p className="font-tajawal text-xs text-muted-foreground mb-3">{t('teacherExpPcAlertTypeLabel')}</p>
                <div className="flex flex-wrap gap-2">
                  {ALERT_TYPES.map((alert, i) => {
                    const Icon = alert.icon;
                    return (
                      <button
                        key={i}
                        onClick={() => setActiveAlertType(i)}
                        className={`flex items-center gap-1.5 font-tajawal text-xs px-3 py-1.5 rounded-lg border transition-all ${
                          activeAlertType === i
                            ? `${alert.color} shadow-sm`
                            : 'bg-muted/50 text-muted-foreground border-border/50 hover:bg-muted'
                        }`}
                      >
                        <Icon className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden="true" />
                        {t(`teacherExpAlertType${i + 1}`)}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* message preview */}
              <div className="px-5 py-4 border-b border-border/50 flex-1 flex flex-col">
                <p className="font-tajawal text-xs text-muted-foreground mb-2">{t('teacherExpPcPreviewLabel')}</p>
                <div className="bg-slate-50 rounded-xl p-3 font-tajawal text-sm text-foreground/80 leading-relaxed border border-border/30 flex-1 min-h-[88px] transition-all duration-300">
                  {t(`teacherExpPcMessageBody${activeAlertType + 1}`)}
                </div>
              </div>

              {/* hakim suggestion */}
              <div className="px-5 py-3 border-b border-border/50 flex items-start gap-2.5 min-h-[64px]">
                <div className="w-6 h-6 rounded-full bg-brand-purple flex items-center justify-center font-cairo font-bold text-[10px] text-white shrink-0 mt-0.5">ح</div>
                <p className="font-tajawal text-xs text-muted-foreground leading-relaxed">
                  <span className="text-brand-purple font-bold font-cairo">{t('teacherExpPcHakimLabel')}</span>
                  {t(`teacherExpPcHakimSuggestion${activeAlertType + 1}`)}
                </p>
              </div>

              {/* send button */}
              <div className="px-5 py-4">
                <button className="w-full flex items-center justify-center gap-2 bg-brand-navy text-white font-cairo font-bold text-sm py-3 rounded-lg hover:bg-brand-navy-light shadow-sm hover:shadow-md transition-all active:scale-[0.98]">
                  <Send className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />
                  {t('teacherExpPcSendBtn')}
                </button>
                <p className="text-center font-tajawal text-xs text-muted-foreground mt-2">
                  {t('teacherExpPcTrialNote')}
                </p>
              </div>
            </div>
          </div>

          {/* copy */}
          <div className="flex flex-col justify-center space-y-6">
            <div className="inline-flex items-center gap-2.5 bg-gradient-to-r from-brand-turquoise/15 to-brand-turquoise/5 border border-brand-turquoise/25 rounded-full px-5 py-2.5 w-fit">
              <MessageCircle className="h-4 w-4 text-brand-turquoise" strokeWidth={1.5} aria-hidden="true" />
              <span className="text-brand-turquoise text-sm font-tajawal font-medium">{t('teacherExpPcEyebrow')}</span>
            </div>
            <h2 className="font-cairo font-black text-foreground text-3xl md:text-5xl lg:text-[3.5rem] leading-tight">
              {t('teacherExpPcHeadingLead')}<br /><span className="text-brand-turquoise">{t('teacherExpPcHeadingAccent')}</span>
            </h2>
            <p className="font-tajawal text-muted-foreground text-lg leading-relaxed max-w-lg">
              {t('teacherExpPcSubheading')}
            </p>
            <div className="grid grid-cols-2 gap-3">
              {PARENT_COMM_CARDS.map((item, i) => {
                const Icon = item.icon;
                return (
                  <div key={i} className="bg-card/80 border border-border/50 rounded-xl p-3 hover:border-brand-turquoise/30 hover:shadow-sm transition-all">
                    <div className="w-8 h-8 rounded-lg bg-brand-turquoise/10 flex items-center justify-center mb-2">
                      <Icon className="h-4 w-4 text-brand-turquoise" strokeWidth={1.5} aria-hidden="true" />
                    </div>
                    <p className="font-cairo text-xs font-bold text-foreground mb-1">{t(`teacherExpPcCard${i + 1}Title`)}</p>
                    <p className="font-tajawal text-[11px] text-muted-foreground">{t(`teacherExpPcCard${i + 1}Desc`)}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      {/* ── FAQ — navy + nassaq texture ───────────────────────── */}
      <section
        className="relative bg-brand-navy py-24 lg:py-32 overflow-hidden"
        id="teacher-faq"
        data-testid="teacher-faq-section"
      >
        {/* Brand background image */}
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: `url('/nassaq-background.png')` }}
          aria-hidden="true"
        />
        {/* Subtle pattern overlay */}
        <div
          className="absolute inset-0 opacity-[0.06]"
          style={{ backgroundImage: `url(${BG_PATTERN})`, backgroundSize: '200% auto', backgroundPosition: 'center center' }}
          aria-hidden="true"
        />
        {/* Navy tint to lock in contrast */}
        <div className="absolute inset-0 bg-brand-navy/70" aria-hidden="true" />
        <div className="absolute top-0 right-0 w-[500px] h-[500px] rounded-full bg-brand-turquoise/6 blur-[120px] animate-pulse" style={{ animationDuration: '10s' }} aria-hidden="true" />
        <div className="absolute bottom-0 left-0 w-[400px] h-[400px] rounded-full bg-brand-purple/6 blur-[100px] animate-pulse" style={{ animationDelay: '3s', animationDuration: '8s' }} aria-hidden="true" />

        <div className="relative max-w-3xl mx-auto px-6">
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-2.5 bg-brand-turquoise/15 border border-brand-turquoise/30 rounded-full px-5 py-2.5 mb-6 backdrop-blur-sm">
              <HelpCircle className="h-4 w-4 text-brand-turquoise animate-pulse" strokeWidth={1.5} aria-hidden="true" />
              <span className="text-brand-turquoise text-sm font-tajawal font-medium">
                {t('teacherFaqEyebrow')}
              </span>
            </div>
            <h2 className="font-cairo font-black text-white text-3xl md:text-4xl text-center leading-tight">
              {t('teacherFaqHeading')}
            </h2>
          </div>

          <div className="space-y-3">
            {Array.from({ length: FAQ_TOTAL }, (_, idx) => idx + 1)
              .slice(0, faqExpanded ? FAQ_TOTAL : FAQ_COLLAPSED_COUNT)
              .map((n) => (
              <details
                key={n}
                className="group bg-white/5 border border-white/10 rounded-2xl overflow-hidden backdrop-blur-sm transition-all duration-300 hover:border-brand-turquoise/30 hover:shadow-md open:border-brand-turquoise/40 open:shadow-xl open:shadow-brand-turquoise/5"
              >
                <summary className="flex items-center justify-between gap-4 px-6 py-5 cursor-pointer list-none focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-turquoise focus-visible:ring-offset-2 focus-visible:ring-offset-brand-navy rounded-2xl">
                  <span className="font-cairo font-bold text-white text-base text-start">
                    {t(`teacherFaqQ${n}`)}
                  </span>
                  <span className="shrink-0 w-8 h-8 rounded-lg bg-brand-turquoise/10 flex items-center justify-center transition-colors group-hover:bg-brand-turquoise/15 group-open:bg-gradient-to-br group-open:from-brand-turquoise group-open:to-cyan-500">
                    <ChevronDown className="h-4 w-4 text-brand-turquoise group-open:text-white group-open:rotate-180 transition-all" strokeWidth={2} aria-hidden="true" />
                  </span>
                </summary>
                <div className="px-6 pb-5 -mt-1">
                  <p className="font-tajawal text-sm text-white/70 leading-relaxed">
                    {t(`teacherFaqA${n}`)}
                  </p>
                </div>
              </details>
            ))}
          </div>

          {FAQ_TOTAL > FAQ_COLLAPSED_COUNT && (
            <div className="mt-8 flex justify-center">
              <button
                type="button"
                onClick={() => setFaqExpanded((v) => !v)}
                aria-expanded={faqExpanded}
                data-testid="teacher-faq-toggle"
                className="inline-flex items-center gap-2 font-cairo font-bold text-sm px-6 py-3 rounded-xl bg-white/5 border border-brand-turquoise/30 text-brand-turquoise hover:bg-brand-turquoise/10 hover:border-brand-turquoise/50 transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-turquoise focus-visible:ring-offset-2 focus-visible:ring-offset-brand-navy"
              >
                {faqExpanded ? t('faqShowLess') : t('faqShowMore')}
                <ChevronDown
                  className={`h-4 w-4 transition-transform ${faqExpanded ? 'rotate-180' : ''}`}
                  strokeWidth={2}
                  aria-hidden="true"
                />
              </button>
            </div>
          )}
        </div>
      </section>

      {/* ── PRICING — navy ────────────────────────────────────── */}
      {showTeacherPricing && (
      <section className="relative bg-brand-navy py-24 lg:py-32 overflow-hidden">
        {/* Brand background image */}
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: `url('/nassaq-background.png')` }}
          aria-hidden="true"
        />
        {/* Subtle pattern overlay */}
        <div
          className="absolute inset-0 opacity-[0.06]"
          style={{ backgroundImage: `url(${BG_PATTERN})`, backgroundSize: '200% auto', backgroundPosition: 'center center' }}
          aria-hidden="true"
        />
        {/* Navy tint to lock in contrast */}
        <div className="absolute inset-0 bg-brand-navy/70" aria-hidden="true" />
        <div className="absolute top-0 left-0 w-[500px] h-[500px] rounded-full bg-brand-turquoise/5 blur-3xl animate-pulse" style={{ animationDuration: '10s' }} aria-hidden="true" />
        <div className="absolute bottom-0 right-0 w-[400px] h-[400px] rounded-full bg-brand-purple/5 blur-3xl animate-pulse" style={{ animationDelay: '2s', animationDuration: '8s' }} aria-hidden="true" />

        <div className="relative max-w-4xl mx-auto px-6">
          <div className="text-center mb-14">
            <div className="inline-flex items-center gap-2 bg-white/10 border border-white/25 rounded-full px-5 py-2 mb-6">
              <Award className="h-4 w-4 text-white" strokeWidth={1.5} aria-hidden="true" />
              <span className="font-tajawal text-sm font-medium text-white">{t('teacherExpPricingEyebrow')}</span>
            </div>
            <h2 className="font-cairo font-black text-white text-3xl md:text-5xl leading-tight mb-4">
              {t('teacherExpPricingHeading')}
            </h2>
          </div>

          <div className="grid md:grid-cols-2 gap-6 max-w-2xl mx-auto">
            {/* Monthly */}
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-7 flex flex-col hover:border-white/20 hover:bg-white/8 transition-all">
              <p className="font-cairo font-bold text-white/70 text-sm mb-4">{t('teacherExpPlanMonthlyName')}</p>
              <div className="flex items-end gap-1 mb-1">
                <span className="font-cairo font-black text-white text-5xl">٢٩</span>
                <span className="font-tajawal text-white/50 text-sm mb-2">{t('teacherExpPlanMonthlyUnit')}</span>
              </div>
              <p className="font-tajawal text-white/40 text-xs mb-6">{t('teacherExpPlanMonthlyNote')}</p>
              <ul className="space-y-2.5 mb-8 flex-1">
                {Array.from({ length: PLAN_FEATURE_COUNT }, (_, i) => i + 1).map((n) => (
                  <li key={n} className="flex items-center gap-2.5 font-tajawal text-sm text-white/70">
                    <Check className="h-4 w-4 text-brand-turquoise shrink-0" strokeWidth={2} aria-hidden="true" />
                    {t(`teacherExpPlanFeature${n}`)}
                  </li>
                ))}
              </ul>
              <Link
                to="/teacher-register"
                className="block text-center font-cairo font-bold text-sm py-3 rounded-lg border-2 border-white/20 text-white hover:bg-white/10 hover:border-white/30 transition-all active:scale-[0.98]"
              >
                {t('teacherExpPlanCta')}
              </Link>
            </div>

            {/* Annual — highlighted */}
            <div className="relative bg-white/10 backdrop-blur-sm border border-brand-turquoise/40 rounded-2xl p-7 flex flex-col shadow-2xl shadow-brand-turquoise/10 scale-[1.02]">
              {/* recommended badge */}
              <div className="absolute -top-3 inset-x-0 flex justify-center">
                <span className="bg-gradient-to-r from-brand-turquoise to-cyan-500 text-white font-cairo text-xs font-bold px-4 py-1 rounded-full shadow-lg shadow-brand-turquoise/30">
                  {t('teacherExpPlanBestValue')}
                </span>
              </div>
              <p className="font-cairo font-bold text-white text-sm mb-4">{t('teacherExpPlanAnnualName')}</p>
              <div className="flex items-end gap-1 mb-1">
                <span className="font-cairo font-black text-brand-turquoise text-5xl">١٩٩</span>
                <span className="font-tajawal text-white/50 text-sm mb-2">{t('teacherExpPlanAnnualUnit')}</span>
              </div>
              <p className="font-tajawal text-white/40 text-xs mb-6">{t('teacherExpPlanAnnualNote')}</p>
              <ul className="space-y-2.5 mb-8 flex-1">
                {Array.from({ length: PLAN_FEATURE_COUNT }, (_, i) => i + 1).map((n) => (
                  <li key={n} className="flex items-center gap-2.5 font-tajawal text-sm text-white/80">
                    <Check className="h-4 w-4 text-brand-turquoise shrink-0" strokeWidth={2} aria-hidden="true" />
                    {t(`teacherExpPlanFeature${n}`)}
                  </li>
                ))}
              </ul>
              <Link
                to="/teacher-register"
                className="block text-center font-cairo font-bold text-sm py-3 rounded-lg bg-gradient-to-r from-brand-turquoise to-cyan-500 hover:from-brand-turquoise-light hover:to-cyan-400 text-white shadow-lg shadow-brand-turquoise/25 hover:shadow-xl transition-all active:scale-[0.98]"
              >
                {t('teacherExpPlanCta')}
              </Link>
            </div>
          </div>

          <p className="text-center font-tajawal text-sm text-white/40 mt-8">
            {t('teacherExpPricingFooter')}
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
                alt={t('teacherExpHakimAlt')}
                className="hakim-img relative w-24 h-24 rounded-2xl object-contain border-2 border-brand-turquoise shadow-xl bg-gradient-to-br from-cyan-50 to-violet-50 p-1"
              />
            </div>
          </div>

          <div className="inline-flex items-center gap-2.5 bg-gradient-to-r from-brand-turquoise/15 to-brand-turquoise/5 border border-brand-turquoise/25 rounded-full px-5 py-2.5 mb-6 backdrop-blur-sm">
            <Sparkles className="h-4 w-4 text-brand-turquoise" strokeWidth={1.5} aria-hidden="true" />
            <span className="text-brand-turquoise text-sm font-tajawal font-medium">{t('teacherExpFinalEyebrow')}</span>
          </div>

          <h2 className="font-cairo font-black text-foreground text-3xl md:text-5xl lg:text-[3.5rem] leading-tight mb-5">
            {t('teacherExpFinalHeadingLead')}<br /><span className="text-brand-turquoise">{t('teacherExpFinalHeadingAccent')}</span>
          </h2>

          <p className="font-tajawal text-muted-foreground text-lg max-w-xl mx-auto leading-relaxed mb-10">
            {t('teacherExpFinalSubheading')}
          </p>

          <div className="flex flex-wrap items-center justify-center gap-4">
            <Link
              to="/teacher-register"
              className="inline-flex items-center gap-2 font-cairo font-bold text-lg px-10 py-4 rounded-2xl bg-gradient-to-r from-brand-turquoise to-cyan-500 hover:from-brand-turquoise-light hover:to-cyan-400 text-white shadow-2xl shadow-brand-turquoise/30 hover:shadow-brand-turquoise/40 transition-all hover:scale-[1.03] active:scale-[0.98]"
              data-testid="teacher-final-cta"
            >
              {t('teacherExpFinalCtaPrimary')}
              {isRTL ? <ArrowLeft className="h-5 w-5" strokeWidth={1.5} aria-hidden="true" /> : <ArrowRight className="h-5 w-5" strokeWidth={1.5} aria-hidden="true" />}
            </Link>
            <Link
              to="/"
              className="inline-flex items-center gap-2 font-tajawal text-sm font-medium px-6 py-3 rounded-lg border border-border text-foreground hover:bg-muted hover:text-foreground transition-all"
            >
              {t('teacherExpFinalCtaSecondary')}
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
