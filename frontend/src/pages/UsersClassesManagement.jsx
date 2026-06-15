import { useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useTheme , useTranslation } from '../contexts/ThemeContext';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/layout/Sidebar';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { Label } from '../components/ui/label';
import { Progress } from '../components/ui/progress';
import { toast } from 'sonner';
import { useNassaqAlert } from '../components/ui/NassaqAlertDialog';
import {
  Users, UserPlus, GraduationCap, School, Search, Plus, Sun, Moon,
  Globe, MoreHorizontal, Edit, Trash2, Mail, Phone, BookOpen, Loader2,
  RefreshCw, Eye, UserCheck, Award, Calendar, Hash, Building2, Upload,
  Download, FileSpreadsheet, FileUp, FileDown, Save, Key, UserX,
  Sparkles, X, AlertTriangle, Wrench, ArrowRight, Clock,
  UserCircle, ChevronRight, ExternalLink, Zap, BarChart3,
  LayoutGrid, List, Heart, Shield, ArrowUpDown, ArrowUp, ArrowDown, Star,
  RotateCcw
} from 'lucide-react';
import { Switch } from '../components/ui/switch';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuTrigger, DropdownMenuSeparator
} from '../components/ui/dropdown-menu';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogDescription, DialogFooter
} from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { CANONICAL_GRADES } from '../utils/stageGrade';
import { NotificationBell } from '../components/notifications/NotificationBell';
import AddStudentWizard from '../components/wizards/AddStudentWizard';
import { AddTeacherWizard } from '../components/wizards/AddTeacherWizard';
import CreateClassWizard from '../components/wizards/CreateClassWizard';
import TeacherProfileDialog from '../components/management/TeacherProfileDialog';
import ParentProfileDialog from '../components/management/ParentProfileDialog';
import StudentClassGrid from '../components/management/StudentClassGrid';
import NoorImportPanel from '../components/management/NoorImportPanel';
import { getApiErrorMessage } from '../utils/apiError';
import { executeStudentTransfer } from '../utils/studentTransfer';

// Visibility flag for the "Show them now" CTA inside the students-without-a-class
// warning banner. The warning banner, its count, and the unassigned-students
// detection stay fully intact regardless of this flag; only the optional CTA
// button is suppressed. Flip to `true` to cleanly re-enable the button.
const SHOW_NO_CLASS_BANNER_CTA = false;

const THEME_COLORS = {
  student: {
    gradient: 'from-[#1B2A4A] to-[#2563eb]',
    bg: 'bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20',
    border: 'border-blue-200/50 dark:border-blue-800',
    hoverBorder: 'hover:border-[#1B2A4A]/40',
    text: 'text-[#1B2A4A]',
    accent: 'text-blue-600',
    badge: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    badgeDot: 'bg-blue-500',
    bar: 'bg-gradient-to-r from-[#1B2A4A] to-[#2563eb]',
    icon: 'text-blue-500',
  },
  teacher: {
    gradient: 'from-emerald-600 to-green-700',
    bg: 'bg-gradient-to-br from-emerald-50 to-green-50 dark:from-emerald-950/20 dark:to-green-950/20',
    border: 'border-emerald-200/50 dark:border-emerald-800',
    hoverBorder: 'hover:border-emerald-500/40',
    text: 'text-emerald-700',
    accent: 'text-emerald-600',
    badge: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
    badgeDot: 'bg-emerald-500',
    bar: 'bg-gradient-to-r from-emerald-500 to-green-600',
    icon: 'text-emerald-500',
  },
  parent: {
    gradient: 'from-amber-500 to-orange-600',
    bg: 'bg-gradient-to-br from-amber-50 to-orange-50 dark:from-amber-950/20 dark:to-orange-950/20',
    border: 'border-amber-200/50 dark:border-amber-800',
    hoverBorder: 'hover:border-amber-500/40',
    text: 'text-amber-700',
    accent: 'text-amber-600',
    badge: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    badgeDot: 'bg-amber-500',
    bar: 'bg-gradient-to-r from-amber-500 to-orange-600',
    icon: 'text-amber-500',
  },
  class: {
    gradient: 'from-violet-500 to-purple-700',
    bg: 'bg-gradient-to-br from-violet-50 to-purple-50 dark:from-violet-950/20 dark:to-purple-950/20',
    border: 'border-violet-200/50 dark:border-violet-800',
    hoverBorder: 'hover:border-purple-500/40',
    text: 'text-purple-700',
    accent: 'text-purple-600',
    badge: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
    badgeDot: 'bg-purple-500',
    bar: 'bg-gradient-to-r from-violet-500 to-purple-600',
    icon: 'text-purple-500',
  },
};

const CartoonMaleAvatar = ({ name, size = 'md' }) => {
  const { t } = useTranslation();
  const dims = size === 'lg' ? 56 : size === 'sm' ? 32 : 44;
  return (
    <svg width={dims} height={dims} viewBox="0 0 100 100" className="shrink-0">
      <defs>
        <linearGradient id="maleBg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#1B2A4A" />
          <stop offset="100%" stopColor="#2563eb" />
        </linearGradient>
      </defs>
      <circle cx="50" cy="50" r="48" fill="url(#maleBg)" />
      <ellipse cx="50" cy="42" rx="20" ry="22" fill="#FDDCB5" />
      <path d="M30 30 Q35 15 50 18 Q65 15 70 30 Q72 22 65 20 Q55 10 45 12 Q35 10 28 22 Z" fill="#3B2314" />
      <ellipse cx="41" cy="40" rx="3.5" ry="4" fill="#2d1810" />
      <ellipse cx="59" cy="40" rx="3.5" ry="4" fill="#2d1810" />
      <circle cx="42.5" cy="39" r="1.2" fill="white" />
      <circle cx="60.5" cy="39" r="1.2" fill="white" />
      <path d="M44 51 Q50 56 56 51" stroke="#c0392b" strokeWidth="2.5" fill="none" strokeLinecap="round" />
      <ellipse cx="33" cy="45" rx="4" ry="3" fill="#F4B8A5" opacity="0.5" />
      <ellipse cx="67" cy="45" rx="4" ry="3" fill="#F4B8A5" opacity="0.5" />
      <path d="M30 70 Q50 62 70 70 L75 90 Q50 85 25 90 Z" fill="#1B2A4A" />
      <text x="50" y="82" textAnchor="middle" fill="white" fontSize="11" fontWeight="bold" fontFamily="Arial">{name?.charAt(0) || ''}</text>
    </svg>
  );
};

const CartoonFemaleAvatar = ({ name, size = 'md' }) => {
  const dims = size === 'lg' ? 56 : size === 'sm' ? 32 : 44;
  return (
    <svg width={dims} height={dims} viewBox="0 0 100 100" className="shrink-0">
      <defs>
        <linearGradient id="femaleBg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#ec4899" />
          <stop offset="100%" stopColor="#f43f5e" />
        </linearGradient>
      </defs>
      <circle cx="50" cy="50" r="48" fill="url(#femaleBg)" />
      <ellipse cx="50" cy="42" rx="20" ry="22" fill="#FDDCB5" />
      <path d="M25 35 Q28 12 50 15 Q72 12 75 35 Q76 28 72 22 Q65 8 50 10 Q35 8 28 22 Q24 28 25 35 Z" fill="#5C3317" />
      <path d="M25 35 Q24 50 28 60" stroke="#5C3317" strokeWidth="5" fill="none" strokeLinecap="round" />
      <path d="M75 35 Q76 50 72 60" stroke="#5C3317" strokeWidth="5" fill="none" strokeLinecap="round" />
      <ellipse cx="41" cy="40" rx="3" ry="3.5" fill="#2d1810" />
      <ellipse cx="59" cy="40" rx="3" ry="3.5" fill="#2d1810" />
      <circle cx="42" cy="39" r="1" fill="white" />
      <circle cx="60" cy="39" r="1" fill="white" />
      <path d="M36 35 Q41 32 46 35" stroke="#5C3317" strokeWidth="1.5" fill="none" />
      <path d="M54 35 Q59 32 64 35" stroke="#5C3317" strokeWidth="1.5" fill="none" />
      <path d="M45 51 Q50 55 55 51" stroke="#e74c6f" strokeWidth="2" fill="none" strokeLinecap="round" />
      <ellipse cx="34" cy="45" rx="4" ry="3" fill="#F4B8A5" opacity="0.6" />
      <ellipse cx="66" cy="45" rx="4" ry="3" fill="#F4B8A5" opacity="0.6" />
      <path d="M30 70 Q50 62 70 70 L75 90 Q50 85 25 90 Z" fill="#ec4899" />
      <text x="50" y="82" textAnchor="middle" fill="white" fontSize="11" fontWeight="bold" fontFamily="Arial">{name?.charAt(0) || ''}</text>
    </svg>
  );
};

const StudentAvatar = ({ student, size = 'md' }) => {
  const gender = student.gender?.toLowerCase();
  if (gender === 'female') return <CartoonFemaleAvatar name={student.full_name} size={size} />;
  return <CartoonMaleAvatar name={student.full_name} size={size} />;
};

const TeacherAvatar = ({ teacher, size = 'md' }) => {
  const dims = size === 'lg' ? 56 : size === 'sm' ? 32 : 44;
  const gender = teacher.gender?.toLowerCase();
  return (
    <svg width={dims} height={dims} viewBox="0 0 100 100" className="shrink-0">
      <defs>
        <linearGradient id="teacherBg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#059669" />
          <stop offset="100%" stopColor="#15803d" />
        </linearGradient>
      </defs>
      <circle cx="50" cy="50" r="48" fill="url(#teacherBg)" />
      <ellipse cx="50" cy="40" rx="18" ry="20" fill="#FDDCB5" />
      {gender === 'female' ? (
        <>
          <path d="M28 32 Q32 10 50 14 Q68 10 72 32 Q72 25 65 18 Q55 6 45 8 Q35 6 28 18 Q25 25 28 32 Z" fill="#5C3317" />
          <path d="M28 32 Q26 48 30 55" stroke="#5C3317" strokeWidth="4" fill="none" />
          <path d="M72 32 Q74 48 70 55" stroke="#5C3317" strokeWidth="4" fill="none" />
        </>
      ) : (
        <path d="M30 28 Q35 13 50 16 Q65 13 70 28 Q71 20 64 17 Q55 8 45 10 Q35 8 29 17 Z" fill="#3B2314" />
      )}
      <ellipse cx="42" cy="38" rx="3" ry="3.5" fill="#2d1810" />
      <ellipse cx="58" cy="38" rx="3" ry="3.5" fill="#2d1810" />
      <circle cx="43" cy="37" r="1" fill="white" />
      <circle cx="59" cy="37" r="1" fill="white" />
      <path d="M44 49 Q50 53 56 49" stroke="#c0392b" strokeWidth="2" fill="none" strokeLinecap="round" />
      <rect x="38" y="28" width="24" height="2.5" rx="1.2" fill="#059669" opacity="0.8" />
      <path d="M30 65 Q50 58 70 65 L74 88 Q50 83 26 88 Z" fill="#059669" />
      <text x="50" y="80" textAnchor="middle" fill="white" fontSize="11" fontWeight="bold" fontFamily="Arial">{teacher.full_name?.charAt(0) || ''}</text>
    </svg>
  );
};

const ParentAvatar = ({ parent, size = 'md' }) => {
  const dims = size === 'lg' ? 56 : size === 'sm' ? 32 : 44;
  const rel = parent.relationship?.toLowerCase();
  const isMother = rel === 'mother' || rel === 'أم';
  return (
    <svg width={dims} height={dims} viewBox="0 0 100 100" className="shrink-0">
      <defs>
        <linearGradient id="parentBg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#f59e0b" />
          <stop offset="100%" stopColor="#ea580c" />
        </linearGradient>
      </defs>
      <circle cx="50" cy="50" r="48" fill="url(#parentBg)" />
      <ellipse cx="50" cy="40" rx="18" ry="20" fill="#FDDCB5" />
      {isMother ? (
        <>
          <path d="M28 32 Q32 10 50 14 Q68 10 72 32 Q72 25 65 18 Q55 6 45 8 Q35 6 28 18 Q25 25 28 32 Z" fill="#5C3317" />
          <path d="M28 32 Q26 48 30 55" stroke="#5C3317" strokeWidth="4" fill="none" />
          <path d="M72 32 Q74 48 70 55" stroke="#5C3317" strokeWidth="4" fill="none" />
        </>
      ) : (
        <>
          <path d="M30 28 Q35 13 50 16 Q65 13 70 28 Q71 20 64 17 Q55 8 45 10 Q35 8 29 17 Z" fill="#3B2314" />
          <rect x="38" y="52" width="24" height="3" rx="1.5" fill="#8B6914" opacity="0.6" />
        </>
      )}
      <ellipse cx="42" cy="38" rx="3" ry="3.5" fill="#2d1810" />
      <ellipse cx="58" cy="38" rx="3" ry="3.5" fill="#2d1810" />
      <circle cx="43" cy="37" r="1" fill="white" />
      <circle cx="59" cy="37" r="1" fill="white" />
      <path d="M44 49 Q50 53 56 49" stroke="#c0392b" strokeWidth="2" fill="none" strokeLinecap="round" />
      <path d="M30 65 Q50 58 70 65 L74 88 Q50 83 26 88 Z" fill="#f59e0b" />
      <text x="50" y="80" textAnchor="middle" fill="white" fontSize="11" fontWeight="bold" fontFamily="Arial">{parent.full_name?.charAt(0) || ''}</text>
    </svg>
  );
};

const StudentCard = ({ student, isRTL, onEdit, onDelete, onView, onAction, viewMode = 'grid' }) => {
  const { t } = useTranslation();
  const tc = THEME_COLORS.student;
  if (viewMode === 'list') {
    return (
      <Card className={`group hover:shadow-md transition-all duration-200 border-border/50 ${tc.hoverBorder} cursor-pointer overflow-hidden`}
        onClick={() => onView(student)}>
        <div className={`h-0.5 ${tc.bar}`} />
        <CardContent className="p-3 flex items-center gap-3">
          <StudentAvatar student={student} size="sm" />
          <div className="flex-1 min-w-0 flex items-center gap-4">
            <h3 className="font-semibold text-sm truncate w-[140px]">{student.full_name}</h3>
            <span className="text-xs text-muted-foreground truncate hidden sm:inline">{student.grade || '-'} • {student.section || student.class_name || '-'}</span>
            <span className="text-[10px] text-muted-foreground font-mono hidden md:inline">{student.student_number || student.id?.slice(0, 8)}</span>
          </div>
          <Badge variant={student.is_active !== false ? 'default' : 'destructive'}
            className={`text-[10px] h-5 rounded-full border-0 ${student.is_active !== false ? tc.badge : ''}`}>
            <span className={`w-1.5 h-1.5 rounded-full me-1 ${student.is_active !== false ? tc.badgeDot : 'bg-red-500'}`} />
            {student.is_active !== false ? (t('active')) : (t('suspended'))}
          </Badge>
          <DropdownMenu>
            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
              <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0"><MoreHorizontal className="h-4 w-4" /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48" onClick={(e) => e.stopPropagation()}>
              <DropdownMenuItem onClick={() => onView(student)}><Eye className="h-3.5 w-3.5 me-2" />{t('viewProfile2')}</DropdownMenuItem>
              <DropdownMenuItem onClick={() => onEdit(student)}><Edit className="h-3.5 w-3.5 me-2" />{t('editInfo')}</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => onAction(student, 'reset-password')}><Key className="h-3.5 w-3.5 me-2" />{t('resetPassword')}</DropdownMenuItem>
              <DropdownMenuItem onClick={() => onDelete(student)} className="text-red-600"><Trash2 className="h-3.5 w-3.5 me-2" />{t('delete')}</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={`group hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 border-border/50 ${tc.hoverBorder} h-full cursor-pointer overflow-hidden`}
      onClick={() => onView(student)}>
      <div className={`h-1.5 ${tc.bar}`} />
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <StudentAvatar student={student} />
            <div className="min-w-0">
              <h3 className="font-semibold text-sm truncate max-w-[140px]">{student.full_name}</h3>
              <p className="text-[10px] text-muted-foreground font-mono">{student.student_number || student.id?.slice(0, 8)}</p>
            </div>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
              <Button variant="ghost" size="icon" className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity"><MoreHorizontal className="h-4 w-4" /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48" onClick={(e) => e.stopPropagation()}>
              <DropdownMenuItem onClick={() => onView(student)}><Eye className="h-3.5 w-3.5 me-2" />{t('viewProfile2')}</DropdownMenuItem>
              <DropdownMenuItem onClick={() => onEdit(student)}><Edit className="h-3.5 w-3.5 me-2" />{t('editInfo')}</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => onAction(student, 'reset-password')}><Key className="h-3.5 w-3.5 me-2" />{t('resetPassword')}</DropdownMenuItem>
              <DropdownMenuItem onClick={() => onAction(student, student.is_active !== false ? 'suspend' : 'activate')}>
                {student.is_active !== false ? <UserX className="h-3.5 w-3.5 me-2" /> : <UserCheck className="h-3.5 w-3.5 me-2" />}
                {student.is_active !== false ? (t('suspendAccount')) : (t('activateAccount'))}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => onDelete(student)} className="text-red-600"><Trash2 className="h-3.5 w-3.5 me-2" />{t('delete')}</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <div className="space-y-1.5 text-xs mb-3">
          <div className="flex items-center gap-2 text-muted-foreground">
            <BookOpen className="h-3 w-3 shrink-0" />
            <span className="truncate">{student.grade || '-'}</span>
            <span className="text-muted-foreground/30 mx-0.5">•</span>
            <span className="truncate">{student.section || student.class_name || '-'}</span>
          </div>
          {student.education_level && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <GraduationCap className="h-3 w-3 shrink-0" />
              <span className="truncate">{student.education_level}</span>
            </div>
          )}
        </div>
        <div className="flex items-center justify-between pt-2.5 border-t border-border/40">
          <Badge variant={student.is_active !== false ? 'default' : 'destructive'}
            className={`text-[10px] h-5 rounded-full border-0 ${student.is_active !== false ? tc.badge : ''}`}>
            <span className={`w-1.5 h-1.5 rounded-full me-1 ${student.is_active !== false ? tc.badgeDot : 'bg-red-500'}`} />
            {student.is_active !== false ? (t('active')) : (t('suspended'))}
          </Badge>
          <ChevronRight className={`h-3.5 w-3.5 text-muted-foreground/30 group-hover:${tc.accent} group-hover:translate-x-0.5 transition-all`} />
        </div>
      </CardContent>
    </Card>
  );
};

const TeacherCard = ({ teacher, isRTL, onEdit, onDelete, onView, onAction, viewMode = 'grid' }) => {
  const { t } = useTranslation();
  const tc = THEME_COLORS.teacher;
  if (viewMode === 'list') {
    return (
      <Card className={`group hover:shadow-md transition-all duration-200 border-border/50 ${tc.hoverBorder} cursor-pointer overflow-hidden`}
        onClick={() => onView(teacher)}>
        <div className={`h-0.5 ${tc.bar}`} />
        <CardContent className="p-3 flex items-center gap-3">
          <TeacherAvatar teacher={teacher} size="sm" />
          <div className="flex-1 min-w-0 flex items-center gap-4">
            <h3 className="font-semibold text-sm truncate w-[140px]">{teacher.full_name}</h3>
            <span className="text-xs text-muted-foreground truncate hidden sm:inline">{teacher.specialization || (t('teacher'))}</span>
            <span className="text-xs text-muted-foreground hidden md:inline">{teacher.weekly_periods || teacher.sessions_count || '-'} {t('sessionsPerWeek')}</span>
          </div>
          <Badge className={`text-[10px] h-5 rounded-full border-0 ${teacher.is_active !== false ? tc.badge : 'bg-red-100 text-red-700'}`}>
            <span className={`w-1.5 h-1.5 rounded-full me-1 ${teacher.is_active !== false ? tc.badgeDot : 'bg-red-500'}`} />
            {teacher.is_active !== false ? (t('active')) : (t('suspended'))}
          </Badge>
          <DropdownMenu>
            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
              <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0"><MoreHorizontal className="h-4 w-4" /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48" onClick={(e) => e.stopPropagation()}>
              <DropdownMenuItem onClick={() => onView(teacher)}><Eye className="h-3.5 w-3.5 me-2" />{t('viewDetails')}</DropdownMenuItem>
              <DropdownMenuItem onClick={() => onEdit(teacher)}><Edit className="h-3.5 w-3.5 me-2" />{t('editInfo')}</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => onDelete(teacher)} className="text-red-600"><Trash2 className="h-3.5 w-3.5 me-2" />{t('delete')}</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={`group hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 border-border/50 ${tc.hoverBorder} h-full cursor-pointer overflow-hidden`}
      onClick={() => onView(teacher)}>
      <div className={`h-1.5 ${tc.bar}`} />
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <TeacherAvatar teacher={teacher} />
            <div className="min-w-0">
              <h3 className="font-semibold text-sm truncate max-w-[140px]">{teacher.full_name}</h3>
              <p className="text-[10px] text-muted-foreground truncate">{teacher.specialization || (t('teacher'))}</p>
            </div>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
              <Button variant="ghost" size="icon" className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity"><MoreHorizontal className="h-4 w-4" /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48" onClick={(e) => e.stopPropagation()}>
              <DropdownMenuItem onClick={() => onView(teacher)}><Eye className="h-3.5 w-3.5 me-2" />{t('viewDetails')}</DropdownMenuItem>
              <DropdownMenuItem onClick={() => onEdit(teacher)}><Edit className="h-3.5 w-3.5 me-2" />{t('editInfo')}</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => onAction(teacher, 'reset-password')}><Key className="h-3.5 w-3.5 me-2" />{t('resetPassword')}</DropdownMenuItem>
              <DropdownMenuItem onClick={() => onAction(teacher, teacher.is_active !== false ? 'suspend' : 'activate')}>
                {teacher.is_active !== false ? <UserX className="h-3.5 w-3.5 me-2" /> : <UserCheck className="h-3.5 w-3.5 me-2" />}
                {teacher.is_active !== false ? (t('suspendAccount')) : (t('activateAccount'))}
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => onDelete(teacher)} className="text-red-600"><Trash2 className="h-3.5 w-3.5 me-2" />{t('delete')}</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <div className="space-y-1.5 text-xs mb-3">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Award className="h-3 w-3 shrink-0" />
            <span className="truncate">{teacher.rank || (t('teacher'))}</span>
            {teacher.years_of_experience > 0 && (
              <Badge variant="outline" className="text-[9px] h-4 px-1.5 border-muted-foreground/20">{teacher.years_of_experience} {t('yrs')}</Badge>
            )}
          </div>
          <div className="flex items-center gap-2 text-muted-foreground">
            <Clock className="h-3 w-3 shrink-0" />
            <span>{teacher.weekly_periods || teacher.sessions_count || '-'} {t('sessionsPerWeek')}</span>
          </div>
        </div>
        <div className="flex items-center justify-between pt-2.5 border-t border-border/40">
          <Badge className={`text-[10px] h-5 rounded-full border-0 ${teacher.is_active !== false ? tc.badge : 'bg-red-100 text-red-700'}`}>
            <span className={`w-1.5 h-1.5 rounded-full me-1 ${teacher.is_active !== false ? tc.badgeDot : 'bg-red-500'}`} />
            {teacher.is_active !== false ? (t('active')) : (t('suspended'))}
          </Badge>
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/30 group-hover:text-emerald-500 group-hover:translate-x-0.5 transition-all" />
        </div>
      </CardContent>
    </Card>
  );
};

const ParentCard = ({ parent, isRTL, onView, onAction, onDelete, viewMode = 'grid' }) => {
  const { t } = useTranslation();
  const tc = THEME_COLORS.parent;
  if (viewMode === 'list') {
    return (
      <Card className={`group hover:shadow-md transition-all duration-200 border-border/50 ${tc.hoverBorder} cursor-pointer overflow-hidden`}
        onClick={() => onView(parent)}>
        <div className={`h-0.5 ${tc.bar}`} />
        <CardContent className="p-3 flex items-center gap-3">
          <ParentAvatar parent={parent} size="sm" />
          <div className="flex-1 min-w-0 flex items-center gap-4">
            <h3 className="font-semibold text-sm truncate w-[140px]">{parent.full_name}</h3>
            <span className="text-xs text-muted-foreground truncate hidden sm:inline">{parent.relationship || (t('parentRole'))}</span>
            <span className="text-xs text-muted-foreground hidden md:inline">{parent.children_count || 0} {t('children')}</span>
          </div>
          <Badge className={`text-[10px] h-5 rounded-full border-0 ${tc.badge}`}>
            <Heart className="h-2.5 w-2.5 me-1" />
            {parent.children_count || 0}
          </Badge>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={`group hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 border-border/50 ${tc.hoverBorder} h-full cursor-pointer overflow-hidden`}
      onClick={() => onView(parent)}>
      <div className={`h-1.5 ${tc.bar}`} />
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <ParentAvatar parent={parent} />
            <div className="min-w-0">
              <h3 className="font-semibold text-sm truncate max-w-[140px]">{parent.full_name}</h3>
              <p className="text-[10px] text-muted-foreground">{parent.relationship || (t('parentRole'))}</p>
            </div>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
              <Button variant="ghost" size="icon" className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity"><MoreHorizontal className="h-4 w-4" /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48" onClick={(e) => e.stopPropagation()}>
              <DropdownMenuItem onClick={() => onView(parent)}><Eye className="h-3.5 w-3.5 me-2" />{t('viewDetails')}</DropdownMenuItem>
              {parent.user_id && (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => onAction(parent, 'reset-password')}><Key className="h-3.5 w-3.5 me-2" />{t('resetPassword')}</DropdownMenuItem>
                </>
              )}
              {onDelete && (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => onDelete(parent)} className="text-red-600 focus:text-red-700 focus:bg-red-50">
                    <Trash2 className="h-3.5 w-3.5 me-2" />{t('deletePermanently')}
                  </DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <div className="space-y-1.5 text-xs mb-3">
          {parent.phone && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Phone className="h-3 w-3 shrink-0" />
              <span className="truncate" dir="ltr">{parent.phone}</span>
            </div>
          )}
          <div className="flex items-center gap-2 text-muted-foreground">
            <Heart className="h-3 w-3 shrink-0" />
            <span>{parent.children_count || 0} {t('registeredChildren')}</span>
          </div>
          {parent.children?.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1">
              {parent.children.slice(0, 3).map((child, i) => (
                <Badge key={i} variant="outline" className="text-[9px] h-4 px-1.5 border-amber-200 text-amber-700 dark:border-amber-700 dark:text-amber-400">
                  {child.name?.split(' ')[0]}
                </Badge>
              ))}
              {parent.children.length > 3 && (
                <Badge variant="outline" className="text-[9px] h-4 px-1.5">+{parent.children.length - 3}</Badge>
              )}
            </div>
          )}
        </div>
        <div className="flex items-center justify-between pt-2.5 border-t border-border/40">
          <Badge className={`text-[10px] h-5 rounded-full border-0 ${tc.badge}`}>
            <Shield className="h-2.5 w-2.5 me-1" />
            {parent.relationship || (t('parentRole'))}
          </Badge>
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/30 group-hover:text-amber-500 group-hover:translate-x-0.5 transition-all" />
        </div>
      </CardContent>
    </Card>
  );
};

const ClassCard = ({ classItem, isRTL, onEdit, onDelete, onView, onReactivate, viewMode = 'grid' }) => {
  const { t } = useTranslation();
  const pct = Math.min(100, ((classItem.student_count || 0) / (classItem.capacity || 30)) * 100);
  const tc = THEME_COLORS.class;

  const isInactive = classItem.is_active === false;
  if (viewMode === 'list') {
    return (
      <Card className={`group hover:shadow-md transition-all duration-200 border-border/50 ${tc.hoverBorder} cursor-pointer overflow-hidden ${isInactive ? 'opacity-60' : ''}`}
        onClick={() => onView(classItem)}>
        <div className={`h-0.5 ${tc.bar}`} />
        <CardContent className="p-3 flex items-center gap-3">
          <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${tc.gradient} flex items-center justify-center shrink-0`}>
            <Building2 className="h-4 w-4 text-white" />
          </div>
          <div className="flex-1 min-w-0 flex items-center gap-4">
            <h3 className="font-semibold text-sm truncate w-[140px]">{classItem.name}</h3>
            <span className="text-xs text-muted-foreground truncate hidden sm:inline">{classItem.grade} - {classItem.section}</span>
            <span className="text-xs text-muted-foreground hidden md:inline">{classItem.student_count || 0}/{classItem.capacity || 30}</span>
            {isInactive && (
              <Badge variant="outline" className="text-[10px] h-5 rounded-full border-red-300 text-red-700 bg-red-50">
                {t('inactive')}
              </Badge>
            )}
          </div>
          <div className="w-20 hidden sm:block">
            <div className="w-full bg-muted rounded-full h-1.5">
              <div className={`h-1.5 rounded-full ${pct > 90 ? 'bg-red-500' : pct > 70 ? 'bg-amber-500' : 'bg-emerald-500'}`} style={{ width: `${pct}%` }} />
            </div>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
              <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0"><MoreHorizontal className="h-4 w-4" /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-44" onClick={(e) => e.stopPropagation()}>
              <DropdownMenuItem onClick={() => onView(classItem)}><Eye className="h-3.5 w-3.5 me-2" />{t('viewDetails')}</DropdownMenuItem>
              <DropdownMenuItem onClick={() => onEdit(classItem)}><Edit className="h-3.5 w-3.5 me-2" />{t('edit')}</DropdownMenuItem>
              {isInactive && onReactivate && (
                <DropdownMenuItem onClick={() => onReactivate(classItem)} data-testid={`reactivate-class-${classItem.id}`}>
                  <RotateCcw className="h-3.5 w-3.5 me-2" />{t('reactivate')}
                </DropdownMenuItem>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => onDelete(classItem)} className="text-red-600"><Trash2 className="h-3.5 w-3.5 me-2" />{t('delete')}</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={`group hover:shadow-lg transition-all duration-200 border-border/50 ${tc.hoverBorder} h-full cursor-pointer ${isInactive ? 'opacity-60' : ''}`}
      onClick={() => onView(classItem)}>
      <div className={`h-1.5 rounded-t-lg ${tc.bar}`} />
      <CardContent className="p-4">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${tc.gradient} flex items-center justify-center shadow-sm`}>
              <Building2 className="h-5 w-5 text-white" />
            </div>
            <div className="min-w-0">
              <h3 className="font-semibold text-sm truncate">{classItem.name}</h3>
              <p className="text-[11px] text-muted-foreground">{classItem.grade} - {classItem.section}</p>
              {isInactive && (
                <Badge variant="outline" className="mt-1 text-[10px] h-5 rounded-full border-red-300 text-red-700 bg-red-50">
                  {t('inactive')}
                </Badge>
              )}
            </div>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
              <Button variant="ghost" size="icon" className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity"><MoreHorizontal className="h-4 w-4" /></Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-44" onClick={(e) => e.stopPropagation()}>
              <DropdownMenuItem onClick={() => onView(classItem)}><Eye className="h-3.5 w-3.5 me-2" />{t('viewDetails')}</DropdownMenuItem>
              <DropdownMenuItem onClick={() => onEdit(classItem)}><Edit className="h-3.5 w-3.5 me-2" />{t('edit')}</DropdownMenuItem>
              {isInactive && onReactivate && (
                <DropdownMenuItem onClick={() => onReactivate(classItem)} data-testid={`reactivate-class-grid-${classItem.id}`}>
                  <RotateCcw className="h-3.5 w-3.5 me-2" />{t('reactivate')}
                </DropdownMenuItem>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => onDelete(classItem)} className="text-red-600"><Trash2 className="h-3.5 w-3.5 me-2" />{t('delete')}</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
          <Users className="h-3 w-3 shrink-0" />
          <span>{classItem.student_count || 0} / {classItem.capacity || 30} {t('studentsLower')}</span>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground mb-3">
          <UserCheck className="h-3 w-3 shrink-0" />
          <span className="truncate">{classItem.homeroom_teacher_name || (t('notAssigned'))}</span>
        </div>
        <div className="mb-2">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] font-medium text-muted-foreground">{Math.round(pct)}% {t('full')}</span>
            <span className={`text-[10px] font-bold ${pct > 90 ? 'text-red-500' : pct > 70 ? 'text-amber-500' : 'text-emerald-500'}`}>
              {classItem.student_count || 0}/{classItem.capacity || 30}
            </span>
          </div>
          <div className="w-full bg-muted rounded-full h-2">
            <div className={`h-2 rounded-full transition-all duration-500 ${pct > 90 ? 'bg-gradient-to-r from-red-400 to-red-500' : pct > 70 ? 'bg-gradient-to-r from-amber-400 to-orange-500' : 'bg-gradient-to-r from-emerald-400 to-green-500'}`} style={{ width: `${pct}%` }} />
          </div>
        </div>
        <div className="flex items-center justify-end pt-1">
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/30 group-hover:text-purple-500 group-hover:translate-x-0.5 transition-all" />
        </div>
      </CardContent>
    </Card>
  );
};

const PermanentHakimWidget = ({ insights, isRTL, onAction, stats }) => {
  const { t } = useTranslation();
  const [panelOpen, setPanelOpen] = useState(false);
  const [currentBubble, setCurrentBubble] = useState(0);
  const hasInsights = insights && insights.length > 0 && insights.some(i => i.severity !== 'success');

  const bubbleMessages = useMemo(() => {
    const msgs = [];
    if (hasInsights) {
      const highCount = insights.filter(i => i.severity === 'high').length;
      if (highCount > 0) msgs.push(t('criticalAlertsMsg', { count: highCount }));
      insights.forEach(i => {
        if (i.severity === 'high' || i.severity === 'medium') msgs.push(i.message);
      });
    }
    if (!hasInsights || msgs.length === 0) {
      msgs.push(t('everythingLooksGreatWellDone'));
    }
    if (stats) {
      msgs.push(t('studentsTeachersStatusMsg', { students: stats.totalStudents, teachers: stats.totalTeachers }));
    }
    return msgs;
  }, [insights, hasInsights, isRTL, stats]);

  useEffect(() => {
    if (bubbleMessages.length <= 1) return;
    const interval = setInterval(() => {
      setCurrentBubble(prev => (prev + 1) % bubbleMessages.length);
    }, 6000);
    return () => clearInterval(interval);
  }, [bubbleMessages.length]);

  const severityIcon = (sev) => {
    if (sev === 'high') return <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0 text-red-500" />;
    if (sev === 'medium') return <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0 text-amber-500" />;
    return <Sparkles className="h-3.5 w-3.5 mt-0.5 shrink-0 text-violet-400" />;
  };

  return (
    <div className="fixed bottom-6 end-6 z-40 flex flex-col items-end gap-3" style={{ maxWidth: '400px' }}>
      {panelOpen && hasInsights && (
        <div className="w-[360px] max-h-[350px] overflow-y-auto bg-white dark:bg-gray-900 rounded-2xl shadow-2xl border border-violet-200 dark:border-violet-800 animate-in slide-in-from-bottom-4 fade-in duration-300">
          <div className="sticky top-0 bg-gradient-to-r from-violet-600 to-purple-600 text-white px-4 py-3 rounded-t-2xl flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center overflow-hidden">
                <img src="/hakim-poses/analyzing-data.png" alt="" className="hakim-img w-10 h-10 object-contain" onError={(e) => { e.target.style.display = 'none'; }} />
              </div>
              <div>
                <h4 className="font-bold text-sm">{t('hakimAnalysis')}</h4>
                <p className="text-[10px] text-white/70">{t('insightsNeedReview', { count: insights.length })}</p>
              </div>
            </div>
            <Button variant="ghost" size="icon" className="h-6 w-6 text-white/70 hover:text-white hover:bg-white/10" onClick={() => setPanelOpen(false)}>
              <X className="h-4 w-4" />
            </Button>
          </div>
          <div className="p-3 space-y-2">
            {insights.map((insight, i) => (
              <div key={i} className={`flex items-start justify-between gap-2 p-3 rounded-xl border transition-all hover:shadow-sm ${
                insight.severity === 'high' ? 'bg-red-50/80 dark:bg-red-950/20 border-red-200 dark:border-red-800' :
                insight.severity === 'medium' ? 'bg-amber-50/80 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800' :
                'bg-violet-50/80 dark:bg-violet-950/20 border-violet-100 dark:border-violet-800'
              }`}>
                <div className="flex items-start gap-2 flex-1 min-w-0">
                  {severityIcon(insight.severity)}
                  <div className="flex-1 min-w-0">
                    <span className="text-xs font-medium block">{insight.message}</span>
                    {insight.suggestion && (
                      <span className="text-[10px] text-muted-foreground mt-0.5 block">{insight.suggestion}</span>
                    )}
                  </div>
                </div>
                {insight.action && (
                  <Button size="sm" variant="outline"
                    className={`shrink-0 h-7 text-[10px] rounded-lg ${
                      insight.severity === 'high' ? 'border-red-300 text-red-700 hover:bg-red-100 hover:text-red-700' :
                      insight.severity === 'medium' ? 'border-amber-300 text-amber-700 hover:bg-amber-100 hover:text-amber-700' :
                      'border-violet-300 text-violet-700 hover:bg-violet-100 hover:text-violet-700'
                    }`}
                    onClick={() => { onAction(insight.action, insight.data); setPanelOpen(false); }}>
                    <ArrowRight className="h-3 w-3 me-1" />
                    {t('view2')}
                  </Button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {!panelOpen && (
        <div className="animate-in fade-in slide-in-from-bottom-2 duration-500 max-w-[280px]">
          <div className="relative bg-white dark:bg-gray-800 rounded-2xl rounded-br-sm shadow-lg border border-violet-200 dark:border-violet-700 px-4 py-2.5">
            <p className="text-xs text-gray-700 dark:text-gray-300 leading-relaxed font-tajawal" key={currentBubble}>
              <span className="animate-in fade-in duration-500">{bubbleMessages[currentBubble]}</span>
            </p>
            {hasInsights && (
              <button onClick={() => setPanelOpen(true)} className="text-[10px] text-violet-600 dark:text-violet-400 font-semibold mt-1 hover:underline block">
                {t('viewInsightsArrow', { count: insights.length })}
              </button>
            )}
          </div>
        </div>
      )}

      <div className="relative group cursor-pointer" onClick={() => setPanelOpen(!panelOpen)}
        title={t('hakimSmartAssistant')}>
        <div className={`w-[72px] h-[72px] rounded-full overflow-hidden bg-white shadow-xl ring-3 ${hasInsights ? 'ring-violet-400 animate-[hakim-ring-pulse_2s_ease-in-out_infinite]' : 'ring-violet-200'} flex items-center justify-center transition-all duration-300 group-hover:scale-110 group-hover:shadow-2xl`}>
          <img src="/hakim-poses/detecting-patterns.png" alt="Hakim" className="hakim-img w-20 h-20 object-contain animate-[hakim-alive_4s_ease-in-out_infinite]"
            onError={(e) => {
              e.target.style.display = 'none';
              const parent = e.target.parentElement;
              if (parent && !parent.querySelector('.hakim-fallback-emoji')) {
                const span = document.createElement('span');
                span.className = 'hakim-fallback-emoji text-3xl';
                span.textContent = '🧠';
                parent.appendChild(span);
              }
            }} />
        </div>
        {hasInsights && (
          <span className="absolute -top-1 -end-1 w-6 h-6 rounded-full bg-red-500 text-white text-[11px] font-bold flex items-center justify-center shadow-md animate-[hakim-badge_2s_ease-in-out_infinite]">
            {insights.length}
          </span>
        )}
        <span className="absolute -bottom-0.5 -end-0.5 w-4.5 h-4.5 rounded-full bg-emerald-400 border-2 border-white animate-[hakim-online_1.5s_ease-in-out_infinite]" />
      </div>

      <style>{`
        @keyframes hakim-alive {
          0%, 100% { transform: translateY(0px) scale(1); }
          15% { transform: translateY(-4px) scale(1.03); }
          30% { transform: translateY(0px) scale(1); }
          45% { transform: translateY(-2px) scale(1.01) rotate(2deg); }
          60% { transform: translateY(1px) scale(1) rotate(0deg); }
          80% { transform: translateY(-1px) scale(1.02); }
        }
        @keyframes hakim-ring-pulse {
          0%, 100% { box-shadow: 0 0 0 0 rgba(139, 92, 246, 0.4); }
          50% { box-shadow: 0 0 0 8px rgba(139, 92, 246, 0); }
        }
        @keyframes hakim-badge {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.15); }
        }
        @keyframes hakim-online {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.6; transform: scale(0.85); }
        }
      `}</style>
    </div>
  );
};

const AddPickerDialog = ({ open, onClose, isRTL, onSelect }) => {
  const { t } = useTranslation();
  return (
  <Dialog open={open} onOpenChange={(val) => { if (!val) onClose(); }}>
    <DialogContent className="sm:max-w-[480px]">
      <DialogHeader>
        <DialogTitle className="text-center text-lg">{t('addNewItem')}</DialogTitle>
        <DialogDescription className="text-center">{t('chooseWhatYouWantToAdd')}</DialogDescription>
      </DialogHeader>
      <div className="grid grid-cols-3 gap-4 py-4">
        <button onClick={() => onSelect('student')}
          className="group p-5 rounded-xl border-2 border-border hover:border-[#1B2A4A] hover:bg-blue-50/50 dark:hover:bg-blue-950/10 transition-all text-center">
          <div className={`w-14 h-14 mx-auto mb-3 rounded-full bg-gradient-to-br ${THEME_COLORS.student.gradient} flex items-center justify-center group-hover:scale-110 transition-transform shadow-md`}>
            <GraduationCap className="h-7 w-7 text-white" />
          </div>
          <p className="font-semibold text-sm">{t('student')}</p>
          <p className="text-[11px] text-muted-foreground mt-1">{t('addNewStudent')}</p>
        </button>
        <button onClick={() => onSelect('teacher')}
          className="group p-5 rounded-xl border-2 border-border hover:border-emerald-500 hover:bg-emerald-50/50 dark:hover:bg-emerald-950/10 transition-all text-center">
          <div className={`w-14 h-14 mx-auto mb-3 rounded-full bg-gradient-to-br ${THEME_COLORS.teacher.gradient} flex items-center justify-center group-hover:scale-110 transition-transform shadow-md`}>
            <UserPlus className="h-7 w-7 text-white" />
          </div>
          <p className="font-semibold text-sm">{t('teacher')}</p>
          <p className="text-[11px] text-muted-foreground mt-1">{t('addNewTeacher')}</p>
        </button>
        <button onClick={() => onSelect('class')}
          className="group p-5 rounded-xl border-2 border-border hover:border-purple-500 hover:bg-purple-50/50 dark:hover:bg-purple-950/10 transition-all text-center">
          <div className={`w-14 h-14 mx-auto mb-3 rounded-xl bg-gradient-to-br ${THEME_COLORS.class.gradient} flex items-center justify-center group-hover:scale-110 transition-transform shadow-md`}>
            <School className="h-7 w-7 text-white" />
          </div>
          <p className="font-semibold text-sm">{t('classLabel')}</p>
          <p className="text-[11px] text-muted-foreground mt-1">{t('createNewClass')}</p>
        </button>
      </div>
    </DialogContent>
  </Dialog>
  );
};

export default function UsersClassesManagement() {
  const { t } = useTranslation();
  const { user, api, schoolContext, isImpersonating } = useAuth();
  const { isRTL, toggleTheme, toggleLanguage, isDark } = useTheme();
  const { nassaqConfirm, nassaqError, nassaqWarning, nassaqInfo } = useNassaqAlert();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState(searchParams.get('filter') || 'students');
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState('grid');
  const [sortBy, setSortBy] = useState('name_asc');

  const [students, setStudents] = useState([]);
  const [teachers, setTeachers] = useState([]);
  const [parents, setParents] = useState([]);
  const [classes, setClasses] = useState([]);
  const [grades, setGrades] = useState([]);

  const [showAddPicker, setShowAddPicker] = useState(false);
  const [showStudentWizard, setShowStudentWizard] = useState(false);
  const [showTeacherWizard, setShowTeacherWizard] = useState(false);
  const [showClassWizard, setShowClassWizard] = useState(false);

  const [noorImportCount, setNoorImportCount] = useState(null);
  const [importType, setImportType] = useState('students');
  const [selectedFile, setSelectedFile] = useState(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [exportType, setExportType] = useState('students');
  const [exportFormat, setExportFormat] = useState('xlsx');
  const [exporting, setExporting] = useState(false);

  const [viewDialogOpen, setViewDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState(null);
  const [selectedItemType, setSelectedItemType] = useState(null);
  const [editLoading, setEditLoading] = useState(false);
  const [editFormData, setEditFormData] = useState({});
  const [viewClassEditing, setViewClassEditing] = useState(false);
  const [viewClassForm, setViewClassForm] = useState({});
  const [viewClassSaving, setViewClassSaving] = useState(false);

  const [teacherProfileOpen, setTeacherProfileOpen] = useState(false);
  const [selectedTeacher, setSelectedTeacher] = useState(null);
  const [parentProfileOpen, setParentProfileOpen] = useState(false);
  const [selectedParent, setSelectedParent] = useState(null);
  const [activeFilter, setActiveFilter] = useState(null);
  const [showInactiveClasses, setShowInactiveClasses] = useState(false);

  const studentsNoClass = useMemo(() => students.filter(s => !s.class_id && !s.class_name), [students]);
  const teachersNoSubject = useMemo(() => teachers.filter(t => !t.specialization && (!t.subject_ids || t.subject_ids.length === 0)), [teachers]);
  const accountsNoEmail = useMemo(() => [...students, ...teachers].filter(u => !u.email), [students, teachers]);
  const studentsNoParent = useMemo(() => {
    const parentStudentIds = new Set(parents.flatMap(p => p.student_ids || []));
    return students.filter(s => !s.parent_id && !parentStudentIds.has(s.id));
  }, [students, parents]);
  const suspendedStudents = useMemo(() => students.filter(s => s.is_active === false), [students]);
  const overCapClasses = useMemo(() => classes.filter(c => (c.student_count || 0) > (c.capacity || 30)), [classes]);

  const stats = useMemo(() => ({
    totalStudents: students.length,
    totalTeachers: teachers.length,
    totalParents: parents.length,
    totalClasses: classes.filter(c => c.is_active !== false).length,
    activeStudents: students.filter(s => s.is_active !== false).length,
    activeTeachers: teachers.filter(t => t.is_active !== false).length,
  }), [students, teachers, parents, classes]);

  const hakimInsights = useMemo(() => {
    const ins = [];
    if (studentsNoParent.length > 0) {
      ins.push({
        message: t('studentsNoParentMsg', { count: studentsNoParent.length }),
        suggestion: t('addParentInfoToEnableFamilyCommunication'),
        severity: 'high', action: 'show_students_no_parent', data: studentsNoParent
      });
    }
    if (studentsNoClass.length > 0) {
      ins.push({
        message: t('studentsNoClassMsg', { count: studentsNoClass.length }),
        suggestion: t('assignClassesToEnsureScheduleWorksProperly'),
        severity: 'high', action: 'show_students_no_class', data: studentsNoClass
      });
    }
    if (teachersNoSubject.length > 0) {
      ins.push({
        message: t('teachersNoSubjectMsg', { count: teachersNoSubject.length }),
        suggestion: t('assignSubjectsToEnableTimetableGeneration'),
        severity: 'medium', action: 'show_teachers_no_subject', data: teachersNoSubject
      });
    }
    if (accountsNoEmail.length > 0) {
      ins.push({
        message: t('accountsNoEmailMsg', { count: accountsNoEmail.length }),
        suggestion: t('emailIsNeededForLoginAndNotifications'),
        severity: 'low', action: 'show_no_email', data: accountsNoEmail
      });
    }
    if (suspendedStudents.length > 0) {
      ins.push({
        message: t('suspendedStudentsMsg', { count: suspendedStudents.length }),
        suggestion: t('reviewSuspendedAccountsAndReactivateOrRemove'),
        severity: 'medium', action: 'show_suspended', data: suspendedStudents
      });
    }
    if (overCapClasses.length > 0) {
      ins.push({
        message: t('overCapClassesMsg', { count: overCapClasses.length }),
        suggestion: t('redistributeStudentsOrIncreaseClassCapacity'),
        severity: 'high', action: 'show_over_capacity', data: overCapClasses
      });
    }
    if (ins.length === 0) {
      ins.push({
        message: t('allDataIsCompleteAndOrganizedGreatJob'),
        severity: 'success'
      });
    }
    return ins;
  }, [studentsNoParent, studentsNoClass, teachersNoSubject, accountsNoEmail, suspendedStudents, overCapClasses, isRTL]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { fetchAllData(); }, [user, schoolContext]);
  useEffect(() => { fetchAllData(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [showInactiveClasses]);
  useEffect(() => {
    if (activeTab && activeTab !== 'all') setSearchParams({ filter: activeTab });
    else setSearchParams({});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);
  useEffect(() => {
    const f = searchParams.get('filter');
    if (f && f !== activeTab) {
      setActiveTab(f);
      setActiveFilter(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const fetchAllData = async () => {
    setLoading(true);
    // Task #511: defensive reset so previously-loaded data from another
    // previewed school cannot momentarily render under a new (empty)
    // school while the in-flight directory requests resolve.
    setStudents([]);
    setTeachers([]);
    setClasses([]);
    setGrades([]);
    setParents([]);
    try {
      const headers = {};
      if (isImpersonating && schoolContext?.school_id) headers['X-School-Context'] = schoolContext.school_id;
      const endpoints = [
        { key: 'students', url: '/students' },
        { key: 'teachers', url: '/teachers' },
        { key: 'classes', url: '/classes', params: showInactiveClasses ? { include_inactive: true } : undefined },
        { key: 'grades', url: '/reference/grades' },
        { key: 'parents', url: '/parents' },
      ];
      const results = await Promise.allSettled(
        endpoints.map(e => api.get(e.url, { headers, ...(e.params ? { params: e.params } : {}) }))
      );
      const failed = [];
      const dataByKey = {};
      results.forEach((r, i) => {
        const key = endpoints[i].key;
        if (r.status === 'fulfilled') {
          dataByKey[key] = Array.isArray(r.value.data) ? r.value.data : [];
        } else {
          dataByKey[key] = [];
          failed.push(endpoints[i].url);
        }
      });
      setStudents(dataByKey.students);
      setTeachers(dataByKey.teachers);
      setClasses(dataByKey.classes);
      setGrades(dataByKey.grades);
      setParents(dataByKey.parents);
      if (failed.length === endpoints.length) {
        nassaqError(t('errorLoadingData'));
      } else if (failed.length > 0) {
        console.warn('Partial data load failure for endpoints:', failed);
      }
    } catch (error) {
      nassaqError(t('errorLoadingData'));
    } finally {
      setLoading(false);
    }
  };

  const applySorting = useCallback((list, type) => {
    const sorted = [...list];
    const [field, dir] = sortBy.split('_');
    const asc = dir === 'asc';
    sorted.sort((a, b) => {
      let valA, valB;
      if (field === 'name') {
        valA = (type === 'class' ? a.name : a.full_name) || '';
        valB = (type === 'class' ? b.name : b.full_name) || '';
        return asc ? valA.localeCompare(valB, 'ar') : valB.localeCompare(valA, 'ar');
      }
      if (field === 'date') {
        valA = a.created_at || a.createdAt || '';
        valB = b.created_at || b.createdAt || '';
        return asc ? valA.localeCompare(valB) : valB.localeCompare(valA);
      }
      if (field === 'email') {
        valA = a.email || '';
        valB = b.email || '';
        return asc ? valA.localeCompare(valB) : valB.localeCompare(valA);
      }
      if (field === 'number') {
        valA = a.student_number || '';
        valB = b.student_number || '';
        return asc ? valA.localeCompare(valB, undefined, { numeric: true }) : valB.localeCompare(valA, undefined, { numeric: true });
      }
      if (field === 'grade') {
        valA = a.grade_level || '';
        valB = b.grade_level || '';
        return asc ? valA.localeCompare(valB, 'ar') : valB.localeCompare(valA, 'ar');
      }
      if (field === 'capacity') {
        valA = a.student_count || 0;
        valB = b.student_count || 0;
        return asc ? valA - valB : valB - valA;
      }
      return 0;
    });
    return sorted;
  }, [sortBy]);

  const filteredStudents = useMemo(() => {
    let list = students;
    if (activeFilter === 'noClass') list = studentsNoClass;
    else if (activeFilter === 'noParent') list = studentsNoParent;
    else if (activeFilter === 'suspended') list = suspendedStudents;
    else if (activeFilter === 'noEmail') list = list.filter(s => !s.email);
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      list = list.filter(s => s.full_name?.toLowerCase().includes(q) || s.student_number?.toLowerCase().includes(q) || s.email?.toLowerCase().includes(q));
    }
    return applySorting(list, 'student');
  }, [students, searchQuery, activeFilter, studentsNoClass, studentsNoParent, suspendedStudents, applySorting]);

  const displayedStudents = filteredStudents;

  const filteredTeachers = useMemo(() => {
    let list = teachers;
    if (activeFilter === 'noSubject') list = teachersNoSubject;
    else if (activeFilter === 'noEmail') list = list.filter(t => !t.email);
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      list = list.filter(t => t.full_name?.toLowerCase().includes(q) || t.email?.toLowerCase().includes(q) || t.specialization?.toLowerCase().includes(q));
    }
    return applySorting(list, 'teacher');
  }, [teachers, searchQuery, activeFilter, teachersNoSubject, applySorting]);

  const filteredParents = useMemo(() => {
    let list = parents;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      list = list.filter(p => p.full_name?.toLowerCase().includes(q) || p.phone?.toLowerCase().includes(q) || p.email?.toLowerCase().includes(q));
    }
    return applySorting(list, 'parent');
  }, [parents, searchQuery, applySorting]);

  const filteredClasses = useMemo(() => {
    let list = showInactiveClasses ? classes : classes.filter(c => c.is_active !== false);
    if (activeFilter === 'overCapacity') list = list.filter(c => (c.student_count || 0) > (c.capacity || 30));
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      list = list.filter(c => c.name?.toLowerCase().includes(q));
    }
    return applySorting(list, 'class');
  }, [classes, searchQuery, activeFilter, applySorting, showInactiveClasses]);

  const handleReactivateClass = async (classItem) => {
    try {
      const headers = {};
      if (isImpersonating && schoolContext?.school_id) headers['X-School-Context'] = schoolContext.school_id;
      await api.put(`/classes/${classItem.id}`, { is_active: true }, { headers });
      toast.success(t('classReactivated'));
      setClasses(prev => prev.map(c => c.id === classItem.id ? { ...c, is_active: true } : c));
    } catch (error) {
      nassaqError(getApiErrorMessage(error) || (t('operationFailed')));
    }
  };

  const handleAddSelect = (type) => {
    setShowAddPicker(false);
    if (type === 'student') setShowStudentWizard(true);
    else if (type === 'teacher') setShowTeacherWizard(true);
    else if (type === 'class') setShowClassWizard(true);
  };

  const handleEdit = (item, type) => {
    setSelectedItem(item);
    setSelectedItemType(type);
    setEditFormData({ ...item });
    setEditDialogOpen(true);
  };

  const refetchClasses = async () => {
    try {
      const headers = {};
      if (isImpersonating && schoolContext?.school_id) headers['X-School-Context'] = schoolContext.school_id;
      const res = await api.get('/classes', { headers });
      if (Array.isArray(res.data)) setClasses(res.data);
    } catch (e) {
      // Preserve current (optimistic) state on transient failure so the
      // stat card and tab badge do not drift back to a stale count.
    }
  };

  // Build the dependency-aware confirmation body the backend's
  // requires_confirmation envelope warrants. The student line explicitly
  // states students are unassigned (NOT deleted) so the principal knows
  // their records survive.
  const buildClassDeleteMessage = (deps = {}) => {
    const lines = [];
    if (deps.teacher_assignments > 0) lines.push(`• ${t('classDeleteDepTeacherAssignments', { count: deps.teacher_assignments })}`);
    if (deps.class_subjects > 0) lines.push(`• ${t('classDeleteDepClassSubjects', { count: deps.class_subjects })}`);
    if (deps.timetable_sessions > 0) lines.push(`• ${t('classDeleteDepTimetableSessions', { count: deps.timetable_sessions })}`);
    let msg = '';
    if (lines.length > 0) msg += `${t('classDeleteLinkedIntro')}\n${lines.join('\n')}\n\n`;
    if (deps.students > 0) msg += `${t('classDeleteStudentsUnassignNote', { count: deps.students })}\n\n`;
    msg += t('classDeleteConfirmQuestion');
    return msg;
  };

  // Honest delete flow: a requires_confirmation envelope is NOT a deletion.
  // We only treat it as success once the backend confirms the class was
  // actually removed (data.success on a real delete or forced re-issue).
  const runClassDelete = async (classId, { onDeleted, setBusy } = {}) => {
    const headers = {};
    if (isImpersonating && schoolContext?.school_id) headers['X-School-Context'] = schoolContext.school_id;
    const forceDelete = async () => {
      try {
        const forced = await api.delete(`/classes/${classId}?force=true`, { headers });
        if (forced.data?.success) {
          await onDeleted?.(forced.data);
        } else {
          nassaqError(t('failedToDeleteClass'));
        }
      } catch (e) {
        nassaqError(getApiErrorMessage(e) || (t('failedToDeleteClass')));
      } finally {
        setBusy?.(false);
      }
    };
    setBusy?.(true);
    try {
      const res = await api.delete(`/classes/${classId}`, { headers });
      if (res.data?.requires_confirmation) {
        setBusy?.(false);
        nassaqConfirm(
          buildClassDeleteMessage(res.data.dependencies),
          () => { setBusy?.(true); return forceDelete(); },
          { title: t('confirmPermanentDelete'), confirmText: t('yesDeleteClass'), cancelText: t('cancel') }
        );
        return;
      }
      if (res.data?.success) {
        await onDeleted?.(res.data);
      } else {
        nassaqError(t('failedToDeleteClass'));
      }
      setBusy?.(false);
    } catch (e) {
      nassaqError(getApiErrorMessage(e) || (t('failedToDeleteClass')));
      setBusy?.(false);
    }
  };

  const handleDelete = (item, type) => {
    if (type === 'class') {
      // Class deletion is driven by the backend confirmation envelope so the
      // card is only removed after a real deletion (no optimistic success on
      // the requires_confirmation response).
      runClassDelete(item.id, {
        onDeleted: () => {
          toast.success(t('classDeletedSuccessfully'));
          // Optimistically remove so the totalClasses stat and tab badge
          // update without waiting for the network round-trip, then run a
          // targeted refetch that won't clobber the list on partial failure.
          setClasses(prev => prev.filter(c => c.id !== item.id));
          refetchClasses();
        },
      });
      return;
    }
    const typeLabels = { student: t('studentLower'), teacher: t('teacherLower'), parent: t('parentLower'), class: t('classLower') };
    const msg = t('confirmDeleteEntity', { label: typeLabels[type] });
    nassaqConfirm(msg, async () => {
      try {
        const endpoints = { student: `/students/${item.id}`, teacher: `/teachers/${item.id}`, parent: `/parents/${item.id}` };
        const ep = endpoints[type];
        const res = await api.delete(ep);
        const cleanup = res.data?.cleanup;
        let successMsg = t('deletedSuccessfully');
        if (cleanup) {
          const parts = [];
          Object.entries(cleanup).forEach(([key, val]) => {
            if (val > 0) parts.push(`${key}: ${val}`);
          });
          if (parts.length > 0) successMsg += ` (${parts.join(', ')})`;
        }
        toast.success(successMsg);
        fetchAllData();
      } catch (error) {
        let errMsg = t('deleteFailed');
        if (getApiErrorMessage(error)) {
          errMsg = typeof getApiErrorMessage(error) === 'string' ? getApiErrorMessage(error) : errMsg;
        }
        nassaqError(errMsg);
      }
    }, { title: t('confirmPermanentDelete'), confirmText: t('yesDeletePermanently'), cancelText: t('cancel') });
  };

  const handleView = (item, type) => {
    const prefix = user?.role === 'school_principal' ? '/principal' : '/admin';
    if (type === 'student') {
      const cls = classes.find(c => c.id === item.class_id);
      navigate(`${prefix}/students/${item.id}`, {
        state: {
          classId: item.class_id,
          className: cls?.name || item.class_name,
          fromPath: `${prefix}/users-management?filter=students`
        }
      });
    }
    else if (type === 'teacher') { setSelectedTeacher(item); setTeacherProfileOpen(true); }
    else if (type === 'parent') { setSelectedParent(item); setParentProfileOpen(true); }
    else if (type === 'class') {
      navigate(`${prefix}/classes/${item.id}`);
    }
    else { setSelectedItem(item); setSelectedItemType(type); setViewDialogOpen(true); }
  };

  const handleAccountAction = async (item, action, entityType) => {
    try {
      const entityId = item.id;
      switch (action) {
        case 'reset-password': {
          const genRes = await api.post('/principal/generate-password');
          const tempPass = genRes.data.password;
          await api.put(`/principal/${entityType}/${entityId}/credentials`, { new_password: tempPass });
          toast.success(t('passwordResetTo', { pass: tempPass }));
          break;
        }
        case 'suspend':
          await api.put(`/principal/${entityType}/${entityId}/status`, { status: 'suspended' });
          toast.success(t('accountSuspended'));
          fetchAllData();
          break;
        case 'activate':
          await api.put(`/principal/${entityType}/${entityId}/status`, { status: 'active' });
          toast.success(t('accountActivated'));
          fetchAllData();
          break;
        default: break;
      }
    } catch (error) {
      const msg = getApiErrorMessage(error);
      nassaqError(typeof msg === 'string' ? msg : (t('operationFailed')));
    }
  };

  const applyTransferSuccess = (studentId, targetClassId, studentName, className, outcome) => {
    const movingStudent = students.find(s => s.id === studentId);
    const oldClassId = outcome.oldClassId || movingStudent?.class_id;
    setStudents(prev => prev.map(s => s.id === studentId ? { ...s, class_id: targetClassId, class_name: className } : s));
    setClasses(prev => prev.map(c => {
      if (c.id === targetClassId && outcome.targetCount != null) {
        return { ...c, student_count: outcome.targetCount, current_students: outcome.targetCount };
      }
      if (oldClassId && c.id === oldClassId && outcome.oldCount != null) {
        return { ...c, student_count: outcome.oldCount, current_students: outcome.oldCount };
      }
      return c;
    }));
    // Re-derive both classes' counts from the server so counters cannot drift
    // even if the response omitted them (e.g. a same-class no-op on retry).
    refetchClasses();
  };

  const handleTransferStudent = async (studentId, targetClassId, studentName, className) => {
    const headers = {};
    if (isImpersonating && schoolContext?.school_id) headers['X-School-Context'] = schoolContext.school_id;
    await executeStudentTransfer({
      api,
      studentId,
      targetClassId,
      headers,
      messages: {
        transferred: t('transferredTo', { student: studentName, className }),
        // A failed transfer NEVER shows the generic cause-hiding fallback:
        // either the backend's own message, a transfer-specific server error,
        // or a dedicated network/connection message.
        serverError: t('transferServerError'),
        network: t('networkErrorRetry'),
      },
      onToast: (msg) => toast.success(msg),
      onSuccess: (outcome) => applyTransferSuccess(studentId, targetClassId, studentName, className, outcome),
      onError: (msg) => nassaqError(msg),
      // Localize coded backend rejections (e.g. CLASS_CAPACITY_REACHED) off the
      // error code so the popup shows one clean Arabic message — never the raw
      // mixed-language backend string.
      t,
    });
  };

  const clearFilter = () => setActiveFilter(null);

  const handleHakimAction = (action, data) => {
    switch (action) {
      case 'show_students_no_parent':
        setActiveTab('students'); setSearchQuery(''); setActiveFilter('noParent');
        toast.info(t('showingNoParent', { count: data.length }));
        break;
      case 'show_students_no_class':
        setActiveTab('students'); setSearchQuery(''); setActiveFilter('noClass');
        toast.info(t('showingNoClass', { count: data.length }));
        break;
      case 'show_teachers_no_subject':
        setActiveTab('teachers'); setSearchQuery(''); setActiveFilter('noSubject');
        toast.info(t('showingNoSubject', { count: data.length }));
        break;
      case 'show_no_email':
        setActiveTab('students'); setSearchQuery(''); setActiveFilter('noEmail');
        toast.info(t('showingNoEmail', { count: data.length }));
        break;
      case 'show_suspended':
        setActiveTab('students'); setSearchQuery(''); setActiveFilter('suspended');
        toast.info(t('showingSuspended', { count: data.length }));
        break;
      case 'show_over_capacity':
        setActiveTab('classes'); setSearchQuery(''); setActiveFilter('overCapacity');
        toast.info(t('showingOverCap', { count: data.length }));
        break;
      default: break;
    }
  };

  const handleSaveEdit = async () => {
    if (!selectedItem || !selectedItemType) return;
    setEditLoading(true);
    try {
      const ep = selectedItemType === 'student' ? `/students/${selectedItem.id}` : selectedItemType === 'teacher' ? `/teachers/${selectedItem.id}` : `/classes/${selectedItem.id}`;
      let updateData = {};
      if (selectedItemType === 'student') {
        const name = editFormData.full_name || editFormData.full_name_ar;
        if (name) updateData.full_name = name;
        if (editFormData.email?.includes('@')) updateData.email = editFormData.email;
        if (editFormData.phone) updateData.phone = editFormData.phone;
        if (editFormData.class_id) updateData.class_id = editFormData.class_id;
        if (editFormData.gender) updateData.gender = editFormData.gender;
        if (typeof editFormData.is_gifted === 'boolean') updateData.is_gifted = editFormData.is_gifted;
        if (typeof editFormData.is_active === 'boolean') updateData.is_active = editFormData.is_active;
      } else if (selectedItemType === 'teacher') {
        const name = editFormData.full_name || editFormData.full_name_ar;
        if (name) updateData.full_name = name;
        if (editFormData.email?.includes('@')) updateData.email = editFormData.email;
        if (editFormData.phone) updateData.phone = editFormData.phone;
        if (editFormData.specialization) updateData.specialization = editFormData.specialization;
        if (typeof editFormData.is_active === 'boolean') updateData.is_active = editFormData.is_active;
      } else if (selectedItemType === 'class') {
        const name = editFormData.name || editFormData.name_ar;
        if (name) updateData.name = name;
        const grade = editFormData.grade_level || editFormData.grade;
        if (grade) updateData.grade_level = grade;
        if (editFormData.section) updateData.section = editFormData.section;
        if (editFormData.capacity) updateData.capacity = editFormData.capacity;
        if (typeof editFormData.is_active === 'boolean') updateData.is_active = editFormData.is_active;
      }
      if (Object.keys(updateData).length === 0) {
        nassaqWarning(t('noChanges'));
        setEditLoading(false);
        return;
      }
      await api.put(ep, updateData);
      const entityLabel = selectedItemType === 'student' ? (t('studentLower')) : selectedItemType === 'teacher' ? (t('teacherLower')) : (t('classLower'));
      toast.success(t('entitySaved', { entity: entityLabel }));
      setEditDialogOpen(false);
      setSelectedItem(null);
      fetchAllData();
    } catch (error) {
      let errMsg = t('saveFailed');
      if (getApiErrorMessage(error)) {
        errMsg = typeof getApiErrorMessage(error) === 'string' ? getApiErrorMessage(error) : errMsg;
      }
      nassaqError(errMsg);
    } finally { setEditLoading(false); }
  };

  const handleRefresh = () => { fetchAllData(); toast.success(t('dataRefreshed')); };
  const handleStudentCreated = () => { setShowStudentWizard(false); fetchAllData(); };
  const handleTeacherCreated = () => { setShowTeacherWizard(false); fetchAllData(); };
  const handleClassCreated = (payload) => {
    setShowClassWizard(false);
    // Optimistically append the new class so the totalClasses stat card and
    // the classes tab badge reflect the addition immediately, without waiting
    // for a full multi-endpoint reload (which can drift on partial failure).
    const created = payload?.class;
    const createdId = payload?.class_id || created?.id;
    if (createdId) {
      setClasses(prev => {
        if (prev.some(c => c.id === createdId)) return prev;
        return [...prev, { id: createdId, is_active: true, student_count: 0, ...(created || {}) }];
      });
    }
    // Targeted refetch keeps the list in sync with the server (fills in any
    // fields the wizard response didn't carry) while preserving the
    // optimistic count on transient failure.
    refetchClasses();
  };

  const [downloadingTemplate, setDownloadingTemplate] = useState(false);

  const downloadTemplate = async (type) => {
    setDownloadingTemplate(true);
    try {
      const response = await api.get(`/bulk/template/${type}`, { responseType: 'blob' });
      const contentType = response.headers['content-type'] || '';
      if (!contentType.includes('spreadsheet') && !contentType.includes('octet-stream') && !contentType.includes('excel')) {
        throw new Error(t('responseIsNotAValidFile'));
      }
      const url = window.URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = url;
      const disposition = response.headers['content-disposition'];
      let filename = type === 'students' ? t('studentsTemplateName') : t('teachersTemplateName');
      if (disposition) {
        try {
          const starMatch = disposition.match(/filename\*=(?:UTF-8''|utf-8'')([^\s;]+)/i);
          const plainMatch = disposition.match(/filename[^;=\n]*=(['"]?)([^'"\n]*)\1/);
          if (starMatch?.[1]) filename = decodeURIComponent(starMatch[1]);
          else if (plainMatch?.[2]) filename = decodeURIComponent(plainMatch[2]);
        } catch (e) { console.error('Error parsing filename from disposition:', e); }
      }
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success(t('templateDownloadedSuccessfully'));
    } catch (err) {
      console.error('Template download error:', err);
      nassaqError(err.message || (t('templateDownloadFailedCheckLoginAndTryAgain')));
    } finally {
      setDownloadingTemplate(false);
    }
  };

  const handleFileSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      if (!['.xlsx', '.xls', '.csv'].some(t => file.name.toLowerCase().endsWith(t))) {
        nassaqWarning(t('unsupportedFormat'));
        return;
      }
      setSelectedFile(file);
      setImportResult(null);
    }
  };

  const handleImport = async () => {
    if (!selectedFile) { nassaqWarning(t('selectAFile')); return; }
    setImporting(true); setImportResult(null);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      const response = await api.post(`/bulk/import/${importType}`, formData, { headers: { 'Content-Type': 'multipart/form-data' } });
      setImportResult(response.data);
      if (response.data.success) { toast.success(t('importedNRecords', { n: response.data.imported })); fetchAllData(); }
      else nassaqWarning(t('importedOfTotal', { imported: response.data.imported, total: response.data.total_rows }));
    } catch (error) { nassaqError(getApiErrorMessage(error) || (t('importFailed'))); }
    finally { setImporting(false); }
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const response = await api.get(`/bulk/export/${exportType}?format=${exportFormat}`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `export_${exportType}.${exportFormat}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success(t('exported'));
    } catch (error) { nassaqError(t('exportFailed')); }
    finally { setExporting(false); }
  };

  const handleStatClick = (type) => {
    setSearchQuery('');
    switch (type) {
      case 'students': setActiveTab('students'); setActiveFilter(null); break;
      case 'parents': setActiveTab('parents'); setActiveFilter(null); break;
      case 'teachers': setActiveTab('teachers'); setActiveFilter(null); break;
      case 'classes': setActiveTab('classes'); setActiveFilter(null); break;
      default: break;
    }
  };

  const isSchoolAdmin = user?.role === 'school_admin' || user?.role === 'school_principal' || user?.role === 'platform_admin';

  const renderStudentsSection = () => {
    return (
      <div className="space-y-4">
        <StudentClassGrid
          students={displayedStudents}
          classes={classes}
          isRTL={isRTL}
          searchQuery={searchQuery}
          onView={(s) => handleView(s, 'student')}
          onEdit={(s) => handleEdit(s, 'student')}
          onDelete={(s) => handleDelete(s, 'student')}
          onAction={(s, a) => handleAccountAction(s, a, 'student')}
          onTransferStudent={handleTransferStudent}
          canDrag={isSchoolAdmin}
        />
      </div>
    );
  };

  const renderSection = (type) => {
    if (type === 'students') return renderStudentsSection();

    const items = type === 'teachers' ? filteredTeachers : type === 'parents' ? filteredParents : filteredClasses;
    const EmptyIcon = type === 'teachers' ? UserCheck : type === 'parents' ? Heart : Building2;

    if (items.length === 0) {
      return (
        <Card className="p-12 text-center border-dashed">
          <EmptyIcon className="h-16 w-16 mx-auto text-muted-foreground/15 mb-4" />
          <p className="text-muted-foreground font-medium">{t('noResults')}</p>
          <p className="text-sm text-muted-foreground/60 mt-1">
            {searchQuery ? (t('tryADifferentSearch')) : (t('addANewItemToStart'))}
          </p>
          {!searchQuery && type !== 'parents' && (
            <Button variant="outline" className="mt-4" onClick={() => setShowAddPicker(true)}>
              <Plus className="h-4 w-4 me-1.5" />{t('addNew')}
            </Button>
          )}
        </Card>
      );
    }

    if (viewMode === 'list') {
      return (
        <div className="space-y-2">
          {items.map(item => (
            type === 'teachers' ? (
              <TeacherCard key={item.id} teacher={item} isRTL={isRTL} viewMode="list"
                onEdit={(t) => handleEdit(t, 'teacher')} onDelete={(t) => handleDelete(t, 'teacher')}
                onView={(t) => handleView(t, 'teacher')} onAction={(t, a) => handleAccountAction(t, a, 'teacher')} />
            ) : type === 'parents' ? (
              <ParentCard key={item.id} parent={item} isRTL={isRTL} viewMode="list"
                onView={(p) => handleView(p, 'parent')} onAction={(p, a) => handleAccountAction(p, a, 'parent')} onDelete={(p) => handleDelete(p, 'parent')} />
            ) : (
              <ClassCard key={item.id} classItem={item} isRTL={isRTL} viewMode="list"
                onEdit={(c) => handleEdit(c, 'class')} onDelete={(c) => handleDelete(c, 'class')}
                onView={(c) => handleView(c, 'class')} onReactivate={handleReactivateClass} />
            )
          ))}
        </div>
      );
    }

    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-4">
        {items.map(item => (
          type === 'teachers' ? (
            <TeacherCard key={item.id} teacher={item} isRTL={isRTL}
              onEdit={(t) => handleEdit(t, 'teacher')} onDelete={(t) => handleDelete(t, 'teacher')}
              onView={(t) => handleView(t, 'teacher')} onAction={(t, a) => handleAccountAction(t, a, 'teacher')} />
          ) : type === 'parents' ? (
            <ParentCard key={item.id} parent={item} isRTL={isRTL}
              onView={(p) => handleView(p, 'parent')} onAction={(p, a) => handleAccountAction(p, a, 'parent')} onDelete={(p) => handleDelete(p, 'parent')} />
          ) : (
            <ClassCard key={item.id} classItem={item} isRTL={isRTL}
              onEdit={(c) => handleEdit(c, 'class')} onDelete={(c) => handleDelete(c, 'class')}
              onView={(c) => handleView(c, 'class')} onReactivate={handleReactivateClass} />
          )
        ))}
      </div>
    );
  };

  return (
    <Sidebar>
      <div className="min-h-screen" data-testid="users-classes-management">
        <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="font-cairo text-2xl font-bold">{t('usersClassesMgmt')}</h1>
              <p className="text-sm text-muted-foreground font-tajawal">{t('comprehensiveManagementCenterForAccountsAndClasses')}</p>
            </div>
            <div className="flex items-center gap-2">
              <Button onClick={() => setShowAddPicker(true)} className="bg-brand-turquoise hover:bg-brand-turquoise/90 rounded-xl h-10 shadow-md">
                <Plus className="h-4 w-4 me-1.5" />{t('add')}
              </Button>
              <Button variant="ghost" size="icon" onClick={toggleLanguage}><Globe className="h-5 w-5" /></Button>
              <Button variant="ghost" size="icon" onClick={toggleTheme}>{isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}</Button>
              <NotificationBell />
            </div>
          </div>
        </header>

        <main className="p-6 space-y-6">
          {(() => {
            const statCards = [
              { key: 'students', label: t('totalStudents'), value: stats.totalStudents, Icon: GraduationCap, accent: '#1C3D74' },
              { key: 'parents',  label: t('totalParents'),  value: stats.totalParents,  Icon: Heart,         accent: '#E07A5F' },
              { key: 'teachers', label: t('totalTeachers'), value: stats.totalTeachers, Icon: UserCheck,     accent: '#2BB5A0' },
              { key: 'classes',  label: t('totalClasses'),  value: stats.totalClasses,  Icon: Building2,     accent: '#46C1BE' },
            ];
            return (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {statCards.map(({ key, label, value, Icon, accent }) => {
                  const isActive = activeTab === key;
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => handleStatClick(key)}
                      aria-pressed={isActive}
                      className={`group relative text-start overflow-hidden rounded-2xl bg-white dark:bg-gray-900
                        border ${isActive ? 'border-[#2BB5A0]/40 shadow-lg shadow-[#2BB5A0]/10' : 'border-gray-200/70 dark:border-gray-800 shadow-sm'}
                        hover:-translate-y-0.5 hover:shadow-md transition-all duration-200
                        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#2BB5A0] focus-visible:ring-offset-2`}
                    >
                      <span
                        aria-hidden="true"
                        className="absolute inset-x-0 top-0 h-1"
                        style={{ background: isActive
                          ? 'linear-gradient(90deg,#1C3D74,#2BB5A0)'
                          : accent
                        }}
                      />
                      <div className="p-4 sm:p-5 flex items-start gap-3">
                        <span
                          className="shrink-0 inline-flex items-center justify-center w-11 h-11 rounded-xl border"
                          style={{
                            backgroundColor: `${accent}14`,
                            color: accent,
                            borderColor: `${accent}33`,
                          }}
                        >
                          <Icon className="h-5 w-5" strokeWidth={2.25} />
                        </span>
                        <div className="min-w-0 flex-1">
                          <p
                            className="text-3xl font-extrabold leading-none tracking-tight tabular-nums text-[#1C3D74] dark:text-white"
                          >
                            {value}
                          </p>
                          <p className="mt-1.5 text-[11px] font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400 line-clamp-1">
                            {label}
                          </p>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            );
          })()}

          <div className="flex items-center gap-3 min-w-0">
            <div className="flex-1 min-w-0 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {(() => {
              const tabTriggerCls = 'rounded-lg text-xs px-3 h-9 transition-all whitespace-nowrap data-[state=active]:bg-[#1C3D74] data-[state=active]:text-white data-[state=active]:shadow-sm hover:text-[#1C3D74] dark:hover:text-white';
              const tabBadgeCls = (key) =>
                `ms-1.5 h-5 text-[10px] px-1.5 border-0 ${
                  activeTab === key
                    ? 'bg-white/20 text-white'
                    : 'bg-gray-200/80 text-gray-600 dark:bg-gray-700/60 dark:text-gray-300'
                }`;
              return (
                <Tabs value={activeTab} onValueChange={(v) => { setActiveTab(v); setActiveFilter(null); }} className="w-auto">
                  <TabsList className="bg-gray-100/80 dark:bg-gray-800/60 rounded-xl h-11 p-1 gap-0.5">
                    <TabsTrigger value="students" className={tabTriggerCls} data-testid="filter-students">
                      <GraduationCap className="h-3.5 w-3.5 me-1.5" />
                      {t('students')}
                      <Badge variant="secondary" className={tabBadgeCls('students')}>{filteredStudents.length}</Badge>
                    </TabsTrigger>
                    <TabsTrigger value="parents" className={tabTriggerCls} data-testid="filter-parents">
                      <Heart className="h-3.5 w-3.5 me-1.5" />
                      {t('parents')}
                      <Badge variant="secondary" className={tabBadgeCls('parents')}>{filteredParents.length}</Badge>
                    </TabsTrigger>
                    <TabsTrigger value="teachers" className={tabTriggerCls} data-testid="filter-teachers">
                      <UserCheck className="h-3.5 w-3.5 me-1.5" />
                      {t('teachers2')}
                      <Badge variant="secondary" className={tabBadgeCls('teachers')}>{filteredTeachers.length}</Badge>
                    </TabsTrigger>
                    <TabsTrigger value="classes" className={tabTriggerCls} data-testid="filter-classes">
                      <Building2 className="h-3.5 w-3.5 me-1.5" />
                      {t('classes2')}
                      <Badge variant="secondary" className={tabBadgeCls('classes')}>{filteredClasses.length}</Badge>
                    </TabsTrigger>
                    <TabsTrigger value="import-export"
                      className="rounded-lg text-xs px-3.5 h-9 transition-all data-[state=active]:bg-[#2BB5A0] data-[state=active]:text-white data-[state=active]:shadow-sm hover:text-[#2BB5A0]">
                      <FileSpreadsheet className="h-3.5 w-3.5 me-1.5" />
                      {t('importexport')}
                      {noorImportCount > 0 && (
                        <Badge
                          variant="secondary"
                          className={tabBadgeCls('import-export')}
                          data-testid="noor-import-history-badge"
                        >
                          {noorImportCount}
                        </Badge>
                      )}
                    </TabsTrigger>
                  </TabsList>
                </Tabs>
              );
            })()}
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="rounded-xl h-10 gap-2 px-3">
                    <ArrowUpDown className="h-4 w-4" />
                    <span className="text-xs hidden sm:inline">
                      {sortBy === 'name_asc' ? (t('az')) :
                       sortBy === 'name_desc' ? (t('za')) :
                       sortBy === 'date_desc' ? (t('newest')) :
                       sortBy === 'date_asc' ? (t('oldest')) :
                       sortBy === 'number_asc' ? (t('number2')) :
                       sortBy === 'grade_asc' ? (t('grade5')) :
                       sortBy === 'capacity_desc' ? (t('mostStudents')) :
                       (t('sort'))}
                    </span>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-48">
                  <DropdownMenuItem onClick={() => setSortBy('name_asc')} className={sortBy === 'name_asc' ? 'bg-accent' : ''}>
                    <ArrowUp className="h-3.5 w-3.5 me-2" />{t('alphabeticalAZ')}
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setSortBy('name_desc')} className={sortBy === 'name_desc' ? 'bg-accent' : ''}>
                    <ArrowDown className="h-3.5 w-3.5 me-2" />{t('alphabeticalZA')}
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => setSortBy('date_desc')} className={sortBy === 'date_desc' ? 'bg-accent' : ''}>
                    <Clock className="h-3.5 w-3.5 me-2" />{t('newestFirst')}
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => setSortBy('date_asc')} className={sortBy === 'date_asc' ? 'bg-accent' : ''}>
                    <Clock className="h-3.5 w-3.5 me-2" />{t('oldestFirst')}
                  </DropdownMenuItem>
                  {activeTab === 'students' && (
                    <>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={() => setSortBy('number_asc')} className={sortBy === 'number_asc' ? 'bg-accent' : ''}>
                        <Hash className="h-3.5 w-3.5 me-2" />{t('studentNumber')}
                      </DropdownMenuItem>
                    </>
                  )}
                  {activeTab === 'classes' && (
                    <>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={() => setSortBy('grade_asc')} className={sortBy === 'grade_asc' ? 'bg-accent' : ''}>
                        <GraduationCap className="h-3.5 w-3.5 me-2" />{t('byGradeLevel')}
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => setSortBy('capacity_desc')} className={sortBy === 'capacity_desc' ? 'bg-accent' : ''}>
                        <Users className="h-3.5 w-3.5 me-2" />{t('mostStudents')}
                      </DropdownMenuItem>
                    </>
                  )}
                </DropdownMenuContent>
              </DropdownMenu>
              <div className="flex items-center bg-muted/50 rounded-lg p-0.5">
                <Button variant={viewMode === 'grid' ? 'default' : 'ghost'} size="icon" className="h-8 w-8 rounded-md"
                  onClick={() => setViewMode('grid')} title={t('gridView')}>
                  <LayoutGrid className="h-4 w-4" />
                </Button>
                <Button variant={viewMode === 'list' ? 'default' : 'ghost'} size="icon" className="h-8 w-8 rounded-md"
                  onClick={() => setViewMode('list')} title={t('listView')}>
                  <List className="h-4 w-4" />
                </Button>
              </div>
              <div className="relative">
                <Search className="absolute start-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input placeholder={t('search')} value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
                  className="ps-10 w-[160px] md:w-[200px] xl:w-[260px] rounded-xl h-10" data-testid="search-input" />
              </div>
              <Button variant="outline" size="icon" onClick={handleRefresh} className="rounded-xl h-10 w-10" title={t('refresh')}>
                <RefreshCw className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {activeTab === 'students' && studentsNoClass.length > 0 && activeFilter !== 'noClass' && (
            <div className="flex items-center gap-3 p-3 px-4 rounded-xl bg-gradient-to-l from-red-50 to-amber-50 dark:from-red-950/30 dark:to-amber-950/20 border border-red-300 dark:border-red-800 shadow-sm">
              <div className="flex items-center justify-center h-9 w-9 rounded-full bg-red-100 dark:bg-red-900/40 shrink-0">
                <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-sm text-red-700 dark:text-red-300">
                    {isRTL ? 'يوجد طلاب بدون فصل' : 'Students without a class'}
                  </span>
                  <Badge className="bg-red-600 hover:bg-red-600 text-white text-xs px-2 h-5 rounded-full">
                    {studentsNoClass.length}
                  </Badge>
                </div>
                <p className="text-xs text-red-700/80 dark:text-red-300/80 mt-0.5">
                  {isRTL
                    ? 'هؤلاء الطلاب لن يظهروا في الجداول الدراسية حتى تُعيّن لهم فصلاً.'
                    : "These students won't appear in any timetable until you assign a class."}
                </p>
              </div>
              {SHOW_NO_CLASS_BANNER_CTA && (
                <Button
                  size="sm"
                  onClick={() => { setActiveFilter('noClass'); setSearchQuery(''); }}
                  className="bg-red-600 hover:bg-red-700 text-white shrink-0"
                  data-testid="banner-show-no-class"
                >
                  {isRTL ? 'عرضهم الآن' : 'Show them now'}
                </Button>
              )}
            </div>
          )}

          {activeTab === 'classes' && (
            <div className="flex items-center justify-end gap-2 px-1">
              <Switch
                id="show-inactive-classes-toggle"
                checked={showInactiveClasses}
                onCheckedChange={setShowInactiveClasses}
                data-testid="toggle-show-inactive-classes"
              />
              <Label htmlFor="show-inactive-classes-toggle" className="text-sm font-tajawal cursor-pointer">
                {t('showInactiveClasses')}
              </Label>
            </div>
          )}

          {activeFilter && (
            <div className="flex items-center gap-2 p-2.5 px-4 rounded-xl bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800">
              <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0" />
              <span className="text-sm text-amber-700 dark:text-amber-300 flex-1">
                {activeFilter === 'noParent' ? (t('showingStudentsWithoutAParent')) :
                 activeFilter === 'noClass' ? (t('showingStudentsWithoutAClass')) :
                 activeFilter === 'noSubject' ? (t('showingTeachersWithoutASubject')) :
                 activeFilter === 'noEmail' ? (t('showingAccountsWithoutEmail')) :
                 activeFilter === 'suspended' ? (t('showingSuspendedAccounts')) :
                 activeFilter === 'overCapacity' ? (t('showingOvercapacityClasses')) : ''}
              </span>
              <Button variant="ghost" size="sm" onClick={clearFilter} className="h-7 text-xs text-amber-700 hover:text-amber-900">
                <X className="h-3.5 w-3.5 me-1" />{t('clearFilter')}
              </Button>
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="h-8 w-8 animate-spin text-brand-turquoise" />
              <span className="ms-3 text-muted-foreground">{t('loading')}</span>
            </div>
          ) : (
            <>
              {activeTab === 'students' && renderSection('students')}
              {activeTab === 'parents' && renderSection('parents')}
              {activeTab === 'teachers' && renderSection('teachers')}
              {activeTab === 'classes' && renderSection('classes')}

              {activeTab === 'import-export' && (
                <div className="space-y-6">
                  <Tabs defaultValue="import" className="space-y-6">
                    <TabsList className="grid w-full max-w-md grid-cols-2">
                      <TabsTrigger value="import"><FileUp className="h-4 w-4 me-2" />{t('import')}</TabsTrigger>
                      <TabsTrigger value="export"><FileDown className="h-4 w-4 me-2" />{t('export')}</TabsTrigger>
                    </TabsList>

                    <TabsContent value="import">
                      <NoorImportPanel api={api} nassaqError={nassaqError} nassaqWarning={nassaqWarning} nassaqConfirm={nassaqConfirm} nassaqInfo={nassaqInfo} t={t} onComplete={fetchAllData} onHistoryCountChange={setNoorImportCount} />
                      <div className="grid gap-6 lg:grid-cols-2 mt-6">
                        <Card>
                          <CardHeader>
                            <CardTitle className="flex items-center gap-2"><Upload className="h-5 w-5 text-brand-turquoise" />{t('importData')}</CardTitle>
                          </CardHeader>
                          <CardContent className="space-y-5">
                            <div className="space-y-2">
                              <Label className="text-sm">{t('dataType')}</Label>
                              <div className="grid grid-cols-2 gap-3">
                                {[{ value: 'students', label: t('students'), icon: GraduationCap }, { value: 'teachers', label: t('teachers2'), icon: Users }].map(opt => {
                                  const Icon = opt.icon;
                                  return (
                                    <button key={opt.value} onClick={() => setImportType(opt.value)}
                                      className={`p-3 rounded-xl border-2 transition-all text-center ${importType === opt.value ? 'border-brand-turquoise bg-brand-turquoise/10' : 'border-border hover:border-brand-turquoise/50'}`}>
                                      <Icon className={`h-6 w-6 mx-auto mb-1 ${importType === opt.value ? 'text-brand-turquoise' : 'text-muted-foreground'}`} />
                                      <p className="text-xs font-medium">{opt.label}</p>
                                    </button>
                                  );
                                })}
                              </div>
                            </div>
                            <Button variant="outline" onClick={() => downloadTemplate(importType)} disabled={downloadingTemplate} className="w-full">{downloadingTemplate ? <Loader2 className="h-4 w-4 me-2 animate-spin" /> : <Download className="h-4 w-4 me-2" />}{downloadingTemplate ? (t('downloading')) : (t('downloadTemplate2'))}</Button>
                            <div className="border-2 border-dashed rounded-xl p-5 text-center hover:border-brand-turquoise/50 transition-colors">
                              <Input type="file" accept=".xlsx,.xls,.csv" onChange={handleFileSelect} className="hidden" id="file-upload" />
                              <label htmlFor="file-upload" className="cursor-pointer">
                                <FileSpreadsheet className="h-10 w-10 mx-auto mb-2 text-muted-foreground" />
                                <p className="text-xs text-muted-foreground">{t('dragOrSelectFile')}</p>
                              </label>
                              {selectedFile && <Badge variant="outline" className="mt-2">{selectedFile.name}</Badge>}
                            </div>
                            <Button onClick={handleImport} disabled={importing || !selectedFile} className="w-full">
                              {importing ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Upload className="h-4 w-4 me-2" />}
                              {importing ? (t('importing')) : (t('startImport'))}
                            </Button>
                          </CardContent>
                        </Card>
                        {importResult && (
                          <Card>
                            <CardHeader><CardTitle>{t('importResult')}</CardTitle></CardHeader>
                            <CardContent className="space-y-3">
                              <div className="grid grid-cols-3 gap-3 text-center">
                                <div className="p-3 bg-muted/50 rounded-lg"><p className="text-xl font-bold">{importResult.total_rows || 0}</p><p className="text-xs text-muted-foreground">{t('total2')}</p></div>
                                <div className="p-3 bg-green-50 dark:bg-green-950/30 rounded-lg"><p className="text-xl font-bold text-green-600">{importResult.imported || 0}</p><p className="text-xs text-muted-foreground">{t('done')}</p></div>
                                <div className="p-3 bg-red-50 dark:bg-red-950/30 rounded-lg"><p className="text-xl font-bold text-red-600">{importResult.failed || 0}</p><p className="text-xs text-muted-foreground">{t('failed')}</p></div>
                              </div>
                              {importResult.errors?.length > 0 && (
                                <div className="max-h-[200px] overflow-y-auto space-y-1">
                                  {importResult.errors.map((err, i) => (
                                    <div key={i} className="text-xs p-2 bg-red-50 dark:bg-red-950/20 rounded text-red-600">Row {err.row}: {err.message || err.error}</div>
                                  ))}
                                </div>
                              )}
                            </CardContent>
                          </Card>
                        )}
                      </div>
                    </TabsContent>

                    <TabsContent value="export">
                      <Card className="max-w-lg">
                        <CardHeader><CardTitle className="flex items-center gap-2"><Download className="h-5 w-5 text-brand-turquoise" />{t('exportData')}</CardTitle></CardHeader>
                        <CardContent className="space-y-4">
                          <div className="space-y-2">
                            <Label>{t('dataType')}</Label>
                            <Select value={exportType} onValueChange={setExportType}>
                              <SelectTrigger><SelectValue /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="students">{t('students')}</SelectItem>
                                <SelectItem value="teachers">{t('teachers2')}</SelectItem>
                                <SelectItem value="schedule">{t('schedule')}</SelectItem>
                                <SelectItem value="attendance">{t('attendance2')}</SelectItem>
                                <SelectItem value="grades">{t('grades')}</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="space-y-2">
                            <Label>{t('format')}</Label>
                            <div className="flex gap-2">
                              {['xlsx', 'csv', 'json'].map(f => (
                                <Button key={f} variant={exportFormat === f ? 'default' : 'outline'} size="sm" onClick={() => setExportFormat(f)} className="flex-1">{f.toUpperCase()}</Button>
                              ))}
                            </div>
                          </div>
                          <Button onClick={handleExport} disabled={exporting} className="w-full">
                            {exporting ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Download className="h-4 w-4 me-2" />}
                            {exporting ? (t('exporting')) : (t('export'))}
                          </Button>
                        </CardContent>
                      </Card>
                    </TabsContent>
                  </Tabs>
                </div>
              )}
            </>
          )}
        </main>

        <PermanentHakimWidget insights={hakimInsights} isRTL={isRTL} onAction={handleHakimAction} stats={stats} />

        <AddPickerDialog open={showAddPicker} onClose={() => setShowAddPicker(false)} isRTL={isRTL} onSelect={handleAddSelect} />

        {showStudentWizard && (
          <AddStudentWizard
            open={showStudentWizard}
            onOpenChange={(val) => { if (!val) setShowStudentWizard(false); }}
            onSuccess={handleStudentCreated}
            api={api}
            isRTL={isRTL}
            grades={grades}
            classes={classes}
          />
        )}
        {showTeacherWizard && (
          <AddTeacherWizard
            open={showTeacherWizard}
            onOpenChange={(val) => { if (!val) setShowTeacherWizard(false); }}
            onSuccess={handleTeacherCreated}
          />
        )}
        {showClassWizard && (
          <CreateClassWizard
            open={showClassWizard}
            onOpenChange={(val) => { if (!val) setShowClassWizard(false); }}
            onSuccess={handleClassCreated}
          />
        )}

        <TeacherProfileDialog
          open={teacherProfileOpen}
          onClose={() => setTeacherProfileOpen(false)}
          teacher={selectedTeacher}
          onRefresh={fetchAllData}
        />

        <ParentProfileDialog
          open={parentProfileOpen}
          onClose={() => setParentProfileOpen(false)}
          parent={selectedParent}
          onRefresh={fetchAllData}
        />

        <Dialog open={viewDialogOpen} onOpenChange={(open) => { setViewDialogOpen(open); if (!open) { setViewClassEditing(false); setViewClassForm({}); } }}>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle>
                {selectedItemType === 'teacher' ? (t('teacherDetails')) :
                 selectedItemType === 'parent' ? (t('parentDetails')) :
                 (t('classDetails'))}
              </DialogTitle>
            </DialogHeader>
            {selectedItem && selectedItemType === 'teacher' && (
              <div className="space-y-4">
                <div className="flex items-center gap-4">
                  <TeacherAvatar teacher={selectedItem} size="lg" />
                  <div>
                    <h3 className="font-bold text-lg">{selectedItem.full_name}</h3>
                    <p className="text-sm text-muted-foreground">{selectedItem.specialization || (t('teacher'))}</p>
                    <Badge className="mt-1">{selectedItem.rank || (t('teacher'))}</Badge>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div><span className="text-muted-foreground">{t('email')}:</span> <span className="font-medium">{selectedItem.email || '-'}</span></div>
                  <div><span className="text-muted-foreground">{t('phone2')}:</span> <span className="font-medium">{selectedItem.phone || '-'}</span></div>
                  <div><span className="text-muted-foreground">{t('experience2')}:</span> <span className="font-medium">{selectedItem.years_of_experience || 0} {t('yearsLabel')}</span></div>
                  <div><span className="text-muted-foreground">{t('status2')}:</span>
                    <Badge variant={selectedItem.is_active !== false ? 'default' : 'secondary'} className="ms-1">{selectedItem.is_active !== false ? (t('active')) : (t('suspended'))}</Badge>
                  </div>
                </div>
              </div>
            )}
            {selectedItem && selectedItemType === 'parent' && (
              <div className="space-y-4">
                <div className="flex items-center gap-4">
                  <ParentAvatar parent={selectedItem} size="lg" />
                  <div>
                    <h3 className="font-bold text-lg">{selectedItem.full_name}</h3>
                    <p className="text-sm text-muted-foreground">{selectedItem.relationship || (t('parentRole'))}</p>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div><span className="text-muted-foreground">{t('phone2')}:</span> <span className="font-medium" dir="ltr">{selectedItem.phone || '-'}</span></div>
                  <div><span className="text-muted-foreground">{t('email')}:</span> <span className="font-medium">{selectedItem.email || '-'}</span></div>
                  <div><span className="text-muted-foreground">{t('nationalId')}:</span> <span className="font-medium">{selectedItem.national_id || '-'}</span></div>
                  <div><span className="text-muted-foreground">{t('children3')}:</span> <span className="font-medium">{selectedItem.children_count || 0}</span></div>
                </div>
                {selectedItem.children?.length > 0 && (
                  <div>
                    <p className="text-sm font-semibold mb-2">{t('registeredChildren')}</p>
                    <div className="flex flex-wrap gap-2">
                      {selectedItem.children.map((child, i) => (
                        <Badge key={i} variant="outline" className="border-amber-300 text-amber-700 dark:border-amber-700 dark:text-amber-400">
                          <GraduationCap className="h-3 w-3 me-1" />{child.name}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
            {selectedItem && selectedItemType === 'class' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className={`w-16 h-16 rounded-xl bg-gradient-to-br ${THEME_COLORS.class.gradient} flex items-center justify-center shadow-md`}>
                      <Building2 className="h-8 w-8 text-white" />
                    </div>
                    <div>
                      <h3 className="font-bold text-lg">{selectedItem.name}</h3>
                      <p className="text-sm text-muted-foreground">{selectedItem.grade} - {selectedItem.section}</p>
                    </div>
                  </div>
                  {!viewClassEditing && (
                    <Button size="sm" variant="outline" onClick={() => { setViewClassEditing(true); setViewClassForm({ name: selectedItem.name || '', grade_level: selectedItem.grade_level || selectedItem.grade || '', section: selectedItem.section || '', capacity: selectedItem.capacity || 30 }); }}>
                      <Edit className="h-3.5 w-3.5 me-1" />{t('edit')}
                    </Button>
                  )}
                </div>

                {viewClassEditing ? (
                  <div className="space-y-3 border rounded-lg p-3">
                    <div className="space-y-2">
                      <Label>{t('className')}</Label>
                      <Input value={viewClassForm.name} onChange={(e) => setViewClassForm({ ...viewClassForm, name: e.target.value })} />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-2">
                        <Label>{t('grade')}</Label>
                        <Select value={viewClassForm.grade_level} onValueChange={(value) => setViewClassForm({ ...viewClassForm, grade_level: value })}>
                          <SelectTrigger><SelectValue placeholder={t('selectGrade')} /></SelectTrigger>
                          <SelectContent>
                            {CANONICAL_GRADES.map((g) => (<SelectItem key={g.grade} value={g.label_ar}>{g.label_ar}</SelectItem>))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label>{t('section')}</Label>
                        <Input value={viewClassForm.section} onChange={(e) => setViewClassForm({ ...viewClassForm, section: e.target.value })} />
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label>{t('capacity2')}</Label>
                      <Input type="number" value={viewClassForm.capacity} onChange={(e) => setViewClassForm({ ...viewClassForm, capacity: parseInt(e.target.value) || 30 })} />
                    </div>
                    <div className="flex gap-2 justify-end">
                      <Button size="sm" variant="outline" onClick={() => setViewClassEditing(false)}><X className="h-3.5 w-3.5 me-1" />{t('cancel')}</Button>
                      <Button size="sm" disabled={viewClassSaving} onClick={async () => {
                        setViewClassSaving(true);
                        try {
                          const updateData = {};
                          if (viewClassForm.name) updateData.name = viewClassForm.name;
                          if (viewClassForm.grade_level) updateData.grade_level = viewClassForm.grade_level;
                          if (viewClassForm.section) updateData.section = viewClassForm.section;
                          if (viewClassForm.capacity) updateData.capacity = viewClassForm.capacity;
                          await api.put(`/classes/${selectedItem.id}`, updateData);
                          toast.success(t('changesSaved2'));
                          setViewClassEditing(false);
                          fetchAllData();
                          setViewDialogOpen(false);
                        } catch (e) {
                          nassaqError(getApiErrorMessage(e) || (t('saveFailed')));
                        } finally { setViewClassSaving(false); }
                      }}>
                        {viewClassSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin me-1" /> : <Save className="h-3.5 w-3.5 me-1" />}
                        {t('save')}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div><span className="text-muted-foreground">{t('capacity2')}:</span> <span className="font-medium">{selectedItem.student_count || 0} / {selectedItem.capacity || 30}</span></div>
                      <div><span className="text-muted-foreground">{t('homeroomLabel')}:</span> <span className="font-medium">{selectedItem.homeroom_teacher_name || '-'}</span></div>
                    </div>
                    <Progress value={((selectedItem.student_count || 0) / (selectedItem.capacity || 30)) * 100} className="h-2" />
                  </>
                )}

                <div className="border-t pt-3">
                  <h4 className="font-semibold text-sm text-red-600 mb-2">{t('dangerZone')}</h4>
                  <Button
                    variant="outline"
                    className="justify-start h-auto py-3 border-red-200 text-red-600 hover:bg-red-50 hover:text-red-600 focus-visible:text-red-600 w-full"
                    disabled={viewClassSaving}
                    onClick={() => {
                      // Backend-driven confirmation: the requires_confirmation
                      // envelope (incl. the students-unassigned warning) is shown
                      // before the class is actually deleted, and the dialog only
                      // closes after a real deletion is confirmed.
                      runClassDelete(selectedItem.id, {
                        setBusy: setViewClassSaving,
                        onDeleted: () => {
                          toast.success(t('classDeletedSuccessfully'));
                          setViewDialogOpen(false);
                          fetchAllData();
                        },
                      });
                    }}
                  >
                    <Trash2 className="h-4 w-4 me-2 text-red-500" />
                    <div className="text-start">
                      <p className="text-sm font-medium text-red-600">{t('deleteClassPermanently')}</p>
                      <p className="text-xs text-muted-foreground">{t('thisActionCannotBeUndone')}</p>
                    </div>
                  </Button>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>

        <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle>{t('editDetails')}</DialogTitle>
            </DialogHeader>
            {selectedItem && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>{t('name')}</Label>
                  <Input value={editFormData.full_name || editFormData.name || ''} onChange={(e) => setEditFormData({ ...editFormData, full_name: e.target.value, name: e.target.value })} />
                </div>
                {selectedItemType !== 'class' && (
                  <>
                    <div className="space-y-2"><Label>{t('email2')}</Label><Input value={editFormData.email || ''} onChange={(e) => setEditFormData({ ...editFormData, email: e.target.value })} /></div>
                    <div className="space-y-2"><Label>{t('phone2')}</Label><Input value={editFormData.phone || ''} onChange={(e) => setEditFormData({ ...editFormData, phone: e.target.value })} /></div>
                  </>
                )}
                {selectedItemType === 'student' && (
                  <>
                    <div className="space-y-2">
                      <Label>{t('class')}</Label>
                      <Select value={editFormData.class_id || ''} onValueChange={(v) => setEditFormData({ ...editFormData, class_id: v })}>
                        <SelectTrigger><SelectValue placeholder={t('selectClass2')} /></SelectTrigger>
                        <SelectContent>{classes.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent>
                      </Select>
                    </div>
                    <div className="flex items-center justify-between p-3 rounded-xl border border-amber-200/60 bg-amber-50/50 dark:bg-amber-950/20 dark:border-amber-800/40">
                      <div className="flex items-center gap-2">
                        <Star className={`h-4 w-4 ${editFormData.is_gifted ? 'text-amber-500 fill-amber-500' : 'text-muted-foreground'}`} />
                        <Label className="cursor-pointer">{t('giftedStudent')}</Label>
                      </div>
                      <button
                        type="button"
                        role="switch"
                        aria-checked={!!editFormData.is_gifted}
                        onClick={() => setEditFormData({ ...editFormData, is_gifted: !editFormData.is_gifted })}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${editFormData.is_gifted ? 'bg-amber-500' : 'bg-gray-300 dark:bg-gray-600'}`}
                      >
                        <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform shadow-sm ${editFormData.is_gifted ? 'translate-x-6 rtl:-translate-x-6' : 'translate-x-1 rtl:-translate-x-1'}`} />
                      </button>
                    </div>
                  </>
                )}
                {selectedItemType === 'teacher' && (
                  <div className="space-y-2"><Label>{t('specialization')}</Label><Input value={editFormData.specialization || ''} onChange={(e) => setEditFormData({ ...editFormData, specialization: e.target.value })} /></div>
                )}
                {selectedItemType === 'class' && (
                  <>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-2"><Label>{t('grade')}</Label>
                        <Select value={editFormData.grade_level || editFormData.grade || ''} onValueChange={(value) => setEditFormData({ ...editFormData, grade_level: value })}>
                          <SelectTrigger><SelectValue placeholder={t('selectGrade')} /></SelectTrigger>
                          <SelectContent>
                            {CANONICAL_GRADES.map((g) => (<SelectItem key={g.grade} value={g.label_ar}>{g.label_ar}</SelectItem>))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2"><Label>{t('section')}</Label><Input value={editFormData.section || ''} onChange={(e) => setEditFormData({ ...editFormData, section: e.target.value })} /></div>
                    </div>
                    <div className="space-y-2"><Label>{t('capacity2')}</Label><Input type="number" value={editFormData.capacity || ''} onChange={(e) => setEditFormData({ ...editFormData, capacity: parseInt(e.target.value) || 30 })} /></div>
                  </>
                )}
              </div>
            )}
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditDialogOpen(false)}>{t('cancel')}</Button>
              <Button onClick={handleSaveEdit} disabled={editLoading}>
                {editLoading ? <Loader2 className="h-4 w-4 animate-spin me-2" /> : <Save className="h-4 w-4 me-2" />}
                {t('save')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Sidebar>
  );
}
