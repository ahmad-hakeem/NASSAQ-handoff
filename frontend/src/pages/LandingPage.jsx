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
  Globe,
  Sun,
  Moon,
  ClipboardCheck,
  Activity,
  Star,
  Layers,
  ChevronDown,
  Zap,
  Shield,
  ArrowRight,
} from 'lucide-react';

const LOGO_WHITE = '/nassaq-logo-white.png';
const BG_PATTERN = '/nassaq-pattern.png';
const HAKIM_CHARACTER = '/hakim-poses/friendly-greeting.png';
const HAKIM_HERO_WELCOME = '/hakim-poses/welcome.png';


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

export const LandingPage = () => {
  const { isRTL, toggleLanguage, toggleTheme, isDark } = useTheme();
  const { t } = useTranslation();
  const { api } = useAuth();
  const [activeJourneyStep, setActiveJourneyStep] = useState(0);
  const [activeAIStep, setActiveAIStep] = useState(0);
  const [activeEcosystemRole, setActiveEcosystemRole] = useState(0);

  const [journeyPaused, setJourneyPaused] = useState(false);
  const [aiPaused, setAIPaused] = useState(false);
  const [ecosystemPaused, setEcosystemPaused] = useState(false);

  // Landing-page anchor sections — kept in nav order so the navbar can render
  // and IntersectionObserver can highlight the active section in sync.
  const navSections = useMemo(() => ([
    { id: 'how-it-works', ar: 'كيف يعمل', en: 'How it works' },
    { id: 'solutions',    ar: 'الحلول',  en: 'Solutions' },
    { id: 'ecosystem',    ar: 'الأدوار',  en: 'Roles' },
    { id: 'proof',        ar: 'النتائج', en: 'Results' },
    { id: 'faq',          ar: 'الأسئلة الشائعة', en: 'FAQ' },
    { id: 'plans',        ar: 'الباقات', en: 'Plans' },
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

  const [platformStats, setPlatformStats] = useState({
    schools: 0,
    students: 0,
    teachers: 0,
    parents: 0,
  });

  const hakimMessages = useMemo(() => isRTL
    ? [
        'مرحبًا… أنا حكيم. العقل الذكي داخل منصة نَسَّق. أساعد المدارس على فهم بياناتها وتحويلها إلى قرارات تعليمية واضحة.',
        'هل ترغب أن أريك كيف يمكن للذكاء الاصطناعي أن يساعد مدرستك؟',
        'من الحضور إلى الأداء الأكاديمي… أنا أرى الصورة كاملة وأكتشف ما تعنيه الأرقام.',
      ]
    : [
        "Hello… I'm Hakim. The smart mind inside NASSAQ. I help schools understand their data and turn it into clear educational decisions.",
        'Would you like me to show you how AI can help your school?',
        'From attendance to academic performance… I see the full picture and discover what the numbers mean.',
      ], [isRTL]);

  const typedHakimText = useTypedText(hakimMessages, 35, 4000);

  const [journeyRef, journeyVisible] = useScrollReveal();
  const [aiRef, aiVisible] = useScrollReveal();
  const [ecoRef, ecoVisible] = useScrollReveal();

  useEffect(() => {
    const fetchStats = async () => {
      // Landing page is unauthenticated. The full /public/stats payload is
      // intentionally platform-admin gated (audit C-4). For the social-proof
      // line we use the curated public schools-count endpoint, which exposes
      // only a single aggregate integer with no per-tenant detail.
      try {
        const response = await api.get('/public/schools-count');
        const count = Number(response?.data?.count) || 0;
        setPlatformStats((prev) => ({ ...prev, schools: count }));
      } catch (error) {
        // Silent — social-proof block hides itself when the count is 0.
      }
    };
    fetchStats();
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
      setActiveEcosystemRole((prev) => (prev + 1) % 4);
    }, 3500);
    return () => clearInterval(interval);
  }, [ecosystemPaused]);

  const journeySteps = isRTL ? [
    {
      title: 'الواقع اليومي للمدرسة',
      subtitle: 'كل مدرسة تنتج آلاف البيانات يوميًا',
      content: 'تسجيل حضور الطلاب، تقييم الواجبات، تسجيل السلوك، مشاركة الطلاب داخل الفصل، نتائج الاختبارات، ملاحظات المعلمين. لكن هذه البيانات غالبًا تكون موزعة ومجزأة.',
      hakimSays: 'المدارس تولد آلاف البيانات كل يوم… لكن القليل منها يستطيع تحويل هذه البيانات إلى معرفة.',
      icons: [BarChart3, Calendar, Brain, BookOpen],
      phase: '01',
    },
    {
      title: 'جمع البيانات داخل نَسَّق',
      subtitle: 'هنا يبدأ دور منصة نَسَّق',
      content: 'يقوم النظام بجمع كل هذه البيانات داخل منصة واحدة: الحضور والانصراف، الأداء الأكاديمي، السلوك اليومي، التفاعل داخل الحصة، الواجبات والتقييمات.',
      hakimSays: 'مهمتي هي تنظيم هذه البيانات وتحويلها إلى صورة واضحة للمدرسة.',
      icons: [Database, TrendingUp, CheckCircle2, Award],
      phase: '02',
    },
    {
      title: 'تحليل البيانات بالذكاء الاصطناعي',
      subtitle: 'عندما يبدأ الذكاء الاصطناعي بالتحليل',
      content: 'اكتشاف الطلاب الذين يحتاجون دعمًا، تحليل الأنماط السلوكية داخل الفصول، رصد تراجع الأداء الأكاديمي، تحديد فرص تحسين المشاركة.',
      hakimSays: 'أنا لا أعرض الأرقام فقط… بل أكتشف ما تعنيه هذه الأرقام.',
      icons: [Brain, Lightbulb, TrendingUp, Target],
      phase: '03',
    },
    {
      title: 'اتخاذ القرار',
      subtitle: 'من البيانات… إلى القرار',
      content: 'خطط دعم الطلاب، تقارير الأداء، قرارات تعليمية دقيقة مبنية على بيانات حقيقية تساعد في تحسين جودة العملية التعليمية.',
      hakimSays: 'البيانات وحدها لا تغيّر التعليم… لكن القرارات الصحيحة تفعل.',
      icons: [CheckCircle2, Award, Target, TrendingUp],
      phase: '04',
    },
  ] : [
    {
      title: 'Daily School Reality',
      subtitle: 'Every school produces thousands of data points daily',
      content: 'Recording attendance, evaluating assignments, recording behavior, student participation, test results, teacher notes. But this data is often distributed and fragmented.',
      hakimSays: 'Schools generate thousands of data points every day... but few can turn this data into knowledge.',
      icons: [BarChart3, Calendar, Brain, BookOpen],
      phase: '01',
    },
    {
      title: 'Data Collection in NASSAQ',
      subtitle: 'Here is where NASSAQ platform begins',
      content: 'The system collects all this data in one platform: attendance, academic performance, daily behavior, in-class interaction, assignments and assessments.',
      hakimSays: 'My mission is to organize this data and turn it into a clear picture for the school.',
      icons: [Database, TrendingUp, CheckCircle2, Award],
      phase: '02',
    },
    {
      title: 'AI Data Analysis',
      subtitle: 'When AI starts analyzing',
      content: 'Discovering students who need support, analyzing behavioral patterns, tracking academic decline, identifying participation improvement opportunities.',
      hakimSays: "I don't just display numbers... I discover what these numbers mean.",
      icons: [Brain, Lightbulb, TrendingUp, Target],
      phase: '03',
    },
    {
      title: 'Decision Making',
      subtitle: 'From Data... to Decisions',
      content: 'Student support plans, performance reports, precise educational decisions based on real data that help improve education quality.',
      hakimSays: "Data alone doesn't change education... but the right decisions do.",
      icons: [CheckCircle2, Award, Target, TrendingUp],
      phase: '04',
    },
  ];

  const aiCapabilities = isRTL ? [
    {
      title: 'تحليل أداء الطلاب',
      subtitle: 'فهم الطالب قبل أن تظهر المشكلة',
      content: 'يقوم الذكاء الاصطناعي بتحليل الحضور، المشاركة، الواجبات، التقييمات، والسلوك بشكل مستمر لاكتشاف الطلاب الذين يحتاجون دعمًا مبكرًا.',
      hakimSays: 'يمكنني اكتشاف الطالب الذي يحتاج دعمًا… قبل أن تتحول المشكلة إلى أزمة تعليمية.',
      icon: Activity,
    },
    {
      title: 'الجداول الدراسية الذكية',
      subtitle: 'عندما تصبح الجداول الدراسية عملية ذكية',
      content: 'إنشاء جدول مدرسي متوازن يراعي المعلمين، الفصول، المواد، القاعات، وعدد الحصص. الذكاء الاصطناعي يحلل آلاف الاحتمالات.',
      hakimSays: 'يمكنني تحليل آلاف الاحتمالات في ثوانٍ لبناء جدول مدرسي متوازن.',
      icon: Calendar,
    },
    {
      title: 'التقارير التعليمية الذكية',
      subtitle: 'التقارير التي تفهمها… لا مجرد تقرأها',
      content: 'بدلاً من عرض الأرقام فقط، يقوم النظام بتحويل البيانات إلى رؤى تعليمية واضحة: أداء الفصول، تطور الطلاب، الأنماط السلوكية.',
      hakimSays: 'الأرقام وحدها لا تكفي… مهمتي هي تحويلها إلى رؤية تساعد المدرسة على اتخاذ القرار.',
      icon: BarChart3,
    },
    {
      title: 'التنبيهات المبكرة',
      subtitle: 'رصد المشكلات قبل حدوثها',
      content: 'يراقب النظام أنماط السلوك والأداء باستمرار ويرسل تنبيهات مبكرة عند اكتشاف تراجع في أداء طالب أو فصل بأكمله.',
      hakimSays: 'كل يوم تولد المدرسة آلاف البيانات… مهمتي هي أن أفهم ما تعنيه هذه البيانات.',
      icon: Database,
    },
  ] : [
    {
      title: 'Student Performance Analysis',
      subtitle: 'Understanding the student before problems appear',
      content: 'AI continuously analyzes attendance, participation, assignments, assessments, and behavior to discover students who need early support.',
      hakimSays: 'I can detect a student who needs support... before the problem becomes an educational crisis.',
      icon: Activity,
    },
    {
      title: 'Smart Scheduling',
      subtitle: 'When scheduling becomes an intelligent process',
      content: 'Creating a balanced school schedule considering teachers, classes, subjects, rooms, and sessions. AI analyzes thousands of possibilities.',
      hakimSays: 'I can analyze thousands of possibilities in seconds to build a balanced schedule.',
      icon: Calendar,
    },
    {
      title: 'Smart Educational Reports',
      subtitle: 'Reports you understand... not just read',
      content: 'Instead of just displaying numbers, the system transforms data into clear educational insights: class performance, student progress, behavioral patterns.',
      hakimSays: "Numbers alone aren't enough... my mission is to turn them into vision that helps the school make decisions.",
      icon: BarChart3,
    },
    {
      title: 'Early Alerts',
      subtitle: 'Detecting issues before they happen',
      content: 'The system continuously monitors behavior and performance patterns and sends early alerts when detecting decline in a student or entire class performance.',
      hakimSays: 'Every day the school generates thousands of data points... my mission is to understand what this data means.',
      icon: Database,
    },
  ];

  const aiAnalysisLayers = isRTL
    ? [
        { label: 'الحضور والانضباط', icon: ClipboardCheck, color: 'from-emerald-500 to-emerald-600', pct: 92 },
        { label: 'الواجبات والتقييمات', icon: BookOpen, color: 'from-sky-500 to-sky-600', pct: 78 },
        { label: 'المشاركة الصفية', icon: Activity, color: 'from-amber-500 to-amber-600', pct: 85 },
        { label: 'السلوك اليومي', icon: Star, color: 'from-purple-500 to-purple-600', pct: 88 },
        { label: 'الأداء الأكاديمي', icon: TrendingUp, color: 'from-rose-500 to-rose-600', pct: 74 },
      ]
    : [
        { label: 'Attendance & Discipline', icon: ClipboardCheck, color: 'from-emerald-500 to-emerald-600', pct: 92 },
        { label: 'Homework & Assessments', icon: BookOpen, color: 'from-sky-500 to-sky-600', pct: 78 },
        { label: 'Class Participation', icon: Activity, color: 'from-amber-500 to-amber-600', pct: 85 },
        { label: 'Daily Behaviour', icon: Star, color: 'from-purple-500 to-purple-600', pct: 88 },
        { label: 'Academic Performance', icon: TrendingUp, color: 'from-rose-500 to-rose-600', pct: 74 },
      ];

  const ecosystemRoles = isRTL ? [
    {
      role: 'مدير المدرسة',
      title: 'المدرسة كاملة… في لوحة تحكم واحدة',
      content: 'عندما يدخل مدير المدرسة إلى نَسَّق، يرى صورة كاملة عن المدرسة: حضور الطلاب، أداء الفصول، نشاط المعلمين، السلوك الطلابي، تقارير الأداء.',
      hakimSays: 'بدل البحث في عشرات التقارير… يمكنني عرض صورة كاملة عن المدرسة في شاشة واحدة.',
      icon: Building2,
      gradient: 'from-brand-turquoise to-cyan-600',
    },
    {
      role: 'المعلم',
      title: 'إدارة الحصة أصبحت أكثر ذكاءً',
      content: 'تسجيل الحضور، متابعة تفاعل الطلاب، تقييم الإجابات، تسجيل السلوك، إضافة التقييمات. كل ذلك في واجهة بسيطة وسريعة.',
      hakimSays: 'أثناء الحصة… أساعد المعلم على فهم مستوى التفاعل داخل الفصل.',
      icon: UserCheck,
      gradient: 'from-emerald-500 to-emerald-600',
    },
    {
      role: 'المعلم المستقل',
      title: 'مساحة عمل كاملة… للمعلم الذي يدير طلابه بنفسه',
      content: 'مساحة عمل مستقلة بطلابك وأولياء أمورهم وخططك وجدولك — دون الحاجة لمدرسة. دعوات أولياء الأمور بضغطة، خطط الدروس، جدول الحصص، تقارير الأداء، وتعاون اختياري مع زميل في حصة مشتركة.',
      hakimSays: 'لست بحاجة لمدرسة لتعمل باحترافية… أرتّب لك يومك التعليمي وأرصد إشارات كل طالب على حدة.',
      icon: BookOpen,
      gradient: 'from-brand-purple to-violet-600',
    },
    {
      role: 'ولي الأمر',
      title: 'متابعة حقيقية لأداء الابن',
      content: 'متابعة الحضور، الواجبات، السلوك، التقييمات عبر لوحة بسيطة وواضحة ومتاحة في أي وقت.',
      hakimSays: 'عندما يكون ولي الأمر جزءًا من الصورة… تصبح العملية التعليمية أكثر نجاحًا.',
      icon: Users,
      gradient: 'from-amber-500 to-orange-600',
    },
  ] : [
    {
      role: 'School Principal',
      title: 'The entire school... in one dashboard',
      content: 'See a complete picture of the school: student attendance, class performance, teacher activity, student behavior, performance reports.',
      hakimSays: 'Instead of searching through dozens of reports... I can display a complete picture on one screen.',
      icon: Building2,
      gradient: 'from-brand-turquoise to-cyan-600',
    },
    {
      role: 'Teacher',
      title: 'Class management is now smarter',
      content: 'Record attendance, track interaction, evaluate answers, record behavior, add assessments. All in a simple and fast interface.',
      hakimSays: 'During class... I help the teacher understand the level of interaction in the classroom.',
      icon: UserCheck,
      gradient: 'from-emerald-500 to-emerald-600',
    },
    {
      role: 'Independent Teacher',
      title: 'A full workspace... for the teacher running their own students',
      content: 'A standalone workspace with your students, their parents, your lesson plans and your schedule — no school required. One-click parent invitations, lesson planning, class timetable, performance reports, and optional co-teaching with a colleague on a shared class.',
      hakimSays: "You don't need a school to work professionally... I organize your teaching day and track signals for every student individually.",
      icon: BookOpen,
      gradient: 'from-brand-purple to-violet-600',
    },
    {
      role: 'Parent',
      title: "Real follow-up on your child's performance",
      content: "Follow attendance, assignments, behavior, assessments through a simple and clear dashboard available anytime.",
      hakimSays: 'When parents are part of the picture... education becomes more successful.',
      icon: Users,
      gradient: 'from-amber-500 to-orange-600',
    },
  ];

  return (
    <div className="min-h-screen" dir={isRTL ? 'rtl' : 'ltr'} data-testid="landing-page">
      {/* ========== STICKY GLASS NAVBAR ========== */}
      <header
        className="sticky top-0 z-50 bg-white/90 backdrop-blur-md border-b border-slate-200"
        data-testid="header"
      >
        <nav className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          {/* RTL Start: Logo */}
          <Link to="/" className="flex items-center gap-2 shrink-0" data-testid="navbar-logo">
            <img
              src="/nassaq-logo.png"
              alt={isRTL ? 'شعار نَسَّق' : 'NASSAQ logo'}
              className="w-10 h-10 rounded-xl object-cover shadow-md ring-1 ring-brand-navy/10"
            />
            <div className="hidden sm:flex flex-col leading-tight">
              <span className="font-cairo font-bold text-brand-navy text-lg">
                {isRTL ? 'نَسَّق' : 'NASSAQ'}
              </span>
              <span className="font-tajawal text-[10px] text-slate-500">
                {isRTL ? 'من البيانات للقرار' : 'From data to decisions'}
              </span>
            </div>
          </Link>

          {/* Center: Anchor Links + IT pill */}
          <div className="hidden lg:flex items-center gap-1">
            {navSections.map(({ id, ar, en }) => {
              const isActive = activeSection === id;
              return (
                <a
                  key={id}
                  href={`#${id}`}
                  onClick={(e) => handleNavClick(e, id)}
                  aria-current={isActive ? 'true' : undefined}
                  className={`font-tajawal text-sm font-medium px-4 py-2 rounded-lg transition-colors ${
                    isActive
                      ? 'bg-brand-navy text-white shadow-sm'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                  data-testid={`nav-link-${id}`}
                >
                  {isRTL ? ar : en}
                </a>
              );
            })}
            <Link
              to="/for-teachers"
              className="ms-2 inline-flex items-center gap-2 font-tajawal text-sm font-medium px-4 py-2 rounded-lg bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 hover:text-brand-navy shadow-sm transition-all"
              data-testid="navbar-teacher-pill"
            >
              <span className="w-5 h-5 rounded-full bg-brand-turquoise text-white flex items-center justify-center text-[10px] font-cairo font-bold" aria-hidden="true">
                ن
              </span>
              {isRTL ? 'معلم نسق' : 'NASSAQ Teacher'}
            </Link>
          </div>

          {/* RTL End: Auth actions + utility toggles */}
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={toggleLanguage}
              className="hidden sm:inline-flex items-center justify-center h-9 w-9 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
              data-testid="language-toggle"
              aria-label={isRTL ? 'تغيير اللغة' : 'Toggle language'}
            >
              <Globe className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={toggleTheme}
              className="hidden sm:inline-flex items-center justify-center h-9 w-9 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
              data-testid="theme-toggle"
              aria-label={isDark ? 'Light mode' : 'Dark mode'}
            >
              {isDark
                ? <Sun className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />
                : <Moon className="h-4 w-4" strokeWidth={1.5} aria-hidden="true" />}
            </button>
            <Link
              to="/login"
              className="font-tajawal text-sm font-medium px-4 py-2 rounded-lg text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
              data-testid="login-link"
            >
              {isRTL ? 'تسجيل الدخول' : 'Log in'}
            </Link>
            <Link
              to="/register"
              className="font-tajawal text-sm font-medium px-6 py-2.5 rounded-lg bg-brand-navy text-white hover:bg-brand-navy-light hover:text-white shadow-sm hover:shadow-md active:scale-95 transition-all"
              data-testid="register-link"
            >
              {isRTL ? 'تسجيل' : 'Sign up'}
            </Link>
          </div>
        </nav>
      </header>

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
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">

            {/* RTL Start = Right: Content */}
            <div className="space-y-8 text-start order-2 lg:order-1 lg:[&]:order-none">
              {/* Eyebrow badge — names the audience, not the product */}
              <div className="inline-flex items-center gap-2 bg-brand-turquoise/15 border border-brand-turquoise/30 rounded-full ps-2 pe-4 py-1.5 backdrop-blur-sm">
                <CheckCircle2 className="h-4 w-4 text-brand-turquoise" />
                <span className="font-tajawal text-sm text-brand-turquoise">
                  {isRTL ? 'لمدراء المدارس · معاهد التعليم · المعلمين المستقلين' : 'For principals, training institutes & independent teachers'}
                </span>
              </div>

              {/* H1 — outcome-specific, pain-aware */}
              <h1
                className="font-cairo font-bold text-white leading-tight text-4xl sm:text-5xl lg:text-6xl"
                data-testid="platform-name"
              >
                <span className="text-brand-turquoise">نَسَّق</span>
              </h1>

              {/* Sub-heading — names the mechanism, doesn't repeat the headline */}
              <p className="font-tajawal text-lg text-white/80 leading-relaxed max-w-xl">
                {isRTL
                  ? 'منصة تساعدك على فهم رحلة الطالب بشكل أعمق.'
                  : 'A platform that helps you understand each student\'s journey more deeply.'}
              </p>

              {/* CTAs */}
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  asChild
                  className="bg-brand-turquoise hover:bg-brand-turquoise-light text-white hover:text-white font-cairo rounded-lg px-8 py-3 h-auto text-base shadow-lg hover:shadow-xl hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.98] transition-all"
                  data-testid="hero-cta-btn"
                >
                  <Link to="/register" className="flex items-center gap-2">
                    {isRTL ? 'ابدأ تجربتك المجانية' : 'Start your free trial'}
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
                    {isRTL ? 'شاهد كيف يعمل (دقيقتان)' : 'See how it works (2 min)'}
                  </a>
                </Button>
              </div>

              {/* Risk-reversal microcopy under CTA */}
              <p className="font-tajawal text-xs text-white/60 -mt-4">
                {isRTL
                  ? 'بدون بطاقة ائتمان · إعداد خلال 24 ساعة · إلغاء في أي وقت'
                  : 'No credit card · Setup in 24 hours · Cancel anytime'}
              </p>

              {/* Social proof — only renders when we have real platform numbers */}
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
                    {isRTL ? (
                      <>
                        <span className="font-bold text-white">
                          <AnimatedCounter target={platformStats.schools} />
                          {' '}مدرسة
                        </span>{' '}
                        تستخدم نسق الآن
                      </>
                    ) : (
                      <>
                        <span className="font-bold text-white">
                          <AnimatedCounter target={platformStats.schools} />
                          {' '}schools
                        </span>{' '}
                        use NASSAQ today
                      </>
                    )}
                  </p>
                </div>
              )}

              {/* Features ticker */}
              <div className="flex flex-wrap items-center gap-x-6 gap-y-2 pt-4 border-t border-white/10">
                {[
                  isRTL ? 'جاهز خلال 24 ساعة' : 'Ready in 24 hours',
                  isRTL ? 'بدون تعقيد تقني' : 'No technical setup',
                  isRTL ? 'يعمل مع نظامك الحالي' : 'Works with your current stack',
                ].map((item, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-brand-turquoise" />
                    <span className="font-tajawal text-sm text-white/80">{item}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* RTL End = Left: Dashboard mockup */}
            <div className="order-1 lg:order-2">
              <div
                className="relative w-full bg-white rounded-2xl shadow-2xl border border-slate-100 overflow-hidden transform hover:scale-[1.02] transition-transform duration-500"
                data-testid="hero-mockup"
              >
                {/* Browser chrome */}
                <div className="flex items-center justify-between gap-2 px-4 h-9 bg-slate-50 border-b border-slate-100">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                    <span className="font-tajawal text-[11px] text-slate-500">{isRTL ? 'مباشر' : 'Live'}</span>
                  </div>
                  <span className="font-tajawal text-[11px] text-slate-500">
                    {isRTL ? 'نسق · لوحة مدير المدرسة' : 'NASSAQ · Principal Dashboard'}
                  </span>
                  <div className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-slate-200" />
                    <span className="w-2 h-2 rounded-full bg-slate-200" />
                    <span className="w-2 h-2 rounded-full bg-slate-200" />
                  </div>
                </div>

                {/* Real product screenshot */}
                <img
                  src="/images/landing-dashboard-preview.png"
                  alt={isRTL ? 'لقطة من لوحة مدير المدرسة في نَسَّق' : 'NASSAQ principal dashboard screenshot'}
                  className="block w-full h-auto"
                  loading="lazy"
                />
              </div>

              {/* Footnote below mockup */}
              <p className="font-tajawal text-xs text-slate-500 text-center mt-4">
                {isRTL
                  ? 'لقطة حقيقية من لوحة مدير المدرسة'
                  : 'Real screenshot from the principal dashboard'}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ========== PAIN SECTION — funnel step 1: agitate the problem ========== */}
      <section
        className="relative bg-slate-50 py-20 lg:py-28"
        data-testid="pain-section"
      >
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-center max-w-2xl mx-auto mb-14">
            <div className="inline-flex items-center gap-2 bg-brand-turquoise/10 border border-brand-turquoise/30 rounded-full ps-2 pe-4 py-1.5 mb-5">
              <Bell className="h-4 w-4 text-brand-turquoise" strokeWidth={1.5} aria-hidden="true" />
              <span className="font-tajawal text-sm text-brand-turquoise">
                {isRTL ? 'إشارات تعرفها كل مدرسة' : 'Signals every school knows'}
              </span>
            </div>
            <h2 className="font-cairo font-bold text-brand-navy text-3xl sm:text-4xl lg:text-5xl leading-tight mb-4">
              {isRTL ? (
                <>هل تواجه هذه الإشارات <span className="text-brand-turquoise">كل أسبوع؟</span></>
              ) : (
                <>Are these signals showing up <span className="text-brand-turquoise">every week?</span></>
              )}
            </h2>
            <p className="font-tajawal text-base text-slate-600 leading-relaxed">
              {isRTL
                ? 'لو تكررت أي اثنتين منها، فأنت تخسر وقتًا وقرارات وفُرص تدخّل — والبيانات موجودة، لكنها مبعثرة.'
                : 'If any two of these recur, you are losing time, decisions and intervention windows — the data exists, but it is scattered.'}
            </p>
          </div>

          {/* 3-role pain columns — same problem from 3 angles */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {[
              {
                roleAr: 'الإدارة',
                roleEn: 'Administration',
                icon: Building2,
                titleAr: 'القرارات تتأخّر حتى تظهر المشكلة.',
                titleEn: 'Decisions are delayed until the problem surfaces.',
                bodyAr: 'الإدارة تتدخل بعد انخفاض النتائج فعليًا — وليس عند ظهور المؤشرات الأكاديمية الأولى.',
                bodyEn: 'Leadership intervenes after grades drop — not when the first academic signals appear.',
                tagAr: 'التراجع يُكتشف متأخرًا',
                tagEn: 'Decline caught too late',
              },
              {
                roleAr: 'طاقم التدريس',
                roleEn: 'Teaching staff',
                icon: GraduationCap,
                titleAr: 'الوقت يُستهلك في المتابعة لا في التدريس.',
                titleEn: 'Time gets spent on tracking, not teaching.',
                bodyAr: 'المعلم يقضي ساعات أسبوعيًا في تسجيل الحضور وتحضير التقارير — ساعات لا تنتج تدخّلًا أكاديميًا فعليًا.',
                bodyEn: 'Teachers spend hours per week on attendance and reports — hours that produce no real academic intervention.',
                tagAr: 'وقت تدريس فعلي أقل من 40%',
                tagEn: 'Actual teaching time under 40%',
              },
              {
                roleAr: 'ولي الأمر',
                roleEn: 'The parent',
                icon: Users,
                titleAr: 'يعلم بالمشكلة بعد فوات الأوان.',
                titleEn: 'They learn about the problem too late.',
                bodyAr: 'ولي الأمر لا يطّلع على المؤشرات الأكاديمية إلا بعد تفاقمها وظهور أثرها في كشف الدرجات.',
                bodyEn: "Parents only see academic signals after they've already escalated into the grade report.",
                tagAr: 'المشكلة ظاهرة قبل أن يعلم ولي الأمر',
                tagEn: 'Problem visible before the parent knows',
              },
            ].map((col, i) => {
              const Icon = col.icon;
              return (
                <div
                  key={i}
                  className="group bg-white border border-slate-200 rounded-2xl p-7 flex flex-col transition-all duration-300 ease-out hover:-translate-y-1.5 hover:shadow-md hover:border-slate-300 motion-reduce:transition-none motion-reduce:hover:translate-y-0"
                >
                  <div className="flex items-center gap-3 mb-5">
                    <div className="shrink-0 w-10 h-10 rounded-lg bg-brand-turquoise/10 flex items-center justify-center transition-colors duration-300 group-hover:bg-brand-turquoise/15">
                      <Icon className="h-5 w-5 text-brand-turquoise" strokeWidth={1.5} aria-hidden="true" />
                    </div>
                    <span className="font-cairo text-xs font-bold text-brand-turquoise uppercase tracking-wider">
                      {isRTL ? col.roleAr : col.roleEn}
                    </span>
                  </div>
                  <h3 className="font-cairo font-bold text-brand-navy text-lg leading-snug mb-3">
                    {isRTL ? col.titleAr : col.titleEn}
                  </h3>
                  <p className="font-tajawal text-sm text-slate-600 leading-relaxed mb-5 flex-1">
                    {isRTL ? col.bodyAr : col.bodyEn}
                  </p>
                  <div className="flex items-center gap-2 pt-4 border-t border-slate-100">
                    <TrendingUp className="h-3.5 w-3.5 text-brand-turquoise shrink-0" strokeWidth={1.5} aria-hidden="true" />
                    <span className="font-tajawal text-xs text-slate-500">
                      {isRTL ? col.tagAr : col.tagEn}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          <p className="font-tajawal text-center text-slate-500 text-sm mt-10">
            {isRTL
              ? 'نَسَّق بُني خصيصًا ليُغلق هذه الفجوات — واحدة تلو الأخرى.'
              : 'NASSAQ was built specifically to close these gaps — one by one.'}
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
          <div className="text-center max-w-2xl mx-auto mb-12">
            <div className="inline-flex items-center gap-2 bg-brand-turquoise/15 border border-brand-turquoise/30 rounded-full ps-2 pe-4 py-1.5 mb-5 backdrop-blur-sm">
              <Zap className="h-4 w-4 text-brand-turquoise" strokeWidth={1.5} aria-hidden="true" />
              <span className="font-tajawal text-sm text-brand-turquoise">
                {isRTL ? 'العمل اليومي في نَسَّق' : 'The daily NASSAQ loop'}
              </span>
            </div>
            <h2 className="font-cairo font-bold text-white text-3xl sm:text-4xl lg:text-5xl leading-tight mb-4">
              {isRTL ? (
                <>أربع خطوات تحوّل الإشارات اليومية إلى <span className="text-brand-turquoise">قرارات واضحة.</span></>
              ) : (
                <>Four steps that turn daily signals into <span className="text-brand-turquoise">clear decisions.</span></>
              )}
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {[
              {
                titleAr: 'رصد الإشارات اليومية',
                titleEn: 'Capture daily signals',
                bodyAr: 'يرصد الأداء والحضور والتفاعل السلوكي من كل مصدر — تلقائيًا، يوميًا، دون تدخل يدوي.',
                bodyEn: 'Pulls performance, attendance and behavior from every source — automatically, daily, without manual entry.',
              },
              {
                titleAr: 'اكتشاف التراجع مبكرًا',
                titleEn: 'Catch decline early',
                bodyAr: 'يكتشف الانحرافات عن المسار الطبيعي قبل ظهور أثرها في النتائج — حين لا يزال التدخل ممكنًا.',
                bodyEn: "Detects deviations from a student's normal trajectory before they show up in grades — while intervention still works.",
              },
              {
                titleAr: 'ترتيب الأولويات',
                titleEn: 'Prioritize',
                bodyAr: 'يُنشئ قائمة تدخّل يومية واضحة لكل دور — الإدارة والمعلم وولي الأمر — مرتّبة حسب الأهمية.',
                bodyEn: 'Builds a clear daily intervention list for every role — admin, teacher, parent — ranked by urgency.',
              },
              {
                titleAr: 'التدخّل والمتابعة',
                titleEn: 'Act & follow up',
                bodyAr: 'توصيات قابلة للتنفيذ مباشرة، مع متابعة أثر كل تدخّل — حتى تعرف أن التحسّن فعلي.',
                bodyEn: 'Directly actionable recommendations, with follow-up on the impact of every intervention — so you know the improvement is real.',
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
                  {isRTL ? step.titleAr : step.titleEn}
                </h3>
                <p className="font-tajawal text-sm text-white/70 leading-relaxed">
                  {isRTL ? step.bodyAr : step.bodyEn}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ========== JOURNEY SECTION ========== */}
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
            className="grid lg:grid-cols-5 gap-6 lg:gap-8 items-start"
            onMouseEnter={() => setJourneyPaused(true)}
            onMouseLeave={() => setJourneyPaused(false)}
          >
            <div className="lg:col-span-3">
              <Card className="relative overflow-hidden border border-border/50 bg-card/80 backdrop-blur-sm p-7 md:p-8 transition-all duration-500 hover:border-brand-turquoise/20 hover:shadow-xl group">
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
                    <div className="flex-1 flex items-center gap-1">
                      {journeySteps.map((_, i) => (
                        <button
                          key={i}
                          onClick={() => setActiveJourneyStep(i)}
                          aria-label={`Step ${i + 1}`}
                          className={`h-1.5 rounded-full transition-all duration-500 ${
                            activeJourneyStep === i ? 'flex-[3] bg-gradient-to-r from-brand-turquoise to-cyan-500' : 'flex-1 bg-muted hover:bg-muted-foreground/30'
                          }`}
                        />
                      ))}
                    </div>
                    <span className="text-xs text-muted-foreground font-mono bg-muted/50 px-2 py-1 rounded-lg">
                      {journeySteps[activeJourneyStep].phase}/04
                    </span>
                  </div>
                </div>
              </Card>
            </div>

            <div className="lg:col-span-2 space-y-5">
              {/* Hakim Quote */}
              <div className="flex items-start gap-3">
                <div className="relative flex-shrink-0">
                  <img src="/hakim-poses/explaining-concept.png" alt={t('hakim')} className="hakim-img w-20 h-20 rounded-2xl object-contain border-2 border-brand-purple/40 shadow-xl bg-gradient-to-br from-violet-50 to-cyan-50 p-1" />
                  <div className="absolute -bottom-1 -end-1 w-5 h-5 rounded-md bg-brand-purple flex items-center justify-center border border-card">
                    <Brain className="h-2.5 w-2.5 text-white" />
                  </div>
                </div>
                <div className="flex-1 relative bg-gradient-to-br from-white to-gray-50 dark:from-white/95 dark:to-gray-100/90 border border-brand-purple/20 rounded-2xl p-5 shadow-lg">
                  <div className="absolute -top-2.5 start-4 bg-gradient-to-r from-brand-purple to-violet-600 text-white text-[10px] font-cairo font-bold px-3 py-0.5 rounded-full shadow-md">
                    {t('hakim')}
                  </div>
                  <p className="text-gray-700 text-sm leading-relaxed font-tajawal mt-1">
                    {journeySteps[activeJourneyStep].hakimSays}
                  </p>
                </div>
              </div>

              {/* Icon Grid */}
              <div className="grid grid-cols-4 gap-2.5">
                {journeySteps[activeJourneyStep].icons.map((Icon, i) => (
                  <div
                    key={`${activeJourneyStep}-icon-${i}`}
                    className="aspect-square rounded-2xl bg-gradient-to-br from-brand-turquoise/8 to-brand-turquoise/3 border border-brand-turquoise/15 flex items-center justify-center transition-all duration-300 hover:scale-110 hover:bg-brand-turquoise/15 hover:shadow-lg hover:shadow-brand-turquoise/10 animate-scale-in cursor-default"
                    style={{ animationDelay: `${i * 100 + 200}ms` }}
                  >
                    <Icon className="h-6 w-6 text-brand-turquoise" />
                  </div>
                ))}
              </div>

              {/* AI Powered Badge */}
              <div className="flex items-center justify-center gap-2 bg-gradient-to-r from-brand-turquoise/5 to-brand-purple/5 border border-brand-turquoise/15 rounded-xl px-4 py-3">
                <Brain className="h-4 w-4 text-brand-turquoise animate-pulse" />
                <span className="text-xs font-tajawal text-muted-foreground">
                  {t('aipoweredIntelligence')}
                </span>
                <Sparkles className="h-3.5 w-3.5 text-brand-purple animate-pulse" style={{ animationDelay: '0.5s' }} />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ========== AI INTELLIGENCE SECTION ========== */}
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

          <div className="grid lg:grid-cols-2 gap-8 lg:gap-10 items-start">
            {/* AI Feature Card */}
            <div
              onMouseEnter={() => setAIPaused(true)}
              onMouseLeave={() => setAIPaused(false)}
            >
              <Card className="relative overflow-hidden bg-white/[0.04] border-white/10 rounded-2xl p-7 md:p-8 transition-all duration-500 backdrop-blur-sm hover:bg-white/[0.06] hover:border-brand-turquoise/20 group">
                <div className="absolute top-0 end-0 w-48 h-48 bg-gradient-to-bl from-brand-turquoise/5 to-transparent rounded-bl-full" />
                <div className="absolute inset-0 animate-shimmer opacity-0 group-hover:opacity-100 transition-opacity" />

                <div className="relative z-10">
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

                  <div className="flex items-center gap-3 mt-6 pt-4 border-t border-white/5">
                    <div className="flex-1 flex items-center gap-1">
                      {aiCapabilities.map((_, i) => (
                        <button
                          key={i}
                          onClick={() => setActiveAIStep(i)}
                          aria-label={`AI capability ${i + 1}`}
                          className={`h-1.5 rounded-full transition-all duration-500 ${
                            activeAIStep === i ? 'flex-[3] bg-gradient-to-r from-brand-turquoise to-cyan-500' : 'flex-1 bg-white/10 hover:bg-white/25'
                          }`}
                        />
                      ))}
                    </div>
                  </div>
                </div>
              </Card>
            </div>

            {/* Analysis Layers + CTA */}
            <div
              className="space-y-5"
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
                className="w-full flex items-center justify-center gap-3 bg-gradient-to-r from-brand-turquoise to-cyan-500 hover:from-brand-turquoise-light hover:to-cyan-400 text-white rounded-2xl px-6 py-4 font-cairo font-bold text-lg shadow-xl shadow-brand-turquoise/25 hover:shadow-2xl hover:shadow-brand-turquoise/40 transition-all active:scale-[0.98] hover:scale-[1.02] animate-pulse-glow"
              >
                <Brain className="h-5 w-5" />
                {t('askHakim2')}
                <Sparkles className="h-4 w-4 animate-pulse" />
              </button>
            </div>
          </div>
        </div>
      </section>

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
            className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4 mb-10"
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

            <div className="relative z-10 grid lg:grid-cols-2 gap-8 items-start">
              <div>
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

              <div className="flex flex-col items-center justify-center gap-6">
                {/* Role Grid */}
                <div className="grid grid-cols-2 gap-3">
                  {ecosystemRoles.map((role, i) => (
                    <button
                      key={i}
                      onClick={() => setActiveEcosystemRole(i)}
                      className={`w-20 h-20 rounded-2xl flex items-center justify-center transition-all duration-500 border-2 ${
                        activeEcosystemRole === i
                          ? 'bg-gradient-to-br from-brand-turquoise to-cyan-500 scale-110 shadow-xl shadow-brand-turquoise/25 border-transparent animate-pulse-glow'
                          : 'bg-muted/30 hover:bg-muted border-border/30 hover:border-brand-turquoise/30'
                      }`}
                    >
                      <role.icon className={`h-8 w-8 transition-colors ${
                        activeEcosystemRole === i ? 'text-white' : 'text-muted-foreground'
                      }`} />
                    </button>
                  ))}
                </div>

                {/* Progress Dots */}
                <div className="flex items-center gap-3">
                  <div className="flex gap-1.5">
                    {ecosystemRoles.map((_, i) => (
                      <button
                        key={i}
                        onClick={() => setActiveEcosystemRole(i)}
                        aria-label={`Role ${i + 1}`}
                        className={`h-1.5 rounded-full transition-all duration-500 ${
                          activeEcosystemRole === i ? 'w-8 bg-gradient-to-r from-brand-turquoise to-cyan-500' : 'w-1.5 bg-muted hover:bg-muted-foreground/30'
                        }`}
                      />
                    ))}
                  </div>
                </div>

                {/* AI Badge */}
                <div className="flex items-center gap-2 bg-gradient-to-r from-brand-turquoise/5 to-brand-purple/5 border border-brand-turquoise/15 rounded-xl px-4 py-2.5">
                  <Brain className="h-3.5 w-3.5 text-brand-turquoise animate-pulse" />
                  <span className="text-[11px] font-tajawal text-muted-foreground">
                    {isRTL ? 'مدعوم بالذكاء الاصطناعي' : 'AI-Powered Platform'}
                  </span>
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
                {isRTL ? 'لماذا تثق بنا المدارس' : 'Why schools trust us'}
              </span>
            </div>
            <h2 className="font-cairo font-bold text-white text-3xl sm:text-4xl lg:text-5xl leading-tight mb-4">
              {isRTL ? (
                <>منصة سعودية، مبنية لـ <span className="text-brand-turquoise">المدارس السعودية.</span></>
              ) : (
                <>A Saudi platform, built for <span className="text-brand-turquoise">Saudi schools.</span></>
              )}
            </h2>
          </div>

          {/* Live stat strip — real numbers only */}
          {platformStats.schools > 0 && (
            <div className="relative bg-white/5 border border-brand-turquoise/30 rounded-2xl px-8 py-10 mb-12 text-center shadow-xl backdrop-blur-sm">
              <p className="font-tajawal text-white/70 text-sm mb-3">
                {isRTL ? 'مدارس فعّلت نَسَّق حتى اليوم' : 'Schools live on NASSAQ today'}
              </p>
              <div className="font-cairo font-black text-white text-6xl lg:text-7xl mb-3">
                <AnimatedCounter target={platformStats.schools} />
                <span className="text-brand-turquoise">+</span>
              </div>
              <p className="font-tajawal text-white/70 text-sm">
                {isRTL
                  ? 'ينمو الرقم كل أسبوع · بيانات حية من المنصة'
                  : 'Growing weekly · live count from the platform'}
              </p>
            </div>
          )}

          {/* Trust pillars — factual claims about architecture, not fake testimonials */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {[
              {
                icon: Shield,
                titleAr: 'بُنيت بمعايير حماية البيانات',
                titleEn: 'Built to data-protection standards',
                bodyAr: 'نَسَّق مصمَّمة بما يتوافق مع متطلبات نظام حماية البيانات الشخصية (PDPL)، مع تشفير كامل أثناء النقل والتخزين، ونسخ احتياطي يومي لبيانات كل مدرسة.',
                bodyEn: 'NASSAQ is designed in line with the Personal Data Protection Law (PDPL): full encryption in transit and at rest, with daily backups for every school.',
              },
              {
                icon: Building2,
                titleAr: 'فصل صارم بين المدارس',
                titleEn: 'Strict tenant separation',
                bodyAr: 'كل استعلام على بيانات الطلاب أو المعلمين مرتبط بمعرّف مدرستك — لا يمكن لأي مستخدم من مدرسة أخرى الوصول إلى صفك أو طالبك، حتى بالخطأ.',
                bodyEn: 'Every query on student or teacher data is bound to your school’s tenant ID — no user from another school can reach your class or your student, even by mistake.',
              },
              {
                icon: Zap,
                titleAr: 'جاهز خلال 24 ساعة',
                titleEn: 'Ready in 24 hours',
                bodyAr: 'لا حاجة لخادم أو تركيب. نُجهّز مساحة مدرستك ونستورد طلابك ومعلميك في أقل من يوم عمل واحد.',
                bodyEn: 'No server, no installation. We set up your school space and import your students and teachers in less than one working day.',
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
                    {isRTL ? pillar.titleAr : pillar.titleEn}
                  </h3>
                  <p className="font-tajawal text-sm text-white/70 leading-relaxed">
                    {isRTL ? pillar.bodyAr : pillar.bodyEn}
                  </p>
                </div>
              );
            })}
          </div>

          {/* Honesty note — we don't have testimonials yet, so we say so */}
          <p className="font-tajawal text-center text-white/50 text-xs mt-10">
            {isRTL
              ? 'قصص شركائنا من المدارس الرائدة قيد الإعداد للنشر — بإذنهم وبلا تجميل.'
              : "Stories from our early partner schools are being prepared for publication — with their consent, unedited."}
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
                {isRTL ? 'الأسئلة التي يطرحها المدراء قبل البدء' : 'Questions principals ask before starting'}
              </span>
            </div>
            <h2 className="font-cairo font-black text-foreground text-3xl md:text-5xl lg:text-[3.5rem] leading-tight">
              {isRTL ? (
                <>إجابات صريحة على <span className="text-brand-turquoise">ما يقلقك.</span></>
              ) : (
                <>Straight answers to <span className="text-brand-turquoise">what worries you.</span></>
              )}
            </h2>
          </div>

          <div className="space-y-3">
            {[
              {
                qAr: 'أخشى أن تكون التكلفة عالية على ميزانية المدرسة.',
                qEn: 'I worry the cost is too high for our school budget.',
                aAr: 'باقات نَسَّق مرنة وتُحسب حسب عدد الطلاب وحجم المؤسسة، وتشمل التحديثات والدعم بدون رسوم إعداد خفية. تبدأ بباقة Pilot المجانية لتجربة المنصة على بياناتك الحقيقية، ويمكنك إلغاء اشتراكك في أي وقت دون التزام.',
                aEn: 'NASSAQ plans are flexible and scale with your student count and institution size, including updates and support with no hidden setup fees. Start with the free Pilot plan to try NASSAQ on your real data, and cancel anytime — no commitment.',
              },
              {
                qAr: 'موظفونا غير متخصصين تقنيًا. هل سيستطيعون استخدامها؟',
                qEn: 'Our staff are not tech specialists. Can they use it?',
                aAr: 'صُممت كل شاشة في نَسَّق لتعمل بدون تدريب — معلم يدخل غيابه في ٣٠ ثانية، ولي أمر يرى تقرير طفله بضغطة. نُقدّم جلسة تأهيل أونلاين لفريقك مجانًا في أول أسبوع، وفريق دعم باللغة العربية متاح طوال أيام العمل.',
                aEn: 'Every screen in NASSAQ is designed to work without training — a teacher logs attendance in 30 seconds, a parent sees their child\'s report in one tap. We onboard your team online free in the first week, and our Arabic-speaking support is available every working day.',
              },
              {
                qAr: 'هل بياناتنا آمنة، ومحفوظة داخل المملكة؟',
                qEn: 'Is our data safe and kept inside the Kingdom?',
                aAr: 'نَسَّق مصمَّمة بما يتوافق مع متطلبات نظام حماية البيانات الشخصية (PDPL): تشفير كامل أثناء النقل والتخزين، نسخ احتياطي يومي، وفصل صارم لبيانات كل مدرسة على مستوى الاستعلام. نعمل حاليًا على اعتماد الاستضافة السيادية داخل المملكة ونُحدّث صفحة الخصوصية فور اكتمالها.',
                aEn: 'NASSAQ is designed in line with the Personal Data Protection Law (PDPL): full encryption in transit and at rest, daily backups, and strict per-school separation enforced at query level. Sovereign hosting inside Saudi Arabia is in progress, and we update the privacy page the moment it is finalized.',
              },
              {
                qAr: 'ماذا لو لم تناسبنا المنصة بعد التجربة؟',
                qEn: "What if the platform doesn't fit us after trying it?",
                aAr: 'تجربة نَسَّق مجانية بالكامل، بدون بطاقة ائتمان وبدون التزام. لو قررت عدم المتابعة، نُساعدك على تصدير بيانات مدرستك كاملة في ملفات قياسية — تبقى ملكك أنت.',
                aEn: 'The NASSAQ trial is fully free, no credit card and no commitment. If you decide not to continue, we help you export all your school data in standard files — it stays yours.',
              },
              {
                qAr: 'هل تتكامل نَسَّق مع نظامنا الحالي (نور، مدرستي…)؟',
                qEn: 'Does NASSAQ integrate with our current system (Noor, Madrasati…)?',
                aAr: 'نعم. نَسَّق يدعم استيراد بيانات الطلاب والمعلمين من نظام نور بصيغ Excel/CSV، ويعمل بجانب مدرستي بدون تعارض. هدفنا أن نُكمّل أدواتك لا أن نستبدلها.',
                aEn: 'Yes. NASSAQ supports importing student and teacher data from Noor via Excel/CSV, and runs alongside Madrasati without conflict. We complement your existing tools, not replace them.',
              },
            ].map((faq, i) => (
              <details
                key={i}
                className="group bg-card/80 border border-border/50 rounded-2xl overflow-hidden backdrop-blur-sm transition-all duration-300 hover:border-brand-turquoise/30 hover:shadow-md open:border-brand-turquoise/40 open:shadow-xl open:shadow-brand-turquoise/5"
              >
                <summary className="flex items-center justify-between gap-4 px-6 py-5 cursor-pointer list-none focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-turquoise focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-2xl">
                  <span className="font-cairo font-bold text-foreground text-base text-start">
                    {isRTL ? faq.qAr : faq.qEn}
                  </span>
                  <span className="shrink-0 w-8 h-8 rounded-lg bg-brand-turquoise/10 flex items-center justify-center transition-colors group-hover:bg-brand-turquoise/15 group-open:bg-gradient-to-br group-open:from-brand-turquoise group-open:to-cyan-500">
                    <ChevronDown className="h-4 w-4 text-brand-turquoise group-open:text-white group-open:rotate-180 transition-all" strokeWidth={2} aria-hidden="true" />
                  </span>
                </summary>
                <div className="px-6 pb-5 -mt-1">
                  <p className="font-tajawal text-sm text-muted-foreground leading-relaxed">
                    {isRTL ? faq.aAr : faq.aEn}
                  </p>
                </div>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* ========== PRICING TIERS — merged from client demo ========== */}
      <section
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
                {isRTL ? 'الباقات' : 'Plans'}
              </span>
            </div>
            <h2 className="font-cairo font-bold text-white text-3xl sm:text-4xl lg:text-5xl leading-tight mb-4">
              {isRTL ? (
                <>ابدأ بـ <span className="text-brand-turquoise">Pilot</span> — وطوّر مع نمو مدرستك.</>
              ) : (
                <>Start with a <span className="text-brand-turquoise">Pilot</span> — then scale as your school grows.</>
              )}
            </h2>
            <p className="font-tajawal text-base text-white/70 leading-relaxed">
              {isRTL
                ? 'ابدأ بتجربة مجانية محدودة، وانتقل إلى باقة المدارس متى احتجت — أو خصّص حلًا للمجموعات التعليمية.'
                : 'Start with a limited free trial, move to the schools plan whenever you need — or customize a solution for education groups.'}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 items-stretch">
            {[
              {
                badge: null,
                nameAr: 'Pilot',
                nameEn: 'Pilot',
                taglineAr: 'للمدارس الراغبة في التجربة',
                taglineEn: 'For schools that want to try first',
                priceAr: 'مجانًا',
                priceEn: 'Free',
                priceNoteAr: 'برنامج تجريبي محدود',
                priceNoteEn: 'Limited pilot program',
                metaAr: 'حتى ٣٠ طالب · معلم واحد · جاهز خلال ٢٤ ساعة',
                metaEn: 'Up to 30 students · 1 teacher · ready in 24 hours',
                ctaAr: 'اطلب Pilot',
                ctaEn: 'Request a Pilot',
                ctaLink: '/register',
                features: [
                  ['إدارة المستويات الأكاديمية', 'Academic levels management'],
                  ['تسجيل الحضور', 'Attendance tracking'],
                  ['السلوك والمشاركة', 'Behavior & participation'],
                  ['تقارير بسيطة', 'Basic reports'],
                ],
                highlight: false,
              },
              {
                badgeAr: 'الأكثر اختيارًا',
                badgeEn: 'Most popular',
                nameAr: 'للمدارس',
                nameEn: 'Schools',
                taglineAr: 'الحل الشامل للاكتشاف المبكر والتدخل الأكاديمي والسلوكي',
                taglineEn: 'The full solution for early detection and academic & behavioral intervention',
                priceAr: 'حسب عدد الطلاب',
                priceEn: 'Per-student pricing',
                priceNoteAr: 'وحجم المؤسسة',
                priceNoteEn: 'and institution size',
                metaAr: 'تسعير شفاف بدون رسوم إعداد · إلغاء في أي وقت',
                metaEn: 'Transparent pricing, no setup fees · cancel anytime',
                ctaAr: 'احجز عرضًا',
                ctaEn: 'Book a demo',
                ctaLink: '/register',
                features: [
                  ['كل ما في Pilot', 'Everything in Pilot'],
                  ['توصيات يومية ذكية', 'Smart daily recommendations'],
                  ['الاكتشاف المبكر للتعثر', 'Early detection of decline'],
                  ['تدخّلات مقترحة لكل حالة', 'Suggested interventions for every case'],
                  ['تقارير تنفيذية للإدارة', 'Executive reports for leadership'],
                  ['متابعة أولياء الأمور', 'Parent follow-up'],
                  ['قياس أثر التدخلات', 'Intervention impact tracking'],
                ],
                highlight: true,
              },
              {
                badge: null,
                nameAr: 'للمجموعات التعليمية',
                nameEn: 'Education groups',
                taglineAr: 'شبكات ومجموعات تعليمية وجهات حكومية',
                taglineEn: 'Networks, education groups and government bodies',
                priceAr: 'تسعير مخصّص',
                priceEn: 'Custom pricing',
                priceNoteAr: 'تواصل معنا',
                priceNoteEn: 'Contact us',
                metaAr: 'تخصيص كامل للشبكات التعليمية',
                metaEn: 'Full customization for education networks',
                ctaAr: 'تواصل مع المبيعات',
                ctaEn: 'Contact sales',
                ctaLink: '/register',
                features: [
                  ['كل ما في باقة المدارس', 'Everything in the Schools plan'],
                  ['ربط أنظمة خارجية', 'External systems integration'],
                  ['تسجيل دخول موحّد (SSO)', 'Single sign-on (SSO)'],
                  ['لوحات مخصّصة بالكامل', 'Fully customized dashboards'],
                  ['مدير نجاح مخصّص', 'Dedicated success manager'],
                  ['تدريب وتشغيل كامل', 'End-to-end training & onboarding'],
                ],
                highlight: false,
              },
            ].map((tier, i) => (
              <div
                key={i}
                aria-label={tier.highlight ? (isRTL ? 'الباقة الموصى بها' : 'Recommended plan') : undefined}
                className={`relative flex flex-col rounded-2xl p-7 backdrop-blur-sm transition-all duration-300 ${
                  tier.highlight
                    ? 'bg-white/10 text-white border-2 border-brand-turquoise shadow-2xl shadow-brand-turquoise/20 scale-100 md:scale-[1.03]'
                    : 'bg-white/5 border border-white/10 hover:bg-white/10 hover:border-brand-turquoise/40 hover:shadow-lg'
                }`}
              >
                {tier.badgeAr && (
                  <div className="absolute -top-3 inset-x-0 flex justify-center">
                    <span className="bg-gradient-to-r from-brand-turquoise to-cyan-500 text-white font-cairo text-xs font-bold px-4 py-1 rounded-full shadow-lg shadow-brand-turquoise/30">
                      {isRTL ? tier.badgeAr : tier.badgeEn}
                    </span>
                  </div>
                )}

                <h3 className="font-cairo font-bold text-xl mb-1 text-white">
                  {isRTL ? tier.nameAr : tier.nameEn}
                </h3>
                <p className="font-tajawal text-sm mb-6 text-white/65">
                  {isRTL ? tier.taglineAr : tier.taglineEn}
                </p>

                <div className="mb-2">
                  <span className={`font-cairo font-black text-3xl ${tier.highlight ? 'text-brand-turquoise' : 'text-white'}`}>
                    {isRTL ? tier.priceAr : tier.priceEn}
                  </span>
                </div>
                <p className="font-tajawal text-xs mb-6 text-white/55">
                  {isRTL ? tier.priceNoteAr : tier.priceNoteEn}
                </p>

                <Button
                  asChild
                  className={`w-full font-cairo rounded-lg h-11 mb-6 ${
                    tier.highlight
                      ? 'bg-gradient-to-r from-brand-turquoise to-cyan-500 hover:from-brand-turquoise-light hover:to-cyan-400 text-white hover:text-white shadow-lg shadow-brand-turquoise/25'
                      : 'bg-white/10 border border-white/20 hover:bg-white/15 hover:border-brand-turquoise/40 text-white hover:text-white backdrop-blur-sm'
                  }`}
                >
                  <Link to={tier.ctaLink}>{isRTL ? tier.ctaAr : tier.ctaEn}</Link>
                </Button>

                <ul className="space-y-3 flex-1">
                  {tier.features.map(([ar, en], j) => (
                    <li key={j} className="flex items-start gap-2.5">
                      <CheckCircle2 className="h-4 w-4 mt-0.5 shrink-0 text-brand-turquoise" strokeWidth={2} aria-hidden="true" />
                      <span className="font-tajawal text-sm leading-snug text-white/85">
                        {isRTL ? ar : en}
                      </span>
                    </li>
                  ))}
                </ul>

                <p className="font-tajawal text-xs mt-6 pt-5 border-t text-white/55 border-white/10">
                  {isRTL ? tier.metaAr : tier.metaEn}
                </p>
              </div>
            ))}
          </div>

          <p className="font-tajawal text-center text-white/60 text-sm mt-10">
            {isRTL
              ? 'دعم عربي كامل · بدون رسوم إعداد · إلغاء في أي وقت'
              : 'Full Arabic support · no setup fees · cancel anytime'}
          </p>
        </div>
      </section>

      {/* ========== CALL TO ACTION ========== */}
      <section
        className="py-24 lg:py-32 bg-gradient-to-b from-background via-background to-background relative overflow-hidden"
        data-testid="cta-section"
      >
        {/* journey-style ambient background — pattern + soft brand-tinted blur orbs */}
        <div className="absolute inset-0 opacity-[0.02]" style={{ backgroundImage: `url(${BG_PATTERN})`, backgroundSize: '200% auto', backgroundPosition: 'center center' }} aria-hidden="true" />
        <div className="absolute top-0 left-0 w-[500px] h-[500px] rounded-full bg-brand-turquoise/5 blur-[120px] animate-pulse" style={{ animationDuration: '8s' }} aria-hidden="true" />
        <div className="absolute bottom-0 right-0 w-[400px] h-[400px] rounded-full bg-brand-purple/5 blur-[100px] animate-pulse" style={{ animationDelay: '2s', animationDuration: '8s' }} aria-hidden="true" />

        <div className="relative max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          {/* eyebrow — matches journey/faq recipe */}
          <div className="inline-flex items-center gap-2.5 bg-gradient-to-r from-brand-turquoise/15 to-brand-turquoise/5 border border-brand-turquoise/25 rounded-full px-5 py-2.5 mb-6 backdrop-blur-sm animate-pulse-glow">
            <Sparkles className="h-4 w-4 text-brand-turquoise animate-pulse" strokeWidth={1.5} aria-hidden="true" />
            <span className="text-brand-turquoise text-sm font-tajawal font-medium">
              {isRTL ? 'ابدأ رحلتك مع نَسَّق' : 'Start your NASSAQ journey'}
            </span>
          </div>

          <h2 className="font-cairo text-3xl md:text-5xl lg:text-[3.5rem] font-black text-foreground mb-5 leading-tight">
            {t('readyToStart')}
          </h2>
          <p className="text-lg md:text-xl text-muted-foreground font-tajawal max-w-2xl mx-auto leading-relaxed mb-12">
            {isRTL
              ? 'سواء كنت مدرسة أو معلمًا — نَسَّق يحوّل بياناتك إلى قرارات أوضح في دقائق.'
              : 'Whether you run a school or teach a class — NASSAQ turns your data into clearer decisions in minutes.'}
          </p>

          <div className="grid md:grid-cols-2 gap-5 mb-12">
            <div className="bg-card/80 backdrop-blur-sm border border-border/50 rounded-2xl p-6 text-start hover:border-brand-turquoise/40 hover:shadow-lg hover:-translate-y-0.5 transition-all group">
              <div className="w-12 h-12 rounded-xl bg-brand-turquoise/10 flex items-center justify-center mb-4 group-hover:bg-brand-turquoise/15 transition-colors">
                <Building2 className="h-6 w-6 text-brand-turquoise" strokeWidth={1.5} aria-hidden="true" />
              </div>
              <h3 className="font-cairo text-xl font-bold text-foreground mb-2">{t('ifYouAreASchool')}</h3>
              <p className="text-muted-foreground text-sm font-tajawal leading-relaxed">
                {t('makeYourSchoolMoreOrganizedAndClearWithNassaqPlatf')}
              </p>
            </div>
            <div className="bg-card/80 backdrop-blur-sm border border-border/50 rounded-2xl p-6 text-start hover:border-brand-purple/40 hover:shadow-lg hover:-translate-y-0.5 transition-all group">
              <div className="w-12 h-12 rounded-xl bg-brand-purple/10 flex items-center justify-center mb-4 group-hover:bg-brand-purple/15 transition-colors">
                <UserCheck className="h-6 w-6 text-brand-purple" strokeWidth={1.5} aria-hidden="true" />
              </div>
              <h3 className="font-cairo text-xl font-bold text-foreground mb-2">{t('ifYouAreATeacher')}</h3>
              <p className="text-muted-foreground text-sm font-tajawal leading-relaxed">
                {t('startOrganizingYourClassesNowAndMakeClassroomManag')}
              </p>
            </div>
          </div>

          <div className="flex items-center justify-center gap-5 mb-12">
            <div className="relative flex-shrink-0">
              <div className="absolute -inset-2 rounded-full bg-brand-turquoise/15 blur-xl animate-pulse" aria-hidden="true" />
              <img src="/hakim-poses/motivating.png" alt={t('hakim')} className="hakim-img relative w-24 h-24 rounded-2xl object-contain border-2 border-brand-turquoise shadow-xl flex-shrink-0 bg-gradient-to-br from-cyan-50 to-violet-50 p-1" />
            </div>
            <div className="bg-card/80 backdrop-blur-sm border border-border/50 rounded-2xl px-6 py-4 max-w-lg text-start shadow-sm">
              <p className="text-foreground/90 font-tajawal text-base leading-relaxed">
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

      <Footer />
      <HakimAssistant />
    </div>
  );
};
