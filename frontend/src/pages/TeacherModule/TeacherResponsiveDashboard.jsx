import { useState, useLayoutEffect } from 'react';
import TeacherHomePage from './TeacherHomePage';
import TeacherMainDashboard from './TeacherMainDashboard';

const MOBILE_BREAKPOINT = 768;

const isMobileViewport = () =>
  typeof window !== 'undefined' && window.innerWidth < MOBILE_BREAKPOINT;

export default function TeacherResponsiveDashboard() {
  // Seed from the real viewport. Defaulting to `false` meant a phone mounted
  // the desktop dashboard first, fired its whole data fetch (dashboard,
  // class-metrics, achievements), and only then swapped to the mobile page —
  // which fetched the same endpoints again.
  const [isMobile, setIsMobile] = useState(isMobileViewport);

  useLayoutEffect(() => {
    const check = () => setIsMobile(isMobileViewport());
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  return isMobile ? <TeacherHomePage /> : <TeacherMainDashboard />;
}
