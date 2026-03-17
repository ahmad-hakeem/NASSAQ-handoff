import { useState, useEffect } from 'react';
import TeacherHomePage from './TeacherHomePage';
import TeacherMainDashboard from './TeacherMainDashboard';

const MOBILE_BREAKPOINT = 768;

export default function TeacherResponsiveDashboard() {
  const [isMobile, setIsMobile] = useState(window.innerWidth < MOBILE_BREAKPOINT);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return isMobile ? <TeacherHomePage /> : <TeacherMainDashboard />;
}
