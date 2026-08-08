import { useLocation } from 'react-router-dom';
import { useAuth } from '@/shared/contexts/AuthContext';
import { useParentActiveStudent } from '@/shared/contexts/ParentActiveStudentContext';
import { HakimAssistant } from './HakimAssistant';
import HakimChatWidget from '@/features/parent-portal/components/parent/HakimChatWidget';

// Single global mount point for the Hakim assistant (rendered once from
// App.js). Replaces the old per-page <HakimAssistant /> mounts, which left
// the assistant missing from every page that forgot to render it (e.g.
// فصولي / TeacherClassesPage) and double-mounted it inside PublicShell.
//
// Routes where Hakim must NOT appear: auth/credential flows, one-shot
// token-redemption landings, legal documents, and the IT onboarding wizard.
const HIDDEN_PREFIXES = [
  '/login',
  '/register',
  '/registration-confirmation',
  '/forgot-password',
  '/reset-password',
  '/change-password',
  '/teacher-register',
  '/auth/mfa',
  '/parent-invitations',
  '/teacher/collab-accept',
  '/workspace-collaborators',
  '/account-erased',
  '/privacy',
  '/terms',
  '/parent/legal',
  '/teacher/onboarding',
];

// Public marketing pages keep the anonymous Hakim chat (streams via the
// /public/hakim endpoints inside HakimAssistant when there is no user).
const PUBLIC_HAKIM_PATHS = ['/', '/for-teachers'];

const isHidden = (path) =>
  HIDDEN_PREFIXES.some((p) => path === p || path.startsWith(`${p}/`));

export default function GlobalHakimMount() {
  const location = useLocation();
  const { user, getEffectiveRole, getEffectiveTenantId } = useAuth();
  const { activeChild } = useParentActiveStudent();

  const path = location.pathname;
  if (isHidden(path)) return null;

  const isPublicPath = PUBLIC_HAKIM_PATHS.includes(path);
  if (!user && !isPublicPath) return null;

  // Key the assistant off the effective role + tenant + user (same contract
  // as the <Routes> tree in appRoutes.js) so chat history can never survive
  // impersonation enter/exit, role switches, or login/logout.
  const role =
    (typeof getEffectiveRole === 'function' ? getEffectiveRole() : null) ||
    user?.role ||
    'anon';
  const tid =
    (typeof getEffectiveTenantId === 'function' ? getEffectiveTenantId() : null) ||
    'self';
  const mountKey = `${role}:${tid}:${user?.id || 'anon'}`;

  // Parents get the child-aware widget on every portal page, fed by the
  // global active-student context; `raised` clears the mobile bottom nav.
  if (user && role === 'parent' && (path === '/parent' || path.startsWith('/parent/'))) {
    return (
      <HakimChatWidget
        key={mountKey}
        childId={activeChild?.id || null}
        childName={activeChild?.name ? String(activeChild.name).split(' ')[0] : undefined}
        raised
      />
    );
  }

  return <HakimAssistant key={mountKey} />;
}
