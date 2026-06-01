import { useState, useLayoutEffect } from 'react';
import TeacherHomePage from './TeacherHomePage';
import TeacherMainDashboard from './TeacherMainDashboard';

const MOBILE_BREAKPOINT = 768;

export default function TeacherResponsiveDashboard() {
  const [isMobile, setIsMobile] = useState(false);

  useLayoutEffect(() => {
    const check = () => setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  return isMobile ? <TeacherHomePage /> : <TeacherMainDashboard />;
}
