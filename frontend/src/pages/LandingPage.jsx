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

const LOGO_WHITE = 'https://customer-assets.emergentagent.com/job_f5ea20bb-5cf5-462f-a7f0-958201e27f89/artifacts/q04svb5j_Nassaq%20LinkedIn%20Logo%20White.png';
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
      try {
                const response = await api.get('/public/stats');
        if (response.data) {
          setPlatformStats({
            schools: response.data.schools || 0,
            students: response.data.students || 0,
            teachers: response.data.teachers || 0,
            parents: response.data.parents || 0,
          });
        }
      } catch (error) {
        console.error('Failed to fetch platform stats:', error);
      }
    };
    fetchStats();
  }, []);

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
      dataIcons: ['📊', '📋', '🧠', '📚', '📝'],
      phase: '01',
    },
    {
      title: 'جمع البيانات داخل نَسَّق',
      subtitle: 'هنا يبدأ دور منصة نَسَّق',
      content: 'يقوم النظام بجمع كل هذه البيانات داخل منصة واحدة: الحضور والانصراف، الأداء الأكاديمي، السلوك اليومي، التفاعل داخل الحصة، الواجبات والتقييمات.',
      hakimSays: 'مهمتي هي تنظيم هذه البيانات وتحويلها إلى صورة واضحة للمدرسة.',
      icons: [Database, TrendingUp, CheckCircle2, Award],
      dataIcons: ['📦', '📈', '✅', '🎯'],
      phase: '02',
    },
    {
      title: 'تحليل البيانات بالذكاء الاصطناعي',
      subtitle: 'عندما يبدأ الذكاء الاصطناعي بالتحليل',
      content: 'اكتشاف الطلاب الذين يحتاجون دعمًا، تحليل الأنماط السلوكية داخل الفصول، رصد تراجع الأداء الأكاديمي، تحديد فرص تحسين المشاركة.',
      hakimSays: 'أنا لا أعرض الأرقام فقط… بل أكتشف ما تعنيه هذه الأرقام.',
      icons: [Brain, Lightbulb, TrendingUp, Target],
      dataIcons: ['📈', '⚠️', '🧠', '💡'],
      phase: '03',
    },
    {
      title: 'اتخاذ القرار',
      subtitle: 'من البيانات… إلى القرار',
      content: 'خطط دعم الطلاب، تقارير الأداء، قرارات تعليمية دقيقة مبنية على بيانات حقيقية تساعد في تحسين جودة العملية التعليمية.',
      hakimSays: 'البيانات وحدها لا تغيّر التعليم… لكن القرارات الصحيحة تفعل.',
      icons: [CheckCircle2, Award, Target, TrendingUp],
      dataIcons: ['✔️', '📊', '🎓', '🏆'],
      phase: '04',
    },
  ] : [
    {
      title: 'Daily School Reality',
      subtitle: 'Every school produces thousands of data points daily',
      content: 'Recording attendance, evaluating assignments, recording behavior, student participation, test results, teacher notes. But this data is often distributed and fragmented.',
      hakimSays: 'Schools generate thousands of data points every day... but few can turn this data into knowledge.',
      icons: [BarChart3, Calendar, Brain, BookOpen],
      dataIcons: ['📊', '📋', '🧠', '📚', '📝'],
      phase: '01',
    },
    {
      title: 'Data Collection in NASSAQ',
      subtitle: 'Here is where NASSAQ platform begins',
      content: 'The system collects all this data in one platform: attendance, academic performance, daily behavior, in-class interaction, assignments and assessments.',
      hakimSays: 'My mission is to organize this data and turn it into a clear picture for the school.',
      icons: [Database, TrendingUp, CheckCircle2, Award],
      dataIcons: ['📦', '📈', '✅', '🎯'],
      phase: '02',
    },
    {
      title: 'AI Data Analysis',
      subtitle: 'When AI starts analyzing',
      content: 'Discovering students who need support, analyzing behavioral patterns, tracking academic decline, identifying participation improvement opportunities.',
      hakimSays: "I don't just display numbers... I discover what these numbers mean.",
      icons: [Brain, Lightbulb, TrendingUp, Target],
      dataIcons: ['📈', '⚠️', '🧠', '💡'],
      phase: '03',
    },
    {
      title: 'Decision Making',
      subtitle: 'From Data... to Decisions',
      content: 'Student support plans, performance reports, precise educational decisions based on real data that help improve education quality.',
      hakimSays: "Data alone doesn't change education... but the right decisions do.",
      icons: [CheckCircle2, Award, Target, TrendingUp],
      dataIcons: ['✔️', '📊', '🎓', '🏆'],
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
      role: 'الطالب',
      title: 'التعلم يصبح تجربة محفزة',
      content: 'حساب بسيط ومحفز وتفاعلي. نقاط المشاركة، إنجازات، متابعة الواجبات، تقارير التقدم الدراسي.',
      hakimSays: 'عندما يرى الطالب تقدمه بنفسه… يصبح التعلم تجربة أكثر تحفيزًا.',
      icon: GraduationCap,
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
      role: 'Student',
      title: 'Learning becomes a motivating experience',
      content: 'Simple, motivating, interactive account. Participation points, achievements, assignment tracking, progress reports.',
      hakimSays: 'When students see their own progress... learning becomes a more motivating experience.',
      icon: GraduationCap,
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
      <header className="fixed top-0 left-0 right-0 z-50 backdrop-blur-xl border-b border-white/5 overflow-hidden" data-testid="header">
        <div className="absolute inset-0 bg-brand-navy/80" />
        <div className="absolute inset-0 opacity-[0.06]" style={{ backgroundImage: `url(${BG_PATTERN})`, backgroundSize: '200% auto', backgroundPosition: 'center top' }} />
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16 lg:h-18">
            <Link to="/" className="flex items-center gap-2" data-testid="navbar-logo">
              <img src={LOGO_WHITE} alt="نَسَّق" className="h-9 lg:h-10 w-auto rounded-xl" />
            </Link>
            <div className="flex items-center gap-1 sm:gap-2">
              <Button variant="ghost" size="icon" onClick={toggleLanguage} className="text-white/70 hover:text-white hover:bg-white/10 rounded-xl h-9 w-9 sm:h-10 sm:w-10" data-testid="language-toggle" aria-label={t('key_xlsw4h')}>
                <Globe className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme} className="text-white/70 hover:text-white hover:bg-white/10 rounded-xl h-9 w-9 sm:h-10 sm:w-10" data-testid="theme-toggle" aria-label={isDark ? 'Light mode' : 'Dark mode'}>
                {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
              </Button>
              <Button variant="ghost" asChild className="text-white/80 hover:text-white hover:bg-white/10 rounded-xl text-xs sm:text-sm px-2.5 sm:px-3 h-9 sm:h-10" data-testid="login-link">
                <Link to="/login">{t('login')}</Link>
              </Button>
              <Button asChild className="bg-brand-turquoise hover:bg-brand-turquoise-light text-white rounded-xl text-xs sm:text-sm px-3 sm:px-5 h-9 sm:h-10 shadow-lg shadow-brand-turquoise/20" data-testid="register-link">
                <Link to="/register">{t('register2')}</Link>
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* ========== HERO SECTION ========== */}
      <section
        className="relative min-h-screen flex items-center overflow-hidden pt-20 bg-brand-navy"
        data-testid="hero-section"
      >
        <div className="absolute inset-0 opacity-[0.07]" style={{ backgroundImage: `url(${BG_PATTERN})`, backgroundSize: '200% auto', backgroundPosition: 'center top' }} />
        <div className="absolute inset-0 opacity-[0.12]" style={{ backgroundImage: `url('/images/nassaq-hero-bg.png')`, backgroundSize: 'cover', backgroundPosition: 'center' }} />
        <div className="absolute inset-0 bg-gradient-to-b from-brand-navy/40 via-transparent to-brand-navy/70" />

        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute top-20 left-10 w-80 h-80 rounded-full bg-brand-turquoise/8 blur-3xl animate-pulse" />
          <div className="absolute bottom-20 right-10 w-96 h-96 rounded-full bg-brand-purple/8 blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
          <div className="absolute top-1/3 left-1/3 w-[500px] h-[500px] rounded-full bg-cyan-500/5 blur-3xl animate-pulse" style={{ animationDelay: '2s' }} />

          <FloatingIcon icon={BarChart3} className="top-[15%] left-[10%]" delay="0s" />
          <FloatingIcon icon={Brain} className="top-[25%] right-[15%]" delay="1s" />
          <FloatingIcon icon={Database} className="bottom-[30%] left-[20%]" delay="2s" />
          <FloatingIcon icon={BookOpen} className="top-[60%] right-[10%]" delay="3s" />
          <FloatingIcon icon={Target} className="top-[40%] left-[5%]" delay="1.5s" />
          <FloatingIcon icon={Award} className="bottom-[20%] right-[25%]" delay="2.5s" />
        </div>

        <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 w-full">
          <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center min-h-[calc(100vh-5rem)]">

            <div className={`space-y-8 ${isRTL ? 'lg:order-1' : 'lg:order-1'}`}>
              <div className="inline-flex items-center gap-2 bg-brand-turquoise/10 border border-brand-turquoise/20 rounded-full px-4 py-2 backdrop-blur-sm">
                <Sparkles className="h-4 w-4 text-brand-turquoise animate-pulse" />
                <span className="text-brand-turquoise/90 text-sm font-tajawal">{t('aipoweredSmartEducationPlatform')}</span>
              </div>

              <div>
                <h1 className="text-5xl md:text-6xl lg:text-7xl font-cairo font-black text-white mb-4 leading-tight" data-testid="platform-name">
                  {t('nassaq')}
                </h1>
                <p className="text-3xl md:text-4xl text-brand-turquoise font-cairo font-bold mb-4">
                  {t('fromDataToDecisions')}
                </p>
                <p className="text-lg text-white/60 font-tajawal leading-relaxed max-w-lg">
                  {t('educationOperationsIntelligencePlatformFromDataToD')
                  }
                </p>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3" data-testid="traction-section">
                {[
                  { icon: Building2, value: platformStats.schools, label: t('schools3') },
                  { icon: GraduationCap, value: platformStats.students, label: isRTL ? 'طالب' : 'Students' },
                  { icon: Users, value: platformStats.parents, label: isRTL ? 'ولي أمر' : 'Parents' },
                  { icon: UserCheck, value: platformStats.teachers, label: isRTL ? 'معلم' : 'Teachers' },
                ].map((stat, i) => (
                  <div key={i} className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-3 text-center group hover:bg-white/10 hover:border-brand-turquoise/30 transition-all duration-300" data-testid={`traction-${stat.label.toLowerCase()}`}>
                    <stat.icon className="h-5 w-5 text-brand-turquoise mx-auto mb-1.5 group-hover:scale-110 transition-transform" />
                    <p className="text-xl font-cairo font-bold text-white">
                      <AnimatedCounter target={stat.value} />
                    </p>
                    <p className="text-white/50 font-tajawal text-xs">{stat.label}</p>
                  </div>
                ))}
              </div>

              <div className="flex flex-col sm:flex-row gap-3">
                <Button asChild size="lg" className="bg-gradient-to-r from-brand-turquoise to-cyan-500 hover:from-brand-turquoise-light hover:to-cyan-400 text-white rounded-2xl h-12 sm:h-14 px-6 sm:px-8 text-base sm:text-lg font-cairo shadow-xl shadow-brand-turquoise/25 hover:shadow-2xl hover:shadow-brand-turquoise/35 transition-all hover:scale-[1.02]" data-testid="hero-cta-btn">
                  <Link to="/login" className="flex items-center gap-2">
                    {t('enterThePlatform')}
                    {isRTL ? <ArrowLeft className="h-5 w-5" /> : <ArrowRight className="h-5 w-5" />}
                  </Link>
                </Button>
                <Button asChild variant="outline" size="lg" className="border-white/20 text-white hover:bg-white/10 rounded-2xl h-12 sm:h-14 px-5 sm:px-6 text-base sm:text-lg font-cairo backdrop-blur-sm" data-testid="teacher-register-cta">
                  <Link to="/teacher-register" className="flex items-center gap-2">
                    <UserCheck className="h-5 w-5" />
                    {t('joinAsTeacher')}
                  </Link>
                </Button>
              </div>

              <div className="inline-flex items-center gap-2 bg-white/5 border border-white/10 rounded-full px-4 py-2">
                <Bell className="h-4 w-4 text-brand-turquoise animate-pulse" />
                <span className="text-white/60 font-tajawal text-sm">{t('247TechnicalSupport')}</span>
              </div>
            </div>

            <div className={`flex flex-col items-center justify-end ${isRTL ? 'lg:order-2' : 'lg:order-2'}`}>
              <div className="relative w-full max-w-md flex flex-col items-center">
                <div className="relative z-10 w-72 lg:w-96 mb-[-40px]" style={{ aspectRatio: '1/1.2' }}>
                  <img
                    src={heroHakim.currentSrc}
                    alt={t('hakim')}
                    className="hakim-img absolute inset-0 w-full h-full object-contain"
                    data-testid="hakim-avatar"
                  />
                </div>

                <div className="relative z-20 w-full">
                  <div className="relative bg-white/10 backdrop-blur-md border border-white/15 rounded-2xl px-6 py-5 shadow-2xl">
                    <div className="absolute -top-3 start-6 bg-brand-turquoise text-white text-xs font-cairo font-bold px-3 py-1 rounded-full shadow-lg flex items-center gap-1.5">
                      <Brain className="h-3.5 w-3.5" />
                      {t('hakim')}
                    </div>
                    <p className="text-white/90 text-base font-tajawal leading-relaxed min-h-[72px]">
                      {typedHakimText}
                      <span className="inline-block w-0.5 h-5 bg-brand-turquoise animate-pulse ms-1 align-middle" />
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-white/40 text-xs font-tajawal">{t('hakimIsOnline')}</span>
              </div>
            </div>
          </div>

          <div className="absolute bottom-8 left-1/2 -translate-x-1/2 animate-bounce">
            <ChevronDown className="h-6 w-6 text-white/30" />
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
                    {journeySteps[activeJourneyStep].dataIcons.map((emoji, i) => (
                      <span
                        key={`${activeJourneyStep}-${i}`}
                        className="w-11 h-11 rounded-xl bg-gradient-to-br from-brand-turquoise/10 to-brand-turquoise/5 border border-brand-turquoise/15 flex items-center justify-center text-lg animate-scale-in shadow-sm"
                        style={{ animationDelay: `${i * 80}ms` }}
                      >
                        {emoji}
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
        className="py-24 lg:py-32 bg-brand-navy relative overflow-hidden"
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
        className="py-24 lg:py-32 bg-gradient-to-b from-background via-background to-background relative overflow-hidden"
        data-testid="ecosystem-section"
      >
        <div className="absolute inset-0 opacity-[0.02]" style={{ backgroundImage: `url(${BG_PATTERN})`, backgroundSize: '200% auto', backgroundPosition: 'center center' }} />
        <div className="absolute top-0 right-0 w-[500px] h-[500px] rounded-full bg-brand-turquoise/5 blur-[120px] animate-pulse" style={{ animationDuration: '10s' }} />
        <div className="absolute bottom-[20%] left-0 w-[400px] h-[400px] rounded-full bg-brand-purple/5 blur-[100px] animate-pulse" style={{ animationDelay: '3s', animationDuration: '8s' }} />

        <div className={`relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 transition-all duration-1000 ${ecoVisible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-12'}`}>
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2.5 bg-gradient-to-r from-brand-purple/15 to-brand-turquoise/10 border border-brand-purple/25 rounded-full px-5 py-2.5 mb-6 backdrop-blur-sm">
              <Shield className="h-4 w-4 text-brand-purple animate-pulse" />
              <span className="text-brand-purple text-sm font-tajawal font-medium">{t('completeEcosystem')}</span>
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
                    ? 'bg-gradient-to-br from-brand-turquoise/10 to-brand-turquoise/3 border-brand-turquoise shadow-xl shadow-brand-turquoise/10 scale-[1.03]'
                    : 'bg-card/80 border-border/30 hover:border-brand-turquoise/30 hover:shadow-lg opacity-70 hover:opacity-100'
                }`}
              >
                <div className={`w-12 h-12 md:w-14 md:h-14 rounded-2xl bg-gradient-to-br ${role.gradient} flex items-center justify-center mb-3 md:mb-4 shadow-lg transition-all duration-300 ${
                  activeEcosystemRole === i ? 'scale-110 shadow-xl' : 'group-hover:scale-105'
                }`}>
                  <role.icon className="h-6 w-6 md:h-7 md:w-7 text-white" />
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
                  <div className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${ecosystemRoles[activeEcosystemRole].gradient} flex items-center justify-center shadow-xl`}>
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
                          ? `bg-gradient-to-br ${role.gradient} scale-110 shadow-xl border-transparent animate-pulse-glow`
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

      {/* ========== CALL TO ACTION ========== */}
      <section
        className="py-24 lg:py-32 relative overflow-hidden"
        data-testid="cta-section"
      >
        <div className="absolute inset-0 bg-brand-navy" />
        <div className="absolute inset-0 opacity-[0.06]" style={{ backgroundImage: `url(${BG_PATTERN})`, backgroundSize: '200% auto', backgroundPosition: 'center bottom' }} />
        <div className="absolute inset-0 bg-gradient-to-b from-brand-navy/30 via-transparent to-brand-navy/50" />
        <div className="absolute inset-0">
          <div className="absolute top-1/4 left-1/4 w-96 h-96 rounded-full bg-brand-turquoise/5 blur-3xl animate-pulse" />
          <div className="absolute bottom-1/4 right-1/4 w-96 h-96 rounded-full bg-brand-purple/5 blur-3xl animate-pulse" style={{ animationDelay: '1s' }} />
        </div>

        <div className="relative max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="font-cairo text-4xl md:text-6xl font-black text-white mb-10">
            {t('readyToStart')}
          </h2>

          <div className="grid md:grid-cols-2 gap-5 mb-12">
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-6 text-start hover:bg-white/10 hover:border-brand-turquoise/30 transition-all hover:scale-[1.02] group">
              <Building2 className="h-10 w-10 text-brand-turquoise mb-4 group-hover:scale-110 transition-transform" />
              <h3 className="font-cairo text-xl font-bold text-white mb-2">{t('ifYouAreASchool')}</h3>
              <p className="text-white/50 text-sm font-tajawal">
                {t('makeYourSchoolMoreOrganizedAndClearWithNassaqPlatf')
                }
              </p>
            </div>
            <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-6 text-start hover:bg-white/10 hover:border-brand-turquoise/30 transition-all hover:scale-[1.02] group">
              <UserCheck className="h-10 w-10 text-brand-turquoise mb-4 group-hover:scale-110 transition-transform" />
              <h3 className="font-cairo text-xl font-bold text-white mb-2">{t('ifYouAreATeacher')}</h3>
              <p className="text-white/50 text-sm font-tajawal">
                {t('startOrganizingYourClassesNowAndMakeClassroomManag')
                }
              </p>
            </div>
          </div>

          <div className="flex items-center justify-center gap-5 mb-12">
            <div className="relative flex-shrink-0">
              <div className="absolute -inset-2 rounded-full bg-brand-turquoise/20 blur-xl animate-pulse" />
              <img src="/hakim-poses/motivating.png" alt={t('hakim')} className="hakim-img relative w-24 h-24 rounded-2xl object-contain border-2 border-brand-turquoise shadow-xl flex-shrink-0 bg-gradient-to-br from-cyan-50 to-violet-50 p-1" />
            </div>
            <div className="bg-white/10 backdrop-blur-sm border border-white/15 rounded-2xl px-6 py-4 max-w-lg text-start">
              <p className="text-white/90 font-tajawal text-base leading-relaxed">
                <span className="text-brand-turquoise font-bold font-cairo">{t('hakim2')}</span>
                {t('goodEducationStartsWithGoodDecisionsAndGoodDecisio')
                }
              </p>
            </div>
          </div>

          <Button asChild size="lg" className="bg-gradient-to-r from-brand-turquoise to-cyan-500 hover:from-brand-turquoise-light hover:to-cyan-400 text-white rounded-2xl h-16 px-14 text-xl font-cairo font-bold shadow-2xl shadow-brand-turquoise/30 hover:shadow-2xl hover:shadow-brand-turquoise/40 transition-all hover:scale-[1.03]" data-testid="cta-register-btn">
            <Link to="/register" className="flex items-center gap-3">
              {t('registerNow')}
              {isRTL ? <ArrowLeft className="h-6 w-6" /> : <ArrowRight className="h-6 w-6" />}
            </Link>
          </Button>
        </div>
      </section>

      <Footer />
      <HakimAssistant />
    </div>
  );
};
