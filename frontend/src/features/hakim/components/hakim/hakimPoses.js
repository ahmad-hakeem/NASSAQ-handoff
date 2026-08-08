const HAKIM_POSES = {
  'friendly-greeting': '/hakim-poses/friendly-greeting.png',
  'hand-wave-greeting': '/hakim-poses/hand-wave-greeting.png',
  'inviting-to-begin': '/hakim-poses/inviting-to-begin.png',
  'open-hands-welcoming': '/hakim-poses/open-hands-welcoming.png',
  'pointing-to-start': '/hakim-poses/pointing-to-start.png',
  'slight-bow-greeting': '/hakim-poses/slight-bow-greeting.png',
  'welcome': '/hakim-poses/welcome.png',
  'explaining-concept': '/hakim-poses/explaining-concept.png',
  'giving-instructions': '/hakim-poses/giving-instructions.png',
  'ai-thinking': '/hakim-poses/ai-thinking.png',
  'ai-thinking-2': '/hakim-poses/ai-thinking-2.png',
  'attention-gesture': '/hakim-poses/attention-gesture.png',
  'clapping-celebration': '/hakim-poses/clapping-celebration.png',
  'congratulating-student': '/hakim-poses/congratulating-student.png',
  'detecting-patterns': '/hakim-poses/detecting-patterns.png',
  'listening': '/hakim-poses/listening.png',
  'motivating': '/hakim-poses/motivating.png',
  'positive-feedback': '/hakim-poses/positive-feedback.png',
  'analyzing-data': '/hakim-poses/analyzing-data.png',
  'looking-at-charts': '/hakim-poses/looking-at-charts.png',
  'support': '/hakim-poses/support.png',
  'teacher-helper': '/hakim-poses/teacher-helper.png',
};

const POSE_CATEGORIES = {
  welcome: ['friendly-greeting', 'hand-wave-greeting', 'open-hands-welcoming', 'welcome', 'slight-bow-greeting'],
  onboarding: ['giving-instructions', 'explaining-concept', 'inviting-to-begin', 'pointing-to-start'],
  teaching: ['giving-instructions', 'explaining-concept', 'pointing-to-start'],
  analysis: ['ai-thinking', 'ai-thinking-2', 'detecting-patterns', 'analyzing-data', 'looking-at-charts'],
  alert: ['attention-gesture', 'explaining-concept', 'support'],
  listening: ['listening', 'explaining-concept'],
  success: ['positive-feedback', 'motivating', 'congratulating-student', 'clapping-celebration'],
  celebration: ['clapping-celebration', 'congratulating-student', 'positive-feedback'],
  guidance: ['explaining-concept', 'giving-instructions', 'inviting-to-begin'],
};

const CONTEXT_MAP = {
  '/': 'welcome',
  '/login': 'welcome',
  '/register': 'onboarding',
  '/admin': 'analysis',
  '/admin/dashboard': 'analysis',
  '/admin/tenants': 'analysis',
  '/admin/schools': 'analysis',
  '/admin/monitoring': 'analysis',
  '/admin/audit': 'analysis',
  '/principal/ai-insights': 'analysis',
  '/admin/security': 'alert',
  '/admin/attendance': 'analysis',
  '/admin/students': 'guidance',
  '/admin/teachers': 'guidance',
  '/admin/classes': 'guidance',
  '/admin/users-management': 'guidance',
  '/principal': 'analysis',
  '/principal/dashboard': 'analysis',
  '/principal/users-management': 'guidance',
  '/principal/communication': 'guidance',
  // Principal route audit 2026-07-28: canonical leadership URLs under
  // /principal/* — mirrors of the legacy /admin//school keys.
  '/principal/attendance': 'analysis',
  '/principal/students': 'guidance',
  '/principal/classes': 'guidance',
  '/principal/subjects': 'guidance',
  '/principal/schedule': 'teaching',
  '/principal/settings': 'guidance',
  '/principal/teacher-attendance': 'analysis',
  '/principal/standby': 'teaching',
  '/school': 'analysis',
  '/school/dashboard': 'analysis',
  '/school/schedule': 'teaching',
  '/school/timetable': 'teaching',
  '/school/assessments': 'teaching',
  '/school/communication': 'guidance',
  '/school/ai-insights': 'analysis',
  '/school/settings': 'guidance',
  '/principal/ai-insights': 'analysis',
  '/teacher': 'teaching',
  '/teacher/home': 'teaching',
  '/teacher/session/start': 'teaching',
  '/teacher/session/teach': 'teaching',
  '/teacher/attendance': 'teaching',
  '/teacher/assessments': 'teaching',
  '/teacher/behavior': 'guidance',
  '/teacher/schedule': 'teaching',
  '/teacher/students': 'guidance',
  '/teacher/classes': 'teaching',
  '/teacher/achievements': 'success',
  '/teacher/settings': 'guidance',
  '/student': 'guidance',
  '/student/grades': 'analysis',
  '/student/achievements': 'success',
  '/student/progress': 'analysis',
  '/parent': 'guidance',
  '/parent/children': 'guidance',
  '/parent/messages': 'guidance',
};

const _lastUsed = {};

function getRandomNonRepeat(arr, contextKey) {
  if (!arr || arr.length === 0) return null;
  if (arr.length === 1) return arr[0];
  const last = _lastUsed[contextKey];
  const filtered = arr.filter(item => item !== last);
  const pick = filtered[Math.floor(Math.random() * filtered.length)];
  _lastUsed[contextKey] = pick;
  return pick;
}

export function getPoseForContext(context) {
  const category = typeof context === 'string' && POSE_CATEGORIES[context]
    ? context
    : null;
  if (category) {
    const poseKey = getRandomNonRepeat(POSE_CATEGORIES[category], `ctx_${category}`);
    return HAKIM_POSES[poseKey];
  }
  return HAKIM_POSES['friendly-greeting'];
}

export function getPoseForPath(pathname) {
  const category = CONTEXT_MAP[pathname];
  if (category) return getPoseForContext(category);

  for (const [path, cat] of Object.entries(CONTEXT_MAP)) {
    if (pathname.startsWith(path) && path !== '/') {
      return getPoseForContext(cat);
    }
  }
  return getPoseForContext('welcome');
}

export function getPose(poseKey) {
  return HAKIM_POSES[poseKey] || HAKIM_POSES['friendly-greeting'];
}

export function getRandomPoseFromCategory(category) {
  const poses = POSE_CATEGORIES[category];
  if (!poses || poses.length === 0) return HAKIM_POSES['friendly-greeting'];
  const key = getRandomNonRepeat(poses, `cat_${category}`);
  return HAKIM_POSES[key];
}

export const HERO_POSES = [
  '/hakim-poses/welcome.png',
  '/hakim-poses/pointing-to-start.png',
  '/hakim-poses/slight-bow-greeting.png',
];

export { HAKIM_POSES, POSE_CATEGORIES, CONTEXT_MAP };
export default HAKIM_POSES;
