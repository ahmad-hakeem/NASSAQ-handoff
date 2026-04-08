import { HAKIM_POSES, POSE_CATEGORIES } from './hakimPoses';

const ANIMATION_LEVELS = {
  IDLE: 'idle',
  INTERACTION: 'interaction',
  CELEBRATION: 'celebration',
};

const SYSTEM_EVENTS = {
  PAGE_LOAD: 'page_load',
  FIRST_LOGIN: 'first_login',
  TASK_COMPLETED: 'task_completed',
  SCHEDULE_CREATED: 'schedule_created',
  TIMETABLE_PUBLISHED: 'timetable_published',
  ATTENDANCE_RECORDED: 'attendance_recorded',
  ASSESSMENT_CREATED: 'assessment_created',
  AI_ANALYSIS_READY: 'ai_analysis_ready',
  SYSTEM_ALERT: 'system_alert',
  ERROR_OCCURRED: 'error_occurred',
  STUDENT_ACHIEVEMENT: 'student_achievement',
  SESSION_STARTED: 'session_started',
  SESSION_ENDED: 'session_ended',
  DATA_EXPORTED: 'data_exported',
  SETTINGS_SAVED: 'settings_saved',
  USER_CREATED: 'user_created',
  BULK_IMPORT_DONE: 'bulk_import_done',
  REPORT_GENERATED: 'report_generated',
  ONBOARDING_STEP: 'onboarding_step',
  HELP_REQUESTED: 'help_requested',
};

const ROLE_CONTEXT = {
  platform_admin: {
    defaultCategory: 'analysis',
    idleMessage: 'مرحبًا مدير المنصة… أنا جاهز لمساعدتك.',
  },
  school_principal: {
    defaultCategory: 'analysis',
    idleMessage: 'مرحبًا… أنا حكيم، مستشارك الذكي.',
  },
  school_admin: {
    defaultCategory: 'guidance',
    idleMessage: 'مرحبًا… كيف أساعدك اليوم؟',
  },
  teacher: {
    defaultCategory: 'teaching',
    idleMessage: 'مرحبًا أستاذ… أنا هنا لمساعدتك.',
  },
  student: {
    defaultCategory: 'guidance',
    idleMessage: 'أهلاً… أنا حكيم، مساعدك الذكي!',
  },
  parent: {
    defaultCategory: 'guidance',
    idleMessage: 'مرحبًا ولي الأمر… أنا حكيم.',
  },
};

const PATH_CONTEXT_RULES = [
  { path: '/', exact: true, context: 'landing', category: 'welcome', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/login', exact: true, context: 'login', category: 'welcome', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/register', exact: true, context: 'register', category: 'onboarding', animLevel: ANIMATION_LEVELS.INTERACTION },

  { path: '/principal', exact: true, context: 'principal_dashboard', category: 'analysis', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/principal/dashboard', context: 'principal_dashboard', category: 'analysis', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/principal/timetable', context: 'timetable', category: 'teaching', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/principal/users-management', context: 'users_management', category: 'guidance', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/principal/communication', context: 'communication', category: 'guidance', animLevel: ANIMATION_LEVELS.IDLE },

  { path: '/school', exact: true, context: 'school_dashboard', category: 'analysis', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/school/dashboard', context: 'school_dashboard', category: 'analysis', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/school/settings', context: 'settings', category: 'guidance', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/school/schedule', context: 'schedule', category: 'teaching', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/school/reports', context: 'reports', category: 'analysis', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/school/ai-insights', context: 'ai_insights', category: 'analysis', animLevel: ANIMATION_LEVELS.INTERACTION },
  { path: '/school/analytics', context: 'analytics', category: 'analysis', animLevel: ANIMATION_LEVELS.IDLE },

  { path: '/teacher', exact: true, context: 'teacher_home', category: 'teaching', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/teacher/home', context: 'teacher_home', category: 'teaching', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/teacher/session/start', context: 'session_start', category: 'teaching', animLevel: ANIMATION_LEVELS.INTERACTION },
  { path: '/teacher/session/teach', context: 'session_teach', category: 'teaching', animLevel: ANIMATION_LEVELS.INTERACTION },
  { path: '/teacher/attendance', context: 'attendance', category: 'teaching', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/teacher/assessments', context: 'assessments', category: 'teaching', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/teacher/behavior', context: 'behavior', category: 'guidance', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/teacher/schedule', context: 'teacher_schedule', category: 'teaching', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/teacher/students', context: 'teacher_students', category: 'guidance', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/teacher/classes', context: 'teacher_classes', category: 'teaching', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/principal/ai-insights', context: 'ai_insights', category: 'analysis', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/teacher/achievements', context: 'achievements', category: 'success', animLevel: ANIMATION_LEVELS.IDLE },

  { path: '/student', context: 'student_portal', category: 'guidance', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/parent', context: 'parent_portal', category: 'guidance', animLevel: ANIMATION_LEVELS.IDLE },

  { path: '/admin', exact: true, context: 'admin_dashboard', category: 'analysis', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/admin/dashboard', context: 'admin_dashboard', category: 'analysis', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/admin/schools', context: 'admin_schools', category: 'analysis', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/admin/tenants', context: 'admin_tenants', category: 'analysis', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/admin/monitoring', context: 'monitoring', category: 'analysis', animLevel: ANIMATION_LEVELS.IDLE },
  { path: '/admin/audit', context: 'audit', category: 'analysis', animLevel: ANIMATION_LEVELS.IDLE },
];

const EVENT_REACTIONS = {
  [SYSTEM_EVENTS.TASK_COMPLETED]: {
    category: 'success',
    animLevel: ANIMATION_LEVELS.CELEBRATION,
    messages: [
      'أحسنت! تم تنفيذ العملية بنجاح.',
      'ممتاز! تم الإنجاز.',
      'عمل رائع… أحسنت!',
    ],
    duration: 4000,
  },
  [SYSTEM_EVENTS.SCHEDULE_CREATED]: {
    category: 'celebration',
    animLevel: ANIMATION_LEVELS.CELEBRATION,
    messages: [
      'تم إنشاء الجدول بنجاح! عمل ممتاز.',
      'الجدول جاهز… أحسنت التخطيط!',
    ],
    duration: 5000,
  },
  [SYSTEM_EVENTS.TIMETABLE_PUBLISHED]: {
    category: 'celebration',
    animLevel: ANIMATION_LEVELS.CELEBRATION,
    messages: [
      'تم نشر الجدول! أصبح متاحًا للجميع الآن.',
      'ممتاز! الجدول منشور وجاهز.',
    ],
    duration: 5000,
  },
  [SYSTEM_EVENTS.ATTENDANCE_RECORDED]: {
    category: 'success',
    animLevel: ANIMATION_LEVELS.INTERACTION,
    messages: [
      'تم تسجيل الحضور بنجاح.',
      'أحسنت! تم رصد الحضور.',
    ],
    duration: 3000,
  },
  [SYSTEM_EVENTS.ASSESSMENT_CREATED]: {
    category: 'success',
    animLevel: ANIMATION_LEVELS.INTERACTION,
    messages: [
      'تم إنشاء التقييم بنجاح!',
      'ممتاز! التقييم جاهز.',
    ],
    duration: 3000,
  },
  [SYSTEM_EVENTS.AI_ANALYSIS_READY]: {
    category: 'analysis',
    animLevel: ANIMATION_LEVELS.INTERACTION,
    messages: [
      'لاحظت نمطًا مهمًا في البيانات.',
      'تم تحليل البيانات… لدي ملاحظات مهمة.',
      'اكتشفت شيئًا يستحق الانتباه.',
    ],
    duration: 5000,
  },
  [SYSTEM_EVENTS.SYSTEM_ALERT]: {
    category: 'alert',
    animLevel: ANIMATION_LEVELS.INTERACTION,
    messages: [
      'يرجى الانتباه… هناك تنبيه مهم.',
      'لاحظت مشكلة تحتاج انتباهك.',
    ],
    duration: 5000,
  },
  [SYSTEM_EVENTS.ERROR_OCCURRED]: {
    category: 'alert',
    animLevel: ANIMATION_LEVELS.INTERACTION,
    messages: [
      'حدث خطأ… دعني أساعدك.',
      'لا تقلق، يمكننا حل هذا معًا.',
    ],
    duration: 4000,
  },
  [SYSTEM_EVENTS.STUDENT_ACHIEVEMENT]: {
    category: 'celebration',
    animLevel: ANIMATION_LEVELS.CELEBRATION,
    messages: [
      'أحسنت! إنجاز رائع.',
      'مبروك! استمر في التميز.',
    ],
    duration: 4000,
  },
  [SYSTEM_EVENTS.SESSION_STARTED]: {
    category: 'teaching',
    animLevel: ANIMATION_LEVELS.INTERACTION,
    messages: [
      'بالتوفيق في الحصة!',
      'حصة موفقة إن شاء الله.',
    ],
    duration: 3000,
  },
  [SYSTEM_EVENTS.SESSION_ENDED]: {
    category: 'success',
    animLevel: ANIMATION_LEVELS.INTERACTION,
    messages: [
      'أحسنت! تم إنهاء الحصة بنجاح.',
      'حصة ناجحة… بارك الله فيك.',
    ],
    duration: 3000,
  },
  [SYSTEM_EVENTS.DATA_EXPORTED]: {
    category: 'success',
    animLevel: ANIMATION_LEVELS.IDLE,
    messages: [
      'تم التصدير بنجاح!',
    ],
    duration: 2500,
  },
  [SYSTEM_EVENTS.SETTINGS_SAVED]: {
    category: 'success',
    animLevel: ANIMATION_LEVELS.IDLE,
    messages: [
      'تم حفظ الإعدادات.',
      'تم التحديث بنجاح.',
    ],
    duration: 2500,
  },
  [SYSTEM_EVENTS.USER_CREATED]: {
    category: 'success',
    animLevel: ANIMATION_LEVELS.INTERACTION,
    messages: [
      'تم إضافة المستخدم بنجاح!',
      'أهلاً بالعضو الجديد!',
    ],
    duration: 3000,
  },
  [SYSTEM_EVENTS.BULK_IMPORT_DONE]: {
    category: 'celebration',
    animLevel: ANIMATION_LEVELS.CELEBRATION,
    messages: [
      'تم الاستيراد بنجاح! البيانات جاهزة.',
      'ممتاز! تم استيراد جميع البيانات.',
    ],
    duration: 4000,
  },
  [SYSTEM_EVENTS.REPORT_GENERATED]: {
    category: 'success',
    animLevel: ANIMATION_LEVELS.INTERACTION,
    messages: [
      'التقرير جاهز!',
      'تم إعداد التقرير بنجاح.',
    ],
    duration: 3000,
  },
  [SYSTEM_EVENTS.ONBOARDING_STEP]: {
    category: 'onboarding',
    animLevel: ANIMATION_LEVELS.INTERACTION,
    messages: [
      'دعني أرشدك للخطوة التالية.',
      'أنت تسير بشكل رائع… تابع!',
    ],
    duration: 4000,
  },
  [SYSTEM_EVENTS.HELP_REQUESTED]: {
    category: 'listening',
    animLevel: ANIMATION_LEVELS.INTERACTION,
    messages: [
      'أنا أستمع… كيف أساعدك؟',
      'بالطبع! أخبرني بما تحتاج.',
    ],
    duration: 0,
  },
  [SYSTEM_EVENTS.FIRST_LOGIN]: {
    category: 'welcome',
    animLevel: ANIMATION_LEVELS.INTERACTION,
    messages: [
      'مرحبًا بك في نَسَّق! أنا حكيم، مساعدك الذكي.',
      'أهلاً وسهلاً! دعني أرشدك لاستكشاف المنصة.',
    ],
    duration: 6000,
  },
};

const PAGE_MESSAGES = {
  landing: {
    messages: [
      'مرحبًا… أنا حكيم، مساعدك الذكي في نَسَّق.',
      'أهلاً بك في منصة نَسَّق التعليمية.',
    ],
  },
  login: {
    messages: [
      'مرحبًا بعودتك!',
      'أهلاً… سجل دخولك للمتابعة.',
    ],
  },
  principal_dashboard: {
    messages: [
      'مرحبًا… إليك ملخص أداء المدرسة اليوم.',
      'صباح الخير… لدي تحديثات مهمة لك.',
    ],
  },
  school_dashboard: {
    messages: [
      'أنا أراقب أداء المدرسة… إليك آخر المستجدات.',
      'لدي بعض الملاحظات حول أداء اليوم.',
    ],
  },
  timetable: {
    messages: [
      'الجدول المدرسي… دعني أساعدك في تنظيمه.',
      'يمكنك سحب الحصص لإعادة ترتيبها.',
    ],
  },
  ai_insights: {
    messages: [
      'دعني أفكر قليلاً… أقوم بتحليل البيانات.',
      'لاحظت أنماطًا مهمة في بيانات المدرسة.',
      'لدي رؤى ذكية أحب أن أشاركها معك.',
    ],
  },
  analytics: {
    messages: [
      'أنا أحلل الأرقام… لحظة.',
      'دعني أعرض لك أهم المؤشرات.',
    ],
  },
  teacher_home: {
    messages: [
      'صباح الخير أستاذ… إليك برنامج اليوم.',
      'مرحبًا… لديك حصص اليوم، هل أنت جاهز؟',
    ],
  },
  session_start: {
    messages: [
      'حصة موفقة إن شاء الله!',
      'هل أنت جاهز لبدء الحصة؟',
    ],
  },
  session_teach: {
    messages: [
      'أنا هنا إذا احتجت مساعدة أثناء الحصة.',
      'استمر… أنت تقوم بعمل رائع!',
    ],
  },
  attendance: {
    messages: [
      'لنسجل الحضور… جاهز!',
      'هل تحتاج مساعدة في رصد الحضور؟',
    ],
  },
  settings: {
    messages: [
      'إعدادات المدرسة… تأكد من ضبط كل شيء.',
      'دعني أرشدك في الإعدادات.',
    ],
  },
  reports: {
    messages: [
      'التقارير جاهزة للمراجعة.',
      'دعني أعرض لك أهم الإحصائيات.',
    ],
  },
  student_portal: {
    messages: [
      'أهلاً! كيف يومك الدراسي؟',
      'أنا هنا لمساعدتك… ماذا تحتاج؟',
    ],
  },
  parent_portal: {
    messages: [
      'مرحبًا ولي الأمر… إليك آخر المستجدات عن أبنائك.',
      'أنا أتابع تقدم أبنائك باستمرار.',
    ],
  },
  admin_dashboard: {
    messages: [
      'مرحبًا مدير المنصة… إليك نظرة عامة.',
      'لدي تقرير شامل عن المنصة.',
    ],
  },
  users_management: {
    messages: [
      'إدارة المستخدمين… كيف أساعدك؟',
    ],
  },
  communication: {
    messages: [
      'مركز التواصل… أنا جاهز للمساعدة.',
    ],
  },
};

function getRandomItem(arr) {
  if (!arr || arr.length === 0) return null;
  return arr[Math.floor(Math.random() * arr.length)];
}

function getRandomPoseKeyFromCategory(categoryName) {
  const poses = POSE_CATEGORIES[categoryName];
  if (!poses || poses.length === 0) return 'friendly-greeting';
  return getRandomItem(poses);
}

class HakimContextEngine {
  constructor() {
    this._listeners = new Set();
    this._currentState = {
      pose: 'friendly-greeting',
      poseUrl: HAKIM_POSES['friendly-greeting'],
      category: 'welcome',
      animationLevel: ANIMATION_LEVELS.IDLE,
      message: '',
      context: 'landing',
      visible: true,
      event: null,
      eventExpiry: null,
    };
    this._eventTimer = null;
  }

  getState() {
    return { ...this._currentState };
  }

  subscribe(listener) {
    this._listeners.add(listener);
    return () => this._listeners.delete(listener);
  }

  _notify() {
    const state = this.getState();
    this._listeners.forEach(fn => {
      try { fn(state); } catch (e) { /* ignore */ }
    });
  }

  detectContext(pathname, userRole) {
    let matched = null;
    for (const rule of PATH_CONTEXT_RULES) {
      if (rule.exact && pathname === rule.path) {
        matched = rule;
        break;
      }
      if (!rule.exact && pathname.startsWith(rule.path)) {
        if (!matched || rule.path.length > matched.path.length) {
          matched = rule;
        }
      }
    }

    if (!matched) {
      const roleCtx = ROLE_CONTEXT[userRole] || ROLE_CONTEXT.school_principal;
      matched = {
        context: 'default',
        category: roleCtx.defaultCategory,
        animLevel: ANIMATION_LEVELS.IDLE,
      };
    }

    if (this._currentState.event && this._currentState.eventExpiry && Date.now() < this._currentState.eventExpiry) {
      return;
    }

    const poseKey = getRandomPoseKeyFromCategory(matched.category);
    const pageMessages = PAGE_MESSAGES[matched.context];
    const roleCtx = ROLE_CONTEXT[userRole];
    const message = pageMessages
      ? getRandomItem(pageMessages.messages)
      : (roleCtx ? roleCtx.idleMessage : '');

    this._currentState = {
      pose: poseKey,
      poseUrl: HAKIM_POSES[poseKey] || HAKIM_POSES['friendly-greeting'],
      category: matched.category,
      animationLevel: matched.animLevel || ANIMATION_LEVELS.IDLE,
      message,
      context: matched.context,
      visible: true,
      event: null,
      eventExpiry: null,
    };

    this._notify();
  }

  fireEvent(eventName, customMessage = null) {
    const reaction = EVENT_REACTIONS[eventName];
    if (!reaction) return;

    if (this._eventTimer) {
      clearTimeout(this._eventTimer);
      this._eventTimer = null;
    }

    const poseKey = getRandomPoseKeyFromCategory(reaction.category);
    const message = customMessage || getRandomItem(reaction.messages) || '';

    this._currentState = {
      ...this._currentState,
      pose: poseKey,
      poseUrl: HAKIM_POSES[poseKey] || HAKIM_POSES['friendly-greeting'],
      category: reaction.category,
      animationLevel: reaction.animLevel,
      message,
      event: eventName,
      eventExpiry: reaction.duration > 0 ? Date.now() + reaction.duration : null,
      visible: true,
    };

    this._notify();

    if (reaction.duration > 0) {
      this._eventTimer = setTimeout(() => {
        this._currentState = {
          ...this._currentState,
          event: null,
          eventExpiry: null,
          animationLevel: ANIMATION_LEVELS.IDLE,
        };
        this._notify();
      }, reaction.duration);
    }
  }

  setVisibility(visible) {
    if (this._currentState.visible !== visible) {
      this._currentState = { ...this._currentState, visible };
      this._notify();
    }
  }

  getIdleMessage(userRole) {
    const roleCtx = ROLE_CONTEXT[userRole];
    return roleCtx ? roleCtx.idleMessage : 'مرحبًا… أنا حكيم.';
  }

  destroy() {
    if (this._eventTimer) clearTimeout(this._eventTimer);
    this._listeners.clear();
  }
}

const hakimEngine = new HakimContextEngine();

export {
  ANIMATION_LEVELS,
  SYSTEM_EVENTS,
  ROLE_CONTEXT,
  PATH_CONTEXT_RULES,
  EVENT_REACTIONS,
  PAGE_MESSAGES,
  HakimContextEngine,
};

export default hakimEngine;
