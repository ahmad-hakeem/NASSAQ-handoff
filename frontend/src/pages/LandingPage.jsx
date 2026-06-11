import { useState, useEffect, useRef, useMemo } from 'react';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { Footer } from '../components/layout/Footer';
import { HakimAssistant } from '../components/hakim/HakimAssistant';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import {
  ArrowLeft,
  Sparkles,
  Database,
  Brain,
  BarChart3,
  CheckCircle2,
  Users,
  GraduationCap,
  UserCheck,
  Building2,
  Calendar,
  BookOpen,
  Bell,
  Target,
  Lightbulb,
  TrendingUp,
  Award,
  ClipboardCheck,
  Activity,
  Star,
  Layers,
  ChevronDown,
  Zap,
  Shield,
  ArrowRight,
  Globe,
} from 'lucide-react';

const LOGO_WHITE = '/nassaq-logo-white.png';
const BG_PATTERN = '/nassaq-pattern.png';
const HAKIM_CHARACTER = '/hakim-poses/friendly-greeting.png';
const HAKIM_HERO_WELCOME = '/hakim-poses/welcome.png';

// Module-level cache for public landing data. The two-tab public shell
// unmounts and remounts this page on every tab switch; without a cache,
// each remount re-issues the /public/schools-count and
// /public/growth-indicators requests. Storing the most recent successful
// response here lets subsequent mounts hydrate instantly from memory while
// still revalidating in the background. The cache lives for the lifetime
// of the tab; a hard reload clears it as expected.
const landingDataCache = {
  platformStats: null,
  growthIndicators: null,
};


function useTypedText(texts, speed = 40, pauseBetween = 3000) {
  const [display, setDisplay] = useState('');
  const [textIndex, setTextIndex] = useState(0);
  const [charIndex, setCharIndex] = useState(0);
  const [phase, setPhase] = useState('typing');

  useEffect(() => {
    if (!texts || texts.length === 0) return;
    const currentText = texts[textIndex];

    if (phase === 'typing') {
      if (charIndex < currentText.length) {
        const timeout = setTimeout(() => {
          setDisplay(currentText.slice(0, charIndex + 1));
          setCharIndex(charIndex + 1);
        }, speed);
        return () => clearTimeout(timeout);
      } else {
        const timeout = setTimeout(() => setPhase('pause'), pauseBetween);
        return () => clearTimeout(timeout);
      }
    }

    if (phase === 'pause') {
      const nextIdx = (textIndex + 1) % texts.length;
      setTextIndex(nextIdx);
      setCharIndex(0);
      setDisplay('');
      setPhase('typing');
    }
  }, [texts, textIndex, charIndex, phase, speed, pauseBetween]);

  return display;
}

function AnimatedCounter({ target, duration = 2000, suffix = '' }) {
  const [count, setCount] = useState(0);
  const ref = useRef(null);
  const hasAnimated = useRef(false);
  const rafRef = useRef(null);
  const isVisible = useRef(false);
  const prevTarget = useRef(0);

  useEffect(() => {
    if (target > 0 && target !== prevTarget.current) {
      prevTarget.current = target;
      if (isVisible.current) {
        hasAnimated.current = false;
      }
    }
  }, [target]);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        isVisible.current = entry.isIntersecting;
        if (entry.isIntersecting && !hasAnimated.current && target > 0) {
          hasAnimated.current = true;
          const startTime = Date.now();
          const animate = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            setCount(Math.round(target * eased));
            if (progress < 1) {
              rafRef.current = requestAnimationFrame(animate);
            }
          };
          rafRef.current = requestAnimationFrame(animate);
        }
      },
      { threshold: 0.3 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => {
      observer.disconnect();
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [target, duration]);

  return <span ref={ref}>{count > 0 ? `${count.toLocaleString()}+` : '0'}{suffix}</span>;
}

function useScrollReveal() {
  const ref = useRef(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setIsVisible(true); },
      { threshold: 0.15 }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return [ref, isVisible];
}

function FloatingIcon({ icon: Icon, className, delay = '0s' }) {
  return (
    <div
      className={`absolute ${className} opacity-20 animate-float`}
      style={{ animationDelay: delay, animationDuration: '6s' }}
    >
      <Icon className="h-6 w-6 text-brand-turquoise" />
    </div>
  );
}

// Set to true to re-enable the pricing/packages section and its navbar link.
const SHOW_PRICING = false;

// Set to true to re-enable the "رحلة التحول الذكي" journey section.
const SHOW_JOURNEY = false;

// Set to true to re-enable the "الذكاء خلف نَسَّق" AI intelligence section
// (also restores its "الحلول/Solutions" navbar anchor).
const SHOW_AI_SECTION = false;

export const LandingPage = () => {
  const { isRTL } = useTheme();
  const { t } = useTranslation();
  const { api } = useAuth();
  const [activeJourneyStep, setActiveJourneyStep] = useState(0);
  const [activeAIStep, setActiveAIStep] = useState(0);
  const [activeEcosystemRole, setActiveEcosystemRole] = useState(0);
  const [faqExpanded, setFaqExpanded] = useState(false);
  const FAQ_COLLAPSED_COUNT = 5;
  const FAQ_TOTAL = 15;

  const [journeyPaused, setJourneyPaused] = useState(false);
  const [aiPaused, setAIPaused] = useState(false);
  const [ecosystemPaused, setEcosystemPaused] = useState(false);

  // Landing-page anchor sections — kept in nav order so the navbar can render
  // and IntersectionObserver can highlight the active section in sync.
  const navSections = useMemo(() => ([
    { id: 'how-it-works', ar: 'كيف يعمل', en: 'How it works' },
    ...(SHOW_AI_SECTION ? [{ id: 'solutions', ar: 'الحلول', en: 'Solutions' }] : []),
    { id: 'ecosystem',    ar: 'الأدوار',  en: 'Roles' },
    { id: 'proof',        ar: 'النتائج', en: 'Results' },
    { id: 'faq',          ar: 'الأسئلة الشائعة', en: 'FAQ' },
    ...(SHOW_PRICING ? [{ id: 'plans', ar: 'الباقات', en: 'Plans' }] : []),
  ]), []);

  const [activeSection, setActiveSection] = useState('');

  useEffect(() => {
    const ids = navSections.map(({ id }) => id);
    const HEADER_OFFSET = 96; // sticky navbar height + breathing room

    const pickActive = () => {
      const targets = ids
        .map((id) => document.getElementById(id))
        .filter(Boolean);
      if (!targets.length) return;

      const scrollY = window.scrollY;
      const docBottomReached =
        window.innerHeight + scrollY >= document.documentElement.scrollHeight - 4;

      // At the very bottom: always highlight the last section so the user
      // doesn't see the second-to-last lit while looking at the final one.
      if (docBottomReached) {
        setActiveSection(targets[targets.length - 1].id);
        return;
      }

      // Pick the section whose top has just crossed the header offset —
      // i.e. the last one whose top <= header offset.
      let current = '';
      for (const el of targets) {
        const top = el.getBoundingClientRect().top;
        if (top - HEADER_OFFSET <= 0) {
          current = el.id;
        } else {
          break;
        }
      }
      setActiveSection(current);
    };

    pickActive();
    window.addEventListener('scroll', pickActive, { passive: true });
    window.addEventListener('resize', pickActive);
    return () => {
      window.removeEventListener('scroll', pickActive);
      window.removeEventListener('resize', pickActive);
    };
  }, [navSections]);

  const handleNavClick = (e, id) => {
    e.preventDefault();
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      setActiveSection(id);
    }
  };

  // Fixed welcome pose for hero (no rotation)
  const heroHakim = { currentSrc: HAKIM_HERO_WELCOME };

  // Module-level cache (see below) hydrates these on remount so switching
  // between the public tabs does not refetch already-loaded data.
  const [platformStats, setPlatformStats] = useState(() => ({
    schools: 0,
    students: 0,
    teachers: 0,
    parents: 0,
    ...(landingDataCache.platformStats || {}),
  }));

  // Sanitized, server-provided display indicators for the trust section.
  // The backend returns ONLY preformatted bucketed strings (e.g. "100+",
  // "1K+") — never raw aggregate counts — so the browser cannot reconstruct
  // the exact platform-wide totals.
  const [growthIndicators, setGrowthIndicators] = useState(() => (
    landingDataCache.growthIndicators || { schools: null, teachers: null }
  ));

  // Single normalized display rule for all growth counters in this section.
  // Accepts an already-vetted string from the server and returns it unchanged
  // when it already ends in "+"; otherwise appends exactly one "+". Never
  // concatenates a prefix-plus with a suffix-plus.
  const formatGrowthIndicator = (raw) => {
    if (raw == null) return null;
    const trimmed = String(raw).trim().replace(/^\++/, '').replace(/\++$/, '');
    if (!trimmed) return null;
    return `${trimmed}+`;
  };

  const hakimMessages = useMemo(() => [
    t('landingHakimIntro1'),
    t('landingHakimIntro2'),
    t('landingHakimIntro3'),
  ], [t]);

  const typedHakimText = useTypedText(hakimMessages, 35, 4000);

  const [journeyRef, journeyVisible] = useScrollReveal();
  const [aiRef, aiVisible] = useScrollReveal();
  const [ecoRef, ecoVisible] = useScrollReveal();

  useEffect(() => {
    // Landing page is unauthenticated. The full /public/stats payload is
    // intentionally platform-admin gated (audit C-4). For the social-proof
    // line we use the curated public schools-count endpoint, which exposes
    // only a single aggregate integer with no per-tenant detail.
    // Skip the request entirely when the module-level cache already holds
    // a successful response from this tab's earlier mount.
    if (landingDataCache.platformStats) return;
    const fetchStats = async () => {
      try {
        const response = await api.get('/public/schools-count');
        const count = Number(response?.data?.count) || 0;
        landingDataCache.platformStats = { schools: count };
        setPlatformStats((prev) => ({ ...prev, schools: count }));
      } catch (error) {
        // Silent — social-proof block hides itself when the count is 0.
      }
    };
    fetchStats();
  }, [api]);

  useEffect(() => {
    // Trust section: pulls vetted, preformatted display strings only.
    // The server bucketizes raw counts into a fixed vocabulary so this
    // request never exposes platform-wide totals to the browser.
    if (landingDataCache.growthIndicators) return;
    const fetchGrowth = async () => {
      try {
        const response = await api.get('/public/growth-indicators');
        const data = response?.data || {};
        const next = {
          schools: typeof data.schools === 'string' ? data.schools : null,
          teachers: typeof data.teachers === 'string' ? data.teachers : null,
        };
        landingDataCache.growthIndicators = next;
        setGrowthIndicators(next);
      } catch (error) {
        // Silent — cards hide themselves when no indicator is available.
      }
    };
    fetchGrowth();
  }, [api]);

  useEffect(() => {
    if (journeyPaused) return;
    const interval = setInterval(() => {
      setActiveJourneyStep((prev) => (prev + 1) % 4);
    }, 3500);
    return () => clearInterval(interval);
  }, [journeyPaused]);

  useEffect(() => {
    if (aiPaused) return;
    const interval = setInterval(() => {
      setActiveAIStep((prev) => (prev + 1) % 4);
    }, 3500);
    return () => clearInterval(interval);
  }, [aiPaused]);

  useEffect(() => {
    if (ecosystemPaused) return;
    const interval = setInterval(() => {
      setActiveEcosystemRole((prev) => (prev + 1) % ecosystemRoles.length);
    }, 3500);
    return () => clearInterval(interval);
  }, [ecosystemPaused]);

  const journeySteps = [
    {
      title: t('landingJourneyStep1Title'),
      subtitle: t('landingJourneyStep1Subtitle'),
      content: t('landingJourneyStep1Content'),
      hakimSays: t('landingJourneyStep1HakimSays'),
      icons: [BarChart3, Calendar, Brain, BookOpen],
      phase: '01',
    },
    {
      title: t('landingJourneyStep2Title'),
      subtitle: t('landingJourneyStep2Subtitle'),
      content: t('landingJourneyStep2Content'),
      hakimSays: t('landingJourneyStep2HakimSays'),
      icons: [Database, TrendingUp, CheckCircle2, Award],
      phase: '02',
    },
    {
      title: t('landingJourneyStep3Title'),
      subtitle: t('landingJourneyStep3Subtitle'),
      content: t('landingJourneyStep3Content'),
      hakimSays: t('landingJourneyStep3HakimSays'),
      icons: [Brain, Lightbulb, TrendingUp, Target],
      phase: '03',
    },
    {
      title: t('landingJourneyStep4Title'),
      subtitle: t('landingJourneyStep4Subtitle'),
      content: t('landingJourneyStep4Content'),
      hakimSays: t('landingJourneyStep4HakimSays'),
      icons: [CheckCircle2, Award, Target, TrendingUp],
      phase: '04',
    },
  ];

  const aiCapabilities = [
    {
      title: t('landingAiCap1Title'),
      subtitle: t('landingAiCap1Subtitle'),
      content: t('landingAiCap1Content'),
      hakimSays: t('landingAiCap1HakimSays'),
      icon: Activity,
    },
    {
      title: t('landingAiCap2Title'),
      subtitle: t('landingAiCap2Subtitle'),
      content: t('landingAiCap2Content'),
      hakimSays: t('landingAiCap2HakimSays'),
      icon: Calendar,
    },
    {
      title: t('landingAiCap3Title'),
      subtitle: t('landingAiCap3Subtitle'),
      content: t('landingAiCap3Content'),
      hakimSays: t('landingAiCap3HakimSays'),
      icon: BarChart3,
    },
    {
      title: t('landingAiCap4Title'),
      subtitle: t('landingAiCap4Subtitle'),
      content: t('landingAiCap4Content'),
      hakimSays: t('landingAiCap4HakimSays'),
      icon: Database,
    },
  ];

  const aiAnalysisLayers = [
    { label: t('landingAiLayer1Label'), icon: ClipboardCheck, color: 'from-emerald-500 to-emerald-600', pct: 92 },
    { label: t('landingAiLayer2Label'), icon: BookOpen, color: 'from-sky-500 to-sky-600', pct: 78 },
    { label: t('landingAiLayer3Label'), icon: Activity, color: 'from-amber-500 to-amber-600', pct: 85 },
    { label: t('landingAiLayer4Label'), icon: Star, color: 'from-purple-500 to-purple-600', pct: 88 },
    { label: t('landingAiLayer5Label'), icon: TrendingUp, color: 'from-rose-500 to-rose-600', pct: 74 },
  ];

  const ecosystemRoles = [
    {
      role: t('landingEcoRole1Role'),
      title: t('landingEcoRole1Title'),
      content: t('landingEcoRole1Content'),
      hakimSays: t('landingEcoRole1HakimSays'),
      icon: Building2,
      gradient: 'from-brand-turquoise to-cyan-600',
    },
    {
      role: t('landingEcoRole2Role'),
      title: t('landingEcoRole2Title'),
      content: t('landingEcoRole2Content'),
      hakimSays: t('landingEcoRole2HakimSays'),
      icon: UserCheck,
      gradient: 'from-emerald-500 to-emerald-600',
    },
    {
      role: t('landingEcoRole4Role'),
      title: t('landingEcoRole4Title'),
      content: t('landingEcoRole4Content'),
      hakimSays: t('landingEcoRole4HakimSays'),
      icon: Users,
      gradient: 'from-amber-500 to-orange-600',
    },
  ];

  return (
    <div className="min-h-screen" dir={isRTL ? 'rtl' : 'ltr'} data-testid="landing-page">
      {/* Header lives in the shared <PublicShell>. Anchor scroll-spy
          (activeSection) still works against the section IDs below. */}

      {/* ========== HERO SECTION (Modern SaaS) ========== */}
      <section
        className="relative bg-brand-navy overflow-hidden"
        data-testid="hero-section"
      >
        {/* Brand background image */}
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: `url('/nassaq-background.png')` }}
        />
        {/* Subtle pattern overlay */}
        <div
          className="absolute inset-0 opacity-[0.08]"
          style={{ backgroundImage: `url(${BG_PATTERN})`, backgroundSize: '200% auto', backgroundPosition: 'center top' }}
        />
        {/* Navy tint to lock in contrast for the headline */}
        <div className="absolute inset-0 bg-brand-navy/70" />
        {/* Soft ambient glows */}
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -top-32 -end-32 w-[520px] h-[520px] rounded-full bg-brand-turquoise/15 blur-3xl" />
          <div className="absolute -bottom-32 -start-32 w-[420px] h-[420px] rounded-full bg-brand-purple/15 blur-3xl" />
        </div>

        <div className="relative max-w-7xl mx-auto px-6 py-16 lg:py-24">
          {/* Two strictly balanced columns: identical height via items-stretch.
              Left = dashboard visual group. Right = content group.
              Both share the same top and bottom boundary. */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:items-stretch">

            {/* ── RIGHT PANEL (RTL Start): content distributed top → bottom ── */}
            <div className="flex flex-col justify-between gap-8 text-start order-2 lg:order-1">

              {/* TOP GROUP: badge + headline + subheading */}
              <div className="space-y-6">
                <div className="inline-flex items-center gap-2 bg-brand-turquoise/15 border border-brand-turquoise/30 rounded-full ps-2 pe-4 py-1.5 backdrop-blur-sm">
                  <CheckCircle2 className="h-4 w-4 text-brand-turquoise" />
                  <span className="font-tajawal text-sm text-brand-turquoise">
                    {t('landingHeroBadge')}
                  </span>
                </div>
                <h1
                  className="font-cairo font-bold text-white leading-tight text-4xl sm:text-5xl lg:text-6xl"
                  data-testid="platform-name"
                >
                  <span className="text-white">{isRTL ? 'نَسَّق' : 'NASSAQ'}</span>
                </h1>
                <div className="space-y-2.5 max-w-xl">
                  <p
                    className="font-tajawal text-xl sm:text-2xl text-white/90 font-medium leading-snug"
                    data-testid="hero-subheading"
                  >
                    {t('landingHeroSubheading')}
                  </p>
                  <p
                    className="font-tajawal text-sm sm:text-base text-white/65 leading-relaxed"
                    data-testid="hero-supporting"
                  >
                    {t('landingHeroSupporting')}
                  </p>
                </div>
              </div>

              {/* MIDDLE GROUP: CTAs + trust microcopy */}
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-3">
                  <Button
                    asChild
                    className="bg-brand-turquoise hover:bg-brand-turquoise-light text-white hover:text-white font-cairo rounded-lg px-8 py-3 h-auto text-base shadow-lg hover:shadow-xl hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.98] transition-all"
                    data-testid="hero-cta-btn"
                  >
                    <Link to="/register" className="flex items-center gap-2">
                      {t('landingHeroCtaPrimary')}
                      {isRTL ? <ArrowLeft className="h-4 w-4" /> : <ArrowRight className="h-4 w-4" />}
                    </Link>
                  </Button>
                  <Button
                    asChild
                    variant="ghost"
                    className="bg-transparent border-2 border-white/30 text-white hover:bg-white/10 hover:text-white hover:border-white/50 font-cairo rounded-lg px-6 py-3 h-auto text-base transition-colors"
                    data-testid="hero-secondary-cta"
                  >
                    <a href="#how-it-works" className="flex items-center gap-2">
                      {t('landingHeroCtaSecondary')}
                    </a>
                  </Button>
                </div>
                <p className="font-tajawal text-xs text-white/60">
                  {t('landingHeroTrustMicrocopy')}
                </p>
              </div>

              {/* BOTTOM GROUP: social proof + feature ticker */}
              <div className="space-y-4">
                {platformStats.schools > 0 && (
                  <div className="flex items-center gap-3" data-testid="traction-section">
                    <div className="flex -space-x-2 rtl:space-x-reverse">
                      {['bg-brand-navy', 'bg-brand-turquoise', 'bg-brand-purple', 'bg-amber-500'].map((bgClass, i) => (
                        <div
                          key={i}
                          className={`w-8 h-8 rounded-full border-2 border-brand-navy flex items-center justify-center text-white text-xs font-cairo font-bold shadow-sm ${bgClass}`}
                        >
                          ن
                        </div>
                      ))}
                    </div>
                    <p className="font-tajawal text-sm text-white/75" data-testid="hero-school-count">
                      <span className="font-bold text-white">
                        <AnimatedCounter target={platformStats.schools} />
                        {' '}{t('landingHeroSchoolCountUnit')}
                      </span>{' '}
                      {t('landingHeroSchoolCountSuffix')}
                    </p>
                  </div>
                )}
                <div className="flex flex-wrap items-center gap-x-6 gap-y-2 pt-3 border-t border-white/10">
                  {[
                    t('landingHeroTicker1'),
                    t('landingHeroTicker2'),
                    t('landingHeroTicker3'),
                  ].map((item, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-brand-turquoise" />
                      <span className="font-tajawal text-sm text-white/80">{item}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* ── LEFT PANEL (RTL End): Hakim + dashboard as one art-directed scene ──
                Single relative stage: the dashboard is offset toward the end and
                Hakim is anchored to the shared baseline on the start side with a
                controlled overlap, so they read as one grounded composition.
                dir="ltr" + !direction lock the scene against page RTL flipping. */}
            <div className="order-1 lg:order-2 flex flex-col justify-center">
              <div
                className="relative ![direction:ltr] w-full max-w-[560px] mx-auto lg:mx-0 lg:ms-auto
                           pt-10 sm:pt-12 lg:pt-16"
                dir="ltr"
                data-testid="hero-visual-composition"
              >
                {/* Ambient glow halo behind the whole scene */}
                <div
                  className="pointer-events-none absolute -inset-x-6 bottom-6 top-2 rounded-[40px] bg-brand-turquoise/10 blur-3xl"
                  aria-hidden="true"
                />

                {/* Dashboard: primary anchor — offset to the end, leaving a column for Hakim */}
                <div
                  className="relative z-10 ms-auto w-[74%] sm:w-[76%] lg:w-[78%]
                             bg-white rounded-2xl shadow-2xl shadow-brand-navy/30 border border-slate-100 overflow-hidden
                             transform transition-transform duration-500 hover:scale-[1.01]"
                  data-testid="hero-mockup"
                >
                  {/* Browser chrome */}
                  <div className="flex items-center justify-between gap-2 px-4 h-9 bg-slate-50 border-b border-slate-100">
                    <div className="flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                      <span className="font-tajawal text-[11px] text-slate-500">{t('landingHeroLive')}</span>
                    </div>
                    <span className="font-tajawal text-[11px] text-slate-500">
                      {t('landingHeroDashboardTab')}
                    </span>
                    <div className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-slate-200" />
                      <span className="w-2 h-2 rounded-full bg-slate-200" />
                      <span className="w-2 h-2 rounded-full bg-slate-200" />
                    </div>
                  </div>

                  {/* Real product screenshot — natural aspect ratio, fully visible */}
                  <img
                    src="/images/landing-dashboard-preview.png"
                    alt={t('landingHeroDashboardAlt')}
                    width={1920}
                    height={827}
                    className="block w-full h-auto"
                    loading="lazy"
                  />
                </div>

                {/* Soft contact shadow grounding Hakim onto the same baseline as the card */}
                <div
                  className="pointer-events-none absolute z-10 bottom-1 start-[2%] w-[34%] sm:w-[30%] lg:w-[32%] h-3
                             rounded-[50%] bg-brand-navy-dark/50 blur-md"
                  aria-hidden="true"
                />

                {/* Hakim: large, static companion anchored to the shared baseline,
                    overlapping the dashboard's start edge so they feel connected. */}
                <div
                  className="pointer-events-none select-none absolute z-20 bottom-0 start-[-2%] sm:start-0
                             w-[46%] sm:w-[42%] lg:w-[44%] max-w-[300px]"
                  aria-hidden="true"
                >
                  <img
                    src="/hakim-welcome.png"
                    alt=""
                    width="320"
                    height="320"
                    loading="lazy"
                    className="block w-full h-auto object-bottom drop-shadow-2xl"
                  />
                </div>
              </div>

              <p className="font-tajawal text-xs text-white/60 text-center mt-4 shrink-0">
                {t('landingHeroDashboardFootnote')}
              </p>
            </div>

          </div>
        </div>
      </section>

      {/* ========== PAIN SECTION — funnel step 1: agitate the problem ========== */}
      <section
        className="relative bg-slate-50 dark:bg-slate-900 py-20 lg:py-28"
        data-testid="pain-section"
      >
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-center max-w-4xl mx-auto mb-14">
            <div className="inline-flex items-center gap-2 bg-brand-turquoise/10 border border-brand-turquoise/30 rounded-full ps-2 pe-4 py-1.5 mb-5">
              <Bell className="h-4 w-4 text-brand-turquoise" strokeWidth={1.5} aria-hidden="true" />
              <span className="font-tajawal text-sm text-brand-turquoise">
                {t('landingPainEyebrow')}
              </span>
            </div>
            <h2 className="font-cairo font-bold text-brand-navy dark:text-white text-3xl sm:text-4xl lg:text-5xl leading-tight mb-4 lg:whitespace-nowrap">
              {t('landingPainHeadingLead')}<span className="text-brand-turquoise">{t('landingPainHeadingAccent')}</span>
            </h2>
            <p className="font-tajawal text-base text-slate-600 dark:text-slate-300 leading-relaxed">
              {t('landingPainSubheading')}
            </p>
          </div>

          {/* 3-role pain columns — same problem from 3 angles */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {[
              {
                role: t('landingPainCol1Role'),
                icon: Building2,
                title: t('landingPainCol1Title'),
                body: t('landingPainCol1Body'),
                tag: t('landingPainCol1Tag'),
              },
              {
                role: t('landingPainCol2Role'),
                icon: GraduationCap,
                title: t('landingPainCol2Title'),
                body: t('landingPainCol2Body'),
                tag: t('landingPainCol2Tag'),
              },
              {
                role: t('landingPainCol3Role'),
                icon: Users,
                title: t('landingPainCol3Title'),
                body: t('landingPainCol3Body'),
                tag: t('landingPainCol3Tag'),
              },
            ].map((col, i) => {
              const Icon = col.icon;
              return (
                <div
                  key={i}
                  className="group bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-7 flex flex-col transition-all duration-300 ease-out hover:-translate-y-1.5 hover:shadow-md hover:border-slate-300 dark:hover:border-slate-600 motion-reduce:transition-none motion-reduce:hover:translate-y-0"
                >
                  <div className="flex items-center gap-3 mb-5">
                    <div className="shrink-0 w-10 h-10 rounded-lg bg-brand-turquoise/10 flex items-center justify-center transition-colors duration-300 group-hover:bg-brand-turquoise/15">
                      <Icon className="h-5 w-5 text-brand-turquoise" strokeWidth={1.5} aria-hidden="true" />
                    </div>
                    <span className="font-cairo text-xs font-bold text-brand-turquoise uppercase tracking-wider">
                      {col.role}
                    </span>
                  </div>
                  <h3 className="font-cairo font-bold text-brand-navy dark:text-white text-lg leading-snug mb-3">
                    {col.title}
                  </h3>
                  <p className="font-tajawal text-sm text-slate-600 dark:text-slate-300 leading-relaxed mb-5 flex-1">
                    {col.body}
                  </p>
                  <div className="flex items-center gap-2 pt-4 border-t border-slate-100 dark:border-slate-700">
                    <TrendingUp className="h-3.5 w-3.5 text-brand-turquoise shrink-0" strokeWidth={1.5} aria-hidden="true" />
                    <span className="font-tajawal text-xs text-slate-500 dark:text-slate-400">
                      {col.tag}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          <p className="font-tajawal text-center text-slate-500 dark:text-slate-400 text-sm mt-10">
            {t('landingPainFooter')}
          </p>
        </div>
      </section>

      {/* ========== HOW IT WORKS — compact 4-step strip (merged from client demo) ========== */}
      <section
        id="how-it-works"
        className="relative bg-brand-navy py-20 lg:py-24 overflow-hidden scroll-mt-24"
        data-testid="how-it-works-steps"
      >
        {/* nassaq background image — same treatment as hero */}
        <div
          className="absolute inset-0 bg-cover bg-center opacity-100"
          style={{ backgroundImage: `url('/nassaq-background.png')` }}
          aria-hidden="true"
        />
        <div
          className="absolute inset-0 opacity-[0.06]"
          style={{ backgroundImage: `url(${BG_PATTERN})`, backgroundSize: '200% auto', backgroundPosition: 'center top' }}
          aria-hidden="true"
        />
        <div className="absolute inset-0 bg-brand-navy/70" aria-hidden="true" />

        <div className="relative max-w-6xl mx-auto px-6">
          <div className="text-center max-w-5xl mx-auto mb-12">
            <div className="inline-flex items-center gap-2 bg-brand-turquoise/15 border border-brand-turquoise/30 rounded-full ps-2 pe-4 py-1.5 mb-5 backdrop-blur-sm">
              <Zap className="h-4 w-4 text-brand-turquoise" strokeWidth={1.5} aria-hidden="true" />
              <span className="font-tajawal text-sm text-brand-turquoise">
                {t('landingLoopEyebrow')}
              </span>
            </div>
            <h2 className="font-cairo font-bold text-white text-3xl sm:text-4xl md:text-5xl leading-tight tracking-normal text-center max-w-5xl mx-auto mb-4 selection:bg-brand-turquoise/30 selection:text-white">
              {t('landingLoopHeading')}
            </h2>
            <p className="font-tajawal text-base text-white/80 leading-relaxed max-w-2xl mx-auto">
              {t('landingLoopSubheading')}
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {[
              {
                title: t('landingLoopStep1Title'),
                body: t('landingLoopStep1Body'),
              },
              {
                title: t('landingLoopStep2Title'),
                body: t('landingLoopStep2Body'),
              },
              {
                title: t('landingLoopStep3Title'),
                body: t('landingLoopStep3Body'),
              },
              {
                title: t('landingLoopStep4Title'),
                body: t('landingLoopStep4Body'),
              },
            ].map((step, i) => (
              <div
                key={i}
                className="relative bg-white/5 border border-white/10 rounded-2xl p-6 backdrop-blur-sm transition-all duration-300 ease-out hover:bg-white/10 hover:border-brand-turquoise/40 hover:-translate-y-1.5 hover:shadow-xl motion-reduce:transition-none motion-reduce:hover:translate-y-0"
              >
                <div className="font-cairo font-black text-brand-turquoise/50 text-5xl leading-none mb-4">
                  {String(i + 1).padStart(2, '0')}
                </div>
                <h3 className="font-cairo font-bold text-white text-base mb-2 leading-snug">
                  {step.title}
                </h3>
                <p className="font-tajawal text-sm text-white/70 leading-relaxed">
                  {step.body}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ========== JOURNEY SECTION — hidden via SHOW_JOURNEY flag ========== */}
      {SHOW_JOURNEY && (
      <section
        ref={journeyRef}
        className="py-24 lg:py-32 bg-gradient-to-b from-background via-background to-background relative overflow-hidden"
        data-testid="journey-section"
      >
        <div className="absolute inset-0 opacity-[0.02]" style={{ backgroundImage: `url(${BG_PATTERN})`, backgroundSize: '200% auto', backgroundPosition: 'center center' }} />
        <div className="absolute top-0 left-0 w-[500px] h-[500px] rounded-full bg-brand-turquoise/5 blur-[120px] animate-pulse" style={{ animationDuration: '8s' }} />
        <div className="absolute bottom-0 right-0 w-[400px] h-[400px] rounded-full bg-brand-purple/5 blur-[100px] animate-pulse" style={{ animationDelay: '2s', animationDuration: '8s' }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[300px] h-[300px] rounded-full bg-cyan-500/3 blur-[80px]" />

        <div className={`relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 transition-all duration-1000 ${journeyVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-12'}`}>
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2.5 bg-gradient-to-r from-brand-turquoise/15 to-brand-turquoise/5 border border-brand-turquoise/25 rounded-full px-5 py-2.5 mb-6 backdrop-blur-sm animate-pulse-glow">
              <Zap className="h-4 w-4 text-brand-turquoise animate-pulse" />
              <span className="text-brand-turquoise text-sm font-tajawal font-medium">{t('smartTransformationJourney')}</span>
            </div>
            <h2 className="font-cairo text-3xl md:text-5xl lg:text-[3.5rem] font-black text-foreground mb-5 leading-tight">
              {t('theSchoolsJourneyToSmartSystems')}
            </h2>
            <p className="text-lg md:text-xl text-muted-foreground font-tajawal max-w-2xl mx-auto leading-relaxed">
              {t('fromScatteredDataToClearEducationalDecisions')}
            </p>
          </div>

          {/* Journey Steps Navigation */}
          <div
            className="flex justify-center gap-1.5 sm:gap-2 mb-12 flex-wrap"
            onMouseEnter={() => setJourneyPaused(true)}
            onMouseLeave={() => setJourneyPaused(false)}
          >
            {journeySteps.map((step, i) => (
              <button
                key={i}
                onClick={() => setActiveJourneyStep(i)}
                className={`flex items-center gap-2 px-4 sm:px-5 py-3 rounded-2xl font-cairo text-sm font-medium transition-all duration-500 border ${
                  activeJourneyStep === i
                    ? 'bg-gradient-to-r from-brand-turquoise to-cyan-500 text-white shadow-xl shadow-brand-turquoise/25 scale-105 border-brand-turquoise/50'
                    : 'bg-card/80 text-muted-foreground hover:bg-muted border-border/50 hover:border-brand-turquoise/30 hover:shadow-md'
                }`}
              >
                <span className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold transition-all ${
                  activeJourneyStep === i ? 'bg-white/25 text-white' : 'bg-brand-turquoise/10 text-brand-turquoise'
                }`}>{step.phase}</span>
                <span className="hidden sm:inline">{step.title}</span>
              </button>
            ))}
          </div>

          {/* Journey Content */}
          <div
            className="grid lg:grid-cols-5 gap-6 lg:gap-8 items-stretch"
            onMouseEnter={() => setJourneyPaused(true)}
            onMouseLeave={() => setJourneyPaused(false)}
          >
            <div className="lg:col-span-3 flex">
              <Card className="relative overflow-hidden border border-border/50 bg-card/80 backdrop-blur-sm p-7 md:p-8 transition-all duration-500 hover:border-brand-turquoise/20 hover:shadow-xl group w-full h-full flex flex-col">
                <div className="absolute top-0 end-0 w-40 h-40 bg-gradient-to-bl from-brand-turquoise/5 to-transparent rounded-bl-full" />
                <div className="absolute bottom-0 start-0 w-32 h-32 bg-gradient-to-tr from-brand-purple/3 to-transparent rounded-tr-full" />
                <div className="absolute inset-0 animate-shimmer opacity-0 group-hover:opacity-100 transition-opacity" />

                <div className="relative z-10">
                  <div className="flex gap-2.5 mb-6">
                    {journeySteps[activeJourneyStep].icons.map((DataIcon, i) => (
                      <span
                        key={`${activeJourneyStep}-${i}`}
                        className="w-11 h-11 rounded-xl bg-gradient-to-br from-brand-turquoise/10 to-brand-turquoise/5 border border-brand-turquoise/15 flex items-center justify-center animate-scale-in shadow-sm"
                        style={{ animationDelay: `${i * 80}ms` }}
                        aria-hidden="true"
                      >
                        <DataIcon className="h-5 w-5 text-brand-turquoise" strokeWidth={1.5} />
                      </span>
                    ))}
                  </div>

                  <div className="mb-6">
                    <h3 className="font-cairo text-2xl font-bold text-foreground mb-2">
                      {journeySteps[activeJourneyStep].title}
                    </h3>
                    <p className="text-brand-turquoise font-cairo font-semibold text-sm flex items-center gap-2">
                      <Sparkles className="h-3.5 w-3.5 animate-pulse" />
                      {journeySteps[activeJourneyStep].subtitle}
                    </p>
                  </div>

                  <p className="text-muted-foreground font-tajawal leading-relaxed mb-8 text-[15px]">
                    {journeySteps[activeJourneyStep].content}
                  </p>

                  {/* Progress Timeline */}
                  <div className="flex items-center gap-3 pt-5 border-t border-border/30">
                    <div className="flex-1 relative h-1.5 bg-muted rounded-full overflow-hidden">
                      <div
                        className="absolute inset-y-0 start-0 bg-gradient-to-r from-brand-turquoise to-cyan-500 rounded-full transition-all duration-500 ease-in-out"
                        style={{ width: `${((activeJourneyStep + 1) / journeySteps.length) * 100}%` }}
                        aria-hidden="true"
                      />
                      <div className="absolute inset-0 flex">
                        {journeySteps.map((_, i) => (
                          <button
                            key={i}
                            onClick={() => setActiveJourneyStep(i)}
                            aria-label={`Step ${i + 1}`}
                            className="flex-1 h-full bg-transparent hover:bg-white/5 transition-colors"
                          />
                        ))}
                      </div>
                    </div>
                    <span className="text-xs text-muted-foreground font-mono bg-muted/50 px-2 py-1 rounded-lg">
                      {journeySteps[activeJourneyStep].phase}/04
                    </span>
                  </div>
                </div>
              </Card>
            </div>

            <div className="lg:col-span-2 flex flex-col h-full">
              {/* Large Hakim Visual Showcase — swaps per active step */}
              <div className="relative bg-gradient-to-br from-brand-purple/8 via-white/60 to-brand-turquoise/8 dark:from-brand-purple/15 dark:via-slate-900/50 dark:to-brand-turquoise/15 border border-brand-purple/20 rounded-3xl overflow-hidden shadow-xl shadow-brand-purple/10 flex-1 flex flex-col">
                <div className="absolute top-8 -end-10 w-44 h-44 rounded-full bg-brand-turquoise/20 blur-3xl" aria-hidden="true" />
                <div className="absolute bottom-8 -start-10 w-36 h-36 rounded-full bg-brand-purple/20 blur-3xl" aria-hidden="true" />

                <div className="absolute top-4 start-4 z-20 bg-gradient-to-r from-brand-purple to-violet-600 text-white text-[11px] font-cairo font-bold px-3 py-1 rounded-full shadow-lg flex items-center gap-1.5">
                  <Brain className="h-3 w-3" strokeWidth={2} aria-hidden="true" />
                  {t('hakim')}
                </div>

                <div className="absolute top-4 end-4 z-20 font-mono text-[11px] font-bold text-brand-purple bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm px-2.5 py-1 rounded-lg border border-brand-purple/20">
                  {journeySteps[activeJourneyStep].phase}/04
                </div>

                <div className="relative z-10 flex-1 flex items-end justify-center px-4 pt-12 pb-2 min-h-[320px]">
                  <img
                    key={activeJourneyStep}
                    src={[
                      '/hakim-poses/friendly-greeting.png',
                      '/hakim-poses/detecting-patterns.png',
                      '/hakim-poses/giving-instructions.png',
                      '/hakim-poses/positive-feedback.png',
                    ][activeJourneyStep]}
                    alt={t('hakim')}
                    className="hakim-img w-full h-full max-h-[460px] object-contain object-bottom animate-fade-in drop-shadow-2xl"
                  />
                </div>

                {/* AI Powered Badge — repositioned as composition footer */}
                <div className="relative z-10 flex items-center justify-center gap-2 bg-gradient-to-r from-brand-turquoise/10 to-brand-purple/10 border-t border-brand-turquoise/15 px-4 py-3 backdrop-blur-sm">
                  <Brain className="h-4 w-4 text-brand-turquoise animate-pulse" aria-hidden="true" />
                  <span className="text-xs font-tajawal text-foreground/70">
                    {t('aipoweredIntelligence')}
                  </span>
                  <Sparkles className="h-3.5 w-3.5 text-brand-purple animate-pulse" style={{ animationDelay: '0.5s' }} aria-hidden="true" />
                </div>
              </div>

            </div>
          </div>
        </div>
      </section>
      )}

      {/* ========== AI INTELLIGENCE SECTION — hidden via SHOW_AI_SECTION flag ========== */}
      {SHOW_AI_SECTION && (
      <section
        ref={aiRef}
        className="py-24 lg:py-32 bg-brand-navy relative overflow-hidden scroll-mt-24"
        id="solutions"
        data-testid="ai-section"
      >
        <div className="absolute inset-0 opacity-[0.05]" style={{ backgroundImage: `url(${BG_PATTERN})`, backgroundSize: '200% auto', backgroundPosition: 'center center' }} />
        <div className="absolute inset-0">
          <div className="absolute top-[15%] left-[5%] w-[500px] h-[500px] rounded-full bg-brand-purple/8 blur-[120px] animate-pulse" style={{ animationDuration: '10s' }} />
          <div className="absolute bottom-[10%] right-[5%] w-[400px] h-[400px] rounded-full bg-brand-turquoise/8 blur-[100px] animate-pulse" style={{ animationDelay: '3s', animationDuration: '10s' }} />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[700px] rounded-full bg-cyan-500/3 blur-[150px] animate-pulse" style={{ animationDuration: '12s' }} />
        </div>

        {/* Floating AI particles */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          {[
            'top-[10%] left-[15%]', 'top-[30%] right-[10%]', 'bottom-[20%] left-[8%]',
            'top-[60%] right-[20%]', 'bottom-[40%] left-[25%]', 'top-[20%] right-[35%]',
          ].map((pos, i) => (
            <div key={i} className={`absolute ${pos} w-1 h-1 rounded-full bg-brand-turquoise/30 animate-float`}
              style={{ animationDelay: `${i * 0.8}s`, animationDuration: `${4 + i * 0.5}s` }}
            />
          ))}
        </div>

        <div className={`relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 transition-all duration-1000 ${aiVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-12'}`}>
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2.5 bg-gradient-to-r from-brand-purple/25 to-brand-turquoise/15 border border-brand-purple/30 rounded-full px-5 py-2.5 mb-6 backdrop-blur-sm">
              <Brain className="h-4 w-4 text-brand-turquoise animate-pulse" />
              <span className="text-white/80 text-sm font-tajawal font-medium">{t('artificialIntelligence')}</span>
              <Sparkles className="h-3.5 w-3.5 text-brand-purple animate-pulse" style={{ animationDelay: '0.5s' }} />
            </div>
            <h2 className="font-cairo text-3xl md:text-5xl lg:text-[3.5rem] font-black text-white mb-5 leading-tight">
              {t('theIntelligenceBehindNassaq')}
            </h2>
            <p className="text-white/40 text-lg md:text-xl font-tajawal max-w-2xl mx-auto leading-relaxed">
              {t('aiIsTheBackboneOfTheSystem')}
            </p>
          </div>

          {/* AI Capability Tabs */}
          <div className="flex justify-center gap-2 mb-10 flex-wrap"
            onMouseEnter={() => setAIPaused(true)}
            onMouseLeave={() => setAIPaused(false)}
          >
            {aiCapabilities.map((cap, i) => {
              const Icon = cap.icon;
              return (
                <button
                  key={i}
                  onClick={() => setActiveAIStep(i)}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-xl font-cairo text-sm transition-all duration-500 border ${
                    activeAIStep === i
                      ? 'bg-white/10 border-brand-turquoise/40 text-white shadow-lg backdrop-blur-sm'
                      : 'border-white/5 text-white/50 hover:text-white/80 hover:border-white/15 hover:bg-white/5'
                  }`}
                >
                  <Icon className={`h-4 w-4 ${activeAIStep === i ? 'text-brand-turquoise' : ''}`} />
                  <span className="hidden sm:inline">{cap.title}</span>
                </button>
              );
            })}
          </div>

          <div className="grid lg:grid-cols-2 gap-8 lg:gap-10 items-stretch">
            {/* AI Feature Card */}
            <div
              className="flex h-full"
              onMouseEnter={() => setAIPaused(true)}
              onMouseLeave={() => setAIPaused(false)}
            >
              <Card className="relative overflow-hidden bg-white/[0.04] border-white/10 rounded-2xl p-7 md:p-8 transition-all duration-500 backdrop-blur-sm hover:bg-white/[0.06] hover:border-brand-turquoise/20 group flex flex-col w-full h-full">
                <div className="absolute top-0 end-0 w-48 h-48 bg-gradient-to-bl from-brand-turquoise/5 to-transparent rounded-bl-full" />
                <div className="absolute inset-0 animate-shimmer opacity-0 group-hover:opacity-100 transition-opacity" />

                <div className="relative z-10 flex flex-col flex-1">
                  <div className="flex items-center gap-4 mb-6">
                    <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-brand-turquoise to-cyan-500 flex items-center justify-center shadow-xl shadow-brand-turquoise/25 group-hover:scale-110 transition-transform">
                      {(() => { const Icon = aiCapabilities[activeAIStep].icon; return <Icon className="h-7 w-7 text-white" />; })()}
                    </div>
                    <div>
                      <h3 className="font-cairo text-xl font-bold text-white">
                        {aiCapabilities[activeAIStep].title}
                      </h3>
                      <p className="text-brand-turquoise font-cairo text-sm flex items-center gap-1.5">
                        <Sparkles className="h-3 w-3 animate-pulse" />
                        {aiCapabilities[activeAIStep].subtitle}
                      </p>
                    </div>
                  </div>

                  <p className="text-white/50 font-tajawal leading-relaxed mb-7 text-[15px]">
                    {aiCapabilities[activeAIStep].content}
                  </p>

                  {/* Hakim Quote */}
                  <div className="flex items-start gap-3 bg-gradient-to-br from-white/95 to-gray-50/95 rounded-xl p-4 shadow-lg border border-white/20">
                    <div className="relative flex-shrink-0">
                      <img src="/hakim-poses/ai-thinking.png" alt={t('hakim')} className="hakim-img w-16 h-16 rounded-xl object-contain border-2 border-brand-turquoise/40 shadow-md bg-gradient-to-br from-cyan-50 to-violet-50 p-1" />
                    </div>
                    <p className="text-gray-700 text-sm font-tajawal leading-relaxed">
                      <span className="text-brand-turquoise font-bold font-cairo">{t('hakim2')}</span>
                      {aiCapabilities[activeAIStep].hakimSays}
                    </p>
                  </div>

                  <div className="flex items-center gap-3 mt-auto pt-4 border-t border-white/5">
                    <div className="flex-1 relative h-1.5 bg-white/10 rounded-full overflow-hidden">
                      <div
                        className="absolute inset-y-0 start-0 bg-gradient-to-r from-brand-turquoise to-cyan-500 rounded-full transition-all duration-500 ease-in-out"
                        style={{ width: `${((activeAIStep + 1) / aiCapabilities.length) * 100}%` }}
                        aria-hidden="true"
                      />
                      <div className="absolute inset-0 flex">
                        {aiCapabilities.map((_, i) => (
                          <button
                            key={i}
                            onClick={() => setActiveAIStep(i)}
                            aria-label={`AI capability ${i + 1}`}
                            className="flex-1 h-full bg-transparent hover:bg-white/5 transition-colors"
                          />
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </Card>
            </div>

            {/* Analysis Layers + CTA */}
            <div
              className="flex flex-col h-full gap-5"
              onMouseEnter={() => setAIPaused(true)}
              onMouseLeave={() => setAIPaused(false)}
            >
              <div className="relative overflow-hidden bg-white/[0.04] border border-white/10 rounded-2xl p-6 backdrop-blur-sm">
                <div className="absolute inset-0 animate-shimmer opacity-30" />
                <div className="relative z-10">
                  <div className="flex items-center gap-3 mb-6">
                    <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-brand-purple to-violet-600 flex items-center justify-center shadow-lg shadow-brand-purple/20">
                      <Layers className="h-5 w-5 text-white" />
                    </div>
                    <div>
                      <h4 className="text-white font-cairo font-bold">{t('analysisLayers')}</h4>
                      <p className="text-white/30 text-xs font-tajawal">{t('multidimensionalAnalysis')}</p>
                    </div>
                  </div>
                  <div className="space-y-4">
                    {aiAnalysisLayers.map((layer, i) => (
                      <div key={i} className="group">
                        <div className="flex items-center gap-3 mb-2">
                          <div className={`w-9 h-9 rounded-lg bg-gradient-to-br ${layer.color} flex items-center justify-center flex-shrink-0 shadow-lg transition-all duration-300 group-hover:scale-110 group-hover:shadow-xl`}>
                            <layer.icon className="h-4 w-4 text-white" />
                          </div>
                          <span className="text-white/70 text-sm font-tajawal flex-1 group-hover:text-white/90 transition-colors">{layer.label}</span>
                          <span className="text-brand-turquoise text-xs font-mono font-bold bg-brand-turquoise/10 px-2.5 py-1 rounded-lg">{layer.pct}%</span>
                        </div>
                        <div className="ms-12 h-2 bg-white/5 rounded-full overflow-hidden">
                          <div
                            className={`h-full bg-gradient-to-r ${layer.color} rounded-full transition-all duration-1000 ease-out relative`}
                            style={{ width: aiVisible ? `${layer.pct}%` : '0%', transitionDelay: `${i * 200}ms` }}
                          >
                            <span className="absolute end-0 top-1/2 -translate-y-1/2 w-2.5 h-2.5 bg-white rounded-full shadow-md opacity-80" />
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <button
                onClick={() => {
                  const hakimBtn = document.querySelector('[data-testid="hakim-toggle-btn"]');
                  if (hakimBtn) hakimBtn.click();
                }}
                className="mt-auto w-full flex items-center justify-center gap-3 bg-gradient-to-r from-brand-turquoise to-cyan-500 hover:from-brand-turquoise-light hover:to-cyan-400 text-white rounded-2xl px-6 py-4 font-cairo font-bold text-lg shadow-xl shadow-brand-turquoise/25 hover:shadow-2xl hover:shadow-brand-turquoise/40 transition-all active:scale-[0.98] hover:scale-[1.02] animate-pulse-glow"
              >
                <Brain className="h-5 w-5" />
                {t('askHakim2')}
                <Sparkles className="h-4 w-4 animate-pulse" />
              </button>
            </div>
          </div>
        </div>
      </section>
      )}

      {/* ========== ECOSYSTEM SECTION ========== */}
      <section
        ref={ecoRef}
        className="py-24 lg:py-32 bg-gradient-to-b from-background via-background to-background relative overflow-hidden scroll-mt-24"
        id="ecosystem"
        data-testid="ecosystem-section"
      >
        <div className="absolute inset-0 opacity-[0.02]" style={{ backgroundImage: `url(${BG_PATTERN})`, backgroundSize: '200% auto', backgroundPosition: 'center center' }} />
        <div className="absolute top-0 right-0 w-[500px] h-[500px] rounded-full bg-brand-turquoise/5 blur-[120px] animate-pulse" style={{ animationDuration: '10s' }} />
        <div className="absolute bottom-[20%] left-0 w-[400px] h-[400px] rounded-full bg-brand-purple/5 blur-[100px] animate-pulse" style={{ animationDelay: '3s', animationDuration: '8s' }} />

        <div className={`relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 transition-all duration-1000 ${ecoVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-12'}`}>
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2.5 bg-gradient-to-r from-brand-turquoise/15 to-brand-turquoise/5 border border-brand-turquoise/25 rounded-full px-5 py-2.5 mb-6 backdrop-blur-sm animate-pulse-glow">
              <Shield className="h-4 w-4 text-brand-turquoise animate-pulse" />
              <span className="text-brand-turquoise text-sm font-tajawal font-medium">{t('completeEcosystem')}</span>
            </div>
            <h2 className="font-cairo text-3xl md:text-5xl lg:text-[3.5rem] font-black text-foreground mb-5 leading-tight">
              {t('onePlatformOneEducationalEcosystem')}
            </h2>
            <p className="text-muted-foreground text-lg md:text-xl font-tajawal max-w-2xl mx-auto leading-relaxed">
              {t('nassaqServesAllPartiesInTheEducationalProcess')}
            </p>
          </div>

          {/* Role Cards */}
          <div
            className="grid grid-cols-1 sm:grid-cols-3 gap-3 md:gap-4 mb-10"
            onMouseEnter={() => setEcosystemPaused(true)}
            onMouseLeave={() => setEcosystemPaused(false)}
          >
            {ecosystemRoles.map((role, i) => (
              <button
                key={i}
                onClick={() => setActiveEcosystemRole(i)}
                className={`text-start rounded-2xl p-5 md:p-6 transition-all duration-500 border-2 group ${
                  activeEcosystemRole === i
                    ? 'bg-gradient-to-br from-brand-turquoise/10 to-brand-turquoise/[0.03] border-brand-turquoise shadow-xl shadow-brand-turquoise/25 scale-[1.03]'
                    : 'bg-card/80 border-border/50 hover:border-brand-turquoise/30 hover:shadow-md opacity-70 hover:opacity-100'
                }`}
              >
                <div className={`w-12 h-12 md:w-14 md:h-14 rounded-2xl flex items-center justify-center mb-3 md:mb-4 transition-all duration-300 ${
                  activeEcosystemRole === i
                    ? 'bg-gradient-to-br from-brand-turquoise to-cyan-500 shadow-xl shadow-brand-turquoise/25 scale-110'
                    : 'bg-brand-turquoise/10 group-hover:bg-brand-turquoise/15 group-hover:scale-105'
                }`}>
                  <role.icon className={`h-6 w-6 md:h-7 md:w-7 ${activeEcosystemRole === i ? 'text-white' : 'text-brand-turquoise'}`} />
                </div>
                <h3 className="font-cairo text-base md:text-lg font-bold text-foreground mb-1">{role.role}</h3>
                <p className="text-[11px] md:text-xs text-muted-foreground font-tajawal line-clamp-2">{role.title}</p>
                {activeEcosystemRole === i && (
                  <div className="mt-2 flex items-center gap-1.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-brand-turquoise animate-pulse" />
                    <span className="text-[10px] text-brand-turquoise font-tajawal">{t('active')}</span>
                  </div>
                )}
              </button>
            ))}
          </div>

          {/* Role Detail Card */}
          <Card
            className="relative overflow-hidden border border-border/50 bg-card/80 backdrop-blur-sm p-7 md:p-8 transition-all duration-500 hover:border-brand-turquoise/15 hover:shadow-xl group"
            onMouseEnter={() => setEcosystemPaused(true)}
            onMouseLeave={() => setEcosystemPaused(false)}
          >
            <div className="absolute top-0 end-0 w-48 h-48 bg-gradient-to-bl from-brand-turquoise/5 to-transparent rounded-bl-full" />
            <div className="absolute bottom-0 start-0 w-36 h-36 bg-gradient-to-tr from-brand-purple/3 to-transparent rounded-tr-full" />
            <div className="absolute inset-0 animate-shimmer opacity-0 group-hover:opacity-100 transition-opacity" />

            <div className="relative z-10 grid lg:grid-cols-2 gap-8 items-stretch">
              <div className="flex flex-col h-full">
                <div className="flex items-center gap-4 mb-5">
                  <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-brand-turquoise to-cyan-500 flex items-center justify-center shadow-xl shadow-brand-turquoise/25">
                    {(() => { const Icon = ecosystemRoles[activeEcosystemRole].icon; return <Icon className="h-7 w-7 text-white" />; })()}
                  </div>
                  <div>
                    <span className="text-brand-turquoise text-xs font-cairo font-bold">{ecosystemRoles[activeEcosystemRole].role}</span>
                    <h3 className="font-cairo text-xl md:text-2xl font-bold text-foreground">
                      {ecosystemRoles[activeEcosystemRole].title}
                    </h3>
                  </div>
                </div>

                <p className="text-muted-foreground font-tajawal leading-relaxed mb-6 text-[15px]">
                  {ecosystemRoles[activeEcosystemRole].content}
                </p>

                <div className="flex items-start gap-3">
                  <div className="relative flex-shrink-0">
                    <img src="/hakim-poses/giving-instructions.png" alt={t('hakim')} className="hakim-img w-16 h-16 rounded-xl object-contain border-2 border-brand-purple/40 shadow-lg bg-gradient-to-br from-violet-50 to-cyan-50 p-1" />
                    <div className="absolute -bottom-1 -end-1 w-5 h-5 rounded-md bg-brand-purple flex items-center justify-center border border-card">
                      <Brain className="h-2.5 w-2.5 text-white" />
                    </div>
                  </div>
                  <div className="flex-1 bg-gradient-to-br from-white to-gray-50 dark:from-white/95 dark:to-gray-100/90 rounded-xl p-4 shadow-md border border-brand-purple/15">
                    <p className="text-gray-700 text-sm font-tajawal leading-relaxed">
                      <span className="text-brand-purple font-bold font-cairo">{t('hakim2')}</span>
                      {ecosystemRoles[activeEcosystemRole].hakimSays}
                    </p>
                  </div>
                </div>
              </div>

              {/* Large dynamic Hakim character card — swaps per active role */}
              <div className="relative bg-gradient-to-br from-brand-purple/8 via-white/60 to-brand-turquoise/8 dark:from-brand-purple/15 dark:via-slate-900/50 dark:to-brand-turquoise/15 border border-brand-purple/20 rounded-3xl overflow-hidden shadow-xl shadow-brand-purple/10 flex flex-col h-full min-h-[360px]">
                <div className="absolute top-8 -end-10 w-44 h-44 rounded-full bg-brand-turquoise/20 blur-3xl" aria-hidden="true" />
                <div className="absolute bottom-8 -start-10 w-36 h-36 rounded-full bg-brand-purple/20 blur-3xl" aria-hidden="true" />

                {/* Hakim badge top-start */}
                <div className="absolute top-4 start-4 z-20 bg-gradient-to-r from-brand-purple to-violet-600 text-white text-[11px] font-cairo font-bold px-3 py-1 rounded-full shadow-lg flex items-center gap-1.5">
                  <Brain className="h-3 w-3" strokeWidth={2} aria-hidden="true" />
                  {t('hakim')}
                </div>

                {/* Active role label top-end */}
                <div className="absolute top-4 end-4 z-20 font-cairo text-[11px] font-bold text-brand-purple bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm px-2.5 py-1 rounded-lg border border-brand-purple/20">
                  {ecosystemRoles[activeEcosystemRole].role}
                </div>

                {/* Dynamic Hakim image */}
                <div className="relative z-10 flex-1 flex items-end justify-center px-4 pt-12 pb-2 min-h-[280px]">
                  <img
                    key={activeEcosystemRole}
                    src={[
                      '/hakim-poses/congratulating-student.png',
                      '/hakim-poses/listening.png',
                      '/hakim-poses/open-hands-welcoming.png',
                    ][activeEcosystemRole]}
                    alt={t('hakim')}
                    className="hakim-img w-full h-full max-h-[420px] object-contain object-bottom animate-fade-in drop-shadow-2xl"
                  />
                </div>

                {/* AI Powered footer chip */}
                <div className="relative z-10 flex items-center justify-center gap-2 bg-gradient-to-r from-brand-turquoise/10 to-brand-purple/10 border-t border-brand-turquoise/15 px-4 py-3 backdrop-blur-sm">
                  <Brain className="h-4 w-4 text-brand-turquoise animate-pulse" aria-hidden="true" />
                  <span className="text-[11px] font-tajawal text-muted-foreground font-medium">
                    {t('landingEcoAiChip')}
                  </span>
                  <Sparkles className="h-3.5 w-3.5 text-brand-purple animate-pulse" style={{ animationDelay: '0.5s' }} aria-hidden="true" />
                </div>
              </div>
            </div>
          </Card>
        </div>
      </section>

      {/* ========== PROOF SECTION — funnel step 3: build trust ========== */}
      <section
        className="relative bg-brand-navy py-20 lg:py-28 overflow-hidden scroll-mt-24"
        id="proof"
        data-testid="proof-section"
      >
        {/* nassaq background image — same treatment as hero & how-it-works */}
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: `url('/nassaq-background.png')` }}
          aria-hidden="true"
        />
        <div
          className="absolute inset-0 opacity-[0.06]"
          style={{ backgroundImage: `url(${BG_PATTERN})`, backgroundSize: '200% auto', backgroundPosition: 'center center' }}
          aria-hidden="true"
        />
        <div className="absolute inset-0 bg-brand-navy/75" aria-hidden="true" />

        <div className="relative max-w-6xl mx-auto px-6">
          <div className="text-center max-w-2xl mx-auto mb-14">
            <div className="inline-flex items-center gap-2 bg-brand-turquoise/15 border border-brand-turquoise/30 rounded-full ps-2 pe-4 py-1.5 mb-5 backdrop-blur-sm">
              <Shield className="h-4 w-4 text-brand-turquoise" strokeWidth={1.5} aria-hidden="true" />
              <span className="font-tajawal text-sm text-brand-turquoise">
                {t('landingProofEyebrow')}
              </span>
            </div>
            <h2 className="font-cairo font-bold text-white text-3xl sm:text-4xl lg:text-5xl leading-tight mb-4">
              {t('landingProofHeadingLead')}<span className="text-brand-turquoise">...</span>{t('landingProofHeadingTail')}
            </h2>
          </div>

          {/* Growth indicators — two equal cards, server-sanitized display
              strings only. No raw aggregate counts are sent to the browser. */}
          {(() => {
            const schoolsDisplay = formatGrowthIndicator(growthIndicators.schools);
            const teachersDisplay = formatGrowthIndicator(growthIndicators.teachers);
            if (!schoolsDisplay && !teachersDisplay) return null;

            const cards = [
              {
                show: !!schoolsDisplay,
                value: schoolsDisplay,
                title: t('landingProofCard1Title'),
                sub: t('landingProofCard1Sub'),
                icon: Building2,
              },
              {
                show: !!teachersDisplay,
                value: teachersDisplay,
                title: t('landingProofCard2Title'),
                sub: t('landingProofCard2Sub'),
                icon: Users,
              },
            ].filter((c) => c.show);

            return (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mb-12 max-w-4xl mx-auto">
                {cards.map((card, idx) => {
                  const Icon = card.icon;
                  return (
                    <div
                      key={idx}
                      className="relative bg-white/5 border border-brand-turquoise/30 rounded-2xl px-8 py-10 text-center shadow-xl backdrop-blur-sm flex flex-col items-center justify-between min-h-[240px]"
                    >
                      <div className="w-12 h-12 rounded-xl bg-brand-turquoise/15 flex items-center justify-center mb-4">
                        <Icon className="h-6 w-6 text-brand-turquoise" strokeWidth={1.5} aria-hidden="true" />
                      </div>
                      <p className="font-tajawal text-white font-semibold text-xl mb-2">
                        {card.title}
                      </p>
                      <div className="font-cairo font-black text-white text-5xl lg:text-6xl mb-3 tracking-tight">
                        {card.value}
                      </div>
                      <p className="font-tajawal text-white/60 text-xs">
                        {card.sub}
                      </p>
                    </div>
                  );
                })}
              </div>
            );
          })()}

          {/* Trust pillars — factual claims about architecture, not fake testimonials */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {[
              {
                icon: Zap,
                title: t('landingProofPillar1Title'),
                body: t('landingProofPillar1Body'),
              },
              {
                icon: Globe,
                title: t('landingProofPillar2Title'),
                body: t('landingProofPillar2Body'),
              },
              {
                icon: Sparkles,
                title: t('landingProofPillar3Title'),
                body: t('landingProofPillar3Body'),
              },
            ].map((pillar, i) => {
              const Icon = pillar.icon;
              return (
                <div
                  key={i}
                  className="bg-white/5 border border-white/10 rounded-2xl p-7 backdrop-blur-sm transition-all duration-300 ease-out hover:bg-white/10 hover:border-brand-turquoise/40 hover:-translate-y-1.5 hover:shadow-xl motion-reduce:transition-none motion-reduce:hover:translate-y-0"
                >
                  <div className="w-12 h-12 rounded-xl bg-brand-turquoise/15 flex items-center justify-center mb-5">
                    <Icon className="h-6 w-6 text-brand-turquoise" strokeWidth={1.5} aria-hidden="true" />
                  </div>
                  <h3 className="font-cairo font-bold text-white text-lg mb-2">
                    {pillar.title}
                  </h3>
                  <p className="font-tajawal text-sm text-white/70 leading-relaxed">
                    {pillar.body}
                  </p>
                </div>
              );
            })}
          </div>

          {/* Honesty note — we don't have testimonials yet, so we say so */}
          <p className="font-tajawal text-center text-white/50 text-xs mt-10">
            {t('landingProofHonestyNote')}
          </p>
        </div>
      </section>

      {/* ========== FAQ SECTION — funnel step 4: handle objections ========== */}
      <section
        className="relative py-24 lg:py-32 bg-gradient-to-b from-background via-background to-background overflow-hidden scroll-mt-24"
        id="faq"
        data-testid="faq-section"
      >
        {/* journey-style ambient background — pattern + soft blur orbs */}
        <div
          className="absolute inset-0 opacity-[0.02]"
          style={{ backgroundImage: `url(${BG_PATTERN})`, backgroundSize: '200% auto', backgroundPosition: 'center center' }}
          aria-hidden="true"
        />
        <div className="absolute top-0 right-0 w-[500px] h-[500px] rounded-full bg-brand-turquoise/5 blur-[120px] animate-pulse" style={{ animationDuration: '10s' }} aria-hidden="true" />
        <div className="absolute bottom-0 left-0 w-[400px] h-[400px] rounded-full bg-brand-purple/5 blur-[100px] animate-pulse" style={{ animationDelay: '3s', animationDuration: '8s' }} aria-hidden="true" />

        <div className="relative max-w-3xl mx-auto px-6">
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-2.5 bg-gradient-to-r from-brand-turquoise/15 to-brand-turquoise/5 border border-brand-turquoise/25 rounded-full px-5 py-2.5 mb-6 backdrop-blur-sm animate-pulse-glow">
              <Lightbulb className="h-4 w-4 text-brand-turquoise animate-pulse" strokeWidth={1.5} aria-hidden="true" />
              <span className="text-brand-turquoise text-sm font-tajawal font-medium">
                {t('landingFaqEyebrow')}
              </span>
            </div>
            <h2 className="font-cairo font-bold text-3xl md:text-4xl text-brand-navy dark:text-white text-center mb-12 leading-tight">
              {t('landingFaqHeading')}
            </h2>
          </div>

          <div className="space-y-3">
            {Array.from({ length: FAQ_TOTAL }, (_, idx) => idx + 1)
              .slice(0, faqExpanded ? FAQ_TOTAL : FAQ_COLLAPSED_COUNT)
              .map((n) => (
              <details
                key={n}
                className="group bg-card/80 border border-border/50 rounded-2xl overflow-hidden backdrop-blur-sm transition-all duration-300 hover:border-brand-turquoise/30 hover:shadow-md open:border-brand-turquoise/40 open:shadow-xl open:shadow-brand-turquoise/5"
              >
                <summary className="flex items-center justify-between gap-4 px-6 py-5 cursor-pointer list-none focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-turquoise focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-2xl">
                  <span className="font-cairo font-bold text-foreground text-base text-start">
                    {t(`landingFaqQ${n}`)}
                  </span>
                  <span className="shrink-0 w-8 h-8 rounded-lg bg-brand-turquoise/10 flex items-center justify-center transition-colors group-hover:bg-brand-turquoise/15 group-open:bg-gradient-to-br group-open:from-brand-turquoise group-open:to-cyan-500">
                    <ChevronDown className="h-4 w-4 text-brand-turquoise group-open:text-white group-open:rotate-180 transition-all" strokeWidth={2} aria-hidden="true" />
                  </span>
                </summary>
                <div className="px-6 pb-5 -mt-1">
                  <p className="font-tajawal text-sm text-muted-foreground leading-relaxed">
                    {t(`landingFaqA${n}`)}
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
                data-testid="landing-faq-toggle"
                className="inline-flex items-center gap-2 font-cairo font-bold text-sm px-6 py-3 rounded-xl bg-card/80 border border-brand-turquoise/30 text-brand-turquoise hover:bg-brand-turquoise/10 hover:border-brand-turquoise/50 transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-turquoise focus-visible:ring-offset-2 focus-visible:ring-offset-background"
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

      {/* ========== PRICING TIERS — hidden via SHOW_PRICING flag ========== */}
      {SHOW_PRICING && <section
        className="relative py-20 lg:py-28 scroll-mt-24 overflow-hidden"
        data-testid="pricing-section"
        id="plans"
      >
        {/* navy + nassaq texture — same treatment as hero, how-it-works, proof & CTA */}
        <div className="absolute inset-0 bg-brand-navy" aria-hidden="true" />
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: `url('/nassaq-background.png')` }}
          aria-hidden="true"
        />
        <div
          className="absolute inset-0 opacity-[0.06]"
          style={{ backgroundImage: `url(${BG_PATTERN})`, backgroundSize: '200% auto', backgroundPosition: 'center center' }}
          aria-hidden="true"
        />
        <div className="absolute inset-0 bg-brand-navy/75" aria-hidden="true" />
        <div className="absolute top-1/4 left-0 w-[500px] h-[500px] rounded-full bg-brand-turquoise/5 blur-3xl animate-pulse" style={{ animationDuration: '10s' }} aria-hidden="true" />
        <div className="absolute bottom-0 right-0 w-[400px] h-[400px] rounded-full bg-brand-purple/5 blur-3xl animate-pulse" style={{ animationDelay: '2s', animationDuration: '8s' }} aria-hidden="true" />

        <div className="relative max-w-6xl mx-auto px-6">
          <div className="text-center max-w-2xl mx-auto mb-14">
            <div className="inline-flex items-center gap-2 bg-white/10 border border-white/25 rounded-full ps-2 pe-4 py-1.5 mb-5 backdrop-blur-sm">
              <Award className="h-4 w-4 text-white" strokeWidth={1.5} aria-hidden="true" />
              <span className="font-tajawal text-sm font-medium text-white">
                {t('landingPricingEyebrow')}
              </span>
            </div>
            <h2 className="font-cairo font-bold text-white text-3xl sm:text-4xl lg:text-5xl leading-tight mb-4">
              {t('landingPricingHeadingLead')}<span className="text-brand-turquoise">Pilot</span>{t('landingPricingHeadingTail')}
            </h2>
            <p className="font-tajawal text-base text-white/70 leading-relaxed">
              {t('landingPricingSubheading')}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 items-stretch">
            {[
              {
                badge: null,
                name: t('landingPricingPilotName'),
                tagline: t('landingPricingPilotTagline'),
                price: t('landingPricingPilotPrice'),
                priceNote: t('landingPricingPilotPriceNote'),
                metaKey: 'landingPricingPilotMeta',
                ctaKey: 'landingPricingPilotCta',
                ctaLink: '/register',
                features: [
                  t('landingPricingPilotFeature1'),
                  t('landingPricingPilotFeature2'),
                  t('landingPricingPilotFeature3'),
                  t('landingPricingPilotFeature4'),
                ],
                highlight: false,
              },
              {
                badge: t('landingPricingSchoolsBadge'),
                name: t('landingPricingSchoolsName'),
                tagline: t('landingPricingSchoolsTagline'),
                price: t('landingPricingSchoolsPrice'),
                priceNote: t('landingPricingSchoolsPriceNote'),
                metaKey: 'landingPricingSchoolsMeta',
                ctaKey: 'landingPricingSchoolsCta',
                ctaLink: '/register',
                features: [
                  t('landingPricingSchoolsFeature1'),
                  t('landingPricingSchoolsFeature2'),
                  t('landingPricingSchoolsFeature3'),
                  t('landingPricingSchoolsFeature4'),
                  t('landingPricingSchoolsFeature5'),
                  t('landingPricingSchoolsFeature6'),
                  t('landingPricingSchoolsFeature7'),
                ],
                highlight: true,
              },
              {
                badge: null,
                name: t('landingPricingGroupsName'),
                tagline: t('landingPricingGroupsTagline'),
                price: t('landingPricingGroupsPrice'),
                priceNote: t('landingPricingGroupsPriceNote'),
                metaKey: 'landingPricingGroupsMeta',
                ctaKey: 'landingPricingGroupsCta',
                ctaLink: '/register',
                features: [
                  t('landingPricingGroupsFeature1'),
                  t('landingPricingGroupsFeature2'),
                  t('landingPricingGroupsFeature3'),
                  t('landingPricingGroupsFeature4'),
                  t('landingPricingGroupsFeature5'),
                  t('landingPricingGroupsFeature6'),
                ],
                highlight: false,
              },
            ].map((tier, i) => (
              <div
                key={i}
                aria-label={tier.highlight ? t('landingPricingRecommendedAria') : undefined}
                className={`relative flex flex-col rounded-2xl p-7 backdrop-blur-sm transition-all duration-300 ${
                  tier.highlight
                    ? 'bg-white/10 text-white border-2 border-brand-turquoise shadow-2xl shadow-brand-turquoise/20 scale-100 md:scale-[1.03]'
                    : 'bg-white/5 border border-white/10 hover:bg-white/10 hover:border-brand-turquoise/40 hover:shadow-lg'
                }`}
              >
                {tier.badge && (
                  <div className="absolute -top-3 inset-x-0 flex justify-center">
                    <span className="bg-gradient-to-r from-brand-turquoise to-cyan-500 text-white font-cairo text-xs font-bold px-4 py-1 rounded-full shadow-lg shadow-brand-turquoise/30">
                      {tier.badge}
                    </span>
                  </div>
                )}

                <h3 className="font-cairo font-bold text-xl mb-1 text-white">
                  {tier.name}
                </h3>
                <p className="font-tajawal text-sm mb-6 text-white/65">
                  {tier.tagline}
                </p>

                <div className="mb-2">
                  <span className={`font-cairo font-black text-3xl ${tier.highlight ? 'text-brand-turquoise' : 'text-white'}`}>
                    {tier.price}
                  </span>
                </div>
                <p className="font-tajawal text-xs mb-6 text-white/55">
                  {tier.priceNote}
                </p>

                <Button
                  asChild
                  className={`w-full font-cairo rounded-lg h-11 mb-6 ${
                    tier.highlight
                      ? 'bg-gradient-to-r from-brand-turquoise to-cyan-500 hover:from-brand-turquoise-light hover:to-cyan-400 text-white hover:text-white shadow-lg shadow-brand-turquoise/25'
                      : 'bg-white/10 border border-white/20 hover:bg-white/15 hover:border-brand-turquoise/40 text-white hover:text-white backdrop-blur-sm'
                  }`}
                >
                  <Link to={tier.ctaLink}>{t(tier.ctaKey)}</Link>
                </Button>

                <ul className="space-y-3 flex-1">
                  {tier.features.map((feature, j) => (
                    <li key={j} className="flex items-start gap-2.5">
                      <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0 text-brand-turquoise" strokeWidth={2} aria-hidden="true" />
                      <span className="font-tajawal text-sm leading-snug text-white/85">
                        {feature}
                      </span>
                    </li>
                  ))}
                </ul>

                <p className="font-tajawal text-xs mt-6 pt-5 border-t text-white/55 border-white/10">
                  {t(tier.metaKey)}
                </p>
              </div>
            ))}
          </div>

          <p className="font-tajawal text-center text-white/60 text-sm mt-10">
            {t('landingPricingFooter')}
          </p>
        </div>
      </section>}

      {/* ========== CALL TO ACTION ========== */}
      <section
        className="py-24 lg:py-32 relative overflow-hidden"
        data-testid="cta-section"
      >
        {/* nassaq background image — same treatment as hero, how-it-works & proof */}
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: `url('/nassaq-background.png')` }}
          aria-hidden="true"
        />
        <div
          className="absolute inset-0 opacity-[0.06]"
          style={{ backgroundImage: `url(${BG_PATTERN})`, backgroundSize: '200% auto', backgroundPosition: 'center center' }}
          aria-hidden="true"
        />
        <div className="absolute inset-0 bg-brand-navy/75" aria-hidden="true" />
        <div className="absolute top-0 left-0 w-[500px] h-[500px] rounded-full bg-brand-turquoise/10 blur-[120px] animate-pulse" style={{ animationDuration: '8s' }} aria-hidden="true" />
        <div className="absolute bottom-0 right-0 w-[400px] h-[400px] rounded-full bg-brand-purple/10 blur-[100px] animate-pulse" style={{ animationDelay: '2s', animationDuration: '8s' }} aria-hidden="true" />

        <div className="relative max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          {/* eyebrow — matches journey/faq recipe */}
          <div className="inline-flex items-center gap-2.5 bg-gradient-to-r from-brand-turquoise/15 to-brand-turquoise/5 border border-brand-turquoise/30 rounded-full px-5 py-2.5 mb-6 backdrop-blur-sm animate-pulse-glow">
            <Sparkles className="h-4 w-4 text-brand-turquoise animate-pulse" strokeWidth={1.5} aria-hidden="true" />
            <span className="text-brand-turquoise text-sm font-tajawal font-medium">
              {t('landingCtaEyebrow')}
            </span>
          </div>

          <h2 className="font-cairo text-3xl md:text-5xl lg:text-[3.5rem] font-black text-white mb-5 leading-tight">
            {t('readyToStart')}
          </h2>
          <p className="text-lg md:text-xl text-white/75 font-tajawal max-w-2xl mx-auto leading-relaxed mb-12">
            {t('landingCtaSubheading')}
          </p>

          <div className="grid md:grid-cols-2 gap-5 mb-12">
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-6 text-start hover:border-brand-turquoise/40 hover:bg-white/[0.07] hover:shadow-lg hover:-translate-y-0.5 transition-all group">
              <div className="w-12 h-12 rounded-xl bg-brand-turquoise/15 flex items-center justify-center mb-4 group-hover:bg-brand-turquoise/25 transition-colors">
                <Building2 className="h-6 w-6 text-brand-turquoise" strokeWidth={1.5} aria-hidden="true" />
              </div>
              <h3 className="font-cairo text-xl font-bold text-white mb-2">{t('ifYouAreASchool')}</h3>
              <p className="text-white/70 text-sm font-tajawal leading-relaxed">
                {t('makeYourSchoolMoreOrganizedAndClearWithNassaqPlatf')}
              </p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-6 text-start hover:border-brand-purple/40 hover:bg-white/[0.07] hover:shadow-lg hover:-translate-y-0.5 transition-all group">
              <div className="w-12 h-12 rounded-xl bg-brand-purple/15 flex items-center justify-center mb-4 group-hover:bg-brand-purple/25 transition-colors">
                <UserCheck className="h-6 w-6 text-brand-purple" strokeWidth={1.5} aria-hidden="true" />
              </div>
              <h3 className="font-cairo text-xl font-bold text-white mb-2">{t('ifYouAreATeacher')}</h3>
              <p className="text-white/70 text-sm font-tajawal leading-relaxed">
                {t('startOrganizingYourClassesNowAndMakeClassroomManag')}
              </p>
            </div>
          </div>

          <div className="flex items-center justify-center gap-5 mb-12">
            <div className="relative flex-shrink-0">
              <div className="absolute -inset-2 rounded-full bg-brand-turquoise/20 blur-xl animate-pulse" aria-hidden="true" />
              <img src="/hakim-poses/motivating.png" alt={t('hakim')} className="hakim-img relative w-24 h-24 rounded-2xl object-contain border-2 border-brand-turquoise shadow-xl flex-shrink-0 bg-gradient-to-br from-cyan-50 to-violet-50 p-1" />
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl px-6 py-4 max-w-lg text-start shadow-sm">
              <p className="text-white/85 font-tajawal text-base leading-relaxed">
                <span className="text-brand-turquoise font-bold font-cairo">{t('hakim2')}</span>
                {t('goodEducationStartsWithGoodDecisionsAndGoodDecisio')}
              </p>
            </div>
          </div>

          <Button asChild size="lg" className="bg-gradient-to-r from-brand-turquoise to-cyan-500 hover:from-brand-turquoise-light hover:to-cyan-400 text-white rounded-2xl h-16 px-14 text-xl font-cairo font-bold shadow-2xl shadow-brand-turquoise/30 hover:shadow-2xl hover:shadow-brand-turquoise/40 transition-all hover:scale-[1.03]" data-testid="cta-register-btn">
            <Link to="/register" className="flex items-center gap-3">
              {t('registerNow')}
              {isRTL ? <ArrowLeft className="h-6 w-6" strokeWidth={1.5} aria-hidden="true" /> : <ArrowRight className="h-6 w-6" strokeWidth={1.5} aria-hidden="true" />}
            </Link>
          </Button>
        </div>
      </section>

      {/* ========== ONBOARDING JOURNEY — light breather before footer ========== */}
      <section
        className="relative py-20 lg:py-24 bg-white border-t border-slate-200/70"
        id="onboarding"
        data-testid="onboarding-section"
      >
        <div className="relative max-w-6xl mx-auto px-6">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <div className="inline-flex items-center gap-2.5 bg-gradient-to-r from-brand-turquoise/15 to-brand-turquoise/5 border border-brand-turquoise/25 rounded-full px-5 py-2.5 mb-5 w-fit mx-auto">
              <span className="text-brand-turquoise text-sm font-tajawal font-medium">
                {t('landingOnboardingEyebrow')}
              </span>
            </div>
            <h2 className="font-cairo font-bold text-3xl md:text-4xl text-brand-navy leading-tight mb-4">
              {t('landingOnboardingHeading')}
            </h2>
            <p className="font-tajawal text-base md:text-lg text-slate-600 leading-relaxed">
              {t('landingOnboardingIntro')}
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {[1, 2, 3, 4].map((n) => (
              <div
                key={n}
                className="relative bg-slate-50 border border-slate-200/70 rounded-2xl p-6 hover:border-brand-turquoise/40 hover:shadow-md transition-all"
                data-testid={`onboarding-step-${n}`}
              >
                <div className="flex items-baseline gap-3 mb-3">
                  <span className="font-cairo font-black text-3xl text-brand-turquoise/40">
                    {n.toLocaleString(isRTL ? 'ar-EG' : 'en-US')}
                  </span>
                  <span className="h-px flex-1 bg-slate-200" aria-hidden="true" />
                </div>
                <h3 className="font-cairo font-bold text-base text-brand-navy mb-2 text-start">
                  {t(`landingOnboardingStep${n}Title`)}
                </h3>
                <p className="font-tajawal text-sm text-slate-600 leading-relaxed text-start">
                  {t(`landingOnboardingStep${n}Desc`)}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <Footer />
      <HakimAssistant />
    </div>
  );
};
