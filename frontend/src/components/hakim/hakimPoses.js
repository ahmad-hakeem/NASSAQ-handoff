const HAKIM_POSES = {
  'friendly-greeting': '/hakim-poses/friendly-greeting.png',
  'hand-wave-greeting': '/hakim-poses/hand-wave-greeting.png',
  'introducing-system': '/hakim-poses/introducing-system.png',
  'inviting-to-begin': '/hakim-poses/inviting-to-begin.png',
  'open-hands-welcoming': '/hakim-poses/open-hands-welcoming.png',
  'pointing-to-start': '/hakim-poses/pointing-to-start.png',
  'slight-bow-greeting': '/hakim-poses/slight-bow-greeting.png',
  'support': '/hakim-poses/support.png',
  'welcome': '/hakim-poses/welcome.png',
  'explaining-concept': '/hakim-poses/explaining-concept.png',
  'giving-instructions': '/hakim-poses/giving-instructions.png',
  'pointing-to-board': '/hakim-poses/pointing-to-board.png',
  'teacher-helper': '/hakim-poses/teacher-helper.png',
  'teaching': '/hakim-poses/teaching.png',
  'ai-thinking': '/hakim-poses/ai-thinking.png',
  'analyzing-data': '/hakim-poses/analyzing-data.png',
  'attention-gesture': '/hakim-poses/attention-gesture.png',
  'clapping-celebration': '/hakim-poses/clapping-celebration.png',
  'congratulating-student': '/hakim-poses/congratulating-student.png',
  'detecting-patterns': '/hakim-poses/detecting-patterns.png',
  'listening': '/hakim-poses/listening.png',
  'looking-at-charts': '/hakim-poses/looking-at-charts.png',
  'motivating': '/hakim-poses/motivating.png',
  'positive-feedback': '/hakim-poses/positive-feedback.png',
};

const POSE_CATEGORIES = {
  welcome: ['friendly-greeting', 'hand-wave-greeting', 'open-hands-welcoming', 'welcome', 'slight-bow-greeting', 'introducing-system'],
  onboarding: ['giving-instructions', 'explaining-concept', 'support', 'teacher-helper', 'inviting-to-begin', 'pointing-to-start'],
  teaching: ['teaching', 'teacher-helper', 'pointing-to-board', 'explaining-concept'],
  analysis: ['ai-thinking', 'analyzing-data', 'looking-at-charts', 'detecting-patterns'],
  alert: ['attention-gesture', 'support', 'explaining-concept'],
  listening: ['listening', 'explaining-concept', 'support'],
  success: ['positive-feedback', 'motivating', 'congratulating-student', 'clapping-celebration'],
  celebration: ['clapping-celebration', 'congratulating-student', 'positive-feedback'],
  guidance: ['explaining-concept', 'giving-instructions', 'pointing-to-board', 'support'],
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

function getRandomFromArray(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

export function getPoseForContext(context) {
  const category = typeof context === 'string' && POSE_CATEGORIES[context]
    ? context
    : null;
  if (category) {
    const poseKey = getRandomFromArray(POSE_CATEGORIES[category]);
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
  const key = getRandomFromArray(poses);
  return HAKIM_POSES[key];
}

export { HAKIM_POSES, POSE_CATEGORIES, CONTEXT_MAP };
export default HAKIM_POSES;
