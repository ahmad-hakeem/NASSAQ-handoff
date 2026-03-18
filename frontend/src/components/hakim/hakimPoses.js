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
};

const POSE_CATEGORIES = {
  welcome: ['friendly-greeting', 'hand-wave-greeting', 'open-hands-welcoming', 'welcome', 'slight-bow-greeting'],
  onboarding: ['giving-instructions', 'explaining-concept', 'inviting-to-begin', 'pointing-to-start'],
  teaching: ['giving-instructions', 'explaining-concept', 'pointing-to-start'],
  analysis: ['ai-thinking', 'ai-thinking-2', 'detecting-patterns'],
  alert: ['attention-gesture', 'explaining-concept'],
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
  '/admin/analytics': 'analysis',
  '/admin/security': 'alert',
  '/admin/attendance': 'analysis',
  '/admin/students': 'guidance',
  '/admin/teachers': 'guidance',
  '/admin/classes': 'guidance',
  '/admin/users-management': 'guidance',
  '/principal': 'analysis',
  '/principal/dashboard': 'analysis',
  '/principal/timetable': 'teaching',
  '/principal/users-management': 'guidance',
  '/principal/communication': 'guidance',
  '/school': 'analysis',
  '/school/dashboard': 'analysis',
  '/school/schedule': 'teaching',
  '/school/timetable': 'teaching',
  '/school/assessments': 'teaching',
  '/school/communication': 'guidance',
  '/school/ai-insights': 'analysis',
  '/school/analytics': 'analysis',
  '/school/settings': 'guidance',
  '/school/reports': 'analysis',
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
  '/teacher/reports': 'analysis',
  '/teacher/achievements': 'success',
  '/teacher/settings': 'guidance',
  '/student': 'guidance',
  '/student/grades': 'analysis',
  '/student/homework': 'teaching',
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
  '/hakim-poses/slight-bow-greeting.png',
  '/hakim-poses/pointing-to-start.png',
  '/hakim-poses/friendly-greeting.png',
];

export { HAKIM_POSES, POSE_CATEGORIES, CONTEXT_MAP };
export default HAKIM_POSES;
